# Phase 11.3 — Anti-Lesson Duplicate / Merge Polish

**Date:** 2026-06-04
**Phase:** 11.3
**Status:** Implemented
**Scope:** Duplicate hygiene + anti+anti merge polish only. No live retrieval
change, no CONTROL prompt change, no patch/benchmark/Dream execution, no
model/API calls, no subprocess/Docker/network, no auto-promotion, no Reverse
Dream.

---

## Motivation

Phase 11.1 made `kind ∈ {"lesson", "anti_lesson"}` a first-class concept and kept
anti-lessons inert; Phase 11.2 added operator-driven manual creation. With humans
now able to hand-write anti-lessons, near-duplicates are easy to create. Phase
11.3 adds **advisory** duplicate detection and hardens the anti+anti merge path —
without moving anti-lessons one inch closer to live retrieval or CONTROL.

The guiding rule: **detection is advisory, never enforcement.** Nothing here
blocks creation, auto-merges, auto-blocks, promotes, or activates.

---

## What this slice does

1. **Anti-lesson duplicate detection** (`core/lesson_duplicates.py`, pure):
   - `detect_anti_lesson_duplicates(record, existing) -> {duplicate_of,
     possible_duplicates, reasons}`. Only records whose kind is `anti_lesson`
     are considered, so a normal lesson is never reported as an anti-lesson
     duplicate. The record's own id is skipped.
   - Deterministic, cheap signals (string normalization + set overlap; **no
     embeddings, no model calls**): same/similar normalized title, same
     `tempting_wrong_pattern`, same `why_wrong`, overlapping `evidence_refs`,
     overlapping `related_lesson_ids`, same `source_report` (and same non-`manual`
     `source`).
   - `duplicate_of` is set only on a **strong** match — identical
     `tempting_wrong_pattern` (the defining trait of an anti-lesson), or matching
     title *and* `why_wrong`. Weaker overlaps (e.g. shared evidence only) surface
     in `possible_duplicates` with `duplicate_of = null`.
   - The existing `find_duplicate_groups` / `_duplicate_hints` (the
     `/lessons/duplicates` route) gains the same anti signals, **gated on both
     records being anti-lessons** so normal+anti are never grouped.
   - `anti_lesson_overlap_reasons_for_group(lessons)` — de-duped union of pairwise
     overlap reasons across a group (used by the merge preview).

2. **Store-aware wrapper** (`core/anti_lessons.py`):
   - `find_anti_lesson_duplicates(record, *, repo_path, scope, repo_scope_id)`
     loads existing anti-lessons via `lesson_store.list_lessons` and delegates to
     the pure detector. Read-only; any store error degrades to an empty
     (no-duplicate) result so it can never break creation.

3. **Manual-creation duplicate warning** (`web/app.py`, `POST /lessons/anti/create`):
   - Least-disruptive policy chosen: **always create the candidate**, then attach
     an advisory `duplicate_warning` ({duplicate_of, possible_duplicates,
     reasons}) to the response. No `409`, no blocking.
   - If a **strong** duplicate exists, the new candidate records a `duplicate_of`
     link via `patch_lesson_fields` — **metadata only**. `patch_lesson_fields`
     keeps the file in its candidate bucket, so `status` stays `candidate` and
     `active_knowledge_allowed` stays `false`. Nothing is promoted, activated, or
     merged.

4. **Anti+anti merge polish** (`core/lesson_merge.py`):
   - `create_merge` for anti+anti already yields a **candidate** anti-lesson with
     `active_knowledge_allowed=false`; 11.3 pins this with tests and confirms
     `merge_sources` / `merge_sources_data` / `supersedes` / `superseded_by` /
     `duplicate_of` stay compatible (sources preserved in `merge_sources_data`).
   - **normal+anti remains a hard block** regardless of `confirm_mix_kinds`
     (unchanged from 11.1).
   - `preview_merge` now appends `anti-lesson overlap: …` warnings for an
     anti+anti preview (kind/candidate/`active_knowledge_allowed=false` already
     shown). It still **writes nothing**, and for normal+anti it still only
     *warns* (`mixing lesson kinds: …`).

5. **UI polish** (`web/templates/index.html`, additive only):
   - Create form surfaces the `duplicate_warning` after creation (⚠ message;
     creation still succeeds).
   - Lesson card shows a `duplicate` badge when `duplicate_of` is set, alongside
     the existing `anti-lesson` kind badge. No CONTROL/retrieval toggles added.

---

## Explicitly out of scope (deferred)

- Live/active retrieval of anti-lessons and any CONTROL prompt integration
  (still gated behind `ANTI_LESSONS_ENABLED`, which stays off).
- Auto-blocking / auto-merging of detected duplicates.
- Automatic anti-lesson creation, Reverse Dream, or any model/API call, patch
  generation, benchmark scoring, Dream execution, subprocess/Docker/network.
- Auto-promotion of any anti-lesson.

---

## Safety proof (tests)

`tests/test_anti_lessons_duplicate_merge.py` pins the guarantees:

- detector catches same `tempting_wrong_pattern` (strong → `duplicate_of`) and
  shared `evidence_refs` (weak → `possible_duplicates`, `duplicate_of=null`);
  ignores unrelated anti-lessons, non-anti records, and the record's own id;
- the route returns `duplicate_warning` metadata, records advisory `duplicate_of`
  on an exact duplicate, and **does not** promote/activate (result stays
  `candidate` / `active_knowledge_allowed=false`; active bucket empty; absent
  from `list_active_lessons`);
- anti+anti merge stays a candidate anti-lesson, keeps
  `active_knowledge_allowed=false`, and preserves merge source metadata;
- normal+anti merge is still hard-blocked (even with `confirm_mix_kinds=True`);
- `preview_merge` normal+anti warns and writes nothing; anti+anti reports the
  candidate-only inert outcome plus overlap reasons and writes nothing;
- after a duplicate + merge (and an explicit promote), **no anti-lesson appears
  in active retrieval**, and the CONTROL prompt contains none of them;
- an AST guard asserts the touched modules (`anti_lessons`, `lesson_duplicates`)
  import/call no forbidden sinks (model/API, patch, benchmark, Dream,
  subprocess, Docker) and never call `build_control_prompt` / `promote_lesson`.
