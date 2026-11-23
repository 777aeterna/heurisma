"""Shared layer of the paper connector: DOI normalisation, credential redaction, one request context for all providers.

Every call goes through ``Context.get`` -> ``fetch_lib.fetch``: retries with backoff, a size limit, an atomic write, a
SHA-256 row in ``download_log.csv`` and a dated failure row in ``data_attempts.csv``. The raw response is kept under
``appendix/data/papers/raw/`` so the run can be replayed offline. Credentials are redacted from everything logged.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import unquote, urlparse

_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import fetch_lib  # noqa: E402
import local_data  # noqa: E402
from contracts import PAPER_COLS  # noqa: E402

Record = dict[str, str]

# arXiv answers a burst with 429 and recovers slowly: wait three times longer between retries than for other providers
DEFAULT_BACKOFF_SCALE: dict[str, float] = {"arxiv": 3.0}
DEFAULT_MIN_INTERVAL: dict[str, float] = {"arxiv": 3.0, "crossref": 0.2, "openalex": 0.1, "europepmc": 0.1, "unpaywall": 0.1}
_CONSERVATIVE_ORDER = ("preprint", "report", "other", "conference", "dataset", "book", "article")
_TYPE_MAP = {
    "article": "article", "journal-article": "article", "review": "article", "letter": "article",
    "preprint": "preprint", "posted-content": "preprint",
    "report": "report", "working-paper": "report", "report-component": "report",
    "conference-paper": "conference", "proceedings-article": "conference", "proceedings": "conference",
    "book": "book", "book-chapter": "book", "monograph": "book", "edited-book": "book", "reference-book": "book",
    "dataset": "dataset",
}


class ProviderUnavailable(Exception):
    """A provider could not be reached or answered with an error; the cause is logged in data_attempts.csv."""


class NotFound(ProviderUnavailable):
    """The provider answered 404: the work is not in its catalogue."""


_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
_DOI_PREFIX_OK = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:?\s*|[(\[<])?$", re.IGNORECASE)


def normalize_doi(text: Any) -> str | None:
    """One canonical (lower-case, bare) DOI from any common spelling, or None.

    Accepts ``https://doi.org/…``, ``doi:…``, bracketed or punctuated DOIs; parentheses, ``<``/``>`` and ``;`` inside
    a DOI (old SICI DOIs) survive, while an unbalanced trailing bracket or punctuation is dropped."""
    if not isinstance(text, str) or not text.strip():
        return None
    s = re.sub(r"^<(.+)>$", r"\1", text.strip())
    m = _DOI_RE.search(s)
    if not m or not _DOI_PREFIX_OK.match(s[: m.start()].strip()):
        return None
    doi = m.group(0)
    while doi:
        if doi[-1] in ".,;:":
            doi = doi[:-1]
        elif doi[-1] in ")]>" and doi.count({")": "(", "]": "[", ">": "<"}[doi[-1]]) < doi.count(doi[-1]):
            doi = doi[:-1]
        else:
            break
    return doi.lower() if _DOI_RE.fullmatch(doi) else None


def record_key(text: Any) -> str | None:
    """The registry key of a work: its DOI, or ``arxiv:<id>`` / ``openalex:<id>`` for works that have none."""
    doi = normalize_doi(text)
    if doi:
        return doi
    if isinstance(text, str) and re.match(r"^(?:arxiv|openalex|epmc):\S+$", text.strip(), re.IGNORECASE):
        return text.strip().lower()
    return None


_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/(.+?)(?:v\d+)?(?:\.pdf)?$", re.IGNORECASE)
_OPENALEX_URL = re.compile(r"openalex\.org/(W\d+)", re.IGNORECASE)
_EPMC_URL = re.compile(r"europepmc\.org/article/([A-Za-z]+)/([^\s?#/]+)", re.IGNORECASE)


def url_for_key(key: str) -> str:
    """The link ``sources.csv`` carries for a registry key: doi.org for a DOI, and the database's own page for a work without one."""
    if key.startswith("arxiv:"):
        return f"https://arxiv.org/abs/{key[len('arxiv:'):]}"
    if key.startswith("openalex:"):
        return f"https://openalex.org/{key[len('openalex:'):].upper()}"
    if key.startswith("epmc:"):
        source, _, ident = key[len("epmc:"):].partition(":")
        return f"https://europepmc.org/article/{source.upper()}/{ident}"
    return f"https://doi.org/{key}" if normalize_doi(key) else key


def key_from_url(url: Any) -> str | None:
    """The registry key a source URL stands for: the inverse of ``url_for_key``, but a DOI is found *anywhere* in the URL
    (a publisher link such as ``https://publisher.example/articles/10.1234/x`` names the same work as ``doi.org/10.1234/x``)."""
    text = unquote(str(url or "")).strip()
    if not text:
        return None
    bare = re.split(r"[?#]", text, maxsplit=1)[0]
    if m := _ARXIV_URL.search(bare):
        return f"arxiv:{m.group(1).lower()}"
    if m := _OPENALEX_URL.search(text):
        return f"openalex:{m.group(1).lower()}"
    if m := _EPMC_URL.search(text):
        return f"epmc:{m.group(1).lower()}:{m.group(2)}"
    if m := _DOI_RE.search(text):
        return normalize_doi(re.split(r"[?#]", m.group(0), maxsplit=1)[0])
    return None


