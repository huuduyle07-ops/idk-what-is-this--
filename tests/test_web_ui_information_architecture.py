"""Phase UI.1 - Web Information Architecture Freeze.

Contract checks for the web UI's *information architecture* after the UI.1
reorganization (grouping / button hierarchy / collapsible advanced+dangerous
controls). The reorg is intentionally **additive**: every ``onclick`` handler,
element ``id`` and button label that existing tests / JS depend on is preserved
verbatim. These tests pin the new hierarchy so a future redesign cannot silently
re-promote dangerous controls or drop a power feature.

Principle under test: *keep power, hide complexity*.

  * Primary demo actions still render (repo path, query, run, generate/apply
    patch, run benchmark, open evidence report).
  * Advanced / debug controls still exist but live inside collapsible
    ``<details>`` sections (harness controls, .env apply, docker-compose apply,
    tool registry, MCP audit, prompt/cost, secondary chat actions).
  * Harness Controls, benchmark run options, and the Cooling Brain (Memory
    Temperature) toggle remain reachable.
  * Dangerous / config actions (.env apply, docker-compose apply) are NOT
    primary visual actions - they sit inside a collapsed advanced panel.
  * The read-only / safety affirmations of the inert panels survive verbatim
    (a template-scoped guard that the reorg changed no behavior).

The module is read-only: it parses the template / stylesheet as text and imports
nothing heavy (asserted by its own AST guard).
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"
IA_DOC = PROJECT_ROOT / "docs" / "web_ui_information_architecture.md"
HARNESS_CONTROLS_SRC = PROJECT_ROOT / "core" / "harness_controls.py"

THIS_FILE = Path(__file__)


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _styles() -> str:
    return STYLE_SHEET.read_text(encoding="utf-8")


def _group_segment(template: str, group: str) -> str:
    """Return the template slice for the collapsible identified by ``group``.

    Each reorganized collapsible carries a unique ``data-ui-group="<group>"``
    attribute on its ``<details>`` open tag and a matching
    ``<!-- /<group> -->`` end-comment sentinel. Slicing between them lets us
    assert a control lives *inside* that collapsible without parsing nested
    HTML.
    """
    start_marker = f'data-ui-group="{group}"'
    end_marker = f"<!-- /{group} -->"
    start = template.index(start_marker)
    end = template.index(end_marker, start)
    return template[start:end]


# ---------------------------------------------------------------------------
# 1 - Primary demo actions still render and stay out of the collapsed area
# ---------------------------------------------------------------------------
def test_primary_demo_actions_render():
    t = _template()

    # Repo path + query input + run.
    assert 'id="repoPathInput"' in t
    assert 'placeholder="Enter your query..."' in t
    assert 'id="primarySubmit"' in t

    # Core patch loop primary actions.
    assert "generatePatch()" in t
    assert "applyPatch()" in t

    # Benchmarks + evidence report (kept visible per the IA spec).
    assert "runAllBenchmarks()" in t
    assert "openPresentationEvidenceIndex()" in t
    assert "buildPresentationEvidence()" in t

    # The two primary patch actions must appear before the collapsed
    # "more actions" group (i.e. they are NOT demoted into it).
    more_actions_at = t.index('data-ui-group="chat-more-actions"')
    assert t.index("generatePatch()") < more_actions_at
    assert t.index("applyPatch()") < more_actions_at


# ---------------------------------------------------------------------------
# 2 - Secondary chat/patch actions live inside the collapsible "More actions"
# ---------------------------------------------------------------------------
def test_secondary_chat_actions_inside_more_actions():
    t = _template()
    assert '<details class="more-actions" data-ui-group="chat-more-actions"' in t

    seg = _group_segment(t, "chat-more-actions")
    for handler in ("generateCandidates()", "testPatch()", "undoPatch()", "localCritique()"):
        assert handler in seg, f"{handler} should be inside the More actions collapsible"

    # The original labels are preserved verbatim inside the collapsible.
    assert "Generate Candidates" in seg
    assert "Test Run Patch" in seg
    assert "Undo" in seg
    assert "Local Critique" in seg


# ---------------------------------------------------------------------------
# 3 - Advanced settings panels are inside collapsible advanced panels
# ---------------------------------------------------------------------------
def test_advanced_settings_panels_are_collapsible():
    t = _template()

    # Harness Controls (incl. the .env-apply + compose-apply containers that JS
    # fills with the dangerous buttons) collapsed.
    assert '<details class="advanced-panel" data-ui-group="settings-harness"' in t
    harness = _group_segment(t, "settings-harness")
    assert 'id="harnessControlsList"' in harness
    assert 'id="harnessEnvApply"' in harness
    assert 'id="harnessComposeApply"' in harness

    # Tool Registry + Recent MCP Audit collapsed together (debug).
    assert '<details class="advanced-panel" data-ui-group="settings-debug"' in t
    debug = _group_segment(t, "settings-debug")
    assert 'id="toolRegistryList"' in debug
    assert "Tool Registry" in debug
    assert 'id="mcpAuditList"' in debug
    assert "Recent MCP Audit" in debug


# ---------------------------------------------------------------------------
# 4 - Prompt/Cost (advanced report) collapsed; evidence report stays visible
# ---------------------------------------------------------------------------
def test_prompt_cost_report_is_collapsible():
    t = _template()
    assert '<details class="reports-panel" data-ui-group="benchmark-prompt-cost"' in t
    seg = _group_segment(t, "benchmark-prompt-cost")
    assert 'id="promptCostSection"' in seg
    assert "refreshPromptCost()" in seg

    # "Open evidence report" remains a visible (non-collapsed) primary action:
    # it must NOT be inside the prompt/cost collapsible.
    assert "openPresentationEvidenceIndex()" not in seg


# ---------------------------------------------------------------------------
# 5 - Harness Controls remain accessible (panel + render machinery present)
# ---------------------------------------------------------------------------
def test_harness_controls_remain_accessible():
    t = _template()
    assert 'id="harnessControlsList"' in t
    assert "_renderHarnessControls" in t
    assert "loadHarnessControls" in t
    assert 'id="harnessEnvApply"' in t
    assert 'id="harnessComposeApply"' in t


# ---------------------------------------------------------------------------
# 6 - Benchmark run options remain accessible
# ---------------------------------------------------------------------------
def test_benchmark_options_remain_accessible():
    t = _template()
    assert 'id="benchOptionsToggle"' in t
    assert 'id="benchRunOptions"' in t
    assert "toggleBenchmarkOptions" in t
    # The individual option controls still exist.
    for opt in ("benchOptFast", "benchOptTurbo", "benchOptSkipToolchain", "benchOptRetry"):
        assert f'id="{opt}"' in t


# ---------------------------------------------------------------------------
# 7 - Cooling Brain (Memory Temperature) toggle remains accessible
# ---------------------------------------------------------------------------
def test_cooling_brain_toggle_remains_accessible():
    t = _template()
    # The toggle is rendered dynamically into the harness controls list from
    # /harness/controls, via the editable_live render path.
    assert "editable_live" in t
    assert 'id="harnessControlsList"' in t

    # And the control is still registered as an editable_live (UI-toggleable)
    # harness control, so the dynamic render will surface it.
    src = HARNESS_CONTROLS_SRC.read_text(encoding="utf-8")
    assert "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED" in src
    assert "EDITABLE_LIVE" in src


# ---------------------------------------------------------------------------
# 8 - Dangerous / config actions are NOT primary visual actions
# ---------------------------------------------------------------------------
def test_dangerous_config_actions_are_not_primary():
    t = _template()

    # The .env-apply and docker-compose-apply buttons are injected by JS into
    # these containers; both containers live inside the collapsed advanced
    # harness panel, so the dangerous buttons render collapsed - never as
    # always-visible primary actions.
    harness = _group_segment(t, "settings-harness")
    assert 'id="harnessEnvApply"' in harness
    assert 'id="harnessComposeApply"' in harness

    # The containers must not leak into the primary chat actions block.
    primary_at = t.index('class="actions actions--primary"')
    more_actions_at = t.index('data-ui-group="chat-more-actions"')
    primary_block = t[primary_at:more_actions_at]
    assert 'id="harnessEnvApply"' not in primary_block
    assert 'id="harnessComposeApply"' not in primary_block

    # The dangerous buttons themselves carry their warning style class, and the
    # stylesheet gives that class a distinct warning/danger treatment.
    assert "harness-envapply__btn" in t
    assert "harness-composeapply__btn" in t
    styles = _styles()
    assert "harness-envapply__btn" in styles or "harness-composeapply__btn" in styles


# ---------------------------------------------------------------------------
# 9 - Guard: the reorg preserved every inert-panel safety affirmation verbatim
# ---------------------------------------------------------------------------
def test_read_only_safety_copy_preserved():
    t = _template()
    # If the reorg silently changed a panel's documented behavior, these break.
    assert "writes reports to .agent/benchmarks" in t
    assert "Read-only: never runs benchmarks or calls models" in t
    assert "This panel does not write" in t  # harness controls: no .env / compose write
    assert "Registry is metadata-only. This page does not execute tools." in t
    assert "Audit is read-only. This panel does not execute MCP tools." in t


# ---------------------------------------------------------------------------
# 10 - Guard: the template introduces no privileged backend-style behavior
# ---------------------------------------------------------------------------
def test_template_introduces_no_privileged_tokens():
    t = _template()
    # The template is client-side only; it must not smuggle in backend/privileged
    # operations. (UI.1 touches template/CSS/doc/test only - no route, patch,
    # validation, scoring, CONTROL-prompt, DB, Docker, or model/API code.)
    forbidden = ("os.system", "child_process", "eval(", "new Function(", "document.write(")
    for token in forbidden:
        assert token not in t, f"unexpected privileged token in template: {token!r}"

    # Four known scripts: Mermaid, keybindings and two local SEC.UI.1 assets;
    # the reorg added no new external script.
    assert t.count("<script src=") == 6  # two local SEC.UI.1 security assets, the AUTH.WEB.1 request-integrity owner and the UX.STATE.1 workflow-state owner
    assert t.count('src="http') == 1  # solely the mermaid CDN


# ---------------------------------------------------------------------------
# 11 - The information-architecture doc exists and classifies every control
# ---------------------------------------------------------------------------
def test_information_architecture_doc_exists_and_classifies():
    assert IA_DOC.exists(), "docs/web_ui_information_architecture.md must exist"
    doc = IA_DOC.read_text(encoding="utf-8").lower()

    # The five-way classification taxonomy is documented.
    for label in (
        "primary demo action",
        "secondary action",
        "advanced/debug",
        "dangerous/config",
        "deprecated/rare",
    ):
        assert label in doc, f"taxonomy label missing from IA doc: {label!r}"

    # The six top-level groups are documented.
    for group in (
        "chat / patch",
        "graph",
        "benchmark",
        "memory",
        "evidence",
        "settings",
    ):
        assert group in doc, f"group missing from IA doc: {group!r}"

    # The seven workspace tabs are enumerated.
    for tab in ("goal brief", "dream", "settings / health"):
        assert tab in doc


# ---------------------------------------------------------------------------
# 12 - AST self-guard: this audit imports nothing heavy / privileged
# ---------------------------------------------------------------------------
def test_audit_module_has_no_forbidden_imports():
    source = THIS_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    allowed_top = {"ast", "pathlib", "__future__"}
    for imp in imported:
        top = imp.split(".")[0]
        assert top in allowed_top, f"unexpected import in IA audit: {imp}"
