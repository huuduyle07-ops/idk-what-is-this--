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

Current benchmark catalog truth:

- 54 benchmark cases
- `benchmark --check`: 54 checked, 0 errors

It is weaker at:

- project creation
- broad migrations
- architecture evolution
- multi-file feature development

Reason:

The current system is optimized for small, evidence-first repair tasks. Creation and migration tasks require broader project understanding and full-file planning.

---

## Track A — Stabilized Debug Agent: safety closures current

Keep improving the existing debug/repair workflow.

### A.1: Benchmark Failure Cause Classification / Environment-aware Summary ✅

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

### A.2: Debug Workflow Stage Map and Contract ✅
Stage list: Intake -> Context -> Proposal -> Safety -> Execution -> Validation -> Evidence -> Learning 

What changed: 
- Added immutable DebugWorkflowStage frozen dataclass metadata. 
- Added DEBUG_WORKFLOW_STAGES, get_debug_workflow_stages(), and canonical_stage_names(). 
- Added the full debug workflow map doc with modules, artifacts, approvals, guardrails, Replay, Benchmarks, Lessons, Anti-lessons, Harness Controls, and Failure Taxonomy coverage. 
- Added contract tests including unique names, exact order, doc phrase coverage, and AST import/call guard. 

UI changed: no. Behavior changed: no. The helper is not wired into runtime behavior and imports only __future__, dataclasses, and typing.

### A.3: Patch Minimality / Changed-files Visibility in Benchmark Tab ✅

Goal: make benchmark reports answer:

Did it pass?
What source files were patched?
What generated artifacts were produced?
Were there unexpected mutations?
Was the patch minimal or suspiciously broad?

### A.4:  Latest Run Health Summary ✅

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

A.4 should combine these into a clear “Run Health” summary. ✅

Scope:
- Add summary computation helper if useful.
- Improve Markdown benchmark report summary.
- Improve web Benchmark tab latest/detail summary.
- Reuse existing benchmark report JSON fields.
- Gracefully support old reports missing new fields.
- Add tests.

### A.5: Universal Patch Safety Chokepoint for Single-file Apply ✅

- Single-file `patch_candidate` real applies now call `core.patch_safety.evaluate_patch_safety` inside `core.executor.Executor.run(...)` before `apply_patch_from_json(...)`.
- `patch_plan` apply paths continue to call `evaluate_patch_safety` through `core.run_lifecycle.run_patch_plan_with_artifacts(...)`.
- The path traversal guard remains a second layer.
- Validation command safety remains separate.

### A.6: LESSON_AUTO_ACTIVE Candidate-only Guard ✅

- `scripts/create_lesson_from_proposal.py` force-disables `LESSON_AUTO_ACTIVE` around `save_candidate_lesson(...)`.
- The previous flag value is restored in `finally`.
- Proposal-created lessons require human Promote before active retrieval.
- `lesson_quality` still routes blocked evidence to `blocked`.

### A.7: Architecture Audit Triage Record ✅

- Added `docs/audits/2026-06-11-architecture-audit-triage.md`.
- Classified audit findings into `already_fixed`, `accepted_now`, `accepted_later`, `rejected`, `frozen`, and `needs_verification`.
- Keeps safety fixes ahead of consolidation and freezes report-only/test-pinned surfaces unless a future phase accepts redesign work.

### A.8: Shared Post-processing Gate Battery ✅

- `core.postprocess_gates.run_postprocess_gate_battery(...)` now owns the shared CLI/web post-processing gate sequence.
- `main.py` and `web/runner.py` call the shared helper.
- Caller-specific behavior, including web harness decisions and missing-JSON callbacks, remains outside the helper.

### A.9: Docs Truth Pass 🔄 current phase

- Refresh README safety, proposal-to-lesson, post-processing, and benchmark wording after A.5-A.8.
- Refresh this roadmap and the architecture audit triage record.
- Documentation-only: no runtime code, tests, patch safety behavior, lesson behavior, benchmark logic, or model routing changes.

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

