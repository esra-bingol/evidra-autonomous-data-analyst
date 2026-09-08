from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from analysis.chat import handle_message
from analysis.report import build_investigation_report
from analysis import store
from analysis.capabilities import detect_capabilities
from analysis.graph import run_investigation
from analysis.limits import (
    UploadLimitError,
    UploadLimits,
    assert_upload_structure,
    display_filename,
    inspect_zip_before_extract,
    reject_if_content_length_exceeds,
    write_upload_file_async,
)
from analysis.load import load_source
from analysis.olist import is_olist_dir
from analysis.roles import infer_roles
from analysis.tools.runtime import inspect_dataset

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"
UPLOAD_DIR = ROOT / "data" / "processed" / "uploads"
PORT = 8765

_FIXTURE_FILES = {
    "clear_driver": ROOT / "data" / "fixtures" / "clear_driver.csv",
    "aov_trap": ROOT / "data" / "fixtures" / "aov_trap.csv",
    "no_signal": ROOT / "data" / "fixtures" / "no_signal.csv",
    "missingness": ROOT / "data" / "fixtures" / "missingness.csv",
    "superstore": ROOT / "data" / "raw" / "superstore.csv",
    "olist": ROOT / "data" / "raw",
    "uci_retail": ROOT / "data" / "fixtures" / "retail_line_items.csv",
}

_datasets: dict[str, dict[str, Any]] = {}
_runs: dict[str, dict[str, Any]] = {}
_chats: dict[str, dict[str, Any]] = {}


def reset_store() -> None:
    _datasets.clear()
    _runs.clear()
    _chats.clear()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class FixtureBody(BaseModel):
    fixture_id: str


class AnalyzeBody(BaseModel):
    question: str = Field(min_length=1)


class ChatMessageBody(BaseModel):
    text: str = Field(min_length=1)


class ChatCreateBody(BaseModel):
    dataset_id: str


def catalog() -> list[dict[str, Any]]:
    rows = []
    for fid, path in _FIXTURE_FILES.items():
        if fid == "olist":
            rows.append({"id": fid, "name": fid, "path": str(path), "available": is_olist_dir(path)})
            continue
        if path.exists():
            rows.append({"id": fid, "name": fid, "path": str(path), "available": True})
        elif fid in {"superstore"}:
            rows.append({"id": fid, "name": fid, "path": str(path), "available": False})
    return rows


def _overview(path: Path) -> dict[str, Any]:
    return _overview_from_source(load_source(path))


def _overview_from_source(src) -> dict[str, Any]:
    inspect = inspect_dataset(src.df, src.tables).to_dict()["value"]
    roles = infer_roles(src.df)
    cols = list(map(str, src.df.columns))
    for frame in src.tables.values():
        cols.extend(map(str, frame.columns))
    caps = detect_capabilities(
        roles, n_tables=int(src.meta.get("n_tables") or 1), available_columns=cols
    ).to_dict()["value"]
    return {
        "n_rows": inspect["n_rows"],
        "n_cols": inspect["n_cols"],
        "n_tables": inspect.get("n_tables") or 1,
        "tables": inspect.get("tables") or [],
        "columns": inspect["columns"],
        "sample": inspect["sample"],
        "roles": roles,
        "capabilities": caps,
    }


def _cleanup_upload(dest: Path) -> None:
    dest.unlink(missing_ok=True)
    extracted = dest.parent / f"{dest.stem}_extracted"
    if extracted.is_dir():
        shutil.rmtree(extracted, ignore_errors=True)


def _persist_run(payload: dict[str, Any]) -> dict[str, Any]:
    saved = store.save_run(payload)
    _runs[saved["id"]] = saved
    return saved


def _load_run(run_id: str) -> dict[str, Any]:
    rec = _runs.get(run_id)
    if rec:
        return rec
    rec = store.get_run(run_id)
    _runs[run_id] = rec
    return rec


def _load_dataset(dataset_id: str) -> dict[str, Any] | None:
    rec = _datasets.get(dataset_id)
    if rec:
        return rec
    try:
        rec = store.get_dataset(dataset_id)
    except LookupError:
        return None
    except FileNotFoundError as exc:
        raise HTTPException(422, "dataset file missing") from exc
    except (OSError, json.JSONDecodeError, store.CorruptDataset) as exc:
        raise HTTPException(422, "dataset record corrupt") from exc
    _datasets[dataset_id] = rec
    return rec


def _load_chat(chat_id: str) -> dict[str, Any] | None:
    rec = _chats.get(chat_id)
    if rec:
        return rec
    try:
        rec = store.get_chat(chat_id)
    except LookupError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "chat record corrupt") from exc
    _chats[chat_id] = rec
    return rec


