"""Adversarial scope, provenance and serializer regressions for DATA-02."""
from dataclasses import replace
from pathlib import Path
import ast

import pytest

from core.execution_outcome_telemetry import (
    AUTHORITY_SOURCE_MANUAL_APPLY, ExecutionReceipt, FinalStateObservation,
    authorized_execution, final_state_observation, observe_named_paths,
    plan_execution_receipt, single_file_execution_receipt,
)
from core.rollback_outcome import (
    RollbackOutcomeError, rollback_completed_verified, rollback_incomplete,
    rollback_not_attempted, rollback_not_required, rollback_outcome_from_mapping,
    rollback_unverifiable,
)
from core.validation_side_effects import with_atomicity_metadata


def telemetry(outcome, changed=(), *, complete=True):
    return authorized_execution(
        authority_source=AUTHORITY_SOURCE_MANUAL_APPLY,
        receipt=ExecutionReceipt(write_receipted=True, rollback_outcome=outcome),
        observation=FinalStateObservation(
            scope="plan_named_paths" if complete else "unavailable",
            changed_paths=changed, complete=complete,
        ),
    )


@pytest.mark.parametrize("changed", [(), ("other.py",)])
def test_narrow_digest_cannot_clear_unresolved_directory(changed):
    outcome = rollback_incomplete([], ["newdir"]).with_recovery_material(["artifact"])
    result = telemetry(outcome, changed)
    assert not result.rollback_performed
    assert result.final_repository_changed
    assert result.rollback_outcome.remaining_created_directories == ("newdir",)
    assert result.rollback_outcome.recovery_artifact_ids == ("artifact",)
    assert "newdir" in result.summary()


def test_byte_digest_cannot_upgrade_a_mode_only_plan_failure(tmp_path):
    target = tmp_path / "mode.py"
    target.write_bytes(b"same bytes")
    before = observe_named_paths(tmp_path, ["mode.py"])
    after = observe_named_paths(tmp_path, ["mode.py"])
    result = authorized_execution(
        authority_source=AUTHORITY_SOURCE_MANUAL_APPLY,
        receipt=plan_execution_receipt({
            "mutation_attempted": True, "recovery_attempted": True,
            "recovery_complete": False, "remaining_changed_paths": ["mode.py"],
            "remaining_created_directories": [],
        }),
        observation=final_state_observation(before, after),
    )
    assert not result.rollback_performed
    assert result.rollback_outcome.remaining_changed_paths == ("mode.py",)


@pytest.mark.parametrize("changed", [(), ("other.py",)])
def test_narrow_digest_preserves_unverifiable_earlier_target(changed):
    result = telemetry(rollback_unverifiable(["unreadable.py"]), changed)
    assert result.rollback_outcome.status == "unverifiable"
    assert not result.rollback_performed
    assert "unreadable.py" in result.rollback_outcome.remaining_changed_paths


def test_successful_noop_uses_executor_verified_state_when_observer_unavailable():
    receipt = single_file_execution_receipt([
        {"phase": "validated", **rollback_not_required().as_payload_fields()}
    ], success=True, validation_requested=True)
    result = authorized_execution(
        authority_source=AUTHORITY_SOURCE_MANUAL_APPLY, receipt=receipt,
        observation=FinalStateObservation(scope="unavailable"),
    )
    assert not result.final_repository_changed
    assert not result.patch_applied
    assert result.rollback_outcome.final_state_verified


@pytest.mark.parametrize("success", [False, True])
@pytest.mark.parametrize("same_target", [False, True])
def test_loop_cannot_erase_prior_unresolved_baseline(success, same_target):
    first = rollback_incomplete(["a.py"]).with_recovery_material(["saved-a"])
    last = rollback_not_required(final_repository_changed=True) if success else rollback_completed_verified()
    receipt = single_file_execution_receipt([
        {"phase": "validation_failed", "target_file": "a.py", **first.as_payload_fields()},
        {"phase": "validated" if success else "validation_failed",
         "target_file": "a.py" if same_target else "b.py", **last.as_payload_fields()},
    ], success=success, validation_requested=True)
    result = authorized_execution(
        authority_source=AUTHORITY_SOURCE_MANUAL_APPLY, receipt=receipt,
        observation=FinalStateObservation(scope="unavailable"),
    )
    assert not result.rollback_performed
    assert not result.patch_applied
    assert result.rollback_outcome.remaining_changed_paths == ("a.py",)
    assert result.rollback_outcome.recovery_artifact_ids == ("saved-a",)


