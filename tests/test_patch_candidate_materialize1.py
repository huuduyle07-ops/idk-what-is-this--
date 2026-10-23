"""Byte composition tests use synthetic frozen candidates and isolated files."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import core.structural_candidate_materialization as materializer
from core.structural_candidate_materialization import (
    ByteEditEvent, MaterializationError, TIMING_FIELDS, compose_byte_events,
    materialize_structural_candidate, validate_materialized_structural_candidate,
)
from core.structural_patch_author import normalize_structural_author_output
from scripts.replay_patch_author_structural1 import synthetic_author_output
from scripts.replay_patch_candidate_materialize1 import (
    SCENARIOS, _collision, no_materialization_effects, replay, synthetic_candidate_case,
)


@pytest.fixture(scope="module")
def cases():
    return {name: synthetic_candidate_case(name) for name in SCENARIOS}


def materialize(case, candidate=None, **changes):
    scope, fresh, original = case
    return materialize_structural_candidate(original if candidate is None else candidate,
        admitted_scope=scope, **{**fresh, **changes})


def virtual(result, path="bank.java"):
    return next(f for f in result.virtual_files if f.path == path)


def prove_preserved(before, after, segments):
    """Verify every recorded source interval directly against both byte buffers."""
    previous_before = previous_after = 0
    for segment in segments:
        assert 0 <= previous_before <= segment.before_start < segment.before_end <= len(before)
        assert 0 <= previous_after <= segment.after_start < segment.after_end <= len(after)
        assert segment.before_end - segment.before_start == segment.after_end - segment.after_start
        old = before[segment.before_start:segment.before_end]
        assert old == after[segment.after_start:segment.after_end]
        assert sha256(old).hexdigest() == segment.sha256
        previous_before, previous_after = segment.before_end, segment.after_end


def independently_compose(before, receipts):
    """Reference original-coordinate composition driven only by typed receipts."""
    removals = sorted((r.before_start, r.before_end) for r in receipts if r.operation == "remove_declaration")
    inserts = sorted((r.before_start, r.order, r.payload_bytes) for r in receipts
                     if r.operation in {"insert_member", "insert_nested_class"})
    parts = []
    for offset in range(len(before) + 1):
        parts.extend(payload for anchor, _, payload in inserts if anchor == offset)
        if offset < len(before) and not any(start <= offset < end for start, end in removals):
            parts.append(before[offset:offset + 1])
    return b"".join(parts)


@pytest.mark.parametrize("name", SCENARIOS)
def test_layouts_materialize_atomically_as_exact_immutable_virtual_bytes(cases, name):
    case = cases[name]
    scope, fresh, candidate = case
    before = scope.to_json(), candidate.to_json(), fresh["current_source"], fresh["repository_evidence"]
    timings = {}
    result = materialize(case, timings=timings)
    assert result.phase_id == "PATCH.CANDIDATE.MATERIALIZE.1"
    assert result.authority == "virtual_post_state_only"
    assert result.candidate_fingerprint == candidate.fingerprint
    assert result.admission_fingerprint == scope.fingerprint
    assert result.implementation_plan_fingerprint == fresh["plan"].fingerprint
    assert result.repository_id == scope.repository_id
    assert len(result.virtual_files) == (1 if name == "nested" else 2)
    assert isinstance(result.virtual_files, tuple) and isinstance(result.applied_operations, tuple)
    assert len(result.applied_operations) == len(candidate.operations)
    assert {r.operation for r in result.applied_operations} == {o.operation for o in candidate.operations}
    assert set(timings) == set(TIMING_FIELDS) and all(type(v) is float and v >= 0 for v in timings.values())
    for key in ("write_authority", "filesystem_write_authority", "filesystem_file_creation_authority",
                "execution_authorized", "apply_authority", "auto_apply"):
        assert getattr(result, key) is False
    assert result.author_calls == result.model_calls == result.repository_traversals == 0
    for f in result.virtual_files:
        assert f.after_sha256 == sha256(f.after_bytes).hexdigest()
        assert f.after_bytes == f.after_source.encode("utf-8") and f.after_size == len(f.after_bytes)
        assert f.physical_write_authority is False
        assert set(f.operation_ids) == {r.operation_id for r in result.applied_operations if r.path == f.path}
        with pytest.raises(FrozenInstanceError):
            f.after_source = "changed"
        if f.before_state == "file":
            assert f.before_sha256 == sha256(fresh["current_source"]).hexdigest()
            assert f.before_size == len(fresh["current_source"])
            prove_preserved(fresh["current_source"], f.after_bytes, f.preservation_proof)
            receipts = [r for r in result.applied_operations if r.path == f.path]
            assert independently_compose(fresh["current_source"], receipts) == f.after_bytes
        else:
            assert f.before_state == "absent" and f.before_sha256 is None and f.before_size is None
            assert not f.preservation_proof
            original = next(o.source_text for o in candidate.operations if o.physical_target == f.path)
            assert f.after_bytes == original.encode("utf-8")
    with pytest.raises(FrozenInstanceError):
        result.status = "write_authorized"
    with pytest.raises(MaterializationError, match="mutable"):
        replace(result, virtual_files=list(result.virtual_files))
    assert validate_materialized_structural_candidate(result.as_dict(), candidate=candidate,
        admitted_scope=scope, **fresh) == result
    assert json.loads(result.to_json()) == result.as_dict()
    assert before == (scope.to_json(), candidate.to_json(), fresh["current_source"], fresh["repository_evidence"])


@pytest.mark.parametrize("name", ("preserve_base_compatibility", "subclass_specialization", "savings_only_on_subclass"))
def test_remove_plus_insert_uses_one_original_coordinate_system_and_no_cleanup(cases, name):
    scope, fresh, _ = cases[name]
    result = materialize(cases[name])
    after = virtual(result).after_bytes
    assert after.count(b"debitForSavings(double amount)") == 1
    method = next(m for m in fresh["current_context"].methods if m.name == "saving")
    saving_bytes = fresh["current_source"][method.span.start:method.span.end]
    if name == "savings_only_on_subclass":
        assert saving_bytes not in after
        removal = next(r for r in result.applied_operations if r.operation == "remove_declaration")
        allowed = next(o for o in scope.permitted_structural_operations if o.operation == "remove_declaration")
        assert (removal.before_start, removal.before_end) == allowed.declaration_byte_span
        assert removal.payload_bytes == b""
    else:
        assert saving_bytes in after
    for method in fresh["current_context"].methods:
        if name == "savings_only_on_subclass" and method.name == "saving":
            continue
        assert fresh["current_source"][method.span.start:method.span.end] in after
    if name == "subclass_specialization":
        assert b"public void saving(" in virtual(result, "SavingAccount.java").after_bytes


@pytest.mark.parametrize("name", ("lf", "crlf"))
def test_existing_line_endings_only_render_inserted_candidate_text(cases, name):
    _, fresh, candidate = cases[name]
    result = materialize(cases[name])
    f = virtual(result)
    newline = b"\r\n" if name == "crlf" else b"\n"
    assert newline in f.after_bytes
    if name == "crlf":
        assert b"\n" not in f.after_bytes.replace(b"\r\n", b"")
    else:
        assert b"\r" not in f.after_bytes
    generated = next(o.source_text for o in candidate.operations if o.operation == "insert_member")
    assert generated.replace("\n", newline.decode()).encode() in f.after_bytes
    new = virtual(result, "SavingAccount.java")
    assert b"\r" not in new.after_bytes
    prove_preserved(fresh["current_source"], f.after_bytes, f.preservation_proof)


def test_packaged_draft_retains_exact_admitted_package_and_top_level_identity(cases):
    scope, _, candidate = cases["packaged"]
    result = materialize(cases["packaged"])
    assert {f.path for f in result.virtual_files} == {"edu/bank.java", "edu/SavingAccount.java"}
    assert scope.new_file_creation_targets[0].package_name == "edu"
    new = virtual(result, "edu/SavingAccount.java")
    assert new.after_bytes.startswith(b"package edu;\npublic class SavingAccount extends BankAccount {")
    assert new.after_bytes == next(o.source_text.encode() for o in candidate.operations if o.operation == "draft_new_file")


def test_nested_insertions_share_harness_owned_anchor_and_plan_definition_order(cases):
    scope, fresh, candidate = cases["nested"]
    result = materialize(cases["nested"])
    assert tuple(f.path for f in result.virtual_files) == ("bank.java",)
    inserts = [r for r in result.applied_operations if r.operation in {"insert_member", "insert_nested_class"}]
    assert len(inserts) == 2
    allowed = next(o for o in scope.permitted_structural_operations if o.class_body is not None)
    anchor = allowed.class_body.body_span[1] - 1
    assert fresh["current_source"][anchor:anchor + 1] == b"}"
    assert {r.anchor_offset for r in inserts} == {anchor}
    assert len({r.order for r in inserts}) == 2
    plan = fresh["plan"].planner_proposal
    planned_ids = [d.identity for mapping in (*plan.logical_creations, *plan.existing_modifications)
                   for d in mapping.definitions]
    rank = {identity: index for index, identity in enumerate(planned_ids)}
    assert [r.operation for r in sorted(inserts, key=lambda r: r.order)] == [r.operation for r in
        sorted(inserts, key=lambda r: min(rank[i] for i in r.definition_ids))]
    final = virtual(result).after_bytes
    assert final.endswith(fresh["current_source"][anchor:])
    assert b"public static class SavingAccount extends BankAccount" in final
    payload = synthetic_author_output(scope)
    payload["candidate"]["operations"].reverse()
    normalized = normalize_structural_author_output(admitted_scope=scope, author_output=payload, **fresh)
    assert normalized.candidate == candidate
    assert materialize(cases["nested"], candidate=normalized.candidate).fingerprint == result.fingerprint


def test_frozen_author_semantics_are_preserved_without_repair(cases):
    case = cases["preserve_base_compatibility"]
    result = materialize(case)
    new = virtual(result, "SavingAccount.java")
    assert b"System.console().readLine()" in new.after_bytes
    assert new.after_source == next(o.source_text for o in case[2].operations if o.operation == "draft_new_file")
    insert = next(r for r in result.applied_operations if r.operation == "insert_member")
    candidate_text = next(o.source_text for o in case[2].operations if o.operation == "insert_member")
    assert candidate_text.encode() in insert.payload_bytes
    assert insert.canonical_source_sha256 == sha256(candidate_text.encode()).hexdigest()
    assert insert.rendered_sha256 == sha256(insert.payload_bytes).hexdigest()


@pytest.mark.parametrize("newline", ("\n", "\r\n"))
def test_utf8_source_offsets_and_nonascii_candidate_comments_are_preserved(newline):
    from scripts.replay_patch_scope_expand1 import fixture_inputs
    source = "// 한글 계좌\n" + fixture_inputs()["current_source"].decode("utf-8")
    source = source.replace("\n", newline)
    scope, fresh, candidate = synthetic_candidate_case(source=source)
    output = synthetic_author_output(scope)
    operation = next(o for o in output["candidate"]["operations"] if o["operation"] == "insert_member")
    operation["source_text"] = "/* 작성된 주석 */\n" + operation["source_text"]
    result = normalize_structural_author_output(admitted_scope=scope, author_output=output, **fresh)
    assert result.candidate, (result.status, result.reason)
    materialized = materialize((scope, fresh, result.candidate))
    after = virtual(materialized).after_bytes
    assert "// 한글 계좌".encode("utf-8") in after
    assert operation["source_text"].replace("\n", newline).encode("utf-8") in after
    prove_preserved(fresh["current_source"], after, virtual(materialized).preservation_proof)


def test_read_only_support_proofs_preserve_exact_neighboring_declarations(cases):
    _, fresh, _ = cases["preserve_base_compatibility"]
    result = materialize(cases["preserve_base_compatibility"])
    expected_support = {(s.declaration.file, s.declaration.owner, s.declaration.name, s.declaration.kind)
                        for s in cases["preserve_base_compatibility"][0].read_only_supporting_targets}
    # Supporting evidence binds every read-only declaration, including containers.
    support = result.supporting_declarations
    assert {(p.path, p.owner, p.name, p.kind) for p in support} == expected_support
    after = virtual(result).after_bytes
    for proof in support:
        start, end = proof.before_span
        if proof.mode == "exact_declaration":
            original = fresh["current_source"][start:end]
            assert original in after and proof.preserved_sha256 == sha256(original).hexdigest()
        else:
            assert proof.mode == "container_surviving_bytes"
        prove_preserved(fresh["current_source"], after, proof.preserved_segments)


def test_idempotency_and_independent_validator_never_trust_stored_fingerprints(cases):
    scope, fresh, candidate = cases["preserve_base_compatibility"]
    result = materialize(cases["preserve_base_compatibility"])
    assert materialize(cases["preserve_base_compatibility"]).to_json() == result.to_json()
    payload = result.as_dict()
    for key in ("materialization_fingerprint", "candidate_fingerprint", "admission_fingerprint",
                "implementation_plan_fingerprint", "repository_id"):
        altered = deepcopy(payload)
        altered[key] = "forged"
        with pytest.raises(MaterializationError):
            validate_materialized_structural_candidate(altered, candidate=candidate, admitted_scope=scope, **fresh)
    for key in ("after_source", "after_sha256", "after_size", "operation_ids", "before_state"):
        altered = deepcopy(payload)
        target = next(f for f in altered["virtual_files"] if f["before_state"] == "file")
        target[key] = {"after_size": 1, "operation_ids": [], "before_state": "absent"}.get(key, "forged")
        with pytest.raises(MaterializationError):
            validate_materialized_structural_candidate(altered, candidate=candidate, admitted_scope=scope, **fresh)


@pytest.mark.parametrize("authority", ("write_authority", "filesystem_write_authority", "filesystem_file_creation_authority",
    "execution_authorized", "apply_authority", "auto_apply"))
def test_materialization_transport_cannot_escalate_authority(cases, authority):
    scope, fresh, candidate = cases["preserve_base_compatibility"]
    payload = materialize(cases["preserve_base_compatibility"]).as_dict()
    payload[authority] = True
    with pytest.raises(MaterializationError):
        validate_materialized_structural_candidate(payload, candidate=candidate, admitted_scope=scope, **fresh)


@pytest.mark.parametrize("change", ("source", "definition", "operation", "lineage", "status", "authority", "path", "package", "top_level"))
def test_fresh_frozen_candidate_validator_rejects_tampering_before_composition(cases, change):
    payload = cases["preserve_base_compatibility"][2].as_dict()
    insert = next(o for o in payload["operations"] if o["operation"] == "insert_member")
    draft = next(o for o in payload["operations"] if o["operation"] == "draft_new_file")
    if change == "source":
        insert["source_text"] += "\nprivate int invented;"
    elif change == "definition":
        insert["definition_ids"] = ["BankAccount::withdraw::method"]
    elif change == "operation":
        insert["operation"] = "replace_file"
    elif change == "lineage":
        payload["implementation_plan_fingerprint"] = "forged"
    elif change == "status":
        payload["status"] = "approved"
    elif change == "authority":
        payload["apply_authority"] = True
    elif change == "path":
        draft["physical_target"] = "MainApp.java"
    elif change == "package":
        draft["source_text"] = "package rogue;\n" + draft["source_text"]
    else:
        draft["source_text"] = draft["source_text"].replace("extends BankAccount", "extends Other")
    with patch.object(materializer, "_compose", side_effect=AssertionError("tampered candidate reached composition")):
        with pytest.raises(MaterializationError):
            materialize(cases["preserve_base_compatibility"], candidate=payload)


def test_duplicate_new_file_operation_is_rejected_atomically(cases):
    payload = cases["preserve_base_compatibility"][2].as_dict()
    payload["operations"].append(deepcopy(next(o for o in payload["operations"] if o["operation"] == "draft_new_file")))
    with pytest.raises(MaterializationError):
        materialize(cases["preserve_base_compatibility"], candidate=payload)


@pytest.mark.parametrize("change", ("source", "collision"))
def test_stale_source_and_new_path_collision_reject_historical_materialization(cases, change):
    scope, fresh, candidate = cases["preserve_base_compatibility"]
    historical = materialize(cases["preserve_base_compatibility"])
    encoded = historical.to_json()
    changes = {"current_source": fresh["current_source"] + b"\n// changed"} if change == "source" else {
        "repository_evidence": _collision(fresh["repository_evidence"])}
    code = "reacquisition_required" if change == "source" else "materialization_conflict_existing_path"
    with pytest.raises(MaterializationError, match=code):
        materialize(cases["preserve_base_compatibility"], **changes)
    with pytest.raises(MaterializationError, match=code):
        validate_materialized_structural_candidate(historical, candidate=candidate, admitted_scope=scope, **{**fresh, **changes})
    assert historical.to_json() == encoded


def test_event_composition_has_exact_preservation_and_transport_independent_order():
    events = (ByteEditEvent("last", "insert", 5, 5, b"Y", 9),
              ByteEditEvent("removed", "remove", 1, 3, b"", 1),
              ByteEditEvent("second", "insert", 5, 5, b"B", 5),
              ByteEditEvent("first", "insert", 5, 5, b"A", 3))
    before = b"abcdef"
    after, proof = compose_byte_events(before, events)
    assert after == b"adeABYf"
    assert compose_byte_events(before, tuple(reversed(events))) == (after, proof)
    prove_preserved(before, after, proof)
    assert sum(s.before_end - s.before_start for s in proof) == len(before) - 2
    with pytest.raises(FrozenInstanceError):
        events[0].start = 0


@pytest.mark.parametrize("events", (
    (ByteEditEvent("one", "remove", 1, 4, b"", 0), ByteEditEvent("two", "remove", 3, 5, b"", 1)),
    (ByteEditEvent("one", "remove", 1, 5, b"", 0), ByteEditEvent("two", "insert", 2, 2, b"x", 1)),
    (ByteEditEvent("one", "insert", 2, 2, b"a", 0), ByteEditEvent("two", "insert", 2, 2, b"b", 0)),
    (ByteEditEvent("same", "insert", 2, 2, b"a", 0), ByteEditEvent("same", "insert", 3, 3, b"b", 1)),
    (ByteEditEvent("past_end", "remove", 1, 20, b"", 0),),
))
def test_overlapping_ambiguous_or_unbounded_events_fail_closed(events):
    with pytest.raises(MaterializationError, match="materialization_structural_conflict"):
        compose_byte_events(b"abcdef", events)


def test_touching_removals_and_explicit_boundary_insertion_compose_once():
    events = (ByteEditEvent("one", "remove", 1, 3, b"", 0),
              ByteEditEvent("two", "remove", 3, 5, b"", 1),
              ByteEditEvent("at_end", "insert", 5, 5, b"X", 2))
    after, proof = compose_byte_events(b"abcdef", events)
    assert after == b"aXf"
    prove_preserved(b"abcdef", after, proof)


def test_no_events_preserves_every_source_byte():
    before = b"// UTF-8: \xe9\x9f\x93\xea\xb8\x80\r\nclass Empty {}\r\n"
    after, proof = compose_byte_events(before, ())
    assert after == before
    prove_preserved(before, after, proof)
    assert sum(p.before_end - p.before_start for p in proof) == len(before)


def test_structural_inventory_distinguishes_legal_local_class_scopes():
    source = b"""class Existing {
      void unused() {}
      void alpha() { class Local { void same() {} } }
      void beta() { class Local { void same() {} } }
      void gamma() { { class Local {} } { class Local {} } }
    }"""
    records = materializer._inventory(materializer._parse(source).root_node, source)
    local_classes = [key for key, _, _ in records if key[1:3] == ("class_declaration", "Local")]
    local_methods = [key for key, _, _ in records if key[1:3] == ("method_declaration", "same")]
    assert len(local_classes) == len(set(local_classes)) == 4
    assert len(local_methods) == len(set(local_methods)) == 2
    # Original-coordinate removal of an unrelated member changes byte offsets,
    # while the surviving local definitions keep their identity.
    after = source.replace(b"void unused() {}", b"")
    resulting = materializer._inventory(materializer._parse(after).root_node, after)
    assert local_classes == [key for key, _, _ in resulting if key[1:3] == ("class_declaration", "Local")]


def test_structural_inventory_qualifies_nested_classes_by_lexical_owner():
    source = b"""class Outer {
      class Left { class Same { void work() {} } }
      class Right { class Same { void work() {} } }
    }"""
    keys = [key for key, _, _ in materializer._inventory(materializer._parse(source).root_node, source)]
    assert len(keys) == len(set(keys))
    assert {key[0] for key in keys if key[1:3] == ("class_declaration", "Same")} == {"Outer::Left", "Outer::Right"}
    assert {key[0] for key in keys if key[1:3] == ("method_declaration", "work")} == {
        "Outer::Left::Same", "Outer::Right::Same"}


@pytest.mark.parametrize("parameter", ("String... values", "String[] values", "String values[]"))
def test_structural_inventory_treats_varargs_and_array_signatures_as_same_identity(parameter):
    source = ("class Existing { void same(" + parameter + ") {} }").encode("utf-8")
    key = next(key for key, _, _ in materializer._inventory(materializer._parse(source).root_node, source)
               if key[1] == "method_declaration")
    assert key == ("Existing", "method_declaration", "same", ("String[]",))


def test_mixed_existing_line_endings_reject_safe_rendering():
    from scripts.replay_patch_scope_expand1 import fixture_inputs
    source = fixture_inputs()["current_source"].decode().replace("\n", "\r\n", 1)
    case = synthetic_candidate_case(source=source)
    with pytest.raises(MaterializationError, match="materialization_unsupported_line_endings"):
        materialize(case)


@pytest.mark.parametrize("source", (b"\xff", b"class BankAccount {\x00}", "class BankAccount {}"))
def test_unsupported_or_non_byte_source_evidence_never_guesses_encoding(cases, source):
    with pytest.raises(MaterializationError, match="materialization_unsupported_source_encoding"):
        materialize(cases["preserve_base_compatibility"], current_source=source)


@pytest.mark.parametrize("failure", ("malformed", "duplicate", "unplanned"))
def test_post_parse_and_structural_post_check_reject_bad_composition_atomically(cases, failure):
    original = materializer._compose
    member = next(o.source_text.encode() for o in cases["preserve_base_compatibility"][2].operations
                  if o.operation == "insert_member")

    def bad_composition(before, events):
        after, proof, positions = original(before, events)
        if failure == "malformed":
            after = after[:-1]
        elif failure == "duplicate":
            after = after[:-1] + b"\n" + member + b"\n}"
        else:
            after += b"\nclass Unplanned {}"
        return after, proof, positions

    with no_materialization_effects(), patch.object(materializer, "_compose", bad_composition):
        with pytest.raises(MaterializationError, match="materialization_structural_conflict"):
            materialize(cases["preserve_base_compatibility"])


@pytest.mark.parametrize("bound", ("MAX_FILES", "MAX_FILE_BYTES", "MAX_TOTAL_BYTES", "MAX_DIFF_BYTES"))
def test_canonical_files_bytes_and_diff_fail_bounds_without_partial_result(cases, monkeypatch, bound):
    monkeypatch.setattr(materializer, bound, 1)
    with pytest.raises(MaterializationError, match="materialization_bounds_exceeded"):
        materialize(cases["preserve_base_compatibility"])


def test_pure_materialization_and_revalidation_have_zero_effects(cases):
    scope, fresh, candidate = cases["preserve_base_compatibility"]
    with no_materialization_effects():
        result = materialize(cases["preserve_base_compatibility"])
        assert validate_materialized_structural_candidate(result, candidate=candidate, admitted_scope=scope, **fresh) == result


def disk_case(root):
    root.mkdir(parents=True, exist_ok=True)
    case = synthetic_candidate_case(root=root)
    (root / "bank.java").write_bytes(case[1]["current_source"])
    return case


def test_facade_reacquires_only_named_files_and_keeps_new_files_virtual(tmp_path):
    scope, fresh, candidate = disk_case(tmp_path)
    before = (tmp_path / "bank.java").read_bytes()
    calls = []
    original = Path.read_bytes

    def record_read(path):
        calls.append(path.resolve())
        return original(path)

    with no_materialization_effects(allow_exact_reads=True), patch.object(Path, "read_bytes", record_read):
        result = materialize_structural_candidate(candidate, admitted_scope=scope, repository_root=tmp_path, **fresh)
        assert validate_materialized_structural_candidate(result, candidate=candidate, admitted_scope=scope,
            repository_root=tmp_path, **fresh) == result
    assert calls and set(calls) <= {tmp_path / "bank.java", tmp_path / ".gitignore", tmp_path / ".cattusignore"}
    assert (tmp_path / "bank.java").read_bytes() == before
    assert not (tmp_path / "SavingAccount.java").exists()


@pytest.mark.parametrize("change", ("source", "collision"))
def test_facade_ignores_old_caller_evidence_and_rechecks_disk_after_materialization(tmp_path, change):
    scope, fresh, candidate = disk_case(tmp_path)
    historical = materialize_structural_candidate(candidate, admitted_scope=scope, repository_root=tmp_path, **fresh)
    before = historical.to_json()
    if change == "source":
        (tmp_path / "bank.java").write_bytes(fresh["current_source"] + b"\n// changed on disk")
    else:
        (tmp_path / "SavingAccount.java").write_text("occupied", encoding="utf-8")
    expected = "reacquisition_required" if change == "source" else "materialization_conflict_existing_path"
    with no_materialization_effects(allow_exact_reads=True):
        with pytest.raises(MaterializationError, match=expected):
            materialize_structural_candidate(candidate, admitted_scope=scope, repository_root=tmp_path, **fresh)
        with pytest.raises(MaterializationError, match=expected):
            validate_materialized_structural_candidate(historical, candidate=candidate, admitted_scope=scope,
                repository_root=tmp_path, **fresh)
    assert historical.to_json() == before


def test_diff_is_a_deterministic_display_projection_of_the_virtual_set(cases):
    result = materialize(cases["savings_only_on_subclass"])
    assert "bank.java" in result.diff_preview and "SavingAccount.java" in result.diff_preview
    assert "debitForSavings" in result.diff_preview and "SavingAccount" in result.diff_preview
    assert result.diff_preview == materialize(cases["savings_only_on_subclass"]).diff_preview
    assert "patch" not in result.as_dict() or not result.as_dict()["patch"]


def test_replay_reports_only_synthetic_virtual_outputs_and_independent_timings():
    result = replay(repetitions=1)
    assert set(result["scenarios"]) == set(SCENARIOS)
    assert result["author_calls"] == result["model_calls"] == result["repository_traversals"] == 0
    assert result["real_BANK2_approval_consumed"] is result["MainApp_session_touched"] is False
    assert result["source_mutation"] is result["filesystem_file_creation_authority"] is False
    assert result["first_remaining_blocker"] == "STRUCTURAL_CANDIDATE_VALIDATION_NOT_IMPLEMENTED"
    for scenario in result["scenarios"].values():
        assert scenario["deterministic"] and set(scenario["performance"]) == set(TIMING_FIELDS)
    for negative in result["negative_cases"].values():
        assert negative["authoritative_virtual_candidate"] is None
    assert result["facade_performance"]["new_file_created"] is False
    assert result["facade_performance"]["source_bytes_unchanged"]
    assert set(result["facade_performance"]["performance"]) == set(TIMING_FIELDS)


@pytest.mark.parametrize("repetitions", (0, -1, True, 1.5, "2"))
def test_replay_repetition_budget_is_typed(repetitions):
    with pytest.raises(ValueError, match="positive_repetitions_required"):
        replay(repetitions=repetitions)


def test_bookkeeping_reversal_preserves_exact_dirty_entry_receipts():
    from tests._patch_candidate_materialize1_maintenance import before_patch_candidate_materialize1
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/patch_candidate_materialize1_reversal.json").read_text(encoding="utf-8"))
    for record in receipt["reversals"]:
        restored = before_patch_candidate_materialize1(record["path"], (root / record["path"]).read_bytes())
        assert sha256(restored).hexdigest() == record["entry_sha256"]
