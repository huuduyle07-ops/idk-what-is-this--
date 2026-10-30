"""Local lecture uploads with learner ownership and the existing web gate.

The WSGI body guard runs before the app's CSRF gate can inspect multipart form
fields. Document parsers have size limits but are not a public-upload sandbox.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from threading import BoundedSemaphore

from flask import Blueprint, current_app, jsonify, render_template, request, url_for
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType
from werkzeug.wrappers import Response
from werkzeug.wsgi import LimitedStream

from core.learning.material_library import MaterialLibrary, MaterialsError
from core.learning.knowledge_graph import LearningKnowledgeGraph
from core.learning.file_labels import FileLabelStore
from core.learning.file_label_suggestions import suggest_file_labels
from core.learning.chat_provider import ChatResponder
from core.learning.store import LearningError
from web.routes.learning_routes import _body, _learning_error, _owner, _private_response, _require_read_access


bp = Blueprint("learning_materials", __name__, url_prefix="/learn")
MAX_UPLOAD_FILES = 10
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_REQUEST_BYTES = 65 * 1024 * 1024
MAX_PATHS_FIELD = 16 * 1024
_IMPORT_PATH = "/learn/api/materials"
_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "targeted_subject"
_LABEL_SUGGESTION_SLOT = BoundedSemaphore(1)


def _early_error(code: str, message: str, status: int):
    response = Response(json.dumps({"ok": False, "error_code": code, "error": message}, ensure_ascii=False),
                        status=status, mimetype="application/json")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


class _UploadBodyBoundary:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Include slash-normalized aliases that Werkzeug can redirect, so its
        # routing normalization cannot bypass the pre-form body budget.
        path = "/" + "/".join(part for part in environ.get("PATH_INFO", "").split("/") if part)
        if environ.get("REQUEST_METHOD") != "POST" or path != _IMPORT_PATH:
            return self.app(environ, start_response)
        value = environ.get("CONTENT_LENGTH", "")
        if not isinstance(value, str) or not value:
            return _early_error("length_required", "Lượt tải tài liệu cần có Content-Length. Hãy tải lại từ trình duyệt.", 411)(environ, start_response)
        if not value.isascii() or not value.isdigit():
            return _early_error("invalid_request", "Dung lượng lượt tải không hợp lệ.", 400)(environ, start_response)
        if len(value) > 12 or int(value) > MAX_REQUEST_BYTES:
            return _early_error("request_too_large", "Lượt tải quá lớn. Mỗi lần chỉ gửi tối đa 64 MiB tài liệu.", 413)(environ, start_response)
        length = int(value)
        environ["wsgi.input"] = LimitedStream(environ["wsgi.input"], length)
        return self.app(environ, start_response)


@bp.record_once
def _install_upload_boundary(state):
    state.app.wsgi_app = _UploadBodyBoundary(state.app.wsgi_app)


def _library() -> MaterialLibrary:
    return MaterialLibrary(Path(current_app.config.get("TARGETED_SUBJECT_ROOT", _DEFAULT_ROOT)))


@bp.before_request
def _materials_boundary():
    if request.endpoint != "learning_materials.page":
        _require_read_access()


bp.after_request(_private_response)
bp.register_error_handler(LearningError, _learning_error)


@bp.errorhandler(MaterialsError)
def _materials_error(error):
    status = {
        "not_found": 404, "collection_not_found": 404,
        "request_collision": 409, "import_incomplete": 409, "output_exists": 409,
        "description_conflict": 409, "knowledge_conflict": 409,
        "label_conflict": 409, "file_labels_conflict": 409,
        "document_limit": 413, "file_too_large": 413, "text_limit": 413,
        "collection_too_large": 413, "file_labels_limit": 413,
        "library_limit": 429, "knowledge_limit": 429,
        "write_failed": 500, "invalid_storage": 500, "invalid_collection": 500,
    }.get(error.code, 400)
    return jsonify(ok=False, error_code=error.code, error=str(error)), status


@bp.errorhandler(BadRequest)
@bp.errorhandler(UnsupportedMediaType)
def _invalid_body(error):
    return jsonify(ok=False, error_code="invalid_request", error="Lượt tải tài liệu không đúng định dạng."), 400


@bp.errorhandler(RequestEntityTooLarge)
def _large_body(error):
    return jsonify(ok=False, error_code="request_too_large", error="Lượt tải vượt giới hạn: tối đa 10 tệp, 20 MiB mỗi tệp và 64 MiB tổng cộng."), 413


def _multipart():
    if request.mimetype != "multipart/form-data":
        raise UnsupportedMediaType()
    allowed_fields = {"title", "request_id", "paths"}
    if set(request.form) != allowed_fields or set(request.files) != {"files"}:
        raise LearningError("invalid_request", "Cần tên bộ tài liệu, mã lượt tải, danh sách đường dẫn và các tệp.", 400)
    if any(len(request.form.getlist(field)) != 1 for field in allowed_fields):
        raise LearningError("invalid_request", "Thông tin lượt tải bị lặp.", 400)
    title = request.form["title"]
    request_id = request.form["request_id"]
    raw_paths = request.form["paths"]
    if len(title) > 200 or len(request_id) > 128 or len(raw_paths) > MAX_PATHS_FIELD:
        raise LearningError("invalid_request", "Thông tin lượt tải quá dài.", 400)
    try:
        paths = json.loads(raw_paths)
    except (ValueError, UnicodeError):
        raise BadRequest() from None
    files = request.files.getlist("files")
    if not 1 <= len(files) <= MAX_UPLOAD_FILES:
        raise LearningError("invalid_request", "Mỗi lần chỉ nhập từ 1 đến 10 tệp bài giảng.", 400)
    if not isinstance(paths, list) or len(paths) != len(files) or any(not isinstance(path, str) for path in paths):
        raise LearningError("invalid_request", "Danh sách đường dẫn phải khớp với các tệp đã chọn.", 400)
    uploads = []
    total = 0
    for relative_path, uploaded in zip(paths, files):
        # Filenames from the browser are display metadata only. The library
        # validates relative paths and creates its own confined destination.
        extension = PurePosixPath(relative_path.replace("\\", "/")).suffix.lower()
        if extension in {".doc", ".ppt"}:
            raise LearningError("legacy_format", "Hãy chuyển .doc/.ppt sang .docx/.pptx hoặc PDF trước khi nhập.", 400)
        if extension not in {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg"}:
            raise LearningError("unsupported_format", "Chỉ hỗ trợ PDF, Word .docx, PowerPoint .pptx và ảnh PNG/JPEG.", 400)
        raw = uploaded.stream.read(MAX_FILE_BYTES + 1)
        total += len(raw)
        if len(raw) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise RequestEntityTooLarge()
        uploads.append((relative_path, raw))
    return request_id, title, uploads


@bp.get("/materials")
def page():
    _owner(create=True)
    return render_template("learning_materials.html")


@bp.get("/api/materials")
def list_materials():
    owner = _owner()
    return jsonify(ok=True, collections=_library().list(owner))


@bp.post("/api/materials")
def import_materials():
    owner = _owner()
    request_id, title, uploads = _multipart()
    collection, created = _library().import_files(owner, request_id, title, uploads)
    return jsonify(ok=True, collection=_collection_payload(collection)), 201 if created else 200


@bp.get("/api/materials/<collection_id>")
def get_materials(collection_id):
    owner = _owner()
    return jsonify(ok=True, collection=_collection_payload(_library().get(owner, collection_id)))


def _collection_payload(collection):
    for source in collection["sources"]:
        if source.get("image"):
            source["image_url"] = url_for("learning_materials.source_image", collection_id=collection["id"], digest=source["source_id"][7:])
    return collection


@bp.get("/api/materials/<collection_id>/sources/<digest>/image")
def source_image(collection_id, digest):
    raw, mime_type = _library().image(_owner(), collection_id, digest)
    response = Response(raw, mimetype=mime_type)
    response.headers["Content-Disposition"] = 'inline; filename="lecture-image.' + ("png" if mime_type == "image/png" else "jpg") + '"'
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    return response


@bp.put("/api/materials/<collection_id>/sources/<digest>/description")
def describe_image(collection_id, digest):
    owner = _owner()
    body = _body(allowed={"text", "expected_revision"}, required={"text", "expected_revision"})
    description = _library().describe_image(owner, collection_id, digest, body["text"], body["expected_revision"])
    return jsonify(ok=True, description=description)


@bp.get("/api/materials/<collection_id>/units/<unit_id>/knowledge")
def unit_knowledge(collection_id, unit_id):
    knowledge = LearningKnowledgeGraph(_library()).get(_owner(), collection_id, unit_id)
    return jsonify(ok=True, knowledge=knowledge)


@bp.get("/api/materials/<collection_id>/map")
def collection_map(collection_id):
    view = LearningKnowledgeGraph(_library()).collection_map(_owner(), collection_id)
    return jsonify(ok=True, map=view)


@bp.put("/api/materials/<collection_id>/units/<unit_id>/knowledge/concepts")
def set_unit_concepts(collection_id, unit_id):
    owner = _owner()
    body = _body(allowed={"labels", "expected_revision"}, required={"labels", "expected_revision"})
    knowledge = LearningKnowledgeGraph(_library()).set_concepts(
        owner, collection_id, unit_id, body["labels"], body["expected_revision"],
    )
    return jsonify(ok=True, knowledge=knowledge)


def _label_responder():
    return current_app.config.get("LEARNING_CHAT_RESPONDER") or ChatResponder()


@bp.get("/api/materials/<collection_id>/labels")
def file_labels(collection_id):
    files = FileLabelStore(_library()).list(_owner(), collection_id)
    return jsonify(ok=True, files=files, model=_label_responder().public_config())


@bp.put("/api/materials/<collection_id>/sources/<digest>/labels")
def save_file_labels(collection_id, digest):
    owner = _owner()
    body = _body(allowed={"labels", "expected_revision"}, required={"labels", "expected_revision"})
    record = FileLabelStore(_library()).save(owner, collection_id, digest, body["labels"], body["expected_revision"])
    return jsonify(ok=True, file=record)


@bp.post("/api/materials/<collection_id>/sources/<digest>/labels/suggest")
def suggest_labels(collection_id, digest):
    owner = _owner()
    body = _body(allowed={"expected_revision"}, required={"expected_revision"})
    expected = body["expected_revision"]
    if type(expected) is not int or expected < 0:
        raise LearningError("invalid_labels", "Phiên bản nhãn không hợp lệ.", 400)
    library = _library()
    store = FileLabelStore(library)
    current = store.get(owner, collection_id, digest)
    if current["revision"] != expected:
        raise LearningError("label_conflict", "Nhãn đã thay đổi. Tải lại nhãn để xem bản đã lưu trước khi đề xuất tiếp.", 409)
    # Bound model work in the local app. No queue or automatic retry can silently
    # spend another model call; a lost response is recovered with a read.
    if not _LABEL_SUGGESTION_SLOT.acquire(blocking=False):
        raise LearningError("labels_busy", "Đang tạo một đề xuất nhãn. Hãy đợi lượt đó hoàn tất rồi thử lại.", 429)
    try:
        if store.get(owner, collection_id, digest)["revision"] != expected:
            raise LearningError("label_conflict", "Nhãn đã thay đổi. Hãy tải lại nhãn trước khi tiếp tục.", 409)
        proposal = suggest_file_labels(library, owner, collection_id, digest, _label_responder())
        # The long model call holds no storage lock. Compare-and-swap prevents a
        # late proposal from overwriting a user's edit in another tab.
        record = store.save_suggestion(owner, collection_id, digest, proposal, expected)
        return jsonify(ok=True, file=record)
    finally:
        _LABEL_SUGGESTION_SLOT.release()
