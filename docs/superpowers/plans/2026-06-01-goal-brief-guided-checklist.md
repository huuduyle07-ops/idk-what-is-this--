# Goal Brief Guided Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Goal Brief panel easier to use by replacing the right-side schema summary with a guided checklist that inserts useful reply templates.

**Architecture:** Keep the backend schema, routes, and parser unchanged. Add frontend-only checklist rendering derived from the returned `brief`, plus focused route-render tests that verify the UI contract and schema compatibility.

**Tech Stack:** Flask/Jinja template in `web/templates/index.html`, plain JavaScript in the same template, CSS in `web/static/style.css`, pytest route tests in `tests/test_goal_brief_routes.py`.

---

## File Map

- Modify `tests/test_goal_brief_routes.py`: add failing route-render assertions for the guided checklist shell, new quick replies, and schema stability.
- Modify `web/templates/index.html`: replace the initial summary markup with a checklist shell, update quick reply chips, and add checklist renderer helpers near the existing Goal Brief JavaScript.
- Modify `web/static/style.css`: style progress, grouped checklist rows, row states, and compact insert buttons inside the existing Goal Brief CSS section.

No backend file should change for this feature.

---

### Task 1: Route-Render Tests

**Files:**
- Modify: `tests/test_goal_brief_routes.py`
- Test: `tests/test_goal_brief_routes.py`

- [ ] **Step 1: Write the failing render tests**

Add this test below `test_goal_brief_panel_is_rendered`:

```python
def test_goal_brief_panel_renders_guided_checklist(client):
    resp = client.get("/")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="goalBriefChecklist"' in html
    assert "goal-brief-checklist-empty" in html
    assert "Start with a goal to build the checklist." in html
    assert "Task type" in html
    assert "Observed result" in html
    assert "Success criteria" in html
    assert "Expected pass" in html
    assert "Actual failure" in html
    assert "Allowed files" in html
    assert "Validation command" in html
    assert "insertGoalBriefReply('expected_result: all tests pass')" in html
    assert "insertGoalBriefReply('validation_command: python -m pytest tests -q')" in html
```

Add this schema compatibility assertion to `test_goal_brief_start_route_creates_draft` after the existing `assert body["brief"]["goal"] == "Fix weird auth failure"` line:

```python
    assert "summary" not in body["brief"]
    assert set(body["brief"]) == set(goal_brief.GOAL_BRIEF_SCHEMA)
```

- [ ] **Step 2: Run the route tests and verify they fail for the missing UI**

Run:

```bash
python -m pytest tests/test_goal_brief_routes.py -q
```

Expected: one failure in `test_goal_brief_panel_renders_guided_checklist` because `goalBriefChecklist` and the new guided copy are not rendered yet. Existing route tests should still pass.

- [ ] **Step 3: Commit the failing test only if working in a branch that keeps red commits**

For normal inline work, do not commit the red state. Keep it local and continue to Task 2.

---

### Task 2: Guided Checklist Markup And JavaScript

**Files:**
- Modify: `web/templates/index.html`
- Test: `tests/test_goal_brief_routes.py`

- [ ] **Step 1: Replace the quick reply chips**

In `web/templates/index.html`, replace the current quick chips inside `<div class="goal-brief-chips" ...>` with:

```html
<button type="button" onclick="insertGoalBriefReply('problem_type: bug_fix')">Bug fix</button>
<button type="button" onclick="insertGoalBriefReply('problem_type: feature')">Feature</button>
<button type="button" onclick="insertGoalBriefReply('expected_result: all tests pass')">Expected pass</button>
<button type="button" onclick="insertGoalBriefReply('actual_result: FAILED test_name - paste the relevant output')">Actual failure</button>
<button type="button" onclick="insertGoalBriefReply('allowed_files: path/to/file.py, tests/test_file.py')">Allowed files</button>
<button type="button" onclick="insertGoalBriefReply('validation_command: python -m pytest tests -q')">Validation command</button>
<button type="button" onclick="insertGoalBriefReply('forbidden_files: none')">No files forbidden</button>
```

- [ ] **Step 2: Replace the initial summary shell**

Replace the current `goalBriefSummary` section contents with this shell:

