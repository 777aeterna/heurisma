"""Opt-in validator checks for data-driven symbolic conjectures (appendix/conjectures.json, code P4-CONJECTURE).

Level semantics (DIS-14): these are *opt-in* epistemic checks. At validation level 3 the
holdout-split and M59 epistemic-ceiling violations are reported as errors; at lower levels (or no
level) they are downgraded to warnings so the same checks stay informative without blocking a
shallower pass.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from checks.common import (
    _declared_sha,
    _extract_citation_ids,
    _extract_section_slice,
    _is_separator_row,
    _split_md_table_row,
)
from contracts import CONJECTURES_JSON, STRONG_TAGS

_ABOVE_PRELIMINARY_TAGS = ("[Strong]", "[Fuerte]", "[Moderate]", "[Moderada]", "[Moderado]")
_CONJECTURE_PROSE_RE = re.compile(
    r"\b(?:conjectures?\.json|conjectur(?:e|ed|al)|conjetura(?:da|do)?|"
    r"(?:discovered|conjectured|symbolic|fitted)\s+(?:scaling\s+)?(?:law|relation|equation|monomial|formula)|"
    r"(?:ley|relaci[oó]n|ecuaci[oó]n|f[oó]rmula)\s+(?:descubierta|conjeturada|simb[oó]lica))\b",
    re.IGNORECASE,
)


def _norm_path(path: str) -> str:
    """Lexically normalize a path: collapse slashes and resolve '.'/'..' segments."""
    parts: list[str] = []
    for seg in path.replace("\\", "/").split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append("..")
        else:
            parts.append(seg)
    return "/".join(parts)


def _location_parts(raw: str) -> tuple[str, str, str] | None:
    """Split a URL or local path into (scheme, host, path); query strings and fragments are dropped.

    scheme is '' for a plain local path; 'file', 'http', or 'https' otherwise. Returns None for
    blank input. The path is kept in full (never reduced to a basename).
    """
    s = (raw or "").strip().replace("\\", "/")
    if not s:
        return None
    s = s.split("#", 1)[0].split("?", 1)[0]
    if "://" in s:
        scheme, _, rest = s.partition("://")
        scheme = scheme.lower()
        host, _, path = rest.partition("/")
        # Drop userinfo and port from the host for a stable comparison key.
        host = host.rsplit("@", 1)[-1].split(":", 1)[0].lower()
        return (scheme, host, _norm_path(path))
    return ("", "", _norm_path(s))


def _same_discovery_data(source_row: dict[str, str], rec: dict[str, Any]) -> bool:
    cid = (source_row.get("claim_id") or "").strip()
    decl_source_ids = {str(s).strip() for s in (rec.get("source_ids") or []) if str(s).strip()}
    if cid and cid in decl_source_ids:
        return True

    # Full 64-hex SHA-256 equality (DIS-13); a prefix fallback is kept only for legacy rows that
    # declare a truncated (< 64 hex) hash.
    data_sha = str(rec.get("data_sha256") or "").strip().lower()
    src_sha = _declared_sha(source_row)
    if data_sha and src_sha:
        if len(data_sha) == 64 and len(src_sha) == 64:
            if data_sha == src_sha:
                return True
        else:
            short = src_sha if len(src_sha) < len(data_sha) else data_sha
            if short and (data_sha.startswith(short) or src_sha.startswith(short)):
                return True

    # Location comparison: same host+path (no query string) for URLs, full path (not basename)
    # for local paths.
    data_loc = _location_parts(str(rec.get("data_file") or ""))
    url_loc = _location_parts(str(source_row.get("url") or ""))
    if data_loc and url_loc:
        d_scheme, d_host, d_path = data_loc
        u_scheme, u_host, u_path = url_loc
        if d_scheme or u_scheme:
            if d_scheme == u_scheme and d_host == u_host and d_path == u_path:
                return True
        else:
            if d_path == u_path:
                return True
    return False


def _audit_one_conjecture_file(
    conj_path: Path,
    rel_name: str,
    clean_text: str,
    section_positions: dict[str, int],
    sources_rows: list[dict[str, str]],
    level: int,
    errors: list[str],
    warnings: list[str],
) -> None:
    raw_text = conj_path.read_text(encoding="utf-8", errors="replace")
    if re.search(r"(?<![\w\"])-?(?:NaN|Infinity)(?![\w\"])", raw_text):
        errors.append(
            f"{rel_name}: file is not strict JSON (contains NaN/Infinity; seal via conjecture.py with allow_nan=False)."
        )
        return

    try:
        rec = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        errors.append(f"{rel_name}: invalid JSON ({exc}).")
        return

    if not isinstance(rec, dict):
        errors.append(f"{rel_name}: root value must be a JSON object.")
        return

    declared_sha = rec.get("sha256")
    body = {k: v for k, v in rec.items() if k != "sha256"}
    expected_sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if not isinstance(declared_sha, str) or declared_sha != expected_sha:
        errors.append(
            f"{rel_name}: file was edited after sealing (sha256 mismatch); re-run conjecture.py discover instead of hand-editing."
        )

    train_count = rec.get("train_count")
    holdout_count = rec.get("holdout_count")
    sink = errors if level == 3 else warnings
    if not isinstance(holdout_count, int) or holdout_count <= 0:
        sink.append(
            f"{rel_name}: holdout_count is {holdout_count!r} (fitting on 100% of rows with no holdout validation is forbidden; require holdout_count >= 2)."
        )
    elif holdout_count < 2 or not isinstance(train_count, int) or train_count < 4:
        sink.append(
            f"{rel_name}: insufficient train/holdout split (train_count={train_count!r}, holdout_count={holdout_count!r}; require train_count >= 4 and holdout_count >= 2)."
        )

    raw_cands = rec.get("candidates")
    candidates: list[Any] = raw_cands if isinstance(raw_cands, list) else []
    cand_ids = [
        str(c.get("id")).strip()
        for c in candidates
        if isinstance(c, dict) and str(c.get("id") or "").strip()
    ]
    cand_exprs = [
        str(c.get("expr")).strip()
        for c in candidates
        if isinstance(c, dict) and len(str(c.get("expr") or "").strip()) >= 6
    ]
    cand_rhs_list: list[str] = []
    for expr in cand_exprs:
        if "=" in expr:
            rhs = expr.split("=", 1)[1].strip()
            if len(rhs) >= 4:
                cand_rhs_list.append(rhs)
    cand_id_re = (
        re.compile(r"\b(?:" + "|".join(re.escape(cid) for cid in cand_ids) + r")\b")
        if cand_ids
        else None
    )
    target_var = str(rec.get("target") or "").strip()
    pred_vars = [str(p).strip() for p in (rec.get("predictors") or []) if str(p).strip()]
    decl_source_ids = {str(s).strip() for s in (rec.get("source_ids") or []) if str(s).strip()}
    target_var_l = target_var.lower()
    pred_vars_l = [p.lower() for p in pred_vars]

    def mentions_conjecture(text: str) -> bool:
        if _CONJECTURE_PROSE_RE.search(text):
            return True
        if cand_id_re is not None and cand_id_re.search(text):
            return True
        if any(expr in text for expr in cand_exprs) or any(rhs in text for rhs in cand_rhs_list):
            return True
        # R2/DIS-5: variable-name matching normalizes whitespace/case and accepts single-letter
        # variables (P, a). The __invariant__ skip and the len >= 2 restrictions are removed.
        norm = re.sub(r"\s+", " ", text).lower()
        if target_var_l and re.search(rf"\b{re.escape(target_var_l)}\b", norm) and any(
            re.search(rf"\b{re.escape(p)}\b", norm) for p in pred_vars_l
        ):
            if "=" in norm or "^" in norm or "∝" in norm:
                return True
        return False

    source_by_id = {(r.get("claim_id") or "").strip(): r for r in sources_rows if (r.get("claim_id") or "").strip()}
    any_source_matches_discovery = any(_same_discovery_data(r, rec) for r in sources_rows)
    discovery_known = bool(decl_source_ids) or any_source_matches_discovery

    def _is_t1_formal(cid: str) -> bool:
        return (
            (source_by_id[cid].get("kind") or "").strip().lower() == "formal-proof"
            and re.search(r"\bTier\s*1\b", source_by_id[cid].get("tier") or "", re.IGNORECASE) is not None
        )

    def _is_t1_data(cid: str) -> bool:
        return (
            (source_by_id[cid].get("kind") or "").strip().lower() == "data"
            and re.search(r"\bTier\s*1\b", source_by_id[cid].get("tier") or "", re.IGNORECASE) is not None
        )

    def _row_refers_to_discovery(text: str) -> bool:
        """Source-driven detection: the row cites a declared discovery source or a source whose
        data matches the discovery dataset by host/path/hash."""
        row_cids = _extract_citation_ids(text)
        if any(cid in decl_source_ids for cid in row_cids):
            return True
        return any(_same_discovery_data(source_by_id[cid], rec) for cid in row_cids if cid in source_by_id)

    def _check_independence(text: str, where: str) -> None:
        row_cids = [cid for cid in _extract_citation_ids(text) if cid in source_by_id]
        has_formal_t1 = any(_is_t1_formal(cid) for cid in row_cids)
        discovery_data_ids = [
            cid for cid in row_cids if _is_t1_data(cid) and _same_discovery_data(source_by_id[cid], rec)
        ]
        indep_data_t1_ids = [
            cid for cid in row_cids if _is_t1_data(cid) and not _same_discovery_data(source_by_id[cid], rec)
        ]
        if has_formal_t1 or indep_data_t1_ids:
            return
        if discovery_data_ids and discovery_known:
            # VAL-8: known non-independence — the only backing is the discovery data itself.
            sink.append(
                f"{where} tags an unproved symbolic conjecture as [Strong] ({rel_name}) but its only backing "
                f"is the discovery data itself ({', '.join(sorted(discovery_data_ids))}); cap data-driven "
                f"conjectures at [Moderate] or [Preliminary] unless backed by a kernel-verified Tier 1 "
                f"formal proof or independent Tier 1 replication data."
            )
        elif discovery_known:
            sink.append(
                f"{where} tags an unproved symbolic conjecture as [Strong] ({rel_name}) without a "
                f"kernel-verified Tier 1 formal proof or independent Tier 1 replication data."
            )
        else:
            # VAL-8: unknown independence — we cannot confirm the cited data differs from the
            # discovery, so this is a soft downgrade (warning), never a hard error.
            warnings.append(
                f"{where} tags an unproved symbolic conjecture as [Strong] ({rel_name}); independence of the "
                f"cited data from the discovery dataset could not be verified. Re-run `conjecture.py discover` "
                f"with --source-ids to distinguish discovery sources from replication, or cap the claim at "
                f"[Moderate]/[Preliminary]."
            )

    if "Claim-Evidence Matrix" in section_positions:
        matrix_block = _extract_section_slice(clean_text, section_positions, "Claim-Evidence Matrix")
        table_lines = [
            ln.strip()
            for ln in matrix_block.splitlines()
            if ln.strip().startswith("|") and ln.strip().endswith("|")
        ]
        data_rows = [
            row
            for row in table_lines[1:]
            if not _is_separator_row(_split_md_table_row(row))
        ]
        for row_idx, row in enumerate(data_rows, start=1):
            if not any(st in row for st in STRONG_TAGS):
                continue
            # DIS-5: flag a [Strong] row source-driven (cites the discovery) even if the prose
            # does not mention the formula verbatim.
            if not (mentions_conjecture(row) or _row_refers_to_discovery(row)):
                continue
            _check_independence(row, f"Claim-Evidence Matrix row {row_idx}")

    # DIS-6: scan Findings (Section 4) for conjecture/invariant claims without cross-contaminating
    # unrelated empirical findings that merely share the same raw source_id (e.g. a NASA catalog).
    if "Findings" in section_positions:
        sec4 = _extract_section_slice(clean_text, section_positions, "Findings")
        for line in sec4.splitlines():
            if not (mentions_conjecture(line) or conj_path.name in line):
                continue
            has_strong = any(tag in line for tag in STRONG_TAGS)
            has_above = any(tag in line for tag in _ABOVE_PRELIMINARY_TAGS)
            if has_strong:
                _check_independence(line, "Findings (Section 4)")
            if rec.get("beats_null") is False and has_above:
                sink.append(
                    f"Section 4 presents conjectured formula above [Preliminary] although {rel_name} "
                    f"records beats_null=false; downgrade to [Preliminary] or report that no candidate beat the null baseline."
                )
                break


def check_conjectures(
    report_dir: Path | None,
    clean_text: str,
    section_positions: dict[str, int],
    sources_rows: list[dict[str, str]],
    level: int,
) -> tuple[list[str], list[str]]:
    """Validate appendix/conjectures.json (and any appendix/*conjecture*.json) integrity, holdout split, and epistemic ceilings (opt-in)."""
    errors: list[str] = []
    warnings: list[str] = []
    if report_dir is None:
        return errors, warnings
    app_dir = report_dir / "appendix"
    if not app_dir.is_dir():
        return errors, warnings

    primary = app_dir / CONJECTURES_JSON
    extra = sorted(
        p for p in app_dir.glob("*conjecture*.json")
        if p.is_file() and p.name != CONJECTURES_JSON
    )
    targets = ([primary] if primary.is_file() else []) + extra
    for conj_path in targets:
        rel_name = f"appendix/{conj_path.name}"
        _audit_one_conjecture_file(
            conj_path,
            rel_name,
            clean_text,
            section_positions,
            sources_rows,
            level,
            errors,
            warnings,
        )
    return errors, warnings
