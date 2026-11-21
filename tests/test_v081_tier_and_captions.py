"""v0.8.1 Phase 2 tests: Tier inherited by local tables (M27), figures in chart captions (M30), `1,00×` baseline."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402


def has(msgs: list[str], pattern: str) -> bool:
    return any(re.search(pattern, m, re.IGNORECASE) for m in msgs)


def full(ws: Path, level: int = 2) -> tuple[list[str], list[str]]:
    M.restamp_gates(ws)
    return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)


class TestInheritedTier(unittest.TestCase):
    def test_strong_on_table_inheriting_tier3_is_p0_strong_error(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m27_strong_on_table_inheriting_tier3(ws)
            e, _ = full(ws)
            hit = [m for m in e if re.search(r"inherit", m, re.IGNORECASE)]
            self.assertTrue(hit and "C5" in hit[0], e)
            self.assertEqual(validate_report.classify_message(hit[0])[0], "P0-STRONG")
        finally:
            tmp.cleanup()

    def test_independent_tier1_source_in_the_same_row_keeps_it_valid(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m27_strong_on_table_inheriting_tier3(ws)
            M._edit(ws, "report.md", "Parameters table [@C5], Tier 2,", "Parameters table [@C5] with trial [@C2], Tier 2,")
            e, _ = full(ws)
            self.assertFalse(has(e, r"inherit"), e)
        finally:
            tmp.cleanup()

    def test_missing_metadata_file_is_silent(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m27_strong_on_table_inheriting_tier3(ws)
            (ws / "appendix" / "data" / "sources_metadata.csv").unlink()
            e, w = full(ws)
            self.assertFalse(has(e + w, r"inherit"), (e, w))
        finally:
            tmp.cleanup()

    def test_table_without_primary_source_id_column_is_silent(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m27_strong_on_table_inheriting_tier3(ws)
            (ws / "appendix" / "data" / "parameters.csv").write_text("parameter,value\nreview_window_days,30\n", encoding="utf-8")
            e, w = full(ws)
            self.assertFalse(has(e + w, r"inherit"), (e, w))
        finally:
            tmp.cleanup()

    def test_table_citing_a_tier2_primary_source_is_not_flagged(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m27_strong_on_table_inheriting_tier3(ws)
            (ws / "appendix" / "data" / "sources_metadata.csv").write_text(
                "source_id,tier,title\nS1,Tier 2,Statistical office table\n", encoding="utf-8"
            )
            e, _ = full(ws)
            self.assertFalse(has(e, r"inherit"), e)
        finally:
            tmp.cleanup()


class TestCaptionClosure(unittest.TestCase):
    def test_untraced_caption_figure_warns_l2_errors_l3_with_code(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m30_chart_caption_contradicts_output(ws)
            e2, w2 = full(ws, 2)
            hit = [m for m in w2 if re.search(r"caption", m, re.IGNORECASE)]
            self.assertTrue(hit and "subgroup_output" in hit[0] and "93,6" in hit[0], (e2, w2))
            self.assertEqual(validate_report.classify_message(hit[0])[0], "P1-UNTRACED-NUM")
            e3, _ = full(ws, 3)
            self.assertTrue(has(e3, r"caption.*untraced"), e3)
        finally:
            tmp.cleanup()

    def test_caption_figure_present_in_output_is_traced(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m30_chart_caption_contradicts_output(ws)
            out = ws / "appendix" / "output.txt"
            out.write_text(out.read_text(encoding="utf-8") + "\nbetween-station share 93.6 %\n", encoding="utf-8")
            e, w = full(ws)
            self.assertFalse(has(e + w, r"caption.*untraced"), (e, w))
        finally:
            tmp.cleanup()

    def test_dates_labels_and_engineering_constants_in_captions_are_ignored(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            import json

            charts = json.loads((ws / "charts.json").read_text(encoding="utf-8"))
            charts[0]["caption"] = "Figura 2. N-1 at 500 kV and 50 Hz, snapshot 2026-12-31, year 2026, Section 4.1."
            charts[0]["source"] = "Own computation, 2026-11"
            (ws / "charts.json").write_text(json.dumps(charts), encoding="utf-8")
            e, w = full(ws)
            self.assertFalse(has(e + w, r"caption.*untraced|source.*untraced"), (e, w))
        finally:
            tmp.cleanup()


class TestBaselineRatio(unittest.TestCase):
    def _table(self, cell: str):
        def add(ws: Path) -> None:
            # the golden numbers.json happens to contain +1.00; remove it so a "1,00" cell is not traced by accident
            M._edit(ws, "appendix/numbers.json", '"+1.00"', '"+0.99"')
            table = f"\n| Metric | Ratio |\n| :- | -: |\n| Baseline | {cell} |\n"
            M._edit(ws, "report.md", "## 5. Counter-Evidence", table + "\n## 5. Counter-Evidence")

        return add

    def test_one_times_baseline_is_not_untraced(self) -> None:
        for cell in ("1,00×", "1.00x", "1,0×"):
            tmp, ws = M.fresh_workspace()
            try:
                self._table(cell)(ws)
                e, w = full(ws)
                self.assertFalse(has(e + w, r"untraced|not found in appendix/output"), (cell, e, w))
            finally:
                tmp.cleanup()

    def test_other_ratio_is_still_untraced(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            self._table("1,37×")(ws)
            _, w = full(ws)
            self.assertTrue(has(w, r"untraced|not found in appendix/output"), w)
        finally:
            tmp.cleanup()

    def test_plain_one_point_zero_without_times_sign_is_still_checked(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            self._table("1,00")(ws)
            _, w = full(ws)
            self.assertTrue(has(w, r"untraced|not found in appendix/output"), w)
        finally:
            tmp.cleanup()


class TestMetadataColumnNames(unittest.TestCase):
    """A real run wrote `tier_classification` (not `tier`) in sources_metadata.csv; every id then looked unknown."""

    def _meta(self, header: str, tier: str) -> list[str]:
        tmp, ws = M.fresh_workspace()
        try:
            M.m27_strong_on_table_inheriting_tier3(ws)
            (ws / "appendix" / "data" / "sources_metadata.csv").write_text(
                f"source_id,title,{header}\nS1,Statistical office table,{tier}\n", encoding="utf-8"
            )
            e, _ = full(ws)
            return e
        finally:
            tmp.cleanup()

    def test_tier_classification_column_is_read(self) -> None:
        self.assertFalse(has(self._meta("tier_classification", "Tier 1"), r"inherit"))
        self.assertTrue(has(self._meta("tier_classification", "Tier 3"), r"inherit"))

    def test_plain_tier_column_still_read(self) -> None:
        self.assertFalse(has(self._meta("tier", "Tier 2"), r"inherit"))

    def test_worst_tier_helper_accepts_both_spellings(self) -> None:
        import tempfile

        import local_data

        rows = [{"primary_source_id": "S1"}]
        for header in ("tier", "tier_classification"):
            with tempfile.TemporaryDirectory() as d:
                meta = Path(d) / "m.csv"
                meta.write_text(f"source_id,{header}\nS1,Tier 1\n", encoding="utf-8")
                self.assertEqual(local_data.worst_tier(rows, "primary_source_id", meta), "Tier 1", header)


if __name__ == "__main__":
    unittest.main()
