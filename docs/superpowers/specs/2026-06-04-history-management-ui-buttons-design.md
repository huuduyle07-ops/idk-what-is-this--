# History Management UI Buttons Design

**Phase:** 11-prep-cleanup-b1b  
**Date:** 2026-06-04  
**Depends on:** Phase 11-prep-cleanup-b1 (history_routes blueprint, session_store, benchmarks_view sidecars, dream_artifacts sidecars)

---

## Goal

Wire archive/pin/delete action buttons into the existing web UI for sessions, benchmark reports, and Dream runs. Uses the 7 history routes added in b1. No new routes, no model calls, no subprocess execution, no lesson/evidence changes.

## Architecture

All three list renderers (session list, benchmark list, Dream runs list) are extended with a `.history-actions` button row per card. Session list is converted from Jinja2-rendered to JS-rendered so button state can reflect live metadata. Archive toggles above each list control whether archived items are included. All mutations go through the existing `/history/*` endpoints via `fetch()` + `URLSearchParams`, matching the project's existing AJAX pattern.

---

## Section 1 — Session List

### Conversion: Jinja2 → JS-rendered

**Current state (lines 51–56 of `index.html`):**  
A `{% for s in sessions %}` loop renders `<a class="session-item">` links at template render time.

**After:**  
The loop block is replaced with a static container:
```html
<div id="sessionList"></div>
```
The `sessions` variable no longer needs to be passed from the Flask route (or can remain for backward compatibility — the JS renderer supersedes it).

### New function: `refreshSessionList(includeArchived = false)`

- Fetches `GET /history/sessions` (appends `?include_archived=1` when `includeArchived` is true)
- Clears `#sessionList`
- For each session object `s` in the response, renders:
  ```html
  <a class="session-item" href="/history/..." data-session-id="{s.id}">
    ... existing card content ...
    <div class="history-actions" data-ui-group="session-history-actions">
      <button class="history-btn" onclick="event.stopPropagation(); _archiveSession('{s.id}', {!s.archived})">
        {s.archived ? 'Unarchive' : 'Archive'}
      </button>
      <button class="history-btn history-btn--danger" onclick="event.stopPropagation(); _deleteSession('{s.id}')">
        Delete
      </button>
    </div>
  </a>
  ```
  All user-controlled strings rendered into onclick attributes must be passed through `_escapeHtml()`.
- Called once at `DOMContentLoaded`; re-called after every successful action

### Helper functions

**`_archiveSession(sessionId, archive)`**  
POSTs to `/history/session/archive` with `session_id`, `archived=true/false`. On success, re-calls `refreshSessionList(currentArchivedFlag)`.

**`_deleteSession(sessionId)`**  
Calls `prompt("Type DELETE_SESSION to confirm deletion:")` — if the returned value is not exactly `"DELETE_SESSION"`, aborts. Otherwise POSTs to `/history/session/delete` with `session_id`, `confirm=DELETE_SESSION`. On success, re-calls `refreshSessionList(currentArchivedFlag)`.

### Toggle

Placed immediately above `#sessionList`:
```html
<label class="history-toggle">
  <input type="checkbox" id="showArchivedSessions"
         onchange="refreshSessionList(this.checked)">
  Show archived sessions
</label>
```

### No pin for sessions

Sessions have no pin field in this phase. Archive and delete only.

---

## Section 2 — Benchmark List

### What changes

`_renderBenchmarkList()` (line ~5723) already renders cards into `#benchList`. Each card gets a `.history-actions` row appended with three buttons.

### Button set per benchmark card

```html
<div class="history-actions" data-ui-group="benchmark-history-actions">
  <button class="history-btn" onclick="event.stopPropagation(); _archiveBenchmark(repoPath, filename, !r.archived)">
    {r.archived ? 'Unarchive' : 'Archive'}
  </button>
  <button class="history-btn" onclick="event.stopPropagation(); _pinBenchmark(repoPath, filename, !r.pinned)">
    {r.pinned ? 'Unpin' : 'Pin'}
  </button>
  <button class="history-btn history-btn--danger" onclick="event.stopPropagation(); _deleteBenchmark(repoPath, filename, r.pinned)">
    Delete
  </button>
</div>
```

### Helper functions

**`_archiveBenchmark(repoPath, filename, archive)`**  
POSTs to `/history/benchmark/update` with `repo_path`, `filename`, `archived=true/false`. On success, re-calls `_renderBenchmarkList(currentArchivedFlag)`.

**`_pinBenchmark(repoPath, filename, pin)`**  
POSTs to `/history/benchmark/update` with `repo_path`, `filename`, `pinned=true/false`. On success, re-renders.

**`_deleteBenchmark(repoPath, filename, isPinned)`**  
- If `isPinned`: calls `alert("Unpin before deleting")` and returns immediately (no API call).
- Else: calls `prompt("Type DELETE_BENCHMARK_REPORT to confirm deletion:")`; if returned value !== `"DELETE_BENCHMARK_REPORT"`, aborts. Otherwise POSTs to `/history/benchmark/delete` with `repo_path`, `filename`, `confirm=DELETE_BENCHMARK_REPORT`. On success, re-renders.

### Toggle

