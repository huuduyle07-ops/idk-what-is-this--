"""Phase 12.14c - Memory Temperature Dogfood Experiment Record.

Builds a read-only experiment/evidence artifact for the cooling-brain /
memory-temperature work shipped in Phase 12.14a (core classifier) and 12.14b
(UI/report visibility in the Related Notes / explainability output). It:

- reuses the Phase 12 experiment/report infrastructure (``core.experiments``)
  and the benchmark before/after comparison from ``core.explainability_dogfood``;
- references the memory-temperature artifacts (the core classifier module, the
  UI/report visibility in ``web/graph_evidence.py`` + the explainability view
  route, and the presentation pack file
  ``08_memory_temperature_explainability.md``);
- records a *behavior-focused* decision: memory temperature core added, memory
  temperature UI/report visibility added, full pytest 1329 passed, benchmark
  ``--check`` 32/0, behavior unchanged, and retrieval/ranking influence not
  enabled.

This module is **read-only / explain-only and deterministic**. It performs no
model/API calls, no subprocess, no benchmark execution, and changes no ranking,
patching, validation, benchmark scoring, retrieval, or UI behavior. It only
reads existing benchmark reports and checks whether memory-temperature artifacts
are present on disk.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import experiments
from core.explainability_dogfood import build_benchmark_comparison


PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_VERSION = 1

EXPERIMENT_SLUG = "memory-temperature-dogfood"

MEMORY_TEMPERATURE_PHASES: tuple[str, ...] = ("12.14a", "12.14b")

MEMORY_TEMPERATURE_DOGFOOD_GUARDRAIL = (
    "Memory temperature dogfood is an explain-only evidence record. It does not "
    "run models, run benchmarks, or change lesson retrieval, CONTROL prompts, "
    "ranking, graph weights, Phantom Limb scoring, patch generation, validation, "
    "benchmark scoring, or storage behavior. It only reads existing benchmark "
    "reports and checks whether memory-temperature artifacts are present on disk."
)

# Behavior-fact defaults, taken from the Phase 12.14c spec.
DEFAULT_BENCHMARK_CHECK = "32/0"
DEFAULT_PYTEST_PASSED = 1329


def _repo_root(repo_path: str | Path | None) -> Path:
    if not repo_path:
        return PROJECT_ROOT
    return Path(repo_path).resolve()


def _now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return now


def _experiment_id(now: datetime) -> str:
    stamp = now.strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{EXPERIMENT_SLUG}"


# --------------------------------------------------------------------------
# Memory-temperature artifact references
# --------------------------------------------------------------------------

def _artifact_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "Memory temperature core classifier",
            "kind": "core_module",
            "phase": "12.14a",
            "reference": (
                "core/memory_temperature.py::classify_memory_temperature "
                "(exponential cooling, explain-only)"
            ),
            "source_path": "core/memory_temperature.py",
        },
        {
            "name": "Memory temperature UI / report visibility",
            "kind": "report_section",
            "phase": "12.14b",
            "reference": (
                "web/graph_evidence.py::format_memory_temperature_section "
                "(## Memory Temperature)"
            ),
            "source_path": "web/graph_evidence.py",
            "view_route": "/graph/explainability/view",
        },
        {
            "name": (
                "Presentation evidence pack file "
                "08_memory_temperature_explainability.md"
            ),
            "kind": "pack_file",
            "phase": "12.14c",
            "reference": (
                ".agent/presentation_evidence/"
                "08_memory_temperature_explainability.md"
            ),
            "source_path": (
                ".agent/presentation_evidence/"
                "08_memory_temperature_explainability.md"
            ),
            "generator": "scripts/build_presentation_evidence_pack.py",
        },
    ]


def build_memory_temperature_artifacts(
    *,
    repo_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return the memory-temperature artifact references with existence flags."""
    root = _repo_root(repo_path)
    artifacts: list[dict[str, Any]] = []
    for spec in _artifact_specs():
        entry = dict(spec)
        source_rel = entry.get("source_path")
        if source_rel:
            entry["exists"] = (root / source_rel).exists()
        else:
            entry["exists"] = None
        artifacts.append(entry)
    return artifacts


# --------------------------------------------------------------------------
# Behavior-focused decision
# --------------------------------------------------------------------------

