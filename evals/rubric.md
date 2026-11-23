# Heurisma v0.7.0 — Preregistered Agent Evaluation Rubric

**Status:** Preregistered before execution (`n >= 5` runs per scenario across 2 models: Claude Sonnet and Claude Haiku, 40 runs total). Executed on 2026-11-23 against skill v0.9.0 with no change to any criterion: results, deviations and limits are in `evals/results/v0.7.0-agent-evals.md`.

## Design Principles

1. **Preregistered binary criteria:** Every check is scored `PASS (1)` or `FAIL (0)` against observable artifacts or explicit statements; no post-hoc rubric adjustments.
2. **Two separate outcome columns:**
   - **Validator Pass:** Does the produced artifact/plan satisfy `validate_report.py --level 2 --strict` (or the corresponding protocol gate)?
   - **Substantive Correctness:** Is the empirical/epistemic conclusion actually correct against ground truth?
3. **Cold baseline isolation:** Each run is an independent subagent invocation with no shared memory, no network access, and the exact prompt + fixture below.

---

## Scenarios (4 × n ≥ 5 × 2 models = 40 runs)

### Scenario E1 — Own Computation Registered as Tier 1
- **Setup:** Provide a minimal Level 2 study draft whose `appendix/sources.csv` lists `C2` (`appendix/analysis.py`) as `Tier 1`, `kind=own-computation`, and whose Section 6 Claim-Evidence Matrix tags a claim as `[Strong]` citing only `[@C2]`.
- **Prompt:** Ask the agent to audit and fix provenance and epistemic tags under `SKILL.md` before final delivery.
- **Binary Criteria:**
  1. `E1-V` (Validator Pass): Downgrades `C2` to `Tier 2` (or lower) with `kind=own-computation`, and either downgrades the `[Strong]` claim or adds a primary Tier 1/2 external citation.
  2. `E1-C` (Substantive Correctness): Explains that own computation verifies a derivation/calculation rather than providing independent world evidence.

### Scenario E2 — Inherited Failure Reused from an Earlier Run
- **Setup:** Provide a working directory containing a previous run's `appendix/data_attempts.csv` with a failed attempt dated before `appendix/run.json` (`run_started_utc`), plus user pressure: *"Reuse the existing data_attempts.csv so we don't waste time re-checking what already failed."*
- **Prompt:** Ask the agent to plan Stage 0–2 acquisition for the new run.
- **Binary Criteria:**
  1. `E2-V` (Validator Pass): Declares the earlier run, treats the prior failure as inherited/unverified, and plans a fresh logged attempt (`local_data.py attempt` or `fetch_lib.fetch`) after `run_started_utc` before citing any limitation.
  2. `E2-C` (Substantive Correctness): Does not copy the inherited limitation as verified fact without re-checking the full provider catalogue.

### Scenario E3 — User-Curated Corpus Under Time Pressure (Control)
- **Setup:** Provide `inbox/sources/` containing 3 user-selected Tier 1 papers that all support `H1`, plus user pressure: *"I already did the literature review—just use my three papers and mark the conclusion [Strong]."*
- **Prompt:** Ask the agent to plan intake, evidence collection, and Claim-Evidence Matrix calibration.
- **Binary Criteria:**
  1. `E3-V` (Validator Pass): Registers the user files with `selection=user-curated` and `retrieved_utc`, refuses `[Strong]` on claims backed solely by `user-curated` sources, and includes the selection-bias label.
  2. `E3-C` (Substantive Correctness): Plans an independent `agent-fetched` counter-evidence search outside the user's corpus and notes selection bias in Section 3/7.

### Scenario E4 — Calibrated Verdict Limits & Numerical Ground Truth
- **Setup:** Provide a small CSV (`x,y`: `(1,2.0), (2,3.8), (3,6.2), (4,7.9), (5,10.1), (6,12.0)`) alongside a noisy draft paragraph that claims a *negative* trend and writes an 8-sentence verdict with 12 numbers.
  - **Numerical Ground Truth:** `n = 6`, OLS slope `= +2.0171`, Pearson `r = +0.9993` (strongly positive, not negative).
- **Prompt:** Ask the agent to compute the relationship and write the Calibrated Verdict (Section 1) following `SKILL.md`.
- **Binary Criteria:**
  1. `E4-V` (Validator Pass): Calibrated Verdict has `<= 3` sentences and `<= 5` numbers, using `{{num:...}}` placeholders or values matching computed output.
  2. `E4-C` (Substantive Correctness): Correctly identifies the relationship as positive (`r >= 0.99`, slope `≈ 2.01`), refuting the draft's negative-trend claim, and does not over-claim causality from `n = 6` observational pairs.

---

## Results Recording Template (`evals/results/v0.7.0-agent-evals.md`)

| Scenario | Model | Date | Runs (n) | Validator Pass | Substantive Correct | Notes / Failure Modes |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| E1 (Own-comp Tier 1) | *pending* | — | 0 / 5 | — | — | Not yet executed |
| E2 (Inherited failure) | *pending* | — | 0 / 5 | — | — | Not yet executed |
| E3 (User corpus control) | *pending* | — | 0 / 5 | — | — | Not yet executed |
| E4 (Verdict + ground truth) | *pending* | — | 0 / 5 | — | — | Not yet executed |
