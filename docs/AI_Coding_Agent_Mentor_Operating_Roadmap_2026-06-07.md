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

### A.9: Docs Truth Pass ✅

- Refresh README safety, proposal-to-lesson, post-processing, and benchmark wording after A.5-A.8.
- Refresh this roadmap and the architecture audit triage record.
- Documentation-only: no runtime code, tests, patch safety behavior, lesson behavior, benchmark logic, or model routing changes.

### Track A cleansing checkpoint (A.5-A.15) ✅

A.5-A.15 are closed as the Track A cleansing pass. The checkpoint includes:

- single-file patch safety through the universal patch safety chokepoint
- proposal candidate-only guard for proposal-created lessons
- shared postprocess gate battery used by CLI and web postprocessing paths
- proposal lesson canonical source identity and dedupe wiring
- deprecated proposal route verification
- benchmark generated-artifact ignore rules

Current benchmark truth remains:

- `benchmark --check`: 54 checked, 0 errors

### A.10d: Failure Category Fresh Run Smoke (Phase 14.7a) ✅

Smoke verification that `failure_category` metadata and all display layers work correctly on a real benchmark report — not only in fixture tests.

Changed files:
- `scripts/create_failure_category_smoke_report.py` — read-only smoke script: loads the latest benchmark report, re-enriches failing cases through `with_failure_category_fields()`, checks all display layers (Run Health, Markdown, web render, backward compat), and writes two audit artifacts to `.agent/audits/`

New file: `tests/test_failure_category_smoke.py` — 5 tests (category fields detected, missing fields no crash, web render with category row, old report no category row, AST guardrail on smoke script)

Audit artifacts generated: `.agent/audits/20260613_081410_failure-category-fresh-run-smoke.json/.md` — ALL CHECKS PASSED

Validation: 3033 tests, compileall OK, benchmark --check 54/0.

### A.10c: Failure Category Trend Display (Phase 14.7) ✅

Makes `failure_category` metadata useful to the operator through display in benchmark reports and UI.

Changed files:
- `benchmarks/run_benchmarks.py` — Markdown Run Health section now includes optional "Failure categories" compact line; Failed Cases section now includes `category: <cat> / <confidence> / <rule>` per case (only when field is present)
- `core/failure_taxonomy_trends.py` — added `extract_failure_category_counts(report)` helper; `compare_failure_taxonomies` per-report entries now optionally include `failure_category_counts` when present in case records
- `web/templates/index.html` — added `_benchFailureCategoryText()` JS helper; `_benchRunHealthSummary` computes `failure_category_counts` from results and includes it in the return; `_renderBenchRunHealth` shows a "Failure categories" row when data exists; failing case detail shows category text if present

New test file: `tests/test_failure_category_trend.py` — 18 tests (4 run health, 2 Markdown, 3 web/view, 2 trends/evidence, 7 AST-based guardrails)

Guardrails: old benchmark reports without `failure_category` render without error. Scoring, retrieval, patch behavior, prompts, lessons, Dream, and Project Evolution are unchanged. `failure_category` metadata remains observational only.

### Goals:

- keep patches small
- preserve evidence grounding
- improve speed/cost
- reduce UI complexity
- expand benchmark coverage

### A.10: Failure Taxonomy Derivation Report (Phase 14.5) ✅

Read-only scan of existing `.agent/` benchmark artifacts that derives a stable 13-category failure taxonomy without changing runtime behavior.

New files:
- `core/failure_taxonomy_derivation.py` — stdlib-only mapper with `DERIVATION_CATEGORIES` (13 categories), `classify_benchmark_case()`, and `derive_taxonomy_report()`
- `scripts/create_failure_taxonomy_derivation_report.py` — CLI that writes `<stamp>_failure-taxonomy-derivation.json/.md` to `.agent/audits/`
- `tests/test_failure_taxonomy_derivation.py` — 39 tests (AST-based import guard)

Categories (stable, ordered): `toolchain_environment`, `security_tool_or_permission`, `validation_command_gap`, `wrong_file_or_decoy`, `forbidden_file_or_scope_violation`, `missing_import_or_dependency`, `async_or_lifecycle_bug`, `state_mutation_or_side_effect`, `data_validation_or_boundary`, `root_cause_multifile`, `false_positive_no_patch`, `insufficient_evidence`, `unknown`.

Guardrails: no model calls, no Flask, no DB, no subprocess, no patch apply, no lesson promotion. Report-only; does not change scoring, retrieval, patching, or lessons.

