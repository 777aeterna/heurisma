# Prompt — Level 3 Cold-Start Showcase (`emergence-in-physics`)

> **Prompt given to the agent (cold run with `heurisma v0.10.2`):**
>
> *"Conduct a rigorous scientific investigation on the phenomenon of emergence in physics."*

## What This Showcase Demonstrates

- **Level 3 (Deep Multi-Disciplinary):** bridges Statistical & Condensed-Matter Physics, Formal Sciences (exact solutions and computability theory), and Philosophy of Science.
- **Preregistration (`appendix/preregistration.json`):** sealed before running `appendix/analysis.py`, with every post-review methodological deviation transparently disclosed in Section 3.
- **Verified academic literature (`appendix/papers.csv`, `appendix/search_log.csv`, `appendix/data/papers/raw/`):** 13 scholarly references (`C1`–`C11`, `C13`–`C14`) retrieved via `scripts/papers.py` (OpenAlex / Crossref / Europe PMC / arXiv) with SHA-256-logged raw API responses (`papers.py replay` runs offline directly from this folder). Seven open-access full texts (including *Nature* 2015, *Physics Reports* 2002, *Foundations of Physics* 2010/2021, *Phys. Rev. B* 1971, MIT Press 2008, and arXiv 2018) were downloaded and hashed with `cite --fulltext`.
- **Reproducible computation (`appendix/analysis.py`, `C12` `own-computation`):** Wolff single-cluster Monte Carlo simulations across a 1D chain control ($N = 64\text{–}1024$), 2D square and triangular lattices ($L = 8\text{–}32$), replica-bootstrap Binder cumulant $U_4$ crossings, log-log finite-size susceptibility scaling, peak-temperature extrapolations across three axes, and $3 \times 3$ majority-rule block-spin RG coarse-graining ($L = 81, 27$), emitting `output.txt`, `numbers.json`, and **7 inline publication SVGs** (`charts.json`).
- **Two rounds of independent Reviewer #2 + Source Verifier + QA (`MODE: subagent`):** `appendix/gates/reviewer_round1.md`, `appendix/gates/reviewer.md` (with `ANALYSIS-SHA256`), `appendix/gates/source_verifier.md`, and `appendix/gates/qa.md`. In Round 2, Reviewer #2 exposed circularity in extrapolating the 1D chain peak temperature against $1/\ln N$ versus $1/\sqrt{N}$ (identical residual sums of squares), prompting all three axes to be reported and the 1D contrast to be downgraded to `[Preliminary]`.

## Validation Note (Withheld Publisher PDFs via `EXCLUDED.csv`)

This repository copy passes `validate_report.py report.md --level 3 --html report.html --strict --reproduce --json` directly with **`0` errors and `0` warnings** and `papers.py replay` offline with `0` discrepancies.

The 7 publisher/arXiv PDFs (~15.2 MB) are omitted from git for licensing and clone-size reasons and declared in [`appendix/data/papers/EXCLUDED.csv`](appendix/data/papers/EXCLUDED.csv) with their exact `download_log.csv` SHA-256 digests, keeping the original `MODE: subagent` gate hashes intact and verifiable:
- Open [`report.html`](report.html) offline directly (0 JS, 7 inline SVGs, embedded appendix, gate traces, and withheld-files notice).
- Re-run `python3 -B appendix/analysis.py` (or `--reproduce`) to regenerate `output.txt`, `numbers.json`, and `charts.json` byte-for-byte.
- Run `HEURISMA_OFFLINE=1 python3 -B ../../skills/heurisma/scripts/papers.py replay --appendix appendix` offline against `appendix/data/papers/raw/`.
