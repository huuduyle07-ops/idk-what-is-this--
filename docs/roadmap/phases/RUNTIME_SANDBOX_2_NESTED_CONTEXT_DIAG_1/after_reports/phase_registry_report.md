# Machine-Readable Phase Registry Report

> Machine-Readable Phase Registry is report-only: it defines, validates, and summarizes roadmap phase metadata. It does not choose work, execute phases, run validation or a benchmark check, call models, apply patches, write to the real repo, push, merge, open PRs, or contact a remote git host, chat app, or external automation. Validation commands are stored as text only; ROAD.1 never runs them. Human approval is required before any phase is acted on.

_Report only: ROAD.1 defines, validates, and summarizes roadmap phase metadata. It chooses no work, runs nothing, and changes nothing in the real repo. Validation commands are stored as text only; ROAD.1 never runs them._

---

## Summary

- **Report id:** `nested-context-preservation`
- **Created at:** `2026-10-10T00:00:00+00:00`
- **Schema version:** `1.0`
- **Registry path:** `docs/roadmap/phase_registry.json`
- **Phase count:** 225
- **Valid:** VALID

## Counts by track

| Key | Count |
|---|---|
| ACQUIRE | 3 |
| ADOPT | 3 |
| AUTO | 3 |
| CHECK | 9 |
| CLAIM | 1 |
| CMD | 11 |
| CONTROL | 43 |
| CTX | 5 |
| DOGFOOD | 2 |
| EVAL | 11 |
| EVIDENCE | 2 |
| HARDEN | 16 |
| HUMAN | 5 |
| INDEX | 12 |
| INPUT | 4 |
| MIRROR | 15 |
| MODEL | 11 |
| OPS | 22 |
| ROAD | 4 |
| SYNTHESIS | 1 |
| UX | 31 |
| VERIFY | 1 |
| WAITER | 5 |
| WORKER | 5 |

## Counts by status

| Key | Count |
|---|---|
| active | 3 |
| complete | 219 |
| proposed | 3 |

## Counts by automation level

| Key | Count |
|---|---|
| LOCAL_0_OBSERVE | 126 |
| LOCAL_1_PREPARE | 99 |

## Validation result

- **Result:** VALID
- **Errors:** 0
- **Warnings:** 0

## Errors

_None._

## Warnings

_None._

## Phase Table

