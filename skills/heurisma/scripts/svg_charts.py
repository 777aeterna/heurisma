#!/usr/bin/env python3
"""Zero-dependency publication-grade SVG charting engine for Heurisma working papers.

Supports Heckbert nice-number ticks on both Y and numeric X axes, locale-aware
number/percent/currency formatting (en/es), horizontal gridlines, date & numeric
X-axes, multi-series line/scatter charts with Okabe-Ito colorblind-safe palette
& print-safe dash styles, automatic marker hiding for dense (>30 pt) or smooth
series, staggered non-overlapping vertical event annotations with right-edge flip
and truncation, white-halo reference labels, scatter y=0 lines & highlighted points,
shaded policy bands, localized 3-layer fan projection charts (P10-P90 / P25-P75 / P50),
grouped bar charts, optional log Y-scale, and <title>/<desc> accessibility.
"""

from __future__ import annotations

import datetime as _dt
import html
import math
import re
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

CHART_I18N: dict[str, dict[str, str]] = {
    "en": {
        "median": "Median (P50)",
        "no_data": "no data",
        "no_data_desc": "No data available for this figure.",
        "axis_truncated": "Truncated axis (does not start at 0)",
        "diff_vs": "Difference vs. {ref}",
        "last_data": "Last data: {x}",
    },
    "es": {
        "median": "Mediana (P50)",
        "no_data": "sin datos",
        "no_data_desc": "No hay datos disponibles para esta figura.",
        "axis_truncated": "Eje truncado (no parte de 0)",
        "diff_vs": "Diferencia vs. {ref}",
        "last_data": "Último dato: {x}",
    },
}

HALO_STYLE = "paint-order: stroke; stroke: #ffffff; stroke-width: 3px; stroke-linejoin: round;"


def _lang_dict(lang: str) -> dict[str, str]:
    return CHART_I18N.get((lang or "en").lower()[:2], CHART_I18N["en"])


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


def _apply_locale(num_str: str, lang: str) -> str:
    if (lang or "en").lower().startswith("es"):
        return num_str.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return num_str


def _format_num(v: float, fmt: str = "", lang: str = "en") -> str:
    fmt_l = (fmt or "").lower().strip()
    if fmt_l == "percent":
        pct = v * 100.0
        if abs(pct - round(pct)) < 1e-6:
            s = f"{int(round(pct)):,}%"
        else:
            s = f"{pct:,.1f}%"
        return _apply_locale(s, lang)

    if fmt_l == "currency":
        if abs(v) >= 1000 or abs(v - round(v)) < 1e-6:
            s = f"${v:,.0f}"
        else:
            s = f"${v:,.2f}"
        return _apply_locale(s, lang)

    if fmt_l == "thousands" or abs(v) >= 1000:
        if abs(v - round(v)) < 1e-6 or abs(v) >= 100:
            s = f"{v:,.0f}"
        else:
            s = f"{v:,.1f}"
        return _apply_locale(s, lang)

    if abs(v) >= 10 or v == int(v):
        s = f"{v:.4g}"
    else:
        s = f"{v:.3g}"
    return _apply_locale(s, lang)


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
    y_fmt: str = "",
    lang: str = "en",
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
            f'font-size="11" fill="#475569">{html.escape(_format_num(tv, y_fmt, lang))}</text>'
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


def _truncate_label(text: str, max_len: int = 16) -> str:
    s = text.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _wrap_label(text: str, max_chars: int = 18) -> list[str]:
    """Greedy word wrap for category labels. Words are never split, so an overlong word yields an overlong line."""
    lines: list[str] = []
    cur = ""
    for word in str(text).split():
        cand = f"{cur} {word}".strip()
        if cur and len(cand) > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines or [""]


def _clip_points(
    pts: list[tuple[float, float, str]], lo: float | None, hi: float | None, interpolate: bool = False
) -> list[tuple[float, float, str]]:
    """Keep points inside [lo, hi]; with ``interpolate`` also insert the boundary crossing (used for bands)."""
    if lo is None and hi is None:
        return pts
    out: list[tuple[float, float, str]] = []
    for i, p in enumerate(pts):
        if (lo is None or p[0] >= lo) and (hi is None or p[0] <= hi):
            out.append(p)
        if interpolate and i + 1 < len(pts):
            q = pts[i + 1]
            for bound in (lo, hi):
                if bound is not None and (p[0] - bound) * (q[0] - bound) < 0:
                    t = (bound - p[0]) / (q[0] - p[0])
                    out.append((bound, p[1] + t * (q[1] - p[1]), ""))
    out.sort(key=lambda item: item[0])
    return out


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}(?:-\d{2})?$")


