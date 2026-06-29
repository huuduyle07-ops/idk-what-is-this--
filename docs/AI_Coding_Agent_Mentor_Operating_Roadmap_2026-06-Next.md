# C.A.T.T.U.S Next Operating Roadmap — Post-Autonomy Command Doctrine

## 1. Executive Summary

The previous C.A.T.T.U.S operating roadmap arc is complete after ROAD.4. The completed work established a machine-readable phase registry, a phase picker with night candidate reporting, a post-MODEL checkpoint audit, a full EVAL benchmark evidence arc (EVAL.1–3), a full CMD orchestration doctrine arc (CMD.1–4), and a post-EVAL/CMD checkpoint audit (ROAD.4). The autonomy experiment is now frozen: the system has tested local autonomy boundaries, recorded the results, and should not chase broader autonomy as the next default move.

The next roadmap should turn the tested boundary into controlled operating doctrine. That means selecting the next work deliberately, branch by branch, with evidence and human authorization before action. C.A.T.T.U.S may recommend, summarize, compare, classify, and prepare reports, but the human operator remains the final authority for direction, approval, execution, merge decisions, and any future unlock.

NEXT.1 is the seed for that decision. It defines candidate branches and decision rules. It does not implement features, add runtime behavior, increase autonomy, or open remote execution.

## 2. Frozen Checkpoint

The completed roadmap arc is frozen at the following checkpoint.

### ROAD: Governance, Registry, Picker, Audit

- ROAD.1 created the machine-readable phase registry.
- ROAD.2 added the phase picker and night candidate report.
- ROAD.3 completed the post-MODEL checkpoint audit.
- ROAD.4 completed the post-EVAL/CMD checkpoint audit (verifies EVAL.1–3 and CMD.1–4).
- The phase registry is valid (33 phases, 4 ROAD + 3 AUTO + 3 MODEL + 3 EVAL + 4 CMD + 4 HARDEN + 12 UX).
- The phase picker currently has no safe candidates.
- The top recommendation is `null`.

### AUTO: Remote Safety Contracts, Dry Run Only

- AUTO.2a defined the Telegram evidence summary contract.
- AUTO.2b defined the GitHub remote PR safety contract.
- AUTO.2c defined the n8n orchestration dry run.
- Remote work remains contract-first and dry-run-only.
- No live remote execution is authorized by the completed AUTO arc.

### MODEL: Advisory Dataset And Baseline Pipeline

- MODEL.1 created the C.A.T.T.U.S artifact dataset builder.
- MODEL.2 created the driver classifier baseline.
- MODEL.3 created the lesson graph activation dataset.
- MODEL outputs remain advisory only.
- No learned model has live routing, veto, merge, or execution authority.

### Validation State

- Registry validation is passing.
- The current phase picker result is intentionally empty because no safe candidate is available under the current map.
- The old roadmap arc is complete and should not be stretched to imply new authorization.

### Benchmark State

- One live benchmark flake was observed.
- An isolated rerun passed 3/3.
- No urgent patch is required.
- The flake still creates a trust question for future benchmark interpretation, which makes benchmark evidence work the strongest next candidate.

## 3. Design Principles

- Evidence before action.
- Advisory models only.
- Remote contracts before remote execution.
- Human approval remains required.
- Benchmark trust before bigger autonomy.
- Operator clarity before feature expansion.

These principles should govern every branch below. Report-only work should come first when a branch touches trust, autonomy, remote action, model influence, or operator-facing execution decisions.

## 4. Candidate Branches

### Branch EVAL — Trust the Run

Purpose:

- Create a benchmark ledger.
- Compare run-to-run evidence.
- Classify flakes.
- Compare replay evidence.
- Track stochastic model behavior.

Example phases:

- EVAL.1 — Live Benchmark Run Ledger — ✅ shipped 2026-06-22 (complete).
- EVAL.2 — Benchmark Report Compare / Single-Case Flake Evidence — ✅ shipped 2026-06-22 (complete).
- EVAL.3 — Flake Classification Report — ✅ shipped 2026-06-22 (complete).
- EVAL.4 — Run Variance Dashboard

Branch boundary:

- EVAL may read benchmark reports and produce evidence summaries.
- EVAL must not change benchmark scoring, benchmark cases, model calls, patch behavior, or runtime behavior unless a later approved phase explicitly changes scope.

### Branch UX — Use It Daily

Purpose:

- Clean up the web/operator surface.
- Reduce button overload.
- Clarify evidence panels.
- Make the common workflow obvious.
- Hide dangerous and debug features behind disclosure.

Example phases:

- UX.1 — Operator Cockpit & Idea Intake Plan — ✅ shipped 2026-06-24 (complete).
- UX.2 — Run Timeline / Progress Surface — ✅ shipped 2026-06-25 (complete).
- UX.3 — Continue-from-Frame Contract — ✅ shipped 2026-06-26 (complete).
- UX.4 — Mixed Mode Intent Router Preview — ✅ shipped 2026-06-26 (complete).
- UX.5 — Goal Brief 4W1H Simplifier — ✅ shipped 2026-06-26 (complete).
- UX.6 — Evidence Card Layout — ✅ shipped 2026-06-26 (complete).
- UX.7 — Cockpit Navigation & Action Hierarchy Cleanup — ✅ shipped 2026-06-27 (complete).
- UX.8 — Cockpit Usability Checkpoint — ✅ shipped 2026-06-27 (complete).
- UX.9 — Unified Workbench Input Plan — ✅ shipped 2026-06-27 (complete).
- UX.10 — Unified Workbench Input Visual Integration — ✅ shipped 2026-06-27 (complete).
- UX.11 — Unified Workbench Behavior Preservation Check — ✅ shipped 2026-06-28 (complete).
- UX.CLOSE — UX Branch Freeze Checkpoint — ✅ shipped 2026-06-28 (complete). UX branch is frozen.

