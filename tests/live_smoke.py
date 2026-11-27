#!/usr/bin/env python3
"""Optional live-API smoke check for the paper-database connectors (excluded from CI).

Queries each real upstream provider (OpenAlex, Crossref, Europe PMC, arXiv, and Unpaywall when
``HEURISMA_MAILTO`` is set) into a temporary directory and checks that each provider's ``parse()``
still understands the live response shape. When ``HEURISMA_MAILTO`` is set, also checks the live
Unpaywall payload against ``tests/fixtures/papers/unpaywall.json`` (which was written from docs).

Usage:
    python3 -B tests/live_smoke.py
    HEURISMA_OPENALEX_KEY=... HEURISMA_MAILTO=alias@example.org python3 -B tests/live_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "heurisma" / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "papers"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import formal_math  # noqa: E402
import papers  # noqa: E402
from providers import arxiv, base, crossref, europepmc, openalex, unpaywall  # noqa: E402

SAMPLE_DOI = "10.1038/s41586-024-07500-2"


def _check_provider(name: str, fn) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    try:
        detail = fn()
        return ("PASS", f"{name}: {detail}")
    except Exception as exc:  # noqa: BLE001
        return ("FAIL", f"{name}: {base.redact(str(exc), os.environ)}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    if (os.environ.get("HEURISMA_OFFLINE") or "").strip().lower() in {"1", "true", "yes", "on"}:
        print("live_smoke: skipped (HEURISMA_OFFLINE is enabled).")
        return 0

    results: list[tuple[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="heurisma-live-smoke-") as tmp:
        appendix = Path(tmp) / "appendix"
        ctx = base.Context(appendix)

        def check_openalex() -> str:
            recs = openalex.search(ctx, "hybrid working from home", limit=2)
            if not recs:
                raise RuntimeError("0 search results returned")
            rec = openalex.lookup(ctx, SAMPLE_DOI)
            if rec is None or rec["doi"] != SAMPLE_DOI:
                raise RuntimeError(f"lookup did not return {SAMPLE_DOI}")
            return f"search={len(recs)} hits, lookup={rec['doi']} ({rec['work_type']}, {rec['year']})"

        def check_crossref() -> str:
            rec = crossref.lookup(ctx, SAMPLE_DOI)
            if rec is None or rec["doi"] != SAMPLE_DOI:
                raise RuntimeError(f"lookup did not return {SAMPLE_DOI}")
            return f"lookup={rec['doi']} ({rec['work_type']}, {rec['year']})"

        def check_europepmc() -> str:
            recs = europepmc.search(ctx, "hybrid working", limit=2)
            if not recs:
                raise RuntimeError("0 search results returned")
            return f"search={len(recs)} hits, first={recs[0]['doi']} ({recs[0]['work_type']})"

        def check_arxiv() -> str:
            recs = arxiv.search(ctx, "hybrid work", limit=2)
            if not recs:
                raise RuntimeError("0 search results returned")
            return f"search={len(recs)} hits, first={recs[0]['doi']} ({recs[0]['work_type'] or 'published-doi'})"

        def check_unpaywall() -> str:
            loc = unpaywall.oa_location(ctx, SAMPLE_DOI)
            if loc is None or not loc.get("pdf_url"):
                raise RuntimeError(f"no OA PDF location returned for {SAMPLE_DOI}")
            # Verify the cached raw payload shape matches the fixture keys
            raw_files = sorted((appendix / "data" / "papers" / "raw").glob("unpaywall-*.json"))
            if not raw_files:
                raise RuntimeError("unpaywall raw cache file missing")
            live_data = json.loads(raw_files[-1].read_text(encoding="utf-8"))
            fixture = json.loads((FIXTURES / "unpaywall.json").read_text(encoding="utf-8"))
            missing_top = [k for k in ("doi", "is_oa", "best_oa_location") if k not in live_data]
            live_best = live_data.get("best_oa_location") or {}
            missing_best = [k for k in fixture.get("best_oa_location", {}) if k not in live_best]
            if missing_top or missing_best:
                raise RuntimeError(f"fixture drift: missing top={missing_top}, best_oa_location={missing_best}")
            return f"oa_location OK (version={loc['version']}, license={loc['license']}), fixture shape matches"

        results.append(_check_provider("openalex", check_openalex))
        results.append(_check_provider("crossref", check_crossref))
        results.append(_check_provider("europepmc", check_europepmc))
        results.append(_check_provider("arxiv", check_arxiv))

        if ctx.mailto:
            results.append(_check_provider("unpaywall", check_unpaywall))
        else:
            results.append(("SKIP", "unpaywall: set HEURISMA_MAILTO to verify Unpaywall live and check fixtures/papers/unpaywall.json"))

        # Offline replay over all raw responses fetched in this smoke run
        results.append(_check_provider("replay", lambda: f"{len(papers.replay(ctx))} discrepancies"))

        # P-12: Optional live elan/lake/lean kernel smoke check (skips cleanly if lake is not installed)
        lake_bin, lean_bin = formal_math.find_lake()
        if lake_bin and lean_bin:
            def check_live_lean() -> str:
                formal_math.init_project(
                    appendix,
                    "smoke_thm",
                    theorem_name="smoke_zero",
                    statement="(n : Nat) : n + 0 = n",
                )
                proj = appendix / "formal" / "smoke_thm"
                (proj / "Solution.lean").write_text(
                    "import Challenge\n"
                    "namespace Solution\n"
                    "theorem smoke_zero (n : Nat) : n + 0 = n := by\n"
                    "  exact Nat.add_zero n\n"
                    "end Solution\n",
                    encoding="utf-8",
                )
                res = formal_math.check_project(appendix, "smoke_thm", timeout=120)
                if res.get("status") not in ("kernel-verified", "comparator-verified"):
                    raise RuntimeError(f"unexpected status={res.get('status')!r}")
                return f"status={res['status']}, mode={res.get('verification_mode')}, lean={res.get('lean_version')}"

            results.append(_check_provider("lean4_lake", check_live_lean))
        else:
            results.append(("SKIP", "lean4_lake: local `lake`/`lean` not installed (optional toolchain)"))

        for w in ctx.warnings:
            print(f"Warning: {w}", file=sys.stderr)

    failed = 0
    for status, msg in results:
        print(f"[{status}] {msg}")
        if status == "FAIL":
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
