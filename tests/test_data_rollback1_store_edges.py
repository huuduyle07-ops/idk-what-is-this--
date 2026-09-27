"""Recovery material stays bound to exact targets and a real local store."""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess

import pytest

import core.failed_rollback_recovery as recovery
from core.rollback_outcome import ROLLBACK_INCOMPLETE, ROLLBACK_UNVERIFIABLE


@contextmanager
def _directory_link(link: Path, destination: Path):
    """Use real Windows junctions without requiring symlink privileges."""
    if os.name == "nt":
        environment = dict(os.environ)
        environment["ROLLBACK_TEST_JUNCTION"] = str(link)
        environment["ROLLBACK_TEST_DESTINATION"] = str(destination)
        subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "$ErrorActionPreference = 'Stop'; "
                "New-Item -ItemType Junction -Path $env:ROLLBACK_TEST_JUNCTION "
                "-Target $env:ROLLBACK_TEST_DESTINATION | Out-Null",
            ],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    else:
        link.symlink_to(destination, target_is_directory=True)
    try:
        yield
    finally:
        # Remove only this exact link, never recurse into its destination.
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


def _persist(store, **overrides):
    values = {
        "relative_path": "target.py",
        "baseline_bytes": b"baseline\r\n",
        "baseline_exists": True,
        "baseline_mode": 0o644,
        "source_execution_id": "test-execution-id",
        "originating_rollback_status": ROLLBACK_INCOMPLETE,
    }
    values.update(overrides)
    return store.persist(**values)


@pytest.mark.parametrize("component", [0, 1, 2])
def test_real_junction_cannot_redirect_emergency_store(tmp_path, component):
    repo, outside = tmp_path / "repo", tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    parts = (".agent", recovery.RECOVERY_ARTIFACT_NAMESPACE, "v1")
    parent = repo.joinpath(*parts[:component])
    parent.mkdir(parents=True, exist_ok=True)
    with _directory_link(parent / parts[component], outside):
        store = recovery.FailedRollbackRecoveryStore(repo)
        with pytest.raises(ValueError, match="links or reparse"):
            _persist(store)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("external", [False, True])
def test_redirected_target_is_rejected_without_relabelling(tmp_path, external):
    repo = tmp_path / "repo"
    repo.mkdir()
    destination = (tmp_path if external else repo) / "real"
    destination.mkdir()
    (destination / "target.py").write_bytes(b"mutated")
    store = recovery.FailedRollbackRecoveryStore(repo)
    with _directory_link(repo / "alias", destination):
        with pytest.raises(ValueError, match="link or reparse"):
            _persist(store, relative_path="alias/target.py")
    assert not (repo / ".agent").exists()
    assert (destination / "target.py").read_bytes() == b"mutated"


def test_junction_inserted_between_baseline_and_manifest_is_rejected(
    tmp_path, monkeypatch
):
    repo, outside = tmp_path / "repo", tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    store = recovery.FailedRollbackRecoveryStore(repo)
    atomic = recovery._atomic_bytes
    displaced = store.directory.with_name("v1-original")
    with ExitStack() as links:
        def redirect_after_baseline(path, raw):
            atomic(path, raw)
            if path.suffix == ".baseline":
                store.directory.rename(displaced)
                links.enter_context(_directory_link(store.directory, outside))

        monkeypatch.setattr(recovery, "_atomic_bytes", redirect_after_baseline)
        with pytest.raises(ValueError, match="links or reparse"):
            _persist(store)
    assert list(outside.iterdir()) == []
    assert len(list(displaced.glob("*.baseline"))) == 1
    assert list(displaced.glob("*.json")) == []


def test_verify_rechecks_store_after_directory_replacement(tmp_path):
    repo, outside = tmp_path / "repo", tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    store = recovery.FailedRollbackRecoveryStore(repo)
    artifact = _persist(store)
    store.directory.rename(store.directory.with_name("v1-original"))
    with _directory_link(store.directory, outside):
        with pytest.raises(ValueError, match="links or reparse"):
            store.verify(artifact)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "relative",
    ["../outside.py", "dir/../../outside.py", ".agent", ".AgEnT/private", "C:/outside.py", "/outside.py"],
)
def test_invalid_target_spellings_do_not_create_store(tmp_path, relative):
    store = recovery.FailedRollbackRecoveryStore(tmp_path)
    with pytest.raises(ValueError):
        _persist(store, relative_path=relative)
    assert not (tmp_path / ".agent").exists()


