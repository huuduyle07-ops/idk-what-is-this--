import copy
import json
from pathlib import Path
import hashlib
import os
import shutil
import pytest

import core.index_manifest as index_manifest_module
from core import repo_librarian
from core.index_manifest import (
    MANIFEST_LOAD_EPOCH_MISMATCH,
    MANIFEST_LOAD_INVALID,
    MANIFEST_LOAD_LOADED,
    MANIFEST_LOAD_MISSING,
    MANIFEST_LOAD_REPOSITORY_MISMATCH,
    MANIFEST_LOAD_ROOT_MISMATCH,
    MANIFEST_LOAD_SCOPE_MISMATCH,
    MANIFEST_LOAD_UNSUPPORTED_SCHEMA,
    MANIFEST_VERSION,
    FileFingerprint,
    RepositoryManifest,
    get_repository_manifest_path,
    load_repository_manifest,
    load_repository_manifest_result,
    save_repository_manifest,
    fingerprint_file,
    inspect_repository_delta
)
from core.repo_ignore import compute_policy_fingerprint
from core.repository_inventory import create_repository_inventory
from core.repository_identity import (
    build_code_index_scope,
    derive_repository_id,
)

VALID_SHA256 = "a" * 64


def _make_manifest(repo_path: Path) -> RepositoryManifest:
    return RepositoryManifest(
        version=MANIFEST_VERSION,
        repo_root=str(repo_path.resolve()),
        policy_fingerprint=VALID_SHA256,
        files={
            "core/example.py": FileFingerprint(
                size=12,
                mtime_ns=123456789,
                sha256=VALID_SHA256,
            )
        },
    )


@pytest.fixture
def manifest_result_repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        index_manifest_module,
        "AGENT_DIR",
        tmp_path / "agent-output",
    )
    return repo


def _manifest_binding(
    repo: Path,
    *,
    architecture_epoch: int | None = None,
) -> tuple[str, str]:
    return (
        derive_repository_id(repo),
        build_code_index_scope(
            repo,
            architecture_epoch=architecture_epoch,
        ),
    )


def _bound_manifest(
    repo: Path,
    *,
    architecture_epoch: int | None = None,
) -> RepositoryManifest:
    repository_id, index_scope = _manifest_binding(
        repo,
        architecture_epoch=architecture_epoch,
    )
    return RepositoryManifest(
        version=MANIFEST_VERSION,
        repo_root=str(repo.resolve()),
        policy_fingerprint=compute_policy_fingerprint(str(repo)),
        files={
            "app.py": fingerprint_file(repo / "app.py").fingerprint,
        },
        repository_id=repository_id,
        architecture_epoch=architecture_epoch,
        index_scope=index_scope,
    )


def _bound_manifest_payload(
    repo: Path,
    *,
    version: str = MANIFEST_VERSION,
    repo_root: str | None = None,
    repository_id: str | None = None,
    architecture_epoch: int | None = None,
    index_scope: str | None = None,
) -> dict:
    expected_repository_id, expected_scope = _manifest_binding(
        repo,
        architecture_epoch=architecture_epoch,
    )
    fingerprint = fingerprint_file(repo / "app.py").fingerprint
    return {
        "version": version,
        "repo_root": repo_root or str(repo.resolve()),
        "policy_fingerprint": compute_policy_fingerprint(str(repo)),
        "files": {
            "app.py": {
                "size": fingerprint.size,
                "mtime_ns": fingerprint.mtime_ns,
                "sha256": fingerprint.sha256,
            },
        },
        "repository_id": repository_id or expected_repository_id,
        "architecture_epoch": architecture_epoch,
        "index_scope": index_scope or expected_scope,
    }


