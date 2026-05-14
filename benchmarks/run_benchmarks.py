from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Use the Windows trust store for SSL verification. The default certifi
# bundle won't include locally-installed CAs (e.g. AVG/Kaspersky/corporate
# proxies that MITM HTTPS), and those break Gemini calls. truststore is the
# stdlib-recommended way to honor the OS trust store from Python.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.fast_env import FAST_ENV, apply_fast_env

# Pre-pass: apply --fast env vars before importing modules that may read env
# at import time (web.runner, core.validator, etc.). Re-applied in main() too,
# so the effect is idempotent.
if "--fast" in sys.argv:
    apply_fast_env()




IGNORE_DIRS = {
    ".git",
    ".agent",
    "target",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".venv",
    "venv",
}
IGNORE_FILES = {
    "Cargo.lock",
}

def discover_case_files(cases_root: Path) -> list[Path]:
    """
    Supports both:
    benchmarks/cases/go_wallet_transfer/case.json
    benchmarks/cases/go/go_wallet_transfer/case.json
    """
    return sorted(cases_root.rglob("case.json"))


def load_case(case_file: Path) -> dict:
    with case_file.open("r", encoding="utf-8") as f:
        case = json.load(f)

    case.setdefault("category", "uncategorized")
    case.setdefault("difficulty", "unknown")

    # Useful for report/debug
    case["_case_file"] = str(case_file)
    case["_case_dir"] = str(case_file.parent)

    return case

def _ignore_patterns(dir_path: str, names: list[str]):
    ignored = []
    for name in names:
        if name in IGNORE_DIRS:
            ignored.append(name)
        if name.endswith(".exe"):
            ignored.append(name)
    return ignored


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def snapshot_files(repo: Path) -> dict[str, str]:
    out: dict[str, str] = {}

    for p in repo.rglob("*"):
        if not p.is_file():
            continue

        rel = p.relative_to(repo).as_posix()
        parts = set(rel.split("/"))

        if parts & IGNORE_DIRS or p.name in IGNORE_FILES:
            continue

        if p.name.endswith(".exe"):
            continue

        try:
            out[rel] = file_hash(p)
        except Exception:
            pass

    return out


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(
        k for k in keys
        if before.get(k) != after.get(k)
    )

def run_case(case_file: Path) -> dict[str, Any]:
    from web.runner import run_agent_web
    from core.validator import run_validation_command
    case = load_case(case_file)
    case_dir = case_file.parent

    name = case.get("name") or case_dir.name
    buggy_repo = case_dir / "buggy_repo"
    if not buggy_repo.exists():
        raise FileNotFoundError(f"Missing buggy_repo: {buggy_repo}")

    validation_command = case.get("validation_command", "").strip()
    patch_style = case.get("patch_style", "balanced")
    agent_mode = case.get("agent_mode", "reviewer")
    prompt = case.get("prompt", "").strip()

    if validation_command and "Validation command:" not in prompt:
        prompt += f"\n\nValidation command: {validation_command}"

    started = time.time()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        temp_repo = Path(tmp) / "repo"
        shutil.copytree(
            buggy_repo,
            temp_repo,
            ignore=_ignore_patterns,
        )

        before = snapshot_files(temp_repo)

        result = run_agent_web(
            query=prompt,
            repo_path=str(temp_repo),
            agent_mode=agent_mode,
            project_tag=f"bench-{name}",
            patch_style=patch_style,
            ignore_repo_dna=False,
        )

        after = snapshot_files(temp_repo)
        changed = changed_files(before, after)

        ok = None
        validation_output = ""
        if validation_command:
            ok, validation_output = run_validation_command(
                validation_command,
                cwd=str(temp_repo),
            )

        expected_changed = set(case.get("expected_changed_files", []))
        forbidden_changed = set(case.get("forbidden_changed_files", []))

        missing_expected = sorted(expected_changed - set(changed))
        touched_forbidden = sorted(forbidden_changed & set(changed))

        success = bool(ok)
        if missing_expected:
            success = False
        if touched_forbidden:
            success = False

        return {
            "name": name,
            "success": success,
            "validation_ok": ok,
            "patch_style": patch_style,
            "language": case.get("language"),
            "case_file": str(case_file),            
            "duration_sec": round(time.time() - started, 2),
            "difficulty": case.get("difficulty"),
            "category": case.get("category", "uncategorized"),
            "changed_files": changed,
            "missing_expected_files": missing_expected,
            "touched_forbidden_files": touched_forbidden,
            "validation_output": validation_output[-4000:],
            "agent_answer": result.get("answer", ""),
            "agent_validation": result.get("validation", ""),
        }


