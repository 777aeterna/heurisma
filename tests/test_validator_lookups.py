"""v0.7.0 Phase 1: the validator verifies against artifacts (recomputed hashes, sources.csv lookups) instead of
trusting strings written in the report. Fixtures are edited copies of the golden example (see mutations.py)."""

import csv
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402


def msgs_after(fn, render=True, level=2):
    tmp, ws = M.fresh_workspace()
    try:
        fn(ws)
        if render:
            M.rerender(ws)
        return M.detect(ws, level=level)
    finally:
        tmp.cleanup()


def any_match(msgs, pattern):
    return any(re.search(pattern, m) for m in msgs)


class TestRecomputedHashes(unittest.TestCase):
    def test_changed_data_file_is_reported_with_both_hashes(self) -> None:
        msgs = msgs_after(M.m01_data_value_changed)
        self.assertTrue(any_match(msgs, r"hybrid_rct_sites\.csv.*changed since it was registered.*9a7419cd6056"), msgs)

    def test_fake_declared_hash_is_reported(self) -> None:
        msgs = msgs_after(M.m02_fake_sha)
        self.assertTrue(any_match(msgs, r"deadbeef0000"), msgs)

    def test_file_with_declared_hash_but_missing_on_disk_is_flagged(self) -> None:
        def gone(ws: Path) -> None:
            (ws / "appendix" / "data" / "hybrid_rct_sites.csv").unlink()

        msgs = msgs_after(gone)
        self.assertTrue(any_match(msgs, r"hybrid_rct_sites\.csv.*not found"), msgs)

    def test_download_log_hash_is_recomputed(self) -> None:
        def with_log(ws: Path) -> None:
            data = ws / "appendix" / "data" / "hybrid_rct_sites.csv"
            (ws / "appendix" / "download_log.csv").write_text(
                "file,url,retrieved_utc,bytes,sha256\n"
                f"hybrid_rct_sites.csv,https://example.org/x.csv,2026-11-20T10:00:00Z,{data.stat().st_size},"
                + "0" * 64
                + "\n",
                encoding="utf-8",
            )

        msgs = msgs_after(with_log)
        self.assertTrue(any_match(msgs, r"download_log\.csv.*hybrid_rct_sites\.csv.*changed"), msgs)

    def test_untouched_golden_example_is_clean(self) -> None:
        self.assertEqual(M.baseline(), [])


class TestStrongClaimsUseSourceLookup(unittest.TestCase):
    def test_relabelled_tier3_in_prose_does_not_hide_the_weak_source(self) -> None:
        msgs = msgs_after(M.m05_strong_on_relabelled_tier3)
        self.assertTrue(any_match(msgs, r"\[Strong\].*only on weak source.*C1"), msgs)

    def test_strong_row_without_citation_is_an_error(self) -> None:
        msgs = msgs_after(M.m06_strong_without_citation)
        self.assertTrue(any_match(msgs, r"\[Strong\].*no \[@id\] citation"), msgs)

    def test_strong_on_own_computation_only_is_an_error(self) -> None:
        msgs = msgs_after(M.m11_strong_on_own_computation_only)
        self.assertTrue(any_match(msgs, r"\[Strong\].*only on weak source.*C4"), msgs)

    def test_strong_with_one_independent_source_is_accepted(self) -> None:
        def strong_ok(ws: Path) -> None:
            row_old = "| 2-day hybrid work lowers quit rates by about one-third | Labor Economics | Trip.com randomized trial [@C2], Tier 1, 2024-06 | `[Moderate]` |"
            M._edit(ws, "report.md", row_old, row_old.replace("`[Moderate]`", "`[Strong]`"))

        msgs = msgs_after(strong_ok)
        self.assertFalse(any_match(msgs, r"\[Strong\].*(weak source|no \[@id\])"), msgs)

    def test_abstract_only_source_is_weak(self) -> None:
        def abstract_strong(ws: Path) -> None:
            row = "| Proximity to teammates raises coding feedback"
            text = (ws / "report.md").read_text(encoding="utf-8")
            i = text.index(row)
            j = text.index("\n", i)
            line = text[i:j].replace("`[Moderate]`", "`[Strong]`")
            (ws / "report.md").write_text(text[:i] + line + text[j:], encoding="utf-8")

        msgs = msgs_after(abstract_strong)
        self.assertTrue(any_match(msgs, r"\[Strong\].*only on weak source.*C3"), msgs)


class TestKindColumn(unittest.TestCase):
    def test_missing_kind_column_names_kind(self) -> None:
        msgs = msgs_after(M.m10_kind_column_removed)
        self.assertTrue(any_match(msgs, r"sources\.csv.*\bkind\b.*column"), msgs)

    def test_invalid_kind_value_is_an_error(self) -> None:
        def bad(ws: Path) -> None:
            M._edit(ws, "appendix/sources.csv", ",literature\n", ",paper\n")

        msgs = msgs_after(bad)
        self.assertTrue(any_match(msgs, r"kind 'paper'"), msgs)

    def test_blank_kind_value_is_an_error(self) -> None:
        def blank(ws: Path) -> None:
            M._rewrite_csv(ws, "appendix/sources.csv", lambda rows, cols: ([dict(r, kind="") for r in rows], cols))

        msgs = msgs_after(blank)
        self.assertTrue(any_match(msgs, r"has no kind"), msgs)

    def test_local_data_writes_kind_and_sha256_columns(self) -> None:
        import tempfile

        import local_data

        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "appendix" / "data").mkdir(parents=True)
            f = root / "appendix" / "data" / "x.csv"
            f.write_text("a\n1\n", encoding="utf-8")
            row = local_data.register_local(f, root / "appendix" / "sources.csv", "Tier 2", "X", relative_to=root)
            with (root / "appendix" / "sources.csv").open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["kind"], "data")
            self.assertEqual(rows[0]["sha256"], local_data.sha256_file(f))
            self.assertEqual(row["kind"], "data")


