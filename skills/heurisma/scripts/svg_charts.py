#!/usr/bin/env python3
"""Zero-dependency publication-grade SVG charting engine for Heurisma working papers.

Supports Heckbert nice-number ticks, horizontal gridlines, date & numeric X-axes,
multi-series line/scatter charts with Okabe-Ito colorblind-safe palette & print-safe
dash styles, automatic marker hiding for dense (>30 pt) series, vertical event
annotations, shaded policy bands, fan projection charts (P10-P90 / P25-P75 / P50),
grouped bar charts, optional log Y-scale, and <title>/<desc> accessibility.
"""

from __future__ import annotations

import datetime as _dt
import html
import math
from typing import Any

# Okabe-Ito colorblind-safe palette + neutral slate for context
OKABE_ITO: tuple[str, ...] = (
    "#0072B2",  # Blue
    "#D55E00",  # Vermilion
    "#009E73",  # Bluish green
    "#E69F00",  # Orange
    "#CC79A7",  # Reddish purple
    "#56B4E9",  # Sky blue
    "#475569",  # Neutral slate
)

DASH_STYLES: tuple[str, ...] = ("", "6,3", "2,3", "8,3,2,3", "10,4")


def _nice_num(val: float, round_val: bool) -> float:
    if val <= 0:
        return 1.0
    exp = math.floor(math.log10(val))
    frac = val / (10.0 ** exp)
    if round_val:
        if frac < 1.5:
            nf = 1.0
        elif frac < 3.0:
            nf = 2.0
        elif frac < 7.0:
            nf = 5.0
        else:
            nf = 10.0
    else:
        if frac <= 1.0:
            nf = 1.0
        elif frac <= 2.0:
            nf = 2.0
        elif frac <= 5.0:
            nf = 5.0
        else:
            nf = 10.0
    return nf * (10.0 ** exp)


def nice_ticks(min_v: float, max_v: float, max_ticks: int = 5) -> list[float]:
    """Heckbert's algorithm for clean axis tick values (1, 2, 5 x 10^n)."""
    if not math.isfinite(min_v) or not math.isfinite(max_v):
        return [0.0, 1.0]
    if min_v == max_v:
        pad = abs(min_v) * 0.1 or 1.0
        min_v, max_v = min_v - pad, max_v + pad
    rng = _nice_num(max_v - min_v, round_val=False)
    step = _nice_num(rng / max(1, max_ticks - 1), round_val=True)
    graph_min = math.floor(min_v / step) * step
    graph_max = math.ceil(max_v / step) * step
    ticks: list[float] = []
    cur = graph_min
    guard = 0
    while cur <= graph_max + 0.5 * step and guard < 20:
        ticks.append(0.0 if abs(cur) < 1e-12 else round(cur, 10))
        cur += step
        guard += 1
    return ticks or [min_v, max_v]


