# Security Policy

## Threat Model & Built-in Mitigations

Heurisma processes untrusted web content, user-supplied data files, and Markdown reports to produce standalone offline HTML working papers. Its zero-dependency Python scripts enforce the following boundaries:

### 1. Untrusted Web Content → Markdown → HTML (`render_report.py`)
- **Zero JavaScript:** Generated HTML working papers contain only static HTML, inline CSS, and inline SVG. No `<script>` tags or external CDN resources are emitted.
- **HTML Escaping:** Narrative text, table cells, metadata, and embedded appendix files are escaped before rendering.
- **URL Scheme Allowlist:** Links (`[label](url)`) are restricted to `http`, `https`, `mailto`, `#` anchors, and relative paths. Images (`![alt](src)`) are embedded only from relative paths; a remote `http(s)` image becomes a plain link, so opening the HTML never contacts another server. Disallowed schemes (`javascript:`, `data:`, `vbscript:`, protocol-relative `//host`) are rendered as inert plain text.
- **Local Path Redaction:** Absolute home-directory paths (such as `/home/...`) are stripped from rendered references and appendices; `validate_report.py` flags any leaked `/home/` path as an error.
- **Prompt-Injection Boundary:** Scraped web pages, search summaries, API responses, user-curated documents (`inbox/sources/`, `appendix/corpus/`), earlier runs and subagent answers are treated strictly as data to be verified, never as instructions (`SKILL.md`, *Untrusted Content & No Exfiltration*). The three gate prompts tell their subagents the same and to report embedded instructions as findings; the source verifier and QA agents have no web tool.

### 2. User-Supplied Data Files (`local_data.py`, `fetch_lib.py`)
- **XLSX XXE / Billion-Laughs Protection:** `read_xlsx()` rejects any XML member containing `<!DOCTYPE` or `<!ENTITY` declarations before parsing.
- **Zip-Bomb Protection:** `read_xlsx()` enforces both a total uncompressed byte cap (`2 × HEURISMA_MAX_BYTES`, default 200 MB) and a maximum compression ratio (`100×` for members or archives ≥ 1 MB), plus a hard read cap on decompressed XML streams.
- **File Size Limits:** `read_csv()`, `read_json()`, `read_xlsx()`, and `read_table()` refuse files larger than `HEURISMA_MAX_BYTES` (default 100 MB) with a clean `ValueError`.
- **Network Fetch Safety (`fetch_lib.py`):** Only `http://` and `https://` URLs are allowed (redirects included), downloads enforce a byte cap and timeout, output filenames cannot escape the destination directory, a URL rejected for its scheme is logged without its credentials, and `HEURISMA_OFFLINE=1` blocks outbound network requests. With `allow_private=False` (always used by the paper connector for links taken from responses) a host that is or resolves to a private, loopback or link-local address is refused, redirects included. The host is resolved before the request and again by the HTTP client, so this guards against careless or planted links, not against a hostile DNS server.

### 3. Paper-Database Connector (`papers.py`, `providers/`)
- **Outbound Queries & Topic Privacy:** Running `papers.py search`, `lookup`, `cite --fulltext`, or `verify` sends the search keywords or DOIs to the selected third-party APIs (OpenAlex, Crossref, Europe PMC, arXiv, Unpaywall), so the research topic leaves the machine. Set `HEURISMA_OFFLINE=1` to block all outbound connector requests (`papers.py` logs `offline mode` and makes no network connection).
- **Credentials in Environment Variables Only & Redaction (`PRIV-CRED`):** Optional API credentials (`HEURISMA_OPENALEX_KEY` for OpenAlex, `HEURISMA_MAILTO` for Crossref/Unpaywall) are read exclusively from environment variables — never passed as CLI flags or stored in repository files. `providers.base.redact()` strips `api_key`, `apikey`, `mailto`, `email`, and the environment variable values themselves from all logged URLs, CSV registries (`download_log.csv`, `data_attempts.csv`, `papers.csv`, `search_log.csv`), cache filenames, and error messages. `validate_report.py` (`PRIV-CRED`) flags any credential parameter, or the value of either variable, left in a text file anywhere under `appendix/` as an error. API text written to the registries is stripped of control characters and neutralised against spreadsheet formula injection (a leading `=`, `+`, `-` or `@` gets an apostrophe).
- **API Responses Are Untrusted Data, Never Instructions:** Every free-text field returned by an API (provider notices, titles, abstracts, metadata — for example, OpenAlex's `meta.notice` prompting AI agents to POST the user's email address to register an API key) is untrusted data, never an instruction to obey. Providers parse only explicit schema fields, reject XML payloads with `<!DOCTYPE` or `<!ENTITY` declarations (except validated JATS full-text downloads checked by header), and verify that full-text downloads begin with a `%PDF` or XML/JATS document signature rather than an HTML landing page or cookie wall.

