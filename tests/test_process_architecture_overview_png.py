import base64
import os
import json
import azure.functions as func
from function_app import process_file  # type: ignore


def make_request(body: dict, url_suffix: str = ""):
    return func.HttpRequest(
        method="POST",
    url=f"http://localhost/api/process_file{url_suffix}",
        params={},
        body=json.dumps(body).encode("utf-8"),
    )


def test_process_image_artifact_markdown():
    """Integration test: process a real PNG artifact in markdown mode.

    Validates header comments and that the body was produced (even if extractor
    yields no additional markdown beyond headers for an image-only file).
    """
    path = "artifacts/architecture overview.png"
    if not os.path.exists(path):  # Safety to avoid false pass if artifact missing
        raise AssertionError(f"Required test artifact missing: {path}")

    with open(path, "rb") as f:
        img_bytes = f.read()
    b64_img = base64.b64encode(img_bytes).decode()

    req = make_request({"filename": "architecture overview.png", "content_base64": b64_img})
    resp = process_file(req)
    assert resp.status_code == 200, resp.get_body()[:200]
    body = resp.get_body().decode(errors="replace")
    lines = body.splitlines()
    assert lines, "Expected non-empty markdown body"
    assert lines[0].startswith("<!-- filename: architecture overview.png"), lines[0]
    assert any("sha256:" in line for line in lines[:3]), "Missing sha256 metadata line"
    # For images the extracted markdown (after header lines) may be empty or contain an image reference.
    # We don't require non-empty content to keep test resilient.
