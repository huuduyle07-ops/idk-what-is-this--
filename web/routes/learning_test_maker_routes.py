"""Seeded mixed-format tests with deterministic objective marking and essay rubrics."""
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from core.learning.test_maker import catalog
from core.learning.test_maker_store import TestMakerStore
from core.learning.store import LearningError
from web.routes.learning_routes import _body, _learning_error, _owner, _private_response, _require_read_access

bp = Blueprint("learning_test_maker", __name__, url_prefix="/learn")
_DEFAULT_STORE = Path(__file__).resolve().parents[2] / ".agent" / "learning" / "test_maker.sqlite3"


def _store():
    return TestMakerStore(Path(current_app.config.get("LEARNING_TEST_MAKER_STORE_PATH", _DEFAULT_STORE)))


@bp.before_request
def _boundary():
    if request.endpoint != "learning_test_maker.page":
        _require_read_access()


bp.after_request(_private_response)
bp.register_error_handler(LearningError, _learning_error)


@bp.errorhandler(BadRequest)
@bp.errorhandler(UnsupportedMediaType)
def _invalid_body(error):
    return jsonify(ok=False, error_code="test_maker_invalid", error="Yêu cầu tạo hoặc làm đề chưa đúng định dạng."), 400


@bp.errorhandler(RequestEntityTooLarge)
def _large_body(error):
    return jsonify(ok=False, error_code="request_too_large", error="Bài làm quá dài. Hãy rút ngắn phần trả lời rồi gửi lại."), 413


@bp.get("/test-maker")
def page():
    _owner(create=True)
    return render_template("learning_test_maker.html")


@bp.get("/api/test-maker/catalog")
def test_catalog():
    _owner()
    return jsonify(ok=True, topics=catalog())


@bp.get("/api/test-maker")
def list_tests():
    owner = _owner()
    return jsonify(ok=True, tests=_store().list(owner))


@bp.post("/api/test-maker")
def create_test():
    owner = _owner()
    fields = {"request_id", "topic_ids", "seed"}
    body = _body(allowed=fields, required=fields)
    store = _store()
    selection = {key: body[key] for key in ("topic_ids", "seed")}
    previous = store.lookup_request(owner, body["request_id"], selection)
    if previous is not None:
        return jsonify(ok=True, test=previous), 200
    test = store.create(owner, body["request_id"], body["topic_ids"], body["seed"])
    return jsonify(ok=True, test=test), 201


@bp.get("/api/test-maker/<test_id>")
def get_test(test_id):
    owner = _owner()
    return jsonify(ok=True, test=_store().get(owner, test_id))


@bp.post("/api/test-maker/<test_id>/actions")
def test_action(test_id):
    owner = _owner()
    fields = {"action", "payload", "expected_revision", "request_id"}
    body = _body(allowed=fields, required=fields, maximum_bytes=128 * 1024)
    test = _store().act(owner, test_id, body["action"], body["payload"],
                        body["expected_revision"], body["request_id"])
    return jsonify(ok=True, test=test)


@bp.delete("/api/test-maker/<test_id>")
def delete_test(test_id):
    owner = _owner()
    _store().delete(owner, test_id)
    return jsonify(ok=True)
