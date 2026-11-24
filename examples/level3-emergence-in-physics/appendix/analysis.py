#!/usr/bin/env python3
"""Emergence in physics: finite-size scaling of nearest-neighbour Ising models (stdlib only).

Wolff single-cluster Monte Carlo [Wolff 1989] on a 1D chain (control), the 2D square lattice and the 2D
triangular lattice (J = 1, k_B = 1, periodic boundaries), plus majority-rule block-spin coarse-graining on
square lattices. Every random stream is seeded from its task label, so the run is bit-for-bit reproducible
whatever the number of worker processes.

Post-review version (after Reviewer #2, see report Section 5): 12 replicas with t(11) critical values,
interval-based Tc decisions, all Binder crossings listed, split-half seed-set robustness, slope drift with the
smallest size, a common ln(N) axis next to ln(linear size), peak-temperature extrapolation, specific heat,
integrated autocorrelation times, an equilibration drift check, a quantified |m| sharpening statistic, and
block-spin standard errors at two lattice sizes and at the finite-size pseudo-critical temperature.

Run from the report folder:  python3 -B appendix/analysis.py
Writes appendix/output.txt, appendix/numbers.json and charts.json directly.
"""

from __future__ import annotations

import json
import math
import os
import random
import statistics
from multiprocessing import Pool
from operator import itemgetter, mul
from pathlib import Path

APPENDIX = Path(__file__).resolve().parent
REPORT_DIR = APPENDIX.parent

# ----------------------------------------------------------------------------- exact reference values
TC_SQUARE = 2.0 / math.log(1.0 + math.sqrt(2.0))  # Onsager (1944)
TC_TRIANGULAR = 4.0 / math.log(3.0)  # exact triangular-lattice value (cited via Newell 1950)
GAMMA_OVER_NU = 7.0 / 4.0  # exact 2D Ising: gamma = 7/4, nu = 1

# ----------------------------------------------------------------------------- simulation design
SIZES_2D = [8, 12, 16, 24, 32]
SIZES_1D = [L * L for L in SIZES_2D]  # chain lengths matched in number of spins
N_REP = 12
N_EQ = 60
N_MEAS = 100
T_CRIT = 2.201  # two-sided 95 % Student t critical value with N_REP - 1 = 11 degrees of freedom
T_CRIT_HALF = 2.571  # same with 5 degrees of freedom (split-half seed sets of 6 replicas)
Z_POWER = 0.842  # one-sided normal quantile for 80 % power (minimum detectable difference)
TOL_TC = 0.02  # pre-registered relative tolerance on Tc
T_CRIT_OLS = 3.182  # two-sided 95 % t with 3 df (OLS slope SE from 5 sizes)
T_CRIT_RG = 3.182  # two-sided 95 % t with 3 df (4 block-spin replicas)
N_BOOT = 200  # replica bootstrap resamples for Binder crossings (crossing re-selected in each resample)
RG_EQ = 150
RG_CFG = 40
SHARP_EXP_FSS = 7.0 / 8.0  # (1 - beta) / nu with beta = 1/8, nu = 1 (2D Ising)


def grid(lo: float, hi: float, n: int) -> list[float]:
    return [round(lo + (hi - lo) * k / (n - 1), 6) for k in range(n)]


T_GRID = {
    "square": grid(2.15, 2.65, 21),
    "triangular": grid(3.45, 4.25, 21),
    "chain": grid(0.20, 1.20, 21),
}
TC_EXACT = {"square": TC_SQUARE, "triangular": TC_TRIANGULAR}
LABEL = {"square": "2D square", "triangular": "2D triangular", "chain": "1D chain (control)"}
SHORT = {"square": "sq", "triangular": "tri", "chain": "ch"}


# ----------------------------------------------------------------------------- lattices
def lattice(kind: str, L: int) -> tuple[list[tuple[int, ...]], list[tuple[int, ...]]]:
    """Return (all neighbours, forward neighbours) for each site; forward lists count every bond once."""
    if kind == "chain":
        return [((i + 1) % L, (i - 1) % L) for i in range(L)], [((i + 1) % L,) for i in range(L)]
    nbr, fwd = [], []
    for i in range(L * L):
        x, y = i % L, i // L

        def site(dx: int, dy: int) -> int:
            return ((y + dy) % L) * L + (x + dx) % L

        f = [site(1, 0), site(0, 1)]
        b = [site(-1, 0), site(0, -1)]
        if kind == "triangular":  # square lattice plus one diagonal = triangular topology (coordination 6)
            f.append(site(1, 1))
            b.append(site(-1, -1))
        nbr.append(tuple(f + b))
        fwd.append(tuple(f))
    return nbr, fwd


# ----------------------------------------------------------------------------- Wolff Monte Carlo
def wolff_sweep(s: list[int], nbr, p: float, rng: random.Random) -> None:
    """Flip Wolff clusters until at least N spins have been flipped (one 'sweep')."""
    n = len(s)
    rand = rng.random
    flipped = 0
    while flipped < n:
        i0 = rng.randrange(n)
        s0 = s[i0]
        s[i0] = -s0
        stack = [i0]
        c = 1
        while stack:
            i = stack.pop()
            for j in nbr[i]:
                if s[j] == s0 and rand() < p:
                    s[j] = -s0
                    stack.append(j)
                    c += 1
        flipped += c


