import base64
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


def test_process_image_unit_1x1_png_json():
    """Unit test: process a minimal 1x1 PNG and request JSON output.

    Ensures metadata + sha256 are returned and markdown field exists (may be empty
    or an extraction_failed marker depending on extractor capabilities).
    """
    # A tiny 1x1 transparent PNG
    b64_pixel = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    pixel_bytes = base64.b64decode(b64_pixel)
    req = make_request(
        {
            "filename": "pixel.png",
            "content_base64": b64_pixel,
        },
        url_suffix="?format=json",
    )

    resp = process_file(req)
    assert resp.status_code == 200, resp.get_body()
    payload = json.loads(resp.get_body())
    assert payload["status"] == "ok"
    data = payload["data"]
    assert data["filename"] == "pixel.png"
    assert data["content_type"] in ("image/png", "application/octet-stream")
    assert data["size_bytes"] == len(pixel_bytes)
    assert len(data["sha256"]) == 64
    assert isinstance(data.get("markdown"), str)
