#!/usr/bin/env python3
"""Zero-dependency local data inventory, preview, table reader, and provenance registration for Heurisma.

Usage:
  python3 -B local_data.py inventory [dir ...]
  python3 -B local_data.py preview <file> [--n 10] [--sheet NAME]
  python3 -B local_data.py register <file> --sources appendix/sources.csv --tier "Tier 1" --title "..." [--claim L1] [--as-of YYYY-MM-DD] [--lang en|es]
  python3 -B local_data.py import <file> --into appendix/data --sources appendix/sources.csv --tier "Tier 1" --title "..." [--lang en|es]
  python3 -B local_data.py attempt --csv appendix/data_attempts.csv --target "..." --source "..." --query "..." --outcome "..." [--failure-reason "..."] [--fallback "..."]

`import` copies the file into appendix/data/, registers the COPY (project-relative path + SHA-256) and logs the rung
in appendix/data_attempts.csv in one step. `register` stores a project-relative path for files inside the report folder
and a file:/// URI only for files outside it. `attempt` logs any rung with a tool-stamped attempted_utc.
Set HEURISMA_OFFLINE=1 to force the local-data rung (no network).

Without explicit directories, inventory searches $HEURISMA_DATA_DIR, ./datos, ./data, and ./appendix/data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

DEFAULT_ROOTS: tuple[str, ...] = ("datos", "data", "appendix/data")
DATA_EXT: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "csv",
    ".txt": "text",
    ".md": "text",
    ".json": "json",
    ".xlsx": "xlsx",
    ".xlsm": "xlsx",
    ".pdf": "pdf",
    ".xls": "xls-legacy",
    ".ods": "ods",
}
NS: dict[str, str] = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


# ---------------------------------------------------------------- inventory
def sha12(path: Path) -> str:
    """Return the first 12 hex characters of the SHA-256 digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def candidate_roots(extra: list[str] | None = None) -> list[Path]:
    """Return existing directories/files to scan for local data."""
    roots = [Path(p) for p in (extra or [])]
    if not roots:
        roots = [Path(p) for p in DEFAULT_ROOTS]
        env_dir = os.environ.get("HEURISMA_DATA_DIR")
        if env_dir:
            roots.insert(0, Path(env_dir))
    return [r for r in roots if r.exists()]


def inventory(roots: list[str] | None = None, max_depth: int = 4) -> list[dict[str, Any]]:
    """List supported local data files with kind, byte size, modified timestamp, and sha256_12."""
    rows: list[dict[str, Any]] = []
    for root in candidate_roots(roots):
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for p in files:
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            if p != root and len(p.relative_to(root).parts) > max_depth:
                continue
            kind = DATA_EXT.get(p.suffix.lower())
            if not kind:
                continue
            st = p.stat()
            rows.append(
                {
                    "path": str(p),
                    "kind": kind,
                    "bytes": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    "sha256_12": sha12(p),
                }
            )
    return rows


# ---------------------------------------------------------------- readers
def _sniff_csv(text: str) -> tuple[str, bool]:
    sample = text[:20000]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ";" if sample.count(";") > sample.count(",") else ","
    decimal_comma = delim != "," and bool(re.search(r"\d,\d", sample))
    return delim, decimal_comma


def _to_number(v: str, decimal_comma: bool) -> Any:
    s = v.strip()
    if not s:
        return None
    t = s.replace(".", "").replace(",", ".") if decimal_comma else s.replace(",", "")
    try:
        return float(t) if re.search(r"[.eE]", t) else int(t)
    except ValueError:
        return s


def read_csv(path: Path) -> list[dict[str, Any]]:
    """Read a CSV/TSV file with delimiter sniffing, European decimal-comma support, and UTF-8/latin-1 fallback."""
    raw = path.read_bytes()
    text = ""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    delim, dec = _sniff_csv(text)
    rd = csv.DictReader(io.StringIO(text), delimiter=delim)
    return [{k: _to_number(v or "", dec) for k, v in row.items() if k is not None} for row in rd]


