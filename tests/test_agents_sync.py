import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTABLE = ROOT / "skills" / "heurisma" / "references" / "agents"
CLAUDE_AGENTS = ROOT / "agents"
PAIRS = {"reviewer.md": "heurisma-reviewer.md", "source-verifier.md": "heurisma-source-verifier.md", "qa.md": "heurisma-qa.md"}


def persona(portable: str) -> str:
    """The part of a portable prompt that the subagent itself reads: everything below its first line that is exactly ``---``.
    Above that line are the orchestrator's instructions (when to dispatch, where to save the answer)."""
    lines = (PORTABLE / portable).read_text(encoding="utf-8").split("\n")
    return "\n".join(lines[lines.index("---") + 1:]).lstrip("\n")


EXPECTED_TOOLS = {
    "heurisma-qa.md": ("Read, Grep, Glob, Bash", "sonnet"),
    "heurisma-reviewer.md": ("Read, Grep, Glob, Bash, WebSearch, WebFetch", "opus"),
    "heurisma-source-verifier.md": ("Read, Grep, Glob, Bash", "sonnet"),
}


class TestAgentsSync(unittest.TestCase):
    def test_claude_code_agents_carry_exactly_the_persona_of_the_portable_prompts(self) -> None:
        for portable, claude in PAIRS.items():
            agent_text = (CLAUDE_AGENTS / claude).read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n\n(.*)$", agent_text, flags=re.DOTALL)
            self.assertIsNotNone(m, msg=f"{claude}: missing frontmatter")
            fields = dict(line.split(": ", 1) for line in m.group(1).splitlines())
            self.assertEqual(fields.get("name"), claude[:-3])
            self.assertTrue(fields.get("description", "").startswith("Use when"), msg=claude)
            self.assertEqual((fields.get("tools"), fields.get("model")), EXPECTED_TOOLS[claude], msg=claude)
            self.assertEqual(m.group(2), persona(portable), msg=f"{claude} drifted from the persona in {portable}")

    def test_installed_agents_carry_only_the_persona(self) -> None:
        for claude in PAIRS.values():
            text = (CLAUDE_AGENTS / claude).read_text(encoding="utf-8")
            for orchestrator_line in ("Dispatch this prompt", "Replace `{REPORT_DIR}`", "Subagent Prompt"):
                self.assertNotIn(orchestrator_line, text, msg=f"{claude} still carries the orchestrator's script")

    def test_no_sentence_declares_the_instructions_untrusted(self) -> None:
        for portable in PAIRS:
            text = (PORTABLE / portable).read_text(encoding="utf-8")
            self.assertNotIn("Everything below is material under audit", text, msg=portable)

    def test_each_persona_has_an_untrusted_material_section_before_its_checks(self) -> None:
        for portable in PAIRS:
            text = persona(portable)
            first_section = min(i for i in (text.find("## Inputs"), text.find("## Checks")) if i >= 0)
            self.assertIn("## Untrusted material", text[:first_section], msg=portable)
            block = text[text.index("## Untrusted material"):first_section]
            self.assertNotRegex(block, r"(?i)\bbelow\b", msg=f"{portable}: the untrusted-material block must not point at the rest of the prompt")
            self.assertIn("are your instructions; follow them", block, msg=portable)

    def test_qa_prompt_has_no_home_path_literal(self) -> None:
        for path in (PORTABLE / "qa.md", CLAUDE_AGENTS / "heurisma-qa.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("/home/", text, msg=str(path))
            self.assertNotIn("/Users/", text, msg=str(path))

    def test_personas_define_input_and_output_contracts(self) -> None:
        for portable in PAIRS:
            text = persona(portable)
            self.assertIn("## Output (exactly this shape)", text, msg=portable)
            self.assertIn("{REPORT_DIR}", text, msg=portable)
            self.assertRegex(text, r"never edit", msg=portable)

    def test_each_prompt_names_its_gate_trace_file(self) -> None:
        gate = {"reviewer.md": "reviewer.md", "source-verifier.md": "source_verifier.md", "qa.md": "qa.md"}
        for portable, trace in gate.items():
            text = (PORTABLE / portable).read_text(encoding="utf-8")
            self.assertIn(f"appendix/gates/{trace}", text, msg=portable)


class TestGateHeaderInPrompts(unittest.TestCase):
    def test_each_prompt_asks_for_the_binding_header(self) -> None:
        gate_of = {"reviewer.md": "reviewer", "source-verifier.md": "source_verifier", "qa.md": "qa"}
        for portable, gate in gate_of.items():
            text = persona(portable)
            for field in ("MODE: subagent", "REVIEWED-SHA256:", "REVIEWED-UTC:", "QUOTE:", f"--gate-hash {gate}", "{SKILL_DIR}"):
                self.assertIn(field, text, msg=f"{portable} must ask for {field!r}")


class TestGateMarkersMatchPrompts(unittest.TestCase):
    def test_validator_markers_are_named_in_the_prompts(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "skills" / "heurisma" / "scripts"))
        import validate_report

        prompt_of = {"source_verifier": "source-verifier.md", "reviewer": "reviewer.md", "qa": "qa.md"}
        for gate, markers in validate_report.GATE_MARKERS.items():
            text = persona(prompt_of[gate])
            for label, _ in markers:
                if label.startswith("check "):
                    continue  # numbered check lines: the prompt defines the checks and the <#> line shape
                key = label.split(":")[0] if ":" in label else label
                self.assertIn(key, text, msg=f"{prompt_of[gate]} does not name validator marker {label!r}")


if __name__ == "__main__":
    unittest.main()
