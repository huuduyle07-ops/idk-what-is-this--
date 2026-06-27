"""Tests for UX.8 - Cockpit Usability Checkpoint.

UX.8 audits whether the cockpit workflow hangs together from goal to review.
It is report-only: no routes, execution, model calls, patches, checks, network
calls, launched agents, database writes, or merge powers are added.
"""
from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).parent.parent
_CORE_PATH = _ROOT / "core" / "cockpit_usability_checkpoint.py"
_SCRIPT_PATH = _ROOT / "scripts" / "create_cockpit_usability_checkpoint.py"
_REGISTRY_PATH = _ROOT / "docs" / "roadmap" / "phase_registry.json"


def _core():
    from core.cockpit_usability_checkpoint import (  # type: ignore
        RISK_LEVELS,
        VISIBILITY_STATUSES,
        build_action_hierarchy_findings,
        build_cockpit_usability_checkpoint,
        build_default_workflow_steps,
        build_navigation_findings,
        build_operator_questions,
        build_ux_risks,
        recommend_next_ux_step,
        render_cockpit_usability_checkpoint_markdown,
        score_workflow_steps,
        write_cockpit_usability_checkpoint_artifacts,
    )

    return {
        "RISK_LEVELS": RISK_LEVELS,
        "VISIBILITY_STATUSES": VISIBILITY_STATUSES,
        "build_action_hierarchy_findings": build_action_hierarchy_findings,
        "build_cockpit_usability_checkpoint": build_cockpit_usability_checkpoint,
        "build_default_workflow_steps": build_default_workflow_steps,
        "build_navigation_findings": build_navigation_findings,
        "build_operator_questions": build_operator_questions,
        "build_ux_risks": build_ux_risks,
        "recommend_next_ux_step": recommend_next_ux_step,
        "render_cockpit_usability_checkpoint_markdown": render_cockpit_usability_checkpoint_markdown,
        "score_workflow_steps": score_workflow_steps,
        "write_cockpit_usability_checkpoint_artifacts": write_cockpit_usability_checkpoint_artifacts,
    }


def _script():
    from scripts.create_cockpit_usability_checkpoint import (  # type: ignore
        main,
        run_create_cockpit_usability_checkpoint,
    )

    return run_create_cockpit_usability_checkpoint, main


def _build(**overrides) -> dict:
    return _core()["build_cockpit_usability_checkpoint"](
        repo_path=".",
        created_at="2026-06-27T00:00:00+00:00",
        checkpoint_id="ux8-test",
        **overrides,
    )


def _risk_map(report_or_risks) -> dict:
    risks = report_or_risks.get("ux_risks", report_or_risks)
    return {risk["risk_id"]: risk for risk in risks}


def test_checkpoint_status_is_reviewable():
    report = _build()
    assert report["checkpoint_status"] in {"ready_for_review", "needs_manual_review"}


def test_default_workflow_contains_all_canonical_steps():
    steps = _core()["build_default_workflow_steps"]()
    assert [step["step_id"] for step in steps] == [
        "goal_brief",
        "mode_decision",
        "run_or_chat_start",
        "run_timeline",
        "answer_patch_review",
        "evidence_cards",
        "continue_from_frame",
        "advanced_debug",
    ]


def test_workflow_steps_include_operator_questions():
    steps = _core()["build_default_workflow_steps"]()
    assert all(step.get("operator_question") for step in steps)


def test_visibility_statuses_are_recognized():
    statuses = set(_core()["VISIBILITY_STATUSES"])
    assert statuses == {
        "clear",
        "visible_but_competing",
        "hidden",
        "duplicated",
        "unclear",
        "not_implemented",
    }


def test_risk_levels_are_recognized():
    assert set(_core()["RISK_LEVELS"]) == {"low", "medium", "high"}


def test_usability_scores_are_deterministic():
    score = _core()["score_workflow_steps"]
    steps = _core()["build_default_workflow_steps"]()
    assert score(steps) == score(steps)
    assert score(steps)["overall_usability_score"] == _build()["overall_usability_score"]


def test_hidden_unclear_and_duplicated_steps_lower_score():
    score = _core()["score_workflow_steps"]
    clear_steps = [
        {**step, "visibility_status": "clear", "risk_level": "low"}
        for step in _core()["build_default_workflow_steps"]()
    ]
    degraded_steps = [
        {**step, "visibility_status": "clear", "risk_level": "low"}
        for step in _core()["build_default_workflow_steps"]()
    ]
    degraded_steps[0]["visibility_status"] = "hidden"
    degraded_steps[1]["visibility_status"] = "unclear"
    degraded_steps[2]["visibility_status"] = "duplicated"
    assert score(degraded_steps)["workflow_clarity_score"] < score(clear_steps)["workflow_clarity_score"]


def test_navigation_findings_mention_primary_workflow_and_advanced_debug_separation():
    text = json.dumps(_core()["build_navigation_findings"]()).lower()
    assert "primary workflow" in text
    assert "advanced" in text
    assert "debug" in text


def test_action_hierarchy_findings_cover_action_classes():
    text = json.dumps(_core()["build_action_hierarchy_findings"]()).lower()
    for phrase in ("primary action", "secondary", "dangerous", "debug"):
        assert phrase in text


def test_operator_questions_include_chat_instant_run_merge_question():
    questions = _core()["build_operator_questions"]()
    assert any("Chat and Instant Run merge" in q or "Chat and Instant Run" in q for q in questions)


def test_ux_risks_include_required_ids():
    risks = _risk_map(_build())
    assert "button_soup_risk" in risks
    assert "chat_instant_split_friction" in risks


