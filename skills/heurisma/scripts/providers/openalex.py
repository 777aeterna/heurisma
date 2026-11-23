"""OpenAlex (https://api.openalex.org): the broadest catalogue; ``type``, ``is_retracted`` and open-access fields.

A free key (``HEURISMA_OPENALEX_KEY``) raises the daily budget; without one small requests still work and a warning
says so. Only named fields are read: free text such as ``meta.notice`` is never copied, let alone obeyed.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode

from providers import base
from providers.base import Context, Record

NAME = "openalex"
DEFAULT_URL = "https://api.openalex.org"
SELECT = (
    "id,doi,title,publication_year,type,is_retracted,cited_by_count,language,has_fulltext,abstract_inverted_index,"
    "authorships,primary_location,open_access"
)


def _credential(ctx: Context) -> dict[str, str]:
    if ctx.key:
        return {"api_key": ctx.key}
    ctx.warn("openalex: no API key (HEURISMA_OPENALEX_KEY); requests share a small free daily budget. A free key is advisable.")
    return {}


def normalize(work: dict[str, Any]) -> Record:
    rec = base.empty_record()
    oa_id = str(work.get("id") or "").rsplit("/", 1)[-1]
    rec["doi"] = base.normalize_doi(work.get("doi")) or (f"openalex:{oa_id.lower()}" if oa_id else "")
    rec["title"] = base.clean_text(work.get("title"))
    authors = [a for a in base.as_list(work.get("authorships")) if isinstance(a, dict)]
    rec["first_author"] = base.clean_text(base.as_dict(authors[0].get("author")).get("display_name"), 200) if authors else ""
    rec["n_authors"] = str(len(authors))
    rec["year"] = base.clean_text(str(work.get("publication_year") or ""), 8)
    loc = base.as_dict(work.get("primary_location"))
    rec["venue"] = base.clean_text(base.as_dict(loc.get("source")).get("display_name"), 200)
    rec["work_type"] = base.map_work_type(work.get("type"))
    if isinstance(work.get("is_retracted"), bool):
        rec["is_retracted"] = str(work["is_retracted"]).lower()
    oa = base.as_dict(work.get("open_access"))
    if isinstance(oa.get("is_oa"), bool):
        rec["is_oa"] = str(oa["is_oa"]).lower()
    rec["abstract"] = base.abstract_from_inverted_index(work.get("abstract_inverted_index"))
    rec["abstract_sha256"] = base.sha256_text(rec["abstract"]) if rec["abstract"] else ""
    rec["oa_url"] = str(oa.get("oa_url") or loc.get("pdf_url") or "")
    rec["providers"] = NAME
    rec["via"] = "api"
    rec["retrieved_utc"] = base.local_data.utc_now()
    return rec


def search(ctx: Context, query: str, *, limit: int = 25, filters: dict[str, Any] | None = None) -> list[Record]:
    params: dict[str, str] = {"search": query, "per-page": str(max(1, min(int(limit), 200))), "select": SELECT}
    if filters:
        params["filter"] = ",".join(f"{k}:{str(v).lower() if isinstance(v, bool) else v}" for k, v in sorted(filters.items()))
    params.update(_credential(ctx))
    return parse(ctx.get(NAME, f"{ctx.base_url(NAME, DEFAULT_URL)}/works?{urlencode(params)}"))


def parse(body: bytes) -> list[Record]:
    """Records of a search response (``results``) or of a single work; any other shape is refused."""
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise base.ProviderUnavailable(f"openalex returned an unreadable response ({exc})") from exc
    try:
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return [normalize(w) for w in data["results"] if isinstance(w, dict)]
        if isinstance(data, dict) and "id" in data and "title" in data:
            return [normalize(data)]
    except (TypeError, AttributeError, KeyError, IndexError, ValueError) as exc:
        raise base.ProviderUnavailable(f"openalex: a work in the response is malformed ({type(exc).__name__}: {exc})") from exc
    raise base.ProviderUnavailable("openalex: the response is neither a list of works nor a single work")


def lookup(ctx: Context, doi: str) -> Record | None:
    params = {"select": SELECT, **_credential(ctx)}
    url = f"{ctx.base_url(NAME, DEFAULT_URL)}/works/doi:{quote(doi, safe='/:')}?{urlencode(params)}"
    try:
        body = ctx.get(NAME, url)
    except base.NotFound:
        return None
    found = parse(body)
    return found[0] if found else None
