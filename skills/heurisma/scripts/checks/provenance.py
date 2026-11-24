"""Provenance checks: source tiers, selection, the source catalogue, local data and inbox/."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from contracts import (
    DOCUMENT_KINDS,
    VALID_SELECTIONS,
    VALID_TIERS,
    WEAK_KINDS,
    WEB_SUMMARY_LABELS,
)
from providers import base  # noqa: E402  (the connector's URL <-> key mapping)
from checks.common import (
    MAX_SNAPSHOT_AGE_DAYS,
    SHA_HEX_RE,
    _WEAK_TITLE_RE,
    _declared_sha,
    _extract_citation_ids,
    _file_sha256,
    _load_sources_rows,
    _local_source_path,
    _parse_utc,
)


def _is_weak_source(row: dict[str, str] | None) -> bool:
    """A source that cannot carry a [Strong] claim on its own, decided from sources.csv (never from prose)."""
    if not row:
        return False
    if re.search(r"\bTier\s*3\b", row.get("tier") or "", re.IGNORECASE):
        return True
    if (row.get("kind") or "").strip().lower() in WEAK_KINDS:
        return True
    return bool(_WEAK_TITLE_RE.search(row.get("source_title") or ""))


def _local_table_worst_tier(report_dir: Path | None, row: dict[str, str] | None) -> str | None:
    """Weakest tier a local CSV inherits through its ``primary_source_id`` column (see ``local_data.worst_tier``).

    ``None`` when the source is not a local CSV, has no ``primary_source_id`` column, or the run has no
    ``appendix/data/sources_metadata.csv``: then there is nothing to inherit from and the declared tier stands."""
    if report_dir is None or not row:
        return None
    url = (row.get("url") or "").strip()
    if not url or not (url.startswith("file://") or "://" not in url):
        return None
    path = _local_source_path(url, report_dir)
    meta = report_dir / "appendix" / "data" / "sources_metadata.csv"
    if path.suffix.lower() != ".csv" or not path.is_file() or not meta.is_file():
        return None
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if "primary_source_id" not in (reader.fieldnames or []):
                return None
            table_rows = list(reader)
        import local_data

        return str(local_data.worst_tier(table_rows, "primary_source_id", meta))
    except (OSError, csv.Error, UnicodeDecodeError):
        return None


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


PRESS_DOMAINS = (
    "nytimes.com", "washingtonpost.com", "bbc.com", "bbc.co.uk", "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "theguardian.com", "economist.com", "forbes.com", "businessinsider.com", "cnn.com", "techcrunch.com", "elpais.com",
    "lanacion.com.ar", "clarin.com", "infobae.com", "ambito.com", "cronista.com", "pagina12.com.ar", "medium.com",
    "substack.com", "blogspot.com", "wordpress.com", "tumblr.com", "twitter.com", "x.com", "facebook.com",
    "linkedin.com", "reddit.com", "youtube.com",
)


_AS_OF_PART_RE = re.compile(r"^\s*(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?(?!\d)")


def _data_as_of_after(value: str, as_of: str) -> bool:
    """True when a ``data_as_of`` value (YYYY, YYYY-MM or YYYY-MM-DD) is later than the report As-Of Date.

    The comparison keeps the value's own granularity: ``2026-11`` is not after ``2026-11-20``. Text that is not a
    date is never reported."""
    v, a = _AS_OF_PART_RE.match(value or ""), _AS_OF_PART_RE.match(as_of or "")
    if not v or not a:
        return False
    parts = [x for x in v.groups() if x is not None]
    return tuple(int(x) for x in parts) > tuple(int(x) for x in a.groups()[: len(parts)] if x is not None)


def _catalogue_column(header: list[str], *names: str, prefix: str = "") -> str | None:
    lowered = {h.strip().lower(): h for h in header}
    for name in names:
        if name in lowered:
            return lowered[name]
    return next((orig for low, orig in lowered.items() if prefix and low.startswith(prefix)), None)


def check_source_metadata(report_dir: Path | None, as_of: str, level: int) -> tuple[list[str], list[str]]:
    """The tier catalogue (appendix/data/sources_metadata.csv) and every ``data_as_of`` must be well-formed.

    ``tier``/``tier_classification``, ``source_id``/``claim_id``/``id`` and ``data_as_of`` columns are optional; a
    catalogue without them is not an error. A future ``data_as_of`` is a warning (error at Level 3); the other
    findings are errors, because a malformed key silently turns a Tier 1 source into Tier 3 or hides it."""
    errors: list[str] = []
    warnings: list[str] = []
    if report_dir is None:
        return errors, warnings
    sink = errors if level == 3 else warnings
    sources_rows, _ = _load_sources_rows(report_dir)
    for row in sources_rows:
        value = (row.get("data_as_of") or "").strip()
        if _data_as_of_after(value, as_of):
            sink.append(
                f"Source '{(row.get('claim_id') or '?').strip()}' has data_as_of {value} later than the As-Of Date {as_of}; "
                f"data cannot postdate the report (for a forecast horizon, record the publication or vintage date and "
                f"say the horizon in the title)."
            )
    data_dir = report_dir / "appendix" / "data"
    meta = data_dir / "sources_metadata.csv"
    if not meta.is_file():
        return errors, warnings
    try:
        with meta.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            header = list(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, csv.Error, UnicodeDecodeError):
        return errors, warnings
    id_col = _catalogue_column(header, "source_id", "claim_id", "id")
    tier_col = _catalogue_column(header, "tier", prefix="tier")
    date_col = _catalogue_column(header, "data_as_of")
    known: set[str] = set()
    canonical = {re.sub(r"\s+", " ", v).lower() for v in VALID_TIERS}
    for n, row in enumerate(rows, start=2):  # line 1 is the header
        sid = (row.get(id_col) or "").strip() if id_col else ""
        if id_col:
            if not sid:
                errors.append(f"appendix/data/sources_metadata.csv line {n} has an empty {id_col}; every row needs its key.")
            elif re.search(r"\s", sid):
                errors.append(
                    f"appendix/data/sources_metadata.csv line {n}: {id_col} '{sid}' contains a space, so no "
                    f"primary_source_id can match it and its tier is lost; write it without spaces."
                )
            else:
                known.add(sid)
        if tier_col:
            tier_value = (row.get(tier_col) or "").strip()
            if re.sub(r"\s+", " ", tier_value).lower() not in canonical:
                errors.append(
                    f"appendix/data/sources_metadata.csv line {n} ({sid or '?'}) has tier '{tier_value}'; write exactly "
                    f"{', '.join(VALID_TIERS)}."
                )
        if date_col and _data_as_of_after((row.get(date_col) or "").strip(), as_of):
            sink.append(
                f"appendix/data/sources_metadata.csv line {n} ({sid or '?'}) has data_as_of "
                f"{(row.get(date_col) or '').strip()} later than the As-Of Date {as_of}; record the publication or vintage "
                f"date, not the forecast horizon."
            )
    if id_col:
        for table in sorted(data_dir.glob("*.csv")):
            if table.name == "sources_metadata.csv":
                continue
            try:
                with table.open(encoding="utf-8-sig", newline="") as fh:
                    treader = csv.DictReader(fh)
                    if "primary_source_id" not in (treader.fieldnames or []):
                        continue
                    cited = {
                        tok.strip()
                        for trow in treader
                        for tok in re.split(r"[;,]", trow.get("primary_source_id") or "")
                        if tok.strip()
                    }
            except (OSError, csv.Error, UnicodeDecodeError):
                continue
            missing = sorted(cited - known)
            if missing:
                warnings.append(
                    f"Table appendix/data/{table.name} cites primary_source_id value(s) "
                    f"{', '.join(repr(m) for m in missing[:6])} that appendix/data/sources_metadata.csv does not define; "
                    f"they count as Tier 3."
                )
    return errors, warnings


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


_OK_OUTCOMES = {"used", "ok", "success", "succeeded", "retrieved", "http 200"}


def _download_proof(
    report_dir: Path | None, include_attempts: bool = True
) -> tuple[set[str], set[str], set[str]]:
    """Return (urls, filenames, sha12s) with logged acquisition proof in download_log.csv or successful data_attempts.csv.

    ``include_attempts=False`` keeps only download_log.csv (a document that was actually saved to disk)."""
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
    if include_attempts and att_csv.is_file():
        ok_out = _OK_OUTCOMES
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


def _attempt_proof(report_dir: Path | None, run_start: Any = None) -> list[dict[str, str]]:
    """``used`` rows of data_attempts.csv stamped on or after the run start.

    A row without a parseable ``attempted_utc`` (or a file without that column) never counts: without a time it could
    belong to an earlier run."""
    if report_dir is None:
        return []
    att = report_dir / "appendix" / "data_attempts.csv"
    rows: list[dict[str, str]] = []
    try:
        with att.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                out = (row.get("outcome") or "").strip().lower()
                if out not in _OK_OUTCOMES and not out.startswith("http 2"):
                    continue
                ts = _parse_utc((row.get("attempted_utc") or "").strip())
                if ts is None or (run_start is not None and ts < run_start):
                    continue
                rows.append(row)
    except (OSError, csv.Error):
        return []
    return rows


def _strip_url(text: str) -> str:
    return re.sub(r"https?://(?:www\.)?", "", text.lower()).rstrip("/")


def _literature_proven(cid: str, url: str, attempts: list[dict[str, str]]) -> bool:
    """A kept attempt names the source's claim_id (any of its text columns) or its URL (query or fallback)."""
    token = re.compile(rf"(?<![A-Za-z0-9]){re.escape(cid)}(?![A-Za-z0-9])")
    needle = _strip_url(url) if url else ""
    for row in attempts:
        if any(token.search(row.get(k) or "") for k in ("target_series", "query_or_endpoint", "fallback_used")):
            return True
        if needle and any(needle in _strip_url(row.get(k) or "") for k in ("query_or_endpoint", "fallback_used")):
            return True
    return False


