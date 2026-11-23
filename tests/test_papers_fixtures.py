"""v0.10.0 Phase 0: the recorded paper-API fixtures keep their real shape, and the local server serves them."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import papers_server  # noqa: E402

F = papers_server.FIXTURES
REAL_DOI = "10.1038/s41586-024-07500-2"


def jload(name: str):
    return json.loads((F / name).read_text(encoding="utf-8"))


def get(url: str) -> tuple[int, bytes, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


class TestFixtureShapes(unittest.TestCase):
    def test_openalex_records_carry_the_fields_the_connector_reads(self) -> None:
        for w in jload("openalex_search.json")["results"]:
            for k in ("id", "doi", "title", "publication_year", "type", "is_retracted", "authorships", "primary_location", "open_access"):
                self.assertIn(k, w, (w.get("doi"), k))
            self.assertIn("abstract_inverted_index", w)

    def test_synthetic_variants_exist_and_use_the_fake_prefix(self) -> None:
        by = {w["doi"].replace("https://doi.org/", ""): w for w in jload("openalex_search.json")["results"]}
        self.assertEqual(by["10.9999/fake.preprint.1"]["type"], "preprint")
        self.assertTrue(by["10.9999/fake.retracted.1"]["is_retracted"])
        self.assertIsNone(by["10.9999/fake.noabstract.1"]["abstract_inverted_index"])
        self.assertEqual(by["10.9999/fake.report.1"]["type"], "report")
        self.assertTrue(any("(" in d and "<" in d and d.startswith("10.9999/") for d in by))
        for doi, w in by.items():
            if doi != REAL_DOI:
                self.assertTrue(doi.startswith("10.9999/"), doi)
            if w["is_retracted"] or w["type"] in ("preprint", "report"):
                self.assertTrue(doi.startswith("10.9999/"), f"a real paper is marked {w['type']}/retracted: {doi}")

    def test_the_real_record_is_a_normal_peer_reviewed_article(self) -> None:
        real = jload("openalex_work.json")
        self.assertEqual((real["type"], real["is_retracted"], real["publication_year"]), ("article", False, 2024))
        self.assertTrue(real["abstract_inverted_index"])

    def test_the_verbatim_agent_instruction_notice_is_kept_as_an_injection_case(self) -> None:
        notice = jload("openalex_search.json")["meta"]["notice"]
        self.assertIn("AI agent", notice)
        self.assertIn("api-keys", notice)

    def test_crossref_europepmc_and_arxiv_shapes(self) -> None:
        cr = jload("crossref_work.json")["message"]
        self.assertEqual(cr["DOI"], REAL_DOI)
        self.assertEqual(cr["type"], "journal-article")
        self.assertEqual(jload("crossref_preprint.json")["message"]["type"], "posted-content")
        epmc = jload("europepmc_search.json")["resultList"]["result"]
        self.assertEqual([r["source"] for r in epmc], ["MED", "PPR"])
        self.assertTrue(epmc[0]["abstractText"])
        feed = ET.fromstring((F / "arxiv_feed.xml").read_bytes())
        ns = {"a": "http://www.w3.org/2005/Atom"}
        self.assertEqual(len(feed.findall("a:entry", ns)), 2)
        self.assertTrue(feed.find("a:entry/a:title", ns).text.strip())

    def test_fixtures_contain_no_personal_data(self) -> None:
        text = " ".join(p.read_text(encoding="utf-8") for p in F.iterdir() if p.suffix in (".json", ".xml", ".md"))
        # generic patterns only: no e-mail address, no home-directory path, no credential in a URL
        self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), "an e-mail address")
        self.assertIsNone(re.search(r"/home/\w|/Users/\w", text), "a home-directory path")
        self.assertIsNone(re.search(r"(?:api_key|mailto)=(?!YOUR_)\w", text), "a credential value in a URL")  # the notice's YOUR_KEY is a placeholder


class TestPapersServer(unittest.TestCase):
    def setUp(self) -> None:
        self.base, self.server = papers_server.start()

    def tearDown(self) -> None:
        self.server.stop()

    def test_search_lookup_and_unknown_doi(self) -> None:
        status, body, _ = get(self.base + "/openalex/works?search=hybrid")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["results"]), 6)
        status, body, _ = get(f"{self.base}/openalex/works/doi:{REAL_DOI}")
        self.assertEqual((status, json.loads(body)["type"]), (200, "article"))
        self.assertEqual(get(f"{self.base}/openalex/works/doi:10.9999/not-there")[0], 404)
        self.assertEqual(get(f"{self.base}/crossref/works/{REAL_DOI}")[0], 200)
        self.assertEqual(get(f"{self.base}/crossref/works/10.9999/not-there")[0], 404)
        self.assertEqual(get(self.base + "/europepmc/search?query=x")[0], 200)
        self.assertEqual(get(self.base + "/arxiv/api/query?search_query=x")[0], 200)
        self.assertEqual(get(f"{self.base}/unpaywall/{REAL_DOI}?email=a@b.c")[0], 200)

    def test_parenthesised_doi_round_trips_through_the_index(self) -> None:
        doi = next(d for d in json.loads((F / "openalex_index.json").read_text(encoding="utf-8")) if "(" in d)
        from urllib.parse import quote

        status, body, _ = get(f"{self.base}/openalex/works/doi:{quote(doi, safe='')}")
        self.assertEqual(status, 200, doi)

    def test_requests_are_recorded_and_failures_can_be_forced(self) -> None:
        self.server.fail_next("/openalex", 429, times=2)
        self.assertEqual(get(self.base + "/openalex/works?search=a")[0], 429)
        status, _, headers = get(self.base + "/openalex/works?search=b&api_key=SECRET")
        self.assertEqual((status, headers.get("Retry-After")), (429, "0"))
        self.assertEqual(get(self.base + "/openalex/works?search=c")[0], 200)
        self.assertEqual(len(self.server.requests), 3)
        self.assertEqual(self.server.requests[1][1]["api_key"], ["SECRET"])


if __name__ == "__main__":
    unittest.main()
