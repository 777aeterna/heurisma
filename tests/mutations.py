"""Known violations ("mutations") applied to a copy of the golden example, and the detector that must catch them.

Each mutation is a function ``fn(ws: Path) -> None`` that edits the workspace; ``detect(ws)`` re-renders and returns
every validator error and warning. A mutation is *caught* when the validator reports anything for it. The golden
example is clean (no messages), so any message is caused by the mutation.

``PENDING`` maps a mutation to the v0.7.0 phase that will make the validator catch it; ``tests/test_mutations.py``
marks those as expected failures and ``tests/mutation_report.py`` publishes the detection rate.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "heurisma" / "scripts"
GOLDEN = ROOT / "examples" / "showcase-hybrid-work"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import render_report  # noqa: E402
import validate_report  # noqa: E402

Mutation = Callable[[Path], None]


# ---------------------------------------------------------------------------------------------- workspace helpers
def fresh_workspace() -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory()
    ws = Path(tmp.name) / "run"
    shutil.copytree(GOLDEN, ws, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return tmp, ws


def rerender(ws: Path) -> None:
    charts = json.loads((ws / "charts.json").read_text(encoding="utf-8"))
    html = render_report.render_html(
        (ws / "report.md").read_text(encoding="utf-8"),
        charts=charts,
        appendix_dir=ws / "appendix",
        source_hash=render_report.compute_source_hash(ws / "report.md", ws / "charts.json", None, ws / "appendix"),
    )
    (ws / "report.html").write_text(html, encoding="utf-8")


def detect(ws: Path, level: int = 2) -> list[str]:
    """All validator errors and warnings for the workspace (markdown, HTML and HTML freshness)."""
    report = ws / "report.md"
    errors, warnings = validate_report.validate_report_full(
        report.read_text(encoding="utf-8"), level=level, report_dir=ws
    )
    html = ws / "report.html"
    if html.is_file():
        h_err, h_warn = validate_report.validate_html_full(html)
        errors += h_err
        warnings += h_warn + validate_report.check_html_freshness(html, report)
    return errors + warnings


def _edit(ws: Path, rel: str, old: str, new: str) -> None:
    p = ws / rel
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(f"mutation anchor not found in {rel}: {old[:60]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def _rewrite_csv(ws: Path, rel: str, fn: Callable[[list[dict[str, str]], list[str]], tuple[list[dict[str, str]], list[str]]]) -> None:
    p = ws / rel
    with p.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = list(reader.fieldnames or [])
        rows = list(reader)
    rows, cols = fn(rows, cols)
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", restval="", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


_ROW2 = (
    "| In the supplied sites, hybrid has lower 12-month attrition in both seniority groups | Labor Economics "
    "| Supplied CSV [@C1] (Tier 3 origin), exact tests in own computation [@C4], 2026-10 | `[Preliminary]` |"
)


# ---------------------------------------------------------------------------------------------- the mutations
def m01_data_value_changed(ws: Path) -> None:
    _edit(ws, "appendix/data/hybrid_rct_sites.csv", "0,031", "0,999")


def m02_fake_sha(ws: Path) -> None:
    _edit(
        ws,
        "appendix/sources.csv",
        "9a7419cd60560e66000022fb1d9f55afa4e207a447812d0bb4538b6e9f7f24b4",
        "deadbeef0000" + "0" * 52,
    )


def m03_fabricated_gates(ws: Path) -> None:
    g = ws / "appendix" / "gates"
    g.joinpath("source_verifier.md").write_text(
        "SOURCE-VERIFIER (written by the audited agent itself)\n"
        + "\n".join(f"{i}. PASS - ok" for i in range(1, 8))
        + "\nSOURCE-VERIFIER: PASS\n"
        + "pad " * 120,
        encoding="utf-8",
    )
    g.joinpath("qa.md").write_text(
        "QA (written by the audited agent itself)\n"
        + "\n".join(f"{i} PASS - ok" for i in range(1, 9))
        + "\nQA: PASS\nFAIL count: 0\n"
        + "pad " * 120,
        encoding="utf-8",
    )


def m04_stale_gate(ws: Path) -> None:
    """The gates reviewed an earlier version: sources.csv changed afterwards and the gates were not re-run."""
    _edit(ws, "appendix/sources.csv", "2026-10", "2026-09")


def m05_strong_on_relabelled_tier3(ws: Path) -> None:
    new = _ROW2.replace("(Tier 3 origin)", "(Tier 2 dataset)").replace("`[Preliminary]`", "`[Strong]`")
    _edit(ws, "report.md", _ROW2, new)


def m06_strong_without_citation(ws: Path) -> None:
    new = _ROW2.replace(
        "Supplied CSV [@C1] (Tier 3 origin), exact tests in own computation [@C4], 2026-10", "Supplied sites, 2026-10"
    ).replace("`[Preliminary]`", "`[Strong]`")
    _edit(ws, "report.md", _ROW2, new)


def m07_bloated_verdict(ws: Path) -> None:
    text = (ws / "report.md").read_text(encoding="utf-8")
    m = re.search(r"- \*\*Calibrated Verdict:\*\*.*", text)
    assert m
    bloat = (
        "- **Calibrated Verdict:** Effect 1.1. Also 2.2 and 3.3 and 4.4. More 5.5, 6.6, 7.7. Even 8.8, 9.9, 10.1. "
        "And 11.2, 12.3. Plus 13.4. Finally 14.5 and 15.6. `[Moderate]` overall."
    )
    (ws / "report.md").write_text(text[: m.start()] + bloat + text[m.end() :], encoding="utf-8")


def m08_same_day_inherited_attempt(ws: Path) -> None:
    """A failed attempt logged earlier on the same calendar day as this run started."""
    (ws / "appendix" / "run.json").write_text(
        json.dumps({"run_started_utc": "2026-11-20T12:00:00Z"}), encoding="utf-8"
    )

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        for r in rows:
            if (r.get("outcome") or "").strip().lower() not in {"used", "ok"}:
                r["attempted_utc"] = "2026-11-20T00:00:01Z"
        return rows, cols

    _rewrite_csv(ws, "appendix/data_attempts.csv", fn)


def m09_unregistered_substring_file(ws: Path) -> None:
    (ws / "appendix" / "data" / "sites.csv").write_text("a;b\n1;2\n", encoding="utf-8")


def m10_kind_column_removed(ws: Path) -> None:
    _rewrite_csv(ws, "appendix/sources.csv", lambda rows, cols: (rows, [c for c in cols if c != "kind"]))


def m11_strong_on_own_computation_only(ws: Path) -> None:
    new = _ROW2.replace(
        "Supplied CSV [@C1] (Tier 3 origin), exact tests in own computation [@C4], 2026-10",
        "Exact tests in own computation [@C4], 2026-10",
    ).replace("`[Preliminary]`", "`[Strong]`")
    _edit(ws, "report.md", _ROW2, new)


def m12_nan_in_charts_json(ws: Path) -> None:
    charts = json.loads((ws / "charts.json").read_text(encoding="utf-8"))
    scatter = next(c for c in charts if c["type"] == "scatter")
    scatter["series"][0]["points"][0][1] = float("nan")
    (ws / "charts.json").write_text(json.dumps(charts, allow_nan=True), encoding="utf-8")


def m13_inverted_fan_quantiles(ws: Path) -> None:
    charts = json.loads((ws / "charts.json").read_text(encoding="utf-8"))
    pts = lambda lo, hi: [["2026-11", lo], ["2027-12", hi]]  # noqa: E731
    charts.append(
        {
            "id": "bad_fan",
            "type": "fan",
            "title": "Inverted quantiles",
            "x": {"type": "date"},
            "y": {"label": "Index"},
            "quantiles": {
                "p10": pts(300, 320),
                "p50": pts(100, 120),
                "p90": pts(10, 20),
            },
        }
    )
    (ws / "charts.json").write_text(json.dumps(charts), encoding="utf-8")
    _edit(ws, "report.md", "{{fig:mentoring_scatter}}", "{{fig:mentoring_scatter}}\n\n{{fig:bad_fan}}")


def m14_user_curated_corpus_without_provenance(ws: Path) -> None:
    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        cols = cols + [c for c in ("selection", "retrieved_utc") if c not in cols]
        for r in rows:
            r["selection"] = "user-curated"
            r["retrieved_utc"] = ""
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)


def m15_gate_deleted(ws: Path) -> None:
    (ws / "appendix" / "gates" / "qa.md").unlink()


def m16_stale_html(ws: Path) -> None:
    _edit(ws, "report.md", "## 7. Limitations", "<!-- edited after render -->\n## 7. Limitations")


def m17_unresolved_num_marker(ws: Path) -> None:
    _edit(ws, "report.md", "{{num:pr_did_p}}", "{{num:no_existe}}")


def m18_citation_to_missing_source(ws: Path) -> None:
    _edit(ws, "report.md", "[@C4]", "[@C99]")


def m19_home_path_in_report(ws: Path) -> None:
    _edit(ws, "report.md", "## 7. Limitations", "Data read from /home/alice/secret/datos.csv.\n\n## 7. Limitations")


def m20_tier_laundering_local_user_curated(ws: Path) -> None:
    """A user-curated local file in appendix/data/ is upgraded to Tier 1 with a dated retrieved_utc."""
    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        cols = cols + [c for c in ("selection", "retrieved_utc") if c not in cols]
        for r in rows:
            if (r.get("claim_id") or "").strip() == "C1":
                r["tier"] = "Tier 1"
                r["selection"] = "user-curated"
                r["retrieved_utc"] = "2026-11-20T09:00:00Z"
            else:
                r["selection"] = "agent-fetched"
                r["retrieved_utc"] = "2026-11-20T12:00:00Z"
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)


def m21_forged_agent_fetched_before_run_start(ws: Path) -> None:
    """An agent-fetched data row has retrieved_utc earlier than run_started_utc and no download_log."""
    (ws / "appendix" / "run.json").write_text(
        json.dumps({"run_started_utc": "2026-11-20T15:07:48Z"}), encoding="utf-8"
    )

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        cols = cols + [c for c in ("selection", "retrieved_utc") if c not in cols]
        for r in rows:
            if (r.get("claim_id") or "").strip() == "C2":
                r["selection"] = "agent-fetched"
                r["retrieved_utc"] = "2026-11-20T15:05:00Z"
            else:
                r["selection"] = "third-party"
                r["retrieved_utc"] = "2026-11-20T15:10:00Z"
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)


def m22_weak_agent_fetched_counter_evidence(ws: Path) -> None:
    """User-curated corpus paired only with a Tier 3 / press agent-fetched source."""
    (ws / "appendix" / "run.json").write_text(
        json.dumps({"run_started_utc": "2026-11-20T09:00:00Z"}), encoding="utf-8"
    )

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        cols = cols + [c for c in ("selection", "retrieved_utc") if c not in cols]
        for r in rows:
            r["selection"] = "user-curated"
            r["retrieved_utc"] = "2026-11-20T09:05:00Z"
        rows.append(
            {
                "claim_id": "C9",
                "source_title": "Industry blog commentary",
                "url": "https://example.org/blog/hybrid-opinion",
                "tier": "Tier 3",
                "accessed_date": "2026-11-20",
                "data_as_of": "2026-11",
                "kind": "press",
                "sha256": "",
                "selection": "agent-fetched",
                "retrieved_utc": "2026-11-20T09:10:00Z",
            }
        )
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)
    _edit(ws, "report.md", "[@C2]", "[@C2; @C9]")


def m23_observed_line_chart_after_as_of(ws: Path) -> None:
    """An observed line chart (no observed_until) plots a point date after the report As-Of Date."""
    charts = json.loads((ws / "charts.json").read_text(encoding="utf-8"))
    charts.append(
        {
            "id": "future_obs",
            "type": "line",
            "title": "Synthetic future observation",
            "x": {"type": "date"},
            "y": {"label": "MW"},
            "series": [{"name": "Capacity", "points": [["2025-12", 100.0], ["2026-12", 110.0]]}],
        }
    )
    (ws / "charts.json").write_text(json.dumps(charts), encoding="utf-8")
    _edit(ws, "report.md", "{{fig:mentoring_scatter}}", "{{fig:mentoring_scatter}}\n\n{{fig:future_obs}}")


def m24_harking_preregistration_contains_results(ws: Path) -> None:
    """preregistration.json seals exact computed numbers from numbers.json inside H1."""
    import hashlib

    nums = json.loads((ws / "appendix" / "numbers.json").read_text(encoding="utf-8"))
    vals = [str(v) for v in nums.values() if re.search(r"\d+\.\d{2,}", str(v))][:2]
    assert len(vals) >= 2
    h0 = "No difference between hybrid and office sites."
    h1 = f"Hybrid changes output by {vals[0]} and second metric by {vals[1]}."
    plan = "Exact stratified permutation tests."
    body = {"sealed_utc": "2026-11-20T08:00:00Z", "hypotheses": {"H0": h0, "H1": h1}, "plan": plan}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
    body["sha256"] = digest
    (ws / "appendix" / "preregistration.json").write_text(json.dumps(body, indent=2), encoding="utf-8")


def m25_untraced_stat_in_section4_table(ws: Path) -> None:
    """A Section 4 results table cell contains a hand-typed statistic absent from output.txt and numbers.json."""
    _edit(
        ws,
        "report.md",
        "| Junior | 8 | {{num:pr_jun_hyb}} | {{num:pr_jun_off}} | {{num:pr_jun_diff}} | {{num:pr_jun_p}} |",
        "| Junior | 8 | {{num:pr_jun_hyb}} | {{num:pr_jun_off}} | {{num:pr_jun_diff}} | 0.4180 |",
    )


# ------------------------------------------------------------------------------------------ v0.8.1 mutations (M26+)
def _add_selection_columns(ws: Path, c1_tier: str | None = None) -> None:
    """Give sources.csv selection/retrieved_utc columns: C1 user-curated, everything else agent-fetched."""

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        cols = cols + [c for c in ("selection", "retrieved_utc") if c not in cols]
        for r in rows:
            if (r.get("claim_id") or "").strip() == "C1":
                if c1_tier:
                    r["tier"] = c1_tier
                r["selection"] = "user-curated"
                r["retrieved_utc"] = "2026-11-20T09:00:00Z"
            else:
                r["selection"] = "agent-fetched"
                r["retrieved_utc"] = "2026-11-20T12:00:00Z"
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)


def _register_local_csv(ws: Path, rel: str, claim_id: str, title: str, tier: str, selection: str | None = None) -> None:
    """Append a registered local data file (with its real sha256 prefix) to sources.csv."""
    import local_data

    digest = local_data.sha256_file(ws / rel)

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        row = {
            "claim_id": claim_id,
            "source_title": f"{title} (local file, sha256 {digest})",
            "url": rel,
            "tier": tier,
            "accessed_date": "2026-11-20",
            "data_as_of": "2026-10",
            "kind": "data",
        }
        if "selection" in cols:
            row["selection"] = selection or "user-curated"
            row["retrieved_utc"] = "2026-11-20T09:00:00Z"
        rows.append(row)
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)


def m26_local_user_curated_laundered_to_tier2(ws: Path) -> None:
    """A user-curated local file is bumped to Tier 2 (not Tier 1) and carries a [Strong] claim."""
    _add_selection_columns(ws, c1_tier="Tier 2")
    _edit(ws, "report.md", _ROW2, _ROW2.replace("(Tier 3 origin)", "(Tier 2)").replace("`[Preliminary]`", "`[Strong]`"))


def _write_parameters_table(ws: Path) -> None:
    """appendix/data/parameters.csv inherits Tier 3 from sources_metadata.csv through primary_source_id."""
    data = ws / "appendix" / "data"
    data.joinpath("parameters.csv").write_text(
        "parameter,value,primary_source_id\nreview_window_days,30,S1\nquorum,5,S1\n", encoding="utf-8"
    )
    data.joinpath("sources_metadata.csv").write_text(
        "source_id,tier,title\nS1,Tier 3,Industry blog commentary\n", encoding="utf-8"
    )


def m27_strong_on_table_inheriting_tier3(ws: Path) -> None:
    """A [Strong] row cites a local table (declared Tier 2) whose cells inherit Tier 3 via primary_source_id."""
    _write_parameters_table(ws)
    _register_local_csv(ws, "appendix/data/parameters.csv", "C5", "Parameters table transcribed from a document", "Tier 2")
    _register_local_csv(ws, "appendix/data/sources_metadata.csv", "C6", "Source metadata for the parameters table", "Tier 2")
    _edit(
        ws,
        "report.md",
        "| Lower mentoring hours explain the junior output gap",
        "| The documented review window is 30 days | Software Engineering | Parameters table [@C5], Tier 2, "
        "2026-10 | `[Strong]` | A revised source document with a different window |\n"
        "| Lower mentoring hours explain the junior output gap",
    )


def m28_agent_fetched_literature_without_proof(ws: Path) -> None:
    """kind=literature rows are marked agent-fetched but no `used` attempt in data_attempts.csv backs them."""
    _add_selection_columns(ws)


def m29_data_file_added_after_prereg(ws: Path) -> None:
    """A data file appears in appendix/data/ after preregistration was sealed, outside download_log and intake."""
    import hashlib

    import local_data

    app = ws / "appendix"
    known = {"data/hybrid_rct_sites.csv": local_data.sha12(app / "data" / "hybrid_rct_sites.csv")}
    body = {
        "sealed_utc": "2026-11-20T08:00:00Z",
        "hypotheses": {"H0": "No difference between hybrid and office sites.", "H1": "Hybrid changes output."},
        "plan": "Exact stratified permutation tests.",
        "known_artifacts": known,
    }
    body["sha256"] = hashlib.sha256(
        json.dumps({k: v for k, v in body.items() if k != "sha256"}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    (app / "preregistration.json").write_text(json.dumps(body, indent=1, ensure_ascii=False), encoding="utf-8")
    (app / "data" / "parameters.csv").write_text("parameter,value\nreview_window_days,30\n", encoding="utf-8")
    _register_local_csv(ws, "appendix/data/parameters.csv", "C5", "Constants transcribed by hand", "Tier 3")


def m30_chart_caption_contradicts_output(ws: Path) -> None:
    """A charts.json caption carries a figure that appears in neither output.txt nor numbers.json."""
    charts = json.loads((ws / "charts.json").read_text(encoding="utf-8"))
    charts[0]["caption"] = charts[0]["caption"].rstrip(".") + "; 93,6 % of the covariance is between stations."
    (ws / "charts.json").write_text(json.dumps(charts), encoding="utf-8")


def _append_fan(ws: Path, chart: dict) -> None:
    charts = json.loads((ws / "charts.json").read_text(encoding="utf-8"))
    charts.append(chart)
    (ws / "charts.json").write_text(json.dumps(charts), encoding="utf-8")
    _edit(ws, "report.md", "{{fig:mentoring_scatter}}", "{{fig:mentoring_scatter}}\n\n{{fig:fan_v081}}")


def m31_fan_called_calibrated_without_calibration(ws: Path) -> None:
    """A fan chart claims calibrated quantiles but has no calibration block (method + source_id)."""
    pts = lambda a, b, c: [["2026-10", a], ["2026-11", b], ["2026-12", c]]  # noqa: E731
    _append_fan(
        ws,
        {
            "id": "fan_v081",
            "type": "fan",
            "title": "Calibrated fan for attrition",
            "caption": "Quantiles are compound-rate scenarios.",
            "x": {"type": "date", "observed_until": "2026-10"},
            "y": {"label": "Index"},
            "quantiles": {"p10": pts(100, 98, 96), "p50": pts(100, 101, 102), "p90": pts(100, 104, 108)},
        },
    )


def m32_fan_p10_excludes_decline(ws: Path) -> None:
    """The first projected p10 sits above the last observed (p50) value, so no decline is representable."""
    pts = lambda a, b, c: [["2026-10", a], ["2026-11", b], ["2026-12", c]]  # noqa: E731
    _append_fan(
        ws,
        {
            "id": "fan_v081",
            "type": "fan",
            "title": "Scenario fan for attrition",
            "caption": "Quantiles are compound-rate scenarios.",
            "x": {"type": "date", "observed_until": "2026-10"},
            "y": {"label": "Index"},
            "quantiles": {"p10": pts(100, 103, 106), "p50": pts(100, 105, 110), "p90": pts(100, 108, 116)},
        },
    )


def m33_analysis_changed_after_reviewer(ws: Path) -> None:
    """analysis.py changes after reviewer.md was stamped and Section 5 has no post-review section."""
    import hashlib

    app = ws / "appendix"
    stale = hashlib.sha256(b"analysis.py as the reviewer saw it").hexdigest()
    app.joinpath("gates", "reviewer.md").write_text(
        "MODE: subagent\n"
        f"REVIEWED-SHA256: {validate_report.gate_hash(ws, 'reviewer')}\n"
        "REVIEWED-UTC: 2026-11-20T10:00:00Z\n"
        f"ANALYSIS-SHA256: {stale}\n"
        "QUOTE: report.md:1: \"Hybrid Work\"\n"
        "QUOTE: report.md:5: \"Executive Summary\"\n" + "pad " * 120,
        encoding="utf-8",
    )


def m34_bare_digit_tier_dodges_tier3_rules(ws: Path) -> None:
    """The Tier 3 source is written as tier '3', so every 'Tier 3' rule misses it, and it carries [Strong]."""

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        for r in rows:
            if (r.get("claim_id") or "").strip() == "C1":
                r["tier"] = "3"
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)
    _edit(ws, "report.md", _ROW2, _ROW2.replace(" (Tier 3 origin), exact tests in own computation [@C4]", "").replace("`[Preliminary]`", "`[Strong]`"))


# ------------------------------------------------------------------------------------------ v0.9.0 mutations (M35+)
def _write_prereg(ws: Path, hypotheses: dict[str, str], known_artifacts: dict[str, str] | None = None) -> None:
    """Seal appendix/preregistration.json validly (digest included) before the run started its analysis."""
    import hashlib

    body: dict = {
        "sealed_utc": "2026-11-20T08:00:00Z",
        "hypotheses": hypotheses,
        "plan": "Exact stratified permutation tests.",
        "known_artifacts": known_artifacts or {},
    }
    body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    (ws / "appendix" / "preregistration.json").write_text(json.dumps(body, indent=1, ensure_ascii=False), encoding="utf-8")


def m35_harking_with_rounded_results(ws: Path) -> None:
    """H1 states two computed results rounded ("30%" and "9,6%"), which the exact-figure HARKing check never matches."""
    nums = json.loads((ws / "appendix" / "numbers.json").read_text(encoding="utf-8"))
    assert nums["attr_rel_drop_w"] == "30.1%" and nums["attr_hyb_w"] == "9.6%"
    _write_prereg(
        ws,
        {
            "H0": "No difference between hybrid and office sites.",
            "H1": "Hybrid cuts attrition by about 30% and brings it down to 9,6% across the supplied sites.",
        },
    )


def m36_unresolvable_primary_source_ids(ws: Path) -> None:
    """A local table cites primary_source_id values that the catalogue cannot resolve (one has an inner space)."""
    data = ws / "appendix" / "data"
    data.joinpath("parameters.csv").write_text(
        "parameter,value,primary_source_id\nreview_window_days,30,SRC _42\nquorum,5,S9\n", encoding="utf-8"
    )
    data.joinpath("sources_metadata.csv").write_text("source_id,tier,title\nS1,Tier 1,Statistical office table\n", encoding="utf-8")
    _register_local_csv(ws, "appendix/data/parameters.csv", "C5", "Parameters table transcribed from a document", "Tier 3")
    _register_local_csv(ws, "appendix/data/sources_metadata.csv", "C6", "Source metadata for the parameters table", "Tier 3")


def m37_data_as_of_after_report_date(ws: Path) -> None:
    """A source claims data as of a month after the report's As-Of Date."""

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        for r in rows:
            if (r.get("claim_id") or "").strip() == "C2":
                r["data_as_of"] = "2027-03"
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)


