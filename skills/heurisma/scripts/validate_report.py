#!/usr/bin/env python3
"""Zero-dependency structural, content, provenance, localization, and epistemic validator for Heurisma reports."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from contracts import (  # noqa: E402
    ALL_TAGS,
    CANONICAL_DATA_ATTEMPTS_COLS,
    DOCUMENT_KINDS,
    GATE_FILES,
    HTML_SECTION_PATTERNS,
    REQUIRED_SECTIONS,
    STRONG_TAGS,
    TAG_TO_CANONICAL as TAG_TO_CANONICAL,
    VALID_KINDS,
    VALID_SELECTIONS,
    WEAK_KINDS,
    __version__,
)

LOW_TIER_SOURCE_RE = re.compile(
    r"\b(?:Tier\s*3|press\s+release|press\s+article|nota\s+de\s+prensa|prensa|news\s+article|blog\s+post|unverified|roadmap)\b",
    re.IGNORECASE,
)

FENCED_CODE_RE = re.compile(r"^```.*?^```[ \t]*$", flags=re.MULTILINE | re.DOTALL)
FIG_MARKER_RE = re.compile(r"\{\{fig:([A-Za-z0-9_-]+)\}\}")
NUM_MARKER_RE = re.compile(r"\{\{num:([A-Za-z0-9_.-]+)\}\}")
LEFTOVER_BRACES_RE = re.compile(r"\{\{[^{}\n]{1,80}\}\}")
CITE_GROUP_RE = re.compile(r"\[(@[A-Za-z0-9_.-]+(?:\s*[;,]\s*@[A-Za-z0-9_.-]+)*)\]")
NUMERIC_CITE_RE = re.compile(r"\[[0-9]+\]")
UNCONVERTED_LATEX_RE = re.compile(r"(?<!\\)\$(?!\s)(?!\d[\d.,]*(?:\s|$|[^\\_^=a-zA-Z]))([^$\n]+?)(?<!\s)\$")
SHA_HEX_RE = re.compile(r"\b[0-9a-fA-F]{12,64}\b")

SPANISH_LEAKED_CHROME: tuple[tuple[str, str], ...] = (
    ("Figure N.", r"<strong>Figure\s+\d+\.</strong>"),
    ("Note:", r"<em>Note:</em>"),
    ("Source:", r"<em>Source:</em>"),
    ("Abstract", r'<div class="abstract-label">\s*Abstract\s*</div>'),
    ("References", r"<h2>\s*References\s*</h2>"),
    ("Median (P50)", r">Median\s*\(P50\)<"),
)


def _strip_fenced_code_blocks(text: str) -> str:
    return FENCED_CODE_RE.sub("", text)


def _split_md_table_row(row: str) -> list[str]:
    stripped = row.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", stripped)]


def _is_separator_row(cells: list[str]) -> bool:
    """Accept valid Markdown table separators including single-dash ':-', '-:', ':-:', '-'."""
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c.replace(" ", "")) for c in cells)


def _extract_section_slice(clean_text: str, section_positions: dict[str, int], target_label: str) -> str:
    if target_label not in section_positions:
        return ""
    start = section_positions[target_label]
    later_positions = [pos for pos in section_positions.values() if pos > start]
    end = min(later_positions) if later_positions else len(clean_text)
    return clean_text[start:end]


def _load_sources_rows(report_dir: Path | None) -> tuple[list[dict[str, str]], list[str]]:
    if report_dir is None:
        return [], []
    sources_csv = report_dir / "appendix" / "sources.csv"
    if not sources_csv.is_file():
        return [], []
    try:
        with sources_csv.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            return list(reader), fieldnames
    except OSError:
        return [], []


def _is_weak_source(row: dict[str, str] | None) -> bool:
    """A source that cannot carry a [Strong] claim on its own, decided from sources.csv (never from prose)."""
    if not row:
        return False
    if re.search(r"\bTier\s*3\b", row.get("tier") or "", re.IGNORECASE):
        return True
    if (row.get("kind") or "").strip().lower() in WEAK_KINDS:
        return True
    return bool(_WEAK_TITLE_RE.search(row.get("source_title") or ""))


def _declared_sha(row: dict[str, str]) -> str:
    """The SHA-256 prefix a source row declares (sha256 column, else 'sha256 <hex>' in the title)."""
    col = SHA_HEX_RE.search((row.get("sha256") or "").strip())
    if col:
        return col.group(0).lower()
    m = re.search(r"sha256\s*[:=]?\s*([0-9a-fA-F]{12,64})\b", row.get("source_title") or "", re.IGNORECASE)
    return m.group(1).lower() if m else ""


def _local_source_path(url: str, report_dir: Path) -> Path:
    raw = url[len("file://"):] if url.startswith("file://") else url
    path = Path(unquote(raw))
    return path if path.is_absolute() else report_dir / path


def _file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registered_data_files(
    report_dir: Path, appendix_dir: Path, sources_rows: list[dict[str, str]]
) -> tuple[set[str], list[str]]:
    """Files of appendix/data/ that sources.csv / download_log.csv register: (relative paths, declared hash prefixes)."""
    paths: set[str] = set()
    hashes: list[str] = []
    data_dir = (appendix_dir / "data").resolve()
    for row in sources_rows:
        url = (row.get("url") or "").strip()
        sha = _declared_sha(row)
        if sha:
            hashes.append(sha)
        if url and (url.startswith("file://") or "://" not in url):
            try:
                paths.add(_local_source_path(url, report_dir).resolve().relative_to(data_dir).as_posix())
            except ValueError:
                pass
    log = appendix_dir / "download_log.csv"
    if log.is_file():
        try:
            with log.open(encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    name = (r.get("file") or "").strip()
                    if name:
                        paths.add(Path(unquote(name)).as_posix())
                    h = SHA_HEX_RE.search((r.get("sha256") or "").strip())
                    if h:
                        hashes.append(h.group(0).lower())
        except OSError:
            pass
    return paths, hashes


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
                files.append(("appendix/" + rel.as_posix(), fp))
    return files


def gate_hash(report_dir: str | Path, gate: str) -> str:
    """SHA-256 over the files a gate reviews (content + relative path; missing files count as absent).

    source_verifier: sources.csv + data_attempts.csv · reviewer: output.txt + charts.json + sources.csv +
    data_attempts.csv · qa: report.md + charts.json + every appendix file except appendix/gates/.
    """
    import hashlib

    h = hashlib.sha256()
    for rel, fp in _gate_files(Path(report_dir), gate):
        digest = _file_sha256(fp) if fp.is_file() else "-"
        h.update(f"{rel}\t{digest}\n".encode("utf-8"))
    return h.hexdigest()


def _check_gate_binding(
    gate: str,
    gtext: str,
    report_dir: Path,
    clean_text: str,
    section_positions: dict[str, int],
    gate_sink: list[str],
    warnings: list[str],
) -> None:
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
                sec5 = _extract_section_slice(clean_text, section_positions, "Counter-Evidence & Alternative Explanations")
                has_closed_disp = bool(
                    re.search(r"(?:Reviewer\s*#?2|Revisor\s*#?2|Disposition|Disposici[oó]n)", sec5, re.IGNORECASE)
                    and re.search(
                        r"\|\s*[`*]{0,2}(?:Fixed|Refuted|Deferred|Corregida|Refutada|Diferida)[`*]{0,2}\b",
                        sec5,
                        re.IGNORECASE,
                    )
                )
                if not has_closed_disp:
                    warnings.append(
                        msg + " (Expected after Reviewer #2 fixes: every critique must be closed in the Disposition Table.)"
                    )
            else:
                gate_sink.append(msg)
    root = report_dir.resolve()
    for rel, line_no, quoted in quotes:
        target = (report_dir / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            gate_sink.append(f"appendix/gates/{gate}.md quotes '{rel}', which is outside the report folder.")
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


PRESS_DOMAINS = (
    "nytimes.com", "washingtonpost.com", "bbc.com", "bbc.co.uk", "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "theguardian.com", "economist.com", "forbes.com", "businessinsider.com", "cnn.com", "techcrunch.com", "elpais.com",
    "lanacion.com.ar", "clarin.com", "infobae.com", "ambito.com", "cronista.com", "pagina12.com.ar", "medium.com",
    "substack.com", "blogspot.com", "wordpress.com", "tumblr.com", "twitter.com", "x.com", "facebook.com",
    "linkedin.com", "reddit.com", "youtube.com",
)


def check_source_domains(sources_rows: list[dict[str, str]]) -> list[str]:
    """P2 heuristic: warn when a declared tier or kind contradicts the source's domain (never raises a tier)."""
    warnings: list[str] = []
    for row in sources_rows:
        cid = (row.get("claim_id") or "?").strip()
        tier = (row.get("tier") or "").strip()
        kind = (row.get("kind") or "").strip().lower()
        url = (row.get("url") or "").strip()
        host = (urlparse(url).hostname or "").lower() if url.startswith(("http://", "https://")) else ""
        press_host = next((d for d in PRESS_DOMAINS if host == d or host.endswith("." + d)), "")
        if kind == "press" and re.search(r"\bTier\s*[12]\b", tier, re.IGNORECASE):
            warnings.append(
                f"Source '{cid}' has kind=press but is declared {tier}; press belongs in Tier 3 (kind and tier contradict "
                f"each other; if it only reproduces a primary source, cite that source instead)."
            )
        elif press_host and re.search(r"\bTier\s*[12]\b", tier, re.IGNORECASE):
            warnings.append(
                f"Source '{cid}' is declared {tier} but its domain ({press_host}) is a press/blog/social site; press belongs "
                f"in Tier 3 unless it is a primary document hosted there (then say so in the title)."
            )
    return warnings


