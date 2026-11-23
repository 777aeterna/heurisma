"""v0.10.0 audit, Task 3: links that come from a response are not trusted, and two commands never lose each other's rows."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_papers_core import REAL, SCRIPTS, Base, read_csv  # noqa: E402

import fetch_lib  # noqa: E402
import papers  # noqa: E402
from providers import base  # noqa: E402


def record(**fields: str) -> dict[str, str]:
    rec = base.empty_record()
    rec.update(doi=REAL, title="t", is_oa="true", providers="openalex")
    rec.update(fields)
    return rec


class TestLinksFromResponsesAreNotTrusted(Base):
    def attempts(self) -> list[dict[str, str]]:
        return read_csv(self.appendix / "data_attempts.csv")

    def test_private_and_local_addresses_are_refused_for_a_link_taken_from_a_response(self) -> None:
        for url in (
            "http://169.254.169.254/latest/meta-data/", "http://10.0.0.1/x.pdf", "http://192.168.1.1/x.pdf", "http://[::1]/x.pdf",
            "http://0.0.0.0/x.pdf", "http://localhost:1/x.pdf", "http://172.16.0.5/x.pdf",
        ):
            with self.subTest(url=url):
                self.assertIsNone(papers.fulltext(self.ctx(), record(oa_url=url)))
                last = self.attempts()[-1]
                self.assertEqual(last["outcome"], "rejected", last)
                self.assertRegex(last["failure_reason"], r"(?i)private or local")
        self.assertEqual([r for r in self.server.requests if not r[0].startswith(("/openalex", "/europepmc"))], [])

    def test_the_hosts_the_user_configured_stay_reachable(self) -> None:
        path = papers.fulltext(self.ctx(), record(oa_url=self.url + "/files/sample.pdf"))
        self.assertIsNotNone(path)

    def test_a_redirect_to_another_scheme_or_a_private_host_is_not_followed(self) -> None:
        for route in ("/redirect/ftp", "/redirect/private"):
            with self.subTest(route=route):
                self.assertIsNone(papers.fulltext(self.ctx(), record(oa_url=self.url + route)))
                last = self.attempts()[-1]
                self.assertEqual(last["outcome"], "rejected", last)
                self.assertRegex(last["failure_reason"], r"(?i)redirect")
        # a refusal is final: the same redirect is not retried
        self.assertEqual(len([r for r in self.server.requests if r[0] == "/redirect/ftp"]), 1)

    def test_an_ordinary_redirect_is_followed(self) -> None:
        self.assertIsNotNone(papers.fulltext(self.ctx(), record(oa_url=self.url + "/redirect/ok")))


class TestFetchLibKeepsItsOldDefault(Base):
    """A user's own ``fetch_data.py`` may legitimately read an intranet host: the guard is opt-in for ``fetch`` itself."""

    def test_private_hosts_are_allowed_by_default_and_refused_on_request(self) -> None:
        appendix = Path(self.tmp.name) / "fetch-app"
        url = self.url + "/files/sample.pdf"
        self.assertIsNotNone(fetch_lib.fetch("t", "s", url, "a.pdf", appendix))
        self.assertIsNone(fetch_lib.fetch("t", "s", url, "b.pdf", appendix, allow_private=False))
        self.assertIn("private or local", read_csv(appendix / "data_attempts.csv")[-1]["failure_reason"])
        self.assertIsNotNone(fetch_lib.fetch("t", "s", url, "c.pdf", appendix, allow_private=False, allowed_hosts=("127.0.0.1",)))


