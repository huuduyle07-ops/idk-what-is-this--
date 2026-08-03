"""CTX.PATCH.1 receipt, capability, evidence, and authority gate tests."""

from __future__ import annotations

import ast
import copy
import hashlib
from pathlib import Path

import pytest

from core.direct_context_runtime import (
    compute_repository_inventory_identity,
    execute_direct_context,
)
from core.direct_patch_candidate_gate import execute_direct_patch_candidate_gate
from core.direct_read_receipt import (
    DirectReadFileIdentity,
    DirectReadRangeReceipt,
    DirectReadReceipt,
)
from core.file_capabilities import classify_file_capability
from core.repository_inventory import (
    RepositoryFileIdentity,
    create_repository_inventory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GATE_MODULES = (
    PROJECT_ROOT / "core" / "file_patchability.py",
    PROJECT_ROOT / "core" / "direct_patch_candidate_gate.py",
    PROJECT_ROOT / "core" / "proposed_patch_set.py",
)


def _write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _proposal(inventory, paths: tuple[str, ...]) -> dict:
    entries = {
        entry.relative_path.as_posix(): entry for entry in inventory.entries
    }
    selected = [
        {
            "path": path,
            "actionability_score": 95 - index,
            "estimated_bytes": entries[path].file_identity.size_bytes,
            "role": "primary_or_supporting_target",
            "selection_reason": "direct target",
            "read_authority": False,
            "write_authority": False,
        }
        for index, path in enumerate(paths)
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


def _read_context(root: Path, inventory, paths: tuple[str, ...]):
    request = {
        "schema_version": 1,
        "task_id": "run-patch",
        "operation_id": "operation-patch",
        "repository_root": str(root.resolve()),
        "inventory_identity": compute_repository_inventory_identity(inventory),
        "selected_files": [
            {"path": path, "requested_mode": "full_file"} for path in paths
        ],
    }
    return execute_direct_context(
        root,
        inventory,
        request,
        proposed_read_set=_proposal(inventory, paths),
    )


def _current(root: Path, *paths: str) -> dict[str, RepositoryFileIdentity]:
    return {
        path: RepositoryFileIdentity.from_stat_result((root / path).stat())
        for path in paths
    }


def _strong_evidence() -> list[dict]:
    return [
        {
            "kind": "direct_read_target_confirmation",
            "detail": "direct read contains the named dispatch branch",
            "evidence_id": "read-target",
        },
        {
            "kind": "diagnosis_confidence",
            "detail": "the bounded branch explains the observed behavior",
        },
        {
            "kind": "change_locality",
            "detail": "one bounded conditional",
        },
        {
            "kind": "symbol_or_branch_specificity",
            "detail": "dispatch branch at lines 2-3",
        },
        {
            "kind": "reversibility",
            "detail": "one local branch can be reverted",
        },
    ]


def _intention(start: int = 2, end: int = 3) -> dict:
    return {
        "summary": "Prevent the verified no-change branch from continuing.",
        "target_ranges": [{"start_line": start, "end_line": end}],
        "expected_behavior_change": "Verified no-change runs return early.",
        "must_preserve": ["non-empty delta behavior"],
    }


def _candidate(path: str = "core/router.py", **over) -> dict:
    result = {
        "path": path,
        "actionability_score": 96,
        "patchability_evidence": _strong_evidence(),
        "change_intention": _intention(),
        "validation_candidates": ["tests/test_router.py"],
        "blast_radius": "low",
        "role": "primary_or_supporting_target",
        "patch_role": "primary",
    }
    result.update(over)
    return result


def _ready_fixture(tmp_path: Path, *, path: str = "core/router.py"):
    _write(tmp_path, path, "header\nif unchanged:\n    return done\nfallback()\n")
    inventory = create_repository_inventory(tmp_path)
    context = _read_context(tmp_path, inventory, (path,))
    return inventory, context


def _gate(tmp_path: Path, inventory, context, candidate: dict, **over):
    parameters = {
        "current_file_identities": _current(tmp_path, candidate["path"]),
    }
    parameters.update(over)
    return execute_direct_patch_candidate_gate(
        inventory, context, [candidate], **parameters
    )


def _forged_receipt(path: Path, relative: str, inventory_identity: str):
    raw = path.read_bytes()
    stat_result = path.stat()
    line_count = len(raw.decode("utf-8").splitlines())
    digest = hashlib.sha256(raw).hexdigest()
    return DirectReadReceipt(
        task_id="run-patch",
        operation_id="operation-patch",
        inventory_identity=inventory_identity,
        path=relative,
        read_status="read_complete",
        read_mode="full_file",
        file_identity=DirectReadFileIdentity.from_stat_result(
            stat_result,
            content_sha256=digest,
            scanned_content_sha256=digest,
        ),
        ranges=(
            DirectReadRangeReceipt(1, line_count, len(raw), line_count),
        ),
        bytes_scanned=len(raw),
        bytes_returned=len(raw),
        lines_scanned=line_count,
        lines_returned=line_count,
        truncated=False,
        truncation_reasons=(),
        decoding="utf8",
        replacement_count=0,
        parser_support="unsupported",
        understanding_confidence="raw_text_only",
    )


def _forged_context(inventory, receipt) -> dict:
    return {
        "operation_status": "operation_complete",
        "task_id": "run-patch",
        "operation_id": "operation-patch",
        "inventory_identity": compute_repository_inventory_identity(inventory),
        "read_receipts": [receipt.as_dict()],
    }


def test_fresh_successful_receipt_produces_bounded_patch_candidate(
    tmp_path: Path,
) -> None:
    inventory, context = _ready_fixture(tmp_path)

    result = _gate(tmp_path, inventory, context, _candidate())
    rendered = result.as_dict()

    assert result.status == "ready"
    assert [item["path"] for item in rendered["implementation_candidates"]] == [
        "core/router.py"
    ]
    candidate = rendered["implementation_candidates"][0]
    assert candidate["candidate_state"] == "eligible"
    assert candidate["receipt_freshness"] == "fresh"
    assert candidate["patchability_score"] != candidate["actionability_score"]
    assert candidate["change_intention"]["diff_generated"] is False


def test_missing_receipt_blocks_candidacy(tmp_path: Path) -> None:
    _write(tmp_path, "core/read.py", "read\n")
    _write(tmp_path, "core/unread.py", "one\ntwo\nthree\n")
    inventory = create_repository_inventory(tmp_path)
    context = _read_context(tmp_path, inventory, ("core/read.py",))
    candidate = _candidate("core/unread.py")

    result = _gate(tmp_path, inventory, context, candidate)
    evaluation = next(item for item in result.evaluations if item.path == candidate["path"])

    assert evaluation.candidate_state == "insufficient_evidence"
    assert evaluation.receipt_freshness == "unverifiable"
    assert result.proposed_patch_set.paths == ()


def test_changed_receipt_requires_reread(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    _write(tmp_path, "core/router.py", "changed\ncontent\nis different\n")

    result = _gate(tmp_path, inventory, context, _candidate())
    evaluation = result.evaluations[0]

    assert result.status == "reread_required"
    assert evaluation.receipt_freshness == "changed"
    assert evaluation.candidate_state == "reread_required"
    assert evaluation.freshness_action == "reread_required"


def test_deleted_receipt_target_is_removed(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)

    result = execute_direct_patch_candidate_gate(
        inventory,
        context,
        [_candidate()],
        current_file_identities={"core/router.py": None},
    )
    evaluation = result.evaluations[0]

    assert evaluation.receipt_freshness == "deleted"
    assert evaluation.freshness_action == "candidate_removed"
    assert evaluation.path not in result.proposed_patch_set.paths


def test_replaced_file_is_security_blocked(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    receipt = context.read_receipts[0]
    replaced = {**receipt.file_identity.as_dict(), "inode": receipt.file_identity.inode + 1}

    result = execute_direct_patch_candidate_gate(
        inventory,
        context,
        [_candidate()],
        current_file_identities={"core/router.py": replaced},
    )
    evaluation = result.evaluations[0]

    assert evaluation.receipt_freshness == "replaced"
    assert evaluation.freshness_action == "security_blocked"
    assert evaluation.candidate_state == "forbidden"
    assert result.status == "blocked"


def test_unverifiable_current_identity_requires_reread(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)

    result = execute_direct_patch_candidate_gate(
        inventory,
        context,
        [_candidate()],
        current_file_identities={"core/router.py": {"size": 20}},
    )

    assert result.evaluations[0].receipt_freshness == "unverifiable"
    assert result.evaluations[0].candidate_state == "reread_required"


def test_partial_receipt_not_covering_target_blocks_candidate(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    receipt = context.read_receipts[0].as_dict()
    receipt.update(
        {
            "read_mode": "explicit_ranges",
            "bytes_returned": 7,
            "lines_returned": 1,
            "ranges": [
                {
                    "start_line": 1,
                    "end_line": 1,
                    "bytes_returned": 7,
                    "lines_returned": 1,
                }
            ],
        }
    )
    partial_context = {**context.as_dict(), "read_receipts": [receipt]}

    result = _gate(tmp_path, inventory, partial_context, _candidate())

    assert result.evaluations[0].candidate_state == "insufficient_evidence"
    assert "target range" in result.evaluations[0].reason


def test_partial_receipt_covering_target_may_qualify_with_review(
    tmp_path: Path,
) -> None:
    inventory, context = _ready_fixture(tmp_path)
    receipt = context.read_receipts[0].as_dict()
    receipt.update(
        {
            "read_status": "read_complete_with_truncation",
            "read_mode": "explicit_ranges",
            "bytes_returned": 30,
            "lines_returned": 2,
            "ranges": [
                {
                    "start_line": 2,
                    "end_line": 3,
                    "bytes_returned": 30,
                    "lines_returned": 2,
                }
            ],
            "truncated": True,
            "truncation_reasons": ["explicit_range"],
        }
    )
    partial_context = {**context.as_dict(), "read_receipts": [receipt]}

    result = _gate(tmp_path, inventory, partial_context, _candidate())

    assert result.evaluations[0].candidate_state == "eligible_with_review"
    assert result.evaluations[0].receipt_freshness == "fresh"


@pytest.mark.parametrize(
    ("editability", "expected_state"),
    [
        ("editable", "eligible"),
        ("editable_with_review", "eligible_with_review"),
        ("read_only", "read_only_context"),
        ("forbidden", "forbidden"),
    ],
)
def test_editability_states_override_score(
    tmp_path: Path, editability: str, expected_state: str
) -> None:
    inventory, context = _ready_fixture(tmp_path)
    capability = classify_file_capability(
        "core/router.py", editability=editability
    )

    result = _gate(
        tmp_path,
        inventory,
        context,
        _candidate(capability=capability),
    )

    assert result.evaluations[0].candidate_state == expected_state


def test_generated_file_redirects_to_authoritative_source(tmp_path: Path) -> None:
    path = "generated/client.py"
    inventory, context = _ready_fixture(tmp_path, path=path)
    capability = classify_file_capability(
        path, authoritative_source="schema/api.yaml"
    )

    result = _gate(
        tmp_path,
        inventory,
        context,
        _candidate(path, capability=capability),
    )
    evaluation = result.evaluations[0]

    assert evaluation.candidate_state == "generated_source_redirect"
    assert evaluation.redirect_to == "schema/api.yaml"
    assert evaluation.patchability_score > 0
    assert evaluation.path not in result.proposed_patch_set.paths


def test_sensitive_env_is_blocked_even_with_a_supplied_read_receipt(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, ".env", "TOKEN=placeholder\n")
    inventory = create_repository_inventory(tmp_path)
    identity = compute_repository_inventory_identity(inventory)
    receipt = _forged_receipt(path, ".env", identity)
    context = _forged_context(inventory, receipt)

    result = execute_direct_patch_candidate_gate(
        inventory,
        context,
        [_candidate(".env", change_intention=_intention(1, 1))],
        current_file_identities=_current(tmp_path, ".env"),
    )

    assert result.evaluations[0].candidate_state == "sensitive_blocked"
    assert result.evaluations[0].patchability_score == 0


def test_outside_inventory_path_is_rejected(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    candidate = _candidate("../outside.py")

    result = execute_direct_patch_candidate_gate(
        inventory,
        context,
        [candidate],
        current_file_identities={"../outside.py": None},
    )

    assert result.evaluations[0].candidate_state == "outside_scope"
    assert result.proposed_patch_set.paths == ()


def test_symlink_or_replacement_ambiguity_fails_closed(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    capability = classify_file_capability(
        "core/router.py", symlink_escape=True
    )

    result = _gate(
        tmp_path,
        inventory,
        context,
        _candidate(capability=capability),
    )

    assert result.evaluations[0].candidate_state == "forbidden"


def test_filename_or_lexical_evidence_alone_is_insufficient(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    candidate = _candidate(
        patchability_evidence=[
            {"kind": "exact_filename_match", "detail": "router.py"},
            {"kind": "lexical_match", "detail": "unchanged"},
        ]
    )

    result = _gate(tmp_path, inventory, context, candidate)

    assert result.evaluations[0].candidate_state == "insufficient_evidence"


def test_lexical_plus_direct_read_confirmation_may_qualify(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    evidence = [
        {"kind": "lexical_match", "detail": "unchanged"},
        *_strong_evidence(),
    ]

    result = _gate(
        tmp_path,
        inventory,
        context,
        _candidate(patchability_evidence=evidence),
    )

    assert result.evaluations[0].candidate_state == "eligible"
    assert "lexical_match" in result.evaluations[0].patchability.ignored_evidence_kinds


def test_matching_validation_raises_patchability(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    with_test = _gate(tmp_path, inventory, context, _candidate())
    without_test = _gate(
        tmp_path,
        inventory,
        context,
        _candidate(validation_candidates=[]),
    )

    assert with_test.evaluations[0].patchability_score > (
        without_test.evaluations[0].patchability_score
    )


def test_validation_gap_is_explicit_and_forces_review(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    evidence = [
        *_strong_evidence(),
        {
            "kind": "authoritative_source_confidence",
            "detail": "the direct source owns the behavior",
        },
    ]
    candidate = _candidate(
        patchability_evidence=evidence,
        validation_candidates=[],
        validation_status="gap",
    )

    result = _gate(tmp_path, inventory, context, candidate)

    assert result.evaluations[0].validation_status == "gap"
    assert result.evaluations[0].candidate_state == "validation_gap"
    assert result.status == "ready_with_review"


def test_bounded_manual_verification_evidence_is_a_validation_path(
    tmp_path: Path,
) -> None:
    inventory, context = _ready_fixture(tmp_path)
    candidate = _candidate(
        patchability_evidence=[
            *_strong_evidence(),
            {
                "kind": "bounded_manual_verification",
                "detail": "manually exercise unchanged and non-empty delta branches",
            },
        ],
        validation_candidates=[],
    )

    result = _gate(tmp_path, inventory, context, candidate)
    evaluation = result.evaluations[0]

    assert evaluation.validation_status == "mapped"
    assert evaluation.validation_candidates[0].kind == "manual"
    assert evaluation.validation_candidates[0].confidence == "low"


def test_unknown_blast_radius_never_defaults_to_low(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)

    result = _gate(
        tmp_path,
        inventory,
        context,
        _candidate(blast_radius="unknown"),
    )

    assert result.evaluations[0].blast_radius == "unknown"
    assert result.evaluations[0].candidate_state == "eligible_with_review"


@pytest.mark.parametrize("blast_radius", ["high", "critical"])
def test_high_blast_radius_has_a_stable_review_state(
    tmp_path: Path, blast_radius: str
) -> None:
    inventory, context = _ready_fixture(tmp_path)
    evidence = [
        *_strong_evidence(),
        {
            "kind": "authoritative_source_confidence",
            "detail": "direct owner",
        },
    ]

    result = _gate(
        tmp_path,
        inventory,
        context,
        _candidate(
            blast_radius=blast_radius,
            patchability_evidence=evidence,
        ),
    )

    assert result.evaluations[0].candidate_state == "high_blast_radius_review"
    assert result.status == "ready_with_review"


def test_unsupported_safe_text_qualifies_with_raw_text_limitations(
    tmp_path: Path,
) -> None:
    path = "config/router.yaml"
    inventory, context = _ready_fixture(tmp_path, path=path)

    result = _gate(tmp_path, inventory, context, _candidate(path))
    rendered = result.evaluations[0].as_dict()

    assert rendered["candidate_state"] == "eligible_with_review"
    assert rendered["parser_support"] == "unsupported"
    assert rendered["understanding_confidence"] == "raw_text_only"
    assert rendered["AST_claimed"] is False
    assert rendered["dependency_completeness_claimed"] is False


def test_env_example_may_be_a_reviewed_configuration_candidate(
    tmp_path: Path,
) -> None:
    path = ".env.example"
    _write(tmp_path, path, "SETTING=old\n")
    inventory = create_repository_inventory(tmp_path)
    context = _read_context(tmp_path, inventory, (path,))
    evidence = [
        *_strong_evidence(),
        {
            "kind": "authoritative_source_confidence",
            "detail": "documented public configuration template",
        },
    ]
    candidate = _candidate(
        path,
        patchability_evidence=evidence,
        change_intention=_intention(1, 1),
    )

    result = _gate(tmp_path, inventory, context, candidate)

    assert result.evaluations[0].candidate_state == "eligible_with_review"
    assert result.evaluations[0].editability == "editable_with_review"


def test_test_file_is_only_a_separate_policy_validation_candidate(
    tmp_path: Path,
) -> None:
    source = "core/router.py"
    test = "tests/test_router.py"
    _write(tmp_path, source, "header\nif unchanged:\n    return done\nfallback()\n")
    _write(tmp_path, test, "header\ndef test_router():\n    assert True\nfooter\n")
    inventory = create_repository_inventory(tmp_path)
    context = _read_context(tmp_path, inventory, (source, test))
    source_candidate = _candidate(
        source,
        validation_candidates=[test],
    )
    test_candidate = _candidate(
        test,
        role="validation",
        patch_role="validation",
        change_intention=_intention(2, 3),
        validation_candidates=[test],
    )

    result = execute_direct_patch_candidate_gate(
        inventory,
        context,
        [source_candidate, test_candidate],
        current_file_identities=_current(tmp_path, source, test),
    ).as_dict()

    assert [item["path"] for item in result["validation_candidates"]] == [test]
    selected = result["validation_candidates"][0]
    assert selected["test_modification_requires_separate_policy"] is True
    assert selected["write_authority"] is False
    assert selected["patch_application_authority"] is False


def test_read_files_need_not_all_become_candidates(tmp_path: Path) -> None:
    _write(tmp_path, "core/router.py", "header\nif unchanged:\n    return done\nfallback()\n")
    _write(tmp_path, "docs/context.md", "one\ntwo\nthree\nfour\n")
    inventory = create_repository_inventory(tmp_path)
    context = _read_context(
        tmp_path, inventory, ("core/router.py", "docs/context.md")
    )

    result = execute_direct_patch_candidate_gate(
        inventory,
        context,
        [_candidate()],
        current_file_identities=_current(
            tmp_path, "core/router.py", "docs/context.md"
        ),
    )

    assert result.files_read == 2
    assert result.proposed_patch_set.paths == ("core/router.py",)
    assert [item.path for item in result.proposed_patch_set.supporting_context] == [
        "docs/context.md"
    ]


def test_task_or_operation_receipt_mismatch_blocks_candidate(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    receipt = context.read_receipts[0].as_dict()
    receipt["operation_id"] = "another-operation"
    mismatched = {**context.as_dict(), "read_receipts": [receipt]}

    result = _gate(tmp_path, inventory, mismatched, _candidate())

    assert result.evaluations[0].candidate_state == "insufficient_evidence"
    assert result.proposed_patch_set.paths == ()


def test_inventory_identity_mismatch_blocks_the_whole_gate(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    mismatched = {**context.as_dict(), "inventory_identity": "sha256:wrong"}

    result = _gate(tmp_path, inventory, mismatched, _candidate())

    assert result.status == "blocked"
    assert result.evaluations == ()


def test_serialized_receipt_authority_escalation_blocks_the_whole_gate(
    tmp_path: Path,
) -> None:
    inventory, context = _ready_fixture(tmp_path)
    receipt = {**context.read_receipts[0].as_dict(), "write_authority": True}
    malformed = {**context.as_dict(), "read_receipts": [receipt]}

    result = _gate(tmp_path, inventory, malformed, _candidate())

    assert result.status == "blocked"
    assert result.evaluations == ()
    assert "authority escalation" in result.errors[0]


def test_gate_inputs_are_not_mutated(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    candidate = _candidate()
    identities = _current(tmp_path, "core/router.py")
    before_candidate = copy.deepcopy(candidate)
    before_identities = copy.deepcopy(identities)

    execute_direct_patch_candidate_gate(
        inventory,
        context,
        [candidate],
        current_file_identities=identities,
    )

    assert candidate == before_candidate
    assert identities == before_identities


def test_every_result_preserves_authority_and_patch_safety_boundaries(
    tmp_path: Path,
) -> None:
    inventory, context = _ready_fixture(tmp_path)
    result = _gate(tmp_path, inventory, context, _candidate()).as_dict()

    assert result["write_authority"] is False
    assert result["patch_application_authority"] is False
    assert result["human_approval_required"] is True
    assert result["patch_safety_required"] is True
    assert result["patch_safety_bypassed"] is False
    for group in (
        "implementation_candidates",
        "validation_candidates",
        "supporting_context",
        "blocked_candidates",
    ):
        for item in result[group]:
            assert item["write_authority"] is False
            assert item["patch_application_authority"] is False
            assert item["human_approval_required"] is True


def test_independence_counters_remain_zero(tmp_path: Path) -> None:
    inventory, context = _ready_fixture(tmp_path)
    rendered = _gate(tmp_path, inventory, context, _candidate()).as_dict()

    assert rendered["canonical_index_used"] is False
    assert rendered["vector_database_used"] is False
    assert rendered["embeddings_used"] is False
    assert rendered["database_operations"] == 0
    assert rendered["graph_constructed"] is False
    assert rendered["parser_used"] is False
    assert rendered["model_used"] is False
    assert rendered["api_calls_made"] is False
    assert rendered["repository_traversals"] == 0
    assert rendered["production_content_reads"] == 0
    assert rendered["filesystem_writes"] == 0
    assert rendered["patches_generated"] == 0
    assert rendered["patches_applied"] == 0
    assert rendered["validation_commands_executed"] == 0
    assert rendered["targeted_identity_checks"] == 1


def test_gate_modules_do_not_import_forbidden_external_systems() -> None:
    forbidden_roots = {
        "requests",
        "httpx",
        "sqlite3",
        "sqlalchemy",
        "subprocess",
        "socket",
        "openai",
        "chromadb",
        "faiss",
        "networkx",
    }

    for module in GATE_MODULES:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imported = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert imported.isdisjoint(forbidden_roots), module.name


def test_gate_source_has_no_patch_generation_or_filesystem_mutation_calls() -> None:
    forbidden_calls = {
        "open",
        "write_text",
        "write_bytes",
        "unlink",
        "replace",
        "rename",
        "rglob",
        "glob",
        "walk",
        "system",
        "run",
        "Popen",
    }

    for module in GATE_MODULES:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        calls = {
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert calls.isdisjoint(forbidden_calls), module.name
