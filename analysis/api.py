from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from analysis.capabilities import detect_capabilities
from analysis.graph import run_investigation
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
}

_datasets: dict[str, dict[str, Any]] = {}
_runs: dict[str, dict[str, Any]] = {}


def reset_store() -> None:
    _datasets.clear()
    _runs.clear()


class FixtureBody(BaseModel):
    fixture_id: str


class AnalyzeBody(BaseModel):
    question: str = Field(min_length=1)


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
    src = load_source(path)
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


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def create_app() -> FastAPI:
    app = FastAPI(title="Evidra", version="0.7.0")

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
            return rec
        form = await request.form()
        upload = form.get("file")
        filename = getattr(upload, "filename", None)
        if not upload or not filename:
            raise HTTPException(400, "upload a CSV/Excel/zip or send fixture_id")
        suffix = Path(str(filename)).suffix.lower()
        if suffix not in {".csv", ".txt", ".xlsx", ".xls", ".zip"}:
            raise HTTPException(400, "CSV, Excel, or zip of CSVs only")
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
        dest.write_bytes(await upload.read())
        if dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, "empty file")
        did = _new_id("ds")
        try:
            rec = {"id": did, "name": str(filename), "path": str(dest), "source": "upload"}
            rec.update(_overview(dest))
        except Exception as exc:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, str(exc)) from exc
        _datasets[did] = rec
        return rec

    @app.get("/datasets/{dataset_id}")
    def get_dataset(dataset_id: str) -> dict[str, Any]:
        rec = _datasets.get(dataset_id)
        if not rec:
            raise HTTPException(404, "dataset not found")
        return rec

    @app.post("/datasets/{dataset_id}/analyze")
    def analyze(dataset_id: str, body: AnalyzeBody) -> dict[str, Any]:
        rec = _datasets.get(dataset_id)
        if not rec:
            raise HTTPException(404, "dataset not found")
        question = body.question.strip()
        if not question:
            raise HTTPException(400, "question required")
        rid = _new_id("run")
        try:
            result = run_investigation(rec["path"], question)
        except Exception as exc:
            payload = {
                "id": rid,
                "dataset_id": dataset_id,
                "question": question,
                "error": str(exc),
                "decision": None,
                "stop_reason": None,
                "plan": [],
                "hypotheses": [],
                "claims": [],
                "evidence": [],
                "charts": [],
                "traces": [],
            }
            _runs[rid] = payload
            return JSONResponse(status_code=400, content=jsonable_encoder(payload))
        payload = {
            "id": rid,
            "dataset_id": dataset_id,
            "question": question,
            "error": None,
            **result,
        }
        _runs[rid] = payload
        return jsonable_encoder(payload)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        rec = _runs.get(run_id)
        if not rec:
            raise HTTPException(404, "run not found")
        return jsonable_encoder(rec)

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
