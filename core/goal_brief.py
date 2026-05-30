"""Goal Brief Builder storage and interview logic.

The builder collects task evidence; it never executes commands or edits source
files. The schema is fixed and model output is treated as interview guidance,
not as evidence.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.json_utils import extract_json_block


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOAL_BRIEFS_ROOT = PROJECT_ROOT / ".agent" / "goal_briefs"

GOAL_BRIEF_SCHEMA: dict[str, Any] = {
    "goal": "",
    "problem_type": "",
    "status": "draft",
    "evidence": {
        "command_run": "",
        "expected_result": "",
        "actual_result": "",
        "error_output": "",
        "changed_files": [],
    },
    "constraints": {
        "allowed_files": [],
        "forbidden_files": [],
        "do_not_weaken": [],
    },
    "validation": {
        "command": "",
        "success_criteria": "",
    },
    "missing_information": [],
    "suggested_terminal_commands": [],
    "final_prompt": "",
    "created_at": "",
    "updated_at": "",
}

INTERVIEWER_PROMPT = (
    "You are Goal Brief Builder. Your job is to collect missing evidence for a "
    "software engineering task. Do not solve the task. Do not invent facts. "
    "Ask at most 2 focused questions at a time. When terminal evidence is "
    "needed, suggest a command for the user to run manually. Update the "
    "structured GoalBrief JSON."
)

Interviewer = Callable[[str, dict[str, Any]], dict[str, Any] | str | None]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _copy_schema() -> dict[str, Any]:
    return copy.deepcopy(GOAL_BRIEF_SCHEMA)


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe_text(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    else:
        raw_values = [values]

    out: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        text = _as_text(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _safe_rel_path(value: Any) -> str | None:
    text = _as_text(value).replace("\\", "/")
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
        return None
    parts = [part for part in text.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _safe_path_list(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in _dedupe_text(values):
        safe = _safe_rel_path(value)
        if safe and safe not in seen:
            seen.add(safe)
            out.append(safe)
    return out


def _normalize_problem_type(value: Any) -> str:
    text = _as_text(value).lower().replace(" ", "_").replace("-", "_")
    text = re.sub(r"[^a-z0-9_]", "", text)
    allowed = {
        "bug_fix",
        "debugging",
        "feature",
        "refactor",
        "code_review",
        "test_failure",
        "documentation",
        "research",
        "performance",
        "security",
    }
    return text if text in allowed else ""


def normalize_goal_brief(data: dict[str, Any] | None) -> dict[str, Any]:
    source = data if isinstance(data, dict) else {}
    brief = _copy_schema()

    brief["goal"] = _as_text(source.get("goal"))
    brief["problem_type"] = _normalize_problem_type(source.get("problem_type"))
    status = _as_text(source.get("status")) or "draft"
    brief["status"] = status if status in {"draft", "ready"} else "draft"
    brief["final_prompt"] = _as_text(source.get("final_prompt"))
    brief["created_at"] = _as_text(source.get("created_at"))
    brief["updated_at"] = _as_text(source.get("updated_at"))

    evidence = source.get("evidence") if isinstance(source.get("evidence"), dict) else {}
    brief["evidence"]["command_run"] = _as_text(evidence.get("command_run"))
    brief["evidence"]["expected_result"] = _as_text(evidence.get("expected_result"))
    brief["evidence"]["actual_result"] = _as_text(evidence.get("actual_result"))
    brief["evidence"]["error_output"] = _as_text(evidence.get("error_output"))
    brief["evidence"]["changed_files"] = _safe_path_list(evidence.get("changed_files"))

    constraints = source.get("constraints") if isinstance(source.get("constraints"), dict) else {}
    brief["constraints"]["allowed_files"] = _safe_path_list(constraints.get("allowed_files"))
    brief["constraints"]["forbidden_files"] = _safe_path_list(constraints.get("forbidden_files"))
    brief["constraints"]["do_not_weaken"] = _dedupe_text(constraints.get("do_not_weaken"))

    validation = source.get("validation") if isinstance(source.get("validation"), dict) else {}
    brief["validation"]["command"] = _as_text(validation.get("command"))
    brief["validation"]["success_criteria"] = _as_text(validation.get("success_criteria"))

    brief["missing_information"] = _dedupe_text(source.get("missing_information"))
    brief["suggested_terminal_commands"] = [
        command for command in _dedupe_text(source.get("suggested_terminal_commands"))
        if _is_safe_terminal_command(command)
    ]
    return brief


def _safe_command_tokens(command: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_.:/\\-]+", command.lower())


def _is_safe_terminal_command(command: str) -> bool:
    text = _as_text(command)
    if not text or len(text) > 220:
        return False
    if any(marker in text for marker in ("\n", "\r", ";", "&&", "||", "|", ">", "<", "$(")):
        return False
    lowered = f" {text.lower()} "
    blocked_phrases = (
        " rm ",
        " del ",
        " erase ",
        " remove-item ",
        " rmdir ",
        " git reset ",
        " git checkout ",
        " git clean ",
        " apply_patch ",
        " patch_plan ",
        " benchmark ",
        " memory promotion ",
        " lesson promotion ",
    )
    if any(phrase in lowered for phrase in blocked_phrases):
        return False
    tokens = _safe_command_tokens(text)
    blocked_tokens = {"curl", "wget", "scp", "ssh"}
    return not any(token in blocked_tokens for token in tokens)


def _compute_missing_information(brief: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    evidence = brief["evidence"]
    constraints = brief["constraints"]
    validation = brief["validation"]

    if not brief["problem_type"]:
        missing.append("problem_type")
    if not evidence["command_run"]:
        missing.append("evidence.command_run")
    if not evidence["expected_result"]:
        missing.append("evidence.expected_result")
    if not evidence["actual_result"] and not evidence["error_output"]:
        missing.append("evidence.actual_result_or_error_output")
    if not constraints["allowed_files"]:
        missing.append("constraints.allowed_files")
    if not validation["command"]:
        missing.append("validation.command")
    if not validation["success_criteria"]:
        missing.append("validation.success_criteria")
    return missing


def _has_enough_evidence(brief: dict[str, Any]) -> bool:
    evidence = brief["evidence"]
    validation = brief["validation"]
    return bool(
        brief["goal"]
        and brief["problem_type"]
        and evidence["command_run"]
        and evidence["expected_result"]
        and (evidence["actual_result"] or evidence["error_output"])
        and validation["command"]
        and validation["success_criteria"]
    )


def _default_suggested_commands(brief: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    evidence = brief["evidence"]
    if not evidence["command_run"]:
        commands.append("git status --short")
    if not evidence["changed_files"]:
        commands.append("git diff --name-only")
    return commands


def _default_questions(brief: dict[str, Any]) -> str:
    missing = _compute_missing_information(brief)
    questions: list[str] = []
    if "problem_type" in missing:
        questions.append("What kind of task is this: bug_fix, feature, refactor, code_review, or documentation?")
    if "evidence.command_run" in missing or "evidence.actual_result_or_error_output" in missing:
        questions.append("What command or manual check shows the current behavior, and what output did you see?")
    if "validation.success_criteria" in missing and len(questions) < 2:
        questions.append("What result should prove the task is complete?")
    if not questions:
        return "I have enough evidence to draft the final task prompt."
    return "\n".join(questions[:2])


def _build_interviewer_prompt(brief: dict[str, Any]) -> str:
    missing = _compute_missing_information(brief)
    return (
        f"{INTERVIEWER_PROMPT}\n\n"
        "Return JSON with these optional keys only: assistant_message, "
        "missing_information, suggested_terminal_commands, problem_type.\n"
        "Do not put command output in evidence unless it was supplied by the user.\n\n"
        f"Current missing fields:\n{json.dumps(missing, indent=2)}\n\n"
        f"Current GoalBrief JSON:\n{json.dumps(brief, indent=2, ensure_ascii=False)}"
    )


def _parse_interviewer_response(raw: dict[str, Any] | str | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = extract_json_block(raw)
        return parsed or {}
    return {}


def _run_interviewer(
    brief: dict[str, Any],
    interviewer: Interviewer | None,
) -> tuple[dict[str, Any], str]:
    prompt = _build_interviewer_prompt(brief)
    if interviewer is None:
        response: dict[str, Any] = {}
    else:
        response = _parse_interviewer_response(interviewer(prompt, copy.deepcopy(brief)))

    if not brief["problem_type"]:
        brief["problem_type"] = _normalize_problem_type(response.get("problem_type"))

    model_missing = _dedupe_text(response.get("missing_information"))
    computed_missing = _compute_missing_information(brief)
    brief["missing_information"] = _dedupe_text([*computed_missing, *model_missing])

    suggested = [
        command for command in _dedupe_text(response.get("suggested_terminal_commands"))
        if _is_safe_terminal_command(command)
    ]
    suggested.extend(_default_suggested_commands(brief))
    brief["suggested_terminal_commands"] = [
        command for command in _dedupe_text(suggested)
        if _is_safe_terminal_command(command)
    ]

    if _has_enough_evidence(brief):
        brief["final_prompt"] = build_final_prompt(brief)
        brief["status"] = "ready"
        assistant_message = _as_text(response.get("assistant_message")) or "Brief is ready. Review the final prompt before sending it to an agent."
    else:
        brief["final_prompt"] = ""
        brief["status"] = "draft"
        assistant_message = _as_text(response.get("assistant_message")) or _default_questions(brief)
    return brief, assistant_message


def _as_lines(items: list[str]) -> str:
    if not items:
        return "- None declared"
    return "\n".join(f"- {item}" for item in items)


def build_final_prompt(brief_data: dict[str, Any]) -> str:
    brief = normalize_goal_brief(brief_data)
    evidence = brief["evidence"]
    constraints = brief["constraints"]
    validation = brief["validation"]

    sections = [
        "# Task Brief",
        "",
        "## Goal",
        brief["goal"] or "Missing",
        "",
        "## Problem Type",
        brief["problem_type"] or "Missing",
        "",
        "## Evidence",
        f"- Command run: {evidence['command_run'] or 'Missing'}",
        f"- Expected result: {evidence['expected_result'] or 'Missing'}",
        f"- Actual result: {evidence['actual_result'] or 'Missing'}",
        f"- Error output: {evidence['error_output'] or 'None provided'}",
        "- Changed files:",
        _as_lines(evidence["changed_files"]),
        "",
        "## Constraints",
        "- Allowed files:",
        _as_lines(constraints["allowed_files"]),
        "- Forbidden files:",
        _as_lines(constraints["forbidden_files"]),
        "- Do not weaken:",
        _as_lines(constraints["do_not_weaken"]),
        "",
        "## Validation",
        f"- Command: {validation['command'] or 'Missing'}",
        f"- Success criteria: {validation['success_criteria'] or 'Missing'}",
        "",
        "## Instructions",
        "Use only the evidence above. Do not invent command output. Respect the file constraints. "
        "Before acting, restate the validation command and success criteria.",
    ]
    return "\n".join(sections).strip() + "\n"


def render_goal_brief_markdown(brief_data: dict[str, Any]) -> str:
    brief = normalize_goal_brief(brief_data)
    evidence = brief["evidence"]
    constraints = brief["constraints"]
    validation = brief["validation"]
    return (
        "# Goal Brief\n\n"
        f"Status: {brief['status']}\n\n"
        "## Goal\n\n"
        f"{brief['goal'] or 'Missing'}\n\n"
        "## Problem Type\n\n"
        f"{brief['problem_type'] or 'Missing'}\n\n"
        "## Evidence\n\n"
        f"- Command run: {evidence['command_run'] or 'Missing'}\n"
        f"- Expected result: {evidence['expected_result'] or 'Missing'}\n"
        f"- Actual result: {evidence['actual_result'] or 'Missing'}\n"
        f"- Error output: {evidence['error_output'] or 'None provided'}\n"
        "- Changed files:\n"
        f"{_as_lines(evidence['changed_files'])}\n\n"
        "## Constraints\n\n"
        "Allowed files:\n"
        f"{_as_lines(constraints['allowed_files'])}\n\n"
        "Forbidden files:\n"
        f"{_as_lines(constraints['forbidden_files'])}\n\n"
        "Do not weaken:\n"
        f"{_as_lines(constraints['do_not_weaken'])}\n\n"
        "## Validation\n\n"
        f"- Command: {validation['command'] or 'Missing'}\n"
        f"- Success criteria: {validation['success_criteria'] or 'Missing'}\n\n"
        "## Missing Information\n\n"
        f"{_as_lines(brief['missing_information'])}\n\n"
        "## Suggested Terminal Commands\n\n"
        f"{_as_lines(brief['suggested_terminal_commands'])}\n\n"
        "## Final Prompt\n\n"
        "```text\n"
        f"{brief['final_prompt'].strip()}\n"
        "```\n"
    )


def _allocate_brief_dir(root: Path) -> Path:
    base = root / _timestamp()
    candidate = base
    suffix = 1
    while candidate.exists():
        candidate = root / f"{base.name}_{suffix:02d}"
        suffix += 1
    return candidate


def _write_outputs(
    brief: dict[str, Any],
    brief_dir: Path,
    *,
    export_md: bool = False,
    dry_run: bool = False,
) -> tuple[Path, Path | None]:
    json_path = brief_dir / "goal_brief.json"
    md_path = brief_dir / "goal_brief.md" if export_md else None
    if not dry_run:
        brief_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(brief, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if md_path:
            md_path.write_text(render_goal_brief_markdown(brief), encoding="utf-8")
    return json_path, md_path


def build_goal_brief_summary(brief_data: dict[str, Any]) -> dict[str, Any]:
    """Return a friendly read-only summary for UI display.

    This is intentionally separate from ``GOAL_BRIEF_SCHEMA``. It is returned
    to callers, but never written into ``goal_brief.json``.
    """
    brief = normalize_goal_brief(brief_data)
    evidence = brief["evidence"]
    constraints = brief["constraints"]
    validation = brief["validation"]
    missing = _compute_missing_information(brief)

    observed = evidence["actual_result"] or evidence["error_output"]
    validation_text = " / ".join(
        part for part in (validation["command"], validation["success_criteria"]) if part
    )
    constraints_text = ", ".join(constraints["allowed_files"])
    if constraints["forbidden_files"]:
        constraints_text = _append_text(
            constraints_text,
            "Forbidden: " + ", ".join(constraints["forbidden_files"]),
        )

    rows = [
        _summary_row("Goal", brief["goal"]),
        _summary_row("Type", brief["problem_type"]),
        _summary_row("Observed Behavior", observed),
        _summary_row("Validation", validation_text),
        _summary_row("Constraints", constraints_text),
        _summary_row("Missing", ", ".join(missing) if missing else "None"),
    ]

    return {
        "status": brief["status"],
        "ready": brief["status"] == "ready",
        "missing_count": len(missing),
        "rows": rows,
    }


def _summary_row(label: str, value: str) -> dict[str, str]:
    text = _as_text(value)
    return {
        "label": label,
        "value": text or "Missing",
        "state": "complete" if text and text != "Missing" else "missing",
    }


def _result(
    brief: dict[str, Any],
    brief_dir: Path,
    assistant_message: str,
    *,
    export_md: bool,
    dry_run: bool,
) -> dict[str, Any]:
    json_path = brief_dir / "goal_brief.json"
    md_path = brief_dir / "goal_brief.md" if export_md else None
    return {
        "ok": True,
        "brief": brief,
        "brief_dir": str(brief_dir),
        "brief_path": str(json_path),
        "markdown_path": str(md_path) if md_path else "",
        "summary": build_goal_brief_summary(brief),
        "assistant_message": assistant_message,
        "dry_run": bool(dry_run),
    }


def create_goal_brief(
    *,
    goal: str,
    repo_path: str | None = None,
    goal_briefs_root: Path | None = None,
    interviewer: Interviewer | None = None,
    export_md: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    del repo_path
    goal_clean = _as_text(goal)
    if not goal_clean:
        raise ValueError("goal must be a non-empty string")

    now = _now_iso()
    brief = _copy_schema()
    brief["goal"] = goal_clean
    brief["created_at"] = now
    brief["updated_at"] = now
    brief, assistant_message = _run_interviewer(brief, interviewer)

    root = Path(goal_briefs_root or DEFAULT_GOAL_BRIEFS_ROOT)
    brief_dir = _allocate_brief_dir(root)
    _write_outputs(brief, brief_dir, export_md=export_md, dry_run=dry_run)
    return _result(
        brief,
        brief_dir,
        assistant_message,
        export_md=export_md,
        dry_run=dry_run,
    )


def resolve_goal_brief_ref(
    brief_ref: str | Path,
    *,
    goal_briefs_root: Path | None = None,
) -> Path:
    raw = _as_text(brief_ref)
    if not raw:
        raise ValueError("brief_ref must be a non-empty path")

    root = Path(goal_briefs_root or DEFAULT_GOAL_BRIEFS_ROOT).resolve()
    path = Path(raw).expanduser()
    candidate = path.resolve() if path.is_absolute() else (root / path).resolve()
    if candidate.is_dir():
        candidate = (candidate / "goal_brief.json").resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"brief_ref must live inside {root}: {candidate}") from exc

    if candidate.name != "goal_brief.json":
        raise ValueError("brief_ref must point to a goal_brief.json file or a brief directory")
    if not candidate.is_file():
        raise FileNotFoundError(f"goal brief not found: {candidate}")
    return candidate


def read_goal_brief(
    brief_ref: str | Path,
    *,
    goal_briefs_root: Path | None = None,
) -> dict[str, Any]:
    path = resolve_goal_brief_ref(brief_ref, goal_briefs_root=goal_briefs_root)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("goal_brief.json must contain a JSON object")
    return normalize_goal_brief(data)


def _parse_json_answer(answer: str) -> dict[str, Any] | None:
    text = _as_text(answer)
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = extract_json_block(text)
    return parsed if isinstance(parsed, dict) else None


def _append_text(existing: str, addition: str) -> str:
    addition = _as_text(addition)
    if not addition:
        return existing
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing}\n\n{addition}"


def _apply_json_answer(brief: dict[str, Any], payload: dict[str, Any]) -> None:
    problem_type = _normalize_problem_type(payload.get("problem_type"))
    if problem_type:
        brief["problem_type"] = problem_type

    evidence_payload = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else payload
    evidence = brief["evidence"]
    for key in ("command_run", "expected_result", "actual_result", "error_output"):
        if key in evidence_payload:
            evidence[key] = _as_text(evidence_payload.get(key))
    if "changed_files" in evidence_payload:
        evidence["changed_files"] = _safe_path_list(evidence_payload.get("changed_files"))

    constraints_payload = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
    constraints = brief["constraints"]
    if "allowed_files" in constraints_payload:
        constraints["allowed_files"] = _safe_path_list(constraints_payload.get("allowed_files"))
    if "forbidden_files" in constraints_payload:
        constraints["forbidden_files"] = _safe_path_list(constraints_payload.get("forbidden_files"))
    if "do_not_weaken" in constraints_payload:
        constraints["do_not_weaken"] = _dedupe_text(constraints_payload.get("do_not_weaken"))

    validation_payload = payload.get("validation") if isinstance(payload.get("validation"), dict) else payload
    validation = brief["validation"]
    if "command" in validation_payload:
        validation["command"] = _as_text(validation_payload.get("command"))
    if "validation_command" in validation_payload:
        validation["command"] = _as_text(validation_payload.get("validation_command"))
    if "success_criteria" in validation_payload:
        validation["success_criteria"] = _as_text(validation_payload.get("success_criteria"))


def _extract_label(text: str, *labels: str) -> str:
    label_group = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?im)^\s*(?:{label_group})\s*:\s*(.+?)\s*$", text)
    return _as_text(match.group(1)) if match else ""


def _apply_text_answer(brief: dict[str, Any], answer: str) -> None:
    text = _as_text(answer)
    if not text:
        return

    problem_type = _extract_label(text, "problem_type", "problem type", "type")
    command = _extract_label(text, "command", "command_run", "command run")
    expected = _extract_label(text, "expected", "expected_result", "expected result")
    actual = _extract_label(text, "actual", "actual_result", "actual result")
    error = _extract_label(text, "error", "error_output", "stderr")
    changed = _extract_label(text, "changed_files", "changed files", "files")
    allowed = _extract_label(text, "allowed_files", "allowed files")
    forbidden = _extract_label(text, "forbidden_files", "forbidden files")
    do_not_weaken = _extract_label(text, "do_not_weaken", "do not weaken")
    validation_command = _extract_label(text, "validation_command", "validation command")
    success_criteria = _extract_label(text, "success_criteria", "success criteria")

    if problem_type:
        brief["problem_type"] = _normalize_problem_type(problem_type)
    evidence = brief["evidence"]
    if command:
        evidence["command_run"] = command
    if expected:
        evidence["expected_result"] = expected
    if actual:
        evidence["actual_result"] = actual
    if error:
        evidence["error_output"] = error
    if changed:
        evidence["changed_files"] = _safe_path_list(re.split(r"[, ]+", changed))

    constraints = brief["constraints"]
    if allowed:
        constraints["allowed_files"] = _safe_path_list(re.split(r"[, ]+", allowed))
    if forbidden:
        constraints["forbidden_files"] = (
            []
            if forbidden.lower() in {"none", "no", "n/a"}
            else _safe_path_list(re.split(r"[, ]+", forbidden))
        )
    if do_not_weaken:
        constraints["do_not_weaken"] = _dedupe_text(do_not_weaken)

    validation = brief["validation"]
    if validation_command:
        validation["command"] = validation_command
    if success_criteria:
        validation["success_criteria"] = success_criteria

    if not any((
        problem_type,
        command,
        expected,
        actual,
        error,
        changed,
        allowed,
        forbidden,
        do_not_weaken,
        validation_command,
        success_criteria,
    )):
        if re.search(r"(?i)\b(error|failed|traceback|exception)\b", text):
            evidence["error_output"] = _append_text(evidence["error_output"], text)
        else:
            evidence["actual_result"] = _append_text(evidence["actual_result"], text)


def apply_answer_to_goal_brief(brief_data: dict[str, Any], answer: str) -> dict[str, Any]:
    brief = normalize_goal_brief(brief_data)
    payload = _parse_json_answer(answer)
    if payload is not None:
        _apply_json_answer(brief, payload)
    else:
        _apply_text_answer(brief, answer)
    return brief


def update_goal_brief(
    brief_ref: str | Path,
    *,
    answer: str = "",
    repo_path: str | None = None,
    goal_briefs_root: Path | None = None,
    interviewer: Interviewer | None = None,
    export_md: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    del repo_path
    path = resolve_goal_brief_ref(brief_ref, goal_briefs_root=goal_briefs_root)
    brief = read_goal_brief(path, goal_briefs_root=goal_briefs_root)
    brief = apply_answer_to_goal_brief(brief, answer)
    brief["updated_at"] = _now_iso()
    brief, assistant_message = _run_interviewer(brief, interviewer)

    brief_dir = path.parent
    _write_outputs(brief, brief_dir, export_md=export_md, dry_run=dry_run)
    return _result(
        brief,
        brief_dir,
        assistant_message,
        export_md=export_md,
        dry_run=dry_run,
    )
