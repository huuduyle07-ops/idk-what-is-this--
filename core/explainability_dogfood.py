"""Phase 12.13g - Explainability Dogfood Experiment Record.

Builds a read-only experiment/evidence artifact for the explainability stack
shipped in Phase 12.12-12.13f. It:

- compares the latest two meaningful benchmark reports (before/after) when
  available, reusing the Phase 12 experiment/report infrastructure
  (``core.experiments``);
- references the five explainability artifacts shipped in 12.12b-12.13f
  (Evidence Confidence section, Graph Attraction/Repulsion section, Related
  Notes / Lessons debug output, the attraction smoke report, and the
  presentation pack file ``07_graph_attraction_explainability.md``);
- records a *behavior-focused* decision: correctness unchanged, benchmark
  ``--check`` 32/0, full pytest 1294 passed, explainability added.

This module is **read-only / explain-only and deterministic**. It performs no
model/API calls, no subprocess, no benchmark execution, and changes no ranking,
patching, validation, benchmark scoring, or UI behavior. It only reads existing
benchmark reports and checks whether explainability source files / artifacts are
present on disk.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import experiments


PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_VERSION = 1

EXPERIMENT_SLUG = "explainability-stack-dogfood"

EXPLAINABILITY_PHASES: tuple[str, ...] = (
    "12.12b",
    "12.13a",
    "12.13b",
    "12.13c",
    "12.13d",
    "12.13e",
    "12.13f",
)

EXPLAINABILITY_DOGFOOD_GUARDRAIL = (
    "Explainability dogfood is an explain-only evidence record. It does not run "
    "models, run benchmarks, or change CONTROL ranking, Evidence Spread scoring, "
    "Phantom Limb ranking, graph-weight math, patch generation, validation, "
    "benchmark scoring, or UI behavior. It only reads existing benchmark reports "
    "and checks whether explainability artifacts are present on disk."
)

# Correctness metrics that must be unchanged for a behavior-neutral change.
_CORRECTNESS_METRICS: tuple[str, ...] = ("passed", "failed", "flaky")
_COMPARISON_METRICS: tuple[str, ...] = ("total", "passed", "failed", "flaky")

# Behavior-fact defaults, taken from the Phase 12.13g spec.
DEFAULT_BENCHMARK_CHECK = "32/0"
DEFAULT_PYTEST_PASSED = 1294


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
# Explainability artifact references
# --------------------------------------------------------------------------

def _artifact_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "Evidence Confidence report section",
            "kind": "report_section",
            "phase": "12.12b",
            "reference": (
                "web/graph_evidence.py::format_evidence_spread_markdown "
                "(## Evidence Confidence)"
            ),
            "source_path": "web/graph_evidence.py",
            "view_route": "/graph/explainability/view",
        },
        {
            "name": "Graph Attraction / Repulsion report section",
            "kind": "report_section",
            "phase": "12.13a/12.13b",
            "reference": (
                "web/graph_evidence.py (## Graph Attraction / Repulsion); "
                "graph/attraction.py"
            ),
            "source_path": "graph/attraction.py",
            "report_dir": ".agent/reports/graph_attraction",
        },
        {
            "name": "Related Notes / Lessons debug output",
            "kind": "report_section",
            "phase": "12.13c/12.13d",
            "reference": (
                "core/related_notes.py; web/graph_evidence.py "
                "(## Related Notes / Lessons)"
            ),
            "source_path": "core/related_notes.py",
        },
        {
            "name": "Graph Explainability attraction smoke report",
            "kind": "cli_report",
            "phase": "12.13e",
            "reference": (
                "python scripts/explain_graph_weights.py --repo-path . "
                "--include-attraction"
            ),
            "source_path": "scripts/explain_graph_weights.py",
        },
        {
            "name": (
                "Presentation evidence pack file "
                "07_graph_attraction_explainability.md"
            ),
            "kind": "pack_file",
            "phase": "12.13f",
            "reference": (
                ".agent/presentation_evidence/"
                "07_graph_attraction_explainability.md"
            ),
            "source_path": (
                ".agent/presentation_evidence/"
                "07_graph_attraction_explainability.md"
            ),
            "generator": "scripts/build_presentation_evidence_pack.py",
        },
    ]


def build_explainability_artifacts(
    *,
    repo_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return the five explainability artifact references with existence flags."""
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
# Benchmark before/after comparison
# --------------------------------------------------------------------------

