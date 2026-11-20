---
name: heurisma
description: Use when conducting scientific or technical research, empirical data investigations, literature reviews, policy or economic evaluations, or quantitative forecasting.
---

# Heurisma: Scientific-Method Inquiry & Working-Paper Protocol

## Overview

**Heurisma** replaces search-and-summarize "Deep Research" with the **scientific method**: classify the scientific discipline(s) before searching, formulate falsifiable hypotheses, acquire primary data (online first, then the user's local files) and execute reproducible code in a clean `appendix/`, actively attempt to falsify conclusions, and deliver a clean narrative `report.md` with linked in-text citations alongside a publication-grade, print-ready working-paper `report.html`.

## The Iron Laws

```
1. NO SEARCH OR SYNTHESIS WITHOUT COGNITIVE TRIAGE AND FALSIFIABLE HYPOTHESES FIRST (PRE-SEARCH GATE)
2. NO QUANTITATIVE STATISTIC OR CHART WITHOUT REPRODUCIBLE PYTHON SCRIPTS IN APPENDIX/ EMITTING CHARTS.JSON DIRECTLY
3. NO "DATA LIMITATION", DEFERRED CRITIQUE, OR TAG-DOWNGRADE CLOSURE WITHOUT A LOGGED ONLINE ATTEMPT AND A LOGGED LOCAL SEARCH
4. NO CONCLUSION WITHOUT ACTIVE FALSIFICATION, CALIBRATED CONFIDENCE TAGS, AND CLOSED REVIEWER #2 DISPOSITION
```

**Script hygiene:** always invoke bundled scripts and your own appendix scripts with `python3 -B` (no `__pycache__/` is written into the installed skill or into `appendix/`). `<skill-dir>` below is the directory containing this `SKILL.md`.

---

## Adaptive Depth Levels

Select the depth level during Stage 0 based on the complexity and stakes of the inquiry:

| Depth Level | Observable Trigger | Required Modules to Read | Deliverables Produced |
| :--- | :--- | :--- | :--- |
| **Level 0 — Light Mode** | Short single-claim check or quick factual question where a 7-section paper is disproportionate | `SKILL.md` only | Compact 3-part inline response (*Calibrated Verdict + Evidence & Tier + Key Falsifier/Limitation*) |
| **Level 1 — Rigorous Inquiry** | Conceptual, literature, technical, or policy investigation without raw dataset computation | [references/disciplines.md](references/disciplines.md), [references/scientific-writing.md](references/scientific-writing.md), [references/example-report.md](references/example-report.md) | Clean `report.md` (7 sections) + working-paper `report.html` |
| **Level 2 — Empirical / Data Study** | User supplies data (files, folders, attachments), local data is found in Stage 0, public datasets exist, or quantitative statistics/charts must be computed | Level 1 + [references/data-protocol.md](references/data-protocol.md) (+ [references/forecasting.md](references/forecasting.md) if projecting future outcomes) | Clean `report.md` (with `{{fig:id}}` markers and `[@C1]` citations) + working-paper `report.html` + `charts.json` + `appendix/{fetch_data.py,analysis.py,output.txt,sources.csv,data_attempts.csv,README.md}` (+ optional `appendix/numbers.json`) |
| **Level 3 — Deep Multi-Disciplinary** | Crosses 3+ branches, contested evidence, macroeconomic/policy forecasting, or high decision stakes | All above + [references/adversarial-review.md](references/adversarial-review.md) | Level 2 deliverables + independent **Reviewer #2** subagent critique & closed Disposition Table |

---

## The 7-Stage Scientific Inquiry Protocol (Levels 1–3)

### Stage 0: Cognitive Triage, Local Data Inventory & Pre-Search Gate (MANDATORY FIRST STEP)
Before running a single web search, fetching data, or drafting findings:
1. Declare the report's **`As-Of Date`** (current date), target language (match the user's language strictly — zero Spanglish), and temporal horizon.
2. Read [references/disciplines.md](references/disciplines.md) and classify the prompt into one or more scientific branches (*Formal, Natural/Physical, Biomedical/Health, Social/Economics, Engineering/Applied, Humanities/Historical*).
3. If 2+ branches apply, apply the **Interdisciplinary Bridge Protocol** in `references/disciplines.md`.
4. If the inquiry involves future projections, scenarios, or target dates, read [references/forecasting.md](references/forecasting.md).
5. **Inventory local data** (zero dependencies, read-only):
   ```bash
   python3 -B <skill-dir>/scripts/local_data.py inventory              # scans $HEURISMA_DATA_DIR, ./datos, ./data, ./appendix/data
   python3 -B <skill-dir>/scripts/local_data.py inventory <path> ...   # plus any file/folder the user mentioned
   ```
   List the local files found (kind, size, SHA-256 prefix) in your response. If the topic is data-heavy and nothing was found, ask the user once whether they have their own files before you rely on online sources only.
