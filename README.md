<p align="center">
  <img src="assets/banner.png" alt="Heurisma — Beyond Deep Research · Scientific-Method Agent Skill" width="100%" />
</p>

<p align="center">
  <strong>Beyond Deep Research: a scientific-method agent skill for discipline-aware inquiry, reproducible data analysis, adversarial peer review, and publication-grade working-paper reports.</strong>
</p>

<p align="center">
  <a href="https://github.com/777aeterna/heurisma/actions/workflows/validate-skill.yml">
    <img src="https://github.com/777aeterna/heurisma/actions/workflows/validate-skill.yml/badge.svg" alt="CI Validation" />
  </a>
  <img src="https://img.shields.io/badge/Version-v0.3.0-0072B2?style=flat-square" alt="Version v0.3.0" />
  <img src="https://img.shields.io/badge/License-MIT-3B82F6?style=flat-square" alt="License: MIT" />
  <img src="https://img.shields.io/badge/Agent_Skills-Spec_Compliant-22D3EE?style=flat-square" alt="Agent Skills Spec" />
  <img src="https://img.shields.io/badge/Cross--Runtime-Antigravity_%7C_Claude_%7C_Codex_%7C_Gemini-0F172A?style=flat-square" alt="Cross-Runtime" />
  <img src="https://img.shields.io/badge/Vibecoded-AI_%2B_Skill_TDD-C9A45C?style=flat-square" alt="Vibecoded with AI + Skill TDD" />
</p>

---

## Why Heurisma? (Beyond Deep Research)

Conventional **Deep Research** tools are primarily *retrieval and summarization engines*: they search the web, mix press releases with peer-reviewed studies, and output long dashboard-style essays that sound authoritative even when the underlying evidence is weak or unverified.

**Heurisma** (from Greek *heuriskein*, "to discover") forces an AI agent to **think and publish like a scientist**:

| Dimension | Conventional Deep Research | Heurisma (`v0.3.0`) |
| :--- | :--- | :--- |
| **Before Searching** | Launches queries immediately | **Pre-Search Gate:** classifies scientific branch(es), `As-Of Date`, evidence standards, and depth level (`Level 0–3`) first |
| **Hypotheses & Forecasts** | Implicit narrative confirmation | Explicit **$H_0$ / $H_1$ falsifiable hypotheses** + multi-scenario forecasting (*identities ≠ forecasts*) |
| **Data & Provenance** | Eyeballs tables or declares lazy "data limitations" | Reproducible `appendix/fetch_data.py` + `analysis.py` + `sources.csv` + mandatory **Data-Attempts Log** |
| **Confirmation Bias** | Summarizes consensus narrative | Mandatory **Counter-Evidence** + independent **Reviewer #2** with closed **Disposition Table** (verify or exclude reviewer facts) |
| **Deliverables & Figures** | Wall of text or bloated code dumps | Clean `report.md` + lightweight (<100 KB), print-ready **working-paper `report.html`** with zero-dependency **inline SVG charts** (`line`, `bar`, `fan`, `bands`, `annotations`, `log`) |
| **Verification** | Unchecked prose | Zero-dependency **bilingual (EN/ES) validator** checking structure, substance, `[Strong]` vs. Tier 3/press bans, and `--html` |

> **Transparency Note:** This skill was **vibecoded** — designed, written, and iteratively pressure-tested with AI agents (including independent cross-model audits between Gemini and Claude) following the *Superpowers* methodology (strict **RED → GREEN → REFACTOR** TDD applied to agent skills).

---

## Cognitive Architecture (7 Stages, Levels 0–3)

```mermaid
flowchart TD
    U["User Research Prompt"] --> S0["Stage 0: Cognitive Triage, As-Of Date & Level 0–3"]
    S0 --> L0{"Level 0 Light Mode?"}
    L0 -- Yes --> FAST["Compact 3-Part Calibrated Response"]
    L0 -- No --> S1["Stage 1: Research Question & Falsifiable Hypotheses"]
    S1 --> S2["Stage 2: Primary Data Acquisition & Data-Attempts Log"]
    S2 --> D{"Level 2+ Quantitative?"}
    D -- Yes --> S3["Stage 3: appendix/fetch_data.py & analysis.py → charts.json v2"]
    D -- No --> S4["Stage 4: Adversarial Falsification & Closed Reviewer #2"]
    S3 --> S4
    S4 --> S5["Stage 5: Single-Language Working-Paper Writing (EN/ES)"]
    S5 --> S6["Stage 6: render_report.py → report.html + validate_report.py"]
```

