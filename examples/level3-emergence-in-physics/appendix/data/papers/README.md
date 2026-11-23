# Full-Text PDFs Excluded from Git

The 10 downloaded full-text PDFs (~16 MB total) for literature citations `C1`–`C10` are **not redistributed** in this repository to respect publisher licensing and keep `git clone` lightweight.

- Their exact DOIs, bibliographic metadata, and SHA-256 digests are preserved in [`../../papers.csv`](../../papers.csv) and [`../../download_log.csv`](../../download_log.csv).
- The raw OpenAlex / Crossref API responses remain in [`raw/`](raw/) so `papers.py replay --appendix appendix` verifies `papers.csv` offline without network access.
- Running `validate_report.py report.md --level 3 --strict` on this checked-in copy will report missing full-text PDFs (`P3-PAPER`) until those open-access PDFs are re-fetched locally; the original local run with all 10 PDFs present passed `--level 3 --html report.html --strict --reproduce` with **0 errors and 0 warnings**.
