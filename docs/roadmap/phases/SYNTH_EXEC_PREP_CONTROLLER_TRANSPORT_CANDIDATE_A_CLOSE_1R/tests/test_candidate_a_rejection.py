"""Independent source, scalar partition and conservative-bound regressions."""
import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[3]
PHASES = OUT.parent
OLD = PHASES / "SYNTH_EXEC_PREP_CONTROLLER_TRANSPORT_CANDIDATE_A_CLOSE_1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def frozen(suffix, name):
    return read(PHASES / ("SYNTH_EXEC_PREP_CONTROLLER_" + suffix) / name)


def leaf_items(value, path=""):
    if isinstance(value, dict):
        if "$unresolved_scalar_width" in value:
            yield path, value
        else:
            for key, child in value.items():
                yield from leaf_items(child, path + "/" + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaf_items(child, path + "/" + str(index))


def canonical_width(value, widths):
    if isinstance(value, dict) and "$unresolved_scalar_width" in value:
        return widths[value["$unresolved_scalar_width"]]
    if isinstance(value, dict):
        return 2 + max(0, len(value)-1) + sum(
            len(json.dumps(key, ensure_ascii=True)) + 1 + canonical_width(child, widths)
            for key, child in value.items())
    if isinstance(value, list):
        return 2 + max(0, len(value)-1) + sum(canonical_width(child, widths) for child in value)
    return len(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii"))


def profile_and_projection():
    projection = frozen("KERNEL_IDENTITY_CONTRACT_1", "budget_projection.json")
    profile = next(row for row in frozen("BUDGET_PROOF_1R", "budget_witness.json")["profiles"]
                   if row["name"] == projection["source_profile"])
    return profile, projection


def test_all_input_hashes_and_prior_closure_index_match():
    inputs = read(OUT / "input_artifacts.json")
    snapshot = read(OUT / "preservation_baseline.json")["files"]
    for row in inputs["files"]:
        content = (ROOT / row["path"]).read_bytes()
        assert len(content) == row["bytes"]
        assert sha256(content).hexdigest() == row["sha256"] == snapshot[row["path"]]["sha256"]
    for row in inputs["embedded_hash_checks"]:
        assert sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["expected_sha256"]
    for row in inputs["prior_final_index_checks"]:
        assert sha256((OLD / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_prior_unresolved_closure_is_preserved_and_correctly_related():
    prior, result = read(OLD / "closure.json"), read(OUT / "closure.json")
    assert prior["typed_result"] == "CANDIDATE_A_CLOSURE_UNRESOLVED"
    assert prior["candidate_rejection_published"] is False
    assert result["historical_closure"]["typed_result"] == prior["typed_result"]
    assert result["historical_closure"]["historical_stop_correct"] is True
    assert result["historical_closure"]["bytes_changed"] is False


def test_exact_two_omitted_class_paths_share_one_width_interval():
    profile, projection = profile_and_projection()
    responses = [row for row in profile["messages"] if row["direction"] == "response"]
    compile_tree = responses[1]["annotated_symbolic_layout"]
    class_fields = [(path, leaf) for path, leaf in leaf_items(compile_tree) if leaf["family"] == "class_size"]
    assert {path for path, _ in class_fields} == {
        "/result/class_metadata/size_bytes", "/result/workspace_state/work_manifest/2/size_bytes"}
    assert len(class_fields) == 2
    assert {leaf["$unresolved_scalar_width"] for _, leaf in class_fields} == {"class_size_digits"}
    assert all(leaf["canonical_width_interval"] == [1, 5] for _, leaf in class_fields)
    assert projection["class_size_legal_envelope"] == [1, 32768]
    assert all(row["symbol"] != "class_size_digits" for row in projection["responses"][1]["unresolved_residual_leaves"])


def test_independent_full_symbolic_evaluation_for_every_legal_class_width():
    profile, projection = profile_and_projection()
    physical = []
    for digits in range(1, 6):
        totals = []
        for message, projected in zip([row for row in profile["messages"] if row["direction"] == "response"], projection["responses"]):
            widths = dict(message["width_assignment"])
            for row in projected["selected_substitutions"]:
                widths[row["symbol"]] = row["partial_lower_canonical_json_bytes"]
            if "class_size_digits" in widths:
                widths["class_size_digits"] = digits
            totals.append(canonical_width(message["annotated_symbolic_layout"], widths))
        assert totals[0] == 3567
        physical.append(sum(totals) + 2 * 4)
    assert physical == [8821, 8823, 8825, 8827, 8829]
    result = read(OUT / "closure.json")
    assert [row["lower_physical_subtotal"] for row in result["class_width_table"]] == physical
    assert [row["proven_excess_lower_bound"] for row in result["class_width_table"]] == [629, 631, 633, 635, 637]


def test_residual_partition_and_every_lower_width_match_frozen_sources():
    profile, projection = profile_and_projection()
    checked = read(OUT / "premise_audit.json")
    counts = []
    for message, projected, audit in zip([row for row in profile["messages"] if row["direction"] == "response"],
                                         projection["responses"], checked["response_audit"]):
        layout = dict(leaf_items(message["annotated_symbolic_layout"]))
        residuals = projected["unresolved_residual_leaves"]
        assert Counter(row["symbol"] for row in residuals) == Counter(projected["unresolved_residual_width_terms"])
        assert {row["path"] for row in audit["residuals"]} == {row["path"] for row in residuals}
        counts.append(len(residuals))
        for row in audit["residuals"]:
            leaf = layout[row["path"]]
            minimum = (len(row["symbol"].split(".", 1)[1]) + 6 if row["symbol"].startswith("namespace.")
                       else 5 if leaf["family"] == "mode"
                       else 3 if leaf["family"] == "kernel_start"
                       else leaf["canonical_width_interval"][0])
            assert row["lower_width"] == minimum
            assert row["expression"] == "Q_actual[" + row["symbol"] + "]-" + str(minimum)
            assert row["nonnegative"] is True
        covered = {row["path"] for row in audit["residuals"] + audit["exact_width_leaves"]}
        class_paths = {path for path, leaf in layout.items() if leaf["family"] == "class_size"}
        assert covered.isdisjoint(class_paths)
        assert covered | class_paths == set(layout)
    assert counts == [39, 49]
    assert checked["existing_residual_leaf_count"] == sum(counts) == 88


def test_candidate_mapping_and_attempt_cap_are_exactly_scoped():
    profile, _ = profile_and_projection()
    selection = frozen("TRANSPORT_1", "selection.json")
    scope = frozen("BUDGET_SCOPE_REQ_1", "requirement.json")
    assert selection["selected_architecture"] is selection["selected_transport"] is None
    assert "Persistent single-thread PID1" in selection["child_process"]["ownership"]
    assert selection["wire"]["maximum_header_bytes"] == 4
    assert "cumulatively over whole preparation attempt, INCLUDING wire headers" in selection["wire"]["stream_budgets"]
    assert scope["caps"]["outer_stdout_max_bytes"] == 8192
    for message in profile["messages"]:
        response = message["direction"] == "response"
        assert message["inside_stdout_cap"] is response
        assert message["physical_stream"] == ("controller_stdout" if response else "controller_stdin")
    assert profile["request_bytes_added_to_stdout"] == profile["candidate_A_stderr_success_bytes"] == 0


def test_theorem_is_a_lower_bound_without_attainable_equality_claim():
    theorem = read(OUT / "closure.json")["theorem"]
    assert theorem["class_width_adjustment_interval"] == [-8, 0]
    assert theorem["physical_stdout_lower_bound_bytes"] == 8821 > theorem["frozen_cumulative_stdout_cap_bytes"] == 8192
    assert theorem["proven_excess_lower_bound_bytes"] == 629
    assert theorem["attainable_minimum_established"] is theorem["exact_minimum_claimed"] is False
    assert theorem["actual_class_size_selected"] is theorem["actual_kernel_values_required"] is False
    assert theorem["witness_required"] is theorem["finite_residual_maxima_required"] is False


def test_writer_topology_retains_lower_profile_and_no_completeness():
    profile, projection = profile_and_projection()
    result = read(OUT / "closure.json")
    writer = result["writer_lower_profile"]
    assert (profile["controller_writers"], profile["potential_write_handles_per_writer"]) == (1, 2)
    assert (writer["controller_writers"], writer["potential_root_handles_per_response"]) == (1, 2)
    assert writer["complete"] is writer["added_record_count_or_values_selected"] is False
    assert projection["writer_completeness"] == result["writer_completeness"] == "WRITER_INVENTORY_COMPLETENESS_UNRESOLVED"
    assert read(OUT / "premise_audit.json")["additional_truthful_records_cannot_reduce_bound"] is True


def test_only_candidate_a_is_rejected_and_no_remaining_design_is_selected():
    result = read(OUT / "closure.json")
    assert result["typed_result"] == "CANDIDATE_A_REJECTED_BUDGET_INCOMPATIBLE"
    assert result["candidate_status"] == "REJECTED_BUDGET_INCOMPATIBLE"
    assert result["candidate"] == "A" and result["candidate_ever_selected"] is False
    assert result["candidate_rejection_recorded"] is True
    assert result["transport_status"] == "TRANSPORT_SELECTION_UNRESOLVED"
    assert result["overall_universal_budget_feasibility"] == "UNRESOLVED"
    assert result["kernel_status"] == "KERNEL_IDENTITY_CONTRACT_UNRESOLVED"
    assert result["settled_projection_rules_frozen"] is True
    assert result["replacement_selected"] is result["remaining_candidates_ranked"] is False
    assert result["universal_transport_impossibility_claimed"] is False
    assert all(value is False for value in result["authority_flags"].values())
    assert all(type(value) is int and value == 0 for value in result["operational_effects"].values())
    assert result["stop"] is True


def test_registry_is_preserved_and_rejection_is_an_additive_record():
    addendum = read(OUT / "roadmap_addendum.json")
    assert addendum["candidate_current_status"] == "REJECTED_BUDGET_INCOMPATIBLE"
    assert addendum["prior_closure_result"] == "CANDIDATE_A_CLOSURE_UNRESOLVED"
    assert addendum["phase_completion_history_changed"] is addendum["production_registry_changed"] is False
    registry_path = "docs/roadmap/phase_registry.json"
    baseline = read(OUT / "preservation_baseline.json")["files"][registry_path]
    assert sha256((ROOT / registry_path).read_bytes()).hexdigest() == baseline["sha256"]


def test_proof_source_has_no_effect_or_owner_import_surface():
    tree = ast.parse((OUT / "proof.py").read_text(encoding="utf-8"))
    forbidden_imports = {"core", "subprocess", "socket", "requests", "http", "urllib", "importlib"}
    forbidden_calls = {"exec", "eval", "__import__", "Popen", "run", "check_output", "system", "fork", "spawn", "stat", "lstat", "readlink"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name.split(".")[0] in forbidden_imports for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_imports
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            assert name not in forbidden_calls
