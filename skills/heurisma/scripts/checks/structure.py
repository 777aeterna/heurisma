"""Calibration-tag spelling diagnostics."""

from __future__ import annotations

import re

from contracts import (
    ALL_TAGS,
)


_TAG_WORD_RE = re.compile(r"\[[A-Za-z\u00c1\u00c9\u00cd\u00d3\u00da\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00d1]+\]")


def _noncanonical_tags(text: str) -> list[str]:
    """Bracketed words that are a calibration tag in another capitalisation (``[fuerte]``, ``[STRONG]``), in order."""
    canonical = {tag.lower(): tag for tag in ALL_TAGS}
    out: list[str] = []
    for m in _TAG_WORD_RE.finditer(text):
        word = m.group(0)
        if word.lower() in canonical and word not in ALL_TAGS and word not in out:
            out.append(word)
    return out


def _canonical_spelling(word: str) -> str:
    return next((tag for tag in ALL_TAGS if tag.lower() == word.lower()), word)
