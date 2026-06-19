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

Checkpoint: after F.5/F.5a, H.1, A.16, F.6/F.6a, F.7 — benchmark 54/54, flaky 3, unexpected mutations 0.

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

### A.16 — Visual Evidence Intake Contract ✅
Goal:
Stop the system from claiming a visual/UI/design issue is resolved just because text/code tests passed. A.16 is a pure contract that records whether a visual issue is actually verifiable before a resolution claim is allowed. It supports the H.1 `vision_or_human_caption_required` vehicle.

Behaviour:
- Reads a `worker_assignment.json` (F.5) or a `driver_decision.json` (H.1) — a JSON file or a plain dict — and inspects title, expected output, stop conditions, safety rules, worker role, source context, and (for driver decisions) reasons / risk flags / recommended vehicle. F.5 boilerplate ("Stop if visual evidence is required but unavailable.") is excluded so it never false-positives.
- Writes inert `.agent/visual_evidence/<visual_evidence_id>/visual_evidence_contract.json` and `.md`.
- Detection: visual reference (screenshot / image / visual / UI / layout / OCR / chart / poster / design) → `visual_evidence_referenced` + `source_mentions_visual_issue`; `--visual-path` or embedded paths → `visual_evidence_present`; no path and no summary → `visual_paths_missing` + `visual_evidence_path_or_caption`; no readable vision model → `vision_model_unavailable`, and with no summary → `human_visual_summary_required` + `human_visual_summary_or_vision_model`; no explicit validation coverage → `validation_does_not_cover_visual_issue` + `explicit_visual_validation_coverage`.
- Resolution claim: allowed only when (a human summary OR a vision-capable model) AND explicit visual validation coverage are present; otherwise `visual_verification_required = true`, `resolution_claim_allowed = false`, `visual_evidence_unverified` + `resolution_claim_not_allowed` + `visual_verification_step`. A non-visual source always allows the claim.
- `visual_evidence_readable_by_model` and `validation_covers_visual_issue` default false and are only ever set true when explicitly passed — never inferred from file presence, never by inspecting images.

Rules (contract-only — verified by guardrail tests):
- No OCR. No vision model. No model call. Image bytes are never read.
- No provider switch. No worker launch. No patch apply. No validation run.
- No Dream. No Project Evolution execution. No webhook/network. No lesson promotion.

Status:
- Complete. Contract-only — no OCR / vision / model execution yet.
- CLI: `python scripts/create_visual_evidence_contract.py --source <worker_assignment_or_driver_decision_json>` (optional `--visual-path`, `--human-summary`, `--visual-readable-by-model true`, `--validation-covers-visual true`, `--json`, `--dry-run`, `--output-root`, deterministic `--visual-evidence-id` / `--created-at`).
- A.16 does not auto-run inside F.5 or H.1; the operator runs the three steps (assignment → driver route → visual evidence contract) manually.
- Files: `core/visual_evidence_contract.py`, `scripts/create_visual_evidence_contract.py`, `tests/test_visual_evidence_contract.py`.
- Shipment checkpoint: `python -m pytest tests/test_visual_evidence_contract.py -q` — also covered by `python -m compileall` and the existing `benchmarks/run_benchmarks.py --check`.

---

### A.17 — Flaky Case Review Report ✅
Goal:
Turn flaky benchmark runs into an explainable, report-only reliability artifact. When a run passes overall but some cases needed a retry (flaky), A.17 explains *which* cases were flaky, *why* they may be flaky, and *what the next human action is* — without fixing anything.

Behaviour:
- Reads an existing benchmark report JSON (the file the benchmark runner writes into `.agent/benchmarks/`) via `--report <path>` or `--latest`. It never runs the benchmark suite.
- Detects a case as flaky when any of: the report marks it `flaky`; `attempts > 1` with a final pass; an early attempt failed then a later attempt passed; retry metadata indicates recovery; or a report-level flaky list names the case.
- Classifies each flaky case with deterministic rules (no model calls) into one of: `model_variance_or_prompt_instability`, `validation_timing_or_environment`, `generated_artifact_scope_noise`, `unexpected_mutation_noise`, `fallback_or_provider_variance`, `test_harness_or_report_shape_issue`, `safety_gate_boundary_case`, `unknown_flake`. Import / timing / toolchain output → environment; unexpected mutation → mutation noise; generated artifacts (no mutation) → scope noise; fallback/provider change → provider variance; an inconsistently-firing safety blocker → safety-gate boundary; clean fail-then-pass with no other signal → model variance.
- Recommends one next human action per case (`add_stability_replay`, `tighten_allowed_files_or_generated_ignore`, `inspect_validation_environment`, `inspect_model_fallback_path`, `add_report_schema_guard`, `promote_to_honeypot_or_regression_case`, `manual_review_required`, `no_action_yet_monitor_only`) plus a confidence level.
- Writes `.agent/reliability/flaky_case_reviews/<review_id>/flaky_case_review.json` and `.md` (operator-readable: Summary, a compact Flaky Cases table, per-case Details, and a Boundaries section). The summary always records `source_report_modified: false` and `benchmarks_run_by_tool: false`.

Rules (report-only — verified by guardrail tests):
- No model call. No patch apply. No validation execution. No benchmark execution inside the tool.
- No Dream. No Project Evolution execution. No webhook/network. No lesson promotion. No proposal import. No worker launch.
- No benchmark case edits, no prompt changes, no patch-generation or validation changes. The source report is read, never written.

Status:
- Complete. Report-only reliability artifact; classifies flaky benchmark cases deterministically; no benchmark execution, no patching, no model calls.
- Intended next step after F.8a/F.8b/F.8c and GOV.1.
- CLI: `python scripts/create_flaky_case_review.py --latest` (or `--report <path>`; optional `--repo-path`, `--json`, deterministic `--review-id` / `--created-at`, `--output-root`).
- Files: `core/flaky_case_review.py`, `scripts/create_flaky_case_review.py`, `tests/test_flaky_case_review.py`.
- Shipment checkpoint: `python -m pytest tests/test_flaky_case_review.py -q` — also covered by `python -m compileall` and the existing `benchmarks/run_benchmarks.py --check`.

---

### A.18 - Validation Execution Safety complete
Goal:
Reduce pre-automation risk from validation commands running through legacy shell validation on real repo paths.

Status:
- Complete. Safe validation execution exists through `SafeValidationCommand`: argv command, `shell=False`, explicit cwd, required bounded timeout, and scrubbed environment.
- Safe mode rejects shell metacharacters, shell interpreters, arbitrary `python -c`, destructive filesystem/git commands, and direct env-dumping tools.
- Legacy shell validation remains explicit/manual and backward-compatible only.
- Automation-safe callers can pass `require_safe_validation=True` to reject raw shell validation before patch operations run.
- No automation, model call, worker launch, Dream execution, Project Evolution execution, webhook/network behavior, lesson promotion, proposal import, benchmark execution, or auto-merge power was added.

---

### A.19 - Patch Plan Atomicity & Validation Side-Effect Boundary complete
Goal:
Make patch-plan atomicity truthful and visible before stronger automation exists.

Status:
- Complete. Patch-plan atomicity is now explicitly patch-operation scoped: patch operations are rollback-protected, but validation side effects are outside patch rollback scope unless sandbox validation or a future explicit side-effect rollback mechanism is used.
- Patch-plan, lifecycle, and single-file executor results expose metadata including `atomicity_scope="patch_ops_only"`, `patch_ops_rollback_protected=true`, `validation_side_effects_in_rollback_scope=false`, `validation_side_effect_policy="reported_not_rolled_back"`, and `sandbox_validation_recommended=true`.
- Validation runs are surrounded by lightweight repo snapshots when supported. Created, modified, and deleted files are reported with patch-touched-scope and generated/noisy flags.
- A.19 reports validation side effects; it does not auto-delete them.
- Future automation/self-evolution paths must require safe validation execution and prefer sandbox validation before trusting validation output.
- No automation, model call, worker launch, Dream execution, Project Evolution execution, webhook/network behavior, lesson promotion, proposal import, benchmark execution, or auto-merge power was added.

---

### A.21 - Upload Temp Repo Lifecycle complete
Goal:
Add an explicit lifecycle policy for `/upload_folder` temp repos before stronger automation exists.

Status:
- Complete. Uploaded folders are staged into managed temp repos with a `cattus-upload-` temp-root prefix and metadata recording creation time, source route, repo path, cleanup policy, last access time, and lifecycle status.
- Failed upload temp dirs with zero indexable files are cleaned up when the path is inside the managed temp root boundary.
- The cleanup helper refuses unmanaged paths, project roots, `.git`, home directories, drive roots, temp-base roots, and paths outside the expected temp base.
- Missing managed temp dirs are handled idempotently.
- Future automation/sandbox/self-evolution runners must not treat upload temp repos as durable project state.
- No automation, model call, worker launch, Dream execution, Project Evolution execution, webhook/network behavior, lesson promotion, proposal import, benchmark execution, or auto-merge power was added.

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

Status: shipped through F.8a.

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