def discover_cases(root: Path) -> list[Path]:
    cases_root = root / "cases"
    if not cases_root.exists():
        return []

    return discover_case_files(cases_root)


def check_case(case_file: Path) -> dict[str, Any]:
    """Validate a case.json without invoking the agent."""
    try:
        case = load_case(case_file)
    except Exception as e:
        return {
            "name": case_file.parent.name,
            "case_file": str(case_file),
            "ok": False,
            "errors": [f"Failed to load case.json: {e!r}"],
            "language": None,
            "category": "uncategorized",
            "difficulty": "unknown",
        }

    case_dir = case_file.parent
    buggy_repo = case_dir / "buggy_repo"
    errors: list[str] = []

    required = [
        "name",
        "language",
        "validation_command",
        "expected_changed_files",
        "forbidden_changed_files",
        "prompt",
    ]
    for field in required:
        if field not in case or case[field] in ("", None):
            errors.append(f"Missing required field: {field}")

    if not buggy_repo.exists():
        errors.append(f"Missing buggy_repo: {buggy_repo}")

    if not isinstance(case.get("expected_changed_files", []), list):
        errors.append("expected_changed_files must be a list")
    if not isinstance(case.get("forbidden_changed_files", []), list):
        errors.append("forbidden_changed_files must be a list")

    if buggy_repo.exists():
        for rel in case.get("expected_changed_files", []) or []:
            if isinstance(rel, str) and not (buggy_repo / rel).exists():
                errors.append(f"Expected changed file does not exist: {rel}")
        for rel in case.get("forbidden_changed_files", []) or []:
            if isinstance(rel, str) and not (buggy_repo / rel).exists():
                errors.append(f"Forbidden file does not exist: {rel}")

    return {
        "name": case.get("name") or case_dir.name,
        "case_file": str(case_file),
        "ok": not errors,
        "errors": errors,
        "language": case.get("language"),
        "category": case.get("category", "uncategorized"),
        "difficulty": case.get("difficulty", "unknown"),
    }


def _run_case_with_capture(case_file: Path, capture: bool) -> dict[str, Any]:
    """Run a case; when capture=True, swallow run_agent_web stdout/stderr."""
    if not capture:
        return run_case(case_file)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            res = run_case(case_file)
        except Exception as e:
            res = {
                "name": case_file.parent.name,
                "success": False,
                "error": repr(e),
            }
    res["runner_log_tail"] = buf.getvalue()[-4000:]
    return res


def _print_summary_table(results: list[dict[str, Any]]) -> None:
    print("\n📊 Benchmark Summary")
    for r in results:
        status = "PASS" if r.get("success") else "FAIL"
        name = str(r.get("name") or "")[:32].ljust(32)
        lang = str(r.get("language") or "")[:12].ljust(12)
        cat = str(r.get("category") or "")[:18].ljust(18)
        diff = str(r.get("difficulty") or "")[:6].ljust(6)
        dur = r.get("duration_sec")
        dur_s = f"{dur:>7.2f}s" if isinstance(dur, (int, float)) else "       -"
        print(f"{status}  {name} {lang} {cat} {diff} {dur_s}")


