"""Phase UI.2 - Command Hierarchy / Progressive Disclosure contract tests.

These pin the *re-layering* introduced by Phase UI.2 on top of the UI.1
information-architecture freeze. Like the freeze tests, this module parses
``index.html`` / ``style.css`` as text and imports nothing heavy.

**UI.2a - Memory segmentation** (this file's current scope):

  * A segmented sub-nav (``data-ui-group="memory-nav"``) switches between the
    Lessons / Proposals / Handoffs / Worker Runs sections via
    ``showMemorySection()`` - they no longer all stack at once.
  * Each section is tagged ``data-memory-section`` (JS toggle) and wrapped with
    a ``data-ui-group="memory-*"`` + ``<!-- /memory-* -->`` contract anchor.
  * Duplicate hints stay *inside* the Lessons segment (not a standalone block).
  * The Lessons metadata filters (kind / language / source / category +
    archived / superseded toggles) are demoted behind a "More filters"
    disclosure (``data-ui-group="lessons-more-filters"``); the primary status
    filter buttons stay visible.

The reorg is **additive**: every existing ``id`` / ``onclick`` / label survives
(the UI.1 freeze and the lesson-merge contracts stay green). Later UI.2 phases
(2b result inspector, 2c inspector drawer, 2d primary-action cleanup) will add
their own sections to this file.
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"
THIS_FILE = Path(__file__)


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _styles() -> str:
    return STYLE_SHEET.read_text(encoding="utf-8")


def _group_segment(template: str, group: str) -> str:
    """Slice the template between ``data-ui-group="<group>"`` and ``<!-- /group -->``.

    Same convention as the UI.1 freeze test: lets us assert a control lives
    *inside* a collapsible/segment without parsing nested HTML.
    """
    start_marker = f'data-ui-group="{group}"'
    end_marker = f"<!-- /{group} -->"
    start = template.index(start_marker)
    end = template.index(end_marker, start)
    return template[start:end]


# ---------------------------------------------------------------------------
# 1 - Segmented Memory sub-nav exists and routes to all four sections
# ---------------------------------------------------------------------------
def test_memory_segmented_nav_exists():
    t = _template()
    assert 'data-ui-group="memory-nav"' in t
    assert "<!-- /memory-nav -->" in t
    assert "function showMemorySection(" in t

    nav = _group_segment(t, "memory-nav")
    for key in ("lessons", "proposals", "handoffs", "worker-runs"):
        assert f"showMemorySection('{key}')" in nav, f"nav missing the {key} tab"


# ---------------------------------------------------------------------------
# 2 - Each section is tagged as a toggneable segment; existing ids preserved
# ---------------------------------------------------------------------------
def test_memory_sections_tagged_as_segments():
    t = _template()
    for key in ("lessons", "proposals", "handoffs", "worker-runs"):
        assert f'data-memory-section="{key}"' in t, f"missing segment marker {key}"

    # Regression: the section render targets keep their ids/handlers.
    assert 'id="proposalsList"' in t
    assert 'id="handoffsList"' in t
    assert 'id="workerRunsList"' in t
    assert 'id="lessonsList"' in t
    assert "consolidateMemory()" in t  # consolidator stays reachable (utility)


# ---------------------------------------------------------------------------
# 3 - Duplicate hints live INSIDE the Lessons segment (not standalone)
# ---------------------------------------------------------------------------
def test_duplicate_hints_inside_lessons_segment():
    t = _template()
    lessons = _group_segment(t, "memory-lessons")
    assert 'id="duplicateHintsPanel"' in lessons

    for other in ("memory-proposals", "memory-handoffs", "memory-workerruns"):
        assert 'id="duplicateHintsPanel"' not in _group_segment(t, other), (
            f"duplicate hints leaked into {other}"
        )


# ---------------------------------------------------------------------------
# 4 - Lessons metadata filters demoted behind a "More filters" disclosure
# ---------------------------------------------------------------------------
def test_lessons_metadata_filters_behind_more_filters():
    t = _template()
    assert 'data-ui-group="lessons-more-filters"' in t
    assert "<!-- /lessons-more-filters -->" in t

    more = _group_segment(t, "lessons-more-filters")
    for fid in (
        "lessonFilterKind",
        "lessonFilterLanguage",
        "lessonFilterSource",
        "lessonFilterCategory",
        "showArchivedLessons",
        "showSupersededLessons",
    ):
        assert f'id="{fid}"' in more, f"{fid} should be inside More filters"


# ---------------------------------------------------------------------------
# 5 - Primary status filters + Merge stay visible (NOT in More filters)
# ---------------------------------------------------------------------------
def test_primary_lesson_controls_stay_visible():
    t = _template()
    more = _group_segment(t, "lessons-more-filters")
    for handler in (
        "filterLessons('')",
        "filterLessons('candidate')",
        "filterLessons('active')",
        "filterLessons('blocked')",
    ):
        assert handler in t, f"{handler} status button missing"
        assert handler not in more, f"{handler} must stay visible, not in More filters"

    assert 'id="mergeSelectToggle"' in t  # Merge button preserved + visible


# ---------------------------------------------------------------------------
# 6 - Convention: every new memory group has a matching end sentinel
# ---------------------------------------------------------------------------
def test_new_memory_groups_have_sentinels():
    t = _template()
    for group in (
        "memory-nav",
        "memory-lessons",
        "memory-proposals",
        "memory-handoffs",
        "memory-workerruns",
        "lessons-more-filters",
    ):
        assert f'data-ui-group="{group}"' in t, f"missing group {group}"
        assert f"<!-- /{group} -->" in t, f"missing sentinel for {group}"


# ---------------------------------------------------------------------------
# 7 - Segment styling present; Lessons is the default-active segment
# ---------------------------------------------------------------------------
def test_memory_segment_css_and_default():
    t = _template()
    assert "data-memory-section" in _styles(), "segment show/hide CSS rule missing"
    # Lessons is the default-active segment (renders before any JS runs)...
    assert "lessons-section is-active" in t, "Lessons section must be default-active"
    # ...and the Lessons nav tab is the default-active tab.
    assert 'memory-nav__tab--active" data-memory-nav="lessons"' in t, (
        "Lessons nav tab must be default-active"
    )


# ---------------------------------------------------------------------------
# 8 - Additive only: no new backend/privileged tokens, script count unchanged
# ---------------------------------------------------------------------------
def test_no_backend_change_in_memory_segmentation():
    t = _template()
    for token in ("os.system", "child_process", "eval(", "new Function(", "document.write("):
        assert token not in t, f"unexpected privileged token: {token!r}"
    assert t.count("<script src=") == 2  # mermaid CDN + keybindings.js only


# ---------------------------------------------------------------------------
# 9 - AST self-guard: this audit imports nothing heavy / privileged
# ---------------------------------------------------------------------------
def test_audit_module_has_no_forbidden_imports():
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    allowed_top = {"ast", "pathlib", "__future__"}
    for imp in imported:
        assert imp.split(".")[0] in allowed_top, f"unexpected import: {imp}"


# ===========================================================================
# UI.2b - Chat/Patch Result Inspector
#
#   * Answer + Patch stay primary (visible) in the result-tab row.
#   * The six secondary result tabs (Context / State / Validation / Cost /
#     Diff / Candidates) are demoted behind a collapsed "Run details"
#     disclosure (``data-ui-group="chat-run-details"``).
#   * ``showTab(id)`` is unchanged except for one additive behavior: when the
#     target tab lives inside Run details, it opens the disclosure first so the
#     active tab button is reachable.
#   * All eight result-pane ids survive; the UI.1 ``chat-more-actions`` anchor
#     and the script-tag count are untouched (strict additive).
# ===========================================================================
SECONDARY_RESULT_TABS = ("context", "state", "validation", "usage", "diff", "candidates")
ALL_RESULT_PANES = ("answer", "context", "state", "patch", "validation", "usage", "diff", "candidates")


def _showtab_body(template: str) -> str:
    """Slice the ``showTab`` function body (up to ``showWorkspaceTab``)."""
    start = template.index("function showTab(")
    end = template.index("function showWorkspaceTab(", start)
    return template[start:end]


# ---------------------------------------------------------------------------
# 10 - Run details disclosure exists with a matching end sentinel
# ---------------------------------------------------------------------------
def test_run_details_group_exists():
    t = _template()
    assert 'data-ui-group="chat-run-details"' in t
    assert "<!-- /chat-run-details -->" in t
    seg = _group_segment(t, "chat-run-details")
    assert "<summary" in seg and "Run details" in seg, "Run details summary missing"


# ---------------------------------------------------------------------------
# 11 - Answer + Patch stay primary: their tab buttons are OUTSIDE/before the
#      Run details disclosure
# ---------------------------------------------------------------------------
def test_primary_result_tabs_outside_run_details():
    t = _template()
    group_at = t.index('data-ui-group="chat-run-details"')
    for key in ("answer", "patch"):
        first = t.index(f"showTab('{key}')")
        assert first < group_at, f"{key} tab must stay primary (before Run details)"

    seg = _group_segment(t, "chat-run-details")
    assert "showTab('answer')" not in seg, "Answer must not be hidden in Run details"
    assert "showTab('patch')" not in seg, "Patch must not be hidden in Run details"


# ---------------------------------------------------------------------------
# 12 - The six secondary result tabs live INSIDE the Run details disclosure
# ---------------------------------------------------------------------------
def test_secondary_result_tabs_inside_run_details():
    t = _template()
    seg = _group_segment(t, "chat-run-details")
    for key in SECONDARY_RESULT_TABS:
        assert f"showTab('{key}')" in seg, f"{key} tab should be inside Run details"


# ---------------------------------------------------------------------------
# 13 - All eight result panes still exist (render targets untouched)
# ---------------------------------------------------------------------------
def test_all_result_panes_preserved():
    t = _template()
    for pane in ALL_RESULT_PANES:
        assert f'id="{pane}"' in t, f"result pane id={pane!r} missing"


# ---------------------------------------------------------------------------
# 14 - showTab() preserved and additively opens Run details for secondary tabs
# ---------------------------------------------------------------------------
def test_showtab_opens_run_details_disclosure():
    t = _template()
    assert "function showTab(" in t, "showTab() must be preserved"
    body = _showtab_body(t)
    assert "chat-run-details" in body, "showTab must target the Run details group"
    assert ".open = true" in body or ".open=true" in body, (
        "showTab must open the Run details disclosure for secondary tabs"
    )
    # The auto-open keys cover exactly the six demoted tabs.
    for key in SECONDARY_RESULT_TABS:
        assert f'"{key}"' in body, f"showTab auto-open list missing {key!r}"


# ---------------------------------------------------------------------------
# 15 - Existing UI.1 "More actions" anchor + sentinel survive untouched
# ---------------------------------------------------------------------------
def test_chat_more_actions_anchor_preserved():
    t = _template()
    assert 'data-ui-group="chat-more-actions"' in t
    assert "<!-- /chat-more-actions -->" in t
    # Primary patch flow stays put.
    assert "generatePatch()" in t
    assert "applyPatch()" in t


# ---------------------------------------------------------------------------
# 16 - Additive only: no new backend/privileged tokens; script count unchanged
# ---------------------------------------------------------------------------
def test_no_backend_change_in_run_inspector():
    t = _template()
    for token in ("os.system", "child_process", "eval(", "new Function(", "document.write("):
        assert token not in t, f"unexpected privileged token: {token!r}"
    assert t.count("<script src=") == 2  # mermaid CDN + keybindings.js only


# ===========================================================================
# UI.2c - Right-side Inspector / Debug Drawer
#
#   * A right-side drawer (id="inspectorDrawer", data-ui-group="inspector-drawer")
#     is the single home for debug/evidence/inspection LAUNCHERS. Collapsed by
#     default; toggled by a visible Inspector button (id="inspectorToggle") and
#     by Ctrl-J. All surfaces reuse existing handlers - no new routes, no
#     duplicate render targets.
#   * Four tagged sections: inspector-graph (viewGraph('debug') / Scope Spread),
#     inspector-replay (loadReplays launcher), inspector-raw (jump to existing
#     raw <details>), inspector-tools (launchMcpInspector + Tool Registry / MCP
#     Audit launchers).
#   * Dangerous controls (.env / compose apply, deletes, block, Dream apply)
#     NEVER live in the drawer; freeze-pinned Tool Registry / MCP Audit DOM and
#     the harness apply controls stay physically in Settings.
# ===========================================================================
INSPECTOR_SECTIONS = ("inspector-graph", "inspector-replay", "inspector-raw", "inspector-tools")
DANGEROUS_TOKENS = (
    "harnessEnvApply",
    "harnessComposeApply",
    "applyEnvFiles",
    "applyComposePatch",
    "applyDream",
    "blockLessonById",
    "deleteLesson",
    "deleteBenchmark",
)


# ---------------------------------------------------------------------------
# 17 - Drawer shell exists: group anchor + sentinel + toggle + function
# ---------------------------------------------------------------------------
def test_inspector_drawer_shell_exists():
    t = _template()
    assert 'data-ui-group="inspector-drawer"' in t
    assert "<!-- /inspector-drawer -->" in t
    assert 'id="inspectorDrawer"' in t
    assert 'id="inspectorToggle"' in t
    assert "function toggleInspector" in t


# ---------------------------------------------------------------------------
# 18 - Drawer is collapsed/closed by default
# ---------------------------------------------------------------------------
def test_inspector_drawer_default_collapsed():
    t = _template()
    drawer = _group_segment(t, "inspector-drawer")
    # The <aside> carries the group anchor; hidden + aria-hidden mark it closed.
    assert "hidden" in drawer, "drawer must be hidden by default"
    assert 'aria-hidden="true"' in drawer, "drawer must be aria-hidden by default"
    # The visible toggle reports the collapsed state.
    assert 'aria-expanded="false"' in t, "inspector toggle must start collapsed"


# ---------------------------------------------------------------------------
# 19 - Ctrl-J toggles the drawer (inline keybinding, no new external script)
# ---------------------------------------------------------------------------
def test_inspector_ctrl_j_keybinding():
    t = _template()
    assert "Ctrl-J" in t, "Ctrl-J intent comment/label missing"
    idx = t.index("Ctrl-J (or Cmd-J)")
    region = t[idx:idx + 560]
    assert "toggleInspector()" in region, "Ctrl-J must call toggleInspector()"
    assert '"j"' in region, "Ctrl-J handler must match the 'j' key"
    assert "ctrlKey" in region and "metaKey" in region, "must gate on Ctrl/Cmd"


# ---------------------------------------------------------------------------
# 20 - All four inspector sections exist, tagged + sentinelled, inside drawer
# ---------------------------------------------------------------------------
def test_inspector_sections_have_sentinels():
    t = _template()
    drawer = _group_segment(t, "inspector-drawer")
    for group in INSPECTOR_SECTIONS:
        assert f'data-ui-group="{group}"' in t, f"missing group {group}"
        assert f"<!-- /{group} -->" in t, f"missing sentinel for {group}"
        assert f'data-ui-group="{group}"' in drawer, f"{group} must live inside the drawer"


# ---------------------------------------------------------------------------
# 21 - Graph section reuses existing debug handlers (no duplicate canvas)
# ---------------------------------------------------------------------------
def test_inspector_graph_reuses_handlers():
    t = _template()
    drawer = _group_segment(t, "inspector-drawer")
    assert "viewGraph('debug')" in drawer, "Debug Graph launcher missing"
    assert "explainEvidenceSpread('graph')" in drawer, "Scope Spread launcher missing"
    # No second graph canvas is introduced; the drawer only launches.
    assert 'id="graphCanvas"' not in drawer, "drawer must not duplicate the graph canvas"


# ---------------------------------------------------------------------------
# 22 - Replay section reuses loadReplays (launcher into Settings)
# ---------------------------------------------------------------------------
def test_inspector_replay_reuses_handler():
    t = _template()
    replay = _group_segment(t, "inspector-replay")
    assert "loadReplays" in replay, "replay launcher must reuse loadReplays"
    # The real replay list lives in Settings - not duplicated in the drawer.
    assert 'id="replayList"' not in replay, "replayList must not be duplicated"


# ---------------------------------------------------------------------------
# 23 - Raw section jumps to existing raw panels (no duplicate ids)
# ---------------------------------------------------------------------------
def test_inspector_raw_jumps_to_existing_panels():
    t = _template()
    raw = _group_segment(t, "inspector-raw")
    assert "patchRawJson" in raw, "raw section should reach the patch raw JSON"
    assert "localCritiqueThought" in raw, "raw section should reach local critique raw"
    # Jump-only: the actual panes keep their single id elsewhere.
    assert 'id="patchRawJson"' not in raw, "patch raw pane id must not be duplicated"
    assert 'id="localCritiqueThought"' not in raw, "critique raw id must not be duplicated"


# ---------------------------------------------------------------------------
# 24 - Tools section: MCP Inspector launcher + Tool Registry / MCP Audit jumps
# ---------------------------------------------------------------------------
def test_inspector_tools_launchers():
    t = _template()
    tools = _group_segment(t, "inspector-tools")
    assert "launchMcpInspector" in tools, "MCP Inspector launcher missing"
    assert "toolRegistryList" in tools, "Tool Registry launcher missing"
    assert "mcpAuditList" in tools, "MCP Audit launcher missing"


# ---------------------------------------------------------------------------
# 25 - Freeze-pinned debug DOM stays physically in Settings (settings-debug)
# ---------------------------------------------------------------------------
def test_tool_registry_and_mcp_audit_stay_in_settings():
    t = _template()
    debug = _group_segment(t, "settings-debug")
    assert 'id="toolRegistryList"' in debug, "toolRegistryList must stay in settings-debug"
    assert 'id="mcpAuditList"' in debug, "mcpAuditList must stay in settings-debug"


# ---------------------------------------------------------------------------
# 26 - Harness apply controls stay in Settings (settings-harness), not in drawer
# ---------------------------------------------------------------------------
def test_harness_apply_stays_in_settings_harness():
    t = _template()
    harness = _group_segment(t, "settings-harness")
    assert 'id="harnessEnvApply"' in harness, "harnessEnvApply must stay in settings-harness"
    assert 'id="harnessComposeApply"' in harness, "harnessComposeApply must stay in settings-harness"


# ---------------------------------------------------------------------------
# 27 - Dangerous controls never appear inside the Inspector drawer
# ---------------------------------------------------------------------------
def test_dangerous_controls_not_in_inspector_drawer():
    t = _template()
    drawer = _group_segment(t, "inspector-drawer")
    for token in DANGEROUS_TOKENS:
        assert token not in drawer, f"dangerous control {token!r} must not be in the drawer"


# ---------------------------------------------------------------------------
# 28 - Additive only: no new external script; no privileged tokens
# ---------------------------------------------------------------------------
def test_no_backend_change_in_inspector_drawer():
    t = _template()
    for token in ("os.system", "child_process", "eval(", "new Function(", "document.write("):
        assert token not in t, f"unexpected privileged token: {token!r}"
    assert t.count("<script src=") == 2  # mermaid CDN + keybindings.js only