def _connector_fulltext_keys(report_dir: Path | None, saved_shas: set[str]) -> set[str]:
    """Keys (DOI, ``arxiv:`` …) of works whose full text the paper connector saved: ``papers.csv`` records its SHA-256 and that
    hash is in ``download_log.csv``. ``sources.csv`` names such a work by its DOI link, not by the URL the PDF came from."""
    papers_csv = report_dir / "appendix" / "papers.csv" if report_dir is not None else None
    if papers_csv is None or not papers_csv.is_file():
        return set()
    try:
        with papers_csv.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error, UnicodeDecodeError):
        return set()
    return {
        r.get("doi", "")
        for r in rows
        if (sha := (r.get("fulltext_sha256") or "").strip().lower()[:12]) and len(sha) == 12 and sha in saved_shas and r.get("doi")
    }


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
    saved_urls, saved_names, saved_shas = _download_proof(report_dir, include_attempts=False)
    connector_saved = _connector_fulltext_keys(report_dir, saved_shas)
    attempts = _attempt_proof(report_dir, run_start)
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
            if is_local and re.search(r"\bTier\s*[12]\b", tier, re.IGNORECASE):
                errors.append(
                    f"Source '{cid}' is a local user-curated file ('{url}') and cannot be {tier} without a verified "
                    f"external origin URL (it stays Tier 3; cite the online primary source separately)."
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
            elif kind == "literature" and report_dir is not None:
                if not _literature_proven(cid, url, attempts):
                    (errors if level == 3 else warnings).append(
                        f"Source '{cid}' is marked agent-fetched (kind=literature) but appendix/data_attempts.csv has no "
                        f"`used` attempt stamped at or after run start that names {cid} or its URL; log the retrieval "
                        f"with `local_data.py attempt`."
                    )
                title = row.get("source_title") or ""
                honest = _WEAK_TITLE_RE.search(title) or any(lbl in title.lower() for lbl in WEB_SUMMARY_LABELS)
                fname = Path(unquote(url)).name if url else ""
                saved = (
                    (url and any(url in u or u in url for u in saved_urls))
                    or (fname and fname in saved_names)
                    or (sha and sha[:12] in saved_shas)
                    or (base.key_from_url(url) in connector_saved)
                )
                if re.search(r"\bTier\s*1\b", tier, re.IGNORECASE) and not saved and not honest:
                    warnings.append(
                        f"Source '{cid}' is agent-fetched literature declared Tier 1 with no downloaded primary document "
                        f"in appendix/download_log.csv; if only a web search summary was read, add '(web summary)' to the "
                        f"title and lower the tier."
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


_INTAKE_FILE_RE = re.compile(r"^- (?:accepted|rejected): (.+?)(?:\s+->\s|\s+\u2014\s|$)", re.MULTILINE)


def _intake_listed_paths(report_dir: Path) -> list[str]:
    """Paths (relative to the folder `local_data.py intake` was run on) that appendix/intake.md accepted or rejected."""
    try:
        text = (report_dir / "appendix" / "intake.md").read_text(encoding="utf-8")
    except OSError:
        return []
    return [m.group(1).strip().replace("\\", "/") for m in _INTAKE_FILE_RE.finditer(text)]


def check_inbox(report_dir: Path, sources_rows: list[dict[str, str]]) -> list[str]:
    """Warn about inbox/ files that neither sources.csv (by hash) nor appendix/intake.md (accepted or rejected) mention.

    A file the intake saw and rejected (a screenshot, an image next to a document) is accounted for. Intake paths are
    relative to the folder it ran on, so one matches when the inbox path ends with it on a ``/`` boundary. Hidden
    files (``.DS_Store``, ``.gitkeep``) are never reported."""
    inbox = report_dir / "inbox"
    if not inbox.is_dir():
        return []
    declared = [h for h in (_declared_sha(r) for r in sources_rows) if h]
    listed = _intake_listed_paths(report_dir)
    out = []
    for fp in sorted(inbox.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(inbox).as_posix()
        if any(part.startswith(".") for part in rel.split("/")):
            continue
        if any(_file_sha256(fp).startswith(h) for h in declared):
            continue
        if any(rel == path or rel.endswith("/" + path) for path in listed):
            continue
        out.append(
            f"inbox/{rel} is not registered in appendix/sources.csv; run `local_data.py intake` or remove it."
        )
    return out
