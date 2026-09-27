"""Offline Dream acceptance tests through the public queue/run/report interface.

Only the external Gemini boundary and infrastructure configuration are replaced.
Database persistence is disabled; artifacts stay in the disposable workspace.
CONTROL, Scout, grounding, patch application, validation and report generation run
normally. These tests deliberately assert user contracts, including currently
unmet contracts; do not turn failures into expected failures to make CI green.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

import config
from agents import gemini_client
from core import dream_artifacts, sleeping_consultant


SOURCE = "def version():\n    return 1\n"
CHANGE_TITLE = "Change version() in app.py to return 2 instead of 1"


def _plan(*, safe=False):
    return {
        "status": "planned",
        "item_type": "debt",
        "priority": "medium",
        "problem_summary": CHANGE_TITLE,
        "likely_files": ["app.py"],
        "recommended_steps": ["Read app.py", "Return 2", "Run the acceptance test"],
        "safe_to_patch_now": safe,
        "patch_style_required": "safe_minimal",
        "validation_commands": ["python -m pytest -q test_app.py"],
        "risks": [],
    }


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Keep artifact namespaces, debug paths, and all target code disposable."""
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_bytes(SOURCE.encode())
    (repository / "test_app.py").write_bytes(
        b"from app import version\n\ndef test_requested_version():\n    assert version() == 2\n"
    )
    storage = tmp_path / "artifacts"
    storage.mkdir()
    monkeypatch.setenv("DB_ENABLED", "false")
    monkeypatch.setattr(config, "DB_ENABLED", False)
    monkeypatch.setattr(config, "AGENT_DIR", storage)
    monkeypatch.setattr(config, "OUTPUT_FILE", storage / "session_log.txt")
    # Modules collected earlier can hold `from config import ...` aliases.
    # Update infrastructure values there as well; subsequent lazy imports read
    # the isolated config above. This does not replace any harness decisions.
    for name, module in list(sys.modules.items()):
        if module is None or not name.startswith((
            "core.", "database.", "agents.", "graph.", "reasoning.",
        )):
            continue
        for setting, value in (
            ("DB_ENABLED", False), ("AGENT_DIR", storage),
            ("OUTPUT_FILE", storage / "session_log.txt"),
        ):
            if hasattr(module, setting):
                monkeypatch.setattr(module, setting, value)
    monkeypatch.chdir(tmp_path)

    def offline_connect(*args, **kwargs):
        raise RuntimeError("Network is disabled in Dream blackbox tests")

    monkeypatch.setattr(socket.socket, "connect", offline_connect)
    return repository


def _provider(monkeypatch, response):
    calls = []

    def request(prompt, repo_path=None, **kwargs):
        calls.append(str(prompt))
        value = response(str(prompt), len(calls))
        if isinstance(value, Exception):
            raise value
        return json.dumps(value) if isinstance(value, dict) else value

    # The direct import and the lazy Scout import are the same external boundary.
    monkeypatch.setattr(gemini_client, "run_gemini_request_2", request)
    monkeypatch.setattr(sleeping_consultant, "run_gemini_request_2", request)
    return calls


def _run(repository, items, **kwargs):
    dream_artifacts.write_queue(str(repository), items)
    result = sleeping_consultant.run_overnight(
        str(repository), time_budget_sec=30, retry_per_item=0,
        max_refine_rounds=0, **kwargs,
    )
    assert "error" not in result, result
    persisted = json.loads((Path(result["report_dir"]) / "list.json").read_text())
    assert persisted["items"] == result["items"]
    return result


def _patch_responder(*, safe=True, replacement=2):
    def respond(prompt, _call_number):
        if "Dream planning mode" in prompt:
            return _plan(safe=safe)
        if "You are a repo scout." in prompt:
            return {
                "request_type": "change", "likely_files": ["app.py"],
                "likely_symbols": ["version"], "reason": "The task explicitly names app.py",
            }
        return {
            "confidence": 0.95, "needs_escalation": False,
            "patch_plan": [{
                "op": "replace_snippet", "relative_path": "app.py",
                "target_snippet": SOURCE,
                "patched_snippet": f"def version():\n    return {replacement}\n",
            }],
        }
    return respond


