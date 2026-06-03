# Phase 11-prep-cleanup-b2b: Lesson Merge/Dedupe UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lesson duplicate hints, merge select, merge preview/create, archive, and archived/superseded visibility toggles to the Memory/Lessons tab UI.

**Architecture:** All changes are additive edits inside `web/templates/index.html` — HTML structure additions in the lessons section plus inline JS additions/replacements. One new test file reads the template as text. No new Python files, no route changes.

**Tech Stack:** HTML/JS (inline in Jinja2 template), pytest (text-grep tests), existing Flask routes `/lessons/duplicates`, `/lessons/merge/preview`, `/lessons/merge/create`, `/lessons/archive`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `web/templates/index.html` | Modify | All HTML + JS changes (lessons section, lines ~877–917 and ~3158–3447) |
| `tests/test_web_ui_lesson_merge_controls.py` | Create | 13 text-grep contract tests |

---

### Task 1: Write the failing test file

**Files:**
- Create: `tests/test_web_ui_lesson_merge_controls.py`

- [ ] **Step 1.1: Create the test file**

```python
"""Phase 11-prep-cleanup-b2b: Lesson Merge/Dedupe UI contract tests.

Read-only: parses index.html as text. Imports nothing from the application.
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
_TMPL = TEMPLATE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Merge select button exists
# ---------------------------------------------------------------------------

def test_merge_select_button_exists():
    assert 'id="mergeSelectToggle"' in _TMPL


# ---------------------------------------------------------------------------
# 2. Duplicate hints panel exists
# ---------------------------------------------------------------------------

def test_duplicate_hints_panel_exists():
    assert 'id="duplicateHintsPanel"' in _TMPL


# ---------------------------------------------------------------------------
# 3. Preview merge modal fields exist
# ---------------------------------------------------------------------------

def test_preview_merge_modal_fields_exist():
    assert 'id="mergePreviewTitle"' in _TMPL
    assert 'id="mergePreviewSummary"' in _TMPL


# ---------------------------------------------------------------------------
# 4. Create merged candidate button exists
# ---------------------------------------------------------------------------

def test_create_merged_candidate_button_exists():
    assert 'id="mergeCreateBtn"' in _TMPL


# ---------------------------------------------------------------------------
# 5. Show archived toggle exists
# ---------------------------------------------------------------------------

def test_show_archived_toggle_exists():
    assert 'id="showArchivedLessons"' in _TMPL


# ---------------------------------------------------------------------------
# 6. Show superseded toggle exists
# ---------------------------------------------------------------------------

def test_show_superseded_toggle_exists():
    assert 'id="showSupersededLessons"' in _TMPL


# ---------------------------------------------------------------------------
# 7. Archive button function defined
# ---------------------------------------------------------------------------

def test_archive_lesson_function_defined():
    assert "function archiveLessonById(" in _TMPL


# ---------------------------------------------------------------------------
# 8. Active archive blocked in UI contract
# ---------------------------------------------------------------------------

def test_active_archive_blocked_in_ui():
    assert "Active lessons cannot be archived" in _TMPL


# ---------------------------------------------------------------------------
# 9. JS calls b2a lesson routes
# ---------------------------------------------------------------------------

def test_js_calls_b2a_lesson_routes():
    assert "/lessons/duplicates" in _TMPL
    assert "/lessons/merge/preview" in _TMPL
    assert "/lessons/merge/create" in _TMPL
    assert "/lessons/archive" in _TMPL


# ---------------------------------------------------------------------------
# 10. Merge JS section does not call forbidden routes
# ---------------------------------------------------------------------------

def test_js_merge_section_does_not_call_forbidden_routes():
    FORBIDDEN = [
        "/benchmarks/run",
        "/dream/run",
        "/generate_patch",
        "/apply_patch",
    ]
    start_marker = "function loadDuplicateHints("
    end_marker = "function loadProposalRuns("
    assert start_marker in _TMPL, "loadDuplicateHints must be defined"
    start = _TMPL.index(start_marker)
    end = _TMPL.index(end_marker, start) if end_marker in _TMPL[start:] else len(_TMPL)
    section = _TMPL[start:end]
    for forbidden in FORBIDDEN:
        assert forbidden not in section, (
            f"Forbidden route {forbidden!r} found in lesson merge JS section"
        )


# ---------------------------------------------------------------------------
# 11. confirm_supersede_active is explicit, not automatic
# ---------------------------------------------------------------------------

def test_confirm_supersede_active_is_explicit_not_automatic():
    assert 'id="mergeConfirmSupersede"' in _TMPL
    assert "confirm_supersede_active: true" not in _TMPL
    assert "confirm_supersede_active:true" not in _TMPL


# ---------------------------------------------------------------------------
# 12. No unsafe inline onclick injection for lesson title/summary
# ---------------------------------------------------------------------------

def test_no_unsafe_inline_onclick_injection():
    # createMergedCandidate reads DOM — called with no args
    assert "createMergedCandidate()" in _TMPL
    # title/summary are never passed as inline onclick string params
    assert "createMergedCandidate('" not in _TMPL


# ---------------------------------------------------------------------------
# 13. AST self-guard: this module imports nothing heavy
# ---------------------------------------------------------------------------

def test_audit_module_has_no_forbidden_imports():
    source = Path(__file__).read_text(encoding="utf-8")
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
        assert top in allowed_top, f"unexpected import in b2b UI audit: {imp}"
```

