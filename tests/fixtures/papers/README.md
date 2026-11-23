# Paper-connector fixtures

Trimmed API responses used by `tests/papers_server.py`. The unit tests never use the network.

| File | Origin |
| :-- | :-- |
| `crossref_work.json`, `openalex_work.json`, `europepmc_search.json` (first result), `arxiv_feed.xml` | **Real responses fetched on 2026-11-23**, reduced to the fields the connector reads (the arXiv feed is verbatim). |
| `openalex_search.json` | One real record plus five synthetic ones. Its `meta.notice` is the **real, verbatim text** OpenAlex returned for a request without a key: it contains an instruction aimed at AI agents (to POST a user's e-mail address to register a key). It is kept on purpose: the connector must treat such text as data and never act on it. |
| `unpaywall.json` | **Shape taken from the public documentation, not from a live response**: the API requires a contact e-mail, which was not used while building these fixtures. Check it with `tests/live_smoke.py`. |
| `sample.pdf`, `europepmc_fulltext.xml` | **Synthetic** stand-ins for a downloaded open-access paper and a Europe PMC full text (the tests never download a real paper). The XML copies the *shape* the real endpoint returns on 2026-11-23: it starts with a JATS `<!DOCTYPE article …>` and has no `<?xml` header. |
| `openalex_index.json` | The OpenAlex records indexed by lower-case DOI, for the lookup route. |

Open-access and PDF links that pointed at a real publisher are replaced by `https://example.invalid/...` (a reserved domain that never resolves), so a test can never download a real paper by accident; `tests/test_papers_core.py` also fails any test that connects anywhere but `127.0.0.1`.

Synthetic records use the DOI prefix **`10.9999/`** so that no real paper is ever described as retracted, a preprint or without an abstract:
`fake.preprint.1` (type `preprint`), `fake.retracted.1` (`is_retracted: true`), `fake.noabstract.1` (no abstract),
`(sici)1097-0000(199801)1:1<1::aid-x>3.0.co;2-z` (a DOI with parentheses, `<`, `>` and `;`), `fake.report.1` (type `report`).

Real-API facts these fixtures encode (observed 2026-11-23): OpenAlex `type` also takes `report` (an NBER working paper) and
`conference-paper`; its abstract is only an inverted index; Europe PMC `abstractText` and `pubType` can be missing; arXiv
answers `429` to two requests in a row.
