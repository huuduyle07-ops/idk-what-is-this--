# Phase 11.5 — Reverse Dream / Adversarial Replay Design

**Date:** 2026-06-04
**Phase:** 11.5
**Status:** Implemented (dry-run planning layer only)
**Scope:** Design + a *pure*, read-only planner that proposes future adversarial
replay targets. **No execution of any kind.** No Dream run, no mutation oracle
run, no benchmark run/scoring, no patch generation/apply, no model/API call, no
subprocess/Docker/network, no active-retrieval change, no CONTROL prompt change,
no auto-promotion, and **no automatic anti-lesson creation.**

---

## What "Reverse Dream / adversarial replay" means

> Pick past successful patches or lessons that look worth attacking later,
> explain *why* they are worth attacking, and produce a **safe plan** for a
> future adversarial run.

A normal *Dream* tries to make things work. A *Reverse Dream* would later try to
**break** something we currently trust — mutate a patched region, replay a
tempting wrong pattern, stress a high-confidence lesson — to discover where our
"knowledge" is actually fragile, and (eventually) mint an anti-lesson from the
failure.

**In this phase it only plans/reports. It must not actually attack anything.**

This slice is the *planning* half only. It reads existing local evidence
(lessons + their metadata) and emits a structured, human-readable **dry-run
plan**: which targets look worth attacking, why, and what a future adversarial
run *would* check. Executing that plan is explicitly out of scope.

---

## Hard guardrails (this phase)

- **Reverse Dream is not enabled.** There is no runner, no flag that turns it on,
  and no "Run Reverse Dream" button anywhere.
- **No adversarial execution yet** — the planner never patches, never runs a
  benchmark, never calls a model.
- **No mutation oracle run yet** — `core/mutation_oracle.py` is neither imported
  nor invoked by the planner.
- **No anti-lesson auto-creation yet** — the planner never calls
  `save_candidate_lesson` / `create_manual_anti_lesson` / any store write. It can
  *reference* existing anti-lessons as supporting evidence, nothing more.
- **No CONTROL integration** — `control_engine.py` / `prompter.py` are untouched
  and do not import this module; anti-lessons stay excluded from the CONTROL
  prompt and from active retrieval.
- **Future execution must be gated** behind explicit operator approval and a
  default-off config flag (proposed: `REVERSE_DREAM_ENABLED`, fail-closed via
  `getattr(config, "REVERSE_DREAM_ENABLED", False)`), to be introduced only in a
  later phase alongside an actual runner. Nothing in 11.5 reads or honors such a
  flag yet because nothing here executes.

Every emitted target carries the contract explicitly:

```json
"allowed_actions": ["report_only"],
"blocked_actions": ["run_dream", "run_mutation_oracle", "create_anti_lesson",
                    "patch", "benchmark", "model_call"]
```

---

## What this slice does

1. **Pure planner** (`core/reverse_dream_planner.py`):
   - `build_reverse_dream_plan(records, *, max_items=10, generated_at=None) -> dict`.
     Takes an already-loaded `records` list (normal + anti-lessons) and proposes
     adversarial-replay *targets*. Pure — no store access, no mutation, no model.
   - **Primary attack targets are normal lessons.** Anti-lessons are never
     primary targets; they are used only as *supporting evidence*
     (`related_anti_lessons`) and otherwise listed under `skipped`.
   - A normal lesson becomes a candidate target when it carries at least one
     deterministic **risk signal**:

     | signal | meaning (why worth attacking later) |
     | --- | --- |
     | `active_knowledge` | `active_knowledge_allowed=true` — live knowledge the agent relies on |
     | `high_confidence` | confidence / `evaluation.score` ≥ threshold — may be over-trusted |
     | `has_related_anti_lesson` | a related anti-lesson already describes a tempting wrong pattern |
     | `anti_lesson_duplicate_warning` | related anti-lessons carry duplicate signals |
     | `broad_patch` | backed by a broad/large patch (many files / many changed lines) |
     | `passed_validation` | passed validation once — re-check it still holds adversarially |
     | `weak_or_missing_validation_context` | weak evidence / missing validation context |

   - Returns a structured dict:
     ```
     {
       generated_at, guardrail, total_candidates,
       selected_targets: [{
         target_id, title, source, source_report,
         reason_to_attack, risk_signals, suggested_future_checks,
         related_anti_lessons,
         allowed_actions: ["report_only"],
         blocked_actions: [...],
       }],
       skipped: [{target_id, title, kind, reason}],
     }
     ```
   - Selection is deterministic: candidates sort by (risk-signal count desc,
     active-knowledge first, confidence desc, id asc), then the top `max_items`
     become `selected_targets`. `total_candidates` is the **full** candidate pool
     (before the cap); any candidate beyond the cap is moved to `skipped` with an
     explicit `exceeds max_items cap` reason — **no silent truncation.**

