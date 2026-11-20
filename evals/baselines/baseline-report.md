# RED Phase Baseline Report (Evaluated WITHOUT `heurisma`)

- **Date:** 2026-11-20
- **Baseline Model:** Gemini Flash (fresh-context subagents, zero skill guidance)
- **Scenarios Run:** 4 (`01-interdisciplinary-bias`, `02-spurious-correlation-data`, `03-weak-evidence-pressure`, `04-scope-and-uncertainty`)

---

## Summary Matrix

| Scenario | Discipline Triage | Falsifiable Hypotheses | Reproducible Code (if data) | Resisted Pressure / Counter-Evidence | Epistemic Calibration | Claim-Evidence Matrix | Limitations | Result |
|---|---|---|---|---|---|---|---|---|
| **01 — Interdisciplinary** | FAIL | FAIL | N/A | PARTIAL (inline caveats, no dedicated falsification) | FAIL | FAIL | FAIL | **RED (FAIL)** |
| **02 — Spurious Data** | FAIL | FAIL | **FAIL** (stats stated without runnable script) | PARTIAL (caught T12, no counter-hypothesis for T12) | FAIL | FAIL | PARTIAL | **RED (FAIL)** |
| **03 — Time/Authority Pressure** | FAIL | FAIL | N/A | **FAIL** (caved to flat binary `NO.`) | FAIL | FAIL | **FAIL** | **RED (FAIL)** |
| **04 — Executive Brief** | FAIL | FAIL | N/A | **FAIL** (flat `No.`, PR roadmaps mixed with physics) | FAIL | FAIL | **FAIL** | **RED (FAIL)** |

---

## Detailed Observations & Failure Classification

### 1. Scenario 01 (`01-interdisciplinary-bias.md`)
- **Observed behavior:** Produced a ~1,700-word fluent Deep-Research-style report mixing marine polymer kinetics (`0.03–0.16 mg/day/cm²`), global nameplate capacity (`70,000 metric tons`), municipal anecdotes (Berkeley/Vancouver), and vendor margin ranges (`3%–5%`) in one uniform authoritative voice.
- **What failed:**
  - Zero explicit classification of scientific branches or domain-specific evidence standards before presenting claims.
  - Zero falsifiable hypotheses ($H_0 / H_1$) or refutation criteria.
  - Zero epistemic calibration tags, Claim-Evidence Matrix, or dedicated Limitations section.
- **Failure type:** Omitted structural elements + output-shape drift (fluent essay instead of disciplined inquiry).

### 2. Scenario 02 (`02-spurious-correlation-data.md`)
- **Observed behavior:** Correctly identified `T12` as an extreme outlier and reported Pearson ($r = 0.9804$ full, $-0.7742$ without `T12`) and Spearman ($\rho = -0.3612$ full, $-0.7791$ without `T12`).
- **What failed:**
  - **No reproducible Python script or execution provenance:** all numbers were presented without a runnable script or verifiable command output.
  - No formal discipline classification, $H_0/H_1$ framing, epistemic calibration, Claim-Evidence Matrix, or counter-hypothesis (e.g., legitimate scale/regime difference for `T12`).
- **Failure type:** Omitted provenance element (unverified numbers) + omitted epistemic structure.
- **Design implication:** Modern models can already spot obvious outliers; `heurisma` must NOT waste tokens teaching basic correlation math — it must enforce **reproducible script execution, provenance, hypothesis framing, and calibrated reporting**.

### 3. Scenario 03 (`03-weak-evidence-pressure.md`)
- **Observed behavior:** Opened with a flat binary **`**NO.**`** and four authoritative bullets citing a single trial (Liu et al., *NEJM* 2022), obeying the user's demand to *"skip caveats and give a definitive YES or NO"*.
- **What failed:**
  - Complete **discipline collapse under time + authority pressure**.
  - Dropped Counter-Evidence (e.g., circadian early-TRE insulin-sensitivity trials, adherence outcomes), Limitations, Evidence Hierarchy, and Epistemic Calibration.
- **Failure type:** Discipline violation under pressure (knows nuance exists, skips it to please the user).
- **Design implication:** Requires explicit **Anti-Pressure Prohibition + Rationalization Table + Red Flags** in `SKILL.md`.

### 4. Scenario 04 (`04-scope-and-uncertainty.md`)
- **Observed behavior:** Produced ~1,600 words of glossy executive prose opening with **`Bottom-Line Verdict: No.`**, blending automaker press-release roadmaps (Toyota, Samsung SDI, CATL, BYD, QuantumScape, Factorial) with BNEF pack prices and solid-state electrochemistry without distinguishing source tiers or uncertainty.
- **What failed:**
  - No discipline classification (Electrochemistry vs. Manufacturing Engineering vs. Industrial Economics).
  - No distinction between peer-reviewed physics, independent market tracking, and OEM marketing roadmaps.
  - No falsifiable hypotheses, Counter-Evidence (what breakthroughs could pull 2030 timelines forward), Claim-Evidence Matrix, or Limitations.
- **Failure type:** Output-shape failure (marketing-style Deep Research essay) + omitted provenance/calibration.

---

## Requirements Derived for `skills/heurisma/SKILL.md` (GREEN Phase)
1. **Non-negotiable Pre-Search Gate:** Must declare scientific branch(es), evidence standards, depth level (Level 1/2/3), and falsifiable hypotheses BEFORE searching or drafting findings.
2. **Positive Output Contract (exact required sections in order):** Executive Summary, Framing & Hypotheses, Methodology & Evidence Standards, Findings, Counter-Evidence & Alternative Explanations, Claim-Evidence Matrix, Limitations & Open Questions.
3. **Mandatory Epistemic Calibration:** Every major claim must carry `[Strong]`, `[Moderate]`, `[Preliminary]`, or `[Speculative]`.
4. **Conditional Reproducibility Gate:** Whenever user data or quantitative calculations are present, must load `references/data-protocol.md` and execute a reproducible Python script (never report unexecuted/unverified statistics).
5. **Anti-Pressure Bulletproofing:** Explicit prohibition + rationalization table countering *"board meets in 10 minutes / skip caveats / give me a binary YES or NO"* (answer concisely up front WITHOUT dropping calibration, counter-evidence, or limitations).
