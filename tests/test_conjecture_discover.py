"""Unit tests for symbolic law discovery, holdout sealing, and P4-CONJECTURE validator checks (Task 2)."""

from __future__ import annotations

import json
import math
from pathlib import Path
import random
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


class TestConjectureDiscover(unittest.TestCase):
    def test_discovers_kepler_third_law_with_snapped_rational_exponents(self) -> None:
        import conjecture  # noqa: PLC0415

        rng = random.Random(17)
        rows: list[dict[str, float]] = []
        # T = 2*pi * a^(3/2) * M_star^(-1/2) in normalized solar units (T in yr, a in AU, M_star in M_sun: T = a^(3/2) * M^(-1/2))
        for i in range(24):
            a = 0.4 + 0.35 * i  # 0.4 .. 8.45 AU (tail holdout tests largest orbits!)
            m_star = 0.6 + 0.1 * ((i * 3) % 9)
            noise = 1.0 + rng.gauss(0.0, 0.008)
            t_orb = (a ** 1.5) * (m_star ** -0.5) * noise
            rows.append({"a": a, "M_star": m_star, "T": t_orb})

        res = conjecture.discover_laws(
            rows,
            target="T",
            predictors=["a", "M_star"],
            sort_by="a",
            holdout_mode="tail",
            holdout_fraction=0.25,
            snap_rationals=True,
            max_denom=8,
            seed=17,
        )
        self.assertTrue(res["beats_null"], res)
        self.assertEqual(res["holdout_mode"], "tail")
        self.assertGreaterEqual(res["holdout_count"], 6)
        self.assertEqual(res["train_count"] + res["holdout_count"], 24)
        top = res["candidates"][0]
        self.assertEqual(top["exponents"].get("a"), "3/2")
        self.assertEqual(top["exponents"].get("M_star"), "-1/2")
        self.assertGreater(top["holdout_r2"], 0.99)

    def test_dimensional_constraints_guide_discovery_and_reject_incompatible_units(self) -> None:
        import conjecture  # noqa: PLC0415

        # Simple pendulum T = 2*pi * sqrt(L / g), mass m is irrelevant noise
        rng = random.Random(99)
        rows: list[dict[str, float]] = []
        for i in range(16):
            length = 0.25 + 0.25 * i
            grav = 9.81 if i % 2 == 0 else 3.71  # Earth vs Mars
            mass = 0.1 + 5.0 * rng.random()
            period = 2.0 * math.pi * math.sqrt(length / grav) * (1.0 + rng.gauss(0.0, 0.003))
            rows.append({"L": length, "g": grav, "m": mass, "t_period": period})

        res = conjecture.discover_laws(
            rows,
            target="t_period",
            predictors=["L", "g", "m"],
            units={"L": "m", "g": "m/s^2", "m": "kg", "t_period": "s"},
            sort_by="L",
        )
        self.assertTrue(res["beats_null"])
        top = res["candidates"][0]
        self.assertEqual(top["exponents"].get("L"), "1/2")
        self.assertEqual(top["exponents"].get("g"), "-1/2")
        self.assertEqual(top["exponents"].get("m", "0"), "0")

        # Orphan target unit (Kelvin) when predictors are mechanical raises UnitError
        with self.assertRaises(conjecture.UnitError):
            conjecture.discover_laws(
                rows,
                target="t_period",
                predictors=["L", "g", "m"],
                units={"L": "m", "g": "m/s^2", "m": "kg", "t_period": "K"},
            )

    def test_pure_noise_does_not_beat_null_baseline_across_200_seeds(self) -> None:
        """P-02 & P-09: Holdout is never used for selection, and across 200 Gaussian noise seeds false positives stay <= 2%."""
        import conjecture  # noqa: PLC0415

        false_positives = 0
        for seed in range(200):
            rng = random.Random(1000 + seed)
            rows = [
                {
                    "x1": 1.0 + 9.0 * rng.random(),
                    "x2": 1.0 + 9.0 * rng.random(),
                    "y": rng.gauss(10.0, 1.5),
                }
                for _ in range(40)
            ]
            res = conjecture.discover_laws(rows, target="y", predictors=["x1", "x2"], seed=seed)
            self.assertGreaterEqual(res.get("n_candidates_evaluated", 0), 5)
            self.assertEqual(res.get("likelihood_scale"), "additive_gaussian_y")
            self.assertIn("val_rmse", res["candidates"][0])
            if res["beats_null"]:
                false_positives += 1
        self.assertLessEqual(false_positives, 4, f"False positive rate too high: {false_positives}/200")

    def test_saturating_michaelis_menten_curve_is_not_forced_into_power_law(self) -> None:
        """P-09: Trap dataset y = 10*x / (1 + 2*x) selects rational_ratio rather than overfitting a power law."""
        import conjecture  # noqa: PLC0415

        rows = []
        for i in range(20):
            x = 0.2 + 0.4 * i  # 0.2 .. 7.8 (saturates near 5.0 in tail holdout)
            rows.append({"x": x, "y": (10.0 * x) / (1.0 + 2.0 * x)})
        res = conjecture.discover_laws(rows, target="y", predictors=["x"], sort_by="x")
        self.assertTrue(res["beats_null"])
        top = res["candidates"][0]
        self.assertEqual(top["family"], "rational_ratio", top)
        self.assertGreater(top["holdout_r2"], 0.99)

    def test_large_scale_predictor_preserves_nonzero_intercept(self) -> None:
        """Review Important #3: Large predictor scale (~1e8) must not shrink intercept c0 toward zero via isotropic ridge."""
        import conjecture  # noqa: PLC0415

        rows = [{"x": 1.0e8 * (i + 1), "y": 500.0 + 1.0e-6 * (1.0e8 * (i + 1))} for i in range(16)]
        res = conjecture.discover_laws(rows, target="y", predictors=["x"], sort_by="x")
        self.assertTrue(res["beats_null"])
        top = res["candidates"][0]
        self.assertAlmostEqual(top["parameters"]["c0"], 500.0, delta=0.5)

    def test_holdout_domain_or_pole_never_leaks_into_candidate_pool_count(self) -> None:
        """Review Important #1: Changing only holdout values cannot alter n_candidates_evaluated or pre-holdout candidate selection."""
        import conjecture  # noqa: PLC0415

        # Use an explicit monotone index `idx` for tail split so train rows 0..11 are 100% identical
        rows_a = [{"idx": float(i), "x": float(i + 1), "y": 10.0 + 2.0 * float(i + 1)} for i in range(16)]
        rows_b = [dict(r) for r in rows_a]
        for j in range(12, 16):
            rows_b[j]["x"] = -5.0  # non-positive x ONLY in holdout!
        res_a = conjecture.discover_laws(rows_a, target="y", predictors=["x"], sort_by="idx")
        res_b = conjecture.discover_laws(rows_b, target="y", predictors=["x"], sort_by="idx")
        self.assertEqual(res_a["n_candidates_evaluated"], res_b["n_candidates_evaluated"])

    def test_conservation_invariant_discovery_finds_constant_energy(self) -> None:
        import conjecture  # noqa: PLC0415

        # Free-fall trajectory with constant total mechanical energy K + U = E0 = 100 J
        rows = []
        for i in range(16):
            u_pot = 10.0 + 5.0 * i
            k_kin = 100.0 - u_pot
            rows.append({"K": k_kin, "U": u_pot})
        res = conjecture.discover_laws(rows, target="__invariant__", predictors=["K", "U"], seed=7)
        self.assertTrue(res["beats_null"], res)
        self.assertIn("K", res["candidates"][0]["expr"])
        self.assertIn("U", res["candidates"][0]["expr"])

    def test_degenerate_negative_nan_or_tiny_inputs_fail_cleanly_without_nan_json(self) -> None:
        import conjecture  # noqa: PLC0415

        # Too few rows (< 8) -> ConjectureError
        tiny = [{"x": float(i), "y": float(2 * i)} for i in range(4)]
        with self.assertRaises(conjecture.ConjectureError):
            conjecture.discover_laws(tiny, target="y", predictors=["x"])

        # NaN in input -> ConjectureError
        bad_nan = [{"x": float(i + 1), "y": float("nan") if i == 3 else float(i)} for i in range(10)]
        with self.assertRaises(conjecture.ConjectureError):
            conjecture.discover_laws(bad_nan, target="y", predictors=["x"])

        # Negative x values skip log-domain gracefully without math domain error and seal strict JSON
        neg_rows = [{"x": -5.0 + float(i), "y": 3.0 + 2.0 * (-5.0 + float(i))} for i in range(12)]
        res = conjecture.discover_laws(neg_rows, target="y", predictors=["x"])
        self.assertTrue(res["beats_null"])
        with tempfile.TemporaryDirectory() as tmp:
            rep = Path(tmp)
            (rep / "appendix").mkdir()
            sealed_path = conjecture.seal_conjectures(rep, res)
            raw_json = sealed_path.read_text(encoding="utf-8")
            self.assertNotIn("NaN", raw_json)
            self.assertNotIn("Infinity", raw_json)
            loaded = json.loads(raw_json)
            self.assertIn("sha256", loaded)
            self.assertIn("falsifier_prediction", loaded)

    def test_cli_discover_writes_sealed_conjectures_json(self) -> None:
        script = SCRIPTS_DIR / "conjecture.py"
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            data_dir = ws / "appendix" / "data"
            data_dir.mkdir(parents=True)
            csv_path = data_dir / "orbits.csv"
            lines = ["a,M_star,T"]
            for i in range(16):
                a = 0.5 + 0.4 * i
                m_s = 1.0 + 0.2 * (i % 3)
                lines.append(f"{a:.4f},{m_s:.4f},{(a ** 1.5) * (m_s ** -0.5):.6f}")
            csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            out_json = ws / "appendix" / "conjectures.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(script),
                    "discover",
                    str(csv_path),
                    "--target",
                    "T",
                    "--predictors",
                    "a,M_star",
                    "--sort-by",
                    "a",
                    "--out",
                    str(out_json),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            sealed = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertTrue(sealed["beats_null"])
            self.assertEqual(sealed["candidates"][0]["exponents"]["a"], "3/2")

    def test_validator_catches_tampered_sha_zero_holdout_beats_null_false_and_strong_conjecture(self) -> None:
        from checks import codes  # noqa: PLC0415
        import mutations as M  # noqa: PLC0415
        import validate_report  # noqa: PLC0415

        # M58: zero holdout
        msgs_m58 = M.run_mutation("M58")
        self.assertTrue(M.caught("M58", msgs_m58), msgs_m58)
        p4_m58 = [m for m in msgs_m58 if codes.classify_message(m)[0] == "P4-CONJECTURE"]
        self.assertTrue(p4_m58, msgs_m58)

        # M59: [Strong] on unproved conjecture
        msgs_m59 = M.run_mutation("M59")
        self.assertTrue(M.caught("M59", msgs_m59), msgs_m59)
        p4_m59 = [m for m in msgs_m59 if codes.classify_message(m)[0] == "P4-CONJECTURE"]
        self.assertTrue(p4_m59, msgs_m59)

        # Tampered sha256 in conjectures.json
        tmp, ws = M.fresh_workspace()
        try:
            payload = M._conjecture_payload(train_count=12, holdout_count=4)
            payload["train_count"] = 99  # tamper after sealing
            (ws / "appendix" / "conjectures.json").write_text(json.dumps(payload), encoding="utf-8")
            M.restamp_gates(ws)
            errs, _ = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws)
            self.assertTrue(any("sha256 mismatch" in e for e in errs), errs)

            # beats_null=False while Section 4 claims conjectured law at [Moderate]
            payload_null = M._conjecture_payload(train_count=12, holdout_count=4, beats_null=False)
            (ws / "appendix" / "conjectures.json").write_text(json.dumps(payload_null), encoding="utf-8")
            M._edit(
                ws,
                "report.md",
                "### 4.1 Retention",
                "Conjectured law C_LAW_1 (`attrition_12m = 0.25 * mentoring_hrs_wk^(-1/2)`) holds `[Moderate]` [@C4].\n\n### 4.1 Retention",
            )
            M.restamp_gates(ws)
            errs3, warns2 = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws)
            self.assertTrue(any("beats_null" in m for m in errs3 + warns2), errs3 + warns2)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
