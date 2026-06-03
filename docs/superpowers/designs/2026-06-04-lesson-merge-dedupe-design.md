
# Lesson Merge / Dedupe Design — Phase 11-prep-cleanup-b2

**Date:** 2026-06-04  
**Phase:** 11-prep-cleanup-b2  
**Status:** Approved — ready for implementation planning  
**Scope:** Design only. No implementation until plan is written and approved.

---

## Motivation

The lesson list grows noisy as repeated benchmark/Dream/proposal runs produce similar or
redundant lessons. A newer run often refines an older lesson. Before Phase 11 adds
anti-lessons, we need:

- duplicate detection hints (deterministic, no model calls)
- a safe merge flow that creates a new candidate from N source lessons
- archive support for lessons that are no longer relevant but should not be deleted
- superseded tracking so provenance chains remain queryable

**Out of scope for b2:**
- active lesson retrieval changes (no changes to `lesson_retrieval.py`)
- CONTROL prompt changes
- auto-promotion of merged lessons
- model/API calls
- patch/benchmark/Dream execution
- deletion of active lessons

---

## 1. Current Lesson Schema

A lesson record is a JSON file stored in one of three filesystem bucket directories:

```
.agent/lessons/{candidate,active,blocked}/<id>.json
.agent/lessons/repos/<repo_scope_id>/{candidate,active,blocked}/<id>.json
```

### Existing top-level fields

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Timestamp slug `YYYYMMDD_HHMMSS_ffffff[-N]` |
| `status` | `str` | `candidate\|active\|blocked` — mirrors filesystem bucket |
| `scope` | `str` | `global\|repo` |
| `repo_scope_id` | `str\|null` | Repo-scope identity |
| `repo_path_hint` | `str\|null` | Human-readable repo name hint |
| `created_at` | ISO str | |
| `updated_at` | ISO str | |
| `source` | `str` | `manual\|benchmark_report\|patch_proposal\|dream\|replay\|merge` |
| `source_report` | `str\|null` | Artifact identifier used as idempotency key |
| `case_name` | `str\|null` | Benchmark/Dream case name |
| `title` | `str` | |
| `summary` | `str` | |
| `tags` | `list[str]` | Derived by `derive_lesson_tags()` |
| `candidate` | `dict` | Raw candidate dict from the source |
| `evaluation` | `dict` | `lesson_quality` output: `{promotion, reasons, score, active_knowledge_allowed}` |
| `active_knowledge_allowed` | `bool` | True only when file lives in `active/` |

---

## 2. Proposed New Fields

All fields are **additive**. Old records simply lack them; all code treats absence as the
default value. No migration needed.

```jsonc
// Appended to the lesson record JSON
"kind":          "lesson",   // "lesson" | "anti_lesson"; default "lesson"
"archived":      false,      // bool; settable only on candidate or blocked; default false
"superseded_by": null,       // str | null — ID of the lesson that replaces this one
"supersedes":    [],         // list[str] — IDs this lesson explicitly replaces
"merge_sources": [],         // list[str] — source IDs when created via merge
"merge_sources_data": [],    // list[{id, candidate, evaluation}] — preserved evidence
"duplicate_of":  null        // str | null — soft hint only, no behavioral enforcement
```

### Effective status (UI-derived, not stored)

The filesystem buckets and the `status` field remain the ground truth for retrieval.
The UI computes an **effective_status** for display and filtering:

1. If `superseded_by` is set → `"superseded"`
2. Else if `archived` is `true` → `"archived"`
3. Otherwise → `status` field (`candidate | active | blocked`)

### Retrieval guard (deferred to Phase 11)

The guard that would exclude `archived=true` and `superseded_by != null` lessons from
`list_lessons(status="active")` is **designed here but not implemented until Phase 11**.
The `lesson_retrieval.py` module is untouched in b2.

---

## 3. Lesson Statuses

| Status | Stored as | Notes |
|---|---|---|
| `candidate` | filesystem bucket | Default for new/merged lessons |
| `active` | filesystem bucket | Retrieval-eligible |
| `blocked` | filesystem bucket | Quality gate rejected |
| `archived` | metadata flag `archived=true` | File stays in candidate or blocked bucket |
| `superseded` | metadata field `superseded_by` set | File stays in its current bucket |

`archived` is only settable on `candidate` or `blocked`. Setting it on `active` → 400.

---

## 4. Duplicate Detection

**New module:** `core/lesson_duplicates.py`

Pure Python, no model calls, deterministic. Returns groups of likely-duplicate lessons.

### Hint signals

Any one signal is sufficient to place two lessons in the same group.

| Signal | Rule |
|---|---|
| `source_key` | Same non-null `source_report` + `case_name` |
| `title_match` | Same title after lowercase + strip punctuation/whitespace |
| `tag_overlap` | Same `language` + `category` + ≥2 shared tags |
| `summary_token_overlap` | Jaccard on whitespace-split word tokens ≥ 0.5 |
| `same_case_different_run` | Same non-null `case_name`, different `source_report` |

### Output shape

