---
name: heurisma
description: Use when conducting scientific or technical research, empirical data investigations, literature reviews, policy or economic evaluations, or quantitative forecasting.
---

# Heurisma: Scientific-Method Inquiry & Working-Paper Protocol

## Overview

**Heurisma** replaces search-and-summarize "Deep Research" with the **scientific method**: classify the scientific discipline(s) before searching, formulate falsifiable hypotheses, acquire primary data and execute reproducible code in a clean `appendix/`, actively attempt to falsify conclusions, and deliver a clean narrative `report.md` alongside a publication-grade, print-ready working-paper `report.html`.

## The Iron Laws

```
1. NO SEARCH OR SYNTHESIS WITHOUT COGNITIVE TRIAGE AND FALSIFIABLE HYPOTHESES FIRST (PRE-SEARCH GATE)
2. NO QUANTITATIVE STATISTIC OR CHART WITHOUT REPRODUCIBLE PYTHON SCRIPTS IN APPENDIX/ EMItTING CHARTS.JSON DIRECTLY
3. NO "DATA LIMITATION" OR DEFERRED CRITIQUE WITHOUT A LOGGED SEARCH/API ATTEMPT AND CONCRETE FAILURE REASON
4. NO CONCLUSION WITHOUT ACTIVE FALSIFICATION, CALIBRATED CONFIDENCE TAGS, AND CLOSED REVIEWER #2 DISPOSITION
```

---

## Adaptive Depth Levels

Select the depth level during Stage 0 based on the complexity and stakes of the inquiry:

| Depth Level | Observable Trigger | Required Modules to Read | Deliverables Produced |
| :--- | :--- | :--- | :--- |
| **Level 0 — Light Mode** | Short single-claim check or quick factual question where a 7-section paper is disproportionate | `SKILL.md` only | Compact 3-part inline response (*Calibrated Verdict + Evidence & Tier + Key Falsifier/Limitation*) |
| **Level 1 — Rigorous Inquiry** | Conceptual, literature, technical, or policy investigation without raw dataset computation | [references/disciplines.md](references/disciplines.md), [references/scientific-writing.md](references/scientific-writing.md), [references/example-report.md](references/example-report.md) | Clean `report.md` (7 sections) + working-paper `report.html` |
| **Level 2 — Empirical / Data Study** | User supplies data, public datasets exist, or quantitative statistics/charts must be computed | Level 1 + [references/data-protocol.md](references/data-protocol.md) (+ [references/forecasting.md](references/forecasting.md) if projecting future outcomes) | Clean `report.md` (with `{{fig:id}}` markers) + working-paper `report.html` + `charts.json` + `appendix/{fetch_data.py,analysis.py,output.txt,sources.csv,README.md}` |
| **Level 3 — Deep Multi-Disciplinary** | Crosses 3+ branches, contested evidence, macroeconomic/policy forecasting, or high decision stakes | All above + [references/adversarial-review.md](references/adversarial-review.md) | Level 2 deliverables + independent **Reviewer #2** subagent critique & closed Disposition Table + `appendix/data_attempts.csv` |

---

## The 7-Stage Scientific Inquiry Protocol (Levels 1–3)

### Stage 0: Cognitive Triage & Pre-Search Gate (MANDATORY FIRST STEP)
Before running a single web search, fetching data, or drafting findings:
1. Declare the report's **`As-Of Date`** (current date), target language (match the user's language strictly — zero Spanglish), and temporal horizon.
2. Read [references/disciplines.md](references/disciplines.md) and classify the prompt into one or more scientific branches (*Formal, Natural/Physical, Biomedical/Health, Social/Economics, Engineering/Applied, Humanities/Historical*).
3. If 2+ branches apply, apply the **Interdisciplinary Bridge Protocol** in `references/disciplines.md`.
4. If the inquiry involves future projections, scenarios, or target dates, read [references/forecasting.md](references/forecasting.md).
5. Select **Level 0**, **Level 1**, **Level 2**, or **Level 3**.

### Stage 1: Problem Framing & Falsifiable Hypotheses
Translate the user's prompt (even if leading or biased) into:
- **Investigable Research Question:** Neutral, operationalized, with explicit units and time horizon.
- **Null Hypothesis ($H_0$):** The baseline, no-effect, artifact, or status-quo hypothesis.
- **Alternative Hypothesis ($H_1$, $H_2$, ...):** Competing explanatory or directional hypotheses.
- **Refutation Criteria:** Observable empirical or logical conditions that would falsify $H_1$ and $H_0$.