def _last_data_position(
    x_cfg: dict[str, Any],
    parsed_series: list[tuple[str, list[tuple[float, float, str]], bool]],
    is_date: bool,
    synthetic: bool = False,
) -> tuple[float, str] | None:
    """Where the "last data" marker goes: (x value, label text), or None when it must not be drawn.

    ``x.last_label`` may be a date (the marker sits there), ``true`` plus ``x.observed_until`` (sits there), or
    ``true``/a text alone (sits on the last observed point). A fan chart's only series is the projected median,
    so without a date it has no observed point to mark (``synthetic``).
    """
    opt = x_cfg.get("last_label")
    if not opt:
        return None
    until = x_cfg.get("observed_until")
    if isinstance(opt, str) and _ISO_DATE_RE.match(opt.strip()):
        return _parse_x(opt.strip(), is_date), opt.strip()
    if until:
        label = opt if isinstance(opt, str) else str(until)
        return _parse_x(until, is_date), label
    if synthetic or not parsed_series:
        return None
    last_pt = max((p for _, pts, _ in parsed_series for p in pts), key=lambda p: p[0])
    return last_pt[0], (opt if isinstance(opt, str) else last_pt[2])


def _render_line_or_scatter(chart: dict[str, Any], is_scatter: bool = False, lang: str = "en") -> str:
    x_cfg = chart.get("x") or {}
    y_cfg = chart.get("y") or {}
    is_date = str(x_cfg.get("type", "")).lower() == "date"
    is_log = str(y_cfg.get("scale", "linear")).lower() == "log"
    x_label = str(x_cfg.get("label", chart.get("x_label", ""))).strip()
    y_label = str(y_cfg.get("label", chart.get("y_label", ""))).strip()
    x_fmt = str(x_cfg.get("format", ""))
    y_fmt = str(y_cfg.get("format", ""))

    width = 680
    pad_l, pad_r, pad_t = 68, 26, 38
    pad_b = 48 if x_label else 30
    height = 330 if x_label else 312
    plot_w = width - pad_l - pad_r

    # Normalize v1 & v2 series structure
    raw_series = chart.get("series") or []
    if not raw_series and chart.get("points"):
        raw_series = [{"name": chart.get("title", "Series"), "points": chart["points"]}]

    parsed_series: list[tuple[str, list[tuple[float, float, str]], bool]] = []
    all_x: list[float] = []
    all_y: list[float] = []

    # Optional x.min / x.max: clip the plotted range (e.g. trim the empty gap left by a projected band)
    lim_lo = _parse_x(x_cfg["min"], is_date) if x_cfg.get("min") is not None else None
    lim_hi = _parse_x(x_cfg["max"], is_date) if x_cfg.get("max") is not None else None

    for s in raw_series:
        pts = _clip_points(_extract_xy_points(s.get("points") or [], is_date), lim_lo, lim_hi)
        if pts:
            hide_markers = bool(s.get("hide_markers", False))
            parsed_series.append((str(s.get("name", "Series")), pts, hide_markers))
            all_x.extend(p[0] for p in pts)
            all_y.extend(p[1] for p in pts)

    # Include bands in bounds
    parsed_bands: list[tuple[str, list[tuple[float, float, str]], list[tuple[float, float, str]], float]] = []
    raw_bands = chart.get("bands") or []
    for b_idx, b in enumerate(raw_bands):
        lo_pts = _clip_points(_extract_xy_points(b.get("lower") or [], is_date), lim_lo, lim_hi, interpolate=True)
        hi_pts = _clip_points(_extract_xy_points(b.get("upper") or [], is_date), lim_lo, lim_hi, interpolate=True)
        if lo_pts and hi_pts:
            opacity = float(b.get("opacity", 0.16 if b_idx == 0 else 0.30))
            parsed_bands.append((str(b.get("name", "Band")), lo_pts, hi_pts, opacity))
            all_x.extend(p[0] for p in lo_pts + hi_pts)
            all_y.extend(p[1] for p in lo_pts + hi_pts)

    ref_lines = chart.get("reference_lines") or []
    for rl in ref_lines:
        if "value" in rl:
            all_y.append(float(rl["value"]))

    highlight = chart.get("highlight")
    if isinstance(highlight, dict) and "x" in highlight and "y" in highlight:
        all_x.append(_parse_x(highlight["x"], is_date))
        all_y.append(float(highlight["y"]))

    if not all_x or not all_y:
        return _empty_svg(chart, lang=lang)

    min_x, max_x = min(all_x), max(all_x)
    if lim_lo is not None:
        min_x = lim_lo
    if lim_hi is not None:
        max_x = lim_hi

    # X-axis ticks: snap multi-year dates to calendar years; use Heckbert nice_ticks for numeric axes
    if is_date:
        span_x = (max_x - min_x) or 1.0
        if span_x > 730:
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
    else:
        x_ticks = nice_ticks(min_x, max_x, max_ticks=5)
        min_x = lim_lo if lim_lo is not None else x_ticks[0]
        max_x = lim_hi if lim_hi is not None else x_ticks[-1]
        x_ticks = [t for t in x_ticks if min_x <= t <= max_x] or [min_x, max_x]
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
        # Tight Y-axis bounds: next nice tick containing the data without artificial overshoot
        y_ticks = nice_ticks(raw_min_y, raw_max_y, max_ticks=5)
        y_min_t, y_max_t = y_ticks[0], y_ticks[-1]

    els, y_px = _render_axes_and_grid(
        width,
        height,
        pad_l,
        pad_r,
        pad_t,
        pad_b,
        y_ticks,
        y_min_t,
        y_max_t,
        is_log,
        min_pos,
        y_label,
        y_fmt=y_fmt,
        lang=lang,
    )

    def x_px(xv: float) -> float:
        if span_x == 0:
            return pad_l + plot_w / 2.0
        return pad_l + (xv - min_x) / span_x * plot_w

    for tx in x_ticks:
        xp = x_px(tx)
        lbl = _format_date_ordinal(tx, span_x) if is_date else _format_num(tx, x_fmt, lang)
        els.append(
            f'<line x1="{xp:.1f}" y1="{height - pad_b}" x2="{xp:.1f}" y2="{height - pad_b + 5}" stroke="#334155"/>'
            f'<text x="{xp:.1f}" y="{height - pad_b + 18}" text-anchor="middle" font-size="11" fill="#475569">{html.escape(lbl)}</text>'
        )
    if x_label:
        els.append(
            f'<text x="{pad_l + plot_w / 2:.1f}" y="{height - 8}" text-anchor="middle" font-size="11" fill="#334155">{html.escape(x_label)}</text>'
        )

    # R4/C6: optional "last data" marker at the last observed date (x.last_label / x.observed_until)
    last_pos = _last_data_position(x_cfg, parsed_series, is_date, synthetic=bool(chart.get("_fan")))
    if last_pos is not None and min_x - span_x * 1e-9 <= last_pos[0] <= max_x + span_x * 1e-9:
        lx = x_px(last_pos[0])
        txt = _lang_dict(lang)["last_data"].format(x=last_pos[1])
        fits_left = lx - 4 - len(txt) * 5.3 >= pad_l
        tx, anchor = (lx - 4, "end") if fits_left else (lx + 4, "start")
        els.append(
            f'<line data-last-data="x" x1="{lx:.1f}" y1="{pad_t}" x2="{lx:.1f}" y2="{height - pad_b}" '
            f'stroke="#94a3b8" stroke-dasharray="1,3" stroke-width="1"/>'
            f'<text x="{tx:.1f}" y="{height - pad_b - 6}" text-anchor="{anchor}" font-size="9.5" '
            f'fill="#475569" style="{HALO_STYLE}">{html.escape(txt)}</text>'
        )

    # Shaded bands behind series
    for b_name, lo_pts, hi_pts, opacity in parsed_bands:
        poly_pts = [(x_px(p[0]), y_px(p[1])) for p in hi_pts] + [
            (x_px(p[0]), y_px(p[1])) for p in reversed(lo_pts)
        ]
        coord_str = " ".join(f"{px:.1f},{py:.1f}" for px, py in poly_pts)
        els.append(f'<polygon points="{coord_str}" fill="#0072B2" fill-opacity="{opacity:.2f}" stroke="none"/>')

    # Scatter zero line (y = 0) when 0 lies inside the Y range
    if is_scatter and not is_log and y_min_t < 0.0 < y_max_t:
        zy = y_px(0.0)
        els.append(
            f'<line data-zero-line="y" x1="{pad_l}" y1="{zy:.1f}" x2="{width - pad_r}" y2="{zy:.1f}" '
            f'stroke="#64748b" stroke-dasharray="4,3" stroke-width="1.1"/>'
        )

    # Vertical event annotations (sorted by X, staggered into up to 3 vertical levels, right-edge flip, 16-char truncation)
    raw_anns: list[tuple[float, str]] = []
    for ann in chart.get("annotations") or []:
        ax = _parse_x(ann.get("x", 0), is_date)
        if min_x <= ax <= max_x:
            raw_anns.append((x_px(ax), _truncate_label(str(ann.get("label", "")), 16)))
    raw_anns.sort(key=lambda item: item[0])

    level_ys = (pad_t + 12, pad_t + 25, pad_t + 38)
    level_spans: list[list[tuple[float, float]]] = [[], [], []]
    for xp, albl in raw_anns:
        est_w = max(24.0, len(albl) * 6.0 + 4.0)
        if xp + 4.0 + est_w > width - pad_r:
            anchor = "end"
            tx = xp - 4.0
            span = (tx - est_w, tx)
        else:
            anchor = "start"
            tx = xp + 4.0
            span = (tx, tx + est_w)

        chosen_level = 0
        for lvl_idx in range(len(level_ys)):
            if all(span[1] + 4.0 < lo or span[0] - 4.0 > hi for lo, hi in level_spans[lvl_idx]):
                chosen_level = lvl_idx
                break
        else:
            chosen_level = min(
                range(len(level_ys)),
                key=lambda idx: max((hi for _, hi in level_spans[idx]), default=-1e9),
            )
        level_spans[chosen_level].append(span)
        ty = level_ys[chosen_level]
        els.append(
            f'<line x1="{xp:.1f}" y1="{pad_t}" x2="{xp:.1f}" y2="{height - pad_b}" '
            f'stroke="#64748b" stroke-dasharray="3,3" stroke-width="1"/>'
            f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}" font-size="10" fill="#334155" '
            f'style="{HALO_STYLE}">{html.escape(albl)}</text>'
        )

    # Plot series (hide circles when dense >30 pts or hide_markers=True)
    legend_items: list[tuple[str, str, str, str, float]] = []
    for idx, (s_name, pts, hide_markers) in enumerate(parsed_series):
        color = OKABE_ITO[idx % len(OKABE_ITO)]
        dash = DASH_STYLES[idx % len(DASH_STYLES)]
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        legend_items.append(("line", s_name, color, dash, 1.0))

        if not is_scatter and len(pts) > 1:
            poly = " ".join(f"{x_px(p[0]):.1f},{y_px(p[1]):.1f}" for p in pts)
            els.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2.2"{dash_attr} points="{poly}"/>'
            )

        if (is_scatter or len(pts) <= 30) and not hide_markers:
            radius = 4.0 if is_scatter else 3.0
            for p in pts:
                els.append(
                    f'<circle cx="{x_px(p[0]):.1f}" cy="{y_px(p[1]):.1f}" r="{radius}" '
                    f'fill="{color}" stroke="#ffffff" stroke-width="0.8"/>'
                )

    # Reference horizontal lines (drawn after series with white-halo labels for legibility)
    for rl in ref_lines:
        if "value" in rl:
            ry = y_px(float(rl["value"]))
            raw_name = str(rl.get("name", ""))
            rname = html.escape(raw_name)
            label_svg = ""
            if raw_name:
                # R2: semi-transparent white box behind the label so the series line never runs through the text
                box_w = len(raw_name) * 5.6 + 6.0
                box_x = width - pad_r - 4 - box_w + 3.0
                label_svg = (
                    f'<rect class="ref-label-bg" x="{box_x:.1f}" y="{ry - 15:.1f}" width="{box_w:.1f}" height="13" '
                    f'rx="2" fill="#ffffff" fill-opacity="0.85"/>'
                    f'<text x="{width - pad_r - 4}" y="{ry - 4:.1f}" text-anchor="end" font-size="10" '
                    f'fill="#334155" style="{HALO_STYLE}">{rname}</text>'
                )
            els.append(
                f'<line x1="{pad_l}" y1="{ry:.1f}" x2="{width - pad_r}" y2="{ry:.1f}" '
                f'stroke="#64748b" stroke-dasharray="4,4" stroke-width="1.2"/>' + label_svg
            )

    # Optional highlighted observation (e.g. current period on scatter)
    if isinstance(highlight, dict) and "x" in highlight and "y" in highlight:
        hx = x_px(_parse_x(highlight["x"], is_date))
        hy = y_px(float(highlight["y"]))
        hlbl = str(highlight.get("label", "")).strip()
        els.append(
            f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="5.5" fill="#D55E00" stroke="#ffffff" stroke-width="1.5"/>'
        )
        if hlbl:
            est_w = len(hlbl) * 6.2 + 8.0
            if hx + 8.0 + est_w > width - pad_r:
                h_anchor, htx = "end", hx - 8.0
            else:
                h_anchor, htx = "start", hx + 8.0
            els.append(
                f'<text x="{htx:.1f}" y="{hy + 3.5:.1f}" text-anchor="{h_anchor}" font-size="10.5" '
                f'font-weight="600" fill="#D55E00" style="{HALO_STYLE}">{html.escape(hlbl)}</text>'
            )

    # Add bands to legend (e.g. fan chart 3-layer legend: Median, P25-P75, P10-P90)
    for b_name, _, _, opacity in parsed_bands:
        legend_items.append(("band", b_name, "#0072B2", "", opacity))

    # Legend (top-right when multiple series or bands)
    if len(legend_items) > 1 or parsed_bands:
        lx = width - pad_r
        ly = 16
        for kind, s_name, color, dash, opacity in reversed(legend_items):
            lbl = html.escape(s_name)
            w_est = max(58, len(s_name) * 6.2 + 24)
            lx -= w_est
            if kind == "band":
                els.append(
                    f'<rect x="{lx:.1f}" y="{ly - 8}" width="14" height="9" rx="1.5" '
                    f'fill="{color}" fill-opacity="{opacity:.2f}" stroke="{color}" stroke-opacity="0.45" stroke-width="0.6"/>'
                    f'<text x="{lx + 18:.1f}" y="{ly}" font-size="10.5" fill="#1e293b">{lbl}</text>'
                )
            else:
                dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
                els.append(
                    f'<line x1="{lx:.1f}" y1="{ly - 3}" x2="{lx + 16:.1f}" y2="{ly - 3}" '
                    f'stroke="{color}" stroke-width="2.2"{dash_attr}/>'
                    f'<text x="{lx + 20:.1f}" y="{ly}" font-size="10.5" fill="#1e293b">{lbl}</text>'
                )

    return _wrap_svg(chart, width, height, els)


