from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import goal_brief


def _mock_interviewer(**overrides):
    calls = []

    def interviewer(prompt: str, brief: dict) -> dict:
        calls.append({"prompt": prompt, "brief": brief})
        payload = {
            "assistant_message": "What command did you run, and what happened?",
            "missing_information": ["evidence.command_run", "validation.command"],
            "suggested_terminal_commands": ["git status --short"],
            "problem_type": "",
        }
        payload.update(overrides)
        return payload

    interviewer.calls = calls
    return interviewer


def test_create_brief_from_vague_goal_writes_draft_json(tmp_path):
    interviewer = _mock_interviewer()

    result = goal_brief.create_goal_brief(
        goal="Make login less broken",
        goal_briefs_root=tmp_path,
        interviewer=interviewer,
    )

    assert result["ok"] is True
    assert result["assistant_message"] == "What command did you run, and what happened?"
    assert interviewer.calls

    brief = result["brief"]
    assert set(brief.keys()) == set(goal_brief.GOAL_BRIEF_SCHEMA.keys())
    assert brief["goal"] == "Make login less broken"
    assert brief["status"] == "draft"
    assert brief["evidence"]["actual_result"] == ""
    assert "evidence.command_run" in brief["missing_information"]

    written = Path(result["brief_path"])
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8")) == brief
    assert "summary" not in brief, "saved goal_brief.json must keep the fixed schema"


def test_create_brief_returns_friendly_summary_without_mutating_schema(tmp_path):
    result = goal_brief.create_goal_brief(
        goal="Make goal brief easier to use",
        goal_briefs_root=tmp_path,
        interviewer=_mock_interviewer(),
    )

    summary = result["summary"]
    assert summary["status"] == "draft"
    assert summary["ready"] is False
    assert summary["missing_count"] >= 1
    labels = [row["label"] for row in summary["rows"]]
    assert labels[:4] == ["Goal", "Type", "Observed Behavior", "Validation"]
    assert summary["rows"][0]["value"] == "Make goal brief easier to use"

    saved = json.loads(Path(result["brief_path"]).read_text(encoding="utf-8"))
    assert set(saved.keys()) == set(goal_brief.GOAL_BRIEF_SCHEMA.keys())


def test_create_brief_lists_missing_fields(tmp_path):
    result = goal_brief.create_goal_brief(
        goal="Something is weird",
        goal_briefs_root=tmp_path,
        interviewer=_mock_interviewer(missing_information=[]),
    )

    missing = result["brief"]["missing_information"]
    assert "problem_type" in missing
    assert "evidence.command_run" in missing
    assert "validation.success_criteria" in missing


def test_model_interviewer_cannot_invent_command_output(tmp_path):
    interviewer = _mock_interviewer(
        evidence={
            "command_run": "pytest",
            "actual_result": "3 failed, invented by model",
        },
        suggested_terminal_commands=["python -m pytest tests -q"],
    )

    result = goal_brief.create_goal_brief(
        goal="Fix tests",
        goal_briefs_root=tmp_path,
        interviewer=interviewer,
    )

    brief = result["brief"]
    assert brief["evidence"]["command_run"] == ""
    assert brief["evidence"]["actual_result"] == ""
    assert "python -m pytest tests -q" in brief["suggested_terminal_commands"]


def test_update_brief_with_user_answer_changes_evidence_fields(tmp_path):
    created = goal_brief.create_goal_brief(
        goal="Fix failing checkout test",
        goal_briefs_root=tmp_path,
        interviewer=_mock_interviewer(),
    )

    result = goal_brief.update_goal_brief(
        created["brief_path"],
        answer=json.dumps(
            {
                "problem_type": "bug_fix",
                "evidence": {
                    "command_run": "python -m pytest tests/test_checkout.py -q",
                    "expected_result": "all tests pass",
                    "actual_result": "1 failed in checkout total",
                    "changed_files": ["core/checkout.py"],
                },
                "constraints": {
                    "allowed_files": ["core/checkout.py", "tests/test_checkout.py"],
                    "forbidden_files": [".env"],
                    "do_not_weaken": ["Do not skip checkout validation"],
                },
                "validation": {
                    "command": "python -m pytest tests/test_checkout.py -q",
                    "success_criteria": "pytest exits 0 and checkout totals are correct",
                },
            }
        ),
        goal_briefs_root=tmp_path,
        interviewer=_mock_interviewer(missing_information=[]),
    )

    brief = result["brief"]
    assert brief["evidence"]["command_run"] == "python -m pytest tests/test_checkout.py -q"
    assert brief["evidence"]["actual_result"] == "1 failed in checkout total"
    assert brief["evidence"]["changed_files"] == ["core/checkout.py"]
    assert brief["constraints"]["allowed_files"] == ["core/checkout.py", "tests/test_checkout.py"]


