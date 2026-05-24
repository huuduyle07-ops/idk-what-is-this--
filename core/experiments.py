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

_EXPERIMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "average_duration": ("average_duration", "avg_duration_sec"),
    "fallback_count": ("fallback_count", "total_fallbacks"),
}


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


def format_comparison_summary(record: dict[str, Any]) -> str:
    result = record.get("result") or {}
    metrics = result.get("metrics") or {}
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
    return "\n".join(lines)
