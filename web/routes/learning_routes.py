"""Small authored Teacher pilot; no model, shell, repo read, or patch execution.

The application's existing origin/CSRF/auth mutation gate applies to this
blueprint. A separate opaque, durable learner cookie scopes learning records;
it never grants authority to the coding runtime or replaces web authentication.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets

from flask import Blueprint, current_app, g, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from core.learning.store import LearningError, LearningStore
from core.learning.lesson import ITEMS
from web import browser_session
from web.auth_gate import extract_web_auth_token

bp = Blueprint("learning", __name__, url_prefix="/learn")
LEARNER_COOKIE = "cattus_learner"
_KEY = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_DEFAULT_STORE = Path(__file__).resolve().parents[2] / ".agent" / "learning" / "sessions.sqlite3"
_MAX_BODY = 16 * 1024


def _store() -> LearningStore:
    return LearningStore(Path(current_app.config.get("LEARNING_STORE_PATH", _DEFAULT_STORE)))


def _owner(*, create: bool = False) -> str:
    values = request.cookies.getlist(LEARNER_COOKIE)
    if len(values) > 1:
        raise LearningError("invalid_learner", "Phiên học không hợp lệ. Hãy mở lại trang Học.", 400)
    value = values[0] if values else None
    if value is not None and not _KEY.fullmatch(value):
        raise LearningError("invalid_learner", "Phiên học không hợp lệ. Hãy xóa cookie của trang và thử lại.", 400)
    if value is None:
        if not create:
            raise LearningError("learner_required", "Hãy mở trang Học trước khi tiếp tục.", 401)
        value = secrets.token_urlsafe(32)
        g.learning_cookie = value
    return hashlib.sha256(("cattus-learning-v1:" + value).encode("ascii")).hexdigest()


def _require_read_access() -> None:
    token = (os.environ.get("WEB_AUTH_TOKEN") or "").strip()
    if token:
        session = browser_session.read_session(
            request.cookies.getlist(browser_session.COOKIE_NAME), configured_token=token
        ).session
        header_ok = browser_session.web_auth_token_matches(extract_web_auth_token(request.headers), token)
        if not ((session and session.authenticated) or header_ok):
            raise LearningError("auth_required", "Đăng nhập vào C.A.T.T.U.S để mở phiên học.", 401)
    elif request.remote_addr not in {"127.0.0.1", "::1", "localhost"}:
        raise LearningError("local_only", "Phiên học cục bộ chỉ mở từ máy đang chạy C.A.T.T.U.S.", 403)


@bp.before_request
def _learning_boundary():
    if request.endpoint == "learning.page":
        return None  # The shell is public; records below require their owner.
    _require_read_access()
    if (request.content_length or 0) > _MAX_BODY:
        raise RequestEntityTooLarge()
    return None


@bp.after_request
def _private_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    cookie = g.pop("learning_cookie", None)
    if cookie:
        response.set_cookie(LEARNER_COOKIE, cookie, max_age=30 * 24 * 60 * 60,
                            httponly=True, secure=request.is_secure,
                            samesite="Strict", path="/learn")
    return response


@bp.errorhandler(LearningError)
def _learning_error(error):
    return jsonify(ok=False, error_code=error.code, error=str(error)), error.status_code


@bp.errorhandler(BadRequest)
@bp.errorhandler(UnsupportedMediaType)
def _invalid_body(error):
    return jsonify(ok=False, error_code="invalid_request", error="Dữ liệu gửi lên không hợp lệ."), 400


@bp.errorhandler(RequestEntityTooLarge)
def _large_body(error):
    return jsonify(ok=False, error_code="request_too_large", error="Câu trả lời quá dài. Hãy rút gọn rồi gửi lại."), 413


def _body(*, allowed: set[str], required: set[str] = frozenset(), maximum_bytes: int = _MAX_BODY) -> dict:
    if not request.is_json:
        raise UnsupportedMediaType()
    raw = request.stream.read(maximum_bytes + 1)
    if len(raw) > maximum_bytes:
        raise RequestEntityTooLarge()
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise BadRequest() from None
    if not isinstance(data, dict) or set(data) - allowed or required - set(data):
        raise LearningError("invalid_request", "Dữ liệu gửi lên không đúng định dạng.", 400)
    return data


@bp.get("")
@bp.get("/")
def page():
    _owner(create=True)
    return render_template("learn.html", lesson_preview={
        "code": ITEMS[0]["code"], "filename": ITEMS[0]["filename"],
    })


@bp.get("/api/session")
def latest_session():
    return jsonify(ok=True, session=_store().latest(_owner()))


@bp.post("/api/sessions")
def create_session():
    _body(allowed=set())
    return jsonify(ok=True, session=_store().create(_owner())), 201


@bp.get("/api/sessions/<session_id>")
def get_session(session_id):
    return jsonify(ok=True, session=_store().get(_owner(), session_id))


@bp.post("/api/sessions/<session_id>/actions")
def session_action(session_id):
    fields = {"action", "payload", "expected_revision", "request_id"}
    data = _body(allowed=fields, required=fields)
    result = _store().act(_owner(), session_id, data["action"], data["payload"],
                          data["expected_revision"], data["request_id"])
    return jsonify(ok=True, session=result)


@bp.get("/api/sessions/<session_id>/export")
def export_session(session_id):
    response = jsonify(_store().export(_owner(), session_id))
    response.headers["Content-Disposition"] = 'attachment; filename="cattus-lesson.json"'
    return response


@bp.delete("/api/sessions/<session_id>")
def delete_session(session_id):
    _store().delete(_owner(), session_id)
    return jsonify(ok=True)
