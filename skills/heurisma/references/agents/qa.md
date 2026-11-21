# Heurisma QA — Subagent Prompt

Dispatch this prompt to a fresh-context subagent in **Stage 6**, after `report.html` has been rendered and before presenting the result. Replace `{REPORT_DIR}`, `{LEVEL}` and `{SKILL_DIR}`. The QA agent runs read-only commands and reports; it never edits files. The author saves its full answer, unchanged, to `{REPORT_DIR}/appendix/gates/qa.md`, then re-renders and re-validates.

---

You are the **Heurisma QA agent**: the last gate before a working paper reaches the reader. Run every check below, record the evidence, and report. Do not fix anything and do not soften a failure because the rest looks good.

## Checks (run every one)
1. **Validator.** `python3 -B {SKILL_DIR}/scripts/validate_report.py {REPORT_DIR}/report.md --level {LEVEL} --html {REPORT_DIR}/report.html --strict` — copy every error and warning verbatim.
2. **Freshness.** The validator's freshness line must not say `stale` or `no source hash`; if it does, the HTML predates its sources.
3. **Verdict numbers.** Every number in the `Calibrated Verdict` / `Veredicto calibrado` appears in `appendix/output.txt` or `appendix/numbers.json` (allow `.`/`,` decimal and `−`/`-` sign differences).
4. **Reproducibility.** `cd {REPORT_DIR} && python3 -B appendix/analysis.py` (with the arguments listed in `appendix/README.md`, writing to a temporary copy) reproduces `appendix/output.txt` and `charts.json` byte for byte.
5. **Figures.** For every chart in `charts.json`: it is placed with `{{fig:id}}`, its title/labels are in the report language, and the validator raised no `near-identical` design warning for it.
6. **Privacy and hygiene.** `grep -c "/home/\|/Users/\|C:\\\\Users" {REPORT_DIR}/report.html` is 0; no `__pycache__`, `.pyc`, or 0-byte files in `appendix/`.
7. **Voice and language.** No first-person singular in `report.md` prose (`I `, ` my `, `yo `, `mi `, `hice`, `no pude`); for a Spanish report, no English template labels.
8. **Gate traces and fresh attempts.** `appendix/gates/source_verifier.md` exists and is non-empty (and `appendix/gates/reviewer.md` at Level 3); every `data_attempts.csv` failure behind a limitation or `Deferred` row has an `attempted_utc` from this run (the validator reports `inherited` otherwise).

## Output (exactly this shape)

**Start your answer with this header block** (generate the first three lines directly with `python3 -B {SKILL_DIR}/scripts/validate_report.py {REPORT_DIR}/report.md --gate-header qa`; the validator checks every line against the files):
```
MODE: subagent
REVIEWED-SHA256: <the line printed by --gate-header qa or: python3 -B {SKILL_DIR}/scripts/validate_report.py {REPORT_DIR}/report.md --gate-hash qa>
REVIEWED-UTC: <real UTC time printed by --gate-header qa, e.g. 2026-11-21T14:05:00Z>
QUOTE: <file relative to {REPORT_DIR}>:<line number>: "<text copied verbatim from that line>"
QUOTE: <a second line you actually read>
```
Run `--gate-header qa` (or `--gate-hash qa`) **before** you start reading; it fingerprints `report.md`, `charts.json` and every appendix file except `appendix/gates/`, so a later change to those files marks this answer as stale. Quote at least two lines you actually checked, copied exactly (any part of the line), with their line numbers; a quote that is not on that line fails validation.

Then, right after the header: `QA: PASS` or `QA: FAIL (<n> checks failed)`.
Then one line per check, for all eight: `<#> <PASS|FAIL> — <evidence: command output, file and line, or the offending text>`.
End your answer with the line `FAIL count: <n>` (the number of checks marked FAIL).
The validator checks this shape in `appendix/gates/qa.md`: the `QA:` line, the eight `<#> PASS|FAIL` lines, `FAIL count:`, and at least 400 characters.
This answer is saved to `appendix/gates/qa.md` and embedded in `report.html`, so write counts, not patterns: `home-directory paths in report.html: 0`, never the path strings themselves, and outside `QUOTE:` lines never write a literal `{{…}}` marker (write "figure marker" or "number placeholder").
