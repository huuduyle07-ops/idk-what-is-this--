"""CTX.READ.1 request validation, ordering, artifact, and guardrail tests."""

from __future__ import annotations

import ast
import copy
import os
from pathlib import Path

import pytest

from core.direct_context_runtime import (
    build_direct_read_request,
    compute_repository_inventory_identity,
    execute_direct_context,
)
from core.direct_file_reader import DirectReadBudgets
from core.repository_inventory import create_repository_inventory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULES = (
    PROJECT_ROOT / "core" / "direct_file_reader.py",
    PROJECT_ROOT / "core" / "direct_context_runtime.py",
    PROJECT_ROOT / "core" / "direct_read_receipt.py",
)


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def _proposal(inventory, ordered: tuple[tuple[str, str], ...] | None = None):
    entries = {
        entry.relative_path.as_posix(): entry for entry in inventory.entries
    }
    ordered = ordered or tuple(
        (path, "primary_or_supporting_target") for path in entries
    )
    selected = [
        {
            "path": path,
            "actionability_score": 90 - index,
            "estimated_bytes": entries[path].file_identity.size_bytes,
            "role": role,
            "selection_reason": role,
            "read_authority": False,
            "write_authority": False,
        }
        for index, (path, role) in enumerate(ordered)
    ]
    return {
        "selected": selected,
        "excluded": [],
        "total_estimated_bytes": sum(item["estimated_bytes"] for item in selected),
        "max_files": 8,
        "max_total_bytes": 1_048_576,
        "read_authority": False,
        "write_authority": False,
    }


def _request(root: Path, inventory, selected, budgets=None):
    request = {
        "schema_version": 1,
        "task_id": "run-context",
        "repository_root": str(root.resolve()),
        "inventory_identity": compute_repository_inventory_identity(inventory),
        "selected_files": selected,
    }
    if budgets is not None:
        request["budgets"] = budgets
    return request


def test_valid_proposed_read_request_is_accepted(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "print('ok')\n")
    inventory = create_repository_inventory(tmp_path)
    request = _request(
        tmp_path, inventory, [{"path": "app.py", "requested_mode": "full_file"}]
    )

    result = execute_direct_context(
        tmp_path, inventory, request, proposed_read_set=_proposal(inventory)
    )

    assert result.status == "operation_complete"
    assert result.files_read == 1
    assert result.file_results[0].read_authority_granted is True
    assert result.file_results[0].as_dict()["write_authority"] is False
    assert result.file_results[0].as_dict()["patch_authority"] is False


def test_arbitrary_inventory_path_not_in_proposed_set_is_rejected(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "approved.py", "approved\n")
    _write(tmp_path, "arbitrary.py", "must not read\n")
    inventory = create_repository_inventory(tmp_path)
    request = _request(
        tmp_path,
        inventory,
        [{"path": "arbitrary.py", "requested_mode": "full_file"}],
    )

    result = execute_direct_context(
        tmp_path,
        inventory,
        request,
        proposed_read_set=_proposal(
            inventory, (("approved.py", "primary_or_supporting_target"),)
        ),
    )

    assert result.status == "operation_complete_with_partial_reads"
    assert result.file_results[0].reason == "path_not_in_proposed_read_set"
    assert result.file_results[0].content is None


@pytest.mark.parametrize("path", ["missing.py", "../outside.py", "C:/outside.py"])
def test_non_inventory_or_outside_paths_fail_closed(tmp_path: Path, path: str) -> None:
    _write(tmp_path, "app.py", "safe\n")
    inventory = create_repository_inventory(tmp_path)
    request = _request(
        tmp_path, inventory, [{"path": path, "requested_mode": "full_file"}]
    )

    result = execute_direct_context(
        tmp_path, inventory, request, proposed_read_set=_proposal(inventory)
    )

    assert result.file_results[0].read_status in {
        "path_not_in_inventory",
        "path_outside_repository",
    }
    assert result.file_results[0].content is None


