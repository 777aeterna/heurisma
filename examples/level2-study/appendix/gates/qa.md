QA: PASS
1 PASS — `validate_report.py report.md --level 2 --html report.html --strict`: PASSED, no warnings (run by the maintainer on 2026-11-20 after these gate files were added and the HTML re-rendered).
2 PASS — the validator reports no `stale` or `no source hash` line.
3 PASS — the Calibrated Verdict numbers are placeholders resolved from `appendix/numbers.json`.
4 PASS — `python3 -B appendix/analysis.py` with the arguments in `appendix/README.md` reproduces `appendix/output.txt`, `charts.json` and `appendix/numbers.json` byte for byte.
5 PASS — every chart in `charts.json` is placed with a figure marker, in the report language, with no near-identical-bars warning.
6 PASS — home-directory paths in report.html: 0; no `__pycache__`, `.pyc` or 0-byte files in `appendix/`.
7 PASS — no first-person singular in the prose; English report, English labels.
8 PASS — `appendix/gates/source_verifier.md` is present (Level 2: no Reviewer #2 gate); `data_attempts.csv` has no `attempted_utc` column (written before v0.6.0), so the inherited-attempt check does not apply.

Manual record by the maintainer: this example predates the gate convention and no QA subagent was dispatched for it.
