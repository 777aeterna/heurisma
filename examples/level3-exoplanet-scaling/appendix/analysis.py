#!/usr/bin/env python3
"""Reproducible analysis of Keplerian two-body scaling and exoplanet mass-radius regimes.

Reads only sealed data and conjecture artifacts under study/appendix/ and emits:
  - stdout -> study/appendix/output.txt
  - study/appendix/numbers.json
  - study/charts.json (v2 schema)
"""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Sequence

APPENDIX = Path(__file__).resolve().parent
STUDY_DIR = APPENDIX.parent
if str(APPENDIX) not in sys.path:
    sys.path.insert(0, str(APPENDIX))

from local_data import read_table  # noqa: E402

TWO_PI = 2.0 * math.pi
FOUR_PI_SQ = 4.0 * math.pi * math.pi
DAY_S = 86400.0
AU_M = 1.495978707e11
R_SUN_M = 6.957e8
GM_SUN = 1.3271244e20
M_EARTH_TO_SUN = 3.003489e-6


def quantile(sorted_vals: Sequence[float], q: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        raise ValueError("empty sequence")
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def robust_stats(vals: Sequence[float]) -> dict[str, float]:
    s = sorted(vals)
    med = statistics.median(s)
    q25 = quantile(s, 0.25)
    q75 = quantile(s, 0.75)
    iqr = q75 - q25
    mad = statistics.median(sorted(abs(v - med) for v in s))
    mean = statistics.fmean(s)
    sd = statistics.stdev(s) if len(s) > 1 else 0.0
    return {
        "n": float(len(s)),
        "mean": mean,
        "sd": sd,
        "median": med,
        "q25": q25,
        "q75": q75,
        "iqr": iqr,
        "mad": mad,
    }


def ols_simple(x: Sequence[float], y: Sequence[float]) -> dict[str, float]:
    n = len(x)
    mx = statistics.fmean(x)
    my = statistics.fmean(y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    syy = sum((yi - my) ** 2 for yi in y)
    slope = sxy / sxx
    intercept = my - slope * mx
    rss = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, y))
    r2 = 1.0 - rss / syy if syy > 0 else 0.0
    rmse = math.sqrt(rss / n)
    se_slope = math.sqrt((rss / max(n - 2, 1)) / sxx) if n > 2 and sxx > 0 else 0.0
    bic = n * math.log(max(rss / n, 1e-300)) + 2.0 * math.log(n)
    return {
        "n": float(n),
        "slope": slope,
        "intercept": intercept,
        "se_slope": se_slope,
        "r2": r2,
        "rmse": rmse,
        "rss": rss,
        "bic": bic,
    }


def solve_linear_system(a: list[list[float]], b: list[float]) -> list[float]:
    m = len(b)
    mat = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(m):
        piv = max(range(col, m), key=lambda r: abs(mat[r][col]))
        mat[col], mat[piv] = mat[piv], mat[col]
        denom = mat[col][col]
        if abs(denom) < 1e-14:
            raise ZeroDivisionError("singular matrix")
        for j in range(col, m + 1):
            mat[col][j] /= denom
        for r in range(m):
            if r != col and mat[r][col] != 0.0:
                factor = mat[r][col]
                for j in range(col, m + 1):
                    mat[r][j] -= factor * mat[col][j]
    return [mat[i][m] for i in range(m)]


def fit_continuous_broken_3(
    x: Sequence[float], y: Sequence[float], k1: float, k2: float
) -> dict[str, object]:
    """Continuous 3-regime piecewise linear fit: y = b0 + b1*x + d2*max(0, x-k1) + d3*max(0, x-k2)."""
    n = len(x)
    xtx = [[0.0] * 4 for _ in range(4)]
    xty = [0.0] * 4
    for xi, yi in zip(x, y):
        row = [1.0, xi, max(0.0, xi - k1), max(0.0, xi - k2)]
        for i in range(4):
            xty[i] += row[i] * yi
            for j in range(4):
                xtx[i][j] += row[i] * row[j]
    beta = solve_linear_system(xtx, xty)
    preds = [
        beta[0] + beta[1] * xi + beta[2] * max(0.0, xi - k1) + beta[3] * max(0.0, xi - k2)
        for xi in x
    ]
    rss = sum((yi - pi) ** 2 for yi, pi in zip(y, preds))
    my = statistics.fmean(y)
    syy = sum((yi - my) ** 2 for yi in y)
    r2 = 1.0 - rss / syy if syy > 0 else 0.0
    rmse = math.sqrt(rss / n)
    bic = n * math.log(max(rss / n, 1e-300)) + 4.0 * math.log(n)
    return {
        "beta": beta,
        "slopes": (beta[1], beta[1] + beta[2], beta[1] + beta[2] + beta[3]),
        "rss": rss,
        "r2": r2,
        "rmse": rmse,
        "bic": bic,
    }


def pearson_r(x: Sequence[float], y: Sequence[float]) -> float:
    mx = statistics.fmean(x)
    my = statistics.fmean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den > 0 else 0.0