def _render_fan(chart: dict[str, Any], lang: str = "en") -> str:
    """Render fan chart (P10-P90 outer band, P25-P75 inner band, localized P50 median line without markers)."""
    q = chart.get("quantiles") or {}
    if not q or "p50" not in q:
        return _empty_svg(chart, lang=lang)

    i18n = _lang_dict(lang)
    synth = dict(chart)
    synth["type"] = "line"
    synth["series"] = [{"name": i18n["median"], "points": q["p50"], "hide_markers": True}]
    synth["_fan"] = True  # the only series is the projected median: last_label needs observed_until
    bands = list(chart.get("bands") or [])
    if "p10" in q and "p90" in q:
        bands.append({"name": "P10–P90", "lower": q["p10"], "upper": q["p90"], "opacity": 0.14})
    if "p25" in q and "p75" in q:
        bands.append({"name": "P25–P75", "lower": q["p25"], "upper": q["p75"], "opacity": 0.28})
    synth["bands"] = bands
    return _render_line_or_scatter(synth, is_scatter=False, lang=lang)


def _parse_bar_data(chart: dict[str, Any]) -> tuple[list[str], list[tuple[str, list[float]]], bool] | None:
    """Return (group_labels, [(series_name, values)], is_flat) for v2 grouped or v1 flat bar charts, or None."""
    groups = chart.get("groups")
    raw_series = chart.get("series") or []
    if groups and raw_series and "values" in raw_series[0]:
        group_labels = [str(g) for g in groups]
        series_list = [
            (str(s.get("name", f"S{i + 1}")), [float(v) for v in s.get("values") or []])
            for i, s in enumerate(raw_series)
        ]
        return group_labels, series_list, False
    if raw_series and "value" in raw_series[0]:
        group_labels = [str(s.get("label", f"#{i + 1}")) for i, s in enumerate(raw_series)]
        return group_labels, [("", [float(s.get("value", 0.0)) for s in raw_series])], True
    return None


