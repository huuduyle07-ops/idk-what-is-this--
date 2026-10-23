"""One gated SYNTH.AUTH.PINNED.1 issuance; stop before lifecycle or execution."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "docs/roadmap/phases/SYNTH_AUTH_PINNED_1"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from scripts.source_layout import source_path, read_preorganization_source


def _check_pure_gates():
    gates = json.loads((PHASE / "pure_preoperational_gates.json").read_text(encoding="utf-8"))
    required = {"focused_authorization_passed", "frozen_semantic_regressions_passed",
        "known_bookkeeping_drift_preserved", "benchmark_check_passed",
        "registry_picker_no_new_failures", "pure_validation_no_operational_effects",
        "in_memory_compilation_passed", "authored_whitespace_and_JSON_passed",
        "git_diff_check_passed", "historical_bytes_preserved"}
    checks = gates.get("checks", {})
    if (gates.get("phase_id") != "SYNTH.AUTH.PINNED.1" or gates.get("pure_gates_ready") is not True
            or not required.issubset(checks) or not all(v is True for v in checks.values())
            or not gates.get("source_bindings") or not gates.get("validation_bindings")):
        raise ValueError("synth_auth_pinned1_all_pure_gates_required_before_operation")
    for row in gates["source_bindings"]:
        if sha256(source_path(row["path"], root=ROOT).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("synth_auth_pinned1_source_changed_after_gates:" + row["path"])
    for row in gates["validation_bindings"]:
        if sha256((PHASE / row["path"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("synth_auth_pinned1_validation_changed_after_gates:" + row["path"])
    baseline = json.loads((PHASE / "preservation_baseline.json").read_text(encoding="utf-8"))
    for row in baseline["files"]:
        path = source_path(row["path"], root=ROOT)
        if not path.is_file() or sha256(read_preorganization_source(row["path"], root=ROOT)).hexdigest() != row["sha256"]:
            raise ValueError("synth_auth_pinned1_historical_bytes_changed:" + row["path"])
    return {"pure_gates_ready": True, "source_hashes_checked": len(gates["source_bindings"]),
        "validation_artifacts_checked": len(gates["validation_bindings"]),
        "historical_files_checked": len(baseline["files"])}


def main():
    if len(sys.argv) != 1:
        raise ValueError("synth_auth_pinned1_fixed_no_argument_replay_required")
    gates = _check_pure_gates()
    output = PHASE / "SYNTH_AUTH_PINNED_1_LOCAL.json"
    # Exclusive reservation consumes this phase's sole attempt even on failure.
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        previous_tempdir = tempfile.tempdir
        outcome = owner = None
        report = {"phase_id": "SYNTH.AUTH.PINNED.1",
            "status": "SYNTH_AUTH_PINNED_1_BLOCKED", "reason": "issuance_not_started",
            "synthetic_scenario_authorized": False, "runtime_execution_authority": False,
            "execution_lease_issued": False, "lifecycle_compatibility_evaluated": False,
            "reflection_admission_issued": False, "SyntheticStateBox_executed": False,
            "negative_authentication_matrix": {}, "provider_negative_authentication_matrix": {},
            "all_negative_controls_rejected": False, "provider_proof_consumed": False,
            "preoperational_gate_summary": gates, "single_live_authorization_attempt": True,
            "provider_proof_issuance_attempts": 0, "exported_json_is_report_only": True}
        try:
            tempfile.tempdir = str(PHASE)
            from core.runtime.synthetic import synthetic_runtime_authorization_pinned as owner
            from core import runtime_java_pinned_provider as provider
            report["provider_proof_issuance_attempts"] = 1
            outcome = owner.issue_pinned_synthetic_runtime_authorization()
            report = {**report, **outcome.as_dict()}
            report.update(preoperational_gate_summary=gates, single_live_authorization_attempt=True,
                historical_sources_modified_by_operation=False)
            if outcome.authorization is not None:
                matrix = owner.negative_authentication_matrix(outcome)
                provider_matrix = provider.negative_authentication_matrix(outcome.provider_outcome)
                report.update(negative_authentication_matrix=matrix,
                    provider_negative_authentication_matrix=provider_matrix,
                    all_negative_controls_rejected=bool(matrix) and all(matrix.values())
                        and bool(provider_matrix) and all(provider_matrix.values()),
                    authorization_authentication_after_negative_controls=(
                        owner.validate_pinned_synthetic_runtime_authorization(outcome.authorization)
                            is outcome.authorization))
                if not report["all_negative_controls_rejected"]:
                    report.update(status=owner.BLOCKED, reason="live_negative_matrix_failed",
                        synthetic_scenario_authorized=False)
                    owner._LIVE.pop(outcome.authorization.authorization_id, None)
                    report["withdrawn_authorization_report"] = report.pop("synthetic_authorization")
                    report["authorization_withdrawn_after_failed_checks"] = True
            else:
                report.update(negative_authentication_matrix={}, provider_negative_authentication_matrix={},
                    all_negative_controls_rejected=False,
                    authorization_authentication_after_negative_controls=False)
        except Exception as error:
            if outcome is not None and outcome.authorization is not None:
                owner._LIVE.pop(outcome.authorization.authorization_id, None)
            if "synthetic_authorization" in report:
                report["withdrawn_authorization_report"] = report.pop("synthetic_authorization")
            report.update(status="SYNTH_AUTH_PINNED_1_BLOCKED",
                reason="single_attempt_failed:" + type(error).__name__ + ":" + str(error)[:300],
                synthetic_scenario_authorized=False, all_negative_controls_rejected=False,
                authorization_authentication_after_negative_controls=False,
                authorization_withdrawn_after_failed_checks=outcome is not None and outcome.authorization is not None,
                provider_effect_accounting_complete=outcome is not None,
                remaining_phase_containers=report.get("remaining_phase_containers"))
        finally:
            tempfile.tempdir = previous_tempdir
        handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "reason": report["reason"], "output": str(output),
        "synthetic_scenario_authorized": report["synthetic_scenario_authorized"],
        "runtime_execution_authority": report["runtime_execution_authority"],
        "execution_lease_issued": report["execution_lease_issued"],
        "SyntheticStateBox_executed": report["SyntheticStateBox_executed"],
        "negative_controls": len(report["negative_authentication_matrix"]),
        "all_negative_controls_rejected": report["all_negative_controls_rejected"]}, indent=2))
    return 0 if report["status"] == "SYNTH_AUTH_PINNED_1_COMPLETE" else 2


if __name__ == "__main__":
    sys.exit(main())
