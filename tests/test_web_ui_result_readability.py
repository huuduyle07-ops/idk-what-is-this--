"""UI-Cutoff.1c result/report readability contracts."""
from __future__ import annotations

import ast
from pathlib import Path

from web import app as web_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"
DEMO_DOC = PROJECT_ROOT / "docs" / "demo_flow.md"
THIS_FILE = Path(__file__)

RESULT_PANES = ("answer", "patch", "context", "state", "validation", "usage", "diff", "candidates")


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _styles() -> str:
    return STYLE_SHEET.read_text(encoding="utf-8")


def _group_segment(template: str, group: str) -> str:
    start_marker = f'data-ui-group="{group}"'
    end_marker = f"<!-- /{group} -->"
    start = template.index(start_marker)
    end = template.index(end_marker, start)
    return template[start:end]


def _css_block(styles: str, selector: str) -> str:
    start = styles.index(f"\n{selector} {{")
    return styles[start : styles.index("}", start)]


def test_root_route_still_renders():
    with web_app.app.test_client() as client:
        resp = client.get("/")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="answer"' in html
    assert 'id="patchRawJson"' in html
    assert 'id="benchDetail"' in html


def test_result_pane_ids_and_tab_references_are_preserved():
    t = _template()

    for pane in RESULT_PANES:
        assert f'id="{pane}"' in t, f"missing result pane id {pane!r}"
        assert f"showTab('{pane}')" in t, f"missing result tab handler for {pane!r}"

    assert 'id="patchRawJson"' in t
    assert "function showTab(" in t
    assert "function showWorkspaceTab(" in t


def test_readability_css_contracts_exist():
    styles = _styles()

    for selector in (
        ".report-card",
        ".report-card__heading",
        ".report-prose",
        ".report-table-scroll",
        ".report-status--success",
        ".report-status--warning",
        ".report-status--error",
        ".report-status--muted",
        ".report-status--raw",
        ".result-panel",
        ".raw-output",
        ".diff-output",
        ".patch-output",
        ".markdown-report",
        ".empty-state",
    ):
        assert selector in styles, f"missing result readability selector {selector!r}"


def test_pre_code_diff_and_raw_output_have_stable_overflow_rules():
    styles = _styles()

    for selector in ("pre, code", ".raw-output", ".diff-output", ".patch-output", ".patch-raw"):
        block = _css_block(styles, selector)
        assert "max-width" in block or selector == "pre, code"
        assert "overflow" in block

    diff = _css_block(styles, ".diff-output")
    assert "white-space: pre" in diff
    assert "font-family: var(--font-mono)" in diff


def test_report_tables_are_readable_and_scrollable():
    styles = _styles()

    table_region = styles[styles.index(".report-table-scroll") : styles.index(".report-status--success")]
    assert "overflow-x: auto" in table_region
    assert "min-width: 100%" in table_region
    assert "position: sticky" in table_region
    assert "padding:" in table_region


def test_presentation_evidence_markdown_keeps_light_contrast_after_cutoff_layer():
    styles = _styles()
    cutoff = styles.index("UI-Cutoff.1c: result/report readability pass")
    after_cutoff = styles[cutoff:]

    assert "Presentation evidence Markdown contrast guard" in after_cutoff
    guard = after_cutoff[after_cutoff.index("Presentation evidence Markdown contrast guard") :]
    assert ".evidence-viewer" in guard
    assert "background: #ffffff" in guard
    assert "color: #1f2328" in guard
    assert ".evidence-markdown" in guard


def test_no_dangerous_actions_became_primary():
    t = _template()
    primary_actions = t[
        t.index('class="actions actions--primary"') : t.index(
            'data-ui-group="chat-more-actions"'
        )
    ]
    primary_nav = _group_segment(t, "ws-nav-primary")

    for token in (
        "applyDream",
        "applyEnvFiles",
        "applyComposePatch",
        "blockLessonById",
        "_deleteBenchmark",
        "promoteProposalToLesson",
    ):
        assert token not in primary_actions
        assert token not in primary_nav


def test_demo_flow_documents_presentation_flow():
    doc = DEMO_DOC.read_text(encoding="utf-8")

    for phrase in (
        "UI-Cutoff.1c presentation flow",
        "open app",
        "choose repo",
        "enter query",
        "show Answer",
        "show Patch",
        "open Run details only if needed",
        "show Benchmarks/Evidence briefly",
        "tomorrow's demo checklist",
    ):
        assert phrase in doc


def test_template_has_no_new_privileged_or_external_script_behavior():
    t = _template()
    for token in ("os.system", "child_process", "eval(", "new Function(", "document.write("):
        assert token not in t, f"unexpected privileged token in template: {token!r}"
    assert t.count("<script src=") == 6  # two local SEC.UI.1 security assets, the AUTH.WEB.1 request-integrity owner and the UX.STATE.1 workflow-state owner
    assert t.count('src="http') == 1


def test_audit_module_has_no_forbidden_imports():
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    allowed_top = {"ast", "pathlib", "__future__", "web"}
    for imp in imported:
        assert imp.split(".")[0] in allowed_top, f"unexpected import: {imp}"
