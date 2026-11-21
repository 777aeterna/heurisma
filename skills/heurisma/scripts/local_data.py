#!/usr/bin/env python3
"""Zero-dependency local data inventory, preview, table reader, and provenance registration for Heurisma.

Usage:
  python3 -B local_data.py inventory [dir ...]
  python3 -B local_data.py preview <file> [--n 10] [--sheet NAME]
  python3 -B local_data.py register <file> --sources appendix/sources.csv --tier "Tier 1" --title "..." [--claim L1] [--as-of YYYY-MM-DD] [--lang en|es]
  python3 -B local_data.py import <file> --into appendix/data --sources appendix/sources.csv --tier "Tier 1" --title "..." [--lang en|es]
  python3 -B local_data.py run-start --appendix appendix
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

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from contracts import (  # noqa: E402
    ATTEMPT_COLS,
    SOURCE_COLS,
    VALID_KINDS,
    VALID_SELECTIONS,
    __version__,
)
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


# --- decimal convention is decided per COLUMN (v0.7.0): one file can hold "3.1416" and "12,34" side by side ---
_EU_CLEAR = "eu"          # 1,5 · 12,34 · 1.234,56 · 1.234.567 -> only readable with a decimal comma / dot thousands
_US_CLEAR = "us"          # 3.1416 · 2.5 · 1,234,567 · 1,234.5 -> only readable with a decimal point / comma thousands
_COMMA_AMBIG = "comma?"   # 1,234 -> decimal comma (1.234) or thousands comma (1234)
_DOT_AMBIG = "dot?"       # 1.234 -> decimal point (1.234) or thousands dot (1234)
_INT = "int"
_SCI = "sci"
_TEXT = "text"


def _cell_class(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"[+-]?\d+", s):
        return _INT
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[eE][+-]?\d+", s):
        return _SCI
    m = re.fullmatch(r"[+-]?(\d+(?:\.\d{3})*),(\d+)", s)  # comma as the last separator
    if m:
        whole, frac = m.group(1), m.group(2)
        if "." in whole or len(frac) != 3 or len(whole) > 3:
            return _EU_CLEAR
        return _COMMA_AMBIG
    if re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+\.\d+", s):
        return _US_CLEAR
    if re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3}){2,}", s):
        return _US_CLEAR
    if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3}){2,}", s):
        return _EU_CLEAR
    if re.fullmatch(r"[+-]?\d{1,3}\.\d{3}", s):
        return _DOT_AMBIG
    if re.fullmatch(r"[+-]?\d+\.\d+", s):
        return _US_CLEAR
    return _TEXT


def _convert_cell(s: str, comma: bool) -> Any:
    t = s.strip()
    t = t.replace(".", "").replace(",", ".") if comma else t.replace(",", "")
    try:
        return float(t) if re.search(r"[.eE]", t) else int(t)
    except ValueError:
        return s


NA_SENTINELS: frozenset[str] = frozenset({"", "na", "n/a", "null", "none", "nan", "—", "-"})


def _analyze_csv_columns(
    headers: list[str], body: list[list[str]], delim: str, keep: Any = False
) -> dict[str, dict[str, Any]]:
    """Per-column format: ``{"format": ..., "comma": bool|None, "keep": bool}``; raises ValueError on a mixed column."""
    cols: dict[str, dict[str, Any]] = {}
    pending: list[str] = []
    for ci, name in enumerate(headers):
        cells = [
            r[ci].strip()
            for r in body
            if ci < len(r) and r[ci].strip().lower() not in NA_SENTINELS
        ]
        classes = [_cell_class(c) for c in cells]
        numeric = [c for c in classes if c != _TEXT]
        keep_col = keep is True or (not isinstance(keep, bool) and name in set(keep or ()))
        identifier = any(re.fullmatch(r"0\d+", c) for c in cells)
        if keep_col or identifier or not cells or len(numeric) * 2 < len(cells):
            cols[name] = {"format": "text", "comma": None, "keep": True, "identifier": identifier and not keep_col}
            continue
        eu = [c for c, k in zip(cells, classes) if k == _EU_CLEAR]
        us = [c for c, k in zip(cells, classes) if k == _US_CLEAR]
        if eu and us:
            raise ValueError(
                f"CSV column '{name}' mixes decimal comma and decimal point (comma: {', '.join(repr(c) for c in eu[:3])}; "
                f"point: {', '.join(repr(c) for c in us[:3])}); the right reading is ambiguous. Fix the file, or pass "
                f"keep_strings=['{name}'] to read it as text."
            )
        if eu:
            cols[name] = {"format": "decimal-comma", "comma": True, "keep": False}
        elif us:
            cols[name] = {"format": "decimal-point", "comma": False, "keep": False}
        elif all(k in (_INT, _SCI) for k in classes):
            cols[name] = {"format": "integer" if all(k == _INT for k in classes) else "number", "comma": False, "keep": False}
        else:
            cols[name] = {"format": "ambiguous", "comma": None, "keep": False}
            pending.append(name)
    decided = [c["comma"] for c in cols.values() if c["comma"] is not None and c["format"].startswith("decimal")]
    if decided and all(decided):
        file_comma = True
    elif decided and not any(decided):
        file_comma = False
    else:
        file_comma = delim != ","  # nothing decisive in the file: follow the delimiter, as before v0.7.0
    for name in pending:
        cols[name]["comma"] = file_comma
        cols[name]["format"] = f"ambiguous -> {'decimal-comma/thousands-dot' if file_comma else 'decimal-point/thousands-comma'}"
    return cols


def _to_number(v: str, decimal_comma: bool) -> Any:
    s = v.strip()
    if s.lower() in NA_SENTINELS:
        return None
    return _convert_cell(s, decimal_comma)


def worst_tier(
    rows: list[dict[str, Any]],
    source_col: str = "primary_source_id",
    meta_csv: str | Path | None = None,
) -> str:
    """Return the weakest evidence tier across ``rows`` by looking up ``source_col`` IDs in ``meta_csv``.

    IDs may be separated by ``;`` or ``,``. Unknown IDs or missing metadata conservatively return ``"Tier 3"``.
    """
    rank = {"tier 1": 1, "tier 2": 2, "tier 3": 3}
    tier_by_id: dict[str, int] = {}
    if meta_csv is not None and Path(meta_csv).is_file():
        for mrow in _read_rows(Path(meta_csv)):
            sid = (mrow.get("source_id") or mrow.get("claim_id") or mrow.get("id") or "").strip()
            # `tier` or any `tier*` column (a real run used `tier_classification`)
            raw_tier = mrow.get("tier") or next((v for k, v in mrow.items() if str(k).strip().lower().startswith("tier") and v), "")
            tval = str(raw_tier or "").strip().lower()
            m = re.search(r"tier\s*([123])", tval)
            if sid and m:
                tier_by_id[sid] = int(m.group(1))
    worst = 0
    for row in rows:
        raw = str(row.get(source_col) or "").strip()
        if not raw:
            continue
        for token in re.split(r"[;,]", raw):
            sid = token.strip()
            if not sid:
                continue
            worst = max(worst, tier_by_id.get(sid, 3))
    return f"Tier {worst}" if worst in rank.values() else "Tier 3"


DEFAULT_MAX_BYTES = 100 * 1024 * 1024  # 100 MB default per-file cap (override with HEURISMA_MAX_BYTES)
MAX_XLSX_COMPRESSION_RATIO = 100.0
MIN_RATIO_CHECK_BYTES = 1024 * 1024  # apply ratio check once uncompressed size >= 1 MB
_XML_FORBIDDEN_RE = re.compile(rb"<!(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def _max_bytes() -> int:
    raw = os.environ.get("HEURISMA_MAX_BYTES", "").strip()
    if raw:
        try:
            val = int(raw)
            if val > 0:
                return val
        except ValueError:
            pass
    return DEFAULT_MAX_BYTES


def _check_file_size(path: Path) -> None:
    limit = _max_bytes()
    size = path.stat().st_size
    if size > limit:
        raise ValueError(
            f"{path.name} is {size:,} bytes, exceeding the {limit:,}-byte safety limit "
            f"(set HEURISMA_MAX_BYTES to override)."
        )


def _check_xlsx_zip(z: zipfile.ZipFile) -> int:
    """Validate XLSX zip member sizes and compression ratios; returns max uncompressed budget."""
    max_uncompressed = _max_bytes() * 2
    total_uncompressed = 0
    total_compressed = 0
    for info in z.infolist():
        total_uncompressed += info.file_size
        total_compressed += info.compress_size
        if info.file_size >= MIN_RATIO_CHECK_BYTES:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_XLSX_COMPRESSION_RATIO:
                raise ValueError(
                    f"XLSX member {info.filename!r} rejected: compression ratio {ratio:.1f}x exceeds "
                    f"{MAX_XLSX_COMPRESSION_RATIO:.0f}x (possible zip bomb)."
                )
    if total_uncompressed > max_uncompressed:
        raise ValueError(
            f"XLSX uncompressed size ({total_uncompressed:,} bytes) exceeds the {max_uncompressed:,}-byte "
            f"safety limit (set HEURISMA_MAX_BYTES to override)."
        )
    if total_uncompressed >= MIN_RATIO_CHECK_BYTES:
        total_ratio = total_uncompressed / max(total_compressed, 1)
        if total_ratio > MAX_XLSX_COMPRESSION_RATIO:
            raise ValueError(
                f"XLSX archive rejected: overall compression ratio {total_ratio:.1f}x exceeds "
                f"{MAX_XLSX_COMPRESSION_RATIO:.0f}x (possible zip bomb)."
            )
    return max_uncompressed


def _read_xlsx_xml(z: zipfile.ZipFile, member: str, max_bytes: int) -> bytes:
    """Read an XML member with a hard decompressed-byte cap and reject DOCTYPE/ENTITY declarations."""
    with z.open(member) as fh:
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(
            f"XLSX member {member!r} decompressed size exceeds the {max_bytes:,}-byte safety limit."
        )
    if _XML_FORBIDDEN_RE.search(data):
        raise ValueError(f"XLSX member {member!r} contains forbidden DOCTYPE/ENTITY declaration.")
    return data


def _decode_csv(path: Path) -> str:
    _check_file_size(path)
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return ""


def csv_columns(path: str | Path, keep_strings: Any = False) -> tuple[str, list[str], list[list[str]], dict[str, dict[str, Any]]]:
    """(delimiter, headers, raw rows, per-column formats) of a CSV/TSV file."""
    text = _decode_csv(Path(path))
    delim, _ = _sniff_csv(text)
    table = list(csv.reader(io.StringIO(text), delimiter=delim))
    if not table:
        return delim, [], [], {}
    headers = [h.strip() for h in table[0]]
    body = table[1:]
    return delim, headers, body, _analyze_csv_columns(headers, body, delim, keep_strings)


def read_csv(path: Path, keep_strings: Any = False) -> list[dict[str, Any]]:
    """Read a CSV/TSV file: delimiter sniffing, per-column decimal convention, UTF-8/latin-1 fallback.

    Each column is read as decimal-comma or decimal-point from its own cells (a file may hold both); a column that
    mixes the two raises ValueError instead of guessing, mostly-text columns and zero-padded identifiers stay text,
    and ``keep_strings`` (a list of column names, or True) forces text.
    """
    _, headers, body, cols = csv_columns(path, keep_strings)
    out: list[dict[str, Any]] = []
    for r in body:
        row: dict[str, Any] = {}
        for ci, name in enumerate(headers):
            raw = r[ci] if ci < len(r) else ""
            info = cols[name]
            if info["keep"]:
                row[name] = raw.strip()
            else:
                row[name] = _to_number(raw, bool(info["comma"]))
        out.append(row)
    return out


def _xlsx_sheets(z: zipfile.ZipFile, max_bytes: int) -> dict[str, str]:
    wb = ET.fromstring(_read_xlsx_xml(z, "xl/workbook.xml", max_bytes))
    rels = ET.fromstring(_read_xlsx_xml(z, "xl/_rels/workbook.xml.rels", max_bytes))
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
    p = Path(path)
    _check_file_size(p)
    with zipfile.ZipFile(p) as z:
        max_uncompressed = _check_xlsx_zip(z)
        sheets = _xlsx_sheets(z, max_uncompressed)
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss_bytes = _read_xlsx_xml(z, "xl/sharedStrings.xml", max_uncompressed)
            for si in ET.fromstring(ss_bytes).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        name = sheet or next(iter(sheets))
        rows: list[list[Any]] = []
        sheet_bytes = _read_xlsx_xml(z, sheets[name], max_uncompressed)
        for _, el in ET.iterparse(io.BytesIO(sheet_bytes)):
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
    p = Path(path)
    _check_file_size(p)
    return json.loads(p.read_text(encoding="utf-8"))


def guess_header_row(rows: list[list[Any]], scan: int = 30) -> int:
    """Return index of the first row with the highest number of non-empty text cells."""
    best, best_i = -1, 0
    for i, r in enumerate(rows[:scan]):
        n = sum(isinstance(v, str) and v.strip() != "" for v in r)
        if n > best:
            best, best_i = n, i
    return best_i


def read_table(
    path: str | Path, sheet: str | None = None, header_row: int | None = None, keep_strings: Any = False
) -> list[dict[str, Any]]:
    """Read CSV, TSV, XLSX, or JSON into a list of row dicts (auto-detects XLSX headers and drops footer notes)."""
    p = Path(path)
    kind = DATA_EXT.get(p.suffix.lower())
    if kind == "csv":
        return read_csv(p, keep_strings=keep_strings)
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
def preview(path: str | Path, n: int = 10, sheet: str | None = None, keep_strings: Any = False) -> str:
    """Return a concise human-readable preview of a local data file."""
    p = Path(path)
    kind = DATA_EXT.get(p.suffix.lower(), "unknown")
    out = [f"{p}  [{kind}, {p.stat().st_size:,} bytes, sha256 {sha12(p)}]"]
    if kind == "csv":
        rows = read_csv(p, keep_strings=keep_strings)
        if not rows:
            raise ValueError(f"{p}: file is empty or has no data rows")
        delim, headers, raw_rows, cols = csv_columns(p, keep_strings)
        out.append(f"rows={len(rows)} delimiter={delim!r}")
        out.append(f"columns={list(rows[0])}")
        out.append("detected format per column:")
        for name in headers:
            info = cols[name]
            note = " (zero-padded identifier kept as text)" if info.get("identifier") else ""
            out.append(f"  {name}: {info['format']}{note}")
        out.append("first rows (raw -> converted):")
        for raw, conv in list(zip(raw_rows, rows))[:n]:
            parts = []
            for ci, name in enumerate(headers):
                rv = (raw[ci] if ci < len(raw) else "").strip()
                cv = conv[name]
                parts.append(f"{name}={cv!r}" if str(cv) == rv else f"{name}: raw {rv!r} -> {cv!r}")
            out.append("  " + "; ".join(parts))
    elif kind == "xlsx":
        sheets, xlsx_rows = read_xlsx(p, sheet, max_rows=n)
        out.append(f"sheets={sheets}  (showing: {sheet or sheets[0]})")
        out.extend(" | ".join("" if v is None else str(v) for v in r)[:200] for r in xlsx_rows)
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


def run_start(appendix_dir: str | Path, force: bool = False) -> dict[str, str]:
    """Stamp the run start in ``appendix/run.json`` (Stage 0). Idempotent: an existing stamp is returned unchanged
    unless ``force``; attempts logged before this instant count as inherited from an earlier run."""
    path = Path(appendix_dir) / "run.json"
    if path.is_file() and not force:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("run_started_utc"):
                return data
        except json.JSONDecodeError:
            pass
    data = {"run_started_utc": utc_now(), "stamped_by": "local_data.py run-start"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return data


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


def _relative_or_uri(p: Path, base: Path) -> str:
    """Return a quoted POSIX relative path under ``base``, or a ``file:///`` URI if outside or on another drive."""
    try:
        rel = Path(os.path.relpath(p, base.resolve())).as_posix()
    except ValueError:
        return p.as_uri()
    return quote(rel) if not rel.startswith("../") else p.as_uri()


