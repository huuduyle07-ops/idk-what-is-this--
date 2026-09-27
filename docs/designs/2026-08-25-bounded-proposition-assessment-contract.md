# CLAIM.1 — Bounded Proposition Assessment Contract

- **Date:** 2026-08-25
- **Track:** CLAIM
- **Depends on:** EVIDENCE.2 (Evidence Set Coverage, Conflict & Independence Contract)
- **Status:** complete, report-only, unwired

## Decision

EVIDENCE.1 answered *what does one acquired source establish about one
proposition*. EVIDENCE.2 answered *what does this evidence set contain*. CLAIM.1
owns exactly one transition and nothing beyond it:

```
one EVIDENCE.2 EvidenceSetAssessment
    ↓  deterministic claim policy
ClaimAssessment
```

It answers **"given this already-assessed evidence set, what categorical
epistemic status is justified for this proposition?"** and never **"what is
ultimately true?"**.

The invariant the phase exists to hold:

```
evidence assessment != proposition assessment != final truth
                                              != final user-facing answer
```

`supported_by_assessed_evidence` means *the currently admitted,
analyzer-assessed evidence set supports P*. It does not mean P is proven, and
there is no field in the contract that could say it was.

## Public contracts

| Module | Contents |
|---|---|
| `core/claim_assessment.py` | `ClaimAssessmentRequest`, `ClaimRequirements`, `ClaimAssessment`, every bounded vocabulary, the fingerprints, `assess_claim`, `claim_authority`, `claim_guardrails`, `render_claim_assessment_json` |

One module, stdlib-only. It imports `core.evidence_set_assessment` (the frozen
EVIDENCE.2 contract), `core.evidence_verification` (the frozen EVIDENCE.1
contract) and `core.evidence_requirements` (the frozen role vocabulary), and
nothing else from the project.

## Input, and what never arrives

CLAIM.1 consumes exactly two things: one `Proposition` and one
`EvidenceSetAssessment`. It does not consume repository files, acquired payload
bytes, raw analyzer output, candidate inventories or CTX.SELECT output. It does
not re-run EVIDENCE.1, does not reinterpret spans or source roles, and calls no
analyzer or model.

The proposition arrives separately because `EvidenceSetAssessment` carries the
claim's *identity* — id, digest, type, scope — and not its text. CLAIM.1 needs
the text to preserve it, and re-binds the supplied claim to the set by digest
before reading anything.

| Supplied | Used for | Produced by CLAIM.1 |
|---|---|---|
| `Proposition` | claim identity and preserved text | never |
| `EvidenceSetAssessment` | every relation, coverage and lineage fact | never |
| `ClaimRequirements` | required roles, demanded independent corroboration | never |
| `expected_evidence_set_fingerprint` | caller-side tamper binding | never |

## Assessment status vocabulary

Eight categorical values. Every one names a *state of the evidence*, never a
state of the world.

| Status | Means |
|---|---|
| `supported_by_assessed_evidence` | directional support, no contradiction, every gate passed |
| `contradicted_by_assessed_evidence` | directional contradiction and no directional support |
| `conflicting_evidence` | both directions present — terminal, no winner |
| `insufficient_evidence` | no directional evidence, or a support-only set missing required roles or scope competence |
| `coverage_incomplete` | a negative existential whose absence coverage is not complete |
| `current_state_unestablished` | a runtime claim whose current-state coverage is not complete |
| `current_state_inconsistent` | a runtime claim whose current-state receipts disagree |
| `inconsistent_input` | the entry gate refused the set |

`true`, `false`, `likely_true`, `probably_false` and `confidence_high` are
absent on purpose: each would assert something CLAIM.1 has no way to establish.

**Why there is no separate `no_directional_evidence` status.** A set holding one
`insufficient` record and a set holding one `unrelated` record mean the same
thing *for the proposition* — nothing directional was established — and
splitting them would invite a reader to treat one as closer to an answer. The
distinction survives in `conflict_status` and in the reason code
`CLAIM_NO_DIRECTIONAL_EVIDENCE`, where it describes the material rather than the
claim.

