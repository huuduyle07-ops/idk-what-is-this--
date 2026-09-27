# SYNTHESIS.1 — Task-Shaped Claim Composition Contract

**Status:** complete, report-only, not live-wired  
**Date:** 2026-08-26  
**Depends on:** INPUT.1 `TaskContract`, CLAIM.1 `ClaimAssessment`

## Boundary

SYNTHESIS.1 owns one deterministic transition:

```text
preserved INPUT.1 task/output structure
    + supplied synthesis specification
    + explicit proposition-to-slot bindings
    + frozen CLAIM.1 assessments
    -> StructuredSynthesis
```

It answers only: *where do the already-assessed propositions belong in the
answer structure the user requested?* It does not decide whether a proposition
is objectively true, derive a proposition, resolve a conflict, choose a winner,
score a comparison, compute confidence, or render a final response.

`core/structured_synthesis.py` is pure and import-time inert. Its project
dependencies are the frozen INPUT.1 and CLAIM.1 data contracts. It does not
read the filesystem or source content, import an acquisition or evidence
runtime, call a model, use a network, execute a command, or write anything.

## Authoritative input

The `TaskContract` is authoritative for explicit user structure:

- comparison subjects and their order
- ordered rubric items classified into INPUT.1's framework contract
- explicit output format
- explicit constraints
- the INPUT.1 preservation receipt

`TaskShape` is intentionally not an input. Workflow-routing shape cannot
rewrite the requested answer shape.

The second input is a supplied `SynthesisSpecification`. This is a structural
contract, not a planner and not a prose prompt:

Literal `explicit_evidence` wins over inferred TaskContract metadata for
subjects, rubric, output format, and constraints. Conflicting literal output
formats fail closed; an inferred output format cannot overwrite one the user
explicitly supplied. Failed preservation, truncated explicit structure, or an
unsupported TaskContract schema remains `inconsistent_input` even when the
synthesis specification itself is missing.

```text
SynthesisSubject:
    subject_id
    label
    ordinal

SynthesisConstraint:
    kind
    text
    ordinal

SynthesisSlot:
    slot_id
    label
    ordinal
    subject_id | null
    required_proposition_ids[]
    required

DecisionRequirement:
    requested
    type
    provenance | null
    decision_performed = false                 # read-only property

SynthesisSpecification:
    task_contract_fingerprint
    preservation_fingerprint
    output_shape
    preserved_output_format | null
    ordered_subjects[]
    ordered_slots[]
    constraints[]
    claim_bindings[]
    decision_requirement
    schema_version
```

Subject, slot, and constraint ordinals are contiguous and begin at one. Their
tuple order is semantic user order. Required proposition ids inside a slot are
canonically ordered because their internal order has no presentation meaning.

The supported output shapes are:

- `single_slot`
- `comparison_matrix`
- `ordered_sections`
- `keyed_report`

`single_slot` contains exactly one slot. `comparison_matrix` contains at least
two ordered subjects; its ordered slots are rows and the subject axes are
columns. The composer materializes every row/subject cell. It does not collapse
the matrix into a summary.

## Explicit claim-slot binding

Every attachment is supplied as an immutable exact binding:

```text
ClaimSlotBinding:
    slot_id
    subject_id | null
    proposition_id
    expected_assessment_fingerprint
    provenance
```

The bounded provenance vocabulary is:

- `explicit_task_contract`
- `preserved_rubric_binding`
- `upstream_proposition_plan`

Provenance is a declaration about a supplied binding; it does not cause this
phase to create the binding. The module performs no text similarity, lexical
guessing, embedding match, or model match. It re-derives each supplied
`ClaimAssessment` fingerprint and checks that both the expected fingerprint and
the proposition id agree with the binding.

A supplied assessment that is not explicitly bound is inconsistent input. A
binding with no supplied assessment remains represented as
`missing_claim_assessment`. A required slot or matrix cell that declares
propositions but has no binding remains represented as
`proposition_binding_required`. Neither case is repaired by inference.

One assessment may appear in several slots only when several explicit bindings
name it. Multiple assessments may occupy one slot only when each proposition is
declared by the slot and explicitly bound.

## Request and bounded references

```text
SynthesisRequest:
    task_contract
    specification | null
    claim_assessments[]
    expected_synthesis_specification_fingerprint | null
    schema_version

ClaimAssessmentReference:
    assessment_fingerprint
    proposition_id
    proposition_sha256
    assessment_status
    semantic_basis
    missing_requirements[]
    inconsistencies[]
```

The reference is deliberately bounded. It carries no source bytes, source id,
path, excerpt, span, analyzer output, probability, score, or newly generated
claim text.

## Slot result

Each structural target becomes one immutable result:

```text
SynthesisSlotResult:
    slot_id
    label
    ordinal
    subject_binding | null
    claim_assessment_refs[]
    missing_proposition_ids[]
    slot_status
    claim_statuses[]
    unresolved_reasons[]
    semantic_basis
    binding_provenances[]
```

