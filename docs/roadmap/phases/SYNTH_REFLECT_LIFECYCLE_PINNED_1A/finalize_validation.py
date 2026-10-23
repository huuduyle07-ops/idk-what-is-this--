"""Source-only preservation, static checks, and validation summary.

Never imports capability owners or executes their validators or issuers.
"""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
OWNER = ROOT / "core/synthetic_reflection_execution_lifecycle_pinned.py"
TEST = ROOT / "tests/test_synthetic_reflection_execution_lifecycle_pinned.py"


def read(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def write(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preservation():
    baseline = read("preservation_baseline.json")["files"]
    changed, deleted = [], []
    for name, previous in baseline.items():
        path = ROOT / name
        if not path.is_file():
            deleted.append(name)
            continue
        content = path.read_bytes()
        current = {"sha256": sha256(content).hexdigest(), "bytes": len(content)}
        if current != previous:
            changed.append({"file": name, "before": previous, "after": current})
    result = {"baseline_file_count": len(baseline), "changed": changed, "deleted": deleted,
        "passed": not changed and not deleted,
        "basis": "Preimplementation workspace bytes, including existing untracked historical files and user edits"}
    write("preservation_check.json", result)
    return result


def tree(name):
    return ast.parse((ROOT / "core" / (name + ".py")).read_text(encoding="utf-8"))


def function(module, name):
    return next(node for node in tree(module).body if isinstance(node, ast.FunctionDef) and node.name == name)


def calls(node):
    return {ast.unparse(item.func) for item in ast.walk(node) if isinstance(item, ast.Call)}


def frozen_source_checks():
    checks = {}
    primitive = "synthetic_read_only_reflection"
    old_admission = "synthetic_reflection_execution_admission"
    old_lifecycle = "synthetic_reflection_execution_lifecycle"
    admission = "synthetic_reflection_execution_admission_pinned"
    runtime = "synthetic_runtime_authorization_pinned_lifecycle"
    checks["old_renderer_only_authenticates_original_request"] = calls(function(primitive,
        "render_synthetic_read_only_reflection")) == {"validate_synthetic_reflection_request"}
    checks["old_admission_uses_unchanged_public_auth_and_request_validators"] = {
        "authorization_owner.validate_synthetic_runtime_authorization",
        "reflection_owner.validate_synthetic_reflection_request"} <= calls(function(old_admission, "_validate_upstream_pair"))
    checks["old_lifecycle_keeps_original_public_epoch"] = {
        "authorization_owner.validate_synthetic_runtime_authorization",
        "runtime_owner.validate_synthetic_runtime_execution_lease"} <= calls(function(old_lifecycle, "_authenticate_inputs"))
    graph = calls(function(admission, "_authenticate_graph"))
    graph_source = ast.unparse(function(admission, "_authenticate_graph"))
    checks["pinned_admission_keeps_public_graph_authentication"] = "_public_validate" in graph and all(
        token in graph_source for token in ("reflection_owner.validate_synthetic_reflection_request",
            "authorization_owner.validate_pinned_synthetic_runtime_authorization",
            "runtime_owner.validate_pinned_synthetic_runtime_execution_lease"))
    record = ast.unparse(function(admission, "_authenticated_record_locked"))
    checks["pinned_admission_retains_original_graph_and_signed_identity"] = all(token in record for token in (
        "record.admission_ref() is not admission", "supplied is not retained", "_authenticate_graph(", "hmac.compare_digest("))
    checks["pinned_runtime_state_uses_public_exact_authorization"] = (
        "runtime_owner.pinned_synthetic_runtime_execution_lease_state" in calls(function(admission, "_runtime_state"))
        and "authorization=authorization" in ast.unparse(function(admission, "_runtime_state")))
    readiness = ast.unparse(function(runtime, "check_pinned_synthetic_runtime_execution_lease_preconditions"))
    checks["pinned_runtime_behavioral_readiness_remains_false"] = "record.lifecycle_state == ISSUED, False" in readiness
    consumer = ast.unparse(function(runtime, "_consumer_readiness"))
    checks["pinned_runtime_consumer_still_unconditionally_unresolved"] = (
        "PROOF_UNRESOLVED" in consumer and calls(function(runtime, "_consumer_readiness")) == {"_fail"})
    for module, reason in (
        ("behavioral_diagnostic_executor_refresh", "existing_synthetic_issuer_cannot_reconstruct_independent_scenario"),
        ("behavioral_diagnostic_executor_retry", "frozen_synth_auth_1_has_no_public_consumption_contract"),
        ("behavioral_diagnostic_executor_lifecycle_retry", "java_profile_contract_mismatch")):
        node = function(module, "verify")
        checks[module + "_historical_stop_preserved"] = reason in {
            item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and type(item.value) is str}
        checks[module + "_no_transition_or_executor_added"] = not any(
            "consume_" in call or "invalidate_" in call or "subprocess" in call for call in calls(node))
    result = {"checks": checks, "passed_count": sum(checks.values()), "passed": all(checks.values()),
        "owner_modules_imported": False, "capability_objects_constructed": False}
    write("frozen_source_checks.json", result)
    return result


def static_checks():
    authored = [path for path in OUTPUT.rglob("*") if path.is_file()
        and "validation_tmp" not in path.relative_to(OUTPUT).parts]
    paths = authored + [OWNER, TEST]
    paths += list((ROOT / "core").glob("synthetic*.py"))
    paths += list((ROOT / "tests").glob("test_synthetic*.py"))
    paths += [ROOT / "core" / (name + ".py") for name in (
        "behavioral_diagnostic_executor_refresh", "behavioral_diagnostic_executor_retry",
        "behavioral_diagnostic_executor_lifecycle_retry")]
    compiled, parsed, json_files, errors, whitespace = [], [], [], [], []
    for path in sorted(set(paths)):
        if path.suffix not in {".py", ".json", ".md"}:
            continue
        name = path.relative_to(ROOT).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix == ".py":
                ast.parse(content, filename=str(path))
                parsed.append(name)
                compile(content, str(path), "exec")
                compiled.append(name)
            elif path.suffix == ".json":
                json.loads(content)
                json_files.append(name)
            if path in authored or path in (OWNER, TEST):
                whitespace.extend({"file": name, "line": line} for line, text in enumerate(content.splitlines(), 1)
                    if text.rstrip() != text)
        except Exception as error:
            errors.append({"file": name, "error": type(error).__name__ + ": " + str(error)})
    result = {"compiled_in_memory": compiled, "parsed_AST": parsed, "UTF8_JSON_validated": json_files,
        "errors": errors, "whitespace_errors": whitespace, "passed": not errors and not whitespace,
        "owner_modules_imported": False, "bytecode_written": False}
    write("static_validation.json", result)
    return result


def report_consistency():
    path = OUTPUT / "SYNTH_REFLECT_LIFECYCLE_PINNED_1A_REPORT.json"
    if not path.exists():
        return None
    report = read(path.name)
    isolated = read("isolated.json")
    checks = {
        "exact_status": report["status"] == "SYNTH_REFLECT_LIFECYCLE_PINNED_1A_COMPLETE",
        "exact_phase": report["phase_id"] == "SYNTH.REFLECT.LIFECYCLE.PINNED.1",
        "exact_type": report["exact_type"] == "PinnedSyntheticReflectionExecutionLease",
        "exact_schema": report["schema_version"] == "synthetic_reflection_execution_lease_pinned_1_v1",
        "exact_domain": report["authentication_domain"] == "CATTUS:SYNTH.REFLECT.LIFECYCLE.PINNED.1:exact-reflection-lease:v1",
        "owner_hash_current": report["owner_source_sha256"] == sha256(OWNER.read_bytes()).hexdigest(),
        "isolated_counts_current": all(report["validation"]["isolated"][key] == isolated[key]
            for key in ("collected", "passed_count", "failed", "exit_code", "audit_guard")),
        "all_eight_APIs": len(report["public_APIs"]) == 8,
        "exactly_three_states": report["states"] == ["ISSUED", "CONSUMED", "INVALIDATED"],
        "readiness_unresolved": report["behavioral_activation_ready"] is False
            and report["reason"] == "PROOF_UNRESOLVED" and report["compilation_authority"] is False,
        "operational_effects_exact_zero": bool(report["operational_effects"]) and all(
            type(count) is int and count == 0 for count in report["operational_effects"].values()),
        "historical_and_operational_flags_false": all(report[name] is False for name in (
            "old_lifecycle_source_changed", "pinned_admission_source_changed",
            "operational_reflection_lease_issued", "operational_reflection_effect")),
        "no_full_suite_claim": report["validation"]["full_suite_run"] is False,
        "no_effect_evidence_claim": all(value is False for value in report["effect_evidence"].values()),
    }
    result = {"checks": checks, "passed": all(checks.values()), "owner_modules_imported": False}
    write("report_consistency.json", result)
    return result


def main():
    baseline, after = read("registry_baseline.json"), read("registry_after.json")
    keys = ("collected", "passed_nodes", "failed", "registry_summary", "picker")
    comparison = {"unchanged": all(baseline[key] == after[key] for key in keys),
        "baseline_collected": baseline["collected"], "after_collected": after["collected"],
        "baseline_passed": baseline["passed_count"], "after_passed": after["passed_count"],
        "baseline_failed": baseline["failed"], "after_failed": after["failed"],
        "registry_and_picker_projections_identical": all(baseline[key] == after[key] for key in ("registry_summary", "picker"))}
    write("registry_comparison.json", comparison)
    modes = ("registry_baseline", "registry_after", "frozen", "focused", "isolated", "benchmark")
    runs = {name: read(name + ".json") for name in modes}
    benchmark_log = (OUTPUT / "benchmark.txt").read_text(encoding="utf-8")
    result = {"phase_id": "SYNTH.REFLECT.LIFECYCLE.PINNED.1", "preservation": preservation(),
        "frozen_source_checks": frozen_source_checks(), "static": static_checks(),
        "registry_picker": comparison, "full_suite_run": False,
        "stale_contract_test_deselected": {
            "nodeid": "tests/test_synthetic_reflection_pinned_contract.py::test_contract_freezes_semantics_and_creates_no_owners_types_or_registry_entries",
            "reason": "Historical contract-freeze assertion predates additive owners; pinned admission already exists at baseline. Frozen test and contract bytes preserved."},
        "benchmark_cases_checked": int(re.search(r"^Checked: (\d+)$", benchmark_log, re.MULTILINE).group(1)),
        "benchmark_errors": int(re.search(r"^Errors: (\d+)$", benchmark_log, re.MULTILINE).group(1)),
        "runs": {name: {key: value for key, value in run.items() if key not in (
            "passed_nodes", "picker", "registry_summary", "selected_nodes")} for name, run in runs.items()},
        "git_diff_check": read("git_diff_check.json")}
    result["report_consistency"] = report_consistency()
    result["all_guarded_runs_zero_effects"] = all(run["all_operational_effects_zero"]
        and (not run["imported_capability_owners"] or name == "isolated") for name, run in runs.items())
    result["scope_passed"] = result["preservation"]["passed"] and result["static"]["passed"] \
        and result["frozen_source_checks"]["passed"] and comparison["unchanged"] \
        and result["all_guarded_runs_zero_effects"] and result["git_diff_check"]["exit_code"] == 0 \
        and all(runs[name]["exit_code"] == 0 for name in ("frozen", "focused", "isolated", "benchmark"))
    result["passed"] = result["scope_passed"] \
        and (result["report_consistency"] is None or result["report_consistency"]["passed"])
    write("validation_summary.json", result)
    print(json.dumps({"passed": result["passed"], "preserved_files": result["preservation"]["baseline_file_count"],
        "isolated_passed": runs["isolated"].get("passed_count"), "registry_unchanged": comparison["unchanged"],
        "static_errors": result["static"]["errors"], "whitespace_errors": result["static"]["whitespace_errors"]}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
