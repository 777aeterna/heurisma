"""Regression tests for the 6 findings uncovered by the live v0.11.1 exoplanet Level 3 stress test.

Covers:
1. conjecture.py --target __invariant__: dimensional homogeneity filter when --units is supplied,
   and anchor-scaled relative SD (never dividing anchor residuals by another column's 1e20 SD).
2. checks/conjecture.py (DIS-6): beats_null=false on one discovery file (e.g. conjectures_invariant.json)
   must not cross-contaminate unrelated Section 4 empirical claims sharing source_ids.
3. checks/prereg.py (P2-PREREG): a post-preregistration derived file in appendix/data/ whose
   provenance is explicitly documented in Section 3 alongside logged downloads in download_log.csv
   is accepted without warning, while undocumented files (M29) still warn.
4. local_data.py register CLI: supports --selection and --retrieved-utc flags.
5. formal_math.py check --register CLI: defaults --tier to 'Tier 3' when status is
   unverified_no_toolchain (and still refuses an explicit --tier 'Tier 1').
6. references/agents/reviewer.md (+ agents/heurisma-reviewer.md): warns Reviewer #2 not to emit
   literal {{num:...}} / {{fig:...}} markers outside QUOTE lines (preventing GATE-PRIVACY friction).
"""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "heurisma" / "scripts"
TESTS_DIR = Path(__file__).resolve().parent
for _p in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conjecture  # noqa: E402
from checks import conjecture as checks_conjecture  # noqa: E402
import formal_math  # noqa: E402
import mutations as M  # noqa: E402
import validate_report  # noqa: E402


