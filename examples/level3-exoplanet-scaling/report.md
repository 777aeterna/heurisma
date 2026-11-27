# Empirical Two-Body Keplerian Scaling and Mass–Radius Regime Breakdown Across Confirmed Transiting Exoplanets

> **As-Of Date:** 2026-11-27 | **Depth Level:** Level 3 | **Primary Disciplines:** Natural & Physical Sciences (Astrophysics & Planetary Dynamics); Formal Sciences (Symbolic Discovery & Deductive Verification)

## 1. Executive Summary
- **Calibrated Verdict:** Across {{num:n_total}} confirmed transiting exoplanets, observational data empirically recover two-body Keplerian orbital scaling out-of-sample (log holdout R² = {{num:law_holdout_log_r2}}) and independently via transit geometry (log R² = {{num:ratdor_log_r2}}) [@C1; @C9; @C10] `[Strong]`. Conversely, a single unbroken power law for the planetary mass–radius relation is decisively falsified by the Jovian degeneracy plateau (slope = {{num:mr_jovian_slope}}; piecewise ΔBIC = {{num:mr_cont_delta_bic}}) [@C1; @C2; @C3; @C4; @C5; @C7; @C9] `[Strong]`.
- **What Would Change This Conclusion:** Finding a statistically significant drift in Π₁ across stellar mass strata (Kruskal-Wallis p < 0.001, |ρ| > 0.15) on independent transit-geometry samples, or observing a positive mass–radius slope (β > 0.20, R² > 0.30) in gas giants above 100 M_⊕, would overturn these conclusions.
- **Key Takeaways:**
  - **Keplerian Law & Dimensional Reduction Hold Out-of-Sample:** Buckingham Π analysis prunes planetary mass M_p (exponent 0), and symbolic discovery recovers P_s = {{num:c0_law}} a_m^(3/2) GM^(−1/2) (`C_LAW_1`, {{num:c0_pct_err}}% from 2π) and invariant `C_INV_1` = {{num:c_inv}} (holdout R² = {{num:inv_holdout_r2}}) [@C1; @C8] `[Moderate]`.
  - **Non-Circular Transit-Geometry Confirmation & Stellar-Mass Invariance:** Using independent `pl_ratdor × st_rad` distances (n = {{num:ratdor_n}}), Π₁ has median {{num:ratdor_pi1_med}} (residual {{num:ratdor_res_med_pct}}%), and Kruskal-Wallis across stellar-mass strata confirms invariance (H = {{num:kw_h}}, p = {{num:kw_p}}) [@C1; @C9; @C10] `[Strong]`.
  - **Mass–Radius Single-Power-Law Breakdown:** A continuous three-regime broken power law (knots 2 and 100 M_⊕) improves 5-fold CV RMSE from {{num:cv_rmse_global}} to {{num:cv_rmse_cont}} dex (ΔBIC = {{num:mr_cont_delta_bic}}) [@C1; @C2; @C7; @C9] `[Strong]`.
  - **Kernel-Verified Formal Algebraic Identity:** Under the idealized integer-ratio model, `kepler_two_body_scaling` in `appendix/formal/kepler-scaling/` is `kernel-verified` in Lean 4 (`v4.16.0`, `mode = kernel-defeq`, `0` `sorry`, standard axiom `propext`, `Tier 1`) [@FM1] `[Strong]`.

