"""ADOPT.MODEL.1 - Human-approved model role catalog adoption.

Adopts the reviewed MODEL.N4 proposed catalog as the active advisory
model-role registry artifact. This module only reads and writes catalog,
backup, and receipt artifacts. It does not route tasks, call models, launch
workers, bind executable model IDs, run validation or benchmarks, invoke MCP
tools, contact networks, write databases, change auth or route behavior, or
grant automatic authority.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.model_role_registry import (
    build_model_role_registry,
    render_model_role_registry_markdown,
)


REPORT_KIND = "model_role_catalog_adoption_receipt"
JSON_NAME = "model_role_catalog_adoption_receipt.json"
MD_NAME = "model_role_catalog_adoption_receipt.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "adoption"
BACKUP_DIR_NAME = "backups"
BACKUP_JSON_NAME = "model_role_registry_before_adoption.json"
BACKUP_MD_NAME = "model_role_registry_before_adoption.md"

ADOPTED_PHASE_ID = "ADOPT.MODEL.1"
SOURCE_PROPOSAL_PHASE_ID = "MODEL.N4"
ACTIVE_REGISTRY_REPORT_KIND = "model_role_registry"
PROPOSED_REGISTRY_REPORT_KIND = "proposed_model_role_registry"

ADDED_ROLE_IDS: tuple[str, ...] = (
    "ui_reviewer",
    "test_designer",
    "documentation_reviewer",
)

ADOPTION_STATUSES: tuple[str, ...] = (
    "model_role_catalog_adoption_complete",
    "model_role_catalog_adoption_complete_with_warnings",
    "model_role_catalog_adoption_incomplete",
    "model_role_catalog_adoption_blocked",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "model_call_performed",
    "model_routing_performed",
    "worker_launch_performed",
    "executable_model_binding_created",
    "automatic_assignment_performed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_used",
    "network_contacted",
    "database_write_performed",
    "route_behavior_changed",
    "routing_changed",
    "auth_policy_changed",
    "approval_token_enforcement_changed",
    "worker_launch_allowed",
    "model_calls_allowed",
    "model_routing_enabled",
)

FORBIDDEN_AUTHORITY_FLAGS: tuple[str, ...] = (
    "auto_run",
    "auto_apply",
    "auto_merge",
    "route_tasks",
    "launch_worker",
    "run_validation",
    "run_benchmark",
    "mutate_files",
    "approve_patch",
)

MODEL_ROUTING_KEYS: tuple[str, ...] = (
    "model_routing_enabled",
    "model_routing_performed",
    "routing_changed",
    "route_tasks",
    "routing_enabled",
    "task_routing_performed",
    "route_behavior_changed",
)

MODEL_CALL_KEYS: tuple[str, ...] = (
    "model_calls_allowed",
    "model_call_enabled",
    "model_call_performed",
)

WORKER_LAUNCH_KEYS: tuple[str, ...] = (
    "worker_launch_allowed",
    "worker_launch_enabled",
    "worker_launch_performed",
    "launch_worker",
)

MODEL_ID_AUTHORITY_KEYS: tuple[str, ...] = (
    "model",
    "model_id",
    "model_name",
    "llm",
    "authority_model",
    "authoritative_model",
    "model_authority",
    "model_binding",
    "executable_model_id",
    "execution_authority",
)

AUTHORITY_KEY_FRAGMENTS: tuple[str, ...] = (
    "can_execute",
    "can_route",
    "can_approve",
    "execute_tasks",
    "route_authority",
    "routing_authority",
    "approval_authority",
    "execution_authority",
    "final_authority",
)

BOUNDARIES: tuple[str, ...] = (
    "artifact adoption only",
    "advisory catalog only",
    "no model calls",
    "no model routing",
    "no worker launch",
    "no executable binding",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP/tool invocation",
    "no Dream execution",
    "no Replay janitor apply",
    "no Docker/subprocess",
    "no network",
    "no database write",
    "no route behavior change",
    "no auth policy change",
    "no approval-token enforcement",
    "no automatic authority escalation",
)

MODEL_ROLE_CATALOG_ADOPTION_GUARDRAIL_NOTE = (
    "Model Role Catalog Adoption is artifact-only: it may replace the active "
    "advisory model-role registry with the reviewed MODEL.N4 proposed catalog "
    "and write backup plus receipt artifacts. It does not route tasks, call "
    "models, launch workers, create executable model bindings, run validation "
    "or benchmarks, apply patches, invoke MCP tools, contact networks, write "
    "databases, change route or auth behavior, enforce approval tokens, or "
    "grant automatic authority."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "ADOPT.MODEL.2",
    "title": "Post-Adoption Role Coverage Recheck",
    "reason": (
        "After artifact-level adoption, re-run report-only coverage checks "
        "against the active 10-role advisory catalog."
    ),
}


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _unique(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(str(value) for value in values if str(value)))


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _split_segments(value: str) -> list[str]:
    return [segment for segment in value.replace("\\", "/").split("/") if segment]


def _path_has_traversal(value: str) -> bool:
    return any(segment == ".." for segment in _split_segments(value))


def _input_path_blockers(path: str | Path | None, label: str, *, required: bool) -> list[str]:
    if path is None or str(path).strip() == "":
        return [f"{label} path is required"] if required else []
    if _path_has_traversal(str(path).strip()):
        return [f"{label} path must not contain traversal segments"]
    return []


def read_json_input(
    path: str | Path | None,
    label: str,
    *,
    required: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Read a JSON input file and return blockers instead of raising."""
    blockers = _input_path_blockers(path, label, required=required)
    if blockers:
        return None, blockers
    if path is None or str(path).strip() == "":
        return None, []
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


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _role_id(role: dict[str, Any]) -> str:
    return str(role.get("role_id") or "").strip()


