"""v0.10.0 audit, Task 2: the connector's registry must not be forgeable by editing one column, one file or one URL."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import papers_server  # noqa: E402
from test_papers_core import REAL, SECRET_MAIL, Base, read_csv  # noqa: E402
import validate_report  # noqa: E402

import papers  # noqa: E402
from contracts import PAPER_COLS  # noqa: E402
from providers import base  # noqa: E402

FIX = papers_server.FIXTURES


def edit_row(appendix: Path, doi: str, **changes: str) -> None:
    rows = read_csv(appendix / "papers.csv")
    for r in rows:
        if r["doi"] == doi:
            r.update(changes)
    papers._write_atomic(appendix / "papers.csv", PAPER_COLS, rows)


def write_sources(appendix: Path, rows: list[dict[str, str]]) -> None:
    appendix.mkdir(parents=True, exist_ok=True)
    cols = ["claim_id", "source_title", "url", "tier", "accessed_date", "data_as_of", "kind", "sha256", "selection", "retrieved_utc"]
    with (appendix / "sources.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(rows)


def src(cid: str, title: str, url: str, tier: str = "Tier 2") -> dict[str, str]:
    return {"claim_id": cid, "source_title": title, "url": url, "tier": tier, "kind": "literature", "selection": "agent-fetched"}


class TestKeysAndUrls(unittest.TestCase):
    def test_a_registry_key_and_its_url_are_inverse_for_every_kind_of_work(self) -> None:
        for key, url in (
            ("10.1038/s41586-024-07500-2", "https://doi.org/10.1038/s41586-024-07500-2"),
            ("arxiv:2401.08922", "https://arxiv.org/abs/2401.08922"),
            ("openalex:w2741809807", "https://openalex.org/W2741809807"),
            ("epmc:med:12345", "https://europepmc.org/article/MED/12345"),
        ):
            self.assertEqual(base.url_for_key(key), url)
            self.assertEqual(base.key_from_url(url), key, url)

    def test_the_doi_is_found_wherever_it_sits_in_a_url(self) -> None:
        for url in (
            "https://www.nature.com/articles/10.9999/fake.publisher.1",
            "https://doi.org/10.9999/fake.publisher.1?utm_source=x",
            "https://dx.doi.org/10.9999/FAKE.publisher.1#abstract",
            "https://example.org/read?doi=10.9999/fake.publisher.1",
            "https://doi.org/10.9999%2Ffake.publisher.1",
        ):
            self.assertEqual(base.key_from_url(url), "10.9999/fake.publisher.1", url)
        self.assertIsNone(base.key_from_url("https://example.org/no-doi-here"))
        self.assertIsNone(base.key_from_url(""))
        self.assertEqual(base.key_from_url("https://arxiv.org/pdf/2401.08922v2.pdf"), "arxiv:2401.08922")


class TestViaIsNeverStuck(Base):
    def test_a_lookup_after_an_import_makes_the_record_connector_retrieved(self) -> None:
        papers.import_json(self.ctx(), "openalex", FIX / "openalex_search.json")
        self.assertEqual(next(r for r in read_csv(self.appendix / "papers.csv") if r["doi"] == REAL)["via"], "import")
        papers.lookup(self.ctx(), REAL)
        row = next(r for r in read_csv(self.appendix / "papers.csv") if r["doi"] == REAL)
        self.assertEqual(row["via"], "api")
        self.assertEqual(papers.replay(self.ctx()), [])

    def test_a_record_that_only_ever_came_from_imports_stays_imported(self) -> None:
        papers.import_json(self.ctx(), "openalex", FIX / "openalex_search.json")
        papers.import_json(self.ctx(), "crossref", FIX / "crossref_work.json")
        self.assertEqual(next(r for r in read_csv(self.appendix / "papers.csv") if r["doi"] == REAL)["via"], "import")


class TestReplayTrustsOnlyLoggedCache(Base):
    def raw(self) -> Path:
        return self.appendix / "data" / "papers" / "raw"

    def test_a_file_dropped_into_the_cache_without_a_logged_hash_explains_nothing(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        real = next(self.raw().glob("openalex-*"))
        forged = self.raw() / "openalex-forged-001.json"
        forged.write_bytes(real.read_bytes().replace(b"Hybrid working", b"Forged working"))
        rows = read_csv(self.appendix / "papers.csv")
        rows[0]["title"] = "Forged working from home improves retention without damaging performance"
        papers._write_atomic(self.appendix / "papers.csv", PAPER_COLS, rows)
        text = "\n".join(papers.replay(self.ctx()))
        self.assertRegex(text, r"openalex-forged-001\.json.*download_log")
        self.assertIn("differs from every cached response", text)

    def test_a_cache_file_edited_after_it_was_logged_is_not_trusted(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        real = next(self.raw().glob("openalex-*"))
        real.write_bytes(real.read_bytes().replace(b"Hybrid", b"Changed"))
        self.assertRegex("\n".join(papers.replay(self.ctx())), rf"{re.escape(real.name)}.*(?:SHA-256|hash|download_log)")

    def test_renaming_an_imported_response_to_look_retrieved_is_detected(self) -> None:
        papers.import_json(self.ctx(), "openalex", FIX / "openalex_search.json")
        imported = next(self.raw().glob("import_openalex-*"))
        imported.rename(self.raw() / imported.name.replace("import_", ""))
        self.assertTrue(papers.replay(self.ctx()))

    def test_a_clean_registry_still_replays_cleanly_after_search_lookup_and_import(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        papers.search(self.ctx(), "europepmc", "y")
        papers.import_json(self.ctx(), "arxiv", FIX / "arxiv_feed.xml")
        papers.lookup(self.ctx(), REAL)
        self.assertEqual(papers.replay(self.ctx()), [])


class TestReplayComparesProvenanceColumns(Base):
    def test_every_provenance_column_is_compared(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        original = (self.appendix / "papers.csv").read_bytes()
        self.assertEqual(papers.replay(self.ctx()), [])
        for column, value in (("via", "import"), ("providers", "openalex;crossref"), ("is_oa", "false"), ("retrieved_utc", "2099-01-01T00:00:00Z"), ("title", "")):
            with self.subTest(column=column):
                (self.appendix / "papers.csv").write_bytes(original)
                edit_row(self.appendix, REAL, **{column: value})
                self.assertRegex("\n".join(papers.replay(self.ctx())), rf"{re.escape(REAL)}.*\b{column}\b")

    def test_a_retrieval_time_a_little_after_the_download_is_normal(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        rows = read_csv(self.appendix / "papers.csv")
        self.assertEqual(papers.replay(self.ctx()), [])
        self.assertTrue(all(r["retrieved_utc"] for r in rows))


class TestCiteIsHonestAboutWhatItDid(Base):
    def test_citing_again_with_another_tier_or_claim_is_an_error_not_a_silent_old_row(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        write_sources(self.appendix, [])
        first = papers.cite(self.ctx(), REAL, tier="Tier 2")
        self.assertEqual(papers.cite(self.ctx(), REAL, tier="Tier 2"), first)  # an identical repeat is idempotent
        with self.assertRaises(papers.CiteError) as cm:
            papers.cite(self.ctx(), REAL, tier="Tier 1")
        self.assertIn(first["claim_id"], str(cm.exception))
        with self.assertRaises(papers.CiteError):
            papers.cite(self.ctx(), REAL, tier="Tier 2", claim_id="C9")
        self.assertEqual(len(read_csv(self.appendix / "sources.csv")), 1)

    def test_asking_for_the_full_text_of_an_abstract_only_citation_does_not_pretend(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        write_sources(self.appendix, [])
        papers.cite(self.ctx(), REAL, tier="Tier 2")
        before = len(self.server.requests)
        with self.assertRaises(papers.CiteError) as cm:
            papers.cite(self.ctx(), REAL, tier="Tier 2", fulltext=True)
        self.assertIn("already registered", str(cm.exception))
        self.assertEqual(len(self.server.requests), before)  # nothing was downloaded for a row that would not change

    def test_a_work_with_no_doi_is_cited_with_a_real_url_the_validator_can_map_back(self) -> None:
        crafted = Path(self.tmp.name) / "epmc.json"
        crafted.write_text(json.dumps({"resultList": {"result": [{"id": "12345", "source": "MED", "title": "A study without a DOI", "abstractText": "An abstract.", "pubYear": "2024", "pubTypeList": {"pubType": ["Journal Article"]}}]}}), encoding="utf-8")
        recs = papers.import_json(self.ctx(), "europepmc", crafted)
        self.assertEqual(recs[0]["doi"], "epmc:med:12345")
        write_sources(self.appendix, [])
        row = papers.cite(self.ctx(), "epmc:med:12345", tier="Tier 2")
        self.assertEqual(row["url"], "https://europepmc.org/article/MED/12345")
        self.assertEqual(base.key_from_url(row["url"]), "epmc:med:12345")


class TestFulltextNaming(Base):
    def test_two_dois_that_slug_alike_never_share_a_file(self) -> None:
        a, b = papers.fulltext_filename("10.1234/a-b", "pdf"), papers.fulltext_filename("10.1234/a_b", "pdf")
        self.assertNotEqual(a, b)
        self.assertEqual(a, papers.fulltext_filename("10.1234/a-b", "pdf"))  # deterministic
        self.assertRegex(a, r"^papers/10\.1234_a_b-[0-9a-f]{8}\.pdf$")

    def test_a_rejected_download_removes_only_its_own_log_row(self) -> None:
        log = self.appendix / "download_log.csv"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(
            "file,url,retrieved_utc,bytes,sha256\n"
            "papers/x.pdf,https://a.example/1,2026-11-20T10:00:00Z,5,aaa\n"
            "papers/other.pdf,https://a.example/2,2026-11-20T10:00:00Z,5,bbb\n"
            "papers/x.pdf,https://a.example/3,2026-11-20T11:00:00Z,5,ccc\n",
            encoding="utf-8",
        )
        papers._drop_download_row(self.appendix, "papers/x.pdf")
        rows = read_csv(log)
        self.assertEqual([(r["file"], r["sha256"]) for r in rows], [("papers/x.pdf", "aaa"), ("papers/other.pdf", "bbb")])


class TestUnpaywallIsTheLastResort(Base):
    def record(self, **fields: str) -> dict[str, str]:
        rec = base.empty_record()
        rec.update(doi=REAL, title="t", is_oa="true", providers="openalex")
        rec.update(fields)
        return rec

    def test_the_contact_address_is_not_sent_when_a_free_copy_works(self) -> None:
        path = papers.fulltext(self.ctx(HEURISMA_MAILTO=SECRET_MAIL), self.record(pmcid="PMC13729011"))
        self.assertIsNotNone(path)
        self.assertEqual([p for p in self.server.requests if p[0].startswith("/unpaywall")], [])

    def test_an_unpaywall_outage_is_a_warning_not_an_exception(self) -> None:
        self.server.fail_next("/unpaywall", 429, times=50)
        ctx = self.ctx(HEURISMA_MAILTO=SECRET_MAIL)
        self.assertIsNone(papers.fulltext(ctx, self.record()))
        self.assertTrue(any("unpaywall" in w.lower() for w in ctx.warnings), ctx.warnings)
        self.assertNotIn(SECRET_MAIL, self.everything_written())
        self.assertNotIn(SECRET_MAIL, "\n".join(ctx.warnings))


class TestVerifyReportsWhatItCouldNotCheck(Base):
    def test_one_provider_outage_does_not_hide_the_other_references(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        write_sources(self.appendix, [
            src("C1", "Some paper in an outage", "https://doi.org/10.9999/fake.outage.1"),
            src("C2", "Completely unrelated title about gardening", f"https://doi.org/{REAL}"),
        ])
        self.server.fail_next("/openalex", 500, times=4)
        self.server.fail_next("/crossref", 500, times=4)
        problems = papers.verify(self.ctx())
        text = "\n".join(problems)
        self.assertRegex(text, r"C1 .*could not be checked")
        self.assertRegex(text, r"C2 .*title")  # the second reference was still examined

    def test_arxiv_references_are_verified_against_arxiv(self) -> None:
        write_sources(self.appendix, [
            src("C1", "Post-Pandemic Hybrid Work in Software Companies (preprint)", "https://arxiv.org/abs/2401.08922"),
            src("C2", "A preprint that does not", "https://arxiv.org/abs/2999.99999"),
        ])
        text = "\n".join(papers.verify(self.ctx()))
        self.assertNotRegex(text, r"C1 ")
        self.assertRegex(text, r"C2 .*not found")

    def test_the_cli_never_claims_every_doi_resolves_when_some_were_not_checked(self) -> None:
        import subprocess

        write_sources(self.appendix, [src("C1", "Some paper in an outage", "https://doi.org/10.9999/fake.outage.1")])
        self.server.fail_next("/openalex", 500, times=8)
        self.server.fail_next("/crossref", 500, times=8)
        env = {**os.environ, **self.env, "HEURISMA_BACKOFF": "0"}
        r = subprocess.run([sys.executable, "-B", str(papers.__file__), "verify", "--appendix", str(self.appendix)], capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("every DOI", r.stdout)


class TestValidatorHolds(unittest.TestCase):
    def run_checks(self, mutation, level: int = 2):  # type: ignore[no-untyped-def]
        tmp, ws = M.fresh_workspace()
        try:
            mutation(ws)
            M.restamp_gates(ws)
            e, w = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)
            keep = lambda ms: [m for m in ms if "papers.csv" in m or "credential" in m or "connector" in m]  # noqa: E731
            return keep(e), keep(w)
        finally:
            tmp.cleanup()

    def test_the_checks_do_not_depend_on_the_kind_or_selection_columns(self) -> None:
        for field, value in (("kind", "press"), ("kind", "data"), ("selection", "third-party")):
            def mutation(ws: Path, field: str = field, value: str = value) -> None:
                M.m41_preprint_declared_tier1(ws)

                def fn(rows: list[dict[str, str]], cols: list[str]):  # type: ignore[no-untyped-def]
                    for r in rows:
                        if r.get("claim_id") == "C5":
                            r[field] = value
                    return rows, cols

                M._rewrite_csv(ws, "appendix/sources.csv", fn)

            e, _ = self.run_checks(mutation)
            self.assertTrue(any(re.search(r"preprint.*Tier 1", m) for m in e), (field, value, e))

    def test_a_publisher_url_that_contains_the_doi_is_still_the_same_work(self) -> None:
        e, _ = self.run_checks(M.m52_publisher_url_hides_the_doi)
        self.assertTrue(any(re.search(r"preprint.*Tier 1", m) for m in e), e)

    def test_typed_from_memory_is_flagged_for_third_party_rows_too(self) -> None:
        def mutation(ws: Path) -> None:
            M.m40_typed_doi_not_in_papers_csv(ws)

            def fn(rows: list[dict[str, str]], cols: list[str]):  # type: ignore[no-untyped-def]
                for r in rows:
                    if r.get("claim_id") == "C5":
                        r["selection"] = "third-party"
                return rows, cols

            M._rewrite_csv(ws, "appendix/sources.csv", fn)

        _, w = self.run_checks(mutation)
        self.assertTrue(any("not in appendix/papers.csv" in m for m in w), w)

    def test_a_recorded_full_text_must_be_a_hashed_file_under_the_papers_folder(self) -> None:
        for rel, sha in (("report.md", ""), ("../../outside.txt", "ab" * 32), ("/etc/hosts", "ab" * 32), ("appendix/data/papers/missing.pdf", "ab" * 32), ("appendix/data/papers/x.pdf", "")):
            def mutation(ws: Path, rel: str = rel, sha: str = sha) -> None:
                (ws / "appendix" / "data" / "papers").mkdir(parents=True, exist_ok=True)
                (ws / "appendix" / "data" / "papers" / "x.pdf").write_bytes(b"%PDF-1.4 fixture")
                M._papers_workspace(ws, [M._paper("10.9999/fake.fulltext.3", "A synthetic article with a bad full text", fulltext_file=rel, fulltext_sha256=sha)])

            e, _ = self.run_checks(mutation)  # must not raise
            self.assertTrue(any("full text" in m for m in e), (rel, e))

    def test_a_valid_saved_full_text_is_accepted(self) -> None:
        import hashlib

        def mutation(ws: Path) -> None:
            target = ws / "appendix" / "data" / "papers" / "ok-12345678.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"%PDF-1.4 fixture")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            (ws / "appendix" / "download_log.csv").write_text(
                f"file,url,retrieved_utc,bytes,sha256\npapers/{target.name},https://example.invalid/x,2026-11-20T12:00:00Z,16,{digest}\n", encoding="utf-8"
            )
            M._papers_workspace(ws, [M._paper("10.9999/fake.fulltext.4", "A synthetic article with a good full text", fulltext_file=f"appendix/data/papers/{target.name}", fulltext_sha256=digest)])

        e, w = self.run_checks(mutation)
        self.assertEqual([m for m in e + w if "full text" in m], [])

    def test_credentials_are_found_anywhere_under_the_appendix_and_by_value(self) -> None:
        def nested(ws: Path) -> None:
            M._papers_workspace(ws)
            (ws / "appendix" / "data").mkdir(parents=True, exist_ok=True)
            (ws / "appendix" / "data" / "notes.csv").write_text("a\nhttps://x.org?api_key=abc123def456\n", encoding="utf-8")

        e, _ = self.run_checks(nested)
        self.assertTrue(any("credential" in m and "notes.csv" in m for m in e), e)

        def by_value(ws: Path) -> None:
            M._papers_workspace(ws)
            (ws / "appendix" / "run-notes.md").write_text("I used the key k3y-SECRET-9999 for OpenAlex.\n", encoding="utf-8")

        with mock.patch.dict(os.environ, {"HEURISMA_OPENALEX_KEY": "k3y-SECRET-9999"}):
            e, _ = self.run_checks(by_value)
        self.assertTrue(any("credential" in m and "run-notes.md" in m for m in e), e)


if __name__ == "__main__":
    unittest.main()