- [ ] **Step 1.2: Run the tests — all should fail**

```
python -m pytest tests/test_web_ui_lesson_merge_controls.py -q --basetemp .fresh_tmp_b2b_ui
```

Expected: 12 FAILED (tests 1–12), 1 PASSED (test 13, the AST self-guard).

- [ ] **Step 1.3: Commit**

```
git add tests/test_web_ui_lesson_merge_controls.py
git commit -m "test: add Phase 11-prep-cleanup-b2b lesson merge UI contract tests (all failing)"
```

---

### Task 2: Add HTML filter bar additions + lessons header merge controls + duplicate hints panel

**Files:**
- Modify: `web/templates/index.html` (lessons section, lines ~877–917)

This task adds all static HTML. After this task tests 1, 2, 5, 6 will pass.

- [ ] **Step 2.1: Update the lessons-header and add mergeSelectBar**

Find this block (around line 878):
```html
            <div class="lessons-header">
              <strong>Lessons</strong>
            </div>
```

Replace it with:
```html
            <div class="lessons-header">
              <strong>Lessons</strong>
              <button type="button" class="sidebar-refresh" onclick="loadLessons(true)" title="Refresh lessons list">&#x27F3; Refresh</button>
              <button type="button" id="mergeSelectToggle" onclick="toggleMergeSelectMode()" title="Select 2+ lessons to merge">Merge lessons</button>
            </div>
            <div id="mergeSelectBar" class="lessons-merge-bar" hidden>
              <span id="mergeSelectCount">0 selected</span>
              <button type="button" id="previewMergeBtn" onclick="previewMergeSelected()" disabled>Preview merge</button>
              <button type="button" onclick="exitMergeSelectMode()">Cancel</button>
            </div>
```

- [ ] **Step 2.2: Add duplicate hints panel after lessons-note**

Find this block (around line 881):
```html
            <div class="lessons-note">
              Only <strong>Active</strong> lessons will be retrieval-eligible in future phases.
              Only Active lessons can be used as patch-prompt hints, and only when LESSON_RETRIEVAL_ENABLED=true.
            </div>
            <div class="lessons-filters"
```

Replace (keeping both divs, inserting between them):
```html
            <div class="lessons-note">
              Only <strong>Active</strong> lessons will be retrieval-eligible in future phases.
              Only Active lessons can be used as patch-prompt hints, and only when LESSON_RETRIEVAL_ENABLED=true.
            </div>
            <details id="duplicateHintsPanel" class="lesson-duplicate-hints"
                     ontoggle="if(this.open) loadDuplicateHints(false)">
              <summary class="lesson-duplicate-hints__summary">Duplicate hints</summary>
              <div class="lesson-duplicate-hints__toolbar">
                <button type="button" onclick="loadDuplicateHints(true)" title="Reload duplicate hints">&#x27F3; Refresh hints</button>
              </div>
              <div id="duplicateHintsList" class="lesson-duplicate-hints__list">
                <div class="health-empty">Open to load duplicate hints.</div>
              </div>
            </details>
            <div class="lessons-filters"
```

- [ ] **Step 2.3: Add kind filter and archived/superseded toggles to filter bar**

Find the closing `</select>` of `lessonFilterDifficulty` (around line 910) followed immediately by the closing `</div>` of `lessons-filters`:

```html
              <select id="lessonFilterDifficulty" class="lessons-filter-select"
                      onchange="_applyLessonFilters()" title="Filter by difficulty"
                      style="display:none">
                <option value="">All difficulties</option>
              </select>
            </div>
```

Replace with:
```html
              <select id="lessonFilterDifficulty" class="lessons-filter-select"
                      onchange="_applyLessonFilters()" title="Filter by difficulty"
                      style="display:none">
                <option value="">All difficulties</option>
              </select>
              <span class="lessons-filter-sep" aria-hidden="true">|</span>
              <select id="lessonFilterKind" class="lessons-filter-select"
                      onchange="_applyLessonFilters()" title="Filter by kind">
                <option value="">All kinds</option>
                <option value="lesson">lesson</option>
                <option value="anti-lesson">anti-lesson</option>
              </select>
              <span class="lessons-filter-sep" aria-hidden="true">|</span>
              <label class="lessons-filter-toggle" title="Show archived lessons (hidden by default)">
                <input type="checkbox" id="showArchivedLessons" onchange="_applyLessonFilters()"> Show archived
              </label>
              <label class="lessons-filter-toggle" title="Show superseded lessons (hidden by default)">
                <input type="checkbox" id="showSupersededLessons" onchange="_applyLessonFilters()"> Show superseded
              </label>
            </div>
```

- [ ] **Step 2.4: Run focused tests — tests 1, 2, 5, 6 should now pass**

