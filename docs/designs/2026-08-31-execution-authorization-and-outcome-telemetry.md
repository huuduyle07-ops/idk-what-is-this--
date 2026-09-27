# EXEC.AUTH.LIVE.1 — Execution Authorization & Outcome Telemetry Reconciliation

**Prerequisite:** OPS.PATCH.2
**Track:** OPS (`EXEC.*` is an ID namespace, following the `PATCH.*` precedent)
**Status:** complete

## 1. The finding

Repeated black-box runs showed T1/T2/T3 genuinely rewriting repository files,
passing validation, and leaving the bytes on disk — while the payload handed to
the operator still read:

```
write_authority             = false
patch_application_authority = false
human_approval_required     = true
```

and said nothing at all about whether a patch had been applied.

## 2. What those fields actually mean

Traced, not inferred from their names.

| Field | Written at | Subject |
| --- | --- | --- |
| `write_authority` | `core/control_engine.py` `enforce_control_grounding_on_payload`; `core/pipeline.py` `_record_patch_safety_handoff` | CONTROL / the planning stage may not authorize a write |
| `patch_application_authority` | same two sites | CONTROL / the planning stage cannot apply a patch |
| `human_approval_required` | same two sites (`policy.human_approval_required` is `True` on **every** style, including one whose `auto_apply_allowed` is `True`) | the candidate-review stage requires a human |

All three are statements about a **component**, and all three stay true for the
whole run — including a run whose patch a *different* component applied a moment
later under a *different* rule. None of them was ever an execution outcome, and
`write_authority=false` in a historical artifact is not retroactively readable as
"no write happened".

So they are preserved verbatim, and given `authority_scope = control_or_planning`
so a reader stops mistaking a component fact for an outcome.

## 3. The real authorization path

```
task route (WAITER.LIVE.1)          read-only ⇒ nothing may be applied
  → preflight / OPS.VALIDATE.1      executed failure evidence
  → CONTROL.SAFETY.LIVE.1           localization + exact source; write_authority=false
  → PATCH.BASIS.LIVE.1              grounded_defect | explicit_change_request
  → enforce_control_grounding_on_payload
                                    eligible_for_patch_safety_handoff on the payload
  → maybe_run_auto_patch            AUTO_PATCH_ENABLED, needs_escalation, style/task
  → build_patch_policy              ***auto_apply_allowed***  ← authorization
       or is_low_risk_single_file_patch  ← the second authorization rule
  → run_patch_plan_with_artifacts / run_self_correct_loop
       → patch safety (again, at the real root, pre-mutation)
       → apply → validate → rollback or persist
  → final result serialization      json_block → result["patch"]
```

**Execution authorization happens in exactly two places**, both inside
`core/pipeline.py::maybe_run_auto_patch`, and both unchanged by this phase:

* `plan_policy.auto_apply_allowed` immediately before `run_patch_plan_with_artifacts`
* `policy.auto_apply_allowed` — or the `is_low_risk_single_file_patch` override —
  immediately before `run_self_correct_loop`

Both reduce to a grounded defect. `explicit_change_request` never reaches either;
it stops at `_record_patch_safety_handoff`, which is the human-approval branch.

## 4. Three subjects, never collapsed

| Subject | Question | Fields |
| --- | --- | --- |
| component authority | may *this component* authorize a write? | `write_authority`, `patch_application_authority`, `human_approval_required`, `authority_scope` |
| execution authorization | did a later runtime gate authorize *this exact mutation*, and which? | `execution_authorized`, `execution_authority_source`, `execution_authorization_denied_reason`, `human_approval_required_for_execution` |
| execution fact | what was attempted, what moved, what survived? | `execution_attempted`, `mutation_observed`, `patch_applied`, `application_status`, `rollback_performed`, `final_repository_changed`, `final_validation_outcome`, `final_state_observation`, `observed_changed_paths` |

Plus one operator sentence, `execution_summary`, composed from the facts rather
than from a universal template.

