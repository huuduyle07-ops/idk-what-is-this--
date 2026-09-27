# CHECK.2 — Post-Run Goal-Fidelity Verification Contract

**Status:** complete, report-only, not live-wired
**Date:** 2026-08-27
**Depends on:** CHECK.1 (`core.post_run_reconciliation`) and CLAIM.1
(`core.claim_assessment`), both frozen

## Boundary

CHECK.2 owns one deterministic transition:

```text
CHECK.1 PostRunReconciliation
    + an explicit requirement ledger
    + an explicit goal-verification specification
    + frozen CLAIM.1 ClaimAssessment records
    -> GoalFidelityAssessment
```

It answers exactly one question:

> For every explicit goal and preservation obligation, what does the
> already-assessed semantic evidence say about whether the final execution
> satisfied that obligation?

It does **not** answer:

> Should this run be finally accepted?

That belongs to a future CHECK.3 / RUN.VERDICT.1. Every result — including one
where every required obligation reads as satisfied — carries
`run_verdict_required` and `human_review_required`, and the result **cannot be
constructed without them**.

`core/goal_fidelity_review.py` is pure and import-time inert. Its only project
imports are the two frozen contracts it reconciles. It performs no repository
traversal, source or diff read, evidence acquisition, semantic re-analysis,
validation execution, command execution, patch generation or application, model
call, network call, merge, or write.

## Why the phase exists

CHECK.1 reconciles *typed declarations against typed facts*: scope, authority,
declared-vs-observed change, validation coverage and freshness, final-state
binding. It closes with `semantic_goal_review_required` on every result,
because none of those facts say whether the implementation did what the user
asked.

The obvious way to close that gap is the one this phase refuses:

```text
TaskContract + diff + worker note  ->  Reviewer LLM  ->  "looks correct"
```

That architecture has a model grading a model with no evidence discipline, no
proposition identity and no way to distinguish "the patch adds a rule" from
"the final behaviour changed". The project already built the discipline —
ACQUIRE → EVIDENCE.1 → EVIDENCE.2 → CLAIM.1 — so CHECK.2 consumes its output
instead of re-deriving it. There is no reviewer model in this phase and no
route to reach one.

## Architecture

```text
              Task obligations
                    │
                    ▼
        GoalVerificationSpecification
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
     CHECK.1               ClaimAssessment[]
 objective reconciliation   (ACQUIRE → EVIDENCE → CLAIM.1)
        └───────────┬────────────┘
                    ▼
                 CHECK.2
                    ▼
          GoalFidelityAssessment
                    ▼
                   STOP
```

CHECK.2 is the first phase that genuinely consumes both branches, so its
registry prerequisites are `["CHECK.1", "CLAIM.1"]`. It consumes no SYNTHESIS.1
`StructuredSynthesis` and imports nothing from it: composing claims into a task
answer and reconciling claims against post-run obligations are different
questions over the same records.

## Supplied records

```text
ExplicitRequirementSource:
    requirement_id
    requirement_kind          goal_requirement | explicit_constraint
    requirement_text_sha256
    provenance                explicit_task_contract | explicit_human_binding
    required
    ordinal                   (optional)

ExplicitRequirementLedger:
    task_contract_fingerprint
    requirements[]
    -> explicit_requirement_ledger_fingerprint()

GoalVerificationObligation:
    obligation_id
    obligation_kind               goal_requirement | preservation_requirement
                                  | explicit_constraint
    obligation_text_sha256
    source_requirement_id
    preservation_obligation_kind  (required iff preservation_requirement)
    required
    ordinal                       (optional)

PostRunStateBinding:
    final_state_fingerprint
    state_receipt_sha256
    provenance                upstream_final_state_receipt
                              | explicit_human_binding

ObligationClaimBinding:
    obligation_id
    proposition_id, proposition_sha256
    expected_claim_assessment_fingerprint
    satisfaction_polarity          (optional in the type, mandatory in the outcome)
    polarity_provenance            (optional in the type, mandatory in the outcome)
    expected_evidence_set_fingerprint  (optional)
    post_run_state_binding             (optional)

GoalVerificationSpecification:
    task_contract_fingerprint
    check_1_reconciliation_fingerprint
    requirement_ledger_fingerprint
    obligations[], bindings[]
    -> goal_verification_specification_fingerprint()

GoalFidelityReviewRequest:
    reconciliation (PostRunReconciliation)
    specification, requirement_ledger
    claim_assessments[]
    expected_* fingerprints
```

