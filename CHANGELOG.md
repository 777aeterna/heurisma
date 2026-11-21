# Changelog

All notable changes to **Heurisma** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.1] - 2026-11-21 (Provenance Gaps, Caption Closure & Calibrated Fans)

Driven by a code-executing audit of v0.8.0 and by replaying a real Level 3 run through the new validator: a run that v0.8.0 passed with 0 errors and 0 warnings now reports 6 errors and 5 warnings, each a genuine provenance or traceability gap. Mutation detection goes from **25/25** to **34/34** (`M26`–`M34`).

### Added
- **Chart text closure (`P1-UNTRACED-NUM`):** figures in a chart's `title`, `caption` and `source` must appear in `appendix/output.txt` or `appendix/numbers.json`, like Section 4 table cells; a bare `1,00×` ratio baseline is exempt.
- **Retrieval proof for literature:** an `agent-fetched` `kind=literature` source needs a `used` row in `data_attempts.csv`, stamped at or after the run start, that names its `claim_id` or URL (warning at Level 2, error at Level 3). A Tier 1 literature row with no saved document and no `(web summary)` / `(resumen web)` / `(abstract only)` label gets a warning.
- **Tier inherited by local tables:** a `[Strong]` matrix row resting only on local tables whose `primary_source_id` rows map to Tier 3 in `appendix/data/sources_metadata.csv` is a `P0-STRONG` error. `tier` and `tier_classification` columns are both read.
- **Files added after preregistration:** a file in `appendix/data/` absent from the sealed `known_artifacts`, `download_log.csv` and `intake.md` raises a `P2-PREREG` warning, even if it is registered in `sources.csv`.
- **Calibrated fans:** a `fan` chart described as calibrated needs a `calibration` block (`method`, `source_id`); the first projected `p10` may not sit above the last observed value (`FIG-DESIGN`).
- **Reviewer anchor:** `--gate-header reviewer` also prints `ANALYSIS-SHA256`; if `appendix/analysis.py` changes afterwards, Section 5 needs a *Post-review changes* subsection (`GATE-BINDING`, checked whenever `reviewer.md` exists).
- **`SRC-TIER`:** the `tier` column must be exactly `Tier 1`, `Tier 2` or `Tier 3`; a bare `3` used to bypass every Tier 3 rule.
- **Nine new mutations (`M26`–`M34`)** and four test modules (`tests/test_v081_*.py`).

### Changed
- A local `user-curated` file can no longer be Tier 2 (it was only blocked at Tier 1): it stays Tier 3, and a stated origin counts only as a separate `agent-fetched` download made in this run.
- `--json`: `agent-fetched` provenance messages are now `P2-SELECTION` (they fell back to `GEN`), and every fan-chart design warning is `FIG-DESIGN` (the divergence warning was reported as `FIG-SCHEMA`).
- `SKILL.md`, `references/` and the three agent prompts (and their `agents/` mirrors) follow the code: local files are Tier 3, mixed tables carry `primary_source_id` + `sources_metadata.csv`, captions are built from computed variables, and at Level 3 the order is Reviewer #2 → Disposition Table → second source-verifier pass → QA. The source-verifier quotes only `sources.csv` / `data_attempts.csv`, so inserting the Disposition Table cannot shift its quoted lines.

### Fixed
- `local_data.worst_tier` ignored a `tier_classification` column and treated every id as unknown (Tier 3).
- Doc contradictions found by cold runs: `SKILL.md` and `data-protocol.md` taught a Tier 2 (and, in an example, Tier 1) cap for local files that the validator rejects.

### Known Debt / Pending Verification
- The 40 agent evaluations of `evals/rubric.md` and the PNG asset recompression are still pending (unchanged from v0.8.0).

## [0.8.0] - 2026-11-21 (Semantic Integrity, Frictionless Gates & Temporal/Chart Guards)