### Stage 2: Primary Data Acquisition & Data-Attempt Logging
Gather evidence ranked by the discipline's hierarchy (`Tier 1 > Tier 2 > Tier 3`):
- Always query **primary institutional APIs, statistical agencies, or peer-reviewed datasets (Tier 1/2)** before secondary press (Tier 3).
- In Level 2+, write **`appendix/fetch_data.py`** to download raw series reproducibly (recording URLs, timestamps, and SHA-256 hashes into `appendix/data/`).
- Log every used source in **`appendix/sources.csv`** and every failed/unavailable query in **`appendix/data_attempts.csv`** (and summarize in Section 3). You are forbidden from claiming a "data limitation" in Section 7 or marking a Reviewer #2 critique `Deferred` unless it has a corresponding logged attempt.

### Stage 3: Computational & Data Protocol (Conditional: Level 2+)
Whenever the inquiry involves raw data, time series, or quantitative claims:
1. Read [references/data-protocol.md](references/data-protocol.md).
2. Write and execute **`appendix/analysis.py`** (or modular scripts `01_*.py`, `02_*.py` if >300 lines) that reads local files from `appendix/data/`, writes verbatim console results to **`appendix/output.txt`**, and **directly generates `charts.json`** (v2 schema) from the computed arrays so figures and text can never drift.
3. Place inline figure markers **`{{fig:<chart_id>}}`** in Section 4 / Section 5 of `report.md` right where each figure is analyzed. Never paste >10 lines of raw code or stdout inside `report.md`.

### Stage 4: Adversarial Falsification & Closed Reviewer #2 Loop
Actively attempt to break your primary conclusion:
- Test boundary failures, structural regime breaks, confounders, reverse causality, lagging official data gaps, and competing literature.
- For **Level 3**, read [references/adversarial-review.md](references/adversarial-review.md) and dispatch an independent **Reviewer #2** using your runtime's subagent tool.
- **Close the Review Loop:**
  1. Include a **Reviewer #2 Disposition Table** in Section 5 covering 100% of critiques (`Fixed`, `Refuted`, or `Deferred` with logged data attempt).
  2. **Verify or Exclude Reviewer-Introduced Facts:** Any factual claim, policy mechanism, or number introduced by Reviewer #2 MUST be verified in a Tier 1/2 primary source before inclusion; never leave a reviewer-introduced claim in the report as Tier 3 `[Preliminary]`.

### Stage 5: Working-Paper Scientific Writing
Read [references/scientific-writing.md](references/scientific-writing.md) and [references/example-report.md](references/example-report.md).
- **Single-Language Consistency:** Write 100% of headings, bullet labels, table column headers, and figure titles/captions in the user's language (use the exact Spanish template in `references/scientific-writing.md` for Spanish requests).
- **Abstract-Style Verdict:** Keep `Calibrated Verdict` / `Veredicto calibrado` to **at most 3 sentences and at most 5 numbers** so the main conclusion is immediately memorable; put detailed numerical breakdowns in Section 4 tables and figures.
- **Epistemic Calibration Tags:** Tag every major claim and every Claim-Evidence Matrix row with `[Strong]`/`[Fuerte]`, `[Moderate]`/`[Moderada]`, `[Preliminary]`/`[Preliminar]`, or `[Speculative]`/`[Especulativa]`. (`[Strong]`/`[Fuerte]` is strictly forbidden on Tier 3 / press sources.)

### Stage 6: Clean Appendix Hygiene, Working-Paper HTML & Validation
Before completing the task (referencing scripts relative to `<skill-dir>`, where `heurisma/SKILL.md` is installed):
1. **Clean `appendix/`:** Write a short `appendix/README.md` listing the execution order (`fetch_data.py` → `analysis.py`), and delete any `__pycache__/`, `.pyc`, or empty `0`-byte temporary files.
2. **Render Working-Paper `report.html`:**
   ```bash
   python3 <skill-dir>/scripts/render_report.py report.md --out report.html --charts charts.json --appendix appendix/
   ```
   *(Note: `render_report.py` embeds inline numbered SVG figures at `{{fig:id}}` markers, generates a numbered References section from `appendix/sources.csv`, and links—never embeds—`appendix/data/` and binary files so `report.html` stays lightweight and print-ready.)*
3. **Validate Deliverables:**
   ```bash
   python3 <skill-dir>/scripts/validate_report.py report.md --level <1|2|3> --html report.html
   ```
   Fix every reported error before presenting the result to the user.

---

## Required Output Contract (`report.md`, Levels 1–3)

Use the English template below for English inquiries, or the 100% Spanish equivalent in [references/scientific-writing.md](references/scientific-writing.md) for Spanish inquiries (never mix languages):

