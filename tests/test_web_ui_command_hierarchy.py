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
