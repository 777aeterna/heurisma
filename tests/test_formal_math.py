"""Unit tests for Lean 4 / anthropics/formal-math Lake adapter (Phase 1 Task 3, audit-hardened)."""

from __future__ import annotations

import csv
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "heurisma" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _write_cross_platform_exe(bin_dir: Path, name: str, py_body: str) -> Path:
    """Create an executable fake binary that works on POSIX (via sys.executable shebang) and Windows (.cmd wrapper)."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        py_helper = bin_dir / f"_{name}_impl.py"
        py_helper.write_text(py_body, encoding="utf-8")
        cmd_path = bin_dir / f"{name}.cmd"
        cmd_path.write_text(f'@"{sys.executable}" -B "%~dp0_{name}_impl.py" %*\r\n', encoding="utf-8")
        return cmd_path
    exe_path = bin_dir / name
    exe_path.write_text(f"#!{sys.executable}\n" + py_body, encoding="utf-8")
    exe_path.chmod(exe_path.stat().st_mode | stat.S_IXUSR)
    return exe_path


def _make_fake_toolchain(
    bin_dir: Path,
    *,
    axioms_line: str = "'Solution.main_claim' depends on axioms: [propext, Classical.choice]",
    build_rc: int = 0,
    audit_rc: int = 0,
    record_env_file: Path | None = None,
) -> tuple[Path, Path]:
    """Create deterministic fake `lake` and `lean` executables in bin_dir."""
    lean_body = (
        "import pathlib, sys\n"
        "if '--version' in sys.argv:\n"
        "    print('Lean (version 4.16.0, commit fake000, Release)')\n"
        "    sys.exit(0)\n"
        "audit_files = [a for a in sys.argv[1:] if a.endswith('.lean')]\n"
        "if audit_files:\n"
        "    p = pathlib.Path(audit_files[-1])\n"
        "    if p.is_file():\n"
        "        pathlib.Path('_last_audit_seen.txt').write_text(p.read_text(encoding='utf-8'), encoding='utf-8')\n"
        f"print({axioms_line!r})\n"
        f"sys.exit({audit_rc})\n"
    )
    lean_path = _write_cross_platform_exe(bin_dir, "lean", lean_body)

    env_dump = (
        f"import json, os, pathlib; pathlib.Path({str(record_env_file)!r}).write_text(json.dumps(dict(os.environ)), encoding='utf-8')\n"
        if record_env_file is not None
        else ""
    )
    lake_body = (
        "import subprocess, sys\n"
        f"{env_dump}"
        "args = sys.argv[1:]\n"
        "if '--version' in args:\n"
        "    print('Lake version 5.0.0 (Lean version 4.16.0)')\n"
        "    sys.exit(0)\n"
        "if args and args[0] == 'exe' and 'cache' in args:\n"
        "    sys.stderr.write('FORBIDDEN_CACHE_FETCH\\n')\n"
        "    sys.exit(99)\n"
        "if args and args[0] == 'build':\n"
        f"    sys.exit({build_rc})\n"
        "if len(args) >= 3 and args[0] == 'env':\n"
        "    proc = subprocess.run(args[1:], capture_output=True, text=True, encoding='utf-8')\n"
        "    sys.stdout.write(proc.stdout)\n"
        "    sys.stderr.write(proc.stderr)\n"
        "    sys.exit(proc.returncode)\n"
        "sys.exit(0)\n"
    )
    lake_path = _write_cross_platform_exe(bin_dir, "lake", lake_body)
    return lake_path, lean_path


class TestFormalMathAdapter(unittest.TestCase):
    def test_nested_comments_strings_and_challenge_sorry_policy(self) -> None:
        """P-07 & Review Focus #1/#2: Challenge.lean may use `sorry` for its target stub; Solution.lean may never."""
        import formal_math  # noqa: PLC0415

        challenge_with_sorry = (
            "/- Outer comment\n"
            "   /- Nested block comment mentioning (h : False) and axiom fake : False -/\n"
            "-/\n"
            "-- line comment mentioning sorry and : True :=\n"
            'def note : String := "sorry admit axiom @[extern]"\n'
            "namespace Challenge\n"
            "theorem main_claim (n : Nat) : n + 0 = n := by sorry\n"
            "end Challenge\n"
        )
        clean_solution = (
            "import Challenge\n"
            "/- /- nested sorry -/ -/\n"
            "namespace Solution\n"
            "theorem main_claim (n : Nat) : n + 0 = n := Nat.add_zero n\n"
            "end Solution\n"
        )
        scan_ok = formal_math.scan_lean_hazards(challenge_with_sorry, clean_solution)
        self.assertTrue(scan_ok["clean"], scan_ok)
        self.assertEqual(scan_ok["sorries"], 0)
        self.assertEqual(scan_ok["challenge_sorries"], 1)
        self.assertIn("main_claim", scan_ok["theorem_names"])

        # Solution.lean calling Challenge.main_claim (which had sorry) is caught statically too
        cheating_call = (
            "import Challenge\nnamespace Solution\n"
            "theorem main_claim (n : Nat) : n + 0 = n := Challenge.main_claim n\n"
            "end Solution\n"
        )
        res_cheat = formal_math.scan_lean_hazards(challenge_with_sorry, cheating_call)
        self.assertFalse(res_cheat["clean"], res_cheat)

        # Real hazards outside comments in Solution.lean are caught
        dirty_cases = [
            ("sorry_after_closed_comment", "import Challenge\n/- closed -/ theorem main_claim (n : Nat) : n + 0 = n := by sorry\n"),
            ("implemented_by_escape", "import Challenge\n@[implemented_by fake] def f : Nat := 0\n"),
            ("custom_axiom", "import Challenge\naxiom cheat : False\n"),
            ("native_decide_escape", "import Challenge\ntheorem main_claim (n : Nat) : n + 0 = n := by native_decide\n"),
        ]
        for label, bad_sol in dirty_cases:
            with self.subTest(label=label):
                res = formal_math.scan_lean_hazards(challenge_with_sorry, bad_sol)
                self.assertFalse(res["clean"], f"{label} was not caught: {res}")
                self.assertTrue(res["solution_hazards"], res)

        # Custom axiom in Challenge.lean IS forbidden (only sorry is tolerated as proof placeholder)
        ax_in_challenge = formal_math.scan_lean_hazards("axiom magic : False\n", clean_solution)
        self.assertFalse(ax_in_challenge["clean"])
        self.assertIn("axiom", ax_in_challenge["challenge_hazards"])

        # Vacuous and trivial Challenge.lean statements are caught
        vacuous = formal_math.scan_lean_hazards("theorem main_claim (h : False) : 1 = 2 := by sorry\n", clean_solution)
        self.assertFalse(vacuous["clean"])
        self.assertTrue(vacuous["vacuous_or_trivial"])

        trivial = formal_math.scan_lean_hazards("theorem main_claim : True := trivial\n", clean_solution)
        self.assertFalse(trivial["clean"])
        self.assertTrue(trivial["vacuous_or_trivial"])

    def test_init_creates_layout_supports_mathlib_and_bridges_from_conjecture(self) -> None:
        """P-06: init supports --mathlib and --toolchain and bridges conjectures."""
        import conjecture  # noqa: PLC0415
        import formal_math  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            app = ws / "appendix"
            app.mkdir()
            conjecture.seal_conjectures(
                ws,
                {
                    "target": "T",
                    "predictors": ["a", "M_star"],
                    "train_count": 12,
                    "holdout_count": 4,
                    "holdout_mode": "tail",
                    "beats_null": True,
                    "candidates": [
                        {
                            "id": "C_LAW_1",
                            "family": "power_law_rational",
                            "expr": "T = 1 * a^(3/2) * M_star^(-1/2)",
                            "exponents": {"a": "3/2", "M_star": "-1/2"},
                            "complexity_k": 2,
                            "train_bic": -80.0,
                            "holdout_rmse": 0.001,
                            "holdout_r2": 0.999,
                        }
                    ],
                    "falsifier_prediction": "Test at a = 15 AU.",
                },
            )
            proj = formal_math.init_project(
                app,
                "kepler_scaling",
                from_conjecture="C_LAW_1",
                toolchain="leanprover/lean4:v4.29.0",
                mathlib=True,
            )
            for fname in ("lean-toolchain", "lakefile.toml", "Challenge.lean", "Solution.lean", "README.md"):
                self.assertTrue((proj / fname).is_file(), f"Missing {fname}")
            self.assertEqual((proj / "lean-toolchain").read_text(encoding="utf-8").strip(), "leanprover/lean4:v4.29.0")
            self.assertIn("mathlib", (proj / "lakefile.toml").read_text(encoding="utf-8"))
            ch_text = (proj / "Challenge.lean").read_text(encoding="utf-8")
            self.assertIn("C_LAW_1", ch_text)
            self.assertIn("T = 1 * a^(3/2) * M_star^(-1/2)", ch_text)

    def test_check_enforces_challenge_solution_statement_match_axioms_comparator_and_offline_git_lock(self) -> None:
        """P-01 & P-05: Kernel witness checks Challenge <-> Solution statement match, optional comparator, and offline git lock."""
        import formal_math  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            app = ws / "appendix"
            proj = formal_math.init_project(
                app,
                "nat_id",
                theorem_name="main_claim",
                statement="(n : Nat) : n + 0 = n",
            )
            env_log = ws / "env_dump.json"
            bin_ok = ws / "bin_ok"
            lake_ok, lean_ok = _make_fake_toolchain(
                bin_ok,
                axioms_line="'Solution.main_claim' depends on axioms: [propext, Classical.choice]",
                record_env_file=env_log,
            )
            env_ok = {
                "PATH": str(bin_ok),
                "HOME": str(ws),
                "HEURISMA_LAKE": str(lake_ok),
                "HEURISMA_LEAN": str(lean_ok),
                "HEURISMA_OFFLINE": "1",
            }
            res_ok = formal_math.check_project(app, "nat_id", env=env_ok)
            self.assertEqual(res_ok["status"], "kernel-verified", res_ok)
            self.assertEqual(res_ok["verification_mode"], "kernel-defeq")
            # Confirm _HeurismaAxiomAudit.lean enforced _heurisma_same_stmt (@Challenge.main_claim) (@Solution.main_claim)
            audit_seen = (proj / "_last_audit_seen.txt").read_text(encoding="utf-8")
            self.assertIn("_heurisma_same_stmt", audit_seen)
            self.assertIn("@Challenge.main_claim", audit_seen)
            self.assertIn("@Solution.main_claim", audit_seen)
            (proj / "_last_audit_seen.txt").unlink()
            # Confirm HEURISMA_OFFLINE=1 locked git network protocols during lake build (P-05)
            dumped_env = json.loads(env_log.read_text(encoding="utf-8"))
            self.assertEqual(dumped_env.get("GIT_CONFIG_VALUE_0"), "never")

            # Statement mismatch: Solution.lean proves a different theorem (1 = 1) than Challenge.lean (n + 0 = n)
            # -> FMT-9 emits a signature_warnings note and delegates definitional equality to the Lean kernel witness!
            (proj / "Solution.lean").write_text(
                "import Challenge\nnamespace Solution\ntheorem main_claim : 1 = 1 := rfl\nend Solution\n",
                encoding="utf-8",
            )
            bin_mismatch = ws / "bin_mismatch"
            lake_m, lean_m = _make_fake_toolchain(bin_mismatch, audit_rc=1)
            env_mismatch = dict(env_ok, PATH=str(bin_mismatch), HEURISMA_LAKE=str(lake_m), HEURISMA_LEAN=str(lean_m))
            res_mismatch = formal_math.check_project(app, "nat_id", env=env_mismatch)
            self.assertTrue(res_mismatch.get("signature_warnings"), res_mismatch)
            self.assertNotEqual(res_mismatch["status"], "kernel-verified", res_mismatch)

            # Review Important #2: Omitting `namespace Challenge` cannot bypass statement pairing or kernel witness!
            (proj / "Challenge.lean").write_text(
                "theorem main_claim (n : Nat) : n + 0 = n := by sorry\n",
                encoding="utf-8",
            )
            (proj / "Solution.lean").write_text(
                "import Challenge\ntheorem unrelated_thm : 1 = 1 := rfl\n",
                encoding="utf-8",
            )
            res_unns_bypass = formal_math.check_project(app, "nat_id", env=env_ok)
            self.assertEqual(res_unns_bypass["status"], "failed_statement_mismatch", res_unns_bypass)

            # Valid top-level `<name>_proof` pairing emits kernel `_heurisma_same_stmt (@main_claim) (@main_claim_proof)` witness
            (proj / "Solution.lean").write_text(
                "import Challenge\ntheorem main_claim_proof (n : Nat) : n + 0 = n := Nat.add_zero n\n",
                encoding="utf-8",
            )
            env_top = dict(
                env_ok,
                HEURISMA_LEAN=str(
                    _make_fake_toolchain(
                        ws / "bin_top",
                        axioms_line="'main_claim_proof' depends on axioms: [propext]",
                    )[1]
                ),
            )
            res_top_ok = formal_math.check_project(app, "nat_id", env=env_top)
            self.assertEqual(res_top_ok["status"], "kernel-verified", res_top_ok)
            audit_top = (proj / "_last_audit_seen.txt").read_text(encoding="utf-8")
            self.assertIn("_heurisma_same_stmt (@main_claim) (@main_claim_proof)", audit_top)
            (proj / "_last_audit_seen.txt").unlink()

            # Restore namespaced Challenge.lean + Solution.lean and test optional `comparator` binary (P-01)
            (proj / "Challenge.lean").write_text(
                "namespace Challenge\ntheorem main_claim (n : Nat) : n + 0 = n := by sorry\nend Challenge\n",
                encoding="utf-8",
            )
            (proj / "Solution.lean").write_text(
                "import Challenge\nnamespace Solution\ntheorem main_claim (n : Nat) : n + 0 = n := Nat.add_zero n\nend Solution\n",
                encoding="utf-8",
            )
            (proj / "comparator.json").write_text('{"challenge": "Challenge", "solution": "Solution"}\n', encoding="utf-8")
            comp_bin = _write_cross_platform_exe(bin_ok, "comparator", "import sys; print('COMPARATOR_OK'); sys.exit(0)\n")
            env_comp = dict(env_ok, HEURISMA_COMPARATOR=str(comp_bin))
            res_comp = formal_math.check_project(app, "nat_id", env=env_comp)
            self.assertEqual(res_comp["status"], "comparator-verified", res_comp)
            self.assertEqual(res_comp["verification_mode"], "comparator")

            reg = formal_math.register_formal_source(
                app, "nat_id", sources_csv=app / "sources.csv", claim_id="F1", tier="Tier 1"
            )
            self.assertEqual(reg["kind"], "formal-proof")
            self.assertEqual(reg["tier"], "Tier 1")

            # sorryAx or custom axiom -> failed_axioms & refuses Tier 1
            for bad_ax in ("[propext, sorryAx]", "[my_custom_axiom]"):
                bin_bad = ws / f"bin_{abs(hash(bad_ax))}"
                lake_b, lean_b = _make_fake_toolchain(
                    bin_bad,
                    axioms_line=f"'Solution.main_claim' depends on axioms: {bad_ax}",
                )
                env_b = {"PATH": str(bin_bad), "HOME": str(ws), "HEURISMA_LAKE": str(lake_b), "HEURISMA_LEAN": str(lean_b)}
                res_bad = formal_math.check_project(app, "nat_id", env=env_b)
                self.assertEqual(res_bad["status"], "failed_axioms", res_bad)
                with self.assertRaises(formal_math.FormalError):
                    formal_math.register_formal_source(
                        app, "nat_id", sources_csv=app / "sources_bad.csv", claim_id="F2", tier="Tier 1"
                    )

    def test_check_without_lake_records_unverified_no_toolchain_cleanly(self) -> None:
        import formal_math  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            app = ws / "appendix"
            formal_math.init_project(app, "no_lean", theorem_name="main_claim")
            empty_env = {"PATH": "", "HOME": str(ws)}
            res = formal_math.check_project(app, "no_lean", env=empty_env)
            self.assertEqual(res["status"], "unverified_no_toolchain")
            self.assertEqual(res["verification_mode"], "none")

            with self.assertRaises(formal_math.FormalError) as ctx:
                formal_math.register_formal_source(
                    app, "no_lean", sources_csv=app / "sources.csv", claim_id="F1", tier="Tier 1"
                )
            self.assertIn("Tier 3", str(ctx.exception))

            script = SCRIPTS_DIR / "formal_math.py"
            cli_env = {"PATH": "", "HOME": str(ws), "PYTHONDONTWRITEBYTECODE": "1"}
            if os.name == "nt":
                for _k in ("SYSTEMROOT", "COMSPEC"):
                    if os.environ.get(_k):
                        cli_env[_k] = os.environ[_k]
            p_soft = subprocess.run(
                [sys.executable, "-B", str(script), "check", "no_lean", "--appendix", str(app)],
                env=cli_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(p_soft.returncode, 2, p_soft.stderr)
            p_req = subprocess.run(
                [sys.executable, "-B", str(script), "check", "no_lean", "--appendix", str(app), "--require-kernel"],
                env=cli_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(p_req.returncode, 2, p_req.stderr)

    def test_fetch_ref_downloads_and_hashes_via_local_server_and_respects_offline(self) -> None:
        import formal_math  # noqa: PLC0415

        files_served = {
            "/anthropics/formal-math/main/eth/README.md": b"# ETH Formalization\n",
            "/anthropics/formal-math/main/eth/lean-toolchain": b"leanprover/lean4:v4.16.0\n",
            "/anthropics/formal-math/main/eth/lakefile.toml": b'name = "eth"\n',
            "/anthropics/formal-math/main/eth/Challenge.lean": b"namespace Challenge\ntheorem eth_bound (n : Nat) : n = n := by sorry\nend Challenge\n",
        }

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = files_served.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args: object) -> None:
                return

        srv = HTTPServer(("127.0.0.1", 0), Handler)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            from unittest.mock import patch  # noqa: PLC0415
            import fetch_lib  # noqa: PLC0415

            base_url = f"http://127.0.0.1:{srv.server_port}"
            with tempfile.TemporaryDirectory() as tmp:
                app = Path(tmp) / "appendix"
                app.mkdir()
                env = dict(os.environ, HEURISMA_GITHUB_RAW_URL=base_url)
                env.pop("HEURISMA_OFFLINE", None)
                # FMT-11: loopback raw URL override is refused by default
                with self.assertRaises(formal_math.FormalError):
                    formal_math.fetch_reference(app, "anthropics/formal-math/eth", env=env)
                # With local-test private-host guard bypassed, downloads & hashes cleanly
                with patch.object(fetch_lib, "_is_private_host", return_value=False):
                    saved = formal_math.fetch_reference(app, "anthropics/formal-math/eth", env=env)
                self.assertEqual(len(saved), 4)
                with (app / "download_log.csv").open(encoding="utf-8", newline="") as fh:
                    dl_rows = list(csv.DictReader(fh))
                self.assertEqual(len(dl_rows), 4)
                self.assertTrue(all(len(r["sha256"]) == 64 for r in dl_rows))

                app_off = Path(tmp) / "appendix_off"
                app_off.mkdir()
                old_off = os.environ.get("HEURISMA_OFFLINE")
                os.environ["HEURISMA_OFFLINE"] = "1"
                try:
                    with patch.object(fetch_lib, "_is_private_host", return_value=False):
                        saved_off = formal_math.fetch_reference(
                            app_off,
                            "anthropics/formal-math/eth",
                            env=dict(env, HEURISMA_OFFLINE="1"),
                        )
                finally:
                    if old_off is None:
                        os.environ.pop("HEURISMA_OFFLINE", None)
                    else:
                        os.environ["HEURISMA_OFFLINE"] = old_off
                self.assertEqual(saved_off, [])
                with (app_off / "data_attempts.csv").open(encoding="utf-8", newline="") as fh:
                    att_rows = list(csv.DictReader(fh))
                self.assertTrue(any(r["outcome"] == "offline mode" for r in att_rows), att_rows)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
