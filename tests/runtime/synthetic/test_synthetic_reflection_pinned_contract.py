"""Pure source/AST checks for the additive pinned reflection contract.

No capability owner is imported or called. State-table cases inspect the
normative JSON only; no requests, admissions, leases or effects are created.
"""
from __future__ import annotations

import ast
from hashlib import sha256
import itertools
import json
from pathlib import Path

import pytest

from scripts.source_layout import previous_path, read_preorganization_source, source_path


ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "docs/roadmap/phases/SYNTH_REFLECT_PINNED_CONTRACT_1"
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
STATES = ("ISSUED", "CONSUMED", "INVALIDATED")
ROLES = ("BEFORE", "AFTER")
PRIMITIVE = "core/runtime/synthetic/synthetic_read_only_reflection.py"
OLD_AUTH = "core/runtime/synthetic/synthetic_runtime_authorization.py"
OLD_RUNTIME = "core/runtime/synthetic/synthetic_runtime_authorization_lifecycle.py"
PINNED_AUTH = "core/runtime/synthetic/synthetic_runtime_authorization_pinned.py"
PINNED_RUNTIME = "core/runtime/synthetic/synthetic_runtime_authorization_pinned_lifecycle.py"
OLD_ADMISSION = "core/runtime/synthetic/synthetic_reflection_execution_admission.py"
OLD_REFLECTION = "core/runtime/synthetic/synthetic_reflection_execution_lifecycle.py"
PUBLIC_VALIDATORS = [
    "core.synthetic_runtime_authorization_pinned.validate_pinned_synthetic_runtime_authorization",
    "core.synthetic_runtime_authorization_pinned_lifecycle.validate_pinned_synthetic_runtime_execution_lease",
]


def _tree(path):
    return ast.parse((ROOT / path).read_text(encoding="utf-8"))


def _function(path, name):
    return next(node for node in _tree(path).body
        if isinstance(node, ast.FunctionDef) and node.name == name)


def _calls(node):
    return {ast.unparse(call.func) for call in ast.walk(node) if isinstance(call, ast.Call)}


def _constant(path, name):
    for node in _tree(path).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
                if isinstance(target, ast.Tuple) and any(
                        isinstance(item, ast.Name) and item.id == name for item in target.elts):
                    values = ast.literal_eval(node.value)
                    return values[next(index for index, item in enumerate(target.elts)
                        if isinstance(item, ast.Name) and item.id == name)]
    raise AssertionError((path, name))


def _class_fields(path, name):
    node = next(node for node in _tree(path).body
        if isinstance(node, ast.ClassDef) and node.name == name)
    return {item.target.id for item in node.body if isinstance(item, ast.AnnAssign)
        and isinstance(item.target, ast.Name)}


def _operation(group, name):
    return next(item for item in CONTRACT["conceptual_public_api"][group] if item["name"] == name)


def test_new_tests_import_no_capability_owner_or_dynamic_execution_api():
    tree = _tree("tests/runtime/synthetic/test_synthetic_reflection_pinned_contract.py")
    roots = {node.names[0].name.split(".")[0] for node in ast.walk(tree)
        if isinstance(node, ast.Import)}
    roots.update(node.module.split(".")[0] for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom))
    assert roots == {"__future__", "ast", "hashlib", "itertools", "json", "pathlib", "pytest", "scripts"}
    assert not _calls(tree) & {"__import__", "eval", "exec", "importlib.import_module"}
    assert CONTRACT["validation_policy"]["pure_source_AST_only"] is True
    assert CONTRACT["validation_policy"]["capability_modules_imported_by_new_contract_tests"] is False
    assert CONTRACT["validation_policy"]["issuance_dependent_suites_allowed"] is False


def test_contract_freezes_semantics_and_creates_no_owners_types_or_registry_entries():
    assert CONTRACT["phase_id"] == "SYNTH.REFLECT.PINNED.CONTRACT.1"
    assert CONTRACT["artifact_kind"] == "normative_semantic_contract_report_only"
    assert CONTRACT["completion_marker"] == "SYNTH_REFLECT_PINNED_CONTRACT_1_COMPLETE"
    assert CONTRACT["unresolved_marker"] == "CONTRACT_UNRESOLVED"
    for name in ("implementation_authorized", "adapter_implemented", "capabilities_created"):
        assert CONTRACT[name] is False
    assert CONTRACT["stop_after_contract_freeze"] is True
    registry = (ROOT / "docs/roadmap/phase_registry.json").read_text(encoding="utf-8")
    for group, old_path, old_type in (
            ("admission_owner", OLD_ADMISSION, "SyntheticReflectionExecutionAdmission"),
            ("lifecycle_owner", OLD_REFLECTION, "SyntheticReflectionExecutionLease")):
        owner = CONTRACT[group]
        assert owner["implemented"] is owner["registered_in_phase_registry"] is False
        assert owner["schema_aliases"] == []
        assert owner["owner_identity"] != previous_path(old_path).removesuffix(".py").replace("/", ".")
        assert owner["exact_type"] != old_type
        assert owner["phase_id"] != _constant(old_path, "PHASE_ID")
        assert owner["schema_version"] != _constant(old_path, "SCHEMA_VERSION")
        assert owner["phase_id"] not in registry
        assert not source_path(owner["owner_identity"].replace(".", "/") + ".py").exists()
    assert CONTRACT["admission_owner"]["owner_identity"] != CONTRACT["lifecycle_owner"]["owner_identity"]


