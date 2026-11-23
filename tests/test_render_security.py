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


class TestRemoteImages(unittest.TestCase):
    """An image copied from a web page into report.md must not make the finished HTML contact that server when it is opened."""

    def test_a_remote_image_is_a_link_not_an_embedded_resource(self) -> None:
        out = body(render("![Chart from a site](https://tracker.example/pixel.png?id=1)"))
        self.assertNotIn("<img", out)
        self.assertIn('<a href="https://tracker.example/pixel.png?id=1">Chart from a site</a>', out)

    def test_a_remote_image_without_alt_text_shows_its_address(self) -> None:
        out = body(render("![](https://tracker.example/p.png)"))
        self.assertNotIn("<img", out)
        self.assertIn('<a href="https://tracker.example/p.png">https://tracker.example/p.png</a>', out)

    def test_nothing_in_a_whole_document_loads_from_the_network(self) -> None:
        html_out = render("![a](https://x.example/a.png) ![b](http://x.example/b.png) ![c](//x.example/c.png) [link](https://x.example/)")
        self.assertNotRegex(html_out, r'(?:src|srcset|data)="(?:https?:)?//')
        self.assertNotRegex(html_out, r"url\(\s*['\"]?(?:https?:)?//")

    def test_relative_images_and_other_schemes(self) -> None:
        self.assertIn('<img src="appendix/fig.png" alt="ok"', body(render("![ok](appendix/fig.png)")))
        for src in ("mailto:a@example.org", "//evil.example/p.png", "data:image/png;base64,AAAA", "ftp://x.example/p.png"):
            self.assertNotIn("<img", body(render(f"![x]({src})")), src)


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


class TestEmbeddedGatesPublishNothingPrivateOrUnverified(unittest.TestCase):
    """v0.10.1: a gate file is embedded in report.html, so what the validator refuses in a gate must not reach the reader."""

    def render_gate(self, text: str) -> tuple[str, str]:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            gate = Path(tmp) / "appendix" / "gates" / "reviewer.md"
            gate.parent.mkdir(parents=True)
            gate.write_text(text, encoding="utf-8")
            out = render_report._render_appendices(Path(tmp) / "appendix", render_report.I18N["en"])
            return out, gate.read_text(encoding="utf-8")

    def test_home_directory_paths_are_redacted(self) -> None:
        for path in ("/home/alice/studies/x.csv", "/Users/bob/Desktop/y.csv", "C:\\Users\\carol\\z.csv"):
            out, _ = self.render_gate(f"QA ran on {path} today.\n")
            self.assertNotIn(path.split("/")[2] if "/" in path else "carol", out, path)
            self.assertIn("[path]", out, path)

    def test_unverified_claims_are_omitted_but_the_file_and_quote_lines_are_kept(self) -> None:
        text = (
            "QUOTE: report.md:3: \"UNVERIFIED: a quoted line stays as it is\"\n"
            "UNVERIFIED: 2. [4] the 2019 swap line was 4.2 — not in sources.csv — verify it\n"
            "1. [1] a verified critique stays\n"
            "3. [2] UNVERIFIED: a policy cap of 17 percent — mid-line prefix\n"
        )
        out, on_disk = self.render_gate(text)
        self.assertNotIn("4.2", out)
        self.assertNotIn("swap line", out)
        self.assertNotIn("17 percent", out)
        self.assertIn("[unverified claim omitted]", out)
        self.assertIn("a quoted line stays as it is", out)
        self.assertIn("a verified critique stays", out)
        self.assertEqual(on_disk, text)


class TestImagesNeverReachOutsideTheReport(unittest.TestCase):
    def test_absolute_and_parent_paths_are_not_embedded(self) -> None:
        for src in ("/etc/passwd", "../secret", "figures/../../secret.png", "/home/x/a.png"):
            self.assertNotIn("<img", body(render(f"![x]({src})")), src)
        self.assertIn('<img src="figures/a.png"', body(render("![y](figures/a.png)")))


if __name__ == "__main__":
    unittest.main()
