"""A local stand-in for the paper APIs, serving the recorded fixtures in ``tests/fixtures/papers/``.

    base, server = papers_server.start()
    os.environ["HEURISMA_OPENALEX_URL"] = base + "/openalex"      # likewise _CROSSREF_, _EUROPEPMC_, _ARXIV_, _UNPAYWALL_
    ...
    server.requests            # [(path, {query: [values]}, {header: value})] in arrival order
    server.fail_next("/openalex", 429, times=2)   # the next 2 matching requests answer 429 (Retry-After: 0)
    server.stop()

Routes: ``/openalex/works`` (search) and ``/openalex/works/doi:<doi>``; ``/crossref/works/<doi>``;
``/europepmc/search`` and ``/europepmc/<pmcid>/fullTextXML``; ``/arxiv/api/query``; ``/unpaywall/<doi>``;
``/files/sample.pdf`` (a PDF) and ``/files/page.html`` (an HTML landing page, not a document); ``/redirect/ok`` (302 to the PDF),
``/redirect/ftp`` and ``/redirect/private`` (302 to an ftp:// link and to 10.0.0.1, to test that redirects are not followed blindly).
An unknown DOI answers 404.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "papers"


def _json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class PapersServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.requests: list[tuple[str, dict[str, list[str]], dict[str, str]]] = []
        self._failures: list[list] = []  # [prefix, status, remaining]
        self._lock = threading.Lock()
        self.openalex_index = _json("openalex_index.json")
        self.crossref = {"10.1038/s41586-024-07500-2": _json("crossref_work.json"), "10.9999/fake.preprint.1": _json("crossref_preprint.json")}
        self._thread = threading.Thread(target=lambda: self.serve_forever(poll_interval=0.01), daemon=True)

    def fail_next(self, prefix: str, status: int, times: int = 1) -> None:
        with self._lock:
            self._failures.append([prefix, status, times])

    def take_failure(self, path: str) -> int | None:
        with self._lock:
            for f in self._failures:
                if path.startswith(f[0]) and f[2] > 0:
                    f[2] -= 1
                    return int(f[1])
        return None

    def stop(self) -> None:
        self.shutdown()
        self.server_close()


class _Handler(BaseHTTPRequestHandler):
    server: PapersServer

    def log_message(self, *args) -> None:  # keep test output quiet
        pass

    def _send(self, status: int, body: bytes, ctype: str = "application/json", extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path, query = unquote(url.path), parse_qs(url.query)
        self.server.requests.append((path, query, {k: v for k, v in self.headers.items()}))
        status = self.server.take_failure(path)
        if status:
            self._send(status, b'{"error":"forced"}', extra={"Retry-After": "0"})
            return
        if path == "/openalex/works":
            self._send(200, (FIXTURES / "openalex_search.json").read_bytes())
        elif path.startswith("/openalex/works/doi:"):
            w = self.server.openalex_index.get(path[len("/openalex/works/doi:"):].lower())
            self._send(200, json.dumps(w).encode()) if w else self._send(404, b'{"error":"not found"}')
        elif path.startswith("/crossref/works/"):
            rec = self.server.crossref.get(path[len("/crossref/works/"):].lower())
            self._send(200, json.dumps(rec).encode()) if rec else self._send(404, b"Resource not found.", "text/plain")
        elif path.startswith("/europepmc/") and path.endswith("/fullTextXML"):
            self._send(200, (FIXTURES / "europepmc_fulltext.xml").read_bytes(), "application/xml")
        elif path == "/redirect/ok":
            self._send(302, b"", extra={"Location": "/files/sample.pdf"})
        elif path == "/redirect/ftp":
            self._send(302, b"", extra={"Location": "ftp://example.invalid/x.pdf"})
        elif path == "/redirect/private":
            self._send(302, b"", extra={"Location": "http://10.0.0.1/x.pdf"})
        elif path == "/files/sample.pdf":
            self._send(200, (FIXTURES / "sample.pdf").read_bytes(), "application/pdf")
        elif path == "/files/page.html":
            self._send(200, b"<html><body>Please accept our cookies to read this article.</body></html>", "text/html")
        elif path == "/europepmc/search":
            self._send(200, (FIXTURES / "europepmc_search.json").read_bytes())
        elif path == "/arxiv/api/query":
            self._send(200, (FIXTURES / "arxiv_feed.xml").read_bytes(), "application/atom+xml")
        elif path.startswith("/unpaywall/"):
            doi = path[len("/unpaywall/"):].lower()
            if doi == "10.1038/s41586-024-07500-2":
                answer = _json("unpaywall.json")
                answer["best_oa_location"]["url_for_pdf"] = f"http://{self.headers['Host']}/files/sample.pdf"  # never the real publisher
                self._send(200, json.dumps(answer).encode())
            else:
                self._send(404, b'{"error":true}')
        else:
            self._send(404, b'{"error":"no such route"}')


def start() -> tuple[str, PapersServer]:
    server = PapersServer()
    server._thread.start()
    return f"http://127.0.0.1:{server.server_address[1]}", server
