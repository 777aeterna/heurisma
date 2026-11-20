import csv
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import local_data  # noqa: E402


def _build_minimal_xlsx(path: Path) -> None:
    """Create a minimal valid .xlsx file with title row, header row, data rows (shared string, inlineStr, number, bool), and 1-cell footer note."""
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Series" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    shared_strings_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5">'
        "<si><t>Monthly FX Report</t></si>"
        "<si><t>date_serial</t></si>"
        "<si><t>rate</t></si>"
        "<si><t>verified</t></si>"
        "<si><t>Source: Central Bank</t></si>"
        "</sst>"
    )
    # Row 1: Title (1 text cell)
    # Row 2: Header (3 text cells: date_serial, rate, verified)
    # Row 3: Data (46311 -> 2026-10-16, 85.4, true, inlineStr note)
    # Row 4: Data (46312 -> 2026-10-17, 100, false)
    # Row 5: Footer note (1 text cell -> must be dropped by read_table)
    sheet1_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        '<row r="1"><c r="A1" t="s"><v>0</v></c></row>'
        '<row r="2">'
        '<c r="A2" t="s"><v>1</v></c>'
        '<c r="B2" t="s"><v>2</v></c>'
        '<c r="C2" t="s"><v>3</v></c>'
        '<c r="D2" t="inlineStr"><is><t>label</t></is></c>'
        "</row>"
        '<row r="3">'
        '<c r="A3"><v>46311</v></c>'
        '<c r="B3"><v>85.4</v></c>'
        '<c r="C3" t="b"><v>1</v></c>'
        '<c r="D3" t="inlineStr"><is><t>ok</t></is></c>'
        "</row>"
        '<row r="4">'
        '<c r="A4"><v>46312</v></c>'
        '<c r="B4"><v>100</v></c>'
        '<c r="C4" t="b"><v>0</v></c>'
        '<c r="D4" t="inlineStr"><is><t>check</t></is></c>'
        "</row>"
        '<row r="5"><c r="A5" t="s"><v>4</v></c></row>'
        "</sheetData>"
        "</worksheet>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        zf.writestr("xl/sharedStrings.xml", shared_strings_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet1_xml)


class TestLocalData(unittest.TestCase):
    def test_inventory_lists_supported_files_with_sha12_and_handles_missing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "rates.csv").write_text("date,val\n2026-01,100\n", encoding="utf-8")
            (root / "notes.pdf").write_bytes(b"%PDF-1.4\n")
            (root / "ignored.bin").write_bytes(b"\x00\x01\x02")
            pycache = root / "__pycache__"
            pycache.mkdir()
            (pycache / "mod.txt").write_text("ignore", encoding="utf-8")

            rows = local_data.inventory([str(root)])
            paths = {Path(r["path"]).name: r for r in rows}
            self.assertIn("rates.csv", paths)
            self.assertIn("notes.pdf", paths)
            self.assertNotIn("ignored.bin", paths)
            self.assertNotIn("mod.txt", paths)
            self.assertEqual(paths["rates.csv"]["kind"], "csv")
            self.assertEqual(len(paths["rates.csv"]["sha256_12"]), 12)
            self.assertEqual(paths["notes.pdf"]["kind"], "pdf")

            # Missing directory must return empty list without raising
            missing_rows = local_data.inventory([str(root / "does_not_exist")])
            self.assertEqual(missing_rows, [])

    def test_csv_semicolon_decimal_comma_and_latin1(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "european.csv"
            # Latin-1 accented header + semicolon delimiter + thousands dot + decimal comma
            content = "Región;Precio;Cantidad\nCórdoba;1.234,5;42\nSanta Fe;987,25;10\n"
            csv_path.write_bytes(content.encode("latin-1"))

            rows = local_data.read_table(csv_path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["Región"], "Córdoba")
            self.assertAlmostEqual(rows[0]["Precio"], 1234.5)
            self.assertEqual(rows[0]["Cantidad"], 42)
            self.assertAlmostEqual(rows[1]["Precio"], 987.25)

    def test_xlsx_reader_header_detection_shared_strings_and_excel_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            xlsx_path = Path(tmpdir) / "sample.xlsx"
            _build_minimal_xlsx(xlsx_path)

            sheets, raw_rows = local_data.read_xlsx(xlsx_path)
            self.assertEqual(sheets, ["Series"])
            self.assertEqual(len(raw_rows), 5)

            table = local_data.read_table(xlsx_path)
            # Title row skipped, 1-cell footer note dropped -> exactly 2 data rows
            self.assertEqual(len(table), 2)
            self.assertEqual(table[0]["date_serial"], 46311)
            self.assertAlmostEqual(table[0]["rate"], 85.4)
            self.assertIs(table[0]["verified"], True)
            self.assertEqual(table[0]["label"], "ok")
            self.assertEqual(table[1]["rate"], 100)
            self.assertIs(table[1]["verified"], False)

            # Excel serial date conversion (1900 system)
            self.assertEqual(local_data.excel_date(46311), date(2026, 10, 16))

    def test_json_nested_results_read_table_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "bcra.json"
            payload = {
                "status": 200,
                "results": [
                    {"fecha": "2026-11-19", "valor": 1562.9893},
                    {"fecha": "2026-11-20", "valor": 1565.10},
                ],
            }
            json_path.write_text(json.dumps(payload), encoding="utf-8")

            table = local_data.read_table(json_path)
            self.assertEqual(len(table), 2)
            self.assertEqual(table[0]["fecha"], "2026-11-19")
            self.assertAlmostEqual(table[0]["valor"], 1562.9893)

            prev = local_data.preview(json_path, n=5)
            self.assertIn("bcra.json", prev)
            self.assertIn("results", prev)

            # Unsupported format preview (PDF) must still succeed gracefully
            pdf_path = Path(tmpdir) / "report.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            pdf_prev = local_data.preview(pdf_path)
            self.assertIn("pdf", pdf_prev.lower())

    def test_register_local_writes_file_uri_and_sha256_to_sources_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_file = root / "series.csv"
            data_file.write_text("a,b\n1,2\n", encoding="utf-8")
            sources_csv = root / "sources.csv"

            row = local_data.register_local(
                data_file,
                sources_csv,
                tier="Tier 1",
                title="BCRA A3500 Local Copy",
                claim_id="C1",
                data_as_of="2026-11-20",
            )
            self.assertTrue(row["url"].startswith("file://"))
            self.assertIn("sha256", row["source_title"].lower())
            self.assertEqual(row["tier"], "Tier 1")
            self.assertEqual(row["claim_id"], "C1")

            with sources_csv.open(encoding="utf-8", newline="") as fh:
                saved = list(csv.DictReader(fh))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["url"], data_file.resolve().as_uri())
            self.assertIn(local_data.sha12(data_file), saved[0]["source_title"])

            # CLI smoke test for inventory, preview, and register
            script_path = SCRIPTS_DIR / "local_data.py"
            res = subprocess.run(
                [sys.executable, "-B", str(script_path), "inventory", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertIn("series.csv", res.stdout)


if __name__ == "__main__":
    unittest.main()
