# History Management UI Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire archive/pin/delete action buttons into the session, benchmark, and Dream run list UIs using the existing `/history/*` routes added in Phase b1.

**Architecture:** All three list renderers are extended with a `.history-actions` button row per card. The session list is converted from Jinja2-rendered to JS-rendered. Archive toggles above each list pass `include_archived=1` to existing fetch calls. All mutations use `fetch()` + `URLSearchParams` matching the project's existing AJAX pattern. Tests are template contract tests (read `index.html` as text, assert strings present).

**Tech Stack:** Vanilla JS (template literals, fetch, URLSearchParams), HTML5, Flask/Jinja2, Python/pytest (template text tests)

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `tests/test_web_ui_history_controls.py` | Create | 16 template contract tests |
| `web/static/style.css` | Modify (line ~1127) | Add `.history-actions`, `.history-btn`, `.history-btn--danger` rules |
| `web/templates/index.html` | Modify (lines 51-56) | Replace Jinja2 session loop with toggle + `<div id="sessionList">` |
| `web/templates/index.html` | Modify (between lines 62-63) | Insert Dream archived toggle above `#dreamRuns` |
| `web/templates/index.html` | Modify (between lines 466-467) | Insert benchmark archived toggle above `#benchList` |
| `web/templates/index.html` | Modify (before line 2782) | Add `refreshSessionList()`, `_archiveSession()`, `_deleteSession()` JS |
| `web/templates/index.html` | Modify (line 2742 DOMContentLoaded) | Add `refreshSessionList()` call |
| `web/templates/index.html` | Modify (line 2790) | Replace `refreshDreamRuns()` body + add `_archiveDreamRun()`, `_pinDreamRun()`, `_deleteDreamRun()` after |
| `web/templates/index.html` | Modify (line 5723) | Replace `_renderBenchmarkList()` body + add `_archiveBenchmark()`, `_pinBenchmark()`, `_deleteBenchmark()` after |
| `web/templates/index.html` | Modify (line 5970) | Replace `loadBenchmarksPanel()` body to read archive toggle |

---

## Task 1: Write test file (all 16 tests fail initially)

**Files:**
- Create: `tests/test_web_ui_history_controls.py`

- [ ] **Step 1: Create the test file**

```python
from __future__ import annotations
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


def _tmpl():
    return TEMPLATE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Session controls
# ---------------------------------------------------------------------------

def test_session_refresh_function_defined():
    assert "function refreshSessionList(" in _tmpl()


def test_session_history_endpoint_referenced():
    assert "/history/sessions" in _tmpl()


def test_session_include_archived_param():
    assert "include_archived=1" in _tmpl()


def test_session_delete_confirm_string():
    assert "DELETE_SESSION" in _tmpl()


def test_session_archive_and_delete_endpoints():
    t = _tmpl()
    assert "/history/session/archive" in t
    assert "/history/session/delete" in t


# ---------------------------------------------------------------------------
# Benchmark controls
# ---------------------------------------------------------------------------

def test_benchmark_archived_toggle_id():
    assert 'id="showArchivedBenchmarks"' in _tmpl()


def test_benchmark_delete_confirm_string():
    assert "DELETE_BENCHMARK_REPORT" in _tmpl()


def test_benchmark_update_endpoint():
    assert "/history/benchmark/update" in _tmpl()


def test_benchmark_delete_endpoint():
    assert "/history/benchmark/delete" in _tmpl()


def test_benchmark_pinned_guard_phrase():
    assert "Unpin before deleting" in _tmpl()


# ---------------------------------------------------------------------------
# Dream controls
# ---------------------------------------------------------------------------

def test_dream_archived_toggle_id():
    assert 'id="showArchivedDreamRuns"' in _tmpl()


def test_dream_delete_confirm_string():
    assert "DELETE_DREAM_RUN" in _tmpl()


def test_dream_update_endpoint():
    assert "/history/dream/update" in _tmpl()


def test_dream_delete_endpoint():
    assert "/history/dream/delete" in _tmpl()


def test_dream_pinned_guard_phrase():
    t = _tmpl()
    assert "/history/dream/delete" in t and "Unpin before deleting" in t


# ---------------------------------------------------------------------------
# Execution fence
# ---------------------------------------------------------------------------

def test_history_actions_do_not_invoke_execution_endpoints():
    """No line containing a /history/* route path may also invoke an
    execution function — history-actions handlers must never trigger runs."""
    EXEC_FNS = [
        "start_benchmark_run_async",
        "start_overnight_async",
        "run_gemini_request",
        "promote_lesson",
    ]
    HISTORY_ROUTES = [
        "/history/session",
        "/history/benchmark",
        "/history/dream",
    ]
    lines = _tmpl().splitlines()
    for line in lines:
        if any(route in line for route in HISTORY_ROUTES):
            for fn in EXEC_FNS:
                assert fn not in line, (
                    f"Execution fn '{fn}' found on same line as history route: {line!r}"
                )
```