def m38_lowercase_tag_in_matrix_row(ws: Path) -> None:
    """A matrix row writes its tag in lowercase (as copied from the rendered HTML): the tag is not canonical."""
    _edit(ws, "report.md", _ROW2, _ROW2.replace("`[Preliminary]`", "`[preliminary]`"))


def m39_unprocessed_file_left_in_inbox(ws: Path) -> None:
    """A file sits in inbox/ that neither sources.csv (by hash) nor intake.md (accepted or rejected) accounts for."""
    inbox = ws / "inbox" / "sources"
    inbox.mkdir(parents=True)
    (inbox / "stray.pdf").write_bytes(b"%PDF-1.4 a document nobody registered\n")
    (ws / "appendix" / "intake.md").write_text(
        "# Intake report\n\n## Channel: sources\n\n- rejected: other.png \u2014 not a table (png)\n", encoding="utf-8"
    )


# ------------------------------------------------------------------------------------------ v0.10.0 mutations (M40+)
from contracts import PAPER_COLS, SEARCH_LOG_COLS  # noqa: E402  (the connector's schemas live in contracts.py)

BLOOM_DOI = "10.1038/s41586-024-07500-2"
BLOOM_TITLE = "Hybrid working from home improves retention without damaging performance"


def _paper(doi: str, title: str, **kw: str) -> dict[str, str]:
    row = {
        "doi": doi, "title": title, "first_author": "Fixture Author", "n_authors": "1", "year": "2024", "venue": "Journal of Fixtures",
        "work_type": "article", "is_retracted": "false", "is_oa": "false", "abstract_sha256": "a" * 64, "fulltext_file": "",
        "fulltext_sha256": "", "providers": "openalex", "via": "api", "retrieved_utc": "2026-11-20T12:00:00Z", "query_id": "Q1",
    }
    row.update(kw)
    return row


