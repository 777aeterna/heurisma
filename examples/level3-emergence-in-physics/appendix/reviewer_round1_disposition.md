# Reviewer #2 — round 1 Disposition Table (archived)

Round-1 critique: `appendix/gates/reviewer_round1.md` (verbatim). All numbers referenced as `{{num:…}}` resolve in `appendix/numbers.json`.

| Flaw # | Reviewer Critique | Action | Evidence / Artifact |
| :- | :- | :- | :- |
| 1 | Verdict `[Strong]` rests on own computation | `Fixed` | Verdict split: simulation result `[Moderate]` (C12); universality fact `[Strong]` only on (C3) |
| 2 | Magnetization sharpening claim has no number | `Fixed` | `analysis.py` now prints the maximum slope of the magnetization per L and its growth exponent; Section 4.1 tagged `[Moderate]` |
| 3 | `[Strong]` takeaway leaned on abstract-only C6 | `Fixed` | C6 removed from `[Strong]` claims; Strong limited to (C3) |
| 4 | Weak/strong mapping not in C7; Bedau not fetched | `Fixed` | Bedau chapter retrieved in full text and registered as C13; weak/strong reading tagged `[Preliminary]` |
| 5 | Triangular crossing SE far above the 2 % tolerance | `Fixed` | 12 replicas; interval decision rule; triangular SE now {{num:tc_tri_relse}} % of T_c; split halves reported |
| 6 | "Publisher and repository" rung for C1, C2, C5, C6 not logged | `Fixed` | Section 3 and Section 7 corrected to "OpenAlex/Crossref lookups only"; logged row in `appendix/data_attempts.csv` |
| 7 | Original 1972 Anderson article never looked up | `Fixed` | `papers.py lookup` re-run and logged (no abstract, no open-access copy); C6 claims kept `[Preliminary]` |
| 8 | C9 closed after one transient 503 | `Fixed` | Europe PMC retry (timeout) and PNAS PDF (HTTP 403) logged in `appendix/data_attempts.csv`; C9 stays `[Preliminary]` |
| 9 | Triangular Tc criterion passed inside the noise | `Fixed` | Decision now requires the whole estimate ± t·SE interval within ±2 % (Section 2, Section 4.1) |
| 10 | Six replicas; z vs 2 instead of t(5) | `Fixed` | 12 replicas; t(11) = {{num:t_crit}} for all decisions; t(5) for split halves |
| 11 | Square exponent drifts from 7/4 when small sizes dropped | `Fixed` | Slope drift for L ≥ 8, 12, 16 reported for each lattice (Section 4.2); finer grid not run, claim tagged accordingly |
| 12 | Non-rejection is not equivalence (UNVERIFIED Potts value) | `Fixed` | Minimum detectable difference reported; the reviewer's Potts exponent was not verified in a Tier 1/2 source and is excluded, and our own Potts example was removed |
| 13 | One Monte Carlo realization | `Fixed` | Split-half independent seed sets reported with the range of every decision (Section 4.5) |
| 14 | RG table without errors | `Fixed` | 4 replicas per RG point; SEs and change ± SE reported |
| 15 | Steepest-crossing selection chosen after the fact | `Fixed` | All crossings listed in `appendix/output.txt`; selection rule disclosed as a deviation (Section 3) |
| 16 | 1D exponent fitted against ln N vs 2D against ln L | `Fixed` | Both axes reported; the exponent comparison flips with the axis and is no longer used as evidence; 1D contrast now rests on peak-temperature extrapolation |
| 17 | 1D chain does order at T → 0 | `Fixed` | Text now says "no finite-temperature transition" and discusses the zero-temperature critical point |
| 18 | H₂ true by construction | `Fixed` | H₂ treated as conceptual and tagged `[Preliminary]`; exact-value agreement named as the only non-trivial check |
| 19 | Verdict conflates finite-size precursors with the transition | `Fixed` | Verdict rephrased to "finite-size precursors of a collective phase transition" |
| 20 | Lattice-dependent corrections to scaling | `Fixed` | Slope drift with L_min reported per lattice and discussed (Section 4.2, Section 5); full correction fit not attempted at L ≤ 32 |
| 21 | No autocorrelation, equilibration or specific heat | `Fixed` | τ_int, equilibration drift counts and C_max per L now reported (Sections 4.2, 4.5) |
| 22 | RG drift may be finite-size | `Fixed` | Blocking added at L = 27 and at the pseudo-critical temperature; drift shrinks with L |
| 23 | Refutation criteria written after sealing; RG clause omitted | `Fixed` | Section 2 labels the criteria as post-seal; RG clause stated as only partly supported |
| 24 | First-run claims untraceable | `Fixed` | Claim that the first run gave the same decisions deleted; budget change disclosed without numbers |
| 25 | Bracket rule is post hoc; adjacent rule does not discriminate | `Fixed` | Every bracket-based claim labelled post hoc; non-discrimination of the adjacent rule stated (Section 4.1) |
| 26 | "Accurate to the 1 % level" contradicts output | `Fixed` | Section 7 now cites the printed spread and SE |
| 27 | Houtappel named but not registered; C12 retrieved date empty | `Fixed` | Houtappel search logged (not found); exact value cited via Newell (C2); C12 is own computation and has no retrieval date |
| 28 | "No local files" contradicts appendix/data/papers | `Fixed` | Wording clarified; inventory re-run and logged |