def _curated_only_ids(row: str, source_by_id: dict[str, dict[str, str]]) -> list[str]:
    """Ids of a matrix row when every non-own-computation source it cites is a user-curated document, else []."""
    ids = [c for c in _extract_citation_ids(row) if c in source_by_id]
    evidence = [c for c in ids if (source_by_id[c].get("kind") or "").strip().lower() != "own-computation"]
    if not evidence:
        return []
    if all(
        (source_by_id[c].get("selection") or "").strip().lower() == "user-curated"
        and (source_by_id[c].get("kind") or "").strip().lower() in DOCUMENT_KINDS
        for c in evidence
    ):
        return evidence
    return []


def _intake_user_curated_hashes(report_dir: Path | None) -> set[str]:
    """Return 12-hex SHA-256 prefixes ingested with selection=user-curated in appendix/intake.md."""
    if report_dir is None:
        return set()
    intake_md = report_dir / "appendix" / "intake.md"
    if not intake_md.is_file():
        return set()
    text = intake_md.read_text(encoding="utf-8", errors="replace")
    hashes: set[str] = set()
    in_user_curated = False
    for line in text.splitlines():
        if line.startswith("## Channel:") or line.startswith("- folder:"):
            if "selection:" in line:
                in_user_curated = "selection: user-curated" in line
        if in_user_curated and "accepted:" in line:
            m = re.search(r"sha256\s+([0-9a-f]{12,64})", line, re.IGNORECASE)
            if m:
                hashes.add(m.group(1).lower()[:12])
    return hashes


def _download_proof(report_dir: Path | None) -> tuple[set[str], set[str], set[str]]:
    """Return (urls, filenames, sha12s) with logged acquisition proof in download_log.csv or successful data_attempts.csv."""
    urls: set[str] = set()
    names: set[str] = set()
    shas: set[str] = set()
    if report_dir is None:
        return urls, names, shas
    app = report_dir / "appendix"
    dl_csv = app / "download_log.csv"
    if dl_csv.is_file():
        try:
            with dl_csv.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    if (row.get("url") or "").strip():
                        urls.add(row["url"].strip())
                    if (row.get("file") or "").strip():
                        names.add(Path(row["file"].strip()).name)
                    m = SHA_HEX_RE.search((row.get("sha256") or "").strip())
                    if m:
                        shas.add(m.group(0).lower()[:12])
        except OSError:
            pass
    att_csv = app / "data_attempts.csv"
    if att_csv.is_file():
        ok_out = {"used", "ok", "success", "succeeded", "retrieved", "http 200"}
        try:
            with att_csv.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    out = (row.get("outcome") or "").strip().lower()
                    if out in ok_out or out.startswith("http 2"):
                        q = (row.get("query_or_endpoint") or "").strip()
                        if q:
                            urls.add(q)
                            for tok in q.split():
                                if tok.startswith(("http://", "https://")):
                                    urls.add(tok)
        except OSError:
            pass
    return urls, names, shas


def check_selection(
    sources_rows: list[dict[str, str]],
    sources_cols: list[str],
    as_of: str,
    level: int,
    report_dir: Path | None = None,
    run_start: Any = None,
) -> tuple[list[str], list[str]]:
    """Pre-intake provenance rules (only when sources.csv has a ``selection`` column)."""
    errors: list[str] = []
    warnings: list[str] = []
    if "selection" not in [c.strip() for c in sources_cols]:
        return errors, warnings
    as_of_dt = _parse_utc(as_of) if as_of else None
    curated_hashes = _intake_user_curated_hashes(report_dir)
    dl_urls, dl_names, dl_shas = _download_proof(report_dir)
    curated_docs = False
    fetched = False
    for row in sources_rows:
        cid = (row.get("claim_id") or "?").strip()
        sel = (row.get("selection") or "").strip().lower()
        kind = (row.get("kind") or "").strip().lower()
        tier = (row.get("tier") or "").strip()
        ret = (row.get("retrieved_utc") or "").strip()
        url = (row.get("url") or "").strip()
        is_local = bool(url) and (url.startswith("file://") or "://" not in url)
        sha = _declared_sha(row)
        if sel not in VALID_SELECTIONS:
            errors.append(f"Source '{cid}' in appendix/sources.csv has selection '{sel}'; use one of: {', '.join(VALID_SELECTIONS)}.")
            continue
        if sel == "user-curated":
            curated_docs = curated_docs or kind in DOCUMENT_KINDS
            if not ret:
                errors.append(
                    f"Source '{cid}' is user-curated but has no retrieved_utc: write when it was retrieved from its "
                    f"origin (ISO UTC) or 'unknown'."
                )
            elif ret.lower() == "unknown" and re.search(r"\bTier\s*[12]\b", tier, re.IGNORECASE):
                errors.append(
                    f"Source '{cid}' is user-curated with retrieved_utc unknown, so it cannot be {tier}: without an origin "
                    f"URL, a retrieval date and a hash an uploaded file stays Tier 3."
                )
            if is_local and re.search(r"\bTier\s*1\b", tier, re.IGNORECASE):
                errors.append(
                    f"Source '{cid}' is a local user-curated file ('{url}') and cannot be Tier 1 without a verified "
                    f"external origin URL."
                )
        elif sel == "agent-fetched" and kind != "own-computation":
            if sha and sha[:12] in curated_hashes:
                errors.append(
                    f"Source '{cid}' was ingested as user-curated in appendix/intake.md (sha256 {sha[:12]}) and cannot "
                    f"be relabelled agent-fetched."
                )
            if kind in ("data", "literature") and re.search(r"\bTier\s*[12]\b", tier, re.IGNORECASE):
                fetched = True
        ret_dt = _parse_utc(ret) if ret and ret.lower() != "unknown" else None
        if ret and ret.lower() != "unknown" and ret_dt is None:
            errors.append(f"Source '{cid}' has an invalid retrieved_utc '{ret}' (use ISO 8601 UTC or 'unknown').")
        if sel == "agent-fetched" and kind != "own-computation":
            if run_start is not None and ret_dt is not None and ret_dt < run_start:
                errors.append(
                    f"Source '{cid}' is marked agent-fetched but retrieved_utc ({ret}) precedes run_started_utc "
                    f"({run_start.strftime('%Y-%m-%dT%H:%M:%SZ')}); fetched sources must be acquired during this run."
                )
            if kind == "data" and report_dir is not None:
                fname = Path(unquote(url)).name if url else ""
                has_proof = (
                    (url and any(url in u or u in url for u in dl_urls))
                    or (fname and fname in dl_names)
                    or (sha and sha[:12] in dl_shas)
                )
                if not has_proof:
                    (errors if level == 3 else warnings).append(
                        f"Source '{cid}' is marked agent-fetched (kind=data) with no matching record in "
                        f"appendix/download_log.csv or appendix/data_attempts.csv."
                    )
        if ret_dt is not None and as_of_dt is not None:
            if as_of_dt.date() < ret_dt.date():
                errors.append(f"As-Of Date {as_of} is earlier than {cid}'s retrieved_utc {ret}.")
            elif (as_of_dt - ret_dt).days > MAX_SNAPSHOT_AGE_DAYS:
                warnings.append(
                    f"Source '{cid}' was retrieved {(as_of_dt - ret_dt).days} days before the As-Of Date; refresh the "
                    f"snapshot or say in Section 3 why that vintage is the right one."
                )
    if curated_docs and not fetched:
        (errors if level == 3 else warnings).append(
            "no agent-fetched source outside the user's corpus (must be Tier 1 or Tier 2 data/literature): at Level 2+ "
            "search for counter-evidence yourself and register what you find with selection=agent-fetched; a corpus the user "
            "chose is never sufficient."
        )
    return errors, warnings


def check_inbox(report_dir: Path, sources_rows: list[dict[str, str]]) -> list[str]:
    inbox = report_dir / "inbox"
    if not inbox.is_dir():
        return []
    declared = [h for h in (_declared_sha(r) for r in sources_rows) if h]
    out = []
    for fp in sorted(inbox.rglob("*")):
        if fp.is_file() and not any(_file_sha256(fp).startswith(h) for h in declared):
            out.append(
                f"inbox/{fp.relative_to(inbox).as_posix()} is not registered in appendix/sources.csv; run "
                f"`local_data.py intake` or remove it."
            )
    return out


def _norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", t)).strip().lower()