def _behavior_decision(
    *,
    asserted_correctness_unchanged: bool,
    observed_correctness_unchanged: bool | None,
    benchmark_check: str,
    pytest_passed: int,
) -> dict[str, Any]:
    # Observed evidence overrides the asserted default when reports exist.
    if observed_correctness_unchanged is None:
        effective = asserted_correctness_unchanged
        correctness_basis = "asserted"
    else:
        effective = observed_correctness_unchanged
        correctness_basis = "observed"

    reasons: list[str] = []
    reasons.append("Memory temperature core added (Phase 12.14a classifier).")
    reasons.append(
        "Memory temperature UI/report visibility added (Phase 12.14b, "
        "## Memory Temperature section)."
    )
    if effective:
        reasons.append(
            "Behavior unchanged (read-only explain layer adds no behavior "
            "change)."
        )
    else:
        reasons.append(
            "Observed benchmark correctness changed between the before/after "
            "reports; human review required."
        )
    reasons.append("Retrieval / ranking influence not enabled (explain-only).")
    reasons.append(f"Benchmark --check: {benchmark_check}.")
    reasons.append(f"Full pytest suite: {pytest_passed} passed.")

    status = (
        "behavior_unchanged_memory_temperature_added"
        if effective
        else "needs_review_correctness_changed"
    )
    return {
        "status": status,
        "correctness_unchanged": bool(effective),
        "correctness_basis": correctness_basis,
        "benchmark_check": benchmark_check,
        "pytest_passed": pytest_passed,
        "memory_temperature_core_added": True,
        "memory_temperature_visibility_added": True,
        "behavior_unchanged": bool(effective),
        "retrieval_ranking_influence_enabled": False,
        "human_review_required": not effective,
        "reasons": reasons,
    }


# --------------------------------------------------------------------------
# Record assembly
# --------------------------------------------------------------------------

