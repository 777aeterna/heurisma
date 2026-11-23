"""Verify that all bundled scripts target Python >= 3.9 (stdlib only)."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "heurisma" / "scripts"
SKILL_MD = REPO_ROOT / "skills" / "heurisma" / "SKILL.md"


def _has_future_annotations(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(alias.name == "annotations" for alias in node.names):
                return True
    return False


def _collect_annotation_nodes(tree: ast.AST) -> set[int]:
    """Return ids of AST nodes located inside type annotations."""
    ann_ids: set[int] = set()

    def mark(node: ast.AST | None) -> None:
        if node is None:
            return
        for child in ast.walk(node):
            ann_ids.add(id(child))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mark(node.returns)
            for arg in (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
                + ([node.args.vararg] if node.args.vararg else [])
                + ([node.args.kwarg] if node.args.kwarg else [])
            ):
                mark(arg.annotation)
        elif isinstance(node, ast.AnnAssign):
            mark(node.annotation)
    return ann_ids


def _scan_310_plus(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    issues: list[str] = []
    try:
        tree = ast.parse(src, filename=str(path), feature_version=(3, 9))
    except SyntaxError as exc:
        return [f"{path.name}:{exc.lineno}: syntax incompatible with Python 3.9 ({exc.msg})"]

    future_ann = _has_future_annotations(tree)
    ann_ids = _collect_annotation_nodes(tree)

    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", 0)
        # 1. PEP 604 union types in annotations without `from __future__ import annotations`,
        #    or in runtime isinstance()/issubclass() calls (3.10+).
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("isinstance", "issubclass") and len(node.args) >= 2:
                for sub in ast.walk(node.args[1]):
                    if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr):
                        issues.append(
                            f"{path.name}:{lineno}: runtime union `|` in {node.func.id}() requires Python 3.10+"
                        )
                        break
            if node.func.id == "zip":
                if any(kw.arg == "strict" for kw in node.keywords):
                    issues.append(f"{path.name}:{lineno}: zip(..., strict=...) requires Python 3.10+")

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            if id(node) in ann_ids and not future_ann:
                issues.append(
                    f"{path.name}:{lineno}: PEP 604 `|` in type annotation requires `from __future__ import annotations` on Python 3.9"
                )

        # 2. datetime.UTC (3.11+)
        if isinstance(node, ast.Attribute) and node.attr == "UTC":
            issues.append(f"{path.name}:{lineno}: datetime.UTC requires Python 3.11+ (use timezone.utc)")
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            if any(a.name == "UTC" for a in node.names):
                issues.append(f"{path.name}:{lineno}: `from datetime import UTC` requires Python 3.11+")

        # 3. itertools.pairwise (3.10+)
        if isinstance(node, ast.Attribute) and node.attr == "pairwise":
            issues.append(f"{path.name}:{lineno}: itertools.pairwise requires Python 3.10+")
        if isinstance(node, ast.ImportFrom) and node.module == "itertools":
            if any(a.name == "pairwise" for a in node.names):
                issues.append(f"{path.name}:{lineno}: `from itertools import pairwise` requires Python 3.10+")

        # 4. tomllib (3.11+)
        if isinstance(node, ast.Import):
            if any(a.name == "tomllib" for a in node.names):
                issues.append(f"{path.name}:{lineno}: tomllib requires Python 3.11+")
        if isinstance(node, ast.ImportFrom) and node.module == "tomllib":
            issues.append(f"{path.name}:{lineno}: tomllib requires Python 3.11+")

        # 5. bisect.*(..., key=...) (3.10+)
        if isinstance(node, ast.Call):
            fn_name = ""
            if isinstance(node.func, ast.Attribute):
                fn_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                fn_name = node.func.id
            if fn_name in ("bisect", "bisect_left", "bisect_right", "insort", "insort_left", "insort_right"):
                if any(kw.arg == "key" for kw in node.keywords):
                    issues.append(f"{path.name}:{lineno}: {fn_name}(..., key=...) requires Python 3.10+")
            if fn_name == "write_text":
                if any(kw.arg == "newline" for kw in node.keywords):
                    issues.append(f"{path.name}:{lineno}: Path.write_text(..., newline=...) requires Python 3.10+")

    return issues


class TestPythonFloor(unittest.TestCase):
    def test_scripts_compatible_with_python_39(self) -> None:
        scripts = sorted(p for p in SCRIPTS_DIR.rglob("*.py") if "__pycache__" not in p.parts)  # includes checks/
        self.assertGreaterEqual(len(scripts), 5)
        all_issues: list[str] = []
        for script in scripts:
            all_issues.extend(_scan_310_plus(script))
        self.assertEqual(all_issues, [], "\n".join(all_issues))

    def test_skill_frontmatter_declares_python_39_compatibility(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        fm = text.split("---\n", 2)[1]
        self.assertLessEqual(len(fm), 1024, f"Frontmatter exceeds 1024 chars ({len(fm)})")
        fields = dict(line.split(": ", 1) for line in fm.strip().splitlines() if ": " in line)
        compat = fields.get("compatibility", "")
        self.assertIn("3.9", compat, f"Expected Python >= 3.9 in compatibility field, got: {compat!r}")


if __name__ == "__main__":
    unittest.main()
