import base64
import os
import azure.functions as func
from function_app import process_file  # type: ignore


def test_process_file_architecture_guidelines_docx_json():
    """Integration test (JSON mode): process the real Architecture Guidelines.docx file.

    Validates end-to-end path and JSON envelope when ?format=json is used.
    """
    path = "tests/fixtures/documents/Architecture Guidelines.docx"
    if not os.path.exists(path):  # safety in case artifact moved
        raise AssertionError(f"Required test artifact missing: {path}")

    with open(path, "rb") as f:
        data = f.read()

    b64 = base64.b64encode(data).decode()

    # Build request asking for JSON output for easier assertions
    req = func.HttpRequest(
        method="POST",
    url="http://localhost/api/process_file?format=json",
        params={},
        body=(
            b'{"filename": "Architecture Guidelines.docx", "content_base64": "'
            + b64.encode()
            + b'"}'
        ),
    )

    resp = process_file(req)
    assert resp.status_code == 200, resp.get_body()

    import json

    payload = json.loads(resp.get_body())
    assert payload["status"] == "ok"
    meta = payload["data"]
    assert meta["filename"] == "Architecture Guidelines.docx"
    assert meta["size_bytes"] == len(data)
    assert meta["content_type"] in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        # Fallback possible if detection changes
        "application/octet-stream",
    )
    markdown = meta.get("markdown") or ""
    # Basic quality assertions (avoid brittle exact content checks):
    assert not markdown.startswith("(extraction_failed"), markdown[:120]
    assert len(markdown) > 50  # should have extracted some substantive text


def test_process_file_architecture_guidelines_docx_markdown():
    """Integration test (Markdown mode): ensure default (no ?format=json) returns markdown body.

    Asserts presence of HTML comment header and adequate extracted content length.
    """
    path = "tests/fixtures/documents/Architecture Guidelines.docx"
    if not os.path.exists(path):
        raise AssertionError(f"Required test artifact missing: {path}")

    with open(path, "rb") as f:
        data = f.read()

    b64 = base64.b64encode(data).decode()
    req = func.HttpRequest(
        method="POST",
    url="http://localhost/api/process_file",  # no format parameter -> markdown
        params={},
        body=(
            b'{"filename": "Architecture Guidelines.docx", "content_base64": "'
            + b64.encode()
            + b'"}'
        ),
    )

    resp = process_file(req)
    assert resp.status_code == 200, resp.get_body()[:200]
    body = resp.get_body().decode(errors="replace")

    lines = body.splitlines()
    assert lines[0].startswith("<!-- filename: Architecture Guidelines.docx"), lines[0]
    # Second line has size + sha256 metadata
    assert "sha256:" in lines[1]

    # Combine remainder for content assessment
    content_md = "\n".join(lines[3:]) if len(lines) > 3 else ""
    assert len(content_md) > 50, "Expected substantial markdown content"
    assert not content_md.startswith("(extraction_failed"), content_md[:120]

