"""TDD tests for the v0.11.0 field-audit remediation (B1–B9, P1–P2, A1–A2)."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
TESTS_DIR = Path(__file__).resolve().parent
for _p in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conjecture  # noqa: E402
import formal_math  # noqa: E402
import papers  # noqa: E402
from providers import base  # noqa: E402
import validate_report  # noqa: E402


class TestConjectureAuditFixes(unittest.TestCase):
    def _kepler_rows(self) -> list[dict[str, float]]:
        gm = 1.32712440018e20
        semi = [5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.786e11, 1.4335e12, 2.8725e12, 4.4951e12]
        masses = [3.30e23, 4.87e24, 5.97e24, 6.42e23, 1.90e27, 5.68e26, 8.68e25, 1.02e26]
        return [
            {
                "a_m": a,
                "T_s": 2.0 * math.pi * (a ** 1.5) / (gm ** 0.5),
                "m_kg": m,
                "GM": gm,
            }
            for a, m in zip(semi, masses)
        ]

    def test_b1_units_evaluates_both_pi_and_data_driven_families_and_flags_constant_predictor(self) -> None:
        rows = self._kepler_rows()
        res = conjecture.discover_laws(
            rows,
            target="T_s",
            predictors=["a_m", "m_kg", "GM"],
            units={"T_s": "s", "a_m": "m", "m_kg": "kg", "GM": "m^3/s^2"},
            sort_by="a_m",
        )
        self.assertGreater(res["n_candidates_evaluated"], 10)
        families = {c["family"] for c in res["candidates"]}
        self.assertIn("buckingham_pi_monomial", families)
        self.assertTrue(families & {"power_law", "power_law_rational"})
        for c in res["candidates"]:
            self.assertIn("dimensionally_consistent", c)
            self.assertIsInstance(c["dimensionally_consistent"], bool)
        pi_cand = next(c for c in res["candidates"] if c["family"] == "buckingham_pi_monomial")
        self.assertTrue(pi_cand["dimensionally_consistent"])
        self.assertTrue(any("GM" in w and "zero variance" in w.lower() for w in res["warnings"]))
        self.assertTrue(any("train_count=6" in w or "fewer than 10" in w.lower() for w in res["warnings"]))

    def test_b7_b8_cli_supports_source_ids_falsifier_at_and_full_64char_data_sha256(self) -> None:
        rows = self._kepler_rows()
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            csv_path = tdir / "planets.csv"
            lines = ["a_m,T_s,m_kg,GM"] + [f"{r['a_m']},{r['T_s']},{r['m_kg']},{r['GM']}" for r in rows]
            csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            out_json = tdir / "appendix" / "conjectures.json"
            rc = conjecture.main([
                "discover",
                str(csv_path),
                "--target", "T_s",
                "--predictors", "a_m,m_kg,GM",
                "--units", "T_s=s,a_m=m,m_kg=kg,GM=m^3/s^2",
                "--source-ids", "C5,C6",
                "--falsifier-at", "a_m=5.906e12,m_kg=1.309e22,GM=1.3271244e20",
                "--out", str(out_json),
            ])
            self.assertEqual(rc, 0)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["data_sha256"]), 64)
            self.assertEqual(payload["source_ids"], ["C5", "C6"])
            self.assertIn("max_abs_error", payload["falsifier_prediction"])
            self.assertIn("5.906e+12", payload["falsifier_prediction"])
            self.assertAlmostEqual(payload["falsifier_point"]["a_m"], 5.906e12)

    def test_b2_m59_catches_discovery_source_citation_and_non_lexical_discovered_law(self) -> None:
        from mutations import _conjecture_payload, _edit, fresh_workspace

        tmp, ws = fresh_workspace()
        try:
            payload = _conjecture_payload(train_count=12, holdout_count=4)
            payload["source_ids"] = ["C5"]
            body = {k: v for k, v in payload.items() if k != "sha256"}
            payload["sha256"] = hashlib.sha256(
                json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            (ws / "appendix" / "conjectures.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
            src_p = ws / "appendix" / "sources.csv"
            src_p.write_text(
                src_p.read_text(encoding="utf-8")
                + "C5,JPL SSD Planetary Fact Sheet,https://ssd.jpl.nasa.gov/planets,Tier 1,2026-11-20,2026-11,data,,agent-fetched,2026-11-20T12:00:00Z\n",
                encoding="utf-8",
            )
            _edit(
                ws,
                "report.md",
                "| Lower mentoring hours explain the junior output gap",
                "| The discovered scaling law attrition_12m = 0.25 * mentoring_hrs_wk^(-1/2) holds across planets | Physics | Symbolic fit [@C4; @C5], Tier 1, 2026-11 | `[Strong]` | Out-of-domain test |\n"
                "| Lower mentoring hours explain the junior output gap",
            )
            errs, _ = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws
            )
            self.assertTrue(any("unproved symbolic conjecture as [Strong]" in e for e in errs), errs)
        finally:
            tmp.cleanup()


class TestValidatorGateAndReproFixes(unittest.TestCase):
    def test_b3_readme_analysis_command_extracts_from_numbered_list_with_trailing_prose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rdir = Path(tmp)
            (rdir / "appendix").mkdir()
            (rdir / "appendix" / "README.md").write_text(
                "# Appendix\n\n"
                "1. `python3 -B appendix/fetch_data.py` downloads the raw tables.\n"
                "2. `python3 -B appendix/analysis.py` parses them (`appendix/build_tables.py`) into `appendix/output.txt`.\n",
                encoding="utf-8",
            )
            cmd = validate_report._readme_analysis_command(rdir)
            self.assertEqual(cmd, "python3 -B appendix/analysis.py")

    def test_b4_reviewer_quote_on_sources_csv_exempted_after_disposition_closed(self) -> None:
        from mutations import fresh_workspace

        tmp, ws = fresh_workspace()
        try:
            rev = ws / "appendix" / "gates" / "reviewer.md"
            rev.write_text(
                "MODE: subagent\n"
                f"REVIEWED-SHA256: {validate_report.gate_hash(ws, 'reviewer')}\n"
                "REVIEWED-UTC: 2026-11-20T12:00:00Z\n"
                f"ANALYSIS-SHA256: {validate_report._analysis_anchor(ws)}\n"
                'QUOTE: appendix/sources.csv:2: "Tier 3"\n'
                'QUOTE: report.md:1: "Hybrid Work"\n\n'
                "1. [1] C1 tier in sources.csv — Needs updated note — Update C1 title\n\n"
                "1. Over-calibrated claims — 1 items\n"
                "2. Unattempted data shortcuts — none found\n"
                "3. Missing counter-evidence and controls — none found\n"
                "4. Interdisciplinary and forecasting flaws — none found\n"
                "5. Decisions inside the noise — none found\n"
                "6. Provenance contradictions — none found\n"
                "MOST DAMAGING: 1 — Source note.\n",
                encoding="utf-8",
            )
            s_path = ws / "appendix" / "sources.csv"
            lines = s_path.read_text(encoding="utf-8").splitlines()
            lines[1] = lines[1].replace("Tier 3", "Tier 2")
            s_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            rep = (ws / "report.md").read_text(encoding="utf-8").replace("Depth Level:** Level 2", "Depth Level:** Level 3")
            rep = rep.replace(
                "## 6. Claim-Evidence Matrix",
                "### Reviewer #2 Disposition Table\n| # | Critique | Action | Resolution |\n| :- | :- | :- | :- |\n| 1 | C1 tier | `Fixed` | Updated sources.csv |\n\n## 6. Claim-Evidence Matrix",
            )
            (ws / "report.md").write_text(rep, encoding="utf-8")
            errs, _ = validate_report.validate_report_full(rep, level=3, report_dir=ws)
            quote_errs = [e for e in errs if "reviewer.md quotes appendix/sources.csv:2" in e]
            self.assertEqual(quote_errs, [])
        finally:
            tmp.cleanup()

    def test_b6_source_verifier_fail_must_be_justified_in_section7_not_section3(self) -> None:
        from mutations import fresh_workspace

        tmp, ws = fresh_workspace()
        try:
            rep_p = ws / "report.md"
            text = rep_p.read_text(encoding="utf-8")
            sec7_idx = text.index("## 7. Limitations")
            before7 = text[:sec7_idx] + "\nSee appendix/gates/source_verifier.md for details.\n"
            after7 = text[sec7_idx:].replace("appendix/gates/source_verifier.md", "the verifier gate")
            rep_p.write_text(before7 + after7, encoding="utf-8")
            errs, _ = validate_report.validate_report_full(rep_p.read_text(encoding="utf-8"), level=3, report_dir=ws)
            self.assertTrue(any("SOURCE-VERIFIER: FAIL" in e and "Section 7" in e for e in errs), errs)
        finally:
            tmp.cleanup()

    def test_sources_csv_blank_row_is_reported(self) -> None:
        from mutations import fresh_workspace

        tmp, ws = fresh_workspace()
        try:
            s_path = ws / "appendix" / "sources.csv"
            lines = s_path.read_text(encoding="utf-8").splitlines()
            s_path.write_text("\n".join(lines[:2] + [""] + lines[2:]) + "\n", encoding="utf-8")
            errs, _ = validate_report.validate_report_full(
                (ws / "report.md").read_text(encoding="utf-8"), level=3, report_dir=ws
            )
            self.assertTrue(any("blank row" in e.lower() for e in errs), errs)
        finally:
            tmp.cleanup()


class TestFormalMathAuditFixes(unittest.TestCase):
    def test_b5_detects_single_tactic_ring_proof_and_unused_hypotheses(self) -> None:
        ch = (
            "namespace Challenge\n"
            "theorem kepler_scaling (k a l T2 : Int) (hk : k > 0) (ha : a > 0) (hl : l > 0) (hT : T2 = k * a ^ 3) :\n"
            "    k * (l * a) ^ 3 = l ^ 3 * T2 := by sorry\n"
            "end Challenge\n"
        )
        sol = (
            "import Challenge\n"
            "namespace Solution\n"
            "theorem kepler_scaling (k a l T2 : Int) (hk : k > 0) (ha : a > 0) (hl : l > 0) (hT : T2 = k * a ^ 3) :\n"
            "    k * (l * a) ^ 3 = l ^ 3 * T2 := by\n"
            "  subst hT; ring\n"
            "end Solution\n"
        )
        hz = formal_math.scan_lean_hazards(ch, sol)
        self.assertTrue(hz["clean"])
        triv = hz.get("trivial_proof_warnings", [])
        unused = hz.get("unused_hypothesis_warnings", [])
        self.assertTrue(any("single_tactic" in t and "ring" in t for t in triv), triv)
        self.assertTrue(any("unused_hypothesis:kepler_scaling:hk" in t for t in unused), unused)

    def test_b8_register_formal_source_writes_full_64char_sha256_in_sources_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "appendix"
            formal_math.init_project(app, "demo_slug")
            formal_math.check_project(app, "demo_slug", env={"PATH": ""})
            row = formal_math.register_formal_source(
                app, "demo_slug", sources_csv=app / "sources.csv", claim_id="FM1", tier="Tier 3"
            )
            self.assertEqual(len(row["sha256"]), 64)


class TestPapersArxivDoiFixes(unittest.TestCase):
    def test_p1_p2_arxiv_10_48550_doi_skips_crossref_404_and_fetches_arxiv_pdf(self) -> None:
        from test_papers_core import Base

        self.assertEqual(base.arxiv_id_from_doi("10.48550/arXiv.2312.09766"), "2312.09766")
        self.assertEqual(base.arxiv_id_from_doi("arxiv:2401.08922v2"), "2401.08922")

        class _Harness(Base):
            def run_check(self) -> None:
                ctx = self.ctx()
                rec = papers.lookup(ctx, "10.48550/arxiv.2401.08922")
                self.assertIsNotNone(rec)
                assert rec is not None
                self.assertEqual(rec["doi"], "10.48550/arxiv.2401.08922")
                attempts = (self.appendix / "data_attempts.csv").read_text(encoding="utf-8") if (self.appendix / "data_attempts.csv").is_file() else ""
                self.assertNotIn("crossref", attempts.lower())
                row = papers.cite(ctx, "10.48550/arxiv.2401.08922", tier="Tier 2", claim_id="C9", fulltext=True)
                self.assertNotIn("abstract only", row["source_title"].lower())
                self.assertEqual(len(row["sha256"]), 64)
                probs = papers.verify(ctx)
                self.assertEqual(probs, [])
                attempts_after = (self.appendix / "data_attempts.csv").read_text(encoding="utf-8")
                self.assertNotIn("crossref", attempts_after.lower())

        h = _Harness("run_check")
        h.setUp()
        try:
            h.run_check()
        finally:
            h.tearDown()


if __name__ == "__main__":
    unittest.main()
