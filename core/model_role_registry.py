"""MODEL.N1 - Model Role Registry / Tower Card Contract (report-only).

Defines advisory model/role tower cards before any routing, worker launch,
model selection, Commander execution, or executable model binding exists.
MODEL.N1 writes deterministic JSON and Markdown artifacts only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_registry"
JSON_NAME = "model_role_registry.json"
MD_NAME = "model_role_registry.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry"

ALLOWED_ROLE_KINDS: tuple[str, ...] = (
    "scout",
    "planner",
    "implementer",
    "reviewer",
    "evidence_checker",
    "risk_auditor",
    "summarizer",
    "fallback",
    "local_offline",
    "unknown",
)

COST_TIERS: tuple[str, ...] = ("free", "low", "medium", "high", "unknown")
LATENCY_TIERS: tuple[str, ...] = ("fast", "medium", "slow", "unknown")
CONTEXT_TIERS: tuple[str, ...] = ("small", "medium", "large", "unknown")
RELIABILITY_TIERS: tuple[str, ...] = ("experimental", "normal", "strong", "unknown")
RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "unknown")

VALIDATION_STATUSES: tuple[str, ...] = (
    "model_roles_ready",
    "model_roles_ready_with_warnings",
    "model_roles_incomplete",
    "model_roles_blocked",
)

ROLE_CARD_FIELDS: tuple[str, ...] = (
    "role_id",
    "display_name",
    "role_kind",
    "description",
    "strengths",
    "weaknesses",
    "best_for",
    "not_for",
    "risk_level",
    "cost_tier",
    "latency_tier",
    "context_tier",
    "reliability_tier",
    "evidence_expectation",
    "allowed_task_types",
    "forbidden_task_types",
    "advisory_only",
    "executable_binding_allowed",
    "model_ids",
    "fallback_roles",
    "human_review_required",
    "notes",
)

REQUIRED_CARD_FIELDS: tuple[str, ...] = (
    "role_id",
    "display_name",
    "role_kind",
    "description",
    "strengths",
    "best_for",
    "not_for",
    "forbidden_task_types",
    "advisory_only",
    "executable_binding_allowed",
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

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "model_call_performed",
    "routing_changed",
    "worker_launch_performed",
    "commander_execution_performed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_used",
    "network_contacted",
    "database_write_performed",
    "auth_policy_changed",
    "route_behavior_changed",
    "executable_model_binding_created",
    "automatic_assignment_performed",
    "commander_artifacts_mutated",
)

MODEL_ROLE_REGISTRY_GUARDRAIL_NOTE = (
    "Model Role Registry is report-only: it defines and validates advisory "
    "model/role tower cards. It does not route tasks, call models, launch "
    "workers, bind Commander roles to executable model IDs, change model "
    "selection behavior, apply patches, run validation, run benchmarks, invoke "
    "MCP tools, execute Dream actions, apply Replay janitor actions, use "
    "Docker/subprocess, contact networks, write databases, change auth policy, "
    "change route behavior, or mutate Commander artifacts."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "MODEL.N2",
    "title": "Model Role Coverage Report",
    "reason": (
        "After advisory tower cards exist, compare Commander advisory roles "
        "from CMD.N5/CMD.N6 against MODEL.N1 cards and report covered, missing, "
        "risky, or overpowered roles without routing or execution."
    ),
}

COVERAGE_REQUIREMENTS: tuple[str, ...] = (
    "scout",
    "planner",
    "implementer",
    "reviewer",
    "evidence_checker",
    "risk_auditor",
    "fallback",
)

_TIER_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("risk_level", RISK_LEVELS),
    ("cost_tier", COST_TIERS),
    ("latency_tier", LATENCY_TIERS),
    ("context_tier", CONTEXT_TIERS),
    ("reliability_tier", RELIABILITY_TIERS),
)

_AUTHORITY_KEY_FRAGMENTS: tuple[str, ...] = (
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


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _dedupe(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(str(value) for value in values if str(value)))


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
    return text, blockers


def _split_segments(value: str) -> list[str]:
    return [segment for segment in value.replace("\\", "/").split("/") if segment]


def _path_has_traversal(value: str) -> bool:
    return any(segment == ".." for segment in _split_segments(value))


def _input_path_blockers(path: str | Path | None, label: str) -> list[str]:
    if path is None or str(path).strip() == "":
        return []
    if _path_has_traversal(str(path).strip()):
        return [f"{label} path must not contain traversal segments"]
    return []


def read_json_input(path: str | Path | None, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Read a manual JSON input file and return blockers instead of raising."""
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


