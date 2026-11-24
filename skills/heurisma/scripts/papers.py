#!/usr/bin/env python3
"""Paper-database connector: search OpenAlex, Europe PMC and arXiv, look a DOI up in OpenAlex and Crossref, and cite a
work into ``appendix/sources.csv`` with the facts the databases report.

    python3 -B <skill-dir>/scripts/papers.py search --provider openalex --query "hybrid work attrition"
    python3 -B <skill-dir>/scripts/papers.py lookup 10.1038/s41586-024-07500-2
    python3 -B <skill-dir>/scripts/papers.py cite 10.1038/s41586-024-07500-2 --tier "Tier 1" --claim C7

Every request is cached (hashed) under ``appendix/data/papers/raw/``; every result is recorded in
``appendix/papers.csv`` and every query in ``appendix/search_log.csv``. The tool never chooses a Tier: the agent does,
from the discipline's evidence hierarchy. It only enforces objective ceilings: a retracted work is refused, a preprint
or a report (not peer reviewed as published) is at most Tier 2, and a work without an abstract or saved full text
cannot be cited as a finding.

Environment: ``HEURISMA_OPENALEX_KEY`` (free key), ``HEURISMA_MAILTO`` (a contact address you choose),
``HEURISMA_OFFLINE=1`` (no request leaves the machine). Credentials are redacted from everything logged. The query text
does leave the machine: it is sent to the provider you choose.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import fetch_lib  # noqa: E402
import local_data  # noqa: E402
from contracts import (  # noqa: E402
    NON_PEER_REVIEWED,
    PAPER_COLS,
    SEARCH_LOG_COLS,
    SOURCE_COLS,
    VALID_TIERS,
    __version__,
)
from providers import arxiv, base, crossref, europepmc, openalex, unpaywall  # noqa: E402
from providers.base import Context, NotFound, ProviderUnavailable, Record  # noqa: E402

PROVIDERS = {"openalex": openalex, "europepmc": europepmc, "arxiv": arxiv, "crossref": crossref}
IMPORTABLE = tuple(PROVIDERS)
MAX_IMPORT_BYTES = 50 * 1024 * 1024
_DOC_START = {"pdf": (b"%PDF",), "xml": (b"<?xml", b"<article", b"<!DOCTYPE article")}  # Europe PMC sends a JATS DOCTYPE first
SEARCHABLE = ("openalex", "europepmc", "arxiv")


class CiteError(Exception):
    """The work cannot be cited as asked; the message says why and what to do instead."""


class FilterError(ValueError):
    """A ``--filter`` the chosen provider cannot apply (it would otherwise be logged as if it had been)."""


# which filters each provider honours: None = any ``key:value`` of OpenAlex's own filter syntax
SUPPORTED_FILTERS: dict[str, frozenset[str] | None] = {"openalex": None, "europepmc": frozenset({"open_access"}), "arxiv": frozenset()}


def parse_filters(items: list[str], provider: str) -> dict[str, Any]:
    """``key=value`` items of ``--filter`` as a dict (``true``/``false`` become booleans); refuse one the provider ignores."""
    allowed = SUPPORTED_FILTERS.get(provider)
    filters: dict[str, Any] = {}
    for item in items:
        key, sep, value = item.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key:
            raise FilterError(f"filter '{item}' must look like key=value")
        if allowed is not None and key not in allowed:
            raise FilterError(f"{provider} does not support the filter '{key}' " + (f"(supported: {', '.join(sorted(allowed))})" if allowed else "(it takes no filters)"))
        filters[key] = True if value.lower() == "true" else False if value.lower() == "false" else value
    return filters


# ------------------------------------------------------------------------------------------------ registry files
_read = local_data._read_rows  # one CSV reader for the whole skill (BOM-tolerant)


def _write_atomic(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    """Write a CSV through a uniquely named temporary file and ``os.replace`` so a failure never leaves a half-written registry."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(columns), extrasaction="ignore", restval="", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))  # write_text(newline=) needs Python 3.10
        os.chmod(tmp_name, 0o644)  # mkstemp creates 0600
        try:
            os.replace(tmp_name, path)
        except PermissionError as exc:
            raise PermissionError(f"cannot replace {path.name}: close it if it is open in another program ({exc})") from exc
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


