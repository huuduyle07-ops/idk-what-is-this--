"""Pure grammar, retained-contract and symbolic-width checks; no owner execution.

All ID strings below are static lexical fixtures, never issued identities. The
reservation checks are arithmetic over fixed histories, not an allocator or an
owner model. Historical Python is parsed as AST only, never imported or run.
"""
import ast
from collections import Counter
import copy
from hashlib import sha256
import json
from pathlib import Path
import re
import runpy

import pytest


PHASE = Path(__file__).resolve().parents[1]
ROOT = PHASE.parents[3]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


CONTRACT = read_json(PHASE / "contract.json")
AUDIT = read_json(PHASE / "budget_ledger_audit.json")
OWNER_AUDIT = read_json(PHASE / "existing_owner_audit.json")
BASELINE = read_json(PHASE / "preservation_baseline.json")
HISTORY = read_json(ROOT / AUDIT["historical_ledger"])
PROFILE = next(p for p in HISTORY["profiles"] if p["name"] == AUDIT["historical_reference_profile"])
RESPONSES = [m for m in PROFILE["messages"] if m["direction"] == "response"]
CLASSES = {c["prefix"]: c for c in CONTRACT["identity_classes"]}
FIELDS = {f: c for c in CLASSES.values() for f in c["fields"]}
SCHEMA = read_json(ROOT / CONTRACT["sources"]["S"])
CONTROLLER = read_json(ROOT / CONTRACT["sources"]["C"])
WORKSPACE = read_json(ROOT / CONTRACT["sources"]["W"])
PREPARATION = read_json(ROOT / CONTRACT["sources"]["P"])


def valid_fixture(value, prefix):
    """Evaluate the additive grammar only; this does not authenticate anything."""
    return (type(value) is str
            and re.fullmatch(CLASSES[prefix]["regex"], value) is not None
            and CONTRACT["encoding"]["semantic_range"][0]
            <= int(value[1:], 16) <= CONTRACT["encoding"]["semantic_range"][1])


def symbolic_leaves(value, path=""):
    if type(value) is dict:
        if "$unresolved_scalar_width" in value:
            yield path, value
        else:
            for key, child in value.items():
                yield from symbolic_leaves(child, path + "/" + key)
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from symbolic_leaves(child, path + "/" + str(index))


