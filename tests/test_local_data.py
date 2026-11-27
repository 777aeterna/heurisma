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
                text=True, encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertIn("series.csv", res.stdout)


    # ---- v0.5.0 Phase 3: L1-L5 --------------------------------------------------------------
    def _read_csv_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def test_register_assigns_sequential_local_ids_when_claim_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            (root / "b.csv").write_text("a,b\n3,4\n", encoding="utf-8")
            src = root / "sources.csv"
            r1 = local_data.register_local(root / "a.csv", src, tier="Tier 2", title="A")
            r2 = local_data.register_local(root / "b.csv", src, tier="Tier 2", title="B")
            self.assertEqual((r1["claim_id"], r2["claim_id"]), ("L1", "L2"))
            self.assertEqual(local_data.next_local_id(src), "L3")
            self.assertEqual(local_data.next_local_id(root / "missing.csv"), "L1")

    def test_register_dedupes_same_file_by_path_and_by_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            (root / "copy_of_a.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            src = root / "sources.csv"
            first = local_data.register_local(root / "a.csv", src, tier="Tier 2", title="A")
            again = local_data.register_local(root / "a.csv", src, tier="Tier 2", title="A")
            same_hash = local_data.register_local(root / "copy_of_a.csv", src, tier="Tier 2", title="A copy")
            self.assertEqual(len(self._read_csv_rows(src)), 1)
            self.assertEqual(again["claim_id"], first["claim_id"])
            self.assertEqual(same_hash["claim_id"], first["claim_id"])

    def test_register_title_localized_and_relative_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "data").mkdir()
            f = root / "data" / "serie propia.csv"
            f.write_text("a,b\n1,2\n", encoding="utf-8")
            row = local_data.register_local(
                f, root / "sources.csv", tier="Tier 2", title="Serie", lang="es", relative_to=root
            )
            self.assertIn("archivo local", row["source_title"])
            self.assertNotIn("local file", row["source_title"])
            self.assertEqual(row["url"], "data/serie%20propia.csv")
            self.assertFalse(row["url"].startswith("file:"))
            self.assertNotIn(str(root), row["url"])

    def test_register_dedupes_against_legacy_file_uri_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "data").mkdir()
            f = root / "data" / "a.csv"
            f.write_text("a\n1\n", encoding="utf-8")
            sp = root / "sources.csv"
            sp.write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of\n"
                "L1,Old,file://data/a.csv,Tier 2,2026-11-20,\n",
                encoding="utf-8",
            )
            row = local_data.register_local(f, sp, tier="Tier 2", title="A", relative_to=root)
            self.assertEqual(row["claim_id"], "L1")
            self.assertEqual(len(self._read_csv_rows(sp)), 1)

    def test_register_inside_report_root_never_stores_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "appendix").mkdir()
            f = root / "appendix" / "a.csv"
            f.write_text("a\n1\n", encoding="utf-8")
            row = local_data.register_local(f, root / "appendix" / "sources.csv", tier="Tier 2", title="A", relative_to=root)
            self.assertNotIn(str(root), row["url"])
            self.assertEqual(row["url"], "appendix/a.csv")

    def test_legacy_six_column_attempts_file_is_widened_not_corrupted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            att = root / "data_attempts.csv"
            att.write_text(
                "target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used\nold,x,y,failed,z,\n",
                encoding="utf-8",
            )
            local_data.log_offline_attempt(att, "BCRA", "offline mode", target="band")
            rows = self._read_csv_rows(att)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["attempted_utc"], "")  # inherited row: no date -> counts as inherited
            self.assertEqual(rows[0]["failure_reason"], "z")
            self.assertEqual(rows[1]["target_series"], "band")
            self.assertRegex(rows[1]["attempted_utc"], r"^\d{4}-")

    def test_offline_attempt_is_timestamped_in_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            att = Path(tmpdir) / "data_attempts.csv"
            local_data.log_offline_attempt(att, "BCRA", "offline mode", target="band")
            rows = self._read_csv_rows(att)
            self.assertRegex(rows[0]["attempted_utc"], r"^\d{4}-\d{2}-\d{2}T")

    def test_attempt_cli_stamps_real_utc_on_new_and_legacy_files(self) -> None:
        import csv as _csv

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy = root / "legacy.csv"
            legacy.write_text(
                "target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used\nold,x,y,failed,z,\n",
                encoding="utf-8",
            )
            for target_csv in (root / "new.csv", legacy):
                for _ in range(2):
                    res = subprocess.run(
                        [sys.executable, "-B", str(SCRIPTS_DIR / "local_data.py"), "attempt", "--csv", str(target_csv),
                         "--target", "Serie X", "--source", "BCRA API v4", "--query", "variable 1187",
                         "--outcome", "HTTP 200", "--fallback", "local:appendix/data/x.csv sha256:abc123def456"],
                        capture_output=True,
                        text=True, encoding="utf-8",
                    )
                    self.assertEqual(res.returncode, 0, msg=res.stderr)
                with target_csv.open(encoding="utf-8", newline="") as fh:
                    reader = _csv.DictReader(fh)
                    self.assertEqual(len(reader.fieldnames), 7)
                    rows = [r for r in reader if r["target_series"] == "Serie X"]
                self.assertEqual(len(rows), 2)
                for r in rows:
                    self.assertRegex(r["attempted_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
                    self.assertEqual(r["query_or_endpoint"], "variable 1187")
                    self.assertEqual(r["fallback_used"], "local:appendix/data/x.csv sha256:abc123def456")

    def test_append_attempt_returns_the_written_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            row = local_data.append_attempt(
                Path(tmpdir) / "a.csv", "band", "BCRA", "catalogue all pages", "not found", failure_reason="no match"
            )
            self.assertEqual(row["failure_reason"], "no match")
            self.assertEqual(row["fallback_used"], "")
            self.assertRegex(row["attempted_utc"], r"Z$")

    def test_register_cli_stores_project_relative_path_and_absolute_uri_outside(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(tmpdir)
            (root / "appendix" / "data").mkdir(parents=True)
            inside = root / "appendix" / "data" / "ej.csv"
            inside.write_text("a\n1\n", encoding="utf-8")
            outside = Path(elsewhere) / "fuera.csv"
            outside.write_text("b\n2\n", encoding="utf-8")
            sources = root / "appendix" / "sources.csv"
            for f in (inside, outside):
                res = subprocess.run(
                    [sys.executable, "-B", str(SCRIPTS_DIR / "local_data.py"), "register", str(f),
                     "--sources", str(sources), "--tier", "Tier 2", "--title", f.stem],
                    capture_output=True,
                    text=True, encoding="utf-8",
                )
                self.assertEqual(res.returncode, 0, msg=res.stderr)
            rows = self._read_csv_rows(sources)
            self.assertEqual(rows[0]["url"], "appendix/data/ej.csv")
            self.assertTrue(rows[1]["url"].startswith("file:///"), msg=rows[1]["url"])
            self.assertNotIn(str(root), rows[0]["url"])

    def test_preview_cli_reports_bad_json_and_empty_csv_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "mal.json").write_text("{not json", encoding="utf-8")
            (root / "vacio.csv").write_text("", encoding="utf-8")
            for name in ("mal.json", "vacio.csv"):
                res = subprocess.run(
                    [sys.executable, "-B", str(SCRIPTS_DIR / "local_data.py"), "preview", str(root / name)],
                    capture_output=True,
                    text=True, encoding="utf-8",
                )
                self.assertEqual(res.returncode, 1, msg=res.stdout + res.stderr)
                self.assertNotIn("Traceback", res.stderr)
                self.assertIn(name, res.stderr)

    def test_import_local_copies_registers_relative_and_logs_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "datos").mkdir()
            src_file = root / "datos" / "mi serie.csv"
            src_file.write_bytes("\ufefffecha;valor\n2026-01-01;1,5\n".encode("utf-8"))
            appendix = root / "appendix"
            row = local_data.import_local(
                src_file, appendix / "data", appendix / "sources.csv", tier="Tier 2", title="Mi serie", lang="es"
            )
            copy = appendix / "data" / "mi serie.csv"
            self.assertTrue(copy.is_file())
            self.assertEqual(copy.read_bytes(), src_file.read_bytes())
            self.assertEqual(row["claim_id"], "L1")
            self.assertEqual(row["url"], "appendix/data/mi%20serie.csv")
            sources = self._read_csv_rows(appendix / "sources.csv")
            self.assertEqual(len(sources), 1)
            self.assertIn(local_data.sha12(copy), sources[0]["source_title"])
            attempts = self._read_csv_rows(appendix / "data_attempts.csv")
            self.assertEqual(
                list(attempts[0]),
                ["target_series", "source_tried", "query_or_endpoint", "outcome", "failure_reason", "fallback_used",
                 "attempted_utc"],
            )
            self.assertRegex(attempts[0]["attempted_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertEqual(
                attempts[0]["fallback_used"],
                f"local:appendix/data/mi%20serie.csv sha256:{local_data.sha256_file(copy)}",
            )
            # idempotent: importing again adds nothing
            local_data.import_local(
                src_file, appendix / "data", appendix / "sources.csv", tier="Tier 2", title="Mi serie", lang="es"
            )
            self.assertEqual(len(self._read_csv_rows(appendix / "sources.csv")), 1)
            self.assertEqual(len(self._read_csv_rows(appendix / "data_attempts.csv")), 1)

    def test_import_cli_and_conflicting_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            f = root / "x.csv"
            f.write_text("a,b\n1,2\n", encoding="utf-8")
            appendix = root / "appendix"
            cmd = [
                sys.executable, "-B", str(SCRIPTS_DIR / "local_data.py"), "import", str(f),
                "--into", str(appendix / "data"), "--sources", str(appendix / "sources.csv"),
                "--tier", "Tier 1", "--title", "X series",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertTrue((appendix / "data" / "x.csv").is_file())
            # same name, different content -> readable error, exit 1, nothing overwritten
            other = root / "other" / "x.csv"
            other.parent.mkdir()
            other.write_text("a,b\n9,9\n", encoding="utf-8")
            res2 = subprocess.run(cmd[:4] + [str(other)] + cmd[5:], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res2.returncode, 1)
            self.assertNotIn("Traceback", res2.stderr)
            self.assertEqual((appendix / "data" / "x.csv").read_text(encoding="utf-8"), "a,b\n1,2\n")

    def test_offline_enabled_reads_env_and_logs_offline_attempt(self) -> None:
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"HEURISMA_OFFLINE": "1"}):
            self.assertTrue(local_data.offline_enabled())
        with mock.patch.dict(os.environ, {"HEURISMA_OFFLINE": "0"}):
            self.assertFalse(local_data.offline_enabled())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(local_data.offline_enabled())
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "appendix" / "data_attempts.csv"
            local_data.log_offline_attempt(log, "BCRA API", "network disabled by HEURISMA_OFFLINE=1", target="A3500", endpoint="GET https://api.example.org/a3500")
            rows = self._read_csv_rows(log)
            self.assertEqual(rows[0]["outcome"], "offline mode")
            self.assertEqual(rows[0]["source_tried"], "BCRA API")
            self.assertEqual(rows[0]["fallback_used"], "")

    def test_offline_run_uses_local_csv_and_validates(self) -> None:
        import importlib.util
        import os
        from unittest import mock

        spec = importlib.util.spec_from_file_location("tvr", Path(__file__).with_name("test_validate_report.py"))
        tvr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tvr)

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.dict(os.environ, {"HEURISMA_OFFLINE": "1"}):
            root = Path(tmpdir)
            (root / "datos").mkdir()
            (root / "datos" / "a3500.csv").write_text("fecha;valor\n2026-01-01;1459,42\n", encoding="utf-8")
            appendix = root / "appendix"
            appendix.mkdir()
            (appendix / "analysis.py").write_text("print('ok')\n", encoding="utf-8")
            tvr._seed_gates(root)
            (appendix / "output.txt").write_text("0.35 60\n", encoding="utf-8")
            self.assertTrue(local_data.offline_enabled())
            local_data.log_offline_attempt(
                appendix / "data_attempts.csv", "BCRA API", "offline", target="A3500", endpoint="GET https://api.example.org"
            )
            row = local_data.import_local(
                root / "datos" / "a3500.csv", appendix / "data", appendix / "sources.csv", tier="Tier 3", title="A3500 local",
                retrieved_utc="2026-11-01T00:00:00Z",  # a local user-curated file stays Tier 3 (v0.8.1: never Tier 1/2)
            )
            marker = tvr._seed_charts(root)
            report = tvr._with_fig(
                tvr.VALID_REPORT.replace("[@C1]", f"[@{row['claim_id']}]")
                .replace("Pure PHA films mineralize", f"Pure PHA films mineralize [@{row['claim_id']}]")
                # a claim resting only on a local user-curated file (Tier 3) cannot be [Strong]
                .replace("(Tier 1) | `[Strong]`", "(Tier 3) | `[Preliminary]`"),
                marker,
            )
            (root / "report.md").write_text(report, encoding="utf-8")
            tvr._restamp_gates(root)  # the QA gate is bound to the final report
            out = root / "report.html"
            cmd_r = [sys.executable, "-B", str(SCRIPTS_DIR / "render_report.py"), str(root / "report.md"), "--out", str(out),
                     "--charts", str(root / "charts.json"), "--appendix", str(appendix)]
            self.assertEqual(subprocess.run(cmd_r, capture_output=True, text=True, encoding="utf-8").returncode, 0)
            res = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS_DIR / "validate_report.py"), str(root / "report.md"),
                 "--level", "2", "--html", str(out), "--strict", "--run-since", "2000-01-01"],
                capture_output=True,
                text=True, encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr + res.stdout)
            self.assertNotIn("/tmp/", out.read_text(encoding="utf-8").replace("/tmp/claude", ""))


if __name__ == "__main__":
    unittest.main()
