"""Confdence — patient-owned Quebec health record. Local dogfood."""

from __future__ import annotations

import io
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import qrcode
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from qrcode.image.svg import SvgPathImage

from store import Store
from mcp_auth import (
    AUTH_COOKIE,
    AuthRequired,
    LockedOut,
    cookie_matches,
    has_password,
    install_agent_hash,
    lock as auth_lock,
    mint_agent_token,
    revoke_agent_token,
    session_valid,
    set_password as auth_set_password,
    unlock as auth_unlock,
)
from mcp_consent import (
    CONSENT_VERSION,
    REQUIRED_ACKS,
    ConsentOff,
    disable as mcp_disable,
    enable as mcp_enable,
    is_enabled as mcp_is_enabled,
    load_consent,
    save_snapshot,
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / ".data"
SESSION_COOKIE = "health_session"
CSRF_COOKIE = "health_csrf"
SESSION_TTL = timedelta(hours=12)
SHARE_TTL = timedelta(hours=8)
DEMO_LOGIN = os.environ.get("HEALTH_ALLOW_DEMO_LOGIN", "1") == "1"
TESTING = os.environ.get("HEALTH_TESTING", "0") == "1"

store = Store(Path(os.environ.get("HEALTH_DB", DATA_DIR / "health.db")))
store.seed_demo_if_empty()

app = FastAPI(title="Confdence", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))

# method -> hits. Auth routes stay tight.
_HITS: dict[str, deque[float]] = defaultdict(deque)
_LIMITS = {
    "session": 5 if not TESTING else 1000,
    "auth": 5 if not TESTING else 1000,
    "write": 60 if not TESTING else 1000,
    "read": 120 if not TESTING else 1000,
    "share": 30 if not TESTING else 1000,
}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_ok(bucket: str, key: str, per_minute: int) -> bool:
    now = time.time()
    q = _HITS[f"{bucket}:{key}"]
    cutoff = now - 60
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= per_minute:
        return False
    q.append(now)
    return True


def _limited(request: Request, bucket: str) -> JSONResponse | None:
    if not _rate_ok(bucket, _client_ip(request), _LIMITS[bucket]):
        return JSONResponse({"error": "rate_limited"}, status_code=429)
    return None


def _session_patient(request: Request) -> int | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return store.session_patient(token)


def _origin_ok(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        # same-origin form posts may omit Origin; require a matching Referer
        referer = request.headers.get("referer")
        if not referer:
            return False
        origin = referer
    try:
        incoming = urlparse(origin)
    except ValueError:
        return False
    host = request.headers.get("host", "")
    return incoming.netloc == host


def _csrf_ok(request: Request) -> bool:
    header = request.headers.get("x-csrf-token")
    cookie = request.cookies.get(CSRF_COOKIE)
    return bool(header and cookie and secrets.compare_digest(header, cookie))


def _json_error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        AUTH_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )


def _authed(request: Request) -> bool:
    return cookie_matches(request.cookies.get(AUTH_COOKIE))


def _set_csrf(response: Response, token: str | None = None) -> str:
    value = token or secrets.token_urlsafe(32)
    response.set_cookie(
        CSRF_COOKIE,
        value,
        httponly=False,
        samesite="lax",
        secure=False,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )
    return value


