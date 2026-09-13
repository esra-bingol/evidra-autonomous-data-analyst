from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from analysis.api import app, reset_store
from analysis.tools.schemas import V1_TOOLS

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    reset_store()
    yield
    reset_store()


@pytest.fixture
def client():
    return TestClient(app)


def test_console_is_four_blocks_not_chat(client: TestClient):
    html = client.get("/").text
    assert "İnceleme konsolu" in html
    assert "block-upload" in html
    assert "block-question" in html
    assert "block-plan" in html
    assert "block-findings" in html
    assert "İnceleme geçmişi" in html
    assert "chatbot" not in html.lower()
    assert "confidence" not in html.lower()
    css = client.get("/static/console.css").text
    js = client.get("/static/console.js").text
    assert "89%" not in html + css + js
    assert "confidence" not in js.lower()
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Genel bakış" in dashboard.text
    assert "kpi-decision" in dashboard.text
    assert "Nerede yoğunlaştı" in dashboard.text
    assert "Verini yükle" in dashboard.text
    assert "Birincil sürücü" not in dashboard.text
    assert "Özerk veri analisti" not in dashboard.text
    assert "Toplam inceleme" not in dashboard.text
    chat = client.get("/chat")
    assert chat.status_code == 200
    assert 'id="file"' in chat.text
    assert "Rapor / follow-up" in chat.text
    chat_js = client.get("/static/chat.js").text
    assert "West'i daha detaylı incele" not in chat_js
    assert "Evidence raporunu göster" not in chat_js
    assert "Ücret neden değişti?" in chat_js
    console = client.get("/console")
    assert console.status_code == 200
    assert "block-upload" in console.text
    console_js = client.get("/static/console.js").text
    assert "abstain / Olist" not in console_js
    assert "Ücret neden değişti?" in console_js
    assert "capability ∩" not in console_js
    assert "Hipotez uydurulmadı" not in console_js
    assert "evidence_ids boş" not in console_js
    assert "Bu soru için mevcut veride belirgin bir yoğunlaşma yok" in console_js


def test_taxi_fixture_is_catalogued(client: TestClient):
    items = {row["id"]: row for row in client.get("/fixtures").json()["items"]}
    assert items["taxi_trips"]["available"] is True
    bound = client.post("/datasets", json={"fixture_id": "taxi_trips"})
    assert bound.status_code == 200
    assert bound.json()["name"] == "Taksi seferleri"
    created = client.post("/datasets", json={"fixture_id": "clear_driver"})
    assert created.status_code == 200
    ds = created.json()
    got = client.get(f"/datasets/{ds['id']}")
    assert got.status_code == 200
    assert got.json()["capabilities"]["delivery_analysis"] is False
    run = client.post(
        f"/datasets/{ds['id']}/analyze",
        json={"question": "Satış neden değişti?"},
    )
    assert run.status_code == 200
    body = run.json()
    assert body["decision"] == "primary_driver"
    assert body["primary_driver"] == "West × Office Supplies"
    assert any(c["kind"] == "association" for c in body["claims"])
    assert all(c.get("evidence_ids") for c in body["claims"] if c["kind"] != "abstention")
    assert body["evidence"]
    assert {e["strength"] for e in body["evidence"]} <= {"weak", "moderate", "strong", "inconclusive"}
    fetched = client.get(f"/runs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["stop_reason"] == body["stop_reason"]
    assert body["investigation_report"]["schema_version"] == "v2.12"
    assert body["investigation_report"]["key_findings"]
    page = client.get("/report")
    assert page.status_code == 200
    assert "İnceleme raporu" in page.text
    assert "block-upload" not in page.text
    report_js = client.get("/static/report.js").text
    assert "Kanıt tablosu" not in report_js
    assert "Reviewer kararları" not in report_js
    assert "Sürücü ayrıştırması" not in report_js
    assert "Nerede yoğunlaştı" in report_js
    assert "Dilim tablosu" in report_js
    packed = client.get(f"/runs/{body['id']}/report")
    assert packed.status_code == 200
    assert packed.json()["source"] == "validated_investigation_state"


def test_abstain_delivery_question_visible(client: TestClient):
    ds = client.post("/datasets", json={"fixture_id": "clear_driver"}).json()
    run = client.post(
        f"/datasets/{ds['id']}/analyze",
        json={"question": "Teslimat gecikmesi puanı nasıl etkiler?"},
    ).json()
    assert run["decision"] == "abstain"
    assert run["stop_reason"] == "abstain"
    assert run["hypotheses"] == []


def test_missing_question_and_empty_upload(client: TestClient):
    ds = client.post("/datasets", json={"fixture_id": "no_signal"}).json()
    missing = client.post(f"/datasets/{ds['id']}/analyze", json={"question": "   "})
    assert missing.status_code == 422 or missing.status_code == 400
    empty = client.post("/datasets", files={"file": ("empty.csv", b"", "text/csv")})
    assert empty.status_code == 400


def test_csv_upload_then_analyze(client: TestClient):
    raw = (FIXTURES / "aov_trap.csv").read_bytes()
    up = client.post("/datasets", files={"file": ("aov_trap.csv", raw, "text/csv")})
    assert up.status_code == 200
    run = client.post(
        f"/datasets/{up.json()['id']}/analyze",
        json={"question": "Satış neden değişti?"},
    ).json()
    assert run["decision"] == "value_not_volume"


def test_tool_surface_unchanged():
    assert "run_python" not in V1_TOOLS
    assert V1_TOOLS == (
        "inspect_dataset",
        "profile_dataset",
        "detect_capabilities",
        "compare_periods",
        "segment_by",
        "decompose_volume_value",
        "test_hypothesis",
        "detect_anomalies",
        "statistical_test",
        "create_chart",
        "run_sql",
        "generate_report",
    )