- [ ] **Step 2: Run tests — verify all 16 fail (strings not yet in template)**

```
python -m pytest tests/test_web_ui_history_controls.py -q --basetemp .fresh_tmp_b1b
```

Expected: 15 failures on `AssertionError` (missing strings), 1 fence test passes (no history routes in template yet = no violations). At least 14 failures confirms the tests are exercising the right thing.

---

## Task 2: CSS rules

**Files:**
- Modify: `web/static/style.css` (after line 1127)

- [ ] **Step 1: Add history-actions CSS after the `.dream-run-item .session-meta` block (end of sidebar section)**

In `web/static/style.css`, find this block (ends around line 1127):
```css
.dream-run-item .session-meta {
    font-style: italic;
}
```

Insert immediately after:
```css

/* Phase b1b: per-card archive/pin/delete action row */
.history-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--color-text-muted);
    padding: 4px 0;
    cursor: pointer;
}

.history-actions {
    display: flex;
    gap: 4px;
    margin-top: 4px;
}

.history-btn {
    font-size: 11px;
    padding: 2px 6px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 3px;
    cursor: pointer;
    color: var(--color-text-muted);
}

.history-btn--danger {
    color: #c00;
}

.session-item--archived {
    opacity: 0.6;
}
```

- [ ] **Step 2: Compile-check (no Python changes, just verify file is valid by running compileall)**

```
python -m compileall core web tests
```

Expected: `Compiling...` for each .py, no errors.

- [ ] **Step 3: Commit**

```
git add web/static/style.css tests/test_web_ui_history_controls.py
git commit -m "test+css: add history-controls contract tests and history-actions CSS"
```

---

## Task 3: Session list — HTML + JS

**Files:**
- Modify: `web/templates/index.html` (lines 51–56 HTML, before line 2782 JS, DOMContentLoaded at line 2742)

- [ ] **Step 1: Replace the Jinja2 session loop (lines 51–56)**

Find this exact block in `index.html`:
```html
        {% for s in sessions %}
        <a class="session-item" href="{{ url_for('load_session', session_id=s.id) }}">
            <div class="session-title">{{ s.title }}</div>
            <div class="session-meta">{{ s.web_mode|default('instant') }} / {{ s.mode }} - {{ s.created_at }}</div>
        </a>
        {% endfor %}
```

Replace with:
```html
        <label class="history-toggle">
          <input type="checkbox" id="showArchivedSessions"
                 onchange="refreshSessionList()">
          Show archived sessions
        </label>
        <div id="sessionList"></div>
```

- [ ] **Step 2: Add session JS functions before line 2782 (`// --- Sidebar: past dream runs`)**

Find this comment (line ~2782):
```js
// --- Sidebar: past dream runs ------------------------------
```

