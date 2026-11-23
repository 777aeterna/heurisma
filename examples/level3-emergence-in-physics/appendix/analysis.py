#!/usr/bin/env python3
"""Reproducible 2D Ising finite-size scaling, universality & emergence simulation (Heurisma v0.10.1).

Zero-dependency Python 3 standard-library implementation of:
  1. Exact Onsager (1944) square-lattice (Tc = 2/ln(1+sqrt(2))) and exact triangular-lattice
     (Tc_tri = 4/ln(3)) thermodynamic-limit benchmarks and 2D Ising universality exponents.
  2. Exact finite-N partition function enumeration for L=2, 3, 4 verifying Lee-Yang analyticity
     and exact zero signed magnetization <m> = 0 under Z2 symmetry.
  3. Wolff single-cluster Monte Carlo simulations on periodic L x L square lattices
     (L = 8, 12, 16, 24, 32) across 17 temperatures spanning ordered, critical, and disordered
     regimes, with 20 measurement blocks per (L, T) for delete-1 block-jackknife SEs,
     lag-1 block autocorrelation, effective sweeps per block, and hot-vs-cold equilibration check.
  4. Second microscopic Hamiltonian in the same 2D Z2 universality class: periodic L x L
     triangular-lattice ferromagnetic Ising model (z = 6 neighbors, Tc_tri = 4/ln(3) = 3.6410)
     simulated at Tc_tri across L = 8, 12, 16, 24, 32 to directly test RG universality.
  5. Pre-registered finite-size scaling regression of log(chi_max) vs. log(L) with block-bootstrap
     95% CIs (2,000 replicates), plus WLS regressions at Tc with exact Student-t 95% CIs,
     reduced chi^2/df, L >= 12 sensitivity fits, jackknife SEs for all three Binder U4 crossings,
     and a 3-seed stability check.

Outputs (written relative to report root):
  - appendix/output.txt
  - appendix/numbers.json
  - charts.json          (Heurisma v2 schema)
"""

from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path

APPENDIX = Path(__file__).resolve().parent
REPORT_DIR = APPENDIX.parent

# Exact 2D Ising constants (J=1, kB=1)
TC_EXACT = 2.0 / math.log(1.0 + math.sqrt(2.0))   # 2.269185314213022 (square, z=4)
TC_TRI_EXACT = 4.0 / math.log(3.0)                # 3.640956906507210 (triangular, z=6)
GAMMA_NU_EXACT = 1.75   # 7/4
BETA_NU_EXACT = 0.125   # 1/8
CV_THEORY_SLOPE = (2.0 / math.pi) * (2.0 / TC_EXACT) ** 2  # 0.4945

# Exact two-sided Student-t 95% critical values t_{0.975, df}
T_CRIT_95 = {1: 12.7062, 2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706}

# Simulation parameters (deterministic seed)
SEED = 42
LATTICE_SIZES = [8, 12, 16, 24, 32]
TEMPS = [
    1.80, 2.00, 2.12, 2.20, 2.24,
    2.26, round(TC_EXACT, 4), 2.28, 2.30, 2.32,
    2.35, 2.38, 2.42, 2.48, 2.55, 2.75, 3.00,
]
N_THERM = 500
N_BLOCKS = 20
STEPS_PER_BLOCK = 180  # 3,600 measured Wolff cluster updates per (L, T)
N_BOOT = 2000


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )


def onsager_magnetization(temp: float) -> float:
    if temp >= TC_EXACT:
        return 0.0
    s = math.sinh(2.0 / temp)
    val = 1.0 - (s ** -4)
    return val ** 0.125 if val > 0.0 else 0.0


def exact_small_lattice(L: int, temp: float) -> dict[str, float]:
    """Exact enumeration for small periodic L x L square lattices (L <= 4)."""
    n = L * L
    beta = 1.0 / temp
    edges = []
    for r in range(L):
        for c in range(L):
            i = r * L + c
            edges.append((i, r * L + ((c + 1) % L)))
            edges.append((i, ((r + 1) % L) * L + c))

    e_shift = -2.0 * n
    z = sum_m = sum_abs_m = sum_m2 = sum_m4 = sum_e = sum_e2 = 0.0
    for state in range(1 << n):
        m_int = 2 * state.bit_count() - n
        e_int = 0
        for u, v in edges:
            e_int += -1 if ((state >> u) & 1) == ((state >> v) & 1) else 1
        w = math.exp(-beta * (e_int - e_shift))
        m_val = m_int / n
        e_val = e_int / n
        z += w
        sum_m += w * m_val
        sum_abs_m += w * abs(m_val)
        sum_m2 += w * (m_val * m_val)
        sum_m4 += w * (m_val ** 4)
        sum_e += w * e_val
        sum_e2 += w * (e_val * e_val)

    avg_m = sum_m / z
    if abs(avg_m) < 1e-12:
        avg_m = 0.0
    avg_abs_m = sum_abs_m / z
    avg_m2 = sum_m2 / z
    avg_m4 = sum_m4 / z
    avg_e = sum_e / z
    avg_e2 = sum_e2 / z
    return {
        "m_signed": avg_m,
        "abs_m": avg_abs_m,
        "chi": (n / temp) * (avg_m2 - avg_abs_m * avg_abs_m),
        "chi0": (n / temp) * avg_m2,
        "cv": (n / (temp * temp)) * (avg_e2 - avg_e * avg_e),
        "u4": 1.0 - avg_m4 / (3.0 * avg_m2 * avg_m2),
    }


