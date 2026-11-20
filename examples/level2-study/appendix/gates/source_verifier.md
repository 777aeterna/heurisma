# Source-verification gate — manual record (maintainer, 2026-11-20)

This example predates the `appendix/gates/` convention (v0.6.0). No subagent output was saved at the time; this file records the provenance checks the maintainer ran by hand, against the seven checks of `references/agents/source-verifier.md`.

VERDICT: PASS

- 1 · no source claims "full text"; there is no `data_attempts.csv` because no rung failed.
- 2 · C2 (`appendix/analysis.py`) is `kind = own-computation`, Tier 2.
- 3 · the matrix uses C1 (user-supplied CSV, Tier 2, declared origin: internal team records) and C2; no claim rests on Tier 3 or press.
- 4 · both ids are cited and every `[@id]` exists in `sources.csv`.
- 5 · the report declares no data limitation and no `Deferred` row.
- 6 · `appendix/data/` is absent; C1 is an internal, user-supplied dataset referenced by an `internal://` identifier, not a local file.
- 7 · Level 2: no Reviewer #2 pass, so no reviewer-introduced facts.

PROPOSED data_attempts.csv ROWS: none.
