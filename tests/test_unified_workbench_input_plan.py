"""Tests for UX.9 - Unified Workbench Input Plan.

UX.9 is a plan-only phase for merging Chat, Instant Run, and Goal Brief / 4W1H
into one conceptual Workbench input. It defines contracts and artifacts only:
no dispatch, execution, model calls, patches, checks, network calls, launched
agents, database writes, or merge powers are added.
"""
from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).parent.parent
_CORE_PATH = _ROOT / "core" / "unified_workbench_input_plan.py"
_SCRIPT_PATH = _ROOT / "scripts" / "create_unified_workbench_input_plan.py"
_REGISTRY_PATH = _ROOT / "docs" / "roadmap" / "phase_registry.json"
_TEMPLATE_PATH = _ROOT / "web" / "templates" / "index.html"


def _core():
    from core.unified_workbench_input_plan import (  # type: ignore
        build_activation_helper_contract,
        build_button_reduction_plan,
        build_confirmation_contract,
        build_field_schema,
        build_manual_review_questions,
        build_migration_plan,
        build_mode_preview_contract,
        build_ui_layout_plan,
        build_unified_input_definition,
        build_unified_workbench_input_plan,
        render_unified_workbench_input_markdown,
        write_unified_workbench_input_artifacts,
    )

    return {
        "build_activation_helper_contract": build_activation_helper_contract,
        "build_button_reduction_plan": build_button_reduction_plan,
        "build_confirmation_contract": build_confirmation_contract,
        "build_field_schema": build_field_schema,
        "build_manual_review_questions": build_manual_review_questions,
        "build_migration_plan": build_migration_plan,
        "build_mode_preview_contract": build_mode_preview_contract,
        "build_ui_layout_plan": build_ui_layout_plan,
        "build_unified_input_definition": build_unified_input_definition,
        "build_unified_workbench_input_plan": build_unified_workbench_input_plan,
        "render_unified_workbench_input_markdown": render_unified_workbench_input_markdown,
        "write_unified_workbench_input_artifacts": write_unified_workbench_input_artifacts,
    }


def _script():
    from scripts.create_unified_workbench_input_plan import (  # type: ignore
        main,
        run_create_unified_workbench_input_plan,
    )

    return run_create_unified_workbench_input_plan, main


def _build(**overrides) -> dict:
    return _core()["build_unified_workbench_input_plan"](
        repo_path=".",
        created_at="2026-06-27T00:00:00+00:00",
        plan_id="ux9-test",
        **overrides,
    )


def test_plan_status_is_reviewable():
    assert _build()["plan_status"] in {"ready_for_review", "needs_manual_review"}


def test_unified_input_definition_merges_chat_instant_and_goal_brief():
    definition = _core()["build_unified_input_definition"]()
    text = json.dumps(definition).lower()
    assert "chat" in text
    assert "instant run" in text
    assert "goal brief" in text
    assert "4w1h" in text
    assert definition["concept"] == "unified_workbench_input"


def test_field_schema_includes_main_intent_and_4w1h_fields():
    fields = {field["field_id"]: field for field in _core()["build_field_schema"]()}
    for field_id in (
        "main_intent_text",
        "what",
        "why",
        "where",
        "when_stop",
        "how_validate",
        "constraints",
        "non_goals",
        "risk_notes",
        "referenced_frame_id",
        "mode_preview",
        "confirmation_action",
    ):
        assert field_id in fields
    assert fields["main_intent_text"]["required"] is True
    assert fields["what"]["group"] == "4W1H"


def test_activation_helper_contract_defines_question_mark_as_help_only():
    helper = _core()["build_activation_helper_contract"]()
    assert helper["symbol"] == "?"
    assert helper["name"] == "Activation Helper"
    assert helper["help_only"] is True
    assert helper["executes_anything"] is False
    assert helper["calls_models"] is False
    assert helper["dispatches_run"] is False


def test_activation_helper_includes_examples_for_required_fields():
    examples = _core()["build_activation_helper_contract"]()["field_examples"]
    for field_id in ("what", "why", "where", "when_stop", "how_validate"):
        assert field_id in examples
        assert examples[field_id]["help_text"]
        assert examples[field_id]["example"]


def test_activation_helper_does_not_execute_or_dispatch():
    helper = _core()["build_activation_helper_contract"]()
    text = json.dumps(helper).lower()
    assert "not execute" in text
    assert "not call models" in text
    assert "not dispatch" in text
    assert helper["auto_fill_without_confirmation"] is False


def test_mode_preview_includes_all_six_ux4_modes():
    modes = _core()["build_mode_preview_contract"]()["modes"]
    assert [mode["mode_id"] for mode in modes] == [
        "chat",
        "instant_run",
        "continue_from_frame",
        "commander_plan",
        "clarify",
        "reject_or_defer",
    ]


def test_confirmation_contract_requires_human_before_execution_or_mutation():
    contract = _core()["build_confirmation_contract"]()
    assert contract["human_confirmation_required"] is True
    assert contract["automatic_confirmation"] is False
    text = json.dumps(contract).lower()
    for phrase in ("mutation", "run", "validation", "benchmark", "model", "push", "merge", "pr"):
        assert phrase in text


def test_confirmation_actions_include_expected_actions():
    actions = {item["action_id"] for item in _core()["build_confirmation_contract"]()["actions"]}
    assert {
        "ask_in_chat",
        "preview_instant_run",
        "open_continue_from_frame",
        "create_commander_contract",
    } <= actions


def test_button_reduction_plan_merges_chat_and_instant_entry():
    text = json.dumps(_core()["build_button_reduction_plan"]()).lower()
    assert "merge visible chat and instant run entry" in text


