# Hybrid Work (2 Days Remote) vs. Full-Time Office in Software Engineering: Output, Retention, and Seniority Heterogeneity

> **As-Of Date:** 2026-11-20 | **Depth Level:** Level 2 (Empirical / Data Study) | **Primary Disciplines:** Social Sciences & Economics (Labor Economics) + Engineering & Applied Sciences (Empirical Software Engineering)

## 1. Executive Summary
- **Calibrated Verdict:** A 2-day/week hybrid schedule sharply reduces 12-month engineering attrition by {{num:attr_rel_drop}} (`{{num:attr_hyb}}` vs. `{{num:attr_off}}`), consistent with peer-reviewed RCT evidence `[Strong]`, but pooled output averages mask opposite seniority effects `[Moderate]`. In the local 16-site dataset (`n = {{num:total_engineers}}` engineers), hybrid work raises senior PR output by `{{num:senior_pr_diff}}` while lowering junior PR output by `{{num:junior_pr_diff}}` alongside a two-thirds drop in weekly mentoring hours `[Moderate]`.
- **What Would Change This Conclusion:** Individual-level longitudinal telemetry controlling for defect severity and structured virtual-onboarding interventions showing junior engineers match office-based output and skill growth under hybrid schedules.
- **Key Takeaways:**
  - **Retention gain is robust:** Local 12-month attrition drops by `{{num:attr_rel_drop}}` [@C1; @C4], closely matching the 33% quit-rate reduction in the 1,612-employee Trip.com *Nature* RCT [@C2] `[Strong]`.
  - **Pooling bias hides seniority divergence:** The pooled output difference (`{{num:pooled_pr_diff}}`) averages a positive senior gain (`{{num:senior_pr_diff}}`) with a steep junior decline (`{{num:junior_pr_diff}}`) [@C4] `[Moderate]`.
  - **Mentoring proximity mechanism:** Junior hybrid sites drop from `{{num:jun_ment_off}}` to `{{num:jun_ment_hyb}}` mentoring hours/week (`r = {{num:r_ment_jun}}` with output delta), aligning with co-location feedback findings in software engineering [@C3] `[Moderate]`.

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** Social Sciences & Economics (Labor Economics — causal field experiments, retention dynamics) + Engineering & Applied Sciences (Empirical Software Engineering — PR throughput, code review mentoring) | **Level 2**. Labor Economics governs attrition identification and subgroup heterogeneity; Software Engineering governs output metric validity and mentoring bottlenecks.
- **Research Question:** Compared to a 5-day office schedule, does a 2-day/week hybrid policy improve software-engineering PR output and 12-month retention, and is the effect homogeneous across senior and junior engineers?
- **Hypotheses:**
  - H₀: A 2-day hybrid schedule produces no statistically distinguishable change in PR output or 12-month retention across seniority groups.
  - H₁: A 2-day hybrid schedule lowers 12-month attrition without reducing aggregate output, with uniform gains across seniority levels.
  - H₂: A 2-day hybrid schedule lowers attrition overall, but produces heterogeneous output effects—raising senior output while reducing junior output due to lower in-person mentoring proximity.
- **Refutation Criteria:** H₁ is falsified if junior and senior output effects have opposite signs with non-overlapping 95% bootstrap confidence intervals. H₀ is falsified if 12-month attrition falls by ≥15% relative to office sites with a 95% CI excluding zero.

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:** Tier 1 = peer-reviewed randomized controlled trials (RCTs) and natural experiments with causal identification; Tier 2 = multi-site administrative/organizational RCT extracts with subgroup covariates; Tier 3 = uncontrolled surveys, press articles, or vendor whitepapers.
- **Analytical & Data Provenance:** Stage 0 local inventory (`local_data.py inventory data/`) discovered the semicolon-delimited European-format CSV `data/hybrid_rct_sites.csv` (`sha256: 9a7419cd6056`), which was copied into `appendix/data/` and registered in [`appendix/sources.csv`](appendix/sources.csv) [@C1]. All statistics, bootstrap 95% CIs (`2,000` draws, fixed seed `42`), `charts.json`, and `appendix/numbers.json` were emitted directly by [`appendix/analysis.py`](appendix/analysis.py) [@C4] (reproduction steps in [`appendix/README.md`](appendix/README.md); console log in [`appendix/output.txt`](appendix/output.txt)).

| Target Series | Source Tried | Query / Endpoint | Outcome | Failure Reason | Fallback Used |
| :- | :- | :- | :- | :- | :- |
| Individual-level microdata & defect severity | Local data inventory | `local_data.py inventory data/` | not found | Only site-level aggregates present in `hybrid_rct_sites.csv` | Site-level subgroup analysis; causal claims capped at `[Moderate]` |
| Full-remote (5d WFH) arm | Local inventory + RCT registry | `local_data.py preview` + Bloom et al. 2024 | not found | Local dataset covers only `Hybrid_2d` vs. `Office_5d` | Full-remote extrapolation capped at `[Preliminary]` |

## 4. Findings