The pure core needs no source bytes, no diff text, no repository root, no
filesystem handle, no validation command and no analyzer. The request type has
nowhere to put any of them, and serializes
`source_content_supplied = diff_content_supplied = repository_root_supplied =
analyzer_supplied = false`.

**No obligation prose anywhere.** Obligations carry `obligation_text_sha256`
only, exactly as CHECK.1's `PreservationObligation` does. CHECK.2 structurally
cannot reinterpret, narrow or broaden what the user asked for, because it never
sees the words. Human-readable text reaches the result only as
`proposition_text`, copied verbatim from the bound ClaimAssessment.

## The CHECK.1 entry gate

Semantic assessment must never rescue an execution-contract violation, so the
mode is decided before a single obligation is read:

| CHECK.1 status | CHECK.2 review mode |
| --- | --- |
| `reconciled` | `assessable` |
| `reconciled_with_warnings` | `assessable` |
| `incomplete` | `diagnostic_only` |
| `suspicious` | `diagnostic_only` |
| `blocked` | `blocked` |
| `inconsistent_input` | `blocked` (+ `inconsistent_input` status) |

`CHECK_1_ENTRY_POLICY` is a table keyed by CHECK.1's own status vocabulary, and
a focused test asserts the table covers every value, so a new CHECK.1 status
cannot silently fall through to a permissive default.

In `blocked` mode every obligation result is `blocked_by_reconciliation`. The
bound proposition and CLAIM.1's own status stay visible for audit, but no
obligation reaches a determined state — and `GoalFidelityAssessment.__post_init__`
**raises** if a blocked review carries a satisfied or violated obligation. The
anti-rescue invariant is structural, not a policy branch somebody could forget.

In `diagnostic_only` mode the mapped semantic states *are* reported, each
carrying `execution_reconciliation_unresolved`, with
`semantic_goal_review_authority = false` and a serialized `review_mode_meaning`
saying the states certify nothing about this run.

## Obligation sources: no invention, no loss, no widening

Two authoritative sources, and neither is the specification itself:

| Obligation kind | Authoritative source | Can the caller mint it? |
| --- | --- | --- |
| `preservation_requirement` | the CHECK.1 result's own `preservation_findings` | **no** — CHECK.1's result is fingerprint-bound |
| `goal_requirement` / `explicit_constraint` | `ExplicitRequirementLedger`, bound to the same `task_contract_fingerprint` | supplied upstream, re-fingerprinted here |

Each obligation must match its named source on identity, text digest, kind and
`required` flag. Then:

- **No invention.** `LEDGER_REQUIREMENT_KINDS` excludes
  `preservation_requirement`, so a preservation obligation cannot be laundered
  in through the caller-supplied ledger. `REQUIREMENT_PROVENANCES` has no
  `inferred` value, so "since this touches indexing, performance should also be
  checked" has no representable provenance.
- **No widening.** An obligation whose `source_requirement_id` names nothing —
  or names a source another obligation already claimed — is
  `obligation_structure_widened` and refuses the request.
- **No loss.** Every CHECK.1 preservation finding and every *required* ledger
  requirement must appear, or the request is
  `preservation_obligation_dropped` / `goal_obligation_dropped`.

Three goals plus two preservation constraints therefore produce exactly five
obligation results, even when all five are `missing_claim_assessment`.
Optionality is never invented: it comes from the ledger's own `required` flag,
and a missing optional obligation is `optional_obligation_evidence_absent`
rather than a required gap.

This mirrors the project's existing preservation invariants: WAITER.2 loses no
capability, ACQUIRE.1 loses no evidence requirement, SYNTHESIS.1 loses no
requested slot, CHECK.2 loses no semantic obligation.

