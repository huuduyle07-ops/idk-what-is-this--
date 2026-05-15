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

from benchmarks.fast_env import apply_fast_env, apply_turbo_env

# Pre-pass: apply --fast env vars before importing modules that may read env
# at import time (web.runner, core.validator, etc.). Re-applied in main() too,
# so the effect is idempotent.
if "--fast" in sys.argv:
    apply_fast_env()
if "--turbo" in sys.argv:
    apply_turbo_env()


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


def classify_toolchain_issue(output: str) -> str | None:
    text = output.lower()

    if "python was not found" in text:
        return "python command not available"
    if "node: bad option: --experimental-strip-types" in text:
        return "node version does not support --experimental-strip-types"
    if "node: command not found" in text or "'node' is not recognized" in text:
        return "node not available"
    if "npm: command not found" in text or "'npm' is not recognized" in text:
        return "npm not available"
    if "g++: command not found" in text or "'g++' is not recognized" in text:
        return "g++ not available"
    if "cargo: command not found" in text or "'cargo' is not recognized" in text:
        return "cargo not available"
    if "go: command not found" in text or "'go' is not recognized" in text:
        return "go not available"

    return None


# Language → CLI tools the case's validation step needs available on PATH.
# Kept narrow on purpose: only tools that, if missing, deterministically
# break the case. Optional helpers (npm/npx/gcc) aren't listed because
# their absence depends on what the case's validation_command actually
# invokes.
LANGUAGE_TOOLCHAINS: dict[str, list[str]] = {
    "python": ["python"],
    "go": ["go"],
    "rust": ["cargo"],
    "cpp": ["g++"],
    "c": ["gcc"],
    "javascript": ["node"],
    "typescript": ["node"],
    "html": [],
}

# Tools recognised when they appear as the first token of validation_command.
# Stays a small allowlist so we don't mistakenly treat a project-local
# script (e.g. `./run.sh`, `bench-tool`) as a toolchain requirement.
_VALIDATION_TOOL_ALLOWLIST = {
    "python", "python3", "node", "npm", "npx",
    "go", "cargo", "rustc", "g++", "gcc", "make",
}


def required_tools(case: dict) -> list[str]:
    """CLI tools that must resolve on PATH for the case to validate.

    Combines a language→tool map with the binary named as the first
    token of `validation_command` (when it's a known interpreter).
    Returns a deduplicated list preserving insertion order.
    """
    language = (case.get("language") or "").lower()
    tools: list[str] = list(LANGUAGE_TOOLCHAINS.get(language, []))

    vc = (case.get("validation_command") or "").strip()
    if vc:
        first = vc.split()[0]
        first_name = Path(first).name
        if first_name in _VALIDATION_TOOL_ALLOWLIST and first_name not in tools:
            tools.append(first_name)

    return tools


def detect_missing_tools(case: dict) -> list[str]:
    """Subset of required_tools(case) that shutil.which() can't resolve."""
    return [t for t in required_tools(case) if shutil.which(t) is None]


def classify_patch_kind(agent_answer: str) -> str:
    try:
        data = json.loads(agent_answer or "")
    except (json.JSONDecodeError, TypeError):
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"
    if data.get("patch_plan") is not None:
        return "patch_plan"
    if data.get("patch_candidate") is not None:
        return "patch_candidate"
    return "unknown"


def detect_rollback(agent_validation: str, validation_output: str) -> bool:
    text = ((agent_validation or "") + "\n" + (validation_output or "")).lower()
    return (
        '"rollback_performed": true' in text
        or "rollback_performed=true" in text
        or "rollback performed" in text
    )


def run_case(case_file: Path) -> dict[str, Any]:
    from web.runner import run_agent_web
    from core.validator import run_validation_command
    from agents.model_stats import ModelStatsScope, summarize as summarize_model_stats
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

        with ModelStatsScope() as model_calls:
            result = run_agent_web(
                query=prompt,
                repo_path=str(temp_repo),
                agent_mode=agent_mode,
                project_tag=f"bench-{name}",
                patch_style=patch_style,
                ignore_repo_dna=False,
            )
        model_stats = summarize_model_stats(model_calls)

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
            "toolchain_issue": classify_toolchain_issue(validation_output),
            "patch_kind": classify_patch_kind(result.get("answer", "")),
            "rollback_happened": detect_rollback(
                result.get("validation", ""),
                validation_output,
            ),
            "agent_answer": result.get("answer", ""),
            "agent_validation": result.get("validation", ""),
            "model_calls": list(model_calls),
            "selected_model": model_stats["selected_model"],
            "model_attempts": model_stats["attempts"],
            "fallback_count": model_stats["fallback_count"],
            "models_by_role": model_stats["models_by_role"],
            "patch_loop_attempts": result.get("patch_loop_attempts", 0),
            "patch_loop_stop_reason": result.get("patch_loop_stop_reason"),
            "self_corrected": (result.get("patch_loop_attempts") or 0) > 1,
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


