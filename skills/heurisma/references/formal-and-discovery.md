# Formal Mathematics (Lean 4 / Lake) & Symbolic Theory Discovery

Part of **Heurisma** (loaded on demand when an inquiry involves mathematical or logical theorems, Lean 4 formal verification, dimensional analysis, or discovering symbolic laws/conjectures from empirical data). Both tools are **100% opt-in** and use only the Python ≥ 3.9 standard library; local `lake` / `lean` (plus optional `comparator` and `landrun`) are detected automatically when installed and never auto-installed.

---

## 1. Symbolic Theory Discovery & Buckingham $\Pi$ (`<skill-dir>/scripts/conjecture.py`)

When an empirical dataset exhibits an unknown scaling law, conservation invariant, or functional relationship, use `conjecture.py` to enforce exact dimensional homogeneity and discover parsimonious candidate laws on an uncontaminated train/holdout split before elevating any equation to a hypothesis or formal theorem.

### 1.1 Exact Dimensional Analysis & Buckingham $\Pi$ (`units`)

Every physical equation must be dimensionally homogeneous over the 6 SI base dimensions (`M, L, T, Theta, I, N`), computed with exact rational exponents (`fractions.Fraction`):

```bash
python3 -B <skill-dir>/scripts/conjecture.py units \
    --target "T=s" \
    --var "L=m" --var "g=m/s^2" --var "m=kg"
```

- Rejects any target variable whose base dimensions lie outside the rational column space of the predictors (`UnitError`), dropping dimensionally orphaned predictors automatically (for example, mass `m=kg` in a simple pendulum).
- Emits the dimensionless $\Pi$ groups ($\Pi_1, \dots, \Pi_{n-r}$) from the rational nullspace of the dimension matrix.

### 1.2 Uncontaminated Train / K-Fold CV / Holdout Symbolic Search (`discover`)

```bash
python3 -B <skill-dir>/scripts/conjecture.py discover appendix/data/pendulum.csv \
    --target T \
    --predictors L,g,m \
    --units "T=s,L=m,g=m/s^2,m=kg" \
    --source-ids C5,C6 \
    --falsifier-at "L=2.5,g=9.80665,m=1.0" \
    --holdout-fraction 0.25 \
    --holdout-mode tail \
    --out appendix/conjectures.json
```

#### Epistemic & Statistical Guarantees (`P4-CONJECTURE`)
1. **Joint Data-Driven & Dimensional Search (`B1`, `--units`):** `conjecture.py discover` **always** evaluates the 9 data-driven model families (`linear`, `linear_2var`, `power_law`, `power_law_rational`, `shifted_power`, `inverse_log`, `exponential`, `rational_ratio`, plus `null_constant`) on all varying predictors—even when `--units` is omitted (so an unconstrained search without a dimensional-closure column always runs). When `--units` is supplied, `discover` **additionally** evaluates the exact Buckingham $\Pi$ families (`buckingham_pi_monomial`, `buckingham_pi_power`) and tags every candidate with `"dimensionally_consistent": true | false`. Any predictor with zero variance on `train` (e.g., a constant central `GM` column) or a small training split (`train_count < 10`) is automatically flagged in `conjectures.json["warnings"]` and excluded from singular free regressions.
2. **Strict Holdout Isolation (`P-02`):** Candidate generation, domain/pole filtering, rational exponent grid search, and model selection run **exclusively** on the training partition (`train_count >= 4`) using internal contiguous $K$-fold out-of-fold validation (`_val_bic`). The holdout partition (`holdout_count >= 2`, `tail` extrapolation by default so the law is tested outside the fitted range) is touched **once** after candidate ranking is frozen, solely to report `holdout_rmse` and `holdout_r2`.
3. **Common-Scale BIC & Multiplicity Penalty (`P-08`):** Every candidate family is evaluated on the **original target scale** (`likelihood_scale = "additive_gaussian_y"`). The top candidate ranked by out-of-fold `_val_bic` sets `beats_null = true` only when `(null_train_bic - train_bic) >= 6 + 2 * ln(M_evaluated)`, `val_rmse < null_val_rmse`, `holdout_rmse < 0.95 * null_holdout_rmse`, and `holdout_r2 > 0.10`.
4. **Conservation Invariants:** Pass `--target __invariant__` to search for non-trivial zero-variance combinations $g(x) \approx c_0$ across regimes (`linear_invariant`, `linear_invariant_rational`, `monomial_invariant`).
5. **Tamper-Evident Sealing, `--source-ids`, `--falsifier-at` & Calibration Ceiling (`M59`, `M61`, `M62`):** `appendix/conjectures.json` (and any secondary `appendix/*conjecture*.json`) embeds a canonical 64-hex `sha256` digest over its payload, the input CSV's 64-hex `data_sha256`, the `--source-ids` (`sources.csv` claim IDs from which the discovery table was built), and an explicit `falsifier_point` / `falsifier_prediction` (`max_abs_error <= ...`, configurable via `--falsifier-at col=val,...`).
   - An empirical symbolic conjecture discovered on dataset $D$ is **capped at `[Preliminary]` or `[Moderate]`** on $D$ (`M59`).
   - To reach `[Strong]` / `[Fuerte]`, the claim must cite **either** an independent `Tier 1` formal proof (`kind=formal-proof`, verified in `appendix/formal_proofs.csv`) **or** an independent `Tier 1` replication dataset (never the discovery `source_ids` themselves; pass `--source-ids C5,C6` when sealing a derived discovery CSV). If `beats_null` is `false`, any claim above `[Preliminary]` triggers a `P4-CONJECTURE` warning.

