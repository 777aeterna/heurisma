# Heurisma Architecture & Design Specification

## Vision

**Heurisma** (from Greek *heuriskein*, "to discover") is a cross-runtime agent skill that elevates AI research beyond conventional *Deep Research*. Instead of acting as a search-and-summarize engine, Heurisma enforces a disciplined **scientific method workflow**:

1. **Cognitive Triage (Pre-Search Gate):** Classify the inquiry across scientific branches and select an adaptive depth level before launching searches or making claims.
2. **Falsifiable Framing:** Formulate an investigable question, null/alternative hypotheses, and explicit confirmation/refutation criteria.
3. **Evidence-Weighted Collection:** Prioritize primary sources and peer-reviewed literature according to the discipline's evidence hierarchy.
4. **Reproducible Data Protocol (On-Demand):** Audit datasets and run verifiable Python scripts for statistical and quantitative claims.
5. **Adversarial Falsification:** Actively seek counter-evidence; at Level 3, dispatch an independent *Reviewer #2* subagent.
6. **Calibrated Scientific Writing:** Deliver high-signal prose with explicit epistemic confidence labels (`[Strong]`, `[Moderate]`, `[Preliminary]`, `[Speculative]`), a Claim-Evidence Matrix, and transparent limitations.

## Modular Architecture

```text
skills/heurisma/
├── SKILL.md                       # Concise core: gates, 6-stage protocol, depth levels
├── references/
│   ├── disciplines.md             # 6+ scientific branches + interdisciplinary bridge
│   ├── data-protocol.md           # Reproducible Python data audit & statistical rigor
│   ├── adversarial-review.md      # Self-falsification + Reviewer #2 dispatch template
│   └── scientific-writing.md      # Epistemic calibration, Claim-Evidence Matrix, formats
└── scripts/
    └── validate_report.py         # Zero-dependency Python structural & calibration validator
```

## Adaptive Depth Levels

| Level | Trigger | Loaded Modules | Subagents |
|---|---|---|---|
| **Level 1 — Rigorous Inquiry** | Bounded conceptual/literature inquiry without raw datasets | `SKILL.md`, `disciplines.md`, `scientific-writing.md` | None (structured self-falsification) |
| **Level 2 — Empirical / Data Study** | User supplies data, public datasets exist, or quantitative claims require computation | Level 1 + `data-protocol.md` | Optional |
| **Level 3 — Deep Multi-Disciplinary** | Complex, high-stakes, or contested cross-domain topics | All + `adversarial-review.md` | Specialist branches + independent *Reviewer #2* |

## GitHub Metadata Reference

- **Repository:** `https://github.com/777aeterna/heurisma`
- **About:** `Scientific-method agent skill that goes beyond Deep Research: discipline-aware inquiry, falsifiable hypotheses, reproducible data analysis, adversarial peer review, and calibrated scientific writing. Vibecoded with AI + TDD for skills.`
- **Topics:** `agent-skills`, `scientific-method`, `deep-research`, `data-analysis`, `epistemology`, `peer-review`, `ai-agents`, `claude-code`, `antigravity`, `gemini-cli`, `vibecoding`
