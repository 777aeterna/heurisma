#!/usr/bin/env python3
"""Zero-dependency local data inventory, preview, table reader, and provenance registration for Heurisma.

Usage:
  python3 -B local_data.py inventory [dir ...]
  python3 -B local_data.py preview <file> [--n 10] [--sheet NAME]
  python3 -B local_data.py register <file> --sources appendix/sources.csv --tier "Tier 1" --title "..." [--claim C1] [--as-of YYYY-MM-DD]

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
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

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
        delim, dec = _sniff_csv(p.read_bytes()[:20000].decode("utf-8", "replace"))
        out.append(f"rows={len(rows)} delimiter={delim!r} decimal_comma={dec}")
        out.append(f"columns={list(rows[0]) if rows else []}")
        out.extend(str(r) for r in rows[:n])
    elif kind == "xlsx":
        sheets, rows = read_xlsx(p, sheet, max_rows=n)
        out.append(f"sheets={sheets}  (showing: {sheet or sheets[0]})")
        out.extend(" | ".join("" if v is None else str(v) for v in r)[:200] for r in rows)
    elif kind == "json":
        js = read_json(p)
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
def register_local(
    path: str | Path,
    sources_csv: str | Path,
    tier: str,
    title: str,
    claim_id: str = "",
    data_as_of: str = "",
) -> dict[str, str]:
    """Append a local file provenance row to sources.csv with file:// URI, sha256_12, and access date."""
    p = Path(path).resolve()
    row = {
        "claim_id": claim_id,
        "source_title": f"{title} (local file, sha256 {sha12(p)})",
        "url": p.as_uri(),
        "tier": tier,
        "accessed_date": date.today().isoformat(),
        "data_as_of": data_as_of,
    }
    sp = Path(sources_csv)
    sp.parent.mkdir(parents=True, exist_ok=True)
    is_new = not sp.exists()
    with sp.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row))
        if is_new:
            writer.writeheader()
        writer.writerow(row)
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

    c = sub.add_parser("register", help="Append a local file entry to sources.csv with file:// URI and sha256.")
    c.add_argument("path", help="Path to local file.")
    c.add_argument("--sources", required=True, help="Path to appendix/sources.csv.")
    c.add_argument("--tier", default="Tier 3", help="Evidence tier (default: Tier 3).")
    c.add_argument("--title", required=True, help="Human-readable source title.")
    c.add_argument("--claim", default="", help="Optional claim_id (e.g., C1).")
    c.add_argument("--as-of", default="", help="Optional data_as_of date.")

    args = ap.parse_args(argv)
    if args.cmd == "inventory":
        rows = inventory(args.roots)
        if not rows:
            print("No local data files found in:", args.roots or list(DEFAULT_ROOTS))
        for r in rows:
            print(f"{r['kind']:<10} {r['bytes']:>12,}  {r['modified']}  {r['sha256_12']}  {r['path']}")
    elif args.cmd == "preview":
        print(preview(args.path, args.n, args.sheet))
    else:
        print(register_local(args.path, args.sources, args.tier, args.title, args.claim, args.as_of))
    return 0


if __name__ == "__main__":
    sys.exit(main())