def test_absolute_path_inside_repository_is_rejected(tmp_path):
    store = recovery.FailedRollbackRecoveryStore(tmp_path)
    with pytest.raises(ValueError):
        _persist(store, relative_path=str(tmp_path / "target.py"))
    assert not (tmp_path / ".agent").exists()


@pytest.mark.parametrize("source", ["", " ", "x\ny", "x\x00y", "x" * 257, None, 1])
def test_source_identity_must_be_bounded_and_nonblank(tmp_path, source):
    store = recovery.FailedRollbackRecoveryStore(tmp_path)
    with pytest.raises(ValueError, match="source execution"):
        _persist(store, source_execution_id=source)
    assert not (tmp_path / ".agent").exists()


@pytest.mark.parametrize("status", ["completed_verified", "not_required", "", None, []])
def test_only_failed_rollback_statuses_create_material(tmp_path, status):
    store = recovery.FailedRollbackRecoveryStore(tmp_path)
    with pytest.raises(ValueError, match="failed rollback status"):
        _persist(store, originating_rollback_status=status)
    assert not (tmp_path / ".agent").exists()


@pytest.mark.parametrize("status", [ROLLBACK_INCOMPLETE, ROLLBACK_UNVERIFIABLE])
def test_artifact_binds_observed_state_exact_path_and_mode(tmp_path, status):
    target = tmp_path / "package" / "target.py"
    target.parent.mkdir()
    target.write_bytes(b"baseline\r\n")
    store = recovery.FailedRollbackRecoveryStore(tmp_path)
    baseline_mode = 0o755
    artifact = _persist(
        store,
        relative_path="package/target.py",
        baseline_mode=baseline_mode,
        originating_rollback_status=status,
    )
    assert artifact.repository_relative_path == "package/target.py"
    assert artifact.baseline_mode == baseline_mode
    assert artifact.baseline_sha256 == artifact.observed_post_sha256
    assert artifact.originating_rollback_status == status
    assert artifact.automated_restore_authority is False
    changed_mode = _persist(
        store,
        relative_path="package/target.py",
        baseline_mode=0o644,
        originating_rollback_status=status,
    )
    assert artifact.artifact_id != changed_mode.artifact_id
    store.verify(artifact)


@pytest.mark.parametrize("tamper", ["baseline", "manifest", "identity"])
def test_integrity_tamper_is_rejected(tmp_path, tamper):
    store = recovery.FailedRollbackRecoveryStore(tmp_path)
    artifact = _persist(store)
    if tamper == "baseline":
        (store.directory / f"{artifact.artifact_id}.baseline").write_bytes(b"wrong")
    elif tamper == "manifest":
        manifest = store.directory / f"{artifact.artifact_id}.json"
        data = json.loads(manifest.read_bytes())
        data["repository_relative_path"] = "other.py"
        manifest.write_text(json.dumps(data), encoding="ascii")
    else:
        artifact = replace(artifact, source_execution_id="another-execution")
    with pytest.raises(ValueError, match="verification"):
        store.verify(artifact)


@pytest.mark.parametrize(
    "field,value",
    [
        ("canonical_repository_identity", "other-repository"),
        ("namespace", "undo"),
        ("schema_version", 2),
        ("automated_restore_authority", True),
    ],
)
def test_rehashed_foreign_scope_is_not_verified(tmp_path, field, value):
    store = recovery.FailedRollbackRecoveryStore(tmp_path)
    original = _persist(store)
    changed = replace(original, **{field: value})
    changed = replace(changed, artifact_id=changed.identity_id())
    with pytest.raises(ValueError, match="scope failed verification"):
        store.verify(changed)


def test_partial_persistence_keeps_verified_ids_and_reports_failure(tmp_path, monkeypatch):
    original = recovery.FailedRollbackRecoveryStore.persist

    def fail_middle(store, **kwargs):
        if kwargs["relative_path"] == "b.py":
            raise PermissionError("private operating-system detail")
        return original(store, **kwargs)

    monkeypatch.setattr(recovery.FailedRollbackRecoveryStore, "persist", fail_middle)
    ids, error, execution_id = recovery.persist_failed_rollback_material(
        tmp_path,
        [(name, raw, True, 0o644) for name, raw in [("a.py", b"a"), ("b.py", b"b"), ("c.py", b"c")]],
        originating_rollback_status=ROLLBACK_INCOMPLETE,
        source_execution_id="partial-execution",
    )
    assert len(ids) == 2
    assert error == "b.py:PermissionError"
    assert execution_id == "partial-execution"
    store = recovery.FailedRollbackRecoveryStore(tmp_path)
    artifacts = [
        recovery.FailedRollbackRecoveryArtifact(
            **json.loads((store.directory / f"{artifact_id}.json").read_bytes())
        )
        for artifact_id in ids
    ]
    assert {artifact.repository_relative_path for artifact in artifacts} == {"a.py", "c.py"}
    for artifact in artifacts:
        store.verify(artifact)


