"""CTX.SEARCH.1 to CTX.SELECT.1 integration tests."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from core.context_search_runtime import execute_context_search
from core.file_candidate_selector import build_lexical_search_request
from core.repository_inventory import create_repository_inventory


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ctx_select_consumes_runtime_results_deterministically(tmp_path: Path) -> None:
    _write(tmp_path, "core/b.py", "needle\n")
    _write(tmp_path, "core/a.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = build_lexical_search_request(["needle"])

    first = execute_context_search(tmp_path, inventory, request)
    second = execute_context_search(
        tmp_path, copy.deepcopy(inventory), copy.deepcopy(request)
    )

    assert first == second
    assert [item.path for item in first.lexical_results.matches] == [
        "core/a.py",
        "core/b.py",
    ]
    assert all(
        item.result_source == "ctx_search_1"
        for item in first.lexical_results.matches
    )


@pytest.mark.parametrize(
    "identity_state",
    [
        "unconfirmed",
        "uninitialized",
        "initial_confirmation_required",
        "major_change_confirmation_required",
        "blocked",
    ],
)
def test_runtime_is_independent_of_identity_vectors_embeddings_and_manifest(
    tmp_path: Path, identity_state: str
) -> None:
    _write(tmp_path, "single.custom", "needle\n")
    inventory = create_repository_inventory(tmp_path)

    result = execute_context_search(
        tmp_path,
        inventory,
        build_lexical_search_request(["needle"]),
        canonical_identity_state=identity_state,
        vector_database_available=False,
        embedding_provider_enabled=False,
        canonical_manifest_available=False,
    )
    rendered = result.as_dict()

    assert result.lexical_results.matches
    assert rendered["canonical_identity_required"] is False
    for key in (
        "vector_database_used",
        "embeddings_used",
        "canonical_manifest_used",
        "canonical_index_used",
        "model_used",
        "api_calls_made",
    ):
        assert rendered[key] is False
    assert rendered["database_operations"] == 0
    assert rendered["writes_performed"] == 0


def test_selector_projection_preserves_candidate_only_authority(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)

    result = execute_context_search(
        tmp_path, inventory, build_lexical_search_request(["needle"])
    )
    rendered = result.as_dict()
    selector_match = rendered["ctx_select_lexical_results"]["matches"][0]

    assert rendered["execution_authority"] == "candidate_discovery_only"
    assert rendered["read_authority"] is False
    assert rendered["write_authority"] is False
    assert selector_match["execution_authority"] == "candidate_discovery_only"
    assert selector_match["read_authority"] is False
    assert selector_match["write_authority"] is False


def test_invalid_request_returns_empty_selector_evidence(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "needle\n")
    inventory = create_repository_inventory(tmp_path)
    request = {**build_lexical_search_request(["needle"]).as_dict(), "terms": []}

    result = execute_context_search(tmp_path, inventory, request)

    assert result.status == "invalid_request"
    assert result.lexical_results.matches == ()

