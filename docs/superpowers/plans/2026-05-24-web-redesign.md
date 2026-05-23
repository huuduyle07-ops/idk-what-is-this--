# Web Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the C.A.T.T.U.S web UI with a 3-theme system, layout rebuild, keyboard shortcuts with custom keybinding editor, and an in-app README viewer — shipped in 4 independent phases.

**Architecture:** CSS custom properties drive theming via `data-theme` on `<body>`; a central `keybindings.js` module handles all keyboard navigation and persists user overrides to `localStorage`; a new Flask `/help` route renders `README.md` into the shared app modal.

**Tech Stack:** Flask/Jinja2, vanilla JS, CSS custom properties, Python `markdown` library

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `web/static/style.css` | **Rewrite** | Replace hardcoded colors with CSS variables; add 3 theme presets |
| `web/templates/index.html` | **Rebuild** | Cleaner layout, remove dead buttons, add theme selector + keybind editor to Settings tab, add `?` help button |
| `web/static/keybindings.js` | **Create** | Central keymap, `keydown` listener, localStorage persistence |
| `web/app.py` | **Modify** | Add `GET /help` route |
| `requirements.txt` | **Modify** | Add `markdown` |
| `tests/test_help_route.py` | **Create** | Tests for `/help` route |
| `tests/test_keybindings.py` | **Create** | Tests for conflict detection logic (pure JS tested via Flask test client or extracted to Python) |

---

## Phase 1 — CSS Theme System

### Task 1: Define CSS custom properties and 3 theme presets

**Files:**
- Modify: `web/static/style.css` (full rewrite of color/font values)

- [ ] **Step 1: Add CSS variable definitions at the top of `style.css`**

Replace the hardcoded `body { background: #0f172a; color: #e2e8f0; font-family: monospace; }` block with:

```css
/* ── Theme tokens ─────────────────────────────────────────── */
:root {
  /* Default: Modern Dev Tool (zinc/indigo) */
  --color-bg:          #09090b;
  --color-surface:     #18181b;
  --color-surface-2:   #09090b;
  --color-border:      #27272a;
  --color-text:        #fafafa;
  --color-text-muted:  #a1a1aa;
  --color-accent:      #6366f1;
  --color-accent-hov:  #4f46e5;
  --color-accent-fg:   #eef2ff;
  --color-danger:      #ef4444;
  --color-danger-bg:   #450a0a;
  --color-success:     #22c55e;
  --color-success-bg:  #052e16;
  --color-warning:     #f59e0b;
  --color-warning-bg:  #422006;
  --font-ui:           system-ui, -apple-system, sans-serif;
  --font-mono:         'Courier New', Consolas, monospace;
  --radius-sm:         4px;
  --radius-md:         6px;
  --radius-lg:         8px;
}

[data-theme="clean"] {
  --color-bg:          #0f172a;
  --color-surface:     #1e293b;
  --color-surface-2:   #0f172a;
  --color-border:      #334155;
  --color-text:        #e2e8f0;
  --color-text-muted:  #94a3b8;
  --color-accent:      #3b82f6;
  --color-accent-hov:  #2563eb;
  --color-accent-fg:   #eff6ff;
  --font-ui:           system-ui, -apple-system, sans-serif;
  --font-mono:         'Courier New', Consolas, monospace;
}

[data-theme="modern"] {
  /* same as :root — explicit for clarity */
  --color-bg:          #09090b;
  --color-surface:     #18181b;
  --color-surface-2:   #09090b;
  --color-border:      #27272a;
  --color-text:        #fafafa;
  --color-text-muted:  #a1a1aa;
  --color-accent:      #6366f1;
  --color-accent-hov:  #4f46e5;
  --color-accent-fg:   #eef2ff;
  --font-ui:           system-ui, -apple-system, sans-serif;
  --font-mono:         'Courier New', Consolas, monospace;
}

[data-theme="terminal"] {
  --color-bg:          #030712;
  --color-surface:     #0a0f1a;
  --color-surface-2:   #030712;
  --color-border:      #1f2937;
  --color-text:        #f9fafb;
  --color-text-muted:  #6b7280;
  --color-accent:      #10b981;
  --color-accent-hov:  #059669;
  --color-accent-fg:   #f0fdf4;
  --font-ui:           'Courier New', Consolas, monospace;
  --font-mono:         'Courier New', Consolas, monospace;
}
```

