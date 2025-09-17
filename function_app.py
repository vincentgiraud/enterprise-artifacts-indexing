"""Azure Functions Python v2 minimal app.

Provides a single HTTP-triggered function at /api/hello that returns a greeting.
Uses the new programming model (no explicit function.json needed).
"""

from __future__ import annotations

import json
from typing import Any

import azure.functions as func
import os
import base64 as _b64
import requests

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="process_file")
@app.route(route="process_file", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.ANONYMOUS)
def process_file(req: func.HttpRequest) -> func.HttpResponse:
    """Process an uploaded document and return Markdown (default) or JSON.

    Expected JSON body:
      {
        "filename": "example.docx",
        "content_base64": "<base64>",
        "content_type": "<mime type>"  # optional
      }

    Default response: text/markdown (with an HTML comment header).
    Add ?format=json for a JSON envelope.
    """
    import base64
    import hashlib

    # When invoking azure.functions.HttpRequest directly in tests, the params dict
    # may not be auto-populated from the URL query string, so fall back to parsing
    # the raw URL for '?format=json'.
    want_json = req.params.get("format") == "json" or ("?format=json" in req.url.lower())

    def error(message: str, code: int = 400) -> func.HttpResponse:
        if want_json:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": message}),
                status_code=code,
                mimetype="application/json",
            )
        return func.HttpResponse(
            f"ERROR: {message}\n",
            status_code=code,
            mimetype="text/plain",
        )

    try:
        body_raw = req.get_body()
        if not body_raw:
            return error("Empty request body")
        payload: Any = json.loads(body_raw)
    except json.JSONDecodeError as e:
        # Provide the underlying JSON error message to aid debugging (e.g. invalid escapes)
        return error(f"Body must be JSON ({e.msg})")

    if not isinstance(payload, dict):
        return error("JSON body must be an object")

    filename = payload.get("filename")
    content_b64 = payload.get("content_base64")
    content_type = payload.get("content_type")

    if not filename or not content_b64:
        return error("Missing filename or content_base64")

    try:
        file_bytes = base64.b64decode(content_b64, validate=True)
    except Exception:  # noqa: BLE001
        return error("content_base64 is not valid base64")

    if not content_type:
        lower = filename.lower()
        if lower.endswith(".pdf"):
            content_type = "application/pdf"
        elif lower.endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif lower.endswith(".pptx"):
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        else:
            content_type = "application/octet-stream"

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    markdown_text = None
    try:
        from markitdown import MarkItDown  # type: ignore
        import io

        mid = MarkItDown()
        result = mid.convert(io.BytesIO(file_bytes), filename=filename)
        if isinstance(result, dict):
            markdown_text = result.get("markdown") or result.get("output")
        else:
            markdown_text = str(result)
    except Exception as e:  # noqa: BLE001
        markdown_text = f"(extraction_failed: {e.__class__.__name__})"

    if not want_json:
        header = [
            f"<!-- filename: {filename} -->",
            f"<!-- size_bytes: {len(file_bytes)} sha256: {sha256_hash} content_type: {content_type} -->",
            "",
        ]
        return func.HttpResponse(
            "\n".join(header) + (markdown_text or ""),
            status_code=200,
            mimetype="text/markdown",
        )

    resp = {
        "status": "ok",
        "data": {
            "filename": filename,
            "size_bytes": len(file_bytes),
            "sha256": sha256_hash,
            "content_type": content_type,
            "markdown": markdown_text,
        },
    }
    return func.HttpResponse(json.dumps(resp), status_code=200, mimetype="application/json")


