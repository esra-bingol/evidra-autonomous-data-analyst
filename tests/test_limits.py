from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from analysis.api import app, reset_store
from analysis.limits import UploadLimitError, UploadLimits, reject_if_content_length_exceeds

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDRA_DATA", str(tmp_path))
    reset_store()
    yield TestClient(app), tmp_path
    reset_store()


def _csv(rows: int, cols: int, cell: str = "x") -> bytes:
    header = ",".join(f"c{i}" for i in range(cols))
    line = ",".join(cell for _ in range(cols))
    body = "\n".join([header, *[line for _ in range(rows)]])
    return (body + "\n").encode("utf-8")


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _post(client: TestClient, name: str, data: bytes, mime: str = "text/csv"):
    return client.post("/datasets", files={"file": (name, data, mime)})


def test_upload_bytes_below_and_at_limit(client, monkeypatch):
    http, data_root = client
    payload = _csv(2, 2)
    monkeypatch.setenv("EVIDRA_MAX_UPLOAD_BYTES", str(len(payload)))
    ok = _post(http, "aov_trap.csv", payload)
    assert ok.status_code == 200, ok.text
    monkeypatch.setenv("EVIDRA_MAX_UPLOAD_BYTES", str(len(payload) + 10))
    reset_store()
    ok2 = _post(http, "ok.csv", payload)
    assert ok2.status_code == 200


def test_upload_above_byte_limit_is_413_and_leaves_no_files(client, monkeypatch):
    http, data_root = client
    payload = _csv(4, 3)
    monkeypatch.setenv("EVIDRA_MAX_UPLOAD_BYTES", str(max(1, len(payload) - 1)))
    res = _post(http, "big.csv", payload)
    assert res.status_code == 413
    assert res.json()["detail"] == "Upload exceeds the maximum allowed size."
    uploads = data_root / "uploads"
    leftover = list(uploads.glob("*")) if uploads.exists() else []
    assert leftover == []
    datasets = data_root / "datasets"
    assert not datasets.exists() or list(datasets.glob("*.json")) == []


def test_content_length_fast_path():
    limits = UploadLimits(
        max_bytes=100,
        max_rows=10,
        max_columns=10,
        max_cell_length=10,
        max_zip_uncompressed_bytes=100,
        max_zip_members=2,
    )
    reject_if_content_length_exceeds("100", limits)
    with pytest.raises(UploadLimitError) as exc:
        reject_if_content_length_exceeds(str(100 + 256 * 1024 + 1), limits)
    assert exc.value.status_code == 413


def test_structural_row_column_cell_limits(client, monkeypatch):
    http, _ = client
    monkeypatch.setenv("EVIDRA_MAX_UPLOAD_ROWS", "2")
    monkeypatch.setenv("EVIDRA_MAX_UPLOAD_COLUMNS", "3")
    monkeypatch.setenv("EVIDRA_MAX_UPLOAD_CELL_LENGTH", "4")
    ok = _post(http, "ok.csv", _csv(2, 3, "ab"))
    assert ok.status_code == 200, ok.text
    rows = _post(http, "rows.csv", _csv(3, 2, "ab"))
    assert rows.status_code == 400
    assert rows.json()["detail"] == "Upload exceeds the maximum allowed row count."
    cols = _post(http, "cols.csv", _csv(1, 4, "ab"))
    assert cols.status_code == 400
    assert cols.json()["detail"] == "Upload exceeds the maximum allowed column count."
    cell = _post(http, "cell.csv", _csv(1, 2, "abcde"))
    assert cell.status_code == 400
    assert cell.json()["detail"] == "Upload exceeds the maximum allowed cell length."


def test_filename_rules(client):
    http, _ = client
    payload = _csv(1, 2)
    ok = _post(http, "aov_trap.csv", payload)
    assert ok.status_code == 200
    assert ok.json()["name"] == "aov_trap.csv"
    unsafe = _post(http, "../aov_trap.csv", payload)
    assert unsafe.status_code == 400
    assert unsafe.json()["detail"] == "Unsafe filename."
    long_name = ("n" * 201) + ".csv"
    long_res = _post(http, long_name, payload)
    assert long_res.status_code == 400
    assert long_res.json()["detail"] == "Filename is too long."


def test_zip_valid_small_archive(client):
    http, _ = client
    inner = (FIXTURES / "aov_trap.csv").read_bytes()
    small = _zip_bytes({"aov_trap.csv": inner})
    ok = _post(http, "bundle.zip", small, "application/zip")
    assert ok.status_code == 200, ok.text


def test_zip_too_many_members(client, monkeypatch):
    http, data_root = client
    monkeypatch.setenv("EVIDRA_MAX_ZIP_MEMBERS", "2")
    too_many = _zip_bytes({f"m{i}.csv": b"a,b\n1,2\n" for i in range(3)})
    many = _post(http, "many.zip", too_many, "application/zip")
    assert many.status_code == 400
    assert many.json()["detail"] == "ZIP contains too many members."
    _assert_no_upload_residue(data_root)


def test_zip_uncompressed_size_rejected(client, monkeypatch):
    http, data_root = client
    monkeypatch.setenv("EVIDRA_MAX_ZIP_UNCOMPRESSED_BYTES", "20")
    huge = _zip_bytes({"big.csv": b"a,b\n" + b"1,2\n" * 50})
    size = _post(http, "huge.zip", huge, "application/zip")
    assert size.status_code == 413
    assert size.json()["detail"] == "Upload exceeds the maximum allowed size."
    _assert_no_upload_residue(data_root)


def test_zip_traversal_rejected_and_cleaned(client):
    http, data_root = client
    traversal = _zip_bytes({"../evil.csv": b"a,b\n1,2\n"})
    bad = _post(http, "trav.zip", traversal, "application/zip")
    assert bad.status_code == 400
    assert bad.json()["detail"] == "ZIP path traversal is not allowed."
    _assert_no_upload_residue(data_root)


def _assert_no_upload_residue(data_root: Path) -> None:
    uploads = data_root / "uploads"
    leftover = list(uploads.rglob("*")) if uploads.exists() else []
    leftover = [p for p in leftover if p.is_file() or (p.is_dir() and p.name.endswith("_extracted"))]
    assert leftover == []
    datasets = data_root / "datasets"
    assert not datasets.exists() or list(datasets.glob("*.json")) == []


def test_fixture_ignores_upload_row_limit(client, monkeypatch):
    http, _ = client
    monkeypatch.setenv("EVIDRA_MAX_UPLOAD_ROWS", "1")
    created = http.post("/datasets", json={"fixture_id": "clear_driver"})
    assert created.status_code == 200
    assert created.json()["n_rows"] > 1
