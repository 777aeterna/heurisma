from __future__ import annotations

import subprocess
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_report  # noqa: E402


VALID_REPORT = """# Empirical & Policy Evaluation of Coastal PHA Packaging Mandate

## 1. Executive Summary
- **Calibrated Verdict:** `[Moderate]` A blanket 3-year switch to PHA packaging paired with a $0.35 surcharge is unlikely to achieve a 60% reduction in total single-use packaging waste without reusable infrastructure, though pure marine-certified thin-film PHA reduces persistent secondary microplastics (`[Strong]`).
- **Key Takeaways:** Cold seawater slows enzymatic kinetics (`[Strong]`); vendor margin impact depends on fee retention (`[Moderate]`).

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** Marine Polymer Chemistry + Behavioral Economics + Supply-Chain Engineering | Level 1
- **Research Question:** Does a municipal PHA mandate plus $0.35 plastic surcharge reduce marine microplastics and remain viable for small food vendors within 36 months?
- **Hypotheses:**
  - $H_0$: The policy fails to reach 60% waste reduction or compresses small-vendor margins below viability due to resin premiums and cold-water kinetic limits.
  - $H_1$: The policy cuts marine microplastic leakage by >=60% while remaining economically neutral for small vendors.
- **Refutation Criteria:** $H_1$ is falsified if cold-water (<10 C) thick-walled PHA persistence exceeds 24 months or if unsubsidized packaging cost increases exceed 50% of small-vendor net margins.

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:** Marine field degradation trials > ASTM D6691 30 C lab tests; municipal natural experiments > theoretical price elasticity.
- **Analytical / Computational Method:** Multi-disciplinary evidence synthesis across polymer degradation kinetics, municipal fee outcomes, and foodservice unit economics.

## 4. Findings
Pure PHA films mineralize in warm aerobic seawater (`[Strong]`), whereas thick thermoformed containers in <10 C coastal water or anoxic sediment degrade orders of magnitude slower (`[Moderate]`). Global PHA capacity creates supply bottlenecks (`[Preliminary]`), and resin cost premiums threaten thin small-vendor margins unless surcharge revenue is retained (`[Moderate]`).

## 5. Counter-Evidence & Alternative Explanations
Thin-film PHA items avoid centuries-long microplastic persistence even when fragmented (`[Strong]`), and cup-surcharge trials achieved >70% switching when paired with accessible deposit-return networks (`[Moderate]`).

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier | Confidence Tag | Key Falsifier / Condition |
| :--- | :--- | :--- | :--- | :--- |
| Thin-film PHA mineralizes enzymatically in aerobic seawater | Marine Chemistry | Peer-reviewed field & lab meta-analyses [@C1] (Tier 1) | `[Strong]` | Blending with non-marine-degradable PLA/PBAT |
| Unretained $0.35 surcharge compresses small vendor profit margins | Micro-Economics | Foodservice margin data & resin spot pricing (Tier 2) | `[Moderate]` | Municipal bulk-purchasing subsidy or vendor fee retention |

## 7. Limitations & Open Questions
- **Methodological & Data Limitations:** Limited multi-year cold-water benthic ecotoxicity datasets for finished commercial PHA blends.
- **Actionable Next Steps / Experiments:** Mandate marine certification on finished items and run a 6-month vendor fee-retention pilot.
"""

SPANISH_REPORT = """# Evaluacion Empirica de Politica de Envases Bioplasticos

## 1. Resumen ejecutivo
- **Veredicto calibrado:** `[Moderada]` La sustitucion obligatoria en 3 anos requiere infraestructura de reutilizacion para cumplir la meta de reduccion total de residuos plasticos, aunque el PHA marino certificado reduce los microplasticos secundarios persistentes en aguas costeras (`[Fuerte]`).
- **Que cambiaria esta conclusion:** Evidencia de campo plurianual en aguas frias que muestre degradacion rapida de envases rigidos junto con paridad de costos para pequenos comercios.

## 2. Encuadre e hipotesis
- **Disciplinas y nivel:** Quimica de Polimeros + Economia Conductual | Nivel 1
- **Pregunta de investigacion:** Reduce la politica los microplasticos marinos sin quebrar a los pequenos comercios?
- **Hipotesis:**
  - $H_0$: La politica no alcanza la meta o comprime los margenes de pequenos vendedores.
  - $H_1$: La politica reduce >=60% los residuos plasticos sin dano economico neto.
- **Criterios de refutacion:** $H_1$ se refuta si el costo adicional supera el 50% del margen neto.

## 3. Metodologia y estandares de evidencia
- **Jerarquia de evidencia:** Ensayos marinos de campo (Tier 1) > pruebas de laboratorio (Tier 2) > notas de prensa (Tier 3).

## 4. Hallazgos
Los filmes finos de PHA mineralizan en agua marina aerobica mediante degradacion enzimatica superficial (`[Fuerte]`), pero los envases rigidos en aguas frias menores a diez grados centigrados degradan mucho mas lento (`[Moderada]`). La capacidad global limitada de PHA y las primas de costo presionan los margenes comerciales (`[Preliminar]`).

## 5. Contraevidencia y explicaciones alternativas
Los ensayos europeos con infraestructura de retorno y depositos lograron mas del setenta por ciento de adopcion de reutilizables (`[Moderada]`).

## 6. Matriz de afirmaciones y evidencia
| Afirmacion | Disciplina | Evidencia y Tier | Confianza | Falsador clave |
| :- | :- | :- | :- | :- |
| El PHA fino mineraliza en agua marina | Quimica Marina | Metaanalisis revisados por pares (Tier 1) | `[Fuerte]` | Mezcla con PLA o PBAT |
| El recargo no retenido afecta margenes | Economia | Datos sectoriales (Tier 2) | `[Moderada]` | Subsidio o retencion del recargo |

## 7. Limitaciones y preguntas abiertas
- **Limitaciones:** Escasos datos plurianuales en aguas frias para mezclas comerciales.
- **Proximos pasos:** Piloto de 6 meses con retencion del recargo.
"""


GOOD_SOURCE_VERIFIER = """# Source-verification gate
1. PASS — read vs. registered: C1 is titled as data and its retrieval is logged in download_log.csv.
2. PASS — own computation: no row points at appendix code; nothing to reclassify.
3. PASS — tag vs. weakest source: the only [Strong] row cites C1, a Tier 1 dataset that supports it.
4. PASS — every [@id] exists in sources.csv and every source row is cited in Section 4.
5. PASS — no data limitation, Deferred row or tag downgrade is declared in this draft.
6. PASS — no local files in appendix/data/; nothing to register.
7. PASS — Level 2 draft: no reviewer-introduced facts.
PROPOSED data_attempts.csv ROWS: none
SOURCE-VERIFIER: PASS
"""

GOOD_REVIEWER = """1. [1] Section 4 marine claim — tagged [Moderate] on two sites — add a third site or keep the tag.
2. [3] Section 4 kinetics — no temperature control — rerun with the Q10 sensitivity.
Coverage:
1. Over-calibrated claims — 1 item
2. Unattempted data shortcuts — none found
3. Missing counter-evidence and controls — 1 item
4. Interdisciplinary and forecasting flaws — none found
5. Decisions inside the noise — none found
6. Provenance contradictions — none found
MOST DAMAGING: 2 — the kinetics result has no temperature control and drives the verdict.
"""


