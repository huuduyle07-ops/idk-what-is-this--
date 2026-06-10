from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODE = "project_evolution_review_gate"
SCHEMA_VERSION = "evolution_review_gate_v1"
EXECUTABLE_DRAFT_SCHEMA_VERSION = "evolution_executable_patch_draft_v1"
REVIEW_GATES_DIRNAME = "review_gates"

_PROTECTED_CATEGORIES: frozenset[str] = frozenset({"config", "dependency"})
_PROTECTED_FILE_NAMES: frozenset[str] = frozenset({
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "pipfile.lock",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
    ".env.sample",
    ".env.template",
    "config.py",
    "settings.py",
    "config.json",
    "config.yaml",
    "config.yml",
})
_HIGH_RISK_FILE_COUNT = 5
_MULTI_FILE_THRESHOLD = 2


def build_project_evolution_review_gate(
    repo_path: str,
    executable_patch_draft_path: str,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    draft_resolved = _resolve_draft_path(repo_root, executable_patch_draft_path)
    if draft_resolved is None:
        return _build_error_record(
            source_draft_path=str(_raw_path(repo_root, executable_patch_draft_path)),
            message="executable patch draft must live inside .agent/project_evolution/executable_patch_drafts/",
            code="draft_path_outside_executable_patch_drafts",
        )

    draft_load = _load_json_record(draft_resolved, EXECUTABLE_DRAFT_SCHEMA_VERSION, "executable patch draft")
    if draft_load["status"] != "ok":
        return _build_error_record(
            source_draft_path=str(draft_resolved),
            message=draft_load["message"],
            code=draft_load["code"],
        )

    draft = draft_load["record"]
    return _build_review_gate(draft, str(draft_resolved))


def _build_review_gate(draft: dict[str, Any], source_draft_path: str) -> dict[str, Any]:
    draft_id = Path(source_draft_path).stem
    affected_files = _extract_affected_files(draft)
    edit_units = draft.get("executable_edit_units", [])
    if not isinstance(edit_units, list):
        edit_units = []
    tests_required = _normalize_string_list(draft.get("tests_required_later", []))
    rollback_notes = _normalize_string_list(draft.get("rollback_notes", []))

    has_tests = bool(tests_required)
    has_rollback = bool(rollback_notes)

    risk_level, risk_reasons = _classify_risk(
        affected_files=affected_files,
        edit_units=edit_units,
        has_tests=has_tests,
        has_rollback=has_rollback,
    )

    missing_evidence = _build_missing_evidence(draft, edit_units, has_tests, has_rollback)
    docs_required = _build_docs_required(affected_files)

    return {
        "generated_at": _utc_now_iso(),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "draft_id": draft_id,
        "source_draft_path": source_draft_path,
        "apply_allowed": False,
        "human_approval_required": True,
        "approval_status": "pending",
        "affected_files": affected_files,
        "planned_edit_count": len(edit_units),
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "missing_evidence": missing_evidence,
        "rollback_notes_required": True,
        "tests_required": tests_required,
        "docs_required": docs_required,
        "reviewer_checklist": _build_reviewer_checklist(affected_files, edit_units, risk_level),
        "final_decision": {
            "options": ["APPROVE_MANUAL_REVIEW_ONLY", "REQUEST_CHANGES", "REJECT"],
            "selected": None,
            "note": (
                "Human reviewer must select one of the options above. "
                "APPROVE_MANUAL_REVIEW_ONLY does not permit automated apply. "
                "No apply step may proceed until this field is set by a human."
            ),
        },
    }


def _classify_risk(
    *,
    affected_files: list[dict[str, Any]],
    edit_units: list[dict[str, Any]],
    has_tests: bool,
    has_rollback: bool,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    file_count = len(affected_files)
    protected = [f for f in affected_files if _is_protected_file(f)]
    deletion_units = [u for u in edit_units if isinstance(u, dict) and _is_deletion_like(u)]

    if file_count >= _HIGH_RISK_FILE_COUNT:
        reasons.append(f"large number of affected files ({file_count})")
    if protected:
        paths = ", ".join(p["path"] for p in protected)
        reasons.append(f"touches protected/config/env/docker/dependency files: {paths}")
    if deletion_units:
        reasons.append(f"deletion-like edit operations present ({len(deletion_units)} unit(s))")

    if reasons:
        return "high", reasons

    med_reasons: list[str] = []
    if file_count >= _MULTI_FILE_THRESHOLD:
        med_reasons.append(f"multiple files affected ({file_count})")
    if not has_tests:
        med_reasons.append("test requirements not specified in draft")
    if not has_rollback:
        med_reasons.append("rollback notes not specified in draft")

    if med_reasons:
        return "medium", med_reasons

    return "low", ["single file, no protected files, test requirements and rollback notes present"]


def _is_protected_file(file_entry: dict[str, Any]) -> bool:
    path = str(file_entry.get("path", ""))
    category = str(file_entry.get("category", "")).lower()
    if category in _PROTECTED_CATEGORIES:
        return True
    filename = Path(path).name.lower()
    if filename in _PROTECTED_FILE_NAMES:
        return True
    if filename.startswith("dockerfile"):
        return True
    if filename.startswith("requirements") and filename.endswith(".txt"):
        return True
    return False


def _is_deletion_like(unit: dict[str, Any]) -> bool:
    edit_type = str(unit.get("edit_type", "")).lower()
    intent = str(unit.get("intent", "")).lower()
    return (
        "delete" in edit_type
        or "remove" in edit_type
        or "delete" in intent
        or "remove" in intent
    )


def _extract_affected_files(draft: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    target_files = draft.get("target_files", [])
    if not isinstance(target_files, list):
        return result
    for item in target_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(
            {
                "path": path,
                "category": str(item.get("category", "unknown")).strip(),
                "confidence": _normalize_confidence(item.get("confidence")),
            }
        )
    return result


def _build_missing_evidence(
    draft: dict[str, Any],
    edit_units: list[dict[str, Any]],
    has_tests: bool,
    has_rollback: bool,
) -> list[str]:
    missing: list[str] = []

    if draft.get("status") == "error":
        missing.append(
            "source executable patch draft has status: error — review gate may be incomplete"
        )

    placeholder_units = [
        u for u in edit_units if isinstance(u, dict) and u.get("old_text") is None
    ]
    if placeholder_units:
        missing.append(
            f"{len(placeholder_units)} edit unit(s) have placeholder old_text — "
            "full file reads required before any grounding phase"
        )

    if not has_tests:
        missing.append("no test requirements specified; tests must be defined before any apply phase")
    if not has_rollback:
        missing.append("no rollback notes specified; rollback plan must be defined before any apply phase")

    open_questions = _normalize_string_list(draft.get("open_questions", []))
    for question in open_questions:
        missing.append(f"open question from draft: {question}")

    return missing


def _build_docs_required(affected_files: list[dict[str, Any]]) -> list[str]:
    docs: list[str] = []
    doc_files = [
        f["path"] for f in affected_files if str(f.get("category", "")).lower() == "doc"
    ]
    if doc_files:
        docs.append(f"update docs aligned to changed files: {', '.join(doc_files)}")
    if any(
        str(f.get("category", "")).lower() in _PROTECTED_CATEGORIES for f in affected_files
    ):
        docs.append(
            "update operator documentation if configuration or dependency changes are made"
        )
    return docs


def _build_reviewer_checklist(
    affected_files: list[dict[str, Any]],
    edit_units: list[dict[str, Any]],
    risk_level: str,
) -> list[str]:
    checklist = [
        "Confirm this review artifact was generated from the correct executable patch draft.",
        f"Verify all {len(affected_files)} affected file(s) are in scope for the approved migration plan.",
        f"Review all {len(edit_units)} planned edit unit(s) for accuracy and completeness.",
        "Confirm apply_allowed is false in this record and in the source draft.",
        "Verify tests_required are actionable and sufficient before any apply phase.",
        "Verify rollback_notes_required is true and a rollback plan is in place.",
        "Confirm no secret/env files are targeted (check affected_files list).",
        "Confirm source files were not mutated by this review process.",
    ]
    if risk_level == "high":
        checklist.append(
            "HIGH RISK: extra scrutiny required before any approval; consider a second reviewer."
        )
        checklist.append(
            "HIGH RISK: verify protected/config/dependency files will not break the runtime."
        )
    checklist.append(
        "Set final_decision.selected to one of: APPROVE_MANUAL_REVIEW_ONLY, REQUEST_CHANGES, or REJECT."
    )
    return checklist


def render_project_evolution_review_gate_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Project Evolution Review Gate",
        "",
        "## Decision",
        f"- Approval status: `{record.get('approval_status', 'pending')}`",
        f"- Human approval required: `{record.get('human_approval_required', True)}`",
        f"- Apply allowed: `{record.get('apply_allowed', False)}`",
    ]
    decision = record.get("final_decision") or {}
    if decision:
        lines += [
            f"- Options: {', '.join(decision.get('options', []))}",
            f"- Selected: `{decision.get('selected')}`",
            f"- Note: {decision.get('note', '')}",
        ]
    lines += [
        "",
        "## Summary",
        f"- Draft ID: `{record.get('draft_id', '')}`",
        f"- Source draft: `{record.get('source_draft_path', '')}`",
        f"- Generated at: `{record.get('generated_at', '')}`",
        f"- Planned edit count: `{record.get('planned_edit_count', 0)}`",
        f"- Affected file count: `{len(record.get('affected_files', []))}`",
        "",
        "## Risk Classification",
        f"- Risk level: **{str(record.get('risk_level', 'unknown')).upper()}**",
        "- Risk reasons:",
        *_render_string_list(record.get("risk_reasons", [])),
        "",
        "## Affected Files",
        *_render_file_lines(record.get("affected_files", [])),
        "",
        "## Planned Edit Units",
        f"- {record.get('planned_edit_count', 0)} edit unit(s) planned.",
        "- All edit units have apply_allowed: false.",
        "- All edit units contain placeholder old_text/new_text requiring full file reads before grounding.",
        "",
        "## Missing Evidence",
        *_render_string_list(record.get("missing_evidence", [])),
        "",
        "## Required Tests",
        *_render_string_list(record.get("tests_required", [])),
        "",
        "## Required Docs",
        *_render_string_list(record.get("docs_required", [])),
        "",
        "## Rollback Notes",
        f"- Rollback notes required: `{record.get('rollback_notes_required', True)}`",
        "",
        "## Reviewer Checklist",
        *_render_string_list(record.get("reviewer_checklist", [])),
        "",
        "## Guardrails",
        "- This phase is review-only.",
        "- No patch was generated or applied.",
        "- apply_allowed remains false.",
        "- Human approval is required before any future apply step.",
        "- This report is not permission to mutate the repository.",
        "",
    ]
    if record.get("status") == "error" and record.get("error"):
        lines += [
            "## Error",
            f"- {record['error']['message']}",
            "",
        ]
    return "\n".join(lines)


def write_project_evolution_review_gate_artifacts(
    repo_path: str,
    executable_patch_draft_path: str,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_project_evolution_review_gate(str(repo_root), executable_patch_draft_path)
    if record.get("status") == "error":
        return {"record": record, "json_path": "", "md_path": ""}

    output_root = _resolve_output_root(repo_root)
    timestamp = _safe_timestamp(record["generated_at"])
    prefix = f"{timestamp}_review_gate"
    json_path = output_root / f"{prefix}.json"
    md_path = output_root / f"{prefix}.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_project_evolution_review_gate_markdown(record), encoding="utf-8")
    return {"record": record, "json_path": str(json_path), "md_path": str(md_path)}


def _resolve_draft_path(repo_root: Path, draft_path: str) -> Path | None:
    root = (repo_root / ".agent" / "project_evolution" / "executable_patch_drafts").resolve()
    candidate = Path(draft_path).expanduser()
    resolved = candidate if candidate.is_absolute() else (repo_root / candidate)
    resolved = resolved.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _raw_path(repo_root: Path, artifact_path: str) -> Path:
    candidate = Path(artifact_path).expanduser()
    return candidate if candidate.is_absolute() else (repo_root / candidate)


def _resolve_output_root(repo_root: Path) -> Path:
    resolved = (repo_root / ".agent" / "project_evolution" / REVIEW_GATES_DIRNAME).resolve()
    resolved.relative_to(repo_root)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _load_json_record(path: Path, schema_version: str, label: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "error",
            "code": f"{label.replace(' ', '_')}_missing",
            "message": f"{label} does not exist: {path}",
        }
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "code": f"{label.replace(' ', '_')}_invalid_json",
            "message": f"{label} is invalid JSON: {path} ({exc})",
        }
    except OSError as exc:
        return {
            "status": "error",
            "code": f"{label.replace(' ', '_')}_unreadable",
            "message": f"{label} could not be read: {path} ({exc})",
        }
    if not isinstance(record, dict) or record.get("schema_version") != schema_version:
        return {
            "status": "error",
            "code": f"{label.replace(' ', '_')}_bad_schema",
            "message": f"{label} has an unexpected schema: {path}",
        }
    return {"status": "ok", "record": record}


def _build_error_record(*, source_draft_path: str, message: str, code: str) -> dict[str, Any]:
    return {
        "generated_at": _utc_now_iso(),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {"code": code, "message": message},
        "draft_id": "",
        "source_draft_path": source_draft_path,
        "apply_allowed": False,
        "human_approval_required": True,
        "approval_status": "pending",
        "affected_files": [],
        "planned_edit_count": 0,
        "risk_level": "unknown",
        "risk_reasons": [],
        "missing_evidence": [],
        "rollback_notes_required": True,
        "tests_required": [],
        "docs_required": [],
        "reviewer_checklist": [],
        "final_decision": {
            "options": ["APPROVE_MANUAL_REVIEW_ONLY", "REQUEST_CHANGES", "REJECT"],
            "selected": None,
            "note": (
                "Human reviewer must select one of the options above before any apply step proceeds."
            ),
        },
    }


def _normalize_string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip() if item is not None else ""
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(confidence, 1.0))


def _render_string_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _render_file_lines(files: list[dict[str, Any]]) -> list[str]:
    if not files:
        return ["- None"]
    lines: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('path', '')}` [{item.get('category', 'unknown')}, "
            f"confidence={item.get('confidence', 0.0):.2f}]"
        )
    return lines or ["- None"]


def _safe_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
