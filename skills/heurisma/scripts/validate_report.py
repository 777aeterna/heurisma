#!/usr/bin/env python3
"""Zero-dependency structural, content, and epistemic validator for Heurisma reports."""

from __future__ import annotations

import argparse
import csv
import re
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

LOW_TIER_SOURCE_RE = re.compile(
    r"\b(?:Tier\s*3|press\s+release|press\s+article|nota\s+de\s+prensa|prensa|news\s+article|blog\s+post|unverified|roadmap)\b",
    re.IGNORECASE,
)

FENCED_CODE_RE = re.compile(r"^```.*?^```[ \t]*$", flags=re.MULTILINE | re.DOTALL)


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


def _load_tier3_source_titles(report_dir: Path | None) -> list[str]:
    if report_dir is None:
        return []
    sources_csv = report_dir / "appendix" / "sources.csv"
    if not sources_csv.is_file():
        return []
    tier3_titles: list[str] = []
    try:
        with sources_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                tier = (row.get("tier") or "").strip()
                title = (row.get("source_title") or "").strip()
                if re.search(r"\bTier\s*3\b", tier, re.IGNORECASE) and len(title) >= 4:
                    tier3_titles.append(title.lower())
    except OSError:
        return []
    return tier3_titles


def validate_report(
    markdown_text: str,
    *,
    level: int | None = None,
    report_dir: Path | None = None,
) -> list[str]:
    """Return a list of validation error strings for a Heurisma markdown report (empty list = valid)."""
    errors: list[str] = []

    if not markdown_text or not markdown_text.strip():
        return ["Report is empty. All 7 required Heurisma sections must be present."]

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

    # 4. Check hypotheses ($H_0$ / H0 and $H_1$ / H1) strictly inside Section 2
    if "Framing & Hypotheses" in section_positions:
        sec2 = _extract_section_slice(clean_text, section_positions, "Framing & Hypotheses")
        has_h0 = bool(re.search(r"(\$H_0\$|\bH_0\b|\bH0\b|Null Hypothesis|Hip[oó]tesis nula)", sec2, re.IGNORECASE))
        has_h1 = bool(re.search(r"(\$H_1\$|\bH_1\b|\bH1\b|Alternative Hypothesis|Hip[oó]tesis alternativa)", sec2, re.IGNORECASE))
        if not (has_h0 and has_h1):
            errors.append(
                "Missing explicit null and alternative hypotheses (H_0 and H_1) inside Section 2 (Framing & Hypotheses)."
            )

    # 5. Validate Claim-Evidence Matrix structure, column count, >=2 rows, per-row tags, and Strong+Tier3/press ban
    tier3_titles = _load_tier3_source_titles(report_dir)
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

    # 6. Level 2 & Level 3 artifact checks (when --level and report_dir provided)
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

    # 7. Level 3 Reviewer #2 Disposition Table & Deferred -> Data Attempts cross-check
    if level == 3:
        has_r2_heading = bool(
            re.search(
                r"(?:Reviewer\s*#?2|Revisor\s*#?2|Disposition|Disposici[oó]n)",
                clean_text,
                re.IGNORECASE,
            )
        )
        # Accept plain, backticked (`Fixed`), or bold (**Fixed**) actions
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

    return errors


def validate_html(html_path: Path) -> list[str]:
    """Verify that a rendered HTML deliverable exists and preserves all 7 required sections."""
    if not html_path.is_file():
        return [f"Rendered HTML file not found: {html_path}"]

    html_text = html_path.read_text(encoding="utf-8")
    if not html_text.strip():
        return [f"Rendered HTML file is empty: {html_path}"]

    errors: list[str] = []
    for label, pattern in HTML_SECTION_PATTERNS:
        if not re.search(pattern, html_text, flags=re.IGNORECASE):
            errors.append(f"HTML deliverable missing required section heading: '{label}'")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Heurisma scientific inquiry report against structural, content, and epistemic gates."
    )
    parser.add_argument("report_path", type=Path, help="Path to the Markdown report file to validate.")
    parser.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3),
        default=None,
        help="Optional depth level (2 checks appendix/ artifacts; 3 also checks Reviewer #2 disposition table).",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Optional path to rendered report.html to verify alongside the Markdown report.",
    )
    args = parser.parse_args(argv)

    if not args.report_path.is_file():
        print(f"Error: File not found: {args.report_path}", file=sys.stderr)
        return 1

    content = args.report_path.read_text(encoding="utf-8")
    errors = validate_report(content, level=args.level, report_dir=args.report_path.parent)
    if args.html is not None:
        errors.extend(validate_html(args.html))

    if errors:
        print(f"Heurisma report validation FAILED ({len(errors)} violation(s)):", file=sys.stderr)
        for idx, err in enumerate(errors, start=1):
            print(f"  {idx}. {err}", file=sys.stderr)
        return 1

    print(f"Heurisma report validation PASSED: {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