Branch boundary:

- UX may improve operator comprehension and workflow layout.
- UX must not weaken approvals, hide required evidence, make dangerous actions easier to trigger, or add new autonomous behavior.

Next recommendation: the UX branch is complete and frozen at UX.CLOSE,
HARDEN.CLOSE has consolidated HARDEN.1-HARDEN.3 evidence, and
MIRROR.1/MIRROR.2/MIRROR.3 have shipped the report-only trace, scoring, and
claim-vs-diff foundation. The phase picker now recommends
**MIRROR.4 - Mirror Tunnel Replay Readiness Pack** as the next
human-approved report-only branch step.

### Branch CMD — Commander Mode

Purpose:

- Design big-task orchestration.
- Define a decomposition contract.
- Estimate budget and time.
- Define stop conditions.
- Support tower-defense style planning.
- Avoid autonomous merge or execution.

Example phases:

- CMD.1 — Commander Run Contract — shipped 2026-06-22 (complete).
- CMD.2 — Task Decomposition Preview — shipped 2026-06-22 (complete).
- CMD.3 — Budget Governor Preview — shipped 2026-06-22 (complete).
- CMD.4 — Commander Readiness / Stop Condition Report — shipped 2026-06-22 (complete).

Branch boundary:

- CMD may design previews, reports, contracts, and planning doctrine.
- CMD must not authorize autonomous merge, live execution, remote execution, or model-directed routing.

### Branch MODEL — Advisory Learning

Purpose:

- Improve MODEL.1, MODEL.2, and MODEL.3 datasets.
- Add more labels.
- Compare deterministic signals against learned advisory signals.
- Keep learned outputs advisory.
- Avoid live routing authority.

Example phases:

- MODEL.N1 — Dataset Coverage Report
- MODEL.N2 — Driver Baseline Compare
- MODEL.N3 — Lesson Activation Scorer Preview
- MODEL.N4 — Advisory Model Veto Contract

Branch boundary:

- MODEL may generate reports, coverage analysis, baseline comparisons, and advisory previews.
- MODEL must not grant live authority to learned signals or replace deterministic safety gates.

### Branch REMOTE — Locked Remote Shell

Purpose:

- Keep Telegram, GitHub, and n8n locked.
- Prepare contracts and dry runs only.
- Prevent real network action until an explicit future unlock phase.

Example phases:

- REMOTE.1 — Remote Unlock Criteria
- REMOTE.2 — Human Approval Ceremony Contract
- REMOTE.3 — Dry-Run Replay Before Live Remote
- REMOTE.4 — Remote Kill Switch Contract

Branch boundary:

- REMOTE may define criteria, ceremonies, kill switches, replay checks, and dry-run evidence.
- REMOTE must not send live messages, open remote PRs, trigger n8n, or perform real network side effects.

### Track S — Skill / Prompt Optimization Evidence Loop

S.1 Skill Registry
S.2 Skill Eval Report
S.3 Rejected Edit Buffer
S.4 Bounded Edit Draft
S.5 Promotion Gate
S.6 Optional optimizer experiment

## 5. Recommended Priority

Recommended branch order:

1. EVAL — shipped through EVAL.3
2. CMD — selected after EVAL; CMD.1, CMD.2, CMD.3, and CMD.4 shipped
3. UX - shipped through UX.CLOSE
4. HARDEN - shipped through HARDEN.CLOSE
5. MIRROR - next recommended report-only branch
6. MODEL
7. REMOTE

EVAL went first because a live benchmark flake appeared. EVAL.1, EVAL.2, and EVAL.3 are now shipped, giving C.A.T.T.U.S a report-only benchmark ledger, case comparison evidence, and flake classification before relying on larger operational claims.

CMD is selected next because large-task orchestration needs doctrine before implementation. CMD.1 is now shipped as a report-only Commander Run Contract that decides planning mode only and previews gates, budgets, evidence, and stop conditions without adding execution power. CMD.2 is also shipped as a report-only Task Decomposition Preview that turns a CMD.1 contract or task text into phase, evidence, validation, benchmark, budget, rollback, and human-checkpoint previews without executing the plan. CMD.3 is shipped as a report-only Budget Governor Preview that estimates budget limits, status, escalation rules, stop conditions, and human checkpoints from CMD.1/CMD.2 inputs without enforcing or executing anything. CMD.4 is shipped as a report-only Commander Readiness / Stop Condition Report that combines CMD.1/CMD.2/CMD.3 artifacts into readiness, gate, budget, stop-condition, and human-approval evidence without declaring anything ready for execution. ROAD.4 is shipped as a report-only Post-EVAL/CMD Checkpoint Audit that verifies all seven EVAL/CMD phases are registered, complete, report-only, artifact-backed, and documented — closing the EVAL and CMD arcs.

UX remains important because operator clarity is required for daily use. If the operator cannot quickly see evidence, approvals, risk, and common workflow state, the system becomes harder to supervise even when the underlying safety contracts are sound.

MODEL should go fourth because the current dataset is small. More coverage, labels, and comparisons are useful, but model output must remain advisory until there is much stronger evidence and explicit authorization.

REMOTE should go last because remote execution should stay locked. Telegram, GitHub, and n8n work should remain in contract and dry-run form until a future roadmap explicitly accepts unlock criteria and operator approval ceremony requirements.

