# Reference Working-Paper Example (`report.md` Pattern)

Part of **Heurisma** (loaded during **Stage 5** so the agent imitates the exact abstract density, single-language discipline, linked citations, booktabs tables, `{{fig:id}}` inline figure placement, and data-attempt logging).

---

## Model Pattern to Imitate

Notice six properties of the reference report below:
1. **Crisp Abstract Verdict:** Section 1's `Calibrated Verdict` is **2 sentences with 3 key numbers**—not a 15-number paragraph. The renderer promotes it to the HTML Abstract without repeating it in §1.
2. **Linked In-Text Citations:** Every sourced claim carries `[@C1]` / `[@C2]` matching `claim_id` values in `appendix/sources.csv` (here `C1` = the user-supplied CSV, `kind = data`, Tier 2; `C2` = the reproducible audit script, `kind = own-computation`, Tier 2 — the report's own code checks a computation on `C1`, it is never independent Tier 1 evidence). The renderer turns them into numbered links `[1]`, `[2]`.
3. **Unicode Math, No LaTeX:** `H₀`, `H₁`, `ρ`, `≤`, `×` are written directly; currency-like `$` never needs escaping.
4. **Zero Code / Stdout Dumps:** All computation lives in `appendix/analysis.py` and `appendix/output.txt`; Section 4 summarizes findings in a clean table and places `{{fig:corr_comparison}}` inline.
5. **Explicit Data Attempts (Online + Local):** Section 3 logs the missing covariates with the online and local rungs tried, so the limitation in Section 7 is earned.
6. **Substantive Claim-Evidence Matrix:** Every row carries a specific source with its citation, tier, `YYYY-MM` date, canonical tag, and concrete falsifier.

```markdown
# Audit of Internal Pair-Programming Hours vs. Bug-Fix Throughput Across Engineering Squads

> **As-Of Date:** 2026-11-20 | **Depth Level:** Level 2 (Empirical / Data Study) | **Primary Disciplines:** Empirical Software Engineering + Observational Causal Inference

## 1. Executive Summary
- **Calibrated Verdict:** The supplied 12-squad dataset does not support claiming that weekly pair programming increases bug-fix throughput `[Strong]`. The apparent full-sample correlation (r = +0.98) is a single-point leverage artifact driven by squad `T12`, and excluding `T12` reverses it among the remaining 11 squads to r = −0.77 `[Moderate]`.
- **What Would Change This Conclusion:** Multi-sprint longitudinal telemetry normalized per developer-hour and weighted by defect severity showing a positive within-squad effect under a controlled crossover design.
- **Key Takeaways:**
  - Full-sample Pearson r = +0.9804 diverges from rank correlation ρ = −0.3612, diagnosing extreme outlier leverage [@C2] `[Strong]`.
  - Across typical squads (`T01`–`T11`), pairing hours and raw bug fixes correlate negatively (r = −0.7742, 95% bootstrap CI `[−0.95, −0.55]`) [@C2] `[Moderate]`.
  - Because the dataset lacks squad headcount and defect complexity controls, neither a positive nor negative causal effect can be inferred [@C1] `[Preliminary]`.

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** Engineering & Applied Sciences (Empirical Software Engineering) + Social Sciences & Economics (Observational Causal Inference) | **Level 2**. Software Engineering governs defect-metric validity, while Causal Inference governs leverage diagnostics and confounding.
- **Research Question:** Across the 12 observed engineering squads, is weekly pair-programming time robustly associated with higher weekly bug-fix counts after accounting for outlier leverage and rank order?
- **Hypotheses:**
  - H₀: No positive monotonic relationship exists across typical squads; the full-sample positive slope is an outlier artifact or confounded by squad scale and ticket complexity.
  - H₁: Higher weekly pair-programming hours are positively associated with higher weekly bug-fix throughput across both parametric and non-parametric estimators.
- **Refutation Criteria:** H₁ is falsified if full-sample Spearman ρ ≤ 0 or if removing observations beyond median + 3 × IQR reduces Pearson r to ≤ 0.

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:** Tier 1 = randomized/crossover squad trials and audited developer-hour telemetry; Tier 2 = multi-sprint observational panels with headcount and severity covariates; Tier 3 = unadjusted single-week aggregate counts.
- **Analytical & Data Provenance:** The user-supplied CSV [@C1] was copied into `appendix/data/` and registered with its SHA-256; all computations run via [`appendix/analysis.py`](appendix/analysis.py) [@C2] (see [`appendix/README.md`](appendix/README.md)), archiving console output in [`appendix/output.txt`](appendix/output.txt) and figure specifications in `charts.json`.

| Target Variable | Source Tried | Query / Endpoint | Outcome & Reason | Fallback Used |
| :- | :- | :- | :- | :- |
| Squad headcount & ticket severity | Supplied internal CSV | Schema audit (`local_data.py preview`) | Columns absent in source extract | — |
| Squad headcount & ticket severity | Local inventory (`./data`, `./datos`) | `local_data.py inventory` | No HR or tracker export found | Causal claims capped at `[Preliminary]` |

## 4. Findings

### 4.1 Leverage Diagnostics and Robust Dispersion
Across `T01`–`T11`, weekly pairing spans `2.0–7.0` hours (median `4.50`, MAD `1.50`) and bugs fixed spans `11.0–16.0` (median `13.50`, MAD `1.50`) [@C1] `[Strong]`. Squad `T12` (`45.0` pair hours, `88.0` bugs fixed) sits more than 6× above the cohort maximum on both axes, exceeding median + 3 × IQR and |z| > 2.5 [@C2] `[Strong]`.

| Analytical Scope | n | Pearson r | 95% Bootstrap CI (r) | Spearman ρ | OLS Slope (bugs / hr) |
| :- | -: | -: | :- | -: | -: |
| Full Sample (`T01`–`T12`) | 12 | +0.9804 | `[−0.8880, +0.9957]` | −0.3612 | +1.7873 |
| Clean Sample (`T01`–`T11`, excl. `T12`) | 11 | −0.7742 | `[−0.9472, −0.5499]` | −0.7791 | −0.7742 |

{{fig:corr_comparison}}

### 4.2 Falsification of H₁
Because the full-sample bootstrap confidence interval spans `[−0.89, +1.00]`—flipping sign whenever resamples omit `T12`—and the clean sample exhibits a negative correlation (r = −0.7742) [@C1; @C2], H₁ is falsified within this dataset `[Strong]`.

{{fig:team_scatter}}

## 5. Counter-Evidence & Alternative Explanations
- **Aggregation Anomaly (`T12`):** `T12`'s volume (`45` hours, `88` fixes) is consistent with a multi-squad department rollup or a full-month total entered into a weekly row rather than a comparable squad [@C1] `[Preliminary]`.
- **Reverse Causality Among Typical Squads (`T01`–`T11`):** Squads assigned complex architectural bugs naturally pair more hours while closing fewer tickets per week `[Speculative]`, and unadjusted ticket counts ignore post-release regression rates `[Moderate]`.

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier (As-Of Date) | Confidence Tag | Key Falsifier / Condition |
| :- | :- | :- | :- | :- |
| Within the supplied dataset, full-sample r = +0.9804 is a single-point `T12` leverage artifact | Causal Inference | Supplied CSV [@C1], Tier 2, analyzed by the own sensitivity & bootstrap audit [@C2] (own computation), 2026-11 | `[Strong]` | Replicated positive slope across independent comparable squads |
| Excluding `T12`, pairing and bug fixes correlate negatively (r = −0.7742) | Software Engineering | Leave-one-out audit on supplied CSV [@C1], Tier 2, 2026-11 | `[Moderate]` | Normalization by squad headcount and ticket story points |
| Reverse causality (bug difficulty) drives the negative `T01`–`T11` slope | Causal Inference | Structural confounder reasoning, no direct data (Tier 3, 2026-11) | `[Speculative]` | Controlled crossover trial matching defect complexity |

## 7. Limitations & Open Questions
- **Verified Methodological & Data Limitations:** Small cross-sectional sample (n = 12); squad headcount, ticket severity weights, `T12` reporting window, and defect reopen rates are missing from the supplied CSV and from the local inventory (both logged in Section 3).
- **Actionable Next Steps / Experiments:** Verify `T12`'s reporting scope, normalize metrics as `pair_hours_per_engineer` and `severity_weighted_fixes_per_engineer_hour`, and run a 4-sprint crossover pilot tracking both throughput and escaped defects.
```