---

## 2. Formal Mathematical Verification (`<skill-dir>/scripts/formal_math.py`)

Heurisma follows the [`anthropics/formal-math`](https://github.com/anthropics/formal-math) two-file layout under `appendix/formal/<slug>/`:
- **`Challenge.lean` (`namespace Challenge`):** states the target definitions and theorem signatures (`:= by sorry` is permitted here as the open challenge specification, while custom axioms and vacuous hypotheses are forbidden).
- **`Solution.lean` (`import Challenge`, `namespace Solution`):** proves every theorem declared in `Challenge.lean` with **zero `sorry`** and without referencing any `sorry`-backed `Challenge` symbol.

### 2.1 Commands

```bash
# 1. Scaffold a Lean 4 / Lake project (optionally seeded from appendix/conjectures.json)
python3 -B <skill-dir>/scripts/formal_math.py init kepler-third-law --appendix appendix \
    --theorem kepler_scaling --statement "(n : Nat) : n + 0 = n" \
    [--from-conjecture C_LAW_1] [--toolchain "leanprover/lean4:v4.16.0"] [--mathlib]

# 2. Verify the proof with the Lean 4 kernel (and optional comparator / landrun), writing verify.json
#    and updating appendix/formal_proofs.csv, appendix/sources.csv, and appendix/data_attempts.csv
python3 -B <skill-dir>/scripts/formal_math.py check kepler-third-law --register --claim FM1 --appendix appendix [--require-kernel]

# 3. Read-only fetch of an external benchmark problem (e.g., from anthropics/formal-math)
#    Hashed in appendix/download_log.csv via fetch_lib.fetch(..., allow_private=False); honors HEURISMA_OFFLINE=1
python3 -B <skill-dir>/scripts/formal_math.py fetch-ref anthropics/formal-math/eth --appendix appendix \
    [--branch main] [--files Challenge.lean]
```

### 2.2 What `formal_math.py check` and `checks/formal.py` (`P4-LEAN`) Enforce

1. **Nested-Comment & String Escape Scanner (`P-07`, `B5`):** Strips arbitrarily nested Lean block comments (`/- ... -/`), line comments (`-- ...`), string literals (including `s!"…"` / `f!"…"` interpolation), and `'…'` char literals before scanning. Forbids `sorry` and `admit` in `Solution.lean`; forbids `axiom`, `opaque`, `@[extern]`, `@[implemented_by]`, `native_decide`, and `Lean.ofReduceBool` in both `Challenge.lean` and `Solution.lean`; rejects empty, vacuous, or trivial `Challenge.lean` theorems (`(h : False)`, `False ->`, `: True`, or zero declared `theorem`/`lemma` items). It records `trivial_proof_warnings` (`single_tactic_proof:<thm>:<tactic>` when closed by a single automation tactic such as `ring`/`simp`/`simpa`/`simp_all`/`nlinarith`/`aesop`/`omega`/`tauto`/`positivity`/`abel`), surfaced as a `P4-LEAN` validator warning, and a separate informational `unused_hypothesis:<thm>:<h>` list (a purely lexical heuristic that cannot tell that `positivity`/`linarith`/`nlinarith` consumed a hypothesis implicitly; it is never surfaced as a hard warning).
2. **Statement Pairing & Kernel Definitional-Equality Witness (`P-01`):**
   - Statically pairs every theorem in `Challenge.lean` with its counterpart in `Solution.lean` using namespace-qualified names (nested namespaces such as `Challenge.Inner` are supported) and forbids calling `Challenge.<thm>` inside `Solution.lean`. A static signature difference is recorded as an informational warning, not a hard failure: the Lean kernel witness below is the authoritative check.
   - When `lake` / `lean` is installed, generates an ephemeral `_HeurismaAxiomAudit.lean` that compiles a **Lean kernel definitional-equality witness** (`def _heurisma_same_stmt {P : Prop} (_ : P) (proof : P) : P := proof` and `def _heurisma_witness_i := _heurisma_same_stmt (@<Challenge.qualified>) (@<Solution.qualified>)`) and runs `#print axioms <Solution.qualified>`. Every depended-on axiom must belong to `STANDARD_LEAN_AXIOMS`:
     `propext`, `Classical.choice`, `Quot.sound`.
   - Writes a `comparator.json` config (`challenge_module`, `solution_module`, `theorem_names`, `permitted_axioms`) for optional `leanprover/comparator` verification. When the standalone `comparator` binary is installed (`HEURISMA_COMPARATOR` or `comparator` on `PATH`), it is run after the kernel check (`status = "comparator-verified"`, `verification_mode = "comparator"`; otherwise `status = "kernel-verified"`, `verification_mode = "kernel-defeq"`); the comparator additionally requires `landrun` and `lean4export` on `PATH`. When `landrun` is available (`HEURISMA_LANDRUN`), `lake build`, the axiom audit, and the comparator run are all wrapped in a read-only sandbox. Under `HEURISMA_OFFLINE=1`, sets `GIT_CONFIG_COUNT=1` (`protocol.allow=never`) so `lake` never fetches remote git packages (`P-05`).
3. **Graceful Degradation Without `lake` (`M56`):** If `lake` / `lean` is not installed on the machine, `formal_math.py check` runs all static hazard and statement-pairing checks, records `status = "unverified_no_toolchain"` (`verification_mode = "none"`), and registers the source at **`Tier 3`** (`[Preliminary]` ceiling). `check` exits non-zero (2) for an unverified proof; exit code `0` is reserved for `kernel-verified` / `comparator-verified`.
4. **Registry Schema (`appendix/formal_proofs.csv`, `FORMAL_PROOF_COLS`):**
   `proof_id, slug, theorem_name, challenge_file, challenge_sha256, solution_file, solution_sha256, toolchain, lean_version, verification_mode, status, sorries, axioms, verified_utc`
   Every `sources.csv` row with `kind = formal-proof` must match a row in `appendix/formal_proofs.csv` (`M60`) and point to `appendix/formal/<slug>/Solution.lean` (or `Challenge.lean`). `validate_report.py` recomputes the full SHA-256 of `Challenge.lean` and `Solution.lean` against both `appendix/formal_proofs.csv` and `appendix/formal/<slug>/verify.json`.
5. **Opt-In Safe Lean Replay (`--reproduce-lean`, `P-04`):** Because `lake build` executes `lakefile.toml` / `lakefile.lean` and Lean metaprograms (`macro`, `elab`, `#eval`), `validate_report.py --reproduce` **never** invokes `lake`. To replay Lean kernel verification in a clean temporary copy (after stripping any pre-built `.lake/build/` `.olean` files), pass `--reproduce-lean` explicitly on trusted reports:
   ```bash
   python3 -B <skill-dir>/scripts/validate_report.py report.md --level 3 --html report.html --strict --reproduce --reproduce-lean
   ```

---

## 3. The Statement-Fidelity Law & Interdisciplinary Deductive Bridge (`P-03`, `P-10`)

A Lean 4 kernel proof guarantees that `Solution.lean` proves `Challenge.lean` — it **cannot** guarantee by itself that `Challenge.lean` faithfully formalizes the natural-language claim in `report.md` or that the mathematical axioms hold in an empirical system.

1. **Statement-Fidelity Law (`P-03`):**
   - Never simplify a non-linear or real-valued (`Real` / `Float`) hypothesis into a trivial identity or `Nat` toy lemma in `Challenge.lean` while claiming in `report.md` that the general theorem was proved.
   - Include the exact `Challenge.lean` theorem signature (or its verbatim mathematical translation, including domain restrictions such as $x > 0$ or linearity) in Section 3 or Section 4 of `report.md`.
   - At Level 3, `--gate-header reviewer` records `FORMAL-SHA256` over `appendix/formal/*/Challenge.lean`, and **Reviewer #2** performs a **blind back-translation** of `Challenge.lean` into natural language *before* reading `report.md`'s claim prose to expose any statement-fidelity gap.
2. **Deductive-to-Empirical Bridge (`P-10`):**
   - In an empirical inquiry (*Natural/Physical, Biomedical, Social/Economics, Engineering*), a `[Strong]` / `[Fuerte]` claim that rests **solely** on a `kind=formal-proof` citation must explicitly scope the sentence to the formal model (*"Under the idealized linear model […]"* / *"Bajo el modelo formal […]"*).
   - If the claim asserts an empirical measurement or real-world observation (*"measured"*, *"observed"*, *"field experiment"*), pair the `formal-proof` citation with an independent empirical `Tier 1` dataset/study (`[@FM1; @C1]`), or `validate_report.py` emits a `P4-LEAN` bridge warning.