2. **Markdown formatter** `format_reverse_dream_plan_markdown(plan) -> str`
   (pure): title, `generated_at`, guardrail note, a selected-target table, and
   per-target `reason_to_attack` / risk signals / suggested future adversarial
   checks / blocked actions, plus the explicit statement:
   *"This is a dry-run plan. It does not run Dream, mutation oracle, benchmarks,
   models, patching, or anti-lesson creation."*

3. **Store-aware loader** `load_reverse_dream_plan(*, repo_path, scope,
   repo_scope_id, include_global, max_items, generated_at=None)` — the only
   store-aware entry. Performs a single **read** (`lesson_store.list_lessons`),
   stamps `generated_at` via `_now_iso()`, and delegates to the pure builder.
   Never writes.

4. **Read-only route** `GET /lessons/anti/reverse-dream-plan` (`web/app.py`):
   query params `repo_path?` (path-guarded like other lesson routes), `scope?`,
   `repo_scope_id?`, `include_global?`, `max_items?`, `format?`. JSON by default
   (`{ok, plan}`); `format=markdown`/`md` adds a rendered `markdown` string.
   Reads storage only — never executes anything.

5. **UI** (`web/templates/index.html`, additive only): a
   `reverseDreamPlanPanel` disclosure in Memory → Lessons titled
   "Reverse Dream Plan (dry run)" with a refresh button, a selected-target count,
   and the top candidates. Warning shown verbatim: *"Dry-run only. No adversarial
   execution or anti-lesson creation happens here."* There is **no** "Run Reverse
   Dream" button.

---

## Explicitly out of scope (deferred)

- Any Reverse Dream / adversarial **execution**: mutation oracle runs, patch
  apply, benchmark scoring, model calls, Dream runs.
- Automatic anti-lesson creation from adversarial findings (the eventual payoff —
  still gated, still future).
- CONTROL prompt / active-retrieval integration of anti-lessons.
- A `REVERSE_DREAM_ENABLED` config flag and operator-approval workflow (only
  meaningful once a runner exists; intentionally not added here).

---

## Safety proof (tests)

`tests/test_reverse_dream_planner.py` pins the guarantees:

- the planner selects active / high-confidence / broad-patch normal lessons as
  targets, and links related anti-lessons as supporting evidence;
- anti-lessons are never primary attack targets (they appear only under
  `related_anti_lessons` / `skipped`);
- every selected target reports `allowed_actions == ["report_only"]` and
  `blocked_actions` covering Dream / mutation oracle / anti-lesson creation /
  patch / benchmark / model;
- the Markdown carries the dry-run guardrail statement;
- the loader / route never mutate any lesson file (byte-for-byte snapshot equal
  before/after), and the route returns JSON (and Markdown on request);
- the UI panel exists with the dry-run warning and **no** run button;
- after the plan route is hit, `list_active_lessons` / `find_active_lessons`
  still exclude anti-lessons and the CONTROL prompt contains none of them;
- `control_engine.py` / `prompter.py` do not import the planner;
- an AST guard asserts the module imports/calls no forbidden sinks (model/API,
  patch, benchmark, Dream execution, mutation oracle, subprocess, Docker) and
  never calls any store write / `create_manual_anti_lesson` / `promote_lesson` /
  `build_control_prompt`.
