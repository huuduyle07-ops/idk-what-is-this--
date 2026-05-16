from __future__ import annotations

import os
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from benchmarks.report_compare import report_success_rate, regression_comparison

BENCH_DIR = PROJECT_ROOT / ".agent" / "benchmarks"
REPORT_DIR = PROJECT_ROOT / ".agent" / "reports"


def run_cmd(args: list[str], timeout_sec: int) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.time()
    try:
        completed = subprocess.run(
            args,
            cwd=PROJECT_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_sec,
            check=False,
            env=env,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "duration_sec": round(time.time() - started, 2),
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-8000:],
            "cmd": args,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "returncode": None,
            "duration_sec": round(time.time() - started, 2),
            "stdout": (e.stdout or "")[-8000:] if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "")[-8000:] if isinstance(e.stderr, str) else "",
            "error": f"TimeoutExpired after {timeout_sec}s",
            "cmd": args,
        }
    except Exception as e:
        return {
            "ok": False,
            "returncode": None,
            "duration_sec": round(time.time() - started, 2),
            "stdout": "",
            "stderr": "",
            "error": repr(e),
            "cmd": args,
        }


def benchmark_reports() -> list[Path]:
    if not BENCH_DIR.exists():
        return []
    return sorted(
        BENCH_DIR.glob("benchmark_report_*.json"),
        key=lambda p: p.stat().st_mtime,
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def find_previous_report(new_report_path: Path) -> Path | None:
    reports = [p for p in benchmark_reports() if p != new_report_path]
    if not reports:
        return None
    older = [p for p in reports if p.stat().st_mtime <= new_report_path.stat().st_mtime]
    return older[-1] if older else reports[-1]

def summarize_report(report: dict[str, Any]) -> list[str]:
    total = report.get("total", 0)
    passed = report.get("passed", 0)
    failed = report.get("failed", 0)
    skipped = report.get("skipped", 0)
    flaky = report.get("flaky", 0)
    duration = report.get("duration_sec")
    rate = report_success_rate(report) * 100

    lines = [
        "## Benchmark Summary",
        "",
        f"- Total: {total}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Skipped: {skipped}",
        f"- Flaky: {flaky}",
        f"- Success rate: {rate:.1f}%",
    ]

    if isinstance(duration, (int, float)):
        lines.append(f"- Duration: {duration:.2f}s")

    slowest = report.get("slowest_cases") or []
    if slowest:
        lines.extend(["", "### Slowest cases", ""])
        for item in slowest[:5]:
            lines.append(f"- `{item.get('name')}` — {item.get('duration_sec')}s")

    failed_cases = [
        r for r in report.get("results", []) or []
        if not r.get("success") and not r.get("skipped")
    ]
    if failed_cases:
        lines.extend(["", "### Failed cases", ""])
        for r in failed_cases:
            lines.append(f"- `{r.get('name')}`")

    flaky_cases = [
        r for r in report.get("results", []) or []
        if r.get("flaky")
    ]
    if flaky_cases:
        lines.extend(["", "### Flaky cases", ""])
        for r in flaky_cases:
            lines.append(f"- `{r.get('name')}` — attempts: {r.get('attempts')}")

    return lines


def brain_stamp_lines(report: dict[str, Any]) -> list[str]:
    stamp = report.get("brain_stamp") or {}
    return [
        "## Brain Stamp",
        "",
        f"- Git SHA: `{stamp.get('git_sha') or 'unknown'}`",
        f"- Branch: `{stamp.get('git_branch') or 'unknown'}`",
        f"- Dirty: `{stamp.get('git_dirty')}` ({stamp.get('git_dirty_summary') or 'unknown'})",
        f"- Prompt/config hash: `{stamp.get('prompt_config_hash') or 'none'}`",
    ]


def write_background_reports(
    check_result: dict[str, Any],
    bench_result: dict[str, Any] | None,
    benchmark_report_path: Path | None,
    benchmark_report: dict[str, Any] | None,
    previous_report_path: Path | None,
    previous_report: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
    alert: dict[str, Any] | None,
) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    md_path = REPORT_DIR / f"background_report_{ts}.md"
    json_path = REPORT_DIR / f"background_report_{ts}.json"

    data = {
        "created_at": datetime.now().isoformat(),
        "check": check_result,
        "benchmark_command": bench_result,
        "benchmark_report": str(benchmark_report_path) if benchmark_report_path else None,
        "previous_benchmark_report": str(previous_report_path) if previous_report_path else None,
        "regression_comparison": comparison,
        "regression_alert": alert,
    }

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    lines: list[str] = [
        "# Background Reporter",
        "",
        f"- Created at: `{data['created_at']}`",
        f"- Benchmark report: `{benchmark_report_path or 'none'}`",
        f"- Previous report: `{previous_report_path or 'none'}`",
        "",
    ]

    if alert:
        lines.extend([
            "## ⚠ Regression detected",
            "",
            f"- Success rate: {alert['old_success_rate']}% → {alert['new_success_rate']}%",
            f"- Drop: {alert['drop_pp']} percentage points",
            f"- Git SHA: `{alert.get('old_git_sha') or 'unknown'}` → `{alert.get('new_git_sha') or 'unknown'}`",
            f"- Dirty tree: `{alert.get('old_dirty')}` → `{alert.get('new_dirty')}`",
            "",
        ])
    elif comparison and comparison.get("checked") is False:
        lines.extend([
            "## Regression comparison",
            "",
            f"- Checked: `False`",
            f"- Reason: `{comparison.get('reason')}`",
            f"- Old runnable: `{comparison.get('old_runnable')}`",
            f"- New runnable: `{comparison.get('new_runnable')}`",
            "",
        ])
        
    lines.extend([
        "## Check",
        "",
        f"- OK: `{check_result.get('ok')}`",
        f"- Return code: `{check_result.get('returncode')}`",
        f"- Duration: `{check_result.get('duration_sec')}s`",
        "",
    ])

    if check_result.get("stderr"):
        lines.extend([
            "## Check error tail",
            "",
            "```text",
            check_result["stderr"][-3000:],
            "```",
            "",
        ])

    if benchmark_report:
        lines.extend(summarize_report(benchmark_report))
        lines.append("")
        lines.extend(brain_stamp_lines(benchmark_report))
        lines.append("")

    if check_result.get("stdout"):
        lines.extend([
            "## Check output tail",
            "",
            "```text",
            check_result["stdout"][-3000:],
            "```",
            "",
        ])

    if bench_result and bench_result.get("stdout"):
        lines.extend([
            "## Benchmark output tail",
            "",
            "```text",
            bench_result["stdout"][-3000:],
            "```",
            "",
        ])
    if bench_result and bench_result.get("stderr"):
        lines.extend([
            "## Benchmark error tail",
            "",
            "```text",
            bench_result["stderr"][-3000:],
            "```",
            "",
        ])

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path, json_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-sec", type=int, default=3600)
    parser.add_argument("--retry-failed", type=int, default=1)
    parser.add_argument("--case", help="Optional smoke test case instead of full run")
    parser.add_argument("--skip-benchmark", action="store_true")
    args = parser.parse_args()

    before_reports = set(benchmark_reports())

    check_cmd = [
        sys.executable,
        "benchmarks/run_benchmarks.py",
        "--check",
    ]
    check_result = run_cmd(check_cmd, timeout_sec=300)

    bench_result = None
    benchmark_report_path = None
    benchmark_report = None
    previous_report_path = None
    previous_report = None
    comparison = None
    alert = None

    if check_result["ok"] and not args.skip_benchmark:
        bench_cmd = [
            sys.executable,
            "benchmarks/run_benchmarks.py",
            "--fast",
            "--summary",
            "--skip-toolchain-failures",
            "--markdown",
            "--retry-failed",
            str(args.retry_failed),
        ]

        if args.case:
            bench_cmd.extend(["--case", args.case])

        bench_result = run_cmd(bench_cmd, timeout_sec=args.timeout_sec)

        after_reports = set(benchmark_reports())
        new_reports = sorted(after_reports - before_reports, key=lambda p: p.stat().st_mtime)

        if new_reports:
            benchmark_report_path = new_reports[-1]
        else:
            reports = benchmark_reports()
            benchmark_report_path = reports[-1] if reports else None

        if benchmark_report_path and benchmark_report_path.exists():
            benchmark_report = load_json(benchmark_report_path)
            previous_report_path = find_previous_report(benchmark_report_path)
            if previous_report_path:
                previous_report = load_json(previous_report_path)
            comparison = regression_comparison(previous_report, benchmark_report)
            alert = comparison.get("alert")

    md_path, json_path = write_background_reports(
        check_result=check_result,
        bench_result=bench_result,
        benchmark_report_path=benchmark_report_path,
        benchmark_report=benchmark_report,
        previous_report_path=previous_report_path,
        previous_report=previous_report,
        comparison=comparison,
        alert=alert,
    )

    print(f"Background report: {md_path}")
    print(f"Background JSON: {json_path}")

    if not check_result["ok"]:
        return 2
    if bench_result and not bench_result["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())