def test_self_correct_loop_stops_before_overwriting_failed_recovery(tmp_path, monkeypatch):
    import core.self_correct_loop as loop
    from core.executor import ExecutionResult
    calls = []
    result = ExecutionResult(
        success=False, phase="validation_failed", message="Rollback incomplete",
        rollback_outcome=rollback_incomplete(["a.py"]),
    )
    monkeypatch.setattr(loop.Executor, "run", lambda *args, **kwargs: calls.append(1) or result)
    attempted_repair = []
    actual = loop.run_self_correct_loop(
        str(tmp_path), {"file": "a.py"}, "python", max_attempts=2,
        re_patch_fn=lambda *args: attempted_repair.append(1) or {"file": "a.py"},
    )
    assert actual["stop_reason"] == "rollback_requires_manual_recovery"
    assert calls == [1] and attempted_repair == []


def test_invalid_typed_evidence_cannot_fall_back_to_legacy_transaction_success():
    invalid = rollback_not_attempted(["a.py"]).as_dict()
    invalid["final_repository_changed"] = False
    result = with_atomicity_metadata({
        "rollback_outcome": invalid, "rollback_performed": True,
        "mutation_attempted": True, "recovery_attempted": True,
        "recovery_complete": True,
    })
    assert result["rollback_status"] == "unverifiable"
    assert not result["rollback_performed"]
    assert result["final_repository_changed"]


@pytest.mark.parametrize("field,value", [
    ("remaining_changed_paths", "unrestored.py"),
    ("remaining_created_directories", None), ("attempted", 1),
    ("final_repository_changed", 0),
])
def test_malformed_serialized_success_cannot_be_normalized_into_proof(field, value):
    raw = rollback_completed_verified().as_dict()
    raw[field] = value
    assert rollback_outcome_from_mapping({"rollback_outcome": raw}).status == "unverifiable"


def test_missing_remaining_paths_cannot_be_defaulted_into_verified_success():
    raw = rollback_completed_verified().as_dict()
    del raw["remaining_changed_paths"]
    assert not rollback_outcome_from_mapping({"rollback_outcome": raw}).performed


@pytest.mark.parametrize("change", [
    {"remaining_changed_paths": "unrestored.py"},
    {"remaining_created_directories": None},
    {"mutation_attempted": 1}, {"recovery_attempted": 1},
    {"mutation_attempted": False}, {"recovery_attempted": False},
])
def test_malformed_transaction_facts_cannot_be_normalized_into_proof(change):
    facts = {
        "mutation_attempted": True, "recovery_attempted": True,
        "recovery_complete": True, "remaining_changed_paths": [],
        "remaining_created_directories": [],
    }
    facts.update(change)
    assert rollback_outcome_from_mapping(facts).status == "unverifiable"


def test_missing_transaction_remaining_sets_cannot_default_into_success():
    assert not rollback_outcome_from_mapping({
        "mutation_attempted": True, "recovery_attempted": True,
        "recovery_complete": True,
    }).performed


@pytest.mark.parametrize("change", [
    {"final_repository_changed": False}, {"failure_code": ""},
    {"failure_reason": ""}, {"attempted": 1},
])
def test_contract_rejects_contradictory_failed_facts(change):
    with pytest.raises(RollbackOutcomeError):
        replace(rollback_incomplete(["a.py"]), **change)


