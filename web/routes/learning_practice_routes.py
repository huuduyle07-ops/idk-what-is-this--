"""Explicit source-backed practice generation, review and durable attempts."""
from pathlib import Path
from threading import BoundedSemaphore

from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from core.learning.chat_provider import ChatResponder
from core.learning.materials import MaterialsError
from core.learning.practice_generation import prepare_practice, generate_prepared_practice
from core.learning.practice_store import PracticeStore
from core.learning.store import LearningError
from web.routes.learning_routes import _body, _learning_error, _owner, _private_response, _require_read_access
from web.routes.learning_material_routes import _library, _materials_error

bp = Blueprint("learning_practice", __name__, url_prefix="/learn")
_DEFAULT_STORE = Path(__file__).resolve().parents[2] / ".agent" / "learning" / "practice.sqlite3"
_GENERATION_SLOT = BoundedSemaphore(1)


def _store():
    return PracticeStore(Path(current_app.config.get("LEARNING_PRACTICE_STORE_PATH", _DEFAULT_STORE)))


def _responder():
    return current_app.config.get("LEARNING_CHAT_RESPONDER") or ChatResponder()


@bp.before_request
def _boundary():
    if request.endpoint != "learning_practice.page":
        _require_read_access()


bp.after_request(_private_response)
bp.register_error_handler(LearningError, _learning_error)
bp.register_error_handler(MaterialsError, _materials_error)


@bp.errorhandler(BadRequest)
@bp.errorhandler(UnsupportedMediaType)
def _invalid_body(error):
    return jsonify(ok=False, error_code="invalid_practice_input", error="Yêu cầu luyện tập chưa đúng định dạng."), 400


@bp.errorhandler(RequestEntityTooLarge)
def _large_body(error):
    return jsonify(ok=False, error_code="request_too_large", error="Yêu cầu luyện tập quá dài. Hãy chọn một phần nhỏ hơn."), 413


@bp.get("/practice")
def page():
    _owner(create=True)
    return render_template("learning_practice.html")


@bp.get("/api/practice/config")
def config():
    _owner()
    return jsonify(ok=True, model=_responder().public_config())


@bp.get("/api/practice")
def list_practice():
    return jsonify(ok=True, practices=_store().list(_owner()))


@bp.post("/api/practice")
def create_practice():
    owner = _owner()
    fields = {"request_id", "collection_id", "unit_ids", "count"}
    body = _body(allowed=fields, required=fields)
    selection = {key: body[key] for key in ("collection_id", "unit_ids", "count")}
    store = _store()
    existing = store.lookup_request(owner, body["request_id"], selection)
    if existing is not None:
        return jsonify(ok=True, practice=existing), 202 if existing["status"] == "generating" else 200
    # Pin the learner's exact source selection before generating. Resuming an
    # existing request above never re-reads changed notes or calls another model.
    prepared = prepare_practice(_library(), owner, body["collection_id"], body["unit_ids"], body["count"])
    responder = _responder()
    configuration = responder.public_config()
    if not configuration["available"]:
        raise LearningError("chat_not_configured", configuration["reason"], 503)
    if not _GENERATION_SLOT.acquire(blocking=False):
        raise LearningError("practice_busy", "Đang tạo một bộ câu hỏi. Hãy đợi lượt đó hoàn tất rồi thử lại.", 429)
    try:
        reserved = store.reserve(owner, body["request_id"], prepared)
        if not reserved["claimed"]:
            view = reserved["practice"]
            return jsonify(ok=True, practice=view), 202 if view["status"] == "generating" else 200
        identifier = reserved["practice"]["id"]
        try:
            bundle = generate_prepared_practice(prepared, responder)
            view = store.finish(owner, identifier, body["request_id"], bundle)
        except Exception:
            # Persist one failed generation, without provider exceptions, paths
            # or source text. Replaying this request cannot silently retry AI.
            view = store.fail(owner, identifier, body["request_id"])
        return jsonify(ok=True, practice=view), 201
    finally:
        _GENERATION_SLOT.release()


@bp.get("/api/practice/<practice_id>")
def get_practice(practice_id):
    return jsonify(ok=True, practice=_store().get(_owner(), practice_id))


@bp.post("/api/practice/<practice_id>/actions")
def practice_action(practice_id):
    owner = _owner()
    fields = {"action", "payload", "expected_revision", "request_id"}
    body = _body(allowed=fields, required=fields)
    view = _store().act(owner, practice_id, body["action"], body["payload"],
                        body["expected_revision"], body["request_id"])
    return jsonify(ok=True, practice=view)


@bp.delete("/api/practice/<practice_id>")
def delete_practice(practice_id):
    _store().delete(_owner(), practice_id)
    return jsonify(ok=True)
