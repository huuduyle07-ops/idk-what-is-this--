"""Pure corrected lower-bound proof over frozen JSON; no historical code execution.

Only this additive directory is writable. No kernel values, class bytes, owner
identities, controller, writer inventory, or replacement transport are created.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PHASES = OUT.parent
PHASE_ID = "SYNTH.EXEC.PREP.CONTROLLER.TRANSPORT.CANDIDATE_A.CLOSE.1R"
PREFIX = "SYNTH_EXEC_PREP_CONTROLLER_"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source(suffix, name):
    return PHASES / (PREFIX + suffix) / name


def leaves(value, path=""):
    if isinstance(value, dict):
        if "$unresolved_scalar_width" in value:
            yield path, value
        else:
            for key, child in value.items():
                yield from leaves(child, path + "/" + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, path + "/" + str(index))


def width(value, assignment):
    if isinstance(value, dict):
        if "$unresolved_scalar_width" in value:
            return assignment[value["$unresolved_scalar_width"]]
        return 2 + max(0, len(value) - 1) + sum(
            len(json.dumps(key, ensure_ascii=True).encode("ascii")) + 1 + width(child, assignment)
            for key, child in value.items())
    if isinstance(value, list):
        return 2 + max(0, len(value) - 1) + sum(width(child, assignment) for child in value)
    return len(json.dumps(value, ensure_ascii=True, separators=(",", ":"),
                          sort_keys=True, allow_nan=False).encode("ascii"))


def frozen_record(path):
    content = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(content), sha256=sha256(content).hexdigest())


def residual_basis(leaf, symbol, assigned):
    family = leaf["family"]
    if symbol.startswith("namespace."):
        minimum = len(symbol.split(".", 1)[1]) + 6
        basis = "Frozen raw namespace grammar: quoted kind:[canonical unsigned decimal], at least one digit."
    elif family == "mode":
        minimum, basis = 5, "Frozen full st_mode includes required regular-file/directory type bits."
    elif family == "kernel_start":
        minimum, basis = 3, "Frozen start-tick grammar is a nonempty quoted canonical decimal string."
    else:
        interval = leaf["canonical_width_interval"]
        minimum = interval[0]
        basis = "Unchanged schema lower width: nonempty generic ID string or canonical integer."
    assert assigned == minimum, (symbol, assigned, minimum)
    return basis


def main():
    baseline = read(OUT / "preservation_baseline.json")["files"]
    prior_dir = PHASES / "SYNTH_EXEC_PREP_CONTROLLER_TRANSPORT_CANDIDATE_A_CLOSE_1"
    prior = read(prior_dir / "closure.json")
    assert prior["typed_result"] == "CANDIDATE_A_CLOSURE_UNRESOLVED"
    assert prior["candidate_rejection_published"] is False
    selection = read(source("TRANSPORT_1", "selection.json"))
    history = read(source("BUDGET_PROOF_1R", "budget_witness.json"))
    projection = read(source("KERNEL_IDENTITY_CONTRACT_1", "budget_projection.json"))
    owner = read(source("IDENTITY_ENCODING_CONTRACT_1", "contract.json"))
    kernel = read(source("KERNEL_IDENTITY_CONTRACT_1", "contract.json"))
    scope = read(source("BUDGET_SCOPE_REQ_1", "requirement.json"))
    profile = next(row for row in history["profiles"] if row["name"] == projection["source_profile"])
    input_paths = {ROOT / row["path"] for row in read(prior_dir / "input_artifacts.json")["files"]}
    input_paths.update(path for path in prior_dir.iterdir() if path.is_file())
    embedded_checks = []
    for row in read(prior_dir / "input_artifacts.json")["embedded_hash_checks"]:
        actual = sha256((ROOT / row["path"]).read_bytes()).hexdigest()
        assert actual == row["expected_sha256"]
        embedded_checks.append(dict(path=row["path"], expected_sha256=row["expected_sha256"], actual_sha256=actual, matched=True))
    historical_index_checks = []
    for row in read(prior_dir / "final_artifact_checks.json")["files_checked"]:
        assert sha256((prior_dir / row["path"]).read_bytes()).hexdigest() == row["sha256"]
        historical_index_checks.append(dict(path=row["path"], sha256=row["sha256"], matched=True))
    input_records = [frozen_record(path) for path in sorted(input_paths)]
    for row in input_records:
        assert row["sha256"] == baseline[row["path"]]["sha256"]
    for row in projection["source_artifacts"]:
        assert sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    for row in read(prior_dir / "input_artifacts.json")["files"]:
        assert sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    write("input_artifacts.json", dict(phase_id=PHASE_ID, files=input_records,
        all_match_initial_preservation_baseline=True, embedded_hash_checks=embedded_checks,
        embedded_hashes_all_match=True, prior_final_index_checks=historical_index_checks,
        prior_final_index_all_match=True, prior_input_hashes_all_match=True,
        historical_code_imported_or_executed=False))

    assert selection["typed_result"] == "TRANSPORT_SELECTION_UNRESOLVED"
    assert selection["selected_transport"] is None and selection["selected_architecture"] is None
    assert selection["reviewed_candidate_architecture"] == "persistent_in_container_controller"
    assert selection["reviewed_candidate_transport"] == "persistent_stdio"
    candidate = next(row for row in selection["candidates"] if row["id"] == "A")
    assert candidate["classification"] == "PREFERRED_BUT_SELECTION_UNRESOLVED"
    assert "Persistent single-thread PID1" in selection["child_process"]["ownership"]
    assert selection["wire"]["length_encoding"] == "unsigned 32-bit big-endian binary, exactly four octets"
    assert selection["wire"]["maximum_header_bytes"] == 4
    assert "controller stderr empty on success" in selection["wire"]["stream_budgets"]
    assert "cumulatively over whole preparation attempt, INCLUDING wire headers" in selection["wire"]["stream_budgets"]
    assert "full 64-lowercase-hex container ID" in selection["bootstrap"]["start_channel"]
    for generation in ("workspace_generation", "controller_generation"):
        assert "Independent owner-generated 32-byte hex token" in selection["generations"][generation]
    assert scope["requirement_frozen"] is True
    assert scope["caps"]["outer_stdout_max_bytes"] == projection["cap_bytes"] == 8192
    assert scope["counter_interval"]["successful_end_event_id"] == "COMPLETE_COMPILE_RESPONSE_FINAL_BYTE"
    assert projection["cap_changed"] is False
    assert profile["controller_writers"] == 1 and profile["potential_write_handles_per_writer"] == 2
    assert profile["request_bytes_added_to_stdout"] == profile["candidate_A_stderr_success_bytes"] == 0
    assert profile["response_frame_overhead_bytes"] == 8
    assert owner["encoding"]["canonical_quoted_json_bytes"] == 19
    assert kernel["typed_result"] == "KERNEL_IDENTITY_CONTRACT_UNRESOLVED"
    assert projection["writer_completeness"] == "WRITER_INVENTORY_COMPLETENESS_UNRESOLVED"
    assert projection["class_size_legal_envelope"] == [1, 32768]
    assert projection["class_size_decimal_width"] == 5
    assert projection["actual_class_size_selected"] is False
    messages = profile["messages"]
    assert [(row["operation"], row["direction"]) for row in messages] == [
        ("MATERIALIZE_EXACT_SCENARIO_SOURCE", "request"),
        ("MATERIALIZE_EXACT_SCENARIO_SOURCE", "response"),
        ("COMPILE_EXACT_SCENARIO", "request"), ("COMPILE_EXACT_SCENARIO", "response")]
    for message in messages:
        response = message["direction"] == "response"
        assert message["inside_effect_interval"] is True and message["inside_stdout_cap"] is response
        assert message["physical_stream"] == ("controller_stdout" if response else "controller_stdin")
        assert message["physical_frame_bytes"] - message["canonical_payload_bytes"] == 4

    responses = [row for row in messages if row["direction"] == "response"]
    response_audit, class_leaves = [], []
    covered_exact_families = {"future_owner", "fixed_digest", "container", "generation", "kernel_namespace", "kernel_cgroup"}
    for historical, projected in zip(responses, projection["responses"]):
        assert historical["operation"] == projected["operation"]
        tree = historical["annotated_symbolic_layout"]
        assignment = dict(historical["width_assignment"])
        assert width(tree, assignment) == historical["canonical_payload_bytes"]
        for row in projected["selected_substitutions"]:
            assignment[row["symbol"]] = row["partial_lower_canonical_json_bytes"]
        subtotal = width(tree, assignment)
        assert subtotal == projected["partial_lower_payload_bytes"]
        layout = dict(leaves(tree))
        residuals = projected["unresolved_residual_leaves"]
        residual_paths = {row["path"] for row in residuals}
        assert len(residual_paths) == len(residuals)
        assert dict(Counter(row["symbol"] for row in residuals)) == projected["unresolved_residual_width_terms"]
        audited, exact = [], []
        for row in residuals:
            leaf, symbol = layout[row["path"]], row["symbol"]
            lower = row["partial_lower_canonical_json_bytes"]
            assert leaf["$unresolved_scalar_width"] == symbol and assignment[symbol] == lower
            expression = "Q_actual[" + symbol + "]-" + str(lower)
            assert row["residual_expression"] == expression
            audited.append(dict(path=row["path"], symbol=symbol, family=leaf["family"],
                lower_width=lower, expression=expression, nonnegative=True,
                basis=residual_basis(leaf, symbol, lower)))
        for path, leaf in layout.items():
            symbol, family = leaf["$unresolved_scalar_width"], leaf["family"]
            if path in residual_paths:
                continue
            if family == "class_size":
                assert leaf["canonical_width_interval"] == [1, 5] and assignment[symbol] == 5
                class_leaves.append(dict(path=path, symbol=symbol, frozen_profile_width=5,
                    legal_width_set=[1, 2, 3, 4, 5], difference_expression="D_class-5",
                    difference_interval=[-4, 0], in_historical_residual=False))
            else:
                assert family in covered_exact_families, (path, family)
                expected = 19 if family == "future_owner" else 66
                assert assignment[symbol] == expected
                exact.append(dict(path=path, symbol=symbol, family=family, exact_canonical_width=expected,
                    basis="Frozen owner encoding, fixed digest width, settled equality projection, or Candidate-A-specific 64-hex identity/generation."))
        class_adjusted = []
        for digits in range(1, 6):
            changed = dict(assignment)
            if "class_size_digits" in changed:
                changed["class_size_digits"] = digits
            class_adjusted.append(width(tree, changed))
        response_audit.append(dict(operation=historical["operation"], retained_profile_subtotal=subtotal,
            residual_count=len(audited), residuals=audited, exact_width_leaves=exact,
            all_existing_residuals_nonnegative=True,
            class_adjusted_subtotals=class_adjusted,
            scalar_variation_coverage="Existing nonnegative residuals plus the explicit class-width correction; retained lower topology only."))
    assert [row["retained_profile_subtotal"] for row in response_audit] == [3567, 5254]
    assert [row["residual_count"] for row in response_audit] == [39, 49]
    assert len(class_leaves) == 2
    assert {row["path"] for row in class_leaves} == {
        "/result/class_metadata/size_bytes", "/result/workspace_state/work_manifest/2/size_bytes"}
    assert {row["symbol"] for row in class_leaves} == {"class_size_digits"}
    rows = []
    for index, digits in enumerate(range(1, 6)):
        semantic = sum(row["class_adjusted_subtotals"][index] for row in response_audit)
        physical, adjustment = semantic + 8, 2 * (digits - 5)
        assert semantic == 8821 + adjustment and physical == 8829 + adjustment
        rows.append(dict(class_decimal_width=digits, class_width_adjustment=adjustment,
            semantic_lower_subtotal=semantic, lower_physical_subtotal=physical,
            proven_excess_lower_bound=physical - 8192, actual_class_size_selected=False,
            attainable_equality_claimed=False))
    assert [row["class_width_adjustment"] for row in rows] == [-8, -6, -4, -2, 0]
    assert [row["lower_physical_subtotal"] for row in rows] == [8821, 8823, 8825, 8827, 8829]
    assert [row["proven_excess_lower_bound"] for row in rows] == [629, 631, 633, 635, 637]
    lower = min(row["lower_physical_subtotal"] for row in rows)
    assert lower == 8821 > 8192 and lower - 8192 == 629
    theorem = dict(quantifier="For every Candidate-A preparation effect encoding satisfying the frozen schema, reviewed Candidate A profile and current frozen evidence semantics.",
        retained_topology_physical_expression="8829+R_M+R_C+2*(D_class-5)",
        residual_constraints={"R_M": ">=0", "R_C": ">=0"}, class_width_set=[1, 2, 3, 4, 5],
        class_width_adjustment_expression="2*(D_class-5)", class_width_adjustment_interval=[-8, 0],
        derivation=["R_M>=0", "R_C>=0", "2*(D_class-5)>=-8", "physical_stdout_bytes>=8829-8=8821", "8821>8192", "physical_stdout_bytes-8192>=629"],
        physical_stdout_lower_bound_bytes=8821, frozen_cumulative_stdout_cap_bytes=8192,
        proven_excess_lower_bound_bytes=629,
        attainable_minimum_established=False, exact_minimum_claimed=False,
        actual_class_size_selected=False, finite_residual_maxima_required=False,
        actual_kernel_values_required=False, witness_required=False)
    flags = dict.fromkeys(("transport_selection", "controller_implementation", "writer_inventory_implementation",
        "kernel_contract_completion", "schema_change", "evidence_change", "cap_change", "owner_encoding_change",
        "kernel_projection_change", "requirement_evolution", "repin", "capability_issuance",
        "runtime_authority", "repository_write_authority"), False)
    effects = dict.fromkeys(("Docker", "network", "owner_import", "capability_issuance", "controller_execution",
        "live_kernel_inspection", "writer_inventory", "java", "javac", "class_size_execution",
        "class_size_observation", "source_materialization", "historical_proof_execution", "child_process_creation"), 0)
    closure = dict(phase_id=PHASE_ID, typed_result="CANDIDATE_A_REJECTED_BUDGET_INCOMPATIBLE",
        candidate="A", candidate_status="REJECTED_BUDGET_INCOMPATIBLE",
        candidate_ever_selected=False, candidate_rejection_recorded=True,
        meaning="The reviewed Candidate A persistent-stdio profile cannot satisfy the frozen 8192-byte cumulative preparation stdout requirement. The rejection follows from a conservative lower bound of at least 8821 bytes; no actual class size, kernel identity encoding or complete writer inventory is required.",
        theorem=theorem, class_width_table=rows,
        rejection_scope=dict(architecture=selection["reviewed_candidate_architecture"],
            controller="Persistent single-thread in-container Python controller", transport="persistent_stdio",
            response_stream="controller_stdout", header_encoding=selection["wire"]["length_encoding"],
            header_bytes_per_response=4, required_complete_responses=[row["operation"] for row in responses],
            request_stream="controller_stdin", request_bytes_added_to_stdout=0,
            successful_controller_stderr_bytes=0, cap_bytes=8192,
            capture_interval=scope["counter_interval"],
            message_evidence_semantics="Current frozen controller schema, owner encoding and settled kernel projection rules, unchanged.",
            class_size_legal_envelope=[1, 32768]),
        writer_lower_profile=dict(controller_writers=1, potential_root_handles_per_response=2,
            description=history["writer_analysis"]["structural_lower_profile"], complete=False,
            monotonicity="Each additional mandatory truthful writer/process/task/handle record contributes nonnegative canonical JSON bytes, plus separators where applicable. No removal, replacement or deduplication is authorized. The full encoding is at least the retained lower-topology encoding.",
            added_record_count_or_values_selected=False),
        historical_closure=dict(phase_id=prior["phase_id"], typed_result=prior["typed_result"],
            reason="The requested universal 8829-byte lower bound and 637-byte minimum excess were too strong because two variable-width class fields were omitted from residuals.",
            historical_stop_correct=True, bytes_changed=False,
            relation="This additive retry closes Candidate A using the corrected conservative theorem; it does not rewrite CLOSE.1."),
        historical_transport_result="TRANSPORT_SELECTION_UNRESOLVED",
        historical_candidate_classification="PREFERRED_BUT_SELECTION_UNRESOLVED",
        transport_status="TRANSPORT_SELECTION_UNRESOLVED", overall_universal_budget_feasibility="UNRESOLVED",
        kernel_status="KERNEL_IDENTITY_CONTRACT_UNRESOLVED", settled_projection_rules_frozen=True,
        writer_completeness="WRITER_INVENTORY_COMPLETENESS_UNRESOLVED",
        replacement_selected=False, remaining_candidates_ranked=False,
        universal_transport_impossibility_claimed=False,
        future_epoch_rule="Reconsideration after explicit evolution of this reviewed architecture/profile, stdout response mapping, framing, current message/evidence schema or 8192 cumulative cap requires a new epoch and additive phase. This rejection remains immutable historical evidence.",
        authority_flags=flags, operational_effects=effects, stop=True)
    write("premise_audit.json", dict(phase_id=PHASE_ID, response_audit=response_audit,
        class_size_occurrences=class_leaves, retained_semantic_subtotal=8821,
        retained_physical_subtotal_before_class_correction=8829, class_width_table=rows,
        existing_residual_leaf_count=88, all_existing_residuals_nonnegative=True,
        every_symbolic_leaf_accounted_for=True, no_concrete_identity_or_class_values_instantiated=True,
        writer_lower_topology_complete=False, additional_truthful_records_cannot_reduce_bound=True))
    write("closure.json", closure)
    write("roadmap_addendum.json", dict(phase_id=PHASE_ID, record_kind="ADDITIVE_CANDIDATE_REJECTION",
        historical_phase="SYNTH.EXEC.PREP.CONTROLLER.TRANSPORT.1", historical_candidate="A",
        historical_classification="PREFERRED_BUT_SELECTION_UNRESOLVED", historical_candidate_ever_selected=False,
        new_evidence=["SYNTH.EXEC.PREP.CONTROLLER.IDENTITY.ENCODING.CONTRACT.1",
            "SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.CONTRACT.1",
            "SYNTH.EXEC.PREP.CONTROLLER.TRANSPORT.CANDIDATE_A.CLOSE.1"],
        prior_closure_result="CANDIDATE_A_CLOSURE_UNRESOLVED",
        candidate_current_status="REJECTED_BUDGET_INCOMPATIBLE", typed_result=closure["typed_result"],
        supersession="Candidate-level closure based on later evidence and corrected conservative arithmetic; historical preference, TRANSPORT.1 and CLOSE.1 outcomes remain byte-identical.",
        phase_completion_history_changed=False, production_registry_changed=False,
        closure_link="closure.json", proof_link="premise_audit.json",
        transport_status="TRANSPORT_SELECTION_UNRESOLVED", budget_feasibility="UNRESOLVED",
        replacement_selected=False, remaining_candidates_ranked=False,
        future_epoch_rule=closure["future_epoch_rule"]))
    print(json.dumps(dict(typed_result=closure["typed_result"], physical_stdout_lower_bound=lower,
        proven_excess_lower_bound=lower-8192, input_artifacts=len(input_records), listed_residuals=88)))


if __name__ == "__main__":
    main()