def _format_num(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 10 or v == int(v):
        return f"{v:.4g}"
    return f"{v:.3g}"


def _parse_x(val: Any, is_date: bool) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if is_date or (len(s) >= 7 and s[4:5] == "-"):
        parts = s.split("-")
        try:
            year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 else 1
            day = int(parts[2][:2]) if len(parts) > 2 else 1
            return float(_dt.date(year, max(1, min(12, month)), max(1, min(28, day))).toordinal())
        except ValueError:
            pass
    try:
        return float(s)
    except ValueError:
        return 0.0


def _format_date_ordinal(ord_val: float, span_days: float) -> str:
    d = _dt.date.fromordinal(max(1, int(round(ord_val))))
    if span_days > 730:
        return f"{d.year}"
    return f"{d.year}-{d.month:02d}"


def _extract_xy_points(raw_points: list[Any], is_date: bool) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    for idx, pt in enumerate(raw_points):
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            out.append((_parse_x(pt[0], is_date), float(pt[1]), str(pt[0])))
        elif isinstance(pt, dict):
            xv = pt.get("x", idx)
            yv = pt.get("y", pt.get("value", 0.0))
            lbl = str(pt.get("label", xv))
            out.append((_parse_x(xv, is_date), float(yv), lbl))
    return out


def _y_transform(v: float, is_log: bool, min_pos: float) -> float:
    if not is_log:
        return v
    return math.log10(max(v, min_pos))


def _render_axes_and_grid(
    width: int,
    height: int,
    pad_l: int,
    pad_r: int,
    pad_t: int,
    pad_b: int,
    y_ticks: list[float],
    y_min_t: float,
    y_max_t: float,
    is_log: bool,
    min_pos: float,
    y_label: str,
) -> tuple[list[str], Any]:
    plot_h = height - pad_t - pad_b
    span_y = (y_max_t - y_min_t) or 1.0

    def y_px(v: float) -> float:
        vt = _y_transform(v, is_log, min_pos)
        return pad_t + (y_max_t - vt) / span_y * plot_h

    els: list[str] = []
    for tv in y_ticks:
        yp = y_px(tv)
        if yp < pad_t - 4 or yp > height - pad_b + 4:
            continue
        els.append(
            f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{width - pad_r}" y2="{yp:.1f}" '
            f'stroke="#e2e8f0" stroke-width="1"/>'
        )
        els.append(
            f'<text x="{pad_l - 8}" y="{yp + 3.5:.1f}" text-anchor="end" '
            f'font-size="11" fill="#475569">{html.escape(_format_num(tv))}</text>'
        )

    els.append(
        f'<line x1="{pad_l}" y1="{height - pad_b}" x2="{width - pad_r}" y2="{height - pad_b}" '
        f'stroke="#334155" stroke-width="1.2"/>'
    )
    if y_label:
        els.append(
            f'<text x="{pad_l}" y="{pad_t - 10}" text-anchor="start" font-size="11" '
            f'font-weight="600" fill="#334155">{html.escape(y_label)}</text>'
        )
    return els, y_px


def _render_line_or_scatter(chart: dict[str, Any], is_scatter: bool = False) -> str:
    width, height = 680, 340
    pad_l, pad_r, pad_t, pad_b = 64, 26, 36, 52
    plot_w = width - pad_l - pad_r

    x_cfg = chart.get("x") or {}
    y_cfg = chart.get("y") or {}
    is_date = str(x_cfg.get("type", "")).lower() == "date"
    is_log = str(y_cfg.get("scale", "linear")).lower() == "log"
    x_label = str(x_cfg.get("label", chart.get("x_label", "")))
    y_label = str(y_cfg.get("label", chart.get("y_label", "")))

    # Normalize v1 & v2 series structure
    raw_series = chart.get("series") or []
    if not raw_series and chart.get("points"):
        raw_series = [{"name": chart.get("title", "Series"), "points": chart["points"]}]

    parsed_series: list[tuple[str, list[tuple[float, float, str]]]] = []
    all_x: list[float] = []
    all_y: list[float] = []

    for s in raw_series:
        pts = _extract_xy_points(s.get("points") or [], is_date)
        if pts:
            parsed_series.append((str(s.get("name", "Series")), pts))
            all_x.extend(p[0] for p in pts)
            all_y.extend(p[1] for p in pts)

    # Include bands & annotations in bounds
    parsed_bands: list[tuple[str, list[tuple[float, float, str]], list[tuple[float, float, str]]]] = []
    for b in chart.get("bands") or []:
        lo_pts = _extract_xy_points(b.get("lower") or [], is_date)
        hi_pts = _extract_xy_points(b.get("upper") or [], is_date)
        if lo_pts and hi_pts:
            parsed_bands.append((str(b.get("name", "Band")), lo_pts, hi_pts))
            all_x.extend(p[0] for p in lo_pts + hi_pts)
            all_y.extend(p[1] for p in lo_pts + hi_pts)

    ref_lines = chart.get("reference_lines") or []
    for rl in ref_lines:
        if "value" in rl:
            all_y.append(float(rl["value"]))

    if not all_x or not all_y:
        return _empty_svg(chart)

    min_x, max_x = min(all_x), max(all_x)
    span_x = (max_x - min_x) or 1.0

    pos_ys = [v for v in all_y if v > 0]
    min_pos = min(pos_ys) if pos_ys else 1.0
    if is_log:
        min_exp = math.floor(math.log10(min_pos))
        max_exp = math.ceil(math.log10(max(pos_ys) if pos_ys else 10.0))
        if min_exp == max_exp:
            max_exp += 1
        y_ticks = [10.0 ** e for e in range(min_exp, max_exp + 1)]
        y_min_t, y_max_t = float(min_exp), float(max_exp)
    else:
        raw_min_y, raw_max_y = min(all_y), max(all_y)
        pad_y = (raw_max_y - raw_min_y) * 0.05 or abs(raw_max_y) * 0.05 or 1.0
        y_ticks = nice_ticks(raw_min_y - pad_y, raw_max_y + pad_y, max_ticks=5)
        y_min_t, y_max_t = y_ticks[0], y_ticks[-1]

    els, y_px = _render_axes_and_grid(
        width, height, pad_l, pad_r, pad_t, pad_b, y_ticks, y_min_t, y_max_t, is_log, min_pos, y_label
    )

    def x_px(xv: float) -> float:
        if span_x == 0:
            return pad_l + plot_w / 2.0
        return pad_l + (xv - min_x) / span_x * plot_w

    # X-axis ticks (4-6 clean ticks; snap multi-year date axes to clean calendar years)
    if is_date and span_x > 730:
        start_y = _dt.date.fromordinal(max(1, int(round(min_x)))).year
        end_y = _dt.date.fromordinal(max(1, int(round(max_x)))).year
        step_y = max(1, int(round(_nice_num((end_y - start_y) / 5.0, round_val=True))))
        first_y = start_y if start_y % step_y == 0 else start_y + (step_y - start_y % step_y)
        x_ticks = [
            float(_dt.date(y, 1, 1).toordinal())
            for y in range(first_y, end_y + 1, step_y)
            if min_x <= _dt.date(y, 1, 1).toordinal() <= max_x
        ]
        if len(x_ticks) < 2:
            x_ticks = [min_x, max_x]
    else:
        n_x_ticks = min(6, max(2, len(set(all_x))))
        x_ticks = [min_x + i * (max_x - min_x) / max(1, n_x_ticks - 1) for i in range(n_x_ticks)]
    for tx in x_ticks:
        xp = x_px(tx)
        lbl = _format_date_ordinal(tx, span_x) if is_date else _format_num(tx)
        els.append(
            f'<line x1="{xp:.1f}" y1="{height - pad_b}" x2="{xp:.1f}" y2="{height - pad_b + 5}" stroke="#334155"/>'
            f'<text x="{xp:.1f}" y="{height - pad_b + 18}" text-anchor="middle" font-size="11" fill="#475569">{html.escape(lbl)}</text>'
        )
    if x_label:
        els.append(
            f'<text x="{pad_l + plot_w / 2:.1f}" y="{height - 10}" text-anchor="middle" font-size="11" fill="#334155">{html.escape(x_label)}</text>'
        )

    # Shaded bands behind series
    for b_name, lo_pts, hi_pts in parsed_bands:
        poly_pts = [(x_px(p[0]), y_px(p[1])) for p in hi_pts] + [
            (x_px(p[0]), y_px(p[1])) for p in reversed(lo_pts)
        ]
        coord_str = " ".join(f"{px:.1f},{py:.1f}" for px, py in poly_pts)
        els.append(f'<polygon points="{coord_str}" fill="#94a3b8" fill-opacity="0.22" stroke="none"/>')

    # Reference horizontal lines
    for rl in ref_lines:
        if "value" in rl:
            ry = y_px(float(rl["value"]))
            rname = html.escape(str(rl.get("name", "")))
            els.append(
                f'<line x1="{pad_l}" y1="{ry:.1f}" x2="{width - pad_r}" y2="{ry:.1f}" '
                f'stroke="#64748b" stroke-dasharray="4,4" stroke-width="1.2"/>'
                f'<text x="{width - pad_r - 4}" y="{ry - 4:.1f}" text-anchor="end" font-size="10" fill="#475569">{rname}</text>'
            )

    # Vertical event annotations
    for ann in chart.get("annotations") or []:
        ax = _parse_x(ann.get("x", 0), is_date)
        if min_x <= ax <= max_x:
            xp = x_px(ax)
            albl = html.escape(str(ann.get("label", "")))
            els.append(
                f'<line x1="{xp:.1f}" y1="{pad_t}" x2="{xp:.1f}" y2="{height - pad_b}" '
                f'stroke="#64748b" stroke-dasharray="3,3" stroke-width="1"/>'
                f'<text x="{xp + 4:.1f}" y="{pad_t + 12}" font-size="10" fill="#334155">{albl}</text>'
            )

    # Plot series (hide circles when dense >30 pts; never clutter with per-point labels)
    legend_items: list[tuple[str, str, str]] = []
    for idx, (s_name, pts) in enumerate(parsed_series):
        color = OKABE_ITO[idx % len(OKABE_ITO)]
        dash = DASH_STYLES[idx % len(DASH_STYLES)]
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        legend_items.append((s_name, color, dash))

        if not is_scatter and len(pts) > 1:
            poly = " ".join(f"{x_px(p[0]):.1f},{y_px(p[1]):.1f}" for p in pts)
            els.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2.2"{dash_attr} points="{poly}"/>'
            )

        if is_scatter or len(pts) <= 30:
            radius = 4.0 if is_scatter else 3.0
            for p in pts:
                els.append(
                    f'<circle cx="{x_px(p[0]):.1f}" cy="{y_px(p[1]):.1f}" r="{radius}" '
                    f'fill="{color}" stroke="#ffffff" stroke-width="0.8"/>'
                )

    # Legend (top-right when multiple series or bands)
    if len(legend_items) > 1 or parsed_bands:
        lx = width - pad_r
        ly = 16
        for s_name, color, dash in reversed(legend_items):
            lbl = html.escape(s_name)
            w_est = max(60, len(lbl) * 6.5 + 24)
            lx -= w_est
            dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
            els.append(
                f'<line x1="{lx:.1f}" y1="{ly - 3}" x2="{lx + 16:.1f}" y2="{ly - 3}" '
                f'stroke="{color}" stroke-width="2.2"{dash_attr}/>'
                f'<text x="{lx + 20:.1f}" y="{ly}" font-size="10.5" fill="#1e293b">{lbl}</text>'
            )

    return _wrap_svg(chart, width, height, els)


