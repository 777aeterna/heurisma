# Validator codes (`validate_report.py --json`)

`python3 -B <skill-dir>/scripts/validate_report.py report.md --level 2 --html report.html --json` prints one JSON object:

```json
{"version": "0.11.0", "passed": false, "strict": false,
 "errors":   [{"severity": "error",   "code": "P0-SHA", "file": "appendix/sources.csv", "line": null, "message": "…"}],
 "warnings": [{"severity": "warning", "code": "P1-ORPHAN", "file": "appendix/data/", "line": null, "message": "…"}]}
```

Codes are stable: a fix script can act on `code` without parsing the English message, and a release can track the rate per code. `GEN` is the fallback for a message that has no code yet. `line` is `null` when the message does not point at a single line. Severity depends on the level: a code listed as *error / warning* is an error at Level 3 and a warning below it.

| Code | Severity | Meaning |
| :- | :- | :- |
| `STRUCT-EMPTY` | error | The report is empty. |
| `STRUCT-SECTION` | error | A required `## N.` section is missing. |
| `STRUCT-ORDER` | error | Sections are out of order. |
| `STRUCT-THIN` | error | A section has fewer words than its minimum. |
| `STRUCT-TAGS` | error | No canonical calibration tag anywhere in the report; when only another capitalisation is present (`[fuerte]`), the message names the exact spelling to use (tags are case-sensitive). |
| `STRUCT-HYPOTHESES` | error | Section 2 lacks explicit H₀ and H₁. |
| `MATRIX` | error | The Claim-Evidence Matrix is missing, too small, too narrow, or a row has no tag; a row that writes a tag in another capitalisation (`[fuerte]`) gets one message with the canonical spelling (`[Fuerte]`). |
| `P0-STRONG` | error | A `[Strong]` row rests only on weak sources (Tier 3, press, own computation, abstract-only), looked up in `sources.csv`, or on local tables whose cells inherit Tier 3 through `primary_source_id` in `appendix/data/sources_metadata.csv`. |
| `P0-STRONG-CITE` | error | A `[Strong]` row has no `[@id]` citation. |
| `P0-SHA` | error | A local file's recomputed SHA-256 differs from the one registered, or none is registered, or the file is missing. |
| `P1-ORPHAN` | warning | A file in `appendix/data/` is not registered by exact path or hash. |
| `P1-KIND` | error | `sources.csv` has no `kind` column, a row has a blank or unknown kind, or `sources.csv` contains an empty blank line. |
| `P1-VERDICT` | error | The Calibrated Verdict has more than 3 sentences or more than 5 numbers. |
| `P1-VERDICT-NUM` | warning / error | Verdict numbers absent from `output.txt`, or figures retyped instead of `{{num:key}}`. |
| `P1-UNTRACED-NUM` | warning / error | Statistical number in a Section 4 table cell, or in a chart `title`/`caption`/`source` in `charts.json`, is absent from both `output.txt` and `numbers.json` (numeric closure violation). A bare `1,00×` / `1.00x` ratio baseline is exempt. |
| `P1-NUM-COVERAGE` | warning | Most Section 4 figures from `output.txt` are typed by hand. |
| `P1-ASOF` | error / warning | The As-Of Date is in the future or earlier than the run start (error), or a `sources.csv` row's `data_as_of` is later than the As-Of Date (warning; error at Level 3). A month-only value (`2026-11`) is compared by month. |
| `P1-RUN` | warning / error | A failed attempt is inherited from an earlier run, `attempted_utc` or `run.json` is missing, or the run start is unknown. |
| `P2-SELECTION` | warning / error | Pre-intake provenance: a user-curated row without `retrieved_utc`, an unknown retrieval date above Tier 3, a local `user-curated` file declared Tier 1 or Tier 2, an `intake.md` `user-curated` hash relabelled `agent-fetched`, an `agent-fetched` row with `retrieved_utc < run_started_utc`, an `agent-fetched` `data` row lacking `download_log.csv`/`data_attempts.csv` proof, an `agent-fetched` `literature` row with no `used` attempt stamped after the run start that names its `claim_id` or URL, an `agent-fetched` Tier 1 `literature` row with no downloaded document and no `(web summary)` label (warning), no Tier 1/2 (`data`/`literature`) agent-fetched counter-evidence outside the user's corpus, a claim resting only on user-curated documents (capped at `[Moderate]`, labelled "Selection bias: user-curated corpus"), or an unregistered file in `inbox/`. |
| `P2-PREREG` | warning / error | `appendix/preregistration.json` is missing at Level 3, was edited after sealing, was sealed post-hoc (`post_hoc=true` or `sealed_utc < run_started_utc`), states two or more computed results from `numbers.json` in `H0`/`H1`, exactly or rounded to 0–2 decimals, at least one of them non-integer (HARKing; years, conventional thresholds and bare counts are ignored), or differs from Section 2 hypotheses; a file in `appendix/data/` that is absent from the sealed `known_artifacts`, `download_log.csv` and `intake.md` (added after sealing; warning). |
| `P3-PAPER` | warning / error | Checked when `appendix/papers.csv` (or `appendix/data/papers/EXCLUDED.csv`) exists: a `literature` `agent-fetched` source whose DOI the connector never retrieved, or retrieved before this run (warning; error at Level 3); a `preprint` or `report` declared Tier 1, whatever the row's `kind` or `selection` and wherever the DOI sits in its URL (error); a retracted work (error if cited, warning if only registered); a `sources.csv` title that does not match the one `papers.csv` records for that DOI (warning); a record imported rather than retrieved that sustains a Tier 1 source (warning; error at Level 3); a saved full text that is missing (unless `appendix/data/papers/EXCLUDED.csv` declares it withheld from this copy with the SHA-256 that `download_log.csv` logged), lies outside `appendix/data/papers/`, has no recorded SHA-256, or whose SHA-256 changed (error); an `EXCLUDED.csv` manifest without `papers.csv`, with missing columns or a malformed filename/SHA-256, with no `download_log.csv` download backing it, or whose file is present with another hash (error); a cached response in `appendix/data/papers/raw/` with no matching SHA-256 in `download_log.csv`; and any row or field of `papers.csv` (including `via`, `providers`, `is_oa`, `retrieved_utc`, or a descriptive field left empty) that the cached responses cannot account for, i.e. a hand-written or hand-edited registry (warning; error at Level 3). |
| `P4-LEAN` | warning / error | Checked when `appendix/formal_proofs.csv` exists or `sources.csv` contains a `kind=formal-proof` row (or when `--reproduce-lean` is passed explicitly): a `formal-proof` source missing from `formal_proofs.csv` or pointing to another `.lean` file, a `Tier 1`/`Tier 2` or `[Strong]` formal proof that is not `kernel-verified` or `comparator-verified` (`unverified_no_toolchain` is capped at `Tier 3`), missing or non-zero `sorries`, non-standard Lean axioms outside `{propext, Classical.choice, Quot.sound}`, stale `verified_utc < run_started_utc`, modified, malformed or missing `Challenge.lean` / `Solution.lean` / `verify.json` SHA-256 or inconsistent `verify.json` fields, forbidden escape tokens (`sorry`, `admit`, `axiom`, `opaque`, `@[extern]`, `@[implemented_by]`, `native_decide`, `Lean.ofReduceBool`), empty or vacuous/trivial `Challenge.lean` statements (`False ->`, `: True`), single-tactic algebraic proof closure or unused domain hypotheses in `Solution.lean` (warning), `--reproduce-lean` replay failure/skip/comparator downgrade, or an empirical measurement claim tagged `[Strong]` on `formal-proof` alone without formal scope qualification or empirical `Tier 1` evidence (warning only). |
| `P4-CONJECTURE` | warning / error | Checked when `appendix/conjectures.json` (or any `appendix/*conjecture*.json`) exists: tampered `sha256` or non-strict JSON, missing or insufficient train/holdout split (`holdout_count < 2` or `train_count < 4`), an unproved data-driven conjecture tagged `[Strong]` / `[Fuerte]` without an independent `Tier 1` formal proof or replicated `Tier 1` dataset (excluding the discovery `source_ids` themselves), or presenting a candidate law above `[Preliminary]` when `beats_null` is `false`. |
| `PRIV-CRED` | error | A text file anywhere under `appendix/` (up to 5 MB) contains `api_key=`, `mailto=` or `email=` followed by a value, or the value of `HEURISMA_OPENALEX_KEY` / `HEURISMA_MAILTO` (when the paper connector is in use): a key or contact address was written where the report is published. |
| `P2-DOMAIN` | warning | A declared tier or kind contradicts the source's domain (e.g. Tier 1 on a newspaper). |
| `SRC-META` | error / warning | `appendix/data/sources_metadata.csv` is malformed: a `source_id` that is empty or contains a space, a tier other than `Tier 1`/`Tier 2`/`Tier 3` (errors), a `data_as_of` later than the As-Of Date (warning; error at Level 3), or a local table whose `primary_source_id` values the catalogue does not define, which silently count as Tier 3 (warning). |
| `SRC-TIER` | error | A `sources.csv` row's tier is not exactly `Tier 1`, `Tier 2` or `Tier 3` (a bare `3` or `T3` would slip past every tier rule). |
| `SRC-OWN-TIER` | error | A row with `kind = own-computation` is declared Tier 1. |
| `SRC-FULLTEXT` | warning | A source titled "full text" has a failed attempt logged for the same URL. |
| `CITE-NONE` | error | Section 4 has no `[@id]` citations. |
| `CITE-UNKNOWN` | error | A `[@id]` does not exist in `sources.csv`. |
| `CITE-UNCITED` | warning / error | A source in `sources.csv` is never cited. |
| `L2-APPENDIX` | error | A Level 2+ report lacks `appendix/`, a script, `output.txt` or `sources.csv`. |
| `ATT-COLUMNS` | error | `data_attempts.csv` is unreadable or lacks canonical columns. |
| `FIG-JSON` | error | `charts.json` is missing (when figures are placed), invalid JSON, or not strict JSON (NaN, Infinity). |
| `FIG-SCHEMA` | error | A chart fails the schema (typo'd key, string or non-finite number, length mismatch, invalid date, observed `line` point after the report `As-Of Date`, unordered quantiles). |
| `FIG-DESIGN` | warning | A design problem: near-identical bars, a fan chart's `last_label` without `observed_until`, fan quantiles diverging at the `observed_until` anchor, a fan called calibrated without a `calibration` block (`method`, `source_id`), or a first projected `p10` above the last observed value. |
| `FIG-MARKER` | error | `{{fig:id}}` markers missing or pointing to an unknown chart. |
| `FIG-UNPLACED` | warning | A chart in `charts.json` is not placed with a marker. |
| `W2-NUM` | error | An unresolved `{{num:key}}` marker, or invalid `numbers.json`. |
| `GATE-MISSING` | warning / error | A gate file is missing, empty, or under 400 characters. |
| `GATE-MARKERS` | warning / error | A gate file lacks the markers its prompt fixes. |
| `GATE-QA` | warning / error | `qa.md` has no `QA: PASS` and Section 7 of the report does not cite `appendix/gates/qa.md` and name each failed check number. |
| `GATE-SV` | warning / error | `source_verifier.md` ends in `SOURCE-VERIFIER: FAIL` and Section 7 of the report does not cite `appendix/gates/source_verifier.md` to name and justify each accepted problem. |
| `GATE-DISP` | error | Level 3: `reviewer.md` raises N numbered critiques (`N. [category]`, `UNVERIFIED:` included; the coverage block is not counted) but the report's Disposition Table has a different number of rows with an action (Fixed / Refuted / Deferred). |
| `GATE-BINDING` | warning / error | A gate's header is incomplete, its hash is stale (for `reviewer.md`, exempted once Section 5 has a closed Disposition Table), a quote does not match, it is a self-review not declared in Section 3, or `reviewer.md` records an `ANALYSIS-SHA256` (over `appendix/analysis.py`) or `FORMAL-SHA256` (over `appendix/formal/*/Challenge.lean`) that the file(s) no longer match and Section 5 has no *Post-review changes* subsection (checked whenever `reviewer.md` exists). A gate with more than one `REVIEWED-SHA256` line (a second pass appended instead of replacing the file) is always an error. |
| `GATE-PRIVACY` | warning / error | A gate file quotes a home-directory path or an unquoted literal marker outside `QUOTE:` lines. |
| `PRIV-HOME` | error | `report.md` or `report.html` contains a home-directory path. |
| `HYG-FILES` | warning | Bytecode artifacts or 0-byte files in `appendix/`. |
| `R2-TABLE` | error | Level 3 without a Reviewer #2 Disposition table. |
| `R2-DEFERRED` | error | A `Deferred` critique without logged attempts. |
| `HTML-STALE` | warning | The HTML predates a change in its sources (or has no source hash). |
| `HTML-MISSING` | error | The HTML deliverable is missing or empty. |
| `HTML-SECTION` | error | The HTML lacks a required section heading. |
| `HTML-LANG` | error | A Spanish HTML report has the wrong `lang` or leaks English chrome. |
| `HTML-MARKER` | error | An unresolved `{{…}}` marker is left in the visible HTML. |
| `HTML-LATEX` | warning | Unconverted LaTeX in the HTML. |
| `REPRO` | error | `--reproduce` could not reproduce `output.txt`, `numbers.json` or `charts.json`, or a sealed artifact (`conjectures.json`, `preregistration.json`, `formal_proofs.csv`, `verify.json`) was re-written by the command. |
| `GEN` | — | Fallback: a message without its own code yet. |
