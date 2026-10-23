"""Additive retry maintenance gates; never invokes an operational owner."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
ORIGINAL = PHASE.parent / "RUNTIME_JAVA_PINNED_1C"
sys.path.insert(0, str(PHASE))
sys.dont_write_bytecode = True
from preservation import check as check_preservation

FIRST_SHA = "e1edf506c522515199a98a0ff90e1985dbfce0235854ac9978b549c5938b8bee"
CORRECTED_SHA = "bca4a46363a27e23fba60cbc556eb30e3f2b6e03f4ed6e95c81ac7231756ddaa"
DRIFT = "tests/test_patch_candidate_behavior_executor1.py::test_bookkeeping_reversal_preserves_exact_frozen_receipts"


def read(name, directory=PHASE):
    return json.loads((directory / name).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def failure_keys(result):
    return sorted((row["nodeid"], row["when"], row["outcome"]) for row in result["failures"])


def drift_identity(result):
    rows = [row for row in result["failures"] if row["nodeid"] == DRIFT and row["when"] == "call"]
    if len(rows) != 1:
        return None
    detail = rows[0]["detail"]
    assertion = next((line.strip() for line in detail.splitlines()
        if line.startswith("E       AssertionError:")), "")
    return {"nodeid": DRIFT, "when": "call", "outcome": rows[0]["outcome"],
        "assertion": assertion, "unchanged_assertion_present": bool(assertion),
        "failure_site": "tests/_runtime_sandbox1_maintenance.py:13: AssertionError"
            if "tests\\_runtime_sandbox1_maintenance.py:13: AssertionError" in detail
            or "tests/_runtime_sandbox1_maintenance.py:13: AssertionError" in detail else None}


def checks(after_live=False):
    focused, config, frozen, benchmark, registry = [read(name + ".json") for name in
        ("focused_validation", "config_path_validation", "frozen_validation", "benchmark_check", "registry_baseline")]
    prior_registry = read("registry_baseline.json", ORIGINAL)
    prior_frozen = read("frozen_validation.json", ORIGINAL)
    historical = check_preservation()
    original_gates = read("pure_preoperational_gates.json", ORIGINAL)
    paths = {row["path"] for row in original_gates["source_bindings"]}
    paths.update(str(path.relative_to(ROOT)).replace("\\", "/") for path in PHASE.glob("*.py"))
    paths.update(("scripts/replay_runtime_java_pinned1c_retry.py", "tests/test_runtime_java_pinned_provider_retry.py"))
    paths.discard("docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C_RETRY/reviewed_source_runtime_java_pinned_provider.py")
    bindings, compilation_errors, whitespace_errors = [], [], []
    for relative in sorted(paths):
        content = (ROOT / relative).read_bytes()
        bindings.append({"path": relative, "sha256": sha256(content).hexdigest(), "size_bytes": len(content)})
        try:
            compile(content, relative, "exec", dont_inherit=True)
        except (SyntaxError, ValueError) as error:
            compilation_errors.append({"path": relative, "error": str(error)})
        if "RETRY/" in relative or relative.endswith("_retry.py") and "pinned" in relative:
            whitespace_errors.extend({"path": relative, "line": index} for index, line in
                enumerate(content.decode("utf-8").splitlines(), 1) if line.rstrip() != line)
            if not content.endswith(b"\n"):
                whitespace_errors.append({"path": relative, "line": "missing_final_newline"})
    json_errors = []
    for path in PHASE.glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            json_errors.append({"path": path.name, "error": str(error)})
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    (PHASE / "git_diff_check.txt").write_text(diff.stdout + diff.stderr, encoding="utf-8")
    current_sha = sha256((ROOT / "core/runtime_java_pinned_provider.py").read_bytes()).hexdigest()
    drift = drift_identity(frozen)
    same_drift = drift is not None and drift == drift_identity(prior_frozen)
    pure_results = (focused, config, frozen, registry)
    clean_tests = lambda value: value["exit_code"] == 0 and value["passed"] == value["collected"] and not value["skipped"]
    values = {
        "reviewed_corrected_provider_source_unchanged": current_sha == CORRECTED_SHA and current_sha != FIRST_SHA,
        "focused_corrected_provider_passed": clean_tests(focused),
        "explicit_independent_config_paths_and_controls_passed": clean_tests(config),
        "frozen_semantic_regressions_passed_with_only_known_drift": same_drift and len(frozen["failures"]) == 1
            and frozen["passed"] + 1 == frozen["collected"] and not frozen["skipped"]
            and frozen["collected"] == prior_frozen["collected"],
        "known_bookkeeping_failure_identity_unchanged": same_drift,
        "registry_picker_baseline_failures_unchanged": failure_keys(registry) == failure_keys(prior_registry)
            and all(registry[key] == prior_registry[key] for key in ("collected", "passed", "skipped", "exit_code")),
        "pure_validation_no_operational_effects": all(not row["real_effect_attempts"] for row in pure_results),
        "pure_validation_temporary_workspaces_removed": all(row.get("validation_temporary_directory_removed") is True
            for row in pure_results),
        "benchmark_check_passed": benchmark["exit_code"] == 0,
        "in_memory_compilation_passed": not compilation_errors,
        "JSON_and_authored_whitespace_passed": not json_errors and not whitespace_errors,
        "git_diff_check_passed": diff.returncode == 0,
        "historical_bytes_preserved": historical["all_bytes_preserved"],
    }
    new_registry_failures = []
    if after_live:
        after = read("registry_after.json")
        new_registry_failures = sorted(set(failure_keys(after)) - set(failure_keys(registry)))
        values["registry_picker_after_live_unchanged"] = failure_keys(after) == failure_keys(registry) and all(
            after[key] == registry[key] for key in ("collected", "passed", "skipped", "exit_code"))
        values["after_live_pure_and_temporaries_clean"] = not after["real_effect_attempts"] and after.get("validation_temporary_directory_removed") is True
    summary = {"checks": values, "current_provider_source_sha256": current_sha,
        "first_attempt_source_sha256": FIRST_SHA, "reviewed_corrected_source_sha256": CORRECTED_SHA,
        "focused": {key: focused[key] for key in ("collected", "passed", "skipped")},
        "config_path_controls": {key: config[key] for key in ("collected", "passed", "skipped")},
        "frozen": {key: frozen[key] for key in ("collected", "passed", "skipped")},
        "known_bookkeeping_failure_identity": drift, "registry_baseline_failure_count": len(registry["failures"]),
        "new_registry_failure_ids": new_registry_failures, "historical_preservation": historical,
        "compilation_errors": compilation_errors, "compiled_source_count": len(bindings),
        "whitespace_errors": whitespace_errors, "JSON_errors": json_errors,
        "benchmark_denied_import_events": benchmark.get("real_effect_attempts", []),
        "full_suite_claimed": False, "historical_repins": False}
    write("validation_after_live_summary.json" if after_live else "validation_summary.json", summary)
    return values, bindings, summary


def main():
    mode = sys.argv[1]
    if mode not in ("prepare", "report"):
        raise ValueError("retry_prepare_or_report_required")
    values, bindings, summary = checks(mode == "report")
    if mode == "prepare":
        artifacts = ("focused_validation.json", "config_path_validation.json", "frozen_validation.json",
            "registry_baseline.json", "benchmark_check.json", "preservation_baseline.json", "validation_summary.json")
        gates = {"phase_id": "RUNTIME.JAVA.PINNED.1C", "attempt_number": 2, "retry_of_attempt_number": 1,
            "provider_schema": "runtime_java_pinned_provider_1c_v1", "pure_gates_ready": all(values.values()),
            "checks": values, "source_bindings": bindings,
            "validation_bindings": [{"path": name, "sha256": sha256((PHASE / name).read_bytes()).hexdigest()} for name in artifacts]}
        write("pure_preoperational_gates.json", gates)
        print(json.dumps({"pure_gates_ready": gates["pure_gates_ready"], **summary}, indent=2))
        return int(not gates["pure_gates_ready"])
    live = read("RUNTIME_JAVA_PINNED_1C_RETRY_LOCAL.json")
    excluded = ("pinned1b_report", "java1c_report", "runtime_docker_controls", "runtime_attachment", "proof_receipt")
    report = {key: value for key, value in live.items() if key not in excluded}
    report.update(validation_summary=summary, historical_preservation=summary["historical_preservation"],
        live_evidence_artifact="RUNTIME_JAVA_PINNED_1C_RETRY_LOCAL.json", exported_JSON_is_report_only=True,
        process_local_proof_is_not_reconstructible_from_report=True, full_suite_claimed=False,
        corrected_source_has_live_success=live.get("exact_provider_proven") is True,
        second_live_attempt_performed=True,
        previous_attempt_status="PINNED_BACKEND_BINDING_MISMATCH",
        previous_attempt_reason="actual_runtime_pair_backend_bridge_mismatch",
        previous_attempt_immutable=True,
        success_semantics="Exact immutable provider proof only; no execution authority.",
        stop_boundary="Corrected provider retry exhausted. Stop after proof root and negative controls; no SYNTH, executor, BANK or Apply.")
    if not all(values.values()) and report.get("exact_provider_proven") is True:
        report.update(status="PINNED_PROOF_UNRESOLVED", reason="post_live_validation_failed",
            exact_provider_proven=False, positive_provider_roots_retained=0,
            positive_live_root_was_authenticated_before_post_validation=True)
    report["corrected_source_has_live_success"] = report.get("exact_provider_proven") is True
    write("RUNTIME_JAVA_PINNED_1C_RETRY_REPORT.json", report)
    print(json.dumps({"status": report["status"], "reason": report["reason"],
        "exact_provider_proven": report["exact_provider_proven"], "all_checks_passed": all(values.values()),
        "negative_controls": len(report.get("negative_authentication_matrix", {})),
        "historical_files_preserved": summary["historical_preservation"].get("files_checked")}, indent=2))
    return int(not all(values.values()) or report["status"] != "RUNTIME_JAVA_PINNED_1C_COMPLETE")


if __name__ == "__main__":
    sys.exit(main())
