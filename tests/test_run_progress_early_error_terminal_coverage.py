"""HARDEN.PROGRESS.1 regression coverage for early terminal errors.

The covered boundary is the genuine pre-generation harness block reached after
``request_received`` has established a stable shadow run ID.  Progress remains
an optional observer: the application result is compared with writer-disabled
behavior and the writer is always confined to a temporary test root.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from core.run_progress_freshness import classify_run_progress_freshness
from core.run_progress_snapshot_shadow_writer import (
    ALLOWED_WRITE_ROOT,
    BLOCKED,
    CANONICAL_JSON_NAME,
    ENVIRONMENT_FLAG,
    WRITTEN_WITH_WARNINGS,
    safe_update_run_progress_snapshot_shadow,
    safe_write_run_progress_snapshot,
)


RUN_ID = "early-error-run"
RAW_REQUEST_SENTINEL = "RAW_REQUEST_DO_NOT_STORE"
INDEX_TEMPLATE = Path(__file__).resolve().parent.parent / "web" / "templates" / "index.html"


def _snapshot_path(root: Path) -> Path:
    return root / ALLOWED_WRITE_ROOT / RUN_ID / CANONICAL_JSON_NAME


def _read_snapshot(root: Path) -> dict:
    return json.loads(_snapshot_path(root).read_text(encoding="utf-8"))


def _patch_source_missing_run(monkeypatch, runner, repo: Path) -> None:
    """Keep the real runner branch while replacing unrelated external work."""
    control_template = {
        "patch_intent": {
            "file": "app.py",
            "source_snippet": "",
        },
        "top_hypothesis": {"confidence": 0.9},
    }
    monkeypatch.setattr(runner, "build_project_tag", lambda *_args, **_kwargs: "safe-project")
    monkeypatch.setattr(
        runner,
        "inspect_repo_inventory",
        lambda _repo_path: {"ok": True, "file_count": 1},
    )
    monkeypatch.setattr(runner, "detect_repo_language", lambda _repo_path: "python")
    monkeypatch.setattr(runner, "detect_input_mode", lambda _query: "natural_language")
    monkeypatch.setattr(
        runner,
        "classify_task",
        lambda _query, mode, language, audience: {
            "intent": "bug_fix",
            "complexity": "simple",
            "language": language,
            "mode": mode,
            "audience": audience,
        },
    )
    monkeypatch.setattr(
        runner,
        "index_repository",
        lambda _repo_path, project_tag=None: {"phantom_limb": {}},
    )
    monkeypatch.setattr(runner, "clear_graph_cache", lambda _repo_path: None)
    monkeypatch.setattr(runner, "extract_user_validation_command", lambda _query: "")
    monkeypatch.setattr(
        runner,
        "run_preflight_validation",
        lambda **_kwargs: {"ran": False, "ok": None},
    )
    monkeypatch.setattr(
        runner,
        "run_control_structured",
        lambda _query, _repo_path: copy.deepcopy(control_template),
    )
    monkeypatch.setattr(runner, "build_related_snippets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(runner, "get_engineering_memory", lambda **_kwargs: [])
    monkeypatch.setattr(
        runner,
        "maybe_enrich_with_scout",
        lambda **kwargs: kwargs["control_result"],
    )
    monkeypatch.setattr(runner, "get_or_compute_dna", lambda _repo_path: {})
    monkeypatch.setattr(runner, "dna_to_prompt_block", lambda _dna, mode="match": "")
    monkeypatch.setattr(runner, "create_session", lambda **_kwargs: 123)
    monkeypatch.setattr(runner, "save_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        runner,
        "run_draft_pipeline",
        lambda _state: (_ for _ in ()).throw(AssertionError("model must not be called")),
    )
    monkeypatch.setattr(
        runner,
        "maybe_run_auto_patch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("patch must not apply")),
    )
    monkeypatch.setattr(runner, "_RUN_PROGRESS_SNAPSHOT_ROOT", repo.parent)
    monkeypatch.setattr(
        runner,
        "_new_run_progress_shadow_run_id",
        lambda: RUN_ID if runner.is_run_progress_shadow_writer_enabled() else "",
    )


def _run_source_missing(runner, repo: Path) -> dict:
    return runner.run_agent_web(
        f"Analyze unavailable input {RAW_REQUEST_SENTINEL}",
        str(repo),
        runtime_environment="local_linux",
    )


def test_genuine_early_error_reuses_run_id_and_preserves_the_application_result(
    tmp_path,
    monkeypatch,
):
    from core import run_progress_snapshot_shadow_writer as writer
    from web import runner

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('safe fixture')\n", encoding="utf-8")
    _patch_source_missing_run(monkeypatch, runner, repo)

    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    disabled_result = _run_source_missing(runner, repo)
    assert disabled_result["harness_mode"] == "source_missing"
    assert not (tmp_path / ALLOWED_WRITE_ROOT).exists()

    timestamps = iter(("2026-07-13T01:00:00+00:00", "2026-07-13T01:00:01+00:00"))
    monkeypatch.setattr(writer, "_utc_now", lambda: next(timestamps))
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    enabled_result = _run_source_missing(runner, repo)

    # The observer neither replaces nor augments the authoritative error result.
    assert enabled_result == disabled_result
    snapshot = _read_snapshot(tmp_path)
    serialized = _snapshot_path(tmp_path).read_text(encoding="utf-8")

    assert snapshot["run_id"] == snapshot["snapshot_id"] == RUN_ID
    assert snapshot["current_stage_id"] == "error_reported"
    assert snapshot["observed_stage_ids"] == ["request_received", "error_reported"]
    assert snapshot["completed_stage_ids"] == ["request_received"]
    assert snapshot["error_stage_ids"] == ["error_reported"]
    assert snapshot["terminal"] is True
    assert snapshot["sequence_number"] == 2
    assert snapshot["created_at"] == "2026-07-13T01:00:00+00:00"
    assert snapshot["updated_at"] == "2026-07-13T01:00:01+00:00"
    assert snapshot["metadata"]["error_category"] == "application_error"
    assert snapshot["errors"] == ["application_error"]
    assert snapshot["stages"][-1]["errors"] == ["application_error"]
    assert "model_response_received" not in snapshot["observed_stage_ids"]
    assert RAW_REQUEST_SENTINEL not in serialized
    assert str(repo) not in serialized
    assert "source context is missing" not in serialized.lower()
    assert [item.name for item in (tmp_path / ALLOWED_WRITE_ROOT).iterdir()] == [RUN_ID]


def test_duplicate_terminal_error_is_idempotent_and_cannot_regress(tmp_path, monkeypatch):
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    safe_update_run_progress_snapshot_shadow(
        RUN_ID,
        stage_id="request_received",
        repo_root=tmp_path,
    )
    first = safe_write_run_progress_snapshot(
        RUN_ID,
        repo_root=tmp_path,
        outcome="error",
        metadata={
            "mode": "reviewer",
            "source_component": "web.runner",
            "result_type": "terminal_error",
            "error_category": "application_error",
        },
    )
    terminal = _read_snapshot(tmp_path)

    duplicate = safe_write_run_progress_snapshot(
        RUN_ID,
        repo_root=tmp_path,
        outcome="error",
        metadata={
            "mode": "reviewer",
            "source_component": "web.runner",
            "result_type": "terminal_error",
            "error_category": "application_error",
        },
    )
    after_duplicate = _read_snapshot(tmp_path)
    regression = safe_update_run_progress_snapshot_shadow(
        RUN_ID,
        stage_id="model_response_received",
        repo_root=tmp_path,
    )

    assert first["snapshot_written"] is True
    assert duplicate["writer_status"] == WRITTEN_WITH_WARNINGS
    assert duplicate["warning"] == "duplicate_stage_update_ignored"
    assert after_duplicate == terminal
    assert after_duplicate["sequence_number"] == 2
    assert after_duplicate["observed_stage_ids"].count("error_reported") == 1
    assert after_duplicate["error_stage_ids"].count("error_reported") == 1
    assert regression["writer_status"] == BLOCKED
    assert regression["blocked_reason"] == "terminal_snapshot_update_rejected"
    assert _read_snapshot(tmp_path) == terminal


def test_old_corrected_error_remains_terminal_under_existing_freshness_rules(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    safe_update_run_progress_snapshot_shadow(
        RUN_ID,
        stage_id="request_received",
        repo_root=tmp_path,
    )
    safe_update_run_progress_snapshot_shadow(
        RUN_ID,
        stage_id="error_reported",
        error_category="application_error",
        repo_root=tmp_path,
    )

    freshness = classify_run_progress_freshness(
        _read_snapshot(tmp_path),
        observed_at="2126-07-13T01:00:00+00:00",
    )

    assert freshness["freshness_status"] == "terminal"
    assert freshness["terminal"] is True
    assert freshness["terminal_outcome"] == "error"
    assert freshness["terminal_stage_id"] == "error_reported"
    assert freshness["action_triggered"] is False
    assert freshness["actions_available"] == []


def test_terminal_writer_failure_does_not_replace_the_original_error_result(
    tmp_path,
    monkeypatch,
):
    from web import runner

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('safe fixture')\n", encoding="utf-8")
    _patch_source_missing_run(monkeypatch, runner, repo)

    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    expected_result = _run_source_missing(runner, repo)

    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    monkeypatch.setattr(
        runner,
        "safe_write_run_progress_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("private-path writer failure must remain isolated")
        ),
    )
    returned = _run_source_missing(runner, repo)

    assert returned == expected_result
    snapshot = _read_snapshot(tmp_path)
    serialized = _snapshot_path(tmp_path).read_text(encoding="utf-8")
    assert snapshot["observed_stage_ids"] == ["request_received"]
    assert snapshot["terminal"] is False
    assert "private-path" not in serialized


def test_existing_bounded_poller_stops_on_the_corrected_terminal_snapshot():
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")
    terminal_guard = template.index("if (snapshot.terminal === true)")
    terminal_stop = template.index('stopRunProgressPolling("terminal")', terminal_guard)

    assert terminal_guard < terminal_stop
    assert "if (snapshot.terminal === true)" in template
    assert 'stopRunProgressPolling("terminal")' in template
    assert "applyPatch(" not in template[terminal_guard:terminal_stop]
    assert "runValidation" not in template[terminal_guard:terminal_stop]