```
python -m pytest tests/test_web_ui_lesson_merge_controls.py -q --basetemp .fresh_tmp_b2b_ui
```

Expected: tests 1, 2, 5, 6, 13 PASS; tests 3, 4, 7, 8, 9, 10, 11, 12 still FAIL.

- [ ] **Step 2.5: Compile check**

```
python -m compileall web tests
```

Expected: no syntax errors.

- [ ] **Step 2.6: Commit**

```
git add web/templates/index.html
git commit -m "feat(b2b): add lessons header merge button, duplicate hints panel, archived/superseded toggles"
```

---

### Task 3: Add new JS state variables, update `_applyLessonFilters`, update `_renderLessonCard`

**Files:**
- Modify: `web/templates/index.html` (JS section, lines ~3158 and ~3214 and ~3303)

After this task tests 7, 8 pass (archive button + "Active lessons cannot be archived" message). Tests 3, 4, 9, 10, 11, 12 still fail (those need functions added in later tasks).

- [ ] **Step 3.1: Add new state variables after `let _lessonsData = []`**

Find this block (around line 3158):
```javascript
let _lessonsCurrentStatus = "";
let _lessonsData = [];
```

Replace with:
```javascript
let _lessonsCurrentStatus = "";
let _lessonsData = [];
let _lessonsShowArchived = false;
let _lessonsShowSuperseded = false;
let _lessonsMergeSelectMode = false;
let _lessonsMergeSelected = new Set();
let _mergePreviewLessonIds = [];
let _duplicateHintsLoaded = false;
```

- [ ] **Step 3.2: Replace `_applyLessonFilters` with the extended version**

Find the entire `_applyLessonFilters` function (lines ~3214–3231):
```javascript
function _applyLessonFilters() {
    const lang = (document.getElementById("lessonFilterLanguage") || {}).value || "";
    const src  = (document.getElementById("lessonFilterSource")   || {}).value || "";
    const cat  = (document.getElementById("lessonFilterCategory") || {}).value || "";
    const diff = (document.getElementById("lessonFilterDifficulty") || {}).value || "";

    document.querySelectorAll("#lessonsList .lesson-card").forEach(card => {
        const lessonId = card.dataset.lessonId;
        const lesson = _lessonsData.find(l => l.id === lessonId);
        if (!lesson) { card.hidden = false; return; }
        let show = true;
        if (lang && _lessonLanguage(lesson) !== lang) show = false;
        if (src  && (lesson.source || "") !== src)    show = false;
        if (cat  && _lessonCategory(lesson) !== cat)  show = false;
        if (diff && _lessonDifficulty(lesson) !== diff) show = false;
        card.hidden = !show;
    });
}
```

Replace with:
```javascript
function _applyLessonFilters() {
    const lang = (document.getElementById("lessonFilterLanguage") || {}).value || "";
    const src  = (document.getElementById("lessonFilterSource")   || {}).value || "";
    const cat  = (document.getElementById("lessonFilterCategory") || {}).value || "";
    const diff = (document.getElementById("lessonFilterDifficulty") || {}).value || "";
    const kind = (document.getElementById("lessonFilterKind") || {}).value || "";
    const showArchived   = !!(document.getElementById("showArchivedLessons")   || {}).checked;
    const showSuperseded = !!(document.getElementById("showSupersededLessons") || {}).checked;

    document.querySelectorAll("#lessonsList .lesson-card").forEach(card => {
        const lessonId = card.dataset.lessonId;
        const lesson = _lessonsData.find(l => l.id === lessonId);
        if (!lesson) { card.hidden = false; return; }
        let show = true;
        if (lang && _lessonLanguage(lesson) !== lang) show = false;
        if (src  && (lesson.source || "") !== src)    show = false;
        if (cat  && _lessonCategory(lesson) !== cat)  show = false;
        if (diff && _lessonDifficulty(lesson) !== diff) show = false;
        if (kind && (lesson.kind || "lesson") !== kind) show = false;
        if (!showArchived   && lesson.archived)       show = false;
        if (!showSuperseded && lesson.superseded_by)  show = false;
        card.hidden = !show;
    });
}
```

- [ ] **Step 3.3: Replace `_renderLessonCard` with the extended version**

Find the entire `_renderLessonCard` function (lines ~3303–3369). Replace it with the version below. Key additions are: `archived`, `supersededBy`, `mergeSources` variables; archive button in the buttons array; new badges; merge checkbox.

