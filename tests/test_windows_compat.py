"""Cross-platform / Windows safety checks (UTF-8 stdio, cross-drive relpath, explicit encodings)."""

from __future__ import annotations

import ast
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "heurisma" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import local_data  # noqa: E402
import render_report  # noqa: E402
import validate_report  # noqa: E402


class _FakeStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.reconfigured: list[dict[str, object]] = []

    def reconfigure(self, **kwargs: object) -> None:
        self.reconfigured.append(kwargs)


class TestWindowsCompat(unittest.TestCase):
    def test_cli_entrypoints_reconfigure_utf8_stdio(self) -> None:
        for mod in (local_data, render_report, validate_report):
            fake_out = _FakeStream()
            fake_err = _FakeStream()
            with mock.patch.object(sys, "stdout", fake_out), mock.patch.object(sys, "stderr", fake_err):
                try:
                    mod.main(["--version"])
                except SystemExit:
                    pass
            self.assertTrue(
                any(call.get("encoding") == "utf-8" for call in fake_out.reconfigured),
                f"{mod.__name__}.main() did not reconfigure sys.stdout to utf-8",
            )
            self.assertTrue(
                any(call.get("encoding") == "utf-8" for call in fake_err.reconfigured),
                f"{mod.__name__}.main() did not reconfigure sys.stderr to utf-8",
            )

    def test_register_local_falls_back_to_uri_on_cross_drive_relpath_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_file = root / "sample.csv"
            data_file.write_text("a,b\n1,2\n", encoding="utf-8")
            sources_csv = root / "appendix" / "sources.csv"
            with mock.patch.object(os.path, "relpath", side_effect=ValueError("path is on mount 'D:', start on mount 'C:'")):
                row = local_data.register_local(
                    data_file, sources_csv, "Tier 3", "Sample", relative_to=root
                )
            self.assertTrue(row["url"].startswith("file:///"), f"Expected file:/// fallback, got {row['url']!r}")

    def test_import_local_falls_back_to_uri_on_cross_drive_relpath_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "inbox" / "sample.csv"
            src.parent.mkdir(parents=True)
            src.write_text("a,b\n1,2\n", encoding="utf-8")
            sources_csv = root / "appendix" / "sources.csv"
            with mock.patch.object(os.path, "relpath", side_effect=ValueError("path is on mount 'D:', start on mount 'C:'")):
                row = local_data.import_local(
                    src, root / "appendix" / "data", sources_csv, "Tier 3", "Sample"
                )
            self.assertTrue(row["url"].startswith("file:///"), f"Expected file:/// fallback, got {row['url']!r}")

    def test_explicit_encoding_in_scripts_and_tests(self) -> None:
        issues: list[str] = []
        for folder in (SCRIPTS_DIR, REPO_ROOT / "tests"):
            for path in sorted(folder.glob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    kws = {k.arg: k.value for k in node.keywords}
                    if isinstance(node.func, ast.Attribute):
                        name = node.func.attr
                        if name in ("read_text", "write_text") and "encoding" not in kws:
                            issues.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {name}() missing encoding=")
                        elif name == "run" and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                            if "text" in kws and "encoding" not in kws:
                                issues.append(
                                    f"{path.relative_to(REPO_ROOT)}:{node.lineno}: subprocess.run(text=...) missing encoding="
                                )
                    elif isinstance(node.func, ast.Name) and node.func.id == "open":
                        mode = None
                        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                            mode = node.args[1].value
                        elif "mode" in kws and isinstance(kws["mode"], ast.Constant) and isinstance(kws["mode"].value, str):
                            mode = kws["mode"].value
                        if (mode is None or "b" not in mode) and "encoding" not in kws:
                            issues.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: open() missing encoding=")
        self.assertEqual(issues, [], "\n".join(issues))

    def test_gate_files_and_reproduce_are_case_order_and_crlf_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "appendix"
            app.mkdir()
            (root / "report.md").write_text("# R\n", encoding="utf-8")
            (app / "README.md").write_text("```bash\npython3 -B appendix/analysis.py > appendix/output.txt\n```\n", encoding="utf-8")
            (app / "analysis.py").write_text("import sys; sys.stdout.buffer.write(b'line1\\r\\nline2')\n", encoding="utf-8")
            (app / "output.txt").write_bytes(b"line1\nline2")
            rels = [rel for rel, _ in validate_report._gate_files(root, "qa")]
            self.assertLess(rels.index("appendix/README.md"), rels.index("appendix/analysis.py"))
            errs = validate_report.reproduce(root)
            self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
