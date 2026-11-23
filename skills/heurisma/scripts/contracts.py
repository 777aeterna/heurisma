#!/usr/bin/env python3
"""Single source of truth for shared Heurisma protocol constants (Python >= 3.9, stdlib only)."""

from __future__ import annotations

__version__ = "0.9.0"

# Epistemic confidence tags (canonical English + localized Spanish)
TAG_TO_CANONICAL: dict[str, str] = {
    "[Strong]": "Strong",
    "[Moderate]": "Moderate",
    "[Preliminary]": "Preliminary",
    "[Speculative]": "Speculative",
    "[Fuerte]": "Strong",
    "[Moderada]": "Moderate",
    "[Moderado]": "Moderate",
    "[Preliminar]": "Preliminary",
    "[Especulativa]": "Speculative",
    "[Especulativo]": "Speculative",
}

ALL_TAGS: tuple[str, ...] = tuple(TAG_TO_CANONICAL.keys())
STRONG_TAGS: tuple[str, ...] = ("[Strong]", "[Fuerte]")

# Provenance schemas
VALID_KINDS: tuple[str, ...] = ("data", "literature", "press", "own-computation")
WEAK_KINDS: tuple[str, ...] = ("press", "blog", "own-computation")
DOCUMENT_KINDS: tuple[str, ...] = ("literature", "press")
VALID_SELECTIONS: tuple[str, ...] = ("user-curated", "agent-fetched", "third-party")
# The tier column is canonical: every tier rule matches "Tier N", so "3" or "T3" would bypass them.
VALID_TIERS: tuple[str, ...] = ("Tier 1", "Tier 2", "Tier 3")
# A title carrying one of these says the document itself was not read (only a web search summary): no Tier 1 on it.
WEB_SUMMARY_LABELS: tuple[str, ...] = ("web summary", "resumen web")

SOURCE_COLS: tuple[str, ...] = (
    "claim_id",
    "source_title",
    "url",
    "tier",
    "accessed_date",
    "data_as_of",
    "kind",
    "sha256",
    "selection",
    "retrieved_utc",
)

CANONICAL_DATA_ATTEMPTS_COLS: tuple[str, ...] = (
    "target_series",
    "source_tried",
    "query_or_endpoint",
    "outcome",
    "failure_reason",
    "fallback_used",
)

ATTEMPT_COLS: tuple[str, ...] = CANONICAL_DATA_ATTEMPTS_COLS + ("attempted_utc",)

# Verification gates
GATE_FILES: tuple[str, ...] = ("source_verifier", "reviewer", "qa")
GATES_BY_LEVEL: dict[int, tuple[str, ...]] = {
    2: ("source_verifier", "qa"),
    3: ("source_verifier", "reviewer", "qa"),
}

# Report sections (Markdown + HTML patterns, EN/ES)
REQUIRED_SECTIONS: list[tuple[str, str]] = [
    (
        "Executive Summary",
        r"^##\s+1\.\s+(?:Executive Summary|Resumen\s+ejecutivo)\b",
    ),
    (
        "Framing & Hypotheses",
        r"^##\s+2\.\s+(?:Framing\s+&\s+Hypotheses|Encuadre\s+e\s+hip[oó]tesis)\b",
    ),
    (
        "Methodology & Evidence Standards",
        r"^##\s+3\.\s+(?:Methodology\s+&\s+Evidence Standards|Metodolog[ií]a\s+y\s+est[aá]ndares\s+de\s+evidencia)\b",
    ),
    (
        "Findings",
        r"^##\s+4\.\s+(?:Findings|Hallazgos)\b",
    ),
    (
        "Counter-Evidence & Alternative Explanations",
        r"^##\s+5\.\s+(?:Counter-Evidence\s+&\s+Alternative Explanations|Contraevidencia\s+y\s+explicaciones\s+alternativas)\b",
    ),
    (
        "Claim-Evidence Matrix",
        r"^##\s+6\.\s+(?:Claim-Evidence Matrix|Matriz\s+de\s+afirmaciones\s+y\s+evidencia)\b",
    ),
    (
        "Limitations & Open Questions",
        r"^##\s+7\.\s+(?:Limitations\s+&\s+Open Questions|Limitaciones\s+y\s+preguntas\s+abiertas)\b",
    ),
]

HTML_SECTION_PATTERNS: list[tuple[str, str]] = [
    (
        "Executive Summary",
        r"<h2[^>]*>\s*1\.\s*(?:Executive Summary|Resumen\s+ejecutivo)\b",
    ),
    (
        "Framing & Hypotheses",
        r"<h2[^>]*>\s*2\.\s*(?:Framing\s*(?:&amp;|&)\s*Hypotheses|Encuadre\s+e\s+hip[oó]tesis)\b",
    ),
    (
        "Methodology & Evidence Standards",
        r"<h2[^>]*>\s*3\.\s*(?:Methodology\s*(?:&amp;|&)\s*Evidence Standards|Metodolog[ií]a\s+y\s+est[aá]ndares\s+de\s+evidencia)\b",
    ),
    (
        "Findings",
        r"<h2[^>]*>\s*4\.\s*(?:Findings|Hallazgos)\b",
    ),
    (
        "Counter-Evidence & Alternative Explanations",
        r"<h2[^>]*>\s*5\.\s*(?:Counter-Evidence\s*(?:&amp;|&)\s*Alternative Explanations|Contraevidencia\s+y\s+explicaciones\s+alternativas)\b",
    ),
    (
        "Claim-Evidence Matrix",
        r"<h2[^>]*>\s*6\.\s*(?:Claim-Evidence Matrix|Matriz\s+de\s+afirmaciones\s+y\s+evidencia)\b",
    ),
    (
        "Limitations & Open Questions",
        r"<h2[^>]*>\s*7\.\s*(?:Limitations\s*(?:&amp;|&)\s*Open Questions|Limitaciones\s+y\s+preguntas\s+abiertas)\b",
    ),
]
