# EVIDENCE.2 — Evidence Set Coverage, Conflict & Independence Contract

- **Date:** 2026-08-25
- **Track:** EVIDENCE
- **Depends on:** EVIDENCE.1 (Acquired Source Verification & Evidence Promotion Contract)
- **Status:** complete, report-only, unwired

## Decision

EVIDENCE.1 answered *what does one acquired source establish about one
proposition*. EVIDENCE.2 owns exactly one transition and nothing beyond it:

```
Proposition + several EVIDENCE.1 results
    ↓  deterministic set description
EvidenceSetAssessment
```

It answers **"what does this evidence set contain?"** and never **"is the
proposition true?"**. There is no verdict field, no confidence, no probability,
no score, no winner and no vote anywhere in the module. CLAIM.1 — which does not
exist — owns proposition assessment.

The invariant the phase exists to hold:

```
Candidate != Acquired Source != Evidence Assessment != Evidence Set != Final Claim
```

## Public contracts

| Module | Contents |
|---|---|
| `core/evidence_set_assessment.py` | `EvidenceSetRequest`, `EvidenceSetRequirements`, `SourceLineageDeclaration`, `EvidenceSetMember`, `RoleCoverage`, `LineageGroup`, `IndependenceAssessment`, `EvidenceSetAssessment`, every bounded vocabulary, the fingerprints, `assess_evidence_set`, `evidence_set_authority`, `evidence_set_guardrails` |

One module, stdlib-only. It imports `core.evidence_verification` (the frozen
EVIDENCE.1 contract) and `core.evidence_requirements` (the frozen role
vocabulary), and nothing else from the project.

## Counting is not weighing

This is the rule the whole phase is built around, and the one the DeepSeek
dogfood failure violated.

```
5 support records + 1 contradiction record  ->  conflicting
```

Not "supported because 5 > 1". There is no majority, no weighted majority, no
support score, no contradiction score, no Bayesian confidence, no Elo and no
averaged analyzer confidence. A static regression asserts that no class field
and no callable in the module has `majority`, `vote`, `winner`, `winning`,
`outweigh`, `tally`, `average` or `score` in its name, and a serialization
regression asserts that no value anywhere in the rendered assessment is a float.

Counts appear only as structural facts — how many records, how many sources, how
many lineage groups — and `record_count_is_evidence_weight: false` says so in
the serialization.

## What arrives, and what never does

EVIDENCE.2 consumes `EvidenceVerificationResult` records through their public
contract, plus four optional supplied artefacts:

| Supplied | Used for | Produced by EVIDENCE.2 |
|---|---|---|
| `NegativeClaimCoverage` | set-level absence coverage | never |
| `CurrentStateReceipt` | set-level currentness | never |
| `SourceLineageDeclaration` | duplication and independence | never |
| `EvidenceSetRequirements` | required-vs-covered roles | never |

It never reads source bytes. `core/content_acquisition.py` is not imported,
`AcquiredSourcePayload` and `BoundedPayloadView` do not appear in the source,
and a static regression asserts both. Hashes and records are enough.

It never reaches an analyzer. Importing `core.evidence_promotion_gate` would
transitively import `core.evidence_analyzer`, so the gate, the analyzer and the
model adapter are all unreachable by import, and `verify_acquired_source`,
`verify_with_bounded_repair`, `adjudicate` and `analyze` are unreachable by
call. A phase whose job is to group already-decided relations must not have a
way to decide one.

## Admission before description

An incoherent set is refused whole rather than described optimistically, the way
EVIDENCE.1 refuses a source whose provenance is already broken. Every fatal
problem is collected first, so a caller sees the whole list at once:

| Inconsistency | Cause |
|---|---|
| `mixed_proposition_binding` | a record bound to a different id, digest, type or scope |
| `record_identity_repeated` | the same re-derived record fingerprint twice |
| `record_not_admissible` | `binding_invalid`, `analysis_invalid` or `unsupported_source` |
| `source_identity_content_conflict` | one identifier, two different content digests |
| `semantic_relation_status_absent` | a record with no analyzer-assessed relation |
| `negative_support_without_coverage` | a hand-built promoted `supports` on an absence with no sufficient coverage |
| `coverage_receipt_not_supplied` | such a record cites coverage the caller did not hand over |
| `coverage_receipt_binding_mismatch` | a coverage receipt for another proposition, or supplied for a positive claim |
| `current_state_receipt_binding_mismatch` | a receipt for another proposition or another source |
| `lineage_declaration_binding_mismatch` | a declaration about a source outside the set |
| `requirements_binding_mismatch` | requirements for another proposition |

