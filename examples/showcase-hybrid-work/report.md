# Hybrid Work (2 Days Remote) vs. Full-Time Office in Software Engineering: Retention, Output, and Seniority Heterogeneity

> **As-Of Date:** 2026-11-20 | **Depth Level:** Level 2 (Empirical / Data Study) | **Primary Disciplines:** Social Sciences & Economics (Labor Economics) + Engineering & Applied Sciences (Empirical Software Engineering)

## 1. Executive Summary
- **Calibrated Verdict:** A six-month randomized trial reports a one-third lower quit rate under 2-day hybrid work (7.20% to 4.80%) [@C2] `[Moderate]`, and the supplied site file points the same way (12-month attrition `{{num:attr_hyb_w}}` vs. `{{num:attr_off_w}}`), but its allocation is undocumented, so it supports only `[Preliminary]` claims [@C1; @C4]. On output, the supplied sites show opposite-signed effects for senior and junior sites that an exact test separates from uniform effects (interaction p = `{{num:pr_did_p}}`) `[Preliminary]`, and neither external study reports output by seniority.
- **What Would Change This Conclusion:** A documented allocation protocol with pre-period baselines for the 16 sites, or engineer-level data controlling for defect severity, that removes the seniority interaction or reverses the attrition difference.
- **Key Takeaways:**
  - **Retention:** the external evidence is a single randomized trial with no seniority split [@C2] `[Moderate]`; the supplied sites agree in direction for both seniority groups, and the data cannot distinguish a smaller junior reduction from none (interaction p = `{{num:attr_did_p}}`) [@C1; @C4] `[Preliminary]`.
  - **Output:** pooling hides the divergence (pooled difference `{{num:pr_pool_diff}}`, stratified exact p = `{{num:pr_pool_p}}`), while the seniority interaction is `{{num:pr_did}}` [@C4] `[Preliminary]`.
  - **Mechanism:** reduced mentoring hours at junior hybrid sites are consistent with, but cannot test, a proximity mechanism supported elsewhere in a different setting [@C3] `[Preliminary]`.

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** Social Sciences & Economics (Labor Economics — field experiments, retention) + Engineering & Applied Sciences (Empirical Software Engineering — pull-request throughput, mentoring) | **Level 2**. Labor Economics governs attrition identification and subgroup heterogeneity; Software Engineering governs the validity of the output metric and the mentoring bottleneck.
- **Research Question:** Compared to a 5-day office schedule, does a 2-day/week hybrid policy change software-engineering PR output and 12-month retention, and is the effect the same for senior and junior engineers?
- **Hypotheses:**
  - H₀: A 2-day hybrid schedule produces no change in PR output or 12-month attrition in any seniority group.
  - H₁: A 2-day hybrid schedule lowers attrition without changing output, and the output effect is the same across seniority groups.
  - H₂: A 2-day hybrid schedule lowers attrition overall, but its output effect differs by seniority.
- **Refutation Criteria:** Because each seniority group has only four sites per policy, all tests are exact permutation tests (not bootstrap), with the threshold p < 0.05 fixed in advance. H₀ is falsified for retention if the stratified exact test of the attrition difference has p < 0.05. H₁ is falsified if the exact test of the seniority × policy interaction on PR output has p < 0.05. Rejecting H₁ does not by itself confirm any mechanism behind H₂.

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:** Tier 1 = peer-reviewed randomized trials and quasi-experiments with causal identification; Tier 2 = administrative or organizational data with documented allocation and covariates; Tier 3 = data of undocumented origin or allocation, press, and vendor material. Single studies and samples under 30 units cap a claim below `[Strong]`.
- **Analytical & Data Provenance:** The semicolon-delimited, decimal-comma file `data/hybrid_rct_sites.csv` (`sha256: 9a7419cd6056`) is an illustrative file shipped with this repository. Its origin, the allocation of sites to policies, the baseline window of the PR delta, and the meaning of `mentoring_hrs_wk` are all undocumented, so it is registered as Tier 3 [@C1] and never as a randomized dataset. All statistics, `charts.json` and `appendix/numbers.json` come from [`appendix/analysis.py`](appendix/analysis.py), an own computation that adds no evidence beyond the file itself [@C4] (steps in [`appendix/README.md`](appendix/README.md); console log in [`appendix/output.txt`](appendix/output.txt)). The trial [@C2] was read in full through its open-access copy after the publisher page required a sign-in; the proximity study [@C3] was read at the abstract level only.
- **Review Gates:** The source-verification and QA gates of this example are manual maintainer records written without a subagent, so they are self-review (`MODE: self-review` in `appendix/gates/`), not independent review.

