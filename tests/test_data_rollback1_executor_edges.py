"""DATA.ROLLBACK.1 single-file caller recovery and cleanup fault controls."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import config
import core.executor as executor
import core.mutation_oracle as mutation_oracle


BASELINE = b"def add(a, b):\r\n    return a - b\r\n"
PATCHED = b"def add(a, b):\r\n    return a + b\r\n"


def _patch():
    return {
        "relative_path": "calc.py",
        "target_snippet": "def add(a, b):\n    return a - b",
        "patched_snippet": "def add(a, b):\n    return a + b",
    }


def _validation(ok=True):
    return SimpleNamespace(
        ok=ok,
        output="1 passed" if ok else "1 failed",
        exit_code=0 if ok else 1,
        timed_out=False,
        timeout_seconds=None,
    )


def _setup_oracle(tmp_path, monkeypatch):
    target = tmp_path / "calc.py"
    target.write_bytes(BASELINE)
    monkeypatch.setattr(config, "MUTATION_ORACLE_ENABLED", True)
    monkeypatch.setattr(config, "MUTATION_ORACLE_MAX_MUTANTS", 1)
    monkeypatch.setattr(
        executor, "run_validation_command_detailed", lambda *a, **kw: _validation()
    )
    monkeypatch.setattr(
        mutation_oracle,
        "generate_mutants",
        lambda *a, **kw: [
            mutation_oracle.Mutant(
                kind="operator_flip", description="replace addition",
                code="def add(a, b):\n    return a * b",
            )
        ],
    )
    monkeypatch.setattr(mutation_oracle, "run_validation_command", lambda *a, **kw: (False, "1 failed"))
    return target


def _run(tmp_path):
    return executor.Executor(str(tmp_path)).run(
        _patch(), "python", validation_command="python -m pytest"
    )


@pytest.mark.parametrize("oracle_fault", ["raise", "noop"])
@pytest.mark.parametrize("outer_fault", [False, True])
def test_live_oracle_restore_failure_recovers_original_or_retains_it(
    tmp_path, monkeypatch, oracle_fault, outer_fault
):
    target = _setup_oracle(tmp_path, monkeypatch)

    def faulty_restore(*args):
        if oracle_fault == "raise":
            raise PermissionError("private restore exception")

    monkeypatch.setattr(mutation_oracle, "restore_backup", faulty_restore)
    if outer_fault:
        monkeypatch.setattr(executor, "restore_backup", faulty_restore)
    result = _run(tmp_path)

    assert result.success is False
    assert result.phase == "oracle_recovery_failed"
    assert result.rollback_attempted is True
    assert "private restore exception" not in (result.oracle_note or "")
    assert result.failure_info["code"] == "oracle_final_state_mismatch"
    guards = list(tmp_path.glob(".calc.py.bak.rollback-*.bak"))
    if outer_fault:
        assert result.rollback_outcome.status == "incomplete"
        assert result.rollback_performed is False
        assert result.final_repository_changed is True
        assert result.rollback_outcome.remaining_changed_paths == ("calc.py",)
        assert target.read_bytes() not in {BASELINE, PATCHED}
        assert len(guards) == 1
        assert guards[0].read_bytes() == BASELINE
        assert result.rollback_outcome.recovery_material_available is True
        store = tmp_path / ".agent" / "failed_rollback_recovery" / "v1"
        artifact_id, = result.rollback_outcome.recovery_artifact_ids
        assert (store / f"{artifact_id}.baseline").read_bytes() == BASELINE
        manifest = json.loads((store / f"{artifact_id}.json").read_text())
        assert manifest["source_execution_id"] == result.failure_info["recovery_source_execution_id"]
    else:
        assert target.read_bytes() == BASELINE
        assert result.rollback_outcome.status == "completed_verified"
        assert result.rollback_performed is True
        assert result.final_repository_changed is False
        assert not guards
        assert not list(tmp_path.glob(".agent/failed_rollback_recovery/v1/*.json"))


def test_live_oracle_success_keeps_verified_patch_and_cleans_original_guard(tmp_path, monkeypatch):
    target = _setup_oracle(tmp_path, monkeypatch)
    validated_bytes = []

    def validate(*args, **kwargs):
        validated_bytes.append(target.read_bytes())
        return _validation()

    monkeypatch.setattr(executor, "run_validation_command_detailed", validate)
    result = _run(tmp_path)
    assert result.success is True
    assert target.read_bytes() == validated_bytes[0]
    assert result.oracle_strength == 1.0
    assert result.oracle_tested == result.oracle_killed == 1
    assert result.rollback_outcome.status == "not_required"
    assert result.rollback_outcome.final_state_verified is True
    assert result.final_repository_changed is True
    assert not list(tmp_path.glob("*.bak"))
    assert not list(tmp_path.glob(".calc.py.bak.rollback-*.bak"))


def test_oracle_unreadable_final_state_uses_original_for_outer_recovery(tmp_path, monkeypatch):
    target = _setup_oracle(tmp_path, monkeypatch)
    original_read = Path.read_bytes
    oracle_finished = False

    def leave_unreadable(**kwargs):
        nonlocal oracle_finished
        target.write_bytes(b"mutant")
        oracle_finished = True
        return mutation_oracle.MutationOracleResult(strength=None, tested=1, killed=0)

    def read(path):
        if oracle_finished and path == target:
            raise PermissionError("private read failure")
        return original_read(path)

    monkeypatch.setattr(mutation_oracle, "run_mutation_oracle", leave_unreadable)
    monkeypatch.setattr(Path, "read_bytes", read)
    result = _run(tmp_path)
    assert result.success is False
    assert result.failure_info["code"] == "oracle_final_state_unverifiable"
    assert result.rollback_outcome.status == "unverifiable"
    assert result.rollback_attempted is True
    assert result.rollback_performed is False
    assert result.rollback_outcome.recovery_material_available is True
    assert result.rollback_outcome.recovery_material_error == ""
    assert original_read(target) == BASELINE
    guard, = tmp_path.glob(".calc.py.bak.rollback-*.bak")
    assert original_read(guard) == BASELINE


@pytest.mark.parametrize("baseline_fault", ["none", "missing", "unreadable"])
def test_unavailable_baseline_does_not_claim_attempt_or_source_id(tmp_path, monkeypatch, baseline_fault):
    target = tmp_path / "calc.py"
    backup = tmp_path / "calc.py.bak"
    target.write_bytes(b"mutated")
    if baseline_fault == "none":
        backup = None
    elif baseline_fault == "unreadable":
        backup.write_bytes(BASELINE)
        original_read = Path.read_bytes

        def read(path):
            if path == backup:
                raise PermissionError("private baseline failure")
            return original_read(path)

        monkeypatch.setattr(Path, "read_bytes", read)

    def must_not_restore(*args):
        pytest.fail("restore requires a readable baseline")

    monkeypatch.setattr(executor, "restore_backup", must_not_restore)
    outcome, source_id = executor._recover_single_file(tmp_path, target, backup)
    assert outcome.status == "unverifiable"
    assert outcome.attempted is False
    assert outcome.performed is False
    assert outcome.recovery_material_available is False
    assert outcome.recovery_material_error.startswith("rollback_baseline_unavailable:")
    assert source_id == ""
    assert target.read_bytes() == b"mutated"


@pytest.mark.parametrize("oracle_enabled", [False, True])
def test_cleanup_failure_preserves_verified_recovery_truth(tmp_path, monkeypatch, oracle_enabled):
    target = _setup_oracle(tmp_path, monkeypatch)
    if oracle_enabled:
        monkeypatch.setattr(mutation_oracle, "restore_backup", lambda *args: None)
    else:
        monkeypatch.setattr(config, "MUTATION_ORACLE_ENABLED", False)
        monkeypatch.setattr(executor, "run_validation_command_detailed", lambda *a, **kw: _validation(False))

    def cleanup_error(*args):
        raise PermissionError("private cleanup failure")

    monkeypatch.setattr(executor, "cleanup_backup", cleanup_error)
    result = _run(tmp_path)
    assert result.success is False
    assert target.read_bytes() == BASELINE
    assert result.rollback_performed is True
    assert result.rollback_outcome.status == "completed_verified"
    assert result.final_repository_changed is False
    assert "backup_cleanup_failed:PermissionError" in result.failure_info["recovery_cleanup_error"]
    assert result.rollback_outcome.failure_code == ""
    assert "private cleanup failure" not in str(result.failure_info)


def test_successful_oracle_cleanup_failure_does_not_erase_verified_state(tmp_path, monkeypatch):
    target = _setup_oracle(tmp_path, monkeypatch)

    def cleanup_error(*args):
        raise PermissionError("private cleanup failure")

    monkeypatch.setattr(executor, "cleanup_backup", cleanup_error)
    result = _run(tmp_path)
    assert result.success is True
    assert b"return a + b" in target.read_bytes()
    assert result.rollback_outcome.status == "not_required"
    assert result.rollback_outcome.final_state_verified is True
    assert result.final_repository_changed is True
    assert "backup_cleanup_failed:PermissionError" in result.failure_info["recovery_cleanup_error"]
    guard, = tmp_path.glob(".calc.py.bak.rollback-*.bak")
    assert guard.read_bytes() == BASELINE


def test_oracle_guard_failure_prevents_oracle_and_recovers_original(tmp_path, monkeypatch):
    target = _setup_oracle(tmp_path, monkeypatch)

    def guard_failure(*args):
        raise PermissionError("cannot stage original")

    def must_not_run(**kwargs):
        pytest.fail("oracle must not run without a protected original baseline")

    monkeypatch.setattr(executor, "_stage_oracle_baseline", guard_failure)
    monkeypatch.setattr(mutation_oracle, "run_mutation_oracle", must_not_run)
    result = _run(tmp_path)
    assert result.success is False
    assert result.failure_info["code"] == "oracle_baseline_unavailable"
    assert result.rollback_performed is True
    assert target.read_bytes() == BASELINE
    assert result.rollback_outcome.recovery_artifact_ids == ()


@pytest.mark.parametrize("external", [False, True])
@pytest.mark.parametrize("matching_bytes", [False, True])
def test_redirected_target_cannot_be_restored_or_relabelled(tmp_path, monkeypatch, external, matching_bytes):
    from tests.test_data_rollback1_store_edges import _directory_link

    repo = tmp_path / "repo"
    repo.mkdir()
    destination = (tmp_path if external else repo) / "replacement"
    destination.mkdir()
    current = BASELINE if matching_bytes else b"unrelated bytes"
    (destination / "calc.py").write_bytes(current)
    backup = repo / "original.bak"
    backup.write_bytes(BASELINE)
    target = repo / "original" / "calc.py"
    calls = []
    monkeypatch.setattr(executor, "restore_backup", lambda *args: calls.append(args))
    with _directory_link(repo / "original", destination):
        outcome, _ = executor._recover_single_file(repo, target, backup)
        assert executor._observe_single_file_change(target, backup) == (True, False)
    assert calls == []
    assert outcome.status == "unverifiable"
    assert outcome.remaining_changed_paths == ("original/calc.py",)
    assert not outcome.performed
    assert not outcome.recovery_material_available
    assert outcome.recovery_material_error
    assert backup.read_bytes() == BASELINE
    assert (destination / "calc.py").read_bytes() == current