def tau_int(series: list[float]) -> float:
    """Integrated autocorrelation time (in sweeps) with the automatic window W >= 6 tau (Sokal)."""
    n = len(series)
    mu = statistics.fmean(series)
    dev = [v - mu for v in series]
    c0 = sum(d * d for d in dev) / n
    if c0 <= 0:
        return 0.5
    tau = 0.5
    for t in range(1, n // 2):
        tau += sum(dev[i] * dev[i + t] for i in range(n - t)) / ((n - t) * c0)
        if t >= 6 * tau:
            break
    return max(tau, 0.5)


def simulate(task: tuple[str, int, float, int]) -> tuple[float, ...]:
    kind, L, T, rep = task
    nbr, fwd = lattice(kind, L)
    n = len(nbr)
    rng = random.Random(f"{kind}|{L}|{T:.6f}|{rep}")
    s = [1 if rng.random() < 0.5 else -1 for _ in range(n)]
    p = 1.0 - math.exp(-2.0 / T)
    getters = [itemgetter(*[f[d] for f in fwd]) for d in range(len(fwd[0]))]  # one getter per bond direction
    for _ in range(N_EQ):
        wolff_sweep(s, nbr, p, rng)
    ms, es = [], []
    for _ in range(N_MEAS):
        wolff_sweep(s, nbr, p, rng)
        ms.append(abs(sum(s)) / n)
        es.append(-sum(sum(map(mul, s, g(s))) for g in getters) / n)
    k = float(N_MEAS)
    a1 = sum(ms) / k
    a2 = sum(m * m for m in ms) / k
    a4 = sum(m ** 4 for m in ms) / k
    e1 = sum(es) / k
    e2 = sum(e * e for e in es) / k
    half = N_MEAS // 2
    drift = statistics.fmean(ms[:half]) - statistics.fmean(ms[half:])
    return a1, a2, a4, e1, e2, tau_int(ms), drift


def block_spin_task(task: tuple[int, str, float, int]) -> list[float]:
    """Majority-rule 3x3 blocking of square configurations; returns nn correlation per blocking level."""
    L, tag, T, rep = task
    nbr, _ = lattice("square", L)
    rng = random.Random(f"rg|{L}|{T:.6f}|{rep}")
    s = [1 if rng.random() < 0.5 else -1 for _ in range(L * L)]
    p = 1.0 - math.exp(-2.0 / T)
    for _ in range(RG_EQ):
        wolff_sweep(s, nbr, p, rng)
    n_levels = round(math.log(L, 3))  # 81 -> levels 81, 27, 9, 3 ; 27 -> 27, 9, 3
    acc = [0.0] * n_levels
    n_cfg = RG_CFG
    for _ in range(n_cfg):
        for _ in range(3):
            wolff_sweep(s, nbr, p, rng)
        conf, size = s[:], L
        for level in range(n_levels):
            tot = 0
            for y in range(size):
                row = y * size
                for x in range(size):
                    v = conf[row + x]
                    tot += v * conf[row + (x + 1) % size] + v * conf[((y + 1) % size) * size + x]
            acc[level] += tot / (2.0 * size * size)
            if level < n_levels - 1:
                nsz = size // 3
                new = []
                for by in range(nsz):
                    for bx in range(nsz):
                        t = 0
                        for dy in range(3):
                            base = (3 * by + dy) * size + 3 * bx
                            t += conf[base] + conf[base + 1] + conf[base + 2]
                        new.append(1 if t > 0 else -1)
                conf, size = new, nsz
    return [a / n_cfg for a in acc]


# ----------------------------------------------------------------------------- estimators
def derived(moms: list[tuple[float, ...]], n_spins: int, T: float) -> dict[str, float]:
    a1 = statistics.fmean(m[0] for m in moms)
    a2 = statistics.fmean(m[1] for m in moms)
    a4 = statistics.fmean(m[2] for m in moms)
    e1 = statistics.fmean(m[3] for m in moms)
    e2 = statistics.fmean(m[4] for m in moms)
    return {
        "m": a1,
        "chi": n_spins * (a2 - a1 * a1) / T,
        "U": 1.0 - a4 / (3.0 * a2 * a2),
        "C": n_spins * (e2 - e1 * e1) / (T * T),
    }


def peak(ts: list[float], ys: list[float]) -> tuple[float, float, bool]:
    """Parabola through the grid maximum and its neighbours; returns (T_peak, y_peak, interior)."""
    k = max(range(len(ys)), key=lambda i: ys[i])
    if k == 0 or k == len(ys) - 1:
        return ts[k], ys[k], False
    x0, x1, x2 = ts[k - 1], ts[k], ts[k + 1]
    y0, y1, y2 = ys[k - 1], ys[k], ys[k + 1]
    h = x1 - x0
    den = y0 - 2 * y1 + y2
    if den >= 0:
        return x1, y1, True
    d = 0.5 * h * (y0 - y2) / den
    return x1 + d, y1 - 0.25 * (y0 - y2) * d / h, True


def crossings(ts: list[float], ua: list[float], ub: list[float]) -> list[float]:
    """All temperatures where U_b - U_a (b = larger size) changes sign from + to - (linear interpolation)."""
    out = []
    for k in range(len(ts) - 1):
        d0, d1 = ub[k] - ua[k], ub[k + 1] - ua[k + 1]
        if d0 > 0 >= d1:
            out.append(ts[k] + (ts[k + 1] - ts[k]) * d0 / (d0 - d1))
    return out


def main_crossing(ts: list[float], ua: list[float], ub: list[float]) -> float | None:
    """The + to - crossing with the steepest change of U_b - U_a."""
    best, best_slope = None, -1.0
    for k in range(len(ts) - 1):
        d0, d1 = ub[k] - ua[k], ub[k + 1] - ua[k + 1]
        if d0 > 0 >= d1 and d0 - d1 > best_slope:
            best_slope = d0 - d1
            best = ts[k] + (ts[k + 1] - ts[k]) * d0 / (d0 - d1)
    return best


def ols(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Slope, intercept and OLS standard error of the slope."""
    n = len(xs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    se = math.sqrt(sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2) / sxx) if n > 2 else float("nan")
    return b, a, se


def jackknife_se(loo: list[float]) -> float:
    n = len(loo)
    mean = statistics.fmean(loo)
    return math.sqrt((n - 1) / n * sum((v - mean) ** 2 for v in loo))


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def analyse(kind: str, sizes: list[int], reps: list[int], results: dict, tcrit: float) -> dict:
    """Curves, peaks, slopes and Binder crossings for one lattice from a subset of replicas (jackknife SEs)."""
    ts = T_GRID[kind]
    full: dict[int, dict[str, list[float]]] = {}
    loo: list[dict[int, dict[str, list[float]]]] = [dict() for _ in reps]
    for L in sizes:
        n_spins = L if kind == "chain" else L * L
        f = {"m": [], "chi": [], "U": [], "C": []}
        lo = [{"m": [], "chi": [], "U": [], "C": []} for _ in reps]
        for T in ts:
            moms = [results[(kind, L, T, r)] for r in reps]
            d = derived(moms, n_spins, T)
            for key in f:
                f[key].append(d[key])
            for q in range(len(reps)):
                dl = derived(moms[:q] + moms[q + 1:], n_spins, T)
                for key in f:
                    lo[q][key].append(dl[key])
        full[L] = f
        for q in range(len(reps)):
            loo[q][L] = lo[q]
    nq = len(reps)
    peaks = {}
    for L in sizes:
        tp, cp, interior = peak(ts, full[L]["chi"])
        peaks[L] = (tp, cp, jackknife_se([peak(ts, loo[q][L]["chi"])[1] for q in range(nq)]), interior)
    lnL = [math.log(L) for L in sizes]
    slope, _, se_ols = ols(lnL, [math.log(peaks[L][1]) for L in sizes])
    se_jk = jackknife_se([ols(lnL, [math.log(peak(ts, loo[q][L]["chi"])[1]) for L in sizes])[0] for q in range(nq)])
    se = max(se_ols, se_jk)
    drift = {}
    for start in range(3):
        sub = sizes[start:]
        b, _, s_ols = ols([math.log(L) for L in sub], [math.log(peaks[L][1]) for L in sub])
        s_jk = jackknife_se([ols([math.log(L) for L in sub], [math.log(peak(ts, loo[q][L]["chi"])[1]) for L in sub])[0]
                             for q in range(nq)])
        drift[sub[0]] = (b, max(s_ols, s_jk))
    pairs = []
    for a, b in zip(sizes[:-1], sizes[1:]):
        allc = crossings(ts, full[a]["U"], full[b]["U"])
        mc = main_crossing(ts, full[a]["U"], full[b]["U"])
        mc_loo = [main_crossing(ts, loo[q][a]["U"], loo[q][b]["U"]) for q in range(nq)]
        mc_se = jackknife_se(mc_loo) if mc is not None and all(v is not None for v in mc_loo) else float("nan")
        adjacent, below, above = [], False, False
        for k in range(len(ts)):
            dk = full[b]["U"][k] - full[a]["U"][k]
            sk = jackknife_se([loo[q][b]["U"][k] - loo[q][a]["U"][k] for q in range(nq)])
            if mc is not None and ts[k] < mc and dk > tcrit * sk:
                below = True
            if mc is not None and ts[k] > mc and dk < -tcrit * sk:
                above = True
            if k < len(ts) - 1:
                d1 = full[b]["U"][k + 1] - full[a]["U"][k + 1]
                s1 = jackknife_se([loo[q][b]["U"][k + 1] - loo[q][a]["U"][k + 1] for q in range(nq)])
                if dk > tcrit * sk and -d1 > tcrit * s1:
                    adjacent.append(ts[k] + (ts[k + 1] - ts[k]) * dk / (dk - d1))
        pairs.append({"a": a, "b": b, "all": allc, "mc": mc, "mc_se": mc_se, "adjacent": adjacent,
                      "bracket": below and above})
    return {"full": full, "peaks": peaks, "slope": slope, "se_ols": se_ols, "se_jk": se_jk, "se": se,
            "drift": drift, "pairs": pairs, "n_bracket": sum(p["bracket"] for p in pairs),
            "n_adjacent": sum(1 for p in pairs if p["adjacent"])}


def tc_decision(est: float | None, se: float, exact: float, tcrit: float) -> str:
    if est is None or math.isnan(se):
        return "undecided (no crossing or no SE)"
    lo, hi = est - tcrit * se, est + tcrit * se
    if lo >= exact * (1 - TOL_TC) and hi <= exact * (1 + TOL_TC):
        return "pass (whole interval within tolerance)"
    if hi < exact * (1 - TOL_TC) or lo > exact * (1 + TOL_TC):
        return "fail (whole interval outside tolerance)"
    return "undecided (interval straddles the tolerance)"


def bootstrap_crossing(kind: str, a: int, b: int, results: dict) -> tuple[float, float, int]:
    """Replica bootstrap of the steepest crossing, re-selecting the crossing in every resample.
    Returns (bootstrap SE, fraction of resamples whose selected crossing lies in a different grid interval, n valid)."""
    ts = T_GRID[kind]
    rng = random.Random(f"boot|{kind}|{a}|{b}")
    def curve(L: int, reps: list[int]) -> list[float]:
        n_spins = L if kind == "chain" else L * L
        return [derived([results[(kind, L, T, r)] for r in reps], n_spins, T)["U"] for T in ts]
    full = list(range(N_REP))
    ref = main_crossing(ts, curve(a, full), curve(b, full))
    vals, moved = [], 0
    for _ in range(N_BOOT):
        reps = [rng.randrange(N_REP) for _ in range(N_REP)]
        c = main_crossing(ts, curve(a, reps), curve(b, reps))
        if c is None:
            moved += 1
            continue
        vals.append(c)
        if ref is not None and abs(c - ref) > (ts[1] - ts[0]):
            moved += 1
    se = statistics.stdev(vals) if len(vals) > 1 else float("nan")
    return se, moved / N_BOOT, len(vals)


# ----------------------------------------------------------------------------- main
def main() -> None:
    lines: list[str] = []
    num: dict[str, object] = {}

    def out(text: str = "") -> None:
        lines.append(text)

    tasks = []
    for kind, sizes in (("square", SIZES_2D), ("triangular", SIZES_2D), ("chain", SIZES_1D)):
        for L in sizes:
            for T in T_GRID[kind]:
                for r in range(N_REP):
                    tasks.append((kind, L, T, r))
    order = sorted(range(len(tasks)), key=lambda i: -(tasks[i][1] ** (2 if tasks[i][0] != "chain" else 1)))
    with Pool(processes=max(1, min(4, os.cpu_count() or 1))) as pool:
        res_sorted = pool.map(simulate, [tasks[i] for i in order], chunksize=4)
        results = {tasks[i]: res_sorted[k] for k, i in enumerate(order)}
        res = {kind: analyse(kind, sizes, list(range(N_REP)), results, T_CRIT)
               for kind, sizes in (("square", SIZES_2D), ("triangular", SIZES_2D), ("chain", SIZES_1D))}
        t_pc = round(res["square"]["pairs"][-1]["mc"], 6)  # finite-size pseudo-critical temperature (24,32)
        rg_specs = [(81, "lo", round(0.9 * TC_SQUARE, 6)), (81, "tc", round(TC_SQUARE, 6)),
                    (81, "hi", round(1.1 * TC_SQUARE, 6)), (81, "pc", t_pc), (27, "tc27", round(TC_SQUARE, 6))]
        rg_tasks = [(L, tag, T, r) for (L, tag, T) in rg_specs for r in range(4)]
        rg_res = pool.map(block_spin_task, rg_tasks, chunksize=1)

    out("EMERGENCE IN PHYSICS - FINITE-SIZE SCALING OF NEAREST-NEIGHBOUR ISING MODELS (post-review version)")
    out("Wolff single-cluster Monte Carlo, J = 1, k_B = 1, periodic boundaries; stdlib-only Python.")
    out(f"Replicas per (lattice, L, T): {N_REP}; equilibration sweeps: {N_EQ}; measurement sweeps: {N_MEAS}.")
    out(f"Decision rules use Student t critical values: {T_CRIT} (11 df, all replicas) and {T_CRIT_HALF} (5 df, split halves).")
    out(f"Temperature grid points per lattice: {len(T_GRID['square'])}; block-spin equilibration sweeps: {RG_EQ}; "
        f"block-spin configurations per replica: {RG_CFG}; replica bootstrap resamples: {N_BOOT}")
    out("Files read by this script from appendix/data/: none (all numbers are generated by the simulation).")
    out(f"Exact Tc square (Onsager) = {TC_SQUARE:.6f}; exact Tc triangular = {TC_TRIANGULAR:.6f}; exact gamma/nu = {GAMMA_OVER_NU:.4f}")
    out()
    num.update({"n_rep": N_REP, "n_meas": N_MEAS, "n_eq": N_EQ, "t_crit": f"{T_CRIT:.3f}",
                "tc_sq_exact": f"{TC_SQUARE:.4f}", "tc_tri_exact": f"{TC_TRIANGULAR:.4f}", "gnu_exact": f"{GAMMA_OVER_NU:.2f}"})

    for kind, sizes in (("square", SIZES_2D), ("triangular", SIZES_2D), ("chain", SIZES_1D)):
        r, ts, key = res[kind], T_GRID[kind], SHORT[kind]
        out(f"=== {LABEL[kind]} ===")
        out("size  T_peak(chi)  chi_max   chi_max_SE  T_peak(C)  C_max   U4(T_grid_min)  U4(T_grid_max)")
        for L in sizes:
            tp, cp, se, _ = r["peaks"][L]
            tpc, cmax, _ = peak(ts, r["full"][L]["C"])
            out(f"{L:5d}  {tp:10.4f}  {cp:9.3f}  {se:9.3f}  {tpc:9.4f}  {cmax:7.3f}  {r['full'][L]['U'][0]:14.4f}  {r['full'][L]['U'][-1]:14.4f}")
            num[f"chimax_{key}_{L}"] = f"{cp:.2f}"
            num[f"chimax_{key}_{L}_se"] = f"{se:.2f}"
            num[f"tpeak_{key}_{L}"] = f"{tp:.3f}"
            num[f"cmax_{key}_{L}"] = f"{cmax:.3f}"
            num[f"tpeakc_{key}_{L}"] = f"{tpc:.3f}"
        out(f"log-log fit ln(chi_max) vs ln(linear size), all sizes: slope = {r['slope']:.4f}, OLS SE = {r['se_ols']:.4f}, "
            f"jackknife SE = {r['se_jk']:.4f}")
        for lmin, (b, s) in r["drift"].items():
            out(f"  slope with smallest size {lmin}: {b:.4f} +/- {s:.4f}")
            num[f"gnu_{key}_min{lmin}"] = f"{b:.3f}"
            num[f"gnu_{key}_min{lmin}_se"] = f"{s:.3f}"
        n_axis = 1.0 if kind == "chain" else 2.0
        out(f"slope against ln(number of spins N): {r['slope'] / n_axis:.4f} +/- {r['se'] / n_axis:.4f}")
        num[f"gnuN_{key}"] = f"{r['slope'] / n_axis:.3f}"
        num[f"gnuN_{key}_se"] = f"{r['se'] / n_axis:.3f}"
        if kind != "chain":
            z = (r["slope"] - GAMMA_OVER_NU) / r["se"]
            t_use = T_CRIT_OLS if r["se_ols"] >= r["se_jk"] else T_CRIT
            r["t_use"] = t_use
            out(f"deviation from exact gamma/nu: {r['slope'] - GAMMA_OVER_NU:+.4f} (z = {z:+.2f}; df-matched t = {t_use} -> "
                f"pass {abs(z) <= t_use}; sealed 2*SE rule -> pass {abs(z) <= 2.0})")
            num[f"t_use_{key}"] = f"{t_use:.3f}"
            num[f"gnu_{key}_sealed"] = "pass" if abs(z) <= 2.0 else "fail"
            num[f"z_{key}"] = f"{z:+.2f}"
            r["z"] = z
        num[f"gnu_{key}"] = f"{r['slope']:.3f}"
        num[f"gnu_{key}_se"] = f"{r['se']:.3f}"

        # peak-temperature extrapolation: 2D T_peak = T_inf + a / L (nu = 1); 1D T_peak = T_inf + a / ln N
        xs = [1.0 / L for L in sizes] if kind != "chain" else [1.0 / math.log(L) for L in sizes]
        b, t_inf, s_b = ols(xs, [r["peaks"][L][0] for L in sizes])
        mx = statistics.fmean(xs)
        resid = [r["peaks"][L][0] - t_inf - b * x for L, x in zip(sizes, xs)]
        s_int = math.sqrt(sum(e * e for e in resid) / (len(xs) - 2) * (1.0 / len(xs) + mx * mx / sum((x - mx) ** 2 for x in xs)))
        var = "1/L" if kind != "chain" else "1/ln N"
        out(f"exploratory: susceptibility-peak temperature extrapolated linearly in {var} to infinite size: "
            f"T_inf = {t_inf:.4f} +/- {s_int:.4f} (OLS)")
        num[f"tinf_{key}"] = f"{t_inf:.3f}"
        num[f"tinf_{key}_se"] = f"{s_int:.3f}"
        if kind == "chain":
            for name, fx in (("lnN", lambda L: 1.0 / math.log(L)), ("sqrtN", lambda L: 1.0 / math.sqrt(L)), ("N", lambda L: 1.0 / L)):
                xs2 = [fx(L) for L in sizes]
                ys2 = [r["peaks"][L][0] for L in sizes]
                b2, a2, _ = ols(xs2, ys2)
                m2 = statistics.fmean(xs2)
                rss = sum((y - a2 - b2 * x) ** 2 for x, y in zip(xs2, ys2))
                se2 = math.sqrt(rss / (len(xs2) - 2) * (1.0 / len(xs2) + m2 * m2 / sum((x - m2) ** 2 for x in xs2)))
                out(f"  1D peak-temperature extrapolation against {name}: T_inf = {a2:.4f} +/- {se2:.4f}, residual sum of squares = {rss:.2e}")
                num[f"tinf_ch_{name}"] = f"{a2:.3f}"
                num[f"tinf_ch_{name}_se"] = f"{se2:.3f}"
                num[f"rss_ch_{name}"] = f"{rss:.2e}"

        out(f"Binder cumulant crossings (adjacent sizes; all + to - sign changes of U_large - U_small):")
        for p in r["pairs"]:
            allc = ", ".join(f"{v:.4f}" for v in p["all"]) if p["all"] else "none"
            mc = "none" if p["mc"] is None else (f"{p['mc']:.4f} +/- n/a" if math.isnan(p["mc_se"]) else f"{p['mc']:.4f} +/- {p['mc_se']:.4f}")
            out(f"  ({p['a']},{p['b']}): all crossings = {allc}; steepest = {mc}; "
                f"adjacent-point rule = {'yes' if p['adjacent'] else 'no'}; bracket rule = {p['bracket']}")
            if kind != "chain" and p["mc"] is not None:
                bse, moved, nval = bootstrap_crossing(kind, p["a"], p["b"], results)
                dec_t = tc_decision(p["mc"], bse, TC_EXACT[kind], T_CRIT).split(" (")[0]
                dec_2 = tc_decision(p["mc"], bse, TC_EXACT[kind], 2.0).split(" (")[0]
                relp = 100 * (p["mc"] - TC_EXACT[kind]) / TC_EXACT[kind]
                out(f"      bootstrap SE = {bse:.4f} ({nval} valid resamples; crossing moved to another grid interval or vanished in "
                    f"{100 * moved:.0f} % of resamples); rel. error {relp:+.2f} %; decision with t: {dec_t}; with sealed 2*SE: {dec_2}")
                num[f"cross_{key}_{p['a']}_{p['b']}_bse"] = f"{bse:.4f}"
                num[f"cross_{key}_{p['a']}_{p['b']}_moved"] = f"{100 * moved:.0f}"
                num[f"cross_{key}_{p['a']}_{p['b']}_rel"] = f"{relp:+.2f}"
                num[f"cross_{key}_{p['a']}_{p['b']}_dec"] = dec_t
                num[f"cross_{key}_{p['a']}_{p['b']}_dec2"] = dec_2
                p["bse"], p["dec_t"], p["dec_2"] = bse, dec_t, dec_2
            if kind != "chain":
                num[f"cross_{key}_{p['a']}_{p['b']}"] = f"{p['mc']:.4f}" if p["mc"] is not None else "none"
                num[f"cross_{key}_{p['a']}_{p['b']}_se"] = "n/a" if math.isnan(p["mc_se"]) else f"{p['mc_se']:.4f}"
                num[f"ncross_{key}_{p['a']}_{p['b']}"] = len(p["all"])
        out(f"pairs passing the adjacent-point rule: {r['n_adjacent']}; pairs passing the bracket rule: {r['n_bracket']} of {len(sizes) - 1}")
        num[f"nbracket_{key}"] = r["n_bracket"]
        num[f"nadjacent_{key}"] = r["n_adjacent"]

        # autocorrelation and equilibration diagnostics
        taus = [results[(kind, L, T, q)][5] for L in sizes for T in ts for q in range(N_REP)]
        n_drift = 0
        for L in sizes:
            for T in ts:
                dr = [results[(kind, L, T, q)][6] for q in range(N_REP)]
                mean_dr = statistics.fmean(dr)
                se_dr = statistics.stdev(dr) / math.sqrt(N_REP)
                if se_dr > 0 and abs(mean_dr) > T_CRIT * se_dr:
                    n_drift += 1
        n_pts = len(sizes) * len(ts)
        out(f"integrated autocorrelation time of |m| (sweeps): median {statistics.median(taus):.2f}, max {max(taus):.2f}")
        out(f"equilibration check: (lattice, L, T) points whose first-half vs second-half mean |m| differs by > t*SE: {n_drift} of {n_pts}")
        num[f"tau_med_{key}"] = f"{statistics.median(taus):.2f}"
        num[f"tau_max_{key}"] = f"{max(taus):.2f}"
        num[f"ndrift_{key}"] = n_drift
        num[f"npts_{key}"] = n_pts

        if kind in TC_EXACT:
            last = r["pairs"][-1]
            rel = (last["mc"] - TC_EXACT[kind]) / TC_EXACT[kind]
            dec = tc_decision(last["mc"], last["mc_se"], TC_EXACT[kind], T_CRIT)
            valid = [p["mc"] for p in r["pairs"] if p["mc"] is not None]
            mean_c = statistics.fmean(valid)
            rel_mean = (mean_c - TC_EXACT[kind]) / TC_EXACT[kind]
            spread = max(valid) - min(valid)
            out(f"largest-pair crossing (24,32) = {last['mc']:.4f} +/- {last['mc_se']:.4f}; exact Tc = {TC_EXACT[kind]:.4f}; "
                f"relative error = {100 * rel:+.2f} %; interval decision (est +/- t*SE vs +/-2 %): {dec}")
            out(f"mean of the {len(valid)} steepest pair crossings = {mean_c:.4f} (relative error {100 * rel_mean:+.2f} %); "
                f"spread = {spread:.4f} ({100 * spread / TC_EXACT[kind]:.1f} % of exact Tc)")
            num.update({f"tc_{key}_est": f"{last['mc']:.4f}", f"tc_{key}_se": f"{last['mc_se']:.4f}",
                        f"tc_{key}_rel": f"{100 * rel:+.2f}", f"tc_{key}_absrel": f"{100 * abs(rel):.2f}",
                        f"tc_{key}_relse": f"{100 * last['mc_se'] / TC_EXACT[kind]:.2f}",
                        f"tc_{key}_decision": dec.split(" (")[0], f"tc_{key}_mean": f"{mean_c:.4f}",
                        f"tc_{key}_mean_rel": f"{100 * rel_mean:+.2f}", f"tc_{key}_spread": f"{spread:.4f}",
                        f"tc_{key}_spread_pct": f"{100 * spread / TC_EXACT[kind]:.1f}"})
            r.update({"rel": rel, "dec": dec})
            # quantified order-parameter sharpening: max |d|m|/dT| per size (finite differences)
            sharp = []
            for L in sizes:
                mv = r["full"][L]["m"]
                sharp.append(max(abs(mv[k + 1] - mv[k]) / (ts[k + 1] - ts[k]) for k in range(len(ts) - 1)))
            sb, _, sse = ols([math.log(L) for L in sizes], [math.log(v) for v in sharp])
            out("max |d<|m|>/dT| per size: " + ", ".join(f"L={L}: {v:.3f}" for L, v in zip(sizes, sharp))
                + f"; log-log growth exponent = {sb:.3f} +/- {sse:.3f} (OLS)")
            num[f"msharp_{key}_8"] = f"{sharp[0]:.3f}"
            num[f"msharp_{key}_32"] = f"{sharp[-1]:.3f}"
            num[f"msharp_{key}_exp"] = f"{sb:.3f}"
            num[f"msharp_{key}_exp_se"] = f"{sse:.3f}"
            zs = (sb - SHARP_EXP_FSS) / sse
            out(f"  finite-size-scaling prediction for this exponent (1 - beta)/nu = {SHARP_EXP_FSS:.3f}; z = {zs:+.1f} "
                f"(the finite-difference statistic on a fixed temperature grid is biased; not used as evidence)")
            num[f"msharp_{key}_z"] = f"{zs:+.1f}"
            num["msharp_fss"] = f"{SHARP_EXP_FSS:.3f}"
            kc = min(range(len(ts)), key=lambda k: abs(ts[k] - TC_EXACT[kind]))
            taus_c = [statistics.fmean(results[(kind, L, ts[kc], q)][5] for q in range(N_REP)) for L in sizes]
            out(f"  mean tau_int of |m| at T = {ts[kc]:.4f} (grid point nearest Tc) by size: "
                + ", ".join(f"L={L}: {v:.2f}" for L, v in zip(sizes, taus_c)))
            for L, v in zip(sizes, taus_c):
                num[f"tauc_{key}_{L}"] = f"{v:.2f}"
            cm = [peak(ts, r["full"][L]["C"])[1] for L in sizes]
            lnl = [math.log(L) for L in sizes]
            b_log, a_log, _ = ols(lnl, cm)
            rss_log = sum((c - a_log - b_log * x) ** 2 for x, c in zip(lnl, cm))
            b_pow, a_pow, _ = ols(lnl, [math.log(c) for c in cm])
            rss_pow = sum((c - math.exp(a_pow + b_pow * x)) ** 2 for x, c in zip(lnl, cm))
            out(f"  C_max fits: C = a + b ln L with b = {b_log:.3f}, RSS = {rss_log:.2e}; C = a L^x with x = {b_pow:.3f}, RSS = {rss_pow:.2e}")
            num[f"cfit_{key}_b"] = f"{b_log:.3f}"
            num[f"cfit_{key}_rsslog"] = f"{rss_log:.2e}"
            num[f"cfit_{key}_x"] = f"{b_pow:.3f}"
            num[f"cfit_{key}_rsspow"] = f"{rss_pow:.2e}"
            if kind == "triangular":
                kp = max(range(len(ts)), key=lambda k: r["full"][32]["chi"][k])
                chis = []
                for q in range(N_REP):
                    a1, a2 = results[(kind, 32, ts[kp], q)][0], results[(kind, 32, ts[kp], q)][1]
                    chis.append(32 * 32 * (a2 - a1 * a1) / ts[kp])
                out(f"  triangular L=32 per-replica chi at grid peak T = {ts[kp]:.4f}: " + ", ".join(f"{v:.2f}" for v in chis))
                med = statistics.median(chis)
                mad = statistics.median(abs(v - med) for v in chis)
                n_out = sum(1 for v in chis if mad > 0 and abs(v - med) > 3 * mad / 0.6745)
                out(f"  replicas beyond median +/- 3 MAD/0.6745: {n_out}")
                num["chi_tri32_nout"] = n_out
        out()

    sq, tr, ch = res["square"], res["triangular"], res["chain"]
    diff = sq["slope"] - tr["slope"]
    diff_se = math.sqrt(sq["se"] ** 2 + tr["se"] ** 2)
    t_mdd = max(sq.get('t_use', T_CRIT), tr.get('t_use', T_CRIT))
    mdd = (t_mdd + Z_POWER) * diff_se
    out("=== Universality and control comparison ===")
    out(f"square minus triangular slope = {diff:+.4f} +/- {diff_se:.4f} (z = {diff / diff_se:+.2f}); "
        f"minimum detectable difference at 80 % power = {mdd:.4f}")
    out(f"against ln(linear size): 1D control slope = {ch['slope']:.4f} +/- {ch['se']:.4f}; square minus 1D = {sq['slope'] - ch['slope']:+.4f}")
    out(f"against ln(N spins): square {sq['slope'] / 2:.4f}, triangular {tr['slope'] / 2:.4f}, 1D {ch['slope']:.4f} "
        f"(the chain's chi_max grows faster per spin; the exponent comparison depends on the size variable)")
    num.update({"slope_diff_sq_tri": f"{diff:+.3f}", "slope_diff_sq_tri_se": f"{diff_se:.3f}",
                "z_diff_sq_tri": f"{diff / diff_se:+.2f}", "mdd_sq_tri": f"{mdd:.3f}"})
    out()

    # split-half seed-set robustness
    out("=== Split-half seed-set robustness (replicas 0-5 vs 6-11, t critical value with 5 df) ===")
    for h, reps in (("A", list(range(0, 6))), ("B", list(range(6, 12)))):
        for kind in ("square", "triangular"):
            a = analyse(kind, SIZES_2D, reps, results, T_CRIT_HALF)
            last = a["pairs"][-1]
            z = (a["slope"] - GAMMA_OVER_NU) / a["se"]
            dec = tc_decision(last["mc"], last["mc_se"], TC_EXACT[kind], T_CRIT_HALF)
            mc_txt = "none" if last["mc"] is None else f"{last['mc']:.4f}"
            out(f"half {h}, {LABEL[kind]}: slope = {a['slope']:.4f} +/- {a['se']:.4f} (z = {z:+.2f}); crossing (24,32) = {mc_txt}; "
                f"Tc decision: {dec.split(' (')[0]}; bracketed pairs = {a['n_bracket']}")
            num[f"half{h}_{SHORT[kind]}_gnu"] = f"{a['slope']:.3f}"
            num[f"half{h}_{SHORT[kind]}_z"] = f"{z:+.2f}"
            num[f"half{h}_{SHORT[kind]}_cross"] = mc_txt
            num[f"half{h}_{SHORT[kind]}_dec"] = dec.split(" (")[0]
            num[f"half{h}_{SHORT[kind]}_nbracket"] = a["n_bracket"]
        a = analyse("chain", SIZES_1D, reps, results, T_CRIT_HALF)
        out(f"half {h}, {LABEL['chain']}: bracketed pairs = {a['n_bracket']}")
        num[f"half{h}_ch_nbracket"] = a["n_bracket"]
    out()

    # RG flow
    out("=== Majority-rule 3x3 block-spin coarse-graining (mean +/- SE over 4 replicas x 40 configurations) ===")
    rg = {}
    for (L, tag, T) in rg_specs:
        reps = [rg_res[k] for k, task in enumerate(rg_tasks) if task[0] == L and task[1] == tag]
        nl = len(reps[0])
        mean = [statistics.fmean(rr[lv] for rr in reps) for lv in range(nl)]
        se = [statistics.stdev([rr[lv] for rr in reps]) / math.sqrt(len(reps)) for lv in range(nl)]
        ch02 = [rr[2] - rr[0] for rr in reps]
        rg[tag] = (L, T, mean, se, statistics.fmean(ch02), statistics.stdev(ch02) / math.sqrt(len(reps)))
        out(f"L = {L}, T = {T:.4f} (T/Tc = {T / TC_SQUARE:.3f}): " + ", ".join(f"level {lv}: {m:.4f} +/- {s:.4f}" for lv, (m, s) in enumerate(zip(mean, se)))
            + f"; change level 0 -> 2 = {rg[tag][4]:+.4f} +/- {rg[tag][5]:.4f}")
        for lv in range(nl):
            num[f"rg_{tag}_{lv}"] = f"{mean[lv]:.3f}"
            num[f"rg_{tag}_{lv}_se"] = f"{se[lv]:.3f}"
        num[f"rg_{tag}_change"] = f"{rg[tag][4]:+.3f}"
        num[f"rg_{tag}_change_se"] = f"{rg[tag][5]:.3f}"
    num["t_pc"] = f"{t_pc:.4f}"
    reps81 = [rg_res[k] for k, task in enumerate(rg_tasks) if task[0] == 81 and task[1] == "tc"]
    reps27 = [rg_res[k] for k, task in enumerate(rg_tasks) if task[0] == 27 and task[1] == "tc27"]
    d = rg["tc27"][4] - rg["tc"][4]
    s_d = math.sqrt(rg["tc27"][5] ** 2 + rg["tc"][5] ** 2)
    out(f"L = 27 minus L = 81 drift (level 0 -> 2) at Tc = {d:+.4f} +/- {s_d:.4f} (z = {d / s_d:+.2f}; t(3) = {T_CRIT_RG} -> "
        f"detectable {abs(d / s_d) > T_CRIT_RG})")
    st81 = [rr[2] - rr[1] for rr in reps81]
    st27 = [rr[1] - rr[0] for rr in reps27]
    m81, m27 = statistics.fmean(st81), statistics.fmean(st27)
    s81, s27 = statistics.stdev(st81) / 2.0, statistics.stdev(st27) / 2.0
    out(f"one blocking step ending on a 9 x 9 block lattice at Tc: from L = 81 (27 -> 9) {m81:+.4f} +/- {s81:.4f}; "
        f"from L = 27 (27 -> 9) {m27:+.4f} +/- {s27:.4f}")
    num.update({"rg_diff_27_81": f"{d:+.3f}", "rg_diff_27_81_se": f"{s_d:.3f}", "rg_diff_27_81_z": f"{d / s_d:+.2f}",
                "rg_step81": f"{m81:+.3f}", "rg_step81_se": f"{s81:.3f}", "rg_step27": f"{m27:+.3f}", "rg_step27_se": f"{s27:.3f}",
                "t_crit_rg": f"{T_CRIT_RG:.3f}", "n_grid": len(T_GRID["square"]), "rg_eq": RG_EQ, "rg_cfg": RG_CFG, "n_boot": N_BOOT})
    out()

    out("=== Decision summary (operational criteria written after sealing; see report Section 2) ===")
    for kind in ("square", "triangular"):
        r = res[kind]
        out(f"{LABEL[kind]}: Tc interval decision = {r['dec']}; |z(gamma/nu)| <= {T_CRIT} -> {abs(r['z']) <= T_CRIT}")
    out(f"universality: |z(square - triangular)| <= {T_CRIT} -> {abs(diff / diff_se) <= T_CRIT} (not an equivalence test; MDD = {mdd:.4f})")
    out(f"bracketed Binder crossings (of 4 pairs, post-hoc rule): square {sq['n_bracket']}, triangular {tr['n_bracket']}, 1D {ch['n_bracket']}")
    out(f"adjacent-point rule (of 4 pairs): square {sq['n_adjacent']}, triangular {tr['n_adjacent']}, 1D {ch['n_adjacent']}")
    out(f"RG clause at Tc (L = 81): change level 0 -> 2 = {rg['tc'][4]:+.4f} +/- {rg['tc'][5]:.4f}; "
        f"at pseudo-critical T = {t_pc:.4f}: {rg['pc'][4]:+.4f} +/- {rg['pc'][5]:.4f}")

    # ---------------------------------------------------------------- charts.json
    charts = []
    for kind in ("square", "triangular"):
        r = res[kind]
        last = r["pairs"][-1]
        charts.append({
            "id": f"binder_{kind}",
            "type": "line",
            "title": f"Binder cumulant U4 vs temperature, {LABEL[kind]} lattice, L = {SIZES_2D[0]}-{SIZES_2D[-1]}",
            "caption": (f"Largest-pair crossing at T = {last['mc']:.4f} ± {last['mc_se']:.4f}, {100 * r['rel']:+.2f} % from the exact "
                        f"Tc = {TC_EXACT[kind]:.4f}; mean of {N_REP} independent replicas per point."),
            "source": "Own Wolff Monte Carlo in appendix/analysis.py; exact Tc from the literature cited in Section 4.",
            "x": {"label": "Temperature T (J/k_B)"},
            "y": {"label": "Binder cumulant U4"},
            "series": [{"name": f"L = {L}", "points": [[t, round(u, 5)] for t, u in zip(T_GRID[kind], r["full"][L]["U"])]}
                       for L in SIZES_2D],
        })
    charts.append({
        "id": "binder_chain",
        "type": "line",
        "title": "Binder cumulant U4 vs temperature, 1D chain control (N = 64-1024)",
        "caption": (f"Under the post-hoc bracket rule {ch['n_bracket']} of 4 adjacent pairs show a crossing; all chains approach "
                    f"full order (U4 = 2/3) as T goes to 0, the chain's zero-temperature critical point."),
        "source": "Own Wolff Monte Carlo in appendix/analysis.py.",
        "x": {"label": "Temperature T (J/k_B)"},
        "y": {"label": "Binder cumulant U4"},
        "series": [{"name": f"N = {L}", "points": [[t, round(u, 5)] for t, u in zip(T_GRID["chain"], ch["full"][L]["U"])]}
                   for L in SIZES_1D],
    })
    charts.append({
        "id": "chi_scaling",
        "type": "line",
        "title": "Finite-size scaling of the susceptibility peak (log-log, linear size)",
        "caption": (f"Slopes against ln(linear size): square {sq['slope']:.3f} ± {sq['se']:.3f}, triangular {tr['slope']:.3f} ± {tr['se']:.3f}, "
                    f"1D control {ch['slope']:.3f} ± {ch['se']:.3f}; exact 2D Ising gamma/nu = {GAMMA_OVER_NU:.2f}. "
                    f"Linear size is L for the 2D lattices and N for the chain; against ln(N spins) the ordering reverses."),
        "source": "Own Wolff Monte Carlo in appendix/analysis.py.",
        "x": {"label": "ln(linear size)"},
        "y": {"label": "ln(chi_max)"},
        "series": [
            {"name": LABEL["square"], "points": [[round(math.log(L), 5), round(math.log(sq["peaks"][L][1]), 5)] for L in SIZES_2D]},
            {"name": LABEL["triangular"], "points": [[round(math.log(L), 5), round(math.log(tr["peaks"][L][1]), 5)] for L in SIZES_2D]},
            {"name": LABEL["chain"], "points": [[round(math.log(L), 5), round(math.log(ch["peaks"][L][1]), 5)] for L in SIZES_1D]},
        ],
    })
    charts.append({
        "id": "tpeak_extrapolation",
        "type": "line",
        "title": "Susceptibility-peak temperature vs inverse size",
        "caption": (f"Exploratory linear extrapolation: square T_inf = {float(num['tinf_sq']):.3f} (exact {TC_SQUARE:.4f}), "
                    f"triangular T_inf = {float(num['tinf_tri']):.3f} (exact {TC_TRIANGULAR:.4f}); x is 1/L in 2D."),
        "source": "Own Wolff Monte Carlo in appendix/analysis.py.",
        "x": {"label": "1/L"},
        "y": {"label": "T at susceptibility peak (J/k_B)"},
        "series": [
            {"name": LABEL["square"], "points": [[round(1.0 / L, 5), round(sq["peaks"][L][0], 5)] for L in SIZES_2D]},
            {"name": LABEL["triangular"], "points": [[round(1.0 / L, 5), round(tr["peaks"][L][0], 5)] for L in SIZES_2D]},
        ],
        "reference_lines": [{"name": "Exact Tc square", "value": round(TC_SQUARE, 4)},
                            {"name": "Exact Tc triangular", "value": round(TC_TRIANGULAR, 4)}],
    })
    charts.append({
        "id": "magnetization_square",
        "type": "line",
        "title": "Order parameter |m| vs temperature, 2D square lattice",
        "caption": (f"The steepest slope of |m| grows from {float(num['msharp_sq_8']):.3f} (L = 8) to {float(num['msharp_sq_32']):.3f} (L = 32) "
                    f"per unit temperature; exact Tc = {TC_SQUARE:.4f}."),
        "source": "Own Wolff Monte Carlo in appendix/analysis.py.",
        "x": {"label": "Temperature T (J/k_B)"},
        "y": {"label": "Mean |m| per spin"},
        "series": [{"name": f"L = {L}", "points": [[t, round(v, 5)] for t, v in zip(T_GRID["square"], sq["full"][L]["m"])]}
                   for L in SIZES_2D],
    })
    charts.append({
        "id": "rg_flow",
        "type": "line",
        "title": "Block-spin coarse-graining flow, square lattice L = 81",
        "caption": (f"Change of the nearest-neighbour block correlation from level 0 to 2: {rg['lo'][4]:+.3f} at T = 0.9 Tc, "
                    f"{rg['tc'][4]:+.3f} ± {rg['tc'][5]:.3f} at Tc, {rg['pc'][4]:+.3f} ± {rg['pc'][5]:.3f} at the pseudo-critical "
                    f"T = {t_pc:.4f}, and {rg['hi'][4]:+.3f} at T = 1.1 Tc."),
        "source": "Own majority-rule 3x3 blocking of Wolff configurations in appendix/analysis.py.",
        "x": {"label": "Blocking level (0 = microscopic spins)"},
        "y": {"label": "Nearest-neighbour correlation"},
        "series": [
            {"name": "T = 0.9 Tc", "points": [[lv, round(v, 5)] for lv, v in enumerate(rg["lo"][2])]},
            {"name": "T = Tc", "points": [[lv, round(v, 5)] for lv, v in enumerate(rg["tc"][2])]},
            {"name": "T pseudo-critical", "points": [[lv, round(v, 5)] for lv, v in enumerate(rg["pc"][2])]},
            {"name": "T = 1.1 Tc", "points": [[lv, round(v, 5)] for lv, v in enumerate(rg["hi"][2])]},
        ],
    })

    (APPENDIX / "output.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(APPENDIX / "numbers.json", num)
    write_json(REPORT_DIR / "charts.json", charts)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