- [ ] **Step 2: Replace all hardcoded color values in `style.css` with variables**

Do a find-and-replace pass. Key mappings:

| Old value | New variable |
|---|---|
| `#0f172a` (bg) | `var(--color-bg)` |
| `#020617` (deeper bg) | `var(--color-bg)` |
| `#1e293b` (surface) | `var(--color-surface)` |
| `#111827` (surface alt) | `var(--color-surface)` |
| `#0f172a` (surface-2) | `var(--color-surface-2)` |
| `#334155`, `#1e293b` (borders) | `var(--color-border)` |
| `#e2e8f0` (text) | `var(--color-text)` |
| `#94a3b8`, `#64748b` (muted text) | `var(--color-text-muted)` |
| `#3b82f6` (accent) | `var(--color-accent)` |
| `#2563eb` (accent hover) | `var(--color-accent-hov)` |
| `monospace` (font-family on body) | `var(--font-ui)` |

Keep semantic overrides as-is (e.g. `.diff-add { background: #e6ffed }` — these are content colors, not theme colors).

- [ ] **Step 3: Update `body` rule to use variables**

```css
body {
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-ui);
}
```

- [ ] **Step 4: Commit**

```bash
git add web/static/style.css
git commit -m "feat(theme): CSS custom properties — 3 theme presets via data-theme"
```

---

### Task 2: Theme switcher UI and persistence JS

**Files:**
- Modify: `web/templates/index.html` (Settings tab section only)

- [ ] **Step 1: Add theme switcher markup inside the Settings workspace tab**

Find the `<div id="ws-settings"` section in `index.html`. Add this block at the top, before the existing `.health-section`:

```html
<!-- Theme selector -->
<div class="health-section theme-section">
  <div class="health-header">
    <strong>Appearance</strong>
  </div>
  <div class="theme-picker" role="group" aria-label="Choose theme">
    <button type="button" class="theme-chip" data-theme-pick="clean"
            onclick="setTheme('clean')">
      <span class="theme-chip__swatch theme-chip__swatch--clean"></span>
      Clean
    </button>
    <button type="button" class="theme-chip" data-theme-pick="modern"
            onclick="setTheme('modern')">
      <span class="theme-chip__swatch theme-chip__swatch--modern"></span>
      Modern
    </button>
    <button type="button" class="theme-chip" data-theme-pick="terminal"
            onclick="setTheme('terminal')">
      <span class="theme-chip__swatch theme-chip__swatch--terminal"></span>
      Terminal
    </button>
  </div>
</div>
```

- [ ] **Step 2: Add theme switcher CSS to `style.css`**

```css
/* ── Theme picker chips (Settings tab) ──────────────────────── */
.theme-section { margin-bottom: 16px; }

.theme-picker {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.theme-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 13px;
  transition: border-color 0.15s, color 0.15s;
}

.theme-chip:hover {
  border-color: var(--color-accent);
  color: var(--color-text);
}

.theme-chip--active {
  border-color: var(--color-accent);
  color: var(--color-text);
  background: var(--color-surface-2);
}

.theme-chip__swatch {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}

.theme-chip__swatch--clean    { background: #3b82f6; }
.theme-chip__swatch--modern   { background: #6366f1; }
.theme-chip__swatch--terminal { background: #10b981; }
```

- [ ] **Step 3: Add `setTheme()` JS function in `index.html` `<script>` block**

```js
// ── Theme persistence ──────────────────────────────────────
const THEME_KEY = 'cattus_theme';

function setTheme(name) {
  document.documentElement.setAttribute('data-theme', name);
  localStorage.setItem(THEME_KEY, name);
  document.querySelectorAll('.theme-chip').forEach(btn => {
    btn.classList.toggle('theme-chip--active', btn.dataset.themePick === name);
  });
}

(function initTheme() {
  const saved = localStorage.getItem(THEME_KEY) || 'modern';
  setTheme(saved);
})();
```

