"""v0.7.0 Phase 4 (P1-4): charts.json is validated against a schema instead of silently rendering nonsense."""

import json
import re
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import svg_charts as SC  # noqa: E402


def errs(chart):
    return SC.validate_charts_schema(chart)


def has(msgs, pattern):
    return any(re.search(pattern, m) for m in msgs)


LINE = {"id": "l", "type": "line", "x": {"type": "date"}, "series": [{"name": "s", "points": [["2026-01", 1], ["2026-02", 2]]}]}


class TestSchema(unittest.TestCase):
    def test_valid_charts_have_no_messages(self) -> None:
        self.assertEqual(errs(LINE), [])
        bar = {"id": "b", "type": "bar", "groups": ["A", "B"], "series": [{"name": "s", "values": [1, 2]}]}
        self.assertEqual(errs(bar), [])
        flat = {"id": "f", "type": "bar", "series": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]}
        self.assertEqual(errs(flat), [])
        fan = {"id": "n", "type": "fan", "x": {"type": "date"}, "quantiles": {
            "p10": [["2026-11", 1], ["2027-01", 2]], "p50": [["2026-11", 2], ["2027-01", 3]], "p90": [["2026-11", 3], ["2027-01", 4]]}}
        self.assertEqual(errs(fan), [])

    def test_golden_and_level2_example_charts_are_valid(self) -> None:
        for d in ("showcase-hybrid-work", "level2-study"):
            charts = json.loads((M.ROOT / "examples" / d / "charts.json").read_text(encoding="utf-8"))
            for ch in charts:
                self.assertEqual(errs(ch), [], msg=f"{d}:{ch['id']}")

    def test_nan_and_inf_are_reported_with_location(self) -> None:
        bad = json.loads(json.dumps(LINE)); bad["series"][0]["points"][1][1] = float("nan")
        self.assertTrue(has(errs(bad), r"non-finite.*series\[0\]\.points\[1\]"), errs(bad))
        bad["series"][0]["points"][1][1] = float("inf")
        self.assertTrue(has(errs(bad), r"non-finite"), errs(bad))

    def test_numeric_string_is_reported(self) -> None:
        bad = {"id": "s", "type": "line", "series": [{"name": "s", "points": [[1, "3,5"], [2, 3]]}]}
        self.assertTrue(has(errs(bad), r"'3,5' is a string, not a number"), errs(bad))

    def test_group_and_value_length_mismatch(self) -> None:
        bad = {"id": "m", "type": "bar", "groups": ["A", "B", "C"], "series": [{"name": "s", "values": [1, 2]}]}
        self.assertTrue(has(errs(bad), r"3 groups but series\[0\] has 2 values"), errs(bad))

    def test_typo_in_a_key_suggests_the_right_one(self) -> None:
        bad = {"id": "t", "type": "bar", "categories": ["A", "B"], "series": [{"name": "s", "values": [1, 2]}]}
        self.assertTrue(has(errs(bad), r"unknown key 'categories'.*did you mean 'groups'"), errs(bad))

    def test_unknown_type_and_empty_chart(self) -> None:
        self.assertTrue(has(errs({"id": "x", "type": "pie", "series": []}), r"unknown type 'pie'"))
        self.assertTrue(has(errs({"id": "e", "type": "line", "series": []}), r"no data"))

    def test_fan_quantiles_must_be_ordered(self) -> None:
        bad = {"id": "q", "type": "fan", "x": {"type": "date"}, "quantiles": {
            "p10": [["2026-11", 300], ["2027-01", 320]], "p50": [["2026-11", 100], ["2027-01", 120]],
            "p90": [["2026-11", 10], ["2027-01", 20]]}}
        self.assertTrue(has(errs(bad), r"quantile p10 exceeds p50 at 2026-11"), errs(bad))
        self.assertTrue(has(errs(bad), r"quantile p50 exceeds p90"), errs(bad))

    def test_fan_needs_p50(self) -> None:
        self.assertTrue(has(errs({"id": "q", "type": "fan", "quantiles": {"p10": [[1, 1]]}}), r"needs a p50"))

    def test_invalid_date_is_reported(self) -> None:
        bad = {"id": "d", "type": "line", "x": {"type": "date"}, "series": [{"name": "s", "points": [["2026-13-45", 1], ["soon", 2]]}]}
        self.assertTrue(has(errs(bad), r"invalid date 'soon'"), errs(bad))

    def test_point_shape(self) -> None:
        bad = {"id": "p", "type": "line", "series": [{"name": "s", "points": [[1], [2, 3]]}]}
        self.assertTrue(has(errs(bad), r"points\[0\] must be \[x, y\]"), errs(bad))


class TestRenderingNeverCrashesOrLeaksNaN(unittest.TestCase):
    def test_non_finite_points_are_dropped_from_the_svg(self) -> None:
        bad = json.loads(json.dumps(LINE)); bad["series"][0]["points"].append(["2026-03", float("nan")])
        svg = SC.render_chart_svg(bad)
        self.assertNotRegex(svg.lower(), r"\bnan\b|\binf\b")

    def test_numeric_strings_are_coerced_without_a_traceback(self) -> None:
        chart = {"id": "s", "type": "line", "series": [{"name": "s", "points": [[1, "3,5"], [2, "4.5"], [3, 5]]}]}
        svg = SC.render_chart_svg(chart)
        self.assertTrue(svg.startswith("<svg") or "<svg" in svg)

    def test_garbage_values_render_the_no_data_figure(self) -> None:
        svg = SC.render_chart_svg({"id": "g", "type": "line", "series": [{"name": "s", "points": [[1, "abc"]]}]})
        self.assertIn("<svg", svg)


class TestValidatorWiring(unittest.TestCase):
    def test_nan_and_inverted_fan_are_errors_in_the_validator(self) -> None:
        for name, pattern in (("M12", r"non-finite"), ("M13", r"quantile p10 exceeds")):
            msgs = M.run_mutation(name)
            self.assertTrue(has(msgs, pattern), (name, msgs))

    def test_strict_json_dump_template_uses_allow_nan_false(self) -> None:
        text = (M.ROOT / "skills" / "heurisma" / "references" / "data-protocol.md").read_text(encoding="utf-8")
        self.assertIn("allow_nan=False", text)

    def test_charts_json_with_nan_literal_is_flagged_as_invalid_strict_json(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m12_nan_in_charts_json(ws)
            self.assertIn("NaN", (ws / "charts.json").read_text(encoding="utf-8"))
            msgs = M.detect(ws)
            self.assertTrue(has(msgs, r"non-finite|NaN"), msgs)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