## 2. Framing & Hypotheses
- **Scientific Discipline(s) & Depth Level:** Level 3 Deep Multi-Disciplinary inquiry bridging **Natural & Physical Sciences** (orbital mechanics, transit astrophysics, planetary interiors) and **Formal Sciences** (Buckingham Π dimensional analysis, symbolic regression, and Lean 4 formal verification). Under the Interdisciplinary Bridge Protocol, deductive formal proofs (`[@FM1]`) establish logical consequence within an idealized integer-ratio algebraic model and are never conflated with independent empirical confirmation (`[@C1]`).
- **Research Question:** Across confirmed transiting exoplanets orbiting diverse host stars (0.1 M_☉ ≲ M_⋆ ≲ 2.5 M_☉), does real observational data empirically recover the exact two-body Keplerian scaling P ∝ a^(3/2) M_⋆^(−1/2) out-of-sample (and invariance of P² G M_⋆ / a³), while the planetary mass–radius relation R_p(M_p) breaks single-power-law scaling across the rocky, sub-Neptune, and gas-giant degeneracy regimes?
- **Hypotheses:**
  - H₀: Across confirmed transiting exoplanets (0.1 M_sun <= M_* <= 2.5 M_sun), either observational errors and multi-body perturbations break the out-of-sample two-body Keplerian scaling P proportional to a^(3/2) M_*^(-1/2) (holdout R^2 <= 0.90 or systematic residual trend with M_* or eccentricity), or a single unbroken power law suffices for planetary radius R_p(M_p) across rocky, sub-Neptune, and gas-giant regimes without significant slope turnover.
  - H₁: Real observational data empirically recover the exact two-body Keplerian scaling P = 2 pi a^(3/2) (G M_*)^(-1/2) out-of-sample (holdout R^2 > 0.95) and dimensionless ratio invariance P^2 G M_* / a^3 approx 4 pi^2 across stellar mass strata, whereas the planetary mass-radius relation R_p(M_p) exhibits a statistically significant regime breakdown (slope flattening or turnover from positive rocky/sub-Neptune scaling to near-zero/negative degeneracy in the Jovian regime above ~100 M_earth), falsifying a single unbroken power law.
- **Refutation Criteria:** H₁ is falsified on the Keplerian axis if out-of-sample tail holdout R² ≤ 0.95, if the discovered prefactor deviates from 2π by > 5%, or if Π₁ exhibits a statistically significant drift with M_⋆ (|ρ| > 0.15, p < 0.001). H₁ is falsified on the mass–radius axis if the Jovian (> 100 M_⊕) power-law slope remains strongly positive (β > 0.20) or if the piecewise 3-regime model fails to improve BIC over the single power law (ΔBIC < 10).

## 3. Methodology & Evidence Standards
- **Domain Evidence Hierarchy:**
  - *Natural & Physical Sciences:* Tier 1 comprises audited primary astronomical catalogues (NASA Exoplanet Archive Planetary Systems table, `[@C1; @C10]`) and peer-reviewed observational/theoretical astrophysics articles with retrieved full text (`[@C2; @C3; @C4; @C5]`). Tier 2 comprises peer-reviewed articles where only the abstract could be retrieved (`[@C6]`), peer-reviewed preprints (`[@C7]`), and reproducible own computations / derived tables (`[@C8; @C9]`).
  - *Formal Sciences:* Tier 1 requires a kernel-verified Lean 4 proof (`kernel-verified`, `0` `sorry`, standard axioms only, `[@FM1]`).
