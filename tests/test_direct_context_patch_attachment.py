"""CTX.APPLY.0 fail-closed attachment and no-authority contract tests."""

from __future__ import annotations

import ast
import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from core.direct_context_runtime import (
    compute_repository_inventory_identity,
    execute_direct_context,
)
from core.direct_context_patch_attachment import (
    ATTACHMENT_STATUSES,
    attach_direct_context_to_patch_safety,
)
from core.direct_patch_candidate_gate import (
    ChangeIntention,
    TargetRange,
    execute_direct_patch_candidate_gate,
)
from core.file_capabilities import classify_file_capability
from core.patch_safety import attach_direct_context_to_patch_safety as safety_attach
from core.repository_identity import derive_repository_id_from_canonical_root
from core.repository_inventory import (
    RepositoryFileIdentity,
    create_repository_inventory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ATTACHMENT_MODULE = PROJECT_ROOT / "core" / "direct_context_patch_attachment.py"


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _proposal(inventory, paths: tuple[str, ...]) -> dict:
    entries = {entry.relative_path.as_posix(): entry for entry in inventory.entries}
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
        {"kind": "change_locality", "detail": "one bounded conditional"},
        {
            "kind": "symbol_or_branch_specificity",
            "detail": "dispatch branch at lines 2-3",
        },
        {"kind": "reversibility", "detail": "one local branch can be reverted"},
    ]


def _intention(start: int = 2, end: int = 3) -> dict:
    return {
        "summary": "Prevent the verified no-change branch from continuing.",
        "target_ranges": [{"start_line": start, "end_line": end}],
        "expected_behavior_change": "Verified no-change runs return early.",
        "must_preserve": ["non-empty delta behavior"],
    }


def _candidate(path: str = "core/router.py", **over) -> dict:
    candidate = {
        "path": path,
        "actionability_score": 96,
        "patchability_evidence": _strong_evidence(),
        "change_intention": _intention(),
        "validation_candidates": ["tests/test_router.py"],
        "blast_radius": "low",
        "role": "primary_or_supporting_target",
        "patch_role": "primary",
    }
    candidate.update(over)
    return candidate


def _fixture(tmp_path: Path, *, include_validation: bool = False):
    source = "core/router.py"
    test = "tests/test_router.py"
    _write(tmp_path, source, "header\nif unchanged:\n    return done\nfallback()\n")
    paths = (source,)
    candidates = [_candidate(source)]
    if include_validation:
        _write(tmp_path, test, "def test_router():\n    assert True\n")
        paths = (source, test)
        candidates.append(
            _candidate(
                test,
                role="validation",
                patch_role="validation",
                change_intention=_intention(1, 2),
                validation_candidates=[test],
            )
        )
    inventory = create_repository_inventory(tmp_path)
    identity = compute_repository_inventory_identity(inventory)
    direct_context = execute_direct_context(
        tmp_path,
        inventory,
        {
            "schema_version": 1,
            "task_id": "run-apply",
            "operation_id": "operation-apply",
            "repository_root": str(tmp_path.resolve()),
            "inventory_identity": identity,
            "selected_files": [
                {"path": path, "requested_mode": "full_file"} for path in paths
            ],
        },
        proposed_read_set=_proposal(inventory, paths),
    )
    current = {
        path: RepositoryFileIdentity.from_stat_result((tmp_path / path).stat())
        for path in paths
    }
    gate = execute_direct_patch_candidate_gate(
        inventory,
        direct_context,
        candidates,
        current_file_identities=current,
    )
    capabilities = [classify_file_capability(path) for path in paths]
    repository_context = {
        "task_id": "run-apply",
        "operation_id": "operation-apply",
        "repository_root": inventory.canonical_root,
        "repository_id": derive_repository_id_from_canonical_root(
            inventory.canonical_root
        ),
        "inventory_identity": identity,
        "inventory": inventory,
        "current_file_identities": current,
        "file_capabilities": capabilities,
        "attachment_created_at": "2026-08-14T00:00:00+00:00",
    }
    return gate, direct_context, repository_context


def _attach(gate, direct_context, repository_context, **over):
    values = {
        "proposed_patch_set": gate,
        "read_receipts": direct_context.read_receipts,
        "repository_context": repository_context,
    }
    values.update(over)
    return attach_direct_context_to_patch_safety(**values)