def test_recommendation_defaults_to_unified_workbench_input_when_split_friction_remains():
    report = _build()
    assert report["recommended_next_step"] == "workbench_unified_input_plan"
    assert report["recommended_next_phase"] == "UX.9 \u2014 Unified Workbench Input Plan"


def test_low_risk_observations_can_recommend_branch_close():
    observations = [
        "button soup risk low",
        "chat instant split friction low",
        "history frame friction low",
        "evidence disconnected risk low",
        "advanced debug overexposure low",
        "timeline hidden risk low",
        "preview action confusion low",
        "goal brief duplication low",
    ]
    report = _build(observations=observations)
    assert report["recommended_next_step"] == "close_ux_branch_checkpoint"
    assert report["recommended_next_phase"] == "UX.CLOSE \u2014 UX Branch Freeze Checkpoint"


def test_manual_review_checklist_contains_key_items():
    report = _build()
    checklist = "\n".join(report["manual_review_checklist"])
    for item in (
        "I can find where to enter the task.",
        "I can tell whether I am chatting or running.",
        "Apply/review patch still feels human-triggered.",
    ):
        assert item in checklist


def test_markdown_contains_required_sections():
    md = _core()["render_cockpit_usability_checkpoint_markdown"](_build())
    for section in (
        "Summary",
        "Workflow Step Review",
        "Usability Scores",
        "Navigation Findings",
        "Action Hierarchy Findings",
        "Operator Questions",
        "UX Risks",
        "Recommended Next Step",
        "Manual Review Checklist",
        "Non-goals",
        "Warnings",
        "Blockers",
        "Guardrails",
        "Boundaries",
    ):
        assert f"## {section}" in md


def test_markdown_contains_boundary_text():
    md = _core()["render_cockpit_usability_checkpoint_markdown"](_build())
    for phrase in (
        "UX.8 is a report-only usability checkpoint.",
        "UX.8 does not add new product powers.",
        "UX.8 does not add backend routes.",
        "UX.8 does not add mutation routes.",
        "UX.8 does not dispatch execution.",
        "UX.8 does not start runs.",
        "UX.8 does not call models.",
        "UX.8 does not apply patches.",
        "UX.8 does not run validation.",
        "UX.8 does not run benchmarks.",
        "UX.8 does not contact network services.",
        "UX.8 does not launch workers.",
        "UX.8 does not push, merge, or open PRs.",
    ):
        assert phrase in md


def test_cli_writes_json_and_markdown(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        checkpoint_id="cli-test",
        created_at="2026-06-27T00:00:00+00:00",
        demo=True,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["checkpoint_id"] == "cli-test"


def test_cli_json_prints_summary_json(capsys, tmp_path):
    _, main = _script()
    code = main([
        "--repo-path", ".",
        "--output-root", str(tmp_path / "out"),
        "--checkpoint-id", "json-test",
        "--created-at", "2026-06-27T00:00:00+00:00",
        "--demo",
        "--json",
    ])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["checkpoint_id"] == "json-test"
    assert printed["recommended_next_phase"] == "UX.9 \u2014 Unified Workbench Input Plan"


def test_demo_mode_uses_static_local_observations_only(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        checkpoint_id="demo-test",
        created_at="2026-06-27T00:00:00+00:00",
        demo=True,
    )
    report = result["report"]
    assert "Buttons feel crowded after UX.7." in report["observations"]
    assert report["guardrails"]["network_call_performed"] is False
    assert report["guardrails"]["model_call_performed"] is False


def test_guardrails_are_safe():
    guardrails = _build()["guardrails"]
    assert guardrails["checkpoint_only"] is True
    for key in (
        "new_product_power_added",
        "new_route_added",
        "mutation_route_added",
        "backend_execution_changed",
        "task_execution_performed",
        "agent_launched",
        "model_call_performed",
        "patch_applied",
        "validation_run",
        "benchmark_run_performed",
        "network_call_performed",
        "database_write_performed",
        "worker_launch_performed",
        "repo_mutation_performed",
        "merge_performed",
    ):
        assert guardrails[key] is False


def test_registry_accepts_ux8():
    data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    ux8 = next((phase for phase in data["phases"] if phase["phase_id"] == "UX.8"), None)
    assert ux8 is not None
    assert ux8["status"] == "complete"
    assert ux8["track"] == "UX"
    assert ux8["prerequisites"] == ["UX.7"]
    assert ux8["automation_level"] == "LOCAL_0_OBSERVE"
    assert ux8["budget_tier"] == "local_only"
    assert ux8["risk_level"] == "low"
    assert ux8["network_allowed"] is False
    assert ux8["model_calls_allowed"] is False
    assert ux8["merge_allowed"] is False
    assert ux8["writes_real_repo"] is False
    assert ".agent/ux/cockpit_usability_checkpoint/cockpit_usability_checkpoint.json" in ux8["expected_artifacts"]


def test_source_contains_no_forbidden_behavior_tokens():
    core_src = _CORE_PATH.read_text(encoding="utf-8") if _CORE_PATH.is_file() else ""
    script_src = _SCRIPT_PATH.read_text(encoding="utf-8") if _SCRIPT_PATH.is_file() else ""
    assert core_src, "core/cockpit_usability_checkpoint.py is missing"
    assert script_src, "scripts/create_cockpit_usability_checkpoint.py is missing"
    combined = core_src + "\n" + script_src
    for token in (
        "subprocess",
        "Popen",
        "os.system",
        "requests",
        "httpx",
        "urllib",
        "websocket",
        "OpenAI",
        "Gemini",
        "Anthropic",
        "generate_patch",
        "apply_patch",
        "patch_apply",
        "run_safe_validation",
        "validation_execution",
        "benchmark execution",
        "worker",
        "git push",
        "gh pr",
        "auto merge",
        "database write",
    ):
        assert token not in combined, f"Forbidden token found: {token!r}"