### F.6 Lesson Teaching Card / Teacher Mode v0 complete
- create local teaching cards from existing lesson, anti-lesson, benchmark case, or failure report JSON
- write `.agent/teaching_cards/<teaching_card_id>/teaching_card.json` and `.md`
- include summary, what happened, why it matters, common trap, safe fix strategy, anti-pattern warning, mini quiz, mini exercise, related artifacts, uncertainty notes, and execution boundary
- preserve uncertainty; visual sources warn that visual claims need visual verification; security/auth/secrets/API key/env sources warn as security-sensitive; external/untrusted sources warn about source trust
- keep all inert flags false: no model call, lesson promotion, anti-lesson creation, patch, validation, worker launch, Dream, Project Evolution, webhook, or source mutation

F.6 shipment checkpoint:
- Targeted pytest: `tests/test_lesson_teaching_card.py`

### F.6a Teaching Card Smoke + Copy Polish complete
- improve smoke coverage so representative lesson, anti-lesson, benchmark case, and failure report fixtures assert the generated Markdown is useful to read, not just structurally present
- keep Markdown compact: required teaching sections, short paragraphs/bullets, mini quiz with exactly three questions, mini exercise, uncertainty notes, and no raw JSON blob dumps
- make default CLI output copy-friendly with teaching card id, JSON path, Markdown path, and a `Copy this Markdown:` hint; Markdown is the copy/study artifact
- keep `--json` deterministic and free of extra human text
- preserve guardrails: no model/provider imports, patch/apply path, validation subprocess call, worker launch, Dream runner, Project Evolution execution, webhook/network call, lesson promotion, or anti-lesson creation

F.6a shipment checkpoint:
- Targeted pytest: `tests/test_lesson_teaching_card.py`

### F.7 Worker Result Import / Review Stub complete
- import pasted or file-based external worker output against an existing Worker Assignment
- write `.agent/worker_result_reviews/<review_id>/worker_result_review.json` and `.md`
- optionally link a Driver Decision and Visual Evidence Contract, but never create or execute them
- keep the result untrusted: `review_status=pending_review`, `trust_level=untrusted`, `human_review_required=true`
- extract claimed changed files, claimed validation commands, visual/security-sensitive claims, missing visual evidence requirements, truncation, and recommended next manual actions
- preserve guardrails: no model/provider import, worker launch, patch/apply path, validation subprocess call, proposal import, lesson promotion, teaching card creation, Dream runner, Project Evolution execution, or webhook/network call

F.7 shipment checkpoint:
- Targeted pytest: `tests/test_worker_result_review.py`

### F.8a Worker Assignment prompt compacting + Goal Brief UI de-dup complete
- UX / prompt-format polish only; no backend permission change and no new capability
- compact the route-card Markdown to six sections (Objective, Source, Scope, Task Rules, Validation, Expected Output)
- state the no-apply / no-launch / no-real-repo-mutation rule once (in Task Rules) instead of repeating the same safety statement across Context, Constraints, Stop Conditions, Safety Rules, and a Final Summary
- keep the JSON record unchanged: inert flags (`human_approval_required=true`, `apply_allowed=false`, `worker_launch_allowed=false`, `model_call_performed=false`, `patch_applied=false`, `validation_run=false`, `promotion_performed=false`) and the full stop_conditions / safety_rules arrays still ship in JSON; Markdown stays deterministic
- de-dup the Goal Brief tab: gate **Create Worker Assignment** behind a usable brief (disabled + helper text until a brief exists), and collapse the duplicate summary / Markdown / empty-state boxes into one compact card (id + JSON path + Markdown path, with the Markdown box hidden until an assignment exists)
- preserve guardrails: no model/provider client, worker launch, patch/apply module, validation subprocess, Dream runner, Project Evolution execution, webhook/network, lesson promotion, or proposal import was added

F.8a shipment checkpoint:
- Targeted pytest: `tests/test_worker_assignment.py` (24 passed)
- `python benchmarks/run_benchmarks.py --check`: 54 checked, 0 errors