Coverage *gaps* are a different thing entirely and never appear here: they live
in the four coverage fields and in `missing_requirements`.

`source_identity_content_conflict` is stricter than the brief asked for, and
deliberately so. Two records naming one path with different bytes make
"one source" ambiguous, which is precisely the ambiguity duplicate and
independence analysis must not guess about.

## Relations are grouped, never regraded

```
supports        -> support_records[]
contradicts     -> contradiction_records[]
insufficient    -> insufficient_records[]
unrelated       -> unrelated_records[]
```

No relation moves. No span is re-read. No model is called. `relation_reinterpreted:
false` appears on every member and `relations_reinterpreted: false` in the
guardrails.

## Conflict states

| State | Meaning |
|---|---|
| `no_directional_evidence` | no `supports` and no `contradicts` |
| `support_only` | directional support, no directional contradiction |
| `contradiction_only` | directional contradiction, no directional support |
| `conflicting` | at least one of each |
| `not_assessed` | the set was refused before partitioning |

The coarse "none" a reader might expect is the union of the first three, exposed
as `NON_CONFLICTING_STATUSES`. None of these is a truth state: `support_only`
means the set holds directional support and nothing pointing the other way. It
does not mean the proposition holds, and no field says it does.

## Role coverage is a different axis from direction

```
role_coverage:
    implementation_authority:  present=true   directional_present=false
    validation_evidence:       present=true   directional_present=true
    configuration_authority:   present=false  directional_present=false
```

`present` and `directional_present` are separate because a source verified as
`implementation_authority` whose relation is `insufficient` **does** discharge
role presence — the set genuinely contains an implementation-authority reading —
and discharges **no** directional support. Collapsing the two is how "we looked
at the implementation" becomes "the implementation says yes".

Two further precisions:

- An `unrelated` record discharges nothing. Its role is reported as
  `unrelated_only`, because a file being acquired and verifying its role is not
  the same as that file bearing on the claim.
- Role requirements are never invented. With no `EvidenceSetRequirements`
  supplied, `role_coverage_status` is `not_applicable` and
  `role_requirements_not_supplied` is recorded as a gap. Supplied requirements
  are bound to the proposition and carry the upstream evidence-requirement
  fingerprint.

`scope_coverage` is separate again and comes from EVIDENCE.1's frozen
`SCOPE_COMPETENT_ROLES`: does the set contain at least one reading by a role
competent for this *kind* of fact? Ten historical notes about a current
implementation claim leave it `incomplete`.

## Duplication, and the asymmetry that defines independence

Identical content digests collapse into one lineage group. So do sources a
supplied declaration marks as `restates`. Nothing else collapses anything — not
a shared directory, not a similar filename, not a similar role.

```
docs/README.md      H1  ┐
docs/README-copy.md H1  ┘  one lineage, two records
docs/other.md       H2     a second lineage
```

The asymmetry is the contract:

| Question | Answerable here? |
|---|---|
| Are these two sources the same content? | yes — digests decide it |
| Are these two sources independently produced? | **no** |

Identical content *proves* duplication. A different digest proves nothing about
origin, so a non-duplicate group is `independence_unknown`. `independent` is
reachable only through a supplied `SourceLineageDeclaration` asserting
`distinct_origin` — the same consume-never-produce shape EVIDENCE.1 uses for
`NegativeClaimCoverage` and `CurrentStateReceipt`. A regression proves that two
records with different paths and different digests and no declaration are never
`independent`.

Identical content wins over a `distinct_origin` note about the same pair: two
sources with the same digest are the same reading, and a note about their
authorship describes who typed them, not whether they corroborate.

`independent_corroboration_unestablished` is recorded whenever support records
exist and fewer than two *declared-independent* lineage groups contribute to
them. In the pipeline as it stands, nothing mints a `distinct_origin`
declaration, so that gap is recorded for every supporting set — which is the
honest reading, not a defect.

### Anti-mirror-tunnel

One upstream hypothesis copied into three derivative artefacts is one lineage
whenever the copies are byte-identical or a declaration exposes the
relationship. The regression is direct: three support records, two sharing a
digest, produce `record_count=3`, `lineage_group_count=2`,
`duplicate_group_count=1`, `independent_group_count=0`. Semantic duplicate
detection is deliberately out of scope: it would need a model, and EVIDENCE.2
calls none.

## Absence still needs coverage

