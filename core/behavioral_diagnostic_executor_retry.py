"""EXECUTOR.1R additive retry: shared live authority, then lifecycle stop.

The frozen SYNTH.AUTH.1 owner has no public consumption contract. This slice
must stop before infrastructure refresh, projection, compilation or execution.
It does not implement an executor-local substitute for upstream consumption.
"""
from __future__ import annotations

from core.runtime.synthetic import synthetic_read_only_reflection as reflection
from core.runtime.synthetic import synthetic_reflection_execution_admission as admission
from core.runtime.synthetic import synthetic_runtime_authorization as authorization

PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SCHEMA_VERSION = "patch_candidate_behavior_executor_1r_retry_v1"
BLOCKED_AUTH_COHERENCE = "PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_BLOCKED_AUTH_COHERENCE"
BLOCKED_AUTH_LIFECYCLE = "PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_BLOCKED_AUTH_LIFECYCLE"
BLOCKED_UNRESOLVED = "PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_BLOCKED_UNRESOLVED"


class ExecutorRetryGateError(ValueError):
    def __init__(self, code, reason):
        self.code, self.reason = code, reason
        super().__init__(code + ": " + reason)


def validate_shared_authorization(auth, before_request, after_request,
        before_admission, after_admission):
    """Reauthenticate all five live objects; exports and copies cannot pass."""
    try:
        spec = authorization.executor1r_decrement_3_spec()
        authorization.validate_synthetic_runtime_authorization(auth, spec=spec,
            source=authorization.get_executor1r_decrement_3_source())
        for request, grant, role in (
                (before_request, before_admission, reflection.BEFORE_ROLE),
                (after_request, after_admission, reflection.AFTER_ROLE)):
            reflection.validate_synthetic_reflection_request(request)
            admission.validate_synthetic_reflection_execution_admission(grant)
            if (request.observation_role != role or grant.observation_role != role
                    or grant.synthetic_authorization_issuance_id != auth.issuance_id
                    or grant.synthetic_authorization_fingerprint != auth.fingerprint
                    or grant.reflection_request_issuance_id != request.issuance_id
                    or grant.reflection_request_fingerprint != request.fingerprint
                    or admission.synthetic_reflection_admission_satisfies_executor(
                        grant, auth, request) is not True):
                raise ValueError("exact live role and shared authorization binding required")
        if (before_request.issuance_id == after_request.issuance_id
                or before_admission.admission_id == after_admission.admission_id):
            raise ValueError("distinct role requests and admissions required")
    except Exception as error:
        raise ExecutorRetryGateError(BLOCKED_AUTH_COHERENCE,
            str(error)) from error
    return auth


def _empty_report():
    report = {
        "phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION,
        "scenario_id": authorization.SCENARIO_ID,
        "report_only": True, "exported_json_is_report_only": True,
        "exported_json_can_recreate_authority": False,
        "scenario_authorization": None, "before_request": None,
        "after_request": None, "before_admission": None, "after_admission": None,
        "exactly_one_scenario_authorization_used": False,
        "shared_authorization_coherence": False,
        "synthetic_authorization_authenticated_in_issuing_process": False,
        "reflection_requests_authenticated_in_issuing_process": False,
        "reflection_admissions_authenticated_in_issuing_process": False,
        "runtime_authorization_state": None,
        "before_admission_consumption_state": None,
        "after_admission_consumption_state": None,
        "source_sha256": authorization.SOURCE_SHA256,
        "source_size_bytes": authorization.SOURCE_SIZE_BYTES,
        "source_projected": False, "harness_rendered": False,
        "harness_sha256": None, "class_manifest": None,
        "compile_stage": None, "runtime_stage": None,
        "measured_observations": None, "measured_before": None,
        "measured_direct_return": None, "measured_after": None,
        "fixture_expectations": {"before": 10, "return": True, "after": 7},
        "fixture_expectation_comparison": None,
        "positive_runtime_receipt": None, "positive_runtime_receipt_fingerprint": None,
        "positive_runtime_receipt_issued": False, "execution_completed": False,
        "sandbox2_authentication": "not_attempted_pre_execution_gate",
        "java1_authentication": "not_attempted_pre_execution_gate",
        "java_compatibility": "not_evaluated_pre_execution_gate",
        "required_java_profile_id": authorization.JAVA_PROFILE_ID,
        "required_java_schema_version": authorization.JAVA_SCHEMA_VERSION,
        "controller_thread_count": None, "timed_out": None,
        "output_bound_result": "not_measured_no_runtime",
        "remaining_phase_containers": None,
        "remaining_phase_containers_measurement": "not_queried_no_container_effects",
        "cleanup_outcome": "not_required_no_runtime_resources_created",
        "compiler_reaped": None, "jvm_reaped": None,
        "bank_oracle_reduced": False, "historical_executor_relabelled": False,
        "reflection_consumption_implemented": False,
        "runtime_consumption_implemented": False,
    }
    for name in (
            "synthetic_runtime_authorizations_issued",
            "synthetic_runtime_authorizations_consumed",
            "real_runtime_authorizations_consumed",
            "before_reflection_admissions_consumed", "after_reflection_admissions_consumed",
            "reflection_admissions_consumed", "reflection_execution_count",
            "public_method_invocation_count", "synthetic_behavioral_execution_count",
            "bank_execution_count", "real_behavioral_execution_count",
            "compile_count", "jvm_execution_count", "console_count", "network_calls",
            "repository_writes", "apply_actions", "model_calls", "author_calls",
            "controller_thread_start_attempts", "phase_containers_created",
            "host_java_artifacts_created", "docker_calls", "shell_calls", "child_processes"):
        report[name] = 0
    for name in (
            "runtime_authority", "real_task_runtime_authority", "real_human_approval",
            "real_session_consumed", "repository_write_authority", "apply_authority",
            "network_authority", "host_mount_authority", "shell_authority",
            "arbitrary_command_authority", "generic_reflection_authority",
            "field_write_authority", "enumeration_authority", "private_method_authority"):
        report[name] = False
    return report