## 6. First Proposed Next Phase

### EVAL.1 — Live Benchmark Run Ledger

**Status: shipped 2026-06-22 (complete).** Implemented report-only as
`core/benchmark_run_ledger.py` + `scripts/create_benchmark_run_ledger.py`, registered
as a `complete` EVAL-track phase in `docs/roadmap/phase_registry.json`, and validated
with `tests/test_benchmark_run_ledger.py`. The ledger reads
`.agent/benchmarks/benchmark_report_*.json` and writes
`.agent/eval/benchmark_run_ledger/benchmark_run_ledger.{json,md}`. It runs no
benchmarks, calls no models, and changes no scoring or cases.

**EVAL.2 — Benchmark Report Compare / Single-Case Flake Evidence is also shipped
2026-06-22 (complete).** Implemented report-only as `core/benchmark_report_compare.py`
+ `scripts/compare_benchmark_reports.py`, registered as a `complete` EVAL-track phase
(prerequisite EVAL.1) in `docs/roadmap/phase_registry.json`, and validated with
`tests/test_benchmark_report_compare.py`. It explains one case (or every flake
candidate) across `.agent/benchmarks/benchmark_report_*.json` — report ordering, case
timeline, evidence labels, conservative classification, and an optional EVAL.1 ledger
cross-check — and writes `.agent/eval/benchmark_report_compare/<case_id>_compare.{json,md}`.
It runs no benchmarks, calls no models, and changes no scoring or cases.

**EVAL.3 — Flake Classification Report is also shipped 2026-06-22 (complete).**
Implemented report-only as `core/flake_classification_report.py` +
`scripts/create_flake_classification_report.py`, registered as a `complete`
EVAL-track phase (prerequisite EVAL.2) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_flake_classification_report.py`. It reads the EVAL.1
ledger, EVAL.2 compare reports, and benchmark reports only as fallback evidence;
then writes `.agent/eval/flake_classification_report/flake_classification_report.{json,md}`.
It produces stable / likely_flake / likely_broken / needs_rerun /
insufficient_history buckets, conservative human actions, and no benchmark/model/
patch/validation/network/worker/merge power.

**CMD.1 — Commander Run Contract is also shipped 2026-06-22 (complete).**
Implemented report-only as `core/commander_run_contract.py` +
`scripts/create_commander_run_contract.py`, registered as a `complete`
CMD-track phase (prerequisite EVAL.3) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_commander_run_contract.py`. It accepts a plain-text
task and optional scope/risk context, then writes
`.agent/commander/contracts/<contract_id>.{json,md}` classifying the task as
`instant_run`, `commander_run`, `needs_clarification`, or `reject_or_defer`. It
previews required gates and stop conditions, but adds no Commander execution,
agent launch, model call, patch apply, validation run, benchmark run, network
call, database write, worker launch, push, merge, or PR power.

**CMD.2 — Task Decomposition Preview is also shipped 2026-06-22 (complete).**
Implemented report-only as `core/commander_task_decomposition.py` +
`scripts/create_commander_task_decomposition.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.1) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_commander_task_decomposition.py`. It reads an optional
CMD.1 contract or task text, then writes
`.agent/commander/decomposition_previews/<preview_id>.{json,md}` with a deterministic
phase plan plus evidence, validation, benchmark, budget, rollback, and human
checkpoint previews. It adds no decomposition execution, agent launch, model call,
patch apply, validation run, benchmark run, network call, database write, worker
launch, push, merge, or PR power.

**CMD.3 — Budget Governor Preview is also shipped 2026-06-22 (complete).**
Implemented report-only as `core/commander_budget_governor.py` +
`scripts/create_commander_budget_governor.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.2) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_commander_budget_governor.py`. It reads an optional
CMD.1 contract and optional CMD.2 decomposition preview, then writes
`.agent/commander/budget_previews/<preview_id>.{json,md}` with deterministic file,
line, time, phase, budget-limit, escalation-rule, stop-condition, and human
checkpoint previews. It adds no budget enforcement, Commander execution, agent
launch, model call, patch apply, validation run, benchmark run, network call,
database write, worker launch, push, merge, or PR power.

**CMD.4 — Commander Readiness / Stop Condition Report is also shipped 2026-06-22
(complete).** Implemented report-only as `core/commander_readiness_report.py` +
`scripts/create_commander_readiness_report.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.3) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_commander_readiness_report.py`. It reads optional
CMD.1, CMD.2, and CMD.3 artifacts, then writes
`.agent/commander/readiness_reports/<report_id>.{json,md}` with deterministic
readiness status, gate summary, budget summary, stop-condition aggregation,
human-approval requirements, and required-before-implementation items. It adds no
readiness execution, Commander execution, agent launch, model call, patch apply,
validation run, benchmark run, network call, database write, worker launch, push,
merge, or PR power.