`core/execution_outcome_telemetry.py::ExecutionTelemetry` refuses the collapses
structurally:

* attempted ⇒ authorized (never the reverse)
* observed mutation ⇒ attempted
* repository changed ⇒ mutation observed
* applied ⇒ changed **and** not rolled back
* rolled back ⇒ not changed

## 5. Authority-source vocabulary

A closed enum of gates that exist in production. No prose, no confidence.

| Value | The rule it names |
| --- | --- |
| `none` | nothing authorized this |
| `grounded_defect_auto_apply_policy` | `PatchPolicy.auto_apply_allowed` |
| `low_risk_grounded_single_file_policy` | `is_low_risk_single_file_patch` |
| `manual_apply_action` | a human pressed Apply (`/dream/apply`) |

## 6. Denials

Every non-executing path records **why**, from a closed set:
`no_change_requested`, `harness_mode_blocked`, `auto_patch_disabled`,
`no_patch_basis_handoff`, `needs_escalation`, `patch_style_or_task_not_eligible`,
`patch_basis_not_accepted`, `human_approval_required`, `patch_safety_blocked`,
`unsafe_validation_command`, `executor_risk_blocked`,
`patch_confidence_below_threshold`, `missing_source_snippet`,
`auto_patch_policy_declined`, `candidate_rejected`, `time_budget_exceeded`.

A **pre-mutation refusal is a denial, not an outcome.** The apply path runs patch
safety and the safe-validation gate against the real root *before* writing; a
refusal there means the mutation was never authorized, so the harmful test-edit
candidate reports `execution_authorized=false`, `execution_attempted=false`
rather than an attempt nobody made. An executor *conflict* — target snippet no
longer matches — is the other case, and stays an execution failure.

## 7. Final state

`final_repository_changed` is derived from CHECK.LIVE.1's own bounded observer —
`digest_known_paths` before, `derive_observed_change_records` after — over
**exactly the paths the operation named** (the payload's targets plus any target
the executor itself reported, relativised to the project root). No directory is
walked; no `git status` is run; nothing is discovered.

`final_state_observation` declares the scope honestly:

* `plan_named_paths` — every named path typed; the digests answered
* `incomplete` — a path had no "before" identity, or was unreadable/oversized; the
  executor's receipt answered instead
* `unavailable` — no digests could be taken; the receipt answered
* `not_attempted` — nothing ran

A rollback is authoritative in the other direction: OPS.PATCH.1 restores the
exact prior bytes, so a rolled-back run never reports persistence.

## 8. Observation never authorizes

CHECK.LIVE.1 primitives are reused to say **what happened**, after the fact. No
CHECK.LIVE shadow verdict is promoted into execution authority, no frozen CHECK.1
semantics are altered, and causality is not reversed. Likewise the model's own
prose ("I applied the patch") is never consulted: the factual sources are the
policy object, `applied_ops` / `rollback_performed` / `ExecutionResult.phase` /
`validation_outcome`, and the bounded digests. Worker declarations are not used
to decide whether a mutation occurred, so WORKER.DECL.2B stays parked.

## 9. Non-goals, enforced

* No authorization policy, patch-safety rule, auto-apply rule or human-approval
  rule changed. With the telemetry deleted, every apply/refuse/validate/rollback
  decision is identical.
* Sandbox validation (OPS.PATCH.2), patch basis (PATCH.BASIS.LIVE.1) and model
  confidence remain non-authorizing.
* Zero model calls, zero network calls, zero traversal, no retrieval or indexing
  change, no timeout re-categorisation — the typed OPS.VALIDATE.1 outcome is
  reported exactly as it currently exists, leaving OPS.VALIDATE.2 next.
* No field removed, renamed or redefined; historical artifacts stay readable.

## 10. Known limitation

`core/pipeline.py::execute_subtask` (mission-mode subtask apply) calls the
Executor directly and produces a subtask record rather than the operator-visible
run payload. It is deliberately left uncovered rather than given telemetry with
no reader.
