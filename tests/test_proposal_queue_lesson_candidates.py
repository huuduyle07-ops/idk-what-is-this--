"""Phase 6.4b-lite tests for proposal-queue lesson candidate creation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from core import lesson_store
from scripts import run_patch_proposal_queue as queue


def _valid_candidate(**overrides):
    candidate = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_plan",
        "rollback_happened": False,
        "changed_files": ["pricing.py"],
        "diff_stats": {"added": 1, "removed": 1},
        "case_name": "python_discount_validation",
        "language": "python",
        "category": "logic_validation",
        "summary": "Fix the discount validation path.",
    }
    candidate.update(overrides)
    return candidate


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def proposal_queue_env(tmp_path, monkeypatch):
    agent_dir = tmp_path / ".agent"
    bench_dir = agent_dir / "benchmarks"
    proposal_root = agent_dir / "proposals"
    cases_dir = tmp_path / "benchmarks" / "cases"
    case_name = "python_discount_validation"
    case_dir = cases_dir / "python" / case_name
    buggy_repo = case_dir / "buggy_repo"
    buggy_repo.mkdir(parents=True)
    (buggy_repo / "pricing.py").write_text("PRICE = 10\n", encoding="utf-8")

    case_file = case_dir / "case.json"
    case = {
        "name": case_name,
        "language": "python",
        "category": "logic_validation",
        "difficulty": "easy",
        "prompt": "Fix discount validation.",
        "validation_command": "echo OK",
        "expected_changed_files": ["pricing.py"],
        "forbidden_changed_files": ["main.py"],
    }
    _write_json(case_file, case)

    report_file = bench_dir / "benchmark_report_1.json"
    _write_json(
        report_file,
        {
            "results": [
                {
                    "name": case_name,
                    "case_file": str(case_file),
                }
            ]
        },
    )

    monkeypatch.setattr(queue, "BENCH_DIR", bench_dir)
    monkeypatch.setattr(queue, "CASES_DIR", cases_dir)
    monkeypatch.setattr(queue, "PROPOSAL_ROOT", proposal_root)
    monkeypatch.setattr(lesson_store, "get_agent_dir", lambda repo_path=None: agent_dir)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)

    payload = {
        "summary": "Fix the discount validation path.",
        "patch_candidate": None,
        "patch_plan": [
            {
                "op": "replace_snippet",
                "relative_path": "pricing.py",
                "target_snippet": "PRICE = 10",
                "patched_snippet": "PRICE = 20",
            }
        ],
        "needs_human_review": False,
    }
    validation = {
        "ok": True,
        "validation_ok": True,
        "command": "echo OK",
        "duration_sec": 0.1,
        "output": "OK",
    }
    apply_result = {
        "success": True,
        "applied_ops": payload["patch_plan"],
        "diffs": ["--- a/pricing.py\n+++ b/pricing.py\n@@ -1 +1 @@\n-PRICE = 10\n+PRICE = 20\n"],
        "rollback_performed": False,
        "error": None,
    }

    monkeypatch.setattr(queue, "_generate_patch_payload", lambda **_: (payload, "raw json"))
    monkeypatch.setattr(queue, "_run_validation_command", lambda *_, **__: dict(validation))

    import core.run_lifecycle as run_lifecycle

    monkeypatch.setattr(
        run_lifecycle,
        "run_patch_plan_with_artifacts",
        lambda *_, **__: dict(apply_result),
    )

    return {
        "agent_dir": agent_dir,
        "bench_dir": bench_dir,
        "proposal_root": proposal_root,
        "cases_dir": cases_dir,
        "case_name": case_name,
        "report_file": report_file,
        "case_file": case_file,
        "validation": validation,
        "apply_result": apply_result,
    }


def _approved_item(env: dict) -> dict:
    return {
        "kind": "slow_passing_case",
        "case_name": env["case_name"],
        "language": "python",
        "category": "logic_validation",
        "source_benchmark_report": str(env["report_file"]),
        "human_approved_for_proposal": True,
    }


def _process(env: dict, *, create_lesson_candidates: bool = False) -> tuple[dict, Path]:
    run_dir = env["proposal_root"] / "run"
    result = queue._process_item(
        item=_approved_item(env),
        idx=1,
        run_dir=run_dir,
        validation_timeout_sec=10,
        create_lesson_candidates=create_lesson_candidates,
    )
    return result, run_dir / f"01-{queue._slug(env['case_name'])}"


def test_proposal_queue_flag_off_does_not_create_lesson(proposal_queue_env):
    result, _item_dir = _process(proposal_queue_env, create_lesson_candidates=False)

    assert result["status"] == "proposal_validated"
    assert result["validation_ok"] is True
    assert "lesson_id" not in result
    assert lesson_store.list_lessons() == []


def test_proposal_queue_flag_on_creates_candidate_lesson_for_validated_proposal(proposal_queue_env):
    result, item_dir = _process(proposal_queue_env, create_lesson_candidates=True)

    assert result["status"] == "proposal_validated"
    assert result["lesson_candidate_created"] is True
    assert result["lesson_status"] == "candidate"

    lessons = lesson_store.list_lessons()
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson["id"] == result["lesson_id"]
    assert lesson["source"] == "patch_proposal"
    assert lesson["source_report"] == str(item_dir)
    assert lesson["status"] == "candidate"
    assert lesson["active_knowledge_allowed"] is False


def test_proposal_queue_failed_validation_does_not_create_lesson(proposal_queue_env):
    proposal_queue_env["validation"].update(ok=False, validation_ok=False, output="FAIL")

    result, _item_dir = _process(proposal_queue_env, create_lesson_candidates=True)

    assert result["status"] == "proposal_validation_failed"
    assert result["validation_ok"] is False
    assert "lesson_id" not in result
    assert lesson_store.list_lessons() == []


def test_proposal_queue_missing_apply_success_does_not_create_lesson(proposal_queue_env):
    proposal_queue_env["apply_result"].pop("success")

    result, _item_dir = _process(proposal_queue_env, create_lesson_candidates=True)

    assert result["status"] == "proposal_apply_failed"
    assert "lesson_id" not in result
    assert lesson_store.list_lessons() == []


def test_proposal_queue_duplicate_run_does_not_create_duplicate_lesson(proposal_queue_env):
    first, _item_dir = _process(proposal_queue_env, create_lesson_candidates=True)
    second, _item_dir = _process(proposal_queue_env, create_lesson_candidates=True)

    assert first["lesson_candidate_created"] is True
    assert second["lesson_already_exists"] is True
    assert second["lesson_message"] == "lesson already exists"
    assert second["lesson_id"] == first["lesson_id"]
    assert len(lesson_store.list_lessons()) == 1


@pytest.mark.parametrize("existing_status", ["candidate", "active", "blocked"])
def test_existing_lesson_in_any_bucket_prevents_duplicate(
    proposal_queue_env,
    existing_status,
):
    run_dir = proposal_queue_env["proposal_root"] / "run"
    item_dir = run_dir / f"01-{queue._slug(proposal_queue_env['case_name'])}"
    existing = lesson_store.save_candidate_lesson(
        _valid_candidate(),
        source="patch_proposal",
        source_report=str(item_dir),
        case_name=proposal_queue_env["case_name"],
    )
    if existing_status == "active":
        existing = lesson_store.promote_lesson(existing["id"])
    elif existing_status == "blocked":
        existing = lesson_store.block_lesson(existing["id"])

    result, _item_dir = _process(proposal_queue_env, create_lesson_candidates=True)

    assert result["lesson_already_exists"] is True
    assert result["lesson_id"] == existing["id"]
    assert result["lesson_status"] == existing_status
    assert len(lesson_store.list_lessons()) == 1


def test_main_passes_create_lesson_candidates_flag(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    _write_json(
        plan_path,
        {
            "items": [
                {
                    "case_name": "case_x",
                    "human_approved_for_proposal": True,
                }
            ]
        },
    )
    captured = {}

    def fake_process(**kwargs):
        captured["create_lesson_candidates"] = kwargs["create_lesson_candidates"]
        return {"case_name": "case_x", "status": "proposal_validated"}

    monkeypatch.setattr(queue, "PROPOSAL_ROOT", tmp_path / "proposals")
    monkeypatch.setattr(queue, "_process_item", fake_process)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_patch_proposal_queue.py",
            "--plan",
            str(plan_path),
            "--create-lesson-candidates",
        ],
    )

    assert queue.main() == 0
    assert captured["create_lesson_candidates"] is True
