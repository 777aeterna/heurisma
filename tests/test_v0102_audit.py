"""v0.10.2 pre-release audit regression tests: LF CSV writers, clone-safe Level 3 showcase, EXCLUDED.csv hardening, and edge cases."""

from __future__ import annotations

import fnmatch
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "heurisma" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import contracts  # noqa: E402
import fetch_lib  # noqa: E402
import local_data  # noqa: E402
import mutations as M  # noqa: E402
import papers  # noqa: E402
import render_report  # noqa: E402
from test_papers_core import REAL, Base, read_csv  # noqa: E402
import validate_report  # noqa: E402
from checks import codes, gates, html as html_checks, numeric, provenance  # noqa: E402


def _has_negated_text_attr(gitattributes_text: str, rel_posix: str) -> bool:
    """Evaluate .gitattributes rules in order to check whether rel_posix ends with -text."""
    negated = False
    for raw_line in gitattributes_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        pattern, attrs = parts[0], parts[1:]
        matched = fnmatch.fnmatch(rel_posix, pattern) or (
            "/" not in pattern and fnmatch.fnmatch(Path(rel_posix).name, pattern)
        )
        if matched:
            if "-text" in attrs or "binary" in attrs:
                negated = True
            elif any(a == "text" or a.startswith("text=") or a.startswith("eol=") for a in attrs):
                negated = False
    return negated


class TestCsvLfAndCloneSafety(unittest.TestCase):
    """Finding 1 (P0): CSV writers emit LF, and a fresh git checkout preserves Level 3 gate/HTML hashes."""

    def test_csv_writers_emit_lf_not_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            p_atomic = base_dir / "papers.csv"
            papers._write_atomic(p_atomic, ("doi", "title"), [{"doi": "10.9999/x", "title": "Alpha"}])
            self.assertNotIn(b"\r\n", p_atomic.read_bytes())

            p_dl = base_dir / "download_log.csv"
            fetch_lib._log_download(
                p_dl,
                {"file": "a.csv", "url": "https://example.org/a.csv", "retrieved_utc": "2026-11-23T00:00:00Z", "bytes": 5, "sha256": "0" * 64},
            )
            self.assertNotIn(b"\r\n", p_dl.read_bytes())

            p_app = base_dir / "attempts.csv"
            local_data._append_row(p_app, ("col_a",), {"col_a": "1"})
            self.assertNotIn(b"\r\n", p_app.read_bytes())
            # Widening an existing CSV with a new column also writes LF
            local_data._append_row(p_app, ("col_a", "col_b"), {"col_a": "2", "col_b": "3"})
            self.assertNotIn(b"\r\n", p_app.read_bytes())

    def test_level3_showcase_survives_git_eol_normalization(self) -> None:
        gitattr = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
        showcase_rel = "examples/level3-emergence-in-physics"
        excl = REPO_ROOT / showcase_rel / "appendix" / "data" / "papers" / "EXCLUDED.csv"
        self.assertNotIn(b"\r\n", excl.read_bytes(), "EXCLUDED.csv must use LF line endings")
        for csv_name in ("download_log.csv", "papers.csv", "search_log.csv", "sources.csv"):
            rel = f"{showcase_rel}/appendix/{csv_name}"
            self.assertTrue(_has_negated_text_attr(gitattr, rel), f"{rel} must carry -text in .gitattributes")

        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "level3-emergence-in-physics"
            shutil.copytree(REPO_ROOT / showcase_rel, dst)
            for p in dst.rglob("*"):
                if not p.is_file():
                    continue
                rel_repo = f"{showcase_rel}/{p.relative_to(dst).as_posix()}"
                if not _has_negated_text_attr(gitattr, rel_repo):
                    raw = p.read_bytes()
                    if b"\r\n" in raw:
                        p.write_bytes(raw.replace(b"\r\n", b"\n"))
            errors, warnings = validate_report.validate_report_full(
                (dst / "report.md").read_text(encoding="utf-8"), level=3, report_dir=dst
            )
            warnings.extend(html_checks.check_html_freshness(dst / "report.html", dst / "report.md"))
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])