def register_local(
    path: str | Path,
    sources_csv: str | Path,
    tier: str,
    title: str,
    claim_id: str = "",
    data_as_of: str = "",
    lang: str = "en",
    relative_to: str | Path | None = None,
    kind: str = "data",
    selection: str = "user-curated",
    retrieved_utc: str = "unknown",
) -> dict[str, str]:
    """Append a local-file provenance row to sources.csv (project-relative path + SHA-256) and return it.

    - ``claim_id`` empty -> next free ``L<n>`` so the source can be cited as ``[@L1]``.
    - Registering the same file again (same URI or same SHA-256) returns the existing row, never a duplicate.
    - ``relative_to`` stores a scheme-less project-relative path (``appendix/data/x.csv``) for files inside that
      folder; ``file:///abs/path`` is kept only for files outside it (a ``file://appendix/...`` URI would read
      ``appendix`` as a host name).
    - ``lang`` (``en``/``es``) localizes the "(local file, sha256 ...)" suffix.
    - ``selection``: who chose the file (``user-curated`` by default for a file the user supplied, ``agent-fetched``,
      ``third-party``); ``retrieved_utc``: when it was obtained from its origin, or ``unknown`` (then the validator
      keeps a user-curated row at Tier 3).
    """
    p = Path(path).resolve()
    sha = sha12(p)
    url = _relative_or_uri(p, Path(relative_to)) if relative_to is not None else p.as_uri()
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {', '.join(VALID_KINDS)}; got {kind!r}")
    if selection not in VALID_SELECTIONS:
        raise ValueError(f"selection must be one of {', '.join(VALID_SELECTIONS)}; got {selection!r}")
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
        "kind": kind,
        "sha256": sha,
        "selection": selection,
        "retrieved_utc": retrieved_utc or "unknown",
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
    selection: str = "user-curated",
    retrieved_utc: str = "unknown",
    kind: str = "data",
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
    rel_url = _relative_or_uri(dest, report_root)
    already = _find_registered(sp, rel_url, sha) is not None
    row = register_local(
        dest, sp, tier, title, claim_id=claim_id, data_as_of=data_as_of, lang=lang, relative_to=report_root,
        kind=kind, selection=selection, retrieved_utc=retrieved_utc,
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


TABLE_KINDS = ("csv", "xlsx", "json")


def _wishlist(path: str | Path | None) -> list[tuple[str, list[str]]]:
    """Lines ``name: keyword, keyword`` -> [(name, [keywords])]; blank lines and ``#`` comments are skipped."""
    if not path:
        return []
    items = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, kws = line.partition(":")
        words = [w.strip().lower() for w in (kws or name).split(",") if w.strip()]
        items.append((name.strip(), words))
    return items


def intake(
    folder: str | Path,
    appendix: str | Path = "appendix",
    channel: str = "data",
    selection: str = "user-curated",
    wishlist: str | Path | None = None,
    tier: str = "Tier 3",
    retrieved_utc: str = "unknown",
    lang: str = "en",
) -> dict[str, Any]:
    """Pre-intake (Stage -1): inspect, import and register every file of ``folder`` in one pass, and write
    ``appendix/intake.md`` (accepted/rejected files, detected format per CSV column, gaps against a wish-list).

    ``channel="data"`` imports tables (CSV/TSV/XLSX/JSON) into ``appendix/data/`` as ``kind=data``; a CSV with an
    ambiguous decimal column is rejected, never guessed. ``channel="sources"`` copies documents into
    ``appendix/corpus/`` as ``kind=literature``. Every row records ``selection`` and ``retrieved_utc``.
    """
    if channel not in ("data", "sources"):
        raise ValueError("channel must be 'data' or 'sources'")
    if selection not in VALID_SELECTIONS:
        raise ValueError(f"selection must be one of {', '.join(VALID_SELECTIONS)}; got {selection!r}")
    folder, appendix = Path(folder), Path(appendix)
    sources_csv = appendix / "sources.csv"
    accepted: list[dict[str, Any]] = []
    rejected: list[tuple[str, str]] = []
    for f in sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        rel = f.relative_to(folder).as_posix()
        kind_of = DATA_EXT.get(f.suffix.lower(), "unknown")
        formats: dict[str, str] = {}
        if channel == "data":
            if kind_of not in TABLE_KINDS:
                rejected.append((rel, f"not a table ({kind_of}); use --channel sources for documents"))
                continue
            try:
                if kind_of == "csv":
                    _, headers, _, cols = csv_columns(f)
                    formats = {h: cols[h]["format"] for h in headers}
                else:
                    read_table(f)
            except (ValueError, KeyError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
                rejected.append((rel, str(exc)))
                continue
            row = import_local(f, appendix / "data", sources_csv, tier, f.stem, lang=lang,
                               selection=selection, retrieved_utc=retrieved_utc)
        else:
            dest_dir = appendix / "corpus"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f.name
            if dest.exists() and sha12(dest) != sha12(f):
                rejected.append((rel, f"{dest} already exists with different content"))
                continue
            if not dest.exists():
                shutil.copy2(f, dest)
            row = register_local(dest, sources_csv, tier, f.stem, lang=lang, relative_to=appendix.resolve().parent,
                                 kind="literature", selection=selection, retrieved_utc=retrieved_utc)
        accepted.append({"file": rel, "claim_id": row["claim_id"], "sha256": row.get("sha256", ""), "formats": formats})

    gaps = []
    for name, words in _wishlist(wishlist):
        haystack = " ".join(
            [a["file"].lower() for a in accepted] + [c.lower() for a in accepted for c in a["formats"]]
        )
        if not any(w in haystack for w in words):
            gaps.append(name)

    section_header = f"## Channel: {channel} (`{folder.name}/`)"
    sec_lines = [
        section_header,
        "",
        f"- folder: `{folder.name}/` · channel: {channel} · selection: {selection} · retrieved_utc: {retrieved_utc}",
        f"- run at: {utc_now()} (local_data.py intake)",
        "",
        "### Files",
        "",
    ]
    for a in accepted:
        sec_lines.append(f"- accepted: {a['file']} -> [@{a['claim_id']}] (sha256 {a['sha256']})")
        for col, fmt in a["formats"].items():
            sec_lines.append(f"  - {col}: {fmt}")
    for rel, why in rejected:
        sec_lines.append(f"- rejected: {rel} — {why}")
    if wishlist:
        sec_lines += ["", "### Gaps (wish-list items no accepted file covers)", ""]
        sec_lines += [f"- {g}" for g in gaps] or ["- none"]
    sec_block = "\n".join(sec_lines)
    footer = "Uploading a file never raises its tier: without an origin URL, a retrieval date and a hash it stays Tier 3."
    appendix.mkdir(parents=True, exist_ok=True)
    intake_md = appendix / "intake.md"
    if intake_md.is_file():
        existing = intake_md.read_text(encoding="utf-8")
        body_no_footer = existing.replace(footer, "").strip()
        sec_re = re.compile(
            rf"^## Channel:\s*{re.escape(channel)}\b.*?(?=^## Channel:|\Z)",
            flags=re.MULTILINE | re.DOTALL,
        )
        if sec_re.search(body_no_footer):
            merged = sec_re.sub(sec_block + "\n\n", body_no_footer).strip()
        elif body_no_footer.startswith("# Intake report"):
            merged = body_no_footer + "\n\n" + sec_block
        else:
            merged = "# Intake report\n\n" + sec_block
        intake_md.write_text(merged + "\n\n" + footer + "\n", encoding="utf-8")
    else:
        intake_md.write_text("# Intake report\n\n" + sec_block + "\n\n" + footer + "\n", encoding="utf-8")
    return {"accepted": accepted, "rejected": rejected, "gaps": gaps}


def _prereg_digest(record: dict[str, Any]) -> str:
    keys = ("sealed_utc", "hypotheses", "plan", "known_artifacts", "post_hoc")
    body = {k: record[k] for k in keys if k in record}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def preregister(
    appendix: str | Path,
    hypotheses: dict[str, str],
    plan: str,
    allow_post_hoc: bool = False,
) -> dict[str, Any]:
    """Seal H0/H1/... and the analysis plan in ``appendix/preregistration.json`` before looking at the data.

    Refuses to overwrite an existing seal, records ``known_artifacts`` present in ``appendix/``, and refuses
    post-hoc sealing if ``output.txt`` or ``numbers.json`` already exist unless ``allow_post_hoc=True``.
    """
    app = Path(appendix)
    path = app / "preregistration.json"
    if path.exists():
        raise ValueError(f"{path} already exists; a preregistration is sealed once (explain any change in Section 3)")
    if not hypotheses.get("H0") or not hypotheses.get("H1"):
        raise ValueError("preregister needs at least H0 and H1")
    post_hoc_files = [name for name in ("output.txt", "numbers.json") if (app / name).is_file()]
    if post_hoc_files and not allow_post_hoc:
        raise ValueError(
            f"Cannot seal preregistration after analysis outputs already exist ({', '.join(post_hoc_files)}); "
            f"run prereg in Stage 1 before analysis.py (or pass --allow-post-hoc to mark it post-hoc)."
        )
    known_artifacts: dict[str, str] = {}
    if app.is_dir():
        for fp in sorted(app.rglob("*"), key=lambda p: p.relative_to(app).parts):
            if fp.is_file() and "__pycache__" not in fp.parts and fp.suffix != ".pyc":
                known_artifacts[fp.relative_to(app).as_posix()] = sha12(fp)
    record: dict[str, Any] = {
        "sealed_utc": utc_now(),
        "hypotheses": hypotheses,
        "plan": plan,
        "known_artifacts": known_artifacts,
    }
    if post_hoc_files:
        record["post_hoc"] = True
    record["sha256"] = _prereg_digest(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"local_data.py {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("inventory", help="List supported local data files with size, mtime, and sha256.")
    a.add_argument("roots", nargs="*", help="Directories or files to scan.")

    b = sub.add_parser("preview", help="Inspect schema and sample rows of a local file.")
    b.add_argument("path", help="Path to local file.")
    b.add_argument("--n", type=int, default=10, help="Number of sample rows/lines to show.")
    b.add_argument("--sheet", default=None, help="Optional XLSX sheet name.")
    b.add_argument("--keep-strings", default="", help="Comma-separated CSV columns to read as text (ids, zip codes).")

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

    g = sub.add_parser("intake", help="Stage -1: import and register a whole folder; writes appendix/intake.md.")
    g.add_argument("folder", help="Folder to ingest (datos/ for data, inbox/sources/ for documents).")
    g.add_argument("--appendix", default="appendix", help="Appendix directory (default: appendix).")
    g.add_argument("--channel", choices=("data", "sources"), default="data")
    g.add_argument("--selection", choices=VALID_SELECTIONS, default="user-curated")
    g.add_argument("--wishlist", default=None, help="Text file with lines 'name: keyword, keyword' to report gaps.")
    g.add_argument("--tier", default="Tier 3", help="Tier for every ingested file (default: Tier 3).")
    g.add_argument("--retrieved-utc", default="unknown", help="When the files were retrieved from their origin.")
    g.add_argument("--lang", choices=("en", "es"), default="en")

    h = sub.add_parser("prereg", help="Seal hypotheses and analysis plan in appendix/preregistration.json (once).")
    h.add_argument("--appendix", default="appendix")
    h.add_argument("--h0", required=True)
    h.add_argument("--h1", required=True)
    h.add_argument("--h2", default="")
    h.add_argument("--plan", required=True)
    h.add_argument("--allow-post-hoc", action="store_true", help="Allow sealing after output.txt/numbers.json exist (marks post_hoc=true).")

    f = sub.add_parser("run-start", help="Stamp appendix/run.json with the run start (Stage 0); idempotent.")
    f.add_argument("--appendix", default="appendix", help="Appendix directory (default: appendix).")
    f.add_argument("--force", action="store_true", help="Overwrite an existing stamp (starts a new run).")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "inventory":
            rows = inventory(args.roots)
            if not rows:
                print("No local data files found in:", args.roots or list(DEFAULT_ROOTS))
            for r in rows:
                print(f"{r['kind']:<10} {r['bytes']:>12,}  {r['modified']}  {r['sha256_12']}  {r['path']}")
        elif args.cmd == "preview":
            print(preview(args.path, args.n, args.sheet, keep_strings=[c for c in args.keep_strings.split(",") if c]))
        elif args.cmd == "register":
            report_root = Path(args.sources).resolve().parent.parent  # appendix/sources.csv -> report folder
            print(
                register_local(
                    args.path, args.sources, args.tier, args.title, args.claim, args.as_of,
                    lang=args.lang, relative_to=report_root,
                )
            )
        elif args.cmd == "intake":
            res = intake(args.folder, args.appendix, args.channel, args.selection, args.wishlist, args.tier,
                         args.retrieved_utc, args.lang)
            print(f"accepted {len(res['accepted'])}, rejected {len(res['rejected'])}, gaps {len(res['gaps'])}; "
                  f"see {Path(args.appendix) / 'intake.md'}")
        elif args.cmd == "prereg":
            hyp = {"H0": args.h0, "H1": args.h1}
            if args.h2:
                hyp["H2"] = args.h2
            print(preregister(args.appendix, hyp, args.plan, allow_post_hoc=args.allow_post_hoc))
        elif args.cmd == "run-start":
            print(run_start(args.appendix, force=args.force))
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
