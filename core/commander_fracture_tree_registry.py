"""CMD.N3 - Commander Fracture Tree Registry (report-only).

Validates and stores manually defined Commander boss/sub-boss fracture trees
from CMD.N2 or a manually written tree JSON file. CMD.N3 writes deterministic
registry artifacts only. It does not execute sub-bosses, assign real workers,
call models, launch Commander mode, change routing, apply patches, run
validation, run benchmarks, invoke MCP tools, execute Dream actions, apply
Replay janitor actions, use Docker/subprocess, contact networks, write
databases, or change runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.boss_half_life_fracture_plan import GUARDRAIL_FALSE_FLAGS as CMD_N1_GUARDRAIL_FALSE_FLAGS


REPORT_KIND = "commander_fracture_tree_registry"
JSON_NAME = "commander_fracture_tree_registry.json"
MD_NAME = "commander_fracture_tree_registry.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "commander" / "fracture_tree_registry"
INVALID_TREE_ID_DIR = "invalid_tree_id"

ALLOWED_SUB_BOSS_STATUSES: tuple[str, ...] = (
    "proposed",
    "ready_for_preflight",
    "blocked",
    "deferred",
    "completed",
)

VALIDATION_STATUSES: tuple[str, ...] = (
    "registry_ready",
    "registry_ready_with_warnings",
    "incomplete_tree",
    "blocked",
)

ROOT_BOSS_FIELDS: tuple[str, ...] = (
    "boss_id",
    "title",
    "description",
    "initial_complexity",
    "actual_remaining",
    "attempt",
    "max_attempts",
    "aggressiveness",
    "tolerance",
    "fracture_pressure",
    "commander_decision",
)

SUB_BOSS_FIELDS: tuple[str, ...] = (
    "sub_boss_id",
    "parent_boss_id",
    "title",
    "goal",
    "scope",
    "expected_complexity",
    "evidence_required",
    "allowed_files",
    "forbidden_files",
    "assigned_role",
    "attempt_budget",
    "completion_signal",
    "rollback_boundary",
    "dependencies",
    "status",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = tuple(
    dict.fromkeys(
        list(CMD_N1_GUARDRAIL_FALSE_FLAGS)
        + [
            "registry_execution_performed",
            "sub_boss_execution_performed",
            "real_worker_assignment_performed",
            "validation_run_performed",
        ]
    )
)

COMMANDER_FRACTURE_TREE_REGISTRY_GUARDRAIL_NOTE = (
    "Commander Fracture Tree Registry is report-only: it validates and stores "
    "manually defined boss/sub-boss trees from CMD.N2 or a manual tree JSON "
    "file. It writes registry artifacts only and does not execute sub-bosses, "
    "assign real workers, call models, launch Commander mode, change routing, "
    "apply patches, run validation, run benchmarks, invoke MCP tools, execute "
    "Dream actions, apply Replay janitor actions, use Docker/subprocess, contact "
    "networks, write databases, change auth policy, or change route behavior."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "CMD.N4",
    "title": "Commander Preflight Contract",
    "reason": (
        "After a fracture tree has a durable validated registry shape, define "
        "the report-only preflight contract that can review readiness before any "
        "routing, worker assignment, or execution behavior exists."
    ),
}

FRACTURE_DECISIONS = {"fracture_recommended", "hard_fracture_required"}


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
        return []
    text = str(path).strip()
    if _path_has_traversal(text):
        return [f"{label} path must not contain traversal segments"]
    return []


def _normalize_path_list(value: Any, *, field: str, sub_boss_id: str) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    normalized: list[str] = []
    if not isinstance(value, list):
        return [], [f"sub_boss {sub_boss_id} {field} must be a list of path strings"]
    for index, item in enumerate(value):
        if not isinstance(item, str):
            blockers.append(f"sub_boss {sub_boss_id} {field}[{index}] must be a string")
            continue
        text = item.strip().replace("\\", "/")
        if not text:
            blockers.append(f"sub_boss {sub_boss_id} {field}[{index}] must not be empty")
            continue
        if text.startswith("/") or ":" in _split_segments(text)[0] or _path_has_traversal(text):
            blockers.append(f"sub_boss {sub_boss_id} {field} contains unsafe path: {item}")
            continue
        normalized.append(text)
    return normalized, blockers


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def read_json_input(path: str | Path | None, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Read a manual JSON input file and report blockers instead of raising."""
    blockers = _input_path_blockers(path, label)
    if blockers:
        return None, blockers
    if path is None or str(path).strip() == "":
        return None, []
    source = Path(path)
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