def _rank(vals: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(vals), key=lambda t: t[1])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = 0.5 * (i + j - 1) + 1.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def spearman_rho(x: Sequence[float], y: Sequence[float]) -> float:
    return pearson_r(_rank(x), _rank(y))


def kruskal_wallis_stat(groups: Sequence[Sequence[float]]) -> float:
    pooled = [v for g in groups for v in g]
    ranks = _rank(pooled)
    n_tot = len(pooled)
    pos = 0
    h_num = 0.0
    for g in groups:
        ng = len(g)
        r_bar = statistics.fmean(ranks[pos : pos + ng])
        h_num += ng * ((r_bar - 0.5 * (n_tot + 1.0)) ** 2)
        pos += ng
    return (12.0 / (n_tot * (n_tot + 1.0))) * h_num


def kruskal_wallis_perm(groups: Sequence[Sequence[float]], n_perm: int = 1000, seed: int = 47) -> tuple[float, float]:
    obs_h = kruskal_wallis_stat(groups)
    pooled = [v for g in groups for v in g]
    sizes = [len(g) for g in groups]
    rng = random.Random(seed)
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        perm_groups = []
        pos = 0
        for sz in sizes:
            perm_groups.append(pooled[pos : pos + sz])
            pos += sz
        if kruskal_wallis_stat(perm_groups) >= obs_h:
            ge += 1
    return obs_h, (ge + 1.0) / (n_perm + 1.0)


