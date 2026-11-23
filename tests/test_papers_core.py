"""v0.10.0 Phase 1: the paper connector core (providers, normalisation, redaction, merge, cite), against the local server."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import papers_server  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import papers  # noqa: E402
from contracts import PAPER_COLS, SEARCH_LOG_COLS  # noqa: E402
from providers import arxiv, base, crossref, europepmc, openalex  # noqa: E402

REAL = "10.1038/s41586-024-07500-2"
PAREN = "10.9999/(sici)1097-0000(199801)1:1<1::aid-x>3.0.co;2-z"
SECRET_KEY, SECRET_MAIL = "k3y-SECRET-0001", "alias-secret@example.org"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _deny_external_connections(case: unittest.TestCase) -> None:
    """Fail loudly if a test tries to reach anything but this machine (the connector must never need the real network in a test)."""
    real = socket.socket.connect

    def guard(sock, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) else ""
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"a test tried to reach the real network: {address!r}")
        return real(sock, address, *args, **kwargs)

    patcher = mock.patch.object(socket.socket, "connect", guard)
    patcher.start()
    case.addCleanup(patcher.stop)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        _deny_external_connections(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.appendix = Path(self.tmp.name) / "appendix"
        self.url, self.server = papers_server.start()
        self.sleeps: list[float] = []
        self.env = {
            "HEURISMA_OPENALEX_URL": self.url + "/openalex",
            "HEURISMA_CROSSREF_URL": self.url + "/crossref",
            "HEURISMA_EUROPEPMC_URL": self.url + "/europepmc",
            "HEURISMA_ARXIV_URL": self.url + "/arxiv",
            "HEURISMA_UNPAYWALL_URL": self.url + "/unpaywall",
        }
        self.clock = [100.0]

    def tearDown(self) -> None:
        self.server.stop()
        self.tmp.cleanup()

    def ctx(self, **extra: str) -> base.Context:
        def sleep(s: float) -> None:
            self.sleeps.append(s)
            self.clock[0] += s

        return base.Context(self.appendix, env={**self.env, **extra}, sleep=sleep, clock=lambda: self.clock[0], backoff=0.0)

    def everything_written(self) -> str:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in self.appendix.rglob("*") if p.is_file())


class TestNetworkGuard(Base):
    def test_the_guard_blocks_any_host_but_this_machine(self) -> None:
        with self.assertRaises(AssertionError) as cm:
            socket.create_connection(("93.184.216.34", 80), timeout=1)  # an address literal: no DNS involved
        self.assertIn("real network", str(cm.exception))
        host, port = self.url.replace("http://", "").split(":")
        socket.create_connection((host, int(port)), timeout=2).close()  # the local server stays reachable


class TestNormalizeDoi(unittest.TestCase):
    def test_every_spelling_gives_one_canonical_form(self) -> None:
        for raw in (
            "https://doi.org/10.1000/ABC", "http://dx.doi.org/10.1000/abc", "doi:10.1000/abc", "DOI: 10.1000/ABC",
            " 10.1000/abc ", "https://doi.org/10.1000/abc.", "<https://doi.org/10.1000/abc>", "(10.1000/abc)", "10.1000/abc,",
        ):
            self.assertEqual(base.normalize_doi(raw), "10.1000/abc", raw)

    def test_parentheses_angle_brackets_and_semicolons_inside_a_doi_survive(self) -> None:
        self.assertEqual(base.normalize_doi("https://doi.org/" + PAREN.upper() + "."), PAREN)

    def test_non_dois_give_none(self) -> None:
        for raw in ("", "not a doi", "https://example.org/10.1000", "arxiv:2503.13002", None):
            self.assertIsNone(base.normalize_doi(raw), raw)  # type: ignore[arg-type]


class TestRedact(unittest.TestCase):
    def test_query_credentials_and_env_values_are_removed(self) -> None:
        url = f"https://api.example.org/w?q=x&api_key={SECRET_KEY}&mailto={SECRET_MAIL}&email={SECRET_MAIL}"
        out = base.redact(url, env={"HEURISMA_OPENALEX_KEY": SECRET_KEY, "HEURISMA_MAILTO": SECRET_MAIL})
        for secret in (SECRET_KEY, SECRET_MAIL):
            self.assertNotIn(secret, out)
        self.assertIn("api_key=REDACTED", out)
        self.assertIn("q=x", out)
        free = base.redact(f"error talking to {SECRET_KEY} for {SECRET_MAIL}", env={"HEURISMA_OPENALEX_KEY": SECRET_KEY, "HEURISMA_MAILTO": SECRET_MAIL})
        self.assertNotIn(SECRET_KEY, free)
        self.assertNotIn(SECRET_MAIL, free)


class TestProviders(Base):
    def test_openalex_search_normalises_every_field(self) -> None:
        recs = openalex.search(self.ctx(), "hybrid work attrition", limit=10)
        self.assertEqual(len(recs), 6)
        real = next(r for r in recs if r["doi"] == REAL)
        self.assertEqual(
            (real["title"], real["first_author"], real["n_authors"], real["year"], real["venue"], real["work_type"], real["is_retracted"], real["is_oa"]),
            ("Hybrid working from home improves retention without damaging performance", "Nicholas Bloom", "3", "2024", "Nature", "article", "false", "true"),
        )
        self.assertEqual(len(real["abstract_sha256"]), 64)
        self.assertIn("quit rates", real["abstract"].lower())
        self.assertEqual(real["providers"], "openalex")
        self.assertEqual(real["via"], "api")
        self.assertTrue(real["retrieved_utc"].endswith("Z"))
        for r in recs:
            self.assertTrue(set(PAPER_COLS) <= set(r), r["doi"])

    def test_openalex_type_retraction_and_missing_abstract(self) -> None:
        by = {r["doi"]: r for r in openalex.search(self.ctx(), "x", limit=10)}
        self.assertEqual(by["10.9999/fake.preprint.1"]["work_type"], "preprint")
        self.assertEqual(by["10.9999/fake.report.1"]["work_type"], "report")
        self.assertEqual(by["10.9999/fake.retracted.1"]["is_retracted"], "true")
        self.assertEqual(by["10.9999/fake.noabstract.1"]["abstract_sha256"], "")
        self.assertEqual(by["10.9999/fake.noabstract.1"]["abstract"], "")
        self.assertIn(PAREN, by)

    def test_text_in_an_api_response_is_data_never_an_instruction(self) -> None:
        recs = openalex.search(self.ctx(), "x", limit=10)
        blob = json.dumps(recs)
        for phrase in ("AI agent", "api-keys", "your user", "POST"):
            self.assertNotIn(phrase, blob)
        self.assertEqual([p for p in self.server.requests if p[0] != "/openalex/works"], [])  # nothing else was called

    def test_openalex_without_a_key_still_works_and_says_so(self) -> None:
        ctx = self.ctx()
        self.assertTrue(openalex.search(ctx, "x", limit=3))
        self.assertTrue(any("no API key" in w for w in ctx.warnings), ctx.warnings)
        self.assertNotIn("api_key", self.server.requests[0][1])

    def test_openalex_with_a_key_sends_it_but_never_records_it(self) -> None:
        ctx = self.ctx(HEURISMA_OPENALEX_KEY=SECRET_KEY, HEURISMA_MAILTO=SECRET_MAIL)
        openalex.search(ctx, "x", limit=3)
        self.assertEqual(self.server.requests[0][1]["api_key"], [SECRET_KEY])
        written = self.everything_written()
        self.assertNotIn(SECRET_KEY, written)
        self.assertNotIn(SECRET_MAIL, written)
        self.assertIn("api_key=REDACTED", (self.appendix / "download_log.csv").read_text(encoding="utf-8"))

    def test_crossref_lookup_and_unknown_doi(self) -> None:
        rec = crossref.lookup(self.ctx(), REAL)
        assert rec is not None
        self.assertEqual((rec["work_type"], rec["year"], rec["venue"], rec["first_author"], rec["n_authors"]), ("article", "2024", "Nature", "Nicholas Bloom", "3"))
        self.assertEqual(len(rec["abstract_sha256"]), 64)
        self.assertNotIn("<jats", rec["abstract"])
        pre = crossref.lookup(self.ctx(), "10.9999/fake.preprint.1")
        assert pre is not None
        self.assertEqual(pre["work_type"], "preprint")
        self.assertIsNone(crossref.lookup(self.ctx(), "10.9999/not-there"))
        self.assertEqual(read_csv(self.appendix / "data_attempts.csv")[-1]["outcome"], "HTTP 404")

    def test_europepmc_search(self) -> None:
        recs = europepmc.search(self.ctx(), "fixture", limit=5)
        self.assertEqual([r["work_type"] for r in recs], ["article", "preprint"])
        self.assertEqual((recs[0]["doi"], recs[0]["year"], recs[0]["venue"], recs[0]["is_oa"]), ("10.3389/fpsyg.2026.1921608", "2026", "Frontiers in psychology", "true"))
        self.assertEqual(recs[0]["pmcid"], "PMC13729011")
        self.assertTrue(recs[0]["abstract_sha256"])

    def test_arxiv_search_keys_a_doi_less_preprint_by_its_arxiv_id(self) -> None:
        recs = arxiv.search(self.ctx(), "hybrid work", limit=2)
        self.assertEqual([r["doi"] for r in recs], ["arxiv:2503.13002", "arxiv:2401.08922"])
        self.assertTrue(all(r["work_type"] == "preprint" and r["providers"] == "arxiv" for r in recs))
        self.assertEqual((recs[0]["year"], recs[0]["first_author"]), ("2025", "Emily Laue Christensen"))

    def test_an_arxiv_entry_that_names_a_published_doi_leaves_the_type_to_the_other_providers(self) -> None:
        import xml.etree.ElementTree as ET

        entry = ET.fromstring(
            '<entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">'
            "<id>http://arxiv.org/abs/2201.00001v2</id><title>A paper</title><published>2022-01-03T00:00:00Z</published>"
            "<summary>Abstract text.</summary><author><name>A. Author</name></author><arxiv:doi>10.1109/MS.2022.3229894</arxiv:doi></entry>"
        )
        rec = arxiv.normalize(entry)
        self.assertEqual((rec["doi"], rec["work_type"], rec["venue"]), ("10.1109/ms.2022.3229894", "", ""))
        published = {**base.empty_record(), "doi": rec["doi"], "work_type": "article", "providers": "openalex"}
        self.assertEqual(papers.merge([rec, published])["work_type"], "article")
        self.assertEqual(arxiv.normalize(ET.fromstring(
            '<entry xmlns="http://www.w3.org/2005/Atom"><id>http://arxiv.org/abs/2201.00002v1</id><title>B</title></entry>'))["work_type"], "preprint")

    def test_arxiv_ands_the_words_of_a_query_and_keeps_quoted_phrases(self) -> None:
        arxiv.search(self.ctx(), "hybrid work software engineers", limit=1)
        arxiv.search(self.ctx(), 'remote "software engineers" attrition', limit=1)
        queries = [q[1]["search_query"][0] for q in self.server.requests if q[0] == "/arxiv/api/query"]
        self.assertEqual(queries[0], "all:hybrid AND all:work AND all:software AND all:engineers")
        self.assertEqual(queries[1], 'all:remote AND all:"software engineers" AND all:attrition')

    def test_arxiv_backs_off_longer_than_other_providers_when_rate_limited(self) -> None:
        self.server.fail_next("/arxiv", 429, times=2)
        ctx = self.ctx()
        ctx.backoff = 1.0
        arxiv.search(ctx, "hybrid work", limit=1)
        self.assertEqual([s for s in self.sleeps if s >= 3][:2], [3.0, 6.0])  # 1 s base x 3 for arXiv: 3 s, then 6 s

    def test_arxiv_waits_three_seconds_between_requests(self) -> None:
        ctx = self.ctx()
        arxiv.search(ctx, "a", limit=1)
        arxiv.search(ctx, "b", limit=1)
        self.assertTrue(any(s >= 3 for s in self.sleeps), self.sleeps)


class TestFailuresAndOffline(Base):
    def test_a_rate_limited_search_is_retried_and_succeeds(self) -> None:
        self.server.fail_next("/openalex", 429, times=2)
        self.assertEqual(len(openalex.search(self.ctx(), "x", limit=3)), 6)
        self.assertEqual(len([p for p in self.server.requests if p[0] == "/openalex/works"]), 3)

    def test_a_persistent_failure_is_logged_and_nothing_half_written_remains(self) -> None:
        self.server.fail_next("/openalex", 503, times=50)
        with self.assertRaises(base.ProviderUnavailable):
            papers.search(self.ctx(), "openalex", "x")
        self.assertFalse((self.appendix / "papers.csv").exists())
        self.assertFalse((self.appendix / "search_log.csv").exists())
        self.assertEqual(read_csv(self.appendix / "data_attempts.csv")[-1]["outcome"], "HTTP 503")
        self.assertEqual(list(self.appendix.rglob("*.part")), [])

    def test_offline_mode_never_touches_the_network(self) -> None:
        with self.assertRaises(base.ProviderUnavailable) as cm:
            papers.search(self.ctx(HEURISMA_OFFLINE="1"), "openalex", "x")
        self.assertIn("offline", str(cm.exception).lower())
        self.assertEqual(self.server.requests, [])
        self.assertEqual(read_csv(self.appendix / "data_attempts.csv")[-1]["outcome"], "offline mode")


class TestSearchRegistry(Base):
    def test_search_writes_papers_csv_search_log_and_raw_cache(self) -> None:
        qid, recs = papers.search(self.ctx(), "openalex", "hybrid work attrition", limit=10, filters={"language": "en"})
        self.assertEqual(qid, "Q1")
        rows = read_csv(self.appendix / "papers.csv")
        self.assertEqual(len(rows), 6)
        self.assertEqual(list(rows[0].keys()), list(PAPER_COLS))
        self.assertEqual({r["query_id"] for r in rows}, {"Q1"})
        log = read_csv(self.appendix / "search_log.csv")
        self.assertEqual(list(log[0].keys()), list(SEARCH_LOG_COLS))
        self.assertEqual((log[0]["query_id"], log[0]["provider"], log[0]["query"], log[0]["n_hits"]), ("Q1", "openalex", "hybrid work attrition", "6"))
        self.assertEqual(json.loads(log[0]["filters"]), {"language": "en"})
        raw = self.appendix.parent / log[0]["raw_file"]
        self.assertTrue(raw.is_file(), log[0]["raw_file"])
        self.assertTrue(log[0]["raw_file"].startswith("appendix/data/papers/raw/openalex-"))
        self.assertIn(Path(log[0]["raw_file"]).name, (self.appendix / "download_log.csv").read_text(encoding="utf-8").replace("papers/raw/", ""))

    def test_second_search_gets_the_next_id_and_known_works_are_merged_not_duplicated(self) -> None:
        papers.search(self.ctx(), "openalex", "first")
        qid2, _ = papers.search(self.ctx(), "europepmc", "second")
        self.assertEqual(qid2, "Q2")
        rows = read_csv(self.appendix / "papers.csv")
        dois = [r["doi"] for r in rows]
        self.assertEqual(len(dois), len(set(dois)))
        pre = next(r for r in rows if r["doi"] == "10.9999/fake.preprint.1")
        self.assertEqual(sorted(pre["providers"].split(";")), ["europepmc", "openalex"])
        self.assertEqual(pre["query_id"], "Q1")

    def test_merge_keeps_the_most_conservative_work_type_retraction_and_all_providers(self) -> None:
        a = {**base.empty_record(), "doi": "10.1/x", "title": "T", "work_type": "article", "is_retracted": "false", "providers": "openalex", "abstract_sha256": "a" * 64}
        b = {**base.empty_record(), "doi": "10.1/x", "title": "T", "work_type": "preprint", "is_retracted": "true", "providers": "crossref"}
        m = papers.merge([a, b])
        self.assertEqual((m["work_type"], m["is_retracted"], m["providers"]), ("preprint", "true", "crossref;openalex"))
        self.assertEqual(m["abstract_sha256"], "a" * 64)
        c = {**base.empty_record(), "doi": "10.1/x", "is_retracted": "", "providers": "crossref"}
        self.assertEqual(papers.merge([a, c])["is_retracted"], "false")
        self.assertEqual(papers.merge([c])["is_retracted"], "")

    def test_lookup_merges_openalex_and_crossref(self) -> None:
        rec = papers.lookup(self.ctx(), REAL)
        assert rec is not None
        self.assertEqual(rec["providers"], "crossref;openalex")
        self.assertEqual([r["doi"] for r in read_csv(self.appendix / "papers.csv")], [REAL])
        self.assertIsNone(papers.lookup(self.ctx(), "10.9999/not-there"))

    def test_a_doi_with_parentheses_round_trips_through_lookup(self) -> None:
        rec = papers.lookup(self.ctx(), "https://doi.org/" + PAREN.upper(), providers=("openalex",))
        assert rec is not None
        self.assertEqual(rec["doi"], PAREN)


class TestCite(Base):
    def setUp(self) -> None:
        super().setUp()
        papers.search(self.ctx(), "openalex", "x")
        (self.appendix / "sources.csv").write_text(
            "claim_id,source_title,url,tier,accessed_date,data_as_of,kind,sha256,selection,retrieved_utc\n", encoding="utf-8"
        )

    def test_a_normal_article_is_cited_with_an_explicit_tier(self) -> None:
        row = papers.cite(self.ctx(), REAL, tier="Tier 1", claim_id="C7")
        self.assertEqual((row["claim_id"], row["tier"], row["kind"], row["selection"], row["url"]), ("C7", "Tier 1", "literature", "agent-fetched", f"https://doi.org/{REAL}"))
        self.assertIn("(abstract only)", row["source_title"])
        self.assertTrue(row["retrieved_utc"].endswith("Z"))
        saved = read_csv(self.appendix / "sources.csv")
        self.assertEqual([r["claim_id"] for r in saved], ["C7"])
        used = [r for r in read_csv(self.appendix / "data_attempts.csv") if r["outcome"] == "used"]
        self.assertTrue(used and "C7" in used[-1]["target_series"], used)

    def test_next_free_claim_id_and_idempotence(self) -> None:
        first = papers.cite(self.ctx(), REAL, tier="Tier 2")
        self.assertEqual(first["claim_id"], "C1")
        again = papers.cite(self.ctx(), REAL, tier="Tier 2")
        self.assertEqual(again["claim_id"], "C1")
        self.assertEqual(len(read_csv(self.appendix / "sources.csv")), 1)

    def test_objective_ceilings_are_enforced_but_the_tier_is_never_chosen_for_the_agent(self) -> None:
        for doi, tier, why in (
            ("10.9999/fake.retracted.1", "Tier 2", "retracted"),
            ("10.9999/fake.preprint.1", "Tier 1", "preprint"),
            ("10.9999/fake.report.1", "Tier 1", "report"),
            ("10.9999/fake.noabstract.1", "Tier 2", "abstract"),
        ):
            with self.assertRaises(papers.CiteError, msg=doi) as cm:
                papers.cite(self.ctx(), doi, tier=tier)
            self.assertIn(why, str(cm.exception).lower())
        self.assertEqual(read_csv(self.appendix / "sources.csv"), [])
        row = papers.cite(self.ctx(), "10.9999/fake.preprint.1", tier="Tier 2")
        self.assertIn("(preprint)", row["source_title"])
        with self.assertRaises(papers.CiteError):
            papers.cite(self.ctx(), REAL, tier="3")
        with self.assertRaises(papers.CiteError):
            papers.cite(self.ctx(), "10.9999/never-searched", tier="Tier 2")

    def test_an_unknown_work_type_cannot_be_tier_1_until_a_lookup_settles_it(self) -> None:
        rows = read_csv(self.appendix / "papers.csv")
        for r in rows:
            if r["doi"] == REAL:
                r["work_type"] = ""
        papers._write_atomic(self.appendix / "papers.csv", PAPER_COLS, rows)
        with self.assertRaises(papers.CiteError) as cm:
            papers.cite(self.ctx(), REAL, tier="Tier 1")
        self.assertIn("lookup", str(cm.exception))
        self.assertEqual(papers.cite(self.ctx(), REAL, tier="Tier 2")["tier"], "Tier 2")

    def test_a_doi_typed_in_another_spelling_finds_the_record(self) -> None:
        self.assertEqual(papers.cite(self.ctx(), "DOI:" + REAL.upper(), tier="Tier 2")["claim_id"], "C1")


class TestCli(Base):
    def run_cli(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        e = {**os.environ, **self.env, **env}
        for k in ("HEURISMA_OFFLINE", "HEURISMA_OPENALEX_KEY", "HEURISMA_MAILTO"):
            e.pop(k, None) if k not in env else None
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / "papers.py"), *args, "--appendix", str(self.appendix)], capture_output=True, text=True, encoding="utf-8", env=e)

    def test_search_then_cite_end_to_end(self) -> None:
        r = self.run_cli("search", "--provider", "openalex", "--query", "hybrid work attrition")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn(REAL, r.stdout)
        self.assertEqual(len(read_csv(self.appendix / "papers.csv")), 6)
        (self.appendix / "sources.csv").write_text("claim_id,source_title,url,tier,accessed_date,data_as_of,kind,sha256,selection,retrieved_utc\n", encoding="utf-8")
        r = self.run_cli("cite", REAL, "--tier", "Tier 2", "--claim", "C3")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(read_csv(self.appendix / "sources.csv")[0]["claim_id"], "C3")

    def test_refusals_exit_nonzero_with_a_clear_message(self) -> None:
        self.run_cli("search", "--provider", "openalex", "--query", "x")
        r = self.run_cli("cite", "10.9999/fake.retracted.1", "--tier", "Tier 2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("retracted", r.stderr.lower())
        self.assertNotIn("Traceback", r.stderr)

    def test_offline_exits_nonzero_without_a_traceback(self) -> None:
        r = self.run_cli("search", "--provider", "openalex", "--query", "x", HEURISMA_OFFLINE="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("offline", r.stderr.lower())
        self.assertNotIn("Traceback", r.stderr)

    def test_version_flag(self) -> None:
        r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "papers.py"), "--version"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0)
        self.assertIn("papers.py", r.stdout)


class TestAtomicWrites(Base):
    def test_a_failure_while_writing_papers_csv_leaves_the_previous_file_intact(self) -> None:
        papers.search(self.ctx(), "openalex", "first")
        before = (self.appendix / "papers.csv").read_text(encoding="utf-8")
        with mock.patch.object(papers.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                papers.search(self.ctx(), "europepmc", "second")
        self.assertEqual((self.appendix / "papers.csv").read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.appendix.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