# ------------------------------------------------------------------------------------------------ one command at a time
_THREAD_LOCK = threading.RLock()
_HELD: dict[str, int] = {}
LOCK_NAME = ".papers.lock"


@contextlib.contextmanager
def _locked(appendix: Path, timeout: float = 30.0, stale_after: float = 600.0) -> Iterator[None]:
    """Serialise the read-modify-write of the registry files between threads and between processes (a lock file, created
    exclusively). Re-entrant. A lock file older than ``stale_after`` seconds was left by a crashed command and is taken over."""
    appendix.mkdir(parents=True, exist_ok=True)
    lock = appendix / LOCK_NAME
    key = str(appendix.resolve())
    with _THREAD_LOCK:
        depth = _HELD.get(key, 0)
        if depth == 0:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, str(os.getpid()).encode("ascii"))
                    os.close(fd)
                    break
                except FileExistsError:
                    try:
                        if time.time() - lock.stat().st_mtime > stale_after:
                            lock.unlink()
                            continue
                    except OSError:
                        continue  # it vanished between the two calls: try again
                    if time.monotonic() >= deadline:
                        raise ProviderUnavailable(
                            f"another papers.py command is using {appendix} ({LOCK_NAME} exists); wait for it, "
                            f"or delete {LOCK_NAME} if no command is running"
                        ) from None
                    time.sleep(0.05)
        _HELD[key] = depth + 1
        try:
            yield
        finally:
            _HELD[key] -= 1
            if _HELD[key] == 0:
                del _HELD[key]
                with contextlib.suppress(OSError):
                    lock.unlink()


def read_papers(appendix: Path) -> list[Record]:
    return [{**base.empty_record(), **row} for row in _read(appendix / "papers.csv")]


def next_query_id(appendix: Path) -> str:
    numbers = [int(m.group(1)) for r in _read(appendix / "search_log.csv") if (m := re.match(r"^Q(\d+)$", r.get("query_id", "")))]
    return f"Q{max(numbers, default=0) + 1}"


# ------------------------------------------------------------------------------------------------ merging
def _tri(values: list[str]) -> str:
    """true beats false beats unknown: one provider reporting a retraction is enough."""
    return "true" if "true" in values else "false" if "false" in values else ""


def merge(records: list[Record]) -> Record:
    """One record from several providers' views of the same work, keeping the cautious reading of every disagreement."""
    out = base.empty_record()
    for col in out:
        out[col] = next((r.get(col, "") for r in records if r.get(col, "")), "")
    out["work_type"] = base.most_conservative_type([r.get("work_type", "") for r in records])
    out["is_retracted"] = _tri([r.get("is_retracted", "") for r in records])
    out["is_oa"] = _tri([r.get("is_oa", "") for r in records])
    out["providers"] = ";".join(sorted({p for r in records for p in r.get("providers", "").split(";") if p}))
    # a work retrieved by the connector even once is vouched for by it; only a record that was never retrieved stays "import"
    out["via"] = "api" if any(r.get("via", "api") == "api" for r in records) else "import"
    out["retrieved_utc"] = max((r.get("retrieved_utc", "") for r in records), default="")
    return out


def upsert(appendix: Path, records: list[Record], query_id: str) -> None:
    """Add records to papers.csv, merging by DOI (or ``arxiv:`` key) and keeping the first ``query_id`` that found a work."""
    with _locked(appendix):
        rows = read_papers(appendix)
        index = {r["doi"]: i for i, r in enumerate(rows) if r["doi"]}
        for rec in records:
            key = rec.get("doi", "")
            if not key:
                continue
            new = {**rec, "query_id": query_id}
            if key in index:
                merged = merge([rows[index[key]], new])
                merged["query_id"] = rows[index[key]]["query_id"] or query_id
                rows[index[key]] = merged
            else:
                index[key] = len(rows)
                rows.append(merge([new]))
                rows[-1]["query_id"] = query_id
        _write_atomic(appendix / "papers.csv", PAPER_COLS, rows)