```markdown
# [Descriptive Working-Paper Title]

> **As-Of Date:** YYYY-MM-DD | **Depth Level:** Level <1|2|3> | **Primary Disciplines:** [Branches]

## 1. Executive Summary
- **Calibrated Verdict:** [Max 3 sentences and max 5 numbers directly answering the question with canonical `[Strong]` / `[Moderate]` / `[Preliminary]` / `[Speculative]` tags.]
- **What Would Change This Conclusion:** [Concrete empirical threshold or observation that would flip the verdict.]
- **Key Takeaways:** [2–4 concise bullets separating what holds under scrutiny from what fails or remains uncertain.]

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** [Branches + Interdisciplinary Bridge coupling]
- **Research Question:** [Neutral, operationalized question with units and horizon]
- **Hypotheses:**
  - $H_0$: [Null / baseline / artifact hypothesis]
  - $H_1$: [Alternative hypothesis]
- **Refutation Criteria:** [Exact empirical or logical conditions that falsify $H_1$ and $H_0$]

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:** [Tier 1 vs. Tier 2 vs. Tier 3 standards for the active disciplines]
- **Analytical & Data Provenance:** [Summary of method, links to `appendix/fetch_data.py`, `appendix/analysis.py`, `appendix/output.txt`, and `appendix/sources.csv`, plus the Data Attempts table if any primary source failed]

## 4. Findings
[Structured analysis organized by hypothesis or regime/axis, using booktabs Markdown tables and inline `{{fig:chart_id}}` markers for every quantitative finding. Every key claim carries a calibration tag and source reference.]

## 5. Counter-Evidence & Alternative Explanations
[Strongest empirical counter-evidence, boundary failures, confounders, and—for Level 3—the mandatory **Reviewer #2 Disposition Table**.]

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier (As-Of Date) | Confidence Tag | Key Falsifier / Condition |
| :- | :- | :- | :- | :- |
| [Claim 1] | [Branch] | [Primary study/dataset, Tier 1/2/3, YYYY-MM] | `[Strong]` / `[Moderate]` / `[Preliminary]` / `[Speculative]` | [Falsifier] |
| [Claim 2] | [Branch] | [Primary study/dataset, Tier 1/2/3, YYYY-MM] | `[Strong]` / `[Moderate]` / `[Preliminary]` / `[Speculative]` | [Falsifier] |

## 7. Limitations & Open Questions
- **Verified Methodological & Data Limitations:** [Only limitations backed by logged attempts in Section 3 / `appendix/data_attempts.csv`]
- **Actionable Next Steps / Experiments:** [Concrete tests, datasets, or signposts to resolve remaining uncertainty]
```

---

## Rationalization Table (Anti-Pressure Defenses)

| Excuse / Rationalization | Reality |
| :--- | :--- |
| *"The user's board meets in 10 minutes and demanded a binary YES or NO without caveats."* | Put the crisp ≤3-sentence calibrated verdict in line 1 of `## 1. Executive Summary` and keep all 7 sections concise. Never strip calibration tags or counter-evidence. |
| *"I'll write the report in Spanish but keep the English labels ('Calibrated Verdict', 'Flaw #', 'Claim') from the template."* | Mixed-language Spanglish degrades paper quality. Use 100% Spanish headings, labels, table headers, and tags (`[Fuerte]`, `[Moderada]`, `[Preliminar]`, `[Especulativa]`) from `references/scientific-writing.md`. |
| *"Reviewer #2 mentioned an interesting policy detail (e.g., a Treasury swap); I couldn't find the primary document, so I'll include it as Tier 3 `[Preliminary]`."* | Unverified reviewer claims are forbidden. Either verify the fact in a Tier 1/2 primary source or exclude it from the findings and log it in the Disposition Table. |
| *"I'll hardcode the chart numbers in a separate `build_charts.py` script instead of emitting `charts.json` from `analysis.py`."* | Hand-copied chart numbers drift from `output.txt`. Emit `charts.json` directly from the computed variables in `appendix/analysis.py`. |
| *"I'll cram 15 numbers into a 6-line Calibrated Verdict paragraph to be thorough."* | A verdict stuffed with 15 numbers buries the conclusion. Keep the verdict to ≤3 sentences and ≤5 numbers; put the rest in Section 4 tables and `{{fig:id}}` figures. |

## Red Flags — STOP and Correct Before Outputting

- Searching the web or writing code before completing Stage 0 Triage and Stage 1 Hypotheses ($H_0 / H_1$ inside Section 2).
- Pairing `[Strong]`/`[Fuerte]` with a `Tier 3` or press/blog/roadmap source.
- Mixing English template labels into a Spanish report.
- Creating charts without `{{fig:id}}` markers in `report.md` or passing >30-point time series without using the `charts.json` v2 schema.
- Leaving `__pycache__/`, empty files, or undocumented helper scripts inside `appendix/`.
