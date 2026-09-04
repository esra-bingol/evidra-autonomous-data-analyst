from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis import store


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    return tmp_path


def test_save_load_list_and_atomic_write(isolated: Path):
    rec = {
        "id": "run-abc",
        "dataset_id": "ds-1",
        "question": "Satış neden değişti?",
        "decision": "primary_driver",
        "evidence": [{"evidence_id": "ev-1", "operation": "compare_periods"}],
        "claims": [{"claim_id": "cl-001", "text": "ok", "kind": "association", "evidence_ids": ["ev-1"]}],
        "reviews": [{"claim_id": "cl-001", "decision": "accept"}],
        "traces": [{"tool": "inspect_dataset", "ok": True}],
        "investigation_report": {"schema_version": "v2.6"},
    }
    saved = store.save_run(rec)
    assert saved["status"] == "completed"
    assert not list(store.runs_dir().glob("*.tmp"))
    loaded = store.get_run("run-abc")
    assert loaded["claims"][0]["claim_id"] == "cl-001"
    assert loaded["evidence"]
    listed = store.list_runs()
    assert listed[0]["id"] == "run-abc"
    assert listed[0]["status"] == "completed"


def test_completed_run_is_immutable(isolated: Path):
    store.save_run({"id": "run-x", "decision": "abstain", "question": "q"})
    with pytest.raises(store.ImmutableRun):
        store.save_run({"id": "run-x", "decision": "primary_driver", "question": "q"})


def test_missing_and_malformed_run(isolated: Path):
    with pytest.raises(store.MissingRun):
        store.get_run("run-missing")
    path = store.runs_dir() / "run-bad.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(store.CorruptRun):
        store.get_run("run-bad")
    empty = store.runs_dir() / "run-empty.json"
    empty.write_text("{}\n", encoding="utf-8")
    with pytest.raises(store.CorruptRun):
        store.get_run("run-empty")
    listed = store.list_runs()
    assert all(r["id"] != "run-bad" for r in listed)


def test_portable_dataset_ref_is_relative(isolated: Path):
    ref = store.portable_ref(store.PROJECT_ROOT / "data" / "fixtures" / "clear_driver.csv")
    assert not Path(ref).is_absolute()
    assert "clear_driver.csv" in ref
    resolved = store.resolve_ref(ref)
    assert resolved.exists()
    nested = isolated / "uploads" / "file.csv"
    nested.parent.mkdir(parents=True)
    nested.write_text("x", encoding="utf-8")
    ref2 = store.portable_ref(nested)
    assert ref2.startswith(store.DATA_REF_PREFIX)
    assert store.resolve_ref(ref2) == nested.resolve()


def test_corrupt_index_is_rebuilt_from_run_files(isolated: Path):
    store.save_run({"id": "run-a", "decision": "primary_driver", "question": "a"})
    store.save_run({"id": "run-b", "decision": "abstain", "question": "b"})
    (store.runs_dir() / "index.json").write_text("{", encoding="utf-8")
    listed = store.list_runs()
    assert {r["id"] for r in listed} == {"run-a", "run-b"}
