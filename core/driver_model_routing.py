"""H.1 Driver Model Routing Contract — contract/report-only.

The Driver inspects a Worker Assignment (F.5) and recommends the safest allowed
"vehicle" (model level) for that task. The Driver does not drive yet: it only
produces an inert recommendation artifact under ``.agent/driver_decisions``.

This module never:

* calls any model
* switches providers
* spends API credits
* launches workers
* applies patches
* runs validation
* triggers Dream
* triggers Project Evolution execution
* calls webhooks / network
* promotes lessons

It only reads a worker assignment (a JSON file or an in-memory dict) and writes
inert ``driver_decision.json`` / ``driver_decision.md`` artifacts.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DRIVER_DECISIONS_DIRNAME = "driver_decisions"

# --- Vehicle levels (stable string constants) -----------------------------
LOCAL_ONLY = "local_only"
FREE_MODEL_OK = "free_model_ok"
CHEAP_API_OK = "cheap_api_ok"
STRONG_MODEL_RECOMMENDED = "strong_model_recommended"
STRONG_MODEL_REQUIRES_APPROVAL = "strong_model_requires_approval"
VISION_OR_HUMAN_CAPTION_REQUIRED = "vision_or_human_caption_required"
HUMAN_ONLY = "human_only"
BLOCKED = "blocked"

# Ordered weakest -> safest/most-restrictive. The Driver recommends the safest
# (highest-index) vehicle that any triggered rule requires. ``blocked`` is the
# top of the order so a block overrides every other recommendation.
VEHICLE_LEVELS = [
    LOCAL_ONLY,
    FREE_MODEL_OK,
    CHEAP_API_OK,
    STRONG_MODEL_RECOMMENDED,
    STRONG_MODEL_REQUIRES_APPROVAL,
    VISION_OR_HUMAN_CAPTION_REQUIRED,
    HUMAN_ONLY,
    BLOCKED,
]

MODE_LABELS: dict[str, str] = {
    "debug": "Debug",
    "project_evolution": "Project Evolution",
    "dream_trial": "Dream Trial",
    "documentation": "Documentation",
    "review_only": "Review-only",
}

# Visual-evidence and security keyword sets. Single tokens are matched on word
# boundaries (so "environment" does NOT match "env"); phrases are matched as
# substrings of the scanned text.
VISUAL_TOKENS = {
    "screenshot",
    "screenshots",
    "image",
    "images",
    "visual",
    "visuals",
    "ocr",
    "chart",
    "charts",
    "poster",
    "posters",
    "design",
    "designs",
}
VISUAL_PHRASES = {"ui layout", "user interface layout"}

SECURITY_TOKENS = {
    "secret",
    "secrets",
    "auth",
    "token",
    "tokens",
    "credential",
    "credentials",
    "env",
    "permission",
    "permissions",
    "webhook",
    "webhooks",
}
SECURITY_PHRASES = {"api key", "api-key", "apikey", "rate limit", "rate-limit", "webhook security"}

PATCH_LIKE_TOKENS = {
    "patch",
    "fix",
    "edit",
    "apply",
    "implement",
    "implementation",
    "bug",
    "regression",
    "repair",
    "refactor",
}

# Boilerplate that every F.5 worker assignment carries. These generic guardrail
# lines mention "visual evidence" / "secrets/env" but are NOT task-specific
# signals, so they are excluded from keyword scanning to avoid false positives.
_BOILERPLATE_MARKERS = (
    "visual evidence is required",
    "secrets/env",
    "do not apply patches",
    "do not call models",
)

_EXECUTION_BOUNDARY = [
    "No model was called.",
    "No provider was switched.",
    "No worker was launched.",
    "No patch was applied.",
    "No validation was run.",
    "No promotion occurred.",
]


# ==========================================================================
# Pure policy
# ==========================================================================


def evaluate_assignment_policy(
    assignment: dict[str, Any],
    *,
    source_type: str = "worker_assignment",
    source_path: str = "",
) -> dict[str, Any]:
    """Evaluate a worker assignment (or plain dict) and return a routing decision.

    Pure function: no IO, no side effects. Returns a dict with
    ``recommended_vehicle``, ``approval_required``, ``blocked``, ``reasons``,
    ``risk_flags`` and ``missing_requirements``.
    """
    mode = normalize_mode(assignment.get("mode"))
    role = _text(assignment.get("worker_role")).lower()
    allowed = _string_list(assignment.get("allowed_files"))
    validation = _string_list(assignment.get("validation_commands"))
    stop_conditions = _string_list(assignment.get("stop_conditions"))
    safety_rules = _string_list(assignment.get("safety_rules"))
    expected_output = _text(assignment.get("expected_output"))
    title = _text(assignment.get("title"))
    wa_source_type = _text(assignment.get("source_type"))
    wa_source_path = _text(assignment.get("source_path"))
    apply_allowed = _truthy(assignment.get("apply_allowed"))
    worker_launch_allowed = _truthy(assignment.get("worker_launch_allowed"))
    auto_apply = _truthy(assignment.get("auto_apply")) or _truthy(
        assignment.get("apply_patches_automatically")
    )

    reasons: list[str] = []
    risk_flags: list[str] = []
    missing: list[str] = []
    approval = False
    vehicle = LOCAL_ONLY
    floor = LOCAL_ONLY

    scan_text = _scan_text(title, expected_output, role, stop_conditions, safety_rules)

    # --- Base recommendation by mode --------------------------------------
    if mode == "Review-only":
        vehicle = LOCAL_ONLY
        reasons.append("Review-only task: critique/report work fits a local or free model.")
    elif mode == "Project Evolution":
        vehicle = _max_vehicle(vehicle, STRONG_MODEL_RECOMMENDED)
        approval = True
        _add(risk_flags, "broad_change")
        reasons.append(
            "Project Evolution implies broad change; a stronger model is recommended with human approval."
        )
    elif mode == "Dream Trial":
        vehicle = _max_vehicle(vehicle, CHEAP_API_OK)
        approval = True
        _add(risk_flags, "experimental_workflow")
        reasons.append(
            "Dream Trial is an experimental workflow; approval is required and Dream must not start in this contract."
        )
    elif mode == "Documentation":
        vehicle = _max_vehicle(vehicle, FREE_MODEL_OK)
        reasons.append("Documentation task: a free model is usually sufficient for drafting text.")
    else:  # Debug or unknown -> treat as Debug.
        if not validation:
            vehicle = _max_vehicle(vehicle, CHEAP_API_OK)
            _add(risk_flags, "missing_validation")
            if _expects_patch_like_output(mode, role, title, expected_output):
                approval = True
            reasons.append(
                "Debug task is missing validation commands; recommend at least a cheap API and flag missing validation."
            )
        else:
            vehicle = _max_vehicle(vehicle, FREE_MODEL_OK)
            if allowed:
                reasons.append(
                    "Narrow Debug task with validation and no apply: a free model is sufficient."
                )

    # --- Rule: visual evidence --------------------------------------------
    if _mentions(scan_text, VISUAL_TOKENS, VISUAL_PHRASES):
        vehicle = _max_vehicle(vehicle, VISION_OR_HUMAN_CAPTION_REQUIRED)
        approval = True
        _add(risk_flags, "visual_evidence_unverified")
        _add(missing, "human_visual_summary_or_vision_model")
        reasons.append(
            "Task references visual evidence; a vision model or human caption summary is required "
            "before a text-only model can proceed."
        )

    # --- Rule: security-sensitive work ------------------------------------
    if _mentions(scan_text, SECURITY_TOKENS, SECURITY_PHRASES):
        vehicle = _max_vehicle(vehicle, STRONG_MODEL_REQUIRES_APPROVAL)
        approval = True
        _add(risk_flags, "security_sensitive")
        reasons.append(
            "Task touches security-sensitive material; a strong model with explicit approval is recommended."
        )

    # --- Rule: missing allowed files (scope unclear) ----------------------
    if not allowed and mode in ("Debug", "Project Evolution"):
        vehicle = _max_vehicle(vehicle, STRONG_MODEL_REQUIRES_APPROVAL)
        approval = True
        _add(risk_flags, "scope_unclear")
        reasons.append(
            "No allowed files are declared for a Debug/Project Evolution task; scope is unclear and needs human scoping."
        )

    # --- Rule: External Queue seed / untrusted source ---------------------
    if _is_external_queue(wa_source_type, source_path, wa_source_path):
        _add(risk_flags, "external_untrusted_source")
        floor = _max_vehicle(floor, FREE_MODEL_OK)
        if _could_modify_code(mode):
            approval = True
        reasons.append(
            "Source originates from the External Queue (untrusted); do not route below a free model and "
            "require approval for any code-modifying task."
        )

    # --- Rule: forbidden write/apply intent (blocked) ---------------------
    # Highest priority: H.1 is contract/report-only and never executes.
    blocked = bool(apply_allowed or worker_launch_allowed or auto_apply)
    if blocked:
        vehicle = BLOCKED
        approval = True
        reasons.append(
            "apply_allowed/worker_launch_allowed is set, but H.1 is contract/report-only and does not permit "
            "execution, provider switching, or worker launch; blocked pending a separate human-approved execution phase."
        )

    # Apply the floor last (never lowers; ``blocked`` stays because it is the
    # top of the order).
    vehicle = _max_vehicle(vehicle, floor)

    return {
        "recommended_vehicle": vehicle,
        "approval_required": bool(approval or blocked),
        "blocked": blocked,
        "reasons": _dedupe(reasons),
        "risk_flags": _dedupe(risk_flags),
        "missing_requirements": _dedupe(missing),
    }


# ==========================================================================
# Decision record + IO
# ==========================================================================


def evaluate_driver_route(
    *,
    worker_assignment_path: str | None = None,
    assignment: dict[str, Any] | None = None,
    repo_path: str | None = None,
    dry_run: bool = False,
    output_root: str | None = None,
    created_at: str | None = None,
    driver_decision_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate a worker assignment and (optionally) write an inert decision."""
    source_path_str = ""
    record_source: dict[str, Any]

    if assignment is not None:
        if not isinstance(assignment, dict):
            return _error_result("invalid_assignment", "assignment must be a dict", status="invalid")
        record_source = assignment
        source_path_str = _text(assignment.get("source_path"))
    elif _text(worker_assignment_path):
        wa_path = Path(_text(worker_assignment_path)).expanduser()
        if not wa_path.is_file():
            return _error_result(
                "worker_assignment_not_found",
                f"worker assignment not found: {wa_path}",
                status="not_found",
            )
        try:
            parsed = json.loads(wa_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            return _error_result(
                "worker_assignment_invalid",
                f"worker assignment is invalid: {exc}",
                status="invalid",
            )
        if not isinstance(parsed, dict):
            return _error_result(
                "worker_assignment_invalid",
                "worker assignment JSON must contain an object",
                status="invalid",
            )
        record_source = parsed
        source_path_str = str(wa_path.resolve())
    else:
        return _error_result(
            "invalid_source",
            "a worker assignment path or assignment dict is required",
        )

    repo_root = Path(
        _text(repo_path) or _text(record_source.get("repo_path")) or "."
    ).expanduser().resolve()

    created = _text(created_at) or _utc_now_iso()
    policy = evaluate_assignment_policy(
        record_source,
        source_type="worker_assignment",
        source_path=source_path_str,
    )
    record = _build_record(
        policy=policy,
        assignment=record_source,
        source_path=source_path_str,
        created_at=created,
        driver_decision_id=driver_decision_id,
    )
    markdown = render_driver_decision_markdown(record)

    try:
        paths = _decision_paths(repo_root, record["driver_decision_id"], output_root=output_root)
    except ValueError as exc:
        return _error_result("invalid_output_root", str(exc))

    if dry_run:
        return {
            "ok": True,
            "status": "dry_run",
            "dry_run": True,
            "json_path": str(paths["json"]),
            "md_path": str(paths["md"]),
            "record": record,
            "markdown": markdown,
        }

    if paths["json"].exists() or paths["md"].exists():
        return {
            "ok": False,
            "status": "already_exists",
            "dry_run": False,
            "json_path": str(paths["json"]),
            "md_path": str(paths["md"]),
            "record": record,
            "markdown": markdown,
            "error": {
                "code": "driver_decision_already_exists",
                "message": "driver decision already exists; no files were overwritten",
            },
        }

    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["json"].write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["md"].write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "status": "decision_created",
        "dry_run": False,
        "json_path": str(paths["json"]),
        "md_path": str(paths["md"]),
        "record": record,
        "markdown": markdown,
    }