def test_exact_primitive_source_definition_roles_and_invocation_remain_frozen():
    primitive = CONTRACT["primitive"]
    source = _constant(OLD_AUTH, "_SOURCE")
    assert type(source) is bytes and len(source) == primitive["source_size_bytes"] == 239
    assert sha256(source).hexdigest() == primitive["source_sha256"] == _constant(PRIMITIVE, "SOURCE_SHA256")
    assert source[36:59] == b"private int value = 10;"
    assert sha256(source[36:59]).hexdigest() == primitive["definition_sha256"] == _constant(PRIMITIVE, "DEFINITION_SHA256")
    assert primitive["scenario_id"] == _constant(PRIMITIVE, "SCENARIO_ID")
    assert primitive["scenario_phase_id"] == _constant(PRIMITIVE, "SCENARIO_PHASE_ID")
    assert primitive["source_kind"] == _constant(PRIMITIVE, "SOURCE_KIND")
    assert (primitive["field_owner"], primitive["field_name"], primitive["field_type"], primitive["operation"]) == (
        "SyntheticStateBox", "value", "int", "read_exact_bound_field")
    assert primitive["roles"] == {"BEFORE": _constant(PRIMITIVE, "BEFORE_ROLE"),
        "AFTER": _constant(PRIMITIVE, "AFTER_ROLE")}
    assert primitive["invocation"] == {"owner": "SyntheticStateBox", "public_method": "decrement",
        "method_signature": "boolean SyntheticStateBox.decrement(int)", "arguments": [3],
        "argument_types": ["int"], "return_type": "boolean"}
    assert primitive["expected_observations"] == {"BEFORE": 10, "public_return": True, "AFTER": 7}
    assert primitive["semantics_unchanged"] is True
    assert primitive["second_primitive_created"] is primitive["semantic_equality_is_authorization_compatibility"] is False


@pytest.mark.parametrize("helper_name", ("_BEFORE_HELPER", "_AFTER_HELPER"))
def test_frozen_helpers_observe_only_one_exact_field(helper_name):
    helper = _constant(PRIMITIVE, helper_name)
    assert "Class<?> owner = SyntheticStateBox.class;" in helper
    assert 'owner.getDeclaredField("value")' in helper
    assert "field.setAccessible(true);" in helper
    assert "int observed = field.getInt(instance);" in helper
    assert all(token not in helper for token in ("authorization", "lease", "provider", "decrement",
        "getDeclaredFields", "setInt", "getDeclaredMethods", "getDeclaredConstructors", "Class.forName"))


def test_request_reuse_A_is_supported_by_independent_payload_validation_and_renderer():
    decision = CONTRACT["request_reuse"]
    assert decision["decision"] == "A"
    assert decision["exact_type"] == "SyntheticReflectionRequest"
    assert decision["schema_version"] == _constant(PRIMITIVE, "SCHEMA_VERSION")
    assert decision["mandatory_public_validator"] == "core.synthetic_read_only_reflection.validate_synthetic_reflection_request"
    assert decision["request_phase_id"] == _constant(PRIMITIVE, "SCENARIO_PHASE_ID")
    fields = _class_fields(PRIMITIVE, "SyntheticReflectionRequest")
    assert {"issuance_id", "issuer_process_id", "scenario_id", "source_sha256", "definition_sha256",
        "owner", "member", "declared_type", "operation", "observation_role"} <= fields
    assert not any(name.endswith(("authorization_id", "authorization_issuance_id")) for name in fields)
    assert decision["request_payload_embeds_old_authorization_identity"] is False
    assert decision["new_request_type_defined"] is decision["request_bytes_changed"] is False
    assert decision["request_issuance_authorized_in_this_phase"] is False
    assert decision["old_compatibility_predicate_unchanged"] is True
    assert decision["old_compatibility_predicate_used_for_pinned"] is decision["new_predicate_is_authority"] is False
    assert decision["new_compatibility_predicate_owner"] == CONTRACT["admission_owner"]["owner_identity"]
    assert _calls(_function(PRIMITIVE, "render_synthetic_read_only_reflection")) == {"validate_synthetic_reflection_request"}
    old_predicate = ast.unparse(_function(PRIMITIVE, "synthetic_reflection_satisfies_authorization"))
    assert "type(synthetic_authorization) is not authorization_owner.SyntheticRuntimeAuthorization" in old_predicate
    assert "authorization_owner.validate_synthetic_runtime_authorization" in _calls(
        _function(PRIMITIVE, "synthetic_reflection_satisfies_authorization"))


def test_fixed_request_fingerprint_does_not_replace_original_request_identity():
    payload = ast.unparse(_function(PRIMITIVE, "_contract_payload"))
    assert "'issuance_id'" in payload and "'issuer_process_id'" in payload
    validator = ast.unparse(_function(PRIMITIVE, "validate_synthetic_reflection_request"))
    assert "type(request) is not SyntheticReflectionRequest" in validator
    assert "_ISSUED_REQUESTS.get(request.issuance_id) is not request" in validator
    assert "request.issuer_process_id != _ISSUER_PID" in validator
    assert CONTRACT["request_reuse"]["fingerprint_is_fixed_per_role_not_original_request_identity"] is True
    assert CONTRACT["upstream_graph"]["original_request_strongly_retained"] is True
    assert "original_request_issuance_id_PID_and_authenticated_fingerprint" in CONTRACT["admission_identity"]["minimum_signed_bindings"]
    renderer = CONTRACT["renderer_binding"]
    assert renderer["required"] is True
    assert renderer["renderer_identity"] == _constant(OLD_ADMISSION, "RENDERER_IDENTITY")
    assert renderer["renderer_phase"] == _constant(PRIMITIVE, "PHASE_ID")
    assert renderer["old_private_signing_or_hash_helpers_used"] is False
    assert renderer["text_output_is_read_evidence"] is renderer["rendering_grants_compilation_authority"] is False


