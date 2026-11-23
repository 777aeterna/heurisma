#!/usr/bin/env python3
"""Freeze the validator's complete output so a refactor can prove it changed nothing.

The snapshot holds, for the in-repo inputs, every message the validator produces with its stable code:
the Level 1 brief, both examples at Levels 2 and 3 (with their HTML), and every mutation of tests/mutations.py.
Extra run folders (for example a real run kept outside the repository) are added with ``--run DIR:LEVEL``; their
snapshot is not meant to be committed, so pass ``--file`` to keep it elsewhere.

Usage:
    python3 -B tests/snapshot_validator.py --write [--file PATH] [--run DIR:LEVEL ...]
    python3 -B tests/snapshot_validator.py --check [--file PATH] [--run DIR:LEVEL ...]   (exit 1 on any difference)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations as M  # noqa: E402
import validate_report  # noqa: E402

DEFAULT_FILE = Path(__file__).resolve().parent / "fixtures" / "validator_snapshot.json"
EXAMPLES = ("level2-study", "showcase-hybrid-work")


def _clean(msg: str) -> str:
    """Drop machine-specific temp paths so the snapshot is identical on every machine."""
    return re.sub(r"(?:/tmp|/var/folders|C:\\\\Users)[^\s'\"),;]*", "<tmp>", msg)


def _items(errors: list[str], warnings: list[str]) -> dict[str, list[list[str]]]:
    def coded(msgs: list[str]) -> list[list[str]]:
        return [[*validate_report.classify_message(m), _clean(m)] for m in msgs]

    return {"errors": coded(errors), "warnings": coded(warnings)}


def run_folder(folder: Path, level: int) -> dict[str, list[list[str]]]:
    report = folder / "report.md"
    errors, warnings = validate_report.validate_report_full(report.read_text(encoding="utf-8"), level=level, report_dir=folder)
    html = folder / "report.html"
    if html.is_file():
        h_err, h_warn = validate_report.validate_html_full(html)
        errors += h_err
        warnings += h_warn + validate_report.check_html_freshness(html, report)
    return _items(errors, warnings)


def build(extra_runs: list[str]) -> dict:
    root = M.ROOT
    snap: dict = {"version": validate_report.__version__, "inputs": {}, "mutations": {}}
    brief = root / "examples" / "level1-brief-example.md"
    errors, warnings = validate_report.validate_report_full(brief.read_text(encoding="utf-8"), level=1)
    snap["inputs"]["level1-brief@1"] = _items(errors, warnings)
    for name in EXAMPLES:
        for level in (2, 3):
            snap["inputs"][f"{name}@{level}"] = run_folder(root / "examples" / name, level)
    for spec in extra_runs:
        folder, _, level = spec.rpartition(":")
        snap["inputs"][f"run:{Path(folder).resolve().as_posix()}@{level}"] = run_folder(Path(folder), int(level))
    for name in M.MUTATIONS:
        snap["mutations"][name] = [[*validate_report.classify_message(m), _clean(m)] for m in M.run_mutation(name)]
    return snap


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    ap.add_argument("--run", action="append", default=[], metavar="DIR:LEVEL", help="extra run folder to include")
    args = ap.parse_args()
    snap = build(args.run)
    text = json.dumps(snap, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    if args.write:
        args.file.parent.mkdir(parents=True, exist_ok=True)
        args.file.write_text(text, encoding="utf-8")
        total = sum(len(v["errors"]) + len(v["warnings"]) for v in snap["inputs"].values()) + sum(len(v) for v in snap["mutations"].values())
        print(f"snapshot written: {args.file} ({len(snap['inputs'])} inputs, {len(snap['mutations'])} mutations, {total} messages)")
        return 0
    old = json.loads(args.file.read_text(encoding="utf-8"))
    new = json.loads(text)
    diffs = []
    for section in ("inputs", "mutations"):
        for key in sorted(set(old[section]) | set(new[section])):
            if old[section].get(key) != new[section].get(key):
                diffs.append(f"{section}/{key}")
    if diffs:
        print("snapshot differs in:", ", ".join(diffs))
        return 1
    print(f"snapshot identical ({len(new['inputs'])} inputs, {len(new['mutations'])} mutations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