**UX.4 — Mixed Mode Intent Router Preview is shipped 2026-06-26 (complete).**
Implemented as `core/mixed_mode_intent_router.py` + `scripts/create_mixed_mode_intent_router_preview.py`,
registered as a `complete` UX-track phase (prerequisite UX.3) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_mixed_mode_intent_router.py` (38 tests +
1 skipped). UX.4 classifies user text into one of six intent modes (chat / instant_run /
continue_from_frame / commander_plan / clarify / reject_or_defer) using deterministic signal matching.
Includes routing policy, UI contract, per-mode allowed/forbidden next steps, mode count summary,
ambiguous and rejected/deferred input surfaces, and demo mode. A read-only "Mixed Mode Router"
placeholder panel was added to `web/templates/index.html` (Views tab group).
Artifacts: `.agent/ux/mixed_mode_intent_router/mixed_mode_intent_router_preview.{json,md}`. No router
dispatch, agent launch, model call, patch apply, validation run, benchmark run, network call, database
write, worker launch, push, merge, or PR power was added.

**UX.5 — Goal Brief 4W1H Simplifier is shipped 2026-06-26 (complete).**
Implemented as `core/goal_brief_4w1h.py` + `scripts/create_goal_brief_4w1h_preview.py`,
registered as a `complete` UX-track phase (prerequisite UX.4) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_goal_brief_4w1h.py` (57 tests).
UX.5 scores operator Goal Briefs across five 4W1H dimensions (What/Why/Where/When-stop/How-validate),
classifies each field as strong/present/weak/missing (score 0–100), generates clarifying questions for
incomplete fields, and recommends a mode hint (instant_run_preview, commander_contract_preview, clarify,
chat). Includes simplified goal brief, field completeness aggregates, allowed/forbidden next steps, demo
mode covering all four hint types, and boundary text. A read-only "4W1H Goal Brief" placeholder panel
was added to `web/templates/index.html` (Views tab group).
Artifacts: `.agent/ux/goal_brief_4w1h/goal_brief_4w1h_preview.{json,md}`. No goal execution,
dispatch, agent launch, model call, patch apply, validation run, benchmark run, network call, database
write, worker launch, push, merge, or PR power was added.

**UX.6 — Evidence Card Layout is shipped 2026-06-26 (complete).**
Implemented as `core/evidence_card_layout.py` + `scripts/create_evidence_card_layout_preview.py`,
registered as a `complete` UX-track phase (prerequisite UX.5) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_evidence_card_layout.py` (42 tests + 1 skipped).
Defines 8 canonical card types (answer_summary, patch_summary, changed_files, validation_summary,
benchmark_summary, risk_summary, human_review, next_action), six card statuses (pass/warn/fail/missing/info/blocked),
three priorities (high/medium/low), five display groups (result/change/checks/risk/decision), and a four-outcome
deterministic operator decision summary (ready_for_human_review, needs_more_evidence, blocked_by_failed_check,
insufficient_information). A read-only "Evidence Cards" placeholder panel was added to `web/templates/index.html`.
Artifacts: `.agent/ux/evidence_card_layout/evidence_card_layout_preview.{json,md}`. No evidence creation,
execution, agent launch, AI service call, patch apply, validation run, benchmark run, network call, database
write, worker launch, push, merge, or PR power was added.

**UX.7 — Cockpit Navigation & Action Hierarchy Cleanup is shipped 2026-06-27 (complete).**
Implemented as `core/cockpit_action_hierarchy.py` + `scripts/create_cockpit_action_hierarchy_report.py`,
registered as a `complete` UX-track phase (prerequisite UX.6) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_cockpit_action_hierarchy.py` (36 tests).
Restructures `web/templates/index.html` navigation into three tiers: Primary (Workbench/Memory/Settings),
Workflow (Run Timeline/Mode Decision/Goal Brief+4W1H/Evidence Cards/Continue From Frame), and a collapsible
Advanced/Debug drawer (Benchmarks/Dream/Graph). Merges the separate "Goal Brief" and "4W1H Goal Brief" nav
tabs into one "Goal Brief / 4W1H" entry. Relabels "Mixed Mode Router" to "Mode Decision". Adds cockpit-section
CSS in `web/static/style.css` for the workflow group and advanced drawer. Extends `showWorkspaceTab()` valid
array to include all UX panel IDs (run-timeline, continue-from-frame, mixed-mode-router, goal-brief-4w1h,
evidence-cards). No new backend routes, mutation routes, execution powers, model calls, network calls,
patches, validation, benchmarks, workers, push, merge, or PRs added.

**UX.8 — Cockpit Usability Checkpoint is shipped 2026-06-27 (complete).**
Implemented as `core/cockpit_usability_checkpoint.py` +
`scripts/create_cockpit_usability_checkpoint.py`, registered as a `complete`
UX-track phase (prerequisite UX.7) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_cockpit_usability_checkpoint.py`. UX.8 is a report-only
checkpoint that audits the goal-to-review cockpit workflow: Goal Brief / 4W1H,
Mode Decision, chat/run/continue/commander start, Run Timeline, Answer / Patch
review, Evidence Cards, Continue From Frame, and Advanced / Debug. It writes
`.agent/ux/cockpit_usability_checkpoint/cockpit_usability_checkpoint.{json,md}`
with deterministic checkpoint usability scores, navigation findings, action hierarchy
findings, operator questions, UX risks, manual review checklist, and a recommended
next phase. Default recommendation: UX.9 — Unified Workbench Input Plan, because
Chat vs Instant Run remains the major structural split. No backend routes, mutation
routes, execution powers, model calls, network calls, patches, validation, benchmarks,
workers, database writes, push, merge, or PRs added.

**UX.9 — Unified Workbench Input Plan is shipped 2026-06-27 (complete).**
Implemented as `core/unified_workbench_input_plan.py` +
`scripts/create_unified_workbench_input_plan.py`, registered as a `complete`
UX-track phase (prerequisite UX.8) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_unified_workbench_input_plan.py`. UX.9 is a plan-only
contract for one Workbench input that conceptually merges Chat, Instant Run, and
Goal Brief / 4W1H. It defines the unified input field schema, the help-only `?`
activation helper, UX.4-style mode preview, explicit confirmation actions, button
reduction plan, future UI layout plan, and staged migration plan. Artifacts:
`.agent/ux/unified_workbench_input_plan/unified_workbench_input_plan.{json,md}`.
Next likely: UX.10 — Unified Workbench Input Visual Integration. No auto-dispatch,
execution-path merge, backend route, mutation route, run start, model call, patch
apply, validation run, benchmark run, network call, database write, worker launch,
push, merge, or PR power was added.