Driven by lessons from a full Level 3 cold-run evaluation of v0.7.0. Closes six semantic bypasses (`M20`–`M25`, bringing mutation detection from **19/25** to **25/25**), eliminates gate-workflow friction (`--gate-header`, closed-loop Reviewer #2 hash exemption, `QUOTE:` marker escaping), and hardens data ingestion and temporal/fan chart rules.

### Added
- **Six new adversarial mutations (`M20`–`M25`) in `tests/mutations.py`:** local `user-curated` Tier laundering (`M20`), backdated `agent-fetched` timestamps (`M21`), Tier 3 press-only counter-evidence (`M22`), observed `line` chart plotting dates past `As-Of Date` (`M23`), HARKing in `preregistration.json` (`M24`), and hand-typed Section 4 table statistics absent from `output.txt`/`numbers.json` (`M25`). `mutation_report.py --min-rate 1.0` catches **25/25**.
- **Numeric closure (`P1-UNTRACED-NUM`):** `validate_report.py` cross-checks statistical numbers in Section 4 table cells against `appendix/output.txt` and `appendix/numbers.json` (warning at Level 2, error at Level 3), excluding years, section references, citations, tiers, and engineering labels.
- **Gate-header CLI (`--gate-header <source_verifier|reviewer|qa> [--mode subagent|self-review]`):** emits `MODE`, `REVIEWED-SHA256`, and real UTC `REVIEWED-UTC` directly so gate timestamps are never typed by hand.
- **Mixed-source tier helper (`local_data.worst_tier`):** computes the weakest contributing tier across rows in composite tables.
- **Statistical helpers in `references/data-protocol.md`:** documented `partial_corr_trend` (partial correlation controlling for secular time trend) and `stratified_perm_pvalue` (within-stratum permutation test).

### Changed
- **Pre-intake & selection provenance (`local_data.py`, `validate_report.py`):** `NA_SENTINELS` (`""`, `"na"`, `"n/a"`, `"null"`, `"none"`, `"nan"`, `"—"`, `"-"`) are ignored during per-column CSV decimal inference and converted to `None`; `intake()` merges `## Channel: <channel>` sections idempotently into `appendix/intake.md`; `check_selection()` caps local `user-curated` files at Tier 2, blocks relabelling `intake.md` `user-curated` hashes to `agent-fetched`, requires `retrieved_utc >= run_started_utc` plus `download_log.csv`/`data_attempts.csv` proof for `agent-fetched`, and requires at least one Tier 1/2 (`data`/`literature`) `agent-fetched` source for counter-evidence.
- **Preregistration anti-post-hoc & anti-HARKing (`local_data.py`, `validate_report.py`):** `preregister()` records `known_artifacts` and rejects sealing after `output.txt`/`numbers.json` exist (unless `--allow-post-hoc`); `check_preregistration()` requires `appendix/preregistration.json` at Level 3, flags `post_hoc=true` and `sealed_utc < run_started_utc`, and flags exact computed decimals from `numbers.json` inside `H0`/`H1`.
- **Frictionless gates (`validate_report.py`, `render_report.py`):** `_check_gate_binding()` exempts stale-hash warnings on `reviewer.md` once Section 5 has a closed Reviewer #2 Disposition Table (allowing `--strict` without re-signing `reviewer.md`); `GATE-PRIVACY` ignores `QUOTE:` lines when checking for literal `{{num:}}`/`{{fig:}}` markers, and `render_report.py` escapes `{{` → `&#123;&#123;` inside embedded gate `<pre><code>` blocks.
- **Temporal & fan chart guards (`svg_charts.py`, `validate_report.py`):** `validate_charts_schema(..., as_of_date=...)` rejects observed `line` chart points dated after the report `As-Of Date` when `x.observed_until` is unset; `chart_warnings()` warns when `fan` quantiles diverge at the `x.observed_until` anchor.
- **Protocol, forecasting & agent prompts (`SKILL.md`, `references/`, `agents/`):** updated to match all v0.8.0 checks, including explicit *Parametric scenario bands* vs. *Calibrated fan* labeling (`references/forecasting.md`) and temporal/causal inversion + operational domain conflation checks in Reviewer #2 Category 4.
- **CI & branding:** removed `continue-on-error` from macOS/Windows jobs in `.github/workflows/validate-skill.yml` after 10/10 green runs; replaced repository banner with `assets/banner.jpeg`.

## [0.7.0] - 2026-11-21 (Epistemic Linter, Bound Gates & Pre-Intake)

Driven by an external code-executing audit of v0.6.1, which demonstrated that several v0.6.1 checks inspected surface form rather than ground truth. Every P0, P1, and P2 finding is addressed, and mutation detection rose from an honest baseline of **4/19** to **19/19** (`python3 -B tests/mutation_report.py --min-rate 1.0`).

### Added
- **Mutation test suite (`tests/mutations.py`, `tests/test_mutations.py`, `tests/mutation_report.py`):** 19 realistic violations applied to copies of the golden example, with rule-specific `EXPECT` assertions (preventing accidental "rebound" detection) and gate restamping to simulate a cover-up. Enforced at `--min-rate 1.0` in CI.
- **Recomputed SHA-256 verification (P0-1):** `validate_report.py` recomputes SHA-256 digests over every local source in `sources.csv` and every file in `download_log.csv`; tampered files fail with both hashes reported.
- **Artifact-bound gates & run start (P0-2, P1-1):** `local_data.py run-start` stamps `appendix/run.json` (`run_started_utc`); every gate file (`appendix/gates/{source_verifier,reviewer,qa}.md`) requires `MODE: subagent | self-review`, `REVIEWED-SHA256:` (via `validate_report.py --gate-hash <gate>`), `REVIEWED-UTC:`, and literal `QUOTE: file:line: "text"` lines verified against disk. `MODE: self-review` triggers a visible warning, must be disclosed in Section 3, and is labelled in the rendered HTML.
- **Validator tools & modes:** `--json` (machine-readable diagnostics with ~45 stable codes documented in `references/validator-codes.md`), `--reproduce` (re-runs `appendix/analysis.py` in a temporary copy and diffs `output.txt`, `numbers.json`, and `charts.json`), `--diff <other-run>`, `--version` (`0.7.0`), domain-tier heuristic warnings, and table-only Level 2 support (`charts.json` required only when `{{fig:}}` markers are present).
- **Bundled download helper (`skills/heurisma/scripts/fetch_lib.py`):** zero-dependency HTTP fetcher with exponential backoff, configurable User-Agent (`HEURISMA_UA`), size caps, optional checksum check, atomic writes, `download_log.csv` + `data_attempts.csv` logging, and `HEURISMA_OFFLINE=1` support.
- **Pre-flight data intake & preregistration (`local_data.py intake`, `local_data.py prereg`):** batch ingestion for `datos/` (`--channel data`) and `inbox/sources/` (`--channel sources`) writing `appendix/intake.md` (accepted/rejected files, per-column formats, wishlist gaps); `sources.csv` gains `selection` (`user-curated|agent-fetched|third-party`) and `retrieved_utc`; `appendix/preregistration.json` seals `H0`/`H1` and the analysis plan. Validator enforces `P2-SELECTION` (caps claims backed only by `user-curated` sources below `[Strong]`, requires selection-bias labeling, requires independent `agent-fetched` counter-evidence, checks `As-Of >= retrieved_utc` and snapshot age) and `P2-PREREG`.
- **Single-source-of-truth contracts (`skills/heurisma/scripts/contracts.py`) & sync guard (`tests/test_contracts_sync.py`):** centralizes `__version__`, EN/ES tags, `VALID_KINDS`, `VALID_SELECTIONS`, `SOURCE_COLS`, `ATTEMPT_COLS`, gate names/levels, and section patterns across all bundled scripts (compatible with `python -I`).
- **Hardened local file readers & security docs (`SECURITY.md`, `tests/test_security_limits.py`):** `read_xlsx` rejects XML `<!DOCTYPE`/`<!ENTITY` declarations (XXE / billion laughs) and zip bombs (uncompressed byte cap + 100× compression ratio check); `read_csv`/`read_json`/`read_xlsx`/`read_table` enforce `HEURISMA_MAX_BYTES` (default 100 MB) with clean `ValueError` errors.
- **Python ≥ 3.9 floor, Windows hardening & CI matrix:** `tests/test_python_floor.py` (AST `feature_version=(3, 9)` + 3.10+ API scan), `tests/test_windows_compat.py` (UTF-8 stdio reconfiguration in CLI `main()`, cross-drive `os.path.relpath` fallback to `file:///`, explicit `encoding="utf-8"`), `pyproject.toml` (dev-only `ruff`/`mypy` config), `.github/workflows/validate-skill.yml` matrix (`3.9`/`3.12`/`3.13` × Ubuntu/macOS/Windows), rewritten `docs/design.md` + `tests/test_docs_tree.py`, and preregistered `evals/rubric.md`.

### Changed
- **Lookup-based `[Strong]` enforcement (P0-3):** `[Strong]`/`[Fuerte]` claims without `[@id]` or backed only by weak sources in `sources.csv` (Tier 3, `press`, `blog`, `own-computation`, abstract-only) are now hard errors, regardless of prose wording.
- **Required `kind` column & verdict caps (P1-5, P1-7):** `kind` is mandatory in `sources.csv` at Level 2+ (`data`, `literature`, `press`, `own-computation`); Calibrated Verdicts exceeding 3 sentences or 5 numbers are errors at Level 2+.
- **Per-column CSV decimal inference & exact orphan matching (P0-4, P1-2):** `local_data.read_csv` infers decimal convention per column, rejects mixed-convention columns with `ValueError`, preserves zero-padded identifiers as strings, and adds `keep_strings`; orphan checks match exact normalized relative paths rather than substrings.
- **Renderer & chart schema hardening (P1-3, P1-4):** `render_report.py` supports balanced parentheses in URLs and `<url>`, escaped `\|` in table cells, strict URL scheme allowlist (`http`, `https`, `mailto`, `#`, relative), `<img>`, and code-fence-safe `{{num:}}` substitution; `svg_charts.validate_charts_schema()` rejects non-finite numbers, invalid dates, mismatched lengths, and inverted fan quantiles, and `validate_report.py` rejects non-strict JSON (`NaN`/`Infinity`).
- **Home-directory path leak (M19):** `/home/...`, `/Users/...`, and `C:\Users\...` paths in `report.md` or `report.html` are now validator errors.
- **Protocol placement & skill-TDD discipline:** Pre-intake is integrated as **Stage 0 step 9** (rather than a separate "Stage −1") because it depends on Stage 0 classification. User-curated corpus selection bias did not reproduce in 6 cold-start baseline trials (0/6), so no rationalization row or red flag was added to `SKILL.md`; enforcement lives deterministically in `validate_report.py` (`P2-SELECTION`).
- **Documentation & README claims:** Updated `README.md` with auditable claims (epistemic linter, measured `19/19` mutation detection, artifact-bound gates with explicit `self-review` labeling, `--reproduce`, Python ≥ 3.9, "Bring your own data", and link to `SECURITY.md`). Clarified in `references/data-protocol.md` that date-only `attempted_utc` is accepted only in reconstructed historical records (repository examples).
- **Examples:** Both `examples/level2-study` and `examples/showcase-hybrid-work` updated with `MODE: self-review` artifact-bound gates (and reconstructed `appendix/run.json` in the showcase), re-rendered with v0.7.0 freshness hashes, and verified with `--strict --reproduce` under both `-B` and `-I`.

### Known Debt / Pending Verification
- **Assets (`assets/banner.png` 612 KB, `assets/logo.png` 829 KB):** Left untouched because no external image optimization tools (PIL, `optipng`, `pngquant`, `cwebp`) were available in the offline build environment and pure-stdlib `zlib` level-9 recompression did not achieve the <400 KB target.
- **Renderer & chart i18n dictionaries:** Remain in `render_report.py` and `svg_charts.py` rather than `contracts.py`.
- **Multi-model agent evals (`evals/rubric.md`):** Rubric is preregistered; the 40 subagent runs (`n=5 × 2 models × 4 scenarios` → `evals/results/v0.7.0-agent-evals.md`) are pending execution.
- **Cross-OS & dev-linter CI verification:** macOS, Windows, Python 3.9/3.13, `ruff`, and `mypy` jobs could not be executed locally (offline Linux Python 3.12 environment); macOS/Windows matrix legs are marked `continue-on-error: true` until verified on GitHub Actions.

## [0.6.1] - 2026-11-20 (Gates That Cannot Be Faked)

Driven by the v0.6.0 audit. Several v0.6.0 checks could be satisfied without doing the work.

### Fixed
- **C1 — Gate files must carry their content, not just exist.** Each `appendix/gates/*.md` needs at least 400 characters plus the markers its prompt fixes:
  - `source_verifier.md`: seven `<#>. PASS|FAIL` lines and `SOURCE-VERIFIER: PASS|FAIL`;
  - `reviewer.md`: the six category titles and `MOST DAMAGING:`;
  - `qa.md`: eight `<#> PASS|FAIL` lines, `QA: PASS|FAIL` and `FAIL count: <n>`.

  The error names the missing marker. The three prompts now ask for this exact shape (`VERDICT:` became `SOURCE-VERIFIER:`), and a test keeps the validator and the prompts aligned.
- **C2 — A `data_attempts.csv` without `attempted_utc` no longer switches the inherited-attempts check off.** It counts as entirely inherited: error at Level 3, warning at Level 2. A run with no determinable start date warns `cannot determine run start; pass --run-since YYYY-MM-DD`.
- **C3 — Inherited-attempt check, fewer false alarms.** Only failures that end in a limitation count: an empty fallback, or one starting with `limitation`/`limitación`/`none`. So do failures that Section 7 or a `Deferred` row leans on, matched by shared words, because reports paraphrase their series names. On the audited run this cuts 21 errors to 10. The REM vintages whose official replacement was used drop out, and the exchange-rate band and floor are still caught.
- **C4 — The date is stamped by a tool.** `local_data.py attempt` and the new `append_attempt()` write a row with the real `attempted_utc`, widening an older file if needed. `SKILL.md` and `data-protocol.md` say never to type attempt rows or their dates by hand.
- **C5 — Retyped figures.** The Calibrated Verdict and Section 1 now fail if they retype 3 or more figures from `output.txt` without any placeholder: a warning at Level 2, an error at Level 3. For Section 4, the marker share required rose to 60 %. Section references such as `§ 4.3` or `Sección 4.3` are no longer counted as figures.
- **C6 — `x.last_label` works on fan charts.** It accepts a date, or `true` together with `x.observed_until`. The marker is drawn wherever that date falls inside the axis; near the left edge its label opens to the right. A fan chart with `last_label` but no date draws nothing, and `chart_warnings` reports `fan chart has last_label but no observed_until`.
- **C7 — `local_data.py register` (CLI).** Files inside the report folder are stored with a project-relative path; `file:///…` is kept only for files outside it. The docstring and help are corrected.
- **C8 — Gate privacy.** Gate files are embedded in `report.html`, so a home-directory path or a literal `{{num:…}}` / `{{fig:…}}` in them is flagged: a warning at Level 2, an error at Level 3.

### Changed
- Examples:
  - The gate records of both examples were rewritten in the v0.6.1 shape. They remain manual maintainer records. The showcase's source verifier still reports its 3 open provenance problems.
  - The showcase's `data_attempts.csv` now carries `attempted_utc` with the date only: the attempts were made on 2026-11-20 and their exact times were not recorded.

## [0.6.0] - 2026-11-20 (Inherited Runs, Gate Traces & Numbers as a Rule)

Driven by the audit of a v0.5.0 run. That run started from an earlier run's folder and kept a false "no official daily band series" limitation; it also discarded the official floor value as "inconsistent".

### Added
- **Inherited attempts no longer count:** `data_attempts.csv` gains `attempted_utc` (ISO UTC, written by `local_data.py` and the `fetch_data.py` template; an older 6-column file is widened, and its old rows stay undated). `validate_report.py` flags a failed series that has no attempt in this run (`--run-since YYYY-MM-DD`, default: first ISO date in the report header): error at Level 3, warning at Level 2. Files without the column are not checked (v0.5 compatibility).
- **`SKILL.md` Stage 0 detects an earlier run** (`report.md`, `data_attempts.csv`, `appendix/` in the folder or `datos/`) and treats its failures as unverified. A "no such series" claim now needs a logged search over the provider's whole catalogue with several keywords. Checked with three cold subagents under time pressure: all three re-ran rung 1 on the whole catalogue with dated rows. The audited run is the baseline failure.
- **Gate traces:** each subagent gate saves its answer to `appendix/gates/{source_verifier,reviewer,qa}.md`. A missing or empty file is a warning at Level 2 and an error at Level 3; `reviewer.md` is required at Level 3 only. `qa.md` must contain `QA: PASS`, unless the report cites it in Section 7 to accept a FAIL. The renderer embeds the gate files in the appendices.
- **`x.last_label`** on line/fan charts: a dotted "Last data: …" / "Último dato: …" marker where observations end before the X axis.

### Changed
- **`numbers.json` is required, not optional (Level 2+):** verdict, Section 1 and Section 4 table figures taken from `output.txt` must be `{{num:key}}`. The validator warns when five or more Section 4 numbers from `output.txt` are retyped and placeholders cover less than 30 % of them.
- **Local paths:** `import`/`register` store project-relative paths without a scheme (`appendix/data/x.csv`); `file:///…` is used only for files outside the report folder. v0.5 rows (`file://appendix/...`, which named `appendix` as a host) are still read and deduplicated.
- **Appendix README** must say which files `fetch_data.py` downloaded in this run and which were copied from `datos/` or an earlier run.
- **Reference-line labels** sit on a semi-transparent white box, so the series no longer runs through them.
- **Examples:** both examples carry `appendix/gates/` as **manual maintainer records**; no subagent output was saved for them. The showcase's source-verification record lists 3 open provenance problems, and its QA record has one accepted FAIL (the verdict quotes the external trial's quit rates). The showcase's local CSV row uses the relative path.