class TestWithheldManifestHardening(unittest.TestCase):
    """Finding 3 (P2): EXCLUDED.csv handles None, requires papers.csv, and flags malformed rows as P3-PAPER."""

    def test_read_withheld_none_returns_empty_dict(self) -> None:
        import os

        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                decoy = Path(tmp) / "None" / contracts.WITHHELD_MANIFEST
                decoy.parent.mkdir(parents=True, exist_ok=True)
                decoy.write_text(f"file,sha256,reason\na.pdf,{'a' * 64},decoy\n", encoding="utf-8")
                self.assertEqual(contracts.read_withheld(None), {})
                self.assertEqual(contracts.read_withheld(""), {})
            finally:
                os.chdir(old_cwd)

    def test_manifest_without_papers_csv_is_an_error_and_not_rendered(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            self.assertFalse((ws / "appendix" / "papers.csv").exists())
            manifest = ws / "appendix" / contracts.WITHHELD_MANIFEST
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(f"file,sha256,reason\nghost.pdf,{'b' * 64},licensing\n", encoding="utf-8")
            M.restamp_gates(ws)
            errors, _ = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws)
            matched = [e for e in errors if e.startswith(f"appendix/{contracts.WITHHELD_MANIFEST}: ")]
            self.assertTrue(matched, errors)
            self.assertEqual(codes.classify_message(matched[0])[0], "P3-PAPER")
            rendered = render_report._render_appendices(ws / "appendix", render_report.I18N["en"])
            self.assertNotIn("withheld", rendered.lower())
        finally:
            tmp.cleanup()

    def test_malformed_manifest_rows_are_reported_as_p3_paper_errors(self) -> None:
        cases = (
            ("missing_col", "file,reason\na.pdf,licensing\n"),
            ("path_sep", f"file,sha256,reason\npapers/a.pdf,{'c' * 64},licensing\n"),
            ("empty_sha", "file,sha256,reason\na.pdf,,licensing\n"),
            ("short_sha", "file,sha256,reason\na.pdf,1234abcd,licensing\n"),
        )
        for label, content in cases:
            with self.subTest(label=label):
                tmp, ws = M.fresh_workspace()
                try:
                    M._papers_workspace(ws)
                    manifest = ws / "appendix" / contracts.WITHHELD_MANIFEST
                    manifest.parent.mkdir(parents=True, exist_ok=True)
                    manifest.write_text(content, encoding="utf-8")
                    M.restamp_gates(ws)
                    errors, _ = validate_report.validate_report_full(
                        (ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws
                    )
                    matched = [e for e in errors if e.startswith(f"appendix/{contracts.WITHHELD_MANIFEST}: ")]
                    self.assertTrue(matched, f"{label}: {errors}")
                    self.assertEqual(codes.classify_message(matched[0])[0], "P3-PAPER")
                finally:
                    tmp.cleanup()


class TestSanitizationAndEdgeCases(Base):
    """Finding 2 (P1) & Finding 4 (P3): repo sanitization, arXiv OA bucket, signed zero, and backslash quote paths."""

    def test_repository_contains_no_local_audit_filenames_or_private_markers(self) -> None:
        # Build patterns via concatenation so this test file itself does not contain literal forbidden markers.
        forbidden = (
            "reporte-tecnico-" + "heurisma",
            "bitacora" + ".md",
            "auditoria_" + "heurisma",
            "Gemini " + "Argo",
            "Gemini " + "Neon",
            "Gemini " + "Argon",
            "Gemini " + "Hydrogen",
            "Qwen" + "4",
            "Co-Authored-" + "By",
        )
        skip_ext = {".png", ".jpeg", ".jpg", ".pdf", ".zip", ".pyc"}
        hits: list[tuple[str, str]] = []
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts or path.suffix in skip_ext:
                continue
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for marker in forbidden:
                if marker.lower() in text:
                    hits.append((path.relative_to(REPO_ROOT).as_posix(), marker))
        self.assertEqual(hits, [])

    def test_openalex_record_with_arxiv_oa_url_uses_arxiv_rate_limit_bucket(self) -> None:
        papers.search(self.ctx(), "openalex", "x")
        rows = read_csv(self.appendix / "papers.csv")
        target_rec = None
        for r in rows:
            if r["doi"] == REAL:
                r.update(providers="openalex", is_oa="true", oa_url=self.url + "/files/sample.pdf?mirror=arxiv.org")
                target_rec = dict(r)
        self.assertIsNotNone(target_rec)
        papers._write_atomic(self.appendix / "papers.csv", contracts.PAPER_COLS, rows)
        ctx = self.ctx()
        saved = papers.fulltext(ctx, target_rec)  # type: ignore[arg-type]
        self.assertIsNotNone(saved)
        self.assertIn("arxiv", ctx._last_call)

    def test_signed_zero_matches_unsigned_zero_in_numeric_closure(self) -> None:
        raw_pos, norm_pos = numeric._closure_haystack("delta 0.0000\n", None)
        self.assertEqual(numeric._untraced_in("| −0.00 | -0.0 | +0.00 |", raw_pos, norm_pos, set()), [])
        raw_neg, norm_neg = numeric._closure_haystack("delta -0.0000\n", None)
        self.assertEqual(numeric._untraced_in("| 0.00 | 0 |", raw_neg, norm_neg, set()), [])

    def test_reviewer_quote_exemption_normalizes_windows_backslashes(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            gate = ws / "appendix" / "gates" / "reviewer.md"
            gate.write_text(
                "MODE: subagent\nREVIEWED-SHA256: 0\nREVIEWED-UTC: 2026-11-20T12:00:00Z\nANALYSIS-SHA256: 0\n"
                'QUOTE: .\\report.md:6: "a corrected draft sentence"\n'
                'QUOTE: appendix/output.txt:1: "Dataset integrity"\n\n1. [1] Over-calibrated — fix.\n',
                encoding="utf-8",
            )
            M._edit(
                ws,
                "report.md",
                "## 6. Claim-Evidence Matrix",
                "### Reviewer #2 Disposition Table\n\n| # | Critique | Action |\n| :- | :- | :- |\n| 1 | over-calibrated | Fixed |\n\n## 6. Claim-Evidence Matrix",
            )
            M.restamp_gates(ws)
            e, w = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws)
            self.assertEqual([m for m in e + w if "reviewer.md quotes" in m], [])

            # A mismatched appendix quote written with Windows backslashes still fails
            gate.write_text(
                gate.read_text(encoding="utf-8").replace(
                    'QUOTE: appendix/output.txt:1: "Dataset integrity"',
                    'QUOTE: .\\appendix\\output.txt:1: "wrong quote"',
                ),
                encoding="utf-8",
            )
            e2, w2 = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws)
            self.assertTrue([m for m in e2 + w2 if "reviewer.md quotes" in m])
        finally:
            tmp.cleanup()


