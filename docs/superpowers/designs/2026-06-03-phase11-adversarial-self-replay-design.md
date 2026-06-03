# Phase 11.0 Adversarial Self-Replay Design Audit

**Date:** 2026-06-03

**Scope:** Design and characterization only. No anti-lesson ranking, no Dream route changes, no lesson promotion or retrieval changes, no CONTROL prompt changes, no model/API calls, and no benchmark scoring changes.

---

## Goal

Prepare the real Phase 11 adversarial self-replay work by documenting where anti-lessons could live and which default-off guardrails must prevent them from becoming active knowledge or CONTROL context accidentally.

Phase 11 is about preserving useful negative evidence: "this tempting patch pattern looked plausible but failed." This audit intentionally stops before wiring that evidence into retrieval, ranking, Dream, CONTROL, or benchmark scoring.

---

## Current Lesson Schema

Lessons are JSON records persisted by `core/lesson_store.py`.

Current storage buckets:

- `.agent/lessons/candidate/`
- `.agent/lessons/active/`
- `.agent/lessons/blocked/`
- `.agent/lessons/repos/<repo_scope_id>/{candidate,active,blocked}/`

Current top-level fields:

- `id`
- `status`: currently `candidate | active | blocked`
- `scope`: `global | repo`
- `repo_scope_id`
- `repo_path_hint`
- `created_at`
- `updated_at`
- `source`
- `source_report`
- `case_name`
- `title`
- `summary`
- `tags`
- `candidate`
- `evaluation`
- `active_knowledge_allowed`

Important current invariant:

`active_knowledge_allowed` is true only when a record lives in the active bucket. Candidate and blocked records normalize to `active_knowledge_allowed=false` even if the quality gate thought the candidate was auto-approvable.

---

## Current Retrieval Flow

Active lesson retrieval is isolated in `core/lesson_retrieval.py`.

The flow is:

1. `control_engine._lessons_prompt_block()` checks `config.LESSON_RETRIEVAL_ENABLED`.
2. If enabled, CONTROL imports `core.lesson_retrieval`, not `core.lesson_store`.
3. `lesson_retrieval.find_active_lessons()` calls `list_active_lessons()`.
4. `list_active_lessons()` calls `lesson_store.list_lessons(status=STATUS_ACTIVE, repo_path=repo_path)`.
5. `list_active_lessons()` defensively filters records where:
   - `record["status"] != "active"`
   - `record["active_knowledge_allowed"] is not True`
   - duplicate lesson IDs have already been emitted
6. `format_lessons_for_prompt()` renders a compact prompt block without dumping raw candidate payloads.

Default behavior:

- `LESSON_RETRIEVAL_ENABLED=false`
- No active lessons are injected into CONTROL by default.
- Candidate and blocked lessons are not active knowledge.

Existing characterization coverage:

- `tests/test_lesson_retrieval.py` verifies candidate and blocked lessons are not returned by `find_active_lessons()`.
- `tests/test_control_prompt_lessons.py` verifies candidate lessons do not enter CONTROL when retrieval is enabled.
- `tests/test_dream_lesson_proposal_routes.py` verifies Dream-created lesson candidates are not auto-promoted even when `LESSON_AUTO_ACTIVE=True`.

This audit adds a matching CONTROL characterization for blocked lessons.

---

## Where Anti-Lessons Could Live

Anti-lessons should use the existing lesson-store boundary rather than a parallel ad hoc store.

Proposed additive fields:

```json
{
  "kind": "lesson",
  "status": "candidate",
  "source": "benchmark"
}
```

Allowed `kind` values:

- `lesson`: positive advisory knowledge, current default for legacy records
- `anti_lesson`: negative evidence about a tempting but harmful patch, diagnosis, route, prompt pattern, or workflow move

Allowed `status` values:

- `candidate`: recorded evidence, not active knowledge
- `active`: explicitly promoted and eligible for future retrieval, subject to kind-specific gates
- `blocked`: rejected or unsafe evidence, never active knowledge
- `superseded`: retained for audit/history but replaced by a newer record, never active knowledge

Allowed `source` values:

- `benchmark`: produced from benchmark failures, comparisons, or post-run audits
- `dream`: produced from Dream artifacts or Dream revalidation evidence
- `replay`: produced from adversarial self-replay traces
- `manual`: created by explicit operator action

Backward compatibility:

- Missing `kind` should be interpreted as `lesson`.
- Current records with `status in {candidate, active, blocked}` remain valid.
- `superseded` should not be added to `LESSON_STATUSES` until the real Phase 11 implementation needs it and has tests.

Storage options:

1. Reuse existing buckets and add `kind`.
   - Pro: minimal migration, existing candidate/active/blocked safety gates still apply.
   - Con: list views and future retrieval must filter `kind` carefully.
2. Add kind sub-buckets such as `lessons/anti_lesson/candidate`.
   - Pro: physically separates positive and negative evidence.
   - Con: larger migration and more retrieval/listing surface area.

Recommended Phase 11 direction:

Use existing buckets with an additive `kind` field first. It preserves current path traversal, scope, promotion, and active-knowledge invariants while keeping anti-lessons inert by default.

---

## CONTROL Exclusion Rules

