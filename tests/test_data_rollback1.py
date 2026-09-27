"""DATA.ROLLBACK.1 — verified rollback truth and emergency recovery data."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

import core.executor as single_executor
import patching.patch_plan_transaction as transaction
from core.execution_outcome_telemetry import (
    AUTHORITY_SOURCE_MANUAL_APPLY,
    FinalStateObservation,
    authorized_execution,
    plan_execution_receipt,
)
from core.failed_rollback_recovery import (
    RECOVERY_ARTIFACT_NAMESPACE,
    FailedRollbackRecoveryArtifact,
    FailedRollbackRecoveryStore,
)
from core.phase_picker import pick_phase_candidates
from core.rollback_outcome import (
    ROLLBACK_COMPLETED_VERIFIED,
    ROLLBACK_INCOMPLETE,
    ROLLBACK_NOT_REQUIRED,
    ROLLBACK_UNVERIFIABLE,
    RollbackOutcome,
    RollbackOutcomeError,
    rollback_outcome_from_mapping,
)
from core.validation_side_effects import with_atomicity_metadata
from patching.patch_plan_executor import apply_patch_plan
from tests._auth_web1_maintenance import before_auth_web1
from tests._data_rollback1_maintenance import before_data_rollback1


ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, before: str = "old", after: str = "new") -> dict:
    return {
        "op": "replace_snippet",
        "relative_path": path,
        "target_snippet": before,
        "patched_snippet": after,
    }


def create(path: str, content: str = "new") -> dict:
    return {"op": "create_file", "relative_path": path, "content": content}


def _later_write_failure(monkeypatch, failed_name: str):
    write = Path.write_bytes

    def fail(path: Path, raw: bytes):
        if path.name == failed_name and raw.startswith(b"new"):
            raise OSError("injected later mutation failure")
        return write(path, raw)

    monkeypatch.setattr(Path, "write_bytes", fail)


def _recovery_manifests(repo: Path) -> list[Path]:
    return list(
        (repo / ".agent" / RECOVERY_ARTIFACT_NAMESPACE / "v1").glob("*.json")
    )


def test_outcome_rejects_completion_without_verification():
    with pytest.raises(RollbackOutcomeError):
        RollbackOutcome(
            status=ROLLBACK_COMPLETED_VERIFIED,
            attempted=True,
            completed=True,
            verified=False,
        )


def test_entry_bytes_reproduce_data02_false_success(tmp_path, monkeypatch):
    old_metadata = ModuleType("core.validation_side_effects")
    old_metadata.__file__ = str(ROOT / "core/validation_side_effects.py")
    exec(
        compile(
            before_data_rollback1("core/validation_side_effects.py"),
            old_metadata.__file__,
            "exec",
        ),
        old_metadata.__dict__,
    )
    monkeypatch.setitem(sys.modules, "core.validation_side_effects", old_metadata)

    old_executor = ModuleType("patching._data_rollback1_entry_executor")
    old_executor.__file__ = str(ROOT / "patching/patch_plan_executor.py")
    old_executor.__package__ = "patching"
    exec(
        compile(
            before_data_rollback1("patching/patch_plan_executor.py"),
            old_executor.__file__,
            "exec",
        ),
        old_executor.__dict__,
    )

    target = tmp_path / "a.txt"
    target.write_bytes(b"old A")
    (tmp_path / "b.txt").write_bytes(b"old B")
    _later_write_failure(monkeypatch, "b.txt")
    original_restore = transaction.restore_target

    def fail_restore(path, baseline):
        if path == target:
            raise PermissionError("injected historical restore failure")
        return original_restore(path, baseline)

    monkeypatch.setattr(transaction, "restore_target", fail_restore)
    result = old_executor.apply_patch_plan(
        str(tmp_path),
        [replace("a.txt", "old A", "new A"), replace("b.txt", "old B", "new B")],
    )

    assert target.read_bytes() == b"new A"
    assert result["recovery_complete"] is False
    assert result["remaining_changed_paths"] == ["a.txt"]
    assert result["rollback_performed"] is True
    assert result["patch_ops_rollback_protected"] is True
    assert "rollback_outcome" not in result


def test_permission_error_restore_is_incomplete_and_preserves_baseline(
    tmp_path, monkeypatch
):
    target = tmp_path / "a.txt"
    target.write_bytes(b"old A\n")
    (tmp_path / "b.txt").write_bytes(b"old B\n")
    _later_write_failure(monkeypatch, "b.txt")
    original_restore = transaction.restore_target

    def fail_restore(path, baseline):
        if path == target:
            raise PermissionError("private restore failure")
        return original_restore(path, baseline)

    monkeypatch.setattr(transaction, "restore_target", fail_restore)
    result = apply_patch_plan(
        str(tmp_path), [replace("a.txt", "old A", "new A"), replace("b.txt", "old B", "new B")]
    )

    assert target.read_bytes() == b"new A\n"
    assert result["rollback_status"] == ROLLBACK_INCOMPLETE
    assert result["rollback_attempted"] is True
    assert result["rollback_performed"] is False
    assert result["rollback_verified"] is True
    assert result["remaining_changed_paths"] == ["a.txt"]
    assert result["final_repository_changed"] is True
    assert result["rollback_failure"]["code"] == "recovery_incomplete"
    assert "private restore failure" not in json.dumps(result)
    assert "rollback is incomplete" in result["message"]
    assert "a.txt" in result["message"]
    assert result["recovery_material_available"] is True
    assert len(result["recovery_artifact_ids"]) == 1

    from web.routes.patch_routes import _plan_transaction_fields

    api_fields = _plan_transaction_fields(result)
    assert api_fields["rollback_status"] == ROLLBACK_INCOMPLETE
    assert api_fields["rollback_outcome"]["performed"] is False
    assert api_fields["remaining_changed_paths"] == ["a.txt"]
    assert api_fields["recovery_artifact_ids"] == result["recovery_artifact_ids"]

    manifests = _recovery_manifests(tmp_path)
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="ascii"))
    artifact_id = result["recovery_artifact_ids"][0]
    baseline = manifests[0].with_name(f"{artifact_id}.baseline").read_bytes()
    assert manifest["namespace"] == RECOVERY_ARTIFACT_NAMESPACE
    assert manifest["repository_relative_path"] == "a.txt"
    assert manifest["originating_rollback_status"] == ROLLBACK_INCOMPLETE
    assert manifest["automated_restore_authority"] is False
    assert manifest["source_execution_id"] == result["recovery_source_execution_id"]
    assert baseline == b"old A\n"
    assert manifest["baseline_sha256"] == hashlib.sha256(baseline).hexdigest()
    assert manifest["observed_post_sha256"] == hashlib.sha256(b"new A\n").hexdigest()
    assert FailedRollbackRecoveryArtifact(**manifest).identity_id() == artifact_id


def test_silent_noop_restore_is_not_success(tmp_path, monkeypatch):
    target = tmp_path / "a.txt"
    target.write_bytes(b"old A")
    (tmp_path / "b.txt").write_bytes(b"old B")
    _later_write_failure(monkeypatch, "b.txt")
    original_restore = transaction.restore_target

    def noop(path, baseline):
        if path == target:
            return None
        return original_restore(path, baseline)

    monkeypatch.setattr(transaction, "restore_target", noop)
    result = apply_patch_plan(
        str(tmp_path), [replace("a.txt", "old A", "new A"), replace("b.txt", "old B", "new B")]
    )
    assert result["rollback_status"] == ROLLBACK_INCOMPLETE
    assert result["rollback_performed"] is False
    assert result["remaining_changed_paths"] == ["a.txt"]
    assert target.read_bytes() == b"new A"


def test_successful_rollback_is_verified_and_leaves_no_artifact(tmp_path, monkeypatch):
    target = tmp_path / "a.txt"
    target.write_bytes(b"old A\r\n")
    (tmp_path / "b.txt").write_bytes(b"old B\n")
    _later_write_failure(monkeypatch, "b.txt")
    result = apply_patch_plan(
        str(tmp_path), [replace("a.txt", "old A", "new A"), replace("b.txt", "old B", "new B")]
    )
    assert target.read_bytes() == b"old A\r\n"
    assert result["rollback_status"] == ROLLBACK_COMPLETED_VERIFIED
    assert result["rollback_attempted"] is True
    assert result["rollback_completed"] is True
    assert result["rollback_verified"] is True
    assert result["rollback_performed"] is True
    assert result["remaining_changed_paths"] == []
    assert result["final_repository_changed"] is False
    assert _recovery_manifests(tmp_path) == []


def test_multifile_partial_recovery_reports_only_unrestored_file(
    tmp_path, monkeypatch
):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_bytes(b"old A")
    b.write_bytes(b"old B")
    _later_write_failure(monkeypatch, "later.txt")
    original_restore = transaction.restore_target

    def partial(path, baseline):
        if path == b:
            raise PermissionError("B denied")
        return original_restore(path, baseline)

    monkeypatch.setattr(transaction, "restore_target", partial)
    result = apply_patch_plan(
        str(tmp_path),
        [replace("a.txt", "old A", "new A"), replace("b.txt", "old B", "new B"), create("later.txt")],
    )
    assert a.read_bytes() == b"old A"
    assert b.read_bytes() == b"new B"
    assert result["rollback_status"] == ROLLBACK_INCOMPLETE
    assert result["remaining_changed_paths"] == ["b.txt"]
    assert result["rollback_performed"] is False
    assert result["final_repository_changed"] is True


def test_pre_mutation_failure_requires_no_rollback(tmp_path):
    result = apply_patch_plan(str(tmp_path), [replace("missing.txt")])
    assert result["mutation_attempted"] is False
    assert result["rollback_status"] == ROLLBACK_NOT_REQUIRED
    assert result["rollback_attempted"] is False
    assert result["rollback_performed"] is False
    assert result["final_repository_changed"] is False


def _failed_validation(*_args, **_kwargs):
    return SimpleNamespace(
        ok=False,
        output="1 failed",
        exit_code=1,
        timed_out=False,
        timeout_seconds=None,
    )


def _single_patch() -> dict:
    return {
        "relative_path": "calc.py",
        "target_snippet": "def add(a, b):\n    return a - b",
        "patched_snippet": "def add(a, b):\n    return a + b",
    }


@pytest.mark.parametrize("restore_fault", ["raise", "noop"])
def test_single_file_restore_is_verified_and_failure_is_structured(
    tmp_path, monkeypatch, restore_fault
):
    target = tmp_path / "calc.py"
    baseline = b"def add(a, b):\n    return a - b\n"
    target.write_bytes(baseline)
    monkeypatch.setattr(single_executor, "run_validation_command_detailed", _failed_validation)

    if restore_fault == "raise":
        def faulty_restore(*_args, **_kwargs):
            raise PermissionError("private single restore failure")
    else:
        def faulty_restore(*_args, **_kwargs):
            return None
    monkeypatch.setattr(single_executor, "restore_backup", faulty_restore)

    result = single_executor.Executor(str(tmp_path)).run(
        _single_patch(), "python", validation_command="python -m pytest"
    )
    assert result.success is False
    assert result.rollback_attempted is True
    assert result.rollback_performed is False
    assert result.rollback_outcome.status == ROLLBACK_INCOMPLETE
    assert result.final_repository_changed is True
    assert result.rollback_outcome.remaining_changed_paths == ("calc.py",)
    assert result.rollback_outcome.recovery_material_available is True
    assert target.read_bytes() != baseline
    assert "private single restore failure" not in result.message
    assert (tmp_path / "calc.py.bak").read_bytes() == baseline


def test_single_file_successful_restore_verifies_exact_bytes(tmp_path, monkeypatch):
    target = tmp_path / "calc.py"
    baseline = b"def add(a, b):\r\n    return a - b\r\n"
    target.write_bytes(baseline)
    monkeypatch.setattr(single_executor, "run_validation_command_detailed", _failed_validation)
    result = single_executor.Executor(str(tmp_path)).run(
        _single_patch(), "python", validation_command="python -m pytest"
    )
    assert target.read_bytes() == baseline
    assert result.rollback_outcome.status == ROLLBACK_COMPLETED_VERIFIED
    assert result.rollback_performed is True
    assert result.final_repository_changed is False
    assert not (tmp_path / "calc.py.bak").exists()
    assert _recovery_manifests(tmp_path) == []


def test_unreadable_final_state_is_unverifiable_and_fails_closed(
    tmp_path, monkeypatch
):
    target, backup = tmp_path / "calc.py", tmp_path / "calc.py.bak"
    target.write_bytes(b"new")
    backup.write_bytes(b"old")
    read = Path.read_bytes

    def unreadable(path):
        if path == target:
            raise PermissionError("unreadable final state")
        return read(path)

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    outcome, _source_id = single_executor._recover_single_file(
        tmp_path.resolve(), target, backup
    )
    assert outcome.status == ROLLBACK_UNVERIFIABLE
    assert outcome.attempted is True
    assert outcome.performed is False
    assert outcome.final_repository_changed is True
    assert outcome.final_state_verified is False
    assert outcome.remaining_changed_paths == ("calc.py",)


def test_recovery_material_persistence_failure_is_reported_separately(
    tmp_path, monkeypatch
):
    target = tmp_path / "calc.py"
    target.write_bytes(b"def add(a, b):\n    return a - b\n")
    monkeypatch.setattr(single_executor, "run_validation_command_detailed", _failed_validation)
    monkeypatch.setattr(single_executor, "restore_backup", lambda *_args: None)
    monkeypatch.setattr(
        single_executor,
        "persist_failed_rollback_material",
        lambda *_args, **_kwargs: ((), "recovery_store_unavailable:PermissionError", "run-id"),
    )

    result = single_executor.Executor(str(tmp_path)).run(
        _single_patch(), "python", validation_command="python -m pytest"
    )
    assert result.rollback_outcome.status == ROLLBACK_INCOMPLETE
    assert result.rollback_performed is False
    assert result.rollback_outcome.recovery_material_available is False
    assert result.rollback_outcome.recovery_material_error == (
        "recovery_store_unavailable:PermissionError"
    )
    assert (tmp_path / "calc.py.bak").is_file()


def test_exec_plan_facts_map_without_reimplementing_recovery():
    completed = rollback_outcome_from_mapping(
        {
            "mutation_attempted": True,
            "recovery_attempted": True,
            "recovery_complete": True,
            "remaining_changed_paths": [],
            "remaining_created_directories": [],
        }
    )
    incomplete = rollback_outcome_from_mapping(
        {
            "mutation_attempted": True,
            "recovery_attempted": True,
            "recovery_complete": False,
            "remaining_changed_paths": ["a.py"],
            "remaining_created_directories": [],
        }
    )
    assert completed.status == ROLLBACK_COMPLETED_VERIFIED
    assert incomplete.status == ROLLBACK_INCOMPLETE
    assert incomplete.remaining_changed_paths == ("a.py",)


def test_validation_defaults_and_legacy_receipts_fail_closed():
    legacy = with_atomicity_metadata({"rollback_performed": True})
    assert legacy["patch_ops_rollback_protected"] is True
    assert legacy["patch_ops_rollback_protection_semantics"] == "capability_only"
    assert legacy["rollback_status"] == ROLLBACK_UNVERIFIABLE
    assert legacy["rollback_performed"] is False

    measured = with_atomicity_metadata(
        {
            "rollback_outcome": rollback_outcome_from_mapping(
                {
                    "mutation_attempted": True,
                    "recovery_attempted": True,
                    "recovery_complete": False,
                    "remaining_changed_paths": ["a.py"],
                }
            ).as_dict(),
            "rollback_performed": True,
        }
    )
    assert measured["rollback_status"] == ROLLBACK_INCOMPLETE
    assert measured["rollback_performed"] is False


def test_later_observation_overrides_a_stale_success_claim():
    receipt = plan_execution_receipt(
        {
            "mutation_attempted": True,
            "recovery_attempted": True,
            "recovery_complete": True,
            "remaining_changed_paths": [],
            "remaining_created_directories": [],
        }
    )
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_MANUAL_APPLY,
        receipt=receipt,
        observation=FinalStateObservation(
            scope="plan_named_paths", changed_paths=("late.py",), complete=True
        ),
    )
    assert telemetry.rollback_performed is False
    assert telemetry.rollback_outcome.status == ROLLBACK_INCOMPLETE
    assert telemetry.final_repository_changed is True
    assert telemetry.rollback_outcome.remaining_changed_paths == ("late.py",)


def test_current_success_writers_are_owned_by_typed_outcome():
    production = [
        ROOT / "core" / "executor.py",
        ROOT / "patching" / "patch_plan_executor.py",
        ROOT / "core" / "validation_side_effects.py",
        ROOT / "core" / "execution_outcome_telemetry.py",
    ]
    for path in production:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        bad = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.keyword) or node.arg != "rollback_performed":
                continue
            if isinstance(node.value, ast.Constant) and node.value.value is True:
                bad.append(node.lineno)
        assert bad == [], f"independent rollback success writer in {path}: {bad}"


def test_recovery_store_rejects_repository_traversal(tmp_path):
    store = FailedRollbackRecoveryStore(tmp_path)
    with pytest.raises(ValueError):
        store.persist(
            relative_path="../outside.py",
            baseline_bytes=b"baseline",
            baseline_exists=True,
            source_execution_id="source",
            originating_rollback_status=ROLLBACK_INCOMPLETE,
        )


def test_created_directory_absence_is_durable_recovery_material(tmp_path):
    created = tmp_path / "new-package"
    created.mkdir()
    store = FailedRollbackRecoveryStore(tmp_path)
    artifact = store.persist(
        relative_path="new-package",
        baseline_bytes=None,
        baseline_exists=False,
        source_execution_id="server-generated-test-id",
        originating_rollback_status=ROLLBACK_INCOMPLETE,
    )
    assert artifact.repository_relative_path == "new-package"
    assert artifact.baseline_exists is False
    assert artifact.observed_post_exists is True
    assert not (store.directory / f"{artifact.artifact_id}.baseline").exists()
    store.verify(artifact)


def test_frozen_phase_and_audit_boundaries_are_byte_exact():
    receipt = json.loads(
        (ROOT / "tests/fixtures/data_rollback1_frozen_boundaries.json").read_text(
            encoding="utf-8"
        )
    )
    for relative, expected in receipt["sha256"].items():
        assert hashlib.sha256(before_auth_web1(relative)).hexdigest() == expected


def test_reversal_receipt_reconstructs_every_entry_file():
    receipt = json.loads(
        (ROOT / "tests/fixtures/data_rollback1_reversal.json").read_text(
            encoding="utf-8"
        )
    )
    for relative, record in receipt["files"].items():
        restored = before_data_rollback1(relative)
        assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"]


def test_registry_has_one_complete_bounded_phase_and_picker_is_unchanged():
    registry = json.loads(
        (ROOT / "docs/roadmap/phase_registry.json").read_text(encoding="utf-8")
    )
    phases = [
        phase for phase in registry["phases"]
        if phase["phase_id"] == "DATA.ROLLBACK.1"
    ]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "HARDEN"
    assert phase["status"] == "complete"
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["prerequisites"] == ["AUTH.DREAM.1"]

    pick = pick_phase_candidates(registry)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_completion_receipt_pins_every_phase_source():
    receipt = json.loads(
        (ROOT / "tests/fixtures/data_rollback1_completion.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["phase"] == "DATA.ROLLBACK.1"
    assert receipt["closed_finding"] == "DATA-02"
    assert receipt["model_calls"] == 0
    assert receipt["external_network_requests"] == 0
    expected = set(receipt["existing_files_changed"] + receipt["new_files"])
    expected.remove("tests/fixtures/data_rollback1_completion.json")
    assert set(receipt["source_sha256"]) == expected
    for relative, digest in receipt["source_sha256"].items():
        assert hashlib.sha256(before_auth_web1(relative)).hexdigest() == digest
