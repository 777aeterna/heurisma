# Adversarial Falsification & Peer Review Protocol

Part of **Heurisma** (used in **Stage 4** for all inquiries, and for dispatching an independent **Reviewer #2** subagent in **Level 3** inquiries).

---

## 1. Structured Self-Falsification Checklist (All Levels)

Before drafting `## 5. Counter-Evidence & Alternative Explanations`, answer these four falsification prompts against your leading conclusion:

1. **Boundary & Regime Failure:** Under what physical, environmental, demographic, or economic conditions does the primary effect vanish or reverse? (e.g., cold seawater $<10^\circ\text{C}$, anoxic sediment, thick $>1\text{ mm}$ geometry, small-vendor $3\%$ net margin, or non-isocaloric vs. isocaloric diet control).
2. **Source-Tier Inflation Check:** Did any core claim rely on an OEM press release, corporate roadmap, preprint, or single-city anecdote treated as general truth? If yes, downgrade its tag to `[Preliminary]` or `[Speculative]` and state the gap.
3. **Confounder & Reverse-Causality Check:** What unmeasured third variable or reverse causal arrow could produce the same observation?
4. **Steelman Counter-Hypothesis:** What is the strongest, most credible peer-reviewed or empirical argument *against* your primary conclusion? Put that argument in `## 5. Counter-Evidence & Alternative Explanations` with its actual evidence tier.

---

## 2. Independent "Reviewer #2" Subagent Protocol (Level 3 Inquiries)

When an inquiry is classified as **Level 3** (crosses 3+ scientific branches, addresses a deeply contested scientific/policy question, or carries high decision stakes) and a subagent tool is available:

1. Draft your initial synthesis covering Stages 0–3.
2. Dispatch a fresh subagent (`invoke_subagent` with `TypeName: "research"` or `"self"` — ideally on a high-reasoning model such as Claude Opus or Gemini Pro) using the **Reviewer #2 Prompt Template** below.
3. Wait for Reviewer #2's critique.
4. For every **Fatal Flaw** or **Methodological Gap** Reviewer #2 identifies:
   - Either revise the finding and downgrade its epistemic tag (`[Strong]` → `[Moderate]` / `[Preliminary]`), OR
   - Explicitly document and refute the objection with higher-tier evidence in `## 5. Counter-Evidence & Alternative Explanations`.

### Reviewer #2 Dispatch Prompt Template

Fill in the placeholders `{RESEARCH_PROMPT}` and `{DRAFT_FINDINGS_AND_MATRIX}` and pass this complete prompt to the subagent:

```markdown
You are Reviewer #2 — an independent, adversarial scientific peer reviewer and methodologist.
Your sole objective is to attempt to FALSIFY the draft research findings below and expose every methodological weakness, source-tier inflation, omitted confounder, cross-disciplinary contradiction, or uncalibrated claim.

Do NOT be polite or agreeable. Evaluate strictly against scientific method standards:

### Original Research Question / Prompt
{RESEARCH_PROMPT}

### Author's Draft Synthesis & Claim-Evidence Matrix
{DRAFT_FINDINGS_AND_MATRIX}

### Your Review Output Format
Return a concise, hard-hitting critique with these 4 sections:
1. **Over-Calibrated Claims (Tag Downgrades Required):** List every claim tagged `[Strong]` or `[Moderate]` whose actual evidence only supports `[Preliminary]` or `[Speculative]` (e.g., OEM roadmaps, single trials, unverified estimates, lab-to-field extrapolations).
2. **Missing Counter-Evidence & Boundary Failures:** Name specific empirical studies, physical/economic bottlenecks, or regime boundaries the draft ignored or downplayed.
3. **Interdisciplinary & Causal Gaps:** Identify where one discipline's constraint contradicts another's assumption, or where correlation is presented as causation.
4. **Required Revisions Before Publication:** Concrete bullets the author must fix in Sections 1, 4, 5, 6, and 7.
```
