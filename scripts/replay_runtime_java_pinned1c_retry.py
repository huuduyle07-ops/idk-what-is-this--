"""Exactly one corrected provider retry; historical Attempt 1 is immutable."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C_RETRY"
sys.path[:0] = [str(ROOT), str(PHASE)]
sys.dont_write_bytecode = True
FIRST_SHA = "e1edf506c522515199a98a0ff90e1985dbfce0235854ac9978b549c5938b8bee"
CORRECTED_SHA = "bca4a46363a27e23fba60cbc556eb30e3f2b6e03f4ed6e95c81ac7231756ddaa"


def _check_pure_gates():
    gates = json.loads((PHASE / "pure_preoperational_gates.json").read_text(encoding="utf-8"))
    if (gates.get("phase_id") != "RUNTIME.JAVA.PINNED.1C" or gates.get("attempt_number") != 2
            or gates.get("provider_schema") != "runtime_java_pinned_provider_1c_v1"
            or gates.get("pure_gates_ready") is not True or not gates.get("checks")
            or not all(value is True for value in gates["checks"].values())):
        raise ValueError("retry_all_fresh_pure_gates_required_before_operation")
    for entry in gates["source_bindings"]:
        if sha256((ROOT / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("retry_source_changed_after_gates:" + entry["path"])
    for entry in gates["validation_bindings"]:
        if sha256((PHASE / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("retry_validation_changed_after_gates:" + entry["path"])
    current = sha256((ROOT / "core/runtime_java_pinned_provider.py").read_bytes()).hexdigest()
    if current != CORRECTED_SHA or current == FIRST_SHA:
        raise ValueError("retry_reviewed_corrected_provider_source_required")
    from preservation import check
    historical = check()
    if not historical["all_bytes_preserved"]:
        raise ValueError("retry_historical_preservation_failed:" + json.dumps(historical))
    return {"pure_gates_ready": True, "source_hashes_checked": len(gates["source_bindings"]),
        "validation_artifacts_checked": len(gates["validation_bindings"]),
        "historical_files_checked": historical["files_checked"], "current_provider_source_sha256": current,
        "preoperational_gates_sha256": sha256((PHASE / "pure_preoperational_gates.json").read_bytes()).hexdigest()}


def main():
    if len(sys.argv) != 1:
        raise ValueError("retry_fixed_no_argument_replay_required")
    gates = _check_pure_gates()
    output = PHASE / "RUNTIME_JAVA_PINNED_1C_RETRY_LOCAL.json"
    # Exclusive reservation precedes owner imports and all operational effects.
    # An exception preserves a blocker and consumes this retry; no retry loop.
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        report = {"phase_id": "RUNTIME.JAVA.PINNED.1C", "schema_version": "runtime_java_pinned_provider_1c_v1",
            "requirement_profile": "RUNTIME.JAVA.PINNED.1", "requirement_schema": "runtime_java_pinned_1_v1",
            "status": "PINNED_PROOF_UNRESOLVED", "reason": "retry_reserved_not_completed", "exact_provider_proven": False}
        previous_tempdir = tempfile.tempdir
        observer = None
        owner = outcome = None
        provider_issuer_call_attempted = False
        try:
            tempfile.tempdir = str(PHASE)
            from core import runtime_java_pinned_provider as owner
            from authentication_controls import (config_observation, negative_authentication_matrix,
                reauthenticate_originals)
            observer = config_observation()
            with observer:
                provider_issuer_call_attempted = True
                outcome = owner.issue_pinned_java_exact_provider()
            report = outcome.as_dict()
            report["private_config_observation"] = observer.as_dict()
            if not observer.cleanup_verified or (outcome.receipt is not None and not observer.records):
                report.update(status=owner.CLEANUP_FAILURE, reason="retry_private_config_or_instrumentation_cleanup_failed",
                    exact_provider_proven=False, proof_receipt=None, runtime_attachment=None)
            elif outcome.receipt is not None:
                matrix = negative_authentication_matrix(outcome, observer)
                report["negative_authentication_matrix"] = matrix
                report["all_negative_controls_rejected"] = bool(matrix) and all(matrix.values())
                authenticated = reauthenticate_originals(outcome)
                report["original_authentication_after_negative_controls"] = authenticated
                report["proof_authentication_after_negative_controls"] = all(authenticated.values())
                report["negative_control_freshness_semantics"] = (
                    "No additional live owner issuance. Different fresh-identity candidates are unauthorized substitutions; "
                    "different independently authenticated graphs are tested in pure controls.")
                if not report["all_negative_controls_rejected"] or not report["proof_authentication_after_negative_controls"]:
                    report.update(status=owner.UNRESOLVED, reason="retry_live_negative_or_original_authentication_failed",
                        exact_provider_proven=False)
            else:
                report.update(negative_authentication_matrix={}, all_negative_controls_rejected=False,
                    proof_authentication_after_negative_controls=False,
                    live_negative_matrix="not_run_no_final_proof_root")
        except Exception as error:
            if outcome is not None:
                report = {**outcome.as_dict(), **report}
            report.update(status=getattr(error, "status", "PINNED_PROOF_UNRESOLVED"),
                reason="retry_fail_closed:" + str(error)[:500], exact_provider_proven=False,
                proof_receipt=None, runtime_attachment=None)
            if observer is not None:
                try:
                    report["private_config_observation"] = observer.as_dict()
                except Exception as diagnostic_error:
                    report["private_config_observation"] = {"authentication_failed": True,
                        "diagnostic_error": str(diagnostic_error)[:300]}
        finally:
            bound = report.get("pinned1b_report", {})
            ledger = report.setdefault("operational_effect_counts_by_owner", {})
            for role in ("bind_pre_effects", "bind_post_effects", "bind_sandbox2_infrastructure_effects"):
                if role in bound:
                    ledger.setdefault(role, bound[role])
            if "target_inspection_effects" in bound:
                ledger.setdefault("PINNED1A", bound["target_inspection_effects"])
            elif "target_inspection_report" in bound:
                ledger.setdefault("PINNED1A", bound["target_inspection_report"].get("operational_effect_counts", {}))
            if bound:
                report["pinned1b_upstream_cleanup"] = bound.get("cleanup", {})
                report["pinned1b_upstream_status"] = bound.get("status")
                report["pinned1b_remaining_phase_containers"] = bound.get("remaining_phase_containers")
            if report.get("exact_provider_proven") is not True and outcome is not None:
                # A failed outer cleanup or authentication control retains no
                # positive provider root in the issuing process.
                if outcome.receipt is not None:
                    owner._LIVE.pop(outcome.receipt.receipt_id, None)
                    report["withdrawn_provider_root_id"] = outcome.receipt.receipt_id
                if outcome.attachment is not None:
                    owner._ATTACHMENTS.pop(outcome.attachment.receipt_id, None)
                report.update(proof_receipt=None, runtime_attachment=None, positive_provider_root_retained=False)
            for key in ("runtime_authority", "real_task_runtime_authority", "repository_write_authority",
                    "apply_authority", "compatibility_authority", "SYNTH_authority", "executor_authority",
                    "complete_inventory_claimed", "complete_local_artifact_discovery_claimed",
                    "global_provider_absence_claimed", "global_provider_uniqueness_claimed",
                    "daemon_identity_claimed", "daemon_continuity_claimed", "aba_resistance_claimed"):
                report.setdefault(key, False)
            report["provider_issuer_call_attempted"] = provider_issuer_call_attempted
            report["final_provider_roots_issued"] = int(outcome is not None and outcome.receipt is not None)
            report["positive_provider_roots_retained"] = int(report.get("exact_provider_proven") is True)
            if not provider_issuer_call_attempted:
                report.update(fresh_pinned1b_invocations=0, fresh_java1c_invocations=0,
                    operational_effects_complete=True, operational_effect_counts_by_owner={},
                    remaining_phase_containers=0)
            elif outcome is None:
                report.update(operational_effects_complete=False,
                    incomplete_effect_accounting_reason="owner_interrupted_before_outcome; retained observer rows are partial")
            tempfile.tempdir = previous_tempdir
            report.update(preoperational_gate_summary=gates, attempt_number=2, retry_of_attempt_number=1,
                single_corrected_live_retry=True, retry_on_failure=False, exported_json_is_report_only=True,
                historical_sources_modified_by_operation=False, historical_attempt1_immutable=True,
                corrected_provider_source_sha256=sha256((ROOT / "core/runtime_java_pinned_provider.py").read_bytes()).hexdigest(),
                stop_boundary="Exact-provider proof and negative controls only; no SYNTH, executor, BANK or Apply.")
            handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "reason": report["reason"], "output": str(output),
        "exact_provider_proven": report["exact_provider_proven"], "runtime_authority": report.get("runtime_authority", False),
        "negative_controls": len(report.get("negative_authentication_matrix", {})),
        "all_negative_controls_rejected": report.get("all_negative_controls_rejected", False)}, indent=2))
    return 0 if report["status"] == "RUNTIME_JAVA_PINNED_1C_COMPLETE" else 2


if __name__ == "__main__":
    sys.exit(main())