### 4.1 Retention Gains Replicate Tier 1 Field-Experiment Evidence
Across all `{{num:total_sites}}` engineering sites (`{{num:total_engineers}}` engineers), 12-month attrition averages `{{num:attr_hyb}}` under 2-day hybrid versus `{{num:attr_off}}` under 5-day office—a `{{num:attr_rel_drop}}` relative reduction (95% bootstrap CI `[-5.4 pp, -2.6 pp]`) [@C1; @C4] `[Strong]`. Both senior (`8.1%` vs. `13.4%`) and junior (`11.6%` vs. `14.3%`) sites exhibit lower turnover [@C4]. This closely aligns with Bloom, Han & Liang's *Nature* RCT of `1,612` employees at Trip.com, which documented a `33%` reduction in quit rates with zero penalty to performance grades or promotions [@C2] `[Strong]`.

### 4.2 Seniority Heterogeneity Falsifies Uniform Output Hypothesis (H₁)
Pooling all sites yields a modest `-1.78 pp` PR delta (`-0.74%` hybrid vs. `+1.04%` office, MAD `3.65 pp`), which conceals opposite-signed subgroup effects [@C4] `[Moderate]`:

| Subgroup | Sites | Hybrid (2d) PR Delta | Office (5d) PR Delta | Difference (95% Bootstrap CI) | Hybrid Attrition | Office Attrition |
| :- | -: | -: | -: | :- | -: | -: |
| Pooled | 16 | -0.74% | +1.04% | {{num:pooled_pr_diff}} | {{num:attr_hyb}} | {{num:attr_off}} |
| Senior | 8 | +2.97% | +0.25% | {{num:senior_pr_diff}} (`[+2.25 pp, +3.20 pp]`) | 8.1% | 13.4% |
| Junior | 8 | -4.45% | +1.82% | {{num:junior_pr_diff}} (`[-6.78 pp, -5.75 pp]`) | 11.6% | 14.3% |

{{fig:subgroup_output}}

Because senior and junior bootstrap 95% CIs are strictly opposite in sign and non-overlapping, H₁ (uniform output effect) is falsified in favor of H₂ [@C4] `[Strong]`.

### 4.3 Mentoring Proximity as the Primary Mechanism
Junior hybrid sites receive `{{num:jun_ment_hyb}}` mentoring hours/week versus `{{num:jun_ment_off}}` hours/week in 5-day office sites (`r = {{num:r_ment_jun}}` between mentoring hours and junior PR delta) [@C1; @C4] `[Moderate]`. This directly mirrors Emanuel, Harrington & Pallais's software-engineering proximity study, which found that co-location increases online code-review feedback to junior engineers by `18.3%` while taxing senior engineers' immediate coding output [@C3] `[Strong]`.

{{fig:mentoring_scatter}}

## 5. Counter-Evidence & Alternative Explanations
- **PR Count Is an Incomplete Output Proxy:** Merging more pull requests does not capture architectural quality, incident rates, or code-review load; senior engineers in hybrid sites may merge more PRs partly because they spend fewer hours reviewing junior code [@C3] `[Moderate]`.
- **Site-Level Aggregation & Small Site Count (`n = 16`):** Without engineer-level microdata, site-level differences could reflect unobserved project complexity or manager quality across sites [@C1] `[Moderate]`.
- **Full-Remote Extrapolation Risk:** Neither the local dataset nor the Trip.com *Nature* RCT directly evaluates a mandatory 5-day full-remote policy; extrapolating hybrid retention gains to full-remote without structured onboarding risks steeper junior skill-acquisition penalties [@C2; @C3] `[Preliminary]`.

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier (As-Of Date) | Confidence Tag | Key Falsifier / Condition |
| :- | :- | :- | :- | :- |
| 2-day hybrid work lowers 12-month attrition by ~29–33% | Labor Economics | Trip.com *Nature* RCT [@C2] (Tier 1, 2024-06) + local 16-site dataset [@C1; @C4] (Tier 2, 2026-10) | `[Strong]` | Replicated multi-year RCT showing turnover rebound once external labor markets tighten |
| Hybrid raises senior PR output (`+2.73 pp`) while lowering junior PR output (`-6.28 pp`) | Empirical Software Engineering | Local 16-site bootstrap audit [@C1; @C4] (Tier 2, 2026-10) | `[Moderate]` | Individual-level panel controlling for ticket complexity and defect reopen rates |
| Reduced physical mentoring proximity drives the junior output penalty | Labor Economics / Software Engineering | Co-location feedback study [@C3] (Tier 1, 2023-11) + local mentoring correlation [@C4] (Tier 2, 2026-10) | `[Moderate]` | Structured virtual pair-programming trial closing the junior output gap |
| Mandatory 5-day full-remote would deepen junior onboarding loss | Labor Economics | Extrapolation from proximity trade-off [@C3] without a 5d remote arm (Tier 2/3, 2026-11) | `[Preliminary]` | Direct 3-arm RCT (Office 5d vs. Hybrid 2d vs. Full Remote) |

## 7. Limitations & Open Questions
- **Verified Methodological & Data Limitations:** Site-level aggregates (`n = 16` sites, `{{num:total_engineers}}` engineers) lack individual tenure, defect-severity weights, and a 5-day full-remote arm (both gaps logged in `appendix/data_attempts.csv`).
- **Actionable Next Steps / Experiments:** Adopt 2-day hybrid with synchronized in-office "anchor days" (e.g., Tuesday–Thursday) pairing junior and senior engineers, track defect-weighted PR quality and code-review turnaround at the engineer level, and test whether scheduled virtual office hours recover junior mentoring hours.
