"""CMD.3 - Budget Governor Preview (report-only).

Builds a deterministic budget governor preview from a CMD.1 Commander Run
Contract, a CMD.2 Task Decomposition Preview, or plain task text. CMD.3
estimates scope, compares it with local budget limits, previews escalation
rules, and names stop gates only. It does not execute tasks, run agents, call
models, apply patches, run validation, run benchmarks, contact network services,
launch workers, write to a database, push, merge, or open PRs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "commander_budget_governor_preview"

BUDGET_STATUSES: tuple[str, ...] = (
    "within_budget",
    "near_limit",
    "over_budget",
    "needs_human_reapproval",
    "insufficient_information",
)

ALLOWED_NEXT_STEPS: tuple[str, ...] = (
    "review_budget_governor_preview",
    "edit_budget_limits",
    "ask_human_for_budget_approval",
    "create_stop_condition_report",
    "create_next_cmd_contract",
)

FORBIDDEN_NEXT_STEPS: tuple[str, ...] = (
    "execute_plan",
    "launch_worker",
    "apply_patch",
    "run_validation",
    "run_benchmark",
    "call_model",
    "contact_remote_service",
    "push_or_merge",
    "open_pr",
    "auto_approve",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "budget_enforcement_performed",
    "commander_execution_performed",
    "agent_launched",
    "model_call_performed",
    "patch_applied",
    "validation_run",
    "benchmark_run_performed",
    "network_call_performed",
    "database_write_performed",
    "worker_launch_performed",
    "merge_performed",
)

BOUNDARY_LINES: tuple[str, ...] = (
    "CMD.3 does not execute tasks.",
    "CMD.3 does not run agents.",
    "CMD.3 does not call models.",
    "CMD.3 does not apply patches.",
    "CMD.3 does not run validation.",
    "CMD.3 does not run benchmarks.",
    "CMD.3 does not contact network services.",
    "CMD.3 does not launch workers.",
    "CMD.3 does not push, merge, or open PRs.",
    "CMD.3 is a report-only budget governor preview.",
)

BUDGET_GOVERNOR_GUARDRAIL_NOTE = (
    "Budget Governor Preview is report-only: it reads an optional CMD.1 "
    "Commander Run Contract and optional CMD.2 Task Decomposition Preview, then "
    "estimates scope, budget limits, escalation rules, stop conditions, and human "
    "approval checkpoints. It does not enforce budgets, execute tasks, run "
    "agents, call models, apply patches, run validation, run benchmarks, contact "
    "network services, launch workers, write to a database, push, merge, or open "
    "PRs."
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _norm(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip()


def _lower(value: Any) -> str:
    return _norm(value).lower()


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _positive_int(value: Any) -> int | None:
    number = _as_int(value, 0)
    return number if number > 0 else None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _safe_file_stem(preview_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in str(preview_id or ""))
    cleaned = cleaned.strip("-._")
    return cleaned or "budget_governor_preview"


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def read_source_contract(path: str | Path) -> tuple[dict[str, Any] | None, str]:
    """Read an optional CMD.1 contract JSON file without raising to callers."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read contract at {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"could not read contract at {path}: contract JSON is not an object"
    if str(data.get("report_kind") or "") != "commander_run_contract":
        return None, f"could not read contract at {path}: not a CMD.1 commander_run_contract"
    return data, ""


