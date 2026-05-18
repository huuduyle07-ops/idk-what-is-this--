from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = PROJECT_ROOT / ".agent" / "benchmarks"
REPORT_DIR = PROJECT_ROOT / ".agent" / "reports"


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _benchmark_reports() -> list[Path]:
    if not BENCH_DIR.is_dir():
        return []
    return sorted(
        BENCH_DIR.glob("benchmark_report_*.json"),
        key=lambda p: p.stat().st_mtime,
    )


def _choose_latest_meaningful_report(min_total: int) -> tuple[Path, dict[str, Any]] | None:
    parsed: list[tuple[Path, dict[str, Any]]] = []
    for path in _benchmark_reports():
        data = _load_json(path)
        if data is not None:
            parsed.append((path, data))

    if not parsed:
        return None

    for path, data in reversed(parsed):
        if int(data.get("total") or 0) >= min_total:
            return path, data

    for path, data in reversed(parsed):
        if int(data.get("total") or 0) > 0:
            return path, data

    return parsed[-1]


def _case_lookup(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        name = str(result.get("name") or "").strip()
        if name:
            lookup[name] = result
    return lookup


def _shorten(text: Any, limit: int = 300) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3].rstrip() + "..."


def _failed_reason(result: dict[str, Any]) -> str:
    bits: list[str] = []
    if result.get("validation_ok") is False:
        bits.append("validation failed")
    if result.get("missing_expected_files"):
        bits.append(f"missing expected files: {result.get('missing_expected_files')}")
    if result.get("touched_forbidden_files"):
        bits.append(f"touched forbidden files: {result.get('touched_forbidden_files')}")
    if result.get("toolchain_issue"):
        bits.append(f"toolchain issue: {result.get('toolchain_issue')}")
    validation_output = result.get("validation_output")
    if validation_output and validation_output != "OK":
        bits.append(f"validation output: {_shorten(validation_output, 220)}")
    if not bits and result.get("runner_log_tail"):
        bits.append(f"runner log: {_shorten(result.get('runner_log_tail'), 220)}")
    return "; ".join(bits) or "benchmark case did not pass"


def _flaky_reason(result: dict[str, Any]) -> str:
    attempts = result.get("attempts")
    retry_results = result.get("retry_results") or []
    failed_attempts = 0
    if isinstance(retry_results, list):
        failed_attempts = sum(
            1
            for item in retry_results
            if isinstance(item, dict) and item.get("success") is False
        )
    bits = ["case required retry before passing"]
    if attempts:
        bits.append(f"attempts: {attempts}")
    if failed_attempts:
        bits.append(f"failed attempts before pass: {failed_attempts}")
    return "; ".join(bits)


def _slow_reason(slow: dict[str, Any], result: dict[str, Any] | None) -> str:
    duration = slow.get("duration_sec")
    bits = [f"slow passing case: {duration}s" if duration is not None else "slow passing case"]
    if result and result.get("patch_loop_attempts"):
        bits.append(f"patch loop attempts: {result.get('patch_loop_attempts')}")
    if result and result.get("fallback_count"):
        bits.append(f"model fallbacks: {result.get('fallback_count')}")
    return "; ".join(bits)


def _base_item(
    *,
    kind: str,
    case_name: str,
    reason: str,
    report_name: str,
    suggested_mode: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "kind": kind,
        "case_name": case_name,
        "reason": reason,
        "source_benchmark_report": report_name,
        "suggested_mode": suggested_mode,
        "human_approved_for_proposal": False,
        "level3_gate": "Set human_approved_for_proposal=true after human review to allow proposal generation.",
    }
    if result:
        if result.get("case_file"):
            item["case_file"] = result.get("case_file")
        if result.get("duration_sec") is not None:
            item["duration_sec"] = result.get("duration_sec")
        if result.get("language"):
            item["language"] = result.get("language")
        if result.get("category"):
            item["category"] = result.get("category")
        if result.get("difficulty"):
            item["difficulty"] = result.get("difficulty")
    return item