def _qa_text(status: str = "PASS", failed: tuple[int, ...] = ()) -> str:
    lines = [f"QA: {status}" + (f" ({len(failed)} checks failed)" if failed else "")]
    for n in range(1, 9):
        verdict = "FAIL" if n in failed else "PASS"
        lines.append(f"{n} {verdict} — evidence for check {n}: command run and its output recorded here in full.")
    lines.append(f"FAIL count: {len(failed)}")
    return "\n".join(lines) + "\n"


def _seed_gates(root: Path, qa: str | None = None) -> None:
    """Write complete appendix/gates/ traces in the shape the agent prompts fix (v0.6.1 markers + v0.7.0 header).

    The header binds each gate to the files present now; call ``_restamp_gates(root)`` after changing them.
    """
    gates = root / "appendix" / "gates"
    gates.mkdir(parents=True, exist_ok=True)
    (gates / "source_verifier.md").write_text(GOOD_SOURCE_VERIFIER, encoding="utf-8")
    (gates / "reviewer.md").write_text(GOOD_REVIEWER, encoding="utf-8")
    (gates / "qa.md").write_text(qa if qa is not None else _qa_text(), encoding="utf-8")
    _restamp_gates(root)


def _restamp_gates(root: Path) -> None:
    """(Re)write the v0.7.0 binding header of every gate: MODE, REVIEWED-SHA256 of the current files, quotes."""
    analysis = root / "appendix" / "analysis.py"
    if not analysis.is_file():
        analysis.parent.mkdir(parents=True, exist_ok=True)
        analysis.write_text("print('ok')\n", encoding="utf-8")
    first = analysis.read_text(encoding="utf-8").splitlines()[0]
    for g in sorted((root / "appendix" / "gates").glob("*.md")):
        body = "\n".join(
            ln for ln in g.read_text(encoding="utf-8").splitlines()
            if not re.match(r"^(MODE|REVIEWED-SHA256|REVIEWED-UTC|QUOTE):", ln)
        ).lstrip("\n")
        head = [
            "MODE: subagent",
            f"REVIEWED-SHA256: {validate_report.gate_hash(root, g.stem)}",
            "REVIEWED-UTC: 2026-11-20T12:00:00Z",
            f'QUOTE: appendix/analysis.py:1: "{first[:5]}"',
            f'QUOTE: appendix/analysis.py:1: "{first}"',
        ]
        g.write_text("\n".join(head) + "\n\n" + body, encoding="utf-8")


def _seed_charts(root: Path) -> str:
    """Write a minimal root charts.json and return the {{fig:}} marker line that places it."""
    import json

    (root / "charts.json").write_text(
        json.dumps([{"id": "fig_main", "type": "bar", "title": "Main", "series": [{"label": "A", "value": 1}]}]),
        encoding="utf-8",
    )
    return "{{fig:fig_main}}"


def _with_fig(report: str, marker: str) -> str:
    return report.replace("## 5. Counter-Evidence", marker + "\n\n## 5. Counter-Evidence", 1)


class TestValidateReport(unittest.TestCase):
    def test_valid_report_passes(self) -> None:
        errors = validate_report.validate_report(VALID_REPORT)
        self.assertEqual(errors, [])

    def test_empty_report_fails(self) -> None:
        errors = validate_report.validate_report("   \n  ")
        self.assertTrue(len(errors) > 0)

    def test_missing_counter_evidence_and_limitations_fails(self) -> None:
        broken = VALID_REPORT.replace("## 5. Counter-Evidence & Alternative Explanations", "## 5. Other Notes")
        broken = broken.replace("## 7. Limitations & Open Questions", "## 7. Conclusion")
        errors = validate_report.validate_report(broken)
        self.assertTrue(any("Counter-Evidence" in err for err in errors))
        self.assertTrue(any("Limitations" in err for err in errors))

    def test_missing_epistemic_calibration_tags_fails(self) -> None:
        uncalibrated = VALID_REPORT
        for tag in ("[Strong]", "[Moderate]", "[Preliminary]", "[Speculative]"):
            uncalibrated = uncalibrated.replace(tag, "")
        errors = validate_report.validate_report(uncalibrated)
        self.assertTrue(any("epistemic" in err.lower() or "calibration" in err.lower() or "tag" in err.lower() for err in errors))

    def test_stub_14_line_report_fails(self) -> None:
        stub = """# Stub
## 1. Executive Summary
[Strong]
## 2. Framing & Hypotheses
H0 H1
## 3. Methodology & Evidence Standards
x
## 4. Findings
x
## 5. Counter-Evidence & Alternative Explanations
x
## 6. Claim-Evidence Matrix
| a |
|---|
| b |
## 7. Limitations & Open Questions
x
"""
        errors = validate_report.validate_report(stub)
        self.assertTrue(len(errors) > 0)

    def test_six_word_filler_stub_fails(self) -> None:
        """Audit v0.2: 6 nonsense words per section + 1-row matrix must FAIL substance gates."""
        filler = """# Filler Report
## 1. Executive Summary
One two three four five `[Moderate]`
## 2. Framing & Hypotheses
H0 baseline and H1 alternative stated here
## 3. Methodology & Evidence Standards
One two three four five six
## 4. Findings
One two three four five `[Moderate]`
## 5. Counter-Evidence & Alternative Explanations
One two three four five six
## 6. Claim-Evidence Matrix
| Claim | Axis | Evidence | Confidence |
| :--- | :--- | :--- | :--- |
| One claim | Econ | Study (Tier 2) | `[Moderate]` |
## 7. Limitations & Open Questions
One two three four five six
"""
        errors = validate_report.validate_report(filler)
        self.assertTrue(any("Executive Summary" in e or "Findings" in e or "at least 2" in e.lower() for e in errors), msg=errors)

    def test_strong_tag_on_tier3_source_fails(self) -> None:
        bad = VALID_REPORT.replace(
            "| Thin-film PHA mineralizes enzymatically in aerobic seawater | Marine Chemistry | Peer-reviewed field & lab meta-analyses [@C1] (Tier 1) | `[Strong]` | Blending with non-marine-degradable PLA/PBAT |",
            "| Forecast hits target | Economics | Press release roadmap (Tier 3) | `[Strong]` | Delay |",
        )
        errors = validate_report.validate_report(bad)
        self.assertTrue(any("strong" in e.lower() for e in errors), msg=errors)

    def test_strong_on_press_without_tier3_literal_fails(self) -> None:
        """Audit v0.2: [Strong] paired with 'nota de prensa' (without literal 'Tier 3') must FAIL."""
        bad = VALID_REPORT.replace(
            "| Thin-film PHA mineralizes enzymatically in aerobic seawater | Marine Chemistry | Peer-reviewed field & lab meta-analyses [@C1] (Tier 1) | `[Strong]` | Blending with non-marine-degradable PLA/PBAT |",
            "| Forecast hits target | Economics | Nota de prensa del diario local | `[Strong]` | Delay |",
        )
        errors = validate_report.validate_report(bad)
        self.assertTrue(any("strong" in e.lower() and ("press" in e.lower() or "tier 3" in e.lower()) for e in errors), msg=errors)

    def test_hypotheses_only_outside_section2_fails(self) -> None:
        sec2_stripped = VALID_REPORT.replace("$H_0$:", "Baseline:").replace("$H_1$:", "Target:").replace("$H_1$", "Target")
        sec2_stripped += "\nNote: H0 and H1 mentioned only in section 7.\n"
        errors = validate_report.validate_report(sec2_stripped)
        self.assertTrue(any("section 2" in e.lower() or "framing" in e.lower() for e in errors), msg=errors)

    def test_matrix_row_missing_calibration_tag_fails(self) -> None:
        bad = VALID_REPORT.replace(
            "| Unretained $0.35 surcharge compresses small vendor profit margins | Micro-Economics | Foodservice margin data & resin spot pricing (Tier 2) | `[Moderate]` | Municipal bulk-purchasing subsidy or vendor fee retention |",
            "| Unretained $0.35 surcharge compresses small vendor profit margins | Micro-Economics | Foodservice margin data & resin spot pricing (Tier 2) | none | Municipal bulk-purchasing subsidy or vendor fee retention |",
        )
        errors = validate_report.validate_report(bad)
        self.assertTrue(any("row" in e.lower() and "tag" in e.lower() for e in errors), msg=errors)

    def test_single_dash_markdown_separator_and_spanish_tags_pass(self) -> None:
        """Audit v0.2: Valid Markdown '| :- |' separators and Spanish tags ([Fuerte], [Moderada]) must PASS."""
        errors = validate_report.validate_report(SPANISH_REPORT)
        self.assertEqual(errors, [], msg=errors)

    def test_heading_inside_fenced_code_block_ignored(self) -> None:
        parts = VALID_REPORT.split("## 7. Limitations & Open Questions")
        fenced = parts[0] + "\n```markdown\n## 7. Limitations & Open Questions\n- inside code block\n```\n"
        errors = validate_report.validate_report(fenced)
        self.assertTrue(any("Missing required section" in e and "Limitations" in e for e in errors), msg=errors)
        self.assertFalse(any("out of order" in e.lower() for e in errors), msg=errors)

    def test_backticked_reviewer2_action_and_deferred_check(self) -> None:
        """Audit v0.2: Backticked `Fixed` passes; `Deferred` requires data_attempts.csv or Data Attempts table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import local_data

            root = Path(tmpdir)
            appendix = root / "appendix"
            appendix.mkdir()
            local_data.preregister(
                appendix,
                {"H0": "No mineralization difference.", "H1": "Marine mineralization differs from soil."},
                "Compare marine and soil mineralization.",
            )
            (appendix / "analysis.py").write_text("print('ok')\n", encoding="utf-8")
            (appendix / "output.txt").write_text("ok\n", encoding="utf-8")
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\nC1,Study,https://example.org,Tier 1,2026-11-20,2025-12,literature\n",
                encoding="utf-8",
            )
            cited_valid = _with_fig(
                VALID_REPORT.replace("Pure PHA films mineralize", "Pure PHA films mineralize [@C1]"), _seed_charts(root)
            )

            with_backtick_fixed = cited_valid.replace(
                "## 6. Claim-Evidence Matrix",
                """### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | Cold water kinetics missing | `Fixed` | Added Q10 sensitivity in appendix/analysis.py |
