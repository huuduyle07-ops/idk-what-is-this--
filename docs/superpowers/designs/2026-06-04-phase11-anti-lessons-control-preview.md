# Phase 11.7a — Anti-Lesson CONTROL Block Formatter (Pure Preview Only)

_Checkpoint design — 2026-06-04_

## Motivation

Phases 11.1–11.6 built the inert, read-only anti-lesson lifecycle: kind-aware
storage, manual creation, duplicate/merge handling, a report, a Reverse Dream
dry-run planner, and — most recently — **shadow retrieval**, which can *rank*
anti-lessons for a query without touching live behavior.

The remaining question before any future CONTROL integration is purely
presentational: **what would an anti-lesson CONTROL block actually look like?**
11.7a answers that with a *pure formatter* and a read-only preview surface. It
renders the block; it does not wire it into anything.

## Hard guardrails (unchanged from 11.1–11.6)

This phase performs **no execution and no live behavior change**. Specifically it
does **not**:

- inject anything into CONTROL or call `build_control_prompt`;
- change active retrieval (anti-lessons remain retrieval-ineligible and
  CONTROL-invisible);
- generate or apply a patch;
- run Dream, the mutation oracle, benchmarks, or any model / API call;
- spawn a subprocess, touch Docker, or open the network;
- create, promote, block, archive, or merge any lesson;
- write to the lesson store at all.

Anti-lessons must **never** become active/retrieval-eligible or CONTROL-visible.

## What it does

- **`core/anti_lesson_prompt_preview.py`** (pure):
  - `build_anti_lesson_control_block_preview(shadow_result, *, max_items=3)` —
    takes the dict returned by the 11.6 shadow retrieval helpers and projects each
    `selected_matches` row into a CONTROL-block item
    (`lesson_id`, `title`, `tempting_wrong_pattern`, `why_wrong`,
    `safer_alternative`, `evidence_refs`, `duplicate_of`, `shadow_only: true`).
    Bounds the block to `max_items` (default 3, clamped `[1, 50]`). Returns a dict
    carrying the explicit `label` = `PREVIEW ONLY / NOT INJECTED INTO CONTROL`,
    `preview_only: true`, and the full `blocked_actions` list.
  - `format_anti_lesson_control_block_markdown(preview)` — renders the preview as
    Markdown: title, the `PREVIEW ONLY / NOT INJECTED INTO CONTROL` label, query,
    guardrail, per-item tempting/why_wrong/safer/evidence/duplicate_of, blocked
    actions, and a trailing guardrail line.
  - Both functions are pure: they take already-built data and never read or write
    the store, never call a model, never execute anything. The module imports only
    `typing` (verified by the AST forbidden-sink guard).

- **Route** `GET /lessons/anti/control-preview?query=...` (read-only): loads
  matching anti-lessons via the existing shadow loader
  (`load_anti_lesson_shadow_retrieval`), then formats a preview. `query` required
  (400 otherwise); `max_items` bounded `[1, 50]`; `repo_path` path-guarded;
  `?format=markdown|md` adds a rendered Markdown view. It never calls
  `build_control_prompt` and never mutates the store.

- **UI** — a small "Anti-Lesson CONTROL Preview" panel with a query input, a
  max-items input, and a **Preview** button. Warning verbatim:
  *"Preview only. This block is not injected into CONTROL."* No
  enable/toggle/inject/promote/run controls.

## Out of scope (future, gated)

- Any actual CONTROL injection of anti-lessons (default-off, operator-gated).
- Contrastive ("don't do X") prompt construction inside `control_engine`.
- Promotion/activation of anti-lessons.

These remain blocked on the held-out eval set (§B) and the patch-minimality
metric (§C) per the roadmap.

## Safety proof (how the tests pin it)

- **Pure / read-only:** byte-snapshot test asserts the route leaves every
  `.agent/lessons/**/*.json` unchanged (JSON + Markdown calls).
- **CONTROL unchanged:** after a preview call, a promoted anti-lesson still does
  not appear in `list_active_lessons` / `find_active_lessons`, and a built CONTROL
  prompt (with `LESSON_RETRIEVAL_ENABLED=True`) contains none of its markers.
- **No back-reference:** `control_engine.py`, `prompter.py`, and
  `lesson_retrieval.py` do not import `anti_lesson_prompt_preview`.
- **No forbidden sinks:** AST guard asserts the module imports none of the
  forbidden roots/modules (models, patching, benchmarks, Dream, mutation oracle,
  subprocess, Docker, network) and calls none of the forbidden functions
  (`build_control_prompt`, `promote_lesson`, `save_candidate_lesson`,
  `create_merge`, …).
- **UI is preview-only:** the panel slice contains the required warning and no
  enable/inject/promote/toggle/run controls.

## Validation

- `python -m compileall core web tests`
- `python -m pytest tests/test_anti_lesson_prompt_preview.py -q`
- `python -m pytest tests -q`
- `python -m benchmarks.run_benchmarks --check`