class TestV0111FieldStressFixes(unittest.TestCase):
    def test_invariant_multiscale_units_skips_inhomogeneous_linear_and_recovers_monomial(self) -> None:
        """Finding 1: P_s ~ 1e5, a_m ~ 1e10, GM ~ 1e20 must not let linear_invariant win with 1e-15 artifact."""
        rows: list[dict[str, float]] = []
        two_pi = 2.0 * math.pi
        for i in range(1, 41):
            gm = 1.327e20 * (0.3 + 0.35 * ((i * 3) % 7))  # independent non-collinear stellar masses
            a_m = 1.5e10 * (1.0 + 0.15 * i)               # ~1.7e10 .. 1.05e11 m
            noise = 1.0 + 0.004 * ((i % 5) - 2)
            p_s = two_pi * (a_m ** 1.5) * (gm ** -0.5) * noise
            rows.append({"P_s": p_s, "a_m": a_m, "GM": gm})

        res = conjecture.discover_laws(
            rows,
            target="__invariant__",
            predictors=["P_s", "a_m", "GM"],
            units={"P_s": "s", "a_m": "m", "GM": "m^3/s^2"},
            source_ids=["C1"],
            seed=0,
        )
        top = res["candidates"][0]
        self.assertEqual(top["family"], "monomial_invariant", res["candidates"])
        self.assertEqual(top["exponents"], {"P_s": "1", "a_m": "-3/2", "GM": "1/2"})
        self.assertTrue(res["beats_null"], res)
        self.assertFalse(any(c["family"].startswith("linear_invariant") for c in res["candidates"]), res["candidates"])

    def test_invariant_without_units_does_not_inflate_denominator_with_1e20_column(self) -> None:
        """Finding 1 (no --units): anchor_sd (not max of all column SDs) scales linear_invariant residuals."""
        rows: list[dict[str, float]] = []
        two_pi = 2.0 * math.pi
        for i in range(1, 41):
            gm = 1.327e20 * (0.3 + 0.05 * i)
            a_m = 1.5e10 * (1.0 + 0.15 * i)
            p_s = two_pi * (a_m ** 1.5) * (gm ** -0.5)
            rows.append({"P_s": p_s, "a_m": a_m, "GM": gm})

        res = conjecture.discover_laws(rows, target="__invariant__", predictors=["P_s", "a_m", "GM"], seed=0)
        top = res["candidates"][0]
        self.assertEqual(top["family"], "monomial_invariant", res["candidates"])
        self.assertTrue(res["beats_null"], res)

    def test_dis6_beats_null_false_does_not_contaminate_unrelated_section4_claims_on_same_source(self) -> None:
        """Finding 2: beats_null=false in conjectures_invariant.json must not flag unrelated Section 4 claims citing [@C1]."""
        inv_rec = {
            "target": "__invariant__",
            "predictors": ["P_s", "a_m", "GM"],
            "train_count": 30,
            "holdout_count": 10,
            "beats_null": False,
            "source_ids": ["C1"],
            "data_file": "appendix/data/exoplanets_clean.csv",
            "data_sha256": "a" * 64,
            "candidates": [{"id": "C_INV_1", "expr": "P_s * a_m^(-3/2) * GM^(1/2) = 6.27"}],
            "warnings": [],
        }
        inv_rec["sha256"] = conjecture.compute_conjectures_sha256(inv_rec)

        report_clean = (
            "# Report\n\n"
            "## 4. Findings\n"
            "Fitting a global mass-radius power law fails across gas giants with slope -0.045 [@C1; @C2] `[Strong]`.\n"
            "The invariant search in appendix/conjectures_invariant.json (`C_INV_1`) stayed `[Preliminary]`.\n\n"
            "## 6. Claim-Evidence Matrix\n"
            "| Claim | Discipline | Evidence | Confidence | Falsifier |\n"
            "| :- | :- | :- | :- | :- |\n"
            "| Mass-radius breaks down | Physics | [@C1; @C2] | `[Moderate]` | Test |\n"
        )
        report_bad = (
            "# Report\n\n"
            "## 4. Findings\n"
            "The invariant `C_INV_1` from appendix/conjectures_invariant.json holds universally [@C1] `[Moderate]`.\n\n"
            "## 6. Claim-Evidence Matrix\n"
            "| Claim | Discipline | Evidence | Confidence | Falsifier |\n"
            "| :- | :- | :- | :- | :- |\n"
            "| Mass-radius breaks down | Physics | [@C1; @C2] | `[Moderate]` | Test |\n"
        )
        sources = [
            {"claim_id": "C1", "kind": "data", "tier": "Tier 1", "url": "appendix/data/exoplanets_clean.csv", "sha256": "a" * 64},
            {"claim_id": "C2", "kind": "literature", "tier": "Tier 1", "url": "https://doi.org/10.3847/x", "sha256": "b" * 64},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "appendix"
            app.mkdir()
            (app / "conjectures_invariant.json").write_text(json.dumps(inv_rec), encoding="utf-8")

            pos_clean = {"Findings": report_clean.index("## 4. Findings"), "Claim-Evidence Matrix": report_clean.index("## 6.")}
            errs_c, warns_c = checks_conjecture.check_conjectures(root, report_clean, pos_clean, sources, level=3)
            self.assertEqual([m for m in errs_c + warns_c if "beats_null=false" in m], [], errs_c + warns_c)

            pos_bad = {"Findings": report_bad.index("## 4. Findings"), "Claim-Evidence Matrix": report_bad.index("## 6.")}
            errs_b, warns_b = checks_conjecture.check_conjectures(root, report_bad, pos_bad, sources, level=3)
            self.assertTrue(any("beats_null=false" in m for m in errs_b + warns_b), errs_b + warns_b)

    def test_prereg_accepts_derived_file_documented_in_section3_when_download_log_exists(self) -> None:
        """Finding 3: a derived CSV documented in Section 3 alongside download_log.csv passes P2-PREREG cleanly."""
        tmp, ws = M.fresh_workspace()
        try:
            M.m29_data_file_added_after_prereg(ws)
            # Add a real downloaded parent file in download_log.csv AND document parameters.csv in Section 3
            (ws / "appendix" / "download_log.csv").write_text(
                "file,url,retrieved_utc,bytes,sha256\n"
                "raw_parent.csv,https://example.org/raw_parent.csv,2026-11-20T09:00:00Z,10," + "c" * 64 + "\n",
                encoding="utf-8",
            )
            M._edit(
                ws,
                "report.md",
                "## 4. Findings",
                "Derived table `appendix/data/parameters.csv` was filtered deterministically from `raw_parent.csv`.\n\n## 4. Findings",
            )
            M.restamp_gates(ws)
            _, warns = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws
            )
            self.assertFalse(any("parameters.csv" in w and "after preregistration" in w for w in warns), warns)
        finally:
            tmp.cleanup()

    def test_local_data_register_cli_accepts_selection_and_retrieved_utc(self) -> None:
        """Finding 4: `local_data.py register` CLI exposes --selection and --retrieved-utc."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "appendix"
            data = app / "data"
            data.mkdir(parents=True)
            csv_p = data / "clean.csv"
            csv_p.write_text("x,y\n1,2\n", encoding="utf-8")
            sources_p = app / "sources.csv"
            res = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS_DIR / "local_data.py"),
                    "register", str(csv_p),
                    "--sources", str(sources_p),
                    "--tier", "Tier 1",
                    "--title", "Derived NASA Table",
                    "--claim", "C7",
                    "--selection", "agent-fetched",
                    "--retrieved-utc", "2026-11-27T01:27:20Z",
                ],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            with sources_p.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["selection"], "agent-fetched")
            self.assertEqual(rows[0]["retrieved_utc"], "2026-11-27T01:27:20Z")
            self.assertEqual(len(rows[0]["sha256"]), 64)

    def test_formal_math_check_register_defaults_to_tier3_when_no_toolchain(self) -> None:
        """Finding 6: `formal_math.py check --register` defaults to Tier 3 on unverified_no_toolchain unless --tier is explicit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "appendix"
            formal_math.init_project(app, "demo_law", theorem_name="main_claim")
            cli_env = {"PATH": "", "HOME": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
            if os.name == "nt":
                for _k in ("SYSTEMROOT", "COMSPEC"):
                    if os.environ.get(_k):
                        cli_env[_k] = os.environ[_k]
            res_auto = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS_DIR / "formal_math.py"),
                    "check", "demo_law", "--appendix", str(app), "--register", "--claim", "FM1",
                ],
                env=cli_env, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            # Exit code 2 for unverified_no_toolchain, AND registered cleanly as Tier 3
            self.assertEqual(res_auto.returncode, 2, res_auto.stdout + res_auto.stderr)
            with (app / "sources.csv").open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["tier"], "Tier 3")

            # Explicit --tier "Tier 1" must still be refused with exit code 1!
            res_t1 = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS_DIR / "formal_math.py"),
                    "check", "demo_law", "--appendix", str(app), "--register", "--claim", "FM2", "--tier", "Tier 1",
                ],
                env=cli_env, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(res_t1.returncode, 1, res_t1.stdout + res_t1.stderr)

    def test_reviewer_prompt_forbids_literal_template_markers_outside_quotes(self) -> None:
        """Finding 5: reviewer.md (+ agents mirror) warns Reviewer #2 not to write literal {{num:...}} markers."""
        for p in (
            REPO_ROOT / "skills" / "heurisma" / "references" / "agents" / "reviewer.md",
            REPO_ROOT / "agents" / "heurisma-reviewer.md",
        ):
            txt = p.read_text(encoding="utf-8")
            self.assertIn("{{num:", txt, f"Missing literal-marker warning in {p}")

    def test_lake_build_cache_ignored_by_qa_gate_hash_and_renderer(self) -> None:
        """Finding 7: Lean .lake build caches (containing machine-local trace paths) must not affect QA/HTML hashes or report.html."""
        import render_report
        from checks import gates

        tmp, ws = M.fresh_workspace()
        try:
            app = ws / "appendix"
            formal_math.init_project(app, "kepler_demo", theorem_name="kepler_law")
            qa_before = gates.gate_hash(ws, "qa")
            html_before = render_report.compute_source_hash(ws / "report.md", ws / "charts.json", None, app)

            lake_lib = app / "formal" / "kepler_demo" / ".lake" / "build" / "lib"
            lake_lib.mkdir(parents=True, exist_ok=True)
            (lake_lib / "Solution.trace").write_text('{"log":[{"message":"/home/alice/.elan/bin/lean"}]}', encoding="utf-8")
            (lake_lib / "Solution.olean").write_bytes(b"\x00\x01lean-binary")

            self.assertEqual(gates.gate_hash(ws, "qa"), qa_before)
            self.assertEqual(render_report.compute_source_hash(ws / "report.md", ws / "charts.json", None, app), html_before)
            rendered = render_report._render_appendices(app, render_report.I18N["en"])
            self.assertNotIn(".lake", rendered)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
