# C.A.T.T.U.S Web Redesign — Design Spec

**Date:** 2026-05-24  
**Scope:** Full web UI redesign — theme system, layout rebuild, keyboard shortcuts, README viewer  
**Approach:** Phased (4 independent shippable phases)

---

## Goals

- Make the UI feel like a polished, modern developer tool rather than a raw prototype
- Add VS Code-style theme switching (3 built-in themes)
- Add keyboard shortcuts for workspace navigation, with a custom keybinding editor
- Surface the README.md as an in-app help resource
- Remove redundant/dead buttons to reduce visual clutter

---

## Phase 1 — CSS Theme System

### What
Replace all hardcoded color values in `web/static/style.css` with CSS custom properties on `:root`. Define 3 theme presets as data attributes on `<body>`.

### Themes
| Name | Palette | Accent | Font |
|---|---|---|---|
| Clean & Structured | Slate dark (`#0f172a` bg) | Blue (`#3b82f6`) | system-ui |
| Modern Dev Tool | Zinc near-black (`#09090b` bg) | Indigo-violet (`#6366f1`) | system-ui |
| Terminal Hacker | Pure black (`#030712` bg) | Emerald green (`#10b981`) | monospace |

### Implementation
- CSS variables: `--color-bg`, `--color-surface`, `--color-surface-2`, `--color-border`, `--color-text`, `--color-text-muted`, `--color-accent`, `--color-accent-hover`, `--color-accent-fg`
- Theme applied via `<body data-theme="clean|modern|terminal">`
- Active theme persisted in `localStorage` key `cattus_theme`
- Theme selector lives in the Settings/Health workspace tab (dropdown + 3 preview chips)
- Default theme: `modern`

---

## Phase 2 — HTML Layout Rebuild

### What
Rebuild `web/templates/index.html` with tighter structure. Remove dead/redundant UI. Improve visual hierarchy throughout.

### Buttons to remove
| Button | Reason |
|---|---|
| `openObsidian()` | Shows a `confirm()` alert as fallback — poor UX, niche use |
| Duplicate `⟳ Refresh` buttons (per-section) | Replace with a single global refresh or auto-refresh on tab focus |
| `Local Critique` brain button | Promote to its own tab section instead of floating action button |

### Layout changes
- **Sidebar:** Add `?` help button next to the brand mark (links to README viewer). Tighten session list item spacing.
- **Main header:** Replace the plain `h1` + eyebrow with a single clean title row. Remove the verbose `margin-top-info` status line — fold into a compact status chip.
- **Form area:** Group repo path + project tag on one row. Collapse `instant-run-controls` into a disclosure `<details>` that opens when needed.
- **Workspace tabs:** Increase tab height, add active underline indicator (already in CSS, make it more prominent). Remove per-tab redundant refresh buttons; each workspace tab auto-refreshes its data when it becomes active (on `showWorkspaceTab()` call).
- **Settings tab:** Add Theme Selector section and Keyboard Shortcuts section (see Phase 3).

---

## Phase 3 — Keyboard Shortcuts + Custom Keybinding Editor

### Default keymap
| Action | Default shortcut | Reason |
|---|---|---|
| Chat / Patch tab | `Ctrl+1` | C conflicts with Copy |
| Benchmarks tab | `Ctrl+K` | K = bencKmark, safe |
| Dream tab | `Ctrl+2` | D conflicts with Bookmark (Chrome/FF) |
| Memory tab | `Ctrl+M` | Safe |
| Graph tab | `Ctrl+G` | User-specified |
| Settings tab | `Ctrl+,` | VS Code standard |
| Submit / Run | `Ctrl+Enter` | Universal form submit |
| New Session | `Ctrl+Shift+N` | Safe |
| Focus repo path | `Ctrl+Shift+P` | Safe |

### Architecture
- Single `keybindings.js` module loaded in `<head>`
- Keymap object: `{ action_id: { key, ctrl, shift, alt, meta } }`
- User overrides stored in `localStorage` key `cattus_keybindings` (JSON), merged over defaults at load
- Listener on `document.keydown`, checks focused element to avoid firing inside inputs/textareas

### Custom Keybinding Editor (in Settings tab)
- Table: Action | Current shortcut | Edit button
- Clicking Edit enters "listening" mode on that row — next keydown captured as new binding
- **Conflict detection:** on capture, check against browser-reserved combos (hardcoded blocklist) and existing bindings. Show inline warning if conflict found — user can override or cancel.
- Reset All button restores defaults
- Changes saved to `localStorage` immediately

---

## Phase 4 — README Viewer

### What
Render `README.md` as styled HTML inside the app. Accessible without leaving the UI.

### Implementation
- New Flask route: `GET /help` — reads `README.md` from project root, parses with Python `markdown` library (add to `requirements.txt`), returns rendered HTML fragment
- Entry points:
  - `?` icon button in sidebar brand area
  - "Help / README" section in Settings tab
- Rendered inside the existing shared modal (`appModal`) — consistent with other app-wide overlays
- Styled with the active theme's text/surface colors
- Flask caches the rendered HTML in memory (re-reads on server restart)

---

## Files Affected

| File | Change |
|---|---|
| `web/static/style.css` | Full rewrite — CSS variables, theme presets |
| `web/templates/index.html` | Full rebuild — layout, removed buttons, new sections |
| `web/static/keybindings.js` | New file — keymap, listener, localStorage |
| `web/app.py` | Add `/help` route |
| `requirements.txt` | Add `markdown` |

---

## Out of Scope

- Mobile/responsive redesign beyond what already exists
- Dark/light mode toggle (all 3 themes are dark)
- Changing any backend pipeline logic
- Migrating to Jinja2 template includes (deferred — future phase)
