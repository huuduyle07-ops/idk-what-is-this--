"""CMD.N4 - Commander Preflight Contract (report-only).

Defines and evaluates the safety/readiness contract for registered CMD.N3
sub-bosses before any Commander routing, assignment, or execution behavior
exists. CMD.N4 writes deterministic preflight artifacts only. It does not
execute sub-bosses, assign real workers, call models, run validation, run
benchmarks, launch Commander mode, mutate eligibility, change routing, apply
patches, invoke MCP tools, execute Dream actions, apply Replay janitor actions,
use Docker/subprocess, contact networks, write databases, or change auth policy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.commander_fracture_tree_registry import GUARDRAIL_FALSE_FLAGS as CMD_N3_GUARDRAIL_FALSE_FLAGS


REPORT_KIND = "commander_preflight_contract"
JSON_NAME = "commander_preflight_contract.json"
MD_NAME = "commander_preflight_contract.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "commander" / "preflight_contract"
INVALID_TREE_ID_DIR = "invalid_tree_id"

PREFLIGHT_STATUSES: tuple[str, ...] = (
    "preflight_ready",
    "preflight_ready_with_warnings",
    "preflight_incomplete",
    "preflight_blocked",
)

EVALUABLE_SUB_BOSS_STATUSES: tuple[str, ...] = ("ready_for_preflight", "proposed")
READY_TREE_STATUSES: tuple[str, ...] = ("registry_ready", "registry_ready_with_warnings")
RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "unknown")

MAX_ALLOWED_FILES = 25
HIGH_COMPLEXITY_THRESHOLD = 80

DEFAULT_HUMAN_APPROVAL_POLICY = {
    "required_before_patch_apply": True,
    "required_before_worker_launch": True,
    "required_before_file_mutation": True,
}

DEFAULT_MUTATION_POLICY = {
    "patch_proposal_only": True,
    "direct_write_allowed": False,
    "apply_allowed_by_commander": False,
}

DEFAULT_VALIDATION_POLICY = {
    "may_recommend_validation": True,
    "may_run_validation": False,
    "benchmark_run_allowed": False,
}

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = tuple(
    dict.fromkeys(
        list(CMD_N3_GUARDRAIL_FALSE_FLAGS)
        + [
            "preflight_execution_performed",
            "sub_boss_execution_performed",
            "real_worker_assignment_performed",
            "validation_run_performed",
            "benchmark_run_performed",
            "execution_eligibility_mutation_performed",
        ]
    )
)

COMMANDER_PREFLIGHT_CONTRACT_GUARDRAIL_NOTE = (
    "Commander Preflight Contract is report-only: it evaluates deterministic "
    "manual CMD.N3 registry data and writes preflight artifacts only. It does "
    "not execute sub-bosses, assign real workers, call models, launch Commander "
    "mode, change routing, mutate execution eligibility, apply patches, run "
    "validation, run benchmarks, invoke MCP tools, execute Dream actions, apply "
    "Replay janitor actions, use Docker/subprocess, contact networks, write "
    "databases, change auth policy, or change route behavior."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "CMD.N5",
    "title": "Commander Manual Assignment Plan",
    "reason": (
        "After report-only preflight readiness exists, the next safe step is "
        "manual/advisory assignment planning: which advisory role should review "
        "which sub-boss, still with no worker launch or routing behavior."
    ),
    "alternative": "CMD.N5 - Commander Preflight UI Preview",
}

EXECUTABLE_WORKER_KEYS: tuple[str, ...] = (
    "worker_binding",
    "worker_id",
    "worker",
    "assigned_worker",
    "executable_worker",
    "execution_worker",
    "launch_worker",
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


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _round_metric(value: float | None, places: int = 6) -> float | int | None:
    if value is None:
        return None
    rounded = round(float(value), places)
    if float(rounded).is_integer():
        return int(rounded)
    return rounded


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or abs(number) == float("inf"):
        return None
    return number


def _as_positive_float(value: Any) -> float | None:
    number = _as_float(value)
    if number is None or number <= 0:
        return None
    return number


def _as_positive_int(value: Any) -> int | None:
    number = _as_float(value)
    if number is None or number <= 0 or not float(number).is_integer():
        return None
    return int(number)


def _safe_identifier(value: Any, field: str) -> tuple[str, list[str]]:
    text = str(value or "").strip()
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    blockers: list[str] = []
    if not text:
        blockers.append(f"{field} must be a non-empty path-safe identifier")
    if text in {".", ".."} or ".." in text:
        blockers.append(f"{field} must not contain path traversal segments")
    if "/" in text or "\\" in text:
        blockers.append(f"{field} must not contain path separators")
    if text.startswith("."):
        blockers.append(f"{field} must not start with a dot")
    if any(ch not in allowed for ch in text):
        blockers.append(f"{field} may contain only letters, numbers, dot, dash, and underscore")
    return text, sorted(set(blockers))


def _split_segments(value: str) -> list[str]:
    return [segment for segment in value.replace("\\", "/").split("/") if segment]


def _path_has_traversal(value: str) -> bool:
    return any(segment == ".." for segment in _split_segments(value))


def _input_path_blockers(path: str | Path | None, label: str) -> list[str]:
    if path is None or str(path).strip() == "":
        return [f"{label} path is required"]
    text = str(path).strip()
    if _path_has_traversal(text):
        return [f"{label} path must not contain traversal segments"]
    return []


def _normalize_path_list(value: Any, *, field: str, sub_boss_id: str) -> tuple[list[str], list[str], list[str]]:
    blockers: list[str] = []
    incomplete: list[str] = []
    normalized: list[str] = []
    if not isinstance(value, list):
        return [], [], [f"sub_boss {sub_boss_id} {field} must be a list of path strings"]
    for index, item in enumerate(value):
        if not isinstance(item, str):
            blockers.append(f"sub_boss {sub_boss_id} {field}[{index}] must be a string")
            continue
        text = item.strip().replace("\\", "/")
        if not text:
            blockers.append(f"sub_boss {sub_boss_id} {field}[{index}] must not be empty")
            continue
        segments = _split_segments(text)
        if text.startswith("/") or (segments and ":" in segments[0]) or _path_has_traversal(text):
            blockers.append(f"sub_boss {sub_boss_id} {field} contains unsafe path: {item}")
            continue
        normalized.append(text)
    if field == "allowed_files":
        if not normalized:
            incomplete.append(f"sub_boss {sub_boss_id} allowed_files must bound file scope")
        elif len(normalized) > MAX_ALLOWED_FILES:
            incomplete.append(
                f"sub_boss {sub_boss_id} allowed_files exceeds maximum bounded scope of {MAX_ALLOWED_FILES}"
            )
    return normalized, blockers, incomplete


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _policy(value: Any, defaults: dict[str, bool], *, name: str, sub_boss_id: str) -> tuple[dict[str, bool], list[str]]:
    if not isinstance(value, dict):
        return dict(defaults), [f"sub_boss {sub_boss_id} {name} defaulted"]
    normalized = dict(defaults)
    warnings: list[str] = []
    for key, default in defaults.items():
        if key not in value:
            warnings.append(f"sub_boss {sub_boss_id} {name}.{key} defaulted")
            continue
        normalized[key] = bool(value[key])
    return normalized, warnings


def _find_true_flags(value: Any, keys: tuple[str, ...], path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}" if path else str(key)
            if str(key) in keys and item is True:
                found.append(current)
            found += _find_true_flags(item, keys, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            current = f"{path}[{index}]" if path else f"[{index}]"
            found += _find_true_flags(item, keys, current)
    return found


def _find_truthy_keys(value: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if value.get(key)]


def _model_authority_blockers(sub: dict[str, Any], sub_boss_id: str) -> list[str]:
    blockers: list[str] = []
    for key in MODEL_AUTHORITY_KEYS:
        if str(sub.get(key) or "").strip():
            blockers.append(f"sub_boss {sub_boss_id} model name is treated as authority via {key}")
    authority = str(sub.get("authority") or sub.get("execution_authority") or "").strip().lower()
    if authority and any(token in authority for token in ("gpt", "claude", "model", "llm")):
        blockers.append(f"sub_boss {sub_boss_id} model name is treated as authority")
    return blockers


def read_json_input(path: str | Path | None, label: str = "tree") -> tuple[dict[str, Any] | None, list[str]]:
    """Read a JSON input and return blockers instead of raising."""
    blockers = _input_path_blockers(path, label)
    if blockers:
        return None, blockers
    source = Path(str(path))
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"{label} could not be read: {exc}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"{label} must contain valid JSON: {exc.msg}"]
    if not isinstance(data, dict):
        return None, [f"{label} must contain a JSON object"]
    return data, []


def _tree_identity(tree_data: dict[str, Any] | None) -> tuple[str, str, str]:
    tree = tree_data if isinstance(tree_data, dict) else {}
    return (
        str(tree.get("tree_id") or "").strip(),
        str(tree.get("boss_id") or "").strip(),
        str(tree.get("title") or "").strip(),
    )


def _has_dependency_cycle(sub_bosses: list[dict[str, Any]]) -> bool:
    graph = {str(sub.get("sub_boss_id")): list(sub.get("dependencies") or []) for sub in sub_bosses}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in graph.get(node, []):
            if dep in graph and visit(dep):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def _dependency_findings(
    *,
    sub: dict[str, Any],
    known_subs: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    readiness: list[dict[str, Any]] = []
    warnings: list[str] = []
    incomplete: list[str] = []
    blockers: list[str] = []
    sub_id = str(sub.get("sub_boss_id") or "").strip()
    allow_pending = bool(sub.get("allow_pending_dependencies")) or bool(
        isinstance(sub.get("dependency_policy"), dict)
        and sub.get("dependency_policy", {}).get("allow_pending_dependencies")
    )
    for dep in _strings(sub.get("dependencies")):
        dep_sub = known_subs.get(dep)
        if dep_sub is None:
            blockers.append(f"sub_boss {sub_id} has missing dependency: {dep}")
            readiness.append({"dependency": dep, "status": "missing", "ready": False})
            continue
        dep_status = str(dep_sub.get("status") or "")
        ready = dep_status == "completed"
        readiness.append({"dependency": dep, "status": dep_status, "ready": ready})
        if not ready:
            message = f"sub_boss {sub_id} dependency {dep} is pending with status {dep_status or '(none)'}"
            if allow_pending:
                warnings.append(f"pending dependency allowed: {message}; explicitly allowed as pending")
            else:
                incomplete.append(message)
    return readiness, warnings, incomplete, blockers


def _evaluate_sub_boss(
    *,
    sub: dict[str, Any],
    root_boss_id: str,
    known_subs: dict[str, dict[str, Any]],
    parent_tree_status: str,
) -> dict[str, Any]:
    raw_sub_id = str(sub.get("sub_boss_id") or "").strip()
    sub_id, id_blockers = _safe_identifier(raw_sub_id, f"sub_boss_id {raw_sub_id}")
    warnings: list[str] = []
    incomplete: list[str] = []
    blockers: list[str] = list(id_blockers)

    if parent_tree_status == "blocked":
        blockers.append("parent tree validation_status is blocked")
    elif parent_tree_status not in READY_TREE_STATUSES:
        incomplete.append(f"parent tree validation_status is {parent_tree_status or '(missing)'}")

    status = str(sub.get("status") or "").strip()
    if status not in EVALUABLE_SUB_BOSS_STATUSES:
        incomplete.append(
            f"sub_boss {sub_id} status must be ready_for_preflight or proposed before preflight"
        )

    valid_parent_ids = {root_boss_id, *known_subs.keys()}
    parent_id = str(sub.get("parent_boss_id") or "").strip()
    if parent_id not in valid_parent_ids:
        blockers.append(f"sub_boss {sub_id} parent_boss_id does not reference a known boss")

    allowed_files, allowed_blockers, allowed_incomplete = _normalize_path_list(
        sub.get("allowed_files"), field="allowed_files", sub_boss_id=sub_id
    )
    forbidden_files, forbidden_blockers, _ = _normalize_path_list(
        sub.get("forbidden_files"), field="forbidden_files", sub_boss_id=sub_id
    )
    blockers += allowed_blockers + forbidden_blockers
    incomplete += allowed_incomplete

    conflicts = sorted(set(allowed_files) & set(forbidden_files))
    if conflicts:
        blockers.append(
            f"sub_boss {sub_id} allowed_files and forbidden_files conflict: {', '.join(conflicts)}"
        )

    evidence = _strings(sub.get("evidence_required"))
    if not evidence:
        incomplete.append(f"sub_boss {sub_id} evidence_required must be non-empty")
    rollback_boundary = str(sub.get("rollback_boundary") or "").strip()
    if not rollback_boundary:
        incomplete.append(f"sub_boss {sub_id} rollback_boundary must be non-empty")
    completion_signal = str(sub.get("completion_signal") or "").strip()
    if not completion_signal:
        incomplete.append(f"sub_boss {sub_id} completion_signal must be non-empty")

    expected_complexity = _as_positive_float(sub.get("expected_complexity"))
    if expected_complexity is None:
        incomplete.append(f"sub_boss {sub_id} expected_complexity must be positive")
    elif expected_complexity >= HIGH_COMPLEXITY_THRESHOLD:
        warnings.append(f"sub_boss {sub_id} expected_complexity is high")

    attempt_budget = _as_positive_int(sub.get("attempt_budget"))
    if attempt_budget is None:
        incomplete.append(f"sub_boss {sub_id} attempt_budget must be a positive integer")

    worker_keys = _find_truthy_keys(sub, EXECUTABLE_WORKER_KEYS)
    if worker_keys:
        blockers.append(f"sub_boss {sub_id} has executable worker binding: {', '.join(worker_keys)}")
    assigned_role_binding = str(sub.get("assigned_role_binding") or "advisory_label_only").strip()
    if assigned_role_binding != "advisory_label_only":
        blockers.append(f"sub_boss {sub_id} has executable worker binding via assigned_role_binding")

    auto_flags = _find_true_flags(sub, AUTO_FLAG_KEYS)
    for flag in auto_flags:
        blockers.append(f"sub_boss {sub_id} hidden auto flag is enabled: {flag}")
    blockers += _model_authority_blockers(sub, sub_id)

    risk_level = str(sub.get("risk_level") or "unknown").strip()
    if risk_level not in RISK_LEVELS:
        warnings.append(f"sub_boss {sub_id} risk_level {risk_level} is not recognized; defaulted to unknown")
        risk_level = "unknown"
    if risk_level == "unknown":
        warnings.append(f"sub_boss {sub_id} risk_level defaulted to unknown")

    human_policy, policy_warnings = _policy(
        sub.get("human_approval_policy"),
        DEFAULT_HUMAN_APPROVAL_POLICY,
        name="human_approval_policy",
        sub_boss_id=sub_id,
    )
    mutation_policy, mutation_warnings = _policy(
        sub.get("mutation_policy"),
        DEFAULT_MUTATION_POLICY,
        name="mutation_policy",
        sub_boss_id=sub_id,
    )
    validation_policy, validation_warnings = _policy(
        sub.get("validation_policy"),
        DEFAULT_VALIDATION_POLICY,
        name="validation_policy",
        sub_boss_id=sub_id,
    )
    warnings += policy_warnings + mutation_warnings + validation_warnings

    if not human_policy.get("required_before_patch_apply"):
        blockers.append(f"sub_boss {sub_id} human approval before patch apply is not required")
    if not human_policy.get("required_before_worker_launch"):
        blockers.append(f"sub_boss {sub_id} human approval before worker launch is not required")
    if not human_policy.get("required_before_file_mutation"):
        blockers.append(f"sub_boss {sub_id} human approval before file mutation is not required")
    if mutation_policy.get("direct_write_allowed"):
        blockers.append(f"sub_boss {sub_id} mutation_policy allows direct writes")
    if mutation_policy.get("apply_allowed_by_commander"):
        blockers.append(f"sub_boss {sub_id} mutation_policy allows Commander patch apply")
    if not mutation_policy.get("patch_proposal_only"):
        blockers.append(f"sub_boss {sub_id} mutation_policy is not patch proposal only")
    if validation_policy.get("may_run_validation"):
        blockers.append(f"sub_boss {sub_id} validation_policy allows validation execution")
    if validation_policy.get("benchmark_run_allowed"):
        blockers.append(f"sub_boss {sub_id} validation_policy allows benchmark execution")

    dependency_readiness, dep_warnings, dep_incomplete, dep_blockers = _dependency_findings(
        sub=sub,
        known_subs=known_subs,
    )
    warnings += dep_warnings
    incomplete += dep_incomplete
    blockers += dep_blockers

    if blockers:
        status_result = "preflight_blocked"
    elif incomplete:
        status_result = "preflight_incomplete"
    elif warnings:
        status_result = "preflight_ready_with_warnings"
    else:
        status_result = "preflight_ready"

    return {
        "sub_boss_id": sub_id,
        "title": str(sub.get("title") or ""),
        "status": str(sub.get("status") or ""),
        "preflight_status": status_result,
        "assigned_role": str(sub.get("assigned_role") or ""),
        "assigned_role_binding": "advisory_label_only",
        "risk_level": risk_level,
        "expected_complexity": _round_metric(expected_complexity),
        "attempt_budget": attempt_budget,
        "allowed_files": allowed_files,
        "forbidden_files": forbidden_files,
        "file_scope": {
            "allowed_file_count": len(allowed_files),
            "forbidden_file_count": len(forbidden_files),
            "maximum_allowed_file_count": MAX_ALLOWED_FILES,
            "bounded": bool(allowed_files) and len(allowed_files) <= MAX_ALLOWED_FILES,
            "conflicts": conflicts,
        },
        "dependency_readiness": dependency_readiness,
        "evidence_required": evidence,
        "rollback_boundary": rollback_boundary,
        "completion_signal": completion_signal,
        "human_approval_policy": human_policy,
        "mutation_policy": mutation_policy,
        "validation_policy": validation_policy,
        "warnings": sorted(dict.fromkeys(warnings)),
        "incomplete_reasons": sorted(dict.fromkeys(incomplete)),
        "blocked_reasons": sorted(dict.fromkeys(blockers)),
    }


def _selected_sub_bosses(
    *,
    sub_bosses: list[dict[str, Any]],
    sub_boss_id: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if sub_boss_id is None or str(sub_boss_id).strip() == "":
        return list(sub_bosses), []
    wanted, blockers = _safe_identifier(sub_boss_id, "sub_boss_id")
    if blockers:
        return [], blockers
    selected = [sub for sub in sub_bosses if str(sub.get("sub_boss_id") or "").strip() == wanted]
    if not selected:
        return [], [f"missing sub-boss: {wanted}"]
    return selected, []


def _overall_status(
    *,
    blockers: list[str],
    incomplete: list[str],
    warnings: list[str],
    findings: list[dict[str, Any]],
) -> str:
    if blockers or any(finding.get("preflight_status") == "preflight_blocked" for finding in findings):
        return "preflight_blocked"
    if incomplete or not findings or any(finding.get("preflight_status") == "preflight_incomplete" for finding in findings):
        return "preflight_incomplete"
    if warnings or any(finding.get("preflight_status") == "preflight_ready_with_warnings" for finding in findings):
        return "preflight_ready_with_warnings"
    return "preflight_ready"


def build_commander_preflight_contract(
    *,
    tree_path: str | Path,
    tree_data: dict[str, Any] | None = None,
    sub_boss_id: str | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic CMD.N4 preflight contract report."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(tree_path, "tree")

    if tree_data is None:
        blockers.append("tree is missing or malformed")
        tree_data = {}

    tree_id, boss_id, title = _tree_identity(tree_data)
    safe_tree_id, tree_id_blockers = _safe_identifier(tree_id, "tree_id")
    safe_boss_id, boss_id_blockers = _safe_identifier(boss_id, "boss_id")
    blockers += tree_id_blockers + boss_id_blockers

    root_boss = tree_data.get("root_boss") if isinstance(tree_data.get("root_boss"), dict) else {}
    root_boss_id = str(root_boss.get("boss_id") or safe_boss_id or "").strip()
    root_safe_id, root_id_blockers = _safe_identifier(root_boss_id, "root_boss.boss_id")
    blockers += root_id_blockers
    root_boss_id = root_safe_id

    raw_sub_bosses = tree_data.get("sub_bosses") if isinstance(tree_data.get("sub_bosses"), list) else []
    sub_bosses = [dict(item) for item in raw_sub_bosses if isinstance(item, dict)]
    known_subs = {str(sub.get("sub_boss_id") or "").strip(): sub for sub in sub_bosses}
    if len(known_subs) != len(sub_bosses):
        blockers.append("sub_boss_id values must be unique and non-empty")
    if _has_dependency_cycle(sub_bosses):
        blockers.append("dependency cycle detected in sub-boss dependencies")

    selected, selection_blockers = _selected_sub_bosses(sub_bosses=sub_bosses, sub_boss_id=sub_boss_id)
    blockers += selection_blockers

    parent_tree_status = str(tree_data.get("validation_status") or "").strip()
    findings = [
        _evaluate_sub_boss(
            sub=sub,
            root_boss_id=root_boss_id,
            known_subs=known_subs,
            parent_tree_status=parent_tree_status,
        )
        for sub in selected
    ]

    warnings: list[str] = []
    incomplete: list[str] = []
    for finding in findings:
        warnings += list(finding.get("warnings") or [])
        incomplete += list(finding.get("incomplete_reasons") or [])
        blockers += list(finding.get("blocked_reasons") or [])
    if not findings and not selection_blockers:
        incomplete.append("no sub-bosses were available to evaluate")

    preflight_status = _overall_status(
        blockers=blockers,
        incomplete=incomplete,
        warnings=warnings,
        findings=findings,
    )

    dependency_readiness = [
        {
            "sub_boss_id": finding["sub_boss_id"],
            "dependencies": list(finding.get("dependency_readiness") or []),
        }
        for finding in findings
    ]
    file_scope_safety = [
        {
            "sub_boss_id": finding["sub_boss_id"],
            "file_scope": dict(finding.get("file_scope") or {}),
        }
        for finding in findings
    ]
    evidence_requirements = [
        {
            "sub_boss_id": finding["sub_boss_id"],
            "evidence_required": list(finding.get("evidence_required") or []),
        }
        for finding in findings
    ]
    rollback_boundaries = [
        {
            "sub_boss_id": finding["sub_boss_id"],
            "rollback_boundary": str(finding.get("rollback_boundary") or ""),
        }
        for finding in findings
    ]

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": COMMANDER_PREFLIGHT_CONTRACT_GUARDRAIL_NOTE,
        "tree_id": safe_tree_id if not tree_id_blockers else tree_id,
        "boss_id": safe_boss_id if not boss_id_blockers else boss_id,
        "title": title,
        "source_tree_path": str(tree_path or ""),
        "requested_sub_boss_id": str(sub_boss_id or ""),
        "source_tree": {
            "tree_id": tree_id,
            "boss_id": boss_id,
            "title": title,
            "validation_status": parent_tree_status,
            "sub_boss_count": len(sub_bosses),
        },
        "evaluated_sub_bosses": [
            {
                "sub_boss_id": finding["sub_boss_id"],
                "title": finding["title"],
                "status": finding["status"],
                "preflight_status": finding["preflight_status"],
            }
            for finding in findings
        ],
        "evaluated_sub_boss_count": len(findings),
        "preflight_status": preflight_status,
        "preflight_contract": {
            "evaluable_statuses": list(EVALUABLE_SUB_BOSS_STATUSES),
            "ready_parent_tree_statuses": list(READY_TREE_STATUSES),
            "required_fields": [
                "sub_boss_id",
                "parent_boss_id",
                "dependencies",
                "allowed_files",
                "forbidden_files",
                "evidence_required",
                "rollback_boundary",
                "completion_signal",
                "attempt_budget",
                "expected_complexity",
            ],
            "maximum_allowed_file_count": MAX_ALLOWED_FILES,
            "hidden_auto_flags_blocked": list(AUTO_FLAG_KEYS),
            "executable_worker_keys_blocked": list(EXECUTABLE_WORKER_KEYS),
        },
        "policy_defaults": {
            "human_approval_policy": dict(DEFAULT_HUMAN_APPROVAL_POLICY),
            "mutation_policy": dict(DEFAULT_MUTATION_POLICY),
            "validation_policy": dict(DEFAULT_VALIDATION_POLICY),
            "risk_level": "unknown",
        },
        "per_sub_boss_findings": findings,
        "dependency_readiness": dependency_readiness,
        "file_scope_safety": file_scope_safety,
        "evidence_requirements": evidence_requirements,
        "rollback_boundaries": rollback_boundaries,
        "human_approval_policy": dict(DEFAULT_HUMAN_APPROVAL_POLICY),
        "warnings": sorted(dict.fromkeys(warnings)),
        "incomplete_reasons": sorted(dict.fromkeys(incomplete)),
        "blocked_reasons": sorted(dict.fromkeys(blockers)),
        "guardrails": _guardrails(),
        "preflight_statuses": list(PREFLIGHT_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "boundaries": [
            "CMD.N4 evaluates preflight readiness only.",
            "CMD.N4 does not execute sub-bosses.",
            "CMD.N4 does not assign real workers.",
            "CMD.N4 does not call models.",
            "CMD.N4 does not run validation or benchmarks.",
            "CMD.N4 does not mutate execution eligibility.",
            "CMD.N4 does not change routing.",
            "CMD.N4 writes preflight artifacts only.",
        ],
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_commander_preflight_contract_markdown(report: dict[str, Any]) -> str:
    """Render a CMD.N4 preflight contract report as Markdown."""
    source = report.get("source_tree") if isinstance(report.get("source_tree"), dict) else {}
    contract = report.get("preflight_contract") if isinstance(report.get("preflight_contract"), dict) else {}
    defaults = report.get("policy_defaults") if isinstance(report.get("policy_defaults"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Commander Preflight Contract",
        "",
        f"> {report.get('guardrail_note', COMMANDER_PREFLIGHT_CONTRACT_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.N4 evaluates whether registered manual sub-bosses have a safe preflight contract. It runs nothing and changes no routing, assignment, or execution behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Tree id:** `{_md(report.get('tree_id', ''))}`",
        f"- **Boss id:** `{_md(report.get('boss_id', ''))}`",
        f"- **Title:** {_md(report.get('title', ''))}",
        f"- **Preflight status:** `{_md(report.get('preflight_status', ''))}`",
        f"- **Evaluated sub-bosses:** {report.get('evaluated_sub_boss_count', 0)}",
        "",
        "## Source Tree",
        "",
        f"- **Tree path:** `{_md(report.get('source_tree_path', ''))}`",
        f"- **Tree validation status:** `{_md(source.get('validation_status', ''))}`",
        f"- **Registered sub-boss count:** {source.get('sub_boss_count', 0)}",
        "",
        "## Evaluated Sub-Bosses",
        "",
    ]
    evaluated = report.get("evaluated_sub_bosses") if isinstance(report.get("evaluated_sub_bosses"), list) else []
    if evaluated:
        lines += [
            "| Sub-boss | Title | Registry status | Preflight status |",
            "| --- | --- | --- | --- |",
        ]
        for row in evaluated:
            lines.append(
                "| {sid} | {title} | {status} | {preflight} |".format(
                    sid=_md(row.get("sub_boss_id", "")),
                    title=_md(row.get("title", "")),
                    status=_md(row.get("status", "")),
                    preflight=_md(row.get("preflight_status", "")),
                )
            )
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Preflight Contract",
        "",
        f"- **Evaluable statuses:** `{_md(', '.join(contract.get('evaluable_statuses') or []))}`",
        f"- **Ready parent tree statuses:** `{_md(', '.join(contract.get('ready_parent_tree_statuses') or []))}`",
        f"- **Maximum allowed file count:** {contract.get('maximum_allowed_file_count')}",
        f"- **Hidden auto flags blocked:** `{_md(', '.join(contract.get('hidden_auto_flags_blocked') or []))}`",
        f"- **Executable worker keys blocked:** `{_md(', '.join(contract.get('executable_worker_keys_blocked') or []))}`",
        "",
        "## Policy Defaults",
        "",
    ]
    for name in ("human_approval_policy", "mutation_policy", "validation_policy"):
        policy = defaults.get(name) if isinstance(defaults.get(name), dict) else {}
        lines.append(f"- **{name}:** `{_md(json.dumps(policy, sort_keys=True))}`")
    lines.append(f"- **risk_level:** `{_md(defaults.get('risk_level', 'unknown'))}`")
    lines += [
        "",
        "## Per-Sub-Boss Findings",
        "",
    ]
    findings = report.get("per_sub_boss_findings") if isinstance(report.get("per_sub_boss_findings"), list) else []
    if findings:
        lines += [
            "| Sub-boss | Status | Risk | Files | Dependencies | Warnings | Incomplete | Blocked |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for finding in findings:
            scope = finding.get("file_scope") if isinstance(finding.get("file_scope"), dict) else {}
            lines.append(
                "| {sid} | {status} | {risk} | {files} | {deps} | {warnings} | {incomplete} | {blocked} |".format(
                    sid=_md(finding.get("sub_boss_id", "")),
                    status=_md(finding.get("preflight_status", "")),
                    risk=_md(finding.get("risk_level", "")),
                    files=scope.get("allowed_file_count", 0),
                    deps=len(finding.get("dependency_readiness") or []),
                    warnings=len(finding.get("warnings") or []),
                    incomplete=len(finding.get("incomplete_reasons") or []),
                    blocked=len(finding.get("blocked_reasons") or []),
                )
            )
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Dependency Readiness",
        "",
    ]
    deps = report.get("dependency_readiness") if isinstance(report.get("dependency_readiness"), list) else []
    if deps:
        for row in deps:
            values = row.get("dependencies") or []
            if values:
                for dep in values:
                    lines.append(
                        f"- `{_md(row.get('sub_boss_id', ''))}` depends on `{_md(dep.get('dependency', ''))}`: `{_md(dep.get('status', ''))}`"
                    )
            else:
                lines.append(f"- `{_md(row.get('sub_boss_id', ''))}` has no dependencies.")
    else:
        lines.append("_None._")
    lines += [
        "",
        "## File Scope Safety",
        "",
    ]
    scopes = report.get("file_scope_safety") if isinstance(report.get("file_scope_safety"), list) else []
    if scopes:
        for row in scopes:
            scope = row.get("file_scope") if isinstance(row.get("file_scope"), dict) else {}
            lines.append(
                f"- `{_md(row.get('sub_boss_id', ''))}`: allowed={scope.get('allowed_file_count', 0)}, forbidden={scope.get('forbidden_file_count', 0)}, bounded={str(bool(scope.get('bounded'))).lower()}"
            )
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Evidence Requirements",
        "",
    ]
    evidence_rows = report.get("evidence_requirements") if isinstance(report.get("evidence_requirements"), list) else []
    if evidence_rows:
        for row in evidence_rows:
            lines.append(f"- `{_md(row.get('sub_boss_id', ''))}`: {_md(', '.join(row.get('evidence_required') or []))}")
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Rollback Boundaries",
        "",
    ]
    rollback_rows = report.get("rollback_boundaries") if isinstance(report.get("rollback_boundaries"), list) else []
    if rollback_rows:
        for row in rollback_rows:
            lines.append(f"- `{_md(row.get('sub_boss_id', ''))}`: {_md(row.get('rollback_boundary', ''))}")
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Human Approval Policy",
        "",
        f"- `{_md(json.dumps(report.get('human_approval_policy') or {}, sort_keys=True))}`",
        "",
        "## Warnings",
        "",
    ]
    _render_list(lines, list(report.get("warnings") or []))

    lines += ["## Blocked Reasons", ""]
    _render_list(lines, list(report.get("blocked_reasons") or []))

    lines += ["## Boundaries / Guardrails", ""]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines += [
        "",
        "- CMD.N4 does not execute sub-bosses.",
        "- CMD.N4 does not assign real workers.",
        "- CMD.N4 does not call models.",
        "- CMD.N4 does not run validation or benchmarks.",
        "- CMD.N4 does not mutate execution eligibility.",
        "- CMD.N4 does not change routing.",
        "- CMD.N4 writes preflight artifacts only.",
        "",
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        f"- **Alternative:** {_md(next_phase.get('alternative', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_commander_preflight_contract(
    *,
    tree_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    sub_boss_id: str | None = None,
) -> dict[str, Any]:
    """Build and write the CMD.N4 JSON + Markdown preflight artifacts."""
    tree_data, read_blockers = read_json_input(tree_path, "tree")
    report = build_commander_preflight_contract(
        tree_path=tree_path,
        tree_data=tree_data,
        sub_boss_id=sub_boss_id,
        input_blockers=read_blockers,
    )
    safe_tree_id, tree_id_blockers = _safe_identifier(report.get("tree_id"), "tree_id")
    target_id = safe_tree_id if not tree_id_blockers else INVALID_TREE_ID_DIR
    out_dir = Path(output_dir) / target_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_commander_preflight_contract_markdown(report), encoding="utf-8")
    return {
        "ok": report.get("preflight_status") != "preflight_blocked",
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