def test_original_pinned_graph_is_reauthenticated_through_both_unchanged_public_validators():
    upstream = CONTRACT["upstream_graph"]
    assert upstream["public_validators"] == PUBLIC_VALIDATORS
    for name in ("validators_unchanged", "public_validators_on_every_admission_operation",
            "public_validators_on_every_lifecycle_operation", "exact_original_objects_required",
            "validator_must_return_original_input", "original_authorization_strongly_retained",
            "original_runtime_strongly_retained", "original_request_strongly_retained",
            "original_admission_strongly_retained_by_lease", "supplied_authorization_must_be_retained_original",
            "supplied_runtime_request_admission_must_be_retained_originals", "omitted_inputs_use_retained_originals"):
        assert upstream[name] is True
    assert upstream["authorization_identity_field"] == "authorization_id"
    assert upstream["authorization_issuance_id_assumed"] is upstream["matching_projection_is_authenticity"] is False
    assert upstream["runtime_state_from_initial_state_or_json"] is False
    assert "pinned_synthetic_runtime_execution_lease_state" in upstream["runtime_state_api"]
    assert {"field_copy", "JSON_reconstruction", "wrapper", "subclass", "schema_alias", "ID_substitution",
        "fingerprint_substitution", "old_auth_synthesis", "old_runtime_synthesis"} == set(upstream["forbidden_bridges"])
    assert "authorization_id" in _class_fields(PINNED_AUTH, "PinnedSyntheticRuntimeAuthorization")
    assert "issuance_id" not in _class_fields(PINNED_AUTH, "PinnedSyntheticRuntimeAuthorization")
    auth = ast.unparse(_function(PINNED_AUTH, "validate_pinned_synthetic_runtime_authorization"))
    assert "type(authorization) is not PinnedSyntheticRuntimeAuthorization" in auth
    assert "record['object'] is not authorization" in auth
    lease = ast.unparse(_function(PINNED_RUNTIME, "_authenticated_record_locked"))
    assert "type(lease) is not PinnedSyntheticRuntimeExecutionLease" in lease
    assert "record.lease_ref() is not lease" in lease
    assert "authorization is not record.authorization" in lease
    assert "_authenticate_authorization" in _calls(_function(PINNED_RUNTIME, "_authenticated_record_locked"))
    assert "authorization_owner.validate_pinned_synthetic_runtime_authorization" in _calls(
        _function(PINNED_RUNTIME, "_authenticate_authorization"))


def test_provider_is_inherited_through_existing_original_graph_without_independent_input():
    provenance = CONTRACT["provider_provenance"]
    assert provenance["decision"] == "INHERIT_TRANSITIVELY"
    assert provenance["path"] == ["exact original pinned runtime lease", "exact original pinned authorization",
        "retained authenticated PINNED provider graph"]
    assert provenance["graph_reauthenticated_by_unchanged_pinned_public_validators"] is True
    for name in ("caller_provider_input_accepted", "direct_provider_projection_required",
            "independent_reflection_provider_requirement_found", "provider_proof_is_reflection_permission",
            "provider_issuance_allowed"):
        assert provenance[name] is False
    assert "_authenticate_provider" in _calls(_function(PINNED_AUTH, "validate_pinned_synthetic_runtime_authorization"))
    assert "provider_owner.validate_pinned_java_exact_provider" in _calls(_function(PINNED_AUTH, "_authenticate_provider"))


def test_admission_signed_identity_covers_original_auth_runtime_request_and_fixed_effect_scope():
    identity = CONTRACT["admission_identity"]
    assert set(identity["minimum_signed_bindings"]) == {
        "admission_owner_phase_schema", "issuing_pid", "admission_id", "semantic_role_and_exact_request_role",
        "authorization_owner_phase_schema_PID_and_authorization_id", "authorization_fingerprint",
        "authorization_proof_context_id", "runtime_owner_phase_schema_PID_and_lease_id",
        "stable_authenticated_runtime_fingerprint", "authenticated_runtime_state_at_issuance",
        "scenario_phase_and_id", "source_kind_sha256_size_and_definition_sha256", "exact_public_invocation",
        "field_owner_name_type_and_read_operation", "original_request_issuance_id_PID_and_authenticated_fingerprint",
        "renderer_identity_and_fingerprint", "admission_evidence_digest_and_stable_fingerprint"}
    assert identity["authenticated_runtime_state_at_issuance"] == "ISSUED"
    assert identity["exact_original_bindings_retained_outside_scalar_payload"] is True
    assert identity["admission_has_no_consumption_state_machine"] is True
    assert identity["admission_issuance_is_behavior"] is identity["fixed_admission_fingerprint_mutates_with_runtime_state"] is False