Insert immediately BEFORE it:
```js
// --- Sidebar: session list --------------------------------
function refreshSessionList() {
    const toggle = document.getElementById("showArchivedSessions");
    const includeArchived = toggle ? toggle.checked : false;
    const url = includeArchived ? "/history/sessions?include_archived=1" : "/history/sessions";
    const container = document.getElementById("sessionList");
    if (!container) return;
    fetch(url)
        .then(r => r.json())
        .then(data => {
            const sessions = data.sessions || [];
            if (sessions.length === 0) {
                container.innerHTML = '<div class="session-item">No sessions yet.</div>';
                return;
            }
            container.innerHTML = sessions.map(s => `
                <a class="session-item ${s.archived ? 'session-item--archived' : ''}"
                   href="/session/${encodeURIComponent(s.id)}"
                   data-session-id="${_escapeHtml(s.id)}">
                  <div class="session-title">${_escapeHtml(s.title || '(untitled)')}</div>
                  <div class="session-meta">${_escapeHtml(s.web_mode || 'instant')} / ${_escapeHtml(s.mode || '')} - ${_escapeHtml(s.created_at || '')}</div>
                  <div class="history-actions" data-ui-group="session-history-actions">
                    <button class="history-btn"
                            onclick="event.stopPropagation(); _archiveSession('${_escapeHtml(s.id)}', ${!s.archived})">
                      ${s.archived ? 'Unarchive' : 'Archive'}
                    </button>
                    <button class="history-btn history-btn--danger"
                            onclick="event.stopPropagation(); _deleteSession('${_escapeHtml(s.id)}')">
                      Delete
                    </button>
                  </div>
                </a>
            `).join("");
        })
        .catch(err => {
            container.innerHTML = `<div class="session-item">Load error: ${_escapeHtml(String(err))}</div>`;
        });
}

function _archiveSession(sessionId, archive) {
    fetch("/history/session/archive", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({session_id: sessionId, archived: archive ? "true" : "false"})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { refreshSessionList(); }
        else { alert(data.error || "Archive failed"); }
    })
    .catch(err => console.error("_archiveSession error:", err));
}

function _deleteSession(sessionId) {
    const input = prompt("Type DELETE_SESSION to confirm deletion:");
    if (input !== "DELETE_SESSION") return;
    fetch("/history/session/delete", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({session_id: sessionId, confirm: "DELETE_SESSION"})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { refreshSessionList(); }
        else { alert(data.error || "Delete failed"); }
    })
    .catch(err => console.error("_deleteSession error:", err));
}

```

- [ ] **Step 3: Add `refreshSessionList()` call in DOMContentLoaded**

Find this line inside the DOMContentLoaded block (line ~2748):
```js
    refreshDreamRuns();
```

Insert `refreshSessionList();` immediately before it:
```js
    refreshSessionList();
    refreshDreamRuns();
```

- [ ] **Step 4: Run session contract tests — 5 should pass**

```
python -m pytest tests/test_web_ui_history_controls.py -k "session" -q --basetemp .fresh_tmp_b1b
```

Expected: 5 passed (`test_session_*`)

- [ ] **Step 5: Commit**

```
git add web/templates/index.html
git commit -m "feat: convert session list to JS-rendered with archive/delete buttons"
```

---

## Task 4: Benchmark list — HTML + JS

**Files:**
- Modify: `web/templates/index.html` (lines 466-467 HTML, line ~5723 `_renderBenchmarkList`, line ~5970 `loadBenchmarksPanel`)

- [ ] **Step 1: Add benchmark archived toggle above `#benchList`**

Find this block (lines ~464-468):
```html
              <div class="bench-sidebar-header">
                <strong>Past runs</strong>
              </div>
              <div id="benchList" class="bench-list">
```

Replace with:
```html
              <div class="bench-sidebar-header">
                <strong>Past runs</strong>
              </div>
              <label class="history-toggle">
                <input type="checkbox" id="showArchivedBenchmarks"
                       onchange="loadBenchmarksPanel(true)">
                Show archived reports
              </label>
              <div id="benchList" class="bench-list">
```

- [ ] **Step 2: Replace `_renderBenchmarkList(reports)` body (line ~5723)**

