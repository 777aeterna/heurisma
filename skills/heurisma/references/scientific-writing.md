# Calibrated Scientific Writing, Citations, Single-Language Templates & `charts.json` v2 Guide

Part of **Heurisma** (loaded during **Stage 5 & Stage 6** before finalizing `report.md` and rendering the working-paper `report.html`).

---

## 1. Epistemic Calibration Scale (English & Spanish)

Every major claim in Section 1, Section 4, and **every row** of Section 6 (`Claim-Evidence Matrix` / `Matriz de afirmaciones y evidencia`) MUST carry a bracketed calibration tag matching the report's language:

| English Tag | Spanish Tag | Meaning | Minimum Evidence Required | Strictly Forbidden For |
| :--- | :--- | :--- | :--- | :--- |
| **`[Strong]`** | **`[Fuerte]`** | High epistemic confidence; robust against confounders | Formal deductive proof; meta-analysis of human RCTs; replicated Tier 1 measurements; conservation laws | **Any Tier 3, press/blog/roadmap, or unknown-origin local source** (`validate_report.py` rejects press/Tier 3), single studies, or unconditional future forecasts |
| **`[Moderate]`** | **`[Moderada]`** | Credible empirical support within bounded conditions | Well-designed single RCT, quasi-experimental causal study (DiD/IV/RDD), audited primary institutional series (Tier 1/2) | Press releases, small unadjusted samples (n < 30), uncalibrated extrapolations |
| **`[Preliminary]`** | **`[Preliminar]`** | Suggestive or context-limited evidence requiring replication | Small-sample empirical data, single observational cohort, high-frequency proxy bridging a lagging series | Definitive policy mandates or unverified claims introduced by a reviewer |
| **`[Speculative]`** | **`[Especulativa]`** | Unverified projection, mechanism hypothesis, or scenario | Corporate roadmap dates, animal/prototype mechanism extrapolated to scale, multi-month point/regime forecast | Presenting as established fact or probable baseline without flagging failure risk |

---

## 2. Working-Paper Prose, Citation & Abstract Rules

1. **Abstract-Style Verdict (Max 3 Sentences, Max 5 Numbers):**
   - `Calibrated Verdict` / `Veredicto calibrado` in Section 1 acts as the paper's **Abstract**: state the direct answer, its calibration tag, and the core mechanism in **at most 3 sentences and at most 5 numbers**.
   - `render_report.py` promotes the verdict into the HTML Abstract box and does not repeat it as the first bullet of §1. To write a separate abstract instead, add `> **Abstract:** …` / `> **Resumen:** …` directly under the title block.
   - Never pack 15 numbers into a dense wall of text in Section 1; put detailed metrics in Section 4 booktabs tables and `{{fig:id}}` figures.
   - Do not over-quantify illustrative scenario probabilities (if scenario weights are illustrative rather than structurally estimated, present scenario levels cleanly without fake 4-decimal precision on combined percentiles).
2. **Linked In-Text Citations (`[@claim_id]`):**
   - Cite with `[@C1]`, or several at once with `[@C1; @C4]`. Each id must be a `claim_id` in `appendix/sources.csv`.
   - Place the citation right after the claim it supports, before the calibration tag: `Real appreciation reached 38% [@C2] `[Moderate]`.`
   - The renderer numbers citations by **first appearance** (`[1]`, `[2]`, …), links each to `#ref-n`, and orders the References list the same way; uncited sources are appended after the cited ones.
   - **Validator (Level 2+):** fails if Section 4 has no citations or if a `[@id]` is missing from `sources.csv`; warns for every `sources.csv` row that is never cited (**fails** at Level 3). Cite every row or remove the ones you did not use.
3. **Math Without LaTeX:**
   - Write symbols in Unicode: `H₀`, `H₁`, `ρ`, `Δ`, `≤`, `≥`, `±`, `×`, `≈`, `σ`, `μ`, `x²`. The working paper has no LaTeX engine.
   - The renderer converts residual inline math (`$H_0$` → H<sub>0</sub>, `$x^2$` → x<sup>2</sup>, `$\Delta$` → Δ) as a safety net and never touches currency (`$1.563`, `$1,200–$1,400`), but the validator warns on any LaTeX left in the HTML.