class TestCommandsDoNotLoseEachOthersRows(Base):
    def test_two_searches_at_once_both_keep_their_query_and_their_works(self) -> None:
        real = papers.next_query_id

        def slow(appendix: Path) -> str:  # widen the window in which two commands would read the same last id
            qid = real(appendix)
            time.sleep(0.05)
            return qid

        errors: list[BaseException] = []

        def run(provider: str, query: str) -> None:
            try:
                papers.search(self.ctx(), provider, query)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        with mock.patch.object(papers, "next_query_id", slow):
            threads = [threading.Thread(target=run, args=args) for args in (("openalex", "a"), ("europepmc", "b"), ("arxiv", "c"))]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(errors, [])
        log = read_csv(self.appendix / "search_log.csv")
        self.assertEqual(sorted(r["query_id"] for r in log), ["Q1", "Q2", "Q3"])
        self.assertEqual({r["provider"] for r in log}, {"openalex", "europepmc", "arxiv"})
        dois = {r["doi"] for r in read_csv(self.appendix / "papers.csv")}
        self.assertIn(REAL, dois)
        self.assertIn("arxiv:2503.13002", dois)
        self.assertEqual(papers.replay(self.ctx()), [])

    def test_parallel_requests_for_the_same_url_get_different_cache_files(self) -> None:
        real = base.Context.download

        def slow(self_: base.Context, *a, **kw):  # type: ignore[no-untyped-def]
            time.sleep(0.05)
            return real(self_, *a, **kw)

        def run() -> None:
            self.ctx().get("openalex", self.url + "/openalex/works?search=x")

        with mock.patch.object(base.Context, "download", slow):
            threads = [threading.Thread(target=run) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        files = sorted(p.name for p in (self.appendix / "data" / "papers" / "raw").glob("openalex-*"))
        self.assertEqual(len(files), 5, files)
        self.assertTrue(all((self.appendix / "data" / "papers" / "raw" / f).stat().st_size > 0 for f in files))

    def test_a_failed_request_leaves_no_empty_cache_file(self) -> None:
        self.server.fail_next("/openalex", 500, times=10)
        with self.assertRaises(base.ProviderUnavailable):
            self.ctx().get("openalex", self.url + "/openalex/works?search=x")
        raw = self.appendix / "data" / "papers" / "raw"
        self.assertEqual(list(raw.glob("*")) if raw.exists() else [], [])

    def test_two_citations_at_once_get_different_claim_ids(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        (self.appendix / "sources.csv").write_text("claim_id,source_title,url,tier,accessed_date,data_as_of,kind,sha256,selection,retrieved_utc\n", encoding="utf-8")
        real = papers._next_claim_id

        def slow(rows: list[dict[str, str]]) -> str:
            cid = real(rows)
            time.sleep(0.05)
            return cid

        errors: list[BaseException] = []

        def run(doi: str) -> None:
            try:
                papers.cite(self.ctx(), doi, tier="Tier 2")
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        with mock.patch.object(papers, "_next_claim_id", slow):
            dois = [r["doi"] for r in read_csv(self.appendix / "papers.csv") if r["abstract_sha256"] and r["work_type"] == "article" and r["is_retracted"] != "true"][:3]
            threads = [threading.Thread(target=run, args=(d,)) for d in dois]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(errors, [])
        ids = [r["claim_id"] for r in read_csv(self.appendix / "sources.csv")]
        self.assertEqual(len(ids), len(set(ids)), ids)
        self.assertEqual(len(ids), len(dois))


class TestLockFile(unittest.TestCase):
    def test_the_lock_is_reentrant_and_removed_on_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            appendix = Path(tmp) / "appendix"
            with papers._locked(appendix):
                with papers._locked(appendix):
                    self.assertTrue((appendix / ".papers.lock").exists())
                self.assertTrue((appendix / ".papers.lock").exists())
            self.assertFalse((appendix / ".papers.lock").exists())

    def test_a_lock_left_by_a_crashed_command_is_taken_over_but_a_fresh_one_is_respected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            appendix = Path(tmp) / "appendix"
            appendix.mkdir()
            lock = appendix / ".papers.lock"
            lock.write_text("12345", encoding="utf-8")
            with self.assertRaises(base.ProviderUnavailable) as cm:
                with papers._locked(appendix, timeout=0.2):
                    self.fail("a fresh lock must be respected")
            self.assertIn("another papers.py command", str(cm.exception))
            old = time.time() - 3600
            os.utime(lock, (old, old))
            with papers._locked(appendix, timeout=0.2):
                pass
            self.assertFalse(lock.exists())


class TestAtomicWrite(unittest.TestCase):
    def test_a_registry_that_another_program_holds_open_gets_an_actionable_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "papers.csv"
            with mock.patch.object(papers.os, "replace", side_effect=PermissionError("sharing violation")):
                with self.assertRaises(PermissionError) as cm:
                    papers._write_atomic(path, ("doi",), [{"doi": "10.1/x"}])
            self.assertIn("open in another program", str(cm.exception))
            self.assertEqual([p.name for p in Path(tmp).iterdir()], [])  # no temporary file left behind

    def test_the_temporary_name_is_unique_so_two_writers_never_share_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seen: list[str] = []
            real = papers.os.replace

            def spy(src: str, dst: str) -> None:
                seen.append(Path(src).name)
                real(src, dst)

            with mock.patch.object(papers.os, "replace", spy):
                papers._write_atomic(Path(tmp) / "papers.csv", ("doi",), [{"doi": "a"}])
                papers._write_atomic(Path(tmp) / "papers.csv", ("doi",), [{"doi": "b"}])
            self.assertEqual(len(set(seen)), 2, seen)


class TestCliNeverTracebacks(Base):
    def test_an_appendix_path_that_cannot_be_written_is_an_error_line(self) -> None:
        blocked = Path(self.tmp.name) / "not-a-folder"
        blocked.write_text("a file where the appendix should be", encoding="utf-8")
        env = {**os.environ, **self.env, "HEURISMA_BACKOFF": "0"}
        r = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "papers.py"), "search", "--provider", "openalex", "--query", "x", "--appendix", str(blocked)],
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertRegex(r.stderr, r"(?m)^Error: ")


if __name__ == "__main__":
    unittest.main()