def check_preregistration(
    report_dir: Path,
    clean_text: str,
    section_positions: dict[str, int],
    level: int = 2,
    run_start: Any = None,
    numbers_data: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    path = report_dir / "appendix" / "preregistration.json"
    if not path.is_file():
        if level == 3:
            return [
                "Level 3 report requires appendix/preregistration.json sealed before analysis "
                "(run `local_data.py prereg` in Stage 1)."
            ], []
        return [], []
    import hashlib

    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        for req_k in ("sealed_utc", "hypotheses", "plan"):
            _ = rec[req_k]
        body = {k: rec[k] for k in ("sealed_utc", "hypotheses", "plan", "known_artifacts", "post_hoc") if k in rec}
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return [f"appendix/preregistration.json is unreadable ({exc})."], []
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    if digest != rec.get("sha256"):
        return ["appendix/preregistration.json was edited after sealing (sha256 mismatch); a preregistration is sealed once."], []
    errors: list[str] = []
    warnings: list[str] = []
    sink = errors if level == 3 else warnings
    if rec.get("post_hoc"):
        sink.append(
            "appendix/preregistration.json is marked post_hoc=true (sealed after analysis outputs already existed)."
        )
    sealed_dt = _parse_utc(str(rec.get("sealed_utc") or ""))
    if run_start is not None and sealed_dt is not None and sealed_dt < run_start:
        sink.append(
            f"appendix/preregistration.json sealed_utc ({rec['sealed_utc']}) precedes run_started_utc "
            f"({run_start.strftime('%Y-%m-%dT%H:%M:%SZ')})."
        )
    sec2 = _norm_text(_extract_section_slice(clean_text, section_positions, "Framing & Hypotheses"))
    for key, text in (body["hypotheses"] or {}).items():
        if _norm_text(str(text)) not in sec2:
            warnings.append(
                f"{key} in Section 2 differs from appendix/preregistration.json (sealed {body['sealed_utc']}); keep the "
                f"sealed wording or say in Section 3 what changed after sealing and why."
            )
    # HARKing check: flag hypotheses containing >= 2 exact computed decimal figures from numbers.json
    if numbers_data:
        computed_nums: set[str] = set()
        for val in numbers_data.values():
            for tok in re.findall(r"\d+[.,]\d{2,}", str(val)):
                computed_nums.add(tok.replace(",", "."))
        if computed_nums:
            hyp_text = " ".join(str(v) for v in (body["hypotheses"] or {}).values())
            hyp_nums = {tok.replace(",", ".") for tok in re.findall(r"\d+[.,]\d{2,}", hyp_text)}
            hits = sorted(hyp_nums & computed_nums)
            if len(hits) >= 2:
                sink.append(
                    f"appendix/preregistration.json hypothesis contains exact computed result figures from "
                    f"appendix/numbers.json ({', '.join(hits[:4])}, possible HARKing); state directional or threshold "
                    f"predictions before running analysis.py."
                )
    return errors, warnings


_TABLE_SKIP_RE = re.compile(
    r"\{\{[^}]+\}\}|\[@[^\]]+\]|(?:Section|Secci[oó]n|§)\s*\d+(?:\.\d+)*"
    r"|\bTier\s*[123]\b|\bN-[12]\b|\b\d+(?:/\d+)?\s*(?:kV|MW|GW|MWh|GWh|Hz)\b"
    r"|\b\d{4}-\d{2}(?:-\d{2})?\b",
    re.IGNORECASE,
)
_TABLE_STAT_RE = re.compile(r"(?<![\w.])(?:[+\-\u2212]\d+(?:[.,]\d+)?%?|\d+[.,]\d+%?|\d+%)")


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
    # Build normalized haystack of output.txt + numbers.json values
    hay_parts = [output_text]
    if numbers_data:
        hay_parts.extend(str(v) for v in numbers_data.values())
    hay_raw = "\n".join(hay_parts)
    hay_norm = hay_raw.replace("\u2212", "-").replace(",", ".")

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
        cleaned = _TABLE_SKIP_RE.sub(" ", stripped)
        for tok in _TABLE_STAT_RE.findall(cleaned):
            norm = tok.replace("\u2212", "-").replace(",", ".")
            bare = norm.lstrip("+-").rstrip("%")
            if re.fullmatch(r"(?:19|20)\d\d", bare):
                continue
            if norm in seen:
                continue
            candidates = {tok, norm, bare, bare.replace(".", ",")}
            if any(re.search(rf"(?<![\d.,]){re.escape(c)}(?!\d)", hay_raw) or re.search(rf"(?<![\d.,]){re.escape(c)}(?!\d)", hay_norm) for c in candidates if c):
                continue
            seen.add(norm)
            untraced.append(tok)
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


def _extract_citation_ids(text: str) -> list[str]:
    ids: list[str] = []
    for m in CITE_GROUP_RE.finditer(text):
        for tok in re.split(r"\s*[;,]\s*", m.group(1)):
            cid = tok.strip().lstrip("@")
            if cid:
                ids.append(cid)
    return ids


def _find_charts_json(report_dir: Path, appendix_dir: Path, explicit: Path | None = None) -> Path | None:
    """Locate charts.json: explicit path, then <report_dir>/charts.json, then <appendix>/charts.json."""
    if explicit is not None:
        return explicit if explicit.is_file() else None
    for candidate in (report_dir / "charts.json", appendix_dir / "charts.json"):
        if candidate.is_file():
            return candidate
    return None


HARDCODED_NUM_RE = re.compile(r"(?<![\w.@#{:-])(\d+[.,]\d+|\d{3,})(?![\w{])")
MIN_TYPED_NUMBERS = 5  # below this many retyped numbers the coverage warning stays quiet
MIN_MARKER_SHARE = 0.60
MIN_TYPED_SUMMARY = 3  # C5: verdict + Section 1 must not retype 3+ output figures without any placeholder
SUMMARY_NUM_RE = re.compile(r"(?<![\w.@#{:-])(\d+[.,]\d+|\d{2,})(?![\w{])")
SECTION_REF_RE = re.compile(r"(?:§\s*|\b(?:Secci[oó]n|Section|Sec\.)\s+)\d+(?:\.\d+)*", re.IGNORECASE)
LIMITATION_FALLBACKS: tuple[str, ...] = ("limitation", "limitación", "limitacion", "none", "ninguno", "n/a")
HOME_PATH_RE = re.compile(r"/home/[^/\s]+/|/Users/[^/\s]+|[A-Za-z]:\\Users\\", re.IGNORECASE)
GATE_MIN_CHARS = 400
SELECTION_LABEL_RE = re.compile(
    r"Selection bias: user-curated corpus|Sesgo de selecci[oó]n: corpus elegido por el usuario", re.IGNORECASE
)
MAX_SNAPSHOT_AGE_DAYS = 365
VERDICT_MAX_SENTENCES = 3
VERDICT_MAX_NUMBERS = 5
_VERDICT_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡`*\[(])")
_VERDICT_NUMBER_RE = re.compile(r"(?<![\w.@#{:-])[+\-\u2212]?\d+(?:[.,]\d+)*%?(?![\w}]|-[A-Za-z])")
_WEAK_TITLE_RE = re.compile(
    r"abstract[\s-]only|abstract\s+read|full\s+text\s+not\s+(?:read|retrieved)|solo\s+(?:el\s+)?resumen"
    r"|texto\s+no\s+recuperado|not\s+retrieved|no\s+recuperado",
    re.IGNORECASE,
)
_REVIEWER_CATEGORIES = (
    "Over-calibrated claims",
    "Unattempted data shortcuts",
    "Missing counter-evidence and controls",
    "Interdisciplinary and forecasting flaws",
    "Decisions inside the noise",
    "Provenance contradictions",
)
# C1: the minimum shape each gate answer must have; mirrors the Output section of references/agents/*.md
GATE_MARKERS: dict[str, list[tuple[str, str]]] = {
    "source_verifier": [(f"check {n}", rf"^\s*{n}[.)]\s+(?:PASS|FAIL)\b") for n in range(1, 8)]
    + [("SOURCE-VERIFIER: PASS|FAIL", r"^\s*SOURCE-VERIFIER:\s*(?:PASS|FAIL)\b")],
    "reviewer": [(title, re.escape(title)) for title in _REVIEWER_CATEGORIES]
    + [("MOST DAMAGING:", r"^\s*MOST DAMAGING:")],
    "qa": [(f"check {n}", rf"^\s*{n}[.)]?\s+(?:PASS|FAIL)\b") for n in range(1, 9)]
    + [("QA: PASS|FAIL", r"^\s*QA:\s*(?:PASS|FAIL)\b"), ("FAIL count: <n>", r"^\s*FAIL count:\s*\d+")],
}
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


_NAME_STOPWORDS = frozenset({"serie", "series", "datos", "data", "para", "from", "with", "sobre", "entre", "the"})


def _name_tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{4,}", folded) if w not in _NAME_STOPWORDS}


def _named_in_any(target: str, lines: list[str]) -> bool:
    """True when one line mentions at least 2 (and at least half) of the target's significant words.

    Reports paraphrase their data series ("Serie oficial del techo y piso" for "Serie diaria oficial del
    techo/piso de la banda"), so an exact-substring test misses the very limitation it should catch.
    """
    want = _name_tokens(target)
    if not want:
        return False
    for line in lines:
        folded = unicodedata.normalize("NFKD", line.lower()).encode("ascii", "ignore").decode()
        hits = sum(1 for w in want if w in folded)
        if hits >= 2 and hits >= 0.5 * len(want):
            return True
    return False


def _parse_utc(value: str):
    """ISO-8601 UTC (``2026-11-20T09:30:00Z``) or a bare date (midnight UTC) -> aware datetime, else None."""
    from datetime import datetime, timezone

    v = (value or "").strip()
    if not v:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        v += "T00:00:00+00:00"
    v = re.sub(r"Z$", "+00:00", v)
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


AS_OF_RE = re.compile(r"As-Of(?:\s+Date)?\)?\s*:?\**\s*:?\**\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def _as_of_date(markdown_text: str) -> str:
    for line in markdown_text.splitlines()[:20]:
        m = AS_OF_RE.search(line)
        if m:
            return m.group(1)
    return ""


def _resolve_run_start(report_dir: Path | None, explicit: str | None, markdown_text: str):
    """(run start, where it came from): appendix/run.json (tool-stamped), --run-since, or the report date."""
    if report_dir is not None:
        run_json = report_dir / "appendix" / "run.json"
        if run_json.is_file():
            try:
                data = json.loads(run_json.read_text(encoding="utf-8"))
                dt = _parse_utc(str(data.get("run_started_utc", ""))) if isinstance(data, dict) else None
                if dt is not None:
                    return dt, "appendix/run.json"
            except (OSError, json.JSONDecodeError):
                pass
    if explicit:
        dt = _parse_utc(_resolve_run_since(explicit, ""))
        if dt is not None:
            return dt, "--run-since"
    dt = _parse_utc(_as_of_date(markdown_text) or _resolve_run_since(None, markdown_text))
    return (dt, "report date") if dt is not None else (None, "")


def _resolve_run_since(explicit: str | None, markdown_text: str) -> str:
    """Run start (YYYY-MM-DD): the explicit value, else the first ISO date in the report's first 20 lines."""
    if explicit:
        m = DATE_RE.search(explicit)
        return m.group(1) if m else ""
    for line in markdown_text.splitlines()[:20]:
        m = DATE_RE.search(line)
        if m:
            return m.group(1)
    return ""


def validate_report_full(
    markdown_text: str,
    *,
    level: int | None = None,
    report_dir: Path | None = None,
    charts_path: Path | None = None,
    run_since: str | None = None,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a Heurisma markdown report."""
    errors: list[str] = []
    warnings: list[str] = []

    if not markdown_text or not markdown_text.strip():
        return ["Report is empty. All 7 required Heurisma sections must be present."], warnings

    clean_text = _strip_fenced_code_blocks(markdown_text)

    if HOME_PATH_RE.search(markdown_text):
        errors.append(
            "report.md contains a home-directory path (e.g. /home/<user>/…); remove it so the report does not leak "
            "the author's machine."
        )
    as_of = _as_of_date(markdown_text)
    if as_of:
        from datetime import datetime, timedelta, timezone

        as_of_dt = _parse_utc(as_of)
        if as_of_dt is not None and as_of_dt > datetime.now(timezone.utc) + timedelta(days=1):
            errors.append(f"As-Of Date {as_of} is in the future.")
        if report_dir is not None and as_of_dt is not None:
            start_dt, start_src = _resolve_run_start(report_dir, None, "")
            if start_src == "appendix/run.json" and as_of_dt.date() < start_dt.date():
                errors.append(
                    f"As-Of Date {as_of} is earlier than the run start {start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')} "
                    f"(appendix/run.json)."
                )
    verdict_match = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:?\**\s*:?\**\s*(.+)", clean_text, re.IGNORECASE)
    if verdict_match:
        n_sent, n_num = _verdict_stats(verdict_match.group(1))
        if n_sent > VERDICT_MAX_SENTENCES:
            errors.append(
                f"Calibrated Verdict has {n_sent} sentences (maximum {VERDICT_MAX_SENTENCES}); keep it abstract-style "
                f"and move detail to Section 4."
            )
        if n_num > VERDICT_MAX_NUMBERS:
            errors.append(
                f"Calibrated Verdict has {n_num} numbers (maximum {VERDICT_MAX_NUMBERS}, counting {{{{num:key}}}} "
                f"placeholders); move the rest to Section 4 tables."
            )

    # 1. Check all 7 required top-level section headings in order (EN or ES)
    last_pos = -1
    section_positions: dict[str, int] = {}
    for label, pattern in REQUIRED_SECTIONS:
        match = re.search(pattern, clean_text, flags=re.MULTILINE | re.IGNORECASE)
        if not match:
            errors.append(f"Missing required section: '## {label}'")
        else:
            pos = match.start()
            section_positions[label] = pos
            if pos < last_pos:
                errors.append(f"Section out of order: '## {label}' must appear after preceding sections.")
            last_pos = max(last_pos, pos)

    # 2. Check minimum substance across required sections (rejects empty/filler stubs)
    min_words_by_section = {
        "Executive Summary": 30,
        "Findings": 30,
        "Counter-Evidence & Alternative Explanations": 12,
        "Limitations & Open Questions": 12,
    }
    for label, min_words in min_words_by_section.items():
        sec_text = _extract_section_slice(clean_text, section_positions, label)
        if sec_text:
            body_lines = [ln.strip() for ln in sec_text.splitlines()[1:] if ln.strip()]
            body_words = sum(len(ln.split()) for ln in body_lines)
            if body_words < min_words:
                errors.append(
                    f"Section '## {label}' lacks substantive content "
                    f"({body_words} words; minimum {min_words} words required)."
                )

    # 3. Check global presence of canonical/localized epistemic calibration tags
    tag_count = sum(clean_text.count(tag) for tag in ALL_TAGS)
    if tag_count == 0:
        errors.append(
            "Missing epistemic calibration tags: report must include canonical tags "
            "([Strong]/[Fuerte], [Moderate]/[Moderada], [Preliminary]/[Preliminar], or [Speculative]/[Especulativa])."
        )

    # 4. Check hypotheses ($H_0$ / H0 / H₀ and $H_1$ / H1 / H₁) strictly inside Section 2
    if "Framing & Hypotheses" in section_positions:
        sec2 = _extract_section_slice(clean_text, section_positions, "Framing & Hypotheses")
        has_h0 = bool(re.search(r"(\$H_0\$|\bH_0\b|\bH0\b|H₀|Null Hypothesis|Hip[oó]tesis nula)", sec2, re.IGNORECASE))
        has_h1 = bool(re.search(r"(\$H_1\$|\bH_1\b|\bH1\b|H₁|Alternative Hypothesis|Hip[oó]tesis alternativa)", sec2, re.IGNORECASE))
        if not (has_h0 and has_h1):
            errors.append(
                "Missing explicit null and alternative hypotheses (H_0 and H_1) inside Section 2 (Framing & Hypotheses)."
            )

    sources_rows, sources_cols = _load_sources_rows(report_dir)
    source_by_id = {(r.get("claim_id") or "").strip(): r for r in sources_rows if (r.get("claim_id") or "").strip()}
    tier3_titles = [
        (row.get("source_title") or "").strip().lower()
        for row in sources_rows
        if re.search(r"\bTier\s*3\b", (row.get("tier") or ""), re.IGNORECASE)
        and len((row.get("source_title") or "").strip()) >= 4
    ]

    # 5. Validate Claim-Evidence Matrix structure, column count, >=2 rows, per-row tags, and Strong+Tier3/press ban
    if "Claim-Evidence Matrix" in section_positions:
        matrix_block = _extract_section_slice(clean_text, section_positions, "Claim-Evidence Matrix")
        table_lines = [
            line.strip()
            for line in matrix_block.splitlines()
            if line.strip().startswith("|") and line.strip().endswith("|")
        ]
        if len(table_lines) < 3:
            errors.append(
                "Claim-Evidence Matrix section must contain a populated Markdown table "
                "(header, separator, and at least 2 claim-evidence rows)."
            )
        else:
            header_cells = _split_md_table_row(table_lines[0])
            if len(header_cells) < 4:
                errors.append(
                    f"Claim-Evidence Matrix table must have at least 4 columns "
                    f"(Claim, Discipline, Evidence/Tier, Confidence Tag); found {len(header_cells)}."
                )
            data_rows = [
                row
                for row in table_lines[1:]
                if not _is_separator_row(_split_md_table_row(row))
            ]
            if len(data_rows) < 2:
                errors.append(
                    f"Claim-Evidence Matrix table must contain at least 2 substantive claim rows; found {len(data_rows)}."
                )
            for row_idx, row in enumerate(data_rows, start=1):
                if not any(tag in row for tag in ALL_TAGS):
                    errors.append(
                        f"Claim-Evidence Matrix row {row_idx} is missing a canonical confidence tag "
                        f"([Strong], [Moderate], [Preliminary], or [Speculative])."
                    )
                if source_by_id and any(st in row for st in STRONG_TAGS):
                    # P0-3: decided from sources.csv by claim_id, so relabelling a source in prose cannot hide it
                    row_ids = _extract_citation_ids(row)
                    known = [cid for cid in row_ids if cid in source_by_id]
                    if not row_ids:
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} is [Strong] but has no [@id] citation: "
                            f"a strong claim must cite the evidence that carries it."
                        )
                    elif known and all(_is_weak_source(source_by_id[cid]) for cid in known):
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} is [Strong] resting only on weak source(s) "
                            f"{', '.join(known)} (Tier 3, press, own-computation or abstract-only in "
                            f"appendix/sources.csv); cite an independent Tier 1/2 source or lower the tag."
                        )
                curated = _curated_only_ids(row, source_by_id)
                if curated:
                    limits = _extract_section_slice(clean_text, section_positions, "Limitations & Open Questions")
                    if any(st in row for st in STRONG_TAGS):
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} rests only on user-curated source(s) {', '.join(curated)}; "
                            f"a claim supported only by documents the user chose is capped at [Moderate] and labelled "
                            f"'Selection bias: user-curated corpus'."
                        )
                    elif not (SELECTION_LABEL_RE.search(row) or SELECTION_LABEL_RE.search(limits)):
                        (errors if level == 3 else warnings).append(
                            f"Claim-Evidence Matrix row {row_idx} rests only on user-curated source(s) {', '.join(curated)}; "
                            f"label it 'Selection bias: user-curated corpus' in the row or in Section 7."
                        )
                if any(st in row for st in STRONG_TAGS):
                    row_lower = row.lower()
                    is_low_tier = bool(LOW_TIER_SOURCE_RE.search(row)) or any(
                        title in row_lower for title in tier3_titles
                    )
                    if is_low_tier:
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} pairs [Strong] with Tier 3 / press evidence, "
                            f"which violates the epistemic calibration scale."
                        )

    # 6. Level 2 & Level 3 artifact, figure (V1), citation (V2), provenance (V5), hygiene (V6), and verdict-number (P11) checks
    if level is not None and level >= 2 and report_dir is not None:
        appendix_dir = report_dir / "appendix"
        if not appendix_dir.is_dir():
            errors.append(f"Level {level} report requires an 'appendix/' directory at {appendix_dir}.")
        else:
            py_files = list(appendix_dir.glob("*.py"))
            if not py_files:
                errors.append(f"Level {level} report requires at least one reproducible Python script in {appendix_dir}.")
            if not (appendix_dir / "output.txt").is_file():
                errors.append(f"Level {level} report requires 'appendix/output.txt' with executed script output.")
            if not (appendix_dir / "sources.csv").is_file():
                errors.append(f"Level {level} report requires 'appendix/sources.csv' logging sources and access dates.")

            # V1: {{fig:id}} <-> charts.json consistency (W1: charts.json lives in the report root)
            charts_json = _find_charts_json(report_dir, appendix_dir, charts_path)
            if charts_json is None:
                # P1-6: a table-only study needs no charts.json; it is required only when the report places figures
                if FIG_MARKER_RE.search(clean_text) or charts_path is not None:
                    where = charts_path if charts_path is not None else f"{report_dir / 'charts.json'} or {appendix_dir / 'charts.json'}"
                    errors.append(f"Level {level} report requires charts.json: charts.json not found ({where}).")
            else:
                try:
                    charts_data = json.loads(charts_json.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"Invalid JSON in {charts_json}: {exc}")
                    charts_data = []
                if re.search(r"(?<![\w\"])-?(?:NaN|Infinity)(?![\w\"])", charts_json.read_text(encoding="utf-8", errors="replace")):
                    errors.append(
                        f"{charts_json.name} is not strict JSON: it contains NaN/Infinity (write with allow_nan=False and "
                        f"drop or fix the non-finite values)."
                    )
                if isinstance(charts_data, list) and charts_data:
                    try:
                        from svg_charts import validate_charts_schema

                        as_of_for_charts = _as_of_date(markdown_text) or None
                        for ch in charts_data:
                            errors.extend(validate_charts_schema(ch, as_of_date=as_of_for_charts))
                    except ImportError:  # validator run in isolation from svg_charts.py
                        pass
                    try:
                        from svg_charts import chart_warnings
                    except ImportError:  # validator run in isolation from svg_charts.py
                        chart_warnings = None  # type: ignore[assignment]
                    if chart_warnings is not None:
                        for ch in charts_data:
                            if isinstance(ch, dict):
                                warnings.extend(chart_warnings(ch))
                    chart_ids = {str(ch.get("id") or f"fig_{i + 1}") for i, ch in enumerate(charts_data)}
                    placed_figs = FIG_MARKER_RE.findall(clean_text)
                    if not placed_figs:
                        errors.append(
                            f"Level >= 2 report with {charts_json.name} must place figures inline using {{{{fig:id}}}} markers."
                        )
                    for fid in placed_figs:
                        if fid not in chart_ids:
                            errors.append(f"Unknown figure marker '{{{{fig:{fid}}}}}' not found in {charts_json.name}.")
                    for cid in sorted(chart_ids - set(placed_figs)):
                        warnings.append(
                            f"Chart '{cid}' in {charts_json.name} is not placed inline via {{{{fig:{cid}}}}} (will render in Additional Figures)."
                        )

            # W2: every {{num:key}} marker must resolve against appendix/numbers.json
            used_num_keys = sorted(set(NUM_MARKER_RE.findall(clean_text)))
            if used_num_keys:
                known_keys: set[str] = set()
                numbers_json = appendix_dir / "numbers.json"
                if numbers_json.is_file():
                    try:
                        loaded_nums = json.loads(numbers_json.read_text(encoding="utf-8"))
                        if isinstance(loaded_nums, dict):
                            known_keys = {str(k) for k in loaded_nums}
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"Invalid JSON in appendix/numbers.json: {exc}")
                for key in used_num_keys:
                    if key not in known_keys:
                        errors.append(
                            f"Unresolved marker '{{{{num:{key}}}}}': key '{key}' not found in appendix/numbers.json."
                        )

            # V2: In-text citations [@id] <-> sources.csv
            if sources_rows:
                valid_claim_ids = {(r.get("claim_id") or "").strip() for r in sources_rows if (r.get("claim_id") or "").strip()}
                sec4 = _extract_section_slice(clean_text, section_positions, "Findings")
                all_cited_ids = _extract_citation_ids(clean_text)
                sec4_cited_ids = _extract_citation_ids(sec4)
                sec4_has_numeric_cite = bool(NUMERIC_CITE_RE.search(sec4))
                if not sec4_cited_ids and not sec4_has_numeric_cite:
                    errors.append(
                        "Level >= 2 report must include in-text citations (e.g. [@C1]) in Section 4 (Findings)."
                    )
                for cid in sorted(set(all_cited_ids) - valid_claim_ids):
                    errors.append(f"In-text citation '[@{cid}]' does not match any claim_id in appendix/sources.csv.")
                for uncited in sorted(valid_claim_ids - set(all_cited_ids)):
                    msg = f"Source '{uncited}' in appendix/sources.csv is never cited in the report text."
                    (errors if level >= 3 else warnings).append(msg)

                # P1-5: every source row carries a valid kind
                if sources_rows and "kind" not in [c.strip() for c in sources_cols]:
                    errors.append(
                        "appendix/sources.csv has no kind column: add kind (data | literature | press | own-computation) "
                        "to every row."
                    )
                else:
                    for srow in sources_rows:
                        cid = (srow.get("claim_id") or "?").strip()
                        kind_value = (srow.get("kind") or "").strip().lower()
                        if not kind_value:
                            errors.append(f"Source '{cid}' in appendix/sources.csv has no kind.")
                        elif kind_value not in VALID_KINDS:
                            errors.append(
                                f"Source '{cid}' in appendix/sources.csv has kind '{kind_value}'; "
                                f"use one of: {', '.join(VALID_KINDS)}."
                            )

                warnings.extend(check_source_domains(sources_rows))
                _resolved_start, _run_src = _resolve_run_start(report_dir, run_since, markdown_text)
                _run_start_dt = _resolved_start if (_resolved_start is not None and "run.json" in _run_src) else None
                sel_err, sel_warn = check_selection(
                    sources_rows, sources_cols, _as_of_date(markdown_text), level,
                    report_dir=report_dir, run_start=_run_start_dt,
                )
                errors.extend(sel_err)
                warnings.extend(sel_warn)
                warnings.extend(check_inbox(report_dir, sources_rows))
                _nums_data_for_checks: dict[str, Any] | None = None
                _nums_path = appendix_dir / "numbers.json"
                if _nums_path.is_file():
                    try:
                        _loaded_n = json.loads(_nums_path.read_text(encoding="utf-8"))
                        if isinstance(_loaded_n, dict):
                            _nums_data_for_checks = _loaded_n
                    except (OSError, json.JSONDecodeError):
                        pass
                pre_err, pre_warn = check_preregistration(
                    report_dir, clean_text, section_positions,
                    level=level, run_start=_run_start_dt, numbers_data=_nums_data_for_checks,
                )
                errors.extend(pre_err)
                warnings.extend(pre_warn)

                # V5a: file:// rows in sources.csv must include a sha256 hash
                for row_idx, srow in enumerate(sources_rows, start=1):
                    url = (srow.get("url") or "").strip()
                    is_own = (srow.get("kind") or "").strip().lower() == "own-computation"
                    if url and not is_own and (url.startswith("file://") or "://" not in url):  # file:// or scheme-less local path
                        title = srow.get("source_title") or ""
                        sha_col = (srow.get("sha256") or "").strip()
                        has_hash = bool(SHA_HEX_RE.search(sha_col)) or (
                            "sha256" in title.lower() and bool(SHA_HEX_RE.search(title))
                        )
                        if not has_hash:
                            errors.append(
                                f"Local source row {row_idx} ('{url}') in appendix/sources.csv must include a SHA-256 hash "
                                f"(in source_title or sha256 column)."
                            )
                        else:
                            # P0-1: recompute the hash; a declared hash that no longer matches the file is an error
                            declared = _declared_sha(srow)
                            local_file = _local_source_path(url, report_dir)
                            if declared and not local_file.is_file():
                                (errors if level >= 3 else warnings).append(
                                    f"'{url}' is registered in appendix/sources.csv with sha256 {declared} but was not found "
                                    f"on disk."
                                )
                            elif declared:
                                actual = _file_sha256(local_file)
                                if not actual.startswith(declared):
                                    errors.append(
                                        f"'{url}' changed since it was registered in appendix/sources.csv: "
                                        f"SHA-256 {actual[:12]} != declared {declared}."
                                    )

            # P0-1: hashes logged by fetch_data.py are recomputed as well
            dl_csv = appendix_dir / "download_log.csv"
            if dl_csv.is_file():
                try:
                    with dl_csv.open(encoding="utf-8-sig", newline="") as fh:
                        dl_rows = list(csv.DictReader(fh))
                except OSError:
                    dl_rows = []
                for dl in dl_rows:
                    fname = (dl.get("file") or "").strip()
                    declared_dl = SHA_HEX_RE.search((dl.get("sha256") or "").strip())
                    target = appendix_dir / "data" / fname
                    if fname and declared_dl and target.is_file():
                        actual = _file_sha256(target)
                        if not actual.startswith(declared_dl.group(0).lower()):
                            errors.append(
                                f"appendix/download_log.csv: '{fname}' changed since it was logged: "
                                f"SHA-256 {actual[:12]} != declared {declared_dl.group(0).lower()[:12]}."
                            )

            # V5b (P1-2): every file in appendix/data/ must be registered by exact relative path or declared hash
            data_dir = appendix_dir / "data"
            if data_dir.is_dir():
                registered_paths, registered_hashes = _registered_data_files(report_dir, appendix_dir, sources_rows)
                for fp in sorted(data_dir.rglob("*")):
                    if not fp.is_file() or "__pycache__" in fp.parts:
                        continue
                    rel = fp.relative_to(data_dir).as_posix()
                    if rel in registered_paths:
                        continue
                    actual = _file_sha256(fp)
                    if any(actual.startswith(h) for h in registered_hashes):
                        continue
                    warnings.append(
                        f"Orphan data file 'appendix/data/{rel}' is not logged in "
                        f"appendix/download_log.csv or appendix/sources.csv."
                    )

            # V5c: data_attempts.csv canonical columns check (D2)
            attempts_csv = appendix_dir / "data_attempts.csv"
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8", newline="") as fh:
                        reader = csv.reader(fh)
                        header = [c.strip() for c in next(reader, [])]
                    missing_cols = [c for c in CANONICAL_DATA_ATTEMPTS_COLS if c not in header]
                    if missing_cols:
                        errors.append(
                            f"appendix/data_attempts.csv is missing canonical column(s): {', '.join(missing_cols)}."
                        )
                except OSError as exc:
                    errors.append(f"Unable to read appendix/data_attempts.csv: {exc}")

            # F2: an own computation (the report's own code) can never be Tier 1 evidence
            for srow in sources_rows:
                if (srow.get("kind") or "").strip().lower() == "own-computation" and re.search(
                    r"\bTier\s*1\b", srow.get("tier") or "", re.IGNORECASE
                ):
                    errors.append(
                        f"Source '{(srow.get('claim_id') or '?').strip()}' has kind=own-computation but tier Tier 1; "
                        f"the report's own computation is not independent evidence (use Tier 2/3 or a different kind)."
                    )

            # F1: source described as retrieved/full text although data_attempts.csv logs a failed attempt for its URL
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8", newline="") as fh:
                        attempt_rows = list(csv.DictReader(fh))
                except OSError:
                    attempt_rows = []
                ok_outcomes = {"used", "ok", "success", "succeeded", "retrieved"}
                for srow in sources_rows:
                    surl = (srow.get("url") or "").strip()
                    stitle = (srow.get("source_title") or "").lower()
                    if not surl or not re.search(r"full[\s-]?text|open[\s-]access|retrieved", stitle):
                        continue
                    for arow in attempt_rows:
                        outcome = (arow.get("outcome") or "").strip().lower()
                        touches = surl in (arow.get("query_or_endpoint") or "") or surl in (arow.get("source_tried") or "")
                        if touches and outcome and outcome not in ok_outcomes:
                            warnings.append(
                                f"Source '{(srow.get('claim_id') or '?').strip()}' is described as full text/retrieved but "
                                f"appendix/data_attempts.csv logs a failed attempt for the same URL ({surl}): "
                                f"'{arow.get('outcome')}'."
                            )
                            break

            # P2: every subagent gate leaves a trace in appendix/gates/ (a manual record when no subagents exist)
            gates_dir = appendix_dir / "gates"
            gate_sink = errors if level == 3 else warnings
            for gate in GATE_FILES:
                if gate == "reviewer" and level != 3:  # Reviewer #2 is dispatched at Level 3 only
                    continue
                gpath = gates_dir / f"{gate}.md"
                gtext = gpath.read_text(encoding="utf-8", errors="replace") if gpath.is_file() else ""
                if not gtext.strip():
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is missing or empty; save the {gate.replace('_', '-')} gate output "
                        f"(or the manual checks that replaced it) there."
                    )
                    continue
                if len(gtext.strip()) < GATE_MIN_CHARS:
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is under {GATE_MIN_CHARS} characters; save the gate's full answer, "
                        f"not a placeholder."
                    )
                missing = [label for label, pattern in GATE_MARKERS[gate] if not re.search(pattern, gtext, re.MULTILINE | re.IGNORECASE)]
                if missing:
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is missing marker(s) its prompt requires: {', '.join(missing)} "
                        f"(see references/agents/{gate.replace('_', '-')}.md, Output section)."
                    )
                _check_gate_binding(gate, gtext, report_dir, clean_text, section_positions, gate_sink, warnings)
                if gate == "qa" and not re.search(r"^QA:\s*PASS\b", gtext, re.MULTILINE):
                    if "gates/qa.md" not in markdown_text:
                        gate_sink.append(
                            "appendix/gates/qa.md has no 'QA: PASS' line; fix the failed checks, or name each accepted "
                            "FAIL with its justification in the report (cite appendix/gates/qa.md in Section 7)."
                        )

            # C8: gate files are embedded in report.html, so they must not quote home paths or literal markers
            if gates_dir.is_dir():
                for gpath in sorted(gates_dir.glob("*.md")):
                    gtext = gpath.read_text(encoding="utf-8", errors="replace")
                    if HOME_PATH_RE.search(gtext):
                        gate_sink_any = errors if level == 3 else warnings
                        gate_sink_any.append(
                            f"appendix/gates/{gpath.name} quotes a home-directory path; it is embedded in report.html, "
                            f"so report counts instead (e.g. 'home-directory paths in report.html: 0')."
                        )
                    non_quote_text = "\n".join(
                        ln for ln in gtext.splitlines() if not re.match(r"^\s*QUOTE:", ln)
                    )
                    if re.search(r"\{\{(?:num|fig):", non_quote_text):
                        (errors if level == 3 else warnings).append(
                            f"appendix/gates/{gpath.name} contains a literal {{{{num:…}}}}/{{{{fig:…}}}} marker; write "
                            f"'number placeholder' or 'figure marker' instead."
                        )

            # P1: a limitation cannot rest on attempts inherited from an earlier run (needs attempted_utc column)
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8-sig", newline="") as fh:
                        att_reader = csv.DictReader(fh)
                        att_cols = [c.strip() for c in (att_reader.fieldnames or [])]
                        att_rows = list(att_reader)
                except OSError:
                    att_cols, att_rows = [], []
                start, start_src = _resolve_run_start(report_dir, run_since, markdown_text)
                since = start.strftime("%Y-%m-%dT%H:%M:%SZ") if start else ""
                if start is not None and start_src == "report date":
                    warnings.append(
                        "no appendix/run.json: the run start is taken from the report date (day granularity), so a failure "
                        "logged earlier the same day counts as fresh; stamp the run with `local_data.py run-start` in Stage 0."
                    )
                inherit_sink = errors if level == 3 else warnings
                if "attempted_utc" not in att_cols:
                    inherit_sink.append(
                        "appendix/data_attempts.csv has no attempted_utc column: every attempt is treated as inherited; "
                        "add the column and re-run the rungs behind each limitation."
                    )
                elif not since:
                    warnings.append("cannot determine run start; pass --run-since YYYY-MM-DD")
                else:
                    ok_out = {"used", "ok", "success", "succeeded", "retrieved"}
                    limits_text = _extract_section_slice(clean_text, section_positions, "Limitations & Open Questions")
                    leaning_lines = [ln for ln in limits_text.splitlines() if ln.strip()] + [
                        ln for ln in clean_text.splitlines() if re.search(r"\b(?:Deferred|Diferida)\b", ln, re.IGNORECASE)
                    ]
                    fresh_targets: set[str] = set()
                    stale_targets: dict[str, str] = {}
                    for arow in att_rows:
                        outcome = (arow.get("outcome") or "").strip().lower()
                        if not outcome or outcome in ok_out:
                            continue
                        att_target = (arow.get("target_series") or arow.get("source_tried") or "?").strip()
                        stamp = (arow.get("attempted_utc") or "").strip()
                        stamp_dt = _parse_utc(stamp)
                        if stamp_dt is not None and stamp_dt >= start:
                            fresh_targets.add(att_target)
                            continue
                        # C3: only failures that end in a limitation (no real fallback) or that the report leans on
                        fallback = (arow.get("fallback_used") or "").strip().lower()
                        ends_in_limitation = not fallback or fallback.startswith(LIMITATION_FALLBACKS)
                        named = _named_in_any(att_target, leaning_lines)
                        if ends_in_limitation or named:
                            stale_targets.setdefault(att_target, stamp or "no date")
                    for att_target, stamp in sorted(stale_targets.items()):
                        if att_target in fresh_targets:
                            continue
                        inherit_sink.append(
                            f"Data attempt for '{att_target}' in appendix/data_attempts.csv is inherited from an earlier run "
                            f"({stamp} < run start {since}); re-run the rung in this session before relying on the limitation."
                        )

            # V6: Hygiene warnings (__pycache__, .pyc, 0-byte files)
            pycache_found = False
            for fp in sorted(appendix_dir.rglob("*"), key=lambda p: p.relative_to(appendix_dir).parts):
                if "__pycache__" in fp.parts or fp.suffix == ".pyc":
                    pycache_found = True
                    continue
                if fp.is_file() and fp.stat().st_size == 0:
                    warnings.append(f"0-byte file detected in appendix: 'appendix/{fp.relative_to(appendix_dir).as_posix()}'.")
            if pycache_found:
                warnings.append(
                    "Python bytecode artifacts (__pycache__ / .pyc) found in appendix/; run scripts with 'python3 -B'."
                )

            # P11: Optional verdict-number cross-check against appendix/output.txt
            output_txt = appendix_dir / "output.txt"
            if output_txt.is_file() and "{{num:" not in markdown_text:
                vm = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:\**\s*(.+)", clean_text, re.IGNORECASE)
                if vm:
                    out_text = output_txt.read_text(encoding="utf-8", errors="replace")
                    verdict_nums = re.findall(r"\b\d+(?:[.,]\d+)?\b", vm.group(1))
                    missing_nums = [
                        n for n in verdict_nums
                        if len(n) >= 2 and n not in out_text and n.replace(",", ".") not in out_text
                    ]
                    if missing_nums:
                        warnings.append(
                            f"Calibrated Verdict number(s) not found literally in appendix/output.txt: {', '.join(missing_nums[:5])}."
                        )

            # P3/C5: figures that come from output.txt should come through {{num:key}} (numbers.json), not be retyped
            if output_txt.is_file():
                out_txt = output_txt.read_text(encoding="utf-8", errors="replace")

                def _typed_from_output(section_text: str, pattern: re.Pattern[str]) -> set[str]:
                    body = re.sub(r"^#{1,6}\s.*$|\[@[^\]]+\]|\{\{[^}]+\}\}", "", section_text, flags=re.MULTILINE)
                    body = SECTION_REF_RE.sub("", body)
                    return {
                        t
                        for t in pattern.findall(body)
                        if not re.fullmatch(r"(?:19|20)\d\d", t)
                        and re.search(rf"(?<![\d.,]){re.escape(t)}(?!\d)", out_txt)
                    }

                summary = _extract_section_slice(clean_text, section_positions, "Executive Summary")
                typed_summary = _typed_from_output(summary, SUMMARY_NUM_RE)
                if len(typed_summary) >= MIN_TYPED_SUMMARY and not NUM_MARKER_RE.search(summary):
                    (errors if level == 3 else warnings).append(
                        f"Calibrated Verdict / Section 1 retypes {len(typed_summary)} figure(s) from appendix/output.txt "
                        f"({', '.join(sorted(typed_summary)[:4])}) and uses no {{{{num:key}}}} placeholder; export them to "
                        f"appendix/numbers.json and write {{{{num:key}}}}."
                    )

                findings = _extract_section_slice(clean_text, section_positions, "Findings")
                typed = _typed_from_output(findings, HARDCODED_NUM_RE)
                used = len(NUM_MARKER_RE.findall(markdown_text))
                if len(typed) >= MIN_TYPED_NUMBERS and used / (used + len(typed)) < MIN_MARKER_SHARE:
                    warnings.append(
                        f"numbers.json coverage is low: {len(typed)} number(s) in Section 4 appear in appendix/output.txt "
                        f"but only {used} {{{{num:key}}}} marker(s) are used (e.g. {', '.join(sorted(typed)[:3])}); "
                        f"write them as {{{{num:key}}}} so the text follows the analysis."
                    )

                # M25: numeric closure on Section 4 tables (catch fabricated stats absent from output.txt/numbers.json)
                _nums_for_closure: dict[str, Any] | None = None
                _nf = appendix_dir / "numbers.json"
                if _nf.is_file():
                    try:
                        _ln = json.loads(_nf.read_text(encoding="utf-8"))
                        if isinstance(_ln, dict):
                            _nums_for_closure = _ln
                    except (OSError, json.JSONDecodeError):
                        pass
                nc_err, nc_warn = check_numeric_closure(clean_text, section_positions, out_txt, _nums_for_closure, level)
                errors.extend(nc_err)
                warnings.extend(nc_warn)

    # 7. Level 3 Reviewer #2 Disposition Table & Deferred -> Data Attempts cross-check
    if level == 3:
        has_r2_heading = bool(
            re.search(
                r"(?:Reviewer\s*#?2|Revisor\s*#?2|Disposition|Disposici[oó]n)",
                clean_text,
                re.IGNORECASE,
            )
        )
        has_r2_action = bool(
            re.search(
                r"\|\s*[`*]{0,2}(?:Fixed|Refuted|Deferred|Corregida|Refutada|Diferida)[`*]{0,2}\b",
                clean_text,
                re.IGNORECASE,
            )
        )
        if not (has_r2_heading and has_r2_action):
            errors.append(
                "Level 3 report requires a Reviewer #2 Disposition table recording each critique "
                "and its action (Fixed / Refuted / Deferred)."
            )

        has_deferred = bool(
            re.search(
                r"\|\s*[`*]{0,2}(?:Deferred|Diferida)[`*]{0,2}\b",
                clean_text,
                re.IGNORECASE,
            )
        )
        if has_deferred:
            has_attempts_file = report_dir is not None and (report_dir / "appendix" / "data_attempts.csv").is_file()
            sec3 = _extract_section_slice(clean_text, section_positions, "Methodology & Evidence Standards")
            has_attempts_table = bool(
                re.search(r"(?:Data\s+Attempts|Intentos\s+de\s+datos|Source\s+Tried|Fuente\s+probada)", sec3, re.IGNORECASE)
            )
            if not (has_attempts_file or has_attempts_table):
                errors.append(
                    "Level 3 report marks Reviewer #2 critique(s) as Deferred/Diferida without a logged "
                    "'appendix/data_attempts.csv' or Data Attempts table in Section 3."
                )

    return errors, warnings


def validate_report(
    markdown_text: str,
    *,
    level: int | None = None,
    report_dir: Path | None = None,
    charts_path: Path | None = None,
    run_since: str | None = None,
) -> list[str]:
    """Return a list of validation error strings for a Heurisma markdown report (empty list = valid)."""
    errors, _ = validate_report_full(
        markdown_text, level=level, report_dir=report_dir, charts_path=charts_path, run_since=run_since
    )
    return errors


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

    path = Path(__file__).resolve().parent / "render_report.py"
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


REPRODUCED_FILES = ("appendix/output.txt", "appendix/numbers.json", "charts.json")
_ANALYSIS_CMD_RE = re.compile(r"^\s*(?:\$\s*)?(python3?\s+.*analysis\.py.*?)\s*$")


def _readme_analysis_command(report_dir: Path) -> str:
    readme = report_dir / "appendix" / "README.md"
    if not readme.is_file():
        return ""
    for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _ANALYSIS_CMD_RE.match(line.replace("`", ""))
        if m:
            return m.group(1)
    return ""


def reproduce(report_dir: Path, command: str | None = None, timeout: int = 300) -> list[str]:
    """Re-run appendix/analysis.py in a temporary copy and compare output.txt, numbers.json and charts.json.

    The command comes from ``appendix/README.md`` (first ``python3 … analysis.py`` line) or ``command``. The three
    artifacts are deleted from the copy first, so a file the command does not regenerate is reported, never passed.
    NOTE: this executes the report's own analysis.py; use it on reports you trust.
    """
    import hashlib
    import os
    import shlex
    import shutil
    import subprocess
    import tempfile

    cmd = command or _readme_analysis_command(report_dir)
    if not cmd:
        return ["reproduce: no analysis.py command found in appendix/README.md (pass --reproduce-cmd '…')."]
    try:
        tokens = shlex.split(cmd)
    except ValueError as exc:
        return [f"reproduce: cannot parse the command ({exc})."]
    redirect = None
    if ">" in tokens:
        i = tokens.index(">")
        redirect = tokens[i + 1] if i + 1 < len(tokens) else None
        tokens = tokens[:i]
    if not tokens or tokens[0] not in ("python", "python3"):
        return ["reproduce: unsupported command; use 'python3 -B appendix/analysis.py [args] [> appendix/output.txt]'."]
    argv = [sys.executable, "-B"] + [t for t in tokens[1:] if t != "-B"]
    if not any(t.endswith("analysis.py") for t in argv):
        return ["reproduce: the command does not run an analysis.py script."]
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "run"
        shutil.copytree(report_dir, work, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for rel in REPRODUCED_FILES:
            (work / rel).unlink(missing_ok=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONPATH=os.pathsep.join(
            [str(Path(__file__).resolve().parent), os.environ.get("PYTHONPATH", "")]))
        try:
            res = subprocess.run(
                argv, cwd=work, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env
            )
        except subprocess.TimeoutExpired:
            return [f"reproduce: appendix/analysis.py failed (timed out after {timeout}s)."]
        if res.returncode != 0:
            tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or [""]
            return [f"reproduce: appendix/analysis.py failed (exit {res.returncode}): {tail[0][:200]}"]
        if redirect:
            target = work / redirect
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(res.stdout.replace("\r\n", "\n").encode("utf-8"))
        for rel in REPRODUCED_FILES:
            original = report_dir / rel
            if not original.is_file():
                continue
            regenerated = work / rel
            if not regenerated.is_file():
                errors.append(f"reproduce: {rel} was not regenerated by the command (add its output flag or redirect).")
                continue
            a = hashlib.sha256(original.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            b = hashlib.sha256(regenerated.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            if a != b:
                errors.append(f"reproduce: {rel} differs after re-running appendix/analysis.py (sha256 {a[:12]} != {b[:12]}).")
    return errors


def _verdict_line(report_md: Path) -> str:
    text = report_md.read_text(encoding="utf-8", errors="replace") if report_md.is_file() else ""
    m = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:?\**\s*:?\**\s*(.+)", text, re.IGNORECASE)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def diff_runs(a_dir: Path, b_dir: Path) -> list[str]:
    """Human-readable differences between two runs of the same brief: data files, numbers.json and the verdict."""
    lines: list[str] = []

    def data_map(root: Path) -> dict[str, str]:
        d = root / "appendix" / "data"
        return {fp.relative_to(d).as_posix(): _file_sha256(fp) for fp in sorted(d.rglob("*")) if fp.is_file()} if d.is_dir() else {}

    da, db = data_map(a_dir), data_map(b_dir)
    data_lines = [f"  changed  {k}  ({da[k][:12]} -> {db[k][:12]})" for k in sorted(da.keys() & db.keys()) if da[k] != db[k]]
    data_lines += [f"  added    {k}" for k in sorted(db.keys() - da.keys())]
    data_lines += [f"  removed  {k}" for k in sorted(da.keys() - db.keys())]
    if data_lines:
        lines += ["data files:"] + data_lines

    def numbers(root: Path) -> dict[str, object]:
        f = root / "appendix" / "numbers.json"
        try:
            data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
        except json.JSONDecodeError:
            data = {}
        return data if isinstance(data, dict) else {}

    na, nb = numbers(a_dir), numbers(b_dir)
    num_lines = [f"  {k}: {na[k]} -> {nb[k]}" for k in sorted(na.keys() & nb.keys()) if na[k] != nb[k]]
    num_lines += [f"  added    {k} = {nb[k]}" for k in sorted(nb.keys() - na.keys())]
    num_lines += [f"  removed  {k} (was {na[k]})" for k in sorted(na.keys() - nb.keys())]
    if num_lines:
        lines += ["numbers.json:"] + num_lines

    va, vb = _verdict_line(a_dir / "report.md"), _verdict_line(b_dir / "report.md")
    if va != vb:
        lines += ["verdict changed:", f"  - {va}", f"  + {vb}"]
    return lines or ["no differences between the two runs (data files, numbers.json, verdict)."]


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
    (r"^numbers\.json coverage", "P1-NUM-COVERAGE", "report.md"),
    (r"^Claim-Evidence Matrix row \d+ is \[Strong\] but has no", "P0-STRONG-CITE", "report.md"),
    (r"^Claim-Evidence Matrix row \d+ (?:is \[Strong\] resting only|pairs \[Strong\])", "P0-STRONG", "report.md"),
    (r"^Claim-Evidence Matrix row \d+ rests only on user-curated", "P2-SELECTION", "report.md"),
    (r"^Claim-Evidence Matrix", "MATRIX", "report.md"),
    (r"appendix/gates/([a-z_]+)\.md quotes a home-directory path|appendix/gates/([a-z_]+)\.md contains a literal", "GATE-PRIVACY", "appendix/gates/"),
    (r"appendix/gates/([a-z_]+)\.md (?:is missing or empty|is under)", "GATE-MISSING", "appendix/gates/\\1.md"),
    (r"appendix/gates/([a-z_]+)\.md is missing marker", "GATE-MARKERS", "appendix/gates/\\1.md"),
    (r"appendix/gates/qa\.md has no 'QA: PASS'", "GATE-QA", "appendix/gates/qa.md"),
    (r"appendix/gates/([a-z_]+)\.md (?:is missing header|reviewed an earlier version|quotes |is a self-review)", "GATE-BINDING", "appendix/gates/\\1.md"),
    (r"^Level \d report requires charts\.json|^Invalid JSON in .*charts|is not strict JSON", "FIG-JSON", "charts.json"),
    (r"^Chart '[^']*': (?:near-identical|fan chart has last_label)", "FIG-DESIGN", "charts.json"),
    (r"^Chart '[^']*': ", "FIG-SCHEMA", "charts.json"),
    (r"must place figures inline|^Unknown figure marker", "FIG-MARKER", "report.md"),
    (r"is not placed inline via", "FIG-UNPLACED", "report.md"),
    (r"^Unresolved marker '\{\{num:|^Invalid JSON in appendix/numbers\.json", "W2-NUM", "report.md"),
    (r"^Level \d report requires (?:an 'appendix/'|at least one reproducible|'appendix/output|'appendix/sources)", "L2-APPENDIX", "appendix/"),
    (r"must include in-text citations", "CITE-NONE", "report.md"),
    (r"does not match any claim_id", "CITE-UNKNOWN", "report.md"),
    (r"is never cited in the report text", "CITE-UNCITED", "appendix/sources.csv"),
    (r"has no kind column|has no kind\.$|has kind '", "P1-KIND", "appendix/sources.csv"),
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
    (r"user-curated|selection '|retrieved_utc|days before the As-Of|agent-fetched source|^inbox/", "P2-SELECTION", "appendix/sources.csv"),
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


def _json_items(messages: list[str], severity: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for msg in messages:
        code, file = classify_message(msg)
        items.append({"severity": severity, "code": code, "file": file, "line": None, "message": msg})
    return items


def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Validate a Heurisma scientific inquiry report against structural, content, provenance, and epistemic gates."
    )
    parser.add_argument("--version", action="version", version=f"validate_report.py {__version__}")
    parser.add_argument("report_path", type=Path, help="Path to the Markdown report file to validate.")
    parser.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3),
        default=None,
        help="Optional depth level (2 checks appendix/, figures, citations, provenance; 3 also checks Reviewer #2 disposition table).",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Optional path to rendered report.html to verify alongside the Markdown report.",
    )
    parser.add_argument(
        "--charts",
        type=Path,
        default=None,
        help="Optional explicit path to charts.json (default: <report dir>/charts.json, then appendix/charts.json).",
    )
    parser.add_argument(
        "--gate-hash",
        choices=GATE_FILES,
        default=None,
        help="Print the hash a gate must declare as REVIEWED-SHA256 for the current files, and exit.",
    )
    parser.add_argument(
        "--gate-header",
        choices=GATE_FILES,
        default=None,
        help="Print the 3-line gate binding header (MODE, REVIEWED-SHA256, real REVIEWED-UTC) and exit.",
    )
    parser.add_argument(
        "--mode",
        choices=("subagent", "self-review"),
        default="subagent",
        help="Gate mode used with --gate-header (default: subagent).",
    )
    parser.add_argument(
        "--run-since",
        default=None,
        metavar="YYYY-MM-DD",
        help="Start date of this run; data_attempts.csv failures older than it count as inherited "
        "(default: first ISO date in the report's first 20 lines).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat validation warnings as hard errors (exit code 1).",
    )
    parser.add_argument(
        "--reproduce",
        action="store_true",
        help="Re-run appendix/analysis.py in a temporary copy (command from appendix/README.md) and compare output.txt, "
        "numbers.json and charts.json. Executes the report's own code: use on reports you trust.",
    )
    parser.add_argument("--reproduce-cmd", default=None, help="Override the command used by --reproduce.")
    parser.add_argument(
        "--diff",
        type=Path,
        default=None,
        metavar="OTHER_RUN",
        help="Compare this report folder with another run (folder or its report.md): data files, numbers.json, verdict.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one JSON object {version, passed, errors, warnings} (items: severity, code, file, line, message).",
    )
    args = parser.parse_args(argv)

    if not args.report_path.is_file():
        print(f"Error: File not found: {args.report_path}", file=sys.stderr)
        return 1

    if args.gate_hash:
        print(gate_hash(args.report_path.parent, args.gate_hash))
        return 0

    if args.gate_header:
        from datetime import datetime, timezone

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"MODE: {args.mode}")
        print(f"REVIEWED-SHA256: {gate_hash(args.report_path.parent, args.gate_header)}")
        print(f"REVIEWED-UTC: {now_utc}")
        return 0

    if args.diff is not None:
        other = args.diff.parent if args.diff.is_file() else args.diff
        if not (other / "report.md").is_file():
            print(f"Error: {args.diff} is not a Heurisma run folder (no report.md).", file=sys.stderr)
            return 1
        print(f"Comparing {args.report_path.parent} with {other}")
        print("\n".join(diff_runs(args.report_path.parent, other)))
        return 0

    content = args.report_path.read_text(encoding="utf-8")
    errors, warnings = validate_report_full(
        content, level=args.level, report_dir=args.report_path.parent, charts_path=args.charts, run_since=args.run_since
    )
    if args.reproduce or args.reproduce_cmd:
        errors.extend(reproduce(args.report_path.parent, args.reproduce_cmd))
    if args.html is not None:
        html_errors, html_warnings = validate_html_full(args.html)
        errors.extend(html_errors)
        warnings.extend(html_warnings)
        warnings.extend(check_html_freshness(args.html, args.report_path, args.charts))

    if args.json:
        failed = bool(errors) or (args.strict and bool(warnings))
        print(
            json.dumps(
                {
                    "version": __version__,
                    "passed": not failed,
                    "strict": bool(args.strict),
                    "errors": _json_items(errors, "error"),
                    "warnings": _json_items(warnings, "warning"),
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return 1 if failed else 0

    if warnings:
        print(f"Heurisma report warnings ({len(warnings)}):", file=sys.stderr)
        for idx, warn in enumerate(warnings, start=1):
            print(f"  [WARN {idx}] {warn}", file=sys.stderr)

    if errors or (args.strict and warnings):
        total = len(errors) + (len(warnings) if args.strict else 0)
        print(f"Heurisma report validation FAILED ({total} violation(s)):", file=sys.stderr)
        for idx, err in enumerate(errors, start=1):
            print(f"  {idx}. {err}", file=sys.stderr)
        return 1

    print(f"Heurisma report validation PASSED: {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
