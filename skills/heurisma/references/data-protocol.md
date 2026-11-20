# Computational & Empirical Data Protocol

Part of **Heurisma** (loaded during **Stage 3** whenever the prompt includes raw data, CSV/JSON/tables, time series, or requires quantitative calculation).

## Core Rules

```
1. NEVER REPORT CORRELATIONS, REGRESSIONS, CONFIDENCE INTERVALS, OR SUMMARY STATISTICS WITHOUT EXECUTING A REPRODUCIBLE PYTHON SCRIPT IN APPENDIX/.
2. EMIt CHARTS.JSON DIRECTLY FROM APPENDIX/ANALYSIS.PY SO FIGURES AND OUTPUT.TXT NEVER DRIFT.
3. NEVER PASTE LONG SCRIPTS OR RAW STDOUT DUMPS INTO REPORT.MD — KEEP REPORT.MD CLEAN AND USE {{fig:id}} MARKERS.
4. NEVER CLAIM A "DATA LIMITATION" WITHOUT LOGGING A REAL SEARCH/API ATTEMPT AND CONCRETE FAILURE REASON.
```

---

## 1. Reproducible Data Ingestion (`appendix/fetch_data.py`) & Provenance

When fetching external datasets, APIs, or downloadable tables (Level 2+):

### Step A: Programmatic Download (`appendix/fetch_data.py`)
Do not rely on undocumented manual `curl` commands that cannot be re-run. Create **`appendix/fetch_data.py`** (using Python stdlib `urllib.request`, `hashlib`, `csv`) that:
1. Sends an explicit browser/institutional `User-Agent` header (many statistical agencies and central banks return `HTTP 403` to Python's default `Python-urllib` header).
2. Saves raw downloaded files into **`appendix/data/`** and logs each file's URL, timestamp, byte size, and SHA-256 prefix.
3. Appends every failed endpoint or missing vintage directly to **`appendix/data_attempts.csv`** with its exact HTTP code or exception.

### Step B: Source Registry (`appendix/sources.csv`) & Data-Attempts Log (`appendix/data_attempts.csv`)
1. Record every used dataset and primary document in **`appendix/sources.csv`** (`render_report.py` uses this file to auto-generate the numbered **References** section in `report.html`):
   ```csv
   claim_id,source_title,url,tier,accessed_date,data_as_of
   C1,Central Bank Monetary Statistics API v4,https://api.example.org/v4/series,Tier 1,2026-11-20,2026-11
   ```
2. Record every failed or unavailable primary source in **`appendix/data_attempts.csv`** (and summarize in Section 3):
   ```csv
   target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used
   Multilateral REER,Central Bank XLS archive,GET /publicaciones/itcrm.xlsx,HTTP 403,WAF blocks default urllib User-Agent; retried with custom UA,Tier 1 XLS retrieved on retry
   ```
   **Gate:** `validate_report.py --level 3` fails if any Reviewer #2 critique is marked `Deferred` / `Diferida` without an `appendix/data_attempts.csv` file or Section 3 Data Attempts table.

---

## 2. Mandatory Statistical & Chart-Generation Workflow (`appendix/analysis.py`)

1. **Parse, Inspect & Separate Regimes:** Check sample size ($n$), missing values, duplicate keys, and units. When comparing volatility or means across time (e.g., across administrations or policy eras), **separate distinct structural regimes** (such as fixed pegs/crawling bands vs. floating regimes) in both tables and charts rather than pooling incompatible regimes silently.
2. **Parametric + Robust Dispersion:** Compute **both** parametric (`mean`, `stdev`) and robust non-parametric (`median`, `IQR`, **MAD — Median Absolute Deviation**) statistics.
3. **Outlier & Leverage Audit:** Flag observations exceeding $\text{median} \pm 3 \times \text{IQR}$, $\text{median} \pm 3 \times \text{MAD}/0.6745$, or $|z| > 2.5$.
4. **Correlation, Lag Regressions & Bootstrap 95% CIs:**
   - Compute both **Pearson $r$** and **Spearman rank $\rho$**, plus deterministic **Bootstrap 95% Confidence Intervals** (use block bootstrap for autocorrelated time series).
   - For time-series pass-through or lead-lag hypotheses, run OLS regression with lag terms and trend/regime controls (and state statistical power limits when $n < 30$).
5. **Direct `charts.json` v2 Emission:**
   - Inside `appendix/analysis.py`, build the `charts.json` payload directly from the computed Python arrays and write it to `charts.json`. Never copy-paste numbers by hand into a separate chart script.
6. **Modularization & Appendix Hygiene:**
   - If the analysis exceeds **~300 lines**, split it into clean modular scripts inside `appendix/` (e.g., `01_ingest.py`, `02_regressions.py`, `03_projections.py`) orchestrated by `analysis.py`.
   - Create a short **`appendix/README.md`** (5–10 lines) stating the exact commands to reproduce `output.txt` and `charts.json`.
   - Remove `__pycache__/`, `.pyc`, and any empty (`0`-byte) temporary files before rendering `report.html`.

---

## 3. Reference Zero-Dependency Python Template (with Fetch, MAD, Bootstrap CI & Direct `charts.json` Output)

```python
#!/usr/bin/env python3
"""Zero-dependency statistical audit template emitting output.txt and charts.json v2."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import statistics
import urllib.request
from pathlib import Path
from typing import Callable


def fetch_with_ua(url: str, dest: Path, timeout: int = 20) -> tuple[bool, str]:
    """Download url to dest with a standard User-Agent and return (ok, sha256_12_or_err)."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; HeurismaResearch/0.3)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True, hashlib.sha256(data).hexdigest()[:12]
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def median_abs_deviation(vals: list[float]) -> tuple[float, float]:
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals])
    return mad, 1.4826 * mad


def pearson_r(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
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
    corr_fn: Callable[[list[float], list[float]], float] = pearson_r,
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(xs)
    draws = sorted(
        corr_fn([xs[i] for i in (rng.randrange(n) for _ in range(n))],
                [ys[i] for i in (rng.randrange(n) for _ in range(n))])
        for _ in range(n_boot)
    )
    return draws[int(0.025 * n_boot)], draws[int(0.975 * n_boot)]
```
