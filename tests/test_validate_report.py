import subprocess
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
| Thin-film PHA mineralizes enzymatically in aerobic seawater | Marine Chemistry | Peer-reviewed field & lab meta-analyses (Tier 1) | `[Strong]` | Blending with non-marine-degradable PLA/PBAT |
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
            "| Thin-film PHA mineralizes enzymatically in aerobic seawater | Marine Chemistry | Peer-reviewed field & lab meta-analyses (Tier 1) | `[Strong]` | Blending with non-marine-degradable PLA/PBAT |",
            "| Forecast hits target | Economics | Press release roadmap (Tier 3) | `[Strong]` | Delay |",
        )
        errors = validate_report.validate_report(bad)
        self.assertTrue(any("strong" in e.lower() for e in errors), msg=errors)

    def test_strong_on_press_without_tier3_literal_fails(self) -> None:
        """Audit v0.2: [Strong] paired with 'nota de prensa' (without literal 'Tier 3') must FAIL."""
        bad = VALID_REPORT.replace(
            "| Thin-film PHA mineralizes enzymatically in aerobic seawater | Marine Chemistry | Peer-reviewed field & lab meta-analyses (Tier 1) | `[Strong]` | Blending with non-marine-degradable PLA/PBAT |",
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
            root = Path(tmpdir)
            appendix = root / "appendix"
            appendix.mkdir()
            (appendix / "analysis.py").write_text("print('ok')\n", encoding="utf-8")
            (appendix / "output.txt").write_text("ok\n", encoding="utf-8")
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,accessed_date,data_as_of\n1,Study,https://example.org,Tier 1,2026-11-20,2025-12\n",
                encoding="utf-8",
            )

            with_backtick_fixed = VALID_REPORT + """
### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | Cold water kinetics missing | `Fixed` | Added Q10 sensitivity in appendix/analysis.py |
"""
            self.assertEqual(validate_report.validate_report(with_backtick_fixed, level=3, report_dir=root), [])

            with_deferred_no_log = VALID_REPORT + """
### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | Missing proprietary customs series | `Deferred` | Unavailable |
"""
            errs_missing_log = validate_report.validate_report(with_deferred_no_log, level=3, report_dir=root)
            self.assertTrue(any("data_attempts" in e.lower() or "attempt" in e.lower() for e in errs_missing_log), msg=errs_missing_log)

            (appendix / "data_attempts.csv").write_text(
                "target,source,method,outcome\ncustoms,https://api.example.org,GET,HTTP 403\n",
                encoding="utf-8",
            )
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

            res_ok = subprocess.run([sys.executable, str(script_path), str(valid_file)], capture_output=True, text=True)
            self.assertEqual(res_ok.returncode, 0, msg=res_ok.stderr)

            res_bad = subprocess.run([sys.executable, str(script_path), str(invalid_file)], capture_output=True, text=True)
            self.assertEqual(res_bad.returncode, 1)


if __name__ == "__main__":
    unittest.main()
