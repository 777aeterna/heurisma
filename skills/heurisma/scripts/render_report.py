#!/usr/bin/env python3
"""Zero-dependency working-paper HTML + inline SVG renderer for Heurisma reports.

Produces a lightweight, print-ready academic working-paper HTML5 document
(serif typography, 720px single column, booktabs tables, sober small-caps
epistemic tags, inline numbered {{fig:id}} SVG figures, linked [@C1] citations
ordered by appearance, full en/es localization, currency-safe inline LaTeX
conversion, nested lists, deduplicated Abstract, {{num:key}} substitution,
@media print A4 CSS, and strict appendix filtering excluding raw data/binaries
and >200 KB files).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

# Ensure sibling modules can be imported when invoked as a script (including under python -I)
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from contracts import __version__  # noqa: E402
import svg_charts  # noqa: E402

TAG_MAP: dict[str, tuple[str, str]] = {
    "[Strong]": ("tag-strong", "strong"),
    "[Moderate]": ("tag-moderate", "moderate"),
    "[Preliminary]": ("tag-preliminary", "preliminary"),
    "[Speculative]": ("tag-speculative", "speculative"),
    "[Fuerte]": ("tag-strong", "fuerte"),
    "[Moderada]": ("tag-moderate", "moderada"),
    "[Moderado]": ("tag-moderate", "moderado"),
    "[Preliminar]": ("tag-preliminary", "preliminar"),
    "[Especulativa]": ("tag-speculative", "especulativa"),
    "[Especulativo]": ("tag-speculative", "especulativo"),
}

I18N: dict[str, dict[str, str]] = {
    "en": {
        "figure": "Figure",
        "note": "Note:",
        "source": "Source:",
        "fig_data_preview": "Figure data preview",
        "abstract": "Abstract",
        "falsifier": "Falsifier:",
        "references": "References",
        "appendices": "Appendices &amp; Reproducible Artifacts",
        "external_files": "External Data &amp; Large Files (Linked, Not Embedded)",
        "external_artifact": "external artifact",
        "self_review": "self-review, not independent",
        "additional_figures": "Additional Figures",
        "credit": "Prepared with Heurisma",
        "data_as_of": "data as of",
        "accessed": "accessed",
        "untitled_source": "Untitled source",
        "group": "Group",
        "label": "Label",
        "value": "Value",
        "local_file": "local file",
    },
    "es": {
        "figure": "Figura",
        "note": "Nota:",
        "source": "Fuente:",
        "fig_data_preview": "Ver datos de la figura",
        "abstract": "Resumen",
        "falsifier": "Falsador:",
        "references": "Referencias",
        "appendices": "Apéndices y artefactos reproducibles",
        "external_files": "Datos externos y archivos grandes (enlazados, no incrustados)",
        "external_artifact": "artefacto externo",
        "self_review": "auto-revisión, no independiente",
        "additional_figures": "Figuras adicionales",
        "credit": "Preparado con Heurisma",
        "data_as_of": "datos al",
        "accessed": "consultado",
        "untitled_source": "Fuente sin título",
        "group": "Grupo",
        "label": "Etiqueta",
        "value": "Valor",
        "local_file": "archivo local",
    },
}

LATEX_SYMBOLS: tuple[tuple[str, str], ...] = (
    (r"\leq", "≤"),
    (r"\le", "≤"),
    (r"\geq", "≥"),
    (r"\ge", "≥"),
    (r"\neq", "≠"),
    (r"\ne", "≠"),
    (r"\times", "×"),
    (r"\approx", "≈"),
    (r"\pm", "±"),
    (r"\Delta", "Δ"),
    (r"\alpha", "α"),
    (r"\beta", "β"),
    (r"\rho", "ρ"),
    (r"\sigma", "σ"),
    (r"\mu", "μ"),
    (r"\pi", "π"),
    (r"\infty", "∞"),
    (r"\cdot", "·"),
    (r"\rightarrow", "→"),
    (r"\to", "→"),
)

MAX_APPENDIX_FILE_BYTES = 200 * 1024
ALLOWED_APPENDIX_FILES = {"output.txt", "sources.csv", "data_attempts.csv", "README.md", "numbers.json"}
FIG_MARKER_RE = re.compile(r"^\{\{fig:([A-Za-z0-9_-]+)\}\}$")
NUM_MARKER_RE = re.compile(r"\{\{num:([A-Za-z0-9_.-]+)\}\}")
NUMERIC_CELL_RE = re.compile(r"^[+\-−]?\s*[$€%]?\s*[\d.,]+(?:\s*[%x×])?$")
INLINE_MATH_RE = re.compile(r"(?<!\\)\$(?!\s)(?!\d[\d.,]*(?:\s|$|[^\\_^=a-zA-Z]))([^$\n]+?)(?<!\s)\$")
CITE_GROUP_RE = re.compile(r"\[(@[A-Za-z0-9_.-]+(?:\s*[;,]\s*@[A-Za-z0-9_.-]+)*)\]")
VERDICT_LINE_RE = re.compile(
    r"^\s*[-*]\s*\*{0,2}(?:Calibrated Verdict|Veredicto calibrado)\s*:\*{0,2}\s*(.+)$",
    re.IGNORECASE,
)
ABSTRACT_QUOTE_RE = re.compile(
    r"^>\s*\*{0,2}(?:Abstract|Resumen)\s*:\*{0,2}\s*(.+)$",
    re.IGNORECASE,
)


def detect_language(report_md: str, lang: str = "auto") -> str:
    """Resolve report language ('en' or 'es') from explicit flag or Spanish section headings."""
    if lang and lang.lower() in ("en", "es"):
        return lang.lower()
    if re.search(
        r"^##\s+(?:1\.\s+Resumen\s+ejecutivo|4\.\s+Hallazgos|6\.\s+Matriz\s+de\s+afirmaciones|7\.\s+Limitaciones)\b",
        report_md,
        flags=re.MULTILINE | re.IGNORECASE,
    ):
        return "es"
    return "en"


FILE_URI_RE = re.compile(r"file://[^\s,\"'<>)]+")
LOCAL_TITLE_SUFFIX_RE = re.compile(r"\s*\((?:local file|archivo local)[^)]*\)", re.IGNORECASE)
SHA_IN_TEXT_RE = re.compile(r"sha256\s+([0-9a-fA-F]{6,64})", re.IGNORECASE)
_SUP_PAREN_RE = re.compile(r"(?<=[A-Za-z0-9)\]])\^\(([^()\s]{1,16})\)")
_SUP_NUM_RE = re.compile(r"(?<=[A-Za-z0-9)\]])\^([-\u2212+]?\d+(?:\.\d+)?)(?![\w^])")
_SCI_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)[eE]([+\-\u2212]?\d+)(?!\w|\.\d)")
_NEG_NUMBER_RE = re.compile(r"(?<![\w.])-(?=\d)")


def _typographic_minus(value: str) -> str:
    """Turn a leading ASCII hyphen-minus before a digit into U+2212 (never touches ranges like 2026-12)."""
    return _NEG_NUMBER_RE.sub("\u2212", value)


def _apply_scientific_notation(text: str) -> str:
    """Render x^2, N^(-1/2) and 3e-08 with <sup>; deliberately narrow so paths, ids and hashes stay intact."""
    out = _SUP_PAREN_RE.sub(lambda m: f"<sup>{m.group(1).replace('-', chr(0x2212))}</sup>", text)
    out = _SUP_NUM_RE.sub(lambda m: f"<sup>{m.group(1).replace('-', chr(0x2212)).lstrip('+')}</sup>", out)

    def _sci(m: re.Match[str]) -> str:
        exp = int(m.group(2).replace("\u2212", "-"))
        sign = "\u2212" if exp < 0 else ""
        return f"{m.group(1)}\u00d710<sup>{sign}{abs(exp)}</sup>"

    return _SCI_RE.sub(_sci, out)


def _redact_local_paths(text: str) -> str:
    """Replace absolute file:// URIs with their basename so reports never leak the author's home directory."""
    return FILE_URI_RE.sub(lambda m: "file://" + Path(unquote(m.group(0)[len("file://"):])).name, text)