def _default_card(
    *,
    role_id: str,
    display_name: str,
    role_kind: str,
    description: str,
    strengths: list[str],
    weaknesses: list[str],
    best_for: list[str],
    not_for: list[str],
    risk_level: str,
    cost_tier: str,
    latency_tier: str,
    context_tier: str,
    reliability_tier: str,
    evidence_expectation: str,
    allowed_task_types: list[str],
    forbidden_task_types: list[str],
    fallback_roles: list[str],
    human_review_required: bool = False,
) -> dict[str, Any]:
    return {
        "role_id": role_id,
        "display_name": display_name,
        "role_kind": role_kind,
        "description": description,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "best_for": best_for,
        "not_for": not_for,
        "risk_level": risk_level,
        "cost_tier": cost_tier,
        "latency_tier": latency_tier,
        "context_tier": context_tier,
        "reliability_tier": reliability_tier,
        "evidence_expectation": evidence_expectation,
        "allowed_task_types": allowed_task_types,
        "forbidden_task_types": forbidden_task_types,
        "advisory_only": True,
        "executable_binding_allowed": False,
        "model_ids": [],
        "fallback_roles": fallback_roles,
        "human_review_required": human_review_required,
        "notes": ["Advisory card only; no executable model binding or routing authority."],
    }


def default_model_role_cards() -> list[dict[str, Any]]:
    """Return the deterministic default MODEL.N1 advisory tower cards."""
    return [
        _default_card(
            role_id="fast_scout",
            display_name="Fast Scout",
            role_kind="scout",
            description="Quickly surveys a task and reports shallow findings for humans or later planning.",
            strengths=["quick triage", "broad summary", "shallow planning"],
            weaknesses=["limited depth", "not a final authority"],
            best_for=["quick triage", "broad summary", "shallow planning"],
            not_for=["final patch authority", "risky refactors"],
            risk_level="medium",
            cost_tier="low",
            latency_tier="fast",
            context_tier="medium",
            reliability_tier="normal",
            evidence_expectation="summarize visible evidence and name uncertainty",
            allowed_task_types=["triage", "summary", "shallow_planning"],
            forbidden_task_types=["final_patch_authority", "risky_refactor"],
            fallback_roles=["local_fallback"],
        ),
        _default_card(
            role_id="planner",
            display_name="Planner",
            role_kind="planner",
            description="Shapes scope and decomposes work before any Commander execution design exists.",
            strengths=["decomposition", "scope shaping", "Commander preflight reasoning"],
            weaknesses=["does not mutate code", "does not approve execution"],
            best_for=["decomposition", "scope shaping", "Commander preflight reasoning"],
            not_for=["direct code mutation", "worker launch"],
            risk_level="low",
            cost_tier="medium",
            latency_tier="medium",
            context_tier="large",
            reliability_tier="strong",
            evidence_expectation="name assumptions, dependencies, and review gates",
            allowed_task_types=["planning", "decomposition", "preflight_reasoning"],
            forbidden_task_types=["direct_code_mutation", "worker_launch"],
            fallback_roles=["fast_scout"],
        ),
        _default_card(
            role_id="patch_implementer",
            display_name="Patch Implementer",
            role_kind="implementer",
            description="Prepares patch proposals for human review without applying patches.",
            strengths=["patch proposal preparation", "localized implementation reasoning"],
            weaknesses=["no patch apply authority", "no final approval"],
            best_for=["patch proposal preparation"],
            not_for=["patch apply", "final approval", "hidden mutation"],
            risk_level="medium",
            cost_tier="medium",
            latency_tier="medium",
            context_tier="large",
            reliability_tier="normal",
            evidence_expectation="cite touched files, tests, and review risks",
            allowed_task_types=["patch_proposal_preparation"],
            forbidden_task_types=["patch_apply", "final_approval", "hidden_mutation"],
            fallback_roles=["planner"],
            human_review_required=True,
        ),
        _default_card(
            role_id="code_reviewer",
            display_name="Code Reviewer",
            role_kind="reviewer",
            description="Critiques proposed work and searches for defects before human approval.",
            strengths=["critique", "bug finding", "consistency review"],
            weaknesses=["no final apply authority", "cannot approve patches alone"],
            best_for=["critique", "bug finding", "consistency review"],
            not_for=["final apply authority", "automatic merge"],
            risk_level="medium",
            cost_tier="medium",
            latency_tier="medium",
            context_tier="large",
            reliability_tier="strong",
            evidence_expectation="cite concrete file and line evidence when available",
            allowed_task_types=["review", "consistency_check", "bug_finding"],
            forbidden_task_types=["final_apply_authority", "automatic_merge"],
            fallback_roles=["evidence_checker"],
            human_review_required=True,
        ),
        _default_card(
            role_id="evidence_checker",
            display_name="Evidence Checker",
            role_kind="evidence_checker",
            description="Matches validation claims to evidence and reports missing proof.",
            strengths=["validation claim matching", "missing evidence detection"],
            weaknesses=["does not run validation", "does not create new evidence"],
            best_for=["validation claim matching", "missing evidence detection"],
            not_for=["running validation automatically", "benchmark execution"],
            risk_level="low",
            cost_tier="low",
            latency_tier="fast",
            context_tier="medium",
            reliability_tier="strong",
            evidence_expectation="list claim, evidence, and gap rows",
            allowed_task_types=["evidence_review", "claim_check"],
            forbidden_task_types=["run_validation", "run_benchmark"],
            fallback_roles=["fast_scout"],
        ),
        _default_card(
            role_id="risk_auditor",
            display_name="Risk Auditor",
            role_kind="risk_auditor",
            description="Reviews file scope, mutation risk, approval boundaries, and authority limits.",
            strengths=["file scope safety", "mutation risk review", "approval boundary checks"],
            weaknesses=["does not execute", "does not approve changes"],
            best_for=["file scope safety", "mutation risk", "approval boundaries"],
            not_for=["execution", "approval authority"],
            risk_level="medium",
            cost_tier="medium",
            latency_tier="medium",
            context_tier="large",
            reliability_tier="strong",
            evidence_expectation="state risk, affected surface, and required human decision",
            allowed_task_types=["risk_review", "scope_review", "approval_boundary_review"],
            forbidden_task_types=["execution", "approval_authority"],
            fallback_roles=["code_reviewer"],
            human_review_required=True,
        ),
        _default_card(
            role_id="local_fallback",
            display_name="Local Fallback",
            role_kind="local_offline",
            description="Low-cost offline fallback for small summaries and no-network contexts.",
            strengths=["small offline summaries", "cheap fallback", "no-network mode"],
            weaknesses=["small context", "not final authority"],
            best_for=["small offline summaries", "cheap fallback", "no-network mode"],
            not_for=["large context", "final authority"],
            risk_level="medium",
            cost_tier="free",
            latency_tier="fast",
            context_tier="small",
            reliability_tier="experimental",
            evidence_expectation="keep summaries short and mark uncertainty",
            allowed_task_types=["small_summary", "offline_fallback"],
            forbidden_task_types=["large_context_analysis", "final_authority"],
            fallback_roles=[],
        ),
    ]


