from __future__ import annotations

import json
from pathlib import Path


def _patch_runner_basics(monkeypatch, runner, repo: Path, control_result: dict):
    monkeypatch.setattr(
        runner,
        "inspect_repo_inventory",
        lambda repo_path: {"ok": True, "file_count": 1},
    )
    monkeypatch.setattr(runner, "detect_repo_language", lambda repo_path: "python")
    monkeypatch.setattr(
        runner,
        "classify_task",
        lambda query, mode, language, audience: {
            "intent": "bug_fix",
            "complexity": "simple",
            "language": language,
        },
    )
    monkeypatch.setattr(runner, "index_repository", lambda repo_path, project_tag=None: {})
    monkeypatch.setattr(runner, "clear_graph_cache", lambda repo_path: None)
    monkeypatch.setattr(
        runner,
        "run_preflight_validation",
        lambda repo_path, language, command=None: {"ran": False, "ok": None},
    )
    monkeypatch.setattr(runner, "run_control_structured", lambda query, repo_path: control_result)
    monkeypatch.setattr(runner, "build_related_snippets", lambda control, repo_path: [])
    monkeypatch.setattr(runner, "get_engineering_memory", lambda **kwargs: [])
    monkeypatch.setattr(runner, "maybe_enrich_with_scout", lambda **kwargs: kwargs["control_result"])
    monkeypatch.setattr(runner, "get_or_compute_dna", lambda repo_path: {})
    monkeypatch.setattr(runner, "dna_to_prompt_block", lambda dna, mode="match": "")
    monkeypatch.setattr(runner, "create_session", lambda **kwargs: 123)
    monkeypatch.setattr(runner, "memory_note_exists", lambda *args, **kwargs: True)
    monkeypatch.setattr(runner, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "save_engineering_memory", lambda *args, **kwargs: None)


def test_web_runner_returns_harness_metadata_and_skips_model_when_generation_forbidden(
    tmp_path,
    monkeypatch,
):
    from web import runner

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('old')\n", encoding="utf-8")
    control_result = {
        "patch_intent": {
            "file": "app.py",
            "source_snippet": "",
        },
        "top_hypothesis": {"confidence": 0.9},
    }
    _patch_runner_basics(monkeypatch, runner, repo, control_result)
    monkeypatch.setattr(
        runner,
        "run_draft_pipeline",
        lambda state: (_ for _ in ()).throw(AssertionError("model should not be called")),
    )
    monkeypatch.setattr(
        runner,
        "maybe_run_auto_patch",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("patch should not apply")),
    )

    result = runner.run_agent_web(
        "fix app.py",
        str(repo),
        runtime_environment="local_linux",
    )

    assert result["harness_mode"] == "source_missing"
    assert result["harness_mode_decision"]["can_generate_patch"] is False
    assert result["harness_mode_decision"]["can_apply_patch"] is False
    assert "source context is missing" in result["answer"]
    assert "source_missing" in result["state"]


def test_web_runner_surfaces_environment_conflict_deny_and_skips_model(
    tmp_path,
    monkeypatch,
):
    from web import runner

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('old')\n", encoding="utf-8")
    requested_path = r"C:\Users\Administrator\Desktop\ml-data\app.py"
    control_result = {
        "patch_intent": {
            "file": requested_path,
            "source_snippet": "print('old')",
        },
        "top_hypothesis": {"confidence": 0.9, "recommended_action": "patch"},
    }
    _patch_runner_basics(monkeypatch, runner, repo, control_result)
    monkeypatch.setattr(
        runner,
        "run_draft_pipeline",
        lambda state: (_ for _ in ()).throw(AssertionError("model should not be called")),
    )
    monkeypatch.setattr(
        runner,
        "maybe_run_auto_patch",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("patch should not apply")),
    )

    result = runner.run_agent_web(
        f"fix {requested_path}",
        str(repo),
        runtime_environment="codespaces",
    )

    assert result["harness_mode"] == "codespaces_local_path_mismatch"
    assert result["harness_mode_decision"]["can_generate_patch"] is False
    assert result["harness_mode_decision"]["can_apply_patch"] is False
    assert "Cannot run: environment/path mismatch." in result["answer"]
    assert "Current runtime environment: codespaces" in result["answer"]
    assert f"Active repo root: {repo.resolve()}" in result["answer"]
    assert f"Requested path: {requested_path}" in result["answer"]
    assert "Detected path environment: local_windows" in result["answer"]
    assert "Gemini/model was not called" in result["answer"]


def test_web_runner_marks_ungrounded_patch_and_does_not_apply(
    tmp_path,
    monkeypatch,
):
    from web import runner

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('old')\n", encoding="utf-8")
    control_result = {
        "patch_intent": {
            "file": "app.py",
            "source_snippet": "",
        },
        "top_hypothesis": {"confidence": 0.9, "recommended_action": "patch"},
    }
    _patch_runner_basics(monkeypatch, runner, repo, control_result)
    monkeypatch.setattr(
        runner,
        "build_related_snippets",
        lambda control, repo_path: [{"file": "app.py", "snippet": "print('old')"}],
    )
    monkeypatch.setattr(
        runner,
        "run_draft_pipeline",
        lambda state: json.dumps(
            {
                "summary": "bad target",
                "issues": [],
                "patch_candidate": {
                    "relative_path": "app.py",
                    "target_snippet": "print('missing')",
                    "patched_snippet": "print('new')",
                },
                "patch_plan": None,
                "confidence": 0.9,
                "needs_escalation": False,
            }
        ),
    )
    monkeypatch.setattr(runner, "run_review_pipeline", lambda state, draft: draft)
    monkeypatch.setattr(
        runner,
        "maybe_run_auto_patch",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("patch should not apply")),
    )

    result = runner.run_agent_web(
        "fix app.py",
        str(repo),
        runtime_environment="local_windows",
    )

    assert result["harness_mode"] == "ungrounded_patch_blocked"
    assert result["harness_mode_decision"]["can_apply_patch"] is False
    assert "ungrounded_patch_blocked" in result["state"]
    assert "print('old')" in (repo / "app.py").read_text(encoding="utf-8")
