"""v0.9.0 Phase 3 tests: a mis-capitalised tag gets a precise diagnosis (N3); inbox/ honours intake.md (N5)."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402

TAG_RE = re.compile(r"\[(Strong|Moderate|Preliminary|Speculative)\]")


def has(msgs: list[str], pattern: str) -> bool:
    return any(re.search(pattern, m) for m in msgs)


def full(ws: Path, level: int = 2) -> tuple[list[str], list[str]]:
    M.restamp_gates(ws)
    return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)


class TestNoncanonicalTags(unittest.TestCase):
    def test_helper_finds_case_variants_only(self) -> None:
        text = "A [fuerte] claim, a [STRONG] one, a canonical [Moderate] one, and a [citation needed]."
        self.assertEqual(validate_report._noncanonical_tags(text), ["[fuerte]", "[STRONG]"])
        self.assertEqual(validate_report._noncanonical_tags("only [Strong] and [Fuerte]"), [])

    def test_matrix_row_gets_one_precise_message(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M._edit(ws, "report.md", M._ROW2, M._ROW2.replace("`[Preliminary]`", "`[preliminary]`"))
            e, _ = full(ws)
            row = [m for m in e if m.startswith("Claim-Evidence Matrix row 2")]
            self.assertEqual(len(row), 1, e)
            self.assertIn("'[preliminary]'", row[0])
            self.assertIn("'[Preliminary]'", row[0])
            self.assertNotIn("missing a canonical", row[0])
            self.assertEqual(validate_report.classify_message(row[0])[0], "MATRIX")
        finally:
            tmp.cleanup()

    def test_all_lowercase_report_explains_capitalisation_once(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            text = TAG_RE.sub(lambda m: m.group(0).lower(), (ws / "report.md").read_text(encoding="utf-8"))
            (ws / "report.md").write_text(text, encoding="utf-8")
            e, _ = full(ws)
            glob = [m for m in e if m.startswith("Missing epistemic calibration tags")]
            self.assertEqual(len(glob), 1, e)
            self.assertIn("case-sensitive", glob[0])
            self.assertIn("'[preliminary]'", glob[0])
            self.assertEqual(validate_report.classify_message(glob[0])[0], "STRUCT-TAGS")
            self.assertFalse([m for m in e if "missing a canonical" in m and "writes" in m])
        finally:
            tmp.cleanup()

    def test_report_without_any_tag_keeps_the_original_message(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            text = re.sub(r"`?\[(Strong|Moderate|Preliminary|Speculative)\]`?", "", (ws / "report.md").read_text(encoding="utf-8"))
            (ws / "report.md").write_text(text, encoding="utf-8")
            e, _ = full(ws)
            glob = [m for m in e if m.startswith("Missing epistemic calibration tags")]
            self.assertEqual(len(glob), 1, e)
            self.assertNotIn("case-sensitive", glob[0])
        finally:
            tmp.cleanup()

    def test_lowercase_is_still_not_accepted_as_a_strong_tag(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m34_bare_digit_tier_dodges_tier3_rules(ws)  # a [Strong] row on weak evidence
            M._edit(ws, "report.md", "Supplied CSV [@C1], 2026-10 | `[Strong]`", "Supplied CSV [@C1], 2026-10 | `[strong]`")
            e, _ = full(ws)
            self.assertTrue(has(e, r"writes '\[strong\]'"), e)
        finally:
            tmp.cleanup()


class TestInboxHonoursIntake(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp, self.ws = M.fresh_workspace()
        inbox = self.ws / "inbox" / "sources"
        (inbox / "media").mkdir(parents=True)
        (inbox / "doc.md").write_text("a document\n", encoding="utf-8")
        (inbox / "media" / "pic.png").write_bytes(b"\x89PNG not really")
        (inbox / "other.png").write_bytes(b"\x89PNG other")
        (inbox / ".DS_Store").write_bytes(b"junk")
        (inbox / "media" / ".gitkeep").write_bytes(b"")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _intake(self, lines: str) -> None:
        (self.ws / "appendix" / "intake.md").write_text("# Intake report\n\n## Channel: sources\n\n" + lines, encoding="utf-8")

    def _flagged(self) -> list[str]:
        rows, _ = validate_report._load_sources_rows(self.ws)
        return validate_report.check_inbox(self.ws, rows)

    def test_without_intake_every_unregistered_file_is_flagged_but_dotfiles_are_not(self) -> None:
        flagged = " ".join(self._flagged())
        for name in ("doc.md", "media/pic.png", "other.png"):
            self.assertIn(f"inbox/sources/{name}", flagged)
        self.assertNotIn(".DS_Store", flagged)
        self.assertNotIn(".gitkeep", flagged)

    def test_files_listed_by_intake_are_attended(self) -> None:
        self._intake("- accepted: doc.md -> [@L1] (sha256 abc123abc123)\n- rejected: media/pic.png — not a table (png); use --channel sources for documents\n")
        flagged = " ".join(self._flagged())
        self.assertNotIn("doc.md", flagged)
        self.assertNotIn("pic.png", flagged)
        self.assertIn("inbox/sources/other.png", flagged)

    def test_a_path_must_match_on_a_directory_boundary(self) -> None:
        self._intake("- rejected: ic.png — not a table\n")
        self.assertIn("inbox/sources/media/pic.png", " ".join(self._flagged()))

    def test_end_to_end_warning_disappears_for_a_rejected_file(self) -> None:
        self._intake("- rejected: other.png — not a table\n- rejected: media/pic.png — not a table\n- accepted: doc.md -> [@L1] (sha256 abc123abc123)\n")
        _, w = full(self.ws)
        self.assertFalse(has(w, r"^inbox/"), w)


if __name__ == "__main__":
    unittest.main()
