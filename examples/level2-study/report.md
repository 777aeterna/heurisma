# Audit of Internal Pair-Programming Hours vs. Bug-Fix Throughput (12-Team Study)

> **As-Of Date:** 2026-11-20 | **Depth Level:** Level 2 (Empirical / Data Study) | **Primary Disciplines:** Empirical Software Engineering + Observational Causal Inference

## 1. Executive Summary
- **Calibrated Verdict:** The supplied 12-team dataset does not support claiming that pair programming boosts bug-fix throughput `[Strong]`. The apparent positive correlation (r = {{num:full_r_short}}) is a single-point leverage artifact driven by `T12`, and excluding `T12` reverses the relationship to r = {{num:clean_r_short}} `[Moderate]`.
- **What Would Change This Conclusion:** Multi-sprint telemetry normalized per developer-hour and weighted by ticket severity across comparable teams showing a replicated positive effect.
- **Key Takeaways:**
  - Full-sample Pearson r = {{num:full_r}} diverges sharply from full-sample Spearman ρ = {{num:full_rho}}, exposing extreme leverage from `T12` [@C1; @C2] `[Strong]`.
  - Across typical teams (`T01`–`T11`), both parametric and rank correlations are negative with narrow bootstrap 95% confidence intervals [@C1; @C2] `[Moderate]`.
  - Uncontrolled confounders (headcount, ticket severity, reverse causality) prevent drawing any causal conclusion from this cross-section [@C1] `[Preliminary]`.

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** Engineering & Applied Sciences (Empirical Software Engineering) + Social Sciences & Economics (Observational Causal Inference) | **Level 2**.
- **Research Question:** In this 12-team internal cross-section, is weekly `pair_hours` robustly associated with higher weekly `bugs_fixed`, or is the apparent positive linear trend an outlier-leverage artifact?
- **Hypotheses:**
  - H₀: No positive monotonic association exists across typical teams; the full-sample positive r is driven by an extreme leverage observation or unmeasured confounders.
  - H₁: Higher `pair_hours` is consistently and positively associated with higher `bugs_fixed`, surviving non-parametric rank tests and outlier removal.
- **Refutation Criteria:** H₁ is falsified if full-sample Spearman ρ ≤ 0 or if removing flagged outliers flips Pearson r ≤ 0.

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:** Tier 1 = controlled crossover experiments and audited normalized telemetry; Tier 2 = multi-sprint panels with headcount/severity covariates; Tier 3 = unadjusted single-week aggregate counts.
- **Analytical & Data Provenance:** All computations were executed in [`appendix/analysis.py`](appendix/analysis.py) [@C2] (see [`appendix/README.md`](appendix/README.md)) on the supplied dataset [@C1], archiving verbatim output in [`appendix/output.txt`](appendix/output.txt), key numbers in [`appendix/numbers.json`](appendix/numbers.json), sources in [`appendix/sources.csv`](appendix/sources.csv), and emitting `charts.json` directly.

| Target Variable | Source Tried | Method | Outcome | Fallback |
| :- | :- | :- | :- | :- |
| Team headcount & ticket severity | User prompt CSV | Schema inspection | Not included in supplied table | Flagged as missing covariate; causal claims capped at `[Preliminary]` |

## 4. Findings
1. **Extreme Single-Row Leverage (`T12`):** `T01`–`T11` span `2–7` `pair_hours` (median `4.50`, MAD `1.50`) and `11–16` `bugs_fixed` (median `13.50`, MAD `1.50`), whereas `T12` reports `45` `pair_hours` and `88` `bugs_fixed`, exceeding both median + 3 × IQR and |z| > 2.5 [@C1; @C2] `[Strong]`.

{{fig:team_scatter}}

2. **Parametric, Rank & Bootstrap Sensitivity:**

| Scope | n | Pearson r | 95% Bootstrap CI (r) | Spearman ρ |
| :- | -: | -: | :- | -: |
| Full Sample (`T01`–`T12`) | 12 | {{num:full_r}} | `[-0.8880, +0.9957]` | {{num:full_rho}} |
| Clean Sample (`T01`–`T11`, excl. `T12`) | 11 | {{num:clean_r}} | `[-0.9472, -0.5499]` | {{num:clean_rho}} |

{{fig:corr_sens}}

3. **Falsification of H₁:** Full-sample bootstrap CI for Pearson r spans `[-0.89, +1.00]` (crossing zero because draws omitting `T12` flip sign), confirming the positive trend is entirely an outlier artifact [@C1; @C2] `[Strong]`.

## 5. Counter-Evidence & Alternative Explanations
- **Scale / Aggregation Mismatch (`T12`):** `T12` is consistent with a multi-squad roll-up, a monthly total logged in a weekly column, or bulk automated ticket closure [@C1] `[Preliminary]`.
- **Reverse Causality & Missing Denominators (`T01`–`T11`):** Teams handling harder, high-severity defects pair more often and close fewer tickets per week `[Speculative]`, while raw counts omit headcount and post-fix defect reopen rates `[Moderate]`.

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier (As-Of Date) | Confidence Tag | Key Falsifier / Condition |
| :- | :- | :- | :- | :- |
| Full-sample r = {{num:full_r}} is a `T12` leverage artifact | Causal Inference | Supplied CSV [@C1] (Tier 2) analyzed by the own bootstrap & sensitivity audit [@C2] (own computation, `appendix/analysis.py`), 2026-11 | `[Strong]` | Replicated positive slope across independent comparable teams |
| Among `T01`–`T11`, pairing and bugs fixed correlate negatively (r = {{num:clean_r}}) | Software Engineering | Leave-one-out audit on supplied CSV [@C1] (`appendix/output.txt`, Tier 2, 2026-11) | `[Moderate]` | Normalization by team size or ticket severity |
| Reverse causality (bug complexity) explains the negative slope | Causal Inference | Structural audit of missing covariates (Tier 3, 2026-11) | `[Speculative]` | Controlled crossover pilot controlling for ticket difficulty |

## 7. Limitations & Open Questions
- **Verified Methodological & Data Limitations:** Small cross-section (n = 12); team headcount, ticket severity, reporting-period verification for `T12`, and defect reopen rates were absent from the supplied CSV (logged in Section 3).
- **Actionable Next Steps / Experiments:** Audit `T12`'s reporting definition, normalize metrics per developer-hour weighted by severity across multiple sprints, and run a controlled crossover pilot tracking both throughput and regression rates.