_ABSTRACT = "A short abstract."


def _cache_for(ws: Path, rec: dict[str, str], *, prefix: str = "", retrieved: str = "2026-11-20T12:00:00Z", log: bool = True) -> str:
    """Write the OpenAlex response the connector would have cached for ``rec``, hash it in download_log.csv, so replay explains the row.

    ``prefix="import_"`` caches it the way ``papers.py import`` does; ``log=False`` leaves it unlogged (a file dropped in by hand)."""
    import hashlib
    import json

    work = {
        "id": f"https://openalex.org/W{int(hashlib.sha256(rec['doi'].encode('utf-8')).hexdigest()[:8], 16) % 10**8}", "doi": f"https://doi.org/{rec['doi']}", "title": rec["title"],
        "publication_year": int(rec["year"]), "type": rec["work_type"], "is_retracted": rec["is_retracted"] == "true",
        "authorships": [{"author": {"display_name": rec["first_author"]}}] * int(rec["n_authors"]),
        "primary_location": {"source": {"display_name": rec["venue"]}}, "open_access": {"is_oa": rec["is_oa"] == "true", "oa_url": None},
        "abstract_inverted_index": {w: [i] for i, w in enumerate(_ABSTRACT.split())},
    }
    payload = json.dumps(work).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    name = f"papers/raw/{prefix}openalex-{digest[:12]}-001.json"
    target = ws / "appendix" / "data" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    if log:
        log_path = ws / "appendix" / "download_log.csv"
        new = not log_path.exists()
        with log_path.open("a", encoding="utf-8", newline="") as fh:
            if new:
                fh.write("file,url,retrieved_utc,bytes,sha256\n")
            fh.write(f"{name},https://api.openalex.org/works/doi:{rec['doi']},{retrieved},{len(payload)},{digest}\n")
    return f"appendix/data/{name}"


