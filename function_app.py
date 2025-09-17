"""Azure Functions Python v2 minimal app.

Provides a single HTTP-triggered function at /api/hello that returns a greeting.
Uses the new programming model (no explicit function.json needed).
"""

from __future__ import annotations

import json
from typing import Any

import azure.functions as func

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

