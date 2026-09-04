"""HTTP upload resource limits. Fixture/CLI ingestion does not use this module."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from analysis.source import SourceBundle

_ALLOWED_SUFFIXES = frozenset({".csv", ".txt", ".xlsx", ".xls", ".zip"})
_CONTENT_LENGTH_SLACK = 256 * 1024
_CHUNK = 64 * 1024


class UploadLimitError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class UploadLimits:
    max_bytes: int
    max_rows: int
    max_columns: int
    max_cell_length: int
    max_zip_uncompressed_bytes: int
    max_zip_members: int
    max_filename_length: int = 200

    @classmethod
    def from_env(cls) -> UploadLimits:
        return cls(
            max_bytes=_env_int("EVIDRA_MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
            max_rows=_env_int("EVIDRA_MAX_UPLOAD_ROWS", 50_000),
            max_columns=_env_int("EVIDRA_MAX_UPLOAD_COLUMNS", 64),
            max_cell_length=_env_int("EVIDRA_MAX_UPLOAD_CELL_LENGTH", 4_096),
            max_zip_uncompressed_bytes=_env_int("EVIDRA_MAX_ZIP_UNCOMPRESSED_BYTES", 10 * 1024 * 1024),
            max_zip_members=_env_int("EVIDRA_MAX_ZIP_MEMBERS", 16),
        )


def reject_if_content_length_exceeds(content_length: str | None, limits: UploadLimits) -> None:
    if not content_length or not str(content_length).isdigit():
        return
    size = int(content_length)
    if size > limits.max_bytes + _CONTENT_LENGTH_SLACK:
        raise UploadLimitError(413, "Upload exceeds the maximum allowed size.")


def display_filename(raw: str, limits: UploadLimits) -> str:
    if not raw or not raw.strip():
        raise UploadLimitError(400, "Unsafe filename.")
    if raw.strip() != raw:
        raise UploadLimitError(400, "Unsafe filename.")
    if any(ord(ch) < 32 or ch == "\x7f" for ch in raw):
        raise UploadLimitError(400, "Unsafe filename.")
    if len(raw) > limits.max_filename_length:
        raise UploadLimitError(400, "Filename is too long.")
    if raw != Path(raw).name or "/" in raw or "\\" in raw:
        raise UploadLimitError(400, "Unsafe filename.")
    suffix = Path(raw).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise UploadLimitError(400, "CSV, Excel, or zip of CSVs only")
    return raw


def write_upload_file(upload, dest: Path, limits: UploadLimits) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = upload.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > limits.max_bytes:
                    raise UploadLimitError(413, "Upload exceeds the maximum allowed size.")
                out.write(chunk)
    except UploadLimitError:
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return written


async def write_upload_file_async(upload, dest: Path, limits: UploadLimits) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await upload.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > limits.max_bytes:
                    raise UploadLimitError(413, "Upload exceeds the maximum allowed size.")
                out.write(chunk)
    except UploadLimitError:
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return written


def inspect_zip_before_extract(path: Path, limits: UploadLimits) -> None:
    with ZipFile(path) as zf:
        infos = zf.infolist()
        if len(infos) > limits.max_zip_members:
            raise UploadLimitError(400, "ZIP contains too many members.")
        total = sum(max(0, int(info.file_size)) for info in infos)
        if total > limits.max_zip_uncompressed_bytes:
            raise UploadLimitError(413, "Upload exceeds the maximum allowed size.")
        for info in infos:
            if ".." in Path(info.filename).parts:
                raise UploadLimitError(400, "ZIP path traversal is not allowed.")


def extract_zip_member(zf: ZipFile, info, dest: Path, limits: UploadLimits | None) -> None:
    if ".." in Path(info.filename).parts:
        if limits is None:
            raise ValueError("zip path traversal")
        raise UploadLimitError(400, "ZIP path traversal is not allowed.")
    name = Path(info.filename).name
    if not name.lower().endswith(".csv"):
        return
    target = dest / name
    if limits is None:
        target.write_bytes(zf.read(info))
        return
    declared = max(0, int(info.file_size))
    if declared > limits.max_zip_uncompressed_bytes:
        raise UploadLimitError(413, "Upload exceeds the maximum allowed size.")
    written = 0
    with zf.open(info) as src, target.open("wb") as out:
        while True:
            chunk = src.read(_CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > limits.max_zip_uncompressed_bytes:
                raise UploadLimitError(413, "Upload exceeds the maximum allowed size.")
            if declared and written > declared:
                raise UploadLimitError(413, "Upload exceeds the maximum allowed size.")
            out.write(chunk)


def assert_upload_structure(src: SourceBundle, limits: UploadLimits) -> None:
    frames = [src.df, *src.tables.values()]
    for frame in frames:
        if len(frame) > limits.max_rows:
            raise UploadLimitError(400, "Upload exceeds the maximum allowed row count.")
        if int(frame.shape[1]) > limits.max_columns:
            raise UploadLimitError(400, "Upload exceeds the maximum allowed column count.")
        _assert_cell_length(frame, limits.max_cell_length)


def _assert_cell_length(frame: pd.DataFrame, max_len: int) -> None:
    for col in frame.columns:
        series = frame[col]
        if series.dtype != object and not pd.api.types.is_string_dtype(series):
            continue
        for value in series:
            if isinstance(value, str) and len(value) > max_len:
                raise UploadLimitError(400, "Upload exceeds the maximum allowed cell length.")
