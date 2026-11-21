"""v0.7.0 Phase 6: pre-intake (selection / retrieved_utc), intake command, and lightweight preregistration."""

import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import local_data  # noqa: E402

SCRIPTS = M.SCRIPTS


def msgs_after(fn, render=True, level=2):
    tmp, ws = M.fresh_workspace()
    try:
        fn(ws)
        M.restamp_gates(ws)
        if render:
            M.rerender(ws)
        return M.detect(ws, level=level)
    finally:
        tmp.cleanup()


def has(msgs, pattern):
    return any(re.search(pattern, m) for m in msgs)


def set_selection(values: dict[str, tuple[str, str]]):
    """claim_id -> (selection, retrieved_utc) for the golden sources.csv."""

    def fn(ws: Path) -> None:
        def edit(rows, cols):
            cols = cols + [c for c in ("selection", "retrieved_utc") if c not in cols]
            for r in rows:
                sel, ret = values.get(r["claim_id"], ("agent-fetched", "2026-11-20T10:00:00Z"))
                r["selection"], r["retrieved_utc"] = sel, ret
            return rows, cols

        M._rewrite_csv(ws, "appendix/sources.csv", edit)

    return fn


class TestSelectionRules(unittest.TestCase):
    def test_golden_with_explicit_selection_is_clean(self) -> None:
        msgs = msgs_after(set_selection({"C1": ("user-curated", "unknown"), "C4": ("agent-fetched", "2026-11-20T10:00:00Z")}))
        self.assertFalse([m for m in msgs if re.search(r"selection|user-curated|retrieved_utc", m)], msgs)

    def test_user_curated_without_retrieval_date_is_an_error(self) -> None:
        msgs = M.run_mutation("M14")
        self.assertTrue(has(msgs, r"user-curated.*retrieved_utc"), msgs)

    def test_unknown_retrieval_date_caps_a_user_file_at_tier3(self) -> None:
        msgs = msgs_after(set_selection({"C2": ("user-curated", "unknown")}))  # C2 is Tier 1
        self.assertTrue(has(msgs, r"C2.*user-curated.*unknown.*Tier 1"), msgs)

    def test_invalid_selection_value(self) -> None:
        msgs = msgs_after(set_selection({"C2": ("mine", "2026-11-20T10:00:00Z")}))
        self.assertTrue(has(msgs, r"selection 'mine'"), msgs)

    def test_as_of_earlier_than_a_retrieval_is_an_error(self) -> None:
        msgs = msgs_after(set_selection({"C2": ("agent-fetched", "2026-12-01T10:00:00Z")}))
        self.assertTrue(has(msgs, r"As-Of Date 2026-11-20 is earlier than C2's retrieved_utc"), msgs)

    def test_old_snapshot_warns(self) -> None:
        msgs = msgs_after(set_selection({"C2": ("agent-fetched", "2020-01-01T00:00:00Z")}))
        self.assertTrue(has(msgs, r"C2.*retrieved .* days before the As-Of Date"), msgs)

    def test_only_user_curated_sources_needs_counter_search(self) -> None:
        everything = {c: ("user-curated", "2026-11-19T10:00:00Z") for c in ("C1", "C2", "C3")}
        everything["C4"] = ("agent-fetched", "2026-11-20T10:00:00Z")  # own computation does not count as a search
        msgs2 = msgs_after(set_selection(everything))
        self.assertTrue(has(msgs2, r"no agent-fetched source outside the user's corpus"), msgs2)

    def test_claim_resting_only_on_user_curated_needs_selection_bias_label(self) -> None:
        def strong_on_curated(ws: Path) -> None:
            set_selection({"C2": ("user-curated", "2026-11-19T10:00:00Z")})(ws)
            row = "| 2-day hybrid work lowers quit rates by about one-third | Labor Economics | Trip.com randomized trial [@C2], Tier 1, 2024-06 | `[Moderate]` |"
            M._edit(ws, "report.md", row, row.replace("`[Moderate]`", "`[Strong]`"))

        msgs = msgs_after(strong_on_curated)
        self.assertTrue(has(msgs, r"rests only on user-curated source\(s\) C2.*\[Moderate\]"), msgs)

    def test_moderate_on_curated_needs_the_label(self) -> None:
        msgs = msgs_after(set_selection({"C2": ("user-curated", "2026-11-19T10:00:00Z")}))
        self.assertTrue(has(msgs, r"Selection bias: user-curated corpus"), msgs)

    def test_label_in_the_row_satisfies_the_rule(self) -> None:
        def labelled(ws: Path) -> None:
            set_selection({"C2": ("user-curated", "2026-11-19T10:00:00Z")})(ws)
            M._edit(ws, "report.md", "Trip.com randomized trial [@C2], Tier 1, 2024-06",
                    "Trip.com randomized trial [@C2], Tier 1, 2024-06; Selection bias: user-curated corpus")

        msgs = msgs_after(labelled)
        self.assertFalse(has(msgs, r"Selection bias"), msgs)

    def test_unregistered_inbox_file_warns(self) -> None:
        def inbox(ws: Path) -> None:
            (ws / "inbox" / "sources").mkdir(parents=True)
            (ws / "inbox" / "sources" / "paper.md").write_text("a paper\n", encoding="utf-8")

        msgs = msgs_after(inbox)
        self.assertTrue(has(msgs, r"inbox/sources/paper\.md is not registered"), msgs)


