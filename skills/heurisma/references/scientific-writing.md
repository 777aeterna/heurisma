# Calibrated Scientific Writing, Single-Language Templates & `charts.json` v2 Guide

Part of **Heurisma** (loaded during **Stage 5 & Stage 6** before finalizing `report.md` and rendering the working-paper `report.html`).

---

## 1. Epistemic Calibration Scale (English & Spanish)

Every major claim in Section 1, Section 4, and **every row** of Section 6 (`Claim-Evidence Matrix` / `Matriz de afirmaciones y evidencia`) MUST carry a bracketed calibration tag matching the report's language:

| English Tag | Spanish Tag | Meaning | Minimum Evidence Required | Strictly Forbidden For |
| :--- | :--- | :--- | :--- | :--- |
| **`[Strong]`** | **`[Fuerte]`** | High epistemic confidence; robust against confounders | Formal deductive proof; meta-analysis of human RCTs; replicated Tier 1 measurements; conservation laws | **Any Tier 3 or press/blog/roadmap source** (`validate_report.py` rejects this), single studies, or unconditional future forecasts |
| **`[Moderate]`** | **`[Moderada]`** | Credible empirical support within bounded conditions | Well-designed single RCT, quasi-experimental causal study (DiD/IV/RDD), audited primary institutional series (Tier 1/2) | Press releases, small unadjusted samples ($n < 30$), uncalibrated extrapolations |
| **`[Preliminary]`** | **`[Preliminar]`** | Suggestive or context-limited evidence requiring replication | Small-sample empirical data, single observational cohort, high-frequency proxy bridging a lagging series | Definitive policy mandates or unverified claims introduced by a reviewer |
| **`[Speculative]`** | **`[Especulativa]`** | Unverified projection, mechanism hypothesis, or scenario | Corporate roadmap dates, animal/prototype mechanism extrapolated to scale, multi-month point/regime forecast | Presenting as established fact or probable baseline without flagging failure risk |

---

## 2. Working-Paper Prose & Abstract Rules

1. **Abstract-Style Verdict (Max 3 Sentences, Max 5 Numbers):**
   - `Calibrated Verdict` / `Veredicto calibrado` in Section 1 acts as the paper's **Abstract**: state the direct answer, its calibration tag, and the core mechanism in **at most 3 sentences and at most 5 numbers**.
   - Never pack 15 numbers into a dense wall of text in Section 1; put detailed metrics in Section 4 booktabs tables and `{{fig:id}}` figures.
   - Do not over-quantify illustrative scenario probabilities (e.g., if scenario weights are illustrative rather than structurally estimated, present scenario levels cleanly without fake 4-decimal precision on combined percentiles).
2. **Inline Figure Placement (`{{fig:chart_id}}`):**
   - Place `{{fig:chart_id}}` on its own line in Section 4 or Section 5 immediately after the paragraph that discusses that figure.
   - `render_report.py` replaces `{{fig:chart_id}}` with a numbered `<figure>` (`Figure 1. Title`, publication SVG, `Note: caption`, `Source: ...`, and a collapsible data table).
3. **Zero Code / Zero Bloat in `report.md`:**
   - Never embed scripts or raw console outputs inside `report.md`. Keep `report.md` focused purely on scientific argument, tables, and `{{fig:id}}` figures.

---

## 3. Strict Single-Language Consistency (100% Spanish Template)

When the user requests a report in Spanish, **do not mix English labels or English table headers into the text**. Use this 100% Spanish contract (accepted natively by `validate_report.py` and `render_report.py`):

```markdown
# [Título descriptivo del documento de trabajo]

> **Fecha de corte (As-Of):** YYYY-MM-DD | **Nivel de profundidad:** Nivel <1|2|3> | **Disciplinas:** [Ramas]

## 1. Resumen ejecutivo
- **Veredicto calibrado:** [Máximo 3 oraciones y máximo 5 cifras respondiendo la pregunta con etiquetas `[Fuerte]` / `[Moderada]` / `[Preliminar]` / `[Especulativa]`.]
- **Qué cambiaría esta conclusión:** [Umbral empírico u observación concreta que revertiría el veredicto.]
- **Conclusiones clave:** [2 a 4 viñetas concisas separando lo que se sostiene bajo escrutinio de lo incierto.]

## 2. Encuadre e hipótesis
- **Disciplinas científicas y nivel:** [Ramas + acoplamiento interdisciplinario]
- **Pregunta de investigación:** [Pregunta neutral y operacionalizada con unidades y horizonte]
- **Hipótesis:**
  - $H_0$: [Hipótesis nula / línea base / artefacto]
  - $H_1$: [Hipótesis alternativa]
- **Criterios de refutación:** [Condiciones empíricas o lógicas exactas que refutan $H_1$ y $H_0$]

## 3. Metodología y estándares de evidencia
- **Jerarquía de evidencia del dominio:** [Estándares Tier 1 vs. Tier 2 vs. Tier 3]
- **Procedencia analítica y de datos:** [Resumen del método, enlaces a `appendix/fetch_data.py`, `appendix/analysis.py`, `appendix/output.txt` y `appendix/sources.csv`, más la tabla de **Intentos de datos** si falló alguna fuente primaria]

## 4. Hallazgos
[Análisis estructurado por hipótesis o eje/régimen, con tablas sobrias y marcadores `{{fig:id_grafico}}` en el lugar exacto donde se analiza cada figura.]

## 5. Contraevidencia y explicaciones alternativas
[Mejor evidencia en contra, límites de régimen, confusores y —en Nivel 3— la tabla **Disposición del Revisor #2** con encabezados en español (`| Falla # | Crítica del revisor | Acción | Evidencia / Artefacto |`).]

## 6. Matriz de afirmaciones y evidencia
| Afirmación | Disciplina / Eje | Evidencia y Tier (Fecha de datos) | Confianza | Falsador clave / Condición |
| :- | :- | :- | :- | :- |
| [Afirmación 1] | [Rama] | [Fuente primaria, Tier 1/2/3, YYYY-MM] | `[Fuerte]` / `[Moderada]` / `[Preliminar]` / `[Especulativa]` | [Falsador] |
| [Afirmación 2] | [Rama] | [Fuente primaria, Tier 1/2/3, YYYY-MM] | `[Fuerte]` / `[Moderada]` / `[Preliminar]` / `[Especulativa]` | [Falsador] |

## 7. Limitaciones y preguntas abiertas
- **Limitaciones metodológicas y de datos verificadas:** [Solo limitaciones respaldadas por intentos registrados en la Sección 3 / `appendix/data_attempts.csv`]
- **Próximos pasos y experimentos sugeridos:** [Pruebas o mediciones concretas para resolver la incertidumbre restante]
```

---

## 4. `charts.json` v2 Schema (Publication SVG Engine)

Emit `charts.json` directly from `appendix/analysis.py` as a JSON array of chart objects. Supported types: `"line"`, `"bar"`, `"fan"`, `"scatter"`.

```json
[
  {
    "id": "fx_band",
    "type": "line",
    "title": "Wholesale Exchange Rate and Crawling Policy Band (2023–2026)",
    "caption": "Spot rate remained within the band, touching the upper bound in Sep 2025.",
    "source": "Central Bank API v4 (series 5); band reconstructed from policy rule.",
    "x": {"type": "date", "label": ""},
    "y": {"label": "Local Currency / USD", "scale": "linear"},
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
      {"x": "2023-12", "label": "Step Devaluation"},
      {"x": "2025-04", "label": "Band Regime"}
    ]
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
  }
]
```
