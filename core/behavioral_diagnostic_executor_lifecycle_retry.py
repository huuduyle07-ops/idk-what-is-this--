"""EXECUTOR.1R lifecycle-closed retry; stop at the frozen Java profile conflict.

This additive gate issues one activation and two subordinate read leases. It
never aliases JAVA.1C to JAVA.1, signs infrastructure evidence, or launches an
executor behind an incompatible contract. Historical blocked retries stay frozen.
"""
from dataclasses import dataclass, fields

from core import behavioral_diagnostic_executor_retry as historical
from core.runtime.synthetic import synthetic_runtime_authorization as authorization
from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as runtime
from core.runtime.synthetic import synthetic_read_only_reflection as reflection
from core.runtime.synthetic import synthetic_reflection_execution_admission as admission
from core.runtime.synthetic import synthetic_reflection_execution_lifecycle as reflection_lifecycle
from core import sandboxed_java_toolchain as java1
from core import sandboxed_java_positive_continuation as java1c
from core import thread_compatible_runtime_sandbox as sandbox2

PHASE_ID = authorization.SCENARIO_PHASE_ID
SCHEMA_VERSION = "patch_candidate_behavior_executor_1r_lifecycle_retry_v1"
BLOCKED = historical.BLOCKED_UNRESOLVED


@dataclass(frozen=True, slots=True)
class ExecutorAuthorityGraph:
    """Container of live owner handles, with no independent authority."""
    authorization: authorization.SyntheticRuntimeAuthorization
    runtime_lease: runtime.SyntheticRuntimeExecutionLease
    before_request: reflection.SyntheticReflectionRequest
    after_request: reflection.SyntheticReflectionRequest
    before_admission: admission.SyntheticReflectionExecutionAdmission
    after_admission: admission.SyntheticReflectionExecutionAdmission
    before_lease: reflection_lifecycle.SyntheticReflectionExecutionLease
    after_lease: reflection_lifecycle.SyntheticReflectionExecutionLease


def validate_authority_graph(graph):
    """Authenticate eight live objects and both pure pre-execution predicates."""
    try:
        if type(graph) is not ExecutorAuthorityGraph:
            raise ValueError("exact typed graph of live owner handles required")
        auth, lease = graph.authorization, graph.runtime_lease
        historical.validate_shared_authorization(auth, graph.before_request,
            graph.after_request, graph.before_admission, graph.after_admission)
        runtime.validate_synthetic_runtime_execution_lease(lease, auth)
        if (lease.lifecycle_state != runtime.ISSUED
                or runtime.synthetic_runtime_execution_lease_satisfies_executor(lease, auth) is not True):
            raise ValueError("one ISSUED runtime execution lease required")
        for label, role in (("before", reflection.BEFORE_ROLE), ("after", reflection.AFTER_ROLE)):
            request = getattr(graph, label + "_request")
            grant = getattr(graph, label + "_admission")
            read = getattr(graph, label + "_lease")
            reflection_lifecycle.validate_synthetic_reflection_execution_lease(read)
            if (read.lifecycle_state != reflection_lifecycle.ISSUED
                    or read.runtime_execution_lease_id != lease.lease_id
                    or read.runtime_execution_lease_fingerprint != lease.fingerprint
                    or read.upstream_authorization_issuance_id != auth.issuance_id
                    or read.upstream_authorization_fingerprint != auth.fingerprint
                    or reflection_lifecycle.synthetic_reflection_execution_lease_satisfies_executor(
                        read, grant, request, lease, auth, observation_role=role) is not True):
                raise ValueError("both exact ISSUED reads must bind the same live activation")
        if graph.before_lease.lease_id == graph.after_lease.lease_id:
            raise ValueError("distinct BEFORE and AFTER leases required")
    except Exception as error:
        raise historical.ExecutorRetryGateError(historical.BLOCKED_AUTH_COHERENCE,
            str(error)) from error
    return graph


