"""Read-only historical comparison and static validation for this additive phase.

No capability owner is imported. Python compilation is in memory only. All
evidence writes are confined to this new phase directory.
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


def read_json(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def write_json(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preservation():
    baseline = read_json("preservation_baseline.json")["files"]
    changed, deleted = [], []
    for name, original in baseline.items():
        path = ROOT / name
        if not path.is_file():
            deleted.append(name)
            continue
        content = path.read_bytes()
        current = {"sha256": sha256(content).hexdigest(), "bytes": len(content)}
        if current != original:
            changed.append({"file": name, "before": original, "after": current})
    result = {"baseline_preexisting_file_count": len(baseline), "changed": changed,
        "deleted": deleted, "historical_preservation_passed": not (changed or deleted),
        "comparison_basis": "current preimplementation workspace bytes, including preexisting untracked history"}
    write_json("preservation_check.json", result)
    return result


def static_checks():
    authored = [path for path in OUTPUT.rglob("*") if path.is_file()
        and "validation_tmp" not in path.relative_to(OUTPUT).parts]
    additional = list((ROOT / "core").glob("synthetic*.py"))
    additional.extend(ROOT / "core" / (name + ".py") for name in (
        "behavioral_diagnostic_executor_refresh", "behavioral_diagnostic_executor_retry",
        "behavioral_diagnostic_executor_lifecycle_retry"))
    additional.extend(path for path in (ROOT / "tests").glob("test_synthetic*.py"))
    new_root_sources = {
        ROOT / "core/synthetic_reflection_execution_admission_pinned.py",
        ROOT / "tests/test_synthetic_reflection_execution_admission_pinned.py",
    }
    compiled, parsed, json_files, errors, whitespace = [], [], [], [], []
    for path in sorted(set(authored + additional)):
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
            if path in authored or path in new_root_sources:
                whitespace.extend({"file": name, "line": line} for line, text in enumerate(content.splitlines(), 1)
                    if text.rstrip() != text)
        except Exception as error:
            errors.append({"file": name, "error": type(error).__name__ + ": " + str(error)})
    result = {"compiled_in_memory": compiled, "parsed_AST": parsed,
        "UTF8_JSON_validated": json_files, "errors": errors, "whitespace_errors": whitespace,
        "owner_modules_imported": False, "bytecode_written": False,
        "whitespace_scope": "authored phase artifacts and new admission owner/tests, including untracked files",
        "passed": not errors and not whitespace}
    write_json("static_validation.json", result)
    return result


def registry_comparison():
    baseline, after = read_json("registry_baseline.json"), read_json("registry_after.json")
    keys = ("collected", "failed", "passed_nodes", "registry_summary", "picker")
    result = {"unchanged": all(baseline[key] == after[key] for key in keys),
        "baseline_collected": baseline["collected"], "after_collected": after["collected"],
        "baseline_passed": baseline["passed_count"], "after_passed": after["passed_count"],
        "baseline_failed": baseline["failed"], "after_failed": after["failed"],
        "existing_failures_preserved": baseline["failed"] == after["failed"],
        "registry_and_picker_projections_identical": all(baseline[key] == after[key] for key in ("registry_summary", "picker"))}
    write_json("registry_comparison.json", result)
    return result


def report_checks():
    path = OUTPUT / "SYNTH_REFLECT_ADMIT_PINNED_1A_REPORT.json"
    if not path.is_file():
        return None
    report = read_json(path.name)
    focused = read_json("inert_admission_tests.json")
    source = ROOT / "core/synthetic_reflection_execution_admission_pinned.py"
    checks = {
        "owner_source_hash_matches": report["owner_source_sha256"] == sha256(source.read_bytes()).hexdigest(),
        "exact_status": report["status"] == "SYNTH_REFLECT_ADMIT_PINNED_1A_COMPLETE",
        "exact_phase": report["phase_id"] == "SYNTH.REFLECT.ADMIT.PINNED.1",
        "exact_schema": report["schema_version"] == "synthetic_reflection_execution_admission_pinned_1_v1",
        "exact_type": report["exact_type"] == "PinnedSyntheticReflectionExecutionAdmission",
        "exact_domain": report["authentication_domain"] == "CATTUS:SYNTH.REFLECT.ADMIT.PINNED.1:exact-reflection-admission:v1",
        "request_decision_A_preserved": report["request_decision"] == "A",
        "focused_measurements_match": report["validation"]["focused_isolated_admission"] == focused,
        "focused_passed": focused["exit_code"] == 0,
        "operational_effects_exact_zero": bool(report["operational_effects"]) and all(
            type(value) is int and value == 0 for value in report["operational_effects"].values()),
        "no_lifecycle_or_operational_admission": all(report[name] is False for name in (
            "lifecycle_owner_implemented", "admission_consumption_API_implemented", "operational_admission_issued")),
        "readiness_unresolved": report["behavioral_activation_ready"] is False
            and report["behavioral_readiness_reason"] == "PROOF_UNRESOLVED"
            and report["compilation_authority"] is False,
        "no_full_frozen_suite_claim": report["validation"]["full_issuance_dependent_suites_run"] is False,
    }
    result = {"checks": checks, "passed": all(checks.values()),
        "report": path.name, "owner_modules_imported": False}
    write_json("report_consistency.json", result)
    return result


def main():
    result = {"phase_id": "SYNTH.REFLECT.ADMIT.PINNED.1", "preservation": preservation(),
        "static": static_checks(), "full_issuance_dependent_suites_run": False}
    result["registry_picker"] = registry_comparison()
    runs = {name: read_json(name + ".json") for name in (
        "registry_baseline", "registry_after", "frozen", "focused", "benchmark")}
    result["historical_source_AST_checks"] = read_json("frozen_source_checks.json")
    result["git_diff_check"] = read_json("git_diff_check.json")
    result["report_consistency"] = report_checks()
    result["guarded_run_summaries"] = {name: {key: run[key] for key in (
        "exit_code", "audit_guard", "all_operational_effects_zero", "imported_capability_owners")}
        for name, run in runs.items()}
    result["frozen_contract_source_AST_tests"] = {key: runs["focused"][key]
        for key in ("collected", "passed_count", "failed")}
    result["frozen_source_AST_regression_selection"] = {key: runs["frozen"][key]
        for key in ("collected", "passed_count", "failed")}
    log = (OUTPUT / "benchmark.txt").read_text(encoding="utf-8")
    result["benchmark_cases_checked"] = int(re.search(r"^Checked: (\d+)$", log, re.MULTILINE).group(1))
    result["benchmark_errors"] = int(re.search(r"^Errors: (\d+)$", log, re.MULTILINE).group(1))
    result["all_guarded_runs_zero_effect_attempts"] = all(run["all_operational_effects_zero"]
        and not run["imported_capability_owners"] for run in runs.values())
    result["safe_validation_passed"] = result["preservation"]["historical_preservation_passed"] \
        and result["static"]["passed"] and result["registry_picker"]["unchanged"] \
        and result["all_guarded_runs_zero_effect_attempts"] \
        and result["git_diff_check"]["exit_code"] == 0 \
        and result["historical_source_AST_checks"]["success"] \
        and (result["report_consistency"] is None or result["report_consistency"]["passed"]) \
        and all(runs[name]["exit_code"] == 0 for name in ("focused", "frozen", "benchmark"))
    write_json("safe_validation_summary.json", result)
    print(json.dumps({key: value for key, value in result.items() if key not in {
        "static", "preservation", "registry_picker", "historical_source_AST_checks"}}, indent=2))
    return 0 if result["safe_validation_passed"] else 1


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
