"""Learner chat with an optional fixed, owner-scoped lecture collection."""
from pathlib import Path
import re

from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from core.learning.chat_provider import ChatResponder
from core.learning.chat_store import ChatStore
from core.learning.chat_retrieval import LectureRetriever, is_followup
from core.learning.materials import MaterialsError
from core.learning.store import LearningError
from web.routes.learning_routes import _body, _learning_error, _owner, _private_response, _require_read_access
from web.routes.learning_material_routes import _library, _materials_error

bp = Blueprint("learning_chat", __name__, url_prefix="/learn")
_DEFAULT_STORE = Path(__file__).resolve().parents[2] / ".agent" / "learning" / "chats.sqlite3"


def _store():
    return ChatStore(Path(current_app.config.get("LEARNING_CHAT_STORE_PATH", _DEFAULT_STORE)))


def _responder():
    return current_app.config.get("LEARNING_CHAT_RESPONDER") or ChatResponder()


@bp.before_request
def _chat_boundary():
    if request.endpoint != "learning_chat.page":
        _require_read_access()


bp.after_request(_private_response)
bp.register_error_handler(LearningError, _learning_error)
bp.register_error_handler(MaterialsError, _materials_error)


@bp.errorhandler(BadRequest)
@bp.errorhandler(UnsupportedMediaType)
def _invalid_body(error):
    return jsonify(ok=False, error_code="invalid_chat_input", error="Nội dung gửi lên không hợp lệ."), 400


@bp.errorhandler(RequestEntityTooLarge)
def _large_body(error):
    return jsonify(ok=False, error_code="request_too_large", error="Tin nhắn quá dài. Hãy chia thành phần nhỏ hơn."), 413


@bp.get("/chat")
def page():
    _owner(create=True)
    return render_template("learning_chat.html")


@bp.get("/api/chat/config")
def config():
    _owner()
    return jsonify(ok=True, config=_responder().public_config())


@bp.get("/api/chats")
def list_chats():
    return jsonify(ok=True, conversations=_store().list(_owner()))


@bp.post("/api/chats")
def create_chat():
    owner = _owner()
    data = _body(allowed={"request_id", "collection_id"}, required={"request_id"})
    collection = None
    if data.get("collection_id") is not None:
        # IDs and scope come from the server library; clients cannot submit
        # paths, excerpts, titles or a different learner's material context.
        collection = _library().get(owner, data["collection_id"])
    return jsonify(ok=True, conversation=_store().create(
        owner, data["request_id"], collection_id=collection["id"] if collection else None,
        collection_title=collection["title"] if collection else None)), 201


def _citations(answer, evidence):
    """Validate reference membership, not whether a claim is entailed by text."""
    available = {source["citation_id"] for source in evidence["sources"]}
    mentions = set(re.findall(r"\[(S\d+)\]", answer))
    evidence = {**evidence, "cited_ids": sorted(mentions & available),
                "invalid_citation_ids": sorted(mentions - available)[:100]}
    answer = re.sub(r"\[(S\d+)\]", lambda match: match[0] if match[1] in available
                    else "(nguồn không xác định)", answer)
    return answer, evidence


@bp.get("/api/chats/<conversation_id>")
def get_chat(conversation_id):
    return jsonify(ok=True, conversation=_store().get(_owner(), conversation_id))


@bp.delete("/api/chats/<conversation_id>")
def delete_chat(conversation_id):
    _store().delete(_owner(), conversation_id)
    return jsonify(ok=True)


@bp.post("/api/chats/<conversation_id>/messages")
def send_message(conversation_id):
    owner = _owner()
    body = _body(allowed={"request_id", "text", "expected_revision"},
                 required={"request_id", "text", "expected_revision"}, maximum_bytes=50 * 1024)
    store = _store()
    # Check ownership before exposing provider readiness or reserving a turn.
    store.get(owner, conversation_id)
    responder = _responder()
    configuration = responder.public_config()
    if not configuration["available"]:
        raise LearningError("chat_not_configured", configuration["reason"], 503)
    turn = store.begin_turn(owner, conversation_id, body["request_id"], body["text"], body["expected_revision"])
    if not turn["claimed"]:
        view = turn["conversation"]
        return jsonify(ok=True, conversation=view), 202 if view["pending"] else 200
    try:
        collection = turn["conversation"].get("collection")
        evidence = None
        provider, model = configuration["provider"], configuration["model"]
        if collection:
            previous = next((item["content"] for item in reversed(turn["conversation"]["messages"][:-1])
                             if item["role"] == "user" and item.get("status") == "completed"
                             and not is_followup(item["content"])), "")
            evidence = LectureRetriever(_library()).retrieve(owner, collection["id"], body["text"], previous_query=previous)
            if evidence["status"] == "no_match":
                answer = ("I couldn't find a relevant passage in the selected lecture collection. "
                          "Search currently uses keywords and does not translate questions into the language of your sources. "
                          "Try terms used in the lecture, check its extracted text in Materials, "
                          "or start a General knowledge conversation.")
                provider, model = "retrieval", "lexical-v1"
            else:
                answer = responder.respond(turn["messages"], grounding=evidence)
            answer, evidence = _citations(answer, evidence)
        else:
            answer = responder.respond(turn["messages"])
        view = store.finish_turn(owner, conversation_id, turn["turn_id"], answer,
                                 provider, model, evidence=evidence)
    except Exception as error:
        # Persist failure so retries after lost responses cannot spend another call.
        code = error.code if isinstance(error, LearningError) and error.code in {
            "chat_provider_error", "chat_not_configured", "chat_conflict"} else "chat_provider_error"
        try:
            store.fail_turn(owner, conversation_id, turn["turn_id"], code)
        except LearningError:
            pass  # A lease expiry/deletion must not be undone by this old worker.
        raise LearningError(code, "Chưa nhận được câu trả lời. Câu hỏi đã lưu; đọc lại hội thoại rồi gửi một lượt mới nếu muốn thử tiếp.",
                            409 if code == "chat_conflict" else 502) from None
    return jsonify(ok=True, conversation=view)
