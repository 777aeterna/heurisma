# Source-verification gate — manual record (maintainer, 2026-11-20)

This example predates the `appendix/gates/` convention. No subagent output was saved for it; this file records the provenance checks the maintainer ran by hand, in the shape fixed by `references/agents/source-verifier.md` (v0.6.1).

1. PASS — read vs. registered: no source claims "full text"; there is no `data_attempts.csv` because no rung failed.
2. PASS — own computation: C2 (`appendix/analysis.py`) is `kind = own-computation`, Tier 2.
3. PASS — tag vs. weakest source: the matrix rests on C1 (user-supplied CSV, Tier 2, declared origin: internal team records) and C2; no claim rests on Tier 3 or press.
4. PASS — both ids are cited and every `[@id]` exists in `sources.csv`.
5. PASS — the report declares no data limitation and no `Deferred` row.
6. PASS — `appendix/data/` is absent; C1 is an internal, user-supplied dataset referenced by an `internal://` identifier, not a local file.
7. PASS — Level 2: no Reviewer #2 pass, so no reviewer-introduced facts.

Problems: none
PROPOSED data_attempts.csv ROWS: none
SOURCE-VERIFIER: PASS