def constant_success_writes(source):
    """Cover literal dict, keyword, assignment and setattr writer shapes."""
    tree = ast.parse(source)
    bad = []
    def key(node):
        return isinstance(node, ast.Constant) and node.value == "rollback_performed"
    def truth(node):
        return isinstance(node, ast.Constant) and node.value is True
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            if any(key(k) and truth(v) for k, v in zip(node.keys, node.values)):
                bad.append(node.lineno)
        elif isinstance(node, ast.keyword) and node.arg == "rollback_performed" and truth(node.value):
            bad.append(node.lineno)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and truth(node.value):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (isinstance(target, ast.Subscript) and key(target.slice)
                    or isinstance(target, ast.Attribute) and target.attr == "rollback_performed"
                    or isinstance(target, ast.Name) and target.id == "rollback_performed"):
                    bad.append(node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
            if len(node.args) == 3 and key(node.args[1]) and truth(node.args[2]):
                bad.append(node.lineno)
    return bad


@pytest.mark.parametrize("source", [
    "return_value = {'rollback_performed': True}",
    "result['rollback_performed'] = True", "result.rollback_performed = True",
    "result.update(rollback_performed=True)", "rollback_performed: bool = True",
    "setattr(result, 'rollback_performed', True)",
])
def test_static_guard_detects_original_bug_and_other_literal_success_writes(source):
    assert constant_success_writes(source)


def test_bounded_current_producers_cannot_write_independent_success():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "core/executor.py", "patching/patch_plan_executor.py",
        "core/validation_side_effects.py", "core/execution_outcome_telemetry.py",
        "core/run_lifecycle.py", "core/pipeline.py", "web/routes/patch_routes.py",
    ):
        assert not constant_success_writes((root / relative).read_text(encoding="utf-8")), relative


# ── Audit follow-up: precedence, absent evidence, wording, sibling fields ─────

@pytest.mark.parametrize("measured", [
    {"recovery_complete": False},
    {"remaining_changed_paths": ["a.py"]},
    {"remaining_created_directories": ["pkg"]},
    {"remaining_changed_paths": "a.py"},
])
def test_typed_success_cannot_outrank_measured_unresolved_state_beside_it(measured):
    receipt = {**rollback_completed_verified().as_payload_fields(), **measured}
    loaded = rollback_outcome_from_mapping(receipt)
    assert loaded.status == "unverifiable"
    assert not loaded.performed
    assert loaded.failure_code == "conflicting_rollback_evidence"
    assert loaded.final_repository_changed
    decorated = with_atomicity_metadata(receipt)
    assert decorated["rollback_status"] == "unverifiable"
    assert decorated["rollback_performed"] is False


def test_consistent_typed_success_beside_complete_transaction_facts_still_loads():
    receipt = {
        "mutation_attempted": True, "recovery_attempted": True, "recovery_complete": True,
        **rollback_completed_verified().as_payload_fields(),
    }
    assert rollback_outcome_from_mapping(receipt).performed
    assert with_atomicity_metadata(receipt)["rollback_performed"] is True


@pytest.mark.parametrize("absent", [None, [], "rollback_performed=true", 1])
def test_absent_receipt_is_not_a_verified_final_state(absent):
    loaded = rollback_outcome_from_mapping(absent)
    assert loaded.status == "not_required"
    assert not loaded.performed and not loaded.verified
    assert loaded.final_state_verified is False


@pytest.mark.parametrize("outcome,expected,forbidden", [
    (rollback_incomplete(["a.py"]).with_recovery_material(["saved-a"]),
     "Emergency recovery material is available.", "partially"),
    (rollback_incomplete(["a.py", "b.py"]).with_recovery_material(
        ["saved-a"], error="b.py:OSError"),
     "only partially available", "material is available"),
    (rollback_incomplete(["a.py"]).with_recovery_material(
        [], error="recovery_store_unavailable:OSError"),
     "could not be fully persisted", "material is available"),
    (rollback_unverifiable(["a.py"]), "material is not recorded", "material is available"),
    (rollback_not_attempted(["a.py"]), "Rollback was not attempted", "failed or is incomplete"),
])
def test_every_current_surface_words_one_outcome_the_same_way(outcome, expected, forbidden):
    from core.executor import _rollback_message
    from web.routes.patch_routes import _rollback_response_message

    messages = [
        _rollback_message("Validation failed (assertion_error).", outcome),
        telemetry(outcome, ("a.py",)).summary(),
        _rollback_response_message("Validation failed.", outcome.as_payload_fields(), "patch"),
    ]
    for message in messages:
        assert expected in message, message
        assert forbidden not in message, message
        assert "a.py" in message, message
        assert "reverted successfully" not in message and "rolled back" not in message


def test_verified_or_unneeded_rollback_has_no_failure_notice():
    from core.rollback_outcome import rollback_failure_notice, recovery_material_notice

    for outcome in (rollback_completed_verified(), rollback_not_required()):
        assert rollback_failure_notice(outcome) == ""
        assert recovery_material_notice(outcome) == ""