### Fixed
- The stale-HTML check no longer turns itself off silently under `python3 -I`: it loads `render_report.py` by path and warns if it cannot.
- `render_report.py` warns on stderr for each unresolved `{{num:key}}` in the report body.
- `3e-08` at the end of a sentence (`3e-08.`) is now typeset as 3×10⁻⁸.

## [0.5.0] - Not released separately, shipped in 0.6.0 (Silent-Failure Gates, Provenance & Subagents)

Driven by an external cold-run audit of v0.4.0 (two reports, fourteen figures) and a Reviewer #2 pass over the showcase.

### Added
- **`local_data.py import`:** copies a user file into `appendix/data/`, registers the **copy** (next free `L<n>`, project-relative `file://` URI, SHA-256, deduplicated by path and hash) and logs the rung in `data_attempts.csv`, in one step. `register` gained `--lang en|es`; `preview` reports bad JSON / empty CSV without a traceback.
- **`HEURISMA_OFFLINE=1`:** `local_data.offline_enabled()` / `log_offline_attempt()` and an `offline()` guard in the `fetch_data.py` template, to rehearse the local-data rung with the network off.
- **Source `kind` column** (`data`, `literature`, `press`, `own-computation`): `own-computation` + Tier 1 is an error; at Level 3 a `[Strong]` row backed only by own computations warns. A source titled "full text/open access" with a failed attempt for the same URL warns.
- **Stale-HTML detection:** `render_report.py` embeds `<!-- heurisma-sources: sha256:… -->`; the validator warns when `report.md`, `charts.json` or `appendix/` changed after rendering (or the HTML has no hash).
- **Chart engine:** wrapped category labels with automatic horizontal bars, `y.baseline` (visible "Truncated axis" notice), `diff: true` (relative difference), `x.min`/`x.max`, and a `near-identical bars` design warning.
- **Renderer:** `####`/`#####` headings, superscripts and scientific notation (`N^(−1/2)`, `3e-08`), typographic minus, localized local-file references that never show absolute paths.
- **Three optional subagents:** `heurisma-reviewer` (Opus), `heurisma-source-verifier` and `heurisma-qa` (Sonnet) as portable prompts (`skills/heurisma/references/agents/`) and Claude Code definitions (`agents/`), kept in sync by `tests/test_agents_sync.py`.