class TestLocalDataColumns(unittest.TestCase):
    def test_register_and_import_write_selection_and_retrieved_utc(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            src = root / "datos" / "x.csv"
            src.parent.mkdir()
            src.write_text("a;b\n1;2\n", encoding="utf-8")
            local_data.import_local(src, root / "appendix" / "data", root / "appendix" / "sources.csv", "Tier 3", "X")
            with (root / "appendix" / "sources.csv").open(encoding="utf-8", newline="") as fh:
                row = list(csv.DictReader(fh))[0]
            self.assertEqual(row["selection"], "user-curated")
            self.assertEqual(row["retrieved_utc"], "unknown")
            local_data.import_local(src, root / "appendix" / "data2", root / "appendix" / "s2.csv", "Tier 1", "X",
                                    selection="agent-fetched", retrieved_utc="2026-11-20T10:00:00Z")
            with (root / "appendix" / "s2.csv").open(encoding="utf-8", newline="") as fh:
                row2 = list(csv.DictReader(fh))[0]
            self.assertEqual((row2["selection"], row2["retrieved_utc"]), ("agent-fetched", "2026-11-20T10:00:00Z"))

    def test_invalid_selection_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "x.csv"
            f.write_text("a\n1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                local_data.register_local(f, Path(t) / "s.csv", "Tier 3", "X", selection="mine")


class TestIntake(unittest.TestCase):
    def _folder(self, root: Path) -> None:
        d = root / "datos"
        d.mkdir()
        (d / "precios.csv").write_text("anio;precio_m2;alquiler\n2024;2150,0;420000\n2025;2080,2;690000\n", encoding="utf-8")
        (d / "mixto.csv").write_text("id;v\n1;1,5\n2;2.5\n", encoding="utf-8")
        (d / "notas.txt").write_text("free text\n", encoding="utf-8")
        (root / "wishlist.txt").write_text("rents: alquiler, rent\nvacancy: vacancia, vacancy\n", encoding="utf-8")

    def test_intake_imports_accepted_files_and_writes_a_report_with_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self._folder(root)
            res = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "local_data.py"), "intake", str(root / "datos"),
                 "--appendix", str(root / "appendix"), "--channel", "data", "--selection", "user-curated",
                 "--wishlist", str(root / "wishlist.txt")],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            report = (root / "appendix" / "intake.md").read_text(encoding="utf-8")
            self.assertRegex(report, r"accepted.*precios\.csv")
            self.assertRegex(report, r"rejected.*mixto\.csv.*mixes decimal comma")
            self.assertIn("alquiler: integer", report)
            self.assertIn("precio_m2: decimal-comma", report)
            self.assertRegex(report, r"(?s)Gaps.*vacancy")
            self.assertNotRegex(report, r"(?s)Gaps.*\brents\b")
            self.assertTrue((root / "appendix" / "data" / "precios.csv").is_file())
            self.assertFalse((root / "appendix" / "data" / "mixto.csv").exists())
            with (root / "appendix" / "sources.csv").open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual({r["selection"] for r in rows}, {"user-curated"})
            self.assertTrue(all(r["kind"] == "data" for r in rows))

    def test_sources_channel_copies_documents_as_literature(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            inbox = root / "inbox" / "sources"
            inbox.mkdir(parents=True)
            (inbox / "nota.md").write_text("# A note\n", encoding="utf-8")
            local_data.intake(inbox, root / "appendix", channel="sources", selection="user-curated")
            self.assertTrue((root / "appendix" / "corpus" / "nota.md").is_file())
            with (root / "appendix" / "sources.csv").open(encoding="utf-8", newline="") as fh:
                row = list(csv.DictReader(fh))[0]
            self.assertEqual((row["kind"], row["selection"]), ("literature", "user-curated"))


class TestPreregistration(unittest.TestCase):
    def test_prereg_seals_hypotheses_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            app = Path(t) / "appendix"
            rec = local_data.preregister(app, {"H0": "No change in rents.", "H1": "Rents fell."}, "Compare medians 2023-2025.")
            data = json.loads((app / "preregistration.json").read_text(encoding="utf-8"))
            self.assertEqual(data["hypotheses"]["H1"], "Rents fell.")
            self.assertRegex(data["sealed_utc"], r"Z$")
            self.assertEqual(rec["sha256"], data["sha256"])
            with self.assertRaises(ValueError):  # sealing twice would let the plan move after the data
                local_data.preregister(app, {"H0": "x", "H1": "y"}, "z")

    def _with_prereg(self, ws: Path, h1: str) -> None:
        text = (ws / "report.md").read_text(encoding="utf-8")
        h0 = re.search(r"H₀[^:]*:\**\s*(.+)", text).group(1).strip()
        local_data.preregister(ws / "appendix", {"H0": h0, "H1": h1}, "Exact permutation tests by seniority.")

    def test_matching_hypotheses_are_clean_and_tampering_is_caught(self) -> None:
        def ok(ws: Path) -> None:
            text = (ws / "report.md").read_text(encoding="utf-8")
            self._with_prereg(ws, re.search(r"H₁[^:]*:\**\s*(.+)", text).group(1).strip())

        self.assertFalse(has(msgs_after(ok), r"preregistration"), msgs_after(ok))

        def tampered(ws: Path) -> None:
            ok(ws)
            p = ws / "appendix" / "preregistration.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            data["plan"] = "Changed after seeing the data."
            p.write_text(json.dumps(data), encoding="utf-8")

        self.assertTrue(has(msgs_after(tampered), r"preregistration\.json was edited after sealing"))

    def test_hypothesis_changed_after_sealing_warns(self) -> None:
        msgs = msgs_after(lambda ws: self._with_prereg(ws, "Something else entirely."))
        self.assertTrue(has(msgs, r"H1 in Section 2 differs from appendix/preregistration\.json"), msgs)


if __name__ == "__main__":
    unittest.main()
