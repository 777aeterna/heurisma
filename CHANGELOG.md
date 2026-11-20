# Changelog

All notable changes to **Heurisma** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-11-20 (Local Data, Linked Citations & Full i18n)

### Added
- **Zero-Dependency Local Data Engine (`scripts/local_data.py`):** `inventory`, `preview`, `read_table`, `read_csv` (`;` delimiter, European decimal-comma `1.234,5`, `latin-1` fallback), `read_xlsx` (no `openpyxl`: shared strings, `inlineStr`, booleans, header auto-detection, footer-note pruning, `excel_date`), `read_json`, and `register_local` (`file://` URI + SHA-256 into `sources.csv`).
- **4-Tier Data Fallback Cascade & Local Protocol (`SKILL.md`, `references/data-protocol.md`):** Stage 0 local inventory, Stage 2 cascade (online primary → online alternatives → local data → limitation), extended Iron Law 3 (requiring online + local attempts, including tag-downgrade closures in `references/adversarial-review.md`), and optional `appendix/numbers.json` (`{{num:key}}`).
- **Linked In-Text Citations (`[@C1]`, `[@C1; @C4]`):** Appearance-ordered `<a href="#ref-n">[n]</a>` links and matching `<li id="ref-n">` References list in `render_report.py`.

### Changed
- **Publication SVG Polish (`scripts/svg_charts.py`):** Staggered non-overlapping annotations (up to 3 rows, right-edge flip, 16-char truncation), white-halo reference labels, scatter `nice_ticks` X-axis + `y=0` line + `highlight` point, `percent`/`thousands`/`currency` locale formatting (`en`/`es`), tighter Y-axis bounds, compact bottom margins, and localized 3-layer fan legend (`Mediana (P50)`, `P25–P75`, `P10–P90`) without median markers.
- **Full `en`/`es` Working-Paper Renderer (`scripts/render_report.py`):** Auto-detected `<html lang>`, zero leaked English chrome in Spanish reports, currency-safe inline LaTeX-to-HTML/Unicode conversion, nested `<ul>` lists, deduplicated Abstract vs. §1 Verdict, footer credit with `--no-credit`, `--lang`, and `--numbers` CLI flags.
- **Hardened Validator (`scripts/validate_report.py`):** Added V1 (`{{fig:id}}` ↔ `charts.json`), V2 (`[@id]` citations ↔ `sources.csv`), V3 (Spanish HTML language purity), V4 (unconverted LaTeX warning), V5 (`file://` SHA-256 check, orphan `appendix/data/` warning, canonical `data_attempts.csv` columns), V6 (`__pycache__`/`.pyc`/0-byte hygiene warnings), P11 verdict-number cross-check, and `--strict` flag.
- **Skill Hygiene:** Standardized `python3 -B` across `SKILL.md`, references, CI, and tests; removed hardcoded version from `data-protocol.md` `User-Agent` and fixed paired bootstrap resampling.

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