def _to_relative_diff(
    group_labels: list[str], series_list: list[tuple[str, list[float]]], flat: bool
) -> tuple[list[str], list[tuple[str, list[float]]], str] | None:
    """Relative difference vs. the first bar (flat) or vs. the first series within each group (grouped)."""
    if flat:
        vals = series_list[0][1]
        if not vals or vals[0] == 0:
            return None
        return group_labels, [("", [(v - vals[0]) / vals[0] for v in vals])], group_labels[0]
    if len(series_list) < 2:
        return None
    ref_name, ref_vals = series_list[0]
    rel = [
        (name, [((v - ref_vals[g]) / ref_vals[g]) if g < len(ref_vals) and ref_vals[g] else 0.0 for g, v in enumerate(vals)])
        for name, vals in series_list[1:]
    ]
    return group_labels, rel, ref_name


def _spread_is_negligible(vals: list[float]) -> bool:
    biggest = max((abs(v) for v in vals), default=0.0)
    return len(vals) >= 2 and biggest > 0 and (max(vals) - min(vals)) < 0.01 * biggest


def chart_warnings(chart: dict[str, Any], lang: str = "en") -> list[str]:
    """Design warnings for a chart dict (the validator surfaces them): near-identical bars (G2) and a fan chart
    whose "last data" marker has no date to sit on (C6)."""
    ctype = str(chart.get("type", "")).lower()
    if ctype == "fan":
        x_cfg = chart.get("x") or {}
        opt = x_cfg.get("last_label")
        has_date = isinstance(opt, str) and bool(_ISO_DATE_RE.match(opt.strip()))
        if opt and not has_date and not x_cfg.get("observed_until"):
            return [
                f"Chart '{chart.get('id', '?')}': fan chart has last_label but no observed_until; add "
                f"x.observed_until (the last observed date) or give last_label as a date."
            ]
        return []
    if ctype != "bar":
        return []
    if chart.get("diff") or (chart.get("y") or {}).get("baseline") is not None:
        return []
    parsed = _parse_bar_data(chart)
    if parsed is None:
        return []
    group_labels, series_list, flat = parsed
    if flat:
        clusters = [series_list[0][1]]
    else:
        clusters = [
            [vals[g] for _, vals in series_list if g < len(vals)] for g in range(len(group_labels))
        ]
    if any(_spread_is_negligible(c) for c in clusters):
        return [
            f"Chart '{chart.get('id', '?')}': near-identical bars (spread < 1% of the largest value) show no visible "
            f"difference; set y.baseline (a truncated-axis notice is drawn) or diff: true."
        ]
    return []