**Why `current_state_inconsistent` is its own status.** Disagreeing receipts are
not a broken set — EVIDENCE.2 assessed it fine — and they are not partial
coverage either. Folding them into `current_state_unestablished` would lose the
difference between *nobody said* and *two authorities disagree*, and folding
them into `inconsistent_input` would call a describable set undescribable.

## Deterministic precedence

The whole rule table, in order. There is no scoring anywhere in it.

```
0.  entry gate produced any inconsistency
        -> inconsistent_input                                [terminal]

1.  conflict_status == conflicting
        -> conflicting_evidence                              [terminal]

2.  conflict_status == contradiction_only
        -> contradicted_by_assessed_evidence

3.  conflict_status == support_only:
      a. negative_existential and negative_claim_coverage != complete
             -> coverage_incomplete
      b. runtime scope and current_state_coverage == inconsistent
             -> current_state_inconsistent
      c. runtime scope and current_state_coverage != complete
             -> current_state_unestablished
      d. role_coverage_status not in {complete, not_applicable}
             -> insufficient_evidence
      e. scope_coverage != complete
             -> insufficient_evidence
      f. independent corroboration explicitly demanded and not established
             -> insufficient_evidence
      g. otherwise
             -> supported_by_assessed_evidence

4.  conflict_status == no_directional_evidence
        -> insufficient_evidence
```

Gate order inside step 3 is fixed and a failing set reports the *first* gap
rather than all of them: stacking gaps would suggest a distance-to-truth this
phase does not measure.

Two adjustments to the suggested table, both forced by the frozen upstream
contracts and both documented here:

- **Absence coverage that is `inconsistent`, not merely `incomplete`, is also
  `coverage_incomplete`.** §17's rule is *without complete valid coverage*, and
  two receipts describing different acquisition universes are not complete valid
  coverage. The distinction is preserved in the reason code
  `CLAIM_NEGATIVE_COVERAGE_INCONSISTENT`.
- **The contradiction branch runs before every coverage gate.** EVIDENCE.1
  already blocks *both* directions on a runtime claim without an established
  current-state receipt (`GATE_PROMOTION_BLOCKED_CURRENT_STATE` applies to any
  directional relation), so a contradiction record in the set necessarily had
  its own receipt. Requiring set-wide coverage before acknowledging it would be
  strictly stricter than the frozen EVIDENCE.1 rule, not more honest.

## Conflict is terminal

`conflict_status == conflicting` produces `conflicting_evidence` and stops.

```
5 support records + 1 contradiction record   ->  conflicting_evidence
31 support records + 1 contradiction record  ->  conflicting_evidence
```

Not "supported because 5 > 1". No majority, no weighted majority, no support
score, no role rank, no source rank, no analyzer rank, no recency rule and no
"implementation beats tests" tiebreak. `conflict_adjudication_unavailable` is
recorded as a gap, for a human adjudication phase that does not exist.

## No majority, proved statically

Four static regressions in `tests/test_claim_assessment_boundaries.py` prove
the arithmetic is absent rather than merely unused:

- no class field or callable carries `majority`, `vote`, `winner`, `winning`,
  `outweigh`, `outrank`, `tally`, `average`, `strength` or `score` in its name
- no `sum`, `max`, `min`, `Counter` or `most_common` call anywhere
- **no arithmetic operator anywhere in the source** — not one `+`, `-`, `*` or
  `/`
- **no comparison with a length on both sides**, and a length compared against a
  bound may only be compared to a literal or a module-level maximum

The corroboration test is written with tuple slicing (`independent[1:]`,
`lineages[1:]`) rather than counting for exactly this reason: there is no number
in the module that could be compared against another number.

## Semantic basis survives aggregation

