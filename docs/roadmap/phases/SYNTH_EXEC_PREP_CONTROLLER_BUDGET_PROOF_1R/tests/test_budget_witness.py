"""Proof-obligation regressions, not runtime/controller tests."""
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parents[1]
API = runpy.run_path(str(HERE / "proof.py"))


def test_no_attainable_or_physical_claim_from_relaxations():
    result = API["build"]()
    assert result["typed_result"] == "BUDGET_WITNESS_UNRESOLVED"
    assert result["identity_subresult"] == "BUDGET_WITNESS_IDENTITY_ENCODING_UNRESOLVED"
    for key in ("attainable_witness_produced", "universal_impossibility_proved",
                "budget_blocker_removed", "transport_selected", "candidate_A_selected"):
        assert result[key] is False
    assert result["exact_attainable_aggregate_payload_bytes"] is None
    assert all(value is False for value in result["authority_flags"].values())
    assert all(value == 0 for value in result["operational_effects"].values())


def test_exact_effect_membership_and_complete_embedded_states():
    result = API["build"]()
    assert len(result["effect_sequence"]) == 4
    assert not result["intervening_observation_required"]
    for profile in result["profiles"]:
        assert len(profile["messages"]) == 4
        assert all(not row["operation"].startswith("OBSERVE_") for row in profile["messages"])
        for row in profile["messages"]:
            assert row["inside_effect_interval"]
            value = row["annotated_symbolic_layout"]
            assert value["challenge"] is None
            if row["direction"] == "response":
                state = value["result"]["workspace_state"]
                assert len(state["mounts"]) == 2
                assert len(state["process_exclusivity_observation"]["processes"]) == 1
                assert len(state["process_exclusivity_observation"]["processes"][0]["tasks"]) == 1
                assert state["observation_challenge"]["canonical_width_interval"] == [66, 66]
                assert len(state["work_manifest"]) == (3 if row["operation"].startswith("COMPILE") else 2)


def test_canonical_accounting_is_additive_and_directions_are_separate():
    for profile in API["build"]()["profiles"]:
        response_total = 0
        for row in profile["messages"]:
            parts = row["field_and_subtree_contributions"]
            assert sum(part["own_bytes"] for part in parts) == row["canonical_payload_bytes"]
            calculated = row["fixed_bytes"] + sum(count * row["width_assignment"][name]
                for name, count in row["width_terms"].items())
            assert calculated == row["canonical_payload_bytes"]
            if row["direction"] == "response":
                response_total += calculated
        assert response_total == profile["response_aggregate_payload_bytes"]
        assert profile["request_bytes_added_to_stdout"] == 0
        if profile["candidate_A_framed_aggregate_bytes"] is not None:
            assert profile["candidate_A_framed_aggregate_bytes"] == response_total + 8
            assert profile["candidate_A_stderr_success_bytes"] == 0


def test_class_width_envelope_and_hashes_never_fabricate_a_class():
    totals = []
    for digits in range(1, 6):
        profile = API["profile"]("class-width-test", candidate=True, class_digits=digits)
        totals.append(profile["response_aggregate_payload_bytes"])
        compile_row = profile["messages"][3]
        assert compile_row["width_terms"]["class_size_digits"] == 2
        assert compile_row["width_terms"]["class_sha256"] == 2
        assert compile_row["width_assignment"]["class_sha256"] == 66
    assert totals == [totals[0] + 2 * offset for offset in range(5)]
    assert totals[-1] - totals[0] == 8
    assert all(total + 8 <= 8192 for total in totals)


def test_schema_max_utf8_is_not_canonical_width_and_modes_use_full_envelope():
    canonical = API["canonical"]
    assert len(canonical("\x01" * 256)) == 1538
    profile = API["profile"]("upper-test", envelope=True)
    row = profile["messages"][3]
    assert row["width_assignment"]["mode./work/classes"] == 19
    assert row["width_assignment"]["workspace_capability_id"] == 1538
    assert profile["response_aggregate_payload_bytes"] > 8192
    assert not profile["attainable_execution_witness"]


def test_writer_free_profile_never_removes_truthful_inventory_requirement():
    profiles = {row["name"]: row for row in API["build"]()["profiles"]}
    free = profiles["universal_lower_relaxation"]
    writer = profiles["minimal_writer_layout_lower_widths"]
    assert free["writer_free_is_relaxation_only"]
    assert writer["controller_writers"] == 1
    for row in writer["messages"]:
        if row["direction"] == "response":
            writers = row["annotated_symbolic_layout"]["result"]["workspace_state"]["process_exclusivity_observation"]["writers"]
            assert len(writers) == 1 and len(writers[0]["handles"]) == 2
    assert writer["response_aggregate_payload_bytes"] > free["response_aggregate_payload_bytes"]
    assert not API["build"]()["writer_analysis"]["exact_representation_frozen"]


def test_sensitivity_cannot_be_promoted_to_witness_and_preserves_stable_identity():
    result = API["build"]()
    sensitivity = result["sensitivity"]
    assert sensitivity["effect_of_one_more_canonical_byte_at_every_future_owner_id"] == 17
    assert sensitivity["all_equal_owner_content_width_fit_threshold_with_every_other_lower_width_held"] == 8
    assert sensitivity["extra_bytes_at_broad_schema_width_ceiling_by_family"]["mode"] == 162
    assert [(row["candidate_A_framed_bytes"], row["remaining_margin"])
            for row in sensitivity["conventional_mode_width_sensitivity"]] == [(8095, 97), (8104, 88)]
    assert not sensitivity["owner_width_threshold_is_attainable_or_recommended"]
    assert not sensitivity["frozen_kernel_max_width_fit"]
    for profile in result["profiles"]:
        responses = [row for row in profile["messages"] if row["direction"] == "response"]
        names = [row["annotated_symbolic_layout"]["result"]["workspace_state"]["stable_fingerprint"]["$unresolved_scalar_width"]
                 for row in responses]
        assert names == ["stable_fingerprint", "stable_fingerprint"]


def test_source_is_ast_recovered_exact_239_bytes_without_owner_import():
    audit = API["source_audit"]()
    assert audit["bytes"] == 239
    assert audit["sha256"] == "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
    assert audit["wire_source_bytes"] == 0


def test_frozen_history_scope_and_transport_stay_frozen():
    phases = HERE.parent
    old = json.loads((phases / "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1_REPORT.json").read_text(encoding="utf-8"))
    scope = json.loads((phases / "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1/requirement.json").read_text(encoding="utf-8"))
    assert old["typed_result"] == "AGGREGATE_BUDGET_SCOPE_UNRESOLVED"
    assert scope["typed_result"] == "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_COMPLETE"
    schema = API["SCHEMA"]
    assert schema["transport_byte_prefix_unselected"]
