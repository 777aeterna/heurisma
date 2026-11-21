MODE: self-review
REVIEWED-SHA256: 5be34406d96ad6ddd235bc91dcd3d1a4ceaad3481b4a2cd512cb3a7a9680110a
REVIEWED-UTC: 2026-11-21T12:27:08Z
QUOTE: appendix/sources.csv:2: "C1,"Multi-site engineering CSV"
QUOTE: appendix/sources.csv:3: "Bloom, N., Han, R., & Liang, J. (2024)"
QUOTE: appendix/data_attempts.csv:2: "Site allocation protocol, baseline window"

# Source-verification gate — manual record (maintainer, 2026-11-20)

This example predates the `appendix/gates/` convention. No subagent output was saved for it; this file records the provenance checks the maintainer ran by hand, in the shape fixed by `references/agents/source-verifier.md` (v0.6.1).

1. FAIL — read vs. registered: C3's title says "published in Quarterly Journal of Economics 141(3), 2026", but `data_attempts.csv` only logs the NBER page (abstract read); C1's `data_as_of = 2026-10` is not documented in any appendix file.
2. FAIL — own computation: C4 (`appendix/analysis.py`) is `own-computation` at Tier 2, but the report's own Tier 2 definition does not cover the report's own code.
3. PASS — tag vs. weakest source: no `[Strong]` tag; every claim resting on the Tier 3 CSV (C1) stays at `[Preliminary]`.
4. PASS — every `[@id]` exists in `sources.csv` and every source row is cited.
5. PASS — the limitations in Section 7 rest on `data_attempts.csv` rows for the online and local searches, dated 2026-11-20.
6. PASS — the one local file (`appendix/data/hybrid_rct_sites.csv`) is registered as C1 with a project-relative path and its SHA-256.
7. PASS — no reviewer-introduced fact entered the report.

Problems:
1. 1 · C3 · only the NBER page was read · log the retrieval of the journal page, or drop the publication detail from the title.
2. 1 · C1 · `data_as_of` has no documented origin · leave it empty or log where the date comes from.
3. 2 · C4 · own computation registered at Tier 2 without a definition covering it · state in Section 3 that own computations are capped at Tier 2 by convention, or move C4 to Tier 3.
PROPOSED data_attempts.csv ROWS: none

These three problems are among the open critiques of the second Reviewer #2 pass on this example; they are recorded here rather than silently fixed.

SOURCE-VERIFIER: FAIL (3 problems)
