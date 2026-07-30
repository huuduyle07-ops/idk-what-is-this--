"""INDEX.1D.2A canonical physical repository identity tests."""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path

import pytest

import config
from core import repository_identity as identity_module
from core.lesson_store import repo_scope_id_for_path
from core.project_tag import build_project_tag
from core.repository_identity import (
    RepositoryIdentity,
    build_code_index_scope,
    build_repository_identity,
    build_repository_storage_key,
    canonicalize_repository_root,
    derive_repository_id,
    derive_repository_index_scope,
    derive_repository_storage_key,
    is_code_index_scope,
    is_repository_id,
    repository_identity_authority_matrix,
)


ROOT = Path(__file__).resolve().parent.parent
IDENTITY_SOURCE = ROOT / "core" / "repository_identity.py"
INDEXER_SOURCE = ROOT / "core" / "indexer.py"
RETRIEVER_SOURCE = ROOT / "core" / "retriever.py"
CODE_INDEX_SOURCE = ROOT / "database" / "code_index.py"


def _legacy_expected_values(repo_path: Path) -> tuple[str, str]:
    root = repo_path.expanduser().resolve()
    slug = root.name.casefold().replace(" ", "-")
    import re

    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-") or "repository"
    normalized = os.path.normcase(os.path.normpath(str(root)))
    digest = hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()
    return (
        f"{slug}-{digest[:16]}",
        f"code-index-{slug}-{digest[:32]}",
    )


