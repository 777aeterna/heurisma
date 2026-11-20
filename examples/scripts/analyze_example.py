#!/usr/bin/env python3
"""Reproducible Level 2 data audit script for Heurisma showcase example.

Audits a 12-team internal study comparing weekly pair-programming hours against
bug-fix throughput, testing outlier leverage and parametric vs. rank correlation.
"""

from __future__ import annotations

import csv
import io
import math
import statistics

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


def pearson_r(xs: list[float], ys: list[float]) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    return num / den if den else 0.0


def ols_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((a - mx) ** 2 for a in xs)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    intercept = my - slope * mx
    r = pearson_r(xs, ys)
    return slope, intercept, r * r


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


def flag_outliers(vals: list[float]) -> list[int]:
    q1, med, q3 = statistics.quantiles(vals, n=4)
    iqr = q3 - q1
    mean, sd = statistics.fmean(vals), statistics.stdev(vals)
    return [
        i
        for i, v in enumerate(vals)
        if (v < med - 3 * iqr or v > med + 3 * iqr) or abs((v - mean) / sd) > 2.5
    ]


def main() -> None:
    rows = list(csv.DictReader(io.StringIO(RAW_CSV.strip())))
    teams = [r["team"] for r in rows]
    x = [float(r["pair_hours"]) for r in rows]
    y = [float(r["bugs_fixed"]) for r in rows]

    outliers = sorted(set(flag_outliers(x) + flag_outliers(y)))
    r_full = pearson_r(x, y)
    slope_full, int_full, r2_full = ols_fit(x, y)
    rho_full = spearman_rho(x, y)

    x_clean = [v for i, v in enumerate(x) if i not in outliers]
    y_clean = [v for i, v in enumerate(y) if i not in outliers]
    r_clean = pearson_r(x_clean, y_clean)
    slope_clean, int_clean, r2_clean = ols_fit(x_clean, y_clean)
    rho_clean = spearman_rho(x_clean, y_clean)

    print(f"Integrity: n={len(rows)}, missing=0, flagged_outliers={[teams[i] for i in outliers]}")
    print(
        f"Full Sample (n={len(x)}): Pearson r={r_full:.4f}, R^2={r2_full:.4f}, "
        f"OLS slope={slope_full:.4f}, intercept={int_full:.4f}, Spearman rho={rho_full:.4f}"
    )
    print(
        f"Outlier-Excluded (n={len(x_clean)}): Pearson r={r_clean:.4f}, R^2={r2_clean:.4f}, "
        f"OLS slope={slope_clean:.4f}, intercept={int_clean:.4f}, Spearman rho={rho_clean:.4f}"
    )


if __name__ == "__main__":
    main()
