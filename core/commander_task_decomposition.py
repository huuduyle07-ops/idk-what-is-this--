"""CMD.2 - Task Decomposition Preview (report-only).

Builds a deterministic decomposition preview from a CMD.1 Commander Run Contract
or a plain task description. CMD.2 decomposes the task into preview phases and
gate plans only. It does not execute the decomposition, run agents, call models,
apply patches, run validation, run benchmarks, contact network services, launch
workers, write to a database, push, merge, or open PRs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "commander_task_decomposition_preview"

ALLOWED_NEXT_STEPS: tuple[str, ...] = (
    "review_decomposition_preview",
    "edit_phase_plan",
    "create_report_only_implementation_prompt",
    "ask_human_for_scope_approval",
    "create_next_cmd_contract",
)

FORBIDDEN_NEXT_STEPS: tuple[str, ...] = (
    "execute_decomposition",
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
    "decomposition_executed",
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
    "CMD.2 does not execute the decomposition.",
    "CMD.2 does not run agents.",
    "CMD.2 does not call models.",
    "CMD.2 does not apply patches.",
    "CMD.2 does not run validation.",
    "CMD.2 does not run benchmarks.",
    "CMD.2 does not contact network services.",
    "CMD.2 does not launch workers.",
    "CMD.2 does not push, merge, or open PRs.",
    "CMD.2 is a report-only decomposition preview.",
)

TASK_DECOMPOSITION_GUARDRAIL_NOTE = (
    "Task Decomposition Preview is report-only: it turns a CMD.1 contract or task "
    "description into a deterministic preview phase plan with evidence, validation, "
    "benchmark, budget, rollback, and human checkpoint gates. It does not execute "
    "the decomposition, run agents, call models, apply patches, run validation, run "
    "benchmarks, contact network services, launch workers, write to a database, "
    "push, merge, or open PRs."
)

DEFAULT_PHASES: tuple[dict[str, str], ...] = (
    {
        "phase_id": "scope_review",
        "title": "Scope Review",
        "purpose": "Confirm the task, source contract, boundaries, estimates, and stop conditions.",
    },
    {
        "phase_id": "design_contract",
        "title": "Design Contract",
        "purpose": "Turn the accepted scope into a written report-only implementation contract.",
    },
    {
        "phase_id": "implementation_plan",
        "title": "Implementation Plan",
        "purpose": "Describe the future code/docs/test changes without applying them.",
    },
    {
        "phase_id": "validation_plan",
        "title": "Validation Plan",
        "purpose": "List future validation and benchmark gates as text-only commands.",
    },
    {
        "phase_id": "handoff_summary",
        "title": "Handoff Summary",
        "purpose": "Summarize evidence, remaining risks, rollback notes, and human approvals.",
    },
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _norm(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip()


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


def _safe_file_stem(preview_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in str(preview_id or ""))
    cleaned = cleaned.strip("-._")
    return cleaned or "task_decomposition_preview"


def read_source_contract(path: str | Path) -> tuple[dict[str, Any] | None, str]:
    """Read an optional CMD.1 contract JSON file.

    Returns ``(contract, error)``. Missing, malformed, or non-object input is an
    error string instead of an exception so CMD.2 can write a blocker report.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read contract at {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"could not read contract at {path}: contract JSON is not an object"
    if str(data.get("report_kind") or "") != "commander_run_contract":
        return None, f"could not read contract at {path}: not a CMD.1 commander_run_contract"
    return data, ""


def _source_values(
    *,
    task: str,
    source_contract: Any,
    source_contract_error: str,
) -> dict[str, Any]:
    contract = source_contract if isinstance(source_contract, dict) else {}
    if contract:
        scope = contract.get("estimated_scope") if isinstance(contract.get("estimated_scope"), dict) else {}
        return {
            "task": str(contract.get("task") or task or ""),
            "source_mode": str(contract.get("recommended_mode") or "unknown"),
            "source_risk_level": str(contract.get("risk_level") or "unknown"),
            "source_complexity_level": str(contract.get("complexity_level") or "unknown"),
            "source_complexity_score": _as_int(contract.get("complexity_score"), 0),
            "required_gates": _string_list(contract.get("required_gates")),
            "stop_conditions": _string_list(contract.get("stop_conditions")),
            "changed_files": _string_list(scope.get("changed_files")),
            "estimated_files_touched": _as_int(scope.get("estimated_files_touched"), 0),
            "estimated_lines_changed": _as_int(scope.get("estimated_lines_changed"), 0),
            "time_budget_minutes": scope.get("time_budget_minutes"),
            "source": "contract",
        }
    return {
        "task": str(task or ""),
        "source_mode": "unavailable" if source_contract_error else "task_only",
        "source_risk_level": "unknown",
        "source_complexity_level": "unknown",
        "source_complexity_score": 0,
        "required_gates": ["human_approval", "scope_confirmed"],
        "stop_conditions": _default_stop_conditions(),
        "changed_files": [],
        "estimated_files_touched": 0,
        "estimated_lines_changed": 0,
        "time_budget_minutes": None,
        "source": "contract_error" if source_contract_error else "task_only",
    }


def _default_stop_conditions() -> list[str]:
    return [
        "stop if task scope expands beyond estimate",
        "stop if forbidden files are requested",
        "stop if validation fails",
        "stop if benchmark check fails",
        "stop if remote action is requested",
        "stop if human approval is missing",
    ]


def _phase_expected_inputs(phase_id: str) -> list[str]:
    base = {
        "scope_review": ["CMD.1 contract or task text", "repo path", "declared estimates"],
        "design_contract": ["approved scope", "required gates", "stop conditions"],
        "implementation_plan": ["design contract", "allowed files", "forbidden files"],
        "validation_plan": ["implementation plan", "test targets", "registry touch status"],
        "handoff_summary": ["evidence checklist", "validation plan", "rollback notes"],
    }
    return list(base.get(phase_id, ["accepted previous phase output"]))


def _phase_expected_outputs(phase_id: str) -> list[str]:
    base = {
        "scope_review": ["confirmed scope notes", "open blockers list"],
        "design_contract": ["report-only design notes", "phase ownership map"],
        "implementation_plan": ["future file-change plan", "test-first checklist"],
        "validation_plan": ["text-only validation commands", "benchmark check note"],
        "handoff_summary": ["operator summary", "human approval checklist"],
    }
    return list(base.get(phase_id, ["phase preview notes"]))


def _phase_allowed_actions(phase_id: str) -> list[str]:
    base = {
        "scope_review": ["review_scope", "edit_estimates", "record_blockers"],
        "design_contract": ["write_report_only_design", "review_gate_list"],
        "implementation_plan": ["write_report_only_plan", "list_future_tests"],
        "validation_plan": ["list_validation_text", "list_benchmark_text"],
        "handoff_summary": ["summarize_evidence", "request_human_review"],
    }
    return list(base.get(phase_id, ["review_preview"]))


def _phase_plan(
    *,
    max_phases: Any,
    source_risk_level: str,
    stop_conditions: list[str],
    required_gates: list[str],
) -> list[dict[str, Any]]:
    limit = max(1, min(len(DEFAULT_PHASES), _as_int(max_phases, len(DEFAULT_PHASES))))
    needs_validation = "validation_required" in required_gates
    out: list[dict[str, Any]] = []
    for index, phase in enumerate(DEFAULT_PHASES[:limit], start=1):
        phase_id = phase["phase_id"]
        validation_required = needs_validation and phase_id in {"implementation_plan", "validation_plan"}
        out.append(
            {
                "phase_index": index,
                "phase_id": phase_id,
                "title": phase["title"],
                "purpose": phase["purpose"],
                "expected_inputs": _phase_expected_inputs(phase_id),
                "expected_outputs": _phase_expected_outputs(phase_id),
                "evidence_required": True,
                "validation_required": bool(validation_required),
                "estimated_risk": source_risk_level if source_risk_level != "unknown" else "medium",
                "human_checkpoint_required": True,
                "stop_conditions": list(stop_conditions),
                "allowed_actions": _phase_allowed_actions(phase_id),
                "forbidden_actions": list(FORBIDDEN_NEXT_STEPS),
            }
        )
    return out


def _task_summary(task: str) -> str:
    text = " ".join(str(task or "").split())
    if not text:
        return "(empty task)"
    return text if len(text) <= 140 else text[:137].rstrip() + "..."


def _evidence_plan(preview_id: str, changed_files: list[str]) -> dict[str, Any]:
    stem = _safe_file_stem(preview_id or "<preview_id>")
    return {
        "changed_files": list(changed_files),
        "generated_artifacts": [
            f".agent/commander/decomposition_previews/{stem}.json",
            f".agent/commander/decomposition_previews/{stem}.md",
        ],
        "tests_run_by_human_later": [
            "python -m pytest tests/test_commander_task_decomposition.py -q",
            "python -m pytest -q",
        ],
        "benchmark_check_run_by_human_later": "python benchmarks/run_benchmarks.py --check",
        "guardrail_confirmation": [f"{key}=false" for key in GUARDRAIL_FALSE_FLAGS],
        "rollback_notes": [
            "Review the future diff before committing.",
            "Keep future implementation isolated in a human-reviewed commit.",
        ],
    }


def _validation_plan() -> dict[str, Any]:
    return {
        "text_only": True,
        "validation_run": False,
        "commands": [
            "python -m compileall -q core scripts web tests benchmarks",
            "python -m pytest tests/test_commander_task_decomposition.py -q",
            "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
            "python -m pytest -q",
        ],
    }


def _benchmark_plan() -> dict[str, Any]:
    return {
        "text_only": True,
        "benchmark_run_performed": False,
        "commands": ["python benchmarks/run_benchmarks.py --check"],
    }


def _budget_plan(
    *,
    estimated_files_touched: int,
    estimated_lines_changed: int,
    time_budget_minutes: Any,
    phase_count: int,
) -> dict[str, Any]:
    files = estimated_files_touched
    lines = estimated_lines_changed
    review_cost = "medium" if files >= 3 or lines >= 50 else "low"
    validation_cost = "high" if phase_count >= 5 else "medium"
    return {
        "estimated_files_touched": files,
        "estimated_lines_changed": lines,
        "estimated_human_review_cost": review_cost,
        "estimated_validation_cost": validation_cost,
        "time_budget_minutes": time_budget_minutes,
        "stop_if_over_budget_rule": "Stop if files, lines, time, risk, or gates exceed the accepted CMD.1 estimate.",
    }


def _rollback_plan() -> dict[str, Any]:
    return {
        "steps": [
            "Perform git diff review before any future commit.",
            "Use commit isolation for any future implementation.",
            "Revert commit if the future implementation fails review.",
            "Do not auto-rollback from CMD.2.",
        ],
        "auto_rollback_allowed": False,
    }


def _human_checkpoint(required_gates: list[str]) -> dict[str, Any]:
    gates = _dedupe(required_gates or ["human_approval", "scope_confirmed"])
    return {
        "required_gates": gates,
        "checkpoints": [
            "Approve scope before implementation.",
            "Inspect evidence after implementation.",
            "Approve commit before integration.",
            "Approve any future escalation.",
        ],
    }


def build_task_decomposition_preview(
    *,
    task: str = "",
    repo_path: str = "",
    source_contract: Any = None,
    source_contract_path: str = "",
    source_contract_error: str = "",
    max_phases: Any = 5,
    preview_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build a deterministic CMD.2 report-only decomposition preview."""
    source = _source_values(task=task, source_contract=source_contract, source_contract_error=source_contract_error)
    chosen_task = source["task"]
    stop_conditions = _dedupe(source["stop_conditions"] or _default_stop_conditions())
    required_gates = _dedupe(source["required_gates"] or ["human_approval", "scope_confirmed"])
    phases = _phase_plan(
        max_phases=max_phases,
        source_risk_level=source["source_risk_level"],
        stop_conditions=stop_conditions,
        required_gates=required_gates,
    )

    warnings: list[str] = []
    if isinstance(source_contract, dict) and task:
        warnings.append("extra task text was provided; contract fields took priority")
    if not isinstance(source_contract, dict) and source_contract_path and not source_contract_error:
        warnings.append("source contract path was provided but no contract data was loaded")
    warnings.extend(
        [
            "phase plan is a preview only and is not registered roadmap phase data",
            "validation and benchmark commands are text-only future gates",
        ]
    )

    blockers: list[str] = []
    if source_contract_error:
        blockers.append(source_contract_error)
    if not chosen_task:
        blockers.append("task description is missing and no readable CMD.1 contract supplied it")

    decomposition_summary = {
        "task_summary": _task_summary(chosen_task),
        "phase_count": len(phases),
        "source": source["source"],
        "preview_only": True,
        "extra_task_note": str(task or "") if isinstance(source_contract, dict) and task else "",
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": TASK_DECOMPOSITION_GUARDRAIL_NOTE,
        "preview_id": str(preview_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm(repo_path),
        "source_contract_path": str(source_contract_path or ""),
        "task": chosen_task,
        "source_mode": source["source_mode"],
        "source_risk_level": source["source_risk_level"],
        "source_complexity_level": source["source_complexity_level"],
        "source_complexity_score": source["source_complexity_score"],
        "decomposition_summary": decomposition_summary,
        "phase_plan_preview": phases,
        "evidence_plan_preview": _evidence_plan(preview_id, source["changed_files"]),
        "validation_plan_preview": _validation_plan(),
        "benchmark_plan_preview": _benchmark_plan(),
        "budget_plan_preview": _budget_plan(
            estimated_files_touched=source["estimated_files_touched"],
            estimated_lines_changed=source["estimated_lines_changed"],
            time_budget_minutes=source["time_budget_minutes"],
            phase_count=len(phases),
        ),
        "rollback_plan_preview": _rollback_plan(),
        "human_checkpoint_preview": _human_checkpoint(required_gates),
        "stop_conditions": stop_conditions,
        "allowed_next_steps": list(ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(FORBIDDEN_NEXT_STEPS),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "guardrails": _guardrails(),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_task_decomposition_markdown(preview: dict[str, Any]) -> str:
    """Render a CMD.2 preview as operator-facing Markdown."""
    summary = preview.get("decomposition_summary") if isinstance(preview.get("decomposition_summary"), dict) else {}
    lines: list[str] = [
        "# Task Decomposition Preview",
        "",
        f"> {preview.get('guardrail_note', TASK_DECOMPOSITION_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.2 decomposes the task into preview phases and gate plans. It runs nothing and changes nothing._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Preview id:** `{_md(preview.get('preview_id') or '(none)')}`",
        f"- **Created at:** `{_md(preview.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(preview.get('repo_path') or '(none)')}`",
        f"- **Task:** {_md(summary.get('task_summary') or preview.get('task') or '')}",
        f"- **Phase count:** {summary.get('phase_count', len(preview.get('phase_plan_preview') or []))}",
        "",
        "## Source Contract",
        "",
        f"- **Path:** `{_md(preview.get('source_contract_path') or '(none)')}`",
        f"- **Mode:** `{_md(preview.get('source_mode') or '')}`",
        f"- **Risk:** `{_md(preview.get('source_risk_level') or '')}`",
        f"- **Complexity:** `{_md(preview.get('source_complexity_level') or '')}`",
        f"- **Complexity score:** {preview.get('source_complexity_score', 0)}",
        "",
        "## Phase Plan Preview",
        "",
    ]
    phases = preview.get("phase_plan_preview") or []
    if phases:
        lines += [
            "| # | Phase | Title | Risk | Validation | Purpose |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
        for phase in phases:
            lines.append(
                f"| {phase.get('phase_index')} | `{_md(phase.get('phase_id'))}` | "
                f"{_md(phase.get('title'))} | `{_md(phase.get('estimated_risk'))}` | "
                f"{str(bool(phase.get('validation_required'))).lower()} | {_md(phase.get('purpose'))} |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    evidence = preview.get("evidence_plan_preview") if isinstance(preview.get("evidence_plan_preview"), dict) else {}
    lines += ["## Evidence Plan Preview", ""]
    lines.append("Changed files:")
    _render_list(lines, _string_list(evidence.get("changed_files")), code=True)
    lines.append("Generated artifacts:")
    _render_list(lines, _string_list(evidence.get("generated_artifacts")), code=True)

    validation = preview.get("validation_plan_preview") if isinstance(preview.get("validation_plan_preview"), dict) else {}
    lines += ["## Validation Plan Preview", ""]
    lines.append(f"- **Text only:** {str(bool(validation.get('text_only'))).lower()}")
    lines.append(f"- **Validation run:** {str(bool(validation.get('validation_run'))).lower()}")
    lines.append("")
    _render_list(lines, _string_list(validation.get("commands")), code=True)

    benchmark = preview.get("benchmark_plan_preview") if isinstance(preview.get("benchmark_plan_preview"), dict) else {}
    lines += ["## Benchmark Plan Preview", ""]
    lines.append(f"- **Text only:** {str(bool(benchmark.get('text_only'))).lower()}")
    lines.append(f"- **Benchmark run performed:** {str(bool(benchmark.get('benchmark_run_performed'))).lower()}")
    lines.append("")
    _render_list(lines, _string_list(benchmark.get("commands")), code=True)

    budget = preview.get("budget_plan_preview") if isinstance(preview.get("budget_plan_preview"), dict) else {}
    lines += ["## Budget Plan Preview", ""]
    for key in (
        "estimated_files_touched",
        "estimated_lines_changed",
        "estimated_human_review_cost",
        "estimated_validation_cost",
        "time_budget_minutes",
        "stop_if_over_budget_rule",
    ):
        lines.append(f"- **{_md(key)}:** {_md(budget.get(key))}")
    lines.append("")

    rollback = preview.get("rollback_plan_preview") if isinstance(preview.get("rollback_plan_preview"), dict) else {}
    lines += ["## Rollback Plan Preview", ""]
    _render_list(lines, _string_list(rollback.get("steps")))
    lines.append(f"- **Auto rollback allowed:** {str(bool(rollback.get('auto_rollback_allowed'))).lower()}")
    lines.append("")

    checkpoint = preview.get("human_checkpoint_preview") if isinstance(preview.get("human_checkpoint_preview"), dict) else {}
    lines += ["## Human Checkpoints", ""]
    _render_list(lines, _string_list(checkpoint.get("checkpoints")))

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


def write_task_decomposition_preview(
    *,
    output_root: str | Path,
    task: str = "",
    repo_path: str = "",
    source_contract: Any = None,
    source_contract_path: str = "",
    source_contract_error: str = "",
    max_phases: Any = 5,
    preview_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write the CMD.2 JSON + Markdown preview artifacts."""
    preview = build_task_decomposition_preview(
        task=task,
        repo_path=repo_path,
        source_contract=source_contract,
        source_contract_path=source_contract_path,
        source_contract_error=source_contract_error,
        max_phases=max_phases,
        preview_id=preview_id,
        created_at=created_at,
    )
    out_dir = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_file_stem(preview.get("preview_id") or "")
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_task_decomposition_markdown(preview), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "preview": preview}