Find this function (lines ~5723-5739):
```js
function _renderBenchmarkList(reports) {
    const list = document.getElementById("benchList");
    if (!list) return;
    if (!reports || reports.length === 0) {
        list.innerHTML = `<div class="health-empty">No reports in .agent/benchmarks/.</div>`;
        return;
    }
    list.innerHTML = reports.map(r => `
        <div class="bench-list-item ${r.filename === _benchActiveFilename ? "is-active" : ""}"
             onclick="viewBenchmarkReport('${_escapeHtml(r.filename)}')">
            <div class="bench-list-item-date">${_benchFmtDate(r.timestamp_iso)}</div>
            <div class="bench-list-item-summary">
                ${r.passed}/${r.total} / ${_benchFmtRate(r.success_rate)} / ${(r.duration_sec || 0).toFixed(1)}s / ${_benchFmtCost(r.total_estimated_cost_usd)}
            </div>
        </div>
    `).join("");
}
```

Replace with:
```js
function _renderBenchmarkList(reports) {
    const list = document.getElementById("benchList");
    if (!list) return;
    if (!reports || reports.length === 0) {
        list.innerHTML = `<div class="health-empty">No reports in .agent/benchmarks/.</div>`;
        return;
    }
    const repo = document.querySelector("input[name='repo_path']")?.value.trim() || "";
    list.innerHTML = reports.map(r => `
        <div class="bench-list-item ${r.filename === _benchActiveFilename ? "is-active" : ""}"
             onclick="viewBenchmarkReport('${_escapeHtml(r.filename)}')">
            <div class="bench-list-item-date">${_benchFmtDate(r.timestamp_iso)}</div>
            <div class="bench-list-item-summary">
                ${r.passed}/${r.total} / ${_benchFmtRate(r.success_rate)} / ${(r.duration_sec || 0).toFixed(1)}s / ${_benchFmtCost(r.total_estimated_cost_usd)}
            </div>
            <div class="history-actions" data-ui-group="benchmark-history-actions">
                <button class="history-btn"
                        onclick="event.stopPropagation(); _archiveBenchmark('${_escapeHtml(repo)}', '${_escapeHtml(r.filename)}', ${!r.archived})">
                    ${r.archived ? 'Unarchive' : 'Archive'}
                </button>
                <button class="history-btn"
                        onclick="event.stopPropagation(); _pinBenchmark('${_escapeHtml(repo)}', '${_escapeHtml(r.filename)}', ${!r.pinned})">
                    ${r.pinned ? 'Unpin' : 'Pin'}
                </button>
                <button class="history-btn history-btn--danger"
                        onclick="event.stopPropagation(); _deleteBenchmark('${_escapeHtml(repo)}', '${_escapeHtml(r.filename)}', ${!!r.pinned})">
                    Delete
                </button>
            </div>
        </div>
    `).join("");
}
```

- [ ] **Step 3: Add benchmark helper functions immediately after `_renderBenchmarkList` closing brace**

Find the line immediately after the new `_renderBenchmarkList` closing `}` (the function ends right before `// Phase 12.8a: presentation evidence pack helpers.`):

Insert:
```js
function _archiveBenchmark(repoPath, filename, archive) {
    fetch("/history/benchmark/update", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({repo_path: repoPath, filename, archived: archive ? "true" : "false"})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { loadBenchmarksPanel(true); }
        else { alert(data.error || "Archive failed"); }
    })
    .catch(err => console.error("_archiveBenchmark error:", err));
}

function _pinBenchmark(repoPath, filename, pin) {
    fetch("/history/benchmark/update", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({repo_path: repoPath, filename, pinned: pin ? "true" : "false"})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { loadBenchmarksPanel(true); }
        else { alert(data.error || "Pin failed"); }
    })
    .catch(err => console.error("_pinBenchmark error:", err));
}

function _deleteBenchmark(repoPath, filename, isPinned) {
    if (isPinned) { alert("Unpin before deleting"); return; }
    const input = prompt("Type DELETE_BENCHMARK_REPORT to confirm deletion:");
    if (input !== "DELETE_BENCHMARK_REPORT") return;
    fetch("/history/benchmark/delete", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({repo_path: repoPath, filename, confirm: "DELETE_BENCHMARK_REPORT"})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { loadBenchmarksPanel(true); }
        else { alert(data.error || "Delete failed"); }
    })
    .catch(err => console.error("_deleteBenchmark error:", err));
}

```

