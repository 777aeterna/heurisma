"""v0.9.0 Phase 1 tests: the HARKing check also catches computed results that H0/H1 state rounded (M35)."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402

HARK = r"HARKing"


def has(msgs: list[str], pattern: str) -> bool:
    return any(re.search(pattern, m, re.IGNORECASE) for m in msgs)


def prereg_msgs(h1: str, h0: str = "No difference between hybrid and office sites.", level: int = 2) -> tuple[list[str], list[str]]:
    tmp, ws = M.fresh_workspace()
    try:
        M._write_prereg(ws, {"H0": h0, "H1": h1})
        M.restamp_gates(ws)
        return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)
    finally:
        tmp.cleanup()


class TestRoundedForms(unittest.TestCase):
    def test_forms_cover_the_roundings_an_author_would_write(self) -> None:
        forms = validate_report._rounded_forms("30.1%")
        self.assertTrue({"30", "30.1"} <= forms, forms)
        self.assertTrue({"4", "4.01"} <= validate_report._rounded_forms("-4.01 pp"))
        self.assertIn("34.76", validate_report._rounded_forms("+34,76%"))
        self.assertIn("34.8", validate_report._rounded_forms("+34,76%"))
        self.assertIn("35", validate_report._rounded_forms("+34,76%"))

    def test_thousands_and_decimal_commas_are_both_considered(self) -> None:
        forms = validate_report._rounded_forms("4,900")
        self.assertIn("4900", forms)
        self.assertIn("4.9", forms)

    def test_non_numeric_value_has_no_forms(self) -> None:
        self.assertEqual(validate_report._rounded_forms("n/a"), set())
        self.assertEqual(validate_report._rounded_forms(""), set())


class TestHypothesisHits(unittest.TestCase):
    NUMS = {"a": "30.1%", "b": "9.6%", "c": "0.0286", "d": 590}

    def test_rounded_hits_need_two_distinct_figures_one_non_integer(self) -> None:
        hits = validate_report._hypothesis_number_hits("about 30% and 9,6%", self.NUMS)
        self.assertEqual(sorted(hits), ["30", "9.6"])

    def test_integers_only_are_not_enough(self) -> None:
        self.assertEqual(validate_report._hypothesis_number_hits("above 30% and below 590 sites", self.NUMS), [])

    def test_single_hit_is_not_enough(self) -> None:
        self.assertEqual(validate_report._hypothesis_number_hits("falls to 9,6%", self.NUMS), [])

    def test_years_and_conventional_thresholds_are_ignored(self) -> None:
        self.assertEqual(validate_report._hypothesis_number_hits("by 2027, with alpha 0.05 and 95% intervals, 1 or 5 sites", self.NUMS), [])


class TestPreregistrationHarking(unittest.TestCase):
    def test_rounded_results_are_flagged_with_code(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m35_harking_with_rounded_results(ws)
            M.restamp_gates(ws)
            _, w = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws)
            hit = [m for m in w if re.search(HARK, m)]
            self.assertTrue(hit and "rounded" in hit[0], w)
            self.assertEqual(validate_report.classify_message(hit[0])[0], "P2-PREREG")
        finally:
            tmp.cleanup()

    def test_rounded_results_are_an_error_at_level_3(self) -> None:
        e, _ = prereg_msgs("Hybrid cuts attrition by about 30% and brings it down to 9,6%.", level=3)
        self.assertTrue(has(e, HARK), e)

    def test_exact_results_are_still_flagged(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m24_harking_preregistration_contains_results(ws)
            M.restamp_gates(ws)
            _, w = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws)
            self.assertTrue(has(w, HARK), w)
        finally:
            tmp.cleanup()

    def test_legitimate_thresholds_are_not_flagged(self) -> None:
        for h1 in (
            "Attrition falls below 5% and output rises above 30% under hybrid.",
            "By 2027 hybrid sites keep more engineers than office sites, at the 0.05 level.",
            "Hybrid sites lose fewer engineers.",
        ):
            _, w = prereg_msgs(h1)
            self.assertFalse(has(w, HARK), (h1, w))

    def test_h0_is_checked_too(self) -> None:
        _, w = prereg_msgs("Hybrid helps.", h0="Hybrid does nothing, although it would cut attrition by 30% to 9,6%.")
        self.assertTrue(has(w, HARK), w)


if __name__ == "__main__":
    unittest.main()
