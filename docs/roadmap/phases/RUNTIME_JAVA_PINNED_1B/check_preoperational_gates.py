"""Pure source-bound gates before the one authorized 1B live attempt."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
NEW_SOURCE = ["core/runtime_java_pinned_backend_target_binding.py",
    "scripts/replay_runtime_java_pinned1b.py",
    "tests/test_runtime_java_pinned_backend_target_binding.py"]
SAFETY_SOURCE = NEW_SOURCE + ["core/runtime_java_pinned_requirement.py",
    "core/runtime_java_pinned_target_inspection.py", "core/runtime_java_pinned_target_archive.py",
    "core/sandbox_backend_binding.py", "core/thread_compatible_runtime_sandbox.py",
    "core/thread_compatible_runtime_sandbox_probe.py", "core/candidate_runtime_sandbox.py",
    "core/sandboxed_java_capture_recovery.py", "core/sandboxed_java_positive_probe.py",
    "core/sandboxed_java_toolchain_discovery.py"]


def read(name):
    path = PHASE / name
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None


def failure_ids(report):
    return sorted(row["nodeid"] for row in report.get("failures", [])) if report else None


def artifact_checks():
    issues, json_errors = [], []
    paths = [ROOT / relative for relative in NEW_SOURCE]
    paths += [p for p in PHASE.iterdir() if p.is_file() and p.suffix in {".py", ".md", ".json"}]
    for path in paths:
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            issues.append({"path": path.relative_to(ROOT).as_posix(), "issue": "missing_final_newline"})
        for number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
            if line.rstrip(" \t") != line:
                issues.append({"path": path.relative_to(ROOT).as_posix(), "line": number,
                    "issue": "trailing_whitespace"})
        if path.suffix == ".json":
            try:
                json.loads(raw.decode("utf-8-sig"))
            except ValueError as error:
                json_errors.append({"path": str(path), "error": str(error)})
    return {"files_checked": len(paths), "whitespace_issues": issues, "json_errors": json_errors,
        "passed": not issues and not json_errors}


def main():
    compilation, errors = [], []
    sources = SAFETY_SOURCE + [p.relative_to(ROOT).as_posix() for p in PHASE.glob("*.py")]
    for relative in sorted(set(sources)):
        path = ROOT / relative
        try:
            raw = path.read_bytes()
            compile(raw, str(path), "exec")
            compilation.append({"path": relative, "sha256": sha256(raw).hexdigest(),
                "size_bytes": len(raw)})
        except Exception as error:
            errors.append({"path": relative, "error": str(error)})
    baseline = read("preservation_baseline.json")
    changed, missing = [], []
    for relative, entry in baseline["files"].items():
        path = ROOT / relative
        expected = entry["sha256"] if isinstance(entry, dict) else entry
        if not path.is_file():
            missing.append(relative)
        elif sha256(path.read_bytes()).hexdigest() != expected:
            changed.append(relative)
    focused, frozen = read("focused.json"), read("frozen_validation.json")
    frozen_assessment = read("frozen_regression_assessment.json")
    registry_before, registry_after = read("registry_baseline.json"), read("registry_after.json")
    benchmark = read("benchmark_check.json")
    artifacts = artifact_checks()
    capture = subprocess.run(["git", "diff", "--check"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    diff_check = {"exit_code": capture.returncode,
        "stdout": capture.stdout.decode(errors="replace"), "stderr": capture.stderr.decode(errors="replace")}
    (PHASE / "git_diff_check.json").write_text(json.dumps(diff_check, indent=2) + "\n", encoding="utf-8")
    checks = {
        "focused_binding_tests_passed": focused is not None and focused["exit_code"] == 0,
        "frozen_semantic_regressions_passed": frozen is not None and (
            frozen["exit_code"] == 0 or frozen_assessment is not None
            and frozen_assessment.get("semantic_regressions_passed") is True
            and frozen_assessment.get("preexisting_bookkeeping_drift_verified") is True
            and failure_ids(frozen) == frozen_assessment.get("accepted_preexisting_failure_ids")
            and frozen["passed"] + len(frozen["failures"]) == frozen["collected"]),
        "benchmark_structure_check_passed": benchmark is not None and benchmark["exit_code"] == 0,
        "registry_picker_has_no_new_failures": registry_before is not None and registry_after is not None
            and failure_ids(registry_before) == failure_ids(registry_after),
        "safety_code_compiles_in_memory": not errors,
        "authored_whitespace_and_json_passed": artifacts["passed"],
        "git_diff_check_passed": diff_check["exit_code"] == 0,
        "historical_bytes_preserved": not changed and not missing,
    }
    result = {"phase_id": "RUNTIME.JAVA.PINNED.1B", "pure_gates_ready": all(checks.values()),
        "checks": checks, "focused_tests_passed": focused.get("passed") if focused else None,
        "frozen_tests_passed": frozen.get("passed") if frozen else None,
        "in_memory_compilation": {"files": compilation, "errors": errors, "code_executed": False},
        "artifact_checks": artifacts, "historical_files_checked": len(baseline["files"]),
        "historical_files_changed": changed, "historical_files_missing": missing,
        "frozen_regression_assessment": frozen_assessment,
        "operational_calls_performed_by_this_gate": 0,
        "maintenance_effect_note": "Git whitespace checks and Python validation are host maintenance; no upstream owner is invoked here."}
    (PHASE / "pure_preoperational_gates.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pure_gates_ready": result["pure_gates_ready"], "checks": checks,
        "focused_tests_passed": result["focused_tests_passed"], "frozen_tests_passed": result["frozen_tests_passed"]}))
    return 0 if result["pure_gates_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