def build_plan(report_path: Path, report: dict[str, Any], max_slow: int) -> dict[str, Any]:
    report_name = report_path.name
    results = [r for r in (report.get("results") or []) if isinstance(r, dict)]
    lookup = _case_lookup(report)
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for result in results:
        if result.get("skipped"):
            continue
        if result.get("success") is True:
            continue
        case_name = str(result.get("name") or "").strip()
        if not case_name:
            continue
        key = ("failed_case", case_name)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            _base_item(
                kind="failed_case",
                case_name=case_name,
                reason=_failed_reason(result),
                report_name=report_name,
                suggested_mode="patch_proposal",
                result=result,
            )
        )

    for result in results:
        if result.get("flaky") is not True:
            continue
        case_name = str(result.get("name") or "").strip()
        if not case_name:
            continue
        key = ("flaky_case", case_name)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            _base_item(
                kind="flaky_case",
                case_name=case_name,
                reason=_flaky_reason(result),
                report_name=report_name,
                suggested_mode="plan_only",
                result=result,
            )
        )

    slowest = report.get("slowest_cases") or []
    if not isinstance(slowest, list) or not slowest:
        slowest = sorted(
            (
                r
                for r in results
                if r.get("success") is True and isinstance(r.get("duration_sec"), (int, float))
            ),
            key=lambda r: float(r.get("duration_sec") or 0),
            reverse=True,
        )

    for slow in slowest:
        if not isinstance(slow, dict):
            continue
        if slow.get("success") is not True:
            continue
        case_name = str(slow.get("name") or "").strip()
        if not case_name:
            continue
        key = ("slow_passing_case", case_name)
        if key in seen:
            continue
        result = lookup.get(case_name)
        seen.add(key)
        items.append(
            _base_item(
                kind="slow_passing_case",
                case_name=case_name,
                reason=_slow_reason(slow, result),
                report_name=report_name,
                suggested_mode="plan_only",
                result=result,
            )
        )
        if sum(1 for kind, _name in seen if kind == "slow_passing_case") >= max_slow:
            break

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_benchmark_report": str(report_path),
        "source_benchmark_report_name": report_name,
        "benchmark_summary": {
            "total": report.get("total"),
            "passed": report.get("passed"),
            "failed": report.get("failed"),
            "skipped": report.get("skipped"),
            "flaky": report.get("flaky"),
            "success_rate": report.get("success_rate"),
            "duration_sec": report.get("duration_sec"),
        },
        "brain_stamp": report.get("brain_stamp") or {},
        "items": items,
    }


def _brain_stamp_lines(stamp: dict[str, Any]) -> list[str]:
    if not stamp:
        return ["## Brain Stamp", "", "- Not available in source benchmark report."]
    return [
        "## Brain Stamp",
        "",
        f"- Created at: `{stamp.get('created_at') or 'unknown'}`",
        f"- Git SHA: `{stamp.get('git_sha') or 'unknown'}`",
        f"- Branch: `{stamp.get('git_branch') or 'unknown'}`",
        f"- Dirty: `{stamp.get('git_dirty')}` ({stamp.get('git_dirty_summary') or 'unknown'})",
        f"- Prompt/config hash: `{stamp.get('prompt_config_hash') or 'none'}`",
    ]


def render_markdown(plan: dict[str, Any]) -> str:
    summary = plan.get("benchmark_summary") or {}
    lines: list[str] = [
        "# Background Dream Plan",
        "",
        f"- Created at: `{plan.get('created_at')}`",
        f"- Source benchmark report: `{plan.get('source_benchmark_report')}`",
        f"- Total: `{summary.get('total')}`",
        f"- Passed: `{summary.get('passed')}`",
        f"- Failed: `{summary.get('failed')}`",
        f"- Flaky: `{summary.get('flaky')}`",
        f"- Success rate: `{summary.get('success_rate')}`",
        "",
        "## Items",
        "",
    ]

    items = plan.get("items") or []
    if not items:
        lines.append("- No failed, flaky, or slow passing cases found.")
    else:
        for idx, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"### {idx}. `{item.get('case_name')}`",
                    "",
                    f"- Kind: `{item.get('kind')}`",
                    f"- Reason: {item.get('reason')}",
                    f"- Source benchmark report: `{item.get('source_benchmark_report')}`",
                    f"- Suggested mode: `{item.get('suggested_mode')}`",
                    f"- Human approved for proposal: `{item.get('human_approved_for_proposal')}`",
                    "",
                ]
            )

    lines.append("")
    lines.extend(_brain_stamp_lines(plan.get("brain_stamp") or {}))
    lines.append("")
    lines.extend(
        [
            "## Level 3 Gate",
            "",
            "Patch proposal generation is disabled for every item by default.",
            "A human must mark an item with `human_approved_for_proposal=true` before the proposal queue will process it.",
            "",
        ]
    )
    return "\n".join(lines)


def write_plan(plan: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"background_dream_plan_{ts}.json"
    md_path = REPORT_DIR / f"background_dream_plan_{ts}.md"
    json_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(plan), encoding="utf-8")
    return md_path, json_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a report-only background Dream plan from benchmark results."
    )
    parser.add_argument("--min-total", type=int, default=5)
    parser.add_argument("--max-slow", type=int, default=5)
    args = parser.parse_args()

    chosen = _choose_latest_meaningful_report(min_total=max(1, args.min_total))
    if not chosen:
        print(f"No benchmark_report_*.json files found in {BENCH_DIR}.")
        return 1

    report_path, report = chosen
    plan = build_plan(report_path, report, max_slow=max(0, args.max_slow))
    md_path, json_path = write_plan(plan)

    print(f"Background Dream plan: {md_path}")
    print(f"Background Dream plan JSON: {json_path}")
    print(f"Items: {len(plan.get('items') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
