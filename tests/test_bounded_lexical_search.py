"""CTX.SEARCH.1 bounded lexical-search safety and determinism tests."""

from __future__ import annotations

import ast
import copy
import os
from pathlib import Path

import pytest

from core.bounded_lexical_search import (
    EXECUTION_AUTHORITY,
    MAX_LEXICAL_TERMS,
    execute_bounded_lexical_search,
)
from core.file_candidate_selector import build_lexical_search_request
from core.repository_inventory import create_repository_inventory


def _write(root: Path, relative: str, content: str | bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _run(root: Path, terms=("needle",), **kwargs):
    inventory = create_repository_inventory(root)
    request = build_lexical_search_request(terms)
    return execute_bounded_lexical_search(root, inventory, request, **kwargs)


def test_literal_term_returns_repository_relative_path_and_line(tmp_path: Path) -> None:
    _write(tmp_path, "core/indexer.py", "first\ntrusted_completion = True\n")

    result = _run(tmp_path, ("trusted_completion",))

    assert result.status == "search_complete"
    assert [(item.path, item.line_number) for item in result.matches] == [
        ("core/indexer.py", 2)
    ]
    match = result.matches[0].as_dict()
    assert match["match_kind"] == "literal"
    assert match["file_understanding"] == "raw_text_only"
    assert match["execution_authority"] == EXECUTION_AUTHORITY
    assert match["read_authority"] is match["write_authority"] is False


def test_case_sensitive_and_insensitive_modes_are_deterministic(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "Needle\nneedle\n")
    inventory = create_repository_inventory(tmp_path)
    insensitive_request = build_lexical_search_request(["needle"])
    sensitive_request = build_lexical_search_request(["needle"], case_sensitive=True)

    insensitive = execute_bounded_lexical_search(
        tmp_path, inventory, insensitive_request
    )
    sensitive = execute_bounded_lexical_search(tmp_path, inventory, sensitive_request)

    assert [item.line_number for item in insensitive.matches] == [1, 2]
    assert [item.line_number for item in sensitive.matches] == [2]
    assert insensitive == execute_bounded_lexical_search(
        tmp_path, inventory, insensitive_request
    )


def test_multiple_terms_preserve_request_priority(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "alpha first\nbeta second\n")
    inventory = create_repository_inventory(tmp_path)
    request = {
        "terms": ["beta", "alpha"],
        "include_paths": [],
        "exclude_paths": [],
        "max_matches": 200,
        "max_files": 40,
        "max_match_length": 240,
        "max_expansion_rounds": 2,
        "scope_mode": "safe_inventory",
        "safe_inventory_filter_required": True,
        "production_execution_authorized": False,
    }

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert [item.matched_term for item in result.matches] == ["beta", "alpha"]
    assert [item.term_priority for item in result.matches] == [0, 1]


def test_search_reuses_inventory_without_repository_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "app.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)

    def forbidden_walk(*args, **kwargs):  # pragma: no cover - called only on failure
        raise AssertionError("repository traversal is forbidden")

    monkeypatch.setattr(os, "walk", forbidden_walk)
    result = execute_bounded_lexical_search(
        tmp_path, inventory, build_lexical_search_request(["needle"])
    )

    assert result.matches
    assert result.diagnostics.inventory_membership_traversals == 0
    assert result.as_dict()["lexical_search"]["inventory_reused"] is True


def test_unsupported_readable_text_is_searchable_as_raw_text(tmp_path: Path) -> None:
    _write(tmp_path, "program.unknown-language", "prefix needle suffix\n")

    result = _run(tmp_path)

    assert len(result.matches) == 1
    assert result.matches[0].parser_support == "unsupported"
    assert result.matches[0].file_understanding == "raw_text_only"


@pytest.mark.parametrize(
    "relative, payload",
    [
        ("assets/blob.unknown", b"\x00needle\x01"),
        ("assets/blob.bin", b"needle"),
    ],
)
def test_binary_files_are_excluded_without_excerpts(
    tmp_path: Path, relative: str, payload: bytes
) -> None:
    _write(tmp_path, relative, payload)

    result = _run(tmp_path)

    assert result.matches == ()
    assert result.status == "binary_file_excluded"
    assert result.file_outcomes[0].status == "binary_file_excluded"
    assert result.file_outcomes[0].as_dict()["excerpt"] is None


@pytest.mark.parametrize("relative", [".env", "private.pem", "credentials/store.txt"])
def test_sensitive_files_never_return_excerpts(tmp_path: Path, relative: str) -> None:
    _write(tmp_path, relative, "needle=VERY_SECRET_VALUE\n")

    result = _run(tmp_path)

    assert result.matches == ()
    assert result.status == "sensitive_file_excluded"
    assert result.file_outcomes[0].as_dict()["excerpt"] is None
    assert "VERY_SECRET_VALUE" not in repr(result.as_dict())


def test_repository_root_mismatch_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    other = tmp_path / "other"
    repo.mkdir()
    other.mkdir()
    _write(repo, "app.py", "needle\n")
    inventory = create_repository_inventory(repo)

    result = execute_bounded_lexical_search(
        other, inventory, build_lexical_search_request(["needle"])
    )

    assert result.status == "inventory_mismatch"
    assert result.matches == ()


def test_symlink_escape_after_inventory_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = _write(repo, "inside.txt", "needle\n")
    outside = _write(tmp_path, "outside.txt", "needle secret\n")
    link = repo / "alias.txt"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")
    inventory = create_repository_inventory(repo)
    link.unlink()
    link.symlink_to(outside)

    result = execute_bounded_lexical_search(
        repo,
        inventory,
        build_lexical_search_request(["needle"], include_paths=["alias.txt"]),
    )

    assert result.matches == ()
    assert result.status == "file_changed_or_replaced"
    assert result.file_outcomes[0].as_dict()["excerpt"] is None


def test_changed_or_replaced_file_after_inventory_fails_closed(tmp_path: Path) -> None:
    path = _write(tmp_path, "app.py", "needle old\n")
    inventory = create_repository_inventory(tmp_path)
    path.write_text("needle replacement with a different identity\n", encoding="utf-8")

    result = execute_bounded_lexical_search(
        tmp_path, inventory, build_lexical_search_request(["needle"])
    )

    assert result.status == "file_changed_or_replaced"
    assert result.matches == ()
    assert result.file_outcomes[0].bytes_scanned == 0


def test_global_match_limit_is_enforced(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "\n".join(["needle"] * 10) + "\n")
    inventory = create_repository_inventory(tmp_path)
    request = build_lexical_search_request(["needle"], max_matches=3)

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert len(result.matches) == 3
    assert result.status == "search_complete_with_truncation"
    assert "global_match_limit" in result.diagnostics.truncation_reasons


def test_per_file_match_limit_is_enforced(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "\n".join(["needle"] * 10) + "\n")

    result = _run(tmp_path, max_matches_per_file=2)

    assert len(result.matches) == 2
    assert "per_file_match_limit" in result.diagnostics.truncation_reasons
    assert result.file_outcomes[0].truncated is True


def test_matched_file_limit_is_enforced(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "needle\n")
    _write(tmp_path, "b.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = build_lexical_search_request(["needle"], max_files=1)

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert len({item.path for item in result.matches}) == 1
    assert "matched_file_limit" in result.diagnostics.truncation_reasons


def test_excerpt_length_is_capped_and_reported(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "a" * 50 + "needle" + "z" * 50 + "\n")
    inventory = create_repository_inventory(tmp_path)
    request = build_lexical_search_request(["needle"], max_match_length=12)

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert len(result.matches[0].excerpt) == 12
    assert result.matches[0].excerpt_truncated is True


def test_file_scan_byte_limit_is_enforced_and_exposed(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle " + "x" * 100)

    result = _run(tmp_path, max_bytes_scanned_per_file=16)

    assert result.diagnostics.bytes_scanned == 16
    assert "file_byte_limit" in result.diagnostics.truncation_reasons
    assert result.diagnostics.truncated is True
    assert result.status == "search_complete_with_truncation"


def test_total_byte_budget_returns_stable_budget_exhausted_outcome(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle " + "x" * 100)

    result = _run(
        tmp_path,
        max_bytes_scanned_per_file=64,
        max_total_bytes_scanned=12,
    )

    assert result.status == "budget_exhausted"
    assert result.diagnostics.bytes_scanned == 12
    assert result.diagnostics.truncated is True
    assert "total_byte_limit" in result.diagnostics.truncation_reasons


def test_whole_token_preference_is_metadata_not_a_symbol_claim(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle needlex xneedle\n")

    result = _run(tmp_path)

    assert [item.whole_token for item in result.matches] == [True, False, False]
    assert all(item.whole_token_preference is True for item in result.matches)
    assert all(item.match_kind == "literal" for item in result.matches)
    assert all(item.file_understanding == "raw_text_only" for item in result.matches)


def test_explicit_include_order_is_candidate_path_priority(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "needle\n")
    _write(tmp_path, "b.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = {
        **build_lexical_search_request(["needle"]).as_dict(),
        "include_paths": ["b.py", "a.py"],
        "scope_mode": "explicit_paths",
    }

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert [item.path for item in result.matches] == ["b.py", "a.py"]
    assert [item.candidate_path_priority for item in result.matches] == [0, 1]


def test_duplicate_terms_and_identical_matches_are_deduplicated(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = {
        **build_lexical_search_request(["needle"]).as_dict(),
        "terms": ["needle", "NEEDLE"],
    }

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert len(result.matches) == 1


def test_result_order_is_deterministic_by_term_path_line_and_offset(tmp_path: Path) -> None:
    _write(tmp_path, "b.py", "beta alpha alpha\n")
    _write(tmp_path, "a.py", "alpha\nbeta\n")
    inventory = create_repository_inventory(tmp_path)
    request = {
        **build_lexical_search_request(["placeholder"]).as_dict(),
        "terms": ["beta", "alpha"],
    }

    first = execute_bounded_lexical_search(tmp_path, inventory, request)
    second = execute_bounded_lexical_search(tmp_path, inventory, copy.deepcopy(request))

    assert first == second
    assert first.matches == tuple(sorted(first.matches, key=lambda item: item.ordering_key()))
    assert [(item.matched_term, item.path) for item in first.matches] == [
        ("beta", "a.py"),
        ("beta", "b.py"),
        ("alpha", "a.py"),
        ("alpha", "b.py"),
        ("alpha", "b.py"),
    ]


def test_empty_terms_are_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = {**build_lexical_search_request(["needle"]).as_dict(), "terms": []}

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert result.status == "invalid_request"
    assert result.matches == ()


def test_excessive_terms_are_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = {
        **build_lexical_search_request(["needle"]).as_dict(),
        "terms": [f"term-{index}" for index in range(MAX_LEXICAL_TERMS + 1)],
    }

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert result.status == "invalid_request"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("include_paths", ["../outside/"]),
        ("include_paths", ["C:/outside/"]),
        ("exclude_paths", ["core\\private/"]),
    ],
)
def test_invalid_include_and_exclude_paths_are_rejected(
    tmp_path: Path, field: str, value: list[str]
) -> None:
    _write(tmp_path, "app.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = {**build_lexical_search_request(["needle"]).as_dict(), field: value}
    if field == "include_paths":
        request["scope_mode"] = "explicit_paths"

    result = execute_bounded_lexical_search(tmp_path, inventory, request)

    assert result.status == "invalid_request"
    assert result.diagnostics.files_scanned == 0


def test_one_file_repository_works_without_canonical_systems(tmp_path: Path) -> None:
    _write(tmp_path, "single.unsupported", "needle\n")
    inventory = create_repository_inventory(tmp_path)

    result = execute_bounded_lexical_search(
        tmp_path, inventory, build_lexical_search_request(["needle"])
    )
    rendered = result.as_dict()

    assert len(result.matches) == 1
    diagnostics = rendered["lexical_search"]
    assert diagnostics["vector_database_used"] is False
    assert diagnostics["embeddings_used"] is False
    assert diagnostics["canonical_manifest_used"] is False
    assert diagnostics["canonical_index_used"] is False
    assert diagnostics["model_used"] is False
    assert diagnostics["database_operations"] == 0
    assert diagnostics["writes_performed"] == 0
    assert diagnostics["patch_authority_granted"] is False


def test_generated_file_requires_explicit_search_only_permission(tmp_path: Path) -> None:
    _write(tmp_path, "generated/client.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = build_lexical_search_request(["needle"])

    excluded = execute_bounded_lexical_search(tmp_path, inventory, request)
    allowed = execute_bounded_lexical_search(
        tmp_path, inventory, request, allow_generated=True
    )

    assert excluded.matches == ()
    assert allowed.matches
    assert allowed.matches[0].as_dict()["write_authority"] is False
    assert allowed.warnings == (
        "generated files were permitted for search-only evidence",
    )


def test_request_and_inventory_are_not_mutated(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = build_lexical_search_request(["needle"])
    request_before = copy.deepcopy(request)
    inventory_before = copy.deepcopy(inventory)

    execute_bounded_lexical_search(tmp_path, inventory, request)

    assert request == request_before
    assert inventory == inventory_before


def test_runtime_source_has_no_traversal_database_model_patch_or_write_call() -> None:
    source_path = Path(__file__).parents[1] / "core" / "bounded_lexical_search.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }

    assert imported.isdisjoint({"subprocess", "sqlite3", "requests", "openai"})
    assert "walk" not in calls
    assert "write_text" not in calls
    assert "write_bytes" not in calls
    assert "apply_patch" not in calls
