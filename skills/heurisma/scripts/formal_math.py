#!/usr/bin/env python3
"""Lean 4 / Lake formal-verification adapter modeled on anthropics/formal-math (Python >= 3.9, stdlib only)."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping
from urllib.parse import urlparse

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from contracts import (  # noqa: E402
    CONJECTURES_JSON as CONJECTURES_JSON,
    FORMAL_PROOFS_CSV as FORMAL_PROOFS_CSV,
    FORMAL_PROOF_COLS as FORMAL_PROOF_COLS,
    SOURCE_COLS as SOURCE_COLS,
    STANDARD_LEAN_AXIOMS as STANDARD_LEAN_AXIOMS,
    VALID_TIERS as VALID_TIERS,
    __version__ as __version__,
)
import fetch_lib  # noqa: E402
import local_data  # noqa: E402

DEFAULT_TOOLCHAIN = "leanprover/lean4:v4.16.0"
DEFAULT_REF_FILES: tuple[str, ...] = ("README.md", "lean-toolchain", "lakefile.toml", "Challenge.lean")
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")


class FormalError(ValueError):
    """Raised when formal project scaffolding, verification, or registration fails."""


def _validate_slug(slug: str) -> str:
    s = (slug or "").strip()
    if not _SLUG_RE.fullmatch(s):
        raise FormalError(f"Invalid formal project slug {slug!r}; use 1..64 ASCII letters, digits, '_' or '-'.")
    return s


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_executable(path: Path) -> bool:
    if not path.is_file():
        return False
    if os.name == "nt":
        return path.suffix.lower() in (".exe", ".cmd", ".bat", ".com")
    return os.access(path, os.X_OK)


# Explicit allowlist of host variables the Lean/Lake toolchain lookup and `lake build` need; nothing else is read.
FORMAL_ENV_KEYS: tuple[str, ...] = (
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "COMSPEC", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL",
    "ELAN_HOME", "ELAN_TOOLCHAIN", "LAKE_HOME", "GIT_SSL_CAINFO", "SSL_CERT_FILE",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "HEURISMA_LAKE", "HEURISMA_LEAN", "HEURISMA_COMPARATOR", "HEURISMA_LANDRUN",
    "HEURISMA_OFFLINE", "HEURISMA_GITHUB_RAW_URL",
)


def formal_env() -> dict[str, str]:
    """Read only the explicit allowlist of variables the formal-verification adapter needs from the host environment."""
    out: dict[str, str] = {}
    for key in FORMAL_ENV_KEYS:
        val = os.environ.get(key)
        if val is not None:
            out[key] = val
    return out


def _find_tool(name: str, env_key: str, env: Mapping[str, str], *, check_elan: bool = False) -> Path | None:
    override = (env.get(env_key) or "").strip()
    if override:
        cand = Path(override)
        if _is_executable(cand):
            return cand

    path_var = env.get("PATH")
    if path_var:
        found = shutil.which(name, path=path_var)
        if found:
            return Path(found)

    if check_elan:
        home_raw = env.get("HOME") or env.get("USERPROFILE")
        if home_raw is None and "PATH" not in env:
            home_raw = str(Path.home())
        if home_raw:
            elan_bin = Path(home_raw) / ".elan" / "bin"
            suffixes = (".exe", ".cmd", ".bat") if os.name == "nt" else ("",)
            for sfx in suffixes:
                cand_elan = elan_bin / f"{name}{sfx}"
                if _is_executable(cand_elan):
                    return cand_elan
    return None


def find_lake(env: Mapping[str, str] | None = None) -> tuple[Path | None, Path | None]:
    """Locate optional local (lake, lean) binaries without ever installing anything."""
    env = formal_env() if env is None else env
    lake_bin = _find_tool("lake", "HEURISMA_LAKE", env, check_elan=True)
    lean_bin = _find_tool("lean", "HEURISMA_LEAN", env, check_elan=True)
    if lake_bin is not None and lean_bin is None:
        suffixes = (".exe", ".cmd", ".bat") if os.name == "nt" else ("",)
        for sfx in suffixes:
            sibling = lake_bin.parent / f"lean{sfx}"
            if _is_executable(sibling):
                lean_bin = sibling
                break
    if lake_bin is None:
        return None, None
    return lake_bin, lean_bin


def find_comparator(env: Mapping[str, str] | None = None) -> Path | None:
    """Locate optional `leanprover/comparator` binary if installed."""
    env = formal_env() if env is None else env
    return _find_tool("comparator", "HEURISMA_COMPARATOR", env, check_elan=True)


def find_landrun(env: Mapping[str, str] | None = None) -> Path | None:
    """Locate optional `landrun` sandbox binary if installed."""
    env = formal_env() if env is None else env
    return _find_tool("landrun", "HEURISMA_LANDRUN", env, check_elan=False)


def _strip_with_state(source: str) -> tuple[str, bool]:
    """Strip nested Lean block comments (/- ... -/), line comments (-- ...), string literals,
    Lean interpolated strings (s!"..." / f!"..."), and '...' char literals.

    Returns ``(stripped, balanced)`` where ``balanced`` is False when a block comment or
    string/char literal is left unterminated at end of input.
    """
    out: list[str] = []
    n = len(source)
    i = 0
    block_depth = 0
    in_line = False
    unterminated = False
    _IDENT_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'")

    def emit(ch: str) -> None:
        out.append(ch)

    def blank(ch: str) -> None:
        out.append("\n" if ch == "\n" else " ")

    def skip_escape() -> None:
        nonlocal i
        out.append(" ")
        i += 1
        if i < n:
            blank(source[i])
            i += 1

    def strip_char_literal() -> None:
        nonlocal i, unterminated
        emit("'")
        i += 1
        while i < n:
            ch = source[i]
            if ch == "\\":
                skip_escape()
            elif ch == "'":
                emit("'")
                i += 1
                return
            else:
                blank(ch)
                i += 1
        unterminated = True

    def strip_string(interp: bool) -> None:
        nonlocal i, unterminated
        emit('"')
        i += 1
        while i < n:
            ch = source[i]
            if ch == "\\":
                skip_escape()
            elif ch == '"':
                emit('"')
                i += 1
                return
            elif interp and ch == "{":
                emit(" ")
                i += 1
                strip_code(1)
            else:
                blank(ch)
                i += 1
        unterminated = True

    def strip_block_comment() -> None:
        nonlocal i, block_depth
        while i < n:
            if source[i] == "/" and i + 1 < n and source[i + 1] == "-":
                block_depth += 1
                emit("  ")
                i += 2
            elif source[i] == "-" and i + 1 < n and source[i + 1] == "/":
                block_depth -= 1
                emit("  ")
                i += 2
                if block_depth == 0:
                    return
            else:
                blank(source[i])
                i += 1

    def strip_line_comment() -> None:
        nonlocal i
        while i < n:
            if source[i] == "\n":
                emit("\n")
                i += 1
                return
            emit(" ")
            i += 1

    def strip_code(interp_depth: int) -> None:
        nonlocal i, block_depth, in_line
        while i < n:
            ch = source[i]
            nxt = source[i + 1] if i + 1 < n else ""
            if block_depth > 0:
                strip_block_comment()
                continue
            if in_line:
                strip_line_comment()
                in_line = False
                continue
            if ch == "/" and nxt == "-":
                block_depth = 1
                emit("  ")
                i += 2
            elif ch == "-" and nxt == "-":
                in_line = True
                emit("  ")
                i += 2
            elif ch == '"':
                if i >= 2 and source[i - 2 : i] in ("s!", "f!"):
                    strip_string(True)
                else:
                    strip_string(False)
            elif ch == "'" and (i == 0 or source[i - 1] not in _IDENT_CHARS):
                strip_char_literal()
            elif interp_depth >= 1 and ch == "{":
                emit(" ")
                i += 1
                strip_code(interp_depth + 1)
            elif interp_depth >= 1 and ch == "}":
                emit(" ")
                i += 1
                return
            else:
                emit(ch)
                i += 1

    strip_code(0)
    balanced = block_depth == 0 and not unterminated
    return "".join(out), balanced


def strip_lean_comments_and_strings(source: str) -> str:
    """Return Lean 4 source with nested block comments, line comments, and string contents blanked out."""
    stripped, _ = _strip_with_state(source)
    return stripped


# Forbidden in Solution.lean (all) and Challenge.lean (all EXCEPT `sorry`, which is allowed as statement stub per P-07)
_SOLUTION_HAZARD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("sorry", re.compile(r"\bsorry\b")),
    ("admit", re.compile(r"\badmit\b")),
    ("axiom", re.compile(r"\baxiom\b")),
    ("opaque", re.compile(r"\bopaque\b")),
    ("extern_or_implemented_by", re.compile(r"@\[[^\]]*\b(?:extern|implemented_by)\b")),
    ("native_decide", re.compile(r"\bnative_decide\b")),
    ("Lean.ofReduceBool", re.compile(r"\bLean\.ofReduceBool\b")),
)

_CHALLENGE_HAZARD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (lbl, pat) for lbl, pat in _SOLUTION_HAZARD_PATTERNS if lbl != "sorry"
)

_VACUOUS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("vacuous_false_premise", re.compile(r"\(\s*[A-Za-z0-9_']+\s*:\s*False\s*\)|\bFalse\s*(?:->|→)")),
    ("trivial_true_target", re.compile(r":\s*True\s*(?::=|\bby\b|\bwhere\b|$)", re.MULTILINE)),
)

_THEOREM_DECL_RE = re.compile(r"\b(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_']*)")
_THEOREM_HEADER_RE = re.compile(
    r"\b(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_']*)\s*(.*?)(?::=|\bwhere\b)",
    re.DOTALL,
)
_THEOREM_FULL_RE = re.compile(
    r"\b(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_']*)\s*(.*?)(?::=|\bwhere\b)\s*(.*?)(?=\b(?:theorem|lemma|def|abbrev|end\s+[A-Za-z_]|namespace\s+[A-Za-z_])\b|\Z)",
    re.DOTALL,
)
_TRIVIAL_CLOSING_TACTICS = frozenset(
    {
        "ring_nf", "ring", "simp", "simp_all", "simpa", "rfl", "norm_num", "norm_num1",
        "decide", "linarith", "nlinarith", "omega", "tauto", "aesop", "positivity",
        "noncomm_ring", "abel", "group", "field_simp",
    }
)
_PROP_TYPE_OP_RE = re.compile(r"(?:>=|<=|!=|≠|≥|≤|>|<|=|->|→|\bProp\b)")


def _extract_single_trivial_tactic(body: str) -> str | None:
    s = body.strip()
    if re.match(r"^by\b", s):
        s = s[2:].strip()
    steps = [st.strip() for st in re.split(r"<;>|[;\n·.]", s) if st.strip()]
    if not steps:
        return None
    for st in steps[:-1]:
        if not re.match(r"^(?:intro|intros|rintro|subst)\b", st):
            return None
    last_tok = steps[-1].split()[0]
    return last_tok if last_tok in _TRIVIAL_CLOSING_TACTICS else None


def _extract_hyp_binders(sig_text: str) -> list[tuple[str, str, int]]:
    """Return ``(name, type, end_index)`` for each named binder in a Lean signature fragment.

    Handles explicit ``(h : P)``, implicit ``{h : P}``, instance ``[h : P]``, and
    forall-bound ``∀ h : P`` binders. ``end_index`` is the offset just past the binder, so
    callers can search the remainder of the signature for uses of the bound name.
    """
    out: list[tuple[str, str, int]] = []
    n = len(sig_text)
    i = 0
    ident_re = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
    closers = {"(": ")", "[": "]", "{": "}"}
    while i < n:
        if sig_text[i] in "([{":
            open_ch = sig_text[i]
            m = ident_re.match(sig_text, i + 1)
            if m:
                pos = m.end()
                while pos < n and sig_text[pos].isspace():
                    pos += 1
                if pos < n and sig_text[pos] == ":":
                    name = m.group(0)
                    j = pos + 1
                    while j < n and sig_text[j].isspace():
                        j += 1
                    depth = 1
                    k = j
                    while k < n:
                        c = sig_text[k]
                        if c == open_ch:
                            depth += 1
                        elif c == closers[open_ch]:
                            depth -= 1
                            if depth == 0:
                                break
                        k += 1
                    ty = sig_text[j:k].strip()
                    if name and ty:
                        out.append((name, ty, k + 1))
                    i = k + 1
                    continue
            i += 1
            continue
        if sig_text[i] == "∀":
            m = re.match(r"∀\s*[\(\{\[]?\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*", sig_text[i:])
            if m:
                name = m.group(1)
                start = i + m.end()
                j = start
                depth = 0
                while j < n:
                    c = sig_text[j]
                    if c in "([{":
                        depth += 1
                    elif c in ")]}":
                        if depth == 0:
                            break
                        depth -= 1
                    elif depth == 0 and (c == "," or c == "→" or (c == "-" and j + 1 < n and sig_text[j + 1] == ">")):
                        break
                    j += 1
                ty = sig_text[start:j].strip()
                if name and ty:
                    out.append((name, ty, j))
                i = j if j > i else i + 1
                continue
            i += 1
            continue
        i += 1
    return out


def _scan_trivial_proofs(sol_clean: str) -> tuple[list[str], list[str]]:
    """Return ``(single_tactic_warnings, unused_hypothesis_warnings)`` for Solution.lean.

    The unused-hypothesis signal is purely lexical (it cannot tell that ``positivity`` /
    ``linarith`` / ``nlinarith`` consumed a hypothesis implicitly), so it is demoted to an
    informational list kept separate from the single-tactic warning channel (FMT-6).
    """
    tactic_warnings: list[str] = []
    unused_warnings: list[str] = []
    decl_re = re.compile(r"\b(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_']*)")
    decls = list(decl_re.finditer(sol_clean))
    end_marker_re = re.compile(r"\b(?:end|namespace)\s+[A-Za-z_][A-Za-z0-9_']*\b")
    for idx, dm in enumerate(decls):
        thm_name = dm.group(1)
        next_decl = decls[idx + 1].start() if idx + 1 < len(decls) else len(sol_clean)
        span = sol_clean[dm.end() : next_decl]
        # Find the theorem definition ':=' or 'where' at parenthesis depth 0
        depth = 0
        assign_idx = -1
        assign_len = 0
        i = 0
        while i < len(span):
            ch = span[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
            elif depth == 0:
                if span[i : i + 2] == ":=":
                    assign_idx = i
                    assign_len = 2
                    break
                if re.match(r"\bwhere\b", span[i:]):
                    assign_idx = i
                    assign_len = 5
                    break
            i += 1
        if assign_idx < 0:
            continue
        sig = span[:assign_idx]
        raw_body = span[assign_idx + assign_len :]
        end_m = end_marker_re.search(raw_body)
        body = (raw_body[: end_m.start()] if end_m else raw_body).strip()

        hyp_binders = _extract_hyp_binders(sig)
        hyp_names: list[str] = []
        for name, ty, _end in hyp_binders:
            if not name.startswith("_") and _PROP_TYPE_OP_RE.search(ty):
                hyp_names.append(name)

        closing_tactic = _extract_single_trivial_tactic(body)
        if closing_tactic and hyp_names:
            tactic_warnings.append(f"single_tactic_proof:{thm_name}:{closing_tactic}")

        for name, ty, end_pos in hyp_binders:
            if name.startswith("_") or not _PROP_TYPE_OP_RE.search(ty):
                continue
            usage_region = sig[end_pos:] + " " + body
            tok_re = re.compile(rf"\b{re.escape(name)}\b")
            if not tok_re.search(usage_region):
                unused_warnings.append(f"unused_hypothesis:{thm_name}:{name}")
    return tactic_warnings, unused_warnings


def _norm_lean_sig(sig: str) -> str:
    s = sig.replace("forall ", "∀ ").replace("->", "→")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*:\s*", ": ", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s*→\s*", " → ", s)
    return s


def extract_theorem_signatures(stripped_src: str) -> dict[str, str]:
    """Map declared theorem/lemma short names to normalized type signatures."""
    out: dict[str, str] = {}
    for m in _THEOREM_HEADER_RE.finditer(stripped_src):
        out[m.group(1)] = _norm_lean_sig(m.group(2))
    return out


_NS_OPEN_RE = re.compile(r"\bnamespace\s+([A-Za-z_][A-Za-z0-9_.']*)")
_NS_END_RE = re.compile(r"\bend\s+([A-Za-z_][A-Za-z0-9_.']*)?")


def _qualified_theorem_names(stripped_src: str) -> dict[str, str]:
    """Map theorem/lemma short names to their namespace-qualified names (nested namespaces supported)."""
    out: dict[str, str] = {}
    stack: list[str] = []
    events: list[tuple[int, int, str]] = []
    for m in _NS_OPEN_RE.finditer(stripped_src):
        events.append((m.start(), 0, m.group(1)))
    for m in _NS_END_RE.finditer(stripped_src):
        events.append((m.start(), 1, m.group(1) or ""))
    for m in _THEOREM_DECL_RE.finditer(stripped_src):
        events.append((m.start(), 2, m.group(1)))
    events.sort(key=lambda e: e[0])
    for _pos, kind, val in events:
        if kind == 0:  # namespace open
            stack.extend(seg for seg in val.split(".") if seg)
        elif kind == 1:  # end
            if val:
                parts = [seg for seg in val.split(".") if seg]
                for _ in parts:
                    if stack:
                        stack.pop()
            elif stack:
                stack.pop()
        else:  # theorem/lemma
            out[val] = ".".join(stack + [val]) if stack else val
    return out


def resolve_theorem_pairs(ch_clean: str, sol_clean: str) -> tuple[bool, list[str], list[str], list[tuple[str, str]]]:
    """Match every theorem declared in Challenge.lean to its proof theorem in Solution.lean.

    Returns ``(paired_ok, missing_errors, signature_warnings, pairs)`` where ``pairs`` holds
    ``(qualified_challenge_thm, qualified_solution_thm)`` tuples. ``paired_ok`` is False only
    when a Challenge theorem has no matching Solution theorem by name; a static signature
    difference is demoted to ``signature_warnings`` because the Lean kernel
    definitional-equality witness is the authoritative check (FMT-9).
    """
    ch_sigs = extract_theorem_signatures(ch_clean)
    sol_sigs = extract_theorem_signatures(sol_clean)
    ch_quals = _qualified_theorem_names(ch_clean)
    sol_quals = _qualified_theorem_names(sol_clean)
    if not ch_sigs:
        return True, [], [], []
    missing: list[str] = []
    sig_warnings: list[str] = []
    pairs: list[tuple[str, str]] = []
    for name, ch_sig in ch_sigs.items():
        sol_short: str | None = None
        if name in sol_sigs:
            sol_short = name
        elif f"{name}_proof" in sol_sigs:
            sol_short = f"{name}_proof"
        if sol_short is None:
            missing.append(f"Challenge theorem '{name}' has no matching proof theorem in Solution.lean")
            continue
        if sol_sigs[sol_short] != ch_sig:
            sig_warnings.append(
                f"theorem '{sol_short}' signature differs from Challenge '{name}': Challenge '{ch_sig}' vs Solution '{sol_sigs[sol_short]}'"
            )
        ch_qual = ch_quals.get(name, name)
        sol_qual = sol_quals.get(sol_short, sol_short)
        pairs.append((ch_qual, sol_qual))
    return len(missing) == 0, missing, sig_warnings, pairs


def check_statement_pairing(ch_clean: str, sol_clean: str) -> tuple[bool, list[str]]:
    """Verify that Solution.lean proves every theorem stated in Challenge.lean with a matching signature."""
    ok, errs, _sig_warns, _ = resolve_theorem_pairs(ch_clean, sol_clean)
    return ok, errs


def scan_lean_hazards(challenge_src: str, solution_src: str) -> dict[str, Any]:
    """Deterministically scan Challenge.lean and Solution.lean for escape hatches and vacuous statements."""
    ch_clean, ch_bal = _strip_with_state(challenge_src)
    sol_clean, sol_bal = _strip_with_state(solution_src)

    sol_hazards: list[str] = []
    ch_hazards: list[str] = []
    if not ch_bal:
        ch_hazards.append("unterminated_comment_or_string")
    if not sol_bal:
        sol_hazards.append("unterminated_comment_or_string")

    for label, pat in _SOLUTION_HAZARD_PATTERNS:
        if pat.search(sol_clean):
            sol_hazards.append(label)
    for label, pat in _CHALLENGE_HAZARD_PATTERNS:
        if pat.search(ch_clean):
            ch_hazards.append(label)

    vacuous: list[str] = []
    for label, pat in _VACUOUS_PATTERNS:
        if pat.search(ch_clean):
            vacuous.append(label)

    sol_sorries = len(re.findall(r"\bsorry\b", sol_clean))
    ch_sorries = len(re.findall(r"\bsorry\b", ch_clean))
    ch_theorems = _THEOREM_DECL_RE.findall(ch_clean)
    sol_theorems = _THEOREM_DECL_RE.findall(sol_clean)

    # P-07: If Challenge.lean uses `sorry` on a theorem, Solution.lean may never reference `Challenge.<thm>`
    if ch_sorries > 0:
        for thm in ch_theorems:
            if re.search(rf"\bChallenge\.{re.escape(thm)}\b", sol_clean):
                sol_hazards.append(f"references_challenge_sorry:{thm}")

    all_theorems = list(dict.fromkeys(ch_theorems + sol_theorems))
    tactic_warnings, unused_warnings = _scan_trivial_proofs(sol_clean)
    clean = not sol_hazards and not ch_hazards and not vacuous
    return {
        "theorem_names": all_theorems,
        "challenge_theorems": ch_theorems,
        "solution_theorems": sol_theorems,
        "sorries": sol_sorries,
        "challenge_sorries": ch_sorries,
        "solution_hazards": sol_hazards,
        "challenge_hazards": ch_hazards,
        "vacuous_or_trivial": vacuous,
        "trivial_proof_warnings": tactic_warnings,
        "unused_hypothesis_warnings": unused_warnings,
        "clean": clean,
    }


def _sanitize_lean_fragment(text: str, field: str) -> str:
    """Refuse ``-/`` (closes a block comment) and ``--`` (starts a line comment) in interpolated text.

    These sequences, if interpolated into a generated Lean artifact, can close a block comment
    or comment out the rest of a line and inject arbitrary Lean (FMT-10). Newlines are also
    refused so a single-line scaffold cannot be split into injected declarations.
    """
    s = str(text)
    if "-/" in s or "--" in s or "\n" in s or "\r" in s:
        raise FormalError(f"{field} contains a forbidden `-/`, `--`, or newline sequence; refusing to scaffold.")
    return s


def init_project(
    appendix: Path,
    slug: str,
    *,
    theorem_name: str = "main_claim",
    statement: str = "(n : Nat) : n + 0 = n",
    from_conjecture: str | None = None,
    toolchain: str = DEFAULT_TOOLCHAIN,
    mathlib: bool = False,
) -> Path:
    """Create appendix/formal/<slug>/ in the anthropics/formal-math Challenge/Solution layout."""
    clean_slug = _validate_slug(slug)
    if not _IDENT_RE.fullmatch(theorem_name):
        raise FormalError(f"Invalid Lean theorem identifier {theorem_name!r}.")

    appendix = Path(appendix)
    proj = appendix / "formal" / clean_slug
    proj.mkdir(parents=True, exist_ok=True)

    conj_comment = ""
    if from_conjecture is not None:
        conj_file = appendix / CONJECTURES_JSON
        if not conj_file.is_file():
            raise FormalError(f"Cannot bridge --from-conjecture={from_conjecture!r}: {conj_file} not found.")
        try:
            conj_data = json.loads(conj_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FormalError(f"Unreadable {conj_file}: {exc}") from exc
        cands = conj_data.get("candidates") if isinstance(conj_data, dict) else []
        chosen = None
        if isinstance(cands, list) and cands:
            chosen = (
                cands[0]
                if from_conjecture == "top"
                else next((c for c in cands if isinstance(c, dict) and c.get("id") == from_conjecture), None)
            )
        if not isinstance(chosen, dict):
            raise FormalError(f"Conjecture {from_conjecture!r} not found in {conj_file}.")
        expr = _sanitize_lean_fragment(chosen.get("expr") or "", "conjecture expr")
        cid = _sanitize_lean_fragment(chosen.get("id") or "", "conjecture id")
        exps = json.dumps(chosen.get("exponents") or {}, sort_keys=True)
        conj_comment = (
            f"/- Bridged from appendix/conjectures.json candidate {cid}\n"
            f"   Conjectured law: {expr}\n"
            f"   Exponents: {exps}\n"
            f"   State the deductive theorem under explicit domain hypotheses in Challenge.{theorem_name},\n"
            f"   then prove the identical statement without `sorry` in Solution.{theorem_name}.\n"
            f"-/\n\n"
        )

    (proj / "lean-toolchain").write_text(toolchain.strip() + "\n", encoding="utf-8")
    mathlib_block = (
        '\n[[require]]\nname = "mathlib"\ngit = "https://github.com/leanprover-community/mathlib4.git"\n'
        if mathlib
        else ""
    )
    lakefile = (
        f'name = "{clean_slug}"\n'
        'defaultTargets = ["Challenge", "Solution"]\n\n'
        "[[lean_lib]]\n"
        'name = "Challenge"\n\n'
        "[[lean_lib]]\n"
        f'name = "Solution"\n{mathlib_block}'
    )
    (proj / "lakefile.toml").write_text(lakefile, encoding="utf-8")

    sig = _sanitize_lean_fragment(statement.strip(), "statement")
    if not sig.startswith(("(", "{", "[", ":")):
        sig = f": {sig}"

    challenge_lean = (
        f"{conj_comment}"
        "-- Target theorem statement (`sorry` is permitted ONLY here in Challenge.lean as the open problem stub)\n"
        "namespace Challenge\n\n"
        f"theorem {theorem_name} {sig} := by sorry\n\n"
        "end Challenge\n"
    )
    default_proof = "Nat.add_zero n" if sig == "(n : Nat) : n + 0 = n" else "by rfl"
    solution_lean = (
        "import Challenge\n\n"
        "-- Machine-checked proof (`0` `sorry`, standard axioms only; verified for type equality against Challenge)\n"
        "namespace Solution\n\n"
        f"theorem {theorem_name} {sig} :=\n"
        f"  {default_proof}\n\n"
        "end Solution\n"
    )
    readme_md = (
        f"# Formal Verification Workspace: `{clean_slug}`\n\n"
        "Layout modeled on `anthropics/formal-math`:\n"
        "- `Challenge.lean`: formal target statement (`namespace Challenge`; `sorry` permitted only as problem placeholder).\n"
        "- `Solution.lean`: machine-checked proof (`namespace Solution`; `0` `sorry`, standard axioms only, kernel-checked to inhabit `Challenge`'s exact theorem type).\n"
        f"- Toolchain: `{toolchain.strip()}` ({'with Mathlib dependency' if mathlib else 'standalone Core/Std; pass --mathlib when Mathlib4 is required'}).\n"
        f"- Verify locally: `python3 -B <skill-dir>/scripts/formal_math.py check {clean_slug}`\n"
    )
    (proj / "Challenge.lean").write_text(challenge_lean, encoding="utf-8")
    (proj / "Solution.lean").write_text(solution_lean, encoding="utf-8")
    (proj / "README.md").write_text(readme_md, encoding="utf-8")
    return proj


_AXIOMS_LIST_RE = re.compile(r"'([^']+)'\s+depends on axioms:\s*\[([^\]]*)\]")
_AXIOMS_NONE_RE = re.compile(r"'([^']+)'\s+does not depend on any axioms")


def _upsert_formal_proofs_csv(csv_path: Path, row: dict[str, str]) -> None:
    existing: list[dict[str, str]] = []
    if csv_path.is_file():
        try:
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                existing = list(csv.DictReader(fh))
        except (OSError, csv.Error):
            existing = []
    replaced = False
    out_rows: list[dict[str, str]] = []
    for r in existing:
        if (r.get("slug") or "").strip() == row["slug"]:
            if not row.get("proof_id") and r.get("proof_id"):
                row["proof_id"] = r["proof_id"]
            out_rows.append(row)
            replaced = True
        else:
            out_rows.append(r)
    if not replaced:
        if not row.get("proof_id"):
            max_num = 0
            for r in existing:
                m = re.match(r"^F(\d+)$", (r.get("proof_id") or "").strip())
                if m:
                    max_num = max(max_num, int(m.group(1)))
            row["proof_id"] = f"F{max_num + 1}"
        out_rows.append(row)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = csv_path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FORMAL_PROOF_COLS), extrasaction="ignore", restval="", lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    tmp.replace(csv_path)


def _write_comparator_config(proj: Path, theorem_names: list[str]) -> None:
    """Write a `leanprover/comparator` config file for optional manual comparator verification."""
    config = {
        "challenge_module": "Challenge",
        "solution_module": "Solution",
        "theorem_names": list(dict.fromkeys(t for t in theorem_names if t)),
        "permitted_axioms": sorted(STANDARD_LEAN_AXIOMS),
    }
    (proj / "comparator.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def check_project(
    appendix: Path,
    slug: str,
    *,
    proof_id: str = "",
    timeout: int = 300,
    env: Mapping[str, str] | None = None,
    register_tier: str | None = None,
) -> dict[str, Any]:
    """Audit Challenge/Solution hazards, verify statement equivalence, and run Lean kernel or comparator."""
    env = formal_env() if env is None else env
    clean_slug = _validate_slug(slug)
    appendix = Path(appendix)
    proj = appendix / "formal" / clean_slug
    ch_path = proj / "Challenge.lean"
    sol_path = proj / "Solution.lean"
    if not ch_path.is_file() or not sol_path.is_file():
        raise FormalError(f"Formal project {proj} must contain both Challenge.lean and Solution.lean.")

    ch_src = ch_path.read_text(encoding="utf-8")
    sol_src = sol_path.read_text(encoding="utf-8")
    ch_sha = _sha256_file(ch_path)
    sol_sha = _sha256_file(sol_path)
    tc_path = proj / "lean-toolchain"
    toolchain = tc_path.read_text(encoding="utf-8").strip() if tc_path.is_file() else "unknown"

    ch_clean, _ = _strip_with_state(ch_src)
    sol_clean, _ = _strip_with_state(sol_src)
    hazards = scan_lean_hazards(ch_src, sol_src)
    paired_ok, pair_errors, sig_warnings, thm_pairs = resolve_theorem_pairs(ch_clean, sol_clean)

    sol_has_ns = bool(re.search(r"\bnamespace\s+Solution\b", sol_clean))
    target_theorems = hazards["challenge_theorems"] or hazards["solution_theorems"]
    primary_thm = target_theorems[0] if target_theorems else "main_claim"

    lake_bin, lean_bin = find_lake(env)
    comp_bin = find_comparator(env)
    landrun_bin = find_landrun(env)

    lean_version = ""
    verification_mode = "none"
    axioms_used: list[str] = []
    sorries = int(hazards["sorries"])
    build_stderr = ""

    if not paired_ok:
        status = "failed_statement_mismatch"
        build_stderr = "; ".join(pair_errors)
    elif not hazards["clean"]:
        status = "failed_hazards"
    elif not hazards["challenge_theorems"]:
        status = "failed_no_theorem"
        build_stderr = "Challenge.lean declares no theorem or lemma to verify."
    elif lake_bin is None:
        status = "unverified_no_toolchain"
    else:
        run_env = dict(env)
        run_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        if os.name == "nt":
            for _win_key in ("SYSTEMROOT", "COMSPEC"):
                if _win_key not in run_env:
                    _win_val = os.environ.get(_win_key)
                    if _win_val:
                        run_env[_win_key] = _win_val
        # P-05: Block git network fetches inside `lake build` when HEURISMA_OFFLINE=1
        is_offline = str(env.get("HEURISMA_OFFLINE", os.environ.get("HEURISMA_OFFLINE", ""))).strip().lower() in ("1", "true", "yes")
        if is_offline:
            run_env["GIT_TERMINAL_PROMPT"] = "0"
            run_env["GIT_CONFIG_COUNT"] = "1"
            run_env["GIT_CONFIG_KEY_0"] = "protocol.allow"
            run_env["GIT_CONFIG_VALUE_0"] = "never"

        if lean_bin is not None:
            try:
                ver_proc = subprocess.run(
                    [str(lean_bin), "--version"],
                    cwd=proj,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=15,
                    env=run_env,
                    check=False,
                )
                ver_out = (ver_proc.stdout or ver_proc.stderr).strip()
                lean_version = ver_out.splitlines()[0] if ver_out else "unknown"
            except (OSError, subprocess.SubprocessError):
                lean_version = "unknown"
        else:
            lean_version = "unknown"

        with tempfile.TemporaryDirectory() as tmp_lean:
            run_env["TMPDIR"] = tmp_lean
            sandbox = [str(landrun_bin), "--ro", "/", "--rw", str(proj), "--rw", tmp_lean] if landrun_bin is not None else []
            build_cmd = sandbox + [str(lake_bin), "build"]
            try:
                b_proc = subprocess.run(
                    build_cmd,
                    cwd=proj,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=timeout,
                    env=run_env,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                b_proc = None
                status = "failed_timeout"
                build_stderr = f"lake build timed out after {timeout}s"
            except (OSError, subprocess.SubprocessError) as exc:
                b_proc = None
                status = "failed_build"
                build_stderr = f"lake build subprocess failed: {exc}"

            if b_proc is not None:
                if b_proc.returncode != 0:
                    status = "failed_build"
                    build_stderr = (b_proc.stderr or b_proc.stdout or "").strip()[-400:]
                else:
                    # P-01: Emit kernel definitional-equality witness `_heurisma_same_stmt (@<chal>) (@<sol>)`
                    audit_file = proj / "_HeurismaAxiomAudit.lean"
                    audit_lines = [
                        "import Challenge",
                        "import Solution",
                        "def _heurisma_same_stmt {P : Prop} (_ : P) (proof : P) : P := proof",
                    ]
                    sol_thms = hazards["solution_theorems"] or [primary_thm]
                    if thm_pairs:
                        for p_idx, (ch_qual, sol_qual) in enumerate(thm_pairs, start=1):
                            audit_lines.append(
                                f"def _heurisma_witness_{p_idx} := _heurisma_same_stmt (@{ch_qual}) (@{sol_qual})"
                            )
                            audit_lines.append(f"#print axioms {sol_qual}")
                    else:
                        for t_name in sol_thms:
                            qual = f"Solution.{t_name}" if sol_has_ns else t_name
                            audit_lines.append(f"#print axioms {qual}")

                    audit_file.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
                    ax_proc: Any = None
                    try:
                        lean_arg = str(lean_bin) if lean_bin is not None else "lean"
                        ax_cmd = sandbox + [str(lake_bin), "env", lean_arg, str(audit_file.name)]
                        ax_proc = subprocess.run(
                            ax_cmd,
                            cwd=proj,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            timeout=min(timeout, 60),
                            env=run_env,
                            check=False,
                        )
                    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
                        ax_proc = None
                        status = "failed_axioms"
                        build_stderr = f"axiom audit subprocess failed: {exc}"
                    finally:
                        audit_file.unlink(missing_ok=True)

                    if ax_proc is not None:
                        combined_out = (ax_proc.stdout or "") + "\n" + (ax_proc.stderr or "")
                        parsed_any = False
                        collected_ax: list[str] = []
                        for m_list in _AXIOMS_LIST_RE.finditer(combined_out):
                            parsed_any = True
                            for tok in m_list.group(2).split(","):
                                a = tok.strip()
                                if a and a not in collected_ax:
                                    collected_ax.append(a)
                        if _AXIOMS_NONE_RE.search(combined_out):
                            parsed_any = True
                        axioms_used = collected_ax

                        if ax_proc.returncode != 0 or not parsed_any:
                            status = "failed_axioms"
                            build_stderr = combined_out.strip()[-400:]
                        else:
                            non_std = [a for a in axioms_used if a not in STANDARD_LEAN_AXIOMS]
                            if "sorryAx" in axioms_used:
                                sorries = max(sorries, 1)
                            if non_std:
                                status = "failed_axioms"
                            else:
                                _write_comparator_config(proj, hazards["challenge_theorems"])
                                if comp_bin is not None and (proj / "comparator.json").is_file():
                                    try:
                                        c_cmd = sandbox + [str(comp_bin), str(proj / "comparator.json")]
                                        c_proc = subprocess.run(
                                            c_cmd,
                                            cwd=proj,
                                            capture_output=True,
                                            text=True,
                                            encoding="utf-8",
                                            timeout=min(timeout, 120),
                                            env=run_env,
                                            check=False,
                                        )
                                    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
                                        verification_mode = "comparator"
                                        status = "failed_comparator"
                                        build_stderr = f"comparator subprocess failed: {exc}"
                                    else:
                                        if c_proc.returncode == 0:
                                            verification_mode = "comparator"
                                            status = "comparator-verified"
                                        else:
                                            verification_mode = "comparator"
                                            status = "failed_comparator"
                                            build_stderr = (c_proc.stderr or c_proc.stdout or "").strip()[-400:]
                                else:
                                    verification_mode = "kernel-defeq"
                                    status = "kernel-verified"

    # FMT-13: enforce the tier/status ceiling BEFORE any registry side effect so `--register` is atomic.
    if register_tier is not None:
        if register_tier not in VALID_TIERS:
            raise FormalError(f"Invalid tier {register_tier!r}; use one of {', '.join(VALID_TIERS)}.")
        if status not in ("kernel-verified", "comparator-verified") and register_tier != "Tier 3":
            raise FormalError(
                f"Formal project '{clean_slug}' has status={status!r} and cannot be registered as {register_tier}; "
                f"only 'kernel-verified' or 'comparator-verified' proofs (0 sorry in Solution.lean, standard axioms) can exceed Tier 3 ([Preliminary])."
            )

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    verify_record: dict[str, Any] = {
        "slug": clean_slug,
        "theorem_name": primary_thm,
        "challenge_sha256": ch_sha,
        "solution_sha256": sol_sha,
        "toolchain": toolchain,
        "lean_version": lean_version,
        "verification_mode": verification_mode,
        "status": status,
        "sorries": sorries,
        "challenge_sorries": int(hazards["challenge_sorries"]),
        "axioms": axioms_used,
        "statement_paired": paired_ok,
        "signature_warnings": sig_warnings,
        "hazards": {
            "solution_hazards": hazards["solution_hazards"],
            "challenge_hazards": hazards["challenge_hazards"],
            "vacuous_or_trivial": hazards["vacuous_or_trivial"],
            "trivial_proof_warnings": hazards["trivial_proof_warnings"],
            "unused_hypothesis_warnings": hazards["unused_hypothesis_warnings"],
        },
        "verified_utc": now_utc,
    }
    if build_stderr:
        verify_record["diagnostics"] = build_stderr

    (proj / "verify.json").write_text(
        json.dumps(verify_record, indent=1, allow_nan=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    csv_row = {
        "proof_id": proof_id,
        "slug": clean_slug,
        "theorem_name": primary_thm,
        "challenge_file": f"appendix/formal/{clean_slug}/Challenge.lean",
        "challenge_sha256": ch_sha,
        "solution_file": f"appendix/formal/{clean_slug}/Solution.lean",
        "solution_sha256": sol_sha,
        "toolchain": toolchain,
        "lean_version": lean_version,
        "verification_mode": verification_mode,
        "status": status,
        "sorries": str(sorries),
        "axioms": ";".join(axioms_used),
        "verified_utc": now_utc,
    }
    _upsert_formal_proofs_csv(appendix / FORMAL_PROOFS_CSV, csv_row)
    verify_record["proof_id"] = csv_row["proof_id"]
    return verify_record


def register_formal_source(
    appendix: Path,
    slug: str,
    *,
    sources_csv: Path,
    claim_id: str = "F1",
    tier: str = "Tier 1",
    selection: str | None = None,
    as_of: str | None = None,
) -> dict[str, str]:
    """Register a verified formal proof into appendix/sources.csv (enforcing kernel/comparator ceiling)."""
    clean_slug = _validate_slug(slug)
    if tier not in VALID_TIERS:
        raise FormalError(f"Invalid tier {tier!r}; use one of {', '.join(VALID_TIERS)}.")
    appendix = Path(appendix)
    proj = appendix / "formal" / clean_slug
    verify_path = proj / "verify.json"
    sol_path = proj / "Solution.lean"
    ch_path = proj / "Challenge.lean"
    if not verify_path.is_file() or not sol_path.is_file() or not ch_path.is_file():
        raise FormalError(f"Run `formal_math.py check {clean_slug}` before registering in sources.csv.")

    verify_data = json.loads(verify_path.read_text(encoding="utf-8"))
    if _sha256_file(sol_path) != verify_data.get("solution_sha256") or _sha256_file(ch_path) != verify_data.get("challenge_sha256"):
        raise FormalError(f"Challenge.lean or Solution.lean changed since verify.json was stamped; re-run `formal_math.py check {clean_slug}`.")

    status = str(verify_data.get("status") or "")
    if status not in ("kernel-verified", "comparator-verified") and tier != "Tier 3":
        raise FormalError(
            f"Formal project '{clean_slug}' has status={status!r} and cannot be registered as {tier}; "
            f"only 'kernel-verified' or 'comparator-verified' proofs (0 sorry in Solution.lean, standard axioms) can exceed Tier 3 ([Preliminary])."
        )

    reg_csv = appendix / FORMAL_PROOFS_CSV
    if reg_csv.is_file():
        with reg_csv.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            if (r.get("slug") or "").strip() == clean_slug:
                r["proof_id"] = claim_id
                _upsert_formal_proofs_csv(reg_csv, r)
                break

    sol_sha_full = str(verify_data["solution_sha256"])
    sol_sha12 = sol_sha_full[:12]
    today = as_of or date.today().isoformat()
    now_utc = str(verify_data.get("verified_utc") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    rel_url = f"appendix/formal/{clean_slug}/Solution.lean"
    mode_tag = str(verify_data.get("verification_mode") or "kernel-defeq")
    row_out: dict[str, str] = {
        "claim_id": claim_id,
        "source_title": f"Lean 4 formal proof {clean_slug} ({verify_data.get('theorem_name', 'main_claim')}, {mode_tag}, sha256 {sol_sha12})",
        "url": rel_url,
        "tier": tier,
        "accessed_date": today[:10],
        "data_as_of": today[:7],
        "kind": "formal-proof",
        "sha256": sol_sha_full,
        "selection": selection or "agent-fetched",
        "retrieved_utc": now_utc,
    }

    existing_src: list[dict[str, str]] = []
    cols = list(SOURCE_COLS)
    if sources_csv.is_file() and sources_csv.stat().st_size > 0:
        with sources_csv.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            cols = list(reader.fieldnames or SOURCE_COLS)
            for req_c in ("kind", "sha256"):
                if req_c not in cols:
                    cols.append(req_c)
            existing_src = list(reader)
    existing_src = [r for r in existing_src if (r.get("claim_id") or "").strip() != claim_id]
    existing_src.append(row_out)

    sources_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = sources_csv.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", restval="", lineterminator="\n")
        w.writeheader()
        w.writerows(existing_src)
    tmp.replace(sources_csv)
    return row_out


def fetch_reference(
    appendix: Path,
    ref_spec: str,
    *,
    branch: str = "main",
    files: tuple[str, ...] = DEFAULT_REF_FILES,
    env: Mapping[str, str] | None = None,
) -> list[Path]:
    """Fetch read-only reference files (e.g. 'anthropics/formal-math/eth') via fetch_lib with SHA-256 logging."""
    env = formal_env() if env is None else env
    spec = (ref_spec or "").strip().strip("/")
    parts = [p for p in spec.split("/") if p]
    if len(parts) < 2 or any(p in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        raise FormalError(
            f"Invalid reference spec {ref_spec!r}; expected '<owner>/<repo>[/<subpath>]' (e.g. 'anthropics/formal-math/eth')."
        )
    owner, repo = parts[0], parts[1]
    subpath = "/".join(parts[2:])
    ref_slug = "_".join(parts[2:]) if len(parts) > 2 else f"{owner}_{repo}"

    branch = (branch or "").strip()
    if not branch or not re.fullmatch(r"[A-Za-z0-9_.-]+", branch):
        raise FormalError(f"Invalid branch/tag {branch!r}; use only ASCII letters, digits, '_', '.', or '-'.")

    raw_override = (env.get("HEURISMA_GITHUB_RAW_URL") or "").strip().rstrip("/")
    base_url = raw_override or "https://raw.githubusercontent.com"
    allowed_hosts: tuple[str, ...] = ()
    if raw_override:
        parsed = urlparse(raw_override)
        parsed_host = parsed.hostname
        if parsed.scheme not in ("http", "https"):
            raise FormalError(f"HEURISMA_GITHUB_RAW_URL must use http(s); got {raw_override!r}.")
        if not parsed_host:
            raise FormalError(f"HEURISMA_GITHUB_RAW_URL has no host: {raw_override!r}.")
        if fetch_lib._is_private_host(parsed_host):
            raise FormalError(f"HEURISMA_GITHUB_RAW_URL host {parsed_host!r} is private/loopback; refused.")
        allowed_hosts = (parsed_host,)

    appendix = Path(appendix)
    offline_in_env = str(env.get("HEURISMA_OFFLINE", "")).strip().lower() in ("1", "true", "yes")
    saved_paths: list[Path] = []

    for fname in files:
        if "/" in fname or "\\" in fname or fname in ("", ".", ".."):
            raise FormalError(f"Invalid reference file name {fname!r}.")
        rel_dest = f"formal_refs/{ref_slug}/{fname}"
        url_tail = f"{subpath}/{fname}" if subpath else fname
        url = f"{base_url}/{owner}/{repo}/{branch}/{url_tail}"
        if offline_in_env and not local_data.offline_enabled():
            local_data.append_attempt(
                appendix / "data_attempts.csv",
                f"formal-ref:{spec}/{fname}",
                f"{owner}/{repo}",
                f"GET {fetch_lib.scrub_url(url)}",
                "offline mode",
                failure_reason="network disabled by HEURISMA_OFFLINE=1",
            )
            continue
        dest = fetch_lib.fetch(
            f"formal-ref:{spec}/{fname}",
            f"{owner}/{repo}",
            url,
            rel_dest,
            appendix,
            retries=1,
            backoff=0.2,
            allow_private=False,
            allowed_hosts=allowed_hosts,
        )
        if dest is not None:
            saved_paths.append(dest)
    return saved_paths


def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Scaffold, verify, and register Lean 4 / Lake formal proofs (anthropics/formal-math layout)."
    )
    parser.add_argument("--version", action="version", version=f"formal_math.py {__version__}")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_init = sub.add_parser("init", help="Initialize appendix/formal/<slug>/ Lake project.")
    p_init.add_argument("slug", help="Project directory slug under appendix/formal/.")
    p_init.add_argument("--appendix", type=Path, default=Path("appendix"), help="Appendix directory.")
    p_init.add_argument("--theorem-name", default="main_claim", help="Primary theorem identifier.")
    p_init.add_argument("--statement", default="(n : Nat) : n + 0 = n", help="Formal signature stub.")
    p_init.add_argument("--from-conjecture", default=None, help="Conjecture ID in appendix/conjectures.json (or 'top').")
    p_init.add_argument("--toolchain", default=DEFAULT_TOOLCHAIN, help="Lean toolchain string.")
    p_init.add_argument("--mathlib", action="store_true", help="Add Mathlib4 dependency block to lakefile.toml.")

    p_chk = sub.add_parser("check", help="Scan Lean hazards and run optional local lake/lean/comparator verification.")
    p_chk.add_argument("slug", help="Project slug under appendix/formal/.")
    p_chk.add_argument("--appendix", type=Path, default=Path("appendix"), help="Appendix directory.")
    p_chk.add_argument("--timeout", type=int, default=300, help="Build timeout in seconds.")
    p_chk.add_argument("--require-kernel", action="store_true", help="Exit non-zero (2) if lake/lean is not installed.")
    p_chk.add_argument("--register", action="store_true", help="Also register the proof in sources.csv.")
    p_chk.add_argument("--sources", type=Path, default=None, help="Path to sources.csv (default: <appendix>/sources.csv).")
    p_chk.add_argument("--claim", default="F1", help="claim_id for sources.csv registration.")
    p_chk.add_argument(
        "--tier",
        default=None,
        help="Tier for sources.csv registration (default: 'Tier 1' if kernel-verified, 'Tier 3' if unverified_no_toolchain).",
    )
    p_chk.add_argument("--json", action="store_true", help="Emit verify.json payload to stdout.")

    p_ref = sub.add_parser("fetch-ref", help="Download read-only reference files (e.g. anthropics/formal-math/eth).")
    p_ref.add_argument("ref_spec", help="Repository spec '<owner>/<repo>[/<subpath>]'.")
    p_ref.add_argument("--appendix", type=Path, default=Path("appendix"), help="Appendix directory.")
    p_ref.add_argument("--branch", default="main", help="Git branch or tag.")
    p_ref.add_argument("--files", default=",".join(DEFAULT_REF_FILES), help="Comma-separated filenames to fetch.")

    args = parser.parse_args(argv)
    try:
        if args.subcommand == "init":
            proj = init_project(
                args.appendix,
                args.slug,
                theorem_name=args.theorem_name,
                statement=args.statement,
                from_conjecture=args.from_conjecture,
                toolchain=args.toolchain,
                mathlib=args.mathlib,
            )
            print(f"Initialized formal workspace: {proj}")
            return 0

        if args.subcommand == "check":
            if args.timeout <= 0:
                raise FormalError("--timeout must be a positive number of seconds.")
            res = check_project(
                args.appendix,
                args.slug,
                proof_id=args.claim if args.register else "",
                timeout=args.timeout,
                register_tier=args.tier if args.register else None,
            )
            if args.register:
                eff_tier = args.tier
                if eff_tier is None:
                    eff_tier = "Tier 3" if res["status"] == "unverified_no_toolchain" else "Tier 1"
                src_csv = args.sources or (args.appendix / "sources.csv")
                register_formal_source(args.appendix, args.slug, sources_csv=src_csv, claim_id=args.claim, tier=eff_tier)
            if args.json:
                print(json.dumps(res, indent=1, allow_nan=False, ensure_ascii=False))
            else:
                print(
                    f"formal_math check '{args.slug}': status={res['status']} mode={res['verification_mode']} "
                    f"sorries={res['sorries']} axioms={res['axioms']}"
                )
            if res["status"] == "unverified_no_toolchain":
                print(
                    "Note: Lean 4 (`lake`/`lean`) is not installed locally; recorded status='unverified_no_toolchain' (capped at Tier 3 / [Preliminary]).",
                    file=sys.stderr,
                )
                return 2
            return 0 if res["status"] in ("kernel-verified", "comparator-verified") else 1

        if args.subcommand == "fetch-ref":
            flist = tuple(f.strip() for f in args.files.split(",") if f.strip())
            saved = fetch_reference(args.appendix, args.ref_spec, branch=args.branch, files=flist)
            print(f"Fetched {len(saved)} reference file(s) under {args.appendix / 'data' / 'formal_refs'}.")
            return 0
    except FormalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
