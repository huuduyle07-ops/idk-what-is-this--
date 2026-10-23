"""Pure read-only closure audit over frozen JSON; no historical code execution.

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
PHASE_ID = "SYNTH.EXEC.PREP.CONTROLLER.TRANSPORT.CANDIDATE_A.CLOSE.1"
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
    selection_path = source("TRANSPORT_1", "selection.json")
    history_path = source("BUDGET_PROOF_1R", "budget_witness.json")
    projection_path = source("KERNEL_IDENTITY_CONTRACT_1", "budget_projection.json")
    selection, history, projection = map(read, (selection_path, history_path, projection_path))
    owner = read(source("IDENTITY_ENCODING_CONTRACT_1", "contract.json"))
    kernel = read(source("KERNEL_IDENTITY_CONTRACT_1", "contract.json"))
    scope = read(source("BUDGET_SCOPE_REQ_1", "requirement.json"))
    profile = next(row for row in history["profiles"] if row["name"] == projection["source_profile"])
    inputs = set()
    # All normative artifacts, reports, source ledgers and their cited source
    # records are hashed as data. Historical validators/proofs are not imported.
    for folder in PHASES.iterdir():
        if folder == OUT or not folder.is_dir() or not folder.name.startswith("SYNTH_EXEC_PREP_"):
            continue
        for path in folder.iterdir():
            if path.is_file() and (path.name in {"contract.json", "requirement.json", "message_schema.json",
                    "selection.json", "budget_witness.json", "budget_projection.json", "evidence_index.json",
                    "source_audit.json", "finite_width.json", "REPORT.md", "proof.py", "budget_projection.py"}
                    or path.name.endswith("_REPORT.json")):
                inputs.add(path)
    cited = []
    for folder, filename, key in (
        ("TRANSPORT_1", "evidence_index.json", "source_records"),
        ("CONTRACT_1", "evidence_index.json", "sources"),
        ("KERNEL_IDENTITY_CONTRACT_1", "source_audit.json", "source_audit"),
        ("KERNEL_IDENTITY_CONTRACT_1", "budget_projection.json", "source_artifacts")):
        for row in read(source(folder, filename))[key]:
            path = ROOT / row["path"]
            actual = sha256(path.read_bytes()).hexdigest()
            cited.append(dict(path=row["path"], expected_sha256=row["sha256"],
                              actual_sha256=actual, matched=actual == row["sha256"]))
            inputs.add(path)
    assert all(row["matched"] for row in cited)
    owner_projection = read(source("IDENTITY_ENCODING_CONTRACT_1", "budget_projection.json"))
    assert owner_projection["source_ledger_sha256"] == sha256(history_path.read_bytes()).hexdigest()
    manifest = [frozen_record(path) for path in sorted(inputs)]
    assert all(row["sha256"] == baseline[row["path"]]["sha256"] for row in manifest)
    write("input_artifacts.json", dict(phase_id=PHASE_ID, files=manifest,
        all_match_initial_preservation_baseline=True, embedded_hash_checks=cited,
        embedded_hashes_all_match=True, historical_code_executed=False))

    assert selection["typed_result"] == "TRANSPORT_SELECTION_UNRESOLVED"
    assert selection["selected_transport"] is None and selection["selected_architecture"] is None
    assert selection["reviewed_candidate_transport"] == "persistent_stdio"
    candidate = next(row for row in selection["candidates"] if row["id"] == "A")
    assert candidate["classification"] == "PREFERRED_BUT_SELECTION_UNRESOLVED"
    assert selection["wire"]["length_encoding"] == "unsigned 32-bit big-endian binary, exactly four octets"
    assert selection["wire"]["maximum_header_bytes"] == 4
    assert profile["controller_writers"] == 1 and profile["potential_write_handles_per_writer"] == 2
    assert profile["response_frame_overhead_bytes"] == 8
    assert profile["request_bytes_added_to_stdout"] == profile["candidate_A_stderr_success_bytes"] == 0
    assert owner["encoding"]["canonical_quoted_json_bytes"] == 19
    assert kernel["typed_result"] == "KERNEL_IDENTITY_CONTRACT_UNRESOLVED"
    assert scope["requirement_frozen"] is True
    assert scope["caps"]["outer_stdout_max_bytes"] == 8192
    assert scope["counter_interval"]["successful_end_event_id"] == "COMPLETE_COMPILE_RESPONSE_FINAL_BYTE"
    assert "Persistent single-thread PID1" in selection["child_process"]["ownership"]
    assert "cumulatively over whole preparation attempt, INCLUDING wire headers" in selection["wire"]["stream_budgets"]
    assert "controller stderr empty on success" in selection["wire"]["stream_budgets"]
    assert projection["cap_bytes"] == 8192 and projection["cap_changed"] is False
    assert [row["operation"] for row in profile["messages"]] == [
        "MATERIALIZE_EXACT_SCENARIO_SOURCE", "MATERIALIZE_EXACT_SCENARIO_SOURCE",
        "COMPILE_EXACT_SCENARIO", "COMPILE_EXACT_SCENARIO"]
    for message in profile["messages"]:
        assert message["inside_effect_interval"] is True
        response = message["direction"] == "response"
        assert message["inside_stdout_cap"] is response
        assert message["physical_stream"] == ("controller_stdout" if response else "controller_stdin")
        assert message["physical_frame_bytes"] - message["canonical_payload_bytes"] == 4

    response_audit, class_leaves = [], []
    responses = [row for row in profile["messages"] if row["direction"] == "response"]
    assert len(responses) == 2
    for historical, projected in zip(responses, projection["responses"]):
        assert historical["operation"] == projected["operation"]
        assert width(historical["annotated_symbolic_layout"], historical["width_assignment"]) == historical["canonical_payload_bytes"]
        assignment = dict(historical["width_assignment"])
        for row in projected["selected_substitutions"]:
            assignment[row["symbol"]] = row["partial_lower_canonical_json_bytes"]
        measured = width(historical["annotated_symbolic_layout"], assignment)
        assert measured == projected["partial_lower_payload_bytes"]
        layout = dict(leaves(historical["annotated_symbolic_layout"]))
        residuals = projected["unresolved_residual_leaves"]
        assert len({row["path"] for row in residuals}) == len(residuals)
        assert dict(Counter(row["symbol"] for row in residuals)) == projected["unresolved_residual_width_terms"]
        audited = []
        for row in residuals:
            leaf = layout[row["path"]]
            assert leaf["$unresolved_scalar_width"] == row["symbol"]
            lower = row["partial_lower_canonical_json_bytes"]
            assert assignment[row["symbol"]] == lower
            assert row["residual_expression"] == "Q_actual[" + row["symbol"] + "]-" + str(lower)
            audited.append(dict(path=row["path"], symbol=row["symbol"], family=row["family"],
                lower_width=lower, expression=row["residual_expression"], nonnegative=True,
                basis=residual_basis(leaf, row["symbol"], lower)))
        for path, leaf in layout.items():
            if leaf["family"] == "class_size":
                assert path not in {row["path"] for row in residuals}
                assert leaf["canonical_width_interval"] == [1, 5]
                class_leaves.append(dict(path=path, symbol=leaf["$unresolved_scalar_width"],
                    frozen_profile_width=assignment[leaf["$unresolved_scalar_width"]],
                    legal_width_interval=leaf["canonical_width_interval"], in_residual=False,
                    width_difference_interval=[-4, 0]))
        response_audit.append(dict(operation=historical["operation"], retained_profile_bytes=measured,
            residual_count=len(audited), residuals=audited,
            every_listed_residual_nonnegative=True,
            listed_residuals_cover_all_scalar_width_variation_in_retained_profile=not any(
                leaf["family"] == "class_size" for leaf in layout.values())))

    assert [row["retained_profile_bytes"] for row in response_audit] == [3567, 5254]
    assert len(class_leaves) == projection["class_size_occurrences_in_compile"] == 2
    assert projection["class_size_decimal_width"] == 5
    assert projection["class_size_legal_envelope"] == [1, 32768]
    assert projection["actual_class_size_selected"] is False
    assert sum(row["retained_profile_bytes"] for row in response_audit) == 8821
    assert 8821 + 8 == 8829 and 8829 - 8192 == 637
    # Width-only sensitivity from an already-frozen interval; no actual class
    # size/value or kernel observation is selected, and no projection is edited.
    class_width_sensitivity = [dict(class_decimal_width=d,
        omitted_class_width_difference=2 * (d - 5),
        semantic_lower_with_listed_residuals_zero=8821 + 2 * (d - 5),
        physical_lower_with_listed_residuals_zero=8829 + 2 * (d - 5),
        excess=637 + 2 * (d - 5)) for d in range(1, 6)]
    assert min(row["excess"] for row in class_width_sensitivity) == 629
    flags = dict.fromkeys(("transport_selection", "candidate_rejection_published", "controller_implementation",
        "writer_inventory_implementation", "kernel_contract_completion", "schema_change", "cap_change",
        "owner_encoding_change", "kernel_projection_change", "requirement_evolution", "repin",
        "capability_issuance", "runtime_authority", "repository_write_authority"), False)
    effects = dict.fromkeys(("Docker", "network", "owner_import", "capability_issuance", "controller_execution",
        "live_kernel_inspection", "writer_inventory", "java", "javac", "class_size_execution",
        "source_materialization", "proof_execution", "child_process_creation"), 0)
    result = dict(phase_id=PHASE_ID, typed_result="CANDIDATE_A_CLOSURE_UNRESOLVED",
        candidate="A", candidate_status="UNSELECTED", candidate_rejection_published=False,
        exact_requested_proof_premises_all_confirmed=False,
        reason="Frozen 8829 is conditional on a five-digit class-size width. Two class-size fields permit widths 1..5 but are omitted from R_C. The requested unconditional minimum excess 637 cannot be frozen truthfully.",
        semantic_retained_profile_expression="8821+R_M+R_C",
        physical_retained_profile_expression="8829+R_M+R_C",
        retained_profile_condition="class_size_decimal_width=5",
        retained_profile_excess_bytes=637, cap_bytes=8192,
        listed_residuals_nonnegative=True, listed_residuals_count=88,
        missing_actual_class_width_term="2*(D_class-5), D_class in {1,2,3,4,5}",
        missing_actual_class_width_term_interval=[-8, 0],
        class_width_sensitivity=class_width_sensitivity,
        independent_conservative_comparison=dict(physical_lower_bytes=8821, excess_bytes=629,
            provenance="Arithmetic relaxation of the already-frozen class-width interval; no new kernel projection or execution.",
            implication="Candidate A incompatibility has a conservative proof, but this phase does not certify the user's mandatory exact 8829/637 minimum or publish a candidate rejection based on a substituted proof."),
        scope=dict(architecture=selection["reviewed_candidate_architecture"],
            transport=selection["reviewed_candidate_transport"], response_stream="controller_stdout",
            header_bytes_per_response=4, responses_in_effect_interval=2,
            request_bytes_added_to_stdout=0, successful_controller_stderr_bytes=0,
            effect_capture="Cumulative over same attempt, unchanged frozen admission-to-complete-COMPILE interval.",
            semantics="Current frozen message/evidence schema, owner encoding and settled kernel projection rules.",
            writer_profile=history["writer_analysis"]["structural_lower_profile"],
            additional_writer_evidence="Appending mandatory truthful array records adds positive serialized bytes; no replacement, omission, deduplication or schema evolution is assumed.",
            writer_profile_complete=False),
        transport_status="TRANSPORT_SELECTION_UNRESOLVED", overall_budget_feasibility="UNRESOLVED",
        kernel_status="KERNEL_IDENTITY_CONTRACT_UNRESOLVED", settled_projection_rules_frozen=True,
        writer_completeness="WRITER_INVENTORY_COMPLETENESS_UNRESOLVED",
        historical_preferred_candidate_status_preserved=candidate["classification"],
        historical_transport_result_rewritten=False, replacement_selected=False,
        remaining_candidates_ranked=False, universal_transport_impossibility_claimed=False,
        exact_kernel_values_instantiated=False, actual_execution_witness_required=False,
        authority_flags=flags, operational_effects=effects, stop=True)
    write("premise_audit.json", dict(phase_id=PHASE_ID, response_audit=response_audit,
        omitted_variable_width_fields=class_leaves, class_width_sensitivity=class_width_sensitivity,
        all_listed_residuals_nonnegative=True, all_actual_width_variation_in_residuals=False,
        retained_semantic_subtotal=8821, retained_physical_subtotal=8829,
        retained_profile_excess=637, conservative_excess=629,
        no_concrete_identity_or_class_values_instantiated=True))
    write("closure.json", result)
    write("roadmap_addendum.json", dict(phase_id=PHASE_ID, record_kind="ADDITIVE_CANDIDATE_CLOSURE_AUDIT",
        phase_completion_history_changed=False, production_registry_changed=False,
        historical_phase="SYNTH.EXEC.PREP.CONTROLLER.TRANSPORT.1", historical_candidate="A",
        historical_classification=candidate["classification"],
        new_evidence=["SYNTH.EXEC.PREP.CONTROLLER.IDENTITY.ENCODING.CONTRACT.1",
                      "SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.CONTRACT.1"],
        closure="CANDIDATE_A_CLOSURE_UNRESOLVED", candidate_rejection_recorded=False,
        supersession="No supersession activated: exact 637-byte minimum premise fails the source audit.",
        resolution_link="closure.json", audit_link="premise_audit.json",
        future_epoch_rule="Any later candidate rejection must be an additive new closure. Explicit evolution of architecture/profile, stream mapping, framing, semantics or cap requires a new epoch; this audit remains immutable historical evidence.",
        transport_status="TRANSPORT_SELECTION_UNRESOLVED", replacement_selection=False))
    print(json.dumps(dict(typed_result=result["typed_result"], conditional_excess=637,
                          conservative_excess=629, input_artifact_count=len(manifest))))


if __name__ == "__main__":
    main()
