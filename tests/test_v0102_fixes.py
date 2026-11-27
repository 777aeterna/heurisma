"""v0.10.2: the four defects reported by the Level 3 field run."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
from test_papers_core import REAL, Base, read_csv  # noqa: E402
import validate_report  # noqa: E402

import papers  # noqa: E402
from checks import numeric, prereg  # noqa: E402
from contracts import PAPER_COLS  # noqa: E402

HEADER = "claim_id,source_title,url,tier,accessed_date,data_as_of,kind,sha256,selection,retrieved_utc\n"


class TestFulltextBeforeAbstract(Base):
    """Bug 1 and Bug 2: an open-access work whose record has no abstract is cited through its full text, and the row keeps its hash."""

    def prepare(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        rows = read_csv(self.appendix / "papers.csv")
        for r in rows:
            if r["doi"] == REAL:
                r.update(abstract_sha256="", is_oa="true", oa_url=self.url + "/files/sample.pdf")
        papers._write_atomic(self.appendix / "papers.csv", PAPER_COLS, rows)
        (self.appendix / "sources.csv").write_text(HEADER, encoding="utf-8")

    def test_fulltext_cite_succeeds_for_an_open_access_work_without_abstract(self) -> None:
        self.prepare()
        row = papers.cite(self.ctx(), REAL, tier="Tier 1", fulltext=True)
        self.assertNotIn("(abstract only)", row["source_title"])

    def test_without_fulltext_a_work_with_no_abstract_is_still_refused(self) -> None:
        self.prepare()
        with self.assertRaises(papers.CiteError) as cm:
            papers.cite(self.ctx(), REAL, tier="Tier 2")
        self.assertIn("--fulltext", str(cm.exception))

    def test_cite_writes_the_fulltext_sha256_into_sources_csv(self) -> None:
        self.prepare()
        papers.cite(self.ctx(), REAL, tier="Tier 1", fulltext=True)
        registered = next(r for r in read_csv(self.appendix / "papers.csv") if r["doi"] == REAL)["fulltext_sha256"]
        self.assertTrue(registered)
        self.assertEqual(read_csv(self.appendix / "sources.csv")[0]["sha256"], registered)


class TestProvenanceReadsTheConnectorRegistry(unittest.TestCase):
    def test_a_tier1_doi_whose_fulltext_is_in_papers_csv_is_not_called_undownloaded(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            doi, title = "10.9999/fake.fulltext.5", "A synthetic article whose PDF came from a preprint server"
            target = ws / "appendix" / "data" / "papers" / "a-12345678.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"%PDF-1.4 fixture")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            (ws / "appendix" / "download_log.csv").write_text(
                f"file,url,retrieved_utc,bytes,sha256\npapers/{target.name},https://preprints.example.org/pdf/x,2026-11-20T12:00:00Z,16,{digest}\n",
                encoding="utf-8",
            )
            M._papers_workspace(ws, [M._paper(doi, title, fulltext_file=f"appendix/data/papers/{target.name}", fulltext_sha256=digest)])
            M._cite_literature(ws, doi, title, "Tier 1")
            M.restamp_gates(ws)
            _, warnings = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws)
            self.assertFalse([w for w in warnings if "'C5'" in w and "no downloaded primary document" in w], warnings)
        finally:
            tmp.cleanup()


class TestReviewerQuotesSurviveTheFixes(unittest.TestCase):
    """Bug 3: a reviewer quote of a report.md line the author then corrected must not break the closed review."""

    def run_case(self, closed: bool, quote_file: str = "report.md") -> list[str]:
        tmp, ws = M.fresh_workspace()
        try:
            gate = ws / "appendix" / "gates" / "reviewer.md"
            gate.write_text(
                "MODE: subagent\nREVIEWED-SHA256: 0\nREVIEWED-UTC: 2026-11-20T12:00:00Z\nANALYSIS-SHA256: 0\n"
                f'QUOTE: {quote_file}:6: "an over-calibrated sentence the author corrected afterwards"\n'
                'QUOTE: appendix/output.txt:1: "Dataset integrity"\n\n1. [1] The verdict is over-calibrated — fix the tag.\n',
                encoding="utf-8",
            )
            if closed:
                M._edit(ws, "report.md", "## 6. Claim-Evidence Matrix",
                        "### Reviewer #2 Disposition Table\n\n| # | Critique | Action |\n| :- | :- | :- |\n| 1 | over-calibrated verdict | Fixed |\n\n## 6. Claim-Evidence Matrix")
            M.restamp_gates(ws)
            e, w = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws)
            return [m for m in e + w if "reviewer.md quotes" in m]
        finally:
            tmp.cleanup()

    def test_a_corrected_report_line_is_accepted_once_the_disposition_is_closed(self) -> None:
        self.assertEqual(self.run_case(closed=True), [])

    def test_without_a_closed_disposition_the_quote_still_fails(self) -> None:
        self.assertTrue(self.run_case(closed=False))

    def test_a_quote_of_a_stable_file_must_still_match(self) -> None:
        self.assertTrue(self.run_case(closed=True, quote_file="appendix/run.json"))


class TestNumbersAreComparedByValue(unittest.TestCase):
    """Friction 4: formatting is not a different number; a different number still is."""

    def untraced(self, text: str, output: str) -> list[str]:
        raw, norm = numeric._closure_haystack(output, None)
        return numeric._untraced_in(text, raw, norm, set())

    def test_thousands_separators_and_trailing_zeros(self) -> None:
        output = "n_sites 1024\nexponent 2.0000\nshift -0.5\nr 0.513\n"
        self.assertEqual(self.untraced("| 1,024 | 2.00 | −0.50 |", output), [])

    def test_a_rounded_or_different_value_is_still_untraced(self) -> None:
        output = "n_sites 1024\nexponent 2.0000\nr 0.513\n"
        self.assertEqual(self.untraced("| 0.51 | 2.01 | 1,025 |", output), ["0.51", "2.01", "1,025"])

    def test_values_from_numbers_json_count_too(self) -> None:
        raw, norm = numeric._closure_haystack("", {"chi_max": 12.50, "n": 1024})
        self.assertEqual(numeric._untraced_in("| 12.5 | 1,024 |", raw, norm, set()), [])


class TestHypothesisWordingIgnoresNotation(unittest.TestCase):
    def test_ascii_and_unicode_notation_are_the_same_hypothesis(self) -> None:
        a = prereg._norm_hypothesis("chi_max grows as N->inf, with alpha <= 1 and beta >= 0")
        b = prereg._norm_hypothesis("χ_max grows as N→∞, with α ≤ 1 and β ≥ 0")
        self.assertEqual(a, b)

    def test_a_real_change_of_wording_still_differs(self) -> None:
        self.assertNotEqual(prereg._norm_hypothesis("chi_max grows as N->inf"), prereg._norm_hypothesis("chi_max shrinks as N->inf"))

    def test_words_that_contain_a_greek_name_are_left_alone(self) -> None:
        self.assertIn("machine", prereg._norm_hypothesis("a machine learning baseline"))
        self.assertIn("alphabet", prereg._norm_hypothesis("the alphabet size"))


if __name__ == "__main__":
    unittest.main()
