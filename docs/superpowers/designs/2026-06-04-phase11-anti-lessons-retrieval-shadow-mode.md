# Phase 11.6 — Anti-Lesson Retrieval Shadow Mode

**Date:** 2026-06-04
**Phase:** 11.6
**Status:** Implemented (read-only shadow retrieval only)
**Scope:** A *shadow* retrieval layer that, for a given query/context, reports
which anti-lessons **would** be relevant *if* anti-lessons were enabled later.
**No live behavior changes.** No CONTROL integration, no active-retrieval change,
no patch generation, no Dream execution, no benchmark scoring, no model/API call,
no subprocess/Docker/network, no auto-promotion, no automatic anti-lesson
creation.

---

## What "shadow retrieval" means

> For this query/task, which anti-lessons would be relevant if anti-lessons were
> enabled later?

It returns/reports **matches only**. It must not affect the prompt. The live
agent path (active retrieval → CONTROL prompt → patch/Dream) is untouched: this
slice answers a "what if" question and writes nothing.

This is the read-only precursor to a *future*, **default-off** CONTROL
integration. By proving we can rank anti-lessons against a query cheaply and
deterministically — and audit those rankings — we set up an opt-in path later
without risking the live loop now.

---

## Hard guardrails (this phase)

- **Report-only.** The helpers/route read storage and rank; they never write,
  promote, block, archive, merge, or create a lesson (normal or anti).
- **No prompt impact.** Nothing here calls `build_control_prompt`, mutates active
  retrieval, or is imported by `control_engine.py` / `prompter.py` /
  `lesson_retrieval.py`.
- **Anti-lessons stay inert.** Even an explicitly-promoted anti-lesson remains
  excluded from `list_active_lessons` / `find_active_lessons` and from the CONTROL
  prompt after a shadow call.
- **Deterministic + cheap.** Matching uses normalized token overlap across a few
  fields. No embeddings, no model calls, no network.
- Every result carries the contract explicitly via `shadow_only: true` per match
  and a top-level `blocked_actions` list:
  `["inject_into_control", "modify_active_retrieval", "patch", "benchmark",
  "dream", "model_call", "promote"]`.

---

## What this slice does

1. **Pure shadow matcher** (`core/anti_lesson_retrieval_shadow.py`):
   - `build_anti_lesson_shadow_retrieval(query, records, *, context=None,
     max_items=5, generated_at=None) -> dict`. Takes an already-loaded `records`
     list; considers **only** anti-lessons (normal lessons are never matched).
     Pure — no store access, no mutation, no model.
   - Deterministic, cheap matching. Each query token is matched (substring, after
     lowercasing + stopword drop, hyphens/underscores preserved) against
     per-field haystacks; a field that matches grants its weight and a reason:

     | field | weight | reason |
     | --- | --- | --- |
     | `title` | 5 | `title match` |
     | `summary` | 3 | `summary match` |
     | `tempting_wrong_pattern` | 4 | `tempting_wrong_pattern match` |
     | `why_wrong` | 3 | `why_wrong match` |
     | `safer_alternative` | 2 | `safer_alternative match` |
     | `evidence_refs` / `source_report` overlap (context) | 3 | `evidence/source_report overlap` |
     | `related_lesson_ids` overlap (context) | 3 | `related_lesson_ids match` |

     The optional `context` dict (`evidence_refs`, `source_report`,
     `related_lesson_ids`) adds the last two signals when provided.
   - Returns:
     ```
     {
       generated_at, query, guardrail, total_anti_lessons_considered, max_items,
       selected_matches: [{
         lesson_id, title, status, scope, score, reasons,
         tempting_wrong_pattern, why_wrong, safer_alternative,
         duplicate_of, related_lesson_ids, evidence_refs, shadow_only: true,
       }],
       skipped: [{lesson_id, title, reason}],
       blocked_actions: [...],
     }
     ```
   - Ordering is deterministic: matches sort by (score desc, lesson_id asc), then
     the top `max_items` (clamped to `[1, 50]`) are returned. Zero-score
     anti-lessons and over-cap matches go to `skipped` with explicit reasons — no
     silent truncation.

