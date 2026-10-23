"""Consolidate guarded, read-only validation for the corrected rejection."""
from hashlib import sha256
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    closure, inputs = read("closure.json"), read("input_artifacts.json")
    focused, benchmark = read("focused.json"), read("benchmark.json")
    baseline, after = read("registry_baseline.json"), read("registry_after.json")
    comparison, preservation = read("registry_comparison.json"), read("preservation_comparison.json")
    static = read("static_validation.json")
    git_before, git_after = read("git_before.json"), read("git_after.json")
    assert closure["typed_result"] == "CANDIDATE_A_REJECTED_BUDGET_INCOMPATIBLE"
    theorem = closure["theorem"]
    assert theorem["physical_stdout_lower_bound_bytes"] == 8821 > theorem["frozen_cumulative_stdout_cap_bytes"] == 8192
    assert theorem["proven_excess_lower_bound_bytes"] == 629
    assert not theorem["exact_minimum_claimed"] and not theorem["attainable_minimum_established"]
    assert focused["exit_code"] == 0 and focused["failed"] == focused["collection_errors"] == []
    assert focused["collected"] == focused["passed_count"] == 20
    new = [node for node in focused["passed_nodes"] if "TRANSPORT_CANDIDATE_A_CLOSE_1R/tests/" in node]
    assert len(new) == 11 and len(focused["passed_nodes"]) - len(new) == 9
    assert benchmark["exit_code"] == 0 and benchmark["benchmark_cases_checked"] == 54 and benchmark["benchmark_errors"] == 0
    assert comparison["unchanged"] and comparison["registry_and_picker_projections_identical"]
    assert len(baseline["failed"]) == len(after["failed"]) == 7
    assert static["passed"] and preservation["historical_preservation_passed"]
    assert preservation["changed"] == preservation["deleted"] == preservation["added_outside_new_phase"] == []
    assert git_before["passed"] and git_after["passed"] and git_before["checks"] == git_after["checks"]
    assert inputs["all_match_initial_preservation_baseline"] and inputs["embedded_hashes_all_match"]
    assert inputs["prior_final_index_all_match"] and inputs["prior_input_hashes_all_match"]
    for name in ("audit", "focused", "benchmark", "registry_baseline", "registry_after"):
        result = read(name + ".json")
        assert result["all_operational_effects_zero"] and not any(result["audit_guard"].values())
        assert result["blocked_actions"] == result["imported_capability_owners"] == []
    assert all(value is False for value in closure["authority_flags"].values())
    assert all(type(value) is int and value == 0 for value in closure["operational_effects"].values())
    write("git_validation.json", dict(passed=True, before_after_checks_identical=True,
        original_dirty_status_preserved=True, fixed_read_only_commands_only=True,
        diff_check_exit_code=git_after["checks"]["diff"]["exit_code"],
        cached_diff_check_exit_code=git_after["checks"]["cached"]["exit_code"],
        target_runtime_process_probe=False, stash_reset_clean_used=False,
        whitespace_configuration="blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol"))
    summary = dict(phase_id=closure["phase_id"], typed_result=closure["typed_result"],
        candidate_status=closure["candidate_status"], candidate_ever_selected=False,
        validation_status="PASSED_WITH_IDENTICAL_PREEXISTING_REGISTRY_FAILURES",
        theorem=dict(physical_stdout_lower_bound_bytes=8821, proven_excess_lower_bound_bytes=629,
            cap_bytes=8192, residuals_nonnegative=True, residual_leaves=88,
            class_occurrences=2, class_width_set=[1, 2, 3, 4, 5], adjustment_interval=[-8, 0],
            attainable_minimum_established=False, exact_minimum_claimed=False),
        input_hashes=dict(artifacts=len(inputs["files"]), embedded_sources=len(inputs["embedded_hash_checks"]),
            prior_indexed_artifacts=len(inputs["prior_final_index_checks"]), passed=True),
        focused=dict(collected=20, passed=20, failed=0, new_closure_tests=11, prior_frozen_closure_tests=9),
        benchmark=dict(checked=54, errors=0, exit_code=0),
        registry_picker=dict(collected=baseline["collected"], baseline_passed=baseline["passed_count"],
            after_passed=after["passed_count"], baseline_failures=7, after_failures=7,
            failure_signatures_identical=True, projections_identical=True,
            production_registry_mutated=False),
        static=dict(passed=True, python_compiled_in_memory=static["compiled_count"],
            bytecode_written=False, json_and_whitespace_checked=True),
        preservation=dict(file_count=preservation["baseline_file_count"], passed=True,
            changed=[], deleted=[], additions_outside_new_phase=[], prior_close_1_byte_identical=True),
        git=dict(passed=True, checks_identical=True, original_dirty_status_preserved=True),
        prior_closure_status="CANDIDATE_A_CLOSURE_UNRESOLVED", historical_stop_correct=True,
        transport_status="TRANSPORT_SELECTION_UNRESOLVED", universal_budget_feasibility="UNRESOLVED",
        kernel_status="KERNEL_IDENTITY_CONTRACT_UNRESOLVED", settled_projection_rules_frozen=True,
        writer_completeness="WRITER_INVENTORY_COMPLETENESS_UNRESOLVED",
        authority_flags=closure["authority_flags"], operational_effects=closure["operational_effects"],
        all_guard_counters_zero=True, owner_imports=[], replacement_selected=False, stop=True)
    write("validation_summary.json", summary)
    write("SYNTH_EXEC_PREP_CONTROLLER_TRANSPORT_CANDIDATE_A_CLOSE_1R_REPORT.json",
        dict(phase_id=closure["phase_id"], typed_result=closure["typed_result"],
            candidate="A", candidate_status=closure["candidate_status"], candidate_ever_selected=False,
            conservative_physical_stdout_lower_bound_bytes=8821, proven_excess_lower_bound_bytes=629,
            exact_minimum_claimed=False, attainable_minimum_established=False,
            closure="closure.json", premise_audit="premise_audit.json", inputs="input_artifacts.json",
            report="REPORT.md", roadmap_addendum="roadmap_addendum.json", validation="validation_summary.json",
            prior_closure_status="CANDIDATE_A_CLOSURE_UNRESOLVED",
            transport_status="TRANSPORT_SELECTION_UNRESOLVED", budget_feasibility="UNRESOLVED",
            kernel_status="KERNEL_IDENTITY_CONTRACT_UNRESOLVED",
            writer_completeness="WRITER_INVENTORY_COMPLETENESS_UNRESOLVED",
            replacement_selected=False, authority_flags=closure["authority_flags"],
            operational_effects=closure["operational_effects"], stop=True))
    checks = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path.name == "final_artifact_checks.json" or "validation_tmp" in path.relative_to(OUT).parts:
            continue
        if path.suffix in {".json", ".py", ".md", ".txt"}:
            content = path.read_text(encoding="utf-8")
            assert all(line.rstrip() == line for line in content.splitlines()), str(path)
            if path.suffix == ".json":
                json.loads(content)
            if path.suffix == ".py":
                compile(content, str(path), "exec")
        checks.append(dict(path=path.relative_to(OUT).as_posix(), sha256=sha256(path.read_bytes()).hexdigest()))
    write("final_artifact_checks.json", dict(passed=True, files_checked=checks,
        self_hash_claimed=False, validation_scratch_excluded=True,
        final_json_whitespace_validated=True, python_compilation_in_memory=True))
    print(json.dumps(dict(typed_result=closure["typed_result"], lower_bound=8821,
        proven_excess_lower_bound=629, focused_passed=20, benchmark_checked=54,
        historical_files=preservation["baseline_file_count"], registry_picker_identical=True)))


if __name__ == "__main__":
    main()
