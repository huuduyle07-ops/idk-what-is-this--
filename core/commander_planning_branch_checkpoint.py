"""CMD.CLOSE - Commander Planning Branch Checkpoint (report-only).

Freezes the CMD.N1-CMD.N6 Commander planning branch before any execution,
routing, worker-launch, tool-use, or patch-application design is added.

This module reads the phase registry and already-written Commander planning
artifacts, then writes JSON and Markdown checkpoint artifacts only. It does not
call models, launch workers, invoke tools, apply patches, run validation, run
benchmarks, use Docker/subprocess, contact networks, write databases, mutate
source artifacts, change route behavior, change auth policy, or change routing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "commander_planning_branch_checkpoint"
JSON_NAME = "commander_planning_branch_checkpoint.json"
MD_NAME = "commander_planning_branch_checkpoint.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "commander" / "planning_branch_checkpoint"
DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"

DEFAULT_BOSS_HALF_LIFE_PATH = (
    Path(".agent") / "commander" / "boss_half_life_fracture_plan" / "boss_half_life_fracture_plan.json"
)
DEFAULT_MANUAL_FRACTURE_PATH = (
    Path(".agent") / "commander" / "manual_boss_fracture_report" / "cmd-n2-demo" / "manual_boss_fracture_report.json"
)
DEFAULT_FRACTURE_TREE_PATH = (
    Path(".agent") / "commander" / "fracture_tree_registry" / "cmd-n3-demo" / "commander_fracture_tree_registry.json"
)
DEFAULT_PREFLIGHT_PATH = (
    Path(".agent") / "commander" / "preflight_contract" / "cmd-n3-demo" / "commander_preflight_contract.json"
)
DEFAULT_ASSIGNMENT_PATH = (
    Path(".agent") / "commander" / "manual_assignment_plan" / "cmd-n3-demo" / "commander_manual_assignment_plan.json"
)
DEFAULT_REVIEW_PACK_PATH = (
    Path(".agent") / "commander" / "assignment_review_pack" / "cmd-n3-demo" / "commander_assignment_review_pack.json"
)

STATUS_FROZEN = "commander_planning_frozen"
STATUS_FROZEN_WARNINGS = "commander_planning_frozen_with_warnings"
STATUS_INCOMPLETE = "commander_planning_incomplete"
STATUS_BLOCKED = "commander_planning_blocked"

CHECKPOINT_STATUSES: tuple[str, ...] = (
    STATUS_FROZEN,
    STATUS_FROZEN_WARNINGS,
    STATUS_INCOMPLETE,
    STATUS_BLOCKED,
)

REQUIRED_PHASE_IDS: tuple[str, ...] = ("CMD.N1", "CMD.N2", "CMD.N3", "CMD.N4", "CMD.N5", "CMD.N6")
THIS_PHASE_ID = "CMD.CLOSE"

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

ARTIFACT_SPECS: tuple[dict[str, str], ...] = (
    {
        "key": "boss_half_life",
        "phase_id": "CMD.N1",
        "title": "Boss Half-Life Fracture Plan",
        "report_kind": "boss_half_life_fracture_plan",
        "status_field": "decision.status",
    },
    {
        "key": "manual_fracture",
        "phase_id": "CMD.N2",
        "title": "Manual Boss Fracture Report",
        "report_kind": "manual_boss_fracture_report",
        "status_field": "commander_decision.status",
    },
    {
        "key": "fracture_tree",
        "phase_id": "CMD.N3",
        "title": "Commander Fracture Tree Registry",
        "report_kind": "commander_fracture_tree_registry",
        "status_field": "validation_status",
    },
    {
        "key": "preflight",
        "phase_id": "CMD.N4",
        "title": "Commander Preflight Contract",
        "report_kind": "commander_preflight_contract",
        "status_field": "preflight_status",
    },
    {
        "key": "assignment",
        "phase_id": "CMD.N5",
        "title": "Commander Manual Assignment Plan",
        "report_kind": "commander_manual_assignment_plan",
        "status_field": "assignment_status",
    },
    {
        "key": "review_pack",
        "phase_id": "CMD.N6",
        "title": "Commander Assignment Review Pack",
        "report_kind": "commander_assignment_review_pack",
        "status_field": "review_status",
    },
)

EXECUTABLE_WORKER_KEYS: tuple[str, ...] = (
    "worker_binding",
    "worker_id",
    "worker",
    "assigned_worker",
    "executable_worker",
    "execution_worker",
    "launch_worker",
    "executable_assignment",
    "executable_worker_id",
)

AUTO_FLAG_KEYS: tuple[str, ...] = (
    "auto_apply",
    "auto_run",
    "auto_merge",
    "automatic_apply",
    "automatic_run",
    "automatic_merge",
)

MODEL_AUTHORITY_KEYS: tuple[str, ...] = (
    "model_authority",
    "authority_model",
    "authoritative_model",
    "model_name_as_authority",
)

MODEL_ID_KEYS: tuple[str, ...] = (
    "model",
    "model_id",
    "model_name",
    "llm",
    "authority",
    "execution_authority",
)

MODEL_ID_TOKENS: tuple[str, ...] = (
    "gpt-",
    "gpt_",
    "claude",
    "gemini",
    "llama",
    "mistral",
    "mixtral",
    "deepseek",
    "o1",
    "o3",
    "o4",
)

EXECUTION_MARKER_REASONS: dict[str, str] = {
    "worker_launch_path": "worker launch path detected",
    "launch_worker_path": "worker launch path detected",
    "patch_apply_path": "patch apply path detected",
    "apply_patch_path": "patch apply path detected",
    "validation_execution_path": "validation execution path detected",
    "validation_run_path": "validation execution path detected",
    "benchmark_execution_path": "benchmark execution path detected",
    "benchmark_run_path": "benchmark execution path detected",
    "route_behavior_changed": "route behavior change marker detected",
    "route_behavior_change": "route behavior change marker detected",
    "web_route_behavior_changed": "web route behavior change marker detected",
    "web_route_behavior_change": "web route behavior change marker detected",
    "routing_changed": "routing behavior change marker detected",
    "routing_change": "routing behavior change marker detected",
    "database_write": "database write marker detected",
    "database_write_path": "database write marker detected",
    "network_call": "network call marker detected",
    "network_request": "network call marker detected",
    "subprocess_invocation": "subprocess invocation marker detected",
    "docker_subprocess": "Docker/subprocess marker detected",
    "tool_invocation": "tool invocation marker detected",
    "mcp_invocation": "MCP invocation marker detected",
    "execution_capability": "execution capability marker detected",
    "execution_capability_added": "execution capability marker detected",
}

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "model_call_performed",
    "worker_launch_performed",
    "real_worker_assignment_performed",
    "executable_worker_binding_performed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_subprocess_performed",
    "network_call_performed",
    "database_write_performed",
    "route_behavior_change_performed",
    "web_route_behavior_change_performed",
    "auth_policy_change_performed",
    "routing_change_performed",
    "source_artifact_mutation_performed",
    "automatic_decomposition_performed",
    "auto_run_performed",
    "auto_apply_performed",
    "auto_merge_performed",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "MODEL.N1",
    "title": "Model Role Registry / Tower Card Contract",
    "reason": (
        "After Mirror gave self-observation and Commander gave planning/fracture "
        "structure, MODEL.N1 should define advisory model/role tower cards before "
        "any actual routing or worker assignment exists."
    ),
    "alternative": (
        "CMD.EXEC_PLAN.1 - Commander Execution Safety Design, available only if "
        "explicitly desired after this planning freeze."
    ),
}

COMMANDER_PLANNING_BRANCH_CHECKPOINT_GUARDRAIL_NOTE = (
    "Commander Planning Branch Checkpoint is report-only: it reads CMD.N1-CMD.N6 "
    "planning artifacts and the phase registry, then writes JSON plus Markdown "
    "checkpoint artifacts only. It does not call models, bind real workers or "
    "models, launch workers, run tools, run validation or benchmarks, apply "
    "patches, mutate source artifacts, route tasks, invoke MCP tools, execute "
    "Dream actions, apply Replay janitor actions, use Docker/subprocess, contact "
    "networks, write databases, or change route, auth, or routing behavior."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "checkpoint only",
    "no model call",
    "no executable worker binding",
    "no real model binding",
    "no automatic decomposition",
    "no worker launch",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP invocation",
    "no Dream execution",
    "no Replay janitor apply",
    "no Docker/subprocess",
    "no network",
    "no database write",
    "no route behavior change",
    "no auth policy change",
    "no routing change",
    "no mutation of source artifacts",
    "writes checkpoint artifacts only",
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _lower(value: Any) -> str:
    return str(bool(value)).lower()


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _split_segments(value: str) -> list[str]:
    return [segment for segment in str(value).replace("\\", "/").split("/") if segment]


def _path_has_traversal(value: str) -> bool:
    return any(segment == ".." for segment in _split_segments(value))


def _input_path_blockers(path: str | Path | None, label: str) -> list[str]:
    if path is None or str(path).strip() == "":
        return [f"{label} path is required"]
    if _path_has_traversal(str(path)):
        return [f"{label} path must not contain traversal segments"]
    return []


def _load_json_object(path: str | Path | None, label: str) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    blockers = _input_path_blockers(path, label)
    if blockers:
        return None, blockers, []
    source = Path(str(path))
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [], [f"{label} artifact is missing or unreadable: {exc}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [], [f"{label} artifact must contain valid JSON: {exc.msg}"]
    if not isinstance(data, dict):
        return None, [], [f"{label} artifact must contain a JSON object"]
    return data, [], []


def _read_registry(path: str | Path | None) -> tuple[dict[str, Any] | None, list[str]]:
    blockers = _input_path_blockers(path, "registry")
    if blockers:
        return None, blockers
    source = Path(str(path))
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"phase registry could not be read: {exc}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"phase registry must contain valid JSON: {exc.msg}"]
    if not isinstance(data, dict):
        return None, ["phase registry must contain a JSON object"]
    return data, []


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    root = registry_data if isinstance(registry_data, dict) else {}
    phases = root.get("phases") if isinstance(root.get("phases"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for phase in phases:
        if isinstance(phase, dict) and str(phase.get("phase_id") or "").strip():
            out[str(phase["phase_id"]).strip()] = phase
    return out


def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    violations = [field for field in PHASE_GUARDRAIL_FIELDS if phase.get(field) is True]
    automation = str(phase.get("automation_level") or "")
    if automation not in {"LOCAL_0_OBSERVE", "LOCAL_1_PREPARE"}:
        violations.append(f"automation_level={automation or '(missing)'}")
    if phase.get("human_approval_required") is not True:
        violations.append("human_approval_required")
    return violations


def _build_phase_completion(registry_data: dict[str, Any] | None, registry_blockers: list[str]) -> tuple[dict[str, Any], list[str]]:
    blockers = list(registry_blockers)
    phases = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    for pid in REQUIRED_PHASE_IDS:
        phase = phases.get(pid)
        present = phase is not None
        status = str(phase.get("status") or "") if present else "(missing)"
        complete = present and status == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        if not present:
            blockers.append(f"required phase {pid} is missing from the registry")
        elif not complete:
            blockers.append(f"required phase {pid} is not complete: {status}")
        if violations:
            blockers.append(f"required phase {pid} has unsafe guardrail metadata: {', '.join(violations)}")
        checks.append(
            {
                "phase_id": pid,
                "present": present,
                "status": status,
                "complete": complete,
                "guardrails_ok": present and not violations,
                "guardrail_violations": violations,
            }
        )

    close_phase = phases.get(THIS_PHASE_ID)
    close_present = close_phase is not None
    close_status = str(close_phase.get("status") or "") if close_present else "(missing)"
    close_violations = _phase_guardrail_violations(close_phase) if close_present else []
    if close_present and close_violations:
        blockers.append(f"{THIS_PHASE_ID} has unsafe guardrail metadata: {', '.join(close_violations)}")

    return (
        {
            "required_phase_ids": list(REQUIRED_PHASE_IDS),
            "phase_checks": checks,
            "all_required_phases_complete": all(check["complete"] for check in checks),
            "all_required_phase_guardrails_ok": all(check["guardrails_ok"] for check in checks),
            "this_phase_id": THIS_PHASE_ID,
            "this_phase_registered": close_present,
            "this_phase_status": close_status,
            "this_phase_complete": close_present and close_status == "complete",
            "this_phase_guardrails_ok": close_present and not close_violations,
            "this_phase_guardrail_violations": close_violations,
        },
        blockers,
    )


def _lookup_status(data: dict[str, Any], dotted: str) -> str:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return ""
        current = current.get(part)
    return str(current or "")


def _artifact_status(data: dict[str, Any], spec: dict[str, str]) -> str:
    status = _lookup_status(data, spec["status_field"])
    if status:
        return status
    if spec["key"] == "manual_fracture":
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        return str(summary.get("decision_status") or "")
    return ""


def _collect_artifact_warnings(key: str, data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for field in ("warnings", "incomplete_reasons"):
        for item in _strings(data.get(field)):
            warnings.append(f"{key}: {item}")
    if key == "boss_half_life":
        for item in _strings(data.get("blockers")):
            warnings.append(f"{key}: {item}")
    return warnings


def _n1_formula_incomplete(data: dict[str, Any] | None) -> list[str]:
    if not isinstance(data, dict):
        return []
    incomplete: list[str] = []
    formula = data.get("formula") if isinstance(data.get("formula"), dict) else {}
    for field in ("expected_remaining", "half_life", "fracture_pressure"):
        if not str(formula.get(field) or "").strip():
            incomplete.append(f"CMD.N1 formula is missing {field}")
    thresholds = data.get("fracture_pressure_thresholds")
    if not isinstance(thresholds, list) or not thresholds:
        incomplete.append("CMD.N1 fracture pressure thresholds are missing")
    return incomplete


def _artifact_incomplete_status(key: str, status: str) -> str:
    if key == "review_pack" and status == "review_pack_incomplete":
        return "review pack is incomplete"
    return ""


def _build_artifact_coverage(
    artifact_data: dict[str, dict[str, Any] | None],
    artifact_paths: dict[str, str | Path],
    input_blockers: dict[str, list[str]],
    input_incomplete: dict[str, list[str]],
) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    blockers: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []

    for spec in ARTIFACT_SPECS:
        key = spec["key"]
        data = artifact_data.get(key)
        path = artifact_paths[key]
        blockers += input_blockers.get(key, [])
        incomplete += input_incomplete.get(key, [])
        report_kind = data.get("report_kind", "") if isinstance(data, dict) else ""
        status = _artifact_status(data, spec) if isinstance(data, dict) else ""
        kind_ok = report_kind == spec["report_kind"] if isinstance(data, dict) else False
        if isinstance(data, dict) and not kind_ok:
            incomplete.append(
                f"{key} artifact report_kind expected {spec['report_kind']} but found {report_kind or '(missing)'}"
            )
        if key == "boss_half_life":
            incomplete += _n1_formula_incomplete(data)
        if isinstance(data, dict):
            incomplete_status = _artifact_incomplete_status(key, status)
            if incomplete_status:
                incomplete.append(incomplete_status)
            warnings += _collect_artifact_warnings(key, data)
            if (
                status.endswith("_with_warnings")
                or status.endswith("with_warnings")
                or "incomplete" in status
                or "blocked" in status
            ):
                warnings.append(f"{key} artifact status requires review: {status}")
        rows.append(
            {
                "key": key,
                "phase_id": spec["phase_id"],
                "title": spec["title"],
                "path": str(path),
                "path_safe": not _path_has_traversal(str(path)),
                "present": isinstance(data, dict),
                "report_kind": report_kind,
                "expected_report_kind": spec["report_kind"],
                "report_kind_ok": kind_ok,
                "status": status,
            }
        )

    all_present = all(row["present"] for row in rows)
    all_kind_ok = all(row["report_kind_ok"] for row in rows)
    all_paths_safe = all(row["path_safe"] for row in rows)
    return (
        {
            "artifact_checks": rows,
            "all_required_artifacts_present": all_present,
            "all_required_artifact_kinds_match": all_kind_ok,
            "all_artifact_paths_safe": all_paths_safe,
        },
        _dedupe(blockers),
        _dedupe(incomplete),
        _dedupe(warnings),
    )


def _looks_like_model_id(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(text == token or text.startswith(token) or f"/{token}" in text for token in MODEL_ID_TOKENS)


def _truthy_marker(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def _scan_forbidden_capabilities(value: Any, label: str, path: str = "") -> tuple[list[str], dict[str, bool]]:
    blockers: list[str] = []
    flags = {
        "executable_worker_binding": False,
        "model_authority_binding": False,
        "auto_flag": False,
        "worker_launch_path": False,
        "patch_apply_path": False,
        "validation_or_benchmark_execution_path": False,
        "route_behavior_change": False,
        "web_route_behavior_change": False,
        "database_write": False,
        "network_subprocess_or_tool_invocation": False,
        "execution_capability": False,
    }
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            low_key = key_text.lower()
            current = f"{path}.{key_text}" if path else key_text
            if low_key in EXECUTABLE_WORKER_KEYS and _truthy_marker(item):
                flags["executable_worker_binding"] = True
                blockers.append(f"{label} defines executable worker binding at {current}")
            if low_key in AUTO_FLAG_KEYS and item is True:
                flags["auto_flag"] = True
                blockers.append(f"{label} enables hidden auto flag at {current}")
            if low_key in MODEL_AUTHORITY_KEYS and str(item or "").strip():
                flags["model_authority_binding"] = True
                blockers.append(f"{label} treats a model name as authority at {current}")
            if low_key in MODEL_ID_KEYS and _looks_like_model_id(item):
                flags["model_authority_binding"] = True
                blockers.append(f"{label} binds model ID as authority at {current}")
            if low_key in EXECUTION_MARKER_REASONS and _truthy_marker(item):
                reason = EXECUTION_MARKER_REASONS[low_key]
                blockers.append(f"{label} {reason} at {current}")
                if "worker launch" in reason:
                    flags["worker_launch_path"] = True
                elif "patch apply" in reason:
                    flags["patch_apply_path"] = True
                elif "validation" in reason or "benchmark" in reason:
                    flags["validation_or_benchmark_execution_path"] = True
                elif "web route" in reason:
                    flags["web_route_behavior_change"] = True
                elif "route" in reason or "routing" in reason:
                    flags["route_behavior_change"] = True
                elif "database" in reason:
                    flags["database_write"] = True
                elif "network" in reason or "subprocess" in reason or "tool" in reason or "MCP" in reason:
                    flags["network_subprocess_or_tool_invocation"] = True
                elif "execution capability" in reason:
                    flags["execution_capability"] = True
            if (low_key.endswith("_performed") or low_key.endswith("_changed") or low_key.endswith("_added")) and item is True:
                blockers.append(f"{label} reports forbidden guardrail action at {current}")
                if "worker_launch" in low_key:
                    flags["worker_launch_path"] = True
                elif "patch" in low_key:
                    flags["patch_apply_path"] = True
                elif "validation" in low_key or "benchmark" in low_key:
                    flags["validation_or_benchmark_execution_path"] = True
                elif "web_route" in low_key:
                    flags["web_route_behavior_change"] = True
                elif "route" in low_key or "routing" in low_key:
                    flags["route_behavior_change"] = True
                elif "database" in low_key:
                    flags["database_write"] = True
                elif "network" in low_key or "subprocess" in low_key or "tool" in low_key or "mcp" in low_key:
                    flags["network_subprocess_or_tool_invocation"] = True
                else:
                    flags["execution_capability"] = True
            child_blockers, child_flags = _scan_forbidden_capabilities(item, label, current)
            blockers += child_blockers
            for flag, detected in child_flags.items():
                flags[flag] = flags[flag] or detected
    elif isinstance(value, list):
        for index, item in enumerate(value):
            current = f"{path}[{index}]" if path else f"[{index}]"
            child_blockers, child_flags = _scan_forbidden_capabilities(item, label, current)
            blockers += child_blockers
            for flag, detected in child_flags.items():
                flags[flag] = flags[flag] or detected
    return blockers, flags


def _combine_scan_flags(scan_rows: list[dict[str, Any]]) -> dict[str, bool]:
    flags = {
        "executable_worker_binding": False,
        "model_authority_binding": False,
        "auto_flag": False,
        "worker_launch_path": False,
        "patch_apply_path": False,
        "validation_or_benchmark_execution_path": False,
        "route_behavior_change": False,
        "web_route_behavior_change": False,
        "database_write": False,
        "network_subprocess_or_tool_invocation": False,
        "execution_capability": False,
    }
    for row in scan_rows:
        row_flags = row.get("detected_flags") if isinstance(row.get("detected_flags"), dict) else {}
        for flag in flags:
            flags[flag] = flags[flag] or bool(row_flags.get(flag))
    return flags


def _build_execution_checks(artifact_data: dict[str, dict[str, Any] | None]) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    scan_rows: list[dict[str, Any]] = []
    for key, data in artifact_data.items():
        if not isinstance(data, dict):
            continue
        row_blockers, detected = _scan_forbidden_capabilities(data, key)
        blockers += row_blockers
        scan_rows.append(
            {
                "artifact": key,
                "detected_flags": detected,
                "blocked_reason_count": len(row_blockers),
            }
        )
    flags = _combine_scan_flags(scan_rows)
    execution_detected = any(flags.values())
    checks = {
        "scan_results": scan_rows,
        "advisory_roles_are_labels_only": not flags["executable_worker_binding"],
        "no_executable_worker_binding": not flags["executable_worker_binding"],
        "no_real_model_binding": not flags["model_authority_binding"],
        "no_model_authority": not flags["model_authority_binding"],
        "no_auto_run_apply_merge": not flags["auto_flag"],
        "no_worker_launch_path": not flags["worker_launch_path"],
        "no_patch_apply_path": not flags["patch_apply_path"],
        "no_validation_or_benchmark_execution_path": not flags["validation_or_benchmark_execution_path"],
        "no_routing_behavior_change": not flags["route_behavior_change"],
        "no_web_route_behavior_change": not flags["web_route_behavior_change"],
        "no_database_write": not flags["database_write"],
        "no_network_subprocess_tool_invocation": not flags["network_subprocess_or_tool_invocation"],
        "execution_capability_detected": execution_detected,
    }
    return checks, _dedupe(blockers)


def _row_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("sub_boss_id") or "").strip() for row in rows if str(row.get("sub_boss_id") or "").strip()}


def _build_alignment_checks(artifact_data: dict[str, dict[str, Any] | None]) -> tuple[dict[str, Any], list[str], list[str]]:
    incomplete: list[str] = []
    warnings: list[str] = []
    tree = artifact_data.get("fracture_tree") if isinstance(artifact_data.get("fracture_tree"), dict) else {}
    preflight = artifact_data.get("preflight") if isinstance(artifact_data.get("preflight"), dict) else {}
    assignment = artifact_data.get("assignment") if isinstance(artifact_data.get("assignment"), dict) else {}
    review = artifact_data.get("review_pack") if isinstance(artifact_data.get("review_pack"), dict) else {}

    tree_id = str(tree.get("tree_id") or "")
    boss_id = str(tree.get("boss_id") or "")
    identity_rows = {
        "fracture_tree": {"tree_id": tree_id, "boss_id": boss_id},
        "preflight": {"tree_id": str(preflight.get("tree_id") or ""), "boss_id": str(preflight.get("boss_id") or "")},
        "assignment": {"tree_id": str(assignment.get("tree_id") or ""), "boss_id": str(assignment.get("boss_id") or "")},
        "review_pack": {"tree_id": str(review.get("tree_id") or ""), "boss_id": str(review.get("boss_id") or "")},
    }
    for key, identity in identity_rows.items():
        if key == "fracture_tree":
            continue
        if tree_id and identity["tree_id"] and identity["tree_id"] != tree_id:
            incomplete.append(f"{key} tree_id does not align with fracture tree")
        if boss_id and identity["boss_id"] and identity["boss_id"] != boss_id:
            incomplete.append(f"{key} boss_id does not align with fracture tree")

    sub_bosses = _dict_rows(tree.get("sub_bosses"))
    eligible_ids = {
        str(row.get("sub_boss_id") or "").strip()
        for row in sub_bosses
        if str(row.get("sub_boss_id") or "").strip()
        and str(row.get("status") or "") in {"ready_for_preflight", "proposed"}
    }
    preflight_ids = _row_ids(_dict_rows(preflight.get("per_sub_boss_findings")))
    assignment_ids = _row_ids(_dict_rows(assignment.get("assignments"))) | _row_ids(_dict_rows(assignment.get("unassigned_sub_bosses")))
    review_ids = _row_ids(_dict_rows(review.get("per_sub_boss_review")))

    if not eligible_ids:
        warnings.append("fracture tree has no eligible sub-bosses to align")
    for sub_id in sorted(eligible_ids - preflight_ids):
        incomplete.append(f"sub_boss {sub_id} missing preflight coverage")
    for sub_id in sorted(eligible_ids - assignment_ids):
        incomplete.append(f"sub_boss {sub_id} missing assignment coverage")
    for sub_id in sorted(eligible_ids - review_ids):
        incomplete.append(f"sub_boss {sub_id} missing review pack coverage")

    align_ok = not incomplete and all(isinstance(artifact_data.get(key), dict) for key in ("fracture_tree", "preflight", "assignment", "review_pack"))
    return (
        {
            "tree_id": tree_id,
            "boss_id": boss_id,
            "identity_rows": identity_rows,
            "eligible_sub_boss_ids": sorted(eligible_ids),
            "preflight_coverage_ids": sorted(preflight_ids),
            "assignment_coverage_ids": sorted(assignment_ids),
            "review_pack_coverage_ids": sorted(review_ids),
            "review_pack_aligns_with_tree_preflight_assignment": align_ok,
        },
        _dedupe(incomplete),
        _dedupe(warnings),
    )


def _human_approval_boundary(artifact_data: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    preflight = artifact_data.get("preflight") if isinstance(artifact_data.get("preflight"), dict) else {}
    assignment = artifact_data.get("assignment") if isinstance(artifact_data.get("assignment"), dict) else {}
    review = artifact_data.get("review_pack") if isinstance(artifact_data.get("review_pack"), dict) else {}
    policy = preflight.get("human_approval_policy") if isinstance(preflight.get("human_approval_policy"), dict) else {}
    boundary = assignment.get("human_approval_boundary") if isinstance(assignment.get("human_approval_boundary"), dict) else {}
    checklist_text = " ".join(_strings(review.get("human_review_checklist"))).lower()
    required_before_worker_launch = bool(
        policy.get("required_before_worker_launch") or boundary.get("required_before_worker_launch")
    )
    required_before_patch_apply = bool(
        policy.get("required_before_patch_apply") or boundary.get("required_before_patch_apply")
    )
    required_before_file_mutation = bool(
        policy.get("required_before_file_mutation") or boundary.get("required_before_file_mutation")
    )
    validation_human_triggered = "validation" in checklist_text and (
        "human-triggered" in checklist_text or "human triggered" in checklist_text
    )
    benchmark_human_triggered = "benchmark" in checklist_text and (
        "human-triggered" in checklist_text or "human triggered" in checklist_text
    )
    assignment_authority = str(boundary.get("assignment_authority") or policy.get("assignment_authority") or "human_only")
    explicit = (
        required_before_worker_launch
        and required_before_patch_apply
        and (required_before_file_mutation or required_before_patch_apply)
        and validation_human_triggered
        and benchmark_human_triggered
        and assignment_authority == "human_only"
    )
    return {
        "required_before_worker_launch": required_before_worker_launch,
        "required_before_patch_apply": required_before_patch_apply,
        "required_before_file_mutation": required_before_file_mutation,
        "validation_remains_human_triggered": validation_human_triggered,
        "benchmark_remains_human_triggered": benchmark_human_triggered,
        "assignment_authority": assignment_authority,
        "human_approval_boundaries_explicit": explicit,
    }


def _planning_capability_summary(artifact_data: dict[str, dict[str, Any] | None], execution_detected: bool) -> dict[str, bool]:
    n1 = artifact_data.get("boss_half_life") if isinstance(artifact_data.get("boss_half_life"), dict) else None
    n1_formula_ok = not _n1_formula_incomplete(n1)
    return {
        "can_define_half_life_stagnation_math": bool(n1 and n1_formula_ok),
        "can_report_manual_boss_fracture": isinstance(artifact_data.get("manual_fracture"), dict),
        "can_store_and_validate_fracture_trees": isinstance(artifact_data.get("fracture_tree"), dict),
        "can_preflight_sub_bosses": isinstance(artifact_data.get("preflight"), dict),
        "can_assign_advisory_role_labels": isinstance(artifact_data.get("assignment"), dict),
        "can_produce_assignment_review_pack": isinstance(artifact_data.get("review_pack"), dict),
        "can_execute_anything": bool(execution_detected),
    }


def _status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_FROZEN_WARNINGS
    return STATUS_FROZEN


def _final_verdict(status: str) -> str:
    if status == STATUS_BLOCKED:
        return "Commander planning branch cannot be frozen until blockers are resolved."
    if status == STATUS_INCOMPLETE:
        return "Commander planning branch is missing required planning evidence."
    if status == STATUS_FROZEN_WARNINGS:
        return "Commander planning branch is safe and complete enough to freeze, with warnings for human review."
    return "Commander planning branch is frozen as planning-only evidence."


def build_commander_planning_branch_checkpoint(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    boss_half_life_path: str | Path = DEFAULT_BOSS_HALF_LIFE_PATH,
    manual_fracture_path: str | Path = DEFAULT_MANUAL_FRACTURE_PATH,
    fracture_tree_path: str | Path = DEFAULT_FRACTURE_TREE_PATH,
    preflight_path: str | Path = DEFAULT_PREFLIGHT_PATH,
    assignment_path: str | Path = DEFAULT_ASSIGNMENT_PATH,
    review_pack_path: str | Path = DEFAULT_REVIEW_PACK_PATH,
) -> dict[str, Any]:
    """Build the deterministic CMD.CLOSE checkpoint report data."""
    registry_data, registry_blockers = _read_registry(registry_path)
    phase_completion, phase_blockers = _build_phase_completion(registry_data, registry_blockers)

    artifact_paths: dict[str, str | Path] = {
        "boss_half_life": boss_half_life_path,
        "manual_fracture": manual_fracture_path,
        "fracture_tree": fracture_tree_path,
        "preflight": preflight_path,
        "assignment": assignment_path,
        "review_pack": review_pack_path,
    }
    artifact_data: dict[str, dict[str, Any] | None] = {}
    input_blockers: dict[str, list[str]] = {}
    input_incomplete: dict[str, list[str]] = {}
    for key, path in artifact_paths.items():
        data, blockers, incomplete = _load_json_object(path, key)
        artifact_data[key] = data
        input_blockers[key] = blockers
        input_incomplete[key] = incomplete

    artifact_coverage, artifact_blockers, artifact_incomplete, artifact_warnings = _build_artifact_coverage(
        artifact_data,
        artifact_paths,
        input_blockers,
        input_incomplete,
    )
    alignment, alignment_incomplete, alignment_warnings = _build_alignment_checks(artifact_data)
    execution_checks, execution_blockers = _build_execution_checks(artifact_data)
    human_boundary = _human_approval_boundary(artifact_data)

    blockers = _dedupe(phase_blockers + artifact_blockers + execution_blockers)
    incomplete = _dedupe(artifact_incomplete + alignment_incomplete)
    warnings = _dedupe(artifact_warnings + alignment_warnings)
    if not human_boundary["human_approval_boundaries_explicit"] and not blockers and not incomplete:
        warnings.append("human approval boundaries are not fully explicit across Commander planning artifacts")

    status = _status(blockers, incomplete, warnings)
    planning = _planning_capability_summary(artifact_data, execution_checks["execution_capability_detected"])
    safety = {
        "required_phases_complete": phase_completion["all_required_phases_complete"],
        "required_artifacts_present": artifact_coverage["all_required_artifacts_present"],
        "artifacts_path_safe": artifact_coverage["all_artifact_paths_safe"],
        "review_pack_aligns": alignment["review_pack_aligns_with_tree_preflight_assignment"],
        "human_approval_boundaries_explicit": human_boundary["human_approval_boundaries_explicit"],
        "commander_branch_remains_planning_only": not execution_checks["execution_capability_detected"],
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": COMMANDER_PLANNING_BRANCH_CHECKPOINT_GUARDRAIL_NOTE,
        "checkpoint_id": "cmd-close-commander-planning-branch-checkpoint",
        "checkpoint_status": status,
        "checkpoint_statuses": list(CHECKPOINT_STATUSES),
        "phase_completion": phase_completion,
        "artifact_coverage": artifact_coverage,
        "review_pack_alignment": alignment,
        "planning_capability_summary": planning,
        "safety_boundary_verification": safety,
        "execution_prohibition_checks": execution_checks,
        "human_approval_boundary": human_boundary,
        "warnings": _dedupe(warnings),
        "incomplete_reasons": _dedupe(incomplete),
        "blocked_reasons": _dedupe(blockers),
        "final_verdict": _final_verdict(status),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_commander_planning_branch_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render a CMD.CLOSE checkpoint report as Markdown."""
    phase_completion = report.get("phase_completion") if isinstance(report.get("phase_completion"), dict) else {}
    artifact_coverage = report.get("artifact_coverage") if isinstance(report.get("artifact_coverage"), dict) else {}
    planning = report.get("planning_capability_summary") if isinstance(report.get("planning_capability_summary"), dict) else {}
    safety = report.get("safety_boundary_verification") if isinstance(report.get("safety_boundary_verification"), dict) else {}
    execution = report.get("execution_prohibition_checks") if isinstance(report.get("execution_prohibition_checks"), dict) else {}
    human = report.get("human_approval_boundary") if isinstance(report.get("human_approval_boundary"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}

    lines: list[str] = [
        "# Commander Planning Branch Checkpoint",
        "",
        f"> {report.get('guardrail_note', COMMANDER_PLANNING_BRANCH_CHECKPOINT_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.CLOSE freezes the Commander planning branch. It verifies planning artifacts and safety boundaries; it runs nothing and changes no source artifact, route, worker, model, validation, benchmark, patch, network, database, or routing behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Checkpoint id:** `{_md(report.get('checkpoint_id', ''))}`",
        f"- **Checkpoint status:** `{_md(report.get('checkpoint_status', ''))}`",
        f"- **Final verdict:** {_md(report.get('final_verdict', ''))}",
        "",
        "## Phase Completion",
        "",
        "| Phase | Present | Status | Complete | Guardrails OK |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in phase_completion.get("phase_checks") or []:
        lines.append(
            "| {phase} | {present} | {status} | {complete} | {guardrails} |".format(
                phase=_md(row.get("phase_id", "")),
                present=_lower(row.get("present")),
                status=_md(row.get("status", "")),
                complete=_lower(row.get("complete")),
                guardrails=_lower(row.get("guardrails_ok")),
            )
        )

    lines += [
        "",
        "## Artifact Coverage",
        "",
        "| Artifact | Phase | Path | Present | Kind OK | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in artifact_coverage.get("artifact_checks") or []:
        lines.append(
            "| {artifact} | {phase} | {path} | {present} | {kind} | {status} |".format(
                artifact=_md(row.get("key", "")),
                phase=_md(row.get("phase_id", "")),
                path=_md(row.get("path", "")),
                present=_lower(row.get("present")),
                kind=_lower(row.get("report_kind_ok")),
                status=_md(row.get("status", "")),
            )
        )

    lines += [
        "",
        "## Planning Capability Summary",
        "",
    ]
    for key in sorted(planning):
        lines.append(f"- `{_md(key)}`: {_lower(planning[key])}")

    lines += [
        "",
        "## Safety Boundary Verification",
        "",
    ]
    for key in sorted(safety):
        lines.append(f"- `{_md(key)}`: {_lower(safety[key])}")

    lines += [
        "",
        "## Execution-Prohibition Checks",
        "",
    ]
    for key in (
        "advisory_roles_are_labels_only",
        "no_executable_worker_binding",
        "no_real_model_binding",
        "no_model_authority",
        "no_auto_run_apply_merge",
        "no_worker_launch_path",
        "no_patch_apply_path",
        "no_validation_or_benchmark_execution_path",
        "no_routing_behavior_change",
        "no_web_route_behavior_change",
        "no_database_write",
        "no_network_subprocess_tool_invocation",
        "execution_capability_detected",
    ):
        lines.append(f"- `{_md(key)}`: {_lower(execution.get(key))}")

    lines += [
        "",
        "## Human Approval Boundary",
        "",
    ]
    for key in sorted(human):
        value = human[key]
        if isinstance(value, bool):
            lines.append(f"- `{_md(key)}`: {_lower(value)}")
        else:
            lines.append(f"- `{_md(key)}`: `{_md(value)}`")

    lines += ["", "## Warnings", ""]
    _render_list(lines, list(report.get("warnings") or []))

    lines += ["## Blocked Reasons", ""]
    _render_list(lines, list(report.get("blocked_reasons") or []))

    lines += ["## Final Verdict", ""]
    lines.append(f"- {_md(report.get('final_verdict', ''))}")
    lines.append("")

    lines += [
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        f"- **Alternative:** {_md(next_phase.get('alternative', ''))}",
        "",
        "## Boundaries / Guardrails",
        "",
    ]
    for boundary in report.get("boundaries") or []:
        lines.append(f"- {_md(boundary)}")
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {_lower(guardrails[key])}")
    lines.append("")
    return "\n".join(lines)


def write_commander_planning_branch_checkpoint(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    boss_half_life_path: str | Path = DEFAULT_BOSS_HALF_LIFE_PATH,
    manual_fracture_path: str | Path = DEFAULT_MANUAL_FRACTURE_PATH,
    fracture_tree_path: str | Path = DEFAULT_FRACTURE_TREE_PATH,
    preflight_path: str | Path = DEFAULT_PREFLIGHT_PATH,
    assignment_path: str | Path = DEFAULT_ASSIGNMENT_PATH,
    review_pack_path: str | Path = DEFAULT_REVIEW_PACK_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Build and write CMD.CLOSE JSON + Markdown checkpoint artifacts."""
    report = build_commander_planning_branch_checkpoint(
        registry_path=registry_path,
        boss_half_life_path=boss_half_life_path,
        manual_fracture_path=manual_fracture_path,
        fracture_tree_path=fracture_tree_path,
        preflight_path=preflight_path,
        assignment_path=assignment_path,
        review_pack_path=review_pack_path,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_commander_planning_branch_checkpoint_markdown(report), encoding="utf-8")
    return {
        "ok": report.get("checkpoint_status") in {STATUS_FROZEN, STATUS_FROZEN_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