def _convert_math_expr(expr: str) -> str:
    out = expr
    for cmd, sym in LATEX_SYMBOLS:
        out = re.sub(re.escape(cmd) + r"(?![A-Za-z])", sym, out)
    out = re.sub(r"_\{([^}]+)\}", r"<sub>\1</sub>", out)
    out = re.sub(r"_([A-Za-z0-9]+)", r"<sub>\1</sub>", out)
    out = re.sub(r"\^\{([^}]+)\}", r"<sup>\1</sup>", out)
    out = re.sub(r"\^([A-Za-z0-9+-]+)", r"<sup>\1</sup>", out)
    return out


class _CitationTracker:
    """Tracks [@claim_id] citations in order of appearance against sources.csv."""

    def __init__(self, sources: list[dict[str, str]]) -> None:
        self.sources = sources
        self.by_id: dict[str, dict[str, str]] = {}
        for row in sources:
            cid = (row.get("claim_id") or "").strip()
            if cid and cid not in self.by_id:
                self.by_id[cid] = row
        self.order: list[str] = []
        self.num_by_id: dict[str, int] = {}

    def cite_match(self, match: re.Match[str]) -> str:
        raw_group = match.group(1)
        tokens = [t.strip().lstrip("@") for t in re.split(r"\s*[;,]\s*", raw_group) if t.strip()]
        rendered: list[str] = []
        for cid in tokens:
            if cid in self.by_id:
                if cid not in self.num_by_id:
                    self.order.append(cid)
                    self.num_by_id[cid] = len(self.order)
                num = self.num_by_id[cid]
                rendered.append(f'<a href="#ref-{num}">[{num}]</a>')
            else:
                rendered.append(f"[@{html.escape(cid)}]")
        return ", ".join(rendered)


def _load_sources(appendix_dir: Path | None) -> list[dict[str, str]]:
    if appendix_dir is None:
        return []
    src_csv = appendix_dir / "sources.csv"
    if not src_csv.is_file():
        return []
    try:
        with src_csv.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


