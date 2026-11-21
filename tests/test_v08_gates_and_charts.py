"""v0.8.0 Phase 3 tests: frictionless gates (Task 6) and temporal/fan chart rules (Task 7 / M23)."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import svg_charts  # noqa: E402
import validate_report  # noqa: E402


class TestFrictionlessGates(unittest.TestCase):
    def test_quote_line_with_num_marker_passes_gate_privacy_and_html_marker(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            # Find a real line in report.md containing {{num:...}} and quote a substring that includes it
            report_lines = (ws / "report.md").read_text(encoding="utf-8").splitlines()
            line_no, full_line = next(
                (i, ln.strip()) for i, ln in enumerate(report_lines, start=1) if "{{num:" in ln
            )
            idx = full_line.index("{{num:")
            snippet = full_line[max(0, idx - 10): idx + 45]
            qa_path = ws / "appendix" / "gates" / "qa.md"
            qa_text = qa_path.read_text(encoding="utf-8")
            qa_text = qa_text.replace(
                "REVIEWED-UTC:",
                f'QUOTE: report.md:{line_no}: "{snippet}"\nREVIEWED-UTC:',
                1,
            )
            qa_path.write_text(qa_text, encoding="utf-8")
            M.restamp_gates(ws)
            M.rerender(ws)
            msgs = M.detect(ws, level=2)
            self.assertEqual(msgs, [], f"Expected QUOTE with {{{{num:...}}}} to pass cleanly, got: {msgs}")
            # Also confirm render_report escaped {{ inside embedded gate <pre><code>
            html = (ws / "report.html").read_text(encoding="utf-8")
            self.assertEqual(validate_report.validate_html_full(ws / "report.html"), ([], []))
            self.assertIn("&#123;&#123;num:", html)
        finally:
            tmp.cleanup()

    def test_reviewer_hash_drift_after_closed_disposition_passes_strict(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            # Add a valid reviewer.md stamped BEFORE editing output.txt, plus a closed Disposition Table in §5
            rev_hash = validate_report.gate_hash(ws, "reviewer")
            rev_md = ws / "appendix" / "gates" / "reviewer.md"
            rev_md.write_text(
                f"MODE: subagent\n"
                f"REVIEWED-SHA256: {rev_hash}\n"
                f"REVIEWED-UTC: 2026-11-20T12:00:00Z\n"
                f'QUOTE: appendix/sources.csv:1: "claim_id,source_title"\n'
                f'QUOTE: appendix/data_attempts.csv:1: "target_series,source_tried"\n\n'
                "1. Over-calibrated claims: checked.\n"
                "2. Unattempted data shortcuts: checked.\n"
                "3. Missing counter-evidence and controls: checked.\n"
                "4. Interdisciplinary and forecasting flaws: checked.\n"
                "5. Decisions inside the noise: checked.\n"
                "6. Provenance contradictions: checked.\n"
                "MOST DAMAGING: minor wording.\n"
                + ("detail " * 80),
                encoding="utf-8",
            )
            # Now edit output.txt (simulating applying Reviewer #2 fixes) and add Disposition Table in §5
            out_p = ws / "appendix" / "output.txt"
            out_p.write_text(out_p.read_text(encoding="utf-8") + "\n# reviewer fix\n", encoding="utf-8")
            disp = (
                "\n### Reviewer #2 Disposition\n\n"
                "| # | Critique | Action | Resolution |\n"
                "| :- | :- | :- | :- |\n"
                "| 1 | Minor wording | Fixed | Updated output and narrative |\n"
            )
            M._edit(ws, "report.md", "## 6. Claim-Evidence Matrix", disp + "\n## 6. Claim-Evidence Matrix")
            # Re-stamp qa.md (runs AFTER fixes), NOT reviewer.md (keeps pre-fix hash!)
            qa_p = ws / "appendix" / "gates" / "qa.md"
            qa_p.write_text(
                re.sub(
                    r"^(REVIEWED-SHA256:\s*)[0-9a-fA-F]+",
                    lambda m: m.group(1) + validate_report.gate_hash(ws, "qa"),
                    qa_p.read_text(encoding="utf-8"),
                    flags=re.MULTILINE,
                ),
                encoding="utf-8",
            )
            text = (ws / "report.md").read_text(encoding="utf-8")
            _, warnings = validate_report.validate_report_full(text, level=3, report_dir=ws)
            self.assertFalse(
                any("reviewer.md reviewed an earlier version" in w for w in warnings),
                f"Expected no reviewer hash warning with closed Disposition Table, got: {warnings}",
            )
        finally:
            tmp.cleanup()

    def test_cli_gate_header_emits_mode_hash_and_real_utc(self) -> None:
        res = subprocess.run(
            [
                sys.executable, "-B", str(M.SCRIPTS / "validate_report.py"),
                str(M.GOLDEN / "report.md"), "--gate-header", "qa",
            ],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("MODE: subagent", res.stdout)
        expected_hash = validate_report.gate_hash(M.GOLDEN, "qa")
        self.assertIn(f"REVIEWED-SHA256: {expected_hash}", res.stdout)
        self.assertRegex(res.stdout, r"REVIEWED-UTC:\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class TestTemporalAndFanCharts(unittest.TestCase):
    def test_line_chart_point_after_as_of_date_is_schema_error(self) -> None:
        ch = {
            "id": "cap",
            "type": "line",
            "title": "Capacity",
            "x": {"type": "date"},
            "y": {"label": "MW"},
            "series": [{"name": "S", "points": [["2025-12", 100.0], ["2026-12", 110.0]]}],
        }
        errs = svg_charts.validate_charts_schema(ch, as_of_date="2026-11-21")
        self.assertTrue(any("after the report As-Of Date" in e for e in errs), errs)

        # Before As-Of Date -> clean
        ch["series"][0]["points"][1][0] = "2026-09"
        self.assertEqual(svg_charts.validate_charts_schema(ch, as_of_date="2026-11-21"), [])

        # With observed_until (projection line) -> future date allowed
        ch["series"][0]["points"][1][0] = "2026-12"
        ch["x"]["observed_until"] = "2026-09"
        self.assertEqual(svg_charts.validate_charts_schema(ch, as_of_date="2026-11-21"), [])

    def test_fan_chart_mismatched_anchor_at_observed_until_warns(self) -> None:
        ch = {
            "id": "f1",
            "type": "fan",
            "title": "Forecast",
            "x": {"type": "date", "observed_until": "2026-01"},
            "y": {"label": "MW"},
            "quantiles": {
                "p10": [["2026-01", 30499.0], ["2027-01", 31000.0]],
                "p50": [["2026-01", 30257.0], ["2027-01", 31500.0]],
                "p90": [["2026-01", 30800.0], ["2027-01", 32000.0]],
            },
        }
        warns = svg_charts.chart_warnings(ch)
        self.assertTrue(any("anchor" in w.lower() or "observed_until" in w.lower() for w in warns), warns)


if __name__ == "__main__":
    unittest.main()
