"""v0.7.0 Phase 2 (P0-4): decimal convention is decided per column; ambiguity is an error, never a guess."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import local_data  # noqa: E402


def read(text: str, name: str = "t.csv", **kw):
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / name
        p.write_text(text, encoding="utf-8")
        return local_data.read_csv(p, **kw)


class TestDecimalPerColumn(unittest.TestCase):
    def test_audit_case_point_decimals_next_to_comma_list_column(self) -> None:
        rows = read("id;value;tags\n1;3.1416;12,34\n2;2.7182;56,78\n")
        self.assertEqual(rows[0]["value"], 3.1416)  # was 31416 (x10^4) before v0.7.0
        self.assertEqual(rows[1]["value"], 2.7182)
        self.assertEqual(rows[0]["tags"], 12.34)

    def test_european_file_still_reads_decimal_comma_and_thousands_dots(self) -> None:
        rows = read("fecha;valor;total\n2026-01-01;1459,42;1.234.567,5\n2026-01-02;1470,10;2.000,25\n")
        self.assertEqual(rows[0]["valor"], 1459.42)
        self.assertEqual(rows[0]["total"], 1234567.5)
        self.assertEqual(rows[1]["total"], 2000.25)

    def test_comma_delimited_file_with_thousands_commas_and_point_decimals(self) -> None:
        rows = read('a,b\n"1,234.5",10\n"2,000.75",20\n')
        self.assertEqual(rows[0]["a"], 1234.5)
        self.assertEqual(rows[1]["a"], 2000.75)

    def test_comma_delimited_quoted_decimal_commas(self) -> None:
        rows = read('a,b\n"1,5",x\n"2,25",y\n')
        self.assertEqual(rows[0]["a"], 1.5)

    def test_column_that_mixes_conventions_raises_with_first_conflicting_cells(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            read("id;v\n1;1,5\n2;2.5\n3;3,5\n4;4.5\n")
        msg = str(ctx.exception)
        self.assertIn("column 'v'", msg)
        self.assertIn("1,5", msg)
        self.assertIn("2.5", msg)

    def test_text_column_with_a_few_numbers_is_not_converted(self) -> None:
        rows = read("id;note\n1;see table 3\n2;12\n3;n/a\n4;pending review\n")
        self.assertEqual([r["note"] for r in rows], ["see table 3", "12", "n/a", "pending review"])

    def test_numeric_column_keeps_non_numeric_cells_as_strings(self) -> None:
        rows = read("id;v\n1;1,5\n2;pending\n3;3,5\n")
        self.assertEqual([r["v"] for r in rows], [1.5, "pending", 3.5])

    def test_leading_zero_identifiers_are_kept_as_text(self) -> None:
        rows = read("code;n\n00123;5\n00456;6\n")
        self.assertEqual(rows[0]["code"], "00123")
        self.assertEqual(rows[0]["n"], 5)

    def test_keep_strings_protects_named_columns(self) -> None:
        rows = read("zip;n\n12345;1,5\n23456;2,5\n", keep_strings=["zip"])
        self.assertEqual(rows[0]["zip"], "12345")
        self.assertEqual(rows[0]["n"], 1.5)
        rows_all = read("zip;n\n12345;1,5\n", keep_strings=True)
        self.assertEqual(rows_all[0]["n"], "1,5")

    def test_empty_cells_are_none(self) -> None:
        rows = read("a;b\n1,5;\n;2,5\n")
        self.assertEqual((rows[0]["b"], rows[1]["a"]), (None, None))

    def test_ambiguous_single_dot_group_follows_the_file_convention(self) -> None:
        eu = read("a;b\n1.234;5,5\n2.345;6,5\n")
        self.assertEqual(eu[0]["a"], 1234)  # file uses decimal comma elsewhere -> thousands dot
        us = read("a;b\n1.234;5.5\n2.345;6.5\n")
        self.assertEqual(us[0]["a"], 1.234)

    def test_read_table_forwards_keep_strings(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "z.csv"
            p.write_text("zip;n\n12345;1,5\n", encoding="utf-8")
            self.assertEqual(local_data.read_table(p, keep_strings=["zip"])[0]["zip"], "12345")

    def test_na_sentinels_excluded_from_column_type_inference(self) -> None:
        rows = read(
            "year;mw;cost\n"
            "2015;NA;N/A\n"
            "2016;—;-\n"
            "2017;null;none\n"
            "2018;33.141,5;68,4\n"
            "2019;34.200,0;71,2\n"
        )
        self.assertIsNone(rows[0]["mw"])
        self.assertIsNone(rows[0]["cost"])
        self.assertIsNone(rows[1]["mw"])
        self.assertIsNone(rows[1]["cost"])
        self.assertIsNone(rows[2]["mw"])
        self.assertIsNone(rows[2]["cost"])
        self.assertAlmostEqual(rows[3]["mw"], 33141.5)
        self.assertAlmostEqual(rows[4]["cost"], 71.2)

    def test_mixed_decimal_column_with_na_still_raises(self) -> None:
        with self.assertRaises(ValueError):
            read("id;v\n1;NA\n2;1,5\n3;2.5\n")

    def test_worst_tier_inherits_weakest_cell_source(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            meta = Path(t) / "sources_metadata.csv"
            meta.write_text(
                "source_id,tier,title\n"
                "SRC_18,Tier 1,Official grid report\n"
                "SRC_45,Tier 3,Wikipedia summary\n",
                encoding="utf-8",
            )
            rows = [
                {"year": 2015, "mw": 33141, "primary_source_id": "SRC_18;SRC_45"},
                {"year": 2025, "mw": 44662, "primary_source_id": "SRC_18"},
            ]
            self.assertEqual(local_data.worst_tier(rows, "primary_source_id", meta), "Tier 3")
            self.assertEqual(local_data.worst_tier(rows[1:], "primary_source_id", meta), "Tier 1")


class TestPreviewShowsDetectedFormat(unittest.TestCase):
    def test_preview_lists_raw_and_converted_values_and_column_formats(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "m.csv"
            p.write_text("id;value;tags\n1;3.1416;12,34\n2;2.7182;56,78\n", encoding="utf-8")
            out = local_data.preview(p)
            self.assertIn("value: decimal-point", out)
            self.assertIn("tags: decimal-comma", out)
            self.assertIn("raw '12,34' -> 12.34", out)

    def test_preview_cli_reports_ambiguity_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "bad.csv"
            p.write_text("id;v\n1;1,5\n2;2.5\n", encoding="utf-8")
            res = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS_DIR / "local_data.py"), "preview", str(p)],
                capture_output=True,
                text=True, encoding="utf-8",
            )
            self.assertEqual(res.returncode, 1)
            self.assertNotIn("Traceback", res.stderr)
            self.assertIn("column 'v'", res.stderr)


if __name__ == "__main__":
    unittest.main()
