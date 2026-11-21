# Validator codes (`validate_report.py --json`)

`python3 -B <skill-dir>/scripts/validate_report.py report.md --level 2 --html report.html --json` prints one JSON object:

```json
{"version": "0.8.0", "passed": false, "strict": false,
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
| `STRUCT-TAGS` | error | No canonical calibration tag anywhere in the report. |
| `STRUCT-HYPOTHESES` | error | Section 2 lacks explicit H₀ and H₁. |
| `MATRIX` | error | The Claim-Evidence Matrix is missing, too small, too narrow, or a row has no tag. |
| `P0-STRONG` | error | A `[Strong]` row rests only on weak sources (Tier 3, press, own computation, abstract-only), looked up in `sources.csv`. |
| `P0-STRONG-CITE` | error | A `[Strong]` row has no `[@id]` citation. |
| `P0-SHA` | error | A local file's recomputed SHA-256 differs from the one registered, or none is registered, or the file is missing. |
| `P1-ORPHAN` | warning | A file in `appendix/data/` is not registered by exact path or hash. |
| `P1-KIND` | error | `sources.csv` has no `kind` column, or a row has a blank or unknown kind. |
| `P1-VERDICT` | error | The Calibrated Verdict has more than 3 sentences or more than 5 numbers. |
| `P1-VERDICT-NUM` | warning / error | Verdict numbers absent from `output.txt`, or figures retyped instead of `{{num:key}}`. |
| `P1-UNTRACED-NUM` | warning / error | Statistical number in a Section 4 table cell is absent from both `output.txt` and `numbers.json` (numeric closure violation). |
| `P1-NUM-COVERAGE` | warning | Most Section 4 figures from `output.txt` are typed by hand. |
| `P1-ASOF` | error | The As-Of Date is in the future or earlier than the run start. |
| `P1-RUN` | warning / error | A failed attempt is inherited from an earlier run, `attempted_utc` or `run.json` is missing, or the run start is unknown. |
| `P2-SELECTION` | warning / error | Pre-intake provenance: a user-curated row without `retrieved_utc`, an unknown retrieval date above Tier 3, a local `user-curated` file declared Tier 1, an `intake.md` `user-curated` hash relabelled `agent-fetched`, an `agent-fetched` row with `retrieved_utc < run_started_utc` or lacking `download_log.csv`/`data_attempts.csv` proof, no Tier 1/2 (`data`/`literature`) agent-fetched counter-evidence outside the user's corpus, a claim resting only on user-curated documents (capped at `[Moderate]`, labelled "Selection bias: user-curated corpus"), or an unregistered file in `inbox/`. |
| `P2-PREREG` | warning / error | `appendix/preregistration.json` is missing at Level 3, was edited after sealing, was sealed post-hoc (`post_hoc=true` or `sealed_utc < run_started_utc`), contains exact computed figures from `numbers.json` in `H0`/`H1` (HARKing), or differs from Section 2 hypotheses. |
| `P2-DOMAIN` | warning | A declared tier or kind contradicts the source's domain (e.g. Tier 1 on a newspaper). |
| `SRC-OWN-TIER` | error | A row with `kind = own-computation` is declared Tier 1. |
| `SRC-FULLTEXT` | warning | A source titled "full text" has a failed attempt logged for the same URL. |
| `CITE-NONE` | error | Section 4 has no `[@id]` citations. |
| `CITE-UNKNOWN` | error | A `[@id]` does not exist in `sources.csv`. |
| `CITE-UNCITED` | warning / error | A source in `sources.csv` is never cited. |
| `L2-APPENDIX` | error | A Level 2+ report lacks `appendix/`, a script, `output.txt` or `sources.csv`. |
| `ATT-COLUMNS` | error | `data_attempts.csv` is unreadable or lacks canonical columns. |
| `FIG-JSON` | error | `charts.json` is missing (when figures are placed), invalid JSON, or not strict JSON (NaN, Infinity). |
| `FIG-SCHEMA` | error | A chart fails the schema (typo'd key, string or non-finite number, length mismatch, invalid date, observed `line` point after the report `As-Of Date`, unordered quantiles). |
| `FIG-DESIGN` | warning | A design problem: near-identical bars, a fan chart's `last_label` without `observed_until`, or fan quantiles diverging at the `observed_until` anchor. |
| `FIG-MARKER` | error | `{{fig:id}}` markers missing or pointing to an unknown chart. |
| `FIG-UNPLACED` | warning | A chart in `charts.json` is not placed with a marker. |
| `W2-NUM` | error | An unresolved `{{num:key}}` marker, or invalid `numbers.json`. |
| `GATE-MISSING` | warning / error | A gate file is missing, empty, or under 400 characters. |
| `GATE-MARKERS` | warning / error | A gate file lacks the markers its prompt fixes. |
| `GATE-QA` | warning / error | `qa.md` has no `QA: PASS` and the report does not accept the FAIL. |
| `GATE-BINDING` | warning / error | A gate's header is incomplete, its hash is stale (for `reviewer.md`, exempted once Section 5 has a closed Disposition Table), a quote does not match, or it is a self-review not declared in Section 3. |
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
| `REPRO` | error | `--reproduce` could not reproduce `output.txt`, `numbers.json` or `charts.json`. |
| `GEN` | — | Fallback: a message without its own code yet. |
