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


if __name__ == "__main__":
    unittest.main()
