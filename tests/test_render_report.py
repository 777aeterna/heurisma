import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import render_report  # noqa: E402
import validate_report  # noqa: E402


SAMPLE_MD = """# Pair-Programming Throughput Audit

> **As-Of Date:** 2026-11-20 | **Depth Level:** Level 2 | **Primary Disciplines:** Empirical Software Engineering, Causal Inference

## 1. Executive Summary
- **Calibrated Verdict:** `[Strong]` The apparent positive correlation ($r = 0.9804$) is an outlier artifact driven by `T12`; excluding `T12` reverses the relationship to negative (`[Moderate]`).
- **What Would Change This Conclusion:** Replicated multi-sprint data normalized by team headcount and ticket severity across comparable teams.

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** Software Engineering + Causal Inference | Level 2
- **Hypotheses:**
  - $H_0$: No positive monotonic association exists across typical teams.
  - $H_1$: Higher pair hours consistently increase bug-fix throughput.

## 3. Methodology & Evidence Standards
- **Analytical Method:** Reproducible zero-dependency Python audit saved in `appendix/analysis.py`.

## 4. Findings
Removing `T12` drops Pearson r from `+0.9804` to `-0.7742` (`[Strong]`), while full-sample Spearman rank correlation is already negative (`-0.3612`, `[Strong]`).

{{fig:corr_sens}}

## 5. Counter-Evidence & Alternative Explanations
Complex tickets may induce more pairing (reverse causality, `[Speculative]`), and unadjusted totals omit headcount denominators (`[Moderate]`).

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier | Confidence Tag | Key Falsifier / Condition |
| :--- | :--- | :--- | :--- | :--- |
| Full-sample r=0.98 is a T12 leverage artifact | Statistics | Python audit (Tier 1) | `[Strong]` | Replication across comparable teams |
| Reverse causality explains negative slope | Causal Inference | Missing covariates (Tier 3) | `[Speculative]` | Controlled crossover pilot |

## 7. Limitations & Open Questions
- **Limitations:** Small sample ($n=12$) without headcount normalization or severity weights.
"""

SAMPLE_CHARTS = [
    {
        "id": "corr_sens",
        "title": "Correlation Sensitivity (Full vs. Clean)",
        "caption": "Excluding T12 flips Pearson r from +0.98 to -0.77.",
        "source": "Internal 12-team CSV; appendix/analysis.py.",
        "type": "bar",
        "groups": ["Pearson r", "Spearman rho"],
        "series": [
            {"name": "Full (n=12)", "values": [0.9804, -0.3612]},
            {"name": "Clean (n=11)", "values": [-0.7742, -0.7791]},
        ],
    },
    {
        "id": "extra_scatter",
        "title": "Unplaced Scatter Goes to Additional Figures",
        "type": "scatter",
        "x": {"label": "Pair Hours"},
        "y": {"label": "Bugs Fixed"},
        "series": [{"name": "Teams", "points": [[2, 14], [7, 12], [45, 88]]}],
    },
]


class TestRenderReport(unittest.TestCase):
    def test_working_paper_layout_inline_figures_and_no_binary_bloat(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            appendix = root / "appendix"
            data_dir = appendix / "data"
            data_dir.mkdir(parents=True)
            (appendix / "analysis.py").write_text("print('<script>alert(1)</script>')\n", encoding="utf-8")
            (appendix / "output.txt").write_text("r=0.9804\n", encoding="utf-8")
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of\n"
                "C1,Internal Team CSV,https://example.org/data,Tier 2,2026-11-20,2026-11\n",
                encoding="utf-8",
            )
            # Simulate large binary / raw data files that MUST NOT be embedded in HTML
            (data_dir / "raw_dump.xlsx").write_bytes(b"PK\x03\x04" + b"X" * 400_000)
            (appendix / "huge_log.txt").write_text("A" * 300_000, encoding="utf-8")

            html = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS, appendix_dir=appendix)

            # Paper-style typography, print CSS, small-caps tags, no dashboard pills
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("Georgia, serif", html)
            self.assertIn("@media print", html)
            self.assertIn("@page", html)
            self.assertIn("font-variant: small-caps", html)
            self.assertNotIn("toggleTheme()", html)

            # Inline figure placement for {{fig:corr_sens}} + Additional Figures for unplaced chart
            self.assertNotIn("{{fig:corr_sens}}", html)
            self.assertIn("Figure 1.", html)
            self.assertIn("Correlation Sensitivity (Full vs. Clean)", html)
            self.assertIn("Additional Figures", html)
            self.assertIn("Figure 2.", html)

            # Auto-generated References section from sources.csv
            self.assertIn("References", html)
            self.assertIn("Internal Team CSV", html)

            # Safe HTML escaping + NO binary or >200KB bloat embedded!
            self.assertNotIn("<script>alert(1)</script>", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertNotIn("PK\x03\x04", html)
            self.assertLess(len(html.encode("utf-8")), 120_000, "HTML must not embed raw data/binaries")

            # Passes HTML structural validator
            out_html = root / "report.html"
            out_html.write_text(html, encoding="utf-8")
            self.assertEqual(validate_report.validate_html(out_html), [])

    def test_cli_renders_html_file(self) -> None:
        script_path = SCRIPTS_DIR / "render_report.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            md_path = root / "report.md"
            charts_path = root / "charts.json"
            out_path = root / "report.html"
            md_path.write_text(SAMPLE_MD, encoding="utf-8")
            charts_path.write_text(json.dumps(SAMPLE_CHARTS), encoding="utf-8")

            res = subprocess.run(
                [sys.executable, str(script_path), str(md_path), "--out", str(out_path), "--charts", str(charts_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertTrue(out_path.is_file())
            self.assertEqual(validate_report.validate_html(out_path), [])


if __name__ == "__main__":
    unittest.main()