def _bar_legend(series_list: list[tuple[str, list[float]]], width: int, pad_r: int) -> list[str]:
    els: list[str] = []
    lx = width - pad_r
    ly = 16
    for s_idx in range(len(series_list) - 1, -1, -1):
        s_name = html.escape(series_list[s_idx][0])
        color = OKABE_ITO[s_idx % len(OKABE_ITO)]
        w_est = max(65, len(series_list[s_idx][0]) * 6.5 + 22)
        lx -= w_est
        els.append(
            f'<rect x="{lx:.1f}" y="{ly - 9}" width="11" height="11" rx="2" fill="{color}"/>'
            f'<text x="{lx + 15:.1f}" y="{ly}" font-size="10.5" fill="#1e293b">{s_name}</text>'
        )
    return els


def _bar_color(n_series: int, s_idx: int, v: float) -> str:
    return OKABE_ITO[s_idx % len(OKABE_ITO)] if n_series > 1 else (OKABE_ITO[0] if v >= 0 else OKABE_ITO[1])


def _axis_warning(width: int, pad_r: int, y: float, text: str) -> str:
    return (
        f'<text class="axis-warning" x="{width - pad_r}" y="{y:.1f}" text-anchor="end" font-size="10" '
        f'fill="#b45309">\u26a0 {html.escape(text)}</text>'
    )