### A.10a: Unknown Failure Category Review (Phase 14.5a) ✅

Read-only review of unknown/unmapped cases from the Phase 14.5 derivation artifact. Proposes rule improvements without applying them.

New files:
- `core/failure_unknown_review.py` — stdlib-only reviewer with `REVIEW_OUTCOMES` (5 outcomes), `review_unknown_case()`, `build_unknown_review()`, and Phase 14.6 readiness computation
- `scripts/create_failure_unknown_review.py` — CLI that reads latest derivation artifact and writes `<stamp>_failure-unknown-review.json/.md`
- `tests/test_failure_unknown_review.py` — 37 tests

Review outcomes: `candidate_mapping_rule`, `candidate_new_category`, `environment_or_tool_noise`, `insufficient_evidence`, `leave_unknown`. Phase 14.6 readiness: `ready_with_unknown_bucket` (unknown is valid — do not force-map).

### A.10b: failure_category Metadata on New Reports (Phase 14.6) ✅

Adds four display-only `failure_category` fields to newly generated benchmark case results using a deterministic priority-ordered mapper.

New files:
- `core/failure_category.py` — stdlib-only mapper with `FAILURE_CATEGORIES` (same 13 categories) and `derive_failure_category(case_record)` returning `failure_category`, `failure_category_confidence`, `failure_category_rule`, `failure_category_reason`
- `tests/test_failure_category.py` — 37 tests (10 mapper rules, 7 report integration, 7 guardrails + extra bench_cat coverage)

Changed files:
- `benchmarks/run_benchmarks.py` — added `with_failure_category_fields()` (parallel to `with_failure_kind_fields()`), called at enrichment point after `with_failure_kind_fields`
- `core/benchmarks_view.py` — added `failure_category_display()` (backward-compatible, empty string on old reports), added `failure_category_counts` to `summarize_run_health()`, updated `_modern_report_signal()` to include `failure_category` key

Guardrails: scoring, pass/fail, retries, patch generation, patch safety, validation, retrieval, lessons, anti-lessons, Dream, Project Evolution, model prompts, and routing are unchanged. `failure_category` is added after scoring is settled and does not affect any existing fields.

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

### B.15 — External Queue Index/List CLI ✅

Implemented read-only index/list layer for imported/reviewed external queue artifacts.

- Core helper: `core/external_queue_index.py`
- CLI: `scripts/list_external_queue.py`
- Scans `.agent/external_queue/**/external_queue_item.json`
- Lists queue id, path, title/summary, source kind, created/modified time, status, risk, gate status, recommendation, linked paths, validation/error summary, display safety, and promotable/executable eligibility.
- Handles invalid JSON, wrong schema, missing optional fields, partial artifacts, missing linked paths, and invalid review files without crashing.
- Supports filters:
  `--status`, `--source`, `--kind`, `--risk`, `--recommendation`, `--reviewed`, `--unreviewed`, `--limit`, `--json`
- Default output is a compact table; `--json` emits deterministic sorted-key JSON.
- No External Queue web UI exists yet; web listing remains deferred.

Rules preserved:
- Read-only.
- No import/review writes.
- No conversion.
- No Dream trigger.
- No patch/apply.
- No model calls.
- No Discord/n8n/webhook calls.
- No live external integration.

### B.15a — External Queue List Smoke + README Usage Examples ✅

Added operator-facing README examples for the read-only External Queue list CLI and smoke coverage for help text, basic listing, unreviewed filtering, JSON output, limit handling, and README example flag validity.

Rules preserved:
- Listing remains read-only.
- No import, review, conversion, execution, promotion, patch/apply, model calls, Discord/n8n/webhook calls, Dream item creation, Goal Brief creation, or Project Evolution plan creation.
- Invalid artifacts remain tolerated as invalid/unknown rows.
- Web list UI remains deferred.

---

### B.16 - External Queue Detail/View CLI shipped

Added a read-only detail command for inspecting one External Queue item by queue id.

- Core helper: `load_external_queue_item_detail(...)` in `core/external_queue_index.py`
- CLI: `scripts/show_external_queue_item.py`
- Shows identity, content summary, gate status, risk/safety warnings, linked artifacts, and review metadata.
- `--json` emits deterministic sorted-key JSON; `--include-raw` can include parsed raw item/review JSON.
- Handles missing queue ids, invalid item JSON, invalid review JSON, missing optional fields, missing linked paths, and ambiguous duplicate queue ids without crashing.

