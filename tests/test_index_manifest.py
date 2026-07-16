import json
from pathlib import Path
import hashlib
import os
import shutil
import pytest

from core.index_manifest import (
    MANIFEST_VERSION,
    FileFingerprint,
    RepositoryManifest,
    get_repository_manifest_path,
    load_repository_manifest,
    save_repository_manifest,
    fingerprint_file,
    inspect_repository_delta
)


VALID_SHA256 = "a" * 64


def _make_manifest(repo_path: Path) -> RepositoryManifest:
    return RepositoryManifest(
        version=MANIFEST_VERSION,
        repo_root=str(repo_path.resolve()),
        policy_fingerprint="policy-v1",
        files={
            "core/example.py": FileFingerprint(
                size=12,
                mtime_ns=123456789,
                sha256=VALID_SHA256,
            )
        },
    )


def test_missing_manifest_returns_none(tmp_path):
    assert load_repository_manifest(str(tmp_path)) is None


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