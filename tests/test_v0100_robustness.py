"""v0.10.0 audit, Task 1: the connector must survive malformed API payloads, odd settings and odd CSV files without a traceback."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
from test_papers_core import REAL, SCRIPTS, Base, read_csv  # noqa: E402
import validate_report  # noqa: E402

import fetch_lib  # noqa: E402
import local_data  # noqa: E402
import papers  # noqa: E402
from providers import base, crossref, europepmc, openalex  # noqa: E402

WORK = {"id": "https://openalex.org/W1", "title": "A title", "doi": "https://doi.org/10.9999/robust.1"}


def _oa(**extra: object) -> bytes:
    return json.dumps({"results": [{**WORK, **extra}]}).encode("utf-8")


class TestParsersTolerateOddShapes(unittest.TestCase):
    """A field of the wrong type is a missing field, not a crash (a cached or imported file can hold anything)."""

    def survives(self, parse, body: bytes) -> list:  # type: ignore[no-untyped-def]
        try:
            return parse(body)
        except base.ProviderUnavailable:
            return []  # refusing is acceptable; any other exception is the defect

    def test_openalex_wrong_types(self) -> None:
        for extra in (
            {"authorships": "x"}, {"authorships": [None]}, {"authorships": [{"author": "x"}]}, {"primary_location": "x"},
            {"primary_location": {"source": "x"}}, {"open_access": "x"}, {"abstract_inverted_index": "x"}, {"publication_year": [1]},
        ):
            with self.subTest(extra=extra):
                self.survives(openalex.parse, _oa(**extra))

    def test_crossref_wrong_types(self) -> None:
        for extra in (
            {"issued": {"date-parts": 5}}, {"issued": "x"}, {"updated-by": ["retraction"]}, {"author": "x"}, {"author": [None]},
            {"container-title": "J"}, {"title": 5}, {"abstract": ["x"]},
        ):
            with self.subTest(extra=extra):
                self.survives(crossref.parse, json.dumps({"message": {"DOI": "10.9999/robust.1", **extra}}).encode("utf-8"))

    def test_europepmc_wrong_types(self) -> None:
        for extra in ({"authorList": "x"}, {"authorList": {"author": "x"}}, {"journalInfo": "x"}, {"pubTypeList": "x"}, {"pubTypeList": {"pubType": 5}}):
            with self.subTest(extra=extra):
                body = json.dumps({"resultList": {"result": [{"id": "1", "source": "MED", "title": "t", **extra}]}}).encode("utf-8")
                self.survives(europepmc.parse, body)

    def test_a_string_where_a_list_is_expected_still_gives_the_value(self) -> None:
        rec = crossref.parse(json.dumps({"message": {"DOI": "10.9999/robust.1", "title": "Hello", "container-title": "J. Fixtures"}}).encode("utf-8"))[0]
        self.assertEqual((rec["title"], rec["venue"]), ("Hello", "J. Fixtures"))
        body = json.dumps({"resultList": {"result": [{"id": "1", "source": "MED", "pubTypeList": {"pubType": "Retracted Publication"}}]}}).encode("utf-8")
        self.assertEqual(europepmc.parse(body)[0]["is_retracted"], "true")

    def test_a_missing_type_is_unknown_not_other(self) -> None:
        self.assertEqual(base.map_work_type(None), "")
        self.assertEqual(base.map_work_type(""), "")
        self.assertEqual(base.map_work_type("editorial"), "other")  # a type the databases gave but we do not map
        self.assertEqual(openalex.parse(_oa())[0]["work_type"], "")

    def test_the_pmcid_is_read_only_when_it_has_the_pmc_form(self) -> None:
        for pmcid, want in (("PMC1234567", "PMC1234567"), ("PMC1/../../x", ""), ("https://evil.example/x", ""), (5, "")):
            body = json.dumps({"resultList": {"result": [{"id": "1", "source": "MED", "pmcid": pmcid}]}}).encode("utf-8")
            self.assertEqual(europepmc.parse(body)[0]["pmcid"], want, pmcid)

    def test_utf16_doctype_is_refused(self) -> None:
        for enc in ("utf-16", "utf-16-le", "utf-16-be", "utf-32"):
            payload = '<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "y">]><a>&x;</a>'.encode(enc)
            with self.subTest(enc=enc), self.assertRaises(base.ProviderUnavailable):
                base.parse_xml(payload)
        base.parse_xml(b"<a>fine</a>")  # an ordinary document still parses


class TestSettings(unittest.TestCase):
    def test_backoff_setting_that_is_not_a_number_falls_back_and_never_goes_negative(self) -> None:
        self.assertEqual(base.backoff_seconds({"HEURISMA_BACKOFF": "abc"}), 1.0)
        self.assertEqual(base.backoff_seconds({"HEURISMA_BACKOFF": ""}), 1.0)
        self.assertEqual(base.backoff_seconds({}), 1.0)
        self.assertEqual(base.backoff_seconds({"HEURISMA_BACKOFF": "-3"}), 0.0)
        self.assertEqual(base.backoff_seconds({"HEURISMA_BACKOFF": "inf"}), 1.0)
        self.assertEqual(base.backoff_seconds({"HEURISMA_BACKOFF": "0.5"}), 0.5)

    def test_context_builds_with_a_bad_backoff_in_the_environment(self) -> None:
        for value in ("abc", "-1"):
            with mock.patch.dict(os.environ, {"HEURISMA_BACKOFF": value}):
                ctx = base.Context(Path("appendix"))
            self.assertGreaterEqual(ctx.backoff, 0.0)


class TestCleanText(unittest.TestCase):
    def test_control_characters_go_and_formula_prefixes_are_neutralised(self) -> None:
        self.assertEqual(base.clean_text('=HYPERLINK("x")\x07'), "'=HYPERLINK(\"x\")")
        for lead in "=+-@":
            self.assertTrue(base.clean_text(f"{lead}cmd").startswith("'"), lead)
        self.assertEqual(base.clean_text("A  title\twith\nbreaks"), "A title with breaks")
        self.assertEqual(base.clean_text("Normal title"), "Normal title")
        self.assertEqual(len(base.clean_text("x" * 900)), 500)
        self.assertEqual(base.clean_text(None), "")  # type: ignore[arg-type]

    def test_a_malicious_title_is_neutralised_before_it_reaches_any_csv(self) -> None:
        rec = openalex.parse(_oa(title='=HYPERLINK("http://x.example","go")'))[0]
        self.assertTrue(rec["title"].startswith("'="))
        rec = crossref.parse(json.dumps({"message": {"DOI": "10.9999/robust.1", "title": ["+cmd|' /C calc'!A0"]}}).encode("utf-8"))[0]
        self.assertTrue(rec["title"].startswith("'+"))


class TestCsvAppend(unittest.TestCase):
    def test_a_file_without_a_final_newline_does_not_swallow_the_new_row(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.csv"
            path.write_bytes(b"claim_id,source_title\nC1,First")  # no trailing newline
            local_data._append_row(path, ("claim_id", "source_title"), {"claim_id": "C2", "source_title": "Second"})
            rows = read_csv(path)
            self.assertEqual([r["claim_id"] for r in rows], ["C1", "C2"])
            self.assertEqual(rows[0]["source_title"], "First")


class TestFetchLibRedaction(unittest.TestCase):
    def test_a_rejected_url_never_writes_its_credential(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            appendix = Path(tmp) / "appendix"
            self.assertIsNone(fetch_lib.fetch("t", "s", "ftp://host.example/x?api_key=SECRET123&mailto=me@example.org", "f.bin", appendix))
            written = (appendix / "data_attempts.csv").read_text(encoding="utf-8")
            self.assertNotIn("SECRET123", written)
            self.assertNotIn("me@example.org", written)
            self.assertIn("rejected", written)


class TestFilters(Base):
    def test_false_is_a_boolean_and_does_not_switch_the_filter_on(self) -> None:
        self.assertEqual(papers.parse_filters(["open_access=false"], "europepmc"), {"open_access": False})
        self.assertEqual(papers.parse_filters(["open_access=True"], "europepmc"), {"open_access": True})
        papers.search(self.ctx(), "europepmc", "hybrid work", filters={"open_access": False})
        sent = [q["query"][0] for path, q, _ in self.server.requests if path.startswith("/europepmc/search")]
        self.assertTrue(sent)
        self.assertNotIn("OPEN_ACCESS", sent[-1])

    def test_europepmc_open_access_filter_covers_the_whole_query(self) -> None:
        papers.search(self.ctx(), "europepmc", "hybrid work OR attrition", filters={"open_access": True})
        sent = [q["query"][0] for path, q, _ in self.server.requests if path.startswith("/europepmc/search")]
        self.assertEqual(sent[-1], "(hybrid work OR attrition) AND OPEN_ACCESS:Y")

    def test_a_filter_the_provider_ignores_is_refused_not_silently_logged(self) -> None:
        with self.assertRaises(papers.FilterError):
            papers.parse_filters(["year=2020"], "arxiv")
        with self.assertRaises(papers.FilterError):
            papers.parse_filters(["year=2020"], "europepmc")
        with self.assertRaises(papers.FilterError):
            papers.parse_filters(["no-equals-sign"], "openalex")
        self.assertEqual(papers.parse_filters(["type=article", "is_oa=true"], "openalex"), {"type": "article", "is_oa": True})


class TestNoTracebacks(Base):
    def run_cli(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        e = {**os.environ, **self.env, **env}
        for k in ("HEURISMA_OFFLINE", "HEURISMA_OPENALEX_KEY", "HEURISMA_MAILTO", "HEURISMA_BACKOFF"):
            if k not in env:
                e.pop(k, None)
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "papers.py"), *args, "--appendix", str(self.appendix)],
            capture_output=True, text=True, encoding="utf-8", env=e,
        )

    def test_importing_a_file_with_odd_shapes_prints_an_error_or_succeeds_but_never_a_traceback(self) -> None:
        bad = Path(self.tmp.name) / "bad.json"
        for payload in (_oa(authorships="x", primary_location="x"), b'{"results": "x"}', b"[1, 2]", b"\xff\xfe not json"):
            bad.write_bytes(payload)
            r = self.run_cli("import", "--provider", "openalex", "--file", str(bad))
            self.assertNotIn("Traceback", r.stderr, payload)
            if r.returncode != 0:
                self.assertRegex(r.stderr, r"(?m)^Error: ")

    def test_a_file_with_no_work_that_has_an_identifier_is_refused(self) -> None:
        bad = Path(self.tmp.name) / "empty.json"
        bad.write_text(json.dumps({"results": [{"authorships": "x"}]}), encoding="utf-8")
        r = self.run_cli("import", "--provider", "openalex", "--file", str(bad))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertRegex(r.stderr, r"(?m)^Error: .*identifier")
        self.assertFalse((self.appendix / "papers.csv").exists())

    def test_a_bad_backoff_setting_does_not_stop_the_cli(self) -> None:
        r = self.run_cli("lookup", REAL, HEURISMA_BACKOFF="abc")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_an_unsupported_filter_is_an_error_not_a_request(self) -> None:
        r = self.run_cli("search", "--provider", "arxiv", "--query", "x", "--filter", "year=2020")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Error:", r.stderr)
        self.assertIn("filter", r.stderr.lower())
        self.assertEqual(self.server.requests, [])


class TestValidatorSurvivesBadCache(unittest.TestCase):
    def test_a_corrupt_cache_file_never_crashes_the_validator(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M._papers_workspace(ws)
            raw = ws / "appendix" / "data" / "papers" / "raw"
            (raw / "openalex-corrupt-001.json").write_bytes(_oa(authorships="x", primary_location="x"))
            (raw / "crossref-corrupt-001.json").write_bytes(json.dumps({"message": {"DOI": "10.9999/x", "issued": {"date-parts": 5}}}).encode("utf-8"))
            (raw / "europepmc-corrupt-001.json").write_bytes(b"\x00\x01 not json")
            (raw / "arxiv-corrupt-001.xml").write_bytes(b"<feed")
            M.restamp_gates(ws)
            errors, warnings = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws)
            self.assertIsInstance(errors, list)
            self.assertIsInstance(warnings, list)
        finally:
            tmp.cleanup()

    def test_the_row_a_corrupt_cache_was_meant_to_support_is_still_reported(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M._papers_workspace(ws)
            for cache in (ws / "appendix" / "data" / "papers" / "raw").glob("openalex-*.json"):
                cache.write_bytes(b'{"results": "x"}')
            M.restamp_gates(ws)
            errors, warnings = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws)
            self.assertTrue(any("papers.csv" in m and "no cached response" in m for m in errors + warnings), errors + warnings)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
