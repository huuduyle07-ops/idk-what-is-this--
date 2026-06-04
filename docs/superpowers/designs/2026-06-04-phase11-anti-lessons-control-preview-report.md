# Phase 11.7b — Default-Off CONTROL Anti-Lesson Preview Report

_Checkpoint design — 2026-06-04_

## Motivation

Phase 11.6 added anti-lesson **shadow retrieval** (rank anti-lessons for a query)
and 11.7a added a pure **CONTROL block preview** (render what the block would look
like). 11.7b stitches them together into a single read-only **report** that an
operator can view *beside* real CONTROL/debug context — so the comparison
"this is your CONTROL prompt / this is the anti-lesson block that is **not** in it"
is visible in one place.

The point is presentational and comparative only. Nothing is injected. The actual
`build_control_prompt` output is provably unchanged.

## Hard guardrails (unchanged from 11.1–11.7a)

This phase performs **no execution and no live behavior change**. It does **not**:

- inject anything into CONTROL or call `build_control_prompt`;
- change active retrieval (anti-lessons remain retrieval-ineligible and
  CONTROL-invisible);
- generate or apply a patch;
- run Dream, the mutation oracle, benchmarks, or any model / API call;
- spawn a subprocess, touch Docker, or open the network;
- create, promote, block, archive, or merge any lesson;
- write to the lesson store at all.

## What it does

- **`core/anti_lesson_control_report.py`**:
  - `build_anti_lesson_control_preview_report(query, records, *, context=None, max_items=3, generated_at=None)`
    (pure) — runs the 11.6 shadow matcher over `records` (generous pool) and the
    11.7a preview-block builder (bounded to `max_items`), then assembles a report
    dict containing: `query`, `generated_at`, `guardrail`,
    `control_prompt_status="unchanged"`, `anti_lesson_injection="not_injected"`,
    `notes` (the two required statements), the full `shadow_retrieval` result, the
    full `preview_block`, `blocked_actions`, and `report_only: true`.
  - `format_anti_lesson_control_preview_report_markdown(report)` (pure) — renders
    the query, guardrail, a **CONTROL vs anti-lesson preview** comparison table
    (actual CONTROL = *unchanged*; block = *preview-only, not_injected*), the two
    statements, the selected anti-lessons, the embedded 11.7a preview block, and
    the blocked-actions list.
  - `load_anti_lesson_control_preview_report(...)` — the only store-aware entry:
    one `lesson_store.list_lessons` **read**, filters to `kind="anti_lesson"`,
    stamps `generated_at`, delegates. Never writes; never calls
    `build_control_prompt`.
  - Imports only `core.anti_lesson_prompt_preview`,
    `core.anti_lesson_retrieval_shadow`, and `core.lesson_store` (verified by the
    AST forbidden-sink guard).

- **Route** `GET /lessons/anti/control-preview-report?query=...` (read-only):
  `query` required (400 otherwise); `max_items` bounded `[1, 50]`; `repo_path`
  path-guarded; `?format=markdown|md` adds a rendered Markdown view. It does **not**
  call `build_control_prompt`.

- **UI** — an "Anti-Lesson CONTROL Preview Report" panel with a query input, a
  max-items input, and a **Preview report** button. Warning verbatim:
  *"Report only. The actual CONTROL prompt is unchanged."* It shows the
  CONTROL-vs-block comparison, the selected anti-lessons, and the preview block. No
  enable/inject/apply/promote/run controls.

## Required statements (verbatim)

- "This report does not modify build_control_prompt output."
- "Anti-lessons are not injected into CONTROL in this phase."

## Out of scope (future, gated)

- **11.7c**: a *default-off* injection flag that would actually append the
  anti-lesson block to CONTROL when explicitly enabled by an operator. Not in this
  phase — there is no injection path here, default-off or otherwise.
- Promotion/activation of anti-lessons.

These remain blocked on the held-out eval set (§B) and the patch-minimality
metric (§C) per the roadmap.

## Safety proof (how the tests pin it)

- **CONTROL byte-identical:** `build_control_prompt` is captured before and after
  the route call (with a promoted anti-lesson and `LESSON_RETRIEVAL_ENABLED=True`)
  and asserted **equal**; the anti-lesson's marker never appears.
- **Read-only:** byte-snapshot test asserts the route leaves every
  `.agent/lessons/**/*.json` unchanged (JSON + Markdown calls).
- **Active retrieval clean:** a promoted anti-lesson still does not appear in
  `list_active_lessons` / `find_active_lessons` after the report call.
- **No back-reference:** `control_engine.py`, `prompter.py`, and
  `lesson_retrieval.py` do not import `anti_lesson_control_report`.
- **No forbidden sinks:** AST guard asserts the module imports none of the
  forbidden roots/modules and calls none of the forbidden functions
  (`build_control_prompt`, `promote_lesson`, `save_candidate_lesson`,
  `create_merge`, `patch_lesson_fields`, …).
- **UI is report-only:** the panel slice contains the required warning and no
  enable/inject/apply/promote/run controls.

## Validation

- `python -m compileall core web tests`
- `python -m pytest tests/test_anti_lesson_control_preview_report.py -q`
- `python -m pytest tests -q`
- `python -m benchmarks.run_benchmarks --check`
