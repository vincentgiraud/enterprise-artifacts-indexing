# Enterprise Artifacts Indexing (Azure Functions - Python)

A minimal Azure Functions (Python v2 programming model) service that converts uploaded enterprise document artifacts (DOCX, PDF, PPTX, images, etc.) into Markdown for downstream indexing / search pipelines.

The app exposes two HTTP-triggered endpoints:

- `POST /api/process_file` — Accepts a JSON payload with a base64-encoded file and returns extracted Markdown (default) or a JSON metadata envelope.
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
b64=$(base64 -w0 tests/fixtures/documents/"Architecture Guidelines.docx")
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
function_app.py               # FunctionApp & route handlers
tests/                        # Unit & integration tests (pytest)
tests/fixtures/documents/     # Sample documents used in integration tests
tests/fixtures/images/        # Sample images used in integration tests
tests/test_logic_app.json     # Sample Logic App workflow (SharePoint -> Functions -> GitHub)
pyproject.toml                # Project metadata & dependencies
requirements.txt              # Runtime deps for Azure Functions deployment
host.json                     # Functions host config
local.settings.json           # Local only runtime settings (ignored in git)
```

## Logic App Integration (SharePoint ➜ Azure Function ➜ GitHub)

The repository includes a sample Azure Logic App definition (`tests/test_logic_app.json`) demonstrating an automated pipeline:

1. Poll a SharePoint document library for new or modified files (every minute).
2. Retrieve file metadata and binary content.
3. Invoke `/api/process_file` to convert each document to Markdown.
4. Invoke `/api/write_to_repo` to commit the generated Markdown into a GitHub repository.

### Workflow Overview

Trigger (SharePoint change poll) → Get file properties → For each item → If not a folder:

- Get file content
- Get file metadata
- POST to Function: process_file
- POST to Function: write_to_repo

Folders are skipped. The sample stores markdown under `tests/fixtures/generated/<SharePointFileId>.md` (adjust to suit your docs repo layout).

### Importing the Logic App

1. Create a Logic App (Consumption or Standard) in Azure.
2. Open the Logic App in the Portal, choose Code View (or add a new workflow in Standard) and paste the contents of `tests/test_logic_app.json`.
3. Save; you will be prompted to create / authorize the SharePoint connection referenced as `sharepointonline_template`.
4. In the workflow parameters set:

- `SharepointSiteAddress_template` — e.g. `https://<tenant>.sharepoint.com/sites/<site>`
- `SharepointLibraryName_template` — e.g. `Documents`
- `FunctionProcessFile_url` — Public URL of your deployed `process_file` endpoint
- `FuntionWriteToRepo_url` — Public URL of your deployed `write_to_repo` endpoint (note the original typo in parameter name)

If you later secure your Functions with keys (`authLevel=Function`), append `?code=<FUNCTION_KEY>` to both URLs.

### GitHub Token Usage

The Logic App does not send a token; the write endpoint relies on the Function App's `GITHUB_TOKEN` application setting. Ensure a PAT with `repo` scope is configured in Azure. The sample request sets:

```json
"repo": "vincentgiraud/enterprise-artifacts-indexing",
"branch": "main",
"path": "tests/fixtures/generated/@{body('Get_file_metadata')?['Id']}.md"
```

To use the original filename (slugified):

```jsonc
"path": "docs/extracted/@{replace(body('Get_file_metadata')?['Name'], ' ', '-')}.md"
```

### Adjusting Polling

Current recurrence: every 1 minute. Increase interval for cost reduction or switch to an event-based SharePoint trigger for near real-time without full enumeration.

### Performance & Scale Notes

- The sample enumerates the entire library each run; for large libraries consider change tokens or filtering by extension early.
- Large files may approach Logic App or Function timeouts—enforce size limits inside `process_file`.
- Add retry policies on HTTP actions if needed (`runtimeConfiguration` supports this).

### Local Development With Tunneling

To test against a local Functions host, expose it via a tunnel (e.g. `ngrok http 7071`) and temporarily set the function URLs to the tunnel endpoints.

### Common Issues

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| 401/403 from Function | Missing function key after changing auth level | Append `?code=<key>` to URL |
| 404 writing to repo | `GITHUB_TOKEN` missing / wrong scope | Add PAT with `repo` scope in App Settings |
| SharePoint 404 | Site or library name mismatch | Verify full site URL and library display name |
| Empty markdown | Unsupported format or extraction failure | Inspect function response for `(extraction_failed: ...)` |

### Source Control & IaC

The Logic App definition is placed under `tests/` for convenience. For production, treat workflow JSON as infrastructure code (e.g. move to `infrastructure/logic-apps/` and deploy via Bicep/ARM/Terraform or `az logicapp deployment source config-zip`).

---

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
