"""Shared constants and parsing helpers (Markdown tables, sections, dates, hashes, citations)."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote



LOW_TIER_SOURCE_RE = re.compile(
    r"\b(?:Tier\s*3|press\s+release|press\s+article|nota\s+de\s+prensa|prensa|news\s+article|blog\s+post|unverified|roadmap)\b",
    re.IGNORECASE,
)

FENCED_CODE_RE = re.compile(r"^```.*?^```[ \t]*$", flags=re.MULTILINE | re.DOTALL)
FIG_MARKER_RE = re.compile(r"\{\{fig:([A-Za-z0-9_-]+)\}\}")
NUM_MARKER_RE = re.compile(r"\{\{num:([A-Za-z0-9_.-]+)\}\}")
LEFTOVER_BRACES_RE = re.compile(r"\{\{[^{}\n]{1,80}\}\}")
CITE_GROUP_RE = re.compile(r"\[(@[A-Za-z0-9_.-]+(?:\s*[;,]\s*@[A-Za-z0-9_.-]+)*)\]")
NUMERIC_CITE_RE = re.compile(r"\[[0-9]+\]")
UNCONVERTED_LATEX_RE = re.compile(r"(?<!\\)\$(?!\s)(?!\d[\d.,]*(?:\s|$|[^\\_^=a-zA-Z]))([^$\n]+?)(?<!\s)\$")
SHA_HEX_RE = re.compile(r"\b[0-9a-fA-F]{12,64}\b")

SPANISH_LEAKED_CHROME: tuple[tuple[str, str], ...] = (
    ("Figure N.", r"<strong>Figure\s+\d+\.</strong>"),
    ("Note:", r"<em>Note:</em>"),
    ("Source:", r"<em>Source:</em>"),
    ("Abstract", r'<div class="abstract-label">\s*Abstract\s*</div>'),
    ("References", r"<h2>\s*References\s*</h2>"),
    ("Median (P50)", r">Median\s*\(P50\)<"),
)


def _strip_fenced_code_blocks(text: str) -> str:
    return FENCED_CODE_RE.sub("", text)


def _split_md_table_row(row: str) -> list[str]:
    stripped = row.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", stripped)]


def _is_separator_row(cells: list[str]) -> bool:
    """Accept valid Markdown table separators including single-dash ':-', '-:', ':-:', '-'."""
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c.replace(" ", "")) for c in cells)


def _extract_section_slice(clean_text: str, section_positions: dict[str, int], target_label: str) -> str:
    if target_label not in section_positions:
        return ""
    start = section_positions[target_label]
    later_positions = [pos for pos in section_positions.values() if pos > start]
    end = min(later_positions) if later_positions else len(clean_text)
    return clean_text[start:end]


def _load_sources_rows(report_dir: Path | None) -> tuple[list[dict[str, str]], list[str]]:
    if report_dir is None:
        return [], []
    sources_csv = report_dir / "appendix" / "sources.csv"
    if not sources_csv.is_file():
        return [], []
    try:
        with sources_csv.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            return list(reader), fieldnames
    except OSError:
        return [], []


def _declared_sha(row: dict[str, str]) -> str:
    """The SHA-256 prefix a source row declares (sha256 column, else 'sha256 <hex>' in the title)."""
    col = SHA_HEX_RE.search((row.get("sha256") or "").strip())
    if col:
        return col.group(0).lower()
    m = re.search(r"sha256\s*[:=]?\s*([0-9a-fA-F]{12,64})\b", row.get("source_title") or "", re.IGNORECASE)
    return m.group(1).lower() if m else ""


def _local_source_path(url: str, report_dir: Path) -> Path:
    raw = url[len("file://"):] if url.startswith("file://") else url
    path = Path(unquote(raw))
    return path if path.is_absolute() else report_dir / path


def _file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", t)).strip().lower()


def _extract_citation_ids(text: str) -> list[str]:
    ids: list[str] = []
    for m in CITE_GROUP_RE.finditer(text):
        for tok in re.split(r"\s*[;,]\s*", m.group(1)):
            cid = tok.strip().lstrip("@")
            if cid:
                ids.append(cid)
    return ids


def _find_charts_json(report_dir: Path, appendix_dir: Path, explicit: Path | None = None) -> Path | None:
    """Locate charts.json: explicit path, then <report_dir>/charts.json, then <appendix>/charts.json."""
    if explicit is not None:
        return explicit if explicit.is_file() else None
    for candidate in (report_dir / "charts.json", appendix_dir / "charts.json"):
        if candidate.is_file():
            return candidate
    return None


HARDCODED_NUM_RE = re.compile(r"(?<![\w.@#{:-])(\d+[.,]\d+|\d{3,})(?![\w{])")
MIN_TYPED_NUMBERS = 5  # below this many retyped numbers the coverage warning stays quiet
MIN_MARKER_SHARE = 0.60
MIN_TYPED_SUMMARY = 3  # C5: verdict + Section 1 must not retype 3+ output figures without any placeholder
SUMMARY_NUM_RE = re.compile(r"(?<![\w.@#{:-])(\d+[.,]\d+|\d{2,})(?![\w{])")
SECTION_REF_RE = re.compile(r"(?:§\s*|\b(?:Secci[oó]n|Section|Sec\.)\s+)\d+(?:\.\d+)*", re.IGNORECASE)
LIMITATION_FALLBACKS: tuple[str, ...] = ("limitation", "limitación", "limitacion", "none", "ninguno", "n/a")
HOME_PATH_RE = re.compile(r"/home/[^/\s]+/|/Users/[^/\s]+|[A-Za-z]:\\Users\\", re.IGNORECASE)
GATE_MIN_CHARS = 400
SELECTION_LABEL_RE = re.compile(
    r"Selection bias: user-curated corpus|Sesgo de selecci[oó]n: corpus elegido por el usuario", re.IGNORECASE
)
MAX_SNAPSHOT_AGE_DAYS = 365
VERDICT_MAX_SENTENCES = 3
VERDICT_MAX_NUMBERS = 5
_VERDICT_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡`*\[(])")
_VERDICT_NUMBER_RE = re.compile(r"(?<![\w.@#{:-])[+\-\u2212]?\d+(?:[.,]\d+)*%?(?![\w}]|-[A-Za-z])")
_WEAK_TITLE_RE = re.compile(
    r"abstract[\s-]only|abstract\s+read|full\s+text\s+not\s+(?:read|retrieved)|solo\s+(?:el\s+)?resumen"
    r"|texto\s+no\s+recuperado|not\s+retrieved|no\s+recuperado",
    re.IGNORECASE,
)
_REVIEWER_CATEGORIES = (
    "Over-calibrated claims",
    "Unattempted data shortcuts",
    "Missing counter-evidence and controls",
    "Interdisciplinary and forecasting flaws",
    "Decisions inside the noise",
    "Provenance contradictions",
)
# C1: the minimum shape each gate answer must have; mirrors the Output section of references/agents/*.md
GATE_MARKERS: dict[str, list[tuple[str, str]]] = {
    "source_verifier": [(f"check {n}", rf"^\s*{n}[.)]\s+(?:PASS|FAIL)\b") for n in range(1, 8)]
    + [("SOURCE-VERIFIER: PASS|FAIL", r"^\s*SOURCE-VERIFIER:\s*(?:PASS|FAIL)\b")],
    "reviewer": [(title, re.escape(title)) for title in _REVIEWER_CATEGORIES]
    + [("MOST DAMAGING:", r"^\s*MOST DAMAGING:")],
    "qa": [(f"check {n}", rf"^\s*{n}[.)]?\s+(?:PASS|FAIL)\b") for n in range(1, 9)]
    + [("QA: PASS|FAIL", r"^\s*QA:\s*(?:PASS|FAIL)\b"), ("FAIL count: <n>", r"^\s*FAIL count:\s*\d+")],
}
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


_NAME_STOPWORDS = frozenset({"serie", "series", "datos", "data", "para", "from", "with", "sobre", "entre", "the"})


def _name_tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{4,}", folded) if w not in _NAME_STOPWORDS}


def _named_in_any(target: str, lines: list[str]) -> bool:
    """True when one line mentions at least 2 (and at least half) of the target's significant words.

    Reports paraphrase their data series ("Serie oficial del techo y piso" for "Serie diaria oficial del
    techo/piso de la banda"), so an exact-substring test misses the very limitation it should catch.
    """
    want = _name_tokens(target)
    if not want:
        return False
    for line in lines:
        folded = unicodedata.normalize("NFKD", line.lower()).encode("ascii", "ignore").decode()
        hits = sum(1 for w in want if w in folded)
        if hits >= 2 and hits >= 0.5 * len(want):
            return True
    return False


def _parse_utc(value: str):
    """ISO-8601 UTC (``2026-11-20T09:30:00Z``) or a bare date (midnight UTC) -> aware datetime, else None."""
    from datetime import datetime, timezone

    v = (value or "").strip()
    if not v:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        v += "T00:00:00+00:00"
    v = re.sub(r"Z$", "+00:00", v)
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


AS_OF_RE = re.compile(r"As-Of(?:\s+Date)?\)?\s*:?\**\s*:?\**\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def _as_of_date(markdown_text: str) -> str:
    for line in markdown_text.splitlines()[:20]:
        m = AS_OF_RE.search(line)
        if m:
            return m.group(1)
    return ""


def _resolve_run_start(report_dir: Path | None, explicit: str | None, markdown_text: str):
    """(run start, where it came from): appendix/run.json (tool-stamped), --run-since, or the report date."""
    if report_dir is not None:
        run_json = report_dir / "appendix" / "run.json"
        if run_json.is_file():
            try:
                data = json.loads(run_json.read_text(encoding="utf-8"))
                dt = _parse_utc(str(data.get("run_started_utc", ""))) if isinstance(data, dict) else None
                if dt is not None:
                    return dt, "appendix/run.json"
            except (OSError, json.JSONDecodeError):
                pass
    if explicit:
        dt = _parse_utc(_resolve_run_since(explicit, ""))
        if dt is not None:
            return dt, "--run-since"
    dt = _parse_utc(_as_of_date(markdown_text) or _resolve_run_since(None, markdown_text))
    return (dt, "report date") if dt is not None else (None, "")


def _resolve_run_since(explicit: str | None, markdown_text: str) -> str:
    """Run start (YYYY-MM-DD): the explicit value, else the first ISO date in the report's first 20 lines."""
    if explicit:
        m = DATE_RE.search(explicit)
        return m.group(1) if m else ""
    for line in markdown_text.splitlines()[:20]:
        m = DATE_RE.search(line)
        if m:
            return m.group(1)
    return ""
