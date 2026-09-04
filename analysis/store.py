"""Durable investigation records. Filesystem only; the engine does not import this module."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_NAME = "index.json"
TERMINAL = frozenset({"completed", "failed", "abstained"})


class MissingRun(LookupError):
    pass


class CorruptRun(ValueError):
    pass


class ImmutableRun(ValueError):
    pass


class CorruptDataset(ValueError):
    pass


def data_root() -> Path:
    override = os.environ.get("EVIDRA_DATA")
    if override:
        return Path(override)
    return PROJECT_ROOT / "data" / "processed"


def runs_dir() -> Path:
    path = data_root() / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


DATA_REF_PREFIX = "data-root:"


def portable_ref(path: str | Path) -> str:
    raw = Path(path).resolve()
    try:
        return str(raw.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        pass
    try:
        return DATA_REF_PREFIX + str(raw.relative_to(data_root().resolve()))
    except ValueError:
        return raw.name


def resolve_ref(ref: str) -> Path:
    if ref.startswith(DATA_REF_PREFIX):
        return (data_root() / ref[len(DATA_REF_PREFIX) :]).resolve()
    p = Path(ref)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


def run_status(record: dict[str, Any]) -> str:
    if record.get("status") in {"running", "completed", "failed", "abstained"}:
        if record.get("error"):
            return "failed"
        return str(record["status"])
    if record.get("error"):
        return "failed"
    if record.get("decision") == "abstain" or record.get("stop_reason") == "abstain":
        return "abstained"
    if record.get("decision"):
        return "completed"
    return "running"


def metadata(record: dict[str, Any]) -> dict[str, Any]:
    rid = record.get("id") or record.get("run_id")
    return {
        "id": rid,
        "run_id": rid,
        "dataset_id": record.get("dataset_id"),
        "question": record.get("question"),
        "status": run_status(record),
        "created_at": record.get("created_at"),
        "completed_at": record.get("completed_at"),
    }


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    tmp.write_text(text + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _run_path(run_id: str) -> Path:
    safe = Path(run_id).name
    if safe != run_id or not run_id:
        raise MissingRun(run_id)
    return runs_dir() / f"{safe}.json"


def save_run(record: dict[str, Any]) -> dict[str, Any]:
    rid = record.get("id") or record.get("run_id")
    if not rid:
        raise ValueError("run id required")
    out = dict(record)
    out["id"] = rid
    out["status"] = run_status(out)
    if "created_at" not in out:
        out["created_at"] = utc_now()
    if out["status"] in TERMINAL and not out.get("completed_at"):
        out["completed_at"] = utc_now()
    path = _run_path(str(rid))
    if path.exists():
        existing = get_run(str(rid))
        if run_status(existing) in TERMINAL:
            raise ImmutableRun(str(rid))
    atomic_write(path, out)
    _upsert_index(metadata(out))
    return out


def get_run(run_id: str) -> dict[str, Any]:
    path = _run_path(run_id)
    if not path.exists():
        raise MissingRun(run_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorruptRun(run_id) from exc
    if not isinstance(data, dict) or not (data.get("id") or data.get("run_id")):
        raise CorruptRun(run_id)
    return data


def list_runs() -> list[dict[str, Any]]:
    rows = _scan_run_metadata()
    _write_index(rows)
    return rows


def _scan_run_metadata() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in runs_dir().glob("*.json"):
        if path.name == INDEX_NAME:
            continue
        try:
            rec = get_run(path.stem)
        except (MissingRun, CorruptRun):
            continue
        rows.append(metadata(rec))
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def _index_path() -> Path:
    return runs_dir() / INDEX_NAME


def _read_index() -> list[dict[str, Any]]:
    path = _index_path()
    if not path.exists():
        return _scan_run_metadata()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _scan_run_metadata()
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict) and isinstance(data.get("runs"), list):
        rows = [r for r in data["runs"] if isinstance(r, dict)]
    else:
        return _scan_run_metadata()
    if not rows and any(p.name != INDEX_NAME for p in runs_dir().glob("*.json")):
        return _scan_run_metadata()
    return rows


def _write_index(rows: list[dict[str, Any]]) -> None:
    atomic_write(_index_path(), {"runs": rows})


def _upsert_index(meta: dict[str, Any]) -> None:
    rows = _read_index()
    rid = meta.get("id")
    rows = [r for r in rows if (r.get("id") or r.get("run_id")) != rid]
    rows.append(meta)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    _write_index(rows)


def save_dataset(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    path = out.get("path")
    if path:
        out["path_ref"] = portable_ref(path)
        out.pop("path", None)
    dest = data_root() / "datasets"
    dest.mkdir(parents=True, exist_ok=True)
    atomic_write(dest / f"{out['id']}.json", {k: v for k, v in out.items() if k not in {"sample"}})
    return out


def get_dataset(dataset_id: str) -> dict[str, Any]:
    path = data_root() / "datasets" / f"{Path(dataset_id).name}.json"
    if not path.exists():
        raise LookupError(dataset_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorruptDataset(dataset_id) from exc
    if not isinstance(data, dict) or not data.get("id"):
        raise CorruptDataset(dataset_id)
    ref = data.get("path_ref") or data.get("path")
    if ref:
        resolved = resolve_ref(ref)
        if not resolved.exists():
            raise FileNotFoundError(str(resolved))
        data["path"] = str(resolved)
    return data


def save_chat(chat: dict[str, Any]) -> None:
    dest = data_root() / "chats"
    dest.mkdir(parents=True, exist_ok=True)
    slim = {
        "id": chat["id"],
        "dataset_id": chat.get("dataset_id"),
        "last_run_id": chat.get("last_run_id"),
        "messages": chat.get("messages") or [],
    }
    atomic_write(dest / f"{chat['id']}.json", slim)


def get_chat(chat_id: str) -> dict[str, Any]:
    path = data_root() / "chats" / f"{Path(chat_id).name}.json"
    if not path.exists():
        raise LookupError(chat_id)
    return json.loads(path.read_text(encoding="utf-8"))