```python
list[DuplicateGroup]

DuplicateGroup = {
    "lesson_ids": list[str],       # IDs of all lessons in the group
    "hint_reasons": list[str],     # human-readable explanation per signal
}
```

### Public API

```python
def find_duplicate_groups(
    lessons: list[dict],
    *,
    min_group_size: int = 2,
) -> list[dict]:
    """Return groups of lessons that share at least one duplicate hint signal."""
```

Takes an already-loaded lesson list so the caller controls scope/status filtering.

---

## 5. Merge Behavior

**New module:** `core/lesson_merge.py`

### Merge preview

```python
def preview_merge(
    lessons: list[dict],
    *,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """
    Build a merged record preview without writing anything.
    Returns a candidate-shaped dict.
    """
```

- Combines `tags` (union, deduped)
- Pre-fills `title` from first source if not provided
- Pre-fills `summary` by joining source summaries (truncated to ~500 chars) if not provided
- Sets `merge_sources`, `merge_sources_data`, `supersedes`
- Sets `status: "candidate"`, `active_knowledge_allowed: False`
- Sets `kind`: uniform from sources; if mixed, sets `kind: "mixed"` and adds a warning

### Merge create

`POST /lessons/merge/create` sequence:

1. Validate: ≥2 source `lesson_ids`, all resolvable
2. If any source has `status="active"`: require `confirm_supersede_active: true` in body, else 400
3. If sources have mixed `kind` values: require `confirm_mix_kinds: true`, else 400
4. Build merged record via `preview_merge()` with user-supplied `title`/`summary`/`tags`
5. Assign a new lesson ID; write to `candidate/` bucket (atomic)
6. Patch each source record in-place: set `superseded_by: new_id`, `updated_at: now` (atomic)
7. Return `{ok: true, lesson: <new record>, superseded: [ids...]}`

### Invariants

- Merged lesson always has `status="candidate"` and `active_knowledge_allowed=False`
- No auto-promotion ever
- Source `candidate` + `evaluation` dicts are preserved in `merge_sources_data`
- Source lessons are marked `superseded_by` only after the merge write succeeds

---

## 6. Routes

All new routes follow existing patterns in `web/app.py`. JSON body in, JSON response out.

### GET /lessons/duplicates

```
Query params: status?, scope?, repo_path?, repo_scope_id?, include_global?
Response: {ok: true, groups: [{lesson_ids: [...], hint_reasons: [...]}]}
```

Loads lessons via `list_lessons(...)`, passes them to `find_duplicate_groups()`.

### POST /lessons/merge/preview

```
Body:   {lesson_ids: [str, ...], title?: str, summary?: str, tags?: [str]}
Response: {ok: true, preview: <lesson record shape>, warnings: [str]}
```

No writes. Returns the would-be merged record plus any warnings (active sources,
mixed kinds).

### POST /lessons/merge/create

```
Body: {
    lesson_ids: [str, ...],
    title: str,
    summary: str,
    tags: [str],
    scope?: str,
    repo_path?: str,
    repo_scope_id?: str,
    confirm_supersede_active?: bool,
    confirm_mix_kinds?: bool,
}
Response: {ok: true, lesson: <new record>, superseded: [str]}
```

### POST /lessons/archive

```
Body:   {lesson_id: str, scope?: str, repo_path?: str, repo_scope_id?: str}
Response: {ok: true, lesson: <updated record>}
Errors: 400 if lesson is active
        404 if not found
```

Sets `archived: true`, `updated_at: now`. Atomic write in-place (file stays in its bucket).

### POST /lessons/supersede (b2b, optional)

```
Body:   {lesson_id: str, superseded_by: str, confirm_supersede_active?: bool, ...}
Response: {ok: true, lesson: <updated record>}
```

Standalone supersede without a merge. Requires `confirm_supersede_active` if active.

---

## 7. UI Flow

### b2a — no UI changes

All b2a work is backend only. Routes are testable via curl/Postman.

### b2b — Memory tab additions

#### Merge flow

1. **"Merge…" button** in Lessons section header → enters select mode
   - Lesson cards gain checkboxes
   - "Cancel" exits select mode
2. **Selection**: user checks ≥2 cards → "Preview merge (N selected)" button activates
3. **Preview modal**:
   - Editable title input (pre-filled from first source)
   - Editable summary textarea (pre-filled from joined summaries)
   - Tag pills (union of sources; removable; add-tag input)
   - "Source lessons" list — read-only, shows title + status badge for each
   - Warning banner (amber): *"⚠ N active lesson(s) will be superseded"* (if any source is active)
   - Warning banner (amber): *"⚠ Mixing lesson and anti-lesson kinds"* (if kinds differ)
   - Explicit confirmation checkbox per warning (required to enable Create button)
   - "Create merged candidate" button (disabled until confirmations satisfied)
   - "Cancel" button
4. **After create**:
   - Modal closes; list refreshes
   - New merged candidate shows `[merged from N]` badge
   - Superseded source lessons show `[superseded]` badge
   - Superseded lessons hidden by default (controlled by "Show superseded" toggle)