4. **Key Numbers from `appendix/numbers.json` & Numeric Closure (Level 2+):**
   - Every figure in the Calibrated Verdict, Section 1 and the Section 4 tables that comes from `appendix/output.txt` is written as `{{num:key}}`, never retyped: a retyped number silently goes stale when the analysis changes. Every statistical number in a Section 4 table cell must appear in `appendix/output.txt` or `appendix/numbers.json` (`P1-UNTRACED-NUM` warns at Level 2 and errors at Level 3 on hand-typed statistics absent from both). The validator also warns when five or more Section 4 figures from `output.txt` are typed by hand and placeholders cover less than 30 % of them.
   - Write `{{num:key}}` instead of retyping a computed value; the renderer substitutes it from `appendix/numbers.json` and prints negative values with a typographic minus (`−16,6 %`). An unknown key is a validator **error**, and any `{{…}}` left in the HTML is an error. Without placeholders, the validator warns when a verdict number is absent from `appendix/output.txt`.
5. **Inline Figure Placement (`{{fig:chart_id}}`):**
   - Place `{{fig:chart_id}}` on its own line in Section 4 or Section 5 immediately after the paragraph that discusses that figure.
   - `render_report.py` replaces it with a numbered `<figure>` (`Figure 1.` / `Figura 1.`, publication SVG, `Note:` / `Nota:`, `Source:` / `Fuente:`, and a collapsible data table).
   - **Validator (Level 2+):** looks for `charts.json` next to `report.md` (then in `appendix/`, or `--charts <path>`); fails if it is missing, if `report.md` has no `{{fig:…}}` marker, or if a marker uses an id absent from `charts.json`; warns for charts never placed (they fall into "Additional Figures").
6. **Nested Lists & Sub-Headings:** Indent sub-bullets by 2 or 4 spaces under their parent bullet (e.g., `Key Takeaways`, `Hypotheses`); the renderer emits a nested list. Sub-sections may go down to `####` / `#####` (e.g. `#### 4.1.1 By regime`). Exponents and scientific notation render as superscripts when written as `N^(−1/2)`, `x^2` or `3e-08`.
7. **Zero Code / Zero Bloat in `report.md`:**
   - Never embed scripts or raw console outputs inside `report.md`. Keep it focused on scientific argument, tables, citations, and `{{fig:id}}` figures.
8. **Commands:** run every script with `python3 -B` in instructions, `appendix/README.md`, and examples.
9. **Voice:** write in the impersonal or first-person plural voice — *"the analysis shows"*, *"only the abstract could be retrieved"*, *"we re-ran the integration with half the step"*; in Spanish, *"el análisis muestra"*, *"solo pudo recuperarse el resumen"*, *"repetimos la integración con la mitad del paso"*. This applies to every section, including Limitations.
10. **Nothing copied from outside:** never paste Markdown links, images or HTML from a web page, an API response or a user document into `report.md`; quote it as plain text and link only URLs registered in `sources.csv`. An image is embedded only from a relative path (your own figures go through `{{fig:id}}`); `![…](https://…)` renders as a plain link, so opening the HTML never contacts another server.
11. **Re-render after every edit:** the HTML carries a hash of `report.md`, `charts.json` and `appendix/`; the validator reports a stale HTML when any of them changed after rendering.

---

## 3. Strict Single-Language Consistency (100% Spanish Template)

When the user requests a report in Spanish, **do not mix English labels or English table headers into the text**. The renderer auto-detects Spanish from the headings below and localizes all HTML chrome (`<html lang="es">`, `Figura`, `Nota:`, `Fuente:`, `Resumen`, `Referencias`, `Mediana (P50)`); the validator fails a Spanish HTML that leaks English chrome. Write chart titles, captions, series names, and annotation labels in Spanish too.

```markdown
# [Título descriptivo del documento de trabajo]

> **Fecha de corte (As-Of):** YYYY-MM-DD | **Nivel de profundidad:** Nivel <1|2|3> | **Disciplinas:** [Ramas]

## 1. Resumen ejecutivo
- **Veredicto calibrado:** [Máximo 3 oraciones y máximo 5 cifras respondiendo la pregunta con etiquetas `[Fuerte]` / `[Moderada]` / `[Preliminar]` / `[Especulativa]`.]
- **Qué cambiaría esta conclusión:** [Umbral empírico u observación concreta que revertiría el veredicto.]
- **Conclusiones clave:**
  - [2 a 4 sub-viñetas concisas separando lo que se sostiene bajo escrutinio de lo incierto.]

## 2. Encuadre e hipótesis
- **Disciplinas científicas y nivel:** [Ramas + acoplamiento interdisciplinario]
- **Pregunta de investigación:** [Pregunta neutral y operacionalizada con unidades y horizonte]
- **Hipótesis:**
  - H₀: [Hipótesis nula / línea base / artefacto]
  - H₁: [Hipótesis alternativa]
- **Criterios de refutación:** [Condiciones empíricas o lógicas exactas que refutan H₁ y H₀]

## 3. Metodología y estándares de evidencia
- **Jerarquía de evidencia del dominio:** [Estándares Tier 1 vs. Tier 2 vs. Tier 3]
- **Procedencia analítica y de datos:** [Resumen del método, enlaces a `appendix/fetch_data.py`, `appendix/analysis.py`, `appendix/output.txt` y `appendix/sources.csv`, más la tabla de **Intentos de datos** (escalones en línea y locales) si falló alguna fuente primaria o se usó un archivo local]

## 4. Hallazgos
[Análisis estructurado por hipótesis o eje/régimen, con tablas sobrias, citas `[@C1]` tras cada afirmación respaldada y marcadores `{{fig:id_grafico}}` en el lugar exacto donde se analiza cada figura.]

## 5. Contraevidencia y explicaciones alternativas
[Mejor evidencia en contra, límites de régimen, confusores y —en Nivel 3— la tabla **Disposición del Revisor #2** con encabezados en español (`| Falla # | Crítica del revisor | Acción | Evidencia / Artefacto |`).]

