"""Tests for UX.7 — Cockpit Navigation & Action Hierarchy Cleanup.

UX.7 reorganises the existing UI surfaces into one operator workflow.
It does not add new backend routes, mutation routes, or execution powers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_HTML   = PROJECT_ROOT / "web" / "templates" / "index.html"
_CSS    = PROJECT_ROOT / "web" / "static" / "style.css"
_REG    = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
_CORE   = PROJECT_ROOT / "core" / "cockpit_action_hierarchy.py"
_SCRIPT = PROJECT_ROOT / "scripts" / "create_cockpit_action_hierarchy_report.py"


def _html() -> str:
    return _HTML.read_text(encoding="utf-8")


def _css() -> str:
    return _CSS.read_text(encoding="utf-8")


# ── 1. Workbench/operator workflow structure exists ───────────────────────────

def test_cockpit_workbench_area_exists_in_html():
    html = _html()
    assert (
        "data-cockpit-area" in html
        or "ws-nav-advanced-drawer" in html
        or "cockpit-section" in html
    ), "HTML must have a cockpit/workbench area attribute or advanced-drawer class"


# ── 2. Goal Brief and 4W1H presented as one merged workflow area ──────────────

def test_4w1h_tab_removed_from_primary_nav():
    """ws-tab-goal-brief-4w1h should be removed as a separate nav tab (panel preserved)."""
    html = _html()
    # Goal Brief panel (ws-goal-brief-4w1h) must still exist — only the nav tab goes away
    assert 'ws-goal-brief-4w1h' in html, "UX.5 panel must still be in DOM"
    # The separate nav tab button should be removed (merged into Goal Brief / 4W1H)
    assert 'id="ws-tab-goal-brief-4w1h"' not in html, (
        "ws-tab-goal-brief-4w1h should be removed from nav (merged into Goal Brief / 4W1H)"
    )


def test_goal_brief_tab_includes_4w1h_label():
    """Goal Brief nav tab should be renamed to indicate 4W1H is merged in."""
    html = _html()
    assert "Goal Brief / 4W1H" in html or "4W1H" in html[:4000], (
        "Goal Brief tab label should include 4W1H reference"
    )


# ── 3. Run Timeline in workflow/cockpit area ──────────────────────────────────

def test_run_timeline_not_in_secondary_views_group():
    """Run Timeline should be in the workflow area, not the old secondary Views group."""
    html = _html()
    assert "ws-tab-run-timeline" in html, "Run Timeline tab must still exist"
    # After UX.7, it's in the workflow group (not secondary), so ws-nav--secondary
    # should NOT contain run-timeline
    secondary_start = html.find("ws-nav--secondary")
    secondary_end   = html.find("/ws-nav-secondary", secondary_start)
    if secondary_start == -1:
        return  # secondary group removed entirely — pass
    section = html[secondary_start:secondary_end] if secondary_end != -1 else html[secondary_start:secondary_start + 1500]
    assert 'data-ws="run-timeline"' not in section, (
        "Run Timeline must not be in ws-nav--secondary; it belongs in the Workflow area"
    )


# ── 4. Evidence Cards near output/review area ─────────────────────────────────

def test_evidence_cards_in_workflow_area():
    """Evidence Cards should be in the workflow/cockpit nav group, not secondary."""
    html = _html()
    assert "ws-tab-evidence-cards" in html
    secondary_start = html.find("ws-nav--secondary")
    secondary_end   = html.find("/ws-nav-secondary", secondary_start)
    if secondary_start == -1:
        return
    section = html[secondary_start:secondary_end] if secondary_end != -1 else html[secondary_start:secondary_start + 1500]
    assert 'data-ws="evidence-cards"' not in section, (
        "Evidence Cards must not be in ws-nav--secondary; it belongs in the Workflow area"
    )


# ── 5. Continue From Frame near history/context/workflow area ─────────────────

def test_continue_from_frame_in_workflow_area():
    """Continue From Frame should be in the workflow area, not old secondary."""
    html = _html()
    assert "ws-tab-continue-from-frame" in html
    secondary_start = html.find("ws-nav--secondary")
    secondary_end   = html.find("/ws-nav-secondary", secondary_start)
    if secondary_start == -1:
        return
    section = html[secondary_start:secondary_end] if secondary_end != -1 else html[secondary_start:secondary_start + 1500]
    assert 'data-ws="continue-from-frame"' not in section, (
        "Continue From Frame must not be in ws-nav--secondary; it belongs in the Workflow area"
    )


# ── 6. Mixed Mode Router not presented as a primary execution button ──────────

def test_mixed_mode_router_relabeled_as_mode_decision():
    """Mixed Mode Router tab should be relabeled 'Mode Decision' to clarify it is preview-only."""
    html = _html()
    assert "ws-tab-mixed-mode-router" in html, "Mixed Mode Router tab must still exist"
    # The button text should now read "Mode Decision"
    btn_idx = html.find('id="ws-tab-mixed-mode-router"')
    btn_text = html[btn_idx: btn_idx + 280]
    assert "Mode Decision" in btn_text, (
        "ws-tab-mixed-mode-router button label should read 'Mode Decision'"
    )


def test_mixed_mode_router_not_in_primary_nav():
    """Mixed Mode Router / Mode Decision must not be a primary-level button."""
    html = _html()
    primary_start = html.find("ws-nav--primary")
    if primary_start == -1:
        pytest.skip("ws-nav--primary not found")
    primary_end = html.find("/ws-nav-primary", primary_start)
    section = (
        html[primary_start:primary_end]
        if primary_end != -1
        else html[primary_start: primary_start + 1000]
    )
    assert "mixed-mode-router" not in section, (
        "Mixed Mode Router must not appear in ws-nav--primary"
    )


# ── 7. Advanced/debug surfaces grouped or collapsible ────────────────────────

def test_advanced_debug_drawer_exists():
    """An Advanced/Debug collapsible drawer must be present in the HTML."""
    html = _html()
    assert "ws-nav-advanced-drawer" in html or "advanced-debug" in html, (
        "HTML must have an Advanced/Debug drawer (ws-nav-advanced-drawer or advanced-debug)"
    )


def test_advanced_drawer_contains_benchmarks():
    """Benchmarks tab should be inside the advanced/debug drawer."""
    html = _html()
    drawer_start = html.find("ws-nav-advanced-drawer")
    if drawer_start == -1:
        drawer_start = html.find('data-ui-group="advanced-debug"')
    if drawer_start == -1:
        pytest.fail("No advanced drawer found")
    assert html.find('data-ws="benchmarks"', drawer_start) != -1, (
        "Benchmarks must be inside the advanced/debug drawer"
    )


def test_advanced_drawer_contains_dream():
    """Dream tab should be inside the advanced/debug drawer."""
    html = _html()
    drawer_start = html.find("ws-nav-advanced-drawer")
    if drawer_start == -1:
        drawer_start = html.find('data-ui-group="advanced-debug"')
    if drawer_start == -1:
        pytest.fail("No advanced drawer found")
    assert html.find('data-ws="dream"', drawer_start) != -1, (
        "Dream must be inside the advanced/debug drawer"
    )


def test_advanced_drawer_contains_graph():
    """Graph tab should be inside the advanced/debug drawer."""
    html = _html()
    drawer_start = html.find("ws-nav-advanced-drawer")
    if drawer_start == -1:
        drawer_start = html.find('data-ui-group="advanced-debug"')
    if drawer_start == -1:
        pytest.fail("No advanced drawer found")
    assert html.find('data-ws="graph"', drawer_start) != -1, (
        "Graph must be inside the advanced/debug drawer"
    )


# ── 8. Graph/Benchmarks/Dream do not dominate the daily workflow row ──────────

def test_benchmarks_not_in_primary_nav():
    html = _html()
    primary_start = html.find("ws-nav--primary")
    if primary_start == -1:
        pytest.skip("ws-nav--primary not found")
    primary_end = html.find("/ws-nav-primary", primary_start)
    section = (
        html[primary_start:primary_end]
        if primary_end != -1
        else html[primary_start: primary_start + 1000]
    )
    assert 'data-ws="benchmarks"' not in section, "Benchmarks must not be in ws-nav--primary"


def test_dream_not_in_primary_nav():
    html = _html()
    primary_start = html.find("ws-nav--primary")
    if primary_start == -1:
        pytest.skip("ws-nav--primary not found")
    primary_end = html.find("/ws-nav-primary", primary_start)
    section = (
        html[primary_start:primary_end]
        if primary_end != -1
        else html[primary_start: primary_start + 1000]
    )
    assert 'data-ws="dream"' not in section, "Dream must not be in ws-nav--primary"


def test_primary_nav_has_at_most_three_items():
    """Primary nav should have ≤3 items (Workbench, Memory, Settings)."""
    html = _html()
    primary_start = html.find("ws-nav--primary")
    if primary_start == -1:
        pytest.skip("ws-nav--primary not found")
    primary_end = html.find("/ws-nav-primary", primary_start)
    section = (
        html[primary_start:primary_end]
        if primary_end != -1
        else html[primary_start: primary_start + 1000]
    )
    count = section.count('data-ws="')
    assert count <= 3, f"Primary nav has {count} items, expected ≤3 (Workbench, Memory, Settings)"


# ── 9. Preview-only panels remain labeled preview-only/contract-only ──────────

def test_ux3_panel_labeled_contract_or_preview():
    html = _html()
    idx = html.find('id="ws-continue-from-frame"')
    assert idx != -1
    panel = html[idx: idx + 1000]
    assert "contract" in panel.lower() or "preview" in panel.lower() or "not implemented" in panel.lower()


def test_ux4_panel_labeled_preview():
    html = _html()
    idx = html.find('id="ws-mixed-mode-router"')
    assert idx != -1
    panel = html[idx: idx + 1000]
    assert "preview" in panel.lower() or "not implemented" in panel.lower()


def test_ux5_panel_labeled_preview():
    html = _html()
    idx = html.find('id="ws-goal-brief-4w1h"')
    assert idx != -1
    panel = html[idx: idx + 1000]
    assert "preview" in panel.lower() or "not implemented" in panel.lower()


def test_ux6_panel_labeled_preview():
    html = _html()
    idx = html.find('id="ws-evidence-cards"')
    assert idx != -1
    panel = html[idx: idx + 1000]
    assert "preview" in panel.lower() or "not implemented" in panel.lower()


# ── 10. No new POST route introduced ─────────────────────────────────────────

def test_no_new_post_route_in_core():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    src = _CORE.read_text(encoding="utf-8")
    assert "@app.route" not in src
    assert 'methods=["POST"]' not in src
    assert "methods=['POST']" not in src


# ── 11. No new mutation route introduced ──────────────────────────────────────

def test_no_new_mutation_route_in_script():
    if not _SCRIPT.exists():
        pytest.skip("script file not yet created")
    src = _SCRIPT.read_text(encoding="utf-8")
    assert "@app.route" not in src
    assert 'methods=["POST"]' not in src


# ── 12. Apply/review patch action remains human-triggered ────────────────────

def test_apply_patch_remains_human_triggered():
    html = _html()
    assert 'onclick="applyPatch()"' in html or "onclick='applyPatch()'" in html, (
        "applyPatch() must remain a human-triggered button"
    )


# ── 13. HTML has fewer competing top-level nav buttons or advanced drawer ─────

def test_html_has_advanced_drawer_reducing_visible_tabs():
    html = _html()
    has_drawer = "ws-nav-advanced-drawer" in html or "advanced-debug" in html
    assert has_drawer, (
        "HTML must have an advanced drawer to reduce visible competing tabs"
    )


# ── 14. CSS contains cockpit/workflow section styles ─────────────────────────

def test_css_has_cockpit_section_styles():
    css = _css()
    assert (
        "ws-nav-advanced-drawer" in css
        or "cockpit" in css.lower()
        or "ws-nav--workflow" in css
        or "ws-nav--advanced" in css
    ), "CSS must have cockpit/workflow section styles"


# ── 15. No backend execution behavior changed ─────────────────────────────────

def test_no_new_execution_in_core():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    src = _CORE.read_text(encoding="utf-8")
    bad = [
        "subprocess", "Popen", "os.system", "requests.", "httpx.",
        "urllib.request", "websocket", "generate_patch", "apply_patch(",
        "run_benchmarks(", "launch_worker(", "spawn_worker",
    ]
    for token in bad:
        assert token not in src, f"Forbidden execution token in core: {token!r}"


# ── 16. Registry contains UX.7 ───────────────────────────────────────────────

def test_registry_contains_ux7():
    data = json.loads(_REG.read_text(encoding="utf-8"))
    ids = [p["phase_id"] for p in data["phases"]]
    assert "UX.7" in ids


def test_registry_ux7_is_complete():
    data = json.loads(_REG.read_text(encoding="utf-8"))
    ux7 = next((p for p in data["phases"] if p["phase_id"] == "UX.7"), None)
    assert ux7 is not None, "UX.7 not found in registry"
    assert ux7["status"] == "complete"


# ── 17. Source files have no forbidden tokens ─────────────────────────────────

_FORBIDDEN = [
    "subprocess", "Popen", "os.system", "requests", "httpx",
    "urllib.request", "websocket", "anthropic", "openai", "gemini",
    "litellm", "generate_patch", "apply_patch(", "patch_apply",
    "run_safe_validation", "validation_execution", "run_benchmarks(",
    "apply_candidate_in_sandbox", "launch_worker(", "worker_launch(",
    "spawn_worker", "proposal_runner", "sqlite3", "psycopg", "pymongo",
    "INSERT INTO", "cursor(", "auto_merge(", "perform_merge", "merge_to_real",
]


def test_core_source_has_no_forbidden_tokens():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    src = _CORE.read_text(encoding="utf-8")
    for token in _FORBIDDEN:
        assert token not in src, f"Forbidden token in core: {token!r}"


def test_script_source_has_no_forbidden_tokens():
    if not _SCRIPT.exists():
        pytest.skip("script file not yet created")
    src = _SCRIPT.read_text(encoding="utf-8")
    for token in _FORBIDDEN:
        assert token not in src, f"Forbidden token in script: {token!r}"


# ── Core module tests (once implemented) ──────────────────────────────────────

def test_core_module_importable():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    from core.cockpit_action_hierarchy import build_cockpit_action_hierarchy_report
    assert callable(build_cockpit_action_hierarchy_report)


def test_build_report_returns_dict():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    from core.cockpit_action_hierarchy import build_cockpit_action_hierarchy_report
    report = build_cockpit_action_hierarchy_report(
        html_path=str(_HTML),
        css_path=str(_CSS),
        repo_path=".",
    )
    assert isinstance(report, dict)


def test_report_has_required_fields():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    from core.cockpit_action_hierarchy import build_cockpit_action_hierarchy_report
    report = build_cockpit_action_hierarchy_report(
        html_path=str(_HTML),
        css_path=str(_CSS),
        repo_path=".",
    )
    for key in ("primary_workflow", "advanced_debug_surfaces", "guardrails", "boundaries"):
        assert key in report, f"Missing required field: {key!r}"


def test_guardrails_are_safe():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    from core.cockpit_action_hierarchy import build_cockpit_action_hierarchy_report
    report = build_cockpit_action_hierarchy_report(
        html_path=str(_HTML),
        css_path=str(_CSS),
        repo_path=".",
    )
    g = report["guardrails"]
    assert g.get("preview_only") is True
    assert g.get("new_backend_route_added") is False
    assert g.get("new_mutation_route_added") is False
    assert g.get("execution_behavior_changed") is False


def test_primary_workflow_is_non_empty_list():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    from core.cockpit_action_hierarchy import build_cockpit_action_hierarchy_report
    report = build_cockpit_action_hierarchy_report(
        html_path=str(_HTML),
        css_path=str(_CSS),
        repo_path=".",
    )
    assert isinstance(report["primary_workflow"], list)
    assert len(report["primary_workflow"]) > 0


def test_advanced_debug_surfaces_is_list():
    if not _CORE.exists():
        pytest.skip("core file not yet created")
    from core.cockpit_action_hierarchy import build_cockpit_action_hierarchy_report
    report = build_cockpit_action_hierarchy_report(
        html_path=str(_HTML),
        css_path=str(_CSS),
        repo_path=".",
    )
    assert isinstance(report["advanced_debug_surfaces"], list)
    assert len(report["advanced_debug_surfaces"]) >= 3  # benchmarks, dream, graph


def test_script_cli_runs_demo():
    if not _SCRIPT.exists():
        pytest.skip("script file not yet created")
    from scripts.create_cockpit_action_hierarchy_report import run_create_cockpit_action_hierarchy_report
    result = run_create_cockpit_action_hierarchy_report(
        html_path=str(_HTML),
        css_path=str(_CSS),
        repo_path=".",
        demo=True,
    )
    assert result.get("ok") is True
    assert result.get("report") is not None
