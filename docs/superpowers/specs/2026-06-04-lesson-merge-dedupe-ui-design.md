# Phase 11-prep-cleanup-b2b: Lesson Merge / Dedupe UI

**Date:** 2026-06-04  
**Scope:** UI only — augments Memory/Lessons section in `web/templates/index.html`  
**Routes used:** existing b2a routes only (no new routes)

---

## Goals

Add controls that let the user discover duplicate lessons, select lessons for merge, preview and confirm a merged candidate, archive candidate/blocked lessons, and reveal archived/superseded lessons when needed. No retrieval behavior, CONTROL prompt, model calls, patch generation, validation, or benchmark execution is touched.

---

## Architecture

### Single-file approach

All changes land in `web/templates/index.html` (HTML structure + inline JS). No new Python files. No route changes.

### Routes called

| Route | Method | When |
|---|---|---|
| `/lessons/duplicates` | GET | On "Duplicate hints" panel open/refresh |
| `/lessons/merge/preview` | POST | On "Preview merge" with 2+ selected lessons |
| `/lessons/merge/create` | POST | On "Create merged candidate" from preview modal |
| `/lessons/archive` | POST | On "Archive" button for candidate/blocked cards |

Routes NOT called: `/lessons/promote`, `/lessons/block`, `/lessons/list` are unmodified. No patch, benchmark, Dream, model, validation, lesson-promotion, or retrieval-control routes.

---

## HTML Changes

### 1. Filter bar (existing `div.lessons-filters`)

Add to the filter bar after the existing status buttons and selects:

- **Kind filter** (`<select id="lessonFilterKind">`): options `All kinds | lesson | anti-lesson`
- **Show archived** toggle (`<input type="checkbox" id="showArchivedLessons">`)
- **Show superseded** toggle (`<input type="checkbox" id="showSupersededLessons">`)

Defaults: both checkboxes unchecked (archived and superseded hidden by default).

### 2. Duplicate hints panel

A `<details id="duplicateHintsPanel">` placed between the lessons header and the filters:

```
[Duplicate hints ▸]   [Refresh hints button]
  — groups render here after open/refresh —
```

- Groups show lesson titles, IDs, status badges, and hint reasons
- Each group has a "Select group for merge" button that enters merge-select mode with those lessons pre-checked
- Default state: collapsed

### 3. Lessons header additions

The `div.lessons-header` gains two buttons:

- **⟳ Refresh** (`onclick="loadLessons(true)"`) — already implied by existing code, now made explicit
- **Merge lessons** (`id="mergeSelectToggle"`, `onclick="toggleMergeSelectMode()"`) — toggles merge-select mode

### 4. Merge preview modal

Uses the existing singleton `openAppModal(title, bodyHtml, footerHtml)`:

- **Body:** editable title (`<input id="mergePreviewTitle">`), editable summary (`<textarea id="mergePreviewSummary">`), editable tags (`<input id="mergePreviewTags">`), source lessons list (read-only), warnings section, active-source confirmation checkbox (`id="mergeConfirmSupersede"`) shown only when warnings include active lessons
- **Footer:** "Create merged candidate" button (`id="mergeCreateBtn"`) + "Cancel" button
- All data passed via JS state variables, not inline onclick user strings

### 5. Lesson card updates

`_renderLessonCard()` is augmented to render:

- **Merge-mode checkbox** (`data-merge-id`, rendered only when `_lessonsMergeSelectMode === true`)
- **Archive button** for candidate/blocked cards only; disabled with tooltip for active cards ("Active lessons cannot be archived; supersede through merge instead.")
- **Badges:** `archived`, `superseded`, `merged from N` alongside existing status badges
- **Card visibility:** cards with `archived=true` or `superseded_by != null` are hidden unless the matching toggle is checked

---

## JS Changes

### New state variables

```js
let _lessonsShowArchived = false;
let _lessonsShowSuperseded = false;
let _lessonsKindFilter = "";
let _lessonsMergeSelectMode = false;
let _lessonsMergeSelected = new Set();   // lesson IDs
let _mergePreviewData = null;            // last preview response
```

### New functions

| Function | Purpose |
|---|---|
| `loadDuplicateHints(force)` | GET /lessons/duplicates, render groups |
| `_renderDuplicateGroup(group)` | Render one duplicate group card |
| `selectGroupForMerge(ids)` | Enter merge-select mode with pre-checked IDs |
| `toggleMergeSelectMode()` | Toggle merge-select on/off |
| `exitMergeSelectMode()` | Clear selection, re-render, update button label |
| `_updateMergeSelectUI()` | Refresh selected count + enable/disable Preview button |
| `previewMergeSelected()` | POST /lessons/merge/preview, open modal |
| `_openMergePreviewModal(preview, warnings, lessonIds)` | Populate and open modal |
| `createMergedCandidate()` | POST /lessons/merge/create from modal state |
| `archiveLessonById(lessonId, scope, repoScopeId)` | POST /lessons/archive |

### Modified functions

- `_applyLessonFilters()`: extend to filter by kind, archived, superseded
- `_renderLessonCard()`: add merge checkbox, archive button, new badges
- `loadLessons()`: unchanged API call; post-render filtering handles visibility

### Safety rules (enforced in implementation)

- `selectGroupForMerge` receives IDs via a `data-merge-ids` attribute on the button, never from inline onclick string interpolation
- `createMergedCandidate` reads title/summary/tags from `getElementById`, never from inline onclick
- `confirm_supersede_active` is sent only when `#mergeConfirmSupersede` is checked
- `auto_promote` is never sent
- All rendered user content uses `_escapeHtml()`

---

## Test File: `tests/test_web_ui_lesson_merge_controls.py`

Coverage:

1. Merge select button exists (`id="mergeSelectToggle"`)
2. Duplicate hints panel exists (`id="duplicateHintsPanel"`)
3. Preview merge modal structure present (`id="mergePreviewTitle"`, `id="mergePreviewSummary"`)
4. Create merged candidate button exists (`id="mergeCreateBtn"`)
5. Show archived toggle exists (`id="showArchivedLessons"`)
6. Show superseded toggle exists (`id="showSupersededLessons"`)
7. Archive button function defined (`archiveLessonById`)
8. Active archive blocked — tooltip text present ("Active lessons cannot be archived")
9. JS only calls b2a lesson routes (grep for route strings in lesson JS block)
10. JS does not call forbidden routes (patch/benchmark/Dream/model/validation/promotion-control)
11. `confirm_supersede_active` is explicit — only sent when checkbox checked, never auto
12. No unsafe inline onclick with lesson title/summary interpolation

---

## Validation Commands

```
python -m compileall web tests
python -m pytest tests/test_web_ui_lesson_merge_controls.py -q --basetemp .fresh_tmp_b2b_ui
python -m pytest tests -q --basetemp .fresh_tmp_b2b_full
python -m benchmarks.run_benchmarks --check
```

Expected: focused tests pass, full pytest green, benchmark --check 50 checked / 0 errors.

---

## Out of scope

- No lesson retrieval behavior changes
- No CONTROL prompt changes
- No active lesson auto-promotion
- No model/API calls
- No patch generation
- No validation/subprocess/Docker
- No benchmark/Dream execution
- No hard delete
- No new Python routes
