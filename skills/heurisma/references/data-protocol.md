# Computational & Empirical Data Protocol

Part of **Heurisma** (loaded during **Stage 2 & Stage 3** whenever the prompt includes raw data, local files, CSV/JSON/XLSX tables, time series, or requires quantitative calculation).

## Core Rules

```
1. NEVER REPORT CORRELATIONS, REGRESSIONS, CONFIDENCE INTERVALS, OR SUMMARY STATISTICS WITHOUT EXECUTING A REPRODUCIBLE PYTHON SCRIPT IN APPENDIX/.
2. EMIT CHARTS.JSON (AND OPTIONALLY NUMBERS.JSON) DIRECTLY FROM APPENDIX/ANALYSIS.PY SO FIGURES, TEXT AND OUTPUT.TXT NEVER DRIFT.
3. NEVER PASTE LONG SCRIPTS OR RAW STDOUT DUMPS INTO REPORT.MD — KEEP REPORT.MD CLEAN AND USE {{fig:id}} MARKERS.
4. NEVER CLAIM A "DATA LIMITATION" WITHOUT LOGGING A REAL ONLINE ATTEMPT AND A LOCAL SEARCH, EACH WITH A CONCRETE FAILURE REASON.
5. EVERY FILE IN APPENDIX/DATA/ IS EITHER IN DOWNLOAD_LOG.CSV (DOWNLOADED) OR IN SOURCES.CSV AS FILE:// WITH ITS SHA-256 (LOCAL).
```

Run every script with `python3 -B` so no `__pycache__/` lands in `appendix/` or in the installed skill.

---

## 1. Data Acquisition & Provenance

Walk the **4-rung fallback cascade** from `SKILL.md` Stage 2 for each target series: **(1) online primary → (2) online alternatives → (3) local data → (4) limitation.** Each failed rung is one row in `appendix/data_attempts.csv`.