**UX.10 — Unified Workbench Input Visual Integration is shipped 2026-06-27 (complete).**
Implemented in `web/templates/index.html` and `web/static/style.css`, registered as a
`complete` UX-track phase (prerequisite UX.9) in `docs/roadmap/phase_registry.json`,
and validated with `tests/test_unified_workbench_visual_integration.py`. UX.10 makes
the existing agent form read visually as one Unified Workbench: one main intent input,
compact 4W1H helper rows with help-only `?` affordances, preview-only mode chips,
confirmation actions that reuse existing mode switching or workflow navigation, and an
explicit safety note that mode preview does not auto-dispatch. Existing behavior is
preserved: no backend route was added, no execution path was merged, no new fetch/post
path was introduced, and Apply / Review Patch remains separate and human-triggered.
Follow-up: UX.11 — Unified Workbench Behavior Preservation Check.

**UX.CLOSE — UX Branch Freeze Checkpoint is shipped 2026-06-28 (complete).**
Implemented as `core/ux_branch_freeze_checkpoint.py` +
`scripts/create_ux_branch_freeze_checkpoint.py`, registered as a `complete` UX-track
phase (prerequisite UX.11) in `docs/roadmap/phase_registry.json`, and validated with
`tests/test_ux_branch_freeze_checkpoint.py`. UX.CLOSE is a report-only checkpoint that
proves the UX branch (UX.1 through UX.11) is complete, behavior-preserving, and safe to
freeze. It verifies: UX.1–UX.11 are registered complete and report-only; the Unified
Workbench visual integration exists; the UX.11 behavior preservation check exists and
passes; the UX branch added no new execution path; UX.10/UX.11 added no new mutation
route; dangerous actions remain separate and human-triggered; Goal Brief / 4W1H / Mode
Preview remain assistive or preview-only; Apply / Review Patch remains outside the
unified input and requires human action; and remaining UX work is future polish only.
It reuses the phase picker for registry state and ingests the UX.11 report (built from
source text) so the freeze criteria are proven by the same source-level checks. Artifacts:
`.agent/ux/ux_branch_freeze_checkpoint/ux_branch_freeze_checkpoint.{json,md}`. No model
call, patch apply, validation run, benchmark run, network call, database write, worker
launch, backend or mutation route, UI behavior change, push, merge, or PR power was added.
The UX and HARDEN branches are now frozen, and MIRROR.1/MIRROR.2/MIRROR.3 have
shipped the trace contract, derailment scoring report, and claim-vs-diff check.
The recommended next move is MIRROR.4 - Mirror Tunnel Replay Readiness Pack.

**UX.11 — Unified Workbench Behavior Preservation Check is shipped 2026-06-28 (complete).**
Implemented as `core/unified_workbench_behavior_preservation.py` +
`scripts/create_unified_workbench_behavior_preservation_report.py`, registered as a
`complete` UX-track phase (prerequisite UX.10) in `docs/roadmap/phase_registry.json`,
and validated with `tests/test_unified_workbench_behavior_preservation.py`. UX.11
proves UX.10 preserved behavior: the existing `agentForm`, real `query` textarea,
primary submit path, help-only 4W1H helpers, preview-only Mode Preview, Goal Brief
builder access, separate human-triggered Apply / Review Patch, no Workbench POST or
mutation route, and no auto-run/fetch path. Optional artifacts:
`.agent/ux/unified_workbench_behavior_preservation/unified_workbench_behavior_preservation_report.{json,md}`.
Next likely: UX.CLOSE — UX Branch Freeze Checkpoint.

**UX.3 — Continue-from-Frame Contract is shipped 2026-06-26 (complete).**
Implemented as `core/continue_from_frame_contract.py` + `scripts/create_continue_from_frame_contract.py`,
registered as a `complete` UX-track phase (prerequisite UX.2) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_continue_from_frame_contract.py` (25 tests).
UX.3 defines the contract for continuing from a prior run frame: frame schema (24 required fields),
allowed/forbidden continuation modes, reusable/excluded context policies, human confirmation policy,
staleness policy (fresh/possibly_stale/stale/unknown), and UI contract. A read-only "Continue From
Frame" placeholder panel was added to `web/templates/index.html` (Views tab group).
Artifacts: `.agent/ux/continue_from_frame_contract/continue_from_frame_contract.{json,md}`. No
continuation execution, agent launch, model call, patch apply, validation run, benchmark run, network
call, database write, worker launch, push, merge, or PR power was added. Next likely: UX.4 — Mixed
Mode Intent Router Preview.

**UX.2 — Run Timeline / Progress Surface is shipped 2026-06-25 (complete).**
Implemented as `core/run_timeline_surface.py` + `scripts/create_run_timeline_surface.py`,
registered as a `complete` UX-track phase (prerequisite UX.1) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_run_timeline_surface.py`.
UX.2 is a passive visibility layer: it surfaces run progress from existing or explicitly
supplied event state via a deterministic timeline data model (10 stages, 7 statuses, a
progress-percent heuristic, blocking-event surface, and next-operator-action field).
Artifacts: `.agent/ux/run_timeline_surface/run_timeline_surface.{json,md}`. A read-only
Run Timeline panel was added to `web/templates/index.html` (Views tab group). No new
mutation routes were introduced. No task execution, agent launch, model call, patch apply,
validation run, benchmark run, network call, database write, worker launch, push, merge,
or PR power was added.