Placed immediately above the benchmark list heading or container:
```html
<label class="history-toggle">
  <input type="checkbox" id="showArchivedBenchmarks"
         onchange="_renderBenchmarkList(this.checked)">
  Show archived reports
</label>
```

`_renderBenchmarkList(includeArchived)` passes `include_archived=1` to `/benchmarks/list` when the flag is true.

---

## Section 3 — Dream Runs List

### What changes

`refreshDreamRuns()` (line ~2790) renders items into `#dreamRuns`. Same shape as benchmarks.

### Button set per Dream run card

```html
<div class="history-actions" data-ui-group="dream-history-actions">
  <button class="history-btn" onclick="event.stopPropagation(); _archiveDreamRun(repoPath, r.date, r.run, !r.archived)">
    {r.archived ? 'Unarchive' : 'Archive'}
  </button>
  <button class="history-btn" onclick="event.stopPropagation(); _pinDreamRun(repoPath, r.date, r.run, !r.pinned)">
    {r.pinned ? 'Unpin' : 'Pin'}
  </button>
  <button class="history-btn history-btn--danger" onclick="event.stopPropagation(); _deleteDreamRun(repoPath, r.date, r.run, r.pinned)">
    Delete
  </button>
</div>
```

The `date` and `run` fields come from the report objects returned by `/dream/reports`.

### Helper functions

**`_archiveDreamRun(repoPath, date, run, archive)`**  
POSTs to `/history/dream/update` with `repo_path`, `date`, `run`, `archived=true/false`. On success, re-calls `refreshDreamRuns(currentArchivedFlag)`.

**`_pinDreamRun(repoPath, date, run, pin)`**  
POSTs to `/history/dream/update` with `repo_path`, `date`, `run`, `pinned=true/false`. On success, re-renders.

**`_deleteDreamRun(repoPath, date, run, isPinned)`**  
- If `isPinned`: `alert("Unpin before deleting")` and return.
- Else: `prompt("Type DELETE_DREAM_RUN to confirm deletion:")`; if returned value !== `"DELETE_DREAM_RUN"`, aborts. POSTs to `/history/dream/delete` with `repo_path`, `date`, `run`, `confirm=DELETE_DREAM_RUN`. On success, re-renders.

### Toggle

Placed immediately above `#dreamRuns` (near line 63):
```html
<label class="history-toggle">
  <input type="checkbox" id="showArchivedDreamRuns"
         onchange="refreshDreamRuns(this.checked)">
  Show archived runs
</label>
```

`refreshDreamRuns(includeArchived)` passes `include_archived=1` to `/dream/reports` when the flag is true.

---

## Section 4 — Test File

**File:** `tests/test_web_ui_history_controls.py`

Template/JS contract tests. Reads `web/templates/index.html` as text; no Flask client, no subprocess.

### Session controls (5 tests)
1. `refreshSessionList` function is defined in the template
2. `GET /history/sessions` endpoint path appears
3. `?include_archived=1` query string appears (toggle path)
4. `DELETE_SESSION` confirm string appears
5. `/history/session/archive` and `/history/session/delete` endpoint paths appear

### Benchmark controls (5 tests)
1. `showArchivedBenchmarks` toggle id is present
2. `DELETE_BENCHMARK_REPORT` confirm string appears
3. `/history/benchmark/update` endpoint path appears
4. `/history/benchmark/delete` endpoint path appears
5. Pinned guard phrase `Unpin before deleting` appears (checked near benchmark delete logic)

### Dream controls (5 tests)
1. `showArchivedDreamRuns` toggle id is present
2. `DELETE_DREAM_RUN` confirm string appears
3. `/history/dream/update` endpoint path appears
4. `/history/dream/delete` endpoint path appears
5. Pinned guard phrase `Unpin before deleting` appears (checked near dream delete logic)

### Execution fence (1 test)
- Confirms that the template does not invoke execution functions (`start_benchmark_run_async`, `start_overnight_async`, `run_gemini_request`, `promote_lesson`) from within the new `.history-actions` onclick attribute strings

**Total: 16 tests**

---

## AJAX Pattern

All fetches follow the existing project pattern:
```js
fetch(url, {
  method: "POST",
  headers: {"Content-Type": "application/x-www-form-urlencoded"},
  body: new URLSearchParams({...fields})
})
.then(r => r.json())
.then(data => { if (data.ok) { refresh(); } else { alert(data.error); } })
.catch(err => console.error(err));
```

## CSS

One new rule needed:
```css
.history-actions { display: flex; gap: 4px; margin-top: 4px; }
.history-btn { font-size: 11px; padding: 2px 6px; cursor: pointer; }
.history-btn--danger { color: #c00; }
```

Added inline in the `<style>` block at the top of `index.html`.

## Scope Boundaries

- No new Flask routes
- No model, subprocess, patch, benchmark-execution, or lesson-promotion calls
- No hard deletes (all deletions remain soft-delete as implemented in b1)
- No bulk-select UI
- No hover/dropdown menus

## Validation

```
python -m compileall core web tests
python -m pytest tests/test_web_ui_history_controls.py -q --basetemp .fresh_tmp_b1b
python -m pytest tests -q --basetemp .fresh_tmp_full
```

Expected: 16 UI contract tests pass, full suite green.
