import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTABLE = ROOT / "skills" / "heurisma" / "references" / "agents"
CLAUDE_AGENTS = ROOT / "agents"
PAIRS = {"reviewer.md": "heurisma-reviewer.md", "source-verifier.md": "heurisma-source-verifier.md", "qa.md": "heurisma-qa.md"}


class TestAgentsSync(unittest.TestCase):
    def test_claude_code_agents_mirror_portable_prompts(self) -> None:
        for portable, claude in PAIRS.items():
            agent_text = (CLAUDE_AGENTS / claude).read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n\n(.*)$", agent_text, flags=re.DOTALL)
            self.assertIsNotNone(m, msg=f"{claude}: missing frontmatter")
            fields = dict(line.split(": ", 1) for line in m.group(1).splitlines())
            self.assertEqual(fields.get("name"), claude[:-3])
            self.assertTrue(fields.get("description", "").startswith("Use when"), msg=claude)
            self.assertIn(fields.get("model"), {"opus", "sonnet", "haiku", "inherit"})
            self.assertEqual(m.group(2), (PORTABLE / portable).read_text(encoding="utf-8"), msg=f"{claude} drifted from {portable}")

    def test_portable_prompts_define_input_and_output_contracts(self) -> None:
        for portable in PAIRS:
            text = (PORTABLE / portable).read_text(encoding="utf-8")
            self.assertIn("## Output (exactly this shape)", text, msg=portable)
            self.assertIn("{REPORT_DIR}", text, msg=portable)
            self.assertRegex(text, r"never edits", msg=portable)

    def test_each_prompt_names_its_gate_trace_file(self) -> None:
        gate = {"reviewer.md": "reviewer.md", "source-verifier.md": "source_verifier.md", "qa.md": "qa.md"}
        for portable, trace in gate.items():
            text = (PORTABLE / portable).read_text(encoding="utf-8")
            self.assertIn(f"appendix/gates/{trace}", text, msg=portable)


class TestGateHeaderInPrompts(unittest.TestCase):
    def test_each_prompt_asks_for_the_binding_header(self) -> None:
        gate_of = {"reviewer.md": "reviewer", "source-verifier.md": "source_verifier", "qa.md": "qa"}
        for portable, gate in gate_of.items():
            text = (PORTABLE / portable).read_text(encoding="utf-8")
            for field in ("MODE: subagent", "REVIEWED-SHA256:", "REVIEWED-UTC:", "QUOTE:", f"--gate-hash {gate}", "{SKILL_DIR}"):
                self.assertIn(field, text, msg=f"{portable} must ask for {field!r}")


class TestGateMarkersMatchPrompts(unittest.TestCase):
    def test_validator_markers_are_named_in_the_prompts(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "skills" / "heurisma" / "scripts"))
        import validate_report

        prompt_of = {"source_verifier": "source-verifier.md", "reviewer": "reviewer.md", "qa": "qa.md"}
        for gate, markers in validate_report.GATE_MARKERS.items():
            text = (PORTABLE / prompt_of[gate]).read_text(encoding="utf-8")
            for label, _ in markers:
                if label.startswith("check "):
                    continue  # numbered check lines: the prompt defines the checks and the <#> line shape
                key = label.split(":")[0] if ":" in label else label
                self.assertIn(key, text, msg=f"{prompt_of[gate]} does not name validator marker {label!r}")


if __name__ == "__main__":
    unittest.main()