> Note: apply `data-theme` to `document.documentElement` (`<html>`) not `<body>` so the attribute selector `[data-theme="..."]` in CSS applies to the whole page.

- [ ] **Step 4: Verify theme switching works**

Start the Flask server: `python main.py --web`
Open `http://localhost:5000`, navigate to Settings tab, click each theme chip. Colors should change immediately. Refresh — active theme should persist.

- [ ] **Step 5: Commit**

```bash
git add web/templates/index.html web/static/style.css
git commit -m "feat(theme): theme switcher UI with localStorage persistence"
```

---

## Phase 2 — HTML Layout Rebuild

### Task 3: Sidebar cleanup and help button

**Files:**
- Modify: `web/templates/index.html` (sidebar section)

- [ ] **Step 1: Replace the sidebar brand block**

Find and replace the existing `.sidebar-brand` div:

```html
<!-- OLD -->
<div class="sidebar-brand">
  <div class="sidebar-brand__mark">AI</div>
  <div>
    <div class="sidebar-brand__name">Coding Agent</div>
    <div class="sidebar-brand__meta">Workspace</div>
  </div>
</div>

<!-- NEW -->
<div class="sidebar-brand">
  <div class="sidebar-brand__mark">AI</div>
  <div class="sidebar-brand__text">
    <div class="sidebar-brand__name">C.A.T.T.U.S</div>
    <div class="sidebar-brand__meta">Coding Agent</div>
  </div>
  <button type="button" class="sidebar-help-btn"
          onclick="openHelpModal()"
          title="How to use — opens README">?</button>
</div>
```

- [ ] **Step 2: Add sidebar help button CSS**

```css
.sidebar-brand__text { flex: 1; }

.sidebar-help-btn {
  width: 26px;
  height: 26px;
  padding: 0;
  border-radius: 50%;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  flex-shrink: 0;
  display: grid;
  place-items: center;
}

.sidebar-help-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
```

- [ ] **Step 3: Commit**

```bash
git add web/templates/index.html web/static/style.css
git commit -m "feat(layout): sidebar brand rename to CATTUS + help button"
```

---

### Task 4: Main form area — collapse controls, remove clutter

**Files:**
- Modify: `web/templates/index.html` (agent form section)

- [ ] **Step 1: Group repo path + project tag on one row**

Find the two `<input>` fields for `repo_path` and `project_tag` and wrap them:

```html
<div class="form-row">
  <input
    id="repoPathInput"
    type="text"
    name="repo_path"
    placeholder="Repo path or drag folder here"
    value="{{ current.repo_path if current else '' }}"
    required
    style="flex:2"
  >
  <input name="project_tag"
         value="{{ current.project_tag if current else '' }}"
         placeholder="Tag (auto)"
         style="flex:1" />
</div>
```

- [ ] **Step 2: Add `.form-row` CSS**

```css
.form-row {
  display: flex;
  gap: 8px;
  margin: 10px 0;
}

.form-row input {
  margin: 0;
  min-width: 0;
}
```

- [ ] **Step 3: Wrap `instant-run-controls` in a `<details>` collapse**

Replace the existing `<div class="instant-run-controls" ...>` with:

```html
<details class="instant-run-controls" data-mode-panel="instant-controls" open>
  <summary class="instant-run-summary">Options</summary>
  <!-- existing controls content unchanged -->
</details>
```

- [ ] **Step 4: Add summary CSS**

```css
.instant-run-summary {
  cursor: pointer;
  color: var(--color-text-muted);
  font-size: 12px;
  padding: 4px 0;
  list-style: none;
  user-select: none;
}

.instant-run-summary::-webkit-details-marker { display: none; }
.instant-run-summary::before { content: '▸ '; }
details[open] .instant-run-summary::before { content: '▾ '; }
```

- [ ] **Step 5: Replace the verbose `.margin-top-info` status line with a compact chip**

