# Changelog

All notable changes to **Heurisma** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-20 (Paper-Grade Edition)

### Added
- **Publication-Grade SVG Engine (`scripts/svg_charts.py`, stdlib only):** Heckbert nice-number axis ticks, horizontal gridlines, clean calendar-year date axes, multi-series Okabe-Ito colorblind-safe palette + print-safe dash styles, automatic marker hiding (>30 points), vertical event `annotations`, shaded `bands`, `fan` projection charts (P10–P90 / P25–P75 / P50), grouped `bar` charts, safe `log` scale, and `<title>`/`<desc>` accessibility.
- **Working-Paper Reference Example (`references/example-report.md`):** Compact gold-standard paper example demonstrating abstract density, `{{fig:id}}` placement, and booktabs tables.
- **Reproducible Ingestion & Direct Chart Emission:** `appendix/fetch_data.py` with explicit `User-Agent` and SHA-256 logging, `appendix/analysis.py` emitting `charts.json` v2 directly, and `appendix/README.md`.

### Changed
- **Working-Paper HTML Renderer (`scripts/render_report.py`):** Replaced dashboard layout with Charter/Georgia serif typography, 720px single column, formal title/abstract block, booktabs tables with right-aligned numeric cells, sober small-caps epistemic tags, inline numbered `{{fig:id}}` figures, auto-generated References from `sources.csv`, `@media print` / `@page` A4 rules, and strict appendix filtering (never embeds `appendix/data/`, binaries, or >200 KB files).
- **Hardened Validator (`scripts/validate_report.py`):** Fixed single-dash Markdown separators (`:-`), accepted backticked Reviewer #2 actions (`` `Fixed` ``), raised substance floors (≥30 words in §1/§4, ≥2 matrix rows), added press/blog keyword & `sources.csv` Tier 3 detection against `[Strong]`, added Spanish localized tags (`[Fuerte]`, `[Moderada]`, `[Preliminar]`, `[Especulativa]`), and enforced `data_attempts` cross-checking for `Deferred` Level 3 critiques.
- **Single-Language Discipline & Abstract Verdict:** Strict ≤3-sentence / ≤5-number verdict limit and 100% Spanish template (zero Spanglish).

## [0.2.0] - Local Preview

### Added
- Stage 6 deliverables, zero-dependency `render_report.py`, `references/forecasting.md`, Level 0 Light Mode, `sources.csv` + Data-Attempts registry, closed Reviewer #2 Disposition Table, MAD + Bootstrap 95% CI helpers, and bilingual EN/ES validator support.

## [0.1.0] - 2026-11-20

### Added
- Core scientific-method agent skill (`skills/heurisma/SKILL.md`), 4 modular reference guides, zero-dependency `validate_report.py`, RED–GREEN–REFACTOR evals, showcase examples, logo, and GitHub Actions CI.
