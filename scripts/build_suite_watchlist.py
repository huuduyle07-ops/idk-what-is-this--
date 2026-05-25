from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / ".agent" / "benchmarks"
UNKNOWN = "unknown"
DEFAULT_SUITE_ID = "held_out_v1"
DEFAULT_LAST = 10
DEFAULT_SLOW_MULTIPLIER = 1.5


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


def _report_sort_key(report: dict[str, Any], path: Path) -> float:
    for field in ("created_at", "timestamp", "created_at_epoch"):
        ts = _timestamp_from_text(report.get(field))
        if ts is not None:
            return ts
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _case_status(result: dict[str, Any]) -> str:
    success = bool(result.get("success"))
    flaky = bool(result.get("flaky"))
    if not success:
        return "fail"
    if flaky:
        return "flaky"
    return "pass"


def _select_reports(
    benchmark_root: Path,
    suite_id: str,
    last: int,
    include_unknown_suite: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    paths = (
        sorted(benchmark_root.glob("benchmark_report_*.json"))
        if benchmark_root.is_dir()
        else []
    )
    skipped: list[dict[str, str]] = []
    candidates: list[tuple[float, Path, dict[str, Any]]] = []
    for path in paths:
        report, error = _load_json(path)
        if error:
            skipped.append({"report": path.name, "reason": error})
            continue
        assert report is not None
        report_suite = report.get("suite_id")
        if report_suite is None or report_suite == "":
            if not include_unknown_suite:
                skipped.append({"report": path.name, "reason": "missing_suite_id"})
                continue
        elif report_suite != suite_id:
            skipped.append({"report": path.name, "reason": "different_suite_id"})
            continue
        sort_key = _report_sort_key(report, path)
        candidates.append((sort_key, path, report))
    candidates.sort(key=lambda item: (item[0], item[1].name))
    selected = candidates[-last:] if last > 0 else candidates
    return (
        [
            {"path": path, "report": report, "sort_key": sort_key}
            for sort_key, path, report in selected
        ],
        skipped,
    )


def _collect_case_entries(
    selected: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for item in selected:
        report = item["report"]
        report_name = item["path"].name
        sort_key = item["sort_key"]
        results = report.get("results") or []
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            name = str(result.get("name") or "").strip()
            if not name:
                continue
            entry = entries.setdefault(
                name,
                {
                    "name": name,
                    "runs_seen": 0,
                    "passes": 0,
                    "failures": 0,
                    "flaky_passes": 0,
                    "_durations": [],
                    "_fallbacks": [],
                    "_last_status": "unknown",
                    "_last_seen_report": "unknown",
                    "_last_sort": float("-inf"),
                },
            )
            entry["runs_seen"] += 1
            status = _case_status(result)
            if status == "fail":
                entry["failures"] += 1
            elif status == "flaky":
                entry["flaky_passes"] += 1
                entry["passes"] += 1
            else:
                entry["passes"] += 1
            duration = _safe_float(result.get("duration_sec"))
            if duration is not None:
                entry["_durations"].append(duration)
            fallback = _safe_float(result.get("fallback_count"))
            if fallback is not None:
                entry["_fallbacks"].append(fallback)
            if sort_key >= entry["_last_sort"]:
                entry["_last_sort"] = sort_key
                entry["_last_status"] = status
                entry["_last_seen_report"] = report_name
    return entries


def _round_or_unknown(value: float | None, ndigits: int = 4) -> float | str:
    if value is None:
        return UNKNOWN
    return round(float(value), ndigits)


def build_watchlist(
    benchmark_root: str | Path = DEFAULT_BENCHMARK_ROOT,
    *,
    suite_id: str = DEFAULT_SUITE_ID,
    last: int = DEFAULT_LAST,
    slow_multiplier: float = DEFAULT_SLOW_MULTIPLIER,
    include_unknown_suite: bool = False,
) -> dict[str, Any]:
    root = Path(benchmark_root)
    selected, skipped = _select_reports(root, suite_id, last, include_unknown_suite)
    raw_entries = _collect_case_entries(selected)

    case_avg_duration: dict[str, float | None] = {}
    cases_list: list[dict[str, Any]] = []
    for name, entry in raw_entries.items():
        durations = entry.pop("_durations")
        fallbacks = entry.pop("_fallbacks")
        entry.pop("_last_sort")
        last_status = entry.pop("_last_status")
        last_seen = entry.pop("_last_seen_report")
        runs_seen = entry["runs_seen"]
        avg_duration = mean(durations) if durations else None
        max_duration = max(durations) if durations else None
        avg_fallbacks = mean(fallbacks) if fallbacks else None
        failure_rate = (
            entry["failures"] / runs_seen if runs_seen > 0 else None
        )
        case_avg_duration[name] = avg_duration
        entry["failure_rate"] = _round_or_unknown(failure_rate)
        entry["average_duration"] = _round_or_unknown(avg_duration)
        entry["max_duration"] = _round_or_unknown(max_duration)
        entry["average_fallbacks"] = _round_or_unknown(avg_fallbacks)
        entry["last_status"] = last_status
        entry["last_seen_report"] = last_seen
        cases_list.append(entry)

    valid_durations = [d for d in case_avg_duration.values() if d is not None]
    suite_average = mean(valid_durations) if valid_durations else None

    for entry in cases_list:
        reasons: list[str] = []
        if entry["failures"] >= 1:
            reasons.append("failures")
        if entry["flaky_passes"] >= 1:
            reasons.append("flaky_passes")
        avg = case_avg_duration.get(entry["name"])
        if (
            suite_average is not None
            and suite_average > 0
            and avg is not None
            and avg > slow_multiplier * suite_average
        ):
            reasons.append("slow")
        entry["watchlist_reasons"] = reasons
        entry["watchlisted"] = bool(reasons)

    cases_list.sort(key=lambda case: case["name"])
    watchlist_names = [case["name"] for case in cases_list if case["watchlisted"]]
    stable_names = [case["name"] for case in cases_list if not case["watchlisted"]]

    first_report = selected[0]["path"].name if selected else UNKNOWN
    last_report = selected[-1]["path"].name if selected else UNKNOWN

    return {
        "suite_id": suite_id,
        "include_unknown_suite": include_unknown_suite,
        "report_window": {
            "requested": last,
            "selected": len(selected),
            "first_report": first_report,
            "last_report": last_report,
        },
        "thresholds": {
            "slow_multiplier": slow_multiplier,
        },
        "suite_average_duration": _round_or_unknown(suite_average),
        "cases": cases_list,
        "watchlist": watchlist_names,
        "stable": stable_names,
        "skipped_reports": skipped,
    }


def _md_cell(value: Any) -> str:
    if value is None:
        return UNKNOWN
    return str(value).replace("|", "\\|")


def render_markdown(data: dict[str, Any]) -> str:
    window = data["report_window"]
    thresholds = data["thresholds"]
    lines = [
        f"# Suite Watchlist {data['suite_id']}",
        "",
        f"- Suite: `{data['suite_id']}`",
        f"- Reports selected: {window['selected']} of last {window['requested']} requested",
        f"- First report: `{window['first_report']}`",
        f"- Last report: `{window['last_report']}`",
        f"- Suite average duration: {data['suite_average_duration']}",
        f"- Slow multiplier: {thresholds['slow_multiplier']}x",
        "",
        "> This watchlist is observational. It does not change pass/fail scoring;",
        "> it only highlights held-out cases that have been unstable across runs.",
        "",
        "## Watchlisted cases",
        "",
    ]
    watchlisted = [case for case in data["cases"] if case["watchlisted"]]
    if watchlisted:
        lines.extend(
            [
                "| case | runs_seen | passes | failures | flaky_passes | failure_rate"
                " | average_duration | max_duration | average_fallbacks"
                " | last_status | last_seen_report | reasons |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
            ]
        )
        for case in watchlisted:
            lines.append(
                "| "
                f"`{_md_cell(case['name'])}` | "
                f"{_md_cell(case['runs_seen'])} | "
                f"{_md_cell(case['passes'])} | "
                f"{_md_cell(case['failures'])} | "
                f"{_md_cell(case['flaky_passes'])} | "
                f"{_md_cell(case['failure_rate'])} | "
                f"{_md_cell(case['average_duration'])} | "
                f"{_md_cell(case['max_duration'])} | "
                f"{_md_cell(case['average_fallbacks'])} | "
                f"{_md_cell(case['last_status'])} | "
                f"`{_md_cell(case['last_seen_report'])}` | "
                f"{', '.join(case['watchlist_reasons']) or '-'} |"
            )
    else:
        lines.append("_No watchlisted cases in the selected window._")

    lines.extend(["", "## Stable cases summary", ""])
    stable = data["stable"]
    if stable:
        lines.append(
            f"{len(stable)} stable case(s): "
            + ", ".join(f"`{name}`" for name in stable)
        )
    else:
        lines.append("_No stable cases in the selected window._")
    lines.append("")

    if data["skipped_reports"]:
        lines.extend(["", "## Skipped reports", ""])
        for entry in data["skipped_reports"]:
            lines.append(f"- `{entry['report']}` — {entry['reason']}")
        lines.append("")

    return "\n".join(lines)


def write_watchlist_files(
    benchmark_root: str | Path = DEFAULT_BENCHMARK_ROOT,
    *,
    suite_id: str = DEFAULT_SUITE_ID,
    last: int = DEFAULT_LAST,
    output_md: bool = False,
    slow_multiplier: float = DEFAULT_SLOW_MULTIPLIER,
    include_unknown_suite: bool = False,
) -> dict[str, Any]:
    root = Path(benchmark_root)
    data = build_watchlist(
        root,
        suite_id=suite_id,
        last=last,
        slow_multiplier=slow_multiplier,
        include_unknown_suite=include_unknown_suite,
    )
    trends_dir = root / "trends"
    trends_dir.mkdir(parents=True, exist_ok=True)
    json_path = trends_dir / f"suite_watchlist_{suite_id}.json"
    json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path: Path | None = None
    if output_md:
        md_path = trends_dir / f"suite_watchlist_{suite_id}.md"
        md_path.write_text(render_markdown(data), encoding="utf-8")
    return {
        "data": data,
        "json_path": json_path,
        "md_path": md_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a held-out stability watchlist from existing benchmark reports."
        ),
    )
    parser.add_argument(
        "--benchmarks-dir",
        default=str(DEFAULT_BENCHMARK_ROOT),
        help="Directory containing benchmark_report_*.json files.",
    )
    parser.add_argument(
        "--suite",
        default=DEFAULT_SUITE_ID,
        help="Suite id to inspect (default: held_out_v1).",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=DEFAULT_LAST,
        help="Number of most recent matching reports to consider (default: 10).",
    )
    parser.add_argument(
        "--slow-multiplier",
        type=float,
        default=DEFAULT_SLOW_MULTIPLIER,
        help="Multiplier over the suite average to flag a case as slow (default: 1.5).",
    )
    parser.add_argument(
        "--output-md",
        action="store_true",
        help="Also write a Markdown summary next to the JSON watchlist.",
    )
    parser.add_argument(
        "--include-unknown-suite",
        action="store_true",
        help="Include reports that do not declare a suite_id.",
    )
    args = parser.parse_args(argv)

    written = write_watchlist_files(
        args.benchmarks_dir,
        suite_id=args.suite,
        last=args.last,
        output_md=args.output_md,
        slow_multiplier=args.slow_multiplier,
        include_unknown_suite=args.include_unknown_suite,
    )
    data = written["data"]
    print(
        f"Watchlist for suite '{args.suite}' from "
        f"{data['report_window']['selected']} report(s): "
        f"{len(data['watchlist'])} watchlisted, {len(data['stable'])} stable."
    )
    print(f"JSON: {written['json_path']}")
    if written["md_path"]:
        print(f"Markdown: {written['md_path']}")
    if data["skipped_reports"]:
        print(f"Skipped reports: {len(data['skipped_reports'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
