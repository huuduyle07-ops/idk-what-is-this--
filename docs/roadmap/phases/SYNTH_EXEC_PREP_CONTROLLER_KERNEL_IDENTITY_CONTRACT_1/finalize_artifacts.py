"""Consolidate required validation evidence; no observer or capability execution."""
from hashlib import sha256
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


contract, budget = read("contract.json"), read("budget_projection.json")
focused, benchmark = read("focused.json"), read("benchmark.json")
baseline, after, comparison = (read(name) for name in (
    "registry_baseline.json", "registry_after.json", "registry_comparison.json"))
static, preservation = read("static_validation.json"), read("preservation_comparison.json")
git_before, git_after = read("git_before.json"), read("git_after.json")
assert focused["exit_code"] == benchmark["exit_code"] == 0
assert benchmark["benchmark_cases_checked"] == 54 and benchmark["benchmark_errors"] == 0
assert static["passed"] and preservation["historical_preservation_passed"]
assert comparison["unchanged"] and comparison["registry_and_picker_projections_identical"]
assert git_before["passed"] and git_after["passed"]
assert git_before["checks"] == git_after["checks"]
for value in (focused, benchmark, baseline, after):
    assert value["all_operational_effects_zero"]
    assert not any(value["audit_guard"].values())
    assert not value["blocked_actions"] and not value["imported_capability_owners"]
for value in (contract, budget):
    assert all(flag is False for flag in value["authority_flags"].values())
    assert all(type(count) is int and count == 0 for count in value["operational_effects"].values())
assert contract["typed_result"] == "KERNEL_IDENTITY_CONTRACT_UNRESOLVED"
assert contract["writer_completeness"] == "WRITER_INVENTORY_COMPLETENESS_UNRESOLVED"
write("git_validation.json", dict(passed=True, before_after_identical=True,
    diff_check_exit_code=git_after["checks"]["diff"]["exit_code"],
    cached_diff_check_exit_code=git_after["checks"]["cached"]["exit_code"],
    status_identical=True, whitespace_configuration="blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
    early_powershell_diagnostic="git_baseline.json retains early output/status but had unavailable native exit codes; authoritative exit codes are in git_before.json/git_after.json.",
    baseline_timing="Whole-workspace snapshot preceded all validation. Fixed Git before/after verification brackets final checks; the earlier diagnostic was captured after additive contract files were created. No existing file was edited at any point.",
    read_only_git_processes="git_checks.py invokes only fixed Git diff/status commands required by the user; these are not target runtime subprocess probes. Guarded pytest/benchmark process-attempt counters are zero.",
    stash_reset_clean_used=False))
summary = dict(phase_id=contract["phase_id"], typed_result=contract["typed_result"],
    validation_status="PASSED_WITH_IDENTICAL_PREEXISTING_REGISTRY_TEST_FAILURES",
    semantic_contract_complete=False, partial_projection_rules_frozen=True,
    focused=dict(collected=focused["collected"], passed=focused["passed_count"], exit_code=focused["exit_code"]),
    benchmark=dict(checked=54, errors=0, exit_code=0),
    registry_picker=dict(collected=baseline["collected"], baseline_passed=baseline["passed_count"], after_passed=after["passed_count"],
        baseline_failures=len(baseline["failed"]), after_failures=len(after["failed"]),
        existing_failure_nodes=[row["nodeid"] for row in baseline["failed"]], exact_comparison_unchanged=True,
        registry_and_picker_projections_identical=True, existing_failures_repaired=False),
    historical_preservation=dict(file_count=preservation["baseline_file_count"], passed=True,
        changed=[], deleted=[], added_outside_new_phase=[]),
    static=dict(passed=True, in_memory_python_compiled=static["compiled_count"], bytecode_written=False,
        evidence="static_validation.json", json_and_whitespace_checked=True),
    git=dict(passed=True, before_after_identical=True, evidence="git_validation.json"),
    budget=dict(partial_lower_materialize=3567, partial_lower_compile=5254,
        partial_lower_semantic_total=8821, conditional_candidate_A_partial_lower_framed_total=8829,
        conditional_candidate_A_excess=637, exact_full_projection_established=False,
        candidate_A_selected=False, cap_bytes=8192, historical_proof_rerun=False),
    writer_completeness=contract["writer_completeness"],
    authority_flags=contract["authority_flags"], operational_effects=contract["operational_effects"],
    all_guard_counters_zero=True, owner_imports=[], stop=True)
write("validation_summary.json", summary)
checks = []
for path in sorted(OUT.rglob("*")):
    if not path.is_file() or path.name == "final_artifact_checks.json" or "validation_tmp" in path.relative_to(OUT).parts:
        continue
    if path.suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))
    if path.suffix in {".json", ".py", ".md", ".txt"}:
        content = path.read_text(encoding="utf-8")
        assert all(line.rstrip() == line for line in content.splitlines()), str(path)
        if path.suffix == ".py":
            compile(content, str(path), "exec")
        checks.append(dict(path=path.relative_to(OUT).as_posix(), sha256=sha256(path.read_bytes()).hexdigest()))
write("final_artifact_checks.json", dict(passed=True, scope="Additive artifact JSON/whitespace/in-memory compilation; validation scratch excluded.",
    files_checked=checks, index_is_not_self_authentication=True,
    volatile_evidence_note="Later static validation can refresh static_validation.json without changing contract semantics; the authoritative current evidence is that file. No recursive self-hash is claimed."))
print(json.dumps(dict(typed_result=contract["typed_result"], validation=summary["validation_status"], focused_passed=focused["passed_count"],
    benchmark_checked=54, historical_files=preservation["baseline_file_count"], registry_unchanged=True)))
