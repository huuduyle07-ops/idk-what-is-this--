"""Collect existing validation evidence and render the final pure proof report."""
import hashlib
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main():
    evidence = {name: read(name + ".json") for name in (
        "focused", "benchmark", "proof", "registry_baseline", "registry_after",
        "registry_comparison", "preservation_comparison", "static_validation", "git_validation")}
    assert evidence["focused"]["exit_code"] == 0
    assert evidence["focused"]["collected"] == evidence["focused"]["passed_count"]
    assert evidence["benchmark"]["exit_code"] == 0 and evidence["benchmark"]["benchmark_errors"] == 0
    assert evidence["proof"]["exit_code"] == 0
    assert evidence["registry_comparison"]["unchanged"]
    assert evidence["preservation_comparison"]["historical_preservation_passed"]
    assert evidence["static_validation"]["passed"]
    assert evidence["git_validation"]["git_diff_check_exit_code"] == 0
    guard_modes = ("focused", "benchmark", "proof", "registry_baseline", "registry_after")
    for mode in guard_modes:
        assert evidence[mode]["all_operational_effects_zero"]
        assert not evidence[mode]["blocked_actions"]
        assert not evidence[mode]["imported_capability_owners"]
        assert all(value == 0 for value in evidence[mode]["audit_guard"].values())
    summary = {
        "phase_id": "SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1",
        "typed_result": "AGGREGATE_BUDGET_SCOPE_UNRESOLVED",
        "all_required_validation_checks_passed": True,
        "focused_tests_collected": evidence["focused"]["collected"],
        "focused_tests_passed": evidence["focused"]["passed_count"],
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
        "static_check_passed": True, "git_diff_check_passed": True,
        "all_operational_effects_zero": True,
        "guarded_modes": {mode: evidence[mode]["audit_guard"] for mode in guard_modes},
        "no_capability_owner_imports": True, "no_requirements_or_historical_files_changed": True,
        "no_transport_selected": True, "all_authority_flags_false": True,
        "proof_outcome_is_scope_unresolved_despite_validation_success": True,
        "evidence_files": [name + ".json" for name in evidence],
    }
    write("validation_summary.json", summary)
    runpy.run_path(str(HERE / "write_report.py"), run_name="__main__")
    files, errors = {}, []
    for path in sorted(HERE.rglob("*")):
        relative = path.relative_to(HERE)
        if not path.is_file() or "validation_tmp" in relative.parts or path.name == "final_artifact_checks.json":
            continue
        raw = path.read_bytes()
        files[relative.as_posix()] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if path.suffix in (".json", ".py", ".md"):
            text = raw.decode("utf-8")
            if path.suffix == ".json":
                json.loads(text)
            elif path.suffix == ".py":
                compile(text, str(path), "exec")
            errors.extend({"file": relative.as_posix(), "line": index} for index, line in enumerate(text.splitlines(), 1) if line.rstrip() != line)
    assert not errors, errors
    write("final_artifact_checks.json", {"passed": True, "whitespace_errors": errors,
        "json_parse_and_in_memory_compile_passed": True,
        "scratch_excluded": "validation_tmp", "files": files})
    print(json.dumps({"result": summary["typed_result"], "focused": summary["focused_tests_passed"],
                      "benchmark_cases": summary["benchmark_cases_checked"], "checks_passed": True}))


if __name__ == "__main__":
    main()
