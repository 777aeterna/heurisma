"""v0.7.0 Phase 5: --reproduce re-runs the analysis and diffs its artifacts; --diff compares two runs."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402

SCRIPTS = M.SCRIPTS


def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-B", *map(str, args)], capture_output=True, text=True, encoding="utf-8", cwd=cwd)


class TestReproduce(unittest.TestCase):
    def test_golden_examples_reproduce(self) -> None:
        for d in ("showcase-hybrid-work", "level2-study"):
            res = run(SCRIPTS / "validate_report.py", M.ROOT / "examples" / d / "report.md", "--level", "2", "--reproduce")
            self.assertEqual(res.returncode, 0, (d, res.stderr))

    def test_edited_output_is_detected(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            out = ws / "appendix" / "output.txt"
            out.write_text(out.read_text(encoding="utf-8").replace("sites=16", "sites=17"), encoding="utf-8")
            M.rerender(ws)
            res = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--reproduce")
            self.assertEqual(res.returncode, 1)
            self.assertRegex(res.stderr, r"reproduce: appendix/output\.txt differs")
        finally:
            tmp.cleanup()

    def test_edited_numbers_and_charts_are_detected(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            n = ws / "appendix" / "numbers.json"
            data = json.loads(n.read_text(encoding="utf-8"))
            k = next(iter(data))
            data[k] = "999"
            n.write_text(json.dumps(data), encoding="utf-8")
            c = ws / "charts.json"
            c.write_text(c.read_text(encoding="utf-8").replace("PR Output", "PR Outcome"), encoding="utf-8")
            res = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--reproduce")
            self.assertEqual(res.returncode, 1)
            self.assertIn("numbers.json differs", res.stderr)
            self.assertIn("charts.json differs", res.stderr)
        finally:
            tmp.cleanup()

    def test_failing_analysis_is_reported_not_a_traceback(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            (ws / "appendix" / "analysis.py").write_text("raise SystemExit('boom')\n", encoding="utf-8")
            res = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--reproduce")
            self.assertEqual(res.returncode, 1)
            self.assertIn("reproduce: appendix/analysis.py failed", res.stderr)
            self.assertNotIn("Traceback", res.stderr)
        finally:
            tmp.cleanup()

    def test_original_files_are_never_modified(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            before = {p: p.read_bytes() for p in ws.rglob("*") if p.is_file()}
            run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--reproduce")
            after = {p: p.read_bytes() for p in ws.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
            self.assertEqual(before, after)
        finally:
            tmp.cleanup()

    def test_custom_command_and_missing_readme_command(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            (ws / "appendix" / "README.md").write_text("no commands here\n", encoding="utf-8")
            res = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--reproduce")
            self.assertEqual(res.returncode, 1)
            self.assertIn("no analysis.py command found", res.stderr)
            res = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--reproduce",
                      "--reproduce-cmd", "python3 -B appendix/analysis.py --charts-out charts.json --numbers-out appendix/numbers.json > appendix/output.txt")
            self.assertEqual(res.returncode, 0, res.stderr)
        finally:
            tmp.cleanup()

    def test_json_mode_reports_the_repro_code(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            (ws / "appendix" / "output.txt").write_text("tampered\n", encoding="utf-8")
            res = run(SCRIPTS / "validate_report.py", ws / "report.md", "--level", "2", "--reproduce", "--json")
            data = json.loads(res.stdout)
            self.assertIn("REPRO", {i["code"] for i in data["errors"]})
        finally:
            tmp.cleanup()


class TestDiff(unittest.TestCase):
    def test_diff_lists_data_numbers_and_verdict_changes(self) -> None:
        tmp, other = M.fresh_workspace()
        try:
            M.m01_data_value_changed(other)
            n = other / "appendix" / "numbers.json"
            data = json.loads(n.read_text(encoding="utf-8"))
            key = sorted(data)[0]
            old = data[key]
            data[key] = "7.77"
            data["brand_new"] = "1"
            del data[sorted(data)[1]]
            n.write_text(json.dumps(data), encoding="utf-8")
            (other / "appendix" / "data" / "extra.csv").write_text("a\n1\n", encoding="utf-8")
            M._edit(other, "report.md", "A six-month randomized trial", "A six-month randomised trial")
            res = run(SCRIPTS / "validate_report.py", M.GOLDEN / "report.md", "--diff", other)
            self.assertEqual(res.returncode, 0, res.stderr)
            out = res.stdout
            self.assertIn("data files", out)
            self.assertRegex(out, r"changed\s+hybrid_rct_sites\.csv")
            self.assertRegex(out, r"added\s+extra\.csv")
            self.assertIn(f"{key}: {old} -> 7.77", out)
            self.assertIn("brand_new", out)
            self.assertIn("verdict changed", out)
        finally:
            tmp.cleanup()

    def test_diff_of_identical_runs_says_so(self) -> None:
        res = run(SCRIPTS / "validate_report.py", M.GOLDEN / "report.md", "--diff", M.GOLDEN)
        self.assertEqual(res.returncode, 0)
        self.assertIn("no differences", res.stdout)

    def test_diff_with_a_missing_folder_is_an_error(self) -> None:
        res = run(SCRIPTS / "validate_report.py", M.GOLDEN / "report.md", "--diff", "/nonexistent/run")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Error", res.stderr)


if __name__ == "__main__":
    unittest.main()
