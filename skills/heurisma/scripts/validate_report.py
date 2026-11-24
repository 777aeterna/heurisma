#!/usr/bin/env python3
"""Zero-dependency structural, content, provenance, localization, and epistemic validator for Heurisma reports."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from contracts import (  # noqa: E402
    ALL_TAGS as ALL_TAGS,
    CANONICAL_DATA_ATTEMPTS_COLS as CANONICAL_DATA_ATTEMPTS_COLS,
    DOCUMENT_KINDS as DOCUMENT_KINDS,
    GATE_FILES as GATE_FILES,
    HTML_SECTION_PATTERNS as HTML_SECTION_PATTERNS,
    REQUIRED_SECTIONS as REQUIRED_SECTIONS,
    STRONG_TAGS as STRONG_TAGS,
    TAG_TO_CANONICAL as TAG_TO_CANONICAL,
    VALID_KINDS as VALID_KINDS,
    VALID_SELECTIONS as VALID_SELECTIONS,
    VALID_TIERS as VALID_TIERS,
    WEAK_KINDS as WEAK_KINDS,
    WEB_SUMMARY_LABELS as WEB_SUMMARY_LABELS,
    WITHHELD_MANIFEST as WITHHELD_MANIFEST,
    __version__ as __version__,
)

# Rule families live in checks/; they are re-exported here so validate_report stays the single public API.
from checks.common import (  # noqa: E402
    LOW_TIER_SOURCE_RE as LOW_TIER_SOURCE_RE,
    FENCED_CODE_RE as FENCED_CODE_RE,
    FIG_MARKER_RE as FIG_MARKER_RE,
    NUM_MARKER_RE as NUM_MARKER_RE,
    LEFTOVER_BRACES_RE as LEFTOVER_BRACES_RE,
    CITE_GROUP_RE as CITE_GROUP_RE,
    NUMERIC_CITE_RE as NUMERIC_CITE_RE,
    UNCONVERTED_LATEX_RE as UNCONVERTED_LATEX_RE,
    SHA_HEX_RE as SHA_HEX_RE,
    SPANISH_LEAKED_CHROME as SPANISH_LEAKED_CHROME,
    _strip_fenced_code_blocks as _strip_fenced_code_blocks,
    _split_md_table_row as _split_md_table_row,
    _is_separator_row as _is_separator_row,
    _extract_section_slice as _extract_section_slice,
    _load_sources_rows as _load_sources_rows,
    _declared_sha as _declared_sha,
    _local_source_path as _local_source_path,
    _file_sha256 as _file_sha256,
    _norm_text as _norm_text,
    _extract_citation_ids as _extract_citation_ids,
    _find_charts_json as _find_charts_json,
    HARDCODED_NUM_RE as HARDCODED_NUM_RE,
    MIN_TYPED_NUMBERS as MIN_TYPED_NUMBERS,
    MIN_MARKER_SHARE as MIN_MARKER_SHARE,
    MIN_TYPED_SUMMARY as MIN_TYPED_SUMMARY,
    SUMMARY_NUM_RE as SUMMARY_NUM_RE,
    SECTION_REF_RE as SECTION_REF_RE,
    LIMITATION_FALLBACKS as LIMITATION_FALLBACKS,
    HOME_PATH_RE as HOME_PATH_RE,
    GATE_MIN_CHARS as GATE_MIN_CHARS,
    SELECTION_LABEL_RE as SELECTION_LABEL_RE,
    MAX_SNAPSHOT_AGE_DAYS as MAX_SNAPSHOT_AGE_DAYS,
    VERDICT_MAX_SENTENCES as VERDICT_MAX_SENTENCES,
    VERDICT_MAX_NUMBERS as VERDICT_MAX_NUMBERS,
    _VERDICT_SENTENCE_RE as _VERDICT_SENTENCE_RE,
    _VERDICT_NUMBER_RE as _VERDICT_NUMBER_RE,
    _WEAK_TITLE_RE as _WEAK_TITLE_RE,
    _REVIEWER_CATEGORIES as _REVIEWER_CATEGORIES,
    GATE_MARKERS as GATE_MARKERS,
    DATE_RE as DATE_RE,
    _NAME_STOPWORDS as _NAME_STOPWORDS,
    _name_tokens as _name_tokens,
    _named_in_any as _named_in_any,
    _parse_utc as _parse_utc,
    AS_OF_RE as AS_OF_RE,
    _as_of_date as _as_of_date,
    _resolve_run_start as _resolve_run_start,
    _resolve_run_since as _resolve_run_since,
)
from checks.structure import (  # noqa: E402
    _TAG_WORD_RE as _TAG_WORD_RE,
    _noncanonical_tags as _noncanonical_tags,
    _canonical_spelling as _canonical_spelling,
)
from checks.gates import (  # noqa: E402
    GATE_HASH_FILES as GATE_HASH_FILES,
    GATE_HEADER_FIELDS as GATE_HEADER_FIELDS,
    GATE_MIN_QUOTES as GATE_MIN_QUOTES,
    _QUOTE_RE as _QUOTE_RE,
    _SELF_REVIEW_DECLARED_RE as _SELF_REVIEW_DECLARED_RE,
    _gate_files as _gate_files,
    gate_hash as gate_hash,
    disposition_rows as disposition_rows,
    reviewer_items as reviewer_items,
    _POST_REVIEW_RE as _POST_REVIEW_RE,
    _analysis_anchor as _analysis_anchor,
    _check_analysis_anchor as _check_analysis_anchor,
    _check_gate_binding as _check_gate_binding,
)
from checks.numeric import (  # noqa: E402
    _TABLE_SKIP_RE as _TABLE_SKIP_RE,
    _TABLE_STAT_RE as _TABLE_STAT_RE,
    _closure_haystack as _closure_haystack,
    _untraced_in as _untraced_in,
    check_caption_closure as check_caption_closure,
    check_numeric_closure as check_numeric_closure,
    _verdict_stats as _verdict_stats,
)
from checks.provenance import (  # noqa: E402
    _is_weak_source as _is_weak_source,
    _local_table_worst_tier as _local_table_worst_tier,
    _registered_data_files as _registered_data_files,
    PRESS_DOMAINS as PRESS_DOMAINS,
    _AS_OF_PART_RE as _AS_OF_PART_RE,
    _data_as_of_after as _data_as_of_after,
    _catalogue_column as _catalogue_column,
    check_source_metadata as check_source_metadata,
    check_source_domains as check_source_domains,
    _curated_only_ids as _curated_only_ids,
    _intake_user_curated_hashes as _intake_user_curated_hashes,
    _OK_OUTCOMES as _OK_OUTCOMES,
    _download_proof as _download_proof,
    _attempt_proof as _attempt_proof,
    _strip_url as _strip_url,
    _literature_proven as _literature_proven,
    check_selection as check_selection,
    _INTAKE_FILE_RE as _INTAKE_FILE_RE,
    _intake_listed_paths as _intake_listed_paths,
    check_inbox as check_inbox,
)
from checks.papers import (  # noqa: E402
    check_papers as check_papers,
)
from checks.prereg import (  # noqa: E402
    _files_added_after_prereg as _files_added_after_prereg,
    _NUM_TOKEN_RE as _NUM_TOKEN_RE,
    _DATE_VALUE_RE as _DATE_VALUE_RE,
    _HARK_IGNORED as _HARK_IGNORED,
    _plain_readings as _plain_readings,
    _canon_number as _canon_number,
    _rounded_forms as _rounded_forms,
    _hypothesis_number_hits as _hypothesis_number_hits,
    check_preregistration as check_preregistration,
)
from checks.html import (  # noqa: E402
    validate_html_full as validate_html_full,
    validate_html as validate_html,
    SOURCE_HASH_RE as SOURCE_HASH_RE,
    _load_render_module as _load_render_module,
    check_html_freshness as check_html_freshness,
)
from checks.codes import (  # noqa: E402
    CODE_RULES as CODE_RULES,
    classify_message as classify_message,
)


def validate_report_full(
    markdown_text: str,
    *,
    level: int | None = None,
    report_dir: Path | None = None,
    charts_path: Path | None = None,
    run_since: str | None = None,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a Heurisma markdown report."""
    errors: list[str] = []
    warnings: list[str] = []

    if not markdown_text or not markdown_text.strip():
        return ["Report is empty. All 7 required Heurisma sections must be present."], warnings

    clean_text = _strip_fenced_code_blocks(markdown_text)

    if HOME_PATH_RE.search(markdown_text):
        errors.append(
            "report.md contains a home-directory path (e.g. /home/<user>/…); remove it so the report does not leak "
            "the author's machine."
        )
    as_of = _as_of_date(markdown_text)
    if as_of:
        from datetime import datetime, timedelta, timezone

        as_of_dt = _parse_utc(as_of)
        if as_of_dt is not None and as_of_dt > datetime.now(timezone.utc) + timedelta(days=1):
            errors.append(f"As-Of Date {as_of} is in the future.")
        if report_dir is not None and as_of_dt is not None:
            start_dt, start_src = _resolve_run_start(report_dir, None, "")
            if start_src == "appendix/run.json" and as_of_dt.date() < start_dt.date():
                errors.append(
                    f"As-Of Date {as_of} is earlier than the run start {start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')} "
                    f"(appendix/run.json)."
                )
    verdict_match = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:?\**\s*:?\**\s*(.+)", clean_text, re.IGNORECASE)
    if verdict_match:
        n_sent, n_num = _verdict_stats(verdict_match.group(1))
        if n_sent > VERDICT_MAX_SENTENCES:
            errors.append(
                f"Calibrated Verdict has {n_sent} sentences (maximum {VERDICT_MAX_SENTENCES}); keep it abstract-style "
                f"and move detail to Section 4."
            )
        if n_num > VERDICT_MAX_NUMBERS:
            errors.append(
                f"Calibrated Verdict has {n_num} numbers (maximum {VERDICT_MAX_NUMBERS}, counting {{{{num:key}}}} "
                f"placeholders); move the rest to Section 4 tables."
            )

    # 1. Check all 7 required top-level section headings in order (EN or ES)
    last_pos = -1
    section_positions: dict[str, int] = {}
    for label, pattern in REQUIRED_SECTIONS:
        match = re.search(pattern, clean_text, flags=re.MULTILINE | re.IGNORECASE)
        if not match:
            errors.append(f"Missing required section: '## {label}'")
        else:
            pos = match.start()
            section_positions[label] = pos
            if pos < last_pos:
                errors.append(f"Section out of order: '## {label}' must appear after preceding sections.")
            last_pos = max(last_pos, pos)

    # 2. Check minimum substance across required sections (rejects empty/filler stubs)
    min_words_by_section = {
        "Executive Summary": 30,
        "Findings": 30,
        "Counter-Evidence & Alternative Explanations": 12,
        "Limitations & Open Questions": 12,
    }
    for label, min_words in min_words_by_section.items():
        sec_text = _extract_section_slice(clean_text, section_positions, label)
        if sec_text:
            body_lines = [ln.strip() for ln in sec_text.splitlines()[1:] if ln.strip()]
            body_words = sum(len(ln.split()) for ln in body_lines)
            if body_words < min_words:
                errors.append(
                    f"Section '## {label}' lacks substantive content "
                    f"({body_words} words; minimum {min_words} words required)."
                )

    # 3. Check global presence of canonical/localized epistemic calibration tags
    tag_count = sum(clean_text.count(tag) for tag in ALL_TAGS)
    if tag_count == 0:
        wrong = _noncanonical_tags(clean_text)
        if wrong:
            errors.append(
                f"Missing epistemic calibration tags: the report writes {', '.join(repr(w) for w in wrong[:4])}, but tags are "
                f"case-sensitive; write exactly {', '.join(repr(_canonical_spelling(w)) for w in wrong[:4])}."
            )
        else:
            errors.append(
                "Missing epistemic calibration tags: report must include canonical tags "
                "([Strong]/[Fuerte], [Moderate]/[Moderada], [Preliminary]/[Preliminar], or [Speculative]/[Especulativa])."
            )

    # 4. Check hypotheses ($H_0$ / H0 / H₀ and $H_1$ / H1 / H₁) strictly inside Section 2
    if "Framing & Hypotheses" in section_positions:
        sec2 = _extract_section_slice(clean_text, section_positions, "Framing & Hypotheses")
        has_h0 = bool(re.search(r"(\$H_0\$|\bH_0\b|\bH0\b|H₀|Null Hypothesis|Hip[oó]tesis nula)", sec2, re.IGNORECASE))
        has_h1 = bool(re.search(r"(\$H_1\$|\bH_1\b|\bH1\b|H₁|Alternative Hypothesis|Hip[oó]tesis alternativa)", sec2, re.IGNORECASE))
        if not (has_h0 and has_h1):
            errors.append(
                "Missing explicit null and alternative hypotheses (H_0 and H_1) inside Section 2 (Framing & Hypotheses)."
            )

    sources_rows, sources_cols = _load_sources_rows(report_dir)
    source_by_id = {(r.get("claim_id") or "").strip(): r for r in sources_rows if (r.get("claim_id") or "").strip()}
    tier3_titles = [
        (row.get("source_title") or "").strip().lower()
        for row in sources_rows
        if re.search(r"\bTier\s*3\b", (row.get("tier") or ""), re.IGNORECASE)
        and len((row.get("source_title") or "").strip()) >= 4
    ]

    # 5. Validate Claim-Evidence Matrix structure, column count, >=2 rows, per-row tags, and Strong+Tier3/press ban
    if "Claim-Evidence Matrix" in section_positions:
        matrix_block = _extract_section_slice(clean_text, section_positions, "Claim-Evidence Matrix")
        table_lines = [
            line.strip()
            for line in matrix_block.splitlines()
            if line.strip().startswith("|") and line.strip().endswith("|")
        ]
        if len(table_lines) < 3:
            errors.append(
                "Claim-Evidence Matrix section must contain a populated Markdown table "
                "(header, separator, and at least 2 claim-evidence rows)."
            )
        else:
            header_cells = _split_md_table_row(table_lines[0])
            if len(header_cells) < 4:
                errors.append(
                    f"Claim-Evidence Matrix table must have at least 4 columns "
                    f"(Claim, Discipline, Evidence/Tier, Confidence Tag); found {len(header_cells)}."
                )
            data_rows = [
                row
                for row in table_lines[1:]
                if not _is_separator_row(_split_md_table_row(row))
            ]
            if len(data_rows) < 2:
                errors.append(
                    f"Claim-Evidence Matrix table must contain at least 2 substantive claim rows; found {len(data_rows)}."
                )
            for row_idx, row in enumerate(data_rows, start=1):
                if not any(tag in row for tag in ALL_TAGS):
                    wrong_tags = _noncanonical_tags(row)
                    if wrong_tags:
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} writes {', '.join(repr(w) for w in wrong_tags)}; write the "
                            f"tag exactly as {', '.join(repr(_canonical_spelling(w)) for w in wrong_tags)} (tags are case-sensitive)."
                        )
                    else:
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} is missing a canonical confidence tag "
                            f"([Strong], [Moderate], [Preliminary], or [Speculative])."
                        )
                if source_by_id and any(st in row for st in STRONG_TAGS):
                    # P0-3: decided from sources.csv by claim_id, so relabelling a source in prose cannot hide it
                    row_ids = _extract_citation_ids(row)
                    known = [cid for cid in row_ids if cid in source_by_id]
                    if not row_ids:
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} is [Strong] but has no [@id] citation: "
                            f"a strong claim must cite the evidence that carries it."
                        )
                    elif known and all(_is_weak_source(source_by_id[cid]) for cid in known):
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} is [Strong] resting only on weak source(s) "
                            f"{', '.join(known)} (Tier 3, press, own-computation or abstract-only in "
                            f"appendix/sources.csv); cite an independent Tier 1/2 source or lower the tag."
                        )
                    else:
                        inherited = [
                            cid for cid in known
                            if not _is_weak_source(source_by_id[cid])
                            and _local_table_worst_tier(report_dir, source_by_id[cid]) == "Tier 3"
                        ]
                        if inherited and all(
                            _is_weak_source(source_by_id[cid]) or cid in inherited for cid in known
                        ):
                            errors.append(
                                f"Claim-Evidence Matrix row {row_idx} is [Strong] resting only on weak source(s) "
                                f"{', '.join(known)}: local table(s) {', '.join(inherited)} inherit Tier 3 through "
                                f"primary_source_id in appendix/data/sources_metadata.csv; cite an independent Tier 1/2 "
                                f"source or lower the tag."
                            )
                curated = _curated_only_ids(row, source_by_id)
                if curated:
                    limits = _extract_section_slice(clean_text, section_positions, "Limitations & Open Questions")
                    if any(st in row for st in STRONG_TAGS):
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} rests only on user-curated source(s) {', '.join(curated)}; "
                            f"a claim supported only by documents the user chose is capped at [Moderate] and labelled "
                            f"'Selection bias: user-curated corpus'."
                        )
                    elif not (SELECTION_LABEL_RE.search(row) or SELECTION_LABEL_RE.search(limits)):
                        (errors if level == 3 else warnings).append(
                            f"Claim-Evidence Matrix row {row_idx} rests only on user-curated source(s) {', '.join(curated)}; "
                            f"label it 'Selection bias: user-curated corpus' in the row or in Section 7."
                        )
                if any(st in row for st in STRONG_TAGS):
                    row_lower = row.lower()
                    is_low_tier = bool(LOW_TIER_SOURCE_RE.search(row)) or any(
                        title in row_lower for title in tier3_titles
                    )
                    if is_low_tier:
                        errors.append(
                            f"Claim-Evidence Matrix row {row_idx} pairs [Strong] with Tier 3 / press evidence, "
                            f"which violates the epistemic calibration scale."
                        )

    # 6. Level 2 & Level 3 artifact, figure (V1), citation (V2), provenance (V5), hygiene (V6), and verdict-number (P11) checks
    if level is not None and level >= 2 and report_dir is not None:
        appendix_dir = report_dir / "appendix"
        if not appendix_dir.is_dir():
            errors.append(f"Level {level} report requires an 'appendix/' directory at {appendix_dir}.")
        else:
            py_files = list(appendix_dir.glob("*.py"))
            if not py_files:
                errors.append(f"Level {level} report requires at least one reproducible Python script in {appendix_dir}.")
            if not (appendix_dir / "output.txt").is_file():
                errors.append(f"Level {level} report requires 'appendix/output.txt' with executed script output.")
            if not (appendix_dir / "sources.csv").is_file():
                errors.append(f"Level {level} report requires 'appendix/sources.csv' logging sources and access dates.")

            # V1: {{fig:id}} <-> charts.json consistency (W1: charts.json lives in the report root)
            charts_json = _find_charts_json(report_dir, appendix_dir, charts_path)
            if charts_json is None:
                # P1-6: a table-only study needs no charts.json; it is required only when the report places figures
                if FIG_MARKER_RE.search(clean_text) or charts_path is not None:
                    where = charts_path if charts_path is not None else f"{report_dir / 'charts.json'} or {appendix_dir / 'charts.json'}"
                    errors.append(f"Level {level} report requires charts.json: charts.json not found ({where}).")
            else:
                try:
                    charts_data = json.loads(charts_json.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"Invalid JSON in {charts_json}: {exc}")
                    charts_data = []
                if re.search(r"(?<![\w\"])-?(?:NaN|Infinity)(?![\w\"])", charts_json.read_text(encoding="utf-8", errors="replace")):
                    errors.append(
                        f"{charts_json.name} is not strict JSON: it contains NaN/Infinity (write with allow_nan=False and "
                        f"drop or fix the non-finite values)."
                    )
                if isinstance(charts_data, list) and charts_data:
                    try:
                        from svg_charts import validate_charts_schema

                        as_of_for_charts = _as_of_date(markdown_text) or None
                        for ch in charts_data:
                            errors.extend(validate_charts_schema(ch, as_of_date=as_of_for_charts))
                    except ImportError:  # validator run in isolation from svg_charts.py
                        pass
                    try:
                        from svg_charts import chart_warnings
                    except ImportError:  # validator run in isolation from svg_charts.py
                        chart_warnings = None  # type: ignore[assignment]
                    if chart_warnings is not None:
                        for ch in charts_data:
                            if isinstance(ch, dict):
                                warnings.extend(chart_warnings(ch))
                    chart_ids = {str(ch.get("id") or f"fig_{i + 1}") for i, ch in enumerate(charts_data)}
                    placed_figs = FIG_MARKER_RE.findall(clean_text)
                    if not placed_figs:
                        errors.append(
                            f"Level >= 2 report with {charts_json.name} must place figures inline using {{{{fig:id}}}} markers."
                        )
                    for fid in placed_figs:
                        if fid not in chart_ids:
                            errors.append(f"Unknown figure marker '{{{{fig:{fid}}}}}' not found in {charts_json.name}.")
                    for cid in sorted(chart_ids - set(placed_figs)):
                        warnings.append(
                            f"Chart '{cid}' in {charts_json.name} is not placed inline via {{{{fig:{cid}}}}} (will render in Additional Figures)."
                        )

            # W2: every {{num:key}} marker must resolve against appendix/numbers.json
            used_num_keys = sorted(set(NUM_MARKER_RE.findall(clean_text)))
            if used_num_keys:
                known_keys: set[str] = set()
                numbers_json = appendix_dir / "numbers.json"
                if numbers_json.is_file():
                    try:
                        loaded_nums = json.loads(numbers_json.read_text(encoding="utf-8"))
                        if isinstance(loaded_nums, dict):
                            known_keys = {str(k) for k in loaded_nums}
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"Invalid JSON in appendix/numbers.json: {exc}")
                for key in used_num_keys:
                    if key not in known_keys:
                        errors.append(
                            f"Unresolved marker '{{{{num:{key}}}}}': key '{key}' not found in appendix/numbers.json."
                        )

            # V2: In-text citations [@id] <-> sources.csv
            if sources_rows:
                valid_claim_ids = {(r.get("claim_id") or "").strip() for r in sources_rows if (r.get("claim_id") or "").strip()}
                sec4 = _extract_section_slice(clean_text, section_positions, "Findings")
                all_cited_ids = _extract_citation_ids(clean_text)
                sec4_cited_ids = _extract_citation_ids(sec4)
                sec4_has_numeric_cite = bool(NUMERIC_CITE_RE.search(sec4))
                if not sec4_cited_ids and not sec4_has_numeric_cite:
                    errors.append(
                        "Level >= 2 report must include in-text citations (e.g. [@C1]) in Section 4 (Findings)."
                    )
                for cid in sorted(set(all_cited_ids) - valid_claim_ids):
                    errors.append(f"In-text citation '[@{cid}]' does not match any claim_id in appendix/sources.csv.")
                for uncited in sorted(valid_claim_ids - set(all_cited_ids)):
                    msg = f"Source '{uncited}' in appendix/sources.csv is never cited in the report text."
                    (errors if level >= 3 else warnings).append(msg)

                # SRC-TIER: every tier rule matches "Tier N"; any other spelling would slip past all of them
                _canonical_tiers = {re.sub(r"\s+", " ", v).lower() for v in VALID_TIERS}
                for srow in sources_rows:
                    tier_value = (srow.get("tier") or "").strip()
                    if re.sub(r"\s+", " ", tier_value).lower() not in _canonical_tiers:
                        errors.append(
                            f"Source '{(srow.get('claim_id') or '?').strip()}' in appendix/sources.csv has tier "
                            f"'{tier_value}'; write exactly {', '.join(VALID_TIERS)} (any other spelling bypasses the tier checks)."
                        )
                # P1-5: every source row carries a valid kind
                if sources_rows and "kind" not in [c.strip() for c in sources_cols]:
                    errors.append(
                        "appendix/sources.csv has no kind column: add kind (data | literature | press | own-computation) "
                        "to every row."
                    )
                else:
                    for srow in sources_rows:
                        cid = (srow.get("claim_id") or "?").strip()
                        kind_value = (srow.get("kind") or "").strip().lower()
                        if not kind_value:
                            errors.append(f"Source '{cid}' in appendix/sources.csv has no kind.")
                        elif kind_value not in VALID_KINDS:
                            errors.append(
                                f"Source '{cid}' in appendix/sources.csv has kind '{kind_value}'; "
                                f"use one of: {', '.join(VALID_KINDS)}."
                            )

                warnings.extend(check_source_domains(sources_rows))
                meta_err, meta_warn = check_source_metadata(report_dir, _as_of_date(markdown_text), level)
                errors.extend(meta_err)
                warnings.extend(meta_warn)
                _resolved_start, _run_src = _resolve_run_start(report_dir, run_since, markdown_text)
                _run_start_dt = _resolved_start if (_resolved_start is not None and "run.json" in _run_src) else None
                sel_err, sel_warn = check_selection(
                    sources_rows, sources_cols, _as_of_date(markdown_text), level,
                    report_dir=report_dir, run_start=_run_start_dt,
                )
                errors.extend(sel_err)
                warnings.extend(sel_warn)
                warnings.extend(check_inbox(report_dir, sources_rows))
                _nums_data_for_checks: dict[str, Any] | None = None
                _nums_path = appendix_dir / "numbers.json"
                if _nums_path.is_file():
                    try:
                        _loaded_n = json.loads(_nums_path.read_text(encoding="utf-8"))
                        if isinstance(_loaded_n, dict):
                            _nums_data_for_checks = _loaded_n
                    except (OSError, json.JSONDecodeError):
                        pass
                pre_err, pre_warn = check_preregistration(
                    report_dir, clean_text, section_positions,
                    level=level, run_start=_run_start_dt, numbers_data=_nums_data_for_checks,
                )
                errors.extend(pre_err)
                warnings.extend(pre_warn)
                paper_err, paper_warn = check_papers(report_dir, sources_rows, set(_extract_citation_ids(clean_text)), level, _run_start_dt)
                errors.extend(paper_err)
                warnings.extend(paper_warn)

                # V5a: file:// rows in sources.csv must include a sha256 hash
                for row_idx, srow in enumerate(sources_rows, start=1):
                    url = (srow.get("url") or "").strip()
                    is_own = (srow.get("kind") or "").strip().lower() == "own-computation"
                    if url and not is_own and (url.startswith("file://") or "://" not in url):  # file:// or scheme-less local path
                        title = srow.get("source_title") or ""
                        sha_col = (srow.get("sha256") or "").strip()
                        has_hash = bool(SHA_HEX_RE.search(sha_col)) or (
                            "sha256" in title.lower() and bool(SHA_HEX_RE.search(title))
                        )
                        if not has_hash:
                            errors.append(
                                f"Local source row {row_idx} ('{url}') in appendix/sources.csv must include a SHA-256 hash "
                                f"(in source_title or sha256 column)."
                            )
                        else:
                            # P0-1: recompute the hash; a declared hash that no longer matches the file is an error
                            declared = _declared_sha(srow)
                            local_file = _local_source_path(url, report_dir)
                            if declared and not local_file.is_file():
                                (errors if level >= 3 else warnings).append(
                                    f"'{url}' is registered in appendix/sources.csv with sha256 {declared} but was not found "
                                    f"on disk."
                                )
                            elif declared:
                                actual = _file_sha256(local_file)
                                if not actual.startswith(declared):
                                    errors.append(
                                        f"'{url}' changed since it was registered in appendix/sources.csv: "
                                        f"SHA-256 {actual[:12]} != declared {declared}."
                                    )
            else:
                _resolved_start, _run_src = _resolve_run_start(report_dir, run_since, markdown_text)
                _run_start_dt = _resolved_start if (_resolved_start is not None and "run.json" in _run_src) else None
                paper_err, paper_warn = check_papers(
                    report_dir, sources_rows, set(_extract_citation_ids(clean_text)), level, _run_start_dt
                )
                errors.extend(paper_err)
                warnings.extend(paper_warn)

            # P0-1: hashes logged by fetch_data.py are recomputed as well
            dl_csv = appendix_dir / "download_log.csv"
            if dl_csv.is_file():
                try:
                    with dl_csv.open(encoding="utf-8-sig", newline="") as fh:
                        dl_rows = list(csv.DictReader(fh))
                except OSError:
                    dl_rows = []
                for dl in dl_rows:
                    fname = (dl.get("file") or "").strip()
                    declared_dl = SHA_HEX_RE.search((dl.get("sha256") or "").strip())
                    target = appendix_dir / "data" / fname
                    if fname and declared_dl and target.is_file():
                        actual = _file_sha256(target)
                        if not actual.startswith(declared_dl.group(0).lower()):
                            errors.append(
                                f"appendix/download_log.csv: '{fname}' changed since it was logged: "
                                f"SHA-256 {actual[:12]} != declared {declared_dl.group(0).lower()[:12]}."
                            )

            # V5b (P1-2): every file in appendix/data/ must be registered by exact relative path or declared hash
            data_dir = appendix_dir / "data"
            if data_dir.is_dir():
                registered_paths, registered_hashes = _registered_data_files(report_dir, appendix_dir, sources_rows)
                for fp in sorted(data_dir.rglob("*")):
                    if not fp.is_file() or "__pycache__" in fp.parts:
                        continue
                    rel = fp.relative_to(data_dir).as_posix()
                    if rel in registered_paths or f"data/{rel}" == WITHHELD_MANIFEST:
                        continue
                    actual = _file_sha256(fp)
                    if any(actual.startswith(h) for h in registered_hashes):
                        continue
                    warnings.append(
                        f"Orphan data file 'appendix/data/{rel}' is not logged in "
                        f"appendix/download_log.csv or appendix/sources.csv."
                    )

            # V5c: data_attempts.csv canonical columns check (D2)
            attempts_csv = appendix_dir / "data_attempts.csv"
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8", newline="") as fh:
                        reader = csv.reader(fh)
                        header = [c.strip() for c in next(reader, [])]
                    missing_cols = [c for c in CANONICAL_DATA_ATTEMPTS_COLS if c not in header]
                    if missing_cols:
                        errors.append(
                            f"appendix/data_attempts.csv is missing canonical column(s): {', '.join(missing_cols)}."
                        )
                except OSError as exc:
                    errors.append(f"Unable to read appendix/data_attempts.csv: {exc}")

            # F2: an own computation (the report's own code) can never be Tier 1 evidence
            for srow in sources_rows:
                if (srow.get("kind") or "").strip().lower() == "own-computation" and re.search(
                    r"\bTier\s*1\b", srow.get("tier") or "", re.IGNORECASE
                ):
                    errors.append(
                        f"Source '{(srow.get('claim_id') or '?').strip()}' has kind=own-computation but tier Tier 1; "
                        f"the report's own computation is not independent evidence (use Tier 2/3 or a different kind)."
                    )

            # F1: source described as retrieved/full text although data_attempts.csv logs a failed attempt for its URL
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8", newline="") as fh:
                        attempt_rows = list(csv.DictReader(fh))
                except OSError:
                    attempt_rows = []
                ok_outcomes = {"used", "ok", "success", "succeeded", "retrieved"}
                for srow in sources_rows:
                    surl = (srow.get("url") or "").strip()
                    stitle = (srow.get("source_title") or "").lower()
                    if not surl or not re.search(r"full[\s-]?text|open[\s-]access|retrieved", stitle):
                        continue
                    for arow in attempt_rows:
                        outcome = (arow.get("outcome") or "").strip().lower()
                        touches = surl in (arow.get("query_or_endpoint") or "") or surl in (arow.get("source_tried") or "")
                        if touches and outcome and outcome not in ok_outcomes:
                            warnings.append(
                                f"Source '{(srow.get('claim_id') or '?').strip()}' is described as full text/retrieved but "
                                f"appendix/data_attempts.csv logs a failed attempt for the same URL ({surl}): "
                                f"'{arow.get('outcome')}'."
                            )
                            break

            # P2: every subagent gate leaves a trace in appendix/gates/ (a manual record when no subagents exist)
            gates_dir = appendix_dir / "gates"
            gate_sink = errors if level == 3 else warnings
            rv_path = gates_dir / "reviewer.md"
            if rv_path.is_file():  # a reviewer gate that exists is bound to analysis.py at any level
                _check_analysis_anchor(
                    rv_path.read_text(encoding="utf-8", errors="replace"), report_dir, clean_text, section_positions, gate_sink
                )
            for gate in GATE_FILES:
                if gate == "reviewer" and level != 3:  # Reviewer #2 is dispatched at Level 3 only
                    continue
                gpath = gates_dir / f"{gate}.md"
                gtext = gpath.read_text(encoding="utf-8", errors="replace") if gpath.is_file() else ""
                if not gtext.strip():
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is missing or empty; save the {gate.replace('_', '-')} gate output "
                        f"(or the manual checks that replaced it) there."
                    )
                    continue
                if len(gtext.strip()) < GATE_MIN_CHARS:
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is under {GATE_MIN_CHARS} characters; save the gate's full answer, "
                        f"not a placeholder."
                    )
                missing = [label for label, pattern in GATE_MARKERS[gate] if not re.search(pattern, gtext, re.MULTILINE | re.IGNORECASE)]
                if missing:
                    gate_sink.append(
                        f"appendix/gates/{gate}.md is missing marker(s) its prompt requires: {', '.join(missing)} "
                        f"(see references/agents/{gate.replace('_', '-')}.md, Output section)."
                    )
                _check_gate_binding(gate, gtext, report_dir, clean_text, section_positions, gate_sink, warnings, errors=errors)
                if gate == "qa" and not re.search(r"^QA:\s*PASS\b", gtext, re.MULTILINE):
                    if "gates/qa.md" not in markdown_text:
                        gate_sink.append(
                            "appendix/gates/qa.md has no 'QA: PASS' line; fix the failed checks, or name each accepted "
                            "FAIL with its justification in the report (cite appendix/gates/qa.md in Section 7)."
                        )
                if (
                    gate == "source_verifier"
                    and re.search(r"^\s*SOURCE-VERIFIER:\s*FAIL\b", gtext, re.MULTILINE)
                    and "gates/source_verifier.md" not in markdown_text
                ):
                    gate_sink.append(
                        "appendix/gates/source_verifier.md ends in SOURCE-VERIFIER: FAIL; fix the problems and re-run the gate, or "
                        "name each accepted problem with its justification in the report (cite appendix/gates/source_verifier.md in Section 7)."
                    )

            # C8: gate files are embedded in report.html, so they must not quote home paths or literal markers
            if gates_dir.is_dir():
                for gpath in sorted(gates_dir.glob("*.md")):
                    gtext = gpath.read_text(encoding="utf-8", errors="replace")
                    if HOME_PATH_RE.search(gtext):
                        gate_sink_any = errors if level == 3 else warnings
                        gate_sink_any.append(
                            f"appendix/gates/{gpath.name} quotes a home-directory path; it is embedded in report.html, "
                            f"so report counts instead (e.g. 'home-directory paths in report.html: 0')."
                        )
                    non_quote_text = "\n".join(
                        ln for ln in gtext.splitlines() if not re.match(r"^\s*QUOTE:", ln)
                    )
                    if re.search(r"\{\{(?:num|fig):", non_quote_text):
                        (errors if level == 3 else warnings).append(
                            f"appendix/gates/{gpath.name} contains a literal {{{{num:…}}}}/{{{{fig:…}}}} marker; write "
                            f"'number placeholder' or 'figure marker' instead."
                        )

            # P1: a limitation cannot rest on attempts inherited from an earlier run (needs attempted_utc column)
            if attempts_csv.is_file():
                try:
                    with attempts_csv.open(encoding="utf-8-sig", newline="") as fh:
                        att_reader = csv.DictReader(fh)
                        att_cols = [c.strip() for c in (att_reader.fieldnames or [])]
                        att_rows = list(att_reader)
                except OSError:
                    att_cols, att_rows = [], []
                start, start_src = _resolve_run_start(report_dir, run_since, markdown_text)
                since = start.strftime("%Y-%m-%dT%H:%M:%SZ") if start else ""
                if start is not None and start_src == "report date":
                    warnings.append(
                        "no appendix/run.json: the run start is taken from the report date (day granularity), so a failure "
                        "logged earlier the same day counts as fresh; stamp the run with `local_data.py run-start` in Stage 0."
                    )
                inherit_sink = errors if level == 3 else warnings
                if "attempted_utc" not in att_cols:
                    inherit_sink.append(
                        "appendix/data_attempts.csv has no attempted_utc column: every attempt is treated as inherited; "
                        "add the column and re-run the rungs behind each limitation."
                    )
                elif not since:
                    warnings.append("cannot determine run start; pass --run-since YYYY-MM-DD")
                else:
                    ok_out = {"used", "ok", "success", "succeeded", "retrieved"}
                    limits_text = _extract_section_slice(clean_text, section_positions, "Limitations & Open Questions")
                    leaning_lines = [ln for ln in limits_text.splitlines() if ln.strip()] + [
                        ln for ln in clean_text.splitlines() if re.search(r"\b(?:Deferred|Diferida)\b", ln, re.IGNORECASE)
                    ]
                    fresh_targets: set[str] = set()
                    stale_targets: dict[str, str] = {}
                    for arow in att_rows:
                        outcome = (arow.get("outcome") or "").strip().lower()
                        if not outcome or outcome in ok_out:
                            continue
                        att_target = (arow.get("target_series") or arow.get("source_tried") or "?").strip()
                        stamp = (arow.get("attempted_utc") or "").strip()
                        stamp_dt = _parse_utc(stamp)
                        if stamp_dt is not None and stamp_dt >= start:
                            fresh_targets.add(att_target)
                            continue
                        # C3: only failures that end in a limitation (no real fallback) or that the report leans on
                        fallback = (arow.get("fallback_used") or "").strip().lower()
                        ends_in_limitation = not fallback or fallback.startswith(LIMITATION_FALLBACKS)
                        named = _named_in_any(att_target, leaning_lines)
                        if ends_in_limitation or named:
                            stale_targets.setdefault(att_target, stamp or "no date")
                    for att_target, stamp in sorted(stale_targets.items()):
                        if att_target in fresh_targets:
                            continue
                        inherit_sink.append(
                            f"Data attempt for '{att_target}' in appendix/data_attempts.csv is inherited from an earlier run "
                            f"({stamp} < run start {since}); re-run the rung in this session before relying on the limitation."
                        )

            # V6: Hygiene warnings (__pycache__, .pyc, 0-byte files)
            pycache_found = False
            for fp in sorted(appendix_dir.rglob("*"), key=lambda p: p.relative_to(appendix_dir).parts):
                if "__pycache__" in fp.parts or fp.suffix == ".pyc":
                    pycache_found = True
                    continue
                if fp.is_file() and fp.stat().st_size == 0:
                    warnings.append(f"0-byte file detected in appendix: 'appendix/{fp.relative_to(appendix_dir).as_posix()}'.")
            if pycache_found:
                warnings.append(
                    "Python bytecode artifacts (__pycache__ / .pyc) found in appendix/; run scripts with 'python3 -B'."
                )

            # P11: Optional verdict-number cross-check against appendix/output.txt
            output_txt = appendix_dir / "output.txt"
            if output_txt.is_file() and "{{num:" not in markdown_text:
                vm = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:\**\s*(.+)", clean_text, re.IGNORECASE)
                if vm:
                    out_text = output_txt.read_text(encoding="utf-8", errors="replace")
                    verdict_nums = re.findall(r"\b\d+(?:[.,]\d+)?\b", vm.group(1))
                    missing_nums = [
                        n for n in verdict_nums
                        if len(n) >= 2 and n not in out_text and n.replace(",", ".") not in out_text
                    ]
                    if missing_nums:
                        warnings.append(
                            f"Calibrated Verdict number(s) not found literally in appendix/output.txt: {', '.join(missing_nums[:5])}."
                        )

            # P3/C5: figures that come from output.txt should come through {{num:key}} (numbers.json), not be retyped
            if output_txt.is_file():
                out_txt = output_txt.read_text(encoding="utf-8", errors="replace")

                def _typed_from_output(section_text: str, pattern: re.Pattern[str]) -> set[str]:
                    body = re.sub(r"^#{1,6}\s.*$|\[@[^\]]+\]|\{\{[^}]+\}\}", "", section_text, flags=re.MULTILINE)
                    body = SECTION_REF_RE.sub("", body)
                    return {
                        t
                        for t in pattern.findall(body)
                        if not re.fullmatch(r"(?:19|20)\d\d", t)
                        and re.search(rf"(?<![\d.,]){re.escape(t)}(?!\d)", out_txt)
                    }

                summary = _extract_section_slice(clean_text, section_positions, "Executive Summary")
                typed_summary = _typed_from_output(summary, SUMMARY_NUM_RE)
                if len(typed_summary) >= MIN_TYPED_SUMMARY and not NUM_MARKER_RE.search(summary):
                    (errors if level == 3 else warnings).append(
                        f"Calibrated Verdict / Section 1 retypes {len(typed_summary)} figure(s) from appendix/output.txt "
                        f"({', '.join(sorted(typed_summary)[:4])}) and uses no {{{{num:key}}}} placeholder; export them to "
                        f"appendix/numbers.json and write {{{{num:key}}}}."
                    )

                findings = _extract_section_slice(clean_text, section_positions, "Findings")
                typed = _typed_from_output(findings, HARDCODED_NUM_RE)
                used = len(NUM_MARKER_RE.findall(markdown_text))
                if len(typed) >= MIN_TYPED_NUMBERS and used / (used + len(typed)) < MIN_MARKER_SHARE:
                    warnings.append(
                        f"numbers.json coverage is low: {len(typed)} number(s) in Section 4 appear in appendix/output.txt "
                        f"but only {used} {{{{num:key}}}} marker(s) are used (e.g. {', '.join(sorted(typed)[:3])}); "
                        f"write them as {{{{num:key}}}} so the text follows the analysis."
                    )

                # M25: numeric closure on Section 4 tables (catch fabricated stats absent from output.txt/numbers.json)
                _nums_for_closure: dict[str, Any] | None = None
                _nf = appendix_dir / "numbers.json"
                if _nf.is_file():
                    try:
                        _ln = json.loads(_nf.read_text(encoding="utf-8"))
                        if isinstance(_ln, dict):
                            _nums_for_closure = _ln
                    except (OSError, json.JSONDecodeError):
                        pass
                nc_err, nc_warn = check_numeric_closure(clean_text, section_positions, out_txt, _nums_for_closure, level)
                errors.extend(nc_err)
                warnings.extend(nc_warn)
                _charts_file = _find_charts_json(report_dir, appendix_dir, charts_path)
                if _charts_file is not None:
                    try:
                        _charts_loaded = json.loads(_charts_file.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        _charts_loaded = None  # reported by the charts.json checks above
                    cc_err, cc_warn = check_caption_closure(_charts_loaded, out_txt, _nums_for_closure, level)
                    errors.extend(cc_err)
                    warnings.extend(cc_warn)

    # 7. Level 3 Reviewer #2 Disposition Table & Deferred -> Data Attempts cross-check
    if level == 3:
        has_r2_heading = bool(
            re.search(
                r"(?:Reviewer\s*#?2|Revisor\s*#?2|Disposition|Disposici[oó]n)",
                clean_text,
                re.IGNORECASE,
            )
        )
        has_r2_action = bool(
            re.search(
                r"\|\s*[`*]{0,2}(?:Fixed|Refuted|Deferred|Corregida|Refutada|Diferida)[`*]{0,2}\b",
                clean_text,
                re.IGNORECASE,
            )
        )
        if not (has_r2_heading and has_r2_action):
            errors.append(
                "Level 3 report requires a Reviewer #2 Disposition table recording each critique "
                "and its action (Fixed / Refuted / Deferred)."
            )
        reviewer_gate = report_dir / "appendix" / "gates" / "reviewer.md" if report_dir is not None else None
        if reviewer_gate is not None and reviewer_gate.is_file():
            n_items = reviewer_items(reviewer_gate.read_text(encoding="utf-8", errors="replace"))
            n_rows = disposition_rows(clean_text)  # same scope as the existence check above: the table belongs in Section 5
            if n_items and n_rows != n_items:
                errors.append(
                    f"Reviewer #2 raised {n_items} item(s) in appendix/gates/reviewer.md but the Disposition Table has "
                    f"{n_rows} row(s) with an action; give every critique its own row (Fixed / Refuted / Deferred)."
                )

        has_deferred = bool(
            re.search(
                r"\|\s*[`*]{0,2}(?:Deferred|Diferida)[`*]{0,2}\b",
                clean_text,
                re.IGNORECASE,
            )
        )
        if has_deferred:
            has_attempts_file = report_dir is not None and (report_dir / "appendix" / "data_attempts.csv").is_file()
            sec3 = _extract_section_slice(clean_text, section_positions, "Methodology & Evidence Standards")
            has_attempts_table = bool(
                re.search(r"(?:Data\s+Attempts|Intentos\s+de\s+datos|Source\s+Tried|Fuente\s+probada)", sec3, re.IGNORECASE)
            )
            if not (has_attempts_file or has_attempts_table):
                errors.append(
                    "Level 3 report marks Reviewer #2 critique(s) as Deferred/Diferida without a logged "
                    "'appendix/data_attempts.csv' or Data Attempts table in Section 3."
                )

    return errors, warnings


def validate_report(
    markdown_text: str,
    *,
    level: int | None = None,
    report_dir: Path | None = None,
    charts_path: Path | None = None,
    run_since: str | None = None,
) -> list[str]:
    """Return a list of validation error strings for a Heurisma markdown report (empty list = valid)."""
    errors, _ = validate_report_full(
        markdown_text, level=level, report_dir=report_dir, charts_path=charts_path, run_since=run_since
    )
    return errors


REPRODUCED_FILES = ("appendix/output.txt", "appendix/numbers.json", "charts.json")
_ANALYSIS_CMD_RE = re.compile(r"^\s*(?:\$\s*)?(python3?\s+.*analysis\.py.*?)\s*$")


def _readme_analysis_command(report_dir: Path) -> str:
    readme = report_dir / "appendix" / "README.md"
    if not readme.is_file():
        return ""
    for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _ANALYSIS_CMD_RE.match(line.replace("`", ""))
        if m:
            return m.group(1)
    return ""


def reproduce(report_dir: Path, command: str | None = None, timeout: int = 300) -> list[str]:
    """Re-run appendix/analysis.py in a temporary copy and compare output.txt, numbers.json and charts.json.

    The command comes from ``appendix/README.md`` (first ``python3 … analysis.py`` line) or ``command``. The three
    artifacts are deleted from the copy first, so a file the command does not regenerate is reported, never passed.
    NOTE: this executes the report's own analysis.py; use it on reports you trust.
    """
    import hashlib
    import os
    import shlex
    import shutil
    import subprocess
    import tempfile

    cmd = command or _readme_analysis_command(report_dir)
    if not cmd:
        return ["reproduce: no analysis.py command found in appendix/README.md (pass --reproduce-cmd '…')."]
    try:
        tokens = shlex.split(cmd)
    except ValueError as exc:
        return [f"reproduce: cannot parse the command ({exc})."]
    redirect = None
    if ">" in tokens:
        i = tokens.index(">")
        redirect = tokens[i + 1] if i + 1 < len(tokens) else None
        tokens = tokens[:i]
    if not tokens or tokens[0] not in ("python", "python3"):
        return ["reproduce: unsupported command; use 'python3 -B appendix/analysis.py [args] [> appendix/output.txt]'."]
    argv = [sys.executable, "-B"] + [t for t in tokens[1:] if t != "-B"]
    if not any(t.endswith("analysis.py") for t in argv):
        return ["reproduce: the command does not run an analysis.py script."]
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "run"
        shutil.copytree(report_dir, work, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for rel in REPRODUCED_FILES:
            (work / rel).unlink(missing_ok=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONPATH=os.pathsep.join(
            [str(Path(__file__).resolve().parent), os.environ.get("PYTHONPATH", "")]))
        try:
            res = subprocess.run(
                argv, cwd=work, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env
            )
        except subprocess.TimeoutExpired:
            return [f"reproduce: appendix/analysis.py failed (timed out after {timeout}s)."]
        if res.returncode != 0:
            tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or [""]
            return [f"reproduce: appendix/analysis.py failed (exit {res.returncode}): {tail[0][:200]}"]
        if redirect:
            target = work / redirect
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(res.stdout.replace("\r\n", "\n").encode("utf-8"))
        for rel in REPRODUCED_FILES:
            original = report_dir / rel
            if not original.is_file():
                continue
            regenerated = work / rel
            if not regenerated.is_file():
                errors.append(f"reproduce: {rel} was not regenerated by the command (add its output flag or redirect).")
                continue
            a = hashlib.sha256(original.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            b = hashlib.sha256(regenerated.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            if a != b:
                errors.append(f"reproduce: {rel} differs after re-running appendix/analysis.py (sha256 {a[:12]} != {b[:12]}).")
    return errors


def _verdict_line(report_md: Path) -> str:
    text = report_md.read_text(encoding="utf-8", errors="replace") if report_md.is_file() else ""
    m = re.search(r"(?:Calibrated Verdict|Veredicto calibrado)\s*:?\**\s*:?\**\s*(.+)", text, re.IGNORECASE)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def diff_runs(a_dir: Path, b_dir: Path) -> list[str]:
    """Human-readable differences between two runs of the same brief: data files, numbers.json and the verdict."""
    lines: list[str] = []

    def data_map(root: Path) -> dict[str, str]:
        d = root / "appendix" / "data"
        return {fp.relative_to(d).as_posix(): _file_sha256(fp) for fp in sorted(d.rglob("*")) if fp.is_file()} if d.is_dir() else {}

    da, db = data_map(a_dir), data_map(b_dir)
    data_lines = [f"  changed  {k}  ({da[k][:12]} -> {db[k][:12]})" for k in sorted(da.keys() & db.keys()) if da[k] != db[k]]
    data_lines += [f"  added    {k}" for k in sorted(db.keys() - da.keys())]
    data_lines += [f"  removed  {k}" for k in sorted(da.keys() - db.keys())]
    if data_lines:
        lines += ["data files:"] + data_lines

    def numbers(root: Path) -> dict[str, object]:
        f = root / "appendix" / "numbers.json"
        try:
            data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
        except json.JSONDecodeError:
            data = {}
        return data if isinstance(data, dict) else {}

    na, nb = numbers(a_dir), numbers(b_dir)
    num_lines = [f"  {k}: {na[k]} -> {nb[k]}" for k in sorted(na.keys() & nb.keys()) if na[k] != nb[k]]
    num_lines += [f"  added    {k} = {nb[k]}" for k in sorted(nb.keys() - na.keys())]
    num_lines += [f"  removed  {k} (was {na[k]})" for k in sorted(na.keys() - nb.keys())]
    if num_lines:
        lines += ["numbers.json:"] + num_lines

    va, vb = _verdict_line(a_dir / "report.md"), _verdict_line(b_dir / "report.md")
    if va != vb:
        lines += ["verdict changed:", f"  - {va}", f"  + {vb}"]
    return lines or ["no differences between the two runs (data files, numbers.json, verdict)."]


def _json_items(messages: list[str], severity: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for msg in messages:
        code, file = classify_message(msg)
        items.append({"severity": severity, "code": code, "file": file, "line": None, "message": msg})
    return items


def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Validate a Heurisma scientific inquiry report against structural, content, provenance, and epistemic gates."
    )
    parser.add_argument("--version", action="version", version=f"validate_report.py {__version__}")
    parser.add_argument("report_path", type=Path, help="Path to the Markdown report file to validate.")
    parser.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3),
        default=None,
        help="Optional depth level (2 checks appendix/, figures, citations, provenance; 3 also checks Reviewer #2 disposition table).",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Optional path to rendered report.html to verify alongside the Markdown report.",
    )
    parser.add_argument(
        "--charts",
        type=Path,
        default=None,
        help="Optional explicit path to charts.json (default: <report dir>/charts.json, then appendix/charts.json).",
    )
    parser.add_argument(
        "--gate-hash",
        choices=GATE_FILES,
        default=None,
        help="Print the hash a gate must declare as REVIEWED-SHA256 for the current files, and exit.",
    )
    parser.add_argument(
        "--gate-header",
        choices=GATE_FILES,
        default=None,
        help="Print the gate binding header (MODE, REVIEWED-SHA256, real REVIEWED-UTC; plus ANALYSIS-SHA256 for reviewer) and exit.",
    )
    parser.add_argument(
        "--mode",
        choices=("subagent", "self-review"),
        default="subagent",
        help="Gate mode used with --gate-header (default: subagent).",
    )
    parser.add_argument(
        "--run-since",
        default=None,
        metavar="YYYY-MM-DD",
        help="Start date of this run; data_attempts.csv failures older than it count as inherited "
        "(default: first ISO date in the report's first 20 lines).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat validation warnings as hard errors (exit code 1).",
    )
    parser.add_argument(
        "--reproduce",
        action="store_true",
        help="Re-run appendix/analysis.py in a temporary copy (command from appendix/README.md) and compare output.txt, "
        "numbers.json and charts.json. Executes the report's own code: use on reports you trust.",
    )
    parser.add_argument("--reproduce-cmd", default=None, help="Override the command used by --reproduce.")
    parser.add_argument(
        "--diff",
        type=Path,
        default=None,
        metavar="OTHER_RUN",
        help="Compare this report folder with another run (folder or its report.md): data files, numbers.json, verdict.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one JSON object {version, passed, errors, warnings} (items: severity, code, file, line, message).",
    )
    args = parser.parse_args(argv)

    if not args.report_path.is_file():
        print(f"Error: File not found: {args.report_path}", file=sys.stderr)
        return 1

    if args.gate_hash:
        print(gate_hash(args.report_path.parent, args.gate_hash))
        return 0

    if args.gate_header:
        from datetime import datetime, timezone

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"MODE: {args.mode}")
        print(f"REVIEWED-SHA256: {gate_hash(args.report_path.parent, args.gate_header)}")
        print(f"REVIEWED-UTC: {now_utc}")
        if args.gate_header == "reviewer":
            anchor = _analysis_anchor(args.report_path.parent)
            if anchor:
                print(f"ANALYSIS-SHA256: {anchor}")
        return 0

    if args.diff is not None:
        other = args.diff.parent if args.diff.is_file() else args.diff
        if not (other / "report.md").is_file():
            print(f"Error: {args.diff} is not a Heurisma run folder (no report.md).", file=sys.stderr)
            return 1
        print(f"Comparing {args.report_path.parent} with {other}")
        print("\n".join(diff_runs(args.report_path.parent, other)))
        return 0

    content = args.report_path.read_text(encoding="utf-8")
    errors, warnings = validate_report_full(
        content, level=args.level, report_dir=args.report_path.parent, charts_path=args.charts, run_since=args.run_since
    )
    if args.reproduce or args.reproduce_cmd:
        errors.extend(reproduce(args.report_path.parent, args.reproduce_cmd))
    if args.html is not None:
        html_errors, html_warnings = validate_html_full(args.html)
        errors.extend(html_errors)
        warnings.extend(html_warnings)
        warnings.extend(check_html_freshness(args.html, args.report_path, args.charts))

    if args.json:
        failed = bool(errors) or (args.strict and bool(warnings))
        print(
            json.dumps(
                {
                    "version": __version__,
                    "passed": not failed,
                    "strict": bool(args.strict),
                    "errors": _json_items(errors, "error"),
                    "warnings": _json_items(warnings, "warning"),
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return 1 if failed else 0

    if warnings:
        print(f"Heurisma report warnings ({len(warnings)}):", file=sys.stderr)
        for idx, warn in enumerate(warnings, start=1):
            print(f"  [WARN {idx}] {warn}", file=sys.stderr)

    if errors or (args.strict and warnings):
        total = len(errors) + (len(warnings) if args.strict else 0)
        print(f"Heurisma report validation FAILED ({total} violation(s)):", file=sys.stderr)
        for idx, err in enumerate(errors, start=1):
            print(f"  {idx}. {err}", file=sys.stderr)
        return 1

    print(f"Heurisma report validation PASSED: {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
