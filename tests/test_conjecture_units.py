"""Unit tests for exact rational dimensional analysis and Buckingham Pi (Task 1)."""

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "heurisma" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestConjectureUnits(unittest.TestCase):
    def test_parse_unit_exact_rational_vectors_and_derived_si(self) -> None:
        import conjecture  # noqa: PLC0415

        self.assertEqual(conjecture.DIMENSIONS, ("M", "L", "T", "Theta", "I", "N"))
        # J = kg * m^2 / s^2 -> (1, 2, -2, 0, 0, 0)
        want_joule = (Fraction(1), Fraction(2), Fraction(-2), Fraction(0), Fraction(0), Fraction(0))
        self.assertEqual(conjecture.parse_unit("J"), want_joule)
        self.assertEqual(conjecture.parse_unit("kg*m^2/s^2"), want_joule)
        self.assertEqual(conjecture.parse_unit("N*m"), want_joule)
        # Fractional exponent m^(1/2)/s -> (0, 1/2, -1, 0, 0, 0)
        self.assertEqual(
            conjecture.parse_unit("m^(1/2)/s"),
            (Fraction(0), Fraction(1, 2), Fraction(-1), Fraction(0), Fraction(0), Fraction(0)),
        )
        # Dimensionless
        zero = (Fraction(0),) * 6
        self.assertEqual(conjecture.parse_unit("1"), zero)
        self.assertEqual(conjecture.parse_unit("dimensionless"), zero)

    def test_pendulum_yields_single_dimensionless_group_excluding_mass(self) -> None:
        import conjecture  # noqa: PLC0415

        groups = conjecture.buckingham_pi({"L": "m", "g": "m/s^2", "m": "kg"}, target="t_period=s")
        self.assertEqual(len(groups), 1)
        g0 = groups[0]
        self.assertEqual(g0["name"], "pi_1")
        self.assertEqual(
            g0["exponents"],
            {
                "t_period": "1",
                "L": "-1/2",
                "g": "1/2",
                "m": "0",
            },
        )
        # Also works when target is passed inside variables dict by name
        groups_by_key = conjecture.buckingham_pi(
            {"L": "m", "g": "m/s^2", "m": "kg", "t_period": "s"},
            target="t_period",
        )
        self.assertEqual(groups_by_key[0]["exponents"], g0["exponents"])

    def test_reynolds_number_nullspace(self) -> None:
        import conjecture  # noqa: PLC0415

        groups = conjecture.buckingham_pi(
            {"rho": "kg/m^3", "v": "m/s", "D": "m", "mu": "kg/(m*s)"}
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            groups[0]["exponents"],
            {"rho": "1", "v": "1", "D": "1", "mu": "-1"},
        )

    def test_target_with_unmatched_base_dimension_or_unspanned_combination_raises_unit_error(self) -> None:
        import conjecture  # noqa: PLC0415

        with self.assertRaises(conjecture.UnitError) as ctx:
            conjecture.buckingham_pi({"L": "m", "g": "m/s^2", "m": "kg"}, target="T_kelvin=K")
        self.assertIn("Theta", str(ctx.exception))

        # Every base dimension M, L, T appears in {m=kg, a=m/s^2}, yet E=J (kg*m^2/s^2) is outside their span
        with self.assertRaises(conjecture.UnitError):
            conjecture.buckingham_pi({"m": "kg", "a": "m/s^2"}, target="E=J")

    def test_incompatible_addition_or_unknown_unit_is_rejected(self) -> None:
        import conjecture  # noqa: PLC0415

        self.assertFalse(conjecture.check_dimensional_homogeneity("m", "s"))
        self.assertTrue(conjecture.check_dimensional_homogeneity("Pa", "kg/(m*s^2)"))
        self.assertTrue(conjecture.check_dimensional_homogeneity("W", "J/s"))
        with self.assertRaises(conjecture.UnitError):
            conjecture.parse_unit("parsec_foo")
        with self.assertRaises(conjecture.UnitError):
            conjecture.parse_unit("")

    def test_cli_units_subcommand_supports_flags_and_spec_json(self) -> None:
        script = SCRIPTS_DIR / "conjecture.py"
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(script),
                "units",
                "--var",
                "L=m",
                "--var",
                "g=m/s^2",
                "--var",
                "m=kg",
                "--target",
                "t_period=s",
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload["groups"]), 1)
        self.assertEqual(payload["groups"][0]["exponents"]["m"], "0")
        self.assertEqual(payload["groups"][0]["exponents"]["g"], "1/2")

        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "units.json"
            spec.write_text(
                json.dumps({"variables": {"L": "m", "g": "m/s^2", "m": "kg"}, "target": "t_period=s"}),
                encoding="utf-8",
            )
            proc2 = subprocess.run(
                [sys.executable, "-B", str(script), "units", "--spec", str(spec), "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(proc2.returncode, 0, proc2.stderr)
            self.assertEqual(json.loads(proc2.stdout)["groups"], payload["groups"])


if __name__ == "__main__":
    unittest.main()
