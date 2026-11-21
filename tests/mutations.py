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
from typing import Callable

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
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", restval="")
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
    _edit(ws, "appendix/sources.csv", "9a7419cd6056", "deadbeef0000")


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
}

# Mutations the validator does not yet catch -> the v0.8.0 phase that will. Remove an entry when its phase lands.
PENDING: dict[str, int] = {
}


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
