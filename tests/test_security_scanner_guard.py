"""Security hardening & static-scanner regression guard for skills/heurisma/.

Ensures zero high/medium SAST patterns (whole-process os.environ capture, subprocess execution,
dynamic eval/exec, or hex/unicode escape obfuscation) inside the distributable skill directory,
while testing genuine security boundaries in providers.base, render_report, and validate_report.reproduce().
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "heurisma"
SCRIPTS_DIR = SKILL_DIR / "scripts"
TESTS_DIR = Path(__file__).resolve().parent
for _p in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mutations as M  # noqa: E402
from providers import base as provider_base  # noqa: E402
import render_report  # noqa: E402
import validate_report  # noqa: E402

FORBIDDEN_IMPORTS = frozenset({
    "subprocess",
    "pty",
    "ctypes",
    "pickle",
    "marshal",
    "shelve",
    "base64",
})
FORBIDDEN_CALLS = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
})
FORBIDDEN_OS_ATTRS = frozenset({
    "system",
    "popen",
    "execl",
    "execle",
    "execlp",
    "execlpe",
    "execv",
    "execve",
    "execvp",
    "execvpe",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
})


class TestSecurityScannerGuard(unittest.TestCase):
    def test_zero_sast_or_obfuscation_patterns_in_skill_tree(self) -> None:
        """skills/heurisma/ must contain zero bare os.environ, subprocess, eval/exec, or hex/unicode escapes."""
        violations: list[str] = []
        bare_environ_re = re.compile(r"\bos\.environ(?!\s*\.\s*get\s*\()")
        hex_or_unicode_escape_re = re.compile(r"\\x[0-9a-fA-F]{2}|\\[uU][0-9a-fA-F]{4,8}")

        for py_path in sorted(SKILL_DIR.rglob("*.py")):
            rel = py_path.relative_to(REPO_ROOT).as_posix()
            src = py_path.read_text(encoding="utf-8")

            for lineno, line in enumerate(src.splitlines(), start=1):
                if bare_environ_re.search(line):
                    violations.append(f"{rel}:{lineno}: bare os.environ reference: {line.strip()}")
                if hex_or_unicode_escape_re.search(line):
                    violations.append(f"{rel}:{lineno}: hex/unicode escape sequence: {line.strip()}")

            tree = ast.parse(src, filename=rel)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top in FORBIDDEN_IMPORTS:
                            violations.append(f"{rel}:{node.lineno}: forbidden import '{alias.name}'")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if top in FORBIDDEN_IMPORTS:
                        violations.append(f"{rel}:{node.lineno}: forbidden import from '{node.module}'")
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                        violations.append(f"{rel}:{node.lineno}: forbidden call '{node.func.id}()'")
                    elif (
                        isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                        and node.func.attr in FORBIDDEN_OS_ATTRS
                    ):
                        violations.append(f"{rel}:{node.lineno}: forbidden call 'os.{node.func.attr}()'")

        self.assertEqual(violations, [], "\n".join(violations))

    def test_provider_context_isolates_only_heurisma_env_allowlist(self) -> None:
        """Context.env and redact() never capture unrelated host secrets from os.environ."""
        sentinel_key = "UNRELATED_HOST_SECRET_TOKEN_TEST"
        old_unrelated = os.environ.get(sentinel_key)
        old_mailto = os.environ.get("HEURISMA_MAILTO")
        try:
            os.environ[sentinel_key] = "super-secret-unrelated-token-9999"
            os.environ["HEURISMA_MAILTO"] = "researcher@example.org"
            with tempfile.TemporaryDirectory() as tmp:
                ctx = provider_base.Context(Path(tmp))
                self.assertNotIn(sentinel_key, ctx.env)
                self.assertEqual(ctx.mailto, "researcher@example.org")
                redacted = provider_base.redact("url?x=1 contact researcher@example.org")
                self.assertNotIn("researcher@example.org", redacted)
                self.assertIn("REDACTED", redacted)

                # Custom injected env controls backoff without touching os.environ
                ctx_custom = provider_base.Context(Path(tmp), env={"HEURISMA_BACKOFF": "0.25"})
                self.assertAlmostEqual(ctx_custom.backoff, 0.25)
        finally:
            if old_unrelated is None:
                os.environ.pop(sentinel_key, None)
            else:
                os.environ[sentinel_key] = old_unrelated
            if old_mailto is None:
                os.environ.pop("HEURISMA_MAILTO", None)
            else:
                os.environ["HEURISMA_MAILTO"] = old_mailto

    def test_clean_text_strips_c0_c1_line_separators_and_trojan_source_bidi(self) -> None:
        """clean_text neutralizes control chars, line separators, and Unicode bidi overrides without hex regexes."""
        dirty = (
            "=SUM(A1)"
            + chr(0x00)
            + "alpha"
            + chr(0x1F)
            + chr(0x7F)
            + chr(0x9F)
            + chr(0x2028)
            + chr(0x2029)
            + chr(0x202E)  # Right-to-Left Override (Trojan Source)
            + "beta"
        )
        cleaned = provider_base.clean_text(dirty)
        self.assertTrue(cleaned.startswith("'="), cleaned)
        self.assertEqual(cleaned, "'=SUM(A1) alpha beta")

    def test_inline_code_and_url_placeholders_cannot_collide_with_user_text(self) -> None:
        """User text mimicking internal stash tokens stays escaped and never collides with code or URL spans."""
        sample = "Literal &&HEURISMA_CODE_0;; and &&HEURISMA_URL_0;; with `x = 1` and [site](https://example.org/a^2)."
        out = render_report._format_inline(sample)
        self.assertIn("&amp;&amp;HEURISMA_CODE_0;;", out)
        self.assertIn("&amp;&amp;HEURISMA_URL_0;;", out)
        self.assertIn("<code>x = 1</code>", out)
        self.assertIn('<a href="https://example.org/a^2">site</a>', out)

    def test_reproduce_blocks_interpreter_flags_path_escape_redirect_escape_symlink_and_timeout(self) -> None:
        """reproduce() enforces strict script/redirect confinement, blocks -c/-m flags, and enforces timeouts."""
        tmp, ws = M.fresh_workspace()
        try:
            # 1. Reject dangerous Python flags before script path (-c / -m)
            errs_c = validate_report.reproduce(ws, command='python3 -c "print(1)" appendix/analysis.py')
            self.assertTrue(errs_c, "Expected -c flag to be rejected")

            errs_m = validate_report.reproduce(ws, command="python3 -m unittest appendix/analysis.py")
            self.assertTrue(errs_m, "Expected -m flag to be rejected")

            # 2. Reject script outside appendix/
            (ws / "analysis.py").write_text("print('outside appendix')\n", encoding="utf-8")
            errs_out = validate_report.reproduce(ws, command="python3 -B analysis.py")
            self.assertTrue(errs_out, "Expected script outside appendix/ to be rejected")

            # 3. Reject redirect escaping workspace (> ../escaped.txt)
            outside_target = ws.parent / "escaped_redirect.txt"
            outside_target.unlink(missing_ok=True)
            errs_red = validate_report.reproduce(
                ws,
                command="python3 -B appendix/analysis.py > ../escaped_redirect.txt",
            )
            self.assertTrue(errs_red, "Expected escaping redirect to be rejected")
            self.assertFalse(outside_target.exists(), "Redirect wrote outside temporary workspace!")

            # 4. Reject symlinked analysis.py pointing outside the report directory
            outside_py = ws.parent / "outside_analysis.py"
            outside_py.write_text("print('from outside')\n", encoding="utf-8")
            real_analysis = ws / "appendix" / "analysis.py"
            backup = real_analysis.read_bytes()
            real_analysis.unlink()
            real_analysis.symlink_to(outside_py)
            try:
                errs_sym = validate_report.reproduce(ws)
                self.assertTrue(errs_sym, "Expected symlinked analysis.py outside report_dir to be rejected")
            finally:
                real_analysis.unlink()
                real_analysis.write_bytes(backup)

            # 5. Enforce timeout on hung analysis.py
            real_analysis.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
            errs_to = validate_report.reproduce(ws, timeout=1)
            self.assertTrue(any("timed out" in e for e in errs_to), errs_to)
        finally:
            tmp.cleanup()

    def test_reproduce_supports_nested_multiprocessing_pool_under_spawn(self) -> None:
        """reproduce() works even when analysis.py uses multiprocessing.Pool."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "appendix"
            app.mkdir()
            (root / "report.md").write_text("# R\n", encoding="utf-8")
            (app / "README.md").write_text(
                "```bash\npython3 -B appendix/analysis.py > appendix/output.txt\n```\n",
                encoding="utf-8",
            )
            (app / "analysis.py").write_text(
                "from multiprocessing import Pool\n"
                "def cube(n):\n"
                "    return n * n * n\n"
                "if __name__ == '__main__':\n"
                "    with Pool(2) as pool:\n"
                "        vals = pool.map(cube, [1, 2, 3])\n"
                "    print('sum=' + str(sum(vals)))\n",
                encoding="utf-8",
            )
            (app / "output.txt").write_text("sum=36\n", encoding="utf-8")
            errs = validate_report.reproduce(root, timeout=15)
            self.assertEqual(errs, [], errs)


if __name__ == "__main__":
    unittest.main()
