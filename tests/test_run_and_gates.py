"""v0.7.0 Phase 3: tool-stamped run start (P1-1) and gates bound to the artifact they reviewed (P0-2)."""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import local_data  # noqa: E402
import validate_report  # noqa: E402

SCRIPTS = M.SCRIPTS


def msgs_after(fn, render=True, level=2):
    tmp, ws = M.fresh_workspace()
    try:
        fn(ws)
        if render:
            M.rerender(ws)
        return M.detect(ws, level=level)
    finally:
        tmp.cleanup()


def any_match(msgs, pattern):
    return any(re.search(pattern, m) for m in msgs)


class TestRunStart(unittest.TestCase):
    def test_run_start_writes_iso_utc_once(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            first = local_data.run_start(Path(t) / "appendix")
            self.assertRegex(first["run_started_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            again = local_data.run_start(Path(t) / "appendix")
            self.assertEqual(first, again)
            data = json.loads((Path(t) / "appendix" / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(data["run_started_utc"], first["run_started_utc"])

    def test_run_start_cli(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            res = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "local_data.py"), "run-start", "--appendix", str(Path(t) / "appendix")],
                capture_output=True,
                text=True, encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue((Path(t) / "appendix" / "run.json").is_file())

    def test_failure_earlier_the_same_day_is_inherited(self) -> None:
        msgs = msgs_after(M.m08_same_day_inherited_attempt)
        self.assertTrue(any_match(msgs, r"inherited"), msgs)

    def test_failure_later_the_same_day_is_fresh(self) -> None:
        def later(ws: Path) -> None:
            (ws / "appendix" / "run.json").write_text(json.dumps({"run_started_utc": "2026-11-20T08:00:00Z"}), encoding="utf-8")

            def fn(rows, cols):
                for r in rows:
                    r["attempted_utc"] = "2026-11-20T09:30:00Z"
                return rows, cols

            M._rewrite_csv(ws, "appendix/data_attempts.csv", fn)

        msgs = msgs_after(later)
        self.assertFalse(any_match(msgs, r"inherited|run\.json"), msgs)

    def test_as_of_before_run_start_is_an_error(self) -> None:
        def early(ws: Path) -> None:
            (ws / "appendix" / "run.json").write_text(json.dumps({"run_started_utc": "2026-11-21T08:00:00Z"}), encoding="utf-8")

        msgs = msgs_after(early)
        self.assertTrue(any_match(msgs, r"As-Of Date 2026-11-20 is earlier than the run start"), msgs)

    def test_as_of_in_the_future_is_an_error(self) -> None:
        def future(ws: Path) -> None:
            M._edit(ws, "report.md", "**As-Of Date:** 2026-11-20", "**As-Of Date:** 2099-01-01")

        msgs = msgs_after(future)
        self.assertTrue(any_match(msgs, r"As-Of Date 2099-01-01 is in the future"), msgs)

    def test_missing_run_json_with_attempts_warns(self) -> None:
        def no_run(ws: Path) -> None:
            (ws / "appendix" / "run.json").unlink()

        msgs = msgs_after(no_run)
        self.assertTrue(any_match(msgs, r"no appendix/run\.json"), msgs)


class TestGateBinding(unittest.TestCase):
    def test_gate_hash_cli_prints_hex(self) -> None:
        res = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "validate_report.py"), str(M.GOLDEN / "report.md"), "--gate-hash", "qa"],
            capture_output=True,
            text=True, encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertRegex(res.stdout.strip(), r"^[0-9a-f]{64}$")
        self.assertEqual(res.stdout.strip(), validate_report.gate_hash(M.GOLDEN, "qa"))

    def test_qa_hash_ignores_the_gate_files_themselves(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            before = validate_report.gate_hash(ws, "qa")
            (ws / "appendix" / "gates" / "qa.md").write_text("changed", encoding="utf-8")
            self.assertEqual(before, validate_report.gate_hash(ws, "qa"))
        finally:
            tmp.cleanup()

    def test_fabricated_silhouette_gate_is_caught_by_missing_header(self) -> None:
        msgs = msgs_after(M.m03_fabricated_gates)
        self.assertTrue(any_match(msgs, r"missing header field\(s\): MODE:, REVIEWED-SHA256:, REVIEWED-UTC:, QUOTE"), msgs)

    def test_gate_that_reviewed_an_earlier_version_is_caught(self) -> None:
        msgs = msgs_after(M.m04_stale_gate)
        self.assertTrue(any_match(msgs, r"source_verifier\.md reviewed an earlier version"), msgs)

    def test_quote_that_does_not_match_its_line_is_caught(self) -> None:
        def bad_quote(ws: Path) -> None:
            g = ws / "appendix" / "gates" / "source_verifier.md"
            text = g.read_text(encoding="utf-8")
            m = re.search(r'^QUOTE: (\S+?):(\d+): "(.+)"$', text, re.MULTILINE)
            g.write_text(text.replace(m.group(0), f'QUOTE: {m.group(1)}:{m.group(2)}: "text that is not there"'), encoding="utf-8")

        msgs = msgs_after(bad_quote)
        self.assertTrue(any_match(msgs, r"quotes .* but that line does not contain"), msgs)

    def test_quote_outside_the_report_folder_is_rejected(self) -> None:
        def escape(ws: Path) -> None:
            g = ws / "appendix" / "gates" / "qa.md"
            text = g.read_text(encoding="utf-8")
            m = re.search(r'^QUOTE: .+$', text, re.MULTILINE)
            g.write_text(text.replace(m.group(0), 'QUOTE: ../../etc/passwd:1: "root"'), encoding="utf-8")

        msgs = msgs_after(escape)
        self.assertTrue(any_match(msgs, r"outside the report folder"), msgs)

    def test_self_review_must_be_declared_in_section_3(self) -> None:
        def undeclared(ws: Path) -> None:
            text = (ws / "report.md").read_text(encoding="utf-8")
            sec3 = text.index("## 3.")
            sec4 = text.index("## 4.")
            body = re.sub(r"(?i)self-review", "manual check", text[sec3:sec4])
            (ws / "report.md").write_text(text[:sec3] + body + text[sec4:], encoding="utf-8")

        msgs = msgs_after(undeclared)
        self.assertTrue(any_match(msgs, r"is a self-review .* say so in Section 3"), msgs)

    def test_golden_gates_are_bound_and_declared(self) -> None:
        self.assertEqual(M.baseline(), [])


if __name__ == "__main__":
    unittest.main()
