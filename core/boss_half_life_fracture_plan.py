"""CMD.N1 - Boss Half-Life Fracture Plan (report-only).

Defines a deterministic Boss Half-Life Fracture model for deciding when a large
task is not shrinking quickly enough and should be reviewed for fracture into
smaller sub-bosses. CMD.N1 writes planning artifacts only. It does not decompose
tasks, assign workers, call models, launch Commander mode, affect routing, apply
patches, run validation, run benchmarks, contact networks, write databases, or
change runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "boss_half_life_fracture_plan"
JSON_NAME = "boss_half_life_fracture_plan.json"
MD_NAME = "boss_half_life_fracture_plan.md"

DEFAULT_INITIAL_COMPLEXITY = 100.0
DEFAULT_ACTUAL_REMAINING = 50.0
DEFAULT_ATTEMPT = 3
DEFAULT_MAX_ATTEMPTS = 6
DEFAULT_AGGRESSIVENESS = 2.0
DEFAULT_TOLERANCE = 0.20

COMMANDER_DECISION_STATUSES: tuple[str, ...] = (
    "ahead_of_decay",
    "on_track",
    "review_recommended",
    "fracture_recommended",
    "hard_fracture_required",
    "invalid_parameters",
)

RECOMMENDED_SUB_BOSS_FIELDS: tuple[str, ...] = (
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
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "model_call_performed",
    "patch_applied",
    "validation_run",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "worker_launch_performed",
    "commander_mode_launched",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_performed",
    "network_call_performed",
    "database_write_performed",
    "route_behavior_changed",
    "auth_policy_changed",
    "automatic_decomposition_performed",
    "automatic_worker_assignment_performed",
    "routing_change_performed",
)

FORBIDDEN_NEXT_STEPS: tuple[str, ...] = (
    "actually_decompose_tasks",
    "assign_workers",
    "launch_commander_mode",
    "call_model",
    "apply_patch",
    "run_validation",
    "run_benchmark",
    "invoke_mcp",
    "launch_worker",
    "execute_dream",
    "apply_replay_janitor",
    "use_docker_or_subprocess",
    "contact_network",
    "write_database",
    "change_routes",
    "change_auth_policy",
    "auto_decompose",
    "auto_assign_worker",
)

ALLOWED_NEXT_STEPS: tuple[str, ...] = (
    "review_boss_half_life_fracture_plan",
    "compare_actual_remaining_against_expected_decay",
    "record_human_complexity_estimates",
    "prepare_cmd_n2_report_only_sub_boss_contract",
)

BOSS_HALF_LIFE_GUARDRAIL_NOTE = (
    "Boss Half-Life Fracture Plan is report-only: it defines a deterministic "
    "stagnation model for comparing actual remaining complexity against an "
    "expected half-life decay curve. It writes plan artifacts only and does not "
    "decompose tasks, assign workers, call models, launch Commander mode, affect "
    "routing, apply patches, run validation, run benchmarks, invoke MCP tools, "
    "execute Dream actions, apply Replay janitor actions, use Docker/subprocess, "
    "contact networks, write databases, change auth policy, or change route "
    "behavior."
)

FORMULA = "B_t = B_0 * (1/2) ** (t / H)"
HALF_LIFE_FORMULA = "H = T / k"


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _finite(value: float) -> bool:
    return value == value and abs(value) != float("inf")


def _as_float(value: Any, field: str, blockers: list[str]) -> float:
    if isinstance(value, bool):
        blockers.append(f"{field} must be a number, not a boolean")
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        blockers.append(f"{field} must be a number")
        return 0.0
    if not _finite(number):
        blockers.append(f"{field} must be finite")
        return 0.0
    return number


def _as_int(value: Any, field: str, blockers: list[str]) -> int:
    number = _as_float(value, field, blockers)
    if blockers and any(field in item for item in blockers):
        return 0
    if not number.is_integer():
        blockers.append(f"{field} must be an integer attempt count")
        return 0
    return int(number)


def _round_metric(value: float | None, places: int = 6) -> float | int | None:
    if value is None:
        return None
    rounded = round(value, places)
    if float(rounded).is_integer():
        return int(rounded)
    return rounded


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def expected_remaining_complexity(initial_complexity: float, attempt: int, half_life: float) -> float:
    """Return expected remaining complexity for attempt ``t`` on the half-life curve."""
    return float(initial_complexity) * (0.5 ** (float(attempt) / float(half_life)))


def classify_fracture_pressure(fracture_pressure: float | None, tolerance: float = DEFAULT_TOLERANCE) -> str:
    """Classify ``actual_remaining / expected_remaining`` into Commander status text."""
    if fracture_pressure is None:
        return "invalid_parameters"
    if fracture_pressure < 1.0:
        return "ahead_of_decay"
    if fracture_pressure < 1.0 + tolerance:
        return "on_track"
    if fracture_pressure < 1.5:
        return "review_recommended"
    if fracture_pressure < 2.0:
        return "fracture_recommended"
    return "hard_fracture_required"


def _thresholds(tolerance: float) -> list[dict[str, str]]:
    return [
        {
            "status": "ahead_of_decay",
            "range": "fracture_pressure < 1.0",
            "meaning": "The boss is shrinking faster than the expected half-life curve.",
        },
        {
            "status": "on_track",
            "range": f"1.0 <= fracture_pressure < {1.0 + tolerance:g}",
            "meaning": "The boss is within tolerance of the expected decay curve.",
        },
        {
            "status": "review_recommended",
            "range": f"{1.0 + tolerance:g} <= fracture_pressure < 1.5",
            "meaning": "The boss is lagging enough to review assumptions before another whole-task attempt.",
        },
        {
            "status": "fracture_recommended",
            "range": "1.5 <= fracture_pressure < 2.0",
            "meaning": "The boss is not shrinking fast enough; fracture into smaller sub-bosses is recommended.",
        },
        {
            "status": "hard_fracture_required",
            "range": "fracture_pressure >= 2.0",
            "meaning": "The boss is far behind the decay curve; retrying as one large task should be stopped.",
        },
    ]


def _parameter_definitions() -> list[dict[str, str]]:
    return [
        {"symbol": "B_0", "name": "initial_complexity", "definition": "Initial boss complexity."},
        {"symbol": "B_t", "name": "expected_remaining", "definition": "Expected remaining boss complexity after attempt t."},
        {"symbol": "t", "name": "attempt", "definition": "Current attempt number."},
        {"symbol": "T", "name": "max_attempts", "definition": "Maximum attempt budget."},
        {"symbol": "H", "name": "half_life", "definition": "Half-life in attempts."},
        {"symbol": "k", "name": "aggressiveness", "definition": "Aggressiveness factor where H = T / k."},
        {"symbol": "tolerance", "name": "tolerance", "definition": "Allowed pressure margin above 1.0 before review is recommended."},
    ]


def _validate_parameters(
    *,
    initial_complexity: Any,
    actual_remaining: Any,
    attempt: Any,
    max_attempts: Any,
    aggressiveness: Any,
    tolerance: Any,
) -> tuple[dict[str, float | int], list[str]]:
    blockers: list[str] = []
    initial = _as_float(initial_complexity, "initial_complexity", blockers)
    actual = _as_float(actual_remaining, "actual_remaining", blockers)
    attempt_count = _as_int(attempt, "attempt", blockers)
    max_attempt_count = _as_int(max_attempts, "max_attempts", blockers)
    factor = _as_float(aggressiveness, "aggressiveness", blockers)
    margin = _as_float(tolerance, "tolerance", blockers)

    if initial <= 0:
        blockers.append("initial_complexity must be greater than 0")
    if actual < 0:
        blockers.append("actual_remaining must be greater than or equal to 0")
    if attempt_count < 0:
        blockers.append("attempt must be greater than or equal to 0")
    if max_attempt_count <= 0:
        blockers.append("max_attempts must be greater than 0")
    if max_attempt_count > 0 and attempt_count > max_attempt_count:
        blockers.append("attempt must be less than or equal to max_attempts")
    if factor <= 0:
        blockers.append("aggressiveness must be greater than 0")
    if margin < 0:
        blockers.append("tolerance must be greater than or equal to 0")

    return (
        {
            "initial_complexity": initial,
            "actual_remaining": actual,
            "attempt": attempt_count,
            "max_attempts": max_attempt_count,
            "aggressiveness": factor,
            "tolerance": margin,
        },
        sorted(set(blockers)),
    )


def _schedule(initial_complexity: float, max_attempts: int, half_life: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for attempt in range(max_attempts + 1):
        expected = expected_remaining_complexity(initial_complexity, attempt, half_life)
        rows.append(
            {
                "attempt": attempt,
                "expected_remaining": _round_metric(expected),
                "expected_remaining_rounded": int(round(expected)),
            }
        )
    return rows


def _recommendation_for_status(status: str) -> str:
    return {
        "ahead_of_decay": "Continue within the current boss shape; the work is shrinking faster than expected.",
        "on_track": "Continue within the current boss shape; actual remaining complexity is within tolerance.",
        "review_recommended": "Review estimates, evidence, and blockers before another whole-boss attempt.",
        "fracture_recommended": "Recommend a human-reviewed fracture into smaller sub-bosses before retrying.",
        "hard_fracture_required": "Stop whole-boss retries and require a human-approved fracture plan.",
        "invalid_parameters": "Fix the input parameters before using the fracture model.",
    }.get(status, "Fix the input parameters before using the fracture model.")


def build_boss_half_life_fracture_plan(
    *,
    initial_complexity: Any = DEFAULT_INITIAL_COMPLEXITY,
    actual_remaining: Any = DEFAULT_ACTUAL_REMAINING,
    attempt: Any = DEFAULT_ATTEMPT,
    max_attempts: Any = DEFAULT_MAX_ATTEMPTS,
    aggressiveness: Any = DEFAULT_AGGRESSIVENESS,
    tolerance: Any = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Build the deterministic CMD.N1 Boss Half-Life Fracture report data."""
    params, blockers = _validate_parameters(
        initial_complexity=initial_complexity,
        actual_remaining=actual_remaining,
        attempt=attempt,
        max_attempts=max_attempts,
        aggressiveness=aggressiveness,
        tolerance=tolerance,
    )
    valid = not blockers
    half_life = None
    expected = None
    pressure = None
    schedule: list[dict[str, Any]] = []

    if valid:
        half_life = float(params["max_attempts"]) / float(params["aggressiveness"])
        expected = expected_remaining_complexity(
            float(params["initial_complexity"]),
            int(params["attempt"]),
            half_life,
        )
        pressure = float(params["actual_remaining"]) / expected if expected > 0 else None
        schedule = _schedule(float(params["initial_complexity"]), int(params["max_attempts"]), half_life)

    status = "invalid_parameters" if not valid else classify_fracture_pressure(pressure, float(params["tolerance"]))
    normalized_parameters = {
        "initial_complexity": _round_metric(float(params["initial_complexity"])),
        "actual_remaining": _round_metric(float(params["actual_remaining"])),
        "attempt": int(params["attempt"]),
        "max_attempts": int(params["max_attempts"]),
        "aggressiveness": _round_metric(float(params["aggressiveness"])),
        "half_life": _round_metric(half_life),
        "tolerance": _round_metric(float(params["tolerance"])),
    }

    warnings = [
        "CMD.N1 uses human-provided actual_remaining; it does not measure task complexity automatically.",
        "CMD.N1 recommends fracture status only; it does not create sub-bosses or assign workers.",
    ]
    if status in {"review_recommended", "fracture_recommended", "hard_fracture_required"}:
        warnings.append("actual remaining complexity is lagging the expected half-life curve")

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": BOSS_HALF_LIFE_GUARDRAIL_NOTE,
        "summary": {
            "purpose": "Define deterministic stagnation detection for large Commander bosses.",
            "key_idea": "A hard task should shrink across attempts; if it decays too slowly, fracture is recommended.",
            "report_only": True,
            "decision_status": status,
        },
        "formula": {
            "expected_remaining": FORMULA,
            "half_life": HALF_LIFE_FORMULA,
            "fracture_pressure": "actual_remaining / expected_remaining",
        },
        "parameter_definitions": _parameter_definitions(),
        "default_policy": {
            "max_attempts": DEFAULT_MAX_ATTEMPTS,
            "aggressiveness": _round_metric(DEFAULT_AGGRESSIVENESS),
            "half_life": _round_metric(DEFAULT_MAX_ATTEMPTS / DEFAULT_AGGRESSIVENESS),
            "tolerance": DEFAULT_TOLERANCE,
            "policy_note": "With T=6 and k=2, the expected boss complexity halves every 3 attempts.",
        },
        "parameters": normalized_parameters,
        "example_decay_schedule": schedule,
        "fracture_pressure_thresholds": _thresholds(float(params["tolerance"])),
        "decision": {
            "status": status,
            "expected_remaining": _round_metric(expected),
            "actual_remaining": _round_metric(float(params["actual_remaining"])),
            "fracture_pressure": _round_metric(pressure),
            "recommendation": _recommendation_for_status(status),
        },
        "recommended_sub_boss_fields": list(RECOMMENDED_SUB_BOSS_FIELDS),
        "integration_boundaries": [
            "MIRROR detects drift; CMD.N1 detects stagnation.",
            "CMD.N1 consumes explicit complexity numbers and does not infer them from code, traces, models, or routes.",
            "Future Commander phases may read the decision status only after human approval.",
            "CMD.N1 does not change routing, execution, validation, benchmark, worker, Dream, Replay, or patch behavior.",
        ],
        "guardrails": _guardrails(),
        "allowed_next_steps": list(ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(FORBIDDEN_NEXT_STEPS),
        "recommended_next_phase": {
            "phase_id": "CMD.N2",
            "title": "Boss Fracture Sub-Boss Contract Plan",
            "reason": (
                "Define the report-only sub-boss contract that a human could use "
                "after CMD.N1 recommends fracture, without automatic decomposition "
                "or worker assignment."
            ),
        },
        "warnings": warnings,
        "blockers": blockers,
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_boss_half_life_fracture_markdown(plan: dict[str, Any]) -> str:
    """Render a CMD.N1 Boss Half-Life Fracture Plan as Markdown."""
    params = plan.get("parameters") if isinstance(plan.get("parameters"), dict) else {}
    decision = plan.get("decision") if isinstance(plan.get("decision"), dict) else {}
    default_policy = plan.get("default_policy") if isinstance(plan.get("default_policy"), dict) else {}
    next_phase = plan.get("recommended_next_phase") if isinstance(plan.get("recommended_next_phase"), dict) else {}

    lines: list[str] = [
        "# Boss Half-Life Fracture Plan",
        "",
        f"> {plan.get('guardrail_note', BOSS_HALF_LIFE_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.N1 defines stagnation detection. It runs nothing and changes no routing or execution behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Purpose:** {_md((plan.get('summary') or {}).get('purpose', ''))}",
        f"- **Decision status:** `{_md(decision.get('status', ''))}`",
        f"- **Recommendation:** {_md(decision.get('recommendation', ''))}",
        f"- **Fracture pressure:** {_md(decision.get('fracture_pressure'))}",
        "",
        "## Formula",
        "",
        f"- `{FORMULA}`",
        f"- `{HALF_LIFE_FORMULA}`",
        "- `fracture_pressure = actual_remaining / expected_remaining`",
        "",
        "## Parameter Definitions",
        "",
        "| Symbol | Parameter | Definition |",
        "| --- | --- | --- |",
    ]
    for item in plan.get("parameter_definitions") or []:
        lines.append(
            f"| `{_md(item.get('symbol'))}` | `{_md(item.get('name'))}` | {_md(item.get('definition'))} |"
        )
    lines += [
        "",
        "## Default Policy",
        "",
        f"- **T / max attempts:** {default_policy.get('max_attempts')}",
        f"- **k / aggressiveness:** {default_policy.get('aggressiveness')}",
        f"- **H / half-life:** {default_policy.get('half_life')}",
        f"- **Tolerance:** {default_policy.get('tolerance')}",
        f"- **Policy note:** {_md(default_policy.get('policy_note', ''))}",
        "",
        "## Example Decay Schedule",
        "",
        f"- **Initial complexity:** {params.get('initial_complexity')}",
        f"- **Max attempts:** {params.get('max_attempts')}",
        f"- **Aggressiveness:** {params.get('aggressiveness')}",
        f"- **Half-life:** {params.get('half_life')}",
        "",
        "| Attempt | Expected remaining | Rounded |",
        "| ---: | ---: | ---: |",
    ]
    for row in plan.get("example_decay_schedule") or []:
        lines.append(
            f"| {row.get('attempt')} | {row.get('expected_remaining')} | {row.get('expected_remaining_rounded')} |"
        )
    lines += [
        "",
        "## Fracture Pressure Thresholds",
        "",
        "| Status | Range | Meaning |",
        "| --- | --- | --- |",
    ]
    for row in plan.get("fracture_pressure_thresholds") or []:
        lines.append(f"| `{_md(row.get('status'))}` | `{_md(row.get('range'))}` | {_md(row.get('meaning'))} |")

    lines += [
        "",
        "## Example Boss Fracture Decision",
        "",
        f"- **Actual remaining:** {decision.get('actual_remaining')}",
        f"- **Expected remaining:** {decision.get('expected_remaining')}",
        f"- **Fracture pressure:** {decision.get('fracture_pressure')}",
        f"- **Commander status:** `{_md(decision.get('status'))}`",
        f"- **Recommendation:** {_md(decision.get('recommendation'))}",
        "",
        "## Recommended Sub-Boss Fields",
        "",
    ]
    _render_list(lines, list(plan.get("recommended_sub_boss_fields") or []), code=True)

    lines += ["## Integration Boundaries", ""]
    _render_list(lines, list(plan.get("integration_boundaries") or []))

    lines += ["## Guardrails", ""]
    guardrails = plan.get("guardrails") if isinstance(plan.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines.append("")

    for title, key in (
        ("Allowed Next Steps", "allowed_next_steps"),
        ("Forbidden Next Steps", "forbidden_next_steps"),
        ("Warnings", "warnings"),
        ("Blockers", "blockers"),
    ):
        lines += [f"## {title}", ""]
        _render_list(lines, list(plan.get(key) or []), code="Steps" in title)

    lines += [
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
        "## Boundaries",
        "",
        "- CMD.N1 defines the model and report artifact only.",
        "- CMD.N1 does not actually decompose tasks.",
        "- CMD.N1 does not assign workers.",
        "- CMD.N1 does not call models.",
        "- CMD.N1 does not launch Commander mode.",
        "- CMD.N1 does not affect routing.",
        "- CMD.N1 writes plan artifacts only.",
        "",
    ]
    return "\n".join(lines)


def write_boss_half_life_fracture_plan(
    *,
    output_dir: str | Path,
    initial_complexity: Any = DEFAULT_INITIAL_COMPLEXITY,
    actual_remaining: Any = DEFAULT_ACTUAL_REMAINING,
    attempt: Any = DEFAULT_ATTEMPT,
    max_attempts: Any = DEFAULT_MAX_ATTEMPTS,
    aggressiveness: Any = DEFAULT_AGGRESSIVENESS,
    tolerance: Any = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Build and write the fixed CMD.N1 JSON + Markdown plan artifacts."""
    plan = build_boss_half_life_fracture_plan(
        initial_complexity=initial_complexity,
        actual_remaining=actual_remaining,
        attempt=attempt,
        max_attempts=max_attempts,
        aggressiveness=aggressiveness,
        tolerance=tolerance,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_boss_half_life_fracture_markdown(plan), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "plan": plan}