def _render_fan(chart: dict[str, Any]) -> str:
    """Render fan chart (P10-P90 outer band, P25-P75 inner band, P50 median line)."""
    q = chart.get("quantiles") or {}
    if not q or "p50" not in q:
        return _empty_svg(chart)

    synth = dict(chart)
    synth["type"] = "line"
    synth["series"] = [{"name": "Median (P50)", "points": q["p50"]}]
    bands = list(chart.get("bands") or [])
    if "p10" in q and "p90" in q:
        bands.append({"name": "P10–P90", "lower": q["p10"], "upper": q["p90"]})
    if "p25" in q and "p75" in q:
        bands.append({"name": "P25–P75", "lower": q["p25"], "upper": q["p75"]})
    synth["bands"] = bands
    return _render_line_or_scatter(synth, is_scatter=False)


def _render_bar(chart: dict[str, Any]) -> str:
    width, height = 680, 320
    pad_l, pad_r, pad_t, pad_b = 64, 24, 38, 56
    plot_w = width - pad_l - pad_r

    y_cfg = chart.get("y") or {}
    y_label = str(y_cfg.get("label", chart.get("y_label", "")))

    # Support both v2 grouped bars (groups + series[{name, values}]) and v1 flat bars (series[{label, value}])
    groups = chart.get("groups")
    raw_series = chart.get("series") or []
    if groups and raw_series and "values" in raw_series[0]:
        group_labels = [str(g) for g in groups]
        series_list = [(str(s.get("name", f"S{i + 1}")), [float(v) for v in s.get("values") or []]) for i, s in enumerate(raw_series)]
    elif raw_series and "value" in raw_series[0]:
        group_labels = [str(s.get("label", f"#{i + 1}")) for i, s in enumerate(raw_series)]
        series_list = [("", [float(s.get("value", 0.0)) for s in raw_series])]
    else:
        return _empty_svg(chart)

    all_vals = [v for _, vals in series_list for v in vals]
    if not all_vals:
        return _empty_svg(chart)

    min_v = min(0.0, min(all_vals))
    max_v = max(0.0, max(all_vals))
    y_ticks = nice_ticks(min_v, max_v, max_ticks=5)
    els, y_px = _render_axes_and_grid(
        width, height, pad_l, pad_r, pad_t, pad_b, y_ticks, y_ticks[0], y_ticks[-1], False, 1.0, y_label
    )

    zero_y = y_px(0.0)
    els.append(
        f'<line x1="{pad_l}" y1="{zero_y:.1f}" x2="{width - pad_r}" y2="{zero_y:.1f}" '
        f'stroke="#334155" stroke-width="1.2"/>'
    )

    n_groups = len(group_labels)
    n_series = len(series_list)
    slot_w = plot_w / max(1, n_groups)
    cluster_w = slot_w * 0.72
    bar_w = max(10.0, min(56.0, cluster_w / max(1, n_series) - 3.0))

    for g_idx, g_lbl in enumerate(group_labels):
        g_center = pad_l + (g_idx + 0.5) * slot_w
        total_w = n_series * bar_w + max(0, n_series - 1) * 3.0
        start_x = g_center - total_w / 2.0
        for s_idx, (_, vals) in enumerate(series_list):
            if g_idx >= len(vals):
                continue
            v = vals[g_idx]
            bx = start_x + s_idx * (bar_w + 3.0)
            by = y_px(v)
            top = min(by, zero_y)
            bh = max(1.5, abs(by - zero_y))
            color = OKABE_ITO[s_idx % len(OKABE_ITO)] if n_series > 1 else (OKABE_ITO[0] if v >= 0 else OKABE_ITO[1])
            val_y = top - 5 if v >= 0 else top + bh + 12
            els.append(
                f'<rect x="{bx:.1f}" y="{top:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="2" fill="{color}"/>'
                f'<text x="{bx + bar_w / 2:.1f}" y="{val_y:.1f}" text-anchor="middle" font-size="10" fill="#1e293b">{_format_num(v)}</text>'
            )
        els.append(
            f'<text x="{g_center:.1f}" y="{height - pad_b + 18}" text-anchor="middle" font-size="11" fill="#334155">{html.escape(g_lbl)}</text>'
        )

    if n_series > 1:
        lx = width - pad_r
        ly = 16
        for s_idx in range(n_series - 1, -1, -1):
            s_name = html.escape(series_list[s_idx][0])
            color = OKABE_ITO[s_idx % len(OKABE_ITO)]
            w_est = max(65, len(s_name) * 6.5 + 22)
            lx -= w_est
            els.append(
                f'<rect x="{lx:.1f}" y="{ly - 9}" width="11" height="11" rx="2" fill="{color}"/>'
                f'<text x="{lx + 15:.1f}" y="{ly}" font-size="10.5" fill="#1e293b">{s_name}</text>'
            )

    return _wrap_svg(chart, width, height, els)