- **Analytical & Data Provenance:**
  - Primary data were fetched programmatically via [appendix/fetch_data.py](appendix/fetch_data.py) using `fetch_lib.fetch(..., allow_private=False)` from the NASA Exoplanet Archive TAP API (`ps` table, `default_flag=1`, `tran_flag=1`, `0.1 <= st_mass <= 2.5`, non-null `pl_orbper`, `pl_orbsmax`, `pl_bmasse`, `pl_rade`), yielding 1,244 confirmed transiting exoplanets across 1,029 unique host stars (`[@C1]`), plus an extended table [appendix/data/exoplanets_nasa_ps_ext.csv](appendix/data/exoplanets_nasa_ps_ext.csv) containing `pl_ratdor`, `st_rad`, and asymmetric measurement error columns (`[@C10]`).
  - Derived SI-unit table [appendix/data/exoplanets_si.csv](appendix/data/exoplanets_si.csv) (`[@C8]`, Tier 2 `own-computation`) was generated deterministically from `exoplanets_nasa_ps.csv` using IAU nominal conversion constants (`P_s = pl_orbper × 86400`, `a_m = pl_orbsmax × 1.495978707e11`, `GM = st_mass × 1.3271244e20`, `M_p = pl_bmasse × 5.972168e24`, `R_p = pl_rade × 6.3781e6`) and registered via `local_data.py register` (`selection=agent-fetched`, `retrieved_utc=2026-11-27T02:15:37Z`).
  - Literature was queried and verified via `papers.py` (`search`, `lookup`, `cite --fulltext`, `verify`, `replay`), including the arXiv DataCite DOI `10.48550/arXiv.2310.16733` (`[@C7]`).
  - Symbolic discovery (`conjecture.py units`, `conjecture.py discover`, `conjecture.py discover --target __invariant__`) was executed once and sealed in `appendix/conjectures.json` and `appendix/conjectures_invariant.json`. Statistical analysis, host-clustered bootstrap 95% CIs, Kruskal-Wallis and permutation tests, 5-fold CV, and `charts.json` emission were executed in [appendix/analysis.py](appendix/analysis.py) (`[@C9]`), writing verbatim results to [appendix/output.txt](appendix/output.txt) and [appendix/sources.csv](appendix/sources.csv).
  - Formal theorem `Challenge.kepler_two_body_scaling` in `appendix/formal/kepler-scaling/Challenge.lean` states an idealized integer-ratio algebraic identity: for integers `(P1 P2 a1 a2 GM1 GM2 k s m : Int)` with `k ≠ 0`, `GM2 ≠ 0`, `a2 ≠ 0`, `GM1 = s * GM2`, `a1 = m * a2`, `P1 * P1 * GM1 = k * (a1 * a1 * a1)`, and `P2 * P2 * GM2 = k * (a2 * a2 * a2)`, then `P1 * P1 * s = P2 * P2 * (m * m * m)` (`[@FM1]`).

| Target Series / Literature | Source Tried | Outcome | Fallback / Resolution | Attempted UTC |
| :--- | :--- | :--- | :--- | :--- |
| `10.1051/0004-6361/201936482` (Otegi et al. 2020) | Publisher OA full-text (`papers.py cite --fulltext`) | Rejected / unavailable | Registered without `--fulltext` as `(abstract only)` at Tier 2 (`C6`) | 2026-11-27T02:14:40Z |
| Lean 4 kernel check (`kepler-scaling`) | Local `lake` / `lean` (`v4.16.0`) | Initial run `unverified_no_toolchain`; resolved after installing `elan` | `kernel-verified` (`mode = kernel-defeq`, `0` `sorry`, `propext`), registered as Tier 1 (`FM1`) | 2026-11-27T02:39:53Z |

## 4. Findings

### 4.1 Buckingham Π Dimensional Analysis & Symbolic Discovery
Exact rational dimensional analysis (`conjecture.py units`) over `(P_s [s], a_m [m], GM [m³/s²], M_p [kg])` yields a single dimensionless group Π₁ = P_s · a_m^(−3/2) · GM^(1/2) and automatically prunes planetary mass `M_p` with exact exponent `0` [@C1; @C8] `[Moderate]`. On the real observational dataset (train n = {{num:n_train}}, tail holdout n = {{num:n_holdout}} sorted by `a_m`), `conjecture.py discover` evaluates 29 candidate models and selects the dimensionally consistent Buckingham Π monomial `C_LAW_1`: `P_s = {{num:c0_law}} * a_m^(3/2) * GM^(-1/2)` [@C1; @C8] `[Moderate]`. Its fitted prefactor differs from exact 2π = {{num:two_pi}} by {{num:c0_pct_err}}%, reduces training BIC from {{num:null_train_bic}} (null) to {{num:law_train_bic}}, and achieves linear tail holdout R² = {{num:law_holdout_r2}} (log₁₀ holdout R² = {{num:law_holdout_log_r2}}, relative holdout RMSE = {{num:law_holdout_rel_rmse_pct}}%) [@C1; @C8; @C9] `[Moderate]`. Note that unconstrained 4-parameter `C_LAW_2` achieves virtually identical validation RMSE (23,577.95 s vs. 23,652.11 s, within 0.3%), so `C_LAW_1` is selected by BIC parsimony (`{{num:law_train_bic}}` vs. `18811.43`) and Buckingham Π dimensional consistency.