### Changed
- **Validator gates that failed silently now fail:** `charts.json` is found next to `report.md` (`--charts` overrides; missing at Level ≥ 2 is an error), an unresolved `{{num:key}}` or `{{…}}` left in the HTML is an error, and an uncited source is an error at Level 3.
- **`SKILL.md`:** source-verification gate before writing Sections 4/6, QA gate before presenting, `kind` column, "(abstract only)" titles, impersonal/plural voice, and `python3 -B appendix/analysis.py` (never `-I`). Measured with cold-start subagents: own code registered as Tier 1 fell from 3/3 to 0/3, the "full text" mislabel from 3/3 to 0/3, first-person prose from 1/3 to 0/3. Two audit findings (hypotheses decided inside Monte Carlo noise; a single deflator in a regime table) did **not** reproduce in 9 micro-tests and were deliberately left without a rule.
- **Examples:** both examples now register `analysis.py` as `own-computation` (Tier 2). The `showcase-hybrid-work` was rebuilt: the CSV is registered as unknown-origin Tier 3 (it never showed random allocation), every claim from it is capped at `[Preliminary]`, bootstrap intervals on 4 sites per arm were replaced by exact permutation tests (stratified, interaction tested directly), attrition is engineer-weighted, the proximity study is cited as a published difference-in-differences study (not an RCT) and the trial was read in full from its open-access copy.

