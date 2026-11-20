# Source-verification gate — manual record (maintainer, 2026-11-20)

This example predates the `appendix/gates/` convention (v0.6.0). No subagent output was saved at the time; this file records the provenance checks the maintainer ran by hand, against the seven checks of `references/agents/source-verifier.md`.

VERDICT: FAIL (3 problems)

1. 6 · C3 · `sources.csv` says "published in Quarterly Journal of Economics 141(3), 2026", but `data_attempts.csv` only logs the NBER page (abstract read) · log the retrieval of the journal page, or drop the publication detail from the title.
2. 2 · C4 · own computation registered as Tier 2; the report's own Tier 2 definition does not cover the report's own code · state in Section 3 that own computations are capped at Tier 2 by convention, or move C4 to Tier 3.
3. 5 · C1 · `data_as_of = 2026-10` is not documented in any file of the appendix · leave `data_as_of` empty or log where the date comes from.

Checks passed: 1 (C2 is titled "open-access full text" and `data_attempts.csv` logs the successful Europe PMC retrieval), 3 (no `[Strong]` tag; claims from the Tier 3 CSV stay at `[Preliminary]`), 4 (every id is cited, every citation exists), 7 (no reviewer-introduced fact entered the report).

PROPOSED data_attempts.csv ROWS: none.

These three items are among the open critiques of the second Reviewer #2 pass on this example (see the repository's review notes); they are documented here rather than silently fixed.
