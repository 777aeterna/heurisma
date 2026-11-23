"""Unpaywall (https://unpaywall.org/products/api): where a work's open-access copy lives, found by DOI.

The API requires a contact address (``HEURISMA_MAILTO``, one you choose) and asks for at most about 100,000 calls a day.
The address is sent as a query parameter and redacted from everything logged.
"""

from __future__ import annotations

import json
from urllib.parse import quote, urlencode

from providers import base
from providers.base import Context

NAME = "unpaywall"
DEFAULT_URL = "https://api.unpaywall.org/v2"


def oa_location(ctx: Context, doi: str) -> dict[str, str] | None:
    """The best open-access copy of a DOI as ``{pdf_url, version, license}``, or None when there is none or the DOI is unknown."""
    if not ctx.mailto:
        raise base.ProviderUnavailable("unpaywall needs a contact address: set HEURISMA_MAILTO to one you choose (it is never logged)")
    url = f"{ctx.base_url(NAME, DEFAULT_URL)}/{quote(doi, safe='/:')}?{urlencode({'email': ctx.mailto})}"
    try:
        body = ctx.get(NAME, url)
    except base.NotFound:
        return None
    try:
        best = (json.loads(body).get("best_oa_location")) or {}
    except (ValueError, AttributeError) as exc:
        raise base.ProviderUnavailable(f"unpaywall returned an unreadable response ({exc})") from exc
    pdf = str(best.get("url_for_pdf") or "")
    if not pdf:
        return None
    return {"pdf_url": pdf, "version": str(best.get("version") or ""), "license": str(best.get("license") or "")}