def _build_record(
    *,
    policy: dict[str, Any],
    assignment: dict[str, Any],
    source_path: str,
    created_at: str,
    driver_decision_id: str | None,
) -> dict[str, Any]:
    title = _text(assignment.get("title")) or "Worker Assignment"
    final_id = _safe_segment(
        driver_decision_id or f"{_timestamp_segment(created_at)}-{title}",
        "driver-decision",
    )
    return {
        "driver_decision_id": final_id,
        "created_at": created_at,
        "source_type": "worker_assignment",
        "source_path": source_path,
        "assignment_id": _text(assignment.get("assignment_id")),
        "title": title,
        "mode": normalize_mode(assignment.get("mode")),
        "worker_role": _text(assignment.get("worker_role")),
        "recommended_vehicle": policy["recommended_vehicle"],
        "approval_required": policy["approval_required"],
        "blocked": policy["blocked"],
        "reasons": list(policy["reasons"]),
        "risk_flags": list(policy["risk_flags"]),
        "missing_requirements": list(policy["missing_requirements"]),
        # Inert flags — H.1 performs none of these.
        "model_call_performed": False,
        "provider_switch_performed": False,
        "worker_launch_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "promotion_performed": False,
    }


# ==========================================================================
# Rendering
# ==========================================================================


def render_driver_decision_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_driver_decision_text(result: dict[str, Any]) -> str:
    lines = [
        "Driver Decision",
        f"Status: {_text(result.get('status'))}",
    ]
    record = result.get("record") if isinstance(result.get("record"), dict) else {}
    if record:
        lines.extend(
            [
                f"Decision ID: {_text(record.get('driver_decision_id'))}",
                f"Recommended vehicle: {_text(record.get('recommended_vehicle'))}",
                f"Approval required: {record.get('approval_required')}",
                f"Blocked: {record.get('blocked')}",
            ]
        )
    if result.get("json_path"):
        lines.append(f"JSON path: {_text(result.get('json_path'))}")
    if result.get("md_path"):
        lines.append(f"Markdown path: {_text(result.get('md_path'))}")
    if result.get("dry_run"):
        lines.append("Dry run: True")
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    if error:
        lines.append(f"Code: {_text(error.get('code'))}")
        lines.append(f"Reason: {_text(error.get('message'))}")
    return "\n".join(lines) + "\n"