# ------------------------------------------------------------------------------------------------ commands
def search(ctx: Context, provider: str, query: str, *, limit: int = 25, filters: dict[str, Any] | None = None) -> tuple[str, list[Record]]:
    """Run one search, record every result and log the query. Raises ``ProviderUnavailable`` (and writes nothing) on failure."""
    if provider not in SEARCHABLE:
        raise ProviderUnavailable(f"'{provider}' cannot search; use one of {', '.join(SEARCHABLE)} (crossref only verifies a DOI)")
    records = PROVIDERS[provider].search(ctx, query, limit=limit, filters=filters)
    with _locked(ctx.appendix):  # the next free id, the works and the log row are one step: another command must not slip in between
        qid = next_query_id(ctx.appendix)
        upsert(ctx.appendix, records, qid)
        log = _read(ctx.appendix / "search_log.csv")
        log.append({
            "query_id": qid, "provider": provider, "query": base.redact(query, ctx.env), "filters": json.dumps(filters or {}, sort_keys=True),
            "n_hits": str(len(records)), "retrieved_utc": local_data.utc_now(), "raw_file": ctx.last_raw,
        })
        _write_atomic(ctx.appendix / "search_log.csv", SEARCH_LOG_COLS, log)
    return qid, records


def lookup(ctx: Context, doi: str, providers: tuple[str, ...] = ("openalex", "crossref")) -> Record | None:
    """Fetch one work by DOI from each provider, merge the answers and record the result; None if nobody has it."""
    key = base.normalize_doi(doi)
    if not key:
        raise ProviderUnavailable(f"'{doi}' is not a DOI")
    found: list[Record] = []
    errors: list[ProviderUnavailable] = []
    for name in providers:
        try:
            rec = PROVIDERS[name].lookup(ctx, key)
        except NotFound:
            continue
        except ProviderUnavailable as exc:
            errors.append(exc)
            continue
        if rec:
            found.append(rec)
    if not found:
        if errors:
            raise errors[-1]
        return None
    merged = merge(found)
    upsert(ctx.appendix, [merged], "lookup")
    return merged


def _find(appendix: Path, text: str) -> Record | None:
    key = base.record_key(text)
    return next((r for r in read_papers(appendix) if r["doi"] == key), None) if key else None


def source_url(rec: Record) -> str:
    """The link ``sources.csv`` carries for a recorded work (a real URL even for a work with no DOI)."""
    return base.url_for_key(rec["doi"])


def _next_claim_id(rows: list[dict[str, str]]) -> str:
    used = {int(m.group(1)) for r in rows if (m := re.match(r"^C(\d+)$", r.get("claim_id", "")))}
    return f"C{max(used, default=0) + 1}"


