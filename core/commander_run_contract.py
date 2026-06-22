"""CMD.1 - Commander Run Contract (report-only).

Classifies a plain-text user task into one planning-mode recommendation:
``instant_run``, ``commander_run``, ``needs_clarification``, or
``reject_or_defer``. The output previews complexity, required gates, stop
conditions, and a non-executing Commander plan shape for human review.

CMD.1 decides planning mode only. It does not execute Commander Mode, run
agents, call models, apply patches, run validation, run benchmarks, contact
network services, launch workers, write to a database, push, merge, or open PRs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "commander_run_contract"

RECOMMENDED_MODES: tuple[str, ...] = (
    "instant_run",
    "commander_run",
    "needs_clarification",
    "reject_or_defer",
)

COMPLEXITY_SIGNALS: tuple[str, ...] = (
    "file_count_signal",
    "line_count_signal",
    "phase_count_signal",
    "validation_signal",
    "benchmark_signal",
    "remote_signal",
    "model_signal",
    "patch_signal",
    "architecture_signal",
    "ambiguity_signal",
    "safety_signal",
)

ALLOWED_NEXT_STEPS: tuple[str, ...] = (
    "review_contract",
    "edit_task_scope",
    "create_followup_design_phase",
    "create_report_only_plan",
    "ask_human_for_approval",
)

FORBIDDEN_NEXT_STEPS: tuple[str, ...] = (
    "execute_commander_plan",
    "launch_worker",
    "apply_patch",
    "run_benchmark",
    "run_validation",
    "call_model",
    "contact_remote_service",
    "push_or_merge",
    "open_pr",
    "auto_approve",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
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
    "CMD.1 does not execute Commander Mode.",
    "CMD.1 does not run agents.",
    "CMD.1 does not call models.",
    "CMD.1 does not apply patches.",
    "CMD.1 does not run validation.",
    "CMD.1 does not run benchmarks.",
    "CMD.1 does not contact network services.",
    "CMD.1 does not launch workers.",
    "CMD.1 does not push, merge, or open PRs.",
    "CMD.1 is a report-only planning contract.",
)

COMMANDER_RUN_CONTRACT_GUARDRAIL_NOTE = (
    "Commander Run Contract is report-only: it classifies a task as instant_run, "
    "commander_run, needs_clarification, or reject_or_defer and previews gates "
    "and stop conditions. It does not execute Commander Mode, run agents, call "
    "models, apply patches, run validation, run benchmarks, contact network "
    "services, launch workers, write to a database, push, merge, or open PRs."
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


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item)
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _sorted_unique(items: list[str]) -> list[str]:
    return sorted(set(str(item) for item in items if str(item)))


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _signal(value: int, reason: str) -> dict[str, Any]:
    return {"value": int(value), "reason": reason}


def _task_summary(task: str) -> str:
    text = " ".join(str(task or "").split())
    if not text:
        return "(empty task)"
    return text if len(text) <= 140 else text[:137].rstrip() + "..."


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _estimated_file_count(changed_files: Any, estimated_files_touched: Any) -> int:
    explicit = _as_int(estimated_files_touched, 0)
    files = _string_list(changed_files)
    return explicit if explicit > 0 else len(files)


def _hard_reject_blockers(text: str) -> list[str]:
    blockers: list[str] = []
    if _contains_any(text, ("auto-merge", "auto merge", "enable auto merge", "merge automatically")):
        blockers.append("auto-merge is forbidden by CMD.1")
    if _contains_any(text, ("without approval", "bypass approval", "skip approval", "auto approve", "auto-approve")):
        blockers.append("bypassing human approval is forbidden by CMD.1")
    if _contains_any(text, ("hidden credential", "hidden secret", "api key", "secret key", "access token")):
        blockers.append("hidden credential or secret access is forbidden by CMD.1")
    if _contains_any(text, (".env", ".git", ".agent/private", "credentials", "secrets")):
        blockers.append("task touches a forbidden file or secret-bearing path")
    if (
        _contains_any(text, ("remote execution", "run remotely", "execute remotely", "remote run"))
        and _contains_any(text, ("without contract", "no contract", "bypass contract"))
    ):
        blockers.append("remote execution without a contract is forbidden by CMD.1")
    if _contains_any(text, ("push to main", "force push", "push without review")):
        blockers.append("push or merge authority is forbidden by CMD.1")
    return _dedupe(blockers)


def _ambiguity_blockers(task: str, repo_path: str, risk_notes: Any) -> list[str]:
    text = _lower(task)
    blockers: list[str] = []
    words = [part for part in text.replace(".", " ").split() if part]
    vague_phrases = (
        "make it better",
        "make better",
        "fix stuff",
        "do it",
        "handle this",
        "update things",
        "improve things",
        "clean up",
        "help me",
    )
    if not text:
        blockers.append("task description is empty")
    elif text in vague_phrases or (len(words) <= 2 and not _contains_any(text, ("typo", "readme", "test", "docs"))):
        blockers.append("task description is too vague to classify safely")
    if not _norm(repo_path):
        blockers.append("repo target is missing")
    notes = " ".join(_string_list(risk_notes)).lower()
    if _contains_any(notes, ("unknown risk", "ambiguous risk", "conflicting requirement")):
        blockers.append("risk notes are ambiguous or conflicting")
    return _dedupe(blockers)


def _build_signals(
    *,
    task: str,
    repo_path: str,
    changed_files: Any,
    estimated_files_touched: Any,
    estimated_lines_changed: Any,
    requires_network: bool,
    requires_model_calls: bool,
    requires_validation: bool,
    requires_benchmark: bool,
    requires_patch: bool,
    requires_remote_action: bool,
    risk_notes: Any,
    hard_blockers: list[str],
    ambiguity_blockers: list[str],
) -> dict[str, dict[str, Any]]:
    text = _lower(task)
    file_count = _estimated_file_count(changed_files, estimated_files_touched)
    line_count = _as_int(estimated_lines_changed, 0)

    if file_count >= 3:
        file_value, file_reason = 2, f"estimated scope touches {file_count} files"
    elif file_count == 2:
        file_value, file_reason = 1, "estimated scope touches 2 files"
    else:
        file_value, file_reason = 0, "estimated file scope is small or unspecified"

    if line_count >= 50:
        line_value, line_reason = 2, f"estimated change size is {line_count} lines"
    elif line_count >= 20:
        line_value, line_reason = 1, f"estimated change size is {line_count} lines"
    else:
        line_value, line_reason = 0, "estimated line change is small or unspecified"

    phase_terms = (
        "multi-phase",
        "multiple phase",
        "phase plan",
        "phases",
        "roadmap",
        "stop condition",
        "budget",
        "evidence",
        "decompose",
        "commander",
    )
    phase_hits = sum(1 for term in phase_terms if term in text)
    if "multi-phase" in text or "multiple phase" in text or phase_hits >= 3:
        phase_value, phase_reason = 2, "task implies multiple planning phases"
    elif phase_hits:
        phase_value, phase_reason = 1, "task has planning-phase language"
    else:
        phase_value, phase_reason = 0, "no multi-phase planning signal"

    validation_value = 1 if requires_validation or _contains_any(text, ("validation", "validate", "pytest", "test suite")) else 0
    benchmark_value = 2 if requires_benchmark or _contains_any(text, ("benchmark", "benchmarks", "flake", "eval.")) else 0
    remote_value = 2 if requires_remote_action or requires_network or _contains_any(text, ("remote", "github", "telegram", "n8n", "deploy", "open pr")) else 0
    model_value = 2 if requires_model_calls or _contains_any(text, ("model authority", "model call", "llm", "routing model")) else 0
    patch_value = 1 if requires_patch or _contains_any(text, ("patch", "write code", "implementation")) else 0
    architecture_value = 2 if _contains_any(
        text,
        (
            "architecture",
            "roadmap",
            "automation",
            "model authority",
            "remote workflow",
            "lessons",
            "phase registry",
            "commander mode",
            "mode router",
            "worker",
            "database",
            "sandbox",
        ),
    ) else 0
    ambiguity_value = 3 if ambiguity_blockers else 0
    safety_value = 3 if hard_blockers else (2 if model_value and "authority" in text else (1 if remote_value else 0))

    return {
        "file_count_signal": _signal(file_value, file_reason),
        "line_count_signal": _signal(line_value, line_reason),
        "phase_count_signal": _signal(phase_value, phase_reason),
        "validation_signal": _signal(validation_value, "validation is required or referenced" if validation_value else "no validation requirement signal"),
        "benchmark_signal": _signal(benchmark_value, "benchmark check is required or referenced" if benchmark_value else "no benchmark signal"),
        "remote_signal": _signal(remote_value, "remote or network action is required or referenced" if remote_value else "no remote action signal"),
        "model_signal": _signal(model_value, "model calls or model authority are referenced" if model_value else "no model authority signal"),
        "patch_signal": _signal(patch_value, "patch or implementation work is referenced" if patch_value else "no patch signal"),
        "architecture_signal": _signal(architecture_value, "architecture, roadmap, automation, or authority surface is referenced" if architecture_value else "no architecture signal"),
        "ambiguity_signal": _signal(ambiguity_value, "; ".join(ambiguity_blockers) if ambiguity_blockers else "task is specific enough for classification"),
        "safety_signal": _signal(safety_value, "; ".join(hard_blockers) if hard_blockers else "no hard safety rejection signal"),
    }


def _complexity_level(score: int) -> str:
    if score >= 7:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def _recommended_mode(signals: dict[str, dict[str, Any]], hard_blockers: list[str], ambiguity_blockers: list[str]) -> tuple[str, str]:
    if hard_blockers:
        return "reject_or_defer", "Hard safety blockers are present."
    if ambiguity_blockers:
        return "needs_clarification", "The task needs clearer scope, repo target, output, or risk details."

    score = sum(int(signals[name]["value"]) for name in COMPLEXITY_SIGNALS)
    commander_triggers = (
        signals["file_count_signal"]["value"] >= 2
        or signals["line_count_signal"]["value"] >= 2
        or signals["phase_count_signal"]["value"] >= 2
        or (signals["validation_signal"]["value"] and signals["benchmark_signal"]["value"])
        or signals["remote_signal"]["value"] > 0
        or signals["model_signal"]["value"] > 0
        or signals["architecture_signal"]["value"] > 0
        or score >= 5
    )
    if commander_triggers:
        return "commander_run", "Task is large, multi-phase, authority-sensitive, or requires stronger gates."
    return "instant_run", "Task appears small, low risk, local, and specific."


def _risk_level(mode: str, signals: dict[str, dict[str, Any]]) -> str:
    if mode == "reject_or_defer":
        return "blocked"
    if signals["safety_signal"]["value"] >= 2 or signals["remote_signal"]["value"] >= 2 or signals["model_signal"]["value"] >= 2:
        return "high"
    if mode == "commander_run" or sum(int(signals[name]["value"]) for name in COMPLEXITY_SIGNALS) >= 3:
        return "medium"
    return "low"


def _required_gates(
    *,
    mode: str,
    signals: dict[str, dict[str, Any]],
    requires_validation: bool,
    requires_benchmark: bool,
    requires_patch: bool,
    requires_remote_action: bool,
    requires_model_calls: bool,
    time_budget_minutes: Any,
) -> list[str]:
    gates = ["human_approval", "scope_confirmed"]
    if mode == "commander_run" or time_budget_minutes is not None:
        gates.append("budget_confirmed")
    if mode == "commander_run" or requires_validation or signals["validation_signal"]["value"]:
        gates.extend(["evidence_required", "validation_required"])
    if requires_benchmark or signals["benchmark_signal"]["value"]:
        gates.append("benchmark_check_required")
    if requires_patch or signals["patch_signal"]["value"] or mode == "commander_run":
        gates.append("rollback_plan_required")
    if requires_remote_action or signals["remote_signal"]["value"]:
        gates.append("remote_contract_required")
    if requires_model_calls or signals["model_signal"]["value"]:
        gates.append("model_authority_blocked")
    return _sorted_unique(gates)


def _stop_conditions() -> list[str]:
    return [
        "stop if task scope expands beyond estimate",
        "stop if forbidden files are requested",
        "stop if validation fails",
        "stop if benchmark check fails",
        "stop if model authority would be increased",
        "stop if remote action is requested",
        "stop if human approval is missing",
    ]


def _warnings(
    *,
    mode: str,
    signals: dict[str, dict[str, Any]],
    requires_validation: bool,
    requires_benchmark: bool,
    requires_patch: bool,
    requires_remote_action: bool,
    requires_model_calls: bool,
) -> list[str]:
    warnings: list[str] = []
    if mode == "instant_run":
        warnings.append("instant_run is only a recommendation; CMD.1 did not execute it")
    if requires_validation or signals["validation_signal"]["value"]:
        warnings.append("validation is a future gate; CMD.1 did not run validation")
    if requires_benchmark or signals["benchmark_signal"]["value"]:
        warnings.append("benchmark check is a future gate; CMD.1 did not run benchmarks")
    if requires_patch or signals["patch_signal"]["value"]:
        warnings.append("patch work may be needed later; CMD.1 did not apply patches")
    if requires_remote_action or signals["remote_signal"]["value"]:
        warnings.append("remote action requires a separate remote contract and human approval")
    if requires_model_calls or signals["model_signal"]["value"]:
        warnings.append("model calls or model authority require separate approval; CMD.1 did not call models")
    return _dedupe(warnings)


def _model_authority_blockers(text: str, requires_model_calls: bool) -> list[str]:
    if requires_model_calls or _contains_any(text, ("model authority", "model call", "llm", "routing model")):
        return ["model authority changes are blocked by CMD.1 and require a separate approved phase"]
    return []


def _estimated_scope(
    *,
    changed_files: Any,
    estimated_files_touched: Any,
    estimated_lines_changed: Any,
    time_budget_minutes: Any,
    risk_notes: Any,
) -> dict[str, Any]:
    files = _string_list(changed_files)
    return {
        "changed_files": files,
        "changed_file_count": len(files),
        "estimated_files_touched": _as_int(estimated_files_touched, 0),
        "estimated_lines_changed": _as_int(estimated_lines_changed, 0),
        "time_budget_minutes": _as_int(time_budget_minutes, 0) if time_budget_minutes is not None else None,
        "risk_notes": _string_list(risk_notes),
    }


def _commander_preview(mode: str, required_gates: list[str], time_budget_minutes: Any) -> dict[str, Any]:
    budget_text = (
        f"Use the declared {time_budget_minutes} minute budget as a stop gate."
        if time_budget_minutes is not None
        else "Confirm a time and scope budget before any Commander-style execution."
    )
    return {
        "non_executing": True,
        "phase_plan_preview": [
            "Confirm task scope and mode recommendation.",
            "Split work into reviewable phases only in a follow-up plan.",
            "Stop before execution; this preview does not start Commander Mode.",
        ],
        "evidence_plan_preview": [
            "List evidence expected from future implementation.",
            "Record files, commands, and artifact paths in a follow-up report.",
        ],
        "validation_plan_preview": [
            "Name validation commands as future gates only.",
            "Do not run validation from CMD.1.",
        ],
        "budget_plan_preview": [budget_text],
        "rollback_plan_preview": [
            "Require a rollback or revert plan before future patch work.",
            "Stop if scope exceeds the original estimate.",
        ],
        "human_checkpoint_preview": [
            "Require human review of this contract.",
            f"Confirm required gates: {', '.join(required_gates) if required_gates else '(none)'}",
            f"Recommended mode: {mode}",
        ],
    }


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def build_commander_run_contract(
    *,
    task: str,
    repo_path: str = "",
    changed_files: Any = None,
    estimated_files_touched: Any = None,
    estimated_lines_changed: Any = None,
    requires_network: bool = False,
    requires_model_calls: bool = False,
    requires_validation: bool = False,
    requires_benchmark: bool = False,
    requires_patch: bool = False,
    requires_remote_action: bool = False,
    time_budget_minutes: Any = None,
    risk_notes: Any = None,
    contract_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build a deterministic report-only Commander Run Contract."""
    text = _lower(task)
    hard_blockers = _hard_reject_blockers(text)
    ambiguity = _ambiguity_blockers(task, repo_path, risk_notes)
    signals = _build_signals(
        task=task,
        repo_path=repo_path,
        changed_files=changed_files,
        estimated_files_touched=estimated_files_touched,
        estimated_lines_changed=estimated_lines_changed,
        requires_network=bool(requires_network),
        requires_model_calls=bool(requires_model_calls),
        requires_validation=bool(requires_validation),
        requires_benchmark=bool(requires_benchmark),
        requires_patch=bool(requires_patch),
        requires_remote_action=bool(requires_remote_action),
        risk_notes=risk_notes,
        hard_blockers=hard_blockers,
        ambiguity_blockers=ambiguity,
    )
    complexity_score = sum(int(signals[name]["value"]) for name in COMPLEXITY_SIGNALS)
    mode, mode_reason = _recommended_mode(signals, hard_blockers, ambiguity)
    required_gates = _required_gates(
        mode=mode,
        signals=signals,
        requires_validation=bool(requires_validation),
        requires_benchmark=bool(requires_benchmark),
        requires_patch=bool(requires_patch),
        requires_remote_action=bool(requires_remote_action),
        requires_model_calls=bool(requires_model_calls),
        time_budget_minutes=time_budget_minutes,
    )
    blockers = _dedupe(hard_blockers + ambiguity + _model_authority_blockers(text, bool(requires_model_calls)))

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": COMMANDER_RUN_CONTRACT_GUARDRAIL_NOTE,
        "contract_id": str(contract_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm(repo_path),
        "task": str(task or ""),
        "task_summary": _task_summary(task),
        "recommended_mode": mode,
        "mode_reason": mode_reason,
        "risk_level": _risk_level(mode, signals),
        "complexity_level": _complexity_level(complexity_score),
        "complexity_score": complexity_score,
        "signals": signals,
        "estimated_scope": _estimated_scope(
            changed_files=changed_files,
            estimated_files_touched=estimated_files_touched,
            estimated_lines_changed=estimated_lines_changed,
            time_budget_minutes=time_budget_minutes,
            risk_notes=risk_notes,
        ),
        "required_gates": required_gates,
        "stop_conditions": _stop_conditions(),
        "allowed_next_steps": list(ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(FORBIDDEN_NEXT_STEPS),
        "commander_preview": _commander_preview(mode, required_gates, time_budget_minutes),
        "warnings": _warnings(
            mode=mode,
            signals=signals,
            requires_validation=bool(requires_validation),
            requires_benchmark=bool(requires_benchmark),
            requires_patch=bool(requires_patch),
            requires_remote_action=bool(requires_remote_action),
            requires_model_calls=bool(requires_model_calls),
        ),
        "blockers": blockers,
        "guardrails": _guardrails(),
    }


def render_commander_run_contract_markdown(contract: dict[str, Any]) -> str:
    """Render a Commander Run Contract as operator-facing Markdown."""
    lines: list[str] = [
        "# Commander Run Contract",
        "",
        f"> {contract.get('guardrail_note', COMMANDER_RUN_CONTRACT_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.1 decides planning mode only. It previews Commander-style gates and stop conditions but performs no execution._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Contract id:** `{_md(contract.get('contract_id') or '(none)')}`",
        f"- **Created at:** `{_md(contract.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(contract.get('repo_path') or '(none)')}`",
        f"- **Task summary:** {_md(contract.get('task_summary') or '')}",
        f"- **Risk level:** `{_md(contract.get('risk_level') or '')}`",
        f"- **Complexity level:** `{_md(contract.get('complexity_level') or '')}`",
        f"- **Complexity score:** {contract.get('complexity_score', 0)}",
        "",
        "## Recommended Mode",
        "",
        f"- **Mode:** `{_md(contract.get('recommended_mode') or '')}`",
        f"- **Reason:** {_md(contract.get('mode_reason') or '')}",
        "",
        "## Complexity Signals",
        "",
        "| Signal | Value | Reason |",
        "| --- | ---: | --- |",
    ]
    signals = contract.get("signals") if isinstance(contract.get("signals"), dict) else {}
    for name in COMPLEXITY_SIGNALS:
        sig = signals.get(name) if isinstance(signals.get(name), dict) else {}
        lines.append(f"| `{name}` | {sig.get('value', 0)} | {_md(sig.get('reason', ''))} |")
    lines.append("")

    for title, key in (
        ("Required Gates", "required_gates"),
        ("Stop Conditions", "stop_conditions"),
    ):
        lines += [f"## {title}", ""]
        values = contract.get(key) or []
        if values:
            for item in values:
                lines.append(f"- `{_md(item)}`" if key == "required_gates" else f"- {_md(item)}")
        else:
            lines.append("_None._")
        lines.append("")

    preview = contract.get("commander_preview") if isinstance(contract.get("commander_preview"), dict) else {}
    lines += [
        "## Commander Preview",
        "",
        f"- **Non-executing:** {str(bool(preview.get('non_executing'))).lower()}",
        "",
    ]
    for label, key in (
        ("Phase plan", "phase_plan_preview"),
        ("Evidence plan", "evidence_plan_preview"),
        ("Validation plan", "validation_plan_preview"),
        ("Budget plan", "budget_plan_preview"),
        ("Rollback plan", "rollback_plan_preview"),
        ("Human checkpoint", "human_checkpoint_preview"),
    ):
        lines.append(f"**{label}:**")
        for item in preview.get(key) or []:
            lines.append(f"- {_md(item)}")
        lines.append("")

    for title, key in (
        ("Allowed Next Steps", "allowed_next_steps"),
        ("Forbidden Next Steps", "forbidden_next_steps"),
        ("Warnings", "warnings"),
        ("Blockers", "blockers"),
    ):
        lines += [f"## {title}", ""]
        values = contract.get(key) or []
        if values:
            for item in values:
                lines.append(f"- `{_md(item)}`" if "Steps" in title else f"- {_md(item)}")
        else:
            lines.append("_None._")
        lines.append("")

    lines += ["## Boundaries", ""]
    for line in BOUNDARY_LINES:
        lines.append(f"- {line}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _safe_file_stem(contract_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in str(contract_id or ""))
    cleaned = cleaned.strip("-._")
    return cleaned or "commander_run_contract"


def write_commander_run_contract(
    *,
    output_root: str | Path,
    task: str,
    repo_path: str = "",
    changed_files: Any = None,
    estimated_files_touched: Any = None,
    estimated_lines_changed: Any = None,
    requires_network: bool = False,
    requires_model_calls: bool = False,
    requires_validation: bool = False,
    requires_benchmark: bool = False,
    requires_patch: bool = False,
    requires_remote_action: bool = False,
    time_budget_minutes: Any = None,
    risk_notes: Any = None,
    contract_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write the JSON + Markdown CMD.1 artifacts."""
    contract = build_commander_run_contract(
        task=task,
        repo_path=repo_path,
        changed_files=changed_files,
        estimated_files_touched=estimated_files_touched,
        estimated_lines_changed=estimated_lines_changed,
        requires_network=requires_network,
        requires_model_calls=requires_model_calls,
        requires_validation=requires_validation,
        requires_benchmark=requires_benchmark,
        requires_patch=requires_patch,
        requires_remote_action=requires_remote_action,
        time_budget_minutes=time_budget_minutes,
        risk_notes=risk_notes,
        contract_id=contract_id,
        created_at=created_at,
    )
    out_dir = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_file_stem(contract.get("contract_id") or "")
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_commander_run_contract_markdown(contract), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "contract": contract}
