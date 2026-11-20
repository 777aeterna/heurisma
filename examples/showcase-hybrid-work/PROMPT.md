# Example Prompt (Level 2 Empirical Study with Local Data + Literature)

> **User Prompt:**
>
> "Using our local multi-site engineering dataset (`data/hybrid_rct_sites.csv`) alongside primary peer-reviewed field experiments, evaluate whether a 2-day/week hybrid work policy improves software-engineering output and employee retention compared to full-time office work, and test whether the effect holds equally for junior and senior engineers."

---

## How This Output Was Generated

1. Installed `heurisma` v0.4.0 (`~/.agents/skills/heurisma`).
2. Ran **Stage 0** local inventory (`python3 -B ~/.agents/skills/heurisma/scripts/local_data.py inventory data/`).
3. Executed **Stages 1–6** (`appendix/analysis.py` → `output.txt`, `numbers.json`, `charts.json`; `render_report.py` → `report.html`; `validate_report.py --level 2 --html report.html --strict`).