def verify():
    """Issue one scenario handle and both role admissions; stop without consuming.

    Compilation and runtime are unreachable. The immutable upstream handle
    authenticates only its issued state; a local counter could not establish
    owner-authenticated consumption. A separate lifecycle-owner change is needed.
    """
    report = _empty_report()
    try:
        spec = authorization.executor1r_decrement_3_spec()
        source = authorization.get_executor1r_decrement_3_source()
        auth = authorization.issue_synthetic_runtime_authorization(spec, source=source)
        report["synthetic_runtime_authorizations_issued"] = 1
        authorization.validate_synthetic_runtime_authorization(auth, spec=spec, source=source)
        report["scenario_authorization"] = auth.as_dict()
        report["runtime_authorization_state"] = auth.status
        report["exactly_one_scenario_authorization_used"] = True
        report["synthetic_authorization_authenticated_in_issuing_process"] = True
        before = reflection.executor1r_before_request()
        after = reflection.executor1r_after_request()
        reflection.validate_synthetic_reflection_request(before)
        reflection.validate_synthetic_reflection_request(after)
        report["before_request"], report["after_request"] = before.as_dict(), after.as_dict()
        report["reflection_requests_authenticated_in_issuing_process"] = True
    except Exception as error:
        report.update(status=BLOCKED_UNRESOLVED, reason="upstream_authentication_failed",
            error_code=getattr(error, "code", type(error).__name__), error=str(error))
        return report

    try:
        # Never call admission.verify(): that frozen proof issues two authorizations.
        before_grant = admission.issue_synthetic_reflection_execution_admission(auth, before)
        admission.validate_synthetic_reflection_execution_admission(before_grant)
        report["before_admission"] = before_grant.as_dict()
        report["before_admission_consumption_state"] = before_grant.consumption_state
        after_grant = admission.issue_synthetic_reflection_execution_admission(auth, after)
        admission.validate_synthetic_reflection_execution_admission(after_grant)
        report["after_admission"] = after_grant.as_dict()
        report["after_admission_consumption_state"] = after_grant.consumption_state
        report["reflection_admissions_authenticated_in_issuing_process"] = True
        validate_shared_authorization(auth, before, after, before_grant, after_grant)
    except Exception as error:
        report.update(status=BLOCKED_AUTH_COHERENCE,
            reason="both_role_admissions_could_not_bind_one_live_authorization",
            error_code=getattr(error, "code", type(error).__name__), error=str(error))
        return report

    report["shared_authorization_coherence"] = True
    report["shared_authorization_proof"] = {
        "scenario_authorization_issuance_id": auth.issuance_id,
        "before_authorization_issuance_id": before_grant.synthetic_authorization_issuance_id,
        "after_authorization_issuance_id": after_grant.synthetic_authorization_issuance_id,
        "same_live_object_passed_to_both_issuers": True,
        "both_public_executor_compatibility_checks_passed": True,
    }
    report.update(status=BLOCKED_AUTH_LIFECYCLE,
        reason="frozen_synth_auth_1_has_no_public_consumption_contract",
        lifecycle_evidence={
            "owner_phase_id": authorization.PHASE_ID,
            "owner_schema_version": authorization.AUTHORIZATION_SCHEMA_VERSION,
            "owner_public_functions": sorted(name for name, value in vars(authorization).items()
                if not name.startswith("_") and callable(value)
                and getattr(value, "__module__", None) == authorization.__name__
                and not isinstance(value, type)),
            "owner_consumption_api": None,
            "owner_authenticated_state": auth.status,
            "owner_authenticated_consumed_count": auth.synthetic_runtime_authorizations_consumed,
            "consumption_point": None,
            "executor_local_substitute_permitted": False,
            "next_dependency": "separate owner-defined single-use synthetic runtime lifecycle",
        })
    return report
