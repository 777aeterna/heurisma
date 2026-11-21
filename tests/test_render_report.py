from __future__ import annotations

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
                [sys.executable, "-B", str(script_path), str(md_path), "--out", str(out_path), "--charts", str(charts_path)],
                capture_output=True,
                text=True, encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertTrue(out_path.is_file())
            self.assertEqual(validate_report.validate_html(out_path), [])

    def test_intext_citations_linked_and_references_ordered_by_appearance(self) -> None:
        md = SAMPLE_MD.replace(
            "Removing `T12` drops Pearson r from `+0.9804` to `-0.7742` (`[Strong]`), while full-sample Spearman rank correlation is already negative (`-0.3612`, `[Strong]`).",
            "Removing `T12` drops Pearson r [@C2] while Spearman confirms the reversal [@C1; @C2] (`[Strong]`).",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            appendix = Path(tmpdir) / "appendix"
            appendix.mkdir()
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of\n"
                "C1,First CSV Source,https://example.org/c1,Tier 1,2026-11-20,2026-11\n"
                "C2,Second CSV Source,https://example.org/c2,Tier 1,2026-11-20,2026-11\n",
                encoding="utf-8",
            )
            rendered = render_report.render_html(md, charts=SAMPLE_CHARTS, appendix_dir=appendix)
            self.assertNotIn("[@C2]", rendered)
            self.assertNotIn("[@C1", rendered)
            self.assertIn('<a href="#ref-1">[1]</a>', rendered)
            self.assertIn('<a href="#ref-2">[2]</a>', rendered)
            # C2 appeared first -> must be ref-1 before C1 (ref-2) in References
            pos_c2 = rendered.find('id="ref-1"')
            pos_c1 = rendered.find('id="ref-2"')
            self.assertGreater(pos_c2, 0)
            self.assertGreater(pos_c1, pos_c2)
            self.assertLess(rendered.find("Second CSV Source"), rendered.find("First CSV Source"))

    def test_spanish_localization_zero_english_chrome_and_lang_es(self) -> None:
        es_md = """# Estudio del Dólar en Argentina

> **Fecha de corte:** 2026-11-20 | **Nivel:** Nivel 2

## 1. Resumen ejecutivo
- **Veredicto calibrado:** `[Moderada]` El tipo de cambio real se apreció frente a su media histórica (`[Fuerte]`).
- **Qué cambiaría esta conclusión:** Una reversión de flujos externos.

## 2. Encuadre e hipótesis
- **Hipótesis:**
  - $H_0$: No hay apreciación sostenida.
  - $H_1$: Existe apreciación sostenida.

## 3. Metodología y estándares de evidencia
- **Método:** Análisis reproducible en Python.

## 4. Hallazgos
La mediana proyectada muestra convergencia [@C1] (`[Moderada]`).

{{fig:fan_es}}

## 5. Contraevidencia y explicaciones alternativas
La productividad sectorial puede elevar el tipo de cambio de equilibrio (`[Preliminar]`).

## 6. Matriz de afirmaciones y evidencia
| Afirmación | Disciplina | Evidencia | Confianza | Falsador |
| :- | :- | :- | :- | :- |
| Apreciación real | Macro | BCRA (Tier 1) | `[Fuerte]` | Cambio de régimen |
| Convergencia 2027 | Proyección | Modelo (Tier 2) | `[Moderada]` | Shock externo |

## 7. Limitaciones y preguntas abiertas
- **Limitaciones:** Horizonte corto.
"""
        es_charts = [
            {
                "id": "fan_es",
                "type": "fan",
                "title": "Proyección del dólar",
                "caption": "Bandas de simulación.",
                "source": "BCRA",
                "x": {"type": "date"},
                "y": {"label": "ARS/USD"},
                "quantiles": {
                    "p10": [["2026-12", 1450], ["2027-12", 1600]],
                    "p25": [["2026-12", 1500], ["2027-12", 1800]],
                    "p50": [["2026-12", 1550], ["2027-12", 2050]],
                    "p75": [["2026-12", 1620], ["2027-12", 2350]],
                    "p90": [["2026-12", 1700], ["2027-12", 2800]],
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            appendix = Path(tmpdir) / "appendix"
            appendix.mkdir()
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of\n"
                "C1,BCRA Serie A3500,https://api.bcra.gob.ar,Tier 1,2026-11-20,2026-11\n",
                encoding="utf-8",
            )
            (appendix / "output.txt").write_text("ok\n", encoding="utf-8")
            rendered = render_report.render_html(es_md, charts=es_charts, appendix_dir=appendix)
            self.assertIn('<html lang="es">', rendered)
            self.assertIn("Figura 1.", rendered)
            self.assertIn("Nota:", rendered)
            self.assertIn("Fuente:", rendered)
            self.assertIn("Resumen", rendered)
            self.assertIn("Referencias", rendered)
            self.assertIn("Mediana (P50)", rendered)
            for leaked in ("Figure ", "Note:", "Source:", "Abstract", "References", "Median (P50)"):
                self.assertNotIn(leaked, rendered, f"English chrome leaked into Spanish HTML: {leaked!r}")

    def test_latex_math_converted_without_breaking_currency(self) -> None:
        md = SAMPLE_MD.replace(
            "Removing `T12` drops Pearson r from `+0.9804` to `-0.7742` (`[Strong]`), while full-sample Spearman rank correlation is already negative (`-0.3612`, `[Strong]`).",
            "Testing $H_0$ vs $H_1$ with $x^2$, $\\Delta \\le 5$, and $r = -0.77$ at prices $1.563 and $1,200–$1,400 ($1,200 to $1,400).",
        )
        rendered = render_report.render_html(md, charts=SAMPLE_CHARTS)
        self.assertIn("H<sub>0</sub>", rendered)
        self.assertIn("H<sub>1</sub>", rendered)
        self.assertIn("x<sup>2</sup>", rendered)
        self.assertIn("Δ ≤ 5", rendered)
        self.assertNotIn("$H_0$", rendered)
        self.assertNotIn("$x^2$", rendered)
        # Currency MUST remain intact
        self.assertIn("$1.563", rendered)
        self.assertIn("$1,200–$1,400", rendered)
        self.assertIn("$1,200 to $1,400", rendered)

    def test_nested_lists_render_nested_ul(self) -> None:
        rendered = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS)
        # SAMPLE_MD has 2-space indented - $H_0$ and - $H_1$ under - **Hypotheses:**
        self.assertIn("<ul>\n<li>", rendered)
        self.assertRegex(rendered, r"<li><strong>Hypotheses:</strong>\s*<ul>\s*<li>")

    def test_abstract_not_duplicated_and_no_credit_flag(self) -> None:
        rendered = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS, no_credit=True)
        # Verdict promoted to Abstract must appear only ONCE (not duplicated as first bullet of §1)
        self.assertEqual(rendered.count("outlier artifact driven by"), 1)
        self.assertNotIn("Prepared with Heurisma", rendered)

    def test_numbers_json_placeholder_substitution(self) -> None:
        md = SAMPLE_MD.replace("`-0.7742`", "`{{num:clean_r}}`")
        with tempfile.TemporaryDirectory() as tmpdir:
            appendix = Path(tmpdir) / "appendix"
            appendix.mkdir()
            (appendix / "numbers.json").write_text(json.dumps({"clean_r": "-0.7742"}), encoding="utf-8")
            rendered = render_report.render_html(md, charts=SAMPLE_CHARTS, appendix_dir=appendix)
            self.assertNotIn("{{num:clean_r}}", rendered)
            self.assertIn("-0.7742", rendered)


    # ---- v0.5.0 Phase 1: W3 source hash -------------------------------------------------------
    def _render_cli(self, root: Path, extra: list[str] | None = None) -> Path:
        out_path = root / "report.html"
        res = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS_DIR / "render_report.py"), str(root / "report.md"), "--out", str(out_path),
             "--charts", str(root / "charts.json"), "--appendix", str(root / "appendix")] + (extra or []),
            capture_output=True,
            text=True, encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        return out_path

    def _seed_report_dir(self, root: Path) -> None:
        (root / "appendix").mkdir()
        (root / "appendix" / "README.md").write_text("original readme\n", encoding="utf-8")
        (root / "report.md").write_text(SAMPLE_MD, encoding="utf-8")
        (root / "charts.json").write_text(json.dumps(SAMPLE_CHARTS), encoding="utf-8")

    def test_render_embeds_source_hash(self) -> None:
        import re

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_report_dir(root)
            html = self._render_cli(root).read_text(encoding="utf-8")
            m = re.search(r"<!-- heurisma-sources: sha256:([0-9a-f]{12}) -->", html)
            self.assertIsNotNone(m, msg="source hash comment missing")
            h1 = render_report.compute_source_hash(
                root / "report.md", root / "charts.json", None, root / "appendix"
            )
            self.assertEqual(h1, m.group(1))
            (root / "appendix" / "README.md").write_text("edited readme\n", encoding="utf-8")
            h2 = render_report.compute_source_hash(
                root / "report.md", root / "charts.json", None, root / "appendix"
            )
            self.assertNotEqual(h1, h2)

    def test_source_hash_ignores_pycache_and_report_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_report_dir(root)
            h1 = render_report.compute_source_hash(root / "report.md", root / "charts.json", None, root / "appendix")
            (root / "appendix" / "__pycache__").mkdir()
            (root / "appendix" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
            (root / "report.html").write_text("<html></html>", encoding="utf-8")
            h2 = render_report.compute_source_hash(root / "report.md", root / "charts.json", None, root / "appendix")
            self.assertEqual(h1, h2)


    # ---- v0.5.0 Phase 2: X1 headings, X2/X3 notation, X4/X5 local paths ------------------------
    def test_h4_h5_headings_render(self) -> None:
        md = SAMPLE_MD.replace("## 4. Findings", "## 4. Findings\n\n#### 4.1.1 By regime\n\n##### Detail level\n\nText.", 1)
        rendered = render_report.render_html(md, charts=SAMPLE_CHARTS)
        self.assertIn("<h4>4.1.1 By regime</h4>", rendered)
        self.assertIn("<h5>Detail level</h5>", rendered)
        self.assertNotIn("#### 4.1.1", rendered)
        self.assertNotIn("##### Detail", rendered)

    def test_scientific_notation_positive_cases(self) -> None:
        f = render_report._apply_scientific_notation
        self.assertEqual(f("N^(\u22121/2)"), "N<sup>\u22121/2</sup>")
        self.assertEqual(f("amplitude^0.50"), "amplitude<sup>0.50</sup>")
        self.assertEqual(f("x^-2 here"), "x<sup>\u22122</sup> here")
        self.assertEqual(f("rate 3e-08 per step"), "rate 3\u00d710<sup>\u22128</sup> per step")
        self.assertEqual(f("1.5e+10 Hz"), "1.5\u00d710<sup>10</sup> Hz")

    def test_scientific_notation_before_sentence_period_and_comma(self) -> None:
        f = render_report._apply_scientific_notation
        self.assertEqual(f("p = 3e-08."), "p = 3\u00d710<sup>\u22128</sup>.")
        self.assertEqual(f("(1.5e-3, 2e-8)."), "(1.5\u00d710<sup>\u22123</sup>, 2\u00d710<sup>\u22128</sup>).")
        self.assertEqual(f("version 1.2.3e4.5"), "version 1.2.3e4.5")

    def test_unresolved_num_marker_warns_on_stderr_but_still_renders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            md = Path(tmpdir) / "report.md"
            md.write_text("# T\n\nValue {{num:no_existe}} here.\n", encoding="utf-8")
            out = Path(tmpdir) / "report.html"
            res = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS_DIR / "render_report.py"), str(md), "--out", str(out)],
                capture_output=True,
                text=True, encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertIn("no_existe", res.stderr)
            self.assertIn("unresolved", res.stderr.lower())

    def test_marker_text_inside_embedded_appendix_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "appendix" / "gates").mkdir(parents=True)
            (root / "appendix" / "gates" / "qa.md").write_text("3 PASS - uses {{num:key}} markers\n", encoding="utf-8")
            md = root / "report.md"
            md.write_text("# T\n\nPlain text.\n", encoding="utf-8")
            res = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS_DIR / "render_report.py"), str(md), "--out", str(root / "r.html"),
                 "--appendix", str(root / "appendix")],
                capture_output=True,
                text=True, encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertNotIn("unresolved", res.stderr.lower())

    def test_scientific_notation_leaves_paths_urls_code_and_ids_intact(self) -> None:
        f = render_report._apply_scientific_notation
        for untouched in ("a^b/c.py", "see 2026-12 and 3e", "sha 12e5ab99 id", "v1e-x"):
            self.assertEqual(f(untouched), untouched)
        rendered = render_report.render_html(
            SAMPLE_MD.replace("## 4. Findings", "## 4. Findings\n\nCode `x^2` and [link](https://example.org/a^2) and https://example.org/b^3 end.", 1),
            charts=SAMPLE_CHARTS,
        )
        self.assertIn("<code>x^2</code>", rendered)
        self.assertIn("https://example.org/a^2", rendered)
        self.assertIn("https://example.org/b^3", rendered)
        self.assertNotIn("a<sup>2</sup>", rendered)

    def test_num_marker_uses_typographic_minus(self) -> None:
        md = SAMPLE_MD.replace("## 4. Findings", "## 4. Findings\n\nGap {{num:gap}}, r = {{num:r}}, span {{num:span}}.", 1)
        rendered = render_report.render_html(
            md, charts=SAMPLE_CHARTS, numbers={"gap": "-16,6%", "r": "-0,40", "span": "2026-12"}
        )
        self.assertIn("\u221216,6%", rendered)
        self.assertIn("r = \u22120,40", rendered)
        self.assertIn("2026-12", rendered)

    def _local_sources_dir(self, root: Path, title: str) -> Path:
        appendix = root / "appendix"
        appendix.mkdir()
        (appendix / "sources.csv").write_text(
            "claim_id,source_title,url,tier,accessed_date,data_as_of\n"
            f'C1,"{title}",file:///home/alice/studies/fx/a3500.csv,Tier 2,2026-11-20,2026-11\n',
            encoding="utf-8",
        )
        return appendix

    def test_references_hide_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            appendix = self._local_sources_dir(Path(tmpdir), "Serie propia (local file, sha256 abc123def456)")
            rendered = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS, appendix_dir=appendix)
            self.assertNotIn("/home/", rendered)
            self.assertIn("a3500.csv", rendered)
            self.assertIn("abc123def456", rendered)

    def test_references_handle_schemeless_relative_local_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            appendix = Path(tmpdir) / "appendix"
            appendix.mkdir()
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of\n"
                'C1,"Serie propia (local file, sha256 abc123def456)",appendix/data/a%20b.csv,Tier 2,2026-11-20,2026-11\n',
                encoding="utf-8",
            )
            rendered = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS, appendix_dir=appendix)
            refs = rendered.split('<section class="references">', 1)[1].split("</section>", 1)[0]
            self.assertIn("<code>a b.csv</code>", refs)
            self.assertIn("abc123def456", refs)
            self.assertNotIn("appendix/data", refs)

    def test_gate_traces_are_embedded_in_appendices(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            appendix = Path(tmpdir) / "appendix"
            (appendix / "gates").mkdir(parents=True)
            (appendix / "gates" / "qa.md").write_text("QA: PASS\n1 PASS - validator clean\n", encoding="utf-8")
            rendered = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS, appendix_dir=appendix)
            self.assertIn("<code>appendix/gates/qa.md</code>", rendered)
            self.assertIn("QA: PASS", rendered)
            self.assertNotIn("external artifact", rendered.split('class="appendices"', 1)[1].lower())

    def test_self_review_gate_is_labelled_in_the_appendix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            appendix = Path(tmpdir) / "appendix"
            (appendix / "gates").mkdir(parents=True)
            (appendix / "gates" / "qa.md").write_text("MODE: self-review\nQA: PASS\n", encoding="utf-8")
            (appendix / "gates" / "source_verifier.md").write_text("MODE: subagent\nok\n", encoding="utf-8")
            en = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS, appendix_dir=appendix)
            self.assertIn("<code>appendix/gates/qa.md</code> — self-review, not independent", en)
            self.assertNotIn("source_verifier.md</code> — self-review", en)
            es = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS, appendix_dir=appendix, lang="es")
            self.assertIn("— auto-revisión, no independiente", es)

    def test_local_copy_label_localized_es(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            appendix = self._local_sources_dir(Path(tmpdir), "Serie propia (local file, sha256 abc123def456)")
            rendered = render_report.render_html(SAMPLE_MD, charts=SAMPLE_CHARTS, appendix_dir=appendix, lang="es")
            refs = rendered.split('<section class="references">', 1)[1].split("</section>", 1)[0]
            self.assertIn("archivo local", refs)
            self.assertNotIn("local file", refs)
            self.assertIn("abc123def456", refs)


    def test_numeric_table_cells_use_typographic_minus(self) -> None:
        md = SAMPLE_MD.replace(
            "## 4. Findings",
            "## 4. Findings\n\n| Group | Delta |\n| :- | -: |\n| A | -0.74% |\n| B | 2026-12 |",
            1,
        )
        rendered = render_report.render_html(md, charts=SAMPLE_CHARTS)
        self.assertIn('<td class="num">\u22120.74%</td>', rendered)
        self.assertIn("<td>2026-12</td>", rendered)


if __name__ == "__main__":
    unittest.main()