| Phase | Title | Track | Status | Automation level | Budget | Risk | Human approval |
|---|---|---|---|---|---|---|---|
| ACQUIRE.1 | Bounded Evidence Acquisition Request Contract | ACQUIRE | complete | LOCAL_0_OBSERVE | local_only | low | true |
| ACQUIRE.2 | Bounded Candidate Eligibility & Selector Bridge | ACQUIRE | complete | LOCAL_0_OBSERVE | local_only | low | true |
| ACQUIRE.3 | Bounded Content Acquisition & Source Receipt | ACQUIRE | complete | LOCAL_1_PREPARE | local_only | medium | true |
| ADOPT.MODEL.1 | Human-Approved Model Role Catalog Adoption | ADOPT | complete | LOCAL_0_OBSERVE | local_only | low | true |
| ADOPT.MODEL.2 | Post-Adoption Role Coverage Recheck | ADOPT | complete | LOCAL_0_OBSERVE | local_only | low | true |
| ADOPT.MODEL.CLOSE | Model Catalog Adoption Branch Checkpoint | ADOPT | complete | LOCAL_0_OBSERVE | local_only | low | true |
| AUTO.2a | Telegram Evidence Summary Contract | AUTO | complete | LOCAL_0_OBSERVE | local_only | low | true |
| AUTO.2b | GitHub Remote PR Safety Contract | AUTO | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| AUTO.2c | n8n Orchestration Dry Run | AUTO | complete | LOCAL_1_PREPARE | local_only | medium | true |
| ANSWER.COHERENCE.LIVE.1 | Candidate-Bound Final Response Provenance | CHECK | complete | LOCAL_1_PREPARE | local_only | low | true |
| ANSWER.GROUND.LIVE.1 | Repository Entity Claim Grounding & Evidence-Bounded Fallback | CHECK | complete | LOCAL_1_PREPARE | local_only | medium | true |
| ANSWER.GROUND.LIVE.2 | Bare Symbol & Qualified Member Claim Grounding | CHECK | complete | LOCAL_1_PREPARE | local_only | medium | true |
| ANSWER.GROUND.LIVE.3 | Non-Destructive Evidence-Gap Remediation & Exact Path Boundaries | CHECK | complete | LOCAL_1_PREPARE | local_only | medium | true |
| ANSWER.GROUND.LIVE.4 | Structured Payload Non-Interference | CHECK | complete | LOCAL_1_PREPARE | local_only | low | true |
| CHECK.1 | Post-Run Contract Reconciliation | CHECK | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CHECK.2 | Post-Run Goal-Fidelity Verification Contract | CHECK | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CHECK.LIVE.1 | Shadow Post-Run Reconciliation Wiring | CHECK | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| CHECK.LIVE.1B | Independent Typed Worker Declaration Wiring | CHECK | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| CLAIM.1 | Bounded Proposition Assessment Contract | CLAIM | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CMD.1 | Commander Run Contract | CMD | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| CMD.2 | Task Decomposition Preview | CMD | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| CMD.3 | Budget Governor Preview | CMD | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| CMD.4 | Commander Readiness / Stop Condition Report | CMD | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| CMD.CLOSE | Commander Planning Branch Checkpoint | CMD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CMD.N1 | Boss Half-Life Fracture Plan | CMD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CMD.N2 | Manual Boss Fracture Report | CMD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CMD.N3 | Commander Fracture Tree Schema / Registry | CMD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CMD.N4 | Commander Preflight Contract | CMD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CMD.N5 | Commander Manual Assignment Plan | CMD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CMD.N6 | Commander Assignment Review Pack | CMD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CONTROL.BOOTSTRAP.1 | Explicit-Target Direct Context Bootstrap | CONTROL | complete | LOCAL_1_PREPARE | strong_model_requires_approval | medium | true |
| CONTROL.FRESH.1 | Explicit No-Prior-Run Context Contract | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| CONTROL.LOCALIZE.LIVE.2 | Entry-Anchored Hypothesis Relevance | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| CONTROL.SAFETY.LIVE.1 | Localization Rank / Patch Authority Separation | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| CTX.OOP.1A | Java Class Semantic Projection Core | CONTROL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CTX.OOP.1B | Bounded OOP Reasoning Context Attachment | CONTROL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CTX.OOP.1C | OOP Semantic Review and Intent-Gap Contract | CONTROL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| OOP.INTENT.CONTINUE.1 | Human Clarification Answer to Typed Design Continuation | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| OOP.INTENT.DESIGN.1 | Explicit Future-Design Commitment Projection | CONTROL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| OOP.INTENT.DETECT.2 | Missing Future-Design Contract Admission | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.AUTHOR.LIVE.1 | Verification-Guided Single Revision | CONTROL | complete | LOCAL_1_PREPARE | strong_model_requires_approval | medium | true |
| PATCH.AUTHOR.LIVE.2 | Self-Contained Authoring Contract Parity | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.AUTHOR.LIVE.3 | Concrete Counterexample Materialization and Truthful Authoring Scope | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.AUTHOR.SCOPE.1 | Measured Repair-Set Authoring Scope | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.AUTHOR.SPAN.1 | Repair-Envelope Target / Replacement Alignment | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.AUTHOR.STRUCTURAL.1 | Admitted Structural Scope to Read-Only Multi-Target Candidate Authoring | CONTROL | complete | LOCAL_1_PREPARE | strong_model_requires_approval | medium | true |
| PATCH.BASIS.LIVE.1 | Typed Patch Basis & Failure-Relevance Binding | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.BASIS.SCOPE.1 | Measured Same-File Multi-Definition Repair Scope | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.BASIS.TARGET.1 | Structural Short-Identifier Target Source Grounding | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1 | Partial Diagnostic Behavioral Execution Admission | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1 | Bounded Behavioral Evidence Execution Planning | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1 | Bounded Ephemeral Java Diagnostic Executor | CONTROL | active | LOCAL_1_PREPARE | local_only | blocked | true |
| PATCH.CANDIDATE.BEHAVIOR.REFLECT.1 | Exact Read-Only Reflection Diagnostic Capability | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.CANDIDATE.BEHAVIOR.SPEC.1 | Typed Behavioral Validation Specification | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.CANDIDATE.MATERIALIZE.1 | Structural Candidate to Immutable Virtual File-Set Materialization | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.CANDIDATE.VALIDATE.1A | Virtual Java Compile Validation | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.MINIMAL.LIVE.1 | Exact No-Op Candidate Rejection | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.MINIMAL.LIVE.2 | Bounded Local Implementation Novelty | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.MINIMAL.LIVE.3 | Authoritative Bindings and Proven Immutable Result-Field Reads | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| PATCH.SCOPE.ADMIT.1 | Deterministic Structural Plan to Concrete Authoring Scope Admission | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.SCOPE.APPROVE.1 | Human Structural Scope Ceiling Approval | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.SCOPE.EXPAND.1 | Evidence-Bound Structural Scope Expansion Proposal | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.SCOPE.PLAN.1 | Read-Only Implementation Plan Within Approved Structural Ceiling | CONTROL | complete | LOCAL_1_PREPARE | strong_model_requires_approval | medium | true |
| PATCH.SCOPE.RECHECK.1 | Scope-Discovered Semantic Recheck | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PATCH.SCOPE.REFRESH.1 | Semantically Revised Structural Scope Re-Proposal | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PREFLIGHT.REQUEST.1 | Typed Diagnostic Evidence Request & Java Compile Adapter | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| PREFLIGHT.RUNTIME.1 | Bounded Runtime Diagnostic Authorization Contract | CONTROL | complete | LOCAL_1_PREPARE | local_only | low | true |
| REPAIR.INTENT.1 | Typed Semantic Ambiguity and User Clarification Handoff | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| REPAIR.INTENT.ADMIT.1 | Author Escalation Admission and Candidate Quarantine | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| REPAIR.INTENT.DETECT.1 | Harness-Owned State Ownership Ambiguity Admission | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| REPAIR.INTENT.GROUND.1 | System-Owned Semantic Gap Source Anchors | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| RUNTIME.JAVA.1 | Verified Java Toolchain Availability and Exact Sandboxed Execution Surface | CONTROL | active | LOCAL_1_PREPARE | blocked | medium | true |
| RUNTIME.SANDBOX.1 | Verified OS-Enforced Candidate Runtime Isolation Adapter | CONTROL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| CTX.APPLY.0 | Direct Context Patch Safety Attachment | CTX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| CTX.PATCH.1 | Direct Context Patch Candidate Gate | CTX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| CTX.READ.1 | Bounded Direct File Read Runtime | CTX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| CTX.SEARCH.1 | Bounded Lexical Search Runtime | CTX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| CTX.SELECT.1 | Bounded Candidate Discovery & File Actionability Contract | CTX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| DOGFOOD.1A | Live Progress Operator Evaluation Framework | DOGFOOD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| DOGFOOD.1B | Real Operator Run Evaluation | DOGFOOD | proposed | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.1 | Live Benchmark Run Ledger | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.2 | Benchmark Report Compare / Single-Case Flake Evidence | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.3 | Flake Classification Report | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.CLOSE | Evidence Quality Branch Checkpoint | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.N1 | Evidence Quality Planning | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.N2 | Evidence Quality Report Contract | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.N3 | Evidence Quality Report Builder | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.N4 | Evidence Quality Artifact Loader Plan | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.N5 | Evidence Quality Read-only UI Stub | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.N6 | Evidence Quality GET-only Artifact Loader | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVAL.N7 | Evidence Quality Loader Readiness Check | EVAL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| EVIDENCE.1 | Acquired Source Verification & Evidence Promotion Contract | EVIDENCE | complete | LOCAL_1_PREPARE | local_only | medium | true |
| EVIDENCE.2 | Evidence Set Coverage, Conflict & Independence Contract | EVIDENCE | complete | LOCAL_0_OBSERVE | local_only | low | true |
| AUTH.DREAM.1 | Reviewed Candidate Exact Binding for Dream Apply | HARDEN | complete | LOCAL_1_PREPARE | local_only | medium | true |
| AUTH.WEB.1 | Same-Origin Request Integrity & Usable Local UI Authentication | HARDEN | complete | LOCAL_1_PREPARE | local_only | medium | true |
| AUTH.WEB.READ.1 | Trusted Host & Sensitive Read Boundary | HARDEN | complete | LOCAL_1_PREPARE | local_only | medium | true |
| DATA.ROLLBACK.1 | Verified Rollback Truthfulness & Recoverable Failure State | HARDEN | complete | LOCAL_1_PREPARE | local_only | medium | true |
| DATA.UNDO.1 | Repository-Scoped Backup Identity & Exact Undo Binding | HARDEN | complete | LOCAL_1_PREPARE | local_only | medium | true |
| EXEC.PLAN.1 | Validate-Before-Mutate & Transaction Containment | HARDEN | complete | LOCAL_1_PREPARE | local_only | medium | true |
| HARDEN.1 | Web Mutation Auth / CSRF Gate | HARDEN | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| HARDEN.2 | Web Mutation Surface Audit | HARDEN | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| HARDEN.3 | Safe Validation / MCP Approval Enforcement Audit | HARDEN | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| HARDEN.CLOSE | Approval Enforcement Planning Branch Checkpoint | HARDEN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HARDEN.N1 | Approval Enforcement Readiness Audit | HARDEN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HARDEN.N2 | Approval Enforcement Attachment Plan | HARDEN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HARDEN.N3 | Approval Enforcement Dry-Run Gate Simulator | HARDEN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HARDEN.N4 | Approval Enforcement Operator Report | HARDEN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HARDEN.PROGRESS.1 | Early Error Terminal Snapshot Coverage | HARDEN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| SEC.UI.1 | Untrusted Evidence Active-Content Boundary | HARDEN | complete | LOCAL_1_PREPARE | local_only | low | true |
| HUMAN.CLOSE | Human Authority Branch Checkpoint | HUMAN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HUMAN.N1 | Human Review Boundary Map | HUMAN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HUMAN.N2 | Human Approval Token / Confirmation Contract | HUMAN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HUMAN.N3 | Human Approval Token Dry-Run Validator | HUMAN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| HUMAN.N4 | Human Approval Token Sample Catalog | HUMAN | complete | LOCAL_0_OBSERVE | local_only | low | true |
| INDEX.1D.1 | Dual Graph Lifecycle Contract | INDEX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| INDEX.1D.2A | Canonical Repository Identity Primitive | INDEX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| INDEX.1D.2B | Identity Confirmation & Architecture Epoch State | INDEX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| INDEX.1D.2C | Honest Persistence Completion Contract | INDEX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| INDEX.1D.3 | Traversal Budget Closure | INDEX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| INDEX.1E.0 | Delta Integration Preflight & Known-Failure Baseline | INDEX | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| INDEX.1E.1 | Manifest Load and Shadow Delta Plan Dispatch | INDEX | complete | LOCAL_1_PREPARE | local_only | high | true |
| INDEX.1E.2 | Verified No-Change Fast Path | INDEX | complete | LOCAL_1_PREPARE | local_only | high | true |
| RETRIEVE.LIVE.1 | Candidate Population Hygiene & Symbol Eligibility | INDEX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| RETRIEVE.LIVE.2 | Query-to-Symbol Entry Recall & Identifier Decomposition | INDEX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| RETRIEVE.LIVE.3 | Production Query-Recall Path Unification | INDEX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| RETRIEVE.LIVE.4 | Repository-Specificity Weighted Entry Ordering | INDEX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| INPUT.1 | Lossless Task Contract & Semantic Waiter Boundary | INPUT | complete | LOCAL_0_OBSERVE | local_only | low | true |
| INPUT.2 | Semantic Waiter Model Adapter & Semantic Evaluation | INPUT | complete | LOCAL_1_PREPARE | local_only | medium | true |
| INPUT.3 | Progressive Intake Completion & Clarification Policy | INPUT | complete | LOCAL_1_PREPARE | local_only | low | true |
| INPUT.PRESERVE.LIVE.1 | Lossless Long-Obligation Transport | INPUT | complete | LOCAL_1_PREPARE | local_only | medium | true |
| MIRROR.1 | Mirror Tunnel Trace Contract | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.2 | Mirror Tunnel Derailment Score Report | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.3 | Claim-vs-Diff Mirror Check | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.4 | Real Run Trace Ingestion Plan | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.5 | Manual Trace Assembler | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.6 | Manual Trace Score Pipeline | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.7 | Shadow Live Trace Writer | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.8 | Live Trace Scoring Preview | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.9 | Live Trace Operator Report Panel Plan | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.10 | Operator Panel Read-only UI Stub | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.11 | Operator Panel Artifact Loader Preview | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.12 | Mirror Tunnel Live Trace Demo Run / Readiness Check | MIRROR | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| MIRROR.13 | Live Trace Frame Capture Quality Plan | MIRROR | proposed | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.CLOSE | Mirror Tunnel Branch Checkpoint | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MIRROR.CLOSE3 | Mirror Tunnel Live UI Readiness Checkpoint | MIRROR | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MODEL.1 | C.A.T.T.U.S Artifact Dataset Builder | MODEL | complete | LOCAL_1_PREPARE | local_only | low | true |
| MODEL.2 | Driver Classifier Baseline | MODEL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| MODEL.3 | Lesson Graph Activation Dataset | MODEL | complete | LOCAL_1_PREPARE | local_only | medium | true |
| MODEL.CLOSE | Model Role Planning Checkpoint | MODEL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MODEL.N1 | Model Role Registry / Tower Card Contract | MODEL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MODEL.N2 | Model Role Coverage Report | MODEL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MODEL.N3 | Model Role Gap Plan | MODEL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MODEL.N4 | Model Role Catalog Update Proposal | MODEL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MODEL.N5 | Model Role Catalog Proposal Review | MODEL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MODEL.N6 | Model Role Catalog Adoption Plan | MODEL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| MODEL.N7 | Model Role Catalog Adoption Readiness Check | MODEL | complete | LOCAL_0_OBSERVE | local_only | low | true |
| CANDIDATE.VERIFY.LIVE.1 | Read-Only Candidate Verification Before Human Review | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| DEFECT.FACT.LIVE.1 | Typed Behavioral Expectation Handoff | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| DEFECT.PROBE.LIVE.1 | Bounded Defect Reproduction Evidence | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| DEFECT.PROBE.LIVE.2 | Immutable Pre/Post Candidate Reproduction Closure | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| DEFECT.PROBE.LIVE.3 | Paired Defect-Fix & Behavior-Preservation Oracle | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| DEFECT.PROBE.LIVE.4 | Depth-Variant Behavioral Discrimination Matrix | OPS | complete | LOCAL_1_PREPARE | local_only | low | true |
| DEFECT.PROBE.LIVE.5 | Distribution-Skew Indentation Unit Discrimination | OPS | complete | LOCAL_1_PREPARE | local_only | low | true |
| EXEC.APPROVAL.LIVE.1 | Human Apply Binding, Freshness Revalidation & Authorization Handoff | OPS | complete | LOCAL_1_PREPARE | local_only | high | true |
| EXEC.AUTH.LIVE.1 | Execution Authorization & Outcome Telemetry Reconciliation | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| EXEC.POLICY.LIVE.1 | Evidence-Bounded Large-Repository Execution Eligibility | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| INDENT.RUNTIME.1 | Language Context Transport & Repair Boundary | OPS | complete | LOCAL_1_PREPARE | local_only | low | true |
| INDENT.SEMANTICS.1 | Language-Aware Indentation Observation Contract | OPS | complete | LOCAL_1_PREPARE | local_only | low | true |
| OPS.PATCH.1 | Byte-Preserving Multi-File Apply & Rollback | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| OPS.PATCH.2 | Explicit-Change Candidate Sandbox Validation | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| OPS.TEST.1 | Test Suite Runtime Profile Audit | OPS | complete | LOCAL_0_OBSERVE | local_only | low | true |
| OPS.TEST.2 | Slow Test Timing Collector | OPS | complete | LOCAL_0_OBSERVE | local_only | low | true |
| OPS.TEST.3 | Suite Split Manifest Plan | OPS | complete | LOCAL_0_OBSERVE | local_only | low | true |
| OPS.TEST.CLOSE | Test Runtime Operations Branch Checkpoint | OPS | complete | LOCAL_0_OBSERVE | local_only | low | true |
| OPS.VALIDATE.1 | Real Repository Validation Recovery | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| OPS.VALIDATE.2 | Timeout Truthfulness, Budget Exhaustion & Python Cache Freshness | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| OPS.VALIDATE.3 | Bounded Targeted Repository Validation | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| VALIDATE.ORACLE.LIVE.1 | Existing Check Role & Candidate-Oracle Conflict Classification | OPS | complete | LOCAL_1_PREPARE | local_only | medium | true |
| ROAD.1 | Machine-Readable Phase Registry | ROAD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| ROAD.2 | Phase Picker / Night Candidate Report | ROAD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| ROAD.3 | Post-MODEL Checkpoint Audit | ROAD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| ROAD.4 | Post-EVAL/CMD Checkpoint Audit | ROAD | complete | LOCAL_0_OBSERVE | local_only | low | true |
| SYNTHESIS.1 | Task-Shaped Claim Composition Contract | SYNTHESIS | complete | LOCAL_0_OBSERVE | local_only | low | true |
| OOP.INTENT.UI.1 | Durable OOP Clarification Session Adapter | UX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| REPAIR.INTENT.UI.1 | Waiting Session Presentation Contract | UX | complete | LOCAL_1_PREPARE | local_only | low | true |
| UX.1 | Operator Cockpit & Idea Intake Plan | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.2 | Run Timeline / Progress Surface | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.3 | Continue-from-Frame Contract | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.4 | Mixed Mode Intent Router Preview | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.5 | Goal Brief 4W1H Simplifier | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.6 | Evidence Card Layout | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.7 | Cockpit Navigation & Action Hierarchy Cleanup | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.8 | Cockpit Usability Checkpoint | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.9 | Unified Workbench Input Plan | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.10 | Unified Workbench Input Visual Integration | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.11 | Unified Workbench Behavior Preservation Check | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.CLOSE | UX Branch Freeze Checkpoint | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.CONTEXT.1 | Run / Repository Context Binding | UX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| UX.LIVE.1 | Run Progress Instrumentation Plan | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.2 | Run Progress Snapshot Writer Plan | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.3 | Run Progress Snapshot Writer Shadow Mode | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.4 | Narrow Multi-Stage Shadow Instrumentation | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.5 | Current Run Snapshot Association | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.6 | Manual Run Progress Refresh | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.7 | Snapshot Freshness and Staleness Plan | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.8 | Freshness Classification Implementation | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.9 | Bounded Progress Polling Experiment Plan | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.10 | Optional Default-Off Bounded Progress Polling | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.LIVE.CLOSE | Live Run Progress Branch Checkpoint | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.RUN.1 | Run Progress / Operator Visibility | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.RUN.2 | Run Progress Snapshot Loader | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.RUN.3 | Run Progress UI Panel Stub | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.RUN.CLOSE | Run Progress Visibility Branch Checkpoint | UX | complete | LOCAL_0_OBSERVE | local_only | low | true |
| UX.STATE.1 | Repository / Run / Candidate State Ownership & Truthful Actions | UX | complete | LOCAL_1_PREPARE | local_only | medium | true |
| VERIFY.TEST.1 | Test Design and TDD Planning | VERIFY | proposed | LOCAL_0_OBSERVE | local_only | low | true |
| ANALYSIS.EVIDENCE.LIVE.1 | Role-Balanced Source Evidence Acquisition | WAITER | complete | LOCAL_1_PREPARE | local_only | medium | true |
| ANALYSIS.MULTIROOT.LIVE.1 | Explicit Read-Only Multi-Repository Evidence Contract | WAITER | complete | LOCAL_1_PREPARE | local_only | medium | true |
| WAITER.1 | Deterministic Capability-Based Execution Router | WAITER | complete | LOCAL_0_OBSERVE | local_only | low | true |
| WAITER.2 | Deterministic Evidence Requirement Contract | WAITER | complete | LOCAL_0_OBSERVE | local_only | low | true |
| WAITER.LIVE.1 | Live Task-Shape Routing & Change-Need Separation | WAITER | complete | LOCAL_1_PREPARE | local_only | medium | true |
| WORKER.DECL.1 | Native Worker Declaration Source Qualification & Wiring | WORKER | complete | LOCAL_0_OBSERVE | local_only | low | true |
| WORKER.DECL.2A | Strict Structured Patch Response Envelope | WORKER | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| WORKER.DECL.2A.1 | Strict Envelope Emission Adoption Experiment | WORKER | complete | LOCAL_0_OBSERVE | local_only | medium | true |
| WORKER.DECL.2A.2 | Live Strict Envelope Adoption Dogfood | WORKER | complete | LOCAL_0_OBSERVE | strong_model_requires_approval | medium | true |
| WORKER.DECL.2B | Pre-Execution Change Intent Channel | WORKER | active | LOCAL_0_OBSERVE | strong_model_requires_approval | medium | true |

## Boundaries

- ROAD.1 does not execute phases.
- ROAD.1 does not run validation or benchmarks.
- ROAD.1 does not call models.
- ROAD.1 does not apply patches.
- ROAD.1 does not push, merge, open PRs, or contact GitHub, Telegram, or N8N / external automation.
- ROAD.1 only validates and summarizes roadmap metadata.

