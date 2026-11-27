#!/usr/bin/env python3
"""Regression tests for the Heurisma formal-math (Lean 4) pipeline fixes.

Covers FMT-1, FMT-4, FMT-5, FMT-7, FMT-8, FMT-9, FMT-10, FMT-11, FMT-12, FMT-15, FMT-16
and the R3 validator gate. Run with either:

    python3 -B tests/test_formal.py
    pytest -q tests/test_formal.py
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "heurisma" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import formal_math as fm  # noqa: E402
import checks.formal as cf  # noqa: E402


def _write_minimal_project(root: Path, slug: str) -> Path:
    proj = root / "formal" / slug
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "Challenge.lean").write_text(
        "namespace Challenge\n\n"
        "theorem main_claim (n : Nat) : n + 0 = n := by sorry\n\n"
        "end Challenge\n",
        encoding="utf-8",
    )
    (proj / "Solution.lean").write_text(
        "import Challenge\n\n"
        "namespace Solution\n\n"
        "theorem main_claim (n : Nat) : n + 0 = n := by rfl\n\n"
        "end Solution\n",
        encoding="utf-8",
    )
    (proj / "lakefile.toml").write_text(
        'name = "proj"\ndefaultTargets = ["Challenge", "Solution"]\n\n'
        "[[lean_lib]]\nname = \"Challenge\"\n\n"
        "[[lean_lib]]\nname = \"Solution\"\n",
        encoding="utf-8",
    )
    (proj / "lean-toolchain").write_text("leanprover/lean4:v4.16.0\n", encoding="utf-8")
    return proj


class TestSha256Exact(unittest.TestCase):
    def test_sha256_re_requires_exactly_64(self):
        self.assertIsNone(cf._SHA256_RE.fullmatch("a" * 12))
        self.assertIsNone(cf._SHA256_RE.fullmatch("a" * 63))
        self.assertIsNone(cf._SHA256_RE.fullmatch("a" * 65))
        self.assertIsNotNone(cf._SHA256_RE.fullmatch("a" * 64))
        self.assertIsNotNone(cf._SHA256_RE.fullmatch("0123456789abcdef" * 4))
        # The validator lower-cases declared digests before matching.
        self.assertIsNone(cf._SHA256_RE.fullmatch("A" * 64))


class TestTrivialProofScan(unittest.TestCase):
    def test_flags_nlinarith_and_simpa(self):
        tactic_warnings, _unused = fm._scan_trivial_proofs(
            "theorem foo (h : 0 < c) : c = c := by nlinarith\n"
            "theorem bar (h : 0 < c) : c = c := by simpa [h]\n"
        )
        self.assertIn("single_tactic_proof:foo:nlinarith", tactic_warnings)
        self.assertIn("single_tactic_proof:bar:simpa", tactic_warnings)

    def test_flags_all_goals_combinator(self):
        tactic_warnings, _unused = fm._scan_trivial_proofs(
            "theorem foo (h : 0 < c) : c = c := by intro x <;> ring\n"
        )
        self.assertIn("single_tactic_proof:foo:ring", tactic_warnings)


class TestUnusedHypothesis(unittest.TestCase):
    def test_sees_implicit_and_forall_binders(self):
        _tactic, unused = fm._scan_trivial_proofs(
            "theorem a {h : 0 < c} : c = c := by rfl\n"
            "theorem b : ∀ h : 0 < c, c = c := by rfl\n"
        )
        self.assertIn("unused_hypothesis:a:h", unused)
        self.assertIn("unused_hypothesis:b:h", unused)

    def test_unused_is_separate_from_single_tactic(self):
        tactic_warnings, unused = fm._scan_trivial_proofs(
            "theorem a {h : 0 < c} : c = c := by rfl\n"
        )
        self.assertIn("single_tactic_proof:a:rfl", tactic_warnings)
        self.assertIn("unused_hypothesis:a:h", unused)
        # The informational unused signal must not leak into the hard warning channel.
        self.assertNotIn("unused_hypothesis:a:h", tactic_warnings)


class TestStripper(unittest.TestCase):
    def test_interpolated_string_is_balanced_and_masks_inner_string(self):
        src = 'x := s!"{if c then "sorry" else "ok"}"'
        stripped, balanced = fm._strip_with_state(src)
        self.assertTrue(balanced)
        self.assertNotIn("sorry", stripped)
        self.assertNotIn("ok", stripped)

    def test_char_literal_double_quote_does_not_open_string(self):
        src = 'x := \'"\' + "tail"'
        _stripped, balanced = fm._strip_with_state(src)
        self.assertTrue(balanced)

    def test_unterminated_string_is_unbalanced(self):
        _stripped, balanced = fm._strip_with_state('x := "abc')
        self.assertFalse(balanced)


class TestSanitize(unittest.TestCase):
    def test_rejects_comment_close(self):
        with self.assertRaises(fm.FormalError):
            fm._sanitize_lean_fragment("x : Nat -/ axiom cheat : False", "statement")

    def test_rejects_line_comment(self):
        with self.assertRaises(fm.FormalError):
            fm._sanitize_lean_fragment("x -- inject", "statement")

    def test_init_project_rejects_injection(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(fm.FormalError):
                fm.init_project(Path(td), "p", statement="(n : Nat) : n + 0 = n -/ axiom cheat : False")


class TestQualifiedNames(unittest.TestCase):
    def test_nested_namespace(self):
        quals = fm._qualified_theorem_names(
            "namespace Challenge.Inner\n"
            "theorem foo (n : Nat) : n + 0 = n := by sorry\n"
            "end Challenge.Inner\n"
        )
        self.assertEqual(quals, {"foo": "Challenge.Inner.foo"})

    def test_resolve_pairs_demotes_signature_mismatch(self):
        ch = (
            "namespace Challenge\n"
            "theorem foo (n : Nat) : n + 0 = n := by sorry\n"
            "end Challenge\n"
        )
        sol = (
            "namespace Solution\n"
            "theorem foo (n : Nat) : 0 + n = n := by rfl\n"
            "end Solution\n"
        )
        paired_ok, missing, sig_warns, pairs = fm.resolve_theorem_pairs(ch, sol)
        self.assertTrue(paired_ok)
        self.assertEqual(missing, [])
        self.assertTrue(sig_warns)
        self.assertEqual(pairs, [("Challenge.foo", "Solution.foo")])

    def test_resolve_pairs_normalizes_whitespace_around_colon(self):
        ch = "theorem foo (n : Nat) : n + 0 = n := by sorry\n"
        sol = "theorem foo (n:Nat) : n + 0 = n := by rfl\n"
        paired_ok, _missing, sig_warns, pairs = fm.resolve_theorem_pairs(ch, sol)
        self.assertTrue(paired_ok)
        self.assertEqual(sig_warns, [])
        self.assertEqual(pairs, [("foo", "foo")])


class TestCheckProjectNoTheorem(unittest.TestCase):
    def test_empty_project_is_failed_no_theorem(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proj = root / "formal" / "p"
            proj.mkdir(parents=True, exist_ok=True)
            (proj / "Challenge.lean").write_text("", encoding="utf-8")
            (proj / "Solution.lean").write_text("", encoding="utf-8")
            (proj / "lean-toolchain").write_text("leanprover/lean4:v4.16.0\n", encoding="utf-8")
            res = fm.check_project(root, "p")
            self.assertEqual(res["status"], "failed_no_theorem")


class TestProofId(unittest.TestCase):
    def test_proof_id_derives_from_max_existing(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "formal_proofs.csv"
            fm._upsert_formal_proofs_csv(csv_path, {"slug": "a", "proof_id": "F1"})
            fm._upsert_formal_proofs_csv(csv_path, {"slug": "b", "proof_id": "F5"})
            fm._upsert_formal_proofs_csv(csv_path, {"slug": "c"})
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            ids = {r["slug"]: r["proof_id"] for r in rows}
            self.assertEqual(ids["a"], "F1")
            self.assertEqual(ids["b"], "F5")
            self.assertEqual(ids["c"], "F6")


class TestBranchAndHostValidation(unittest.TestCase):
    def test_rejects_bad_branch(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(fm.FormalError):
                fm.fetch_reference(Path(td), "owner/repo", branch="../v1")

    def test_rejects_loopback_raw_override(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(fm.FormalError):
                fm.fetch_reference(
                    Path(td), "owner/repo", env={"HEURISMA_GITHUB_RAW_URL": "http://127.0.0.1"}
                )


class TestExitCode(unittest.TestCase):
    def test_unverified_no_toolchain_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_project(root, "p")
            orig = fm.find_lake
            fm.find_lake = lambda env=None: (None, None)
            try:
                rc = fm.main(["check", "p", "--appendix", str(root)])
            finally:
                fm.find_lake = orig
            self.assertEqual(rc, 2)


class TestComparatorConfig(unittest.TestCase):
    def test_write_comparator_config_schema(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            fm._write_comparator_config(proj, ["main_claim"])
            data = json.loads((proj / "comparator.json").read_text(encoding="utf-8"))
            self.assertEqual(data["challenge_module"], "Challenge")
            self.assertEqual(data["solution_module"], "Solution")
            self.assertEqual(data["theorem_names"], ["main_claim"])
            self.assertEqual(sorted(data["permitted_axioms"]), sorted(["propext", "Quot.sound", "Classical.choice"]))


class TestR3ValidatorGate(unittest.TestCase):
    def test_audit_runs_for_tier3_draft(self):
        # A Tier 3 draft (unverified, not strong, not verified) must still be scanned:
        # its triviality signal is surfaced as a validator warning.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            appendix = root / "appendix"
            slug = "draft"
            proj = appendix / "formal" / slug
            proj.mkdir(parents=True, exist_ok=True)
            (proj / "Challenge.lean").write_text(
                "namespace Challenge\n"
                "theorem t (h : 0 < c) : c = c := by sorry\n"
                "end Challenge\n",
                encoding="utf-8",
            )
            (proj / "Solution.lean").write_text(
                "import Challenge\n"
                "namespace Solution\n"
                "theorem t (h : 0 < c) : c = c := by nlinarith\n"
                "end Solution\n",
                encoding="utf-8",
            )
            ch_sha = fm._sha256_file(proj / "Challenge.lean")
            sol_sha = fm._sha256_file(proj / "Solution.lean")
            (appendix / "formal_proofs.csv").write_text(
                "proof_id,slug,challenge_file,challenge_sha256,solution_file,solution_sha256,"
                "status,sorries,axioms,verified_utc,theorem_name,toolchain,lean_version,verification_mode\n"
                f"F1,{slug},appendix/formal/{slug}/Challenge.lean,{ch_sha},"
                f"appendix/formal/{slug}/Solution.lean,{sol_sha},"
                "unverified_no_toolchain,0,,,main_claim,,,\n",
                encoding="utf-8",
            )
            (appendix / "sources.csv").write_text(
                "claim_id,source_title,url,tier,kind,sha256,selection,accessed_date,data_as_of,retrieved_utc\n"
                f"F1,draft,appendix/formal/{slug}/Solution.lean,Tier 3,formal-proof,{sol_sha},agent-fetched,,,\n",
                encoding="utf-8",
            )
            (proj / "verify.json").write_text(
                json.dumps(
                    {
                        "slug": slug,
                        "challenge_sha256": ch_sha,
                        "solution_sha256": sol_sha,
                        "status": "unverified_no_toolchain",
                    }
                ),
                encoding="utf-8",
            )
            sources_rows = [
                {
                    "claim_id": "F1",
                    "url": f"appendix/formal/{slug}/Solution.lean",
                    "kind": "formal-proof",
                    "tier": "Tier 3",
                    "sha256": sol_sha,
                }
            ]
            clean_text = "# report\n\n## 1. Executive Summary\n\n"
            errors, warnings = cf.check_formal_proofs(
                root, sources_rows, clean_text, {}, level=2, run_start=None
            )
            self.assertTrue(any("triviality" in w or "nlinarith" in w for w in warnings), warnings)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