Anti-lessons must stay out of CONTROL by default.

Required default behavior:

- `ANTI_LESSONS_ENABLED=false`
- `LESSON_RETRIEVAL_ENABLED=false` remains the existing master gate for any active lesson block.
- Even if `LESSON_RETRIEVAL_ENABLED=true`, `anti_lesson` records must not be included unless `ANTI_LESSONS_ENABLED=true`.
- Candidate, blocked, and superseded anti-lessons must never be included in CONTROL.
- Active anti-lessons should not be formatted by `format_lessons_for_prompt()` until a separate prompt format is designed.

Recommended future retrieval boundary:

- Keep `find_active_lessons()` as positive-lesson-only.
- Add a separate future function such as `find_active_anti_lessons()` only after a design for prompt wording, ranking, and safety review exists.
- Do not overload the existing `[ACTIVE LESSONS]` block with anti-lessons.

Reason:

Negative examples can poison prompts if they are rendered as ordinary advice. They need separate phrasing, opt-in flags, and ideally replay-local use before CONTROL exposure.

---

## Proposed Flags

Add these only in the real implementation phase, all disabled by default:

```python
ANTI_LESSONS_ENABLED = os.getenv("ANTI_LESSONS_ENABLED", "false").lower() not in {"0", "false", "no"}
REVERSE_DREAM_ENABLED = os.getenv("REVERSE_DREAM_ENABLED", "false").lower() not in {"0", "false", "no"}
ADVERSARIAL_SELF_REPLAY_ENABLED = os.getenv("ADVERSARIAL_SELF_REPLAY_ENABLED", "false").lower() not in {"0", "false", "no"}
```

Flag responsibilities:

- `ANTI_LESSONS_ENABLED`: permits anti-lesson reads in future, non-CONTROL experimental surfaces. It must not automatically inject anti-lessons into CONTROL.
- `REVERSE_DREAM_ENABLED`: permits future Dream variants that intentionally search for tempting wrong moves. It must not create active lessons or alter Dream routes by default.
- `ADVERSARIAL_SELF_REPLAY_ENABLED`: permits future replay generation/evaluation. It must not alter benchmark scoring, patch scoring, or lesson retrieval by default.

Recommended gate order:

1. Write anti-lesson candidates only when an explicit experimental action is enabled.
2. Keep candidates out of active knowledge.
3. Require explicit promotion to `active`.
4. Require `ANTI_LESSONS_ENABLED=true` for any anti-lesson retrieval surface.
5. Require a separate future CONTROL-specific flag before prompt injection.

---

## Candidate Record Shape

Future anti-lesson candidate example:

```json
{
  "kind": "anti_lesson",
  "status": "candidate",
  "source": "replay",
  "title": "Tempting duplicate-file fix failed validation",
  "summary": "Do not patch the same-named fixture config when the import path points at app/config.py.",
  "candidate": {
    "failure_mode": "wrong_file_temptation",
    "tempting_action": "edit tests/fixtures/config.py",
    "observed_failure": "validation still imports app/config.py",
    "counter_evidence": ["import traceback", "validation command output"],
    "case_name": "python_duplicate_filename_temptation",
    "language": "python",
    "changed_files": ["tests/fixtures/config.py"],
    "validation_ok": false
  },
  "active_knowledge_allowed": false
}
```

This is deliberately candidate-only. It records what went wrong without treating the negative example as operational guidance.

---

## Non-Goals For Phase 11.0

This audit does not implement:

- anti-lesson ranking
- anti-lesson retrieval
- anti-lesson prompt formatting
- anti-lesson promotion workflows
- reverse Dream routes
- adversarial replay execution
- benchmark scoring changes
- CONTROL prompt changes
- model/API calls

---

## Characterization Tests

Useful existing and added tests:

- `tests/test_lesson_retrieval.py::test_list_active_lessons_returns_only_active`
- `tests/test_lesson_retrieval.py::test_candidate_lessons_not_returned_by_find`
- `tests/test_lesson_retrieval.py::test_blocked_lessons_not_returned_by_find`
- `tests/test_lesson_retrieval.py::test_tagged_lesson_safety_still_filters_candidate_and_blocked`
- `tests/test_control_prompt_lessons.py::test_retrieval_enabled_candidate_only_omits_block`
- `tests/test_control_prompt_lessons.py::test_retrieval_enabled_blocked_only_omits_block`
- `tests/test_dream_lesson_proposal_routes.py::test_create_lesson_candidate_never_auto_promotes`

These tests document the current safety boundary that Phase 11 must preserve.

---

## Validation Plan

Because this phase changes only docs and characterization tests:

1. Run `python -m compileall tests/test_control_prompt_lessons.py`.
2. Run focused tests:
   - `pytest tests/test_control_prompt_lessons.py tests/test_lesson_retrieval.py tests/test_dream_lesson_proposal_routes.py -q`
3. Run full `pytest` only if feasible.
4. Run benchmark check and confirm it remains `50/0`.

Expected result:

- No production behavior changes.
- Candidate/blocked lessons remain outside active retrieval.
- Dream-created candidates remain candidates.
- CONTROL remains free of anti-lessons and inactive lessons by default.
