"""Verify that the repository tree documented in docs/design.md matches the actual files."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_MD = REPO_ROOT / "docs" / "design.md"
SKILL_ROOT = REPO_ROOT / "skills" / "heurisma"


def _extract_tree_paths(markdown_text: str) -> list[str]:
    """Parse ASCII tree code blocks in docs/design.md and return relative paths."""
    paths: list[str] = []
    for block in re.findall(r"```text\s*\n(.*?)```", markdown_text, flags=re.DOTALL):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        root = lines[0].split("#", 1)[0].strip().rstrip("/")
        if not root or not (REPO_ROOT / root).exists():
            continue
        stack: list[tuple[int, str]] = [(-1, root)]
        for raw in lines[1:]:
            code = raw.split("#", 1)[0].rstrip()
            m = re.match(r"^([│├└─\s]+)(.+)$", code)
            if not m:
                continue
            prefix, name = m.group(1), m.group(2).strip()
            depth = len(prefix) // 4
            while stack and stack[-1][0] >= depth:
                stack.pop()
            parent = stack[-1][1] if stack else root
            is_dir = name.endswith("/")
            clean = name.rstrip("/")
            rel = f"{parent}/{clean}"
            paths.append(rel)
            if is_dir:
                stack.append((depth, rel))
    return paths


class TestDocsTree(unittest.TestCase):
    def test_every_documented_path_exists(self) -> None:
        text = DESIGN_MD.read_text(encoding="utf-8")
        paths = _extract_tree_paths(text)
        self.assertGreaterEqual(len(paths), 10, "docs/design.md should document the skill tree")
        missing = [p for p in paths if not (REPO_ROOT / p).exists()]
        self.assertEqual(missing, [], f"Documented paths do not exist: {missing}")

    def test_all_skill_scripts_and_references_are_documented(self) -> None:
        text = DESIGN_MD.read_text(encoding="utf-8")
        paths = set(_extract_tree_paths(text))
        expected = {
            p.relative_to(REPO_ROOT).as_posix()
            for p in list((SKILL_ROOT / "scripts").glob("*.py"))
            + list((SKILL_ROOT / "references").rglob("*.md"))
            + [SKILL_ROOT / "SKILL.md"]
        }
        undocumented = sorted(expected - paths)
        self.assertEqual(undocumented, [], f"Files missing from docs/design.md tree: {undocumented}")


if __name__ == "__main__":
    unittest.main()
