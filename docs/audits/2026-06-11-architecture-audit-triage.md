# Architecture Audit Triage Record - 2026-06-11

- Audit name: C.A.T.T.U.S Architecture Audit — 2026-06-11
- Source audit: `docs/CATTUS_ARCHITECTURE_AUDIT_2026-06-11.md`
- Purpose: convert the audit tsunami into a controlled backlog.

## Triage Rules

- Audit findings do not become work until accepted into a named phase.
- Safety fixes happen before consolidation.
- Freeze is preferred over deletion for report-only or test-pinned code.
- This record is documentation only. It does not authorize runtime behavior changes, patching changes, lesson logic changes, module deletion, model runs, web UI work, or code merges.

## Status Vocabulary

- `already_fixed`: confirmed urgent item already closed and should not be reopened.
- `accepted_now`: near-term Track A work, still requiring characterization and verification before edits.
- `accepted_later`: valid backlog candidate, not current work.
- `rejected`: audit finding explicitly declined.
- `frozen`: keep as-is unless a future accepted phase redesigns the owning area.
- `needs_verification`: plausible finding that must be checked before becoming accepted work.

## Already Fixed

Status: `already_fixed`

### A.5 Universal Patch Safety Chokepoint for Single-file Apply

- Single-file `patch_candidate` path now calls `evaluate_patch_safety` before write.
- Validation does not run after a safety block.
- Rollback is not needed for the blocked path because no write happened.

### A.6 LESSON_AUTO_ACTIVE Candidate-only Guard

- `create_lesson_from_proposal` forces `LESSON_AUTO_ACTIVE` off around `save_candidate_lesson`.
- Proposal lessons cannot bypass the human Promote step.

### A.8 Shared Post-processing Gate Battery

- `main.py` and `web/runner.py` now call `core.postprocess_gates.run_postprocess_gate_battery(...)`.
- The shared helper preserves the former post-processing gate order.
- Caller-specific behavior, including web harness decisions, remains outside the shared helper.

## Accepted Now

Status: `accepted_now`

### A.9 Docs Truth Pass

- Update README/debug matrix wording after A.5.
- Correct benchmark count truth.
- Refresh technical debt or blueprint status only if stale.
- Confirm this phase changes docs only.

## Accepted Later

Status: `accepted_later`

### Proposal → Lesson Entry Consolidation

- Move toward one creation function.
- Use a unified source label and `source_key` dedup scheme.
- Do not merge the dual Dream lesson endpoints.
- **A.11 consolidation plan**: see `.agent/audits/*_proposal-lesson-consolidation-plan.{json,md}`
  — canonical target selected (`create_lesson_from_proposal`); future phases A.12/A.13/A.14 defined.

### Track F Consolidation

- Consolidate `mode_router` into `goal_brief_autocomplete`.
- Consolidate `handoff_composer` into `handoff_notes`.
- Unify prompt-builder logic and the forbidden-files constant.
- Fix or remove the broken F.1 → Goal Brief `problem_type` bridge.

### Dream Hygiene

- Cut the dead `write_report_markdown` alias target and stale `morning_report` log.
- Unify mode alias tables.
- Optionally extract case-idea research.

### Project Evolution B.5-B.7 Collapse

- Consider only after hash-chain implications are planned.
- Preserve B.4 approval, B.8 sandbox validation, and B.10 review gate.

### `web/app.py` Blueprint Extraction

- Extract Dream and lessons route groups first.

## Rejected

Status: `rejected`

### Merge Dual Dream Lesson Endpoints

- Rejected because the audit verifier refuted the finding.
- The split is intentional: `ready_to_apply` and non-ready items need different evidence paths.

## Frozen

Status: `frozen`

### `scripts/seed_lessons_from_benchmark.py`

- This is the only benchmark-to-lesson path.
- It is rarely used, but should not be cut casually.

### `reverse_dream_planner`

- Read-only route only.
- No execution wiring.

### Report-only Anti-lesson, Memory-temperature, and Experiment Dogfood Families

- These are inert or report-only.
- Tests and scripts may depend on them.

### `route_request`

- No production caller is currently known.
- Tests pin it, so freeze unless the router is redesigned.

### External Queue B.12-B.14

- Safe as-is.
- Do not add live automation before B.15/index and later gates.

## Needs Verification

Status: `needs_verification`

### `/lessons/create-candidate-from-proposal` Has No UI Caller

- Verify no external or manual client relies on it before cutting.

### `repo_inventory` Orphan Claim

- Verify current imports before cutting.

### Project Evolution B.5-B.7 Duplication Amount

- Verify the current duplication before collapsing stages.

### `web/app.py` Route Counts and Blueprint Target Grouping

- Verify the current route state before extraction.

## Cleansing Rules

- Never delete enforcement core during cleanup.
- Never weaken `patch_safety`, `lesson_quality`, `lesson_store` promotion, temp-clone isolation, replay, or Project Evolution B.4/B.8/B.10 gates.
- Any new phase that re-solves an existing problem must retire, delegate to, or explicitly freeze the older path.
- One audit may create at most one urgent safety fix, one consolidation phase, and one deferred note.
- Expensive audits require a budget and stop condition before running.

## Recommended Next Track A Phases

1. A.9 Docs Truth Pass.
2. A.10 Proposal/Lesson Entry Dedup Audit, report-only.
3. Decide whether to move to consolidation or H.1 cost pressure.
