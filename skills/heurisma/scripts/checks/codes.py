"""Stable machine-readable codes for --json (documented in references/validator-codes.md)."""

from __future__ import annotations

import re



# Stable machine-readable codes for --json (documented in references/validator-codes.md; keep the two in sync).
# (message regex, code, file template: \1 = first group of the regex). The first matching rule wins.
CODE_RULES: list[tuple[str, str, str]] = [
    (r"^Report is empty", "STRUCT-EMPTY", "report.md"),
    (r"^Missing required section", "STRUCT-SECTION", "report.md"),
    (r"^Section out of order", "STRUCT-ORDER", "report.md"),
    (r"lacks substantive content", "STRUCT-THIN", "report.md"),
    (r"^Missing epistemic calibration tags", "STRUCT-TAGS", "report.md"),
    (r"^Missing explicit null and alternative", "STRUCT-HYPOTHESES", "report.md"),
    (r"^report\.md contains a home-directory path", "PRIV-HOME", "report.md"),
    (r"^report\.html contains a home-directory path", "PRIV-HOME", "report.html"),
    (r"^As-Of Date", "P1-ASOF", "report.md"),
    (r"^Calibrated Verdict has \d+ (?:sentences|numbers)", "P1-VERDICT", "report.md"),
    (r"^Calibrated Verdict number\(s\) not found|^Calibrated Verdict / Section 1 retypes", "P1-VERDICT-NUM", "report.md"),
    (r"^Section 4 table contains untraced numeric", "P1-UNTRACED-NUM", "report.md"),
    (r"^Chart '[^']+' (?:title|caption|source) contains untraced numeric", "P1-UNTRACED-NUM", "charts.json"),
    (r"^numbers\.json coverage", "P1-NUM-COVERAGE", "report.md"),
    (r"^Claim-Evidence Matrix row \d+ is \[Strong\] but has no", "P0-STRONG-CITE", "report.md"),
    (r"^Claim-Evidence Matrix row \d+ (?:is \[Strong\] resting only|pairs \[Strong\])", "P0-STRONG", "report.md"),
    (r"^Claim-Evidence Matrix row \d+ rests only on user-curated", "P2-SELECTION", "report.md"),
    (r"^Claim-Evidence Matrix", "MATRIX", "report.md"),
    (r"appendix/gates/([a-z_]+)\.md quotes a home-directory path|appendix/gates/([a-z_]+)\.md contains a literal", "GATE-PRIVACY", "appendix/gates/"),
    (r"appendix/gates/([a-z_]+)\.md (?:is missing or empty|is under)", "GATE-MISSING", "appendix/gates/\\1.md"),
    (r"appendix/gates/([a-z_]+)\.md is missing marker", "GATE-MARKERS", "appendix/gates/\\1.md"),
    (r"appendix/gates/qa\.md has no 'QA: PASS'", "GATE-QA", "appendix/gates/qa.md"),
    (r"appendix/gates/([a-z_]+)\.md (?:is missing header|reviewed an earlier version|quotes |is a self-review|records ANALYSIS-SHA256)", "GATE-BINDING", "appendix/gates/\\1.md"),
    (r"^Level \d report requires charts\.json|^Invalid JSON in .*charts|is not strict JSON", "FIG-JSON", "charts.json"),
    (r"^Chart '[^']*': (?:near-identical|fan chart)", "FIG-DESIGN", "charts.json"),
    (r"^Chart '[^']*': ", "FIG-SCHEMA", "charts.json"),
    (r"must place figures inline|^Unknown figure marker", "FIG-MARKER", "report.md"),
    (r"is not placed inline via", "FIG-UNPLACED", "report.md"),
    (r"^Unresolved marker '\{\{num:|^Invalid JSON in appendix/numbers\.json", "W2-NUM", "report.md"),
    (r"^Level \d report requires (?:an 'appendix/'|at least one reproducible|'appendix/output|'appendix/sources)", "L2-APPENDIX", "appendix/"),
    (r"must include in-text citations", "CITE-NONE", "report.md"),
    (r"does not match any claim_id", "CITE-UNKNOWN", "report.md"),
    (r"is never cited in the report text", "CITE-UNCITED", "appendix/sources.csv"),
    (r"has no kind column|has no kind\.$|has kind '", "P1-KIND", "appendix/sources.csv"),
    (r"in appendix/sources\.csv has tier '", "SRC-TIER", "appendix/sources.csv"),
    (r"^appendix/data/sources_metadata\.csv |^Table appendix/data/\S+ cites primary_source_id", "SRC-META", "appendix/data/sources_metadata.csv"),
    (r"^Source '[^']*' has data_as_of .* later than the As-Of", "P1-ASOF", "appendix/sources.csv"),
    (r"has kind=own-computation but tier", "SRC-OWN-TIER", "appendix/sources.csv"),
    (r"is described as full text", "SRC-FULLTEXT", "appendix/sources.csv"),
    (r"changed since it was registered|must include a SHA-256|registered in appendix/sources\.csv with sha256", "P0-SHA", "appendix/sources.csv"),
    (r"download_log\.csv: .* changed since it was logged", "P0-SHA", "appendix/download_log.csv"),
    (r"^Orphan data file", "P1-ORPHAN", "appendix/data/"),
    (r"is declared Tier|has kind=press but", "P2-DOMAIN", "appendix/sources.csv"),
    (r"data_attempts\.csv is missing canonical|^Unable to read appendix/data_attempts", "ATT-COLUMNS", "appendix/data_attempts.csv"),
    (r"inherited|no attempted_utc column|cannot determine run start|no appendix/run\.json", "P1-RUN", "appendix/data_attempts.csv"),
    (r"^0-byte file|^Python bytecode", "HYG-FILES", "appendix/"),
    (r"^Level 3 report requires a Reviewer", "R2-TABLE", "report.md"),
    (r"^Level 3 report marks Reviewer", "R2-DEFERRED", "report.md"),
    (r"is stale|has no source hash|freshness check skipped", "HTML-STALE", "report.html"),
    (r"^Rendered HTML file", "HTML-MISSING", "report.html"),
    (r"^HTML deliverable missing", "HTML-SECTION", "report.html"),
    (r"^Spanish HTML report", "HTML-LANG", "report.html"),
    (r"^Rendered HTML contains unresolved", "HTML-MARKER", "report.html"),
    (r"^Unconverted LaTeX", "HTML-LATEX", "report.html"),
    (r"^reproduce:", "REPRO", "appendix/analysis.py"),
    (r"user-curated|selection '|retrieved_utc|days before the As-Of|agent-fetched|^inbox/", "P2-SELECTION", "appendix/sources.csv"),
    (r"preregistration\.json", "P2-PREREG", "appendix/preregistration.json"),
]


def classify_message(message: str) -> tuple[str, str]:
    """(stable code, file) of a validator message; ``("GEN", "")`` when no rule matches."""
    for pattern, code, file_tpl in CODE_RULES:
        m = re.search(pattern, message)
        if m:
            groups = [g for g in m.groups() if g]
            return code, (m.expand(file_tpl) if "\\1" in file_tpl and groups else file_tpl.replace("\\1", groups[0] if groups else ""))
    return "GEN", ""