def test_plain_text_answer_accepts_friendly_quick_reply_labels():
    brief = goal_brief.normalize_goal_brief(
        {
            "goal": "Fix checkout",
            "constraints": {"forbidden_files": ["old/forbidden.py"]},
        }
    )

    updated = goal_brief.apply_answer_to_goal_brief(
        brief,
        "\n".join(
            [
                "problem_type: bug_fix",
                "allowed_files: core/checkout.py, tests/test_checkout.py",
                "forbidden_files: none",
                "do_not_weaken: Do not skip checkout validation",
                "success_criteria: pytest exits 0",
            ]
        ),
    )

    assert updated["problem_type"] == "bug_fix"
    assert updated["constraints"]["allowed_files"] == [
        "core/checkout.py",
        "tests/test_checkout.py",
    ]
    assert updated["constraints"]["forbidden_files"] == []
    assert updated["constraints"]["do_not_weaken"] == [
        "Do not skip checkout validation",
    ]
    assert updated["validation"]["success_criteria"] == "pytest exits 0"
    assert updated["evidence"]["actual_result"] == ""


def test_final_prompt_includes_required_task_context(tmp_path):
    created = goal_brief.create_goal_brief(
        goal="Fix checkout totals",
        goal_briefs_root=tmp_path,
        interviewer=_mock_interviewer(),
    )

    result = goal_brief.update_goal_brief(
        created["brief_path"],
        answer=json.dumps(
            {
                "problem_type": "bug_fix",
                "evidence": {
                    "command_run": "python -m pytest tests/test_checkout.py -q",
                    "expected_result": "pass",
                    "actual_result": "FAILED test_checkout_total",
                    "error_output": "AssertionError: 19 != 20",
                    "changed_files": ["core/checkout.py"],
                },
                "constraints": {
                    "allowed_files": ["core/checkout.py"],
                    "forbidden_files": ["database/schema.sql"],
                    "do_not_weaken": ["Do not loosen price assertions"],
                },
                "validation": {
                    "command": "python -m pytest tests/test_checkout.py -q",
                    "success_criteria": "the command exits 0",
                },
            }
        ),
        goal_briefs_root=tmp_path,
        interviewer=_mock_interviewer(missing_information=[]),
    )

    brief = result["brief"]
    prompt = brief["final_prompt"]
    assert brief["status"] == "ready"
    assert "Fix checkout totals" in prompt
    assert "python -m pytest tests/test_checkout.py -q" in prompt
    assert "FAILED test_checkout_total" in prompt
    assert "core/checkout.py" in prompt
    assert "database/schema.sql" in prompt
    assert "Do not loosen price assertions" in prompt
    assert "the command exits 0" in prompt


def test_path_traversal_for_brief_refs_is_blocked(tmp_path):
    outside = tmp_path.parent / "outside_goal_brief.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        goal_brief.resolve_goal_brief_ref(str(outside), goal_briefs_root=tmp_path)

    with pytest.raises(ValueError):
        goal_brief.resolve_goal_brief_ref("../outside_goal_brief.json", goal_briefs_root=tmp_path)


def test_markdown_export_writes_summary(tmp_path):
    result = goal_brief.create_goal_brief(
        goal="Document brittle checkout evidence",
        goal_briefs_root=tmp_path,
        interviewer=_mock_interviewer(),
        export_md=True,
    )

    md_path = Path(result["markdown_path"])
    assert md_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    assert "# Goal Brief" in text
    assert "Document brittle checkout evidence" in text


def test_empty_goal_returns_friendly_error(tmp_path):
    with pytest.raises(ValueError, match="goal must be a non-empty string"):
        goal_brief.create_goal_brief(
            goal="   ",
            goal_briefs_root=tmp_path,
            interviewer=_mock_interviewer(),
        )


def test_goal_brief_core_does_not_import_forbidden_execution_paths():
    source = Path(goal_brief.__file__).read_text(encoding="utf-8")
    forbidden = [
        "run_benchmarks",
        "benchmark_web",
        "patch_plan_executor",
        "run_patch_plan_with_artifacts",
        "seed_lessons_from_benchmark",
        "seed_lessons_from_proposals",
        "promote_lesson",
    ]
    for token in forbidden:
        assert token not in source