def _empty_svg(chart: dict[str, Any]) -> str:
    title = html.escape(str(chart.get("title", "Figure")))
    return (
        f'<svg viewBox="0 0 680 120" width="100%" role="img">'
        f"<title>{title}</title><desc>No data available for this figure.</desc>"
        f'<text x="340" y="64" text-anchor="middle" font-size="12" fill="#64748b">{title} (no data)</text>'
        f"</svg>"
    )


def _wrap_svg(chart: dict[str, Any], width: int, height: int, elements: list[str]) -> str:
    title = html.escape(str(chart.get("title", "Figure")))
    desc = html.escape(str(chart.get("caption") or chart.get("title") or "Scientific figure"))
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'style="font-family: inherit; display: block;">'
        f"<title>{title}</title><desc>{desc}</desc>"
        + "".join(elements)
        + "</svg>"
    )


def render_chart_svg(chart: dict[str, Any]) -> str:
    """Dispatch chart dict (v2 or v1 schema) to the appropriate SVG renderer."""
    ctype = str(chart.get("type", "line")).lower()
    if ctype == "bar":
        return _render_bar(chart)
    if ctype == "fan":
        return _render_fan(chart)
    if ctype == "scatter":
        return _render_line_or_scatter(chart, is_scatter=True)
    return _render_line_or_scatter(chart, is_scatter=False)