## Proposition binding and satisfaction polarity

CHECK.2 never writes proposition text and never matches one. An obligation
reaches its semantics only through an explicit `ObligationClaimBinding` naming
a proposition id, its digest and the exact expected ClaimAssessment
fingerprint. There is no text similarity, no embedding and no model matching.

Polarity is the field that makes the mapping honest. The obligation

> Do not change embedding behaviour.

is satisfied by **support** for

> Final implementation preserves the previous embedding behaviour.

and by **contradiction** of

> Final implementation changes the embedding behaviour.

A CLAIM.1 relation alone cannot distinguish those, so the binding must state
`satisfaction_polarity` *and* `polarity_provenance`
(`explicit_human_binding` / `upstream_goal_projection` /
`preserved_requirement_binding`). A binding missing either is
`binding_invalid` — never guessed, never defaulted. A focused regression binds
one ClaimAssessment to two obligations under opposite explicit orientations and
asserts they produce opposite obligation states, which is the proof that
CHECK.2 is not quietly assuming claim direction equals obligation direction.

`POLARITY_PROVENANCES` contains no CHECK.2 value, so the phase has nowhere to
record having produced an orientation itself.

## Status mapping

`support_means_satisfied`:

| ClaimAssessment | Obligation |
| --- | --- |
| `supported_by_assessed_evidence` | `satisfied_by_assessed_evidence` |
| `contradicted_by_assessed_evidence` | `violated_by_assessed_evidence` |

`contradiction_means_satisfied` reverses exactly those two rows and nothing
else. Every unresolved state is looked up *first* and is polarity-independent:

| ClaimAssessment | Obligation, under either polarity |
| --- | --- |
| `conflicting_evidence` | `conflicting_evidence` |
| `insufficient_evidence` | `insufficient_evidence` |
| `coverage_incomplete` | `coverage_incomplete` |
| `current_state_unestablished` | `current_state_unestablished` |
| `current_state_inconsistent` | `current_state_inconsistent` |
| `inconsistent_input` | `binding_invalid` |

CLAIM.1's own status is preserved on every obligation result next to the mapped
one, so the mapping is auditable without trusting that it was applied
correctly. CHECK.2 never re-runs CLAIM.1 logic and never reinterprets evidence:
`_map_claim_status` is a dictionary lookup.

Two further states exist because the alternative would be invention:
`missing_claim_assessment` for a required obligation with no binding or no
supplied claim, and `composite_obligation_unsupported` when more than one
binding names one obligation — CHECK.2 invents no aggregation rule, and an
upstream composite proposition with its own CLAIM.1 assessment is the supported
route.

One claim may serve several obligations, but only where it was explicitly bound
several times. A supplied ClaimAssessment nobody bound is recorded in
`unbound_claim_assessments` with `CHECK2_UNBOUND_CLAIM_ASSESSMENTS_IGNORED` —
visible, never opportunistically reused.

## A validation receipt is not a semantic claim

CHECK.1 may report that `test_tmp_ignore` passed, was required, and binds the
final state. That establishes the *execution of a validation*, not the meaning
of a goal. A regression sets exactly that up with no bound ClaimAssessment for
the `.tmp` obligation and asserts `missing_claim_assessment`, not `satisfied`.

The same separation holds for current-state claims. CHECK.1's
`validated_state_current` does not discharge CLAIM.1's `CurrentStateReceipt`
requirement; `current_state_unestablished` and `current_state_inconsistent`
survive into the obligation result untouched. And a negative existential whose
`coverage_incomplete` CLAIM.1 refused to resolve stays `coverage_incomplete`
here: many files lacking a counterexample is still not an absence proof.

Diff-intent and final-state propositions are likewise never collapsed. "The
patch adds a `.tmp` exclusion rule" and "the final indexing behaviour excludes
`.tmp` files" are different propositions with different evidence paths; CHECK.2
preserves whichever one was bound and infers neither from the other.

## Post-run final-state binding — a stated gap

