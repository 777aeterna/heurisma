# Appendix — Emergence in Physics (Heurisma Level 3)

## Reproducibility Commands (run from report root)

1. Acquire literature metadata and open-access full texts (requires network; respects `HEURISMA_OFFLINE=1`):
   ```bash
   python3 -B appendix/fetch_data.py
   ```
2. Run the 2D Ising exact enumeration and Wolff single-cluster Monte Carlo simulation (zero external dependencies, deterministic seed `42`):
   ```bash
   python3 -B appendix/analysis.py > appendix/output.txt
   ```
   This regenerates `appendix/output.txt`, `appendix/numbers.json`, and `charts.json` byte for byte.

## Provenance of `appendix/data/`

- All files under `appendix/data/papers/` (raw OpenAlex/arXiv/Crossref API responses and 10 peer-reviewed full-text PDFs) were downloaded in this run via `papers.py` (invoked from `appendix/fetch_data.py` and `papers.py cite --fulltext`) and are hashed in `appendix/download_log.csv`.
- No local user-curated datasets were present in `datos/` or `data/` (logged in `appendix/data_attempts.csv`).
