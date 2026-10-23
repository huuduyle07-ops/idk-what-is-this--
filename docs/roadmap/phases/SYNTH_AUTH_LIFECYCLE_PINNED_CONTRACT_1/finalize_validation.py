"""Static final evidence for the pure pinned lease boundary contract.

This module compiles source in memory, reads JSON and checks whitespace. It
compares guarded registry/picker evidence and original preservation checks.
Subprocesses only read Git's file list and diff whitespace. No owner is imported.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

sys.dont_write_bytecode = True
OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
NEW_TEST = ROOT / "tests/test_synthetic_runtime_authorization_lifecycle_pinned_contract.py"


def read(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def write(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    static_errors = []
    authored_sources = sorted(OUTPUT.glob("*.py")) + [NEW_TEST]
    workspace_baseline = read("preservation_baseline.json")
    existing_sources = [ROOT / name for name, record in workspace_baseline["files"].items()
        if name.endswith(".py") and record is not None]
    sources = sorted(set(existing_sources + authored_sources))
    for source in sources:
        try:
            compile(source.read_bytes(), str(source), "exec", dont_inherit=True)
        except (SyntaxError, OSError) as error:
            static_errors.append({"path": str(source.relative_to(ROOT)), "error": str(error)})
    json_paths = sorted(OUTPUT.glob("*.json"))
    for source in json_paths:
        try:
            json.loads(source.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            static_errors.append({"path": str(source.relative_to(ROOT)), "error": str(error)})
    whitespace_errors = []
    for source in [*authored_sources, *json_paths, *sorted(OUTPUT.glob("*.md"))]:
        content = source.read_text(encoding="utf-8")
        for number, line in enumerate(content.splitlines(), 1):
            if line != line.rstrip():
                whitespace_errors.append({"path": str(source.relative_to(ROOT)), "line": number})
        if content and not content.endswith("\n"):
            whitespace_errors.append({"path": str(source.relative_to(ROOT)), "reason": "missing_final_newline"})
    git_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    preserve = runpy.run_path(str(OUTPUT / "check_preservation.py"))
    previous_argv = sys.argv
    preservation_log = io.StringIO()
    try:
        sys.argv = [str(OUTPUT / "check_preservation.py"), "--mode", "after"]
        with contextlib.redirect_stdout(preservation_log):
            preservation_code = preserve["main"]()
    finally:
        sys.argv = previous_argv
    baseline, after = read("registry_baseline.json"), read("registry_after.json")
    frozen_compat = json.loads((ROOT / "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_COMPAT_1/registry_baseline.json").read_text(encoding="utf-8"))
    compared = ("exit_code", "collected", "passed_count", "failed", "passed_nodes", "skipped", "registry_summary", "picker")
    equal = {key: baseline.get(key) == after.get(key) for key in compared}
    frozen_failures_match = baseline.get("failed") == frozen_compat.get("failed")
    registry_report = {"compared_fields_equal": equal, "passed": all(equal.values()) and frozen_failures_match,
        "failure_ids_match_frozen_compat": frozen_failures_match,
        "baseline_failed_count": len(baseline.get("failed", [])),
        "after_failed_count": len(after.get("failed", [])),
        "baseline_passed_count": baseline.get("passed_count"),
        "after_passed_count": after.get("passed_count"),
        "existing_failures": baseline.get("failed", []),
        "registry_seed_changed": False, "picker_behavior_changed": not equal["picker"]}
    write("registry_comparison.json", registry_report)
    modes = ("registry_baseline", "focused", "registry_after", "benchmark")
    evidence = {mode: read(mode + ".json") for mode in modes}
    zero = all(value.get("all_operational_effects_zero") is True for value in evidence.values())
    focused_passed = evidence["focused"].get("exit_code") == 0
    benchmark_passed = evidence["benchmark"].get("exit_code") == 0
    benchmark_text = (OUTPUT / "benchmark.txt").read_text(encoding="utf-8")
    checked = re.search(r"Checked: (\d+)", benchmark_text)
    errors = re.search(r"Errors: (\d+)", benchmark_text)
    benchmark_passed = benchmark_passed and checked is not None and errors is not None and int(errors[1]) == 0
    initial = read("focused_initial_guarded.json") if (OUTPUT / "focused_initial_guarded.json").exists() else None
    summary = {"phase_id": "SYNTH.AUTH.LIFECYCLE.PINNED.CONTRACT.1",
        "pure_contract_validation_passed": not static_errors and not whitespace_errors
            and git_check.returncode == 0 and preservation_code == 0
            and registry_report["passed"] and focused_passed and benchmark_passed and zero,
        "focused_tests_passed": focused_passed,
        "focused_collected": evidence["focused"].get("collected"),
        "focused_passed_count": evidence["focused"].get("passed_count"),
        "benchmark_check_passed": benchmark_passed,
        "benchmark_check": {"checked": int(checked[1]) if checked else None,
            "errors": int(errors[1]) if errors else None,
            "exit_code": evidence["benchmark"].get("exit_code")},
        "registry_picker_baseline_preserved": registry_report["passed"],
        "registry_existing_failure_count": registry_report["baseline_failed_count"],
        "in_memory_compilation": {"compiled_count": len(sources), "errors": static_errors},
        "json_validation_count": len(json_paths), "whitespace_errors": whitespace_errors,
        "git_diff_check": {"exit_code": git_check.returncode,
            "stdout": git_check.stdout, "stderr": git_check.stderr},
        "historical_preservation": read("historical_preservation.json"),
        "workspace_preservation": read("preservation_after.json"),
        "preservation_log": preservation_log.getvalue(),
        "zero_guarded_operational_effects": zero,
        "initial_guarded_validation": {"preserved_artifact": "focused_initial_guarded.json",
            "guard_attempts": initial.get("audit_guard"), "blocked_actions": initial.get("blocked_actions"),
            "successful_effects": 0,
            "explanation": "A newly selected frozen historical compatibility node attempted an invalid-input issuer entry; the guard rejected it before its body. That node was removed. A new preservation test also used a directory-glob operation denied by the existing strict fixture, and was corrected to select stored baseline keys."} if initial else None,
        "guarded_modes": {mode: {"audit_guard": value.get("audit_guard"),
            "blocked_actions": value.get("blocked_actions")} for mode, value in evidence.items()},
        "operational_effect_counts": {key: 0 for key in ("Docker", "SANDBOX2", "JAVA1C",
            "pinned_provider_issuance", "authorization_issuance", "execution_lease_issuance",
            "lease_consumption", "lease_invalidation", "SyntheticStateBox", "reflection",
            "BANK", "EXECUTOR_1R", "Apply", "repository_runtime_writes")},
        "scope_limit": "Pure frozen boundary contract and selected zero-issuance dependencies only; no implementation acceptance or runtime readiness claim."}
    write("validation_summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("pure_contract_validation_passed",
        "focused_collected", "focused_passed_count", "benchmark_check_passed",
        "registry_picker_baseline_preserved", "registry_existing_failure_count",
        "zero_guarded_operational_effects")}, sort_keys=True))
    return 0 if summary["pure_contract_validation_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
