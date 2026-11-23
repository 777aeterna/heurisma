#!/usr/bin/env python3
"""Zero-dependency download helper for ``appendix/fetch_data.py``: retries with exponential backoff, a configurable
User-Agent, a size limit, an optional expected checksum, a ``download_log.csv`` row on success and a canonical,
tool-dated ``data_attempts.csv`` row on failure.

    import sys; sys.path.insert(0, "<skill-dir>/scripts")
    from fetch_lib import fetch
    fetch("Wholesale FX", "Central Bank API v4", "https://api.example.org/v4/series.csv", "series.csv", Path("appendix"))

``HEURISMA_OFFLINE=1`` skips the network and logs ``offline mode`` (rehearse the local-data rung);
``HEURISMA_UA`` overrides the default User-Agent. Only http(s) URLs are fetched.
"""

from __future__ import annotations

import csv
import hashlib
import ipaddress
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from contracts import __version__ as __version__  # noqa: E402
import local_data  # noqa: E402

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) research-script (+reproducible appendix)"
DOWNLOAD_COLS = ("file", "url", "retrieved_utc", "bytes", "sha256")
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
MAX_BYTES_DEFAULT = 50 * 1024 * 1024
# A credential in a query string (an API key, a contact address) must never reach a log: the connector passes its own
# redacted ``log_url``; for any other caller the same pattern is the default.
QUERY_SECRET = re.compile(r"(?i)\b(api_key|apikey|mailto|email)=([^&\s\"']+)")


def scrub_url(url: str) -> str:
    """``url`` with the value of every credential-like query parameter replaced by ``REDACTED``."""
    return QUERY_SECRET.sub(lambda m: f"{m.group(1)}=REDACTED", url)


class Refused(urllib.error.URLError):
    """A request the guard refuses (a private address, a redirect to another scheme): final, never retried."""


def _is_private_host(host: str) -> bool:
    """True when ``host`` is, or resolves to, a loopback, private, link-local, reserved, multicast or unspecified address."""
    if host.lower().endswith((".invalid", ".test", ".example")):  # reserved names that never resolve: no lookup needed
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):
        return False  # it does not resolve: the request will fail on its own and be logged as such
    for info in infos:
        try:
            addr = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast or addr.is_unspecified:
            return True
    return False


def _blocked(host: str | None, allowed_hosts: tuple[str, ...]) -> bool:
    if not host:
        return True
    if host.lower() in {h.lower() for h in allowed_hosts}:
        return False
    return _is_private_host(host)