def create_app() -> FastAPI:
    app = FastAPI(title="Evidra", version="0.8.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/fixtures")
    def list_fixtures() -> dict[str, Any]:
        return {"items": catalog()}

    @app.post("/datasets")
    async def create_dataset(request: Request) -> dict[str, Any]:
        ctype = request.headers.get("content-type", "")
        if "application/json" in ctype:
            body = FixtureBody.model_validate(await request.json())
            path = _FIXTURE_FILES.get(body.fixture_id)
            if path is None or (body.fixture_id == "olist" and not is_olist_dir(path)):
                raise HTTPException(404, f"fixture not available: {body.fixture_id}")
            if path is None or (body.fixture_id != "olist" and not path.exists()):
                raise HTTPException(404, f"fixture not available: {body.fixture_id}")
            did = _new_id("ds")
            rec = {"id": did, "name": body.fixture_id, "path": str(path), "source": "fixture"}
            rec.update(_overview(path))
            _datasets[did] = rec
            store.save_dataset(rec)
            rec["path"] = str(path)
            return rec
        limits = UploadLimits.from_env()
        try:
            reject_if_content_length_exceeds(request.headers.get("content-length"), limits)
        except UploadLimitError as exc:
            raise HTTPException(exc.status_code, exc.detail) from None
        form = await request.form()
        upload = form.get("file")
        filename = getattr(upload, "filename", None)
        if not upload or not filename:
            raise HTTPException(400, "upload a CSV/Excel/zip or send fixture_id")
        try:
            safe_name = display_filename(str(filename), limits)
        except UploadLimitError as exc:
            raise HTTPException(exc.status_code, exc.detail) from None
        suffix = Path(safe_name).suffix.lower()
        dest_dir = store.data_root() / "uploads"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"
        try:
            await write_upload_file_async(upload, dest, limits)
        except UploadLimitError as exc:
            raise HTTPException(exc.status_code, exc.detail) from None
        if not dest.exists() or dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, "empty file")
        try:
            if suffix == ".zip":
                inspect_zip_before_extract(dest, limits)
            src = load_source(dest, upload_limits=limits)
            assert_upload_structure(src, limits)
            rec = {
                "id": _new_id("ds"),
                "name": safe_name,
                "path": str(dest),
                "source": "upload",
            }
            rec.update(_overview_from_source(src))
        except UploadLimitError as exc:
            _cleanup_upload(dest)
            raise HTTPException(exc.status_code, exc.detail) from None
        except HTTPException:
            _cleanup_upload(dest)
            raise
        except Exception as exc:
            _cleanup_upload(dest)
            raise HTTPException(400, str(exc)) from exc
        _datasets[rec["id"]] = rec
        store.save_dataset(rec)
        rec["path"] = str(dest)
        return rec

    @app.get("/datasets/{dataset_id}")
    def get_dataset(dataset_id: str) -> dict[str, Any]:
        rec = _load_dataset(dataset_id)
        if not rec:
            raise HTTPException(404, "dataset not found")
        return rec

    @app.post("/datasets/{dataset_id}/analyze")
    def analyze(dataset_id: str, body: AnalyzeBody) -> dict[str, Any]:
        rec = _load_dataset(dataset_id)
        if not rec:
            raise HTTPException(404, "dataset not found")
        if not Path(rec["path"]).exists():
            raise HTTPException(422, "dataset file missing")
        question = body.question.strip()
        if not question:
            raise HTTPException(400, "question required")
        rid = _new_id("run")
        created = store.utc_now()
        try:
            result = run_investigation(rec["path"], question)
        except Exception as exc:
            payload = {
                "id": rid,
                "dataset_id": dataset_id,
                "dataset_ref": rec.get("path_ref") or store.portable_ref(rec["path"]),
                "question": question,
                "error": str(exc),
                "decision": None,
                "stop_reason": None,
                "status": "failed",
                "created_at": created,
                "plan": [],
                "hypotheses": [],
                "claims": [],
                "evidence": [],
                "charts": [],
                "traces": [],
            }
            saved = _persist_run(payload)
            return JSONResponse(status_code=400, content=jsonable_encoder(saved))
        payload = {
            "id": rid,
            "dataset_id": dataset_id,
            "dataset_ref": rec.get("path_ref") or store.portable_ref(rec["path"]),
            "question": question,
            "error": None,
            **result,
            "created_at": created,
        }
        saved = _persist_run(payload)
        return jsonable_encoder(saved)

    @app.get("/runs")
    def list_runs() -> dict[str, Any]:
        return {"runs": store.list_runs()}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            rec = _load_run(run_id)
        except store.MissingRun:
            raise HTTPException(404, "run not found") from None
        except store.CorruptRun:
            raise HTTPException(422, "run record corrupt") from None
        return jsonable_encoder(rec)

    @app.get("/runs/{run_id}/report")
    def get_run_report(run_id: str) -> dict[str, Any]:
        try:
            rec = _load_run(run_id)
        except store.MissingRun:
            raise HTTPException(404, "run not found") from None
        except store.CorruptRun:
            raise HTTPException(422, "run record corrupt") from None
        report = rec.get("investigation_report")
        if not report:
            report = build_investigation_report(rec)
        return jsonable_encoder(report)

    @app.get("/report")
    def report_page() -> FileResponse:
        page = UI_DIR / "report.html"
        if not page.exists():
            raise HTTPException(500, "report UI missing")
        return FileResponse(page)

    @app.post("/chats")
    def create_chat(body: ChatCreateBody) -> dict[str, Any]:
        rec = _load_dataset(body.dataset_id)
        if not rec:
            raise HTTPException(404, "dataset not found")
        cid = _new_id("chat")
        chat = {
            "id": cid,
            "dataset_id": body.dataset_id,
            "last_run_id": None,
            "messages": [],
        }
        _chats[cid] = chat
        store.save_chat(chat)
        return chat

    @app.get("/chats/{chat_id}")
    def get_chat(chat_id: str) -> dict[str, Any]:
        chat = _load_chat(chat_id)
        if not chat:
            raise HTTPException(404, "chat not found")
        return jsonable_encoder(chat)

    @app.post("/chats/{chat_id}/messages")
    def post_chat_message(chat_id: str, body: ChatMessageBody) -> dict[str, Any]:
        chat = _load_chat(chat_id)
        if not chat:
            raise HTTPException(404, "chat not found")
        ds = _load_dataset(chat["dataset_id"])
        if not ds:
            raise HTTPException(404, "dataset not found")
        if not Path(ds["path"]).exists():
            raise HTTPException(422, "dataset file missing")
        text = body.text.strip()
        if not text:
            raise HTTPException(400, "text required")
        last = None
        if chat.get("last_run_id"):
            try:
                last = _load_run(chat["last_run_id"])
            except (store.MissingRun, store.CorruptRun):
                last = None
        user_msg = {"role": "user", "text": text}
        chat["messages"].append(user_msg)

        def _investigate(path: str, question: str) -> dict[str, Any]:
            return run_investigation(path, question)

        turn = handle_message(
            text=text,
            dataset_path=ds["path"],
            last_run=last,
            investigate=_investigate,
        )
        if turn.get("ran_investigation"):
            raw = turn.pop("run", {}) or {}
            rid = _new_id("run")
            payload = {
                "id": rid,
                "dataset_id": chat["dataset_id"],
                "dataset_ref": ds.get("path_ref") or store.portable_ref(ds["path"]),
                "question": text,
                "error": raw.get("error"),
                **raw,
                "created_at": store.utc_now(),
            }
            payload["id"] = rid
            saved = _persist_run(payload)
            chat["last_run_id"] = rid
            turn["run_id"] = rid
            turn["status"] = {
                "decision": saved.get("decision"),
                "stop_reason": saved.get("stop_reason"),
                "primary_driver": saved.get("primary_driver"),
            }
            turn["claim_ids"] = [c.get("claim_id") for c in (saved.get("claims") or []) if c.get("claim_id")]
            eids: list[str] = []
            for claim in saved.get("claims") or []:
                for eid in claim.get("evidence_ids") or []:
                    if eid not in eids:
                        eids.append(eid)
            turn["evidence_ids"] = eids
        assistant = {k: v for k, v in turn.items() if k != "run"}
        chat["messages"].append(assistant)
        store.save_chat(chat)
        return jsonable_encoder({"chat": chat, "message": assistant})

    @app.get("/chat")
    def chat_page() -> FileResponse:
        page = UI_DIR / "chat.html"
        if not page.exists():
            raise HTTPException(500, "chat UI missing")
        return FileResponse(page)

    @app.get("/dashboard")
    def dashboard_page() -> FileResponse:
        page = UI_DIR / "dashboard.html"
        if not page.exists():
            raise HTTPException(500, "dashboard UI missing")
        return FileResponse(page)

    @app.get("/console")
    def console_page() -> FileResponse:
        page = UI_DIR / "index.html"
        if not page.exists():
            raise HTTPException(500, "console UI missing")
        return FileResponse(page)

    @app.get("/")
    def index() -> FileResponse:
        index = UI_DIR / "index.html"
        if not index.exists():
            raise HTTPException(500, "UI missing")
        return FileResponse(index)

    if UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("analysis.api:app", host="127.0.0.1", port=PORT, reload=False)


if __name__ == "__main__":
    main()
