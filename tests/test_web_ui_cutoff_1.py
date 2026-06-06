"""UI-Cutoff.1 visual/workflow cleanup contracts.

These tests pin the cutoff boundary: visual/workflow cleanup only, preserved
DOM contracts, collapsed advanced/debug/dangerous surfaces by default, and a
visible Chat/Patch happy path.
"""
from __future__ import annotations

import ast
from pathlib import Path

from web import app as web_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"
IA_DOC = PROJECT_ROOT / "docs" / "web_ui_information_architecture.md"
DEMO_DOC = PROJECT_ROOT / "docs" / "demo_flow.md"
THIS_FILE = Path(__file__)


PRESERVED_IDS = (
    "repoPathInput",
    "primarySubmit",
    "webModeInput",
    "modeSelect",
    "agentModeSelect",
    "patchStyleSelect",
    "runtimeEnvironmentSelect",
    "runtimeEnvironmentCustomFields",
    "applyPolicy",
    "answer",
    "patch",
    "context",
    "state",
    "validation",
    "usage",
    "diff",
    "candidates",
    "patchRawJson",
    "harnessControlsList",
    "harnessEnvApply",
    "harnessComposeApply",
    "toolRegistryList",
    "mcpAuditList",
    "inspectorToggle",
    "inspectorDrawer",
)

WORKSPACE_IDS = (
    "ws-chat",
    "ws-goal-brief",
    "ws-benchmarks",
    "ws-dream",
    "ws-memory",
    "ws-graph",
    "ws-settings",
    "ws-tab-chat",
    "ws-tab-goal-brief",
    "ws-tab-benchmarks",
    "ws-tab-dream",
    "ws-tab-memory",
    "ws-tab-graph",
    "ws-tab-settings",
)

PRESERVED_HANDLERS = (
    "setProductMode",
    "showWorkspaceTab",
    "showTab",
    "generatePatch",
    "applyPatch",
    "generateCandidates",
    "testPatch",
    "undoPatch",
    "localCritique",
    "toggleInspector",
    "loadHarnessControls",
    "refreshPromptCost",
)

DANGEROUS_TOKENS = (
    "applyDream",
    "applyEnvFiles",
    "applyComposePatch",
    "blockLessonById",
    "_deleteBenchmark",
    "promoteProposalToLesson",
    "createHandoff(true)",
    "runHandoff",
)


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


def _open_tag_for_group(template: str, group: str) -> str:
    start = template.index(f'data-ui-group="{group}"')
    tag_start = template.rfind("<", 0, start)
    tag_end = template.index(">", start)
    return template[tag_start : tag_end + 1]


def _css_block(styles: str, selector: str) -> str:
    start = styles.index(f"\n{selector} {{")
    return styles[start : styles.index("}", start)]


def test_root_route_renders_operator_console():
    with web_app.app.test_client() as client:
        resp = client.get("/")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="repoPathInput"' in html
    assert 'id="primarySubmit"' in html
    assert "Chat / Patch" in html
    assert "Generate Patch" in html
    assert "Apply / Review Patch" in html


def test_preserved_ids_and_handlers_survive():
    t = _template()

    for element_id in PRESERVED_IDS + WORKSPACE_IDS:
        assert f'id="{element_id}"' in t, f"missing preserved id {element_id!r}"

    for handler in PRESERVED_HANDLERS:
        assert handler in t, f"missing preserved handler {handler!r}"


def test_advanced_debug_and_dangerous_surfaces_collapsed_by_default():
    t = _template()

    options_start = t.index('<details class="instant-run-controls"')
    options_tag = t[options_start : t.index(">", options_start) + 1]
    assert " open" not in options_tag, "Run Options must be collapsed by default"

    for group in (
        "chat-run-details",
        "chat-more-actions",
        "settings-harness",
        "settings-debug",
        "benchmark-prompt-cost",
    ):
        tag = _open_tag_for_group(t, group)
        assert " open" not in tag, f"{group} must be collapsed by default"

    drawer = _open_tag_for_group(t, "inspector-drawer")
    assert "hidden" in drawer
    assert 'aria-hidden="true"' in drawer


