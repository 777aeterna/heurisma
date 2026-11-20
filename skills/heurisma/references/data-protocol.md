# Computational & Empirical Data Protocol

Part of **Heurisma** (loaded during **Stage 3** whenever the prompt includes raw data, CSV/JSON/tables, or requires quantitative calculation).

## Core Rule

```
NEVER REPORT CORRELATIONS, REGRESSIONS, P-VALUES, OR SUMMARY STATISTICS FROM RAW DATA WITHOUT EXECUTING A REPRODUCIBLE PYTHON SCRIPT IN THIS SESSION.
```

Mental math, eyeballing tables, or quoting plausible numbers without running code is a direct protocol violation.

---

## 1. Mandatory 5-Step Data Audit Workflow

Whenever data is provided (inline CSV, markdown table, file path, or fetched dataset):

### Step 1: Parse & Inspect Integrity
Write a Python script (using standard library `csv`, `math`, `statistics` or `numpy`/`scipy`/`pandas` if installed) that checks:
- Row count ($n$), column types, missing/null values, duplicate IDs, and unit consistency.
- Range (min, max), mean vs. median, and standard deviation vs. interquartile range (IQR).

### Step 2: Outlier & Leverage Audit
Before trusting any parametric statistic (mean, OLS slope, Pearson $r$):
- Flag observations exceeding $\text{median} \pm 3 \times \text{IQR}$ or $|z| > 2.5$.
- Check whether a single data point accounts for a large shift in slope or correlation (**leverage point**).

### Step 3: Parametric vs. Non-Parametric & Sensitivity Comparison
Always compute and compare **both**:
1. **Full-sample parametric:** Pearson $r$, OLS linear regression slope, $R^2$.
2. **Rank / Non-parametric:** Spearman rank correlation $\rho$.
3. **Leave-Out Sensitivity (if outliers exist):** Re-compute Pearson $r$, Spearman $\rho$, and slope after excluding flagged outlier(s).
   - *Classic Diagnostic:* If full-sample Pearson $r$ is strongly positive (e.g., $r > 0.8$) while Spearman $\rho$ or outlier-excluded Pearson $r$ is zero or negative, **the positive trend is an outlier artifact**. State this prominently in `## 1. Executive Summary`.

### Step 4: Causal & Confounder Audit
Even when a correlation survives outlier removal:
- Check for **reverse causality** (e.g., do complex bugs cause more pair programming rather than pair programming causing fewer bug fixes?).
- Check for **denominator / scale omission** (e.g., raw totals not normalized per headcount, time window, or severity).
- Check for **multiple testing / $p$-hacking** when scanning many variables on small $n$.

### Step 5: Embed Reproducible Provenance in the Report
In `## 3. Methodology & Evidence Standards` (or `## 4. Findings`), include:
1. The exact runnable Python snippet (or path to the executed script in the workspace).
2. A concise summary table of the exact computed metrics (Full Sample vs. Outlier-Excluded / Non-Parametric).

---

## 2. Reference Zero-Dependency Python Template

Use or adapt this self-contained Python 3 stdlib template so analysis works in any sandbox even when `scipy` or `pandas` is not installed:

```python
import csv
import io
import math
import statistics

RAW_CSV = """team,pair_hours,bugs_fixed
T01,2,14
T02,4,12
"""  # Replace with actual dataset

rows = list(csv.DictReader(io.StringIO(RAW_CSV.strip())))
x = [float(r["pair_hours"]) for r in rows]
y = [float(r["bugs_fixed"]) for r in rows]


def pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
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


def iqr_outliers(vals: list[float]) -> list[int]:
    q1, _, q3 = statistics.quantiles(vals, n=4)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return [i for i, v in enumerate(vals) if v < low or v > high]


outliers = sorted(set(iqr_outliers(x) + iqr_outliers(y)))
print(f"n={len(x)}, full Pearson r={pearson_r(x, y):.4f}, full Spearman rho={spearman_rho(x, y):.4f}")
print(f"IQR outlier indices: {outliers}")
if outliers:
    x_clean = [v for i, v in enumerate(x) if i not in outliers]
    y_clean = [v for i, v in enumerate(y) if i not in outliers]
    print(
        f"Clean (n={len(x_clean)}): Pearson r={pearson_r(x_clean, y_clean):.4f}, "
        f"Spearman rho={spearman_rho(x_clean, y_clean):.4f}"
    )
```
