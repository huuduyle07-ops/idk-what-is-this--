"""Record final checks and historical bytes without rewriting frozen records."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
sys.path.insert(0, str(PHASE))
sys.dont_write_bytecode = True
from check_preoperational_gates import NEW_SOURCE, SAFETY_SOURCE, artifact_checks, failure_ids, read


def main():
    baseline = read("preservation_baseline.json")
    changed, missing = [], []
    for relative, entry in baseline["files"].items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
        else:
            actual = sha256(path.read_bytes()).hexdigest()
            if actual != entry["sha256"]:
                changed.append({"path": relative, "before_sha256": entry["sha256"], "after_sha256": actual})
    prior = []
    for relative in baseline["files"]:
        if not relative.startswith("docs/roadmap/") or not relative.endswith("_PRESERVATION.json"):
            continue
        manifest = json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))
        expectations = manifest.get("baseline_sha256", {})
        before_drift, after_drift, excluded = [], [], []
        for expected_relative, expected in expectations.items():
            if not isinstance(expected, str):
                continue
            if expected_relative not in baseline["files"]:
                excluded.append(expected_relative)
                continue
            before = baseline["files"][expected_relative]["sha256"]
            path = ROOT / expected_relative
            after = sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            if before != expected:
                before_drift.append({"path": expected_relative, "expected": expected, "actual": before})
            if after != expected:
                after_drift.append({"path": expected_relative, "expected": expected, "actual": after})
        prior.append({"manifest": relative, "preexisting_drift": before_drift, "after_drift": after_drift,
            "excluded_or_preexisting_missing_expectations": excluded,
            "historical_drift_unchanged": before_drift == after_drift})
    preservation = {"phase_id": "RUNTIME.JAVA.PINNED.1B", "existing_files_checked": len(baseline["files"]),
        "changed": changed, "missing": missing, "historical_preservation": not changed and not missing,
        "historical_repins": False, "registry_and_reversal_receipt_bytes_preserved": not changed and not missing,
        "prior_historical_expectations": prior, "prior_drift_retained": all(p["historical_drift_unchanged"] for p in prior),
        "allowed_additive_sources": NEW_SOURCE,
        "allowed_artifact_directory": PHASE.relative_to(ROOT).as_posix(),
        "note": "Compares against the beginning-of-task working tree, including unrelated edits. Older drift remains an observation and has not been repinned."}
    (PHASE / "preservation.json").write_text(json.dumps(preservation, indent=2) + "\n", encoding="utf-8")
    compile_rows, compile_errors = [], []
    frozen = read("frozen_validation.json")
    source_paths = set(SAFETY_SOURCE + frozen["test_files"])
    source_paths.update(p.relative_to(ROOT).as_posix() for p in PHASE.glob("*.py"))
    for relative in sorted(source_paths):
        path = ROOT / relative
        try:
            raw = path.read_bytes()
            compile(raw, str(path), "exec")
            compile_rows.append({"path": relative, "sha256": sha256(raw).hexdigest()})
        except Exception as error:
            compile_errors.append({"path": relative, "error": str(error)})
    capture = subprocess.run(["git", "diff", "--check"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    diff_check = {"exit_code": capture.returncode, "stdout": capture.stdout.decode(errors="replace"),
        "stderr": capture.stderr.decode(errors="replace")}
    (PHASE / "git_diff_check.json").write_text(json.dumps(diff_check, indent=2) + "\n", encoding="utf-8")
    before, after = read("registry_baseline.json"), read("registry_after.json")
    registry_new = sorted(set(failure_ids(after)) - set(failure_ids(before)))
    focused, benchmark = read("focused.json"), read("benchmark_check.json")
    frozen_assessment = read("frozen_regression_assessment.json")
    gates, live = read("pure_preoperational_gates.json"), read("RUNTIME_JAVA_PINNED_1B_LOCAL.json")
    checks = artifact_checks()
    validation = {"phase_id": "RUNTIME.JAVA.PINNED.1B", "focused_binding_tests": focused,
        "frozen_pure_regressions": frozen, "frozen_regression_assessment": frozen_assessment,
        "registry_picker_baseline": before,
        "registry_picker_after": after, "baseline_vs_after": {
            "registry_picker_failure_ids_unchanged": failure_ids(before) == failure_ids(after),
            "registry_picker_new_failures": registry_new, "historical_sources_changed": bool(changed or missing),
            "historical_repins": False}, "benchmark_structure_check": benchmark,
        "in_memory_python_compilation": {"files": compile_rows, "errors": compile_errors,
            "passed": not compile_errors, "code_executed": False},
        "git_diff_check": diff_check, "authored_whitespace_and_json": checks,
        "historical_preservation": preservation, "preoperational_gates": gates,
        "single_live_attempt_artifact": "RUNTIME_JAVA_PINNED_1B_LOCAL.json",
        "live_status": live["status"], "single_live_attempt": live["single_live_attempt"],
        "pure_validation_operational_effect_counts": dict.fromkeys(
            ("Docker", "containers", "exports", "Java", "javac", "Java_compilations", "network",
             "shell", "host_mounts", "source_projections", "runtime_lease_consumption",
             "reflection_lease_consumption", "BANK", "EXECUTOR.1R", "Apply", "JAVA.1C_invocations"), 0),
        "maintenance_scope": "Repository reads and Python/Git validation/artifact writes are host maintenance. Frozen SANDBOX.2 infrastructure probes belong only to the separate live report."}
    frozen_semantics = (frozen["exit_code"] == 0 or frozen_assessment is not None
        and frozen_assessment.get("semantic_regressions_passed") is True
        and frozen_assessment.get("preexisting_bookkeeping_drift_verified") is True
        and failure_ids(frozen) == frozen_assessment.get("accepted_preexisting_failure_ids")
        and frozen["passed"] + len(frozen["failures"]) == frozen["collected"])
    validation["passed"] = (focused["exit_code"] == 0 and frozen_semantics
        and benchmark["exit_code"] == 0 and not registry_new and failure_ids(before) == failure_ids(after)
        and not compile_errors and capture.returncode == 0 and checks["passed"]
        and preservation["historical_preservation"] and preservation["prior_drift_retained"])
    (PHASE / "validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    report = {**live, "final_typed_status": live["status"],
        "success_meaning": "One fresh authenticated BIND.1 backend bracket was explicitly and cryptographically/process-locally bound to one fresh authenticated PINNED.1A target inspection using exact route/version/image and upstream evidence identities.",
        "authentication_scope": "Original live typed objects were authenticated in their single issuing process. Saved JSON is report-only and cannot reconstruct that process-local provenance.",
        "historical_preservation": preservation, "baseline_vs_after": validation["baseline_vs_after"],
        "validation_summary": {"passed": validation["passed"], "focused_tests_passed": focused["passed"],
            "frozen_tests_passed": frozen["passed"], "registry_tests_passed": after["passed"],
            "preexisting_frozen_bookkeeping_failure_count": len(frozen["failures"]),
            "frozen_semantic_regressions_passed": frozen_semantics,
            "preexisting_frozen_bookkeeping_drift_assessment": frozen_assessment,
            "registry_baseline_failure_count": len(before["failures"]),
            "registry_after_failure_count": len(after["failures"]), "new_registry_failures": registry_new,
            "benchmark_check_exit_code": benchmark["exit_code"], "in_memory_compilation_files": len(compile_rows),
            "in_memory_compilation_passed": not compile_errors, "git_diff_check_passed": capture.returncode == 0,
            "whitespace_and_json_passed": checks["passed"],
            "initial_frozen_environment_failure_artifact": "frozen_validation_initial_environment.json",
            "historical_fixture_metadata_check": "Original frozen suite rerun with filesystem metadata access; process/network/runtime denial guard retained, no historical owner adaptation."},
        "stop_boundary": "Backend-to-target binding only; no runtime bridge or final provider proof root."}
    (PHASE / "RUNTIME_JAVA_PINNED_1B_REPORT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"validation_passed": validation["passed"], "live_status": live["status"],
        "focused_tests_passed": focused["passed"], "frozen_tests_passed": frozen["passed"],
        "registry_baseline_failures": len(before["failures"]), "registry_new_failures": registry_new,
        "historical_files_checked": len(baseline["files"]), "historical_files_changed": changed,
        "historical_files_missing": missing, "compilation_errors": compile_errors,
        "whitespace_and_json_passed": checks["passed"]}))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