def _patch_calls(calls):
    return [p for p in calls if "Generate patch_plan for:" in p]


def _record_evidence(record_property, calls, result, repository):
    stages = {
        "planning": sum("Dream planning mode" in p for p in calls),
        "scout": sum("You are a repo scout." in p for p in calls),
        "patch_generation": len(_patch_calls(calls)),
        "total": len(calls),
    }
    items = []
    for item in result["items"]:
        item_dir = Path(result["report_dir"]) / item.get("item_dir_name", "")
        detail = {
            "title": item["title"], "status": item["status"],
            "validation_artifact_exists": (item_dir / "validation.log").exists(),
        }
        if (item_dir / "patch.json").exists():
            candidate = json.loads((item_dir / "patch.json").read_text())
            detail["grounding_rejection"] = candidate.get("control_patch_candidate_reject_reason")
        items.append(detail)
    evidence = {
        "provider_stage_counts": stages, "items": items,
        "source_unchanged": (repository / "app.py").read_bytes() == SOURCE.encode(),
        "report_dir": result["report_dir"],
        "database_enabled": config.DB_ENABLED,
    }
    database_module = sys.modules.get("database.memory")
    if database_module is not None:
        evidence["database_alias_enabled"] = database_module.DB_ENABLED
        evidence["database_pool_created"] = database_module._pool is not None
    (Path(result["report_dir"]) / "blackbox_observation.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8",
    )
    record_property("blackbox_observation", json.dumps(evidence))


def test_default_dream_leaves_reviewable_plans_and_preserves_user_code(workspace, monkeypatch, record_property):
    calls = _provider(monkeypatch, lambda _prompt, _number: _plan(safe=True))
    before = {p.name: p.read_bytes() for p in workspace.iterdir() if p.is_file()}
    result = _run(workspace, [
        {"kind": "debt", "title": CHANGE_TITLE},
        {"kind": "idea", "title": "Expose version information in a CLI"},
    ])
    _record_evidence(record_property, calls, result, workspace)
    assert len(calls) == 2
    assert result["dream_mode"] == "plan_only"
    assert all(item["status"] == "planned_no_patch" for item in result["items"])
    for item in result["items"]:
        item_dir = Path(result["report_dir"]) / item["item_dir_name"]
        plan = json.loads((item_dir / "plan_analysis.json").read_text())
        assert plan["recommended_steps"] and plan["validation_commands"]
        assert not (item_dir / "patch_plan.json").exists()
    report = (Path(result["report_dir"]) / "dream_run_summary.md").read_text()
    assert CHANGE_TITLE in report
    assert "Expose version information in a CLI" in report
    assert before == {p.name: p.read_bytes() for p in workspace.iterdir() if p.is_file()}


def test_provider_exception_is_visible_and_next_queue_item_still_completes(workspace, monkeypatch, record_property):
    calls = _provider(monkeypatch, lambda _prompt, number: (
        RuntimeError("offline provider unavailable") if number == 1 else _plan()
    ))
    result = _run(workspace, [
        {"kind": "debt", "title": "First task"},
        {"kind": "debt", "title": "Second task"},
    ])
    _record_evidence(record_property, calls, result, workspace)
    first, second = result["items"]
    assert first["status"] == "error"
    assert "offline provider unavailable" in first["summary"]
    assert second["status"] == "planned_no_patch"
    assert (workspace / "app.py").read_bytes() == SOURCE.encode()


def test_provider_error_text_is_not_reported_as_a_completed_plan(workspace, monkeypatch, record_property):
    calls = _provider(monkeypatch, lambda _prompt, number: (
        "AGENT_ERROR: All candidate models failed (offline quota simulation)."
        if number == 1 else _plan()
    ))
    result = _run(workspace, [
        {"kind": "debt", "title": "Unavailable-provider task"},
        {"kind": "debt", "title": "Independent valid task"},
    ])
    _record_evidence(record_property, calls, result, workspace)
    first, second = result["items"]
    assert second["status"] == "planned_no_patch"
    assert first["status"] in {"error", "failed", "provider_error"}, (
        "A provider error is being presented as a useful completed plan", first
    )