Rules preserved:
- Viewing remains read-only.
- No import/review writes.
- No conversion.
- No Dream item creation.
- No Goal Brief creation.
- No Project Evolution plan creation.
- No lesson promotion.
- No patch/apply.
- No model calls.
- No Discord/n8n/Zalo/webhook/network calls.
- No live external integration.

### B.17 - External Queue Export Draft shipped

Added a draft-only bridge from a reviewed External Queue item into inert seed artifacts for later human review.

- Core helper: `core/external_queue_export.py`
- CLI: `scripts/export_external_queue_item.py`
- Supported targets:
  `goal_brief_seed`, `dream_candidate_seed`, `project_evolution_seed`
- Output path:
  `.agent/external_queue_exports/<queue_id>/<target>_draft.{json,md}`
- Requires a valid `external_queue_review.json` by default.
- Review recommendation must match the requested target.
- Existing draft files return `already_exists` and are not overwritten.
- `--dry-run` reports the draft without writing files.
- `--json` emits deterministic sorted-key JSON status output.

Rules preserved:
- Export creates draft artifacts only.
- No real Goal Brief is created.
- No Dream item is created and no Dream run starts.
- No Project Evolution plan is created.
- No model calls.
- No webhook/network/Discord/n8n/Zalo calls.
- No patch/apply.
- No lesson promotion.
- No validation command is run.
- Human approval remains required before any target workflow starts.

### B.17a - External Queue Export Smoke + Operator Examples ✅

Smoke coverage and operator examples proving all three B.17 export targets work safely.

- README "Export reviewed item as draft" section now shows examples for all three targets (`goal_brief_seed`, `dream_candidate_seed`, `project_evolution_seed`) plus `--dry-run` and `--json`.
- Added `test_dream_candidate_seed_smoke_inert_flags_and_no_dream_artifact` — verifies all inert safety flags and confirms no Dream inbox directory is created.
- Added `test_project_evolution_seed_smoke_inert_flags_and_no_plan_artifact` — verifies all inert safety flags and confirms no Project Evolution directory is created.
- Added `test_readme_export_examples_cover_all_three_targets` — asserts all three `SUPPORTED_TARGETS` appear in the README export section.
- No export behavior changed. Still draft-only, still requires human approval before any target workflow.

### B.17b — External Queue Slice Closure Note ✅

**B.12 through B.17a is complete and safe. The External Queue slice is closed.**

#### Complete operator pipeline

```
import inert item
  └─ scripts/import_external_queue_item.py  (B.12)
       .agent/external_queue/<queue_id>/external_queue_item.{json,md}

review recommendation
  └─ scripts/create_external_queue_review.py  (B.14)
       .agent/external_queue/<queue_id>/external_queue_review.{json,md}
       recommendation: reject | needs_more_evidence
                     | convert_to_goal_brief_seed
                     | convert_to_dream_candidate
                     | convert_to_project_evolution_candidate

list / index
  └─ scripts/list_external_queue.py  (B.15, B.15a)
       read-only compact table or --json

detail / view
  └─ scripts/show_external_queue_item.py  (B.16)
       read-only identity + content + risk + review metadata

export inert seed draft
  └─ scripts/export_external_queue_item.py  (B.17, B.17a)
       .agent/external_queue_exports/<queue_id>/<target>_draft.{json,md}
       target: goal_brief_seed | dream_candidate_seed | project_evolution_seed
```

#### What this slice never does

- No auto Dream run.
- No Goal Brief activation or creation.
- No Project Evolution plan creation.
- No patch or apply on any file.
- No lesson promotion.
- No model calls.
- No webhooks, live Discord, n8n, or Zalo calls.
- No subprocess or network calls from core export helper.
- Human approval is required before any target workflow starts.

#### Suggested next future phase

**B.18 — Human-approved seed promotion gate** (deferred): a CLI or web action that takes a reviewed export draft and hands it to the appropriate target workflow (Goal Brief, Dream, or Project Evolution) after explicit operator confirmation. Not implemented in this slice.

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

Status: shipped through F.5.

### Purpose:
Reduce manual friction in Goal Brief and Mayor Mode by converting messy user intent into structured, reviewable task briefs and handoff notes.

Guardrail: Track F is draft/suggestion/prompt-generation only. It does not execute patches, validation, benchmarks, Dream runs, handoff creation, worker launch, model/API calls, DB writes, Docker, subprocesses, or lesson promotion.

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