def java_profile_contract_audit():
    """Pure contract inspection, never fresh capability authentication.

    Inspect the actual frozen descriptor/receipt schema defaults and the policy
    bound into JAVA.1 receipts. JAVA.1C's public predicate covers its own live
    SANDBOX.2 pair; it does not assert the exact SYNTH.AUTH.1 Java profile/schema.
    No unsigned descriptor, saved report, or reconstructed receipt is used here.
    """
    def defaults(kind):
        return {f.name: f.default for f in fields(kind)
            if f.name in ("phase_id", "schema_version", "seccomp_policy_sha256")}
    required = {"phase_id": authorization.JAVA_PROFILE_ID,
        "schema_version": authorization.JAVA_SCHEMA_VERSION,
        "seccomp_policy_sha256": authorization.SANDBOX_POLICY_SHA256}
    original = defaults(java1.SandboxedJavaToolchainVerificationReceipt)
    continuation = defaults(java1c.JavaContinuationReceipt)
    original_descriptor = defaults(java1.SandboxedJavaToolchainDescriptor)
    continuation_descriptor = defaults(java1c.JavaContinuationDescriptor)
    original_matches = original == required
    continuation_matches = continuation == required
    return {"required": required, "java1_receipt_contract": original,
        "java1_descriptor_contract": original_descriptor,
        "java1_sandbox_owner_phase_id": java1.sandbox.PHASE_ID,
        "java1_sandbox_owner_schema_version": java1.sandbox.SCHEMA_VERSION,
        "java1c_receipt_contract": continuation,
        "java1c_descriptor_contract": continuation_descriptor,
        "sandbox2_policy_sha256": sandbox2.POLICY_SHA256,
        "original_profile_matches_required_policy": original_matches,
        "continuation_profile_matches_required_contract": continuation_matches,
        "compatible_frozen_contract_found": original_matches or continuation_matches,
        "inspection_only": True, "capabilities_authenticated": False,
        "profile_alias_inferred": False,
        "owner_compatibility_predicates": [
            "core.sandboxed_java_toolchain.java_toolchain_satisfies_executor_runtime",
            "core.sandboxed_java_positive_continuation.java_toolchain_satisfies_executor_runtime"],
        "conflict": "JAVA.1 binds SANDBOX.1 policy; SANDBOX.2 continuation has JAVA.1C schema"}


def _empty_report():
    result = {"phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION,
        "scenario_id": authorization.SCENARIO_ID, "status": BLOCKED,
        "report_only": True, "exported_json_can_recreate_authority": False,
        "source_sha256": authorization.SOURCE_SHA256, "source_size_bytes": authorization.SOURCE_SIZE_BYTES,
        "fixture_expectations": {"before": 10, "return": True, "after": 7},
        "authority_graph_authenticated": False, "same_activation_proven": False,
        "source_projected": False, "harness_rendered": False,
        "positive_runtime_receipt_issued": False, "execution_completed": False,
        "sandbox2_authentication": "not_attempted_java_contract_gate_blocked",
        "java1_authentication": "not_attempted_java_contract_gate_blocked",
        "java_compatibility": "not_evaluated", "compilation_boundary": runtime.COMPILATION_POLICY,
        "cleanup_outcome": "not_required_no_runtime_resources_created",
        "remaining_phase_containers_measurement": "not_queried_no_container_effects",
        "output_bound_result": "not_measured_no_runtime", "historical_executor_relabelled": False,
        "bank_oracle_reduced": False}
    for name in ("scenario_authorization", "runtime_execution_lease", "before_request", "after_request",
            "before_admission", "after_admission", "before_reflection_lease", "after_reflection_lease",
            "runtime_lease_initial_state", "runtime_lease_final_state",
            "before_lease_initial_state", "before_lease_final_state", "after_lease_initial_state",
            "after_lease_final_state", "harness_sha256", "compile_argv", "compile_stage",
            "class_manifest", "runtime_argv", "runtime_stage", "runtime_consumption_point",
            "before_consumption_point", "after_consumption_point", "measured_observations",
            "measured_before", "measured_direct_return", "measured_after", "fixture_expectation_comparison",
            "timed_out", "compiler_reaped", "jvm_reaped", "remaining_phase_containers",
            "positive_runtime_receipt", "positive_runtime_receipt_fingerprint"):
        result[name] = None
    for name in ("synthetic_runtime_authorizations_issued", "runtime_execution_leases_issued",
            "runtime_execution_leases_consumed", "before_reflection_leases_issued",
            "before_reflection_leases_consumed", "after_reflection_leases_issued",
            "after_reflection_leases_consumed", "reflection_execution_count", "public_method_invocation_count",
            "synthetic_behavioral_execution_count", "bank_execution_count", "real_behavioral_execution_count",
            "real_runtime_authorizations_consumed", "compile_count", "jvm_execution_count",
            "controller_thread_start_attempts", "phase_containers_created", "docker_calls",
            "host_java_artifacts_created", "repository_writes", "apply_actions", "network_calls",
            "console_count", "pty_count", "model_calls", "author_calls", "shell_calls", "child_processes"):
        result[name] = 0
    for name in ("runtime_authority", "real_task_runtime_authority", "repository_write_authority",
            "apply_authority", "network_authority", "host_mount_authority", "shell_authority",
            "arbitrary_command_authority", "generic_reflection_authority", "field_write_authority",
            "enumeration_authority", "private_method_authority", "constructor_reflection_authority",
            "arbitrary_class_loading_authority"):
        result[name] = False
    return result


