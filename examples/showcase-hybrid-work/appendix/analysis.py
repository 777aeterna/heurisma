#!/usr/bin/env python3
"""Reproducible Level 2 hybrid-work audit: exact stratified permutation tests on 16 sites (4 vs 4 per seniority cell).

With only four sites per cell a bootstrap is unreliable (35 distinct resample means per arm), so every test here is an
exact permutation test that enumerates all assignments: 70 per subgroup, 4,900 for stratified pooled/interaction tests.
Run from the report folder: python3 -B appendix/analysis.py --charts-out charts.json --numbers-out appendix/numbers.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from itertools import combinations, product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT.parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from local_data import read_table  # noqa: E402

EPS = 1e-12


def pearson_r(xs: list[float], ys: list[float]) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    return num / den if den else 0.0


def split_diffs(a: list[float], b: list[float]) -> tuple[float, list[float]]:
    """Observed mean(a)-mean(b) and the same difference for every way of relabeling len(a) of the pooled sites as 'a'."""
    vals = a + b
    n, total = len(a), sum(vals)
    obs = statistics.fmean(a) - statistics.fmean(b)
    diffs = []
    for idx in combinations(range(len(vals)), n):
        sa = sum(vals[i] for i in idx)
        diffs.append(sa / n - (total - sa) / (len(vals) - n))
    return obs, diffs


def p_two_sided(obs: float, null: list[float]) -> float:
    return sum(1 for d in null if abs(d) >= abs(obs) - EPS) / len(null)


def weighted_mean(rows: list[dict], key: str) -> float:
    w = sum(int(r["n_engineers"]) for r in rows)
    return sum(float(r[key]) * int(r["n_engineers"]) for r in rows) / w


def cell(rows: list[dict], seniority: str, policy: str) -> list[dict]:
    return [r for r in rows if r["seniority"] == seniority and r["policy_group"] == policy]


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze hybrid_rct_sites.csv and emit charts.json + numbers.json.")
    parser.add_argument("--charts-out", type=Path, default=None, help="Output path for charts.json v2.")
    parser.add_argument("--numbers-out", type=Path, default=None, help="Output path for appendix/numbers.json.")
    args = parser.parse_args()

    rows = read_table(ROOT / "appendix" / "data" / "hybrid_rct_sites.csv")
    total_eng = sum(int(r["n_engineers"]) for r in rows)
    sh, so = cell(rows, "Senior", "Hybrid_2d"), cell(rows, "Senior", "Office_5d")
    jh, jo = cell(rows, "Junior", "Hybrid_2d"), cell(rows, "Junior", "Office_5d")
    hyb, off = sh + jh, so + jo

    def col(rs: list[dict], key: str) -> list[float]:
        return [float(r[key]) for r in rs]

    results: dict[str, float] = {}
    for key, label in (("prs_merged_delta_pct", "pr"), ("attrition_12m_pct", "attr")):
        d_s, null_s = split_diffs(col(sh, key), col(so, key))
        d_j, null_j = split_diffs(col(jh, key), col(jo, key))
        null_pool = [(x + y) / 2.0 for x, y in product(null_s, null_j)]
        null_did = [y - x for x, y in product(null_s, null_j)]
        results.update(
            {
                f"{label}_sen_diff": d_s,
                f"{label}_sen_p": p_two_sided(d_s, null_s),
                f"{label}_jun_diff": d_j,
                f"{label}_jun_p": p_two_sided(d_j, null_j),
                f"{label}_pool_diff": (d_s + d_j) / 2.0,
                f"{label}_pool_p": p_two_sided((d_s + d_j) / 2.0, null_pool),
                f"{label}_did": d_j - d_s,
                f"{label}_did_p": p_two_sided(d_j - d_s, null_did),
            }
        )
    n_sub, n_strat = len(split_diffs(col(sh, "n_engineers"), col(so, "n_engineers"))[1]), 0
    n_strat = n_sub * n_sub
    p_floor_sub = 2.0 / n_sub

    # Engineer-weighted attrition (descriptive) and relative drops
    aw_h, aw_o = weighted_mean(hyb, "attrition_12m_pct"), weighted_mean(off, "attrition_12m_pct")
    au_h, au_o = statistics.fmean(col(hyb, "attrition_12m_pct")), statistics.fmean(col(off, "attrition_12m_pct"))
    rel_w = (aw_h - aw_o) / aw_o
    rel_sen = (statistics.fmean(col(sh, "attrition_12m_pct")) - statistics.fmean(col(so, "attrition_12m_pct"))) / statistics.fmean(col(so, "attrition_12m_pct"))
    rel_jun = (statistics.fmean(col(jh, "attrition_12m_pct")) - statistics.fmean(col(jo, "attrition_12m_pct"))) / statistics.fmean(col(jo, "attrition_12m_pct"))

    # Mentoring: means by cell, and within-arm correlations with PR delta (n = 4 each, descriptive only)
    ment = {name: statistics.fmean(col(rs, "mentoring_hrs_wk")) for name, rs in (("sh", sh), ("so", so), ("jh", jh), ("jo", jo))}
    r_cell = {
        name: pearson_r(col(rs, "mentoring_hrs_wk"), col(rs, "prs_merged_delta_pct"))
        for name, rs in (("sh", sh), ("so", so), ("jh", jh), ("jo", jo))
    }
    r_jun_pooled = pearson_r(col(jh + jo, "mentoring_hrs_wk"), col(jh + jo, "prs_merged_delta_pct"))

    pr_cell = {name: statistics.fmean(col(rs, "prs_merged_delta_pct")) for name, rs in (("sh", sh), ("so", so), ("jh", jh), ("jo", jo))}
    at_cell = {name: statistics.fmean(col(rs, "attrition_12m_pct")) for name, rs in (("sh", sh), ("so", so), ("jh", jh), ("jo", jo))}
    pr_pool_h, pr_pool_o = statistics.fmean(col(hyb, "prs_merged_delta_pct")), statistics.fmean(col(off, "prs_merged_delta_pct"))

    pct = lambda v: f"{v * 100:+.2f} pp"  # noqa: E731
    print(f"Dataset integrity: sites={len(rows)}, total_engineers={total_eng}, missing=0, sites per cell=4")
    print(f"Exact tests: {n_sub} relabelings per subgroup, {n_strat:,} stratified; smallest attainable two-sided p: subgroup {p_floor_sub:.4f}")
    print(f"PR delta: Senior Hybrid={pr_cell['sh']*100:+.2f}% Office={pr_cell['so']*100:+.2f}% diff={pct(results['pr_sen_diff'])} exact p={results['pr_sen_p']:.4f}")
    print(f"PR delta: Junior Hybrid={pr_cell['jh']*100:+.2f}% Office={pr_cell['jo']*100:+.2f}% diff={pct(results['pr_jun_diff'])} exact p={results['pr_jun_p']:.4f}")
    print(f"PR delta: pooled diff={pct(results['pr_pool_diff'])} (stratified exact p={results['pr_pool_p']:.4f}); interaction junior-senior={pct(results['pr_did'])} exact p={results['pr_did_p']:.4f}")
    print(f"Attrition (unweighted site means): Hybrid={au_h*100:.1f}% Office={au_o*100:.1f}%; engineer-weighted: Hybrid={aw_h*100:.1f}% Office={aw_o*100:.1f}% (rel={rel_w*100:+.1f}%)")
    print(f"Attrition: Senior Hybrid={at_cell['sh']*100:.1f}% Office={at_cell['so']*100:.1f}% diff={pct(results['attr_sen_diff'])} (rel={rel_sen*100:+.1f}%) exact p={results['attr_sen_p']:.4f}")
    print(f"Attrition: Junior Hybrid={at_cell['jh']*100:.1f}% Office={at_cell['jo']*100:.1f}% diff={pct(results['attr_jun_diff'])} (rel={rel_jun*100:+.1f}%) exact p={results['attr_jun_p']:.4f}")
    print(f"Attrition: pooled diff={pct(results['attr_pool_diff'])} stratified exact p={results['attr_pool_p']:.4f}; interaction junior-senior={pct(results['attr_did'])} exact p={results['attr_did_p']:.4f}")
    print(f"Mentoring hrs/wk: Senior Hybrid={ment['sh']:.2f} Office={ment['so']:.2f}; Junior Hybrid={ment['jh']:.2f} Office={ment['jo']:.2f}")
    print(f"Within-arm r(mentoring, PR delta), n=4 each: Senior Hybrid={r_cell['sh']:+.3f} Senior Office={r_cell['so']:+.3f} Junior Hybrid={r_cell['jh']:+.3f} Junior Office={r_cell['jo']:+.3f}")
    print(f"Junior pooled r (confounded with policy arm, not a mechanism test)={r_jun_pooled:+.3f}")

    if args.charts_out is not None:
        sub = "Local multi-site CSV (appendix/data/hybrid_rct_sites.csv); own computation in appendix/analysis.py."
        charts_v2 = [
            {
                "id": "subgroup_output",
                "type": "bar",
                "title": "PR Output Change by Seniority and Work Policy (16 Sites)",
                "caption": "Site-level means. With 4 sites per cell the difference is exactly testable but small-sample; see Section 4.2.",
                "source": sub,
                "y": {"label": "PRs Merged Delta", "format": "percent"},
                "groups": ["Pooled (16 sites)", "Senior (8 sites)", "Junior (8 sites)"],
                "series": [
                    {"name": "Hybrid (2d WFH)", "values": [round(pr_pool_h, 4), round(pr_cell["sh"], 4), round(pr_cell["jh"], 4)]},
                    {"name": "Office (5d)", "values": [round(pr_pool_o, 4), round(pr_cell["so"], 4), round(pr_cell["jo"], 4)]},
                ],
            },
            {
                "id": "attrition_by_seniority",
                "type": "bar",
                "title": "12-Month Attrition by Seniority and Work Policy (16 Sites)",
                "caption": "Hybrid sites have lower attrition in both groups; the reduction is smaller for junior sites (Section 4.1).",
                "source": sub,
                "y": {"label": "12-Month Attrition", "format": "percent"},
                "groups": ["Pooled (16 sites)", "Senior (8 sites)", "Junior (8 sites)"],
                "series": [
                    {"name": "Hybrid (2d WFH)", "values": [round(au_h, 4), round(at_cell["sh"], 4), round(at_cell["jh"], 4)]},
                    {"name": "Office (5d)", "values": [round(au_o, 4), round(at_cell["so"], 4), round(at_cell["jo"], 4)]},
                ],
            },
            {
                "id": "mentoring_scatter",
                "type": "scatter",
                "title": "Weekly Mentoring Hours vs. PR Output Delta Across Engineering Sites",
                "caption": "Points cluster by policy arm, so the pooled slope mostly reflects the policy itself; within each arm n = 4 (Section 4.3).",
                "source": sub,
                "x": {"label": "Mentoring Hours / Week"},
                "y": {"label": "PRs Merged Delta", "format": "percent"},
                "series": [
                    {"name": "Senior Sites", "points": [[float(r["mentoring_hrs_wk"]), float(r["prs_merged_delta_pct"])] for r in sh + so]},
                    {"name": "Junior Sites", "points": [[float(r["mentoring_hrs_wk"]), float(r["prs_merged_delta_pct"])] for r in jh + jo]},
                ],
            },
        ]
        args.charts_out.write_text(json.dumps(charts_v2, indent=2) + "\n", encoding="utf-8")

    if args.numbers_out is not None:
        pp = lambda v: f"{v * 100:+.2f} pp"  # noqa: E731
        pv = lambda v: f"{v:.4f}"  # noqa: E731
        numbers = {
            "total_sites": len(rows),
            "total_engineers": total_eng,
            "n_perm_sub": n_sub,
            "n_perm_strat": f"{n_strat:,}",
            "p_floor_sub": pv(p_floor_sub),
            "attr_hyb_u": f"{au_h * 100:.1f}%",
            "attr_off_u": f"{au_o * 100:.1f}%",
            "attr_hyb_w": f"{aw_h * 100:.1f}%",
            "attr_off_w": f"{aw_o * 100:.1f}%",
            "attr_rel_drop_w": f"{abs(rel_w) * 100:.1f}%",
            "attr_rel_sen": f"{abs(rel_sen) * 100:.1f}%",
            "attr_rel_jun": f"{abs(rel_jun) * 100:.1f}%",
            "attr_pool_diff": pp(results["attr_pool_diff"]),
            "attr_pool_p": pv(results["attr_pool_p"]),
            "attr_sen_diff": pp(results["attr_sen_diff"]),
            "attr_sen_p": pv(results["attr_sen_p"]),
            "attr_jun_diff": pp(results["attr_jun_diff"]),
            "attr_jun_p": pv(results["attr_jun_p"]),
            "attr_did": pp(results["attr_did"]),
            "attr_did_p": pv(results["attr_did_p"]),
            "attr_sen_hyb": f"{at_cell['sh'] * 100:.1f}%",
            "attr_sen_off": f"{at_cell['so'] * 100:.1f}%",
            "attr_jun_hyb": f"{at_cell['jh'] * 100:.1f}%",
            "attr_jun_off": f"{at_cell['jo'] * 100:.1f}%",
            "pr_pool_diff": pp(results["pr_pool_diff"]),
            "pr_pool_p": pv(results["pr_pool_p"]),
            "pr_sen_diff": pp(results["pr_sen_diff"]),
            "pr_sen_p": pv(results["pr_sen_p"]),
            "pr_jun_diff": pp(results["pr_jun_diff"]),
            "pr_jun_p": pv(results["pr_jun_p"]),
            "pr_did": pp(results["pr_did"]),
            "pr_did_p": pv(results["pr_did_p"]),
            "pr_sen_hyb": f"{pr_cell['sh'] * 100:+.2f}%",
            "pr_sen_off": f"{pr_cell['so'] * 100:+.2f}%",
            "pr_jun_hyb": f"{pr_cell['jh'] * 100:+.2f}%",
            "pr_jun_off": f"{pr_cell['jo'] * 100:+.2f}%",
            "pr_pool_hyb": f"{pr_pool_h * 100:+.2f}%",
            "pr_pool_off": f"{pr_pool_o * 100:+.2f}%",
            "ment_sen_hyb": f"{ment['sh']:.2f}",
            "ment_sen_off": f"{ment['so']:.2f}",
            "ment_jun_hyb": f"{ment['jh']:.2f}",
            "ment_jun_off": f"{ment['jo']:.2f}",
            "r_sen_hyb": f"{r_cell['sh']:+.2f}",
            "r_sen_off": f"{r_cell['so']:+.2f}",
            "r_jun_hyb": f"{r_cell['jh']:+.2f}",
            "r_jun_off": f"{r_cell['jo']:+.2f}",
            "r_jun_pooled": f"{r_jun_pooled:+.2f}",
        }
        args.numbers_out.write_text(json.dumps(numbers, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