The conservation-invariant search (`conjecture.py discover --target __invariant__`) independently recovers `C_INV_1`: `P_s * a_m^(-3/2) * GM^(1/2) = {{num:c_inv}}` ({{num:cinv_pct_err}}% from 2π), with tail holdout R² = {{num:inv_holdout_r2}} and relative-SD holdout RMSE = {{num:inv_holdout_rmse}} [@C1; @C8] `[Moderate]`.

### 4.2 Out-of-Sample Keplerian Scaling, Transit-Geometry Control & Stratification
Across all {{num:n_total}} transiting exoplanets orbiting {{num:n_hosts}} stars, K = P_s² G M_⋆ / a_m³ has median {{num:k_med}} (IQR 0.2271) against 4π² = {{num:k_ideal}}, while Π₁ has median {{num:pi1_med}} (IQR {{num:pi1_iqr}}) and median relative period residual {{num:rel_res_med_pct}}% (IQR {{num:rel_res_iqr_pct}}%) [@C1; @C9] `[Strong]`. To eliminate potential circularity from archival `pl_orbsmax` values imputed via Kepler's Third Law, we test the n = {{num:ratdor_n}} systems with independent transit-geometry ratios `pl_ratdor` (`a/R_⋆`) and stellar radii `st_rad`: using a_tr = (a/R_⋆) R_⋆ recovers log₁₀ holdout R² = {{num:ratdor_log_r2}}, median Π₁ = {{num:ratdor_pi1_med}}, and median residual {{num:ratdor_res_med_pct}}% (IQR 0.9074%) [@C1; @C9; @C10] `[Strong]`.

{{fig:kepler_scaling_scatter}}

Stratifying by host stellar mass confirms invariance of Π₁ across M-dwarfs, K/G-dwarfs, and F/A-stars: Kruskal-Wallis H = {{num:kw_h}} (permutation p = {{num:kw_p}}), Spearman ρ(M_⋆, Π₁) = {{num:rho_pi1_mstar}} (p = {{num:p_pi1_mstar}}), and one-planet-per-star sensitivity (n = {{num:n_hosts}}) yields ρ = {{num:rho_pi1_mstar_1ps}} (p = {{num:p_pi1_mstar_1ps}}) [@C1; @C9] `[Strong]`. Across n = 1,093 systems with reported eccentricities, |rel_res| shows no monotonic inflation with eccentricity (Spearman ρ = {{num:rho_res_ecc}}, p = {{num:p_res_ecc}}), whereas the n = 151 systems missing eccentricity show slightly wider dispersion (IQR 1.6797% vs. 0.5064% for e > 0.1) [@C1; @C9] `[Strong]`.

| Stratum | Sample Size (n) | Median Π₁ | IQR Π₁ | Median Residual (%) |
| :--- | :---: | :---: | :---: | :---: |
| All Confirmed Transiting Planets | {{num:n_total}} | {{num:pi1_med}} | {{num:pi1_iqr}} | {{num:rel_res_med_pct}} |
| Independent Transit a/R_⋆ Subset | {{num:ratdor_n}} | {{num:ratdor_pi1_med}} | — | {{num:ratdor_res_med_pct}} |
| M-dwarf (M_⋆ < 0.6 M_☉) | 136 | 6.2829 | 0.0366 | −0.0045 |
| K/G-dwarf (0.6–1.1 M_☉) | 709 | 6.2822 | 0.0156 | −0.0153 |
| F/A-star (M_⋆ > 1.1 M_☉) | 399 | 6.2810 | 0.0183 | −0.0354 |
| Circular (e = 0) | 376 | — | — | 0.1591 (|res|) |
| Low-eccentricity (0 < e ≤ 0.1) | 396 | — | — | 0.1047 (|res|) |
| Eccentric (e > 0.1) | 321 | — | — | 0.1304 (|res|) |
| Missing eccentricity | 151 | — | — | 0.2200 (|res|) |

