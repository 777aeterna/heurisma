"""v0.10.2: full texts withheld from a redistributed copy (copyright) are declared in a manifest, not silently missing.

`appendix/data/papers/EXCLUDED.csv` (file, sha256, reason) lists each saved full text left out of the copy. A listed file
whose hash matches download_log.csv and papers.csv counts as present with that hash: in the gate and HTML fingerprints (so
gates reviewed on the full copy stay valid) and in the full-text check. Anything inconsistent is an error."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import render_report  # noqa: E402
import validate_report  # noqa: E402

import contracts  # noqa: E402
from checks import gates  # noqa: E402

DOI, TITLE = "10.9999/fake.withheld.1", "A synthetic article whose PDF is withheld from the copy"
PDF = b"%PDF-1.4 withheld fixture"
DIGEST = hashlib.sha256(PDF).hexdigest()
NAME = "10.9999_fake.withheld.1-1234abcd.pdf"


def full_copy(ws: Path) -> Path:
    target = ws / "appendix" / "data" / "papers" / NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(PDF)
    with (ws / "appendix" / "download_log.csv").open("a", encoding="utf-8") as fh:
        if (ws / "appendix" / "download_log.csv").stat().st_size == 0:
            fh.write("file,url,retrieved_utc,bytes,sha256\n")
        fh.write(f"papers/{NAME},https://preprints.example.org/pdf/w1,2026-11-20T12:00:00Z,{len(PDF)},{DIGEST}\n")
    M._papers_workspace(ws, [M._paper(DOI, TITLE, fulltext_file=f"appendix/data/papers/{NAME}", fulltext_sha256=DIGEST)])
    return target


def withhold(ws: Path, target: Path, sha: str = DIGEST) -> None:
    target.unlink()
    (ws / "appendix" / contracts.WITHHELD_MANIFEST).write_text(
        f"file,sha256,reason\n{NAME},{sha},publisher licensing: not redistributed in this copy\n", encoding="utf-8"
    )


def messages(ws: Path, level: int = 3) -> tuple[list[str], list[str]]:
    return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)


class TestManifest(unittest.TestCase):
    def test_the_manifest_is_read_into_appendix_paths_and_hashes(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            withhold(ws, full_copy(ws))
            self.assertEqual(contracts.read_withheld(ws / "appendix"), {f"data/papers/{NAME}": DIGEST})
            self.assertEqual(contracts.read_withheld(ws / "nowhere"), {})
        finally:
            tmp.cleanup()


class TestFingerprintsSurviveWithholding(unittest.TestCase):
    def test_gate_and_html_hashes_equal_those_of_the_full_copy(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            target = full_copy(ws)
            before = {g: gates.gate_hash(ws, g) for g in ("qa", "reviewer", "source_verifier")}
            src_before = render_report.compute_source_hash(ws / "report.md", ws / "charts.json", None, ws / "appendix")
            withhold(ws, target)
            self.assertEqual({g: gates.gate_hash(ws, g) for g in before}, before)
            self.assertEqual(render_report.compute_source_hash(ws / "report.md", ws / "charts.json", None, ws / "appendix"), src_before)
        finally:
            tmp.cleanup()

    def test_a_wrong_hash_in_the_manifest_does_not_reproduce_the_fingerprint(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            target = full_copy(ws)
            before = gates.gate_hash(ws, "qa")
            withhold(ws, target, sha="ab" * 32)
            self.assertNotEqual(gates.gate_hash(ws, "qa"), before)
        finally:
            tmp.cleanup()


class TestValidatorAcceptsOnlyConsistentWithholding(unittest.TestCase):
    def test_a_consistently_withheld_full_text_is_not_an_error(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            withhold(ws, full_copy(ws))
            M.restamp_gates(ws)
            e, w = messages(ws)
            noise = [m for m in e + w if "EXCLUDED.csv" in m or NAME in m or "Orphan" in m]
            self.assertEqual(noise, [], noise)
        finally:
            tmp.cleanup()

    def test_a_manifest_hash_that_does_not_match_the_logs_is_an_error(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            withhold(ws, full_copy(ws), sha="ab" * 32)
            M.restamp_gates(ws)
            e, _ = messages(ws)
            self.assertTrue([m for m in e if "EXCLUDED.csv" in m], e)
        finally:
            tmp.cleanup()

    def test_a_file_never_downloaded_cannot_be_declared_withheld(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M._papers_workspace(ws)
            (ws / "appendix" / contracts.WITHHELD_MANIFEST).write_text(f"file,sha256,reason\nnever-fetched.pdf,{DIGEST},licensing\n", encoding="utf-8")
            M.restamp_gates(ws)
            e, _ = messages(ws)
            self.assertTrue([m for m in e if "EXCLUDED.csv" in m and "never-fetched.pdf" in m], e)
        finally:
            tmp.cleanup()


class TestTheReaderIsTold(unittest.TestCase):
    def test_the_html_lists_the_withheld_files(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            withhold(ws, full_copy(ws))
            out = render_report._render_appendices(ws / "appendix", render_report.I18N["en"])
            self.assertIn(NAME, out)
            self.assertIn("withheld", out.lower())
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
