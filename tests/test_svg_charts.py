import re
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import svg_charts  # noqa: E402


class TestSvgCharts(unittest.TestCase):
    def test_heckbert_nice_ticks(self) -> None:
        ticks = svg_charts.nice_ticks(0.0, 1870.0, max_ticks=5)
        self.assertGreaterEqual(len(ticks), 4)
        self.assertLessEqual(len(ticks), 7)
        self.assertLessEqual(ticks[0], 0.0)
        self.assertGreaterEqual(ticks[-1], 1870.0)

    def test_dense_date_line_chart_with_bands_and_annotations(self) -> None:
        # 120 monthly points (>30 -> must omit per-point circles and per-point labels!)
        pts = [[f"{2016 + i // 12:04d}-{(i % 12) + 1:02d}", 100.0 + i * 12.5] for i in range(120)]
        chart = {
            "id": "fx_band",
            "type": "line",
            "title": "Official Exchange Rate and Policy Band",
            "caption": "Rate stayed inside the crawling band throughout 2025.",
            "source": "Central Bank API v4",
            "x": {"type": "date", "label": ""},
            "y": {"label": "ARS / USD", "scale": "linear"},
            "series": [{"name": "A3500", "points": pts}],
            "bands": [
                {
                    "name": "Policy Band",
                    "lower": [["2025-01", 1000.0], ["2025-12", 1100.0]],
                    "upper": [["2025-01", 1400.0], ["2025-12", 1600.0]],
                }
            ],
            "annotations": [{"x": "2023-12", "label": "Devaluation"}],
        }
        svg = svg_charts.render_chart_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("<title>", svg)
        self.assertIn("<desc>", svg)
        self.assertIn("Devaluation", svg)
        self.assertIn("<polygon", svg)  # shaded band
        self.assertIn("2020", svg)      # readable date tick
        self.assertIn("#0072B2", svg)   # Okabe-Ito primary blue
        # Must NOT draw 120 circles on a dense (>30 pt) series
        self.assertEqual(svg.count("<circle"), 0)

    def test_fan_projection_chart(self) -> None:
        chart = {
            "id": "proj_fan",
            "type": "fan",
            "title": "Projected Exchange Rate Distribution",
            "x": {"type": "date"},
            "y": {"label": "ARS / USD"},
            "quantiles": {
                "p10": [["2026-12", 1450], ["2027-12", 1600]],
                "p25": [["2026-12", 1500], ["2027-12", 1800]],
                "p50": [["2026-12", 1550], ["2027-12", 2050]],
                "p75": [["2026-12", 1620], ["2027-12", 2350]],
                "p90": [["2026-12", 1700], ["2027-12", 2800]],
            },
            "reference_lines": [{"name": "Band Ceiling", "value": 2400}],
        }
        svg = svg_charts.render_chart_svg(chart)
        self.assertIn("<polygon", svg)
        self.assertIn("<polyline", svg)
        self.assertIn("Band Ceiling", svg)

    def test_grouped_bar_chart_and_log_scale_safety(self) -> None:
        bar = {
            "id": "gov_bar",
            "type": "bar",
            "title": "Depreciation vs. CPI by Administration",
            "groups": ["Admin A", "Admin B"],
            "series": [
                {"name": "Depreciation (%)", "values": [120.0, 85.0]},
                {"name": "CPI (%)", "values": [110.0, 95.0]},
            ],
        }
        svg_bar = svg_charts.render_chart_svg(bar)
        self.assertIn("<rect", svg_bar)
        self.assertIn("Admin A", svg_bar)
        self.assertIn("CPI (%)", svg_bar)

        # Log scale with a zero value must not crash
        log_chart = {
            "id": "log_safe",
            "type": "line",
            "title": "Log Scale Test",
            "y": {"label": "Index", "scale": "log"},
            "series": [{"name": "S1", "points": [[1, 0.0], [2, 10.0], [3, 1000.0]]}],
        }
        svg_log = svg_charts.render_chart_svg(log_chart)
        self.assertIn("<svg", svg_log)

    def test_v1_backward_compatibility(self) -> None:
        v1_bar = {
            "title": "Legacy v1 Bar",
            "type": "bar",
            "series": [{"label": "Full r", "value": 0.98}, {"label": "Clean r", "value": -0.77}],
        }
        svg = svg_charts.render_chart_svg(v1_bar)
        self.assertIn("<rect", svg)
        self.assertIn("Full r", svg)

    def test_close_annotations_stagger_vertically_and_flip_near_right_edge(self) -> None:
        import re

        pts = [[f"{2016 + i // 12:04d}-{(i % 12) + 1:02d}", 100.0 + i * 5.0] for i in range(120)]
        chart = {
            "id": "ann_test",
            "type": "line",
            "title": "Close Annotations & Right Edge",
            "x": {"type": "date"},
            "y": {"label": "Index"},
            "series": [{"name": "Series", "points": pts}],
            "annotations": [
                {"x": "2023-11", "label": "Elecciones"},
                {"x": "2023-12", "label": "Devaluación fuerte"},
                {"x": "2025-11", "label": "Salida convert."},
            ],
        }
        svg = svg_charts.render_chart_svg(chart)
        # Long label (>16 chars) should be truncated with ellipsis
        self.assertIn("…", svg)
        # Close annotations must have distinct y coordinates
        m1 = re.search(r'<text[^>]*y="([0-9.]+)"[^>]*>Elecciones</text>', svg)
        m2 = re.search(r'<text[^>]*y="([0-9.]+)"[^>]*>Devaluación[^<]*</text>', svg)
        self.assertIsNotNone(m1, msg=svg)
        self.assertIsNotNone(m2, msg=svg)
        self.assertNotEqual(float(m1.group(1)), float(m2.group(1)), "Close annotations must stagger vertically")
        # Right-edge annotation must flip left with text-anchor="end"
        m3 = re.search(r'<text[^>]*text-anchor="end"[^>]*>Salida convert\.</text>', svg)
        self.assertIsNotNone(m3, "Right-edge annotation must flip left using text-anchor='end'")

    def test_reference_line_label_has_white_halo(self) -> None:
        chart = {
            "id": "ref_halo",
            "type": "line",
            "title": "ITCRM with Mean",
            "x": {"type": "date"},
            "y": {"label": "Index"},
            "series": [{"name": "ITCRM", "points": [["2020-01", 90], ["2021-01", 110], ["2022-01", 95]]}],
            "reference_lines": [{"name": "Media 1997-2026", "value": 100}],
        }
        svg = svg_charts.render_chart_svg(chart)
        self.assertIn("Media 1997-2026", svg)
        self.assertIn("paint-order", svg)
        # R2: a semi-transparent white box sits right behind the label so the series never shows through it
        m = re.search(r'<rect[^>]*class="ref-label-bg"[^>]*fill="#ffffff"[^>]*fill-opacity="0\.\d+"[^>]*/>\s*<text[^>]*>Media 1997-2026</text>', svg)
        self.assertIsNotNone(m, msg=svg[-800:])

    def test_last_data_marker_on_line_chart(self) -> None:
        chart = {
            "id": "last_data",
            "type": "line",
            "title": "FX with projection band",
            "x": {"type": "date", "last_label": True},
            "y": {"label": "ARS/USD"},
            "series": [{"name": "Spot", "points": [["2026-01", 1400], ["2026-06", 1500], ["2026-11", 1450]]}],
            "bands": [{"name": "P10-P90", "lower": [["2026-11", 1450], ["2027-12", 1600]],
                       "upper": [["2026-11", 1450], ["2027-12", 2400]]}],
        }
        es = svg_charts.render_chart_svg(chart, lang="es")
        self.assertIn("Último dato: 2026-11", es)
        self.assertIn('data-last-data="x"', es)
        self.assertIn("Last data: 2026-11", svg_charts.render_chart_svg(chart, lang="en"))
        # a date string positions the marker at that date
        chart["x"]["last_label"] = "2026-06-15"
        self.assertIn("Last data: 2026-06-15", svg_charts.render_chart_svg(chart))
        # off by default
        chart["x"].pop("last_label")
        self.assertNotIn("data-last-data", svg_charts.render_chart_svg(chart))
        # C6: drawn whenever it falls inside the axis, even when the observed series reaches the end of it
        chart["x"]["last_label"] = True
        chart.pop("bands")
        self.assertIn("data-last-data", svg_charts.render_chart_svg(chart))
        # outside the axis: not drawn
        chart["x"]["last_label"] = "2030-01-01"
        self.assertNotIn("data-last-data", svg_charts.render_chart_svg(chart))

    def _fan(self, x: dict) -> dict:
        q = {
            "p10": [["2026-11-13", 1450], ["2027-12-31", 1400]],  # lower tail allows a decline (v0.8.1 p10 anchor rule)
            "p25": [["2026-11-13", 1450], ["2027-12-31", 1700]],
            "p50": [["2026-11-13", 1450], ["2027-12-31", 1900]],
            "p75": [["2026-11-13", 1450], ["2027-12-31", 2100]],
            "p90": [["2026-11-13", 1450], ["2027-12-31", 2500]],
        }
        return {"id": "proyeccion_fan", "type": "fan", "title": "Proyección", "x": x, "y": {"label": "ARS/USD"},
                "quantiles": q}

    def test_fan_last_label_needs_observed_until(self) -> None:
        fan = self._fan({"type": "date", "last_label": True, "observed_until": "2026-11-13"})
        svg = svg_charts.render_chart_svg(fan, lang="es")
        self.assertIn('data-last-data="x"', svg)
        self.assertIn("Último dato: 2026-11-13", svg)
        # the observed date sits at the left edge of a fan: the label must open to the right, inside the plot
        self.assertRegex(svg, r'<text[^>]*text-anchor="start"[^>]*>Último dato: 2026-11-13</text>')
        self.assertEqual(svg_charts.chart_warnings(fan), [])
        bare = self._fan({"type": "date", "last_label": True})
        self.assertNotIn("data-last-data", svg_charts.render_chart_svg(bare))
        self.assertTrue(any("fan chart has last_label but no observed_until" in w for w in svg_charts.chart_warnings(bare)))
        dated = self._fan({"type": "date", "last_label": "2026-11-13"})
        self.assertIn("Last data: 2026-11-13", svg_charts.render_chart_svg(dated))
        self.assertEqual(svg_charts.chart_warnings(dated), [])

    def test_scatter_uses_nice_x_ticks_zero_line_and_highlight_point(self) -> None:
        chart = {
            "id": "scatter_nice",
            "type": "scatter",
            "title": "Scatter Test",
            "x": {"label": "Real Rate (%)"},
            "y": {"label": "FX Change (%)"},
            "series": [{"name": "Periods", "points": [[-29.0, -15.0], [12.3, 8.5], [148.7, 62.0]]}],
            "highlight": {"x": 12.3, "y": 8.5, "label": "Actual (2026)"},
        }
        svg = svg_charts.render_chart_svg(chart)
        # Nice ticks on X axis: should NOT show ugly -29 or 6.7 / 42.4, should include clean 0 and 50 or 100
        self.assertNotIn(">6.7<", svg)
        self.assertNotIn(">42.4<", svg)
        self.assertIn(">0<", svg)
        # Highlighted point label must appear
        self.assertIn("Actual (2026)", svg)
        # Zero horizontal reference line must be drawn when 0 is in Y range
        self.assertIn('data-zero-line="y"', svg)

    def test_percent_and_locale_number_formatting_and_tight_y_max(self) -> None:
        # Percent format (0 -> 0%, 0.5 -> 50%, 1.0 -> 100%, 1.5 -> 150%)
        pct_chart = {
            "id": "brecha_pct",
            "type": "line",
            "title": "FX Gap",
            "x": {"type": "date"},
            "y": {"label": "Brecha", "format": "percent"},
            "series": [{"name": "Brecha", "points": [["2023-01", 0.0], ["2024-01", 1.5], ["2025-01", 0.2]]}],
        }
        svg_pct = svg_charts.render_chart_svg(pct_chart, lang="es")
        self.assertIn("0%", svg_pct)
        self.assertIn("150%", svg_pct)

        # Locale es: dot thousands, tight Y max (max 50,000 must NOT stretch to 60,000)
        res_chart = {
            "id": "reserves_tight",
            "type": "line",
            "title": "Reservas",
            "x": {"type": "date"},
            "y": {"label": "USD M", "format": "thousands"},
            "series": [{"name": "Reservas", "points": [["2020-01", 20000], ["2021-01", 49500], ["2022-01", 35000]]}],
        }
        svg_res = svg_charts.render_chart_svg(res_chart, lang="es")
        self.assertIn("50.000", svg_res)
        self.assertNotIn("60.000", svg_res)

    def test_fan_chart_localized_three_layer_legend_and_no_median_markers(self) -> None:
        chart = {
            "id": "proj_fan_es",
            "type": "fan",
            "title": "Proyección TC 2027",
            "x": {"type": "date"},
            "y": {"label": "ARS / USD"},
            "quantiles": {
                "p10": [["2026-12", 1450], ["2027-06", 1520], ["2027-12", 1600]],
                "p25": [["2026-12", 1500], ["2027-06", 1650], ["2027-12", 1800]],
                "p50": [["2026-12", 1550], ["2027-06", 1800], ["2027-12", 2050]],
                "p75": [["2026-12", 1620], ["2027-06", 1980], ["2027-12", 2350]],
                "p90": [["2026-12", 1700], ["2027-06", 2200], ["2027-12", 2800]],
            },
        }
        svg = svg_charts.render_chart_svg(chart, lang="es")
        self.assertIn("Mediana (P50)", svg)
        self.assertNotIn("Median (P50)", svg)
        self.assertIn("P25–P75", svg)
        self.assertIn("P10–P90", svg)
        # Smooth fan median must NOT have point markers
        self.assertEqual(svg.count("<circle"), 0)


    # ---- v0.5.0 Phase 4: G1 long category labels, G2 near-identical bars, G3 x.max ---------------
    CAT_RE = r'<text class="cat-label" data-group="(\d+)" x="([\d.]+)" y="([\d.]+)"[^>]*>([^<]*)</text>'
    BAR_RE = r'<rect class="bar" data-value="([^"]+)" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"'

    def _bar(self, labels: list[str], values: list[float], **extra: object) -> dict:
        chart = {
            "id": "b",
            "type": "bar",
            "title": "Bars",
            "series": [{"label": lb, "value": v} for lb, v in zip(labels, values)],
        }
        chart.update(extra)
        return chart

    def test_wrap_label_greedy_and_never_splits_words(self) -> None:
        self.assertEqual(svg_charts._wrap_label("Consenso REM: estabilizaci\u00f3n real", 14),
                         ["Consenso REM:", "estabilizaci\u00f3n", "real"])
        self.assertEqual(svg_charts._wrap_label("short", 14), ["short"])
        self.assertEqual(svg_charts._wrap_label("a" * 20, 14), ["a" * 20])  # overlong word kept whole

    def test_long_category_labels_wrap_without_overlap(self) -> None:
        import re

        labels = ["Consenso REM: estabilizaci\u00f3n real", "Escenario base: apreciaci\u00f3n", "Ruptura: salto cambiario",
                  "Banda: techo oficial", "Mercado: futuros", "Contraste hist\u00f3rico"]
        svg = svg_charts.render_chart_svg(self._bar(labels, [1, 2, 3, 4, 5, 6]), lang="es")
        self.assertIn('data-bar-layout="vertical"', svg)
        items = [(float(x), float(y), t) for _, x, y, t in re.findall(self.CAT_RE, svg)]
        self.assertGreaterEqual(len(items), len(labels))
        by_y: dict[float, list[tuple[float, str]]] = {}
        for x, y, t in items:
            by_y.setdefault(y, []).append((x, t))
        for row in by_y.values():
            row.sort()
            for (x1, t1), (x2, t2) in zip(row, row[1:]):
                self.assertGreaterEqual(x2 - 3.1 * len(t2), x1 + 3.1 * len(t1), msg=f"{t1!r} overlaps {t2!r}")
        self.assertNotIn("\u2026", svg)  # nothing truncated

    def test_labels_that_do_not_fit_wrapped_switch_to_horizontal_bars(self) -> None:
        import re

        labels = [f"Continuaci\u00f3n de 2026: apreciaci\u00f3n real {i}" for i in range(1, 9)]
        values = [10.0, 20.0, 40.0, 15.0, 5.0, 30.0, 25.0, 35.0]
        svg = svg_charts.render_chart_svg(self._bar(labels, values), lang="es")
        self.assertIn('data-bar-layout="horizontal"', svg)
        bars = {float(v): float(w) for v, _, _, w, _ in re.findall(self.BAR_RE, svg)}
        self.assertAlmostEqual(bars[20.0] / bars[10.0], 2.0, places=1)
        self.assertAlmostEqual(bars[40.0] / bars[10.0], 4.0, places=1)
        self.assertIn("Continuaci\u00f3n", svg)
        self.assertNotIn("\u2026", svg)

    def test_baseline_truncates_axis_with_visible_warning(self) -> None:
        import re

        chart = self._bar(["A", "B"], [0.717, 0.760], y={"baseline": 0.70})
        svg_en = svg_charts.render_chart_svg(chart, lang="en")
        self.assertIn("Truncated axis", svg_en)
        self.assertIn("Eje truncado", svg_charts.render_chart_svg(chart, lang="es"))
        hs = {float(v): float(h) for v, _, _, _, h in re.findall(self.BAR_RE, svg_en)}
        self.assertGreater(hs[0.76] / hs[0.717], 2.0)  # from zero it would be ~1.06

    def test_diff_plots_relative_difference_vs_first_bar(self) -> None:
        svg = svg_charts.render_chart_svg(self._bar(["Base", "Variant"], [0.717, 0.760], diff=True), lang="en")
        self.assertIn("6.0%", svg)
        self.assertIn("Difference vs. Base", svg)
        grouped = {
            "id": "g", "type": "bar", "title": "G", "diff": True, "groups": ["G1", "G2"],
            "series": [{"name": "Ref", "values": [100.0, 200.0]}, {"name": "Alt", "values": [110.0, 190.0]}],
        }
        svg_g = svg_charts.render_chart_svg(grouped, lang="en")
        self.assertIn("10%", svg_g)
        self.assertIn("\u22125%", svg_g.replace("-5%", "\u22125%"))

    def test_chart_warnings_flag_near_identical_bars_only_without_baseline_or_diff(self) -> None:
        near = self._bar(["A", "B"], [0.717, 0.7172])
        self.assertTrue(any("near-identical" in w for w in svg_charts.chart_warnings(near)))
        self.assertEqual(svg_charts.chart_warnings(self._bar(["A", "B"], [0.717, 0.7172], y={"baseline": 0.7})), [])
        self.assertEqual(svg_charts.chart_warnings(self._bar(["A", "B"], [0.717, 0.7172], diff=True)), [])
        self.assertEqual(svg_charts.chart_warnings(self._bar(["A", "B"], [1.0, 2.0])), [])
        self.assertEqual(svg_charts.chart_warnings({"type": "line", "series": []}), [])
        grouped = {"type": "bar", "groups": ["G1", "G2"],
                   "series": [{"name": "A", "values": [1.0, 5.0]}, {"name": "B", "values": [1.001, 9.0]}]}
        self.assertTrue(any("near-identical" in w for w in svg_charts.chart_warnings(grouped)))

    def test_x_max_trims_empty_right_gap_on_date_axis(self) -> None:
        import re

        pts = [[f"2026-{m:02d}", 1400.0 + m * 10] for m in range(1, 11)] + [["2026-11-19", 1562.99]]
        base = {
            "id": "fx", "type": "line", "title": "FX", "x": {"type": "date"},
            "series": [{"name": "A3500", "points": pts}],
            "bands": [{"name": "Band", "lower": [["2026-01", 1000.0], ["2026-12-31", 1100.0]],
                       "upper": [["2026-01", 1900.0], ["2026-12-31", 2000.0]]}],
        }

        def last_x(chart: dict) -> float:
            svg = svg_charts.render_chart_svg(chart)
            poly = re.search(r'<polyline fill="none" stroke="#0072B2"[^>]*points="([^"]+)"', svg).group(1)
            return float(poly.split()[-1].split(",")[0])

        self.assertLess(last_x(base), 640.0)  # gap on the right (band runs to December)
        trimmed = dict(base, x={"type": "date", "max": "2026-11-19"})
        self.assertGreater(last_x(trimmed), 653.0)  # right plot edge = 680 - 26

    def test_scatter_acceptance_round_ticks_zero_line_highlight_and_percent_axis(self) -> None:
        chart = {
            "id": "sc", "type": "scatter", "title": "Gap vs level",
            "x": {"label": "Level"}, "y": {"label": "Gap", "format": "percent"},
            "series": [{"name": "Obs", "points": [[0.13, -0.08], [0.27, 0.02], [0.41, 0.06], [0.58, -0.03], [0.87, 0.11]]}],
            "highlight": {"x": 0.58, "y": -0.03, "label": "Now"},
        }
        svg = svg_charts.render_chart_svg(chart, lang="es")
        self.assertIn('data-zero-line="y"', svg)
        self.assertIn("#D55E00", svg)
        self.assertIn("Now", svg)
        self.assertIn("%", svg)
        for round_tick in (">0,2<", ">0,4<", ">0,6<", ">0,8<"):
            self.assertIn(round_tick, svg)


    def test_truncated_axis_warning_sits_below_plot_not_over_value_labels(self) -> None:
        import re

        svg = svg_charts.render_chart_svg(self._bar(["A", "B"], [0.717, 0.760], y={"baseline": 0.70}), lang="en")
        m = re.search(r'<text class="axis-warning" x="[\d.]+" y="([\d.]+)"', svg)
        height = float(re.search(r'viewBox="0 0 680 ([\d.]+)"', svg).group(1))
        cats = [float(y) for _, _, y, _ in re.findall(self.CAT_RE, svg)]
        self.assertGreater(float(m.group(1)), max(cats))  # below category labels
        self.assertLessEqual(float(m.group(1)), height)

    def test_negative_bar_value_labels_do_not_collide_with_category_labels(self) -> None:
        import re

        svg = svg_charts.render_chart_svg(self._bar(["G1", "G2"], [0.10, -0.05], y={"format": "percent"}), lang="en")
        cat_y = min(float(y) for _, _, y, _ in re.findall(self.CAT_RE, svg))
        m = re.search(r'<text x="[\d.]+" y="([\d.]+)" text-anchor="middle" font-size="10"[^>]*>-5%</text>', svg)
        self.assertIsNotNone(m, msg="negative value label missing")
        self.assertLess(float(m.group(1)), cat_y - 8.0)  # label sits clear above the category row


if __name__ == "__main__":
    unittest.main()