- [ ] **Step 4: Modify `loadBenchmarksPanel` to read archive toggle (line ~5970)**

Find this function:
```js
function loadBenchmarksPanel(force = false) {
    if (_benchLoaded && !force) return;
    const list = document.getElementById("benchList");
    if (list) list.innerHTML = `<div class="health-empty">Loading…</div>`;
    const repo = document.querySelector("input[name='repo_path']")?.value.trim() || "";
    if (!repo) {
        if (list) list.innerHTML = `<div class="health-empty">Set a repo path in the form above first.</div>`;
        return;
    }
    refreshPresentationEvidence();
    refreshPromptCost();
    fetch(`/benchmarks/list?repo_path=${encodeURIComponent(repo)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                if (list) list.innerHTML = `<div class="health-empty">${_escapeHtml(data.error)}</div>`;
                return;
            }
            _renderBenchmarkList(data.reports || []);
            _benchLoaded = true;
        })
        .catch(err => {
            if (list) list.innerHTML = `<div class="health-empty">Failed: ${_escapeHtml(err)}</div>`;
        });
}
```

Replace with:
```js
function loadBenchmarksPanel(force = false) {
    if (_benchLoaded && !force) return;
    const toggle = document.getElementById("showArchivedBenchmarks");
    const includeArchived = toggle ? toggle.checked : false;
    const list = document.getElementById("benchList");
    if (list) list.innerHTML = `<div class="health-empty">Loading…</div>`;
    const repo = document.querySelector("input[name='repo_path']")?.value.trim() || "";
    if (!repo) {
        if (list) list.innerHTML = `<div class="health-empty">Set a repo path in the form above first.</div>`;
        return;
    }
    refreshPresentationEvidence();
    refreshPromptCost();
    const benchUrl = `/benchmarks/list?repo_path=${encodeURIComponent(repo)}${includeArchived ? '&include_archived=1' : ''}`;
    fetch(benchUrl)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                if (list) list.innerHTML = `<div class="health-empty">${_escapeHtml(data.error)}</div>`;
                return;
            }
            _renderBenchmarkList(data.reports || []);
            _benchLoaded = true;
        })
        .catch(err => {
            if (list) list.innerHTML = `<div class="health-empty">Failed: ${_escapeHtml(err)}</div>`;
        });
}
```

- [ ] **Step 5: Run benchmark contract tests — 5 + fence should pass**

```
python -m pytest tests/test_web_ui_history_controls.py -k "benchmark or execution" -q --basetemp .fresh_tmp_b1b
```

Expected: 6 passed (5 benchmark + 1 fence)

- [ ] **Step 6: Commit**

```
git add web/templates/index.html
git commit -m "feat: add archive/pin/delete buttons to benchmark list"
```

---

## Task 5: Dream runs list — HTML + JS

**Files:**
- Modify: `web/templates/index.html` (between lines 62-63 HTML, line ~2790 `refreshDreamRuns`)

- [ ] **Step 1: Add Dream archived toggle above `#dreamRuns`**

Find this block (lines ~58-65):
```html
        <h3 class="sidebar-section-heading">
          Dream runs
          <button type="button" class="sidebar-refresh"
                  onclick="refreshDreamRuns()" title="Reload dream-run list">⟳</button>
        </h3>
        <div id="dreamRuns" class="dream-runs">
```