def test_main_chat_patch_workflow_visible_and_result_contract_intact():
    t = _template()

    more_actions_at = t.index('data-ui-group="chat-more-actions"')
    assert t.index('id="primarySubmit"') < more_actions_at
    assert t.index("generatePatch()") < more_actions_at
    assert t.index("applyPatch()") < more_actions_at

    run_details = _group_segment(t, "chat-run-details")
    assert "showTab('answer')" not in run_details
    assert "showTab('patch')" not in run_details
    for secondary in ("context", "state", "validation", "usage", "diff", "candidates"):
        assert f"showTab('{secondary}')" in run_details

    showtab = t[t.index("function showTab(") : t.index("function showWorkspaceTab(")]
    assert "chat-run-details" in showtab
    assert ".open = true" in showtab or ".open=true" in showtab


def test_dangerous_actions_are_not_primary_or_inspector_actions():
    t = _template()
    primary_actions = t[
        t.index('class="actions actions--primary"') : t.index(
            'data-ui-group="chat-more-actions"'
        )
    ]
    primary_nav = _group_segment(t, "ws-nav-primary")
    inspector = _group_segment(t, "inspector-drawer")

    for token in DANGEROUS_TOKENS:
        assert token not in primary_actions, f"{token} leaked into primary actions"
        assert token not in primary_nav, f"{token} leaked into primary nav"
        assert token not in inspector, f"{token} leaked into inspector"


def test_ui_cutoff_docs_record_operator_policy():
    doc = IA_DOC.read_text(encoding="utf-8") + "\n" + DEMO_DOC.read_text(encoding="utf-8")

    for phrase in (
        "UI-Cutoff.1",
        "visual/workflow cleanup only",
        "main operator workflow",
        "dangerous-action policy",
        "preserved DOM contracts",
        "advanced/debug/dangerous panels are collapsed by default",
    ):
        assert phrase in doc


def test_css_supports_calm_operator_console_and_readable_results():
    styles = _styles()

    for selector in (
        ".operator-workflow",
        ".tab-content",
        ".patch-card",
        ".bench-detail",
        ".actions--primary > button",
        "button:focus-visible",
        "button:disabled",
        "pre, code",
    ):
        assert selector in styles, f"missing visual contract selector {selector!r}"

    assert "linear-gradient" not in styles, "UI-Cutoff.1 must avoid gradient treatment"


def test_ui2_form_controls_have_explicit_dark_contrast_rules():
    styles = _styles()

    form_block = _css_block(styles, 'input:not([type="checkbox"]), textarea, select')
    assert "background:" in form_block
    assert "border:" in form_block
    assert "border: none" not in form_block
    assert "color: var(--color-text)" in form_block

    for selector in (
        "input::placeholder",
        "textarea::placeholder",
        'input:not([type="checkbox"]):focus',
        "textarea:focus",
        "select:focus",
        'input:not([type="checkbox"]):disabled',
        "textarea:disabled",
        "select:disabled",
        "#repoPathInput",
        'textarea[name="query"]',
    ):
        assert selector in styles, f"missing UI-2 form contrast selector {selector!r}"


def test_ui2_harness_pending_panels_do_not_use_near_white_backgrounds():
    styles = _styles()
    forbidden = ("background: #fff", "background: white", "background: #f8fafc", "background: #eff6ff")

    for selector in (".harness-envapply__box", ".harness-composeapply__box"):
        block = _css_block(styles, selector)
        assert "background:" in block, f"{selector} needs an explicit dark background"
        assert "border:" in block, f"{selector} needs an explicit card border"
        lowered = block.lower()
        for token in forbidden:
            assert token not in lowered, f"{selector} regressed to a near-white background: {token}"


def test_template_has_no_new_privileged_or_external_script_behavior():
    t = _template()
    for token in ("os.system", "child_process", "eval(", "new Function(", "document.write("):
        assert token not in t, f"unexpected privileged token in template: {token!r}"
    assert t.count("<script src=") == 2
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
