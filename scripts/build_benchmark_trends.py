from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / ".agent" / "benchmarks"
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


def _case_names(report: dict[str, Any]) -> list[str]:
    results = report.get("results") or []
    if not isinstance(results, list):
        return []

    names: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            names.add(name)
    return sorted(names)


def suite_fingerprint(case_names: list[str]) -> str:
    payload = json.dumps(sorted(case_names), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _unknown_if_missing(value: Any) -> Any:
    if value is None or value == "":
        return UNKNOWN
    return value


def _first_metric(report: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = report.get(key)
        if value is not None and value != "":
            return value
    return UNKNOWN


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


def _report_created_at(report: dict[str, Any], path: Path) -> tuple[str, float, str]:
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

    try:
        created_at, sort_value = _mtime_iso(path)
        return created_at, sort_value, "mtime"
    except OSError:
        return UNKNOWN, 0.0, "unknown"


def _brain_stamp_summary(report: dict[str, Any]) -> dict[str, Any]:
    stamp = report.get("brain_stamp") or {}
    if not isinstance(stamp, dict):
        stamp = {}
    return {
        "git_sha": _unknown_if_missing(stamp.get("git_sha")),
        "git_branch": _unknown_if_missing(stamp.get("git_branch")),
        "brain_stamp_id": _unknown_if_missing(stamp.get("brain_stamp_id")),
        "prompt_config_hash": _unknown_if_missing(stamp.get("prompt_config_hash")),
        "code_dna_hash": _unknown_if_missing(stamp.get("code_dna_hash")),
    }


def _run_row(path: Path, report: dict[str, Any], fingerprint: str) -> dict[str, Any]:
    created_at, sort_value, sort_source = _report_created_at(report, path)
    return {
        "report": path.name,
        "created_at": created_at,
        "created_at_source": sort_source,
        "suite_fingerprint": fingerprint,
        "total": _first_metric(report, "total"),
        "passed": _first_metric(report, "passed"),
        "failed": _first_metric(report, "failed"),
        "flaky": _first_metric(report, "flaky"),
        "average_duration": _first_metric(report, "average_duration", "avg_duration_sec"),
        "fallback_count": _first_metric(report, "fallback_count", "total_fallbacks"),
        "tokens": {
            "input": _first_metric(report, "input_tokens"),
            "output": _first_metric(report, "output_tokens"),
            "total": _first_metric(report, "total_tokens"),
        },
        "estimated_cost": _first_metric(
            report,
            "estimated_cost",
            "total_estimated_cost_usd",
        ),
        "average_total_changed_lines": _first_metric(
            report,
            "average_total_changed_lines",
        ),
        "average_files_touched": _first_metric(report, "average_files_touched"),
        "largest_patch_case": _unknown_if_missing(report.get("largest_patch_case")),
        "smallest_patch_case": _unknown_if_missing(report.get("smallest_patch_case")),
        "brain_stamp": _brain_stamp_summary(report),
        "_sort_value": sort_value,
    }


def _same_total_warnings(groups: list[dict[str, Any]]) -> list[str]:
    by_total: dict[Any, list[dict[str, Any]]] = {}
    for group in groups:
        by_total.setdefault(group.get("total"), []).append(group)

    warnings: list[str] = []
    for total, same_total_groups in sorted(by_total.items(), key=lambda item: str(item[0])):
        fingerprints = {group["suite_fingerprint"] for group in same_total_groups}
        if len(fingerprints) <= 1:
            continue
        names = ", ".join(sorted(fingerprints))
        warnings.append(
            f"Reports with same total {total} have different case names; "
            f"kept separate suite groups: {names}"
        )
    return warnings


def build_trend_ledger(benchmark_root: str | Path = DEFAULT_BENCHMARK_ROOT) -> dict[str, Any]:
    root = Path(benchmark_root)
    report_paths = sorted(root.glob("benchmark_report_*.json")) if root.is_dir() else []
    skipped: list[dict[str, str]] = []
    grouped: dict[str, dict[str, Any]] = {}

    for path in report_paths:
        report, error = _load_json(path)
        if error:
            skipped.append({"report": path.name, "reason": error})
            continue
        assert report is not None

        names = _case_names(report)
        fingerprint = suite_fingerprint(names)
        group = grouped.setdefault(
            fingerprint,
            {
                "suite_fingerprint": fingerprint,
                "case_names": names,
                "total": len(names),
                "runs": [],
            },
        )
        group["runs"].append(_run_row(path, report, fingerprint))

    groups = list(grouped.values())
    for group in groups:
        group["runs"].sort(
            key=lambda run: (
                float(run.get("_sort_value") or 0.0),
                str(run.get("report") or ""),
            )
        )
        for run in group["runs"]:
            run.pop("_sort_value", None)

    groups.sort(
        key=lambda group: (
            group["runs"][0]["created_at"] if group["runs"] else "",
            group["suite_fingerprint"],
        )
    )

    warnings = _same_total_warnings(groups)
    return {
        "benchmark_root": str(root),
        "groups": groups,
        "warnings": warnings,
        "skipped_reports": skipped,
    }


def _md_cell(value: Any) -> str:
    if value is None:
        return UNKNOWN
    return str(value).replace("|", "\\|")


def render_markdown(group: dict[str, Any], warnings: list[str] | None = None) -> str:
    lines = [
        f"# Benchmark Trend {group['suite_fingerprint']}",
        "",
        f"- Suite fingerprint: `{group['suite_fingerprint']}`",
        f"- Case count: {len(group.get('case_names') or [])}",
        f"- Reports: {len(group.get('runs') or [])}",
    ]
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend([
        "",
        "## Trend",
        "",
        "| report | passed | failed | flaky | average_duration | fallback_count | tokens_total | estimated_cost | average_total_changed_lines |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for run in group.get("runs") or []:
        lines.append(
            "| "
            f"`{_md_cell(run.get('report'))}` | "
            f"{_md_cell(run.get('passed'))} | "
            f"{_md_cell(run.get('failed'))} | "
            f"{_md_cell(run.get('flaky'))} | "
            f"{_md_cell(run.get('average_duration'))} | "
            f"{_md_cell(run.get('fallback_count'))} | "
            f"{_md_cell((run.get('tokens') or {}).get('total'))} | "
            f"{_md_cell(run.get('estimated_cost'))} | "
            f"{_md_cell(run.get('average_total_changed_lines'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_trend_files(
    benchmark_root: str | Path = DEFAULT_BENCHMARK_ROOT,
    *,
    output_md: bool = False,
) -> dict[str, Any]:
    root = Path(benchmark_root)
    ledger = build_trend_ledger(root)
    trends_dir = root / "trends"
    trends_dir.mkdir(parents=True, exist_ok=True)

    json_files: list[Path] = []
    markdown_files: list[Path] = []
    for group in ledger["groups"]:
        fingerprint = group["suite_fingerprint"]
        payload = {
            "suite_fingerprint": fingerprint,
            "case_names": group["case_names"],
            "total": group["total"],
            "runs": group["runs"],
            "warnings": [
                warning for warning in ledger["warnings"] if fingerprint in warning
            ],
        }
        json_path = trends_dir / f"benchmark_trend_{fingerprint}.json"
        json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        json_files.append(json_path)

        if output_md:
            md_path = trends_dir / f"benchmark_trend_{fingerprint}.md"
            md_path.write_text(
                render_markdown(payload, payload["warnings"]),
                encoding="utf-8",
            )
            markdown_files.append(md_path)

    index_path = trends_dir / "benchmark_trend_index.json"
    index_path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    json_files.append(index_path)

    return {
        "ledger": ledger,
        "json_files": json_files,
        "markdown_files": markdown_files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build same-suite benchmark trend ledgers from existing reports."
    )
    parser.add_argument(
        "--benchmarks-dir",
        default=str(DEFAULT_BENCHMARK_ROOT),
        help="Directory containing benchmark_report_*.json files.",
    )
    parser.add_argument(
        "--output-md",
        action="store_true",
        help="Also write Markdown trend tables next to JSON trend files.",
    )
    args = parser.parse_args(argv)

    written = write_trend_files(args.benchmarks_dir, output_md=args.output_md)
    ledger = written["ledger"]
    print(
        f"Built {len(ledger['groups'])} trend group(s) from "
        f"{args.benchmarks_dir}"
    )
    for path in written["json_files"]:
        print(f"JSON: {path}")
    for path in written["markdown_files"]:
        print(f"Markdown: {path}")
    for warning in ledger["warnings"]:
        print(f"Warning: {warning}")
    if ledger["skipped_reports"]:
        print(f"Skipped malformed/unreadable reports: {len(ledger['skipped_reports'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