class TestFinalReviewFixes(unittest.TestCase):
    """Independent code-review pass fixes: confinement before report.md skip, empty sources.csv + fingerprint guards, spaced CSV headers, and corrupt papers.csv."""

    def test_reviewer_parent_traversal_and_dotfile_quotes_are_not_exempted(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            gate = ws / "appendix" / "gates" / "reviewer.md"
            gate.write_text(
                "MODE: subagent\nREVIEWED-SHA256: 0\nREVIEWED-UTC: 2026-11-20T12:00:00Z\nANALYSIS-SHA256: 0\n"
                'QUOTE: ../report.md:1: "escaped"\n'
                'QUOTE: .report.md:1: "dotfile"\n'
                'QUOTE: appendix/output.txt:1: "Dataset integrity"\n\n1. [1] Over-calibrated — fix.\n',
                encoding="utf-8",
            )
            M._edit(
                ws,
                "report.md",
                "## 6. Claim-Evidence Matrix",
                "### Reviewer #2 Disposition Table\n\n| # | Critique | Action |\n| :- | :- | :- |\n| 1 | over-calibrated | Fixed |\n\n## 6. Claim-Evidence Matrix",
            )
            M.restamp_gates(ws)
            e, w = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws)
            msgs = "\n".join(e + w)
            self.assertIn("outside the report folder", msgs)
            self.assertIn(".report.md:1", msgs)
        finally:
            tmp.cleanup()

    def test_manifest_without_papers_csv_fails_with_empty_sources_and_leaves_hashes_untouched(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            (ws / "appendix" / "sources.csv").write_text(",".join(contracts.SOURCE_COLS) + "\n", encoding="utf-8")
            qa_before = gates.gate_hash(ws, "qa")
            html_before = render_report.compute_source_hash(ws / "report.md", ws / "charts.json", None, ws / "appendix")

            manifest = ws / "appendix" / contracts.WITHHELD_MANIFEST
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(f"file,sha256,reason\nghost.pdf,{'d' * 64},licensing\n", encoding="utf-8")

            self.assertEqual(gates.gate_hash(ws, "qa"), qa_before)
            self.assertEqual(
                render_report.compute_source_hash(ws / "report.md", ws / "charts.json", None, ws / "appendix"),
                html_before,
            )
            errors, _ = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=2, report_dir=ws)
            self.assertTrue([e for e in errors if e.startswith(f"appendix/{contracts.WITHHELD_MANIFEST}: ")], errors)
        finally:
            tmp.cleanup()

    def test_spaced_header_in_excluded_csv_is_parsed_cleanly(self) -> None:
        import hashlib

        tmp, ws = M.fresh_workspace()
        try:
            pdf_bytes = b"%PDF-1.4 spaced header"
            digest = hashlib.sha256(pdf_bytes).hexdigest()
            name = "10.9999_spaced-12345678.pdf"
            (ws / "appendix" / "download_log.csv").write_text(
                f"file,url,retrieved_utc,bytes,sha256\npapers/{name},https://preprints.example.org/s,2026-11-20T12:00:00Z,{len(pdf_bytes)},{digest}\n",
                encoding="utf-8",
            )
            M._papers_workspace(ws, [M._paper("10.9999/spaced.1", "Synthetic spaced manifest test", fulltext_file=f"appendix/data/papers/{name}", fulltext_sha256=digest)])
            manifest = ws / "appendix" / contracts.WITHHELD_MANIFEST
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(f"file, sha256, reason\n{name}, {digest}, publisher licensing\n", encoding="utf-8")
            self.assertEqual(contracts.read_withheld(ws / "appendix"), {f"data/papers/{name}": digest})
            M.restamp_gates(ws)
            errors, _ = validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws)
            self.assertEqual([e for e in errors if "EXCLUDED.csv" in e or name in e], [])
        finally:
            tmp.cleanup()

    def test_connector_fulltext_keys_handles_uppercase_sha_and_corrupt_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            app = ws / "appendix"
            app.mkdir(parents=True)
            p_csv = app / "papers.csv"
            p_csv.write_text("doi,fulltext_sha256\n10.9999/up," + ("AB" * 32) + "\n", encoding="utf-8")
            self.assertEqual(provenance._connector_fulltext_keys(ws, {"ab" * 6}), {"10.9999/up"})
            p_csv.write_bytes(b"\xff\xfe\x00\x00corrupt\x00csv")
            self.assertEqual(provenance._connector_fulltext_keys(ws, {"ab" * 6}), set())


if __name__ == "__main__":
    unittest.main()
