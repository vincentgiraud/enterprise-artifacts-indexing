# Enterprise Artifacts Indexing (Azure Functions - Python)

A minimal Azure Functions (Python v2 programming model) service that converts uploaded enterprise document artifacts (DOCX, PDF, PPTX, images, etc.) into Markdown for downstream indexing / search pipelines.

The app exposes two HTTP-triggered endpoints:

- `POST /api/process_file` — Accepts a JSON payload with a base64-encoded file and returns extracted Markdown (default) or a JSON metadata envelope.
- `GET  /api/ping` — Lightweight health probe returning `pong`.
- `POST /api/write_to_repo` — Create or replace a markdown (or any UTF-8 text) file in a GitHub repository (requires `GITHUB_TOKEN`).

## Features

- Azure Functions Python v2 (no explicit `function.json` files required)
- Automatic content-type inference from filename extension
- SHA-256 hash + size metadata for integrity / dedupe logic
- Graceful base64 parsing & clear error messages
- Dual output modes:
  - Markdown body with HTML comment metadata headers (default)
  - Structured JSON (`?format=json`) including filename, size, hash, content type, markdown
- Robust extraction via [`markitdown`](https://pypi.org/project/markitdown/) (supports Office formats, PDFs, images OCR when extras installed)
- Comprehensive unit & integration tests covering success & failure scenarios
- Easily containerizable or deployable via Azure Functions Core Tools / GitHub Actions

## Request / Response Contract

### POST /api/process_file (default Markdown)

Request JSON body:

```json
{
  "filename": "Architecture Guidelines.docx",
  "content_base64": "<base64 bytes>",
  "content_type": "<optional mime>"
}
```

Markdown response (example header):

```markdown
<!-- filename: Architecture Guidelines.docx -->
<!-- size_bytes: 12345 sha256: <64hex> content_type: application/vnd.openxmlformats-officedocument.wordprocessingml.document -->

# Extracted content ...
```

### JSON mode

Append `?format=json` to the URL:

```json
{
  "status": "ok",
  "data": {
    "filename": "sample.pdf",
    "size_bytes": 42,
    "sha256": "<64hex>",
    "content_type": "application/pdf",
    "markdown": "..."
  }
}
```

### Error example

```json
{
  "status": "error",
  "error": "Missing filename or content_base64"
}
```

## Local Development

### Prerequisites

- Python 3.12 (matches `pyproject.toml` constraint)
- [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) v4
- (Optional) [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) for `UseDevelopmentStorage=true`

### Install dependencies

Using `uv` (pyproject-aware) or fallback to pip:

```bash
# Using uv (fast):
uv sync

# Or pip (will use requirements.txt)
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

### Run Functions host

```bash
func start
```
Core Tools will expose `http://localhost:7071/api/process_file`.

### Quick cURL example

```bash
b64=$(base64 -w0 artifacts/"Architecture Guidelines.docx")
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"filename\":\"Architecture Guidelines.docx\",\"content_base64\":\"$b64\"}" \
  "http://localhost:7071/api/process_file?format=json" | jq .
```

### Run Tests

Pytest is included as a dependency.

```bash
pytest -q
```

Tests exercise:

- PDF success path
- Missing / invalid base64 validation
- Image processing metadata
- Real DOCX & PNG artifacts (integration)
- Markdown vs JSON mode behavior

## Deployment

1. Create an Azure Function App (Python 3.12, Consumption or Premium) & Storage Account.
2. Set `FUNCTIONS_WORKER_RUNTIME=python` and appropriate storage settings.
3. Deploy via your preferred method:
   - Core Tools: `func azure functionapp publish <APP_NAME>`
   - GitHub Actions / Azure DevOps pipeline
4. (Optional) Add monitoring (Azure Monitor / OpenTelemetry) by uncommenting dependency in `requirements.txt`.

### Environment / Settings

`local.settings.json` is excluded from version control. For production, configure equivalents as application settings in Azure.

Suggested production settings:

- `AzureWebJobsStorage`
- Any downstream service keys for indexing pipeline (not yet implemented)
- `GITHUB_TOKEN` (PAT with `repo` scope to enable `/api/write_to_repo`)

## Write to GitHub Endpoint (`POST /api/write_to_repo`)

Create or update (replace) a file in a GitHub repository using the REST API. Useful for persisting extracted markdown into a docs repo.

Environment variable required:

```bash
export GITHUB_TOKEN=<personal access token with repo scope>
```

Request body:

```json
{
  "repo": "owner/repository",
  "path": "docs/extracted/Architecture-Guidelines.md",
  "content": "# Title\nExtracted markdown...",
  "branch": "main",
  "commit_message": "Add extracted Architecture Guidelines"
}
```

Minimal required fields: `repo`, `path`, `content`. `branch` defaults to `main`; `commit_message` is auto-generated if omitted.

Successful response:

```json
{
  "status": "ok",
  "action": "created",
  "repo": "owner/repository",
  "path": "docs/extracted/Architecture-Guidelines.md",
  "branch": "main",
  "commit_sha": "abc123def...",
  "html_url": "https://github.com/owner/repository/blob/main/docs/extracted/Architecture-Guidelines.md"
}
```

Error example (missing token):

```json
{ "status": "error", "error": "GITHUB_TOKEN environment variable not set" }
```

Security note: Endpoint currently anonymous; protect with `FUNCTION` or AAD in production. Token should be stored as an application setting in Azure, not committed to source.

## CORS (Cross-Origin Resource Sharing)

If you call the Function endpoints directly from a browser-based frontend (SPA) hosted on a different origin, you must enable CORS so the browser will allow the requests.

## Project Structure

```text
function_app.py        # FunctionApp & route handlers
artifacts/             # Sample documents used in tests
tests/                 # Unit & integration tests (pytest)
pyproject.toml         # Project metadata & dependencies
requirements.txt       # Runtime deps for Azure Functions deployment
host.json              # Functions host config
local.settings.json    # Local only runtime settings (ignored in git)
```

## Extending

Ideas:

- Add blob trigger to auto-process new uploads
- Persist extracted markdown to Azure Cognitive Search or AI Search
- Add language detection & embeddings generation
- Implement batching / chunking for large docs
- Provide `/api/version` endpoint including git SHA
- Enrich `/api/write_to_repo` with append mode, batch writes, or front-matter templating

## Error Handling Notes

- All validation errors return HTTP 400 with structured JSON if `?format=json`.
- Extraction failures embed a `(extraction_failed: <Reason>)` marker inside the markdown field instead of hard-failing.

## Security Considerations

- Current auth level is `ANONYMOUS` for simplicity. Use `FUNCTION` or `AAD` in production.
- Enforce size limits (not yet implemented) to prevent abuse. Consider rejecting files above a threshold (e.g. 10 MB).
- Sanitize or restrict supported file types depending on your data governance requirements.

## License

TBD (add a LICENSE file, e.g., MIT, if you plan to open-source).

---
Feel free to ask if you’d like a sample GitHub Actions workflow or Azure deployment script next.
