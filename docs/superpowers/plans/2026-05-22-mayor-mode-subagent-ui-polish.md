# Mayor Mode Sub-agent UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Darken the Mayor Mode handoff and Worker Runs cards in the Memory tab and clarify safe command-copy actions versus quota-consuming temp-clone runs without changing route behavior.

**Architecture:** Keep the presentation change on the existing template and stylesheet surface. A focused template contract test locks the requested labels, link, empty-state copy, and dark-theme class hooks before the template JavaScript emits dark card markup and CSS owns the visual treatment.

**Tech Stack:** Flask template HTML, vanilla JavaScript template strings, CSS, pytest

---

## File Map

- `tests/test_mayor_mode_ui.py`: template contract checks for the requested Sub-agent UI copy and CSS hooks.
- `web/templates/index.html`: Sub-agent audit link markup, emitted handoff/worker-run class hooks, button labels, and Worker Runs empty-state text.
- `web/static/style.css`: dark card surfaces, metadata contrast, card action layout, status badge, warning-outline execution button, audit link, and Worker Runs detail styling.

### Task 1: Lock The Template UI Contract

**Files:**
- Create: `tests/test_mayor_mode_ui.py`
- Test: `tests/test_mayor_mode_ui.py`

- [ ] **Step 1: Write the failing template contract test**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails before UI changes**

Run:

```powershell
python -m pytest tests/test_mayor_mode_ui.py -q
```

Expected: FAIL because `View MCP audit`, the renamed handoff action labels, and the dark-theme class hooks are not present yet.

- [ ] **Step 3: Commit the failing test**

```powershell
git add tests/test_mayor_mode_ui.py
git commit -m "test: cover subagent UI polish contract"
```

### Task 2: Move Sub-agent Cards Onto Dark Theme CSS

**Files:**
- Modify: `web/templates/index.html`
- Modify: `web/static/style.css`
- Test: `tests/test_mayor_mode_ui.py`

- [ ] **Step 1: Add the Sub-agent header audit link**

Update the Sub-agent header markup in `web/templates/index.html`:

```html
<div class="subagent-group__header">
  <h3 class="subagent-group__title">Sub-agent</h3>
  <a class="subagent-group__audit-link" href="/mcp/audit?limit=10">View MCP audit</a>
</div>
```

- [ ] **Step 2: Emit dark handoff card hooks and rename the two handoff actions**

Replace the handoff list card template in `refreshHandoffs()` with class-driven markup:

```javascript
list.innerHTML = body.handoffs.map(h => `
    <div class="handoff-item subagent-run-card" data-path="${_escapeHtml(h.path)}">
        <div class="handoff-item__head subagent-run-card__head">
            <strong>${_escapeHtml(h.title || "(untitled)")}</strong>
            <span class="handoff-item__status handoff-item__status--${_escapeHtml(h.status || "draft")}">${_escapeHtml(h.status || "draft")}</span>
        </div>
        <div class="handoff-item__meta subagent-run-card__meta">
            worker: <code>${_escapeHtml(h.intended_worker || "?")}</code>
            &middot; task: <code>${_escapeHtml(h.task_type || "?")}</code>
            &middot; ${_escapeHtml(h.created_at || "")}
        </div>
        <div class="handoff-item__actions subagent-run-card__actions">
            <button type="button" class="lesson-btn--secondary" onclick="runHandoff('${_escapeHtml(h.path).replace(/'/g, "\\'")}', false)">Copy command</button>
            <button type="button" class="handoff-run-btn--warning-outline" onclick="runHandoff('${_escapeHtml(h.path).replace(/'/g, "\\'")}', true)">Run subagent in temp clone</button>
        </div>
    </div>
`).join("");
```

- [ ] **Step 3: Update Worker Runs empty-state copy and card hooks**

Change the empty state in `refreshWorkerRuns()`:

```javascript
list.innerHTML = '<div class="health-empty">No worker runs yet. Run a handoff in a temp clone to create .agent/worker_runs/.</div>';
```

Replace the Worker Runs card template with dark class hooks while preserving the existing `viewWorkerRun(...)` and import button logic:

```javascript
return `
    <div class="worker-run-item subagent-run-card" data-run-id="${_escapeHtml(r.run_id)}">
        <div class="worker-run-item__head subagent-run-card__head">
            <strong>${_escapeHtml(r.handoff_title || r.run_id || "(unnamed)")}</strong>
            <span class="worker-run-item__id">${_escapeHtml(r.run_id || "")}</span>
        </div>
        <div class="worker-run-item__meta subagent-run-card__meta">
            worker: <code>${_escapeHtml(r.worker || "?")}</code>${dryBadge}${exitBadge}
            &middot; ${_escapeHtml(propBadge)} &middot; ${_escapeHtml(planBadge)}
        </div>
        <div class="worker-run-item__actions subagent-run-card__actions">
            <button type="button" class="lesson-btn--secondary" onclick="viewWorkerRun('${_escapeHtml(r.run_id).replace(/'/g, "\\'")}', this)">View details</button>
            ${importBtn}
        </div>
        <div class="worker-run-detail"></div>
    </div>
