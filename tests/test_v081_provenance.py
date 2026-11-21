"""v0.8.1 Phase 1 tests: Tier 2 laundering (M26), literature proof (M28), post-prereg files (M29), JSON codes."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402

ATTEMPT_COLS = ["target_series", "source_tried", "query_or_endpoint", "outcome", "failure_reason", "fallback_used", "attempted_utc"]


def has(msgs: list[str], pattern: str) -> bool:
    return any(re.search(pattern, m, re.IGNORECASE) for m in msgs)


def full(ws: Path, level: int = 2) -> tuple[list[str], list[str]]:
    M.restamp_gates(ws)
    return validate_report.validate_report_full((ws / "report.md").read_text(encoding="utf-8"), level=level, report_dir=ws)


def add_attempts(ws: Path, rows: list[dict[str, str]], drop_utc: bool = False) -> None:
    p = ws / "appendix" / "data_attempts.csv"
    with p.open(encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        cols = list(rd.fieldnames or [])
        old = list(rd)
    cols = [c for c in cols if not (drop_utc and c == "attempted_utc")]
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(old + rows)


def used_row(target: str, endpoint: str) -> dict[str, str]:
    return {
        "target_series": target,
        "source_tried": "web",
        "query_or_endpoint": endpoint,
        "outcome": "used",
        "failure_reason": "",
        "fallback_used": "",
        "attempted_utc": "2026-11-20T12:01:00Z",
    }


class TestJsonCodes(unittest.TestCase):
    def test_agent_fetched_missing_proof_is_p2_selection_not_gen(self) -> None:
        for kind in ("data", "literature"):
            msg = (
                f"Source 'C1' is marked agent-fetched (kind={kind}) with no matching record in "
                f"appendix/download_log.csv or appendix/data_attempts.csv."
            )
            self.assertEqual(validate_report.classify_message(msg), ("P2-SELECTION", "appendix/sources.csv"))


class TestLocalTierCap(unittest.TestCase):
    def test_local_user_curated_tier2_is_error(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m26_local_user_curated_laundered_to_tier2(ws)
            e, _ = full(ws)
            self.assertTrue(has(e, r"cannot be Tier 2"), e)
        finally:
            tmp.cleanup()

    def test_local_user_curated_tier3_has_no_cap_error(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M._add_selection_columns(ws)
            e, w = full(ws)
            self.assertFalse(has(e + w, r"cannot be Tier"), (e, w))
        finally:
            tmp.cleanup()

    def test_remote_user_curated_tier2_with_origin_is_not_capped(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M._add_selection_columns(ws, c1_tier="Tier 2")

            def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
                for r in rows:
                    if r["claim_id"] == "C1":
                        r["url"] = "https://example.org/open-data/sites.csv"
                return rows, cols

            M._rewrite_csv(ws, "appendix/sources.csv", fn)
            e, w = full(ws)
            self.assertFalse(has(e + w, r"cannot be Tier"), (e, w))
        finally:
            tmp.cleanup()


class TestLiteratureProof(unittest.TestCase):
    def test_unproven_literature_warns_l2_and_errors_l3(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m28_agent_fetched_literature_without_proof(ws)
            e2, w2 = full(ws, 2)
            self.assertTrue(has(w2, r"kind=literature"), (e2, w2))
            self.assertFalse(has(e2, r"kind=literature"), e2)
            e3, _ = full(ws, 3)
            self.assertTrue(has(e3, r"kind=literature"), e3)
        finally:
            tmp.cleanup()

    def test_used_attempt_after_run_start_proves_literature(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m28_agent_fetched_literature_without_proof(ws)
            add_attempts(
                ws,
                [
                    used_row("Bloom 2024 full text", "GET https://doi.org/10.1038/s41586-024-07500-2"),
                    used_row("C3 NBER abstract", "GET https://www.nber.org/papers/w31880"),
                ],
            )
            e, w = full(ws)
            self.assertFalse(has(e + w, r"kind=literature"), (e, w))
        finally:
            tmp.cleanup()

    def test_attempt_matched_by_claim_id_token(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m28_agent_fetched_literature_without_proof(ws)
            add_attempts(ws, [used_row("C2 Bloom full text", "europepmc fulltext"), used_row("C3 NBER", "nber page")])
            e, w = full(ws)
            self.assertFalse(has(e + w, r"kind=literature"), (e, w))
        finally:
            tmp.cleanup()

    def test_attempt_before_run_start_does_not_count(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m28_agent_fetched_literature_without_proof(ws)
            old = used_row("C2 Bloom", "GET https://doi.org/10.1038/s41586-024-07500-2")
            old["attempted_utc"] = "2026-11-19T12:00:00Z"
            add_attempts(ws, [old, used_row("C3 NBER", "GET https://www.nber.org/papers/w31880")])
            _, w = full(ws)
            self.assertTrue(has(w, r"Source 'C2'.*kind=literature"), w)
            self.assertFalse(has(w, r"Source 'C3'.*kind=literature"), w)
        finally:
            tmp.cleanup()

    def test_legacy_attempts_without_timestamp_never_crash_and_do_not_prove(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m28_agent_fetched_literature_without_proof(ws)
            add_attempts(ws, [used_row("C2", "GET https://doi.org/10.1038/s41586-024-07500-2")], drop_utc=True)
            _, w = full(ws)
            self.assertTrue(has(w, r"kind=literature"), w)
        finally:
            tmp.cleanup()

    def test_missing_attempts_file_never_crashes(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m28_agent_fetched_literature_without_proof(ws)
            (ws / "appendix" / "data_attempts.csv").unlink()
            _, w = full(ws)
            self.assertTrue(has(w, r"kind=literature"), w)
        finally:
            tmp.cleanup()

    def test_tier1_without_downloaded_document_or_label_warns(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m28_agent_fetched_literature_without_proof(ws)
            add_attempts(ws, [used_row("C2", "GET https://doi.org/10.1038/s41586-024-07500-2"), used_row("C3", "C3 page")])
            _, w = full(ws)
            self.assertTrue(has(w, r"Source 'C2'.*Tier 1.*no downloaded primary document"), w)
        finally:
            tmp.cleanup()

    def test_web_summary_label_or_download_log_silences_tier1_warning(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m28_agent_fetched_literature_without_proof(ws)
            add_attempts(ws, [used_row("C2", "C2 page"), used_row("C3", "C3 page")])

            def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
                for r in rows:
                    if r["claim_id"] == "C2":
                        r["source_title"] += " (web summary)"
                return rows, cols

            M._rewrite_csv(ws, "appendix/sources.csv", fn)
            (ws / "appendix" / "download_log.csv").write_text(
                "url,file,sha256\nhttps://www.nber.org/papers/w31880,w31880.pdf,\n", encoding="utf-8"
            )
            _, w = full(ws)
            self.assertFalse(has(w, r"no downloaded primary document"), w)
        finally:
            tmp.cleanup()


class TestFilesAfterPrereg(unittest.TestCase):
    def test_new_data_file_warns_with_code_and_name(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m29_data_file_added_after_prereg(ws)
            _, w = full(ws)
            hit = [m for m in w if re.search(r"after preregistration", m, re.IGNORECASE)]
            self.assertTrue(hit and "parameters.csv" in hit[0], w)
            self.assertEqual(validate_report.classify_message(hit[0])[0], "P2-PREREG")
        finally:
            tmp.cleanup()

    def test_file_in_download_log_is_not_flagged(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m29_data_file_added_after_prereg(ws)
            (ws / "appendix" / "download_log.csv").write_text(
                "url,file,sha256\nhttps://example.org/parameters.csv,appendix/data/parameters.csv,\n", encoding="utf-8"
            )
            _, w = full(ws)
            self.assertFalse(has(w, r"after preregistration"), w)
        finally:
            tmp.cleanup()

    def test_file_listed_in_intake_is_not_flagged(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m29_data_file_added_after_prereg(ws)
            (ws / "appendix" / "intake.md").write_text(
                "# Intake report\n\n## Channel: data (`datos/`)\n\n- accepted: parameters.csv -> [@C5]\n", encoding="utf-8"
            )
            _, w = full(ws)
            self.assertFalse(has(w, r"after preregistration"), w)
        finally:
            tmp.cleanup()

    def test_without_preregistration_nothing_is_flagged(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m29_data_file_added_after_prereg(ws)
            (ws / "appendix" / "preregistration.json").unlink()
            _, w = full(ws)
            self.assertFalse(has(w, r"after preregistration"), w)
        finally:
            tmp.cleanup()

    def test_known_artifact_is_not_flagged(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m29_data_file_added_after_prereg(ws)
            p = ws / "appendix" / "preregistration.json"
            rec = json.loads(p.read_text(encoding="utf-8"))
            rec["known_artifacts"]["data/parameters.csv"] = "000000000000"
            import local_data

            rec["sha256"] = local_data._prereg_digest(rec)
            p.write_text(json.dumps(rec), encoding="utf-8")
            _, w = full(ws)
            self.assertFalse(has(w, r"after preregistration"), w)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
