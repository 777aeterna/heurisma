#!/usr/bin/env python3
"""Reproducible Level 2 data audit emitting console stats and charts.json v2."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import statistics
from pathlib import Path
from typing import Callable

RAW_CSV = """team,pair_hours,bugs_fixed
T01,2,14
T02,4,12
T03,3,15
T04,5,11
T05,6,13
T06,2,16
T07,7,12
T08,4,14
T09,5,13
T10,3,15
T11,6,11
T12,45,88"""


def median_abs_deviation(vals: list[float]) -> tuple[float, float]:
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals])
    return mad, 1.4826 * mad


def pearson_r(xs: list[float], ys: list[float]) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    return num / den if den else 0.0


def ranks(vals: list[float]) -> list[float]:
    indexed = sorted(enumerate(vals), key=lambda t: t[1])
    out = [0.0] * len(vals)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[indexed[k][0]] = avg_rank
        i = j + 1
    return out


def spearman_rho(xs: list[float], ys: list[float]) -> float:
    return pearson_r(ranks(xs), ranks(ys))


def bootstrap_ci_corr(
    xs: list[float],
    ys: list[float],
    corr_fn: Callable[[list[float], list[float]], float],
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(xs)
    draws = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        draws.append(corr_fn([xs[i] for i in idx], [ys[i] for i in idx]))
    draws.sort()
    return draws[int(0.025 * n_boot)], draws[int(0.975 * n_boot)]


def flag_outliers(vals: list[float]) -> list[int]:
    q1, med, q3 = statistics.quantiles(vals, n=4)
    iqr = q3 - q1
    mean, sd = statistics.fmean(vals), statistics.stdev(vals)
    return [i for i, v in enumerate(vals) if (v < med - 3 * iqr or v > med + 3 * iqr) or abs((v - mean) / sd) > 2.5]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Level 2 pair-programming audit and emit charts.json v2.")
    parser.add_argument("--charts-out", type=Path, default=None, help="Optional path to write charts.json v2.")
    args = parser.parse_args()

    rows = list(csv.DictReader(io.StringIO(RAW_CSV.strip())))
    teams = [r["team"] for r in rows]
    x = [float(r["pair_hours"]) for r in rows]
    y = [float(r["bugs_fixed"]) for r in rows]

    outliers = sorted(set(flag_outliers(x) + flag_outliers(y)))
    x_clean = [v for i, v in enumerate(x) if i not in outliers]
    y_clean = [v for i, v in enumerate(y) if i not in outliers]

    mad_x, madn_x = median_abs_deviation(x)
    mad_y, madn_y = median_abs_deviation(y)
    r_full = pearson_r(x, y)
    rho_full = spearman_rho(x, y)
    r_clean = pearson_r(x_clean, y_clean)
    rho_clean = spearman_rho(x_clean, y_clean)

    ci_r_full = bootstrap_ci_corr(x, y, pearson_r)
    ci_r_clean = bootstrap_ci_corr(x_clean, y_clean, pearson_r)
    ci_rho_clean = bootstrap_ci_corr(x_clean, y_clean, spearman_rho)

    print(f"Integrity: n={len(rows)}, missing=0, flagged_outliers={[teams[i] for i in outliers]}")
    print(f"Robust dispersion (full): pair_hours median={statistics.median(x):.2f} (MAD={mad_x:.2f}, MAD_n={madn_x:.2f}); bugs_fixed median={statistics.median(y):.2f} (MAD={mad_y:.2f}, MAD_n={madn_y:.2f})")
    print(f"Full Sample (n={len(x)}): Pearson r={r_full:.4f} (95% boot CI [{ci_r_full[0]:.4f}, {ci_r_full[1]:.4f}]), Spearman rho={rho_full:.4f}")
    print(f"Clean Sample (n={len(x_clean)}): Pearson r={r_clean:.4f} (95% boot CI [{ci_r_clean[0]:.4f}, {ci_r_clean[1]:.4f}]), Spearman rho={rho_clean:.4f} (95% boot CI [{ci_rho_clean[0]:.4f}, {ci_rho_clean[1]:.4f}])")

    if args.charts_out is not None:
        charts_v2 = [
            {
                "id": "corr_sens",
                "type": "bar",
                "title": "Correlation Sensitivity: Full Sample vs. Outlier-Excluded",
                "caption": "Excluding T12 reverses Pearson r from +0.98 to -0.77, matching the negative rank correlation.",
                "source": "Internal 12-team CSV; computed in appendix/analysis.py.",
                "y": {"label": "Correlation coefficient"},
                "groups": ["Pearson r", "Spearman rho"],
                "series": [
                    {"name": "Full (n=12)", "values": [round(r_full, 4), round(rho_full, 4)]},
                    {"name": "Clean (n=11)", "values": [round(r_clean, 4), round(rho_clean, 4)]},
                ],
            },
            {
                "id": "team_scatter",
                "type": "scatter",
                "title": "Weekly Pair Hours vs. Bugs Fixed Across 12 Teams",
                "caption": "T12 (45 pair hours, 88 bugs) sits >6x above T01-T11 on both axes, driving full-sample OLS leverage.",
                "source": "Internal 12-team CSV; appendix/analysis.py.",
                "x": {"label": "Weekly Pair Hours"},
                "y": {"label": "Bugs Fixed"},
                "series": [
                    {"name": "Typical Teams (T01-T11)", "points": [[x[i], y[i]] for i in range(len(x)) if i not in outliers]},
                    {"name": "Flagged Outlier (T12)", "points": [[x[i], y[i]] for i in outliers]},
                ],
            },
        ]
        args.charts_out.write_text(json.dumps(charts_v2, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
