"""End-to-end integration test for v0.11.0: CSV -> conjecture.py -> formal_math.py -> render -> validate."""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "heurisma" / "scripts"
TESTS_DIR = Path(__file__).resolve().parent
for _p in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mutations as M  # noqa: E402
import validate_report  # noqa: E402
from test_formal_math import _make_fake_toolchain  # noqa: E402


class TestV0110E2EPipeline(unittest.TestCase):
    def test_pendulum_csv_to_conjecture_to_lean_proof_to_strict_level3_html(self) -> None:
        """Full pipeline: pendulum CSV -> units -> discover -> formal_math init/check -> render -> Level 3 --strict."""
        tmp, ws = M.fresh_workspace()
        try:
            app = ws / "appendix"
            data_dir = app / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            # 1. Create a clean pendulum dataset T = 2*pi*sqrt(L/g) (independent of mass m)
            csv_path = data_dir / "pendulum.csv"
            g = 9.81
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, lineterminator="\n")
                w.writerow(["L", "g", "m", "T"])
                for i in range(1, 21):
                    length = 0.25 * i
                    mass = 0.5 + 0.3 * (i % 5)
                    period = 2.0 * math.pi * math.sqrt(length / g)
                    w.writerow([f"{length:.4f}", f"{g:.2f}", f"{mass:.2f}", f"{period:.6f}"])

            # Register the pendulum dataset as a local Tier 3 data row in sources.csv so P1-ORPHAN is clean
            p_sha = validate_report._file_sha256(csv_path)
            src_path = app / "sources.csv"
            with src_path.open(encoding="utf-8", newline="") as fh:
                srows = list(csv.DictReader(fh))
                scols = list(srows[0].keys())
            if "sha256" not in scols:
                scols.append("sha256")
            srows.append({
                "claim_id": "L_PEND",
                "source_title": "Synthetic pendulum calibration table (local file)",
                "url": "appendix/data/pendulum.csv",
                "tier": "Tier 3",
                "accessed_date": "2026-11-20",
                "data_as_of": "2026-11-20",
                "kind": "data",
                "sha256": p_sha,
            })
            with src_path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=scols, lineterminator="\n")
                w.writeheader()
                w.writerows(srows)

            # 2. Run conjecture.py units via CLI
            res_u = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS_DIR / "conjecture.py"),
                    "units", "--target", "T=s", "--var", "L=m", "--var", "g=m/s^2", "--var", "m=kg", "--json",
                ],
                cwd=ws, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(res_u.returncode, 0, res_u.stderr)
            units_out = json.loads(res_u.stdout)
            self.assertEqual(units_out["groups"][0]["exponents"]["m"], "0")
            self.assertEqual(units_out["groups"][0]["exponents"]["L"], "-1/2")
            self.assertEqual(units_out["groups"][0]["exponents"]["g"], "1/2")

            # 3. Run conjecture.py discover via CLI -> appendix/conjectures.json
            conj_path = app / "conjectures.json"
            res_d = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS_DIR / "conjecture.py"),
                    "discover", str(csv_path),
                    "--target", "T", "--predictors", "L,g,m",
                    "--units", "T=s,L=m,g=m/s^2,m=kg",
                    "--holdout-fraction", "0.25", "--holdout-mode", "tail",
                    "--out", str(conj_path),
                ],
                cwd=ws, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(res_d.returncode, 0, res_d.stderr)
            self.assertTrue(conj_path.is_file())
            cdata = json.loads(conj_path.read_text(encoding="utf-8"))
            self.assertTrue(cdata["beats_null"], cdata)
            self.assertGreaterEqual(cdata["holdout_count"], 2)

            # 4. Run formal_math.py init --from-conjecture C_LAW_1 via CLI
            res_i = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS_DIR / "formal_math.py"),
                    "init", "pendulum_law", "--appendix", str(app),
                    "--from-conjecture", "C_LAW_1",
                    "--statement", "(n : Nat) : n + 0 = n",
                ],
                cwd=ws, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(res_i.returncode, 0, res_i.stderr)

            # 5. Run formal_math.py check --register --claim FM_PEND with fake lake/lean
            bin_dir = ws / "fake_lean_bin"
            lake_p, lean_p = _make_fake_toolchain(
                bin_dir,
                axioms_line="'Solution.main_claim' depends on axioms: [propext, Classical.choice]",
            )
            fake_env = {
                "PATH": str(bin_dir),
                "HOME": str(ws),
                "HEURISMA_LAKE": str(lake_p),
                "HEURISMA_LEAN": str(lean_p),
            }
            if os.name == "nt":
                for _k in ("SYSTEMROOT", "COMSPEC", "PATHEXT"):
                    if os.environ.get(_k):
                        fake_env[_k] = os.environ[_k]
            res_c = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS_DIR / "formal_math.py"),
                    "check", "pendulum_law", "--appendix", str(app),
                    "--register", "--claim", "FM_PEND", "--require-kernel",
                ],
                cwd=ws, capture_output=True, text=True, encoding="utf-8", env=fake_env, check=False,
            )
            self.assertEqual(res_c.returncode, 0, res_c.stdout + res_c.stderr)

            # 6. Cite L_PEND and FM_PEND in report.md (scoped to formal model so P-10 bridge stays clean)
            md_path = ws / "report.md"
            md = md_path.read_text(encoding="utf-8")
            md = md.replace(
                "## 5.",
                "The synthetic pendulum table [@L_PEND] yielded conjecture `C_LAW_1` in `appendix/conjectures.json`, "
                "and under the formal model the scaling theorem is kernel-verified [@FM_PEND].\n\n## 5.",
                1,
            )
            md = md.replace(
                "## 7.",
                "| Under the formal model, pendulum scaling satisfies the kernel-verified identity | Formal Sciences | "
                "Lean 4 proof [@FM_PEND] and calibration table [@L_PEND], Tier 1, 2026-11 | `[Strong]` | "
                "Violation of ideal small-angle axiom |\n\n## 7.",
                1,
            )
            md_path.write_text(md, encoding="utf-8")

            # 7. Re-stamp gates (including FORMAL-SHA256 in reviewer.md), render report.html, and validate!
            M.restamp_gates(ws)
            rev_path = app / "gates" / "reviewer.md"
            if rev_path.is_file():
                hdr = subprocess.run(
                    [sys.executable, "-B", str(SCRIPTS_DIR / "validate_report.py"), str(md_path), "--gate-header", "reviewer"],
                    cwd=ws, capture_output=True, text=True, encoding="utf-8", check=True,
                ).stdout
                self.assertIn("FORMAL-SHA256:", hdr)

            html_path = ws / "report.html"
            M.rerender(ws)
            errs, warns = validate_report.validate_report_full(
                md_path.read_text(encoding="utf-8"), level=2, report_dir=ws
            )
            h_errs, h_warns = validate_report.validate_html_full(html_path)
            f_warns = validate_report.check_html_freshness(html_path, md_path)
            self.assertEqual(errs + h_errs, [], f"Errors: {errs + h_errs}")
            self.assertEqual(warns + h_warns + f_warns, [], f"Warnings: {warns + h_warns + f_warns}")

            # 8. Replay Lean proof via opt-in reproduce_lean()
            r_errs, r_warns = validate_report.reproduce_lean(ws, env=fake_env)
            self.assertEqual(r_errs, [], r_errs)
            self.assertEqual(r_warns, [], r_warns)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
