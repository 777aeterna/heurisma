"""Preregistration checks: sealing, files added after sealing, and HARKing."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contracts import WITHHELD_MANIFEST
from checks.common import (
    _extract_section_slice,
    _file_sha256,
    _norm_text,
    _parse_utc,
)
from checks.provenance import (
    _download_proof,
)


def _files_added_after_prereg(report_dir: Path, rec: dict[str, Any]) -> list[str]:
    """Files in appendix/data/ absent from the sealed ``known_artifacts`` and from download_log.csv / intake.md."""
    known = rec.get("known_artifacts")
    data_dir = report_dir / "appendix" / "data"
    if not isinstance(known, dict) or not data_dir.is_dir():
        return []  # a preregistration sealed before known_artifacts existed has nothing to compare against
    _, saved_names, saved_shas = _download_proof(report_dir, include_attempts=False)
    try:
        intake = (report_dir / "appendix" / "intake.md").read_text(encoding="utf-8")
    except OSError:
        intake = ""
    out: list[str] = []
    for fp in sorted(data_dir.rglob("*"), key=lambda q: q.relative_to(data_dir).parts):
        if not fp.is_file() or "__pycache__" in fp.parts or fp.suffix == ".pyc":
            continue
        rel = fp.relative_to(report_dir / "appendix").as_posix()
        if rel == WITHHELD_MANIFEST:
            continue  # written when a copy is prepared for redistribution, not research data
        digest = _file_sha256(fp)[:12]
        if rel in known or fp.name in saved_names or digest in saved_shas:
            continue
        if intake and (fp.name in intake or digest in intake):
            continue
        out.append(rel)
    return out


_NUM_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*")
_DATE_VALUE_RE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")
_HARK_IGNORED = {"0.01", "0.05", "0.1", "1", "5", "95", "99", "100"}  # conventional thresholds, never a finding


def _plain_readings(token: str) -> set[str]:
    """The numeric values (as plain ``1234.5`` strings) a token may mean: a comma is a decimal point or, when it
    groups exactly three digits, a thousands separator; with both separators the last one is the decimal."""
    if "," in token and "." in token:
        return {token.replace(".", "").replace(",", ".")} if token.rfind(",") > token.rfind(".") else {token.replace(",", "")}
    if "," in token:
        out = {token.replace(",", ".")}
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", token):
            out.add(token.replace(",", ""))
        return out
    return {token}


_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ",
    "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "phi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
}
_GREEK_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(sorted(_GREEK, key=len, reverse=True)) + r")(?![A-Za-z])", re.IGNORECASE)
_SYMBOLS = (("<->", "↔"), ("->", "→"), ("<-", "←"), ("<=", "≤"), (">=", "≥"), ("!=", "≠"), ("+/-", "±"), ("−", "-"))


def _norm_hypothesis(text: str) -> str:
    """A hypothesis' wording with notation normalised, so an ASCII preregistration (``N->inf``, ``chi_max``, ``<=``) and
    the Unicode of Section 2 (``N→∞``, ``χ_max``, ``≤``) compare equal; words that merely contain a Greek name stay as they are."""
    out = text
    for ascii_form, symbol in _SYMBOLS:
        out = out.replace(ascii_form, symbol)
    out = re.sub(r"(?<![A-Za-z])(?:infinity|inf)(?![A-Za-z])", "∞", out, flags=re.IGNORECASE)
    out = _GREEK_RE.sub(lambda m: _GREEK[m.group(1).lower()], out)  # before _norm_text, which drops the "_" of chi_max
    return re.sub(r"\s*([→←↔≤≥≠±])\s*", r" \1 ", _norm_text(out)).strip()


def _canon_number(text: str) -> str:
    return text.rstrip("0").rstrip(".") if "." in text else text


def _rounded_forms(value: Any) -> set[str]:
    """Every way an author may quote a computed value: exact, and rounded to 0, 1 and 2 decimals (sign and unit
    dropped, ``.`` as the decimal mark). A bare integer (a count such as 16 sites) has no forms: it is not a result."""
    forms: set[str] = set()
    for token in _NUM_TOKEN_RE.findall(str(value).replace("−", "-")):
        if token.isdigit():
            continue
        for reading in _plain_readings(token):
            try:
                x = float(reading)
            except ValueError:
                continue
            forms.add(_canon_number(reading))
            for places in (0, 1, 2):
                forms.add(_canon_number(f"{round(x, places):.{places}f}"))
    return forms


def _hypothesis_number_hits(hyp_text: str, numbers_data: dict[str, Any]) -> list[str]:
    """Figures of a hypothesis that equal (exactly or rounded) a computed value of numbers.json.

    Needs two distinct figures, at least one non-integer: one threshold ("below 5%") or two round numbers
    ("30% and 10%") are legitimate predictions. Years, conventional thresholds and date values are ignored."""
    forms: set[str] = set()
    for value in numbers_data.values():
        if not _DATE_VALUE_RE.fullmatch(str(value).strip()):
            forms |= _rounded_forms(value)
    hits: set[str] = set()
    for token in _NUM_TOKEN_RE.findall(hyp_text.replace("−", "-")):
        if re.fullmatch(r"(?:19|20)\d\d", token):
            continue
        for reading in _plain_readings(token):
            norm = _canon_number(reading)
            if norm not in _HARK_IGNORED and norm in forms:
                hits.add(norm)
    return sorted(hits) if len(hits) >= 2 and any("." in h for h in hits) else []


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
    for rel in _files_added_after_prereg(report_dir, rec):
        warnings.append(
            f"appendix/{rel} was added after preregistration sealing (appendix/preregistration.json) without a "
            f"download_log.csv or intake.md entry; document its provenance in Section 3, or run `local_data.py intake` "
            f"before `prereg`."
        )
    sec2 = _norm_hypothesis(_extract_section_slice(clean_text, section_positions, "Framing & Hypotheses"))
    for key, text in (body["hypotheses"] or {}).items():
        if _norm_hypothesis(str(text)) not in sec2:
            warnings.append(
                f"{key} in Section 2 differs from appendix/preregistration.json (sealed {body['sealed_utc']}); keep the "
                f"sealed wording or say in Section 3 what changed after sealing and why."
            )
    # HARKing check: flag hypotheses that state >= 2 computed results from numbers.json, exact or rounded
    if numbers_data:
        hyp_text = " ".join(str(v) for v in (body["hypotheses"] or {}).values())
        hits = _hypothesis_number_hits(hyp_text, numbers_data)
        if hits:
            sink.append(
                f"appendix/preregistration.json hypothesis contains computed result figures from "
                f"appendix/numbers.json, exact or rounded ({', '.join(hits[:4])}; possible HARKing); state directional "
                f"or threshold predictions before running analysis.py."
            )
    return errors, warnings