def cite(ctx: Context, doi: str, *, tier: str, claim_id: str | None = None, fulltext: bool = False) -> dict[str, str]:
    """Write the ``sources.csv`` row for a recorded work (``literature``, ``agent-fetched``) and log its retrieval.

    The Tier is the agent's call and must be written exactly (``Tier 1``..``Tier 3``). Refused: a retracted work; a preprint or
    report above Tier 2; a work with neither an abstract nor saved full text."""
    if tier not in VALID_TIERS:
        raise CiteError(f"tier must be exactly one of {', '.join(VALID_TIERS)}, not '{tier}'")
    rec = _find(ctx.appendix, doi)
    if rec is None:
        raise CiteError(f"'{doi}' is not in appendix/papers.csv: find it with `papers.py search` or `lookup` first (a DOI typed from memory is not evidence)")
    if rec["is_retracted"] == "true":
        raise CiteError(f"{rec['doi']} is retracted; do not cite it as evidence (cite the retraction notice if the retraction itself matters)")
    if rec["work_type"] in NON_PEER_REVIEWED and tier == "Tier 1":
        raise CiteError(f"{rec['doi']} is a {rec['work_type']} (not peer reviewed as published): it cannot be Tier 1; use Tier 2 or lower, or cite the published version")
    if tier == "Tier 1" and not rec["work_type"]:
        raise CiteError(f"{rec['doi']} has no known work type (an arXiv record that names a published DOI): run `papers.py lookup {rec['doi']}` to learn whether it is peer reviewed before calling it Tier 1")
    has_text = bool(rec["fulltext_file"])
    if not rec["abstract_sha256"] and not has_text and not fulltext:
        raise CiteError(
            f"{rec['doi']} has no abstract in the databases and no saved full text, so it cannot be cited as a finding; "
            f"if it is open access, cite it with --fulltext"
        )
    sources_csv = ctx.appendix / "sources.csv"
    existing = _read(sources_csv)
    url = source_url(rec)
    for row in existing:
        if row.get("url") == url:
            if row.get("tier") != tier or (claim_id and row.get("claim_id") != claim_id):
                raise CiteError(
                    f"{rec['doi']} is already registered as {row.get('claim_id')} ({row.get('tier')}); to change its tier or claim id, "
                    f"edit appendix/sources.csv and explain the change in Section 3"
                )
            if fulltext and not has_text:
                raise CiteError(
                    f"{rec['doi']} is already registered as {row.get('claim_id')} without its full text; delete that row from "
                    f"appendix/sources.csv and cite it again with --fulltext"
                )
            return row
    if fulltext and not has_text:
        saved = fulltext_for(ctx, rec)
        if saved is None:
            if not rec["abstract_sha256"]:
                raise CiteError(f"no open-access full text could be saved for {rec['doi']}, and it has no abstract, so it cannot be cited as a finding")
            raise CiteError(f"no open-access full text could be saved for {rec['doi']}; cite it without --fulltext (it is then marked abstract only)")
        rec = _find(ctx.appendix, doi) or rec
        has_text = True
    with _locked(ctx.appendix):  # choosing the next claim id and writing the row is one step
        existing = _read(sources_csv)
        for row in existing:
            if row.get("url") == url:
                return row  # another command registered it while the full text was downloading
        cid = claim_id or _next_claim_id(existing)
        if any(r.get("claim_id") == cid for r in existing):
            raise CiteError(f"claim id {cid} is already used in appendix/sources.csv by another source")
        labels = [f"({rec['work_type']})"] if rec["work_type"] in NON_PEER_REVIEWED else []
        if not has_text:
            labels.append("(abstract only)")
        row = {
            "claim_id": cid, "source_title": " ".join([rec["title"], *labels]), "url": url, "tier": tier,
            "accessed_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "data_as_of": rec["year"], "kind": "literature",
            "sha256": rec["fulltext_sha256"], "selection": "agent-fetched", "retrieved_utc": rec["retrieved_utc"],
        }
        local_data._append_row(sources_csv, SOURCE_COLS, row)
        local_data.append_attempt(
            ctx.appendix / "data_attempts.csv", f"{cid} {rec['title'][:60]}", rec["providers"].replace(";", "+"),
            f"lookup doi:{rec['doi']}", "used", fallback=f"{'full text' if has_text else 'abstract only'}; query {rec['query_id'] or 'lookup'}",
        )
    return row


# ------------------------------------------------------------------------------------------------ full text
def _slug(key: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "_", key.lower()).strip("_")


def fulltext_filename(key: str, ext: str) -> str:
    """Where the full text of ``key`` lives under ``appendix/data/``: the readable slug plus a hash of the key, so that two
    DOIs that slug alike (``10.1/a-b``, ``10.1/a_b``) never overwrite each other's file."""
    return f"papers/{_slug(key)}-{base.sha256_text(key)[:8]}.{ext}"