6. Select **Level 0**, **Level 1**, **Level 2**, or **Level 3**.

### Stage 1: Problem Framing & Falsifiable Hypotheses
Translate the user's prompt (even if leading or biased) into:
- **Investigable Research Question:** Neutral, operationalized, with explicit units and time horizon.
- **Null Hypothesis (H₀):** The baseline, no-effect, artifact, or status-quo hypothesis.
- **Alternative Hypothesis (H₁, H₂, ...):** Competing explanatory or directional hypotheses.
- **Refutation Criteria:** Observable empirical or logical conditions that would falsify H₁ and H₀.

Write hypotheses with Unicode subscripts (`H₀`, `H₁`) rather than LaTeX.

### Stage 2: Primary Data Acquisition — 4-Tier Fallback Cascade & Data-Attempt Logging
Gather evidence ranked by the discipline's hierarchy (`Tier 1 > Tier 2 > Tier 3`). For every target series, walk this **mandatory cascade** and stop at the first rung that succeeds:

| Rung | Action | Logged As |
| :- | :- | :- |
| **1. Online primary** | Query the primary institutional API, statistical agency, or peer-reviewed dataset (Tier 1/2) via `appendix/fetch_data.py` | `download_log.csv` on success; `data_attempts.csv` row on failure |
| **2. Online alternatives** | Mirrors, alternate formats (XLSX vs. CSV vs. JSON), archived vintages, or a web search for the exact file | `data_attempts.csv` row per failed alternative |
| **3. Local data** | User files or prior downloads found in Stage 0: inspect with `local_data.py preview`, **copy** into `appendix/data/`, register with `local_data.py register` | `sources.csv` row with `file://` URL + SHA-256; `fallback_used = local:<path> sha256:<hash>` in the failed rung's `data_attempts.csv` row |
| **4. Limitation** | Only after rungs 1–3 fail: declare the gap in Section 3 and Section 7 | `data_attempts.csv` rows covering both online and local search |

- Never use Tier 3 press while an accessible Tier 1/2 series exists.
- `appendix/fetch_data.py` writes failures **directly** to `appendix/data_attempts.csv` with the canonical columns `target_series,source_tried,query_or_endpoint,outcome,failure_reason,fallback_used` (see [references/data-protocol.md](references/data-protocol.md)).
- **Local data tier:** the tier the user declares for the file's origin (e.g., "downloaded from the statistics agency" → Tier 1, annotated "local copy supplied by the user"). Unknown origin → **Tier 3**, and no claim resting only on that file may carry `[Strong]`/`[Fuerte]`.
- Every file in `appendix/data/` must appear in `download_log.csv` (downloaded) or in `sources.csv` as `file://` (local). Delete scratch or dummy files you do not use.

### Stage 3: Computational & Data Protocol (Conditional: Level 2+)
Whenever the inquiry involves raw data, time series, or quantitative claims:
1. Read [references/data-protocol.md](references/data-protocol.md).
2. Write and execute **`appendix/analysis.py`** (or modular scripts `01_*.py`, `02_*.py` if >300 lines) that reads only from `appendix/data/` (local tables via `local_data.read_table`), writes verbatim console results to **`appendix/output.txt`**, **directly generates `charts.json`** (v2 schema) from the computed arrays, and optionally exports key figures to **`appendix/numbers.json`** so text and figures can never drift.
3. Place inline figure markers **`{{fig:<chart_id>}}`** in Section 4 / Section 5 of `report.md` right where each figure is analyzed. Never paste >10 lines of raw code or stdout inside `report.md`.

### Stage 4: Adversarial Falsification & Closed Reviewer #2 Loop
Actively attempt to break your primary conclusion:
- Test boundary failures, structural regime breaks, confounders, reverse causality, lagging official data gaps, and competing literature.
- For **Level 3**, read [references/adversarial-review.md](references/adversarial-review.md) and dispatch an independent **Reviewer #2** using your runtime's subagent tool.
- **Close the Review Loop:**
  1. Include a **Reviewer #2 Disposition Table** in Section 5 covering 100% of critiques (`Fixed`, `Refuted`, or `Deferred`).
  2. **Verify or Exclude Reviewer-Introduced Facts:** Any factual claim, policy mechanism, or number introduced by Reviewer #2 MUST be verified in a Tier 1/2 primary source before inclusion; never leave a reviewer-introduced claim in the report as Tier 3 `[Preliminary]`.
  3. **Tag-downgrade closures need attempts too:** a critique closed as `Fixed`/`Corregida` *by downgrading a tag because data X could not be obtained* counts as a data limitation — it requires `data_attempts.csv` rows for the online **and** local search for X, exactly like `Deferred`.