def test_role_admission_and_lease_tombstones_never_reopen_on_collection_or_new_request():
    admission = CONTRACT["admission_one_shot"]
    machine = CONTRACT["state_machine"]
    assert admission["maximum_admissions_per_runtime_role"] == 1
    assert admission["maximum_roles_per_runtime"] == 2
    assert admission["key_fields"] == ["admission_owner_phase_schema_PID",
        "authorization_owner_phase_schema_PID_authorization_id", "runtime_owner_phase_schema_PID_lease_id",
        "semantic_role", "exact_scenario_source_definition_field_read_scope"]
    assert {"request_issuance_id", "request_fingerprint", "renderer_fingerprint", "authorization_fingerprint",
        "authorization_proof_context_id", "runtime_fingerprint"} == set(admission["excluded_key_fields"])
    assert admission["key_derived_only_after_original_public_authentication"] is True
    assert admission["request_identity_signed_and_retained_separately"] is True
    assert admission["fresh_same_role_request_reopens_issuance"] is False
    assert machine["maximum_leases_per_admission"] == machine["maximum_terminal_commits_per_lease"] == 1
    assert machine["roles_independent"] is machine["separate_admission_and_lease_for_each_role"] is True
    assert machine["one_shot_lease_key"] == ["admission_owner_phase_schema_PID", "original_admission_id"]
    for group, tombstone in ((admission, "permanent_tombstones"), (machine, "permanent_admission_and_lease_tombstones")):
        assert group[tombstone] is True
        assert group["tombstone_lifetime"] == "issuing owner process lifetime"
        for name in ("refund_allowed", "reissue_allowed", "collection_reopens_issuance"):
            assert group[name] is False


@pytest.mark.parametrize("source,target", tuple(itertools.product(STATES, repeat=2)))
def test_only_issued_to_terminal_transitions_exist(source, target):
    machine = CONTRACT["state_machine"]
    assert machine["states"] == list(STATES) and machine["initial_state"] == "ISSUED"
    assert machine["terminal_states"] == ["CONSUMED", "INVALIDATED"]
    assert machine["new_semantic_state"] is None
    transitions = {tuple(pair) for pair in machine["transitions"]}
    assert ((source, target) in transitions) == (source == "ISSUED" and target in ("CONSUMED", "INVALIDATED"))
    assert machine["stable_lease_fingerprint_includes_mutable_current_state"] is False
    assert machine["current_state_authenticated_in_separate_signed_record"] is True
    assert machine["terminal_evidence_valid_if_all_original_upstreams_authenticate"] is True
    assert machine["terminal_validation_grants_readiness"] is False


@pytest.mark.parametrize("operation,role,runtime", tuple(itertools.product(
    ("admission_issuance", "lease_issuance"), ROLES, STATES)))
def test_both_role_permissions_are_prepared_only_while_runtime_is_issued(operation, role, runtime):
    rule = CONTRACT["runtime_state_rules"][operation]
    assert rule["roles"] == list(ROLES)
    assert rule["reflection_state"] is None
    assert rule["runtime_authentication_required"] is True
    allowed = role in rule["roles"] and runtime == rule["runtime_state"]
    assert allowed == (runtime == "ISSUED")


@pytest.mark.parametrize("operation,role,reflection,runtime", tuple(itertools.product(
    ("pre_execution_readiness", "active_readiness", "consumption", "invalidation", "terminal_validation"),
    ROLES, STATES, STATES)))
def test_authenticated_runtime_and_reflection_state_matrix_is_frozen(operation, role, reflection, runtime):
    rule = CONTRACT["runtime_state_rules"][operation]
    assert rule["roles"] == list(ROLES) and rule["runtime_authentication_required"] is True
    allowed = role in rule["roles"]
    allowed &= reflection == rule["reflection_state"] if rule["reflection_state"] is not None else True
    allowed &= runtime == rule["runtime_state"] if rule["runtime_state"] is not None else True
    allowed &= reflection in rule.get("reflection_states", STATES)
    allowed &= runtime in rule.get("runtime_states", STATES)
    expected = {
        "pre_execution_readiness": reflection == "ISSUED" and runtime == "ISSUED",
        "active_readiness": reflection == "ISSUED" and runtime == "CONSUMED",
        "consumption": reflection == "ISSUED" and runtime == "CONSUMED",
        "invalidation": reflection == "ISSUED",
        "terminal_validation": reflection in ("CONSUMED", "INVALIDATED"),
    }[operation]
    assert allowed == expected
    if operation == "terminal_validation":
        assert rule["grants_readiness"] is False


def test_state_requirements_match_frozen_old_reflection_source_without_importing_it():
    issue = ast.unparse(_function(OLD_REFLECTION, "issue_synthetic_reflection_execution_lease"))
    assert "_runtime_state(runtime, authorization, ISSUED)" in issue
    pre = _function(OLD_REFLECTION, "synthetic_reflection_execution_lease_satisfies_executor")
    active = _function(OLD_REFLECTION, "consumable_during_active_execution")
    for node, state in ((pre, "ISSUED"), (active, "CONSUMED")):
        call = next(node for node in ast.walk(node) if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "_compatible")
        assert ast.unparse(call.args[-1]) == state
    transition = ast.unparse(_function(OLD_REFLECTION, "_transition"))
    assert "record.lifecycle_state != ISSUED" in transition
    branch = next(node for node in ast.walk(_function(OLD_REFLECTION, "_transition"))
        if isinstance(node, ast.If) and ast.unparse(node.test) == "target == CONSUMED")
    assert "_runtime_state(runtime, authorization, CONSUMED)" in ast.unparse(branch)
    assert not branch.orelse
    assert "runtime_owner.synthetic_runtime_execution_lease_state" in _calls(_function(OLD_REFLECTION, "_runtime_state"))


