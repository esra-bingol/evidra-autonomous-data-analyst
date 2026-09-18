from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from analysis.api import app, reset_store


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    monkeypatch.delenv("EVIDRA_ACCESS_TOKEN", raising=False)
    reset_store()
    yield
    reset_store()


def test_open_by_default():
    client = TestClient(app)
    assert client.get("/auth/status").json() == {"required": False, "unlocked": True}
    assert client.get("/health").status_code == 200
    assert client.get("/fixtures").status_code == 200


def test_token_locks_apis_and_unlocks_with_cookie(monkeypatch):
    monkeypatch.setenv("EVIDRA_ACCESS_TOKEN", "secret-token")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/chat").status_code == 200
    status = client.get("/auth/status").json()
    assert status == {"required": True, "unlocked": False}
    locked = client.get("/fixtures")
    assert locked.status_code == 401
    bad = client.post("/auth/unlock", json={"token": "nope"})
    assert bad.status_code == 401
    ok = client.post("/auth/unlock", json={"token": "secret-token"})
    assert ok.status_code == 200
    assert client.get("/fixtures").status_code == 200
    assert client.get("/auth/status").json()["unlocked"] is True


def test_bearer_header_unlocks(monkeypatch):
    monkeypatch.setenv("EVIDRA_ACCESS_TOKEN", "secret-token")
    client = TestClient(app)
    res = client.get("/fixtures", headers={"Authorization": "Bearer secret-token"})
    assert res.status_code == 200
