# Phase UI.2 — Demo Flow & Screenshot Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `docs/demo_flow.md` (3-min + 5-min demo scripts, screenshot checklist) and `tests/test_web_ui_demo_flow.py` (8 tests pinning demo-path contract + AST safety guards), with zero template/CSS/backend changes.

**Architecture:** Option A (docs + tests only). The IA freeze from UI.1 already ensures primary actions are visible and dangerous controls are collapsed; UI.2 documents and mechanically verifies that state. The test file uses text-only parsing (same pattern as `tests/test_web_ui_information_architecture.py`) so it imports nothing heavy and can run without a running Flask server.

**Tech Stack:** Python 3, `pathlib`, `ast`, `re` (stdlib only). Markdown for the demo doc. pytest for test runner.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `docs/demo_flow.md` | Demo scripts (3-min, 5-min), fallback plan, safety message, screenshot checklist |
| Create | `tests/test_web_ui_demo_flow.py` | 8 tests: demo-path contract + AST safety guards |

No other files are touched.

---

### Task 1: Write `docs/demo_flow.md`

**Files:**
- Create: `docs/demo_flow.md`

- [ ] **Step 1: Create the file with the full demo flow document**

Write `docs/demo_flow.md` with exactly this content:

```markdown
# C.A.T.T.U.S — Demo Flow

> Last updated: 2026-06-02. Covers Phase UI.2 (IA freeze active).

**Safety message:** Dangerous controls are available but collapsed; automation is gated.

---

## 3-Minute Demo

Eight stops. Each stop has a *click* action and a *say* line.

| # | Tab / Area | Click | Say |
|---|-----------|-------|-----|
| 1 | **Agent form** | Point at repo path field and query textarea | "You give it a repo path and a question — that's the whole input." |
| 2 | **Agent form** | Click **Run** (or load a pre-run session — see Fallback) | "It runs the full retrieval + analysis pipeline." |
| 3 | **Graph** tab | Click **Clean Graph**, then click **Scope Spread** | "This is the explainability layer — every node is a code file, edges are evidence links." |
| 4 | **Chat / Patch** tab | Click **Generate Patch** | "Based on that graph evidence, it proposes a targeted patch." |
| 5 | **Chat / Patch** tab | Click **Apply / Review Patch** | "Apply writes the patch to disk; the diff is shown immediately for review." |
| 6 | **Benchmarks** tab | Click on the latest run in the past-runs list | "32 checks, 0 errors — the safety suite runs after every patch." |
| 7 | **Benchmarks** tab | Click **Open evidence index** | "This is the full audit trail — every benchmark result linked to its evidence pack." |
| 8 | **Settings / Health** tab | Point at the **Advanced** disclosure (do not open) | "Harness controls, .env apply, and docker-compose are all here — available but collapsed. Nothing dangerous runs automatically." |

**Total time:** ~3 minutes at a comfortable pace.

---

## 5-Minute Demo

Run the 8 stops above, then continue:

| # | Tab / Area | Click | Say |
|---|-----------|-------|-----|
| 9 | **Goal Brief** tab | Click **Start brief** | "Goal Brief guides you through scoping the problem before generating anything." |
| 10 | **Memory** tab | Scroll through the Lessons list | "Every run produces lessons. These feed back into the retrieval graph on the next run." |
| 11 | **Settings / Health** tab | Open the **Advanced** disclosure → point at **Cooling Brain** toggle | "This is the Memory Temperature toggle — it gates retrieval. It's OFF by default; you enable it deliberately." |
| 12 | **Dream** tab | Show the queue panel only — do not click Start | "The overnight queue lets you schedule a batch of Dream items. Nothing runs until you explicitly start it." |

**Total time:** ~5 minutes.

---

## Fallback (if live analysis is slow)

If the live Run in stop 2 takes too long during the demo:

1. **Pre-load a session.** Open the app, load a previously completed session from the sidebar. Skip stop 2 entirely — the graph, patch, and benchmark results are all already populated.
2. **Benchmark results are cached.** The Benchmarks tab shows the last run result without re-running. Stop 6 always works without a new run.
3. **Evidence index is static.** The evidence index opened in stop 7 is a static file written by the last `build_presentation_evidence` call. It loads instantly.

---

## Screenshot Checklist

Prepare these screenshots before the demo. Each one covers a key demo stop.

- [ ] **Chat/Patch primary row** — both "Generate Patch" and "Apply / Review Patch" buttons visible; "More actions" disclosure closed.
- [ ] **Graph — clean graph** — at least one rendered graph with nodes and edges; zoom controls visible.
- [ ] **Graph — evidence spread** — Scope Spread output panel open and showing spread data.
- [ ] **Benchmarks — runner with options collapsed** — "Run all" and "Run selected" visible; ⚙ Options disclosure closed (default state).
- [ ] **Benchmarks — result 32 / 0** — detail panel showing 32 checked, 0 errors.
- [ ] **Memory — Lessons list or Cooling Brain toggle** — either the lessons list with at least one entry, or the Cooling Brain toggle visible inside the Harness Controls panel.
- [ ] **Settings — Harness Controls collapsed** — Advanced disclosure closed, showing only the summary label ("Advanced — Harness Controls, .env, docker-compose").
```

