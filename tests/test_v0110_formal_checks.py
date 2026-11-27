"""Unit tests for P4-LEAN formal-proof validator, FORMAL-SHA256 gate anchor, and --reproduce-lean (Phase 2 Task 4)."""

from __future__ import annotations

import csv
import json
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


class TestV0110FormalChecks(unittest.TestCase):
    def test_clean_kernel_verified_formal_workspace_produces_zero_errors_and_warnings(self) -> None:
        import mutations as M  # noqa: PLC0415
        import validate_report  # noqa: PLC0415

        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws)
            M.restamp_gates(ws)
            M.rerender(ws)
            errs, warns = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws
            )
            self.assertEqual(errs, [], errs)
            self.assertEqual(warns, [], warns)
        finally:
            tmp.cleanup()

    def test_mutations_m55_m56_m57_m60_caught_as_p4_lean(self) -> None:
        from checks import codes  # noqa: PLC0415
        import mutations as M  # noqa: PLC0415

        for name in ("M55", "M56", "M57", "M60"):
            with self.subTest(mutation=name):
                msgs = M.run_mutation(name)
                self.assertTrue(M.caught(name, msgs), f"{name} missed: {msgs}")
                p4 = [m for m in msgs if codes.classify_message(m)[0] == "P4-LEAN"]
                self.assertTrue(p4, f"{name} not classified as P4-LEAN: {msgs}")

    def test_post_verify_edit_nonstandard_axiom_and_trivial_true_challenge_are_rejected(self) -> None:
        from checks import codes  # noqa: PLC0415
        import mutations as M  # noqa: PLC0415
        import validate_report  # noqa: PLC0415

        # 1. Solution.lean edited after verify.json was stamped (hash mismatch against verify.json/formal_proofs.csv)
        tmp, ws = M.fresh_workspace()
        try:
            proj = M._formal_workspace(ws)
            (proj / "Solution.lean").write_text(
                "import Challenge\nnamespace Solution\ntheorem main_claim (n : Nat) : n + 0 = n := by simp\nend Solution\n",
                encoding="utf-8",
            )
            M.restamp_gates(ws)
            errs, _ = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws
            )
            p4 = [e for e in errs if codes.classify_message(e)[0] == "P4-LEAN"]
            self.assertTrue(p4, errs)
        finally:
            tmp.cleanup()

        # 2. Non-standard axiom in formal_proofs.csv
        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws, axioms="propext;my_custom_axiom")
            M.restamp_gates(ws)
            errs, _ = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws
            )
            self.assertTrue(any("non-standard axiom" in e.lower() for e in errs), errs)
        finally:
            tmp.cleanup()

        # 3. Trivial `: True :=` in Challenge.lean
        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(
                ws,
                challenge_src="namespace Challenge\ntheorem main_claim : True := trivial\nend Challenge\n",
                solution_src="import Challenge\nnamespace Solution\ntheorem main_claim : True := trivial\nend Solution\n",
            )
            M.restamp_gates(ws)
            errs, _ = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws
            )
            self.assertTrue(any("trivial" in e.lower() or "vacuous" in e.lower() for e in errs), errs)
        finally:
            tmp.cleanup()

    def test_p10_deductive_to_empirical_bridge_warns_only_never_hard_errors(self) -> None:
        """P-10: Empirical wording on a formal-proof-only [Strong] row emits a warning (not an error even at Level 3)."""
        from checks import codes  # noqa: PLC0415
        import mutations as M  # noqa: PLC0415
        import validate_report  # noqa: PLC0415

        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws)
            M._edit(
                ws,
                "report.md",
                "| Formal deductive identity n + 0 = n holds under Peano axioms | Formal Sciences | Lean 4 proof [@F1], Tier 1, 2026-11 | `[Strong]` | Kernel refutation |",
                "| Field experiment measured 12% higher retention in empirical survey | Labor Economics | Lean 4 proof [@F1], Tier 1, 2026-11 | `[Strong]` | New survey |",
            )
            M.restamp_gates(ws)
            errs, warns = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws
            )
            p4_warns = [w for w in warns if codes.classify_message(w)[0] == "P4-LEAN"]
            p4_errs = [e for e in errs if codes.classify_message(e)[0] == "P4-LEAN"]
            self.assertTrue(p4_warns, f"Expected P4-LEAN warning for empirical laundering, got warns={warns}")
            self.assertEqual(p4_errs, [], f"P-10 must be warning-only, not error: {p4_errs}")
        finally:
            tmp.cleanup()

    def test_reviewer_gate_header_anchors_formal_challenge_sha256(self) -> None:
        """gates.py records FORMAL-SHA256 over appendix/formal/*/Challenge.lean and flags post-review edits."""
        import mutations as M  # noqa: PLC0415
        import validate_report  # noqa: PLC0415

        tmp, ws = M.fresh_workspace()
        try:
            proj = M._formal_workspace(ws)
            proc = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS_DIR / "validate_report.py"), str(ws / "report.md"), "--gate-header", "reviewer"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("FORMAL-SHA256:", proc.stdout)

            # Write reviewer.md with the printed header, then mutate Challenge.lean without a Post-review changes section
            (ws / "appendix" / "gates" / "reviewer.md").write_text(
                proc.stdout
                + 'QUOTE: report.md:1: "Hybrid Work"\n'
                + 'QUOTE: appendix/output.txt:1: "Dataset integrity"\n\n'
                + "1. [1] Sample critique.\n"
                + "pad " * 120,
                encoding="utf-8",
            )
            (proj / "Challenge.lean").write_text(
                "namespace Challenge\ntheorem main_claim (n : Nat) : 0 + n = n := by sorry\nend Challenge\n",
                encoding="utf-8",
            )
            errs, warns = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws
            )
            self.assertTrue(any("FORMAL-SHA256" in m for m in errs + warns), errs + warns)
        finally:
            tmp.cleanup()

    def test_p04_reproduce_never_runs_lake_and_reproduce_lean_is_explicit_opt_in(self) -> None:
        """P-04: Default reproduce() never executes lake; explicit reproduce_lean() replays fake lake or skips cleanly."""
        import mutations as M  # noqa: PLC0415
        from test_formal_math import _make_fake_toolchain  # noqa: PLC0415
        import validate_report  # noqa: PLC0415

        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws)
            # 1. reproduce_lean with no lake installed -> 0 errors, 1 skip warning
            errs_skip, warns_skip = validate_report.reproduce_lean(ws, env={"PATH": "", "HOME": str(ws)})
            self.assertEqual(errs_skip, [])
            self.assertTrue(any("skipped" in w.lower() for w in warns_skip), warns_skip)

            # 2. reproduce_lean with working fake lake -> 0 errors, 0 warnings
            bin_ok = ws / "bin_ok"
            lake_ok, lean_ok = _make_fake_toolchain(
                bin_ok,
                axioms_line="'Solution.main_claim' depends on axioms: [propext, Classical.choice]",
            )
            env_ok = {"PATH": str(bin_ok), "HOME": str(ws), "HEURISMA_LAKE": str(lake_ok), "HEURISMA_LEAN": str(lean_ok)}
            errs_ok, warns_ok = validate_report.reproduce_lean(ws, env=env_ok)
            self.assertEqual(errs_ok, [], errs_ok)
            self.assertEqual(warns_ok, [], warns_ok)

            # 3. reproduce_lean with failing fake lake -> error
            bin_bad = ws / "bin_bad"
            lake_b, lean_b = _make_fake_toolchain(bin_bad, build_rc=1)
            env_bad = {"PATH": str(bin_bad), "HOME": str(ws), "HEURISMA_LAKE": str(lake_b), "HEURISMA_LEAN": str(lean_b)}
            errs_bad, _ = validate_report.reproduce_lean(ws, env=env_bad)
            self.assertTrue(errs_bad, "Expected reproduce_lean error on failing lake build")
            self.assertTrue(any("reproduce: formal_math" in e for e in errs_bad), errs_bad)
        finally:
            tmp.cleanup()

    def test_review_critical_short_sha_prefix_rejected(self) -> None:
        """Critical #1: 1-char or malformed hex prefixes in formal_proofs.csv / verify.json must fail."""
        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws)
            reg_p = ws / "appendix" / "formal_proofs.csv"
            with reg_p.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
                cols = list(rows[0].keys())
            # Replace with 1-char matching prefix
            rows[0]["challenge_sha256"] = rows[0]["challenge_sha256"][:1]
            with reg_p.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            md = (ws / "report.md").read_text(encoding="utf-8")
            errs = validate_report.validate_report(md, level=2, report_dir=ws)
            self.assertTrue(any("SHA-256" in e for e in errs), errs)
            self.assertTrue(all(validate_report.classify_message(e)[0] == "P4-LEAN" for e in errs if "SHA-256" in e), errs)
        finally:
            tmp.cleanup()

    def test_review_critical_tier2_failed_formal_proof_rejected(self) -> None:
        """Critical #2: Tier 2 formal-proof with status=failed_hazards must be rejected."""
        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws)
            reg_p = ws / "appendix" / "formal_proofs.csv"
            with reg_p.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
                cols = list(rows[0].keys())
            pid = rows[0]["proof_id"]
            # Downgrade source tier to Tier 2 and remove [Strong] claim citation so only Tier 2 triggers
            src_p = ws / "appendix" / "sources.csv"
            with src_p.open(encoding="utf-8", newline="") as fh:
                srows = list(csv.DictReader(fh))
                scols = list(srows[0].keys())
            for r in srows:
                if r["claim_id"] == pid or r.get("kind") == "formal-proof":
                    r["tier"] = "Tier 2"
            with src_p.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=scols, lineterminator="\n")
                w.writeheader()
                w.writerows(srows)
            rows[0]["status"] = "failed_hazards"
            with reg_p.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            md = (ws / "report.md").read_text(encoding="utf-8").replace("[Strong]", "[Moderate]")
            (ws / "report.md").write_text(md, encoding="utf-8")
            errs = validate_report.validate_report(md, level=2, report_dir=ws)
            self.assertTrue(any("failed_hazards" in e for e in errs), errs)
        finally:
            tmp.cleanup()

    def test_review_critical_reproduce_lean_clears_prebuilt_lake_build(self) -> None:
        """Critical #3: reproduce_lean() must remove pre-built .lake/build before running lake."""
        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws)
            with (ws / "appendix" / "formal_proofs.csv").open(encoding="utf-8", newline="") as fh:
                slug = next(csv.DictReader(fh))["slug"]
            stale = ws / "appendix" / "formal" / slug / ".lake" / "build" / "stale.olean"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text("stale-olean", encoding="utf-8")

            bin_dir = ws / "bin_check_clean"
            bin_dir.mkdir(parents=True, exist_ok=True)
            lake_p = bin_dir / "lake"
            lean_p = bin_dir / "lean"
            # Fake lake fails if .lake/build/stale.olean still exists in CWD!
            lake_p.write_text(
                f"#!{sys.executable}\n"
                "import pathlib, sys\n"
                "if (pathlib.Path('.lake') / 'build' / 'stale.olean').exists():\n"
                "    sys.stderr.write('STALE_OLEAN_NOT_CLEARED\\n')\n"
                "    sys.exit(2)\n"
                "if 'env' in sys.argv:\n"
                "    print(\"'Solution.main_claim' depends on axioms: [propext]\")\n"
                "sys.exit(0)\n",
                encoding="utf-8",
            )
            lean_p.write_text(f"#!{sys.executable}\nprint('Lean 4.14.0')\n", encoding="utf-8")
            lake_p.chmod(0o755)
            lean_p.chmod(0o755)

            env = {"PATH": str(bin_dir), "HOME": str(ws), "HEURISMA_LAKE": str(lake_p), "HEURISMA_LEAN": str(lean_p)}
            errs, _ = validate_report.reproduce_lean(ws, env=env)
            self.assertEqual(errs, [], errs)
        finally:
            tmp.cleanup()

    def test_review_important_empty_challenge_and_verify_json_crosschecks(self) -> None:
        """Important #4 & #5: empty Challenge.lean, blank sorries, and tampered verify.json fields must fail."""
        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws)
            reg_p = ws / "appendix" / "formal_proofs.csv"
            with reg_p.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
                cols = list(rows[0].keys())
            slug = rows[0]["slug"]
            proj = ws / "appendix" / "formal" / slug
            (proj / "Challenge.lean").write_text("namespace Challenge\ndef x : Nat := 1\nend Challenge\n", encoding="utf-8")
            (proj / "Solution.lean").write_text("import Challenge\nnamespace Solution\ndef y : Nat := 1\nend Solution\n", encoding="utf-8")
            ch_sha = validate_report._file_sha256(proj / "Challenge.lean")
            sol_sha = validate_report._file_sha256(proj / "Solution.lean")
            rows[0]["challenge_sha256"] = ch_sha
            rows[0]["solution_sha256"] = sol_sha
            rows[0]["sorries"] = ""
            with reg_p.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            vdata = json.loads((proj / "verify.json").read_text(encoding="utf-8"))
            vdata["challenge_sha256"] = ch_sha
            vdata["solution_sha256"] = sol_sha
            vdata["sorries"] = 1
            vdata["statement_paired"] = False
            (proj / "verify.json").write_text(json.dumps(vdata, indent=2) + "\n", encoding="utf-8")

            md = (ws / "report.md").read_text(encoding="utf-8")
            errs = validate_report.validate_report(md, level=2, report_dir=ws)
            self.assertTrue(any("no theorem" in e.lower() for e in errs), errs)
            self.assertTrue(any("sorries" in e.lower() for e in errs), errs)
            self.assertTrue(any("statement_paired" in e.lower() for e in errs), errs)
        finally:
            tmp.cleanup()

    def test_review_minor_comparator_downgrade_warns_in_reproduce_lean(self) -> None:
        """Minor #7: reproduce_lean emits a warning if comparator-verified downgrades to kernel-verified."""
        tmp, ws = M.fresh_workspace()
        try:
            M._formal_workspace(ws)
            reg_p = ws / "appendix" / "formal_proofs.csv"
            with reg_p.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
                cols = list(rows[0].keys())
            rows[0]["status"] = "comparator-verified"
            with reg_p.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            bin_ok = ws / "bin_ok"
            lake_ok, lean_ok = _make_fake_toolchain(
                bin_ok,
                axioms_line="'Solution.main_claim' depends on axioms: [propext]",
            )
            env_ok = {"PATH": str(bin_ok), "HOME": str(ws), "HEURISMA_LAKE": str(lake_ok), "HEURISMA_LEAN": str(lean_ok)}
            errs, warns = validate_report.reproduce_lean(ws, env=env_ok)
            self.assertEqual(errs, [], errs)
            self.assertTrue(any("comparator" in w.lower() for w in warns), warns)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