def _drop_download_row(appendix: Path, filename: str) -> None:
    """Remove the newest ``download_log.csv`` row for ``filename`` (the rejected download just logged), keeping earlier ones."""
    log = appendix / "download_log.csv"
    rows = _read(log)
    for i in range(len(rows) - 1, -1, -1):
        if rows[i].get("file") == filename:
            del rows[i]
            break
    _write_atomic(log, fetch_lib.DOWNLOAD_COLS, rows)


def fulltext(ctx: Context, rec: Record) -> Path | None:
    """Save the open-access full text of ``rec`` under ``appendix/data/papers/`` (hash in download_log.csv); None if there is none.

    Only a work flagged open access is tried: Europe PMC full text (by PMCID), then the arXiv or publisher link the
    databases gave, and only if both fail Unpaywall (when ``HEURISMA_MAILTO`` is set, so the address is sent only when needed).
    A download that is not a PDF or XML document (a landing page, a cookie wall) is deleted and logged as rejected."""
    if rec.get("is_oa") != "true":
        return None
    candidates: list[tuple[str, str, str]] = []
    if rec.get("pmcid"):
        candidates.append(("europepmc", f"{ctx.base_url('europepmc', europepmc.DEFAULT_URL)}/{rec['pmcid']}/fullTextXML", "xml"))
    if rec.get("oa_url"):
        is_arxiv_oa = "arxiv.org" in rec["oa_url"].lower() or rec["oa_url"].startswith(ctx.base_url("arxiv", arxiv.DEFAULT_URL))
        candidates.append(("arxiv" if is_arxiv_oa else "publisher", rec["oa_url"], "pdf"))
    if not ctx.mailto and base.normalize_doi(rec["doi"]) and not candidates:
        ctx.warn("unpaywall was skipped: set HEURISMA_MAILTO to a contact address you choose to let it look for an open-access copy")

    def attempt(provider: str, url: str, ext: str) -> Path | None:
        filename = fulltext_filename(rec["doi"], ext)
        try:
            path = ctx.download(provider, url, filename, timeout=60)
        except NotFound:
            return None
        except ProviderUnavailable:
            if ctx.offline:
                raise
            return None
        head = path.read_bytes()[:64].lstrip()
        if not any(head.startswith(sig) for sig in _DOC_START[ext]):
            path.unlink()
            _drop_download_row(ctx.appendix, filename)
            local_data.append_attempt(
                ctx.appendix / "data_attempts.csv", f"{rec['doi']} full text", provider, f"GET {base.redact(url, ctx.env)}", "rejected",
                failure_reason="the response is not a PDF or XML document (a landing page or a cookie wall?)",
            )
            return None
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with _locked(ctx.appendix):
            rows = read_papers(ctx.appendix)
            for row in rows:
                if row["doi"] == rec["doi"]:
                    row["fulltext_file"], row["fulltext_sha256"] = f"appendix/data/{filename}", digest
            _write_atomic(ctx.appendix / "papers.csv", PAPER_COLS, rows)
        return path

    for provider, url, ext in candidates:
        saved = attempt(provider, url, ext)
        if saved is not None:
            return saved
    if ctx.mailto and base.normalize_doi(rec["doi"]):
        try:
            loc = unpaywall.oa_location(ctx, rec["doi"])
        except NotFound:
            return None
        except ProviderUnavailable as exc:
            if ctx.offline:
                raise
            ctx.warn(f"unpaywall could not be asked ({base.redact(str(exc), ctx.env)})")
            return None
        if loc and all(loc["pdf_url"] != c[1] for c in candidates):
            return attempt("publisher", loc["pdf_url"], "pdf")
    return None



# ``cite`` takes a ``fulltext: bool`` argument that shadows the function inside it, so it calls it by this second name
fulltext_for = fulltext