#### Duplicate hints panel

- Collapsible `<details>` section above the lesson list: "Duplicate hints (N groups)"
- On expand: fetches `GET /lessons/duplicates` for current scope/status
- Each group shown as a card with lesson titles + hint reasons
- "Select all in group" shortcut pre-populates the merge select mode

#### Filter bar additions

New controls added to the existing `.lessons-filters` bar:

| Control | Type | Values |
|---|---|---|
| Kind | `<select>` | All kinds / Lesson / Anti-lesson |
| Effective status | Status buttons | Add: Archived, Superseded alongside existing |
| Show superseded | Toggle (default OFF) | Hides superseded lessons unless enabled |
| Show archived | Toggle (default OFF) | Hides archived lessons unless enabled |

---

## 8. Safety Invariants

| Rule | Enforcement |
|---|---|
| `archived` only on candidate/blocked | Route returns 400 if `status="active"` |
| Supersede active lesson requires confirmation | Route returns 400 without `confirm_supersede_active: true` |
| Merged lesson always `candidate` | Hardcoded in `lesson_merge.py`; no override path |
| No auto-promote | No code path in b2 promotes the merged record |
| No hard-delete | No delete route exists or is added |
| Mixing `lesson`+`anti_lesson` requires confirmation | Route returns 400 without `confirm_mix_kinds: true` |
| `blocked` lessons may be merge sources | Allowed; merged product is still always `candidate` |
| Source evidence preserved | `merge_sources_data` captures full `candidate`+`evaluation` per source |

---

## 9. Tests Design

### `tests/test_lesson_duplicates.py`

- Same `source_report` + `case_name` → grouped (signal: `source_key`)
- Same normalized title → grouped (signal: `title_match`)
- Same language + category + 2 shared tags → grouped (signal: `tag_overlap`)
- Jaccard of summary tokens ≥ 0.5 → grouped (signal: `summary_token_overlap`)
- Same `case_name`, different `source_report` → grouped (signal: `same_case_different_run`)
- No overlap on any signal → not grouped
- Single lesson → no groups

### `tests/test_lesson_merge.py`

- `preview_merge()` — no file writes; returns candidate-shaped dict
- `preview_merge()` — combined tags are union of sources, deduped
- `preview_merge()` — `merge_sources_data` contains source `candidate`+`evaluation`
- `POST /lessons/merge/create` — merged lesson exists in candidate bucket
- `POST /lessons/merge/create` — merged lesson has `status="candidate"`, `active_knowledge_allowed=False`
- `POST /lessons/merge/create` — source lessons have `superseded_by` set to merged ID
- `POST /lessons/merge/create` — active source without `confirm_supersede_active` → 400
- `POST /lessons/merge/create` — mixed `kind` without `confirm_mix_kinds` → 400
- No auto-promotion: merged lesson never becomes active without explicit promote call

### `tests/test_lesson_archive.py`

- Archive candidate → `archived=True`, file stays in candidate bucket
- Archive blocked → `archived=True`, file stays in blocked bucket
- Archive active → 400

### `tests/test_lesson_retrieval_guard.py` (Phase 11 — design only, not implemented in b2)

- `list_lessons(status="active")` excludes lessons with `superseded_by` set
- `list_lessons(status="active")` excludes lessons with `archived=True`
- Normal active lesson without either flag → still included

---

## 10. Implementation Plan Split

### b2a — Core + Routes (no UI)

1. Add 6 new fields to the record written by `save_candidate_lesson()` in `lesson_store.py`
2. Add `get_lesson_by_id(lesson_id, ...)` helper to `lesson_store.py` (needed by merge)
3. Add `patch_lesson_fields(lesson_id, fields: dict, ...)` helper for atomic in-place updates
4. Write `core/lesson_duplicates.py` — `find_duplicate_groups(lessons)`
5. Write `core/lesson_merge.py` — `preview_merge()`, `create_merge()`, `archive_lesson()`
6. Wire routes in `web/app.py`:
   - `GET /lessons/duplicates`
   - `POST /lessons/merge/preview`
   - `POST /lessons/merge/create`
   - `POST /lessons/archive`
7. Write tests: `test_lesson_duplicates.py`, `test_lesson_merge.py`, `test_lesson_archive.py`

### b2b — UI

1. Filter bar: kind select, archived/superseded toggles, effective-status buttons
2. Select mode: "Merge…" button, card checkboxes, cancel
3. Preview merge modal (title/summary/tags editable, warnings, confirmation checkboxes)
4. Duplicate hints collapsible panel with "Select all in group" shortcut
5. Optional: `POST /lessons/supersede` standalone route

---

## 11. Non-Goals (explicitly out of scope)

- Changes to `lesson_retrieval.py` or `find_active_lessons()` — deferred to Phase 11
- CONTROL prompt changes
- Auto-promotion of any lesson
- Model/API calls anywhere in this feature
- Deletion of lessons (active or otherwise)
- Benchmark/Dream/patch execution
- Replay or re-evaluation of merged lessons