| 2 | Kinetics without temperature control | `Fixed` | Q10 sensitivity rerun in appendix/analysis.py |

## 6. Claim-Evidence Matrix""",
            )
            _seed_gates(root)
            self.assertEqual(validate_report.validate_report(with_backtick_fixed, level=3, report_dir=root), [])

            with_deferred_no_log = cited_valid.replace(
                "## 6. Claim-Evidence Matrix",
                """### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | Missing proprietary customs series | `Deferred` | Unavailable |
| 2 | Kinetics without temperature control | `Fixed` | Q10 sensitivity rerun in appendix/analysis.py |

## 6. Claim-Evidence Matrix""",
            )
            errs_missing_log = validate_report.validate_report(with_deferred_no_log, level=3, report_dir=root)
            self.assertTrue(any("data_attempts" in e.lower() or "attempt" in e.lower() for e in errs_missing_log), msg=errs_missing_log)

            (appendix / "data_attempts.csv").write_text(
                "target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used,attempted_utc\n"
                "customs,Customs API,https://api.example.org,failed,HTTP 403,limitation,2026-11-20T10:00:00Z\n",
                encoding="utf-8",
            )
            _restamp_gates(root)
            self.assertEqual(validate_report.validate_report(with_deferred_no_log, level=3, report_dir=root), [])

    def test_html_validation_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = Path(tmpdir) / "report.html"
            self.assertTrue(len(validate_report.validate_html(html_file)) > 0)
            full_html = "<!DOCTYPE html><html><body>" + "".join(
                f"<h2>{i}. {name}</h2>"
                for i, name in enumerate(
                    [
                        "Executive Summary",
                        "Framing & Hypotheses",
                        "Methodology & Evidence Standards",
                        "Findings",
                        "Counter-Evidence & Alternative Explanations",
                        "Claim-Evidence Matrix",
                        "Limitations & Open Questions",
                    ],
                    start=1,
                )
            ) + "</body></html>"
            html_file.write_text(full_html, encoding="utf-8")
            self.assertEqual(validate_report.validate_html(html_file), [])

    def test_cli_exit_codes(self) -> None:
        script_path = SCRIPTS_DIR / "validate_report.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            valid_file = Path(tmpdir) / "valid.md"
            invalid_file = Path(tmpdir) / "invalid.md"
            valid_file.write_text(VALID_REPORT, encoding="utf-8")
            invalid_file.write_text("# Incomplete Report\nNo sections here.\n", encoding="utf-8")

            res_ok = subprocess.run([sys.executable, "-B", str(script_path), str(valid_file)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res_ok.returncode, 0, msg=res_ok.stderr)

            res_bad = subprocess.run([sys.executable, "-B", str(script_path), str(invalid_file)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res_bad.returncode, 1)

    def test_level2_fails_without_fig_markers_or_unknown_fig_id(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            appendix = root / "appendix"
            appendix.mkdir()
            (appendix / "analysis.py").write_text("print('ok')\n", encoding="utf-8")
            (appendix / "output.txt").write_text("ok 60\n", encoding="utf-8")
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\n"
                "C1,Primary Study,https://example.org/c1,Tier 1,2026-11-20,2026-11,literature\n",
                encoding="utf-8",
            )
            (appendix / "charts.json").write_text(
                json.dumps([{"id": "fig_main", "type": "bar", "title": "Main", "series": [{"label": "A", "value": 1}]}]),
                encoding="utf-8",
            )
            report_with_cite = VALID_REPORT.replace(
                "Pure PHA films mineralize",
                "Pure PHA films mineralize [@C1]",
            )
            # Missing {{fig:...}} when charts.json exists -> MUST fail
            errs_no_fig = validate_report.validate_report(report_with_cite, level=2, report_dir=root)
            self.assertTrue(any("fig" in e.lower() for e in errs_no_fig), msg=errs_no_fig)

            # Unknown {{fig:does_not_exist}} -> MUST fail
            report_bad_fig = report_with_cite.replace("## 5. Counter-Evidence", "{{fig:does_not_exist}}\n\n## 5. Counter-Evidence")
            errs_bad_fig = validate_report.validate_report(report_bad_fig, level=2, report_dir=root)
            self.assertTrue(any("does_not_exist" in e for e in errs_bad_fig), msg=errs_bad_fig)

            # Valid {{fig:fig_main}} -> MUST pass
            report_ok = report_with_cite.replace("## 5. Counter-Evidence", "{{fig:fig_main}}\n\n## 5. Counter-Evidence")
            errs_ok = validate_report.validate_report(report_ok, level=2, report_dir=root)
            self.assertEqual(errs_ok, [], msg=errs_ok)

    def test_level2_fails_without_intext_citations_or_unknown_claim_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            appendix = root / "appendix"
            appendix.mkdir()
            (appendix / "analysis.py").write_text("print('ok')\n", encoding="utf-8")
            (appendix / "output.txt").write_text("ok 60\n", encoding="utf-8")
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\n"
                "C1,Primary Study,https://example.org/c1,Tier 1,2026-11-20,2026-11,literature\n",
                encoding="utf-8",
            )
            # No citations in Section 4 -> MUST fail at Level 2
            errs_no_cite = validate_report.validate_report(VALID_REPORT, level=2, report_dir=root)
            self.assertTrue(any("citation" in e.lower() or "cite" in e.lower() for e in errs_no_cite), msg=errs_no_cite)

            # Unknown [@C99] -> MUST fail
            bad_cite = VALID_REPORT.replace("Pure PHA films mineralize", "Pure PHA films mineralize [@C99]")
            errs_bad_cite = validate_report.validate_report(bad_cite, level=2, report_dir=root)
            self.assertTrue(any("C99" in e for e in errs_bad_cite), msg=errs_bad_cite)

    def test_html_spanish_report_fails_if_english_chrome_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = Path(tmpdir) / "report_es.html"
            leaked_html = (
                '<!DOCTYPE html><html lang="en"><body>'
                '<div class="abstract-label">Abstract</div>'
                "<h2>1. Resumen ejecutivo</h2>"
                "<h2>2. Encuadre e hipótesis</h2>"
                "<h2>3. Metodología y estándares de evidencia</h2>"
                "<h2>4. Hallazgos</h2>"
                '<div class="fig-title"><strong>Figure 1.</strong> Serie</div>'
                "<figcaption><em>Note:</em> Nota</figcaption>"
                "<h2>5. Contraevidencia y explicaciones alternativas</h2>"
                "<h2>6. Matriz de afirmaciones y evidencia</h2>"
                "<h2>7. Limitaciones y preguntas abiertas</h2>"
                "</body></html>"
            )
            html_file.write_text(leaked_html, encoding="utf-8")
            errs = validate_report.validate_html(html_file)
            self.assertTrue(any("english" in e.lower() or "spanish" in e.lower() or "lang" in e.lower() for e in errs), msg=errs)

    def test_html_warns_on_unconverted_latex(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = Path(tmpdir) / "report_latex.html"
            html_with_latex = (
                '<!DOCTYPE html><html lang="en"><body>'
                "<h2>1. Executive Summary</h2>"
                "<p>Price is $1.563 and band is $1,200–$1,400, testing $H_0$ vs $H_1$.</p>"
                "<h2>2. Framing &amp; Hypotheses</h2>"
                "<h2>3. Methodology &amp; Evidence Standards</h2>"
                "<h2>4. Findings</h2>"
                "<h2>5. Counter-Evidence &amp; Alternative Explanations</h2>"
                "<h2>6. Claim-Evidence Matrix</h2>"
                "<h2>7. Limitations &amp; Open Questions</h2>"
                "</body></html>"
            )
            html_file.write_text(html_with_latex, encoding="utf-8")
            errs, warnings = validate_report.validate_html_full(html_file)
            self.assertEqual(errs, [], msg=errs)
            self.assertTrue(any("latex" in w.lower() for w in warnings), msg=warnings)

    def test_provenance_checks_file_uri_hash_orphan_data_and_attempts_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            appendix = root / "appendix"
            data_dir = appendix / "data"
            data_dir.mkdir(parents=True)
            (appendix / "analysis.py").write_text("print('ok')\n", encoding="utf-8")
            (appendix / "output.txt").write_text("ok 60\n", encoding="utf-8")
            local_csv = data_dir / "local_series.csv"
            local_csv.write_text("a,b\n1,2\n", encoding="utf-8")
            # Orphan data file not registered anywhere
            (data_dir / "dummy.json").write_text("{}", encoding="utf-8")

            report_with_cite = _with_fig(
                VALID_REPORT.replace("Pure PHA films mineralize", "Pure PHA films mineralize [@C1]"), _seed_charts(root)
            )

            # 1) file:// without sha256 -> ERROR
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\n"
                f"C1,Local Copy,{local_csv.resolve().as_uri()},Tier 2,2026-11-20,2026-11,data\n",
                encoding="utf-8",
            )
            errs, _ = validate_report.validate_report_full(report_with_cite, level=2, report_dir=root)
            self.assertTrue(any("sha256" in e.lower() for e in errs), msg=errs)

            # 2) file:// WITH sha256 -> passes sources check, but orphan dummy.json -> WARNING
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\n"
                f"C1,Local Copy (sha256 {hashlib.sha256(local_csv.read_bytes()).hexdigest()}),{local_csv.resolve().as_uri()},Tier 2,2026-11-20,2026-11,data\n",
                encoding="utf-8",
            )
            errs2, warns2 = validate_report.validate_report_full(report_with_cite, level=2, report_dir=root)
            self.assertEqual(errs2, [], msg=errs2)
            self.assertTrue(any("dummy.json" in w for w in warns2), msg=warns2)

            # 3) data_attempts.csv without canonical columns -> ERROR
            (appendix / "data_attempts.csv").write_text(
                "target,source,method,outcome\ncustoms,https://api.example.org,GET,HTTP 403\n",
                encoding="utf-8",
            )
            errs3, _ = validate_report.validate_report_full(report_with_cite, level=2, report_dir=root)
            self.assertTrue(any("data_attempts.csv" in e and "column" in e.lower() for e in errs3), msg=errs3)

    def test_hygiene_warns_on_pycache_and_zero_byte_files_in_appendix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            appendix = root / "appendix"
            pycache = appendix / "__pycache__"
            pycache.mkdir(parents=True)
            (appendix / "analysis.py").write_text("print('ok')\n", encoding="utf-8")
            (appendix / "output.txt").write_text("ok 60\n", encoding="utf-8")
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\n"
                "C1,Study,https://example.org/c1,Tier 1,2026-11-20,2026-11,literature\n",
                encoding="utf-8",
            )
            (pycache / "analysis.cpython-312.pyc").write_bytes(b"\x00\x00")
            (appendix / "empty_log.txt").write_text("", encoding="utf-8")

            report_with_cite = _with_fig(
                VALID_REPORT.replace("Pure PHA films mineralize", "Pure PHA films mineralize [@C1]"), _seed_charts(root)
            )
            errs, warns = validate_report.validate_report_full(report_with_cite, level=2, report_dir=root)
            self.assertEqual(errs, [], msg=errs)
            self.assertTrue(any("__pycache__" in w or ".pyc" in w for w in warns), msg=warns)
            self.assertTrue(any("0-byte" in w.lower() or "empty_log.txt" in w for w in warns), msg=warns)


    # ---- v0.5.0 Phase 1: W1 charts.json location -------------------------------------------------
    def _l2_dir(self, root: Path, charts_where: str | None = "root", n_charts: int = 2) -> Path:
        import json

        appendix = root / "appendix"
        appendix.mkdir()
        (appendix / "analysis.py").write_text("print('ok')\n", encoding="utf-8")
        (appendix / "output.txt").write_text("ok 60\n", encoding="utf-8")
        (appendix / "sources.csv").write_text(
            "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\n"
            "C1,Primary Study,https://example.org/c1,Tier 1,2026-11-20,2026-11,literature\n",
            encoding="utf-8",
        )
        charts = [
            {"id": f"fig_{i}", "type": "bar", "title": f"T{i}", "series": [{"label": "A", "value": 1}]}
            for i in range(1, n_charts + 1)
        ]
        if charts_where == "root":
            (root / "charts.json").write_text(json.dumps(charts), encoding="utf-8")
        elif charts_where == "appendix":
            (appendix / "charts.json").write_text(json.dumps(charts), encoding="utf-8")
        return root

    def _cited(self, markers: str = "") -> str:
        return VALID_REPORT.replace("Pure PHA films mineralize", "Pure PHA films mineralize [@C1]").replace(
            "## 5. Counter-Evidence", markers + "\n\n## 5. Counter-Evidence"
        )

    def test_missing_fig_markers_fail_when_charts_json_in_report_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root")
            errs = validate_report.validate_report(self._cited(), level=2, report_dir=root)
            self.assertTrue(any("must place figures inline" in e for e in errs), msg=errs)

    def test_one_unplaced_chart_warns_with_exact_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root")
            errs, warns = validate_report.validate_report_full(
                self._cited("{{fig:fig_1}}"), level=2, report_dir=root
            )
            self.assertEqual(errs, [], msg=errs)
            self.assertTrue(any("fig_2" in w for w in warns), msg=warns)

    def test_level2_without_any_charts_json_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), None)
            errs = validate_report.validate_report(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertTrue(any("charts.json not found" in e for e in errs), msg=errs)
            # a table-only study (no figure markers) needs no charts.json (v0.7.0)
            errs_tables = validate_report.validate_report(self._cited(), level=2, report_dir=root)
            self.assertFalse(any("charts.json" in e for e in errs_tables), msg=errs_tables)

    def test_charts_json_in_appendix_is_still_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "appendix")
            errs = validate_report.validate_report(self._cited(), level=2, report_dir=root)
            self.assertTrue(any("must place figures inline" in e for e in errs), msg=errs)

    def test_charts_flag_overrides_search(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), None)
            custom = root / "custom_charts.json"
            custom.write_text(
                json.dumps([{"id": "only", "type": "bar", "title": "x", "series": [{"label": "A", "value": 1}]}]),
                encoding="utf-8",
            )
            errs = validate_report.validate_report(
                self._cited("{{fig:only}}"), level=2, report_dir=root, charts_path=custom
            )
            self.assertEqual(errs, [], msg=errs)


    # ---- v0.5.0 Phase 1: W2 unresolved markers, W4 uncited sources at level 3 --------------------
    def test_unresolved_num_marker_is_error(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "numbers.json").write_text(json.dumps({"known": "42"}), encoding="utf-8")
            report = self._cited("{{fig:fig_1}}").replace(
                "Pure PHA films", "Value {{num:known}} and {{num:no_existe}} pure PHA films", 1
            )
            errs = validate_report.validate_report(report, level=2, report_dir=root)
            self.assertTrue(any("no_existe" in e for e in errs), msg=errs)
            self.assertFalse(any("'known'" in e or "num:known" in e for e in errs), msg=errs)

    def test_num_marker_without_numbers_json_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            report = self._cited("{{fig:fig_1}}").replace("Pure PHA films", "Value {{num:x}} pure PHA films", 1)
            errs = validate_report.validate_report(report, level=2, report_dir=root)
            self.assertTrue(any("num:x" in e or "'x'" in e for e in errs), msg=errs)

    def test_html_with_leftover_braces_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html = Path(tmpdir) / "report.html"
            html.write_text(
                "<html lang=\"en\"><body><h2>1. Executive Summary</h2><h2>2. Framing &amp; Hypotheses</h2>"
                "<h2>3. Methodology &amp; Evidence Standards</h2><h2>4. Findings</h2>"
                "<h2>5. Counter-Evidence &amp; Alternative Explanations</h2><h2>6. Claim-Evidence Matrix</h2>"
                "<h2>7. Limitations &amp; Open Questions</h2><p>Value {{num:missing}}</p></body></html>",
                encoding="utf-8",
            )
            errs, _ = validate_report.validate_html_full(html)
            self.assertTrue(any("{{" in e for e in errs), msg=errs)

    def test_uncited_source_is_error_at_level3_warning_at_level2(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            with (root / "appendix" / "sources.csv").open("a", encoding="utf-8") as fh:
                fh.write("C2,Second Study,https://example.org/c2,Tier 1,2026-11-20,2026-11,literature\n")
            r2 = self._cited("{{fig:fig_1}}")
            errs2, warns2 = validate_report.validate_report_full(r2, level=2, report_dir=root)
            self.assertFalse(any("C2" in e for e in errs2), msg=errs2)
            self.assertTrue(any("C2" in w for w in warns2), msg=warns2)

            r3 = r2 + """
### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | Cold water kinetics missing | `Fixed` | Added Q10 sensitivity in appendix/analysis.py |
| 2 | Kinetics without temperature control | `Fixed` | Q10 sensitivity rerun in appendix/analysis.py |
"""
            errs3 = validate_report.validate_report(r3, level=3, report_dir=root)
            self.assertTrue(any("C2" in e and "never cited" in e for e in errs3), msg=errs3)


    # ---- v0.5.0 Phase 1: W3 stale HTML ---------------------------------------------------------
    def _render_for_validation(self, root: Path) -> Path:
        import subprocess as sp

        root_report = root / "report.md"
        root_report.write_text(self._cited("{{fig:fig_1}}"), encoding="utf-8")
        out = root / "report.html"
        res = sp.run(
            [sys.executable, "-B", str(SCRIPTS_DIR / "render_report.py"), str(root_report), "--out", str(out),
             "--charts", str(root / "charts.json"), "--appendix", str(root / "appendix")],
            capture_output=True,
            text=True, encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        return out

    def test_validator_warns_when_readme_changed_after_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "README.md").write_text("v1\n", encoding="utf-8")
            html = self._render_for_validation(root)
            fresh = validate_report.check_html_freshness(html, root / "report.md")
            self.assertEqual(fresh, [], msg=fresh)
            (root / "appendix" / "README.md").write_text("v2 edited after render\n", encoding="utf-8")
            stale = validate_report.check_html_freshness(html, root / "report.md")
            self.assertTrue(any("stale" in w.lower() or "out of date" in w.lower() for w in stale), msg=stale)

    def test_freshness_check_runs_under_isolated_mode(self) -> None:
        import subprocess as sp

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "README.md").write_text("v1\n", encoding="utf-8")
            html = self._render_for_validation(root)
            (root / "appendix" / "README.md").write_text("v2 edited after render\n", encoding="utf-8")
            res = sp.run(
                [sys.executable, "-I", "-B", str(SCRIPTS_DIR / "validate_report.py"), str(root / "report.md"),
                 "--level", "2", "--html", str(html)],
                capture_output=True,
                text=True, encoding="utf-8",
            )
            out = (res.stdout + res.stderr).lower()
            self.assertTrue("stale" in out or "out of date" in out, msg=out)

    def test_schemeless_local_source_requires_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            sources = root / "appendix" / "sources.csv"
            sources.write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\n"
                "C1,Local table,appendix/data/x.csv,Tier 2,2026-11-20,2026-11,data\n",
                encoding="utf-8",
            )
            errs = validate_report.validate_report(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertTrue(any("SHA-256" in e for e in errs), msg=errs)

    def test_validator_silent_on_html_without_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "report.md").write_text(self._cited("{{fig:fig_1}}"), encoding="utf-8")
            html = root / "report.html"
            html.write_text("<html><body>legacy v0.4 html</body></html>", encoding="utf-8")
            warns = validate_report.check_html_freshness(html, root / "report.md")
            self.assertEqual(len(warns), 1, msg=warns)
            self.assertIn("no source hash", warns[0].lower())


    # ---- v0.6.0 Phase B: P1 inherited attempts (attempted_utc) ----------------------------------
    _ATT_HEAD = "target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used,attempted_utc\n"

    def _l3_text(self) -> str:
        return self._cited("{{fig:fig_1}}").replace(
            "## 6. Claim-Evidence Matrix",
            """### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | Band series missing | `Deferred` | Logged in appendix/data_attempts.csv |
| 2 | Kinetics without temperature control | `Fixed` | Q10 sensitivity rerun in appendix/analysis.py |

## 6. Claim-Evidence Matrix""",
        )

    def test_inherited_failed_attempt_is_error_at_level3_warning_at_level2(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                self._ATT_HEAD + "band,BCRA catalog,https://x.org,failed,not found,,2026-11-19T16:29:00Z\n",
                encoding="utf-8",
            )
            errs3, _ = validate_report.validate_report_full(
                self._l3_text(), level=3, report_dir=root, run_since="2026-11-20"
            )
            self.assertTrue(any("inherited" in e.lower() and "band" in e for e in errs3), msg=errs3)
            errs2, warns2 = validate_report.validate_report_full(
                self._cited("{{fig:fig_1}}"), level=2, report_dir=root, run_since="2026-11-20"
            )
            self.assertFalse(any("inherited" in e.lower() for e in errs2), msg=errs2)
            self.assertTrue(any("inherited" in w.lower() and "band" in w for w in warns2), msg=warns2)

    def test_fresh_retry_clears_inherited_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                self._ATT_HEAD
                + "band,BCRA catalog,https://x.org,failed,not found,,2026-11-19T16:29:00Z\n"
                + "band,BCRA catalog (paged),https://x.org,failed,not found,,2026-11-20T10:00:00Z\n",
                encoding="utf-8",
            )
            errs3, warns3 = validate_report.validate_report_full(
                self._l3_text(), level=3, report_dir=root, run_since="2026-11-20"
            )
            self.assertFalse(any("inherited" in x.lower() for x in errs3 + warns3), msg=errs3 + warns3)

    def test_attempts_without_attempted_utc_column_count_as_inherited(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                "target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used\n"
                "band,BCRA,https://x.org,failed,not found,\n",
                encoding="utf-8",
            )
            msg = "appendix/data_attempts.csv has no attempted_utc column"
            errs3, _ = validate_report.validate_report_full(
                self._l3_text(), level=3, report_dir=root, run_since="2026-11-20"
            )
            self.assertTrue(any(msg in e for e in errs3), msg=errs3)
            errs2, warns2 = validate_report.validate_report_full(
                self._cited("{{fig:fig_1}}"), level=2, report_dir=root, run_since="2026-11-20"
            )
            self.assertFalse(any(msg in e for e in errs2), msg=errs2)
            self.assertTrue(any(msg in w for w in warns2), msg=warns2)

    def test_fresh_dated_attempts_are_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                self._ATT_HEAD + "band,BCRA,https://x.org,failed,not found,,2026-11-20T10:00:00Z\n", encoding="utf-8"
            )
            errs3, warns3 = validate_report.validate_report_full(
                self._l3_text(), level=3, report_dir=root, run_since="2026-11-20"
            )
            self.assertFalse(any("inherited" in x.lower() or "attempted_utc" in x for x in errs3 + warns3), msg=errs3 + warns3)

    def test_unknown_run_start_warns_instead_of_skipping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                self._ATT_HEAD + "band,BCRA,https://x.org,failed,not found,,2026-01-05\n", encoding="utf-8"
            )
            text = self._l3_text()
            self.assertIsNone(re.search(r"\d{4}-\d{2}-\d{2}", "\n".join(text.splitlines()[:20])))
            for level, body in ((2, self._cited("{{fig:fig_1}}")), (3, text)):
                _, warns = validate_report.validate_report_full(body, level=level, report_dir=root)
                self.assertTrue(any("cannot determine run start; pass --run-since YYYY-MM-DD" in w for w in warns), msg=warns)

    # ---- v0.6.1 C3: only failures that back a limitation count ---------------------------------
    def test_failed_row_with_real_fallback_is_not_inherited(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                self._ATT_HEAD
                + "REM vintage 2025-10,BCRA xlsx,/rem-2025-10.xlsx,HTTP 404,no file,Official REM history file used,2026-11-19\n"
                + "band,BCRA catalog,https://x.org,failed,not found,,2026-11-19\n"
                + "fx floor,BCRA,https://y.org,failed,not found,limitation (press value),2026-11-19\n",
                encoding="utf-8",
            )
            errs3, _ = validate_report.validate_report_full(
                self._l3_text(), level=3, report_dir=root, run_since="2026-11-20"
            )
            inherited = [e for e in errs3 if "inherited" in e.lower()]
            self.assertFalse(any("REM vintage" in e for e in inherited), msg=inherited)
            self.assertTrue(any("'band'" in e for e in inherited), msg=inherited)
            self.assertTrue(any("'fx floor'" in e for e in inherited), msg=inherited)

    def test_band_series_paraphrased_in_deferred_row_still_counts(self) -> None:
        """Audit v0.6 case: the band series had a real-looking fallback and a paraphrased Deferred row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                self._ATT_HEAD
                + "Serie diaria oficial del techo/piso de la banda,BCRA API v4,first 1000 variables,not found,"
                "no series,Reconstrucción propia del techo con prensa,2026-11-19\n"
                + "REM vintage 2025-10,BCRA xlsx,/rem-2025-10.xlsx,HTTP 404,no file,Base histórica del REM usada,2026-11-19\n",
                encoding="utf-8",
            )
            text = self._cited("{{fig:fig_1}}") + """
### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 9 | Serie oficial del techo y piso sin rungs completos | `Deferred` | data_attempts.csv |
| 2 | Kinetics without temperature control | `Fixed` | Q10 sensitivity rerun in appendix/analysis.py |
"""
            errs3, _ = validate_report.validate_report_full(text, level=3, report_dir=root, run_since="2026-11-20")
            inherited = [e for e in errs3 if "inherited" in e.lower()]
            self.assertTrue(any("techo/piso" in e for e in inherited), msg=inherited)
            self.assertFalse(any("REM vintage" in e for e in inherited), msg=inherited)

    def test_failed_row_named_in_limitations_counts_even_with_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                self._ATT_HEAD
                + "Cold water kinetics,Journal API,https://z.org,HTTP 403,paywall,abstract only,2026-11-19\n",
                encoding="utf-8",
            )
            text = self._l3_text().replace(
                "- **Methodological & Data Limitations:**",
                "- **Methodological & Data Limitations:** Cold water kinetics could not be retrieved.",
                1,
            )
            errs3, _ = validate_report.validate_report_full(text, level=3, report_dir=root, run_since="2026-11-20")
            self.assertTrue(any("Cold water kinetics" in e and "inherited" in e.lower() for e in errs3), msg=errs3)

    def test_run_since_defaults_to_report_header_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "data_attempts.csv").write_text(
                self._ATT_HEAD + "band,BCRA,https://x.org,failed,not found,,2026-01-05\n", encoding="utf-8"
            )
            text = "**Date:** 2026-11-20\n\n" + self._cited("{{fig:fig_1}}")
            _, warns = validate_report.validate_report_full(text, level=2, report_dir=root)
            self.assertTrue(any("inherited" in w.lower() for w in warns), msg=warns)

    # ---- v0.6.0 Phase B: P2 subagent gate traces ----------------------------------------------
    def _write_gates(self, root: Path, qa: str | None = None) -> None:
        _seed_gates(root, qa)

    def test_missing_gates_warn_at_level2_and_error_at_level3(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            errs2, warns2 = validate_report.validate_report_full(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertFalse(any("gates" in e for e in errs2), msg=errs2)
            for name in ("source_verifier", "qa"):
                self.assertTrue(any(f"gates/{name}.md" in w for w in warns2), msg=warns2)
            self.assertFalse(any("gates/reviewer.md" in w for w in warns2), msg=warns2)  # Reviewer #2 is Level 3 only
            errs3, _ = validate_report.validate_report_full(self._l3_text(), level=3, report_dir=root)
            for name in ("source_verifier", "reviewer", "qa"):
                self.assertTrue(any(f"gates/{name}.md" in e for e in errs3), msg=errs3)

    def test_all_gates_present_with_qa_pass_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            self._write_gates(root)
            errs, warns = validate_report.validate_report_full(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertFalse(any("gates" in x for x in errs + warns), msg=errs + warns)

    def test_qa_gate_without_pass_line_is_flagged_unless_accepted_in_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            self._write_gates(root, qa=_qa_text("FAIL", failed=(4,)))
            errs3, _ = validate_report.validate_report_full(self._l3_text(), level=3, report_dir=root)
            self.assertTrue(any("QA: PASS" in e for e in errs3), msg=errs3)
            accepted = self._l3_text() + "\nAccepted QA FAIL check 4 (see appendix/gates/qa.md): drift is cosmetic.\n"
            errs3b, warns3b = validate_report.validate_report_full(accepted, level=3, report_dir=root)
            self.assertFalse(any("QA: PASS" in x for x in errs3b + warns3b), msg=errs3b + warns3b)

    def test_empty_gate_file_counts_as_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            self._write_gates(root)
            (root / "appendix" / "gates" / "source_verifier.md").write_text("  \n", encoding="utf-8")
            _, warns = validate_report.validate_report_full(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertTrue(any("gates/source_verifier.md" in w for w in warns), msg=warns)

    # ---- v0.6.1 C1: gate files must carry the markers their prompts fix ------------------------
    def test_placeholder_gates_fail_and_name_the_missing_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            gates = root / "appendix" / "gates"
            gates.mkdir(parents=True)
            for name in ("source_verifier", "reviewer"):
                (gates / f"{name}.md").write_text("x\n", encoding="utf-8")
            (gates / "qa.md").write_text("QA: PASS\n", encoding="utf-8")
            errs3, _ = validate_report.validate_report_full(self._l3_text(), level=3, report_dir=root)
            self.assertTrue(any("source_verifier.md" in e and "SOURCE-VERIFIER: PASS|FAIL" in e for e in errs3), msg=errs3)
            self.assertTrue(any("reviewer.md" in e and "Over-calibrated claims" in e for e in errs3), msg=errs3)
            self.assertTrue(any("qa.md" in e and "FAIL count" in e for e in errs3), msg=errs3)
            self.assertTrue(any("400 characters" in e for e in errs3), msg=errs3)

    def test_complete_handwritten_gates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            _seed_gates(root)
            errs3, warns3 = validate_report.validate_report_full(self._l3_text(), level=3, report_dir=root)
            self.assertFalse(any("gates/" in x for x in errs3 + warns3), msg=errs3 + warns3)

    def test_qa_pass_without_the_eight_checks_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            _seed_gates(root, qa="QA: PASS\nFAIL count: 0\n" + "All good, everything checked carefully. " * 12)
            errs3, _ = validate_report.validate_report_full(self._l3_text(), level=3, report_dir=root)
            missing = [e for e in errs3 if "qa.md" in e]
            self.assertTrue(any("check 1" in e and "check 8" in e for e in missing), msg=errs3)

    # ---- v0.6.1 C8: gate files are embedded in the HTML, so they must not leak paths or markers -
    def test_gate_with_home_path_or_literal_marker_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            _seed_gates(root, qa=_qa_text() + "Checked /home/usuario/x and {{num:spot}}.\n")
            errs3, _ = validate_report.validate_report_full(self._l3_text(), level=3, report_dir=root)
            self.assertTrue(any("qa.md" in e and "home-directory path" in e for e in errs3), msg=errs3)
            self.assertTrue(any("qa.md" in e and "{{num:" in e for e in errs3), msg=errs3)
            _, warns2 = validate_report.validate_report_full(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertTrue(any("home-directory path" in w for w in warns2), msg=warns2)

    def test_gate_reporting_a_zero_count_passes_privacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            _seed_gates(root, qa=_qa_text() + "home-directory paths in report.html: 0\n")
            errs3, warns3 = validate_report.validate_report_full(self._l3_text(), level=3, report_dir=root)
            self.assertFalse(any("home-directory path" in x for x in errs3 + warns3), msg=errs3 + warns3)

    # ---- v0.6.0 Phase B: P3 numbers.json coverage ----------------------------------------------
    def _output_with(self, root: Path, numbers: list[str]) -> None:
        (root / "appendix" / "output.txt").write_text("\n".join(numbers) + "\n", encoding="utf-8")

    def test_hardcoded_output_numbers_without_markers_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            nums = ["12.31", "45.67", "78.90", "23.45", "56.78", "89.01"]
            self._output_with(root, nums)
            report = self._cited("{{fig:fig_1}}").replace(
                "Pure PHA films", "Effects were " + ", ".join(nums) + " pure PHA films", 1
            )
            _, warns = validate_report.validate_report_full(report, level=2, report_dir=root)
            self.assertTrue(any("numbers.json" in w and "{{num:" in w for w in warns), msg=warns)

    def test_markers_covering_most_numbers_do_not_warn(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            nums = ["12.31", "45.67", "78.90", "23.45", "56.78", "89.01"]
            self._output_with(root, nums)
            keys = {f"k{i}": n for i, n in enumerate(nums)}
            (root / "appendix" / "numbers.json").write_text(json.dumps(keys), encoding="utf-8")
            body = ", ".join(f"{{{{num:k{i}}}}}" for i in range(6))
            report = self._cited("{{fig:fig_1}}").replace("Pure PHA films", f"Effects were {body} pure PHA films", 1)
            _, warns = validate_report.validate_report_full(report, level=2, report_dir=root)
            self.assertFalse(any("numbers.json" in w and "coverage" in w.lower() for w in warns), msg=warns)

    # ---- v0.6.1 C5 ----------------------------------------------------------------------------
    def test_nine_markers_sixteen_typed_in_section4_warns(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            typed = [f"{10 + i}.{i + 11}" for i in range(16)]
            keyed = [f"{50 + i}.{i + 21}" for i in range(9)]
            self._output_with(root, typed + keyed)
            (root / "appendix" / "numbers.json").write_text(
                json.dumps({f"k{i}": v for i, v in enumerate(keyed)}), encoding="utf-8"
            )
            body = ", ".join(typed) + "; " + ", ".join(f"{{{{num:k{i}}}}}" for i in range(9))
            report = self._cited("{{fig:fig_1}}").replace("Pure PHA films", f"Effects {body} pure PHA films", 1)
            _, warns = validate_report.validate_report_full(report, level=2, report_dir=root)
            self.assertTrue(any("numbers.json coverage is low" in w for w in warns), msg=warns)

    def test_section_numbers_are_not_counted_as_typed_figures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            self._output_with(root, ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6"])
            report = self._cited("{{fig:fig_1}}").replace(
                "Pure PHA films",
                "See Section 4.1, Sección 4.2, § 4.3, §4.4, Section 4.5 and Sección 4.6 pure PHA films",
                1,
            )
            _, warns = validate_report.validate_report_full(report, level=2, report_dir=root)
            self.assertFalse(any("numbers.json coverage" in w for w in warns), msg=warns)

    def test_typed_verdict_numbers_from_output_warn_then_error_at_level3(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            self._output_with(root, ["surcharge 0.35", "target 60", "years 3", "rate 12.75", "share 41.20"])
            text = self._cited("{{fig:fig_1}}").replace(
                "though pure marine-certified", "with a 12.75 rate and 41.20 share, though pure marine-certified", 1
            )
            msg = "Calibrated Verdict / Section 1"
            _, warns2 = validate_report.validate_report_full(text, level=2, report_dir=root)
            self.assertTrue(any(msg in w for w in warns2), msg=warns2)
            l3 = text + self._l3_text()[len(self._cited("{{fig:fig_1}}")):]
            errs3, _ = validate_report.validate_report_full(l3, level=3, report_dir=root, run_since="2026-11-20")
            self.assertTrue(any(msg in e for e in errs3), msg=errs3)

    def test_verdict_with_markers_does_not_warn(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            self._output_with(root, ["surcharge 0.35", "target 60", "rate 12.75", "share 41.20"])
            (root / "appendix" / "numbers.json").write_text(
                json.dumps({"s": "0.35", "t": "60", "r": "12.75", "h": "41.20"}), encoding="utf-8"
            )
            text = self._cited("{{fig:fig_1}}").replace("$0.35 surcharge", "${{num:s}} surcharge", 1).replace(
                "a 60% reduction", "a {{num:t}}% reduction", 1
            ).replace("though pure marine-certified", "with {{num:r}} and {{num:h}}, though pure marine-certified", 1)
            _, warns = validate_report.validate_report_full(text, level=2, report_dir=root)
            self.assertFalse(any("Calibrated Verdict / Section 1" in w for w in warns), msg=warns)

    def test_few_hardcoded_numbers_do_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            self._output_with(root, ["12.31", "45.67"])
            report = self._cited("{{fig:fig_1}}").replace("Pure PHA films", "Effects 12.31 and 45.67 pure PHA films", 1)
            _, warns = validate_report.validate_report_full(report, level=2, report_dir=root)
            self.assertFalse(any("numbers.json" in w for w in warns), msg=warns)

    # ---- v0.5.0 Phase 3: F1 contradictory provenance, F2 source kind ---------------------------
    ATTEMPTS_HEADER = "target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used\n"
    SOURCES_HEADER = "claim_id,source_title,url,tier,accessed_date,data_as_of,kind\n"

    def test_source_described_as_full_text_but_failed_attempt_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "sources.csv").write_text(
                self.SOURCES_HEADER + "C1,Moran 1953 (open-access full text),https://example.org/c1,Tier 2,2026-11-20,2026-11,literature\n",
                encoding="utf-8",
            )
            (root / "appendix" / "data_attempts.csv").write_text(
                self.ATTEMPTS_HEADER + "C1 paper,Publisher,GET https://example.org/c1,CAPTCHA,full text not retrievable,limitation\n",
                encoding="utf-8",
            )
            errs, warns = validate_report.validate_report_full(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertEqual(errs, [], msg=errs)
            self.assertTrue(any("C1" in w and "failed attempt" in w for w in warns), msg=warns)

    def test_successful_attempt_does_not_trigger_contradiction_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "sources.csv").write_text(
                self.SOURCES_HEADER + "C1,Paper (full text),https://example.org/c1,Tier 2,2026-11-20,2026-11,literature\n",
                encoding="utf-8",
            )
            (root / "appendix" / "data_attempts.csv").write_text(
                self.ATTEMPTS_HEADER + "C1 paper,Publisher,GET https://example.org/c1,used,,\n",
                encoding="utf-8",
            )
            _, warns = validate_report.validate_report_full(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertFalse(any("failed attempt" in w for w in warns), msg=warns)

    def test_own_computation_cannot_be_tier1_and_missing_kind_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            errs0 = validate_report.validate_report(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertEqual(errs0, [], msg=errs0)  # legacy sources.csv without a kind column
            (root / "appendix" / "sources.csv").write_text(
                self.SOURCES_HEADER + "C1,analysis.py,appendix/analysis.py,Tier 1,2026-11-20,2026-11,own-computation\n",
                encoding="utf-8",
            )
            errs = validate_report.validate_report(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertTrue(any("own-computation" in e and "Tier 1" in e for e in errs), msg=errs)

    def test_strong_claim_backed_only_by_own_computation_warns_at_level3(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "appendix" / "sources.csv").write_text(
                self.SOURCES_HEADER + "C1,analysis.py,appendix/analysis.py,Tier 2,2026-11-20,2026-11,own-computation\n",
                encoding="utf-8",
            )
            report = self._cited("{{fig:fig_1}}").replace(
                "Peer-reviewed field & lab meta-analyses [@C1] (Tier 1)", "Own simulation [@C1] (Tier 2)", 1
            )
            disp = """
### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | Cold water kinetics missing | `Fixed` | Added Q10 sensitivity in appendix/analysis.py |
| 2 | Kinetics without temperature control | `Fixed` | Q10 sensitivity rerun in appendix/analysis.py |
"""
            _seed_gates(root)
            errs2, _ = validate_report.validate_report_full(report, level=2, report_dir=root)
            self.assertTrue(any("[Strong]" in e and "weak source" in e for e in errs2), msg=errs2)
            errs3, _ = validate_report.validate_report_full(report + disp, level=3, report_dir=root)
            self.assertTrue(any("[Strong]" in e and "weak source" in e and "C1" in e for e in errs3), msg=errs3)


    def test_validator_surfaces_chart_design_warnings(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._l2_dir(Path(tmpdir), "root", n_charts=1)
            (root / "charts.json").write_text(
                json.dumps([{"id": "fig_1", "type": "bar", "title": "T",
                             "series": [{"label": "A", "value": 0.717}, {"label": "B", "value": 0.7171}]}]),
                encoding="utf-8",
            )
            errs, warns = validate_report.validate_report_full(self._cited("{{fig:fig_1}}"), level=2, report_dir=root)
            self.assertEqual(errs, [], msg=errs)
            self.assertTrue(any("fig_1" in w and "near-identical" in w for w in warns), msg=warns)


if __name__ == "__main__":
    unittest.main()
