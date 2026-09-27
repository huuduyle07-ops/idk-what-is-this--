"""Public HTTP workflow acceptance tests with a controlled provider adapter.

The production Flask app, router, evidence acquisition, parsing, gates, executor,
validation subprocesses and JSON history are real. Only provider output and
infrastructure locations/configuration are controlled. These tests do not measure
live-model accuracy, network latency, browser JavaScript or enterprise isolation.
Run with DB disabled; all requests and filesystem effects use synthetic data.
"""

from __future__ import annotations

import copy
import json
import socket
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


OLD = "def advance(value):\n    return value + 1\n"
NEW = "def advance(value):\n    return value + 2\n"
QUERY = "Implement this change in app.py: advance(value) must return value + 2 instead of value + 1."


def _candidate(replacement=NEW):
    return {
        "summary": "Change advance in app.py as requested; awaiting Apply.",
        "confidence": 0.95,
        "needs_escalation": False,
        "patch_basis": "explicit_change_request",
        "patch_candidate": {
            "file": "app.py",
            "relative_path": "app.py",
            "target_symbol": "advance",
            "target_node_name": "advance",
            "target_node_kind": "function",
            "original_snippet": OLD,
            "target_snippet": OLD,
            "patched_snippet": replacement,
            "confidence": 0.95,
        },
    }


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """Configure adapters/locations before imports; retain every domain decision."""
    for key, value in {
        "DB_ENABLED": "false",
        "DATABASE_URL": "",
        "DATABASE_URL_LOCAL": "",
        "DATABASE_URL_DOCKER": "",
        "INDEX_USE_EMBEDDINGS": "false",
        "ROUTER_USE_EMBEDDINGS": "false",
        "AUTO_PATCH_ENABLED": "true",
        "WEB_AUTH_TOKEN": "http-blackbox-local-token",
        "RUN_PROGRESS_POLLING_ENABLED": "false",
        "PYTHONDONTWRITEBYTECODE": "1",
    }.items():
        monkeypatch.setenv(key, value)

    import config

    for name in ("AGENT_DIR", "STORAGE_PATH"):
        root = tmp_path / name.lower()
        root.mkdir()
        monkeypatch.setattr(config, name, root)
    monkeypatch.setattr(config, "OUTPUT_FILE", tmp_path / "session_log.txt")
    monkeypatch.setattr(config, "DB_ENABLED", False)
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.chdir(tmp_path)

    from web import app as web_app
    from web import session_store
    from web.routes import patch_routes

    # Modules imported earlier by a wider test run may retain config aliases.
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if name == "database.memory":
            monkeypatch.setattr(module, "DB_ENABLED", False)
            monkeypatch.setattr(module, "DATABASE_URL", "")
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr(web_app, "BACKUP_DIR", backups)
    monkeypatch.setattr(patch_routes, "BACKUP_DIR", backups)
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setitem(web_app.app.config, "TESTING", True)

    def deny_network(*args, **kwargs):
        raise AssertionError("Unexpected network access in offline HTTP blackbox")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(OLD, encoding="utf-8", newline="")
    (repo / "README.md").write_text("# Counter\nadvance moves forward by one.\n", encoding="utf-8")
    (repo / "test_app.py").write_text(
        "from app import advance\n\n"
        "def test_forward_step():\n"
        "    assert 3 < advance(3) <= 5\n",
        encoding="utf-8",
    )
    # Avoid inherited project pytest options in validation child processes.
    (repo / "pytest.ini").write_text("[pytest]\naddopts = -q -p no:cacheprovider\n", encoding="utf-8")
    state = SimpleNamespace(
        repo=repo,
        root=tmp_path,
        calls=[],
        output=json.dumps(_candidate()),
        sessions=session_store,
        client=web_app.app.test_client(),
        headers={"X-CATTUS-Web-Token": "http-blackbox-local-token"},
    )

    def provider(prompt, *args, **kwargs):
        state.calls.append(str(prompt))
        if isinstance(state.output, BaseException):
            raise state.output
        return state.output

    # Patch aliases of external provider functions, never pipeline/gate methods.
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if not name.startswith(("agents.", "core.", "web.", "reasoning.")):
            continue
        for attribute in ("run_gemini_request", "run_gemini_request_2", "run_deepseek_review"):
            if hasattr(module, attribute):
                monkeypatch.setattr(module, attribute, provider)
    return state