For `negative_existential` propositions:

| Situation | `negative_claim_coverage` |
|---|---|
| positive proposition | `not_applicable` |
| no coverage receipt supplied | `incomplete` |
| receipts disagree on acquisition universe, required roles or status | `inconsistent` |
| at least one supplied receipt is `coverage_sufficient` | `complete` |

Twenty files that say nothing about persistence stay twenty `insufficient`
records. There is no count at which they become support, and no code path that
could promote one.

Two coverage receipts describing different acquisition universes are never added
together into a wider one — that is `inconsistent`, and merging them would
manufacture exactly the confident absence the track exists to prevent.

A counterexample needs none of this. One concrete contradiction against an
absence is grouped, visible, and requires no coverage receipt at all; the set
still emits no `proposition = false`.

## Current-state coverage

For `runtime_behaviour` scopes only, and from supplied receipts only:

| Situation | `current_state_coverage` |
|---|---|
| non-runtime scope | `not_applicable` |
| a member cites no receipt, or cites one not supplied, or cites an unestablished one | `incomplete` |
| two receipts disagree about one source | `inconsistent` |
| every member cites a supplied, established receipt | `complete` |

Nothing inspects a runtime. Nothing mints a receipt.

## Result identity and canonical ordering

`assessment_fingerprint` is a SHA-256 over the assessment's own canonical
identity: the proposition, the ordered member record fingerprints, the coverage
and current-state receipt fingerprints, the lineage declarations and the
supplied requirements identity. No timestamp, no counter, no random token.

Member order is a property of the caller's loop, not of the evidence, so the
request fingerprint is computed over *sorted* collections and members are sorted
by record fingerprint. `[A, B, C]` and `[C, A, B]` produce byte-identical
assessments, and a regression asserts it on the rendered JSON.

## Tamper binding

Every record's identity is re-derived here from its own serialization —
proposition binding, source content digest, every evidence span, the relation,
the role assessments and the semantic assessment marker are all inside the
digest. No caller-supplied fingerprint field is trusted, because none is read.

Two of the tamper cases turn out to be unreachable rather than merely detected,
because EVIDENCE.1's own record refuses to be built that way. That is a stronger
outcome and the regression accepts it explicitly.

## Semantic status survives aggregation

This is a hard invariant and it is enforced structurally rather than by rule.

Every member's relation is `analyzer_assessed` and stays `analyzer_assessed`.
The set-level `VerificationLevels` is EVIDENCE.1's own record type, whose
`DIMENSION_MAX_LEVEL` ceiling makes a deterministically verified semantic
relation *unconstructible*. Ten agreeing analyzer-assessed support records are
ten analyzer-assessed support records; agreement between analyzers is agreement
between analyzers.

The structural dimensions aggregate as a floor: the set is only as
`source_binding` / `citation_integrity` / `role_admissibility` verified as its
weakest member.

## Authority and performed-state separation

One narrow authority, conditional on a describable set:

```
evidence_set_assessment_authority   true only for an assessed set
human_approval_required             always true
```

Everything else is false in every outcome, including the two a reader would most
like to treat as a verdict: `claim_decision_authority` and
`final_claim_authority`. Those two are **properties, not fields** — there is no
construction path that could set them, and a static regression asserts they are
absent from `dataclasses.fields`.

Guardrails record what actually happened — `evidence_records_aggregated`,
`duplicate_analysis_performed`, `role_coverage_assessed`, `conflict_assessed` —
and keep `source_content_read`, `evidence_acquired`, `repository_traversed`,
`model_called`, `claim_decision_performed`, `final_claim_emitted`,
`confidence_computed`, `majority_vote_computed`, `relations_reinterpreted`,
`semantic_status_upgraded`, `coverage_receipts_minted`,
`current_state_receipts_minted` and `lineage_inferred_from_paths` false.

## Bounded regressions

- **Basic sets:** one support, one contradiction, one insufficient, one
  unrelated; support + contradiction is `conflicting`; five supports and one
  contradiction is still `conflicting` with no winner
- **One proposition:** a mixed set and a merely rescoped proposition are both
  `inconsistent_input`
- **Duplication:** the same record twice is refused; two identifiers with one
  digest are one lineage; different digests with no metadata are
  `independence_unknown`; a supplied `restates` declaration collapses two
  lineages; `independent` appears only with a supplied `distinct_origin`
  declaration; a declaration about an absent source is refused; two readings of
  one file are one lineage and two records
