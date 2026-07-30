from __future__ import annotations

import json
from pathlib import Path


def _patch_runner_basics(monkeypatch, runner, repo: Path, control_result: dict):
    monkeypatch.setattr(
        runner,
        "classify_task",
        lambda query, mode, language, audience: {
            "intent": "bug_fix",
            "complexity": "simple",
            "language": language,
        },
    )
    monkeypatch.setattr(
        runner,
        "index_repository",
        lambda repo_path, project_tag=None, **kwargs: {},
    )
    monkeypatch.setattr(runner, "clear_graph_cache", lambda repo_path: None)
    monkeypatch.setattr(
        runner,
        "run_preflight_validation",
        lambda repo_path, language, command=None, **kwargs: {
            "ran": False,
            "ok": None,
        },
    )
    monkeypatch.setattr(
        runner,
        "run_control_structured",
        lambda query, repo_path, **kwargs: control_result,
    )
    monkeypatch.setattr(
        runner,
        "build_related_snippets",
        lambda control, repo_path, **kwargs: [],
    )
    monkeypatch.setattr(runner, "get_engineering_memory", lambda **kwargs: [])
    monkeypatch.setattr(runner, "maybe_enrich_with_scout", lambda **kwargs: kwargs["control_result"])
    monkeypatch.setattr(
        runner,
        "get_or_compute_dna",
        lambda repo_path, **kwargs: {},
    )
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


def test_web_runner_propagates_delta_shadow_through_harness_block(
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
    delta_shadow = {
        "mode": "shadow_only",
        "manifest": {"status": "loaded"},
    }
    _patch_runner_basics(monkeypatch, runner, repo, control_result)
    monkeypatch.setattr(
        runner,
        "index_repository",
        lambda repo_path, project_tag=None, **kwargs: {
            "delta_shadow": delta_shadow,
        },
    )
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
        runtime_environment="local_windows",
    )

    assert result["harness_mode"] == "source_missing"
    assert result["delta_shadow"] == delta_shadow
    assert control_result["delta_shadow"] == delta_shadow


def test_web_runner_propagates_delta_shadow_for_empty_repository(
    tmp_path,
    monkeypatch,
):
    from web import runner

    repo = tmp_path / "empty-repo"
    repo.mkdir()
    delta_shadow = {
        "mode": "shadow_only",
        "manifest": {"status": "missing"},
    }
    indexing_error = RuntimeError("No indexable files found")
    indexing_error.delta_shadow = delta_shadow

    def fail_empty_index(*args, **kwargs):
        raise indexing_error

    monkeypatch.setattr(runner, "index_repository", fail_empty_index)
    monkeypatch.setattr(
        runner,
        "run_draft_pipeline",
        lambda state: (_ for _ in ()).throw(AssertionError("model should not be called")),
    )

    result = runner.run_agent_web(
        "inspect this repository",
        str(repo),
        runtime_environment="local_windows",
    )

    assert result["harness_mode"] == "source_missing"
    assert "contains 0 indexable files" in result["answer"]
    assert result["delta_shadow"] == delta_shadow


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
    assert "C.A.T.T.U.S is running in: GitHub Codespaces" in result["answer"]
    assert "Requested path looks like: Local Windows" in result["answer"]
    assert f"Active repo root:\n{repo.resolve()}" in result["answer"]
    assert f"Requested path:\n{requested_path}" in result["answer"]
    assert "GitHub Codespaces cannot access files on your Windows computer." in result["answer"]
    assert "Gemini was not called." in result["answer"]


def test_web_runner_windows_repo_path_in_codespaces_denies_before_source_missing(
    monkeypatch,
):
    from web import runner

    repo_path = r"C:\Users\Admin\Documents\Code\day 14\AI project\app.py"
    monkeypatch.setattr(
        runner,
        "run_draft_pipeline",
        lambda state: (_ for _ in ()).throw(AssertionError("model should not be called")),
    )

    result = runner.run_agent_web(
        "fix it",
        repo_path,
        runtime_environment="codespaces",
    )

    assert result["harness_mode"] == "codespaces_local_path_mismatch"
    assert "Cannot run: environment/path mismatch." in result["answer"]
    assert "Requested path looks like: Local Windows" in result["answer"]
    assert repo_path in result["answer"]
    assert "source_missing" not in result["answer"]


def test_generate_candidates_denies_environment_conflict_without_model_call(monkeypatch):
    from web import app as web_app

    repo_path = r"C:\Users\Admin\Documents\Code\day 14\AI project\app.py"
    control = {
        "patch_intent": {
            "file": "app.py",
            "source_snippet": "print('old')",
        }
    }
    monkeypatch.setattr(
        web_app,
        "run_gemini_request",
        lambda prompt: (_ for _ in ()).throw(AssertionError("Gemini should not be called")),
    )
    monkeypatch.setattr(
        web_app,
        "run_deepseek_review",
        lambda prompt: (_ for _ in ()).throw(AssertionError("DeepSeek should not be called")),
    )

    with web_app.app.test_client() as client:
        response = client.post(
            "/generate_candidates",
            data={
                "control": json.dumps(control),
                "repo_path": repo_path,
                "runtime_environment": "codespaces",
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["harness_mode"] == "codespaces_local_path_mismatch"
    assert "Cannot run: environment/path mismatch." in data["error"]
    assert "Gemini was not called." in data["error"]


def test_generate_patch_denies_environment_conflict_without_model_call(monkeypatch):
    from web import app as web_app

    repo_path = r"C:\Users\Admin\Documents\Code\day 14\AI project\app.py"
    control = {
        "patch_intent": {
            "file": "app.py",
            "source_snippet": "print('old')",
        }
    }
    monkeypatch.setattr(
        web_app,
        "run_gemini_request",
        lambda prompt: (_ for _ in ()).throw(AssertionError("Gemini should not be called")),
    )

    with web_app.app.test_client() as client:
        response = client.post(
            "/generate_patch",
            data={
                "control": json.dumps(control),
                "repo_path": repo_path,
                "runtime_environment": "codespaces",
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["harness_mode"] == "codespaces_local_path_mismatch"
    assert "Cannot run: environment/path mismatch." in data["error"]
    assert "Gemini was not called." in data["error"]


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
        lambda control, repo_path, **kwargs: [
            {"file": "app.py", "snippet": "print('old')"}
        ],
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