def test_button_reduction_plan_merges_goal_brief_and_4w1h():
    text = json.dumps(_core()["build_button_reduction_plan"]()).lower()
    assert "merge goal brief and 4w1h" in text


def test_button_reduction_plan_moves_router_into_mode_preview():
    text = json.dumps(_core()["build_button_reduction_plan"]()).lower()
    assert "mixed mode router" in text
    assert "mode preview" in text


def test_ui_layout_plan_includes_required_surfaces():
    text = json.dumps(_core()["build_ui_layout_plan"]()).lower()
    for phrase in (
        "unified input",
        "mode preview",
        "confirmation",
        "run timeline",
        "output review",
        "evidence cards",
        "advanced debug",
    ):
        assert phrase in text


def test_migration_plan_has_staged_rollout_and_preserves_old_behavior():
    stages = _core()["build_migration_plan"]()
    assert [stage["stage"] for stage in stages] == ["stage_1", "stage_2", "stage_3", "stage_4", "stage_5"]
    text = json.dumps(stages).lower()
    assert "keep old behavior" in text or "old flows are preserved" in text
    assert "no auto-dispatch" in text


def test_manual_review_questions_include_chat_instant_merge():
    questions = _core()["build_manual_review_questions"]()
    assert any("chat and instant run" in question.lower() for question in questions)


def test_markdown_contains_required_sections():
    md = _core()["render_unified_workbench_input_markdown"](_build())
    for section in (
        "Summary",
        "Unified Input Definition",
        "Field Schema",
        "Activation Helper Contract",
        "Mode Preview Contract",
        "Confirmation Contract",
        "Button Reduction Plan",
        "UI Layout Plan",
        "Migration Plan",
        "Manual Review Questions",
        "Next UX Steps",
        "Warnings",
        "Blockers",
        "Guardrails",
        "Boundaries",
    ):
        assert f"## {section}" in md


def test_markdown_contains_boundary_text():
    md = _core()["render_unified_workbench_input_markdown"](_build())
    for phrase in (
        "UX.9 is a plan-only unified input phase.",
        "UX.9 does not auto-dispatch.",
        "UX.9 does not merge execution paths yet.",
        "UX.9 does not start runs.",
        "UX.9 does not call models.",
        "UX.9 does not apply patches.",
        "UX.9 does not run validation.",
        "UX.9 does not run benchmarks.",
        "UX.9 does not contact network services.",
        "UX.9 does not launch workers.",
        "UX.9 does not push, merge, or open PRs.",
    ):
        assert phrase in md


def test_cli_writes_json_and_markdown(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        plan_id="cli-test",
        created_at="2026-06-27T00:00:00+00:00",
        demo=True,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["plan_id"] == "cli-test"


def test_cli_json_prints_summary_json(capsys, tmp_path):
    _, main = _script()
    code = main([
        "--repo-path", ".",
        "--output-root", str(tmp_path / "out"),
        "--plan-id", "json-test",
        "--created-at", "2026-06-27T00:00:00+00:00",
        "--demo",
        "--json",
    ])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["plan_id"] == "json-test"
    assert printed["recommended_next_phase"] == "UX.10 \u2014 Unified Workbench Input Visual Integration"


def test_demo_mode_uses_static_local_data_only(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        plan_id="demo-test",
        created_at="2026-06-27T00:00:00+00:00",
        demo=True,
    )
    report = result["report"]
    assert "demo_notes" in report
    assert report["guardrails"]["network_call_performed"] is False
    assert report["guardrails"]["model_call_performed"] is False


def test_guardrails_are_safe():
    guardrails = _build()["guardrails"]
    assert guardrails["plan_only"] is True
    for key in (
        "unified_input_execution_implemented",
        "auto_dispatch_implemented",
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


def test_optional_ui_placeholder_contains_unified_workbench_if_present():
    html = _TEMPLATE_PATH.read_text(encoding="utf-8")
    if "Unified Workbench" not in html:
        return
    assert "Plan-only unified input contract defined in UX.9" in html
    for label in ("Main input", "4W1H fields", "? helper", "Mode preview", "Confirmation action"):
        assert label in html


def test_optional_ui_placeholder_does_not_add_new_mutation_route():
    html = _TEMPLATE_PATH.read_text(encoding="utf-8")
    if "Unified Workbench" not in html:
        return
    start = html.index("UX.9 unified-workbench-placeholder")
    end = html.index("/UX.9 unified-workbench-placeholder", start)
    marker = html[start:end]
    assert 'method="post"' not in marker.lower()
    assert "fetch(" not in marker.lower()
    assert "XMLHttpRequest" not in marker


def test_registry_accepts_ux9():
    data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    ux9 = next((phase for phase in data["phases"] if phase["phase_id"] == "UX.9"), None)
    assert ux9 is not None
    assert ux9["status"] == "complete"
    assert ux9["track"] == "UX"
    assert ux9["prerequisites"] == ["UX.8"]
    assert ux9["automation_level"] == "LOCAL_0_OBSERVE"
    assert ux9["budget_tier"] == "local_only"
    assert ux9["risk_level"] == "low"
    assert ux9["network_allowed"] is False
    assert ux9["model_calls_allowed"] is False
    assert ux9["merge_allowed"] is False
    assert ux9["writes_real_repo"] is False
    assert ".agent/ux/unified_workbench_input_plan/unified_workbench_input_plan.json" in ux9["expected_artifacts"]


def test_source_contains_no_forbidden_behavior_tokens():
    core_src = _CORE_PATH.read_text(encoding="utf-8") if _CORE_PATH.is_file() else ""
    script_src = _SCRIPT_PATH.read_text(encoding="utf-8") if _SCRIPT_PATH.is_file() else ""
    assert core_src, "core/unified_workbench_input_plan.py is missing"
    assert script_src, "scripts/create_unified_workbench_input_plan.py is missing"
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