def _papers_workspace(
    ws: Path,
    extra: list[dict[str, str]] | None = None,
    search_rows: list[dict[str, str]] | None = None,
    cache_opts: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Give the golden copy a connector registry: papers.csv with the real article (and ``extra`` records), their cached
    responses and a search log. A clean registry replays cleanly; each mutation then breaks exactly one thing."""
    import hashlib

    _add_selection_columns(ws)
    rows = [_paper(BLOOM_DOI, BLOOM_TITLE, first_author="Bloom", n_authors="3", venue="Nature", is_oa="true")]
    rows += extra or []
    cached = []
    unlogged: set[int] = set()
    for i, r in enumerate(rows):
        r["abstract_sha256"] = hashlib.sha256(_ABSTRACT.encode("utf-8")).hexdigest()
        opts = (cache_opts or {}).get(r["doi"], {})
        cached.append(_cache_for(ws, r, **opts))
        if opts.get("log") is False:
            unlogged.add(i)
    for name, cols, data in (
        ("papers.csv", PAPER_COLS, rows),
        ("search_log.csv", SEARCH_LOG_COLS, search_rows or [
            {"query_id": f"Q{i + 1}", "provider": "openalex", "query": "hybrid work attrition", "filters": "", "n_hits": "1",
             "retrieved_utc": "2026-11-20T12:00:00Z", "raw_file": raw}
            for i, raw in enumerate(cached) if i not in unlogged  # one logged search per legitimate cache file
        ]),
    ):
        with (ws / "appendix" / name).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(data)


def _cite_literature(ws: Path, doi: str, title: str, tier: str, claim_id: str = "C5", url: str = "") -> None:
    """Register a literature source for ``doi`` (``url`` defaults to its doi.org link) and cite it in the report."""

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        rows.append({
            "claim_id": claim_id, "source_title": title, "url": url or f"https://doi.org/{doi}", "tier": tier, "accessed_date": "2026-11-20",
            "data_as_of": "2024-06", "kind": "literature", "selection": "agent-fetched", "retrieved_utc": "2026-11-20T12:00:00Z",
        })
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)
    _edit(ws, "report.md", _ROW2, _ROW2.replace("[@C4]", f"[@C4; @{claim_id}]"))


def m40_typed_doi_not_in_papers_csv(ws: Path) -> None:
    """An agent-fetched literature row names a DOI that the connector never retrieved (typed from memory)."""
    _papers_workspace(ws)
    _cite_literature(ws, "10.9999/typed.from.memory.1", "A paper cited from memory", "Tier 2")


def m41_preprint_declared_tier1(ws: Path) -> None:
    """A work the connector recorded as a preprint is registered as Tier 1."""
    _papers_workspace(ws, [_paper("10.9999/fake.preprint.1", "A synthetic preprint about fixtures", work_type="preprint")])
    _cite_literature(ws, "10.9999/fake.preprint.1", "A synthetic preprint about fixtures", "Tier 1")


def m42_retracted_work_cited(ws: Path) -> None:
    """A work recorded as retracted is cited in the report."""
    _papers_workspace(ws, [_paper("10.9999/fake.retracted.1", "A synthetic retracted article", is_retracted="true")])
    _cite_literature(ws, "10.9999/fake.retracted.1", "A synthetic retracted article", "Tier 2")


def m43_fulltext_edited_after_registration(ws: Path) -> None:
    """The open-access full text saved by the connector is edited after its hash was logged (regression of P0-SHA)."""
    import hashlib

    rel = "appendix/data/papers/10.9999_fake.fulltext.1.txt"
    target = ws / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("The full text as it was downloaded.\n", encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (ws / "appendix" / "download_log.csv").write_text(
        "file,url,retrieved_utc,bytes,sha256\n"  # `file` is relative to appendix/data/, as fetch_lib writes it
        + f"papers/{target.name},https://doi.org/10.9999/fake.fulltext.1,2026-11-20T12:00:00Z,{target.stat().st_size},{digest}\n",
        encoding="utf-8",
    )
    _papers_workspace(ws, [_paper("10.9999/fake.fulltext.1", "A synthetic article with saved full text", fulltext_file=rel, fulltext_sha256=digest)])
    target.write_text("The full text, quietly rewritten afterwards.\n", encoding="utf-8")


def m44_title_differs_from_papers_csv(ws: Path) -> None:
    """sources.csv gives the DOI a title unrelated to the one the connector recorded."""
    _papers_workspace(ws, [_paper("10.9999/fake.title.1", "Quarterly attrition among hospital nurses")])
    _cite_literature(ws, "10.9999/fake.title.1", "Remote work and productivity gains in software teams", "Tier 2")


def m45_credentials_left_in_appendix(ws: Path) -> None:
    """A logged request URL keeps the API key and the contact address in appendix/."""
    _papers_workspace(
        ws,
        search_rows=[{
            "query_id": "Q1", "provider": "openalex", "query": "hybrid work attrition", "filters": "", "n_hits": "6",
            "retrieved_utc": "2026-11-20T12:00:00Z",
            "raw_file": "https://api.openalex.org/works?search=x&api_key=abc123def456&mailto=alias@example.org",
        }],
    )


def m47_papers_csv_edited_by_hand(ws: Path) -> None:
    """A title in papers.csv is edited after the connector cached the response that gave the original one."""
    _papers_workspace(ws, [_paper("10.9999/fake.edited.1", "The title the databases gave")])
    p = ws / "appendix" / "papers.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("The title the databases gave", "A title nobody retrieved"), encoding="utf-8")


def m46_imported_record_carries_tier1(ws: Path) -> None:
    """A record the agent imported by hand (not retrieved by the connector) sustains a Tier 1 source."""
    _papers_workspace(
        ws,
        [_paper("10.9999/fake.imported.1", "A synthetic article whose record was imported", via="import")],
        cache_opts={"10.9999/fake.imported.1": {"prefix": "import_"}},
    )
    _cite_literature(ws, "10.9999/fake.imported.1", "A synthetic article whose record was imported", "Tier 1")


# ---- v0.10.0 audit: ways to make a connector registry say what the cache does not (M48+)
def m48_via_import_relabelled_api(ws: Path) -> None:
    """A record the agent imported is relabelled ``via=api`` in papers.csv so it can sustain Tier 1."""
    doi, title = "10.9999/fake.relabelled.1", "A synthetic article whose provenance was relabelled"
    _papers_workspace(ws, [_paper(doi, title, via="api")], cache_opts={doi: {"prefix": "import_"}})
    _cite_literature(ws, doi, title, "Tier 1")


def m49_retrieved_utc_moved_into_the_run(ws: Path) -> None:
    """papers.csv says the work was retrieved inside the run; the cache says it was retrieved before it started."""
    doi, title = "10.9999/fake.backdated.1", "A synthetic article retrieved before the run"
    _papers_workspace(
        ws,
        [_paper(doi, title, retrieved_utc="2026-11-20T13:00:00Z")],
        cache_opts={doi: {"retrieved": "2026-11-20T11:00:00Z"}},
    )
    _cite_literature(ws, doi, title, "Tier 2")


def m50_forged_cache_file_explains_a_row(ws: Path) -> None:
    """A response file dropped into raw/ by hand (no search_log row, no download_log hash) is used to explain a hand-written row."""
    doi = "10.9999/fake.forged.1"
    _papers_workspace(ws, [_paper(doi, "A synthetic article nobody retrieved")], cache_opts={doi: {"log": False}})


def m51_fulltext_points_at_any_file(ws: Path) -> None:
    """A recorded full text is the report itself and has no SHA-256, so nothing can ever show it changed."""
    _papers_workspace(ws, [_paper("10.9999/fake.fulltext.2", "A synthetic article with a fake full text", fulltext_file="report.md", fulltext_sha256="")])


def m52_publisher_url_hides_the_doi(ws: Path) -> None:
    """A preprint is declared Tier 1 with the publisher's URL (the DOI is inside the path) instead of a doi.org link."""
    doi, title = "10.9999/fake.publisher.1", "A synthetic preprint cited by its publisher link"
    _papers_workspace(ws, [_paper(doi, title, work_type="preprint")])
    _cite_literature(ws, doi, title, "Tier 1", url=f"https://www.example.org/articles/{doi}")


# ---- v0.10.1: gate laws the validator now counts (second audit)
def m53_source_verifier_fail_not_named(ws: Path) -> None:
    """The source verifier ended in FAIL and the report no longer names and justifies the accepted problems."""
    report = ws / "report.md"
    report.write_text(report.read_text(encoding="utf-8").replace("appendix/gates/source_verifier.md", "the source-verification gate"), encoding="utf-8")


def m54_second_gate_pass_appended(ws: Path) -> None:
    """A second source-verifier pass is appended below the first instead of replacing the file."""
    gate = ws / "appendix" / "gates" / "source_verifier.md"
    text = gate.read_text(encoding="utf-8")
    gate.write_text(text + "\n\n" + text, encoding="utf-8")


# ---- v0.11.0: formal mathematics (Lean 4 / Lake) & symbolic conjecture discovery (M55–M60)
from contracts import FORMAL_PROOF_COLS  # noqa: E402


def _formal_workspace(
    ws: Path,
    *,
    slug: str = "bound_proof",
    challenge_src: str = "namespace Challenge\ntheorem main_claim (n : Nat) : n + 0 = n := by sorry\nend Challenge\n",
    solution_src: str = "import Challenge\nnamespace Solution\ntheorem main_claim (n : Nat) : n + 0 = n := Nat.add_zero n\nend Solution\n",
    status: str = "kernel-verified",
    verification_mode: str = "kernel-defeq",
    sorries: str = "0",
    axioms: str = "propext;Classical.choice",
    tier: str = "Tier 1",
    write_registry: bool = True,
    strong_claim: bool = True,
) -> Path:
    """Seed an opt-in Lean 4 formal-proof workspace and register source F1."""
    import hashlib

    proj = ws / "appendix" / "formal" / slug
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "lean-toolchain").write_text("leanprover/lean4:v4.16.0\n", encoding="utf-8")
    (proj / "lakefile.toml").write_text(f'name = "{slug}"\ndefaultTargets = ["Challenge", "Solution"]\n', encoding="utf-8")
    ch_path = proj / "Challenge.lean"
    sol_path = proj / "Solution.lean"
    ch_path.write_text(challenge_src, encoding="utf-8")
    sol_path.write_text(solution_src, encoding="utf-8")
    ch_sha = hashlib.sha256(ch_path.read_bytes()).hexdigest()
    sol_sha = hashlib.sha256(sol_path.read_bytes()).hexdigest()
    eff_mode = "none" if status == "unverified_no_toolchain" else verification_mode
    verify = {
        "slug": slug,
        "theorem_name": "main_claim",
        "challenge_sha256": ch_sha,
        "solution_sha256": sol_sha,
        "toolchain": "leanprover/lean4:v4.16.0",
        "lean_version": "Lean (version 4.16.0)",
        "verification_mode": eff_mode,
        "status": status,
        "sorries": int(sorries),
        "axioms": [a for a in axioms.split(";") if a],
        "verified_utc": "2026-11-20T12:30:00Z",
    }
    (proj / "verify.json").write_text(json.dumps(verify, indent=1) + "\n", encoding="utf-8")
    if write_registry:
        reg_path = ws / "appendix" / "formal_proofs.csv"
        with reg_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FORMAL_PROOF_COLS, lineterminator="\n")
            w.writeheader()
            w.writerow(
                {
                    "proof_id": "F1",
                    "slug": slug,
                    "theorem_name": "main_claim",
                    "challenge_file": f"appendix/formal/{slug}/Challenge.lean",
                    "challenge_sha256": ch_sha,
                    "solution_file": f"appendix/formal/{slug}/Solution.lean",
                    "solution_sha256": sol_sha,
                    "toolchain": "leanprover/lean4:v4.16.0",
                    "lean_version": "4.16.0",
                    "verification_mode": eff_mode,
                    "status": status,
                    "sorries": sorries,
                    "axioms": axioms,
                    "verified_utc": "2026-11-20T12:30:00Z",
                }
            )

    rel_sol = f"appendix/formal/{slug}/Solution.lean"

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        if "sha256" not in cols:
            cols = cols + ["sha256"]
        rows.append(
            {
                "claim_id": "F1",
                "source_title": f"Lean 4 formal proof {slug}/Solution.lean (sha256 {sol_sha})",
                "url": rel_sol,
                "tier": tier,
                "accessed_date": "2026-11-20",
                "data_as_of": "2026-11",
                "kind": "formal-proof",
                "sha256": sol_sha,
            }
        )
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)
    tag = "`[Strong]`" if strong_claim else "`[Preliminary]`"
    _edit(
        ws,
        "report.md",
        "| Lower mentoring hours explain the junior output gap",
        f"| Formal deductive identity n + 0 = n holds under Peano axioms | Formal Sciences | Lean 4 proof [@F1], {tier}, 2026-11 | {tag} | Kernel refutation |\n"
        "| Lower mentoring hours explain the junior output gap",
    )
    return proj


