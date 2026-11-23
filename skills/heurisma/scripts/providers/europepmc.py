"""Europe PMC (https://europepmc.org/RestfulWebService): biomedicine and the life sciences, open-access full text.

No key. Full text exists only for works flagged ``OPEN_ACCESS:Y``; ``abstractText`` and the publication type may be
missing from a record, so an empty abstract is a normal outcome and is recorded as such.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode

from providers import base
from providers.base import Context, Record

NAME = "europepmc"
DEFAULT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


_PMCID = re.compile(r"PMC\d{1,12}")


def normalize(item: dict[str, Any]) -> Record:
    rec = base.empty_record()
    source, ident = str(item.get("source") or ""), str(item.get("id") or "")
    rec["doi"] = base.normalize_doi(item.get("doi")) or (f"epmc:{source.lower()}:{ident}" if ident else "")
    title = item.get("title")
    rec["title"] = base.clean_text(base.jats_to_text(title) if isinstance(title, str) else "")
    people = [p for p in base.as_list(base.as_dict(item.get("authorList")).get("author")) if isinstance(p, dict)]
    if people:
        rec["first_author"] = base.clean_text(people[0].get("fullName"), 200)
        rec["n_authors"] = str(len(people))
    else:
        names = [a.strip() for a in str(item.get("authorString") or "").split(",") if a.strip()]
        rec["first_author"] = base.clean_text(names[0].rstrip("."), 200) if names else ""
        rec["n_authors"] = str(len(names)) if names else ""
    rec["year"] = base.clean_text(str(item.get("pubYear") or ""), 8)
    rec["venue"] = base.clean_text(base.as_dict(base.as_dict(item.get("journalInfo")).get("journal")).get("title"), 200)
    types = [str(t).lower() for t in base.as_list(base.as_dict(item.get("pubTypeList")).get("pubType"))]
    preprint = source == "PPR" or any("preprint" in t for t in types)
    rec["work_type"] = "preprint" if preprint else "article"
    if any("retracted publication" in t for t in types):
        rec["is_retracted"] = "true"
    if item.get("isOpenAccess") in ("Y", "N"):
        rec["is_oa"] = "true" if item["isOpenAccess"] == "Y" else "false"
    abstract = item.get("abstractText")
    rec["abstract"] = base.jats_to_text(abstract) if isinstance(abstract, str) else ""
    rec["abstract_sha256"] = base.sha256_text(rec["abstract"]) if rec["abstract"] else ""
    pmcid = item.get("pmcid")
    rec["pmcid"] = pmcid if isinstance(pmcid, str) and _PMCID.fullmatch(pmcid) else ""  # it becomes part of a URL: only the PMC form
    rec["oa_url"] = ""
    rec["providers"] = NAME
    rec["via"] = "api"
    rec["retrieved_utc"] = base.local_data.utc_now()
    return rec


def search(ctx: Context, query: str, *, limit: int = 25, filters: dict[str, Any] | None = None) -> list[Record]:
    q = f"({query}) AND OPEN_ACCESS:Y" if filters and filters.get("open_access") is True else query
    params = {"query": q, "format": "json", "pageSize": str(max(1, min(int(limit), 100))), "resultType": "core"}
    return parse(ctx.get(NAME, f"{ctx.base_url(NAME, DEFAULT_URL)}/search?{urlencode(params)}"))


def parse(body: bytes) -> list[Record]:
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise base.ProviderUnavailable(f"europepmc returned an unreadable response ({exc})") from exc
    results = ((data.get("resultList") or {}).get("result")) if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise base.ProviderUnavailable("europepmc: the response has no resultList.result")
    try:
        return [normalize(r) for r in results if isinstance(r, dict)]
    except (TypeError, AttributeError, KeyError, IndexError, ValueError) as exc:
        raise base.ProviderUnavailable(f"europepmc: a work in the response is malformed ({type(exc).__name__}: {exc})") from exc


def lookup(ctx: Context, doi: str) -> Record | None:
    found = [r for r in search(ctx, f'DOI:"{doi}"', limit=1) if r["doi"] == doi]
    return found[0] if found else None