### §1.A Programmatic Download (`appendix/fetch_data.py`)
Do not rely on undocumented manual `curl` commands that cannot be re-run. Create **`appendix/fetch_data.py`** (Python stdlib `urllib.request`, `hashlib`, `csv`) that:
1. Sends an explicit browser-like `User-Agent` defined **once** as a module constant (many statistical agencies and central banks return `HTTP 403` to Python's default `Python-urllib` header). Do not hard-code a Heurisma version number in it.
2. Saves raw downloaded files into **`appendix/data/`** and appends each file's URL, timestamp, byte size, and SHA-256 to **`appendix/download_log.csv`**.
3. Writes every failed endpoint or missing vintage **directly** to **`appendix/data_attempts.csv`** with the canonical columns below (never to a side file such as `data_attempts_fetch.csv` with different columns).

### §1.B Source Registry (`appendix/sources.csv`) & Data-Attempts Log (`appendix/data_attempts.csv`)
1. Record every used dataset and primary document in **`appendix/sources.csv`**. The `claim_id` column is the id you cite in the text as `[@C1]`; `render_report.py` numbers citations by first appearance and builds the linked **References** section from this file:
   ```csv
   claim_id,source_title,url,tier,accessed_date,data_as_of
   C1,Central Bank Monetary Statistics API v4,https://api.example.org/v4/series,Tier 1,2026-11-20,2026-11
   C2,Wholesale FX series — local copy supplied by the user (local file, sha256 3f9a1c0b7d2e),file:///home/user/datos/a3500.csv,Tier 1,2026-11-20,2026-11
   ```
2. Record every failed rung in **`appendix/data_attempts.csv`** with **exactly** these canonical columns (and summarize them in Section 3):
   ```csv
   target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used
   Wholesale FX,Central Bank API v4,GET /estadisticascambiarias/v1.0/Cotizaciones/USD,HTTP 404,Endpoint retired in 2026 API migration,local:datos/a3500.csv sha256:3f9a1c0b7d2e
   Multilateral REER,Central Bank XLS archive,GET /publicaciones/itcrm.xlsx,HTTP 403,WAF blocks default urllib User-Agent; retried with custom UA,Tier 1 XLSX retrieved on retry
   Alternative CPI 2007–2015,Provincial statistics offices + local inventory,web search + local_data.py inventory,not found,No provincial series online; no local file matched,limitation (tag capped at [Preliminary])
   ```
   **Gates (`validate_report.py`):** `--level 2+` fails if `data_attempts.csv` exists without the canonical columns; `--level 3` fails if a Reviewer #2 critique is `Deferred` / `Diferida` without `data_attempts.csv` or a Section 3 Data Attempts table.

### §1.C Local Data (`<skill-dir>/scripts/local_data.py`)
Use local files when the user supplies them or when online rungs fail. The bundled script is stdlib-only and offline:

```bash
python3 -B <skill-dir>/scripts/local_data.py inventory [dir_or_file ...]   # kind, bytes, mtime, sha256 prefix
python3 -B <skill-dir>/scripts/local_data.py preview datos/a3500.csv        # delimiter, decimal comma, columns, first rows
python3 -B <skill-dir>/scripts/local_data.py preview datos/rem.xlsx --sheet "Cuadros de resultados"
python3 -B <skill-dir>/scripts/local_data.py register appendix/data/a3500.csv \
    --sources appendix/sources.csv --tier "Tier 1" \
    --title "Wholesale FX series — local copy supplied by the user" --claim C2 --as-of 2026-11-19
```

Rules:
1. **Preview before use.** Check delimiter, decimal convention, units, header row, date encoding, and footer notes before any computation.
2. **Copy, don't link.** Copy the file into `appendix/data/`, then `register` the copy. `register` appends a `sources.csv` row with a `file://` URL and the SHA-256 prefix in the title, so the appendix stays self-contained and the validator can check provenance.
3. **Read from `appendix/data/` only.** In `analysis.py`, import the bundled reader instead of writing ad-hoc parsers:
   ```python
   import sys; from pathlib import Path
   sys.path.insert(0, "<skill-dir>/scripts")      # or copy local_data.py into appendix/ for full portability
   from local_data import read_table, excel_date
   rows = read_table(Path("appendix/data/a3500.csv"))   # ';' + decimal comma ('1.234,5' -> 1234.5) + latin-1 handled
   itcrm = read_table(Path("appendix/data/itcrm.xlsx"))  # header row auto-detected; title rows and footer notes dropped
   ```
   Supported: CSV/TSV, XLSX/XLSM (shared strings, inline strings, booleans, sheets by name; Excel serial dates via `excel_date`), JSON (top-level list or `results`/`data`/`rows`/`items`). PDF, legacy XLS, and ODS are listed but must be converted first.
4. **Tier of a local file** = the tier of its declared origin, annotated *"local copy supplied by the user"*. Unknown origin → **Tier 3**: claims resting only on that file may never carry `[Strong]`/`[Fuerte]`.
5. **When local data rescues a failed rung**, write `fallback_used = local:<path> sha256:<hash>` in that rung's `data_attempts.csv` row.

### §1.D Key Numbers (`appendix/numbers.json`, optional)
`analysis.py` may export the figures quoted in the prose as named values:
```json
{"clean_r": "-0.7742", "full_r": "+0.9804", "n_clean": 11}
```
Write `{{num:clean_r}}` in `report.md`; `render_report.py` substitutes it from `appendix/numbers.json` (or `--numbers <file>`). If you do not use placeholders, `validate_report.py --level 2` warns when a number in the Calibrated Verdict does not appear literally in `appendix/output.txt`.

---

## 2. Mandatory Statistical & Chart-Generation Workflow (`appendix/analysis.py`)

1. **Parse, Inspect & Separate Regimes:** Check sample size (n), missing values, duplicate keys, and units. When comparing volatility or means across time (e.g., across administrations or policy eras), **separate distinct structural regimes** (such as fixed pegs/crawling bands vs. floating regimes) in both tables and charts rather than pooling incompatible regimes silently.
2. **Parametric + Robust Dispersion:** Compute **both** parametric (`mean`, `stdev`) and robust non-parametric (`median`, `IQR`, **MAD — Median Absolute Deviation**) statistics.
3. **Outlier & Leverage Audit:** Flag observations beyond median ± 3 × IQR, median ± 3 × MAD / 0.6745, or |z| > 2.5.
4. **Correlation, Lag Regressions & Bootstrap 95% CIs:**
   - Compute both **Pearson r** and **Spearman rank ρ**, plus deterministic **Bootstrap 95% Confidence Intervals** (use block bootstrap for autocorrelated time series).
   - For time-series pass-through or lead-lag hypotheses, run OLS regression with lag terms and trend/regime controls (and state statistical power limits when n < 30).
5. **Direct `charts.json` v2 Emission:**
   - Inside `appendix/analysis.py`, build the `charts.json` payload directly from the computed Python arrays and write it to `charts.json`. Never copy-paste numbers by hand into a separate chart script.
   - Use `"y": {"format": "percent"}` for ratios stored as fractions (0.5 → 50%), `"thousands"` or `"currency"` for large levels; axis labels follow the report language automatically.
6. **Modularization & Appendix Hygiene:**
   - If the analysis exceeds **~300 lines**, split it into clean modular scripts inside `appendix/` (e.g., `01_ingest.py`, `02_regressions.py`, `03_projections.py`) orchestrated by `analysis.py`.
   - Create a short **`appendix/README.md`** (5–10 lines) stating the exact `python3 -B` commands to reproduce `output.txt`, `charts.json`, and `numbers.json`.
   - Remove `__pycache__/`, `.pyc`, empty (`0`-byte) temporary files, and unregistered files in `appendix/data/` before rendering `report.html` (`validate_report.py --level 2` warns on each).

---

## 3. Reference Zero-Dependency Python Template (Fetch + Canonical Attempts Log, MAD, Bootstrap CI & Direct `charts.json` Output)

```python
#!/usr/bin/env python3
"""Zero-dependency fetch + statistical audit template emitting data_attempts.csv, output.txt and charts.json v2."""

from __future__ import annotations

import csv
import hashlib
import math
import random
import statistics
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

APPENDIX = Path(__file__).resolve().parent
DATA_DIR = APPENDIX / "data"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) research-script (+reproducible appendix)"
ATTEMPT_COLS = ["target_series", "source_tried", "query_or_endpoint", "outcome", "failure_reason", "fallback_used"]
DOWNLOAD_COLS = ["file", "url", "retrieved_utc", "bytes", "sha256"]


def _append_csv(path: Path, cols: list[str], row: dict[str, object]) -> None:
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def log_attempt(target: str, source: str, endpoint: str, outcome: str, reason: str, fallback: str = "") -> None:
    """Append one failed rung to the canonical appendix/data_attempts.csv."""
    _append_csv(APPENDIX / "data_attempts.csv", ATTEMPT_COLS, {
        "target_series": target, "source_tried": source, "query_or_endpoint": endpoint,
        "outcome": outcome, "failure_reason": reason, "fallback_used": fallback,
    })


def fetch(target: str, source: str, url: str, filename: str, timeout: int = 20) -> Path | None:
    """Download url into appendix/data/; log success to download_log.csv or failure to data_attempts.csv."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
    except Exception as exc:  # noqa: BLE001 - every failure must be logged, never swallowed
        code = getattr(exc, "code", type(exc).__name__)
        log_attempt(target, source, f"GET {url}", f"HTTP {code}" if isinstance(code, int) else str(code), str(exc))
        return None
    dest = DATA_DIR / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)
    _append_csv(APPENDIX / "download_log.csv", DOWNLOAD_COLS, {
        "file": filename, "url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
    })
    return dest


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
    """Paired bootstrap: resample (x, y) pairs together with a fixed seed for reproducibility."""
    rng = random.Random(seed)
    n = len(xs)
    draws = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        draws.append(corr_fn([xs[i] for i in idx], [ys[i] for i in idx]))
    draws.sort()
    return draws[int(0.025 * n_boot)], draws[int(0.975 * n_boot)]
```
