"""Crossref (https://api.crossref.org): authoritative metadata for a DOI, used to verify that a reference exists.

No key. ``HEURISMA_MAILTO`` (a contact address you choose) joins the faster "polite" pool; without it the public pool
is used. Crossref cannot say a work is *not* retracted, so an absent notice is recorded as unknown, never as false.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode

from providers import base
from providers.base import Context, Record

NAME = "crossref"
DEFAULT_URL = "https://api.crossref.org"


def _first(value: Any) -> Any:
    """The first item of a list, or the value itself when Crossref (or a hand-made file) gives a bare string."""
    items = value if isinstance(value, list) else [value]
    return items[0] if items else ""


def normalize(message: dict[str, Any]) -> Record:
    rec = base.empty_record()
    rec["doi"] = base.normalize_doi(message.get("DOI")) or ""
    title = _first(message.get("title"))
    rec["title"] = base.clean_text(base.jats_to_text(title) if isinstance(title, str) else "")
    authors = [a for a in base.as_list(message.get("author")) if isinstance(a, dict)]
    if authors:
        first = authors[0]
        rec["first_author"] = base.clean_text(" ".join(str(p) for p in (first.get("given"), first.get("family") or first.get("name")) if p), 200)
    rec["n_authors"] = str(len(authors))
    parts = _first(base.as_dict(message.get("issued")).get("date-parts"))
    year = _first(parts) if isinstance(parts, list) else None
    rec["year"] = str(year) if isinstance(year, int) and year else ""
    container = _first(message.get("container-title"))
    rec["venue"] = base.clean_text(str(container) if container else str(message.get("publisher") or ""), 200)
    rec["work_type"] = base.map_work_type(message.get("type"))
    notices = [n for n in base.as_list(message.get("updated-by")) if isinstance(n, dict)]
    if any("retraction" in str(n.get("type") or "").lower() for n in notices):
        rec["is_retracted"] = "true"
    abstract = message.get("abstract")
    rec["abstract"] = base.jats_to_text(abstract) if isinstance(abstract, str) else ""
    rec["abstract_sha256"] = base.sha256_text(rec["abstract"]) if rec["abstract"] else ""
    rec["providers"] = NAME
    rec["via"] = "api"
    rec["retrieved_utc"] = base.local_data.utc_now()
    return rec


def lookup(ctx: Context, doi: str) -> Record | None:
    url = f"{ctx.base_url(NAME, DEFAULT_URL)}/works/{quote(doi, safe='/:')}"
    if ctx.mailto:
        url += "?" + urlencode({"mailto": ctx.mailto})
    try:
        body = ctx.get(NAME, url)
    except base.NotFound:
        return None
    found = parse(body)
    return found[0] if found else None


def parse(body: bytes) -> list[Record]:
    """Records of a ``/works/<doi>`` response (``message``) or of a list response (``message.items``); other shapes are refused."""
    try:
        message = json.loads(body).get("message")
    except (ValueError, AttributeError) as exc:
        raise base.ProviderUnavailable(f"crossref returned an unreadable response ({exc})") from exc
    try:
        if isinstance(message, dict) and isinstance(message.get("items"), list):
            return [normalize(m) for m in message["items"] if isinstance(m, dict)]
        if isinstance(message, dict) and "DOI" in message:
            return [normalize(message)]
    except (TypeError, AttributeError, KeyError, IndexError, ValueError) as exc:
        raise base.ProviderUnavailable(f"crossref: a work in the response is malformed ({type(exc).__name__}: {exc})") from exc
    raise base.ProviderUnavailable("crossref: the response has no work in its 'message'")
