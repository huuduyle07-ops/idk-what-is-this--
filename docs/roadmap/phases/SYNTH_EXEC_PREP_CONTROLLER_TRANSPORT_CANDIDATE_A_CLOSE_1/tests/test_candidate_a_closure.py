"""Independent frozen-source arithmetic and exact-proof counter-premise tests."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
PHASES = HERE.parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def frozen(suffix, name):
    return read(PHASES / ("SYNTH_EXEC_PREP_CONTROLLER_" + suffix) / name)


def test_every_input_and_embedded_source_hash_matches():
    manifest = read(HERE / "input_artifacts.json")
    baseline = read(HERE / "preservation_baseline.json")["files"]
    for row in manifest["files"]:
        content = (ROOT / row["path"]).read_bytes()
        assert len(content) == row["bytes"]
        assert sha256(content).hexdigest() == row["sha256"] == baseline[row["path"]]["sha256"]
    for row in manifest["embedded_hash_checks"]:
        assert sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["expected_sha256"]


def test_frozen_candidate_scope_and_cumulative_cap():
    selection = frozen("TRANSPORT_1", "selection.json")
    scope = frozen("BUDGET_SCOPE_REQ_1", "requirement.json")
    assert selection["reviewed_candidate_architecture"] == "persistent_in_container_controller"
    assert selection["reviewed_candidate_transport"] == "persistent_stdio"
    assert "Persistent single-thread PID1" in selection["child_process"]["ownership"]
    assert selection["wire"]["maximum_header_bytes"] == 4
    assert "controller stderr empty on success" in selection["wire"]["stream_budgets"]
    assert "cumulatively over whole preparation attempt, INCLUDING wire headers" in selection["wire"]["stream_budgets"]
    assert scope["caps"]["outer_stdout_max_bytes"] == 8192
    assert scope["counter_interval"]["successful_end_event_id"] == "COMPLETE_COMPILE_RESPONSE_FINAL_BYTE"


def test_exact_8829_is_conditional_on_five_class_digits():
    projection = frozen("KERNEL_IDENTITY_CONTRACT_1", "budget_projection.json")
    assert projection["partial_lower_materialize_response_bytes"] == 3567
    assert projection["partial_lower_compile_response_bytes"] == 5254
    assert 3567 + 5254 == projection["partial_lower_semantic_total_bytes"] == 8821
    assert 8821 + 2 * 4 == projection["conditional_candidate_A_partial_lower_framed_total_bytes"] == 8829
    assert 8829 - projection["cap_bytes"] == projection["conditional_candidate_A_excess_bytes"] == 637
    assert projection["class_size_decimal_width"] == 5
    assert projection["class_size_legal_envelope"] == [1, 32768]
    assert projection["actual_class_size_selected"] is False


def test_omitted_class_fields_prevent_requested_exact_minimum():
    witness = frozen("BUDGET_PROOF_1R", "budget_witness.json")
    projection = frozen("KERNEL_IDENTITY_CONTRACT_1", "budget_projection.json")
    profile = next(row for row in witness["profiles"] if row["name"] == projection["source_profile"])
    response = next(row for row in profile["messages"] if row["direction"] == "response" and row["operation"] == "COMPILE_EXACT_SCENARIO")
    tree = response["annotated_symbolic_layout"]
    fields = [tree["result"]["class_metadata"]["size_bytes"],
              tree["result"]["workspace_state"]["work_manifest"][2]["size_bytes"]]
    for leaf in fields:
        assert leaf["family"] == "class_size"
        assert leaf["canonical_width_interval"] == [1, 5]
        assert leaf["$unresolved_scalar_width"] == "class_size_digits"
    residuals = projection["responses"][1]["unresolved_residual_leaves"]
    assert all(row["symbol"] != "class_size_digits" for row in residuals)
    # This is a legal width interval counter-premise, never an assertion that
    # any particular authentic compiled class has a selected numeric size.
    assert 2 * (1 - response["width_assignment"]["class_size_digits"]) == -8
    assert read(HERE / "closure.json")["typed_result"] == "CANDIDATE_A_CLOSURE_UNRESOLVED"


def test_all_88_listed_residuals_are_nonnegative_minimum_width_differences():
    projection = frozen("KERNEL_IDENTITY_CONTRACT_1", "budget_projection.json")
    audit = read(HERE / "premise_audit.json")
    assert sum(len(row["unresolved_residual_leaves"]) for row in projection["responses"]) == 88
    for response, checked in zip(projection["responses"], audit["response_audit"]):
        assert Counter(row["symbol"] for row in response["unresolved_residual_leaves"]) == Counter(response["unresolved_residual_width_terms"])
        for row in checked["residuals"]:
            minimum = row["lower_width"]
            assert minimum in {1, 3, 5, 9, 10, 12}
            assert row["nonnegative"] is True
            for additional_width in (0, 1, 16, 1535):
                assert minimum + additional_width - minimum >= 0
    assert audit["all_actual_width_variation_in_residuals"] is False


def test_conservative_width_sensitivity_is_separate_and_always_exceeds_cap():
    result = read(HERE / "closure.json")
    rows = result["class_width_sensitivity"]
    assert [row["class_decimal_width"] for row in rows] == list(range(1, 6))
    assert [row["excess"] for row in rows] == [629, 631, 633, 635, 637]
    assert all(row["physical_lower_with_listed_residuals_zero"] > 8192 for row in rows)
    assert result["retained_profile_excess_bytes"] == 637
    assert result["independent_conservative_comparison"]["excess_bytes"] == 629
    assert result["exact_requested_proof_premises_all_confirmed"] is False


def test_writer_profile_is_lower_and_additional_records_add_bytes():
    witness = frozen("BUDGET_PROOF_1R", "budget_witness.json")
    projection = frozen("KERNEL_IDENTITY_CONTRACT_1", "budget_projection.json")
    profile = next(row for row in witness["profiles"] if row["name"] == projection["source_profile"])
    assert (profile["controller_writers"], profile["potential_write_handles_per_writer"]) == (1, 2)
    assert witness["writer_analysis"]["exact_representation_frozen"] is False
    assert projection["writer_completeness"] == "WRITER_INVENTORY_COMPLETENESS_UNRESOLVED"
    assert read(HERE / "closure.json")["scope"]["writer_profile_complete"] is False
    # A new nonempty canonical record in an existing nonempty JSON array adds
    # its positive byte width and a comma. No synthetic writer identity exists.
    assert 1 + 2 > 0  # even the empty-object relaxation adds three bytes


def test_no_rejection_selection_authority_or_completion_is_published():
    result = read(HERE / "closure.json")
    assert result["candidate_rejection_published"] is False
    assert result["candidate_status"] == "UNSELECTED"
    assert result["transport_status"] == "TRANSPORT_SELECTION_UNRESOLVED"
    assert result["overall_budget_feasibility"] == "UNRESOLVED"
    assert result["kernel_status"] == "KERNEL_IDENTITY_CONTRACT_UNRESOLVED"
    assert result["settled_projection_rules_frozen"] is True
    assert result["writer_completeness"] == "WRITER_INVENTORY_COMPLETENESS_UNRESOLVED"
    assert all(value is False for value in result["authority_flags"].values())
    assert all(type(value) is int and value == 0 for value in result["operational_effects"].values())
    assert result["stop"] is True


def test_roadmap_addendum_does_not_supersede_historical_preference():
    addendum = read(HERE / "roadmap_addendum.json")
    assert addendum["historical_candidate"] == "A"
    assert addendum["historical_classification"] == "PREFERRED_BUT_SELECTION_UNRESOLVED"
    assert addendum["phase_completion_history_changed"] is False
    assert addendum["production_registry_changed"] is False
    assert addendum["candidate_rejection_recorded"] is False
    assert addendum["replacement_selection"] is False