def test_root_and_inventory_identity_mismatch_block_whole_operation(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    other = tmp_path / "other"
    repo.mkdir()
    other.mkdir()
    _write(repo, "app.py", "safe\n")
    inventory = create_repository_inventory(repo)
    request = _request(
        repo, inventory, [{"path": "app.py", "requested_mode": "full_file"}]
    )

    wrong_root = execute_direct_context(
        other, inventory, request, proposed_read_set=_proposal(inventory)
    )
    wrong_identity_request = {**request, "inventory_identity": "sha256:wrong"}
    wrong_identity = execute_direct_context(
        repo,
        inventory,
        wrong_identity_request,
        proposed_read_set=_proposal(inventory),
    )

    assert wrong_root.status == "operation_blocked"
    assert wrong_identity.status == "operation_blocked"
    assert wrong_root.file_results == wrong_identity.file_results == ()


def test_duplicate_and_excessive_file_requests_are_structurally_blocked(
    tmp_path: Path,
) -> None:
    for index in range(9):
        _write(tmp_path, f"file-{index}.txt", str(index))
    inventory = create_repository_inventory(tmp_path)
    duplicate = _request(
        tmp_path,
        inventory,
        [
            {"path": "file-0.txt", "requested_mode": "full_file"},
            {"path": "file-0.txt", "requested_mode": "full_file"},
        ],
    )
    excessive = _request(
        tmp_path,
        inventory,
        [
            {"path": f"file-{index}.txt", "requested_mode": "full_file"}
            for index in range(9)
        ],
    )

    duplicate_result = execute_direct_context(
        tmp_path, inventory, duplicate, proposed_read_set=_proposal(inventory)
    )
    excessive_result = execute_direct_context(
        tmp_path, inventory, excessive, proposed_read_set=_proposal(inventory)
    )

    assert duplicate_result.status == "operation_blocked"
    assert excessive_result.status == "operation_blocked"


@pytest.mark.parametrize(
    "selected",
    [
        [{"path": "app.py", "requested_mode": "tail"}],
        [
            {
                "path": "app.py",
                "requested_mode": "match_windows",
                "match_locations": [{"line": 0, "term": "bad"}],
            }
        ],
        [
            {
                "path": "app.py",
                "requested_mode": "explicit_ranges",
                "ranges": [{"start_line": 5, "end_line": 2}],
            }
        ],
    ],
)
def test_structurally_malformed_nested_requests_block_the_operation(
    tmp_path: Path, selected
) -> None:
    _write(tmp_path, "app.py", "safe\n")
    inventory = create_repository_inventory(tmp_path)

    result = execute_direct_context(
        tmp_path,
        inventory,
        _request(tmp_path, inventory, selected),
        proposed_read_set=_proposal(inventory),
    )

    assert result.status == "operation_blocked"
    assert result.file_results == ()


def test_request_and_evidence_inputs_are_not_mutated(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "safe\n")
    inventory = create_repository_inventory(tmp_path)
    request = _request(
        tmp_path, inventory, [{"path": "app.py", "requested_mode": "full_file"}]
    )
    proposal = _proposal(inventory)
    request_before = copy.deepcopy(request)
    proposal_before = copy.deepcopy(proposal)

    execute_direct_context(
        tmp_path, inventory, request, proposed_read_set=proposal
    )

    assert request == request_before
    assert proposal == proposal_before


def test_priority_order_comes_from_proposed_set_not_request_or_filesystem(
    tmp_path: Path,
) -> None:
    for path in ("config.toml", "tests/test_app.py", "dependency.py", "target.py"):
        _write(tmp_path, path, f"{path}\n")
    inventory = create_repository_inventory(tmp_path)
    priority = (
        ("target.py", "primary_or_supporting_target"),
        ("dependency.py", "dependency_or_caller"),
        ("tests/test_app.py", "validation"),
        ("config.toml", "configuration"),
    )
    selected = [
        {"path": path, "requested_mode": "full_file"}
        for path in reversed([item[0] for item in priority])
    ]

    result = execute_direct_context(
        tmp_path,
        inventory,
        _request(tmp_path, inventory, selected),
        proposed_read_set=_proposal(inventory, priority),
    )

    assert [item.path for item in result.file_results] == [item[0] for item in priority]


def test_file_budget_omits_lower_priority_files_explicitly(tmp_path: Path) -> None:
    for path in ("target.py", "dependency.py", "tests/test_app.py"):
        _write(tmp_path, path, f"{path}\n")
    inventory = create_repository_inventory(tmp_path)
    priority = (
        ("target.py", "primary_or_supporting_target"),
        ("dependency.py", "dependency_or_caller"),
        ("tests/test_app.py", "validation"),
    )
    budgets = {**DirectReadBudgets().as_dict(), "max_files": 1}
    request = _request(
        tmp_path,
        inventory,
        [{"path": path, "requested_mode": "full_file"} for path, _ in priority],
        budgets,
    )

    result = execute_direct_context(
        tmp_path,
        inventory,
        request,
        proposed_read_set=_proposal(inventory, priority),
    )

    assert result.file_results[0].read_status == "read_complete"
    assert [item.read_status for item in result.file_results[1:]] == [
        "budget_exhausted",
        "budget_exhausted",
    ]
    assert [item.path for item in result.omitted_files] == [
        "dependency.py",
        "tests/test_app.py",
    ]


def test_total_byte_budget_preserves_earlier_complete_file(tmp_path: Path) -> None:
    _write(tmp_path, "first.txt", "12345678")
    _write(tmp_path, "second.txt", "abcdefgh")
    inventory = create_repository_inventory(tmp_path)
    priority = (
        ("first.txt", "primary_or_supporting_target"),
        ("second.txt", "dependency_or_caller"),
    )
    budgets = {**DirectReadBudgets().as_dict(), "max_total_bytes": 10}

    result = execute_direct_context(
        tmp_path,
        inventory,
        _request(
            tmp_path,
            inventory,
            [
                {"path": "second.txt", "requested_mode": "full_file"},
                {"path": "first.txt", "requested_mode": "full_file"},
            ],
            budgets,
        ),
        proposed_read_set=_proposal(inventory, priority),
    )

    assert result.file_results[0].content == "12345678"
    assert result.file_results[1].read_status == "budget_exhausted"
    assert result.total_bytes_returned == 8
    assert result.budget_remaining == 2


def test_partial_file_failure_does_not_abort_safe_reads(tmp_path: Path) -> None:
    _write(tmp_path, "safe.txt", "safe\n")
    _write(tmp_path, "bad.custom", "will change\n")
    inventory = create_repository_inventory(tmp_path)
    (tmp_path / "bad.custom").write_text("changed\n", encoding="utf-8")
    priority = (
        ("safe.txt", "primary_or_supporting_target"),
        ("bad.custom", "dependency_or_caller"),
    )

    result = execute_direct_context(
        tmp_path,
        inventory,
        _request(
            tmp_path,
            inventory,
            [
                {"path": "safe.txt", "requested_mode": "full_file"},
                {"path": "bad.custom", "requested_mode": "full_file"},
            ],
        ),
        proposed_read_set=_proposal(inventory, priority),
    )

    assert result.status == "operation_complete_with_partial_reads"
    assert result.file_results[0].read_status == "read_complete"
    assert result.file_results[1].read_status == "file_changed_or_replaced"


def test_restrictive_capability_evidence_cannot_be_relaxed(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "must remain blocked\n")
    inventory = create_repository_inventory(tmp_path)

    result = execute_direct_context(
        tmp_path,
        inventory,
        _request(
            tmp_path,
            inventory,
            [{"path": "app.py", "requested_mode": "full_file"}],
        ),
        proposed_read_set=_proposal(inventory),
        capabilities=[
            {
                "path": "app.py",
                "size_bytes": len("must remain blocked\n"),
                "repository_contained": False,
                "readability": "readable_text",
            }
        ],
    )

    assert result.file_results[0].read_authority_granted is False
    assert result.file_results[0].content is None


@pytest.mark.parametrize(
    "identity_state",
    ["unconfirmed", "uninitialized", "blocked", "confirmation_required"],
)
def test_runtime_is_independent_and_context_claims_remain_narrow(
    tmp_path: Path, identity_state: str
) -> None:
    _write(tmp_path, "only.custom", "direct\n")
    inventory = create_repository_inventory(tmp_path)

    result = execute_direct_context(
        tmp_path,
        inventory,
        _request(
            tmp_path,
            inventory,
            [{"path": "only.custom", "requested_mode": "auto"}],
        ),
        proposed_read_set=_proposal(inventory),
        canonical_identity_state=identity_state,
        vector_database_available=False,
        embedding_provider_enabled=False,
        canonical_manifest_available=False,
        parser_available=False,
    )
    rendered = result.as_dict()

    assert rendered["repository_completeness_claimed"] is False
    assert rendered["canonical_identity_required"] is False
    assert rendered["ephemeral"] is True
    assert rendered["persisted"] is False
    for key in (
        "canonical_index_used",
        "canonical_manifest_used",
        "vector_database_used",
        "embeddings_used",
        "activation_graph_used",
        "parser_used",
        "model_used",
        "api_calls_made",
    ):
        assert rendered[key] is False
    assert rendered["database_operations"] == 0
    assert rendered["writes_performed"] == 0
    assert rendered["patches_applied"] == 0
    assert rendered["repository_membership_traversals"] == 0
    assert rendered["additional_searches_performed"] == 0
    assert rendered["write_authority"] is False
    assert rendered["patch_authority"] is False


def test_runtime_performs_no_additional_repository_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "app.py", "safe\n")
    inventory = create_repository_inventory(tmp_path)

    def forbidden_walk(*args, **kwargs):  # pragma: no cover - failure only
        raise AssertionError("repository traversal is forbidden")

    monkeypatch.setattr(os, "walk", forbidden_walk)
    result = execute_direct_context(
        tmp_path,
        inventory,
        _request(
            tmp_path,
            inventory,
            [{"path": "app.py", "requested_mode": "full_file"}],
        ),
        proposed_read_set=_proposal(inventory),
    )

    assert result.status == "operation_complete"


