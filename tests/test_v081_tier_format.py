"""v0.8.1 Phase 4 (refactor) tests: the tier column must be canonical, or every 'Tier 3' rule is bypassed (M34)."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402


def with_tier(value: str) -> tuple[list[str], list[str]]:
    tmp, ws = M.fresh_workspace()
    try:
        def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
            for r in rows:
                if r["claim_id"] == "C1":
                    r["tier"] = value
            return rows, cols

        M._rewrite_csv(ws, "appendix/sources.csv", fn)
        M.restamp_gates(ws)
        return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws)
    finally:
        tmp.cleanup()


class TestTierFormat(unittest.TestCase):
    def test_non_canonical_tier_is_an_error_with_code(self) -> None:
        for bad in ("3", "T3", "Tier III", "tier-1", "", "Tier 4"):
            e, _ = with_tier(bad)
            hit = [m for m in e if "has tier" in m and "C1" in m]
            self.assertTrue(hit, (bad, e))
            self.assertEqual(validate_report.classify_message(hit[0]), ("SRC-TIER", "appendix/sources.csv"))

    def test_canonical_tiers_pass(self) -> None:
        for good in ("Tier 1", "Tier 2", "Tier 3", "tier 3", "Tier  3"):
            e, w = with_tier(good)
            self.assertFalse([m for m in e + w if re.search(r"has tier", m)], (good, e, w))

    def test_mutation_m34_is_caught(self) -> None:
        self.assertTrue(M.caught("M34", M.run_mutation("M34")))


if __name__ == "__main__":
    unittest.main()