def _catalog_shape(
    role_catalog: dict[str, Any] | None,
) -> tuple[str, list[dict[str, Any]], list[str], list[str]]:
    if role_catalog is None:
        return "default_catalog", default_model_role_cards(), [], []
    roles = role_catalog.get("roles")
    if not isinstance(roles, list):
        return "manual_role_catalog", [], [], ["role_catalog roles must be a list"]
    warnings: list[str] = []
    blockers: list[str] = []
    normalized: list[dict[str, Any]] = []
    if not roles:
        warnings.append("manual role catalog contains no roles")
    for index, item in enumerate(roles):
        if not isinstance(item, dict):
            blockers.append(f"role_catalog roles[{index}] must be a JSON object")
            continue
        normalized.append(dict(item))
    return "manual_role_catalog", normalized, warnings, blockers


def _normalize_tier(
    *,
    role_id: str,
    raw: dict[str, Any],
    field: str,
    allowed: tuple[str, ...],
    warnings: list[str],
) -> str:
    value = str(raw.get(field) or "unknown").strip()
    if value not in allowed:
        warnings.append(f"role {role_id} has invalid {field} {value}; stored as unknown")
        return "unknown"
    if value == "unknown":
        warnings.append(f"role {role_id} has unknown {field}")
    return value


def _authority_claim_blockers(role_id: str, raw: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key, value in raw.items():
        low = str(key).lower()
        if any(fragment in low for fragment in _AUTHORITY_KEY_FRAGMENTS) and bool(value):
            blockers.append(f"role {role_id} claims executable authority via {key}")
    return blockers


def _normalize_card(
    raw: dict[str, Any],
    *,
    index: int,
    seen_ids: set[str],
) -> tuple[dict[str, Any], list[str], list[str], list[dict[str, Any]]]:
    warnings: list[str] = []
    blockers: list[str] = []
    missing_fields: list[dict[str, Any]] = []

    raw_role_id = raw.get("role_id", f"#{index}")
    role_id, id_blockers = _safe_identifier(raw_role_id, f"role_id {raw_role_id}")
    blockers += id_blockers
    if role_id in seen_ids:
        blockers.append(f"duplicate role_id: {role_id}")
    seen_ids.add(role_id)

    missing = [field for field in REQUIRED_CARD_FIELDS if field not in raw or raw.get(field) in (None, "", [])]
    if missing:
        missing_fields.append({"role_id": role_id, "index": index, "missing_fields": missing})

    role_kind = str(raw.get("role_kind") or "unknown").strip()
    if role_kind not in ALLOWED_ROLE_KINDS:
        blockers.append(f"role {role_id} has invalid role_kind: {role_kind}")
        role_kind = "unknown"
    elif role_kind == "unknown":
        warnings.append(f"role {role_id} has unknown role_kind")

    tiers = {
        field: _normalize_tier(role_id=role_id, raw=raw, field=field, allowed=allowed, warnings=warnings)
        for field, allowed in _TIER_FIELDS
    }

    strengths = _strings(raw.get("strengths"))
    weaknesses = _strings(raw.get("weaknesses"))
    best_for = _strings(raw.get("best_for"))
    not_for = _strings(raw.get("not_for"))
    allowed_task_types = _strings(raw.get("allowed_task_types"))
    forbidden_task_types = _strings(raw.get("forbidden_task_types"))
    model_ids = _strings(raw.get("model_ids"))
    fallback_roles = _strings(raw.get("fallback_roles"))
    notes = _strings(raw.get("notes"))

    if not strengths:
        warnings.append(f"role {role_id} has empty strengths")
    if not best_for:
        warnings.append(f"role {role_id} has empty best_for")
    if not not_for:
        warnings.append(f"role {role_id} has empty not_for")
    if not forbidden_task_types:
        warnings.append(f"role {role_id} has empty forbidden_task_types")

    advisory_only = True if "advisory_only" not in raw else bool(raw.get("advisory_only"))
    executable_binding_allowed = bool(raw.get("executable_binding_allowed", False))
    human_review_required = bool(raw.get("human_review_required", False))

    if advisory_only is not True:
        blockers.append(f"role {role_id} advisory_only must be true")
    if executable_binding_allowed is True:
        blockers.append(f"role {role_id} executable_binding_allowed must be false")
    if role_kind in {"implementer", "reviewer", "risk_auditor"} and human_review_required is not True:
        blockers.append(f"role {role_id} human_review_required must be true for {role_kind} roles")

    for flag in FORBIDDEN_AUTHORITY_FLAGS:
        if flag in raw:
            blockers.append(f"role {role_id} includes forbidden authority flag: {flag}")
    blockers += _authority_claim_blockers(role_id, raw)

    conflict = sorted(set(allowed_task_types) & set(forbidden_task_types))
    if conflict:
        blockers.append(
            f"role {role_id} allowed_task_types conflicts with forbidden_task_types: {', '.join(conflict)}"
        )

    card = {
        "role_id": role_id if not id_blockers else str(raw_role_id or ""),
        "display_name": str(raw.get("display_name") or "").strip(),
        "role_kind": role_kind,
        "description": str(raw.get("description") or "").strip(),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "best_for": best_for,
        "not_for": not_for,
        "risk_level": tiers["risk_level"],
        "cost_tier": tiers["cost_tier"],
        "latency_tier": tiers["latency_tier"],
        "context_tier": tiers["context_tier"],
        "reliability_tier": tiers["reliability_tier"],
        "evidence_expectation": str(raw.get("evidence_expectation") or "").strip(),
        "allowed_task_types": allowed_task_types,
        "forbidden_task_types": forbidden_task_types,
        "advisory_only": advisory_only,
        "executable_binding_allowed": executable_binding_allowed,
        "model_ids": model_ids,
        "model_id_policy": "descriptive_metadata_only",
        "fallback_roles": fallback_roles,
        "human_review_required": human_review_required,
        "notes": notes,
    }
    return card, warnings, blockers, missing_fields


def _validate_fallbacks(roles: list[dict[str, Any]]) -> list[str]:
    known = {str(role.get("role_id")) for role in roles}
    blockers: list[str] = []
    for role in roles:
        role_id = str(role.get("role_id"))
        for fallback in role.get("fallback_roles") or []:
            if fallback not in known:
                blockers.append(f"role {role_id} references unknown fallback role: {fallback}")
    return blockers


def _is_weak_role(role: dict[str, Any]) -> bool:
    unknown_tiers = sum(1 for field, _allowed in _TIER_FIELDS if role.get(field) == "unknown")
    return (
        role.get("role_kind") == "unknown"
        or not role.get("strengths")
        or not role.get("best_for")
        or unknown_tiers >= 3
    )


def _coverage_matrix(roles: list[dict[str, Any]]) -> dict[str, Any]:
    covered: dict[str, list[str]] = {requirement: [] for requirement in COVERAGE_REQUIREMENTS}
    for role in roles:
        role_id = str(role.get("role_id"))
        kind = str(role.get("role_kind"))
        if kind in covered:
            covered[kind].append(role_id)
        if kind == "local_offline" or role_id.endswith("fallback") or "fallback" in role_id:
            covered["fallback"].append(role_id)
    missing = [key for key in COVERAGE_REQUIREMENTS if not covered[key]]
    return {
        "required_capabilities": list(COVERAGE_REQUIREMENTS),
        "covered": {key: covered[key] for key in COVERAGE_REQUIREMENTS},
        "missing": missing,
        "coverage_status": "meaningful_coverage" if not missing else "partial_coverage",
    }


def _risk_and_cost_tiers(roles: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for field, allowed in _TIER_FIELDS:
        counts = {value: 0 for value in allowed}
        for role in roles:
            value = str(role.get(field) or "unknown")
            counts[value if value in counts else "unknown"] += 1
        result[field] = {key: counts[key] for key in allowed if counts[key]}
    return result


def _fallback_role_map(roles: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {str(role.get("role_id")): list(role.get("fallback_roles") or []) for role in roles}


def _forbidden_authority_checks(roles: list[dict[str, Any]], blocked: list[str]) -> dict[str, Any]:
    hits = [reason for reason in blocked if "forbidden authority flag" in reason or "claims executable authority" in reason]
    return {
        "forbidden_flags": list(FORBIDDEN_AUTHORITY_FLAGS),
        "blocked_hits": hits,
        "passed": not hits,
    }


def _validation_status(
    *,
    roles: list[dict[str, Any]],
    blockers: list[str],
    warnings: list[str],
    missing_fields: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> str:
    if blockers:
        return "model_roles_blocked"
    if not roles or missing_fields:
        return "model_roles_incomplete"
    if roles and all(_is_weak_role(role) for role in roles):
        return "model_roles_incomplete"
    if warnings or coverage.get("coverage_status") != "meaningful_coverage":
        return "model_roles_ready_with_warnings"
    return "model_roles_ready"


def build_model_role_registry(
    *,
    role_catalog: dict[str, Any] | None = None,
    role_catalog_path: str = "",
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic report-only MODEL.N1 role registry."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(role_catalog_path, "role_catalog")
    input_source, raw_roles, input_warnings, shape_blockers = _catalog_shape(role_catalog)
    warnings = list(input_warnings)
    blockers += shape_blockers

    roles: list[dict[str, Any]] = []
    missing_fields: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_roles):
        card, card_warnings, card_blockers, card_missing = _normalize_card(raw, index=index, seen_ids=seen_ids)
        roles.append(card)
        warnings += card_warnings
        blockers += card_blockers
        missing_fields += card_missing

    blockers += _validate_fallbacks(roles)
    coverage = _coverage_matrix(roles)
    if coverage.get("coverage_status") != "meaningful_coverage" and roles:
        warnings.append("role catalog does not cover every required MODEL.N1 capability")

    warnings = _dedupe(warnings)
    blockers = _dedupe(blockers)
    status = _validation_status(
        roles=roles,
        blockers=blockers,
        warnings=warnings,
        missing_fields=missing_fields,
        coverage=coverage,
    )

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": MODEL_ROLE_REGISTRY_GUARDRAIL_NOTE,
        "source_inputs": {
            "input_source": input_source,
            "role_catalog_path": str(role_catalog_path or ""),
        },
        "role_catalog_path": str(role_catalog_path or ""),
        "role_card_fields": list(ROLE_CARD_FIELDS),
        "roles": roles,
        "role_count": len(roles),
        "validation_status": status,
        "validation_findings": {
            "role_count": len(roles),
            "missing_role_fields": missing_fields,
            "warning_count": len(warnings),
            "blocked_reason_count": len(blockers),
            "weak_role_count": sum(1 for role in roles if _is_weak_role(role)),
        },
        "coverage_matrix": coverage,
        "risk_and_cost_tiers": _risk_and_cost_tiers(roles),
        "fallback_role_map": _fallback_role_map(roles),
        "forbidden_authority_checks": _forbidden_authority_checks(roles, blockers),
        "warnings": warnings,
        "blocked_reasons": blockers,
        "guardrails": _guardrails(),
        "allowed_role_kinds": list(ALLOWED_ROLE_KINDS),
        "allowed_tiers": {
            "risk_level": list(RISK_LEVELS),
            "cost_tier": list(COST_TIERS),
            "latency_tier": list(LATENCY_TIERS),
            "context_tier": list(CONTEXT_TIERS),
            "reliability_tier": list(RELIABILITY_TIERS),
        },
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "boundaries": [
            "MODEL.N1 defines advisory model/tower cards only.",
            "MODEL.N1 does not route tasks.",
            "MODEL.N1 does not call models.",
            "MODEL.N1 does not launch workers.",
            "MODEL.N1 does not bind Commander roles to executable model IDs.",
            "MODEL.N1 does not change existing model selection behavior.",
            "MODEL.N1 writes model role registry artifacts only.",
        ],
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_model_role_registry_markdown(registry: dict[str, Any]) -> str:
    """Render a MODEL.N1 model role registry as Markdown."""
    source = registry.get("source_inputs") if isinstance(registry.get("source_inputs"), dict) else {}
    findings = registry.get("validation_findings") if isinstance(registry.get("validation_findings"), dict) else {}
    coverage = registry.get("coverage_matrix") if isinstance(registry.get("coverage_matrix"), dict) else {}
    next_phase = registry.get("recommended_next_phase") if isinstance(registry.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Model Role Registry / Tower Card Contract",
        "",
        f"> {registry.get('guardrail_note', MODEL_ROLE_REGISTRY_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.N1 defines advisory model/role tower cards. It routes nothing, calls no models, launches no workers, and creates no executable bindings._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Validation status:** `{_md(registry.get('validation_status', ''))}`",
        f"- **Role count:** {registry.get('role_count', 0)}",
        f"- **Warning count:** {findings.get('warning_count', 0)}",
        f"- **Blocked reason count:** {findings.get('blocked_reason_count', 0)}",
        "",
        "## Role Catalog Source",
        "",
        f"- **Input source:** `{_md(source.get('input_source', ''))}`",
        f"- **Role catalog path:** `{_md(source.get('role_catalog_path', ''))}`",
        "",
        "## Model/Tower Cards",
        "",
    ]
    roles = registry.get("roles") if isinstance(registry.get("roles"), list) else []
    if roles:
        lines += [
            "| Role | Kind | Risk | Cost | Latency | Context | Reliability | Human review | Model IDs |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for role in roles:
            lines.append(
                "| {rid} | {kind} | {risk} | {cost} | {latency} | {context} | {reliability} | {review} | {models} |".format(
                    rid=_md(role.get("role_id", "")),
                    kind=_md(role.get("role_kind", "")),
                    risk=_md(role.get("risk_level", "")),
                    cost=_md(role.get("cost_tier", "")),
                    latency=_md(role.get("latency_tier", "")),
                    context=_md(role.get("context_tier", "")),
                    reliability=_md(role.get("reliability_tier", "")),
                    review=str(bool(role.get("human_review_required"))).lower(),
                    models=_md(", ".join(role.get("model_ids") or [])),
                )
            )
    else:
        lines.append("_None._")
    lines += ["", "## Coverage Matrix", ""]
    covered = coverage.get("covered") if isinstance(coverage.get("covered"), dict) else {}
    if covered:
        lines += ["| Capability | Covered roles |", "| --- | --- |"]
        for key in coverage.get("required_capabilities") or []:
            lines.append(f"| {_md(key)} | {_md(', '.join(covered.get(key) or []))} |")
    else:
        lines.append("_None._")
    lines += [
        "",
        f"- **Coverage status:** `{_md(coverage.get('coverage_status', ''))}`",
        f"- **Missing:** `{_md(', '.join(coverage.get('missing') or []))}`",
        "",
        "## Risk and Cost Tiers",
        "",
    ]
    tier_counts = registry.get("risk_and_cost_tiers") if isinstance(registry.get("risk_and_cost_tiers"), dict) else {}
    if tier_counts:
        for field in sorted(tier_counts):
            lines.append(f"- **{field}:** {_md(tier_counts[field])}")
    else:
        lines.append("_None._")
    lines += ["", "## Fallback Role Map", ""]
    fallback_map = registry.get("fallback_role_map") if isinstance(registry.get("fallback_role_map"), dict) else {}
    if fallback_map:
        for role_id in sorted(fallback_map):
            lines.append(f"- `{_md(role_id)}` -> `{_md(', '.join(fallback_map[role_id]))}`")
    else:
        lines.append("_None._")
    checks = registry.get("forbidden_authority_checks") if isinstance(registry.get("forbidden_authority_checks"), dict) else {}
    lines += [
        "",
        "## Forbidden Authority Checks",
        "",
        f"- **Passed:** {str(bool(checks.get('passed'))).lower()}",
        f"- **Forbidden flags:** `{_md(', '.join(checks.get('forbidden_flags') or []))}`",
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
        "- MODEL.N1 does not route tasks.",
        "- MODEL.N1 does not call models.",
        "- MODEL.N1 does not launch workers.",
        "- MODEL.N1 does not bind executable model IDs.",
        "- MODEL.N1 writes model role registry artifacts only.",
        "",
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_model_role_registry(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    role_catalog_path: str = "",
    role_catalog: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write MODEL.N1 JSON + Markdown artifacts."""
    registry = build_model_role_registry(
        role_catalog=role_catalog,
        role_catalog_path=role_catalog_path,
        input_blockers=input_blockers,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_registry_markdown(registry), encoding="utf-8")
    return {
        "ok": registry.get("validation_status") != "model_roles_blocked",
        "json_path": str(json_path),
        "md_path": str(md_path),
        "registry": registry,
    }
