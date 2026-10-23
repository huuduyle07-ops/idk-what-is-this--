"""Host maintenance gates/reporting only. Never invokes a runtime owner."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
DRIFT = "tests/test_patch_candidate_behavior_executor1.py::test_bookkeeping_reversal_preserves_exact_frozen_receipts"
AUTHORED = ["core/runtime_java_pinned_provider.py", "scripts/replay_runtime_java_pinned1c.py",
    "tests/test_runtime_java_pinned_provider.py", "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C/pure_validation.py",
    "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C/check_validation.py"]


def read(name):
    return json.loads((PHASE / name).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def preservation():
    baseline = read("preservation_baseline.json")
    changed, missing = [], []
    for row in baseline["files"]:
        path = ROOT / row["path"]
        if not path.is_file():
            missing.append(row["path"])
        elif sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            changed.append(row["path"])
    return {"files_checked": len(baseline["files"]), "changed": changed, "missing": missing,
        "all_bytes_preserved": not changed and not missing, "historical_repins": False}


def checks():
    focused, frozen, benchmark = [read(name + ".json") for name in
        ("focused_validation", "frozen_validation", "benchmark_check")]
    before, after = read("registry_baseline.json"), read("registry_after.json")
    key = lambda row: (row["nodeid"], row["when"], row["outcome"])
    new_failures = sorted({key(row) for row in after["failures"]} - {key(row) for row in before["failures"]})
    prior = json.loads((ROOT / "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1B/frozen_validation.json").read_text(encoding="utf-8"))
    drift = [row for row in frozen["failures"] if row["nodeid"] == DRIFT and row["when"] == "call"]
    drift_known = len(drift) == 1 and any(row["nodeid"] == DRIFT for row in prior["failures"])
    frozen_ok = (not frozen["failures"] and frozen["exit_code"] == 0) or (
        drift_known and len(frozen["failures"]) == 1 and frozen["passed"] + 1 == frozen["collected"])
    preserved = preservation()
    paths = set(AUTHORED)
    previous = json.loads((ROOT / "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1B/pure_preoperational_gates.json").read_text(encoding="utf-8"))
    paths.update(row["path"] for row in previous["in_memory_compilation"]["files"])
    paths.update(str(path.relative_to(ROOT)).replace("\\", "/") for pattern in
        ("core/*runtime*.py", "core/*sandboxed_java*.py", "core/java_single_thread_capture.py")
        for path in ROOT.glob(pattern))
    bindings, compilation_errors = [], []
    for relative in sorted(paths):
        content = (ROOT / relative).read_bytes()
        bindings.append({"path": relative, "sha256": sha256(content).hexdigest(), "size_bytes": len(content)})
        try:
            compile(content, relative, "exec", dont_inherit=True)
        except (SyntaxError, ValueError) as error:
            compilation_errors.append({"path": relative, "error": str(error)})
    whitespace_errors = []
    for relative in AUTHORED:
        content = (ROOT / relative).read_text(encoding="utf-8")
        whitespace_errors.extend({"path": relative, "line": index} for index, line in enumerate(content.splitlines(), 1)
            if line.rstrip() != line)
        if not content.endswith("\n"):
            whitespace_errors.append({"path": relative, "line": "missing_final_newline"})
    json_errors = []
    for path in PHASE.glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            json_errors.append({"path": path.name, "error": str(error)})
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    (PHASE / "git_diff_check.txt").write_text(diff.stdout + diff.stderr, encoding="utf-8")
    pure = (not focused["real_effect_attempts"] and not frozen["real_effect_attempts"]
        and not before["real_effect_attempts"] and not after["real_effect_attempts"])
    check_values = {"focused_full_provider_graph_passed": focused["exit_code"] == 0 and focused["passed"] == focused["collected"],
        "frozen_semantic_regressions_passed": frozen_ok and not frozen["skipped"],
        "known_bookkeeping_drift_preserved": drift_known and preserved["all_bytes_preserved"],
        "benchmark_check_passed": benchmark["exit_code"] == 0,
        "registry_picker_no_new_failures": not new_failures,
        "pure_validation_no_operational_effects": pure,
        "in_memory_compilation_passed": not compilation_errors,
        "authored_whitespace_and_JSON_passed": not whitespace_errors and not json_errors,
        "git_diff_check_passed": diff.returncode == 0,
        "historical_bytes_preserved": preserved["all_bytes_preserved"]}
    summary = {"checks": check_values, "focused": {key: focused[key] for key in ("collected", "passed", "skipped")},
        "frozen": {key: frozen[key] for key in ("collected", "passed", "skipped")},
        "frozen_accepted_preexisting_failure_ids": [DRIFT] if drift_known else [],
        "registry_baseline_failure_count": len(before["failures"]), "registry_after_failure_count": len(after["failures"]),
        "new_registry_failure_ids": new_failures, "preservation": preserved,
        "in_memory_compilation_files": len(bindings), "compilation_errors": compilation_errors,
        "whitespace_errors": whitespace_errors, "JSON_errors": json_errors,
        "benchmark_check_exit_code": benchmark["exit_code"],
        "benchmark_denied_import_event": benchmark.get("real_effect_attempts", []),
        "full_suite_claimed": False, "historical_owners_changed": False}
    write("validation_summary.json", summary)
    return check_values, bindings, summary


def main():
    mode = sys.argv[1]
    values, bindings, summary = checks()
    if mode == "prepare":
        artifacts = ("focused_validation.json", "frozen_validation.json", "registry_baseline.json",
            "registry_after.json", "benchmark_check.json", "preservation_baseline.json", "validation_summary.json")
        gates = {"phase_id": "RUNTIME.JAVA.PINNED.1C", "pure_gates_ready": all(values.values()),
            "checks": values, "source_bindings": bindings,
            "validation_bindings": [{"path": name, "sha256": sha256((PHASE / name).read_bytes()).hexdigest()} for name in artifacts]}
        write("pure_preoperational_gates.json", gates)
        print(json.dumps({"pure_gates_ready": gates["pure_gates_ready"], **summary}, indent=2))
        return int(not gates["pure_gates_ready"])
    if mode != "report":
        raise ValueError(mode)
    live = read("RUNTIME_JAVA_PINNED_1C_LOCAL.json")
    excluded = ("pinned1b_report", "java1c_report", "runtime_docker_controls", "runtime_attachment", "proof_receipt")
    report = {key: value for key, value in live.items() if key not in excluded}
    report.update(validation_summary=summary,
        live_evidence_artifact="RUNTIME_JAVA_PINNED_1C_LOCAL.json",
        exported_JSON_is_report_only=True,
        process_local_proof_is_not_reconstructible_from_report=True,
        historical_preservation=summary["preservation"],
        baseline_vs_after={"new_registry_failures": summary["new_registry_failure_ids"],
            "historical_bookkeeping_drift_preserved": values["known_bookkeeping_drift_preserved"]},
        success_semantics="Exact immutable provider evidence only; no execution authority.")
    if live["exact_provider_proven"] is not True:
        # Diagnostic comparisons of preserved reports grant no live provenance.
        bound, java = live.get("pinned1b_report", {}), live.get("java1c_report", {})
        binding = bound.get("binding_receipt", {})
        target = bound.get("target_inspection_report", {})
        inspected = target.get("inspection_receipt", {})
        archive = inspected.get("archive", {})
        controller = archive.get("controller", {})
        jr = java.get("verification_receipt", {})
        jd = java.get("descriptor", {})
        pair = java.get("sandbox_authentication", {})
        source = dict(binding.get("inspection_controller_source_identity", ()))
        created = [row for row in live.get("runtime_docker_controls", ())
            if row["command"] == "create" and row["scope"] == "JAVA1C_fixed_controller"]
        actual_source = created[0]["argv"][-1].encode() if len(created) == 1 else b""
        report.update(
            diagnostics_are_report_only=True,
            final_cross_pair_bridge_result=False,
            provider_proof_receipt_id=None, provider_proof_fingerprint=None,
            controller_runtime_identity_attachment_issued=False,
            runtime_controller_identity_result="unresolved_final_attachment_not_issued",
            runtime_controller_identity_proof_method="immutable_image_relation_implemented_but_live_bridge_blocked",
            runtime_controller_byte_rehash_performed=False,
            fresh_pinned1b_identity=binding.get("receipt_id"),
            fresh_pinned1b_fingerprint=binding.get("binding_receipt_fingerprint"),
            fresh_target_inspection_identity=inspected.get("receipt_id"),
            fresh_target_inspection_fingerprint=target.get("inspection_receipt_fingerprint"),
            fresh_bind_identity=binding.get("bind_attachment_id"),
            fresh_bind_fingerprint=binding.get("bind_attachment_fingerprint"),
            bind_sandbox_descriptor_fingerprint=binding.get("bind_sandbox_descriptor_fingerprint"),
            bind_sandbox_receipt_fingerprint=binding.get("bind_sandbox_receipt_fingerprint"),
            bind_sandbox_evidence_digest=binding.get("bind_sandbox_receipt_evidence_digest"),
            canonical_backend_route=binding.get("canonical_backend_route_identity"),
            canonical_backend_version=binding.get("canonical_backend_server_version"),
            fresh_java1c_descriptor_fingerprint=jd.get("java_descriptor_fingerprint"),
            fresh_java1c_receipt_fingerprint=jr.get("verification_receipt_fingerprint"),
            fresh_java1c_evidence_digest=jr.get("evidence_sha256"),
            actual_java1c_sandbox_descriptor_fingerprint=pair.get("descriptor_fingerprint"),
            actual_java1c_sandbox_receipt_fingerprint=pair.get("receipt_fingerprint"),
            actual_java1c_sandbox_evidence_digest=pair.get("evidence_sha256"),
            measured_route_version_equal=(live.get("runtime_backend_pre") == live.get("runtime_backend_post")
                == [binding.get("canonical_backend_route_identity"), binding.get("canonical_backend_server_version")]),
            image_coherence_observed=binding.get("target_image_identity") == jr.get("image_identity"),
            java_coherence_observed=archive.get("java", {}).get("sha256") == java.get("facts", {}).get("java_binary_sha256"),
            javac_coherence_observed=archive.get("javac", {}).get("sha256") == java.get("facts", {}).get("javac_binary_sha256"),
            target_controller_path=controller.get("normalized_path"),
            target_controller_resolved_path=controller.get("resolved_path"),
            target_controller_sha256=controller.get("sha256"),
            runtime_controller_path="/usr/local/bin/python" if len(created) == 1 else None,
            controller_source_coherence_observed=(sha256(actual_source).hexdigest() == source.get("source_sha256")
                and str(len(actual_source)) == source.get("source_size_bytes")),
            archive_ancestor_metadata_complete=controller.get("ancestor_metadata_complete"),
            runtime_controller_traversal_confirmed=java.get("status") == "RUNTIME_JAVA_1_COMPLETE_WITH_WARNINGS",
            upstream_cleanup={"pinned1b": bound.get("cleanup_verified"), "inspection": target.get("cleanup"),
                "runtime": {key: java.get(key) for key in ("cleanup_verified", "container_cleanup_verified",
                    "child_and_capture_cleanup_verified", "temporary_workspace_removed", "phase_container_count_after_teardown")},
                "runtime_backend_controls": live["runtime_backend_effects"]["controls_reaped_and_pipes_closed"]},
            remaining_phase_containers=0 if bound.get("remaining_phase_containers") == 0
                and java.get("phase_container_count_after_teardown") == 0 else None,
            live_negative_matrix="not_run_no_final_proof_root",
            failure_cause="Owner erroneously compared fresh private empty Docker config paths as backend identity",
            correction="Project frozen endpoint route semantics; separately retain and verify each absent config path",
            correction_pure_tests_passed=values["focused_full_provider_graph_passed"],
            second_live_attempt_performed=False,
            live_attempt_gates_artifact="live_attempt_gates.json",
            live_attempt_source_artifact="attempt_source_runtime_java_pinned_provider.py",
            live_attempt_source_sha256=sha256((PHASE / "attempt_source_runtime_java_pinned_provider.py").read_bytes()).hexdigest(),
            current_provider_source_sha256=sha256((ROOT / "core/runtime_java_pinned_provider.py").read_bytes()).hexdigest(),
            corrected_source_has_live_success=False,
            stop_boundary="Single live attempt exhausted. No final root, SYNTH authorization, executor or Apply.")
    write("RUNTIME_JAVA_PINNED_1C_REPORT.json", report)
    print(json.dumps({"status": report["status"], "exact_provider_proven": report["exact_provider_proven"],
        "runtime_authority": report["runtime_authority"], "all_checks_passed": all(values.values()),
        "historical_files_preserved": report["historical_preservation"]["files_checked"]}, indent=2))
    return int(not all(values.values()) or report["status"] != "RUNTIME_JAVA_PINNED_1C_COMPLETE")


if __name__ == "__main__":
    sys.exit(main())