def _qr_svg(url: str) -> str:
    img = qrcode.make(url, image_factory=SvgPathImage, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    html = (ROOT / "confdence.html").read_text(encoding="utf-8")
    response = HTMLResponse(html)
    if not request.cookies.get(CSRF_COOKIE):
        _set_csrf(response)
    return response


@app.get("/s/{token}", response_class=HTMLResponse)
def share_page(request: Request, token: str) -> HTMLResponse:
    limited = _limited(request, "share")
    if limited:
        return templates.TemplateResponse(
            request, "share.html", {"state": "rate", "payload": None}, status_code=429
        )
    opened = store.open_share(token)
    if not opened:
        return templates.TemplateResponse(
            request, "share.html", {"state": "gone", "payload": None}, status_code=404
        )
    return templates.TemplateResponse(
        request, "share.html", {"state": "ok", "payload": opened}
    )


@app.post("/api/session")
def create_session(request: Request) -> Response:
    limited = _limited(request, "session")
    if limited:
        return limited
    if not DEMO_LOGIN:
        return _json_error("demo_login_disabled", 403)
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    patient_id = store.demo_patient_id()
    if patient_id is None:
        return _json_error("no_patient", 500)
    token = secrets.token_urlsafe(32)
    store.create_session(patient_id, token, SESSION_TTL)
    response = JSONResponse({"ok": True})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )
    _set_csrf(response)
    return response


@app.delete("/api/session")
def end_session(request: Request) -> Response:
    limited = _limited(request, "write")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        store.delete_session(token)
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/api/me")
def me(request: Request) -> Response:
    limited = _limited(request, "read")
    if limited:
        return limited
    patient_id = _session_patient(request)
    if patient_id is None:
        return _json_error("unauthorized", 401)
    record = store.get_record(patient_id)
    if record is None:
        return _json_error("not_found", 404)
    return JSONResponse({"record": record, "shares": store.list_shares(patient_id)})


@app.put("/api/me")
async def update_me(request: Request) -> Response:
    limited = _limited(request, "write")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    patient_id = _session_patient(request)
    if patient_id is None:
        return _json_error("unauthorized", 401)
    try:
        body = await request.json()
    except Exception:
        return _json_error("invalid_json")
    if not isinstance(body, dict):
        return _json_error("invalid_json")
    try:
        record = store.update_record(patient_id, body)
    except ValueError as exc:
        return _json_error(str(exc))
    return JSONResponse({"record": record})


