"""Draft-only Worker Assignment / Route Card generator.

This module converts existing operator artifacts into copy-pasteable worker
assignments. It only reads source artifacts and writes inert draft artifacts
under ``.agent/worker_assignments``. It does not launch workers, call models,
apply patches, execute validation, start Dream, run Project Evolution, call
webhooks, or promote lessons.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKER_ASSIGNMENTS_DIRNAME = "worker_assignments"

SourceType = Literal["goal_brief", "handoff", "seed_draft", "review_pack"]

MODE_LABELS: dict[str, str] = {
    "debug": "Debug",
    "project_evolution": "Project Evolution",
    "dream_trial": "Dream Trial",
    "documentation": "Documentation",
    "review_only": "Review-only",
}

ROLE_LABELS = {"implementer", "reviewer", "skeptic", "documenter", "researcher"}

DEFAULT_FORBIDDEN_FILES = [
    ".env",
    ".agent",
    ".git",
    "node_modules",
    "target",
]

BASE_STOP_CONDITIONS = [
    "Stop if required files are missing.",
    "Stop if the task requires files outside allowed scope.",
    "Stop if a validation command is unavailable or cannot be run in the worker environment.",
    "Stop if secrets/env/protected files are needed.",
    "Stop if patch safety would block the change.",
    "Stop if visual evidence is required but unavailable.",
    "Stop before applying real repo changes unless explicitly approved by the human.",
]

BASE_SAFETY_RULES = [
    "Draft-only Worker Assignment / Route Card.",
    "Copy Markdown to the worker manually; do not launch a worker from this artifact.",
    "Do not call models or external agents from assignment creation.",
    "Do not apply patches, commit, push, run validation, run benchmarks, start Dream, run Project Evolution execution, call webhooks, or promote lessons.",
    "Human approval is required before any worker action or repo mutation.",
    "apply_allowed remains false unless a human creates a separate explicit approval.",
]

EXPECTED_SUMMARY_FORMAT = [
    "Files inspected",
    "Findings or changes proposed",
    "Allowed files touched or proposed",
    "Validation evidence or reason validation was not run",
    "Risks, blockers, and stop-condition hits",
    "Next human approval needed",
]

_HANDOFF_META_RE = re.compile(
    r"<!--HANDOFF_META\s*(?P<json>\{.*?\})\s*HANDOFF_META-->",
    re.DOTALL,
)


def create_worker_assignment(
    *,
    repo_path: str,
    goal_brief_path: str | None = None,
    handoff_path: str | None = None,
    seed_draft_path: str | None = None,
    review_pack_path: str | None = None,
    mode: str | None = "debug",
    worker_role: str | None = "implementer",
    allowed_files: Any = None,
    forbidden_files: Any = None,
    validation_commands: Any = None,
    dry_run: bool = False,
    output_root: str | None = None,
    created_at: str | None = None,
    assignment_id: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path or ".").expanduser().resolve()
    selected = _selected_source(
        goal_brief_path=goal_brief_path,
        handoff_path=handoff_path,
        seed_draft_path=seed_draft_path,
        review_pack_path=review_pack_path,
    )
    if not selected:
        return _error_result("invalid_source", "exactly one source artifact path is required")

    source_type, raw_source_path = selected
    source_path = _resolve_source_path(source_type, raw_source_path)
    if not source_path.is_file():
        return _error_result(
            "source_not_found",
            f"source artifact not found: {source_path}",
            status="not_found",
            source_type=source_type,
        )

    try:
        source = _read_source(source_type, source_path)
    except (json.JSONDecodeError, ValueError) as exc:
        return _error_result(
            "source_invalid",
            f"source artifact is invalid: {exc}",
            status="invalid",
            source_type=source_type,
        )

    created = _text(created_at) or _utc_now_iso()
    mode_label = _normalize_mode(mode or _source_mode_hint(source))
    role = _normalize_role(worker_role)
    record = _build_record(
        source=source,
        source_type=source_type,
        source_path=source_path,
        repo_root=repo_root,
        created_at=created,
        assignment_id=assignment_id,
        mode_label=mode_label,
        worker_role=role,
        extra_allowed=allowed_files,
        extra_forbidden=forbidden_files,
        extra_validation=validation_commands,
    )
    markdown = render_worker_assignment_markdown(record)
    try:
        paths = _assignment_paths(repo_root, record["assignment_id"], output_root=output_root)
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
                "code": "assignment_already_exists",
                "message": "worker assignment already exists; no files were overwritten",
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
        "status": "draft_created",
        "dry_run": False,
        "json_path": str(paths["json"]),
        "md_path": str(paths["md"]),
        "record": record,
        "markdown": markdown,
    }


def render_worker_assignment_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_worker_assignment_text(result: dict[str, Any]) -> str:
    lines = [
        "Worker Assignment Draft",
        f"Status: {_text(result.get('status'))}",
    ]
    record = result.get("record") if isinstance(result.get("record"), dict) else {}
    if record:
        lines.extend(
            [
                f"Assignment ID: {_text(record.get('assignment_id'))}",
                f"Title: {_text(record.get('title'))}",
                f"Mode: {_text(record.get('mode'))}",
                f"Worker role: {_text(record.get('worker_role'))}",
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


def render_worker_assignment_markdown(record: dict[str, Any]) -> str:
    """Render a compact, copy-pasteable route card.

    The Markdown is intentionally shorter than the JSON record: it states the
    no-apply / no-launch / no-real-repo-mutation rule once (in Task Rules)
    instead of repeating the same safety statement across Context, Constraints,
    Stop Conditions, Safety Rules, and a Final Summary. The full safety arrays
    (stop_conditions, safety_rules, inert flags) still live in the JSON record.
    """
    objective = _text(record.get("title")) or "Untitled worker assignment"
    return (
        "# Worker Assignment\n\n"
        "## Objective\n\n"
        f"{objective}\n\n"
        "## Source\n\n"
        f"- Source type: `{_text(record.get('source_type'))}`\n"
        f"- Source path: `{_text(record.get('source_path'))}`\n"
        f"- Repo path: `{_text(record.get('repo_path'))}`\n"
        f"- Mode: `{_text(record.get('mode'))}`\n"
        f"- Worker role: `{_text(record.get('worker_role'))}`\n\n"
        "## Scope\n\n"
        "Allowed files:\n\n"
        f"{_bullet_list(_strings(record.get('allowed_files')))}\n\n"
        "Forbidden:\n\n"
        f"{_bullet_list(_strings(record.get('forbidden_files')))}\n\n"
        "## Task Rules\n\n"
        "- Inspect only the allowed scope.\n"
        "- Propose changes only unless explicit human approval says otherwise.\n"
        "- Do not edit, apply, commit, push, launch workers, call tools, or mutate the real repo from this route card.\n"
        "- Stop if the task needs files outside scope, secrets/protected files, unavailable validation, or missing visual evidence.\n\n"
        "## Validation\n\n"
        f"{_validation_block(_strings(record.get('validation_commands')))}\n\n"
        "## Expected Output\n\n"
        "Return:\n\n"
        "- files inspected\n"
        "- findings\n"
        "- proposed change\n"
        "- validation evidence or recommendation\n"
        "- blockers / risks\n"
        "- next human approval needed\n"
    )


def _validation_block(commands: list[str]) -> str:
    if not commands:
        return "None declared. Recommend validation before trusting the result."
    return _bullet_list(commands)


def _selected_source(
    *,
    goal_brief_path: str | None,
    handoff_path: str | None,
    seed_draft_path: str | None,
    review_pack_path: str | None,
) -> tuple[SourceType, str] | None:
    candidates: list[tuple[SourceType, str]] = []
    if _text(goal_brief_path):
        candidates.append(("goal_brief", _text(goal_brief_path)))
    if _text(handoff_path):
        candidates.append(("handoff", _text(handoff_path)))
    if _text(seed_draft_path):
        candidates.append(("seed_draft", _text(seed_draft_path)))
    if _text(review_pack_path):
        candidates.append(("review_pack", _text(review_pack_path)))
    if len(candidates) != 1:
        return None
    return candidates[0]


def _resolve_source_path(source_type: SourceType, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if source_type == "goal_brief" and path.is_dir():
        path = path / "goal_brief.json"
    return path.resolve()


def _read_source(source_type: SourceType, path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if source_type == "handoff" and path.suffix.lower() == ".md":
        match = _HANDOFF_META_RE.search(text)
        if not match:
            raise ValueError("handoff markdown is missing HANDOFF_META")
        meta = json.loads(match.group("json"))
        if not isinstance(meta, dict):
            raise ValueError("handoff HANDOFF_META must be a JSON object")
        return {"meta": meta, "body": text[match.end():].strip()}

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("source JSON must contain an object")
    return parsed


def _build_record(
    *,
    source: dict[str, Any],
    source_type: SourceType,
    source_path: Path,
    repo_root: Path,
    created_at: str,
    assignment_id: str | None,
    mode_label: str,
    worker_role: str,
    extra_allowed: Any,
    extra_forbidden: Any,
    extra_validation: Any,
) -> dict[str, Any]:
    title = _title_from_source(source_type, source)
    allowed = _dedupe([
        *_source_allowed_files(source_type, source),
        *_safe_paths(extra_allowed),
    ])
    forbidden = _merge_forbidden(
        [
            *_source_forbidden_files(source_type, source),
            *_safe_paths(extra_forbidden),
        ],
        allowed,
    )
    validation = _dedupe([
        *_source_validation_commands(source_type, source),
        *_as_list(extra_validation),
    ])
    stop_conditions = _stop_conditions(mode_label, validation)
    safety_rules = _safety_rules(mode_label)
    expected_output = _expected_output(mode_label, source_type, source)
    final_id = _safe_segment(assignment_id or f"{_timestamp_segment(created_at)}-{title}", "worker-assignment")
    return {
        "assignment_id": final_id,
        "created_at": created_at,
        "source_type": source_type,
        "source_path": str(source_path.resolve()),
        "title": title,
        "mode": mode_label,
        "worker_role": worker_role,
        "repo_path": str(repo_root),
        "allowed_files": allowed,
        "forbidden_files": forbidden,
        "validation_commands": validation,
        "stop_conditions": stop_conditions,
        "safety_rules": safety_rules,
        "expected_output": expected_output,
        "expected_summary_format": list(EXPECTED_SUMMARY_FORMAT),
        "human_approval_required": True,
        "apply_allowed": False,
        "worker_launch_allowed": False,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "promotion_performed": False,
    }


def _title_from_source(source_type: SourceType, source: dict[str, Any]) -> str:
    if source_type == "handoff" and isinstance(source.get("meta"), dict):
        meta = source["meta"]
        return _first_text(meta.get("title"), "Worker Assignment")
    if source_type == "seed_draft":
        return _first_text(
            source.get("title"),
            source.get("suggested_goal"),
            source.get("evolution_goal"),
            source.get("dream_seed_title"),
            source.get("summary"),
            "External Queue Worker Assignment",
        )
    return _first_text(
        source.get("title"),
        source.get("goal"),
        source.get("problem_statement"),
        source.get("task_summary"),
        "Worker Assignment",
    )


def _source_allowed_files(source_type: SourceType, source: dict[str, Any]) -> list[str]:
    if source_type == "handoff" and isinstance(source.get("meta"), dict):
        return _safe_paths(source["meta"].get("allowed_files"))
    if source_type == "review_pack":
        return _safe_paths(source.get("allowed_files"))
    if source_type == "seed_draft":
        return _safe_paths(source.get("suggested_read_first_files"))
    constraints = source.get("constraints") if isinstance(source.get("constraints"), dict) else {}
    evidence = source.get("evidence") if isinstance(source.get("evidence"), dict) else {}
    return _dedupe([
        *_safe_paths(constraints.get("allowed_files")),
        *_safe_paths(source.get("suspected_files_or_areas")),
        *_safe_paths(evidence.get("changed_files")),
    ])


def _source_forbidden_files(source_type: SourceType, source: dict[str, Any]) -> list[str]:
    if source_type == "handoff" and isinstance(source.get("meta"), dict):
        return _safe_paths(source["meta"].get("forbidden_files"))
    if source_type == "review_pack":
        return _safe_paths(source.get("forbidden_files"))
    constraints = source.get("constraints") if isinstance(source.get("constraints"), dict) else {}
    return _safe_paths(constraints.get("forbidden_files"))


def _source_validation_commands(source_type: SourceType, source: dict[str, Any]) -> list[str]:
    if source_type == "handoff" and isinstance(source.get("meta"), dict):
        return _as_list(source["meta"].get("validation_command"))
    if source_type == "review_pack":
        return _as_list(source.get("validation_hints"))
    if source_type == "seed_draft":
        return _as_list(source.get("suggested_validation"))
    validation = source.get("validation") if isinstance(source.get("validation"), dict) else {}
    return _as_list(validation.get("command"))


def _source_mode_hint(source: dict[str, Any]) -> str:
    return _first_text(
        source.get("recommended_mode"),
        source.get("suggested_mode"),
        source.get("likely_mode"),
        "debug",
    )


def _expected_output(mode_label: str, source_type: SourceType, source: dict[str, Any]) -> str:
    if mode_label == "Review-only":
        return "Critique/report only. No patch generation, no file edits, and no validation execution."
    if mode_label == "Project Evolution":
        return "A draft plan/review report with phases, risks, allowed-scope notes, and approval questions."
    if mode_label == "Dream Trial":
        return "A draft trial/research report only. No real repo apply and no Dream execution."
    if mode_label == "Documentation":
        return "Documentation-oriented draft output with proposed text, evidence, and unresolved questions."
    if source_type == "review_pack":
        explicit = _text(source.get("expected_deliverable"))
        if explicit:
            return explicit
    if source_type == "seed_draft":
        explicit = _text(source.get("proposed_next_human_action"))
        if explicit:
            return explicit
    validation = source.get("validation") if isinstance(source.get("validation"), dict) else {}
    return _text(validation.get("success_criteria")) or "A concise worker report with findings, proposed changes, validation evidence, and blockers."


def _stop_conditions(mode_label: str, validation_commands: list[str]) -> list[str]:
    conditions = list(BASE_STOP_CONDITIONS)
    if mode_label == "Debug":
        conditions.append("Stop if the debug fix cannot remain minimal.")
        if validation_commands:
            conditions.append("Stop if the provided validation command is unavailable.")
    if mode_label == "Project Evolution":
        conditions.append("Stop until a human accepts the plan/review gate for any broad migration.")
    if mode_label == "Dream Trial":
        conditions.append("Stop if the work would require real repo apply instead of a later approved sandbox/temp clone.")
    if mode_label == "Review-only":
        conditions.append("Stop if patch generation or code edits are requested.")
    return _dedupe(conditions)


def _safety_rules(mode_label: str) -> list[str]:
    rules = list(BASE_SAFETY_RULES)
    if mode_label == "Debug":
        rules.extend(
            [
                "Debug mode: keep allowed_files narrow and patch intent minimal.",
                "Debug mode: validation is required when validation_commands are provided.",
            ]
        )
    elif mode_label == "Project Evolution":
        rules.extend(
            [
                "Project Evolution mode: require a plan/review gate before any implementation.",
                "Project Evolution mode: broad migration must stay draft/review-only unless approved.",
            ]
        )
    elif mode_label == "Dream Trial":
        rules.extend(
            [
                "Dream Trial mode: no real repo apply.",
                "Dream Trial mode: sandbox/temp clone only if later approved.",
            ]
        )
    elif mode_label == "Review-only":
        rules.append("Review-only mode: no patch generation and no code edits.")
    elif mode_label == "Documentation":
        rules.append("Documentation mode: propose documentation text only unless separately approved.")
    return _dedupe(rules)


def _normalize_mode(mode: str | None) -> str:
    key = _text(mode).lower().replace("-", "_").replace(" ", "_")
    if key in {"review", "reviewonly"}:
        key = "review_only"
    if key in {"dream", "dreamtrial"}:
        key = "dream_trial"
    if key in {"project", "projectevolution"}:
        key = "project_evolution"
    return MODE_LABELS.get(key, "Debug")


def _normalize_role(role: str | None) -> str:
    value = _text(role).lower().replace("-", "_").replace(" ", "_")
    return value if value in ROLE_LABELS else "implementer"


def _assignment_paths(repo_root: Path, assignment_id: str, *, output_root: str | None) -> dict[str, Path]:
    root = _output_root(repo_root, output_root)
    directory = root / _safe_segment(assignment_id, "worker-assignment")
    return {
        "dir": directory,
        "json": directory / "worker_assignment.json",
        "md": directory / "worker_assignment.md",
    }


def _output_root(repo_root: Path, output_root: str | None) -> Path:
    base = (repo_root / ".agent" / DEFAULT_WORKER_ASSIGNMENTS_DIRNAME).resolve()
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
    source_type: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "status": status,
        "dry_run": False,
        "json_path": "",
        "md_path": "",
        "error": {"code": code, "message": message},
    }
    if source_type:
        result["source_type"] = source_type
    return result


def _merge_forbidden(values: list[str], allowed_files: list[str]) -> list[str]:
    merged = _dedupe([*values, *DEFAULT_FORBIDDEN_FILES])
    final: list[str] = []
    for item in merged:
        if any(path == item or path.startswith(item + "/") for path in allowed_files):
            continue
        final.append(item)
    return final


def _safe_paths(value: Any) -> list[str]:
    paths: list[str] = []
    for item in _as_list(value):
        safe = _safe_rel_path(item)
        if safe and safe not in paths:
            paths.append(safe)
    return paths


def _safe_rel_path(value: Any) -> str | None:
    text = _text(value).replace("\\", "/")
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
        return None
    parts = [part for part in text.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = re.split(r"[,\n]", value)
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]
    return _dedupe([_text(item) for item in raw])


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None declared"
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


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text[:160]
    return ""


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
    return _safe_segment(created_at.replace(":", "-"), "assignment")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
