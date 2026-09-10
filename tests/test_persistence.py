from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from analysis.api import app, reset_store
from analysis import store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    reset_store()
    yield TestClient(app)
    reset_store()


def test_investigation_persists_and_survives_memory_reset(client: TestClient):
    ds = client.post("/datasets", json={"fixture_id": "clear_driver"}).json()
    run = client.post(
        f"/datasets/{ds['id']}/analyze",
        json={"question": "Satış neden değişti?"},
    )
    assert run.status_code == 200
    body = run.json()
    rid = body["id"]
    assert body["status"] in {"completed", "abstained"}
    assert body["evidence"]
    assert body["claims"]
    assert body["reviews"]
    assert body["traces"]
    assert body["investigation_report"]
    listed = client.get("/runs").json()["runs"]
    assert any(r["id"] == rid for r in listed)

    reset_store()

    listed_after = client.get("/runs").json()["runs"]
    assert any(r["id"] == rid for r in listed_after)
    fetched = client.get(f"/runs/{rid}")
    assert fetched.status_code == 200
    again = fetched.json()
    assert again["id"] == rid
    assert again["evidence"]
    assert again["claims"]
    assert again["reviews"]
    assert again["traces"]
    assert again["investigation_report"]["schema_version"] == "v2.11"
    assert again["question"] == "Satış neden değişti?"
    report = client.get(f"/runs/{rid}/report").json()
    assert report["key_findings"]
    missing = client.get("/runs/run-does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "run not found"


def test_upload_dataset_survives_reset(client: TestClient, tmp_path: Path):
    raw = (Path(__file__).resolve().parents[1] / "data" / "fixtures" / "aov_trap.csv").read_bytes()
    up = client.post("/datasets", files={"file": ("aov_trap.csv", raw, "text/csv")})
    assert up.status_code == 200
    did = up.json()["id"]
    run = client.post(
        f"/datasets/{did}/analyze",
        json={"question": "Satış neden değişti?"},
    )
    assert run.status_code == 200
    rid = run.json()["id"]
    reset_store()
    ds = client.get(f"/datasets/{did}")
    assert ds.status_code == 200
    assert Path(ds.json()["path"]).exists()
    fetched = client.get(f"/runs/{rid}")
    assert fetched.status_code == 200
    assert fetched.json()["dataset_id"] == did
    assert fetched.json()["dataset_ref"]


def test_corrupt_run_is_not_empty_run(client: TestClient, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    runs = tmp_path / "runs"
    runs.mkdir(parents=True)
    (runs / "run-broken.json").write_text("{", encoding="utf-8")
    res = client.get("/runs/run-broken")
    assert res.status_code == 422


def test_chat_last_run_survives_reset(client: TestClient):
    ds = client.post("/datasets", json={"fixture_id": "clear_driver"}).json()
    chat = client.post("/chats", json={"dataset_id": ds["id"]}).json()
    first = client.post(
        f"/chats/{chat['id']}/messages",
        json={"text": "Satış neden değişti?"},
    ).json()["message"]
    rid = first["run_id"]
    reset_store()
    hist = client.get(f"/chats/{chat['id']}").json()
    assert hist["last_run_id"] == rid
    follow = client.post(
        f"/chats/{chat['id']}/messages",
        json={"text": "Peki West'te durum nasıl?"},
    ).json()["message"]
    assert follow["ran_investigation"] is False
    assert follow["run_id"] == rid


def test_subprocess_reads_completed_run(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    store.save_run(
        {
            "id": "run-proc",
            "dataset_id": "ds-1",
            "question": "q",
            "decision": "primary_driver",
            "evidence": [{"evidence_id": "ev-1"}],
            "claims": [{"claim_id": "cl-001", "evidence_ids": ["ev-1"]}],
            "reviews": [{"claim_id": "cl-001", "decision": "accept"}],
            "traces": [{"tool": "inspect_dataset"}],
            "investigation_report": {"schema_version": "v2.6"},
        }
    )
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["EVIDRA_DATA"] = str(tmp_path)
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from analysis.store import get_run; r=get_run('run-proc'); "
            "assert r['evidence'] and r['claims'] and r['reviews'] and r['traces'] and r['investigation_report']",
        ],
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_incomplete_run_is_not_padded_empty(client: TestClient, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    store.atomic_write(
        tmp_path / "runs" / "run-old.json",
        {"id": "run-old", "question": "q", "status": "running"},
    )
    res = client.get("/runs/run-old")
    assert res.status_code == 200
    body = res.json()
    assert "evidence" not in body
    assert "claims" not in body
    assert body["status"] == "running"