def test_fresh_bound_candidate_attaches_without_authority(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)

    result = _attach(gate, context, repository_context).as_dict()

    assert result["status"] == "attached"
    assert result["allowed_proposed_targets"] == ["core/router.py"]
    assert result["implementation_targets"][0]["receipt_freshness"] == "fresh"
    assert result["implementation_targets"][0]["target_ranges"] == [
        {"start_line": 2, "end_line": 3}
    ]
    assert result["human_review_request"]["generic_repository_wide_approval_sufficient"] is False
    assert result["human_review_request"]["approval_record_created"] is False
    assert result["human_review_request"]["risk_level"] == "low"
    assert result["human_review_request"]["receipt_freshness"] == [
        {"path": "core/router.py", "status": "fresh"}
    ]
    validation_plan = result["human_review_request"]["validation_plan"]
    assert validation_plan[0]["source_path"] == "core/router.py"
    assert validation_plan[0]["validation_status"] == "mapped"
    assert validation_plan[0]["target_path"] == "tests/test_router.py"
    assert validation_plan[0]["approved_test_modification_target"] is None
    assert "Prevent the verified no-change branch" not in json.dumps(result)
    assert result["implementation_targets"][0]["change_intention_fingerprint"].startswith(
        "sha256:"
    )
    assert result["human_review_request"]["target_change_intentions"][0]["path"] == (
        "core/router.py"
    )
    for key in (
        "write_authority",
        "patch_generation_authority",
        "patch_application_authority",
    ):
        assert result[key] is False
    assert result["human_approval_required"] is True


@pytest.mark.parametrize(
    ("field", "bad_value", "expected"),
    [
        ("task_id", "another-run", "task_id_mismatch"),
        ("repository_root", "C:\\wrong-root", "repository_root_mismatch"),
        ("repository_id", "wrong-repository-id", "repository_id_mismatch"),
        ("inventory_identity", "sha256:wrong", "inventory_identity_mismatch"),
    ],
)
def test_context_binding_mismatches_fail_closed(
    tmp_path: Path, field: str, bad_value: str, expected: str
) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    broken = {**repository_context, field: bad_value}

    result = _attach(gate, context, broken)

    assert result.status == "invalid_evidence"
    assert expected in result.errors
    assert result.implementation_targets == ()