```html
<section id="goalBriefSummary" class="goal-brief-summary" aria-live="polite">
  <div id="goalBriefProgress" class="goal-brief-progress">
    <strong>Not started</strong>
  </div>
  <div id="goalBriefChecklist" class="goal-brief-checklist">
    <div class="goal-brief-checklist-empty">Start with a goal to build the checklist.</div>
  </div>
</section>
```

- [ ] **Step 3: Add checklist helper functions**

In the Goal Brief JavaScript block, add these helpers after `_goalBriefCommandList` and before `_renderGoalBriefSummary`:

```javascript
const GOAL_BRIEF_CHECKLIST = [
    {
        group: "Task",
        items: [
            {
                key: "problem_type",
                label: "Task type",
                template: "problem_type: bug_fix",
                value: brief => brief.problem_type || "",
            },
        ],
    },
    {
        group: "Evidence",
        items: [
            {
                key: "evidence.command_run",
                label: "Command or check",
                template: "command: python -m pytest tests -q",
                value: brief => brief.evidence?.command_run || "",
            },
            {
                key: "evidence.expected_result",
                label: "Expected result",
                template: "expected_result: all tests pass",
                value: brief => brief.evidence?.expected_result || "",
            },
            {
                key: "evidence.actual_result_or_error_output",
                label: "Observed result",
                template: "actual_result: FAILED test_name - paste the relevant output",
                value: brief => brief.evidence?.actual_result || brief.evidence?.error_output || "",
            },
        ],
    },
    {
        group: "Scope",
        items: [
            {
                key: "constraints.allowed_files",
                label: "Allowed files",
                template: "allowed_files: path/to/file.py, tests/test_file.py",
                value: brief => Array.isArray(brief.constraints?.allowed_files)
                    ? brief.constraints.allowed_files.join(", ")
                    : "",
            },
        ],
    },
    {
        group: "Validation",
        items: [
            {
                key: "validation.command",
                label: "Validation command",
                template: "validation_command: python -m pytest tests -q",
                value: brief => brief.validation?.command || "",
            },
            {
                key: "validation.success_criteria",
                label: "Success criteria",
                template: "success_criteria: the validation command exits 0",
                value: brief => brief.validation?.success_criteria || "",
            },
        ],
    },
];

function _goalBriefChecklistRows(brief) {
    const source = brief || {};
    return GOAL_BRIEF_CHECKLIST.map(group => ({
        group: group.group,
        items: group.items.map(item => {
            const value = String(item.value(source) || "").trim();
            return { ...item, value, complete: Boolean(value) };
        }),
    }));
}

function _renderGoalBriefChecklist(brief) {
    const progressEl = document.getElementById("goalBriefProgress");
    const checklistEl = document.getElementById("goalBriefChecklist");
    if (!progressEl || !checklistEl) return;

    if (!brief) {
        progressEl.innerHTML = "<strong>Not started</strong>";
        checklistEl.innerHTML = '<div class="goal-brief-checklist-empty">Start with a goal to build the checklist.</div>';
        return;
    }

    const groups = _goalBriefChecklistRows(brief);
    const total = groups.reduce((count, group) => count + group.items.length, 0);
    const complete = groups.reduce(
        (count, group) => count + group.items.filter(item => item.complete).length,
        0
    );
    progressEl.innerHTML = `<strong>${complete} of ${total} complete</strong>`;
    checklistEl.innerHTML = groups.map(group => `
        <div class="goal-brief-checklist-group">
          <div class="goal-brief-checklist-group__title">${_escapeHtml(group.group)}</div>
          ${group.items.map(item => `
            <div class="goal-brief-checklist-row ${item.complete ? "goal-brief-checklist-row--complete" : "goal-brief-checklist-row--missing"}">
              <div class="goal-brief-checklist-row__main">
                <span>${_escapeHtml(item.label)}</span>
                <strong>${_escapeHtml(item.value || "Missing")}</strong>
              </div>
              <button type="button" onclick="insertGoalBriefReply('${_escapeHtml(item.template)}')">Insert</button>
            </div>
          `).join("")}
        </div>
    `).join("");
}
```

- [ ] **Step 4: Wire the checklist renderer into response rendering**

