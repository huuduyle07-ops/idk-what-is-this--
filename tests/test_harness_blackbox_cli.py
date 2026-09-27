"""Customer-contract tests through main.main and simulated terminal input.

The SDK transport is scripted; routing, CLI intake, plan execution, patching,
validation and output persistence are real. Deliberately unmet contracts remain
ordinary failures. These are offline harness tests, not model-quality tests.
Session creation also runs through the real disabled-persistence profile.
"""
from __future__ import annotations

import json
import socket
import sys
import time
from types import SimpleNamespace

import pytest


SOURCE = "def calculate_postage(weight):\n    return weight + 1\n"
REPLACEMENT = SOURCE.replace("+ 1", "+ 2")


@pytest.fixture
def terminal(tmp_path, monkeypatch):
    for name in (
        "DB_ENABLED", "INDEX_USE_EMBEDDINGS", "RETRIEVER_USE_EMBEDDINGS",
        "RETRIEVER_USE_DB", "ROUTER_USE_EMBEDDINGS", "AUTO_PATCH_ENABLED",
        "OLLAMA_ENABLED", "RUN_PROGRESS_SNAPSHOT_SHADOW_ENABLED",
        "MIRROR_TUNNEL_SHADOW_LIVE_TRACE_ENABLED",
    ):
        monkeypatch.setenv(name, "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "off")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("MAX_MODEL_FALLBACKS", "1")

    import config
    import main
    from agents import deepseek_client, gemini_client
    from cli import interactive
    from core import index_manifest, pipeline, session_io
    from database import memory

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    monkeypatch.setattr(config, "AGENT_DIR", artifacts)
    monkeypatch.setattr(config, "STORAGE_PATH", artifacts)
    monkeypatch.setattr(config, "OUTPUT_FILE", artifacts / "session_log.txt")
    monkeypatch.setattr(index_manifest, "AGENT_DIR", artifacts)
    monkeypatch.setattr(session_io, "OUTPUT_FILE", artifacts / "session_log.txt")
    monkeypatch.setattr(memory, "DB_ENABLED", False)
    monkeypatch.setattr(config, "AUTO_PATCH_ENABLED", False)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    monkeypatch.setattr(deepseek_client, "ollama", None)
    monkeypatch.setattr(gemini_client, "GOOGLE_API_KEY", "offline-test-key")

    def no_network(*args, **kwargs):
        raise AssertionError("Unexpected network access in offline CLI test")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "customer_repo"
    repo.mkdir()
    target = repo / "postage.py"
    target.write_bytes(SOURCE.encode())
    (repo / "test_postage.py").write_bytes(
        b"from postage import calculate_postage\n\n"
        b"def test_requested_postage():\n    assert calculate_postage(3) == 5\n"
    )
    (repo / "pytest.ini").write_bytes(b"[pytest]\npythonpath = .\n")

    plan = {
        "goal": "Change calculate_postage to add two",
        "confidence": 0.99, "needs_escalation": False,
        "subtasks": [{
            "id": "S1", "action": "edit", "targets": [str(target)],
            "reason": "The requested postage surcharge is two",
            "expected_outcome": "calculate_postage(3) returns 5",
        }],
    }
    patch = {
        "status": "success", "summary": "Change surcharge to two", "blocked": False,
        "confidence": 0.99, "needs_escalation": False,
        "patch_candidate": {
            "file": str(target), "relative_path": "postage.py",
            "target_node_name": "calculate_postage", "target_node_kind": "function",
            "target_snippet": SOURCE.rstrip(), "patched_snippet": REPLACEMENT.rstrip(),
            "issue": "Requested postage adjustment",
        },
    }

    def run(question, *, provider_error=False, persistence_adapter=False,
            auto_patch_enabled=False, second_step=False, author_blocked=False):
        calls = []
        monkeypatch.setattr(config, "AUTO_PATCH_ENABLED", auto_patch_enabled)
        monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", auto_patch_enabled)
        if persistence_adapter:
            monkeypatch.setattr(interactive, "create_session", lambda **kw: 1)
        response_plan = {**plan, "subtasks": list(plan["subtasks"])}
        if second_step:
            response_plan["subtasks"].append({
                "id": "S2", "action": "inspect", "targets": [str(target)],
                "reason": "Inspect the result of the preceding edit",
            })

        def generate_content(*, contents, **kwargs):
            prompt = str(contents[0])
            calls.append(prompt)
            if provider_error:
                raise RuntimeError("offline provider unavailable")
            if "You are a repo scout." in prompt:
                response = {"request_type": "change", "likely_files": ["postage.py"],
                            "likely_symbols": ["calculate_postage"]}
            elif "You are an execution agent performing one step" in prompt:
                response = {**patch, "blocked": True, "status": "blocked"} if author_blocked else patch
            elif "You are replanning after a failure" in prompt:
                response = {"goal": plan["goal"], "subtasks": [], "confidence": 0.99}
            elif "memory" in prompt[:150].lower():
                response = []
            else:
                response = response_plan
            return SimpleNamespace(text=json.dumps(response), usage_metadata=None)

        def client(**kwargs):
            return SimpleNamespace(
                models=SimpleNamespace(generate_content=generate_content),
                files=SimpleNamespace(upload=lambda **kw: SimpleNamespace(uri="offline://fixture")),
            )

        monkeypatch.setattr(gemini_client.genai, "Client", client)
        replies = iter(["agent", "planner", "safe_minimal", "n", question,
                        str(repo), "cli-blackbox", "exit"])
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(replies))
        monkeypatch.setattr(sys, "argv", ["main.py", "--cli"])
        finished_runs = []
        real_finish = main.finish_task_run

        def record_finished_run(**kwargs):
            finished_runs.append(kwargs)
            return real_finish(**kwargs)

        monkeypatch.setattr(main, "finish_task_run", record_finished_run)
        before = target.read_bytes()
        started = time.perf_counter()
        error = None
        try:
            main.main()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        evidence = {
            "model_calls": len(calls),
            "subtask_calls": sum("You are an execution agent performing one step" in p for p in calls),
            "elapsed_sec": round(time.perf_counter() - started, 4),
            "source_unchanged": target.read_bytes() == before,
            "source_after": target.read_text(),
            "auto_patch_enabled": pipeline.AUTO_PATCH_ENABLED,
            "persistence_adapter": persistence_adapter,
            "error": error,
            "finished_run_status": finished_runs[-1]["status"] if finished_runs else None,
        }
        (tmp_path / "cli-result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print("BLACKBOX_CLI_RESULT " + json.dumps(evidence))
        return evidence

    return run


def test_terminal_read_only_request_cannot_execute_model_supplied_edit_plan(terminal, record_property):
    result = terminal("Explain what calculate_postage does in postage.py. Do not change any files.")
    record_property("evidence", json.dumps(result))
    assert result["error"] is None, result
    assert result["source_unchanged"], result
    assert result["subtask_calls"] == 0, result


def test_terminal_planner_respects_disabled_automatic_writes(terminal, record_property):
    result = terminal(
        "Change calculate_postage in postage.py to add two."
    )
    record_property("evidence", json.dumps(result))
    assert result["error"] is None, result
    assert result["subtask_calls"] > 0, "The scenario did not reach planner execution"
    assert result["source_unchanged"], (
        "AUTO_PATCH_ENABLED=false must preserve customer source until explicit apply; " + json.dumps(result)
    )


def test_terminal_provider_failure_halts_without_modifying_source(terminal, capsys, record_property):
    result = terminal("Change calculate_postage in postage.py to add two.", provider_error=True)
    record_property("evidence", json.dumps(result))
    assert result["error"] is None, result
    output = capsys.readouterr().out
    assert "Pipeline Halted: Step 1 failed" in output, output
    assert result["source_unchanged"], result
    assert result["subtask_calls"] == 0, result


def test_terminal_starts_without_database_when_persistence_is_disabled(terminal, record_property):
    result = terminal("Explain calculate_postage in postage.py.", persistence_adapter=False)
    record_property("evidence", json.dumps(result))
    assert result["source_unchanged"], result
    assert result["error"] is None, (
        "DB_ENABLED=false should support a local CLI session; " + json.dumps(result)
    )


def test_terminal_pauses_dependent_steps_and_shows_unapplied_proposal(terminal, capsys):
    result = terminal("Change calculate_postage in postage.py to add two.", second_step=True)
    output = capsys.readouterr().out
    assert result["error"] is None, result
    assert result["source_unchanged"], result
    assert result["subtask_calls"] == 1, result
    assert result["finished_run_status"] == "blocked", result
    assert '"remaining_subtasks"' in output and '"S2"' in output
    assert '"patched_snippet"' in output and "weight + 2" in output
    assert "The proposed edit was not applied" in output


def test_terminal_does_not_apply_an_author_blocker_even_with_auto_patch_enabled(terminal):
    result = terminal("Change calculate_postage in postage.py to add two.",
                      auto_patch_enabled=True, author_blocked=True)
    assert result["error"] is None, result
    assert result["source_unchanged"], result
    assert result["subtask_calls"] == 1, result


def test_terminal_enabled_planner_still_applies_and_validates_its_edit(terminal, capsys):
    result = terminal("Change calculate_postage in postage.py to add two.", auto_patch_enabled=True)
    output = capsys.readouterr().out
    assert result["error"] is None, result
    assert result["source_after"] == REPLACEMENT, result
    assert result["finished_run_status"] == "succeeded", result
    assert "Patch OK + validation passed" in output
