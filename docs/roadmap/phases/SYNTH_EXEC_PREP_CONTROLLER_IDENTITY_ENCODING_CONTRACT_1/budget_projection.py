"""Substitute owner widths in frozen JSON data; never execute the old proof."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HISTORY = HERE.parent / "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1R/budget_witness.json"
PROFILE = "candidate_A_writer_lower_widths_class_5_digits"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def leaves(value, path=""):
    if type(value) is dict:
        if "$unresolved_scalar_width" in value:
            yield path, value
        else:
            for key, item in value.items():
                yield from leaves(item, path + "/" + key)
    elif type(value) is list:
        for index, item in enumerate(value):
            yield from leaves(item, path + "/" + str(index))


def build():
    contract, audit = (read(HERE / name) for name in ("contract.json", "budget_ledger_audit.json"))
    history = read(HISTORY)
    profile = next(row for row in history["profiles"] if row["name"] == PROFILE)
    width = contract["encoding"]["exact_content_bytes"]
    family_widths = {field: width for row in contract["identity_classes"] for field in row["fields"]}
    rows = []
    for message in profile["messages"]:
        if message["direction"] != "response":
            continue
        projected = message["canonical_payload_bytes"]
        replacements = []
        for path, leaf in leaves(message["annotated_symbolic_layout"]):
            if leaf["family"] != "future_owner":
                continue
            symbol = leaf["$unresolved_scalar_width"]
            family = symbol.split(".")[0] if symbol.startswith(("request_id.", "operation_id.")) else symbol
            new_content_width = family_widths[family]
            old_quoted_width = message["width_assignment"][symbol]
            assert old_quoted_width == 3
            delta = new_content_width + 2 - old_quoted_width
            projected += delta
            replacements.append(dict(path=path, symbol=symbol, family=family,
                old_content_bytes=old_quoted_width - 2, new_content_bytes=new_content_width,
                delta_bytes=delta))
        rows.append(dict(operation=message["operation"], baseline_payload_bytes=message["canonical_payload_bytes"],
            owner_occurrences=len(replacements), substitutions=replacements,
            delta_bytes=sum(row["delta_bytes"] for row in replacements),
            conditional_payload_bytes=projected))
    assert len(rows) == 2
    assert [row["owner_occurrences"] for row in rows] == [8, 9]
    payload = sum(row["conditional_payload_bytes"] for row in rows)
    framing = profile["response_frame_overhead_bytes"]
    assert framing == 8
    total = payload + framing
    expected = audit["accepted_width_substitution"]
    assert [row["conditional_payload_bytes"] for row in rows] == [
        expected["conditional_materialize_response_bytes"], expected["conditional_compile_response_bytes"]]
    assert total == expected["conditional_candidate_A_framed_total_bytes"]
    families = audit["response_identity_ledger"] + audit["nullable_identity_fields"]
    return dict(phase_id=contract["phase_id"], result_kind="CONDITIONAL_OWNER_WIDTH_CONSEQUENCE_ONLY",
        typed_result="OWNER_ENCODING_ALONE_EXCEEDS_8192_FOR_CANDIDATE_A" if total > 8192
            else "OWNER_ENCODING_COMPATIBLE_WITH_8192_CONDITIONALLY",
        source_ledger=HISTORY.relative_to(ROOT).as_posix(), source_ledger_sha256=sha256(HISTORY.read_bytes()).hexdigest(),
        source_profile=PROFILE, historical_proof_rerun=False, candidate_A_selected=False,
        kernel_widths="Previous unresolved lower placeholders unchanged; no new observation or serializer.",
        other_widths="All non-owner terms, writer topology, maximum class decimal width and Candidate-A-only generation/container/framing assumptions unchanged.",
        exact_execution_witness=False, overall_budget_feasibility="UNRESOLVED",
        family_ledger=families, responses=rows, conditional_response_payload_bytes=payload,
        conditional_candidate_A_framing_bytes=framing, conditional_candidate_A_framed_total_bytes=total,
        cap_bytes=8192, remaining_margin_bytes=8192 - total, excess_bytes=max(0, total - 8192),
        request_bytes_added_to_stdout=0, authority_flags=contract["authority_flags"],
        operational_effects=contract["operational_effects"])


if __name__ == "__main__":
    result = build()
    (HERE / "budget_projection.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("typed_result", "conditional_candidate_A_framed_total_bytes", "excess_bytes")}))
