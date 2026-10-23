"""Static/source checks and final evidence aggregation; imports no owners."""
from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
NEW_TEST = ROOT / "tests/test_synthetic_reflection_pinned_contract.py"


def write_json(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def tree(name):
    return ast.parse((ROOT / "core" / (name + ".py")).read_text(encoding="utf-8"))


def function(module, name):
    return next(node for node in tree(module).body if isinstance(node, ast.FunctionDef) and node.name == name)


def calls(node):
    return {ast.unparse(item.func) for item in ast.walk(node) if isinstance(item, ast.Call)}


def source_checks():
    passed, failed = [], []

    def check(name, condition):
        (passed if condition else failed).append(name)

    primitive = "synthetic_read_only_reflection"
    admission = "synthetic_reflection_execution_admission"
    lifecycle = "synthetic_reflection_execution_lifecycle"
    pinned = "synthetic_runtime_authorization_pinned_lifecycle"
    request = next(node for node in tree(primitive).body if isinstance(node, ast.ClassDef)
        and node.name == "SyntheticReflectionRequest")
    fields = {node.target.id for node in request.body if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)}
    identity_fields = {name for name in fields if name not in {
        "runtime_authority", "real_task_runtime_authority"}}
    check("old_request_payload_has_no_upstream_authorization_or_runtime_identity",
        fields and not any("authorization" in name or "runtime" in name or "provider" in name
            for name in identity_fields))
    check("old_renderer_authenticates_only_independent_original_request",
        calls(function(primitive, "render_synthetic_read_only_reflection")) == {"validate_synthetic_reflection_request"})
    check("old_auth_compatibility_keeps_unchanged_public_old_auth_validator",
        "authorization_owner.validate_synthetic_runtime_authorization" in
        calls(function(primitive, "synthetic_reflection_satisfies_authorization")))
    check("old_admission_authenticates_old_auth_and_original_request_publicly",
        {"authorization_owner.validate_synthetic_runtime_authorization",
        "reflection_owner.validate_synthetic_reflection_request"} <= calls(function(admission, "_validate_upstream_pair")))
    admission_source = (ROOT / "core" / (admission + ".py")).read_text(encoding="utf-8")
    check("old_admission_has_no_pinned_or_runtime_or_provider_bridge",
        not any(value in admission_source for value in ("synthetic_runtime_authorization_pinned",
            "synthetic_runtime_authorization_lifecycle", "runtime_java")))
    pair = ast.unparse(function(admission, "_validate_upstream_pair"))
    check("old_admission_scope_preserves_invocation_observation_role_and_read_operation",
        all(value in pair for value in ("invocation.arguments", "observation.roles", "request.observation_role", "request.operation")))
    auth_record = ast.unparse(function(lifecycle, "_authenticated_record_locked"))
    check("old_reflection_original_record_and_signed_terminal_state_authentication",
        all(value in auth_record for value in ("record.lease_ref() is not lease", "_authenticate_inputs(",
            "record.lifecycle_state not in (ISSUED, CONSUMED, INVALIDATED)", "hmac.compare_digest")))
    transition = ast.unparse(function(lifecycle, "_transition"))
    check("old_reflection_consumption_requires_consumed_runtime_but_invalidation_does_not",
        "if target == CONSUMED:" in transition and "_runtime_state(runtime, authorization, CONSUMED)" in transition
        and "target not in (CONSUMED, INVALIDATED)" in transition and "record.lifecycle_state != ISSUED" in transition)
    issue = ast.unparse(function(lifecycle, "issue_synthetic_reflection_execution_lease"))
    check("old_reflection_permanent_one_admission_one_lease_tombstones",
        "admission.admission_id in _ADMISSION_LEASES" in issue and
        "_ADMISSION_LEASES[admission.admission_id] = lease_id" in issue)
    readiness = ast.unparse(function(pinned, "check_pinned_synthetic_runtime_execution_lease_preconditions"))
    check("pinned_runtime_keeps_false_behavioral_readiness_and_unresolved_consumer",
        "record.lifecycle_state == ISSUED, False" in readiness and
        "PROOF_UNRESOLVED" in ast.unparse(function(pinned, "_consumer_readiness")))
    result = {"passed": passed, "failed": failed, "passed_count": len(passed),
        "owner_modules_imported": False, "capability_objects_constructed": False,
        "operational_effects_zero": True, "success": not failed}
    write_json("frozen_source_checks.json", result)
    return result


