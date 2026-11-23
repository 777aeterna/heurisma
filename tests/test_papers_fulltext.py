"""v0.10.0 Phase 2: open-access full text with a hash, `verify`, `import` and `replay` of the paper connector."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import papers_server  # noqa: E402
from test_papers_core import REAL, SECRET_MAIL, Base, read_csv  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import papers  # noqa: E402
from contracts import PAPER_COLS, SOURCE_COLS  # noqa: E402
from providers import base, unpaywall  # noqa: E402

FIX = papers_server.FIXTURES


def sources(appendix: Path, rows: list[dict[str, str]]) -> None:
    appendix.mkdir(parents=True, exist_ok=True)
    with (appendix / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(SOURCE_COLS), restval="")
        w.writeheader()
        w.writerows(rows)


def src(cid: str, title: str, doi: str, tier: str = "Tier 2") -> dict[str, str]:
    return {"claim_id": cid, "source_title": title, "url": f"https://doi.org/{doi}", "tier": tier, "kind": "literature", "selection": "agent-fetched"}


class TestUnpaywall(Base):
    def test_it_needs_a_contact_address_and_never_records_it(self) -> None:
        with self.assertRaises(base.ProviderUnavailable) as cm:
            unpaywall.oa_location(self.ctx(), REAL)
        self.assertIn("HEURISMA_MAILTO", str(cm.exception))
        self.assertEqual(self.server.requests, [])
        loc = unpaywall.oa_location(self.ctx(HEURISMA_MAILTO=SECRET_MAIL), REAL)
        assert loc is not None
        self.assertTrue(loc["pdf_url"].endswith(".pdf"))
        self.assertEqual(self.server.requests[0][1]["email"], [SECRET_MAIL])
        self.assertNotIn(SECRET_MAIL, self.everything_written())

    def test_unknown_doi_gives_none(self) -> None:
        self.assertIsNone(unpaywall.oa_location(self.ctx(HEURISMA_MAILTO=SECRET_MAIL), "10.9999/not-there"))


class TestFulltext(Base):
    def record(self, **kw: str) -> dict[str, str]:
        papers.search(self.ctx(), "openalex", "x")
        rec = next(r for r in papers.read_papers(self.appendix) if r["doi"] == REAL)
        rec.update({"is_oa": "true", "oa_url": self.url + "/files/sample.pdf", **kw})
        return rec

    def test_an_open_access_pdf_is_saved_hashed_and_registered(self) -> None:
        path = papers.fulltext(self.ctx(), self.record())
        assert path is not None
        self.assertEqual(path.parent.resolve(), (self.appendix / "data" / "papers").resolve())
        self.assertTrue(path.name.endswith(".pdf") and "10.1038" in path.name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row = next(r for r in read_csv(self.appendix / "papers.csv") if r["doi"] == REAL)
        self.assertEqual((row["fulltext_file"], row["fulltext_sha256"]), (f"appendix/data/papers/{path.name}", digest))
        logged = [r for r in read_csv(self.appendix / "download_log.csv") if r["file"] == f"papers/{path.name}"]
        self.assertEqual([r["sha256"] for r in logged], [digest])

    def test_europe_pmc_full_text_xml_is_preferred_when_the_work_has_a_pmcid(self) -> None:
        path = papers.fulltext(self.ctx(), self.record(pmcid="PMC13729011"))
        assert path is not None
        self.assertTrue(path.name.endswith(".xml"))
        self.assertTrue([p for p in self.server.requests if p[0] == "/europepmc/PMC13729011/fullTextXML"])

    def test_a_work_that_is_not_open_access_gets_nothing(self) -> None:
        rec = self.record(is_oa="false")
        self.server.requests.clear()
        self.assertIsNone(papers.fulltext(self.ctx(), rec))
        self.assertEqual(self.server.requests, [])

    def test_a_landing_page_is_not_a_document_and_leaves_no_trace(self) -> None:
        rec = self.record(oa_url=self.url + "/files/page.html")
        self.assertIsNone(papers.fulltext(self.ctx(), rec))
        self.assertEqual([p.name for p in (self.appendix / "data" / "papers").glob("*") if p.is_file()], [])
        self.assertFalse([r for r in read_csv(self.appendix / "download_log.csv") if "page.html" in r["url"]])
        attempts = read_csv(self.appendix / "data_attempts.csv")
        self.assertIn("not a PDF or XML document", attempts[-1]["failure_reason"])

    def test_unpaywall_is_the_last_resort_and_needs_the_contact_address(self) -> None:
        rec = self.record(oa_url="")
        ctx = self.ctx()
        self.assertIsNone(papers.fulltext(ctx, rec))  # no address: skipped, with a warning, not an error
        self.assertTrue(any("HEURISMA_MAILTO" in w for w in ctx.warnings), ctx.warnings)
        self.assertEqual([p for p in self.server.requests if p[0].startswith("/unpaywall")], [])
        path = papers.fulltext(self.ctx(HEURISMA_MAILTO=SECRET_MAIL), rec)
        assert path is not None
        self.assertTrue(path.name.endswith(".pdf"))
        self.assertNotIn(SECRET_MAIL, self.everything_written())

    def test_cite_with_fulltext_fetches_it_from_the_stored_open_access_link(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        rows = read_csv(self.appendix / "papers.csv")
        for r in rows:
            if r["doi"] == REAL:
                r["is_oa"], r["oa_url"] = "true", self.url + "/files/sample.pdf"
        papers._write_atomic(self.appendix / "papers.csv", PAPER_COLS, rows)
        sources(self.appendix, [])
        row = papers.cite(self.ctx(), REAL, tier="Tier 1", claim_id="C2", fulltext=True)
        self.assertNotIn("(abstract only)", row["source_title"])
        self.assertTrue(next(r for r in read_csv(self.appendix / "papers.csv") if r["doi"] == REAL)["fulltext_sha256"])

    def test_cite_with_fulltext_refuses_cleanly_when_there_is_no_open_access_text(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        rows = read_csv(self.appendix / "papers.csv")
        for r in rows:
            r["is_oa"], r["oa_url"] = "false", ""
        papers._write_atomic(self.appendix / "papers.csv", PAPER_COLS, rows)
        sources(self.appendix, [])
        with self.assertRaises(papers.CiteError) as cm:
            papers.cite(self.ctx(), REAL, tier="Tier 1", fulltext=True)
        self.assertIn("full text", str(cm.exception))
        self.assertEqual(read_csv(self.appendix / "sources.csv"), [])

    def test_cite_with_fulltext_uses_the_saved_file(self) -> None:
        papers.fulltext(self.ctx(), self.record())
        sources(self.appendix, [])
        row = papers.cite(self.ctx(), REAL, tier="Tier 1", claim_id="C2", fulltext=True)
        self.assertNotIn("(abstract only)", row["source_title"])


class TestVerify(Base):
    def test_matching_unknown_mismatched_and_retracted_references_are_each_reported(self) -> None:
        sources(self.appendix, [
            src("C1", "Hybrid working from home improves retention without damaging performance", REAL, "Tier 1"),
            src("C2", "A paper that does not exist", "10.9999/not-there"),
            src("C3", "Remote work and productivity gains in software teams", "10.9999/fake.preprint.1"),
            src("C4", "A synthetic retracted article", "10.9999/fake.retracted.1"),
            {"claim_id": "L1", "source_title": "A local file", "url": "appendix/data/x.csv", "tier": "Tier 3", "kind": "data"},
            {"claim_id": "C5", "source_title": "Own computation", "url": "appendix/analysis.py", "tier": "Tier 2", "kind": "own-computation"},
        ])
        problems = papers.verify(self.ctx())
        text = "\n".join(problems)
        self.assertNotIn("C1", text)
        self.assertRegex(text, r"C2.*not found")
        self.assertRegex(text, r"C3.*title")
        self.assertRegex(text, r"C4.*retracted")
        self.assertNotIn("L1", text)
        self.assertNotIn("C5", text)

    def test_verify_records_what_it_saw_in_papers_csv(self) -> None:
        sources(self.appendix, [src("C1", "Hybrid working from home improves retention without damaging performance", REAL, "Tier 1")])
        papers.verify(self.ctx())
        self.assertEqual([r["doi"] for r in read_csv(self.appendix / "papers.csv")], [REAL])

    def test_offline_verify_says_it_cannot_verify(self) -> None:
        sources(self.appendix, [src("C1", "x", REAL)])
        with self.assertRaises(base.ProviderUnavailable):
            papers.verify(self.ctx(HEURISMA_OFFLINE="1"))

    def test_title_overlap_ignores_labels_case_and_short_words(self) -> None:
        a = "Hybrid working from home improves retention (abstract only)"
        self.assertGreaterEqual(base.title_overlap(a, "Hybrid Working From Home Improves Retention"), 0.99)
        self.assertLess(base.title_overlap("Quarterly attrition among nurses", "Remote work and productivity gains"), 0.2)
        self.assertEqual(base.title_overlap("", "anything"), 0.0)


class TestImport(Base):
    def test_a_search_response_saved_elsewhere_is_validated_normalised_and_stored(self) -> None:
        recs = papers.import_json(self.ctx(), "openalex", FIX / "openalex_search.json")
        self.assertEqual(len(recs), 6)
        self.assertEqual({r["via"] for r in read_csv(self.appendix / "papers.csv")}, {"import"})
        self.assertEqual(self.server.requests, [])
        raw = [p for p in (self.appendix / "data" / "papers" / "raw").glob("import_openalex-*")]
        self.assertEqual(len(raw), 1)
        self.assertIn(f"papers/raw/{raw[0].name}", (self.appendix / "download_log.csv").read_text(encoding="utf-8"))
        self.assertEqual(read_csv(self.appendix / "search_log.csv")[0]["provider"], "import:openalex")

    def test_every_provider_shape_is_accepted_and_a_wrong_shape_is_refused(self) -> None:
        self.assertEqual(len(papers.import_json(self.ctx(), "crossref", FIX / "crossref_work.json")), 1)
        self.assertEqual(len(papers.import_json(self.ctx(), "europepmc", FIX / "europepmc_search.json")), 2)
        self.assertEqual(len(papers.import_json(self.ctx(), "arxiv", FIX / "arxiv_feed.xml")), 2)
        self.assertEqual(len(papers.import_json(self.ctx(), "openalex", FIX / "openalex_work.json")), 1)
        with self.assertRaises(base.ProviderUnavailable):
            papers.import_json(self.ctx(), "crossref", FIX / "arxiv_feed.xml")
        bad = self.appendix.parent / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(base.ProviderUnavailable):
            papers.import_json(self.ctx(), "openalex", bad)
        with self.assertRaises(base.ProviderUnavailable):
            papers.import_json(self.ctx(), "openalex", self.appendix.parent / "missing.json")


class TestReplay(Base):
    def test_a_registry_built_by_the_connector_replays_cleanly(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        papers.search(self.ctx(), "europepmc", "y")
        papers.lookup(self.ctx(), REAL)
        self.assertEqual(papers.replay(self.ctx()), [])
        self.assertEqual(self.server.requests.count(None), 0)

    def test_replay_never_touches_the_network(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        before = len(self.server.requests)
        papers.replay(self.ctx())
        self.assertEqual(len(self.server.requests), before)

    def test_a_hand_edited_title_a_hand_added_row_and_a_deleted_cache_file_are_reported(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        rows = read_csv(self.appendix / "papers.csv")
        rows[0]["title"] = "A title nobody retrieved"
        rows.append({**{c: "" for c in PAPER_COLS}, "doi": "10.9999/made.up", "title": "Invented", "work_type": "article", "via": "api"})
        papers._write_atomic(self.appendix / "papers.csv", PAPER_COLS, rows)
        text = "\n".join(papers.replay(self.ctx()))
        self.assertIn(rows[0]["doi"], text)
        self.assertRegex(text, r"title")
        self.assertRegex(text, r"10\.9999/made\.up.*(not supported|no cached response)")
        next((self.appendix / "data" / "papers" / "raw").glob("openalex-*")).unlink()
        self.assertTrue(any("cache" in m.lower() for m in papers.replay(self.ctx())))

    def test_imported_records_replay_too(self) -> None:
        papers.import_json(self.ctx(), "europepmc", FIX / "europepmc_search.json")
        self.assertEqual(papers.replay(self.ctx()), [])


class TestCliPhase2(Base):
    def run_cli(self, *args: str, **env: str):
        import os
        import subprocess

        e = {k: v for k, v in os.environ.items() if not k.startswith("HEURISMA_")}
        e.update(self.env)
        e["HEURISMA_BACKOFF"] = "0"  # no waiting between retries in a test
        e.update(env)
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / "papers.py"), *args, "--appendix", str(self.appendix)], capture_output=True, text=True, encoding="utf-8", env=e)

    def test_import_replay_and_verify_from_the_command_line(self) -> None:
        r = self.run_cli("import", "--provider", "openalex", "--file", str(FIX / "openalex_search.json"))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        r = self.run_cli("replay")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        sources(self.appendix, [src("C2", "A paper that does not exist", "10.9999/not-there")])
        r = self.run_cli("verify")
        self.assertEqual(r.returncode, 1)
        self.assertIn("C2", r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_cite_with_fulltext_flag_reports_a_missing_file_cleanly(self) -> None:
        self.run_cli("search", "--provider", "openalex", "--query", "x")
        sources(self.appendix, [])
        r = self.run_cli("cite", REAL, "--tier", "Tier 1", "--fulltext")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
