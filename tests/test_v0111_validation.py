"""Offline regression tests for the Heurisma report validator and gate checks.

These tests use synthetic report fixtures (no network, no source modification) and cover the
findings fixed in this pass: R4, VAL-1, VAL-2, VAL-3, VAL-4, VAL-7, VAL-10, VAL-13, VAL-14 (plus
VAL-9 and VAL-11 as a bonus). Run with ``python3 -B tests/test_validation.py``.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

import validate_report as vr  # noqa: E402
from checks import common, gates  # noqa: E402


def full_report(sec3: str | None = None, sec5: str | None = None, sec7: str | None = None) -> str:
    """A minimal 7-section Heurisma report; callers override Section 3/5/7 to exercise gate logic."""
    parts = [
        "## 1. Executive Summary",
        "This executive summary is long enough to satisfy the minimum word count and to describe the inquiry and its verdict clearly.",
        "",
        "## 2. Framing & Hypotheses",
        "H0 is the null hypothesis and H1 is the alternative hypothesis; both are stated here explicitly.",
        "",
        "## 3. Methodology & Evidence Standards",
        sec3 if sec3 is not None else "Methodology details and evidence standards are described here in enough words.",
        "",
        "## 4. Findings",
        "The findings section presents the analysis results with citations and calibrated confidence tags in enough words.",
        "",
        "## 5. Counter-Evidence & Alternative Explanations",
        sec5 if sec5 is not None else "Counter-evidence and alternative explanations are discussed here.",
        "",
        "## 6. Claim-Evidence Matrix",
        "| Claim | Discipline | Evidence | Tag | Falsifier |",
        "| :- | :- | :- | :- | :- |",
        "| A claim | Science | [@C1], Tier 1 | [Moderate] | A test |",
        "",
        "## 7. Limitations & Open Questions",
        sec7 if sec7 is not None else "Limitations and open questions are listed here.",
    ]
    return "\n".join(parts) + "\n"


def make_report_dir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="heurisma_test_"))
    (d / "appendix").mkdir()
    (d / "appendix" / "gates").mkdir(parents=True)
    return d


def _sv_gate(problem_lines: str, fail_line: str = "SOURCE-VERIFIER: FAIL (1 problems)") -> str:
    return (
        "MODE: subagent\n"
        "REVIEWED-SHA256: " + "a" * 64 + "\n"
        "REVIEWED-UTC: 2026-11-21T14:05:00Z\n"
        'QUOTE: appendix/sources.csv:1: "x"\n'
        'QUOTE: appendix/sources.csv:2: "y"\n'
        + "1. PASS — ok\n" * 7
        + problem_lines
        + fail_line + "\n"
    )


def _qa_gate(fail_line: str | None = "3 FAIL — some evidence") -> str:
    lines = [
        "MODE: subagent",
        "REVIEWED-SHA256: " + "b" * 64,
        "REVIEWED-UTC: 2026-11-21T14:05:00Z",
        'QUOTE: report.md:1: "x"',
        'QUOTE: report.md:2: "y"',
        "QA: FAIL (1 checks failed)",
        "1 PASS — ok",
        "2 PASS — ok",
    ]
    if fail_line is not None:
        lines.append(fail_line)
    lines += ["4 PASS — ok", "5 PASS — ok", "6 PASS — ok", "7 PASS — ok", "8 PASS — ok", "FAIL count: 1"]
    return "\n".join(lines) + "\n"


class TestR4SourceVerifier(unittest.TestCase):
    def test_fail_without_list_number(self):
        d = make_report_dir()
        (d / "appendix" / "gates" / "source_verifier.md").write_text(
            _sv_gate("3 · C6 · tier overstated · lower\n"), encoding="utf-8")
        sec7 = "We cite gates/source_verifier.md: accepted problem C6 with justification."
        _, warnings = vr.validate_report_full(full_report(sec7=sec7), level=2, report_dir=d)
        self.assertFalse(any("ends in SOURCE-VERIFIER: FAIL" in w for w in warnings), warnings)

    def test_fail_with_list_number(self):
        d = make_report_dir()
        (d / "appendix" / "gates" / "source_verifier.md").write_text(
            _sv_gate("1. 3 · C6 · tier overstated · lower\n"), encoding="utf-8")
        sec7 = "We cite gates/source_verifier.md: accepted problem C6 with justification."
        _, warnings = vr.validate_report_full(full_report(sec7=sec7), level=2, report_dir=d)
        self.assertFalse(any("ends in SOURCE-VERIFIER: FAIL" in w for w in warnings), warnings)

    def test_fail_without_extractable_problem_is_error(self):
        # Regression for the all([]) vacuous-true hole: FAIL + no problem line must error.
        d = make_report_dir()
        (d / "appendix" / "gates" / "source_verifier.md").write_text(
            _sv_gate("Problems: none\n"), encoding="utf-8")
        sec7 = "We cite gates/source_verifier.md."
        _, warnings = vr.validate_report_full(full_report(sec7=sec7), level=2, report_dir=d)
        self.assertTrue(any("ends in SOURCE-VERIFIER: FAIL" in w for w in warnings), warnings)


class TestVal1MalformedUtf8(unittest.TestCase):
    def test_malformed_charts_json_yields_coded_error_not_traceback(self):
        d = make_report_dir()
        (d / "appendix" / "charts.json").write_bytes(b"\xff\xfe\x00\x80")
        errors, _ = vr.validate_report_full(full_report(), level=2, report_dir=d)
        self.assertTrue(any("Invalid JSON" in e for e in errors), errors)

    def test_malformed_sources_csv_does_not_crash(self):
        d = make_report_dir()
        (d / "appendix" / "sources.csv").write_bytes(b"\xff\xfe\x00\x80")
        rows, cols = common._load_sources_rows(d)
        self.assertIsInstance(rows, list)
        self.assertIsInstance(cols, list)


class TestVal2Redirect(unittest.TestCase):
    def test_absolute_redirect_refused(self):
        result = vr.reproduce(
            Path(tempfile.mkdtemp()), "python3 -B appendix/analysis.py > /tmp/heurisma_escaped.txt"
        )
        self.assertTrue(any("redirect target must stay inside" in r for r in result), result)

    def test_dotdot_redirect_refused(self):
        result = vr.reproduce(
            Path(tempfile.mkdtemp()), "python3 -B appendix/analysis.py > ../escaped.txt"
        )
        self.assertTrue(any("redirect target must stay inside" in r for r in result), result)


class TestVal3FileEscape(unittest.TestCase):
    def _assert_inside(self, p: Path, root: Path):
        root = root.resolve()
        self.assertTrue(p == root or root in p.parents, f"{p} escapes {root}")

    def test_file_absolute_url_is_project_relative(self):
        d = make_report_dir()
        p = common._local_source_path("file:///etc/hostname", d)
        self._assert_inside(p, d)
        self.assertNotEqual(p, Path("/etc/hostname"))

    def test_file_dotdot_escape_refused(self):
        d = make_report_dir()
        p = common._local_source_path("file://../secret", d)
        self._assert_inside(p, d)


class TestVal4Disposition(unittest.TestCase):
    def test_action_cell_outside_section5_not_counted(self):
        d = make_report_dir()
        (d / "appendix" / "gates" / "reviewer.md").write_text(
            "1. [Over-calibrated claims] The claim is over-calibrated — fix it — add a control.\n", encoding="utf-8")
        sec3 = (
            "| Target | Source | Outcome |\n"
            "| :- | :- | :- |\n"
            "| X | api | Deferred |\n"
        )
        sec5 = (
            "### Reviewer #2 Disposition Table\n"
            "| # | Critique | Action |\n"
            "| :- | :- | :- |\n"
            "| 1 | Some critique | Fixed |\n"
        )
        errors, _ = vr.validate_report_full(full_report(sec3=sec3, sec5=sec5), level=3, report_dir=d)
        self.assertFalse(any("Reviewer #2 raised" in e for e in errors), errors)

    def test_missing_section5_row_is_error(self):
        d = make_report_dir()
        (d / "appendix" / "gates" / "reviewer.md").write_text(
            "1. [Over-calibrated claims] The claim is over-calibrated — fix it — add a control.\n", encoding="utf-8")
        sec5 = (
            "### Reviewer #2 Disposition Table\n"
            "| # | Critique | Action |\n"
            "| :- | :- | :- |\n"
            "| 1 | Some critique | Pending |\n"
        )
        errors, _ = vr.validate_report_full(full_report(sec5=sec5), level=3, report_dir=d)
        self.assertTrue(any("Reviewer #2 raised" in e for e in errors), errors)


class TestVal7QaNaming(unittest.TestCase):
    def test_named_failed_check_passes(self):
        d = make_report_dir()
        (d / "appendix" / "gates" / "qa.md").write_text(_qa_gate("3 FAIL — some evidence"), encoding="utf-8")
        sec7 = "We cite gates/qa.md: accepted FAIL check 3 with justification."
        _, warnings = vr.validate_report_full(full_report(sec7=sec7), level=2, report_dir=d)
        self.assertFalse(any("has no 'QA: PASS' line" in w for w in warnings), warnings)

    def test_unnamed_failed_check_errors(self):
        d = make_report_dir()
        (d / "appendix" / "gates" / "qa.md").write_text(_qa_gate("3 FAIL — some evidence"), encoding="utf-8")
        sec7 = "We cite gates/qa.md but name no failed check number."
        _, warnings = vr.validate_report_full(full_report(sec7=sec7), level=2, report_dir=d)
        self.assertTrue(any("has no 'QA: PASS' line" in w for w in warnings), warnings)

    def test_fail_without_check_number_errors(self):
        d = make_report_dir()
        (d / "appendix" / "gates" / "qa.md").write_text(_qa_gate(fail_line=None), encoding="utf-8")
        sec7 = "We cite gates/qa.md."
        _, warnings = vr.validate_report_full(full_report(sec7=sec7), level=2, report_dir=d)
        self.assertTrue(any("has no 'QA: PASS' line" in w for w in warnings), warnings)


class TestVal10Sha(unittest.TestCase):
    def test_12_hex_rejected_64_accepted(self):
        self.assertIsNone(common.SHA_HEX_RE.search("a" * 12))
        self.assertIsNotNone(common.SHA_HEX_RE.search("a" * 64))
        self.assertEqual(common._declared_sha({"sha256": "a" * 12}), "")
        self.assertEqual(common._declared_sha({"sha256": "a" * 64}), "a" * 64)

    def test_gate_header_requires_64(self):
        pattern = gates.GATE_HEADER_FIELDS[1][1]
        self.assertIsNone(re.search(pattern, "REVIEWED-SHA256: " + "a" * 12))
        self.assertIsNotNone(re.search(pattern, "REVIEWED-SHA256: " + "a" * 64))


class TestVal13Interpreter(unittest.TestCase):
    def test_python_dot_version_accepted(self):
        d = make_report_dir()
        (d / "appendix" / "analysis.py").write_text(
            "from pathlib import Path\n"
            "a = Path(__file__).resolve().parent\n"
            "(a / 'output.txt').write_text('hi\\n', encoding='utf-8')\n"
            "(a / 'numbers.json').write_text('{}', encoding='utf-8')\n",
            encoding="utf-8",
        )
        result = vr.reproduce(d, "python3.11 -B appendix/analysis.py")
        self.assertFalse(any("unsupported command" in r for r in result), result)


class TestVal14HomePath(unittest.TestCase):
    def test_bare_home_and_users_matched(self):
        self.assertIsNotNone(common.HOME_PATH_RE.search("/home/alice"))
        self.assertIsNotNone(common.HOME_PATH_RE.search("/Users/alice"))


class TestVal9ReadmeParser(unittest.TestCase):
    def test_single_backtick_stops_at_prose(self):
        d = make_report_dir()
        (d / "appendix" / "README.md").write_text(
            "Run `python3 -B appendix/analysis.py parses the tables` to build charts.\n", encoding="utf-8")
        self.assertEqual(vr._readme_analysis_command(d), "python3 -B appendix/analysis.py")

    def test_double_backtick_handled(self):
        d = make_report_dir()
        (d / "appendix" / "README.md").write_text("Command: ``python3 -B appendix/analysis.py``\n", encoding="utf-8")
        self.assertEqual(vr._readme_analysis_command(d), "python3 -B appendix/analysis.py")

    def test_bare_list_line_stops_at_prose(self):
        d = make_report_dir()
        (d / "appendix" / "README.md").write_text("2. python3 -B appendix/analysis.py parses the tables\n", encoding="utf-8")
        self.assertEqual(vr._readme_analysis_command(d), "python3 -B appendix/analysis.py")


class TestVal11SealedArtifacts(unittest.TestCase):
    def test_resealed_conjectures_detected(self):
        d = make_report_dir()
        (d / "appendix" / "analysis.py").write_text(
            "from pathlib import Path\n"
            "a = Path(__file__).resolve().parent\n"
            "(a / 'output.txt').write_text('hi\\n', encoding='utf-8')\n"
            "(a / 'numbers.json').write_text('{}', encoding='utf-8')\n"
            "p = a / 'conjectures.json'\n"
            "p.write_text(p.read_text(encoding='utf-8') + ' resealed\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        (d / "appendix" / "conjectures.json").write_text('{"sealed": true}\n', encoding="utf-8")
        result = vr.reproduce(d, "python3 -B appendix/analysis.py")
        self.assertTrue(any("sealed artifacts must not change" in r for r in result), result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