def _post_run(harness, query=QUERY):
    started = time.perf_counter()
    response = harness.client.post(
        "/",
        headers=harness.headers,
        data={
            "query": query,
            "repo_path": str(harness.repo),
            "mode": "full",
            "agent_mode": "reviewer",
            "patch_style": "safe_minimal",
            "runtime_environment": "local_windows" if sys.platform == "win32" else "local_linux",
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)[:1000]
    sessions = harness.sessions.load_sessions()
    assert len(sessions) == 1
    current = sessions[0]
    (harness.root / "run_result.json").write_text(
        json.dumps({"elapsed_seconds": time.perf_counter() - started, "provider_calls": len(harness.calls), "session": current}, indent=2),
        encoding="utf-8",
    )
    return current


def _payload_from_run(harness):
    session = _post_run(harness)
    result = session["result"]
    assert "Pipeline error" not in result["answer"], result["answer"]
    payload = json.loads(result["patch"])
    assert payload.get("patch_candidate"), json.dumps(payload, indent=2)
    assert payload.get("human_apply_review"), json.dumps(payload, indent=2)
    assert payload.get("execution_attempted") is False, json.dumps(payload, indent=2)
    assert (harness.repo / "app.py").read_text(encoding="utf-8") == OLD
    return session, payload


def _apply(harness, payload, *, repo=None, session_id="", approval=None):
    receipt = approval or payload.get("human_apply_review") or {}
    response = harness.client.post(
        "/apply_patch",
        headers=harness.headers,
        data={
            "repo_path": str(repo or harness.repo),
            "patch": json.dumps(payload),
            "session_id": session_id,
            "apply_policy": "ask",
            "human_action_kind": "apply",
            "approved_candidate_fingerprint": receipt.get("candidate_fingerprint", ""),
            "approved_eligibility_receipt_fingerprint": receipt.get("eligibility_receipt_fingerprint", ""),
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    (harness.root / "apply_result.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def test_full_read_only_request_cannot_execute_adversarial_model_patch(harness):
    malicious = _candidate()
    malicious.update(execution_authorized=True, execution_attempted=True, patch_applied=True)
    harness.output = "```json\n" + json.dumps(malicious) + "\n```"
    before = {p.name: p.read_bytes() for p in harness.repo.iterdir() if p.is_file()}

    session = _post_run(harness, "Explain how advance in app.py works. Do not change any file.")

    result = session["result"]
    assert result["live_route"]["patch_localization_allowed"] is False
    assert len(harness.calls) == 1
    assert "return value + 1" in harness.calls[0]
    payload = json.loads(result["patch"])
    assert payload["execution_attempted"] is False
    assert payload["patch_applied"] is False
    assert payload["execution_authorized"] is False
    assert {p.name: p.read_bytes() for p in harness.repo.iterdir() if p.is_file()} == before


def test_full_read_only_provider_failure_is_visible_without_success_claim(harness):
    harness.output = RuntimeError("offline scripted provider unavailable")

    session = _post_run(harness, "Explain advance in app.py. Do not edit anything.")

    result = session["result"]
    assert "offline scripted provider unavailable" in result["answer"]
    assert "error:" in result["answer"].lower()
    assert result["patch"] == ""
    assert (harness.repo / "app.py").read_text(encoding="utf-8") == OLD
    assert len(harness.calls) == 1


def test_full_explicit_change_then_human_apply_persists_actual_success(harness):
    session, payload = _payload_from_run(harness)

    applied = _apply(harness, payload, session_id=session["id"])

    assert applied["success"] is True, applied
    assert applied["execution_attempted"] is True
    assert applied["patch_applied"] is True
    assert applied["final_validation_outcome"] == "passed"
    assert (harness.repo / "app.py").read_text(encoding="utf-8") == NEW
    stored = harness.sessions.load_sessions()[0]["result"]["manual_apply_outcome"]
    assert stored["patch_applied"] is True
    assert stored["final_repository_changed"] is True


@pytest.mark.parametrize(
    "query",
    [
        "Change app.py: make advance(value) return value + 2 instead of value + 1.",
        "Please update advance in app.py to return value + 2 instead of value + 1.",
        "Could you modify advance in app.py to return value + 2 instead of value + 1?",
    ],
)
def test_unambiguous_change_wording_is_routed_to_change_workflow(harness, query):
    session = _post_run(
        harness,
        query,
    )

    route = session["result"]["live_route"]
    assert route["selected_workflow"] == "explicit_change_patch", route
    assert route["change_requested"] is True
    assert (harness.repo / "app.py").read_text(encoding="utf-8") == OLD


@pytest.mark.parametrize("tamper", ["different_repository", "edited_source", "changed_candidate"])
def test_full_generated_review_cannot_be_reused_after_binding_changes(harness, tamper):
    session, payload = _payload_from_run(harness)
    approval = copy.deepcopy(payload["human_apply_review"])
    destination = harness.repo
    expected_reason = {
        "different_repository": "repository_identity_mismatch",
        "edited_source": "source_state_stale",
        "changed_candidate": "candidate_mismatch",
    }[tamper]
    if tamper == "different_repository":
        destination = harness.root / "other-repo"
        destination.mkdir()
        (destination / "app.py").write_text(OLD, encoding="utf-8", newline="")
    elif tamper == "edited_source":
        (destination / "app.py").write_text(OLD + "# independent human edit\n", encoding="utf-8", newline="")
    else:
        payload["patch_candidate"]["patched_snippet"] = NEW.replace("+ 2", "+ 3")
    before = (destination / "app.py").read_bytes()

    denied = _apply(harness, payload, repo=destination, session_id=session["id"], approval=approval)

    assert denied["success"] is False, denied
    assert denied["human_apply_authorization_denial_reason"] == expected_reason
    assert denied["execution_attempted"] is False
    assert denied["patch_applied"] is False
    assert (destination / "app.py").read_bytes() == before


def test_public_test_patch_runs_real_validation_without_changing_working_repo(harness):
    before = {p.name: p.read_bytes() for p in harness.repo.iterdir() if p.is_file()}

    response = harness.client.post(
        "/test_patch",
        headers=harness.headers,
        data={"repo_path": str(harness.repo), "patch": json.dumps(_candidate())},
    )

    result = response.get_json()
    assert response.status_code == 200
    assert result["success"] is True, result
    assert "passed" in result["validation"]
    assert "+    return value + 2" in result["diff"]
    assert {p.name: p.read_bytes() for p in harness.repo.iterdir() if p.is_file()} == before
    assert harness.calls == []


def test_public_apply_validation_failure_rolls_back_and_reports_actual_state(harness):
    payload = _candidate(NEW.replace("+ 2", "- 1"))
    before = (harness.repo / "app.py").read_bytes()

    result = _apply(harness, payload)

    assert result["success"] is False, result
    assert result["execution_attempted"] is True
    assert result["rollback_performed"] is True
    assert result["patch_applied"] is False
    assert result["final_repository_changed"] is False
    assert result["final_validation_outcome"] == "failed"
    assert result["phase"] == "validation_failed"
    assert result["validation_outcome"] == "failed"
    assert result["failure_info"]
    assert (harness.repo / "app.py").read_bytes() == before
    assert "rolled back" in result["message"].lower()


def test_public_apply_risk_refusal_does_not_claim_validation_failed(harness):
    payload = _candidate()
    payload["patch_candidate"].pop("target_node_name")
    payload["patch_candidate"].pop("target_node_kind")

    result = _apply(harness, payload)

    assert result["success"] is False
    assert result["rollback_performed"] is True
    assert result["validation"] in (None, "")
    assert result["phase"] == "post_apply_blocked"
    assert result["validation_outcome"] is None
    assert result["failure_info"] is None
    assert result["final_repository_changed"] is False
    assert (harness.repo / "app.py").read_text(encoding="utf-8") == OLD
    assert "validation failed" not in result["message"].lower(), result
    assert "risk" in result["message"].lower(), result


def test_public_apply_inconclusive_validation_preserves_reason_and_rolls_back(harness):
    (harness.repo / "test_app.py").write_text(
        "# No runnable tests are present in this repository yet.\n",
        encoding="utf-8",
    )
    before = (harness.repo / "app.py").read_bytes()

    result = _apply(harness, _candidate())

    assert result["success"] is False
    assert result["rollback_performed"] is True
    assert result["phase"] == "validation_environment_failed", result
    assert result["validation_outcome"] == "inconclusive"
    assert result["final_validation_outcome"] == "inconclusive"
    assert "inconclusive" in result["message"].lower()
    assert "validation failed" not in result["message"].lower()
    assert "rolled back" in result["message"].lower()
    assert result["failure_info"]["category"] in result["message"]
    assert (harness.repo / "app.py").read_bytes() == before


@pytest.mark.parametrize("failure", ["operation_conflict", "no_tests", "assertion_failure"])
def test_public_apply_plan_rollback_preserves_actual_failure(harness, failure):
    replacement = NEW.replace("+ 2", "- 1") if failure == "assertion_failure" else NEW
    plan = [{
        "op": "replace_snippet",
        "relative_path": "app.py",
        "target_snippet": OLD,
        "patched_snippet": replacement,
    }]
    if failure == "operation_conflict":
        plan.append({
            "op": "replace_snippet",
            "relative_path": "app.py",
            "target_snippet": "# this text does not exist\n",
            "patched_snippet": "# replacement\n",
        })
    elif failure == "no_tests":
        (harness.repo / "test_app.py").write_text("# no tests yet\n", encoding="utf-8")
    before = (harness.repo / "app.py").read_bytes()

    response = harness.client.post(
        "/apply_patch_plan",
        headers=harness.headers,
        data={
            "repo_path": str(harness.repo),
            "patch_style": "balanced",
            "apply_policy": "ask",
            "patch": json.dumps({"patch_basis": "explicit_change_request", "patch_plan": plan}),
        },
    )
    result = response.get_json()
    (harness.root / "apply_plan_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    assert response.status_code == 200
    assert result["success"] is False, result
    assert result["rollback_performed"] is True, result
    assert result["final_repository_changed"] is False
    assert result["patch_applied"] is False
    assert (harness.repo / "app.py").read_bytes() == before
    assert "rolled back" in result["message"].lower()
    assert result["error"] in result["message"]
    if failure == "operation_conflict":
        assert result["failed_op_index"] == 1
        assert result["failed_op"]["op"] == "replace_snippet"
        assert "not found verbatim" in result["message"]
        assert result["validation"] in (None, "")
        assert result["validation_outcome"] is None
        assert "validation failed" not in result["message"].lower()
    elif failure == "no_tests":
        assert result["validation_outcome"] == "inconclusive"
        assert result["final_validation_outcome"] == "inconclusive"
        assert result["validation_info"]["category"] == "no_tests_collected"
        assert "inconclusive" in result["message"].lower()
        assert "validation failed" not in result["message"].lower()
    else:
        assert result["validation_outcome"] == "failed"
        assert result["final_validation_outcome"] == "failed"
        assert "validation failed" in result["message"].lower()
