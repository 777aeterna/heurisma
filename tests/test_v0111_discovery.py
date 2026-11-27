"""Regression tests for the discovery subsystem fixes (N1, N3, DIS-*, M5, R1/R2, VAL-*).

Stdlib only, no network. Run with:  python3 -B tests/test_discovery.py
"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = str(Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import conjecture  # noqa: E402
from checks import conjecture as checks_conjecture  # noqa: E402


def test_num_and_fmt_preserve_small_coefficients():
    # N1: a small coefficient must round-trip losslessly, never collapse to 0.0.
    small = 5.454e-10
    assert conjecture._num(small) == small, "_num must be lossless"
    assert conjecture._num(small) != 0.0
    # round(..., 8) would produce 0.0; verify the replacement helper does not.
    assert conjecture._num(round(small, 8) + small) == small
    # _fmt_num must not silently render small values as "0".
    assert conjecture._fmt_num(small) != "0"
    assert "e" in conjecture._fmt_num(small)
    assert conjecture._fmt_num(0.0) == "0"


def test_falsifier_tolerance_is_relative_not_absolute_floor():
    # N3: for a large-magnitude target the tolerance must scale with |predicted|, not clamp to 1e-4.
    rows = [{"x": float(i), "y": 1e6 + 2.0 * i} for i in range(1, 21)]
    res = conjecture.discover_laws(rows, target="y", predictors=["x"], seed=0)
    falsifier = res["falsifier_prediction"]
    m = re.search(r"max_abs_error <= ([0-9.eE+-]+)", falsifier)
    assert m, f"no tolerance in falsifier: {falsifier!r}"
    tol = float(m.group(1))
    # The old absolute floor was 1e-4; with y ~ 1e6 the relative floor is ~1e-6 * 1e6 = 1.
    assert tol > 1e-3, f"tolerance {tol!r} should be relative to the predicted magnitude"
    assert "0.0001" not in falsifier


def test_invariant_falsifier_and_source_ids():
    # DIS-2/N3/DIS-4: invariant path must use min/max sort range, a relative-SD floor, and emit source_ids.
    rows = [{"a": float(i), "b": (100.0 - float(i)) / 2.0} for i in range(1, 21)]  # a + 2*b = 100
    res = conjecture.discover_laws(
        rows, target="__invariant__", predictors=["a", "b"], source_ids=["C1", "C2"], seed=0
    )
    assert res["target"] == "__invariant__"
    assert res["source_ids"] == ["C1", "C2"], "invariant result must carry source_ids (DIS-4)"
    assert "units" in res and "warnings" in res, "invariant result must carry units/warnings (DIS-4)"
    falsifier = res["falsifier_prediction"]
    assert "relative SD <=" in falsifier
    assert "0.0001" not in falsifier, "invariant falsifier must not use the absolute 1e-4 floor"


def test_same_discovery_data_host_path_and_full_sha():
    sd = checks_conjecture._same_discovery_data

    # host+path (no query) must be treated as the same source.
    assert sd(
        {"claim_id": "C1", "url": "https://example.com/data/slice.csv?offset=10", "sha256": ""},
        {"data_file": "https://example.com/data/slice.csv", "data_sha256": "", "source_ids": []},
    ) is True

    # same basename, different host must NOT match.
    assert sd(
        {"claim_id": "C2", "url": "https://other.example.com/data/slice.csv", "sha256": ""},
        {"data_file": "https://example.com/data/slice.csv", "data_sha256": "", "source_ids": []},
    ) is False

    # full relative path (not bare basename).
    assert sd(
        {"claim_id": "C3", "url": "data/foo.csv", "sha256": ""},
        {"data_file": "data/foo.csv", "data_sha256": "", "source_ids": []},
    ) is True
    assert sd(
        {"claim_id": "C4", "url": "other/foo.csv", "sha256": ""},
        {"data_file": "data/foo.csv", "data_sha256": "", "source_ids": []},
    ) is False

    # full 64-hex SHA equality.
    full = "a" * 64
    assert sd({"claim_id": "C5", "url": "", "sha256": full}, {"data_file": "", "data_sha256": full, "source_ids": []}) is True
    # 12-hex prefix collision must NOT match (DIS-13).
    other = "a" * 12 + "b" * 52
    assert sd({"claim_id": "C6", "url": "", "sha256": other}, {"data_file": "", "data_sha256": full, "source_ids": []}) is False

    # claim_id membership still wins.
    assert sd({"claim_id": "C7", "url": "", "sha256": ""}, {"data_file": "", "data_sha256": "", "source_ids": ["C7"]}) is True


def test_single_letter_variable_m59_detection():
    # R2/DIS-5: single-letter variables (P, a) must be detected, so the M59 ceiling fires.
    rec = {
        "target": "P",
        "predictors": ["a"],
        "train_count": 8,
        "holdout_count": 2,
        "beats_null": True,
        "source_ids": [],
        "data_file": "",
        "data_sha256": "",
        "candidates": [{"id": "C_LAW_1", "expr": "P = 2 * a^1.5"}],
        "warnings": [],
    }
    rec["sha256"] = conjecture.compute_conjectures_sha256(rec)

    clean_text = (
        "# Report\n\n"
        "## Claim-Evidence Matrix\n"
        "| Claim | Evidence | Source |\n"
        "| --- | --- | --- |\n"
        "| [Strong] | P ∝ a^1.5 | |\n"
        "\n## Findings\n"
    )
    section_positions = {
        "Claim-Evidence Matrix": clean_text.index("## Claim-Evidence Matrix"),
        "Findings": clean_text.index("## Findings"),
    }

    with tempfile.TemporaryDirectory() as tmp:
        report_dir = Path(tmp)
        app_dir = report_dir / "appendix"
        app_dir.mkdir()
        (app_dir / "conjectures.json").write_text(json.dumps(rec), encoding="utf-8")

        errors, warnings = checks_conjecture.check_conjectures(
            report_dir, clean_text, section_positions, sources_rows=[], level=2
        )
        joined = "\n".join(errors + warnings)
        assert "[Strong]" in joined and ("independence" in joined or "verif" in joined), joined
        # DIS-14: at level 2 the M59 violation is a warning, not an error.
        assert not any("independence" in e for e in errors)


def test_m59_is_error_at_level_3():
    # DIS-14/VAL-8: a *known* non-independent [Strong] claim (its only backing is the discovery
    # data itself, declared via --source-ids) is an error at level 3.
    rec = {
        "target": "P",
        "predictors": ["a"],
        "train_count": 8,
        "holdout_count": 2,
        "beats_null": True,
        "source_ids": ["C_DISC"],
        "data_file": "",
        "data_sha256": "",
        "candidates": [{"id": "C_LAW_1", "expr": "P = 2 * a^1.5"}],
        "warnings": [],
    }
    rec["sha256"] = conjecture.compute_conjectures_sha256(rec)
    clean_text = (
        "# Report\n\n"
        "## Claim-Evidence Matrix\n"
        "| Claim | Evidence | Source |\n"
        "| --- | --- | --- |\n"
        "| [Strong] | P ∝ a^1.5 | [@C_DISC] |\n"
        "\n## Findings\n"
    )
    section_positions = {
        "Claim-Evidence Matrix": clean_text.index("## Claim-Evidence Matrix"),
        "Findings": clean_text.index("## Findings"),
    }
    sources_rows = [
        {"claim_id": "C_DISC", "kind": "data", "tier": "Tier 1", "url": "", "sha256": ""},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        report_dir = Path(tmp)
        app_dir = report_dir / "appendix"
        app_dir.mkdir()
        (app_dir / "conjectures.json").write_text(json.dumps(rec), encoding="utf-8")
        errors, _warnings = checks_conjecture.check_conjectures(
            report_dir, clean_text, section_positions, sources_rows=sources_rows, level=3
        )
        assert any("discovery data itself" in e for e in errors), errors


def test_constant_predictor_does_not_emit_spurious_slopes():
    # DIS-3: a constant predictor must not be re-included; only the null model is fitted.
    rows = [{"x": 5.0, "y": float(i)} for i in range(1, 21)]
    res = conjecture.discover_laws(rows, target="y", predictors=["x"], seed=0)
    families = [c.get("family") for c in res["candidates"]]
    assert families.count("null_constant") == 1, families
    assert all(f == "null_constant" for f in families), families


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures.append((t.__name__, exc))
            print(f"FAIL {t.__name__}: {exc!r}")
    if failures:
        print(f"\n{len(failures)} test(s) failed.")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed.")




class TestV0111Discovery(unittest.TestCase):
    def test_num_and_fmt_preserve_small_coefficients(self) -> None:
        test_num_and_fmt_preserve_small_coefficients()

    def test_falsifier_tolerance_is_relative_not_absolute_floor(self) -> None:
        test_falsifier_tolerance_is_relative_not_absolute_floor()

    def test_invariant_falsifier_and_source_ids(self) -> None:
        test_invariant_falsifier_and_source_ids()

    def test_same_discovery_data_host_path_and_full_sha(self) -> None:
        test_same_discovery_data_host_path_and_full_sha()

    def test_single_letter_variable_m59_detection(self) -> None:
        test_single_letter_variable_m59_detection()

    def test_m59_is_error_at_level_3(self) -> None:
        test_m59_is_error_at_level_3()

    def test_constant_predictor_does_not_emit_spurious_slopes(self) -> None:
        test_constant_predictor_does_not_emit_spurious_slopes()


if __name__ == "__main__":
    _run_all()