_NEG_HEADROOM = 0.12  # extra axis room (fraction of the range) below negative bars so value labels stay clear
_WARN_ROW = 16  # extra bottom padding for the truncated-axis notice


def _padded_low(min_v: float, max_v: float, base_val: float) -> float:
    return min_v - _NEG_HEADROOM * (max_v - min_v) if min_v < base_val else min_v


def _render_bar_horizontal(
    chart: dict[str, Any],
    group_labels: list[str],
    series_list: list[tuple[str, list[float]]],
    y_label: str,
    y_fmt: str,
    base_val: float,
    truncated: bool,
    lang: str,
) -> str:
    """Horizontal bars: category labels sit on the left (wrapped), so long labels never collide."""
    i18n = _lang_dict(lang)
    width, pad_t, pad_b, pad_r = 680, 38, 30, 48
    wrapped = []
    for g in group_labels:
        lines = _wrap_label(g, 30)[:3]
        wrapped.append([_truncate_label(ln, 30) if len(ln) > 30 else ln for ln in lines])
    longest = max(len(ln) for w in wrapped for ln in w)
    pad_l = int(max(90, min(250, longest * 6.2 + 16)))
    plot_w = width - pad_l - pad_r
    n_series = len(series_list)
    bar_h, gap = 14.0, 3.0
    slot_h = max(26.0, max(len(w) for w in wrapped) * 13.0 + 6.0, n_series * (bar_h + gap) + 10.0)
    height = int(pad_t + slot_h * len(group_labels) + pad_b + (_WARN_ROW if truncated else 0))

    all_vals = [v for _, vals in series_list for v in vals]
    lo_v, hi_v = min(base_val, min(all_vals)), max(base_val, max(all_vals))
    ticks = nice_ticks(_padded_low(lo_v, hi_v, base_val), hi_v, max_ticks=5)
    lo, hi = ticks[0], ticks[-1]
    span = (hi - lo) or 1.0

    def x_px(v: float) -> float:
        return pad_l + (v - lo) / span * plot_w

    plot_bottom = height - pad_b - (_WARN_ROW if truncated else 0)
    els: list[str] = ['<g data-bar-layout="horizontal"></g>']
    for tv in ticks:
        xp = x_px(tv)
        els.append(
            f'<line x1="{xp:.1f}" y1="{pad_t}" x2="{xp:.1f}" y2="{plot_bottom}" stroke="#e2e8f0" stroke-width="1"/>'
            f'<text x="{xp:.1f}" y="{plot_bottom + 16}" text-anchor="middle" font-size="11" fill="#475569">'
            f'{html.escape(_format_num(tv, y_fmt, lang))}</text>'
        )
    x0 = x_px(base_val)
    els.append(f'<line x1="{x0:.1f}" y1="{pad_t}" x2="{x0:.1f}" y2="{plot_bottom}" stroke="#334155" stroke-width="1.2"/>')
    if y_label:
        els.append(
            f'<text x="{pad_l}" y="{pad_t - 10}" text-anchor="start" font-size="11" font-weight="600" '
            f'fill="#334155">{html.escape(y_label)}</text>'
        )
    if truncated:
        els.append(_axis_warning(width, pad_r, height - 5, i18n["axis_truncated"]))

    for g_idx, lines in enumerate(wrapped):
        cy = pad_t + (g_idx + 0.5) * slot_h
        first_y = cy - (len(lines) - 1) * 6.5 + 4.0
        for li, ln in enumerate(lines):
            els.append(
                f'<text class="cat-label" data-group="{g_idx}" x="{pad_l - 8}" y="{first_y + li * 13.0:.1f}" '
                f'text-anchor="end" font-size="11" fill="#334155">{html.escape(ln)}</text>'
            )
        total_h = n_series * bar_h + (n_series - 1) * gap
        for s_idx, (_, vals) in enumerate(series_list):
            if g_idx >= len(vals):
                continue
            v = vals[g_idx]
            xv = x_px(v)
            by = cy - total_h / 2.0 + s_idx * (bar_h + gap)
            bx = min(xv, x0)
            bw = abs(xv - x0)
            color = _bar_color(n_series, s_idx, v)
            text_x = xv + 5 if v >= base_val else xv - 5
            anchor = "start" if v >= base_val else "end"
            els.append(
                f'<rect class="bar" data-value="{v}" x="{bx:.1f}" y="{by:.1f}" width="{max(1.5, bw):.1f}" '
                f'height="{bar_h:.1f}" rx="2" fill="{color}"/>'
                f'<text x="{text_x:.1f}" y="{by + bar_h - 3:.1f}" text-anchor="{anchor}" font-size="10" fill="#1e293b">'
                f'{html.escape(_format_num(v, y_fmt, lang))}</text>'
            )
    if n_series > 1:
        els.extend(_bar_legend(series_list, width, pad_r))
    return _wrap_svg(chart, width, height, els)