A `ClaimAssessment` carries a proposition, an evidence-set fingerprint and a
semantic basis. It carries no repository identity and no final-state identity.
A repository source digest alone therefore does **not** prove that a claim
describes the state CHECK.1 reconciled.

CHECK.2 does not invent that binding:

- **No binding supplied** → the obligation records
  `final_state_binding_unavailable`, the result raises
  `post_run_semantic_state_binding_unavailable`, and the top-level status is
  `assessed_with_gaps` rather than `assessed`. The obligation's own mapped
  state is still reported — it is bounded evidence about a proposition, and
  saying so is honest — but nothing reads as proven for the post-run state.
- **A binding naming a different final state** → `post_run_state_binding_mismatch`,
  refused as `inconsistent_input`.
- **A binding naming CHECK.1's exact final state**, with an upstream receipt
  digest and bounded provenance → `bound_to_final_state`, and the status may
  reach `assessed`.

Because nothing upstream currently mints such a receipt, `assessed_with_gaps`
is the honest normal outcome today. That is deliberate.

## Result

```text
GoalFidelityAssessment:
    status                        assessed | assessed_with_gaps
                                  | diagnostic_only | blocked | inconsistent_input
    review_mode                   assessable | diagnostic_only | blocked
    task_contract_fingerprint
    check_1_reconciliation_fingerprint
    verification_specification_fingerprint
    requirement_ledger_fingerprint
    request_fingerprint
    execution_reconciliation      (CHECK.1 status, inconsistencies, unresolved
                                   requirements, final state, coverage, freshness)
    obligation_results[]
    satisfied_obligations[] / violated_obligations[] / unresolved_obligations[]
    unbound_claim_assessments[]
    semantic_basis
    unresolved_requirements[], reasons[], inconsistencies[]
    -> assessment_fingerprint
```

`assessed` means *every required obligation reached a determined state and
CHECK.1 permitted semantic review*. It says nothing about direction: an
assessment holding one violated preservation obligation is `assessed` too. The
contract serializes `assessed_meaning` to say so. There is no `success`,
`failure`, `correct` or `incorrect` value in either status vocabulary.

The three obligation lists are identities, not quantities, and a constructor
invariant requires them to mirror `obligation_results` exactly — so an
obligation cannot be reported in a bucket it does not belong to, or omitted
from all of them.

## No majority, no score, no acceptance

Three satisfied goals do not outvote one violated preservation constraint. A
satisfied primary goal cannot hide a violated preservation obligation: a
regression asserts both appear, with no combined reading anywhere. There is no
count, tally, percentage, score, confidence or weight in the contract, and the
static suite proves the arithmetic that would allow one is absent from the
module — no `sum`, `max`, `min`, `Counter`, no `+`/`-`/`*`/`/`, and no
comparison with a length on both sides.

Serialization carries only *denials*: `goal_proven`,
`objective_truth_asserted`, `implementation_correctness_asserted`,
`run_verdict_produced`, `semantic_evidence_reassessed`,
`obligations_derived_by_check_2`, `propositions_derived_by_check_2`,
`polarity_derived_by_check_2` — all `false`, all properties or constants rather
than settable fields. A boundary test renders a fully-satisfied assessment and
asserts no key equivalent to `run_success`, `final_success`, `merge_ready`,
`safe_to_merge`, `implementation_correct`, `goal_satisfied`,
`semantic_truth_verified`, `confidence`, `probability`, `score` or
`satisfied_count` exists at all.

The deliberately-absent boolean is `all_required_obligations_assessed_satisfied`.
It would be a defensible evidence-state summary and it would also be the exact
field a downstream consumer would read as a verdict, so the reduction is left
entirely to CHECK.3.

## Semantic provenance

Directional CLAIM.1 records arrive `analyzer_assessed` and leave
`analyzer_assessed`. Ten satisfied obligations are ten analyzer-assessed
obligations; aggregation upgrades nothing, and there is no
`semantically_verified`, `deterministic_semantic_truth` or `goal_proven` value
to upgrade *to*.

The contract states the limitation in words, in the payload:

> **`satisfied_by_assessed_evidence` means:** given the supplied
> proposition-to-obligation orientation, the bounded CLAIM.1 assessment for this
> obligation points toward satisfaction of that explicit obligation. It does
> **not** mean the implementation was deterministically proven to satisfy it —
> the underlying semantic relations remain analyzer-assessed.

This inherits CLAIM.1's own limitation exactly: `supported_by_assessed_evidence`
means the admitted evidence set supports the proposition according to gated
analyzer assessments, not that the proposition is true.

## Fingerprints, tamper binding and determinism

Canonical SHA-256 identities bind the task contract, the CHECK.1
reconciliation, the requirement ledger, the verification specification, every
obligation, every proposition binding and every ClaimAssessment. All of them
are **re-derived** from the exact frozen records rather than accepted from the
caller; `type(x) is T` checks make the identity properties impossible to
override.

| Tamper | Outcome |
| --- | --- |
| specification prepared for another task contract | `specification_task_binding_mismatch` |
| ledger prepared for another task contract | `requirement_ledger_task_binding_mismatch` |
| specification bound to another execution | `specification_reconciliation_binding_mismatch` |
| expected reconciliation/specification/ledger fingerprint edited | the matching `*_fingerprint_mismatch` |
| a ClaimAssessment edited after the binding was written | `claim_assessment_fingerprint_mismatch` |
| a proposition reworded | `claim_proposition_binding_mismatch` |
| a binding naming another evidence set | `claim_evidence_set_binding_mismatch` |
| two ClaimAssessments for one proposition | `duplicate_claim_assessment_supplied` |
| a binding for an obligation that is not in the set | `claim_binding_names_unknown_obligation` |
| an upstream record already asserting authority or a violated guardrail | `upstream_authority_asserted` / `upstream_guardrail_violated` |

A refused request emits **no** obligation results: the specification that names
the obligations is exactly what was refused, so reporting per-obligation states
derived from it would be reporting from an untrusted source. The refusal names
its inconsistency and nothing reads as satisfied.

Determinism: unordered binding and claim input canonicalises; explicit
obligation ordinals are preserved where stated and refused when only partly
stated (a partly-ordered set has no canonical order, and CHECK.2 will not
invent one); time, randomness and machine state are absent. Same inputs, byte
identical `GoalFidelityAssessment`.

## Authority and guardrails

`semantic_goal_review_authority` is true only for an `assessable`, coherent
request. Always false: `post_run_reconciliation_authority`,
`final_success_authority`, `run_verdict_authority`, `merge_authority`,
`implementation_correctness_authority`, `objective_truth_authority`,
`claim_assessment_authority`, `conflict_adjudication_authority`,
`evidence_acquisition_authority`, `evidence_verification_authority`,
`repository_read_authority`, `repository_traversal_authority`,
`validation_execution_authority`, `command_execution_authority`,
`worker_launch_authority`, `patch_authority`, `write_authority`,
`routing_authority`, `planning_authority`, `model_selection_authority`,
`provider_selection_authority`, `response_synthesis_authority`,
`final_response_authority`. `human_approval_required` is always true.

Honest true guardrails: `check_1_gate_evaluated`,
`semantic_obligations_reconciled`, `claim_assessments_consumed`,
`preservation_obligations_checked`, `semantic_provenance_preserved`,
`post_run_state_binding_checked` — each reported only when that work actually
ran. Always false: `source_content_read`, `diff_content_read`,
`repository_traversed`, `evidence_acquired`, `evidence_reassessed`,
`validation_executed`, `model_called`, `network_called`,
`proposition_invented`, `proposition_rewritten`, `obligation_invented`,
`obligation_dropped`, `polarity_inferred`, `claim_status_reinterpreted`,
`semantic_status_upgraded`, `conflict_resolved`, `majority_computed`,
`confidence_computed`, `worker_repaired`, `patch_modified`, `files_modified`,
`merge_performed`, `final_success_declared`, `run_verdict_declared`,
`objective_truth_asserted`.

## DeepSeek-style regressions