`;
```

- [ ] **Step 4: Add dark theme CSS for the Sub-agent surfaces and warning outline action**

Append the following CSS near the existing `.subagent-group` styles in `web/static/style.css`:

```css
.subagent-group__audit-link {
    color: #93c5fd;
    font-size: 12px;
    text-decoration: none;
}

.subagent-group__audit-link:hover {
    color: #bfdbfe;
    text-decoration: underline;
}

.subagent-run-card {
    margin-bottom: 12px;
    padding: 12px;
    border: 1px solid #334155;
    border-radius: 6px;
    background: #0f172a;
    color: #e2e8f0;
}

.subagent-run-card__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 6px;
}

.subagent-run-card__head strong {
    min-width: 0;
    color: #f8fafc;
    overflow-wrap: anywhere;
}

.subagent-run-card__meta {
    margin-bottom: 10px;
    color: #94a3b8;
    font-size: 12px;
    line-height: 1.45;
    overflow-wrap: anywhere;
}

.subagent-run-card__meta code {
    color: #cbd5e1;
}

.subagent-run-card__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.handoff-item__status {
    flex: 0 0 auto;
    padding: 2px 6px;
    border: 1px solid #475569;
    border-radius: 4px;
    background: #1e293b;
    color: #cbd5e1;
    font-size: 11px;
    font-weight: 700;
    line-height: 1.2;
}

.handoff-item__status--ran {
    background: #052e16;
    border-color: #166534;
    color: #bbf7d0;
}

.handoff-item__status--failed {
    background: #450a0a;
    border-color: #7f1d1d;
    color: #fecaca;
}

.worker-run-item__id {
    color: #64748b;
    flex: 0 0 auto;
    font-size: 11px;
}

.handoff-item__actions button,
.worker-run-item__actions button {
    padding: 4px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
}

.handoff-item__actions .lesson-btn--secondary,
.worker-run-item__actions .lesson-btn--secondary {
    background: #1e293b;
    border: 1px solid #475569;
    color: #cbd5e1;
}

.handoff-run-btn--warning-outline {
    background: transparent;
    border: 1px solid #f59e0b;
    color: #fbbf24;
}

.handoff-run-btn--warning-outline:hover {
    background: #422006;
    color: #fde68a;
}

.worker-run-detail {
    display: none;
    margin-top: 10px;
    padding: 8px;
    border: 1px solid #334155;
    border-radius: 4px;
    background: #020617;
    color: #cbd5e1;
    font-size: 12px;
}
```

- [ ] **Step 5: Run the focused template test to verify it passes**

Run:

```powershell
python -m pytest tests/test_mayor_mode_ui.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the dark-theme UI update**

```powershell
git add web/templates/index.html web/static/style.css
git commit -m "polish subagent memory cards"
```

### Task 3: Verify Presentation-Only Behavior

**Files:**
- Verify: `tests/test_mayor_mode_ui.py`
- Verify: `tests/test_handoff_routes.py`
- Verify: `tests/test_worker_runs_routes.py`
- Inspect: `web/templates/index.html`
- Inspect: `web/static/style.css`

- [ ] **Step 1: Run the relevant UI and route tests**

```powershell
python -m pytest tests/test_mayor_mode_ui.py tests/test_handoff_routes.py tests/test_worker_runs_routes.py -q
```

Expected: PASS with no route-test failures.

- [ ] **Step 2: Run existing web/template-adjacent tests**

```powershell
python -m pytest tests/test_dream_patch_blockers.py tests/test_mcp_audit_route.py -q
```

Expected: PASS.

- [ ] **Step 3: Visually inspect the Memory tab in the local browser**

Start the existing Flask app if it is not already running:

```powershell
python web/app.py
```

Open the Memory tab in the Codex browser, refresh the handoff list, and inspect a populated handoff card at desktop width. Confirm the card uses a dark surface, the status badge remains visible, metadata text is readable, the audit link is beside the Sub-agent header, `Copy command` is visually quiet, and `Run subagent in temp clone` reads as a warning outline action.

- [ ] **Step 4: Review the diff against the scope guardrails**

```powershell
git diff --stat HEAD~2
git diff -- web/templates/index.html web/static/style.css tests/test_mayor_mode_ui.py
```

Expected: only template, stylesheet, and template-contract-test changes for the UI polish.