# ------------------------------------------------------------------------------------------------ verify / import / replay
def verify(ctx: Context) -> list[str]:
    """Look every DOI or arXiv link cited in ``sources.csv`` up again and report what does not hold: a work no database knows,
    a title that does not match, a retracted work, and any reference that could not be checked because a provider was down.
    Local files and own computations are skipped. Raises when offline."""
    problems: list[str] = []
    for row in _read(ctx.appendix / "sources.csv"):
        if row.get("kind") == "own-computation":
            continue
        key = base.key_from_url(row.get("url", ""))
        if not key or not (base.normalize_doi(key) or key.startswith("arxiv:")):
            continue  # a local file, or a work known only by its database id: there is nothing to look up
        cid = row.get("claim_id", "?")
        try:
            if key.startswith("arxiv:"):
                rec = arxiv.lookup(ctx, key[len("arxiv:"):])
                if rec is not None:
                    upsert(ctx.appendix, [rec], "lookup")
            else:
                rec = lookup(ctx, key)
        except ProviderUnavailable as exc:
            if ctx.offline:
                raise
            problems.append(f"{cid} ({key}): could not be checked, so it is not verified ({base.redact(str(exc), ctx.env)})")
            continue
        if rec is None:
            problems.append(f"{cid} ({key}): not found in {'arXiv' if key.startswith('arxiv:') else 'OpenAlex or Crossref'}, so it cannot be verified; a reference that does not resolve is not evidence")
            continue
        if rec["is_retracted"] == "true":
            problems.append(f"{cid} ({key}): the work is retracted")
        overlap = base.title_overlap(row.get("source_title", ""), rec["title"])
        if overlap < 0.6:
            problems.append(f"{cid} ({key}): the title in sources.csv does not match the databases' title ('{rec['title'][:70]}'; word overlap {overlap:.2f})")
    return problems


def import_json(ctx: Context, provider: str, path: Path) -> list[Record]:
    """Record a provider response that was fetched by some other tool (a web tool, a browser): validate its shape, keep a hashed copy.

    The records are marked ``via=import``: the connector did not retrieve them, so the validator treats them as attested by the agent."""
    if provider not in IMPORTABLE:
        raise ProviderUnavailable(f"cannot import '{provider}'; use one of {', '.join(IMPORTABLE)}")
    try:
        if path.stat().st_size > MAX_IMPORT_BYTES:
            raise ProviderUnavailable(f"{path.name} is larger than {MAX_IMPORT_BYTES} bytes")
        payload = path.read_bytes()
    except OSError as exc:
        raise ProviderUnavailable(f"cannot read {path}: {exc}") from exc
    records = [r for r in PROVIDERS[provider].parse(payload) if r["doi"]]
    if not records:
        raise ProviderUnavailable(f"{path.name} holds no work with a DOI or identifier, so there is nothing to import")
    for rec in records:
        rec["via"] = "import"
    ext = "xml" if provider == "arxiv" else "json"
    with _locked(ctx.appendix):
        raw = ctx.store(f"import_{provider}", payload, ext, f"import:{provider}")
        qid = next_query_id(ctx.appendix)
        upsert(ctx.appendix, records, qid)
        log = _read(ctx.appendix / "search_log.csv")
        log.append({
            "query_id": qid, "provider": f"import:{provider}", "query": "(imported file)", "filters": "{}", "n_hits": str(len(records)),
            "retrieved_utc": local_data.utc_now(), "raw_file": raw,
        })
        _write_atomic(ctx.appendix / "search_log.csv", SEARCH_LOG_COLS, log)
    return records


def _provider_of(cache_name: str) -> tuple[str, bool] | None:
    stem = cache_name.split("-", 1)[0]
    imported = stem.startswith("import_")
    name = stem[len("import_"):] if imported else stem
    return (name, imported) if name in PROVIDERS else None


