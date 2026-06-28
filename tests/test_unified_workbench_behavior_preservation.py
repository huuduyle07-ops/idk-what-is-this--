"""Tests for UX.11 - Unified Workbench Behavior Preservation Check.

UX.11 proves the UX.10 visual Workbench preserved existing behavior. It is
report-only: no routes, model calls, auto-dispatch, patch application, validation
runs, benchmark runs, network calls, or repo mutation powers are introduced.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path


_ROOT = Path(__file__).parent.parent
_HTML_PATH = _ROOT / "web" / "templates" / "index.html"
_REGISTRY_PATH = _ROOT / "docs" / "roadmap" / "phase_registry.json"
_CORE_PATH = _ROOT / "core" / "unified_workbench_behavior_preservation.py"
_SCRIPT_PATH = _ROOT / "scripts" / "create_unified_workbench_behavior_preservation_report.py"


def _html() -> str:
    return _HTML_PATH.read_text(encoding="utf-8")


def _workbench_block() -> str:
    html = _html()
    start = html.index("UX.10 unified-workbench")
    end = html.index("/UX.10 unified-workbench", start)
    return html[start:end]


def _route_source() -> str:
    parts = [(_ROOT / "web" / "app.py").read_text(encoding="utf-8")]
    for path in sorted((_ROOT / "web" / "routes").glob("*.py")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _core():
    spec = importlib.util.find_spec("core.unified_workbench_behavior_preservation")
    assert spec is not None, "UX.11 core report module is missing"
    return importlib.import_module("core.unified_workbench_behavior_preservation")


def _report() -> dict:
    return _core().build_unified_workbench_behavior_preservation_report(
        repo_path=str(_ROOT),
        report_id="test-report",
        created_at="2026-06-28T00:00:00+00:00",
    )


def test_existing_agent_form_wraps_the_workbench():
    html = _html()
    block = _workbench_block()
    assert '<form method="POST" class="agent-form" id="agentForm">' in html
    assert html.index('id="agentForm"') < html.index("UX.10 unified-workbench")
    assert html.index("/UX.10 unified-workbench") < html.index("</form>", html.index('id="agentForm"'))
    assert 'class="unified-workbench"' in block


def test_query_textarea_remains_the_real_main_intent_input():
    html = _html()
    block = _workbench_block()
    assert 'textarea name="query"' in html
    assert 'textarea name="query"' in block
    assert "What do you want C.A.T.T.U.S to do?" in block


def test_existing_submit_path_still_exists():
    block = _workbench_block()
    assert '<button type="submit" id="primarySubmit">Run</button>' in block
    assert "existing agent form" in block
    assert "No new route" in block


def test_chat_and_instant_controls_do_not_replace_submit_with_new_route():
    block = _workbench_block()
    assert 'onclick="setProductMode(\'chat\')"' in block
    assert 'onclick="setProductMode(\'instant\')"' in block
    assert "action=" not in block
    assert 'method="post"' not in block.lower()


def test_mode_preview_is_preview_only_and_has_no_fetch_trigger():
    block = _workbench_block()
    assert "Mode Preview" in block
    assert "Preview only." in block
    assert "does not auto-dispatch" in block
    assert "fetch(" not in block
    assert "onclick=" not in block[block.index("workbench-mode-preview"):block.index("workbench-confirmation-actions")]


def test_activation_helpers_are_help_only():
    block = _workbench_block()
    assert block.count('class="workbench-helper"') >= 5
    assert block.count(">?</summary>") >= 5
    assert block.count("Help only.") >= 5


def test_4w1h_helper_rows_do_not_introduce_submit_buttons():
    block = _workbench_block()
    brief = block[block.index('class="workbench-brief"'):block.index('class="workbench-mode-preview"')]
    assert "What are we changing?" in brief
    assert "Why are we changing it?" in brief
    assert "Where should C.A.T.T.U.S focus?" in brief
    assert "When should it stop?" in brief
    assert "How do we validate?" in brief
    assert 'type="submit"' not in brief
    assert "fetch(" not in brief


def test_goal_brief_builder_remains_reachable_from_workbench():
    block = _workbench_block()
    assert "Open Goal Brief / 4W1H Builder" in block
    assert "showWorkspaceTab('goal-brief')" in block
    assert "full builder still owns the existing Goal Brief workflow" in block


def test_apply_review_patch_remains_outside_workbench_and_human_triggered():
    html = _html()
    block = _workbench_block()
    assert "Apply / Review Patch" not in block
    assert html.index("Apply / Review Patch") > html.index("/UX.10 unified-workbench")
    assert '<button type="button" onclick="applyPatch()">Apply / Review Patch</button>' in html


def test_no_workbench_form_action_or_backend_post_route_was_added():
    html = _html()
    routes = _route_source().lower()
    assert html.count('method="POST"') == 1
    assert 'action="' not in _workbench_block()
    route_lines = [line.strip().lower() for line in routes.splitlines() if "@app.route" in line or "@bp.route" in line]
    assert not [line for line in route_lines if ("workbench" in line or "unified" in line) and "post" in line]


def test_no_new_workbench_mutation_route_was_added():
    routes = _route_source().lower()
    route_lines = [line.strip() for line in routes.splitlines() if "@app.route" in line or "@bp.route" in line]
    suspicious = [
        line for line in route_lines
        if ("workbench" in line or "unified" in line)
        and any(token in line for token in ("apply", "run", "execute", "mutate", "write"))
    ]
    assert suspicious == []


def test_no_auto_run_javascript_is_tied_to_mode_preview_chips():
    html = _html()
    chip_index = html.index('class="workbench-mode-chip"')
    script_tail = html[chip_index:]
    assert "querySelectorAll('.workbench-mode-chip'" not in script_tail
    assert 'querySelectorAll(".workbench-mode-chip"' not in script_tail
    assert "data-workbench-mode" in _workbench_block()
    js_index = html.index('document.querySelectorAll("[data-workbench-mode]")')
    js_segment = html[js_index:html.index("});", js_index) + 3]
    assert "workbench-mode-chip--active" in js_segment
    assert "fetch(" not in js_segment
    assert ".submit(" not in js_segment
    assert "dispatchEvent" not in js_segment


def test_advanced_debug_surfaces_remain_secondary():
    html = _html()
    assert 'class="ws-nav-advanced-drawer"' in html
    assert 'data-ui-group="advanced-debug"' in html
    assert html.index('data-ui-group="advanced-debug"') > html.index("/UX.10 unified-workbench")


def test_workbench_visual_integration_keeps_safety_labels_visible():
    block = _workbench_block()
    for phrase in (
        "Visual integration only",
        "existing behavior is preserved",
        "does not auto-dispatch",
        "Apply Patch remains separate",
        "human-triggered",
    ):
        assert phrase in block


def test_report_summarizes_behavior_preservation_as_pass():
    report = _report()
    assert report["report_kind"] == "unified_workbench_behavior_preservation"
    assert report["report_id"] == "test-report"
    assert report["created_at"] == "2026-06-28T00:00:00+00:00"
    assert report["status"] == "pass"
    assert report["recommended_next_phase"] == "UX.CLOSE - UX Branch Freeze Checkpoint"
    assert report["guardrails"]
    for section in (
        "preservation_checks",
        "route_safety_checks",
        "form_safety_checks",
        "workbench_safety_checks",
        "remaining_risks",
    ):
        assert section in report, section
    all_checks = (
        report["preservation_checks"]
        + report["route_safety_checks"]
        + report["form_safety_checks"]
        + report["workbench_safety_checks"]
    )
    assert len(all_checks) >= 18
    assert all(check["status"] == "pass" for check in all_checks)


def test_report_markdown_names_boundaries_and_next_phase():
    md = _core().render_unified_workbench_behavior_preservation_markdown(_report())
    assert "# Unified Workbench Behavior Preservation Check" in md
    assert "## Preservation Checks" in md
    assert "## Route Safety Checks" in md
    assert "## Guardrails" in md
    assert "UX.CLOSE - UX Branch Freeze Checkpoint" in md
    low = md.lower()
    assert "report-only" in low
    assert "does not add routes" in low
    assert "does not start runs automatically" in low
    assert "does not call models" in low


def test_report_writer_creates_optional_artifacts(tmp_path):
    result = _core().write_unified_workbench_behavior_preservation_artifacts(
        repo_path=str(_ROOT),
        output_root=str(tmp_path),
        report_id="writer-test",
        created_at="2026-06-28T00:00:00+00:00",
    )
    assert result["ok"] is True
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path.name == "unified_workbench_behavior_preservation_report.json"
    assert md_path.name == "unified_workbench_behavior_preservation_report.md"
    assert json_path.is_file()
    assert md_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["status"] == "pass"


def test_cli_prints_report_json(tmp_path, capsys):
    spec = importlib.util.find_spec("scripts.create_unified_workbench_behavior_preservation_report")
    assert spec is not None, "UX.11 report script is missing"
    script = importlib.import_module("scripts.create_unified_workbench_behavior_preservation_report")
    code = script.main([
        "--repo-path",
        str(_ROOT),
        "--output-root",
        str(tmp_path),
        "--report-id",
        "cli-test",
        "--created-at",
        "2026-06-28T00:00:00+00:00",
        "--json",
    ])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "cli-test"
    assert printed["status"] == "pass"


def test_registry_accepts_ux11():
    data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    ux11 = next((phase for phase in data["phases"] if phase["phase_id"] == "UX.11"), None)
    assert ux11 is not None
    assert ux11["track"] == "UX"
    assert ux11["status"] == "complete"
    assert ux11["prerequisites"] == ["UX.10"]
    assert ux11["automation_level"] == "LOCAL_0_OBSERVE"
    assert ux11["budget_tier"] == "local_only"
    assert ux11["risk_level"] == "low"
    assert ux11["network_allowed"] is False
    assert ux11["model_calls_allowed"] is False
    assert ux11["merge_allowed"] is False
    assert ux11["writes_real_repo"] is False
    assert ".agent/ux/unified_workbench_behavior_preservation/unified_workbench_behavior_preservation_report.json" in ux11["expected_artifacts"]


def test_phase_registry_seed_counts_include_ux11():
    data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    ids = {p["phase_id"] for p in data["phases"]}
    assert "UX.11" in ids
    assert len(data["phases"]) == 30
    assert sum(1 for p in data["phases"] if p["track"] == "UX") == 12


def test_new_ux11_core_script_files_are_safe():
    assert _CORE_PATH.is_file()
    assert _SCRIPT_PATH.is_file()
    combined = _CORE_PATH.read_text(encoding="utf-8") + "\n" + _SCRIPT_PATH.read_text(encoding="utf-8")
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