def render_driver_decision_markdown(record: dict[str, Any]) -> str:
    return (
        "# Driver Decision\n\n"
        f"Decision ID: `{_text(record.get('driver_decision_id'))}`\n\n"
        f"Created at: `{_text(record.get('created_at'))}`\n\n"
        "## Recommended Vehicle\n\n"
        f"`{_text(record.get('recommended_vehicle'))}`\n\n"
        "## Approval Required\n\n"
        f"- Approval required: `{str(bool(record.get('approval_required'))).lower()}`\n"
        f"- Blocked: `{str(bool(record.get('blocked'))).lower()}`\n\n"
        "## Risk Flags\n\n"
        f"{_bullet_list(_strings(record.get('risk_flags')))}\n\n"
        "## Missing Requirements\n\n"
        f"{_bullet_list(_strings(record.get('missing_requirements')))}\n\n"
        "## Reasons\n\n"
        f"{_bullet_list(_strings(record.get('reasons')))}\n\n"
        "## Execution Boundary\n\n"
        "This is a contract/report-only recommendation. The Driver does not drive yet.\n\n"
        f"{_bullet_list(list(_EXECUTION_BOUNDARY))}\n\n"
        "## Source Assignment\n\n"
        f"- Source type: `{_text(record.get('source_type'))}`\n"
        f"- Source path: `{_text(record.get('source_path'))}`\n"
        f"- Assignment id: `{_text(record.get('assignment_id'))}`\n"
        f"- Title: {_text(record.get('title')) or 'Untitled worker assignment'}\n"
        f"- Mode: `{_text(record.get('mode'))}`\n"
        f"- Worker role: `{_text(record.get('worker_role'))}`\n"
    )


