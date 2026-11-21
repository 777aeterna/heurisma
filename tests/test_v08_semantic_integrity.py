"""v0.8.0 Phase 2 tests: numeric closure (M25), tier laundering & agent-fetched proof (M20-M22), prereg & HARKing (M24)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402


def has(msgs: list[str], pattern: str) -> bool:
    return any(re.search(pattern, m, re.IGNORECASE) for m in msgs)


def msgs_after(fn, level: int = 2) -> list[str]:
    tmp, ws = M.fresh_workspace()
    try:
        fn(ws)
        M.restamp_gates(ws)
        M.rerender(ws)
        return M.detect(ws, level=level)
    finally:
        tmp.cleanup()


class TestNumericClosure(unittest.TestCase):
    def test_untraced_stat_in_section4_table_warns_l2_and_errors_l3(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            M.m25_untraced_stat_in_section4_table(ws)
            M.restamp_gates(ws)
            text = (ws / "report.md").read_text(encoding="utf-8")
            e2, w2 = validate_report.validate_report_full(text, level=2, report_dir=ws)
            self.assertTrue(has(w2, r"not found in appendix/output\.txt or appendix/numbers\.json"), (e2, w2))
            self.assertTrue(any(validate_report.classify_message(m)[0] == "P1-UNTRACED-NUM" for m in w2), w2)
            e3, _ = validate_report.validate_report_full(text, level=3, report_dir=ws)
            self.assertTrue(has(e3, r"not found in appendix/output\.txt or appendix/numbers\.json"), e3)
        finally:
            tmp.cleanup()

    def test_legitimate_non_computed_tokens_do_not_trigger_untraced_num(self) -> None:
        def add_context_table(ws: Path) -> None:
            table = (
                "\n| Parameter | Rating | Reference | Year | Tier |\n"
                "| :- | :- | :- | -: | :- |\n"
                "| Grid criterion | N-1 / N-2 at 500 kV (132/220 kV, 50 Hz) | Section 4.1 [@C2] | 2025 | Tier 1 |\n"
                "| Snapshot date | 2026-11-20 | § 4.2 | 2026 | Tier 2 |\n"
            )
            M._edit(ws, "report.md", "## 5. Counter-Evidence", table + "\n## 5. Counter-Evidence")

        msgs = msgs_after(add_context_table, level=2)
        self.assertFalse(has(msgs, r"untraced|not found in appendix/output\.txt"), msgs)


class TestSelectionIntegrity(unittest.TestCase):
    def test_intake_user_curated_cannot_be_relabelled_agent_fetched(self) -> None:
        def tamper(ws: Path) -> None:
            (ws / "appendix" / "intake.md").write_text(
                "# Intake report\n\n## Channel: data (`datos/`)\n\n"
                "- folder: `datos/` · channel: data · selection: user-curated · retrieved_utc: unknown\n\n"
                "### Files\n\n"
                "- accepted: hybrid_rct_sites.csv -> [@C1] (sha256 9a7419cd6056)\n",
                encoding="utf-8",
            )

            def fn(rows, cols):
                cols = cols + [c for c in ("selection", "retrieved_utc") if c not in cols]
                for r in rows:
                    r["selection"] = "agent-fetched"
                    r["retrieved_utc"] = "2026-11-20T12:00:00Z"
                return rows, cols

            M._rewrite_csv(ws, "appendix/sources.csv", fn)

        msgs = msgs_after(tamper, level=2)
        self.assertTrue(has(msgs, r"ingested as user-curated.*intake\.md|cannot be relabelled agent-fetched"), msgs)

    def test_agent_fetched_data_without_download_log_is_flagged(self) -> None:
        def no_dl(ws: Path) -> None:
            (ws / "appendix" / "run.json").write_text(
                json.dumps({"run_started_utc": "2026-11-20T08:00:00Z"}), encoding="utf-8"
            )

            def fn(rows, cols):
                cols = cols + [c for c in ("selection", "retrieved_utc") if c not in cols]
                for r in rows:
                    if (r.get("claim_id") or "").strip() == "C1":
                        r["selection"] = "agent-fetched"
                        r["retrieved_utc"] = "2026-11-20T09:00:00Z"
                        r["url"] = "https://example.org/data/sites.csv"
                    else:
                        r["selection"] = "third-party"
                        r["retrieved_utc"] = "2026-11-20T09:00:00Z"
                return rows, cols

            M._rewrite_csv(ws, "appendix/sources.csv", fn)

        msgs = msgs_after(no_dl, level=2)
        self.assertTrue(has(msgs, r"download_log\.csv"), msgs)


class TestPreregistrationIntegrity(unittest.TestCase):
    def test_missing_preregistration_is_error_at_level3(self) -> None:
        tmp, ws = M.fresh_workspace()
        try:
            text = (ws / "report.md").read_text(encoding="utf-8")
            e3, _ = validate_report.validate_report_full(text, level=3, report_dir=ws)
            self.assertTrue(has(e3, r"preregistration\.json"), e3)
        finally:
            tmp.cleanup()

    def test_post_hoc_preregistration_is_flagged(self) -> None:
        def post_hoc(ws: Path) -> None:
            text = (ws / "report.md").read_text(encoding="utf-8")
            h0 = re.search(r"H₀[^:]*:\**\s*(.+)", text).group(1).strip()
            h1 = re.search(r"H₁[^:]*:\**\s*(.+)", text).group(1).strip()
            body = {
                "sealed_utc": "2026-11-20T12:00:00Z",
                "hypotheses": {"H0": h0, "H1": h1},
                "plan": "Exact tests.",
                "known_artifacts": {"output.txt": "abc123def456"},
                "post_hoc": True,
            }
            body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            (ws / "appendix" / "preregistration.json").write_text(json.dumps(body), encoding="utf-8")

        msgs = msgs_after(post_hoc, level=2)
        self.assertTrue(has(msgs, r"post_hoc"), msgs)


if __name__ == "__main__":
    unittest.main()