```javascript
function _renderLessonCard(lesson) {
    const status = lesson.status || "candidate";
    const evaluation = lesson.evaluation || {};
    const promotion = evaluation.promotion || "unknown";
    const allowed = lesson.active_knowledge_allowed === true;
    const reasons = Array.isArray(evaluation.reasons) ? evaluation.reasons : [];
    const tags = Array.isArray(lesson.tags) ? lesson.tags.filter(t => typeof t === "string" && t) : [];
    const lessonScope = lesson.scope === "repo" ? "repo" : "global";
    const repoScopeId = typeof lesson.repo_scope_id === "string" ? lesson.repo_scope_id : "";
    const scopeLabel = lessonScope === "repo" && repoScopeId ? `repo:${repoScopeId}` : "global";
    const scopeClass = lessonScope === "repo" ? "lesson-scope-badge--repo" : "lesson-scope-badge--global";
    const archived = lesson.archived === true;
    const supersededBy = lesson.superseded_by || null;
    const mergeSources = Array.isArray(lesson.merge_sources) ? lesson.merge_sources : [];
    const mergeSourcesCount = mergeSources.length;

    const idAttr = _escapeHtml(lesson.id || "");
    const scopeAttr = _escapeHtml(lessonScope);
    const repoScopeAttr = _escapeHtml(repoScopeId);
    const buttons = [];
    if (lesson.source === "patch_proposal" && lesson.source_report) {
        buttons.push(`<button type="button" class="lesson-btn--secondary" onclick="viewLessonProposal('${idAttr}', '${scopeAttr}', '${repoScopeAttr}')" title="Open proposal.md for this lesson">View proposal</button>`);
    }
    if (status === "candidate") {
        buttons.push(`<button type="button" onclick="promoteLessonById('${idAttr}', '${scopeAttr}', '${repoScopeAttr}')" title="Move to active">Promote</button>`);
        buttons.push(`<button type="button" class="lesson-btn--danger" onclick="blockLessonById('${idAttr}', '${scopeAttr}', '${repoScopeAttr}')" title="Move to blocked">Block</button>`);
        buttons.push(`<button type="button" class="lesson-btn--secondary" onclick="archiveLessonById('${idAttr}', '${scopeAttr}', '${repoScopeAttr}')" title="Archive this lesson">Archive</button>`);
    } else if (status === "active") {
        buttons.push(`<button type="button" class="lesson-btn--danger" onclick="blockLessonById('${idAttr}', '${scopeAttr}', '${repoScopeAttr}')" title="Move to blocked">Block</button>`);
        buttons.push(`<button type="button" class="lesson-btn--secondary" disabled title="Active lessons cannot be archived; supersede through merge instead.">Archive</button>`);
    } else if (status === "blocked") {
        buttons.push(`<button type="button" class="lesson-btn--secondary" onclick="archiveLessonById('${idAttr}', '${scopeAttr}', '${repoScopeAttr}')" title="Archive this lesson">Archive</button>`);
    }

    const mergeCheckHtml = _lessonsMergeSelectMode
        ? `<label class="lesson-merge-check"><input type="checkbox" data-merge-id="${idAttr}" ${_lessonsMergeSelected.has(lesson.id) ? "checked" : ""} onchange="toggleMergeSelection(this)"> Select</label>`
        : "";

    const metaRows = [];
    if (lesson.source) metaRows.push(`<div><strong>source:</strong> ${_escapeHtml(lesson.source)}</div>`);
    if (lesson.source_report) metaRows.push(`<div><strong>report:</strong> ${_escapeHtml(lesson.source_report)}</div>`);
    if (lesson.case_name) metaRows.push(`<div><strong>case:</strong> ${_escapeHtml(lesson.case_name)}</div>`);
    metaRows.push(`<div><strong>promotion:</strong> ${_escapeHtml(promotion)}</div>`);
    metaRows.push(`<div><strong>active_knowledge_allowed:</strong> ${allowed ? "true" : "false"}</div>`);
    if (lesson.created_at) metaRows.push(`<div><strong>created:</strong> ${_escapeHtml(lesson.created_at)}</div>`);
    if (lesson.updated_at && lesson.updated_at !== lesson.created_at) {
        metaRows.push(`<div><strong>updated:</strong> ${_escapeHtml(lesson.updated_at)}</div>`);
    }

    const tagsHtml = tags.length
        ? `<div class="lesson-tags">${tags.map(t => `<span class="lesson-tag">${_escapeHtml(t)}</span>`).join("")}</div>`
        : "";

    const reasonsHtml = reasons.length
        ? `<details class="lesson-reasons"><summary>evaluation reasons (${reasons.length})</summary><ul>${reasons.map(r => `<li>${_escapeHtml(r)}</li>`).join("")}</ul></details>`
        : "";

    const summaryHtml = lesson.summary
        ? `<div class="lesson-summary">${_escapeHtml(lesson.summary)}</div>`
        : "";

    return `
      <div class="lesson-card lesson-card--${_escapeHtml(status)}" data-lesson-id="${idAttr}">
        ${mergeCheckHtml}
        <div class="lesson-card-header">
          <span class="lesson-title">${_escapeHtml(lesson.title || "Untitled lesson")}</span>
          <span class="lesson-badges">
            <span class="lesson-scope-badge ${scopeClass}" title="${_escapeHtml(scopeLabel)}">${_escapeHtml(scopeLabel)}</span>
            <span class="lesson-badge lesson-badge--${_escapeHtml(status)}">${_escapeHtml(status)}</span>
            ${archived ? `<span class="lesson-badge lesson-badge--archived">archived</span>` : ""}
            ${supersededBy ? `<span class="lesson-badge lesson-badge--superseded" title="Superseded by: ${_escapeHtml(supersededBy)}">superseded</span>` : ""}
            ${mergeSourcesCount > 0 ? `<span class="lesson-badge lesson-badge--merged" title="Merged from ${mergeSourcesCount} sources">merged from ${mergeSourcesCount}</span>` : ""}
          </span>
        </div>
        ${tagsHtml}
        <div class="lesson-meta">${metaRows.join("")}</div>
        ${summaryHtml}
        ${reasonsHtml}
        <div class="lesson-id"><code>${idAttr}</code></div>
        ${buttons.length ? `<div class="lesson-actions">${buttons.join(" ")}</div>` : ""}
      </div>
    `;
}
```