@app.post("/api/shares")
async def create_share(request: Request) -> Response:
    limited = _limited(request, "write")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    patient_id = _session_patient(request)
    if patient_id is None:
        return _json_error("unauthorized", 401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    label = None
    if isinstance(body, dict) and body.get("label"):
        label = str(body["label"])[:80]
    token = secrets.token_urlsafe(24)
    share_id = secrets.token_urlsafe(12)
    share = store.create_share(patient_id, share_id, token, SHARE_TTL, label)
    url = str(request.base_url).rstrip("/") + f"/s/{token}"
    return JSONResponse(
        {
            "share": share,
            "url": url,
            "qr_svg": _qr_svg(url),
        }
    )


@app.delete("/api/shares/{share_id}")
def revoke_share(request: Request, share_id: str) -> Response:
    limited = _limited(request, "write")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    patient_id = _session_patient(request)
    if patient_id is None:
        return _json_error("unauthorized", 401)
    if not store.revoke_share(share_id, patient_id):
        return _json_error("not_found", 404)
    return JSONResponse({"ok": True})


@app.get("/s/{token}/json")
def share_json(request: Request, token: str) -> Response:
    limited = _limited(request, "share")
    if limited:
        return limited
    opened = store.open_share(token)
    if not opened:
        return _json_error("gone", 404)
    return JSONResponse(opened)


@app.get("/logout")
def logout_redirect() -> RedirectResponse:
    return RedirectResponse("/", status_code=302)


@app.get("/api/mcp/status")
def mcp_status(request: Request) -> Response:
    limited = _limited(request, "read")
    if limited:
        return limited
    return JSONResponse(
        {
            "enabled": mcp_is_enabled(),
            "unlocked": session_valid() and _authed(request),
            "has_password": has_password(),
            "version": CONSENT_VERSION,
            "required": list(REQUIRED_ACKS),
            "consent": load_consent(),
        }
    )


@app.post("/api/mcp/consent")
async def mcp_consent(request: Request) -> Response:
    limited = _limited(request, "write")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    try:
        body = await request.json()
    except Exception:
        return _json_error("invalid_json")
    if not isinstance(body, dict):
        return _json_error("invalid_json")
    if body.get("enabled") is False:
        return JSONResponse({"consent": mcp_disable(), "enabled": False})
    if not _authed(request):
        return _json_error("auth_required", 401)
    try:
        row = mcp_enable(list(body.get("acknowledged") or []))
    except ValueError as exc:
        return _json_error(str(exc))
    return JSONResponse({"consent": row, "enabled": True})


@app.put("/api/mcp/snapshot")
async def mcp_snapshot(request: Request) -> Response:
    limited = _limited(request, "write")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    if not _authed(request):
        return _json_error("auth_required", 401)
    try:
        body = await request.json()
    except Exception:
        return _json_error("invalid_json")
    if not isinstance(body, dict):
        return _json_error("invalid_json")
    record = body.get("record") if isinstance(body.get("record"), dict) else {}
    incidents = body.get("incidents") if isinstance(body.get("incidents"), list) else []
    try:
        save_snapshot(record, incidents)
    except AuthRequired as exc:
        return _json_error(str(exc), 401)
    except ConsentOff as exc:
        return _json_error(str(exc), 403)
    return JSONResponse({"ok": True})


@app.get("/api/auth/status")
def auth_status(request: Request) -> Response:
    limited = _limited(request, "read")
    if limited:
        return limited
    return JSONResponse(
        {
            "has_password": has_password(),
            "unlocked": _authed(request),
        }
    )


@app.post("/api/auth/set")
async def auth_set(request: Request) -> Response:
    limited = _limited(request, "auth")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    try:
        body = await request.json()
    except Exception:
        return _json_error("invalid_json")
    if not isinstance(body, dict):
        return _json_error("invalid_json")
    try:
        session = auth_set_password(str(body.get("password") or ""))
    except ValueError as exc:
        return _json_error(str(exc))
    response = JSONResponse({"ok": True, "has_password": True, "unlocked": True})
    _set_auth_cookie(response, session["token"])
    return response


@app.post("/api/auth/unlock")
async def auth_unlock_route(request: Request) -> Response:
    limited = _limited(request, "auth")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    try:
        body = await request.json()
    except Exception:
        return _json_error("invalid_json")
    if not isinstance(body, dict):
        return _json_error("invalid_json")
    try:
        session = auth_unlock(str(body.get("password") or ""))
    except LockedOut as exc:
        return _json_error(str(exc), 429)
    except AuthRequired as exc:
        return _json_error(str(exc), 401)
    response = JSONResponse({"ok": True, "unlocked": True})
    _set_auth_cookie(response, session["token"])
    return response


@app.post("/api/auth/lock")
def auth_lock_route(request: Request) -> Response:
    limited = _limited(request, "auth")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    auth_lock()
    response = JSONResponse({"ok": True, "unlocked": False})
    response.delete_cookie(AUTH_COOKIE, path="/")
    return response


@app.post("/api/auth/agent/mint")
async def auth_agent_mint(request: Request) -> Response:
    limited = _limited(request, "auth")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    if not _authed(request):
        return _json_error("auth_required", 401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    if isinstance(body, dict) and body.get("hash"):
        try:
            install_agent_hash({"hash": str(body["hash"])})
        except ValueError as exc:
            return _json_error(str(exc))
        return JSONResponse({"ok": True, "has_agent_token": True})
    try:
        token = mint_agent_token()
    except AuthRequired as exc:
        return _json_error(str(exc), 401)
    return JSONResponse({"token": token, "has_agent_token": True})


@app.post("/api/auth/agent/revoke")
def auth_agent_revoke(request: Request) -> Response:
    limited = _limited(request, "auth")
    if limited:
        return limited
    if not _origin_ok(request) or not _csrf_ok(request):
        return _json_error("csrf", 403)
    if not _authed(request):
        return _json_error("auth_required", 401)
    revoke_agent_token()
    return JSONResponse({"ok": True, "has_agent_token": False})