# ==========================================================================
# Helpers
# ==========================================================================


def normalize_mode(mode: Any) -> str:
    key = _text(mode).lower().replace("-", "_").replace(" ", "_")
    if key in {"review", "reviewonly"}:
        key = "review_only"
    if key in {"dream", "dreamtrial"}:
        key = "dream_trial"
    if key in {"project", "projectevolution"}:
        key = "project_evolution"
    if key in {"docs", "documentation"}:
        key = "documentation"
    return MODE_LABELS.get(key, "Debug")


def _scan_text(
    title: str,
    expected_output: str,
    role: str,
    stop_conditions: list[str],
    safety_rules: list[str],
) -> str:
    parts = [title, expected_output, role]
    for line in [*stop_conditions, *safety_rules]:
        if _is_boilerplate(line):
            continue
        parts.append(line)
    return " \n ".join(part for part in parts if part).lower()


def _is_boilerplate(line: str) -> bool:
    lowered = _text(line).lower()
    return any(marker in lowered for marker in _BOILERPLATE_MARKERS)


def _mentions(text: str, tokens: set[str], phrases: set[str]) -> bool:
    if any(phrase in text for phrase in phrases):
        return True
    words = set(re.findall(r"[a-z0-9]+", text))
    return not words.isdisjoint(tokens)


