"""v0.9.0 Phase 2 tests: the source catalogue and `data_as_of` are validated, not silently trusted (M36, M37)."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402

OK_TABLE = "parameter,value,primary_source_id\nreview_window_days,30,S1\n"


def has(msgs: list[str], pattern: str) -> bool:
    return any(re.search(pattern, m, re.IGNORECASE) for m in msgs)


def catalog_ws(meta_text: str | None, table_text: str = OK_TABLE):
    """A workspace with a registered table and (unless meta_text is None) its registered catalogue."""
    tmp, ws = M.fresh_workspace()
    data = ws / "appendix" / "data"
    data.joinpath("parameters.csv").write_text(table_text, encoding="utf-8")
    M._register_local_csv(ws, "appendix/data/parameters.csv", "C5", "Parameters table", "Tier 3")
    if meta_text is not None:
        data.joinpath("sources_metadata.csv").write_text(meta_text, encoding="utf-8")
        M._register_local_csv(ws, "appendix/data/sources_metadata.csv", "C6", "Source metadata", "Tier 3")
    return tmp, ws


def run(ws: Path, level: int = 2) -> tuple[list[str], list[str]]:
    M.restamp_gates(ws)
    return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)


def meta_msgs(meta_text: str | None, table_text: str = OK_TABLE, level: int = 2) -> tuple[list[str], list[str]]:
    tmp, ws = catalog_ws(meta_text, table_text)
    try:
        e, w = run(ws, level)
        keep = lambda ms: [m for m in ms if "sources_metadata" in m or "primary_source_id" in m]  # noqa: E731
        return keep(e), keep(w)
    finally:
        tmp.cleanup()


class TestCatalogueKeys(unittest.TestCase):
    def test_inner_space_in_source_id_is_an_error_with_code(self) -> None:
        e, _ = meta_msgs("source_id,tier,title\nS1,Tier 1,Office\nSRC _42,Tier 1,Bad key\n")
        hit = [m for m in e if "space" in m]
        self.assertTrue(hit and "SRC _42" in hit[0], e)
        self.assertEqual(validate_report.classify_message(hit[0]), ("SRC-META", "appendix/data/sources_metadata.csv"))

    def test_empty_source_id_is_an_error(self) -> None:
        e, _ = meta_msgs("source_id,tier,title\nS1,Tier 1,Office\n,Tier 2,No key\n")
        self.assertTrue(has(e, r"empty source_id|no source_id"), e)

    def test_non_canonical_tier_is_an_error(self) -> None:
        e, _ = meta_msgs("source_id,tier,title\nS1,3,Office\n")
        self.assertTrue(has(e, r"has tier '3'"), e)

    def test_clean_catalogue_is_silent(self) -> None:
        e, w = meta_msgs("source_id,tier,title\nS1,Tier 1,Office\n")
        self.assertEqual(e + w, [])


class TestUnresolvedIds(unittest.TestCase):
    def test_mutation_m36_lists_unresolved_ids_as_a_warning(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m36_unresolvable_primary_source_ids(ws)
            e, w = run(ws)
            hit = [m for m in w if "cites primary_source_id" in m]
            self.assertTrue(hit and "SRC _42" in hit[0] and "S9" in hit[0], (e, w))
            self.assertEqual(validate_report.classify_message(hit[0])[0], "SRC-META")
        finally:
            tmp.cleanup()

    def test_resolved_ids_are_silent_and_lists_are_split(self) -> None:
        _, w = meta_msgs(
            "source_id,tier,title\nS1,Tier 1,Office\nS2,Tier 3,Press\n",
            "parameter,value,primary_source_id\na,1,S1\nb,2,S1; S2\n",
        )
        self.assertFalse(has(w, r"cites primary_source_id"), w)

    def test_no_catalogue_means_no_message(self) -> None:
        e, w = meta_msgs(None, "parameter,value,primary_source_id\na,1,S9\n")
        self.assertFalse(has(e + w, r"cites primary_source_id|SRC-META"), (e, w))


class TestDataAsOf(unittest.TestCase):
    def test_future_data_as_of_in_catalogue_warns_l2_errors_l3(self) -> None:
        meta = "source_id,tier,data_as_of\nS1,Tier 1,2029-12\n"
        _, w2 = meta_msgs(meta)
        _, w3 = meta_msgs(meta, level=3)
        e3, _ = meta_msgs(meta, level=3)
        self.assertTrue(has(w2, r"data_as_of 2029-12"), w2)
        self.assertTrue(has(e3, r"data_as_of 2029-12"), (e3, w3))

    def test_same_month_year_only_and_past_values_are_fine(self) -> None:
        for value in ("2026-11", "2026-11-20", "2026", "2025-10", "2024-06-30"):
            e, w = meta_msgs(f"source_id,tier,data_as_of\nS1,Tier 1,{value}\n")
            self.assertFalse(has(e + w, r"data_as_of"), (value, e, w))

    def test_unparseable_value_is_ignored(self) -> None:
        e, w = meta_msgs("source_id,tier,data_as_of\nS1,Tier 1,Q4 of last year\n")
        self.assertFalse(has(e + w, r"data_as_of"), (e, w))

    def test_mutation_m37_sources_csv_row_has_code(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m37_data_as_of_after_report_date(ws)
            e, w = run(ws)
            hit = [m for m in w if "data_as_of" in m]
            self.assertTrue(hit and "C2" in hit[0], (e, w))
            self.assertEqual(validate_report.classify_message(hit[0]), ("P1-ASOF", "appendix/sources.csv"))
            e3, _ = run(ws, 3)
            self.assertTrue(has(e3, r"data_as_of 2027-03"), e3)
        finally:
            tmp.cleanup()


class TestAlternativeColumns(unittest.TestCase):
    def test_real_run_columns_do_not_crash_and_stay_silent(self) -> None:
        meta = (
            "source_id,title,institution,publication_date,exact_url,data_as_of,tier_classification\n"
            'S1,"Office table",Statistical office,2025-11-03,https://example.org/t.pdf,2025-10,Tier 1\n'
        )
        e, w = meta_msgs(meta)
        self.assertEqual(e + w, [])

    def test_catalogue_without_id_or_date_columns_does_not_crash(self) -> None:
        e, w = meta_msgs("title,tier\nOffice,Tier 1\n")
        self.assertIsInstance(e + w, list)


if __name__ == "__main__":
    unittest.main()
