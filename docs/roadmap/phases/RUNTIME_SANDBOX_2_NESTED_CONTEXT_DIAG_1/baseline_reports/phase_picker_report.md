# Phase Picker / Night Candidate Report

> Phase Picker / Night Candidate Report is report-only: it reads the ROAD.1 phase registry and classifies phases into safe-candidate buckets. It does not choose and execute work, run phases, run validation or a benchmark check, call models, apply patches, write to the real repo, push, merge, open PRs, or contact a remote git host, chat app, or external automation. ROAD.2 only recommends; human approval is required before any phase is acted on.

_Report only: ROAD.2 classifies roadmap phase metadata from the ROAD.1 registry into candidate buckets. It recommends only; it runs nothing, changes nothing, and contacts nothing._

---

## Summary

- **Report id:** `nested-context-preservation`
- **Created at:** `2026-10-10T00:00:00+00:00`
- **Registry path:** `docs/roadmap/phase_registry.json`
- **Registry valid:** VALID
- **Phase count:** 225

| Bucket | Count |
|---|---|
| safe_to_prepare | 3 |
| sandbox_required | 1 |
| human_approval_required | 0 |
| blocked | 2 |
| deferred_or_parked | 0 |
| complete_or_history | 219 |

## Top recommendation

- **DOGFOOD.1B** — Real Operator Run Evaluation (risk low, LOCAL_0_OBSERVE) → `prepare_worker_assignment`

## Safe to prepare

| Phase | Title | Track | Status | Risk | Automation | Budget | Next step | Reasons |
|---|---|---|---|---|---|---|---|---|
| DOGFOOD.1B | Real Operator Run Evaluation | DOGFOOD | proposed | low | LOCAL_0_OBSERVE | local_only | prepare_worker_assignment | status is proposed; automation_level LOCAL_0_OBSERVE is local; budget_tier is local_only; risk_level is low; no network, model calls, merge, or real-repo writes; allowed_files and validation are declared |
| VERIFY.TEST.1 | Test Design and TDD Planning | VERIFY | proposed | low | LOCAL_0_OBSERVE | local_only | complete_prerequisites | status is proposed; automation_level LOCAL_0_OBSERVE is local; budget_tier is local_only; risk_level is low; no network, model calls, merge, or real-repo writes; allowed_files and validation are declared; prerequisites not yet complete: DOGFOOD.1B |
| MIRROR.13 | Live Trace Frame Capture Quality Plan | MIRROR | proposed | low | LOCAL_0_OBSERVE | local_only | prepare_worker_assignment | status is proposed; automation_level LOCAL_0_OBSERVE is local; budget_tier is local_only; risk_level is low; no network, model calls, merge, or real-repo writes; allowed_files and validation are declared |

## Sandbox required

| Phase | Title | Track | Status | Risk | Automation | Budget | Next step | Reasons |
|---|---|---|---|---|---|---|---|---|
| WORKER.DECL.2B | Pre-Execution Change Intent Channel | WORKER | active | medium | LOCAL_0_OBSERVE | strong_model_requires_approval | prepare_sandbox_trial_contract | requires_sandbox is true; allowed_files include patch/sandbox-related paths |

## Human approval required

_None._

## Blocked

| Phase | Title | Track | Status | Risk | Automation | Budget | Next step | Reasons |
|---|---|---|---|---|---|---|---|---|
| RUNTIME.JAVA.1 | Verified Java Toolchain Availability and Exact Sandboxed Execution Surface | CONTROL | active | medium | LOCAL_1_PREPARE | blocked | blocked_until_metadata_fixed | budget_tier is blocked |
| PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1 | Bounded Ephemeral Java Diagnostic Executor | CONTROL | active | blocked | LOCAL_1_PREPARE | local_only | blocked_until_metadata_fixed | risk_level is blocked |

## Deferred or parked

_None._

## Complete or history

