"""File-based experiment registry for benchmark report comparisons."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import get_agent_dir


SCHEMA_VERSION = 1
SUPPORTED_METRICS: tuple[str, ...] = (
    "total",
    "passed",
    "failed",
    "flaky",
    "average_duration",
    "model_calls",
    "fallback_count",
)
EXPERIMENT_LIST_COLUMNS: tuple[str, ...] = (
    "created_at",
    "status",
    "title",
    "experiment_id",
    "baseline_report",
    "variant_report",
)

_EXPERIMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "average_duration": ("average_duration", "avg_duration_sec"),
    "fallback_count": ("fallback_count", "total_fallbacks"),
}
_HIGHER_IS_BETTER: frozenset[str] = frozenset({"passed"})
_LOWER_IS_BETTER: frozenset[str] = frozenset(
    {"failed", "flaky", "average_duration", "model_calls", "fallback_count"}
)
_CORRECTNESS_METRICS: frozenset[str] = frozenset({"passed", "failed", "flaky"})
_CRITICAL_REGRESSION_INCREASES: frozenset[str] = frozenset({"failed", "flaky"})
_CRITICAL_REGRESSION_DECREASES: frozenset[str] = frozenset({"passed"})
_REVIEW_ON_CHANGE: frozenset[str] = frozenset({"total"})
_REVIEW_ON_INCREASE: frozenset[str] = frozenset(
    {"average_duration", "fallback_count", "model_calls"}
)
_BENCHMARK_TIMESTAMP_FIELDS: tuple[str, ...] = (
    "created_at",
    "timestamp",
    "timestamp_iso",
    "started_at",
    "finished_at",
    "run_started_at",
    "generated_at",
    "completed_at",
)
_BENCHMARK_EPOCH_FIELDS: tuple[str, ...] = (
    "timestamp_epoch",
    "created_at_epoch",
    "started_at_epoch",
    "finished_at_epoch",
)


class ExperimentError(ValueError):
    """Friendly registry error suitable for CLI output."""


def default_experiments_root() -> Path:
    return get_agent_dir(None) / "experiments"


def default_benchmark_root() -> Path:
    return get_agent_dir(None) / "benchmarks"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _root(path: str | Path | None, default_factory) -> Path:
    return Path(path) if path is not None else default_factory()


def _project_root_for_agent_child(child_root: Path) -> Path | None:
    root = child_root.resolve()
    if root.parent.name == ".agent":
        return root.parent.parent.resolve()
    return None


def _has_parent_reference(raw: str) -> bool:
    return any(part == ".." for part in raw.replace("\\", "/").split("/"))


def _slug(text: str, fallback: str = "experiment") -> str:
    out: list[str] = []
    for ch in (text or "").lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    value = "".join(out).strip("-")
    return value[:60] or fallback


def _normalize_experiment_id(raw: str) -> str:
    text = str(raw or "").strip()
    if text.endswith(".json"):
        text = text[:-5]
    if not _EXPERIMENT_ID_RE.match(text):
        raise ExperimentError(
            "experiment_id must use only letters, numbers, dots, dashes, or underscores"
        )
    return text


def _generated_experiment_id(title: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{_slug(title)}"


def resolve_experiment_path(
    experiment_ref: str | Path,
    *,
    experiments_root: str | Path | None = None,
    must_exist: bool = False,
) -> Path:
    root = _root(experiments_root, default_experiments_root).resolve()
    text = str(experiment_ref or "").strip()
    if not text:
        raise ExperimentError("experiment reference must be non-empty")
    if _has_parent_reference(text):
        raise ExperimentError("experiment path must not contain '..'")

    ref = Path(text).expanduser()
    normalized = text.replace("\\", "/")
    project_root = _project_root_for_agent_child(root)
    if ref.is_absolute():
        candidate = ref
    elif normalized.startswith(".agent/experiments/") and project_root is not None:
        candidate = project_root / normalized
    elif "/" in normalized:
        candidate = ref if ref.is_absolute() else root / text
    else:
        name = text if text.endswith(".json") else f"{text}.json"
        candidate = root / name

    path = candidate.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ExperimentError(f"experiment path must live inside {root}: {text}") from exc
    if path.suffix.lower() != ".json":
        raise ExperimentError("experiment path must point to a JSON file")
    if must_exist and not path.is_file():
        raise ExperimentError(f"experiment record not found: {path}")
    return path


def resolve_benchmark_report_path(
    report_ref: str | Path,
    *,
    benchmark_root: str | Path | None = None,
    must_exist: bool = False,
) -> Path:
    root = _root(benchmark_root, default_benchmark_root).resolve()
    text = str(report_ref or "").strip()
    if not text:
        raise ExperimentError("benchmark report path must be non-empty")
    if _has_parent_reference(text):
        raise ExperimentError("benchmark report path must not contain '..'")

    ref = Path(text).expanduser()
    normalized = text.replace("\\", "/")
    project_root = _project_root_for_agent_child(root)
    if ref.is_absolute():
        candidate = ref
    elif normalized.startswith(".agent/benchmarks/") and project_root is not None:
        candidate = project_root / normalized
    else:
        candidate = root / text

    path = candidate.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ExperimentError(
            f"benchmark report path must live inside {root}: {text}"
        ) from exc
    if path.suffix.lower() != ".json":
        raise ExperimentError("benchmark report path must point to a JSON file")
    if must_exist and not path.is_file():
        raise ExperimentError(f"benchmark report not found: {path}")
    return path


def _stored_report_ref(path: Path, benchmark_root: Path) -> str:
    project_root = _project_root_for_agent_child(benchmark_root)
    if project_root is not None:
        try:
            return path.resolve().relative_to(project_root).as_posix()
        except ValueError:
            pass
    return path.resolve().relative_to(benchmark_root.resolve()).as_posix()


def _metric_names(metric_names: list[str] | tuple[str, ...] | None) -> list[str]:
    if not metric_names:
        return list(SUPPORTED_METRICS)
    out: list[str] = []
    for raw in metric_names:
        name = str(raw or "").strip()
        if not name:
            continue
        if name not in out:
            out.append(name)
    if not out:
        raise ExperimentError("metric_names must include at least one metric")
    return out


def _write_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _created_at_sort_value(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def list_experiments(
    *,
    status: str | None = None,
    limit: int | None = None,
    experiments_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    if limit is not None and limit < 0:
        raise ExperimentError("limit must be greater than or equal to 0")

    root = _root(experiments_root, default_experiments_root).resolve()
    if not root.is_dir():
        return []

    status_filter = str(status or "").strip() or None
    items: list[tuple[int, float | str, dict[str, Any]]] = []
    for path in root.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if status_filter and data.get("status") != status_filter:
            continue

        row = {
            "created_at": data.get("created_at"),
            "status": data.get("status"),
            "title": data.get("title"),
            "experiment_id": data.get("experiment_id") or path.stem,
            "baseline_report": data.get("baseline_report"),
            "variant_report": data.get("variant_report"),
        }
        created_sort = _created_at_sort_value(row["created_at"])
        if created_sort is None:
            items.append((0, path.name, row))
        else:
            items.append((1, created_sort, row))

    items.sort(key=lambda item: (item[0], item[1]), reverse=True)
    rows = [row for _has_created_at, _sort_value, row in items]
    if limit is not None:
        rows = rows[:limit]
    return rows


def _numeric_value(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _timestamp_value(value: Any) -> float | None:
    numeric = _numeric_value(value)
    if numeric is not None:
        return float(numeric)

    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _benchmark_report_timestamp(report: dict[str, Any]) -> tuple[float, str] | None:
    for field in _BENCHMARK_EPOCH_FIELDS:
        value = _timestamp_value(report.get(field))
        if value is not None:
            return value, field
    for field in _BENCHMARK_TIMESTAMP_FIELDS:
        value = _timestamp_value(report.get(field))
        if value is not None:
            return value, field
    return None


def list_benchmark_reports(
    *,
    min_total: int = 5,
    benchmark_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    if min_total < 0:
        raise ExperimentError("min_total must be greater than or equal to 0")

    root = _root(benchmark_root, default_benchmark_root).resolve()
    if not root.is_dir():
        return []

    items: list[tuple[tuple[int, float | str, str], dict[str, Any]]] = []
    for path in root.glob("*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(report, dict):
            continue

        total = _numeric_value(report.get("total"))
        if total is None or total < min_total:
            continue

        timestamp_info = _benchmark_report_timestamp(report)
        if timestamp_info is not None:
            sort_value, sort_source = timestamp_info
            sort_key: tuple[int, float | str, str] = (2, sort_value, path.name)
        else:
            sort_source = "mtime"
            try:
                sort_key = (1, path.stat().st_mtime, path.name)
            except OSError:
                sort_source = "filename"
                sort_key = (0, path.name, path.name)

        row = {
            "path": str(path.resolve()),
            "filename": path.name,
            "total": total,
            "passed": report.get("passed"),
            "failed": report.get("failed"),
            "flaky": report.get("flaky"),
            "created_at": report.get("created_at"),
            "timestamp": report.get("timestamp"),
            "sort_source": sort_source,
        }
        items.append((sort_key, row))

    items.sort(key=lambda item: item[0], reverse=True)
    return [row for _sort_key, row in items]


def create_experiment(
    *,
    title: str,
    hypothesis: str,
    baseline_report: str | Path,
    variant_report: str | Path,
    subset: Any = None,
    metric_names: list[str] | tuple[str, ...] | None = None,
    greenlight_rule: str = "",
    experiment_id: str | None = None,
    benchmark_root: str | Path | None = None,
    experiments_root: str | Path | None = None,
) -> dict[str, Any]:
    title_clean = str(title or "").strip()
    hypothesis_clean = str(hypothesis or "").strip()
    if not title_clean:
        raise ExperimentError("title must be non-empty")
    if not hypothesis_clean:
        raise ExperimentError("hypothesis must be non-empty")

    bench_root = _root(benchmark_root, default_benchmark_root).resolve()
    exp_root = _root(experiments_root, default_experiments_root).resolve()
    baseline_path = resolve_benchmark_report_path(
        baseline_report,
        benchmark_root=bench_root,
        must_exist=False,
    )
    variant_path = resolve_benchmark_report_path(
        variant_report,
        benchmark_root=bench_root,
        must_exist=False,
    )

    chosen_id = (
        _normalize_experiment_id(experiment_id)
        if experiment_id
        else _generated_experiment_id(title_clean)
    )
    path = resolve_experiment_path(chosen_id, experiments_root=exp_root)
    if path.exists():
        if experiment_id:
            raise ExperimentError(f"experiment already exists: {path.name}")
        base_id = chosen_id
        suffix = 1
        while path.exists():
            chosen_id = f"{base_id}-{suffix}"
            path = resolve_experiment_path(chosen_id, experiments_root=exp_root)
            suffix += 1

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": chosen_id,
        "title": title_clean,
        "hypothesis": hypothesis_clean,
        "baseline_report": _stored_report_ref(baseline_path, bench_root),
        "variant_report": _stored_report_ref(variant_path, bench_root),
        "subset": subset,
        "metric_names": _metric_names(metric_names),
        "greenlight_rule": str(greenlight_rule or "").strip(),
        "status": "created",
        "result": None,
        "created_at": _now_iso(),
    }
    _write_record(path, record)
    return record


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExperimentError(f"{label} is not valid JSON: {path}") from exc
    except OSError as exc:
        raise ExperimentError(f"could not read {label}: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise ExperimentError(f"{label} must be a JSON object: {path}")
    return data


def _number_or_none(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _metric_value(report: dict[str, Any], metric: str) -> int | float | None:
    fields = _METRIC_ALIASES.get(metric, (metric,))
    for field in fields:
        if field in report:
            return _number_or_none(report.get(field))
    return None


def _metric_status(
    baseline: int | float | None,
    variant: int | float | None,
) -> tuple[int | float | None, str]:
    if baseline is None or variant is None:
        return None, "unknown"
    delta = variant - baseline
    if delta > 0:
        return delta, "increased"
    if delta < 0:
        return delta, "decreased"
    return delta, "unchanged"


def _metric_delta(entry: dict[str, Any]) -> int | float | None:
    return _number_or_none(entry.get("delta"))


def _metric_is_unknown(entry: dict[str, Any]) -> bool:
    return entry.get("status") == "unknown" or _metric_delta(entry) is None


def decide_experiment_result(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    critical_regressions: list[str] = []
    review_triggers: list[str] = []
    warnings: list[str] = []
    improvements: list[str] = []

    for metric, entry in metrics.items():
        metric_name = str(metric)
        metric_entry = entry if isinstance(entry, dict) else {}
        if _metric_is_unknown(metric_entry):
            message = f"{metric_name} unknown"
            if metric_name in _CORRECTNESS_METRICS:
                review_triggers.append(message)
            else:
                warnings.append(message)
            continue

        delta = _metric_delta(metric_entry)
        if delta is None or delta == 0:
            continue

        if metric_name in _CRITICAL_REGRESSION_DECREASES and delta < 0:
            critical_regressions.append(f"{metric_name} decreased")
            continue
        if metric_name in _CRITICAL_REGRESSION_INCREASES and delta > 0:
            critical_regressions.append(f"{metric_name} increased")
            continue
        if metric_name in _REVIEW_ON_CHANGE:
            review_triggers.append(f"{metric_name} changed")
            continue
        if metric_name in _REVIEW_ON_INCREASE and delta > 0:
            review_triggers.append(f"{metric_name} increased")
            continue

        outcome = _metric_outcome(metric_name, metric_entry)
        if outcome == "improved":
            direction = "increased" if delta > 0 else "decreased"
            improvements.append(f"{metric_name} {direction}")

    if critical_regressions:
        status = "reject"
        reasons = list(critical_regressions)
    elif review_triggers:
        status = "needs_review"
        reasons = list(review_triggers)
    else:
        status = "greenlight"
        reasons = ["no critical regressions or review triggers"]

    return {
        "status": status,
        "human_review_required": status != "greenlight",
        "reasons": reasons,
        "warnings": warnings,
        "critical_regressions": critical_regressions,
        "improvements": improvements,
    }


def compare_experiment(
    experiment_ref: str | Path,
    *,
    benchmark_root: str | Path | None = None,
    experiments_root: str | Path | None = None,
) -> dict[str, Any]:
    bench_root = _root(benchmark_root, default_benchmark_root).resolve()
    exp_root = _root(experiments_root, default_experiments_root).resolve()
    experiment_path = resolve_experiment_path(
        experiment_ref,
        experiments_root=exp_root,
        must_exist=True,
    )
    record = _read_json_object(experiment_path, "experiment record")

    baseline_path = resolve_benchmark_report_path(
        record.get("baseline_report"),
        benchmark_root=bench_root,
        must_exist=True,
    )
    variant_path = resolve_benchmark_report_path(
        record.get("variant_report"),
        benchmark_root=bench_root,
        must_exist=True,
    )
    baseline_report = _read_json_object(baseline_path, "baseline report")
    variant_report = _read_json_object(variant_path, "variant report")

    metric_names = _metric_names(record.get("metric_names"))
    metrics: dict[str, dict[str, Any]] = {}
    for metric in metric_names:
        baseline_value = _metric_value(baseline_report, metric)
        variant_value = _metric_value(variant_report, metric)
        delta, status = _metric_status(baseline_value, variant_value)
        metrics[metric] = {
            "baseline": baseline_value,
            "variant": variant_value,
            "delta": delta,
            "status": status,
        }

    record["status"] = "compared"
    record["result"] = {
        "compared_at": _now_iso(),
        "baseline_report": record.get("baseline_report"),
        "variant_report": record.get("variant_report"),
        "metrics": metrics,
        "decision": decide_experiment_result(metrics),
    }
    _write_record(experiment_path, record)
    return record


def _format_number(value: int | float | None) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _format_delta(value: int | float | None) -> str:
    if value is None:
        return "unknown"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_format_number(value)}"


def _md_cell(value: Any) -> str:
    text = str(value if value is not None and value != "" else "unknown")
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _resolve_markdown_output_path(
    output_ref: str | Path | None,
    *,
    default_path: Path,
    experiments_root: Path,
) -> Path:
    root = experiments_root.resolve()
    if output_ref is None:
        path = default_path.resolve()
    else:
        text = str(output_ref or "").strip()
        if not text:
            raise ExperimentError("output path must be non-empty")
        if _has_parent_reference(text):
            raise ExperimentError("output path must not contain '..'")

        ref = Path(text).expanduser()
        normalized = text.replace("\\", "/")
        project_root = _project_root_for_agent_child(root)
        if ref.is_absolute():
            candidate = ref
        elif normalized.startswith(".agent/experiments/") and project_root is not None:
            candidate = project_root / normalized
        else:
            candidate = root / text
        path = candidate.resolve()

    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ExperimentError(f"output path must live inside {root}: {path}") from exc
    if path.suffix.lower() != ".md":
        raise ExperimentError("output path must point to a Markdown .md file")
    return path


def _metric_entries_for_markdown(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = record.get("result")
    metrics = result.get("metrics") if isinstance(result, dict) else None
    if isinstance(metrics, dict):
        return metrics
    return {
        name: {
            "baseline": None,
            "variant": None,
            "delta": None,
            "status": "unknown",
        }
        for name in _metric_names(record.get("metric_names"))
    }


def _metric_outcome(metric: str, entry: dict[str, Any]) -> str:
    status = entry.get("status")
    delta = _number_or_none(entry.get("delta"))
    if status == "unknown" or delta is None:
        return "unknown"
    if delta == 0:
        return "unchanged"
    if metric in _LOWER_IS_BETTER:
        return "improved" if delta < 0 else "regressed"
    if metric in _HIGHER_IS_BETTER:
        return "improved" if delta > 0 else "regressed"
    return "improved" if delta > 0 else "regressed"


def _conclusion(record: dict[str, Any], metrics: dict[str, dict[str, Any]]) -> str:
    if record.get("result") is None:
        return "Not compared yet."
    counts = {"improved": 0, "regressed": 0, "unchanged": 0, "unknown": 0}
    for metric, entry in metrics.items():
        outcome = _metric_outcome(metric, entry)
        counts[outcome] = counts.get(outcome, 0) + 1
    return (
        f"{counts['improved']} improved, {counts['regressed']} regressed, "
        f"{counts['unchanged']} unchanged, {counts['unknown']} unknown."
    )


def _append_decision_list(
    lines: list[str],
    label: str,
    values: list[Any],
) -> None:
    lines.append(f"- {label}:")
    if not values:
        lines.append("  - none")
        return
    for value in values:
        lines.append(f"  - {_md_cell(value)}")


def _render_experiment_markdown(record: dict[str, Any]) -> str:
    title = record.get("title") or record.get("experiment_id") or "Experiment"
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    compared_at = result.get("compared_at") if isinstance(result, dict) else None
    decision = result.get("decision") if isinstance(result, dict) else None
    metrics = _metric_entries_for_markdown(record)
    metric_order = record.get("metric_names") or list(metrics)

    lines = [
        f"# {_md_cell(title)}",
        "",
        "## Summary",
        "",
        f"- Experiment ID: `{_md_cell(record.get('experiment_id'))}`",
        f"- Status: `{_md_cell(record.get('status'))}`",
        f"- Hypothesis: {_md_cell(record.get('hypothesis'))}",
        f"- Subset: {_md_cell(record.get('subset'))}",
        f"- Baseline report: `{_md_cell(record.get('baseline_report'))}`",
        f"- Variant report: `{_md_cell(record.get('variant_report'))}`",
        f"- Greenlight rule: {_md_cell(record.get('greenlight_rule'))}",
        f"- Created at: {_md_cell(record.get('created_at'))}",
    ]
    if compared_at:
        lines.append(f"- Compared at: {_md_cell(compared_at)}")

    if isinstance(decision, dict):
        human_review_required = str(bool(decision.get("human_review_required"))).lower()
        lines += [
            "",
            "## Decision",
            "",
            f"- Status: `{_md_cell(decision.get('status'))}`",
            f"- Human review required: `{human_review_required}`",
        ]
        _append_decision_list(lines, "Reasons", list(decision.get("reasons") or []))
        _append_decision_list(lines, "Warnings", list(decision.get("warnings") or []))
        _append_decision_list(
            lines,
            "Critical regressions",
            list(decision.get("critical_regressions") or []),
        )
        _append_decision_list(
            lines,
            "Improvements",
            list(decision.get("improvements") or []),
        )

    lines += [
        "",
        "## Metrics",
        "",
        "| metric | baseline | variant | delta | status |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in metric_order:
        entry = metrics.get(metric) or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(metric),
                    _format_number(entry.get("baseline")),
                    _format_number(entry.get("variant")),
                    _format_delta(entry.get("delta")),
                    _md_cell(entry.get("status")),
                ]
            )
            + " |"
        )

    lines += [
        "",
        "## Conclusion",
        "",
        f"Conclusion: {_conclusion(record, metrics)}",
        "",
    ]
    return "\n".join(lines)


def export_experiment_markdown(
    experiment_ref: str | Path,
    *,
    output: str | Path | None = None,
    experiments_root: str | Path | None = None,
) -> dict[str, Any]:
    exp_root = _root(experiments_root, default_experiments_root).resolve()
    experiment_path = resolve_experiment_path(
        experiment_ref,
        experiments_root=exp_root,
        must_exist=True,
    )
    record = _read_json_object(experiment_path, "experiment record")
    output_path = _resolve_markdown_output_path(
        output,
        default_path=experiment_path.with_suffix(".md"),
        experiments_root=exp_root,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = _render_experiment_markdown(record)
    output_path.write_text(markdown, encoding="utf-8")
    return {
        "path": str(output_path),
        "experiment_path": str(experiment_path),
    }


def format_comparison_summary(record: dict[str, Any]) -> str:
    result = record.get("result") or {}
    metrics = result.get("metrics") or {}
    decision = result.get("decision") if isinstance(result, dict) else None
    lines = [
        f"Experiment: {record.get('title') or record.get('experiment_id')}",
        f"ID: {record.get('experiment_id')}",
        f"Status: {record.get('status')}",
        f"Baseline: {record.get('baseline_report')}",
        f"Variant: {record.get('variant_report')}",
        "Metrics:",
    ]
    for name in record.get("metric_names") or list(metrics):
        item = metrics.get(name) or {}
        baseline = item.get("baseline")
        variant = item.get("variant")
        delta = item.get("delta")
        status = item.get("status") or "unknown"
        if status == "unknown":
            lines.append(
                f"  {name}: unknown "
                f"(baseline {_format_number(baseline)}, variant {_format_number(variant)})"
            )
        else:
            lines.append(
                f"  {name}: {_format_number(baseline)} -> {_format_number(variant)} "
                f"(delta {_format_delta(delta)})"
            )
    if isinstance(decision, dict):
        human_review_required = str(bool(decision.get("human_review_required"))).lower()
        lines.extend(
            [
                "",
                "Decision:",
                f"  status: {decision.get('status') or 'unknown'}",
                f"  human_review_required: {human_review_required}",
                "  reasons:",
            ]
        )
        for reason in decision.get("reasons") or ["none"]:
            lines.append(f"    - {reason}")
        lines.append("  warnings:")
        for warning in decision.get("warnings") or ["none"]:
            lines.append(f"    - {warning}")
    return "\n".join(lines)