def test_eight_step_order_places_runtime_commit_before_permission_commit_before_first_read():
    order = CONTRACT["ordering"]
    assert order == ["authenticate all capability gates", "source/harness ready", "consume pinned runtime lease",
        "consume BEFORE reflection lease", "perform BEFORE read", "invoke public decrement(3)",
        "consume AFTER reflection lease", "perform AFTER read"]
    frozen = _constant(OLD_REFLECTION, "EXECUTOR_SEQUENCE")
    assert frozen == ("all capability/authentication gates", "source/harness ready", "consume scenario runtime lease",
        "consume BEFORE reflection lease", "perform BEFORE exact reflection read", "invoke exact public decrement(3)",
        "consume AFTER reflection lease", "perform AFTER exact reflection read")
    boundary = CONTRACT["first_behavior_boundary"]
    assert boundary["first_behavioral_effect"] == "BEFORE exact read"
    for name in ("before_reflection_consumption_is_permission_state_mutation",
            "runtime_consumption_precedes_before_permission_and_read", "executor_responsible_for_order_and_effect_evidence"):
        assert boundary[name] is True
    for name in ("before_reflection_consumption_is_behavioral_read", "runtime_consumption_after_before_read_allowed",
            "reflection_owner_performs_reads", "reflection_owner_invokes_method", "failure_after_commit_refunds",
            "already_consumed_runtime_reachable_by_this_contract"):
        assert boundary[name] is False
    assert "does not prove a field read" in boundary["consumed_reflection_means"]
    assert "does not prove BEFORE read, invocation or AFTER read" in boundary["consumed_runtime_means"]


def test_distinct_authentication_domains_reject_reconstructions_and_export_no_capabilities():
    domains = CONTRACT["authentication_domains"]
    upstream_domains = {_constant(PINNED_AUTH, "_DOMAIN").rstrip(b"\x00"), _constant(PINNED_RUNTIME, "_DOMAIN")}
    new_domains = {domains[group]["domain"].encode() for group in ("admission", "lifecycle")}
    assert len(new_domains) == 2 and not new_domains & upstream_domains
    for group, owner_key in (("admission", "admission_owner"), ("lifecycle", "lifecycle_owner")):
        domain = domains[group]
        assert CONTRACT[owner_key]["phase_id"] in domain["domain"]
        assert domain["algorithm"] == "HMAC-SHA256"
        assert domain["independent_private_secret_required"] is True
        assert domain["secret_created_in_this_phase"] is False
        assert len(set(domain["roles"])) == len(domain["roles"])
    assert set(domains["independent_of"]) == {"old_reflection_admission_secret_domain",
        "old_reflection_lifecycle_secret_domain", "pinned_authorization_secret_domain", "pinned_runtime_lifecycle_secret_domain"}
    for name in ("separate_locks_registries_records_and_secrets", "exact_class_required",
            "live_original_registry_identity_required", "issuing_PID_required", "wrong_PID_rejected_before_lock"):
        assert domains[name] is True
    assert {"copy", "deepcopy", "dataclasses.replace", "manual_reconstruction", "JSON", "report",
        "ID_string", "fingerprint_string", "wrapper", "subclass", "old_type", "schema_relabel"} <= set(domains["rejected_inputs"])
    assert domains["secrets_signatures_registries_exported"] is domains["reports_restore_capabilities"] is False
    assert all(token in domains["canonical_payload"] for token in ("sorted keys", "compact separators", "allow_nan=false", "UTF-8", "domain + NUL + role"))


def test_atomic_owner_publication_and_terminal_checks_use_public_upstream_snapshots():
    atomicity = CONTRACT["atomicity"]
    for kind in ("admission", "lease"):
        sequence = atomicity[kind + "_locked_sequence"]
        duplicate = next(index for index, item in enumerate(sequence) if item.startswith("duplicate check"))
        construction = next(index for index, item in enumerate(sequence) if item.startswith("construct and sign"))
        gate = sequence.index("final authenticated public runtime ISSUED eligibility check")
        assert sequence[0].startswith("authenticate exact original")
        assert duplicate < construction < gate < len(sequence) - 1
        assert sequence[-1] == "single owner-store replacement publishes atomically"
    terminal = atomicity["terminal_locked_sequence"]
    assert terminal[0].startswith("authenticate exact original")
    assert terminal.index("require reflection ISSUED") < terminal.index("sign terminal record")
    assert terminal.index("for consumption only authenticate runtime CONSUMED; invalidation imposes no runtime state") < terminal.index("sign terminal record")
    assert terminal[-1] == "replace complete owner store at exactly one linearization point"
    for name in ("read_validation_state_and_readiness_under_owner_lock", "no_partial_publication",
            "failed_operation_preserves_store", "concurrent_terminal_commits_at_most_one",
            "upstream_public_validators_use_independent_locks", "runtime_ISSUED_check_is_issuance_eligibility_point",
            "runtime_state_can_change_after_eligibility_check", "runtime_CONSUMED_terminal_once_authenticated",
            "admission_lease_issuance_never_consumes_upstreams",
            "owner_store_records_retain_upstreams_strongly_and_capability_identity_weakly",
            "collected_capability_identity_cannot_be_reconstructed_from_tombstone"):
        assert atomicity[name] is True
    for name in ("cross_owner_atomic_transaction_claimed", "stale_precheck_is_reservation", "upstream_private_lock_access_allowed"):
        assert atomicity[name] is False
    assert CONTRACT["authentication_domains"]["wrong_PID_rejected_before_lock"] is True