def _conjecture_payload(*, train_count: int = 12, holdout_count: int = 4, beats_null: bool = True) -> dict[str, Any]:
    import hashlib

    body: dict[str, Any] = {
        "sealed_utc": "2026-11-20T12:00:00Z",
        "data_file": "appendix/data/hybrid_rct_sites.csv",
        "data_sha256": "9a7419cd60560e66000022fb1d9f55afa4e207a447812d0bb4538b6e9f7f24b4",
        "target": "attrition_12m",
        "predictors": ["mentoring_hrs_wk"],
        "train_count": train_count,
        "holdout_count": holdout_count,
        "holdout_mode": "tail",
        "beats_null": beats_null,
        "candidates": [
            {
                "id": "C_LAW_1",
                "family": "power_law",
                "expr": "attrition_12m = 0.25 * mentoring_hrs_wk^(-1/2)",
                "complexity_k": 2,
                "train_bic": -42.0,
                "holdout_rmse": 0.012,
                "holdout_r2": 0.94,
            }
        ],
        "falsifier_prediction": "At mentoring_hrs_wk = 16.0, attrition_12m should equal 0.0625 +/- 0.02.",
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    body["sha256"] = digest
    return body


def m55_formal_proof_with_sorry_or_custom_axiom(ws: Path) -> None:
    """A kind=formal-proof source declared Tier 1 has an active sorry / non-standard axiom in Solution.lean."""
    _formal_workspace(
        ws,
        solution_src="import Challenge\ntheorem main_claim_proof (n : Nat) : n + 0 = n := by sorry\n",
    )


def m56_unverified_formal_proof_declared_tier1(ws: Path) -> None:
    """A kind=formal-proof source declared Tier 1 has status=unverified_no_toolchain."""
    _formal_workspace(ws, status="unverified_no_toolchain")


def m57_vacuous_challenge_lean_statement(ws: Path) -> None:
    """Challenge.lean proves a vacuous premise (h : False) while sustaining a [Strong] claim."""
    _formal_workspace(
        ws,
        challenge_src="theorem main_claim (h : False) : 1 = 2 := False.elim h\n",
        solution_src="import Challenge\n",
    )


def m58_conjectures_json_zero_holdout(ws: Path) -> None:
    """appendix/conjectures.json was fitted on 100% of rows with holdout_count == 0."""
    payload = _conjecture_payload(train_count=16, holdout_count=0)
    (ws / "appendix" / "conjectures.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


def m59_strong_claim_on_unproved_conjecture(ws: Path) -> None:
    """A Claim-Evidence Matrix row tags an unproved symbolic conjecture from conjectures.json as [Strong]."""
    payload = _conjecture_payload(train_count=12, holdout_count=4)
    (ws / "appendix" / "conjectures.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    _edit(
        ws,
        "report.md",
        "| Lower mentoring hours explain the junior output gap",
        "| Conjectured scaling law C_LAW_1 from appendix/conjectures.json holds universally | Physics | Symbolic fit [@C4] on benchmark [@C2], 2026-10 | `[Strong]` | Out-of-domain test |\n"
        "| Lower mentoring hours explain the junior output gap",
    )


def m60_formal_proof_missing_from_registry(ws: Path) -> None:
    """A kind=formal-proof row claims Tier 1 without a matching entry in appendix/formal_proofs.csv."""
    _formal_workspace(ws, write_registry=False)


def m61_conjecture_strong_cites_discovery_source_as_replication(ws: Path) -> None:
    """A [Strong] conjecture row cites the discovery dataset's own Tier 1 kind=data source (source_ids) as if it were independent replication."""
    import hashlib

    payload = _conjecture_payload(train_count=12, holdout_count=4)
    payload["source_ids"] = ["C5"]
    body = {k: v for k, v in payload.items() if k != "sha256"}
    payload["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    (ws / "appendix" / "conjectures.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    def fn(rows: list[dict[str, str]], cols: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        rows.append(
            {
                "claim_id": "C5",
                "source_title": "Primary discovery table (JPL SSD)",
                "url": "https://ssd.jpl.nasa.gov/planets",
                "tier": "Tier 1",
                "accessed_date": "2026-11-20",
                "data_as_of": "2026-11",
                "kind": "data",
            }
        )
        return rows, cols

    _rewrite_csv(ws, "appendix/sources.csv", fn)
    _edit(
        ws,
        "report.md",
        "| Lower mentoring hours explain the junior output gap",
        "| Conjectured law C_LAW_1 holds across planets | Physics | Symbolic fit [@C4; @C5], Tier 1, 2026-11 | `[Strong]` | Out-of-domain test |\n"
        "| Lower mentoring hours explain the junior output gap",
    )


def m62_conjecture_strong_non_lexical_formula_row(ws: Path) -> None:
    """A [Strong] row states the discovered formula from conjectures.json without using the word 'conjecture'."""
    payload = _conjecture_payload(train_count=12, holdout_count=4)
    (ws / "appendix" / "conjectures.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    _edit(
        ws,
        "report.md",
        "| Lower mentoring hours explain the junior output gap",
        "| The empirical scaling relation attrition_12m = 0.25 * mentoring_hrs_wk^(-1/2) holds universally | Physics | Symbolic fit [@C4] on [@C2], 2026-10 | `[Strong]` | Out-of-domain test |\n"
        "| Lower mentoring hours explain the junior output gap",
    )


def m63_source_verifier_fail_linked_outside_section7(ws: Path) -> None:
    """source_verifier.md ends in FAIL and the report links the gate in Section 3 instead of justifying the problems in Section 7."""
    rep_p = ws / "report.md"
    text = rep_p.read_text(encoding="utf-8")
    sec7_idx = text.index("## 7. Limitations")
    before7 = text[:sec7_idx] + "\nProvenance audit stored in `appendix/gates/source_verifier.md`.\n\n"
    after7 = text[sec7_idx:].replace("appendix/gates/source_verifier.md", "the verifier gate")
    rep_p.write_text(before7 + after7, encoding="utf-8")


def m64_blank_row_in_sources_csv(ws: Path) -> None:
    """appendix/sources.csv contains an empty blank line between rows."""
    s_path = ws / "appendix" / "sources.csv"
    lines = s_path.read_text(encoding="utf-8").splitlines()
    s_path.write_text("\n".join(lines[:2] + [""] + lines[2:]) + "\n", encoding="utf-8")


MUTATIONS: dict[str, tuple[str, Mutation, bool]] = {
    # name: (description, function, re-render after applying)
    "M01": ("data value changed, HTML re-rendered", m01_data_value_changed, True),
    "M02": ("fake 12-hex SHA-256 in sources.csv", m02_fake_sha, True),
    "M03": ("gates rewritten with the right silhouette", m03_fabricated_gates, True),
    "M04": ("gate reviewed an earlier version of the sources", m04_stale_gate, True),
    "M05": ("[Strong] citing a Tier 3 source relabelled in prose", m05_strong_on_relabelled_tier3, True),
    "M06": ("[Strong] row with no citation", m06_strong_without_citation, True),
    "M07": ("verdict with 8 sentences and 15 numbers", m07_bloated_verdict, True),
    "M08": ("failed attempt from earlier the same day", m08_same_day_inherited_attempt, True),
    "M09": ("unregistered file whose name is a substring of a registered one", m09_unregistered_substring_file, True),
    "M10": ("kind column absent from sources.csv", m10_kind_column_removed, True),
    "M11": ("[Strong] resting only on own computation", m11_strong_on_own_computation_only, True),
    "M12": ("NaN in charts.json", m12_nan_in_charts_json, True),
    "M13": ("inverted quantiles in a fan chart", m13_inverted_fan_quantiles, True),
    "M14": ("user-curated corpus without retrieval provenance", m14_user_curated_corpus_without_provenance, True),
    "M15": ("a gate file deleted", m15_gate_deleted, True),
    "M16": ("report edited after the HTML was rendered", m16_stale_html, False),
    "M17": ("unresolved {{num:}} marker", m17_unresolved_num_marker, True),
    "M18": ("citation to a source that does not exist", m18_citation_to_missing_source, True),
    "M19": ("home-directory path in the report", m19_home_path_in_report, True),
    "M20": ("local user-curated file laundered to Tier 1 with dated retrieved_utc", m20_tier_laundering_local_user_curated, True),
    "M21": ("agent-fetched row with retrieved_utc earlier than run_started_utc", m21_forged_agent_fetched_before_run_start, True),
    "M22": ("user-curated corpus paired only with Tier 3 press agent-fetched source", m22_weak_agent_fetched_counter_evidence, True),
    "M23": ("observed line chart plots a point date after the report As-Of Date", m23_observed_line_chart_after_as_of, True),
    "M24": ("preregistration H1 contains exact computed figures from numbers.json (HARKing)", m24_harking_preregistration_contains_results, True),
    "M25": ("Section 4 table cell has a hand-typed statistic absent from output.txt/numbers.json", m25_untraced_stat_in_section4_table, True),
    "M26": ("local user-curated file raised to Tier 2 carrying a [Strong] claim", m26_local_user_curated_laundered_to_tier2, True),
    "M27": ("[Strong] row on a local table whose cells inherit Tier 3 via primary_source_id", m27_strong_on_table_inheriting_tier3, True),
    "M28": ("agent-fetched kind=literature rows with no used attempt in data_attempts.csv", m28_agent_fetched_literature_without_proof, True),
    "M29": ("data file added to appendix/data/ after preregistration was sealed", m29_data_file_added_after_prereg, True),
    "M30": ("charts.json caption carries a figure absent from output.txt/numbers.json", m30_chart_caption_contradicts_output, True),
    "M31": ("fan chart called calibrated with no calibration block", m31_fan_called_calibrated_without_calibration, True),
    "M32": ("fan chart whose first projected p10 is above the last observed value", m32_fan_p10_excludes_decline, True),
    "M33": ("analysis.py changed after reviewer.md with no post-review section in Section 5", m33_analysis_changed_after_reviewer, True),
    "M34": ("tier written as a bare digit ('3') so Tier 3 rules miss a [Strong] row", m34_bare_digit_tier_dodges_tier3_rules, True),
    "M35": ("preregistration H1 states computed results rounded (30%, 9,6%)", m35_harking_with_rounded_results, True),
    "M36": ("local table cites primary_source_id values the catalogue cannot resolve", m36_unresolvable_primary_source_ids, True),
    "M37": ("a source's data_as_of is later than the report As-Of Date", m37_data_as_of_after_report_date, True),
    "M38": ("a matrix row writes its tag in lowercase ('[preliminary]')", m38_lowercase_tag_in_matrix_row, True),
    "M39": ("a file in inbox/ that neither sources.csv nor intake.md accounts for", m39_unprocessed_file_left_in_inbox, True),
    "M40": ("agent-fetched literature row whose DOI is not in papers.csv (typed from memory)", m40_typed_doi_not_in_papers_csv, True),
    "M41": ("a preprint recorded by the connector registered as Tier 1", m41_preprint_declared_tier1, True),
    "M42": ("a work recorded as retracted is cited in the report", m42_retracted_work_cited, True),
    "M43": ("open-access full text edited after its hash was logged", m43_fulltext_edited_after_registration, True),
    "M44": ("sources.csv title unrelated to the papers.csv title of the same DOI", m44_title_differs_from_papers_csv, True),
    "M45": ("API key and contact address left in a logged URL under appendix/", m45_credentials_left_in_appendix, True),
    "M46": ("an imported (agent-attested) record sustains a Tier 1 source", m46_imported_record_carries_tier1, True),
    "M47": ("a papers.csv title edited by hand after the response was cached", m47_papers_csv_edited_by_hand, True),
    "M48": ("an imported record relabelled via=api in papers.csv sustains Tier 1", m48_via_import_relabelled_api, True),
    "M49": ("papers.csv retrieved_utc moved into the run while the cache says it was before", m49_retrieved_utc_moved_into_the_run, True),
    "M50": ("a hand-dropped, unlogged cache file used to explain a papers.csv row", m50_forged_cache_file_explains_a_row, True),
    "M51": ("a recorded full text that is any file, with no SHA-256", m51_fulltext_points_at_any_file, True),
    "M52": ("a preprint declared Tier 1 through a publisher URL that contains the DOI", m52_publisher_url_hides_the_doi, True),
    "M53": ("a source-verifier FAIL the report no longer names and justifies", m53_source_verifier_fail_not_named, True),
    "M54": ("a second source-verifier pass appended instead of replacing the file", m54_second_gate_pass_appended, True),
    "M55": ("a Tier 1 formal-proof source whose Solution.lean contains an active sorry", m55_formal_proof_with_sorry_or_custom_axiom, True),
    "M56": ("a Tier 1 formal-proof source with status=unverified_no_toolchain", m56_unverified_formal_proof_declared_tier1, True),
    "M57": ("Challenge.lean with vacuous premise (h : False) sustaining a [Strong] claim", m57_vacuous_challenge_lean_statement, True),
    "M58": ("appendix/conjectures.json fitted on 100% of rows with holdout_count == 0", m58_conjectures_json_zero_holdout, True),
    "M59": ("a [Strong] matrix row resting on an unproved conjecture from conjectures.json", m59_strong_claim_on_unproved_conjecture, True),
    "M60": ("a Tier 1 formal-proof row with no matching entry in appendix/formal_proofs.csv", m60_formal_proof_missing_from_registry, True),
    "M61": ("a [Strong] conjecture row citing the discovery dataset's own Tier 1 data source as replication", m61_conjecture_strong_cites_discovery_source_as_replication, True),
    "M62": ("a [Strong] matrix row stating the discovered formula without the word 'conjecture'", m62_conjecture_strong_non_lexical_formula_row, True),
    "M63": ("a source-verifier FAIL linked in Section 3 instead of justified in Section 7", m63_source_verifier_fail_linked_outside_section7, True),
    "M64": ("an empty blank line inside appendix/sources.csv", m64_blank_row_in_sources_csv, True),
}

# Mutations the validator does not yet catch -> the v0.8.0 phase that will. Remove an entry when its phase lands.
PENDING: dict[str, int] = {}


# Every mutation must be caught by the check that targets it, never as a side effect (e.g. a gate going stale):
# a message must match its pattern.
EXPECT: dict[str, str] = {
    "M01": r"changed since it was registered",
    "M02": r"deadbeef0000",
    "M03": r"missing header field",
    "M04": r"reviewed an earlier version",
    "M05": r"\[Strong\].*weak source",
    "M06": r"\[Strong\].*no \[@id\] citation",
    "M07": r"Calibrated Verdict has \d+ (?:sentences|numbers)",
    "M08": r"inherited",
    "M09": r"Orphan data file 'appendix/data/sites\.csv'",
    "M10": r"\bkind\b",
    "M11": r"\[Strong\].*weak source.*C4",
    "M12": r"(?i)non-finite|NaN",
    "M13": r"(?i)quantile",
    "M14": r"(?i)user-curated",
    "M15": r"gates/qa\.md is missing",
    "M16": r"(?i)stale",
    "M17": r"no_existe",
    "M18": r"C99",
    "M19": r"home-directory",
    "M20": r"(?i)local.*user-curated.*Tier 1|cannot be Tier 1",
    "M21": r"(?i)agent-fetched.*before run start|precedes run_started_utc",
    "M22": r"(?i)agent-fetched.*Tier 1 or Tier 2|independent Tier 1/2",
    "M23": r"(?i)after the report As-Of Date",
    "M24": r"(?i)computed result figures|HARKing|numbers\.json",
    "M25": r"(?i)not found in appendix/output\.txt or appendix/numbers\.json|untraced",
    "M26": r"cannot be Tier 2",
    "M27": r"(?i)inherit",
    "M28": r"kind=literature",
    "M29": r"(?i)after preregistration",
    "M30": r"(?i)caption",
    "M31": r"(?i)calibration",
    "M32": r"(?i)\bp10\b",
    "M33": r"(?i)after the reviewer",
    "M34": r"has tier '3'",
    "M35": r"(?i)rounded|HARKing",
    "M36": r"(?i)source_id",
    "M37": r"(?i)data_as_of",
    "M38": r"writes '\[preliminary\]'.*exactly as '\[Preliminary\]'",
    "M39": r"^inbox/sources/stray\.pdf is not registered",
    "M40": r"(?i)not in appendix/papers\.csv",
    "M41": r"(?i)preprint.*Tier 1",
    "M42": r"(?i)retracted",
    "M43": r"changed since it was (?:registered|logged)",
    "M44": r"(?i)title.*papers\.csv",
    "M45": r"(?i)credential",
    "M46": r"(?i)imported|attested",
    "M47": r"differs from every cached response",
    "M48": r"(?i)\bvia\b",
    "M49": r"(?i)retrieved_utc",
    "M50": r"(?i)no matching SHA-256 in download_log",
    "M51": r"(?i)full text.*(?:SHA-256|appendix/data/papers)",
    "M52": r"(?i)preprint.*Tier 1",
    "M53": r"SOURCE-VERIFIER: FAIL",
    "M54": r"REVIEWED-SHA256 lines",
    "M55": r"(?i)\bsorry\b|forbidden|non-standard axiom",
    "M56": r"(?i)unverified_no_toolchain|not kernel-verified",
    "M57": r"(?i)vacuous|trivial.*Challenge\.lean",
    "M58": r"(?i)conjectures\.json.*(?:holdout|sha256 mismatch)",
    "M59": r"(?i)conjecture.*\[Strong\]|\[Strong\].*conjecture",
    "M60": r"(?i)formal_proofs\.csv",
    "M61": r"(?i)conjecture.*\[Strong\]|\[Strong\].*conjecture",
    "M62": r"(?i)conjecture.*\[Strong\]|\[Strong\].*conjecture",
    "M63": r"SOURCE-VERIFIER: FAIL.*Section 7",
    "M64": r"sources\.csv contains a blank row",
}
# Mutations about the gates themselves keep the gates as the mutation left them; every other mutation re-stamps
# REVIEWED-SHA256 afterwards, as an agent covering its tracks would.
NO_RESTAMP = {"M03", "M04", "M15"}


def caught(name: str, msgs: list[str]) -> bool:
    return any(re.search(EXPECT[name], m) for m in msgs)


def restamp_gates(ws: Path) -> None:
    gates = ws / "appendix" / "gates"
    for g in sorted(gates.glob("*.md")) if gates.is_dir() else []:
        text = g.read_text(encoding="utf-8")
        new = re.sub(
            r"^(\s*REVIEWED-SHA256:\s*)[0-9a-fA-F]{12,64}",
            lambda m: m.group(1) + validate_report.gate_hash(ws, g.stem),
            text,
            flags=re.MULTILINE,
        )
        g.write_text(new, encoding="utf-8")


def run_mutation(name: str) -> list[str]:
    """Apply one mutation to a fresh copy of the golden example and return the validator's messages."""
    _, fn, render = MUTATIONS[name]
    tmp, ws = fresh_workspace()
    try:
        fn(ws)
        if name not in NO_RESTAMP:
            restamp_gates(ws)
        if render:
            rerender(ws)
        return detect(ws)
    finally:
        tmp.cleanup()


def baseline() -> list[str]:
    tmp, ws = fresh_workspace()
    try:
        rerender(ws)
        return detect(ws)
    finally:
        tmp.cleanup()