def _root_from_cmd_n2(source_report: dict[str, Any]) -> dict[str, Any]:
    boss = source_report.get("boss_input") if isinstance(source_report.get("boss_input"), dict) else {}
    params = source_report.get("half_life_parameters") if isinstance(source_report.get("half_life_parameters"), dict) else {}
    decision = source_report.get("commander_decision") if isinstance(source_report.get("commander_decision"), dict) else {}
    return {
        "boss_id": boss.get("boss_id", ""),
        "title": boss.get("title", ""),
        "description": boss.get("description", ""),
        "initial_complexity": params.get("initial_complexity"),
        "actual_remaining": source_report.get("actual_remaining_complexity", params.get("actual_remaining")),
        "attempt": params.get("attempt"),
        "max_attempts": params.get("max_attempts"),
        "aggressiveness": params.get("aggressiveness"),
        "tolerance": params.get("tolerance"),
        "fracture_pressure": source_report.get("fracture_pressure"),
        "commander_decision": decision.get("status", ""),
    }


def _sub_bosses_from_cmd_n2(source_report: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = source_report.get("manual_sub_boss_candidates")
    if not isinstance(candidates, list):
        return []
    boss = source_report.get("boss_input") if isinstance(source_report.get("boss_input"), dict) else {}
    root_boss_id = str(boss.get("boss_id") or "").strip()
    tree = source_report.get("fracture_tree") if isinstance(source_report.get("fracture_tree"), dict) else {}
    children = tree.get("children") if isinstance(tree.get("children"), list) else []
    parents_by_id = {
        str(child.get("sub_boss_id")): str(child.get("parent_boss_id") or "").strip()
        for child in children
        if isinstance(child, dict) and child.get("sub_boss_id")
    }
    rows: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict):
            row = dict(item)
            if not row.get("parent_boss_id"):
                row["parent_boss_id"] = parents_by_id.get(str(row.get("sub_boss_id")), "") or root_boss_id
            row.setdefault("status", "proposed")
            rows.append(row)
    return rows


