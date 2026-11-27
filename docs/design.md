# Heurisma Architecture & Design Specification

## Vision

**Heurisma** (from Greek *heuriskein*, "to discover") is a cross-runtime agent skill and epistemic linter that replaces search-and-summarize *Deep Research* with a verifiable **scientific method workflow**:

- **Stage 0 — Cognitive Triage, Local Data Inventory, Run Stamp & Pre-Intake (Pre-Search Gate):** Classify the inquiry across scientific branches, choose an adaptive depth level (Levels 0–3), inventory local files, detect inherited runs, stamp `appendix/run.json`, and offer one non-blocking pre-flight data intake (`datos/` and `inbox/sources/` — Stage 0 step 9).
- **Stage 1 — Falsifiable Framing & Preregistration:** Formulate an investigable question, null/alternative hypotheses (`H₀`/`H₁`), explicit confirmation/refutation criteria, and (at Level 2+) seal `appendix/preregistration.json`.
- **Stage 2 — Evidence-Weighted Collection (4-Rung Cascade):** Acquire primary data online first, then alternatives, then user-supplied local files (`local_data.py import`/`intake`), and only then a documented limitation — with mandatory counter-evidence search outside any user-curated corpus.
- **Stage 3 — Reproducible Data Protocol:** Inspect schemas, reject ambiguous decimal columns, run deterministic Python scripts in `appendix/` emitting `output.txt`, `numbers.json`, and `charts.json` directly.
- **Stage 4 — Adversarial Falsification & Gate Verification:** Actively seek counter-evidence; run the **Source-Verifier** gate (Level 2+) and independent **Reviewer #2** gate (Level 3), each bound to the reviewed artifacts via `REVIEWED-SHA256`, `REVIEWED-UTC`, literal `QUOTE:` lines, and `MODE: subagent | self-review`.
- **Stage 5 — Calibrated Scientific Writing:** Deliver clean narrative `report.md` with linked citations (`[@C1]`), `{{num:key}}` and `{{fig:id}}` placeholders, explicit confidence tags (`[Strong]`, `[Moderate]`, `[Preliminary]`, `[Speculative]`), a Claim-Evidence Matrix, and transparent limitations.
- **Stage 6 — Deliverables, Rendering & QA Gate:** Render a standalone offline working-paper `report.html` (inline CSS + SVG, zero JS), run `validate_report.py --strict --reproduce`, and record the **QA** gate trace in `appendix/gates/qa.md`.

## Modular Architecture

All runtime scripts in `skills/heurisma/scripts/` target **Python ≥ 3.9** using only the standard library (zero external dependencies).

```text
skills/heurisma/
├── SKILL.md                           # Core protocol: Iron Laws, depth levels, 7 stages (+ Stage 0 step 9 pre-intake)
├── references/
│   ├── disciplines.md                 # Scientific branches, evidence tiers & interdisciplinary bridge
│   ├── data-protocol.md               # 4-rung acquisition cascade, local data, fetch_lib & statistical cautions
│   ├── forecasting.md                 # Horizons, base rates, fan charts & scenario discipline
│   ├── formal-and-discovery.md        # Opt-in Lean 4 / Lake formal verification & Buckingham Pi symbolic conjecture discovery
│   ├── adversarial-review.md          # Self-falsification, Reviewer #2 disposition & degradation rules
│   ├── scientific-writing.md          # Epistemic calibration, Claim-Evidence Matrix, charts.json & i18n
│   ├── example-report.md              # Annotated reference report template
│   ├── validator-codes.md             # Stable machine-readable diagnostic codes for validate_report.py --json
│   └── agents/
│       ├── source-verifier.md         # Portable Source-Verifier gate prompt
│       ├── reviewer.md                # Portable Reviewer #2 gate prompt
│       └── qa.md                      # Portable QA gate prompt
└── scripts/
    ├── checks/                        # Rule families of validate_report.py, which re-exports them as its public API
    │   ├── __init__.py                # Package marker
    │   ├── common.py                  # Shared constants & parsers (tables, sections, dates, hashes, citations)
    │   ├── structure.py               # Calibration-tag spelling diagnostics
    │   ├── gates.py                   # Gate hash, header, quotes & reviewer analysis anchor
    │   ├── numeric.py                 # Numeric closure (Section 4 tables, chart text) & verdict size
    │   ├── provenance.py              # Tiers, selection, source catalogue, local data & inbox/
    │   ├── prereg.py                  # Preregistration sealing, post-seal files & HARKing
    │   ├── papers.py                  # Paper-connector rules (opt-in): DOI anywhere in a URL, preprint tier, retracted, title, confined & hashed full text, replay, credentials
    │   ├── conjecture.py              # Symbolic conjecture rules (opt-in): conjectures.json hash, holdout split & [Strong] cap
    │   ├── formal.py                  # Lean 4 formal-proof rules (opt-in): formal_proofs.csv, hashes, hazards, statement pairing & P-10 warning
    │   ├── html.py                    # report.html sections, language, markers, privacy & freshness
    │   └── codes.py                   # Stable --json codes (CODE_RULES, classify_message)
    ├── providers/                     # Paper-database sources used by papers.py, one module per provider
    │   ├── __init__.py                # Package marker
    │   ├── base.py                    # DOI normalisation, credential redaction, request context (cached, hashed, rate-limited)
    │   ├── openalex.py                # OpenAlex: search and DOI lookup (type, retraction, open access)
    │   ├── crossref.py                # Crossref: DOI lookup to verify a reference exists
    │   ├── europepmc.py               # Europe PMC: search for biomedicine and open-access work
    │   ├── arxiv.py                   # arXiv: preprint search
    │   └── unpaywall.py               # Unpaywall: open-access copy of a DOI (needs a contact address)
    ├── papers.py                      # Paper connector CLI: search, lookup, cite, verify, import, replay (papers.csv, search_log.csv; lock file; replay trusts only logged hashes)
    ├── conjecture.py                  # Exact Buckingham Pi dimensional analysis & symbolic conjecture engine
    ├── formal_math.py                 # Lean 4 / Lake formal-verification adapter (anthropics/formal-math layout)
    ├── contracts.py                   # Single source of truth for version, tags, schemas, gates & section patterns
    ├── local_data.py                  # Inventory, preview, per-column CSV/XLSX/JSON reader, register, import, intake, prereg, run-start
    ├── fetch_lib.py                   # Retry/backoff HTTP fetcher with checksums, size caps, download_log, offline guard, URL redaction & private-host/redirect guard
    ├── svg_charts.py                  # Zero-dependency SVG chart engine & charts.json schema validator
    ├── render_report.py               # Working-paper HTML/SVG renderer with URL allowlist, {{num:}} & freshness hash
    └── validate_report.py             # Epistemic & structural linter: orchestrator + CLI (--strict, --json, --reproduce, --diff, --gate-hash)
```

