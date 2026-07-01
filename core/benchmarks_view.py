"""Web-facing summary helpers for benchmark reports (Phase 5 Slice 3).

The CLI summarizers in benchmarks/run_benchmarks.py (`summarize_report` etc.)
print to stdout. The web UI needs structured data, so this module reads the
JSON reports and returns dicts safe to serialize.

All file lookups are scoped to <repo_path>/.agent/benchmarks/. Filenames are
validated against a regex AND resolved+checked-against the bench dir to
prevent path-traversal via the web routes.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_FILENAME_RE = re.compile(r"^benchmark_report_(\d+)\.json$")
_META_FILENAME = "history_meta.json"
_FILE_CHANGE_LEDGER_FIELDS = (
    "patched_files",
    "generated_artifacts",
    "unexpected_mutations",
)
_FILE_CHANGE_SCOPES = ("CLEAN", "GENERATED", "UNEXPECTED", "UNKNOWN")
_TEMP_CREATE_ATTEMPTS = 100
_WINDOWS_REPLACE_ATTEMPTS = 4
_WINDOWS_REPLACE_RETRY_DELAY_SECONDS = 0.02
_FAILURE_KIND_DISPLAY_BY_KIND = {
    "environment": "ENVIRONMENT",
    "toolchain": "TOOLCHAIN",
    "security_tool": "SECURITY TOOL",
    "code_unknown": "CODE / UNKNOWN",
}
_ENVIRONMENT_OR_TOOLCHAIN_FAILURE_DISPLAYS = {
    "ENVIRONMENT",
    "TOOLCHAIN",
    "SECURITY TOOL",
}
_CODE_UNKNOWN_FAILURE_DISPLAYS = {"CODE / UNKNOWN"}


def _bench_dir(repo_path: str | Path) -> Path:
    return Path(repo_path).resolve() / ".agent" / "benchmarks"


def _meta_path(repo_path: str | Path) -> Path:
    return _bench_dir(repo_path) / _META_FILENAME


def read_benchmark_meta(repo_path: str | Path) -> dict:
    path = _meta_path(repo_path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_benchmark_meta(repo_path: str | Path, meta: dict) -> None:
    path = _meta_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _write_meta_temp_file(path, meta)
    try:
        _replace_meta_file(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _write_meta_temp_file(path: Path, meta: dict) -> Path:
    for attempt in range(_TEMP_CREATE_ATTEMPTS):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        tmp_path = path.with_name(f"{path.name}.{stamp}.{attempt}.tmp")
        try:
            with tmp_path.open("x", encoding="utf-8") as tmp:
                json.dump(meta, tmp, indent=2, ensure_ascii=False)
            return tmp_path
        except FileExistsError:
            continue
        except Exception:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            raise
    raise FileExistsError(f"could not create unique temp file for {path}")


def _replace_meta_file(tmp_path: Path, path: Path) -> None:
    attempts = _WINDOWS_REPLACE_ATTEMPTS if path.drive else 1
    for attempt in range(attempts):
        try:
            tmp_path.replace(path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            _wait_before_replace_retry()


def _wait_before_replace_retry() -> None:
    deadline = (
        datetime.now(timezone.utc).timestamp()
        + _WINDOWS_REPLACE_RETRY_DELAY_SECONDS
    )
    while datetime.now(timezone.utc).timestamp() < deadline:
        pass


def update_benchmark_entry(repo_path: str | Path, filename: str, **fields) -> dict:
    meta = read_benchmark_meta(repo_path)
    entry = dict(meta.get(filename, {}))
    entry.update(fields)
    meta[filename] = entry
    write_benchmark_meta(repo_path, meta)
    return entry


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _has_artifact_ledger(result: dict[str, Any]) -> bool:
    return any(field in result for field in _FILE_CHANGE_LEDGER_FIELDS)


def _changed_total(result: dict[str, Any], files: list[str]) -> int | None:
    if "changed_files" in result and isinstance(result.get("changed_files"), list):
        return len(_string_list(result.get("changed_files")))
    if files:
        return len(set(files))
    return None


def summarize_file_change_scope(result: dict[str, Any] | None) -> dict[str, Any]:
    """Return display-only file-change scope metadata for one case result.

    The helper only summarizes fields already present in a benchmark report.
    It does not re-run ledger classification and does not affect pass/fail
    values, benchmark scoring, patching, validation, or report storage.
    """
    if not isinstance(result, dict):
        result = {}
    patched = _string_list(result.get("patched_files"))
    generated = _string_list(result.get("generated_artifacts"))
    unexpected = _string_list(result.get("unexpected_mutations"))
    has_ledger = _has_artifact_ledger(result)

    if not has_ledger:
        scope = "UNKNOWN"
    elif unexpected:
        scope = "UNEXPECTED"
    elif generated:
        scope = "GENERATED"
    else:
        scope = "CLEAN"

    all_known_files = patched + generated + unexpected
    return {
        "scope": scope,
        "changed_total": _changed_total(result, all_known_files),
        "patched_files": patched,
        "generated_artifacts": generated,
        "unexpected_mutations": unexpected,
        "has_artifact_ledger": has_ledger,
    }


def with_file_change_summaries(report: dict[str, Any]) -> dict[str, Any]:
    """Attach per-case file-change display summaries without mutating input."""
    if not isinstance(report, dict):
        return report
    out = dict(report)
    results = report.get("results")
    if not isinstance(results, list):
        return out

    normalized: list[Any] = []
    for item in results:
        if isinstance(item, dict):
            copied = dict(item)
            copied["file_change_summary"] = summarize_file_change_scope(item)
            normalized.append(copied)
        else:
            normalized.append(item)
    out["results"] = normalized
    return out


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _case_name(result: dict[str, Any]) -> str:
    value = result.get("name")
    if value is None:
        return "(unknown)"
    text = str(value).strip()
    return text or "(unknown)"


def _modern_report_signal(result: dict[str, Any]) -> bool:
    file_summary = result.get("file_change_summary")
    return (
        _has_artifact_ledger(result)
        or (
            isinstance(file_summary, dict)
            and file_summary.get("has_artifact_ledger") is True
        )
        or "failure_kind" in result
        or "failure_kind_display" in result
        or "failure_category" in result
    )


def _failure_kind_display(result: dict[str, Any]) -> str:
    display = result.get("failure_kind_display")
    if isinstance(display, str) and display.strip():
        return display.strip().upper()
    kind = result.get("failure_kind")
    if isinstance(kind, str):
        mapped = _FAILURE_KIND_DISPLAY_BY_KIND.get(kind.strip().lower())
        if mapped:
            return mapped
    return "CODE / UNKNOWN"


def failure_category_display(result: dict[str, Any]) -> str:
    """Return a display string for failure_category (backward-compatible).

    Falls back to empty string when the field is absent (old reports).
    """
    cat = result.get("failure_category")
    if isinstance(cat, str) and cat.strip():
        return cat.strip().replace("_", " ").upper()
    return ""


def _top_duration_cases(results: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for result in results:
        duration = _float_or_none(result.get("duration_sec"))
        if duration is None:
            continue
        cases.append({"name": _case_name(result), "duration_sec": duration})
    cases.sort(key=lambda item: (item["duration_sec"], item["name"]), reverse=True)
    return cases[:limit]


def _top_cost_cases(results: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for result in results:
        cost = _float_or_none(result.get("estimated_cost_usd"))
        if cost is None:
            continue
        cases.append({"name": _case_name(result), "estimated_cost_usd": cost})
    cases.sort(key=lambda item: (item["estimated_cost_usd"], item["name"]), reverse=True)
    return cases[:limit]


def _total_tokens(report: dict[str, Any], results: list[dict[str, Any]]) -> int | None:
    top_level = _int_or_none(report.get("total_tokens"))
    if top_level is not None:
        return top_level

    saw_tokens = False
    total = 0
    for result in results:
        case_total = _int_or_none(result.get("total_tokens"))
        if case_total is None:
            input_tokens = _int_or_none(result.get("input_tokens"))
            output_tokens = _int_or_none(result.get("output_tokens"))
            if input_tokens is None and output_tokens is None:
                continue
            case_total = (input_tokens or 0) + (output_tokens or 0)
        saw_tokens = True
        total += case_total
    return total if saw_tokens else None


def _estimated_cost_usd(
    report: dict[str, Any],
    results: list[dict[str, Any]],
) -> float | None:
    top_level = _float_or_none(report.get("total_estimated_cost_usd"))
    if top_level is not None:
        return top_level

    saw_cost = False
    total = 0.0
    for result in results:
        cost = _float_or_none(result.get("estimated_cost_usd"))
        if cost is None:
            continue
        saw_cost = True
        total += cost
    return round(total, 10) if saw_cost else None


def _fallback_count(report: dict[str, Any], results: list[dict[str, Any]]) -> int | None:
    top_level = _int_or_none(report.get("total_fallbacks"))
    if top_level is not None:
        return top_level

    saw_fallbacks = False
    total = 0
    for result in results:
        count = _int_or_none(result.get("fallback_count"))
        if count is None:
            continue
        saw_fallbacks = True
        total += count
    return total if saw_fallbacks else None


def _health_label(
    *,
    total_cases: int,
    failed: int,
    skipped: int,
    runnable: int,
    pass_rate: float | None,
    has_modern_signal: bool,
    environment_or_toolchain_failure_count: int,
    code_unknown_failure_count: int,
    unexpected_scope_count: int,
) -> str:
    if total_cases <= 0 or not has_modern_signal:
        return "UNKNOWN"
    if unexpected_scope_count > 0 or environment_or_toolchain_failure_count > 0:
        return "ATTENTION"
    if runnable > 0 and failed >= max(3, int(runnable * 0.2)):
        return "ATTENTION"
    if failed == 0 and skipped == 0:
        return "GREEN"
    if code_unknown_failure_count > 0:
        return "MIXED"
    if pass_rate is not None and pass_rate >= 0.9 and failed <= 2:
        return "MOSTLY GREEN"
    if failed > 0:
        return "MIXED"
    return "MOSTLY GREEN"


def summarize_run_health(report: dict[str, Any] | None) -> dict[str, Any]:
    """Return display-only latest-run health metadata for a benchmark report.

    The summary is derived only from fields already present in the loaded JSON.
    It does not run benchmarks, classify files from disk, change scoring,
    execute validation, patch anything, or write report files.
    """
    if not isinstance(report, dict):
        report = {}
    raw_results = report.get("results")
    results = [item for item in raw_results if isinstance(item, dict)] if isinstance(raw_results, list) else []

    total_cases = _int_or_none(report.get("total"))
    if total_cases is None:
        total_cases = len(results)
    passed = _int_or_none(report.get("passed"))
    if passed is None:
        passed = sum(1 for result in results if result.get("success") is True)
    skipped = _int_or_none(report.get("skipped"))
    if skipped is None:
        skipped = sum(1 for result in results if result.get("skipped"))
    failed = _int_or_none(report.get("failed"))
    if failed is None:
        failed = max(0, total_cases - passed - skipped)

    runnable = max(0, total_cases - skipped)
    pass_rate = (passed / runnable) if runnable else None
    pass_rate_display = (
        f"{passed}/{runnable} ({pass_rate * 100:.1f}%)"
        if pass_rate is not None
        else f"{passed}/{runnable} (-)"
    )

    failure_kind_counts: dict[str, int] = {}
    failure_category_counts: dict[str, int] = {}
    for result in results:
        if result.get("success") is True or result.get("skipped"):
            continue
        display = _failure_kind_display(result)
        failure_kind_counts[display] = failure_kind_counts.get(display, 0) + 1
        cat = result.get("failure_category")
        if isinstance(cat, str) and cat:
            failure_category_counts[cat] = failure_category_counts.get(cat, 0) + 1

    scope_counts = {scope: 0 for scope in _FILE_CHANGE_SCOPES}
    for result in results:
        scope = summarize_file_change_scope(result).get("scope")
        if scope not in scope_counts:
            scope = "UNKNOWN"
        scope_counts[str(scope)] += 1

    environment_or_toolchain_failure_count = sum(
        failure_kind_counts.get(label, 0)
        for label in _ENVIRONMENT_OR_TOOLCHAIN_FAILURE_DISPLAYS
    )
    code_unknown_failure_count = sum(
        failure_kind_counts.get(label, 0) for label in _CODE_UNKNOWN_FAILURE_DISPLAYS
    )
    has_modern_signal = bool(results) and any(_modern_report_signal(result) for result in results)

    health_label = _health_label(
        total_cases=total_cases,
        failed=failed,
        skipped=skipped,
        runnable=runnable,
        pass_rate=pass_rate,
        has_modern_signal=has_modern_signal,
        environment_or_toolchain_failure_count=environment_or_toolchain_failure_count,
        code_unknown_failure_count=code_unknown_failure_count,
        unexpected_scope_count=scope_counts["UNEXPECTED"],
    )

    return {
        "total_cases": total_cases,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": pass_rate,
        "pass_rate_display": pass_rate_display,
        "health_label": health_label,
        "failure_kind_counts": dict(sorted(failure_kind_counts.items())),
        "failure_category_counts": dict(sorted(failure_category_counts.items())),
        "environment_or_toolchain_failure_count": environment_or_toolchain_failure_count,
        "code_unknown_failure_count": code_unknown_failure_count,
        "clean_scope_count": scope_counts["CLEAN"],
        "generated_scope_count": scope_counts["GENERATED"],
        "unexpected_scope_count": scope_counts["UNEXPECTED"],
        "unknown_scope_count": scope_counts["UNKNOWN"],
        "file_scope_counts": dict(scope_counts),
        "slowest_cases": _top_duration_cases(results),
        "highest_cost_cases": _top_cost_cases(results),
        "total_tokens": _total_tokens(report, results),
        "estimated_cost_usd": _estimated_cost_usd(report, results),
        "fallback_count": _fallback_count(report, results),
    }


def with_run_health_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Attach run-level health display metadata without mutating input."""
    if not isinstance(report, dict):
        return report
    out = dict(report)
    out["run_health_summary"] = summarize_run_health(out)
    return out


