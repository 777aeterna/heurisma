import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path so validate_report can be imported
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
- **Refutation Criteria:** $H_1$ is falsified if cold-water (<10 °C) thick-walled PHA persistence exceeds 24 months or if unsubsidized packaging cost increases exceed 50% of small-vendor net margins.

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:** Marine field degradation trials > ASTM D6691 30 °C lab tests; municipal natural experiments (Berkeley, Vancouver) > theoretical price elasticity.
- **Analytical / Computational Method:** Multi-disciplinary evidence synthesis across polymer degradation kinetics, municipal fee outcomes, and foodservice unit economics.

## 4. Findings
Pure PHA films mineralize in warm aerobic seawater (`[Strong]`), whereas thick thermoformed containers in <10 °C coastal water or anoxic sediment degrade orders of magnitude slower (`[Moderate]`). Global PHA capacity (~70k MT) creates acute supply bottlenecks (`[Preliminary]`), and 2x-4x resin cost premiums threaten 3%-5% small-vendor margins unless surcharge revenue is retained (`[Moderate]`).

## 5. Counter-Evidence & Alternative Explanations
Thin-film PHA items (straws, bags) do avoid centuries-long microplastic persistence even when fragmented (`[Strong]`), and European cup-surcharge trials (€0.30-€0.90) achieved >70% switching when paired with accessible deposit-return networks (`[Moderate]`).

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier | Confidence Tag | Key Falsifier / Condition |
| :--- | :--- | :--- | :--- | :--- |
| Thin-film PHA mineralizes enzymatically in aerobic seawater | Marine Chemistry | Peer-reviewed field & lab meta-analyses (Tier 1) | `[Strong]` | Blending with non-marine-degradable PLA/PBAT |
| Unretained $0.35 surcharge compresses small vendor profit margins | Micro-Economics | Foodservice margin data & resin spot pricing (Tier 2) | `[Moderate]` | Municipal bulk-purchasing subsidy or vendor fee retention |

## 7. Limitations & Open Questions
- **Methodological & Data Limitations:** Limited multi-year cold-water benthic ecotoxicity datasets for finished commercial PHA blends.
- **Actionable Next Steps / Experiments:** Mandate TÜV OK Biodegradable MARINE certification on finished items and run a 6-month vendor fee-retention pilot.
"""


class TestValidateReport(unittest.TestCase):
    def test_valid_report_passes(self) -> None:
        errors = validate_report.validate_report(VALID_REPORT)
        self.assertEqual(errors, [])

    def test_empty_report_fails(self) -> None:
        errors = validate_report.validate_report("   \n  ")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("empty" in err.lower() or "section" in err.lower() for err in errors))

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

    def test_missing_hypotheses_or_matrix_table_fails(self) -> None:
        no_matrix = VALID_REPORT.split("## 6. Claim-Evidence Matrix")[0] + "## 6. Claim-Evidence Matrix\nNone.\n\n## 7. Limitations & Open Questions\n- Limit."
        errors = validate_report.validate_report(no_matrix)
        self.assertTrue(any("matrix" in err.lower() or "table" in err.lower() for err in errors))

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
            self.assertIn("Missing required section", res_bad.stderr)


if __name__ == "__main__":
    unittest.main()
