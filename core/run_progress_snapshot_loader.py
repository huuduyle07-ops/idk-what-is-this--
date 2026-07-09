"""UX.RUN.2 - Run Progress Snapshot Loader.

Loads existing run-progress snapshot/report artifacts for operator review. This
module is read-only with respect to source artifacts: it does not create live
progress, poll jobs, change execution behavior, launch workers, call models,
apply patches, run validation, run benchmarks, or trigger actions.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


REPORT_KIND = "run_progress_snapshot_loader"
JSON_NAME = "run_progress_snapshot_loader_report.json"
MD_NAME = "run_progress_snapshot_loader_report.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "ux" / "run_progress_snapshot_loader"
VISIBILITY_ROOT = Path(".agent") / "ux" / "run_progress_visibility"
SNAPSHOT_ROOT = Path(".agent") / "ux" / "run_progress_snapshots"
VISIBILITY_REPORT_JSON = "run_progress_visibility_report.json"

LOADED = "run_progress_snapshot_loaded"
LOADED_WITH_WARNINGS = "run_progress_snapshot_loaded_with_warnings"
NOT_FOUND = "run_progress_snapshot_not_found"
MALFORMED = "run_progress_snapshot_malformed"
BLOCKED = "run_progress_snapshot_blocked"

SAFE_SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

REQUIRED_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "snapshot_id",
    "snapshot_status",
    "source_contract_phase",
    "stages",
    "current_stage_id",
    "completed_stage_ids",
    "pending_stage_ids",
    "warning_stage_ids",
    "error_stage_ids",
    "progress_notice",
    "simulated_only",
    "live_stream_enabled",
    "polling_enabled",
    "runtime_behavior_changed",
    "actions_available",
    "warnings",
    "blocked_reasons",
    "recommended_next_phase",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.RUN.3",
    "title": "Run Progress UI Panel Stub",
    "reason": (
        "Add a read-only UI panel that displays loaded progress snapshots while "
        "still avoiding live streaming, polling, and action controls."
    ),
}

GUARDRAIL_NOTE = (
    "Run Progress Snapshot Loader is read-only: it loads existing progress "
    "snapshot/report JSON for review and does not create live progress, poll "
    "running jobs, change execution behavior, call models, launch workers, "
    "apply patches, run validation, run benchmarks, or trigger actions."
)

NO_LIVE_PROGRESS_WARNING = (
    "No live progress stream yet; UX.RUN.2 only loads existing snapshot artifacts."
)

READ_ONLY_BOUNDARIES: tuple[str, ...] = (
    "Loads existing JSON only.",
    "Rejects traversal, absolute paths, unsafe ids, and unsafe extensions.",
    "Does not create live progress.",
    "Does not poll active runs.",
    "Does not change execution behavior.",
    "Does not launch workers.",
    "Does not call or route models.",
    "Does not apply patches.",
    "Does not run validation.",
    "Does not run benchmarks.",
    "Does not expose action controls.",
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _add_reason(reasons: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in reasons):
        reasons.append({"reason": reason, "message": message})


def _result(
    *,
    loader_status: str,
    snapshot_id: str,
    source_path: str = "",
    snapshot: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    blocked_reasons: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "loader_status": loader_status,
        "snapshot_id": str(snapshot_id or ""),
        "source_path": str(source_path or ""),
        "snapshot": snapshot,
        "warnings": list(warnings or []),
        "blocked_reasons": list(blocked_reasons or []),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _validate_snapshot_id(raw_snapshot_id: str | None) -> tuple[str, list[dict[str, str]]]:
    snapshot_id = str(raw_snapshot_id or "default").strip() or "default"
    reasons: list[dict[str, str]] = []
    lower = snapshot_id.lower()

    if snapshot_id in {".", ".."} or ".." in snapshot_id:
        _add_reason(
            reasons,
            "snapshot_id_traversal_blocked",
            "Snapshot id must not contain traversal markers.",
        )
    if any(sep in snapshot_id for sep in ("/", "\\")):
        _add_reason(
            reasons,
            "snapshot_id_path_separator_blocked",
            "Snapshot id must not contain path separators.",
        )
    if ":" in snapshot_id or snapshot_id.startswith(("/", "\\")) or Path(snapshot_id).is_absolute():
        _add_reason(
            reasons,
            "snapshot_id_absolute_path_blocked",
            "Snapshot id must not be an absolute path.",
        )
    if "?" in snapshot_id or "#" in snapshot_id or "\x00" in snapshot_id:
        _add_reason(
            reasons,
            "snapshot_id_unsafe_character_blocked",
            "Snapshot id contains unsafe characters.",
        )

    suffix = Path(snapshot_id).suffix.lower()
    if suffix and suffix != ".json":
        _add_reason(
            reasons,
            "snapshot_id_unsafe_extension_blocked",
            "Only extensionless ids or .json snapshot ids are allowed.",
        )
    if lower.endswith(".json"):
        base = snapshot_id[:-5]
    else:
        base = snapshot_id
    if not base or not SAFE_SNAPSHOT_ID_RE.fullmatch(snapshot_id):
        _add_reason(
            reasons,
            "snapshot_id_pattern_blocked",
            "Snapshot id must be a safe slug.",
        )
    return snapshot_id, reasons


def _candidate_paths(snapshot_id: str, repo_root: Path) -> list[Path]:
    visibility_root = (repo_root / VISIBILITY_ROOT).resolve()
    snapshot_root = (repo_root / SNAPSHOT_ROOT).resolve()
    if snapshot_id == "default":
        return [(visibility_root / VISIBILITY_REPORT_JSON).resolve()]

    file_name = snapshot_id if snapshot_id.lower().endswith(".json") else f"{snapshot_id}.json"
    return [
        (snapshot_root / file_name).resolve(),
        (snapshot_root / snapshot_id / "run_progress_snapshot.json").resolve(),
        (visibility_root / file_name).resolve(),
    ]


def _inside_allowed_roots(path: Path, repo_root: Path) -> bool:
    roots = [
        (repo_root / VISIBILITY_ROOT).resolve(),
        (repo_root / SNAPSHOT_ROOT).resolve(),
    ]
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, False
    if not isinstance(data, dict):
        return None, False
    return data, True


def _visibility_report_to_snapshot(report: dict[str, Any], snapshot_id: str) -> dict[str, Any]:
    stages = copy.deepcopy(_list(report.get("stage_contract")))
    stage_ids = [str(stage.get("stage_id", "")) for stage in stages if isinstance(stage, dict)]
    return {
        "snapshot_id": snapshot_id,
        "snapshot_status": "run_progress_snapshot_from_visibility_report",
        "source_contract_phase": "UX.RUN.1",
        "stages": stages,
        "current_stage_id": stage_ids[0] if stage_ids else "",
        "completed_stage_ids": [],
        "pending_stage_ids": stage_ids,
        "warning_stage_ids": [],
        "error_stage_ids": [],
        "progress_notice": (
            "No live progress stream yet; loaded the UX.RUN.1 visibility report as "
            "a read-only snapshot source."
        ),
        "simulated_only": True,
        "live_stream_enabled": False,
        "polling_enabled": False,
        "runtime_behavior_changed": False,
        "actions_available": [],
        "warnings": _string_list(report.get("warnings")),
        "blocked_reasons": copy.deepcopy(_list(report.get("blocked_reasons"))),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _coerce_snapshot(data: dict[str, Any], snapshot_id: str) -> dict[str, Any] | None:
    if data.get("report_kind") == "run_progress_visibility":
        return _visibility_report_to_snapshot(data, snapshot_id)
    return copy.deepcopy(data)


def _required_field_reasons(snapshot: dict[str, Any] | None) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    if not isinstance(snapshot, dict):
        _add_reason(reasons, "snapshot_required_object_missing", "Snapshot JSON must be an object.")
        return reasons
    missing = [field for field in REQUIRED_SNAPSHOT_FIELDS if field not in snapshot]
    if missing:
        _add_reason(
            reasons,
            "snapshot_required_fields_missing",
            "Snapshot JSON is missing required fields: " + ", ".join(missing),
        )
    if "stages" in snapshot and not isinstance(snapshot.get("stages"), list):
        _add_reason(reasons, "snapshot_required_stages_invalid", "Snapshot stages must be a list.")
    if "actions_available" in snapshot and not isinstance(snapshot.get("actions_available"), list):
        _add_reason(
            reasons,
            "snapshot_required_actions_invalid",
            "Snapshot actions_available must be a list.",
        )
    return reasons


def _boundary_reasons(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    if snapshot.get("live_stream_enabled") is True:
        _add_reason(
            reasons,
            "snapshot_live_stream_enabled_blocked",
            "Snapshot claims live stream support, which UX.RUN.2 does not provide.",
        )
    if snapshot.get("polling_enabled") is True:
        _add_reason(
            reasons,
            "snapshot_polling_enabled_blocked",
            "Snapshot claims polling support, which UX.RUN.2 must not add.",
        )
    if snapshot.get("runtime_behavior_changed") is True:
        _add_reason(
            reasons,
            "snapshot_runtime_behavior_changed_blocked",
            "Snapshot claims runtime behavior changed.",
        )
    if _list(snapshot.get("actions_available")):
        _add_reason(
            reasons,
            "snapshot_actions_available_blocked",
            "Snapshot exposes action controls, which UX.RUN.2 must not load as actionable.",
        )
    for key in ("runtime_authority_claimed", "runtime_authority", "claims_runtime_authority"):
        if snapshot.get(key) is True:
            _add_reason(
                reasons,
                "snapshot_runtime_authority_claim_blocked",
                "Snapshot claims runtime authority.",
            )

    for stage in _list(snapshot.get("stages")):
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("stage_id") or "(unknown)")
        if stage.get("is_runtime_authority") is True:
            _add_reason(
                reasons,
                f"stage:{stage_id}:runtime_authority_blocked",
                f"Stage {stage_id} claims runtime authority.",
            )
        if stage.get("may_trigger_action") is True:
            _add_reason(
                reasons,
                f"stage:{stage_id}:action_trigger_blocked",
                f"Stage {stage_id} claims action-triggering power.",
            )
    return reasons


def _snapshot_warnings(snapshot: dict[str, Any]) -> list[str]:
    warnings = _string_list(snapshot.get("warnings"))
    if not any(NO_LIVE_PROGRESS_WARNING in warning for warning in warnings):
        warnings.append(NO_LIVE_PROGRESS_WARNING)
    return warnings


def load_run_progress_snapshot(
    snapshot_id: str | None = "default",
    *,
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    """Load one existing progress snapshot/report artifact without mutation."""
    repo = Path(repo_root)
    safe_id, unsafe_reasons = _validate_snapshot_id(snapshot_id)
    if unsafe_reasons:
        return _result(
            loader_status=BLOCKED,
            snapshot_id=safe_id,
            warnings=[],
            blocked_reasons=unsafe_reasons,
        )

    candidates = _candidate_paths(safe_id, repo)
    for candidate in candidates:
        if not _inside_allowed_roots(candidate, repo):
            return _result(
                loader_status=BLOCKED,
                snapshot_id=safe_id,
                blocked_reasons=[
                    {
                        "reason": "snapshot_path_outside_allowed_roots_blocked",
                        "message": "Resolved snapshot path escaped the allowed input roots.",
                    }
                ],
            )
        if not candidate.is_file():
            continue

        source_path = _rel_path(candidate, repo)
        data, ok = _load_json(candidate)
        if not ok:
            return _result(
                loader_status=MALFORMED,
                snapshot_id=safe_id,
                source_path=source_path,
                blocked_reasons=[
                    {
                        "reason": "snapshot_json_malformed",
                        "message": "Snapshot JSON could not be parsed as an object.",
                    }
                ],
            )

        snapshot = _coerce_snapshot(_dict(data), safe_id)
        malformed_reasons = _required_field_reasons(snapshot)
        if malformed_reasons:
            return _result(
                loader_status=MALFORMED,
                snapshot_id=safe_id,
                source_path=source_path,
                blocked_reasons=malformed_reasons,
            )

        blocked_reasons = _boundary_reasons(snapshot)
        warnings = _snapshot_warnings(snapshot)
        if blocked_reasons:
            return _result(
                loader_status=BLOCKED,
                snapshot_id=safe_id,
                source_path=source_path,
                snapshot=snapshot,
                warnings=warnings,
                blocked_reasons=blocked_reasons,
            )

        status = LOADED_WITH_WARNINGS if warnings else LOADED
        return _result(
            loader_status=status,
            snapshot_id=safe_id,
            source_path=source_path,
            snapshot=snapshot,
            warnings=warnings,
            blocked_reasons=[],
        )

    return _result(
        loader_status=NOT_FOUND,
        snapshot_id=safe_id,
        source_path=_rel_path(candidates[0], repo) if candidates else "",
        blocked_reasons=[],
    )


def build_run_progress_snapshot_loader_report(
    *,
    repo_root: str | Path = ".",
    snapshot_id: str | None = "default",
    report_id: str = "ux-run-2",
    created_at: str = "",
) -> dict[str, Any]:
    loader_result = load_run_progress_snapshot(snapshot_id=snapshot_id, repo_root=repo_root)
    return {
        "report_kind": REPORT_KIND,
        "report_id": str(report_id),
        "created_at": str(created_at),
        "status": loader_result["loader_status"],
        "guardrail_note": GUARDRAIL_NOTE,
        "snapshot_id": loader_result["snapshot_id"],
        "allowed_input_roots": [
            VISIBILITY_ROOT.as_posix(),
            SNAPSHOT_ROOT.as_posix(),
        ],
        "loader_result": loader_result,
        "read_only_boundaries": list(READ_ONLY_BOUNDARIES),
        "warnings": list(loader_result.get("warnings") or []),
        "blocked_reasons": list(loader_result.get("blocked_reasons") or []),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def render_run_progress_snapshot_loader_markdown(report: dict[str, Any]) -> str:
    """Render the loader report as operator-readable Markdown."""
    result = _dict(report.get("loader_result"))
    snapshot = _dict(result.get("snapshot"))
    next_phase = _dict(report.get("recommended_next_phase"))
    lines: list[str] = [
        "# Run Progress Snapshot Loader",
        "",
        f"> {report.get('guardrail_note', GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id', ''))}`",
        f"- **Created at:** `{_md(report.get('created_at', ''))}`",
        "- **Loader status:** `{}`".format(_md(result.get("loader_status", report.get("status", "")))),
        "- **Snapshot id:** `{}`".format(_md(result.get("snapshot_id", report.get("snapshot_id", "")))),
        f"- **Source path:** `{_md(result.get('source_path', ''))}`",
        f"- **Live stream enabled:** `{str(bool(snapshot.get('live_stream_enabled'))).lower()}`",
        f"- **Polling enabled:** `{str(bool(snapshot.get('polling_enabled'))).lower()}`",
        f"- **Runtime behavior changed:** `{str(bool(snapshot.get('runtime_behavior_changed'))).lower()}`",
        "",
        "## Progress Notice",
        "",
        _md(snapshot.get("progress_notice", "No live progress stream yet.")),
        "",
        "## Stages",
        "",
        "| Stage | Label | Runtime authority | Triggers action | Safe to display |",
        "| --- | --- | --- | --- | --- |",
    ]
    for stage in _list(snapshot.get("stages")):
        row = _dict(stage)
        lines.append(
            "| {stage} | {label} | {authority} | {trigger} | {safe} |".format(
                stage=_md(row.get("stage_id", "")),
                label=_md(row.get("label", "")),
                authority=str(bool(row.get("is_runtime_authority"))).lower(),
                trigger=str(bool(row.get("may_trigger_action"))).lower(),
                safe=str(bool(row.get("safe_to_display", True))).lower(),
            )
        )

    lines.extend(["", "## Warnings", ""])
    warnings = _string_list(report.get("warnings"))
    lines.extend([f"- {_md(warning)}" for warning in warnings] if warnings else ["_None._"])

    lines.extend(["", "## Blocked Reasons", ""])
    blocked = _list(report.get("blocked_reasons"))
    if blocked:
        for reason in blocked:
            row = _dict(reason)
            lines.append(f"- `{_md(row.get('reason', ''))}`: {_md(row.get('message', ''))}")
    else:
        lines.append("_None._")

    lines.extend(["", "## Boundaries", ""])
    for boundary in report.get("read_only_boundaries") or READ_ONLY_BOUNDARIES:
        lines.append(f"- {_md(boundary)}")

    lines.extend(
        [
            "",
            "## Recommended Next Phase",
            "",
            f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
            f"- **Title:** {_md(next_phase.get('title', ''))}",
            f"- **Reason:** {_md(next_phase.get('reason', ''))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_run_progress_snapshot_loader_report(
    *,
    repo_root: str | Path = ".",
    snapshot_id: str | None = "default",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "ux-run-2",
    created_at: str = "",
) -> dict[str, Any]:
    """Write UX.RUN.2 JSON and Markdown loader report artifacts."""
    report = build_run_progress_snapshot_loader_report(
        repo_root=repo_root,
        snapshot_id=snapshot_id,
        report_id=report_id,
        created_at=created_at,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_run_progress_snapshot_loader_markdown(report), encoding="utf-8")
    return {
        "ok": report["status"] in {LOADED, LOADED_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
