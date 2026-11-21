# Security Policy

## Threat Model & Built-in Mitigations

Heurisma processes untrusted web content, user-supplied data files, and Markdown reports to produce standalone offline HTML working papers. Its zero-dependency Python scripts enforce the following boundaries:

### 1. Untrusted Web Content → Markdown → HTML (`render_report.py`)
- **Zero JavaScript:** Generated HTML working papers contain only static HTML, inline CSS, and inline SVG. No `<script>` tags or external CDN resources are emitted.
- **HTML Escaping:** Narrative text, table cells, metadata, and embedded appendix files are escaped before rendering.
- **URL Scheme Allowlist:** Links (`[label](url)`) and images (`![alt](src)`) are restricted to `http`, `https`, `mailto`, `#` anchors, and relative paths. Disallowed schemes (`javascript:`, `data:`, `vbscript:`, protocol-relative `//host`) are rendered as inert plain text.
- **Local Path Redaction:** Absolute home-directory paths (such as `/home/...`) are stripped from rendered references and appendices; `validate_report.py` flags any leaked `/home/` path as an error.
- **Prompt-Injection Boundary:** Scraped web pages and user-curated documents (`inbox/sources/`, `appendix/corpus/`) are treated strictly as data to be verified, never as instructions to override protocol gates.

### 2. User-Supplied Data Files (`local_data.py`, `fetch_lib.py`)
- **XLSX XXE / Billion-Laughs Protection:** `read_xlsx()` rejects any XML member containing `<!DOCTYPE` or `<!ENTITY` declarations before parsing.
- **Zip-Bomb Protection:** `read_xlsx()` enforces both a total uncompressed byte cap (`2 × HEURISMA_MAX_BYTES`, default 200 MB) and a maximum compression ratio (`100×` for members or archives ≥ 1 MB), plus a hard read cap on decompressed XML streams.
- **File Size Limits:** `read_csv()`, `read_json()`, `read_xlsx()`, and `read_table()` refuse files larger than `HEURISMA_MAX_BYTES` (default 100 MB) with a clean `ValueError`.
- **Network Fetch Safety (`fetch_lib.py`):** Only `http://` and `https://` URLs are allowed, downloads enforce a byte cap and timeout, output filenames cannot escape the destination directory, and `HEURISMA_OFFLINE=1` blocks outbound network requests.

### 3. Executing Report Code (`validate_report.py --reproduce`)
- `--reproduce` executes `appendix/analysis.py` (using the command documented in `appendix/README.md` or passed via `--reproduce-cmd`) inside a temporary copy of the report directory to verify deterministic regeneration of `output.txt`, `numbers.json`, and `charts.json`.
- **Trust Warning:** `--reproduce` runs arbitrary Python code from the report's appendix without OS-level sandboxing. It is **opt-in** and must only be run on reports whose `appendix/analysis.py` you have inspected or trust.

### 4. Gate Provenance vs. Independence
- Gate files (`appendix/gates/{source_verifier,reviewer,qa}.md`) are bound to the reviewed artifacts via `REVIEWED-SHA256` and literal `QUOTE:` lines.
- A gate marked `MODE: self-review` means the authoring agent ran the checklist inline rather than dispatching an independent subagent. The validator flags this visibly and the HTML labels it as self-review. Do not treat `self-review` gates as independent peer review.

## Supported Versions

Security fixes are applied to the latest release on the `main` branch (`0.7.x`).

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately via [GitHub Security Advisories](https://github.com/777aeterna/heurisma/security/advisories/new) on `777aeterna/heurisma`. Do not open public issues for unpatched security bugs. Include a minimal reproduction (for example, a crafted Markdown snippet, `charts.json`, or XLSX file) and the Python version used.