### F.8b Goal Brief action-bar cleanup complete
- UX / template / JS / CSS only; no backend permission, no Worker Assignment JSON schema change, and no new capability
- stage the Goal Brief tab top-to-bottom with one primary action per stage: conversation actions (Start brief / Send reply) -> chat + checklist -> Worker Assignment handoff -> collapsed Review Pack
- move the Worker Assignment handoff (Copy final prompt + Create Worker Assignment) *below* the chat/checklist so it reads as the post-interview step instead of crowding the top
- gate Copy final prompt and Create Worker Assignment on brief readiness (disabled with helper text until the brief's final prompt is built); `_updateWorkerAssignmentAvailability()` drives a `none|draft|ready` panel state
- show one compact Worker Assignment card: id + JSON path + Markdown path + copyable Markdown textarea + Copy assignment, all hidden until an assignment exists (no empty "no assignment yet" boxes, no duplicate action bars)
- demote the Review Pack to a collapsed secondary `<details>` so its Copy Markdown button no longer competes with the primary Create Worker Assignment
- preserve guardrails: no model call, worker launch, patch/apply, validation run, Dream, Project Evolution, webhook/network, lesson promotion, or proposal import was added

F.8b shipment checkpoint:
- Targeted pytest: `tests/test_worker_assignment.py` (28 passed)
- `python benchmarks/run_benchmarks.py --check`: 54 checked, 0 errors

### F.8c Goal Brief assistive intake simplification complete
- UX / template / JS / CSS only; no backend permission, no Worker Assignment JSON schema change, and no new capability
- core principle: the system assists the operator instead of forcing a strict interview
- merge the intake surfaces into one Step 1 box ("What do you want help with?") with rough notes (messy intent + "Help me structure this") collapsed into an optional detail
- add a three-step stage indicator (Step 1 Describe -> Step 2 Refine -> Step 3 Handoff) with one stage primary at a time, driven by `_setGoalBriefStage()`
- make the checklist non-blocking: soft labels ("Not provided yet", "Needed before worker assignment") via `_goalBriefMissingLabel()` instead of a blunt red "Missing" wall, with a soft amber accent only on readiness-gating fields
- add friendly "good enough" guidance before handoff ("You can continue with a rough brief, but Worker Assignment will be safer with allowed files + validation.")
- assistive button wording: "Start assisted brief", "Help me structure this", "Suggest workflow mode"
- move advanced helpers (mode routing, review pack, raw details) into one collapsed `<details class="goal-brief-advanced">` so they stay available but secondary
- preserve F.8b gating: Create Worker Assignment stays disabled until the final prompt is ready, Copy assignment stays hidden until Markdown exists, and there are no empty worker-assignment boxes or duplicate action bars
- preserve guardrails: no model call beyond the existing Goal Brief interview route, worker launch, patch/apply, validation run, Dream, Project Evolution, webhook/network, lesson promotion, or proposal import was added

F.8c shipment checkpoint:
- Targeted pytest: `tests/test_worker_assignment.py` (35 passed)
- Related UI suites: `tests/test_goal_brief_routes.py`, `tests/test_goal_brief_autocomplete_routes.py`, `tests/test_mode_router_routes.py`, `tests/test_mayor_mode_ui.py` (green)
- `python benchmarks/run_benchmarks.py --check`: 54 checked, 0 errors

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

H.1 supports the **A.16 Visual Evidence Intake Contract** (shipped): when a task needs visual evidence, H.1 routes to `vision_or_human_caption_required` instead of letting a text-only model pretend it verified a screenshot, and A.16 is where the human records the caption summary (or asserts a vision model) plus validation coverage before any resolution claim is allowed.

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
| **A.16** ✅ | Visual Evidence Intake Contract | Shipped contract that records whether a visual/UI issue is verifiable before a resolution claim (report-only; no OCR/vision/model) |
| **A.17** ✅ | Flaky Case Review Report | Report-only reliability artifact that reads an existing benchmark report, deterministically classifies flaky cases and recommends a next human action (no benchmark execution, no patching, no model calls) |
| **A.18** complete | Validation Execution Safety | Safe argv validation boundary with legacy shell validation explicit/manual only; automation-safe callers can require safe validation before patch ops |
| **A.19** complete | Patch Plan Atomicity Boundary | Patch rollback is patch-op scoped; validation side effects are reported, not auto-cleaned, and future automation must prefer sandbox validation |
| **A.21** complete | Upload Temp Repo Lifecycle | Uploads stage into managed temp repos with metadata; zero-indexable failures are cleaned or reported, and cleanup refuses unmanaged paths |
| **F.6** complete | Lesson Teaching Card / Teacher Mode | Shipped local teaching cards for lessons, anti-lessons, benchmark cases, and failure reports (artifact-only; no model/patch/validation/promotion) |
| **F.6a** complete | Teaching Card Smoke + Copy Polish | Shipped fixture smoke tests and copy-friendly CLI text while keeping the flow inert |
| **F.7** complete | Worker Result Import / Review Stub | Shipped untrusted worker-output intake artifact for manual review; no patch, validation, proposal import, worker launch, model call, promotion, Dream, or Project Evolution behavior |
| **F.8a** complete | Worker Assignment prompt compacting + Goal Brief UI de-dup | UX-only: compact six-section route-card Markdown (safety stated once, JSON record + inert flags unchanged) and a de-duplicated Goal Brief tab that gates Create Worker Assignment behind a usable brief; no new execution power |
| **F.8b** complete | Goal Brief action-bar cleanup | UX-only: staged Goal Brief actions (one primary per stage), Worker Assignment handoff moved below the checklist and gated on a ready brief, single compact card hidden until creation, Review Pack demoted to a collapsed secondary section; no backend/schema/execution change |
| **F.8c** complete | Goal Brief assistive intake simplification | UX-only: one primary intake box + optional details, 3-step stage indicator (Describe/Refine/Handoff), non-blocking checklist wording, friendly "good enough" guidance, assistive button labels, advanced helpers (mode routing/review pack/raw details) collapsed; F.8b gating preserved; no backend/schema/execution change |
| **AUTO.1a** ✅ | Sandbox Self-Evolution Trial Contract | Report-only safety contract that defines five automation levels and scores whether a self-evolution attempt is safe to try (safety/scope/validation/budget/reviewability); blocks self-approval and auto-merge; no model/agent launch, repo edit, push/merge/PR, or validation/benchmark run |
| **AUTO.1b** ✅ | Sandbox Self-Evolution Dry-Run Runner | First executable sandbox layer: copies the repo to a disposable managed sandbox and runs only declared safe validation (A.18) there, reports A.19 side effects, gates on the AUTO.1a contract; no model call, patch generation, real-repo mutation, push/merge/PR, or auto-merge |
| **AUTO.1c** ✅ | Sandbox Patch Candidate Evaluation | Writes a provided patch candidate into the disposable sandbox only (never the real repo), rejects forbidden/traversal/empty/oversized patches, runs A.18 validation + reports A.19 side effects around apply and validation; no patch generation, real-repo write, push/merge/PR, or auto-merge — human review required before graduation |
| **AUTO.1d** ✅ | Sandbox Patch Graduation Review | Review-only gate that consumes an AUTO.1c evaluation artifact and decides whether the candidate is eligible for human review (separates "passed in sandbox" from "ready for human review"); deterministic safety/sandbox/human-gate/patch-safety/validation/side-effect checks; blocks self-approval and auto-merge; no patch apply, validation run, benchmark run, model call, real-repo write, push/merge/PR, or auto-merge |
| **AUTO.1e** ✅ | Sandbox Self-Evolution Evidence Pack | Report-only builder that bundles the AUTO.1a/1b/1c/1d artifacts into one human-readable review package (summary, timeline, verdicts table, risk summary, human review packet); `--trial-dir` auto-discovery; deterministic final verdict (`ready_for_human_review` / `needs_more_validation` / `blocked` / `incomplete_pack`); any hard breach in any artifact blocks; bridge toward future Telegram/GitHub/n8n summaries but contacts none; no execution, patch apply, validation/benchmark run, model call, real-repo write, push/merge/PR, or auto-merge |
| **AUTO.1f** ✅ | End-to-End Sandbox Self-Evolution Smoke Scenario | Deterministic single-trial smoke runner that drives the AUTO.1a→1e chain over one harmless explicit literal patch (creates `pkg/auto1f_smoke_demo.txt` in the sandbox copy only) inside one shared trial directory and `trial_id`; the only execution is declared safe validation (`compileall -q core`) inside a disposable managed sandbox; explicit cleanup (removes the sandbox by default, `--keep-sandbox` keeps it); clean smoke ends at `ready_for_human_review`; no patch generation, real-repo write, model call, push/merge/PR, auto-merge, worker launch, lesson promotion, proposal import, or external automation |
| **ROAD.1** ✅ | Machine-Readable Phase Registry | Report-only validator + deterministic summary/report for roadmap phase metadata; seeds eight conservative phases (ROAD/AUTO/MODEL) and enforces required fields, the four enum vocabularies, unique phase ids, and safety rules (rejects `AUTO_4_AUTO_MERGE`, `merge_allowed`, non-complete human-approval-off / real-repo-write, `network_allowed`, `model_calls_allowed` outside the approval tier, empty allowed_files/validation, and missing forbidden_files); stores validation commands as text and never runs them; prepares the ROAD.2 phase picker; no execution, model, network, patch, push/merge/PR, or external-automation power added |
| **ROAD.2** ✅ | Phase Picker / Night Candidate Report | Report-only classifier that consumes the ROAD.1 registry (reusing its validator, never re-implementing it) and sorts every phase into one of six buckets (`safe_to_prepare` / `sandbox_required` / `human_approval_required` / `blocked` / `deferred_or_parked` / `complete_or_history`) with `reasons` + a `recommended_next_step`; deterministic ranking (risk, automation, track, natural id) picks a `top_recommendation`; an invalid registry yields no candidates; never runs the stored validation commands; prepares the AUTO.2 contracts; no execution, model, network, patch, push/merge/PR, worker-launch, or auto-merge power added |

These features are additive. They do not require implementing any district infrastructure.

---

## Track GOV — Persona Governance

Purpose:
Keep the District Model framing from turning into uncontrolled architecture
sprawl. Track GOV defines and **limits** the governance vocabulary (personas,
layers, transitions) instead of building new personas. It is docs/governance
only.

### GOV.1 — Persona Governance Manifest ✅

Status: **Complete / docs-only.**

Notes:
- defines City / District / Persona / Artifact / Button boundaries
- defines Explorer / Verifier / Arbiter / Courier / Human
- adds persona anti-inflation rules (a new persona needs a distinct responsibility, permissions, forbidden actions, artifact boundary, and a failure mode worth governing)
- parks Neural Lesson Graph / nano-agent ideas for a future report-only **GOV.2 — Neural Lesson Graph Activation Preview** (see the Parking Lot note under Track D)
- no backend execution power added

Core principle: **GOV.1 does not build new personas. GOV.1 limits and defines personas.**

Files:
- `docs/governance/persona_governance_manifest.md`
- README "Persona governance (GOV.1)" section links to the manifest
- `tests/test_persona_governance_manifest.py` (docs guardrail — content only, no execution)

Guardrail (docs-only — nothing below was added):
- no new agent, nano-agent execution, model call, worker launch, patch/apply, validation run, Dream, Project Evolution, webhook/network, lesson promotion, proposal import, database migration, new backend route, or new UI panel.

---

## Track AUTO — Sandbox Self-Evolution

Purpose:
Define the safety contract for future automation in which C.A.T.T.U.S tests
small self-improvement tasks in a disposable sandbox **before** any real repo,
remote git branch, Telegram approval, or external coding agent is given more
power. Track AUTO defines and **scores** self-evolution attempts; it does not
run them.

Core principle: **Self-evolution may be tested in a sandbox. Self-approval is
forbidden.**

### AUTO.1a — Sandbox Self-Evolution Trial Contract ✅

Status: **Complete when implemented — report-only; no execution power added.**

Goal:
Define and score a single sandbox self-evolution attempt and decide whether it
would be safe to try and reviewable by a human — without running anything.

Behaviour:
- Defines five automation levels and only defines/scores them: `LOCAL_0_OBSERVE`
  (read-only checks + report), `LOCAL_1_PREPARE` (planning artifacts only),
  `SANDBOX_2_DRAFT_PATCH` (a proposed patch inside a disposable sandbox only;
  real repo untouched), `REMOTE_3_DRAFT_PR` (future only — not implemented in
  AUTO.1a), and `AUTO_4_AUTO_MERGE` (forbidden). None are executed.
- Scores the attempt on five deterministic dimensions — safety, scope control,
  validation plan, budget, reviewability — and produces a verdict
  (`eligible_for_review`, `not_eligible_for_review`, `blocked`) plus one next
  safe step (`keep_report_only`, `create_worker_assignment`,
  `run_sandbox_trial_manually`, `request_human_approval_for_external_model`,
  `blocked_until_scope_is_narrowed`, `blocked_until_validation_is_declared`).
- Blocks self-approval and auto-merge: `self_approval_allowed=true` or an
  auto-merge level always scores a safety fail → `blocked`.
- Writes `.agent/self_evolution_trials/<trial_id>/self_evolution_trial.json` and
  `.md` (operator-readable: Summary, Scorecard, Automation Levels, Boundaries,
  Next Safe Step), plus `selected_phase.md` and `trial_contract.md` companions.

Rules (report-only — verified by guardrail tests):
- No model or external coding agent launch. No real-repo edit. No push, merge,
  or PR. No validation run. No benchmark run inside the tool.
- No Dream. No Project Evolution execution. No webhook/network. No lesson
  promotion. No proposal import. No worker launch. No database migration. No new
  UI panel.

Status:
- Complete. Report-only self-evolution safety contract; defines automation
  levels; scores safety/scope/validation/budget/reviewability; blocks
  self-approval and auto-merge; no execution power added.
- First step before any n8n / Telegram / GitHub / Claude / Codex automation.
- CLI: `python scripts/create_sandbox_self_evolution_trial.py --phase-id <id> --automation-level <level>`
  (optional `--phase-title`, `--phase-summary`, `--allowed-files`,
  `--validation`, `--budget-tier`, `--json`, `--repo-path`, `--output-root`,
  deterministic `--trial-id` / `--created-at`).
- Files: `core/sandbox_self_evolution_trial.py`,
  `scripts/create_sandbox_self_evolution_trial.py`,
  `tests/test_sandbox_self_evolution_trial.py`.
- Shipment checkpoint: `python -m pytest tests/test_sandbox_self_evolution_trial.py -q`
  — also covered by `python -m compileall` and the existing
  `benchmarks/run_benchmarks.py --check`.

### AUTO.1b — Sandbox Self-Evolution Dry-Run Runner ✅

Status: **Complete when implemented — first executable sandbox layer; no model
calls, no patch generation, no real-repo mutation.**

Goal:
Copy the current repo into a disposable managed sandbox, run only explicitly
declared safe validation commands there, record side effects, and write a review
artifact. The runner may test the sandbox; it may not evolve the real repo.

Behaviour:
- Creates a disposable, managed sandbox copy (marked with a marker file) that
  excludes `.git`, `.agent`, `.tmp`, `tmp_tests`, `__pycache__`, `.pytest_cache`,
  virtualenvs, `node_modules`, build outputs, and local env / secrets.
- Gates on an AUTO.1a trial contract (path or equivalent CLI args). Refuses to
  run when the contract verdict is `blocked`, `self_approval_allowed` is true,
  `eligible_for_auto_merge` is true, the level is `AUTO_4_AUTO_MERGE` or
  `REMOTE_3_DRAFT_PR`, `sandbox_required` is false, or `human_approval_required`
  is false → `blocked_by_contract`.
- Runs only declared safe validation commands inside the sandbox through the
  A.18 safe path (`SafeValidationCommand`: argv, shell disabled, required bounded
  timeout, scrubbed environment — no raw shell fallback, no legacy shell
  validation). No command declared → `validation_skipped`. No full test suite or
  benchmark check runs unless explicitly declared.
- Reports A.19 before/after side effects (created / modified / deleted), confirms
  they were sandbox-only, and keeps `real_repo_modified` false. Side effects are
  reported, never auto-cleaned; only `--cleanup` deletes the whole managed
  sandbox (and cleanup refuses any unmanaged path).
- Verdicts: `dry_run_passed`, `dry_run_failed`, `blocked_by_contract`,
  `validation_skipped`, `sandbox_setup_failed`. Writes
  `.agent/self_evolution_trials/<trial_id>/sandbox_dry_run.json` and `.md`.

Rules (verified by guardrail tests):
- No model call. No patch generation. No patch apply to the real repo. No real
  repo mutation. No push, merge, or PR. No auto-merge.
- No Dream. No Project Evolution execution. No webhook/network. No lesson
  promotion. No proposal import. No worker launch. No remote git host / chat /
  external automation contact.

Status:
- Complete. First executable sandbox layer; uses A.18 safe validation; reports
  A.19 validation side effects; blocks self-approval and auto-merge; no model
  calls, no patch generation, no real-repo mutation.
- CLI: `python scripts/run_sandbox_self_evolution_dry_run.py --repo-path . --validation-json '["python","-m","compileall","-q","core"]'`
  (optional `--trial-contract`, `--validation` text, `--automation-level`,
  `--cleanup`, `--timeout`, `--sandbox-root`, `--output-root`, `--json`,
  deterministic `--trial-id` / `--created-at`).
- Files: `core/sandbox_self_evolution_runner.py`,
  `scripts/run_sandbox_self_evolution_dry_run.py`,
  `tests/test_sandbox_self_evolution_runner.py`.
- Shipment checkpoint: `python -m pytest tests/test_sandbox_self_evolution_runner.py -q`
  — also covered by `python -m compileall` and the existing
  `benchmarks/run_benchmarks.py --check`.

### AUTO.1c — Sandbox Patch Candidate Evaluation ✅

Status: **Complete when implemented — sandbox-only patch evaluation; no model
calls, no patch generation, no real-repo mutation.**

Goal:
Evaluate a *provided* patch candidate inside a disposable managed sandbox. The
evaluator may write the candidate into the sandbox copy only; it must never write
to the real repo, and it never generates a patch itself. Patch candidates may be
tested in a sandbox; they may not graduate without human review.

Behaviour:
- Takes an explicit patch file (unified diff). Rejects, before applying, any
  candidate that touches a forbidden path (`.env`, `.git`, `.agent/private`,
  secrets), an absolute or parent-traversal path, is empty, or is oversized
  (above a conservative line/file ceiling) unless explicitly marked for manual
  review → `patch_candidate_rejected_by_safety`. Path safety reuses the shared
  `evaluate_patch_safety` gate plus a secrets check; it never auto-fixes or
  regenerates the patch.
- Gates on an AUTO.1a trial contract (path or built from args). Refuses to run
  when the verdict is `blocked`, `self_approval_allowed` is true,
  `eligible_for_auto_merge` is true, the level is `AUTO_4_AUTO_MERGE` /
  `REMOTE_3_DRAFT_PR`, `sandbox_required`/`human_approval_required` is false, or
  the level is below the sandbox patch level (unless an explicit evaluation-only
  test mode is set) → `blocked_by_contract`.
- Copies the repo into a managed sandbox (AUTO.1b rules), writes the candidate
  into the sandbox copy only (all-or-nothing; a failed apply is reported, never
  retried → `patch_candidate_failed_apply`), then runs only declared A.18-safe
  validation inside the sandbox. No command → `validation_skipped`.
- Reports A.19 side effects around both the patch apply and the validation
  (files changed by the patch; files created/modified/deleted by validation;
  generated/noisy flags), confirms all effects were sandbox-only, and keeps
  `real_repo_modified` / `patch_applied_to_real_repo` false. Only `--cleanup`
  deletes the managed sandbox.
- Verdicts: `patch_candidate_passed`, `patch_candidate_failed_validation`,
  `patch_candidate_failed_apply`, `patch_candidate_rejected_by_safety`,
  `blocked_by_contract`, `validation_skipped`, `sandbox_setup_failed`. Writes
  `.agent/self_evolution_trials/<trial_id>/patch_candidate_evaluation.json` and
  `.md`.

Rules (verified by guardrail tests):
- No model call. No patch generation. No patch write to the real repo. No real
  repo mutation. No push, merge, or PR. No auto-merge.
- No Dream. No Project Evolution execution. No webhook/network. No lesson
  promotion. No proposal import. No worker launch. No remote git host / chat /
  external automation contact.

Status:
- Complete. Sandbox-only patch candidate evaluation; applies provided candidates
  to a disposable sandbox; uses A.18 safe validation; reports A.19 side effects;
  blocks self-approval and auto-merge; no model, no patch generation, no real
  repo mutation.
- CLI: `python scripts/evaluate_sandbox_patch_candidate.py --repo-path . --patch-file candidate.patch --validation-json '["python","-m","compileall","-q","core"]'`
  (optional `--trial-contract`, `--automation-level`, `--allow-large`,
  `--cleanup`, `--timeout`, `--sandbox-root`, `--output-root`, `--json`,
  deterministic `--trial-id` / `--created-at`).
- Files: `core/sandbox_patch_candidate_evaluation.py`,
  `scripts/evaluate_sandbox_patch_candidate.py`,
  `tests/test_sandbox_patch_candidate_evaluation.py`.
- Shipment checkpoint: `python -m pytest tests/test_sandbox_patch_candidate_evaluation.py -q`
  — also covered by `python -m compileall` and the existing
  `benchmarks/run_benchmarks.py --check`.

### AUTO.1d — Sandbox Patch Graduation Review ✅

Status: **Complete when implemented — review-only; no execution power added.**

Goal:
Consume an AUTO.1c sandbox patch candidate evaluation artifact and decide whether
the candidate is eligible for human review. Passing in a sandbox is not the same
as being safe to graduate: a candidate may be recommended for human review, but
it may not approve itself.

Behaviour:
- Reads a parsed evaluation record (a plain dict) and emits a deterministic
  graduation decision — it reads no files itself in the core and runs nothing.
- Runs eight deterministic checks over the source artifact: the source verdict is
  acceptable (`patch_candidate_passed` acceptable; `validation_skipped`
  conditional; failed-validation / failed-apply / rejected-by-safety /
  blocked-by-contract / sandbox-setup-failed reject or block); the real repo is
  unchanged; effects were sandbox-only; the human gate is intact (human approval
  required, no self-approval, no auto-merge); patch safety (no forbidden /
  traversal path, a provided candidate within a reviewable size, no generated
  patch); validation passed (or, if skipped, more is needed); side effects are
  not suspicious (generated / noisy effects are warnings only; any real repo
  effect blocks); and the candidate is reviewable (touched files recorded).
- Graduation verdicts: `eligible_for_human_review`, `needs_more_validation`,
  `blocked_by_safety`, `not_reviewable`. Recommended next steps:
  `prepare_human_review_packet`, `request_more_validation`, `reject_candidate`,
  `narrow_patch_scope`, `manual_review_required`. Any hard safety failure →
  `blocked_by_safety`; a missing / malformed source artifact → `not_reviewable`.
- Keeps its own guardrail booleans inert (`human_review_required=true`,
  `self_approval_allowed=false`, `eligible_for_auto_merge=false`,
  `real_repo_modified=false`, `patch_applied_to_real_repo=false`,
  `push_performed=false`, `merge_performed=false`, `model_call_performed=false`,
  `validation_run_by_tool=false`, `benchmark_run_by_tool=false`,
  `worker_launch_performed=false`). Writes
  `.agent/self_evolution_trials/<trial_id>/patch_graduation_review.json` and
  `.md` (Summary, Graduation Checks, Blockers, Warnings, Human Review Packet,
  Boundaries), or under `<review_id>` when the source reveals no trial directory.

Rules (review-only — verified by guardrail tests):
- No patch apply. No sandbox patch application. No validation run. No benchmark
  run. No model call. No real-repo mutation. No push, merge, or PR. No auto-merge.
- No subprocess, repo clone, or git. Does not modify the source evaluation
  artifact or inspect secrets.
- No Dream. No Project Evolution execution. No webhook/network. No lesson
  promotion. No proposal import. No worker launch. No remote git host / chat /
  external automation contact. No database migration. No new UI panel.

Status:
- Complete. Review-only graduation gate; consumes sandbox patch evaluation
  artifacts; separates "passed in sandbox" from "ready for human review"; blocks
  self-approval and auto-merge; no execution power added.
- CLI: `python scripts/create_sandbox_patch_graduation_review.py --evaluation <path>`
  (optional `--review-id`, `--created-at`, `--output-root`, `--json`).
- Files: `core/sandbox_patch_graduation_review.py`,
  `scripts/create_sandbox_patch_graduation_review.py`,
  `tests/test_sandbox_patch_graduation_review.py`.
- Shipment checkpoint: `python -m pytest tests/test_sandbox_patch_graduation_review.py -q`
  — also covered by `python -m compileall` and the existing
  `benchmarks/run_benchmarks.py --check`.

### AUTO.1e — Sandbox Self-Evolution Evidence Pack ✅

Status: **Complete when implemented — report-only; no execution power added.**

Goal:
Bundle the AUTO.1a/1b/1c/1d sandbox self-evolution artifacts into one
human-readable evidence pack, so an operator does not need to inspect four
separate files before deciding what to do next. AUTO.1e packages evidence; it
does not execute, approve, apply, push, merge, or contact external systems.

Behaviour:
- Consumes the four artifacts (parsed dicts): the AUTO.1a contract
  (`self_evolution_trial.json`), the AUTO.1b dry run (`sandbox_dry_run.json`), the
  AUTO.1c patch evaluation (`patch_candidate_evaluation.json`), and the AUTO.1d
  graduation review (`patch_graduation_review.json`). A `--trial-dir` shortcut
  auto-discovers those filenames; explicit per-artifact paths override discovery.
  A slot whose `report_kind` does not match is treated as absent (and warned).
- Decides deterministically. Any source artifact that reports a hard breach
  (`self_approval_allowed`, `eligible_for_auto_merge`, `real_repo_modified`,
  `patch_applied_to_real_repo`, `push_performed`, `merge_performed`,
  `model_call_performed`, `worker_launch_performed`, or non-sandbox-only side
  effects) forces `blocked`. Otherwise the graduation review drives the verdict:
  `eligible_for_human_review` → `ready_for_human_review`, `needs_more_validation`
  → `needs_more_validation`, `blocked_by_safety` / `not_reviewable` → `blocked`.
  A missing graduation review (or patch evaluation) → `incomplete_pack`; a
  contract-only pack is valid as `incomplete_pack`, not a failure.
- Final verdicts: `ready_for_human_review`, `needs_more_validation`, `blocked`,
  `incomplete_pack`. Recommended next steps: `review_patch_candidate`,
  `request_more_validation`, `reject_candidate`, `complete_missing_artifacts`,
  `keep_report_only`. Skipped validation anywhere relevant adds a warning.
- Produces one record + Markdown (Summary, Timeline, Verdicts table, Risk Summary,
  Human Review Packet, Blockers, Warnings, Boundaries) and keeps its own guardrail
  booleans inert (`human_review_required=true`, everything else `false`). Writes
  `.agent/self_evolution_trials/<trial_id>/self_evolution_evidence_pack.json` and
  `.md`, or under `<pack_id>` when no trial directory is available.

Rules (report-only — verified by guardrail tests):
- No execution. No patch apply. No sandbox patch application. No validation run.
  No benchmark run. No model call. No real-repo mutation. No push, merge, or PR.
  No auto-merge. Source artifacts are never modified.
- No subprocess, repo clone, or git. Does not inspect secrets.
- No Dream. No Project Evolution execution. No webhook/network. No lesson
  promotion. No proposal import. No worker launch. No remote git host / chat /
  external automation contact. No database migration. No new UI panel.

Status:
- Complete. Report-only evidence bundle; consumes AUTO.1a/1b/1c/1d artifacts;
  creates one human-readable review packet; separates evidence packaging from
  approval/execution; the bridge toward future Telegram / GitHub / n8n summaries
  without contacting them; no execution power added.
- CLI: `python scripts/create_self_evolution_evidence_pack.py --trial-dir <dir>`
  (or explicit `--trial-contract`, `--dry-run`, `--patch-evaluation`,
  `--graduation-review`; optional `--pack-id`, `--created-at`, `--output-root`,
  `--json`).
- Files: `core/self_evolution_evidence_pack.py`,
  `scripts/create_self_evolution_evidence_pack.py`,
  `tests/test_self_evolution_evidence_pack.py`.
- Shipment checkpoint: `python -m pytest tests/test_self_evolution_evidence_pack.py -q`
  — also covered by `python -m compileall` and the existing
  `benchmarks/run_benchmarks.py --check`.

### AUTO.1f — End-to-End Sandbox Self-Evolution Smoke Scenario ✅

Status: **Complete when implemented — orchestration only; no execution power added beyond declared sandboxed validation.**

Goal:
Provide one deterministic single-trial smoke scenario where all AUTO.1 artifacts
share the same `trial_id` and output directory, exercising the AUTO.1a→1e chain
over one harmless patch candidate before any future Telegram / n8n / GitHub
automation is wired in.

Behaviour:
- Uses one deterministic `trial_id` and `created_at` across every step, so the
  resulting artifacts form one coherent single-trial bundle.
- 1a builds a contract (`SANDBOX_2_DRAFT_PATCH`) for a harmless text patch; 1b
  runs a sandbox dry run; 1c evaluates a **fixed, explicit literal** patch
  candidate (creates `pkg/auto1f_smoke_demo.txt` in the sandbox copy only — never
  generated, never written to the real repo); 1d reviews graduation; 1e packages
  the evidence pack. The four chain artifacts are discovered in the shared trial
  directory.
- The only execution is declared safe validation (`python -m compileall -q core`)
  inside a disposable managed sandbox (the AUTO.1b/1c path).
- Cleanup is explicit: the managed sandbox is removed by default and kept with
  `--keep-sandbox`; the result reports `sandbox_exists_after` either way.
- All ten artifacts (five JSON + five Markdown) land under
  `.agent/self_evolution_trials/<trial_id>/`; the clean smoke ends at
  `ready_for_human_review`.
- Operational note: keep the managed sandbox **outside the repo working tree**
  (`--sandbox-root`) when an IDE/language-server builder is active — a repo-local
  copy of a foreign-language project (e.g. a `.csproj` under `benchmarks/cases/`)
  can be rebuilt by an external watcher that races the A.19 side-effect snapshot,
  which the chain honestly reports and downgrades to `needs_more_validation`.

Rules (orchestration only — verified by guardrail tests):
- No model call. No Claude/Codex/Gemini launch. No patch generation. No patch
  apply to the real repo. No validation outside the sandbox. No benchmark
  execution. No real-repo mutation. No push, merge, or PR. No auto-merge.
- No Dream. No Project Evolution execution. No webhook/network. No Telegram / n8n
  / GitHub contact. No lesson promotion. No proposal import. No worker launch. No
  autonomous retry loop. No database migration. No new UI panel.

Status:
- Complete. Deterministic single-trial smoke runner over the AUTO.1a→1e chain;
  one `trial_id` and output directory; one harmless explicit literal candidate;
  explicit sandbox cleanup; clean smoke verdict `ready_for_human_review`; no
  external automation or real-repo mutation power added.
- CLI: `python scripts/run_self_evolution_smoke.py` (optional `--repo-path`,
  `--trial-id`, `--created-at`, `--output-root`, `--sandbox-root`,
  `--keep-sandbox`, `--json`).
- Files: `scripts/run_self_evolution_smoke.py`,
  `tests/test_self_evolution_smoke.py`.
- Shipment checkpoint: `python -m pytest tests/test_self_evolution_smoke.py -q`
  — also covered by `python -m compileall` and the existing
  `benchmarks/run_benchmarks.py --check`.

---
## Future Roadmap Notes — ROAD / AUTO / MODEL

These tracks are future-facing architecture tracks. They should not be treated as immediate implementation unless explicitly promoted into the active roadmap.

Core rule:

> Do not automate “thinking harder.” Automate “choosing safer.”

---

## Track ROAD — Machine-Readable Roadmap

Purpose: make the roadmap readable by both humans and C.A.T.T.U.S.

The current roadmap is mostly prose. Future automation needs structured phase metadata so C.A.T.T.U.S can safely decide what can be prepared, sandboxed, deferred, or escalated.

### ROAD.1 — Machine-Readable Phase Registry ✅

Status: **Complete / shipped (2026-06-18) — report-only; no execution power added.**

Goal: define a structured registry for roadmap phases.

Example fields:

```yaml
phase_id: AUTO.2a
title: Telegram Evidence Summary Contract
track: AUTO
status: proposed
automation_level: LOCAL_1_PREPARE
budget_tier: local_only
allowed_files:
  - core/...
  - scripts/...
  - tests/...
forbidden_files:
  - .env
  - .git
  - .agent/private
validation:
  - python -m pytest tests/test_x.py -q
human_approval_required: true
merge_allowed: false
```

Boundary:

* Registry only.
* No execution.
* No model calls.
* No automatic phase selection yet.

Implemented (2026-06-18):

* Seed registry `docs/roadmap/phase_registry.json` with eight phases (ROAD.1, ROAD.2, AUTO.2a–2c, MODEL.1–3). Every entry is conservative: human approval required; `merge_allowed` / `network_allowed` / `model_calls_allowed` / `writes_real_repo` all false; `AUTO_4_AUTO_MERGE` never appears.
* `core/phase_registry.py` — pure stdlib validator + deterministic summary/report builder (`load_phase_registry`, `validate_phase_registry`, `summarize_phase_registry`, `render_phase_registry_markdown`, `write_phase_registry_report`). Enforces the required root/phase fields, the four enum vocabularies (status / automation_level / budget_tier / risk_level), unique phase ids, and the safety rules: rejects `AUTO_4_AUTO_MERGE`, `merge_allowed=true`, `human_approval_required=false` (non-complete), `writes_real_repo=true` (non-complete), `network_allowed=true`, `model_calls_allowed=true` outside the approval budget tier, empty allowed_files/validation for active/proposed phases, and forbidden_files missing `.env` / `.git` / `.agent/private`.
* `scripts/validate_phase_registry.py` — CLI that writes `.agent/roadmap/phase_registry_report.json` + `.md`; exits nonzero on an invalid registry unless `--allow-invalid-report`.
* Validation commands are stored as **text only** and are never run by ROAD.1.
* No patch generation/apply, validation/benchmark run, sandbox run, push/merge/PR, remote host / chat app / external automation, lesson promotion, proposal import, or worker launch power was added. ROAD.1 prepares ROAD.2 (the phase picker) but selects nothing itself.

Files:

* `core/phase_registry.py`
* `scripts/validate_phase_registry.py`
* `tests/test_phase_registry.py`
* `docs/roadmap/phase_registry.json`

CLI: `python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --output-root .agent/roadmap`

Shipment checkpoint: `python -m pytest tests/test_phase_registry.py -q`

### ROAD.2 — Phase Picker / Night Candidate Report ✅

Status: **Complete / shipped (2026-06-18) — report-only; no execution power added.**

Goal: read the phase registry and produce a report of safe candidate work.

Example output:

* Safe tonight: docs-only/report-only/sandbox-only phases
* Needs human approval: strong model / broad refactor / missing allowed files
* Blocked: no validation plan / unsafe scope / auto-merge requested

Boundary:

* Report-only.
* Does not run phases.
* Does not call models.
* Does not create branches or PRs.

Implemented (2026-06-18):

* `core/phase_picker.py` — pure stdlib classifier that **consumes** the ROAD.1 layer (`pick_phase_candidates`, `summarize_phase_candidates`, `render_phase_picker_markdown`, `write_phase_picker_report`). It reuses `core.phase_registry.validate_phase_registry` and never re-implements the schema validation.
* Every phase is sorted into exactly one bucket — `safe_to_prepare`, `sandbox_required`, `human_approval_required`, `blocked`, `deferred_or_parked`, `complete_or_history` — by deterministic rules over the ROAD.1 metadata. Each candidate carries `reasons` and a `recommended_next_step`.
* Within a bucket, candidates rank by lower risk, then lower automation level, then track order (ROAD, AUTO, MODEL, GOV, A, F, H), then natural phase id. The `top_recommendation` is the best safe candidate.
* **An invalid registry yields no candidates** (`safe_to_prepare` empty, no `top_recommendation`). The validation commands inside the registry are treated as text and are never run.
* `scripts/create_phase_picker_report.py` — CLI that writes `.agent/roadmap/phase_picker_report.json` + `.md`; exits nonzero on an invalid registry unless `--allow-invalid-registry-report`.
* Against the seed registry the five shipped phases (ROAD.1, ROAD.2, AUTO.2a, AUTO.2b, AUTO.2c) classify as `complete_or_history` and the remaining three (MODEL.1–3) as `safe_to_prepare`; MODEL.1 — the only remaining low-risk phase — is the top recommendation, and with the whole AUTO.2 contract track shipped the MODEL track is next. (Seed statuses were synced in **ROAD.2a** (2026-06-18) and **AUTO.2a / AUTO.2b / AUTO.2c** (2026-06-19).)
* No execution, model call, network, patch generation/apply, sandbox run, push/merge/PR, remote host / chat app / external automation, lesson promotion, proposal import, worker launch, or auto-merge power was added. ROAD.2 prepares the AUTO.2 contracts but selects-and-prepares nothing itself.

Files:

* `core/phase_picker.py`
* `scripts/create_phase_picker_report.py`
* `tests/test_phase_picker.py`

CLI: `python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --output-root .agent/roadmap`

Shipment checkpoint: `python -m pytest tests/test_phase_picker.py -q`

---

## Track AUTO (continue) — Controlled Automation

Purpose: gradually reduce biological coordination load while preserving human approval and evidence boundaries.

AUTO.1 establishes local sandbox evidence. Later AUTO.2 may define remote/Telegram/GitHub contracts.

### AUTO.1a–AUTO.1f — Local Sandbox Self-Evolution Chain

Status: active/current near-term chain.

* AUTO.1a: Sandbox Self-Evolution Trial Contract
* AUTO.1b: Sandbox Self-Evolution Dry-Run Runner
* AUTO.1c: Sandbox Patch Candidate Evaluation
* AUTO.1d: Sandbox Patch Graduation Review
* AUTO.1e: Sandbox Self-Evolution Evidence Pack
* AUTO.1f: End-to-End Sandbox Self-Evolution Smoke Scenario

Rule:

> Self-evolution may be tested in a sandbox. Self-approval is forbidden.

### AUTO.2a — Telegram Evidence Summary Contract ✅

Status: **Complete / shipped (2026-06-19) — report-only; no chat / network / model / patch / merge power added.**

Goal: define how C.A.T.T.U.S evidence packs are summarized for Telegram.

Telegram may present:

* phase
* verdict
* tests
* risks
* touched files
* recommended next step
* human action options

Telegram must not:

* bypass branch protection
* approve unsupported claims
* merge failed work
* override C.A.T.T.U.S safety gates

Boundary:

* Contract only.
* No Telegram API integration yet.

Implemented (2026-06-19):

* `core/telegram_evidence_contract.py` — pure stdlib builder that **consumes** an AUTO.1e evidence pack (a parsed dict) and returns a deterministic contract record plus Markdown (`build_telegram_evidence_contract`, `render_telegram_evidence_contract_markdown`, `write_telegram_evidence_contract`). It imports no other `core` module and reads no files.
* The contract carries a `telegram_message` preview, informational `approval_options` (`review`, `defer`, `reject`, `request_more_validation`), a `forbidden_actions` list (`approve_merge`, `push`, `merge`, `apply_patch`, `run_worker`, `launch_model`, `rerun_automation`, `contact_network`), `required_human_checks`, a `risk_summary`, `evidence_links`, and a fixed `guardrails` block.
* **Sendability is conservative.** `is_sendable` is true only for a `ready_for_human_review` or `needs_more_validation` pack with no hard guardrail breach. A `blocked` / `incomplete_pack` source — or any breach (auto-merge eligibility, real-repo write, push/merge, model call, worker launch, self-approval, or a missing human-review gate) — forces `is_sendable=false` with `send_blockers` explaining why. For `needs_more_validation`, `request_more_validation` is emphasised.
* The summary **never implies chat approval is enough to merge**: it always states that human review, local evidence, and branch protection remain required. Every output guardrail is inert (`human_review_required=true`; `telegram_message_sent` / `network_call_performed` / merge / push / model / worker all false).
* `scripts/create_telegram_evidence_contract.py` — CLI that reads `--evidence-pack`, writes `.agent/automation_contracts/telegram_evidence_contract.json` + `.md`, and exits nonzero on a blocked/incomplete source unless `--allow-blocked-summary` (which still keeps the summary not-sendable). It sends nothing.
* Registry synced: AUTO.2a → `complete`. The ROAD.2 picker now classifies the three shipped phases (ROAD.1, ROAD.2, AUTO.2a) as `complete_or_history`; **MODEL.1** is the new top recommendation and **AUTO.2b is unblocked** (its AUTO.2a prerequisite is now complete).
* No Telegram/chat send, webhook, network, model call, patch generation/apply, sandbox run, validation/benchmark run, push/merge/PR, GitHub/n8n contact, lesson promotion, proposal import, worker launch, or auto-merge power was added.

Files:

* `core/telegram_evidence_contract.py`
* `scripts/create_telegram_evidence_contract.py`
* `tests/test_telegram_evidence_contract.py`

CLI: `python scripts/create_telegram_evidence_contract.py --evidence-pack <pack.json> --output-root .agent/automation_contracts`

Shipment checkpoint: `python -m pytest tests/test_telegram_evidence_contract.py -q`

### AUTO.2b — GitHub Remote PR Safety Contract ✅

Status: **Complete / shipped (2026-06-19) — report-only; no GitHub / git / network / model / patch / merge power added.**

Goal: define branch/PR rules before remote automation.

Rules:

* no push to main
* no auto-merge
* required evidence pack
* required checks
* no secrets
* branch naming convention
* labels/comments only after safety checks

Boundary:

* Contract only.
* No remote worker execution yet.

Implemented (2026-06-19):

* `core/github_pr_safety_contract.py` — pure stdlib builder that **consumes** one upstream artifact (an AUTO.1e evidence pack **or** an AUTO.2a evidence summary contract, detected via `detect_source_kind`) and returns a deterministic contract record plus Markdown (`build_github_pr_safety_contract`, `render_github_pr_safety_contract_markdown`, `write_github_pr_safety_contract`). It imports no other `core` module and reads no files.
* The contract carries `pr_readiness`, `required_checks`, `required_branch_protection`, `required_human_checks`, a `forbidden_actions` list (`push_to_main`, `force_push`, `open_pr_without_human_review`, `merge_pr`, `enable_auto_merge`, `bypass_branch_protection`, `apply_patch_to_real_repo`, `launch_worker`, `call_model`, `contact_remote_service`), informational `allowed_future_actions` (`prepare_draft_pr_after_human_review`, `request_more_validation`, `reject_candidate`, `keep_local_only`), a `risk_summary`, `evidence_links`, and a fixed `guardrails` block.
* **PR-readiness is conservative.** `is_pr_draft_allowed_in_future` is true only for a `ready_for_human_review` source with no hard guardrail breach and no carried blocker. `needs_more_validation` requires more validation first; a `blocked` / `incomplete_pack` / missing source — or any breach (real-repo write, patch applied, push/merge, model call, worker launch, self-approval, auto-merge eligibility, or a missing human-review gate) — blocks readiness. `is_merge_allowed` and `is_auto_merge_allowed` are **always false**.
* The contract **never implies a future PR is enough to merge**: it always states that human review and branch protection remain required. Every output guardrail is inert (`human_review_required=true`; `pr_created` / `branch_created` / `github_contacted` / `network_call_performed` / push / merge / model / worker all false).
* `scripts/create_github_pr_safety_contract.py` — CLI that reads `--source-artifact`, writes `.agent/automation_contracts/github_pr_safety_contract.json` + `.md`, and exits nonzero on a blocked/incomplete source unless `--allow-blocked-contract` (which still keeps a PR not allowed). It contacts no remote host and runs no git.
* Registry synced: AUTO.2b → `complete`. The ROAD.2 picker now classifies the four shipped phases (ROAD.1, ROAD.2, AUTO.2a, AUTO.2b) as `complete_or_history`; **MODEL.1** remains the top recommendation and **AUTO.2c is unblocked** (its AUTO.2b prerequisite is now complete).
* No GitHub/remote contact, git command, branch/PR/push/merge, webhook, network, model call, patch generation/apply, sandbox run, validation/benchmark run, Telegram/n8n contact, lesson promotion, proposal import, worker launch, or auto-merge power was added.

Files:

* `core/github_pr_safety_contract.py`
* `scripts/create_github_pr_safety_contract.py`
* `tests/test_github_pr_safety_contract.py`

CLI: `python scripts/create_github_pr_safety_contract.py --source-artifact <artifact.json> --output-root .agent/automation_contracts`

Shipment checkpoint: `python -m pytest tests/test_github_pr_safety_contract.py -q`

### AUTO.2c — n8n Orchestration Dry Run ✅

Status: **Complete / shipped (2026-06-19) — report-only; no n8n / network / Telegram / GitHub / git / model / patch / worker / merge power added.**

Goal: simulate n8n orchestration using existing evidence packs.

Allowed:

* read a sample evidence pack
* produce a fake/limited notification payload
* verify approval wording

Forbidden:

* repo mutation
* external coding agent launch
* GitHub push/PR/merge
* Telegram live action unless explicitly promoted later

Implemented (2026-06-19):

* `core/n8n_orchestration_dry_run.py` — pure stdlib builder that **consumes** one or more upstream artifacts (an AUTO.1e evidence pack, an AUTO.2a evidence summary, and/or an AUTO.2b PR safety contract; each detected via `detect_source_kind`) and returns a deterministic report record plus Markdown (`build_n8n_orchestration_dry_run`, `render_n8n_orchestration_dry_run_markdown`, `write_n8n_orchestration_dry_run`). It imports no other `core` module and reads no files.
* The report lays out a deterministic 7-step simulated plan (`load_evidence_pack`, `build_telegram_summary`, `build_github_pr_safety_contract`, `prepare_human_review_notification`, `wait_for_human_review`, `prepare_future_draft_pr_request`, `stop_before_live_execution`). Each step records a descriptive `would_contact` plus **`actual_contact_performed=false`**, and the `simulated_notifications` / `simulated_remote_actions` are previews only (`actual_send_performed` / `actual_action_performed` are always false).
* **The verdict is conservative.** All-ready sources → `overall_verdict="dry_run_ready_for_human_review"` and `is_orchestration_allowed_in_future=true`. `needs_more_validation` allows a review notification but blocks the draft-PR step. Any blocked/incomplete/missing source — or any hard guardrail breach in any source (push/merge/pr_created/branch_created, real-repo write, model call, worker launch, self-approval, auto-merge eligibility, github/n8n/chat contact, or a missing human-review gate) — forces `overall_verdict="blocked"`. `is_live_execution_allowed`, `is_merge_allowed`, and `is_auto_merge_allowed` are **always false**.
* The report **never implies a dry run is enough to act**: it always states that human review and branch protection remain required before any live remote action. Every output guardrail is inert (`human_review_required=true`; `live_execution_allowed` / `n8n_contacted` / `telegram_message_sent` / `github_contacted` / `network_call_performed` / `pr_created` / `branch_created` all false).
* `scripts/create_n8n_orchestration_dry_run.py` — CLI that reads `--evidence-pack` / `--telegram-contract` / `--github-pr-contract`, writes `.agent/automation_contracts/n8n_orchestration_dry_run.json` + `.md`, and exits nonzero on a blocked dry run unless `--allow-blocked-dry-run`. It contacts nothing and runs no git.
* Registry synced: AUTO.2c → `complete`. The ROAD.2 picker now classifies the five shipped phases (ROAD.1, ROAD.2, AUTO.2a, AUTO.2b, AUTO.2c) as `complete_or_history`; with the whole AUTO.2 contract track shipped, **MODEL.1** is the top recommendation and the three MODEL phases are the remaining safe candidates.
* No n8n/orchestrator contact, webhook, network, Telegram/chat send, GitHub/remote contact, git command, branch/PR/push/merge, model call, patch generation/apply, sandbox run, validation/benchmark run, lesson promotion, proposal import, worker launch, or auto-merge power was added.

Files:

* `core/n8n_orchestration_dry_run.py`
* `scripts/create_n8n_orchestration_dry_run.py`
* `tests/test_n8n_orchestration_dry_run.py`

CLI: `python scripts/create_n8n_orchestration_dry_run.py --evidence-pack <pack.json> --telegram-contract <tg.json> --github-pr-contract <gh.json> --output-root .agent/automation_contracts`

Shipment checkpoint: `python -m pytest tests/test_n8n_orchestration_dry_run.py -q`

---

## Track MODEL — C.A.T.T.U.S-Native Specialist Models

Purpose: reduce cost and improve speed by training small specialist models on C.A.T.T.U.S artifacts.

This track is not about training a general coding model. It is about training small models that help C.A.T.T.U.S route, activate lessons, and decide when expensive external models are worth using.

Core rule:

> The learned model may recommend. Deterministic Driver rules may veto.

---

### MODEL.1 — C.A.T.T.U.S Artifact Dataset Builder

Goal: export C.A.T.T.U.S artifacts into a clean training/evaluation dataset.

Sources:

* Goal Briefs
* Worker Assignments
* Driver Decisions
* Worker Result Reviews
* Teaching Cards
* A.17 Flaky Reviews
* AUTO.1 evidence packs
* patch safety outputs
* lessons / anti-lessons
* benchmark outcomes

Example record:

```json
{
  "input_text": "...",
  "artifact_type": "worker_assignment",
  "label_mode": "Debug",
  "label_risk": "medium",
  "label_vehicle": "cheap_api_allowed",
  "label_next_step": "create_worker_assignment"
}
```

Boundary:

* Dataset/export only.
* No training yet.
* No model authority.

---

### MODEL.2 — Driver Classifier Baseline

Goal: train a small cheap model that predicts Driver-like recommendations.

Possible baseline:

* TF-IDF text features
* logistic regression
* decision tree / random forest

Predicted fields:

* mode
* risk
* vehicle
* missing artifacts
* recommended next step

Boundary:

* Model recommends only.
* Deterministic Driver remains final safety gate.
* No automatic execution.

---

### MODEL.3 — Lesson Graph Activation Dataset

Goal: build dataset for lesson/anti-lesson activation.

Metaphor:

* lesson = neuron
* anti-lesson = inhibition node
* evidence/benchmark/replay = grounding signal
* edge = synapse
* current task = input current
* activation score = which lessons should enter context

Example output:

```json
{
  "activated_lessons": [
    {
      "lesson_id": "lesson_allowed_files_scope",
      "activation_score": 0.91,
      "reason": "Task is broad and file scope is unclear"
    }
  ],
  "activated_anti_lessons": [
    {
      "anti_lesson_id": "anti_wrong_file_assumption",
      "inhibition_score": 0.84,
      "reason": "Task may touch similar-looking files"
    }
  ]
}
```

Boundary:

* Dataset/report-only.
* No auto-promotion.
* No auto-deletion.
* No silent graph mutation.

---

### MODEL.4 — Lesson Activation Scorer Baseline

Goal: train a small model to predict which lessons/anti-lessons should activate for a task.

Possible features:

* task text similarity
* lesson confidence
* lesson recency
* benchmark links
* anti-lesson links
* past success/failure
* mode match
* scope match

Possible baseline:

* rules + weighted scoring
* TF-IDF + logistic regression
* graph-weighted ranker

Boundary:

* Produces activation preview only.
* Arbiter limits top-k context.
* Verifier checks grounding evidence.
* Human or approved process handles persistent graph changes.

---

### MODEL.5 — Edge Recommendation Preview

Goal: recommend possible new lesson/evidence/benchmark edges.

Example:

* lesson A should link to benchmark B
* anti-lesson C should inhibit lesson D
* replay E supports lesson F

Boundary:

* Preview-only.
* No graph mutation without approval.
* No lesson promotion.

---

## Parking Lot:

### GOV.2 / Neural Lesson Graph Activation Preview

GOV.2 remains parked until ROAD/AUTO/MODEL foundations are stable.

Parked by:
GOV.1 — Persona Governance Manifest (`docs/governance/persona_governance_manifest.md`, §5). GOV.1 records this idea as parked and explicitly forbids autonomous nano-agent execution.

Idea:
Treat lessons as knowledge nodes, anti-lessons as inhibition nodes, evidence/benchmark links as grounding edges, and bounded courier/nano-agent behavior as activation pulses.

Boundary:

* Report-only when implemented.
* No autonomous nano-agent execution.
* No unlimited context injection.
* No auto-promotion.
* No patch/apply behavior.

### Future District — Model Lab District

Purpose:
Build and evaluate C.A.T.T.U.S-native specialist models.

Initial targets:
- Driver Classifier
- Lesson Graph Activation Scorer
- Risk / budget classifier
- Artifact completeness classifier

Research targets:
- graph-based lesson activation
- predictive coding-inspired error signals
- non-transformer toy experiments
- small local specialist models

Boundary:
Research and recommendation only. No model produced by this district receives execution authority without Driver, Verifier, sandbox evidence, and human approval.

### Future Cross-District Council — Model Lab Support

Model Lab District may request support from:
- Math District: formalize objectives, labels, scoring, optimization, and evaluation metrics.
- Biology District: provide inspiration from memory, inhibition, replay, pruning, and predictive coding.
- Physics District: check plausibility, resource limits, feedback loops, signal storm risk, and cost/latency constraints.
- Coding District: implement sandboxed experiments and evaluation harnesses.

Boundary:
Biology and physics metaphors are inspiration, not proof. Any Model Lab idea must become a testable artifact before entering production. No trained model or activation scorer receives execution authority without Driver, Verifier, sandbox evidence, and human approval.
---

## Priority Recommendation

After AUTO.1f, preferred order:

1. ROAD.1 — Machine-Readable Phase Registry ✅ shipped (2026-06-18)
2. ROAD.2 — Phase Picker / Night Candidate Report ✅ shipped (2026-06-18)
3. AUTO.2a — Telegram Evidence Summary Contract ✅ shipped (2026-06-19)
4. AUTO.2b — GitHub Remote PR Safety Contract ✅ shipped (2026-06-19)
5. AUTO.2c — n8n Orchestration Dry Run ✅ shipped (2026-06-19)
6. MODEL.1 — C.A.T.T.U.S Artifact Dataset Builder ← next (the ROAD.2 picker's top safe candidate; whole AUTO.2 contract track shipped)
7. MODEL.2 — Driver Classifier Baseline
8. MODEL.3 — Lesson Graph Activation Dataset

Do not start MODEL-G or GOV.2 before the roadmap becomes machine-readable.

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

# Weird Idea: C.A.T.T.U.S as Tower-Defense Commander

C.A.T.T.U.S should not become only a faster coding agent. It should become a tactical supervisor around coding agents.

## Core metaphor

* Model / worker = tower
* Task / bug / migration = enemy
* Big task = boss enemy
* Subtasks = smaller enemies
* Lesson cards = tower upgrades
* Prompt/context cost = upgrade cost
* Validation = enemy HP check
* Human approval = final gate

## Main idea

Do not force every task through one heavy workflow.

Separate modes:

* **Instant Run**: fast, safe, small repair.
* **Commander Run**: slow, strategic, for broad / uncertain / low-confidence / multi-file tasks.
* **Project Evolution**: architecture and migration planning.
* **Dream**: sandboxed exploration.
* **Lesson Mode**: controlled memory upgrade system.

## Commander Run responsibilities

Commander Run should decide:

1. Is this task too large for Instant Run?
2. Should the task be decomposed?
3. Which model/tower should handle each part?
4. Which lesson cards are worth injecting?
5. What is the prompt/context cost?
6. What files are allowed or forbidden?
7. What validation proves success?
8. Did the worker’s change note match the actual diff?

## Key mechanisms

### 1. λ Decomposition

Break a large or uncertain task into smaller owned subtasks.

### 2. λ² Wave Scheduler

Do not spawn every sub-agent at once. Group subtasks into waves.

Example:

* Wave 1: evidence / file discovery
* Wave 2: patch draft
* Wave 3: review / validation / merge check

### 3. Boss Fracture

If one “boss” subtask is still too large, break it into smaller owned parts.

### 4. Lesson Upgrade Budget

Lesson cards are like tower upgrades. They improve model behavior, but cost prompt tokens and context window space.

Inject lessons only when:

* relevance is high
* risk reduction is worth the cost
* the lesson is trusted / active
* it does not crowd out source-code evidence

### 5. Worker Change Ledger

Every worker must write a temporary markdown note explaining:

* what it intended to change
* what it actually changed
* why it changed those files
* which files it touched
* what validation it expects
* what uncertainty remains

### 6. Note-vs-Diff Check

A second model or checker compares:

* worker_change_note.md
* actual changed files / git diff
* allowed files
* forbidden files
* validation result

If the worker touched undeclared or forbidden files, the output becomes suspicious or blocked.

## Difference from Claude Code / Codex

Claude Code and Codex are strong coding workers.

C.A.T.T.U.S should become the commander around workers:

* decides task shape
* routes models
* controls lesson injection
* enforces safety gates
* compares claims vs actual diffs
* validates results
* stores lessons only after evidence

## Product law

Instant Run optimizes for speed with safety.

Commander Run optimizes for control, coordination, evidence, and cost-aware model usage.

Do not make Instant Run carry Commander weight.

Do not let Commander Run bypass Instant safety gates.

## Extra Pro: Agent-as-Customer Readiness

A future trend may be that agents are not only used by developers, but also become “customers” of tools, APIs, MCP servers, plugins, benchmark services, retrieval backends, and automation platforms.

Commander Run gives C.A.T.T.U.S a safe place to evaluate tool adoption.

It can ask:

- Does this tool solve a real bottleneck?
- Is it cheaper than using a stronger model?
- Does it reduce prompt/context cost?
- Does it improve validation, retrieval, safety, or speed?
- What data would it access?
- What permissions does it need?
- Can it be tested in a sandbox first?
- Is there a free/local alternative?
- Does human approval need to happen before payment, install, or API-key use?

Important rule:

C.A.T.T.U.S may recommend, compare, or create a tool-adoption report.

C.A.T.T.U.S must not auto-buy, auto-subscribe, auto-install, expose secrets, or connect paid services without explicit human approval.
