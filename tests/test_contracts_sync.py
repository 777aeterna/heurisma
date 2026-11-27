"""Verify single-source-of-truth contracts.py stays synced with scripts and references."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO_ROOT / "skills" / "heurisma"
SCRIPTS_DIR = SKILL_ROOT / "scripts"
REFS_DIR = SKILL_ROOT / "references"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestContractsSync(unittest.TestCase):
    def test_contracts_module_and_scripts_share_constants(self) -> None:
        import conjecture  # noqa: PLC0415
        import contracts  # noqa: PLC0415
        import fetch_lib  # noqa: PLC0415
        import formal_math  # noqa: PLC0415
        import local_data  # noqa: PLC0415
        import render_report  # noqa: PLC0415
        import svg_charts  # noqa: PLC0415
        import validate_report  # noqa: PLC0415

        for mod in (conjecture, fetch_lib, formal_math, local_data, render_report, svg_charts, validate_report):
            self.assertEqual(mod.__version__, contracts.__version__, f"{mod.__name__} version drift")

        self.assertIs(local_data.VALID_KINDS, contracts.VALID_KINDS)
        self.assertIs(validate_report.VALID_KINDS, contracts.VALID_KINDS)
        self.assertIs(local_data.VALID_SELECTIONS, contracts.VALID_SELECTIONS)
        self.assertIs(validate_report.VALID_SELECTIONS, contracts.VALID_SELECTIONS)
        self.assertIs(local_data.SOURCE_COLS, contracts.SOURCE_COLS)
        self.assertIs(local_data.ATTEMPT_COLS, contracts.ATTEMPT_COLS)
        self.assertIs(validate_report.STRONG_TAGS, contracts.STRONG_TAGS)
        self.assertIs(validate_report.GATE_FILES, contracts.GATE_FILES)
        self.assertIs(validate_report.TAG_TO_CANONICAL, contracts.TAG_TO_CANONICAL)

    def test_epistemic_tags_synced_with_references(self) -> None:
        import contracts  # noqa: PLC0415

        sci = (REFS_DIR / "scientific-writing.md").read_text(encoding="utf-8")
        sv = (REFS_DIR / "agents" / "source-verifier.md").read_text(encoding="utf-8")
        en_tags = ("[Strong]", "[Moderate]", "[Preliminary]", "[Speculative]")
        for tag in en_tags:
            self.assertIn(tag, contracts.TAG_TO_CANONICAL)
            self.assertIn(tag, sci, f"{tag} missing from scientific-writing.md")
            self.assertIn(tag, sv, f"{tag} missing from references/agents/source-verifier.md")

    def test_kinds_selections_and_columns_synced_with_data_protocol(self) -> None:
        import contracts  # noqa: PLC0415

        dp = (REFS_DIR / "data-protocol.md").read_text(encoding="utf-8")
        for kind in contracts.VALID_KINDS:
            self.assertIn(kind, dp, f"kind '{kind}' missing from data-protocol.md")
        for sel in contracts.VALID_SELECTIONS:
            self.assertIn(sel, dp, f"selection '{sel}' missing from data-protocol.md")
        for col in contracts.SOURCE_COLS:
            self.assertIn(col, dp, f"sources.csv column '{col}' missing from data-protocol.md")
        for col in contracts.ATTEMPT_COLS:
            self.assertIn(col, dp, f"data_attempts.csv column '{col}' missing from data-protocol.md")

    def test_gates_synced_with_skill_md_and_agent_prompts(self) -> None:
        import contracts  # noqa: PLC0415

        skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for gate in contracts.GATE_FILES:
            self.assertIn(gate, skill_md, f"gate '{gate}' missing from SKILL.md")
        self.assertEqual(set(contracts.GATES_BY_LEVEL[2]), {"source_verifier", "qa"})
        self.assertEqual(set(contracts.GATES_BY_LEVEL[3]), {"source_verifier", "reviewer", "qa"})
        for prompt in ("source-verifier.md", "reviewer.md", "qa.md"):
            self.assertTrue((REFS_DIR / "agents" / prompt).is_file(), f"Missing prompt {prompt}")

    def test_validator_codes_synced_with_reference_doc(self) -> None:
        import validate_report  # noqa: PLC0415

        doc = (REFS_DIR / "validator-codes.md").read_text(encoding="utf-8")
        codes = {code for _, code, _ in validate_report.CODE_RULES}
        missing = sorted(c for c in codes if c not in doc)
        self.assertEqual(missing, [], f"Validator codes missing from validator-codes.md: {missing}")

    def test_formal_and_discovery_reference_and_skill_routing_synced(self) -> None:
        import conjecture  # noqa: PLC0415
        import contracts  # noqa: PLC0415
        import formal_math  # noqa: PLC0415

        ref_path = REFS_DIR / "formal-and-discovery.md"
        self.assertTrue(ref_path.is_file(), "Missing references/formal-and-discovery.md")
        ref_text = ref_path.read_text(encoding="utf-8")
        self.assertIn(
            ", ".join(contracts.FORMAL_PROOF_COLS),
            ref_text,
            "Exact FORMAL_PROOF_COLS comma-separated schema missing from formal-and-discovery.md",
        )
        self.assertIn(
            ", ".join(conjecture.DIMENSIONS),
            ref_text,
            "Exact conjecture.DIMENSIONS tuple missing from formal-and-discovery.md",
        )
        for ax in contracts.STANDARD_LEAN_AXIOMS:
            self.assertIn(ax, ref_text, f"Standard Lean axiom '{ax}' missing from formal-and-discovery.md")
        for token in (
            contracts.FORMAL_PROOFS_CSV,
            contracts.CONJECTURES_JSON,
            "formal_math.py",
            "conjecture.py",
            "Challenge.lean",
            "Solution.lean",
            "--reproduce-lean",
            "additive_gaussian_y",
            "Statement-Fidelity",
            '--target "T=s"',
            '--var "L=m"',
            "conjecture.py discover appendix/data/",
            "formal_math.py init kepler-third-law",
            "formal_math.py check kepler-third-law --register --claim FM1",
            "formal_math.py fetch-ref anthropics/formal-math",
            formal_math.DEFAULT_TOOLCHAIN,
            "_heurisma_same_stmt",
        ):
            self.assertIn(token, ref_text, f"{token!r} missing from formal-and-discovery.md")

        skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/formal-and-discovery.md", skill_md)
        self.assertIn("formal-proof", skill_md)
        self.assertIn("FORMAL-SHA256", skill_md)
        # H-04: SKILL.md stays lean (< 275 lines)
        self.assertLess(len(skill_md.splitlines()), 275, "SKILL.md grew too large; keep details in references/formal-and-discovery.md")
        # H-02: explicit post-QA re-render + strict validation reminder
        self.assertIn("render_report.py", skill_md.split("appendix/gates/qa.md", 1)[1])
        # H-07: same-model correlation disclosure
        self.assertRegex(skill_md, r"(?i)same-model|correlated blind spots")

        disc_md = (REFS_DIR / "disciplines.md").read_text(encoding="utf-8")
        self.assertIn("formal-proof", disc_md)
        self.assertIn("unverified_no_toolchain", disc_md)


if __name__ == "__main__":
    unittest.main()
