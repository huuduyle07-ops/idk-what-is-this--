# AI Coding Agent/Mentor — Operating Roadmap 2026-06

## Purpose

This roadmap is the post-stabilization operating roadmap for C.A.T.T.U.S / AI Coding Mentor.

The old roadmap remains the historical build log:

- AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md

This roadmap focuses on what to improve next after the Phase 13 stabilization and UI presentation freeze.

---

## Current Position

C.A.T.T.U.S is currently strongest at:

- debugging
- repair
- explanation
- validation
- evidence-grounded patching
- benchmark-based safety checks

It is weaker at:

- project creation
- broad migrations
- architecture evolution
- multi-file feature development

Reason:

The current system is optimized for small, evidence-first repair tasks. Creation and migration tasks require broader project understanding and full-file planning.

---

## Track A — Stabilized Debug Agent

Keep improving the existing debug/repair workflow.

Goals:

- keep patches small
- preserve evidence grounding
- improve speed/cost
- reduce UI complexity
- expand benchmark coverage

---

## Track B — Project Evolution Mode

New idea, not part of the frozen historical roadmap.

Purpose:

Support creation/migration tasks such as:

- migrating MiniLM embeddings to Semble/model2vec
- replacing storage backends
- changing project architecture
- adding multi-file features
- updating config/docs/tests together

Workflow:

1. Build project map
2. Read relevant full files
3. Produce architecture migration plan
4. Identify affected modules
5. Identify risks
6. Ask for approval
7. Generate controlled multi-file patch
8. Update tests/docs/config
9. Run validation
10. Produce rollback notes

Important rule:

Project Evolution Mode should be separate from Debug Mode.

Debug Mode should stay small, fast, and evidence-first.
Evolution Mode can read more files, but only when explicitly selected.

---

## Deferred Ideas

- Migration Planner
- Full-file project understanding mode
- Architecture change proposal generator
- Multi-file patch planner
- Rollback report generator
- Compatibility report generator