def _render_bar(chart: dict[str, Any], lang: str = "en") -> str:
    i18n = _lang_dict(lang)
    y_cfg = chart.get("y") or {}
    y_label = str(y_cfg.get("label", chart.get("y_label", ""))).strip()
    y_fmt = str(y_cfg.get("format", ""))

    parsed = _parse_bar_data(chart)
    if parsed is None:
        return _empty_svg(chart, lang=lang)
    group_labels, series_list, flat = parsed
    if not [v for _, vals in series_list for v in vals]:
        return _empty_svg(chart, lang=lang)

    base_val = 0.0
    truncated = False
    if chart.get("diff"):
        rel = _to_relative_diff(group_labels, series_list, flat)
        if rel is not None:
            group_labels, series_list, ref_label = rel
            y_fmt = "percent"
            y_label = i18n["diff_vs"].format(ref=ref_label)
    elif y_cfg.get("baseline") is not None:
        base_val = float(y_cfg["baseline"])
        truncated = base_val != 0.0

    all_vals = [v for _, vals in series_list for v in vals]
    n_groups = len(group_labels)
    n_series = len(series_list)

    width = 680
    pad_l, pad_r, pad_t = 68, 24, 38
    plot_w = width - pad_l - pad_r
    slot_w = plot_w / max(1, n_groups)
    max_chars = max(6, int((slot_w - 6.0) // 6.2))
    wrapped = [_wrap_label(g, max_chars) for g in group_labels]
    fits = all(len(w) <= 3 and all(len(ln) <= max_chars for ln in w) for w in wrapped)
    if not fits:
        return _render_bar_horizontal(chart, group_labels, series_list, y_label, y_fmt, base_val, truncated, lang)

    extra_lines = max(len(w) for w in wrapped) - 1
    warn_row = _WARN_ROW if truncated else 0
    pad_b = 36 + 13 * extra_lines + warn_row
    height = 304 + 13 * extra_lines + warn_row

    min_v = min(base_val, min(all_vals))
    max_v = max(base_val, max(all_vals))
    y_ticks = nice_ticks(_padded_low(min_v, max_v, base_val), max_v, max_ticks=5)
    els, y_px = _render_axes_and_grid(
        width, height, pad_l, pad_r, pad_t, pad_b, y_ticks, y_ticks[0], y_ticks[-1],
        False, 1.0, y_label, y_fmt=y_fmt, lang=lang,
    )
    els.insert(0, '<g data-bar-layout="vertical"></g>')
    if truncated:
        els.append(_axis_warning(width, pad_r, height - 5, i18n["axis_truncated"]))

    zero_y = y_px(base_val)
    els.append(
        f'<line x1="{pad_l}" y1="{zero_y:.1f}" x2="{width - pad_r}" y2="{zero_y:.1f}" '
        f'stroke="#334155" stroke-width="1.2"/>'
    )

    cluster_w = slot_w * 0.72
    bar_w = max(10.0, min(56.0, cluster_w / max(1, n_series) - 3.0))

    for g_idx, g_lines in enumerate(wrapped):
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
            color = _bar_color(n_series, s_idx, v - base_val)
            val_y = top - 5 if v >= base_val else top + bh + 12
            els.append(
                f'<rect class="bar" data-value="{v}" x="{bx:.1f}" y="{top:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                f'rx="2" fill="{color}"/>'
                f'<text x="{bx + bar_w / 2:.1f}" y="{val_y:.1f}" text-anchor="middle" font-size="10" fill="#1e293b">'
                f'{html.escape(_format_num(v, y_fmt, lang))}</text>'
            )
        for li, ln in enumerate(g_lines):
            els.append(
                f'<text class="cat-label" data-group="{g_idx}" x="{g_center:.1f}" '
                f'y="{height - pad_b + 18 + 13 * li}" text-anchor="middle" font-size="11" fill="#334155">'
                f'{html.escape(ln)}</text>'
            )

    if n_series > 1:
        els.extend(_bar_legend(series_list, width, pad_r))

    return _wrap_svg(chart, width, height, els)


def _empty_svg(chart: dict[str, Any], lang: str = "en") -> str:
    i18n = _lang_dict(lang)
    title = html.escape(str(chart.get("title", "Figure")))
    return (
        f'<svg viewBox="0 0 680 120" width="100%" role="img">'
        f"<title>{title}</title><desc>{html.escape(i18n['no_data_desc'])}</desc>"
        f'<text x="340" y="64" text-anchor="middle" font-size="12" fill="#64748b">{title} ({html.escape(i18n["no_data"])})</text>'
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


def render_chart_svg(chart: dict[str, Any], lang: str = "en") -> str:
    """Dispatch chart dict (v2 or v1 schema) to the appropriate SVG renderer."""
    ctype = str(chart.get("type", "line")).lower()
    if ctype == "bar":
        return _render_bar(chart, lang=lang)
    if ctype == "fan":
        return _render_fan(chart, lang=lang)
    if ctype == "scatter":
        return _render_line_or_scatter(chart, is_scatter=True, lang=lang)
    return _render_line_or_scatter(chart, is_scatter=False, lang=lang)
