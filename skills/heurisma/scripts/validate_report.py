#!/usr/bin/env python3
"""Zero-dependency structural and epistemic calibration validator for Heurisma reports."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS: list[tuple[str, str]] = [
    ("Executive Summary", r"^##\s+1\.\s+Executive Summary\b"),
    ("Framing & Hypotheses", r"^##\s+2\.\s+Framing\s+&\s+Hypotheses\b"),
    ("Methodology & Evidence Standards", r"^##\s+3\.\s+Methodology\s+&\s+Evidence Standards\b"),
    ("Findings", r"^##\s+4\.\s+Findings\b"),
    (
        "Counter-Evidence & Alternative Explanations",
        r"^##\s+5\.\s+Counter-Evidence\s+&\s+Alternative Explanations\b",
    ),
    ("Claim-Evidence Matrix", r"^##\s+6\.\s+Claim-Evidence Matrix\b"),
    ("Limitations & Open Questions", r"^##\s+7\.\s+Limitations\s+&\s+Open Questions\b"),
]

EPISTEMIC_TAGS: tuple[str, ...] = (
    "[Strong]",
    "[Moderate]",
    "[Preliminary]",
    "[Speculative]",
)


def validate_report(markdown_text: str) -> list[str]:
    """Return a list of validation error strings for a Heurisma markdown report (empty list = valid)."""
    errors: list[str] = []

    if not markdown_text or not markdown_text.strip():
        return ["Report is empty. All 7 required Heurisma sections must be present."]

    # 1. Check all 7 required top-level section headings in order
    last_pos = -1
    section_positions: dict[str, int] = {}
    for label, pattern in REQUIRED_SECTIONS:
        match = re.search(pattern, markdown_text, flags=re.MULTILINE | re.IGNORECASE)
        if not match:
            errors.append(f"Missing required section: '## {label}'")
        else:
            pos = match.start()
            section_positions[label] = pos
            if pos < last_pos:
                errors.append(f"Section out of order: '## {label}' must appear after preceding sections.")
            last_pos = max(last_pos, pos)

    # 2. Check epistemic calibration tags
    tag_count = sum(markdown_text.count(tag) for tag in EPISTEMIC_TAGS)
    if tag_count == 0:
        errors.append(
            "Missing epistemic calibration tags: report must include at least one of "
            "[Strong], [Moderate], [Preliminary], or [Speculative]."
        )

    # 3. Check hypotheses ($H_0$ / H0 and $H_1$ / H1) inside Framing & Hypotheses
    if "Framing & Hypotheses" in section_positions:
        has_h0 = bool(re.search(r"(\$H_0\$|\bH_0\b|\bH0\b|Null Hypothesis)", markdown_text, re.IGNORECASE))
        has_h1 = bool(re.search(r"(\$H_1\$|\bH_1\b|\bH1\b|Alternative Hypothesis)", markdown_text, re.IGNORECASE))
        if not (has_h0 and has_h1):
            errors.append(
                "Missing explicit null and alternative hypotheses (H_0 and H_1) in Framing & Hypotheses."
            )

    # 4. Check Claim-Evidence Matrix contains a markdown table with at least 1 data row
    if "Claim-Evidence Matrix" in section_positions:
        start = section_positions["Claim-Evidence Matrix"]
        end = section_positions.get("Limitations & Open Questions", len(markdown_text))
        matrix_block = markdown_text[start:end]
        table_rows = [
            line.strip()
            for line in matrix_block.splitlines()
            if line.strip().startswith("|") and line.strip().endswith("|")
        ]
        # A valid markdown table needs header + separator + >=1 data row (>= 3 rows)
        if len(table_rows) < 3:
            errors.append(
                "Claim-Evidence Matrix section must contain a populated Markdown table "
                "(header, separator, and at least one claim-evidence row)."
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Heurisma scientific inquiry report against structural and epistemic gates."
    )
    parser.add_argument("report_path", type=Path, help="Path to the Markdown report file to validate.")
    args = parser.parse_args(argv)

    if not args.report_path.is_file():
        print(f"Error: File not found: {args.report_path}", file=sys.stderr)
        return 1

    content = args.report_path.read_text(encoding="utf-8")
    errors = validate_report(content)
    if errors:
        print(f"Heurisma report validation FAILED ({len(errors)} violation(s)):", file=sys.stderr)
        for idx, err in enumerate(errors, start=1):
            print(f"  {idx}. {err}", file=sys.stderr)
        return 1

    print(f"Heurisma report validation PASSED: {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