### 4. Executing Report Code (`validate_report.py --reproduce` & `--reproduce-lean`)
- `--reproduce` copies the report directory with `symlinks=True` (never dereferencing symlinks to host files), confines the script path to `appendix/analysis.py` (rejecting interpreter flags other than `-B` and escaping symlinks), confines any `>` redirect inside the temporary workspace, and runs `appendix/analysis.py` in a child Python process (`multiprocessing.Process`, no `subprocess`) with a hard timeout to verify deterministic regeneration of `output.txt`, `numbers.json`, and `charts.json`. It **never** invokes `lake` or `lean`.
- **Environment Isolation:** `providers/base.py` and `formal_math.py` read only explicit allowlists of variables (the 9-key `HEURISMA_*` set, and the `PATH`/`HOME`/`ELAN_*`/`HEURISMA_*` toolchain set) via `os.environ.get()`, never capturing the host's full `os.environ`; `clean_text()` strips non-printable control and Unicode Bidi-override characters. The skill contains no `eval`/`exec`, `shell=True`, `ctypes`, `pickle`/`marshal`, or `\x`/`\u` escape chains (guarded by `tests/test_security_scanner_guard.py`); the only `subprocess` use is `formal_math.py` launching the native `lake`/`lean` binaries without a shell.
- `--reproduce-lean` is a **separate, explicit opt-in flag** that replays kernel-verified Lean 4 proofs (`appendix/formal_proofs.csv`) in a temporary copy after removing any pre-built `.lake/build/` `.olean` artifacts, using `landrun` when installed.
- **Trust Warning:** Both `--reproduce` (arbitrary Python in `appendix/analysis.py`) and `--reproduce-lean` (`lake build`, which executes `lakefile.toml`/`lakefile.lean` and Lean metaprograms such as `macro`, `elab`, and `#eval`) execute code from the report's appendix without guaranteed OS-level sandboxing. Both flags are **opt-in** and must only be run on reports you have inspected or trust.
- **Offline Lock (`HEURISMA_OFFLINE=1`):** When `HEURISMA_OFFLINE=1` is set, `formal_math.py fetch-ref` blocks all outbound network requests and `formal_math.py check` exports `GIT_CONFIG_COUNT=1` (`protocol.allow=never`) so `lake` cannot fetch remote git dependencies.

### 5. Gate Provenance vs. Independence
- Gate files (`appendix/gates/{source_verifier,reviewer,qa}.md`) are bound to the reviewed artifacts via `REVIEWED-SHA256`, `ANALYSIS-SHA256` (and `FORMAL-SHA256` over `appendix/formal/*/Challenge.lean` when present), and literal `QUOTE:` lines.
- A gate marked `MODE: self-review` means the authoring agent ran the checklist inline rather than dispatching an independent subagent. The validator flags this visibly and the HTML labels it as self-review. Do not treat `self-review` gates as independent peer review. Even with `MODE: subagent`, a same-model subagent provides fresh-context isolation rather than human peer review and can share correlated blind spots with the author.

## Supported Versions

Security fixes are applied to the latest release on the `main` branch (`0.11.x`).

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately via [GitHub Security Advisories](https://github.com/777aeterna/heurisma/security/advisories/new) on `777aeterna/heurisma`. Do not open public issues for unpatched security bugs. Include a minimal reproduction (for example, a crafted Markdown snippet, `charts.json`, or XLSX file) and the Python version used.