def structural_width(value, assignment):
    """Arithmetic on a frozen symbolic tree, without constructing scalar values."""
    if type(value) is dict:
        if "$unresolved_scalar_width" in value:
            return assignment[value["$unresolved_scalar_width"]]
        return 2 + max(0, len(value) - 1) + sum(
            len(json.dumps(k, ensure_ascii=True).encode("utf-8")) + 1
            + structural_width(v, assignment) for k, v in value.items())
    if type(value) is list:
        return 2 + max(0, len(value) - 1) + sum(structural_width(v, assignment) for v in value)
    return len(json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


POSITIVE = (
    ("w", "w0000000000000001"), ("c", "c0000000000000002"),
    ("x", "x0000000000000003"), ("a", "a0000000000000004"),
    ("t", "t0000000000000005"), ("r", "r0000000000000006"),
    ("o", "o0000000000000007"), ("d", "d0000000000000008"),
    ("w", "w7fffffffffffffff"), ("o", "o000000000000000f"),
)


@pytest.mark.parametrize("prefix,value", POSITIVE)
def test_positive_grammar_ascii_json_width(prefix, value):
    assert valid_fixture(value, prefix)
    assert len(value.encode("ascii")) == CONTRACT["encoding"]["exact_content_bytes"] == 17
    quoted = json.dumps(value, ensure_ascii=True).encode("ascii")
    assert len(quoted) == CONTRACT["encoding"]["canonical_quoted_json_bytes"] == 19
    assert b"\\" not in quoted
    assert json.loads(quoted) == value
    assert 1 <= len(value.encode("utf-8")) <= SCHEMA["definitions"]["id"]["max_utf8_bytes"]


@pytest.mark.parametrize("value", (
    None, True, 1, b"w0000000000000001", "", "w", "0000000000000001",
    "w000000000000001", "w00000000000000001", "w0000000000000000",
    "w8000000000000000", "wffffffffffffffff", "w000000000000000g",
    "W0000000000000001", "w000000000000000F", "z0000000000000001",
    "w+000000000000001", "w-000000000000001", "w0x00000000000001",
    " w0000000000000001", "w0000000000000001 ", "w0000000000000001\n",
    "w0000000000000001\x00", "w00000000_0000001", "w00000000/0000001",
    "w０００００００００００００００１", "w000000000000000\u0661", "w000000000000000\u0001",
))
def test_negative_grammar_rejects_without_normalization(value):
    assert not valid_fixture(value, "w")


@pytest.mark.parametrize("prefix,value", POSITIVE)
def test_exact_family_prefix_prevents_class_substitution(prefix, value):
    assert [p for p in CLASSES if valid_fixture(value, p)] == [prefix]


def test_zero_is_separate_semantic_predicate_and_range_is_injective():
    assert re.fullmatch(CLASSES["w"]["regex"], "w0000000000000000")
    assert not valid_fixture("w0000000000000000", "w")
    assert CONTRACT["encoding"]["semantic_range"] == [1, (1 << 63) - 1]
    assert CONTRACT["encoding"]["suffix_hex_digits"] == 16
    # Fixed digits encode n uniquely; n+1 never aliases n within the accepted range.
    fixed_numbers = (1, 2, 15, 16, (1 << 32) - 1, (1 << 63) - 2)
    assert all(0 < n < n + 1 <= (1 << 63) - 1 for n in fixed_numbers)
    assert (1 << 63) > CONTRACT["encoding"]["semantic_range"][1]


def test_all_requested_fields_are_classified_and_kernel_fields_are_excluded():
    assert set(FIELDS) == {
        "workspace_capability_id", "controller_identity", "exclusive_owner_relation_id",
        "admission_relation_id", "preparation_attempt_id", "request_id", "operation_id",
        "deadline_identity", "writer.accounted_original_relation_id",
        "process.admitted_operation_id", "writer_handle.admitted_operation_id", "active_operation_id",
    }
    assert len(CLASSES) == 8 and set(CLASSES) == set("wcxatrod")
    assert len({c["class"] for c in CLASSES.values()}) == 8
    assert not (set(FIELDS) & set(CONTRACT["out_of_scope"]))
    for field in ("container_identity", "workspace_generation", "controller_generation",
                  "mount_identity", "namespace_generation", "root_identity", "cgroup identity",
                  "start identity", "process group identity", "descriptor identity"):
        assert field in CONTRACT["out_of_scope"]
    assert SCHEMA["definitions"]["id"] == {
        "type": "str", "min_utf8_bytes": 1, "max_utf8_bytes": 256, "NUL_allowed": False}
    assert CONTRACT["schema_modified"] is CONTRACT["requirement_evolution_required"] is False


def test_collision_reuse_and_atomic_reservation_reasoning_from_fixed_histories():
    g = CONTRACT["generation_semantics"]
    assert g["reuse_forbidden"] is True
    for text in ("linearizable", "No assumption about the GIL", "stays burned"):
        assert text in g["thread_safety"]
    assert "all participating families and owners" in g["reservation"]
    assert "reserved, active, terminal or tombstoned" in g["collision_handling"]
    assert "At reservation" in g["collision_handling"]
    assert "only that issuer's own newly created reservation, once" in g["collision_handling"]
    assert "reject a foreign reservation" in g["collision_handling"]
    reserved, active, terminal, tombstoned = frozenset({2}), frozenset({3}), frozenset({4}), frozenset({5})
    occupied = reserved | active | terminal | tombstoned
    # Failed registration cannot make reservation 2 available, nor terminal 4/5.
    assert all(n in occupied for n in (2, 3, 4, 5))
    assert 6 not in occupied
    # Fixed examples distinguish a linearized reservation history from racing reads.
    assert len({1, 2, 3}) == len((1, 2, 3))
    assert len({1, 1}) != len((1, 1))
    assert "no retry with the same value" in g["collision_handling"]
    assert "Never wrap" in g["wrap"] and "not cleanup" in g["wrap"]
    assert "never remove a tombstone" in g["terminal"].lower()
    assert "fail closed" in g["reload_boundary"]


def test_process_fork_restart_and_pid_reuse_reasoning_without_processes():
    g = CONTRACT["generation_semantics"]
    assert "before validation or issuance" in g["fork_boundary"]
    assert "may not continue an inherited namespace or lock" in g["fork_boundary"]
    assert "independently initialized owner secrets" in g["fork_boundary"]
    assert "PID equality alone never permits continuity" in g["restart_boundary"]
    assert "disjoint new namespace" in g["restart_boundary"]
    # Textual equality and a reused numeric PID are insufficient without incarnation.
    old = ("incarnation-before", 42, "w0000000000000001")
    restarted = ("incarnation-after", 42, "w0000000000000001")
    forked = ("incarnation-before", 43, "w0000000000000001")
    assert old[1:] == restarted[1:] and old != restarted
    assert old[0] == forked[0] and old != forked
    assert "new secrets and empty original-object registry" in g["restart_boundary"]


def test_json_and_copied_values_have_grammar_but_no_original_object_authority():
    report = {"workspace_capability_id": "w0000000000000001"}
    json_copy, ordinary_copy = json.loads(json.dumps(report)), copy.copy(report)
    assert report == json_copy == ordinary_copy
    assert report is not json_copy and report is not ordinary_copy
    assert valid_fixture(json_copy["workspace_capability_id"], "w")
    basis = CONTRACT["authority_basis"]
    assert basis["scalar_is_bearer_credential"] is basis["scalar_is_authentication_proof"] is False
    assert basis["scoped_bearer_ids_found"] == []
    assert "Neither a wire ID nor JSON reconstruction creates a registry entry or original object" in basis["wire_rule"]
    assert "stop unresolved" in basis["trust_boundary_rule"]
    assert "Making the handle longer does not repair" in basis["trust_boundary_rule"]
    conjunction = " ".join(basis["required_conjunction"])
    for predicate in ("wrappers and subclasses", "exact original", "registry", "issuing PID",
                      "HMAC", "stable fingerprint", "one-shot/tombstone"):
        assert predicate in conjunction
    assert WORKSPACE["exact_live_object"]["scalar_projection_sufficient"] is False
    assert {"JSON", "copied dataclass", "wrapper", "subclass"} <= set(WORKSPACE["exact_live_object"]["forbidden_substitutes"])
    assert CONTROLLER["authority_separation"]["scalar_admission_id_is_authority"] is False


def test_replay_attempt_request_operation_and_deadline_invariants_match_history():
    generation = CONTRACT["generation_semantics"]
    assert "callers may echo" in generation["caller_control"]
    assert "cannot select, register, overwrite or alias" in generation["caller_control"]
    assert "no reuse, reopen, refund" in CLASSES["t"]["lifetime"]
    assert "never reset, extended or replaced" in CLASSES["d"]["lifetime"]
    assert "not a timestamp" in CLASSES["d"]["role"]
    assert "same exclusive_owner_relation_id" in CLASSES["x"]["lifetime"]
    assert "copy the exact bound operation_id" in CLASSES["o"]["role"]
    assert "Reject repeated operation/request/admission IDs" in CONTROLLER["serialization"]["duplicate_or_replay"]
    assert "Never rerun a mutation even if previous response lost" in CONTROLLER["serialization"]["duplicate_or_replay"]
    assert "never reset per operation" in CONTROLLER["bounds"]["attempt_budget_scope"]
    semantics = PREPARATION["preparation_authority"]["semantics"]
    assert "No reissue or refund" in semantics["authority_lifetime"]
    assert "no existing attempt tombstone" in " ".join(semantics["authority_issuance_requires"])
    # One attempt/deadline, two separate exchanges: static correlation facts only.
    facts = (("t0000000000000001", "d0000000000000002", "r0000000000000003", "o0000000000000004"),
             ("t0000000000000001", "d0000000000000002", "r0000000000000005", "o0000000000000006"))
    assert facts[0][:2] == facts[1][:2]
    assert facts[0][2] != facts[1][2] and facts[0][3] != facts[1][3]


def test_controller_identity_is_separate_from_source_protocol_and_generation():
    separation = CONTRACT["controller_identity_separation"]
    assert set(separation["forbidden_overloads"]) == {
        "source SHA256", "protocol string", "module name", "PID", "controller_generation",
        "container_identity", "workspace_generation"}
    assert "owner-object reference only" in separation["controller_identity"]
    assert "Separate exact source bytes/hash/size" in separation["stable_implementation_identity"]
    assert "No controller generation encoder is selected here" in separation["incarnation"]
    assert CONTRACT["encoding"]["entropy_bits_required"] == 0
    assert CONTRACT["encoding"]["secret"] is False
    assert "availability policy, not a cryptographic minimum" in CONTRACT["encoding"]["capacity_rationale"]
    assert "Observation challenges and independent HMAC secrets retain" in CONTRACT["generation_semantics"]["random_alternatives"]
    assert SCHEMA["definitions"]["hash"]["type"] == "str"
    assert WORKSPACE["authentication"]["algorithm"] == "HMAC-SHA256"
    assert "fingerprint" in WORKSPACE["authentication"]["identity_hmac_payload"]
    assert CONTROLLER["observations"]["owner_challenge"]["random_bytes"] == 32


def test_all_requested_threats_have_distinct_encoding_and_enforcement_explanations():
    rows = CONTRACT["security_property_matrix"]
    assert {r["threat"] for r in rows} >= {
        "accidental collision", "malicious caller guessing another live ID", "replay of stale ID",
        "cross-process copy", "cross-owner substitution", "same-process forged dataclass with copied scalar IDs",
        "PID reuse", "registry reuse after terminal state", "ID reuse after tombstone",
        "serialization/reconstruction", "JSON copy", "wrapper/subclass"}
    assert all(r["encoding"] and r["enforcement"] for r in rows)
    assert len({r["threat"] for r in rows}) == len(rows)


def test_null_borrower_handoff_and_quiescent_operation_references_are_truthful():
    classifications = {r["field"]: r for r in CONTRACT["classification_only"]}
    assert set(classifications) == {"authorized_borrower_relation_id", "handoff_identity"}
    for row in classifications.values():
        assert row["minimum_path_value"] is None
        assert row["minimum_path_json_bytes"] == len(json.dumps(None)) == 4
        assert row["nonnull_encoding_frozen"] is False
    assert "never a placeholder borrower token" in CONTROLLER["handoff"]["current_admission"]
    operation_refs = CONTRACT["nullable_operation_references"]
    assert set(operation_refs["fields"]) == {"process.admitted_operation_id", "writer_handle.admitted_operation_id", "active_operation_id"}
    assert operation_refs["nonnull_content_bytes"] == 17 and operation_refs["null_json_bytes"] == 4
    for message in RESPONSES:
        p = message["annotated_symbolic_layout"]["result"]["workspace_state"]["process_exclusivity_observation"]
        assert p["authorized_borrower_relation_id"] is p["handoff_identity"] is p["active_operation_id"] is None
        assert p["processes"][0]["admitted_operation_id"] is None
        assert len(p["writers"]) == 1 and len(p["writers"][0]["handles"]) == 2
        assert all(h["admitted_operation_id"] is None for h in p["writers"][0]["handles"])
        assert p["writers"][0]["accounted_original_relation_id"] == p["exclusive_owner_relation_id"]
    for definition, field in (("process", "admitted_operation_id"), ("writer_handle", "admitted_operation_id"),
                              ("process_exclusivity", "active_operation_id"),
                              ("process_exclusivity", "authorized_borrower_relation_id"), ("process_exclusivity", "handoff_identity")):
        record = SCHEMA["definitions"][definition]
        assert record["all_fields_required"] is True
        assert record["fields"][field] == {"type": "nullable", "item": "id"}


@pytest.mark.parametrize("owner", OWNER_AUDIT["owners"], ids=lambda o: o["family"] + "-" + o["variant"])
def test_existing_owner_audit_matches_source_hash_ast_and_original_identity(owner):
    source = (ROOT / owner["source"]).read_bytes()
    assert sha256(source).hexdigest() == owner["sha256"] == BASELINE["files"][owner["source"]]["sha256"]
    tree = ast.parse(source.decode("utf-8-sig"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    tokens = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "token_hex"]
    assert tokens and all(len(n.args) == 1 and isinstance(n.args[0], ast.Constant) and n.args[0].value == 32 for n in tokens)
    assert any(isinstance(n.func, ast.Attribute) and n.func.attr == "compare_digest" for n in calls)
    assert any(isinstance(n.func, ast.Attribute) and n.func.attr == "getpid" for n in calls)
    assert any(isinstance(n, ast.Compare) and any(isinstance(op, ast.IsNot) for op in n.ops) for n in ast.walk(tree))
    assert owner["authentication_reference"] and owner["collision_handling"] and owner["tombstone"]
    assert OWNER_AUDIT["common_existing_encoding"]["exact_ascii_bytes"] == 64
    assert OWNER_AUDIT["common_existing_encoding"]["random_bits_requested"] == 256
    assert OWNER_AUDIT["common_existing_encoding"]["historical_convention_is_required_for_future_handles"] is False


def test_historical_source_and_contract_preservation_hashes():
    paths = set(CONTRACT["sources"].values()) | {AUDIT["historical_source"]}
    for relative in paths:
        entry = BASELINE["files"][relative]
        raw = (ROOT / relative).read_bytes()
        assert len(raw) == entry["bytes"] and sha256(raw).hexdigest() == entry["sha256"]
    reflection_request = OWNER_AUDIT["supporting_reflection_request_convention"]
    assert sha256((ROOT / reflection_request["source"]).read_bytes()).hexdigest() == reflection_request["sha256"]


def test_frozen_symbolic_leaf_paths_and_counts_independently_match_audit():
    counts = []
    for message in RESPONSES:
        response_index = 0 if message["operation"] == "MATERIALIZE_EXACT_SCENARIO_SOURCE" else 1
        pairs = [(path, leaf) for path, leaf in symbolic_leaves(message["annotated_symbolic_layout"]) if leaf["family"] == "future_owner"]
        counts.append(len(pairs))
        expected = {}
        for row in AUDIT["response_identity_ledger"]:
            paths = row.get("paths_in_each_response", row.get("paths_in_compile_response", []) if response_index else [])
            assert len(paths) == row[("materialize_occurrences", "compile_occurrences")[response_index]]
            for path in paths:
                expected[path] = row.get("symbolic_identity_alias", row["identity_family"])
        assert {path: leaf["$unresolved_scalar_width"].split(".")[0] for path, leaf in pairs} == expected
        assert all(message["width_assignment"][leaf["$unresolved_scalar_width"]] == 3 for _, leaf in pairs)
        assert "admission_relation_id" not in {leaf["$unresolved_scalar_width"] for _, leaf in pairs}
    assert counts == [8, 9] and sum(counts) == AUDIT["counts"]["total_nonnull_owner_id_occurrences"] == 17
    totals = Counter(r["identity_family"] for r in AUDIT["response_identity_ledger"])
    assert len(totals) == 9 and set(totals) == {"workspace_capability_id", "controller_identity", "exclusive_owner_relation_id",
        "writer.accounted_original_relation_id", "admission_relation_id", "preparation_attempt_id", "request_id", "operation_id", "deadline_identity"}


@pytest.mark.parametrize("content_width,expected_total", ((1, 8068), (17, 8340), (32, 8595), (64, 9139)))
def test_independent_symbolic_arithmetic_reproduces_only_owner_width_substitution(content_width, expected_total):
    widths = []
    for message in RESPONSES:
        original = message["width_assignment"]
        assert structural_width(message["annotated_symbolic_layout"], original) == message["canonical_payload_bytes"]
        assignment = dict(original)
        owner_symbols = {leaf["$unresolved_scalar_width"] for _, leaf in symbolic_leaves(message["annotated_symbolic_layout"]) if leaf["family"] == "future_owner"}
        assignment.update({symbol: content_width + 2 for symbol in owner_symbols})
        assert all(assignment[symbol] == old for symbol, old in original.items() if symbol not in owner_symbols)
        widths.append(structural_width(message["annotated_symbolic_layout"], assignment))
    assert sum(widths) + PROFILE["response_frame_overhead_bytes"] == expected_total
    assert expected_total == 8068 + 17 * (content_width - 1)
    if content_width == 17:
        assert widths == [3379, 4953]
        accepted = AUDIT["accepted_width_substitution"]
        assert accepted["conditional_materialize_response_bytes"] == widths[0]
        assert accepted["conditional_compile_response_bytes"] == widths[1]
        assert accepted["conditional_candidate_A_framed_total_bytes"] == expected_total
        assert accepted["remaining_margin_bytes"] == 8192 - expected_total == -148
        assert accepted["excess_bytes"] == 148


def test_new_projection_build_matches_independent_arithmetic_and_keeps_limits():
    # The only executed phase helper is NEW, data-only width arithmetic.
    projection = runpy.run_path(str(PHASE / "budget_projection.py"))["build"]()
    assert [r["owner_occurrences"] for r in projection["responses"]] == [8, 9]
    assert [r["conditional_payload_bytes"] for r in projection["responses"]] == [3379, 4953]
    assert projection["conditional_candidate_A_framed_total_bytes"] == 8340
    assert projection["conditional_candidate_A_framing_bytes"] == 8
    assert projection["excess_bytes"] == 148 and projection["remaining_margin_bytes"] == -148
    assert projection["typed_result"] == "OWNER_ENCODING_ALONE_EXCEEDS_8192_FOR_CANDIDATE_A"
    assert projection["overall_budget_feasibility"] == "UNRESOLVED"
    assert projection["candidate_A_selected"] is projection["historical_proof_rerun"] is projection["exact_execution_witness"] is False
    assert projection["request_bytes_added_to_stdout"] == 0
    assert projection["source_ledger_sha256"] == BASELINE["files"][AUDIT["historical_ledger"]]["sha256"]
    assert all(flag is False for flag in projection["authority_flags"].values())
    assert all(type(count) is int and count == 0 for count in projection["operational_effects"].values())


def test_class_width_and_alias_sensitivities_do_not_add_requests_or_nulls():
    totals = {r["identity_family"]: r["total_occurrences"] for r in AUDIT["response_identity_ledger"]}
    assert totals["workspace_capability_id"] == 4
    assert totals["exclusive_owner_relation_id"] + totals["writer.accounted_original_relation_id"] == 4
    assert totals["request_id"] == totals["operation_id"] == 2
    assert totals["admission_relation_id"] == 0 and totals["deadline_identity"] == 1
    assert sum(totals.values()) == 17
    assert AUDIT["counts"]["truthful_null_identity_occurrences_both_responses"] == 12
    assert all(row["budget_delta_bytes"] == 0 for row in AUDIT["nullable_identity_fields"])
    assert AUDIT["accepted_width_substitution"]["minimum_class_width_conditional_framed_total_bytes"] == 8340 - 2 * (5 - 1) == 8332
    assert CONTRACT["typed_result"] == "SYNTH_EXEC_PREP_CONTROLLER_IDENTITY_ENCODING_CONTRACT_1_COMPLETE"
    assert CONTRACT["cap_bytes"] == AUDIT["budget_cap_bytes"] == 8192
    assert CONTRACT["candidate_A_selected"] is False and CONTRACT["overall_budget_feasibility"] == "UNRESOLVED"
    assert all(flag is False for flag in CONTRACT["authority_flags"].values())
    assert all(type(count) is int and count == 0 for count in CONTRACT["operational_effects"].values())