`claim_statuses` exactly mirrors the ordered claim references. The composer
does not replace several statuses with a directional aggregate.

| CLAIM.1 status | Slot status |
|---|---|
| `supported_by_assessed_evidence` | `populated` |
| `contradicted_by_assessed_evidence` | `populated` |
| `conflicting_evidence` | `unresolved_conflict` |
| `insufficient_evidence` | `unresolved_insufficient` |
| `coverage_incomplete` | `unresolved_coverage` |
| `current_state_unestablished` | `unresolved_current_state` |
| `current_state_inconsistent` | `unresolved_current_state` |
| `inconsistent_input` | `inconsistent` |

An unbound required target is `proposition_binding_required`; a bound target
without its assessment is `missing_claim_assessment`; and an explicitly
non-applicable optional target is `not_applicable`. Different statuses in one
slot produce `mixed_claim_states`. There is no majority, precedence, strongest
claim, contradiction-wins, or support-wins rule.

Supported means support for the proposition as written, not positive sentiment.
For example, support for a proposition describing a missing capability remains
support for that negative proposition. Contradiction is likewise preserved as
a claim status rather than converted into sentiment.

## Structured result

```text
StructuredSynthesis:
    status
    task_contract_fingerprint
    preservation_fingerprint
    synthesis_specification_fingerprint | null
    request_fingerprint
    output_shape
    preserved_output_format | null
    ordered_subjects[]
    ordered_slots[]
    preserved_constraints[]
    slot_results[]
    decision_requirement
    unresolved_requirements[]
    reasons[]
    inconsistencies[]
    semantic_basis
    preservation | null
    schema_version
    synthesis_fingerprint                 # derived property
    authority                             # serialization only
    guardrails                            # serialization only
```

The top-level status vocabulary is:

- `composed`: every required target is populated without an unresolved state
- `composed_with_gaps`: the requested shape is complete but at least one claim
  remains conflicting, insufficient, coverage-blocked, current-state-blocked,
  inconsistent, missing, mixed, or requires a downstream decision
- `incomplete_specification`: the specification is absent or a required target
  lacks a proposition binding
- `inconsistent_input`: task/specification, fingerprint, binding, subject,
  rubric, constraint, output-format, or upstream-authority checks failed

`composed_with_gaps` deliberately separates structural completeness from
epistemic resolution. A missing assessment is a visible cell, not a deleted
cell and not a negative finding.

`render_structured_synthesis_json` serializes this schema as structured data.
It is not RESPONSE.1 and emits no generated answer paragraph.

## Preservation gate

`check_synthesis_preservation(task_contract, synthesis_specification,
synthesis_result, claim_assessments)` is structural only. It never judges
whether a claim is correct. The exact frozen assessments are required whenever
claim bindings exist; a copied opaque digest is not accepted as proof of a
claim's status or semantic basis. The gate verifies:

- task, INPUT.1 preservation, and specification fingerprint bindings
- requested output shape and preserved output format
- exact ordered subjects, slots, and constraints
- exact decision requirement
- every expected slot or matrix cell exists in exact order
- no extra slot or matrix cell exists
- each claim reference exactly re-derives from its bound frozen assessment
- every bound proposition appears either as a reference or as an explicit
  missing proposition
- binding gaps and unresolved states remain visible
- top-level status, unresolved requirements, semantic basis, reasons, and
  request identity are re-derived rather than trusted

This establishes both halves of the output invariant:

```text
not narrower: no required subject, rubric item, section, slot, or cell is lost
not wider:    no subject, rubric item, section, slot, cell, or claim is invented
```

A caller cannot replace a five-item rubric with an architecture summary, add a
sixth dimension, alphabetize an explicitly ordered rubric, rename a comparison
subject, change a matrix into bullets, or hide a missing cell and still pass the
gate.

## No cross-claim or cross-slot inference

SYNTHESIS.1 may only collect exact references. It cannot turn two existing
capability claims into a new proposition such as “the architecture is mature.”
It cannot turn several populated dimensions into “overall strong,” and it
cannot count populated rows to select a comparison winner. Such a higher-order
statement would need its own proposition and CLAIM.1 assessment, or a future
separately governed decision contract.

There are no score, weight, tally, probability, percentage, confidence, rank,
winner, or recommendation fields. The same rule applies even when every input
assessment is directional.

## Semantic basis

The semantic basis ceiling remains `analyzer_assessed`. When all referenced
claims are analyzer-assessed, the slot and composed result say
`analyzer_assessed`; when no such basis can be established, they say
`not_established`. Several analyzer-assessed claims never become deterministic
truth through aggregation.

Conflict, insufficiency, coverage gaps, current-state gaps, and upstream claim
inconsistency remain first-class output states. None is converted into a
directional conclusion.