**HARDEN.1 — Web Mutation Auth / CSRF Gate is shipped 2026-06-23 (complete).**
Implemented as `web/auth_gate.py` wired into `web/app.py` via `before_request`, registered
as a `complete` HARDEN-track phase (prerequisite ROAD.4) in `docs/roadmap/phase_registry.json`,
and validated with `tests/test_web_mutation_auth_gate.py`. It adds a centralized Flask gate
that blocks unauthenticated or cross-origin mutating HTTP requests (POST/PUT/PATCH/DELETE).
Token reads `WEB_AUTH_TOKEN` env var at request time; loopback-only fallback when unset.
Cross-origin mutations are always rejected. Adds no model call, patch apply, validation run,
benchmark run, network call, database write, worker launch, push, merge, or PR power.

**HARDEN.2 — Web Mutation Surface Audit is shipped 2026-06-28 (complete).**
Implemented report-only as `core/web_mutation_surface_audit.py` +
`scripts/create_web_mutation_surface_audit.py`, registered as a `complete`
HARDEN-track phase (prerequisites UX.CLOSE and HARDEN.1) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_web_mutation_surface_audit.py` plus the HARDEN.1 gate tests. It
inspects the Flask `app.url_map`, classifies safe/read-only versus mutating
methods, flags high-risk route keywords, reports dangerous-sounding GET-only
routes for manual review, checks route modules that define routes but are not in
the app map, and confirms mutating routes are covered by the HARDEN.1 gate.
Artifacts: `.agent/harden/web_mutation_surface_audit/web_mutation_surface_audit.{json,md}`.
Adds no model call, patch apply, validation run, benchmark run, network call,
database write, worker launch, Dream execution, Replay janitor apply, route
behavior change, auth policy change, UI behavior change, push, merge, or PR power.

**HARDEN.3 — Safe Validation / MCP Approval Enforcement Audit is shipped 2026-06-29 (complete).**
Implemented report-only as `core/safe_validation_mcp_approval_audit.py` +
`scripts/create_safe_validation_mcp_approval_audit.py`, registered as a
`complete` HARDEN-track phase (prerequisite HARDEN.2) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_safe_validation_mcp_approval_audit.py` plus the HARDEN.1 and
HARDEN.2 safety tests. It statically inspects local Python source for validation
execution, MCP/tool-style artifact actions, janitor/apply/delete cleanup paths,
approval-sensitive fields, and route metadata. It reports gate evidence such as
safe-validation helpers, command safety checks, temp-clone/sandbox boundaries,
MCP allowlists, audit logging, confirmation tokens, HARDEN.1 auth coverage, and
human-approval policy fields. Artifacts:
`.agent/harden/safe_validation_mcp_approval_audit/safe_validation_mcp_approval_audit.{json,md}`.
Adds no model call, patch apply, validation run, benchmark run, MCP invocation,
worker launch, Dream execution, Replay janitor apply, network call, database
write, route behavior change, auth policy change, UI behavior change, push,
merge, or PR power. Then shipped: HARDEN.CLOSE - Hardening Branch Checkpoint.

**HARDEN.CLOSE - Hardening Branch Checkpoint is shipped 2026-06-29 (complete).**
Implemented report-only as `core/hardening_branch_checkpoint.py` +
`scripts/create_hardening_branch_checkpoint.py`, registered as a `complete`
HARDEN-track phase (prerequisite HARDEN.3) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_hardening_branch_checkpoint.py` plus the HARDEN.1, HARDEN.2, and
HARDEN.3 safety tests. It reads the phase registry, HARDEN.1 source markers,
and existing HARDEN.2/HARDEN.3 artifacts, then decides whether the HARDEN branch
is frozen, frozen with manual-review warnings, needs HARDEN.4, or is blocked.
Artifacts:
`.agent/harden/hardening_branch_checkpoint/hardening_branch_checkpoint.{json,md}`.
Adds no model call, patch apply, validation run, benchmark run, MCP invocation,
worker launch, Dream execution, Replay janitor apply, Docker/subprocess use,
network call, database write, route behavior change, auth policy change, UI
behavior change, push, merge, or PR power. MIRROR.1, MIRROR.2, and MIRROR.3
have since shipped; next likely: MIRROR.4 - Mirror Tunnel Replay Readiness Pack.

**MIRROR.1 - Mirror Tunnel Trace Contract is shipped 2026-06-29 (complete).**
Implemented as `core/mirror_tunnel_trace_contract.py` +
`scripts/create_mirror_tunnel_trace_contract.py`, registered as a `complete`
MIRROR-track phase (prerequisite HARDEN.CLOSE) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_trace_contract.py`. It reads explicit existing
artifact paths and writes
`.agent/mirror_tunnel/trace_contract/mirror_tunnel_trace_contract.{json,md}`.
The contract records canonical frame order, frame schema, available and missing
evidence, reusable and excluded context, trust level, artifact references,
boundaries, and `recommended_next_phase = MIRROR.2`. It does not call models,
apply patches, run validation, run benchmarks, invoke MCP tools, launch workers,
execute Dream actions, apply Replay janitor actions, use Docker or subprocess,
contact network services, write to a database, change route behavior, change
auth policy, change UI behavior, score derailment, push, merge, or open PRs.

