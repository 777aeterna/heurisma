# Adversarial Falsification & Closed-Loop Peer Review Protocol

Part of **Heurisma** (used in **Stage 4** for all inquiries, and for dispatching and closing an independent **Reviewer #2** subagent audit in **Level 3** inquiries).

---

## 1. Structured Self-Falsification Checklist (All Levels)

Before drafting `## 5. Counter-Evidence & Alternative Explanations`, answer these four falsification prompts against your leading conclusion:

1. **Boundary & Regime Failure:** Under what physical, environmental, demographic, or macroeconomic conditions does the primary effect vanish or reverse?
2. **Source-Tier Inflation Check:** Did any core claim rely on a press article, corporate roadmap, preprint, or single anecdote treated as general truth? If yes, downgrade its tag to `[Preliminary]`/`[Preliminar]` or `[Speculative]`/`[Especulativa]` and state the gap.
3. **Confounder, Lag & Reverse-Causality Check:** What unmeasured third variable, lag structure, or reverse causal arrow could produce the same observation?
4. **Steelman Counter-Hypothesis:** What is the strongest, most credible peer-reviewed or empirical argument *against* your primary conclusion? Present that argument in Section 5 with its actual evidence tier.

---

## 2. Independent "Reviewer #2" Subagent Protocol (Level 3 Inquiries)

When an inquiry is classified as **Level 3** and your runtime provides a subagent tool (e.g., `Agent` in Claude Code, `invoke_subagent` in Antigravity, or equivalent fresh-context agent dispatch):

### Step 1: Dispatch Reviewer #2
Draft your initial synthesis covering Stages 0–3, then dispatch a fresh-context subagent—preferably on a high-reasoning model—using the **Reviewer #2 Dispatch Prompt Template** below.

### Step 2: STRICT Rule — Verify in Tier 1/2 or Exclude Reviewer-Introduced Facts
Reviewer #2 can hallucinate or misstate facts just like any model. If Reviewer #2 introduces a new statistic, policy detail, historical date, or external agreement (e.g., a currency swap, regulatory clause, or clinical trial) to critique your draft:
- **You MUST verify it in a primary source (Tier 1 or Tier 2)** before including it in your report.
- **FORBIDDEN:** You are strictly forbidden from including an unverified Reviewer #2 claim in `report.md` and tagging it as Tier 3 `[Preliminary]` with a *"not independently verified"* note. If you cannot verify a reviewer's factual assertion in a primary source after a logged attempt, **exclude the assertion from the report findings** and record the exclusion in the Disposition Table.

### Step 3: Mandatory Reviewer #2 Disposition Table (Close the Loop)
Every Level 3 report MUST include a **Reviewer #2 Disposition Table** in Section 5 accounting for **100% of Reviewer #2's critiques** (match the report's language — English or Spanish):

**English Template:**
```markdown
### Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | [Exact methodological or data flaw raised] | `Fixed` | [What changed in appendix/analysis.py or Section 4] |
| 2 | [Alternative claim or unverified fact from reviewer] | `Refuted` | [Primary Tier 1/2 evidence falsifying or excluding the claim] |
| 3 | [Request requiring inaccessible proprietary dataset] | `Deferred` | [Logged in appendix/data_attempts.csv with HTTP/failure reason] |
```

**Spanish Template (100% Spanish — no English headers):**
```markdown
### Disposición del Revisor #2
| Falla # | Crítica del revisor | Acción | Evidencia / Artefacto |
| :- | :- | :- | :- |
| 1 | [Falla metodológica o de datos señalada] | `Corregida` | [Cambio ejecutado en appendix/analysis.py o Sección 4] |
| 2 | [Afirmación alternativa o dato no verificado del revisor] | `Refutada` | [Evidencia primaria Tier 1/2 que la refuta o motivo de exclusión] |
| 3 | [Pedido de serie privada inaccesible tras intento real] | `Diferida` | [Registrado en appendix/data_attempts.csv con motivo concreto] |
```

Valid `Action` / `Acción` values checked by `validate_report.py --level 3` (with or without backticks):
- **`Fixed`** / **`Corregida`**: You executed the additional regression/fetch/re-calibration and updated the report.
- **`Refuted`** / **`Refutada`**: You disproved Reviewer #2's objection using Tier 1/2 evidence (or excluded an unverifiable reviewer claim after a primary check).
- **`Deferred`** / **`Diferida`**: The requested data are genuinely inaccessible *after* logging a real online fetch attempt **and** a local search in `appendix/data_attempts.csv` (checked automatically by `validate_report.py --level 3`).

### Step 4: Tag-Downgrade Closures Count as Data Limitations (Iron Law 3)
A critique is sometimes closed as `Fixed` / `Corregida` **by downgrading a tag** because the data needed to defend the original tag could not be obtained (e.g., *"downgraded to `[Preliminary]` because no alternative CPI series for 2007–2015 was found"*). That closure is a data limitation in disguise:
- Before writing it, walk the 4-rung cascade (online primary → online alternatives → local inventory → limitation) for the missing series.
- Log every failed rung in `appendix/data_attempts.csv` with the canonical columns, and reference the row in the Evidence / Artifact cell.
- A downgrade with no matching `data_attempts.csv` row is an unattempted shortcut; Reviewer #2 category 2 applies to it.

```markdown
| 4 | Pre-2016 CPI series not cross-checked against provincial indices | `Fixed` | Tag downgraded to `[Preliminary]`; provincial-index search online + `local_data.py inventory` logged in appendix/data_attempts.csv (rows 3–4) |
```

---

## 3. Reviewer #2 Dispatch Prompt Template

Fill in `{RESEARCH_PROMPT}` and `{DRAFT_FINDINGS_AND_MATRIX}` and pass to your subagent tool:

```markdown
You are Reviewer #2 — an independent, adversarial scientific peer reviewer and methodologist.
Your sole objective is to attempt to FALSIFY the draft research findings below and expose every methodological weakness, source-tier inflation, unattempted data shortcut, omitted confounder, cross-disciplinary contradiction, or uncalibrated forecast.

Do NOT be polite or agreeable. Evaluate strictly against scientific method standards:

### Original Research Question / Prompt
{RESEARCH_PROMPT}

### Author's Draft Synthesis, Data Attempts & Claim-Evidence Matrix
{DRAFT_FINDINGS_AND_MATRIX}

### Your Review Output Format
Return a numbered list of concrete flaws across these 4 categories (every numbered item will require an explicit Fixed / Refuted / Deferred row in the author's final Disposition Table):
1. **Over-Calibrated Claims (Tag Downgrades Required):** Every claim tagged `[Strong]` or `[Moderate]` whose actual source tier or sample size only supports `[Preliminary]` or `[Speculative]`.
2. **Unattempted Data Shortcuts & Primary-Source Gaps:** Where the author relied on Tier 3 press/blogs, declared a "data limitation", or closed a critique by downgrading a tag when an accessible primary institutional series, archive, mirror, local file, or proxy exists (check `data_attempts.csv` for both online and local rungs).
3. **Missing Counter-Evidence, Regressions & Boundary Failures:** Specific statistical controls, lag regressions, regime separations, base-rate calibrations, or canonical literature the draft omitted.
4. **Interdisciplinary & Forecasting Flaws:** Where an accounting identity was confused with a forecast, units were mixed (EoP vs. average, nominal vs. real), or one discipline's constraint invalidates another's assumption.
```