Every member relation arrived `analyzer_assessed` from EVIDENCE.1. Every
ClaimAssessment states `semantic_basis: analyzer_assessed` and
`assessment_basis: gated_analyzer_assessments`.

The invariant is **structural**, not a rule someone could forget:

```python
SEMANTIC_BASES = (BASIS_ANALYZER_ASSESSED, BASIS_NOT_ESTABLISHED)
```

`deterministically_verified` is not in the tuple, so a ClaimAssessment asserting
deterministic semantics does not construct. An assessed claim that does not
state `analyzer_assessed` does not construct either. Twenty agreeing support
records produce one analyzer-assessed supported status.

## Duplication, independence, corroboration

`corroboration_status` is a description of the lineage shape behind the
directional records — never a quantity, never a probability.

| Value | Reached when |
|---|---|
| `none` | there is no directional evidence |
| `duplicate_only` | the directional records collapse to one duplicated lineage |
| `independence_unknown` | anything else short of a declaration |
| `independently_corroborated` | two or more directional lineages EVIDENCE.2 marked `independent` |
| `not_assessed` | the set was refused |

One support plus five byte-identical copies yields **the same
`assessment_status`** as the one real lineage; only the descriptive
corroboration field changes, to `duplicate_only`, with the reason code
`CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN`. There is no `stronger_support`
and no strength scale to put one on.

A different content digest proves nothing about independence, so non-duplicate
lineages stay `independence_unknown`. That is recorded as
`independent_corroboration_unestablished` and **blocks nothing** — because
nothing in the pipeline currently mints a distinct-origin declaration, treating
it as a veto would refuse every positive assessment forever. Independent
corroboration is required only where a supplied `ClaimRequirements` sets
`independent_corroboration_required=True`, which is opt-in and honest about what
switching it on costs.

## Absence, currentness, roles

**Absence still needs coverage.** A `negative_existential` proposition reaches
support only through `negative_claim_coverage == complete`. Six absence
documents are six analyzer-assessed non-directional records; there is no count
at which they become a coverage receipt. One concrete counterexample still
contradicts an absence with no coverage at all, because acknowledging a
counterexample and proving an absence are different questions. Coverage-backed
support plus a counterexample is `conflicting_evidence`, with neither side
chosen.

**Code existing is not code running.** A `runtime_behaviour` proposition reaches
support only through `current_state_coverage == complete`. Four static
implementation files that look like persistence were already downgraded by
EVIDENCE.1 for want of a receipt, and CLAIM.1 does not re-promote them.

**Role presence is not directional support.** EVIDENCE.2 kept `present` and
`directional_present` apart and CLAIM.1 does not merge them. A source verified
as `implementation_authority` whose relation is `insufficient` discharges
required-role coverage and discharges no support: a set holding only that record
is `insufficient_evidence` with `role_coverage_status == complete`. Role
requirements are consumed, never invented: `not_applicable` passes the gate and
is recorded as `role_requirements_not_supplied`.

## The entry gate

Ten fatal inconsistencies, each producing `inconsistent_input` with no
assessment at all. CLAIM.1 does not repair a malformed set, does not reacquire
evidence and does not fall back to a weaker reading.

| Code | Refuses |
|---|---|
| `evidence_set_inconsistent` | a set that refused itself |
| `proposition_binding_mismatch` | a reworded, narrowed, broadened or requalified claim |
| `evidence_set_fingerprint_mismatch` | a supplied expected fingerprint that does not match |
| `member_fingerprint_invalid` | a malformed or repeated member identity |
| `relation_partition_mismatch` | a summary that disagrees with the records it summarises |
| `lineage_membership_mismatch` | a member that does not match its own lineage group |
| `semantic_basis_upgraded` | any semantic status that is not `analyzer_assessed` |
| `upstream_claim_authority_asserted` | a set arriving with claim-decision authority |
| `upstream_guardrail_violated` | an upstream admitting it interpreted, weighed or called a model |
| `evidence_requirement_binding_mismatch` | requirements bound elsewhere or naming roles the set never assessed |

