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

## Track A — Stabilized Debug Agent: cycle 1 complete

Keep improving the existing debug/repair workflow.

### A.1: Benchmark Failure Cause Classification / Environment-aware Summary

New observational per-case fields: 
- failure_kind 
- failure_kind_display 
- failure_cause 
- failure_evidence 

Examples now classified: 
- fork/exec ... Access is denied -> security_tool / SECURITY TOOL 
- Go temp executable blocked on Windows -> security_tool / SECURITY TOOL 
- g++: command not found -> toolchain / TOOLCHAIN - ordinary AssertionError -> code_unknown / CODE / UNKNOWN 

Scoring is unchanged: the runner only adds display fields after retry/skipped state is settled, and pass/fail still derives from the existing success / skipped logic. Tests also assert scoring fields and source benchmark reports are not mutated by summary/web rendering.

### A.2: Debug Workflow Stage Map and Contract
Stage list: Intake -> Context -> Proposal -> Safety -> Execution -> Validation -> Evidence -> Learning 

What changed: 
- Added immutable DebugWorkflowStage frozen dataclass metadata. 
- Added DEBUG_WORKFLOW_STAGES, get_debug_workflow_stages(), and canonical_stage_names(). 
- Added the full debug workflow map doc with modules, artifacts, approvals, guardrails, Replay, Benchmarks, Lessons, Anti-lessons, Harness Controls, and Failure Taxonomy coverage. 
- Added contract tests including unique names, exact order, doc phrase coverage, and AST import/call guard. 

UI changed: no. Behavior changed: no. The helper is not wired into runtime behavior and imports only __future__, dataclasses, and typing.

### A.3: Patch Minimality / Changed-files Visibility in Benchmark Tab

Goal: make benchmark reports answer:

Did it pass?
What source files were patched?
What generated artifacts were produced?
Were there unexpected mutations?
Was the patch minimal or suspiciously broad?

### A.4:  Latest Run Health Summary

Goal:
Add a compact latest-run health summary for benchmark reports so operators can understand benchmark health at a glance.

This is a reporting/UI slice. Do not change benchmark scoring, benchmark execution, patch behavior, validation behavior, CONTROL prompts, model routing, lessons, anti-lessons, or harness behavior.

Background:
A.1 added observational failure taxonomy fields:
- failure_kind
- failure_kind_display
- failure_cause
- failure_evidence

A.3 surfaced file-change scope fields:
- CLEAN
- GENERATED
- UNEXPECTED
- UNKNOWN

A.4 should combine these into a clear “Run Health” summary.

Scope:
- Add summary computation helper if useful.
- Improve Markdown benchmark report summary.
- Improve web Benchmark tab latest/detail summary.
- Reuse existing benchmark report JSON fields.
- Gracefully support old reports missing new fields.
- Add tests.

### Goals:

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

### B.1: Project Evolution Mode Contract + Project Map Upgrade Plan.

Goal:
Define Project Evolution Mode as a separate broad-change workflow for migrations, architecture changes, dependency/provider swaps, and multi-file feature evolution.

This is a docs/metadata/test slice only.
Do not wire Project Evolution Mode into runtime patch generation yet.

Important:
C.A.T.T.U.S already has project-map / repo-map / repo-librarian / indexer / graph capability.
B.1 must not create a competing second project-map system.
B.1 should document how existing mapping/search components will be reused or upgraded for Evolution Mode.

Debug Mode vs Project Evolution Mode:

Debug Mode:
- small
- evidence-first
- bug/patch oriented
- minimal context
- minimal file reads
- does not read broad/full-project files by default

Project Evolution Mode:
- broad project map
- architecture understanding
- selected full-file reading when justified
- impact analysis before patching
- migration plan before patching
- human approval before multi-file patch generation

Scope:
- Add docs/project_evolution_mode.md.
- Add docs/project_map_upgrade_plan.md if useful.
- Add pure metadata helper if useful:
  core/project_evolution_mode.py
- Add tests:
  tests/test_project_evolution_mode_contract.py
- No UI changes.
- No runtime route changes.
- No model/API calls.
- No patch generation changes.
- No benchmark scoring changes.
- No lesson/anti-lesson behavior changes.

Required Project Evolution stages:
1. Intake
   Capture evolution request, repo path, goal, constraints, risk tolerance.

2. Existing Map Inventory
   Identify current repo-map/project-map/indexer/repo-librarian/graph/search capabilities.
   Decide reuse / extend / leave unchanged.

3. Project Map
   Identify structure, languages, dependency files, config files, test roots, docs, entrypoints, generated/build folders to ignore.

4. Architecture Read
   Select relevant full files for broad understanding.
   Do not blindly read every file.

5. Impact Analysis
   Identify affected modules, dependency edges, compatibility risks, tests needed, rollout/rollback points.

6. Migration Plan
   Produce a human-readable plan with likely changed files, reason, risk, tests, and rollback notes.

7. Approval Gate
   Human must approve before patch generation.

8. Patch Execution
   Later phase only.
   Multi-file patches must be controlled, minimal, and validated.

9. Evidence
   Store plan, project map, selected files, approvals, validation, replay/debug artifacts.

Required retrieval/search architecture notes:
Document these layers clearly:
- Tree-sitter: structural reader for symbols/imports/classes/functions.
- Existing project map / repo librarian / indexer: repo layout and ownership.
- Graph builder / graph weights: relationship and evidence graph.
- Grep/ripgrep fallback: exact text search.
- MiniLM / embeddings: semantic similarity.
- Semble: optional future fast local code-search backend, candidate only.
- Gemini/model2vec/Semble migration ideas: future provider evaluation, not required in B.1.
- LLM: summarizer/planner only after selected files/snippets are chosen.

