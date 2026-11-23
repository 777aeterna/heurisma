"""Checks on the rendered report.html: sections, language, markers, privacy and freshness."""

from __future__ import annotations

import re
from pathlib import Path

from contracts import (
    HTML_SECTION_PATTERNS,
)
from checks.common import (
    HOME_PATH_RE,
    LEFTOVER_BRACES_RE,
    SPANISH_LEAKED_CHROME,
    UNCONVERTED_LATEX_RE,
    _find_charts_json,
)


def validate_html_full(html_path: Path) -> tuple[list[str], list[str]]:
    """Verify rendered HTML sections, Spanish language purity (V3), and unconverted LaTeX (V4)."""
    if not html_path.is_file():
        return [f"Rendered HTML file not found: {html_path}"], []

    html_text = html_path.read_text(encoding="utf-8")
    if not html_text.strip():
        return [f"Rendered HTML file is empty: {html_path}"], []

    errors: list[str] = []
    if HOME_PATH_RE.search(html_text):
        errors.append("report.html contains a home-directory path (e.g. /home/<user>/…); it leaks the author's machine.")
    warnings: list[str] = []

    for label, pattern in HTML_SECTION_PATTERNS:
        if not re.search(pattern, html_text, flags=re.IGNORECASE):
            errors.append(f"HTML deliverable missing required section heading: '{label}'")

    # V3: Spanish HTML language purity check
    is_spanish_html = bool(
        re.search(r"<h2[^>]*>\s*(?:1\.\s*Resumen\s+ejecutivo|4\.\s*Hallazgos|6\.\s*Matriz\s+de\s+afirmaciones)", html_text, re.IGNORECASE)
    )
    if is_spanish_html:
        if re.search(r'<html\b[^>]*\blang="en"', html_text, re.IGNORECASE):
            errors.append("Spanish HTML report has wrong language attribute: expected <html lang=\"es\">, found lang=\"en\".")
        leaked = [label for label, pat in SPANISH_LEAKED_CHROME if re.search(pat, html_text)]
        if leaked:
            errors.append(
                f"Spanish HTML report leaks untranslated English chrome: {', '.join(leaked)}."
            )

    # W2: unresolved {{...}} markers left in visible HTML (strip <style>, <script>, <pre>, <code> first)
    visible_for_braces = re.sub(
        r"<(?:style|script|pre|code)\b[^>]*>.*?</(?:style|script|pre|code)>", " ", html_text, flags=re.DOTALL | re.IGNORECASE
    )
    leftovers = LEFTOVER_BRACES_RE.findall(visible_for_braces)
    if leftovers:
        errors.append(
            f"Rendered HTML contains unresolved marker(s) {', '.join(sorted(set(leftovers))[:4])}; "
            f"fix the key or figure id and re-render."
        )

    # V4: Unconverted LaTeX warning (strip <style>, <script>, <pre>, <code> before scanning)
    visible = re.sub(r"<(?:style|script|pre|code)\b[^>]*>.*?</(?:style|script|pre|code)>", " ", html_text, flags=re.DOTALL | re.IGNORECASE)
    latex_hits = UNCONVERTED_LATEX_RE.findall(visible)
    if latex_hits:
        sample = ", ".join(f"${h}$" for h in latex_hits[:4])
        warnings.append(f"Unconverted LaTeX expression(s) detected in HTML: {sample}.")

    return errors, warnings


def validate_html(html_path: Path) -> list[str]:
    """Verify that a rendered HTML deliverable exists, preserves all 7 sections, and respects language purity."""
    errors, _ = validate_html_full(html_path)
    return errors


SOURCE_HASH_RE = re.compile(r"<!--\s*heurisma-sources:\s*sha256:([0-9a-f]{12})\s*-->")


def _load_render_module():
    """Import render_report.py by explicit path so it also works under ``python3 -I`` (no script dir on sys.path)."""
    import importlib.util

    path = Path(__file__).resolve().parent.parent / "render_report.py"  # checks/ lives inside scripts/
    spec = importlib.util.spec_from_file_location("_heurisma_render_report", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_html_freshness(html_path: Path, report_path: Path, charts_path: Path | None = None) -> list[str]:
    """Warn when the rendered HTML predates a change to the report, charts.json, numbers.json or appendix/ (W3)."""
    if not html_path.is_file():
        return []
    try:
        compute_source_hash = _load_render_module().compute_source_hash
    except Exception as exc:  # never skip the freshness check silently
        return [f"freshness check skipped: could not load render_report.py ({exc})."]
    html_text = html_path.read_text(encoding="utf-8", errors="replace")
    m = SOURCE_HASH_RE.search(html_text)
    if not m:
        return [
            f"HTML '{html_path.name}' has no source hash (rendered before v0.5.0); "
            f"re-render with render_report.py so staleness can be detected."
        ]
    report_dir = report_path.parent
    appendix_dir = report_dir / "appendix"
    charts = _find_charts_json(report_dir, appendix_dir, charts_path)
    current = compute_source_hash(report_path, charts, None, appendix_dir if appendix_dir.is_dir() else None)
    if current != m.group(1):
        return [
            f"HTML '{html_path.name}' is stale (out of date): sources hash {current} != embedded {m.group(1)}; "
            f"re-run render_report.py."
        ]
    return []