def _expects_patch_like_output(mode: str, role: str, title: str, expected_output: str) -> bool:
    if mode not in ("Debug", "Project Evolution"):
        return False
    if role in {"implementer"}:
        return True
    # Scan ONLY task-specific text. The worker assignment's stop conditions and
    # safety rules carry boilerplate ("apply_allowed remains false", "patch
    # safety would block") whose "apply"/"patch" tokens would otherwise make
    # every task look patch-like and defeat the role/content discrimination.
    words = set(re.findall(r"[a-z0-9]+", f"{title}\n{expected_output}".lower()))
    return not words.isdisjoint(PATCH_LIKE_TOKENS)


def _could_modify_code(mode: str) -> bool:
    return mode in ("Debug", "Project Evolution")


def _is_external_queue(*values: str) -> bool:
    for value in values:
        lowered = _text(value).lower()
        if not lowered:
            continue
        if "external_queue" in lowered or "external queue" in lowered:
            return True
        if lowered in {"seed_draft", "external_queue", "external_queue_seed"}:
            return True
        if "seed_draft" in lowered:
            return True
    return False


def _max_vehicle(current: str, candidate: str) -> str:
    if VEHICLE_LEVELS.index(candidate) > VEHICLE_LEVELS.index(current):
        return candidate
    return current


def _decision_paths(repo_root: Path, decision_id: str, *, output_root: str | None) -> dict[str, Path]:
    root = _output_root(repo_root, output_root)
    directory = root / _safe_segment(decision_id, "driver-decision")
    return {
        "dir": directory,
        "json": directory / "driver_decision.json",
        "md": directory / "driver_decision.md",
    }


def _output_root(repo_root: Path, output_root: str | None) -> Path:
    base = (repo_root / ".agent" / DEFAULT_DRIVER_DECISIONS_DIRNAME).resolve()
    if _text(output_root):
        root = Path(_text(output_root)).expanduser()
        if not root.is_absolute():
            root = repo_root / root
        resolved = root.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"output_root must stay inside {base}: {resolved}") from exc
        return resolved
    return base


def _error_result(
    code: str,
    message: str,
    *,
    status: str = "error",
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "dry_run": False,
        "json_path": "",
        "md_path": "",
        "error": {"code": code, "message": message},
    }


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = re.split(r"[,\n]", value)
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    return [text for text in (_text(item) for item in items) if text]


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _add(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_segment(value: str, fallback: str) -> str:
    chars: list[str] = []
    last_dash = False
    for char in _text(value):
        if char.isalnum():
            chars.append(char.lower())
            last_dash = False
        elif char in {"-", "_"}:
            chars.append(char)
            last_dash = False
        elif chars and not last_dash:
            chars.append("-")
            last_dash = True
    segment = "".join(chars).strip("-_")
    return segment[:96] or fallback


def _timestamp_segment(created_at: str) -> str:
    return _safe_segment(created_at.replace(":", "-"), "decision")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