**MIRROR.2 - Mirror Tunnel Derailment Score Report is shipped 2026-06-29 (complete).**
Implemented as `core/mirror_tunnel_derailment_score.py` +
`scripts/create_mirror_tunnel_derailment_score.py`, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.1) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_derailment_score.py`. It reads a MIRROR.1 trace
contract and writes
`.agent/mirror_tunnel/derailment_score/mirror_tunnel_derailment_score.{json,md}`.
The score report uses deterministic heuristics only across intent drift, scope
drift, evidence loss, claim/action mismatch, validation gap, and confidence
inflation, then emits weighted verdicts and recommended next actions. It does
not call models, use embeddings or semantic APIs, apply patches, run validation,
run benchmarks, invoke MCP tools, launch workers, execute Dream actions, apply
Replay janitor actions, use Docker or subprocess, contact network services,
write to a database, change route behavior, change auth policy, block execution,
push, merge, or open PRs. Recommended next phase: MIRROR.3.

**MIRROR.3 - Claim-vs-Diff Mirror Check is shipped 2026-06-29 (complete).**
Implemented as `core/mirror_tunnel_claim_diff_check.py` +
`scripts/create_mirror_tunnel_claim_diff_check.py`, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.2) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_claim_diff_check.py`. It reads a MIRROR.1 trace
contract, an optional MIRROR.2 derailment score report, and optional explicit
evidence files (`--patch-json`, `--diff`, `--validation-json`,
`--benchmark-json`, `--final-answer-file`, `--worker-reply-file`), then writes
`.agent/mirror_tunnel/claim_diff_check/mirror_tunnel_claim_diff_check.{json,md}`.
The report detects changed-file, no-change, validation, benchmark, test, safety,
scope, completion, and uncertainty claims, compares them against patch/diff,
artifact, validation, benchmark, replay, and safety evidence, and emits matches,
mismatches, unsupported claims, honest uncertainty claims, and a recommended next
action. It does not call models, use embeddings or semantic APIs, apply patches,
run validation, run benchmarks, invoke MCP tools, launch workers, execute Dream
actions, apply Replay janitor actions, use Docker or subprocess, contact network
services, write to a database, change route behavior, change auth policy, block
execution, push, merge, or open PRs. Recommended next phase: MIRROR.4.

**UX.1 — Operator Cockpit & Idea Intake Plan is shipped 2026-06-24 (complete).**
Implemented report-only as `core/operator_cockpit_plan.py` +
`scripts/create_operator_cockpit_plan.py`, registered as a `complete`
UX-track phase (prerequisite HARDEN.1) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_operator_cockpit_plan.py`. It builds a deterministic UX
planning report inventorying 8 pain points, a 5-step operator workflow (Start/Run/Review/
Continue/Learn), 10 cockpit sections (Task Bar, Mode Decision, Run Timeline, etc.),
primary/advanced/debug action maps, an idea intake board (use_now/prototype_later/park/block),
metaphor placement for 4W1H/Navier-Stokes/Excavator, and a UX roadmap proposal (UX.1–UX.6).
Artifacts: `.agent/ux/operator_cockpit_plan/operator_cockpit_plan.{json,md}`. It adds no
UI implementation, backend behavior change, task execution, agent launch, model call,
patch apply, validation run, benchmark run, network call, database write, worker launch,
push, merge, or PR power.

**ROAD.4 — Post-EVAL/CMD Checkpoint Audit is shipped 2026-06-23 (complete).**
Implemented report-only as `core/post_eval_cmd_checkpoint_audit.py` +
`scripts/create_post_eval_cmd_checkpoint_audit.py`, registered as a `complete`
ROAD-track phase (prerequisite CMD.4) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_post_eval_cmd_checkpoint_audit.py`. It reads the
phase registry, EVAL.1–3 artifact roots, CMD.1–4 artifact roots, and project
documentation, then writes
`.agent/roadmap/post_eval_cmd_checkpoint/post_eval_cmd_checkpoint_audit.{json,md}`
verifying that all seven required phases are registered, complete, report-only,
artifact-backed, and documented. Audit statuses: `pass`, `pass_with_warnings`,
`blocked`. It adds no model call, patch apply, validation run, benchmark run,
network call, database write, worker launch, push, merge, or PR power.

Purpose:

Track full benchmark runs as artifacts so operators can understand benchmark health over time instead of treating each run as an isolated event.

The ledger should record:

- Run id.
- Timestamp.
- Model config.
- Pass/fail per case.
- Duration.
- Fallback count.
- Token/cost summary.
- Failed cases.
- Rerun evidence.
- Flake classification.

Boundary:

- Reads benchmark reports.
- Writes ledger/report.
- Does not run benchmarks itself.
- Does not call models.
- Does not patch code.
- Does not alter benchmark cases.

Expected first shape:

- A report-only phase.
- Deterministic parsing of existing benchmark report artifacts.
- Backward-compatible handling for older benchmark reports.
- Clear classification of confirmed failures, isolated rerun passes, and unresolved flakes.
- Tests only if they fit the existing documentation/reporting pattern for this repository and do not require runtime behavior changes.

## 7. Parking Lot

- Commander Mode execution beyond the CMD.1 report-only contract.
- Model Lab specialist models.
- Remote execution unlock.
- Cross-district architecture.
- Biology/Math/Physics inspiration districts.
- AI-agent-as-customer idea.

These ideas remain useful but are not selected by NEXT.1. They should not be smuggled into EVAL.1 or any first branch phase without explicit approval.

## 8. Decision Rule

Before implementing any branch:

- Create a machine-readable phase entry.
- Require explicit human approval.
- Prefer report-only first.
- Validate with tests.
- Update the ROAD picker only after the new map is accepted.