## 6. Matriz de afirmaciones y evidencia
| Afirmación | Disciplina / Eje | Evidencia y Tier (Fecha de datos) | Confianza | Falsador clave / Condición |
| :- | :- | :- | :- | :- |
| [Afirmación 1] | [Rama] | [Fuente primaria [@C1], Tier 1/2/3, YYYY-MM] | `[Fuerte]` / `[Moderada]` / `[Preliminar]` / `[Especulativa]` | [Falsador] |
| [Afirmación 2] | [Rama] | [Fuente primaria [@C2], Tier 1/2/3, YYYY-MM] | `[Fuerte]` / `[Moderada]` / `[Preliminar]` / `[Especulativa]` | [Falsador] |

## 7. Limitaciones y preguntas abiertas
- **Limitaciones metodológicas y de datos verificadas:** [Solo limitaciones respaldadas por intentos en línea y búsquedas locales registrados en la Sección 3 / `appendix/data_attempts.csv`]
- **Próximos pasos y experimentos sugeridos:** [Pruebas o mediciones concretas para resolver la incertidumbre restante]
```

---

## 4. `charts.json` v2 Schema (Publication SVG Engine)

Emit `charts.json` directly from `appendix/analysis.py` as a JSON array of chart objects. Supported types: `"line"`, `"bar"`, `"fan"`, `"scatter"`.

Authoring rules:
- **Annotation labels name the event**, not a phase number: `"Band 1,000–1,400"`, `"Step devaluation"`, `"Elections"` — never `"Phase 3"`. Keep them ≤16 characters (longer labels are truncated with `…`). The engine sorts annotations, staggers close ones over up to 3 rows, and flips labels near the right edge.
- **Axis formats:** `"y": {"format": "percent"}` for fractions (0.5 → 50%), `"thousands"` for large levels, `"currency"` for money. Thousands/decimal separators follow the report language (Spanish: `50.000`, `1,5`).
- **Scatter:** numeric X gets clean ticks automatically; a dashed `y = 0` line is drawn when 0 is in range; mark the current observation with `"highlight": {"x": …, "y": …, "label": "…"}`.
- **Fan:** the legend shows the median plus both bands (P25–P75, P10–P90) in the report language; the median line has no point markers.
- **Reference lines** get a white halo so their labels stay legible over the series.
- **Bar categories** wrap onto up to three lines; when they still do not fit, the engine draws horizontal bars automatically. Keep category names descriptive rather than truncating them by hand.
- **Near-identical bars** (spread under 1% of the largest value) show no visible difference and the validator warns. Either set `"y": {"baseline": 0.70}` (the axis starts at the baseline and a visible "Truncated axis" / "Eje truncado" notice is drawn) or set `"diff": true` (bars show the relative difference against the first bar, or against the first series in each group). Prefer `diff` or a table when the point is the size of a small difference.
- **`x.min` / `x.max`** clip a line or fan chart to a date or number range — e.g. `"x": {"type": "date", "max": "2026-11-19"}` removes the empty right-hand gap left by a band that extends past the last observation.
- **`x.last_label`** marks where the observed data end, with a dotted vertical line labelled *"Last data: 2026-11-13"* / *"Último dato: 2026-11-13"*. Give it as a **date** (`"last_label": "2026-11-13"`), or as `true` together with **`x.observed_until`** (`"x": {"type": "date", "last_label": true, "observed_until": "2026-11-13"}`). On a line chart, `true` alone marks the last observed point. A **fan chart** only holds the projection, so it needs the date: `true` without `observed_until` draws nothing and the validator warns. Use it on every fan chart and on every line chart whose X axis runs past the last observation.
- Write every title, caption, series name, and label in the report's language.

```json
[
  {
    "id": "fx_band",
    "type": "line",
    "title": "Wholesale Exchange Rate and Crawling Policy Band (2023–2026)",
    "caption": "Spot rate remained within the band, touching the upper bound in Sep 2025.",
    "source": "Central Bank API v4 (series 5); band reconstructed from policy rule.",
    "x": {"type": "date", "label": ""},
    "y": {"label": "Local Currency / USD", "scale": "linear", "format": "thousands"},
    "series": [
      {"name": "Spot Rate", "points": [["2023-12", 808.5], ["2024-06", 912.0], ["2025-09", 1395.0], ["2026-10", 1480.0]]}
    ],
    "bands": [
      {
        "name": "Policy Band (Floor–Ceiling)",
        "lower": [["2025-04", 1000.0], ["2026-10", 1080.0]],
        "upper": [["2025-04", 1400.0], ["2026-10", 1540.0]]
      }
    ],
    "annotations": [
      {"x": "2023-12", "label": "Step devaluation"},
      {"x": "2025-04", "label": "Band 1,000–1,400"}
    ]
  },
  {
    "id": "fx_gap",
    "type": "line",
    "title": "Parallel-Market Gap (2019–2026)",
    "caption": "Gap stored as a fraction in analysis.py and displayed as a percentage.",
    "source": "Own calculations from Central Bank and market quotes.",
    "x": {"type": "date"},
    "y": {"label": "Gap", "format": "percent"},
    "series": [
      {"name": "Gap", "points": [["2019-09", 0.12], ["2023-10", 1.65], ["2025-04", 0.03], ["2026-10", 0.05]]}
    ],
    "reference_lines": [{"name": "Zero gap", "value": 0.0}]
  },
  {
    "id": "rate_vs_fx",
    "type": "scatter",
    "title": "Real Policy Rate vs. 12-Month Depreciation by Quarter",
    "caption": "Highlighted point marks the latest quarter.",
    "source": "Own calculations in appendix/analysis.py.",
    "x": {"label": "Real policy rate (%)"},
    "y": {"label": "12-month depreciation (%)"},
    "series": [{"name": "Quarters", "points": [[-29.0, 140.0], [-5.2, 48.0], [3.1, 21.0], [6.7, 18.5]]}],
    "highlight": {"x": 6.7, "y": 18.5, "label": "2026-Q3"}
  },
  {
    "id": "proj_fan",
    "type": "fan",
    "title": "12-Month Scenario Fan Projection (P10–P90 and P25–P75)",
    "caption": "Fan reflects regime-weighted historical forecast errors; dashed line marks band ceiling identity.",
    "source": "Own calculations in appendix/analysis.py.",
    "x": {"type": "date"},
    "y": {"label": "Local Currency / USD", "scale": "linear"},
    "quantiles": {
      "p10": [["2026-11", 1480], ["2027-06", 1620], ["2027-12", 1780]],
      "p25": [["2026-11", 1480], ["2027-06", 1710], ["2027-12", 1950]],
      "p50": [["2026-11", 1480], ["2027-06", 1850], ["2027-12", 2210]],
      "p75": [["2026-11", 1480], ["2027-06", 2080], ["2027-12", 2640]],
      "p90": [["2026-11", 1480], ["2027-06", 2390], ["2027-12", 3150]]
    },
    "reference_lines": [
      {"name": "Band Ceiling Identity", "value": 2040}
    ]
  },
  {
    "id": "regime_bars",
    "type": "bar",
    "title": "Cumulative Nominal Depreciation vs. Inflation by Regime",
    "caption": "Separates crawling-peg and floating regimes to avoid pooling bias.",
    "source": "National Statistical Institute and Central Bank series.",
    "y": {"label": "Annualized Rate (%)"},
    "groups": ["Regime A (Float)", "Regime B (Crawl)", "Regime C (Band)"],
    "series": [
      {"name": "FX Depreciation (%)", "values": [48.2, 112.5, 24.1]},
      {"name": "CPI Inflation (%)", "values": [51.0, 128.4, 31.8]}
    ]
  },
  {
    "id": "flat_bars",
    "type": "bar",
    "title": "Single-Series Flat Bar Chart Example",
    "caption": "Flat (ungrouped) bar charts omit 'groups' and put one {'label', 'value'} object per bar inside 'series'.",
    "source": "Own calculations in appendix/analysis.py.",
    "y": {"label": "Slope"},
    "series": [
      {"label": "Rocky", "value": 0.25},
      {"label": "Sub-Neptune", "value": 0.43},
      {"label": "Gas Giant", "value": -0.05}
    ]
  }
]
```
