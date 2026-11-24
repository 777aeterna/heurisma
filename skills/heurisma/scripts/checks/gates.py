"""Gate files: the hash a gate is bound to, its header and quotes, and the reviewer's analysis anchor."""

from __future__ import annotations

import re
from pathlib import Path

from checks.common import (
    _extract_section_slice,
    _file_sha256,
)
from contracts import WITHHELD_MANIFEST, read_withheld


# P0-2: a gate is bound to the files it reviewed (hash), quotes them verbatim, and says who wrote it (MODE)
GATE_HASH_FILES: dict[str, tuple[str, ...]] = {
    "source_verifier": ("appendix/sources.csv", "appendix/data_attempts.csv"),
    "reviewer": ("appendix/output.txt", "charts.json", "appendix/sources.csv", "appendix/data_attempts.csv"),
}
GATE_HEADER_FIELDS: tuple[tuple[str, str], ...] = (
    ("MODE:", r"^\s*MODE:\s*(?:subagent|self-review)\b"),
    ("REVIEWED-SHA256:", r"^\s*REVIEWED-SHA256:\s*[0-9a-fA-F]{12,64}\b"),
    ("REVIEWED-UTC:", r"^\s*REVIEWED-UTC:\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z"),
)
GATE_MIN_QUOTES = 2
_QUOTE_RE = re.compile(r'^\s*QUOTE:\s*(\S+?):(\d+):\s*"(.+)"\s*$', re.MULTILINE)
_SELF_REVIEW_DECLARED_RE = re.compile(r"self-review|auto-?revisi[oó]n|autorrevisi[oó]n", re.IGNORECASE)


def _gate_files(report_dir: Path, gate: str) -> list[tuple[str, Path]]:
    """(path relative to the report folder, file) pairs a gate reviews; relative paths keep the hash location-free."""
    if gate in GATE_HASH_FILES:
        return [(rel, report_dir / rel) for rel in GATE_HASH_FILES[gate]]
    files = [("report.md", report_dir / "report.md"), ("charts.json", report_dir / "charts.json")]
    appendix = report_dir / "appendix"
    if appendix.is_dir():
        for fp in sorted(appendix.rglob("*"), key=lambda p: p.relative_to(appendix).parts):
            rel = fp.relative_to(appendix)
            if fp.is_file() and rel.parts[0] != "gates" and "__pycache__" not in fp.parts and fp.suffix != ".pyc":
                if rel.as_posix() != WITHHELD_MANIFEST:  # a distribution artifact, not something the gate reviewed
                    files.append(("appendix/" + rel.as_posix(), fp))
    return files


def gate_hash(report_dir: str | Path, gate: str) -> str:
    """SHA-256 over the files a gate reviews (content + relative path; missing files count as absent).

    source_verifier: sources.csv + data_attempts.csv · reviewer: output.txt + charts.json + sources.csv +
    data_attempts.csv · qa: report.md + charts.json + every appendix file except appendix/gates/.
    """
    import hashlib

    report_dir = Path(report_dir)
    entries = [(rel, _file_sha256(fp) if fp.is_file() else "-") for rel, fp in _gate_files(report_dir, gate)]
    if gate not in GATE_HASH_FILES and (report_dir / "appendix" / "papers.csv").is_file():  # qa covers the whole appendix: a withheld full text counts with its recorded hash
        withheld = read_withheld(report_dir / "appendix")
        present = {rel for rel, _ in entries}
        entries += [("appendix/" + rel, sha) for rel, sha in withheld.items() if "appendix/" + rel not in present]
        head, tail = entries[:2], entries[2:]
        entries = head + sorted(tail, key=lambda e: Path(e[0][len("appendix/"):]).parts)
    h = hashlib.sha256()
    for rel, digest in entries:
        h.update(f"{rel}\t{digest}\n".encode("utf-8"))
    return h.hexdigest()


_POST_REVIEW_RE = re.compile(r"post-review\s+changes|cambios\s+posteriores\s+a\s+la\s+revisi[oó]n", re.IGNORECASE)


def _analysis_anchor(report_dir: Path) -> str:
    """12-hex SHA-256 prefix of appendix/analysis.py ('' when absent): what the reviewer's code reading is bound to."""
    fp = report_dir / "appendix" / "analysis.py"
    return _file_sha256(fp)[:12] if fp.is_file() else ""


def _check_analysis_anchor(
    gtext: str,
    report_dir: Path,
    clean_text: str,
    section_positions: dict[str, int],
    sink: list[str],
) -> None:
    """reviewer.md may record ANALYSIS-SHA256; analysis.py edited after that needs a 'Post-review changes' subsection."""
    declared = re.search(r"^\s*ANALYSIS-SHA256:\s*([0-9a-fA-F]{12,64})\b", gtext, re.MULTILINE)
    current = _analysis_anchor(report_dir)
    if not declared or not current or current.startswith(declared.group(1).lower()[:12]):
        return
    sec5 = _extract_section_slice(clean_text, section_positions, "Counter-Evidence & Alternative Explanations")
    if _POST_REVIEW_RE.search(sec5):
        return
    sink.append(
        f"appendix/gates/reviewer.md records ANALYSIS-SHA256 {declared.group(1)[:12]} but appendix/analysis.py is now "
        f"{current}: analysis.py changed after the reviewer saw it; list what changed in a 'Post-review changes' "
        f"subsection of Section 5, or run Reviewer #2 again."
    )


