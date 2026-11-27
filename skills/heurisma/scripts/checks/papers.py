"""Paper-connector checks (opt-in: they run only when ``appendix/papers.csv`` exists).

The connector (``papers.py``) records every work it retrieved, with its type, retraction status and a hash of any saved
full text. These checks hold a report to that registry: a reference whose DOI the connector never retrieved, a preprint
declared Tier 1, a retracted work that is cited, a title that is not the one the databases give, and a registry that
the cached responses do not explain (a hand-written or hand-edited ``papers.csv``). Nothing here touches the network.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from checks.common import _declared_sha, _parse_utc
from contracts import NON_PEER_REVIEWED, WITHHELD_MANIFEST, read_withheld
from providers import base

_CREDENTIAL = re.compile(r"(?i)\b(api_key|apikey|mailto|email)=(?!REDACTED\b|YOUR_)([^\s&\"']{3,})")
_REGISTRY_TEXT = ("csv", "md", "txt", "json")


def _read(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


_SECRET_ENV = ("HEURISMA_OPENALEX_KEY", "HEURISMA_MAILTO")
_MAX_SCANNED_BYTES = 5_000_000  # a larger file is a data table, not a log


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_withheld_manifest(appendix: Path) -> list[str]:
    manifest = appendix / WITHHELD_MANIFEST
    if not manifest.is_file():
        return []
    errors: list[str] = []
    try:
        with manifest.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            header = [c.strip() if c is not None else "" for c in (reader.fieldnames or [])]
            reader.fieldnames = header
            missing = [c for c in ("file", "sha256") if c not in header]
            if missing:
                return [
                    f"appendix/{WITHHELD_MANIFEST}: missing required column(s) {', '.join(missing)} "
                    f"(expected: file,sha256,reason)."
                ]
            for line_no, row in enumerate(reader, start=2):
                name = (row.get("file") or "").strip()
                sha = (row.get("sha256") or "").strip()
                if not name or "/" in name or "\\" in name or name in (".", ".."):
                    errors.append(
                        f"appendix/{WITHHELD_MANIFEST}: line {line_no} must name a bare file under "
                        f"appendix/data/papers/, not '{name}'."
                    )
                elif not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
                    errors.append(
                        f"appendix/{WITHHELD_MANIFEST}: line {line_no} ('{name}') must record a full 64-character "
                        f"hex SHA-256, not '{sha}'."
                    )
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        return [f"appendix/{WITHHELD_MANIFEST}: unreadable manifest ({exc})."]
    return errors


def check_papers(
    report_dir: Path | None,
    sources_rows: list[dict[str, str]],
    cited_ids: set[str],
    level: int,
    run_start: Any = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if report_dir is None:
        return errors, warnings
    appendix = report_dir / "appendix"
    papers_csv = appendix / "papers.csv"
    if not papers_csv.is_file():
        if (appendix / WITHHELD_MANIFEST).is_file():
            return [
                f"appendix/{WITHHELD_MANIFEST}: manifest exists without appendix/papers.csv; "
                f"only full texts saved by the paper connector can be declared withheld."
            ], []
        return errors, warnings
    errors.extend(_validate_withheld_manifest(appendix))
    sink = errors if level == 3 else warnings
    records = {r.get("doi", ""): r for r in _read(papers_csv)}

    for row in sources_rows:
        key = base.key_from_url(row.get("url") or "")
        if not key:
            continue
        cid = (row.get("claim_id") or "?").strip()
        tier = (row.get("tier") or "").strip()
        rec = records.get(key)
        if rec is None:
            # the rule is about literature the agent says it retrieved; a dataset DOI or a user's own file is not a paper to look up
            if (row.get("kind") or "").strip().lower() == "literature" and (row.get("selection") or "").strip().lower() != "user-curated":
                sink.append(
                    f"Source '{cid}' ({key}) is not in appendix/papers.csv: the connector never retrieved it, so the reference was "
                    f"typed from memory; find it with `papers.py search` or `lookup` first."
                )
            continue
        retrieved = _parse_utc(rec.get("retrieved_utc", ""))
        if run_start is not None and retrieved is not None and retrieved < run_start:
            sink.append(
                f"Source '{cid}' ({key}) was retrieved by the connector before this run started ({rec.get('retrieved_utc')}); "
                f"look it up again in this run."
            )
        if rec.get("work_type") in NON_PEER_REVIEWED and re.search(r"\bTier\s*1\b", tier, re.IGNORECASE):
            errors.append(
                f"Source '{cid}' ({key}) is a {rec['work_type']} in appendix/papers.csv (not peer reviewed as published) but is declared "
                f"Tier 1; a {rec['work_type']} is Tier 2 at most (cite the published version if there is one)."
            )
        if rec.get("is_retracted") == "true":
            if cid in cited_ids:
                errors.append(f"Source '{cid}' ({key}) is retracted according to appendix/papers.csv and the report cites it; remove the claim it supports.")
            else:
                warnings.append(f"Source '{cid}' ({key}) is retracted according to appendix/papers.csv; remove it from sources.csv.")
        title, recorded = (row.get("source_title") or ""), rec.get("title", "")
        if recorded and base.title_overlap(title, recorded) < 0.6:
            warnings.append(
                f"Source '{cid}' ({key}): the title in sources.csv does not match the title papers.csv records for the same DOI "
                f"('{recorded[:70]}'); a reference whose title was changed or invented is not the paper the DOI names."
            )
        if rec.get("via") == "import" and re.search(r"\bTier\s*1\b", tier, re.IGNORECASE):
            sink.append(
                f"Source '{cid}' ({key}) is Tier 1 but its record was imported (attested by the agent, not retrieved by the connector); "
                f"retrieve it with `papers.py lookup` so the connector can vouch for it."
            )

    papers_dir = (appendix / "data" / "papers").resolve()
    withheld = read_withheld(appendix)
    logged = {r.get("file", ""): (r.get("sha256") or "").strip().lower() for r in _read(appendix / "download_log.csv")}
    for rel_w, sha_w in withheld.items():
        name = rel_w[len("data/papers/"):]
        on_disk = appendix / rel_w
        if logged.get(f"papers/{name}") != sha_w:
            errors.append(
                f"appendix/{WITHHELD_MANIFEST}: '{name}' is declared withheld with SHA-256 {sha_w[:12]}, but download_log.csv has no "
                f"download of that file with that hash; only a full text the connector saved can be withheld from a copy."
            )
        elif on_disk.is_file() and _file_sha256(on_disk) != sha_w:
            errors.append(f"appendix/{WITHHELD_MANIFEST}: '{name}' is present but its SHA-256 differs from the one declared withheld.")
    for rec in records.values():
        rel = (rec.get("fulltext_file") or "").strip()
        if not rel:
            continue
        doi = rec.get("doi")
        try:
            target = (report_dir / rel).resolve()
            confined = papers_dir in target.parents
        except (OSError, ValueError):
            confined, target = False, report_dir / "?"
        if not confined:
            errors.append(
                f"appendix/papers.csv: the full text '{rel}' of {doi} is not a file under appendix/data/papers/, where `papers.py cite --fulltext` "
                f"saves it; a path elsewhere cannot show what was downloaded."
            )
            continue
        if not target.is_file():
            rel_appendix = rel[len("appendix/"):] if rel.startswith("appendix/") else rel
            if withheld.get(rel_appendix) and withheld[rel_appendix] == (rec.get("fulltext_sha256") or "").strip().lower():
                continue  # withheld from this copy with the hash it was saved with (checked against download_log.csv above)
            errors.append(f"appendix/papers.csv: the full text '{rel}' of {doi} is recorded but the file is missing.")
            continue
        recorded_sha = (rec.get("fulltext_sha256") or "").strip().lower()
        if not recorded_sha:
            errors.append(f"appendix/papers.csv: the full text '{rel}' of {doi} has no recorded SHA-256, so nothing shows it is the file that was downloaded.")
            continue
        try:
            actual = _file_sha256(target)
        except OSError:
            errors.append(f"appendix/papers.csv: the full text '{rel}' of {doi} cannot be read.")
            continue
        if actual != recorded_sha:
            errors.append(
                f"appendix/papers.csv: '{rel}' changed since it was recorded: SHA-256 {actual[:12]} != recorded {recorded_sha[:12]}."
            )

    # M1: a full text that is on disk and in download_log.csv but no longer referenced by papers.csv or sources.csv
    # (e.g. the source was removed from both registries without deleting the file) is orphaned. Compare against the
    # fulltext_file path papers.csv records and the SHA-256 a sources.csv row declares.
    source_hashes = {h for row in sources_rows if (h := _declared_sha(row))}
    paper_fulltext_paths = {
        (rec.get("fulltext_file") or "").strip() for rec in records.values() if (rec.get("fulltext_file") or "").strip()
    }
    paper_hashes = {
        (rec.get("fulltext_sha256") or "").strip().lower()
        for rec in records.values()
        if (rec.get("fulltext_sha256") or "").strip()
    }
    for fp in sorted(papers_dir.iterdir()) if papers_dir.is_dir() else []:
        if not fp.is_file():
            continue
        name = f"papers/{fp.name}"
        if name not in logged:
            continue  # not a file download_log.csv records: a stray file, not a full text the connector saved
        if f"appendix/data/{name}" in paper_fulltext_paths or f"data/{name}" in withheld:
            continue
        try:
            actual = _file_sha256(fp)
        except OSError:
            continue
        if actual in paper_hashes or any(actual.startswith(h) for h in source_hashes):
            continue
        warnings.append(
            f"appendix/data/{name} is on disk and in appendix/download_log.csv but is referenced by neither "
            f"appendix/papers.csv nor appendix/sources.csv (orphaned full text); remove it, or the source that saved it."
        )

    try:
        import papers as _papers  # the connector itself: replay needs no network

        for message in _papers.replay(_papers.Context(appendix)):
            sink.append(f"appendix/papers.csv: {message}")
    except (ImportError, OSError):  # validator run without the connector next to it, or a cache folder it cannot read
        pass

    env_secrets = [(name, v) for name in _SECRET_ENV if len(v := (os.environ.get(name) or "").strip()) >= 4]
    for path in sorted(appendix.rglob("*")) if appendix.is_dir() else []:
        try:
            if not path.is_file() or path.suffix.lstrip(".") not in _REGISTRY_TEXT or path.stat().st_size > _MAX_SCANNED_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        shown = path.relative_to(report_dir).as_posix()
        m = _CREDENTIAL.search(text)
        if m:
            errors.append(
                f"{shown} contains a credential ({m.group(1)}= followed by a value): a key or contact address must "
                f"never be written to the appendix; remove it and rotate the key."
            )
            continue
        leaked = next((name for name, value in env_secrets if value in text), None)
        if leaked:
            errors.append(f"{shown} contains a credential: the value of {leaked}; it must never be written to the appendix; remove it and rotate the key.")
    return errors, warnings
