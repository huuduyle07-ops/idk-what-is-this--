"""CHECK.LIVE.1 — shadow post-run reconciliation wiring.

These tests exercise the *live* path: a real patch plan is applied by the real
apply engine against a real temporary repository, the real validation command
runs, and the shadow observer produces CHECK.1's inputs from what that run
actually did.  Fixtures construct CHECK.1 records directly only where the live
path structurally cannot reach a case yet, and those tests say so.

The invariant every one of them protects is the same: whatever CHECK.1 says,
the authoritative run result is exactly what it would have been without this
phase.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

import core.run_lifecycle as run_lifecycle
from core.live_change_observation import (
    LivePathDigests,
    derive_observed_change_records,
    digest_known_paths,
    observed_change_state_fingerprint,
)
from core.live_execution_authorization import (
    LiveAuthorityWideningError,
    build_live_execution_authorization,
    live_authorization_fingerprint,
    upstream_authority_from_patch_safety,
)
from core.live_worker_declaration import (
    DECLARATION_SOURCE_INDEPENDENT,
    DECLARATION_SOURCE_LEGACY_PLAN_DERIVED,
    DECLARATION_SOURCE_UNAVAILABLE,
    DeclaredChangeClaim,
    WorkerChangeDeclaration,
)
from core.live_validation_receipt import (
    LIVE_VALIDATION_ID,
    build_live_validation_expectation,
    build_live_validation_receipt,
    live_validation_receipt_fingerprint,
)
from core.live_worker_report import (
    build_live_worker_report,
    declared_changes_from_patch_plan,
    declared_status_from_apply_outcome,
)
from core.patch_safety import evaluate_patch_safety
from core.validation_bytecode_cache import VALIDATION_PYCACHE_DIR_PREFIX
from core.post_run_observation import (
    build_observed_post_run_facts,
    observed_changes_from_records,
)
from core.post_run_reconciliation import (
    PATH_AUTHORITY_FORBIDDEN,
    PATH_AUTHORITY_SUPPORTING_READ_ONLY,
    PATH_AUTHORITY_WRITABLE,
    DeclaredValidationAction,
    PostRunReconciliationRequest,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_RECONCILED,
    STATUS_SUSPICIOUS,
    observed_post_run_facts_fingerprint,
    reconcile_post_run,
    worker_report_fingerprint,
)
from core.post_run_reconciliation_shadow import (
    COMPLETENESS_COMPLETE,
    COMPLETENESS_PARTIAL,
    COMPLETENESS_UNAVAILABLE,
    DISAGREEMENT_CHECKER_STRICTER,
    DISAGREEMENT_NONE,
    DISAGREEMENT_NOT_COMPARABLE,
    ENVIRONMENT_FLAG,
    INCOMPLETE_OBSERVED_CHANGE_IDENTITY,
    MISSING_OBSERVED_CHANGE_IDENTITY,
    MISSING_VALIDATION_RECEIPT,
    NOT_REACHED_BOUNDARY,
    RESULT_METADATA_KEYS,
    RUN_STATUS_SUCCESS,
    SHADOW_ARTIFACT_NAME,
    SHADOW_CHECKER_ERROR,
    SHADOW_EVALUATED,
    SHADOW_NOT_REACHED,
    LiveExecutionObservation,
    is_post_run_reconciliation_shadow_enabled,
    load_shadow_post_run_check,
    run_shadow_post_run_reconciliation,
    safe_run_shadow_post_run_reconciliation,
    shadow_disagreement,
)


PASSING_VALIDATION = 'python -c "raise SystemExit(0)"'
FAILING_VALIDATION = 'python -c "raise SystemExit(1)"'


# ── Harness ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _quiet_brain_stamp(monkeypatch):
    """The brain stamp shells out to git; it is irrelevant to this phase."""
    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo: {"brain_stamp_id": "stamp", "schema_version": 2},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    return project


def _enable(monkeypatch, enabled: bool = True) -> None:
    if enabled:
        monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    else:
        monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)


def _edit_main(patched: str = "VALUE = 2\n") -> list[dict]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": "main.py",
            "target_snippet": "VALUE = 1\n",
            "patched_snippet": patched,
        }
    ]


def _run(repo: Path, plan: list[dict], **kwargs) -> dict:
    return run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), plan, source="unit", **kwargs
    )


def _receipt(result: dict) -> dict:
    replay_dir = Path(result["replay_dir"])
    payload = json.loads(
        (replay_dir / SHADOW_ARTIFACT_NAME).read_text(encoding="utf-8")
    )
    assert payload["authoritative_effect"] is False
    return payload


def _declaration(
    *changes: tuple[str, str],
    validation_passed: bool | None = True,
) -> WorkerChangeDeclaration:
    actions = (
        (
            DeclaredValidationAction(
                validation_id=LIVE_VALIDATION_ID,
                validation_kind="unit_tests",
                declared_result="passed" if validation_passed else "failed",
            ),
        )
        if validation_passed is not None
        else ()
    )
    return WorkerChangeDeclaration(
        declaration_id="worker-declaration",
        execution_run_id="worker-known-run",
        worker_id="worker-1",
        declaration_stage="completed",
        declared_status="success" if validation_passed is not False else "failed",
        declared_changes=tuple(
            DeclaredChangeClaim(path=path, change_kind=kind)
            for path, kind in changes
        ),
        declared_validation_actions=actions,
    )


# ── The flag ──────────────────────────────────────────────────────────────────

def test_the_shadow_observer_is_disabled_unless_explicitly_enabled(monkeypatch):
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    assert is_post_run_reconciliation_shadow_enabled() is False
    for value in ("", "0", "false", "no", "off", "maybe"):
        monkeypatch.setenv(ENVIRONMENT_FLAG, value)
        assert is_post_run_reconciliation_shadow_enabled() is False
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(ENVIRONMENT_FLAG, value)
        assert is_post_run_reconciliation_shadow_enabled() is True


def test_a_disabled_shadow_leaves_the_run_result_untouched(repo, monkeypatch):
    _enable(monkeypatch, False)
    result = _run(
        repo,
        _edit_main(),
        validation_command=PASSING_VALIDATION,
        worker_declaration=_declaration(("main.py", "modified")),
    )

    assert result["success"] is True
    for key in RESULT_METADATA_KEYS:
        assert key not in result
    replay_dir = Path(result["replay_dir"])
    assert not (replay_dir / SHADOW_ARTIFACT_NAME).exists()


# ── A clean live run ──────────────────────────────────────────────────────────

def test_a_clean_live_run_reconciles_without_changing_the_run(repo, monkeypatch):
    _enable(monkeypatch)
    result = _run(repo, _edit_main(), validation_command=PASSING_VALIDATION)

    assert result["success"] is True
    assert result["rollback_performed"] is False
    assert (repo / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"

    receipt = _receipt(result)
    assert receipt["shadow_outcome"] == SHADOW_EVALUATED
    assert receipt["reconciliation_status"] == STATUS_RECONCILED
    assert receipt["producer_completeness"] == COMPLETENESS_COMPLETE
    assert receipt["disagreement"] == DISAGREEMENT_NONE
    assert receipt["authoritative_run_status"] == RUN_STATUS_SUCCESS
    assert receipt["observation"]["observed_change_paths"] == ["main.py"]
    assert receipt["observation"]["validation_receipt_result"] == "passed"
    assert receipt["observation"]["validated_state_is_final_state"] is True
    assert receipt["reconciliation"]["inconsistencies"] == []
    assert receipt["worker_declaration_source"] == (
        DECLARATION_SOURCE_LEGACY_PLAN_DERIVED
    )
    assert receipt["worker_declaration_invalid"] is False
    assert receipt["independent_worker_declaration_missing"] is True

    assert result["post_run_reconciliation_available"] is True
    assert result["post_run_reconciliation_status"] == STATUS_RECONCILED
    assert result["post_run_reconciliation_authoritative_effect"] is False


def test_an_independent_declaration_can_exactly_agree_with_a_live_run(
    repo, monkeypatch
):
    _enable(monkeypatch)
    declaration = _declaration(("main.py", "modified"))

    result = _run(
        repo,
        _edit_main(),
        validation_command=PASSING_VALIDATION,
        worker_declaration=declaration,
    )
    receipt = _receipt(result)

    assert result["success"] is True
    assert receipt["worker_declaration_source"] == DECLARATION_SOURCE_INDEPENDENT
    assert receipt["worker_declaration_invalid"] is False
    assert receipt["independent_worker_declaration_missing"] is False
    assert receipt["reconciliation_status"] == STATUS_RECONCILED
    assert receipt["reconciliation"]["change_findings"][0]["classification"] == (
        "matched"
    )


def test_an_independent_declaration_omission_is_measured_by_the_live_run(
    repo, monkeypatch
):
    _enable(monkeypatch)
    (repo / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
    plan = _edit_main() + [
        {
            "op": "replace_snippet",
            "relative_path": "other.py",
            "target_snippet": "OTHER = 1\n",
            "patched_snippet": "OTHER = 2\n",
        }
    ]

    result = _run(
        repo,
        plan,
        validation_command=PASSING_VALIDATION,
        worker_declaration=_declaration(("main.py", "modified")),
    )
    receipt = _receipt(result)
    findings = receipt["reconciliation"]["change_findings"]

    assert result["success"] is True
    assert receipt["worker_declaration_source"] == DECLARATION_SOURCE_INDEPENDENT
    assert receipt["reconciliation_status"] == STATUS_SUSPICIOUS
    assert [
        item["path"]
        for item in findings
        if item["classification"] == "undeclared_change"
    ] == ["other.py"]


def test_an_independent_declaration_overclaim_is_measured_by_the_live_run(
    repo, monkeypatch
):
    _enable(monkeypatch)
    declaration = _declaration(
        ("main.py", "modified"),
        ("other.py", "added"),
    ).as_dict()
    declaration.pop("phase_id")
    result = _run(
        repo,
        _edit_main(),
        validation_command=PASSING_VALIDATION,
        worker_declaration=declaration,
    )
    receipt = _receipt(result)
    findings = receipt["reconciliation"]["change_findings"]

    assert result["success"] is True
    assert receipt["worker_declaration_source"] == DECLARATION_SOURCE_INDEPENDENT
    assert [
        item["path"]
        for item in findings
        if item["classification"] == "declared_but_unobserved_change"
    ] == ["other.py"]


@pytest.mark.parametrize(
    "declaration",
    [
        {
            "declaration_id": "invalid-kind",
            "execution_run_id": "worker-run",
            "worker_id": None,
            "declaration_stage": "completed",
            "declared_status": "success",
            "declared_changes": [
                {"path": "main.py", "change_kind": "teleported"}
            ],
        },
        {
            "declaration_id": "unknown-key",
            "execution_run_id": "worker-run",
            "worker_id": None,
            "declaration_stage": "completed",
            "declared_status": "success",
            "declared_changes": [],
            "patch_authority": True,
        },
    ],
)
def test_an_invalid_declaration_falls_back_and_is_never_silent(
    repo, monkeypatch, declaration
):
    _enable(monkeypatch)
    result = _run(
        repo,
        _edit_main(),
        validation_command=PASSING_VALIDATION,
        worker_declaration=declaration,
    )
    receipt = _receipt(result)

    assert result["success"] is True
    assert receipt["reconciliation_status"] == STATUS_RECONCILED
    assert receipt["worker_declaration_source"] == (
        DECLARATION_SOURCE_LEGACY_PLAN_DERIVED
    )
    assert receipt["worker_declaration_invalid"] is True
    assert receipt["independent_worker_declaration_missing"] is True


def test_the_shadow_result_never_asserts_a_semantic_verdict(repo, monkeypatch):
    _enable(monkeypatch)
    receipt = _receipt(_run(repo, _edit_main(), validation_command=PASSING_VALIDATION))
    rendered = json.dumps(receipt)

    for forbidden in (
        "goal_satisfied",
        "implementation_good",
        "semantically_correct",
        "merge_ready",
    ):
        assert forbidden not in rendered, forbidden

    authority = receipt["reconciliation"]["authority"]
    for denied in (
        "final_success_authority",
        "implementation_correctness_authority",
        "merge_authority",
        "patch_authority",
        "semantic_goal_review_authority",
        "write_authority",
    ):
        assert authority[denied] is False, denied

    unresolved = receipt["reconciliation"]["unresolved_requirements"]
    assert "semantic_goal_review_required" in unresolved
    assert "human_review_required" in unresolved


# ── Undeclared, forbidden and out-of-scope changes ────────────────────────────

def test_an_undeclared_change_on_an_authorized_path_is_suspicious(repo):
    """Live producers, sub-plan declaration: A and B authorized, only A declared.

    The fully wired path derives both the declaration and the authorization from
    one patch plan, so it cannot currently produce this divergence on its own —
    that limitation is recorded in the phase design.  The producers themselves
    must still classify it correctly the moment a worker declaration becomes
    independent of the applied operations.
    """
    (repo / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
    targets = ("main.py", "other.py")
    before = digest_known_paths(repo, targets)
    (repo / "main.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "other.py").write_text("OTHER = 2\n", encoding="utf-8")
    after = digest_known_paths(repo, targets)
    change_set = derive_observed_change_records(before, after)
    assert len(change_set.records) == 2

    verdict = evaluate_patch_safety(list(targets), project_root=repo)
    authority, reasons, fingerprint = upstream_authority_from_patch_safety(
        targets, verdict
    )
    assert authority == {
        "main.py": PATH_AUTHORITY_WRITABLE,
        "other.py": PATH_AUTHORITY_WRITABLE,
    }

    pre = observed_change_state_fingerprint("repo-id", before, ())
    final = observed_change_state_fingerprint("repo-id", before, change_set.records)
    authorization = build_live_execution_authorization(
        execution_run_id="run-1",
        repository_id="repo-id",
        task_contract_fingerprint=pre,
        pre_execution_state_fingerprint=pre,
        upstream_authority=authority,
        upstream_forbidden_reasons=reasons,
        upstream_authority_fingerprint=fingerprint,
    )
    declared, _untranslated = declared_changes_from_patch_plan(
        [
            {
                "op": "replace_snippet",
                "relative_path": "main.py",
                "target_snippet": "x",
                "patched_snippet": "y",
            }
        ]
    )
    report = build_live_worker_report(
        execution_run_id="run-1",
        declared_status=declared_status_from_apply_outcome(
            apply_succeeded=True, rollback_performed=False, blocked=False
        ),
        declared_changes=declared,
    )
    facts = build_observed_post_run_facts(
        facts_id="facts-1",
        execution_run_id="run-1",
        repository_id="repo-id",
        pre_execution_state_fingerprint=pre,
        post_execution_state_fingerprint=final,
        final_state_fingerprint=final,
        observed_changes=observed_changes_from_records(change_set.records),
    )
    outcome = reconcile_post_run(
        PostRunReconciliationRequest(
            authorization=authorization,
            worker_report=report,
            observed_facts=facts,
            expected_task_contract_fingerprint=pre,
            expected_authorization_fingerprint=live_authorization_fingerprint(
                authorization
            ),
            expected_worker_report_fingerprint=worker_report_fingerprint(report),
            expected_observed_facts_fingerprint=(
                observed_post_run_facts_fingerprint(facts)
            ),
        )
    )

    assert outcome.status == STATUS_SUSPICIOUS
    assert [item.path for item in outcome.undeclared_changes] == ["other.py"]
    assert "undeclared_change_observed" in outcome.inconsistencies


def test_a_declared_forbidden_path_is_never_treated_as_authorized(repo):
    """Declared is not authorized: the gate's own verdict wins.

    The live apply path refuses such a plan before it writes anything, so this
    exercises the producers directly with the fact set that would exist if a
    forbidden path had nonetheless changed.
    """
    targets = ("main.py", ".env")
    verdict = evaluate_patch_safety(list(targets), project_root=repo)
    authority, reasons, fingerprint = upstream_authority_from_patch_safety(
        targets, verdict
    )
    assert authority[".env"] == PATH_AUTHORITY_FORBIDDEN
    assert reasons[".env"] == "env"

    before = LivePathDigests(digests=((".env", None), ("main.py", "a" * 64)))
    records = (
        {
            "path": ".env",
            "change_kind": "added",
            "before_sha256": None,
            "after_sha256": "b" * 64,
        },
    )
    pre = observed_change_state_fingerprint("repo-id", before, ())
    final = observed_change_state_fingerprint("repo-id", before, records)
    authorization = build_live_execution_authorization(
        execution_run_id="run-2",
        repository_id="repo-id",
        task_contract_fingerprint=pre,
        pre_execution_state_fingerprint=pre,
        upstream_authority=authority,
        upstream_forbidden_reasons=reasons,
        upstream_authority_fingerprint=fingerprint,
    )
    declared, _ = declared_changes_from_patch_plan(
        [{"op": "create_file", "relative_path": ".env", "content": "S=1"}]
    )
    report = build_live_worker_report(
        execution_run_id="run-2",
        declared_status="success",
        declared_changes=declared,
    )
    facts = build_observed_post_run_facts(
        facts_id="facts-2",
        execution_run_id="run-2",
        repository_id="repo-id",
        pre_execution_state_fingerprint=pre,
        post_execution_state_fingerprint=final,
        final_state_fingerprint=final,
        observed_changes=observed_changes_from_records(records),
    )
    outcome = reconcile_post_run(
        PostRunReconciliationRequest(
            authorization=authorization,
            worker_report=report,
            observed_facts=facts,
            expected_task_contract_fingerprint=pre,
            expected_authorization_fingerprint=live_authorization_fingerprint(
                authorization
            ),
            expected_worker_report_fingerprint=worker_report_fingerprint(report),
            expected_observed_facts_fingerprint=(
                observed_post_run_facts_fingerprint(facts)
            ),
        )
    )

    assert outcome.status == STATUS_BLOCKED
    assert "forbidden_path_changed" in outcome.inconsistencies
    assert [item.path for item in outcome.forbidden_changes] == [".env"]


def test_an_independent_declaration_cannot_authorize_a_forbidden_live_fact(repo):
    before = digest_known_paths(repo, (".env",))
    (repo / ".env").write_text("SECRET=changed\n", encoding="utf-8")
    plan = ({"op": "create_file", "relative_path": ".env", "content": "x"},)
    receipt = run_shadow_post_run_reconciliation(
        LiveExecutionObservation(
            project_root=str(repo),
            execution_run_id="forbidden-run",
            authoritative_run_status=RUN_STATUS_SUCCESS,
            plan=plan,
            patch_safety_verdict=evaluate_patch_safety(
                [".env"], project_root=repo
            ),
            pre_apply_digests=before,
            apply_succeeded=True,
            worker_declaration=_declaration(
                (".env", "added"), validation_passed=None
            ),
        )
    )

    assert receipt.worker_declaration_source == DECLARATION_SOURCE_INDEPENDENT
    assert receipt.reconciliation_status == STATUS_BLOCKED
    assert receipt.reconciliation is not None
    assert "forbidden_path_changed" in receipt.reconciliation["inconsistencies"]


def test_an_independent_kind_mismatch_uses_the_real_change_observer(repo):
    before = digest_known_paths(repo, ("main.py",))
    (repo / "main.py").unlink()
    plan = tuple(_edit_main())
    receipt = run_shadow_post_run_reconciliation(
        LiveExecutionObservation(
            project_root=str(repo),
            execution_run_id="kind-mismatch-run",
            authoritative_run_status=RUN_STATUS_SUCCESS,
            plan=plan,
            patch_safety_verdict=evaluate_patch_safety(
                ["main.py"], project_root=repo
            ),
            pre_apply_digests=before,
            apply_succeeded=True,
            worker_declaration=_declaration(
                ("main.py", "modified"), validation_passed=None
            ),
        )
    )

    assert receipt.reconciliation is not None
    assert receipt.observation["observed_change_paths"] == ["main.py"]
    assert receipt.reconciliation["change_findings"][0]["classification"] == (
        "declared_change_kind_mismatch"
    )


def test_a_validation_side_effect_outside_scope_blocks_in_shadow(repo, monkeypatch):
    """A live run whose validation writes an unauthorized file is blocked."""
    _enable(monkeypatch)
    result = _run(
        repo,
        _edit_main(),
        validation_command=(
            'python -c "open(\'.env\',\'w\').write(\'SECRET=1\')"'
        ),
    )

    assert result["success"] is True  # authoritative outcome unchanged
    receipt = _receipt(result)
    assert receipt["reconciliation_status"] == STATUS_BLOCKED
    assert receipt["disagreement"] == DISAGREEMENT_CHECKER_STRICTER
    assert ".env" in receipt["observation"]["observed_change_paths"]
    assert "out_of_authorized_scope_change" in receipt["reconciliation"][
        "inconsistencies"
    ]


# ── Validation receipts ───────────────────────────────────────────────────────

def test_a_failed_validation_still_emits_a_typed_receipt(repo, monkeypatch):
    _enable(monkeypatch)
    result = _run(repo, _edit_main(), validation_command=FAILING_VALIDATION)

    assert result["success"] is False
    assert result["rollback_performed"] is True
    assert (repo / "main.py").read_text(encoding="utf-8") == "VALUE = 1\n"

    receipt = _receipt(result)
    assert receipt["observation"]["validation_receipt_result"] == "failed"
    assert receipt["reconciliation_status"] == STATUS_BLOCKED
    assert "required_validation_failed" in receipt["reconciliation"][
        "inconsistencies"
    ]
    assert receipt["disagreement"] == DISAGREEMENT_NONE


def test_a_validation_that_never_ran_is_missing_not_failed(repo, monkeypatch):
    """An apply failure aborts before validation; that is not a red check."""
    _enable(monkeypatch)
    plan = [
        {
            "op": "replace_snippet",
            "relative_path": "main.py",
            "target_snippet": "NOT PRESENT\n",
            "patched_snippet": "x\n",
        }
    ]
    result = _run(repo, plan, validation_command=PASSING_VALIDATION)

    assert result["success"] is False
    receipt = _receipt(result)
    assert receipt["observation"]["validation_receipt_result"] is None
    assert MISSING_VALIDATION_RECEIPT in receipt["missing_live_facts"]
    inconsistencies = receipt["reconciliation"]["inconsistencies"]
    assert "required_validation_missing" in inconsistencies
    assert "required_validation_failed" not in inconsistencies
    assert receipt["reconciliation_status"] == STATUS_INCOMPLETE


def test_a_validation_claim_with_no_bindable_receipt_stays_unverified(
    tmp_path, monkeypatch
):
    """The validation genuinely passed, but no receipt could be bound to it.

    A plan wider than the receipt's target-scope bound leaves the typed worker
    validation claim standing with nothing to discharge it.  CHECK.1 must see
    an unverified claim, and no prose may be consulted to invent a receipt.
    """
    _enable(monkeypatch)
    from core.post_run_reconciliation import MAX_TARGET_SCOPE_ENTRIES

    project = tmp_path / "wide"
    project.mkdir()
    plan = []
    for index in range(MAX_TARGET_SCOPE_ENTRIES + 1):
        name = f"mod_{index:03d}.py"
        (project / name).write_text("VALUE = 1\n", encoding="utf-8")
        plan.append(
            {
                "op": "replace_snippet",
                "relative_path": name,
                "target_snippet": "VALUE = 1\n",
                "patched_snippet": "VALUE = 2\n",
            }
        )

    result = _run(project, plan, validation_command=PASSING_VALIDATION)
    assert result["success"] is True

    receipt = _receipt(result)
    assert receipt["observation"]["validation_receipt_result"] is None
    assert MISSING_VALIDATION_RECEIPT in receipt["missing_live_facts"]
    assert "unverified_worker_validation_claim" in receipt["reconciliation"][
        "inconsistencies"
    ]
    assert receipt["reconciliation_status"] == STATUS_SUSPICIOUS
    assert receipt["producer_completeness"] == COMPLETENESS_PARTIAL


def test_a_stale_validation_is_detected_through_the_live_producer_path(
    repo, monkeypatch
):
    """The validation itself moves the state it just validated."""
    _enable(monkeypatch)
    result = _run(
        repo,
        _edit_main(),
        validation_command=(
            'python -c "open(\'generated_note.txt\',\'w\').write(\'x\')"'
        ),
    )

    assert result["success"] is True
    receipt = _receipt(result)
    assert receipt["observation"]["validated_state_is_final_state"] is False
    assert receipt["observation"]["validation_window_paths"] == [
        "generated_note.txt"
    ]
    assert "validation_stale_for_final_state" in receipt["reconciliation"][
        "inconsistencies"
    ]
    stale = [
        finding
        for finding in receipt["reconciliation"]["validation_findings"]
        if finding["coverage"] == "stale"
    ]
    assert [item["validation_id"] for item in stale] == [LIVE_VALIDATION_ID]


# ── Empty, early and failing observation ──────────────────────────────────────

def test_a_no_op_run_reports_an_empty_change_set_not_a_missing_one(
    repo, monkeypatch
):
    _enable(monkeypatch)
    result = _run(repo, _edit_main(patched="VALUE = 1\n"))

    assert result["success"] is True
    receipt = _receipt(result)
    assert receipt["observation"]["observed_change_set_empty"] is True
    assert receipt["observation"]["observed_change_paths"] == []
    assert MISSING_OBSERVED_CHANGE_IDENTITY not in receipt["missing_live_facts"]
    assert receipt["shadow_outcome"] == SHADOW_EVALUATED
    summary = receipt["reconciliation"]["observed_change_summary"]
    assert summary == {
        "added_paths": [],
        "deleted_paths": [],
        "modified_paths": [],
        "renamed_paths": [],
    }


def test_a_run_with_no_plan_and_no_declaration_records_source_unavailable(repo):
    receipt = run_shadow_post_run_reconciliation(
        LiveExecutionObservation(
            project_root=str(repo),
            execution_run_id="empty-run",
            authoritative_run_status=RUN_STATUS_SUCCESS,
            plan=(),
            patch_safety_verdict=evaluate_patch_safety([], project_root=repo),
            pre_apply_digests=digest_known_paths(repo, ()),
            apply_succeeded=True,
        )
    )

    assert receipt.worker_declaration_source == DECLARATION_SOURCE_UNAVAILABLE
    assert receipt.worker_declaration_invalid is False
    assert receipt.independent_worker_declaration_missing is True


def test_an_early_error_run_never_reaches_the_post_run_boundary(
    repo, monkeypatch
):
    _enable(monkeypatch)
    plan = [{"op": "create_file", "relative_path": ".env", "content": "S=1\n"}]
    result = _run(repo, plan)

    assert result["success"] is False
    assert "blocked by safety gate" in result["message"]
    assert not (repo / ".env").exists()

    receipt = _receipt(result)
    assert receipt["shadow_outcome"] == SHADOW_NOT_REACHED
    assert receipt["reconciliation_status"] is None
    assert receipt["reconciliation_available"] is False
    assert receipt["producer_completeness"] == COMPLETENESS_UNAVAILABLE
    assert receipt["not_reached_reason"] == NOT_REACHED_BOUNDARY
    assert MISSING_OBSERVED_CHANGE_IDENTITY in receipt["missing_live_facts"]


def test_a_producer_failure_is_isolated_and_invents_no_reconciliation(
    repo, monkeypatch
):
    _enable(monkeypatch)

    def _explode(*_args, **_kwargs):
        raise RuntimeError("observed-fact producer failed")

    monkeypatch.setattr(
        "core.post_run_reconciliation_shadow.observe_final_change_set", _explode
    )
    result = _run(repo, _edit_main(), validation_command=PASSING_VALIDATION)

    assert result["success"] is True
    assert (repo / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    receipt = _receipt(result)
    assert receipt["shadow_outcome"] == SHADOW_CHECKER_ERROR
    assert receipt["reconciliation_status"] is None
    assert receipt["shadow_error_category"] == "unexpected_shadow_error"
    assert receipt["producer_completeness"] == COMPLETENESS_UNAVAILABLE


def test_a_checker_failure_carries_no_traceback_or_command_text(repo, monkeypatch):
    _enable(monkeypatch)

    def _explode(*_args, **_kwargs):
        raise RuntimeError("SECRET_TOKEN=abcdef traceback detail")

    monkeypatch.setattr(
        "core.post_run_reconciliation_shadow.reconcile_post_run", _explode
    )
    result = _run(repo, _edit_main(), validation_command=PASSING_VALIDATION)

    rendered = json.dumps(_receipt(result))
    assert "SECRET_TOKEN" not in rendered
    assert "traceback" not in rendered.lower()
    assert result["success"] is True


# ── Authoritative outcome preservation ────────────────────────────────────────

@pytest.mark.parametrize(
    "plan_factory, validation, expected_success",
    [
        (lambda: _edit_main(), None, True),
        (lambda: _edit_main(), PASSING_VALIDATION, True),
        (lambda: _edit_main(), FAILING_VALIDATION, False),
        (
            lambda: [
                {
                    "op": "replace_snippet",
                    "relative_path": "main.py",
                    "target_snippet": "MISSING\n",
                    "patched_snippet": "x\n",
                }
            ],
            None,
            False,
        ),
        (
            lambda: [
                {"op": "create_file", "relative_path": ".env", "content": "S=1\n"}
            ],
            None,
            False,
        ),
        (lambda: [], None, False),
        (lambda: _edit_main(patched="VALUE = 1\n"), None, True),
    ],
)
def test_the_shadow_never_rewrites_an_existing_terminal_outcome(
    tmp_path, monkeypatch, plan_factory, validation, expected_success
):
    """Every representative terminal outcome survives the shadow unchanged."""
    compared: list[dict] = []
    for enabled in (False, True):
        project = tmp_path / f"repo-{int(enabled)}"
        project.mkdir()
        (project / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
        _enable(monkeypatch, enabled)
        result = _run(project, plan_factory(), validation_command=validation)
        compared.append(
            {
                key: value
                for key, value in result.items()
                if key
                not in set(RESULT_METADATA_KEYS)
                | {"replay_dir", "replay_id", "brain_stamp_id"}
            }
        )
        assert result["success"] is expected_success

    assert compared[0] == compared[1]


# ── Cost invariants ───────────────────────────────────────────────────────────

class _TraversalCounter:
    """Record every directory-enumeration primitive and where it was rooted.

    Bookkeeping inside the run's own ``.agent`` artifact bundle is not a
    repository traversal — the artifact store already lists that directory on
    every write it makes — so the counters are kept apart.

    OPS.VALIDATE.2 adds a second such exception on exactly the same grounds:
    removing the temporary bytecode-cache directory the validation run itself
    created (``shutil.rmtree`` walks it on Windows) enumerates a scratch
    directory under the system temp root, never a path in the project.  It is
    counted separately so this test keeps measuring what its name says —
    *repository* membership traversal — rather than silently absorbing, or
    silently forbidding, enumeration of directories C.A.T.T.U.S owns outright.
    """

    def __init__(self, monkeypatch):
        self.repository: list[str] = []
        self.artifact_store: list[str] = []
        self.validation_cache: list[str] = []
        original_walk = os.walk
        original_rglob = Path.rglob
        original_glob = Path.glob
        original_iterdir = Path.iterdir

        def record(target: object, primitive: str) -> None:
            rendered = str(target).replace("\\", "/")
            if VALIDATION_PYCACHE_DIR_PREFIX in rendered:
                bucket = self.validation_cache
            elif "/.agent/" in rendered or rendered.endswith("/.agent"):
                bucket = self.artifact_store
            else:
                bucket = self.repository
            bucket.append(f"{primitive}:{rendered}")

        def walk(top, *args, **kwargs):
            record(top, "walk")
            return original_walk(top, *args, **kwargs)

        def rglob(instance, *args, **kwargs):
            record(instance, "rglob")
            return original_rglob(instance, *args, **kwargs)

        def glob(instance, *args, **kwargs):
            record(instance, "glob")
            return original_glob(instance, *args, **kwargs)

        def iterdir(instance, *args, **kwargs):
            record(instance, "iterdir")
            return original_iterdir(instance, *args, **kwargs)

        monkeypatch.setattr(os, "walk", walk)
        monkeypatch.setattr(Path, "rglob", rglob)
        monkeypatch.setattr(Path, "glob", glob)
        monkeypatch.setattr(Path, "iterdir", iterdir)


def _traversal_counter(
    tmp_path, monkeypatch, name: str, enabled: bool
) -> _TraversalCounter:
    with monkeypatch.context() as patch:
        patch.setattr(
            run_lifecycle,
            "collect_brain_stamp",
            lambda repo: {"brain_stamp_id": "stamp", "schema_version": 2},
        )
        project = tmp_path / name
        project.mkdir()
        (project / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
        if enabled:
            patch.setenv(ENVIRONMENT_FLAG, "true")
        else:
            patch.delenv(ENVIRONMENT_FLAG, raising=False)
        counter = _TraversalCounter(patch)
        _run(
            project,
            _edit_main(),
            validation_command=PASSING_VALIDATION,
            worker_declaration=(
                _declaration(("main.py", "modified")) if enabled else None
            ),
        )
        return counter


def test_the_shadow_adds_no_repository_membership_traversal(tmp_path, monkeypatch):
    baseline = _traversal_counter(tmp_path, monkeypatch, "baseline", enabled=False)
    shadow = _traversal_counter(tmp_path, monkeypatch, "shadow", enabled=True)

    # The two existing walks are the validation side-effect snapshots the apply
    # path already took; asserting their presence keeps this test non-vacuous.
    assert [item.split(":", 1)[0] for item in baseline.repository] == [
        "walk",
        "walk",
    ]
    assert [item.split(":", 1)[0] for item in shadow.repository] == [
        "walk",
        "walk",
    ]
    # OPS.VALIDATE.2: the validation bytecode cache is enumerated only to
    # remove itself, and only ever under the system temp root.
    assert all(
        VALIDATION_PYCACHE_DIR_PREFIX in item
        for item in baseline.validation_cache + shadow.validation_cache
    )
    assert len(baseline.validation_cache) == len(shadow.validation_cache)
    # The only enumeration difference is the artifact store listing its own
    # bundle when the additive receipt and its event are written.
    assert len(shadow.artifact_store) > len(baseline.artifact_store)
    assert all(
        item.startswith("iterdir:") for item in shadow.artifact_store
    ), shadow.artifact_store


def _call_count(tmp_path, monkeypatch, name: str, enabled: bool) -> dict[str, int]:
    counts = {"validation": 0, "apply": 0}
    with monkeypatch.context() as patch:
        patch.setattr(
            run_lifecycle,
            "collect_brain_stamp",
            lambda repo: {"brain_stamp_id": "stamp", "schema_version": 2},
        )
        import core.validator as validator

        original_validation = validator.run_validation_command_detailed
        original_apply = run_lifecycle.apply_patch_plan

        def counted_validation(*args, **kwargs):
            counts["validation"] += 1
            return original_validation(*args, **kwargs)

        def counted_apply(*args, **kwargs):
            counts["apply"] += 1
            return original_apply(*args, **kwargs)

        patch.setattr(
            validator, "run_validation_command_detailed", counted_validation
        )
        patch.setattr(run_lifecycle, "apply_patch_plan", counted_apply)

        project = tmp_path / name
        project.mkdir()
        (project / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
        if enabled:
            patch.setenv(ENVIRONMENT_FLAG, "true")
        else:
            patch.delenv(ENVIRONMENT_FLAG, raising=False)
        _run(
            project,
            _edit_main(),
            validation_command=PASSING_VALIDATION,
            worker_declaration=(
                _declaration(("main.py", "modified")) if enabled else None
            ),
        )
    return counts


def test_the_shadow_adds_no_validation_execution_and_no_patch_application(
    tmp_path, monkeypatch
):
    baseline = _call_count(tmp_path, monkeypatch, "cost-baseline", enabled=False)
    shadow = _call_count(tmp_path, monkeypatch, "cost-shadow", enabled=True)

    assert baseline["validation"] == 1
    assert baseline["apply"] == 1
    assert shadow == baseline


def test_the_shadow_imports_no_model_or_network_runtime(repo, monkeypatch):
    _enable(monkeypatch)
    before = set(sys.modules)
    _run(
        repo,
        _edit_main(),
        validation_command=PASSING_VALIDATION,
        worker_declaration=_declaration(("main.py", "modified")),
    )
    introduced = set(sys.modules) - before

    for module in introduced:
        assert not module.startswith("agents"), module
        assert not module.startswith("reasoning"), module
        assert module not in {"requests", "httpx", "aiohttp"}, module


# ── Producer contracts ────────────────────────────────────────────────────────

def test_a_producer_may_not_widen_upstream_write_authority():
    upstream = {
        "core/a.py": PATH_AUTHORITY_WRITABLE,
        "core/b.py": PATH_AUTHORITY_SUPPORTING_READ_ONLY,
    }
    with pytest.raises(LiveAuthorityWideningError):
        build_live_execution_authorization(
            execution_run_id="run",
            repository_id="repo",
            task_contract_fingerprint="a" * 64,
            pre_execution_state_fingerprint="b" * 64,
            upstream_authority=upstream,
            upstream_authority_fingerprint="c" * 64,
            requested_authority={
                "core/a.py": PATH_AUTHORITY_WRITABLE,
                "core/b.py": PATH_AUTHORITY_WRITABLE,
            },
        )


def test_a_producer_may_not_invent_a_path_upstream_never_authorized():
    with pytest.raises(LiveAuthorityWideningError):
        build_live_execution_authorization(
            execution_run_id="run",
            repository_id="repo",
            task_contract_fingerprint="a" * 64,
            pre_execution_state_fingerprint="b" * 64,
            upstream_authority={"core/a.py": PATH_AUTHORITY_WRITABLE},
            upstream_authority_fingerprint="c" * 64,
            requested_authority={"core/new.py": PATH_AUTHORITY_WRITABLE},
        )


def test_a_gate_blocked_path_cannot_be_declared_writable_by_a_producer():
    authorization = build_live_execution_authorization(
        execution_run_id="run",
        repository_id="repo",
        task_contract_fingerprint="a" * 64,
        pre_execution_state_fingerprint="b" * 64,
        upstream_authority={"tests/test_x.py": PATH_AUTHORITY_WRITABLE},
        upstream_authority_fingerprint="c" * 64,
    )
    entry = {item.path: item for item in authorization.authorized_paths}
    assert entry["tests/test_x.py"].authority == PATH_AUTHORITY_FORBIDDEN
    assert entry["tests/test_x.py"].forbidden_reason == "test"


def test_a_different_upstream_authority_changes_the_produced_fingerprint():
    def _authorization(paths):
        verdict = evaluate_patch_safety(list(paths))
        authority, reasons, fingerprint = upstream_authority_from_patch_safety(
            paths, verdict
        )
        return build_live_execution_authorization(
            execution_run_id="run",
            repository_id="repo",
            task_contract_fingerprint="a" * 64,
            pre_execution_state_fingerprint="b" * 64,
            upstream_authority=authority,
            upstream_forbidden_reasons=reasons,
            upstream_authority_fingerprint=fingerprint,
        )

    first = _authorization(("core/a.py",))
    second = _authorization(("core/a.py", "core/b.py"))

    assert first.authorization_id != second.authorization_id
    assert live_authorization_fingerprint(first) != live_authorization_fingerprint(
        second
    )
    assert live_authorization_fingerprint(first) == live_authorization_fingerprint(
        _authorization(("core/a.py",))
    )


def test_the_validation_receipt_binds_state_result_and_scope():
    def _receipt_for(*, state: str, passed: bool, scope):
        return build_live_validation_receipt(
            execution_run_id="run",
            repository_id="repo",
            validated_state_fingerprint=state,
            target_scope=scope,
            executed=True,
            passed=passed,
        )

    base = _receipt_for(state="a" * 64, passed=True, scope=("core/a.py",))
    assert live_validation_receipt_fingerprint(base) == (
        live_validation_receipt_fingerprint(
            _receipt_for(state="a" * 64, passed=True, scope=("core/a.py",))
        )
    )
    for altered in (
        _receipt_for(state="b" * 64, passed=True, scope=("core/a.py",)),
        _receipt_for(state="a" * 64, passed=False, scope=("core/a.py",)),
        _receipt_for(state="a" * 64, passed=True, scope=("core/b.py",)),
    ):
        assert live_validation_receipt_fingerprint(
            altered
        ) != live_validation_receipt_fingerprint(base)


def test_no_validation_request_yields_no_expectation_and_no_receipt():
    expectation, reason = build_live_validation_expectation(
        validation_requested=False, target_scope=("core/a.py",)
    )
    assert expectation is None
    assert reason == "no_validation_requested"

    assert (
        build_live_validation_receipt(
            execution_run_id="run",
            repository_id="repo",
            validated_state_fingerprint="a" * 64,
            target_scope=("core/a.py",),
            executed=False,
            passed=None,
        )
        is None
    )


def test_a_refused_validation_is_skipped_not_failed():
    receipt = build_live_validation_receipt(
        execution_run_id="run",
        repository_id="repo",
        validated_state_fingerprint="a" * 64,
        target_scope=("core/a.py",),
        executed=False,
        passed=None,
        blocked=True,
    )
    assert receipt is not None
    assert receipt.result == "skipped"


def test_the_final_state_fingerprint_moves_with_the_observed_change_set():
    base = LivePathDigests(digests=(("core/a.py", "a" * 64),))
    empty = observed_change_state_fingerprint("repo", base, ())
    one = observed_change_state_fingerprint(
        "repo",
        base,
        (
            {
                "path": "core/a.py",
                "change_kind": "modified",
                "before_sha256": "a" * 64,
                "after_sha256": "b" * 64,
            },
        ),
    )
    other = observed_change_state_fingerprint(
        "repo",
        base,
        (
            {
                "path": "core/a.py",
                "change_kind": "modified",
                "before_sha256": "a" * 64,
                "after_sha256": "c" * 64,
            },
        ),
    )

    assert empty != one
    assert one != other
    assert empty == observed_change_state_fingerprint("repo", base, ())
    assert empty != observed_change_state_fingerprint("other-repo", base, ())


def test_the_state_fingerprint_carries_no_clock_or_random_value():
    base = LivePathDigests(digests=(("core/a.py", "a" * 64),))
    values = {
        observed_change_state_fingerprint("repo", base, ()) for _ in range(5)
    }
    assert len(values) == 1


def test_the_worker_report_translates_only_known_plan_operations():
    declared, untranslated = declared_changes_from_patch_plan(
        [
            {"op": "create_file", "relative_path": "new.py", "content": ""},
            {
                "op": "replace_snippet",
                "relative_path": "old.py",
                "target_snippet": "a",
                "patched_snippet": "b",
            },
            {"op": "teleport_file", "relative_path": "weird.py"},
        ]
    )
    assert [(item.path, item.change_kind) for item in declared] == [
        ("new.py", "added"),
        ("old.py", "modified"),
    ]
    assert untranslated == ("teleport_file",)


# ── Disagreement, completeness, persistence and handoff ───────────────────────

def test_the_disagreement_report_names_the_measured_direction():
    assert shadow_disagreement(RUN_STATUS_SUCCESS, STATUS_BLOCKED) == (
        DISAGREEMENT_CHECKER_STRICTER
    )
    assert shadow_disagreement(RUN_STATUS_SUCCESS, STATUS_RECONCILED) == (
        DISAGREEMENT_NONE
    )
    assert shadow_disagreement("failed", STATUS_RECONCILED) == (
        "checker_weaker_than_run"
    )
    assert shadow_disagreement("failed", STATUS_BLOCKED) == DISAGREEMENT_NONE
    assert shadow_disagreement(RUN_STATUS_SUCCESS, None) == (
        DISAGREEMENT_NOT_COMPARABLE
    )


def test_producer_completeness_is_partial_when_a_live_fact_is_missing(
    repo, monkeypatch
):
    _enable(monkeypatch)
    complete = _receipt(_run(repo, _edit_main(), validation_command=PASSING_VALIDATION))
    assert complete["producer_completeness"] == COMPLETENESS_COMPLETE

    other = repo.parent / "repo2"
    other.mkdir()
    (other / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    partial = _receipt(_run(other, _edit_main()))
    assert partial["producer_completeness"] == COMPLETENESS_PARTIAL
    assert "validation_expectation_missing" in partial["missing_live_facts"]


def test_a_rolled_back_run_reports_an_incomplete_observed_identity(
    repo, monkeypatch
):
    _enable(monkeypatch)
    receipt = _receipt(_run(repo, _edit_main(), validation_command=FAILING_VALIDATION))
    assert INCOMPLETE_OBSERVED_CHANGE_IDENTITY in receipt["missing_live_facts"]
    assert receipt["producer_completeness"] == COMPLETENESS_PARTIAL


def test_the_receipt_is_attached_to_the_existing_run_artifact_bundle(
    repo, monkeypatch
):
    _enable(monkeypatch)
    result = _run(repo, _edit_main(), validation_command=PASSING_VALIDATION)
    replay_dir = Path(result["replay_dir"])
    manifest = json.loads(
        (replay_dir / "replay_manifest.json").read_text(encoding="utf-8")
    )

    assert SHADOW_ARTIFACT_NAME in manifest["files_present"]
    assert manifest["replay_id"] == result["replay_id"]
    loaded = load_shadow_post_run_check(replay_dir)
    assert loaded["reconciliation_available"] is True
    assert loaded["legacy_run"] is False
    assert loaded["execution_run_id"] == result["replay_id"]

    events = [
        json.loads(line)
        for line in (replay_dir / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    phases = [event["phase"] for event in events]
    assert phases[-1] == "post_run_reconciliation_shadow"
    assert events[-1]["payload"]["authoritative_effect"] is False


def test_a_run_without_an_artifact_bundle_survives_and_stays_honest(
    repo, monkeypatch
):
    """No replay bundle means no persistence — and no invented reconciliation."""
    _enable(monkeypatch)
    monkeypatch.setattr(
        run_lifecycle,
        "create_replay_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no bundle")),
    )
    result = _run(repo, _edit_main(), validation_command=PASSING_VALIDATION)

    assert result["success"] is True
    assert (repo / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    assert "replay_dir" not in result
    assert result["post_run_reconciliation_available"] is False
    assert result["post_run_reconciliation_producer_completeness"] == (
        COMPLETENESS_UNAVAILABLE
    )
    assert result["post_run_reconciliation_authoritative_effect"] is False


def test_a_pre_apply_observation_failure_reports_not_reached(repo, monkeypatch):
    """A collector that could not observe the starting state invents nothing."""
    _enable(monkeypatch)
    monkeypatch.setattr(
        run_lifecycle, "_shadow_pre_apply_digests", lambda *_args: None
    )
    result = _run(repo, _edit_main(), validation_command=PASSING_VALIDATION)

    assert result["success"] is True
    receipt = _receipt(result)
    assert receipt["shadow_outcome"] == SHADOW_NOT_REACHED
    assert receipt["reconciliation_status"] is None
    assert receipt["not_reached_reason"] == NOT_REACHED_BOUNDARY


def test_a_legacy_run_without_a_receipt_stays_readable(tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    loaded = load_shadow_post_run_check(legacy)

    assert loaded["reconciliation_available"] is False
    assert loaded["legacy_run"] is True
    assert loaded["authoritative_effect"] is False


def test_a_pre_declaration_shadow_receipt_defaults_new_fields_safely(tmp_path):
    replay = tmp_path / "pre-declaration-receipt"
    replay.mkdir()
    (replay / SHADOW_ARTIFACT_NAME).write_text(
        json.dumps(
            {
                "reconciliation_available": True,
                "reconciliation_status": STATUS_RECONCILED,
                "authoritative_effect": False,
            }
        ),
        encoding="utf-8",
    )

    loaded = load_shadow_post_run_check(replay)
    assert loaded["legacy_run"] is False
    assert loaded["worker_declaration_source"] is None
    assert loaded["worker_declaration_invalid"] is False
    assert loaded["independent_worker_declaration_missing"] is True


def test_check_2_is_not_invoked_and_its_inputs_are_reported_honestly(
    repo, monkeypatch
):
    _enable(monkeypatch)
    receipt = _receipt(_run(repo, _edit_main(), validation_command=PASSING_VALIDATION))
    handoff = receipt["check_2_handoff"]

    assert handoff["check_2_invoked"] is False
    assert handoff["task_contract_available"] is False
    assert handoff["requirement_ledger_available"] is False
    assert handoff["goal_proposition_binding_available"] is False
    assert handoff["claim_assessment_available"] is False
    assert handoff["execution_run_identity_available"] is True
    assert handoff["final_state_identity_available"] is True
    assert receipt["guardrails"]["check_3_implemented"] is False
    assert "goal_fidelity" not in json.dumps(receipt)


def test_the_dogfood_summary_answers_the_disagreement_question(repo, monkeypatch):
    """How often would CHECK.1 have disagreed with the current executor?"""
    from core.post_run_reconciliation_shadow import summarize_shadow_post_run_checks

    _enable(monkeypatch)
    clean = _run(
        repo,
        _edit_main(),
        validation_command=PASSING_VALIDATION,
        worker_declaration=_declaration(("main.py", "modified")),
    )

    stricter_repo = repo.parent / "repo-side-effect"
    stricter_repo.mkdir()
    (stricter_repo / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    stricter = _run(
        stricter_repo,
        _edit_main(),
        validation_command=(
            'python -c "open(\'generated_note.txt\',\'w\').write(\'x\')"'
        ),
        worker_declaration={
            "declaration_id": "invalid-summary-declaration",
            "execution_run_id": "worker-run",
            "worker_id": None,
            "declaration_stage": "completed",
            "declared_status": "success",
            "declared_changes": [],
            "unknown_key": True,
        },
    )

    legacy = repo.parent / "legacy-bundle"
    legacy.mkdir()

    summary = summarize_shadow_post_run_checks(
        [Path(clean["replay_dir"]), Path(stricter["replay_dir"]), legacy]
    )

    assert summary["runs_with_receipt"] == 2
    assert summary["legacy_runs_without_receipt"] == 1
    assert summary["authoritative_run_status_counts"] == {"success": 2}
    assert summary["reconciliation_status_counts"] == {
        STATUS_BLOCKED: 1,
        STATUS_RECONCILED: 1,
    }
    assert summary["disagreement_counts"] == {
        DISAGREEMENT_CHECKER_STRICTER: 1,
        DISAGREEMENT_NONE: 1,
    }
    assert summary["disagreement_reason_counts"][
        "validation_stale_for_final_state"
    ] == 1
    assert summary["worker_declaration_source_counts"] == {
        DECLARATION_SOURCE_INDEPENDENT: 1,
        DECLARATION_SOURCE_LEGACY_PLAN_DERIVED: 1,
    }
    assert summary["worker_declaration_invalid_runs"] == 1
    assert summary["authoritative_effect"] is False
    assert summary["counts_decide_nothing"] is True


def test_the_safe_entry_point_never_raises_on_a_malformed_observation():
    receipt = safe_run_shadow_post_run_reconciliation(
        LiveExecutionObservation(
            project_root="",
            execution_run_id="",
            authoritative_run_status="not-a-status",
        )
    )
    assert receipt.shadow_outcome == SHADOW_CHECKER_ERROR
    assert receipt.reconciliation_status is None
    assert receipt.authoritative_effect is False
