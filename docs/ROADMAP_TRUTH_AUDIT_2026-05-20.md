# Roadmap Truth Audit - 2026-05-20

Source reviewed: `D:/Downloads/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`.

This audit records which roadmap/Gemini claims matched the current codebase before
the replay-artifact work. It is intentionally documentation-only.

## Confirmed In Code

- Brain Stamp exists and is used in benchmark/reporting paths:
  `core/brain_stamp.py`, `benchmarks/run_benchmarks.py`,
  `core/benchmark_web.py`.
- Code DNA is not isolated; it is computed during indexing and injected into
  control prompts through CLI/web runners:
  `core/code_dna.py`, `core/indexer.py`, `cli/interactive.py`,
  `web/runner.py`, `core/control_engine.py`.
- Phantom Limb is wired into repository indexing and control context:
  `core/phantom_limb.py`, `core/indexer.py`, `core/repo_librarian.py`.
- Patch safety is deterministic and apply-time guarded in web patch routes:
  `core/patch_safety.py`, `web/app.py`.
- Lesson storage/retrieval exists and remains manual-safe; proposal-to-lesson
  creation is explicit/manual through `scripts/create_lesson_from_proposal.py`.

## Stale Or Overstated Claims

- The roadmap text says lesson retrieval uses per-repo plus global scope union.
  The current dirty worktree has changed `core/lesson_store.py` and
  `core/lesson_retrieval.py` toward a global-only lesson bucket. This plan does
  not resolve that product decision; it only records the drift.
- Gemini's claim that `brain_stamp.py`, `code_dna.py`, `phantom_limb.py`, and
  `agent_memory.py` are "completely isolated" is inaccurate. Some are passive,
  but several are wired into indexing, prompts, reports, or manual memory flow.
- The repo did not have a `BrainVersionStamp`, `RepoStateManager`,
  `ExecutionState`, `ReplayBundle`, `ArtifactBundle`, or event bus before this
  work.
- The existing `patching/patch_plan_executor.py` was an atomic function with
  LIFO rollback, not a run lifecycle manager.
- LLM critique exists as an advisory/local critique surface, not as an
  authoritative apply-time safety gate.

## Decision For This Increment

- Preserve existing deterministic safety gates.
- Add stable run provenance and replay artifacts first.
- Keep lesson auto-creation out of v1; review real replay artifacts before
  planning Phase 6.4 automation.
