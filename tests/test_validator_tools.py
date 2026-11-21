"""v0.7.0 Phase 5: table-only studies (P1-6), --version, --json with stable codes, domain/tier heuristic."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402

SCRIPTS = M.SCRIPTS


def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-B", *map(str, args)], capture_output=True, text=True, encoding="utf-8", cwd=cwd)


def msgs_after(fn, render=True, level=2):
    tmp, ws = M.fresh_workspace()
    try:
        fn(ws)
        if render:
            M.rerender(ws)
        return M.detect(ws, level=level)
    finally:
        tmp.cleanup()


class TestTableOnlyStudy(unittest.TestCase):
    def _table_only(self, ws: Path) -> None:
        (ws / "charts.json").unlink()
        text = (ws / "report.md").read_text(encoding="utf-8")
        text = re.sub(r"^\{\{fig:[a-z_]+\}\}\n?", "", text, flags=re.MULTILINE)
        (ws / "report.md").write_text(text, encoding="utf-8")
        (ws / "charts.json").write_text("[]", encoding="utf-8")
        (ws / "charts.json").unlink()

    def test_level2_without_charts_or_fig_markers_passes(self) -> None:
        msgs = msgs_after(self._table_only, render=False)
        self.assertFalse([m for m in msgs if "charts.json" in m], msgs)

    def test_fig_marker_without_charts_json_is_still_an_error(self) -> None:
        def marker_only(ws: Path) -> None:
            (ws / "charts.json").unlink()

        msgs = msgs_after(marker_only, render=False)
        self.assertTrue(any("charts.json not found" in m for m in msgs), msgs)


class TestVersion(unittest.TestCase):
    def test_every_script_exposes_the_same_version(self) -> None:
        import local_data
        import render_report
        import svg_charts

        versions = {m.__name__: getattr(m, "__version__", None) for m in (validate_report, local_data, render_report, svg_charts)}
        self.assertEqual(len(set(versions.values())), 1, versions)
        self.assertRegex(next(iter(versions.values())), r"^\d+\.\d+\.\d+$")

    def test_version_flag(self) -> None:
        for script in ("validate_report.py", "render_report.py", "local_data.py"):
            res = run(SCRIPTS / script, "--version")
            self.assertEqual(res.returncode, 0, (script, res.stderr))
            self.assertIn(validate_report.__version__, res.stdout)

    def test_renderer_version_is_part_of_the_freshness_hash(self) -> None:
        import render_report

        old = render_report.__version__
        try:
            before = render_report.compute_source_hash(M.GOLDEN / "report.md", M.GOLDEN / "charts.json", None, M.GOLDEN / "appendix")
            render_report.__version__ = "9.9.9"
            after = render_report.compute_source_hash(M.GOLDEN / "report.md", M.GOLDEN / "charts.json", None, M.GOLDEN / "appendix")
        finally:
            render_report.__version__ = old
        self.assertNotEqual(before, after)


class TestJsonOutput(unittest.TestCase):
    def test_json_for_a_passing_report(self) -> None:
        res = run(SCRIPTS / "validate_report.py", M.GOLDEN / "report.md", "--level", "2", "--html", M.GOLDEN / "report.html", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertTrue(data["passed"])
        self.assertEqual(data["errors"], [])
        self.assertEqual(data["version"], validate_report.__version__)

    def test_json_items_carry_stable_codes_and_files(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m01_data_value_changed(ws)
            M.m17_unresolved_num_marker(ws)
            M.rerender(ws)
            res = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--json")
            self.assertEqual(res.returncode, 1)
            data = json.loads(res.stdout)
            self.assertFalse(data["passed"])
            by_code = {i["code"]: i for i in data["errors"]}
            self.assertIn("P0-SHA", by_code)
            self.assertIn("W2-NUM", by_code)
            for item in data["errors"] + data["warnings"]:
                self.assertEqual(set(item), {"severity", "code", "file", "line", "message"})
                self.assertRegex(item["code"], r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")
            self.assertEqual(by_code["P0-SHA"]["file"], "appendix/sources.csv")
            self.assertEqual(by_code["P0-SHA"]["severity"], "error")
        finally:
            tmp.cleanup()

    def test_strict_json_promotes_warnings_to_failure(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m09_unregistered_substring_file(ws)
            M.rerender(ws)
            ok = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--json")
            strict = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--json", "--strict")
            self.assertEqual(ok.returncode, 0)
            self.assertEqual(strict.returncode, 1)
            self.assertEqual(json.loads(strict.stdout)["warnings"][0]["code"], "P1-ORPHAN")
        finally:
            tmp.cleanup()

    def test_every_code_is_documented_and_every_documented_code_exists(self) -> None:
        doc = (M.ROOT / "skills" / "heurisma" / "references" / "validator-codes.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"^\| `([A-Z0-9]+(?:-[A-Z0-9]+)*)` \|", doc, re.MULTILINE))
        in_code = {code for _, code, _ in validate_report.CODE_RULES} | {"GEN"}
        self.assertEqual(documented, in_code)

    def test_all_golden_mutation_messages_get_a_specific_code(self) -> None:
        for name in M.MUTATIONS:
            msgs = M.run_mutation(name)
            for m in msgs:
                code, _ = validate_report.classify_message(m)
                if M.caught(name, [m]):
                    self.assertNotEqual(code, "GEN", f"{name}: {m[:80]}")


class TestDomainTierHeuristic(unittest.TestCase):
    def _with_row(self, row: str):
        def fn(ws: Path) -> None:
            p = ws / "appendix" / "sources.csv"
            p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\n" + row + "\n", encoding="utf-8")
            M._edit(ws, "report.md", "[@C4]", "[@C4; @C5]")

        return fn

    def test_tier1_declared_on_a_newspaper_domain_warns(self) -> None:
        msgs = msgs_after(self._with_row('C5,"Opinion piece on hybrid work",https://www.nytimes.com/2026/x.html,Tier 1,2026-11-20,2026-11,literature'))
        self.assertTrue(any(re.search(r"C5.*Tier 1.*nytimes\.com.*press/blog", m) for m in msgs), msgs)

    def test_press_kind_declared_tier2_warns(self) -> None:
        msgs = msgs_after(self._with_row('C5,"Market note",https://example.org/n,Tier 2,2026-11-20,2026-11,press'))
        self.assertTrue(any(re.search(r"C5.*kind=press.*Tier 2", m) for m in msgs), msgs)

    def test_official_domain_with_tier1_is_fine(self) -> None:
        msgs = msgs_after(self._with_row('C5,"Statistics agency series",https://www.bls.gov/x,Tier 1,2026-11-20,2026-11,data'))
        self.assertFalse(any("C5" in m and "domain" in m.lower() for m in msgs), msgs)

    def test_conservative_tier3_on_an_official_domain_is_not_flagged(self) -> None:
        msgs = msgs_after(self._with_row('C5,"Statistics agency series",https://www.bls.gov/x,Tier 3,2026-11-20,2026-11,data'))
        self.assertFalse(any("C5" in m and "domain" in m.lower() for m in msgs), msgs)


if __name__ == "__main__":
    unittest.main()
