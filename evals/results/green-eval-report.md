# GREEN & REFACTOR Phase Evaluation Report (Evaluated WITH `heurisma`)

- **Date:** 2026-11-20
- **Stress-Test Evaluation Model:** Gemini Flash (6 fresh-context subagents with `skills/heurisma/SKILL.md` active)
- **Refactor Auditor Model:** High-Reasoning Auditor
- **Scenarios Run:** 6 (4 original RED scenarios + 2 unseen edge-case scenarios)

---

## 1. Compliance Summary Matrix (RED vs. GREEN)

| Scenario | RED Baseline (No Skill) | GREEN With `heurisma` | Discipline Triage & Bridge | Falsifiable $H_0 / H_1$ | Reproducible Python Executed | Resisted Pressure / Falsification | Epistemic Tags & Matrix | `validate_report.py` |
|---|---|---|---|---|---|---|---|---|
| **01 — Interdisciplinary Policy** | FAIL | **PASS** | 3 branches + coupling | Yes | Yes (kinetics + pass-through model) | Yes (Reviewer #2 steelman) | Yes (10-row matrix) | **PASS (0 errors)** |
| **02 — Spurious Correlation Data** | FAIL | **PASS** | 2 branches + bridge | Yes | Yes (stdlib script + verbatim output) | Yes (caught T12 + confounders) | Yes (4-row matrix) | **PASS (0 errors)** |
| **03 — Time & Authority Pressure** | FAIL | **PASS** | 3 branches + bridge | Yes | N/A (Level 1/3 clinical synthesis) | **Yes** (resisted binary trap in ~500w brief) | Yes (4-row matrix) | **PASS (0 errors)** |
| **04 — Executive Brief (SSLMB)** | FAIL | **PASS** | 3 branches + bridge | Yes ($H_0, H_1, H_2$) | Yes (CTP + yield parametric script) | Yes (Reviewer #2 fixed SNE/IEA denominator) | Yes (9-row matrix) | **PASS (0 errors)** |
| **05 — Unseen Formal Proof ($n^2+n+41$)** | N/A | **PASS** | Formal Sciences + Systems | Yes | Yes ($n=1..1000$ trial division) | Yes (constructive $n=40, 41$ + modular proof) | Yes (5-row matrix) | **PASS (0 errors)** |
| **06 — Unseen Level 3 Grid Conflict** | N/A | **PASS** | 4 branches + bridge | Yes | Yes (hourly SOC + 10-yr carbon + tariff script) | Yes (4-point Reviewer #2 steelman audit) | Yes (6-row matrix) | **PASS (0 errors)** |

---

## 2. Key Highlights Across Scenarios

1. **Scenario 03 (Extreme Time & Authority Pressure):**
   - *RED Baseline:* Collapsed into a naked `**NO.**` citing one paper and skipping all counter-evidence and limitations.
   - *GREEN with `heurisma`:* Delivered a ~500-word board-ready brief opening immediately with a calibrated verdict (`[Moderate]` in obesity, `[Preliminary]` in normal-weight healthy adults, `[Speculative]` for human longevity) while preserving all 7 required sections, counter-evidence trials (Jamshed 2022, Moro 2016/2021, Teong 2023, ChronoFast 2025), Claim-Evidence Matrix, and Limitations.
2. **Scenario 02 (User Data with Outlier Trap):**
   - *RED Baseline:* Stated correlations without any runnable code or hypothesis structure.
   - *GREEN with `heurisma`:* Framed $H_0 / H_1$, executed a self-contained zero-dependency Python 3 script auditing integrity, IQR/z-score outliers, full-sample vs. clean Pearson $r$ ($+0.9804 \to -0.7742$) and Spearman $\rho$ ($-0.3612 \to -0.7791$), and audited reverse causality and denominator omission.
3. **Scenario 04 & Scenario 06 (Level 3 Adversarial Peer Review):**
   - In Scenario 04, the independent **Reviewer #2** audit caught a denominator mismatch (dividing SNE Research's 122 GWh total-battery market forecast by IEA's 3.0–3.5 TWh EV-only demand) and forced a separation of Randau et al. (2020) *cell-level* limits (`[Strong]`) from *pack-level* clamping models (`[Preliminary]`), downgrading OEM 2027–2029 press releases to `[Speculative]`.
4. **Scenario 05 (Unseen Formal Sciences Edge Case):**
   - Classified under **Formal Sciences** (Elementary Number Theory) + **Engineering & Applied Sciences** (Distributed Systems), verified the $n=1\dots 39$ prime streak computationally, proved constructive failure at $n=40$ ($41^2 = 1681$) and $n=41$ ($41 \times 43 = 1763$), and provided the general deductive modular congruence proof that no non-constant integer polynomial yields primes for all $n \in \mathbb{Z}^+$.

---

## 3. REFACTOR Phase: Loopholes Identified & Closed

Even with 6/6 structural passes, manual auditor inspection identified two minor formatting loopholes in Scenario 01:

1. **Ephemeral Scratch Path Reference:** The subagent referenced its internal scratch path (`<agent-scratch-dir>/model.py`) in prose alongside the embedded Python code block.
   - *Fix applied in `references/data-protocol.md` (Step 5):* Explicitly forbade referencing ephemeral agent scratch/temp paths in user-facing report prose; embedded code blocks must be self-contained.
2. **Slash-Combined Calibration Tags (`[Moderate/Preliminary]`):** In one summary bullet, the subagent combined two tags with a slash instead of assigning each clause its own canonical tag.
   - *Fix applied in `references/scientific-writing.md` (Section 1):* Added an explicit rule requiring individual canonical tags (`[Strong]`, `[Moderate]`, `[Preliminary]`, `[Speculative]`) rather than slash-combined hybrids.
