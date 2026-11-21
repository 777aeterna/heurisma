#!/usr/bin/env python3
"""Zero-dependency structural, content, provenance, localization, and epistemic validator for Heurisma reports."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
import sys
from pathlib import Path

REQUIRED_SECTIONS: list[tuple[str, str]] = [
    (
        "Executive Summary",
        r"^##\s+1\.\s+(?:Executive Summary|Resumen\s+ejecutivo)\b",
    ),
    (
        "Framing & Hypotheses",
        r"^##\s+2\.\s+(?:Framing\s+&\s+Hypotheses|Encuadre\s+e\s+hip[oó]tesis)\b",
    ),
    (
        "Methodology & Evidence Standards",
        r"^##\s+3\.\s+(?:Methodology\s+&\s+Evidence Standards|Metodolog[ií]a\s+y\s+est[aá]ndares\s+de\s+evidencia)\b",
    ),
    (
        "Findings",
        r"^##\s+4\.\s+(?:Findings|Hallazgos)\b",
    ),
    (
        "Counter-Evidence & Alternative Explanations",
        r"^##\s+5\.\s+(?:Counter-Evidence\s+&\s+Alternative Explanations|Contraevidencia\s+y\s+explicaciones\s+alternativas)\b",
    ),
    (
        "Claim-Evidence Matrix",
        r"^##\s+6\.\s+(?:Claim-Evidence Matrix|Matriz\s+de\s+afirmaciones\s+y\s+evidencia)\b",
    ),
    (
        "Limitations & Open Questions",
        r"^##\s+7\.\s+(?:Limitations\s+&\s+Open Questions|Limitaciones\s+y\s+preguntas\s+abiertas)\b",
    ),
]

HTML_SECTION_PATTERNS: list[tuple[str, str]] = [
    (
        "Executive Summary",
        r"<h2[^>]*>\s*1\.\s*(?:Executive Summary|Resumen\s+ejecutivo)\b",
    ),
    (
        "Framing & Hypotheses",
        r"<h2[^>]*>\s*2\.\s*(?:Framing\s*(?:&amp;|&)\s*Hypotheses|Encuadre\s+e\s+hip[oó]tesis)\b",
    ),
    (
        "Methodology & Evidence Standards",
        r"<h2[^>]*>\s*3\.\s*(?:Methodology\s*(?:&amp;|&)\s*Evidence Standards|Metodolog[ií]a\s+y\s+est[aá]ndares\s+de\s+evidencia)\b",
    ),
    (
        "Findings",
        r"<h2[^>]*>\s*4\.\s*(?:Findings|Hallazgos)\b",
    ),
    (
        "Counter-Evidence & Alternative Explanations",
        r"<h2[^>]*>\s*5\.\s*(?:Counter-Evidence\s*(?:&amp;|&)\s*Alternative Explanations|Contraevidencia\s+y\s+explicaciones\s+alternativas)\b",
    ),
    (
        "Claim-Evidence Matrix",
        r"<h2[^>]*>\s*6\.\s*(?:Claim-Evidence Matrix|Matriz\s+de\s+afirmaciones\s+y\s+evidencia)\b",
    ),
    (
        "Limitations & Open Questions",
        r"<h2[^>]*>\s*7\.\s*(?:Limitations\s*(?:&amp;|&)\s*Open Questions|Limitaciones\s+y\s+preguntas\s+abiertas)\b",
    ),
]

# Supports both canonical English and localized Spanish epistemic tags
TAG_TO_CANONICAL: dict[str, str] = {
    "[Strong]": "Strong",
    "[Moderate]": "Moderate",
    "[Preliminary]": "Preliminary",
    "[Speculative]": "Speculative",
    "[Fuerte]": "Strong",
    "[Moderada]": "Moderate",
    "[Moderado]": "Moderate",
    "[Preliminar]": "Preliminary",
    "[Especulativa]": "Speculative",
    "[Especulativo]": "Speculative",
}

ALL_TAGS: tuple[str, ...] = tuple(TAG_TO_CANONICAL.keys())
STRONG_TAGS: tuple[str, ...] = ("[Strong]", "[Fuerte]")

CANONICAL_DATA_ATTEMPTS_COLS: tuple[str, ...] = (
    "target_series",
    "source_tried",
    "query_or_endpoint",
    "outcome",
    "failure_reason",
    "fallback_used",
)

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
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


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
GATE_FILES: tuple[str, ...] = ("source_verifier", "reviewer", "qa")
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


def validate_report_full(
    markdown_text: str,
    *,
    level: int | None = None,
    report_dir: Path | None = None,
    charts_path: Path | None = None,
    run_since: str | None = None,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a Heurisma markdown report."""
    errors: list[str] = []
    warnings: list[str] = []

    if not markdown_text or not markdown_text.strip():
        return ["Report is empty. All 7 required Heurisma sections must be present."], warnings

    clean_text = _strip_fenced_code_blocks(markdown_text)

    # 1. Check all 7 required top-level section headings in order (EN or ES)
    last_pos = -1
    section_positions: dict[str, int] = {}
    for label, pattern in REQUIRED_SECTIONS:
        match = re.search(pattern, clean_text, flags=re.MULTILINE | re.IGNORECASE)
        if not match:
            errors.append(f"Missing required section: '## {label}'")
        else:
            pos = match.start()
            section_positions[label] = pos
            if pos < last_pos:
                errors.append(f"Section out of order: '## {label}' must appear after preceding sections.")
            last_pos = max(last_pos, pos)

    # 2. Check minimum substance across required sections (rejects empty/filler stubs)
    min_words_by_section = {
        "Executive Summary": 30,
        "Findings": 30,
        "Counter-Evidence & Alternative Explanations": 12,
        "Limitations & Open Questions": 12,
    }
    for label, min_words in min_words_by_section.items():
        sec_text = _extract_section_slice(clean_text, section_positions, label)
        if sec_text:
            body_lines = [ln.strip() for ln in sec_text.splitlines()[1:] if ln.strip()]
            body_words = sum(len(ln.split()) for ln in body_lines)
            if body_words < min_words:
                errors.append(
                    f"Section '## {label}' lacks substantive content "
                    f"({body_words} words; minimum {min_words} words required)."
                )

    # 3. Check global presence of canonical/localized epistemic calibration tags
    tag_count = sum(clean_text.count(tag) for tag in ALL_TAGS)
    if tag_count == 0:
        errors.append(
            "Missing epistemic calibration tags: report must include canonical tags "
            "([Strong]/[Fuerte], [Moderate]/[Moderada], [Preliminary]/[Preliminar], or [Speculative]/[Especulativa])."
        )

    # 4. Check hypotheses ($H_0$ / H0 / H₀ and $H_1$ / H1 / H₁) strictly inside Section 2
    if "Framing & Hypotheses" in section_positions:
        sec2 = _extract_section_slice(clean_text, section_positions, "Framing & Hypotheses")
        has_h0 = bool(re.search(r"(\$H_0\$|\bH_0\b|\bH0\b|H₀|Null Hypothesis|Hip[oó]tesis nula)", sec2, re.IGNORECASE))
        has_h1 = bool(re.search(r"(\$H_1\$|\bH_1\b|\bH1\b|H₁|Alternative Hypothesis|Hip[oó]tesis alternativa)", sec2, re.IGNORECASE))
        if not (has_h0 and has_h1):
            errors.append(
                "Missing explicit null and alternative hypotheses (H_0 and H_1) inside Section 2 (Framing & Hypotheses)."
            )

    sources_rows, _ = _load_sources_rows(report_dir)
    tier3_titles = [
        (row.get("source_title") or "").strip().lower()
        for row in sources_rows
        if re.search(r"\bTier\s*3\b", (row.get("tier") or ""), re.IGNORECASE)
        and len((row.get("source_title") or "").strip()) >= 4
    ]

    kind_by_id = {
        (row.get("claim_id") or "").strip(): (row.get("kind") or "").strip().lower()
        for row in sources_rows
        if (row.get("claim_id") or "").strip()
    }

    # 5. Validate Claim-Evidence Matrix structure, column count, >=2 rows, per-row tags, and Strong+Tier3/press ban
    if "Claim-Evidence Matrix" in section_positions:
        matrix_block = _extract_section_slice(clean_text, section_positions, "Claim-Evidence Matrix")
        table_lines = [
            line.strip()
            for line in matrix_block.splitlines()
            if line.strip().startswith("|") and line.strip().endswith("|")
        ]
        if len(table_lines) < 3:
            errors.append(
                "Claim-Evidence Matrix section must contain a populated Markdown table "
                "(header, separator, and at least 2 claim-evidence rows)."
            )
        else:
            header_cells = _split_md_table_row(table_lines[0])
            if len(header_cells) < 4:
                errors.append(
                    f"Claim-Evidence Matrix table must have at least 4 columns "
                    f"(Claim, Discipline, Evidence/Tier, Confidence Tag); found {len(header_cells)}."
                )
            data_rows = [
                row
                for row in table_lines[1:]
                if not _is_separator_row(_split_md_table_row(row))
            ]
            if len(data_rows) < 2:
                errors.append(
                    f"Claim-Evidence Matrix table must contain at least 2 substantive claim rows; found {len(data_rows)}."
                )
            for row_idx, row in enumerate(data_rows, start=1):
                if not any(tag in row for tag in ALL_TAGS):
                    errors.append(
                        f"Claim-Evidence Matrix row {row_idx} is missing a canonical confidence tag "
                        f"([Strong], [Moderate], [Preliminary], or [Speculative])."
                    )
                if level == 3 and any(st in row for st in STRONG_TAGS):
                    row_ids = _extract_citation_ids(row)
                    if row_ids and all(kind_by_id.get(cid) == "own-computation" for cid in row_ids):
                        warnings.append(
                            f"Claim-Evidence Matrix row {row_idx} is [Strong] but its only evidence is own-computation "
                            f"({', '.join(row_ids)}); own computations are not independent evidence."
                        )
                if any(st in row for st in STRONG_TAGS):
                    row_lower = row.lower()
                    is_low_tier = bool(LOW_TIER_SOURCE_RE.search(row)) or any(
                        title in row_lower for title in tier3_titles
                    )
                    if is_low_tier:
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} pairs [Strong] with Tier 3 / press evidence, "
                            f"which violates the epistemic calibration scale."
                        )

    # 6. Level 2 & Level 3 artifact, figure (V1), citation (V2), provenance (V5), hygiene (V6), and verdict-number (P11) checks
    if level is not None and level >= 2 and report_dir is not None:
        appendix_dir = report_dir / "appendix"
        if not appendix_dir.is_dir():
            errors.append(f"Level {level} report requires an 'appendix/' directory at {appendix_dir}.")
        else:
            py_files = list(appendix_dir.glob("*.py"))
            if not py_files:
                errors.append(f"Level {level} report requires at least one reproducible Python script in {appendix_dir}.")
            if not (appendix_dir / "output.txt").is_file():
                errors.append(f"Level {level} report requires 'appendix/output.txt' with executed script output.")
            if not (appendix_dir / "sources.csv").is_file():
                errors.append(f"Level {level} report requires 'appendix/sources.csv' logging sources and access dates.")

            # V1: {{fig:id}} <-> charts.json consistency (W1: charts.json lives in the report root)
            charts_json = _find_charts_json(report_dir, appendix_dir, charts_path)
            if charts_json is None:
                where = charts_path if charts_path is not None else f"{report_dir / 'charts.json'} or {appendix_dir / 'charts.json'}"
                errors.append(f"Level {level} report requires charts.json: charts.json not found ({where}).")
            else:
                try:
                    charts_data = json.loads(charts_json.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"Invalid JSON in {charts_json}: {exc}")
                    charts_data = []
                if isinstance(charts_data, list) and charts_data:
                    try:
                        from svg_charts import chart_warnings
                    except ImportError:  # validator run in isolation from svg_charts.py
                        chart_warnings = None  # type: ignore[assignment]
                    if chart_warnings is not None:
                        for ch in charts_data:
                            if isinstance(ch, dict):
                                warnings.extend(chart_warnings(ch))
                    chart_ids = {str(ch.get("id") or f"fig_{i + 1}") for i, ch in enumerate(charts_data)}
                    placed_figs = FIG_MARKER_RE.findall(clean_text)
                    if not placed_figs:
                        errors.append(
                            f"Level >= 2 report with {charts_json.name} must place figures inline using {{{{fig:id}}}} markers."
                        )
                    for fid in placed_figs:
                        if fid not in chart_ids:
                            errors.append(f"Unknown figure marker '{{{{fig:{fid}}}}}' not found in {charts_json.name}.")
                    for cid in sorted(chart_ids - set(placed_figs)):
                        warnings.append(
                            f"Chart '{cid}' in {charts_json.name} is not placed inline via {{{{fig:{cid}}}}} (will render in Additional Figures)."
                        )

            # W2: every {{num:key}} marker must resolve against appendix/numbers.json
            used_num_keys = sorted(set(NUM_MARKER_RE.findall(clean_text)))
            if used_num_keys:
                known_keys: set[str] = set()
                numbers_json = appendix_dir / "numbers.json"
                if numbers_json.is_file():
                    try:
                        loaded_nums = json.loads(numbers_json.read_text(encoding="utf-8"))
                        if isinstance(loaded_nums, dict):
                            known_keys = {str(k) for k in loaded_nums}
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"Invalid JSON in appendix/numbers.json: {exc}")
                for key in used_num_keys:
                    if key not in known_keys:
                        errors.append(
                            f"Unresolved marker '{{{{num:{key}}}}}': key '{key}' not found in appendix/numbers.json."
                        )

            # V2: In-text citations [@id] <-> sources.csv
            if sources_rows:
                valid_claim_ids = {(r.get("claim_id") or "").strip() for r in sources_rows if (r.get("claim_id") or "").strip()}
                sec4 = _extract_section_slice(clean_text, section_positions, "Findings")
                all_cited_ids = _extract_citation_ids(clean_text)
                sec4_cited_ids = _extract_citation_ids(sec4)
                sec4_has_numeric_cite = bool(NUMERIC_CITE_RE.search(sec4))
                if not sec4_cited_ids and not sec4_has_numeric_cite:
                    errors.append(
                        "Level >= 2 report must include in-text citations (e.g. [@C1]) in Section 4 (Findings)."
                    )
                for cid in sorted(set(all_cited_ids) - valid_claim_ids):
                    errors.append(f"In-text citation '[@{cid}]' does not match any claim_id in appendix/sources.csv.")
                for uncited in sorted(valid_claim_ids - set(all_cited_ids)):
                    msg = f"Source '{uncited}' in appendix/sources.csv is never cited in the report text."
                    (errors if level >= 3 else warnings).append(msg)

                # V5a: file:// rows in sources.csv must include a sha256 hash
                for row_idx, row in enumerate(sources_rows, start=1):
                    url = (row.get("url") or "").strip()
                    is_own = (row.get("kind") or "").strip().lower() == "own-computation"
                    if url and not is_own and (url.startswith("file://") or "://" not in url):  # file:// or scheme-less local path
                        title = row.get("source_title") or ""
                        sha_col = (row.get("sha256") or "").strip()
                        has_hash = bool(SHA_HEX_RE.search(sha_col)) or (
                            "sha256" in title.lower() and bool(SHA_HEX_RE.search(title))
                        )
                        if not has_hash:
                            errors.append(
                                f"Local source row {row_idx} ('{url}') in appendix/sources.csv must include a SHA-256 hash "
                                f"(in source_title or sha256 column)."
                            )

            # V5b: Orphan files in appendix/data/ not referenced in download_log.csv or sources.csv
            data_dir = appendix_dir / "data"
            if data_dir.is_dir():
                provenance_corpus = ""
                for log_name in ("download_log.csv", "sources.csv"):
                    lp = appendix_dir / log_name
                    if lp.is_file():
                        provenance_corpus += "\n" + lp.read_text(encoding="utf-8", errors="replace")
                for fp in sorted(data_dir.rglob("*")):
                    if fp.is_file() and "__pycache__" not in fp.parts:
                        if fp.name not in provenance_corpus:
                            warnings.append(
                                f"Orphan data file 'appendix/data/{fp.relative_to(data_dir)}' is not logged in "
                                f"appendix/download_log.csv or appendix/sources.csv."
                            )

            # V5c: data_attempts.csv canonical columns check (D2)
            attempts_csv = appendix_dir / "data_attempts.csv"
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8", newline="") as fh:
                        reader = csv.reader(fh)
                        header = [c.strip() for c in next(reader, [])]
                    missing_cols = [c for c in CANONICAL_DATA_ATTEMPTS_COLS if c not in header]
                    if missing_cols:
                        errors.append(
                            f"appendix/data_attempts.csv is missing canonical column(s): {', '.join(missing_cols)}."
                        )
                except OSError as exc:
                    errors.append(f"Unable to read appendix/data_attempts.csv: {exc}")

            # F2: an own computation (the report's own code) can never be Tier 1 evidence
            for row in sources_rows:
                if (row.get("kind") or "").strip().lower() == "own-computation" and re.search(
                    r"\bTier\s*1\b", row.get("tier") or "", re.IGNORECASE
                ):
                    errors.append(
                        f"Source '{(row.get('claim_id') or '?').strip()}' has kind=own-computation but tier Tier 1; "
                        f"the report's own computation is not independent evidence (use Tier 2/3 or a different kind)."
                    )

            # F1: source described as retrieved/full text although data_attempts.csv logs a failed attempt for its URL
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8", newline="") as fh:
                        attempt_rows = list(csv.DictReader(fh))
                except OSError:
                    attempt_rows = []
                ok_outcomes = {"used", "ok", "success", "succeeded", "retrieved"}
                for row in sources_rows:
                    surl = (row.get("url") or "").strip()
                    stitle = (row.get("source_title") or "").lower()
                    if not surl or not re.search(r"full[\s-]?text|open[\s-]access|retrieved", stitle):
                        continue
                    for arow in attempt_rows:
                        outcome = (arow.get("outcome") or "").strip().lower()
                        touches = surl in (arow.get("query_or_endpoint") or "") or surl in (arow.get("source_tried") or "")
                        if touches and outcome and outcome not in ok_outcomes:
                            warnings.append(
                                f"Source '{(row.get('claim_id') or '?').strip()}' is described as full text/retrieved but "
                                f"appendix/data_attempts.csv logs a failed attempt for the same URL ({surl}): "
                                f"'{arow.get('outcome')}'."
                            )
                            break

            # P2: every subagent gate leaves a trace in appendix/gates/ (a manual record when no subagents exist)
            gates_dir = appendix_dir / "gates"
            gate_sink = errors if level == 3 else warnings
            for gate in GATE_FILES:
                if gate == "reviewer" and level != 3:  # Reviewer #2 is dispatched at Level 3 only
                    continue
                gpath = gates_dir / f"{gate}.md"
                gtext = gpath.read_text(encoding="utf-8", errors="replace") if gpath.is_file() else ""
                if not gtext.strip():
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is missing or empty; save the {gate.replace('_', '-')} gate output "
                        f"(or the manual checks that replaced it) there."
                    )
                    continue
                if len(gtext.strip()) < GATE_MIN_CHARS:
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is under {GATE_MIN_CHARS} characters; save the gate's full answer, "
                        f"not a placeholder."
                    )
                missing = [label for label, pattern in GATE_MARKERS[gate] if not re.search(pattern, gtext, re.MULTILINE | re.IGNORECASE)]
                if missing:
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is missing marker(s) its prompt requires: {', '.join(missing)} "
                        f"(see references/agents/{gate.replace('_', '-')}.md, Output section)."
                    )
                if gate == "qa" and not re.search(r"^QA:\s*PASS\b", gtext, re.MULTILINE):
                    if "gates/qa.md" not in markdown_text:
                        gate_sink.append(
                            "appendix/gates/qa.md has no 'QA: PASS' line; fix the failed checks, or name each accepted "
                            "FAIL with its justification in the report (cite appendix/gates/qa.md in Section 7)."
                        )

            # C8: gate files are embedded in report.html, so they must not quote home paths or literal markers
            if gates_dir.is_dir():
                for gpath in sorted(gates_dir.glob("*.md")):
                    gtext = gpath.read_text(encoding="utf-8", errors="replace")
                    if HOME_PATH_RE.search(gtext):
                        gate_sink_any = errors if level == 3 else warnings
                        gate_sink_any.append(
                            f"appendix/gates/{gpath.name} quotes a home-directory path; it is embedded in report.html, "
                            f"so report counts instead (e.g. 'home-directory paths in report.html: 0')."
                        )
                    if re.search(r"\{\{(?:num|fig):", gtext):
                        (errors if level == 3 else warnings).append(
                            f"appendix/gates/{gpath.name} contains a literal {{{{num:…}}}}/{{{{fig:…}}}} marker; write "
                            f"'number placeholder' or 'figure marker' instead."
                        )

            # P1: a limitation cannot rest on attempts inherited from an earlier run (needs attempted_utc column)
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8-sig", newline="") as fh:
                        att_reader = csv.DictReader(fh)
                        att_cols = [c.strip() for c in (att_reader.fieldnames or [])]
                        att_rows = list(att_reader)
                except OSError:
                    att_cols, att_rows = [], []
                since = _resolve_run_since(run_since, markdown_text)
                inherit_sink = errors if level == 3 else warnings
                if "attempted_utc" not in att_cols:
                    inherit_sink.append(
                        "appendix/data_attempts.csv has no attempted_utc column: every attempt is treated as inherited; "
                        "add the column and re-run the rungs behind each limitation."
                    )
                elif not since:
                    warnings.append("cannot determine run start; pass --run-since YYYY-MM-DD")
                else:
                    ok_out = {"used", "ok", "success", "succeeded", "retrieved"}
                    limits_text = _extract_section_slice(clean_text, section_positions, "Limitations & Open Questions")
                    leaning_lines = [ln for ln in limits_text.splitlines() if ln.strip()] + [
                        ln for ln in clean_text.splitlines() if re.search(r"\b(?:Deferred|Diferida)\b", ln, re.IGNORECASE)
                    ]
                    fresh_targets: set[str] = set()
                    stale_targets: dict[str, str] = {}
                    for arow in att_rows:
                        outcome = (arow.get("outcome") or "").strip().lower()
                        if not outcome or outcome in ok_out:
                            continue
                        target = (arow.get("target_series") or arow.get("source_tried") or "?").strip()
                        stamp = (arow.get("attempted_utc") or "").strip()[:10]
                        if stamp and stamp >= since:
                            fresh_targets.add(target)
                            continue
                        # C3: only failures that end in a limitation (no real fallback) or that the report leans on
                        fallback = (arow.get("fallback_used") or "").strip().lower()
                        ends_in_limitation = not fallback or fallback.startswith(LIMITATION_FALLBACKS)
                        named = _named_in_any(target, leaning_lines)
                        if ends_in_limitation or named:
                            stale_targets.setdefault(target, stamp or "no date")
                    for target, stamp in sorted(stale_targets.items()):
                        if target in fresh_targets:
                            continue
                        inherit_sink.append(
                            f"Data attempt for '{target}' in appendix/data_attempts.csv is inherited from an earlier run "
                            f"({stamp} < run start {since}); re-run the rung in this session before relying on the limitation."
                        )

            # V6: Hygiene warnings (__pycache__, .pyc, 0-byte files)
            pycache_found = False
            for fp in sorted(appendix_dir.rglob("*")):
                if "__pycache__" in fp.parts or fp.suffix == ".pyc":
                    pycache_found = True
                    continue
                if fp.is_file() and fp.stat().st_size == 0:
                    warnings.append(f"0-byte file detected in appendix: 'appendix/{fp.relative_to(appendix_dir)}'.")
            if pycache_found:
                warnings.append(
                    "Python bytecode artifacts (__pycache__ / .pyc) found in appendix/; run scripts with 'python3 -B'."
                )

            # P11: Optional verdict-number cross-check against appendix/output.txt
            output_txt = appendix_dir / "output.txt"
            if output_txt.is_file() and "{{num:" not in markdown_text:
                vm = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:\**\s*(.+)", clean_text, re.IGNORECASE)
                if vm:
                    out_text = output_txt.read_text(encoding="utf-8", errors="replace")
                    verdict_nums = re.findall(r"\b\d+(?:[.,]\d+)?\b", vm.group(1))
                    missing_nums = [
                        n for n in verdict_nums
                        if len(n) >= 2 and n not in out_text and n.replace(",", ".") not in out_text
                    ]
                    if missing_nums:
                        warnings.append(
                            f"Calibrated Verdict number(s) not found literally in appendix/output.txt: {', '.join(missing_nums[:5])}."
                        )

            # P3/C5: figures that come from output.txt should come through {{num:key}} (numbers.json), not be retyped
            if output_txt.is_file():
                out_txt = output_txt.read_text(encoding="utf-8", errors="replace")

                def _typed_from_output(section_text: str, pattern: re.Pattern[str]) -> set[str]:
                    body = re.sub(r"^#{1,6}\s.*$|\[@[^\]]+\]|\{\{[^}]+\}\}", "", section_text, flags=re.MULTILINE)
                    body = SECTION_REF_RE.sub("", body)
                    return {
                        t
                        for t in pattern.findall(body)
                        if not re.fullmatch(r"(?:19|20)\d\d", t)
                        and re.search(rf"(?<![\d.,]){re.escape(t)}(?!\d)", out_txt)
                    }

                summary = _extract_section_slice(clean_text, section_positions, "Executive Summary")
                typed_summary = _typed_from_output(summary, SUMMARY_NUM_RE)
                if len(typed_summary) >= MIN_TYPED_SUMMARY and not NUM_MARKER_RE.search(summary):
                    (errors if level == 3 else warnings).append(
                        f"Calibrated Verdict / Section 1 retypes {len(typed_summary)} figure(s) from appendix/output.txt "
                        f"({', '.join(sorted(typed_summary)[:4])}) and uses no {{{{num:key}}}} placeholder; export them to "
                        f"appendix/numbers.json and write {{{{num:key}}}}."
                    )

                findings = _extract_section_slice(clean_text, section_positions, "Findings")
                typed = _typed_from_output(findings, HARDCODED_NUM_RE)
                used = len(NUM_MARKER_RE.findall(markdown_text))
                if len(typed) >= MIN_TYPED_NUMBERS and used / (used + len(typed)) < MIN_MARKER_SHARE:
                    warnings.append(
                        f"numbers.json coverage is low: {len(typed)} number(s) in Section 4 appear in appendix/output.txt "
                        f"but only {used} {{{{num:key}}}} marker(s) are used (e.g. {', '.join(sorted(typed)[:3])}); "
                        f"write them as {{{{num:key}}}} so the text follows the analysis."
                    )

    # 7. Level 3 Reviewer #2 Disposition Table & Deferred -> Data Attempts cross-check
    if level == 3:
        has_r2_heading = bool(
            re.search(
                r"(?:Reviewer\s*#?2|Revisor\s*#?2|Disposition|Disposici[oó]n)",
                clean_text,
                re.IGNORECASE,
            )
        )
        has_r2_action = bool(
            re.search(
                r"\|\s*[`*]{0,2}(?:Fixed|Refuted|Deferred|Corregida|Refutada|Diferida)[`*]{0,2}\b",
                clean_text,
                re.IGNORECASE,
            )
        )
        if not (has_r2_heading and has_r2_action):
            errors.append(
                "Level 3 report requires a Reviewer #2 Disposition table recording each critique "
                "and its action (Fixed / Refuted / Deferred)."
            )

        has_deferred = bool(
            re.search(
                r"\|\s*[`*]{0,2}(?:Deferred|Diferida)[`*]{0,2}\b",
                clean_text,
                re.IGNORECASE,
            )
        )
        if has_deferred:
            has_attempts_file = report_dir is not None and (report_dir / "appendix" / "data_attempts.csv").is_file()
            sec3 = _extract_section_slice(clean_text, section_positions, "Methodology & Evidence Standards")
            has_attempts_table = bool(
                re.search(r"(?:Data\s+Attempts|Intentos\s+de\s+datos|Source\s+Tried|Fuente\s+probada)", sec3, re.IGNORECASE)
            )
            if not (has_attempts_file or has_attempts_table):
                errors.append(
                    "Level 3 report marks Reviewer #2 critique(s) as Deferred/Diferida without a logged "
                    "'appendix/data_attempts.csv' or Data Attempts table in Section 3."
                )

    return errors, warnings