def test_explicit_empty_source_is_not_silently_replaced(tmp_path):
    ids, error, source = recovery.persist_failed_rollback_material(
        tmp_path,
        [("target.py", b"old", True, 0o644)],
        originating_rollback_status=ROLLBACK_INCOMPLETE,
        source_execution_id="",
    )
    assert ids == ()
    assert error == "target.py:ValueError"
    assert source == ""
    assert not (tmp_path / ".agent").exists()


def test_empty_recovery_and_store_construction_do_not_create_directories(tmp_path):
    recovery.FailedRollbackRecoveryStore(tmp_path)
    ids, error, source = recovery.persist_failed_rollback_material(
        tmp_path, [], originating_rollback_status=ROLLBACK_INCOMPLETE
    )
    assert ids == ()
    assert error == ""
    assert source
    assert not (tmp_path / ".agent").exists()


def test_emergency_artifacts_are_never_undo_backup_authority(tmp_path):
    from core.undo_backup import UndoBackupStore

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "target.py").write_bytes(b"unresolved\r\n")
    store = recovery.FailedRollbackRecoveryStore(repo)
    artifact = _persist(store)
    undo = UndoBackupStore(tmp_path / "undo-backups")

    # Both IDs are 64-hex opaque strings, so separation must not rely on format.
    refused = undo.undo(repo, artifact.artifact_id, relative="target.py")
    assert refused["success"] is False
    assert refused["code"] == "backup_not_found"

    # Even the exact emergency bytes placed where Undo looks are not a backup.
    undo.directory.mkdir(parents=True)
    (undo.directory / f"{artifact.artifact_id}.json").write_bytes(
        (store.directory / f"{artifact.artifact_id}.json").read_bytes()
    )
    (undo.directory / f"{artifact.artifact_id}.bak").write_bytes(
        (store.directory / f"{artifact.artifact_id}.baseline").read_bytes()
    )
    refused = undo.undo(repo, artifact.artifact_id, relative="target.py")
    assert refused["success"] is False
    assert refused["code"] == "backup_metadata_invalid"
    assert (repo / "target.py").read_bytes() == b"unresolved\r\n"
    store.verify(artifact)
    assert not any(
        hasattr(store, name) for name in ("undo", "restore", "consume", "apply", "lookup")
    )


def test_plan_partial_persistence_is_reported_as_partial_not_recoverable(
    tmp_path, monkeypatch
):
    import patching.patch_plan_transaction as transaction
    from patching.patch_plan_executor import apply_patch_plan

    names = ("a.py", "b.py", "c.py")
    for name in names:
        (tmp_path / name).write_bytes(b"old " + name.encode())
    write, restore = Path.write_bytes, transaction.restore_target
    persist = recovery.FailedRollbackRecoveryStore.persist

    def later_failure(path, raw):
        if path.name == "c.py" and raw.startswith(b"new"):
            raise OSError("injected later mutation failure")
        return write(path, raw)

    def denied(path, baseline):
        if path.name in {"a.py", "b.py"}:
            raise PermissionError("injected restore failure")
        return restore(path, baseline)

    def lose_b(store, **kwargs):
        if kwargs["relative_path"] == "b.py":
            raise OSError("private disk detail")
        return persist(store, **kwargs)

    monkeypatch.setattr(Path, "write_bytes", later_failure)
    monkeypatch.setattr(transaction, "restore_target", denied)
    monkeypatch.setattr(recovery.FailedRollbackRecoveryStore, "persist", lose_b)
    result = apply_patch_plan(str(tmp_path), [
        {"op": "replace_snippet", "relative_path": name,
         "target_snippet": f"old {name}", "patched_snippet": f"new {name}"}
        for name in names
    ])
    assert result["rollback_status"] == ROLLBACK_INCOMPLETE
    assert result["remaining_changed_paths"] == ["a.py", "b.py"]
    assert len(result["recovery_artifact_ids"]) == 1
    assert result["recovery_material_available"] is True
    assert result["recovery_material_error"] == "b.py:OSError"
    assert "only partially available" in result["message"]
    assert "Emergency recovery material is available." not in result["message"]
    assert "private disk detail" not in json.dumps(result)
