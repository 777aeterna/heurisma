#!/usr/bin/env python3
"""Zero-dependency working-paper HTML + inline SVG renderer for Heurisma reports.

Produces a lightweight, print-ready academic working-paper HTML5 document
(serif typography, 700px single column, booktabs tables, sober small-caps
epistemic tags, inline numbered {{fig:id}} SVG figures, auto-generated
References from sources.csv, @media print A4 CSS, and strict appendix filtering
excluding raw data/binaries and >200 KB files).
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

# Ensure sibling svg_charts.py can be imported when invoked as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))
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

MAX_APPENDIX_FILE_BYTES = 200 * 1024
ALLOWED_APPENDIX_FILES = {"output.txt", "sources.csv", "data_attempts.csv", "README.md"}
FIG_MARKER_RE = re.compile(r"^\{\{fig:([A-Za-z0-9_-]+)\}\}$")
NUMERIC_CELL_RE = re.compile(r"^[+\-−]?\s*[$€%]?\s*[\d.,]+(?:\s*[%x×])?$")


def _format_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(
        r"`(\[(?:Strong|Moderate|Preliminary|Speculative|Fuerte|Moderada|Moderado|Preliminar|Especulativa|Especulativo)\])`",
        r"\1",
        escaped,
    )
    for raw_tag, (css_cls, label) in TAG_MAP.items():
        escaped = escaped.replace(
            raw_tag,
            f'<span class="ep-tag {css_cls}">[{label}]</span>',
        )
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def _extract_metadata(report_md: str) -> tuple[str, str, str, str]:
    title = "Heurisma Working Paper"
    meta_line = ""
    verdict = ""
    change = ""
    for line in report_md.splitlines():
        s = line.strip()
        if s.startswith("# ") and title == "Heurisma Working Paper":
            title = s[2:].strip()
        elif s.startswith("> ") and ("As-Of" in s or "Fecha" in s or "Depth" in s or "Nivel" in s):
            meta_line = s[2:].strip()
    vm = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:\**\s*(.+)", report_md, re.IGNORECASE)
    if vm:
        verdict = vm.group(1).strip()
    cm = re.search(r"(?:What Would Change[^:]*|Qu[eé] cambiar[ií]a[^:]*)\s*:\**\s*(.+)", report_md, re.IGNORECASE)
    if cm:
        change = cm.group(1).strip()
    return title, meta_line, verdict, change


def _chart_data_table(chart: dict[str, Any]) -> str:
    """Compact collapsible data preview for figure accessibility."""
    rows: list[str] = []
    if chart.get("groups") and chart.get("series"):
        headers = ["Group"] + [str(s.get("name", "")) for s in chart["series"]]
        rows.append("<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr>")
        for idx, g in enumerate(chart["groups"]):
            vals = [str((s.get("values") or [""])[idx]) if idx < len(s.get("values") or []) else "" for s in chart["series"]]
            rows.append(
                f"<tr><td>{html.escape(str(g))}</td>"
                + "".join(f'<td class="num">{html.escape(v)}</td>' for v in vals)
                + "</tr>"
            )
    elif chart.get("series") and "value" in (chart["series"][0] if chart["series"] else {}):
        rows.append("<tr><th>Label</th><th>Value</th></tr>")
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
        '<details class="fig-data"><summary>Figure data preview</summary>'
        f'<table class="booktabs compact"><thead>{rows[0]}</thead><tbody>{"".join(rows[1:])}</tbody></table></details>'
    )


def _build_figure_html(chart: dict[str, Any], fig_num: int) -> str:
    title = html.escape(str(chart.get("title", f"Figure {fig_num}")))
    caption = str(chart.get("caption", "")).strip()
    source = str(chart.get("source", "")).strip()
    svg = svg_charts.render_chart_svg(chart)
    parts = [f'<figure class="paper-fig" id="fig-{fig_num}">']
    parts.append(f'<div class="fig-title"><strong>Figure {fig_num}.</strong> {title}</div>')
    parts.append(svg)
    note_bits: list[str] = []
    if caption:
        note_bits.append(f"<em>Note:</em> {_format_inline(caption)}")
    if source:
        note_bits.append(f"<em>Source:</em> {_format_inline(source)}")
    if note_bits:
        parts.append(f'<figcaption>{" ".join(note_bits)}</figcaption>')
    parts.append(_chart_data_table(chart))
    parts.append("</figure>")
    return "\n".join(parts)


def _markdown_to_paper_html(
    report_md: str,
    charts_by_id: dict[str, dict[str, Any]],
) -> tuple[str, set[str], int]:
    lines = report_md.splitlines()
    out: list[str] = []
    placed_ids: set[str] = set()
    fig_counter = 0

    in_code = False
    code_buf: list[str] = []
    in_list = False
    in_table = False
    table_buf: list[str] = []
    skipped_h1 = False

    def flush_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def flush_table() -> None:
        nonlocal in_table, table_buf
        if not in_table:
            return
        rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table_buf]
        out.append('<div class="table-wrap"><table class="booktabs">')
        if rows:
            out.append("<thead><tr>" + "".join(f"<th>{_format_inline(c)}</th>" for c in rows[0]) + "</tr></thead>")
            out.append("<tbody>")
            for row in rows[1:]:
                if all(re.fullmatch(r":?-{1,}:?", c.replace(" ", "")) for c in row):
                    continue
                tds = []
                for c in row:
                    clean_c = c.strip("`*")
                    cls = ' class="num"' if NUMERIC_CELL_RE.match(clean_c) else ""
                    tds.append(f"<td{cls}>{_format_inline(c)}</td>")
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
                out.append(_build_figure_html(charts_by_id[fid], fig_counter))
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
        if stripped.startswith("> ") and ("As-Of" in stripped or "Fecha" in stripped or "Depth" in stripped):
            continue
        if stripped.startswith("## "):
            flush_list()
            out.append(f"<h2>{_format_inline(stripped[3:].strip())}</h2>")
        elif stripped.startswith("### "):
            flush_list()
            out.append(f"<h3>{_format_inline(stripped[4:].strip())}</h3>")
        elif stripped.startswith("> "):
            flush_list()
            out.append(f"<blockquote>{_format_inline(stripped[2:].strip())}</blockquote>")
        elif re.match(r"^[-*]\s+", stripped):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_format_inline(re.sub(r'^[-*]\s+', '', stripped))}</li>")
        else:
            flush_list()
            out.append(f"<p>{_format_inline(stripped)}</p>")

    flush_list()
    flush_table()
    if in_code:
        out.append(f'<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>')

    return "\n".join(out), placed_ids, fig_counter


def _render_references(appendix_dir: Path | None) -> str:
    if appendix_dir is None:
        return ""
    src_csv = appendix_dir / "sources.csv"
    if not src_csv.is_file():
        return ""
    items: list[str] = []
    try:
        with src_csv.open(encoding="utf-8", newline="") as fh:
            for idx, row in enumerate(csv.DictReader(fh), start=1):
                title = html.escape((row.get("source_title") or "Untitled source").strip())
                url = (row.get("url") or "").strip()
                tier = html.escape((row.get("tier") or "").strip())
                accessed = html.escape((row.get("accessed_date") or "").strip())
                as_of = html.escape((row.get("data_as_of") or "").strip())
                url_html = (
                    f' <a href="{html.escape(url)}">{html.escape(url)}</a>'
                    if url.startswith(("http://", "https://"))
                    else (f" <code>{html.escape(url)}</code>" if url else "")
                )
                meta = ", ".join(x for x in (tier, f"data as of {as_of}" if as_of else "", f"accessed {accessed}" if accessed else "") if x)
                items.append(f"<li><strong>[{idx}]</strong> {title}.{url_html} ({meta})</li>")
    except OSError:
        return ""
    if not items:
        return ""
    return '<section class="references"><h2>References</h2><ol class="ref-list">' + "".join(items) + "</ol></section>"


def _render_appendices(appendix_dir: Path | None) -> str:
    """Embed ONLY small (.py, output.txt, sources.csv, data_attempts.csv <=200KB); link raw data/binaries."""
    if appendix_dir is None or not appendix_dir.is_dir():
        return ""
    embedded: list[str] = []
    linked: list[str] = []

    for path in sorted(appendix_dir.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rel = path.relative_to(appendix_dir)
        rel_str = html.escape(str(rel))
        size = path.stat().st_size

        in_data_dir = "data" in rel.parts
        is_allowed_text = (not in_data_dir) and (path.suffix == ".py" or path.name in ALLOWED_APPENDIX_FILES)

        if is_allowed_text and size <= MAX_APPENDIX_FILE_BYTES:
            content = html.escape(path.read_text(encoding="utf-8", errors="replace"))
            embedded.append(
                f'<details class="appendix-item"><summary><code>appendix/{rel_str}</code> ({size:,} bytes)</summary>'
                f"<pre><code>{content}</code></pre></details>"
            )
        else:
            linked.append(f'<li><a href="appendix/{rel_str}"><code>appendix/{rel_str}</code></a> ({size:,} bytes — external artifact)</li>')

    if not embedded and not linked:
        return ""
    parts = ['<section class="appendices"><h2>Appendices &amp; Reproducible Artifacts</h2>']
    parts.extend(embedded)
    if linked:
        parts.append('<h3>External Data &amp; Large Files (Linked, Not Embedded)</h3><ul>' + "".join(linked) + "</ul>")
    parts.append("</section>")
    return "\n".join(parts)


def render_html(
    report_md: str,
    *,
    charts: list[dict[str, Any]] | None = None,
    appendix_dir: Path | None = None,
) -> str:
    """Render a Heurisma Markdown report into a print-ready working-paper HTML5 document."""
    title, meta_line, verdict, change = _extract_metadata(report_md)

    charts_list = charts or []
    charts_by_id: dict[str, dict[str, Any]] = {}
    for idx, ch in enumerate(charts_list):
        cid = str(ch.get("id") or f"fig_{idx + 1}")
        charts_by_id[cid] = ch

    body_html, placed_ids, fig_counter = _markdown_to_paper_html(report_md, charts_by_id)

    # Unplaced charts go to Additional Figures appendix (never dumped at the top)
    extra_figs: list[str] = []
    for idx, ch in enumerate(charts_list):
        cid = str(ch.get("id") or f"fig_{idx + 1}")
        if cid not in placed_ids:
            fig_counter += 1
            extra_figs.append(_build_figure_html(ch, fig_counter))
    extra_figs_html = (
        '<section class="extra-figures"><h2>Additional Figures</h2>' + "\n".join(extra_figs) + "</section>"
        if extra_figs
        else ""
    )

    refs_html = _render_references(appendix_dir)
    appendices_html = _render_appendices(appendix_dir)

    abstract_html = ""
    if verdict:
        change_p = f'<p class="abstract-change"><strong>Falsifier:</strong> {_format_inline(change)}</p>' if change else ""
        abstract_html = (
            '<section class="abstract">'
            '<div class="abstract-label">Abstract</div>'
            f"<p>{_format_inline(verdict)}</p>"
            f"{change_p}"
            "</section>"
        )

    meta_html = f'<p class="meta-line">{_format_inline(meta_line)} &middot; Prepared with Heurisma</p>' if meta_line else '<p class="meta-line">Prepared with Heurisma</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
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
    p, li {{ margin: 0.45rem 0; }}
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
    figure.paper-fig {{ margin: 1.75rem 0; page-break-inside: avoid; }}
    .fig-title {{ font-size: 0.95rem; margin-bottom: 0.4rem; color: var(--text); }}
    figcaption {{ font-size: 0.84rem; color: var(--muted); margin-top: 0.45rem; line-height: 1.4; }}
    details.fig-data, details.appendix-item {{
      margin-top: 0.5rem; font-size: 0.85rem; border-top: 1px solid var(--rule); padding-top: 0.35rem;
    }}
    details summary {{ cursor: pointer; color: var(--muted); font-family: system-ui, -apple-system, sans-serif; }}
    pre {{ background: var(--tint); padding: 0.75rem; overflow-x: auto; font-size: 0.8rem; border: 1px solid var(--rule); }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.86em; }}
    ol.ref-list {{ list-style: none; padding-left: 0; font-size: 0.86rem; line-height: 1.45; }}
    ol.ref-list li {{ margin: 0.4rem 0; }}
    blockquote {{ border-left: 2.5px solid var(--rule); margin: 1rem 0; padding-left: 1rem; color: var(--muted); }}
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
  <article class="paper">
    <header class="title-block">
      <h1>{_format_inline(title)}</h1>
      {meta_html}
    </header>
    {abstract_html}
    <main>{body_html}</main>
    {extra_figs_html}
    {refs_html}
    {appendices_html}
  </article>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a Heurisma Markdown report into a working-paper HTML + SVG document.")
    parser.add_argument("report_path", type=Path, help="Input Markdown report path.")
    parser.add_argument("--out", type=Path, required=True, help="Output HTML file path.")
    parser.add_argument("--charts", type=Path, default=None, help="Optional JSON file defining charts (v2 or v1 schema).")
    parser.add_argument("--appendix", type=Path, default=None, help="Optional appendix/ directory for References & small code/output appendices.")
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

    report_md = args.report_path.read_text(encoding="utf-8")
    rendered = render_html(report_md, charts=charts_data, appendix_dir=args.appendix)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    print(f"Rendered Heurisma working-paper HTML: {args.out} ({len(rendered.encode('utf-8')):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
