"""v0.10.0 Phase 3: the opt-in validator rules for the paper connector (they act only when appendix/papers.csv exists)."""

from __future__ import annotations

import csv
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import papers_server  # noqa: E402
from test_papers_core import REAL, Base  # noqa: E402
import validate_report  # noqa: E402

import papers  # noqa: E402


def has(msgs: list[str], pattern: str) -> bool:
    return any(re.search(pattern, m, re.IGNORECASE) for m in msgs)


def run(ws: Path, level: int = 2) -> tuple[list[str], list[str]]:
    M.restamp_gates(ws)
    return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)


def papers_msgs(ws: Path, level: int = 2) -> tuple[list[str], list[str]]:
    e, w = run(ws, level)
    keep = lambda ms: [m for m in ms if "papers.csv" in m or "credential" in m or "connector" in m]  # noqa: E731
    return keep(e), keep(w)


class TestOptIn(unittest.TestCase):
    def test_without_papers_csv_the_connector_rules_say_nothing(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M._add_selection_columns(ws)
            M._cite_literature(ws, "10.9999/typed.from.memory.1", "A paper cited from memory", "Tier 1")
            e, w = papers_msgs(ws)
            self.assertEqual(e + w, [])
        finally:
            tmp.cleanup()

    def test_credentials_are_scanned_only_when_the_connector_is_in_use(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            (ws / "appendix" / "notes.txt").write_text("see https://x.org?api_key=abc123def456\n", encoding="utf-8")
            e, w = papers_msgs(ws)
            self.assertFalse(has(e + w, r"credential"), (e, w))
        finally:
            tmp.cleanup()


class TestRules(unittest.TestCase):
    def check(self, mutation, level: int = 2) -> tuple[list[str], list[str]]:
        tmp, ws = M.fresh_workspace()
        try:
            mutation(ws)
            return papers_msgs(ws, level)
        finally:
            tmp.cleanup()

    def test_a_clean_hand_built_registry_with_its_cache_is_silent(self) -> None:
        def clean(ws: Path) -> None:
            M._papers_workspace(ws)

        e, w = self.check(clean)
        self.assertEqual(e + w, [])

    def test_doi_typed_from_memory_warns_l2_errors_l3_with_code(self) -> None:
        e2, w2 = self.check(M.m40_typed_doi_not_in_papers_csv)
        hit = [m for m in w2 if "not in appendix/papers.csv" in m]
        self.assertTrue(hit and "10.9999/typed.from.memory.1" in hit[0], (e2, w2))
        self.assertEqual(validate_report.classify_message(hit[0]), ("P3-PAPER", "appendix/papers.csv"))
        e3, _ = self.check(M.m40_typed_doi_not_in_papers_csv, level=3)
        self.assertTrue(has(e3, r"not in appendix/papers\.csv"), e3)

    def test_preprint_or_report_cannot_be_tier_1(self) -> None:
        e, _ = self.check(M.m41_preprint_declared_tier1)
        hit = [m for m in e if re.search(r"preprint.*Tier 1", m)]
        self.assertTrue(hit, e)
        self.assertEqual(validate_report.classify_message(hit[0])[0], "P3-PAPER")

        def report_tier1(ws: Path) -> None:
            M._papers_workspace(ws, [M._paper("10.9999/fake.report.1", "A synthetic working paper", work_type="report")])
            M._cite_literature(ws, "10.9999/fake.report.1", "A synthetic working paper", "Tier 1")

        e, _ = self.check(report_tier1)
        self.assertTrue(has(e, r"report.*Tier 1"), e)

    def test_preprint_at_tier_2_is_fine(self) -> None:
        def ok(ws: Path) -> None:
            M._papers_workspace(ws, [M._paper("10.9999/fake.preprint.1", "A synthetic preprint about fixtures", work_type="preprint")])
            M._cite_literature(ws, "10.9999/fake.preprint.1", "A synthetic preprint about fixtures (preprint)", "Tier 2")

        e, w = self.check(ok)
        self.assertEqual(e + w, [])

    def test_retracted_work_is_an_error_when_cited_and_a_warning_when_only_registered(self) -> None:
        e, _ = self.check(M.m42_retracted_work_cited)
        self.assertTrue(has(e, r"retracted.*cites it"), e)

        def registered_only(ws: Path) -> None:
            M._papers_workspace(ws, [M._paper("10.9999/fake.retracted.1", "A synthetic retracted article", is_retracted="true")])

            def fn(rows: list[dict[str, str]], cols: list[str]):
                rows.append({"claim_id": "C5", "source_title": "A synthetic retracted article", "url": "https://doi.org/10.9999/fake.retracted.1", "tier": "Tier 2",
                             "kind": "literature", "selection": "agent-fetched", "retrieved_utc": "2026-11-20T12:00:00Z"})
                return rows, cols

            M._rewrite_csv(ws, "appendix/sources.csv", fn)

        e, w = self.check(registered_only)
        self.assertFalse(has(e, r"retracted"), e)
        self.assertTrue(has(w, r"retracted"), w)

    def test_a_changed_title_warns(self) -> None:
        _, w = self.check(M.m44_title_differs_from_papers_csv)
        hit = [m for m in w if "title in sources.csv" in m]
        self.assertTrue(hit, w)
        self.assertEqual(validate_report.classify_message(hit[0])[0], "P3-PAPER")

    def test_an_imported_record_cannot_vouch_for_tier_1(self) -> None:
        _, w = self.check(M.m46_imported_record_carries_tier1)
        self.assertTrue(has(w, r"imported.*attested"), w)
        e3, _ = self.check(M.m46_imported_record_carries_tier1, level=3)
        self.assertTrue(has(e3, r"imported.*attested"), e3)

    def test_a_hand_edited_registry_is_caught_by_replaying_the_cache(self) -> None:
        _, w = self.check(M.m47_papers_csv_edited_by_hand)
        hit = [m for m in w if "differs from every cached response" in m]
        self.assertTrue(hit and hit[0].startswith("appendix/papers.csv: "), w)
        self.assertEqual(validate_report.classify_message(hit[0])[0], "P3-PAPER")

    def test_a_fabricated_row_with_no_cache_at_all_is_caught_too(self) -> None:
        def fabricate(ws: Path) -> None:
            M._papers_workspace(ws)
            with (ws / "appendix" / "papers.csv").open("a", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(M.PAPER_COLS))
                w.writerow(M._paper("10.9999/made.up", "An invented paper"))

        _, w = self.check(fabricate)
        self.assertTrue(has(w, r"10\.9999/made\.up.*no cached response"), w)

    def test_a_credential_in_the_appendix_is_an_error_with_its_own_code(self) -> None:
        e, _ = self.check(M.m45_credentials_left_in_appendix)
        hit = [m for m in e if "credential" in m]
        self.assertTrue(hit and "search_log.csv" in hit[0], e)
        self.assertEqual(validate_report.classify_message(hit[0]), ("PRIV-CRED", "appendix/"))

    def test_redacted_and_placeholder_values_are_not_credentials(self) -> None:
        def redacted(ws: Path) -> None:
            M._papers_workspace(ws, search_rows=[{
                "query_id": "Q1", "provider": "openalex", "query": "x", "filters": "", "n_hits": "1", "retrieved_utc": "2026-11-20T12:00:00Z",
                "raw_file": "https://api.openalex.org/works?api_key=REDACTED&mailto=REDACTED&note=api_key=YOUR_KEY",
            }])

        e, w = self.check(redacted)
        self.assertFalse(has(e + w, r"credential"), (e, w))

    def test_a_missing_or_changed_full_text_is_an_error(self) -> None:
        e, _ = self.check(M.m43_fulltext_edited_after_registration)
        self.assertTrue(has(e, r"appendix/papers\.csv: .*changed since it was recorded"), e)

        def missing(ws: Path) -> None:
            M._papers_workspace(ws, [M._paper("10.9999/fake.fulltext.2", "Another", fulltext_file="appendix/data/papers/gone.pdf", fulltext_sha256="a" * 64)])

        e, _ = self.check(missing)
        self.assertTrue(has(e, r"full text .* is recorded but the file is missing"), e)


class TestPositiveControl(Base):
    """A registry the connector itself built (against the local server) passes the validator with nothing to say."""

    def test_connector_built_registry_is_silent(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M._add_selection_columns(ws)
            ctx = self.ctx()
            ctx.appendix = ws / "appendix"
            papers.search(ctx, "openalex", "hybrid work attrition")
            papers.lookup(ctx, REAL)
            row = papers.cite(ctx, REAL, tier="Tier 1")
            self.assertEqual(row["claim_id"], "C2")  # the example already cites this DOI: cite is idempotent by URL
            e, w = papers_msgs(ws)
            self.assertEqual(e + w, [])
            e3, _ = papers_msgs(ws, 3)
            self.assertEqual([m for m in e3 if "papers.csv" in m], [])
        finally:
            tmp.cleanup()

    def test_a_connector_built_registry_edited_by_hand_is_caught(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            ctx = self.ctx()
            ctx.appendix = ws / "appendix"
            papers.search(ctx, "openalex", "x")
            rows = papers.read_papers(ws / "appendix")
            for r in rows:
                if r["doi"] == "10.9999/fake.preprint.1":
                    r["work_type"] = "article"  # quietly upgrade a preprint so it could be Tier 1
            papers._write_atomic(ws / "appendix" / "papers.csv", M.PAPER_COLS, rows)
            _, w = papers_msgs(ws)
            self.assertTrue(has(w, r"work_type is 'article' but the cached responses give 'preprint'"), w)
        finally:
            tmp.cleanup()


class TestCodesDocumented(unittest.TestCase):
    def test_new_codes_exist_in_the_reference(self) -> None:
        doc = (Path(M.ROOT) / "skills" / "heurisma" / "references" / "validator-codes.md").read_text(encoding="utf-8")
        for code in ("P3-PAPER", "PRIV-CRED"):
            self.assertIn(f"`{code}`", doc)


_ = papers_server  # the local server module is imported for Base's fixtures

if __name__ == "__main__":
    unittest.main()