def build_dogfood_record(
    *,
    repo_path: str | Path | None = None,
    benchmark_root: str | Path | None = None,
    min_total: int = 5,
    correctness_unchanged: bool = True,
    benchmark_check: str = DEFAULT_BENCHMARK_CHECK,
    pytest_passed: int = DEFAULT_PYTEST_PASSED,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Assemble the full memory-temperature dogfood record (no disk writes)."""
    moment = _now(now)
    comparison = build_benchmark_comparison(
        benchmark_root=benchmark_root,
        min_total=min_total,
    )
    artifacts = build_memory_temperature_artifacts(repo_path=repo_path)
    decision = _behavior_decision(
        asserted_correctness_unchanged=bool(correctness_unchanged),
        observed_correctness_unchanged=comparison.get("correctness_unchanged"),
        benchmark_check=benchmark_check,
        pytest_passed=pytest_passed,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_kind": "memory_temperature_dogfood",
        "experiment_id": _experiment_id(moment),
        "title": "Memory Temperature Dogfood (Phase 12.14a-12.14b)",
        "hypothesis": (
            "The memory-temperature work adds a read-only cooling classifier "
            "(Phase 12.14a) and explain-only UI/report visibility (Phase 12.14b) "
            "without changing lesson retrieval, ranking, graph weights, Phantom "
            "Limb scoring, patch generation, validation, benchmark scoring, or "
            "storage behavior; retrieval/ranking influence is not enabled."
        ),
        "phases_covered": list(MEMORY_TEMPERATURE_PHASES),
        "created_at": moment.isoformat(timespec="seconds"),
        "benchmark_comparison": comparison,
        "memory_temperature_artifacts": artifacts,
        "behavior_decision": decision,
        "guardrail": MEMORY_TEMPERATURE_DOGFOOD_GUARDRAIL,
    }


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------

def _md_cell(value: Any) -> str:
    text = str(value if value is not None and value != "" else "unknown")
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _format_number(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _format_delta(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "unknown"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_format_number(value)}"


def _render_comparison_section(comparison: dict[str, Any]) -> list[str]:
    lines = ["## Benchmark before/after", ""]
    if not comparison.get("available"):
        lines.append(f"_{_md_cell(comparison.get('note'))}_")
        lines.append("")
        return lines

    unchanged = comparison.get("correctness_unchanged")
    unchanged_display = "inconclusive" if unchanged is None else str(bool(unchanged)).lower()
    lines += [
        f"- Baseline report (before): `{_md_cell(comparison.get('baseline_report'))}`",
        f"- Variant report (after): `{_md_cell(comparison.get('variant_report'))}`",
        f"- Correctness unchanged: `{unchanged_display}`",
    ]
    if comparison.get("correctness_note"):
        lines.append(f"- Note: {_md_cell(comparison.get('correctness_note'))}")
    lines += [
        "",
        "| metric | baseline | variant | delta | status |",
        "|---|---:|---:|---:|---|",
    ]
    metrics = comparison.get("metrics") or {}
    for name in ("total", "passed", "failed", "flaky"):
        entry = metrics.get(name) or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(name),
                    _format_number(entry.get("baseline")),
                    _format_number(entry.get("variant")),
                    _format_delta(entry.get("delta")),
                    _md_cell(entry.get("status")),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _render_artifacts_section(artifacts: list[dict[str, Any]]) -> list[str]:
    lines = ["## Memory temperature artifacts referenced", ""]
    for art in artifacts:
        exists = art.get("exists")
        if exists is True:
            mark = "present"
        elif exists is False:
            mark = "not generated yet"
        else:
            mark = "n/a"
        lines.append(f"### {_md_cell(art.get('name'))}")
        lines.append(f"- Phase: `{_md_cell(art.get('phase'))}`")
        lines.append(f"- Kind: `{_md_cell(art.get('kind'))}`")
        lines.append(f"- Reference: {_md_cell(art.get('reference'))}")
        if art.get("view_route"):
            lines.append(f"- View route: `{_md_cell(art.get('view_route'))}`")
        if art.get("generator"):
            lines.append(f"- Generator: `{_md_cell(art.get('generator'))}`")
        lines.append(f"- Status: {mark}")
        lines.append("")
    return lines


def render_dogfood_markdown(record: dict[str, Any]) -> str:
    decision = record.get("behavior_decision") or {}
    lines = [
        f"# {_md_cell(record.get('title'))}",
        "",
        "## Summary",
        "",
        f"- Experiment ID: `{_md_cell(record.get('experiment_id'))}`",
        f"- Kind: `{_md_cell(record.get('experiment_kind'))}`",
        f"- Phases covered: {_md_cell(', '.join(record.get('phases_covered') or []))}",
        f"- Created at: {_md_cell(record.get('created_at'))}",
        f"- Hypothesis: {_md_cell(record.get('hypothesis'))}",
        "",
        "## Decision (behavior-focused)",
        "",
        f"- Status: `{_md_cell(decision.get('status'))}`",
        f"- Memory temperature core added: "
        f"`{str(bool(decision.get('memory_temperature_core_added'))).lower()}`",
        f"- Memory temperature UI/report visibility added: "
        f"`{str(bool(decision.get('memory_temperature_visibility_added'))).lower()}`",
        f"- Behavior unchanged: `{str(bool(decision.get('behavior_unchanged'))).lower()}` "
        f"(basis: {_md_cell(decision.get('correctness_basis'))})",
        f"- Retrieval / ranking influence enabled: "
        f"`{str(bool(decision.get('retrieval_ranking_influence_enabled'))).lower()}` "
        "(retrieval/ranking influence not enabled)",
        f"- Benchmark --check: `{_md_cell(decision.get('benchmark_check'))}`",
        f"- Full pytest: `{_md_cell(decision.get('pytest_passed'))} passed`",
        f"- Human review required: `{str(bool(decision.get('human_review_required'))).lower()}`",
        "- Reasons:",
    ]
    for reason in decision.get("reasons") or ["none"]:
        lines.append(f"  - {_md_cell(reason)}")
    lines.append("")

    lines += _render_comparison_section(record.get("benchmark_comparison") or {})
    lines += _render_artifacts_section(record.get("memory_temperature_artifacts") or [])

    lines += [
        "## Guardrail",
        "",
        f"> {record.get('guardrail', '')}",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Disk writes (JSON + Markdown)
# --------------------------------------------------------------------------

def write_dogfood_record(
    record: dict[str, Any],
    *,
    experiments_root: str | Path | None = None,
) -> dict[str, str]:
    """Write the record to ``.agent/experiments/<id>.json`` + ``.md`` safely."""
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
    md_path.write_text(render_dogfood_markdown(record), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "experiment_id": experiment_id,
    }


def create_memory_temperature_dogfood(
    *,
    repo_path: str | Path | None = None,
    benchmark_root: str | Path | None = None,
    experiments_root: str | Path | None = None,
    min_total: int = 5,
    correctness_unchanged: bool = True,
    benchmark_check: str = DEFAULT_BENCHMARK_CHECK,
    pytest_passed: int = DEFAULT_PYTEST_PASSED,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build and write the dogfood record; return paths + the record."""
    record = build_dogfood_record(
        repo_path=repo_path,
        benchmark_root=benchmark_root,
        min_total=min_total,
        correctness_unchanged=correctness_unchanged,
        benchmark_check=benchmark_check,
        pytest_passed=pytest_passed,
        now=now,
    )
    out = write_dogfood_record(record, experiments_root=experiments_root)
    return {
        "record": record,
        "json_path": out["json_path"],
        "md_path": out["md_path"],
        "experiment_id": out["experiment_id"],
    }