_BALANCED_URL = r"((?:[^()\s]|\([^()]*\))*)"
_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(" + _BALANCED_URL + r"\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(" + _BALANCED_URL + r"\)")
_AUTOLINK_RE = re.compile(r"&lt;(https?://(?:(?!&gt;)\S)+)&gt;")
_SAFE_SCHEMES = {"http", "https", "mailto"}
_FENCED_SEGMENT_RE = re.compile(r"(^```.*?^```[ \t]*$)", re.MULTILINE | re.DOTALL)


def _is_safe_url(escaped_url: str) -> bool:
    """Allow http(s), mailto, #fragments and relative paths; reject javascript:, data:, vbscript:, protocol-relative."""
    u = re.sub(r"[\x00-\x20]", "", html.unescape(escaped_url))
    if not u or u.startswith("//"):
        return False
    m = re.match(r"([A-Za-z][A-Za-z0-9+.\-]*):", u)
    return m is None or m.group(1).lower() in _SAFE_SCHEMES


def _split_table_cells(row: str) -> list[str]:
    """Split a Markdown table row on unescaped pipes; ``\\|`` stays inside its cell."""
    inner = row.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", inner)]


def _substitute_markers(report_md: str, nums: dict[str, Any]) -> str:
    """Replace {{num:key}} outside fenced code blocks (the validator ignores fenced code too)."""
    parts = _FENCED_SEGMENT_RE.split(report_md)
    for i in range(0, len(parts), 2):  # even parts are outside fences
        parts[i] = NUM_MARKER_RE.sub(
            lambda m: _typographic_minus(str(nums[m.group(1)])) if m.group(1) in nums else m.group(0), parts[i]
        )
    return "".join(parts)


def _format_inline(text: str, tracker: _CitationTracker | None = None) -> str:
    escaped = html.escape(text)
    # Strip backticks around canonical epistemic tags so they render as small-caps tags
    escaped = re.sub(
        r"`(\[(?:Strong|Moderate|Preliminary|Speculative|Fuerte|Moderada|Moderado|Preliminar|Especulativa|Especulativo)\])`",
        r"\1",
        escaped,
    )

    # Protect inline code spans from math/emphasis/citation transformations
    code_spans: list[str] = []

    def _stash_code(m: re.Match[str]) -> str:
        idx = len(code_spans)
        code_spans.append(f"<code>{m.group(1)}</code>")
        return f"\x00CODE{idx}\x00"

    escaped = re.sub(r"`([^`]+)`", _stash_code, escaped)

    # Convert inline LaTeX math ($H_0$, $x^2$, $\Delta$) while preserving currency ($1.563, $1,200-$1,400)
    escaped = INLINE_MATH_RE.sub(lambda m: _convert_math_expr(m.group(1)), escaped)

    # Superscripts / scientific notation, with URLs and link targets protected
    url_spans: list[str] = []

    def _stash_url(m: re.Match[str]) -> str:
        url_spans.append(m.group(0))
        return f"\x00URL{len(url_spans) - 1}\x00"

    escaped = re.sub(r"\]\((?:[^()\s]|\([^()]*\))*\)|https?://[^\s<>)\"]+", _stash_url, escaped)
    escaped = _apply_scientific_notation(escaped)
    for idx, url_text in enumerate(url_spans):
        escaped = escaped.replace(f"\x00URL{idx}\x00", url_text)

    # Convert in-text citations [@C1] / [@C1; @C2]
    if tracker is not None:
        escaped = CITE_GROUP_RE.sub(tracker.cite_match, escaped)

    for raw_tag, (css_cls, label) in TAG_MAP.items():
        escaped = escaped.replace(
            raw_tag,
            f'<span class="ep-tag {css_cls}">[{label}]</span>',
        )

    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = _AUTOLINK_RE.sub(
        lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>' if _is_safe_url(m.group(1)) else m.group(1), escaped
    )
    escaped = _IMAGE_RE.sub(
        lambda m: (
            f'<img src="{m.group(2)}" alt="{m.group(1)}" loading="lazy">' if _is_safe_url(m.group(2)) else m.group(1)
        ),
        escaped,
    )
    escaped = _LINK_RE.sub(
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>' if _is_safe_url(m.group(2)) else m.group(1),
        escaped,
    )

    for idx, code_html in enumerate(code_spans):
        escaped = escaped.replace(f"\x00CODE{idx}\x00", code_html)

    return escaped


def _extract_metadata(report_md: str) -> tuple[str, str, str, str, bool]:
    title = "Heurisma Working Paper"
    meta_line = ""
    abstract_text = ""
    explicit_abstract = False
    change = ""
    for line in report_md.splitlines():
        s = line.strip()
        if s.startswith("# ") and title == "Heurisma Working Paper":
            title = s[2:].strip()
        elif s.startswith("> ") and ("As-Of" in s or "Fecha" in s or "Depth" in s or "Nivel" in s):
            meta_line = s[2:].strip()
        else:
            am = ABSTRACT_QUOTE_RE.match(s)
            if am and not abstract_text:
                abstract_text = am.group(1).strip()
                explicit_abstract = True

    if not abstract_text:
        vm = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:\**\s*(.+)", report_md, re.IGNORECASE)
        if vm:
            abstract_text = vm.group(1).strip()

    cm = re.search(r"(?:What Would Change[^:]*|Qu[eé] cambiar[ií]a[^:]*)\s*:\**\s*(.+)", report_md, re.IGNORECASE)
    if cm:
        change = cm.group(1).strip()

    return title, meta_line, abstract_text, change, explicit_abstract


def _chart_data_table(chart: dict[str, Any], i18n: dict[str, str]) -> str:
    """Compact collapsible data preview for figure accessibility."""
    rows: list[str] = []
    if chart.get("groups") and chart.get("series"):
        headers = [i18n["group"]] + [str(s.get("name", "")) for s in chart["series"]]
        rows.append("<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr>")
        for idx, g in enumerate(chart["groups"]):
            vals = [str((s.get("values") or [""])[idx]) if idx < len(s.get("values") or []) else "" for s in chart["series"]]
            rows.append(
                f"<tr><td>{html.escape(str(g))}</td>"
                + "".join(f'<td class="num">{html.escape(v)}</td>' for v in vals)
                + "</tr>"
            )
    elif chart.get("series") and "value" in (chart["series"][0] if chart["series"] else {}):
        rows.append(f"<tr><th>{i18n['label']}</th><th>{i18n['value']}</th></tr>")
        for s in chart["series"]:
            rows.append(f'<tr><td>{html.escape(str(s.get("label", "")))}</td><td class="num">{html.escape(str(s.get("value", "")))}</td></tr>')
    elif chart.get("series"):
        s0 = chart["series"][0]
        pts = (s0.get("points") or [])[:12]
        rows.append("<tr><th>X</th><th>Y</th></tr>")
        for pt in pts:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                rows.append(f'<tr><td>{html.escape(str(pt[0]))}</td><td class="num">{html.escape(str(pt[1]))}</td></tr>')
    if len(rows) < 2:
        return ""
    return (
        f'<details class="fig-data"><summary>{i18n["fig_data_preview"]}</summary>'
        f'<table class="booktabs compact"><thead>{rows[0]}</thead><tbody>{"".join(rows[1:])}</tbody></table></details>'
    )


def _build_figure_html(
    chart: dict[str, Any],
    fig_num: int,
    *,
    lang: str,
    i18n: dict[str, str],
    tracker: _CitationTracker | None = None,
) -> str:
    title = html.escape(str(chart.get("title", f"{i18n['figure']} {fig_num}")))
    caption = str(chart.get("caption", "")).strip()
    source = str(chart.get("source", "")).strip()
    svg = svg_charts.render_chart_svg(chart, lang=lang)
    parts = [f'<figure class="paper-fig" id="fig-{fig_num}">']
    parts.append(f'<div class="fig-title"><strong>{i18n["figure"]} {fig_num}.</strong> {title}</div>')
    parts.append(svg)
    note_bits: list[str] = []
    if caption:
        note_bits.append(f"<em>{i18n['note']}</em> {_format_inline(caption, tracker)}")
    if source:
        note_bits.append(f"<em>{i18n['source']}</em> {_format_inline(source, tracker)}")
    if note_bits:
        parts.append(f'<figcaption>{" ".join(note_bits)}</figcaption>')
    parts.append(_chart_data_table(chart, i18n))
    parts.append("</figure>")
    return "\n".join(parts)


def _markdown_to_paper_html(
    report_md: str,
    charts_by_id: dict[str, dict[str, Any]],
    *,
    lang: str,
    i18n: dict[str, str],
    tracker: _CitationTracker | None,
    skip_verdict_bullet: bool,
) -> tuple[str, set[str], int]:
    lines = report_md.splitlines()
    out: list[str] = []
    placed_ids: set[str] = set()
    fig_counter = 0

    in_code = False
    code_buf: list[str] = []
    list_stack: list[int] = []
    in_table = False
    table_buf: list[str] = []
    skipped_h1 = False
    verdict_skipped = False

    def flush_list() -> None:
        while list_stack:
            out.append("</li>")
            out.append("</ul>")
            list_stack.pop()

    def flush_table() -> None:
        nonlocal in_table, table_buf
        if not in_table:
            return
        rows = [_split_table_cells(r) for r in table_buf]
        out.append('<div class="table-wrap"><table class="booktabs">')
        if rows:
            out.append("<thead><tr>" + "".join(f"<th>{_format_inline(c, tracker)}</th>" for c in rows[0]) + "</tr></thead>")
            out.append("<tbody>")
            for row in rows[1:]:
                if all(re.fullmatch(r":?-{1,}:?", c.replace(" ", "")) for c in row):
                    continue
                tds = []
                for c in row:
                    clean_c = c.strip("`*")
                    is_num = bool(NUMERIC_CELL_RE.match(clean_c))
                    cls = ' class="num"' if is_num else ""
                    cell = _typographic_minus(c) if is_num else c
                    tds.append(f"<td{cls}>{_format_inline(cell, tracker)}</td>")
                out.append("<tr>" + "".join(tds) + "</tr>")
            out.append("</tbody>")
        out.append("</table></div>")
        in_table = False
        table_buf = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_list()
            flush_table()
            if not in_code:
                in_code = True
                code_buf = []
            else:
                out.append(f'<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>')
                in_code = False
                code_buf = []
            continue

        if in_code:
            code_buf.append(line)
            continue

        fig_m = FIG_MARKER_RE.match(stripped)
        if fig_m:
            flush_list()
            flush_table()
            fid = fig_m.group(1)
            if fid in charts_by_id:
                fig_counter += 1
                placed_ids.add(fid)
                out.append(_build_figure_html(charts_by_id[fid], fig_counter, lang=lang, i18n=i18n, tracker=tracker))
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_list()
            in_table = True
            table_buf.append(stripped)
            continue
        else:
            flush_table()

        if not stripped:
            flush_list()
            continue

        if stripped.startswith("# ") and not skipped_h1:
            skipped_h1 = True
            continue
        if stripped.startswith("> ") and ("As-Of" in stripped or "Fecha" in stripped or "Depth" in stripped or "Nivel" in stripped):
            continue
        if ABSTRACT_QUOTE_RE.match(stripped):
            continue

        if stripped.startswith("## "):
            flush_list()
            out.append(f"<h2>{_format_inline(stripped[3:].strip(), tracker)}</h2>")
        elif stripped.startswith("### "):
            flush_list()
            out.append(f"<h3>{_format_inline(stripped[4:].strip(), tracker)}</h3>")
        elif stripped.startswith("##### "):
            flush_list()
            out.append(f"<h5>{_format_inline(stripped[6:].strip(), tracker)}</h5>")
        elif stripped.startswith("#### "):
            flush_list()
            out.append(f"<h4>{_format_inline(stripped[5:].strip(), tracker)}</h4>")
        elif stripped.startswith("> "):
            flush_list()
            out.append(f"<blockquote>{_format_inline(stripped[2:].strip(), tracker)}</blockquote>")
        elif re.match(r"^\s*[-*]\s+", line):
            if skip_verdict_bullet and not verdict_skipped and VERDICT_LINE_RE.match(line):
                verdict_skipped = True
                continue
            m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
            indent = len(m.group(1).expandtabs(4)) if m else 0
            item_text = m.group(2).strip() if m else stripped[2:].strip()

            if not list_stack:
                out.append("<ul>")
                list_stack.append(indent)
                out.append(f"<li>{_format_inline(item_text, tracker)}")
            elif indent > list_stack[-1]:
                out.append("<ul>")
                list_stack.append(indent)
                out.append(f"<li>{_format_inline(item_text, tracker)}")
            else:
                while len(list_stack) > 1 and indent < list_stack[-1]:
                    out.append("</li>")
                    out.append("</ul>")
                    list_stack.pop()
                out.append("</li>")
                out.append(f"<li>{_format_inline(item_text, tracker)}")
        else:
            flush_list()
            out.append(f"<p>{_format_inline(stripped, tracker)}</p>")

    flush_list()
    flush_table()
    if in_code:
        out.append(f'<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>')

    return "\n".join(out), placed_ids, fig_counter


def _render_references(tracker: _CitationTracker, i18n: dict[str, str]) -> str:
    if not tracker.sources:
        return ""

    ordered_rows: list[tuple[int, dict[str, str]]] = []
    emitted_ids: set[str] = set()
    for cid in tracker.order:
        if cid in tracker.by_id:
            ordered_rows.append((tracker.num_by_id[cid], tracker.by_id[cid]))
            emitted_ids.add(cid)

    next_num = len(ordered_rows) + 1
    for row in tracker.sources:
        cid = (row.get("claim_id") or "").strip()
        if cid and cid in emitted_ids:
            continue
        ordered_rows.append((next_num, row))
        next_num += 1

    items: list[str] = []
    for num, row in ordered_rows:
        raw_title = (row.get("source_title") or i18n["untitled_source"]).strip()
        url = (row.get("url") or "").strip()
        is_local = bool(url) and (url.startswith("file://") or "://" not in url)  # file:// URIs and scheme-less paths
        local_note = ""
        if is_local:
            sha_m = SHA_IN_TEXT_RE.search(raw_title) or SHA_IN_TEXT_RE.search("sha256 " + (row.get("sha256") or ""))
            raw_title = LOCAL_TITLE_SUFFIX_RE.sub("", raw_title).strip() or i18n["untitled_source"]
            local_note = i18n["local_file"] + (f", sha256 {sha_m.group(1)}" if sha_m else "")
        title = html.escape(raw_title)
        tier = html.escape((row.get("tier") or "").strip())
        accessed = html.escape((row.get("accessed_date") or "").strip())
        as_of = html.escape((row.get("data_as_of") or "").strip())
        url_html = (
            f' <a href="{html.escape(url)}">{html.escape(url)}</a>'
            if url.startswith(("http://", "https://"))
            else (
                f" <code>{html.escape(Path(unquote(url[len('file://'):] if url.startswith('file://') else url)).name)}</code> ({html.escape(local_note)})"
                if is_local
                else (f" <code>{html.escape(url)}</code>" if url else "")
            )
        )
        meta = ", ".join(
            x
            for x in (
                tier,
                f"{i18n['data_as_of']} {as_of}" if as_of else "",
                f"{i18n['accessed']} {accessed}" if accessed else "",
            )
            if x
        )
        items.append(f'<li id="ref-{num}"><strong>[{num}]</strong> {title}.{url_html} ({meta})</li>')

    if not items:
        return ""
    return f'<section class="references"><h2>{i18n["references"]}</h2><ol class="ref-list">' + "".join(items) + "</ol></section>"


def _render_appendices(appendix_dir: Path | None, i18n: dict[str, str]) -> str:
    """Embed ONLY small (.py, output.txt, sources.csv, data_attempts.csv, numbers.json <=200KB); link raw data/binaries."""
    if appendix_dir is None or not appendix_dir.is_dir():
        return ""
    embedded: list[str] = []
    linked: list[str] = []

    for path in sorted(appendix_dir.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rel = path.relative_to(appendix_dir)
        rel_str = html.escape(rel.as_posix())
        size = path.stat().st_size

        in_data_dir = "data" in rel.parts
        is_gate_trace = rel.parts[:1] == ("gates",) and path.suffix == ".md"
        is_allowed_text = (not in_data_dir) and (
            path.suffix == ".py" or path.name in ALLOWED_APPENDIX_FILES or is_gate_trace
        )

        if is_allowed_text and size <= MAX_APPENDIX_FILE_BYTES:
            raw_text = path.read_text(encoding="utf-8", errors="replace")
            content = html.escape(_redact_local_paths(raw_text))
            if is_gate_trace:
                content = content.replace("{{", "&#123;&#123;")
            label = (
                f" — {i18n['self_review']}"
                if is_gate_trace and re.search(r"^\s*MODE:\s*self-review\b", raw_text, re.MULTILINE)
                else ""
            )
            embedded.append(
                f'<details class="appendix-item"><summary><code>appendix/{rel_str}</code>{label} ({size:,} bytes)</summary>'
                f"<pre><code>{content}</code></pre></details>"
            )
        else:
            linked.append(
                f'<li><a href="appendix/{rel_str}"><code>appendix/{rel_str}</code></a> '
                f'({size:,} bytes — {i18n["external_artifact"]})</li>'
            )

    if not embedded and not linked:
        return ""
    parts = [f'<section class="appendices"><h2>{i18n["appendices"]}</h2>']
    parts.extend(embedded)
    if linked:
        parts.append(f'<h3>{i18n["external_files"]}</h3><ul>' + "".join(linked) + "</ul>")
    parts.append("</section>")
    return "\n".join(parts)


def compute_source_hash(
    report_md: Path,
    charts: Path | None,
    numbers: Path | None,
    appendix_dir: Path | None,
) -> str:
    """Return a 12-hex fingerprint of every input that shapes the rendered HTML (W3 stale-HTML detection).

    Covers the report Markdown, charts.json, numbers.json (when outside appendix/) and all appendix files,
    ignoring ``__pycache__``/``.pyc``. Content-only: paths never enter the hash, so it is stable across machines.
    """

    def _file_sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    entries: list[tuple[str, str]] = [("renderer-version", __version__), ("report.md", _file_sha(report_md))]
    if charts is not None and charts.is_file():
        entries.append(("charts.json", _file_sha(charts)))
    in_appendix = False
    if numbers is not None and numbers.is_file():
        if appendix_dir is not None:
            try:
                numbers.resolve().relative_to(appendix_dir.resolve())
                in_appendix = True
            except ValueError:
                in_appendix = False
        if not in_appendix:
            entries.append(("numbers.json", _file_sha(numbers)))
    if appendix_dir is not None and appendix_dir.is_dir():
        for fp in sorted(appendix_dir.rglob("*"), key=lambda p: p.relative_to(appendix_dir).parts):
            if not fp.is_file() or "__pycache__" in fp.parts or fp.suffix == ".pyc":
                continue
            entries.append((f"appendix/{fp.relative_to(appendix_dir).as_posix()}", _file_sha(fp)))
    digest = hashlib.sha256("".join(f"{label}\0{sha}\n" for label, sha in entries).encode("utf-8"))
    return digest.hexdigest()[:12]


def render_html(
    report_md: str,
    *,
    charts: list[dict[str, Any]] | None = None,
    appendix_dir: Path | None = None,
    lang: str = "auto",
    no_credit: bool = False,
    numbers: dict[str, Any] | None = None,
    source_hash: str | None = None,
) -> str:
    """Render a Heurisma Markdown report into a print-ready working-paper HTML5 document."""
    resolved_lang = detect_language(report_md, lang)
    i18n = I18N[resolved_lang]
    hash_comment = f"<!-- heurisma-sources: sha256:{source_hash} -->\n  " if source_hash else ""

    # Substitute {{num:key}} placeholders from explicit numbers dict or appendix/numbers.json
    nums: dict[str, Any] = {}
    if appendix_dir is not None and (appendix_dir / "numbers.json").is_file():
        try:
            loaded = json.loads((appendix_dir / "numbers.json").read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                nums.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    if numbers:
        nums.update(numbers)
    if nums:
        report_md = _substitute_markers(report_md, nums)

    title, meta_line, abstract_text, change, explicit_abstract = _extract_metadata(report_md)
    sources = _load_sources(appendix_dir)
    tracker = _CitationTracker(sources)

    charts_list = charts or []
    charts_by_id: dict[str, dict[str, Any]] = {}
    for idx, ch in enumerate(charts_list):
        cid = str(ch.get("id") or f"fig_{idx + 1}")
        charts_by_id[cid] = ch

    # Render Abstract first so any citations in Abstract get numbered first
    abstract_html = ""
    if abstract_text:
        change_p = (
            f'<p class="abstract-change"><strong>{i18n["falsifier"]}</strong> {_format_inline(change, tracker)}</p>'
            if change
            else ""
        )
        abstract_html = (
            '<section class="abstract">'
            f'<div class="abstract-label">{i18n["abstract"]}</div>'
            f"<p>{_format_inline(abstract_text, tracker)}</p>"
            f"{change_p}"
            "</section>"
        )

    body_html, placed_ids, fig_counter = _markdown_to_paper_html(
        report_md,
        charts_by_id,
        lang=resolved_lang,
        i18n=i18n,
        tracker=tracker,
        skip_verdict_bullet=(bool(abstract_text) and not explicit_abstract),
    )

    # Unplaced charts go to Additional Figures appendix (never dumped at the top)
    extra_figs: list[str] = []
    for idx, ch in enumerate(charts_list):
        cid = str(ch.get("id") or f"fig_{idx + 1}")
        if cid not in placed_ids:
            fig_counter += 1
            extra_figs.append(_build_figure_html(ch, fig_counter, lang=resolved_lang, i18n=i18n, tracker=tracker))
    extra_figs_html = (
        f'<section class="extra-figures"><h2>{i18n["additional_figures"]}</h2>' + "\n".join(extra_figs) + "</section>"
        if extra_figs
        else ""
    )

    refs_html = _render_references(tracker, i18n)
    appendices_html = _render_appendices(appendix_dir, i18n)

    meta_html = f'<p class="meta-line">{_format_inline(meta_line, tracker)}</p>' if meta_line else ""
    footer_html = f'<footer class="paper-footer">{i18n["credit"]}</footer>' if not no_credit else ""

    return f"""<!DOCTYPE html>
<html lang="{resolved_lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --text: #111827; --muted: #4b5563; --rule: #cbd5e1; --rule-dark: #1e293b;
      --bg: #ffffff; --tint: #f8fafc; --accent: #0072B2;
    }}
    body {{
      font-family: Charter, 'Bitstream Charter', 'Iowan Old Style', 'Source Serif Pro', Georgia, serif;
      font-size: 17px; line-height: 1.55; color: var(--text); background: var(--bg);
      margin: 0; font-variant-numeric: tabular-nums;
    }}
    .paper {{ max-width: 720px; margin: 0 auto; padding: 3rem 1.5rem 4.5rem; }}
    header.title-block {{ border-bottom: 1.5px solid var(--rule-dark); padding-bottom: 1.25rem; margin-bottom: 1.75rem; }}
    h1 {{ font-size: 1.9rem; line-height: 1.22; margin: 0 0 0.6rem; font-weight: 700; letter-spacing: -0.01em; }}
    .meta-line {{ font-size: 0.88rem; color: var(--muted); margin: 0; font-family: system-ui, -apple-system, sans-serif; }}
    .abstract {{
      background: var(--tint); border-left: 3px solid var(--accent);
      padding: 1rem 1.25rem; margin: 1.5rem 0 2rem; font-size: 0.96rem;
    }}
    .abstract-label {{
      font-family: system-ui, -apple-system, sans-serif; font-size: 0.75rem;
      font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); margin-bottom: 0.35rem;
    }}
    .abstract p {{ margin: 0.25rem 0; }}
    .abstract-change {{ font-size: 0.88rem; color: var(--muted); margin-top: 0.5rem; }}
    h2 {{
      font-size: 1.28rem; margin-top: 2.25rem; margin-bottom: 0.75rem;
      border-bottom: 1px solid var(--rule); padding-bottom: 0.25rem; page-break-after: avoid;
    }}
    h3 {{ font-size: 1.05rem; margin-top: 1.5rem; margin-bottom: 0.5rem; page-break-after: avoid; }}
    h4 {{ font-size: 0.98rem; margin-top: 1.2rem; margin-bottom: 0.4rem; font-style: italic; page-break-after: avoid; }}
    h5 {{ font-size: 0.9rem; margin-top: 1rem; margin-bottom: 0.3rem; font-variant: small-caps; page-break-after: avoid; }}
    p, li {{ margin: 0.45rem 0; }}
    ul ul {{ margin-top: 0.25rem; margin-bottom: 0.25rem; padding-left: 1.35rem; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .ep-tag {{
      font-variant: small-caps; font-family: system-ui, -apple-system, sans-serif;
      font-size: 0.82em; font-weight: 600; letter-spacing: 0.02em; padding-left: 0.25rem;
    }}
    .tag-strong {{ color: #166534; border-left: 2px solid #166534; }}
    .tag-moderate {{ color: #075985; border-left: 2px solid #075985; }}
    .tag-preliminary {{ color: #92400e; border-left: 2px solid #92400e; }}
    .tag-speculative {{ color: #991b1b; border-left: 2px solid #991b1b; }}
    .table-wrap {{ overflow-x: auto; margin: 1.25rem 0; }}
    table.booktabs {{
      width: 100%; border-collapse: collapse; font-size: 0.88rem; line-height: 1.4;
      border-top: 1.5px solid var(--rule-dark); border-bottom: 1.5px solid var(--rule-dark);
      page-break-inside: avoid;
    }}
    table.booktabs th, table.booktabs td {{ padding: 0.45rem 0.55rem; text-align: left; border: none; vertical-align: top; }}
    table.booktabs thead th {{ border-bottom: 1px solid var(--rule-dark); font-weight: 700; }}
    table.booktabs td.num {{ text-align: right; white-space: nowrap; }}
    table.booktabs.compact {{ font-size: 0.8rem; margin-top: 0.5rem; }}
    figure.paper-fig {{ margin: 1.5rem 0; page-break-inside: avoid; }}
    .fig-title {{ font-size: 0.95rem; margin-bottom: 0.35rem; color: var(--text); }}
    figcaption {{ font-size: 0.84rem; color: var(--muted); margin-top: 0.35rem; line-height: 1.4; }}
    details.fig-data, details.appendix-item {{
      margin-top: 0.5rem; font-size: 0.85rem; border-top: 1px solid var(--rule); padding-top: 0.35rem;
    }}
    details summary {{ cursor: pointer; color: var(--muted); font-family: system-ui, -apple-system, sans-serif; }}
    pre {{ background: var(--tint); padding: 0.75rem; overflow-x: auto; font-size: 0.8rem; border: 1px solid var(--rule); }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.86em; }}
    ol.ref-list {{ list-style: none; padding-left: 0; font-size: 0.86rem; line-height: 1.45; }}
    ol.ref-list li {{ margin: 0.4rem 0; }}
    blockquote {{ border-left: 2.5px solid var(--rule); margin: 1rem 0; padding-left: 1rem; color: var(--muted); }}
    footer.paper-footer {{
      margin-top: 3rem; padding-top: 0.75rem; border-top: 1px solid var(--rule);
      font-size: 0.8rem; color: var(--muted); font-family: system-ui, -apple-system, sans-serif;
    }}
    @page {{ size: A4; margin: 2.2cm; }}
    @media print {{
      body {{ font-size: 11pt; }}
      .paper {{ max-width: none; padding: 0; }}
      details.fig-data, details.appendix-item {{ display: none; }}
      a[href^="http"]::after {{ content: " (" attr(href) ")"; font-size: 0.8em; color: #4b5563; }}
      figure.paper-fig, table.booktabs {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  {hash_comment}<article class="paper">
    <header class="title-block">
      <h1>{_format_inline(title, tracker)}</h1>
      {meta_html}
    </header>
    {abstract_html}
    <main>{body_html}</main>
    {extra_figs_html}
    {refs_html}
    {appendices_html}
    {footer_html}
  </article>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Render a Heurisma Markdown report into a working-paper HTML + SVG document.")
    parser.add_argument("--version", action="version", version=f"render_report.py {__version__}")
    parser.add_argument("report_path", type=Path, help="Input Markdown report path.")
    parser.add_argument("--out", type=Path, required=True, help="Output HTML file path.")
    parser.add_argument("--charts", type=Path, default=None, help="Optional JSON file defining charts (v2 or v1 schema).")
    parser.add_argument("--appendix", type=Path, default=None, help="Optional appendix/ directory for References & small code/output appendices.")
    parser.add_argument("--lang", choices=("auto", "en", "es"), default="auto", help="Output chrome language (default: auto-detected from headings).")
    parser.add_argument("--no-credit", action="store_true", help="Omit the Heurisma footer credit.")
    parser.add_argument("--numbers", type=Path, default=None, help="Optional JSON file mapping {{num:key}} placeholders to values.")
    args = parser.parse_args(argv)

    if not args.report_path.is_file():
        print(f"Error: Report not found: {args.report_path}", file=sys.stderr)
        return 1

    charts_data = None
    if args.charts is not None:
        if not args.charts.is_file():
            print(f"Error: Charts JSON not found: {args.charts}", file=sys.stderr)
            return 1
        charts_data = json.loads(args.charts.read_text(encoding="utf-8"))

    numbers_data = None
    if args.numbers is not None:
        if not args.numbers.is_file():
            print(f"Error: Numbers JSON not found: {args.numbers}", file=sys.stderr)
            return 1
        numbers_data = json.loads(args.numbers.read_text(encoding="utf-8"))

    report_md = args.report_path.read_text(encoding="utf-8")
    rendered = render_html(
        report_md,
        charts=charts_data,
        appendix_dir=args.appendix,
        lang=args.lang,
        no_credit=args.no_credit,
        numbers=numbers_data,
        source_hash=compute_source_hash(args.report_path, args.charts, args.numbers, args.appendix),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    body_only = re.sub(  # quoted appendix files and code blocks are text, not markers
        r'<section class="appendices">.*?</section>|<(?:pre|code)\b[^>]*>.*?</(?:pre|code)>', "", rendered, flags=re.DOTALL
    )
    for key in sorted(set(NUM_MARKER_RE.findall(body_only))):
        print(
            f"Warning: unresolved marker '{{{{num:{key}}}}}' left literal in the HTML (no such key in numbers.json); "
            f"validate_report.py will fail on it.",
            file=sys.stderr,
        )
    print(f"Rendered Heurisma working-paper HTML: {args.out} ({len(rendered.encode('utf-8')):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