# Health probe (optional simple text) - helpful for quick container checks
@app.function_name(name="ping")
@app.route(route="ping", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def ping(req: func.HttpRequest) -> func.HttpResponse:  # pragma: no cover - trivial
    # 'req' param name must match a binding; using '_' caused FunctionLoadError in some Core Tools versions
    return func.HttpResponse("pong", status_code=200, mimetype="text/plain")


# New endpoint: create or replace a markdown (or any text) file in a GitHub repo
@app.function_name(name="write_to_repo")
@app.route(route="write_to_repo", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.ANONYMOUS)
def write_to_repo(req: func.HttpRequest) -> func.HttpResponse:
    """Write (create or replace) a file in a GitHub repository using the REST API.

    Request JSON body:
        {
          "repo": "owner/name",          # required
          "path": "docs/file.md",        # required
          "content": "# Markdown...",    # required (UTF-8 text)
          "branch": "main",              # optional (default=main)
          "commit_message": "..."         # optional
        }

    Behavior:
      - If file exists (GET returns 200), capture its sha and overwrite.
      - If not found (404), create new file.
      - Returns JSON metadata with commit SHA and HTML URL.
    """
    def respond(obj: Any, status: int = 200) -> func.HttpResponse:
        return func.HttpResponse(json.dumps(obj), status_code=status, mimetype="application/json")

    try:
        body_raw = req.get_body() or b"{}"
        payload = json.loads(body_raw)
    except json.JSONDecodeError as e:  # pragma: no cover - simple validation
        return respond({"status": "error", "error": f"Invalid JSON body: {e.msg}"}, 400)

    if not isinstance(payload, dict):
        return respond({"status": "error", "error": "JSON body must be an object"}, 400)

    repo = payload.get("repo")
    path = payload.get("path")
    content_text = payload.get("content")
    branch = payload.get("branch") or "main"
    commit_message = payload.get("commit_message")

    # Determine missing required fields
    required_pairs = [("repo", repo), ("path", path), ("content", content_text)]
    missing = [k for k, v in required_pairs if v in (None, "")]
    if missing:
        return respond({"status": "error", "error": f"Missing required field(s): {', '.join(missing)}"}, 400)

    # Safe now: repo, path, content_text are non-empty strings
    assert isinstance(path, str) and isinstance(repo, str) and isinstance(content_text, str)

    if ".." in path.split("/"):
        return respond({"status": "error", "error": "Path may not contain '..' segments"}, 400)

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return respond({"status": "error", "error": "GITHUB_TOKEN environment variable not set"}, 500)

    if not commit_message:
        commit_message = f"Update {path}"  # simple default

    owner_repo = repo.strip()
    if owner_repo.count("/") != 1:
        return respond({"status": "error", "error": "repo must be in form 'owner/name'"}, 400)

    api_base = "https://api.github.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "enterprise-artifacts-indexing-func",
    }

    # Step 1: check if file exists
    get_url = f"{api_base}/repos/{owner_repo}/contents/{path}"
    params = {"ref": branch}
    sha: str | None = None
    try:
        r_get = requests.get(get_url, headers=headers, params=params, timeout=10)
    except Exception as e:  # noqa: BLE001
        return respond({"status": "error", "error": f"Failed to contact GitHub: {e}"}, 502)

    if r_get.status_code == 200:
        try:
            data_existing = r_get.json()
            sha = data_existing.get("sha")
        except Exception:  # pragma: no cover - defensive
            pass
    elif r_get.status_code not in (404,):  # other errors propagate
        return respond({
            "status": "error",
            "error": f"GitHub GET failed: {r_get.status_code} {r_get.text[:300]}"
        }, 502)

    b64_content = _b64.b64encode(content_text.encode("utf-8")).decode("ascii")
    put_url = get_url
    payload_put: dict[str, Any] = {
        "message": commit_message,
        "content": b64_content,
        "branch": branch,
    }
    if sha:
        payload_put["sha"] = sha

    try:
        r_put = requests.put(put_url, headers=headers, json=payload_put, timeout=15)
    except Exception as e:  # noqa: BLE001
        return respond({"status": "error", "error": f"GitHub PUT failed: {e}"}, 502)

    if r_put.status_code not in (200, 201):
        return respond({
            "status": "error",
            "error": f"GitHub PUT failed: {r_put.status_code} {r_put.text[:300]}"
        }, 502)

    try:
        result = r_put.json()
    except Exception:  # pragma: no cover - defensive
        result = {}

    commit_sha = (
        (result.get("commit") or {}).get("sha")
        if isinstance(result.get("commit"), dict) else None
    )
    html_url = result.get("content", {}).get("html_url") if isinstance(result.get("content"), dict) else None

    action = "updated" if sha else "created"
    return respond({
        "status": "ok",
        "action": action,
        "repo": owner_repo,
        "path": path,
        "branch": branch,
        "commit_sha": commit_sha,
        "html_url": html_url,
    })