```text
Goal:          add session persistence
Preservation:  do not weaken authorization checks
CHECK.1:       reconciled
Claims:        persistence  -> supported_by_assessed_evidence
               authorization -> contradicted_by_assessed_evidence
```

Result: `G-session` is `satisfied_by_assessed_evidence`, `O-auth` is
`violated_by_assessed_evidence`, both visible, no combined reading, no
`run_success`, no "primary goal wins".

Same semantic claims with CHECK.1 `blocked` because a forbidden config path
changed: `review_mode = blocked`, every obligation
`blocked_by_reconciliation`, `satisfied_obligations` empty, CHECK.1's
`forbidden_path_changed` carried forward. Supporting semantic evidence rescues
nothing.

## Known limitations and missing upstream producers

1. **No goal-obligation producer.** `TaskContract` exposes explicit
   `constraints[]` and `ExplicitEvidence`, but nothing projects them into a
   typed goal requirement set, and `task_contract_fingerprint` currently lives
   in `core.structured_synthesis` (SYNTHESIS.1), which CHECK.2 must not depend
   on. So the `ExplicitRequirementLedger` is *supplied*, bound to CHECK.1's own
   `task_contract_fingerprint`. A `goal_requirement_projection` producer is
   future work.
2. **No proposition projection producer.** Nothing turns "exclude `.tmp` files"
   into `Proposition("Final implementation excludes .tmp files from repository
   indexing.")`. CHECK.2 requires the binding as input and solves none of it
   opportunistically. `goal_proposition_projection` is a likely small future
   phase.
3. **No polarity producer.** Nothing mints obligation-to-proposition
   orientation. It must be supplied with bounded provenance.
4. **No post-run ClaimAssessment producer.** Nothing currently runs the
   ACQUIRE → EVIDENCE → CLAIM.1 spine *after* an execution against post-run
   propositions.
5. **No final-state semantic binding.** Nothing mints a receipt tying an
   evidence set to an exact post-run repository state, so
   `final_state_binding_unavailable` is today's normal outcome and the phase
   says so rather than pretending otherwise.
6. **Preservation obligations only from CHECK.1.** Preservation obligations are
   authoritative from the CHECK.1 result. A run whose authorization carried no
   preservation obligation offers CHECK.2 none to check — the gap is upstream,
   and inventing one here would be exactly the failure this phase exists to
   prevent.
7. **One canonical proposition per obligation.** Multiple claims per obligation
   return `composite_obligation_unsupported` rather than an invented
   aggregation rule.
8. **No repair loop.** CHECK.2 never asks an analyzer, a worker or ACQUIRE for
   more, so an input mismatch stays auditable.
9. **Registry prerequisites.** The registry supports multiple prerequisites, so
   `["CHECK.1", "CLAIM.1"]` is recorded truthfully rather than flattened to a
   single linear predecessor.

## Not wired

No Commander, Instant Run, Project Evolution, Workbench, Mixed Mode, executor,
validation runner, patch path, merge path or response generation imports or
calls CHECK.2. Tests and fixtures are its only callers.

CHECK.1, CLAIM.1, EVIDENCE.1–2 and ACQUIRE.1–3 behaviour is unchanged. The
boundary suites of both upstream phases were widened by exactly one permitted
report-only contract consumer each, and each widening is guarded by a narrower
assertion proving CHECK.2 reads the frozen contract, names none of the
upstream construction types, and can re-run neither phase.

## Recommended next phase

**CHECK.3 / RUN.VERDICT.1 — bounded run acceptance eligibility.** It may
combine CHECK.1's contractual reconciliation state with CHECK.2's per-obligation
fidelity states into a bounded
`eligible_for_human_acceptance` / `unresolved` / `blocked` verdict. It must not
be automatic merge or automatic patch acceptance, and it inherits every
limitation above: a verdict built on `analyzer_assessed` obligations is a
verdict about assessed evidence, not about truth.

Before that, the smaller missing producers — goal-obligation projection,
proposition projection with polarity, and a post-run final-state receipt —
would each make CHECK.2's output substantially less gap-laden, and each is a
separately governable slice.