def final_report_checks():
    report_path = OUTPUT / "SYNTH_REFLECT_PINNED_CONTRACT_1_REPORT.json"
    if not report_path.exists():
        return None
    report, summary, contract = read(report_path.name), read("validation_summary.json"), read("contract.json")
    focused, frozen = read("focused.json"), read("frozen.json")
    measured_hashes = {
        "contract_json": sha256((OUTPUT / "contract.json").read_bytes()).hexdigest(),
        "new_source_test": sha256(NEW_TEST.read_bytes()).hexdigest(),
        "validation_harness": sha256((OUTPUT / "validate_pure_contract.py").read_bytes()).hexdigest(),
    }
    expected_summary_hashes = {
        "contract.json": measured_hashes["contract_json"],
        "test_synthetic_reflection_pinned_contract.py": measured_hashes["new_source_test"],
        "validate_pure_contract.py": measured_hashes["validation_harness"],
    }
    measured_checks = {
        "completion_status_matches_contract": report["status"] == contract["completion_marker"],
        "readiness_remains_fail_closed": report["behavioral_activation_ready"] is False
            and report["behavioral_readiness_reason"] == "PROOF_UNRESOLVED"
            and report["compilation_authority"] is False,
        "all_declared_operational_effects_zero": all(type(value) is int and value == 0
            for value in report["operational_effects"].values()),
        "no_implementation_or_capability_effect": all(report[key] is False for key in (
            "adapter_implemented", "admission_owner_implemented", "reflection_lifecycle_owner_implemented",
            "runtime_consumer_implemented", "executor_implemented", "capabilities_issued",
            "capabilities_consumed", "capabilities_invalidated", "reflection_performed")),
        "focused_counts_match_measurement": report["validation"]["new_contract_AST_JSON_tests"] == {
            "collected": focused["collected"], "passed": focused["passed_count"],
            "failed": len(focused["failed"]), "warning_free": "warning" not in
                (OUTPUT / "focused.txt").read_text(encoding="utf-8").lower()},
        "frozen_counts_match_measurement": report["validation"]["frozen_source_AST_regression_selection"]["passed"]
            == frozen["passed_count"] == summary["frozen"]["passed"],
        "independent_source_counts_match": report["validation"]["independent_frozen_source_checks"]["passed"]
            == summary["frozen_source_checks"]["passed_count"],
        "benchmark_counts_match_measurement": report["validation"]["benchmark_check"]["cases"]
            == summary["benchmark_cases_checked"] and report["validation"]["benchmark_check"]["errors"]
            == summary["benchmark_errors"] == 0,
        "registry_baseline_and_after_match": all(report["validation"]["registry_picker"][mode] == {
            "collected": summary["registry_picker"][mode + "_collected"],
            "passed": summary["registry_picker"][mode + "_passed"],
            "failed": len(summary["registry_picker"][mode + "_failed"])} for mode in ("baseline", "after")),
        "historical_counts_match": report["validation"]["historical_preservation"]["baseline_preexisting_file_count"]
            == summary["historical_preservation"]["baseline_file_count"] and
            summary["historical_preservation"]["changed"] == summary["historical_preservation"]["deleted"] == [],
        "hashes_match_summary_and_report": report["artifact_hashes"] == measured_hashes
            and summary["artifact_hashes"] == expected_summary_hashes,
        "denied_probe_transparency_preserved": report["validation"]["all_validation_attempts_zero"] is False
            and report["validation"]["initial_denied_dependency_probe"]["attempts"] == 1
            and report["validation"]["initial_denied_dependency_probe"]["blocked_before_effect"] is True
            and report["validation"]["all_actual_operational_effects_zero"] is True,
        "summary_validation_passed": summary["validation_passed"] is True,
    }
    result = {"checks": measured_checks, "passed": all(measured_checks.values()),
        "report_json_checked": report_path.name,
        "report_markdown_checked": "SYNTH_REFLECT_PINNED_CONTRACT_1_REPORT.md",
        "measured_artifact_hashes": measured_hashes, "owner_modules_imported": False,
        "operational_effects_zero": True}
    write_json("final_artifact_checks.json", result)
    return result


def static_validation():
    source = source_checks()
    final_artifacts = final_report_checks()
    candidates = [path for path in OUTPUT.rglob("*") if path.is_file()
        and "validation_tmp" not in path.relative_to(OUTPUT).parts]
    candidates.append(NEW_TEST)
    compiled, validated_json, compile_errors, json_errors, whitespace_errors = [], [], [], [], []
    owners = list((ROOT / "core").glob("synthetic*.py")) + [ROOT / "core" / (name + ".py") for name in (
        "behavioral_diagnostic_executor_refresh", "behavioral_diagnostic_executor_retry",
        "behavioral_diagnostic_executor_lifecycle_retry")]
    for path in candidates + owners:
        if path.suffix not in {".py", ".json", ".md", ".txt"}:
            continue
        name = path.relative_to(ROOT).as_posix()
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            try:
                compile(content, str(path), "exec")
                compiled.append(name)
            except SyntaxError as error:
                compile_errors.append({"file": name, "error": str(error)})
        if path.suffix == ".json":
            try:
                json.loads(content)
                validated_json.append(name)
            except ValueError as error:
                json_errors.append({"file": name, "error": str(error)})
        # Preserve verbatim captured tool/pytest .txt output, including its
        # native diagnostic indentation. Authored source/JSON/Markdown is clean.
        if path in candidates and path.suffix in {".py", ".json", ".md"}:
            for line, value in enumerate(content.splitlines(), 1):
                if value.rstrip() != value:
                    whitespace_errors.append({"file": name, "line": line})
    result = {"compiled_in_memory": compiled, "json_validated": validated_json,
        "in_memory_compile_errors": compile_errors, "json_errors": json_errors,
        "whitespace_errors": whitespace_errors, "bytecode_written": False,
        "whitespace_scope": "authored .py/.json/.md; captured .txt diagnostic output retained verbatim",
        "owner_modules_imported": False,
        "final_completion_report_consistent": final_artifacts["passed"] if final_artifacts else None,
        "passed": not (compile_errors or json_errors or whitespace_errors) and source["success"]
            and (final_artifacts is None or final_artifacts["passed"])}
    write_json("static_validation.json", result)
    return result