def _write_manifest_payload(repo: Path, payload: dict) -> Path:
    path = get_repository_manifest_path(str(repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _load_result(
    repo: Path,
    *,
    architecture_epoch: int | None = None,
):
    repository_id, index_scope = _manifest_binding(
        repo,
        architecture_epoch=architecture_epoch,
    )
    return load_repository_manifest_result(
        str(repo),
        repository_id=repository_id,
        architecture_epoch=architecture_epoch,
        index_scope=index_scope,
    )


def test_missing_manifest_returns_none(tmp_path):
    assert load_repository_manifest(str(tmp_path)) is None


def test_supplied_inventory_rejects_conflicting_policy_fingerprint(
    tmp_path,
):
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    inventory = create_repository_inventory(tmp_path)

    with pytest.raises(
        ValueError,
        match="policy_fingerprint conflicts",
    ):
        inspect_repository_delta(
            str(tmp_path),
            inventory=inventory,
            policy_fingerprint="not-the-inventory-policy",
        )


def test_supplied_inventory_root_mismatch_precedes_missing_root_fallback(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    inventory = create_repository_inventory(repo)

    with pytest.raises(
        ValueError,
        match="belongs to another repository",
    ):
        inspect_repository_delta(
            str(tmp_path / "missing"),
            inventory=inventory,
        )


def test_save_and_load_manifest_round_trip(tmp_path):
    manifest = _make_manifest(tmp_path)

    saved_path = save_repository_manifest(
        str(tmp_path),
        manifest,
    )
    loaded = load_repository_manifest(str(tmp_path))

    assert saved_path.is_file()
    assert loaded == manifest


def test_save_creates_manifest_file(tmp_path):
    manifest = _make_manifest(tmp_path)
    path = get_repository_manifest_path(str(tmp_path))

    # Ensure this test starts without the destination directory,
    # regardless of artifacts left by an earlier test run.
    if path.parent.exists():
        shutil.rmtree(path.parent)

    assert not path.parent.exists()
    assert not path.exists()

    saved_path = save_repository_manifest(
        str(tmp_path),
        manifest,
    )

    assert saved_path == path
    assert path.parent.is_dir()
    assert path.is_file()


def test_malformed_json_returns_none(tmp_path):
    path = get_repository_manifest_path(str(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")

    assert load_repository_manifest(str(tmp_path)) is None


def test_wrong_version_returns_none(tmp_path):
    path = get_repository_manifest_path(str(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": "unknown_manifest_v99",
        "repo_root": str(tmp_path.resolve()),
        "policy_fingerprint": "policy-v1",
        "files": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_repository_manifest(str(tmp_path)) is None


def test_manifest_for_other_repository_is_rejected(
    tmp_path,
):
    repository_a = tmp_path / "repo-a"
    repository_b = tmp_path / "repo-b"
    repository_a.mkdir()
    repository_b.mkdir()

    manifest = _make_manifest(repository_a)

    with pytest.raises(ValueError):
        save_repository_manifest(
            str(repository_b),
            manifest,
        )


def test_save_output_is_deterministic(tmp_path):
    manifest = RepositoryManifest(
        version=MANIFEST_VERSION,
        repo_root=str(tmp_path.resolve()),
        policy_fingerprint="policy-v1",
        files={
            "z.py": FileFingerprint(
                size=1,
                mtime_ns=2,
                sha256="b" * 64,
            ),
            "a.py": FileFingerprint(
                size=3,
                mtime_ns=4,
                sha256="c" * 64,
            ),
        },
    )

    path = save_repository_manifest(
        str(tmp_path),
        manifest,
    )
    first = path.read_bytes()

    save_repository_manifest(str(tmp_path), manifest)
    second = path.read_bytes()

    assert first == second
    assert first.find(b'"a.py"') < first.find(b'"z.py"')


def test_invalid_file_record_returns_none(tmp_path):
    path = get_repository_manifest_path(str(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": MANIFEST_VERSION,
        "repo_root": str(tmp_path.resolve()),
        "policy_fingerprint": "policy-v1",
        "files": {
            "core/example.py": {
                "size": -1,
                "mtime_ns": 123,
                "sha256": VALID_SHA256,
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_repository_manifest(str(tmp_path)) is None

def test_fingerprint_new_file_computes_sha256(tmp_path):
    path = tmp_path / "example.py"
    content = b"print('hello')\n"
    path.write_bytes(content)

    result = fingerprint_file(path)

    assert result.hash_reused is False
    assert result.fingerprint.size == len(content)
    assert result.fingerprint.sha256 == hashlib.sha256(
        content
    ).hexdigest()

def test_fingerprint_reuses_hash_when_metadata_is_unchanged(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "example.py"
    path.write_text("hello\n", encoding="utf-8")

    first = fingerprint_file(path)

    def fail_if_hashed(_path):
        raise AssertionError("unchanged file was hashed again")

    monkeypatch.setattr(
        "core.index_manifest._sha256_file",
        fail_if_hashed,
    )

    second = fingerprint_file(
        path,
        previous=first.fingerprint,
    )

    assert second.hash_reused is True
    assert second.fingerprint == first.fingerprint

def test_mtime_change_rehashes_but_preserves_content_hash(
    tmp_path,
):
    path = tmp_path / "example.py"
    path.write_text("stable\n", encoding="utf-8")

    first = fingerprint_file(path)

    stat = path.stat()
    os.utime(
        path,
        ns=(
            stat.st_atime_ns,
            stat.st_mtime_ns + 1_000_000_000,
        ),
    )

    second = fingerprint_file(
        path,
        previous=first.fingerprint,
    )

    assert second.hash_reused is False
    assert second.fingerprint.sha256 == first.fingerprint.sha256
    assert second.fingerprint.mtime_ns != first.fingerprint.mtime_ns

def test_fingerprint_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        fingerprint_file(tmp_path / "missing.py")

def test_first_delta_marks_all_files_added(tmp_path):
    first = tmp_path / "b.py"
    second = tmp_path / "a.py"

    first.write_text("b = 2\n", encoding="utf-8")
    second.write_text("a = 1\n", encoding="utf-8")

    manifest, delta = inspect_repository_delta(
        str(tmp_path),
        policy_fingerprint="policy-v1",
    )

    assert delta.added == ("a.py", "b.py")
    assert delta.modified == ()
    assert delta.deleted == ()
    assert delta.unchanged == ()
    assert delta.hashes_computed == 2
    assert delta.hashes_reused == 0
    assert tuple(manifest.files) == ("a.py", "b.py")


def test_second_delta_reuses_all_unchanged_hashes(tmp_path):
    path = tmp_path / "example.py"
    path.write_text("value = 1\n", encoding="utf-8")

    first_manifest, _ = inspect_repository_delta(
        str(tmp_path),
        policy_fingerprint="policy-v1",
    )

    second_manifest, delta = inspect_repository_delta(
        str(tmp_path),
        previous=first_manifest,
        policy_fingerprint="policy-v1",
    )

    assert delta.added == ()
    assert delta.modified == ()
    assert delta.deleted == ()
    assert delta.unchanged == ("example.py",)
    assert delta.hashes_computed == 0
    assert delta.hashes_reused == 1
    assert second_manifest == first_manifest

def test_delta_detects_added_file(tmp_path):
    existing = tmp_path / "existing.py"
    existing.write_text("existing = True\n", encoding="utf-8")

    previous, _ = inspect_repository_delta(str(tmp_path))

    added = tmp_path / "added.py"
    added.write_text("added = True\n", encoding="utf-8")

    _, delta = inspect_repository_delta(
        str(tmp_path),
        previous=previous,
    )

    assert delta.added == ("added.py",)
    assert delta.modified == ()
    assert delta.deleted == ()
    assert delta.unchanged == ("existing.py",)

def test_delta_detects_modified_content(tmp_path):
    path = tmp_path / "example.py"
    path.write_text("old\n", encoding="utf-8")

    previous, _ = inspect_repository_delta(str(tmp_path))

    path.write_text(
        "new content with a different size\n",
        encoding="utf-8",
    )

    _, delta = inspect_repository_delta(
        str(tmp_path),
        previous=previous,
    )

    assert delta.modified == ("example.py",)
    assert delta.added == ()
    assert delta.deleted == ()
    assert delta.unchanged == ()
    assert delta.hashes_computed == 1

def test_delta_detects_deleted_file(tmp_path):
    removed = tmp_path / "removed.py"
    kept = tmp_path / "kept.py"

    removed.write_text("remove = True\n", encoding="utf-8")
    kept.write_text("keep = True\n", encoding="utf-8")

    previous, _ = inspect_repository_delta(str(tmp_path))
    removed.unlink()

    _, delta = inspect_repository_delta(
        str(tmp_path),
        previous=previous,
    )

    assert delta.deleted == ("removed.py",)
    assert delta.unchanged == ("kept.py",)
    assert delta.added == ()
    assert delta.modified == ()

def test_delta_treats_mtime_only_change_as_unchanged(tmp_path):
    path = tmp_path / "example.py"
    path.write_text("stable = True\n", encoding="utf-8")

    previous, _ = inspect_repository_delta(str(tmp_path))

    stat = path.stat()
    os.utime(
        path,
        ns=(
            stat.st_atime_ns,
            stat.st_mtime_ns + 1_000_000_000,
        ),
    )

    current, delta = inspect_repository_delta(
        str(tmp_path),
        previous=previous,
    )

    assert delta.modified == ()
    assert delta.unchanged == ("example.py",)
    assert delta.hashes_computed == 1
    assert delta.hashes_reused == 0

    assert (
        current.files["example.py"].sha256
        == previous.files["example.py"].sha256
    )

def test_delta_reports_newly_ignored_file_as_deleted(tmp_path):
    generated = tmp_path / "generated.py"
    generated.write_text(
        "generated = True\n",
        encoding="utf-8",
    )

    gitignore = tmp_path / ".gitignore"

    # The policy file must already belong to the previous manifest.
    gitignore.write_text("", encoding="utf-8")

    previous, _ = inspect_repository_delta(str(tmp_path))

    gitignore.write_text(
        "generated.py\n",
        encoding="utf-8",
    )

    _, delta = inspect_repository_delta(
        str(tmp_path),
        previous=previous,
    )

    assert delta.deleted == ("generated.py",)
    assert delta.added == ()
    assert delta.modified == (".gitignore",)

def test_delta_never_includes_hard_excluded_temp_files(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("source = True\n", encoding="utf-8")

    temporary = tmp_path / ".tmp" / "generated.py"
    temporary.parent.mkdir()
    temporary.write_text("temporary = True\n", encoding="utf-8")

    manifest, delta = inspect_repository_delta(str(tmp_path))

    assert "source.py" in manifest.files
    assert ".tmp/generated.py" not in manifest.files
    assert ".tmp/generated.py" not in delta.added

def test_inspect_delta_does_not_save_manifest(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("source = True\n", encoding="utf-8")

    manifest_path = get_repository_manifest_path(str(tmp_path))
    manifest_path.unlink(missing_ok=True)

    inspect_repository_delta(str(tmp_path))

    assert not manifest_path.exists()

def test_delta_rejects_manifest_from_other_repository(tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    source = repo_a / "source.py"
    source.write_text("source = True\n", encoding="utf-8")

    manifest_a, _ = inspect_repository_delta(str(repo_a))

    with pytest.raises(
        ValueError,
        match="another repository",
    ):
        inspect_repository_delta(
            str(repo_b),
            previous=manifest_a,
        )

def test_policy_fingerprint_is_deterministic(tmp_path):
    first = compute_policy_fingerprint(str(tmp_path))
    second = compute_policy_fingerprint(str(tmp_path))

    assert first == second
    assert len(first) == 64

def test_policy_fingerprint_changes_with_gitignore(tmp_path):
    first = compute_policy_fingerprint(str(tmp_path))

    (tmp_path / ".gitignore").write_text(
        "*.log\n",
        encoding="utf-8",
    )

    second = compute_policy_fingerprint(str(tmp_path))

    assert second != first

def test_policy_fingerprint_changes_with_cattusignore(tmp_path):
    first = compute_policy_fingerprint(str(tmp_path))

    (tmp_path / ".cattusignore").write_text(
        "docs/archive/\n",
        encoding="utf-8",
    )

    second = compute_policy_fingerprint(str(tmp_path))

    assert second != first

def test_first_scan_does_not_report_policy_changed(tmp_path):
    (tmp_path / "source.py").write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    _, delta = inspect_repository_delta(str(tmp_path))

    assert delta.policy_changed is False

def test_gitignore_change_reports_policy_changed(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")

    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("", encoding="utf-8")

    previous, _ = inspect_repository_delta(str(tmp_path))

    gitignore.write_text("*.log\n", encoding="utf-8")

    _, delta = inspect_repository_delta(
        str(tmp_path),
        previous=previous,
    )

    assert delta.policy_changed is True
    assert "source.py" in delta.unchanged
    assert ".gitignore" in delta.modified

def test_policy_fingerprint_changes_when_policy_version_changes(
    tmp_path,
    monkeypatch,
):
    first = compute_policy_fingerprint(str(tmp_path))

    monkeypatch.setattr(
        "core.repo_ignore.REPO_IGNORE_POLICY_VERSION",
        "repo_ignore_v2",
    )

    second = compute_policy_fingerprint(str(tmp_path))

    assert second != first

def test_policy_fingerprint_includes_hard_excludes(
    tmp_path,
    monkeypatch,
):
    first = compute_policy_fingerprint(str(tmp_path))

    monkeypatch.setattr(
        "core.repo_ignore.ROOT_ONLY_HARD_EXCLUDES",
        frozenset({"different-directory"}),
    )

    second = compute_policy_fingerprint(str(tmp_path))

    assert second != first

def test_persistent_manifest_second_scan_reuses_all_hashes(tmp_path):
    first = tmp_path / "a.py"
    second = tmp_path / "b.py"

    first.write_text("a = 1\n", encoding="utf-8")
    second.write_text("b = 2\n", encoding="utf-8")

    initial_manifest, initial_delta = inspect_repository_delta(
        str(tmp_path)
    )

    assert initial_delta.added == ("a.py", "b.py")
    assert initial_delta.hashes_computed == 2

    save_repository_manifest(
        str(tmp_path),
        initial_manifest,
    )

    loaded = load_repository_manifest(str(tmp_path))

    assert loaded == initial_manifest

    current_manifest, current_delta = inspect_repository_delta(
        str(tmp_path),
        previous=loaded,
    )

    assert current_delta.added == ()
    assert current_delta.modified == ()
    assert current_delta.deleted == ()
    assert current_delta.unchanged == ("a.py", "b.py")
    assert current_delta.hashes_computed == 0
    assert current_delta.hashes_reused == 2
    assert current_delta.policy_changed is False
    assert current_manifest == initial_manifest

def test_persistent_manifest_rehashes_only_modified_file(tmp_path):
    first = tmp_path / "a.py"
    second = tmp_path / "b.py"

    first.write_text("a = 1\n", encoding="utf-8")
    second.write_text("b = 2\n", encoding="utf-8")

    initial_manifest, _ = inspect_repository_delta(str(tmp_path))
    save_repository_manifest(str(tmp_path), initial_manifest)

    first.write_text(
        "a = 1000\n",
        encoding="utf-8",
    )

    loaded = load_repository_manifest(str(tmp_path))
    assert loaded is not None

    current_manifest, delta = inspect_repository_delta(
        str(tmp_path),
        previous=loaded,
    )

    assert delta.added == ()
    assert delta.modified == ("a.py",)
    assert delta.deleted == ()
    assert delta.unchanged == ("b.py",)
    assert delta.hashes_computed == 1
    assert delta.hashes_reused == 1

    save_repository_manifest(str(tmp_path), current_manifest)

    reloaded = load_repository_manifest(str(tmp_path))
    assert reloaded == current_manifest

def test_persistent_manifest_records_deleted_file(tmp_path):
    removed = tmp_path / "removed.py"
    kept = tmp_path / "kept.py"

    removed.write_text("removed = True\n", encoding="utf-8")
    kept.write_text("kept = True\n", encoding="utf-8")

    initial_manifest, _ = inspect_repository_delta(str(tmp_path))
    save_repository_manifest(str(tmp_path), initial_manifest)

    removed.unlink()

    loaded = load_repository_manifest(str(tmp_path))
    assert loaded is not None

    current_manifest, delta = inspect_repository_delta(
        str(tmp_path),
        previous=loaded,
    )

    assert delta.deleted == ("removed.py",)
    assert delta.unchanged == ("kept.py",)
    assert delta.hashes_computed == 0
    assert delta.hashes_reused == 1

    save_repository_manifest(str(tmp_path), current_manifest)

    final_manifest = load_repository_manifest(str(tmp_path))
    assert final_manifest is not None
    assert "removed.py" not in final_manifest.files

def test_persistent_policy_change_reuses_unaffected_hashes(tmp_path):
    source = tmp_path / "source.py"
    ignored_candidate = tmp_path / "generated.log"
    gitignore = tmp_path / ".gitignore"

    source.write_text("value = 1\n", encoding="utf-8")
    ignored_candidate.write_text("generated\n", encoding="utf-8")
    gitignore.write_text("", encoding="utf-8")

    initial_manifest, _ = inspect_repository_delta(str(tmp_path))
    save_repository_manifest(str(tmp_path), initial_manifest)

    gitignore.write_text(
        "*.log\n",
        encoding="utf-8",
    )

    loaded = load_repository_manifest(str(tmp_path))
    assert loaded is not None

    _, delta = inspect_repository_delta(
        str(tmp_path),
        previous=loaded,
    )

    assert delta.policy_changed is True
    assert "generated.log" in delta.deleted
    assert "source.py" in delta.unchanged
    assert ".gitignore" in delta.modified

    # source.py reuses its hash; only .gitignore needs rehashing.
    assert delta.hashes_computed == 1
    assert delta.hashes_reused == 1

def test_successful_save_leaves_no_temporary_manifest(tmp_path):
    manifest, _ = inspect_repository_delta(str(tmp_path))

    path = save_repository_manifest(
        str(tmp_path),
        manifest,
    )

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    assert path.is_file()
    assert not temporary_path.exists()

def test_manifest_path_is_stable_when_repository_membership_changes(
    tmp_path,
):
    first_path = get_repository_manifest_path(
        str(tmp_path)
    )

    created = tmp_path / "created.py"
    created.write_text(
        "created = True\n",
        encoding="utf-8",
    )

    second_path = get_repository_manifest_path(
        str(tmp_path)
    )

    created.unlink()

    third_path = get_repository_manifest_path(
        str(tmp_path)
    )

    assert second_path == first_path
    assert third_path == first_path


def test_inspect_delta_reuses_supplied_inventory_without_scanning(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    inventory = create_repository_inventory(tmp_path)

    def forbidden_scan(_root):
        raise AssertionError(
            "supplied inventory must prevent a repository rescan"
        )

    monkeypatch.setattr(
        repo_librarian,
        "_walk_policy_files",
        forbidden_scan,
    )

    manifest, delta = inspect_repository_delta(
        str(tmp_path),
        inventory=inventory,
    )

    assert tuple(manifest.files) == ("source.py",)
    assert delta.added == ("source.py",)
    assert delta.hashes_computed == 1


def test_inspect_delta_rejects_supplied_inventory_root_mismatch(
    tmp_path,
):
    first_repo = tmp_path / "first"
    second_repo = tmp_path / "second"
    first_repo.mkdir()
    second_repo.mkdir()
    (first_repo / "source.py").write_text(
        "value = 1\n",
        encoding="utf-8",
    )
    inventory = create_repository_inventory(first_repo)

    with pytest.raises(
        ValueError,
        match="belongs to another repository",
    ):
        inspect_repository_delta(
            str(second_repo),
            inventory=inventory,
        )


def test_manifest_load_result_distinguishes_missing_manifest(
    manifest_result_repo,
):
    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_MISSING
    assert result.manifest is None
    assert result.present is False
    assert result.reason == "manifest_missing"
    assert result.bytes_read == 0


def test_manifest_load_result_loads_valid_bound_manifest(
    manifest_result_repo,
):
    manifest = _bound_manifest(manifest_result_repo)
    path = save_repository_manifest(
        str(manifest_result_repo),
        manifest,
    )
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_LOADED
    assert result.manifest == manifest
    assert result.present is True
    assert result.reason == "manifest_loaded"
    assert result.bytes_read == len(before)
    assert result.legacy_binding is False
    assert path.read_bytes() == before


def test_manifest_load_result_distinguishes_invalid_json(
    manifest_result_repo,
):
    path = get_repository_manifest_path(str(manifest_result_repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_INVALID
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_json_invalid"
    assert path.read_bytes() == before


def test_manifest_load_result_distinguishes_root_mismatch(
    manifest_result_repo,
):
    other_repo = manifest_result_repo.parent / "other-root"
    other_repo.mkdir()
    payload = _bound_manifest_payload(
        manifest_result_repo,
        repo_root=str(other_repo.resolve()),
    )
    path = _write_manifest_payload(manifest_result_repo, payload)
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_ROOT_MISMATCH
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_root_mismatch"
    assert path.read_bytes() == before


def test_manifest_load_result_distinguishes_repository_mismatch(
    manifest_result_repo,
):
    other_repo = manifest_result_repo.parent / "other-repository"
    other_repo.mkdir()
    payload = _bound_manifest_payload(
        manifest_result_repo,
        repository_id=derive_repository_id(other_repo),
    )
    path = _write_manifest_payload(manifest_result_repo, payload)
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_REPOSITORY_MISMATCH
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_repository_mismatch"
    assert path.read_bytes() == before


def test_manifest_load_result_distinguishes_epoch_mismatch(
    manifest_result_repo,
):
    payload = _bound_manifest_payload(
        manifest_result_repo,
        architecture_epoch=1,
    )
    path = _write_manifest_payload(manifest_result_repo, payload)
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_EPOCH_MISMATCH
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_epoch_mismatch"
    assert path.read_bytes() == before


def test_manifest_load_result_distinguishes_scope_mismatch(
    manifest_result_repo,
):
    other_repo = manifest_result_repo.parent / "other-scope"
    other_repo.mkdir()
    payload = _bound_manifest_payload(
        manifest_result_repo,
        index_scope=build_code_index_scope(other_repo),
    )
    path = _write_manifest_payload(manifest_result_repo, payload)
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_SCOPE_MISMATCH
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_scope_mismatch"
    assert path.read_bytes() == before


def test_manifest_load_result_distinguishes_unsupported_schema(
    manifest_result_repo,
):
    payload = _bound_manifest_payload(
        manifest_result_repo,
        version="repository_manifest_v999",
    )
    path = _write_manifest_payload(manifest_result_repo, payload)
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_UNSUPPORTED_SCHEMA
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_schema_unsupported"
    assert path.read_bytes() == before


def test_manifest_load_result_enforces_bounded_read(
    manifest_result_repo,
    monkeypatch,
):
    monkeypatch.setattr(
        index_manifest_module,
        "MAX_MANIFEST_BYTES",
        64,
    )
    path = get_repository_manifest_path(str(manifest_result_repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    oversized = b"x" * 65
    path.write_bytes(oversized)

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_INVALID
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_read_bound_exceeded"
    assert result.bytes_read <= index_manifest_module.MAX_MANIFEST_BYTES
    assert path.read_bytes() == oversized


def test_manifest_load_result_rejects_duplicate_json_key(
    manifest_result_repo,
):
    payload = _bound_manifest_payload(manifest_result_repo)
    serialized = json.dumps(payload, sort_keys=True)
    duplicate = (
        serialized[:-1]
        + f', "version": {json.dumps(MANIFEST_VERSION)}}}'
    )
    path = get_repository_manifest_path(str(manifest_result_repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(duplicate, encoding="utf-8")
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_INVALID
    assert result.manifest is None
    assert result.reason == "manifest_json_invalid"
    assert path.read_bytes() == before


def test_manifest_load_result_rejects_duplicate_file_path_key(
    manifest_result_repo,
):
    payload = _bound_manifest_payload(manifest_result_repo)
    file_record = json.dumps(payload["files"]["app.py"], sort_keys=True)
    duplicate_files = (
        "{"
        f'"version": {json.dumps(payload["version"])},'
        f'"repo_root": {json.dumps(payload["repo_root"])},'
        '"policy_fingerprint": '
        f'{json.dumps(payload["policy_fingerprint"])},'
        f'"repository_id": {json.dumps(payload["repository_id"])},'
        '"architecture_epoch": null,'
        f'"index_scope": {json.dumps(payload["index_scope"])},'
        '"files": {'
        f'"app.py": {file_record},'
        f'"app.py": {file_record}'
        "}"
        "}"
    )
    path = get_repository_manifest_path(str(manifest_result_repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(duplicate_files, encoding="utf-8")
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_INVALID
    assert result.manifest is None
    assert result.reason == "manifest_json_invalid"
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "relative_path",
    (
        pytest.param("./app.py", id="explicit-current-directory"),
        pytest.param("nested//app.py", id="duplicate-separator"),
        pytest.param("nested/", id="trailing-separator"),
        pytest.param("app.py:alternate-data", id="colon-or-ads"),
        pytest.param("control\x1f.py", id="c0-control-character"),
        pytest.param("control\x7f.py", id="delete-control-character"),
    ),
)
def test_manifest_load_result_rejects_noncanonical_file_path_spellings(
    manifest_result_repo,
    relative_path,
):
    payload = _bound_manifest_payload(manifest_result_repo)
    fingerprint = payload["files"].pop("app.py")
    payload["files"][relative_path] = fingerprint
    path = _write_manifest_payload(manifest_result_repo, payload)
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_INVALID
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_payload_invalid"
    assert path.read_bytes() == before


def test_manifest_load_result_contains_huge_integer_parse_failure(
    manifest_result_repo,
):
    payload = _bound_manifest_payload(manifest_result_repo)
    payload_without_files = {
        key: value
        for key, value in payload.items()
        if key != "files"
    }
    prefix = json.dumps(payload_without_files, sort_keys=True)[:-1]
    raw = (
        prefix
        + ', "files": {"app.py": {"size": '
        + ("9" * 10_000)
        + ', "mtime_ns": 1, "sha256": "'
        + VALID_SHA256
        + '"}}}'
    )
    path = get_repository_manifest_path(str(manifest_result_repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_INVALID
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_json_invalid"
    assert path.read_bytes() == before


def test_manifest_load_result_contains_deep_nesting_parse_failure(
    manifest_result_repo,
):
    payload = _bound_manifest_payload(manifest_result_repo)
    prefix = json.dumps(payload, sort_keys=True)[:-1]
    raw = (
        prefix
        + ', "untrusted_extension": '
        + ("[" * 2_000)
        + "0"
        # Deliberately leave one deeply nested array unterminated.
        + ("]" * 1_999)
        + "}"
    )
    path = get_repository_manifest_path(str(manifest_result_repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    before = path.read_bytes()

    result = _load_result(manifest_result_repo)

    assert result.status == MANIFEST_LOAD_INVALID
    assert result.manifest is None
    assert result.present is True
    assert result.reason == "manifest_json_invalid"
    assert path.read_bytes() == before


def test_indexable_only_requires_supplied_inventory(tmp_path):
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="requires a supplied inventory",
    ):
        inspect_repository_delta(
            str(tmp_path),
            indexable_only=True,
        )


def test_indexable_only_rejects_secret_like_sources_without_extra_walk(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "safe.py").write_text("safe = True\n", encoding="utf-8")
    (repo / "password.py").write_text(
        "password = 'not-read'\n",
        encoding="utf-8",
    )
    (repo / "api_secret.py").write_text(
        "secret = 'not-read'\n",
        encoding="utf-8",
    )

    real_walk = repo_librarian._walk_policy_files
    walk_count = 0

    def counting_walk(root):
        nonlocal walk_count
        walk_count += 1
        yield from real_walk(root)

    monkeypatch.setattr(
        repo_librarian,
        "_walk_policy_files",
        counting_walk,
    )
    inventory = create_repository_inventory(repo)

    manifest, delta = inspect_repository_delta(
        str(repo),
        inventory=inventory,
        indexable_only=True,
    )

    assert walk_count == 1
    assert tuple(manifest.files) == ("safe.py",)
    assert delta.added == ("safe.py",)
    assert "password.py" not in manifest.files
    assert "api_secret.py" not in manifest.files


def test_indexable_only_rejects_post_inventory_symlink_escape_without_walk(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "source.py"
    source.write_text("safe = True\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("outside = True\n", encoding="utf-8")

    real_walk = repo_librarian._walk_policy_files
    walk_count = 0

    def counting_walk(root):
        nonlocal walk_count
        walk_count += 1
        yield from real_walk(root)

    monkeypatch.setattr(
        repo_librarian,
        "_walk_policy_files",
        counting_walk,
    )
    inventory = create_repository_inventory(repo)
    source.unlink()
    try:
        source.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(
        PermissionError,
        match="failed safety validation",
    ):
        inspect_repository_delta(
            str(repo),
            inventory=inventory,
            indexable_only=True,
        )

    assert walk_count == 1


def test_indexable_only_excludes_legacy_noncanonical_deletion_authority(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    safe = repo / "safe.py"
    newly_ignored = repo / "newly_ignored.py"
    password = repo / "password.py"
    binary = repo / "notes.bin"
    gitignore = repo / ".gitignore"
    safe.write_text("safe = True\n", encoding="utf-8")
    newly_ignored.write_text("ignored = False\n", encoding="utf-8")
    password.write_text("password = 'legacy'\n", encoding="utf-8")
    binary.write_text("legacy metadata\n", encoding="utf-8")
    gitignore.write_text("", encoding="utf-8")

    legacy_all_members, _ = inspect_repository_delta(str(repo))
    assert {
        ".gitignore",
        "notes.bin",
        "password.py",
        "newly_ignored.py",
        "safe.py",
    }.issubset(legacy_all_members.files)

    repository_id, index_scope = _manifest_binding(repo)
    previous = RepositoryManifest(
        version=legacy_all_members.version,
        repo_root=legacy_all_members.repo_root,
        policy_fingerprint=legacy_all_members.policy_fingerprint,
        files=legacy_all_members.files,
        repository_id=repository_id,
        architecture_epoch=None,
        index_scope=index_scope,
    )

    gitignore.write_text("newly_ignored.py\n", encoding="utf-8")
    inventory = create_repository_inventory(repo)
    manifest, delta = inspect_repository_delta(
        str(repo),
        previous=previous,
        inventory=inventory,
        indexable_only=True,
        repository_id=repository_id,
        architecture_epoch=None,
        index_scope=index_scope,
    )

    assert tuple(manifest.files) == ("safe.py",)
    assert delta.deleted == ("newly_ignored.py",)
    assert delta.unchanged == ("safe.py",)
    assert delta.previous_records_excluded == 3
    assert {
        ".gitignore",
        "notes.bin",
        "password.py",
    }.isdisjoint(delta.deleted)


def test_indexable_only_reuses_inventory_and_is_immutable_and_deterministic(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(
        index_manifest_module,
        "AGENT_DIR",
        tmp_path / "agent-output",
    )

    files = {
        "z.py": "z = 2\n",
        "a.py": "a = 1\n",
        ".gitignore": "",
        ".cattusignore": "",
        "notes.bin": "unsupported\n",
        "requirements.txt": "pytest\n",
        "session_log.txt": "sensitive\n",
        "memory_file_for_agent.txt": "sensitive\n",
        "postgres_auth.txt": "sensitive\n",
        ".env.json": '{"token": "secret"}\n',
    }
    for relative_path, content in files.items():
        (repo / relative_path).write_text(content, encoding="utf-8")

    real_walk = repo_librarian._walk_policy_files
    walk_count = 0

    def counting_walk(root):
        nonlocal walk_count
        walk_count += 1
        yield from real_walk(root)

    monkeypatch.setattr(
        repo_librarian,
        "_walk_policy_files",
        counting_walk,
    )
    inventory = create_repository_inventory(repo)
    inventory_snapshot = (
        inventory.entries,
        inventory.indexable_entries,
        inventory.ignore_policy_fingerprint,
        inventory.traversal_count,
        inventory.walk_sites,
    )
    repository_id, index_scope = _manifest_binding(repo)

    applied, cold_delta = inspect_repository_delta(
        str(repo),
        inventory=inventory,
        indexable_only=True,
        repository_id=repository_id,
        architecture_epoch=None,
        index_scope=index_scope,
    )

    assert walk_count == 1
    assert tuple(applied.files) == ("a.py", "z.py")
    assert cold_delta.added == ("a.py", "z.py")
    assert applied.policy_fingerprint == inventory.ignore_policy_fingerprint

    excluded = {
        ".gitignore",
        ".cattusignore",
        "notes.bin",
        "requirements.txt",
        "session_log.txt",
        "memory_file_for_agent.txt",
        "postgres_auth.txt",
        ".env.json",
    }
    assert excluded.isdisjoint(applied.files)
    assert excluded.isdisjoint(cold_delta.added)

    path = save_repository_manifest(str(repo), applied)
    applied_bytes = path.read_bytes()
    applied_snapshot = copy.deepcopy(applied)

    observed, unchanged_delta = inspect_repository_delta(
        str(repo),
        previous=applied,
        inventory=inventory,
        indexable_only=True,
        repository_id=repository_id,
        architecture_epoch=None,
        index_scope=index_scope,
    )
    repeated, repeated_delta = inspect_repository_delta(
        str(repo),
        previous=applied,
        inventory=inventory,
        indexable_only=True,
        repository_id=repository_id,
        architecture_epoch=None,
        index_scope=index_scope,
    )

    assert walk_count == 1
    assert observed is not applied
    assert observed == repeated == applied
    assert unchanged_delta == repeated_delta
    assert unchanged_delta.added == ()
    assert unchanged_delta.modified == ()
    assert unchanged_delta.deleted == ()
    assert unchanged_delta.unchanged == ("a.py", "z.py")
    assert unchanged_delta.hashes_computed == 0
    assert unchanged_delta.hashes_reused == 2
    assert applied == applied_snapshot
    assert path.read_bytes() == applied_bytes
    assert inventory_snapshot == (
        inventory.entries,
        inventory.indexable_entries,
        inventory.ignore_policy_fingerprint,
        inventory.traversal_count,
        inventory.walk_sites,
    )