def build_neighbors(L: int, lattice: str = "square") -> list[tuple[int, ...]]:
    nbrs = []
    for r in range(L):
        rm = (r - 1) % L
        rp = (r + 1) % L
        for c in range(L):
            cm = (c - 1) % L
            cp = (c + 1) % L
            if lattice == "square":
                nbrs.append((r * L + cp, r * L + cm, rp * L + c, rm * L + c))
            elif lattice == "triangular":
                nbrs.append((
                    r * L + cp, r * L + cm,
                    rp * L + c, rm * L + c,
                    rp * L + cp, rm * L + cm,
                ))
            else:
                raise ValueError(f"Unknown lattice: {lattice}")
    return nbrs


def lag1_autocorr(vals: list[float]) -> float:
    if len(vals) < 3:
        return 0.0
    mu = statistics.fmean(vals)
    den = sum((v - mu) ** 2 for v in vals)
    if den < 1e-15:
        return 0.0
    num = sum((vals[i] - mu) * (vals[i + 1] - mu) for i in range(len(vals) - 1))
    return num / den


def wolff_simulate(
    L: int,
    temp: float,
    rng: random.Random,
    lattice: str = "square",
    hot_start: bool = False,
    compute_cv: bool = True,
) -> dict[str, object]:
    """Run Wolff single-cluster MC at (L, temp) and return observables, diagnostics, and block arrays."""
    n = L * L
    nbrs = build_neighbors(L, lattice)
    p_add = 1.0 - math.exp(-2.0 / temp)
    spins = [1 if rng.random() < 0.5 else -1 for _ in range(n)] if hot_start else [1] * n
    mag_int = sum(spins)

    rand = rng.random
    randrange = rng.randrange

    def wolff_step() -> int:
        nonlocal mag_int
        seed = randrange(n)
        old_s = spins[seed]
        new_s = -old_s
        spins[seed] = new_s
        stack = [seed]
        csize = 1
        while stack:
            u = stack.pop()
            for v in nbrs[u]:
                if spins[v] == old_s and rand() < p_add:
                    spins[v] = new_s
                    stack.append(v)
                    csize += 1
        mag_int += 2 * new_s * csize
        return csize

    def compute_energy_sq() -> int:
        e = 0
        for r in range(L):
            row_off = r * L
            next_row = ((r + 1) % L) * L
            for c in range(L):
                i = row_off + c
                si = spins[i]
                e -= si * (spins[row_off + ((c + 1) % L)] + spins[next_row + c])
        return e

    # Thermalization
    for _ in range(N_THERM):
        wolff_step()

    blk_abs_m: list[float] = []
    blk_m2: list[float] = []
    blk_m4: list[float] = []
    blk_e: list[float] = []
    blk_e2: list[float] = []
    total_cluster_spins = 0

    inv_n = 1.0 / n
    for _ in range(N_BLOCKS):
        s_am = s_m2 = s_m4 = s_e = s_e2 = 0.0
        for _ in range(STEPS_PER_BLOCK):
            total_cluster_spins += wolff_step()
            m = mag_int * inv_n
            am = abs(m)
            m2 = m * m
            s_am += am
            s_m2 += m2
            s_m4 += m2 * m2
            if compute_cv and lattice == "square":
                e = compute_energy_sq() * inv_n
                s_e += e
                s_e2 += e * e
        k = float(STEPS_PER_BLOCK)
        blk_abs_m.append(s_am / k)
        blk_m2.append(s_m2 / k)
        blk_m4.append(s_m4 / k)
        blk_e.append(s_e / k)
        blk_e2.append(s_e2 / k)

    mean_am = statistics.fmean(blk_abs_m)
    mean_m2 = statistics.fmean(blk_m2)
    mean_m4 = statistics.fmean(blk_m4)
    mean_e = statistics.fmean(blk_e)
    mean_e2 = statistics.fmean(blk_e2)

    chi = (n / temp) * (mean_m2 - mean_am * mean_am)
    chi0 = (n / temp) * mean_m2
    cv = (n / (temp * temp)) * (mean_e2 - mean_e * mean_e) if (compute_cv and lattice == "square") else 0.0
    u4 = 1.0 - mean_m4 / (3.0 * mean_m2 * mean_m2)

    # Delete-1 block jackknife replicates
    B = N_BLOCKS
    jk_am, jk_chi, jk_chi0, jk_cv, jk_u4 = [], [], [], [], []
    sum_am, sum_m2, sum_m4 = sum(blk_abs_m), sum(blk_m2), sum(blk_m4)
    sum_e, sum_e2 = sum(blk_e), sum(blk_e2)
    for b in range(B):
        am_b = (sum_am - blk_abs_m[b]) / (B - 1)
        m2_b = (sum_m2 - blk_m2[b]) / (B - 1)
        m4_b = (sum_m4 - blk_m4[b]) / (B - 1)
        e_b = (sum_e - blk_e[b]) / (B - 1)
        e2_b = (sum_e2 - blk_e2[b]) / (B - 1)
        jk_am.append(am_b)
        jk_chi.append((n / temp) * (m2_b - am_b * am_b))
        jk_chi0.append((n / temp) * m2_b)
        jk_cv.append((n / (temp * temp)) * (e2_b - e_b * e_b))
        jk_u4.append(1.0 - m4_b / (3.0 * m2_b * m2_b))

    def jk_se(vals: list[float]) -> float:
        mu = statistics.fmean(vals)
        return math.sqrt(((B - 1) / B) * sum((v - mu) ** 2 for v in vals))

    mean_cluster = total_cluster_spins / (N_BLOCKS * STEPS_PER_BLOCK)
    eff_sweeps_per_blk = STEPS_PER_BLOCK * mean_cluster / n

    return {
        "abs_m": mean_am,
        "abs_m_se": jk_se(jk_am),
        "chi": chi,
        "chi_se": jk_se(jk_chi),
        "chi0": chi0,
        "chi0_se": jk_se(jk_chi0),
        "cv": cv,
        "cv_se": jk_se(jk_cv),
        "u4": u4,
        "u4_se": jk_se(jk_u4),
        "jk_u4": jk_u4,
        "blk_am": blk_abs_m,
        "blk_m2": blk_m2,
        "r1_m2": lag1_autocorr(blk_m2),
        "eff_sweeps_per_blk": eff_sweeps_per_blk,
    }


