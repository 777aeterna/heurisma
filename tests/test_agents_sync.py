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


if __name__ == "__main__":
    unittest.main()
