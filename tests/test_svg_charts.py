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


if __name__ == "__main__":
    unittest.main()