> **Status: planning, approval, draft, and sandbox-gate pipeline shipped.** Real executable patch generation/apply deferred. 

### B.1: Project Evolution Mode Contract + Project Map Upgrade Plan. ✅

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

### B.2: Project Map v2 Builder for Evolution Mode. ✅

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

### B.2a through B.8 addendum ✅
Added the Project Evolution milestone chain from B.2a through B.8:

- B.2a: Heuristic read-only summaries for high-value Project Map and graph nodes.
- B.3: Deterministic migration planner with goal classification, risks, tests, docs, rollout, rollback, and approval gate.
- B.4: Exact-hash approval records with approve/reject/needs_revision decisions and patch-generation gating.
- B.4a: Web approval panel and buttons for reviewing a migration plan in the Project Evolution workflow.
- B.5: Approval-gated patch draft package with likely files, read-first files, and no patch/apply/validation behavior.
- B.6: Approval-gated patch candidate package with grouped candidate change areas.
- B.7: Narrative patch text draft package with no executable diff.
- B.8: Sandbox/temp-clone validation that verifies the approved chain without generating, applying, or validating a real patch.

### B.9 — Executable Patch Draft Format ✅
- Generate a patch draft in .agent\project_evolution\patch_drafts\*
- Currently, it cannot apply without human approval

### B.10 Project Evolution Review Gate ✅
- Workflow:
project map
→ upgrade plan
→ executable patch draft
→ review gate
→ approval_status: pending
→ apply_allowed: false

- review-only
- apply_allowed false
- human_approval_required true
- full pytest 2631 passed
- benchmark --check 54/54

### B.11 — README Operating Modes / Permission Matrix ✅
- Added Operating Modes / Permission Matrix to README.
- Clarifies which modes can call models, write artifacts, modify the real repo, apply patches, and require human approval.
- Establishes the power leakage rule:
  Mode decides permission.
  Gate decides escalation.
  Human decides activation.
- Documentation-only.
- No code behavior change.
- Validation:
  - compileall clean
  - B.10 tests 20/20 passed

### B.12 — External Queue Import Contract ✅
- Added review-only import contract for external Discord/n8n/Zalo/webhook/manual items.
- Artifacts:
  .agent/external_queue/<queue_id>/external_queue_item.json
  .agent/external_queue/<queue_id>/external_queue_item.md
- Hardcoded gates:
  auto_dream_allowed: false
  human_review_required: true
  import_status: pending_review
- Secrets are redacted/flagged.
- No live external integration.
- No Dream trigger.
- No patch/apply behavior.
- Validation:
  - B.12 tests 37/37 passed
  - full pytest 2668/2668 passed
  - benchmark --check 54/54 PASS

### B.13 — External Queue Operator Workflow ✅
- Documented how to manually import Discord/n8n/Zalo/webhook research output into C.A.T.T.U.S.
- Added example JSON fixture:
  docs/examples/external_queue_item.example.json
- Importing creates artifacts only.
- No auto-Dream, no patch/apply, no live integration.
- Validation:
  - fixture import succeeded
  - B.12 tests 37/37 passed
  - compileall clean

### B.14 — External Queue Review Recommendation ✅
- Added review-only recommendation layer for imported external queue items.
- Reads:
  .agent/external_queue/<queue_id>/external_queue_item.json
- Writes:
  external_queue_review.json
  external_queue_review.md
- Recommendations:
  reject
  needs_more_evidence
  convert_to_goal_brief_seed
  convert_to_dream_candidate
  convert_to_project_evolution_candidate
- Hardcoded gates:
  human_approval_required: true
  action_performed: false
- No conversion performed.
- No Dream item created.
- No Goal Brief created.
- No Project Evolution plan created.
- No patch/apply.
- No model calls/subprocess/live integration.
- Validation:
  - B.14 tests 32/32 passed
  - full pytest 2700/2700 passed

