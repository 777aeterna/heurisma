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
import os
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
) -> Path | None:
    """Download ``url`` into ``<appendix>/data/<filename>``; return the path, or None after logging why it failed.

    Network errors and HTTP 408/425/429/5xx are retried (``retries`` times, waiting ``backoff * 2**n`` seconds);
    other 4xx errors are not. Success appends to ``download_log.csv`` (with the SHA-256); failure appends a dated
    row to ``data_attempts.csv`` via ``local_data.append_attempt``.
    """
    appendix = Path(appendix)
    data_dir = (appendix / "data").resolve()
    dest = (data_dir / filename).resolve()
    if data_dir not in dest.parents:
        raise ValueError(f"filename {filename!r} escapes {data_dir}")
    attempts_csv = appendix / "data_attempts.csv"

    def fail(outcome: str, reason: str) -> None:
        local_data.append_attempt(attempts_csv, target, source, f"GET {url}", outcome, failure_reason=reason)

    if local_data.offline_enabled():
        fail("offline mode", "network disabled by HEURISMA_OFFLINE=1")
        return None
    if urlparse(url).scheme not in ("http", "https"):
        fail("rejected", f"unsupported URL scheme in {url!r} (only http and https are fetched)")
        return None

    import urllib.request as _rq

    ua = user_agent or os.environ.get("HEURISMA_UA") or DEFAULT_USER_AGENT
    last_outcome, last_reason = "error", "no attempt made"
    for n in range(retries + 1):
        try:
            with opener(_rq.Request(url, headers={"User-Agent": ua}), timeout=timeout) as resp:
                payload = resp.read(max_bytes + 1)
            break
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
        {"file": filename, "url": url, "retrieved_utc": local_data.utc_now(), "bytes": len(payload), "sha256": digest},
    )
    return dest
