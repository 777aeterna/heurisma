# Calibrated Scientific Writing & Output Formats

Part of **Heurisma** (loaded during **Stage 5** before finalizing any research report).

---

## 1. Epistemic Calibration Scale

Every major claim in `## 1. Executive Summary`, `## 4. Findings`, and `## 6. Claim-Evidence Matrix` MUST carry an explicit bracketed calibration tag:

| Tag | Meaning | Minimum Evidence Required | Forbidden For |
| :--- | :--- | :--- | :--- |
| **`[Strong]`** | High epistemic confidence; robust against plausible confounders | Formal deductive proof; meta-analysis of human RCTs; replicated multi-method field/lab measurements; conservation laws | Single studies, preprints, observational correlations without causal identification, industry forecasts |
| **`[Moderate]`** | Credible empirical support within bounded conditions | Well-designed single RCT, quasi-experimental causal study (DiD/IV/RDD), audited institutional dataset, lab standard with known field caveats | Vendor press releases, small unadjusted samples ($n < 30$), theoretical extrapolations |
| **`[Preliminary]`** | Suggestive or context-limited evidence requiring replication or data audit | Small-sample empirical data, single observational cohort, pilot-line demonstration, unadjusted correlation | Definitive policy mandates or unqualified executive verdicts |
| **`[Speculative]`** | Unverified projection, mechanism hypothesis, or corporate target | OEM commercial roadmap dates, early coin-cell/animal mechanism extrapolated to scale, untested hypothesis | Presenting as established fact or probable baseline without flagging failure risk |

---

## 2. High-Signal Scientific Prose Rules

1. **Answer First, Calibrated:** Open `## 1. Executive Summary` with `- **Calibrated Verdict:**` stating the direct answer and its `[Tag]` in the very first sentence. Never bury the bottom line at the end of a 1,500-word essay, and never strip the calibration tag to sound punchy.
2. **Separate Fact from Forecast:** When citing quantitative figures, name the source tier inline:
   - *Good:* `"Global volume-weighted Li-ion pack prices reached $108/kWh in 2025 (BNEF market survey, Tier 2) [Moderate], whereas automaker targets for 2027 all-solid-state mass production reflect self-reported OEM roadmaps (Tier 3) [Speculative]."`
   - *Bad:* `"Pack prices are $108/kWh and solid-state batteries will enter mass production in 2027."`
3. **Zero Marketing Fluff:** Eliminate throat-clearing introductions (*"In recent years, there has been growing interest..."*), vague intensifiers (*"game-changing"*, *"revolutionary"*), and unquantified adjectives. State physical quantities, effect sizes, sample sizes, and boundary conditions.
4. **Adapt Length to User Constraint Without Dropping Structure:**
   - If the user asks for an **urgent 10-minute board verdict** or **short brief**, keep the entire report under ~450–600 words by using crisp 1–2 bullet entries inside each of the 7 required sections.
   - If the user asks for a **deep technical investigation**, expand `## 4. Findings`, `## 5. Counter-Evidence & Alternative Explanations`, and `## 6. Claim-Evidence Matrix` with full quantitative breakdowns and reproducible scripts.
   - **In both cases, all 7 top-level section headings remain mandatory.**

---

## 3. Pre-Delivery Verification Checklist

Before outputting the report to the user, verify:
- [ ] All 7 required `## N. ...` headings appear in exact order (`1. Executive Summary` through `7. Limitations & Open Questions`).
- [ ] `## 2. Framing & Hypotheses` explicitly states `Scientific Discipline(s) & Depth Level`, `Research Question`, `$H_0$`, `$H_1$`, and `Refutation Criteria`.
- [ ] Every major claim in Sections 1, 4, and 6 includes `[Strong]`, `[Moderate]`, `[Preliminary]`, or `[Speculative]`.
- [ ] If raw data was analyzed (Level 2+), the executed Python code and its exact output are included.
- [ ] `## 6. Claim-Evidence Matrix` contains a valid Markdown table (`| Claim | Discipline / Axis | Evidence & Source Tier | Confidence Tag | Key Falsifier / Condition |`).
