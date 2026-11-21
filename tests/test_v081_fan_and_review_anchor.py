"""v0.8.1 Phase 3 tests: calibrated fans (M31, M32) and the analysis.py anchor of the reviewer gate (M33)."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import svg_charts  # noqa: E402
import validate_report  # noqa: E402

SCRIPT = Path(M.SCRIPTS) / "validate_report.py"


def has(msgs: list[str], pattern: str) -> bool:
    return any(re.search(pattern, m, re.IGNORECASE) for m in msgs)


def full(ws: Path, level: int = 2) -> tuple[list[str], list[str]]:
    M.restamp_gates(ws)
    return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)


def fan(title: str = "Scenario fan", calibration=None, p10=(100, 98, 96), p50=(100, 101, 102), observed="2026-10") -> dict:
    pts = lambda vals: [[f"2026-{10 + i}", v] for i, v in enumerate(vals)]  # noqa: E731
    chart = {
        "id": "f1",
        "type": "fan",
        "title": title,
        "caption": "Scenario quantiles.",
        "x": {"type": "date", **({"observed_until": observed} if observed else {})},
        "y": {"label": "Index"},
        "quantiles": {"p10": pts(p10), "p50": pts(p50), "p90": pts((100, 104, 108))},
    }
    if calibration is not None:
        chart["calibration"] = calibration
    return chart


class TestFanCalibration(unittest.TestCase):
    def test_calibrated_without_block_warns(self) -> None:
        w = svg_charts.chart_warnings(fan(title="Calibrated fan"))
        self.assertTrue(has(w, r"calibration"), w)

    def test_partial_block_warns(self) -> None:
        w = svg_charts.chart_warnings(fan(title="Calibrated fan", calibration={"method": "rolling RMSE"}))
        self.assertTrue(has(w, r"calibration"), w)

    def test_complete_block_is_accepted_by_warnings_and_schema(self) -> None:
        block = {"method": "rolling-origin RMSE, 24 months", "source_id": "C4"}
        chart = fan(title="Calibrated fan", calibration=block)
        self.assertFalse(has(svg_charts.chart_warnings(chart), r"calibration"))
        self.assertEqual(svg_charts.validate_charts_schema(chart), [])

    def test_calibration_must_be_an_object(self) -> None:
        errs = svg_charts.validate_charts_schema(fan(calibration="yes"))
        self.assertTrue(has(errs, r"calibration"), errs)

    def test_spanish_word_and_non_calibrated_fan(self) -> None:
        self.assertTrue(has(svg_charts.chart_warnings(fan(title="Abanico calibrado")), r"calibration"))
        self.assertFalse(has(svg_charts.chart_warnings(fan(title="Scenario fan")), r"calibration"))

    def test_mutation_m31_has_design_code(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m31_fan_called_calibrated_without_calibration(ws)
            _, w = full(ws)
            hit = [m for m in w if re.search(r"calibration", m, re.IGNORECASE)]
            self.assertTrue(hit, w)
            self.assertEqual(validate_report.classify_message(hit[0])[0], "FIG-DESIGN")
        finally:
            tmp.cleanup()


class TestFanLowerAnchor(unittest.TestCase):
    def test_p10_above_last_observed_warns(self) -> None:
        w = svg_charts.chart_warnings(fan(p10=(100, 103, 106), p50=(100, 105, 110)))
        self.assertTrue(has(w, r"\bp10\b"), w)

    def test_p10_at_or_below_last_observed_is_fine(self) -> None:
        for first_step in (100, 99, 90):
            w = svg_charts.chart_warnings(fan(p10=(100, first_step, 95)))
            self.assertFalse(has(w, r"\bp10\b"), (first_step, w))

    def test_single_point_or_missing_observed_until_never_crashes(self) -> None:
        one = fan(p10=(100,), p50=(100,))
        self.assertFalse(has(svg_charts.chart_warnings(one), r"\bp10\b"))
        none = fan(p10=(100, 103, 106), observed="")
        self.assertFalse(has(svg_charts.chart_warnings(none), r"\bp10\b"))
        empty = fan()
        empty["quantiles"]["p10"] = []
        self.assertIsInstance(svg_charts.chart_warnings(empty), list)

    def test_fan_messages_are_design_not_schema(self) -> None:
        for msg in (
            "Chart 'f1': fan chart quantiles diverge at observed_until anchor '2026-10' (99 to 101); anchor all quantiles.",
            "Chart 'f1': fan chart first projected p10 (103) is above the last observed value (100).",
        ):
            self.assertEqual(validate_report.classify_message(msg)[0], "FIG-DESIGN", msg)

    def test_mutation_m32_is_flagged(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m32_fan_p10_excludes_decline(ws)
            _, w = full(ws)
            self.assertTrue(has(w, r"\bp10\b"), w)
        finally:
            tmp.cleanup()


class TestReviewerAnalysisAnchor(unittest.TestCase):
    def test_changed_analysis_without_section_warns_l2_errors_l3(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m33_analysis_changed_after_reviewer(ws)
            e2, w2 = full(ws, 2)
            hit = [m for m in w2 if re.search(r"after the reviewer", m, re.IGNORECASE)]
            self.assertTrue(hit, (e2, w2))
            self.assertEqual(validate_report.classify_message(hit[0]), ("GATE-BINDING", "appendix/gates/reviewer.md"))
            e3, _ = full(ws, 3)
            self.assertTrue(has(e3, r"after the reviewer"), e3)
        finally:
            tmp.cleanup()

    def test_post_review_section_silences_it(self) -> None:
        for heading in ("### Post-review changes", "### Cambios posteriores a la revisión"):
            tmp, ws = M.fresh_workspace()
            try:
                M.m33_analysis_changed_after_reviewer(ws)
                M._edit(ws, "report.md", "## 6. Claim-Evidence Matrix", f"{heading}\n- analysis.py: seed fixed.\n\n## 6. Claim-Evidence Matrix")
                e, w = full(ws)
                self.assertFalse(has(e + w, r"after the reviewer"), (heading, e, w))
            finally:
                tmp.cleanup()

    def test_matching_hash_or_missing_line_is_silent(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m33_analysis_changed_after_reviewer(ws)
            gate = ws / "appendix" / "gates" / "reviewer.md"
            current = hashlib.sha256((ws / "appendix" / "analysis.py").read_bytes()).hexdigest()[:12]
            text = gate.read_text(encoding="utf-8")
            gate.write_text(re.sub(r"ANALYSIS-SHA256: \w+", f"ANALYSIS-SHA256: {current}", text), encoding="utf-8")
            e, w = full(ws)
            self.assertFalse(has(e + w, r"after the reviewer"), (e, w))
            gate.write_text(re.sub(r"ANALYSIS-SHA256: \w+\n", "", text), encoding="utf-8")  # a v0.8.0 gate
            e, w = full(ws)
            self.assertFalse(has(e + w, r"after the reviewer"), (e, w))
        finally:
            tmp.cleanup()

    def test_gate_header_prints_analysis_hash_for_reviewer_only(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            expected = hashlib.sha256((ws / "appendix" / "analysis.py").read_bytes()).hexdigest()[:12]
            run = lambda gate: subprocess.run(  # noqa: E731
                [sys.executable, "-B", str(SCRIPT), str(ws / "report.md"), "--gate-header", gate],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertIn(f"ANALYSIS-SHA256: {expected}", run("reviewer").stdout)
            self.assertNotIn("ANALYSIS-SHA256", run("qa").stdout)
            self.assertNotIn("ANALYSIS-SHA256", run("source_verifier").stdout)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