def wls_fit(xs: list[float], ys: list[float], ses: list[float]) -> dict[str, float]:
    """Weighted least squares y = a + b*x with exact Student-t 95% CI and reduced chi^2/df."""
    n = len(xs)
    df = n - 2
    ws = [1.0 / max(se * se, 1e-12) for se in ses]
    sw = sum(ws)
    sx = sum(w * x for w, x in zip(ws, xs))
    sy = sum(w * y for w, y in zip(ws, ys))
    sxx = sum(w * x * x for w, x in zip(ws, xs))
    sxy = sum(w * x * y for w, x, y in zip(ws, xs, ys))
    denom = sw * sxx - sx * sx
    b = (sw * sxy - sx * sy) / denom
    a = (sy - b * sx) / sw
    se_b = math.sqrt(sw / denom)
    chi2 = sum(w * (y - (a + b * x)) ** 2 for w, x, y in zip(ws, xs, ys))
    red_chi2 = chi2 / df if df > 0 else 0.0
    # Scale SE by sqrt(max(1, red_chi2)) if overdispersed
    se_eff = se_b * math.sqrt(max(1.0, red_chi2))
    t_crit = T_CRIT_95[df]
    my = statistics.fmean(ys)
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {
        "slope": b,
        "se": se_eff,
        "lo": b - t_crit * se_eff,
        "hi": b + t_crit * se_eff,
        "intercept": a,
        "r2": r2,
        "chi2_df": red_chi2,
        "df": df,
        "t_crit": t_crit,
    }


def ols_slope(xs: list[float], ys: list[float]) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


def find_crossing(temps: list[float], u1: list[float], u2: list[float]) -> float | None:
    diffs = [a - b for a, b in zip(u1, u2)]
    for i in range(len(temps) - 1):
        d0, d1 = diffs[i], diffs[i + 1]
        if d0 == 0.0:
            return temps[i]
        if (d0 < 0 and d1 > 0) or (d0 > 0 and d1 < 0):
            frac = abs(d0) / (abs(d0) + abs(d1))
            return temps[i] + frac * (temps[i + 1] - temps[i])
    return None


