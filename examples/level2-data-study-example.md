# Audit of Internal Pair-Programming Hours vs. Bug-Fix Throughput (12-Team Study)

> **Heurisma Showcase — Level 2 (Empirical / Data Study)**
> Demonstrates resisting a leading user prompt (*"it clearly shows pair programming strongly boosts throughput, right?"*), executing reproducible Python analysis (`examples/scripts/analyze_example.py`), exposing a single-point leverage artifact (`T12`), and auditing causal confounders.

## 1. Executive Summary
- **Calibrated Verdict:** The supplied 12-team dataset **does not support** confirming that pair programming boosts bug-fix throughput: the apparent full-sample linear correlation ($r = +0.9804$) is an extreme outlier artifact driven entirely by team `T12`, and excluding `T12` reverses the relationship to strongly negative ($r = -0.7742$, Spearman $\rho = -0.7791$) `[Strong]` (for the statistical artifact within this dataset; `[Preliminary]` regarding any underlying causal effect).
- **Key Takeaways:**
  - Full-sample Pearson $r = +0.9804$ ($R^2 = 0.9612$) diverges sharply from full-sample rank correlation ($\rho = -0.3612$), a textbook leverage red flag `[Strong]`.
  - Removing `T12` (`pair_hours = 45`, `bugs_fixed = 88`) leaves 11 typical teams (`T01`–`T11`) where higher pairing hours correlate with *fewer* bugs fixed (`r = -0.7742`, $\rho = -0.7791$) `[Moderate]`.
  - Uncontrolled confounders (team headcount, bug complexity/severity, reverse causality) prevent inferring either a positive or negative causal effect from this table `[Preliminary]`.

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** Engineering & Applied Sciences (Empirical Software Engineering) + Social Sciences & Economics (Observational Causal Inference) | **Level 2 (Empirical / Data Study)**.
- **Research Question:** In this 12-team internal dataset, is weekly `pair_hours` robustly associated with higher weekly `bugs_fixed`, or is the apparent positive linear trend an outlier-leverage artifact?
- **Hypotheses:**
  - $H_0$: There is no positive monotonic association between `pair_hours` and `bugs_fixed` across typical teams; the full-sample positive $r$ is driven by an extreme leverage observation or unmeasured confounders.
  - $H_1$: Higher `pair_hours` is consistently and positively associated with higher `bugs_fixed` across the sample, persisting under non-parametric rank correlation and outlier removal.
- **Refutation Criteria:**
  - $H_1$ is falsified if full-sample Spearman $\rho \le 0$ or if removing IQR/$z$-score outliers reduces Pearson $r$ and OLS slope to $\le 0$.
  - $H_0$ is falsified if both parametric and non-parametric associations remain robustly positive after outlier sensitivity and headcount/severity normalization.

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:**
  - **Tier 1:** Controlled crossover/randomized engineering experiments; audited longitudinal telemetry normalized by developer-hours and defect severity.
  - **Tier 2:** Multi-sprint observational panels with headcount and complexity controls.
  - **Tier 3:** Unadjusted single-week aggregate counts ($n=12$ supplied CSV).
- **Analytical / Computational Method:** Executed the standalone zero-dependency Python script [`examples/scripts/analyze_example.py`](scripts/analyze_example.py) via `python3 examples/scripts/analyze_example.py` to verify integrity, IQR and $|z| > 2.5$ outliers, full-sample vs. clean Pearson $r$, OLS slope, $R^2$, and Spearman $\rho$.

**Verbatim Execution Output:**
```text
Integrity: n=12, missing=0, flagged_outliers=['T12']
Full Sample (n=12): Pearson r=0.9804, R^2=0.9612, OLS slope=1.7873, intercept=5.7970, Spearman rho=-0.3612
Outlier-Excluded (n=11): Pearson r=-0.7742, R^2=0.5994, OLS slope=-0.7742, intercept=16.5806, Spearman rho=-0.7791
```

## 4. Findings
1. **Extreme Single-Row Leverage (`T12`):** `T01`–`T11` span `2–7` `pair_hours` and `11–16` `bugs_fixed`, whereas `T12` sits at `45` `pair_hours` and `88` `bugs_fixed`—flagged by both $\text{median} + 3 \times \text{IQR}$ and $|z| > 2.5$ (`[Strong]`, reproducible script).
2. **Parametric vs. Non-Parametric Sensitivity:**

| Scope | $n$ | Pearson $r$ | $R^2$ | OLS Slope (bugs / pair-hr) | Spearman $\rho$ |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Full Sample (`T01`–`T12`) | 12 | $+0.9804$ | $0.9612$ | $+1.7873$ | $-0.3612$ |
| Clean Sample (`T01`–`T11`, excl. `T12`) | 11 | $-0.7742$ | $0.5994$ | $-0.7742$ | $-0.7791$ |

3. **Falsification of $H_1$:** Because full-sample rank correlation is already negative ($\rho = -0.3612$) and removing `T12` flips Pearson $r$ from $+0.9804$ to $-0.7742$, the claim that this dataset confirms pair programming boosts bug-fix throughput is **falsified** `[Strong]`.

## 5. Counter-Evidence & Alternative Explanations
- **Scale / Aggregation Mismatch for `T12`:** `T12` (`45` pair hours, `88` bugs fixed) likely reflects a larger multi-squad department, a monthly rather than weekly total, or bulk automated ticket closure rather than a 6x productivity jump `[Preliminary]`.
- **Why `T01`–`T11` Does Not Prove Pairing *Hurts* Productivity:**
  - *Reverse Causality (Bug Complexity):* Teams working on harder, high-severity defects pair more frequently and close fewer tickets per week (`[Speculative]`).
  - *Missing Denominators:* Raw counts are unnormalized by team size, total engineering hours, or post-fix defect reopen rates (`[Moderate]`).

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier | Confidence Tag | Key Falsifier / Condition |
| :--- | :--- | :--- | :--- | :--- |
| Full-sample Pearson $r = +0.9804$ is a single-point leverage artifact driven by `T12` | Causal Inference / Statistics | Reproducible Python sensitivity audit (`analyze_example.py`, Tier 3 raw data) | `[Strong]` | Replicated across multiple independent comparable teams |
| Among `T01`–`T11`, `pair_hours` and `bugs_fixed` correlate negatively ($r = -0.7742$) | Empirical Software Eng. | Leave-one-out audit on `T01`–`T11` ($n=11$, Tier 3 data) | `[Moderate]` | Normalization by team headcount or ticket severity |
| Pair programming causes higher bug-fix throughput | Software Engineering | Claimed from unadjusted 12-team table (Tier 3) | `[Preliminary]` | Refuted in this dataset by $\rho = -0.3612$ and clean $r = -0.7742$ |
| Reverse causality (bug difficulty) explains the `T01`–`T11` negative slope | Causal Inference | Structural audit of omitted covariates | `[Speculative]` | Controlled crossover pilot controlling for ticket complexity |

## 7. Limitations & Open Questions
- **Methodological & Data Limitations:** Small cross-sectional sample ($n=12$); missing team headcount, total developer hours, severity weights, reporting-period verification, and defect-reopen / regression metrics.
- **Actionable Next Steps / Experiments:**
  1. Audit `T12`'s reporting period, team size, and ticket-counting definition before presenting any figures to leadership.
  2. Normalize both metrics per developer-hour and weight bugs by severity/story points across multiple sprints.
  3. Run a controlled crossover pilot tracking both throughput and code quality (reopen rate, production regressions).
