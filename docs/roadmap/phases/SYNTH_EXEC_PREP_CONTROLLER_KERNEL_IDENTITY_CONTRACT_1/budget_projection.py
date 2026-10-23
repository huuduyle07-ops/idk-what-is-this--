"""Pure read-only substitution in frozen JSON; never import or rerun the proof.

Only the final JSON beside this file is written. No kernel or owner observation,
digest preimage construction, process creation, or network operation occurs.
The result is a conditional partial lower subtotal, never an execution witness.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PHASES = HERE.parent
HISTORY = PHASES / "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1R/budget_witness.json"
PROOF_SOURCE = HISTORY.parent / "proof.py"
OWNER_CONTRACT = PHASES / "SYNTH_EXEC_PREP_CONTROLLER_IDENTITY_ENCODING_CONTRACT_1/contract.json"
OWNER_PROJECTION = OWNER_CONTRACT.parent / "budget_projection.json"
SCHEMA = PHASES / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json"
PROFILE = "candidate_A_writer_lower_widths_class_5_digits"
PHASE_ID = "SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.CONTRACT.1"
NAMESPACE_KINDS = ("user", "mnt", "net", "pid", "ipc", "cgroup", "uts")
NAMESPACE_MINIMUM_JSON_WIDTH = {kind: len(kind) + 6 for kind in NAMESPACE_KINDS}
EXACT_FAMILIES = {"future_owner", "fixed_digest", "container", "generation", "class_size"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def leaves(value, path=""):
    if type(value) is dict:
        if "$unresolved_scalar_width" in value:
            yield path, value
        else:
            for key, child in value.items():
                yield from leaves(child, path + "/" + key)
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from leaves(child, path + "/" + str(index))


def structural_width(value, assignment):
    """Evaluate only the retained symbolic JSON tree, without scalar values."""
    if type(value) is dict:
        if "$unresolved_scalar_width" in value:
            return assignment[value["$unresolved_scalar_width"]]
        return 2 + max(0, len(value) - 1) + sum(
            len(json.dumps(key, ensure_ascii=True).encode("utf-8")) + 1
            + structural_width(child, assignment) for key, child in value.items())
    if type(value) is list:
        return 2 + max(0, len(value) - 1) + sum(
            structural_width(child, assignment) for child in value)
    return len(json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8"))


def selected_width(symbol, family, owner_width):
    if family == "future_owner":
        return owner_width, "FROZEN_OWNER_EXACT_WIDTH", True
    if symbol.startswith("namespace."):
        kind = symbol.split(".", 1)[1]
        assert kind in NAMESPACE_MINIMUM_JSON_WIDTH
        return NAMESPACE_MINIMUM_JSON_WIDTH[kind], "RAW_NAMESPACE_GRAMMAR_LOWER_BOUND", False
    if symbol == "process_namespace_identity":
        return 66, "NAMESPACE_AGGREGATE_64_LOWERCASE_HEX_EQUALITY_PROJECTION", True
    if family == "kernel_cgroup":
        return 66, "CGROUP_64_LOWERCASE_HEX_EQUALITY_PROJECTION", True
    if family == "mode":
        return 5, "FULL_STAT_MODE_ADMITTED_REGULAR_FILE_OR_DIRECTORY_LOWER_BOUND", False
    if family == "kernel_start":
        return 3, "RAW_DECIMAL_START_TICKS_STRING_GRAMMAR_LOWER_BOUND", False
    return None


def build():
    history, owner, prior = (read(path) for path in (HISTORY, OWNER_CONTRACT, OWNER_PROJECTION))
    assert prior["source_ledger_sha256"] == sha256(HISTORY.read_bytes()).hexdigest()
    profile = next(row for row in history["profiles"] if row["name"] == PROFILE)
    assert owner["encoding"]["exact_content_bytes"] == 17
    owner_width = owner["encoding"]["canonical_quoted_json_bytes"]
    assert owner_width == 19
    assert profile["class_size_decimal_width"] == 5
    assert profile["controller_writers"] == 1
    assert profile["potential_write_handles_per_writer"] == 2
    assert profile["response_frame_overhead_bytes"] == 8
    assert profile["request_bytes_added_to_stdout"] == 0
    assert profile["candidate_A_UNSELECTED"] is True
    messages = [message for message in profile["messages"] if message["direction"] == "response"]
    rows = []
    for message in messages:
        assignment = dict(message["width_assignment"])
        assert structural_width(message["annotated_symbolic_layout"], assignment) == message["canonical_payload_bytes"]
        selected, residuals = [], []
        for path, leaf in leaves(message["annotated_symbolic_layout"]):
            symbol, family = leaf["$unresolved_scalar_width"], leaf["family"]
            old_width = message["width_assignment"][symbol]
            decision = selected_width(symbol, family, owner_width)
            if decision is not None:
                new_width, basis, exact = decision
                assert new_width >= old_width
                assignment[symbol] = new_width
                selected.append(dict(path=path, symbol=symbol, family=family,
                    historical_canonical_json_bytes=old_width,
                    partial_lower_canonical_json_bytes=new_width,
                    delta_bytes=new_width - old_width, selection_basis=basis,
                    selected_width_is_exact=exact, semantic_value_selected=False))
            else:
                new_width, exact = old_width, family in EXACT_FAMILIES
            if not exact:
                residuals.append(dict(path=path, symbol=symbol, family=family,
                    partial_lower_canonical_json_bytes=new_width,
                    residual_expression="Q_actual[" + symbol + "]-" + str(new_width),
                    width_not_an_execution_observation=True,
                    unresolved_role="Wider truthful observation or outside-phase retained lower-width assumption"))
        # Repeated symbols must use one width consistently; no alias is rewritten.
        payload = structural_width(message["annotated_symbolic_layout"], assignment)
        delta = sum(row["delta_bytes"] for row in selected)
        assert payload == message["canonical_payload_bytes"] + delta
        owner_delta = sum(row["delta_bytes"] for row in selected if row["family"] == "future_owner")
        kernel_delta = delta - owner_delta
        terms = Counter(row["symbol"] for row in residuals)
        lower_widths = {row["symbol"]: row["partial_lower_canonical_json_bytes"] for row in residuals}
        rows.append(dict(operation=message["operation"],
            historical_payload_bytes=message["canonical_payload_bytes"],
            frozen_owner_width_delta_bytes=owner_delta,
            frozen_owner_only_partial_lower_bytes=message["canonical_payload_bytes"] + owner_delta,
            selected_kernel_width_delta_bytes=kernel_delta,
            selected_substitutions=selected, partial_lower_payload_bytes=payload,
            exact_full_projected_size_bytes=None,
            unresolved_residual_leaves=residuals,
            unresolved_residual_width_terms=dict(sorted(terms.items())),
            residual_partial_lower_widths=dict(sorted(lower_widths.items())),
            residual_formula="R=" + "+".join(str(count) + "*(Q_actual[" + symbol + "]-" + str(lower_widths[symbol]) + ")"
                for symbol, count in sorted(terms.items())),
            full_size_expression=str(payload) + "+R_" + ("M" if len(rows) == 0 else "C")))
    assert [row["partial_lower_payload_bytes"] for row in rows] == [3567, 5254]
    assert [row["frozen_owner_only_partial_lower_bytes"] for row in rows] == [3379, 4953]
    assert [row["selected_kernel_width_delta_bytes"] for row in rows] == [188, 301]
    assert [row["frozen_owner_only_partial_lower_bytes"] for row in rows] == [
        response["conditional_payload_bytes"] for response in prior["responses"]]
    payload = sum(row["partial_lower_payload_bytes"] for row in rows)
    framed = payload + profile["response_frame_overhead_bytes"]
    assert (payload, framed) == (8821, 8829)
    inputs = (HISTORY, PROOF_SOURCE, OWNER_CONTRACT, OWNER_PROJECTION, SCHEMA)
    return dict(phase_id=PHASE_ID, artifact_kind="READ_ONLY_FROZEN_LEDGER_PARTIAL_WIDTH_SUBSTITUTION",
        typed_result="CONDITIONAL_PARTIAL_LOWER_SUBTOTAL_EXCEEDS_8192",
        result_kind="CONDITIONAL_PARTIAL_LOWER_BOUND_NOT_ATTAINABLE_WITNESS",
        source_profile=PROFILE,
        source_artifacts=[dict(path=path.relative_to(ROOT).as_posix(),
            sha256=sha256(path.read_bytes()).hexdigest(),
            usage="source bytes hashed only; never imported or executed" if path == PROOF_SOURCE else "read-only JSON data")
            for path in inputs],
        canonical_encoding=history["canonical_encoding"],
        frozen_owner_content_bytes=17, frozen_owner_json_bytes=19,
        namespace_grammar="<exact-lowercase-kind>:[<unsigned-canonical-decimal-inode>]",
        namespace_minimum_json_widths=NAMESPACE_MINIMUM_JSON_WIDTH,
        namespace_minimum_width_meaning="Grammar lower bounds only; no claim that one-digit namespace inodes occur or that a finite semantic maximum is established.",
        namespace_set_minimum_json_bytes=67, namespace_set_historical_json_bytes=21,
        namespace_set_minimum_delta_bytes=46,
        selected_digest_algorithm="SHA256", selected_digest_content_bytes=64, selected_digest_json_bytes=66,
        digest_role="Non-secret identity/equality projections of separately frozen canonical preimages; never authentication, authority or a width-driven replacement. This script constructs and hashes no observation preimage.",
        mode_meaning="Full int(st_mode), including file type and permission/special bits; no S_IMODE alternative.",
        mode_partial_lower_decimal_digits=5,
        mode_upper_semantic_width_claimed=False,
        numeric_serialization="Ordinary canonical decimal JSON integers; no quotes, leading zeros, signs on nonnegative values, alternate bases or coercion. Existing uint/positive_int 63-bit schema envelope is unchanged.",
        admitted_schema_numeric_maximum=9223372036854775807,
        admitted_schema_numeric_maximum_decimal_digits=19,
        admitted_schema_numeric_envelope_is_attainability_proof=False,
        responses=rows,
        partial_lower_materialize_response_bytes=3567,
        partial_lower_compile_response_bytes=5254,
        partial_lower_semantic_total_bytes=payload,
        partial_lower_semantic_margin_bytes=8192 - payload,
        partial_lower_semantic_excess_bytes=payload - 8192,
        conditional_candidate_A_framing_bytes=8,
        conditional_candidate_A_partial_lower_framed_total_bytes=framed,
        conditional_candidate_A_margin_bytes=8192 - framed,
        conditional_candidate_A_excess_bytes=framed - 8192,
        exact_full_projected_materialize_response_bytes=None,
        exact_full_projected_compile_response_bytes=None,
        exact_full_projected_semantic_total_bytes=None,
        exact_full_projected_candidate_A_framed_total_bytes=None,
        exact_full_projection_status="UNRESOLVED: unselected identity encodings, truthful widths, writer completeness and physical transport remain separate.",
        residual_formulas=dict(materialize="3567+R_M", compile="5254+R_C",
            semantic_total="8821+R_M+R_C", conditional_candidate_A_framed_total="8829+R_M+R_C",
            conditional_candidate_A_margin="-637-R_M-R_C",
            meaning="Each R is the path-counted sum of actual canonical scalar width minus the declared partial lower assignment; all unchanged conditional assumptions stay fixed."),
        cap_bytes=8192, cap_changed=False,
        class_size_decimal_width=5, class_size_occurrences_in_compile=2,
        class_size_legal_envelope=[1, 32768], actual_class_size_selected=False,
        unchanged_conditional_assumptions=dict(container_json_bytes=66,
            workspace_generation_json_bytes=66, controller_generation_json_bytes=66,
            same_authenticated_original_bindings=True,
            controller_writers_per_response=1, potential_root_handles_per_writer=2,
            compiler_reaped_before_prepared_snapshot=True,
            closed_transient_handles_assumed_for_lower_shape=True,
            successful_candidate_A_controller_stderr_bytes=0,
            two_four_byte_candidate_A_response_headers=True,
            request_bytes_added_to_stdout=0,
            fixed_process_and_manifest_uid_gid=65534,
            fixed_regular_file_link_count=1, subordinate_mount_count=0),
        writer_topology_changed=False,
        writer_completeness="WRITER_INVENTORY_COMPLETENESS_UNRESOLVED",
        writer_lower_profile=history["writer_analysis"]["structural_lower_profile"],
        candidate_A_selected=False, transport_selected=False,
        physical_transport_feasibility="UNRESOLVED",
        overall_budget_feasibility="UNRESOLVED",
        universal_transport_impossibility_claimed=False,
        conditional_result_limit="Only this retained lower topology and conditional framing arithmetic are assessed. No complete writer inventory or transport-independent feasibility claim is produced.",
        attainable_execution_witness=False, historical_proof_imported=False,
        historical_proof_rerun=False, frozen_artifacts_modified=False,
        authority_flags=dict.fromkeys(("observer_implementation", "controller_implementation",
            "owner_implementation", "identity_generation", "transport_selection", "workspace_issuance",
            "capability_issuance", "source_materialization", "scenario_compilation", "runtime_activation"), False),
        operational_effects=dict.fromkeys(("Docker", "network", "owner_import", "capability_issuance",
            "live_kernel_inspection", "target_runtime_stat", "namespace_inspection", "child_process_creation",
            "controller_execution", "source_materialization", "java", "javac", "proof_execution"), 0))


if __name__ == "__main__":
    result = build()
    (HERE / "budget_projection.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("typed_result",
        "partial_lower_materialize_response_bytes", "partial_lower_compile_response_bytes",
        "partial_lower_semantic_total_bytes", "conditional_candidate_A_partial_lower_framed_total_bytes",
        "conditional_candidate_A_excess_bytes")}, sort_keys=True))
