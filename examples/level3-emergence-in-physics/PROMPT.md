# Prompt — Level 3 Cold-Start Showcase (`emergence-in-physics`)

> **Prompt given to the agent (cold run with `heurisma v0.10.1`):**
>
> *"Conduct a rigorous scientific investigation on the phenomenon of emergence in physics."*

## What This Showcase Demonstrates

- **Level 3 (Deep Multi-Disciplinary):** bridges Statistical Mechanics / Condensed Matter Physics, Mathematical Physics / Computability Theory, and Philosophy of Physics.
- **Preregistration (`appendix/preregistration.json`):** sealed before running `appendix/analysis.py`.
- **Verified academic literature (`appendix/papers.csv`, `appendix/search_log.csv`, `appendix/data/papers/raw/`):** 10 peer-reviewed papers (`C1`–`C10`) retrieved via `scripts/papers.py` (OpenAlex / Crossref / Unpaywall) with SHA-256-logged raw API responses (`papers.py replay` runs offline directly from this folder).
- **Reproducible computation (`appendix/analysis.py`):** 2D Ising Wolff-cluster Monte Carlo simulations across square and triangular lattices plus exact $L=2\text{–}4$ enumeration, Binder cumulant $U_4$ crossings, and log-log finite-size scaling emitting `output.txt`, `numbers.json`, and 4 inline publication SVGs (`charts.json`).
- **Three independent subagent gates (`MODE: subagent`):** `appendix/gates/source_verifier.md`, `appendix/gates/reviewer.md` (with `ANALYSIS-SHA256`), and `appendix/gates/qa.md`. Reviewer #2 caught an over-calibrated `[Strong]` claim resting on own computation (`@C11`) where square vs. triangular $\gamma/\nu$ estimates differed by $2.1\sigma$; the claim was downgraded to `[Moderate]` and resolved in the Section 5 Disposition Table.

## Validation Note (Publisher PDFs Excluded)

In the original local run (with all 10 downloaded full-text PDFs present), `validate_report.py report.md --level 3 --html report.html --strict --reproduce --json` passed with **`0` errors and `0` warnings**.

The 10 publisher PDFs (~16 MB) are excluded from this repository for copyright and clone-size reasons (see [`appendix/data/papers/README.md`](appendix/data/papers/README.md) for their DOIs and SHA-256 digests). You can still:
- Open [`report.html`](report.html) offline directly (0 JS, 4 inline SVGs, embedded appendix & gate traces).
- Re-run `python3 -B appendix/analysis.py` to reproduce `output.txt`, `numbers.json`, and `charts.json` byte-for-byte.
- Run `python3 -B ../../skills/heurisma/scripts/papers.py replay --appendix appendix` offline against `appendix/data/papers/raw/`.
