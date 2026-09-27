"""CHECK.LIVE.1B — independent typed worker declaration contract."""

from __future__ import annotations

import dataclasses

import pytest

from core.live_worker_declaration import (
    CHANGE_KIND_UNAVAILABLE_CLAIM,
    DECLARATION_STAGE_COMPLETED,
    LiveWorkerDeclarationInputError,
    DeclaredChangeClaim,
    WorkerChangeDeclaration,
    worker_change_declaration_fingerprint,
    worker_change_declaration_from_mapping,
    worker_declaration_authority,
    worker_declaration_guardrails,
)
from core.live_worker_report import (
    declared_changes_from_worker_declaration,
    declared_status_from_worker_declaration,
    declared_validation_actions_from_worker_declaration,
)
from core.post_run_reconciliation import DeclaredValidationAction


def _mapping(**overrides):
    payload = {
        "declaration_id": "declaration-1",
        "execution_run_id": "run-1",
        "worker_id": "worker-1",
        "declaration_stage": DECLARATION_STAGE_COMPLETED,
        "declared_status": "success",
        "declared_changes": [
            {"path": "core/a.py", "change_kind": "modified"}
        ],
        "declared_validation_actions": [
            {
                "validation_id": "tests",
                "validation_kind": "unit_tests",
                "declared_result": "passed",
            }
        ],
        "limitations": ["Only the typed operation result is declared."],
        "unresolved_items": [],
    }
    payload.update(overrides)
    return payload


def test_a_structured_mapping_builds_one_frozen_bounded_declaration():
    declaration = worker_change_declaration_from_mapping(_mapping())

    assert declaration.declared_changes == (
        DeclaredChangeClaim(path="core/a.py", change_kind="modified"),
    )
    assert declaration.declared_validation_actions == (
        DeclaredValidationAction(
            validation_id="tests",
            validation_kind="unit_tests",
            declared_result="passed",
        ),
    )
    assert len(worker_change_declaration_fingerprint(declaration)) == 64
    assert worker_change_declaration_fingerprint(declaration) == (
        worker_change_declaration_fingerprint(declaration)
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        declaration.declared_status = "failed"


def test_the_worker_report_translation_preserves_only_independent_typed_claims():
    action = DeclaredValidationAction(
        validation_id="tests",
        validation_kind="unit_tests",
        declared_result="passed",
    )
    declaration = WorkerChangeDeclaration(
        declaration_id="declaration-2",
        execution_run_id="run-2",
        worker_id=None,
        declaration_stage=DECLARATION_STAGE_COMPLETED,
        declared_status="partial",
        declared_changes=(
            DeclaredChangeClaim(path="core/b.py", change_kind="added"),
            DeclaredChangeClaim(
                path="core/unknown.py",
                change_kind=CHANGE_KIND_UNAVAILABLE_CLAIM,
            ),
        ),
        declared_validation_actions=(action,),
    )

    changes, untranslated = declared_changes_from_worker_declaration(declaration)
    assert [(item.path, item.change_kind) for item in changes] == [
        ("core/b.py", "added")
    ]
    assert untranslated == ("core/unknown.py",)
    assert declared_status_from_worker_declaration(declaration) == "partial"
    assert declared_validation_actions_from_worker_declaration(declaration) == (
        action,
    )
    assert changes[0].expected_change_identity_sha256 is None


@pytest.mark.parametrize(
    "payload",
    [
        _mapping(write_authority=True),
        _mapping(patch_authority=True),
        _mapping(unexpected=True),
        _mapping(
            declared_changes=[
                {"path": "core/a.py", "change_kind": "teleported"}
            ]
        ),
        _mapping(
            declared_changes=[
                {"path": "core/a.py", "change_kind": "modified"},
                {"path": "core/a.py", "change_kind": "added"},
            ]
        ),
    ],
)
def test_malformed_or_authority_claiming_mappings_fail_closed(payload):
    with pytest.raises(LiveWorkerDeclarationInputError):
        worker_change_declaration_from_mapping(payload)


@pytest.mark.parametrize("path", ["../escape.py", "/rooted.py", "C:/drive.py"])
def test_change_claim_paths_use_the_shared_repository_path_policy(path):
    with pytest.raises((TypeError, ValueError)):
        DeclaredChangeClaim(path=path, change_kind="modified")


def test_rename_claims_require_one_distinct_original_path():
    with pytest.raises(ValueError):
        DeclaredChangeClaim(path="new.py", change_kind="renamed")
    with pytest.raises(ValueError):
        DeclaredChangeClaim(
            path="same.py", change_kind="renamed", from_path="same.py"
        )
    with pytest.raises(ValueError):
        DeclaredChangeClaim(
            path="new.py", change_kind="modified", from_path="old.py"
        )


def test_the_declaration_is_self_report_evidence_and_holds_no_other_authority():
    authority = worker_declaration_authority()
    assert authority == {
        "write_authority": False,
        "patch_authority": False,
        "validation_authority": False,
        "observed_fact_authority": False,
        "worker_self_report_authority": True,
    }
    guardrails = worker_declaration_guardrails()
    assert guardrails["derived_from_patch_plan"] is False
    assert guardrails["derived_from_execution_authorization"] is False
    assert guardrails["derived_from_observed_facts"] is False
    assert guardrails["prose_parsed"] is False
    assert guardrails["model_called"] is False
    assert guardrails["authoritative_effect"] is False