### Stage 5: Working-Paper Scientific Writing
Read [references/scientific-writing.md](references/scientific-writing.md) and [references/example-report.md](references/example-report.md).
- **Single-Language Consistency:** Write 100% of headings, bullet labels, table column headers, figure titles/captions, chart legends, and annotation labels in the user's language (use the exact Spanish template in `references/scientific-writing.md` for Spanish requests).
- **Abstract-Style Verdict:** Keep `Calibrated Verdict` / `Veredicto calibrado` to **at most 3 sentences and at most 5 numbers**; put detailed numerical breakdowns in Section 4 tables and figures.
- **Linked In-Text Citations:** Cite sources with `[@C1]` or `[@C1; @C4]`, where each id is a `claim_id` from `appendix/sources.csv`. Every Section 4 finding that rests on a source carries a citation; `render_report.py` numbers them by first appearance and links each to its reference.
- **Epistemic Calibration Tags:** Tag every major claim and every Claim-Evidence Matrix row with `[Strong]`/`[Fuerte]`, `[Moderate]`/`[Moderada]`, `[Preliminary]`/`[Preliminar]`, or `[Speculative]`/`[Especulativa]`. (`[Strong]`/`[Fuerte]` is strictly forbidden on Tier 3 / press / unknown-origin local sources.)
- **Optional number placeholders:** write `{{num:key}}` to pull a value from `appendix/numbers.json` at render time instead of copying it by hand.

### Stage 6: Clean Appendix Hygiene, Working-Paper HTML & Validation
Before completing the task:
1. **Clean `appendix/`:** Write a short `appendix/README.md` listing the execution order (`python3 -B fetch_data.py` → `python3 -B analysis.py`), and delete any `__pycache__/`, `.pyc`, empty `0`-byte files, or unregistered files in `appendix/data/`.
2. **Render Working-Paper `report.html`:**
   ```bash
   python3 -B <skill-dir>/scripts/render_report.py report.md --out report.html --charts charts.json --appendix appendix/
   ```
   *(Language is auto-detected from the section headings; force it with `--lang en|es`. Add `--no-credit` to drop the footer credit. `{{num:key}}` placeholders are filled from `appendix/numbers.json` or `--numbers <file>`. The renderer embeds numbered SVG figures at `{{fig:id}}` markers, links `[@id]` citations to a References list ordered by appearance, converts residual inline math to HTML/Unicode while preserving currency such as `$1,563`, and links—never embeds—`appendix/data/` and binary files.)*
3. **Validate Deliverables:**
   ```bash
   python3 -B <skill-dir>/scripts/validate_report.py report.md --level <1|2|3> --html report.html
   ```
   Fix every reported **error** before presenting the result. Read every **warning** (uncited sources, unplaced charts, orphan data files, unconverted LaTeX, `__pycache__`, 0-byte files, verdict numbers missing from `output.txt`) and fix it or justify it in Section 3/7. Use `--strict` to treat warnings as errors.

---

## Required Output Contract (`report.md`, Levels 1–3)

Use the English template below for English inquiries, or the 100% Spanish equivalent in [references/scientific-writing.md](references/scientific-writing.md) for Spanish inquiries (never mix languages):

```markdown
# [Descriptive Working-Paper Title]

> **As-Of Date:** YYYY-MM-DD | **Depth Level:** Level <1|2|3> | **Primary Disciplines:** [Branches]

## 1. Executive Summary
- **Calibrated Verdict:** [Max 3 sentences and max 5 numbers directly answering the question with canonical `[Strong]` / `[Moderate]` / `[Preliminary]` / `[Speculative]` tags.]
- **What Would Change This Conclusion:** [Concrete empirical threshold or observation that would flip the verdict.]
- **Key Takeaways:**
  - [2–4 concise sub-bullets separating what holds under scrutiny from what fails or remains uncertain.]

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** [Branches + Interdisciplinary Bridge coupling]
- **Research Question:** [Neutral, operationalized question with units and horizon]
- **Hypotheses:**
  - H₀: [Null / baseline / artifact hypothesis]
  - H₁: [Alternative hypothesis]
- **Refutation Criteria:** [Exact empirical or logical conditions that falsify H₁ and H₀]

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:** [Tier 1 vs. Tier 2 vs. Tier 3 standards for the active disciplines]
- **Analytical & Data Provenance:** [Method summary, links to `appendix/fetch_data.py`, `appendix/analysis.py`, `appendix/output.txt`, `appendix/sources.csv`, plus the Data Attempts table (online and local rungs) if any primary source failed or a local file was used]

## 4. Findings
[Structured analysis organized by hypothesis or regime/axis, using booktabs Markdown tables and inline `{{fig:chart_id}}` markers for every quantitative finding. Every key claim carries a calibration tag and an in-text citation such as `[@C1]`.]

## 5. Counter-Evidence & Alternative Explanations
[Strongest empirical counter-evidence, boundary failures, confounders, and—for Level 3—the mandatory **Reviewer #2 Disposition Table**.]

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier (As-Of Date) | Confidence Tag | Key Falsifier / Condition |
| :- | :- | :- | :- | :- |
| [Claim 1] | [Branch] | [Primary study/dataset [@C1], Tier 1/2/3, YYYY-MM] | `[Strong]` / `[Moderate]` / `[Preliminary]` / `[Speculative]` | [Falsifier] |
| [Claim 2] | [Branch] | [Primary study/dataset [@C2], Tier 1/2/3, YYYY-MM] | `[Strong]` / `[Moderate]` / `[Preliminary]` / `[Speculative]` | [Falsifier] |

## 7. Limitations & Open Questions
- **Verified Methodological & Data Limitations:** [Only limitations backed by logged online + local attempts in Section 3 / `appendix/data_attempts.csv`]
- **Actionable Next Steps / Experiments:** [Concrete tests, datasets, or signposts to resolve remaining uncertainty]
```