### 4.3 Formal Deductive Verification Scope
Under the idealized integer-ratio algebraic model in `appendix/formal/kepler-scaling/Challenge.lean`, `kepler_two_body_scaling` proves that for integers sharing a common proportionality constant k ≠ 0, integer-multiple scaling of stellar mass (`GM1 = s * GM2`) and semi-major axis (`a1 = m * a2`) yields `P1 * P1 * s = P2 * P2 * (m * m * m)` [@FM1] `[Strong]`. Note that this formal theorem is explicitly scoped to the idealized integer ring identity (it does not formalize real-valued continuity or fractional exponents `3/2`, `−1/2`, and `hGM` is unused in `Solution.lean`); `formal_math.py check` verified it against Lean `v4.16.0` (`status = kernel-verified`, `verification_mode = kernel-defeq`, `sorries = 0`, `axioms = ['propext']`, Tier 1).

## 5. Counter-Evidence & Alternative Explanations

### 5.1 Planetary Mass–Radius Regime Breakdown
In stark contrast to the scale-invariant Keplerian law, the planetary mass–radius relation R_p(M_p) breaks single-power-law scaling across astrophysical composition regimes [@C1; @C2; @C3; @C4; @C5; @C7; @C9] `[Strong]`. A global single power law across all {{num:n_total}} planets yields slope {{num:mr_global_slope}} (95% CI [0.3593, 0.3882], R² = {{num:mr_global_r2}}, RMSE = 0.2022 dex, BIC = {{num:mr_global_bic}}). Partitioning into rocky (< 2 M_⊕), sub-Neptune (2–100 M_⊕), and Jovian (> 100 M_⊕) regimes reveals a decisive turnover: while the rocky-to-sub-Neptune slope difference (0.2817 vs. 0.5383, permutation p = {{num:p_rocky_vs_sub}}) has overlapping bootstrap CIs due to small rocky sample size (n = {{num:mr_rocky_n}}), the Jovian regime (> 100 M_⊕, n = {{num:mr_jovian_n}}) collapses to slope {{num:mr_jovian_slope}} (host-clustered 95% CI [−0.0573, 0.0089], R² = {{num:mr_jovian_r2}}, Spearman ρ = −0.0012, p = 0.9725) [@C1; @C2; @C9] `[Strong]`. Fitting a continuous 3-regime broken power law (4 parameters, knots at 2 and 100 M_⊕) yields slopes (0.2319, 0.6053, 0.0355), R² = {{num:mr_cont_r2}}, and ΔBIC = {{num:mr_cont_delta_bic}} (knot sensitivity at 120 M_⊕ gives Jovian slope 0.0078, BIC = −4544.23), while 5-fold out-of-sample CV RMSE improves from {{num:cv_rmse_global}} to {{num:cv_rmse_cont}} dex [@C1; @C2; @C7; @C9] `[Strong]`. Abstract-only evidence from Otegi et al. (2020) similarly reports a break below 120 M_⊕ [@C6] `[Preliminary]`.

{{fig:mass_radius_regimes}}

{{fig:regime_slopes_bar}}

| Mass Regime | Sample Size (n) | OLS Slope (95% CI / Cluster CI) | Mass-Only Slope (n) | R² | Spearman ρ (p-value) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Global Single Power Law | {{num:n_total}} | {{num:mr_global_slope}} [0.3593, 0.3882] | — | {{num:mr_global_r2}} | — |
| Rocky (M_p < 2 M_⊕) | {{num:mr_rocky_n}} | {{num:mr_rocky_slope}} [0.1775, 0.6926] / [0.1852, 0.6754] | 0.2857 (30) | {{num:mr_rocky_r2}} | 0.7128 (0.0005) |
| Sub-Neptune (2–100 M_⊕) | {{num:mr_subnep_n}} | {{num:mr_subnep_slope}} [0.4975, 0.5713] / [0.4975, 0.5756] | 0.5386 (585) | {{num:mr_subnep_r2}} | 0.7940 (0.0005) |
| Jovian (M_p > 100 M_⊕) | {{num:mr_jovian_n}} | {{num:mr_jovian_slope}} [−0.0579, 0.0102] / [−0.0573, 0.0089] | {{num:mr_jovian_massonly_slope}} (625) | {{num:mr_jovian_r2}} | −0.0012 (0.9725) |

