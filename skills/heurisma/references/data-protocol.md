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

Walk the **4-rung fallback cascade** from `SKILL.md` Stage 2 for each target series: **(1) online primary → (2) online alternatives → (3) local data → (4) limitation.** Each failed rung is one row in `appendix/data_attempts.csv`, stamped with the UTC time it ran (`attempted_utc`).

**Attempts from an earlier run do not count.** A `data_attempts.csv`, `report.md` or `appendix/` copied or inherited from a previous run (yours or someone else's) records what failed *then*. Before any of its failures supports a limitation, a `Deferred` critique or a tag downgrade in this report, re-run that rung now and log the new row with today's `attempted_utc`. Keep the old rows only as history. `validate_report.py` treats a failure whose `target_series` has no attempt dated on or after the run start (`--run-since`, default: the first ISO date in the report header) as **inherited**: error at Level 3, warning at Level 2.

**Before declaring that a series does not exist**, search the provider's **whole** catalogue — every page of a paginated variable list, not the first page — with at least three keywords for the concept, including the institutional names (for an exchange-rate band: `banda`, `techo`, `piso`, `límite`, `band`, `ceiling`, `floor`), and check the provider's statistics/publications section. Log each search as its own row with the keywords in `query_or_endpoint`.

### §1.A Programmatic Download (`appendix/fetch_data.py`)
Do not rely on undocumented manual `curl` commands that cannot be re-run. Create **`appendix/fetch_data.py`** (Python stdlib `urllib.request`, `hashlib`, `csv`) that:
1. Sends an explicit browser-like `User-Agent` defined **once** as a module constant (many statistical agencies and central banks return `HTTP 403` to Python's default `Python-urllib` header). Do not hard-code a Heurisma version number in it.
2. Saves raw downloaded files into **`appendix/data/`** and appends each file's URL, timestamp, byte size, and SHA-256 to **`appendix/download_log.csv`**.
3. Writes every failed endpoint or missing vintage **directly** to **`appendix/data_attempts.csv`** with the canonical columns below (never to a side file such as `data_attempts_fetch.csv` with different columns).
4. Honors **`HEURISMA_OFFLINE=1`**: when it is set, skip every request and log the rung as `outcome = offline mode` (see `fetch()` in the template), so the run must fall through to the local-data rung. Use it to rehearse rung 3 before relying on it.

### §1.B Source Registry (`appendix/sources.csv`) & Data-Attempts Log (`appendix/data_attempts.csv`)
1. Record every used dataset and primary document in **`appendix/sources.csv`**. The `claim_id` column is the id you cite in the text as `[@C1]`; `render_report.py` numbers citations by first appearance and builds the linked **References** section from this file:
   ```csv
   claim_id,source_title,url,tier,accessed_date,data_as_of,kind
   C1,Central Bank Monetary Statistics API v4,https://api.example.org/v4/series,Tier 1,2026-11-20,2026-11,data
   C2,Calvo & Reinhart 2002 — Fear of Floating (abstract only),https://doi.org/10.1162/003355302753650274,Tier 1,2026-11-20,2002,literature
   C3,Own Monte Carlo mixture (appendix/analysis.py),appendix/analysis.py,Tier 2,2026-11-20,2026-11,own-computation
   L1,Wholesale FX series — copy supplied by the user (local file, sha256 3f9a1c0b7d2e),appendix/data/a3500.csv,Tier 1,2026-11-20,2026-11,data
   ```
   **`kind` (required on every row; the validator errors on a missing or unknown value):** `data`, `literature`, `press`, or `own-computation`.
   **Local files:** `local_data.py import`/`register` also write a `sha256` column (12-hex prefix). `validate_report.py` **recomputes** the SHA-256 of every local file and of every file in `download_log.csv`; a file edited after it was registered is an error (`changed since it was registered`), so re-import instead of editing `appendix/data/` in place.
   - A row for the report's own code or output is `own-computation`, **Tier 2 at most**: it checks a derivation or a numerical result, it is never independent evidence about the world, and it cannot carry a `[Strong]` claim about the world on its own (`validate_report.py` errors on `own-computation` + Tier 1 and warns at Level 3 when a `[Strong]` row cites only own computations).
   - The title records what was actually read: `(abstract only)` when the full text was not retrievable. A row titled "full text"/"open access" with a failed attempt for the same URL in `data_attempts.csv` triggers a validator warning.
2. Record every failed rung in **`appendix/data_attempts.csv`** with **exactly** these canonical columns (and summarize them in Section 3):
   ```csv
   target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used,attempted_utc
   Wholesale FX,Central Bank API v4,GET /estadisticascambiarias/v1.0/Cotizaciones/USD,HTTP 404,Endpoint retired in 2026 API migration,local:appendix/data/a3500.csv sha256:3f9a1c0b7d2e,2026-11-20T14:02:11Z
   Multilateral REER,Central Bank XLS archive,GET /publicaciones/itcrm.xlsx,HTTP 403,WAF blocks default urllib User-Agent; retried with custom UA,Tier 1 XLSX retrieved on retry,2026-11-20T14:02:40Z
   Alternative CPI 2007–2015,Provincial statistics offices + local inventory,web search + local_data.py inventory,not found,No provincial series online; no local file matched,limitation (tag capped at [Preliminary]),2026-11-20T14:05:03Z
   ```
   The first six columns are required; `attempted_utc` (full ISO 8601 UTC, e.g. `2026-11-20T14:02:11Z`) is required for every row this run writes. A bare date (`YYYY-MM-DD`) is accepted only in reconstructed historical records (such as repository examples where exact times were not logged); tools always stamp full ISO UTC. **Never type a row or its date by hand:** `fetch_lib.fetch` (inside `fetch_data.py`), `local_data.py import`, and `local_data.py attempt` (for web searches, catalogue browsing, or a local inventory done outside `fetch_data.py`) stamp it with the real UTC time:
   ```bash
   python3 -B <skill-dir>/scripts/local_data.py attempt --csv appendix/data_attempts.csv --target "Exchange-rate band (daily)" \
       --source "BCRA API v4 catalogue (all pages)" --query "keywords: banda; techo; piso; band; ceiling; floor" \
       --outcome "not found" --failure-reason "no matching variable" --fallback "limitation"
   ```
   A file without the `attempted_utc` column is treated as entirely inherited (error at Level 3, warning at Level 2), and only failures that end in a limitation (empty `fallback_used` or `limitation …`) or that Section 7 / a `Deferred` row leans on are checked.
   **Gates (`validate_report.py`):** `--level 2+` fails if `data_attempts.csv` exists without the canonical columns; `--level 3` fails if a Reviewer #2 critique is `Deferred` / `Diferida` without `data_attempts.csv` or a Section 3 Data Attempts table, and if a failure is only backed by inherited rows (see above).

   With `HEURISMA_OFFLINE=1`, an online rung is logged as `outcome = offline mode` and the rescuing local row reads `fallback_used = local:appendix/data/a3500.csv sha256:3f9a1c0b7d2e`.

   **Offline acceptance check (rung 3).** Before trusting the local rung in a real run, rehearse it once:
   ```bash
   mkdir -p datos && cp <your-file>.csv datos/
   HEURISMA_OFFLINE=1 python3 -B appendix/fetch_data.py          # every online rung logged as "offline mode"
   python3 -B <skill-dir>/scripts/local_data.py import datos/<your-file>.csv --into appendix/data \
       --sources appendix/sources.csv --tier "Tier 3" --title "<what the file is>"
   python3 -B appendix/analysis.py && python3 -B <skill-dir>/scripts/render_report.py report.md --out report.html --charts charts.json --appendix appendix/
   python3 -B <skill-dir>/scripts/validate_report.py report.md --level 2 --html report.html --strict
   ```
   Pass = the report cites the `L<n>` row, `data_attempts.csv` holds the `offline mode` rows **and** a row with `fallback_used = local:appendix/data/<file> sha256:<hash>`, and the validator passes.

### §1.C Local Data (`<skill-dir>/scripts/local_data.py`)
Use local files when the user supplies them or when online rungs fail. The bundled script is stdlib-only and offline:

```bash
python3 -B <skill-dir>/scripts/local_data.py inventory [dir_or_file ...]   # kind, bytes, mtime, sha256 prefix
python3 -B <skill-dir>/scripts/local_data.py preview datos/a3500.csv        # delimiter, decimal comma, columns, first rows
python3 -B <skill-dir>/scripts/local_data.py preview datos/rem.xlsx --sheet "Cuadros de resultados"
python3 -B <skill-dir>/scripts/local_data.py import datos/a3500.csv \
    --into appendix/data --sources appendix/sources.csv --tier "Tier 1" \
    --title "Wholesale FX series — copy supplied by the user" --as-of 2026-11-19 --lang en
```

`import` does the whole rung in one step: it copies the file into `appendix/data/` (refusing to overwrite a different file with the same name), registers the **copy** in `sources.csv` with the next free id (`L1`, `L2`, …), a project-relative path (`appendix/data/…`, no `file://` scheme) and its SHA-256, and appends the `data_attempts.csv` row with `fallback_used = local:<path> sha256:<hash>`. Re-running it adds nothing. `register` (same flags plus `--claim`) only appends the `sources.csv` row, for a file already inside `appendix/data/`; a file outside the report folder is stored as an absolute `file:///…` URI, so prefer `import`. `--lang es` writes the title suffix in Spanish (`archivo local`).

**Whole folders (pre-flight intake, `SKILL.md` Stage 0 step 9):** `local_data.py intake <folder> --channel data|sources --selection user-curated|agent-fetched [--wishlist wishlist.txt] [--tier …] [--retrieved-utc …]` runs `preview` + `import` on every file, rejects ambiguous CSVs instead of guessing, copies documents to `appendix/corpus/` (`kind=literature`), and merges a `## Channel: <data|sources>` section idempotently into `appendix/intake.md` (running `--channel data` and `--channel sources` sequentially preserves both channels). Every `sources.csv` row it writes carries:
- `selection`: `user-curated` (the user chose it), `agent-fetched` (you found it), or `third-party`;
- `retrieved_utc`: when the file was obtained from its origin, or `unknown`. A local `user-curated` row with `unknown` stays **Tier 3**, and even with a dated `--retrieved-utc` a local `user-curated` file is capped at **Tier 2** (never `Tier 1` without a live online download in `download_log.csv`). Hashes recorded as `user-curated` in `appendix/intake.md` cannot be relabelled `agent-fetched` in `sources.csv`, every `agent-fetched` row requires `retrieved_utc >= run_started_utc` plus proof in `download_log.csv` or `data_attempts.csv`, and counter-evidence outside a user-curated corpus must include at least one `agent-fetched` **Tier 1 or Tier 2** (`data` or `literature`) source.

A wish-list line is `name: keyword, keyword`; a name that no accepted file or column matches is reported as a gap.

Rules:
1. **Preview before use.** Check delimiter, decimal convention, units, header row, date encoding, and footer notes before any computation.
2. **Copy, don't link.** Use `import` so the appendix holds the copy and `sources.csv` points at it with a relative URL — never at the user's absolute path (absolute paths leak the user's home directory into the report; the renderer shows only the file name and hash).
3. **Read from `appendix/data/` only.** In `analysis.py`, import the bundled reader instead of writing ad-hoc parsers:
   ```python
   import sys; from pathlib import Path
   sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling helpers (e.g. common.py) import under any cwd
   sys.path.insert(0, "<skill-dir>/scripts")      # or copy local_data.py into appendix/ for full portability
   from local_data import read_table, excel_date, worst_tier
   rows = read_table(Path("appendix/data/a3500.csv"))   # ';' + decimal comma ('1.234,5' -> 1234.5) + latin-1 handled
   itcrm = read_table(Path("appendix/data/itcrm.xlsx"))  # header row auto-detected; title rows and footer notes dropped
   ```
   **CSV decimals and missing-value sentinels are decided per column.** `read_table` ignores `NA_SENTINELS` (`""`, `"na"`, `"n/a"`, `"null"`, `"none"`, `"nan"`, `"—"`, `"-"`) when inferring a column's numeric format and converts sentinel cells to `None` in numeric columns (so a numeric column with `NA` cells is never downgraded to strings). Each column is read as decimal-comma or decimal-point from its own non-sentinel cells (`3.1416` and `12,34` can sit in one file); a column that mixes the two raises `ValueError` with the first conflicting cells instead of guessing, and mostly-text columns and zero-padded identifiers (`00123`) stay text. Force text with `read_table(path, keep_strings=["zip"])` (CLI: `preview --keep-strings zip`). Run `local_data.py preview` first: it prints the detected format per column and `raw -> converted` for each cell that changes.
   Supported: CSV/TSV, XLSX/XLSM (shared strings, inline strings, booleans, sheets by name; Excel serial dates via `excel_date`), JSON (top-level list or `results`/`data`/`rows`/`items`). PDF, legacy XLS, and ODS are listed but must be converted first.
4. **Tier of a local file & mixed-source tables (`worst_tier`).** A local user-supplied file with documented institutional origin and retrieval date is **Tier 2 at most** (annotated *"local copy supplied by the user"*); unknown origin → **Tier 3**, and claims resting only on that file may never carry `[Strong]`/`[Fuerte]`. When a table or composite series combines rows from multiple sources (tracked by a `primary_source_id` or `source_id` column), call `worst_tier(rows, source_col="primary_source_id", meta_csv=Path("appendix/sources.csv"))` so the table and its Claim-Evidence Matrix row inherit the weakest contributing tier (`Tier 3` > `Tier 2` > `Tier 1`).
5. **When local data rescues a failed rung**, write `fallback_used = local:<path> sha256:<hash>` in that rung's `data_attempts.csv` row.

### §1.D Key Numbers (`appendix/numbers.json`) & Numeric Closure (`P1-UNTRACED-NUM`)
`analysis.py` exports **every figure the prose or Section 4 tables quote from `output.txt`** — the Calibrated Verdict, Section 1 and all Section 4 statistical cells — as named values:
```json
{"clean_r": "-0.7742", "full_r": "+0.9804", "n_clean": 11}
```
Write `{{num:clean_r}}` in `report.md`; `render_report.py` substitutes it from `appendix/numbers.json` (or `--numbers <file>`).
- **Numeric closure (`P1-UNTRACED-NUM`):** every statistical number in a Section 4 table cell (means, medians, p-values, correlations, percentages, rates, capacity figures) must appear in `appendix/output.txt` or `appendix/numbers.json`. Any hand-typed statistic in a Section 4 table absent from both is flagged by `validate_report.py` (warning at Level 2, error at Level 3). Never type ad-hoc calculations in prose or copy numbers from Reviewer #2 notes into a Section 4 table without computing them in `analysis.py`.
- `validate_report.py --level 2` also warns when five or more Section 4 numbers that appear in `output.txt` are typed by hand and fewer than 30 % of the figures use `{{num:key}}`; without any placeholder it warns when a Calibrated Verdict number is missing from `output.txt`.

---

## 2. Mandatory Statistical & Chart-Generation Workflow (`appendix/analysis.py`)

1. **Parse, Inspect & Separate Regimes:** Check sample size (n), missing values, duplicate keys, and units. When comparing volatility or means across time (e.g., across administrations or policy eras), **separate distinct structural regimes** (such as fixed pegs/crawling bands vs. floating regimes) in both tables and charts rather than pooling incompatible regimes silently.
2. **Parametric + Robust Dispersion:** Compute **both** parametric (`mean`, `stdev`) and robust non-parametric (`median`, `IQR`, **MAD — Median Absolute Deviation**) statistics.
3. **Outlier & Leverage Audit:** Flag observations beyond median ± 3 × IQR, median ± 3 × MAD / 0.6745, or |z| > 2.5.
4. **Correlation, Partial Correlation, Stratified Permutation & Bootstrap 95% CIs** (small-sample cautions below):
   - Compute both **Pearson r** and **Spearman rank ρ**, plus deterministic **Bootstrap 95% Confidence Intervals** (use block bootstrap for autocorrelated time series).
   - **Control for secular trend and seasonal/regime confounders:** when two trending time series or seasonal panels are correlated, report the **partial correlation controlling for time trend** (`partial_corr_trend(x, y, t)`) alongside the raw correlation, and permute **within strata** (e.g. season, policy regime, or seniority cell via `stratified_perm_pvalue`) rather than pooling incompatible strata into an unstratified permutation test.
   - For time-series pass-through or lead-lag hypotheses, run OLS regression with lag terms and trend/regime controls (and state statistical power limits when n < 30).
   **Small-sample cautions (state them in Section 4 when they apply):**
   - **n < 30:** a percentile bootstrap is unstable and understates the width of the interval (with 4 units per arm it is meaningless). Prefer an **exact or stratified permutation test**, or BCa intervals, and say how few units there are.
   - **Effect size, not only p:** report the magnitude (difference, ratio or r) with its units next to every p-value; a tiny p on a tiny effect, or a large effect with p = 0.2, are different findings.
   - **Multiple comparisons:** when several subgroups or outcomes are tested, say how many and apply a correction (Holm or Bonferroni) or label the extra tests exploratory; if every p sits at the exact-test floor, say that no correction can lower it.
   - **Decisions inside the noise:** a threshold crossed by less than the Monte Carlo or seed interval is "not distinguishable", not a result.
5. **Direct `charts.json` v2 Emission:**
   - Inside `appendix/analysis.py`, build the `charts.json` payload directly from the computed Python arrays and write it with `json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=1)`: a NaN or Infinity then fails loudly in the script instead of producing a figure with nonsense coordinates. `validate_report.py` checks every chart against the schema (unknown or misspelled keys, strings or non-finite numbers, group/value length mismatches, invalid dates, observed `"line"` chart points dated after the report `As-Of Date` when `x.observed_until` is unset, unordered fan quantiles, and `"fan"` quantiles that fail to converge at the `x.observed_until` anchor). Never copy-paste numbers by hand into a separate chart script.
   - Use `"y": {"format": "percent"}` for ratios stored as fractions (0.5 → 50%), `"thousands"` or `"currency"` for large levels; axis labels follow the report language automatically.
6. **Modularization & Appendix Hygiene:**
   - If the analysis exceeds **~300 lines**, split it into clean modular scripts inside `appendix/` (e.g., `01_ingest.py`, `02_regressions.py`, `03_projections.py`) orchestrated by `analysis.py`.
   - Create a short **`appendix/README.md`** (5–10 lines) stating the exact commands, run from the report folder, that reproduce `output.txt`, `charts.json`, and `numbers.json` (e.g. `python3 -B appendix/analysis.py > appendix/output.txt`), and **where each data file came from**: "downloaded by `fetch_data.py` in this folder" versus "copied from `datos/` or from an earlier run (listed in `sources.csv` as `L<n>`)". Never write that `fetch_data.py` produced files it did not download in this run. Do not document `python3 -I`: isolated mode drops the script folder from `sys.path`, so sibling imports fail unless `analysis.py` inserts its own folder as shown in §1.C.
   - Remove `__pycache__/`, `.pyc`, empty (`0`-byte) temporary files, and unregistered files in `appendix/data/` before rendering `report.html` (`validate_report.py --level 2` warns on each).

---

## 3. Reference Zero-Dependency Python Template (Fetch + Canonical Attempts Log, MAD, Bootstrap CI & Direct `charts.json` Output)

```python
#!/usr/bin/env python3
"""Zero-dependency fetch + statistical audit template emitting data_attempts.csv, output.txt and charts.json v2."""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Callable

APPENDIX = Path(__file__).resolve().parent
sys.path.insert(0, "<skill-dir>/scripts")  # or copy fetch_lib.py and local_data.py next to this script
from fetch_lib import fetch  # noqa: E402  retries + backoff, UA, checksum, download_log.csv, dated attempts log

# Downloading: one call per file. On success it writes appendix/data/<file> and a download_log.csv row with its
# SHA-256; on failure (or with HEURISMA_OFFLINE=1) it returns None after logging a dated data_attempts.csv row.
#   fetch("Wholesale FX", "Central Bank API v4", "https://api.example.org/v4/series.csv", "series.csv", APPENDIX)
# Searches done outside this script (web search, catalogue browsing, local inventory) are logged with:
#   python3 -B <skill-dir>/scripts/local_data.py attempt --csv appendix/data_attempts.csv --target ... --source ... --query ... --outcome ...


def write_json(path: Path, payload: object) -> None:
    """Strict JSON for charts.json and numbers.json: a NaN or Infinity raises here instead of reaching the figures."""
    path.write_text(json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


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


def partial_corr_trend(xs: list[float], ys: list[float], ts: list[float] | None = None) -> float:
    """Partial Pearson r(x, y | t) removing shared linear time trend t (defaults to 0..n-1)."""
    t_idx = [float(i) for i in range(len(xs))] if ts is None else ts
    rxt, ryt, rxy = pearson_r(xs, t_idx), pearson_r(ys, t_idx), pearson_r(xs, ys)
    denom = math.sqrt(max(0.0, (1.0 - rxt * rxt) * (1.0 - ryt * ryt)))
    return (rxy - rxt * ryt) / denom if denom > 1e-12 else 0.0


def stratified_perm_pvalue(
    strata: dict[str, tuple[list[float], list[float]]],
    n_perm: int = 5000,
    seed: int = 42,
) -> tuple[float, float]:
    """Two-sided stratified permutation test of mean(treated) - mean(control) permuting within each stratum."""
    rng = random.Random(seed)
    weights = {k: len(a) + len(b) for k, (a, b) in strata.items() if a and b}
    total_n = sum(weights.values()) or 1
    obs = sum(weights[k] * (statistics.fmean(a) - statistics.fmean(b)) for k, (a, b) in strata.items() if k in weights) / total_n
    extreme = 0
    for _ in range(n_perm):
        stat = 0.0
        for k, (a, b) in strata.items():
            if k not in weights:
                continue
            pooled = list(a) + list(b)
            rng.shuffle(pooled)
            na = len(a)
            stat += weights[k] * (statistics.fmean(pooled[:na]) - statistics.fmean(pooled[na:]))
        if abs(stat / total_n) >= abs(obs) - 1e-12:
            extreme += 1
    return obs, (extreme + 1) / (n_perm + 1)


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