The branch selector should be treated as a map, not permission to execute. Each branch still requires a concrete phase proposal, a registry entry, and human acceptance before implementation begins.

## 9. Boundary Statement

This roadmap does not authorize live autonomy.

This roadmap does not authorize remote execution.

This roadmap does not authorize auto-merge.

This roadmap does not authorize model authority.

It only defines the next candidate map.

## HARDEN Track

HARDEN phases add defensive hardening to the CATTUS web app. They do not redesign the app, add new automation power, call models, contact network services, run validation, apply patches, push, merge, or open PRs.

### HARDEN.1 — Web Mutation Auth / CSRF Gate

**Status:** Complete  
**Prerequisite:** ROAD.4  
**Risk:** Medium (modifies web/app.py before_request behavior)

Adds a centralized `@app.before_request` security gate to the Flask web app. For safe HTTP methods (GET, HEAD, OPTIONS), all requests are allowed. For mutating methods (POST, PUT, PATCH, DELETE):

- If `WEB_AUTH_TOKEN` is set: all mutating requests require a matching token in `X-CATTUS-Web-Token` or `Authorization: Bearer <token>`.
- If `WEB_AUTH_TOKEN` is not set: mutating requests are allowed only from loopback addresses (127.0.0.1, ::1, localhost); all others receive 403.
- Cross-origin mutating requests are always rejected (Origin/Referer CSRF check).

**New env vars:**
- `WEB_AUTH_TOKEN` — token for web mutation auth; unset means loopback-only
- `WEB_SECRET_KEY` — Flask secret key; generates a dev-only placeholder if unset

**New files:**
- `web/auth_gate.py` — pure gate helpers, GateDecision dataclass
- `tests/test_web_mutation_auth_gate.py` — 21-test suite (15 cases)

**No new automation power.** Does not run models, apply patches, validate, benchmark, contact network services, push, merge, or open PRs.

### HARDEN.2 — Web Mutation Surface Audit

**Status:** Complete  
**Prerequisites:** UX.CLOSE, HARDEN.1  
**Risk:** Medium (security audit of route mutation surface; report-only)

Creates a report-only inventory of all Flask routes from the registered app
route map. Routes are classified by safe methods (GET, HEAD, OPTIONS), mutating
methods (POST, PUT, PATCH, DELETE), mixed method surfaces, high-risk route
keywords, and category hints including artifact-writing, validation-running,
benchmark-running, worker-launching, replay/janitor-related, and
external-integration-related.

**Artifacts:**
- `.agent/harden/web_mutation_surface_audit/web_mutation_surface_audit.json`
- `.agent/harden/web_mutation_surface_audit/web_mutation_surface_audit.md`

**No new automation power.** Does not call handlers, run models, apply patches,
validate, benchmark, launch workers, execute Dream actions, apply Replay janitor
actions, contact network services, write to a database, change routes, change
auth policy, change UI behavior, push, merge, or open PRs.

### HARDEN.3 — Safe Validation / MCP Approval Enforcement Audit

**Status:** Complete  
**Prerequisite:** HARDEN.2  
**Risk:** Medium (security audit of execution and approval surfaces; report-only)

Creates a report-only static source audit for validation execution, MCP/tool
artifact actions, janitor/apply/delete cleanup paths, approval-sensitive fields,
and route metadata. The report inventories audited files, routes, functions,
validation surfaces, MCP surfaces, janitor or cleanup surfaces, and approval
gate surfaces. It distinguishes blockers from manual-review warnings and records
gate evidence such as safe validation helpers, command safety checks,
temp-clone/sandbox boundaries, MCP tool allowlists, audit logging, confirmation
tokens, HARDEN.1 auth coverage, and human-approval policy fields.

**Artifacts:**
- `.agent/harden/safe_validation_mcp_approval_audit/safe_validation_mcp_approval_audit.json`
- `.agent/harden/safe_validation_mcp_approval_audit/safe_validation_mcp_approval_audit.md`

**No new automation power.** Does not import audited application modules, call
handlers, invoke MCP tools, run models, apply patches, validate, benchmark,
launch workers, execute Dream actions, apply Replay janitor actions, contact
network services, write to a database, change routes, change auth policy, change
UI behavior, push, merge, or open PRs.

### HARDEN.CLOSE - Hardening Branch Checkpoint

**Status:** Complete  
**Prerequisite:** HARDEN.3  
**Risk:** Medium (branch closure checkpoint; report-only)

Creates a report-only checkpoint that reviews HARDEN.1, HARDEN.2, and HARDEN.3
evidence together. It verifies that HARDEN.1 is registered complete and the
auth gate is detectable, HARDEN.2 has zero uncovered mutating routes and zero
blockers, HARDEN.3 has zero blockers, and HARDEN.2/HARDEN.3 warnings are
manual-review items rather than confirmed bypasses. It decides one of four
statuses: frozen, frozen_with_manual_review_warnings, needs_harden_4, or
blocked.

**Artifacts:**
- `.agent/harden/hardening_branch_checkpoint/hardening_branch_checkpoint.json`
- `.agent/harden/hardening_branch_checkpoint/hardening_branch_checkpoint.md`

**No new automation power.** Does not call models, apply patches, validate,
benchmark, invoke MCP tools, launch workers, execute Dream actions, apply Replay
janitor actions, use Docker or subprocess, contact network services, write to a
database, change route behavior, change auth policy, change UI behavior, push,
merge, or open PRs. MIRROR.1, MIRROR.2, and MIRROR.3 have since shipped; the
next recommended phase is MIRROR.4 - Mirror Tunnel Replay Readiness Pack.