```html
<!-- OLD -->
<div class="margin-top-info">
  Current mode: {{ current.mode if current else 'none' }}
  · Vibecoding: {{ current.patch_style if current and current.patch_style else 'safe_minimal' }}
  · Code DNA: {{ 'ignored' if current and current.ignore_repo_dna else 'match repo' }}
</div>

<!-- NEW -->
{% if current %}
<div class="status-chip">
  <span class="status-chip__item">{{ current.mode or 'none' }}</span>
  <span class="status-chip__sep">·</span>
  <span class="status-chip__item">{{ current.patch_style or 'safe_minimal' }}</span>
  <span class="status-chip__sep">·</span>
  <span class="status-chip__item">{{ 'no-dna' if current.ignore_repo_dna else 'dna-on' }}</span>
</div>
{% endif %}
```

- [ ] **Step 6: Add status chip CSS**

```css
.status-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.status-chip__item {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
}

.status-chip__sep { color: var(--color-border); }
```

- [ ] **Step 7: Commit**

```bash
git add web/templates/index.html web/static/style.css
git commit -m "feat(layout): grouped form row, collapsible options, compact status chip"
```

---

### Task 5: Remove dead buttons + auto-refresh on tab focus

**Files:**
- Modify: `web/templates/index.html`

- [ ] **Step 1: Remove the `openObsidian()` button**

Delete this button from the Graph workspace tab:

```html
<!-- DELETE this line -->
<button type="button" onclick="openObsidian()">Open Obsidian Vault</button>
```

Also delete the `openObsidian()` JS function (search for `function openObsidian()`).

- [ ] **Step 2: Remove per-section `⟳ Refresh` buttons from Memory, Dream, Benchmarks tabs**

Delete these specific refresh buttons (keep the sidebar dream runs `⟳`):
- `<button type="button" class="sidebar-refresh" onclick="loadBenchmarksPanel(true)"...>⟳</button>` in bench sidebar
- `<button type="button" class="memory-refresh" onclick="refreshHandoffs()"...>⟳ Refresh</button>`
- `<button type="button" class="memory-refresh" onclick="refreshWorkerRuns()"...>⟳ Refresh</button>`
- `<button type="button" class="sidebar-refresh" onclick="loadProposalRuns(true)"...>⟳ Refresh</button>`
- `<button type="button" class="sidebar-refresh" onclick="loadLessons(true)"...>⟳ Refresh</button>`

- [ ] **Step 3: Add auto-refresh on tab focus in `showWorkspaceTab()`**

Find the `showWorkspaceTab` function and add refresh calls:

```js
function showWorkspaceTab(name) {
  document.querySelectorAll('.ws-content').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.ws-tab').forEach(t => t.classList.remove('ws-tab--active'));
  const panel = document.getElementById('ws-' + name);
  const tab   = document.getElementById('ws-tab-' + name);
  if (panel) panel.style.display = 'block';
  if (tab)   tab.classList.add('ws-tab--active');

  // Auto-refresh data when tab becomes active
  const autoLoad = {
    benchmarks: () => loadBenchmarksPanel(false),
    memory:     () => {
      loadProposalRuns(false);
      refreshHandoffs();
      refreshWorkerRuns();
      loadLessons(false);
    },
    dream:      () => { refreshDreamStatus(); loadPlanItems(false); },
    settings:   () => loadHealthPanel(false),
    graph:      () => {},  // graph only loads on explicit button click
  };
  if (autoLoad[name]) autoLoad[name]();
}
```

- [ ] **Step 4: Commit**

```bash
git add web/templates/index.html
git commit -m "feat(layout): remove dead buttons, auto-refresh on tab focus"
```

---

## Phase 3 — Keyboard Shortcuts + Custom Keybinding Editor

### Task 6: Create `keybindings.js` — keymap and navigation

**Files:**
- Create: `web/static/keybindings.js`
- Modify: `web/templates/index.html` (add `<script>` tag)

- [ ] **Step 1: Create `web/static/keybindings.js`**