def test_relative_and_absolute_paths_share_canonical_root(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(tmp_path)

    assert canonicalize_repository_root("repo") == (
        canonicalize_repository_root(repo)
    )


def test_canonical_root_is_absolute_and_normalizes_dotdot(tmp_path):
    repo = tmp_path / "repo"
    nested = repo / "nested"
    nested.mkdir(parents=True)

    canonical = canonicalize_repository_root(
        nested / ".." / "."
    )

    assert Path(canonical).is_absolute()
    assert canonical == str(repo.resolve())


def test_trailing_separator_does_not_change_identity(tmp_path):
    direct = derive_repository_id(tmp_path)
    with_separator = derive_repository_id(
        str(tmp_path) + os.sep
    )
    assert with_separator == direct


@pytest.mark.skipif(
    os.name != "nt",
    reason="Windows separator equivalence policy",
)
def test_windows_separator_forms_share_identity(tmp_path):
    normal = derive_repository_id(tmp_path)
    forward = derive_repository_id(
        str(tmp_path).replace("\\", "/")
    )
    assert forward == normal


@pytest.mark.skipif(
    os.name != "nt",
    reason="Windows case-folding policy",
)
def test_windows_path_case_does_not_change_identity(tmp_path):
    canonical = canonicalize_repository_root(tmp_path)
    assert derive_repository_id(canonical.swapcase()) == (
        derive_repository_id(canonical)
    )


@pytest.mark.skipif(
    os.name != "nt",
    reason="Windows normcase compatibility policy",
)
def test_windows_normcase_does_not_overcollapse_unicode_names(
    tmp_path,
):
    sharp_s = tmp_path / "Straße"
    double_s = tmp_path / "Strasse"
    sharp_s.mkdir()
    try:
        double_s.mkdir()
    except FileExistsError:
        pytest.skip(
            "filesystem treats sharp-s and double-s as equivalent"
        )

    assert derive_repository_id(sharp_s) != (
        derive_repository_id(double_s)
    )
    assert derive_repository_storage_key(sharp_s) == (
        _legacy_expected_values(sharp_s)[0]
    )
    assert derive_repository_storage_key(double_s) == (
        _legacy_expected_values(double_s)[0]
    )


@pytest.mark.skipif(
    os.name == "nt",
    reason="Case-sensitive platform policy",
)
def test_non_windows_identity_does_not_casefold(tmp_path):
    upper = tmp_path / "CaseRepo"
    lower = tmp_path / "caserepo"
    upper.mkdir()
    lower.mkdir()
    assert derive_repository_id(upper) != derive_repository_id(
        lower
    )


def test_symlink_and_real_path_share_identity(tmp_path):
    real = tmp_path / "real"
    link = tmp_path / "link"
    real.mkdir()
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    assert canonicalize_repository_root(link) == (
        canonicalize_repository_root(real)
    )
    assert derive_repository_id(link) == derive_repository_id(
        real
    )


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_or_non_directory_path_fails_deterministically(
    tmp_path,
    kind,
):
    candidate = tmp_path / kind
    if kind == "file":
        candidate.write_text("not a repo", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        canonicalize_repository_root(candidate)
    with pytest.raises(NotADirectoryError):
        derive_repository_id(candidate)


def test_same_root_produces_same_repository_id(tmp_path):
    first = derive_repository_id(tmp_path)
    second = derive_repository_id(tmp_path)
    assert first == second
    assert is_repository_id(first)


def test_different_roots_produce_different_repository_ids(
    tmp_path,
):
    repo_a = tmp_path / "a" / "repo"
    repo_b = tmp_path / "b" / "repo"
    repo_a.mkdir(parents=True)
    repo_b.mkdir(parents=True)
    assert derive_repository_id(repo_a) != derive_repository_id(
        repo_b
    )


def test_add_delete_and_rename_do_not_change_identity(tmp_path):
    before = build_repository_identity(tmp_path)
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    after_add = build_repository_identity(tmp_path)
    source.rename(tmp_path / "renamed.py")
    after_rename = build_repository_identity(tmp_path)
    (tmp_path / "renamed.py").unlink()
    after_delete = build_repository_identity(tmp_path)

    assert {
        before.repository_id,
        after_add.repository_id,
        after_rename.repository_id,
        after_delete.repository_id,
    } == {before.repository_id}
    assert {
        before.index_scope,
        after_add.index_scope,
        after_rename.index_scope,
        after_delete.index_scope,
    } == {before.index_scope}


def test_git_objects_changes_do_not_change_identity(tmp_path):
    objects = tmp_path / ".git" / "objects"
    objects.mkdir(parents=True)
    before = derive_repository_id(tmp_path)
    (objects / "aa").mkdir()
    (objects / "aa" / "object").write_bytes(b"git object")
    after = derive_repository_id(tmp_path)
    assert after == before


def test_large_architecture_change_does_not_change_physical_id(
    tmp_path,
):
    web = tmp_path / "web"
    web.mkdir()
    (web / "app.py").write_text("web = True\n", encoding="utf-8")
    before = derive_repository_id(tmp_path)

    (web / "app.py").unlink()
    web.rmdir()
    cli = tmp_path / "cli"
    cli.mkdir()
    for index in range(50):
        (cli / f"command_{index}.py").write_text(
            f"command = {index}\n",
            encoding="utf-8",
        )

    assert derive_repository_id(tmp_path) == before


def test_identity_derivation_performs_zero_repository_walks(
    tmp_path,
    monkeypatch,
):
    def forbidden_walk(*_args, **_kwargs):
        raise AssertionError("identity must not call os.walk")

    monkeypatch.setattr(os, "walk", forbidden_walk)
    identity = build_repository_identity(tmp_path)
    assert identity.repository_id


def test_identity_derivation_reads_no_source_contents(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.py"
    source.write_text("secret-shaped source", encoding="utf-8")

    def forbidden_read(*_args, **_kwargs):
        raise AssertionError("identity must not read source files")

    monkeypatch.setattr(Path, "read_text", forbidden_read)
    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    monkeypatch.setattr(Path, "open", forbidden_read)

    assert derive_repository_id(tmp_path)


def test_identity_record_is_derived_from_one_canonicalization(
    tmp_path,
    monkeypatch,
):
    original = identity_module.canonicalize_repository_root
    calls = []

    def counting_canonicalization(repo_path):
        calls.append(repo_path)
        return original(repo_path)

    monkeypatch.setattr(
        identity_module,
        "canonicalize_repository_root",
        counting_canonicalization,
    )

    identity = identity_module.build_repository_identity(
        tmp_path
    )

    assert identity.repository_id
    assert len(calls) == 1


def test_index_scope_is_never_empty_or_none(tmp_path):
    identity = build_repository_identity(tmp_path)
    assert identity.index_scope
    assert identity.index_scope is not None
    assert is_code_index_scope(identity.index_scope)


def test_project_tag_none_is_semantic_metadata_only(tmp_path):
    identity = build_repository_identity(
        tmp_path,
        project_tag=None,
    )
    assert isinstance(identity, RepositoryIdentity)
    assert identity.project_tag is None
    assert identity.index_scope


def test_project_tag_does_not_change_physical_authority(tmp_path):
    unlabeled = build_repository_identity(
        tmp_path,
        project_tag=None,
    )
    labeled = build_repository_identity(
        tmp_path,
        project_tag="Human Project Name",
    )
    assert labeled.project_tag == "Human Project Name"
    assert labeled.repository_id == unlabeled.repository_id
    assert labeled.storage_key == unlabeled.storage_key
    assert labeled.index_scope == unlabeled.index_scope


def test_epochs_keep_repository_id_and_change_scope(tmp_path):
    epoch_one = build_repository_identity(
        tmp_path,
        architecture_epoch=1,
    )
    epoch_two = build_repository_identity(
        tmp_path,
        architecture_epoch=2,
    )
    assert epoch_one.repository_id == epoch_two.repository_id
    assert epoch_one.storage_key == epoch_two.storage_key
    assert epoch_one.index_scope != epoch_two.index_scope
    assert is_code_index_scope(epoch_one.index_scope)
    assert is_code_index_scope(epoch_two.index_scope)


def test_epoch_integer_and_equivalent_string_are_stable(tmp_path):
    assert derive_repository_index_scope(
        tmp_path,
        architecture_epoch=1,
    ) == derive_repository_index_scope(
        tmp_path,
        architecture_epoch="1",
    )


@pytest.mark.parametrize(
    "epoch",
    ["", "   ", -1, True, object()],
)
def test_invalid_epoch_is_rejected(tmp_path, epoch):
    with pytest.raises(ValueError):
        derive_repository_index_scope(
            tmp_path,
            architecture_epoch=epoch,
        )


def test_existing_storage_and_default_scope_formats_are_compatible(
    tmp_path,
):
    expected_storage, expected_scope = _legacy_expected_values(
        tmp_path
    )
    assert derive_repository_storage_key(tmp_path) == (
        expected_storage
    )
    assert build_repository_storage_key(tmp_path) == (
        expected_storage
    )
    assert derive_repository_index_scope(tmp_path) == expected_scope
    assert build_code_index_scope(tmp_path) == expected_scope


def test_long_repository_names_produce_bounded_distinct_storage_keys(
    tmp_path,
):
    repo_a = tmp_path / ("a" * 119 + "x")
    repo_b = tmp_path / ("a" * 119 + "y")
    repo_a.mkdir()
    repo_b.mkdir()

    key_a = derive_repository_storage_key(repo_a)
    key_b = derive_repository_storage_key(repo_b)

    assert len(key_a) <= 128
    assert len(key_b) <= 128
    assert key_a != key_b
    assert repo_scope_id_for_path(repo_a) == key_a
    assert repo_scope_id_for_path(repo_b) == key_b


def test_build_project_tag_default_delegates_without_walk(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "core.project_tag.os.walk",
        lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(AssertionError("project tag must not walk")),
    )
    assert build_project_tag(str(tmp_path)) == (
        build_repository_storage_key(tmp_path)
    )


def test_explicit_project_tag_sanitization_is_compatible(tmp_path):
    assert build_project_tag(
        str(tmp_path),
        "  My Human_Label!!  ",
    ) == "my-humanlabel"


def test_get_agent_dir_is_path_derived_and_walk_free(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    app_root = tmp_path / "application"
    agent_root = tmp_path / "agent"
    repo.mkdir()
    app_root.mkdir()
    monkeypatch.setattr(config, "BASE_DIR", app_root)
    monkeypatch.setattr(config, "AGENT_DIR", agent_root)
    monkeypatch.setattr(
        os,
        "walk",
        lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(AssertionError("get_agent_dir must not walk")),
    )

    result = config.get_agent_dir(str(repo))
    assert result == (
        agent_root / build_repository_storage_key(repo)
    )
    assert result.is_dir()


def test_get_agent_dir_preserves_application_root_alias(
    tmp_path,
    monkeypatch,
):
    app_root = tmp_path / "application"
    agent_root = tmp_path / "agent"
    app_root.mkdir()
    monkeypatch.setattr(config, "BASE_DIR", app_root)
    monkeypatch.setattr(config, "AGENT_DIR", agent_root)
    assert config.get_agent_dir(str(app_root)) == agent_root


def test_lesson_repo_scope_uses_canonical_storage_key(tmp_path):
    assert repo_scope_id_for_path(tmp_path) == (
        build_repository_storage_key(tmp_path)
    )


def test_authority_matrix_separates_label_from_scope():
    rows = {
        row["field"]: row
        for row in repository_identity_authority_matrix()
    }
    assert rows["project_tag"]["may_be_none"] is True
    assert (
        rows["project_tag"][
            "may_scope_db_writes_or_deletes"
        ]
        is False
    )
    assert (
        rows["index_scope"][
            "may_scope_db_writes_or_deletes"
        ]
        is True
    )
    assert all(
        row["may_depend_on_inventory"] is False
        for row in rows.values()
    )


def test_identity_input_is_not_mutated(tmp_path):
    path_parts = [str(tmp_path)]
    before = copy.deepcopy(path_parts)
    build_repository_identity(path_parts[0])
    assert path_parts == before


def test_identity_module_has_no_walk_rglob_git_or_runtime_calls():
    source = IDENTITY_SOURCE.read_text(encoding="utf-8")
    for forbidden in (
        "os.walk",
        ".rglob(",
        ".glob(",
        ".git",
        "index_repository(",
        "build_graph_from_repo(",
        "save_repository_manifest(",
        "reconcile_code_index_scope(",
        "requests.",
        "subprocess.",
    ):
        assert forbidden not in source


def test_production_code_index_callers_use_strict_facade():
    indexer_source = INDEXER_SOURCE.read_text(encoding="utf-8")
    retriever_source = RETRIEVER_SOURCE.read_text(
        encoding="utf-8"
    )
    facade_source = CODE_INDEX_SOURCE.read_text(
        encoding="utf-8"
    )

    for production_source in (
        indexer_source,
        retriever_source,
    ):
        assert "from database.code_index import" in (
            production_source
        )
        assert "from database.memory import" not in (
            production_source
        )

    assert "project_tag=index_scope" not in retriever_source
    assert "_require_index_scope" in facade_source
    assert "project_tag=scope" in facade_source
    assert "os.walk" not in facade_source