def _role_ids(roles: list[dict[str, Any]]) -> list[str]:
    return [_role_id(role) for role in roles if _role_id(role)]


def _is_meaningful(value: Any) -> bool:
    return value not in (False, None, "", [], {})


def _truthy_key_hits(data: dict[str, Any], keys: tuple[str, ...], label: str) -> list[str]:
    hits: list[str] = []
    for key in keys:
        if data.get(key) is True:
            phrase = key.replace("_", " ")
            if key in MODEL_ROUTING_KEYS:
                phrase = "model routing"
            elif key in MODEL_CALL_KEYS:
                phrase = "model calls"
            elif key in WORKER_LAUNCH_KEYS:
                phrase = "worker launch"
            hits.append(f"{label} {phrase} enabled by {key}")
    guardrails = data.get("guardrails")
    if isinstance(guardrails, dict):
        for key in keys:
            if guardrails.get(key) is True:
                phrase = key.replace("_", " ")
                if key in MODEL_ROUTING_KEYS:
                    phrase = "model routing"
                elif key in MODEL_CALL_KEYS:
                    phrase = "model calls"
                elif key in WORKER_LAUNCH_KEYS:
                    phrase = "worker launch"
                hits.append(f"{label} {phrase} guardrail unexpectedly true: {key}")
    return hits


