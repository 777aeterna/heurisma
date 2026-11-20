# Quantitative Forecasting & Scenario Calibration Protocol

Part of **Heurisma** (loaded during **Stage 0 / Stage 3** whenever an inquiry involves future projections, macroeconomic/financial forecasts, technology adoption timelines, or multi-scenario planning).

---

## Core Rule

```
AN ARITHMETIC IDENTITY, ACCOUNTING TAUTOLOGY, OR POLICY BAND CEILING IS A BOUNDARY CONDITION — NEVER A FORECAST.
```

Example: Calculating where an exchange-rate crawling band or statutory debt ceiling would sit in 12 months under its formula defines the *policy boundary assuming the regime survives*; it does **not** forecast the realized variable, which depends on the probability of regime survival vs. regime break.

---

## 1. Mandatory 5-Part Forecasting Protocol

### 1. Explicit Horizon, Target Definition & Unit Discipline
Before stating any projection, define without ambiguity:
- **As-Of Date & Last Observed Data Point:** Exact date of the report (`YYYY-MM-DD`) and the final date of each official historical series used.
- **Temporal Aggregation Unit:** Distinguish **end-of-period (EoP)** (e.g., Dec 31 spot value) from **period-average** (e.g., full-year mean). Never compare an EoP market quote against a period-average consensus forecast without adjustment.
- **Measurement Basis:** Nominal vs. real (deflated by which price index and base period?), local currency vs. USD/PPP, bilateral vs. multilateral index.

### 2. Lagging Official Series & Nowcasting Bridge
When an official series ends prior to the `As-Of Date`:
1. State the exact **last official observation date** (e.g., *"Official central bank series ends 2026-09"*).
2. Bridge the gap to the present (`nowcast`) using documented high-frequency proxies or market series, explicitly tagged **`[Preliminary]`**.
3. Never silently extrapolate a stale series as if it were current measured data.

### 3. Multi-Scenario Architecture (Minimum 3 Scenarios)
Never present a single point forecast for an uncertain complex system. Construct at least three mutually exclusive, exhaustive scenarios:

| Scenario | Required Elements |
| :--- | :--- |
| **Baseline / Modal Regime** | Explicit structural assumptions, policy/physical continuation rule, and estimated plausibility weight or probability range. |
| **Upside / Accelerated Case** | Concrete observable **trigger conditions** (what must happen first), quantification of the transmission channel, and probability range. |
| **Downside / Regime-Break Case** | Concrete **stress triggers** (e.g., reserve threshold breach, supply bottleneck, regulatory delay), historical base rate of similar breaks, and magnitude calibrated from historical analogies. |

### 4. Calibration Against Historical Forecast Errors
Point forecasts and institutional consensus surveys (e.g., central bank market expectations surveys, IEA/industry roadmaps) systematically understate tail risk and regime shifts:
- When citing consensus or survey forecasts, inspect or compute their **historical forecast error** (MAE, RMSE, or directional hit rate at 6-, 12-, and 24-month horizons) if historical vintages exist.
- Width of scenario intervals should reflect empirical historical forecast errors rather than narrow within-regime linear trend bands.

### 5. Epistemic Tag Ceiling for Forecasts
- Pure accounting/physical conservation bounds conditional on explicit assumptions: up to **`[Strong]`** or **`[Moderate]`** *strictly as conditional bounds* (`"If X holds, Y must exceed Z"`).
- Empirically calibrated near-term nowcasts or base-rate frequencies: **`[Moderate]`** or **`[Preliminary]`**.
- Unconditional point or regime forecasts over future multi-month/multi-year horizons: **`[Preliminary]`** or **`[Speculative]`** (never `[Strong]`).
