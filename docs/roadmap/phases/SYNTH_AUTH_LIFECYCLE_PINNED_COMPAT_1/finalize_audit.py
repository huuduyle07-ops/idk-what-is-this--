"""Read-only checks plus new audit artifacts; never imports a runtime owner."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TEST = "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py"


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def write(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    baseline = read("preservation_baseline.json")
    drift = []
    for name, expected in baseline["files"].items():
        path = ROOT / name
        if not path.is_file():
            drift.append({"path": name, "reason": "missing"})
            continue
        data = path.read_bytes()
        if sha256(data).hexdigest() != expected["sha256"] or len(data) != expected["size_bytes"]:
            drift.append({"path": name, "reason": "byte_identity_changed"})
    listing = subprocess.run(["git", "ls-files", "-c", "-o", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True)
    current = {name for name in listing.stdout.splitlines() if (ROOT / name).is_file()
        and not any(part.startswith("tmp_tests") or part in {".git", "__pycache__", ".pytest_cache"}
            for part in Path(name).parts)}
    new = sorted(current - set(baseline["files"]))
    phase_prefix = HERE.relative_to(ROOT).as_posix() + "/"
    unexpected = [name for name in new if name != TEST and not name.startswith(phase_prefix)]
    before, after = read("registry_baseline.json"), read("registry_after.json")
    comparison_keys = ("collected", "passed_count", "failed", "skipped", "registry_summary", "picker")
    changed_registry_keys = [key for key in comparison_keys if before[key] != after[key]]
    prior = json.loads((ROOT / "docs/roadmap/phases/SYNTH_AUTH_PINNED_1R/pure_validation_summary.json").read_text(encoding="utf-8"))
    prior_failure_ids = sorted(prior["registry_picker_test_baseline"]["failure_ids"], key=lambda row: (row["nodeid"], row["when"]))
    focused, benchmark = read("focused.json"), read("benchmark.json")
    benchmark_text = (HERE / "benchmark.txt").read_text(encoding="utf-8")
    checked_match = re.search(r"Checked: (\d+)", benchmark_text)
    errors_match = re.search(r"Errors: (\d+)", benchmark_text)
    assert checked_match and errors_match, "actual benchmark summary required"
    benchmark_checked, benchmark_errors = int(checked_match[1]), int(errors_match[1])
    final_guard_attempts = {name: row["audit_guard"] for name, row in
        (("focused", focused), ("benchmark", benchmark), ("registry_baseline", before), ("registry_after", after))}
    compilation_errors = []
    compilation_paths = sorted({name for name in current | set(baseline["files"]) if name.endswith(".py")})
    for name in compilation_paths:
        try:
            compile((ROOT / name).read_bytes(), str(ROOT / name), "exec")
        except Exception as error:
            compilation_errors.append({"path": name, "error": str(error)})
    artifact_errors = []
    artifact_paths = sorted([ROOT / TEST, *HERE.rglob("*")])
    json_count, whitespace_count = 0, 0
    for path in artifact_paths:
        if not path.is_file() or path.suffix not in {".py", ".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            json_count += 1
            try:
                json.loads(text)
            except ValueError as error:
                artifact_errors.append({"path": str(path), "error": str(error)})
        whitespace_count += 1
        for number, line in enumerate(text.splitlines(), 1):
            if line != line.rstrip():
                artifact_errors.append({"path": str(path), "line": number, "error": "trailing_whitespace"})
        if text and not text.endswith("\n"):
            artifact_errors.append({"path": str(path), "error": "missing_final_newline"})
    git_check = subprocess.run(["git", "-c", "core.safecrlf=false", "diff", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    write("git_diff_check.json", {"exit_code": git_check.returncode,
        "stdout": git_check.stdout, "stderr": git_check.stderr})
    historical = read("historical_preservation.json")
    preservation = {"baseline_file_count": len(baseline["files"]), "drift": drift,
        "unexpected_new_files": unexpected, "authorized_new_files": new,
        "existing_lifecycle_source_changed": any(row["path"] == "core/synthetic_runtime_authorization_lifecycle.py" for row in drift),
        "pinned_auth_source_changed": any(row["path"] == "core/synthetic_runtime_authorization_pinned.py" for row in drift),
        "repinned_drift": False, "passed": not drift and not unexpected}
    write("preservation_after.json", preservation)
    validation = {"phase_id": "SYNTH.AUTH.LIFECYCLE.PINNED.COMPAT.1",
        "focused": {"collected": focused["collected"], "passed": focused["passed_count"],
            "failed": focused["failed"], "suite_counts": dict(Counter(node.split("::")[0] for node in focused["passed_nodes"]))},
        "full_frozen_suites_run": False,
        "reflection_validation": "frozen source/test dependency inspection plus new AST and inert validator rejection tests; no issuance-dependent frozen test run",
        "registry_picker": {"before_passed": before["passed_count"], "after_passed": after["passed_count"],
            "collected": before["collected"], "failure_ids": before["failed"],
            "changed_comparison_keys": changed_registry_keys,
            "failure_ids_match_frozen_1r": before["failed"] == prior_failure_ids},
        "benchmark_check": {"exit_code": benchmark["exit_code"], "checked": benchmark_checked, "errors": benchmark_errors},
        "in_memory_compilation": {"file_count": len(compilation_paths), "errors": compilation_errors},
        "artifact_checks": {"json_count": json_count, "whitespace_file_count": whitespace_count, "errors": artifact_errors},
        "git_diff_check_exit_code": git_check.returncode,
        "final_worker_guard_attempts": final_guard_attempts,
        "historical_preservation_passed": historical["historical_preservation_verified"],
        "current_workspace_preservation": preservation,
        "initial_bootstrap_denials": {"shell_metadata_fallback": 1, "socket_availability_probe": 1, "existing_directory_mkdir": 4,
            "successful_effects": 0},
        "frozen_fixture_note": "pinned signature fixture reversibly replaces unused provider entrypoints and virtual transports and isolates empty registries; no public validator patched or handle registered"}
    validation["passed"] = (focused["exit_code"] == 0 and benchmark["exit_code"] == 0 and benchmark_errors == 0
        and not changed_registry_keys and before["failed"] == prior_failure_ids
        and not compilation_errors and not artifact_errors and git_check.returncode == 0
        and preservation["passed"] and historical["historical_preservation_verified"]
        and all(all(value == 0 for value in guards.values()) for guards in final_guard_attempts.values()))
    write("validation_summary.json", validation)
    effects = dict.fromkeys(("Docker", "provider_infrastructure", "provider_issuance", "JAVA1C", "SANDBOX2_issuance",
        "PINNED1A_export", "authorization_issuance", "live_authorization_attempts", "execution_lease_issuance",
        "execution_lease_consumption", "execution_lease_invalidation", "SyntheticStateBox", "reflection",
        "BANK", "EXECUTOR_1R", "Apply", "repository_runtime_writes"), 0)
    report = {"phase_id": validation["phase_id"], "result": "LIFECYCLE_PINNED_REQUIRES_ADDITIVE_ADAPTER",
        "audit_only": True, "stop_after_compatibility_conclusion": True,
        "lifecycle": {"owner": "core.synthetic_runtime_authorization_lifecycle", "phase": "SYNTH.AUTH.LIFECYCLE.1", "schema": "synthetic_runtime_execution_lease_v1"},
        "old_authorization": {"owner": "core.synthetic_runtime_authorization", "phase": "SYNTH.AUTH.1", "schema": "synthetic_runtime_authorization_v1"},
        "pinned_authorization": {"owner": "core.synthetic_runtime_authorization_pinned", "phase": "SYNTH.AUTH.PINNED.1", "schema": "synthetic_runtime_authorization_pinned_1_v1"},
        "scenario_identity_equal": True, "authorization_epoch_equal": False, "authentication_domain_equal": False,
        "provider_requirement_equal": False, "old_provider_requirement": ["RUNTIME.JAVA.1", "runtime_java_1_v1"],
        "pinned_provider_requirement": ["RUNTIME.JAVA.PINNED.1", "runtime_java_pinned_1_v1"],
        "pinned_provider_proof": ["RUNTIME.JAVA.PINNED.1C", "runtime_java_pinned_provider_1c_v1"],
        "lifecycle_independently_checks_provider": False, "old_provider_dependency": "transitive old-auth validation plus preserved JAVA.1 future activation policy",
        "state_machine_semantics_reusable": True, "implementation_api_reusable": False,
        "reflection_compatibility_claimed": False, "lease_shape_for_future_owner_decided": False,
        "existing_lifecycle_source_changed": preservation["existing_lifecycle_source_changed"],
        "pinned_auth_source_changed": preservation["pinned_auth_source_changed"],
        "execution_lease_issued": False, "operational_effects": effects,
        "public_validators_weakened": False, "live_registry_seeded": False, "adapter_implemented": False,
        "consumer_classification_artifact": "lifecycle_trace.md", "exact_comparison_artifact": "authorization_comparison.md",
        "reflection_dependency_artifact": "reflection_dependencies.md", "validation_artifact": "validation_summary.json",
        "historical_preservation_artifact": "historical_preservation.json",
        "recommended_next_slice": "Define truthful additive pinned authorization-to-lease owner binding; preserve frozen owners, one-shot semantics and history; separately audit reflection acceptance before any execution.",
        "validation_passed_with_preserved_baseline_failures": validation["passed"]}
    write("SYNTH_AUTH_LIFECYCLE_PINNED_COMPAT_1_REPORT.json", report)
    print(json.dumps({"outcome": report["result"], "passed": validation["passed"], "preserved_files": len(baseline["files"]),
        "compiled_files": len(compilation_paths), "focused_passed": focused["passed_count"],
        "new_failures": changed_registry_keys, "drift": drift, "unexpected_new_files": unexpected,
        "compilation_errors": compilation_errors, "artifact_errors": artifact_errors}, indent=2))
    assert validation["passed"]


if __name__ == "__main__":
    main()
