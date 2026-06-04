# Phase 11.4 — Anti-Lesson Evidence / Reporting Shadow Views

**Date:** 2026-06-04
**Phase:** 11.4
**Status:** Implemented
**Scope:** Read-only reporting / shadow visibility only. No active retrieval
change, no CONTROL prompt change, no patch/benchmark/Dream execution, no
model/API calls, no subprocess/Docker/network, no auto-promotion, no Reverse
Dream execution.

---

## Motivation

Phase 11.1–11.3 made anti-lessons first-class but inert: stored, manually
creatable, and duplicate-aware, yet excluded from live retrieval and the CONTROL
prompt. Before any *Reverse Dream* or *retrieval shadow mode* can be trusted, an
operator needs to be able to **see and audit** what anti-lessons exist and how
healthy they are. Phase 11.4 adds exactly that — a report — and nothing else.

The guiding rule: **report-only.** The report is shadow visibility. It reads from
storage and renders; it never writes, promotes, blocks, archives, merges, or
feeds anything into the live agent.

---

## What this slice does

1. **Pure report builder** (`core/anti_lesson_reports.py`):
   - `build_anti_lesson_report(lessons, *, generated_at=None) -> dict`. Takes an
     already-loaded list (anti + normal). Only anti-lessons are summarized;
     normal lessons are used solely to resolve `related_lesson_ids`. Pure — no
     store access, no mutation, no model.
   - Report sections: `counts` (total, by_status, by_scope, by_kind, archived,
     superseded, with_duplicate_of, weak), `records` (all anti rows),
     `candidates` (status=candidate table rows), `duplicate_groups` (via the
     anti-aware `lesson_duplicates.find_duplicate_groups`), `duplicate_links`
     (records carrying `duplicate_of`), `related_normal_lessons` (resolved),
     `weak_records` (missing required fields), `archived`, `superseded`,
     `top_tempting_patterns`, plus `title`/`generated_at`/`guardrail`.
   - A record is **weak/incomplete** when it is missing any required field
     (`title`, `tempting_wrong_pattern`, `why_wrong`, `safer_alternative`).

2. **Markdown formatter** `format_anti_lesson_report_markdown(report) -> str`
   (pure): title + `generated_at`, counts, candidate table, duplicate warnings,
   related normal lessons (if any), weak/incomplete section, top patterns,
   archived/superseded, and the guardrail note verbatim:
   *"Anti-lessons are report-only in this phase. They are not used by active
   retrieval or CONTROL prompts."*

3. **Store-aware loader** `load_anti_lesson_report(*, repo_path, scope,
   repo_scope_id, include_global, generated_at=None)` — the only store-aware
   entry. Performs a single **read** (`lesson_store.list_lessons`), stamps
   `generated_at` via `_now_iso()`, and delegates to the pure builder. Never
   writes.

4. **Read-only route** `GET /lessons/anti/report` (`web/app.py`):
   - Query params: `repo_path?` (path-guarded like other lesson routes),
     `scope?`, `repo_scope_id?`, `include_global?`, `format?`.
   - JSON by default (`{ok, report}`); `format=markdown`/`md` adds a rendered
     `markdown` string. Reads storage only — never promotes/blocks/archives/
     merges, never calls CONTROL/Dream/patching/benchmark/model/subprocess/Docker.

5. **UI** (`web/templates/index.html`, additive only): an `antiLessonReportPanel`
   disclosure in Memory → Lessons with a "Refresh anti-lesson report" button,
   summary counts, and candidate/duplicate/weak sections rendered from the JSON
   report. Inert warning shown verbatim: *"Anti-lessons are report-only and are
   not used by CONTROL yet."* No CONTROL/retrieval toggles. Existing ids/handlers
   untouched.

---

## Explicitly out of scope (deferred)

- Live/active retrieval of anti-lessons and any CONTROL prompt integration
  (still gated behind `ANTI_LESSONS_ENABLED`, which stays off).
- Reverse Dream execution and retrieval shadow mode (this slice only makes them
  *auditable* first).
- Automatic anti-lesson creation; any model/API call, patch generation,
  benchmark scoring, Dream execution, subprocess/Docker/network.
- Auto-promotion / any mutation of anti-lessons.

---

## Safety proof (tests)

`tests/test_anti_lesson_reports.py` pins the guarantees:

- counts by status (candidate/active/blocked) and scope (global/repo); normal
  lessons are ignored by the anti report;
- duplicate `duplicate_links` + anti-aware `duplicate_groups`; `evidence_refs` and
  `related_lesson_ids` surface (with related normal lessons resolved);
  `top_tempting_patterns` aggregated; archived/superseded listed; weak records
  flagged with the missing field;
- Markdown contains the title, the guardrail note, and the expected sections;
- the route returns the JSON report (and Markdown on request) and **does not
  mutate** any lesson file (byte-for-byte snapshot equal before/after, including
  for a duplicate pair — the report never writes the `duplicate_of` link);
- after the report route is hit, `list_active_lessons` and `find_active_lessons`
  still exclude anti-lessons, and the CONTROL prompt contains none of them;
- `control_engine.py` and `prompter.py` do not reference `anti_lesson_reports`
  (no coupling); both files are unmodified by this slice;
- an AST guard asserts `anti_lesson_reports.py` imports/calls no forbidden sinks
  (model/API, patch, benchmark, Dream, subprocess, Docker) and never calls any
  mutating store op (`promote_lesson`/`block_lesson`/`archive_lesson`/
  `create_merge`/`save_*`/`patch_lesson_fields`) or `build_control_prompt`.
