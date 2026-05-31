"""Phase 12.15a - Harness Control routes.

GET /harness/controls          → grouped registry + read-only docker status.
POST /harness/controls/overlay → Save overlay (persist desired value), and
                                 live-patch editable_live controls in-process.

Read-only with respect to models / DB / patching. This phase never writes
``.env`` or ``docker-compose.yml`` and never starts/stops containers.
"""
from __future__ import annotations

from flask import Blueprint, request

from core import harness_controls as hc


bp = Blueprint("harness_controls_routes", __name__)


def _docker_status() -> dict:
    """Reuse the existing read-only docker probe. Fail-soft to a stub."""
    try:
        from core.health import check_docker_sandbox

        return check_docker_sandbox()
    except Exception as exc:  # noqa: BLE001 - never let the panel crash
        return {
            "name": "Docker sandbox",
            "status": "error",
            "detail": f"probe failed: {type(exc).__name__}: {exc}"[:160],
        }


@bp.route("/harness/controls", methods=["GET"])
def harness_controls_list():
    try:
        categories = hc.list_categories()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"failed to list controls: {exc}"}, 500
    try:
        env_diff = hc.pending_env_diff()
    except Exception:  # noqa: BLE001 - never let a diff probe crash the panel
        env_diff = []
    try:
        compose_diff = hc.preview_compose_patch()
    except Exception:  # noqa: BLE001
        compose_diff = []
    return {
        "ok": True,
        "categories": categories,
        "docker_status": _docker_status(),
        "env_diff": env_diff,
        "compose_diff": compose_diff,
    }


@bp.route("/harness/controls/apply-env", methods=["POST"])
def harness_controls_apply_env():
    payload = request.get_json(silent=True) or request.form
    control_ids = payload.get("control_ids")
    if control_ids is not None and not isinstance(control_ids, list):
        return {"ok": False, "error": "control_ids must be a list"}, 400

    try:
        report = hc.apply_to_env_files(control_ids=control_ids)
    except hc.HarnessControlError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"unexpected error: {exc}"}, 500

    return {"ok": True, "report": report}


@bp.route("/harness/controls/compose-preview", methods=["POST"])
def harness_controls_compose_preview():
    payload = request.get_json(silent=True) or request.form
    control_ids = payload.get("control_ids")
    if control_ids is not None and not isinstance(control_ids, list):
        return {"ok": False, "error": "control_ids must be a list"}, 400

    try:
        diff = hc.preview_compose_patch(control_ids=control_ids)
    except hc.HarnessControlError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"unexpected error: {exc}"}, 500

    return {"ok": True, "diff": diff}


@bp.route("/harness/controls/compose-apply", methods=["POST"])
def harness_controls_compose_apply():
    payload = request.get_json(silent=True) or request.form
    control_ids = payload.get("control_ids")
    if control_ids is not None and not isinstance(control_ids, list):
        return {"ok": False, "error": "control_ids must be a list"}, 400

    try:
        report = hc.apply_compose_patch(control_ids=control_ids)
    except hc.HarnessControlError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"unexpected error: {exc}"}, 500

    return {"ok": True, "report": report}


@bp.route("/harness/controls/overlay", methods=["POST"])
def harness_controls_overlay():
    payload = request.get_json(silent=True) or request.form
    control_id = str(payload.get("control_id") or "").strip()
    if not control_id:
        return {"ok": False, "error": "control_id is required"}, 400
    if "value" not in payload:
        return {"ok": False, "error": "value is required"}, 400
    value = payload.get("value")

    try:
        control = hc.set_override(control_id, value)
    except hc.HarnessControlError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"unexpected error: {exc}"}, 500

    return {"ok": True, "control": control}