def _input_shape(
    *,
    boss_id: str,
    title: str,
    source_report: dict[str, Any] | None,
    tree_data: dict[str, Any] | None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if source_report is not None:
        if tree_data is not None:
            warnings.append("source_report and tree_file were both provided; source_report was used")
        return "cmd_n2_source_report", _root_from_cmd_n2(source_report), _sub_bosses_from_cmd_n2(source_report), warnings
    if tree_data is not None:
        root = tree_data.get("root_boss") if isinstance(tree_data.get("root_boss"), dict) else {}
        sub_bosses = tree_data.get("sub_bosses") if isinstance(tree_data.get("sub_bosses"), list) else []
        return "manual_tree_file", dict(root), [dict(item) for item in sub_bosses if isinstance(item, dict)], warnings
    warnings.append("no source_report or tree_file was provided; registry contains minimal CLI metadata only")
    return (
        "minimal_cli_metadata",
        {
            "boss_id": boss_id,
            "title": title,
            "description": "",
            "initial_complexity": None,
            "actual_remaining": None,
            "attempt": None,
            "max_attempts": None,
            "aggressiveness": None,
            "tolerance": None,
            "fracture_pressure": None,
            "commander_decision": "",
        },
        [],
        warnings,
    )


def _normalize_root(root: dict[str, Any], *, boss_id: str, title: str) -> dict[str, Any]:
    normalized = {field: root.get(field) for field in ROOT_BOSS_FIELDS}
    normalized["boss_id"] = str(normalized.get("boss_id") or boss_id or "").strip()
    normalized["title"] = str(normalized.get("title") or title or "").strip()
    normalized["description"] = str(normalized.get("description") or "")
    decision = normalized.get("commander_decision")
    if isinstance(decision, dict):
        normalized["commander_decision"] = str(decision.get("status") or "")
    else:
        normalized["commander_decision"] = str(decision or "")
    return normalized


def _normalize_sub_bosses(
    raw_sub_bosses: list[dict[str, Any]],
    *,
    root_boss_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]], list[str], list[str]]:
    sub_bosses: list[dict[str, Any]] = []
    seen: set[str] = set()
    missing_fields: list[dict[str, Any]] = []
    dependency_edges: list[dict[str, str]] = []
    warnings: list[str] = []
    blockers: list[str] = []

    for index, raw in enumerate(raw_sub_bosses):
        sub_id = str(raw.get("sub_boss_id") or f"#{index}").strip()
        safe_sub_id, id_blockers = _safe_identifier(sub_id, f"sub_boss_id {sub_id}")
        blockers += id_blockers
        if safe_sub_id in seen:
            blockers.append(f"duplicate sub_boss_id: {safe_sub_id}")
        seen.add(safe_sub_id)

        missing = [field for field in SUB_BOSS_FIELDS if field not in raw or raw.get(field) in (None, "")]
        if missing:
            missing_fields.append({"sub_boss_id": safe_sub_id, "index": index, "missing_fields": missing})

        status = str(raw.get("status") or "proposed").strip()
        if status not in ALLOWED_SUB_BOSS_STATUSES:
            warnings.append(f"sub_boss {safe_sub_id} has unknown status {status}; stored as proposed")
            status = "proposed"

        expected = _as_positive_float(raw.get("expected_complexity"))
        if expected is None:
            blockers.append(f"sub_boss {safe_sub_id} expected_complexity must be positive")
        attempt_budget = _as_positive_int(raw.get("attempt_budget"))
        if attempt_budget is None:
            blockers.append(f"sub_boss {safe_sub_id} attempt_budget must be a positive integer")

        evidence = _strings(raw.get("evidence_required"))
        rollback_boundary = str(raw.get("rollback_boundary") or "").strip()
        if status == "ready_for_preflight":
            if not evidence:
                warnings.append(f"sub_boss {safe_sub_id} ready_for_preflight requires non-empty evidence_required")
            if not rollback_boundary:
                warnings.append(f"sub_boss {safe_sub_id} ready_for_preflight requires rollback_boundary")
        assigned_role = str(raw.get("assigned_role") or "").strip()
        if not assigned_role:
            warnings.append(f"sub_boss {safe_sub_id} assigned_role is missing; role remains advisory only")

        allowed_files, allowed_blockers = _normalize_path_list(
            raw.get("allowed_files"), field="allowed_files", sub_boss_id=safe_sub_id
        )
        forbidden_files, forbidden_blockers = _normalize_path_list(
            raw.get("forbidden_files"), field="forbidden_files", sub_boss_id=safe_sub_id
        )
        blockers += allowed_blockers + forbidden_blockers

        dependencies = _strings(raw.get("dependencies"))
        for dep in dependencies:
            dependency_edges.append({"from": dep, "to": safe_sub_id})

        sub_bosses.append(
            {
                "sub_boss_id": safe_sub_id,
                "parent_boss_id": str(raw.get("parent_boss_id") or "").strip(),
                "title": str(raw.get("title") or ""),
                "goal": str(raw.get("goal") or ""),
                "scope": str(raw.get("scope") or ""),
                "expected_complexity": _round_metric(expected),
                "evidence_required": evidence,
                "allowed_files": allowed_files,
                "forbidden_files": forbidden_files,
                "assigned_role": assigned_role,
                "assigned_role_binding": "advisory_label_only",
                "attempt_budget": attempt_budget,
                "completion_signal": str(raw.get("completion_signal") or ""),
                "rollback_boundary": rollback_boundary,
                "dependencies": dependencies,
                "status": status,
            }
        )

    known = {sub["sub_boss_id"] for sub in sub_bosses}
    valid_parent_ids = set(known)
    valid_parent_ids.add(root_boss_id)
    for sub in sub_bosses:
        parent = sub.get("parent_boss_id")
        if parent not in valid_parent_ids:
            blockers.append(f"sub_boss {sub['sub_boss_id']} parent_boss_id references unknown boss: {parent}")
        for dep in sub.get("dependencies") or []:
            if dep not in known:
                blockers.append(f"sub_boss {sub['sub_boss_id']} has unknown dependency: {dep}")

    if _has_dependency_cycle(sub_bosses):
        blockers.append("dependency cycle detected in sub-boss dependencies")

    return sub_bosses, missing_fields, dependency_edges, warnings, blockers


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