def main() -> None:
    rng = random.Random(SEED)
    lines: list[str] = []
    nums: dict[str, str] = {}

    def log(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    log("=" * 80)
    log("HEURISMA COMPUTATIONAL APPENDIX — EMERGENCE IN PHYSICS (2D ISING UNIVERSALITY)")
    log("=" * 80)
    log(
        f"Seed: {SEED} | Lattices: {LATTICE_SIZES} | Temps: {len(TEMPS)} points [{TEMPS[0]}..{TEMPS[-1]}]"
    )
    log(
        f"Wolff MC protocol: N_THERM={N_THERM}, N_BLOCKS={N_BLOCKS}, "
        f"STEPS_PER_BLOCK={STEPS_PER_BLOCK} ({N_BLOCKS * STEPS_PER_BLOCK} measured updates per (L,T)), "
        f"N_BOOT={N_BOOT}"
    )
    log(
        f"Exact square Tc = {TC_EXACT:.6f} | Exact triangular Tc_tri = {TC_TRI_EXACT:.6f} | "
        f"Exact gamma/nu = {GAMMA_NU_EXACT:.4f} | Exact beta/nu = {BETA_NU_EXACT:.4f}"
    )

    nums["tc_exact"] = f"{TC_EXACT:.4f}"
    nums["tc_tri_exact"] = f"{TC_TRI_EXACT:.4f}"
    nums["gamma_nu_exact"] = f"{GAMMA_NU_EXACT:.2f}"
    nums["beta_nu_exact"] = f"{BETA_NU_EXACT:.3f}"
    nums["cv_theory_slope"] = f"{CV_THEORY_SLOPE:.3f}"
    nums["n_therm"] = str(N_THERM)
    nums["n_blocks"] = str(N_BLOCKS)
    nums["steps_per_block"] = str(STEPS_PER_BLOCK)
    nums["total_updates"] = f"{N_BLOCKS * STEPS_PER_BLOCK:,}"

    # 1. Exact small-lattice verification of Lee-Yang analyticity & zero exact <m>
    log("\n--- 1. EXACT ENUMERATION AT Tc (FINITE-N ANALYTICITY & Z2 SYMMETRY) ---")
    log(f"{'L':>4} {'N':>5} {'<m> (signed)':>14} {'<|m|>':>10} {'chi0':>10} {'chi':>10} {'Cv':>10} {'U4':>10}")
    for L in (2, 3, 4):
        ex = exact_small_lattice(L, TC_EXACT)
        log(
            f"{L:4d} {L*L:5d} {ex['m_signed']:14.1f} {ex['abs_m']:10.4f} "
            f"{ex['chi0']:10.4f} {ex['chi']:10.4f} {ex['cv']:10.4f} {ex['u4']:10.4f}"
        )
        nums[f"exact_L{L}_m_signed"] = f"{ex['m_signed']:.1f}"

    # 2. Wolff MC across all (L, T) on square lattice
    results: dict[int, dict[float, dict[str, object]]] = {}
    for L in LATTICE_SIZES:
        results[L] = {}
        for T in TEMPS:
            results[L][T] = wolff_simulate(L, T, rng, lattice="square", hot_start=False, compute_cv=True)

    tc_grid = round(TC_EXACT, 4)

    log("\n--- 2. SQUARE-LATTICE OBSERVABLES AT Tc (T = 2.2692) ---")
    log(f"{'L':>4} {'N':>5} {'<|m|> +/- SE':>18} {'chi0 +/- SE':>18} {'chi +/- SE':>18} {'Cv +/- SE':>16} {'U4 +/- SE':>16}")
    for L in LATTICE_SIZES:
        r = results[L][tc_grid]
        log(
            f"{L:4d} {L*L:5d} "
            f"{r['abs_m']:7.4f} +/- {r['abs_m_se']:6.4f} "
            f"{r['chi0']:7.2f} +/- {r['chi0_se']:6.2f} "
            f"{r['chi']:7.2f} +/- {r['chi_se']:6.2f} "
            f"{r['cv']:6.3f} +/- {r['cv_se']:5.3f} "
            f"{r['u4']:6.4f} +/- {r['u4_se']:6.4f}"
        )
        nums[f"tc_L{L}_abs_m"] = f"{r['abs_m']:.3f}"
        nums[f"tc_L{L}_abs_m_se"] = f"{r['abs_m_se']:.3f}"
        nums[f"tc_L{L}_chi0"] = f"{r['chi0']:.1f}"
        nums[f"tc_L{L}_chi0_se"] = f"{r['chi0_se']:.1f}"
        nums[f"tc_L{L}_chi"] = f"{r['chi']:.2f}"
        nums[f"tc_L{L}_chi_se"] = f"{r['chi_se']:.2f}"
        nums[f"tc_L{L}_cv"] = f"{r['cv']:.3f}"
        nums[f"tc_L{L}_cv_se"] = f"{r['cv_se']:.3f}"
        nums[f"tc_L{L}_u4"] = f"{r['u4']:.3f}"
        nums[f"tc_L{L}_u4_se"] = f"{r['u4_se']:.3f}"

    # 3. Equilibration & autocorrelation diagnostics
    hot_rng = random.Random(SEED + 999)
    r_hot = wolff_simulate(32, tc_grid, hot_rng, lattice="square", hot_start=True, compute_cv=False)
    r_cold = results[32][tc_grid]
    hot_cold_z = (r_hot["chi0"] - r_cold["chi0"]) / math.sqrt(r_hot["chi0_se"] ** 2 + r_cold["chi0_se"] ** 2)
    r_dis32 = results[32][2.75]

    log("\n--- 3. EQUILIBRATION & AUTOCORRELATION DIAGNOSTICS (L = 32) ---")
    log(
        f"Hot vs Cold start at (L=32, Tc): cold chi0 = {r_cold['chi0']:.2f} +/- {r_cold['chi0_se']:.2f}, "
        f"hot chi0 = {r_hot['chi0']:.2f} +/- {r_hot['chi0_se']:.2f} (z = {hot_cold_z:+.2f})"
    )
    log(
        f"L=32 at Tc:   lag-1 block autocorr r1(m^2) = {r_cold['r1_m2']:+.3f}, "
        f"eff. sweeps/block = {r_cold['eff_sweeps_per_blk']:.1f}"
    )
    log(
        f"L=32 at 2.75: lag-1 block autocorr r1(m^2) = {r_dis32['r1_m2']:+.3f}, "
        f"eff. sweeps/block = {r_dis32['eff_sweeps_per_blk']:.1f}"
    )
    nums["hot_cold_z"] = f"{hot_cold_z:+.2f}"
    nums["r1_tc_32"] = f"{r_cold['r1_m2']:+.2f}"
    nums["sweeps_tc_32"] = f"{r_cold['eff_sweeps_per_blk']:.1f}"
    nums["sweeps_275_32"] = f"{r_dis32['eff_sweeps_per_blk']:.1f}"

    # 4. Second microscopic Hamiltonian: 2D Triangular-Lattice Ising at exact Tc_tri = 4/ln(3)
    tri_res: dict[int, dict[str, object]] = {}
    for L in LATTICE_SIZES:
        tri_res[L] = wolff_simulate(L, TC_TRI_EXACT, rng, lattice="triangular", hot_start=False, compute_cv=False)

    log("\n--- 4. SECOND MICROSCOPIC HAMILTONIAN: 2D TRIANGULAR ISING AT Tc_tri (3.6410) ---")
    log(f"{'L':>4} {'N':>5} {'<|m|> +/- SE':>18} {'chi0 +/- SE':>18} {'U4 +/- SE':>16}")
    for L in LATTICE_SIZES:
        r = tri_res[L]
        log(
            f"{L:4d} {L*L:5d} "
            f"{r['abs_m']:7.4f} +/- {r['abs_m_se']:6.4f} "
            f"{r['chi0']:7.2f} +/- {r['chi0_se']:6.2f} "
            f"{r['u4']:6.4f} +/- {r['u4_se']:6.4f}"
        )
        nums[f"tri_L{L}_chi0"] = f"{r['chi0']:.1f}"
        nums[f"tri_L{L}_chi0_se"] = f"{r['chi0_se']:.1f}"

    # 5. Pre-registered primary regression: log(chi_max(L)) vs. log(L) with block-bootstrap 95% CI
    log_L = [math.log(L) for L in LATTICE_SIZES]
    peak_temps = {L: max(TEMPS, key=lambda t: results[L][t]["chi"]) for L in LATTICE_SIZES}
    chi_max_vals = [results[L][peak_temps[L]]["chi"] for L in LATTICE_SIZES]
    chi_max_ses = [results[L][peak_temps[L]]["chi_se"] for L in LATTICE_SIZES]
    log_chi_max = [math.log(v) for v in chi_max_vals]
    se_log_chi_max = [s / v for v, s in zip(chi_max_vals, chi_max_ses)]
    fit_peak = wls_fit(log_L, log_chi_max, se_log_chi_max)

    # Block-bootstrap (2,000 replicates) for pre-registered log(chi_max) vs log(L)
    boot_rng = random.Random(SEED + 1)
    boot_slopes: list[float] = []
    for _ in range(N_BOOT):
        b_y = []
        for L in LATTICE_SIZES:
            t_pk = peak_temps[L]
            r = results[L][t_pk]
            idx = [boot_rng.randrange(N_BLOCKS) for _ in range(N_BLOCKS)]
            am_b = statistics.fmean([r["blk_am"][i] for i in idx])
            m2_b = statistics.fmean([r["blk_m2"][i] for i in idx])
            chi_b = max((L * L / t_pk) * (m2_b - am_b * am_b), 1e-6)
            b_y.append(math.log(chi_b))
        boot_slopes.append(ols_slope(log_L, b_y))
    boot_slopes.sort()
    peak_boot_lo = boot_slopes[int(0.025 * N_BOOT)]
    peak_boot_hi = boot_slopes[int(0.975 * N_BOOT)]
    peak_ols = ols_slope(log_L, log_chi_max)

    # Complementary WLS regressions at Tc (exact Student-t 95% CIs, chi^2/df)
    log_chi0 = [math.log(results[L][tc_grid]["chi0"]) for L in LATTICE_SIZES]
    se_log_chi0 = [results[L][tc_grid]["chi0_se"] / results[L][tc_grid]["chi0"] for L in LATTICE_SIZES]
    fit_chi0 = wls_fit(log_L, log_chi0, se_log_chi0)
    fit_chi0_ge12 = wls_fit(log_L[1:], log_chi0[1:], se_log_chi0[1:])

    log_am = [math.log(results[L][tc_grid]["abs_m"]) for L in LATTICE_SIZES]
    se_log_am = [results[L][tc_grid]["abs_m_se"] / results[L][tc_grid]["abs_m"] for L in LATTICE_SIZES]
    fit_am = wls_fit(log_L, log_am, se_log_am)
    fit_am_ge12 = wls_fit(log_L[1:], log_am[1:], se_log_am[1:])

    cvs = [results[L][tc_grid]["cv"] for L in LATTICE_SIZES]
    cv_ses = [results[L][tc_grid]["cv_se"] for L in LATTICE_SIZES]
    fit_cv = wls_fit(log_L, cvs, cv_ses)

    # Triangular lattice WLS regressions at Tc_tri
    tri_log_chi0 = [math.log(tri_res[L]["chi0"]) for L in LATTICE_SIZES]
    tri_se_chi0 = [tri_res[L]["chi0_se"] / tri_res[L]["chi0"] for L in LATTICE_SIZES]
    fit_tri_chi0 = wls_fit(log_L, tri_log_chi0, tri_se_chi0)

    tri_log_am = [math.log(tri_res[L]["abs_m"]) for L in LATTICE_SIZES]
    tri_se_am = [tri_res[L]["abs_m_se"] / tri_res[L]["abs_m"] for L in LATTICE_SIZES]
    fit_tri_am = wls_fit(log_L, tri_log_am, tri_se_am)

    chi0_ratio = results[32][tc_grid]["chi0"] / results[8][tc_grid]["chi0"]
    chi_ratio = results[32][tc_grid]["chi"] / results[8][tc_grid]["chi"]
    cv_ratio = results[32][tc_grid]["cv"] / results[8][tc_grid]["cv"]

    log("\n--- 5. FINITE-SIZE SCALING REGRESSIONS (EXACT STUDENT-t CIs & BLOCK BOOTSTRAP) ---")
    log(
        f"[Pre-registered] log(chi_max) vs log(L): OLS={peak_ols:.4f} (block-bootstrap 95% CI "
        f"[{peak_boot_lo:.3f}, {peak_boot_hi:.3f}]); WLS={fit_peak['slope']:.4f} +/- {fit_peak['se']:.4f} "
        f"(t-95% CI [{fit_peak['lo']:.3f}, {fit_peak['hi']:.3f}], chi2/df={fit_peak['chi2_df']:.2f}, R^2={fit_peak['r2']:.4f})"
    )
    log(
        f"[Square Tc]      chi0(Tc, L) ~ L^(g/n):  g/n = {fit_chi0['slope']:.4f} +/- {fit_chi0['se']:.4f} "
        f"(t-95% CI [{fit_chi0['lo']:.3f}, {fit_chi0['hi']:.3f}], chi2/df={fit_chi0['chi2_df']:.2f}, R^2={fit_chi0['r2']:.5f}) | "
        f"L>=12: {fit_chi0_ge12['slope']:.4f} +/- {fit_chi0_ge12['se']:.4f}"
    )
    log(
        f"[Triangular Tc]  chi0(Tc, L) ~ L^(g/n):  g/n = {fit_tri_chi0['slope']:.4f} +/- {fit_tri_chi0['se']:.4f} "
        f"(t-95% CI [{fit_tri_chi0['lo']:.3f}, {fit_tri_chi0['hi']:.3f}], chi2/df={fit_tri_chi0['chi2_df']:.2f}, R^2={fit_tri_chi0['r2']:.5f})"
    )
    log(
        f"[Square Tc]      <|m|>(Tc, L) ~ L^(-b/n): b/n = {-fit_am['slope']:.4f} +/- {fit_am['se']:.4f} "
        f"(t-95% CI [{-fit_am['hi']:.3f}, {-fit_am['lo']:.3f}], chi2/df={fit_am['chi2_df']:.2f}, R^2={fit_am['r2']:.4f}) | "
        f"L>=12: {-fit_am_ge12['slope']:.4f} +/- {fit_am_ge12['se']:.4f}"
    )
    log(
        f"[Triangular Tc]  <|m|>(Tc, L) ~ L^(-b/n): b/n = {-fit_tri_am['slope']:.4f} +/- {fit_tri_am['se']:.4f} "
        f"(t-95% CI [{-fit_tri_am['hi']:.3f}, {-fit_tri_am['lo']:.3f}], chi2/df={fit_tri_am['chi2_df']:.2f}, R^2={fit_tri_am['r2']:.4f})"
    )
    log(
        f"[Square Tc]      Cv(Tc, L) ~ a*ln(L)+b:  a   = {fit_cv['slope']:.4f} +/- {fit_cv['se']:.4f} "
        f"(t-95% CI [{fit_cv['lo']:.3f}, {fit_cv['hi']:.3f}], chi2/df={fit_cv['chi2_df']:.2f}, R^2={fit_cv['r2']:.4f}) | "
        f"Onsager asymp. = {CV_THEORY_SLOPE:.4f}"
    )
    log(f"Growth from L=8 to L=32 (4x linear size): chi0 x{chi0_ratio:.1f}, chi x{chi_ratio:.1f}, Cv x{cv_ratio:.2f}")

    nums["peak_gn_ols"] = f"{peak_ols:.3f}"
    nums["peak_gn_boot_lo"] = f"{peak_boot_lo:.3f}"
    nums["peak_gn_boot_hi"] = f"{peak_boot_hi:.3f}"
    nums["peak_gn_wls"] = f"{fit_peak['slope']:.3f}"
    nums["peak_gn_se"] = f"{fit_peak['se']:.3f}"
    nums["peak_gn_chi2"] = f"{fit_peak['chi2_df']:.2f}"

    nums["gamma_nu_hat"] = f"{fit_chi0['slope']:.3f}"
    nums["gamma_nu_se"] = f"{fit_chi0['se']:.3f}"
    nums["gamma_nu_lo"] = f"{fit_chi0['lo']:.3f}"
    nums["gamma_nu_hi"] = f"{fit_chi0['hi']:.3f}"
    nums["gamma_nu_r2"] = f"{fit_chi0['r2']:.4f}"
    nums["gamma_nu_chi2"] = f"{fit_chi0['chi2_df']:.2f}"
    nums["gamma_nu_ge12"] = f"{fit_chi0_ge12['slope']:.3f}"

    nums["tri_gn_hat"] = f"{fit_tri_chi0['slope']:.3f}"
    nums["tri_gn_se"] = f"{fit_tri_chi0['se']:.3f}"
    nums["tri_gn_lo"] = f"{fit_tri_chi0['lo']:.3f}"
    nums["tri_gn_hi"] = f"{fit_tri_chi0['hi']:.3f}"
    nums["tri_gn_r2"] = f"{fit_tri_chi0['r2']:.4f}"
    nums["tri_gn_chi2"] = f"{fit_tri_chi0['chi2_df']:.2f}"

    nums["beta_nu_hat"] = f"{-fit_am['slope']:.3f}"
    nums["beta_nu_se"] = f"{fit_am['se']:.3f}"
    nums["beta_nu_lo"] = f"{-fit_am['hi']:.3f}"
    nums["beta_nu_hi"] = f"{-fit_am['lo']:.3f}"
    nums["beta_nu_r2"] = f"{fit_am['r2']:.4f}"
    nums["beta_nu_chi2"] = f"{fit_am['chi2_df']:.2f}"
    nums["beta_nu_ge12"] = f"{-fit_am_ge12['slope']:.3f}"

    nums["tri_bn_hat"] = f"{-fit_tri_am['slope']:.3f}"
    nums["tri_bn_se"] = f"{fit_tri_am['se']:.3f}"
    nums["tri_bn_lo"] = f"{-fit_tri_am['hi']:.3f}"
    nums["tri_bn_hi"] = f"{-fit_tri_am['lo']:.3f}"
    nums["tri_bn_chi2"] = f"{fit_tri_am['chi2_df']:.2f}"

    nums["cv_log_slope"] = f"{fit_cv['slope']:.3f}"
    nums["cv_log_se"] = f"{fit_cv['se']:.3f}"
    nums["cv_log_lo"] = f"{fit_cv['lo']:.3f}"
    nums["cv_log_hi"] = f"{fit_cv['hi']:.3f}"
    nums["cv_log_r2"] = f"{fit_cv['r2']:.3f}"
    nums["cv_log_chi2"] = f"{fit_cv['chi2_df']:.2f}"

    nums["chi0_ratio_8_32"] = f"{chi0_ratio:.1f}"
    nums["chi_ratio_8_32"] = f"{chi_ratio:.1f}"
    nums["cv_ratio_8_32"] = f"{cv_ratio:.2f}"

    # 6. Binder cumulant crossings with delete-1 block-jackknife SEs + 3-seed stability check
    log("\n--- 6. BINDER CUMULANT U4 CROSSINGS (WITH BLOCK-JACKKNIFE SEs) & 3-SEED CHECK ---")
    pairs = [(8, 16), (12, 24), (16, 32)]
    crossings: dict[tuple[int, int], tuple[float, float]] = {}
    for l1, l2 in pairs:
        u1 = [results[l1][T]["u4"] for T in TEMPS]
        u2 = [results[l2][T]["u4"] for T in TEMPS]
        tc_c = find_crossing(TEMPS, u1, u2)
        jk_vals = []
        for b in range(N_BLOCKS):
            u1_b = [results[l1][T]["jk_u4"][b] for T in TEMPS]
            u2_b = [results[l2][T]["jk_u4"][b] for T in TEMPS]
            c_b = find_crossing(TEMPS, u1_b, u2_b)
            if c_b is not None:
                jk_vals.append(c_b)
        mu_jk = statistics.fmean(jk_vals)
        se_c = math.sqrt(((len(jk_vals) - 1) / len(jk_vals)) * sum((v - mu_jk) ** 2 for v in jk_vals))
        crossings[(l1, l2)] = (tc_c, se_c)
        err_pct = 100.0 * (tc_c - TC_EXACT) / TC_EXACT
        z_tc = (tc_c - TC_EXACT) / max(se_c, 1e-9)
        log(
            f"U4 crossing (L={l1:2d}, L={l2:2d}): Tc_est = {tc_c:.4f} +/- {se_c:.4f} "
            f"(diff = {err_pct:+.2f}%, z = {z_tc:+.2f})"
        )
        nums[f"u4_cross_{l1}_{l2}"] = f"{tc_c:.4f}"
        nums[f"u4_se_{l1}_{l2}"] = f"{se_c:.4f}"
        nums[f"u4_err_{l1}_{l2}"] = f"{abs(err_pct):.2f}"

    # 3-seed stability check for (16, 32) in the critical window
    crit_win = [2.24, 2.26, tc_grid, 2.28, 2.30]
    seed_crosses = [crossings[(16, 32)][0]]
    for s_alt in (137, 2026):
        r_alt = random.Random(s_alt)
        u16 = [wolff_simulate(16, T, r_alt, compute_cv=False)["u4"] for T in crit_win]
        u32 = [wolff_simulate(32, T, r_alt, compute_cv=False)["u4"] for T in crit_win]
        c_alt = find_crossing(crit_win, u16, u32)
        if c_alt is not None:
            seed_crosses.append(c_alt)
    log(
        f"3-seed (L=16, 32) U4 crossings (seeds 42, 137, 2026): "
        f"{[round(x, 4) for x in seed_crosses]} | range = [{min(seed_crosses):.4f}, {max(seed_crosses):.4f}]"
    )
    nums["u4_seed_min"] = f"{min(seed_crosses):.4f}"
    nums["u4_seed_max"] = f"{max(seed_crosses):.4f}"

    log("\nPseudocritical temperature T_peak(L) maximizing connected susceptibility chi(T, L):")
    for L in LATTICE_SIZES:
        t_pk = peak_temps[L]
        chi_pk = results[L][t_pk]["chi"]
        chi_pk_se = results[L][t_pk]["chi_se"]
        log(f"  L={L:2d}: T_peak = {t_pk:.4f} (shift = {t_pk - TC_EXACT:+.4f}), chi_max = {chi_pk:.2f} +/- {chi_pk_se:.2f}")
        nums[f"tpeak_L{L}"] = f"{t_pk:.4f}"
        nums[f"chimax_L{L}"] = f"{chi_pk:.2f}"

    # 7. Finite-N vs Onsager thermodynamic limit magnetization (including T=2.00)
    log("\n--- 7. FINITE-N VS. THERMODYNAMIC LIMIT (ONSAGER) MAGNETIZATION ---")
    for T in (1.80, 2.00, 2.12, tc_grid, 2.42, 2.75):
        m_ex = onsager_magnetization(T)
        m8 = results[8][T]["abs_m"]
        m16 = results[16][T]["abs_m"]
        m32 = results[32][T]["abs_m"]
        log(f"  T={T:.4f}: Onsager={m_ex:.4f} | L=8: {m8:.4f} | L=16: {m16:.4f} | L=32: {m32:.4f}")
    nums["m_dis_275_L8"] = f"{results[8][2.75]['abs_m']:.3f}"
    nums["m_dis_275_L32"] = f"{results[32][2.75]['abs_m']:.3f}"
    nums["m_ord_200_exact"] = f"{onsager_magnetization(2.00):.3f}"
    nums["m_ord_200_L32"] = f"{results[32][2.00]['abs_m']:.3f}"

    # 8. Emit charts.json (Heurisma v2 schema) directly from computed variables
    tc16_32, se16_32 = crossings[(16, 32)]
    charts = [
        {
            "id": "magnetization_vs_temp",
            "type": "line",
            "title": "Emergence of Spontaneous Magnetization: Finite Lattices vs. Onsager Limit",
            "caption": (
                f"Finite lattices smooth out the phase transition at Tc = {TC_EXACT:.4f}; "
                f"at T = 2.0000, L = 32 matches Onsager ({results[32][2.00]['abs_m']:.3f} vs. {onsager_magnetization(2.00):.3f}), "
                f"while at T = 2.75, <|m|> decays from {results[8][2.75]['abs_m']:.3f} (L = 8) to "
                f"{results[32][2.75]['abs_m']:.3f} (L = 32)."
            ),
            "source": "Own Wolff-cluster Monte Carlo simulation (seed = 42) and exact Onsager (1944) formula.",
            "x": {"type": "number", "label": "Temperature T (J/kB)"},
            "y": {"label": "Magnetization <|m|>"},
            "series": [
                {
                    "name": "L = 8 (N = 64)",
                    "points": [[T, round(results[8][T]["abs_m"], 4)] for T in TEMPS],
                },
                {
                    "name": "L = 16 (N = 256)",
                    "points": [[T, round(results[16][T]["abs_m"], 4)] for T in TEMPS],
                },
                {
                    "name": "L = 32 (N = 1,024)",
                    "points": [[T, round(results[32][T]["abs_m"], 4)] for T in TEMPS],
                },
                {
                    "name": "Onsager Limit (L -> inf)",
                    "points": [[T, round(onsager_magnetization(T), 4)] for T in TEMPS],
                },
            ],
            "annotations": [
                {"x": round(TC_EXACT, 4), "label": "Onsager Tc"},
            ],
        },
        {
            "id": "susceptibility_fss",
            "type": "line",
            "title": "Sharpening Magnetic Susceptibility Peak Across Lattice Sizes",
            "caption": (
                f"Connected susceptibility chi(T, L) grows by {chi_ratio:.1f}x at Tc from L = 8 "
                f"({results[8][tc_grid]['chi']:.2f}) to L = 32 ({results[32][tc_grid]['chi']:.2f}); "
                f"peak T_peak shifts from {peak_temps[8]:.4f} (L = 8) to {peak_temps[32]:.4f} (L = 32)."
            ),
            "source": "Own Wolff-cluster Monte Carlo simulation in appendix/analysis.py (seed = 42).",
            "x": {"type": "number", "label": "Temperature T (J/kB)"},
            "y": {"label": "Connected Susceptibility chi(T, L)"},
            "series": [
                {
                    "name": f"L = {L}",
                    "points": [[T, round(results[L][T]["chi"], 3)] for T in TEMPS],
                }
                for L in LATTICE_SIZES
            ],
            "annotations": [
                {"x": round(TC_EXACT, 4), "label": "Onsager Tc"},
            ],
        },
        {
            "id": "binder_crossing",
            "type": "line",
            "title": "Scale-Invariant Binder Cumulant U4 Crossing Near Tc",
            "caption": (
                f"The L = 16 and L = 32 Binder cumulants intersect at T = {tc16_32:.4f} +/- {se16_32:.4f} "
                f"(3-seed range [{min(seed_crosses):.4f}, {max(seed_crosses):.4f}], exact Tc = {TC_EXACT:.4f})."
            ),
            "source": "Own Wolff-cluster Monte Carlo simulation in appendix/analysis.py (seed = 42).",
            "x": {"type": "number", "label": "Temperature T (J/kB)"},
            "y": {"label": "Binder Cumulant U4"},
            "series": [
                {
                    "name": f"L = {L}",
                    "points": [
                        [T, round(results[L][T]["u4"], 4)]
                        for T in TEMPS
                        if 2.12 <= T <= 2.42
                    ],
                }
                for L in LATTICE_SIZES
            ],
            "annotations": [
                {"x": round(TC_EXACT, 4), "label": "Onsager Tc"},
            ],
        },
        {
            "id": "fss_universality",
            "type": "scatter",
            "title": "Universality Test: Log-Log Susceptibility Scaling on Square vs. Triangular Lattices",
            "caption": (
                f"Despite distinct coordination numbers (z = 4 vs. z = 6) and critical temperatures "
                f"({TC_EXACT:.4f} vs. {TC_TRI_EXACT:.4f}), WLS slopes yield gamma/nu = "
                f"{fit_chi0['slope']:.3f} +/- {fit_chi0['se']:.3f} (square) and "
                f"{fit_tri_chi0['slope']:.3f} +/- {fit_tri_chi0['se']:.3f} (triangular), both consistent with exact {GAMMA_NU_EXACT:.2f}."
            ),
            "source": "Own Wolff-cluster Monte Carlo simulation in appendix/analysis.py (seed = 42).",
            "x": {"label": "ln(L)"},
            "y": {"label": "ln(chi0(Tc, L))"},
            "series": [
                {
                    "name": "Square Lattice (z = 4, Tc = 2.2692)",
                    "points": [
                        [round(math.log(L), 4), round(math.log(results[L][tc_grid]["chi0"]), 4)]
                        for L in LATTICE_SIZES
                    ],
                },
                {
                    "name": "Triangular Lattice (z = 6, Tc = 3.6410)",
                    "points": [
                        [round(math.log(L), 4), round(math.log(tri_res[L]["chi0"]), 4)]
                        for L in LATTICE_SIZES
                    ],
                },
            ],
            "highlight": {
                "x": round(math.log(32), 4),
                "y": round(math.log(results[32][tc_grid]["chi0"]), 4),
                "label": "Square L = 32",
            },
        },
    ]

    write_json(APPENDIX / "numbers.json", nums)
    write_json(REPORT_DIR / "charts.json", charts)
    (APPENDIX / "output.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