- [ ] **Step 3.4: Run focused tests — tests 7 and 8 should now pass**

```
python -m pytest tests/test_web_ui_lesson_merge_controls.py -q --basetemp .fresh_tmp_b2b_ui
```

Expected: tests 1, 2, 5, 6, 7, 8, 13 PASS; tests 3, 4, 9, 10, 11, 12 still FAIL.

- [ ] **Step 3.5: Compile check**

```
python -m compileall web tests
```

- [ ] **Step 3.6: Commit**

```
git add web/templates/index.html
git commit -m "feat(b2b): extend _renderLessonCard with archive button, merged/superseded/archived badges; extend _applyLessonFilters for kind/archived/superseded"
```

---

### Task 4: Add `archiveLessonById` JS function

**Files:**
- Modify: `web/templates/index.html` (JS, after `blockLessonById`)

Add the archive function directly after `blockLessonById` (which ends around line 3447).

- [ ] **Step 4.1: Add `archiveLessonById` after `blockLessonById`**

Find the closing brace of `blockLessonById`:
```javascript
        .catch(err => alert(`Network error: ${err}`));
}

// ============================================================
// Phase 5 Polish — Proposals sub-section (Memory tab)
```

Insert between the closing brace and the comment:
```javascript
        .catch(err => alert(`Network error: ${err}`));
}

function archiveLessonById(lessonId, scope, repoScopeId) {
    if (!lessonId) return;
    if (!confirm("Archive this lesson? It will be hidden from the default view.")) return;
    const payload = { lesson_id: lessonId };
    if (scope) payload.scope = scope;
    if (repoScopeId) payload.repo_scope_id = repoScopeId;
    const repo = _lessonRepoPath();
    if (repo) payload.repo_path = repo;
    fetch("/lessons/archive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
        .then(r => r.json())
        .then(data => {
            if (!data.ok) {
                alert(`❌ Archive failed: ${data.error || "unknown error"}`);
                return;
            }
            loadLessons(true);
        })
        .catch(err => alert(`Network error: ${err}`));
}

// ============================================================
// Phase 5 Polish — Proposals sub-section (Memory tab)
```

- [ ] **Step 4.2: Run focused tests — no change expected (7, 8 were already passing)**

```
python -m pytest tests/test_web_ui_lesson_merge_controls.py -q --basetemp .fresh_tmp_b2b_ui
```

Expected: same pass/fail as after Task 3.

- [ ] **Step 4.3: Commit**

```
git add web/templates/index.html
git commit -m "feat(b2b): add archiveLessonById JS function"
```

---

### Task 5: Add duplicate hints JS functions

**Files:**
- Modify: `web/templates/index.html` (JS, before `archiveLessonById`)

Insert `loadDuplicateHints`, `_renderDuplicateGroup`, and `selectGroupForMerge` immediately before `archiveLessonById` (which was just added in Task 4).

- [ ] **Step 5.1: Add duplicate hints functions before `archiveLessonById`**

Find the line `function archiveLessonById(lessonId, scope, repoScopeId) {` and insert before it:

```javascript
// ============================================================
// Phase 11-prep-cleanup-b2b — Duplicate hints
// ============================================================

function loadDuplicateHints(force) {
    if (_duplicateHintsLoaded && !force) return;
    _duplicateHintsLoaded = true;
    const listEl = document.getElementById("duplicateHintsList");
    if (listEl) listEl.innerHTML = '<div class="health-empty">Loading…</div>';
    const params = new URLSearchParams();
    const repo = _lessonRepoPath();
    if (repo) params.set("repo_path", repo);
    if (_lessonsCurrentStatus) params.set("status", _lessonsCurrentStatus);
    fetch("/lessons/duplicates?" + params.toString())
        .then(r => r.json())
        .then(data => {
            if (!data.ok) {
                if (listEl) listEl.innerHTML = `<div class="health-empty">❌ ${_escapeHtml(data.error || "Failed to load hints")}</div>`;
                return;
            }
            const groups = data.groups || [];
            if (!groups.length) {
                if (listEl) listEl.innerHTML = '<div class="health-empty">No duplicate groups found.</div>';
                return;
            }
            if (listEl) listEl.innerHTML = groups.map(_renderDuplicateGroup).join("");
        })
        .catch(err => {
            if (listEl) listEl.innerHTML = `<div class="health-empty">❌ Network error: ${_escapeHtml(String(err))}</div>`;
        });
}

function _renderDuplicateGroup(group) {
    const lessons = Array.isArray(group.lessons) ? group.lessons : [];
    const reason = group.reason || group.hint || "";
    const ids = lessons.map(l => l.id || "").filter(Boolean);
    const idsAttr = _escapeHtml(JSON.stringify(ids));
    const lessonRows = lessons.map(l => {
        const st = l.status || "candidate";
        return `<div class="dup-group__lesson">
            <span class="lesson-badge lesson-badge--${_escapeHtml(st)}">${_escapeHtml(st)}</span>
            <span class="dup-group__title">${_escapeHtml(l.title || "Untitled")}</span>
            <code class="dup-group__id">${_escapeHtml(l.id || "")}</code>
        </div>`;
    }).join("");
    return `<div class="dup-group">
        ${reason ? `<div class="dup-group__reason">${_escapeHtml(reason)}</div>` : ""}
        <div class="dup-group__lessons">${lessonRows}</div>
        <div class="dup-group__actions">
            <button type="button" data-merge-ids="${idsAttr}"
                    onclick="selectGroupForMerge(this)">Select group for merge</button>
        </div>
    </div>`;
}

function selectGroupForMerge(btn) {
    let ids;
    try { ids = JSON.parse(btn.dataset.mergeIds || "[]"); } catch (e) { return; }
    if (!Array.isArray(ids) || ids.length < 2) return;
    _lessonsMergeSelectMode = true;
    _lessonsMergeSelected = new Set(ids);
    _updateMergeSelectModeUI();
    loadLessons(true);
    const el = document.getElementById("lessonsList");
    if (el) el.scrollIntoView({ behavior: "smooth" });
}

```

- [ ] **Step 5.2: Run focused tests — test 9 (route check) should now pass**

```
python -m pytest tests/test_web_ui_lesson_merge_controls.py -q --basetemp .fresh_tmp_b2b_ui
```

