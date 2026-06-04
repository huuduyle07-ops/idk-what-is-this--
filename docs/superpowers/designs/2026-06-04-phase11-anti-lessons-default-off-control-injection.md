# Phase 11.7c — Default-Off CONTROL Anti-Lesson Injection (two-key gate)

_Checkpoint design — 2026-06-04_

## Motivation

Phases 11.1–11.7b kept anti-lessons completely inert: stored as a first-class
lesson kind, shadow-retrieved (11.6), previewed as a CONTROL block (11.7a), and
shown beside CONTROL in a read-only report (11.7b) that *proved*
`build_control_prompt` output was byte-identical. 11.7c is the **first
behavior-changing slice**: it lets the anti-lesson block actually reach the
CONTROL prompt — but only behind a deliberately conservative gate.

## Two-key gate

Injection happens **only when BOTH keys are turned**:

1. **Server flag** — `config.ANTI_LESSONS_CONTROL_ENABLED` is true (default off).
2. **Per-request flag** — the specific call passes
   `anti_lesson_control_requested=True`.

If **either** key is missing, the helper returns `""` and the CONTROL prompt is
**byte-identical to Phase 11.7b**. The gate lives in one place
(`core/anti_lesson_control_injection.build_anti_lesson_control_block`), which
re-checks the server flag fail-closed; `control_engine` additionally short-circuits
on `requested=False` *before importing anything*, so the default path is import-free.

## Default disabled / per-run only

- The flag defaults **false** (`os.getenv("ANTI_LESSONS_CONTROL_ENABLED", "false")`).
- The opt-in is **per-run**: a UI checkbox ("Include anti-lesson warning block for
  this run") sends a single per-request field. There is **no global UI toggle**,
  **no persistent/saved setting**, **no auto-enable**, and **no route that flips
  config/env or writes a setting file**. The UI warning states verbatim:
  *"Requires server flag ANTI_LESSONS_CONTROL_ENABLED=true. Does not save a global
  setting."*

## What it does

- **`core/anti_lesson_control_injection.py`** (new):
  - `build_anti_lesson_control_block(repo_path, user_query, *, requested=False, max_items=3)`
    — the two-key gate. Reads anti-lessons read-only via the 11.6 shadow loader,
    projects them through the 11.7a preview builder, and renders an
    `[ANTI-LESSONS / DO NOT REPEAT — EXPERIMENTAL]` block with, per item,
    `tempting_wrong_pattern` / `why_wrong` / `safer_alternative` /
    `evidence_refs` (when available). Returns `""` on any disabled key, empty
    match set, or error. **Small by design:** default 1–3 items, hard cap 5.
  - `summarize_anti_lesson_control_injection(...)` — the *only* metadata a
    runner/session may record: `requested` / `enabled_by_config` / `injected` /
    `selected_count`. Never a global preference.
  - Imports only `core.anti_lesson_prompt_preview` and
    `core.anti_lesson_retrieval_shadow` (verified by the AST forbidden-sink guard).
- **`core/control_engine.py`**: `build_control_prompt` gains two keyword-only,
  default-off params (`anti_lesson_control_requested=False`,
  `anti_lesson_control_max_items=3`). A new `_anti_lessons_prompt_block` helper
  produces `""` by default; the block is appended **right after `[ACTIVE LESSONS]`**
  (`{lessons_block}{anti_lessons_block}`) in all three prompt branches.
- **Route** `POST /generate_patch`: reads the per-request field
  `anti_lesson_control_requested`, forwards it to `build_control_prompt`, and
  returns the per-run metadata transiently. It never writes the server flag.
- **Source of anti-lessons**: the existing 11.6 shadow retrieval / 11.7a preview
  builder. It does **not** use `list_active_lessons` for anti-lessons, does not
  change normal active-lesson retrieval, does not make anti-lessons
  active-retrieval eligible, and does not promote anything.

## Injection location

Appended immediately after the `[ACTIVE LESSONS]` advisory block:

```
[ANTI-LESSONS / DO NOT REPEAT — EXPERIMENTAL]
These are warnings about tempting but wrong patterns. Use them only to avoid repeating known bad fixes.

1. <title>
   - tempting_wrong_pattern: ...
   - why_wrong: ...
   - safer_alternative: ...
   - evidence_refs: ...
```

## Disabled path is byte-identical (the most important property)

Tests pin the full matrix against the pre-11.7c baseline prompt:

| server flag | request flag | result |
| --- | --- | --- |
| false | false | byte-identical to 11.7b |
| false | true  | byte-identical to 11.7b |
| true  | false | byte-identical to 11.7b |
| true  | true  | block injected (only this case) |

## No mutation / promotion / creation

- Byte-snapshot test: building the prompt with injection on leaves every
  `.agent/lessons/**/*.json` unchanged.
- Anti-lessons stay **excluded** from `list_active_lessons` / `find_active_lessons`
  even after an injected build (governed by the independent `ANTI_LESSONS_ENABLED`,
  which stays off) — including the worst case of an explicitly promoted anti-lesson.
- AST forbidden-sink guard on the new module: no model/API, patch, benchmark,
  Dream, mutation-oracle, subprocess, or Docker imports/calls, and none of
  `save_candidate_lesson` / `promote_lesson` / `create_merge` / `patch_lesson_fields`.

## Benchmark safety

Benchmarks call `build_control_prompt` **without** the new request flag, so their
prompts are byte-identical to before. `benchmark --check` remains 50 checked, 0
errors. **This flag must be benchmarked on a held-out set before any default-on
consideration.**

## Out of scope (future)

- Any default-on behavior — this stays per-run + server-flag gated.
- Promotion/activation of anti-lessons or making them active-retrieval eligible.
- Persisted/global UI settings for anti-lesson injection.

## Validation

- `python -m compileall core web tests`
- `python -m pytest tests/test_anti_lesson_control_injection.py -q --basetemp .fresh_tmp_anti_lessons_11_7c`
- `python -m pytest tests -q --basetemp .fresh_tmp_phase11_7c_full`
- `python -m benchmarks.run_benchmarks --check`