### B.15 — External Queue Index/List CLI
Goal:
Make imported/reviewed external queue items easy to inspect.

Planned behavior:
- Scan .agent/external_queue/
- List queue_id, source, kind, query preview, risk, import_status, review status, recommendation, confidence.
- Support filters:
  --source
  --kind
  --risk
  --recommendation
  --unreviewed
  --reviewed
  --limit
  --json

Rules:
- Read-only.
- No import.
- No review.
- No conversion.
- No Dream trigger.
- No patch/apply.
- No live external integration.
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

F.4 shipment checkpoint:
- Full pytest: 1993 passed, 1 warning

Current benchmark catalog:
- benchmark --check: 54 checked, 0 errors

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

**Ideal workflow:**
Stage 1 — Safe now
n8n research scout
→ Tavily/Perplexity result
→ Zalo/Discord review message
→ you decide manually
Stage 2 — Safer automation later
n8n research scout
→ POST to C.A.T.T.U.S dream inbox
→ C.A.T.T.U.S saves .agent/dream_inbox/*.json
→ no Dream run yet
→ human review in UI
Stage 3 — risky future
n8n
→ C.A.T.T.U.S endpoint
→ Dream run / proposal generation
→ still no patch/apply

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
## Track H — Cost Pressure / Model Budget Control

Purpose:
C.A.T.T.U.S must reduce dependence on expensive AI model usage. Recent usage patterns show token/model limits are becoming the bottleneck, so the system should become stronger at local/rule-based decisions, cheap-first routing, and explicit expensive-model approval.

Main principle:
Expensive AI should be a specialist, not oxygen.

### H.1 — Cost Pressure / Token Burden Report
Goal:
Produce a local report showing where C.A.T.T.U.S is likely causing unnecessary model usage.

Questions:
- Which modes call models?
- Which flows can be local/rule-based?
- Which artifacts duplicate each other?
- Which tasks should never use expensive models?
- Which tasks require human approval before expensive model calls?

Rules:
- Report-only.
- No model calls.
- No routing behavior change.
- No patch/apply.

### H.2 — Model Budget Gate Contract
Goal:
Define a permission model for local / cheap / expensive / blocked model usage.

Possible categories:
- local_only
- cheap_model_allowed
- expensive_model_requires_approval
- blocked

Rules:
- Contract/metadata/tests only.
- No automatic routing change yet.
- No provider-specific lock-in.

### H.3 — Cheap-First Router Policy
Goal:
Route simple classification/listing/review/report tasks away from expensive models.

Cheap/local candidates:
- external queue import
- external queue review
- external queue index
- review gate risk classification
- mode matrix/doc generation
- artifact summaries
- path safety
- benchmark check parsing

Expensive model candidates:
- hard root-cause analysis
- architecture audit
- broad migration planning
- final review for dangerous changes

Rules:
- Preserve human approval for expensive runs.
- Never let n8n/Discord trigger expensive model usage directly.

### H.4 — Model Usage Ledger
Goal:
Record model calls by mode, task type, provider, estimated cost/tokens when available, and outcome usefulness.

Purpose:
Allow future decisions like:
- which model saved time
- which model produced generic output
- which flow burned tokens
- which mode should be downgraded to local rules

### H.5 — Expensive Audit Scorecard
Goal:
Evaluate expensive architecture audits using a fixed rubric.

Score dimensions:
- file-specific insight
- real redundancy found
- safe simplification path
- respects Mode Matrix
- no hallucinated modules/features
- cheaper-model comparison

3. In Current Position, add a short note:
C.A.T.T.U.S is also now being optimized to reduce operator burden and external model dependence:
- fewer repeated audits
- fewer expensive model calls
- more local/rule-based review
- stronger artifact visibility
- explicit budget gates before expensive reasoning
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