def with_benchmark_display_summaries(report: dict[str, Any]) -> dict[str, Any]:
    """Attach all web display-only benchmark summaries without mutating input."""
    return with_run_health_summary(with_file_change_summaries(report))


def _summarize_one(path: Path) -> dict | None:
    """Return a small metadata dict for one report file. Returns None if the
    filename doesn't match the expected pattern OR the JSON can't be parsed
    (silently skipped in lists)."""
    m = _FILENAME_RE.match(path.name)
    if not m:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    ts = int(m.group(1))
    iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return {
        "filename": path.name,
        "timestamp_epoch": ts,
        "timestamp_iso": iso,
        "total": data.get("total", 0),
        "passed": data.get("passed", 0),
        "failed": data.get("failed", 0),
        "skipped": data.get("skipped", 0),
        "success_rate": data.get("success_rate", 0),
        "duration_sec": data.get("duration_sec", 0),
        "total_tokens": data.get("total_tokens", 0),
        "total_estimated_cost_usd": data.get("total_estimated_cost_usd", 0),
        "health_label": summarize_run_health(data).get("health_label", "UNKNOWN"),
    }


def list_benchmark_reports(
    repo_path: str | Path,
    include_archived: bool = False,
) -> list[dict]:
    """All benchmark reports for a repo, newest first.

    Returns an empty list if .agent/benchmarks/ doesn't exist or contains no
    parseable reports. Entries with deleted=True are always hidden.
    Entries with archived=True are hidden unless include_archived is set."""
    bench_dir = _bench_dir(repo_path)
    if not bench_dir.is_dir():
        return []
    meta = read_benchmark_meta(repo_path)
    summaries: list[dict] = []
    for p in bench_dir.glob("benchmark_report_*.json"):
        s = _summarize_one(p)
        if s is None:
            continue
        entry = meta.get(s["filename"], {})
        s["archived"] = bool(entry.get("archived", False))
        s["pinned"] = bool(entry.get("pinned", False))
        s["deleted"] = bool(entry.get("deleted", False))
        if s["deleted"]:
            continue
        if s["archived"] and not include_archived:
            continue
        summaries.append(s)
    summaries.sort(key=lambda s: s["timestamp_epoch"], reverse=True)
    return summaries


def read_benchmark_report(repo_path: str | Path, filename: str) -> dict | None:
    """Return the full JSON of one report, or None if not found / invalid name.

    Filename validation prevents path traversal: must match
    `benchmark_report_<digits>.json` AND resolve to a file inside the bench
    dir. Anything else returns None.
    """
    if not _FILENAME_RE.match(filename):
        return None
    bench_dir = _bench_dir(repo_path)
    target = (bench_dir / filename).resolve()
    try:
        target.relative_to(bench_dir.resolve())
    except ValueError:
        return None
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    return with_benchmark_display_summaries(data)
