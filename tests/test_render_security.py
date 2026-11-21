"""v0.7.0 Phase 4 (P1-3): renderer link/table/image handling that the audit reproduced as broken or unsafe."""

import re
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import render_report  # noqa: E402
import validate_report  # noqa: E402


def render(md: str, **kw) -> str:
    return render_report.render_html("# T\n\n" + md + "\n", lang="en", **kw)


def body(html: str) -> str:
    return html.split("<main>", 1)[1].split("</main>", 1)[0]


class TestLinks(unittest.TestCase):
    def test_url_with_balanced_parentheses_is_not_truncated(self) -> None:
        out = body(render("[b](https://en.wikipedia.org/wiki/Bootstrap_(statistics)) next"))
        self.assertIn('<a href="https://en.wikipedia.org/wiki/Bootstrap_(statistics)">b</a> next', out)

    def test_doi_with_parentheses(self) -> None:
        out = body(render("[d](https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8<873::AID-SIM779>3.0.CO;2-I)"))
        self.assertIn('href="https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8&lt;873::AID-SIM779&gt;3.0.CO;2-I"', out)

    def test_angle_bracket_autolink(self) -> None:
        out = body(render("see <https://example.org/a_(b)> now"))
        self.assertIn('<a href="https://example.org/a_(b)">https://example.org/a_(b)</a>', out)

    def test_ampersands_in_urls_are_escaped_once(self) -> None:
        out = body(render("[q](https://example.org/?a=1&b=2)"))
        self.assertIn('href="https://example.org/?a=1&amp;b=2"', out)

    def test_dangerous_schemes_are_shown_as_text_only(self) -> None:
        for url in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html;base64,PHNjcmlwdD4=", "vbscript:x",
                    " javascript:alert(1)", "//evil.example/x"):
            out = body(render(f"[click me]({url}) end"))
            self.assertNotIn("href", out, msg=url)
            self.assertIn("click me", out, msg=url)

    def test_safe_schemes_and_relative_links_survive(self) -> None:
        for url in ("https://example.org/x", "http://example.org/x", "mailto:a@b.org", "#sec", "appendix/data/x.csv", "../a.md"):
            out = body(render(f"[ok]({url})"))
            self.assertIn(f'href="{url}"', out, msg=url)

    def test_citations_and_tags_still_work_next_to_links(self) -> None:
        out = body(render("[s](https://example.org/a_(b)) `[Moderate]` and 1e-5."))
        self.assertIn("ep-tag", out)
        self.assertIn("10<sup>", out)


class TestImages(unittest.TestCase):
    def test_markdown_image_becomes_img(self) -> None:
        out = body(render("![Figure alt](fig.png)"))
        self.assertIn('<img src="fig.png" alt="Figure alt"', out)
        self.assertNotIn("!<a", out)

    def test_unsafe_image_source_falls_back_to_alt_text(self) -> None:
        out = body(render("![alt text](javascript:alert(1))"))
        self.assertNotIn("<img", out)
        self.assertIn("alt text", out)


class TestTables(unittest.TestCase):
    def test_escaped_pipe_stays_inside_its_cell(self) -> None:
        out = body(render("| A | B |\n| :- | :- |\n| a \\| b | 2 |\n"))
        row = re.search(r"<tbody>\s*<tr>(.*?)</tr>", out, re.DOTALL).group(1)
        self.assertEqual(len(re.findall(r"<td", row)), 2, row)
        self.assertIn("a | b", row)

    def test_validator_splits_rows_the_same_way(self) -> None:
        cells = validate_report._split_md_table_row("| a \\| b | 2 | `x` |")
        self.assertEqual(cells, ["a | b", "2", "`x`"])


class TestFencedBlocks(unittest.TestCase):
    def test_num_marker_is_not_substituted_inside_fenced_code(self) -> None:
        md = "Value {{num:k}}.\n\n```\nwrite {{num:k}} in the report\n```\n"
        out = body(render(md, numbers={"k": "42"}))
        self.assertIn("Value 42.", out)
        self.assertIn("write {{num:k}} in the report", out)

    def test_validator_accepts_the_documented_marker_inside_code(self) -> None:
        import tempfile

        md = "Value {{num:k}}.\n\n```\nwrite {{num:k}} in the report\n```\n"
        with tempfile.TemporaryDirectory() as t:
            h = Path(t) / "r.html"
            h.write_text(render(md, numbers={"k": "42"}), encoding="utf-8")
            errs, _ = validate_report.validate_html_full(h)
            self.assertFalse([e for e in errs if "unresolved marker" in e], errs)


if __name__ == "__main__":
    unittest.main()