Update `_renderGoalBriefSummary(summary)` so it only handles the legacy compact rows when there is no `brief`; then call the checklist renderer from `_renderGoalBriefResponse`.

Use this minimal replacement:

```javascript
function _renderGoalBriefSummary(summary) {
    const rows = Array.isArray(summary?.rows) ? summary.rows : [];
    if (!rows.length) {
        _renderGoalBriefChecklist(null);
        return;
    }
    _renderGoalBriefChecklist(_goalBriefCurrent);
}
```

Keep this existing call in `_renderGoalBriefResponse`:

```javascript
_renderGoalBriefSummary(data.summary);
```

- [ ] **Step 5: Run the route tests and verify they pass**

Run:

```bash
python -m pytest tests/test_goal_brief_routes.py -q
```

Expected: all tests in `tests/test_goal_brief_routes.py` pass.

---

### Task 3: Checklist Styling

**Files:**
- Modify: `web/static/style.css`
- Test: `tests/test_goal_brief_routes.py`

- [ ] **Step 1: Add checklist CSS inside the Goal Brief panel section**

Add these rules after `.goal-brief-summary-status--ready`:

```css
.goal-brief-progress {
    padding-bottom: 8px;
    border-bottom: 1px solid var(--color-border);
    color: #fbbf24;
}

.goal-brief-checklist {
    display: grid;
    gap: 10px;
}

.goal-brief-checklist-empty {
    color: var(--color-text-muted);
    font-size: 12px;
}

.goal-brief-checklist-group {
    display: grid;
    gap: 6px;
}

.goal-brief-checklist-group__title {
    color: var(--color-text-muted);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}

.goal-brief-checklist-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
    align-items: center;
    padding: 8px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-surface-2);
}

.goal-brief-checklist-row--complete {
    border-color: #166534;
}

.goal-brief-checklist-row--missing {
    border-color: #7f1d1d;
}

.goal-brief-checklist-row__main {
    min-width: 0;
    display: grid;
    gap: 3px;
}

.goal-brief-checklist-row__main span {
    color: var(--color-text-muted);
    font-size: 12px;
}

.goal-brief-checklist-row__main strong {
    font-size: 12px;
    font-weight: 600;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

.goal-brief-checklist-row--missing strong {
    color: #fca5a5;
}

.goal-brief-checklist-row button {
    padding: 4px 8px;
    font-size: 11px;
}
```

- [ ] **Step 2: Keep existing summary row CSS for compatibility**

Do not delete `.goal-brief-summary-row` styles in this task. They are harmless, and keeping them reduces risk if older markup appears during browser cache transitions.

- [ ] **Step 3: Run the route tests again**

Run:

```bash
python -m pytest tests/test_goal_brief_routes.py -q
```

Expected: all tests pass.

---

### Task 4: Verification And Commit

**Files:**
- Modify: `tests/test_goal_brief_routes.py`
- Modify: `web/templates/index.html`
- Modify: `web/static/style.css`

- [ ] **Step 1: Run focused backend and route tests**

Run:

```bash
python -m pytest tests/test_goal_brief.py tests/test_goal_brief_routes.py -q
```

Expected: all tests pass. The core tests confirm the saved schema is unchanged; the route tests confirm the guided checklist UI is present.

- [ ] **Step 2: Start the local app if manual browser verification is part of the execution**

Run:

```bash
python web/app.py
```

Expected: Flask starts and prints the local URL. If the port is already in use, use the URL printed by the running process or start on another available port using the app's existing convention.

- [ ] **Step 3: Manually verify the Goal Brief tab**

Open the app in the in-app Browser and check:

- The Goal Brief tab shows the checklist empty state before starting.
- Starting a brief changes progress to `1 of 7 complete` when only the goal exists.
- Clicking `Insert` on a missing row appends the matching labeled template to the reply textarea.
- Sending a reply with `problem_type`, `expected_result`, and `validation_command` updates the relevant rows.
- Raw details remain collapsed below the primary checklist.

- [ ] **Step 4: Commit the implementation**

Run:

```bash
git add tests/test_goal_brief_routes.py web/templates/index.html web/static/style.css
git commit -m "Add guided goal brief checklist"
```

Expected: one commit containing only the test, template, and CSS changes.