def verify():
    """One fresh graph; stop before infrastructure, consumption or projection.

    No effectful runner is implemented while the exact frozen infrastructure
    contract is incompatible. Even a changed audit cannot silently activate it.
    """
    report, handles = _empty_report(), {}
    try:
        source = authorization.get_executor1r_decrement_3_source()
        spec = authorization.executor1r_decrement_3_spec()
        auth = authorization.issue_synthetic_runtime_authorization(spec, source=source)
        handles["authorization"] = auth
        report["synthetic_runtime_authorizations_issued"] = 1
        authorization.validate_synthetic_runtime_authorization(auth, spec=spec, source=source)
        report["scenario_authorization"] = auth.as_dict()
        lease = runtime.issue_synthetic_runtime_execution_lease(auth)
        handles["runtime_lease"] = lease
        report["runtime_execution_leases_issued"] = 1
        runtime.validate_synthetic_runtime_execution_lease(lease, auth)
        report["runtime_lease_initial_state"] = lease.lifecycle_state
        for label, role, factory in (("before", reflection.BEFORE_ROLE, reflection.executor1r_before_request),
                ("after", reflection.AFTER_ROLE, reflection.executor1r_after_request)):
            request = factory()
            handles[label + "_request"] = reflection.validate_synthetic_reflection_request(request)
            report[label + "_request"] = request.as_dict()
            grant = admission.issue_synthetic_reflection_execution_admission(auth, request)
            handles[label + "_admission"] = admission.validate_synthetic_reflection_execution_admission(grant)
            report[label + "_admission"] = grant.as_dict()
            read = reflection_lifecycle.issue_synthetic_reflection_execution_lease(
                grant, request, lease, auth, observation_role=role)
            handles[label + "_lease"] = read
            report[label + "_reflection_leases_issued"] = 1
            reflection_lifecycle.validate_synthetic_reflection_execution_lease(read)
            report[label + "_lease_initial_state"] = read.lifecycle_state
        graph = validate_authority_graph(ExecutorAuthorityGraph(**handles))
        report.update(authority_graph_authenticated=True, same_activation_proven=True,
            shared_authorization_issuance_id=auth.issuance_id,
            shared_authorization_fingerprint=auth.fingerprint,
            shared_runtime_execution_lease_id=lease.lease_id,
            shared_runtime_execution_lease_fingerprint=lease.fingerprint,
            preexecution_compatibility={"runtime": True, "before": True, "after": True})
        audit = java_profile_contract_audit()
        report["java_contract_audit"] = audit
        report["java_compatibility"] = "incompatible_frozen_profile_contract"
        report.update(reason="java_profile_contract_mismatch", infrastructure_blocker=java1.INCOMPATIBLE,
            error="Required JAVA.1 schema/policy pair has no compatible frozen SANDBOX.2 issuer")
        if audit["compatible_frozen_contract_found"]:
            report.update(reason="infrastructure_contract_changed_requires_review",
                java_compatibility="not_authenticated_contract_changed")
        # Retain the graph until the last public owner validation has completed.
        validate_authority_graph(graph)
    except Exception as error:
        report.update(status=getattr(error, "code", BLOCKED)
            if isinstance(error, historical.ExecutorRetryGateError) else BLOCKED,
            reason="preexecution_authentication_failed", error_code=getattr(error, "code", type(error).__name__),
            error=str(error))
    finally:
        for label, key in (("runtime", "runtime_lease"), ("before", "before_lease"), ("after", "after_lease")):
            if key not in handles:
                continue
            try:
                lease = handles[key]
                if label == "runtime":
                    runtime.validate_synthetic_runtime_execution_lease(lease, handles["authorization"])
                    report["runtime_execution_lease"] = lease.as_dict()
                else:
                    reflection_lifecycle.validate_synthetic_reflection_execution_lease(lease)
                    report[label + "_reflection_lease"] = lease.as_dict()
                report[label + "_lease_final_state"] = lease.lifecycle_state
            except Exception as error:
                report.update(status=BLOCKED, reason="final_lease_authentication_failed", error=str(error))
    return report
