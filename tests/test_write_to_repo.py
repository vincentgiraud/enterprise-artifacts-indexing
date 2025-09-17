import json
import azure.functions as func
import os
from function_app import write_to_repo  # type: ignore


class DummyResp:
    def __init__(self, status_code: int, json_obj=None, text: str = ""):
        self.status_code = status_code
        self._json = json_obj or {}
        self.text = text or json.dumps(self._json)

    def json(self):  # noqa: D401 - simple
        return self._json


def make_req(body: dict):
    return func.HttpRequest(
        method="POST",
        url="http://localhost/api/write_to_repo",
        params={},
        body=json.dumps(body).encode("utf-8"),
    )


def patch_requests(monkeypatch, get_resp, put_resp):
    import requests  # type: ignore

    def fake_get(*a, **kw):  # noqa: D401
        return get_resp

    def fake_put(*a, **kw):  # noqa: D401
        return put_resp

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "put", fake_put)


def test_write_to_repo_create(monkeypatch):
    os.environ["GITHUB_TOKEN"] = "testtoken"
    get_resp = DummyResp(404, {})  # not found -> create
    put_resp = DummyResp(201, {
        "content": {"html_url": "https://github.com/owner/repo/blob/main/docs/file.md"},
        "commit": {"sha": "abc123"},
    })
    patch_requests(monkeypatch, get_resp, put_resp)

    req = make_req({
        "repo": "owner/repo",
        "path": "docs/file.md",
        "content": "# Title\nBody",
    })
    resp = write_to_repo(req)
    assert resp.status_code == 200
    payload = json.loads(resp.get_body())
    assert payload["status"] == "ok"
    assert payload["action"] == "created"
    assert payload["commit_sha"] == "abc123"


def test_write_to_repo_update(monkeypatch):
    os.environ["GITHUB_TOKEN"] = "testtoken"
    get_resp = DummyResp(200, {"sha": "oldsha"})
    put_resp = DummyResp(200, {
        "content": {"html_url": "https://github.com/owner/repo/blob/main/docs/file.md"},
        "commit": {"sha": "def456"},
    })
    patch_requests(monkeypatch, get_resp, put_resp)
    req = make_req({
        "repo": "owner/repo",
        "path": "docs/file.md",
        "content": "Updated content",
        "commit_message": "Update docs/file.md",
    })
    resp = write_to_repo(req)
    assert resp.status_code == 200
    payload = json.loads(resp.get_body())
    assert payload["action"] == "updated"
    assert payload["commit_sha"] == "def456"


def test_write_to_repo_missing_fields():
    req = make_req({"repo": "owner/repo"})  # missing path & content
    resp = write_to_repo(req)
    assert resp.status_code == 400
    body = json.loads(resp.get_body())
    assert body["status"] == "error"
    assert "Missing required field" in body["error"]


def test_write_to_repo_no_token(monkeypatch):
    # Ensure token not set
    if "GITHUB_TOKEN" in os.environ:
        del os.environ["GITHUB_TOKEN"]
    req = make_req({
        "repo": "owner/repo",
        "path": "docs/file.md",
        "content": "Anything",
    })
    resp = write_to_repo(req)
    assert resp.status_code == 500
    payload = json.loads(resp.get_body())
    assert payload["status"] == "error"
    assert "GITHUB_TOKEN" in payload["error"]