Expected: tests 1, 2, 5, 6, 7, 8, 9, 13 PASS; tests 3, 4, 10, 11, 12 still FAIL (10 needs `loadDuplicateHints` present as start marker, which is now there; but merge/create routes aren't in the template yet).

Note: test 10 may still fail until `loadProposalRuns` can be found after `loadDuplicateHints` — this is fine at this stage.

- [ ] **Step 5.3: Commit**

```
git add web/templates/index.html
git commit -m "feat(b2b): add loadDuplicateHints, _renderDuplicateGroup, selectGroupForMerge"
```

---

### Task 6: Add merge select mode JS functions

**Files:**
- Modify: `web/templates/index.html` (JS, after `selectGroupForMerge`)

- [ ] **Step 6.1: Add merge select mode functions after `selectGroupForMerge`**

Find the line after `selectGroupForMerge`'s closing brace (the blank line before `function archiveLessonById`). Insert:

```javascript
function toggleMergeSelectMode() {
    if (_lessonsMergeSelectMode) {
        exitMergeSelectMode();
    } else {
        _lessonsMergeSelectMode = true;
        _lessonsMergeSelected = new Set();
        _updateMergeSelectModeUI();
        loadLessons(true);
    }
}

function exitMergeSelectMode() {
    _lessonsMergeSelectMode = false;
    _lessonsMergeSelected = new Set();
    _updateMergeSelectModeUI();
    loadLessons(true);
}

function _updateMergeSelectModeUI() {
    const toggle = document.getElementById("mergeSelectToggle");
    const bar = document.getElementById("mergeSelectBar");
    const countEl = document.getElementById("mergeSelectCount");
    const previewBtn = document.getElementById("previewMergeBtn");
    if (toggle) toggle.textContent = _lessonsMergeSelectMode ? "Cancel merge" : "Merge lessons";
    if (bar) {
        if (_lessonsMergeSelectMode) bar.removeAttribute("hidden");
        else bar.setAttribute("hidden", "");
    }
    const count = _lessonsMergeSelected.size;
    if (countEl) countEl.textContent = `${count} selected`;
    if (previewBtn) previewBtn.disabled = count < 2;
}

function toggleMergeSelection(checkbox) {
    const lessonId = checkbox.dataset.mergeId;
    if (!lessonId) return;
    if (checkbox.checked) {
        _lessonsMergeSelected.add(lessonId);
    } else {
        _lessonsMergeSelected.delete(lessonId);
    }
    _updateMergeSelectModeUI();
}

```

- [ ] **Step 6.2: Compile check**

```
python -m compileall web tests
```

- [ ] **Step 6.3: Commit**

```
git add web/templates/index.html
git commit -m "feat(b2b): add merge select mode JS (toggle, exit, UI update, checkbox handler)"
```

---

### Task 7: Add preview merge, open modal, and create merged candidate JS functions

**Files:**
- Modify: `web/templates/index.html` (JS, after `toggleMergeSelection`)

After this task all 12 contract tests pass.

- [ ] **Step 7.1: Add `previewMergeSelected`, `_openMergePreviewModal`, and `createMergedCandidate` after `toggleMergeSelection`**

Insert between `toggleMergeSelection`'s closing brace and `function archiveLessonById`:

```javascript
function previewMergeSelected() {
    const ids = [..._lessonsMergeSelected];
    if (ids.length < 2) return;
    openAppModal("Preview merge", '<div class="health-empty">Loading preview…</div>', "");
    const payload = { lesson_ids: ids };
    const repo = _lessonRepoPath();
    if (repo) payload.repo_path = repo;
    fetch("/lessons/merge/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
        .then(r => r.json())
        .then(data => {
            if (!data.ok) {
                openAppModal("Preview merge", `<div class="health-empty">❌ ${_escapeHtml(data.error || "Preview failed")}</div>`, "");
                return;
            }
            _openMergePreviewModal(data.preview, data.warnings || [], ids);
        })
        .catch(err => {
            openAppModal("Preview merge", `<div class="health-empty">❌ Network error: ${_escapeHtml(String(err))}</div>`, "");
        });
}

function _openMergePreviewModal(preview, warnings, lessonIds) {
    _mergePreviewLessonIds = lessonIds;
    const hasActive = warnings.some(w => w.includes("active"));
    const hasMixedKind = warnings.some(w => w.includes("kind") || w.includes("mix"));
    const warningsHtml = warnings.length
        ? `<div class="merge-preview__warnings">${warnings.map(w => `<div class="merge-preview__warning">⚠ ${_escapeHtml(w)}</div>`).join("")}</div>`
        : "";
    const activeConfirmHtml = hasActive
        ? `<label class="merge-preview__confirm"><input type="checkbox" id="mergeConfirmSupersede"> I confirm superseding active lesson(s)</label>`
        : `<input type="hidden" id="mergeConfirmSupersede" value="">`;
    const sourceRows = (preview.merge_sources || lessonIds).map(id => `<li><code>${_escapeHtml(id)}</code></li>`).join("");
    const tagsValue = Array.isArray(preview.tags) ? preview.tags.join(", ") : "";
    const bodyHtml = `
        <div class="merge-preview">
            ${warningsHtml}
            <div class="merge-preview__field">
                <label for="mergePreviewTitle">Title</label>
                <input type="text" id="mergePreviewTitle" class="merge-preview__input"
                       value="${_escapeHtml(preview.title || "")}">
            </div>
            <div class="merge-preview__field">
                <label for="mergePreviewSummary">Summary</label>
                <textarea id="mergePreviewSummary" class="merge-preview__textarea" rows="3">${_escapeHtml(preview.summary || "")}</textarea>
            </div>
            <div class="merge-preview__field">
                <label for="mergePreviewTags">Tags (comma-separated)</label>
                <input type="text" id="mergePreviewTags" class="merge-preview__input"
                       value="${_escapeHtml(tagsValue)}">
            </div>
            <div class="merge-preview__sources">
                <strong>Source lessons:</strong><ul>${sourceRows}</ul>
            </div>
            ${activeConfirmHtml}
        </div>`;
    const footerHtml = `
        <button type="button" id="mergeCreateBtn" onclick="createMergedCandidate()">Create merged candidate</button>
        <button type="button" onclick="closeAppModal()">Cancel</button>
        <div id="mergeCreateStatus" class="merge-create-status"></div>`;
    openAppModal("Preview merge", bodyHtml, footerHtml);
    if (hasMixedKind) {
        const btn = document.getElementById("mergeCreateBtn");
        if (btn) { btn.disabled = true; btn.title = "Cannot merge lessons of different kinds"; }
    }
}

function createMergedCandidate() {
    const titleEl = document.getElementById("mergePreviewTitle");
    const summaryEl = document.getElementById("mergePreviewSummary");
    const tagsEl = document.getElementById("mergePreviewTags");
    const confirmEl = document.getElementById("mergeConfirmSupersede");
    const statusEl = document.getElementById("mergeCreateStatus");
    const createBtn = document.getElementById("mergeCreateBtn");
    const title = (titleEl ? titleEl.value : "").trim();
    if (!title) {
        if (statusEl) { statusEl.textContent = "❌ Title is required."; statusEl.className = "merge-create-status merge-create-status--error"; }
        return;
    }
    const summary = summaryEl ? summaryEl.value : "";
    const tagsRaw = tagsEl ? tagsEl.value : "";
    const tags = tagsRaw.split(",").map(t => t.trim()).filter(Boolean);
    const confirmSupersede = confirmEl && confirmEl.type === "checkbox" ? confirmEl.checked : false;
    const payload = {
        lesson_ids: _mergePreviewLessonIds,
        title,
        summary,
        tags,
        confirm_supersede_active: confirmSupersede,
    };
    const repo = _lessonRepoPath();
    if (repo) payload.repo_path = repo;
    if (createBtn) createBtn.disabled = true;
    if (statusEl) { statusEl.textContent = "Creating…"; statusEl.className = "merge-create-status merge-create-status--running"; }
    fetch("/lessons/merge/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
        .then(r => r.json())
        .then(data => {
            if (!data.ok) {
                if (statusEl) { statusEl.textContent = `❌ ${_escapeHtml(data.error || "Merge failed")}`; statusEl.className = "merge-create-status merge-create-status--error"; }
                if (createBtn) createBtn.disabled = false;
                return;
            }
            if (statusEl) { statusEl.textContent = "✓ Merged candidate created."; statusEl.className = "merge-create-status merge-create-status--ok"; }
            exitMergeSelectMode();
            closeAppModal();
            loadLessons(true);
            loadDuplicateHints(true);
        })
        .catch(err => {
            if (statusEl) { statusEl.textContent = `❌ Network error: ${_escapeHtml(String(err))}`; statusEl.className = "merge-create-status merge-create-status--error"; }
            if (createBtn) createBtn.disabled = false;
        });
}

```

- [ ] **Step 7.2: Run focused tests — all 13 tests should now pass**

```
python -m pytest tests/test_web_ui_lesson_merge_controls.py -v --basetemp .fresh_tmp_b2b_ui
```

Expected: 13 PASSED.

If test 10 still fails, verify the JS block ordering: `loadDuplicateHints` must appear BEFORE `loadProposalRuns` in the template.

- [ ] **Step 7.3: Compile check**

```
python -m compileall web tests
```

Expected: Listing 0 files with syntax errors.

- [ ] **Step 7.4: Commit**

```
git add web/templates/index.html
git commit -m "feat(b2b): add previewMergeSelected, _openMergePreviewModal, createMergedCandidate"
```

---

### Task 8: Full validation

**Files:** none (validation only)

- [ ] **Step 8.1: Compile all**

```
python -m compileall web tests
```

Expected: no errors.

- [ ] **Step 8.2: Focused pytest**

```
python -m pytest tests/test_web_ui_lesson_merge_controls.py -q --basetemp .fresh_tmp_b2b_ui
```

Expected: 13 passed.

- [ ] **Step 8.3: Full pytest**

```
python -m pytest tests -q --basetemp .fresh_tmp_b2b_full
```

Expected: all green (same pass count as before this branch, no regressions).

- [ ] **Step 8.4: Benchmark check**

```
python -m benchmarks.run_benchmarks --check
```

Expected: 50 checked, 0 errors.

- [ ] **Step 8.5: Commit if any uncommitted changes remain**

```
git status
```

If clean, nothing to do. Otherwise commit any stragglers.

---

## Self-Review

**Spec coverage check:**

| Requirement | Task |
|---|---|
| Kind filter (All/Lesson/Anti-lesson) | Task 2.3 |
| Show archived toggle | Task 2.3 |
| Show superseded toggle | Task 2.3 |
| Default archived hidden | Task 3.2 (`_applyLessonFilters` — hides when checkbox unchecked) |
| Default superseded hidden | Task 3.2 |
| Duplicate hints panel collapsed | Task 2.2 (`<details>` collapses by default) |
| Duplicate hints refresh | Task 2.2 + Task 5 |
| Hint reasons, status badges | Task 5 (`_renderDuplicateGroup`) |
| Select group for merge button | Task 5 (`selectGroupForMerge`) |
| Merge lessons button | Task 2.1 (`mergeSelectToggle`) |
| Checkboxes in select mode | Task 3.3 (`_renderLessonCard` → `mergeCheckHtml`) |
| Selected count updates live | Task 6 (`_updateMergeSelectModeUI`) |
| Preview merge enabled only with 2+ | Task 6 (`previewBtn.disabled = count < 2`) |
| Cancel exits select mode | Task 6 (`exitMergeSelectMode`) |
| Preview merge modal → editable title | Task 7 (`mergePreviewTitle`) |
| Preview merge modal → editable summary | Task 7 (`mergePreviewSummary`) |
| Preview merge modal → editable tags | Task 7 (`mergePreviewTags`) |
| Source lesson list (read-only) | Task 7 (`sourceRows`) |
| Active source warning + confirm | Task 7 (`mergeConfirmSupersede` checkbox) |
| Mixed kind blocked | Task 7 (`hasMixedKind` disables create button) |
| No writes during preview | Task 7 (preview calls POST /merge/preview, not /merge/create) |
| Create merged candidate | Task 7 (`createMergedCandidate`) |
| Confirm supersede active → explicit | Task 7 (checkbox only) |
| Never send auto-promote | Task 7 (no `auto_promote` field in payload) |
| On success refresh lessons + hints | Task 7 (`loadLessons(true)` + `loadDuplicateHints(true)`) |
| Archive button for candidate/blocked | Task 3.3 |
| Archive disabled for active + tooltip | Task 3.3 |
| archived badge | Task 3.3 |
| superseded badge | Task 3.3 |
| merged from N badge | Task 3.3 |
| data-* attributes, no raw onclick strings | Tasks 3, 5, 7 (all user content via `_escapeHtml`, IDs via dataset) |
| No forbidden routes | Task 7 (verified by test 10) |
| confirm_supersede_active explicit | Task 7 (verified by test 11) |
| No inline unsafe onclick injection | Task 7 (verified by test 12) |

No gaps found.
