"""CMD.N2 - Manual Boss Fracture Report (report-only).

Applies the CMD.N1 Boss Half-Life Fracture model to one manually described boss
and optional manually supplied sub-boss candidates. CMD.N2 writes deterministic
report artifacts only. It does not call models, automatically decompose tasks,
assign workers, launch workers, launch Commander mode, affect routing, apply
patches, run validation, run benchmarks, invoke MCP tools, execute Dream actions,
apply Replay janitor actions, use Docker/subprocess, contact networks, write
databases, or change runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.boss_half_life_fracture_plan import (
    DEFAULT_AGGRESSIVENESS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TOLERANCE,
    GUARDRAIL_FALSE_FLAGS as CMD_N1_GUARDRAIL_FALSE_FLAGS,
    RECOMMENDED_SUB_BOSS_FIELDS,
    build_boss_half_life_fracture_plan,
)


REPORT_KIND = "manual_boss_fracture_report"
JSON_NAME = "manual_boss_fracture_report.json"
MD_NAME = "manual_boss_fracture_report.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "commander" / "manual_boss_fracture_report"
INVALID_BOSS_ID_DIR = "invalid_boss_id"

REQUIRED_SUB_BOSS_FIELDS: tuple[str, ...] = RECOMMENDED_SUB_BOSS_FIELDS

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = tuple(
    dict.fromkeys(
        list(CMD_N1_GUARDRAIL_FALSE_FLAGS)
        + [
            "validation_run_performed",
            "automatic_fracture_tree_generated",
        ]
    )
)

MANUAL_BOSS_FRACTURE_GUARDRAIL_NOTE = (
    "Manual Boss Fracture Report is report-only: it applies the CMD.N1 "
    "Boss Half-Life Fracture model to a manually described boss and optional "
    "manual sub-boss candidates. It writes report artifacts only and does not "
    "call models, automatically decompose tasks, assign workers, launch workers, "
    "launch Commander mode, affect routing, apply patches, run validation, run "
    "benchmarks, invoke MCP tools, execute Dream actions, apply Replay janitor "
    "actions, use Docker/subprocess, contact networks, write databases, change "
    "auth policy, or change route behavior."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "CMD.N3",
    "title": "Commander Fracture Tree Schema / Registry",
    "alternative": "Manual Commander Preflight Report",
    "reason": (
        "Promote the manually reviewed fracture tree into a stable schema and "
        "registry before any Commander runtime, routing, worker, or automatic "
        "decomposition behavior exists."
    ),
}

FRACTURE_STATUSES = {"fracture_recommended", "hard_fracture_required"}


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _round_metric(value: float | None, places: int = 6) -> float | int | None:
    if value is None:
        return None
    rounded = round(float(value), places)
    if float(rounded).is_integer():
        return int(rounded)
    return rounded


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _as_positive_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or abs(number) == float("inf") or number <= 0:
        return None
    return number


def _safe_boss_id(value: Any) -> tuple[str, list[str]]:
    boss_id = str(value or "").strip()
    blockers: list[str] = []
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if not boss_id:
        blockers.append("boss_id must be a non-empty path-safe identifier")
    if boss_id in {".", ".."} or ".." in boss_id:
        blockers.append("boss_id must not contain path traversal segments")
    if "/" in boss_id or "\\" in boss_id:
        blockers.append("boss_id must not contain path separators")
    if boss_id.startswith("."):
        blockers.append("boss_id must not start with a dot")
    if any(ch not in allowed for ch in boss_id):
        blockers.append("boss_id may contain only letters, numbers, dot, dash, and underscore")
    return boss_id, sorted(set(blockers))


def read_sub_boss_candidates(path: str | Path | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Read a manual sub-boss JSON file without generating or inferring entries."""
    if path is None or str(path).strip() == "":
        return [], []
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        return [], [f"sub_boss_file could not be read: {exc}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [], [f"sub_boss_file must contain valid JSON: {exc.msg}"]
    if not isinstance(data, list):
        return [], ["sub_boss_file must contain a JSON list of manual sub-boss candidates"]
    blockers: list[str] = []
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if isinstance(item, dict):
            candidates.append(dict(item))
        else:
            blockers.append(f"sub_boss_file item #{index} must be a JSON object")
    return candidates, blockers


def _validate_sub_bosses(
    sub_bosses: list[dict[str, Any]],
    *,
    actual_remaining: float | int | None,
    tolerance: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[str], list[str]]:
    candidates: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []
    complexity_sum = 0.0

    for index, raw in enumerate(sub_bosses):
        if not isinstance(raw, dict):
            blockers.append(f"sub_boss #{index} must be a mapping")
            continue
        candidate = dict(raw)
        label = str(candidate.get("sub_boss_id") or f"#{index}")
        missing_fields = [field for field in REQUIRED_SUB_BOSS_FIELDS if field not in candidate or _is_blank(candidate.get(field))]
        if missing_fields:
            missing.append(
                {
                    "index": index,
                    "sub_boss_id": label,
                    "missing_fields": missing_fields,
                }
            )

        expected = _as_positive_float(candidate.get("expected_complexity"))
        if expected is None:
            warnings.append(f"sub_boss {label} expected_complexity must be positive")
        else:
            complexity_sum += expected

        if _is_blank(candidate.get("assigned_role")):
            warnings.append(f"sub_boss {label} assigned_role is missing")
        if _is_blank(candidate.get("rollback_boundary")):
            warnings.append(f"sub_boss {label} rollback_boundary is missing")
        evidence = candidate.get("evidence_required")
        if not isinstance(evidence, list) or len(evidence) == 0:
            warnings.append(f"sub_boss {label} evidence_required is empty")
        candidates.append(candidate)

    ratio = None
    comparison = "not_applicable"
    actual = float(actual_remaining) if isinstance(actual_remaining, (int, float)) else None
    if candidates and actual is not None and actual > 0:
        ratio = complexity_sum / actual
        lower = max(0.0, 1.0 - tolerance)
        upper = 1.0 + tolerance
        if ratio < lower:
            comparison = "much_smaller_than_actual_remaining"
            warnings.append(
                "sum of sub-boss expected_complexity is much smaller than actual_remaining"
            )
        elif ratio > upper:
            comparison = "much_larger_than_actual_remaining"
            warnings.append(
                "sum of sub-boss expected_complexity is much larger than actual_remaining"
            )
        else:
            comparison = "within_tolerance_of_actual_remaining"
    elif candidates:
        comparison = "actual_remaining_unavailable"

    summary = {
        "sub_boss_count": len(candidates),
        "expected_complexity_sum": _round_metric(complexity_sum),
        "actual_remaining": _round_metric(actual),
        "ratio_to_actual_remaining": _round_metric(ratio),
        "comparison": comparison,
        "tolerance": _round_metric(tolerance),
    }
    return candidates, missing, summary, warnings, blockers


def _fracture_tree(
    *,
    boss_id: str,
    title: str,
    decision_status: str,
    actual_remaining: float | int | None,
    sub_bosses: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "tree_kind": "manual_fracture_tree",
        "generated_by_ai": False,
        "root": {
            "boss_id": boss_id,
            "title": title,
            "actual_remaining": _round_metric(float(actual_remaining)) if isinstance(actual_remaining, (int, float)) else None,
            "decision_status": decision_status,
        },
        "children": [
            {
                "sub_boss_id": candidate.get("sub_boss_id"),
                "parent_boss_id": candidate.get("parent_boss_id") or boss_id,
                "title": candidate.get("title"),
                "expected_complexity": candidate.get("expected_complexity"),
                "dependencies": list(candidate.get("dependencies") or [])
                if isinstance(candidate.get("dependencies"), list)
                else [],
                "manual_candidate": True,
            }
            for candidate in sub_bosses
        ],
    }


def _recommendation_for_status(status: str) -> str:
    return {
        "ahead_of_decay": "Continue monitoring the current boss shape; the manual estimate is ahead of decay.",
        "on_track": "Continue with the current boss shape; actual remaining complexity is within tolerance.",
        "review_recommended": "Review the manual boss estimate and candidate fracture fields before another whole-boss attempt.",
        "fracture_recommended": "Use the supplied manual candidates to review a fracture tree before retrying the boss.",
        "hard_fracture_required": "Stop whole-boss retries until a human-approved fracture tree exists.",
        "invalid_parameters": "Fix boss parameters, boss_id, or manual sub-boss input before using the report.",
    }.get(status, "Fix boss parameters, boss_id, or manual sub-boss input before using the report.")


def build_manual_boss_fracture_report(
    *,
    boss_id: Any,
    title: Any,
    description: Any,
    initial_complexity: Any,
    actual_remaining: Any,
    attempt: Any,
    max_attempts: Any = DEFAULT_MAX_ATTEMPTS,
    aggressiveness: Any = DEFAULT_AGGRESSIVENESS,
    tolerance: Any = DEFAULT_TOLERANCE,
    sub_bosses: list[dict[str, Any]] | None = None,
    sub_boss_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build the deterministic CMD.N2 manual fracture report data."""
    safe_id, boss_id_blockers = _safe_boss_id(boss_id)
    n1 = build_boss_half_life_fracture_plan(
        initial_complexity=initial_complexity,
        actual_remaining=actual_remaining,
        attempt=attempt,
        max_attempts=max_attempts,
        aggressiveness=aggressiveness,
        tolerance=tolerance,
    )
    n1_decision = n1.get("decision") if isinstance(n1.get("decision"), dict) else {}
    n1_params = n1.get("parameters") if isinstance(n1.get("parameters"), dict) else {}

    blockers = list(n1.get("blockers") or []) + list(boss_id_blockers) + list(sub_boss_blockers or [])
    numeric_tolerance = n1_params.get("tolerance")
    if not isinstance(numeric_tolerance, (int, float)):
        numeric_tolerance = DEFAULT_TOLERANCE

    raw_sub_bosses = list(sub_bosses or [])
    candidates, missing, complexity_summary, sub_warnings, sub_blockers = _validate_sub_bosses(
        raw_sub_bosses,
        actual_remaining=n1_decision.get("actual_remaining"),
        tolerance=float(numeric_tolerance),
    )
    blockers += sub_blockers

    status = str(n1_decision.get("status") or "invalid_parameters")
    if blockers:
        status = "invalid_parameters"

    warnings = [
        "CMD.N2 consumes manual boss and sub-boss input only; it does not generate decomposition candidates.",
        "CMD.N2 applies CMD.N1 math and reports a proposed fracture tree only.",
    ]
    warnings += list(n1.get("warnings") or [])
    warnings += sub_warnings
    if status in FRACTURE_STATUSES and not candidates:
        warnings.append(
            "no manual sub-boss candidates were provided even though the Commander decision recommends fracture"
        )

    expected_remaining = n1_decision.get("expected_remaining")
    actual_value = n1_decision.get("actual_remaining")
    pressure = n1_decision.get("fracture_pressure")
    display_boss_id = safe_id if not boss_id_blockers else str(boss_id or "")

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": MANUAL_BOSS_FRACTURE_GUARDRAIL_NOTE,
        "summary": {
            "purpose": "Apply CMD.N1 stagnation detection to one manually described boss.",
            "report_only": True,
            "manual_input_only": True,
            "decision_status": status,
            "sub_boss_count": len(candidates),
        },
        "boss_input": {
            "boss_id": display_boss_id,
            "title": str(title or ""),
            "description": str(description or ""),
        },
        "half_life_parameters": {
            "initial_complexity": n1_params.get("initial_complexity"),
            "actual_remaining": actual_value,
            "attempt": n1_params.get("attempt"),
            "max_attempts": n1_params.get("max_attempts"),
            "aggressiveness": n1_params.get("aggressiveness"),
            "half_life": n1_params.get("half_life"),
            "tolerance": n1_params.get("tolerance"),
        },
        "expected_remaining_complexity": expected_remaining,
        "actual_remaining_complexity": actual_value,
        "fracture_pressure": pressure,
        "commander_decision": {
            "status": status,
            "source_status": n1_decision.get("status"),
            "recommendation": _recommendation_for_status(status),
        },
        "manual_sub_boss_candidates": candidates,
        "sub_boss_complexity_summary": complexity_summary,
        "fracture_tree": _fracture_tree(
            boss_id=display_boss_id,
            title=str(title or ""),
            decision_status=status,
            actual_remaining=actual_value,
            sub_bosses=candidates,
        ),
        "missing_sub_boss_fields": missing,
        "warnings": sorted(dict.fromkeys(warnings)),
        "blockers": sorted(dict.fromkeys(blockers)),
        "guardrails": _guardrails(),
        "required_sub_boss_fields": list(REQUIRED_SUB_BOSS_FIELDS),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "integration_boundaries": [
            "CMD.N1 defines the half-life model; CMD.N2 applies it to one manual boss input.",
            "Sub-boss candidates must come from a human-authored JSON file or direct caller input.",
            "CMD.N2 may propose a fracture tree in the report, but it does not create tasks or assign workers.",
            "Future phases may define a schema registry only after human review.",
        ],
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_manual_boss_fracture_markdown(report: dict[str, Any]) -> str:
    """Render a CMD.N2 Manual Boss Fracture Report as Markdown."""
    boss = report.get("boss_input") if isinstance(report.get("boss_input"), dict) else {}
    params = report.get("half_life_parameters") if isinstance(report.get("half_life_parameters"), dict) else {}
    decision = report.get("commander_decision") if isinstance(report.get("commander_decision"), dict) else {}
    tree = report.get("fracture_tree") if isinstance(report.get("fracture_tree"), dict) else {}
    root = tree.get("root") if isinstance(tree.get("root"), dict) else {}
    complexity = report.get("sub_boss_complexity_summary") if isinstance(report.get("sub_boss_complexity_summary"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}

    lines: list[str] = [
        "# Manual Boss Fracture Report",
        "",
        f"> {report.get('guardrail_note', MANUAL_BOSS_FRACTURE_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.N2 applies CMD.N1 math to manual inputs. It runs nothing and changes no routing or execution behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Decision status:** `{_md(decision.get('status', ''))}`",
        f"- **Recommendation:** {_md(decision.get('recommendation', ''))}",
        f"- **Manual sub-boss count:** {(report.get('summary') or {}).get('sub_boss_count', 0)}",
        "",
        "## Boss Input",
        "",
        f"- **Boss id:** `{_md(boss.get('boss_id', ''))}`",
        f"- **Title:** {_md(boss.get('title', ''))}",
        f"- **Description:** {_md(boss.get('description', ''))}",
        "",
        "## Half-Life Parameters",
        "",
        f"- **Initial complexity:** {params.get('initial_complexity')}",
        f"- **Attempt:** {params.get('attempt')}",
        f"- **Max attempts:** {params.get('max_attempts')}",
        f"- **Aggressiveness:** {params.get('aggressiveness')}",
        f"- **Half-life:** {params.get('half_life')}",
        f"- **Tolerance:** {params.get('tolerance')}",
        "",
        "## Expected Remaining Complexity",
        "",
        f"- `{_md(report.get('expected_remaining_complexity'))}`",
        "",
        "## Actual Remaining Complexity",
        "",
        f"- `{_md(report.get('actual_remaining_complexity'))}`",
        "",
        "## Fracture Pressure",
        "",
        f"- `{_md(report.get('fracture_pressure'))}`",
        "",
        "## Commander Decision",
        "",
        f"- **Status:** `{_md(decision.get('status', ''))}`",
        f"- **Source CMD.N1 status:** `{_md(decision.get('source_status', ''))}`",
        f"- **Recommendation:** {_md(decision.get('recommendation', ''))}",
        "",
        "## Manual Sub-Boss Candidates",
        "",
    ]

    candidates = report.get("manual_sub_boss_candidates") or []
    if candidates:
        lines += [
            "| Sub-boss | Parent | Title | Expected complexity | Assigned role | Rollback boundary |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
        for candidate in candidates:
            lines.append(
                "| {sid} | {parent} | {title} | {complexity} | {role} | {rollback} |".format(
                    sid=_md(candidate.get("sub_boss_id", "")),
                    parent=_md(candidate.get("parent_boss_id", "")),
                    title=_md(candidate.get("title", "")),
                    complexity=_md(candidate.get("expected_complexity", "")),
                    role=_md(candidate.get("assigned_role", "")),
                    rollback=_md(candidate.get("rollback_boundary", "")),
                )
            )
    else:
        lines.append("_None provided._")
    lines += [
        "",
        "## Fracture Tree",
        "",
        f"- **Root:** `{_md(root.get('boss_id', ''))}` - {_md(root.get('title', ''))}",
        f"- **Decision:** `{_md(root.get('decision_status', ''))}`",
        f"- **Generated by AI:** `{str(bool(tree.get('generated_by_ai'))).lower()}`",
        "",
    ]
    children = tree.get("children") if isinstance(tree.get("children"), list) else []
    if children:
        for child in children:
            lines.append(
                f"- `{_md(child.get('sub_boss_id', ''))}` under `{_md(child.get('parent_boss_id', ''))}`: "
                f"{_md(child.get('title', ''))} ({_md(child.get('expected_complexity'))})"
            )
    else:
        lines.append("_No child nodes because no manual candidates were supplied._")
    lines += [
        "",
        "## Missing Sub-Boss Fields",
        "",
    ]
    missing = report.get("missing_sub_boss_fields") or []
    if missing:
        for item in missing:
            fields = ", ".join(str(field) for field in item.get("missing_fields") or [])
            lines.append(f"- `{_md(item.get('sub_boss_id', ''))}`: {_md(fields)}")
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Sub-Boss Complexity Comparison",
        "",
        f"- **Expected complexity sum:** {complexity.get('expected_complexity_sum')}",
        f"- **Actual remaining:** {complexity.get('actual_remaining')}",
        f"- **Ratio:** {complexity.get('ratio_to_actual_remaining')}",
        f"- **Comparison:** `{_md(complexity.get('comparison'))}`",
        "",
        "## Warnings",
        "",
    ]
    _render_list(lines, list(report.get("warnings") or []))

    lines += ["## Blockers", ""]
    _render_list(lines, list(report.get("blockers") or []))

    lines += ["## Guardrails", ""]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines += [
        "",
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Alternative:** {_md(next_phase.get('alternative', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
        "## Integration Boundaries",
        "",
    ]
    _render_list(lines, list(report.get("integration_boundaries") or []))

    lines += [
        "## Boundaries",
        "",
        "- CMD.N2 does not call models.",
        "- CMD.N2 does not automatically decompose tasks.",
        "- CMD.N2 does not assign workers.",
        "- CMD.N2 does not launch workers.",
        "- CMD.N2 does not route tasks.",
        "- CMD.N2 does not apply patches.",
        "- CMD.N2 does not run validation or benchmarks.",
        "- CMD.N2 writes report artifacts only.",
        "",
    ]
    return "\n".join(lines)


def write_manual_boss_fracture_report(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    boss_id: Any,
    title: Any,
    description: Any,
    initial_complexity: Any,
    actual_remaining: Any,
    attempt: Any,
    max_attempts: Any = DEFAULT_MAX_ATTEMPTS,
    aggressiveness: Any = DEFAULT_AGGRESSIVENESS,
    tolerance: Any = DEFAULT_TOLERANCE,
    sub_bosses: list[dict[str, Any]] | None = None,
    sub_boss_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write the CMD.N2 JSON + Markdown report artifacts."""
    safe_id, boss_id_blockers = _safe_boss_id(boss_id)
    report = build_manual_boss_fracture_report(
        boss_id=boss_id,
        title=title,
        description=description,
        initial_complexity=initial_complexity,
        actual_remaining=actual_remaining,
        attempt=attempt,
        max_attempts=max_attempts,
        aggressiveness=aggressiveness,
        tolerance=tolerance,
        sub_bosses=sub_bosses,
        sub_boss_blockers=sub_boss_blockers,
    )
    target_id = safe_id if not boss_id_blockers else INVALID_BOSS_ID_DIR
    out_dir = Path(output_dir) / target_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_manual_boss_fracture_markdown(report), encoding="utf-8")
    return {
        "ok": not bool(report.get("blockers")),
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
