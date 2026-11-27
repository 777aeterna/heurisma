MODE: self-review
REVIEWED-SHA256: 0dfe9561b22df8aa3669a001a2a1372990e59f4d25458628fb0e227d14cd6169
REVIEWED-UTC: 2026-11-23T18:47:40Z
QUOTE: report.md:6: "- **Calibrated Verdict:** A six-month"
QUOTE: appendix/output.txt:1: "Dataset integrity: sites=16, total_engineers=590"

QA: FAIL (1 checks failed)
1 PASS — `validate_report.py report.md --level 2 --html report.html --strict` (v0.10.1 validator, re-run by the maintainer on 2026-11-23 after Section 7 was extended to name the three accepted source-verifier problems): the only message is that this gate reviewed the earlier version of the report, which saving this file resolves; no other error or warning.
2 PASS — report.html was re-rendered before these checks; the validator reports no `stale` or `no source hash` line for it.
3 FAIL — the Calibrated Verdict quotes 7.20% and 4.80% (the quit rates reported by the external trial [@C2]); they appear in neither `appendix/output.txt` nor `appendix/numbers.json`. The other verdict figures are placeholders resolved from `appendix/numbers.json`. Accepted and justified in Section 7.
4 PASS — `validate_report.py report.md --level 2 --reproduce` re-ran `appendix/analysis.py` in a temporary copy and reported `appendix/output.txt`, `numbers.json` and `charts.json` reproduced (no reproduction message).
5 PASS — every chart in `charts.json` is placed with a figure marker, in the report language; the validator raised no `FIG-DESIGN` warning.
6 PASS — home-directory paths: 0 (from the validator in check 1); no `__pycache__`, `.pyc` or 0-byte files under `appendix/`.
7 PASS — no first-person singular in the prose (whole-word search); English report, English labels.
8 PASS — `appendix/gates/source_verifier.md` is present with its seven check lines and ends in an accepted `SOURCE-VERIFIER: FAIL` that Section 7 now names and justifies (Level 2: no Reviewer #2 gate); all five `data_attempts.csv` rows carry `attempted_utc` = 2026-11-20, the day the attempts were made.
FAIL count: 1

Manual record by the maintainer (self-review, no QA subagent dispatched): this example predates the gate convention. This pass replaces the 2026-11-21 record because Section 7 of the report changed.
