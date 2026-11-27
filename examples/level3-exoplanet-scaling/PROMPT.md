# Prompt — Level 3 Cold-Start Showcase (`level3-exoplanet-scaling`)

> **Research Question (cold run with `heurisma v0.11.1`):**
>
> *"Across confirmed transiting exoplanets orbiting diverse host stars ($0.1\,M_\odot \lesssim M_\star \lesssim 2.5\,M_\odot$), does real observational data empirically recover the exact two-body Keplerian scaling $P \propto a^{3/2} M_\star^{-1/2}$ out-of-sample (and invariance of $P^2 G M_\star / a^3$), while the planetary mass–radius relation $R_p(M_p)$ breaks single-power-law scaling across the rocky, sub-Neptune, and gas-giant degeneracy regimes?"*

## What This Showcase Demonstrates (`v0.11.1` Full Feature Set)

- **Level 3 (Deep Multi-Disciplinary):** bridges **Natural & Physical Sciences** (observational astrophysics, transit dynamics, planetary interiors) with **Formal Sciences** (exact Buckingham $\Pi$ dimensional reduction, out-of-sample symbolic discovery, conservation-invariant search, and Lean 4 formal verification).
- **Preregistration (`appendix/preregistration.json`):** sealed before downloading or computing, with post-preregistration derived SI table provenance (`appendix/data/exoplanets_si.csv`) transparently documented in Section 3 (`P2-PREREG` clean).
- **Real empirical archive data via anti-SSRF IP-pinned `fetch_lib.py` (`appendix/fetch_data.py`):** 1,244 confirmed transiting exoplanets across 1,029 host stars downloaded from the NASA Exoplanet Archive TAP API (`ps` table, `C1` + extended transit-geometry & uncertainty table `C10`, 64-hex SHA-256 digests logged in `appendix/download_log.csv`).
- **Verified academic literature + arXiv DataCite DOI (`appendix/papers.csv`, `appendix/search_log.csv`, `appendix/data/papers/raw/`):** 6 references (`C2`–`C7`, including Chen & Kipping 2017, Fulton et al. 2017, Rogers 2015, Weiss & Marcy 2014, Otegi et al. 2020, and arXiv DataCite `10.48550/arXiv.2310.16733`) verified via `papers.py search|lookup|cite --fulltext|verify|replay`.
- **Exact Dimensional Analysis & Symbolic Discovery (`conjecture.py`):**
  - `conjecture.py units` isolates $\Pi_1 = P_s \cdot a_m^{-3/2} \cdot (GM)^{1/2}$ and prunes planetary mass $M_p$ (`exponent = 0`).
  - `appendix/conjectures.json` (`C_LAW_1`): recovers $P_s = 6.2502 \, a_m^{3/2} (GM)^{-1/2}$ (0.52% from $2\pi$, `holdout_r2 = 0.9932`, `beats_null = true`, capped at `[Moderate]` on discovery data).
  - `appendix/conjectures_invariant.json` (`C_INV_1`): recovers $P_s \, a_m^{-3/2} (GM)^{1/2} = 6.27644$ (0.11% from $2\pi$, `holdout_r2 = 0.9945`, `beats_null = true`).
- **Counter-Evidence & Non-Circular Controls (`appendix/analysis.py`, 3 inline SVGs):** independent transit-geometry $a_{\text{tr}} = (a/R_\star) R_\star$ (`n = 863`, $\log_{10} R^2 = 0.9871$), host-clustered bootstrap 95% CIs, Kruskal-Wallis invariance test ($H = 1.87$, $p = 0.40$), 5-fold CV RMSE + continuous broken power-law $\Delta\text{BIC} = 553.2$ falsifying a single mass–radius power law, and $3\sigma$ uncertainty propagation on `>5%` outliers.
- **Lean 4 Formal Verification (`appendix/formal/kepler-scaling/`):** real kernel-checked `Int`-ring algebraic scaling proof (`Challenge.lean` / `Solution.lean`, Lean `v4.16.0` / Lake `5.0.0`, `status=kernel-verified`, `verification_mode=kernel-defeq`, `0` `sorry`, `axioms=['propext']`, `0` trivial-proof warnings, `FM1` automatically promoted to `Tier 1` `[Strong]`) with `FORMAL-SHA256` gate binding.
- **Three independent `MODE: subagent` gates (`reviewer.md`, `source_verifier.md`, `qa.md`):** Reviewer #2 performed blind back-translation of `Challenge.lean`, checked `FORMAL-SHA256` and `ANALYSIS-SHA256`, and caught a real `C9` SHA-256 mismatch in `sources.csv` plus exclusion-rate / knot-sensitivity gaps — all resolved and closed in Section 5.3; `QA: PASS` (`FAIL count: 0`).

## Validation Note (Withheld Publisher PDFs via `EXCLUDED.csv`)

This repository copy passes `validate_report.py report.md --level 3 --html report.html --strict --reproduce --json` (and `--reproduce-lean` when Lean 4 / `lake` is installed) directly with **`0` errors and `0` warnings**, and `papers.py replay` offline with **`0` discrepancies**.

The 5 publisher/arXiv PDFs (~16 MB) are omitted from git for licensing and clone-size reasons and declared in [`appendix/data/papers/EXCLUDED.csv`](appendix/data/papers/EXCLUDED.csv) with their exact `download_log.csv` SHA-256 digests (and `.lake/` build caches are omitted cleanly), keeping the `MODE: subagent` gate hashes intact and verifiable:
- Open [`report.html`](report.html) offline directly (0 JS, 3 inline SVGs, embedded appendix, gate traces, and withheld-files notice).
- Re-run `python3 -B appendix/analysis.py` (or `--reproduce` / `--reproduce-lean`) to regenerate `output.txt`, `numbers.json`, and `charts.json` byte-for-byte and replay the Lean 4 kernel proof from scratch.
- Run `HEURISMA_OFFLINE=1 python3 -B ../../skills/heurisma/scripts/papers.py replay --appendix appendix` offline against `appendix/data/papers/raw/`.