def _metric_delta(baseline: Any, variant: Any) -> tuple[int | float | None, str]:
    if not isinstance(baseline, (int, float)) or isinstance(baseline, bool):
        return None, "unknown"
    if not isinstance(variant, (int, float)) or isinstance(variant, bool):
        return None, "unknown"
    delta = variant - baseline
    if delta > 0:
        return delta, "increased"
    if delta < 0:
        return delta, "decreased"
    return delta, "unchanged"


def _correctness_assessment(
    metrics: dict[str, dict[str, Any]],
) -> tuple[bool | None, str]:
    """Assess correctness using the same semantics as ``core.experiments``.

    Returns ``(correctness_unchanged, note)``:
    - ``None`` when the before/after pair is not comparable (a metric is
      unknown, or the suite size ``total`` differs between the two reports).
    - ``False`` when a regression is present in a same-size suite (``failed`` or
      ``flaky`` increased, or ``passed`` decreased).
    - ``True`` when same-size reports show no correctness regression.

    A higher ``passed`` count alone is not a regression, so it does not flip the
    result to ``False`` (matching the experiment decision policy).
    """
    for name in ("total",) + _CORRECTNESS_METRICS:
        entry = metrics.get(name) or {}
        if entry.get("delta") is None or entry.get("status") == "unknown":
            return None, (
                f"`{name}` is unknown in one of the reports; the before/after "
                "comparison is inconclusive."
            )

    total_delta = (metrics.get("total") or {}).get("delta")
    if total_delta != 0:
        return None, (
            "Benchmark suite size differs between the two reports "
            f"(total delta {total_delta:+}); a partial run versus a full run is "
            "not a directly comparable before/after pair, so correctness is "
            "recorded as asserted."
        )

    failed_up = (metrics.get("failed") or {}).get("delta", 0) > 0
    flaky_up = (metrics.get("flaky") or {}).get("delta", 0) > 0
    passed_down = (metrics.get("passed") or {}).get("delta", 0) < 0
    if failed_up or flaky_up or passed_down:
        return False, (
            "Correctness regression detected between same-size before/after "
            "reports (failed/flaky increased or passed decreased)."
        )
    return True, "No correctness regression between same-size before/after reports."