def test_local_active_and_behavioral_readiness_remain_distinct_and_fail_closed():
    readiness = CONTRACT["readiness"]
    assert "reflection lease ISSUED AND runtime lease ISSUED" in readiness["reflection_local_ready"]
    assert "reflection lease ISSUED AND runtime lease CONSUMED" in readiness["reflection_active_ready"]
    assert readiness["behavioral_activation_ready"] is False and readiness["reason"] == "PROOF_UNRESOLVED"
    for name in ("local_implies_active", "local_or_active_implies_behavioral", "terminal_reflection_readiness",
            "caller_boolean_or_JSON_readiness_accepted", "active_state_table_is_reachability_proof"):
        assert readiness[name] is False
    assert readiness["pinned_runtime_current_readiness_unchanged"] is True
    assert readiness["overall_behavior_blocked_until_separate_source_compile_consumer_contract"] is True
    source = ast.unparse(_function(PINNED_RUNTIME, "check_pinned_synthetic_runtime_execution_lease_preconditions"))
    assert "record.lifecycle_state == ISSUED, False" in source
    consumer = _function(PINNED_RUNTIME, "_consumer_readiness")
    assert "_fail('PROOF_UNRESOLVED'" in ast.unparse(consumer)
    assert "_consumer_readiness" in _calls(_function(PINNED_RUNTIME, "_transition"))
    assert "_STORE = updated" in ast.unparse(_function(PINNED_RUNTIME, "_transition"))
    assert ast.unparse(_function(PINNED_RUNTIME, "_transition")).index("_consumer_readiness()") < ast.unparse(
        _function(PINNED_RUNTIME, "_transition")).index("_STORE = updated")


def test_source_and_compilation_dependencies_still_block_runtime_consumption():
    dependencies = CONTRACT["downstream_dependencies"]
    for name in ("source_materialization_position", "scenario_compilation_timing_authority", "pinned_consumer_executor_contract"):
        assert dependencies[name] == "UNRESOLVED_DOWNSTREAM_DEPENDENCY"
    assert dependencies["blocks_behavioral_activation_ready"] is dependencies["blocks_pinned_runtime_consumption"] is True
    for name in ("compilation_authority", "source_compile_resolution_in_this_phase",
            "provider_infrastructure_compile_is_scenario_compile", "caller_readiness_flag_can_resolve"):
        assert dependencies[name] is False


@pytest.mark.parametrize("operation", [CONTRACT["conceptual_public_api"]["compatibility_predicate"]]
    + CONTRACT["conceptual_public_api"]["admission_operations"]
    + CONTRACT["conceptual_public_api"]["lifecycle_operations"], ids=lambda item: item["name"])
def test_every_future_public_operation_requires_both_original_pinned_validators(operation):
    assert operation["mandatory_upstream_validators"] == PUBLIC_VALIDATORS
    assert operation["all_originals_reauthenticated"] is operation["supplied_originals_checked_by_identity"] is True
    assert operation["conceptual_only"] is True
    inputs = operation.get("inputs", operation.get("required_inputs", [])) + operation.get("optional_inputs", [])
    assert not any("provider" in item or "readiness" in item or "JSON" in item for item in inputs)


def test_public_operations_follow_state_rules_and_do_not_hide_terminal_readiness():
    api = CONTRACT["conceptual_public_api"]
    assert api["implemented"] is False
    pairs = {
        "issue_pinned_synthetic_reflection_execution_lease": "lease_issuance",
        "check_pinned_synthetic_reflection_execution_lease_preconditions": "pre_execution_readiness",
        "check_pinned_synthetic_reflection_active_readiness": "active_readiness",
        "consume_pinned_synthetic_reflection_execution_lease": "consumption",
        "invalidate_pinned_synthetic_reflection_execution_lease": "invalidation",
    }
    for operation_name, rule_name in pairs.items():
        operation = _operation("lifecycle_operations", operation_name)
        rule = CONTRACT["runtime_state_rules"][rule_name]
        assert operation["runtime_state_required"] == rule["runtime_state"]
        assert operation["reflection_state_required"] == rule["reflection_state"]
    admission = _operation("admission_operations", "issue_pinned_synthetic_reflection_execution_admission")
    assert admission["runtime_state_required"] == "ISSUED"
    assert _operation("lifecycle_operations", "validate_pinned_synthetic_reflection_execution_lease")["reflection_state_required"] is None
    assert "same original lease in any authenticated state" == _operation(
        "lifecycle_operations", "validate_pinned_synthetic_reflection_execution_lease")["output"]
    delivery = api["readiness_error_delivery"]
    assert "both reflection readiness flags false" in delivery
    assert "behavioral_activation_ready=false and PROOF_UNRESOLVED" in delivery