def _utc(text: str) -> datetime | None:
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# a registry row is stamped when its response is parsed, a moment after fetch_lib logged the download
RETRIEVAL_SLACK_SECONDS = 120
_DESCRIPTIVE = ("title", "first_author", "n_authors", "year", "venue", "abstract_sha256")


def replay(ctx: Context) -> list[str]:
    """Rebuild what ``papers.csv`` should contain from the cached raw responses alone (no network) and report every row it
    cannot account for: a hand-edited field, a hand-added row, a cache file that went missing, or a response that is not the
    one the connector logged (its SHA-256 must match ``download_log.csv``, so a file dropped into the cache explains nothing)."""
    problems: list[str] = []
    raw_dir = ctx.appendix / "data" / "papers" / "raw"
    ledger = {r.get("file", ""): r for r in _read(ctx.appendix / "download_log.csv")}  # the newest row of a file wins
    for entry in _read(ctx.appendix / "search_log.csv"):
        raw = entry.get("raw_file", "")
        if raw and not (ctx.appendix.parent / raw).is_file():
            problems.append(f"{entry.get('query_id', '?')}: the cache file {raw} listed in search_log.csv is missing")
    expected: dict[str, list[Record]] = {}
    for cache in sorted(raw_dir.glob("*")) if raw_dir.is_dir() else []:
        found = _provider_of(cache.name)
        if not found:
            continue
        name, imported = found
        try:
            payload = cache.read_bytes()
        except OSError:
            continue
        logged = ledger.get(f"papers/raw/{cache.name}")
        if not logged or logged.get("sha256", "").lower() != hashlib.sha256(payload).hexdigest():
            problems.append(
                f"{cache.name}: no matching SHA-256 in download_log.csv (a response the connector did not fetch, or one edited since); "
                f"it explains no row"
            )
            continue
        try:
            records = PROVIDERS[name].parse(payload)
        except ProviderUnavailable:
            continue  # an unreadable or malformed body supports no row; a row that needed it is reported below
        for rec in records:
            if imported:
                rec["via"] = "import"
            rec["retrieved_utc"] = logged.get("retrieved_utc", "")
            expected.setdefault(rec["doi"], []).append(rec)
    for row in read_papers(ctx.appendix):
        views = expected.get(row["doi"])
        if not views:
            problems.append(f"{row['doi']}: no cached response supports this row (added by hand, or its cache file is missing)")
            continue
        for col in ("title", "first_author", "n_authors", "year", "venue", "abstract_sha256", "oa_url", "pmcid"):
            if row[col] and row[col] not in {v[col] for v in views}:
                problems.append(f"{row['doi']}: {col} '{row[col][:60]}' differs from every cached response")
        for col in _DESCRIPTIVE:
            given = next((v[col] for v in views if v[col]), "")
            if not row[col] and given:
                problems.append(f"{row['doi']}: {col} is empty but the cached responses give '{given[:60]}'")
        want = merge(views)
        for col in ("work_type", "is_retracted", "is_oa", "via"):
            if row[col] != want[col]:
                problems.append(f"{row['doi']}: {col} is '{row[col]}' but the cached responses give '{want[col]}'")
        if {p for p in row["providers"].split(";") if p} != {p for p in want["providers"].split(";") if p}:
            problems.append(f"{row['doi']}: providers is '{row['providers']}' but the cached responses come from '{want['providers']}'")
        stamped, newest = _utc(row["retrieved_utc"]), _utc(want["retrieved_utc"])
        if stamped is None or newest is None or (stamped - newest).total_seconds() > RETRIEVAL_SLACK_SECONDS:
            problems.append(f"{row['doi']}: retrieved_utc is '{row['retrieved_utc']}' but the newest cached response was logged at '{want['retrieved_utc']}'")
    return problems


