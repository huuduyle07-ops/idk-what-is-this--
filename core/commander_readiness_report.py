"""CMD.4 - Commander Readiness / Stop Condition Report (report-only).

Builds a deterministic readiness report from optional CMD.1, CMD.2, and CMD.3
artifacts. CMD.4 assesses gate coverage, budget posture, stop conditions, and
human approval requirements only. It does not execute the commander plan, run
agents, call models, apply patches, run validation, run benchmarks, contact
network services, launch workers, write to a database, push, merge, or open PRs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "commander_readiness_report"

READINESS_STATUSES: tuple[str, ...] = (
    "ready_for_human_approval",
    "needs_human_reapproval",
    "blocked",
    "insufficient_evidence",
)

TRACKED_GATES: tuple[str, ...] = (
    "human_approval",
    "scope_confirmed",
    "budget_confirmed",
    "evidence_required",
    "validation_required",
    "benchmark_check_required",
    "rollback_plan_required",
)

ALLOWED_NEXT_STEPS: tuple[str, ...] = (
    "review_readiness_report",
    "request_human_approval",
    "revise_scope",
    "revise_budget",
    "create_report_only_implementation_prompt",
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
    "readiness_execution_performed",
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
    "CMD.4 does not execute the commander plan.",
    "CMD.4 does not run agents.",
    "CMD.4 does not call models.",
    "CMD.4 does not apply patches.",
    "CMD.4 does not run validation.",
    "CMD.4 does not run benchmarks.",
    "CMD.4 does not contact network services.",
    "CMD.4 does not launch workers.",
    "CMD.4 does not push, merge, or open PRs.",
    "CMD.4 is a report-only readiness check.",
)

READINESS_GUARDRAIL_NOTE = (
    "Commander Readiness Report is report-only: it reads optional CMD.1, CMD.2, "
    "and CMD.3 artifacts and assesses readiness, gates, budget posture, stop "
    "conditions, and human approval requirements. It does not execute the "
    "commander plan, run agents, call models, apply patches, run validation, run "
    "benchmarks, contact network services, launch workers, write to a database, "
    "push, merge, or open PRs."
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _norm(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip()


def _as_bool(value: Any) -> bool:
    return bool(value)


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


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _safe_file_stem(report_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in str(report_id or ""))
    cleaned = cleaned.strip("-._")
    return cleaned or "commander_readiness_report"


def _read_source(path: str | Path, *, kind: str, expected_report_kind: str) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read {kind} at {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"could not read {kind} at {path}: {kind} JSON is not an object"
    if str(data.get("report_kind") or "") != expected_report_kind:
        return None, f"could not read {kind} at {path}: not a {expected_report_kind}"
    return data, ""


def read_source_contract(path: str | Path) -> tuple[dict[str, Any] | None, str]:
    """Read an optional CMD.1 contract without raising to callers."""
    return _read_source(path, kind="contract", expected_report_kind="commander_run_contract")


def read_source_decomposition(path: str | Path) -> tuple[dict[str, Any] | None, str]:
    """Read an optional CMD.2 decomposition preview without raising to callers."""
    return _read_source(path, kind="decomposition", expected_report_kind="commander_task_decomposition_preview")


def read_source_budget(path: str | Path) -> tuple[dict[str, Any] | None, str]:
    """Read an optional CMD.3 budget preview without raising to callers."""
    return _read_source(path, kind="budget", expected_report_kind="commander_budget_governor_preview")


def _contract_gates(source_contract: Any) -> list[str]:
    contract = source_contract if isinstance(source_contract, dict) else {}
    return _string_list(contract.get("required_gates"))


def _decomposition_gates(source_decomposition: Any) -> list[str]:
    preview = source_decomposition if isinstance(source_decomposition, dict) else {}
    checkpoint = preview.get("human_checkpoint_preview") if isinstance(preview.get("human_checkpoint_preview"), dict) else {}
    return _string_list(checkpoint.get("required_gates"))


def _budget_gates(source_budget: Any) -> list[str]:
    budget = source_budget if isinstance(source_budget, dict) else {}
    summary = budget.get("source_summary") if isinstance(budget.get("source_summary"), dict) else {}
    return _string_list(summary.get("required_gates"))


def _collect_gates(source_contract: Any, source_decomposition: Any, source_budget: Any) -> list[str]:
    return _dedupe(_contract_gates(source_contract) + _decomposition_gates(source_decomposition) + _budget_gates(source_budget))


def _gate_summary(source_contract: Any, source_decomposition: Any, source_budget: Any) -> dict[str, Any]:
    present_gates = _collect_gates(source_contract, source_decomposition, source_budget)
    present = set(present_gates)
    gate_map = {gate: gate in present for gate in TRACKED_GATES}
    missing = [gate for gate in TRACKED_GATES if not gate_map[gate]]
    return {
        "present_gates": present_gates,
        "tracked_gate_order": list(TRACKED_GATES),
        "gates": gate_map,
        "missing_gates": missing,
        "human_approval_gate_present": gate_map["human_approval"],
        "all_required_gates_present": not missing,
    }


def _stop_conditions(source_contract: Any, source_decomposition: Any, source_budget: Any) -> list[str]:
    contract = source_contract if isinstance(source_contract, dict) else {}
    decomposition = source_decomposition if isinstance(source_decomposition, dict) else {}
    budget = source_budget if isinstance(source_budget, dict) else {}
    defaults = [
        "stop if forbidden files are requested",
        "stop if validation fails",
        "stop if benchmark check fails",
        "stop if remote action is requested",
        "stop if model authority is requested",
        "stop if push, merge, or PR authority is requested",
        "stop if human approval is missing",
    ]
    conditions = (
        _string_list(contract.get("stop_conditions"))
        + _string_list(decomposition.get("stop_conditions"))
        + _string_list(budget.get("stop_conditions"))
        + defaults
    )
    return sorted(set(conditions))


def _budget_summary(source_budget: Any) -> dict[str, Any]:
    budget = source_budget if isinstance(source_budget, dict) else {}
    summary = budget.get("budget_summary") if isinstance(budget.get("budget_summary"), dict) else {}
    scope = budget.get("estimated_scope") if isinstance(budget.get("estimated_scope"), dict) else {}
    return {
        "budget_status": str(budget.get("budget_status") or "unavailable"),
        "limit_classification": str(summary.get("limit_classification") or "unavailable"),
        "human_reapproval_required": _as_bool(summary.get("human_reapproval_required")),
        "authority_escalation_required": _as_bool(summary.get("authority_escalation_required")),
        "estimated_files_touched": scope.get("estimated_files_touched"),
        "estimated_lines_changed": scope.get("estimated_lines_changed"),
        "estimated_minutes": scope.get("estimated_minutes"),
        "phase_count": scope.get("phase_count"),
    }


def _active_authority_escalation(source_budget: Any) -> bool:
    budget = source_budget if isinstance(source_budget, dict) else {}
    summary = budget.get("budget_summary") if isinstance(budget.get("budget_summary"), dict) else {}
    if _as_bool(summary.get("authority_escalation_required")):
        return True
    rules = budget.get("escalation_rules") if isinstance(budget.get("escalation_rules"), list) else []
    authority_needles = ("remote", "model", "network", "push", "merge", "pr", "forbidden")
    for rule in rules:
        if not isinstance(rule, dict) or not _as_bool(rule.get("active")):
            continue
        trigger = str(rule.get("trigger") or "").lower()
        if any(needle in trigger for needle in authority_needles):
            return True
    return False


def _source_summary(
    *,
    source_contract: Any,
    source_contract_path: str,
    source_decomposition: Any,
    source_decomposition_path: str,
    source_budget: Any,
    source_budget_path: str,
) -> dict[str, Any]:
    contract = source_contract if isinstance(source_contract, dict) else {}
    decomposition = source_decomposition if isinstance(source_decomposition, dict) else {}
    budget = source_budget if isinstance(source_budget, dict) else {}
    has_contract = bool(contract)
    has_decomposition = bool(decomposition)
    has_budget = bool(budget)
    return {
        "source_count": int(has_contract) + int(has_decomposition) + int(has_budget),
        "has_contract": has_contract,
        "has_decomposition": has_decomposition,
        "has_budget": has_budget,
        "contract_path": str(source_contract_path or ""),
        "decomposition_path": str(source_decomposition_path or ""),
        "budget_path": str(source_budget_path or ""),
        "contract_mode": str(contract.get("recommended_mode") or "unavailable"),
        "decomposition_mode": str(decomposition.get("source_mode") or "unavailable"),
        "budget_status": str(budget.get("budget_status") or "unavailable"),
    }


def _human_approval_summary(gate_summary: dict[str, Any], budget_summary: dict[str, Any], source_budget: Any) -> dict[str, Any]:
    budget = source_budget if isinstance(source_budget, dict) else {}
    checkpoints = budget.get("human_approval_checkpoints") if isinstance(budget.get("human_approval_checkpoints"), list) else []
    checkpoint_ids = [str(checkpoint.get("checkpoint_id")) for checkpoint in checkpoints if isinstance(checkpoint, dict)]
    return {
        "human_approval_required": True,
        "human_approval_gate_present": bool(gate_summary.get("human_approval_gate_present")),
        "budget_reapproval_required": bool(budget_summary.get("human_reapproval_required")),
        "checkpoint_ids": checkpoint_ids,
        "approval_status": "needs_reapproval" if budget_summary.get("human_reapproval_required") else "needs_initial_approval",
    }


def _required_before_implementation(budget_summary: dict[str, Any]) -> list[str]:
    required = ["human_scope_approval"]
    if budget_summary.get("human_reapproval_required") or budget_summary.get("limit_classification") == "over_budget":
        required.append("human_budget_reapproval")
    required.extend(
        [
            "review_decomposition_preview",
            "review_budget_preview",
            "confirm_validation_plan",
            "confirm_benchmark_plan",
            "confirm_rollback_plan",
            "confirm_no_remote_or_model_authority_change",
        ]
    )
    return required


def _source_warnings(source_contract: Any, source_decomposition: Any, source_budget: Any) -> list[str]:
    warnings: list[str] = []
    for source in (source_contract, source_decomposition, source_budget):
        if isinstance(source, dict):
            warnings.extend(_string_list(source.get("warnings")))
    return _dedupe(warnings)


def _source_blockers(source_contract: Any, source_decomposition: Any, source_budget: Any) -> list[str]:
    blockers: list[str] = []
    for source in (source_contract, source_decomposition, source_budget):
        if isinstance(source, dict):
            blockers.extend(_string_list(source.get("blockers")))
    return _dedupe(blockers)


def _classify(
    *,
    source_summary: dict[str, Any],
    gate_summary: dict[str, Any],
    budget_summary: dict[str, Any],
    blockers: list[str],
    active_authority_escalation: bool,
) -> tuple[str, str, list[str]]:
    final_blockers = list(blockers)
    if active_authority_escalation:
        final_blockers.append("remote/model/merge/forbidden-file escalation is active and blocks readiness")
    if source_summary["source_count"] > 0 and not gate_summary["human_approval_gate_present"]:
        final_blockers.append("human_approval gate is missing")
    if final_blockers:
        return "blocked", "Readiness is blocked by source errors, missing approval gates, or authority escalation.", _dedupe(final_blockers)
    if source_summary["source_count"] == 0:
        return "insufficient_evidence", "No CMD.1, CMD.2, or CMD.3 source artifacts were supplied.", []
    if budget_summary["budget_status"] in {"needs_human_reapproval", "over_budget"} or budget_summary["limit_classification"] == "over_budget":
        return "needs_human_reapproval", "CMD.3 budget posture requires human reapproval before implementation.", []
    if source_summary["source_count"] == 3 and budget_summary["budget_status"] in {"within_budget", "near_limit"}:
        return "ready_for_human_approval", "Complete CMD.1, CMD.2, and CMD.3 evidence is ready for human approval only.", []
    return "insufficient_evidence", "CMD source coverage is incomplete for a readiness decision.", []


def build_commander_readiness_report(
    *,
    repo_path: str = "",
    source_contract: Any = None,
    source_contract_path: str = "",
    source_contract_error: str = "",
    source_decomposition: Any = None,
    source_decomposition_path: str = "",
    source_decomposition_error: str = "",
    source_budget: Any = None,
    source_budget_path: str = "",
    source_budget_error: str = "",
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build a deterministic CMD.4 report-only readiness report."""
    source = _source_summary(
        source_contract=source_contract,
        source_contract_path=source_contract_path,
        source_decomposition=source_decomposition,
        source_decomposition_path=source_decomposition_path,
        source_budget=source_budget,
        source_budget_path=source_budget_path,
    )
    gates = _gate_summary(source_contract, source_decomposition, source_budget)
    budget = _budget_summary(source_budget)
    stops = _stop_conditions(source_contract, source_decomposition, source_budget)
    stop_summary = {
        "stop_condition_count": len(stops),
        "stop_conditions": stops,
        "has_validation_stop": any("validation fails" in condition.lower() for condition in stops),
        "has_benchmark_stop": any("benchmark check fails" in condition.lower() for condition in stops),
        "has_human_approval_stop": any("human approval is missing" in condition.lower() for condition in stops),
    }
    blockers = _dedupe([source_contract_error, source_decomposition_error, source_budget_error] + _source_blockers(source_contract, source_decomposition, source_budget))
    warnings = _source_warnings(source_contract, source_decomposition, source_budget)
    if source["source_count"] < 3:
        warnings.append("readiness source coverage is incomplete")
    warnings.append("CMD.4 is ready for human approval only; it is never ready for execution")
    status, reason, final_blockers = _classify(
        source_summary=source,
        gate_summary=gates,
        budget_summary=budget,
        blockers=blockers,
        active_authority_escalation=_active_authority_escalation(source_budget),
    )
    human = _human_approval_summary(gates, budget, source_budget)

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": READINESS_GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm(repo_path),
        "source_contract_path": str(source_contract_path or ""),
        "source_decomposition_path": str(source_decomposition_path or ""),
        "source_budget_path": str(source_budget_path or ""),
        "readiness_status": status,
        "readiness_reason": reason,
        "source_summary": source,
        "gate_summary": gates,
        "budget_summary": budget,
        "stop_condition_summary": stop_summary,
        "human_approval_summary": human,
        "required_before_implementation": _required_before_implementation(budget),
        "allowed_next_steps": list(ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(FORBIDDEN_NEXT_STEPS),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(final_blockers),
        "guardrails": _guardrails(),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_commander_readiness_markdown(report: dict[str, Any]) -> str:
    """Render a CMD.4 Commander Readiness Report as Markdown."""
    source = report.get("source_summary") if isinstance(report.get("source_summary"), dict) else {}
    gates = report.get("gate_summary") if isinstance(report.get("gate_summary"), dict) else {}
    budget = report.get("budget_summary") if isinstance(report.get("budget_summary"), dict) else {}
    stops = report.get("stop_condition_summary") if isinstance(report.get("stop_condition_summary"), dict) else {}
    human = report.get("human_approval_summary") if isinstance(report.get("human_approval_summary"), dict) else {}

    lines: list[str] = [
        "# Commander Readiness Report",
        "",
        f"> {report.get('guardrail_note', READINESS_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.4 checks readiness for human approval. It never declares a plan ready for execution._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(report.get('repo_path') or '(none)')}`",
        f"- **Readiness:** `{_md(report.get('readiness_status') or '')}`",
        "",
        "## Readiness Status",
        "",
        f"- **Status:** `{_md(report.get('readiness_status') or '')}`",
        f"- **Reason:** {_md(report.get('readiness_reason') or '')}",
        "",
        "## Source Coverage",
        "",
        f"- **Source count:** {source.get('source_count', 0)}",
        f"- **Contract:** {str(bool(source.get('has_contract'))).lower()} `{_md(report.get('source_contract_path') or '(none)')}`",
        f"- **Decomposition:** {str(bool(source.get('has_decomposition'))).lower()} `{_md(report.get('source_decomposition_path') or '(none)')}`",
        f"- **Budget:** {str(bool(source.get('has_budget'))).lower()} `{_md(report.get('source_budget_path') or '(none)')}`",
        "",
        "## Gate Summary",
        "",
        "| Gate | Present |",
        "| --- | --- |",
    ]
    gate_map = gates.get("gates") if isinstance(gates.get("gates"), dict) else {}
    for gate in TRACKED_GATES:
        lines.append(f"| `{gate}` | {str(bool(gate_map.get(gate))).lower()} |")
    lines.append("")
    lines.append("Missing gates:")
    _render_list(lines, _string_list(gates.get("missing_gates")), code=True)

    lines += [
        "## Budget Summary",
        "",
        f"- **Budget status:** `{_md(budget.get('budget_status') or '')}`",
        f"- **Limit classification:** `{_md(budget.get('limit_classification') or '')}`",
        f"- **Human reapproval required:** {str(bool(budget.get('human_reapproval_required'))).lower()}",
        f"- **Authority escalation required:** {str(bool(budget.get('authority_escalation_required'))).lower()}",
        f"- **Estimate:** {_md(budget.get('estimated_files_touched'))} files, {_md(budget.get('estimated_lines_changed'))} lines, {_md(budget.get('estimated_minutes'))} minutes",
        "",
        "## Stop Conditions",
        "",
    ]
    _render_list(lines, _string_list(stops.get("stop_conditions")))

    lines += [
        "## Human Approval Requirements",
        "",
        f"- **Human approval required:** {str(bool(human.get('human_approval_required'))).lower()}",
        f"- **Human approval gate present:** {str(bool(human.get('human_approval_gate_present'))).lower()}",
        f"- **Budget reapproval required:** {str(bool(human.get('budget_reapproval_required'))).lower()}",
        f"- **Approval status:** `{_md(human.get('approval_status') or '')}`",
        "",
        "Checkpoint ids:",
    ]
    _render_list(lines, _string_list(human.get("checkpoint_ids")), code=True)

    for title, key in (
        ("Required Before Implementation", "required_before_implementation"),
        ("Allowed Next Steps", "allowed_next_steps"),
        ("Forbidden Next Steps", "forbidden_next_steps"),
        ("Warnings", "warnings"),
        ("Blockers", "blockers"),
    ):
        lines += [f"## {title}", ""]
        _render_list(lines, _string_list(report.get(key)), code="Steps" in title or title.startswith("Required"))

    lines += ["## Boundaries", ""]
    for line in BOUNDARY_LINES:
        lines.append(f"- {line}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_commander_readiness_report(
    *,
    output_root: str | Path,
    repo_path: str = "",
    source_contract: Any = None,
    source_contract_path: str = "",
    source_contract_error: str = "",
    source_decomposition: Any = None,
    source_decomposition_path: str = "",
    source_decomposition_error: str = "",
    source_budget: Any = None,
    source_budget_path: str = "",
    source_budget_error: str = "",
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write the CMD.4 JSON + Markdown readiness artifacts."""
    report = build_commander_readiness_report(
        repo_path=repo_path,
        source_contract=source_contract,
        source_contract_path=source_contract_path,
        source_contract_error=source_contract_error,
        source_decomposition=source_decomposition,
        source_decomposition_path=source_decomposition_path,
        source_decomposition_error=source_decomposition_error,
        source_budget=source_budget,
        source_budget_path=source_budget_path,
        source_budget_error=source_budget_error,
        report_id=report_id,
        created_at=created_at,
    )
    out_dir = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_file_stem(report.get("report_id") or "")
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_commander_readiness_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
