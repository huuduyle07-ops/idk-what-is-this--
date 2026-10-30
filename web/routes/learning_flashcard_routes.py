"""Owner-scoped flashcards copied from completed Practice; no model calls."""
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from core.learning.flashcard_store import FlashcardStore
from core.learning.store import LearningError
from web.routes.learning_routes import _body, _learning_error, _owner, _private_response, _require_read_access
from web.routes.learning_practice_routes import _store as _practice_store

bp = Blueprint("learning_flashcards", __name__, url_prefix="/learn")
_DEFAULT_STORE = Path(__file__).resolve().parents[2] / ".agent" / "learning" / "flashcards.sqlite3"


def _store():
    return FlashcardStore(Path(current_app.config.get("LEARNING_FLASHCARD_STORE_PATH", _DEFAULT_STORE)))


@bp.before_request
def _boundary():
    if request.endpoint != "learning_flashcards.page":
        _require_read_access()


bp.after_request(_private_response)
bp.register_error_handler(LearningError, _learning_error)


@bp.errorhandler(BadRequest)
@bp.errorhandler(UnsupportedMediaType)
def _invalid_body(error):
    return jsonify(ok=False, error_code="flashcards_invalid", error="Yêu cầu thẻ ôn tập chưa đúng định dạng."), 400


@bp.errorhandler(RequestEntityTooLarge)
def _large_body(error):
    return jsonify(ok=False, error_code="request_too_large", error="Yêu cầu thẻ ôn tập quá dài."), 413


@bp.get("/flashcards")
def page():
    _owner(create=True)
    return render_template("learning_flashcards.html")


@bp.get("/api/flashcards")
def list_decks():
    owner = _owner()
    return jsonify(ok=True, decks=_store().list(owner))


@bp.post("/api/flashcards")
def create_deck():
    owner = _owner()
    fields = {"request_id", "practice_id", "question_ids"}
    body = _body(allowed=fields, required=fields)
    selection = {key: body[key] for key in ("practice_id", "question_ids")}
    store = _store()
    previous = store.lookup_request(owner, body["request_id"], selection)
    if previous is not None:
        return jsonify(ok=True, deck=previous), 200
    # Only read this learner's completed public Practice projection. Its answers
    # were already available after completion; no new AI operation or hidden
    # answer-key export is needed to create the deterministic review deck.
    practice = _practice_store().get(owner, body["practice_id"])
    if practice["status"] != "completed":
        raise LearningError("flashcards_conflict", "Hoàn thành bộ Practice trước khi tạo thẻ ôn tập từ bộ đó.", 409)
    deck = store.create(owner, body["request_id"], practice, body["question_ids"])
    return jsonify(ok=True, deck=deck), 201


@bp.get("/api/flashcards/<deck_id>")
def get_deck(deck_id):
    owner = _owner()
    return jsonify(ok=True, deck=_store().get(owner, deck_id))


@bp.post("/api/flashcards/<deck_id>/actions")
def deck_action(deck_id):
    owner = _owner()
    fields = {"action", "payload", "expected_revision", "request_id"}
    body = _body(allowed=fields, required=fields)
    deck = _store().act(owner, deck_id, body["action"], body["payload"],
                        body["expected_revision"], body["request_id"])
    return jsonify(ok=True, deck=deck)


@bp.delete("/api/flashcards/<deck_id>")
def delete_deck(deck_id):
    owner = _owner()
    _store().delete(owner, deck_id)
    return jsonify(ok=True)