Important Semble rule:
Semble is a candidate retrieval/search backend, not the summarizer.
Do not add Semble as a dependency in B.1.
Do not require Semble for tests.
Only document where it could fit later.

Required boundaries:
- Project Evolution Mode must not replace Debug Mode.
- Normal Debug Mode must not start reading broad/full-project files by default.
- No automatic multi-file patching in B.1.
- No automatic dependency upgrades.
- No automatic GitHub writes.
- No n8n/remote worker integration yet.
- No Dream/research auto-ingestion yet.
- No CONTROL prompt changes.
- No benchmark scoring changes.
- No lesson/anti-lesson behavior changes.
- No model/API/subprocess/Docker behavior.

### B.2: Project Map v2 Builder for Evolution Mode.

Goal:
Build read-only Project Map v2 artifacts for Project Evolution Mode.

Project Map v2 helps broad migration/planning tasks understand repo structure, dependencies, configs, tests, entrypoints, docs, integration boundaries, external services/env vars, full-file-read candidates, and migration risks.

This is read-only map generation.
Do not generate patches.
Do not call models.
Do not run validation.
Do not change Debug Mode behavior.

Background:
B.1 defined Project Evolution Mode as separate from Debug Mode.
B.1 also said C.A.T.T.U.S must reuse/upgrade existing project-map/repo-librarian/indexer/graph/search components instead of building a competing second map system.

Scope:
- Add a Project Map v2 builder for Evolution Mode.
- Reuse existing repo-librarian/indexer/project-map/graph helpers where possible.
- Produce JSON and Markdown artifacts.
- Add CLI script or core helper for building the map manually.
- Add tests.

---
### B.2a — Heuristic Graph/Project Node Summaries

---

## Track C — External Benchmark Sandbox

- C.1 Public benchmark survey
- C.2 Manual import of 3–5 small real-world cases
- C.3 Dependency sandbox design
- C.4 Explicit package-install approval gate
- C.5 Real-world benchmark trial report

---

## Track E — Dream Evolution Sandbox

### Goal:
Let Dream propose architecture improvements in isolated branches/temp clones,
evaluate them with tests/benchmarks/replay evidence,
then ask the human before any merge/apply.

### E.1 Branch Sandbox Proposal Writer
- create feature branch or temp clone
- write proposal only
- no merge
- no auto PR

### E.2 Dream Evolution Scorecard
- tests passed
- benchmark delta
- files touched
- risk score
- replay artifacts
- rollback notes

### E.3 Human Review Pack
- summary
- changed files
- why this exists
- evidence
- risks
- rollback command

### E.4 Optional PR Draft
- create PR draft only after explicit user click
- never auto-merge

### E.5 Artifact Janitor / Branch Janitor
- dry-run first
- delete only failed sandbox branches or old temp artifacts
- never delete active lessons or pinned replays

---

## Track F — Operator Assistant / Prompt Courier

Status: shipped through F.4.

### Purpose:
Reduce manual friction in Goal Brief and Mayor Mode by converting messy user intent into structured, reviewable task briefs and handoff notes.

Guardrail: Track F is draft/suggestion/prompt-generation only. It does not execute patches, validation, benchmarks, Dream runs, handoff creation, model/API calls, DB writes, Docker, subprocesses, or lesson promotion.

### F.1 Goal Brief Autocomplete ✅
- user writes messy request
- assistant proposes structured Goal Brief fields
- user edits/approves
- no patch/model execution from this step

### F.2 Handoff Composer ✅
- convert Goal Brief into Mayor handoff note
- fill title, allowed files, validation command, risk notes
- keep "human_approved_for_proposal=false"

### F.3 Mode Router ✅
- suggest Debug Mode vs Project Evolution Mode vs Dream Trial
- explanation only
- user must confirm

### F.4 Review Pack Generator ✅
- generate a final prompt for Claude/Codex/Gemini worker
- include constraints, allowed files, validation, stop conditions

Latest checkpoint:
- Full pytest: 1993 passed, 1 warning
- benchmark --check: 50 checked, 0 errors

Future freeze: optional polish only.

---

## Track G — Remote Operator Mode

### G.1 Local daemon
- C.A.T.T.U.S runs on stayed-on computer
- localhost/local LAN first
- no public internet exposure yet

### G.2 Secure remote web access
- login token
- one-user mode
- HTTPS/tunnel only
- read-only dashboard first

### G.3 Remote approval actions
- approve proposal
- start benchmark
- view replay
- create goal brief
- create handoff note

### G.4 Dangerous actions require second confirmation
- apply patch
- run validation
- create branch
- install packages
- delete artifacts

### G.5 Mobile-friendly UI
- simplified dashboard
- approve/reject buttons
- replay summary
- benchmark status

### Reference Study: Scrapling + Arkon

#### Goal:
Evaluate whether Scrapling/WebBridge and Arkon can help C.A.T.T.U.S collect public documentation and build a dynamic AI-readable graph.

#### Rules:
- no anti-bot evasion goal
- no scraping behind login
- no CAPTCHA solving
- no automatic browsing
- no automatic patching
- output only local research notes

---

## Deferred Ideas

- Migration Planner
- Full-file project understanding mode
- Architecture change proposal generator
- Multi-file patch planner
- Rollback report generator
- Compatibility report generator
- Chat app intergration (like OpenClaw/n8n)

Phase 7      → Deferred/reference research
Phase 10     → Deferred/research-only branched repair idea
Phase 10.5   → Migrated as possible Track A graph-role/evidence idea
Phase 15     → Migrated as possible later lambda/complexity research thread
Reverse Dream execution → Deferred until stronger eval/minimality proof
Mutation-oracle anti-lesson minting → Deferred
Default-on anti-lesson CONTROL → Not approved