### Fixed
- Negative-value labels in bar charts no longer collide with category labels (present since v0.4.0).

## [0.4.0] - 2026-11-20 (Local Data, Linked Citations & Full i18n)

### Added
- **Zero-Dependency Local Data Engine (`scripts/local_data.py`):** `inventory`, `preview`, `read_table`, `read_csv` (`;` delimiter, European decimal-comma `1.234,5`, `latin-1` fallback), `read_xlsx` (no `openpyxl`: shared strings, `inlineStr`, booleans, header auto-detection, footer-note pruning, `excel_date`), `read_json`, and `register_local` (`file://` URI + SHA-256 into `sources.csv`).
- **4-Tier Data Fallback Cascade & Local Protocol (`SKILL.md`, `references/data-protocol.md`):** Stage 0 local inventory, Stage 2 cascade (online primary → online alternatives → local data → limitation), extended Iron Law 3 (requiring online + local attempts, including tag-downgrade closures in `references/adversarial-review.md`), and optional `appendix/numbers.json` (`{{num:key}}`).
- **Linked In-Text Citations (`[@C1]`, `[@C1; @C4]`):** Appearance-ordered `<a href="#ref-n">[n]</a>` links and matching `<li id="ref-n">` References list in `render_report.py`.

### Changed
- **Publication SVG Polish (`scripts/svg_charts.py`):** Staggered non-overlapping annotations (up to 3 rows, right-edge flip, 16-char truncation), white-halo reference labels, scatter `nice_ticks` X-axis + `y=0` line + `highlight` point, `percent`/`thousands`/`currency` locale formatting (`en`/`es`), tighter Y-axis bounds, compact bottom margins, and localized 3-layer fan legend (`Mediana (P50)`, `P25–P75`, `P10–P90`) without median markers.
- **Full `en`/`es` Working-Paper Renderer (`scripts/render_report.py`):** Auto-detected `<html lang>`, zero leaked English chrome in Spanish reports, currency-safe inline LaTeX-to-HTML/Unicode conversion, nested `<ul>` lists, deduplicated Abstract vs. §1 Verdict, footer credit with `--no-credit`, `--lang`, and `--numbers` CLI flags.
- **Hardened Validator (`scripts/validate_report.py`):** Added V1 (`{{fig:id}}` ↔ `charts.json`), V2 (`[@id]` citations ↔ `sources.csv`), V3 (Spanish HTML language purity), V4 (unconverted LaTeX warning), V5 (`file://` SHA-256 check, orphan `appendix/data/` warning, canonical `data_attempts.csv` columns), V6 (`__pycache__`/`.pyc`/0-byte hygiene warnings), P11 verdict-number cross-check, and `--strict` flag.
- **Skill Hygiene:** Standardized `python3 -B` across `SKILL.md`, references, CI, and tests; removed hardcoded version from `data-protocol.md` `User-Agent` and fixed paired bootstrap resampling.