Replace with:
```html
        <h3 class="sidebar-section-heading">
          Dream runs
          <button type="button" class="sidebar-refresh"
                  onclick="refreshDreamRuns()" title="Reload dream-run list">⟳</button>
        </h3>
        <label class="history-toggle">
          <input type="checkbox" id="showArchivedDreamRuns"
                 onchange="refreshDreamRuns()">
          Show archived runs
        </label>
        <div id="dreamRuns" class="dream-runs">
```

- [ ] **Step 2: Replace `refreshDreamRuns()` body (line ~2790)**

Find the full function (lines ~2790-2834):
```js
function refreshDreamRuns() {
    const repoEl = document.querySelector("input[name='repo_path']");
    const repo = repoEl ? repoEl.value.trim() : "";
    const container = document.getElementById("dreamRuns");
    if (!container) return;

    if (!repo) {
        container.innerHTML = '<div class="dream-runs-empty">Set a repo path to load.</div>';
        return;
    }

    fetch(`/dream/reports?repo_path=${encodeURIComponent(repo)}`)
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            container.innerHTML = `<div class="dream-runs-empty">${data.error}</div>`;
            return;
        }
        const reports = data.reports || [];
        if (reports.length === 0) {
            container.innerHTML = '<div class="dream-runs-empty">No dream runs yet.</div>';
            return;
        }
        container.innerHTML = reports.map(r => {
            const meta = [
                `${r.item_count} item${r.item_count === 1 ? "" : "s"}`,
                r.patch_style || "",
                _statusesPretty(r.statuses),
            ].filter(Boolean).join(" · ");
            // Slice γ.3.1: show run_id (HHMMSS-run) when present, fall back
            // to just date for legacy runs.
            const label = r.run_id ? `${r.date} · ${_escapeHtml(r.run_id)}` : r.date;
            const runArg = r.run_id ? `'${r.run_id}'` : "''";
            return `
              <a class="session-item dream-run-item" href="javascript:viewDreamRun('${r.date}', ${runArg})">
                <div class="session-title">${label}</div>
                <div class="session-meta">${meta}</div>
              </a>
            `;
        }).join("");
    })
    .catch(err => {
        container.innerHTML = `<div class="dream-runs-empty">Load error: ${err}</div>`;
    });
}
```

Replace with:
```js
function refreshDreamRuns() {
    const toggle = document.getElementById("showArchivedDreamRuns");
    const includeArchived = toggle ? toggle.checked : false;
    const repoEl = document.querySelector("input[name='repo_path']");
    const repo = repoEl ? repoEl.value.trim() : "";
    const container = document.getElementById("dreamRuns");
    if (!container) return;

    if (!repo) {
        container.innerHTML = '<div class="dream-runs-empty">Set a repo path to load.</div>';
        return;
    }

    const dreamUrl = `/dream/reports?repo_path=${encodeURIComponent(repo)}${includeArchived ? '&include_archived=1' : ''}`;
    fetch(dreamUrl)
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            container.innerHTML = `<div class="dream-runs-empty">${data.error}</div>`;
            return;
        }
        const reports = data.reports || [];
        if (reports.length === 0) {
            container.innerHTML = '<div class="dream-runs-empty">No dream runs yet.</div>';
            return;
        }
        container.innerHTML = reports.map(r => {
            const meta = [
                `${r.item_count} item${r.item_count === 1 ? "" : "s"}`,
                r.patch_style || "",
                _statusesPretty(r.statuses),
            ].filter(Boolean).join(" · ");
            // Slice γ.3.1: show run_id (HHMMSS-run) when present, fall back
            // to just date for legacy runs.
            const label = r.run_id ? `${r.date} · ${_escapeHtml(r.run_id)}` : r.date;
            const runArg = r.run_id ? `'${r.run_id}'` : "''";
            const repoEsc = _escapeHtml(repo);
            const dateEsc = _escapeHtml(r.date);
            const runIdEsc = _escapeHtml(r.run_id || "");
            return `
              <a class="session-item dream-run-item ${r.archived ? 'session-item--archived' : ''}"
                 href="javascript:viewDreamRun('${r.date}', ${runArg})">
                <div class="session-title">${label}</div>
                <div class="session-meta">${meta}</div>
                <div class="history-actions" data-ui-group="dream-history-actions">
                  <button class="history-btn"
                          onclick="event.stopPropagation(); _archiveDreamRun('${repoEsc}', '${dateEsc}', '${runIdEsc}', ${!r.archived})">
                    ${r.archived ? 'Unarchive' : 'Archive'}
                  </button>
                  <button class="history-btn"
                          onclick="event.stopPropagation(); _pinDreamRun('${repoEsc}', '${dateEsc}', '${runIdEsc}', ${!r.pinned})">
                    ${r.pinned ? 'Unpin' : 'Pin'}
                  </button>
                  <button class="history-btn history-btn--danger"
                          onclick="event.stopPropagation(); _deleteDreamRun('${repoEsc}', '${dateEsc}', '${runIdEsc}', ${!!r.pinned})">
                    Delete
                  </button>
                </div>
              </a>
            `;
        }).join("");
    })
    .catch(err => {
        container.innerHTML = `<div class="dream-runs-empty">Load error: ${err}</div>`;
    });
}
```