def validate_report(
    markdown_text: str,
    *,
    level: int | None = None,
    report_dir: Path | None = None,
    charts_path: Path | None = None,
    run_since: str | None = None,
) -> list[str]:
    """Return a list of validation error strings for a Heurisma markdown report (empty list = valid)."""
    errors, _ = validate_report_full(
        markdown_text, level=level, report_dir=report_dir, charts_path=charts_path, run_since=run_since
    )
    return errors


def validate_html_full(html_path: Path) -> tuple[list[str], list[str]]:
    """Verify rendered HTML sections, Spanish language purity (V3), and unconverted LaTeX (V4)."""
    if not html_path.is_file():
        return [f"Rendered HTML file not found: {html_path}"], []

    html_text = html_path.read_text(encoding="utf-8")
    if not html_text.strip():
        return [f"Rendered HTML file is empty: {html_path}"], []

    errors: list[str] = []
    warnings: list[str] = []

    for label, pattern in HTML_SECTION_PATTERNS:
        if not re.search(pattern, html_text, flags=re.IGNORECASE):
            errors.append(f"HTML deliverable missing required section heading: '{label}'")

    # V3: Spanish HTML language purity check
    is_spanish_html = bool(
        re.search(r"<h2[^>]*>\s*(?:1\.\s*Resumen\s+ejecutivo|4\.\s*Hallazgos|6\.\s*Matriz\s+de\s+afirmaciones)", html_text, re.IGNORECASE)
    )
    if is_spanish_html:
        if re.search(r'<html\b[^>]*\blang="en"', html_text, re.IGNORECASE):
            errors.append("Spanish HTML report has wrong language attribute: expected <html lang=\"es\">, found lang=\"en\".")
        leaked = [label for label, pat in SPANISH_LEAKED_CHROME if re.search(pat, html_text)]
        if leaked:
            errors.append(
                f"Spanish HTML report leaks untranslated English chrome: {', '.join(leaked)}."
            )

    # W2: unresolved {{...}} markers left in visible HTML (strip <style>, <script>, <pre>, <code> first)
    visible_for_braces = re.sub(
        r"<(?:style|script|pre|code)\b[^>]*>.*?</(?:style|script|pre|code)>", " ", html_text, flags=re.DOTALL | re.IGNORECASE
    )
    leftovers = LEFTOVER_BRACES_RE.findall(visible_for_braces)
    if leftovers:
        errors.append(
            f"Rendered HTML contains unresolved marker(s) {', '.join(sorted(set(leftovers))[:4])}; "
            f"fix the key or figure id and re-render."
        )

    # V4: Unconverted LaTeX warning (strip <style>, <script>, <pre>, <code> before scanning)
    visible = re.sub(r"<(?:style|script|pre|code)\b[^>]*>.*?</(?:style|script|pre|code)>", " ", html_text, flags=re.DOTALL | re.IGNORECASE)
    latex_hits = UNCONVERTED_LATEX_RE.findall(visible)
    if latex_hits:
        sample = ", ".join(f"${h}$" for h in latex_hits[:4])
        warnings.append(f"Unconverted LaTeX expression(s) detected in HTML: {sample}.")

    return errors, warnings


