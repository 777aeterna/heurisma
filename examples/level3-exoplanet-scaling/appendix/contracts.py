#!/usr/bin/env python3
"""Single source of truth for shared Heurisma protocol constants (Python >= 3.9, stdlib only)."""

from __future__ import annotations

__version__ = "0.11.1"

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
VALID_KINDS: tuple[str, ...] = ("data", "literature", "press", "own-computation", "formal-proof")
WEAK_KINDS: tuple[str, ...] = ("press", "blog", "own-computation")

# Formal verification & symbolic conjecture schemas (scripts/formal_math.py, scripts/conjecture.py)
FORMAL_PROOFS_CSV = "formal_proofs.csv"  # relative to appendix/
FORMAL_PROOF_COLS: tuple[str, ...] = (
    "proof_id",
    "slug",
    "theorem_name",
    "challenge_file",
    "challenge_sha256",
    "solution_file",
    "solution_sha256",
    "toolchain",
    "lean_version",
    "verification_mode",
    "status",
    "sorries",
    "axioms",
    "verified_utc",
)
STANDARD_LEAN_AXIOMS: frozenset[str] = frozenset({"propext", "Classical.choice", "Quot.sound"})
CONJECTURES_JSON = "conjectures.json"  # relative to appendix/
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

# Paper connector (scripts/papers.py): the registry columns and the work types it can tell apart
PAPER_COLS: tuple[str, ...] = (
    "doi",
    "title",
    "first_author",
    "n_authors",
    "year",
    "venue",
    "work_type",
    "is_retracted",
    "is_oa",
    "oa_url",
    "pmcid",
    "abstract_sha256",
    "fulltext_file",
    "fulltext_sha256",
    "providers",
    "via",
    "retrieved_utc",
    "query_id",
)
SEARCH_LOG_COLS: tuple[str, ...] = ("query_id", "provider", "query", "filters", "n_hits", "retrieved_utc", "raw_file")
WORK_TYPES: tuple[str, ...] = ("article", "preprint", "report", "conference", "book", "dataset", "other")
# Not peer reviewed as published: capped at Tier 2 (a working paper is not a journal article, whoever hosts it)
NON_PEER_REVIEWED: tuple[str, ...] = ("preprint", "report")

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


# Full texts withheld from a redistributed copy (publisher licensing): one row per file left out, with the SHA-256 it had.
# A listed file counts as present with that hash in every fingerprint, so gates reviewed on the full copy stay valid.
WITHHELD_MANIFEST = "data/papers/EXCLUDED.csv"  # relative to appendix/
WITHHELD_COLS: tuple[str, ...] = ("file", "sha256", "reason")


def read_withheld(appendix_dir: object) -> dict[str, str]:
    """``{appendix-relative path: sha256}`` of the withheld full texts declared in ``appendix/data/papers/EXCLUDED.csv``."""
    import csv
    import re
    from pathlib import Path

    if appendix_dir is None or not str(appendix_dir).strip():
        return {}
    manifest = Path(str(appendix_dir)) / WITHHELD_MANIFEST
    if not manifest.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        with manifest.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            reader.fieldnames = [c.strip() if c is not None else "" for c in (reader.fieldnames or [])]
            for row in reader:
                name, sha = (row.get("file") or "").strip(), (row.get("sha256") or "").strip().lower()
                if (
                    name
                    and re.fullmatch(r"[0-9a-f]{64}", sha)
                    and "/" not in name
                    and "\\" not in name
                    and name not in (".", "..")
                ):
                    out[f"data/papers/{name}"] = sha
    except (OSError, csv.Error, UnicodeDecodeError):
        return {}
    return out