def test_ctx_patch_result_and_receipt_scope_mismatches_fail_closed(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    wrong_gate = replace(gate, task_id="another-run")
    wrong_receipt = replace(context.read_receipts[0], operation_id="another-operation")

    gate_result = _attach(wrong_gate, context, repository_context)
    receipt_result = _attach(
        gate, context, repository_context, read_receipts=(wrong_receipt,)
    )

    assert gate_result.status == "invalid_evidence"
    assert "task_id_mismatch" in gate_result.errors
    assert receipt_result.status == "invalid_evidence"
    assert "receipt_scope_mismatch" in receipt_result.errors


def test_bare_or_serialized_patch_set_is_not_trusted_evidence(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)

    bare = _attach(gate.proposed_patch_set, context, repository_context)
    serialized = _attach(gate.as_dict(), context, repository_context)

    assert bare.status == serialized.status == "invalid_evidence"
    assert "ctx_patch_result_must_be_typed" in bare.errors
    assert "ctx_patch_result_must_be_typed" in serialized.errors


def test_range_not_covered_by_receipt_is_not_attached(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    original = gate.proposed_patch_set.implementation_candidates[0]
    longer_intention = ChangeIntention(
        summary="Bound the target to a later source line.",
        target_ranges=(TargetRange(5, 5),),
        expected_behavior_change="The later branch changes only after review.",
    )
    candidate = replace(original, change_intention=longer_intention)
    plan = replace(gate.proposed_patch_set, implementation_candidates=(candidate,))
    result = _attach(
        replace(gate, proposed_patch_set=plan, evaluations=(candidate,)),
        context,
        repository_context,
    )

    assert result.status == "invalid_evidence"
    assert result.implementation_targets == ()
    assert result.blocked_candidates[0].reason_code == "receipt_does_not_cover_target_ranges"


@pytest.mark.parametrize(
    ("current", "decision", "top_status"),
    [
        ("changed", "reread_required", "reread_required"),
        ("deleted", "candidate_removed", "invalid_evidence"),
        ("replaced", "security_blocked", "security_blocked"),
        ("unverifiable", "attachment_blocked", "invalid_evidence"),
    ],
)
def test_freshness_is_rechecked_at_attachment_boundary(
    tmp_path: Path, current: str, decision: str, top_status: str
) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    path = "core/router.py"
    identity = repository_context["current_file_identities"][path]
    if current == "changed":
        replacement = replace(identity, size_bytes=identity.size_bytes + 1)
    elif current == "deleted":
        replacement = None
    elif current == "replaced":
        replacement = replace(identity, inode=identity.inode + 1)
    else:
        replacement = {"size": 1}
    current_identities = {path: replacement}
    result = _attach(
        gate,
        context,
        {**repository_context, "current_file_identities": current_identities},
    )

    assert result.status == top_status
    assert result.implementation_targets == ()
    assert result.blocked_candidates[0].decision == decision
    assert result.targeted_identity_checks == 1


def test_path_alias_and_duplicate_receipt_fail_closed(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    receipt = context.read_receipts[0]
    path_alias = replace(receipt, path="../outside.py")
    case_alias = replace(receipt, path="CORE/router.py")

    traversal = _attach(
        gate, context, repository_context, read_receipts=(path_alias,)
    )
    collision = _attach(
        gate, context, repository_context, read_receipts=(receipt, case_alias)
    )

    assert traversal.status == "invalid_evidence"
    assert "receipt_path_is_not_repository_relative" in traversal.errors
    assert collision.status == "invalid_evidence"
    assert "receipt_path_not_in_inventory" in collision.errors


def test_capability_blocks_generated_sensitive_and_symlink_targets(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    path = "core/router.py"
    for capability, decision in (
        (classify_file_capability(path, generated=True), "attachment_blocked"),
        (classify_file_capability(path, symlink_escape=True), "security_blocked"),
        (
            classify_file_capability(path, editability="sensitive_requires_approval"),
            "security_blocked",
        ),
    ):
        result = _attach(
            gate,
            context,
            {**repository_context, "file_capabilities": [capability]},
        )
        assert result.implementation_targets == ()
        assert result.blocked_candidates[0].decision == decision


def test_capability_mapping_key_cannot_alias_a_candidate_path(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    capability = classify_file_capability("core/router.py")

    result = _attach(
        gate,
        context,
        {**repository_context, "file_capabilities": {"CORE/router.py": capability}},
    )

    assert result.status == "invalid_evidence"
    assert "capability_path_key_mismatch" in result.errors


def test_validation_candidate_is_evidence_not_a_writable_target(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path, include_validation=True)

    result = _attach(gate, context, repository_context).as_dict()

    assert result["allowed_proposed_targets"] == ["core/router.py"]
    assert [item["path"] for item in result["validation_evidence"]] == [
        "tests/test_router.py"
    ]
    validation = result["validation_evidence"][0]
    assert validation["validation_only"] is True
    assert validation["approved_test_modification_target"] is None
    assert validation["write_authority"] is False


def test_validation_command_is_fingerprinted_but_never_serialized(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    original = gate.proposed_patch_set.implementation_candidates[0]
    command = "pytest tests/test_router.py --api-key not-for-review-123456789"
    mapping = replace(original.validation_candidates[0], target=command)
    candidate = replace(original, validation_candidates=(mapping,))
    plan = replace(gate.proposed_patch_set, implementation_candidates=(candidate,))
    altered_gate = replace(
        gate,
        proposed_patch_set=plan,
        evaluations=(candidate,),
    )

    rendered = _attach(altered_gate, context, repository_context).as_dict()
    validation = rendered["human_review_request"]["validation_plan"][0]

    assert validation["target_path"] is None
    assert validation["target_fingerprint"].startswith("sha256:")
    assert command not in json.dumps(rendered)


def test_existing_patch_safety_can_narrow_but_cannot_be_bypassed(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    calls: list[tuple[str, ...]] = []

    def block_policy(paths, **_kwargs):
        calls.append(tuple(paths))
        return {
            "ok": False,
            "blocked_paths": [
                {"path": "core/router.py", "reason": "review policy", "category": "other"}
            ],
            "reasons": ["review policy"],
        }

    result = _attach(
        gate, context, repository_context, existing_patch_policy=block_policy
    )

    assert calls == [("core/router.py",)]
    assert result.status == "policy_blocked"
    assert result.blocked_candidates[0].reason_code == "existing_patch_safety_blocked"
    assert result.eligible_for_patch_safety_review is False


def test_patch_safety_namespace_lazily_exposes_the_same_adapter(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)

    result = safety_attach(
        proposed_patch_set=gate,
        read_receipts=context.read_receipts,
        repository_context=repository_context,
    )

    assert result.status == "attached"


def test_review_states_attach_only_with_explicit_review(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    original = gate.proposed_patch_set.implementation_candidates[0]
    reviewed = replace(original, candidate_state="high_blast_radius_review", blast_radius="high")
    plan = replace(gate.proposed_patch_set, implementation_candidates=(reviewed,))

    result = _attach(
        replace(gate, proposed_patch_set=plan, evaluations=(reviewed,)),
        context,
        repository_context,
    )

    assert result.status == "attached_with_review"
    assert result.implementation_targets[0].candidate_state == "high_blast_radius_review"
    assert "high_blast_radius_review" in result.human_review_points


def test_secret_like_change_intention_is_blocked_and_never_serialized(
    tmp_path: Path,
) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    original = gate.proposed_patch_set.implementation_candidates[0]
    secret = "Keep API_KEY=not-for-review-123456789 intact."
    intention = replace(original.change_intention, summary=secret)
    candidate = replace(original, change_intention=intention)
    plan = replace(gate.proposed_patch_set, implementation_candidates=(candidate,))

    result = _attach(
        replace(gate, proposed_patch_set=plan, evaluations=(candidate,)),
        context,
        repository_context,
    )
    rendered = json.dumps(result.as_dict())

    assert result.status == "invalid_evidence"
    assert result.blocked_candidates[0].reason_code == (
        "change_summary_may_contain_sensitive_content"
    )
    assert secret not in rendered
    assert "not-for-review-123456789" not in rendered


@pytest.mark.parametrize(
    "additional_context",
    [
        {"patch_generation_authority": True},
        {"human_approval_required": False},
    ],
)
def test_context_cannot_supply_authority_or_bypass_human_approval(
    tmp_path: Path, additional_context: dict[str, object]
) -> None:
    gate, context, repository_context = _fixture(tmp_path)

    result = _attach(gate, context, {**repository_context, **additional_context})

    assert result.status == "invalid_evidence"
    assert result.implementation_targets == ()


@pytest.mark.parametrize(
    "terminal_status",
    ["blocked", "reread_required", "human_file_selection_required"],
)
def test_terminal_patch_set_status_cannot_attach_candidates(
    tmp_path: Path, terminal_status: str
) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    plan = replace(gate.proposed_patch_set, status=terminal_status)
    terminal_gate = replace(
        gate,
        patch_candidate_status=terminal_status,
        proposed_patch_set=plan,
    )

    result = _attach(terminal_gate, context, repository_context)

    assert result.status == "invalid_evidence"
    assert result.implementation_targets == ()
    assert result.errors == ("terminal_patch_set_status_has_candidates",)


def test_proposed_candidate_must_match_its_original_gate_evaluation(
    tmp_path: Path,
) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    original = gate.proposed_patch_set.implementation_candidates[0]
    tampered = replace(original, blast_radius="high")
    plan = replace(gate.proposed_patch_set, implementation_candidates=(tampered,))

    result = _attach(replace(gate, proposed_patch_set=plan), context, repository_context)

    assert result.status == "invalid_evidence"
    assert result.errors == ("proposed_candidate_not_backed_by_gate_evaluation",)


def test_proposal_identity_binds_candidate_scope_and_risk(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    original = gate.proposed_patch_set.implementation_candidates[0]
    changed = replace(original, blast_radius="high")
    changed_plan = replace(
        gate.proposed_patch_set,
        implementation_candidates=(changed,),
    )
    changed_gate = replace(
        gate,
        proposed_patch_set=changed_plan,
        evaluations=(changed,),
    )

    baseline = _attach(gate, context, repository_context)
    revised = _attach(changed_gate, context, repository_context)

    assert baseline.proposed_patch_set_identity != revised.proposed_patch_set_identity
    assert revised.status == "attached_with_review"


def test_inputs_are_not_mutated_and_output_is_deterministic(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    before_gate = copy.deepcopy(gate)
    before_receipts = copy.deepcopy(context.read_receipts)
    before_repository_context = copy.deepcopy(repository_context)

    first = _attach(gate, context, repository_context).as_dict()
    second = _attach(gate, context, repository_context).as_dict()

    assert gate == before_gate
    assert context.read_receipts == before_receipts
    assert repository_context == before_repository_context
    assert first["attachment_fingerprint"] == second["attachment_fingerprint"]


def test_result_schema_is_bounded_and_independent(tmp_path: Path) -> None:
    gate, context, repository_context = _fixture(tmp_path)
    rendered = _attach(gate, context, repository_context).as_dict()

    assert rendered["raw_file_content_included"] is False
    assert rendered["security_redacted"] is True
    assert rendered["repository_traversals"] == 0
    assert rendered["production_content_reads"] == 0
    assert rendered["filesystem_writes"] == 0
    assert rendered["patches_generated"] == 0
    assert rendered["patches_applied"] == 0
    assert rendered["validation_commands_executed"] == 0
    assert rendered["database_operations"] == 0
    assert rendered["model_calls"] == 0
    assert set(ATTACHMENT_STATUSES) >= {rendered["status"]}


def test_attachment_source_has_no_mutation_or_execution_calls() -> None:
    tree = ast.parse(ATTACHMENT_MODULE.read_text(encoding="utf-8"))
    calls = {
        node.func.id
        if isinstance(node.func, ast.Name)
        else node.func.attr
        if isinstance(node.func, ast.Attribute)
        else ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }

    assert not calls & {
        "open",
        "write_text",
        "write_bytes",
        "unlink",
        "replace",
        "rename",
        "rglob",
        "glob",
        "walk",
        "run",
        "Popen",
        "apply_patch",
    }
