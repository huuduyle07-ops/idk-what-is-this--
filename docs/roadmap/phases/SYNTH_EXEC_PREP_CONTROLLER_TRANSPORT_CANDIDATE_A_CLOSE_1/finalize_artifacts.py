"""Consolidate pure closure evidence without mutating any historical artifact."""
from hashlib import sha256
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize(value):
    if isinstance(value, str):
        return re.sub(r" at 0x[0-9A-Fa-f]+>", " at <process-address>>", value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    return value


def main():
    closure = read("closure.json")
    audit = read("premise_audit.json")
    inputs = read("input_artifacts.json")
    baseline, focused = read("focused_baseline.json"), read("focused.json")
    registry_baseline, registry_after = read("registry_baseline.json"), read("registry_after.json")
    registry_comparison, preservation = read("registry_comparison.json"), read("preservation_comparison.json")
    benchmark, static = read("benchmark.json"), read("static_validation.json")
    git_before, git_after = read("git_before.json"), read("git_after.json")
    assert closure["typed_result"] == "CANDIDATE_A_CLOSURE_UNRESOLVED"
    assert closure["candidate_rejection_published"] is False
    assert inputs["all_match_initial_preservation_baseline"] and inputs["embedded_hashes_all_match"]
    assert audit["all_listed_residuals_nonnegative"] and not audit["all_actual_width_variation_in_residuals"]
    assert (audit["retained_semantic_subtotal"], audit["retained_physical_subtotal"],
            audit["retained_profile_excess"], audit["conservative_excess"]) == (8821, 8829, 637, 629)
    assert benchmark["exit_code"] == 0 and benchmark["benchmark_errors"] == 0
    assert benchmark["benchmark_cases_checked"] == 54
    assert static["passed"] and preservation["historical_preservation_passed"]
    assert registry_comparison["unchanged"] and registry_comparison["registry_and_picker_projections_identical"]
    assert git_before["passed"] and git_after["passed"] and git_before["checks"] == git_after["checks"]
    assert len(baseline["failed"]) == len(focused["failed"]) == 1
    assert normalize(baseline["failed"]) == normalize(focused["failed"])
    assert baseline["collection_errors"] == focused["collection_errors"] == []
    assert baseline["skipped"] == focused["skipped"] == []
    assert baseline["exit_code"] == focused["exit_code"] == 1
    own = sorted(set(focused["passed_nodes"]) - set(baseline["passed_nodes"]))
    assert len(own) == 9
    assert all("TRANSPORT_CANDIDATE_A_CLOSE_1/tests/" in node for node in own)
    assert set(baseline["passed_nodes"]) < set(focused["passed_nodes"])
    for name in ("audit", "focused_baseline", "focused", "benchmark", "registry_baseline", "registry_after"):
        result = read(name + ".json")
        assert result["all_operational_effects_zero"] and not any(result["audit_guard"].values())
        assert result["blocked_actions"] == result["imported_capability_owners"] == []
    focus_comparison = dict(unchanged_historical_tests=True,
        historical_collected=baseline["collected"], current_collected=focused["collected"],
        historical_passed=baseline["passed_count"], current_passed=focused["passed_count"],
        new_passed_nodes=own, new_passed_count=9,
        historical_failure_count=1, current_failure_count=1,
        failure_signatures_identical_after_allocator_address_normalization=True,
        historical_failed=baseline["failed"], current_failed=focused["failed"],
        existing_failure_source_not_modified=True,
        baseline_note="Historical-only focused run was captured after the initial combined run exposed this existing frozen-source failure. Historical sources are byte-identical to the pre-work snapshot.")
    write("focused_comparison.json", focus_comparison)
    write("git_validation.json", dict(passed=True, fixed_read_only_checks_only=True,
        checks_identical=True, status_identical=True,
        diff_check_exit_code=git_after["checks"]["diff"]["exit_code"],
        cached_diff_check_exit_code=git_after["checks"]["cached"]["exit_code"],
        whitespace_configuration="blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
        target_runtime_process_probe=False, stash_reset_clean_used=False,
        git_baseline_scope="Original dirty worktree state, captured after creation of excluded additive validation helpers; no historical source had been changed."))
    summary = dict(phase_id=closure["phase_id"], typed_result=closure["typed_result"],
        validation_status="PASSED_WITH_IDENTICAL_PREEXISTING_FAILURES",
        exact_requested_proof_closed=False, candidate_rejection_published=False,
        exact_premise_failure="Two legal variable-width class-size fields are absent from R_C; profile width 5 is not a universal minimum.",
        conditional_arithmetic=dict(materialize=3567, compile=5254, semantic=8821, physical=8829,
            excess=637, condition="five-digit class-size profile retained"),
        conservative_arithmetic=dict(physical_lower=8821, excess=629, formal_rejection_substituted=False),
        input_hashes=dict(artifacts=len(inputs["files"]), embedded_references=len(inputs["embedded_hash_checks"]),
            passed=True, history_imported_or_rerun=False),
        residuals=dict(listed_leaves=88, all_listed_nonnegative=True,
            omitted_class_width_occurrences=2, omitted_difference_interval=[-8, 0]),
        new_closure_tests=dict(collected=9, passed=9, failed=0),
        focused=dict(collected=focused["collected"], passed=focused["passed_count"], failed=1,
            unchanged_historical_failure=True, evidence="focused_comparison.json"),
        registry_picker=dict(collected=registry_baseline["collected"],
            baseline_passed=registry_baseline["passed_count"], after_passed=registry_after["passed_count"],
            baseline_failed=len(registry_baseline["failed"]), after_failed=len(registry_after["failed"]),
            projections_identical=True, existing_failure_signatures_preserved=True),
        benchmark=dict(checked=54, errors=0, exit_code=0),
        static=dict(passed=True, in_memory_python_compiled=static["compiled_count"],
            bytecode_written=False, json_whitespace_checked=True),
        preservation=dict(file_count=preservation["baseline_file_count"], passed=True,
            changed=[], deleted=[], additions_outside_new_phase=[]),
        git=dict(passed=True, original_dirty_state_preserved=True),
        transport_status=closure["transport_status"], overall_budget_feasibility="UNRESOLVED",
        kernel_status=closure["kernel_status"], writer_completeness=closure["writer_completeness"],
        settled_projection_rules_frozen=True,
        authority_flags=closure["authority_flags"], operational_effects=closure["operational_effects"],
        all_guard_counters_zero=True, owner_imports=[], stop=True)
    write("validation_summary.json", summary)
    write("SYNTH_EXEC_PREP_CONTROLLER_TRANSPORT_CANDIDATE_A_CLOSE_1_REPORT.json",
        dict(phase_id=closure["phase_id"], typed_result=closure["typed_result"],
            candidate="A", candidate_status="UNSELECTED", candidate_rejection_published=False,
            closure="closure.json", premise_audit="premise_audit.json", source_hashes="input_artifacts.json",
            report="REPORT.md", roadmap_addendum="roadmap_addendum.json", validation="validation_summary.json",
            historical_transport_result="TRANSPORT_SELECTION_UNRESOLVED",
            budget_feasibility="UNRESOLVED", kernel_identity="KERNEL_IDENTITY_CONTRACT_UNRESOLVED",
            writer_completeness="WRITER_INVENTORY_COMPLETENESS_UNRESOLVED",
            authority_flags=closure["authority_flags"], operational_effects=closure["operational_effects"], stop=True))
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
        final_json_and_whitespace_passed=True, final_python_compile_in_memory_passed=True))
    print(json.dumps(dict(typed_result=closure["typed_result"], validation=summary["validation_status"],
        new_tests_passed=9, benchmark_checked=54, historical_files=preservation["baseline_file_count"],
        registry_picker_identical=True)))


if __name__ == "__main__":
    main()