_SECRET_ENV = ("HEURISMA_OPENALEX_KEY", "HEURISMA_MAILTO")
_QUERY_SECRET = fetch_lib.QUERY_SECRET


def redact(text: str, env: Mapping[str, str] | None = None) -> str:
    """Remove credentials from a string that is about to be logged: query parameters and the env values themselves."""
    env = os.environ if env is None else env
    out = _QUERY_SECRET.sub(lambda m: f"{m.group(1)}=REDACTED", text)
    for name in _SECRET_ENV:
        value = (env.get(name) or "").strip()
        if len(value) >= 4:
            out = out.replace(value, "REDACTED")
    return out


def as_dict(value: Any) -> dict[str, Any]:
    """``value`` if it is a dict, else ``{}``: a field of the wrong type in an API payload is a missing field, not a crash."""
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    """``value`` if it is a list, a one-item list for a lone string or dict, else ``[]``."""
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, (str, dict)) and value else []


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]+")


def clean_text(value: Any, limit: int = 500) -> str:
    """Text that came from an API, made safe to write to a CSV and to print: control characters collapse to a space, the
    length is capped, and a leading ``=``, ``+``, ``-`` or ``@`` is neutralised with an apostrophe (spreadsheet formula injection)."""
    text = re.sub(r"\s+", " ", _CONTROL_CHARS.sub(" ", value if isinstance(value, str) else "")).strip()[:limit]
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def backoff_seconds(env: Mapping[str, str]) -> float:
    """``HEURISMA_BACKOFF`` as a non-negative number of seconds; a missing, empty or unusable value means 1.0."""
    raw = (env.get("HEURISMA_BACKOFF") or "").strip()
    try:
        value = float(raw) if raw else 1.0
    except ValueError:
        return 1.0
    if value != value or value in (float("inf"), float("-inf")):
        return 1.0
    return max(0.0, value)


def empty_record() -> Record:
    """A record with every registry column plus ``abstract`` (kept in the raw cache, never written to papers.csv)."""
    rec = {c: "" for c in PAPER_COLS}
    rec["abstract"] = ""
    return rec


_TITLE_STOP = {"the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "into", "its", "their", "than", "then"}
_LABEL_RE = re.compile(r"\((?:abstract only|preprint|report|web summary|metadata only)\)", re.IGNORECASE)


def _title_words(title: str) -> set[str]:
    cleaned = _LABEL_RE.sub(" ", title.lower())
    return {w for w in re.findall(r"[^\W_]{3,}", cleaned) if w not in _TITLE_STOP}


def title_overlap(a: str, b: str) -> float:
    """Share of the shorter title's words that the other title has (labels such as "(abstract only)" are ignored)."""
    wa, wb = _title_words(a), _title_words(b)
    return len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0.0


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def map_work_type(raw: Any) -> str:
    """The registry work type of a database's ``type``: ``""`` when it gave none (unknown), ``other`` when it gave one we do not map."""
    text = str(raw or "").strip().lower()
    return _TYPE_MAP.get(text, "other") if text else ""


def most_conservative_type(types: list[str]) -> str:
    present = [t for t in types if t]
    for t in _CONSERVATIVE_ORDER:
        if t in present:
            return t
    return present[0] if present else ""


def abstract_from_inverted_index(index: Any) -> str:
    """Rebuild an abstract from OpenAlex's ``{word: [positions]}`` (the only form it publishes)."""
    if not isinstance(index, dict) or not index:
        return ""
    slots: dict[int, str] = {}
    for word, positions in index.items():
        for pos in positions if isinstance(positions, list) else []:
            if isinstance(pos, int):
                slots[pos] = str(word)
    return " ".join(slots[i] for i in sorted(slots)).strip()


def jats_to_text(markup: Any) -> str:
    """Plain text of a Crossref/Europe PMC abstract (JATS or HTML markup)."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(markup or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^Abstract\s+", "", text)


def parse_xml(payload: bytes) -> ET.Element:
    """Parse an API's XML, refusing a DOCTYPE or entity declaration (entity-expansion bombs) as local_data does."""
    # look for the declaration in every encoding an XML parser would accept, not only the one the bytes happen to look like
    for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "utf-32"):
        if re.search(r"<!(?:DOCTYPE|ENTITY)\b", payload.decode(encoding, errors="ignore"), re.IGNORECASE):
            raise ProviderUnavailable("the response contains a DOCTYPE or ENTITY declaration and was refused")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ProviderUnavailable(f"the response is not valid XML ({exc})") from exc