def _complexity_warning(
    *,
    total_expected: float,
    actual_remaining: Any,
    tolerance: Any,
) -> tuple[dict[str, Any], list[str]]:
    actual = _as_float(actual_remaining)
    margin = _as_float(tolerance)
    warnings: list[str] = []
    ratio = None
    comparison = "not_applicable"
    if margin is None:
        margin = 0.20
    if actual is not None and actual > 0:
        ratio = total_expected / actual
        if abs(total_expected - actual) > actual * margin:
            comparison = "outside_tolerance"
            warnings.append("total expected sub-boss complexity differs from root actual_remaining by more than tolerance")
        else:
            comparison = "within_tolerance"
    return (
        {
            "total_expected_complexity": _round_metric(total_expected),
            "root_actual_remaining": _round_metric(actual),
            "ratio_to_actual_remaining": _round_metric(ratio),
            "tolerance": _round_metric(margin),
            "comparison": comparison,
        },
        warnings,
    )


def _validation_status(
    *,
    blockers: list[str],
    warnings: list[str],
    root_boss: dict[str, Any],
    sub_bosses: list[dict[str, Any]],
) -> str:
    if blockers:
        return "blocked"
    if not root_boss.get("boss_id") or not root_boss.get("title"):
        return "incomplete_tree"
    if not sub_bosses:
        return "incomplete_tree"
    if warnings:
        return "registry_ready_with_warnings"
    return "registry_ready"


