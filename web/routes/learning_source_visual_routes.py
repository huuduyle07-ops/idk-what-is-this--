"""On-demand source images with immutable provenance; no visual interpretation."""
from flask import Blueprint, current_app, jsonify, url_for
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from core.learning.materials import MaterialsError
from core.learning.source_visual_store import SourceVisualStore
from core.learning.store import LearningError
from web.routes.learning_material_routes import _library
from web.routes.learning_routes import _body, _learning_error, _owner, _private_response, _require_read_access


bp = Blueprint("learning_source_visuals", __name__, url_prefix="/learn")


def _store():
    return SourceVisualStore(_library(), renderer=current_app.config.get("LEARNING_SOURCE_VISUAL_RENDERER"))


bp.before_request(_require_read_access)
bp.after_request(_private_response)
bp.register_error_handler(LearningError, _learning_error)


@bp.errorhandler(MaterialsError)
def _visual_error(error):
    status = {
        "not_found": 404, "collection_not_found": 404, "visual_not_found": 404,
        "visual_source_changed": 409, "visual_busy": 429, "visual_limit": 413,
        "document_limit": 413, "visual_unavailable": 503, "extractor_unavailable": 503,
        "visual_render_failed": 502, "visual_storage_error": 500,
        "invalid_collection": 500, "invalid_storage": 500, "write_failed": 500,
    }.get(error.code, 400)
    return jsonify(ok=False, error_code=error.code, error=str(error)), status


@bp.errorhandler(BadRequest)
@bp.errorhandler(UnsupportedMediaType)
def _invalid_body(error):
    return jsonify(ok=False, error_code="visual_invalid", error="Yêu cầu chuẩn bị hình không đúng định dạng."), 400


@bp.errorhandler(RequestEntityTooLarge)
def _large_body(error):
    return jsonify(ok=False, error_code="request_too_large", error="Yêu cầu chuẩn bị hình quá dài."), 413


def _public(record, collection_id):
    return {**record, "visuals": [
        {**visual, "image_url": url_for("learning_source_visuals.image", collection_id=collection_id,
                                       unit_id=record["unit_id"], visual_id=visual["id"])}
        for visual in record["visuals"]
    ]}


@bp.get("/api/materials/<collection_id>/units/<unit_id>/visuals")
def get_visuals(collection_id, unit_id):
    record = _store().get(_owner(), collection_id, unit_id)
    return jsonify(ok=True, record=_public(record, collection_id))


@bp.post("/api/materials/<collection_id>/units/<unit_id>/visuals")
def prepare_visuals(collection_id, unit_id):
    _body(allowed=set(), maximum_bytes=1024)
    record = _store().prepare(_owner(), collection_id, unit_id)
    return jsonify(ok=True, record=_public(record, collection_id))


@bp.get("/api/materials/<collection_id>/units/<unit_id>/visuals/<visual_id>/image")
def image(collection_id, unit_id, visual_id):
    raw, mime_type = _store().image(_owner(), collection_id, unit_id, visual_id)
    response = current_app.response_class(raw, mimetype=mime_type)
    extension = "png" if mime_type == "image/png" else "jpg"
    response.headers["Content-Disposition"] = f'inline; filename="source-visual.{extension}"'
    return response
