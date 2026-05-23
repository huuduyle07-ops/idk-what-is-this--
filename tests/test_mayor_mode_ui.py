"""Template contract checks for Mayor Mode Sub-agent UI polish."""
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"


def test_subagent_ui_copy_and_dark_surface_hooks():
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")
    styles = STYLE_SHEET.read_text(encoding="utf-8")

    assert 'href="/mcp/audit?limit=10"' in template
    assert "View MCP audit" in template
    assert "MCP Inspector" in template
    assert "Inspect read-only MCP" in template
    assert "Inspect artifact-write MCP" in template
    assert '"/mcp/inspector/launch"' in template
    assert ">Copy command</button>" in template
    assert ">Run subagent in temp clone</button>" in template
    assert (
        "No worker runs yet. Run a handoff in a temp clone to create "
        ".agent/worker_runs/."
    ) in template

    assert 'class="handoff-item"' not in template
    assert 'class="handoff-item subagent-run-card"' in template
    assert 'class="worker-run-item subagent-run-card"' in template
    assert 'class="handoff-run-btn--warning-outline"' in template
    assert ".subagent-run-card" in styles
    assert ".handoff-run-btn--warning-outline" in styles


def test_handoff_buttons_use_handoff_id_not_path():
    """Copy command and Run subagent buttons must use handoff_id (filename),
    not the absolute h.path, to avoid Windows backslash JS-escape mangling."""
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")
    # Both action buttons must reference handoff_id
    assert "h.handoff_id" in template
    # Neither action button may embed the absolute path in its onclick
    import re
    onclick_pattern = re.compile(
        r"onclick=['\"]runHandoff\(['\"]?\$\{[^}]*h\.path[^}]*\}['\"]?",
    )
    assert not onclick_pattern.search(template), (
        "runHandoff onclick must not interpolate h.path — use h.handoff_id instead"
    )
    # The runHandoff JS function must submit handoff_id, not handoff_path
    assert 'fd.append("handoff_id"' in template
    assert 'fd.append("handoff_path"' not in template