```js
// keybindings.js — central keyboard shortcut system for CATTUS
(function () {
  'use strict';

  const STORAGE_KEY = 'cattus_keybindings';

  // Default keymap: action_id -> { key, ctrl, shift, alt, label }
  const DEFAULT_MAP = {
    tab_chat:        { key: '1',     ctrl: true,  shift: false, alt: false, label: 'Chat / Patch' },
    tab_benchmarks:  { key: 'k',     ctrl: true,  shift: false, alt: false, label: 'Benchmarks' },
    tab_dream:       { key: '2',     ctrl: true,  shift: false, alt: false, label: 'Dream' },
    tab_memory:      { key: 'm',     ctrl: true,  shift: false, alt: false, label: 'Memory' },
    tab_graph:       { key: 'g',     ctrl: true,  shift: false, alt: false, label: 'Graph' },
    tab_settings:    { key: ',',     ctrl: true,  shift: false, alt: false, label: 'Settings' },
    run_submit:      { key: 'Enter', ctrl: true,  shift: false, alt: false, label: 'Submit / Run' },
    new_session:     { key: 'n',     ctrl: true,  shift: true,  alt: false, label: 'New Session' },
    focus_repo:      { key: 'p',     ctrl: true,  shift: true,  alt: false, label: 'Focus Repo Path' },
  };

  // Browser-reserved combos — warn if user tries to bind these
  const BROWSER_RESERVED = new Set([
    'ctrl+a','ctrl+c','ctrl+v','ctrl+x','ctrl+z','ctrl+y',
    'ctrl+f','ctrl+n','ctrl+t','ctrl+w','ctrl+r','ctrl+s',
    'ctrl+p','ctrl+l','ctrl+b','ctrl+h','ctrl+j','ctrl+u',
    'ctrl+d','ctrl+e','ctrl+o','ctrl+i',
    'ctrl+shift+i','ctrl+shift+j','f5','f12',
  ]);

  function comboKey(binding) {
    const parts = [];
    if (binding.ctrl)  parts.push('ctrl');
    if (binding.shift) parts.push('shift');
    if (binding.alt)   parts.push('alt');
    parts.push(binding.key.toLowerCase());
    return parts.join('+');
  }

  function isReserved(binding) {
    return BROWSER_RESERVED.has(comboKey(binding));
  }

  function loadUserMap() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  }

  function saveUserMap(overrides) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
  }

  function activeMap() {
    const overrides = loadUserMap();
    return Object.assign({}, DEFAULT_MAP, overrides);
  }

  function handleKey(e) {
    // Don't fire when typing in inputs/textareas (except Ctrl+Enter for submit)
    const tag = document.activeElement?.tagName;
    const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
    if (inInput && !(e.ctrlKey && e.key === 'Enter')) return;

    const map = activeMap();
    for (const [action, binding] of Object.entries(map)) {
      if (
        e.key.toLowerCase() === binding.key.toLowerCase() &&
        !!e.ctrlKey  === !!binding.ctrl  &&
        !!e.shiftKey === !!binding.shift &&
        !!e.altKey   === !!binding.alt
      ) {
        e.preventDefault();
        dispatch(action);
        return;
      }
    }
  }

  function dispatch(action) {
    const tabMap = {
      tab_chat:       'chat',
      tab_benchmarks: 'benchmarks',
      tab_dream:      'dream',
      tab_memory:     'memory',
      tab_graph:      'graph',
      tab_settings:   'settings',
    };
    if (tabMap[action]) {
      if (typeof showWorkspaceTab === 'function') showWorkspaceTab(tabMap[action]);
      return;
    }
    if (action === 'run_submit') {
      document.getElementById('primarySubmit')?.click();
    }
    if (action === 'new_session') {
      document.getElementById('newSessionLink')?.click();
    }
    if (action === 'focus_repo') {
      document.getElementById('repoPathInput')?.focus();
    }
  }

  document.addEventListener('keydown', handleKey);

  // Public API — used by the keybinding editor in the Settings tab
  window.CATTUS_KB = {
    DEFAULT_MAP,
    BROWSER_RESERVED,
    comboKey,
    isReserved,
    activeMap,
    loadUserMap,
    saveUserMap,
    resetAll() {
      localStorage.removeItem(STORAGE_KEY);
    },
  };
})();
```