def _xlsx_sheets(z: zipfile.ZipFile) -> dict[str, str]:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
    out: dict[str, str] = {}
    sheets_el = wb.find("m:sheets", NS)
    if sheets_el is None:
        return out
    for s in sheets_el:
        rid = s.get(f"{{{NS['r']}}}id")
        raw_t = (target.get(rid) or "").lstrip("/")
        name = s.get("name") or "Sheet1"
        out[name] = raw_t if raw_t.startswith("xl/") else f"xl/{raw_t}"
    return out


def _col_index(ref: str) -> int:
    m = re.match(r"[A-Z]+", ref or "")
    if not m:
        return 0
    n = 0
    for ch in m.group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path: Path, sheet: str | None = None, max_rows: int | None = None) -> tuple[list[str], list[list[Any]]]:
    """Read an XLSX sheet without external dependencies; returns (sheet_names, rows)."""
    with zipfile.ZipFile(path) as z:
        sheets = _xlsx_sheets(z)
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        name = sheet or next(iter(sheets))
        rows: list[list[Any]] = []
        with z.open(sheets[name]) as fh:
            for _, el in ET.iterparse(fh):
                if el.tag != f"{{{NS['m']}}}row":
                    continue
                vals: dict[int, Any] = {}
                for c in el.findall("m:c", NS):
                    v = c.find("m:v", NS)
                    t = c.get("t")
                    if t == "inlineStr":
                        val: Any = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                    elif v is None or v.text is None:
                        continue
                    elif t == "s":
                        val = shared[int(v.text)]
                    elif t in ("str", "e"):
                        val = v.text
                    elif t == "b":
                        val = v.text == "1"
                    else:
                        f = float(v.text)
                        val = int(f) if f.is_integer() else f
                    vals[_col_index(c.get("r") or "A1")] = val
                if vals:
                    rows.append([vals.get(i) for i in range(max(vals) + 1)])
                el.clear()
                if max_rows and len(rows) >= max_rows:
                    break
    return list(sheets), rows


def excel_date(serial: float) -> date:
    """Convert an Excel serial date number (1900 date system) to a Python date."""
    return date.fromordinal(date(1899, 12, 30).toordinal() + int(serial))