## [0.3.0] - 2026-11-20 (Paper-Grade Edition)

### Added
- **Publication-Grade SVG Engine (`scripts/svg_charts.py`, stdlib only):** Heckbert nice-number axis ticks, horizontal gridlines, clean calendar-year date axes, multi-series Okabe-Ito colorblind-safe palette + print-safe dash styles, automatic marker hiding (>30 points), vertical event `annotations`, shaded `bands`, `fan` projection charts (P10–P90 / P25–P75 / P50), grouped `bar` charts, safe `log` scale, and `<title>`/`<desc>` accessibility.
- **Working-Paper Reference Example (`references/example-report.md`):** Compact gold-standard paper example demonstrating abstract density, `{{fig:id}}` placement, and booktabs tables.
- **Reproducible Ingestion & Direct Chart Emission:** `appendix/fetch_data.py` with explicit `User-Agent` and SHA-256 logging, `appendix/analysis.py` emitting `charts.json` v2 directly, and `appendix/README.md`.

### Changed
- **Working-Paper HTML Renderer (`scripts/render_report.py`):** Replaced dashboard layout with Charter/Georgia serif typography, 720px single column, formal title/abstract block, booktabs tables with right-aligned numeric cells, sober small-caps epistemic tags, inline numbered `{{fig:id}}` figures, auto-generated References from `sources.csv`, `@media print` / `@page` A4 rules, and strict appendix filtering (never embeds `appendix/data/`, binaries, or >200 KB files).
- **Hardened Validator (`scripts/validate_report.py`):** Fixed single-dash Markdown separators (`:-`), accepted backticked Reviewer #2 actions (`` `Fixed` ``), raised substance floors (≥30 words in §1/§4, ≥2 matrix rows), added press/blog keyword & `sources.csv` Tier 3 detection against `[Strong]`, added Spanish localized tags (`[Fuerte]`, `[Moderada]`, `[Preliminar]`, `[Especulativa]`), and enforced `data_attempts` cross-checking for `Deferred` Level 3 critiques.
- **Single-Language Discipline & Abstract Verdict:** Strict ≤3-sentence / ≤5-number verdict limit and 100% Spanish template (zero Spanglish).

## [0.2.0] - Local Preview

### Added
- Stage 6 deliverables, zero-dependency `render_report.py`, `references/forecasting.md`, Level 0 Light Mode, `sources.csv` + Data-Attempts registry, closed Reviewer #2 Disposition Table, MAD + Bootstrap 95% CI helpers, and bilingual EN/ES validator support.

## [0.1.0] - 2026-11-20

### Added
- Core scientific-method agent skill (`skills/heurisma/SKILL.md`), 4 modular reference guides, zero-dependency `validate_report.py`, RED–GREEN–REFACTOR evals, showcase examples, logo, and GitHub Actions CI.
