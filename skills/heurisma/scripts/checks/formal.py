"""Opt-in validator checks for Lean 4 / Lake formal proofs (appendix/formal_proofs.csv, code P4-LEAN)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re
from typing import Any

from checks.common import (
    _extract_citation_ids,
    _extract_section_slice,
    _file_sha256,
    _is_separator_row,
    _parse_utc,
    _split_md_table_row,
)
from contracts import (
    FORMAL_PROOFS_CSV,
    STANDARD_LEAN_AXIOMS,
    STRONG_TAGS,
)
import formal_math

_REQ_FORMAL_COLS = (
    "proof_id",
    "slug",
    "challenge_file",
    "challenge_sha256",
    "solution_file",
    "solution_sha256",
    "status",
    "sorries",
    "axioms",
    "verified_utc",
)
_VERIFIED_STATUSES = frozenset({"kernel-verified", "comparator-verified"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EMPIRICAL_BRANCH_RE = re.compile(
    r"\b(?:Natural|Physical|Physics|Biomedical|Biology|Chemistry|Medicine|Clinical|Ecology|Earth|Health|Social|Economics|Engineering|"
    r"F[ií]sic[ao]|Biom[eé]dic[ao]|Biolog[ií]a|Qu[ií]mica|Medicina|Cl[ií]nic[ao]|Ecolog[ií]a|Salud|Sociales|Econom[ií]a|Ingenier[ií]a)\b",
    re.IGNORECASE,
)
_EMPIRICAL_CLAIM_RE = re.compile(
    r"\b(?:measured|observed|field\s+experiment|experiment|survey|empirical|"
    r"medid[oa]|observad[oa]|emp[ií]ric[oa]|experimento|encuesta)\b",
    re.IGNORECASE,
)
_FORMAL_SCOPE_RE = re.compile(
    r"\b(?:formal|mathematical|deductive|axiom|axioms|model|theorem|under\s+the\s+model|"
    r"bajo\s+el\s+modelo|deductiv[oa]|matem[aá]tic[oa]|teorema|axioma)\b",
    re.IGNORECASE,
)


def _load_formal_registry(csv_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            header = [c.strip() if c is not None else "" for c in (reader.fieldnames or [])]
            reader.fieldnames = header
            missing = [c for c in _REQ_FORMAL_COLS if c not in header]
            if missing:
                errors.append(
                    f"appendix/{FORMAL_PROOFS_CSV}: missing required column(s): {', '.join(missing)}."
                )
                return [], errors
            return list(reader), errors
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        return [], [f"appendix/{FORMAL_PROOFS_CSV}: unreadable registry ({exc})."]


def _match_registry_row(
    source_row: dict[str, str],
    reg_rows: list[dict[str, str]],
) -> dict[str, str] | None:
    cid = (source_row.get("claim_id") or "").strip()
    url = (source_row.get("url") or "").strip().replace("\\", "/")
    for r in reg_rows:
        if cid and (r.get("proof_id") or "").strip() == cid:
            return r
    for r in reg_rows:
        sol_f = (r.get("solution_file") or "").strip().replace("\\", "/")
        if url and sol_f and (url == sol_f or url.endswith("/" + sol_f) or sol_f.endswith("/" + url)):
            return r
    return None


def _audit_formal_project_row(
    report_dir: Path,
    reg_row: dict[str, str],
    *,
    level: int,
    run_start: Any,
    errors: list[str],
    warnings: list[str],
) -> None:
    pid = (reg_row.get("proof_id") or reg_row.get("slug") or "?").strip()
    slug = (reg_row.get("slug") or "").strip()
    status = (reg_row.get("status") or "").strip()
    sorries_raw = (reg_row.get("sorries") or "").strip()
    axioms_raw = (reg_row.get("axioms") or "").strip()
    verified_utc = (reg_row.get("verified_utc") or "").strip()

    if status in _VERIFIED_STATUSES:
        if sorries_raw != "0":
            errors.append(
                f"appendix/{FORMAL_PROOFS_CSV}: proof '{pid}' records sorries={sorries_raw!r}; verified proofs must record sorries='0'."
            )
    elif sorries_raw and sorries_raw != "0":
        errors.append(
            f"appendix/{FORMAL_PROOFS_CSV}: proof '{pid}' records sorries={sorries_raw!r}; verified proofs must have 0 sorry."
        )

    axioms_list = [a.strip() for a in re.split(r"[;,]", axioms_raw) if a.strip()]
    bad_axioms = [a for a in axioms_list if a not in STANDARD_LEAN_AXIOMS]
    if bad_axioms:
        errors.append(
            f"appendix/{FORMAL_PROOFS_CSV}: proof '{pid}' depends on non-standard axiom(s) {', '.join(bad_axioms)} "
            f"(only {', '.join(sorted(STANDARD_LEAN_AXIOMS))} are permitted)."
        )

    if run_start is not None and verified_utc:
        v_dt = _parse_utc(verified_utc)
        if v_dt is not None and v_dt < run_start:
            (errors if level == 3 else warnings).append(
                f"appendix/{FORMAL_PROOFS_CSV}: proof '{pid}' verified_utc ({verified_utc}) precedes "
                f"run_started_utc ({run_start.strftime('%Y-%m-%dT%H:%M:%SZ')}); re-run formal_math.py check."
            )

    if not slug or "/" in slug or "\\" in slug or slug in (".", ".."):
        errors.append(f"appendix/{FORMAL_PROOFS_CSV}: proof '{pid}' has invalid slug {slug!r}.")
        return

    root = report_dir.resolve()
    proj = (report_dir / "appendix" / "formal" / slug).resolve()
    try:
        proj.relative_to(root)
    except ValueError:
        errors.append(f"appendix/{FORMAL_PROOFS_CSV}: proof '{pid}' slug {slug!r} escapes report directory.")
        return

    ch_path = proj / "Challenge.lean"
    sol_path = proj / "Solution.lean"
    verify_path = proj / "verify.json"

    if not ch_path.is_file() or not sol_path.is_file():
        errors.append(
            f"appendix/formal/{slug}/: missing Challenge.lean or Solution.lean referenced by appendix/{FORMAL_PROOFS_CSV}."
        )
        return

    expected_ch_rel = f"appendix/formal/{slug}/Challenge.lean"
    expected_sol_rel = f"appendix/formal/{slug}/Solution.lean"
    decl_ch_file = (reg_row.get("challenge_file") or "").strip().replace("\\", "/")
    decl_sol_file = (reg_row.get("solution_file") or "").strip().replace("\\", "/")
    if decl_ch_file and decl_ch_file != expected_ch_rel:
        errors.append(
            f"appendix/{FORMAL_PROOFS_CSV}: proof '{pid}' challenge_file {decl_ch_file!r} must be {expected_ch_rel!r}."
        )
    if decl_sol_file and decl_sol_file != expected_sol_rel:
        errors.append(
            f"appendix/{FORMAL_PROOFS_CSV}: proof '{pid}' solution_file {decl_sol_file!r} must be {expected_sol_rel!r}."
        )

    actual_ch_sha = _file_sha256(ch_path)
    actual_sol_sha = _file_sha256(sol_path)
    decl_ch_sha = (reg_row.get("challenge_sha256") or "").strip().lower()
    decl_sol_sha = (reg_row.get("solution_sha256") or "").strip().lower()

    if not _SHA256_RE.fullmatch(decl_ch_sha) or actual_ch_sha != decl_ch_sha:
        errors.append(
            f"appendix/formal/{slug}/Challenge.lean: SHA-256 {actual_ch_sha[:12]} != declared {decl_ch_sha[:12]} "
            f"in appendix/{FORMAL_PROOFS_CSV} (missing, malformed, or file changed after verification)."
        )
    if not _SHA256_RE.fullmatch(decl_sol_sha) or actual_sol_sha != decl_sol_sha:
        errors.append(
            f"appendix/formal/{slug}/Solution.lean: SHA-256 {actual_sol_sha[:12]} != declared {decl_sol_sha[:12]} "
            f"in appendix/{FORMAL_PROOFS_CSV} (missing, malformed, or file changed after verification)."
        )

    if not verify_path.is_file():
        errors.append(
            f"appendix/formal/{slug}/verify.json: missing verification certificate for proof '{pid}'."
        )
    else:
        try:
            vdata = json.loads(verify_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"appendix/formal/{slug}/verify.json: unreadable JSON ({exc}).")
            vdata = None
        if isinstance(vdata, dict):
            v_slug = str(vdata.get("slug") or "").strip()
            if v_slug and v_slug != slug:
                errors.append(
                    f"appendix/formal/{slug}/verify.json: slug {v_slug!r} does not match directory slug {slug!r}."
                )
            v_ch = str(vdata.get("challenge_sha256") or "").strip().lower()
            v_sol = str(vdata.get("solution_sha256") or "").strip().lower()
            if not _SHA256_RE.fullmatch(v_ch) or actual_ch_sha != v_ch:
                errors.append(
                    f"appendix/formal/{slug}/verify.json: Challenge.lean SHA-256 mismatch ({actual_ch_sha[:12]} != {v_ch[:12]})."
                )
            if not _SHA256_RE.fullmatch(v_sol) or actual_sol_sha != v_sol:
                errors.append(
                    f"appendix/formal/{slug}/verify.json: Solution.lean SHA-256 mismatch ({actual_sol_sha[:12]} != {v_sol[:12]})."
                )
            v_status = str(vdata.get("status") or "").strip()
            if status in _VERIFIED_STATUSES and v_status != status:
                errors.append(
                    f"appendix/formal/{slug}/verify.json: status {v_status!r} disagrees with appendix/{FORMAL_PROOFS_CSV} ({status!r})."
                )
            if status in _VERIFIED_STATUSES:
                v_sorries = vdata.get("sorries")
                if v_sorries is not None and v_sorries != 0:
                    errors.append(
                        f"appendix/formal/{slug}/verify.json: records sorries={v_sorries!r} on a verified proof."
                    )
                if "statement_paired" in vdata and vdata.get("statement_paired") is not True:
                    errors.append(
                        f"appendix/formal/{slug}/verify.json: records statement_paired={vdata.get('statement_paired')!r} on a verified proof."
                    )
                v_axioms = vdata.get("axioms")
                if isinstance(v_axioms, list):
                    v_bad = [str(a) for a in v_axioms if str(a) not in STANDARD_LEAN_AXIOMS]
                    if v_bad:
                        errors.append(
                            f"appendix/formal/{slug}/verify.json: records non-standard axiom(s) {', '.join(v_bad)}."
                        )

    ch_src = ch_path.read_text(encoding="utf-8", errors="replace")
    sol_src = sol_path.read_text(encoding="utf-8", errors="replace")
    hazards = formal_math.scan_lean_hazards(ch_src, sol_src)
    if hazards["solution_hazards"]:
        errors.append(
            f"appendix/formal/{slug}/Solution.lean: contains forbidden Lean escape hazard(s): "
            f"{', '.join(hazards['solution_hazards'])}."
        )
    if hazards["challenge_hazards"]:
        errors.append(
            f"appendix/formal/{slug}/Challenge.lean: contains forbidden Lean escape hazard(s): "
            f"{', '.join(hazards['challenge_hazards'])}."
        )
    if hazards["vacuous_or_trivial"]:
        errors.append(
            f"appendix/formal/{slug}/Challenge.lean: contains vacuous or trivial theorem statement "
            f"({', '.join(hazards['vacuous_or_trivial'])}); cannot sustain a verified formal claim."
        )
    if hazards.get("trivial_proof_warnings"):
        warnings.append(
            f"appendix/formal/{slug}/Solution.lean: proof exhibits triviality or unused-hypothesis signal(s) "
            f"({', '.join(hazards['trivial_proof_warnings'])}); verify that Challenge.lean formalizes a non-trivial "
            f"domain theorem rather than an algebraic substitution with unused hypotheses."
        )

    ch_clean = formal_math.strip_lean_comments_and_strings(ch_src)
    sol_clean = formal_math.strip_lean_comments_and_strings(sol_src)
    paired_ok, pair_errs, sig_warns, pairs = formal_math.resolve_theorem_pairs(ch_clean, sol_clean)
    if not hazards["challenge_theorems"]:
        errors.append(
            f"appendix/formal/{slug}/Challenge.lean: declares no theorem or lemma to verify."
        )
    elif not paired_ok:
        errors.append(
            f"appendix/formal/{slug}/Solution.lean: missing proof theorem against Challenge.lean ({'; '.join(pair_errs)})."
        )
    if sig_warns:
        warnings.append(
            f"appendix/formal/{slug}/Solution.lean: static signature heuristic differs from Challenge.lean "
            f"({'; '.join(sig_warns)}); the Lean kernel definitional-equality witness is authoritative."
        )


def check_formal_proofs(
    report_dir: Path | None,
    sources_rows: list[dict[str, str]],
    clean_text: str,
    section_positions: dict[str, int],
    level: int,
    run_start: Any = None,
) -> tuple[list[str], list[str]]:
    """Validate Lean 4 formal proofs, registry provenance, and deductive-vs-empirical bridge (opt-in)."""
    errors: list[str] = []
    warnings: list[str] = []
    if report_dir is None:
        return errors, warnings

    reg_path = report_dir / "appendix" / FORMAL_PROOFS_CSV
    formal_sources = [r for r in sources_rows if (r.get("kind") or "").strip().lower() == "formal-proof"]
    if not reg_path.is_file() and not formal_sources:
        return errors, warnings

    reg_rows: list[dict[str, str]] = []
    if reg_path.is_file():
        reg_rows, reg_errs = _load_formal_registry(reg_path)
        errors.extend(reg_errs)

    source_by_id = {(r.get("claim_id") or "").strip(): r for r in sources_rows if (r.get("claim_id") or "").strip()}
    strong_cited_ids: set[str] = set()
    matrix_data_rows: list[str] = []

    if "Claim-Evidence Matrix" in section_positions:
        matrix_block = _extract_section_slice(clean_text, section_positions, "Claim-Evidence Matrix")
        table_lines = [
            ln.strip()
            for ln in matrix_block.splitlines()
            if ln.strip().startswith("|") and ln.strip().endswith("|")
        ]
        matrix_data_rows = [
            row
            for row in table_lines[1:]
            if not _is_separator_row(_split_md_table_row(row))
        ]
        for row in matrix_data_rows:
            if any(st in row for st in STRONG_TAGS):
                strong_cited_ids.update(_extract_citation_ids(row))

    audited_slugs: set[str] = set()
    for srow in formal_sources:
        cid = (srow.get("claim_id") or "?").strip()
        tier = (srow.get("tier") or "").strip()
        is_above_tier3 = bool(re.search(r"\bTier\s*[12]\b", tier, re.IGNORECASE))
        in_strong = cid in strong_cited_ids

        reg_row = _match_registry_row(srow, reg_rows)
        if reg_row is None:
            errors.append(
                f"Source '{cid}' (kind=formal-proof) has no matching entry in appendix/{FORMAL_PROOFS_CSV}; "
                f"run `formal_math.py check` before registering a formal proof."
            )
            continue

        status = (reg_row.get("status") or "").strip()
        slug = (reg_row.get("slug") or "").strip()
        s_url = (srow.get("url") or "").strip().replace("\\", "/")
        expected_prefix = f"appendix/formal/{slug}/"
        if slug and s_url.endswith(".lean") and not (
            s_url == f"{expected_prefix}Solution.lean"
            or s_url == f"{expected_prefix}Challenge.lean"
            or s_url.endswith("/" + expected_prefix + "Solution.lean")
            or s_url.endswith("/" + expected_prefix + "Challenge.lean")
        ):
            errors.append(
                f"Source '{cid}' (kind=formal-proof) points to {s_url!r} which does not match "
                f"appendix/formal/{slug}/ in appendix/{FORMAL_PROOFS_CSV}."
            )

        if status == "unverified_no_toolchain" and is_above_tier3:
            errors.append(
                f"Source '{cid}' (kind=formal-proof) has status=unverified_no_toolchain and cannot be declared {tier}; "
                f"cap unverified Lean drafts at Tier 3 ([Preliminary])."
            )
        elif (is_above_tier3 or in_strong) and status not in _VERIFIED_STATUSES:
            errors.append(
                f"Source '{cid}' (kind=formal-proof) is declared {tier} / sustains [Strong] but has status={status!r} "
                f"(not kernel-verified or comparator-verified in appendix/{FORMAL_PROOFS_CSV})."
            )

        # R3: scan hazards/triviality for EVERY registered Lean project regardless of tier,
        # [Strong] citation, or verified status. The tier-ceiling error above stays separate.
        audited_slugs.add(slug)
        _audit_formal_project_row(
            report_dir,
            reg_row,
            level=level,
            run_start=run_start,
            errors=errors,
            warnings=warnings,
        )

    for reg_row in reg_rows:
        slug = (reg_row.get("slug") or "").strip()
        if slug not in audited_slugs:
            audited_slugs.add(slug)
            _audit_formal_project_row(
                report_dir,
                reg_row,
                level=level,
                run_start=run_start,
                errors=errors,
                warnings=warnings,
            )

    # P-10: Deductive-to-empirical bridge check (warning ONLY — lexical heuristic, never a hard Level 3 error)
    sec2 = _extract_section_slice(clean_text, section_positions, "Framing & Hypotheses") if "Framing & Hypotheses" in section_positions else ""
    if matrix_data_rows and _EMPIRICAL_BRANCH_RE.search(sec2):
        for row_idx, row in enumerate(matrix_data_rows, start=1):
            if not any(st in row for st in STRONG_TAGS):
                continue
            cited = [cid for cid in _extract_citation_ids(row) if cid in source_by_id]
            if not cited:
                continue
            if all((source_by_id[cid].get("kind") or "").strip().lower() == "formal-proof" for cid in cited):
                cells = _split_md_table_row(row)
                claim_cell = cells[0] if cells else row
                if _EMPIRICAL_CLAIM_RE.search(claim_cell) and not _FORMAL_SCOPE_RE.search(claim_cell):
                    warnings.append(
                        f"Claim-Evidence Matrix row {row_idx} rests solely on formal-proof source(s) ({', '.join(cited)}) "
                        f"while using empirical observation language without a formal-scope qualifier; verify that a "
                        f"deductive theorem is not being presented as an empirical measurement (or cite empirical Tier 1 evidence)."
                    )

    return errors, warnings
