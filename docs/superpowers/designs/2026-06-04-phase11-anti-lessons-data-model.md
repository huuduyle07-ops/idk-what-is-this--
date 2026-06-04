# Phase 11.1 — Anti-Lesson Data Model + Store Safety

**Date:** 2026-06-04
**Phase:** 11.1
**Status:** Implemented
**Scope:** Core/storage only. No UI, no CONTROL prompt changes, no live retrieval
behavior change, no patch/benchmark/Dream execution, no model/API calls, no
subprocess/Docker/network, no auto-promotion.

---

## Motivation

Phase 11-prep added lesson merge/dedupe and the additive schema fields (`kind`,
`archived`, `superseded_by`, `supersedes`, `merge_sources`,
`merge_sources_data`, `duplicate_of`). Phase 11.1 builds on that by making the
`kind` field a first-class concept with **anti-lessons** — and, crucially, keeps
them **inert by default**.

- A **normal lesson** says: *"Do this pattern when this evidence appears."*
- An **anti-lesson** says: *"Do NOT do this tempting but wrong pattern, even if
  it looks plausible."*

Anti-lessons are valuable precisely because they would mislead a model if they
ever leaked into the live CONTROL context prematurely. So 11.1 only adds **safe
storage + safety rails**. Making active anti-lessons retrieval-eligible (and any
CONTROL integration) is deferred to a later Phase 11 slice.

---

## What this slice does

1. **Lesson kind is first-class.** `kind ∈ {"lesson", "anti_lesson"}`.
   - Missing/None/blank `kind` defaults to `"lesson"` (legacy records predate the
     field and are normal lessons).
   - Unknown kinds are rejected on write paths.

2. **Anti-lessons can occupy the existing statuses** — `candidate`, `active`
   (only via explicit human `promote_lesson`), `blocked`, plus the `archived` /
   `superseded` metadata. But an `active` anti-lesson is **still not
   retrieval-eligible** (see #5).

3. **Store helpers** (`core/lesson_store.py`):
   - `KIND_LESSON`, `KIND_ANTI_LESSON`, `LESSON_KINDS`
   - `validate_lesson_kind(value)` — raises on unknown/None (no default).
   - `normalize_lesson_kind(value)` — missing → `"lesson"`, known → unchanged,
     unknown → `ValueError`.
   - `is_anti_lesson(record)` — lenient predicate, never raises.
   - `_normalize_record` canonicalizes `kind` on every read (lenient: corrupt
     values default to `"lesson"` rather than raising in a read path).
   - `save_raw_lesson_record` canonicalizes `kind` on raw writes (strict).

4. **Save/create behavior for anti-lessons** (`save_candidate_lesson(..., kind=…)`):
   - status defaults to `candidate`;
   - **never auto-activates** — even when the quality guard returns
     `auto_approved` and `LESSON_AUTO_ACTIVE` is on (a `blocked` verdict still
     routes to `blocked`);
   - `active_knowledge_allowed` is forced `false` (it can only be true in the
     `active` bucket, which anti-lessons never auto-reach);
   - `source`, `source_report`, `candidate` (evidence), and `evaluation` are
     preserved verbatim.

5. **Retrieval guard** (`core/lesson_retrieval.py`): `list_active_lessons` — the
   single chokepoint feeding `find_active_lessons` and the CONTROL prompt — now
   excludes anti-lessons even if a record reaches the `active` bucket, unless a
   reserved, **default-off** placeholder flag `ANTI_LESSONS_ENABLED` is set. The
   flag is read **fail-closed** (`getattr(config, "ANTI_LESSONS_ENABLED", False)`,
   `False` on any import error). It is **not wired** into CONTROL, promotion, the
   UI, or any automation — flipping it on is reserved for a later Phase 11 slice.

6. **Merge safety** (`core/lesson_merge.py`):
   - **normal + anti_lesson → hard-blocked.** `create_merge` raises `ValueError`
     for this combination *regardless of* `confirm_mix_kinds`. Because `lesson`
     and `anti_lesson` are the only kinds, the only possible "mixed" merge is
     normal+anti, so the prior `confirm_mix_kinds` override (added same-day in the
     merge/dedupe slice) is now **vestigial** — retained only for API/route
     compatibility.
   - **anti_lesson + anti_lesson → allowed**, producing a **candidate**
     anti-lesson with `active_knowledge_allowed=False` (never auto-promoted).
   - `preview_merge` is unchanged (non-writing; it still *warns* about mixed
     kinds rather than blocking).

7. **Archive / supersede compatibility:** anti-lessons work with the existing
   `archive_lesson` (soft, no hard delete) and `superseded_by`/`supersedes`
   metadata; `kind` survives field patches and bucket moves.

---

## Explicitly out of scope (deferred)

- Live/active retrieval of anti-lessons and any CONTROL prompt integration
  (gated behind `ANTI_LESSONS_ENABLED`, which stays off).
- Automatic anti-lesson creation (no Dream/proposal/benchmark wiring produces
  anti-lessons in this slice).
- Any model/API call, patch generation, benchmark scoring, Dream execution,
  subprocess/Docker/network.
- UI work (no new controls; existing merge/list views already tolerate `kind`).
- Auto-promotion of any anti-lesson.

---

## Safety proof (tests)

`tests/test_anti_lessons_store.py` pins the guarantees, including:

- missing `kind` defaults to `lesson`; invalid `kind` rejected;
- anti-lesson saved as `candidate`; `active_knowledge_allowed` forced false;
- anti-lesson not auto-activated even with `LESSON_AUTO_ACTIVE=True`;
- **even an explicitly-promoted `active` anti-lesson is not retrieval-eligible**
  (while a normal active lesson with the same query match *is*), and is absent
  from the CONTROL prompt;
- `ANTI_LESSONS_ENABLED` is the fail-closed gate (flipping it on surfaces the
  anti-lesson — proving the guard reads the flag and is not dead code);
- source/evidence preserved; archive is soft; supersede metadata preserved;
- normal+anti merge blocked (even with `confirm_mix_kinds=True`); anti+anti merge
  yields a candidate anti-lesson;
- an AST guard asserts the three touched modules (`lesson_store`, `lesson_merge`,
  `lesson_retrieval`) import/call no forbidden sinks (model/API, patch,
  benchmark, Dream, subprocess, Docker) and never call `build_control_prompt`.

`tests/test_lesson_merge.py` updated the two prior mixed-kind tests to assert the
new hard block (the only behavioral change to existing tests).