- [ ] **Step 2: Add the script tag to `index.html` `<head>`**

```html
<script src="{{ url_for('static', filename='keybindings.js') }}" defer></script>
```

Add it after the Mermaid CDN script line.

- [ ] **Step 3: Commit**

```bash
git add web/static/keybindings.js web/templates/index.html
git commit -m "feat(shortcuts): central keybindings module with default keymap"
```

---

### Task 7: Keybinding editor UI in Settings tab

**Files:**
- Modify: `web/templates/index.html` (Settings tab)
- Modify: `web/static/style.css`

- [ ] **Step 1: Add keybinding editor markup to Settings tab**

Inside `<div id="ws-settings"`, after the theme section (Task 2), add:

```html
<!-- Keyboard Shortcuts editor -->
<div class="health-section kb-section">
  <div class="health-header">
    <strong>Keyboard Shortcuts</strong>
    <button type="button" class="sidebar-refresh"
            onclick="kbResetAll()">Reset all</button>
  </div>
  <div id="kbConflictBanner" class="kb-conflict-banner" hidden></div>
  <div id="kbList" class="kb-list"></div>
</div>
```

- [ ] **Step 2: Add keybinding editor JS to `index.html` `<script>` block**

```js
// ── Keybinding editor ──────────────────────────────────────
let _kbListeningAction = null;

function _kbFormatCombo(binding) {
  const parts = [];
  if (binding.ctrl)  parts.push('Ctrl');
  if (binding.shift) parts.push('Shift');
  if (binding.alt)   parts.push('Alt');
  parts.push(binding.key === ',' ? ',' : binding.key.toUpperCase());
  return parts.join('+');
}

function renderKbList() {
  const el = document.getElementById('kbList');
  if (!el || !window.CATTUS_KB) return;
  const map = CATTUS_KB.activeMap();
  const overrides = CATTUS_KB.loadUserMap();

  el.innerHTML = Object.entries(map).map(([action, binding]) => {
    const isOverridden = !!overrides[action];
    const isListening  = _kbListeningAction === action;
    return `
      <div class="kb-row" id="kb-row-${action}">
        <span class="kb-label">${binding.label}</span>
        <kbd class="kb-key ${isOverridden ? 'kb-key--custom' : ''} ${isListening ? 'kb-key--listening' : ''}"
             id="kb-key-${action}">
          ${isListening ? 'Press key…' : _kbFormatCombo(binding)}
        </kbd>
        <button type="button" class="kb-edit-btn"
                onclick="kbStartListening('${action}')">edit</button>
        ${isOverridden
          ? `<button type="button" class="kb-reset-btn"
                     onclick="kbResetOne('${action}')">↩</button>`
          : '<span class="kb-reset-placeholder"></span>'}
      </div>`;
  }).join('');
}

function kbStartListening(action) {
  _kbListeningAction = action;
  renderKbList();

  function onKey(e) {
    // Ignore bare modifier keys
    if (['Control','Shift','Alt','Meta'].includes(e.key)) return;
    e.preventDefault();
    e.stopPropagation();

    const newBinding = {
      key:   e.key === ',' ? ',' : e.key.toLowerCase(),
      ctrl:  e.ctrlKey,
      shift: e.shiftKey,
      alt:   e.altKey,
      label: CATTUS_KB.DEFAULT_MAP[action]?.label || action,
    };

    _kbListeningAction = null;
    document.removeEventListener('keydown', onKey, true);

    // Conflict check
    const map = CATTUS_KB.activeMap();
    const combo = CATTUS_KB.comboKey(newBinding);
    const reservedConflict = CATTUS_KB.isReserved(newBinding);
    const existingConflict = Object.entries(map).find(
      ([a, b]) => a !== action && CATTUS_KB.comboKey(b) === combo
    );

    const banner = document.getElementById('kbConflictBanner');
    if (reservedConflict) {
      banner.hidden = false;
      banner.textContent = `⚠ ${combo} is reserved by the browser — binding saved but may not work reliably.`;
    } else if (existingConflict) {
      banner.hidden = false;
      banner.textContent = `⚠ ${combo} is already used by "${existingConflict[1].label}" — choose a different key.`;
      renderKbList();
      return; // don't save on collision
    } else {
      banner.hidden = true;
    }

    const overrides = CATTUS_KB.loadUserMap();
    overrides[action] = newBinding;
    CATTUS_KB.saveUserMap(overrides);
    renderKbList();
  }

  document.addEventListener('keydown', onKey, true);
}

function kbResetOne(action) {
  const overrides = CATTUS_KB.loadUserMap();
  delete overrides[action];
  CATTUS_KB.saveUserMap(overrides);
  renderKbList();
}

function kbResetAll() {
  if (!confirm('Reset all keyboard shortcuts to defaults?')) return;
  CATTUS_KB.resetAll();
  renderKbList();
}

document.addEventListener('DOMContentLoaded', renderKbList);
```