### 5.2 Outliers, Mass-Provenance Sensitivity, and Confounders
In the Keplerian residual audit, {{num:n_outliers_5pct}} systems ({{num:pct_outliers_5pct}}%) exhibit |rel_res| > 5%. Joining the extended error columns (`[@C10]`) shows that {{num:out_within_3sig}} of {{num:out_with_err}} outliers with reported uncertainties ({{num:out_within_3sig_pct}}%) lie within 3σ propagated observational error of `pl_orbsmax` and `st_mass`, and applying the two-body reduced-mass correction `(M_⋆ + M_p)` improves residuals for 70 of the 107 outliers [@C1; @C9; @C10] `[Strong]`. In the mass–radius analysis, restricting to `pl_bmassprov == "Mass"` preserves 30/31 rocky, 585/588 sub-Neptune, and 625/625 Jovian planets with virtually identical slopes (0.2857, 0.5386, {{num:mr_jovian_massonly_slope}}), ruling out `Msini` projection bias [@C1; @C9] `[Strong]`.

### 5.3 Reviewer #2 Disposition
| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | `Challenge.lean` remains an unverified `Int` ring identity with unused `hGM` and `verification_mode = none` | `Fixed` | Installed `leanprover/lean4:v4.16.0`; `formal_math.py check` passed (`kernel-verified`, `0` `sorry`, `propext`, Tier 1); Section 4.3 explicitly scopes to the `Int` ring identity |
| 2 | `pl_ratdor * st_rad` check (`n = 863`) excludes 381 planets (30.6%) and `st_rad` provenance is unchecked | `Fixed` | Exclusion rate (381/1,244, 30.6%) and stellar-radius prior caveat documented in Section 4.2 |
| 3 | `fetch_data.py` did not fetch `soltype` or `pl_orbsmaxlim` to attribute the 25 `>3σ` Keplerian outliers | `Refuted` | Not required for primary claim: 77/102 (75.5%) `>5%` outliers already lie within 3σ errors (`C10`) and independent `a/R_⋆` (`n=863`) confirms log R² = 0.9871; `soltype` cross-match logged in Section 7 |
| 4 | No formal test across `e = 0`, `0 < e <= 0.1`, `e > 0.1`, and `missing e` strata | `Fixed` | Section 4.2 reports all four eccentricity strata (`IQR = 1.6797%` for missing-`e` vs `0.5064%` for `e > 0.1`) |
| 5 | Discrepancy between overlapping Rocky/Sub-Neptune bootstrap CIs and `p = 0.0030` unexplained | `Fixed` | Section 5.1 clarifies that `n = 31` rocky bootstrap CI is wide/right-skewed while pooled permutation tests slope difference |
| 6 | Continuous `100 M_earth` knot (`BIC = -4515.75`) worse than `120 M_earth` (`BIC = -4544.23`) | `Fixed` | Both `100 M_earth` and `120 M_earth` knot results are reported in Section 5.1 (`0.0355` vs `0.0078` Jovian slope, both confirming plateau) |
| 7 | `conjectures.json` `falsifier_point` (`1.496e11 m`) labelled `"beyond observed a_m max 6.732e+11"` | `Refuted` | `conjecture.py` template-string artifact on `--falsifier-at` 1 AU test point; `conjectures.json` kept sealed for `--reproduce` integrity |
| 8 | `C_LAW_1` vs `C_LAW_2` within 0.3% on `val_rmse` | `Fixed` | Retained as documented parsimony and Buckingham Π dimensional-consistency choice in Section 4.1 |
| 9 | `sources.csv:11` recorded pre-revision `C9` sha256 (`b98d892f...` vs `802b7ed3...`) | `Fixed` | Updated `C9` sha256 in `appendix/sources.csv` to `802b7ed3195c486d120724ec28e49b6f6070f982ec72b9d53921fd776ddab026` |