def build_benchmark_comparison(
    *,
    benchmark_root: str | Path | None = None,
    min_total: int = 5,
) -> dict[str, Any]:
    """Compare the latest two meaningful benchmark reports (before/after).

    Newest report is the variant (after the explainability stack); the previous
    one is the baseline (before). Degrades gracefully when fewer than two
    meaningful reports exist.
    """
    reports = experiments.list_benchmark_reports(
        min_total=min_total,
        benchmark_root=benchmark_root,
    )
    if len(reports) < 2:
        return {
            "available": False,
            "min_total": min_total,
            "report_count": len(reports),
            "note": (
                "Fewer than two meaningful benchmark reports "
                f"(total >= {min_total}) were available; recording asserted "
                "behavior facts without an empirical before/after comparison."
            ),
            "metrics": {},
            "correctness_unchanged": None,
        }

    variant = reports[0]
    baseline = reports[1]
    baseline_values = experiments.extract_benchmark_metrics(baseline, _COMPARISON_METRICS)
    variant_values = experiments.extract_benchmark_metrics(variant, _COMPARISON_METRICS)
    metrics: dict[str, dict[str, Any]] = {}
    for name in _COMPARISON_METRICS:
        base = baseline_values.get(name)
        var = variant_values.get(name)
        delta, status = _metric_delta(base, var)
        metrics[name] = {
            "baseline": base,
            "variant": var,
            "delta": delta,
            "status": status,
        }

    correctness_unchanged, correctness_note = _correctness_assessment(metrics)
    return {
        "available": True,
        "min_total": min_total,
        "report_count": len(reports),
        "baseline_report": baseline.get("filename"),
        "variant_report": variant.get("filename"),
        "metrics": metrics,
        "correctness_unchanged": correctness_unchanged,
        "correctness_note": correctness_note,
    }


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
    if effective:
        reasons.append(
            "Correctness unchanged (read-only explainability layers add no "
            "behavior change)."
        )
    else:
        reasons.append(
            "Observed benchmark correctness changed between the before/after "
            "reports; human review required."
        )
    reasons.append(f"Benchmark --check: {benchmark_check}.")
    reasons.append(f"Full pytest suite: {pytest_passed} passed.")
    reasons.append(
        "Explainability stack added (Phase "
        + ", ".join(EXPLAINABILITY_PHASES)
        + ")."
    )

    status = (
        "behavior_unchanged_explainability_added"
        if effective
        else "needs_review_correctness_changed"
    )
    return {
        "status": status,
        "correctness_unchanged": bool(effective),
        "correctness_basis": correctness_basis,
        "benchmark_check": benchmark_check,
        "pytest_passed": pytest_passed,
        "explainability_added": True,
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
    """Assemble the full explainability dogfood record (no disk writes)."""
    moment = _now(now)
    comparison = build_benchmark_comparison(
        benchmark_root=benchmark_root,
        min_total=min_total,
    )
    artifacts = build_explainability_artifacts(repo_path=repo_path)
    decision = _behavior_decision(
        asserted_correctness_unchanged=bool(correctness_unchanged),
        observed_correctness_unchanged=comparison.get("correctness_unchanged"),
        benchmark_check=benchmark_check,
        pytest_passed=pytest_passed,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_kind": "explainability_dogfood",
        "experiment_id": _experiment_id(moment),
        "title": "Explainability Stack Dogfood (Phase 12.12-12.13f)",
        "hypothesis": (
            "The explainability stack adds read-only evidence layers (Evidence "
            "Confidence, Graph Attraction/Repulsion, Related Notes/Lessons, the "
            "attraction smoke report, and the presentation pack file) without "
            "changing correctness, ranking, patching, validation, benchmark "
            "scoring, or UI behavior."
        ),
        "phases_covered": list(EXPLAINABILITY_PHASES),
        "created_at": moment.isoformat(timespec="seconds"),
        "benchmark_comparison": comparison,
        "explainability_artifacts": artifacts,
        "behavior_decision": decision,
        "guardrail": EXPLAINABILITY_DOGFOOD_GUARDRAIL,
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
    for name in _COMPARISON_METRICS:
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
    lines = ["## Explainability artifacts referenced", ""]
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
        if art.get("report_dir"):
            lines.append(f"- Report dir: `{_md_cell(art.get('report_dir'))}`")
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
        f"- Correctness unchanged: `{str(bool(decision.get('correctness_unchanged'))).lower()}` "
        f"(basis: {_md_cell(decision.get('correctness_basis'))})",
        f"- Benchmark --check: `{_md_cell(decision.get('benchmark_check'))}`",
        f"- Full pytest: `{_md_cell(decision.get('pytest_passed'))} passed`",
        f"- Explainability added: `{str(bool(decision.get('explainability_added'))).lower()}`",
        f"- Human review required: `{str(bool(decision.get('human_review_required'))).lower()}`",
        "- Reasons:",
    ]
    for reason in decision.get("reasons") or ["none"]:
        lines.append(f"  - {_md_cell(reason)}")
    lines.append("")

    lines += _render_comparison_section(record.get("benchmark_comparison") or {})
    lines += _render_artifacts_section(record.get("explainability_artifacts") or [])

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


def create_explainability_dogfood(
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