- [ ] **Step 2: Verify the file contains the required anchors the tests will check**

Run:
```
python -c "
from pathlib import Path
doc = Path('docs/demo_flow.md').read_text(encoding='utf-8').lower()
checks = ['3-minute', '5-minute', 'fallback', 'screenshot checklist', 'dangerous controls are available but collapsed']
for c in checks:
    status = 'OK' if c in doc else 'MISSING'
    print(f'{status}: {c!r}')
"
```

Expected — all five lines print `OK`:
```
OK: '3-minute'
OK: '5-minute'
OK: 'fallback'
OK: 'screenshot checklist'
OK: 'dangerous controls are available but collapsed'
```

- [ ] **Step 3: Commit**

```
git add docs/demo_flow.md
git commit -m "docs: add Phase UI.2 demo flow and screenshot checklist"
```

---

### Task 2: Write `tests/test_web_ui_demo_flow.py`

**Files:**
- Create: `tests/test_web_ui_demo_flow.py`

- [ ] **Step 1: Create the test file**

Write `tests/test_web_ui_demo_flow.py` with exactly this content:

```python
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
```

- [ ] **Step 2: Run compile check**

```
python -m compileall web tests
```

Expected: `Compiling ...` lines, no errors, exit 0.

- [ ] **Step 3: Run the two targeted test files**

```
python -m pytest tests/test_web_ui_information_architecture.py tests/test_web_ui_demo_flow.py -q
```

Expected:
```
................
16 passed in X.XXs
```

(12 IA tests + 8 demo-flow tests = 20 passed — adjust if count differs, but all must be green.)

- [ ] **Step 4: Run the full test suite**

```
python -m pytest tests -q --basetemp .fresh_tmp_ui2
```

Expected: all tests pass. No new failures.

- [ ] **Step 5: Run benchmark check**

```
python benchmarks/run_benchmarks.py --check
```

Expected: exits 0 (check mode only — does not run benchmarks).

- [ ] **Step 6: Commit**

```
git add tests/test_web_ui_demo_flow.py
git commit -m "test: add Phase UI.2 demo-flow contract and AST safety guards"
```

---

## Final Validation

After both tasks are committed, run the full validation sequence once more to confirm nothing is broken:

```
python -m compileall web tests
python -m pytest tests/test_web_ui_information_architecture.py tests/test_web_ui_demo_flow.py -q
python -m pytest tests -q --basetemp .fresh_tmp_ui2
python benchmarks/run_benchmarks.py --check
```

All four commands must exit 0.
