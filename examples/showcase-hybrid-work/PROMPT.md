# Example Prompt (Level 2 Empirical Study with Local Data + Literature)

> **User Prompt:**
>
> "Using our local multi-site engineering dataset (`data/hybrid_rct_sites.csv`) alongside primary peer-reviewed field experiments, evaluate whether a 2-day/week hybrid work policy improves software-engineering output and employee retention compared to full-time office work, and test whether the effect holds equally for junior and senior engineers."

> **About the data:** `data/hybrid_rct_sites.csv` is an **illustrative file shipped with this repository** (16 sites, semicolon-delimited, decimal comma). It is not field data, and its allocation of sites to policies is undocumented. The report therefore treats it as unknown-origin data (Tier 3, claims capped at `[Preliminary]`) — which is the behavior this showcase is meant to demonstrate. The literature it is read against (a randomized trial and a published quasi-experimental study) was read from the sources listed in `appendix/sources.csv`.

---

## How This Output Was Generated

1. Ran **Stage 0** local inventory (`python3 -B <skill-dir>/scripts/local_data.py inventory data/`).
2. Executed **Stages 1–6** (`appendix/analysis.py` → `output.txt`, `numbers.json`, `charts.json`; `render_report.py` → `report.html`; `validate_report.py --level 2 --html report.html --strict`).
3. v0.5.0 revision: the first version of this showcase tagged causal claims `[Strong]` and listed its own script as Tier 1. A Reviewer #2 pass (`references/agents/reviewer.md`) found that allocation was never shown to be random, that a working paper was cited as a randomized trial, and that bootstrap intervals on four sites per arm are unreliable. This version registers the file as Tier 3, uses exact permutation tests, reads the cited sources (and says so when only an abstract was read), and caps every claim from the file at `[Preliminary]`.