### Modular Structure (`skills/heurisma/`)
- **[`SKILL.md`](skills/heurisma/SKILL.md):** Lean, runtime-agnostic core enforcing the 4 Iron Laws, adaptive depth (`Level 0–3`), abstract-style verdict limits (≤3 sentences, ≤5 numbers), single-language discipline, and Stage 6 deliverables.
- **[`references/disciplines.md`](skills/heurisma/references/disciplines.md):** Taxonomy of 6 scientific branches + Interdisciplinary Bridge Protocol.
- **[`references/data-protocol.md`](skills/heurisma/references/data-protocol.md):** Reproducible `fetch_data.py`, `sources.csv`, `data_attempts.csv`, MAD + Bootstrap 95% CI template, and direct `charts.json` emission.
- **[`references/forecasting.md`](skills/heurisma/references/forecasting.md):** Multi-scenario triggers, base rates, historical error calibration, lagging-series nowcasting, and the *identity-vs-forecast* rule.
- **[`references/adversarial-review.md`](skills/heurisma/references/adversarial-review.md):** Self-falsification checklist, **Reviewer #2** prompt template, mandatory Disposition Table (EN/ES), and primary verification rule.
- **[`references/scientific-writing.md`](skills/heurisma/references/scientific-writing.md):** Epistemic calibration scale, 100% English and 100% Spanish contracts, and `charts.json` v2 specification.
- **[`references/example-report.md`](skills/heurisma/references/example-report.md):** Compact gold-standard working-paper reference example.
- **[`scripts/svg_charts.py`](skills/heurisma/scripts/svg_charts.py):** Zero-dependency publication SVG engine (Heckbert ticks, calendar-year date axes, Okabe-Ito palette + print dash styles, automatic >30-pt marker hiding, `bands`, `annotations`, `fan` charts, grouped `bar`, safe `log` scale).
- **[`scripts/render_report.py`](skills/heurisma/scripts/render_report.py):** Zero-dependency working-paper HTML renderer (serif typography, 720px column, booktabs tables, small-caps tags, inline `{{fig:id}}` figures, auto-generated References, `@media print` A4 rules, and strict appendix filtering excluding raw data/binaries).
- **[`scripts/validate_report.py`](skills/heurisma/scripts/validate_report.py):** Zero-dependency bilingual (EN/ES) validator checking headings, substance, Section 2 hypotheses, per-row matrix tags, `[Strong]` vs. Tier 3/press bans, `--level 2|3` artifacts, and `--html`.

---

## Installation (Cross-Runtime)

Heurisma follows the open [Agent Skills Specification](https://agentskills.io/specification) and works out of the box across **Antigravity (`agy`)**, **Claude Code**, **Codex**, and **Gemini CLI**:

```bash
# Clone the repository
git clone https://github.com/777aeterna/heurisma.git

# Install globally for Antigravity / Codex / Gemini CLI (~/.agents/skills/)
mkdir -p ~/.agents/skills
cp -r heurisma/skills/heurisma ~/.agents/skills/heurisma

# Or install globally for Claude Code (~/.claude/skills/)
mkdir -p ~/.claude/skills
cp -r heurisma/skills/heurisma ~/.claude/skills/heurisma
```

---

## Showcase Examples & CLI Tools

Inspect validated outputs generated with Heurisma:
- **Level 1 — Rigorous Inquiry (Pressure-Tested Board Brief):** [`examples/level1-brief-example.md`](examples/level1-brief-example.md)
- **Level 2 — Empirical Data Study (Working-Paper Format + Reproducible Appendix):** [`examples/level2-study/report.md`](examples/level2-study/report.md) + [`examples/level2-study/appendix/`](examples/level2-study/appendix)

Render and validate locally with zero external dependencies:

```bash
python3 examples/level2-study/appendix/analysis.py --charts-out examples/level2-study/charts.json > examples/level2-study/appendix/output.txt
python3 skills/heurisma/scripts/render_report.py examples/level2-study/report.md \
  --out examples/level2-study/report.html \
  --charts examples/level2-study/charts.json \
  --appendix examples/level2-study/appendix
python3 skills/heurisma/scripts/validate_report.py examples/level2-study/report.md \
  --level 2 --html examples/level2-study/report.html
```

---

## Verification & Quality Assurance

- **22/22 unit tests passing** across [`tests/test_validate_report.py`](tests/test_validate_report.py), [`tests/test_svg_charts.py`](tests/test_svg_charts.py), and [`tests/test_render_report.py`](tests/test_render_report.py).
- **Skill TDD evals:** 4/4 RED baseline failures ([`evals/baselines/baseline-report.md`](evals/baselines/baseline-report.md)) → 6/6 GREEN passes ([`evals/results/green-eval-report.md`](evals/results/green-eval-report.md)), hardened further through two full external Claude audits (`v0.1 → v0.2 → v0.3`).

---

## Contributing & License

Contributions (especially new discipline protocols in `references/disciplines.md` and pressure scenarios in `evals/scenarios/`) are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

Released under the [MIT License](LICENSE) © 2026 [777aeterna](https://github.com/777aeterna).