Two of these deserve a note. The **relation partition** is recomputed from the
set's own members rather than read off its summary tuples, so a hand-assembled
assessment whose `support_records` and `insufficient_records` were swapped is
refused rather than adjudicated. And the **upstream declaration** check reads
EVIDENCE.2's own `authority` and `guardrails` blocks: a phase that already
asserted claim-decision authority is not an input, and adjudicating its output
would launder that overstep into a claim.

Coverage *gaps* are a different thing entirely. They are not inconsistencies;
they live in the four coverage fields and in `missing_requirements`.

## Result schema

```
ClaimAssessment:
    assessment_status
    proposition_id, proposition_sha256, proposition_text,
    proposition_type, proposition_scope
    evidence_set_fingerprint
    evidence_set_request_fingerprint
    request_fingerprint
    semantic_basis                  # analyzer_assessed | not_established
    assessment_basis                # gated_analyzer_assessments | not_assessed
    conflict_status
    role_coverage_status, scope_coverage
    negative_claim_coverage, current_state_coverage
    corroboration_status
    directional_record_refs[]       # fingerprints only
    non_directional_record_refs[]   # fingerprints only
    lineage_group_refs[]            # fingerprints only
    missing_requirements[]
    reasons[]
    inconsistencies[]
    assessment_fingerprint          # property
    authority, guardrails           # serialization only
```

There is no `final_answer`, no `recommendation`, no `confidence`, no
`probability`, no `truth_score` and no count of any kind.

**No evidence content.** Evidence is referenced by fingerprint. No source
identifier, no content digest, no path, no excerpt and no span reaches the
result — a regression asserts that no member's `source_identifier` or
`source_content_sha256` appears anywhere in the rendered page.

## Reason codes

Bounded, stable, canonically ordered, no free-form text anywhere — a sentence is
where a verdict hides. Twenty-six codes including
`CLAIM_SUPPORTED_DIRECTIONAL_EVIDENCE`,
`CLAIM_CONTRADICTED_DIRECTIONAL_EVIDENCE`, `CLAIM_CONFLICTING_EVIDENCE`,
`CLAIM_CONFLICT_NOT_ADJUDICATED`, `CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE`,
`CLAIM_REQUIRED_ROLE_COVERAGE_INCOMPLETE`, `CLAIM_NEGATIVE_COVERAGE_REQUIRED`,
`CLAIM_CURRENT_STATE_UNESTABLISHED`,
`CLAIM_INDEPENDENT_CORROBORATION_UNESTABLISHED`,
`CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN`, and the four standing denials
`CLAIM_NO_MAJORITY_COMPUTED`, `CLAIM_NO_CONFIDENCE_COMPUTED`,
`CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED`, `CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED`.

## Authority

`claim_assessment_authority` is the single narrow authority, and it is true only
for a usable set. Everything else is false, in every outcome:

```
evidence_set_assessment, evidence_acquisition, evidence_verification,
evidence_promotion, conflict_adjudication, repository_read,
repository_traversal, external_search, web_fetch, context_selection,
indexing, graph, validation_execution, command_execution, worker_launch,
repository_write, patch, planning, routing, model_selection,
provider_selection, project_evolution, response_synthesis, final_claim
```

`human_approval_required` is always true — because the semantic relations
underneath every status originate from analyzer assessments, and a human
reviewer needs to see the proposition, the support/contradiction condition, the
coverage, the conflict and the duplication without the system pretending it
proved semantic truth deterministically.

`final_claim_authority`, `objective_truth_asserted` and
`response_synthesis_performed` are read-only **properties** returning false,
absent from `dataclasses.fields`, so no construction path can set them —
including for the outcome a reader would most like to treat as an answer.

## Determinism

The same `EvidenceSetAssessment` yields a byte-identical `ClaimAssessment`.
Member order in the upstream set does not reach the claim; there is no clock, no
counter, no random token, no filesystem and no machine state. A static
regression forbids `time`, `random` and `uuid` by import and by call.