- [ ] **Step 3: Add Dream helper functions immediately after the closing brace of `refreshDreamRuns`**

Find the line immediately after `refreshDreamRuns`'s closing `}` (the next function is `function viewDreamRun`):

Insert before `function viewDreamRun`:
```js
function _archiveDreamRun(repoPath, date, run, archive) {
    fetch("/history/dream/update", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({repo_path: repoPath, date, run, archived: archive ? "true" : "false"})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { refreshDreamRuns(); }
        else { alert(data.error || "Archive failed"); }
    })
    .catch(err => console.error("_archiveDreamRun error:", err));
}

function _pinDreamRun(repoPath, date, run, pin) {
    fetch("/history/dream/update", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({repo_path: repoPath, date, run, pinned: pin ? "true" : "false"})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { refreshDreamRuns(); }
        else { alert(data.error || "Pin failed"); }
    })
    .catch(err => console.error("_pinDreamRun error:", err));
}

function _deleteDreamRun(repoPath, date, run, isPinned) {
    if (isPinned) { alert("Unpin before deleting"); return; }
    const input = prompt("Type DELETE_DREAM_RUN to confirm deletion:");
    if (input !== "DELETE_DREAM_RUN") return;
    fetch("/history/dream/delete", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({repo_path: repoPath, date, run, confirm: "DELETE_DREAM_RUN"})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { refreshDreamRuns(); }
        else { alert(data.error || "Delete failed"); }
    })
    .catch(err => console.error("_deleteDreamRun error:", err));
}

```

- [ ] **Step 4: Run all 16 tests — all should pass**

```
python -m pytest tests/test_web_ui_history_controls.py -q --basetemp .fresh_tmp_b1b
```

Expected: 16 passed

- [ ] **Step 5: Commit**

```
git add web/templates/index.html
git commit -m "feat: add archive/pin/delete buttons to Dream run list with archived toggle"
```

---

## Task 6: Full validation

**Files:** None (validation only)

- [ ] **Step 1: Compile-check all Python**

```
python -m compileall core web tests
```

Expected: No errors.

- [ ] **Step 2: Run the UI contract test suite**

```
python -m pytest tests/test_web_ui_history_controls.py -q --basetemp .fresh_tmp_b1b
```

Expected: `16 passed`

- [ ] **Step 3: Run the full test suite**

```
python -m pytest tests -q --basetemp .fresh_tmp_full
```

Expected: Full suite green (existing tests from b1 still pass, no regressions).

- [ ] **Step 4: Commit**

If all tests pass and no uncommitted changes remain from validation:

```
git add -A
git status
```

If clean (all already committed in Tasks 2-5), done. If any stragglers:

```
git commit -m "chore: b1b history management UI buttons — full validation pass"
```
