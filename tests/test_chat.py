from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from analysis.api import app, reset_store
from analysis.chat import classify_turn
from analysis.router import CAUSAL_LIMIT
from analysis.tools.schemas import V1_TOOLS


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    reset_store()
    yield
    reset_store()


def test_console_still_exists_and_chat_is_separate():
    client = TestClient(app)
    home = client.get("/").text
    assert "block-upload" in home
    assert "Sohbet yüzeyi (V2.5)" in home
    assert "chatbot" not in home.lower()
    chat = client.get("/chat")
    assert chat.status_code == 200
    assert "Sohbet yüzeyi" in chat.text
    assert "block-upload" not in chat.text


def test_chat_text_is_not_sql_or_python():
    assert "run_python" not in V1_TOOLS
    assert classify_turn("SELECT * FROM orders; --", has_run=False) == "investigate"
    west_run = {"primary_driver": "West × Office Supplies", "evidence": []}
    assert classify_turn("Peki West'te durum nasıl?", has_run=True, last_run=west_run) == "answer_from_evidence"
    assert classify_turn("West'i daha detaylı incele.", has_run=True, last_run=west_run) == "follow_up_investigate"
    assert classify_turn("Araştırma adımlarını göster.", has_run=True) == "show_steps"
    assert classify_turn("Detaylı raporu göster.", has_run=True) == "show_report"


def _start_sales_chat(client: TestClient) -> tuple[dict, dict]:
    ds = client.post("/datasets", json={"fixture_id": "clear_driver"}).json()
    chat = client.post("/chats", json={"dataset_id": ds["id"]}).json()
    first = client.post(
        f"/chats/{chat['id']}/messages",
        json={"text": "Satış neden değişti?"},
    )
    assert first.status_code == 200
    return chat, first.json()["message"]


def test_first_message_runs_engine_follow_up_does_not():
    client = TestClient(app)
    chat, msg = _start_sales_chat(client)
    assert msg["ran_investigation"] is True
    assert msg["status"]["decision"] == "primary_driver"
    assert msg["claim_ids"]
    assert msg["evidence_ids"]
    assert "West" in msg["text"] or "west" in msg["text"].lower()
    assert "associated" not in msg["text"].lower()
    assert msg.get("response", {}).get("answer") == msg["text"]
    run_id = msg["run_id"]

    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("follow-up must not start a new investigation")

    with patch("analysis.api.run_investigation", boom):
        second = client.post(
            f"/chats/{chat['id']}/messages",
            json={"text": "Peki West'te durum nasıl?"},
        )
    assert second.status_code == 200
    follow = second.json()["message"]
    assert follow["ran_investigation"] is False
    assert follow["run_id"] == run_id
    assert follow["intent"] == "answer_from_evidence"
    assert "segment_by" not in follow["text"]
    assert "share_of_change" not in follow["text"]
    assert "west" in follow["text"].lower()
    assert calls["n"] == 0
    hist = client.get(f"/chats/{chat['id']}").json()["messages"]
    assert len(hist) == 4
    assert hist[0]["role"] == "user"
    assert hist[-1]["run_id"] == run_id


def test_followups_answer_from_existing_evidence():
    client = TestClient(app)
    chat, first = _start_sales_chat(client)
    run_id = first["run_id"]

    with patch("analysis.api.run_investigation", side_effect=AssertionError("must not rerun")):
        west = client.post(
            f"/chats/{chat['id']}/messages",
            json={"text": "Peki West'te durum nasıl?"},
        ).json()["message"]
        worst = client.post(
            f"/chats/{chat['id']}/messages",
            json={"text": "En kötü kategori hangisi?"},
        ).json()["message"]
        why = client.post(
            f"/chats/{chat['id']}/messages",
            json={"text": "Bunun nedeni ne?"},
        ).json()["message"]

    assert west["ran_investigation"] is False
    assert west["intent"] == "answer_from_evidence"
    assert west["run_id"] == run_id
    assert "west" in west["text"].lower()
    assert "associated" not in west["text"].lower()

    assert worst["ran_investigation"] is False
    assert "kategori" in worst["text"].lower() or "office" in worst["text"].lower()
    assert "segment_by" not in worst["text"]

    assert why["ran_investigation"] is False
    assert CAUSAL_LIMIT in why["text"]
    assert "neden oldu" not in why["text"].lower()


def test_missing_capability_does_not_run_engine():
    client = TestClient(app)
    ds = client.post("/datasets", json={"fixture_id": "clear_driver"}).json()
    chat = client.post("/chats", json={"dataset_id": ds["id"]}).json()
    with patch("analysis.api.run_investigation", side_effect=AssertionError("must not run")):
        msg = client.post(
            f"/chats/{chat['id']}/messages",
            json={"text": "Bu veriyle müşteri kaybını analiz edebilir miyiz?"},
        ).json()["message"]
    assert msg["ran_investigation"] is False
    assert msg["intent"] == "abstain_capability"
    assert "müşteri kaybını temsil eden bir alan bulunmuyor" in msg["text"]
    assert msg.get("missing_capability") == "retention_analysis"


def test_west_why_opens_scoped_run_in_same_chat():
    client = TestClient(app)
    chat, first = _start_sales_chat(client)
    first_run = first["run_id"]
    second = client.post(
        f"/chats/{chat['id']}/messages",
        json={"text": "Peki West'te neden?"},
    )
    assert second.status_code == 200
    msg = second.json()["message"]
    assert msg["ran_investigation"] is True
    assert msg["intent"] == "follow_up_investigate"
    assert msg["run_id"] != first_run
    assert msg.get("parent_run_id") == first_run
    assert (msg.get("scope") or {}).get("region") == "West"
    assert "ayrı bir hipotez" in msg["text"]
    assert "west" in msg["text"].lower()
    assert "associated" not in msg["text"].lower()
    hist = client.get(f"/chats/{chat['id']}").json()
    assert hist["last_run_id"] == msg["run_id"]
    assert len(hist["messages"]) == 4
    saved = client.get(f"/runs/{msg['run_id']}").json()
    assert saved.get("parent_run_id") == first_run
    assert saved.get("scope") == {"region": "West"}
    assert saved.get("investigation_report")
