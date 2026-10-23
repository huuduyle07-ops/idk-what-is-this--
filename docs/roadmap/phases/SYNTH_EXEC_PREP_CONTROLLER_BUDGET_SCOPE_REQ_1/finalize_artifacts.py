"""Assemble pure additive scope validation evidence without retrying any proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE = "SYNTH.EXEC.PREP.CONTROLLER.BUDGET.SCOPE.REQ.1"
COMPLETE = "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_COMPLETE"
REPORT = "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_REPORT.json"


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def digest(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def main():
    requirement = read("requirement.json")
    evidence = {name: read(name + ".json") for name in (
        "focused", "benchmark", "registry_baseline", "registry_after",
        "registry_comparison", "preservation_comparison", "static_validation", "git_validation")}
    assert requirement["typed_result"] == COMPLETE
    assert requirement["historical_bytes_preserved"]
    assert all(value is False for value in requirement["authority_flags"].values())
    assert all(value == 0 for value in requirement["operational_effects"].values())
    assert evidence["focused"]["exit_code"] == 0
    assert evidence["focused"]["collected"] == evidence["focused"]["passed_count"]
    assert evidence["benchmark"]["exit_code"] == 0
    assert evidence["benchmark"]["benchmark_errors"] == 0
    assert evidence["registry_comparison"]["unchanged"]
    assert evidence["preservation_comparison"]["historical_preservation_passed"]
    assert evidence["static_validation"]["passed"]
    assert evidence["git_validation"]["git_diff_check_exit_code"] == 0
    assert evidence["git_validation"]["git_cached_diff_check_exit_code"] == 0
    assert evidence["git_validation"]["baseline_vs_after_identical"]
    guard_modes = ("focused", "benchmark", "registry_baseline", "registry_after")
    for mode in guard_modes:
        assert evidence[mode]["all_operational_effects_zero"]
        assert not evidence[mode]["blocked_actions"]
        assert not evidence[mode]["imported_capability_owners"]
        assert all(value == 0 for value in evidence[mode]["audit_guard"].values())
    validator_sha = digest("validate_pure.py")
    assert all(evidence[mode]["validator_sha256"] == validator_sha for mode in guard_modes)
    summary = {
        "phase_id": PHASE,
        "typed_result": COMPLETE,
        "created_at": "2026-10-19",
        "requirement_file": "requirement.json",
        "requirement_sha256": digest("requirement.json"),
        "all_required_validation_checks_passed": True,
        "focused_tests_collected": evidence["focused"]["collected"],
        "focused_tests_passed": evidence["focused"]["passed_count"],
        "focused_selected_nodes": evidence["focused"]["selected_nodes"],
        "benchmark_cases_checked": evidence["benchmark"]["benchmark_cases_checked"],
        "benchmark_errors": evidence["benchmark"]["benchmark_errors"],
        "registry_picker_baseline": {"collected": evidence["registry_baseline"]["collected"],
            "passed": evidence["registry_baseline"]["passed_count"],
            "failed": len(evidence["registry_baseline"]["failed"])},
        "registry_picker_after": {"collected": evidence["registry_after"]["collected"],
            "passed": evidence["registry_after"]["passed_count"],
            "failed": len(evidence["registry_after"]["failed"])},
        "registry_picker_and_existing_failures_unchanged": True,
        "baseline_failure_normalization": evidence["registry_comparison"]["signature_comparison"],
        "preservation": evidence["preservation_comparison"],
        "preservation_baseline_sha256": digest("preservation_baseline.json"),
        "registry_baseline_sha256": digest("registry_baseline.json"),
        "static_check_passed": True,
        "git_diff_check_passed": True,
        "git_baseline_vs_after_identical": True,
        "all_operational_effects_zero": True,
        "guarded_modes": {mode: evidence[mode]["audit_guard"] for mode in guard_modes},
        "no_capability_owner_imports": True,
        "historical_bytes_preserved": True,
        "new_requirement_only": True,
        "no_transport_selected": True,
        "all_authority_flags_false": True,
        "old_budget_proof_retried": False,
        "final_feasibility_or_impossibility_claim": False,
        "scope_clarification_only": True,
        "evidence_files": [name + ".json" for name in evidence],
    }
    write("validation_summary.json", summary)
    report = {
        "phase_id": PHASE,
        "typed_result": COMPLETE,
        "meaning": "The cumulative preparation-capture interval is now explicitly defined without changing the 8192-byte cap or protocol schema.",
        "artifact_kind": "PURE_ADDITIVE_REQUIREMENT_CLARIFICATION",
        "created_at": "2026-10-19",
        "requirement": {"file": "requirement.json", "sha256": summary["requirement_sha256"]},
        "normative_table": "normative_table.md",
        "counter_interval": requirement["counter_interval"],
        "fresh_readiness_observation": requirement["fresh_readiness_observation"],
        "initial_empty_observation": requirement["initial_empty_observation"],
        "caps": requirement["caps"],
        "independent_bounds": requirement["independent_bounds"],
        "cleanup": requirement["cleanup"],
        "handoff": requirement["handoff"],
        "stream_accounting": requirement["stream_accounting"],
        "budget_arithmetic_consequence": requirement["budget_arithmetic_consequence"],
        "validation": {"file": "validation_summary.json", "sha256": digest("validation_summary.json"),
            "all_required_validation_checks_passed": True},
        "historical_bytes_preserved": True,
        "old_budget_proof_retried": False,
        "old_budget_proof_outcome_changed": False,
        "final_feasibility_or_impossibility_claim": False,
        "transport_selected": False,
        "authority_flags": requirement["authority_flags"],
        "operational_effects": requirement["operational_effects"],
        "stop": True,
    }
    write(REPORT, report)
    files, whitespace, parsed, compiled = {}, [], [], []
    for path in sorted(HERE.rglob("*")):
        relative = path.relative_to(HERE)
        if not path.is_file() or "validation_tmp" in relative.parts or path.name == "final_artifact_checks.json":
            continue
        raw = path.read_bytes()
        files[relative.as_posix()] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if path.suffix in (".json", ".py", ".md"):
            content = raw.decode("utf-8")
            if path.suffix == ".json":
                json.loads(content)
                parsed.append(relative.as_posix())
            elif path.suffix == ".py":
                compile(content, str(path), "exec")
                compiled.append(relative.as_posix())
            whitespace.extend({"file": relative.as_posix(), "line": index}
                for index, line in enumerate(content.splitlines(), 1) if line.rstrip() != line)
    assert not whitespace, whitespace
    write("final_artifact_checks.json", {"passed": True, "whitespace_errors": whitespace,
        "json_parse_and_in_memory_compile_passed": True, "json_parsed": parsed,
        "python_compiled_in_memory": compiled, "bytecode_written": False,
        "scratch_excluded": "validation_tmp", "self_hash_excluded_to_avoid_cycle": True,
        "files": files})
    print(json.dumps({"result": COMPLETE, "focused": summary["focused_tests_passed"],
        "benchmark_cases": summary["benchmark_cases_checked"], "checks_passed": True,
        "old_budget_proof_retried": False}))


if __name__ == "__main__":
    main()
