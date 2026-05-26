"""Phase 5.7 — Prompt-Version & Cost Quantifier.

Read-only analytics over existing ``.agent/benchmarks/benchmark_report_*.json``
files. Groups reports by ``brain_stamp.prompt_config_hash`` (falling back to
``"unknown"`` when absent) and computes averages so a user can tell whether a
specific prompt/config identity is more expensive, slower, or fallback-heavy
than another.

Safety:
    * Never runs benchmarks.
    * Never calls a model.
    * Never executes a patch.
    * Never mutates the source benchmark report files.
    * Malformed/unreadable reports are skipped with a structured warning.

The module exposes:
    - ``build_prompt_cost_report(benchmark_root)`` — returns the structured
      ledger as a plain dict.
    - ``render_markdown(report)`` — renders the compact panel table.
    - ``write_prompt_cost_files(benchmark_root, output_json, output_md)`` —
      thin file writer used by the CLI and by the web route caller.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / ".agent" / "benchmarks"
PROMPT_COST_SUBDIR = "prompt_cost"
UNKNOWN = "unknown"


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "malformed_json"
    except OSError:
        return None, "read_error"
    if not isinstance(data, dict):
        return None, "not_object"
    return data, None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _timestamp_from_text(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
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


def _mtime_iso(path: Path) -> tuple[str, float]:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(), ts


def _report_created_at(
    report: dict[str, Any], path: Path
) -> tuple[str, float, str]:
    """Pick the most reliable created-at marker available.

    Mirrors :mod:`scripts.build_benchmark_trends` so the two read the same way.
    """
    for field in ("created_at", "timestamp", "created_at_epoch"):
        sort_value = _timestamp_from_text(report.get(field))
        if sort_value is None:
            continue
        raw = report.get(field)
        if isinstance(raw, (int, float)):
            created_at = datetime.fromtimestamp(float(raw), timezone.utc).isoformat()
        else:
            created_at = str(raw)
        return created_at, sort_value, field

    stamp = report.get("brain_stamp") or {}
    if isinstance(stamp, dict):
        stamp_created = stamp.get("created_at")
        sort_value = _timestamp_from_text(stamp_created)
        if sort_value is not None:
            return str(stamp_created), sort_value, "brain_stamp.created_at"

    try:
        created_at, sort_value = _mtime_iso(path)
        return created_at, sort_value, "mtime"
    except OSError:
        return UNKNOWN, 0.0, "unknown"


def _group_key(report: dict[str, Any]) -> str:
    stamp = report.get("brain_stamp") or {}
    if not isinstance(stamp, dict):
        return UNKNOWN
    raw = stamp.get("prompt_config_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return UNKNOWN


def _is_dirty(report: dict[str, Any]) -> bool:
    stamp = report.get("brain_stamp") or {}
    if not isinstance(stamp, dict):
        return False
    return bool(stamp.get("git_dirty"))


def _model_call_count(report: dict[str, Any]) -> int | None:
    results = report.get("results")
    if not isinstance(results, list):
        return None
    found_any = False
    total = 0
    for item in results:
        if not isinstance(item, dict):
            continue
        calls = item.get("model_calls")
        if not isinstance(calls, list):
            continue
        found_any = True
        total += len(calls)
    return total if found_any else None


def _stamp_summary(report: dict[str, Any]) -> dict[str, Any]:
    stamp = report.get("brain_stamp") or {}
    if not isinstance(stamp, dict):
        stamp = {}

    def _unknown_if_missing(value: Any) -> Any:
        if value is None or value == "":
            return UNKNOWN
        return value

    return {
        "git_sha": _unknown_if_missing(stamp.get("git_sha")),
        "git_branch": _unknown_if_missing(stamp.get("git_branch")),
        "git_dirty": bool(stamp.get("git_dirty")),
        "git_dirty_summary": _unknown_if_missing(stamp.get("git_dirty_summary")),
        "git_diff_stat_capped": _unknown_if_missing(
            stamp.get("git_diff_stat_capped")
        ),
        "prompt_config_hash": _unknown_if_missing(stamp.get("prompt_config_hash")),
        "prompt_config_files": stamp.get("prompt_config_files") or {},
        "brain_stamp_id": _unknown_if_missing(stamp.get("brain_stamp_id")),
        "code_dna_hash": _unknown_if_missing(stamp.get("code_dna_hash")),
    }


def _avg(values: Iterable[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 6)


def _sum_known(values: Iterable[float | None]) -> float | None:
    """Sum of known values; ``None`` only if every value was ``None``.

    Used for the dirty-run count and unknown-cost-call count so an all-missing
    group reports ``"unknown"`` instead of a misleading 0.
    """
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return float(sum(nums))


def _unknown_if_none(value: float | None) -> Any:
    return UNKNOWN if value is None else value


def _run_view(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    created_at, sort_value, sort_source = _report_created_at(report, path)
    return {
        "report": path.name,
        "created_at": created_at,
        "created_at_source": sort_source,
        "_sort_value": sort_value,
        "metrics": {
            "success_rate": _number(report.get("success_rate")),
            "total": _number(report.get("total")),
            "passed": _number(report.get("passed")),
            "failed": _number(report.get("failed")),
            "flaky": _number(report.get("flaky")),
            "duration": _number(
                report.get("avg_duration_sec")
                if report.get("avg_duration_sec") is not None
                else report.get("duration_sec")
            ),
            "fallback_count": _number(report.get("total_fallbacks")),
            "model_calls": _model_call_count(report),
            "input_tokens": _number(report.get("input_tokens")),
            "output_tokens": _number(report.get("output_tokens")),
            "total_tokens": _number(report.get("total_tokens")),
            "estimated_cost": _number(report.get("total_estimated_cost_usd")),
            "unknown_cost_calls": _number(report.get("unknown_cost_calls")),
        },
        "is_dirty": _is_dirty(report),
        "brain_stamp": _stamp_summary(report),
    }


def _aggregate_group(prompt_hash: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [run["metrics"] for run in runs]
    sort_values = [float(run.get("_sort_value") or 0.0) for run in runs]
    last_seen_idx = sort_values.index(max(sort_values)) if sort_values else 0
    first_seen_idx = sort_values.index(min(sort_values)) if sort_values else 0
    latest_report = runs[last_seen_idx]["report"] if runs else None

    # Sum-style metrics. Use ``_sum_known`` so reports without a dirty flag or
    # ``unknown_cost_calls`` don't get silently coerced to 0.
    dirty_runs = _sum_known([1.0 if run["is_dirty"] else 0.0 for run in runs])
    unknown_cost_total = _sum_known([m.get("unknown_cost_calls") for m in metrics])

    averaged = {
        "avg_success_rate": _avg(m.get("success_rate") for m in metrics),
        "avg_total": _avg(m.get("total") for m in metrics),
        "avg_passed": _avg(m.get("passed") for m in metrics),
        "avg_failed": _avg(m.get("failed") for m in metrics),
        "avg_flaky": _avg(m.get("flaky") for m in metrics),
        "avg_duration": _avg(m.get("duration") for m in metrics),
        "avg_fallback_count": _avg(m.get("fallback_count") for m in metrics),
        "avg_model_calls": _avg(m.get("model_calls") for m in metrics),
        "avg_input_tokens": _avg(m.get("input_tokens") for m in metrics),
        "avg_output_tokens": _avg(m.get("output_tokens") for m in metrics),
        "avg_total_tokens": _avg(m.get("total_tokens") for m in metrics),
        "avg_estimated_cost": _avg(m.get("estimated_cost") for m in metrics),
    }

    return {
        "prompt_config_hash": prompt_hash,
        "runs": len(runs),
        "latest_report": latest_report,
        "first_seen": runs[first_seen_idx]["created_at"] if runs else UNKNOWN,
        "last_seen": runs[last_seen_idx]["created_at"] if runs else UNKNOWN,
        "_last_seen_sort": sort_values[last_seen_idx] if sort_values else 0.0,
        **{k: _unknown_if_none(v) for k, v in averaged.items()},
        "unknown_cost_call_count": _unknown_if_none(unknown_cost_total),
        "dirty_run_count": _unknown_if_none(dirty_runs),
        "reports": [
            {
                "report": run["report"],
                "created_at": run["created_at"],
                "git_sha": run["brain_stamp"]["git_sha"],
                "git_branch": run["brain_stamp"]["git_branch"],
                "git_dirty": run["brain_stamp"]["git_dirty"],
                "metrics": run["metrics"],
            }
            for run in runs
        ],
        "brain_stamp_latest": runs[last_seen_idx]["brain_stamp"] if runs else {},
    }


def _summary_highest(
    groups: list[dict[str, Any]], key: str
) -> dict[str, Any] | None:
    candidates: list[tuple[float, dict[str, Any]]] = []
    for group in groups:
        value = group.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            candidates.append((float(value), group))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    best_value, best_group = candidates[0]
    return {
        "prompt_config_hash": best_group["prompt_config_hash"],
        "value": best_value,
        "latest_report": best_group.get("latest_report"),
        "runs": best_group.get("runs"),
    }


def build_prompt_cost_report(
    benchmark_root: str | Path = DEFAULT_BENCHMARK_ROOT,
) -> dict[str, Any]:
    """Group benchmark reports by prompt/config hash and aggregate metrics.

    Source files under ``benchmark_root`` are only read — never modified.
    Returns a structured dict suitable for serialization."""
    root = Path(benchmark_root)
    report_paths = (
        sorted(root.glob("benchmark_report_*.json")) if root.is_dir() else []
    )
    skipped: list[dict[str, str]] = []
    by_hash: dict[str, list[dict[str, Any]]] = {}

    for path in report_paths:
        report, error = _load_json(path)
        if error or report is None:
            skipped.append({"report": path.name, "reason": error or "empty_report"})
            continue
        prompt_hash = _group_key(report)
        by_hash.setdefault(prompt_hash, []).append(_run_view(path, report))

    groups: list[dict[str, Any]] = []
    for prompt_hash, runs in by_hash.items():
        runs.sort(
            key=lambda run: (
                float(run.get("_sort_value") or 0.0),
                str(run.get("report") or ""),
            )
        )
        groups.append(_aggregate_group(prompt_hash, runs))

    # Default sort: newest last_seen first.
    groups.sort(key=lambda g: g["_last_seen_sort"], reverse=True)
    for group in groups:
        group.pop("_last_seen_sort", None)
        for run in group.get("reports", []):
            run.pop("_sort_value", None)

    summary = {
        "group_count": len(groups),
        "report_count": sum(g["runs"] for g in groups),
        "skipped_count": len(skipped),
        "highest_avg_cost": _summary_highest(groups, "avg_estimated_cost"),
        "highest_avg_fallback_count": _summary_highest(
            groups, "avg_fallback_count"
        ),
    }

    return {
        "benchmark_root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "groups": groups,
        "summary": summary,
        "skipped_reports": skipped,
    }


def _md_cell(value: Any) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, float):
        return f"{value:g}".replace("|", "\\|")
    return str(value).replace("|", "\\|")


def _short_hash(value: Any) -> str:
    text = str(value or UNKNOWN)
    if text == UNKNOWN or len(text) <= 12:
        return text
    return text[:12]


def render_markdown(report: dict[str, Any]) -> str:
    """Render the compact prompt-cost panel as Markdown."""
    lines: list[str] = [
        "# Prompt / Cost Quantifier",
        "",
        f"- Benchmark root: `{report.get('benchmark_root', UNKNOWN)}`",
        f"- Generated at: {report.get('generated_at', UNKNOWN)}",
        f"- Groups: {report['summary']['group_count']}",
        f"- Reports analysed: {report['summary']['report_count']}",
        f"- Skipped reports: {report['summary']['skipped_count']}",
    ]

    summary = report.get("summary") or {}
    highest_cost = summary.get("highest_avg_cost")
    highest_fb = summary.get("highest_avg_fallback_count")
    if highest_cost:
        lines.append(
            f"- Highest avg cost: `{_short_hash(highest_cost.get('prompt_config_hash'))}` "
            f"({_md_cell(highest_cost.get('value'))})"
        )
    if highest_fb:
        lines.append(
            f"- Highest avg fallbacks: `{_short_hash(highest_fb.get('prompt_config_hash'))}` "
            f"({_md_cell(highest_fb.get('value'))})"
        )

    lines.extend(
        [
            "",
            "## Groups",
            "",
            "| prompt_hash | runs | avg_success | avg_duration | avg_fallbacks |"
            " avg_total_tokens | avg_cost | latest_report |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )

    for group in report.get("groups") or []:
        lines.append(
            "| "
            f"`{_short_hash(group.get('prompt_config_hash'))}` | "
            f"{_md_cell(group.get('runs'))} | "
            f"{_md_cell(group.get('avg_success_rate'))} | "
            f"{_md_cell(group.get('avg_duration'))} | "
            f"{_md_cell(group.get('avg_fallback_count'))} | "
            f"{_md_cell(group.get('avg_total_tokens'))} | "
            f"{_md_cell(group.get('avg_estimated_cost'))} | "
            f"`{_md_cell(group.get('latest_report'))}` |"
        )

    if report.get("skipped_reports"):
        lines.extend(["", "## Skipped reports", ""])
        for entry in report["skipped_reports"]:
            lines.append(f"- `{entry['report']}` — {entry['reason']}")

    lines.append("")
    return "\n".join(lines)


def write_prompt_cost_files(
    benchmark_root: str | Path = DEFAULT_BENCHMARK_ROOT,
    *,
    output_json: bool = True,
    output_md: bool = False,
) -> dict[str, Any]:
    """Write the report under ``<benchmark_root>/prompt_cost/`` and return paths.

    Writes only inside the ``prompt_cost`` subdirectory. Source
    ``benchmark_report_*.json`` files are never modified.
    """
    root = Path(benchmark_root)
    report = build_prompt_cost_report(root)
    out_dir = root / PROMPT_COST_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    if output_json:
        json_path = out_dir / "prompt_cost_report.json"
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths["json"] = json_path
    if output_md:
        md_path = out_dir / "prompt_cost_report.md"
        md_path.write_text(render_markdown(report), encoding="utf-8")
        paths["markdown"] = md_path

    return {"report": report, "paths": paths, "output_dir": out_dir}
