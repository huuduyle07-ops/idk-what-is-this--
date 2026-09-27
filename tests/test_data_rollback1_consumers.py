"""DATA.ROLLBACK.1 consumer regressions: final truth and disposable evidence."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
import pytest

from core.executor import ExecutionResult
from core.lesson_quality import evaluate_lesson_candidate
from core.rollback_outcome import (
    disposable_clone_rollback_fields,
    rollback_completed_verified,
    rollback_incomplete,
)
from web.routes import patch_routes as routes


PATCH = {
    "relative_path": "pricing.py", "target_snippet": "old",
    "patched_snippet": "new",
}
PLAN = [{"op": "replace_snippet", **PATCH}]


@pytest.fixture
def route_environment(tmp_path, monkeypatch):
    (tmp_path / "pricing.py").write_bytes(b"old\r\n")
    monkeypatch.setattr(routes, "evaluate_patch_safety", lambda *a, **k: {"ok": True, "reasons": []})
    monkeypatch.setattr(routes, "get_default_validation_command", lambda *a: "python check.py")
    monkeypatch.setattr(routes, "_persist_manual_apply", lambda **k: None)
    authorization = SimpleNamespace(authorized=True, as_payload_fields=lambda: {}, as_dict=lambda: {})
    monkeypatch.setattr(routes, "authorize_human_apply", lambda **k: authorization)
    monkeypatch.setattr(routes, "UndoBackupStore", lambda *a: SimpleNamespace(prepare=lambda *a: None))
    app = Flask(__name__)
    app.register_blueprint(routes.bp)
    return app.test_client(), tmp_path


def _execution_result(root, outcome):
    return ExecutionResult(
        success=False, phase="validation_failed",
        message=("Validation failed (assertion_error). Changes were reverted successfully."
                 if outcome.performed else "Validation failed (assertion_error). Rollback failed or is incomplete."),
        target_file=str(root / "pricing.py"), validation_outcome="failed",
        rollback_outcome=outcome,
    )


@pytest.mark.parametrize("route", ["/apply_patch", "/apply_patch_plan"])
@pytest.mark.parametrize("final_changed", [True, False])
def test_apply_message_and_fields_use_final_observation(route_environment, monkeypatch, route, final_changed):
    client, repo = route_environment
    stale = rollback_completed_verified()

    def execute(root):
        if final_changed:
            (root / "pricing.py").write_bytes(b"new\r\n")
        return _execution_result(root, stale)

    if route == "/apply_patch":
        monkeypatch.setattr(routes, "Executor", lambda project_root, **k: SimpleNamespace(run=lambda **k: execute(Path(project_root))))
        payload = PATCH
    else:
        def execute_plan(project_root, *a, **k):
            execute(Path(project_root))
            return {
                "success": False, "error": "validation assertion failed", "failed_op_index": 1,
                "failed_op": {"op": "validation"}, "validation_outcome": "failed",
                "applied_ops": PLAN, "diffs": [], "mutation_attempted": True,
                "recovery_attempted": True, "recovery_complete": stale.performed,
                **stale.as_payload_fields(),
            }
        monkeypatch.setattr(routes, "run_patch_plan_with_artifacts", execute_plan)
        payload = {"patch_plan": PLAN}
    response = client.post(route, data={"repo_path": str(repo), "patch": json.dumps(payload)}).get_json()
    assert response["rollback_performed"] is not final_changed
    assert response["final_repository_changed"] is final_changed
    assert response["rollback_status"] == ("incomplete" if final_changed else "completed_verified")
    assert "assertion" in response["message"]
    if final_changed:
        assert "Rollback performed: True" not in response["message"]
        assert "rolled back" not in response["message"].lower()
        assert "reverted successfully" not in response["message"].lower()
        assert "incomplete" in response["message"].lower()
    else:
        assert "rolled back" in response["message"].lower()
        assert "incomplete" not in response["message"].lower()


@pytest.mark.parametrize("final_changed", [True, False])
def test_apply_failure_info_rollback_facts_follow_the_final_outcome(
    route_environment, monkeypatch, final_changed
):
    client, repo = route_environment

    def execute(root):
        if final_changed:
            (root / "pricing.py").write_bytes(b"new\r\n")
        result = _execution_result(root, rollback_completed_verified())
        result.failure_info = {
            "category": "assertion_error", "rollback_code": "", "rollback_reason": "",
        }
        return result

    monkeypatch.setattr(routes, "Executor", lambda project_root, **k: SimpleNamespace(
        run=lambda **k: execute(Path(project_root))))
    response = client.post(
        "/apply_patch", data={"repo_path": str(repo), "patch": json.dumps(PATCH)}
    ).get_json()
    # One payload, one rollback account: executor diagnostics keep their cause
    # but cannot keep a rollback code the final observation refuted.
    assert response["failure_info"]["category"] == "assertion_error"
    assert response["failure_info"]["rollback_code"] == response["rollback_failure"]["code"]
    assert response["failure_info"]["rollback_reason"] == response["rollback_failure"]["reason"]
    if final_changed:
        assert response["rollback_status"] == "incomplete"
        assert response["failure_info"]["rollback_code"] == "post_rollback_state_changed"
    else:
        assert response["rollback_status"] == "completed_verified"
        assert response["failure_info"]["rollback_code"] == ""


@pytest.mark.parametrize("route", ["/test_patch", "/test_patch_plan"])
def test_disposable_routes_never_advertise_deleted_recovery_material(route_environment, monkeypatch, route):
    client, repo = route_environment
    clones = []
    outcome = rollback_incomplete(["pricing.py"]).with_recovery_material(["a" * 64])

    def execute(root):
        clones.append(root)
        (root / "pricing.py").write_bytes(b"new\r\n")
        artifact = root / ".agent" / "failed_rollback_recovery" / "v1" / "artifact.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}", encoding="utf-8")
        return _execution_result(root, outcome)

    if route == "/test_patch":
        monkeypatch.setattr(routes, "Executor", lambda project_root, **k: SimpleNamespace(run=lambda **k: execute(Path(project_root))))
        payload = PATCH
    else:
        def execute_plan(project_root, *a, **k):
            execute(Path(project_root))
            return {
                "success": False, "error": "validation failed", "applied_ops": PLAN,
                "recovery_complete": False, "recovery_source_execution_id": "disposed-run",
                **outcome.as_payload_fields(),
            }
        monkeypatch.setattr(routes, "run_patch_plan_with_artifacts", execute_plan)
        payload = {"patch_plan": PLAN}
    response = client.post(route, data={"repo_path": str(repo), "patch": json.dumps(payload)}).get_json()
    assert clones and all(not clone.exists() for clone in clones)
    assert (repo / "pricing.py").read_bytes() == b"old\r\n"
    assert response["rollback_status"] == "incomplete"
    assert response["rollback_attempted"] is True
    assert response["rollback_performed"] is False
    assert response["rollback_scope"] == response["final_repository_state_scope"] == "disposable_clone"
    assert response["final_repository_changed"] is True
    assert response["real_repository_changed"] is False
    assert response["recovery_artifact_ids"] == response["rollback_outcome"]["recovery_artifact_ids"] == []
    assert response["recovery_material_available"] is response["rollback_outcome"]["recovery_material_available"] is False
    assert response["recovery_source_execution_id"] == ""
    assert "disposable clone" in response["message"].lower()
    assert "recovery material is available" not in response["message"].lower()


def test_verified_clone_rollback_is_still_verified_without_artifact_error():
    fields = disposable_clone_rollback_fields(rollback_completed_verified().as_payload_fields())
    assert fields["rollback_performed"] is True
    assert fields["recovery_material_error"] == ""
    assert fields["real_repository_changed"] is False


@pytest.mark.parametrize("rollback", [
    {"rollback_performed": True},
    rollback_incomplete(["pricing.py"]).as_payload_fields(),
    {"rollback_outcome": {"schema_version": "unknown", "status": "unknown"}},
])
def test_lesson_consumers_preserve_negative_or_unknown_rollback_evidence(rollback):
    from core.lesson_auto_candidates import _dream_candidate_from_artifact
    from core.sleeping_consultant import _lesson_candidate_from_revalidation
    from scripts.create_lesson_from_proposal import _build_candidate
    from scripts.seed_lessons_from_proposals import _apply_summary

    result = {"success": True, "validation_ok": True, "changed_files": ["pricing.py"], **rollback}
    candidates = [
        _dream_candidate_from_artifact(result),
        _lesson_candidate_from_revalidation(result, ["pricing.py"], ""),
        _build_candidate({
            "item.json": {}, "case.json": {}, "patch_proposal.json": {"patch_plan": PLAN},
            "apply_result.json": result, "validation.json": {"validation_ok": True},
        }),
    ]
    embedded = {**candidates[0], "rollback_happened": False}
    candidates.append(_dream_candidate_from_artifact({**result, "lesson_candidate": embedded}))
    for candidate in candidates:
        assert candidate["rollback_happened"] is True
        evaluation = evaluate_lesson_candidate(candidate)
        assert evaluation["promotion"] in {"blocked", "needs_human_review"}
        assert evaluation["active_knowledge_allowed"] is False
    summary = _apply_summary(result)
    assert summary["rollback_happened"] is True
    assert summary["rollback_performed"] is False


def test_dream_revalidation_artifact_does_not_keep_discarded_clone_locators(tmp_path, monkeypatch):
    from core import sleeping_consultant as consultant

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pricing.py").write_bytes(b"old\n")
    item_dir = tmp_path / "item"
    item_dir.mkdir()
    (item_dir / "patch_plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
    outcome = rollback_incomplete(["pricing.py"]).with_recovery_material(["b" * 64])
    monkeypatch.setattr(consultant, "_validation_command", lambda root: "python check.py")
    monkeypatch.setattr(consultant, "run_patch_plan_with_artifacts", lambda *a, **k: {
        "success": False, "validation_ok": False, **outcome.as_payload_fields(),
        "message": "Validation failed. Emergency recovery material is available.",
    })
    consultant._revalidate_ready_to_apply_item(str(repo), {}, 1, item_dir, 1)
    artifact = json.loads((item_dir / "patch_revalidation_pass1.json").read_text(encoding="utf-8"))
    assert artifact["recovery_artifact_ids"] == []
    assert artifact["recovery_material_available"] is False
    assert artifact["rollback_scope"] == "disposable_clone"
    assert artifact["real_repository_changed"] is False
    assert "recovery material is available" not in artifact["message"].lower()
    assert "disposable clone" in artifact["message"].lower()


def _lifecycle_run(tmp_path, monkeypatch, scenario):
    import patching.patch_plan_transaction as transaction
    from core import run_lifecycle
    from core.post_run_reconciliation_shadow import ENVIRONMENT_FLAG, SHADOW_ARTIFACT_NAME

    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    monkeypatch.setattr(
        run_lifecycle, "collect_brain_stamp",
        lambda repo: {"brain_stamp_id": "stamp", "schema_version": 2},
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_bytes(b"old A\n")
    (repo / "b.txt").write_bytes(b"old B\n")
    write, restore = Path.write_bytes, transaction.restore_target

    def later_failure(path, raw):
        if path.name == "b.txt" and raw.startswith(b"new"):
            raise OSError("injected later mutation failure")
        return write(path, raw)

    def restore_fault(path, baseline):
        if scenario == "restore_fails" and path.name == "a.txt":
            raise PermissionError("injected restore failure")
        return restore(path, baseline)

    monkeypatch.setattr(Path, "write_bytes", later_failure)
    monkeypatch.setattr(transaction, "restore_target", restore_fault)
    first = "absent snippet" if scenario == "no_mutation" else "old A"
    result = run_lifecycle.run_patch_plan_with_artifacts(str(repo), [
        {"op": "replace_snippet", "relative_path": "a.txt",
         "target_snippet": first, "patched_snippet": "new A"},
        {"op": "replace_snippet", "relative_path": "b.txt",
         "target_snippet": "old B", "patched_snippet": "new B"},
    ], source="unit")
    replay = Path(result["replay_dir"])
    events = [
        json.loads(line)
        for line in (replay / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    shadow = json.loads((replay / SHADOW_ARTIFACT_NAME).read_text(encoding="utf-8"))
    return repo, result, events, shadow


@pytest.mark.parametrize("scenario", ["restored", "restore_fails", "no_mutation"])
def test_lifecycle_events_and_shadow_input_follow_the_measured_rollback(
    tmp_path, monkeypatch, scenario
):
    repo, result, events, shadow = _lifecycle_run(tmp_path, monkeypatch, scenario)
    phases = [event["phase"] for event in events]
    # A reversed patched state was never digested, whether or not it completed.
    identity_partial = "observed_change_identity_incomplete" in shadow["missing_live_facts"]
    if scenario == "restored":
        assert result["rollback_status"] == "completed_verified"
        assert "rollback_performed" in phases
        assert "rollback_incomplete" not in phases
        assert identity_partial
    elif scenario == "restore_fails":
        assert (repo / "a.txt").read_bytes() == b"new A\n"
        assert result["rollback_status"] == "incomplete"
        assert result["rollback_performed"] is False
        assert "rollback_performed" not in phases
        [event] = [event for event in events if event["phase"] == "rollback_incomplete"]
        assert event["payload"]["rollback_status"] == "incomplete"
        assert event["payload"]["remaining_changed_paths"] == ["a.txt"]
        assert event["payload"]["recovery_artifact_ids"] == result["recovery_artifact_ids"]
        assert event["payload"]["recovery_artifact_ids"]
        assert "injected restore failure" not in json.dumps(events)
        assert identity_partial
    else:
        assert result["rollback_status"] == "not_required"
        assert not {"rollback_performed", "rollback_incomplete"} & set(phases)
        assert not identity_partial
