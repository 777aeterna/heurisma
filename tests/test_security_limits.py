"""Security limits for local_data.py (XXE/billion-laughs, zip bombs, oversized files)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "heurisma" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import local_data  # noqa: E402

WORKBOOK_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
    "</workbook>"
)
RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
    "</Relationships>"
)
SHEET_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<sheetData><row r="1"><c r="A1"><v>42</v></c></row></sheetData>'
    "</worksheet>"
)


def _write_xlsx(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)


class TestSecurityLimits(unittest.TestCase):
    def test_read_xlsx_rejects_doctype_entity_in_shared_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "xxe.xlsx"
            hostile_ss = (
                '<?xml version="1.0"?>'
                '<!DOCTYPE sst [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;">]>'
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<si><t>&lol2;</t></si></sst>"
            ).encode("utf-8")
            _write_xlsx(
                p,
                {
                    "xl/workbook.xml": WORKBOOK_XML.encode("utf-8"),
                    "xl/_rels/workbook.xml.rels": RELS_XML.encode("utf-8"),
                    "xl/sharedStrings.xml": hostile_ss,
                    "xl/worksheets/sheet1.xml": SHEET_XML.encode("utf-8"),
                },
            )
            with self.assertRaises(ValueError) as ctx:
                local_data.read_xlsx(p)
            self.assertRegex(str(ctx.exception), r"(?i)doctype|entity")

    def test_read_xlsx_rejects_doctype_entity_in_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "xxe_sheet.xlsx"
            hostile_sheet = (
                '<?xml version="1.0"?>'
                '<!DOCTYPE worksheet [<!ENTITY a "x">]>'
                + SHEET_XML.split("?>", 1)[1]
            ).encode("utf-8")
            _write_xlsx(
                p,
                {
                    "xl/workbook.xml": WORKBOOK_XML.encode("utf-8"),
                    "xl/_rels/workbook.xml.rels": RELS_XML.encode("utf-8"),
                    "xl/worksheets/sheet1.xml": hostile_sheet,
                },
            )
            with self.assertRaises(ValueError) as ctx:
                local_data.read_xlsx(p)
            self.assertRegex(str(ctx.exception), r"(?i)doctype|entity")

    def test_read_xlsx_rejects_zip_bomb_compression_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bomb.xlsx"
            # 2 MB of spaces inside an XML comment compresses to ~2 KB (ratio ~1000x).
            filler = b" " * (2 * 1024 * 1024)
            bomb_sheet = (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b"<!--" + filler + b"-->"
                + SHEET_XML.split("?>", 1)[1].encode("utf-8")
            )
            _write_xlsx(
                p,
                {
                    "xl/workbook.xml": WORKBOOK_XML.encode("utf-8"),
                    "xl/_rels/workbook.xml.rels": RELS_XML.encode("utf-8"),
                    "xl/worksheets/sheet1.xml": bomb_sheet,
                },
            )
            with self.assertRaises(ValueError) as ctx:
                local_data.read_xlsx(p)
            self.assertRegex(str(ctx.exception), r"(?i)ratio|bomb|uncompressed")

    def test_read_xlsx_rejects_uncompressed_size_over_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "big.xlsx"
            _write_xlsx(
                p,
                {
                    "xl/workbook.xml": WORKBOOK_XML.encode("utf-8"),
                    "xl/_rels/workbook.xml.rels": RELS_XML.encode("utf-8"),
                    "xl/worksheets/sheet1.xml": SHEET_XML.encode("utf-8"),
                },
            )
            with mock.patch.dict(os.environ, {"HEURISMA_MAX_BYTES": "200"}):
                with self.assertRaises(ValueError) as ctx:
                    local_data.read_xlsx(p)
            self.assertRegex(str(ctx.exception), r"(?i)size|limit|uncompressed")

    def test_read_csv_and_json_enforce_max_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "big.csv"
            csv_path.write_text("a,b\n" + "1,2\n" * 200, encoding="utf-8")
            json_path = Path(tmp) / "big.json"
            json_path.write_text("[" + ",".join('{"a":1}' for _ in range(100)) + "]", encoding="utf-8")
            with mock.patch.dict(os.environ, {"HEURISMA_MAX_BYTES": "256"}):
                for fn, target in (
                    (local_data.read_csv, csv_path),
                    (local_data.read_table, csv_path),
                    (local_data.read_json, json_path),
                    (local_data.read_table, json_path),
                ):
                    with self.assertRaises(ValueError) as ctx:
                        fn(target)
                    self.assertRegex(str(ctx.exception), r"(?i)limit|HEURISMA_MAX_BYTES|exceeds")

    def test_cli_preview_oversized_csv_exits_cleanly_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "big.csv"
            csv_path.write_text("a,b\n" + "1,2\n" * 200, encoding="utf-8")
            env = dict(os.environ, HEURISMA_MAX_BYTES="128")
            res = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS_DIR / "local_data.py"), "preview", str(csv_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("Error:", res.stderr)
            self.assertNotIn("Traceback", res.stderr)


if __name__ == "__main__":
    unittest.main()