class _GuardedRedirects(urllib.request.HTTPRedirectHandler):
    """Follow only http(s) redirects and, when asked, never to a private or local address (a public link can redirect inwards)."""

    def __init__(self, *, block_private: bool, allowed_hosts: tuple[str, ...]) -> None:
        self.block_private, self.allowed_hosts = block_private, allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        parts = urlparse(newurl)
        if parts.scheme not in ("http", "https"):
            raise Refused(f"redirect to '{parts.scheme}:' refused (only http and https are followed)")
        if self.block_private and _blocked(parts.hostname, self.allowed_hosts):
            raise Refused(f"redirect to a private or local address ({parts.hostname}) refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _log_download(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(DOWNLOAD_COLS))
        if new:
            writer.writeheader()
        writer.writerow(row)


def fetch(
    target: str,
    source: str,
    url: str,
    filename: str,
    appendix: str | Path = "appendix",
    *,
    retries: int = 3,
    backoff: float = 1.0,
    timeout: float = 20,
    user_agent: str | None = None,
    expected_sha256: str | None = None,
    max_bytes: int = MAX_BYTES_DEFAULT,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
    headers: dict[str, str] | None = None,
    log_url: str | None = None,
    allow_private: bool = True,
    allowed_hosts: tuple[str, ...] = (),
    on_fail: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Download ``url`` into ``<appendix>/data/<filename>``; return the path, or None after logging why it failed.

    Network errors and HTTP 408/425/429/5xx are retried (``retries`` times, waiting ``backoff * 2**n`` seconds);
    other 4xx errors are not. Success appends to ``download_log.csv`` (with the SHA-256); failure appends a dated
    row to ``data_attempts.csv`` via ``local_data.append_attempt``.

    ``headers`` are sent along with the User-Agent. ``log_url`` is what both logs record instead of ``url``: pass the
    URL with its API key and contact address redacted so that no credential is ever written to the appendix.

    ``allow_private=False`` refuses a URL (and any redirect) whose host is a private, loopback or link-local address, except the
    hosts in ``allowed_hosts``: use it for a link that came out of a response, which an attacker can point at the user's network.
    The default keeps the old behaviour so that a user's own ``fetch_data.py`` can read an intranet source. The host is resolved
    before the request and again by the HTTP client, so this is a guard against careless links, not against a hostile DNS server.
    Redirects to any scheme but http(s) are always refused. ``on_fail(outcome, reason)`` is called with what was logged when the
    download fails (so a caller can tell a 404 from an outage without rereading ``data_attempts.csv``).
    """
    appendix = Path(appendix)
    data_dir = (appendix / "data").resolve()
    dest = (data_dir / filename).resolve()
    if data_dir not in dest.parents:
        raise ValueError(f"filename {filename!r} escapes {data_dir}")
    attempts_csv = appendix / "data_attempts.csv"

    shown = log_url or scrub_url(url)

    def fail(outcome: str, reason: str) -> None:
        local_data.append_attempt(attempts_csv, target, source, f"GET {shown}", outcome, failure_reason=reason)
        if on_fail is not None:
            on_fail(outcome, reason)

    if local_data.offline_enabled():
        fail("offline mode", "network disabled by HEURISMA_OFFLINE=1")
        return None
    if urlparse(url).scheme not in ("http", "https"):
        fail("rejected", f"unsupported URL scheme in {shown!r} (only http and https are fetched)")
        return None

    if not allow_private and _blocked(urlparse(url).hostname, allowed_hosts):
        fail("rejected", "the URL points to a private or local address; a link taken from a response is fetched only if it is public")
        return None

    import urllib.request as _rq

    if opener is urllib.request.urlopen:
        opener = urllib.request.build_opener(_GuardedRedirects(block_private=not allow_private, allowed_hosts=allowed_hosts)).open

    ua = user_agent or os.environ.get("HEURISMA_UA") or DEFAULT_USER_AGENT
    last_outcome, last_reason = "error", "no attempt made"
    for n in range(retries + 1):
        try:
            with opener(_rq.Request(url, headers={"User-Agent": ua, **(headers or {})}), timeout=timeout) as resp:
                payload = resp.read(max_bytes + 1)
            break
        except Refused as exc:
            fail("rejected", str(exc))
            return None
        except urllib.error.HTTPError as exc:
            last_outcome, last_reason = f"HTTP {exc.code}", str(exc)
            if exc.code not in RETRY_STATUS:
                fail(last_outcome, last_reason)
                return None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_outcome, last_reason = type(exc).__name__, str(getattr(exc, "reason", exc))
        if n < retries:
            sleep(backoff * (2 ** n))
    else:
        fail(last_outcome, f"{last_reason} (after {retries + 1} attempts)")
        return None

    if len(payload) > max_bytes:
        fail("rejected", f"response larger than {max_bytes} bytes")
        return None
    digest = hashlib.sha256(payload).hexdigest()
    if expected_sha256 and not digest.startswith(expected_sha256.lower()):
        fail("rejected", f"checksum mismatch: got {digest[:16]}, expected {expected_sha256[:16]}")
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(payload)
    tmp.replace(dest)
    _log_download(
        appendix / "download_log.csv",
        {"file": filename, "url": shown, "retrieved_utc": local_data.utc_now(), "bytes": len(payload), "sha256": digest},
    )
    return dest