## Decision requirement

An explicit request such as “which is better?” is preserved structurally as a
bounded `DecisionRequirement` with type `comparative_preference`,
`comparative_selection`, or `recommendation`. Its `decision_performed` property
is always false, `decision_authority` is always false, and the result records
`downstream_decision_required`.

This preserves the user's requirement without executing it. SYNTHESIS.1 does
not implement DECIDE.1, and RESPONSE.1 may not silently smuggle in a decision
policy later.

## Fingerprints and determinism

Canonical SHA-256 identities bind:

- the exact `TaskContract`
- the INPUT.1 preservation receipt
- the `SynthesisSpecification`, including order, bindings, and decision marker
- every referenced CLAIM.1 assessment, re-derived from its frozen fields
- the request
- the structured result and output-side preservation report; a passed report is
  bound to the exact pre-receipt result identity and cannot be reused after a
  result field is changed

ClaimAssessment input order is semantically irrelevant and is canonicalized.
Subject and rubric order is semantically meaningful and remains controlled by
explicit ordinals. The same inputs produce byte-identical JSON. There is no
clock, randomness, counter, filesystem state, or machine state in the identity.

## Authority and guardrails

`structured_synthesis_authority` is true only for `composed` or
`composed_with_gaps` with a passed output preservation report. Every other
authority is always false:

```text
final_response, final_claim, decision, recommendation,
evidence_verification, evidence_acquisition, repository_read, network,
model_selection, provider_selection, execution, patch, write
```

Human approval is always required.

Serialization states the performed structural work and the standing denials.
`claim_assessments_composed`, `task_shape_preserved`,
`output_structure_preserved`, and `unresolved_states_preserved` may be true for
a valid composition. The following are always false:

```text
model_called, repository_read, evidence_acquired, evidence_reverified,
claim_invented, claim_reinterpreted, conflict_resolved, decision_performed,
winner_selected, confidence_computed, score_computed,
final_response_generated
```

## DeepSeek five-way regression

The acceptance fixture preserves these subjects in order:

1. C.A.T.T.U.S
2. DeepSeek Harness

and these dimensions in order:

1. planning
2. repository understanding
3. execution
4. evidence
5. safety

Explicit proposition-to-cell bindings and synthetic frozen ClaimAssessments
produce exactly ten structural cells. Conflict, insufficiency, contradiction,
and a missing assessment remain visible in their original cells. No sixth
dimension, omitted cell, architecture-summary replacement, new proposition,
winner, score, confidence, or final prose is produced.

This closes the original failure class at the contract layer: an agent-selected
answer shape cannot replace the user's preserved five-way rubric and still pass
the output preservation gate.

## Known limitations

### No proposition-binding producer

The current production pipeline has no phase that translates preserved rubric
slots into proposition ids and no production producer for
`SynthesisSpecification` or `ClaimSlotBinding`. Tests and fixtures supply them
explicitly. The provenance value `upstream_proposition_plan` reserves a bounded
contract shape; it does not imply such a planner exists.

When the specification itself is absent, SYNTHESIS.1 returns
`incomplete_specification` with `synthesis_specification_required`. When a
required target lacks proposition bindings, it returns
`incomplete_specification` with explicit `proposition_binding_required` slot
states. The composer does not absorb proposition planning to make this gap
disappear.

The frozen INPUT.1 schema also has no typed requested-section or decision-marker
field. Consequently SYNTHESIS.1 does not reinterpret raw request text or generic
list items to create either one. Where those structures are needed, the supplied
fingerprint-bound `SynthesisSpecification` must carry them; producing that
specification remains the same explicit upstream dependency, not hidden work in
this phase.

### No rendering or decision policy

There is no RESPONSE.1 renderer and no DECIDE phase. An explicit decision
requirement can be retained but cannot be fulfilled here. Mixed claim states
remain mixed because no upstream deterministic composition policy exists.

### No live wiring

No Commander, Instant Run, Project Evolution, Workbench, Mixed Mode, planner,
response-generation, patching, or other production path imports or calls
SYNTHESIS.1. It is report-only. The live pipeline still stops after CLAIM.1.

## Recommended next phase

The immediate missing dependency is a separately reviewed proposition-planning
and slot-binding producer that consumes the frozen INPUT.1 structure without
inventing answer content. It must be its own contract and must not be hidden in
SYNTHESIS.1.

After explicit bindings exist, RESPONSE.1 may render `StructuredSynthesis` into
human-readable language only if it preserves every subject, slot, claim status,
gap, semantic basis, and decision marker exactly. A decision phase should be
introduced only if an explicit recommendation request needs a separately
governed policy. Neither future phase is implemented here.

```text
INPUT.1 ... CLAIM.1
    -> SYNTHESIS.1 structured composition
    -> STOP

future: proposition/slot binding producer
future: RESPONSE.1 rendering
optional future: separately governed decision policy
```