def validate_html(html_path: Path) -> list[str]:
    """Verify that a rendered HTML deliverable exists, preserves all 7 sections, and respects language purity."""
    errors, _ = validate_html_full(html_path)
    return errors


SOURCE_HASH_RE = re.compile(r"<!--\s*heurisma-sources:\s*sha256:([0-9a-f]{12})\s*-->")


def _load_render_module():
    """Import render_report.py by explicit path so it also works under ``python3 -I`` (no script dir on sys.path)."""
    import importlib.util

    path = Path(__file__).resolve().parent / "render_report.py"
    spec = importlib.util.spec_from_file_location("_heurisma_render_report", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_html_freshness(html_path: Path, report_path: Path, charts_path: Path | None = None) -> list[str]:
    """Warn when the rendered HTML predates a change to the report, charts.json, numbers.json or appendix/ (W3)."""
    if not html_path.is_file():
        return []
    try:
        compute_source_hash = _load_render_module().compute_source_hash
    except Exception as exc:  # never skip the freshness check silently
        return [f"freshness check skipped: could not load render_report.py ({exc})."]
    html_text = html_path.read_text(encoding="utf-8", errors="replace")
    m = SOURCE_HASH_RE.search(html_text)
    if not m:
        return [
            f"HTML '{html_path.name}' has no source hash (rendered before v0.5.0); "
            f"re-render with render_report.py so staleness can be detected."
        ]
    report_dir = report_path.parent
    appendix_dir = report_dir / "appendix"
    charts = _find_charts_json(report_dir, appendix_dir, charts_path)
    current = compute_source_hash(report_path, charts, None, appendix_dir if appendix_dir.is_dir() else None)
    if current != m.group(1):
        return [
            f"HTML '{html_path.name}' is stale (out of date): sources hash {current} != embedded {m.group(1)}; "
            f"re-run render_report.py."
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Heurisma scientific inquiry report against structural, content, provenance, and epistemic gates."
    )
    parser.add_argument("report_path", type=Path, help="Path to the Markdown report file to validate.")
    parser.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3),
        default=None,
        help="Optional depth level (2 checks appendix/, figures, citations, provenance; 3 also checks Reviewer #2 disposition table).",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Optional path to rendered report.html to verify alongside the Markdown report.",
    )
    parser.add_argument(
        "--charts",
        type=Path,
        default=None,
        help="Optional explicit path to charts.json (default: <report dir>/charts.json, then appendix/charts.json).",
    )
    parser.add_argument(
        "--run-since",
        default=None,
        metavar="YYYY-MM-DD",
        help="Start date of this run; data_attempts.csv failures older than it count as inherited "
        "(default: first ISO date in the report's first 20 lines).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat validation warnings as hard errors (exit code 1).",
    )
    args = parser.parse_args(argv)

    if not args.report_path.is_file():
        print(f"Error: File not found: {args.report_path}", file=sys.stderr)
        return 1

    content = args.report_path.read_text(encoding="utf-8")
    errors, warnings = validate_report_full(
        content, level=args.level, report_dir=args.report_path.parent, charts_path=args.charts, run_since=args.run_since
    )
    if args.html is not None:
        html_errors, html_warnings = validate_html_full(args.html)
        errors.extend(html_errors)
        warnings.extend(html_warnings)
        warnings.extend(check_html_freshness(args.html, args.report_path, args.charts))

    if warnings:
        print(f"Heurisma report warnings ({len(warnings)}):", file=sys.stderr)
        for idx, warn in enumerate(warnings, start=1):
            print(f"  [WARN {idx}] {warn}", file=sys.stderr)

    if errors or (args.strict and warnings):
        total = len(errors) + (len(warnings) if args.strict else 0)
        print(f"Heurisma report validation FAILED ({total} violation(s)):", file=sys.stderr)
        for idx, err in enumerate(errors, start=1):
            print(f"  {idx}. {err}", file=sys.stderr)
        return 1

    print(f"Heurisma report validation PASSED: {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
