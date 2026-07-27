from pathlib import Path

import pytest

from core.repository_identity import (
    build_code_index_scope,
    build_repository_storage_key,
    is_code_index_scope,
)

def test_code_index_scope_survives_repository_changes(tmp_path):
    scope_before = build_code_index_scope(tmp_path)

    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")

    scope_after_add = build_code_index_scope(tmp_path)

    source.write_text("value = 2\n", encoding="utf-8")
    scope_after_modify = build_code_index_scope(tmp_path)

    source.rename(tmp_path / "renamed.py")
    scope_after_rename = build_code_index_scope(tmp_path)

    (tmp_path / "renamed.py").unlink()
    scope_after_delete = build_code_index_scope(tmp_path)

    assert scope_after_add == scope_before
    assert scope_after_modify == scope_before
    assert scope_after_rename == scope_before
    assert scope_after_delete == scope_before

def test_same_named_repositories_have_distinct_scopes(tmp_path):
    repo_a = tmp_path / "a" / "project"
    repo_b = tmp_path / "b" / "project"

    repo_a.mkdir(parents=True)
    repo_b.mkdir(parents=True)

    assert (
        build_code_index_scope(repo_a)
        != build_code_index_scope(repo_b)
    )

def test_path_aliases_resolve_to_same_scope(tmp_path):
    direct = build_code_index_scope(tmp_path)
    aliased = build_code_index_scope(
        tmp_path / "." / "nested" / ".."
    )

    assert aliased == direct

def test_code_index_scope_has_expected_format(tmp_path):
    scope = build_code_index_scope(tmp_path)

    assert scope.startswith("code-index-")
    assert is_code_index_scope(scope) is True

def test_arbitrary_project_tag_is_not_code_index_scope():
    assert is_code_index_scope("my-project") is False
    assert is_code_index_scope("shared") is False
    assert is_code_index_scope(None) is False

def test_missing_repository_is_rejected(tmp_path):
    with pytest.raises(NotADirectoryError):
        build_code_index_scope(tmp_path / "missing")

def test_manifest_uses_shared_storage_identity(tmp_path):
    from core.index_manifest import (
        get_repository_manifest_path,
    )

    path = get_repository_manifest_path(str(tmp_path))
    expected_key = build_repository_storage_key(tmp_path)

    assert path.parent.name == expected_key