def build_commander_fracture_tree_registry(
    *,
    tree_id: Any,
    boss_id: Any,
    title: Any,
    source_report_path: str = "",
    tree_file_path: str = "",
    source_report: dict[str, Any] | None = None,
    tree_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic CMD.N3 fracture tree registry record."""
    safe_tree_id, tree_id_blockers = _safe_identifier(tree_id, "tree_id")
    safe_boss_id, boss_id_blockers = _safe_identifier(boss_id, "boss_id")
    blockers = list(tree_id_blockers) + list(boss_id_blockers) + list(input_blockers or [])
    blockers += _input_path_blockers(source_report_path, "source_report")
    blockers += _input_path_blockers(tree_file_path, "tree_file")

    input_source, raw_root, raw_sub_bosses, input_warnings = _input_shape(
        boss_id=safe_boss_id,
        title=str(title or ""),
        source_report=source_report,
        tree_data=tree_data,
    )
    root_boss = _normalize_root(raw_root, boss_id=safe_boss_id, title=str(title or ""))
    root_safe_id, root_id_blockers = _safe_identifier(root_boss.get("boss_id"), "root_boss.boss_id")
    blockers += root_id_blockers
    root_boss["boss_id"] = root_safe_id
    if root_boss.get("boss_id") != safe_boss_id and not boss_id_blockers:
        input_warnings.append("CLI boss_id differs from root_boss boss_id; root_boss value was preserved")

    sub_bosses, missing_fields, dependency_edges, sub_warnings, sub_blockers = _normalize_sub_bosses(
        raw_sub_bosses,
        root_boss_id=root_boss.get("boss_id") or safe_boss_id,
    )
    blockers += sub_blockers

    total_expected_float = 0.0
    total_attempt_budget = 0
    for sub in sub_bosses:
        expected = _as_float(sub.get("expected_complexity"))
        if expected is not None:
            total_expected_float += expected
        budget = sub.get("attempt_budget")
        if isinstance(budget, int):
            total_attempt_budget += budget

    complexity_budget, complexity_warnings = _complexity_warning(
        total_expected=total_expected_float,
        actual_remaining=root_boss.get("actual_remaining"),
        tolerance=root_boss.get("tolerance"),
    )
    warnings = input_warnings + sub_warnings + complexity_warnings
    commander_decision = str(root_boss.get("commander_decision") or "")
    if not sub_bosses:
        if commander_decision in FRACTURE_DECISIONS:
            warnings.append("fracture decision exists but no sub-bosses exist")
        else:
            warnings.append("fracture tree has no sub-bosses")
    if sub_bosses and all(sub.get("status") == "deferred" for sub in sub_bosses):
        warnings.append("all sub-bosses are deferred")

    status = _validation_status(
        blockers=blockers,
        warnings=warnings,
        root_boss=root_boss,
        sub_bosses=sub_bosses,
    )
    validation_findings = {
        "sub_boss_count": len(sub_bosses),
        "dependency_edge_count": len(dependency_edges),
        "missing_sub_boss_fields": missing_fields,
        "blocked_reason_count": len(sorted(set(blockers))),
        "warning_count": len(sorted(set(warnings))),
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": COMMANDER_FRACTURE_TREE_REGISTRY_GUARDRAIL_NOTE,
        "tree_id": safe_tree_id if not tree_id_blockers else str(tree_id or ""),
        "boss_id": safe_boss_id if not boss_id_blockers else str(boss_id or ""),
        "title": str(title or ""),
        "source_report_path": str(source_report_path or ""),
        "tree_file_path": str(tree_file_path or ""),
        "source_inputs": {
            "input_source": input_source,
            "source_report_path": str(source_report_path or ""),
            "tree_file_path": str(tree_file_path or ""),
        },
        "root_boss": root_boss,
        "sub_bosses": sub_bosses,
        "dependency_edges": dependency_edges,
        "total_expected_complexity": _round_metric(total_expected_float),
        "total_attempt_budget": total_attempt_budget,
        "complexity_budget": complexity_budget,
        "validation_status": status,
        "validation_findings": validation_findings,
        "warnings": sorted(dict.fromkeys(warnings)),
        "blocked_reasons": sorted(dict.fromkeys(blockers)),
        "guardrails": _guardrails(),
        "allowed_sub_boss_statuses": list(ALLOWED_SUB_BOSS_STATUSES),
        "root_boss_fields": list(ROOT_BOSS_FIELDS),
        "sub_boss_fields": list(SUB_BOSS_FIELDS),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "boundaries": [
            "CMD.N3 validates and stores fracture tree registry artifacts only.",
            "CMD.N3 does not execute sub-bosses.",
            "CMD.N3 does not assign real workers.",
            "CMD.N3 treats assigned_role as an advisory label only.",
            "CMD.N3 does not route tasks or launch Commander mode.",
        ],
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_commander_fracture_tree_registry_markdown(registry: dict[str, Any]) -> str:
    """Render a CMD.N3 fracture tree registry as Markdown."""
    root = registry.get("root_boss") if isinstance(registry.get("root_boss"), dict) else {}
    source = registry.get("source_inputs") if isinstance(registry.get("source_inputs"), dict) else {}
    complexity = registry.get("complexity_budget") if isinstance(registry.get("complexity_budget"), dict) else {}
    findings = registry.get("validation_findings") if isinstance(registry.get("validation_findings"), dict) else {}
    next_phase = registry.get("recommended_next_phase") if isinstance(registry.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Commander Fracture Tree Registry",
        "",
        f"> {registry.get('guardrail_note', COMMANDER_FRACTURE_TREE_REGISTRY_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.N3 validates manual fracture trees and writes registry artifacts. It runs nothing and changes no routing or execution behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Tree id:** `{_md(registry.get('tree_id', ''))}`",
        f"- **Boss id:** `{_md(registry.get('boss_id', ''))}`",
        f"- **Title:** {_md(registry.get('title', ''))}",
        f"- **Validation status:** `{_md(registry.get('validation_status', ''))}`",
        f"- **Sub-boss count:** {findings.get('sub_boss_count', 0)}",
        "",
        "## Source Inputs",
        "",
        f"- **Input source:** `{_md(source.get('input_source', ''))}`",
        f"- **Source report path:** `{_md(source.get('source_report_path', ''))}`",
        f"- **Tree file path:** `{_md(source.get('tree_file_path', ''))}`",
        "",
        "## Root Boss",
        "",
    ]
    for field in ROOT_BOSS_FIELDS:
        lines.append(f"- **{field}:** `{_md(root.get(field))}`")
    lines += [
        "",
        "## Sub-Boss Registry",
        "",
    ]
    sub_bosses = registry.get("sub_bosses") if isinstance(registry.get("sub_bosses"), list) else []
    if sub_bosses:
        lines += [
            "| Sub-boss | Parent | Status | Expected complexity | Attempt budget | Assigned role | Binding |",
            "| --- | --- | --- | ---: | ---: | --- | --- |",
        ]
        for sub in sub_bosses:
            lines.append(
                "| {sid} | {parent} | {status} | {expected} | {budget} | {role} | {binding} |".format(
                    sid=_md(sub.get("sub_boss_id", "")),
                    parent=_md(sub.get("parent_boss_id", "")),
                    status=_md(sub.get("status", "")),
                    expected=_md(sub.get("expected_complexity", "")),
                    budget=_md(sub.get("attempt_budget", "")),
                    role=_md(sub.get("assigned_role", "")),
                    binding=_md(sub.get("assigned_role_binding", "")),
                )
            )
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Dependency Graph",
        "",
    ]
    edges = registry.get("dependency_edges") if isinstance(registry.get("dependency_edges"), list) else []
    if edges:
        for edge in edges:
            lines.append(f"- `{_md(edge.get('from', ''))}` -> `{_md(edge.get('to', ''))}`")
    else:
        lines.append("_No dependency edges._")
    lines += [
        "",
        "## Complexity Budget",
        "",
        f"- **Total expected complexity:** {registry.get('total_expected_complexity')}",
        f"- **Root actual remaining:** {complexity.get('root_actual_remaining')}",
        f"- **Ratio:** {complexity.get('ratio_to_actual_remaining')}",
        f"- **Comparison:** `{_md(complexity.get('comparison'))}`",
        "",
        "## Attempt Budget",
        "",
        f"- **Total attempt budget:** {registry.get('total_attempt_budget')}",
        "",
        "## Validation Findings",
        "",
        f"- **Dependency edge count:** {findings.get('dependency_edge_count', 0)}",
        f"- **Missing sub-boss field rows:** {len(findings.get('missing_sub_boss_fields') or [])}",
        f"- **Warning count:** {findings.get('warning_count', 0)}",
        f"- **Blocked reason count:** {findings.get('blocked_reason_count', 0)}",
        "",
        "## Warnings",
        "",
    ]
    _render_list(lines, list(registry.get("warnings") or []))

    lines += ["## Blocked Reasons", ""]
    _render_list(lines, list(registry.get("blocked_reasons") or []))

    lines += ["## Boundaries / Guardrails", ""]
    guardrails = registry.get("guardrails") if isinstance(registry.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines += [
        "",
        "- CMD.N3 does not execute sub-bosses.",
        "- CMD.N3 does not assign real workers.",
        "- CMD.N3 does not call models.",
        "- CMD.N3 does not launch Commander mode.",
        "- CMD.N3 does not route tasks.",
        "- CMD.N3 writes registry artifacts only.",
        "",
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_commander_fracture_tree_registry(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    tree_id: Any,
    boss_id: Any,
    title: Any,
    source_report_path: str = "",
    tree_file_path: str = "",
    source_report: dict[str, Any] | None = None,
    tree_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write the CMD.N3 JSON + Markdown registry artifacts."""
    safe_tree_id, tree_id_blockers = _safe_identifier(tree_id, "tree_id")
    registry = build_commander_fracture_tree_registry(
        tree_id=tree_id,
        boss_id=boss_id,
        title=title,
        source_report_path=source_report_path,
        tree_file_path=tree_file_path,
        source_report=source_report,
        tree_data=tree_data,
        input_blockers=input_blockers,
    )
    target_id = safe_tree_id if not tree_id_blockers else INVALID_TREE_ID_DIR
    out_dir = Path(output_dir) / target_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_commander_fracture_tree_registry_markdown(registry), encoding="utf-8")
    return {
        "ok": registry.get("validation_status") != "blocked",
        "json_path": str(json_path),
        "md_path": str(md_path),
        "registry": registry,
    }