# ------------------------------------------------------------------------------------------------ CLI
def _print_records(records: list[Record]) -> None:
    for r in records:
        flags = ",".join(f for f in (r["work_type"], "RETRACTED" if r["is_retracted"] == "true" else "", "" if r["abstract_sha256"] else "no-abstract") if f)
        print(f"{r['doi']} | {r['year']} | {flags} | {r['first_author']} | {r['title'][:80]}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Search paper databases and cite what you find, with every request cached and hashed.")
    parser.add_argument("--version", action="version", version=f"papers.py {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--appendix", type=Path, default=Path("appendix"), help="The report's appendix folder (default: appendix).")

    s = sub.add_parser("search", help="Search one provider and record every result.")
    common(s)
    s.add_argument("--provider", choices=SEARCHABLE, required=True)
    s.add_argument("--query", required=True)
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--filter", action="append", default=[], metavar="KEY=VALUE", help="Provider filter, repeatable (openalex: language=en; europepmc: open_access=true).")
    lk = sub.add_parser("lookup", help="Fetch one work by DOI from OpenAlex and Crossref.")
    common(lk)
    lk.add_argument("doi")
    vf = sub.add_parser("verify", help="Look up every DOI cited in sources.csv again; report the ones that do not hold.")
    common(vf)
    rp = sub.add_parser("replay", help="Rebuild papers.csv from the cached responses (offline) and report what it cannot account for.")
    common(rp)
    im = sub.add_parser("import", help="Record a provider response saved by another tool (marked as attested, not retrieved).")
    common(im)
    im.add_argument("--provider", choices=IMPORTABLE, required=True)
    im.add_argument("--file", type=Path, required=True)
    c = sub.add_parser("cite", help="Write the sources.csv row for a recorded work.")
    common(c)
    c.add_argument("doi")
    c.add_argument("--tier", required=True, help='Exactly "Tier 1", "Tier 2" or "Tier 3": your call from the discipline\'s evidence hierarchy.')
    c.add_argument("--claim", help="Claim id for the row (default: the next free C<n>).")
    c.add_argument("--fulltext", action="store_true", help="Also save the open-access full text.")
    args = parser.parse_args(argv)
    ctx = Context(args.appendix)
    try:
        if args.command == "search":
            filters = parse_filters(args.filter, args.provider)
            qid, records = search(ctx, args.provider, args.query, limit=args.limit, filters=filters)
            print(f"{qid}: {len(records)} result(s) from {args.provider}, recorded in {args.appendix}/papers.csv")
            _print_records(records)
        elif args.command == "lookup":
            rec = lookup(ctx, args.doi)
            if rec is None:
                print(f"{args.doi}: not found in OpenAlex or Crossref (a DOI that does not resolve is not evidence)", file=sys.stderr)
                return 1
            _print_records([rec])
        elif args.command == "verify":
            problems = verify(ctx)
            for line in problems:
                print(line)
            print(f"verify: {len(problems)} problem(s) in appendix/sources.csv" if problems else "verify: every DOI in appendix/sources.csv resolves, matches its title and is not retracted")
            return 1 if problems else 0
        elif args.command == "replay":
            problems = replay(ctx)
            for line in problems:
                print(line)
            print(f"replay: {len(problems)} discrepancy(ies) between papers.csv and the cached responses" if problems else "replay: papers.csv is fully explained by the cached responses")
            return 1 if problems else 0
        elif args.command == "import":
            records = import_json(ctx, args.provider, args.file)
            print(f"imported {len(records)} record(s) from {args.file.name} as {args.provider} (via=import: attested, not retrieved by the connector)")
            _print_records(records)
        else:
            row = cite(ctx, args.doi, tier=args.tier, claim_id=args.claim, fulltext=args.fulltext)
            print(f"{row['claim_id']}: {row['source_title']} -> {args.appendix}/sources.csv ({row['tier']})")
    except (ProviderUnavailable, CiteError, FilterError, OSError) as exc:
        print(f"Error: {base.redact(str(exc), ctx.env)}", file=sys.stderr)
        return 1
    finally:
        for warning in ctx.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