def _role_safety_blockers(roles: list[dict[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    advisory_failures: list[str] = []
    executable_failures: list[str] = []
    model_id_authority_hits: list[str] = []
    model_routing_hits: list[str] = []
    model_call_hits: list[str] = []
    worker_launch_hits: list[str] = []
    forbidden_authority_hits: list[str] = []

    ids = _role_ids(roles)
    for role_id in sorted({role_id for role_id in ids if ids.count(role_id) > 1}):
        blockers.append(f"duplicate role_id: {role_id}")

    for index, role in enumerate(roles):
        role_id = _role_id(role) or f"#{index}"
        if role.get("advisory_only") is not True:
            advisory_failures.append(role_id)
            blockers.append(f"role {role_id} advisory_only must be true")
        if role.get("executable_binding_allowed") is True:
            executable_failures.append(role_id)
            blockers.append(f"role {role_id} executable_binding_allowed must be false")
        for flag in FORBIDDEN_AUTHORITY_FLAGS:
            if role.get(flag) is True:
                reason = f"role {role_id} includes forbidden authority flag: {flag}"
                forbidden_authority_hits.append(reason)
                blockers.append(reason)
        for reason in _truthy_key_hits(role, MODEL_ROUTING_KEYS, f"role {role_id}"):
            model_routing_hits.append(reason)
            blockers.append(reason)
        for reason in _truthy_key_hits(role, MODEL_CALL_KEYS, f"role {role_id}"):
            model_call_hits.append(reason)
            blockers.append(reason)
        for reason in _truthy_key_hits(role, WORKER_LAUNCH_KEYS, f"role {role_id}"):
            worker_launch_hits.append(reason)
            blockers.append(reason)
        model_id_policy = str(role.get("model_id_policy") or "descriptive_metadata_only").strip()
        if model_id_policy != "descriptive_metadata_only":
            reason = f"role {role_id} model_id_policy must keep model_ids descriptive metadata only"
            model_id_authority_hits.append(reason)
            blockers.append(reason)
        for key in MODEL_ID_AUTHORITY_KEYS:
            if key in role and _is_meaningful(role.get(key)):
                reason = f"role {role_id} defines executable model authority via {key}"
                model_id_authority_hits.append(reason)
                blockers.append(reason)
        for key, value in role.items():
            low = str(key).lower()
            if any(fragment in low for fragment in AUTHORITY_KEY_FRAGMENTS) and bool(value):
                reason = f"role {role_id} claims executable authority via {key}"
                forbidden_authority_hits.append(reason)
                blockers.append(reason)

    checks = {
        "advisory_only_failures": _unique(advisory_failures),
        "executable_binding_failures": _unique(executable_failures),
        "model_id_authority_hits": _unique(model_id_authority_hits),
        "model_routing_hits": _unique(model_routing_hits),
        "model_call_hits": _unique(model_call_hits),
        "worker_launch_hits": _unique(worker_launch_hits),
        "forbidden_authority_hits": _unique(forbidden_authority_hits),
    }
    return blockers, checks


def _catalog_shape_blockers(
    active_catalog_data: dict[str, Any] | None,
    proposed_catalog_data: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    if active_catalog_data is None:
        blockers.append("active catalog is missing or malformed")
        active_catalog_data = {}
    if proposed_catalog_data is None:
        blockers.append("proposed catalog is missing or malformed")
        proposed_catalog_data = {}
    if not isinstance(active_catalog_data, dict):
        blockers.append("active catalog must contain a JSON object")
        active_catalog_data = {}
    if not isinstance(proposed_catalog_data, dict):
        blockers.append("proposed catalog must contain a JSON object")
        proposed_catalog_data = {}

    if active_catalog_data.get("report_kind") != ACTIVE_REGISTRY_REPORT_KIND:
        blockers.append("active catalog report_kind must be model_role_registry")
    if proposed_catalog_data.get("report_kind") != PROPOSED_REGISTRY_REPORT_KIND:
        blockers.append("proposed catalog report_kind must be proposed_model_role_registry")
    if not isinstance(active_catalog_data.get("roles"), list):
        blockers.append("active catalog roles must be a list")
    if not isinstance(proposed_catalog_data.get("roles"), list):
        blockers.append("proposed catalog roles must be a list")

    return (
        _list_of_dicts(active_catalog_data.get("roles")),
        _list_of_dicts(proposed_catalog_data.get("roles")),
        blockers,
    )


def _adoption_status(
    *,
    blockers: list[str],
    incomplete: list[str],
    warnings: list[str],
) -> str:
    if blockers:
        return "model_role_catalog_adoption_blocked"
    if incomplete:
        return "model_role_catalog_adoption_incomplete"
    if warnings:
        return "model_role_catalog_adoption_complete_with_warnings"
    return "model_role_catalog_adoption_complete"


def build_model_role_catalog_adoption(
    *,
    active_catalog_path: str | Path | None,
    active_catalog_data: dict[str, Any] | None,
    proposed_catalog_path: str | Path | None,
    proposed_catalog_data: dict[str, Any] | None,
    backup_paths: dict[str, str] | None = None,
    receipt_paths: dict[str, str] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic ADOPT.MODEL.1 adoption receipt."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(active_catalog_path, "active catalog", required=True)
    blockers += _input_path_blockers(proposed_catalog_path, "proposed catalog", required=True)
    warnings = ["post-adoption role coverage recheck is still needed"]
    incomplete: list[str] = []

    active_roles, proposed_roles, shape_blockers = _catalog_shape_blockers(active_catalog_data, proposed_catalog_data)
    blockers += shape_blockers

    active_ids = _role_ids(active_roles)
    proposed_ids = _role_ids(proposed_roles)
    active_id_set = set(active_ids)
    proposed_id_set = set(proposed_ids)
    added_roles = [role_id for role_id in proposed_ids if role_id not in active_id_set]
    preserved_roles = [role_id for role_id in active_ids if role_id in proposed_id_set]

    for role_id in sorted(active_id_set - proposed_id_set):
        blockers.append(f"proposed catalog loses required existing role: {role_id}")
    for role_id in ADDED_ROLE_IDS:
        if role_id not in proposed_id_set:
            blockers.append(f"proposed catalog is missing expected added role: {role_id}")

    declared_count = proposed_catalog_data.get("role_count") if isinstance(proposed_catalog_data, dict) else None
    if isinstance(declared_count, int) and declared_count != len(proposed_roles):
        blockers.append(f"proposed catalog role_count {declared_count} does not match roles {len(proposed_roles)}")

    if isinstance(proposed_catalog_data, dict):
        for reason in _truthy_key_hits(proposed_catalog_data, MODEL_ROUTING_KEYS, "proposed catalog"):
            blockers.append(reason)
        for reason in _truthy_key_hits(proposed_catalog_data, MODEL_CALL_KEYS, "proposed catalog"):
            blockers.append(reason)
        for reason in _truthy_key_hits(proposed_catalog_data, WORKER_LAUNCH_KEYS, "proposed catalog"):
            blockers.append(reason)

    role_blockers, role_checks = _role_safety_blockers(proposed_roles)
    blockers += role_blockers

    backup_paths = dict(backup_paths or {})
    receipt_paths = dict(receipt_paths or {})
    if not blockers:
        if not backup_paths.get("json") or not backup_paths.get("markdown"):
            incomplete.append("backup artifacts are missing")
        if not receipt_paths.get("json") or not receipt_paths.get("markdown"):
            incomplete.append("receipt artifacts are missing")

    blockers = _unique(blockers)
    incomplete = _unique(incomplete)
    warnings = _unique(warnings)
    status = _adoption_status(blockers=blockers, incomplete=incomplete, warnings=warnings)

    safety = {
        "advisory_only_confirmed": bool(proposed_roles)
        and not role_checks["advisory_only_failures"]
        and all(role.get("advisory_only") is True for role in proposed_roles),
        "executable_binding_allowed_confirmed_false": bool(proposed_roles)
        and not role_checks["executable_binding_failures"]
        and all(role.get("executable_binding_allowed") is False for role in proposed_roles),
        "model_routing_enabled_confirmed_false": not role_checks["model_routing_hits"]
        and not any(reason for reason in blockers if "model_routing" in reason or "routing" in reason),
        "model_calls_allowed_confirmed_false": not role_checks["model_call_hits"]
        and not any(reason for reason in blockers if "model_call" in reason or "model calls" in reason),
        "worker_launch_allowed_confirmed_false": not role_checks["worker_launch_hits"]
        and not any(reason for reason in blockers if "worker_launch" in reason or "worker launch" in reason),
        "model_ids_metadata_only_confirmed": not role_checks["model_id_authority_hits"],
    }

    return {
        "report_kind": REPORT_KIND,
        "adoption_id": "model-role-catalog-adoption",
        "adopted_phase_id": ADOPTED_PHASE_ID,
        "source_proposal_phase_id": SOURCE_PROPOSAL_PHASE_ID,
        "source_proposed_catalog_path": str(proposed_catalog_path or ""),
        "active_catalog_path": str(active_catalog_path or ""),
        "backup_paths": backup_paths,
        "receipt_paths": receipt_paths,
        "adoption_status": status,
        "previous_role_count": len(active_roles),
        "adopted_role_count": len(proposed_roles),
        "added_roles": added_roles,
        "preserved_roles": preserved_roles,
        "role_count_delta": len(proposed_roles) - len(active_roles),
        **safety,
        "safety_checks": {
            **safety,
            **role_checks,
            "expected_added_roles": list(ADDED_ROLE_IDS),
            "expected_added_roles_present": all(role_id in proposed_id_set for role_id in ADDED_ROLE_IDS),
            "existing_roles_preserved": active_id_set <= proposed_id_set,
            "passed": not blockers,
        },
        "warnings": warnings,
        "incomplete_reasons": incomplete,
        "blocked_reasons": blockers,
        "guardrail_note": MODEL_ROLE_CATALOG_ADOPTION_GUARDRAIL_NOTE,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "adoption_statuses": list(ADOPTION_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_model_role_catalog_adoption_markdown(receipt: dict[str, Any]) -> str:
    """Render an ADOPT.MODEL.1 adoption receipt as Markdown."""
    next_phase = receipt.get("recommended_next_phase") if isinstance(receipt.get("recommended_next_phase"), dict) else {}
    safety = receipt.get("safety_checks") if isinstance(receipt.get("safety_checks"), dict) else {}
    backup_paths = receipt.get("backup_paths") if isinstance(receipt.get("backup_paths"), dict) else {}
    lines: list[str] = [
        "# Model Role Catalog Adoption Receipt",
        "",
        f"> {receipt.get('guardrail_note', MODEL_ROLE_CATALOG_ADOPTION_GUARDRAIL_NOTE)}",
        "",
        "_Artifact only: ADOPT.MODEL.1 adopts an advisory model-role catalog. It grants no model routing, model calls, worker launch, or executable model binding._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Adoption status:** `{_md(receipt.get('adoption_status', ''))}`",
        f"- **Adoption id:** `{_md(receipt.get('adoption_id', ''))}`",
        f"- **Adopted phase:** `{_md(receipt.get('adopted_phase_id', ''))}`",
        f"- **Source proposal phase:** `{_md(receipt.get('source_proposal_phase_id', ''))}`",
        f"- **Previous role count:** {receipt.get('previous_role_count', 0)}",
        f"- **Adopted role count:** {receipt.get('adopted_role_count', 0)}",
        "",
        "## Source and Active Catalog",
        "",
        f"- **Source proposed catalog:** `{_md(receipt.get('source_proposed_catalog_path', ''))}`",
        f"- **Active catalog:** `{_md(receipt.get('active_catalog_path', ''))}`",
        "",
        "## Role Adoption",
        "",
        "- **Added roles:**",
    ]
    _render_list(lines, list(receipt.get("added_roles") or []), code=True)
    lines += ["- **Preserved roles:**"]
    _render_list(lines, list(receipt.get("preserved_roles") or []), code=True)
    lines += ["## Safety Confirmations", ""]
    for key in (
        "advisory_only_confirmed",
        "executable_binding_allowed_confirmed_false",
        "model_routing_enabled_confirmed_false",
        "model_calls_allowed_confirmed_false",
        "worker_launch_allowed_confirmed_false",
        "model_ids_metadata_only_confirmed",
    ):
        lines.append(f"- `{_md(key)}`: {str(bool(receipt.get(key))).lower()}")
    for key in sorted(safety):
        if key.endswith("_hits") and safety[key]:
            lines.append(f"- **{_md(key)}:** {_md(safety[key])}")
    lines += ["", "## Backups", ""]
    if backup_paths:
        for key in sorted(backup_paths):
            lines.append(f"- **{_md(key)}:** `{_md(backup_paths[key])}`")
    else:
        lines.append("_None._")
    lines += ["", "## Warnings", ""]
    _render_list(lines, list(receipt.get("warnings") or []))
    lines += ["## Blocked Reasons", ""]
    _render_list(lines, list(receipt.get("blocked_reasons") or []))
    lines += ["## Boundaries / Guardrails", ""]
    for boundary in receipt.get("boundaries") or []:
        lines.append(f"- {_md(boundary)}")
    guardrails = receipt.get("guardrails") if isinstance(receipt.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines += [
        "",
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
    ]
    return "\n".join(lines)


def _adopted_registry_from_proposed(proposed_catalog_data: dict[str, Any], proposed_catalog_path: str | Path) -> dict[str, Any]:
    registry = build_model_role_registry(
        role_catalog={"roles": _list_of_dicts(proposed_catalog_data.get("roles"))},
        role_catalog_path=str(proposed_catalog_path or ""),
    )
    registry["recommended_next_phase"] = dict(RECOMMENDED_NEXT_PHASE)
    registry["boundaries"] = list(registry.get("boundaries") or []) + [
        "ADOPT.MODEL.1 adopted this advisory catalog as an artifact only.",
        "ADOPT.MODEL.1 does not make any model role executable.",
    ]
    return registry


def write_model_role_catalog_adoption(
    *,
    active_catalog_path: str | Path,
    proposed_catalog_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    active_catalog_md_path: str | Path | None = None,
    active_catalog_data: dict[str, Any] | None = None,
    proposed_catalog_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Adopt the proposed catalog artifact and write backup/receipt artifacts."""
    blockers = list(input_blockers or [])
    if active_catalog_data is None and not blockers:
        active_catalog_data, read_blockers = read_json_input(active_catalog_path, "active catalog", required=True)
        blockers += read_blockers
    if proposed_catalog_data is None and not blockers:
        proposed_catalog_data, read_blockers = read_json_input(proposed_catalog_path, "proposed catalog", required=True)
        blockers += read_blockers

    out_dir = Path(output_dir)
    backup_dir = out_dir / BACKUP_DIR_NAME
    backup_paths = {
        "json": str(backup_dir / BACKUP_JSON_NAME),
        "markdown": str(backup_dir / BACKUP_MD_NAME),
    }
    receipt_paths = {
        "json": str(out_dir / JSON_NAME),
        "markdown": str(out_dir / MD_NAME),
    }

    receipt = build_model_role_catalog_adoption(
        active_catalog_path=active_catalog_path,
        active_catalog_data=active_catalog_data,
        proposed_catalog_path=proposed_catalog_path,
        proposed_catalog_data=proposed_catalog_data,
        backup_paths=backup_paths,
        receipt_paths=receipt_paths,
        input_blockers=blockers,
    )

    if receipt["adoption_status"] != "model_role_catalog_adoption_blocked":
        adopted_registry = _adopted_registry_from_proposed(proposed_catalog_data or {}, proposed_catalog_path)
        if adopted_registry.get("validation_status") == "model_roles_blocked":
            receipt = build_model_role_catalog_adoption(
                active_catalog_path=active_catalog_path,
                active_catalog_data=active_catalog_data,
                proposed_catalog_path=proposed_catalog_path,
                proposed_catalog_data=proposed_catalog_data,
                backup_paths=backup_paths,
                receipt_paths=receipt_paths,
                input_blockers=list(adopted_registry.get("blocked_reasons") or []),
            )
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            backup_dir.mkdir(parents=True, exist_ok=True)
            active_path = Path(active_catalog_path)
            active_md_path = Path(active_catalog_md_path) if active_catalog_md_path else active_path.with_suffix(".md")
            backup_json = Path(backup_paths["json"])
            backup_md = Path(backup_paths["markdown"])
            backup_json.write_text(
                json.dumps(active_catalog_data, indent=2, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            if active_md_path.is_file():
                backup_md.write_text(active_md_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                backup_md.write_text(render_model_role_registry_markdown(active_catalog_data or {}), encoding="utf-8")
            active_path.write_text(
                json.dumps(adopted_registry, indent=2, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            active_md_path.write_text(render_model_role_registry_markdown(adopted_registry), encoding="utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(receipt_paths["json"])
    md_path = Path(receipt_paths["markdown"])
    json_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_catalog_adoption_markdown(receipt), encoding="utf-8")
    ok = receipt.get("adoption_status") in {
        "model_role_catalog_adoption_complete",
        "model_role_catalog_adoption_complete_with_warnings",
    }
    return {
        "ok": ok,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "receipt": receipt,
    }
