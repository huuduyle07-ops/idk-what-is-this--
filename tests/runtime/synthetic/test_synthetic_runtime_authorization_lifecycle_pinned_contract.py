"""Pure boundary contract checks; no new owner, issued handle or transition.

Inert projections exercise unchanged validator rejection only. State-table
enumeration inspects the normative document, never a live lifecycle registry.
"""
from __future__ import annotations

import ast
from copy import copy, deepcopy
from dataclasses import asdict, fields, replace
from hashlib import sha256
import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.source_layout import previous_path, read_preorganization_source, source_path

from tests._preflight_runtime1_guard import no_runtime_effects
from tests.runtime.synthetic import test_synthetic_runtime_authorization_lifecycle_pinned_compat as compat

old, pinned, lifecycle, reflection = compat.old, compat.pinned, compat.lifecycle, compat.reflection
ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1"
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
STATES = ("ISSUED", "CONSUMED", "INVALIDATED")


@pytest.fixture(autouse=True)
def pure_scope():
    registries = (old._ISSUED_HANDLES, pinned._LIVE, lifecycle._AUTHORIZATION_LEASES,
        lifecycle._LEASES, reflection._LEASES)
    before = [dict(registry) for registry in registries]
    with no_runtime_effects(strict=True) as evidence:
        yield
    assert evidence.denied_attempts == {}
    assert [dict(registry) for registry in registries] == before


def _operation(name):
    return next(item for item in CONTRACT["public_api"]["operations"] if item["name"] == name)