def _aggregate_models(results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """role -> {model_name: cases_won} across non-skipped cases."""
    by_role: dict[str, dict[str, int]] = {}
    for r in results:
        if r.get("skipped"):
            continue
        for role, model in (r.get("models_by_role") or {}).items():
            if not model:
                continue
            by_role.setdefault(role, {})
            by_role[role][model] = by_role[role].get(model, 0) + 1
    return by_role


def _print_model_usage(results: list[dict[str, Any]]) -> None:
    """Print which models actually won the work, per role."""
    by_role = _aggregate_models(results)
    if not by_role:
        return
    print("\nModels used:")
    role_w = max(len(r) for r in by_role)
    for role in sorted(by_role):
        items = sorted(by_role[role].items(), key=lambda x: -x[1])
        parts = [f"{model} ({count})" for model, count in items]
        print(f"  {role:<{role_w}}  {', '.join(parts)}")
    total_fallbacks = sum(r.get("fallback_count", 0) for r in results if not r.get("skipped"))
    if total_fallbacks:
        print(f"Fallbacks: {total_fallbacks}")
    self_corrected = sum(
        1 for r in results if not r.get("skipped") and r.get("self_corrected")
    )
    if self_corrected:
        print(f"Self-corrected: {self_corrected} (needed a 2nd patch attempt)")


def _print_summary_table(results: list[dict[str, Any]]) -> None:
    print("\n📊 Benchmark Summary")
    for r in results:
        if r.get("skipped"):
            status = "SKIP"
        elif r.get("success"):
            status = "PASS"
        else:
            status = "FAIL"
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


def _md_cell(s: Any) -> str:
    return str(s).replace("|", "\\|")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    results = report.get("results", []) or []
    total = report.get("total", len(results))
    passed = report.get("passed", sum(1 for r in results if r.get("success")))
    skipped = report.get("skipped", sum(1 for r in results if r.get("skipped")))
    failed = report.get("failed", max(0, total - passed - skipped))
    rate = (passed / total * 100) if total else 0.0
    duration = report.get("duration_sec")
    filters = report.get("filters") or {}
    groups = report.get("groups") or {}

    lines: list[str] = []
    lines.append("# Benchmark Report")
    lines.append("")

    lines.append("## Totals")
    lines.append(f"- Total: {total}")
    lines.append(f"- Passed: {passed}")
    lines.append(f"- Failed: {failed}")
    lines.append(f"- Skipped: {skipped}")
    lines.append(f"- Success rate: {rate:.1f}%")
    if isinstance(duration, (int, float)):
        lines.append(f"- Duration: {duration:.2f}s")
    lines.append("")

    if filters:
        lines.append("## Filters")
        for k, v in filters.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    for label in ("language", "category", "difficulty"):
        grouped = groups.get(label)
        if not grouped:
            grouped = group_results(results, label)
        if not grouped:
            continue
        title = label.capitalize()
        lines.append(f"## By {label}")
        lines.append("")
        lines.append(f"| {title} | Passed/Total |")
        lines.append("|---|---|")
        for key in sorted(grouped):
            bucket = grouped[key]
            lines.append(
                f"| `{_md_cell(key)}` | "
                f"{bucket.get('passed', 0)}/{bucket.get('total', 0)} |"
            )
        lines.append("")

    durations = [
        (r.get("name") or "(unknown)", r.get("duration_sec"))
        for r in results
        if isinstance(r.get("duration_sec"), (int, float))
    ]
    durations.sort(key=lambda x: x[1], reverse=True)
    if durations:
        lines.append("## Slowest Cases")
        lines.append("")
        lines.append("| Name | Duration |")
        lines.append("|---|---|")
        for name, dur in durations[:5]:
            lines.append(f"| `{_md_cell(name)}` | {dur:.2f}s |")
        lines.append("")

    failed_results = [
        r for r in results
        if not r.get("success") and not r.get("skipped")
    ]
    if failed_results:
        lines.append("## Failed Cases")
        lines.append("")
        for r in failed_results:
            name = r.get("name") or "(unknown)"
            lines.append(f"### `{name}`")
            if r.get("missing_expected_files"):
                files = ", ".join(f"`{f}`" for f in r["missing_expected_files"])
                lines.append(f"- missing_expected_files: {files}")
            if r.get("touched_forbidden_files"):
                files = ", ".join(f"`{f}`" for f in r["touched_forbidden_files"])
                lines.append(f"- touched_forbidden_files: {files}")
            if r.get("toolchain_issue"):
                lines.append(f"- toolchain_issue: {r['toolchain_issue']}")
            if r.get("patch_kind"):
                lines.append(f"- patch_kind: {r['patch_kind']}")
            if r.get("rollback_happened"):
                lines.append("- rollback_happened: true")
            if r.get("error"):
                lines.append(f"- error: `{_md_cell(r['error'])}`")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def compare_reports(
    old: dict[str, Any],
    new: dict[str, Any],
    top_slowest: int = 3,
) -> None:
    print("📊 Benchmark Comparison")

    old_passed = old.get("passed", 0)
    old_total = old.get("total", 0)
    new_passed = new.get("passed", 0)
    new_total = new.get("total", 0)
    print(f"Old: {old_passed}/{old_total}")
    print(f"New: {new_passed}/{new_total}")

    old_results = old.get("results", []) or []
    new_results = new.get("results", []) or []
    old_by_name = {r.get("name"): r for r in old_results if r.get("name")}
    new_by_name = {r.get("name"): r for r in new_results if r.get("name")}

    new_cases = sorted(set(new_by_name) - set(old_by_name))
    removed_cases = sorted(set(old_by_name) - set(new_by_name))

    if new_cases:
        print(f"\nNew cases ({len(new_cases)}):")
        for n in new_cases:
            print(f"  + {n}")
    if removed_cases:
        print(f"\nRemoved cases ({len(removed_cases)}):")
        for n in removed_cases:
            print(f"  - {n}")

    changes: list[tuple[str, bool, bool]] = []
    for name in sorted(set(old_by_name) & set(new_by_name)):
        op = bool(old_by_name[name].get("success"))
        np = bool(new_by_name[name].get("success"))
        if op != np:
            changes.append((name, op, np))
    if changes:
        print(f"\nStatus changes ({len(changes)}):")
        for name, op, np in changes:
            arrow = "PASS → FAIL" if op else "FAIL → PASS"
            print(f"  {name}: {arrow}")

    def _avg_dur(results: list[dict]) -> float:
        durs = [
            r.get("duration_sec") for r in results
            if isinstance(r.get("duration_sec"), (int, float))
        ]
        return sum(durs) / len(durs) if durs else 0.0

    old_avg = _avg_dur(old_results)
    new_avg = _avg_dur(new_results)
    print(f"\nAvg duration: {old_avg:.2f}s → {new_avg:.2f}s")

    durations = [
        (r.get("name") or "(unknown)", r.get("duration_sec"))
        for r in new_results
        if isinstance(r.get("duration_sec"), (int, float))
    ]
    durations.sort(key=lambda x: x[1], reverse=True)
    if durations:
        print("\nSlowest in new:")
        for name, dur in durations[:top_slowest]:
            print(f"  {name} {dur:.2f}s")


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
    parser.add_argument(
        "--turbo",
        action="store_true",
        help="Like --fast, but limits model fallbacks to 1. Faster but may be flaky.",
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
        "--skip-toolchain-failures",
        action="store_true",
        help=(
            "Skip cases whose required CLI tools (python/node/go/cargo/g++/...) "
            "aren't on PATH instead of running and counting them as failures."
        ),
    )
    parser.add_argument(
        "--report",
        help="Read an existing benchmark_report JSON and print summary; no agent runs.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Write a Markdown report next to the JSON report.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Summarize the newest benchmark_report_*.json in .agent/benchmarks.",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="Compare two benchmark report JSON files; no agent runs.",
    )
    args = parser.parse_args()

    if args.fast:
        apply_fast_env()
    if args.turbo:
        apply_turbo_env()

    # --compare: load two reports and diff them; no discovery, no agent.
    if args.compare:
        old_path = Path(args.compare[0])
        new_path = Path(args.compare[1])
        if not old_path.exists():
            print(f"Old report not found: {old_path}")
            return 1
        if not new_path.exists():
            print(f"New report not found: {new_path}")
            return 1
        try:
            old = json.loads(old_path.read_text(encoding="utf-8"))
            new = json.loads(new_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Failed to read report: {e!r}")
            return 1
        compare_reports(old, new)
        return 0

    # --latest: find newest benchmark_report_*.json and summarize it.
    if args.latest:
        out_dir = PROJECT_ROOT / ".agent" / "benchmarks"
        if not out_dir.exists():
            print(f"No benchmark reports found (missing {out_dir}).")
            return 1
        candidates = list(out_dir.glob("benchmark_report_*.json"))
        if not candidates:
            print(f"No benchmark_report_*.json in {out_dir}.")
            return 1
        report_path = max(candidates, key=lambda p: p.stat().st_mtime)
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Failed to read report: {e!r}")
            return 1
        print(f"Latest report: {report_path}")
        summarize_report(report)
        if args.markdown:
            md_path = report_path.with_suffix(".md")
            write_markdown_report(report, md_path)
            print(f"\nMarkdown report: {md_path}")
        passed = report.get("passed", 0)
        total = report.get("total", 0)
        return 0 if total and passed == total else 2

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
        if args.markdown:
            md_path = report_path.with_suffix(".md")
            write_markdown_report(report, md_path)
            print(f"\nMarkdown report: {md_path}")
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

            missing = (
                detect_missing_tools(case)
                if args.skip_toolchain_failures
                else []
            )
            if missing:
                if not quiet:
                    print(
                        f"\n⏭️ Skipping benchmark: {case_name} "
                        f"(missing tools: {', '.join(missing)})"
                    )
                res = {
                    "name": case_name,
                    "success": False,
                    "skipped": True,
                    "skip_reason": "toolchain",
                    "toolchain_issue": f"missing tools: {', '.join(missing)}",
                    "case_file": str(case_file),
                    "language": case.get("language"),
                    "difficulty": case.get("difficulty"),
                    "category": case.get("category", "uncategorized"),
                    "duration_sec": 0.0,
                    "changed_files": [],
                    "missing_expected_files": [],
                    "touched_forbidden_files": [],
                    "validation_output": "",
                    "patch_kind": "skipped",
                    "rollback_happened": False,
                    "agent_answer": "",
                    "agent_validation": "",
                }
            else:
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
            if res.get("skipped"):
                status = "⏭️ SKIP"
            elif res.get("success"):
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
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

        if args.fail_fast and not res.get("success") and not res.get("skipped"):
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
        "success_rate": (passed / (total - skipped)) if (total - skipped) else 0,
        "duration_sec": run_duration,
        "filters": {
            "case": args.case,
            "language": args.language,
            "category": args.category,
            "difficulty": args.difficulty,
            "limit": args.limit,
            "fast": bool(args.fast),
            "turbo": bool(args.turbo),
        },
        "groups": {
            "language": group_results(results, "language"),
            "category": group_results(results, "category"),
            "difficulty": group_results(results, "difficulty"),
        },
        "models_used": _aggregate_models(results),
        "total_fallbacks": sum(
            r.get("fallback_count", 0) for r in results if not r.get("skipped")
        ),
        "self_corrected_count": sum(
            1 for r in results if not r.get("skipped") and r.get("self_corrected")
        ),
        "results": results,
    }

    out_dir = PROJECT_ROOT / ".agent" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    out_path = out_dir / f"benchmark_report_{ts}.json"
    out_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_path: Path | None = None
    if args.markdown:
        md_path = out_dir / f"benchmark_report_{ts}.md"
        write_markdown_report(report, md_path)

    runnable = total - skipped
    rate = (passed / runnable * 100) if runnable else 0.0
    skip_note = f" ({skipped} skipped)" if skipped else ""

    if summary or quiet:
        _print_summary_table(results)
        _print_model_usage(results)
        print(f"\nTotal: {passed}/{runnable} passed{skip_note}")
        print(f"Success rate: {rate:.1f}%")
        print(f"Report: {out_path}")
        if md_path is not None:
            print(f"Markdown: {md_path}")
    else:
        print(f"\n📊 Benchmark: {passed}/{runnable} passed{skip_note}")
        print(f"Report written to: {out_path}")
        if md_path is not None:
            print(f"Markdown written to: {md_path}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())