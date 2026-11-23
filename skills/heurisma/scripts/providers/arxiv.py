"""arXiv (https://info.arxiv.org/help/api): preprints in physics, mathematics, computer science and economics.

No key. The terms of use ask for one request every three seconds on a single connection, and the API answers 429 to
bursts; ``Context`` waits and ``fetch_lib`` retries. A work without a DOI is keyed ``arxiv:<id>``.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from providers import base
from providers.base import Context, Record

NAME = "arxiv"
DEFAULT_URL = "https://export.arxiv.org"
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"


def _text(node: Any, tag: str) -> str:
    child = node.find(tag)
    return re.sub(r"\s+", " ", child.text or "").strip() if child is not None else ""


def normalize(entry: Any) -> Record:
    rec = base.empty_record()
    raw_id = _text(entry, _ATOM + "id")
    arxiv_id = re.sub(r"v\d+$", "", raw_id.rsplit("/abs/", 1)[-1])
    rec["doi"] = base.normalize_doi(_text(entry, _ARXIV + "doi")) or (f"arxiv:{arxiv_id.lower()}" if arxiv_id else "")
    rec["title"] = base.clean_text(_text(entry, _ATOM + "title"))
    names = [_text(a, _ATOM + "name") for a in entry.findall(_ATOM + "author")]
    rec["first_author"] = base.clean_text(names[0], 200) if names else ""
    rec["n_authors"] = str(len(names))
    rec["year"] = _text(entry, _ATOM + "published")[:4]
    # an <arxiv:doi> names the PUBLISHED version: "preprint" and "arXiv" describe the arXiv copy, not that DOI, so leave both unknown
    published = bool(_text(entry, _ARXIV + "doi"))
    rec["venue"] = "" if published else "arXiv"
    rec["work_type"] = "" if published else "preprint"
    rec["is_oa"] = "true"
    rec["abstract"] = _text(entry, _ATOM + "summary")
    rec["abstract_sha256"] = base.sha256_text(rec["abstract"]) if rec["abstract"] else ""
    for link in entry.findall(_ATOM + "link"):
        if link.get("title") == "pdf" and link.get("href"):
            rec["oa_url"] = str(link.get("href")).replace("http://", "https://", 1)
    rec["providers"] = NAME
    rec["via"] = "api"
    rec["retrieved_utc"] = base.local_data.utc_now()
    return rec


def _arxiv_id(entry: Any) -> str:
    return re.sub(r"v\d+$", "", _text(entry, _ATOM + "id").rsplit("/abs/", 1)[-1]).lower()


def lookup(ctx: Context, arxiv_id: str) -> Record | None:
    """The record of one arXiv identifier (``2401.08922``), or None when arXiv answers with a different work or none."""
    wanted = re.sub(r"v\d+$", "", arxiv_id.strip().lower())
    url = f"{ctx.base_url(NAME, DEFAULT_URL)}/api/query?{urlencode({'id_list': wanted, 'max_results': '1'})}"
    root = base.parse_xml(ctx.get(NAME, url, ext="xml"))
    if root.tag != _ATOM + "feed":
        raise base.ProviderUnavailable("arxiv: the response is not an Atom feed")
    for entry in root.findall(_ATOM + "entry"):
        if _arxiv_id(entry) == wanted:
            return normalize(entry)
    return None


def _query(text: str) -> str:
    """Every word must match (``AND``); a quoted phrase stays a phrase. A whole query as one phrase almost never matches."""
    parts = re.findall(r'"[^"]+"|\S+', text)
    return " AND ".join(f"all:{p}" for p in parts) or 'all:""'


def search(ctx: Context, query: str, *, limit: int = 25, filters: dict[str, Any] | None = None) -> list[Record]:
    params = {"search_query": _query(query), "max_results": str(max(1, min(int(limit), 100)))}
    return parse(ctx.get(NAME, f"{ctx.base_url(NAME, DEFAULT_URL)}/api/query?{urlencode(params)}", ext="xml"))


def parse(body: bytes) -> list[Record]:
    root = base.parse_xml(body)
    if root.tag != _ATOM + "feed":
        raise base.ProviderUnavailable("arxiv: the response is not an Atom feed")
    try:
        return [normalize(e) for e in root.findall(_ATOM + "entry")]
    except (TypeError, AttributeError, KeyError, IndexError, ValueError) as exc:
        raise base.ProviderUnavailable(f"arxiv: an entry in the response is malformed ({type(exc).__name__}: {exc})") from exc