def test_queue_item_plan_only_is_respected_under_global_patch_mode(workspace, monkeypatch, record_property):
    calls = _provider(monkeypatch, _patch_responder())
    result = _run(workspace, [{
        "kind": "bug", "dream_type": "bug_investigation",
        "action_level": "plan_only", "title": CHANGE_TITLE,
    }], dream_mode="patch_if_safe")
    _record_evidence(record_property, calls, result, workspace)
    assert (workspace / "app.py").read_bytes() == SOURCE.encode()
    assert not _patch_calls(calls), (
        "An item explicitly configured plan_only requested patch generation",
        result["items"],
    )
    assert result["items"][0]["status"] == "planned_no_patch"


def test_string_false_does_not_authorize_patch_generation(workspace, monkeypatch, record_property):
    calls = _provider(monkeypatch, _patch_responder(safe="false"))
    result = _run(workspace, [{"kind": "debt", "title": CHANGE_TITLE}],
                  dream_mode="patch_if_safe")
    _record_evidence(record_property, calls, result, workspace)
    assert not _patch_calls(calls), (
        "The malformed model value safe_to_patch_now='false' triggered patch generation",
        result["items"],
    )
    assert result["items"][0]["status"] != "ready_to_apply"


def test_unverified_candidate_is_not_ready_even_when_planner_claims_safe(workspace, monkeypatch, record_property):
    """A pass proves rejection, not that Dream ran the behavioral test.

    Current CONTROL rejects this candidate before patch validation. The recorded
    validation_artifact_exists and grounding_rejection expose that limitation.
    """
    calls = _provider(monkeypatch, _patch_responder(replacement=3))
    result = _run(workspace, [{"kind": "debt", "title": CHANGE_TITLE}],
                  dream_mode="patch_if_safe")
    _record_evidence(record_property, calls, result, workspace)
    assert _patch_calls(calls), "The fixture did not reach patch generation"
    assert (workspace / "app.py").read_bytes() == SOURCE.encode()

    # Independent oracle: the model's proposed code is syntactically valid but
    # fails the real task's supplied acceptance test. No harness decision mocked.
    oracle = workspace.parent / "acceptance-oracle"
    oracle.mkdir()
    (oracle / "app.py").write_bytes(b"def version():\n    return 3\n")
    (oracle / "test_app.py").write_bytes((workspace / "test_app.py").read_bytes())
    check = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_app.py"],
        cwd=oracle, capture_output=True, text=True, timeout=30,
    )
    (oracle / "acceptance-result.txt").write_text(check.stdout + check.stderr, encoding="utf-8")
    assert check.returncode == 1 and "assert 3 == 2" in check.stdout
    item = result["items"][0]
    assert item["status"] != "ready_to_apply", (
        "Dream advertises a candidate as ready despite failing the supplied acceptance test", item
    )


@pytest.mark.parametrize("response", ["", "not json", "{}", '{"error": "quota exceeded"}'])
def test_invalid_planning_output_reports_error_and_keeps_queue_moving(workspace, monkeypatch, response):
    calls = _provider(monkeypatch, lambda _prompt, number: response if number == 1 else _plan())
    result = _run(workspace, [
        {"kind": "bug", "title": "Invalid planning output"},
        {"kind": "debt", "title": "Valid next plan"},
    ])
    first, second = result["items"]
    assert first["status"] == "error"
    assert second["status"] == "planned_no_patch"
    assert (Path(result["report_dir"]) / first["item_dir_name"] / "error.txt").exists()
    assert not _patch_calls(calls)


@pytest.mark.parametrize("safe", ["true", 1, [True], {"approved": True}, None])
def test_non_boolean_safety_values_never_request_a_patch(workspace, monkeypatch, safe):
    calls = _provider(monkeypatch, _patch_responder(safe=safe))
    result = _run(workspace, [{"kind": "bug", "title": CHANGE_TITLE}], dream_mode="patch_if_safe")
    assert len(calls) == 1
    assert not _patch_calls(calls)
    assert result["items"][0]["status"] == "error"
    assert "JSON boolean" in result["items"][0]["summary"]
    assert (workspace / "app.py").read_bytes() == SOURCE.encode()


