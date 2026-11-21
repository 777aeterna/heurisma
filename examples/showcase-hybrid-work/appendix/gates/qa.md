MODE: self-review
REVIEWED-SHA256: dfecc0f1214a03f84746c30a1fc490fdf520faf6bee639253f6e1d350ded0402
REVIEWED-UTC: 2026-11-21T12:27:08Z
QUOTE: report.md:6: "- **Calibrated Verdict:** A six-month"
QUOTE: appendix/output.txt:1: "Dataset integrity: sites=16, total_engineers=590"

QA: FAIL (1 checks failed)
1 PASS — `validate_report.py report.md --level 2 --html report.html --strict`: PASSED, no warnings (run by the maintainer on 2026-11-20 with the v0.6.1 validator, after these gate files were rewritten in the v0.6.1 shape and the HTML re-rendered; the validator accepts the check-3 FAIL because Section 7 cites this file).
2 PASS — the validator reports no `stale` or `no source hash` line.
3 FAIL — the Calibrated Verdict quotes 7.20% and 4.80% (the quit rates reported by the external trial [@C2]); they appear in neither `appendix/output.txt` nor `appendix/numbers.json`. The other verdict figures are placeholders resolved from `appendix/numbers.json`. Accepted: the two figures are cited external results, not outputs of this analysis (justified in Section 7 of the report).
4 PASS — `python3 -B appendix/analysis.py` with the arguments in `appendix/README.md` reproduces `appendix/output.txt`, `charts.json` and `appendix/numbers.json` byte for byte.
5 PASS — every chart in `charts.json` is placed with a figure marker, in the report language, with no near-identical-bars warning.
6 PASS — home-directory paths in report.html: 0; no `__pycache__`, `.pyc` or 0-byte files in `appendix/`.
7 PASS — no first-person singular in the prose; English report, English labels.
8 PASS — `appendix/gates/source_verifier.md` is present with its seven check lines (Level 2: no Reviewer #2 gate); every `data_attempts.csv` row carries `attempted_utc` = 2026-11-20, the day the attempts were made (date only: the exact times were not recorded). `appendix/run.json` sets the run start to the start of that day (reconstructed, as the file says).
FAIL count: 1

Manual record by the maintainer: this example predates the gate convention and no QA subagent was dispatched for it.