def test_failure_categories_preserve_authentication_scope_state_role_and_unknown_proof_distinctions():
    taxonomy = CONTRACT["error_taxonomy"]
    assert {"PINNED_AUTH_UNAUTHENTICATED", "PINNED_RUNTIME_LEASE_UNAUTHENTICATED", "PINNED_RUNTIME_STATE_MISMATCH",
        "REFLECTION_REQUEST_UNAUTHENTICATED", "REFLECTION_SCOPE_MISMATCH", "REFLECTION_ADMISSION_UNAUTHENTICATED",
        "DUPLICATE_REFLECTION_ADMISSION", "REFLECTION_LEASE_UNAUTHENTICATED", "DUPLICATE_REFLECTION_LEASE",
        "REFLECTION_LEASE_ALREADY_CONSUMED", "REFLECTION_LEASE_INVALIDATED", "REFLECTION_ROLE_MISMATCH",
        "PROOF_UNRESOLVED"} <= set(taxonomy)
    assert "not an authentication failure" in taxonomy["PINNED_RUNTIME_STATE_MISMATCH"]
    assert "never relabeled authentication failure" in taxonomy["REFLECTION_SCOPE_MISMATCH"]
    mapping = CONTRACT["error_mapping"]
    assert mapping["known_state_or_scope_mismatch_relabelled_authentication"] is False
    assert mapping["unknown_upstream_validator_failure"] == "PROOF_UNRESOLVED"
    assert mapping["upstream_code_and_reason_preserved"] is True
    assert mapping["request_synthetic_reflection_scope_mismatch"] == "REFLECTION_SCOPE_MISMATCH"
    assert mapping["runtime_LEASE_ALREADY_CONSUMED_or_LEASE_INVALIDATED_when_runtime_ISSUED_required"] == "PINNED_RUNTIME_STATE_MISMATCH"


def test_exact_read_authority_request_renderer_and_observation_data_are_not_effect_evidence():
    authority = CONTRACT["authority"]
    assert authority["exact_role_read_only_permission"] is authority["admission_can_prepare_lease_only"] is True
    assert authority["field"] == "SyntheticStateBox.value:int" and authority["operation"] == "read_exact_bound_field"
    assert {"runtime_authority", "repository_write_authority", "apply_authority", "network_authority",
        "host_mount_authority", "shell_authority", "arbitrary_java_authority", "arbitrary_reflection_authority",
        "private_method_authority", "field_write_authority", "enumeration_authority", "executor_authority",
        "BANK_authority", "compilation_authority"} <= set(authority["false_in_all_states"])
    assert authority["compilation_authority"] is authority["consumption_widens_scope"] is False
    assert authority["lease_consumption_performs_read"] is authority["provider_proof_is_permission"] is False
    distinction = CONTRACT["request_renderer_evidence"]
    assert distinction["actual_read_evidence_owner"] == "downstream executor"
    assert all(value is False for name, value in distinction.items() if name != "actual_read_evidence_owner")
    assert not _calls(_function(PRIMITIVE, "validate_synthetic_private_field_observation")) & {
        "authorization_owner.validate_synthetic_runtime_authorization", "runtime_owner.validate_synthetic_runtime_execution_lease"}


def test_future_executor_projection_is_complete_but_never_reconstructs_authority():
    projection = CONTRACT["executor_projection"]
    assert {"semantic_role", "exact_request_observation_role", "lease_id", "stable_authenticated_fingerprint",
        "authenticated_state_API", "scenario_phase_and_id", "source_kind_sha256_size_definition_sha256",
        "exact_public_invocation", "field_owner_name_type_read_operation",
        "runtime_owner_phase_schema_PID_lease_id_fingerprint",
        "authorization_owner_phase_schema_PID_authorization_id_fingerprint_proof_context_id",
        "original_admission_id_fingerprint_binding", "original_request_issuance_id_PID_fingerprint_binding"} == set(projection["minimum_fields"])
    assert projection["original_objects_required_alongside_projection"] is projection["original_bindings_authenticated_via_public_apis"] is True
    for name in ("scalar_projection_substitutes_for_originals", "secrets_or_private_signatures_included", "terminal_projection_is_readiness"):
        assert projection[name] is False


def test_signed_lease_issuance_projection_retains_exact_originals_and_separate_current_state():
    identity = CONTRACT["lease_identity"]
    assert set(identity["minimum_signed_bindings"]) == {
        "lifecycle_owner_phase_schema", "issuing_pid", "lease_id", "initial_reflection_state_ISSUED",
        "semantic_role_and_exact_request_role",
        "original_admission_owner_phase_schema_PID_id_and_authenticated_fingerprint",
        "original_request_issuance_id_PID_and_authenticated_fingerprint", "renderer_identity_and_fingerprint",
        "authorization_owner_phase_schema_PID_authorization_id", "authorization_fingerprint",
        "authorization_proof_context_id", "runtime_owner_phase_schema_PID_lease_id",
        "stable_authenticated_runtime_fingerprint", "authenticated_runtime_state_at_issuance_ISSUED",
        "scenario_phase_and_id", "source_kind_sha256_size_and_definition_sha256", "exact_public_invocation",
        "field_owner_name_type_and_read_operation", "authority_matrix", "lease_evidence_digest",
        "stable_authenticated_lease_fingerprint"}
    assert identity["exact_original_bindings_retained_outside_scalar_payload"] is True
    assert identity["current_state_signed_separately_with_immutable_projection"] is True
    for name in ("stable_fingerprint_includes_mutable_current_state",
            "runtime_state_at_issuance_is_current_state_substitute", "secret_or_private_record_signature_in_public_payload"):
        assert identity[name] is False