2. **Markdown formatter** `format_anti_lesson_shadow_retrieval_markdown(result)`
   (pure): title, `generated_at`, query, guardrail, a matched-anti-lesson table,
   per-match reasons / `tempting_wrong_pattern` / `safer_alternative`, the blocked
   actions, and the verbatim statement:
   *"Shadow retrieval is report-only. These anti-lessons are not injected into
   active retrieval or CONTROL prompts."*

3. **Store-aware loader** `load_anti_lesson_shadow_retrieval(query, *, repo_path,
   scope, repo_scope_id, include_global, max_items, context=None)` — the only
   store-aware entry. Performs a single **read** (`lesson_store.list_lessons`),
   filters to `kind="anti_lesson"` (candidate/active alike, all marked
   `shadow_only`), stamps `generated_at`, and delegates to the pure builder. Never
   writes.

4. **Read-only route** `GET /lessons/anti/shadow-retrieval` (`web/app.py`): query
   params `query` (**required**), `max_items?` (bounded), `repo_path?`
   (path-guarded), `scope?`, `repo_scope_id?`, `include_global?`, `format?`. JSON
   by default (`{ok, result}`); `format=markdown`/`md` adds `markdown`. Missing
   `query` → `400`. Reads storage only — never executes anything.

5. **UI** (`web/templates/index.html`, additive only): an
   `antiShadowRetrievalPanel` disclosure in Memory → Lessons titled
   "Anti-Lesson Shadow Retrieval" with a query input, optional max-items input, a
   Search button, and a results area (count considered, top matches with
   score/reasons/tempting pattern/safer alternative). Warning verbatim:
   *"Shadow retrieval is report-only and is not used by CONTROL yet."* It adds
   **no** "Enable anti-lessons" / "Inject into prompt" / "Promote" / "Run patch" /
   "Run Dream" controls.

---

## Explicitly out of scope (deferred)

- Any CONTROL prompt / active-retrieval integration of anti-lessons (the eventual
  *default-off* opt-in — still future).
- Automatic anti-lesson creation/promotion; any model/API call, patch generation,
  benchmark scoring, Dream execution, subprocess/Docker/network.
- Embedding-based or model-scored ranking.

---

## Safety proof (tests)

`tests/test_anti_lesson_retrieval_shadow.py` pins the guarantees:

- the matcher matches on title / summary / tempting_wrong_pattern and on
  why_wrong / safer_alternative; unrelated anti-lessons score 0 and are skipped;
- **normal lessons are never returned** as anti-lesson matches
  (`total_anti_lessons_considered` counts anti-lessons only);
- results are deterministic and bounded by `max_items` (over-cap → `skipped`);
- every match is `shadow_only: true` and the result lists the full
  `blocked_actions`;
- the Markdown carries the shadow-only guardrail and lists blocked actions;
- the route requires `query` (400 otherwise), returns JSON (and Markdown on
  request), bounds `max_items`, and **does not mutate** any lesson file
  (byte-for-byte snapshot equal before/after);
- after a shadow call, `list_active_lessons` / `find_active_lessons` still exclude
  anti-lessons and the CONTROL prompt contains none of them;
- `control_engine.py` / `prompter.py` / `lesson_retrieval.py` do not import the
  shadow module;
- the UI panel exists with the warning and **no** enable/inject/promote/run
  controls;
- an AST guard asserts the module imports/calls no forbidden sinks (model/API,
  patch, benchmark, Dream, mutation oracle, subprocess, Docker) and never calls
  `build_control_prompt` / `promote_lesson` / `save_candidate_lesson` /
  `create_manual_anti_lesson` / `create_merge`.