class TestVerdictLimits(unittest.TestCase):
    def test_bloated_verdict_is_an_error(self) -> None:
        msgs = msgs_after(M.m07_bloated_verdict)
        self.assertTrue(any_match(msgs, r"Calibrated Verdict has \d+ sentences"), msgs)
        self.assertTrue(any_match(msgs, r"Calibrated Verdict has \d+ numbers"), msgs)

    def test_years_hyphenated_words_and_citations_are_not_counted(self) -> None:
        def ok_verdict(ws: Path) -> None:
            text = (ws / "report.md").read_text(encoding="utf-8")
            m = re.search(r"- \*\*Calibrated Verdict:\*\*.*", text)
            line = (
                "- **Calibrated Verdict:** A 6-month, 12-site study from 2024 [@C2] reports a 4.80% quit rate. "
                "The 2026 site file agrees `[Moderate]`."
            )
            (ws / "report.md").write_text(text[: m.start()] + line + text[m.end():], encoding="utf-8")

        msgs = msgs_after(ok_verdict)
        self.assertFalse(any_match(msgs, r"Calibrated Verdict has"), msgs)

    def test_spanish_verdict_is_checked_too(self) -> None:
        import validate_report

        text = (
            "**Veredicto calibrado:** Uno 1.5. Dos 2.5. Tres 3.5. Cuatro 4.5 `[Moderada]`.\n"
        )
        errs, _ = validate_report.validate_report_full(text, level=1)
        self.assertTrue(any_match(errs, r"Calibrated Verdict has 4 sentences"), errs)


class TestHomePaths(unittest.TestCase):
    def test_home_path_in_report_is_an_error(self) -> None:
        msgs = msgs_after(M.m19_home_path_in_report)
        self.assertTrue(any_match(msgs, r"home-directory path"), msgs)

    def test_home_path_in_html_is_an_error(self) -> None:
        def html_only(ws: Path) -> None:
            pass

        tmp, ws = M.fresh_workspace()
        try:
            M.rerender(ws)
            h = ws / "report.html"
            h.write_text(h.read_text(encoding="utf-8").replace("</body>", "<p>/Users/maria/x</p></body>"), encoding="utf-8")
            import validate_report

            errs, _ = validate_report.validate_html_full(h)
            self.assertTrue(any_match(errs, r"home-directory path"), errs)
        finally:
            tmp.cleanup()


class TestOrphanDataFiles(unittest.TestCase):
    """P1-2: registered means the exact relative path (or declared hash), never a substring of the CSV text."""

    def test_unregistered_file_whose_name_is_a_substring_is_an_orphan(self) -> None:
        msgs = msgs_after(M.m09_unregistered_substring_file)
        self.assertTrue(any_match(msgs, r"Orphan data file 'appendix/data/sites\.csv'"), msgs)

    def test_import_of_a_file_with_spaces_and_accents_is_not_an_orphan(self) -> None:
        import local_data

        def imported(ws: Path) -> None:
            src = ws / "datos" / "serie IPC señal.csv"
            src.parent.mkdir()
            src.write_text("fecha;valor\n2026-01-01;1,5\n", encoding="utf-8")
            local_data.import_local(src, ws / "appendix" / "data", ws / "appendix" / "sources.csv", "Tier 3", "Serie IPC")

        msgs = msgs_after(imported)
        self.assertFalse(any_match(msgs, r"Orphan"), msgs)

    def test_file_logged_only_in_download_log_by_name_is_registered(self) -> None:
        def logged(ws: Path) -> None:
            f = ws / "appendix" / "data" / "extra.csv"
            f.write_text("a;b\n1;2\n", encoding="utf-8")
            (ws / "appendix" / "download_log.csv").write_text(
                "file,url,retrieved_utc,bytes,sha256\n"
                f"extra.csv,https://example.org/extra.csv,2026-11-20T10:00:00Z,{f.stat().st_size},"
                f"{__import__('hashlib').sha256(f.read_bytes()).hexdigest()}\n",
                encoding="utf-8",
            )

        msgs = msgs_after(logged)
        self.assertFalse(any_match(msgs, r"Orphan"), msgs)

    def test_file_in_a_subfolder_is_matched_by_its_relative_path(self) -> None:
        def nested(ws: Path) -> None:
            (ws / "appendix" / "data" / "sub").mkdir()
            (ws / "appendix" / "data" / "sub" / "hybrid_rct_sites.csv").write_text("x\n1\n", encoding="utf-8")

        msgs = msgs_after(nested)
        self.assertTrue(any_match(msgs, r"Orphan data file 'appendix/data/sub/hybrid_rct_sites\.csv'"), msgs)


if __name__ == "__main__":
    unittest.main()