def filter_cases(cases: list[Path], args) -> list[Path]:
    out = []
    for case_file in cases:
        try:
            case = load_case(case_file)
        except Exception:
            # Malformed case.json — keep it so the downstream loop (check or
            # run) can report the load error. Field filters can't apply
            # without parsed JSON; --case can still match on folder name.
            if args.case and case_file.parent.name != args.case:
                continue
            out.append(case_file)
            continue

        name = case.get("name") or case_file.parent.name

        if args.case and not (name == args.case or case_file.parent.name == args.case):
            continue
        if args.language and case.get("language") != args.language:
            continue
        if args.category and case.get("category", "uncategorized") != args.category:
            continue
        if args.difficulty and case.get("difficulty", "unknown") != args.difficulty:
            continue

        out.append(case_file)
    return out


def group_results(
    results: list[dict[str, Any]],
    key: str,
) -> dict[str, dict[str, int]]:
    grouped: dict[str, dict[str, int]] = {}
    for r in results:
        value = r.get(key) or "unknown"
        bucket = grouped.setdefault(value, {"passed": 0, "total": 0})
        bucket["total"] += 1
        if r.get("success"):
            bucket["passed"] += 1
    return grouped


def _print_group(label: str, grouped: dict[str, dict[str, int]]) -> None:
    if not grouped:
        return
    print(f"\nBy {label}:")
    width = max(len(k) for k in grouped)
    for key in sorted(grouped):
        bucket = grouped[key]
        print(f"{key:<{width}}  {bucket.get('passed', 0)}/{bucket.get('total', 0)}")


