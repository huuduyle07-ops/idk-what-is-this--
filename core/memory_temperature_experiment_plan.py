"""Phase 12.14d - Memory Temperature Retrieval Experiment Plan.

Builds a read-only experiment plan/harness describing how memory temperature
(Phase 12.14a classifier, surfaced in 12.14b explainability and recorded in
12.14c evidence) *would* be tested safely before any behavior change. It does
**not** enable memory temperature to affect retrieval or ranking.

The plan defines:
- default-off feature flags (``MEMORY_TEMPERATURE_RETRIEVAL_ENABLED=false``,
  ``MEMORY_TEMPERATURE_TIEBREAK_ONLY=true``);
- first-experiment safety constraints (tie-breaker only, no hard filtering of
  cold memories, frozen/audit-only memory stays excluded);
- the experiment protocol (baseline vs experiment via the existing experiment
  registry, dev suite first, held-out suite only after dev passes);
- the greenlight / needs_review / reject decision policy;
- the metrics to watch (fallback / model-call / token pressure).

This module is **read-only and deterministic**. It performs no model/API calls,
no subprocess, no benchmark execution, and changes no lesson retrieval, CONTROL
prompts, ranking, graph weights, Phantom Limb scoring, patch generation,
validation, benchmark scoring, lesson storage, or DB behavior. It only assembles
a plan record and writes it to ``.agent/experiments/``.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import experiments


SCHEMA_VERSION = 1

EXPERIMENT_SLUG = "memory-temperature-retrieval-plan"

PHASES_COVERED: tuple[str, ...] = ("12.14a", "12.14b", "12.14c", "12.14d")

MEMORY_TEMPERATURE_RETRIEVAL_PLAN_GUARDRAIL = (
    "This phase only writes an experiment plan. It does not change lesson "
    "retrieval, CONTROL prompts, ranking, patch generation, validation, "
    "benchmark scoring, lesson storage, model calls, or DB behavior."
)

# Suggested *future* flag names. They are documented in the plan only; this
# module never reads, sets, or honors them.
FEATURE_FLAGS: tuple[dict[str, str], ...] = (
    {
        "name": "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED",
        "default": "false",
        "note": (
            "Master switch; must be default off. Memory temperature does not "
            "influence retrieval or ranking until this is explicitly enabled "
            "for an experiment run."
        ),
    },
    {
        "name": "MEMORY_TEMPERATURE_TIEBREAK_ONLY",
        "default": "true",
        "note": (
            "In the first experiment, memory temperature may only act as a "
            "tie-breaker between otherwise equally-ranked candidates; it must "
            "not change the primary ranking score."
        ),
    },
)

SAFETY_CONSTRAINTS: tuple[str, ...] = (
    "The feature flag MEMORY_TEMPERATURE_RETRIEVAL_ENABLED must be default off.",
    "In the first experiment, memory temperature may only be used as a "
    "tie-breaker between otherwise equally-ranked candidates.",
    "No hard filtering of cold memories in the first experiment: cold memories "
    "must not be dropped from retrieval, only deprioritized on ties.",
    "Frozen / audit-only memories must remain excluded (audit-only) and never "
    "become retrievable.",
    "Fallback rate, model-call count, and token pressure must be watched for "
    "regressions even when correctness is unchanged.",
)

EXPERIMENT_PROTOCOL: tuple[str, ...] = (
    "Compare a baseline run (flag off) against an experiment run (flag on, "
    "tie-break only) using the existing experiment registry (core.experiments).",
    "Run the dev suite first; only proceed if the dev suite passes with no "
    "correctness regression.",
    "Run the held-out suite only after the dev suite passes, to avoid "
    "overfitting the held-out split.",
    "Greenlight requires no correctness regression on the same suite size; "
    "any correctness regression is an automatic reject.",
)

WATCH_METRICS: tuple[str, ...] = (
    "fallback_count",
    "model_calls",
    "total_tokens",
    "avg_duration_sec",
    "total_estimated_cost_usd",
)

# Decision policy (mirrors the experiment decision semantics used elsewhere).
GREENLIGHT_CRITERIA: tuple[str, ...] = (
    "Same suite size (total unchanged).",
    "Passed count not decreased.",
    "Failed count not increased.",
    "Flaky count not increased.",
    "Fallback / model_calls / tokens not significantly worse.",
)

NEEDS_REVIEW_CRITERIA: tuple[str, ...] = (
    "Suite size changed (a partial run vs a full run is not a comparable "
    "before/after pair).",
    "Speed / cost / fallback pressure increased.",
    "Correctness unknown or unmeasured.",
)

REJECT_CRITERIA: tuple[str, ...] = (
    "Same-size passed count decreases.",
    "Failed count increases.",
    "Flaky count increases.",
    "A frozen / audit-only memory becomes retrievable.",
)


def _now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return now


def _experiment_id(now: datetime) -> str:
    stamp = now.strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{EXPERIMENT_SLUG}"


# --------------------------------------------------------------------------
# Plan assembly
# --------------------------------------------------------------------------

def build_experiment_plan(*, now: datetime | None = None) -> dict[str, Any]:
    """Assemble the read-only memory-temperature retrieval experiment plan."""
    moment = _now(now)
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_kind": "memory_temperature_retrieval_experiment_plan",
        "experiment_id": _experiment_id(moment),
        "title": "Memory Temperature Retrieval Experiment Plan (Phase 12.14d)",
        "created_at": moment.isoformat(timespec="seconds"),
        "phases_covered": list(PHASES_COVERED),
        "status": "planned",
        "behavior_change_enabled": False,
        "objective": (
            "Define how memory temperature would be tested safely as a "
            "retrieval/ranking signal before any behavior change. Memory "
            "temperature stays explain-only until an experiment greenlights it."
        ),
        "feature_flags": [dict(flag) for flag in FEATURE_FLAGS],
        "safety_constraints": list(SAFETY_CONSTRAINTS),
        "experiment_protocol": list(EXPERIMENT_PROTOCOL),
        "watch_metrics": list(WATCH_METRICS),
        "decision_policy": {
            "greenlight": list(GREENLIGHT_CRITERIA),
            "needs_review": list(NEEDS_REVIEW_CRITERIA),
            "reject": list(REJECT_CRITERIA),
        },
        "guardrail": MEMORY_TEMPERATURE_RETRIEVAL_PLAN_GUARDRAIL,
    }


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------

def _md_cell(value: Any) -> str:
    text = str(value if value is not None and value != "" else "unknown")
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_plan_markdown(record: dict[str, Any]) -> str:
    lines = [
        f"# {_md_cell(record.get('title'))}",
        "",
        "## Summary",
        "",
        f"- Experiment ID: `{_md_cell(record.get('experiment_id'))}`",
        f"- Kind: `{_md_cell(record.get('plan_kind'))}`",
        f"- Phases covered: {_md_cell(', '.join(record.get('phases_covered') or []))}",
        f"- Created at: {_md_cell(record.get('created_at'))}",
        f"- Status: `{_md_cell(record.get('status'))}`",
        f"- Behavior change enabled: "
        f"`{str(bool(record.get('behavior_change_enabled'))).lower()}`",
        f"- Objective: {_md_cell(record.get('objective'))}",
        "",
        "## Feature flags (future, default off)",
        "",
        "| flag | default | note |",
        "|---|---|---|",
    ]
    for flag in record.get("feature_flags") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{_md_cell(flag.get('name'))}`",
                    f"`{_md_cell(flag.get('default'))}`",
                    _md_cell(flag.get("note")),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append(
        "> The master flag `MEMORY_TEMPERATURE_RETRIEVAL_ENABLED` must be "
        "default off. Memory temperature stays explain-only until an "
        "experiment greenlights it."
    )
    lines.append("")

    lines.append("## Safety constraints")
    lines.append("")
    for item in record.get("safety_constraints") or []:
        lines.append(f"- {_md_cell(item)}")
    lines.append("")

    lines.append("## Experiment protocol")
    lines.append("")
    for item in record.get("experiment_protocol") or []:
        lines.append(f"- {_md_cell(item)}")
    lines.append("")

    lines.append("## Metrics to watch")
    lines.append("")
    for item in record.get("watch_metrics") or []:
        lines.append(f"- `{_md_cell(item)}`")
    lines.append("")

    policy = record.get("decision_policy") or {}
    lines.append("## Decision policy")
    lines.append("")
    for key, heading in (
        ("greenlight", "greenlight"),
        ("needs_review", "needs_review"),
        ("reject", "reject"),
    ):
        lines.append(f"### {heading}")
        lines.append("")
        for item in policy.get(key) or []:
            lines.append(f"- {_md_cell(item)}")
        lines.append("")

    lines.append("## Guardrail")
    lines.append("")
    lines.append(f"> {record.get('guardrail', '')}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Disk writes (JSON + Markdown)
# --------------------------------------------------------------------------

def write_plan(
    record: dict[str, Any],
    *,
    experiments_root: str | Path | None = None,
) -> dict[str, str]:
    """Write the plan to ``.agent/experiments/<id>.json`` + ``.md`` safely."""
    root = (
        Path(experiments_root)
        if experiments_root is not None
        else experiments.default_experiments_root()
    ).resolve()
    experiment_id = record["experiment_id"]
    json_path = experiments.resolve_experiment_path(
        experiment_id,
        experiments_root=root,
    )
    md_path = json_path.with_suffix(".md")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(render_plan_markdown(record), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "experiment_id": experiment_id,
    }


def create_memory_temperature_retrieval_plan(
    *,
    experiments_root: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build and write the experiment plan; return paths + the record."""
    record = build_experiment_plan(now=now)
    out = write_plan(record, experiments_root=experiments_root)
    return {
        "record": record,
        "json_path": out["json_path"],
        "md_path": out["md_path"],
        "experiment_id": out["experiment_id"],
    }