_LITERAL_SUCCESS = {
    "rollback_performed": True, "rollback_completed": True,
    "rollback_verified": True, "rollback_status": "completed_verified",
}


def literal_rollback_success_writes(source):
    """Literal success claims for every rollback-success field and writer shape."""
    def success(name, value):
        expected = _LITERAL_SUCCESS.get(name, None)
        return (
            name in _LITERAL_SUCCESS and isinstance(value, ast.Constant)
            and type(value.value) is type(expected) and value.value == expected
        )

    bad = []
    for node in ast.walk(ast.parse(source)):
        pairs = []
        if isinstance(node, ast.Dict):
            pairs = [(k.value, v) for k, v in zip(node.keys, node.values)
                     if isinstance(k, ast.Constant)]
        elif isinstance(node, ast.keyword):
            pairs = [(node.arg, node.value)]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
                    pairs.append((target.slice.value, node.value))
                elif isinstance(target, ast.Attribute):
                    pairs.append((target.attr, node.value))
                elif isinstance(target, ast.Name):
                    pairs.append((target.id, node.value))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "setattr" and len(node.args) == 3
              and isinstance(node.args[1], ast.Constant)):
            pairs = [(node.args[1].value, node.args[2])]
        if any(success(name, value) for name, value in pairs):
            bad.append(node.lineno)
    return bad


@pytest.mark.parametrize("source", [
    "x = {'rollback_verified': True}", "x['rollback_completed'] = True",
    "result.update(rollback_verified=True)", "x = {'rollback_status': 'completed_verified'}",
    "result['rollback_status'] = 'completed_verified'",
    "setattr(result, 'rollback_completed', True)", "rollback_performed: bool = True",
])
def test_sibling_success_guard_detects_literal_claims(source):
    assert literal_rollback_success_writes(source)


@pytest.mark.parametrize("source", [
    "x = {'rollback_verified': outcome.verified}", "x = {'rollback_status': outcome.status}",
    "x = {'rollback_performed': False}", "x = {'rollback_completed': 1}",
    "x = {'recovery_complete': True}",
])
def test_sibling_success_guard_ignores_derived_or_negative_writes(source):
    assert not literal_rollback_success_writes(source)


def test_current_producers_and_translators_write_no_literal_rollback_success():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "core/executor.py", "patching/patch_plan_executor.py",
        "core/validation_side_effects.py", "core/execution_outcome_telemetry.py",
        "core/run_lifecycle.py", "core/pipeline.py", "web/routes/patch_routes.py",
        "web/session_store.py", "core/self_correct_loop.py", "core/sleeping_consultant.py",
        "core/lesson_auto_candidates.py", "core/failed_rollback_recovery.py",
        "scripts/create_lesson_from_proposal.py", "scripts/seed_lessons_from_proposals.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert not literal_rollback_success_writes(source), relative


def test_verified_success_is_constructed_only_by_measuring_owners():
    root = Path(__file__).resolve().parents[1]
    owners: dict[str, set] = {"rollback_completed_verified": set(), "RollbackOutcome": set()}
    replaced_status = []
    for directory in ("core", "patching", "web", "scripts", "cli", "graph", "database"):
        for path in sorted((root / directory).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            # Every typed-outcome user imports core.rollback_outcome by name.
            if "rollback_outcome" not in text and "RollbackOutcome" not in text:
                continue
            relative = path.relative_to(root).as_posix()
            for function in ast.walk(ast.parse(text)):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for call in ast.walk(function):
                    if not isinstance(call, ast.Call):
                        continue
                    name = getattr(call.func, "id", getattr(call.func, "attr", ""))
                    if name in owners:
                        owners[name].add((relative, function.name))
                    if (name == "replace" and relative != "core/rollback_outcome.py"
                            and {k.arg for k in call.keywords} & {"status", "completed", "verified"}):
                        replaced_status.append((relative, call.lineno))
    # Success is only ever built after a byte comparison or from EXEC.PLAN.1's
    # verified transaction facts; nothing else can mint or relabel it.
    assert owners["rollback_completed_verified"] == {
        ("core/executor.py", "_recover_single_file"),
        ("core/rollback_outcome.py", "rollback_outcome_from_plan"),
    }
    assert {relative for relative, _ in owners["RollbackOutcome"]} == {"core/rollback_outcome.py"}
    assert replaced_status == []
