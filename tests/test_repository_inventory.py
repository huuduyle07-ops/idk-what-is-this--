from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import core.code_dna as code_dna_module
from core.repo_librarian import build_repo_manifest
from core.repository_inventory import (
    CANONICAL_WALK_SITE,
    RepositoryEntry,
    create_repository_inventory,
    repository_inventory_from_entries,
    validate_repository_inventory,
)


def _write(
    root: Path,
    relative_path: str,
    content: str = "",
) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _relative_paths(entries) -> tuple[str, ...]:
    return tuple(
        entry.relative_path.as_posix()
        for entry in entries
    )


def test_shared_scan_is_deterministic_and_filtering_is_stable(
    tmp_path,
):
    _write(tmp_path, "b.py", "b = 2\n")
    _write(tmp_path, "a.py", "a = 1\n")
    _write(tmp_path, "notes.bin", "not indexable\n")
    _write(tmp_path, "requirements.txt", "pytest\n")

    first = create_repository_inventory(tmp_path)
    second = create_repository_inventory(tmp_path)

    assert first.traversal_count == 1
    assert first.walk_sites == (CANONICAL_WALK_SITE,)
    assert _relative_paths(first.entries) == (
        "a.py",
        "b.py",
        "notes.bin",
        "requirements.txt",
    )
    assert first.entry_pairs == second.entry_pairs
    assert _relative_paths(first.indexable_entries) == (
        "a.py",
        "b.py",
    )
    assert _relative_paths(first.entries_for_query(None)) == (
        "a.py",
        "b.py",
        "notes.bin",
    )
    assert _relative_paths(
        first.entries_for_query("dependency install")
    ) == (
        "a.py",
        "b.py",
        "notes.bin",
        "requirements.txt",
    )


def test_manifest_validates_supplied_inventory_before_missing_root_fallback(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo, "app.py", "x = 1\n")
    inventory = create_repository_inventory(repo)

    with pytest.raises(
        ValueError,
        match="belongs to another repository",
    ):
        build_repo_manifest(
            str(tmp_path / "missing"),
            inventory=inventory,
        )


def test_code_dna_validates_supplied_inventory_before_missing_root_fallback(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo, "app.py", "x = 1\n")
    inventory = create_repository_inventory(repo)

    with pytest.raises(
        ValueError,
        match="belongs to another repository",
    ):
        code_dna_module.compute_dna(
            str(tmp_path / "missing"),
            inventory=inventory,
        )


def test_inventory_obeys_ignore_policy_and_hard_excludes(
    tmp_path,
):
    _write(tmp_path, "kept.py", "kept = True\n")
    _write(tmp_path, "ignored.py", "ignored = True\n")
    _write(tmp_path, "generated/output.py", "generated = True\n")
    _write(tmp_path, ".tmp/transient.py", "transient = True\n")
    _write(tmp_path, ".git/object.py", "git = True\n")
    _write(
        tmp_path,
        "vendor/node_modules/pkg/index.js",
        "export default 1;\n",
    )
    _write(tmp_path, ".gitignore", "ignored.py\n")
    _write(tmp_path, ".cattusignore", "generated/\n")

    inventory = create_repository_inventory(tmp_path)
    paths = set(_relative_paths(inventory.entries))

    assert "kept.py" in paths
    assert "ignored.py" not in paths
    assert "generated/output.py" not in paths
    assert ".tmp/transient.py" not in paths
    assert ".git/object.py" not in paths
    assert "vendor/node_modules/pkg/index.js" not in paths


def test_inventory_and_entries_are_immutable(tmp_path):
    source = _write(tmp_path, "source.py", "value = 1\n")
    inventory = create_repository_inventory(tmp_path)

    assert isinstance(inventory.entries, tuple)
    assert isinstance(inventory.indexable_entries, tuple)
    assert inventory.entries == (
        RepositoryEntry(source.resolve(), Path("source.py")),
    )

    with pytest.raises(FrozenInstanceError):
        inventory.created_at = "changed"

    with pytest.raises(FrozenInstanceError):
        inventory.entries[0].relative_path = Path("changed.py")


def test_duplicate_canonical_paths_fail_validation(tmp_path):
    source = _write(tmp_path, "source.py", "value = 1\n")

    with pytest.raises(
        ValueError,
        match="duplicate canonical paths",
    ):
        repository_inventory_from_entries(
            tmp_path,
            [
                (source, Path("source.py")),
                (source, Path("source.py")),
            ],
        )


def test_outside_repository_paths_fail_validation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = _write(tmp_path, "outside.py", "outside = True\n")

    with pytest.raises(
        ValueError,
        match="outside the repository",
    ):
        repository_inventory_from_entries(
            repo,
            [(outside, Path("outside.py"))],
        )


def test_root_mismatch_fails_validation(tmp_path):
    first_repo = tmp_path / "first"
    second_repo = tmp_path / "second"
    first_repo.mkdir()
    second_repo.mkdir()
    _write(first_repo, "source.py", "value = 1\n")
    inventory = create_repository_inventory(first_repo)

    with pytest.raises(
        ValueError,
        match="belongs to another repository",
    ):
        validate_repository_inventory(second_repo, inventory)


def test_supplied_entries_require_order_and_are_not_mutated(
    tmp_path,
):
    a_path = _write(tmp_path, "a.py", "a = 1\n")
    b_path = _write(tmp_path, "b.py", "b = 2\n")
    entries = [
        (b_path, Path("b.py")),
        (a_path, Path("a.py")),
    ]
    before = list(entries)

    with pytest.raises(
        ValueError,
        match="deterministic path ordering",
    ):
        repository_inventory_from_entries(tmp_path, entries)

    assert entries == before

    ordered_entries = list(reversed(entries))
    ordered_before = list(ordered_entries)
    inventory = repository_inventory_from_entries(
        tmp_path,
        ordered_entries,
    )

    assert ordered_entries == ordered_before
    assert _relative_paths(inventory.entries) == (
        "a.py",
        "b.py",
    )


def test_diagnostics_are_deterministic_and_path_safe(tmp_path):
    _write(tmp_path, "source.py", "value = 1\n")
    inventory = create_repository_inventory(tmp_path)

    diagnostics = inventory.diagnostics(
        inventory_reuse={
            "project_map": True,
            "indexer": True,
            "manifest": False,
        }
    )

    assert diagnostics == {
        "repository_walks": 1,
        "walk_sites": [CANONICAL_WALK_SITE],
        "inventory_reuse": {
            "indexer": True,
            "manifest": False,
            "project_map": True,
        },
    }
    assert str(tmp_path.resolve()) not in repr(diagnostics)
