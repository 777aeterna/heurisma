MODE: subagent
REVIEWED-SHA256: fd8a633ab2dce604d6dd535586bbac5d482b474f666731ad1541d2fa7cedb8d2
REVIEWED-UTC: 2026-11-27T02:27:03Z
ANALYSIS-SHA256: 802b7ed3195c486d120724ec28e49b6f6070f982ec72b9d53921fd776ddab026
FORMAL-SHA256: d8b723d7cbdfcd961caa90f223e4dead9ce8ec9359312e41b4c89430c12221df

QUOTE: appendix/formal/kepler-scaling/Challenge.lean:11: "theorem kepler_two_body_scaling (P1 P2 a1 a2 GM1 GM2 k s m : Int) (hk : k ≠ 0) (hGM : GM2 ≠ 0) (ha : a2 ≠ 0) (hs : GM1 = s * GM2) (hm : a1 = m * a2) (h1 : P1 * P1 * GM1 = k * (a1 * a1 * a1)) (h2 : P2 * P2 * GM2 = k * (a2 * a2 * a2)) : P1 * P1 * s = P2 * P2 * (m * m * m) := by sorry"
QUOTE: appendix/output.txt:1: "=== HEURISMA LEVEL 3 EXOPLANET KEPLERIAN & MASS-RADIUS ANALYSIS ==="
QUOTE: appendix/sources.csv:11: "C9,Own statistical and chart analysis (appendix/analysis.py),appendix/analysis.py,Tier 2,2026-11-27,2026-11,own-computation,b98d892faa8355b0826c491b63699cc817d4873b1e26c831a8f8477d387cfae1,agent-fetched,2026-11-27T02:18:04Z"

Blind Back-Translation of `Challenge.lean` (`kepler_two_body_scaling`): Quantifies over nine integers (`Int`) `P1 P2 a1 a2 GM1 GM2 k s m`, assuming `k ≠ 0`, `GM2 ≠ 0` (unused in `Solution.lean` per `verify.json`), `a2 ≠ 0`, integer-multiple scaling `GM1 = s * GM2` and `a1 = m * a2`, and `P1^2 * GM1 = k * a1^3`, `P2^2 * GM2 = k * a2^3`, to conclude the integer ring identity `P1^2 * s = P2^2 * m^3` — with no real numbers, no positivity, no fractional exponents (`3/2`, `-1/2`), no `4π^2` constant, and `verification_mode = none` (`unverified_no_toolchain`).

1. [1] Section 4.3 & `appendix/formal/kepler-scaling/Challenge.lean:11` (`kepler_two_body_scaling`) — Even with Section 4.3 disclosure, the Lean theorem itself remains an unverified `Int` ring identity with unused `hGM` and `verification_mode = none` (`unverified_no_toolchain`), not a `Real`-valued proof of Keplerian scaling — Re-state `Challenge.lean` over positive `Real` numbers via Mathlib and verify with `lake build`.
2. [1] Section 4.2 (`pl_ratdor * st_rad` check, `n = 863`) — Claiming `a_tr = (a/R_⋆) R_⋆` eliminates circularity overlooks that 381 of 1,244 planets (30.6%) lack `pl_ratdor` or `st_rad`, and `st_rad` in composite `ps` can itself depend on transit-duration/stellar-density priors — Report the `n = 381` exclusion rate and compare `st_rad` provenance (spectroscopic/Gaia parallax vs transit-derived) on the `n = 863` subset.
3. [2] `appendix/fetch_data.py` & Section 7 (`soltype` provenance on the 25 `>3σ` Keplerian outliers) — `fetch_data.py` did not fetch `soltype` or `pl_orbsmaxlim` from the accessible NASA TAP `ps` table, leaving the 25 `>3σ` outliers (`24.5%` of `>5%` outliers with error bars) unattributed — Fetch `soltype` and test whether those 25 `>3σ` outliers are composite-vintage mismatches.
4. [3] Section 4.2 (`n = 151` missing-eccentricity stratum) — Missing-`e` planets (`n = 151`) exhibit more than triple the `|rel_res|` IQR (`1.6797%` vs `0.5064%` for `e > 0.1`), yet no control tests whether missing `e` or fixed `e = 0` (`n = 376`) drives the `339` `3*sigma_MAD` (`27.3%`) outlier tail — Run a Mann-Whitney / Kruskal-Wallis test across `e = 0`, `0 < e <= 0.1`, `e > 0.1`, and `missing e` strata.
5. [3] Section 5.1 (`Rocky` vs `Sub-Neptune` permutation `p = 0.0030` vs overlapping CIs) — Section 5.1 states the rocky-to-sub-Neptune slope difference has overlapping bootstrap CIs (`[0.1775, 0.6926]` vs `[0.4975, 0.5713]`) while simultaneously citing `permutation p = 0.0030`, without explaining the discrepancy between the asymmetric small-sample rocky bootstrap (`n = 31`) and the pooled-slope permutation test — Clarify the statistical basis of the `p = 0.0030` vs CI overlap in Section 5.1.
6. [4] Section 5.1 & `appendix/output.txt:42-44` (continuous knot choice `100 M_earth` vs `120 M_earth`) — The continuous 3-regime model with knots `(2, 100 M_earth)` (`BIC = -4515.75`) is worse by 32.9 BIC points than the disconnected 3-regime model (`BIC = -4548.65`) and worse by 28.48 BIC points than the `120 M_earth` knot (`BIC = -4544.23`), yet `100 M_earth` is retained as the primary knot — Profile-optimize the upper mass knot on BIC/CV RMSE rather than fixing `100 M_earth` ad hoc.
7. [4] `appendix/conjectures.json:194,198` (`falsifier_point`) — `conjectures.json` still labels `a_m = 1.496e+11` (1 AU) as `"beyond observed a_m max 6.732e+11"`, which is inside the observed domain — Document this `conjecture.py` template-string artifact in Section 4.1 or re-seal with an out-of-domain `falsifier_point`.
8. [5] Section 4.1 (`C_LAW_1` vs `C_LAW_2`) — `C_LAW_1` and `C_LAW_2` remain within 0.3% on `val_rmse` (`23,652.11 s` vs `23,577.95 s`), so empirical validation error alone does not separate them — Retained as a documented parsimony/dimensional-consistency choice.
9. [6] `appendix/sources.csv:11` (`C9` sha256 mismatch) — `sources.csv:11` still records `b98d892faa8355b0826c491b63699cc817d4873b1e26c831a8f8477d387cfae1` for `appendix/analysis.py`, whereas the current `ANALYSIS-SHA256` is `802b7ed3195c486d120724ec28e49b6f6070f982ec72b9d53921fd776ddab026` — Re-register `C9` in `appendix/sources.csv` so the recorded sha256 matches the edited `appendix/analysis.py`.

Coverage:
1. Over-calibrated claims — 2 items
2. Unattempted data shortcuts — 1 item
3. Missing counter-evidence and controls — 2 items
4. Interdisciplinary and forecasting flaws — 2 items
5. Decisions inside the noise — 1 item
6. Provenance contradictions — 1 item

MOST DAMAGING: 9 — `appendix/sources.csv` still records the pre-revision SHA-256 for `appendix/analysis.py` (`b98d892f...` vs `802b7ed3...`), breaking strict provenance parity between the registered `C9` source and the executed analysis script.