@pytest.mark.parametrize("permission", ["proposal_draft", "unknown", None, True])
def test_non_patch_item_permissions_cannot_inherit_global_patch_permission(workspace, monkeypatch, permission):
    calls = _provider(monkeypatch, _patch_responder())
    result = _run(workspace, [{
        "kind": "debt", "title": CHANGE_TITLE, "action_level": permission,
    }], dream_mode="patch_if_safe")
    assert len(calls) == 1
    assert not _patch_calls(calls)
    assert result["items"][0]["effective_dream_mode"] == "plan_only"
    assert result["items"][0]["status"] == "planned_no_patch"


def test_item_patch_permission_cannot_upgrade_a_plan_only_run(workspace, monkeypatch):
    calls = _provider(monkeypatch, _patch_responder())
    result = _run(workspace, [{
        "kind": "bug", "title": CHANGE_TITLE, "action_level": "patch_if_safe",
    }], dream_mode="plan_only")
    assert len(calls) == 1
    assert not _patch_calls(calls)
    assert result["items"][0]["effective_dream_mode"] == "plan_only"


def test_report_only_item_writes_research_under_global_patch_mode(workspace, monkeypatch):
    calls = _provider(monkeypatch, lambda prompt, _number: (
        _plan(safe=True) if "Dream planning mode" in prompt
        else "# Proposal\nMeasure cache misses before changing the design."
    ))
    result = _run(workspace, [{
        "kind": "research", "title": "Cache study", "action_level": "report_only",
    }], dream_mode="patch_if_safe")
    item = result["items"][0]
    assert item["status"] == "research_note_created"
    assert item["effective_dream_mode"] == "research"
    assert (Path(result["report_dir"]) / item["item_dir_name"] / "proposal.md").exists()
    assert not _patch_calls(calls)


@pytest.mark.parametrize("dream_mode,kind,extra", [
    ("research", "research", {}),
    ("patch_if_safe", "idea", {"patch_style": "vibe"}),
    ("case_idea_research", "reference_study", {}),
])
def test_provider_errors_do_not_become_successful_notes(workspace, monkeypatch, dream_mode, kind, extra):
    calls = _provider(monkeypatch, lambda _prompt, _number: "  AGENT_ERROR: offline quota failure")
    result = _run(workspace, [{
        "kind": kind, "title": "Failure must remain visible", "notes": "Study cache invalidation.",
    }], dream_mode=dream_mode, **extra)
    assert result["items"][0]["status"] == "error"
    assert "offline quota failure" in result["items"][0]["summary"]
    assert len(calls) == 1


def test_provider_error_during_patch_generation_is_not_downgraded_to_a_plan(workspace, monkeypatch):
    respond = _patch_responder()
    calls = _provider(monkeypatch, lambda prompt, number: (
        "AGENT_ERROR: patch provider unavailable"
        if "Generate patch_plan for:" in prompt else respond(prompt, number)
    ))
    result = _run(workspace, [{"kind": "bug", "title": CHANGE_TITLE}], dream_mode="patch_if_safe")
    assert len(_patch_calls(calls)) == 1
    assert result["items"][0]["status"] == "error"
    assert "patch provider unavailable" in result["items"][0]["summary"]
    assert (workspace / "app.py").read_bytes() == SOURCE.encode()


@pytest.mark.parametrize("dream_mode", ["plan_only", "research"])
def test_refinement_error_does_not_count_as_an_improved_artifact(workspace, monkeypatch, dream_mode):
    calls = _provider(monkeypatch, lambda prompt, _number: (
        "AGENT_ERROR: refinement provider unavailable" if "CRITICAL REVIEW INSTRUCTIONS:" in prompt
        else _plan() if "Dream planning mode" in prompt else "# Original research proposal"
    ))
    dream_artifacts.write_queue(str(workspace), [{"kind": "debt", "title": CHANGE_TITLE}])
    result = sleeping_consultant.run_overnight(
        str(workspace), dream_mode=dream_mode, time_budget_sec=90,
        retry_per_item=0, max_refine_rounds=1,
    )
    item = result["items"][0]
    assert item["refinement_attempt_count"] == 1
    assert item["refinement_count"] == 0
    assert item["refinement_history"][0]["ok"] is False
    assert "refinement provider unavailable" in item["latest_refinement_error_summary"]
    assert "latest_refined_artifact" not in item
    assert not _patch_calls(calls)