def read_source_decomposition(path: str | Path) -> tuple[dict[str, Any] | None, str]:
    """Read an optional CMD.2 decomposition preview without raising to callers."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read decomposition at {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"could not read decomposition at {path}: decomposition JSON is not an object"
    if str(data.get("report_kind") or "") != "commander_task_decomposition_preview":
        return None, f"could not read decomposition at {path}: not a CMD.2 commander_task_decomposition_preview"
    return data, ""


def _default_stop_conditions() -> list[str]:
    return [
        "stop if estimated files exceed max_files",
        "stop if estimated lines exceed max_lines",
        "stop if estimated minutes exceed max_minutes",
        "stop if forbidden files are requested",
        "stop if validation fails",
        "stop if benchmark check fails",
        "stop if remote action is requested",
        "stop if model authority is requested",
        "stop if network service contact is requested",
        "stop if push, merge, or PR authority is requested",
        "stop if human approval is missing",
    ]


def _contract_values(source_contract: Any) -> dict[str, Any]:
    contract = source_contract if isinstance(source_contract, dict) else {}
    scope = contract.get("estimated_scope") if isinstance(contract.get("estimated_scope"), dict) else {}
    changed_files = _string_list(scope.get("changed_files"))
    return {
        "has_source": bool(contract),
        "task": str(contract.get("task") or ""),
        "mode": str(contract.get("recommended_mode") or ""),
        "risk_level": str(contract.get("risk_level") or ""),
        "complexity_level": str(contract.get("complexity_level") or ""),
        "changed_files": changed_files,
        "estimated_files_touched": max(_as_int(scope.get("estimated_files_touched"), 0), len(changed_files)),
        "estimated_lines_changed": _as_int(scope.get("estimated_lines_changed"), 0),
        "estimated_minutes": _positive_int(scope.get("time_budget_minutes")),
        "required_gates": _string_list(contract.get("required_gates")),
        "stop_conditions": _string_list(contract.get("stop_conditions")),
        "warnings": _string_list(contract.get("warnings")),
        "blockers": _string_list(contract.get("blockers")),
    }


def _decomposition_values(source_decomposition: Any) -> dict[str, Any]:
    preview = source_decomposition if isinstance(source_decomposition, dict) else {}
    budget = preview.get("budget_plan_preview") if isinstance(preview.get("budget_plan_preview"), dict) else {}
    evidence = preview.get("evidence_plan_preview") if isinstance(preview.get("evidence_plan_preview"), dict) else {}
    checkpoint = preview.get("human_checkpoint_preview") if isinstance(preview.get("human_checkpoint_preview"), dict) else {}
    phases = preview.get("phase_plan_preview") if isinstance(preview.get("phase_plan_preview"), list) else []
    changed_files = _string_list(evidence.get("changed_files"))
    generated_artifacts = _string_list(evidence.get("generated_artifacts"))
    return {
        "has_source": bool(preview),
        "task": str(preview.get("task") or ""),
        "source_mode": str(preview.get("source_mode") or ""),
        "risk_level": str(preview.get("source_risk_level") or ""),
        "complexity_level": str(preview.get("source_complexity_level") or ""),
        "changed_files": changed_files,
        "generated_artifacts": generated_artifacts,
        "phase_count": len(phases),
        "estimated_files_touched": max(_as_int(budget.get("estimated_files_touched"), 0), len(changed_files)),
        "estimated_lines_changed": _as_int(budget.get("estimated_lines_changed"), 0),
        "estimated_minutes": _positive_int(budget.get("time_budget_minutes")),
        "required_gates": _string_list(checkpoint.get("required_gates")),
        "stop_conditions": _string_list(preview.get("stop_conditions")),
        "warnings": _string_list(preview.get("warnings")),
        "blockers": _string_list(preview.get("blockers")),
    }


def _estimate_minutes(*, explicit_minutes: int | None, files: int, lines: int, phase_count: int) -> int | None:
    if explicit_minutes is not None:
        return explicit_minutes
    if files <= 0 and lines <= 0 and phase_count <= 0:
        return None
    return max(15, files * 8 + ((lines + 9) // 10) + phase_count * 5)


def _choose_task(task: str, contract: dict[str, Any], decomposition: dict[str, Any]) -> str:
    if contract["task"]:
        return contract["task"]
    if decomposition["task"]:
        return decomposition["task"]
    return str(task or "")


def _merge_source_values(
    *,
    task: str,
    source_contract: Any,
    source_contract_path: str,
    source_contract_error: str,
    source_decomposition: Any,
    source_decomposition_path: str,
    source_decomposition_error: str,
) -> dict[str, Any]:
    contract = _contract_values(source_contract)
    decomposition = _decomposition_values(source_decomposition)
    chosen_task = _choose_task(task, contract, decomposition)
    changed_files = _dedupe(contract["changed_files"] + decomposition["changed_files"])
    explicit_minutes = max(
        [value for value in (contract["estimated_minutes"], decomposition["estimated_minutes"]) if value is not None],
        default=None,
    )
    files = max(contract["estimated_files_touched"], decomposition["estimated_files_touched"], len(changed_files))
    lines = max(contract["estimated_lines_changed"], decomposition["estimated_lines_changed"])
    phase_count = decomposition["phase_count"]
    minutes = _estimate_minutes(explicit_minutes=explicit_minutes, files=files, lines=lines, phase_count=phase_count)
    source_count = int(contract["has_source"]) + int(decomposition["has_source"])

    required_gates = _dedupe(contract["required_gates"] + decomposition["required_gates"])
    if not required_gates:
        required_gates = ["human_approval", "scope_confirmed"]

    stop_conditions = _dedupe(contract["stop_conditions"] + decomposition["stop_conditions"] + _default_stop_conditions())
    warnings: list[str] = []
    if contract["has_source"] and task:
        warnings.append("extra task text was provided; contract fields took priority")
    if contract["has_source"] and decomposition["has_source"] and contract["task"] and decomposition["task"] and contract["task"] != decomposition["task"]:
        warnings.append("contract task took priority over decomposition task")
    warnings.extend(contract["warnings"])
    warnings.extend(decomposition["warnings"])

    blockers = _dedupe(
        [source_contract_error, source_decomposition_error]
        + contract["blockers"]
        + decomposition["blockers"]
    )
    if not chosen_task:
        blockers.append("task description is missing and no readable CMD.1/CMD.2 source supplied it")

    return {
        "task": chosen_task,
        "changed_files": changed_files,
        "generated_artifacts": decomposition["generated_artifacts"],
        "estimated_files_touched": files,
        "estimated_lines_changed": lines,
        "estimated_minutes": minutes,
        "phase_count": phase_count,
        "required_gates": required_gates,
        "stop_conditions": stop_conditions,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "source_summary": {
            "source_count": source_count,
            "contract_source": str(source_contract_path or ""),
            "decomposition_source": str(source_decomposition_path or ""),
            "contract_mode": contract["mode"] or "unavailable",
            "decomposition_mode": decomposition["source_mode"] or "unavailable",
            "risk_level": contract["risk_level"] or decomposition["risk_level"] or "unknown",
            "complexity_level": contract["complexity_level"] or decomposition["complexity_level"] or "unknown",
            "required_gates": required_gates,
            "phase_count": phase_count,
            "evidence_artifact_count": len(decomposition["generated_artifacts"]),
        },
    }


def _limit_result(name: str, estimated: int | None, limit: int) -> dict[str, Any]:
    if estimated is None or estimated <= 0 or limit <= 0:
        return {
            "name": name,
            "estimated": estimated,
            "limit": limit,
            "ratio": None,
            "classification": "insufficient_information",
        }
    ratio = estimated / limit
    if estimated > limit:
        classification = "over_budget"
    elif ratio >= 0.8:
        classification = "near_limit"
    else:
        classification = "within_budget"
    return {
        "name": name,
        "estimated": estimated,
        "limit": limit,
        "ratio": round(ratio, 3),
        "classification": classification,
    }


def _limit_classification(limit_results: list[dict[str, Any]]) -> str:
    classes = {str(result.get("classification")) for result in limit_results}
    if "over_budget" in classes:
        return "over_budget"
    if classes == {"insufficient_information"}:
        return "insufficient_information"
    if "near_limit" in classes:
        return "near_limit"
    if "insufficient_information" in classes:
        return "insufficient_information"
    return "within_budget"


def _authority_escalation_required(task: str, required_gates: list[str], stop_conditions: list[str]) -> bool:
    # Stop conditions are static guardrails; only the task and inherited gates
    # indicate that authority-sensitive work was actually requested.
    _ = stop_conditions
    text = _lower(" ".join([task] + required_gates))
    needles = (
        "remote",
        "network",
        "model authority",
        "model call",
        "call model",
        "push",
        "merge",
        "open pr",
        "pr authority",
    )
    return any(needle in text for needle in needles)


def _budget_summary(
    *,
    files: int,
    lines: int,
    minutes: int | None,
    phase_count: int,
    max_files: int,
    max_lines: int,
    max_minutes: int,
    authority_escalation_required: bool,
) -> dict[str, Any]:
    limit_results = [
        _limit_result("files", files, max_files),
        _limit_result("lines", lines, max_lines),
        _limit_result("minutes", minutes, max_minutes),
    ]
    classification = _limit_classification(limit_results)
    human_reapproval = classification == "over_budget" or authority_escalation_required
    if classification == "over_budget":
        status = "needs_human_reapproval"
    elif authority_escalation_required:
        status = "needs_human_reapproval"
    else:
        status = classification
    return {
        "estimated_files_touched": files,
        "estimated_lines_changed": lines,
        "estimated_minutes": minutes,
        "phase_count": phase_count,
        "limit_classification": classification,
        "status": status,
        "human_reapproval_required": human_reapproval,
        "authority_escalation_required": authority_escalation_required,
        "limit_results": limit_results,
    }


def _escalation_rules() -> list[dict[str, str]]:
    return [
        {
            "trigger": "estimated_files_touched_exceeds_max_files",
            "action": "stop_and_request_human_reapproval",
            "severity": "hard_stop",
        },
        {
            "trigger": "estimated_lines_changed_exceeds_max_lines",
            "action": "stop_and_request_human_reapproval",
            "severity": "hard_stop",
        },
        {
            "trigger": "estimated_minutes_exceeds_max_minutes",
            "action": "stop_and_request_human_reapproval",
            "severity": "hard_stop",
        },
        {
            "trigger": "remote_action_requested",
            "action": "stop_and_escalate",
            "severity": "hard_stop",
        },
        {
            "trigger": "model_authority_requested",
            "action": "stop_and_escalate",
            "severity": "hard_stop",
        },
        {
            "trigger": "network_service_requested",
            "action": "stop_and_escalate",
            "severity": "hard_stop",
        },
        {
            "trigger": "push_merge_or_pr_requested",
            "action": "stop_and_escalate",
            "severity": "hard_stop",
        },
        {
            "trigger": "missing_human_approval",
            "action": "stop_and_request_human_reapproval",
            "severity": "hard_stop",
        },
    ]


def _human_checkpoints(human_reapproval_required: bool) -> list[dict[str, Any]]:
    checkpoints = [
        {
            "checkpoint_id": "approve_budget_limits",
            "required": True,
            "reason": "Human reviews max_files, max_lines, and max_minutes before future execution.",
        },
        {
            "checkpoint_id": "approve_escalation_rules",
            "required": True,
            "reason": "Human accepts stop and escalation triggers before any follow-up phase.",
        },
        {
            "checkpoint_id": "approve_future_validation_gate",
            "required": True,
            "reason": "Validation remains a future gate and must be approved before it is run.",
        },
        {
            "checkpoint_id": "approve_future_benchmark_gate",
            "required": True,
            "reason": "Benchmark checks remain future gates and must be approved before they are run.",
        },
    ]
    if human_reapproval_required:
        checkpoints.append(
            {
                "checkpoint_id": "human_reapprove_budget",
                "required": True,
                "reason": "The preview is over budget or authority-sensitive; human reapproval is required.",
            }
        )
    return checkpoints


def build_budget_governor_preview(
    *,
    task: str = "",
    repo_path: str = "",
    source_contract: Any = None,
    source_contract_path: str = "",
    source_contract_error: str = "",
    source_decomposition: Any = None,
    source_decomposition_path: str = "",
    source_decomposition_error: str = "",
    max_files: Any = 5,
    max_lines: Any = 150,
    max_minutes: Any = 60,
    preview_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build a deterministic CMD.3 report-only budget governor preview."""
    merged = _merge_source_values(
        task=task,
        source_contract=source_contract,
        source_contract_path=source_contract_path,
        source_contract_error=source_contract_error,
        source_decomposition=source_decomposition,
        source_decomposition_path=source_decomposition_path,
        source_decomposition_error=source_decomposition_error,
    )
    files = _as_int(merged["estimated_files_touched"], 0)
    lines = _as_int(merged["estimated_lines_changed"], 0)
    minutes = merged["estimated_minutes"]
    phase_count = _as_int(merged["phase_count"], 0)
    limits = {
        "max_files": _as_int(max_files, 5),
        "max_lines": _as_int(max_lines, 150),
        "max_minutes": _as_int(max_minutes, 60),
        "near_limit_threshold": 0.8,
    }
    authority_required = _authority_escalation_required(
        merged["task"],
        _string_list(merged["required_gates"]),
        _string_list(merged["stop_conditions"]),
    )
    summary = _budget_summary(
        files=files,
        lines=lines,
        minutes=minutes,
        phase_count=phase_count,
        max_files=limits["max_files"],
        max_lines=limits["max_lines"],
        max_minutes=limits["max_minutes"],
        authority_escalation_required=authority_required,
    )

    warnings = list(merged["warnings"])
    if summary["limit_classification"] == "insufficient_information":
        warnings.append("missing scope information prevents a confident budget classification")
    if summary["limit_classification"] == "over_budget":
        warnings.append("estimated scope exceeds at least one budget limit and requires human reapproval")
    if authority_required:
        warnings.append("authority-sensitive wording requires stop/escalation review before any future action")
    warnings.append("validation and benchmark checks are future gates only; CMD.3 did not run them")

    estimated_scope = {
        "changed_files": _string_list(merged["changed_files"]),
        "changed_file_count": len(_string_list(merged["changed_files"])),
        "estimated_files_touched": files,
        "estimated_lines_changed": lines,
        "estimated_minutes": minutes,
        "phase_count": phase_count,
        "generated_artifacts": _string_list(merged["generated_artifacts"]),
        "evidence_artifact_count": len(_string_list(merged["generated_artifacts"])),
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": BUDGET_GOVERNOR_GUARDRAIL_NOTE,
        "preview_id": str(preview_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm(repo_path),
        "source_contract_path": str(source_contract_path or ""),
        "source_decomposition_path": str(source_decomposition_path or ""),
        "task": merged["task"],
        "budget_summary": summary,
        "estimated_scope": estimated_scope,
        "budget_limits": limits,
        "budget_status": summary["status"],
        "source_summary": merged["source_summary"],
        "escalation_rules": _escalation_rules(),
        "stop_conditions": _dedupe(_string_list(merged["stop_conditions"]) + _default_stop_conditions()),
        "human_approval_checkpoints": _human_checkpoints(bool(summary["human_reapproval_required"])),
        "allowed_next_steps": list(ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(FORBIDDEN_NEXT_STEPS),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(_string_list(merged["blockers"])),
        "guardrails": _guardrails(),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_budget_governor_markdown(preview: dict[str, Any]) -> str:
    """Render a CMD.3 Budget Governor Preview as operator-facing Markdown."""
    summary = preview.get("budget_summary") if isinstance(preview.get("budget_summary"), dict) else {}
    source = preview.get("source_summary") if isinstance(preview.get("source_summary"), dict) else {}
    scope = preview.get("estimated_scope") if isinstance(preview.get("estimated_scope"), dict) else {}
    limits = preview.get("budget_limits") if isinstance(preview.get("budget_limits"), dict) else {}

    lines: list[str] = [
        "# Budget Governor Preview",
        "",
        f"> {preview.get('guardrail_note', BUDGET_GOVERNOR_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.3 estimates budgets and stop thresholds. It runs nothing and changes nothing._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Preview id:** `{_md(preview.get('preview_id') or '(none)')}`",
        f"- **Created at:** `{_md(preview.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(preview.get('repo_path') or '(none)')}`",
        f"- **Task:** {_md(preview.get('task') or '')}",
        f"- **Budget status:** `{_md(preview.get('budget_status') or '')}`",
        "",
        "## Sources",
        "",
        f"- **Contract path:** `{_md(preview.get('source_contract_path') or '(none)')}`",
        f"- **Decomposition path:** `{_md(preview.get('source_decomposition_path') or '(none)')}`",
        f"- **Source count:** {source.get('source_count', 0)}",
        f"- **Risk level:** `{_md(source.get('risk_level') or '')}`",
        f"- **Complexity level:** `{_md(source.get('complexity_level') or '')}`",
        f"- **Phase count:** {source.get('phase_count', 0)}",
        "",
        "## Estimated Scope",
        "",
        f"- **Estimated files touched:** {scope.get('estimated_files_touched', 0)}",
        f"- **Estimated lines changed:** {scope.get('estimated_lines_changed', 0)}",
        f"- **Estimated minutes:** {_md(scope.get('estimated_minutes'))}",
        f"- **Evidence artifact count:** {scope.get('evidence_artifact_count', 0)}",
        "",
        "Changed files:",
    ]
    _render_list(lines, _string_list(scope.get("changed_files")), code=True)
    lines += ["Generated artifacts:"]
    _render_list(lines, _string_list(scope.get("generated_artifacts")), code=True)

    lines += [
        "## Budget Limits",
        "",
        f"- **max_files:** {limits.get('max_files')}",
        f"- **max_lines:** {limits.get('max_lines')}",
        f"- **max_minutes:** {limits.get('max_minutes')}",
        f"- **near_limit_threshold:** {limits.get('near_limit_threshold')}",
        "",
        "## Budget Status",
        "",
        f"- **Overall:** `{_md(preview.get('budget_status') or '')}`",
        f"- **Limit classification:** `{_md(summary.get('limit_classification') or '')}`",
        f"- **Human reapproval required:** {str(bool(summary.get('human_reapproval_required'))).lower()}",
        f"- **Authority escalation required:** {str(bool(summary.get('authority_escalation_required'))).lower()}",
        "",
        "| Limit | Estimated | Max | Ratio | Classification |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for result in summary.get("limit_results") or []:
        lines.append(
            f"| `{_md(result.get('name'))}` | {_md(result.get('estimated'))} | "
            f"{_md(result.get('limit'))} | {_md(result.get('ratio'))} | "
            f"`{_md(result.get('classification'))}` |"
        )
    lines.append("")

    lines += ["## Escalation Rules", ""]
    rules = preview.get("escalation_rules") if isinstance(preview.get("escalation_rules"), list) else []
    if rules:
        lines += [
            "| Trigger | Action | Severity |",
            "| --- | --- | --- |",
        ]
        for rule in rules:
            lines.append(
                f"| `{_md(rule.get('trigger'))}` | `{_md(rule.get('action'))}` | `{_md(rule.get('severity'))}` |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Stop Conditions", ""]
    _render_list(lines, _string_list(preview.get("stop_conditions")))

    lines += ["## Human Approval Checkpoints", ""]
    checkpoints = preview.get("human_approval_checkpoints") if isinstance(preview.get("human_approval_checkpoints"), list) else []
    if checkpoints:
        for checkpoint in checkpoints:
            lines.append(
                f"- `{_md(checkpoint.get('checkpoint_id'))}`: {_md(checkpoint.get('reason'))}"
            )
    else:
        lines.append("_None._")
    lines.append("")

    for title, key in (
        ("Allowed Next Steps", "allowed_next_steps"),
        ("Forbidden Next Steps", "forbidden_next_steps"),
        ("Warnings", "warnings"),
        ("Blockers", "blockers"),
    ):
        lines += [f"## {title}", ""]
        _render_list(lines, _string_list(preview.get(key)), code="Steps" in title)

    lines += ["## Boundaries", ""]
    for line in BOUNDARY_LINES:
        lines.append(f"- {line}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_budget_governor_preview(
    *,
    output_root: str | Path,
    task: str = "",
    repo_path: str = "",
    source_contract: Any = None,
    source_contract_path: str = "",
    source_contract_error: str = "",
    source_decomposition: Any = None,
    source_decomposition_path: str = "",
    source_decomposition_error: str = "",
    max_files: Any = 5,
    max_lines: Any = 150,
    max_minutes: Any = 60,
    preview_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write the CMD.3 JSON + Markdown budget preview artifacts."""
    preview = build_budget_governor_preview(
        task=task,
        repo_path=repo_path,
        source_contract=source_contract,
        source_contract_path=source_contract_path,
        source_contract_error=source_contract_error,
        source_decomposition=source_decomposition,
        source_decomposition_path=source_decomposition_path,
        source_decomposition_error=source_decomposition_error,
        max_files=max_files,
        max_lines=max_lines,
        max_minutes=max_minutes,
        preview_id=preview_id,
        created_at=created_at,
    )
    out_dir = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_file_stem(preview.get("preview_id") or "")
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_budget_governor_markdown(preview), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "preview": preview}