| Target Series | Source Tried | Query / Endpoint | Outcome | Failure Reason | Fallback Used |
| :- | :- | :- | :- | :- | :- |
| Site allocation protocol, baseline window, `mentoring_hrs_wk` definition | Local data inventory | `local_data.py inventory data/` | not found | Only the CSV is supplied; no data dictionary or protocol | Local file kept at Tier 3; all claims from it capped at `[Preliminary]` |
| Individual-level engineer microdata | Online and local | Private organizational data; local inventory | not available | Only the data owner can supply it | Site-level exact tests only; request listed in Section 7 |
| Bloom, Han & Liang (2024) full text | Publisher page | `GET nature.com/articles/s41586-024-07500-2` | HTTP 303 | Redirects to a sign-in page | Open-access copy in Europe PMC (PMC11208135) |
| Bloom, Han & Liang (2024) full text | Europe PMC | `GET europepmc.org/…/PMC11208135/fullTextXML` | used | | Full text read (Data availability statement not verified) |
| Emanuel, Harrington & Pallais (2023) | NBER page | `GET nber.org/papers/w31880` | used | | Abstract read; full text not read |

## 4. Findings

### 4.1 Retention: External Trial Evidence and the Supplied Sites
The only randomized evidence is a six-month trial of 2-day hybrid work with 1,612 employees at Trip.com, assigned by birthday parity: the quit rate was 7.20% in the office group and 4.80% in the hybrid group (P = 0.043), a one-third reduction concentrated among non-managers, women, and long commuters, with no difference for managers [@C2] `[Moderate]`. The trial reports no seniority split, and one company in one labor market over six months limits generalization [@C2].

In the supplied file, 12-month attrition averages `{{num:attr_hyb_w}}` under hybrid and `{{num:attr_off_w}}` under office when weighted by engineers (`{{num:attr_hyb_u}}` vs. `{{num:attr_off_u}}` unweighted), a `{{num:attr_rel_drop_w}}` relative reduction; the stratified exact test gives p = `{{num:attr_pool_p}}` [@C1; @C4] `[Preliminary]`. The reduction appears in both groups, `{{num:attr_sen_diff}}` for senior sites (p = `{{num:attr_sen_p}}`, relative `{{num:attr_rel_sen}}`) and `{{num:attr_jun_diff}}` for junior sites (p = `{{num:attr_jun_p}}`, relative `{{num:attr_rel_jun}}`), where `{{num:p_floor_sub}}` is the smallest p a 4-vs-4 comparison can reach. The junior reduction is smaller, but the exact interaction test cannot tell it from no difference (`{{num:attr_did}}`, p = `{{num:attr_did_p}}`) [@C4] `[Preliminary]`.

{{fig:attrition_by_seniority}}

The two estimates are not combined into one range: the trial measures quits over six months in a travel-technology company, and the file reports 12-month attrition at engineering sites with undocumented allocation [@C1; @C2].

### 4.2 Seniority Heterogeneity in Output Rejects Uniform Effects (H₁)
Pooling all sites gives a small difference (`{{num:pr_pool_hyb}}` hybrid vs. `{{num:pr_pool_off}}` office; `{{num:pr_pool_diff}}`, stratified exact p = `{{num:pr_pool_p}}`), which conceals opposite-signed subgroup differences [@C4] `[Preliminary]`:

| Subgroup | Sites | Hybrid (2d) PR Delta | Office (5d) PR Delta | Difference | Exact p |
| :- | -: | -: | -: | -: | -: |
| Pooled | 16 | {{num:pr_pool_hyb}} | {{num:pr_pool_off}} | {{num:pr_pool_diff}} | {{num:pr_pool_p}} |
| Senior | 8 | {{num:pr_sen_hyb}} | {{num:pr_sen_off}} | {{num:pr_sen_diff}} | {{num:pr_sen_p}} |
| Junior | 8 | {{num:pr_jun_hyb}} | {{num:pr_jun_off}} | {{num:pr_jun_diff}} | {{num:pr_jun_p}} |

{{fig:subgroup_output}}

Within each seniority group, every hybrid site lies on one side of every office site, so each subgroup test sits at its floor (`{{num:p_floor_sub}}`). The interaction test over all `{{num:n_perm_strat}}` stratified relabelings gives `{{num:pr_did}}` (p = `{{num:pr_did_p}}`), which rejects the uniform-effect hypothesis H₁ under the pre-specified threshold [@C4] `[Preliminary]`. The output pattern is consistent with H₂, but this does not identify why it arises. The trial reports no evidence of an effect on performance grades or promotions overall [@C2] `[Moderate]`; it does not report results by seniority.