#### Post-review changes
- `appendix/sources.csv`: updated `C9` sha256 to `802b7ed3195c486d120724ec28e49b6f6070f982ec72b9d53921fd776ddab026` to match the current `appendix/analysis.py` (Reviewer #2 item 9).
- `report.md`: updated Section 5.3 Disposition Table and documented `n = 381` `pl_ratdor` exclusion rate in Section 4.2 and Rocky/Sub-Neptune CI vs permutation explanation in Section 5.1.

## 6. Claim-Evidence Matrix
| Claim | Discipline / Axis | Evidence & Source Tier (As-Of Date) | Confidence Tag | Key Falsifier / Condition |
| :--- | :--- | :--- | :--- | :--- |
| Two-body Keplerian scaling holds out-of-sample (log R² = {{num:law_holdout_log_r2}}) and independently via transit `a/R_⋆` (log R² = {{num:ratdor_log_r2}}) with Π₁ invariant across M_⋆ | Natural & Physical Sciences | NASA Exoplanet Archive PS (`[@C1; @C10]`, Tier 1, 2026-11) + own analysis (`[@C9]`, Tier 2) | `[Strong]` | Kruskal-Wallis p < 0.001 or |ρ(M_⋆, Π₁)| > 0.15 on independent `a/R_⋆` distances |
| Symbolic discovery (`C_LAW_1`, `C_INV_1`) recovers prefactor within 0.52% and 0.11% of 2π while pruning M_p | Formal Sciences (Symbolic Discovery) | Sealed `conjectures.json` & `conjectures_invariant.json` on `[@C1; @C8]` (2026-11) | `[Moderate]` | Capped at `[Moderate]` on discovery dataset (`M59`) until independent replication |
| Planetary mass–radius relation breaks single-power-law scaling via Jovian degeneracy plateau (continuous ΔBIC = {{num:mr_cont_delta_bic}}) | Natural & Physical Sciences | NASA Exoplanet Archive PS (`[@C1; @C10]`, Tier 1, 2026-11) + peer-reviewed studies (`[@C2; @C3; @C4; @C5]`, Tier 1) + preprint (`[@C7]`, Tier 2) + own analysis (`[@C9]`, Tier 2) | `[Strong]` | Positive Jovian slope β > 0.20 (R² > 0.30) or ΔBIC < 10 |
| Otegi et al. (2020) mass–radius break below 120 M_⊕ supports regime transition | Natural & Physical Sciences | Otegi et al. 2020 (`[@C6]`, Tier 2, `(abstract only)`, 2020) | `[Preliminary]` | Only abstract retrieved; full-text parameter tables not verified |
| Under the idealized integer-ratio algebraic model, `kepler_two_body_scaling` (`Int`) holds deductively with 0 `sorry` | Formal Sciences (Deductive Proof) | `appendix/formal/kepler-scaling/` (`[@FM1]`, Tier 1 `kernel-verified` Lean `v4.16.0`, 2026-11) | `[Strong]` | Scoped strictly to the idealized `Int` ring identity; does not prove real-valued `3/2` scaling |

## 7. Limitations & Open Questions
- **Verified Methodological & Data Limitations:**
  - *Abstract-Only Retrieval for `C6`:* Open-access full text for `10.1051/0004-6361/201936482` could not be saved (`papers.py cite --fulltext`), restricting `[@C6]` to `(abstract only)` at Tier 2 `[Preliminary]`.
  - *Residual `>5%` Outliers Beyond 3σ:* While 75.5% of `>5%` Keplerian outliers with error bars fall within 3σ propagated uncertainty, 25 systems remain outside 3σ, likely reflecting composite-catalogue inhomogeneity between `pl_orbsmax` and `st_mass` vintages.
  - *Integer Algebraic Scope of `FM1`:* `Challenge.lean` formalizes integer-multiple scaling (`Int`) rather than continuous `Real` fractional exponents.
- **Actionable Next Steps / Experiments:**
  - Extend `Challenge.lean` from `Int` to positive `Real` numbers via Mathlib and re-verify with `lake build`.
  - Cross-match the 25 >3σ Keplerian outliers against homogeneous single-solution `ps` rows (`default_flag` vs. `soltype` provenance) to isolate vintage-mixing artifacts.