def test_request_builder_carries_no_authority(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "safe\n")
    inventory = create_repository_inventory(tmp_path)
    proposal_mapping = _proposal(inventory)

    # The builder intentionally requires the typed upstream evidence object;
    # use its explicit selected list here to show the envelope flags separately.
    from core.context_selection import ProposedReadFile, ProposedReadSet

    typed = ProposedReadSet(
        selected=(
            ProposedReadFile(
                "app.py", 80, len("safe\n"), "primary_or_supporting_target", "test"
            ),
        ),
        excluded=(),
        total_estimated_bytes=len("safe\n"),
        max_files=8,
        max_total_bytes=1_048_576,
        truncated=False,
        selection_reasons=(("app.py", "test"),),
    )
    request = build_direct_read_request(
        task_id="run-builder",
        repository_root=tmp_path,
        inventory=inventory,
        proposed_read_set=typed,
    )

    assert proposal_mapping["read_authority"] is False
    assert request["read_authority"] is False
    assert request["write_authority"] is False
    assert request["patch_authority"] is False


def test_core_runtime_has_no_forbidden_subsystem_imports() -> None:
    forbidden_prefixes = (
        "sqlite3",
        "subprocess",
        "requests",
        "httpx",
        "database",
        "graph",
        "patching",
        "core.indexer",
        "core.embedding_providers",
        "core.retriever",
        "openai",
    )
    for path in RUNTIME_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(
            name == prefix or name.startswith(prefix + ".")
            for name in imports
            for prefix in forbidden_prefixes
        ), (path, imports)
        calls = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        assert not calls & {
            "walk",
            "rglob",
            "write_text",
            "write_bytes",
            "connect",
            "Popen",
            "run",
            "request",
            "urlopen",
            "index_repository",
            "build_activation_graph",
            "apply_patch",
        }, (path, calls)