def test_old_exact_type_gates_registries_and_acceptance_remain_isolated():
    isolation = CONTRACT["old_owner_isolation"]
    for name in ("old_primitive_request_admission_lifecycle_unchanged", "pinned_authorization_runtime_unchanged",
            "historical_receipts_registry_reversal_executor_runtime_provider_bytes_unchanged"):
        assert isolation[name] is True
    for name in ("new_types_subclass_or_alias_old", "old_registries_used", "old_validators_modified", "old_private_signing_helpers_used"):
        assert isolation[name] is False
    assert {"insert_pinned_into_old_registries", "fabricate_old_admission", "fabricate_old_reflection_lease",
        "reuse_old_private_signing_helpers", "modify_old_public_validators", "change_old_auth_runtime_acceptance",
        "change_old_request_bytes", "rewrite_receipt_history", "schema_alias", "subclass_bridge", "repin", "stash", "reset", "clean"} <= set(isolation["prohibited"])
    for path in (PRIMITIVE, OLD_ADMISSION, OLD_REFLECTION):
        assert "synthetic_runtime_authorization_pinned" not in (ROOT / path).read_text(encoding="utf-8")
    old = ast.unparse(_function(OLD_RUNTIME, "_authenticated_record_locked"))
    assert old.index("type(lease) is not SyntheticRuntimeExecutionLease") < old.index("_LEASES.get")
    assert "record.lease_ref() is not lease" in old
    old_auth = ast.unparse(_function(OLD_AUTH, "validate_synthetic_runtime_authorization"))
    assert "type(authorization) is not SyntheticRuntimeAuthorization" in old_auth
    assert "_ISSUED_HANDLES.get(authorization.issuance_id) is not authorization" in old_auth
    assert {"authorization_owner.validate_synthetic_runtime_authorization",
        "runtime_owner.validate_synthetic_runtime_execution_lease"} <= _calls(_function(OLD_REFLECTION, "_authenticate_inputs"))


@pytest.mark.parametrize("module_name,reason", (
    ("behavioral_diagnostic_executor_refresh", "existing_synthetic_issuer_cannot_reconstruct_independent_scenario"),
    ("behavioral_diagnostic_executor_retry", "frozen_synth_auth_1_has_no_public_consumption_contract"),
    ("behavioral_diagnostic_executor_lifecycle_retry", "java_profile_contract_mismatch")))
def test_historical_executor_stops_are_preserved_without_running_verifiers(module_name, reason):
    path = "core/" + module_name + ".py"
    verify = _function(path, "verify")
    constants = {node.value for node in ast.walk(verify) if isinstance(node, ast.Constant) and type(node.value) is str}
    assert reason in constants
    calls = _calls(verify)
    assert not any("consume_" in name or "invalidate_" in name or "subprocess" in name
        or name.startswith(("execute_", "run_")) for name in calls)
    if module_name == "behavioral_diagnostic_executor_refresh":
        assert "'source_projected': False" in ast.unparse(verify)
        assert "'measured_observations': None" in ast.unparse(verify)
    else:
        assert "authorization.issue_synthetic_runtime_authorization" in calls
        assert "'source_projected': False" in ast.unparse(_function(path, "_empty_report"))
        if module_name == "behavioral_diagnostic_executor_lifecycle_retry":
            assert "infrastructure_contract_changed_requires_review" in constants


def test_all_frozen_capability_and_registry_bytes_match_precontract_preservation_snapshot():
    baseline = json.loads((HERE / "preservation_baseline.json").read_text(encoding="utf-8"))["files"]
    paths = (PRIMITIVE, OLD_AUTH, OLD_RUNTIME, PINNED_AUTH, PINNED_RUNTIME, OLD_ADMISSION, OLD_REFLECTION,
        "core/phase_registry.py", "docs/roadmap/phase_registry.json",
        "core/behavioral_diagnostic_executor_refresh.py", "core/behavioral_diagnostic_executor_retry.py",
        "core/behavioral_diagnostic_executor_lifecycle_retry.py",
        "tests/runtime/synthetic/test_synthetic_reflection_lifecycle_pinned_compat.py")
    for path in paths:
        content = read_preorganization_source(path)
        path = previous_path(path)
        assert sha256(content).hexdigest() == baseline[path]["sha256"], path
        assert len(content) == baseline[path]["bytes"], path


def test_all_operational_effects_are_exact_integer_zero_and_phase_stops_at_freeze():
    effects = CONTRACT["operational_effects"]
    assert set(effects) == {"Docker", "SANDBOX2", "JAVA1C", "provider_issuance", "pinned_authorization_issuance",
        "pinned_runtime_lease_issuance", "runtime_lease_consumption", "runtime_lease_invalidation",
        "reflection_request_operational_issuance", "reflection_admission_issuance", "reflection_lease_issuance",
        "reflection_lease_consumption", "reflection_lease_invalidation", "reflection_read", "SyntheticStateBox",
        "BANK", "EXECUTOR.1R", "Apply", "repository_runtime_writes"}
    assert all(type(value) is int and value == 0 for value in effects.values())
    assert "Stop after freeze" in CONTRACT["completion_rule"]
    document = (HERE / "SYNTH_REFLECT_PINNED_CONTRACT_1.md").read_text(encoding="utf-8")
    assert "No adapter, reflection capability or" in document
    assert "behavioral effect exists" in document