def finalize():
    static = static_validation()
    baseline, after = read("registry_baseline.json"), read("registry_after.json")
    keys = ("collected", "failed", "passed_nodes", "registry_summary", "picker")
    comparison = {"unchanged": all(baseline[key] == after[key] for key in keys),
        "baseline_collected": baseline["collected"], "after_collected": after["collected"],
        "baseline_passed": baseline["passed_count"], "after_passed": after["passed_count"],
        "baseline_failed": baseline["failed"], "after_failed": after["failed"],
        "existing_failures_preserved": baseline["failed"] == after["failed"],
        "registry_and_picker_projections_identical": all(baseline[key] == after[key] for key in ("registry_summary", "picker")),
        "old_files_not_modified_to_repair_baseline": True}
    write_json("registry_comparison.json", comparison)
    validation = {name: read(name + ".json") for name in ("frozen", "focused", "benchmark")}
    initial = read("benchmark_initial.json")
    benchmark_log = (OUTPUT / "benchmark.txt").read_text(encoding="utf-8")
    benchmark_checked = int(re.search(r"^Checked: (\d+)$", benchmark_log, re.MULTILINE).group(1))
    benchmark_errors = int(re.search(r"^Errors: (\d+)$", benchmark_log, re.MULTILINE).group(1))
    preservation = read("preservation_comparison.json")
    diff = read("git_diff_check.json")
    final_guards = [baseline, after, *validation.values()]
    all_final_attempts_zero = all(item["all_operational_effects_zero"] and
        not item["imported_capability_owners"] for item in final_guards)
    denied_probe_only = initial["blocked_actions"] == ["socket.bind"] and initial["audit_guard"] == {
        "process_attempts": 0, "network_attempts": 1, "repository_runtime_write_attempts": 0,
        "capability_owner_import_attempts": 0, "capability_or_transition_attempts": 0,
        "execution_or_verification_attempts": 0}
    summary = {"phase_id": "SYNTH.REFLECT.PINNED.CONTRACT.1",
        "historical_preservation": preservation, "registry_picker": comparison,
        "static_validation_passed": static["passed"], "git_diff_check": diff,
        "all_final_guarded_runs_zero_attempts": all_final_attempts_zero,
        "all_actual_operational_effects_zero": all_final_attempts_zero and denied_probe_only,
        "all_validation_attempts_zero": False,
        "initial_denied_dependency_probe": {"event": "socket.bind", "attempts": 1,
            "blocked_by_audit_hook_before_effect": denied_probe_only,
            "reason": "urllib3 import-time IPv6 availability probe",
            "resolution": "Only socket.has_ipv6 dependency availability probe disabled for final guarded run; no capability owner or validator patched."},
        "frozen_source_checks": read("frozen_source_checks.json"),
        "full_issuance_dependent_suites_run": False,
        "owner_modules_imported": False, "capabilities_created": False,
        "benchmark_cases_checked": benchmark_checked, "benchmark_errors": benchmark_errors,
        "artifact_hashes": {path.name: sha256(path.read_bytes()).hexdigest() for path in (
            OUTPUT / "contract.json", OUTPUT / "validate_pure_contract.py", NEW_TEST)},
        "validation_passed": preservation["historical_preservation_passed"] and comparison["unchanged"]
            and static["passed"] and diff["exit_code"] == 0 and all_final_attempts_zero
            and denied_probe_only and benchmark_errors == 0
            and all(item["exit_code"] == 0 for item in validation.values())}
    for name, item in validation.items():
        summary[name] = {key: item[key] for key in ("exit_code", "audit_guard", "all_operational_effects_zero")}
        if name != "benchmark":
            summary[name].update(passed=item["passed_count"], collected=item["collected"], failed=item["failed"])
    write_json("validation_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["validation_passed"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("static", "finalize"))
    args = parser.parse_args()
    if args.mode == "finalize":
        return finalize()
    result = static_validation()
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