---

## Rationalization Table (Anti-Pressure Defenses)

| Excuse / Rationalization | Reality |
| :--- | :--- |
| *"The user's board meets in 10 minutes and demanded a binary YES or NO without caveats."* | Put the crisp ≤3-sentence calibrated verdict in line 1 of `## 1. Executive Summary` and keep all 7 sections concise. Never strip calibration tags or counter-evidence. |
| *"I'll write the report in Spanish but keep the English labels ('Calibrated Verdict', 'Flaw #', 'Claim') from the template."* | Mixed-language Spanglish degrades paper quality. Use 100% Spanish headings, labels, table headers, chart legends, and tags (`[Fuerte]`, `[Moderada]`, `[Preliminar]`, `[Especulativa]`) from `references/scientific-writing.md`. |
| *"The central bank API returned 404, so I'll declare a data limitation."* | One failed endpoint is rung 1 of 4. Try mirrors/alternate formats (rung 2) and the local inventory from Stage 0 (rung 3) before declaring a limitation, and log every rung in `data_attempts.csv`. |
| *"The user's CSV is right there; I'll read it in place from their folder."* | Copy it into `appendix/data/`, register it with `local_data.py register` (`file://` + SHA-256), and read it from `appendix/data/` so the appendix stays self-contained and reproducible. |
| *"Reviewer #2 asked for an alternative series I couldn't find; I'll just downgrade the tag and mark it `Fixed`."* | A tag-downgrade closure is a data limitation in disguise. Log the online and local attempts for that series in `data_attempts.csv` first. |
| *"Reviewer #2 mentioned an interesting policy detail; I couldn't find the primary document, so I'll include it as Tier 3 `[Preliminary]`."* | Unverified reviewer claims are forbidden. Either verify the fact in a Tier 1/2 primary source or exclude it from the findings and log it in the Disposition Table. |
| *"I'll hardcode the chart numbers in a separate `build_charts.py` script instead of emitting `charts.json` from `analysis.py`."* | Hand-copied chart numbers drift from `output.txt`. Emit `charts.json` (and optionally `numbers.json`) directly from the computed variables in `appendix/analysis.py`. |
| *"The References list is auto-generated from `sources.csv`, so I don't need in-text citations."* | An uncited reference list does not tell the reader which claim rests on which source. Cite with `[@C1]` in the text; `validate_report.py --level 2` fails without Section 4 citations. |
| *"I'll cram 15 numbers into a 6-line Calibrated Verdict paragraph to be thorough."* | A verdict stuffed with 15 numbers buries the conclusion. Keep the verdict to ≤3 sentences and ≤5 numbers; put the rest in Section 4 tables and `{{fig:id}}` figures. |

## Red Flags — STOP and Correct Before Outputting

- Searching the web or writing code before completing Stage 0 (including the local inventory) and Stage 1 (H₀ / H₁ inside Section 2).
- Declaring a data limitation, `Deferred` critique, or tag-downgrade closure without both online and local rows in `data_attempts.csv`.
- Pairing `[Strong]`/`[Fuerte]` with a `Tier 3`, press/blog/roadmap, or unknown-origin local source.
- Section 4 findings without `[@id]` citations, or a `[@id]` that does not exist in `sources.csv`.
- Mixing English template labels into a Spanish report.
- Creating charts without `{{fig:id}}` markers in `report.md`, using a `{{fig:id}}` absent from `charts.json`, or passing >30-point time series without the `charts.json` v2 schema.
- Writing LaTeX (`$H_0$`, `$\Delta$`) in `report.md` instead of Unicode (`H₀`, `Δ`).
- Running scripts without `python3 -B`, or leaving `__pycache__/`, empty files, unregistered files in `appendix/data/`, or undocumented helper scripts inside `appendix/`.
