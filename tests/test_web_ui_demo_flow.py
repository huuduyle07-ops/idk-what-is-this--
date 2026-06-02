"""Phase UI.2 - Demo Flow & Screenshot Polish contract.

Pins the demo path: every stop in docs/demo_flow.md is reachable in the
current UI, dangerous controls remain collapsed, and core safety tokens in
the backend source files are intact.

The module is read-only: it parses the template / source files as text and
imports nothing heavy (asserted by its own AST guard).
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
DEMO_FLOW_DOC = PROJECT_ROOT / "docs" / "demo_flow.md"

PATCH_GATES_SRC = PROJECT_ROOT / "patching" / "patch_gates.py"
VALIDATOR_SRC = PROJECT_ROOT / "core" / "validator.py"
HARNESS_CONTROLS_SRC = PROJECT_ROOT / "core" / "harness_controls.py"
BENCHMARKS_SRC = PROJECT_ROOT / "benchmarks" / "run_benchmarks.py"

THIS_FILE = Path(__file__)


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _group_segment(template: str, group: str) -> str:
    """Return the template slice for the collapsible identified by ``group``.

    Each collapsible carries ``data-ui-group="<group>"`` on its ``<details>``
    open tag and a matching ``<!-- /<group> -->`` end-comment sentinel.
    """
    start_marker = f'data-ui-group="{group}"'
    end_marker = f"<!-- /{group} -->"
    start = template.index(start_marker)
    end = template.index(end_marker, start)
    return template[start:end]


# ---------------------------------------------------------------------------
# 1 - Demo flow doc exists and contains all required sections
# ---------------------------------------------------------------------------
def test_demo_flow_doc_exists_and_has_required_sections():
    assert DEMO_FLOW_DOC.exists(), "docs/demo_flow.md must exist"
    doc = DEMO_FLOW_DOC.read_text(encoding="utf-8").lower()

    assert "3-minute" in doc, "demo flow doc must contain a 3-minute demo section"
    assert "5-minute" in doc, "demo flow doc must contain a 5-minute demo section"
    assert "fallback" in doc, "demo flow doc must contain a fallback section"
    assert "screenshot checklist" in doc, "demo flow doc must contain a screenshot checklist"

    # Safety message verbatim (case-insensitive).
    assert (
        "dangerous controls are available but collapsed" in doc
    ), "safety message missing from demo flow doc"
    assert "automation is gated" in doc, "safety message incomplete in demo flow doc"


# ---------------------------------------------------------------------------
# 2 - Primary demo actions are visible in the template
# ---------------------------------------------------------------------------
def test_primary_demo_actions_visible():
    t = _template()

    # Demo stop 1: agent form inputs.
    assert 'id="repoPathInput"' in t
    assert 'placeholder="Enter your query..."' in t
    assert 'id="primarySubmit"' in t

    # Demo stops 4 + 5: core patch loop.
    assert "generatePatch()" in t
    assert "applyPatch()" in t

    # Demo stop 6: benchmark run.
    assert "runAllBenchmarks()" in t

    # Demo stop 7: evidence index.
    assert "openPresentationEvidenceIndex()" in t
    assert "buildPresentationEvidence()" in t

    # Primary patch actions must appear before the "More actions" collapsible
    # (they are not demoted into it).
    more_actions_at = t.index('data-ui-group="chat-more-actions"')
    assert t.index("generatePatch()") < more_actions_at
    assert t.index("applyPatch()") < more_actions_at


# ---------------------------------------------------------------------------
# 3 - Advanced / dangerous controls remain inside collapsed <details> panels
# ---------------------------------------------------------------------------
def test_advanced_dangerous_controls_remain_collapsed():
    t = _template()

    # Harness Controls (incl. dangerous .env + compose buttons).
    assert '<details class="advanced-panel" data-ui-group="settings-harness"' in t

    # Tool Registry + MCP Audit debug panel.
    assert '<details class="advanced-panel" data-ui-group="settings-debug"' in t

    # Prompt/Cost report.
    assert '<details class="reports-panel" data-ui-group="benchmark-prompt-cost"' in t

    # Secondary chat actions.
    assert '<details class="more-actions" data-ui-group="chat-more-actions"' in t

    # Verify the harness segment actually contains the dangerous containers.
    harness = _group_segment(t, "settings-harness")
    assert 'id="harnessEnvApply"' in harness
    assert 'id="harnessComposeApply"' in harness


# ---------------------------------------------------------------------------
# 4 - Evidence index is visible outside collapsed panels (demo stop 7)
# ---------------------------------------------------------------------------
def test_evidence_index_visible_outside_collapsed_panels():
    t = _template()

    # Must exist at all.
    assert "openPresentationEvidenceIndex()" in t

    # Must NOT be hidden inside the prompt/cost collapsible.
    prompt_cost_seg = _group_segment(t, "benchmark-prompt-cost")
    assert "openPresentationEvidenceIndex()" not in prompt_cost_seg

    # Must NOT be hidden inside the harness collapsible.
    harness_seg = _group_segment(t, "settings-harness")
    assert "openPresentationEvidenceIndex()" not in harness_seg


# ---------------------------------------------------------------------------
# 5 - Harness Controls panel remains reachable (demo stop 8)
# ---------------------------------------------------------------------------
def test_harness_controls_reachable():
    t = _template()
    assert 'id="harnessControlsList"' in t
    assert "_renderHarnessControls" in t
    assert "loadHarnessControls" in t

    # The containers for dangerous buttons exist inside the panel.
    harness = _group_segment(t, "settings-harness")
    assert 'id="harnessControlsList"' in harness
    assert 'id="harnessEnvApply"' in harness
    assert 'id="harnessComposeApply"' in harness

    # The Cooling Brain (Memory Temperature) toggle is rendered dynamically
    # into harnessControlsList via the editable_live path.
    assert "editable_live" in t


# ---------------------------------------------------------------------------
# 6 - No new backend tokens introduced into the template
# ---------------------------------------------------------------------------
def test_no_new_backend_tokens_in_template():
    t = _template()
    forbidden = ("os.system", "child_process", "eval(", "new Function(", "document.write(")
    for token in forbidden:
        assert token not in t, f"unexpected privileged token in template: {token!r}"

    # UI.1 fixed the external-script count; UI.2 must not add new ones.
    assert t.count("<script src=") == 2
    assert t.count('src="http') == 1  # mermaid CDN only


# ---------------------------------------------------------------------------
# 7 - AST safety guards: core safety tokens intact in source files
# ---------------------------------------------------------------------------
def test_ast_safety_guards():
    # Patch grounding gate — must remain in patching/patch_gates.py.
    patch_gates = PATCH_GATES_SRC.read_text(encoding="utf-8")
    assert (
        "reject_ungrounded_patch" in patch_gates
    ), "reject_ungrounded_patch missing from patching/patch_gates.py"

    # Validation command runner — must remain in core/validator.py.
    validator = VALIDATOR_SRC.read_text(encoding="utf-8")
    assert (
        "run_validation_command" in validator
    ), "run_validation_command missing from core/validator.py"

    # Memory Temperature harness controls — editable_live type and the
    # specific control name must remain in core/harness_controls.py.
    harness = HARNESS_CONTROLS_SRC.read_text(encoding="utf-8")
    assert (
        "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED" in harness
    ), "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED missing from core/harness_controls.py"
    assert (
        "EDITABLE_LIVE" in harness
    ), "EDITABLE_LIVE constant missing from core/harness_controls.py"

    # Benchmark scoring — PASS/FAIL decision tokens must remain.
    benchmarks = BENCHMARKS_SRC.read_text(encoding="utf-8")
    assert '"PASS"' in benchmarks, '"PASS" scoring token missing from benchmarks/run_benchmarks.py'
    assert '"FAIL"' in benchmarks, '"FAIL" scoring token missing from benchmarks/run_benchmarks.py'


# ---------------------------------------------------------------------------
# 8 - AST self-guard: this test module imports nothing heavy / privileged
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
        assert top in allowed_top, f"unexpected import in demo-flow audit: {imp}"
