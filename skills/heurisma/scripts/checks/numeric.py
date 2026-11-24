"""Numeric closure (Section 4 tables, chart text) and the calibrated-verdict size check."""

from __future__ import annotations

import functools
import re
from typing import Any

from checks.common import (
    NUM_MARKER_RE,
    _VERDICT_NUMBER_RE,
    _VERDICT_SENTENCE_RE,
    _extract_section_slice,
)
from checks.prereg import _canon_number, _plain_readings

_HAY_NUMBER_RE = re.compile(r"[+\-\u2212]?\d+(?:[.,]\d+)*")


def _signed_values(token: str) -> set[str]:
    """Every value a number may mean, canonical (``1,024`` -> {1.024, 1024}; ``2.00`` -> 2; ``−0.50`` -> -0.5; ``−0.00`` -> 0)."""
    token = token.replace("\u2212", "-").rstrip("%")
    sign = "-" if token.startswith("-") else ""
    digits = token.lstrip("+-")
    return {("0" if c == "0" else sign + c) for r in _plain_readings(digits) for c in (_canon_number(r),)} if digits else set()


@functools.lru_cache(maxsize=8)
def _hay_values(hay_raw: str) -> frozenset[str]:
    return frozenset(v for m in _HAY_NUMBER_RE.finditer(hay_raw) for v in _signed_values(m.group(0)))


_TABLE_SKIP_RE = re.compile(
    r"\{\{[^}]+\}\}|\[@[^\]]+\]|(?:Section|Secci[oó]n|§)\s*\d+(?:\.\d+)*"
    r"|\bTier\s*[123]\b|\bN-[12]\b|\b\d+(?:/\d+)?\s*(?:kV|MW|GW|MWh|GWh|Hz)\b"
    r"|\b\d{4}-\d{2}(?:-\d{2})?\b",
    re.IGNORECASE,
)
_TABLE_STAT_RE = re.compile(r"(?<![\w.])(?:[+\-\u2212]\d+(?:[.,]\d+)?%?|\d+[.,]\d+%?|\d+%)")


def _closure_haystack(output_text: str, numbers_data: dict[str, Any] | None) -> tuple[str, str]:
    """(raw, normalised) text of output.txt plus the numbers.json values, the only places a figure may come from."""
    hay_parts = [output_text]
    if numbers_data:
        hay_parts.extend(str(v) for v in numbers_data.values())
    hay_raw = "\n".join(hay_parts)
    return hay_raw, hay_raw.replace("\u2212", "-").replace(",", ".")


def _untraced_in(text: str, hay_raw: str, hay_norm: str, seen: set[str]) -> list[str]:
    """Statistical-looking figures of ``text`` found in neither haystack (years, dates, tiers, section refs and
    engineering constants are skipped; a bare ``1,00×`` is the trivial baseline of a ratio and needs no source)."""
    found: list[str] = []
    cleaned = _TABLE_SKIP_RE.sub(" ", text)
    for m in _TABLE_STAT_RE.finditer(cleaned):
        tok = m.group(0)
        norm = tok.replace("\u2212", "-").replace(",", ".")
        bare = norm.lstrip("+-").rstrip("%")
        if re.fullmatch(r"(?:19|20)\d\d", bare):
            continue
        if cleaned[m.end():m.end() + 1] in ("\u00d7", "x", "X") and re.fullmatch(r"\+?1(?:\.0+)?", norm):
            continue
        if norm in seen:
            continue
        candidates = {tok, norm, bare, bare.replace(".", ",")}
        if _signed_values(tok) & _hay_values(hay_raw):  # the same value, formatted differently (1,024 = 1024; 2.00 = 2.0000)
            continue
        if any(
            re.search(rf"(?<![\d.,]){re.escape(c)}(?!\d)", hay_raw) or re.search(rf"(?<![\d.,]){re.escape(c)}(?!\d)", hay_norm)
            for c in candidates
            if c
        ):
            continue
        seen.add(norm)
        found.append(tok)
    return found


def check_caption_closure(
    charts: Any,
    output_text: str,
    numbers_data: dict[str, Any] | None,
    level: int,
) -> tuple[list[str], list[str]]:
    """Flag figures in the title/caption/source of a chart that appear in neither output.txt nor numbers.json."""
    if not isinstance(charts, list):
        return [], []
    hay_raw, hay_norm = _closure_haystack(output_text, numbers_data)
    msgs: list[str] = []
    for i, ch in enumerate(charts):
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or f"fig_{i + 1}")
        for field in ("title", "caption", "source"):
            value = ch.get(field)
            if not isinstance(value, str):
                continue
            untraced = _untraced_in(value, hay_raw, hay_norm, set())
            if untraced:
                msgs.append(
                    f"Chart '{cid}' {field} contains untraced numeric figure(s) not found in appendix/output.txt or "
                    f"appendix/numbers.json: {', '.join(untraced[:5])}; build the {field} from the analysis output instead "
                    f"of typing the figure."
                )
    return (msgs, []) if level == 3 else ([], msgs)


def check_numeric_closure(
    clean_text: str,
    section_positions: dict[str, int],
    output_text: str,
    numbers_data: dict[str, Any] | None,
    level: int,
) -> tuple[list[str], list[str]]:
    """Flag statistical numbers hand-typed in Section 4 tables that appear in neither output.txt nor numbers.json."""
    findings = _extract_section_slice(clean_text, section_positions, "Findings")
    if not findings:
        return [], []
    hay_raw, hay_norm = _closure_haystack(output_text, numbers_data)

    untraced: list[str] = []
    seen: set[str] = set()
    lines = findings.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        # Skip header and separator rows
        if re.fullmatch(r"\|[\s:\-|]+\|", stripped):
            continue
        if idx + 1 < len(lines) and re.fullmatch(r"\|[\s:\-|]+\|", lines[idx + 1].strip()):
            continue
        untraced.extend(_untraced_in(stripped, hay_raw, hay_norm, seen))
    if not untraced:
        return [], []
    msg = (
        f"Section 4 table contains untraced numeric figure(s) not found in appendix/output.txt or "
        f"appendix/numbers.json: {', '.join(untraced[:5])}; compute them in appendix/analysis.py and reference via "
        f"{{{{num:key}}}}."
    )
    return ([msg], []) if level == 3 else ([], [msg])


def _verdict_stats(verdict: str) -> tuple[int, int]:
    """(sentences, numbers) of a calibrated verdict, ignoring citations, tags, years and digits inside words."""
    body = re.sub(r"\[@[^\]]+\]", "", verdict)
    body = re.sub(r"`?\[(?:Strong|Moderate|Preliminary|Speculative|Fuerte|Moderada|Preliminar|Especulativa)\]`?", "", body)
    markers = len(NUM_MARKER_RE.findall(body))
    plain = NUM_MARKER_RE.sub(" ", body)
    numbers = [n for n in _VERDICT_NUMBER_RE.findall(plain) if not re.fullmatch(r"(?:19|20)\d\d", n)]
    sentences = [x for x in _VERDICT_SENTENCE_RE.split(plain.strip()) if x.strip()]
    return len(sentences), len(numbers) + markers