def _closed_disposition(clean_text: str, section_positions: dict[str, int]) -> bool:
    """Section 5 holds a Reviewer #2 Disposition Table with at least one action (the review loop was closed)."""
    sec5 = _extract_section_slice(clean_text, section_positions, "Counter-Evidence & Alternative Explanations")
    return bool(
        re.search(r"(?:Reviewer\s*#?2|Revisor\s*#?2|Disposition|Disposici[oó]n)", sec5, re.IGNORECASE)
        and re.search(r"\|\s*[`*]{0,2}(?:Fixed|Refuted|Deferred|Corregida|Refutada|Diferida)[`*]{0,2}\b", sec5, re.IGNORECASE)
    )


def _check_gate_binding(
    gate: str,
    gtext: str,
    report_dir: Path,
    clean_text: str,
    section_positions: dict[str, int],
    gate_sink: list[str],
    warnings: list[str],
    errors: list[str] | None = None,
) -> None:
    headers = len(re.findall(r"^\s*REVIEWED-SHA256:", gtext, re.MULTILINE))
    if headers >= 2:  # the validator reads the first header, so an appended pass would be judged by the stale one
        (gate_sink if errors is None else errors).append(
            f"appendix/gates/{gate}.md has {headers} REVIEWED-SHA256 lines; a later pass must replace the file, not append."
        )
    missing = [label for label, pattern in GATE_HEADER_FIELDS if not re.search(pattern, gtext, re.MULTILINE)]
    quotes = _QUOTE_RE.findall(gtext)
    if len(quotes) < GATE_MIN_QUOTES:
        missing.append(f"QUOTE: <file>:<line>: \"…\" (at least {GATE_MIN_QUOTES})")
    if missing:
        gate_sink.append(
            f"appendix/gates/{gate}.md is missing header field(s): {', '.join(missing)}; the gate must say who wrote it, "
            f"which version it reviewed (validate_report.py --gate-hash {gate}) and quote what it read."
        )
    declared = re.search(r"^\s*REVIEWED-SHA256:\s*([0-9a-fA-F]{12,64})", gtext, re.MULTILINE)
    if declared:
        current = gate_hash(report_dir, gate)
        if not current.startswith(declared.group(1).lower()):
            msg = (
                f"appendix/gates/{gate}.md reviewed an earlier version: REVIEWED-SHA256 {declared.group(1)[:16]} != current "
                f"{current[:16]}; re-run the gate on the current files."
            )
            if gate == "reviewer":  # fixes made after Reviewer #2 legitimately change what it read
                if not _closed_disposition(clean_text, section_positions):
                    warnings.append(
                        msg + " (Expected after Reviewer #2 fixes: every critique must be closed in the Disposition Table.)"
                    )
            else:
                gate_sink.append(msg)
    root = report_dir.resolve()
    # Reviewer #2 quotes the draft; once its critiques are closed, the author has corrected those very lines (same reason the
    # pre-fix hash is accepted). Quotes of the appendix still have to match.
    reviewed_draft_fixed = gate == "reviewer" and _closed_disposition(clean_text, section_positions)
    for rel, line_no, quoted in quotes:
        rel_posix = rel.replace("\\", "/")
        target = (report_dir / rel_posix).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            gate_sink.append(f"appendix/gates/{gate}.md quotes '{rel}', which is outside the report folder.")
            continue
        if reviewed_draft_fixed and target == root / "report.md":
            continue
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines() if target.is_file() else []
        idx = int(line_no) - 1
        norm = lambda t: re.sub(r"\s+", " ", t).strip()  # noqa: E731
        if not (0 <= idx < len(lines)) or norm(quoted) not in norm(lines[idx]):
            gate_sink.append(
                f"appendix/gates/{gate}.md quotes {rel}:{line_no} but that line does not contain \"{quoted[:60]}\"."
            )
    if re.search(r"^\s*MODE:\s*self-review\b", gtext, re.MULTILINE):
        method = _extract_section_slice(clean_text, section_positions, "Methodology & Evidence Standards")
        if not _SELF_REVIEW_DECLARED_RE.search(method):
            warnings.append(
                f"appendix/gates/{gate}.md is a self-review (MODE: self-review), not an independent subagent; say so in "
                f"Section 3 (e.g. 'gates run as self-review: no subagent tool available')."
            )


_REVIEWER_ITEM = re.compile(r"^\s*(?:UNVERIFIED:\s*)?\d+\.\s+\[", re.MULTILINE)
_DISPOSITION_ACTIONS = {"fixed", "refuted", "deferred", "corregida", "refutada", "diferida"}


def reviewer_items(text: str) -> int:
    """Critiques in a Reviewer #2 answer: numbered lines that open with a ``[category]`` (the coverage block does not)."""
    return len(_REVIEWER_ITEM.findall(text))


def disposition_rows(section5: str) -> int:
    """Table rows in Section 5 with a cell that is exactly one of the six actions (backticks and asterisks ignored)."""
    count = 0
    for line in section5.splitlines():
        line = line.strip()
        if not line.startswith("|") or re.fullmatch(r"[|:\-\s]+", line):
            continue
        cells = {c.strip().strip("`*").strip().lower() for c in line.strip("|").split("|")}
        if cells & _DISPOSITION_ACTIONS:
            count += 1
    return count
