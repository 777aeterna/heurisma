"""v0.10.1: gate laws the prompts state and the validator did not count (second audit, P1-2, P1-3, P1-7)."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402

from checks import gates  # noqa: E402

SV = "appendix/gates/source_verifier.md"
REVIEWER = """MODE: subagent
REVIEWED-SHA256: {sha}
REVIEWED-UTC: 2026-11-20T12:00:00Z
ANALYSIS-SHA256: {analysis}
QUOTE: appendix/sources.csv:1: "claim_id"
QUOTE: appendix/sources.csv:1: "source_title"

1. [1] The verdict rests on one series — the tier is too high — fetch the second series.
UNVERIFIED: 2. [3] A study nobody registered — not in sources.csv — verify it or drop it.
3. [6] The caption figure is typed by hand — untraced number — compute it in analysis.py.

1. Over-calibrated claims — 1 items
2. Unattempted data shortcuts — none found
3. Missing counter-evidence and controls — 1 items
4. Interdisciplinary and forecasting flaws — none found
5. Decisions inside the noise — none found
6. Provenance contradictions — 1 items

MOST DAMAGING: 1 — the verdict is over-calibrated.
""" + "Padding so the gate is long enough to count as a saved answer. " * 8


def messages(ws: Path, level: int) -> tuple[list[str], list[str]]:
    M.restamp_gates(ws)
    return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)


def set_verifier_outcome(ws: Path, outcome: str) -> None:
    p = ws / SV
    p.write_text(re.sub(r"^SOURCE-VERIFIER:.*$", f"SOURCE-VERIFIER: {outcome}", p.read_text(encoding="utf-8"), flags=re.MULTILINE), encoding="utf-8")


class TestSourceVerifierFailBlocks(unittest.TestCase):
    def run_case(self, level: int, cite: bool) -> tuple[list[str], list[str]]:
        tmp, ws = M.fresh_workspace()
        try:
            set_verifier_outcome(ws, "FAIL (1 problems)")
            report = ws / "report.md"  # the golden report already names its accepted problems: drop that citation first
            report.write_text(report.read_text(encoding="utf-8").replace("appendix/gates/source_verifier.md", "the source-verification gate"), encoding="utf-8")
            if cite:
                M._edit(ws, "report.md", "## 7. Limitations", "## 7. Limitations\n\nOne accepted source-verifier problem is justified in appendix/gates/source_verifier.md.\n")
            return messages(ws, level)
        finally:
            tmp.cleanup()

    def hits(self, msgs: list[str]) -> list[str]:
        return [m for m in msgs if "SOURCE-VERIFIER: FAIL" in m]

    def test_an_uncited_fail_is_an_error_at_level_3_and_a_warning_at_level_2(self) -> None:
        e3, _ = self.run_case(3, cite=False)
        self.assertTrue(self.hits(e3), e3)
        self.assertEqual(validate_report.classify_message(self.hits(e3)[0])[0], "GATE-SV")
        e2, w2 = self.run_case(2, cite=False)
        self.assertFalse(self.hits(e2))
        self.assertTrue(self.hits(w2), w2)

    def test_a_fail_the_report_names_and_justifies_is_accepted(self) -> None:
        e3, w3 = self.run_case(3, cite=True)
        self.assertFalse(self.hits(e3 + w3), e3 + w3)

    def test_a_pass_is_untouched(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            e, w = messages(ws, 3)
            self.assertFalse(self.hits(e + w))
        finally:
            tmp.cleanup()


class TestDispositionCoversEveryItem(unittest.TestCase):
    def test_items_and_rows_are_counted_without_the_coverage_block_or_the_separator(self) -> None:
        self.assertEqual(gates.reviewer_items(REVIEWER), 3)
        table = (
            "| # | Critique | Action |\n| :- | :- | :- |\n| 1 | tier | `Fixed` |\n| 2 | study | **Refuted** |\n"
            "| 3 | caption | Diferida |\n| 4 | prose mentions Fixed in a sentence | under review |\n"
        )
        self.assertEqual(gates.disposition_rows(table), 3)
        self.assertEqual(gates.reviewer_items("1. Over-calibrated claims — 1 items\nMOST DAMAGING: 1"), 0)

    def run_case(self, n_rows: int) -> list[str]:
        tmp, ws = M.fresh_workspace()
        try:
            gate = ws / "appendix" / "gates" / "reviewer.md"
            gate.write_text(REVIEWER.format(sha="0" * 64, analysis="0" * 64), encoding="utf-8")
            rows = "".join(f"| {i} | critique {i} | Fixed |\n" for i in range(1, n_rows + 1))
            M._edit(ws, "report.md", "## 6. Claim-Evidence Matrix",
                    f"### Reviewer #2 Disposition Table\n\n| # | Critique | Action |\n| :- | :- | :- |\n{rows}\n## 6. Claim-Evidence Matrix")
            e, w = messages(ws, 3)
            return [m for m in e + w if m.startswith("Reviewer #2 raised")]
        finally:
            tmp.cleanup()

    def test_three_items_and_one_row_is_an_error(self) -> None:
        hits = self.run_case(1)
        self.assertTrue(hits)
        self.assertIn("3", hits[0])
        self.assertIn("1", hits[0])
        self.assertEqual(validate_report.classify_message(hits[0])[0], "GATE-DISP")

    def test_three_items_and_three_rows_is_fine(self) -> None:
        self.assertEqual(self.run_case(3), [])


class TestAppendedPassIsRefused(unittest.TestCase):
    def test_two_header_lines_fail_even_if_the_first_matches(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            p = ws / SV
            p.write_text(p.read_text(encoding="utf-8") + "\n\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
            for level in (2, 3):
                e, _ = messages(ws, level)
                hits = [m for m in e if "REVIEWED-SHA256 lines" in m]
                self.assertTrue(hits, (level, e))
                self.assertEqual(validate_report.classify_message(hits[0])[0], "GATE-BINDING")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