### 4.3 Mentoring Hours: Consistent Pattern, Mechanism Untested
Mentoring hours per week fall from `{{num:ment_jun_off}}` at junior office sites to `{{num:ment_jun_hyb}}` at junior hybrid sites, and from `{{num:ment_sen_off}}` to `{{num:ment_sen_hyb}}` at senior sites [@C1; @C4] `[Preliminary]`. The pooled junior correlation with PR delta (r = `{{num:r_jun_pooled}}`) is not a mechanism test: it is driven by the policy arm, which determines both variables. Within each arm (four sites each) the correlation is positive in all four cells (junior hybrid `{{num:r_jun_hyb}}`, junior office `{{num:r_jun_off}}`, senior hybrid `{{num:r_sen_hyb}}`, senior office `{{num:r_sen_off}}`), which four points cannot support as evidence [@C4] `[Preliminary]`. At senior sites, mentoring hours are slightly lower under hybrid while output is higher, so a single "mentoring drives output" mechanism does not fit both groups.

{{fig:mentoring_scatter}}

A quasi-experimental study of software engineers finds that sitting near teammates raises coding feedback by 18.3% and improves code quality, with gains concentrated among less-tenured and younger employees and experienced engineers writing less code nearby [@C3] `[Moderate]`. That evidence concerns proximity within teams; the supplied file cannot test it, because each site is wholly senior or wholly junior and the direction of `mentoring_hrs_wk` (hours given or received) is undocumented [@C1].

## 5. Counter-Evidence & Alternative Explanations
- **Undocumented Allocation:** Without a documented assignment of sites to policies and a pre-period baseline, differences between hybrid and office sites may reflect site selection, project complexity, or manager quality [@C1] `[Preliminary]`.
- **Survivorship and Composition:** Output is measured on engineers who remain; office sites lose about four percentage points more engineers, so who is observed differs by arm, and the baseline window of the PR delta is undefined [@C1; @C4] `[Preliminary]`.
- **PR Count Is an Incomplete Proxy:** Merged pull requests do not capture quality, incident rates, or review load, and senior engineers may merge more partly because they review less junior code [@C3] `[Moderate]`.
- **External Validity of the Trial:** One company, one country, hybrid-versus-office only, with the effect concentrated in specific subgroups and no seniority breakdown [@C2] `[Moderate]`.
- **Tiny Cells:** Four sites per cell make the exact tests coarse and confidence intervals uninformative, so no interval is reported [@C4] `[Preliminary]`.

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier (As-Of Date) | Confidence Tag | Key Falsifier / Condition |
| :- | :- | :- | :- | :- |
| 2-day hybrid work lowers quit rates by about one-third | Labor Economics | Trip.com randomized trial [@C2], Tier 1, 2024-06 | `[Moderate]` | A replicated multi-year trial in which the effect fades or is absent outside the reported subgroups |
| In the supplied sites, hybrid has lower 12-month attrition in both seniority groups | Labor Economics | Supplied CSV [@C1] (Tier 3 origin), exact tests in own computation [@C4], 2026-10 | `[Preliminary]` | A documented non-random assignment, or engineer-level data reversing the sign |
| In the supplied sites, the output effect differs by seniority (interaction p = `{{num:pr_did_p}}`) | Empirical Software Engineering | Supplied CSV [@C1] (Tier 3 origin), exact interaction test in own computation [@C4], 2026-10 | `[Preliminary]` | Pre-period baselines and engineer-level controls that remove the interaction |
| Proximity to teammates raises coding feedback, mostly for less-tenured engineers, and lowers experienced engineers' own code output | Labor Economics / Software Engineering | Difference-in-differences study [@C3], Tier 1 (published 2026), abstract read | `[Moderate]` | Re-estimation with other firms or specifications showing no feedback gain |
| Lower mentoring hours explain the junior output gap in the supplied sites | Software Engineering | Supplied CSV [@C1] and own computation [@C4]; proximity study [@C3] is analogy only | `[Preliminary]` | Data defining `mentoring_hrs_wk` and mixed-seniority sites showing the gap persists at equal mentoring hours |

## 7. Limitations & Open Questions
- **Verified Methodological & Data Limitations:** Site-level aggregates (`n = {{num:total_sites}}` sites, `{{num:total_engineers}}` engineers, four per cell) with no documented allocation, baseline window, or data dictionary, and no engineer-level records (searches logged in `appendix/data_attempts.csv`); the trial's data availability statement and the proximity study's full text were not read. The QA gate records one accepted FAIL (`appendix/gates/qa.md`, check 3): the verdict's 7.20% and 4.80% are the external trial's published quit rates [@C2], not outputs of `appendix/analysis.py`.
- **Actionable Next Steps / Experiments:** Request from the data owner the allocation protocol, pre-period attrition and output by site, the definition of `mentoring_hrs_wk`, and engineer-level records; re-estimate with pre-period baselines and attrition-adjusted bounds; and read the full text of the proximity study before relying on its subgroup magnitudes.
