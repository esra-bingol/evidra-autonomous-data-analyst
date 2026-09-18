"""Optional shared access token. Not multi-tenant auth."""

from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

COOKIE = "evidra_access"
OPEN_PREFIXES = ("/health", "/auth/", "/static/")
OPEN_GET_PAGES = frozenset({"/", "/chat", "/dashboard", "/console", "/report"})


def bind_host() -> str:
    return (os.environ.get("EVIDRA_HOST") or "127.0.0.1").strip() or "127.0.0.1"


def bind_port() -> int:
    raw = (os.environ.get("EVIDRA_PORT") or "8765").strip()
    try:
        port = int(raw)
    except ValueError:
        return 8765
    if port < 1 or port > 65535:
        return 8765
    return port


def access_token() -> str:
    return (os.environ.get("EVIDRA_ACCESS_TOKEN") or "").strip()


def required() -> bool:
    return bool(access_token())


def _matches(given: str, expected: str) -> bool:
    if not given or not expected or len(given) != len(expected):
        return False
    return hmac.compare_digest(given, expected)


def token_matches(given: str) -> bool:
    return _matches((given or "").strip(), access_token())


def unlocked(request: Request) -> bool:
    if not required():
        return True
    token = access_token()
    cookie = request.cookies.get(COOKIE) or ""
    header = request.headers.get("authorization") or ""
    bearer = header[7:].strip() if header.lower().startswith("bearer ") else ""
    return _matches(cookie, token) or _matches(bearer, token)


def status_payload(request: Request) -> dict[str, bool]:
    return {"required": required(), "unlocked": unlocked(request)}


async def gate_middleware(request: Request, call_next):
    if not required():
        return await call_next(request)
    path = request.url.path
    if path.startswith(OPEN_PREFIXES):
        return await call_next(request)
    if request.method == "GET" and path in OPEN_GET_PAGES:
        return await call_next(request)
    if unlocked(request):
        return await call_next(request)
    return JSONResponse({"detail": "access token required"}, status_code=401)
