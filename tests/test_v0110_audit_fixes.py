"""Audit regression tests for v0.11.0 Phase 1 fixes (H-01 strict CLI output, Windows utf-8 & encoding hygiene)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "heurisma" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestV0110AuditFixes(unittest.TestCase):
    def test_h01_strict_mode_lists_promoted_warnings_under_failed_header(self) -> None:
        """H-01: When --strict fails solely due to warnings, the numbered list beneath FAILED names them."""
        brief = (REPO_ROOT / "examples" / "level1-brief-example.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            rep = ws / "report.md"
            html = ws / "report.html"
            rep.write_text(brief, encoding="utf-8")
            # Render HTML without source hash comment -> triggers 1 warning (HTML-STALE), 0 errors
            proc_render = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS_DIR / "render_report.py"), str(rep), "--out", str(html)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(proc_render.returncode, 0, proc_render.stderr)
            # Edit report.md slightly so HTML becomes stale (warning, not error)
            rep.write_text(brief + "\n<!-- trailing comment -->\n", encoding="utf-8")

            proc_val = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPTS_DIR / "validate_report.py"),
                    str(rep),
                    "--level",
                    "1",
                    "--html",
                    str(html),
                    "--strict",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(proc_val.returncode, 1)
            self.assertIn("Heurisma report validation FAILED (1 violation(s)):", proc_val.stderr)
            after_failed = proc_val.stderr.split("Heurisma report validation FAILED (1 violation(s)):", 1)[1]
            self.assertIn("1.", after_failed, f"Expected numbered violation under FAILED header, got:\n{proc_val.stderr}")
            self.assertIn("stale", after_failed.lower())

    def test_new_entrypoints_reconfigure_utf8_stdio(self) -> None:
        from unittest import mock  # noqa: PLC0415

        import conjecture  # noqa: PLC0415
        import formal_math  # noqa: PLC0415
        from test_windows_compat import _FakeStream  # noqa: PLC0415

        for mod in (conjecture, formal_math):
            fake_out = _FakeStream()
            fake_err = _FakeStream()
            with mock.patch.object(sys, "stdout", fake_out), mock.patch.object(sys, "stderr", fake_err):
                try:
                    mod.main(["--version"])
                except SystemExit:
                    pass
            self.assertTrue(any(c.get("encoding") == "utf-8" for c in fake_out.reconfigured))
            self.assertTrue(any(c.get("encoding") == "utf-8" for c in fake_err.reconfigured))


if __name__ == "__main__":
    unittest.main()