@dataclass
class Context:
    """Everything one connector call needs: where the appendix is, the environment, and injectable time for tests."""

    appendix: Path
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    backoff: float = field(default_factory=lambda: backoff_seconds(os.environ))
    min_interval: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_MIN_INTERVAL))
    backoff_scale: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_BACKOFF_SCALE))
    warnings: list[str] = field(default_factory=list)
    last_raw: str = ""
    _last_call: dict[str, float] = field(default_factory=dict, repr=False)

    def base_url(self, provider: str, default: str) -> str:
        return (self.env.get(f"HEURISMA_{provider.upper()}_URL") or default).rstrip("/")

    @property
    def key(self) -> str:
        return (self.env.get("HEURISMA_OPENALEX_KEY") or "").strip()

    @property
    def mailto(self) -> str:
        return (self.env.get("HEURISMA_MAILTO") or "").strip()

    @property
    def offline(self) -> bool:
        return (self.env.get("HEURISMA_OFFLINE") or "").strip().lower() in {"1", "true", "yes", "on"}

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def _attempts(self) -> Path:
        return self.appendix / "data_attempts.csv"

    def configured_hosts(self) -> tuple[str, ...]:
        """Hosts the user pointed a provider at (``HEURISMA_<PROVIDER>_URL``): trusted even if they are local, as in the tests."""
        hosts = (urlparse(self.env.get(f"HEURISMA_{name}_URL") or "").hostname for name in ("OPENALEX", "CROSSREF", "EUROPEPMC", "ARXIV", "UNPAYWALL"))
        return tuple(h for h in hosts if h)

    def _reserve(self, raw_dir: Path, stem: str, ext: str) -> tuple[int, Path]:
        """Claim the next free cache file name by creating it exclusively, so two commands never write to the same one."""
        raw_dir.mkdir(parents=True, exist_ok=True)
        n = len(list(raw_dir.glob(f"{stem}-*"))) + 1
        while True:
            path = raw_dir / f"{stem}-{n:03d}.{ext}"
            try:
                os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return n, path
            except FileExistsError:
                n += 1

    def get(self, provider: str, url: str, *, ext: str = "json", headers: dict[str, str] | None = None) -> bytes:
        """GET ``url`` through ``fetch_lib.fetch`` and return the body; the credentialed URL is never logged."""
        raw_dir = self.appendix / "data" / "papers" / "raw"
        stem = f"{provider}-{sha256_text(redact(url, self.env))[:12]}"
        n, placeholder = self._reserve(raw_dir, stem, ext)
        try:
            path = self.download(provider, url, f"papers/raw/{stem}-{n:03d}.{ext}", headers=headers)
        except BaseException:
            placeholder.unlink(missing_ok=True)  # a failed request leaves no empty file behind
            raise
        self.last_raw = f"appendix/data/papers/raw/{stem}-{n:03d}.{ext}"
        return path.read_bytes()

    def download(self, provider: str, url: str, filename: str, *, headers: dict[str, str] | None = None, timeout: float = 20) -> Path:
        """Fetch ``url`` into ``appendix/data/<filename>`` (hashed and logged by ``fetch_lib``); raise on failure or offline mode."""
        shown = redact(url, self.env)
        if self.offline:
            local_data.append_attempt(self._attempts(), f"{provider} request", provider, f"GET {shown}", "offline mode", "network disabled by HEURISMA_OFFLINE=1")
            raise ProviderUnavailable("offline mode: HEURISMA_OFFLINE=1 blocks every connector request")
        wait = self.min_interval.get(provider, 0.0) - (self.clock() - self._last_call[provider]) if provider in self._last_call else 0.0
        if wait > 0:
            self.sleep(wait)
        failure: list[str] = []
        path = fetch_lib.fetch(
            f"{provider} request", provider, url, filename, self.appendix,
            backoff=self.backoff * self.backoff_scale.get(provider, 1.0), sleep=self.sleep, headers=headers, log_url=shown, timeout=timeout,
            allow_private=False, allowed_hosts=self.configured_hosts(), on_fail=lambda outcome, _reason: failure.append(outcome),
        )
        self._last_call[provider] = self.clock()
        if path is None:
            status = failure[-1] if failure else ""
            if status == "HTTP 404":
                raise NotFound(f"{provider}: not found")
            raise ProviderUnavailable(f"{provider} is unavailable ({status or 'error'}); see appendix/data_attempts.csv")
        return path

    def store(self, name: str, payload: bytes, ext: str, source_url: str) -> str:
        """Keep a response obtained elsewhere (an import) in the raw cache, hashed in download_log.csv; return its project path."""
        digest = hashlib.sha256(payload).hexdigest()
        filename = f"papers/raw/{name}-{digest[:12]}.{ext}"
        dest = self.appendix / "data" / filename
        if not dest.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            tmp.write_bytes(payload)
            tmp.replace(dest)
            fetch_lib._log_download(
                self.appendix / "download_log.csv",
                {"file": filename, "url": source_url, "retrieved_utc": local_data.utc_now(), "bytes": len(payload), "sha256": digest},
            )
        return f"appendix/data/{filename}"