- **Role coverage:** an insufficient record discharges presence and not
  direction; validation support plus implementation insufficiency covers both
  roles without reinterpretation; a missing required role is `incomplete`;
  requirements are never invented; an unrelated record discharges nothing
- **Negative claims:** many insufficient sources do not cover an absence; a
  hand-built uncovered support is refused; a covered support is accepted and
  still decides nothing; one counterexample needs no coverage; covered support
  plus a counterexample is `conflicting`; incompatible receipts are
  `inconsistent`; an insufficient receipt does not complete coverage
- **Current state:** missing receipts are `incomplete`; compatible established
  receipts are `complete`; disagreeing receipts are `inconsistent`; a receipt for
  another source is refused
- **Historical / test / manifest:** ten historical notes stay insufficient and
  never outrank one current implementation; three agreeing tests do not establish
  runtime behaviour; a manifest declaration stays insufficient
- **DeepSeek dogfood:** three sets, ending with four duplicated
  "no persistence" documents that collapse to one lineage, produce no support and
  never outvote the SQLite counterexample
- **Determinism:** order-independent fingerprints and byte-identical rendered
  JSON; supplied receipts and requirements move the fingerprint
- **Static:** no `os` / `pathlib` / `glob` / `socket` / `subprocess` / database /
  index / graph / selector / validation / model imports; no traversal; no
  filesystem access; import-time inert; the analyzer and the gate are unreachable;
  the payload contract is not imported; no numeric field; no vote-shaped name;
  nothing in the product imports or calls it

## Not wired

Nothing imports or calls `assess_evidence_set`. EVIDENCE.2 is not wired into
Commander, Instant Run, Project Evolution, Workbench, Mixed Mode, the planner,
the ACQUIRE runtime, CTX.SELECT, patching or final response generation. It is
offline and report-only.

## Upstream regression amended, not weakened

EVIDENCE.1's boundary suite asserted that no production path imports it.
EVIDENCE.2 imports its frozen contract module by design, so that regression now
treats `core/evidence_set_assessment.py` as a downstream contract consumer and
adds a narrower assertion in its place: it binds to `core/evidence_verification.py`,
never imports the gate, the analyzer or the model adapter, and never calls
`verify_acquired_source`, `verify_with_bounded_repair` or `adjudicate`. Every
other production path is still asserted to import and call nothing.

## Known limitations

- **`independent` has no producer.** Nothing upstream mints a `distinct_origin`
  declaration, so in the current pipeline every non-duplicate lineage is
  `independence_unknown` and `independent_corroboration_unestablished` is
  recorded for every supporting set. The state exists so a future lineage-bearing
  phase has somewhere to land; EVIDENCE.2 will never derive it.
- **`duplicate_of` does not reach here.** ACQUIRE.2's inventory carries a
  `duplicate_of` marker, but ACQUIRE.3's frozen `SourceAcquisitionReceipt` does
  not propagate it and EVIDENCE.1's result does not carry it. Until some phase
  threads it through, a caller wanting that signal must restate it as a
  `SourceLineageDeclaration`.
- **Only exact-content duplication is detected.** A paraphrased restatement with
  a different digest and no declaration is `independence_unknown`. Semantic
  duplicate detection would need a model and is out of scope by design.
- **Coverage and current-state receipts still have no producer.** Inherited from
  EVIDENCE.1: absence coverage and currentness are representable, gated and
  consumable, and nothing upstream currently emits them.
- **A refused set describes nothing.** `inconsistent_input` reports the
  inconsistencies and no groupings. A caller that wants a partial description
  must hand over a coherent subset itself; EVIDENCE.2 will not choose which
  records to drop.
- **Set size is bounded at 32 records**, inherited from
  `MAX_INITIAL_SOURCES_CEILING`. A larger evidence set has to be split, and
  splitting it is a decision EVIDENCE.2 does not make.

## Next boundary: CLAIM.1

A bounded proposition assessment over one `EvidenceSetAssessment`. The shape the
set contract already suggests:

- consume one assessed set through its public contract; refuse an
  `inconsistent_input` one outright
- refuse to assess at all when `negative_claim_coverage`, `current_state_coverage`
  or required role coverage is `incomplete` or `inconsistent`
- treat `conflicting` as a terminal state that produces an unresolved claim
  needing human adjudication, never a winner
- keep the claim's own epistemic status bounded by the members': a claim resting
  on analyzer-assessed relations is an analyzer-assessed claim
- emit a categorical claim status with no confidence, and keep
  `human_approval_required` true

Not implemented and not authorized here.