def bootstrap_ci(
    x: Sequence[float],
    y: Sequence[float],
    stat_fn,
    n_boot: int = 1000,
    seed: int = 42,
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(x)
    boots = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        bx = [x[i] for i in idx]
        by = [y[i] for i in idx]
        try:
            boots.append(stat_fn(bx, by))
        except ZeroDivisionError:
            continue
    boots.sort()
    return quantile(boots, 0.025), quantile(boots, 0.975)


def cluster_bootstrap_slope(
    clusters: Sequence[Sequence[int]],
    x: Sequence[float],
    y: Sequence[float],
    n_boot: int = 1000,
    seed: int = 48,
) -> tuple[float, float]:
    rng = random.Random(seed)
    nc = len(clusters)
    boots = []
    for _ in range(n_boot):
        chosen = [clusters[rng.randrange(nc)] for _ in range(nc)]
        bx = [x[i] for cl in chosen for i in cl]
        by = [y[i] for cl in chosen for i in cl]
        if len(bx) > 3:
            try:
                boots.append(ols_simple(bx, by)["slope"])
            except ZeroDivisionError:
                continue
    boots.sort()
    return quantile(boots, 0.025), quantile(boots, 0.975)


def perm_pvalue_corr(
    x: Sequence[float],
    y: Sequence[float],
    n_perm: int = 2000,
    seed: int = 42,
) -> float:
    rng = random.Random(seed)
    obs = abs(spearman_rho(x, y))
    y_copy = list(y)
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(y_copy)
        if abs(spearman_rho(x, y_copy)) >= obs:
            ge += 1
    return (ge + 1.0) / (n_perm + 1.0)


def perm_pvalue_slope_diff(
    x1: Sequence[float], y1: Sequence[float], x2: Sequence[float], y2: Sequence[float], n_perm: int = 1000, seed: int = 49
) -> float:
    obs_diff = abs(ols_simple(x2, y2)["slope"] - ols_simple(x1, y1)["slope"])
    px = list(x1) + list(x2)
    py = list(y1) + list(y2)
    n1 = len(x1)
    idx = list(range(len(px)))
    rng = random.Random(seed)
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(idx)
        g1 = idx[:n1]
        g2 = idx[n1:]
        try:
            s1 = ols_simple([px[i] for i in g1], [py[i] for i in g1])["slope"]
            s2 = ols_simple([px[i] for i in g2], [py[i] for i in g2])["slope"]
        except ZeroDivisionError:
            continue
        if abs(s2 - s1) >= obs_diff:
            ge += 1
    return (ge + 1.0) / (n_perm + 1.0)


def main() -> int:
    rows = read_table(APPENDIX / "data" / "exoplanets_si.csv")
    ext_rows = read_table(APPENDIX / "data" / "exoplanets_nasa_ps_ext.csv")
    ext_by_name = {str(r["pl_name"]): r for r in ext_rows}
    conj = json.loads((APPENDIX / "conjectures.json").read_text(encoding="utf-8"))
    inv = json.loads((APPENDIX / "conjectures_invariant.json").read_text(encoding="utf-8"))

    n_total = len(rows)
    host_to_idx: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        host_to_idx.setdefault(str(r["hostname"]), []).append(i)
    n_hosts = len(host_to_idx)
    one_per_host_idx = [idxs[0] for idxs in host_to_idx.values()]

    p_obs_d = [float(r["pl_orbper"]) for r in rows]
    a_au = [float(r["pl_orbsmax"]) for r in rows]
    m_star = [float(r["st_mass"]) for r in rows]
    m_pl = [float(r["pl_bmasse"]) for r in rows]
    r_pl = [float(r["pl_rade"]) for r in rows]
    p_s = [float(r["P_s"]) for r in rows]
    a_m = [float(r["a_m"]) for r in rows]
    gm = [float(r["GM"]) for r in rows]

    p_kep_s = [TWO_PI * (ai ** 1.5) / math.sqrt(gmi) for ai, gmi in zip(a_m, gm)]
    p_kep_d = [ps / DAY_S for ps in p_kep_s]
    rel_res = [(po - pk) / pk for po, pk in zip(p_obs_d, p_kep_d)]
    abs_rel_res = [abs(r) for r in rel_res]
    pi1 = [ps * (ai ** -1.5) * math.sqrt(gmi) for ps, ai, gmi in zip(p_s, a_m, gm)]
    k_kep = [(ps ** 2) * gmi / (ai ** 3) for ps, ai, gmi in zip(p_s, a_m, gm)]

    # Tail holdout (last 25% sorted by a_m)
    indexed_by_a = sorted(range(n_total), key=lambda i: a_m[i])
    n_train = int(round(n_total * 0.75))
    holdout_idx = indexed_by_a[n_train:]
    holdout_rel = [rel_res[i] for i in holdout_idx]
    holdout_pi1 = [pi1[i] for i in holdout_idx]

    # Log-space holdout R^2
    log_p_obs_h = [math.log10(p_s[i]) for i in holdout_idx]
    c0_law = conj["candidates"][0]["parameters"]["c0"]
    log_p_pred_h = [math.log10(c0_law * (a_m[i] ** 1.5) / math.sqrt(gm[i])) for i in holdout_idx]
    mean_lp = statistics.fmean(log_p_obs_h)
    rss_lp = sum((o - p) ** 2 for o, p in zip(log_p_obs_h, log_p_pred_h))
    tss_lp = sum((o - mean_lp) ** 2 for o in log_p_obs_h)
    holdout_log_r2 = 1.0 - rss_lp / tss_lp
    holdout_rel_rmse = math.sqrt(statistics.fmean([r ** 2 for r in holdout_rel]))

    st_res_all = robust_stats(rel_res)
    st_pi1_all = robust_stats(pi1)
    st_k_all = robust_stats(k_kep)
    st_res_hold = robust_stats(holdout_rel)
    st_pi1_hold = robust_stats(holdout_pi1)

    # Independent transit-geometry check (a_transit = pl_ratdor * st_rad * R_SUN)
    ratdor_res = []
    ratdor_pi1 = []
    ratdor_log_obs = []
    ratdor_log_pred = []
    for i, r in enumerate(rows):
        er = ext_by_name.get(str(r["pl_name"]))
        if not er or er["pl_ratdor"] is None or er["st_rad"] is None:
            continue
        ratdor = float(er["pl_ratdor"])
        srad = float(er["st_rad"])
        if ratdor <= 0 or srad <= 0:
            continue
        a_tr = ratdor * srad * R_SUN_M
        pk_tr = TWO_PI * (a_tr ** 1.5) / math.sqrt(gm[i])
        ratdor_res.append((p_s[i] - pk_tr) / pk_tr)
        ratdor_pi1.append(p_s[i] * (a_tr ** -1.5) * math.sqrt(gm[i]))
        ratdor_log_obs.append(math.log10(p_s[i]))
        ratdor_log_pred.append(math.log10(pk_tr))
    st_ratdor_res = robust_stats(ratdor_res)
    st_ratdor_pi1 = robust_stats(ratdor_pi1)
    ratdor_log_r2 = 1.0 - sum((o - p) ** 2 for o, p in zip(ratdor_log_obs, ratdor_log_pred)) / sum(
        (o - statistics.fmean(ratdor_log_obs)) ** 2 for o in ratdor_log_obs
    )

    # Outlier & 3-sigma observational uncertainty audit + reduced mass correction
    med_r = st_res_all["median"]
    mad_r = st_res_all["mad"]
    sigma_mad = mad_r / 0.6745 if mad_r > 0 else 1e-6
    outliers_3mad = [i for i, v in enumerate(rel_res) if abs(v - med_r) > 3.0 * sigma_mad]
    outliers_5pct = [i for i, v in enumerate(abs_rel_res) if v > 0.05]

    out_with_err = 0
    out_within_3sig = 0
    out_reduced_mass_improved = 0
    for i in outliers_5pct:
        # Reduced mass check: GM_tot = GM * (1 + M_p / M_*)
        gm_tot = gm[i] * (1.0 + (m_pl[i] * M_EARTH_TO_SUN) / m_star[i])
        pk_red = TWO_PI * (a_m[i] ** 1.5) / math.sqrt(gm_tot)
        if abs((p_s[i] - pk_red) / pk_red) < abs_rel_res[i]:
            out_reduced_mass_improved += 1

        er = ext_by_name.get(str(rows[i]["pl_name"]))
        if not er:
            continue
        e_a1, e_a2 = er["pl_orbsmaxerr1"], er["pl_orbsmaxerr2"]
        e_m1, e_m2 = er["st_masserr1"], er["st_masserr2"]
        if e_a1 is not None and e_a2 is not None and e_m1 is not None and e_m2 is not None:
            sig_a = max(abs(float(e_a1)), abs(float(e_a2)))
            sig_m = max(abs(float(e_m1)), abs(float(e_m2)))
            sig_rel = math.sqrt((1.5 * sig_a / a_au[i]) ** 2 + (0.5 * sig_m / m_star[i]) ** 2)
            if sig_rel > 0:
                out_with_err += 1
                if abs_rel_res[i] <= 3.0 * sig_rel:
                    out_within_3sig += 1

    # Stratification by stellar mass + Kruskal-Wallis
    strata_defs = [
        ("M-dwarf (< 0.6 M_sun)", lambda i: m_star[i] < 0.6),
        ("K/G-dwarf (0.6-1.1 M_sun)", lambda i: 0.6 <= m_star[i] <= 1.1),
        ("F/A-star (> 1.1 M_sun)", lambda i: m_star[i] > 1.1),
    ]
    strata_stats = {}
    kw_groups = []
    for label, pred in strata_defs:
        idx = [i for i in range(n_total) if pred(i)]
        vals_pi1 = [pi1[i] for i in idx]
        kw_groups.append(vals_pi1)
        strata_stats[label] = {
            "pi1": robust_stats(vals_pi1),
            "res": robust_stats([rel_res[i] for i in idx]),
        }
    kw_h, kw_p = kruskal_wallis_perm(kw_groups, n_perm=1000, seed=47)

    # Host-clustered & one-per-star sensitivity for Keplerian Pi_1
    rho_pi1_mstar = spearman_rho(m_star, pi1)
    p_pi1_mstar = perm_pvalue_corr(m_star, pi1, n_perm=2000, seed=42)
    rho_pi1_mstar_1ps = spearman_rho([m_star[i] for i in one_per_host_idx], [pi1[i] for i in one_per_host_idx])
    p_pi1_mstar_1ps = perm_pvalue_corr([m_star[i] for i in one_per_host_idx], [pi1[i] for i in one_per_host_idx], n_perm=2000, seed=50)

    # Eccentricity missingness & stratification
    ecc_idx = [i for i, r in enumerate(rows) if r["pl_orbeccen"] is not None]
    miss_ecc_idx = [i for i, r in enumerate(rows) if r["pl_orbeccen"] is None]
    ecc_vals = [float(rows[i]["pl_orbeccen"]) for i in ecc_idx]
    res_ecc = [abs_rel_res[i] for i in ecc_idx]
    rho_res_ecc = spearman_rho(ecc_vals, res_ecc)
    p_res_ecc = perm_pvalue_corr(ecc_vals, res_ecc, n_perm=2000, seed=43)

    ecc_strata = [
        ("Circular (e = 0)", [i for i in ecc_idx if float(rows[i]["pl_orbeccen"]) == 0.0]),
        ("Low-ecc (0 < e <= 0.1)", [i for i in ecc_idx if 0.0 < float(rows[i]["pl_orbeccen"]) <= 0.1]),
        ("Eccentric (e > 0.1)", [i for i in ecc_idx if float(rows[i]["pl_orbeccen"]) > 0.1]),
        ("Missing e", miss_ecc_idx),
    ]

    # Mass-Radius regime analysis (Counter-Evidence)
    log_m = [math.log10(m) for m in m_pl]
    log_r = [math.log10(r) for r in r_pl]
    mr_global = ols_simple(log_m, log_r)
    mr_global_ci = bootstrap_ci(log_m, log_r, lambda x, y: ols_simple(x, y)["slope"], n_boot=1000, seed=44)

    mr_regimes_def = [
        ("rocky", "Rocky (< 2 M_earth)", lambda m: m < 2.0),
        ("sub_neptune", "Sub-Neptune (2-100 M_earth)", lambda m: 2.0 <= m <= 100.0),
        ("jovian", "Jovian (> 100 M_earth)", lambda m: m > 100.0),
    ]
    mr_regimes = {}
    piecewise_rss = 0.0
    for key, label, pred in mr_regimes_def:
        idx = [i for i in range(n_total) if pred(m_pl[i])]
        lx = [log_m[i] for i in idx]
        ly = [log_r[i] for i in idx]
        fit = ols_simple(lx, ly)
        ci = bootstrap_ci(lx, ly, lambda x, y: ols_simple(x, y)["slope"], n_boot=1000, seed=45)
        # Host-clustered bootstrap CI
        reg_clusters: dict[str, list[int]] = {}
        for i in idx:
            reg_clusters.setdefault(str(rows[i]["hostname"]), []).append(i)
        cl_ci = cluster_bootstrap_slope(list(reg_clusters.values()), log_m, log_r, n_boot=1000, seed=51)
        # Mass-only provenance sensitivity
        mass_idx = [i for i in idx if rows[i]["pl_bmassprov"] == "Mass"]
        mass_fit = ols_simple([log_m[i] for i in mass_idx], [log_r[i] for i in mass_idx])
        rho = spearman_rho(lx, ly)
        p_val = perm_pvalue_corr(lx, ly, n_perm=2000, seed=46)
        piecewise_rss += fit["rss"]
        mr_regimes[key] = {
            "label": label,
            "idx": idx,
            "fit": fit,
            "ci_lo": ci[0],
            "ci_hi": ci[1],
            "cl_ci_lo": cl_ci[0],
            "cl_ci_hi": cl_ci[1],
            "mass_n": int(mass_fit["n"]),
            "mass_slope": mass_fit["slope"],
            "rho": rho,
            "p_val": p_val,
        }

    # Rocky vs Sub-Neptune slope equality permutation test
    r_idx = mr_regimes["rocky"]["idx"]
    s_idx = mr_regimes["sub_neptune"]["idx"]
    p_rocky_vs_sub = perm_pvalue_slope_diff(
        [log_m[i] for i in r_idx],
        [log_r[i] for i in r_idx],
        [log_m[i] for i in s_idx],
        [log_r[i] for i in s_idx],
        n_perm=1000,
        seed=49,
    )

    # Disconnected vs Continuous 3-regime broken power law + knot sensitivity + 5-fold CV
    piecewise_bic = n_total * math.log(max(piecewise_rss / n_total, 1e-300)) + 6.0 * math.log(n_total)
    delta_bic_mr = mr_global["bic"] - piecewise_bic
    piecewise_rmse = math.sqrt(piecewise_rss / n_total)

    cont_100 = fit_continuous_broken_3(log_m, log_r, math.log10(2.0), math.log10(100.0))
    cont_120 = fit_continuous_broken_3(log_m, log_r, math.log10(2.0), math.log10(120.0))
    delta_bic_cont_100 = mr_global["bic"] - float(cont_100["bic"])

    # 5-fold out-of-sample CV RMSE
    rng_cv = random.Random(52)
    cv_idx = list(range(n_total))
    rng_cv.shuffle(cv_idx)
    folds = [cv_idx[k::5] for k in range(5)]
    sq_err_global = 0.0
    sq_err_cont = 0.0
    for fk in range(5):
        val_i = set(folds[fk])
        tr_x = [log_m[i] for i in range(n_total) if i not in val_i]
        tr_y = [log_r[i] for i in range(n_total) if i not in val_i]
        va_x = [log_m[i] for i in range(n_total) if i in val_i]
        va_y = [log_r[i] for i in range(n_total) if i in val_i]
        fg = ols_simple(tr_x, tr_y)
        fc = fit_continuous_broken_3(tr_x, tr_y, math.log10(2.0), math.log10(100.0))
        b = fc["beta"]
        k1, k2 = math.log10(2.0), math.log10(100.0)
        for xi, yi in zip(va_x, va_y):
            sq_err_global += (yi - (fg["intercept"] + fg["slope"] * xi)) ** 2
            pc = b[0] + b[1] * xi + b[2] * max(0.0, xi - k1) + b[3] * max(0.0, xi - k2)
            sq_err_cont += (yi - pc) ** 2
    cv_rmse_global = math.sqrt(sq_err_global / n_total)
    cv_rmse_cont = math.sqrt(sq_err_cont / n_total)

    # Sealed conjecture summary
    top_law = conj["candidates"][0]
    top_inv = inv["candidates"][0]
    c0_pct_err = abs(c0_law - TWO_PI) / TWO_PI * 100.0
    c_inv = top_inv["parameters"]["constant"]
    cinv_pct_err = abs(c_inv - TWO_PI) / TWO_PI * 100.0

    # Print verbatim output.txt
    print("=== HEURISMA LEVEL 3 EXOPLANET KEPLERIAN & MASS-RADIUS ANALYSIS ===")
    print(f"Dataset: exoplanets_si.csv | N = {n_total} planets | Host stars = {n_hosts}")
    print(f"Stellar mass range: {min(m_star):.3f} to {max(m_star):.3f} M_sun")
    print(f"Orbital period range: {min(p_obs_d):.4f} to {max(p_obs_d):.2f} d")
    print()
    print("--- 1. Sealed Symbolic Discovery & Invariant (conjecture.py) ---")
    print(f"Top law (C_LAW_1): {top_law['expr']}")
    print(f"  c0 = {c0_law:.4f} vs 2*pi = {TWO_PI:.4f} (deviation = {c0_pct_err:.2f}%)")
    print(f"  Train BIC = {top_law['train_bic']:.2f} vs Null BIC = {conj['null_train_bic']:.2f}")
    print(f"  Holdout (n={conj['holdout_count']}): linear R^2 = {top_law['holdout_r2']:.6f}, log10 R^2 = {holdout_log_r2:.6f}, rel RMSE = {holdout_rel_rmse*100:.2f}%")
    print(f"Top invariant (C_INV_1): {top_inv['expr']}")
    print(f"  c_inv = {c_inv:.5f} vs 2*pi = {TWO_PI:.5f} (deviation = {cinv_pct_err:.2f}%)")
    print(f"  Holdout R^2 = {top_inv['holdout_r2']:.6f}, Holdout RMSE = {top_inv['holdout_rmse']:.5f}")
    print()
    print("--- 2. Keplerian Residuals, Independent Transit a/R_* Check & Outliers ---")
    print(f"Pi_1 = P_s * a_m^(-3/2) * GM^(1/2): mean = {st_pi1_all['mean']:.4f}, sd = {st_pi1_all['sd']:.4f}, median = {st_pi1_all['median']:.4f}, IQR = {st_pi1_all['iqr']:.4f}, MAD = {st_pi1_all['mad']:.4f}")
    print(f"K = P_s^2 * GM / a_m^3 (ideal 4*pi^2 = {FOUR_PI_SQ:.4f}): median = {st_k_all['median']:.4f}, IQR = {st_k_all['iqr']:.4f}")
    print(f"Relative period residual (P_obs - P_kep)/P_kep: median = {st_res_all['median']*100:.4f}%, IQR = {st_res_all['iqr']*100:.4f}%, MAD = {st_res_all['mad']*100:.4f}%")
    print(f"Independent transit a_tr = (a/R_*)*R_* check (n={int(st_ratdor_res['n'])}): log10 R^2 = {ratdor_log_r2:.6f}, Pi_1 med = {st_ratdor_pi1['median']:.4f}, rel_res med = {st_ratdor_res['median']*100:.4f}% (IQR={st_ratdor_res['iqr']*100:.4f}%)")
    print(f"Outlier audit: |res - med| > 3*sigma_MAD: n = {len(outliers_3mad)} ({len(outliers_3mad)/n_total*100:.1f}%); |res| > 5%: n = {len(outliers_5pct)} ({len(outliers_5pct)/n_total*100:.1f}%)")
    print(f"  Outliers >5% with error bars (n={out_with_err}): within 3-sigma propagated uncertainty = {out_within_3sig}/{out_with_err} ({out_within_3sig/max(out_with_err,1)*100:.1f}%)")
    print(f"  Reduced-mass (M_* + M_p) correction improved {out_reduced_mass_improved}/{len(outliers_5pct)} >5% outliers")
    print()
    print("--- 3. Stratification by Host-Star Mass, Clustering & Eccentricity ---")
    for label, d in strata_stats.items():
        p1 = d["pi1"]
        rs = d["res"]
        print(f"  {label}: n={int(p1['n'])}, Pi_1 med={p1['median']:.4f} (IQR={p1['iqr']:.4f}), rel_res med={rs['median']*100:.4f}%")
    print(f"Kruskal-Wallis across stellar-mass strata: H = {kw_h:.4f}, perm p = {kw_p:.4f}")
    print(f"Spearman(M_star, Pi_1): all n={n_total} rho = {rho_pi1_mstar:.4f} (p={p_pi1_mstar:.4f}); 1-per-star n={n_hosts} rho = {rho_pi1_mstar_1ps:.4f} (p={p_pi1_mstar_1ps:.4f})")
    print(f"Eccentricity available: n={len(ecc_idx)} (missing n={len(miss_ecc_idx)}) | Spearman(e, |rel_res|): rho = {rho_res_ecc:.4f}, perm p = {p_res_ecc:.4f}")
    for label, idx in ecc_strata:
        st = robust_stats([abs_rel_res[i] for i in idx])
        print(f"  {label}: n={int(st['n'])}, |rel_res| med={st['median']*100:.4f}% (IQR={st['iqr']*100:.4f}%)")
    print()
    print("--- 4. Counter-Evidence: Planetary Mass-Radius Regime Breakdown ---")
    print(f"Global single power law (n={n_total}): slope = {mr_global['slope']:.4f} (95% CI [{mr_global_ci[0]:.4f}, {mr_global_ci[1]:.4f}]), R^2 = {mr_global['r2']:.4f}, RMSE = {mr_global['rmse']:.4f} dex, BIC = {mr_global['bic']:.2f}")
    for key, label, _ in mr_regimes_def:
        reg = mr_regimes[key]
        f = reg["fit"]
        print(f"  {label}: n={int(f['n'])} (Mass-only n={reg['mass_n']}, slope={reg['mass_slope']:.4f}), slope = {f['slope']:.4f} (95% CI [{reg['ci_lo']:.4f}, {reg['ci_hi']:.4f}], cluster CI [{reg['cl_ci_lo']:.4f}, {reg['cl_ci_hi']:.4f}]), R^2 = {f['r2']:.4f}, rho = {reg['rho']:.4f} (p={reg['p_val']:.4f})")
    print(f"Rocky vs Sub-Neptune slope equality perm p = {p_rocky_vs_sub:.4f}")
    print(f"Disconnected 3-regime model: RMSE = {piecewise_rmse:.4f} dex, BIC = {piecewise_bic:.2f}, Delta_BIC = {delta_bic_mr:.2f}")
    print(f"Continuous 3-regime model (knots 2, 100 M_earth): slopes = ({cont_100['slopes'][0]:.4f}, {cont_100['slopes'][1]:.4f}, {cont_100['slopes'][2]:.4f}), R^2 = {cont_100['r2']:.4f}, RMSE = {cont_100['rmse']:.4f} dex, BIC = {cont_100['bic']:.2f}, Delta_BIC = {delta_bic_cont_100:.2f}")
    print(f"Continuous knot sensitivity (120 M_earth): Jovian slope = {cont_120['slopes'][2]:.4f}, BIC = {cont_120['bic']:.2f}")
    print(f"5-fold CV out-of-sample RMSE: Global = {cv_rmse_global:.4f} dex vs Continuous 3-regime = {cv_rmse_cont:.4f} dex")

    numbers = {
        "n_total": n_total,
        "n_hosts": n_hosts,
        "n_train": conj["train_count"],
        "n_holdout": conj["holdout_count"],
        "c0_law": round(c0_law, 4),
        "two_pi": round(TWO_PI, 4),
        "c0_pct_err": round(c0_pct_err, 2),
        "law_holdout_r2": round(top_law["holdout_r2"], 4),
        "law_holdout_log_r2": round(holdout_log_r2, 4),
        "law_holdout_rel_rmse_pct": round(holdout_rel_rmse * 100.0, 2),
        "law_train_bic": round(top_law["train_bic"], 1),
        "null_train_bic": round(conj["null_train_bic"], 1),
        "c_inv": round(c_inv, 4),
        "cinv_pct_err": round(cinv_pct_err, 2),
        "inv_holdout_r2": round(top_inv["holdout_r2"], 4),
        "inv_holdout_rmse": round(top_inv["holdout_rmse"], 4),
        "pi1_med": round(st_pi1_all["median"], 4),
        "pi1_iqr": round(st_pi1_all["iqr"], 4),
        "k_med": round(st_k_all["median"], 3),
        "k_ideal": round(FOUR_PI_SQ, 3),
        "rel_res_med_pct": round(st_res_all["median"] * 100.0, 3),
        "rel_res_iqr_pct": round(st_res_all["iqr"] * 100.0, 3),
        "ratdor_n": int(st_ratdor_res["n"]),
        "ratdor_log_r2": round(ratdor_log_r2, 4),
        "ratdor_pi1_med": round(st_ratdor_pi1["median"], 4),
        "ratdor_res_med_pct": round(st_ratdor_res["median"] * 100.0, 3),
        "kw_h": round(kw_h, 2),
        "kw_p": round(kw_p, 4),
        "rho_pi1_mstar": round(rho_pi1_mstar, 4),
        "p_pi1_mstar": round(p_pi1_mstar, 4),
        "rho_pi1_mstar_1ps": round(rho_pi1_mstar_1ps, 4),
        "p_pi1_mstar_1ps": round(p_pi1_mstar_1ps, 4),
        "rho_res_ecc": round(rho_res_ecc, 4),
        "p_res_ecc": round(p_res_ecc, 4),
        "n_outliers_5pct": len(outliers_5pct),
        "pct_outliers_5pct": round(len(outliers_5pct) / n_total * 100.0, 1),
        "out_with_err": out_with_err,
        "out_within_3sig": out_within_3sig,
        "out_within_3sig_pct": round(out_within_3sig / max(out_with_err, 1) * 100.0, 1),
        "mr_global_slope": round(mr_global["slope"], 3),
        "mr_global_r2": round(mr_global["r2"], 3),
        "mr_global_bic": round(mr_global["bic"], 1),
        "mr_piecewise_bic": round(piecewise_bic, 1),
        "mr_delta_bic": round(delta_bic_mr, 1),
        "mr_cont_delta_bic": round(delta_bic_cont_100, 1),
        "mr_cont_r2": round(float(cont_100["r2"]), 3),
        "cv_rmse_global": round(cv_rmse_global, 4),
        "cv_rmse_cont": round(cv_rmse_cont, 4),
        "mr_rocky_n": int(mr_regimes["rocky"]["fit"]["n"]),
        "mr_rocky_slope": round(mr_regimes["rocky"]["fit"]["slope"], 3),
        "mr_rocky_r2": round(mr_regimes["rocky"]["fit"]["r2"], 3),
        "p_rocky_vs_sub": round(p_rocky_vs_sub, 4),
        "mr_subnep_n": int(mr_regimes["sub_neptune"]["fit"]["n"]),
        "mr_subnep_slope": round(mr_regimes["sub_neptune"]["fit"]["slope"], 3),
        "mr_subnep_r2": round(mr_regimes["sub_neptune"]["fit"]["r2"], 3),
        "mr_jovian_n": int(mr_regimes["jovian"]["fit"]["n"]),
        "mr_jovian_slope": round(mr_regimes["jovian"]["fit"]["slope"], 3),
        "mr_jovian_r2": round(mr_regimes["jovian"]["fit"]["r2"], 3),
        "mr_jovian_massonly_slope": round(mr_regimes["jovian"]["mass_slope"], 3),
    }
    (APPENDIX / "numbers.json").write_text(
        json.dumps(numbers, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    scatter_pts = [[round(math.log10(pk), 4), round(math.log10(po), 4)] for pk, po in zip(p_kep_d, p_obs_d)]
    max_hold_i = max(holdout_idx, key=lambda i: p_obs_d[i])
    hl_x = round(math.log10(p_kep_d[max_hold_i]), 4)
    hl_y = round(math.log10(p_obs_d[max_hold_i]), 4)
    hl_name = str(rows[max_hold_i]["pl_name"])

    bin_edges = [-1.0 + 0.35 * k for k in range(15)]
    med_pts, p25_pts, p75_pts, global_pts = [], [], [], []
    for k in range(len(bin_edges) - 1):
        lo, hi = bin_edges[k], bin_edges[k + 1]
        in_bin = [r_pl[i] for i in range(n_total) if lo <= log_m[i] < hi]
        if len(in_bin) >= 5:
            mid_x = round(0.5 * (lo + hi), 3)
            s_bin = sorted(in_bin)
            med_pts.append([mid_x, round(statistics.median(s_bin), 3)])
            p25_pts.append([mid_x, round(quantile(s_bin, 0.25), 3)])
            p75_pts.append([mid_x, round(quantile(s_bin, 0.75), 3)])
            g_pred = 10.0 ** (mr_global["intercept"] + mr_global["slope"] * mid_x)
            global_pts.append([mid_x, round(g_pred, 3)])

    bar_groups = [
        f"Rocky (<2 M_E, n={int(mr_regimes['rocky']['fit']['n'])})",
        f"Sub-Neptune (2-100 M_E, n={int(mr_regimes['sub_neptune']['fit']['n'])})",
        f"Jovian (>100 M_E, n={int(mr_regimes['jovian']['fit']['n'])})",
        f"Global Single Fit (n={n_total})",
    ]
    bar_values = [
        round(mr_regimes["rocky"]["fit"]["slope"], 3),
        round(mr_regimes["sub_neptune"]["fit"]["slope"], 3),
        round(mr_regimes["jovian"]["fit"]["slope"], 3),
        round(mr_global["slope"], 3),
    ]

    charts = [
        {
            "id": "kepler_scaling_scatter",
            "type": "scatter",
            "title": f"Observed vs. Two-Body Keplerian Orbital Period (N = {n_total}, Log Holdout R^2 = {holdout_log_r2:.4f})",
            "caption": f"Log10 observed period vs. predicted P_kep across {n_hosts} host stars; median residual {st_res_all['median']*100:.3f}%.",
            "source": f"NASA Exoplanet Archive PS (N = {n_total}); own computations in appendix/analysis.py.",
            "x": {"label": "Predicted log10(P_kep / days)"},
            "y": {"label": "Observed log10(P_obs / days)"},
            "series": [{"name": "Confirmed transiting planets", "points": scatter_pts}],
            "highlight": {"x": hl_x, "y": hl_y, "label": hl_name},
        },
        {
            "id": "mass_radius_regimes",
            "type": "line",
            "title": f"Planetary Mass-Radius Degeneracy vs. Single Power Law (Delta BIC = {delta_bic_cont_100:.1f})",
            "caption": f"Binned median radius (P25-P75 band) flattens at Jovian slope {mr_regimes['jovian']['fit']['slope']:.3f} above 100 M_earth, diverging from the global slope {mr_global['slope']:.3f}.",
            "source": f"NASA Exoplanet Archive PS (N = {n_total}); own computations in appendix/analysis.py.",
            "x": {"type": "number", "label": "log10(Planet Mass / M_earth)"},
            "y": {"label": "Planet Radius (R_earth)", "scale": "linear"},
            "series": [
                {"name": "Observed median R_p", "points": med_pts},
                {"name": "Single power-law fit", "points": global_pts},
            ],
            "bands": [{"name": "Observed IQR (P25-P75)", "lower": p25_pts, "upper": p75_pts}],
            "annotations": [{"x": 0.30, "label": "Rocky/Sub-Nep"}, {"x": 2.00, "label": "Jovian turnover"}],
        },
        {
            "id": "regime_slopes_bar",
            "type": "bar",
            "title": f"Mass-Radius Power-Law Slope by Regime (Sub-Neptune {mr_regimes['sub_neptune']['fit']['slope']:.3f} vs. Jovian {mr_regimes['jovian']['fit']['slope']:.3f})",
            "caption": f"OLS exponent d(log10 R_p)/d(log10 M_p) drops from {mr_regimes['sub_neptune']['fit']['slope']:.3f} in sub-Neptunes to {mr_regimes['jovian']['fit']['slope']:.3f} in Jovians.",
            "source": f"NASA Exoplanet Archive PS (N = {n_total}); own computations in appendix/analysis.py.",
            "y": {"label": "Power-Law Slope (d log R_p / d log M_p)"},
            "groups": bar_groups,
            "series": [{"name": "Power-law exponent", "values": bar_values}],
        },
    ]

    (STUDY_DIR / "charts.json").write_text(
        json.dumps(charts, allow_nan=False, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