`assessment_fingerprint` binds the preserved proposition, the EVIDENCE.2
assessment fingerprint, the EVIDENCE.2 request fingerprint, the claim request
fingerprint, the status, the basis, every coverage reading and every ordered
reference.

## Static inertness and no live wiring

No filesystem, no traversal, no network, no database, no index, no graph, no
selector, no validation execution, no subprocess, no model. Importing the
EVIDENCE.1 promotion gate would transitively import an analyzer, so the gate,
the analyzer and the model adapter are unreachable by import, and
`verify_acquired_source`, `verify_with_bounded_repair`, `adjudicate`, `analyze`
and `assess_evidence_set` are unreachable by call. Import-time inertness is
proved: only definitions run when the module loads.

`core/claim_assessment.py` is imported and called by nothing. It is not wired
into final response generation, Commander, Instant Run, Project Evolution, the
Workbench, Mixed Mode, the planner or patching.

## Upstream regressions amended, not weakened

EVIDENCE.1 and EVIDENCE.2 each asserted that no production path imports them.
CLAIM.1 imports both frozen contract modules by design, so each live-wiring
regression now treats `core/claim_assessment.py` as a downstream contract
consumer and adds a narrower assertion in its place — it binds to the contract
module, never imports the gate, analyzer, adapter or acquisition payload
contract, and never calls the gate or aggregator entry points. Every other
production path is still asserted to import and call nothing.

## DeepSeek dogfood

The original failure class, reproduced at claim level for
*"DeepSeek Harness has no session persistence."*

| Set | Content | Claim status |
|---|---|---|
| A | unrelated and insufficient sources only | `insufficient_evidence`, coverage absent |
| B | four byte-identical absence documents | `insufficient_evidence` — one lineage, still no coverage |
| C | one concrete SQLite implementation | `contradicted_by_assessed_evidence`, no absence coverage required |
| D | valid absence coverage + support + the SQLite counterexample | `conflicting_evidence`, no winner |

The duplicated documents never outvote the counterexample. No final claim, no
confidence and no truth value is emitted in any of the four.

## Known limitations

- **No conflict adjudication.** `conflicting_evidence` is where the pipeline
  stops today. Resolving it needs an authority that can weigh sources, and no
  such authority exists.
- **Independence is effectively unreachable.** Nothing mints a distinct-origin
  declaration, so `independently_corroborated` is reachable only in tests that
  hand-supply one.
- **`member_fingerprint_invalid` is defensive.** `EvidenceSetMember` refuses a
  malformed or repeated fingerprint at construction, so the check exists for a
  duck-typed or subclassed upstream rather than for anything EVIDENCE.2 emits.
- **Negative coverage that is `incomplete` with support present is unreachable
  through the honest path.** EVIDENCE.1 blocks an uncovered absence support and
  EVIDENCE.2 refuses a hand-built one, so the reachable failure is
  `inconsistent` coverage. Both are covered by regressions.
- **One proposition only.** There is no field anywhere that accepts a second.

## Recommended next phase

SYNTHESIS.1 should consume several bounded `ClaimAssessment` records through
their public contract, refuse any that is `inconsistent_input`, present
conflicting and coverage-blocked propositions as unresolved rather than
resolving them, preserve each claim's analyzer-assessed semantic basis and its
recorded gaps into whatever it renders, keep the answer bounded by the
propositions actually assessed rather than inferring new ones, and still emit no
confidence and no objective truth. It is not implemented or authorized here.

## The pipeline, as it now stands

```
ACQUIRE.3    exact acquired source bytes
    ↓
EVIDENCE.1   one source vs one proposition — deterministic binding,
             citation and role verification; analyzer-assessed relation
    ↓
EVIDENCE.2   set composition, coverage, conflict, duplication, independence
    ↓
CLAIM.1      bounded proposition assessment
    ↓
STOP
```
