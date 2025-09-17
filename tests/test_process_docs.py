import base64
import json
import azure.functions as func
from function_app import process_file  # type: ignore


def make_request(body: dict | None = None, url_suffix: str = ""):
    data = json.dumps(body or {}).encode("utf-8")
    return func.HttpRequest(
        method="POST",
    url=f"http://localhost/api/process_file{url_suffix}",
        params={},
        body=data,
    )


def test_process_file_success_pdf():
    content = b"%PDF-1.4 example minimal"
    b64 = base64.b64encode(content).decode()
    req = make_request(
        {
            "filename": "sample.pdf",
            "content_base64": b64,
        },
        url_suffix="?format=json",
    )
    resp = process_file(req)
    assert resp.status_code == 200
    payload = json.loads(resp.get_body())
    assert payload["status"] == "ok"
    assert payload["data"]["filename"] == "sample.pdf"
    assert payload["data"]["size_bytes"] == len(content)
    assert payload["data"]["content_type"] == "application/pdf"
    assert len(payload["data"]["sha256"]) == 64
    # markdown should be present (may be empty or extraction failure marker)
    assert "markdown" in payload["data"]


def test_process_file_missing_fields():
    req = make_request({"filename": "file.docx"}, url_suffix="?format=json")  # missing content_base64
    resp = process_file(req)
    assert resp.status_code == 400
    payload = json.loads(resp.get_body())
    assert payload["status"] == "error"
    assert "content_base64" in payload["error"].lower()


def test_process_file_bad_base64():
    req = make_request({"filename": "bad.pptx", "content_base64": "**notb64**"}, url_suffix="?format=json")
    resp = process_file(req)
    assert resp.status_code == 400
    payload = json.loads(resp.get_body())
    assert payload["status"] == "error"
    assert "base64" in payload["error"].lower()


def test_process_file_default_markdown_output():
    content = b"Hello world in a txt-like file"  # unknown extension fallback
    b64 = base64.b64encode(content).decode()
    req = make_request({"filename": "notes.bin", "content_base64": b64})  # no format param -> markdown
    resp = process_file(req)
    assert resp.status_code == 200
    body = resp.get_body().decode()
    # Should contain HTML comment header with filename
    assert "filename: notes.bin" in body.splitlines()[0]