def read_json(path: Path) -> Any:
    """Read and parse a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def guess_header_row(rows: list[list[Any]], scan: int = 30) -> int:
    """Return index of the first row with the highest number of non-empty text cells."""
    best, best_i = -1, 0
    for i, r in enumerate(rows[:scan]):
        n = sum(isinstance(v, str) and v.strip() != "" for v in r)
        if n > best:
            best, best_i = n, i
    return best_i


def read_table(path: str | Path, sheet: str | None = None, header_row: int | None = None) -> list[dict[str, Any]]:
    """Read CSV, TSV, XLSX, or JSON into a list of row dicts (auto-detects XLSX headers and drops footer notes)."""
    p = Path(path)
    kind = DATA_EXT.get(p.suffix.lower())
    if kind == "csv":
        return read_csv(p)
    if kind == "xlsx":
        _, rows = read_xlsx(p, sheet)
        if not rows:
            return []
        if header_row is None:
            header_row = guess_header_row(rows)
        head = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(rows[header_row])]
        body = [r for r in rows[header_row + 1 :] if sum(v is not None and v != "" for v in r) >= 2]
        return [dict(zip(head, r)) for r in body]
    if kind == "json":
        js = read_json(p)
        if isinstance(js, dict):
            for key in ("results", "data", "rows", "items"):
                if isinstance(js.get(key), list):
                    return js[key]
            return [js]
        return js
    raise ValueError(f"Unsupported tabular format: {p.suffix} (pdf/xls/ods require conversion or an external reader)")


# ---------------------------------------------------------------- preview
def preview(path: str | Path, n: int = 10, sheet: str | None = None) -> str:
    """Return a concise human-readable preview of a local data file."""
    p = Path(path)
    kind = DATA_EXT.get(p.suffix.lower(), "unknown")
    out = [f"{p}  [{kind}, {p.stat().st_size:,} bytes, sha256 {sha12(p)}]"]
    if kind == "csv":
        rows = read_csv(p)
        if not rows:
            raise ValueError(f"{p}: file is empty or has no data rows")
        delim, dec = _sniff_csv(p.read_bytes()[:20000].decode("utf-8", "replace"))
        out.append(f"rows={len(rows)} delimiter={delim!r} decimal_comma={dec}")
        out.append(f"columns={list(rows[0]) if rows else []}")
        out.extend(str(r) for r in rows[:n])
    elif kind == "xlsx":
        sheets, rows = read_xlsx(p, sheet, max_rows=n)
        out.append(f"sheets={sheets}  (showing: {sheet or sheets[0]})")
        out.extend(" | ".join("" if v is None else str(v) for v in r)[:200] for r in rows)
    elif kind == "json":
        try:
            js = read_json(p)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{p}: invalid JSON ({exc})") from exc
        if isinstance(js, list):
            out.append(f"list of {len(js)} items")
            out.extend(json.dumps(x, ensure_ascii=False)[:200] for x in js[:n])
        elif isinstance(js, dict):
            out.append(f"object with keys {list(js)[:20]}")
            for k, v in list(js.items())[:n]:
                desc = f"list[{len(v)}]" if isinstance(v, list) else json.dumps(v, ensure_ascii=False)[:120]
                out.append(f"  {k}: {desc}")
        else:
            out.append(repr(js)[:200])
    elif kind == "text":
        out.extend(p.read_text(encoding="utf-8", errors="replace").splitlines()[:n])
    else:
        out.append("No stdlib reader available: file listed only (convert to CSV or use an external tool).")
    return "\n".join(out)


# ---------------------------------------------------------------- provenance
ATTEMPT_COLS: tuple[str, ...] = (
    "target_series",
    "source_tried",
    "query_or_endpoint",
    "outcome",
    "failure_reason",
    "fallback_used",
    "attempted_utc",
)
SOURCE_COLS: tuple[str, ...] = ("claim_id", "source_title", "url", "tier", "accessed_date", "data_as_of")
_LOCAL_LABEL: dict[str, str] = {"en": "local file", "es": "archivo local"}


def offline_enabled() -> bool:
    """True when HEURISMA_OFFLINE is set to 1/true/yes/on: skip the network and force the local-data rung."""
    return os.environ.get("HEURISMA_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        return []
    with csv_path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def utc_now() -> str:
    """ISO-8601 UTC timestamp (second precision) for ``data_attempts.csv`` ``attempted_utc``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_row(csv_path: Path, columns: tuple[str, ...], row: dict[str, str]) -> None:
    """Append ``row``. An existing file missing some of ``columns`` (e.g. a v0.5 ``data_attempts.csv`` without
    ``attempted_utc``) is widened first: its old rows get an empty value, so they read as undated/inherited."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not csv_path.exists() or csv_path.stat().st_size == 0
    if not is_new:
        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            header = [c.strip() for c in (reader.fieldnames or [])]
            old_rows = list(reader)
        missing = [c for c in columns if c not in header]
        if missing:
            header += missing
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore", restval="")
                writer.writeheader()
                writer.writerows(old_rows)
        fieldnames = header
    else:
        fieldnames = list(columns)
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore", restval="")
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def next_local_id(sources_csv: str | Path) -> str:
    """Return the next free local claim id (L1, L2, ...) for appendix/sources.csv."""
    used = [
        int(m.group(1))
        for r in _read_rows(Path(sources_csv))
        if (m := re.fullmatch(r"L(\d+)", (r.get("claim_id") or "").strip()))
    ]
    return f"L{max(used, default=0) + 1}"


def append_attempt(
    attempts_csv: str | Path,
    target: str,
    source: str,
    query: str,
    outcome: str,
    failure_reason: str = "",
    fallback: str = "",
) -> dict[str, str]:
    """Append one rung to data_attempts.csv with ``attempted_utc`` stamped by the tool, never typed by hand."""
    row = {
        "target_series": target,
        "source_tried": source,
        "query_or_endpoint": query,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "fallback_used": fallback,
        "attempted_utc": utc_now(),
    }
    _append_row(Path(attempts_csv), ATTEMPT_COLS, row)
    return row


def log_offline_attempt(
    attempts_csv: str | Path, source: str, reason: str, target: str = "", endpoint: str = ""
) -> None:
    """Record a skipped online rung (HEURISMA_OFFLINE=1) in the canonical data_attempts.csv."""
    append_attempt(attempts_csv, target, source, endpoint, "offline mode", failure_reason=reason)


def _find_registered(sources_csv: Path, url: str, sha: str) -> dict[str, str] | None:
    legacy = "file://" + url if not url.startswith(("file:", "http:", "https:")) else url  # v0.5 rows
    for r in _read_rows(sources_csv):
        if (r.get("url") or "").strip() in (url, legacy) or sha in (r.get("source_title") or "") or sha in (r.get("sha256") or ""):
            return r
    return None


def register_local(
    path: str | Path,
    sources_csv: str | Path,
    tier: str,
    title: str,
    claim_id: str = "",
    data_as_of: str = "",
    lang: str = "en",
    relative_to: str | Path | None = None,
) -> dict[str, str]:
    """Append a local-file provenance row to sources.csv (file:// URI + SHA-256) and return it.

    - ``claim_id`` empty -> next free ``L<n>`` so the source can be cited as ``[@L1]``.
    - Registering the same file again (same URI or same SHA-256) returns the existing row, never a duplicate.
    - ``relative_to`` stores a scheme-less project-relative path (``appendix/data/x.csv``) for files inside that
      folder; ``file:///abs/path`` is kept only for files outside it (a ``file://appendix/...`` URI would read
      ``appendix`` as a host name).
    - ``lang`` (``en``/``es``) localizes the "(local file, sha256 ...)" suffix.
    """
    p = Path(path).resolve()
    sha = sha12(p)
    if relative_to is not None:
        rel = Path(os.path.relpath(p, Path(relative_to).resolve())).as_posix()
        url = quote(rel) if not rel.startswith("../") else p.as_uri()
    else:
        url = p.as_uri()
    sp = Path(sources_csv)
    existing = _find_registered(sp, url, sha)
    if existing is not None:
        return dict(existing)
    label = _LOCAL_LABEL.get(lang, _LOCAL_LABEL["en"])
    row = {
        "claim_id": claim_id or next_local_id(sp),
        "source_title": f"{title} ({label}, sha256 {sha})",
        "url": url,
        "tier": tier,
        "accessed_date": date.today().isoformat(),
        "data_as_of": data_as_of,
    }
    _append_row(sp, SOURCE_COLS, row)
    return row


def import_local(
    path: str | Path,
    into: str | Path,
    sources_csv: str | Path,
    tier: str,
    title: str,
    lang: str = "en",
    claim_id: str = "",
    data_as_of: str = "",
) -> dict[str, str]:
    """Copy a user file into ``into`` (appendix/data), register the COPY, and log the rung in data_attempts.csv.

    Idempotent: importing the same file again adds no rows. Raises ValueError if a different file of the
    same name already sits in ``into`` (nothing is overwritten).
    """
    src = Path(path).resolve()
    dest_dir = Path(into)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = (dest_dir / src.name).resolve()
    if dest.exists() and dest != src and sha12(dest) != sha12(src):
        raise ValueError(f"{dest} already exists with different content; rename the source file or remove the old copy")
    if not dest.exists():
        shutil.copy2(src, dest)
    sp = Path(sources_csv)
    report_root = sp.resolve().parent.parent
    sha = sha12(dest)
    rel_url = quote(Path(os.path.relpath(dest, report_root)).as_posix())
    already = _find_registered(sp, rel_url, sha) is not None
    row = register_local(
        dest, sp, tier, title, claim_id=claim_id, data_as_of=data_as_of, lang=lang, relative_to=report_root
    )
    if not already:
        append_attempt(
            sp.parent / "data_attempts.csv",
            title,
            f"{_LOCAL_LABEL.get(lang, _LOCAL_LABEL['en'])} ({src.name})",
            rel_url,
            "used",
            fallback=f"local:{rel_url} sha256:{sha}",
        )
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("inventory", help="List supported local data files with size, mtime, and sha256.")
    a.add_argument("roots", nargs="*", help="Directories or files to scan.")

    b = sub.add_parser("preview", help="Inspect schema and sample rows of a local file.")
    b.add_argument("path", help="Path to local file.")
    b.add_argument("--n", type=int, default=10, help="Number of sample rows/lines to show.")
    b.add_argument("--sheet", default=None, help="Optional XLSX sheet name.")

    c = sub.add_parser(
        "register",
        help="Append a local file to sources.csv (project-relative path + sha256; file:/// only outside the project).",
    )
    c.add_argument("path", help="Path to local file.")
    c.add_argument("--sources", required=True, help="Path to appendix/sources.csv.")
    c.add_argument("--tier", default="Tier 3", help="Evidence tier (default: Tier 3).")
    c.add_argument("--title", required=True, help="Human-readable source title.")
    c.add_argument("--claim", default="", help="Optional claim_id (default: next free L<n>).")
    c.add_argument("--as-of", default="", help="Optional data_as_of date.")
    c.add_argument("--lang", choices=("en", "es"), default="en", help="Language of the registered title suffix.")

    d = sub.add_parser("import", help="Copy a file into appendix/data/, register the copy and log the rung in one step.")
    d.add_argument("path", help="Path to the user's local file.")
    d.add_argument("--into", default="appendix/data", help="Destination directory (default: appendix/data).")
    d.add_argument("--sources", required=True, help="Path to appendix/sources.csv.")
    d.add_argument("--tier", default="Tier 3", help="Evidence tier (default: Tier 3; unknown origin is never Tier 1).")
    d.add_argument("--title", required=True, help="Human-readable source title.")
    d.add_argument("--claim", default="", help="Optional claim_id (default: next free L<n>).")
    d.add_argument("--as-of", default="", help="Optional data_as_of date.")
    d.add_argument("--lang", choices=("en", "es"), default="en", help="Language of the registered title suffix.")

    e = sub.add_parser("attempt", help="Log one cascade rung in data_attempts.csv with a tool-stamped attempted_utc.")
    e.add_argument("--csv", default="appendix/data_attempts.csv", help="Path to appendix/data_attempts.csv.")
    e.add_argument("--target", required=True, help="target_series (the series or document sought).")
    e.add_argument("--source", required=True, help="source_tried (provider, mirror, or local inventory).")
    e.add_argument("--query", required=True, help="query_or_endpoint (URL, variable id, keywords).")
    e.add_argument("--outcome", required=True, help="outcome (e.g. 'HTTP 404', 'not found', 'used').")
    e.add_argument("--failure-reason", default="", help="failure_reason (empty on success).")
    e.add_argument("--fallback", default="", help="fallback_used (e.g. 'local:appendix/data/x.csv sha256:...').")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "inventory":
            rows = inventory(args.roots)
            if not rows:
                print("No local data files found in:", args.roots or list(DEFAULT_ROOTS))
            for r in rows:
                print(f"{r['kind']:<10} {r['bytes']:>12,}  {r['modified']}  {r['sha256_12']}  {r['path']}")
        elif args.cmd == "preview":
            print(preview(args.path, args.n, args.sheet))
        elif args.cmd == "register":
            report_root = Path(args.sources).resolve().parent.parent  # appendix/sources.csv -> report folder
            print(
                register_local(
                    args.path, args.sources, args.tier, args.title, args.claim, args.as_of,
                    lang=args.lang, relative_to=report_root,
                )
            )
        elif args.cmd == "attempt":
            print(
                append_attempt(
                    args.csv, args.target, args.source, args.query, args.outcome,
                    failure_reason=args.failure_reason, fallback=args.fallback,
                )
            )
        else:
            print(
                import_local(
                    args.path, args.into, args.sources, args.tier, args.title,
                    lang=args.lang, claim_id=args.claim, data_as_of=args.as_of,
                )
            )
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
