# Appendix — Exoplanet Keplerian Scaling & Mass–Radius Regimes

## Reproducible Execution (from `study/`)
```bash
python3 -B appendix/fetch_data.py
python3 -B appendix/analysis.py > appendix/output.txt
```

## Data Provenance & Helper Modules
- `appendix/data/exoplanets_nasa_ps.csv`: downloaded in this run by `appendix/fetch_data.py` from the NASA Exoplanet Archive TAP API (`ps` table, `default_flag=1`, `tran_flag=1`).
- `appendix/data/exoplanets_nasa_ps_ext.csv`: extended uncertainty and transit `a/R_*` (`pl_ratdor`, `st_rad`) columns downloaded in this run by `appendix/fetch_data.py` from the NASA Exoplanet Archive TAP API.
- `appendix/data/exoplanets_si.csv`: derived locally from `exoplanets_nasa_ps.csv` by SI unit conversion (`P_s = pl_orbper * 86400`, `a_m = pl_orbsmax * 1.495978707e11`, `GM = st_mass * 1.3271244e20`, `M_p = pl_bmasse * 5.972168e24`, `R_p = pl_rade * 6.3781e6`).
- `appendix/data/papers/`: open-access literature PDFs/XMLs and raw provider API responses fetched by `papers.py`.
- `appendix/contracts.py`, `appendix/local_data.py`, `appendix/fetch_lib.py`: portable zero-dependency helper modules copied from the Heurisma v0.11.1 skill `scripts/` directory so `fetch_data.py` and `analysis.py` run without hardcoded absolute paths.
- `appendix/conjectures.json`, `appendix/conjectures_invariant.json`: sealed one-off `conjecture.py discover` outputs (read-only during `analysis.py`).
- `appendix/formal/kepler-scaling/`: Lean 4 formalization (`Challenge.lean`, `Solution.lean`, `verify.json`) checked via `formal_math.py check`.