- [ ] **Step 3: Add keybinding editor CSS**

```css
/* ── Keybinding editor ───────────────────────────────────── */
.kb-section { margin-top: 16px; }

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.kb-row {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  background: var(--color-surface-2);
}

.kb-row:hover { background: var(--color-surface); }

.kb-label {
  font-size: 13px;
  color: var(--color-text);
}

.kb-key {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  font-size: 12px;
  color: var(--color-text-muted);
  min-width: 80px;
  text-align: center;
}

.kb-key--custom {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.kb-key--listening {
  border-style: dashed;
  border-color: var(--color-accent);
  color: var(--color-accent);
  animation: kb-pulse 1s ease infinite;
}

@keyframes kb-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.5; }
}

.kb-edit-btn {
  background: transparent;
  border: none;
  color: var(--color-accent);
  font-size: 12px;
  padding: 2px 4px;
  cursor: pointer;
}

.kb-reset-btn {
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  font-size: 13px;
  padding: 2px 4px;
  cursor: pointer;
}

.kb-reset-btn:hover { color: var(--color-text); }

.kb-reset-placeholder { width: 24px; }

.kb-conflict-banner {
  margin: 8px 0;
  padding: 8px 10px;
  background: var(--color-warning-bg);
  color: var(--color-warning);
  border-radius: var(--radius-sm);
  font-size: 12px;
  border-left: 3px solid var(--color-warning);
}
```

- [ ] **Step 4: Verify keybinding editor**

Start server, go to Settings tab. The shortcut table should render. Click "edit" on Graph row, press `Ctrl+G` — it should save. Press `Ctrl+C` — browser conflict banner should appear. Press `↩` reset — reverts to default.

- [ ] **Step 5: Commit**

```bash
git add web/templates/index.html web/static/style.css
git commit -m "feat(shortcuts): keybinding editor with conflict detection in Settings tab"
```

---

## Phase 4 — README Viewer

### Task 8: Flask `/help` route

**Files:**
- Modify: `web/app.py`
- Modify: `requirements.txt`
- Create: `tests/test_help_route.py`

- [ ] **Step 1: Add `markdown` to `requirements.txt`**

```
markdown>=3.5
```

- [ ] **Step 2: Install it**

```bash
pip install markdown>=3.5
```

- [ ] **Step 3: Write the failing test first**

Create `tests/test_help_route.py`:

```python
import pytest
from web.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_help_route_returns_200(client):
    resp = client.get('/help')
    assert resp.status_code == 200

def test_help_route_returns_html_fragment(client):
    resp = client.get('/help')
    data = resp.get_data(as_text=True)
    # README has a heading — markdown renders it as <h1> or <h2>
    assert '<h' in data

def test_help_route_content_type(client):
    resp = client.get('/help')
    assert 'text/html' in resp.content_type
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
pytest tests/test_help_route.py -v
```

Expected: `FAILED` — 404 on `/help` route.

- [ ] **Step 5: Add the `/help` route to `web/app.py`**

