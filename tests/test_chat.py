from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from analysis.api import app, reset_store
from analysis.chat import classify_turn
from analysis.tools.schemas import V1_TOOLS


def setup_function():
    reset_store()


def teardown_function():
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
    assert classify_turn("West'i daha detaylı incele.", has_run=True) == "focus_existing"
    assert classify_turn("Araştırma adımlarını göster.", has_run=True) == "show_steps"


def test_first_message_runs_engine_follow_up_does_not():
    client = TestClient(app)
    ds = client.post("/datasets", json={"fixture_id": "clear_driver"}).json()
    chat = client.post("/chats", json={"dataset_id": ds["id"]}).json()
    first = client.post(
        f"/chats/{chat['id']}/messages",
        json={"text": "Satış neden değişti?"},
    )
    assert first.status_code == 200
    msg = first.json()["message"]
    assert msg["ran_investigation"] is True
    assert msg["status"]["decision"] == "primary_driver"
    assert msg["claim_ids"]
    assert msg["evidence_ids"]
    assert "West" in msg["text"] or "associated" in msg["text"]
    run_id = msg["run_id"]

    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("follow-up must not start a new investigation")

    with patch("analysis.api.run_investigation", boom):
        second = client.post(
            f"/chats/{chat['id']}/messages",
            json={"text": "West'i daha detaylı incele."},
        )
    assert second.status_code == 200
    follow = second.json()["message"]
    assert follow["ran_investigation"] is False
    assert follow["run_id"] == run_id
    assert follow["intent"] == "focus_existing"
    assert "SQL" in follow["text"] or "evidence" in follow["text"].lower() or "segment_by" in follow["text"]
    assert calls["n"] == 0
    hist = client.get(f"/chats/{chat['id']}").json()["messages"]
    assert len(hist) == 4
    assert hist[0]["role"] == "user"
    assert hist[-1]["run_id"] == run_id