### F.5 One-click Worker Assignment / Route Card ✅
- create a draft Worker Assignment from a Goal Brief, Handoff, Review Pack, or External Queue seed draft
- write `.agent/worker_assignments/<assignment_id>/worker_assignment.json` and `.md`
- include mode, worker role, allowed/forbidden files, validation commands, stop conditions, safety rules, and final summary format
- keep `human_approval_required=true`, `apply_allowed=false`, and `worker_launch_allowed=false`
- no worker/model/patch/validation/Dream/Project Evolution/promotion behavior

F.5 shipment checkpoint:
- Targeted pytest: `tests/test_worker_assignment.py`

### F.5a Worker Assignment Smoke + Copy UX Polish ✅
- add web and CLI smoke coverage for Worker Assignment artifact creation, dry-run, JSON output, missing source, and no-overwrite behavior
- show assignment id, JSON path, Markdown path, and copyable Markdown in the Goal Brief UI
- keep the flow draft-only and inert
- no worker/model/patch/validation/Dream/Project Evolution/webhook/promotion behavior

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
## Track H — Driver Model Routing

Purpose:
Tell the operator which model "vehicle" level a task deserves *before* any model is called. The Driver recommends the safest allowed vehicle; it never auto-spends, auto-escalates, or executes. Expensive AI should be a specialist, not oxygen.

Main principle:
The Driver does not drive yet. It only recommends the safest allowed vehicle.

### H.1 — Driver Model Routing Contract ✅
Goal:
Evaluate a Worker Assignment (F.5) and recommend the safest allowed vehicle level.

Vehicle levels (stable string constants):
- `local_only`
- `free_model_ok`
- `cheap_api_ok`
- `strong_model_recommended`
- `strong_model_requires_approval`
- `vision_or_human_caption_required`
- `human_only`
- `blocked`

Behaviour:
- Reads a `worker_assignment.json` (or a plain dict) and inspects mode, worker role, allowed/forbidden files, validation commands, stop conditions, safety rules, expected output, source type, and the apply / worker-launch / approval flags.
- Writes inert `.agent/driver_decisions/<driver_decision_id>/driver_decision.json` and `.md`.
- Recommends per task: Review-only → local/free; narrow Debug with validation → free; missing validation → at least cheap API + `missing_validation`; Project Evolution → strong + approval (`broad_change`); Dream Trial → cheap/strong + approval (`experimental_workflow`, Dream does not start); visual evidence → `vision_or_human_caption_required`; security-sensitive → `strong_model_requires_approval`; `apply_allowed` / `worker_launch_allowed` → `blocked`; missing allowed files → `scope_unclear`; External Queue source → `external_untrusted_source`, never below free.

Rules (contract/report-only — verified by guardrail tests):
- No model call. No provider switch. No API spend.
- No worker launch. No patch apply. No validation run.
- No Dream. No Project Evolution execution. No webhook/network. No lesson promotion.

Status:
- Complete. Contract/report-only — no real model switching yet.
- CLI: `python scripts/evaluate_driver_route.py --worker-assignment <path>` (optional `--json`, `--dry-run`, `--output-root`, deterministic `--driver-decision-id` / `--created-at`).
- Files: `core/driver_model_routing.py`, `scripts/evaluate_driver_route.py`, `tests/test_driver_model_routing.py`.
- Shipment checkpoint: `python -m pytest tests/test_driver_model_routing.py -q` (23 cases) — also covered by `python -m compileall` and the existing `benchmarks/run_benchmarks.py --check`.

### H.2 — Model Budget / Provider Switch (future)
- Turn the H.1 recommendation into an actual, approval-gated model/provider choice.
- Deferred: H.1 stays recommend-only until a separate human-approved execution phase exists.

H.1 supports the future **A.16 Visual Evidence Intake Contract**: when a task needs visual evidence, H.1 already routes to `vision_or_human_caption_required` instead of letting a text-only model pretend it verified a screenshot.

---

## Long-term Framing: District Model

> **This is long-term framing, not an implementation commitment. Do not build any of this yet.**

C.A.T.T.U.S is not the whole AI society. It is the **Coding / Engineering District** of a possible future AI city. It specializes in debugging, patch safety, benchmarks, evidence, lessons, and operator workflow. It should not try to become every possible AI system.

**Core principle:** One city, many districts. Shared roads, separate laws. Artifacts travel, permissions do not.

### What C.A.T.T.U.S Is

The Coding / Engineering District. Its laws:

- patch safety
- validation evidence
- benchmark grounding
- lesson quality
- human approval for any real-repo change

C.A.T.T.U.S does not expand into research, teaching, math, physics, or biology by absorbing those concerns. It routes to other districts when those concerns arise.

### Possible Future Districts

Future specialized agents could become separate districts. Each district keeps its own laws, gates, and evaluation. Districts communicate through artifacts and shared protocols. Permissions do not transfer between districts.

| District | Purpose | Key laws |
| --- | --- | --- |
| **Coding / Engineering** | Current C.A.T.T.U.S. Debugging, repair, patch safety, benchmarks, evidence, lessons, operator workflow. | Patch safety, validation, benchmark evidence, lesson quality, human approval |
| **Research / Journalist** | Searches external public sources. Produces cited briefings. | Cannot trigger Dream/patch/workers automatically |
| **Teacher** | Teaches from existing lessons, anti-lessons, benchmark cases, and failure reports. | Cannot promote lessons or modify repo |
| **Math** | Proof checking, calculation validation, counterexample search. | Separate from coding patch safety |
| **Physics** | Units, equations, assumptions, simulation validation. | Domain-specific rigor gates |
| **Biology** | Citation quality, uncertainty, safety/ethics boundaries. | No unsafe lab/procedure instructions |
| **Visual Inspector** | Screenshot/visual evidence handling. If vision unavailable, requires human caption. Does not claim validation proves a visual issue is fixed unless visual verification exists. | Vision-or-human-caption required |

n8n or similar workflow tools can act as roads/transport between districts. Artifacts travel between districts; permissions do not.

### City Hall / Router

The City Hall Router:

- Routes tasks to the appropriate district.
- May ask multiple districts to collaborate on a single task.
- Does not bypass district laws.
- Human remains final authority.

The City Hall Router is a concept, not a component. Do not implement it yet.

### Driver

The Driver chooses the model/vehicle level for a task:

- `local_free` — local model or rule-based, no cost
- `cheap_api` — inexpensive API call
- `strong_api` — expensive API, requires operator approval
- `human_only` — blocked; human must act directly

The Driver recommends escalation. It does not auto-spend or auto-escalate without operator approval.

The H.1 Driver Model Routing Contract is the near-term step toward this concept.

### Do Not Build Yet

All of the following are **deferred**. Do not implement:

- Autonomous AI society or agent-to-agent chat running 24/7
- Automatic n8n-to-Dream routing
- Automatic patch/apply from any district
- Automatic model escalation
- Autonomous cross-district workflows
- Math, Physics, or Biology districts
- City Hall Router implementation
- Driver auto-escalation
- Any inter-district artifact exchange protocol

### Near-term Roadmap Implications

The District Model framing does not change the near-term roadmap. The next practical features remain small and self-contained:

| Track | Feature | Purpose |
| --- | --- | --- |
| **F.5** | One-click Worker Assignment / Route Card | Shipped draft route card for manual worker assignment |
| **H.1** ✅ | Driver Model Routing Contract | Shipped contract that recommends the safest model vehicle for a worker assignment (report-only) |
| **A.16** | Visual Evidence Intake Contract | How screenshots/visual output enters the evidence chain |
| **F.6** | Lesson Teaching Card / Teacher Mode | Present lessons in a teaching-friendly format |

These features are additive. They do not require implementing any district infrastructure.

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

### Future District Protocol (Track D — all deferred)

Possible later phases for the District Model. **Do not implement any of these yet.**

- **D.1** District Manifest Schema
- **D.2** Artifact Exchange Protocol
- **D.3** City Hall Router Draft
- **D.4** Research / Journalist District Brief
- **D.5** Teacher District Teaching Card

#### District: Admission Guidance District

>Project status: **hibernation / data collection mode**.
The system will collect market signal history until the next admission cycle.
Planned resume window: April 2027.
Current priority is C.A.T.T.U.S / Coding District.

Purpose:
- Estimate high-school admission risk/probability.
- Explain score gap versus historical cutoff.
- Classify student planning posture into 4 practical groups.
- Read market/exam-season signals.
- Help students/families make safer NV1/NV2 decisions.

Hard limits:
- No guaranteed admission claims.
- No mental-health diagnosis.
- No shaming students.
- No storing sensitive student data without clear consent.
- No public ranking of individual students.
- No fully automated advice without uncertainty display.

Outputs:
- risk band
- admission probability estimate
- persona/planning group
- recommended next action
- uncertainty explanation
- family-pressure warning, if relevant