def summarize_report(report: dict[str, Any], top_slowest: int = 3) -> None:
    results = report.get("results", []) or []
    total = report.get("total", len(results))
    passed = report.get("passed", sum(1 for r in results if r.get("success")))
    skipped = report.get("skipped", sum(1 for r in results if r.get("skipped")))
    failed = report.get("failed", max(0, total - passed - skipped))
    rate = (passed / total * 100) if total else 0.0
    duration = report.get("duration_sec")

    print("📊 Benchmark Report")
    print(f"Total: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Success rate: {rate:.1f}%")
    if isinstance(duration, (int, float)):
        print(f"Duration: {duration:.2f}s")

    # Prefer pre-computed groups; fall back to computing from results
    # (backwards-compat for older report files).
    groups = report.get("groups") or {}
    for label in ("language", "category", "difficulty"):
        grouped = groups.get(label)
        if not grouped:
            grouped = group_results(results, label)
        _print_group(label, grouped)

    durations = [
        (r.get("name") or "(unknown)", r.get("duration_sec"))
        for r in results
        if isinstance(r.get("duration_sec"), (int, float))
    ]
    durations.sort(key=lambda x: x[1], reverse=True)
    if durations:
        print("\nSlowest:")
        for name, dur in durations[:top_slowest]:
            print(f"{name} {dur:.2f}s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", help="Run one case by folder name")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate case structure only; no agent calls.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Short per-case lines + final summary table; capture agent logs.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print final summary table + totals; capture agent logs.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Disable expensive optional subsystems (DB, embeddings, etc.) via env.",
    )
    parser.add_argument("--language", help="Filter by language (exact match)")
    parser.add_argument("--category", help="Filter by category (exact match)")
    parser.add_argument("--difficulty", help="Filter by difficulty (exact match)")
    parser.add_argument("--limit", type=int, help="Run only first N matched cases")
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after first failed case",
    )
    parser.add_argument(
        "--report",
        help="Read an existing benchmark_report JSON and print summary; no agent runs.",
    )
    args = parser.parse_args()

    if args.fast:
        apply_fast_env()

    # --report: read-and-summarize mode, no discovery, no agent.
    if args.report:
        report_path = Path(args.report)
        if not report_path.exists():
            print(f"Report not found: {report_path}")
            return 1
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Failed to read report: {e!r}")
            return 1
        summarize_report(report)
        passed = report.get("passed", 0)
        total = report.get("total", 0)
        return 0 if total and passed == total else 2

    # --quiet wins over --summary if both are passed.
    quiet = args.quiet
    summary = args.summary and not quiet
    capture = quiet or summary

    root = Path(__file__).resolve().parent
    cases = discover_cases(root)
    cases = filter_cases(cases, args)
    if args.limit is not None:
        cases = cases[: args.limit]

    if not cases:
        print("No benchmark cases found.")
        return 1

    # --------- check mode ---------
    if args.check:
        print("🔍 Benchmark Case Check\n")
        seen: set[str] = set()
        check_results: list[dict[str, Any]] = []
        for case_file in cases:
            res = check_case(case_file)
            name = res.get("name") or case_file.parent.name
            if name in seen:
                res["ok"] = False
                res.setdefault("errors", []).append(f"Duplicate case name: {name}")
            else:
                seen.add(name)
            check_results.append(res)

            status = "PASS" if res["ok"] else "FAIL"
            print(f"{status}  {name}")
            for err in res.get("errors", []):
                print(f"  - {err}")

        errors = sum(1 for r in check_results if not r["ok"])
        print(f"\nChecked: {len(check_results)}")
        print(f"Errors: {errors}")
        return 0 if errors == 0 else 2

    # --------- run mode ---------
    seen_names: set[str] = set()
    results: list[dict[str, Any]] = []
    run_started = time.time()

    for case_file in cases:
        case_label = case_file.parent.name

        try:
            case = load_case(case_file)
            case_name = case.get("name") or case_label

            if case_name in seen_names:
                raise ValueError(f"Duplicate benchmark case name: {case_name}")
            seen_names.add(case_name)

            if not quiet:
                print(f"\n🧪 Running benchmark: {case_name}")
            res = _run_case_with_capture(case_file, capture=capture)
        except Exception as e:
            res = {
                "name": case_file.parent.name,
                "success": False,
                "error": repr(e),
            }

        results.append(res)

        if not quiet:
            status = "✅ PASS" if res.get("success") else "❌ FAIL"
            name = res.get("name")
            dur = res.get("duration_sec")
            if summary and isinstance(dur, (int, float)):
                print(f"{status} {name} ({dur:.2f}s)")
            else:
                print(f"{status} {name}")

            if not summary:
                if res.get("changed_files"):
                    print("Changed:", ", ".join(res["changed_files"]))
                if res.get("missing_expected_files"):
                    print("Missing expected:", res["missing_expected_files"])
                if res.get("touched_forbidden_files"):
                    print("Touched forbidden:", res["touched_forbidden_files"])
                if res.get("error"):
                    print("Error:", res["error"])

        if args.fail_fast and not res.get("success"):
            break

    run_duration = round(time.time() - run_started, 2)
    passed = sum(1 for r in results if r.get("success"))
    skipped = sum(1 for r in results if r.get("skipped"))
    total = len(results)
    failed = max(0, total - passed - skipped)

    report = {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "success_rate": passed / total if total else 0,
        "duration_sec": run_duration,
        "filters": {
            "case": args.case,
            "language": args.language,
            "category": args.category,
            "difficulty": args.difficulty,
            "limit": args.limit,
            "fast": bool(args.fast),
        },
        "groups": {
            "language": group_results(results, "language"),
            "category": group_results(results, "category"),
            "difficulty": group_results(results, "difficulty"),
        },
        "results": results,
    }

    out_dir = PROJECT_ROOT / ".agent" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"benchmark_report_{int(time.time())}.json"
    out_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if summary or quiet:
        _print_summary_table(results)
        rate = (passed / total * 100) if total else 0.0
        print(f"\nTotal: {passed}/{total} passed")
        print(f"Success rate: {rate:.1f}%")
        print(f"Report: {out_path}")
    else:
        print(f"\n📊 Benchmark: {passed}/{total} passed")
        print(f"Report written to: {out_path}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if passed == total else 2


if __name__ == "__main__":
    raise SystemExit(main())