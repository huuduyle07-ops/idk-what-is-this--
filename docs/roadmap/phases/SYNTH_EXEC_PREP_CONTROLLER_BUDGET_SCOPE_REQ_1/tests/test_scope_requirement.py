"""Read-only tests of the additive scope artifact and its frozen source evidence.

No owner or proof module is imported. Historical inputs are parsed as data only;
these checks neither calculate a new proof nor exercise a controller operation.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
PREFIX = "docs/roadmap/phases/"
CONTROLLER = PREFIX + "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/contract.json"
SCHEMA = PREFIX + "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json"
PREP = PREFIX + "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1/contract.json"
WORKSPACE = PREFIX + "SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/contract.json"
TRANSPORT = PREFIX + "SYNTH_EXEC_PREP_CONTROLLER_TRANSPORT_1/selection.json"
PROOF = PREFIX + "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1_REPORT.json"


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=unique_object, parse_constant=reject_constant)


def resolve_pointer(value, pointer):
    assert pointer.startswith("/")
    for component in pointer[1:].split("/"):
        component = component.replace("~1", "/").replace("~0", "~")
        value = value[int(component)] if type(value) is list else value[component]
    return value


@pytest.fixture(scope="module")
def requirement():
    return load_json(HERE / "requirement.json")


@pytest.fixture(scope="module")
def baseline():
    return load_json(HERE / "preservation_baseline.json")["files"]


def table_row(requirement, label):
    matches = [row for row in requirement["normative_table"]
               if row["event_message"] == label]
    assert len(matches) == 1, label
    return matches[0]


def test_requirement_is_additive_and_does_not_rewrite_prior_entailment(requirement):
    assert requirement["phase_id"] == "SYNTH.EXEC.PREP.CONTROLLER.BUDGET.SCOPE.REQ.1"
    assert requirement["new_requirement_id"] == requirement["phase_id"]
    assert requirement["typed_result"] == "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_COMPLETE"
    assert requirement["completion_marker"] == requirement["typed_result"]
    assert requirement["artifact_kind"] == "PURE_ADDITIVE_REQUIREMENT_CLARIFICATION"
    assert requirement["requirement_frozen"] is True
    assert requirement["historical_bytes_preserved"] is True
    assert requirement["historical_contract_globally_wrong"] is False
    assert requirement["prior_text_uniquely_defined_endpoint"] is False
    assert requirement["stop"] is True


@pytest.mark.parametrize("relative", [CONTROLLER, SCHEMA, PREP, WORKSPACE, TRANSPORT, PROOF])
def test_frozen_sources_match_prechange_external_baseline(relative, baseline):
    expected = baseline[relative]
    raw = (ROOT / relative).read_bytes()
    assert expected["kind"] == "file"
    assert expected["bytes"] == len(raw)
    assert expected["sha256"] == sha256(raw).hexdigest()


def test_every_cited_pointer_is_exact_unchanged_source_data(requirement, baseline):
    assert len(requirement["evidence"]) >= 15
    for name, evidence in requirement["evidence"].items():
        path = ROOT / evidence["path"]
        assert path.resolve().is_relative_to(ROOT)
        assert evidence["path"] in {CONTROLLER, SCHEMA, PREP, WORKSPACE, TRANSPORT, PROOF}
        raw = path.read_bytes()
        assert evidence["sha256"] == sha256(raw).hexdigest(), name
        assert evidence["sha256"] == baseline[evidence["path"]]["sha256"], name
        assert evidence["size_bytes"] == len(raw), name
        assert evidence["value"] == resolve_pointer(load_json(path), evidence["pointer"]), name
        assert evidence["reason"].strip(), name


def test_clarifications_preserve_actual_ambiguous_wording_and_identify_scope(requirement):
    expected = {(CONTROLLER, "/bounds/attempt_budget_scope"),
                (SCHEMA, "/cross_field_rules/10"),
                (TRANSPORT, "/wire/stream_budgets"), (PREP, "/compiler")}
    records = requirement["clarifications"]
    assert {(record["historical_artifact"], record["historical_key"])
            for record in records} == expected
    for record in records:
        original = load_json(ROOT / record["historical_artifact"])
        assert record["old_ambiguous_wording"] == resolve_pointer(original, record["historical_key"])
        assert record["new_requirement_id"] == requirement["phase_id"]
        assert record["historical_bytes_preserved"] is True
        assert all(record[key].strip() for key in ("new_exact_interpretation", "scope", "reason"))
        assert "underspecified" in record["reason"]


def test_semantic_selection_uses_effect_facets_and_separate_cleanup(requirement):
    selection = requirement["semantic_selection"]
    assert selection["choice"] == "A"
    assert selection["effect_attempt_semantics"] is True
    assert selection["wider_readiness_lifecycle_semantics"] is False
    assert selection["selection_based_on_budget_fit"] is False
    assert "two non-interchangeable" in selection["reason"]
    assert "cleanup" in selection["reason"]
    evidence = requirement["evidence"]
    assert "materialize-then-compile" in evidence["fixed_attempt"]["value"]
    assert evidence["facets"]["value"] == ["exact_sandbox_materialization_authority",
                                           "exact_scenario_compilation_authority"]
    assert evidence["cleanup_not_preparation"]["value"] is False


def test_caps_match_frozen_controller_without_stdin_or_transport_widening(requirement):
    historical = load_json(ROOT / CONTROLLER)["bounds"]["preparation_attempt"]
    caps = requirement["caps"]
    for key in ("outer_stdout_max_bytes", "outer_stderr_max_bytes"):
        assert caps[key] == historical[key] == 8192
    assert caps["individual_frame_max_bytes"] == 8192
    assert caps["shared_attempt_deadline_ms"] == historical["shared_controller_deadline_ms"] == 5000
    assert caps["hard_preparation_bound_ms"] == historical["outer_timeout_ms"] == 10000
    assert caps["compiler_child_stdout_max_bytes"] == historical["compiler_stdout_max_bytes"] == 2048
    assert caps["compiler_child_stderr_max_bytes"] == historical["compiler_stderr_max_bytes"] == 2048
    assert caps["controller_stdin_cumulative_8192_cap_frozen"] is False
    assert all(value is False for value in requirement["non_changes"].values())


def test_origin_is_owner_facet_admission_before_dispatch_not_time_inference(requirement):
    interval = requirement["counter_interval"]
    assert interval["start_event_id"] == "OWNER_MATERIALIZATION_ADMISSION_BEFORE_DISPATCH"
    assert "before dispatching" in interval["start"]
    assert "both counters at zero" in interval["start"]
    assert interval["origin_derived_from_deadline_alone"] is False
    assert "materialization facet admission" in interval["origin_basis"]
    assert interval["earlier_events_outside"] == ["before empty observation",
        "OBSERVE_EMPTY_WORKSPACE request", "OBSERVE_EMPTY_WORKSPACE response"]


def test_success_endpoint_includes_complete_compile_evidence_and_final_byte(requirement):
    interval = requirement["counter_interval"]
    assert interval["successful_end_event_id"] == "COMPLETE_COMPILE_RESPONSE_FINAL_BYTE"
    endpoint = interval["successful_end"]
    assert "final physical byte" in endpoint
    assert "including all actual framing" in endpoint
    for component in ("workspace_state", "compiler_identity", "capture_and_reap", "class_metadata"):
        assert component in endpoint
    assert "receipt authentication" in endpoint
    assert "cleanup completion" in endpoint
    assert "not this endpoint" in endpoint
    assert "actual framing" in interval["membership_rule"]
    assert "No chunking, delayed suffix" in interval["no_evidence_deferral"]
    assert "deferred effect response evidence" in interval["no_evidence_deferral"]


def test_failure_cases_close_without_receipt_or_counter_reset(requirement):
    interval = requirement["counter_interval"]
    assert interval["failure_end_event_id"] == "ORDINARY_RESPONSE_DRAIN_TERMINATION"
    cases = interval["failure_end_cases"]
    assert set(cases) == {"no_response_pending", "response_pending", "early_failure",
                          "cleanup_preemption", "overflow", "loss_or_deadline"}
    assert "irrevocable terminal attempt-abort" in cases["no_response_pending"]
    for terminal in ("final byte", "channel closure/loss", "10000ms hard preparation deadline"):
        assert terminal in cases["response_pending"]
    assert "partial/invalid ordinary byte" in cases["response_pending"]
    assert "materialization failure/rejection" in cases["early_failure"]
    assert "nonexistent successful compile response" in cases["early_failure"]
    assert "does not close a pending ordinary response ledger" in cases["cleanup_preemption"]
    assert "failed effect attempt" in cases["cleanup_preemption"]
    assert "never resets" in cases["overflow"]
    assert "unbounded buffering" in cases["overflow"]
    assert "No terminal response is fabricated" in cases["loss_or_deadline"]
    assert "cannot reopen or publish success" in cases["loss_or_deadline"]
    assert set(interval["no_resets"]) >= {"compile admission", "observation",
        "receipt authentication", "cleanup barrier", "lost response"}
    assert "clamped to original 10000ms hard bound" in interval["no_deadline_extension"]


def test_observations_are_classified_by_lifecycle_and_never_cached_poststate(requirement):
    fresh = requirement["fresh_readiness_observation"]
    empty = requirement["initial_empty_observation"]
    for observation in (fresh, empty):
        assert observation["classification"] == "OUTSIDE_PREPARATION_CAPTURE_WITH_SEPARATE_BOUND"
        assert observation["bounds_ref"] == "independent_bounds.observation"
    assert empty["mandatory"] is True
    assert empty["request_and_response_both_classified"] is True
    assert fresh["mandatory_before_readiness_or_handoff"] is True
    assert fresh["mutation_poststate_substitutes"] is False
    assert fresh["lifecycle_class"] == "workspace current-liveness/readiness evidence"
    assert fresh["required_tag"] == "new complete challenged OBSERVE_* of prepared current state"
    assert fresh["CURRENT_before_initial_receipt_allowed"] is True
    assert fresh["PREPARED_before_original_receipt_allowed"] is False
    assert fresh["PREPARED_with_original_receipt_allowed"] is True
    row = table_row(requirement, "OBSERVE_CURRENT_WORKSPACE request / response between materialization admission and compile response completion")
    assert row["inside_8192_preparation_cap"] == "YES"
    assert "remaining effect bounds" in row["other_applicable_bound"]


def test_independent_observation_and_cleanup_bounds_are_exact_existing_profiles(requirement):
    controller = load_json(ROOT / CONTROLLER)
    bounds = requirement["independent_bounds"]
    assert bounds["observation"] == controller["bounds"]["observation"]
    assert bounds["cleanup"] == controller["bounds"]["cleanup"]
    assert bounds["outer_custodian"] == controller["cleanup"]["outer"]["bounds"]
    assert bounds["retained_lifetime_gate"] == controller["bounds"]["retention"]
    assert bounds["all_frames_max_bytes"] == 8192
    assert bounds["observation"] == {"timeout_ms": 5000, "outer_timeout_ms": 10000,
        "request_max_bytes": 8192, "response_max_bytes": 8192, "work_entries_max": 3,
        "tmp_entries_max": 0, "process_tasks_max": 128, "regular_file_bytes_max": 33007,
        "writer_records_max": 128, "writer_handles_max": 128, "mount_records_max": 2}
    assert "Missing reviewed retained bounds denies readiness" in bounds["no_unbounded_exemption"]
    diagnostics = bounds["outside_diagnostics"]
    assert "do not independently bound arbitrary controller stderr" in diagnostics
    assert "unexpected/nonprotocol output fails closed" in diagnostics
    assert "finite capture bounds for all outer channels" in diagnostics
    assert "before operational eligibility" in diagnostics
    assert "No new universal stderr number is invented" in diagnostics


def test_candidate_session_limits_and_framing_remain_conditional(requirement):
    candidate = requirement["independent_bounds"]["conditional_candidate_A_only"]
    assert candidate["accepted"] is False
    assert candidate["session_bytes_each_direction"] == 65536
    assert candidate["session_request_count_including_cleanup"] == 64
    assert candidate["reserved_cleanup_request_slots"] == 2
    assert (candidate["retained_total_ms"], candidate["work_cutoff_ms"],
            candidate["cleanup_reserve_ms"]) == (30000, 20000, 10000)
    assert candidate["framing_header_bytes"] == 4
    assert candidate["whole_frame_max_bytes"] == 8192
    assert "not final transport" in candidate["reason"]


def test_cleanup_survives_full_effect_allowance_and_preemption(requirement):
    cleanup = requirement["cleanup"]
    assert cleanup["cleanup_is_preparation"] is False
    assert cleanup["membership"] == "OUTSIDE_PREPARATION_CAPTURE_WITH_SEPARATE_BOUND"
    assert cleanup["preemption_allowed"] is True
    assert cleanup["duty_mandatory"] is True
    assert cleanup["requires_remaining_effect_budget"] is False
    assert "all 8192 bytes without spending cleanup capacity" in cleanup["safety_capacity"]
    assert "deny ordinary admission" in cleanup["safety_capacity"]
    assert "already-started ordinary response" in cleanup["shared_channel"]
    assert "independent exact-generation outer teardown" in cleanup["shared_channel"]
    assert "Ordinary admission cannot spend" in cleanup["reserves"]
    assert "Removal and absence do not prove missing child reaping/EOF" in cleanup["lost_inner_evidence"]


def test_normative_table_has_complete_explicit_message_and_embedded_evidence_coverage(requirement):
    rows = requirement["normative_table"]
    labels = [row["event_message"] for row in rows]
    assert len(labels) == len(set(labels))
    assert len(rows) >= 15
    fields = {"event_message", "semantic_lifecycle_owner", "mandatory",
              "inside_8192_preparation_cap", "other_applicable_bound", "reason"}
    for row in rows:
        assert set(row) == fields
        assert all(type(value) is str and value.strip() and value.lower() != "later"
                   for value in row.values())
        assert row["inside_8192_preparation_cap"] in {
            "YES", "NO", "YES_IN_PARENT_ONCE", "NO_CONTROLLER_WIRE_BYTES"}
    expected = {
        "OBSERVE_EMPTY_WORKSPACE request / response": "NO",
        "MATERIALIZE_EXACT_SCENARIO_SOURCE request / response": "YES",
        "materialize response.result.workspace_state": "YES_IN_PARENT_ONCE",
        "COMPILE_EXACT_SCENARIO request / response": "YES",
        "compile response.result.workspace_state": "YES_IN_PARENT_ONCE",
        "fresh prepared-current-state OBSERVE_* request / response after compile response": "NO",
        "preparation receipt authentication": "NO_CONTROLLER_WIRE_BYTES",
        "PREPARE_EXCLUSIVE_HANDOFF request / response": "NO",
        "BEGIN_CLEANUP request / response": "NO",
        "CLEANUP_AND_REPORT request / response": "NO",
        "outer TERMINATE_REMOVE_EXACT_RETAINED_GENERATION": "NO",
        "outer OBSERVE_EXACT_RETAINED_GENERATION_ABSENCE": "NO",
    }
    for label, membership in expected.items():
        assert table_row(requirement, label)["inside_8192_preparation_cap"] == membership
    operations = load_json(ROOT / CONTROLLER)["operations"]
    complete_text = " ".join(labels)
    assert all(operation["tag"] in complete_text for operation in operations)


def test_request_response_child_and_host_evidence_ledgers_do_not_double_count(requirement):
    streams = requirement["stream_accounting"]
    assert "stdin into captured outer stdout or stderr" in streams["controller_stdin_requests"]
    assert "no bidirectional sum" in streams["controller_stdin_requests"]
    assert "once" in streams["controller_stdout_responses"]
    assert "actual transport framing" in streams["controller_stdout_responses"]
    assert "All bytes observed" in streams["controller_stderr"]
    assert "No untagged/shared stderr may be favorably relabeled" in streams["controller_stderr"]
    for key in ("compiler_child_stdout", "compiler_child_stderr"):
        assert "<=2048" in streams[key]
        assert "observed bytes=0" in streams[key]
        assert "do not add it twice" in streams[key]
    assert "no invented four-byte prefix" in streams["outer_custodian_channel"]
    assert "not extra controller wire responses" in streams["host_in_process_composed_evidence"]
    assert "future serialization would require its actual bounded channel accounting" in streams["host_in_process_composed_evidence"]
    assert "No transport mapping is selected" in streams["payload_vs_physical"]
    assert "never added twice within one ledger" in streams["attempt_vs_session"]
    assert "ordinary response suffixes past the endpoint" in streams["unattributed_or_late_bytes"]


def test_handoff_is_optional_retained_evidence_and_grants_no_consumer_authority(requirement):
    handoff = requirement["handoff"]
    assert handoff["required_for_preparation_eligibility"] is False
    assert handoff["inside_preparation_capture"] is False
    assert handoff["frame_budget_class"] == "retained-session/handoff budget"
    assert handoff["existing_operation_bounds_profile"] == "observation"
    assert handoff["activation_status"] == "PROOF_UNRESOLVED"
    assert handoff["future_consumer_capture_scope"] == "UNRESOLVED_FUTURE_CONSUMER_SCOPE"
    assert handoff["consumer_authority_invented"] is False


def test_old_proof_is_data_only_and_next_phase_requires_attainable_witness(requirement):
    consequence = requirement["budget_arithmetic_consequence"]
    old = load_json(ROOT / PROOF)
    assert consequence["historical_proof_outcome_unchanged"] == old["typed_result"] == "AGGREGATE_BUDGET_SCOPE_UNRESOLVED"
    assert consequence["old_proof_rerun"] is False
    assert consequence["next_phase"] == "SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1R"
    assert consequence["next_phase_requirement"] == "TRUTHFUL_ATTAINABLE_WITNESS_REQUIRED"
    assert consequence["feasibility_decision"] == "NOT_MADE_IN_SCOPE_PHASE"
    assert consequence["budget_blocker_removed"] is False
    assert consequence["known_relaxations_read_only"] == {
        "materialize_compile_payload": 6702, "with_fresh_CURRENT_payload": 9423}
    historical_bounds = old["formal_conservative_payload_lower_bounds"]
    assert consequence["known_relaxations_read_only"]["materialize_compile_payload"] == historical_bounds[
        "guaranteed_materialize_compile_response_payload_bytes"]
    assert consequence["known_relaxations_read_only"]["with_fresh_CURRENT_payload"] == historical_bounds[
        "conditional_with_fresh_current_response_payload_bytes"]
    assert "does not prove an attainable semantic identity encoding" in consequence["reason"]


def test_authority_and_domain_operational_effects_are_strictly_zero(requirement):
    assert requirement["authority_flags"]
    assert all(type(value) is bool and value is False
               for value in requirement["authority_flags"].values())
    assert requirement["operational_effects"]
    assert all(type(value) is int and value == 0
               for value in requirement["operational_effects"].values())


def test_authoring_source_has_only_data_dependencies_and_no_execution_imports():
    tree = ast.parse((HERE / "write_requirement.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile", "__import__"}
    assert imported == {"hashlib", "json", "pathlib"}
    assert not any(name.startswith(("core.", "subprocess", "socket", "requests"))
                   for name in imported)


@pytest.mark.parametrize("text", ['{"same": 1, "same": 2}', '{"value": NaN}',
                                  '{"value": Infinity}', '{"value": -Infinity}'])
def test_evidence_json_parser_rejects_duplicate_keys_and_nonfinite_constants(text):
    with pytest.raises(ValueError):
        json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