def _function(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _calls(node):
    return {ast.unparse(call.func) for call in ast.walk(node) if isinstance(call, ast.Call)}


def test_contract_is_additive_and_has_no_owner_implementation_or_registry_entry():
    owner = CONTRACT["proposed_owner"]
    assert CONTRACT["phase_id"] == "SYNTH.AUTH.LIFECYCLE.PINNED.CONTRACT.1"
    assert CONTRACT["implementation_authorized"] is CONTRACT["owner_implemented"] is False
    assert CONTRACT["stop_after_contract_freeze"] is True
    assert owner["owner_identity"] != lifecycle.__name__
    assert owner["phase_id"] != lifecycle.PHASE_ID
    assert owner["schema_version"] != lifecycle.SCHEMA_VERSION
    assert owner["exact_type"] != lifecycle.SyntheticRuntimeExecutionLease.__name__
    assert owner["schema_aliases"] == []
    assert not source_path(owner["owner_identity"].replace(".", "/") + ".py").exists()
    registry = (ROOT / "docs/roadmap/phase_registry.json").read_text(encoding="utf-8")
    assert owner["phase_id"] not in registry


def test_upstream_is_the_original_pinned_public_authentication_boundary():
    upstream = CONTRACT["upstream"]
    assert upstream["owner_identity"] == pinned.OWNER_ID
    assert upstream["phase_id"] == pinned.PHASE_ID
    assert upstream["schema_version"] == pinned.SCHEMA_VERSION
    assert upstream["exact_type"] == pinned.PinnedSyntheticRuntimeAuthorization.__name__
    assert upstream["mandatory_public_validator"] == pinned.OWNER_ID + ".validate_pinned_synthetic_runtime_authorization"
    assert upstream["validator_must_return_original_input"] is upstream["validator_unchanged"] is True
    assert upstream["original_authorization_retained"] is True
    assert upstream["caller_provider_input_accepted"] is False
    assert set(upstream["forbidden_bridges"]) == {
        "field_copy", "JSON_reconstruction", "old_auth_synthesis", "HMAC_copy",
        "schema_relabel", "authorization_ID_substitution"}


@pytest.mark.parametrize("kind", ("original_inert", "copy", "deepcopy", "replace", "JSON", "field_coincidence"))
def test_pinned_field_coincidence_cannot_enter_old_auth_or_old_lifecycle(kind):
    candidate = compat._pinned_projection()
    if kind == "copy":
        candidate = copy(candidate)
    elif kind == "deepcopy":
        candidate = deepcopy(candidate)
    elif kind == "replace":
        candidate = replace(candidate)
    elif kind == "JSON":
        candidate = json.loads(json.dumps(asdict(candidate)))
    elif kind == "field_coincidence":
        projection = asdict(candidate)
        projection.update(issuance_id=candidate.authorization_id,
            issuer_process_id=candidate.issuing_pid, scenario_id=candidate.scenario.scenario_id)
        candidate = SimpleNamespace(**projection)
    spec = old.executor1r_decrement_3_spec()
    source = old.get_executor1r_decrement_3_source()
    with pytest.raises(old.SyntheticRuntimeAuthorizationError) as error:
        old.validate_synthetic_runtime_authorization(candidate, spec=spec, source=source)
    assert error.value.code == "synthetic_authorization_unauthenticated"
    with pytest.raises(lifecycle.SyntheticRuntimeExecutionLeaseError) as error:
        lifecycle._authenticate_authorization(candidate)
    assert error.value.code == "synthetic_runtime_lease_upstream_authentication_failed"
    with pytest.raises(pinned.PinnedSyntheticAuthorizationError):
        pinned.validate_pinned_synthetic_runtime_authorization(candidate)


def test_exact_scenario_projection_uses_frozen_source_and_original_auth_identity():
    spec, scenario = pinned._scenario_identity()
    expected = asdict(scenario)
    expected["arguments"] = list(expected["arguments"])
    expected["argument_types"] = list(expected["argument_types"])
    assert {name: CONTRACT["scenario"][name] for name in expected} == expected
    assert CONTRACT["scenario"]["scenario_phase_id"] == spec.phase_id
    assert CONTRACT["scenario"]["source_kind"] == spec.source_kind
    assert CONTRACT["scenario"]["bind_from_authenticated_original_authorization"] is True
    assert CONTRACT["scenario"]["matching_projection_is_authenticity"] is False
    assert CONTRACT["scenario"]["source_owner"] == "core.synthetic_runtime_authorization"
    assert sha256(old.get_executor1r_decrement_3_source()).hexdigest() == expected["source_sha256"]


def test_provider_choice_B_binds_complete_existing_public_projection_and_original_graph():
    provenance = CONTRACT["provider_provenance"]
    assert provenance["decision"] == "B" and provenance["reason"]
    assert provenance["projection_source"] == "validated_original_authorization.provider"
    assert provenance["projection_exact_type"] == pinned.PinnedSyntheticProviderIdentity.__name__
    assert provenance["projection_fields"] == [item.name for item in fields(pinned.PinnedSyntheticProviderIdentity)]
    assert provenance["signed_in_immutable_lease_payload"] is True
    assert provenance["recompare_after_public_upstream_validation_on_every_operation"] is True
    assert provenance["root_phase_id"] == pinned.provider_owner.PHASE_ID
    assert provenance["root_schema_version"] == pinned.provider_owner.SCHEMA_VERSION
    assert provenance["root_owner_identity"] == pinned.provider_owner.__name__
    assert provenance["exact_provider_proven_at_authorization_issuance"] is True
    assert provenance["retained_graph_required_at_activation"] is True
    for key in ("provider_authority", "proof_is_execution_permission", "JSON_reconstruction_allowed",
            "old_JAVA_1_bridge_allowed", "private_provider_registry_access_allowed", "additional_provider_issuance_allowed"):
        assert provenance[key] is False
    assert "_authenticate_provider" in compat._calls(pinned, "validate_pinned_synthetic_runtime_authorization")
    assert "provider_owner.validate_pinned_java_exact_provider" in compat._calls(pinned, "_authenticate_provider")


def test_pinned_activation_prerequisites_are_exact_without_an_invented_readiness_owner():
    policy = CONTRACT["activation_policy"]
    requirement = pinned.REQUIREMENT
    assert (policy["requirement_profile"], policy["requirement_schema"]) == (
        requirement.java_profile_id, requirement.java_schema_version)
    assert (policy["runtime_sandbox_profile"], policy["runtime_sandbox_policy_sha256"]) == (
        requirement.sandbox_profile_id, requirement.sandbox_policy_sha256)
    assert policy["valid_original_pinned_authorization_required"] is True
    assert policy["retained_authenticated_provider_graph_required"] is True
    assert policy["provider_checks_via_mandatory_upstream_public_validator"] is True
    assert policy["identity_and_canonical_policy_digest_bound_in_lease"] is True
    assert policy["additional_runtime_readiness_evidence_owner"] is None
    assert policy["invented_runtime_readiness_token_allowed"] is False
    assert policy["lease_local_ready_implies_behavioral_ready"] is False
    assert policy["behavioral_readiness_established_by_this_phase"] is False
    assert policy["unresolved_dependency_error"] == "PROOF_UNRESOLVED"


@pytest.mark.parametrize("source,target", itertools.product(STATES, repeat=2))
def test_only_frozen_one_shot_state_transitions_are_permitted(source, target):
    table = {tuple(pair) for pair in CONTRACT["state_machine"]["transitions"]}
    assert ((source, target) in table) == (source == "ISSUED" and target in ("CONSUMED", "INVALIDATED"))


def test_tombstone_key_uses_real_pinned_authorization_ID_and_never_reopens_issuance():
    machine = CONTRACT["state_machine"]
    assert machine["states"] == list(STATES)
    assert machine["terminal_states"] == ["CONSUMED", "INVALIDATED"]
    assert machine["maximum_leases_per_authorization"] == machine["maximum_successful_terminal_transitions"] == 1
    assert machine["permanent_tombstones"] is True
    assert machine["refund_allowed"] is machine["collection_reopens_issuance"] is False
    assert machine["one_shot_key_fields"] == ["owner_identity", "phase_id", "schema_version", "issuing_pid", "authorization_id"]
    assert set(machine["one_shot_key_fields"]) <= {item.name for item in fields(pinned.PinnedSyntheticRuntimeAuthorization)}
    assert machine["fingerprint_or_proof_context_in_one_shot_key"] is machine["issuance_id_assumed"] is False
    assert machine["new_state_requires_requirement_evolution_stop"] is True


def test_atomicity_covers_authentication_signing_installation_and_terminal_recheck():
    atomicity = CONTRACT["atomicity"]
    assert atomicity["issuance_locked_sequence"] == [
        "authenticate_original_pinned_authorization_through_unchanged_public_validator",
        "derive_permanent_one_shot_key", "duplicate_issuance_check",
        "construct_lease_and_sign_immutable_payload_and_state_record",
        "install_authorization_tombstone_and_lease_record_atomically"]
    sequence = atomicity["terminal_locked_sequence"]
    assert sequence[0] == "authenticate_original_lease_and_original_upstream_through_public_validator"
    assert sequence.index("check_current_state_IS_ISSUED") < sequence.index("sign_target_terminal_record")
    assert sequence.index("check_consumer_preconditions_for_consumption_only") < sequence.index("sign_target_terminal_record")
    assert sequence[-1] == "replace_record_at_single_linearization_point"
    for name in ("wrong_PID_rejected_before_lock", "read_validation_and_readiness_under_same_lock",
            "failed_checks_or_partial_construction_publish_nothing", "failed_transition_preserves_record"):
        assert atomicity[name] is True
    assert atomicity["stale_precheck_is_reservation"] is atomicity["behavioral_effect_performed_by_owner"] is False


def test_stable_issuance_identity_and_separately_authenticated_current_state_are_complete():
    identity = CONTRACT["lease_identity"]
    required = {"phase", "schema", "owner_identity", "lease_id", "issuing_PID", "initial_state",
        "current_authenticated_state", "pinned_authorization_id", "pinned_authorization_fingerprint",
        "pinned_authorization_proof_context_id", "exact_authenticated_scenario_projection",
        "authenticated_provider_projection_B", "activation_policy_identity_and_digest",
        "authority_matrix", "lease_evidence_digest", "stable_lease_fingerprint", "private_record_signature"}
    assert set(identity["semantic_bindings"]) == required
    assert identity["stable_fingerprint_includes_current_mutable_state"] is False
    assert identity["current_state_signed_with_immutable_issuance_projection"] is True
    assert identity["original_upstream_strongly_retained"] is True
    assert identity["weak_lease_identity_and_permanent_records"] is True
    assert identity["original_upstream_mutated"] is False
    assert identity["terminal_records_remain_authenticatable_if_upstreams_authenticate"] is True


def test_owner_authentication_is_separate_and_exports_cannot_restore_capability():
    auth = CONTRACT["authentication_domain"]
    assert auth["algorithm"] == "HMAC-SHA256"
    assert auth["domain"].encode() != pinned._DOMAIN.rstrip(b"\x00")
    assert CONTRACT["proposed_owner"]["phase_id"] in auth["domain"]
    assert auth["independent_private_secret_required"] is True
    assert auth["old_or_pinned_authorization_secret_reused"] is False
    assert auth["exact_live_owner_registry_required"] is auth["original_object_required"] is True
    assert auth["wrong_PID_rejected"] is auth["JSON_exports_report_only"] is True
    assert auth["secret_signature_and_registry_exported"] is False
    assert {"copy", "deepcopy", "dataclasses.replace", "matching_constructor", "JSON", "wrapper", "subclass"} <= set(auth["rejected_inputs"])
    assert "allow_nan=false" in auth["canonical_payload"]


def test_lease_issuance_does_not_report_consumption_or_grant_effect_or_compile_authority():
    authority = CONTRACT["authority"]
    assert authority["ISSUED_projection"] == {"lease_issued": True,
        "runtime_activation_consumed": False, "one_shot_exact_synthetic_activation_capability": True}
    assert {"repository_write_authority", "apply_authority", "network_authority", "host_mount_authority",
        "shell_authority", "arbitrary_java_authority", "arbitrary_command_authority", "executor_authority",
        "BANK_authority", "reflection_execution_authority", "compilation_authority"} <= set(authority["false_in_all_states"])
    assert authority["compilation_authority"] is False
    assert authority["provider_compilation_implies_scenario_compilation_authority"] is False
    assert authority["consumption_widens_authority"] is False
    assert "authenticated current state == CONSUMED" in authority["runtime_activation_consumed_source"]


def test_behavioral_boundary_preserves_order_and_records_compile_dependency_without_new_state():
    boundary = CONTRACT["consumption_boundary"]
    assert boundary["semantic_boundary_defined"] is True
    assert "immediately before the first behavioral runtime effect" in boundary["point"]
    assert boundary["terminal_commit_precedes_effect"] is True
    assert boundary["activation_failure_after_commit_refunds"] is False
    assert boundary["never_consume_during"] == ["provider_proof_validation", "authorization_validation",
        "lease_issuance", "reflection_admission_planning", "source_inspection", "static_validation"]
    assert boundary["source_harness_readiness_before_consumption"] is True
    assert boundary["actual_source_projection_position"] == boundary["scenario_compile_position"] == "UNRESOLVED_DOWNSTREAM_DEPENDENCY"
    assert boundary["unresolved_dependency_blocks_behavioral_readiness_and_consumption"] is True
    assert boundary["new_semantic_state"] is None
    assert "JAVA.1" in lifecycle.CONSUMPTION_POLICY and "SANDBOX.2" in lifecycle.CONSUMPTION_POLICY
    assert "grants no compilation authority" in lifecycle.COMPILATION_POLICY
    order = reflection.EXECUTOR_SEQUENCE
    assert order.index("source/harness ready") < order.index("consume scenario runtime lease")
    assert order.index("consume scenario runtime lease") < order.index("perform BEFORE exact reflection read")
    assert all(item["adds_lifecycle_state"] is False for item in CONTRACT["unresolved_downstream_dependencies"])


@pytest.mark.parametrize("operation", CONTRACT["public_api"]["operations"], ids=lambda item: item["name"])
def test_every_public_operation_has_exact_types_authentication_states_atomicity_and_errors(operation):
    assert set(operation) == {"name", "inputs", "authentication", "allowed_source_states",
        "output", "mutation", "atomicity", "terminal_behavior", "errors"}
    assert operation["authentication"] and operation["atomicity"] and operation["terminal_behavior"]
    assert all(item["exact_type"] in ("PinnedSyntheticRuntimeAuthorization", "PinnedSyntheticRuntimeExecutionLease") for item in operation["inputs"])
    assert set(operation["allowed_source_states"]) <= set(STATES)
    assert set(operation["errors"]) <= set(CONTRACT["error_taxonomy"])
    assert "PROOF_UNRESOLVED" in operation["errors"]
    assert "LEASE_WRONG_PROCESS" in operation["errors"]
    assert "PINNED_AUTH_SCOPE_MISMATCH" in operation["errors"]
    assert "PINNED_PROVIDER_PROVENANCE_MISMATCH" in operation["errors"]


def test_mutating_operations_require_ISSUED_and_recheck_preconditions_without_readiness_tokens():
    consume = _operation("consume_pinned_synthetic_runtime_execution_lease")
    invalidate = _operation("invalidate_pinned_synthetic_runtime_execution_lease")
    assert consume["allowed_source_states"] == invalidate["allowed_source_states"] == ["ISSUED"]
    assert consume["mutation"] == "ISSUED -> CONSUMED"
    assert invalidate["mutation"] == "ISSUED -> INVALIDATED"
    assert all(item["required"] for item in consume["inputs"])
    assert "no caller Boolean/JSON readiness accepted" in consume["authentication"]
    assert "no consumer readiness required" in invalidate["authentication"]
    for operation in (consume, invalidate):
        assert {"LEASE_ALREADY_CONSUMED", "LEASE_INVALIDATED", "LEASE_NOT_ISSUED"} <= set(operation["errors"])
    for name in ("validate_pinned_synthetic_runtime_execution_lease", "pinned_synthetic_runtime_execution_lease_state"):
        operation = _operation(name)
        assert operation["allowed_source_states"] == list(STATES)
        assert operation["mutation"] == "none"
        assert "LEASE_ALREADY_CONSUMED" not in operation["errors"]
    readiness = _operation("check_pinned_synthetic_runtime_execution_lease_preconditions")
    assert readiness["mutation"] == "none"
    assert "not a reservation" in readiness["atomicity"]


def test_error_taxonomy_distinguishes_semantics_authentication_and_unresolved_proof():
    taxonomy = CONTRACT["error_taxonomy"]
    assert set(taxonomy) == {"PINNED_AUTH_UNAUTHENTICATED", "PINNED_AUTH_SCOPE_MISMATCH",
        "PINNED_PROVIDER_PROVENANCE_MISMATCH", "DUPLICATE_LEASE_ISSUANCE", "LEASE_UNAUTHENTICATED",
        "LEASE_WRONG_PROCESS", "LEASE_NOT_ISSUED", "LEASE_ALREADY_CONSUMED", "LEASE_INVALIDATED",
        "ACTIVATION_PRECONDITION_UNSATISFIED", "PROOF_UNRESOLVED"}
    assert "never relabeled authentication failure" in taxonomy["PINNED_AUTH_SCOPE_MISMATCH"]
    assert "projection mismatch" in taxonomy["PINNED_PROVIDER_PROVENANCE_MISMATCH"]
    assert "defined and authenticated" in taxonomy["ACTIVATION_PRECONDITION_UNSATISFIED"]
    assert "not established" in taxonomy["PROOF_UNRESOLVED"]
    assert "code and reason" in CONTRACT["public_api"]["error_type"]
    assert "forged or unknown" in taxonomy["LEASE_UNAUTHENTICATED"]
    assert "authentic terminal source states only" in taxonomy["LEASE_NOT_ISSUED"]
    delivery = CONTRACT["public_api"]["readiness_error_delivery"]
    assert "validation failures raise typed errors" in delivery
    assert "behavioral_activation_ready=false with PROOF_UNRESOLVED" in delivery
    assert "both readiness flags false" in delivery


def test_reflection_projection_is_a_future_audit_boundary_without_frozen_acceptance():
    projection = CONTRACT["reflection_projection"]
    assert {"lease_id", "stable_authenticated_lease_fingerprint", "authenticated_state_API",
        "pinned_authorization_id", "pinned_authorization_fingerprint",
        "pinned_authorization_proof_context_id", "original_pinned_authorization_binding"} <= set(projection["minimum_bindings"])
    assert projection["original_binding_observable_via_public_lease_validation_with_exact_authorization"] is True
    assert projection["reflection_compatible_projection_is_acceptance"] is False
    assert projection["frozen_reflection_acceptance_claimed"] is False
    assert projection["separate_reflection_audit_required"] is True
    assert projection["old_class_field_mimicry_is_design_goal"] is False
    assert reflection.authorization_owner is old and reflection.runtime_owner is lifecycle
    assert {"authorization_owner.validate_synthetic_runtime_authorization",
        "runtime_owner.validate_synthetic_runtime_execution_lease"} <= compat._calls(reflection, "_authenticate_inputs")
    admission = _function("core/runtime/synthetic/synthetic_reflection_execution_admission.py", "_validate_upstream_pair")
    assert "authorization_owner.validate_synthetic_runtime_authorization" in _calls(admission)


def test_old_owner_isolation_and_compatibility_declaration_are_explicit():
    assert CONTRACT["compatibility"] == {"state_machine_semantics_reused": True,
        "old_implementation_api_reused": False, "old_authorization_domain_reused": False,
        "old_lease_type_reused": False, "old_lifecycle_history_preserved": True, "pinned_owner_additive": True}
    isolation = CONTRACT["old_owner_isolation"]
    assert isolation["separate_secrets_locks_maps_records_and_types"] is True
    assert isolation["old_new_runtime_lease_interchangeable"] is False
    assert {"modify_old_lifecycle_registry", "insert_pinned_into_old_authorization_registry",
        "call_private_old_signing_helpers", "fabricate_old_SyntheticRuntimeAuthorization",
        "fabricate_old_SyntheticRuntimeExecutionLease", "change_old_CONSUMPTION_POLICY",
        "change_old_receipts_or_tombstones", "modify_old_reflection_owner", "repin_history",
        "stash", "reset", "clean"} == set(isolation["prohibited"])


def test_existing_owner_and_registry_bytes_match_precontract_baseline():
    baseline = json.loads((HERE / "preservation_baseline.json").read_text(encoding="utf-8"))["files"]
    names = ["core/runtime/synthetic/synthetic_runtime_authorization.py", "core/runtime/synthetic/synthetic_runtime_authorization_pinned.py",
        "core/runtime/synthetic/synthetic_runtime_authorization_lifecycle.py", "core/runtime/synthetic/synthetic_read_only_reflection.py",
        "core/runtime/synthetic/synthetic_reflection_execution_admission.py", "core/runtime/synthetic/synthetic_reflection_execution_lifecycle.py",
        "core/phase_registry.py", "docs/roadmap/phase_registry.json"]
    names.extend(name for name in baseline if name.startswith("core/runtime_java_pinned") and name.endswith(".py"))
    for name in names:
        content = read_preorganization_source(name)
        name = previous_path(name)
        assert sha256(content).hexdigest() == baseline[name]["sha256"], name


def test_historical_executor_stops_and_no_effectful_runner_are_preserved_by_source_inspection():
    historical = (ROOT / "core/behavioral_diagnostic_executor_lifecycle_retry.py").read_text(encoding="utf-8")
    assert "java_profile_contract_mismatch" in historical
    assert "infrastructure_contract_changed_requires_review" in historical
    assert "No effectful runner is implemented" in historical
    policy = _function("core/behavioral_diagnostic_executor_lifecycle_retry.py", "java_profile_contract_audit")
    assert "JAVA.1" in ast.unparse(policy) or "required_java_profile" in ast.unparse(policy)


def test_all_operational_effects_are_zero_and_all_new_artifacts_remain_report_only():
    effects = CONTRACT["operational_effects"]
    assert set(effects) == {"Docker", "SANDBOX2", "JAVA1C", "PINNED_provider_issuance",
        "authorization_issuance", "execution_lease_issuance", "lease_consumption", "lease_invalidation",
        "SyntheticStateBox", "reflection", "BANK", "EXECUTOR.1R", "Apply", "repository_runtime_writes"}
    assert all(type(count) is int and count == 0 for count in effects.values())
    assert CONTRACT["public_api"]["conceptual_only"] is True
    assert CONTRACT["artifact_kind"] == "normative_semantic_contract_report_only"
    assert "documentation and validation artifacts" in CONTRACT["effect_scope"]
    document = (HERE / "SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1.md").read_text(encoding="utf-8")
    assert "Authorization issuance != lease issuance != lease consumption != behavior" in document
    assert "Reflection-compatible projection != reflection" in document