Claude Code subagent mirrors (kept byte-synced with `skills/heurisma/references/agents/` by `tests/test_agents_sync.py`):

```text
agents/
├── heurisma-source-verifier.md        # Claude Code subagent mirror of references/agents/source-verifier.md
├── heurisma-reviewer.md               # Claude Code subagent mirror of references/agents/reviewer.md
└── heurisma-qa.md                     # Claude Code subagent mirror of references/agents/qa.md
```

## Study Artifact Layout (Level 2–3)

```text
<study-dir>/
├── report.md                          # Clean narrative with [@id] citations, {{num:key}} & {{fig:id}}
├── report.html                        # Standalone offline working-paper HTML + inline SVG + freshness hash
├── charts.json                        # Chart specs emitted by analysis.py (required when {{fig:}} is used)
└── appendix/
    ├── run.json                       # Tool-stamped run_started_utc (local_data.py run-start)
    ├── preregistration.json           # Sealed H0/H1 & analysis plan (local_data.py prereg)
    ├── conjectures.json               # Opt-in sealed symbolic law candidates & holdout metrics (conjecture.py)
    ├── conjectures_invariant.json     # Optional sealed conservation/ratio invariant candidates (--target __invariant__)
    ├── formal_proofs.csv              # Opt-in Lean 4 kernel-verification registry (formal_math.py)
    ├── intake.md                      # Pre-intake audit of user files, column formats & wishlist gaps
    ├── fetch_data.py                  # Reproducible online acquisition script (imports fetch_lib)
    ├── analysis.py                    # Deterministic computation script
    ├── output.txt                     # Verbatim analysis output
    ├── numbers.json                   # Machine-readable metrics referenced via {{num:key}}
    ├── sources.csv                    # Provenance register (tier, kind, sha256, selection, retrieved_utc)
    ├── data_attempts.csv              # Chronological acquisition log with attempted_utc
    ├── download_log.csv               # Checksummed downloads from fetch_lib
    ├── data/                          # Imported local data copies
    ├── formal/                        # Opt-in Lake/Lean 4 proof workspaces (<slug>/Challenge.lean, Solution.lean)
    ├── corpus/                        # Imported user-curated source documents
    ├── gates/
    │   ├── source_verifier.md         # Source-Verifier gate trace (Level 2+)
    │   ├── reviewer.md                # Reviewer #2 gate trace (Level 3)
    │   └── qa.md                      # QA gate trace (Level 2+)
    └── README.md                      # Exact reproduction command and provenance notes
```

## Adaptive Depth Levels

| Level | Trigger | Loaded Modules | Required Gates |
| :--- | :--- | :--- | :--- |
| **Level 0 — Light Mode** | Short single-claim check where a 7-section paper is disproportionate | `SKILL.md` only | None (compact 3-part inline response) |
| **Level 1 — Rigorous Inquiry** | Conceptual, literature, or policy inquiry without raw dataset computation | `SKILL.md`, `disciplines.md`, `scientific-writing.md`, `example-report.md` | Self-falsification in §5 |
| **Level 2 — Empirical / Data Study** | User supplies data, local files exist, or quantitative claims require computation | Level 1 + `data-protocol.md` (+ `forecasting.md` if projecting) | `source_verifier.md`, `qa.md` |
| **Level 3 — Deep Multi-Disciplinary** | Crosses 3+ branches, contested evidence, forecasting, or high stakes | All modules + `adversarial-review.md` | `source_verifier.md`, `reviewer.md`, `qa.md` |

## GitHub Metadata Reference

- **Repository:** `https://github.com/777aeterna/heurisma`
- **Topics:** `agent-skills`, `scientific-method`, `deep-research`, `data-analysis`, `epistemology`, `peer-review`, `reproducible-research`, `subagents`, `ai-agents`, `claude-code`, `antigravity`, `gemini-cli`, `vibecoding`