| Phase | Title | Track | Status | Risk | Automation | Budget | Next step | Reasons |
|---|---|---|---|---|---|---|---|---|
| ROAD.1 | Machine-Readable Phase Registry | ROAD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| ROAD.2 | Phase Picker / Night Candidate Report | ROAD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| ROAD.3 | Post-MODEL Checkpoint Audit | ROAD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| ROAD.4 | Post-EVAL/CMD Checkpoint Audit | ROAD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| AUTO.2a | Telegram Evidence Summary Contract | AUTO | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.CLOSE | Model Role Planning Checkpoint | MODEL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.N1 | Model Role Registry / Tower Card Contract | MODEL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.N2 | Model Role Coverage Report | MODEL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.N3 | Model Role Gap Plan | MODEL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.N4 | Model Role Catalog Update Proposal | MODEL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.N5 | Model Role Catalog Proposal Review | MODEL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.N6 | Model Role Catalog Adoption Plan | MODEL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.N7 | Model Role Catalog Adoption Readiness Check | MODEL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.1 | Live Benchmark Run Ledger | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.2 | Benchmark Report Compare / Single-Case Flake Evidence | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.3 | Flake Classification Report | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.CLOSE | Evidence Quality Branch Checkpoint | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.N1 | Evidence Quality Planning | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.N2 | Evidence Quality Report Contract | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.N3 | Evidence Quality Report Builder | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.N4 | Evidence Quality Artifact Loader Plan | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.N5 | Evidence Quality Read-only UI Stub | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.N6 | Evidence Quality GET-only Artifact Loader | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVAL.N7 | Evidence Quality Loader Readiness Check | EVAL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HUMAN.CLOSE | Human Authority Branch Checkpoint | HUMAN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HUMAN.N1 | Human Review Boundary Map | HUMAN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HUMAN.N2 | Human Approval Token / Confirmation Contract | HUMAN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HUMAN.N3 | Human Approval Token Dry-Run Validator | HUMAN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HUMAN.N4 | Human Approval Token Sample Catalog | HUMAN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| ADOPT.MODEL.1 | Human-Approved Model Role Catalog Adoption | ADOPT | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| ADOPT.MODEL.2 | Post-Adoption Role Coverage Recheck | ADOPT | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| ADOPT.MODEL.CLOSE | Model Catalog Adoption Branch Checkpoint | ADOPT | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.CLOSE | Commander Planning Branch Checkpoint | CMD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.N1 | Boss Half-Life Fracture Plan | CMD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.N2 | Manual Boss Fracture Report | CMD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.N3 | Commander Fracture Tree Schema / Registry | CMD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.N4 | Commander Preflight Contract | CMD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.N5 | Commander Manual Assignment Plan | CMD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.N6 | Commander Assignment Review Pack | CMD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.CLOSE | Approval Enforcement Planning Branch Checkpoint | HARDEN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.N1 | Approval Enforcement Readiness Audit | HARDEN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.N2 | Approval Enforcement Attachment Plan | HARDEN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.N3 | Approval Enforcement Dry-Run Gate Simulator | HARDEN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.N4 | Approval Enforcement Operator Report | HARDEN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.PROGRESS.1 | Early Error Terminal Snapshot Coverage | HARDEN | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.TEST.1 | Test Suite Runtime Profile Audit | OPS | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.TEST.2 | Slow Test Timing Collector | OPS | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.TEST.3 | Suite Split Manifest Plan | OPS | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.TEST.CLOSE | Test Runtime Operations Branch Checkpoint | OPS | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.1 | Operator Cockpit & Idea Intake Plan | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.2 | Run Timeline / Progress Surface | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.3 | Continue-from-Frame Contract | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.4 | Mixed Mode Intent Router Preview | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.5 | Goal Brief 4W1H Simplifier | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.6 | Evidence Card Layout | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.7 | Cockpit Navigation & Action Hierarchy Cleanup | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.8 | Cockpit Usability Checkpoint | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.9 | Unified Workbench Input Plan | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.10 | Unified Workbench Input Visual Integration | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.11 | Unified Workbench Behavior Preservation Check | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.CLOSE | UX Branch Freeze Checkpoint | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.1 | Run Progress Instrumentation Plan | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.2 | Run Progress Snapshot Writer Plan | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.3 | Run Progress Snapshot Writer Shadow Mode | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.4 | Narrow Multi-Stage Shadow Instrumentation | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.5 | Current Run Snapshot Association | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.6 | Manual Run Progress Refresh | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.7 | Snapshot Freshness and Staleness Plan | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.8 | Freshness Classification Implementation | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.9 | Bounded Progress Polling Experiment Plan | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.10 | Optional Default-Off Bounded Progress Polling | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.LIVE.CLOSE | Live Run Progress Branch Checkpoint | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.RUN.1 | Run Progress / Operator Visibility | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.RUN.2 | Run Progress Snapshot Loader | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.RUN.3 | Run Progress UI Panel Stub | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| UX.RUN.CLOSE | Run Progress Visibility Branch Checkpoint | UX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| DOGFOOD.1A | Live Progress Operator Evaluation Framework | DOGFOOD | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.1 | Mirror Tunnel Trace Contract | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.2 | Mirror Tunnel Derailment Score Report | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.3 | Claim-vs-Diff Mirror Check | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.4 | Real Run Trace Ingestion Plan | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.5 | Manual Trace Assembler | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.6 | Manual Trace Score Pipeline | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.7 | Shadow Live Trace Writer | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.8 | Live Trace Scoring Preview | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.9 | Live Trace Operator Report Panel Plan | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.10 | Operator Panel Read-only UI Stub | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.11 | Operator Panel Artifact Loader Preview | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.CLOSE | Mirror Tunnel Branch Checkpoint | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.CLOSE3 | Mirror Tunnel Live UI Readiness Checkpoint | MIRROR | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| ACQUIRE.1 | Bounded Evidence Acquisition Request Contract | ACQUIRE | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| ACQUIRE.2 | Bounded Candidate Eligibility & Selector Bridge | ACQUIRE | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CHECK.1 | Post-Run Contract Reconciliation | CHECK | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CHECK.2 | Post-Run Goal-Fidelity Verification Contract | CHECK | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CLAIM.1 | Bounded Proposition Assessment Contract | CLAIM | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CTX.OOP.1A | Java Class Semantic Projection Core | CONTROL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CTX.OOP.1B | Bounded OOP Reasoning Context Attachment | CONTROL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CTX.OOP.1C | OOP Semantic Review and Intent-Gap Contract | CONTROL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CTX.SELECT.1 | Bounded Candidate Discovery & File Actionability Contract | CTX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| EVIDENCE.2 | Evidence Set Coverage, Conflict & Independence Contract | EVIDENCE | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| INDEX.1D.1 | Dual Graph Lifecycle Contract | INDEX | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| INPUT.1 | Lossless Task Contract & Semantic Waiter Boundary | INPUT | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| OOP.INTENT.DESIGN.1 | Explicit Future-Design Commitment Projection | CONTROL | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| SYNTHESIS.1 | Task-Shaped Claim Composition Contract | SYNTHESIS | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| WAITER.1 | Deterministic Capability-Based Execution Router | WAITER | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| WAITER.2 | Deterministic Evidence Requirement Contract | WAITER | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| WORKER.DECL.1 | Native Worker Declaration Source Qualification & Wiring | WORKER | complete | low | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.1 | C.A.T.T.U.S Artifact Dataset Builder | MODEL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| SEC.UI.1 | Untrusted Evidence Active-Content Boundary | HARDEN | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| DEFECT.PROBE.LIVE.4 | Depth-Variant Behavioral Discrimination Matrix | OPS | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| DEFECT.PROBE.LIVE.5 | Distribution-Skew Indentation Unit Discrimination | OPS | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INDENT.RUNTIME.1 | Language Context Transport & Repair Boundary | OPS | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INDENT.SEMANTICS.1 | Language-Aware Indentation Observation Contract | OPS | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| REPAIR.INTENT.UI.1 | Waiting Session Presentation Contract | UX | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| ANSWER.COHERENCE.LIVE.1 | Candidate-Bound Final Response Provenance | CHECK | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| ANSWER.GROUND.LIVE.4 | Structured Payload Non-Interference | CHECK | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INPUT.3 | Progressive Intake Completion & Clarification Policy | INPUT | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.AUTHOR.LIVE.2 | Self-Contained Authoring Contract Parity | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.AUTHOR.LIVE.3 | Concrete Counterexample Materialization and Truthful Authoring Scope | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1 | Partial Diagnostic Behavioral Execution Admission | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1 | Bounded Behavioral Evidence Execution Planning | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.CANDIDATE.BEHAVIOR.REFLECT.1 | Exact Read-Only Reflection Diagnostic Capability | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.CANDIDATE.BEHAVIOR.SPEC.1 | Typed Behavioral Validation Specification | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.MINIMAL.LIVE.1 | Exact No-Op Candidate Rejection | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.MINIMAL.LIVE.2 | Bounded Local Implementation Novelty | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.MINIMAL.LIVE.3 | Authoritative Bindings and Proven Immutable Result-Field Reads | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PREFLIGHT.RUNTIME.1 | Bounded Runtime Diagnostic Authorization Contract | CONTROL | complete | low | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| AUTO.2b | GitHub Remote PR Safety Contract | AUTO | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.1 | Commander Run Contract | CMD | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.2 | Task Decomposition Preview | CMD | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.3 | Budget Governor Preview | CMD | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CMD.4 | Commander Readiness / Stop Condition Report | CMD | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.1 | Web Mutation Auth / CSRF Gate | HARDEN | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.2 | Web Mutation Surface Audit | HARDEN | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| HARDEN.3 | Safe Validation / MCP Approval Enforcement Audit | HARDEN | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| MIRROR.12 | Mirror Tunnel Live Trace Demo Run / Readiness Check | MIRROR | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CHECK.LIVE.1 | Shadow Post-Run Reconciliation Wiring | CHECK | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| CHECK.LIVE.1B | Independent Typed Worker Declaration Wiring | CHECK | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| INDEX.1E.0 | Delta Integration Preflight & Known-Failure Baseline | INDEX | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| WORKER.DECL.2A | Strict Structured Patch Response Envelope | WORKER | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| WORKER.DECL.2A.1 | Strict Envelope Emission Adoption Experiment | WORKER | complete | medium | LOCAL_0_OBSERVE | local_only | no_action_complete | status is complete (shipped history) |
| WORKER.DECL.2A.2 | Live Strict Envelope Adoption Dogfood | WORKER | complete | medium | LOCAL_0_OBSERVE | strong_model_requires_approval | no_action_complete | status is complete (shipped history) |
| AUTO.2c | n8n Orchestration Dry Run | AUTO | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.2 | Driver Classifier Baseline | MODEL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| MODEL.3 | Lesson Graph Activation Dataset | MODEL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| AUTH.DREAM.1 | Reviewed Candidate Exact Binding for Dream Apply | HARDEN | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| AUTH.WEB.1 | Same-Origin Request Integrity & Usable Local UI Authentication | HARDEN | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| AUTH.WEB.READ.1 | Trusted Host & Sensitive Read Boundary | HARDEN | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| DATA.ROLLBACK.1 | Verified Rollback Truthfulness & Recoverable Failure State | HARDEN | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| DATA.UNDO.1 | Repository-Scoped Backup Identity & Exact Undo Binding | HARDEN | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| EXEC.PLAN.1 | Validate-Before-Mutate & Transaction Containment | HARDEN | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| CANDIDATE.VERIFY.LIVE.1 | Read-Only Candidate Verification Before Human Review | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| DEFECT.FACT.LIVE.1 | Typed Behavioral Expectation Handoff | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| DEFECT.PROBE.LIVE.1 | Bounded Defect Reproduction Evidence | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| DEFECT.PROBE.LIVE.2 | Immutable Pre/Post Candidate Reproduction Closure | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| DEFECT.PROBE.LIVE.3 | Paired Defect-Fix & Behavior-Preservation Oracle | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| EXEC.AUTH.LIVE.1 | Execution Authorization & Outcome Telemetry Reconciliation | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| EXEC.POLICY.LIVE.1 | Evidence-Bounded Large-Repository Execution Eligibility | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.PATCH.1 | Byte-Preserving Multi-File Apply & Rollback | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.PATCH.2 | Explicit-Change Candidate Sandbox Validation | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.VALIDATE.1 | Real Repository Validation Recovery | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.VALIDATE.2 | Timeout Truthfulness, Budget Exhaustion & Python Cache Freshness | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| OPS.VALIDATE.3 | Bounded Targeted Repository Validation | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| VALIDATE.ORACLE.LIVE.1 | Existing Check Role & Candidate-Oracle Conflict Classification | OPS | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| OOP.INTENT.UI.1 | Durable OOP Clarification Session Adapter | UX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| UX.CONTEXT.1 | Run / Repository Context Binding | UX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| UX.STATE.1 | Repository / Run / Candidate State Ownership & Truthful Actions | UX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| ACQUIRE.3 | Bounded Content Acquisition & Source Receipt | ACQUIRE | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| ANALYSIS.EVIDENCE.LIVE.1 | Role-Balanced Source Evidence Acquisition | WAITER | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| ANALYSIS.MULTIROOT.LIVE.1 | Explicit Read-Only Multi-Repository Evidence Contract | WAITER | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| ANSWER.GROUND.LIVE.1 | Repository Entity Claim Grounding & Evidence-Bounded Fallback | CHECK | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| ANSWER.GROUND.LIVE.2 | Bare Symbol & Qualified Member Claim Grounding | CHECK | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| ANSWER.GROUND.LIVE.3 | Non-Destructive Evidence-Gap Remediation & Exact Path Boundaries | CHECK | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| CONTROL.BOOTSTRAP.1 | Explicit-Target Direct Context Bootstrap | CONTROL | complete | medium | LOCAL_1_PREPARE | strong_model_requires_approval | no_action_complete | status is complete (shipped history) |
| CONTROL.FRESH.1 | Explicit No-Prior-Run Context Contract | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| CONTROL.LOCALIZE.LIVE.2 | Entry-Anchored Hypothesis Relevance | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| CONTROL.SAFETY.LIVE.1 | Localization Rank / Patch Authority Separation | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| CTX.APPLY.0 | Direct Context Patch Safety Attachment | CTX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| CTX.PATCH.1 | Direct Context Patch Candidate Gate | CTX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| CTX.READ.1 | Bounded Direct File Read Runtime | CTX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| CTX.SEARCH.1 | Bounded Lexical Search Runtime | CTX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| EVIDENCE.1 | Acquired Source Verification & Evidence Promotion Contract | EVIDENCE | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INDEX.1D.2A | Canonical Repository Identity Primitive | INDEX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INDEX.1D.2B | Identity Confirmation & Architecture Epoch State | INDEX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INDEX.1D.2C | Honest Persistence Completion Contract | INDEX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INDEX.1D.3 | Traversal Budget Closure | INDEX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INPUT.2 | Semantic Waiter Model Adapter & Semantic Evaluation | INPUT | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INPUT.PRESERVE.LIVE.1 | Lossless Long-Obligation Transport | INPUT | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| OOP.INTENT.CONTINUE.1 | Human Clarification Answer to Typed Design Continuation | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| OOP.INTENT.DETECT.2 | Missing Future-Design Contract Admission | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.AUTHOR.LIVE.1 | Verification-Guided Single Revision | CONTROL | complete | medium | LOCAL_1_PREPARE | strong_model_requires_approval | no_action_complete | status is complete (shipped history) |
| PATCH.AUTHOR.SCOPE.1 | Measured Repair-Set Authoring Scope | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.AUTHOR.SPAN.1 | Repair-Envelope Target / Replacement Alignment | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.AUTHOR.STRUCTURAL.1 | Admitted Structural Scope to Read-Only Multi-Target Candidate Authoring | CONTROL | complete | medium | LOCAL_1_PREPARE | strong_model_requires_approval | no_action_complete | status is complete (shipped history) |
| PATCH.BASIS.LIVE.1 | Typed Patch Basis & Failure-Relevance Binding | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.BASIS.SCOPE.1 | Measured Same-File Multi-Definition Repair Scope | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.BASIS.TARGET.1 | Structural Short-Identifier Target Source Grounding | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.CANDIDATE.MATERIALIZE.1 | Structural Candidate to Immutable Virtual File-Set Materialization | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.CANDIDATE.VALIDATE.1A | Virtual Java Compile Validation | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.SCOPE.ADMIT.1 | Deterministic Structural Plan to Concrete Authoring Scope Admission | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.SCOPE.APPROVE.1 | Human Structural Scope Ceiling Approval | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.SCOPE.EXPAND.1 | Evidence-Bound Structural Scope Expansion Proposal | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.SCOPE.PLAN.1 | Read-Only Implementation Plan Within Approved Structural Ceiling | CONTROL | complete | medium | LOCAL_1_PREPARE | strong_model_requires_approval | no_action_complete | status is complete (shipped history) |
| PATCH.SCOPE.RECHECK.1 | Scope-Discovered Semantic Recheck | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PATCH.SCOPE.REFRESH.1 | Semantically Revised Structural Scope Re-Proposal | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| PREFLIGHT.REQUEST.1 | Typed Diagnostic Evidence Request & Java Compile Adapter | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| REPAIR.INTENT.1 | Typed Semantic Ambiguity and User Clarification Handoff | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| REPAIR.INTENT.ADMIT.1 | Author Escalation Admission and Candidate Quarantine | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| REPAIR.INTENT.DETECT.1 | Harness-Owned State Ownership Ambiguity Admission | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| REPAIR.INTENT.GROUND.1 | System-Owned Semantic Gap Source Anchors | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| RETRIEVE.LIVE.1 | Candidate Population Hygiene & Symbol Eligibility | INDEX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| RETRIEVE.LIVE.2 | Query-to-Symbol Entry Recall & Identifier Decomposition | INDEX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| RETRIEVE.LIVE.3 | Production Query-Recall Path Unification | INDEX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| RETRIEVE.LIVE.4 | Repository-Specificity Weighted Entry Ordering | INDEX | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| RUNTIME.SANDBOX.1 | Verified OS-Enforced Candidate Runtime Isolation Adapter | CONTROL | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| WAITER.LIVE.1 | Live Task-Shape Routing & Change-Need Separation | WAITER | complete | medium | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| EXEC.APPROVAL.LIVE.1 | Human Apply Binding, Freshness Revalidation & Authorization Handoff | OPS | complete | high | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INDEX.1E.1 | Manifest Load and Shadow Delta Plan Dispatch | INDEX | complete | high | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |
| INDEX.1E.2 | Verified No-Change Fast Path | INDEX | complete | high | LOCAL_1_PREPARE | local_only | no_action_complete | status is complete (shipped history) |

## Boundaries

- ROAD.2 does not execute phases.
- ROAD.2 does not run validation or benchmarks.
- ROAD.2 does not call models.
- ROAD.2 does not apply patches.
- ROAD.2 does not push, merge, open PRs, or contact GitHub, Telegram, or N8N / external automation.
- ROAD.2 only classifies phase metadata from the registry.

