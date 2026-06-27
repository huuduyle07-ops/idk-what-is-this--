"""Tests for UX.10 - Unified Workbench Input Visual Integration.

UX.10 is a visual/layout phase. It makes the Workbench input the visible center
of the cockpit without adding backend routes, auto-dispatch, or new mutation
behavior.
"""
from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).parent.parent
_HTML_PATH = _ROOT / "web" / "templates" / "index.html"
_CSS_PATH = _ROOT / "web" / "static" / "style.css"
_REGISTRY_PATH = _ROOT / "docs" / "roadmap" / "phase_registry.json"
_OPTIONAL_CORE = _ROOT / "core" / "unified_workbench_visual_integration.py"
_OPTIONAL_SCRIPT = _ROOT / "scripts" / "create_unified_workbench_visual_integration_report.py"


def _html() -> str:
    return _HTML_PATH.read_text(encoding="utf-8")


def _css() -> str:
    return _CSS_PATH.read_text(encoding="utf-8")


def _workbench_block() -> str:
    html = _html()
    start = html.index("UX.10 unified-workbench")
    end = html.index("/UX.10 unified-workbench", start)
    return html[start:end]


def test_unified_workbench_visual_area_exists_in_html():
    block = _workbench_block()
    assert "Unified Workbench" in block
    assert 'class="unified-workbench"' in block


def test_workbench_includes_main_intent_input_label():
    block = _workbench_block()
    assert "What do you want C.A.T.T.U.S to do?" in block
    assert 'textarea name="query"' in _html()


def test_workbench_includes_4w1h_fields():
    block = _workbench_block()
    for label in (
        "What are we changing?",
        "Why are we changing it?",
        "Where should C.A.T.T.U.S focus?",
        "When should it stop?",
        "How do we validate?",
    ):
        assert label in block


def test_workbench_includes_activation_helpers():
    block = _workbench_block()
    assert block.count('class="workbench-helper"') >= 5
    assert block.count(">?</summary>") >= 5


def test_each_activation_helper_includes_example_help_text():
    block = _workbench_block()
    for phrase in (
        "Describe the specific change or question.",
        "Example: Move Run Timeline closer to the Run action.",
        "Explain why this matters.",
        "Example: The current layout makes progress hard to see.",
        "Name a file, UI area, route, workflow, or artifact.",
        "Example: web/templates/index.html, Workbench header.",
        "Define the stopping boundary.",
        "Example: Stop after visual integration; do not change execution paths.",
        "Say how success should be checked.",
        "Example: targeted UI tests, registry validation, full pytest, manual screenshot review.",
        "Help only.",
    ):
        assert phrase in block


def test_mode_preview_area_exists():
    block = _workbench_block()
    assert "Mode Preview" in block
    assert 'class="workbench-mode-preview"' in block


def test_mode_preview_includes_expected_modes():
    block = _workbench_block()
    for label in ("Chat", "Instant Run", "Continue", "Commander", "Clarify"):
        assert label in block


def test_mode_preview_is_labeled_preview_only_and_no_auto_dispatch():
    block = _workbench_block()
    assert "Preview only." in block
    assert "requires confirmation" in block
    assert "does not auto-dispatch" in block


def test_confirmation_actions_area_exists():
    block = _workbench_block()
    assert "Confirmation Actions" in block
    assert 'class="workbench-confirmation-actions"' in block


def test_confirmation_actions_include_expected_actions():
    block = _workbench_block()
    for label in ("Ask", "Preview Run", "Continue From Frame", "Commander Plan"):
        assert label in block


def test_workbench_visually_merges_chat_and_instant_run_entry_concept():
    block = _workbench_block()
    assert "one input for Chat and Instant Run" in block
    assert "Current mode" in block


def test_goal_brief_and_4w1h_are_not_duplicated_as_competing_primary_areas():
    html = _html()
    primary_start = html.index('class="ws-nav ws-nav--primary"')
    primary_end = html.index("</div>", primary_start)
    primary_block = html[primary_start:primary_end]
    assert "ws-tab-goal-brief" not in primary_block


def test_dangerous_mutating_actions_remain_separate_from_workbench_input():
    html = _html()
    block = _workbench_block()
    assert "Apply / Review Patch" not in block
    assert html.index("Apply / Review Patch") > html.index("/UX.10 unified-workbench")


def test_no_new_post_route_is_introduced():
    html = _html()
    assert html.count('method="POST"') == 1
    block = _workbench_block().lower()
    assert 'method="post"' not in block


def test_no_new_mutation_route_is_introduced():
    block = _workbench_block().lower()
    for token in ("url_for('", "action=", "method=\"post\""):
        assert token not in block


def test_no_new_fetch_auto_run_behavior_is_introduced():
    block = _workbench_block()
    assert "fetch(" not in block
    assert "DOMContentLoaded" not in block
    assert "setInterval(" not in block


def test_existing_apply_patch_remains_human_triggered():
    html = _html()
    assert 'onclick="applyPatch()"' in html
    assert "Apply / Review Patch" in html


def test_css_includes_workbench_layout_classes():
    css = _css()
    for selector in (
        ".unified-workbench",
        ".workbench-main-intent",
        ".workbench-brief-grid",
        ".workbench-mode-preview",
        ".workbench-confirmation-actions",
        ".workbench-safety-note",
    ):
        assert selector in css


def test_registry_accepts_ux10():
    data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    ux10 = next((phase for phase in data["phases"] if phase["phase_id"] == "UX.10"), None)
    assert ux10 is not None
    assert ux10["track"] == "UX"
    assert ux10["status"] == "complete"
    assert ux10["prerequisites"] == ["UX.9"]
    assert ux10["automation_level"] == "LOCAL_0_OBSERVE"
    assert ux10["budget_tier"] == "local_only"
    assert ux10["network_allowed"] is False
    assert ux10["model_calls_allowed"] is False
    assert ux10["merge_allowed"] is False
    assert ux10["writes_real_repo"] is False


def test_optional_new_ux10_core_script_files_are_safe_if_present():
    parts = []
    for path in (_OPTIONAL_CORE, _OPTIONAL_SCRIPT):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    if not parts:
        return
    combined = "\n".join(parts)
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
