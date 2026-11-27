"""Offline regression tests for the paper-connector fixes (no network, no subprocesses beyond a PID probe).

Covers: replay reconstruction for the N2 case and the PAP-1 published-``<arxiv:doi>`` case, ``_locked`` PID liveness,
``normalize_doi``/``scrub_url`` interplay, ``_data_as_of_after`` granularity, PAP-6 missing-raw detection, PAP-9
"not found vs. provider down", and M1 orphan-PDF detection.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "skills" / "heurisma" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import fetch_lib  # noqa: E402
import papers  # noqa: E402
from checks.papers import check_papers  # noqa: E402
from checks.provenance import _data_as_of_after  # noqa: E402
from providers import base  # noqa: E402

DATACITE_DOI = "10.48550/arxiv.2111.12210"
PUBLISHED_DOI = "10.1038/s41586-024-07500-2"
T = "2026-11-25T00:00:00Z"


def _openalex_payload() -> bytes:
    return json.dumps(
        {
            "id": "https://openalex.org/W1234567890",
            "doi": "https://doi.org/10.48550/arxiv.2111.12210",
            "title": "A Test Paper",
            "publication_year": 2021,
            "type": "article",
            "is_retracted": False,
            "open_access": {"is_oa": True, "oa_url": "https://arxiv.org/pdf/2111.12210.pdf"},
            "authorships": [{"author": {"display_name": "Alice Example"}}],
            "primary_location": {"source": {"display_name": "arXiv"}},
            "abstract_inverted_index": {"hello": [0], "world": [1]},
        }
    ).encode("utf-8")


def _arxiv_payload(published_doi: str | None = None) -> bytes:
    doi_el = f"<arxiv:doi>{published_doi}</arxiv:doi>" if published_doi else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">'
        "<entry>"
        "<id>http://arxiv.org/abs/2111.12210v1</id>"
        f"{doi_el}"
        "<published>2021-11-22T00:00:00Z</published>"
        "<title>A Test Paper</title>"
        "<author><name>Alice Example</name></author>"
        "<summary>hello world</summary>"
        '<link title="pdf" href="http://arxiv.org/pdf/2111.12210v1"/>'
        "</entry>"
        "</feed>"
    ).encode("utf-8")


def _dead_pid() -> int:
    """A PID that no live process owns (a forked child that already exited and was reaped)."""
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
    return pid


class ReplayTests(unittest.TestCase):
    def _build_appendix(self, base_dir: Path, published_doi: str | None) -> Path:
        """Write the synthetic cached responses, download_log.csv and the merged papers.csv row for one lookup."""
        appendix = base_dir / "report" / "appendix"
        raw_dir = appendix / "data" / "papers" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        oa_payload = _openalex_payload()
        ax_payload = _arxiv_payload(published_doi)
        oa_name, ax_name = "openalex-abc.json", "arxiv-def.xml"
        (raw_dir / oa_name).write_bytes(oa_payload)
        (raw_dir / ax_name).write_bytes(ax_payload)

        download_rows = [
            {
                "file": f"papers/raw/{oa_name}",
                "url": "https://api.openalex.org/works/doi:10.48550%2Farxiv.2111.12210",
                "retrieved_utc": T,
                "bytes": str(len(oa_payload)),
                "sha256": hashlib.sha256(oa_payload).hexdigest(),
            },
            {
                "file": f"papers/raw/{ax_name}",
                "url": "https://export.arxiv.org/api/query?id_list=2111.12210",
                "retrieved_utc": T,
                "bytes": str(len(ax_payload)),
                "sha256": hashlib.sha256(ax_payload).hexdigest(),
            },
        ]
        papers._write_atomic(appendix / "download_log.csv", fetch_lib.DOWNLOAD_COLS, download_rows)

        oa_rec = papers.PROVIDERS["openalex"].parse(oa_payload)[0]
        oa_rec["retrieved_utc"] = T
        ax_rec = papers.PROVIDERS["arxiv"].parse(ax_payload)[0]
        ax_rec["retrieved_utc"] = T
        row = papers.merge([oa_rec, {**ax_rec, "doi": DATACITE_DOI}])
        row["query_id"] = "lookup"
        papers._write_atomic(appendix / "papers.csv", papers.PAPER_COLS, [row])
        return appendix

    def test_replay_n2_arxiv_view_without_published_doi(self):
        with tempfile.TemporaryDirectory() as d:
            appendix = self._build_appendix(Path(d), published_doi=None)
            problems = papers.replay(papers.Context(appendix))
        self.assertEqual(problems, [], f"replay should fully explain the N2 row, got: {problems}")

    def test_replay_pap1_arxiv_view_with_published_doi(self):
        with tempfile.TemporaryDirectory() as d:
            appendix = self._build_appendix(Path(d), published_doi=PUBLISHED_DOI)
            problems = papers.replay(papers.Context(appendix))
        self.assertEqual(problems, [], f"replay should fully explain the PAP-1 row, got: {problems}")

    def test_replay_detects_missing_lookup_raw_from_download_log(self):
        with tempfile.TemporaryDirectory() as d:
            appendix = Path(d) / "report" / "appendix"
            (appendix / "data" / "papers" / "raw").mkdir(parents=True)
            papers._write_atomic(
                appendix / "download_log.csv",
                fetch_lib.DOWNLOAD_COLS,
                [
                    {
                        "file": "papers/raw/openalex-missing.json",
                        "url": "https://api.openalex.org/works/doi:10.1234/x",
                        "retrieved_utc": T,
                        "bytes": "10",
                        "sha256": "a" * 64,
                    }
                ],
            )
            problems = papers.replay(papers.Context(appendix))
        self.assertTrue(
            any("listed in download_log.csv is missing" in p for p in problems),
            f"expected a missing-raw message, got: {problems}",
        )


class LockTests(unittest.TestCase):
    def test_pid_alive(self):
        self.assertTrue(papers._pid_alive(os.getpid()))
        self.assertFalse(papers._pid_alive(0))
        self.assertFalse(papers._pid_alive(-1))

    @unittest.skipUnless(hasattr(os, "fork"), "requires fork()")
    def test_pid_alive_dead(self):
        dead = _dead_pid()
        self.assertFalse(papers._pid_alive(dead))

    def test_locked_does_not_steal_live_stale_lock(self):
        with tempfile.TemporaryDirectory() as d:
            appendix = Path(d) / "appendix"
            appendix.mkdir(parents=True)
            lock = appendix / papers.LOCK_NAME
            lock.write_text(str(os.getpid()), encoding="utf-8")
            old = time.time() - 1000
            os.utime(lock, (old, old))  # stale, but the recorded owner is alive
            with self.assertRaises(papers.ProviderUnavailable):
                with papers._locked(appendix, timeout=0.3, stale_after=1.0):
                    pass
            self.assertTrue(lock.exists(), "a live owner's lock must not be stolen")

    @unittest.skipUnless(hasattr(os, "fork"), "requires fork()")
    def test_locked_steals_dead_stale_lock(self):
        with tempfile.TemporaryDirectory() as d:
            appendix = Path(d) / "appendix"
            appendix.mkdir(parents=True)
            lock = appendix / papers.LOCK_NAME
            dead = _dead_pid()
            lock.write_text(str(dead), encoding="utf-8")
            old = time.time() - 1000
            os.utime(lock, (old, old))
            acquired = False
            with papers._locked(appendix, timeout=2.0, stale_after=1.0):
                acquired = True
            self.assertTrue(acquired, "a dead owner's stale lock should be taken over")
            self.assertFalse(lock.exists(), "the lock is released after the section ends")


class NormalizeScrubTests(unittest.TestCase):
    def test_normalize_doi_strips_query_and_fragment(self):
        self.assertEqual(base.normalize_doi("https://doi.org/10.1234/x?foo=bar"), "10.1234/x")
        self.assertEqual(base.normalize_doi("10.1234/x#section-1"), "10.1234/x")
        self.assertEqual(base.normalize_doi("10.48550/arxiv.2111.12210?download=1"), "10.48550/arxiv.2111.12210")

    def test_arxiv_id_from_doi_uses_normalized_doi(self):
        self.assertEqual(base.arxiv_id_from_doi("10.48550/arxiv.2111.12210?download=1"), "2111.12210")
        self.assertEqual(base.arxiv_id_from_doi("arxiv:2111.12210"), "2111.12210")

    def test_scrub_url_and_redact_userinfo(self):
        scrubbed = fetch_lib.scrub_url("https://user:pass@example.com/api?api_key=SECRET")
        self.assertNotIn("user", scrubbed)
        self.assertNotIn("pass", scrubbed)
        self.assertNotIn("SECRET", scrubbed)
        redacted = base.redact("https://user:pass@example.com/x?mailto=a@b.c")
        self.assertNotIn("user", redacted)
        self.assertNotIn("pass", redacted)
        self.assertNotIn("a@b.c", redacted)


class DataAsOfTests(unittest.TestCase):
    def test_month_day_granularity_not_always_later(self):
        self.assertFalse(_data_as_of_after("2026-11-20", "2026-11"))
        self.assertFalse(_data_as_of_after("2026-11", "2026-11-20"))
        self.assertTrue(_data_as_of_after("2026-12-20", "2026-11"))
        self.assertTrue(_data_as_of_after("2026-12", "2026-11-20"))
        self.assertTrue(_data_as_of_after("2027", "2026-11-20"))
        self.assertFalse(_data_as_of_after("2026", "2026-11-20"))
        self.assertTrue(_data_as_of_after("2026-11-21", "2026-11-20"))
        self.assertFalse(_data_as_of_after("not-a-date", "2026-11-20"))


class LookupNotFoundTests(unittest.TestCase):
    def test_not_found_beats_down_provider(self):
        with tempfile.TemporaryDirectory() as d:
            appendix = Path(d) / "appendix"
            appendix.mkdir(parents=True)
            ctx = papers.Context(appendix)

            def down(_ctx, _doi):
                raise papers.ProviderUnavailable("openalex is unavailable (HTTP 503)")

            def nf(_ctx, _doi):
                raise papers.NotFound("crossref: not found")

            with patch.object(papers.PROVIDERS["openalex"], "lookup", down), patch.object(
                papers.PROVIDERS["crossref"], "lookup", nf
            ):
                result = papers.lookup(ctx, "10.1234/example")

        self.assertIsNone(result)
        self.assertTrue(any("reported not found" in w for w in ctx.warnings), ctx.warnings)


class OrphanPdfTests(unittest.TestCase):
    def test_orphan_pdf_warning(self):
        with tempfile.TemporaryDirectory() as d:
            report_dir = Path(d) / "report"
            appendix = report_dir / "appendix"
            data_papers = appendix / "data" / "papers"
            data_papers.mkdir(parents=True)
            orphan = data_papers / "orphan.pdf"
            orphan.write_bytes(b"%PDF-1.4\norphan")
            sha = hashlib.sha256(orphan.read_bytes()).hexdigest()

            papers._write_atomic(appendix / "papers.csv", papers.PAPER_COLS, [])
            papers._write_atomic(
                appendix / "download_log.csv",
                fetch_lib.DOWNLOAD_COLS,
                [
                    {
                        "file": "papers/orphan.pdf",
                        "url": "https://example.org/orphan.pdf",
                        "retrieved_utc": T,
                        "bytes": str(orphan.stat().st_size),
                        "sha256": sha,
                    }
                ],
            )
            errors, warnings = check_papers(
                report_dir, sources_rows=[], cited_ids=set(), level=2, run_start=None
            )

        self.assertEqual(errors, [], f"unexpected errors: {errors}")
        self.assertTrue(any("orphaned full text" in w for w in warnings), warnings)




class PinnedConnectionAndSearchReplayTests(unittest.TestCase):
    def test_pinned_https_connection_default_port_and_request_port_parsing(self) -> None:
        import urllib.request
        self.assertEqual(fetch_lib._PinnedHTTPSConnection.default_port, 443)
        h = fetch_lib._PinnedHTTPSHandler("93.184.216.34")
        req = urllib.request.Request("https://example.com:8443/path")
        captured = {}

        def fake_do_open(make_conn, request):
            conn = make_conn("example.com", timeout=5)
            captured["port"] = conn.port
            captured["host"] = conn.host
            captured["pinned_host"] = conn._pinned_host
            return None

        with patch.object(h, "do_open", side_effect=fake_do_open):
            h.https_open(req)
        self.assertEqual(captured, {"port": 8443, "host": "93.184.216.34", "pinned_host": "example.com"})

    def test_replay_search_row_openalex_only_does_not_false_positive_with_separate_arxiv_search(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            appendix = Path(d) / "report" / "appendix"
            raw_dir = appendix / "data" / "papers" / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            oa_payload = _openalex_payload()
            ax_payload = _arxiv_payload(None)
            (raw_dir / "openalex-q1.json").write_bytes(oa_payload)
            (raw_dir / "arxiv-q2.xml").write_bytes(ax_payload)
            papers._write_atomic(
                appendix / "download_log.csv",
                fetch_lib.DOWNLOAD_COLS,
                [
                    {"file": "papers/raw/openalex-q1.json", "url": "https://api.openalex.org/works?search=x", "retrieved_utc": T, "bytes": str(len(oa_payload)), "sha256": hashlib.sha256(oa_payload).hexdigest()},
                    {"file": "papers/raw/arxiv-q2.xml", "url": "https://export.arxiv.org/api/query?search_query=x", "retrieved_utc": T, "bytes": str(len(ax_payload)), "sha256": hashlib.sha256(ax_payload).hexdigest()},
                ],
            )
            oa_rec = papers.PROVIDERS["openalex"].parse(oa_payload)[0]
            oa_rec["retrieved_utc"] = T
            oa_rec["query_id"] = "Q1"
            ax_rec = papers.PROVIDERS["arxiv"].parse(ax_payload)[0]
            ax_rec["retrieved_utc"] = T
            ax_rec["query_id"] = "Q2"
            papers._write_atomic(appendix / "papers.csv", papers.PAPER_COLS, [oa_rec, ax_rec])
            self.assertEqual(papers.replay(papers.Context(appendix)), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