After the existing imports, add:

```python
import markdown as _markdown_lib
```

Then add the route (near the bottom of `app.py`, before `if __name__ == '__main__'`):

```python
_help_cache: dict[str, str] = {}

@app.route('/help')
def help_route():
    readme_path = PROJECT_ROOT / 'README.md'
    cache_key = str(readme_path)
    if cache_key not in _help_cache:
        if readme_path.exists():
            raw = readme_path.read_text(encoding='utf-8')
            _help_cache[cache_key] = _markdown_lib.markdown(
                raw,
                extensions=['fenced_code', 'tables', 'toc'],
            )
        else:
            _help_cache[cache_key] = '<p>README.md not found.</p>'
    return _help_cache[cache_key], 200, {'Content-Type': 'text/html; charset=utf-8'}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_help_route.py -v
```

Expected: all 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add web/app.py requirements.txt tests/test_help_route.py
git commit -m "feat(help): /help route renders README.md via markdown lib"
```

---

### Task 9: README viewer modal in the UI

**Files:**
- Modify: `web/templates/index.html`
- Modify: `web/static/style.css`

- [ ] **Step 1: Add `openHelpModal()` JS function to `index.html` `<script>` block**

```js
// ── README / Help viewer ───────────────────────────────────
function openHelpModal() {
  openAppModal('How to use C.A.T.T.U.S', '<em>Loading README…</em>');
  fetch('/help')
    .then(r => r.text())
    .then(html => {
      const body = document.getElementById('appModalBody');
      if (body) body.innerHTML = `<div class="help-body">${html}</div>`;
    })
    .catch(err => {
      const body = document.getElementById('appModalBody');
      if (body) body.innerHTML = `<p style="color:var(--color-danger)">Failed to load README: ${escapeHtml(String(err))}</p>`;
    });
}
```

- [ ] **Step 2: Add "Help / README" section inside the Settings tab**

After the keyboard shortcuts section, add:

```html
<div class="health-section">
  <div class="health-header">
    <strong>Help</strong>
  </div>
  <p style="font-size:13px;color:var(--color-text-muted);margin:6px 0 10px;">
    Opens the project README with usage instructions.
  </p>
  <button type="button" onclick="openHelpModal()">Open README</button>
</div>
```

- [ ] **Step 3: Add README modal content styling**

```css
/* ── Help / README modal content ────────────────────────── */
.help-body {
  font-size: 14px;
  line-height: 1.65;
  color: var(--color-text);
}

.help-body h1, .help-body h2, .help-body h3 {
  color: var(--color-text);
  margin-top: 1.4em;
  margin-bottom: 0.4em;
}

.help-body h1 { font-size: 1.4em; }
.help-body h2 { font-size: 1.2em; border-bottom: 1px solid var(--color-border); padding-bottom: 4px; }
.help-body h3 { font-size: 1em; }

.help-body code {
  background: var(--color-surface-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 1px 5px;
  font-family: var(--font-mono);
  font-size: 0.9em;
}

.help-body pre {
  background: var(--color-surface-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 12px;
}

.help-body pre code {
  background: none;
  border: none;
  padding: 0;
}

.help-body a { color: var(--color-accent); }

.help-body table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}

.help-body th, .help-body td {
  border: 1px solid var(--color-border);
  padding: 6px 10px;
  text-align: left;
}

.help-body th {
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-weight: 600;
}
```

- [ ] **Step 4: Verify end-to-end**

Start server: `python main.py --web`
1. Click `?` in the sidebar — modal opens, README loads.
2. Click "Open README" in Settings tab — same modal opens.
3. Switch to Terminal theme — modal content should inherit theme colors.
4. Close modal with Escape key.

- [ ] **Step 5: Commit**

```bash
git add web/templates/index.html web/static/style.css
git commit -m "feat(help): README viewer modal via ? button and Settings tab"
```

---

## Done

All 4 phases ship independently. Suggested order: Phase 1 → Phase 2 → Phase 3 → Phase 4.
Each commit is self-contained and can be reverted without breaking others.
