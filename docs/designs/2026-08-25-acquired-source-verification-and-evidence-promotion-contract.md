# EVIDENCE.1 — Acquired Source Verification & Evidence Promotion Contract

- **Date:** 2026-08-25
- **Track:** EVIDENCE
- **Depends on:** ACQUIRE.3 (Bounded Content Acquisition & Source Receipt)
- **Status:** complete, report-only, unwired — **closed / frozen** at the semantic-assessment provenance amendment

## Decision

ACQUIRE.3 established what bytes were acquired and bound them to a tamper-evident
receipt, while insisting that an acquired source is `unverified` with authority
`not_verified`. EVIDENCE.1 owns exactly one transition and nothing beyond it:

```
Acquired Source
    ↓  proposition-bound verification
Verified Evidence / Contradiction / Insufficient / Unrelated
```

It answers two separate questions about one acquired source:

1. **Source role verification** — does this content actually satisfy one of the
   evidence roles it was acquired for?
2. **Proposition relationship** — relative to one supplied proposition, does the
   material `support`, `contradict`, provide `insufficient` evidence, or have no
   relevant relationship?

These are different gates. A file may verify as `validation_evidence` and be
`insufficient` for "runtime persistence uses SQLite". A file may verify as
`implementation_authority` and `contradict` the claim it was acquired to check.

The invariant the whole phase exists to hold:

```
Candidate != Acquired Source != Verified Evidence != Supported Claim
```

## Public contracts

| Module | Contents |
|---|---|
| `core/evidence_verification.py` | `Proposition`, `EvidenceVerificationRequest`, `NegativeClaimCoverage`, `CurrentStateReceipt`, `BoundedPayloadView`, `EvidenceSpan` / `EvidenceSpanRef`, `RoleAssessment`, `EvidenceVerificationProposal`, `VerificationLevels`, `VerifiedEvidence`, `EvidenceVerificationResult`, every bounded vocabulary, the fingerprints, `verification_authority`, `verification_guardrails` |
| `core/evidence_analyzer.py` | `EvidenceAnalyzer` protocol, `StaticEvidenceAnalyzer`, `ScriptedEvidenceAnalyzer`, the analyzer exception hierarchy |
| `core/evidence_promotion_gate.py` | `binding_inconsistencies`, `proposal_defects`, `adjudicate`, `verify_acquired_source`, `verify_with_bounded_repair` |
| `core/evidence_analyzer_adapter.py` | `EvidenceModelClient` protocol, strict response parsing, `EvidenceAnalyzerModelAdapter`, `ScriptedEvidenceModelClient`, the source-disclosure policy |

The first three modules are the *pure decision path*. The fourth is an optional
boundary a caller may plug a model into; a static regression proves the gate
cannot reach it.

## The proposition is supplied, never invented

`EvidenceVerificationRequest` cannot be constructed without a `Proposition`, and
a `Proposition` cannot be constructed without an identifier, text, a bounded
type and a bounded scope. Its `proposition_sha256` is computed over all four
together, so every way of tampering with the claim changes the digest the gate
holds:

```
reworded entity        -> different digest
added/removed qualifier -> different digest
widened scope          -> different digest
flipped type           -> different digest
```

There is no field anywhere in the module in which an analyzer could write a
*different* proposition. `EVIDENCE.1` never reads content and asks "what claims
could I make from this?".

## Proposition types and scopes

Two types, deliberately:

| Type | Established by |
|---|---|
| `positive` | an instance |
| `negative_existential` | coverage, never an instance |

Seven scopes, each earning its place by having a different answer to *which
verified role could establish this kind of fact at all*:

| Scope | Competent verified role |
|---|---|
| `implementation_state` | `implementation_authority` |
| `interface_capability` | `interface_contract` |
| `configuration_declaration` | `configuration_authority` |
| `validation_expectation` | `validation_evidence` |
| `documented_architecture` | `architecture_description` |
| `historical_intent` | `historical_context` |
| `runtime_behaviour` | `implementation_authority` **plus a current-state receipt** |

`supplied_material`, `hypothesis_support` and `current_external_authority` appear
in no entry. Supplied material and hypotheses corroborate and illustrate;
external authority describes the world outside the repository, and ACQUIRE.3
acquires no external bytes to verify.

Type and scope are supplied by the deterministic caller. An analyzer never
chooses either, and unknown values are refused at construction.

## The competence table is the epistemic spine

A verified role outside a scope's entry cannot move that proposition in *either*
direction. This is not modesty applied loosely — it is the absence of a table
entry, and it is what makes the whole distinction matrix fall out:

| Source | Proposition scope | Result |
|---|---|---|
| interface with `save_session()` | `implementation_state` | `insufficient` |
| manifest declaring `sqlite-utils` | `implementation_state` | `insufficient` |
| manifest declaring `sqlite-utils` | `configuration_declaration` | `supports` |
| test asserting persistence | `runtime_behaviour` | `insufficient` |
| test asserting persistence | `validation_expectation` | `supports` / `contradicts` |
| rejected design note naming SQLite | `implementation_state` | `insufficient` |
| rejected design note naming SQLite | `historical_intent` | `supports` |

A downgrade names itself: `relation_downgraded_role_not_competent`. It never
silently becomes `insufficient`.

## Absence needs coverage; a counterexample does not

Supporting `"DeepSeek Harness has no session persistence."` requires a supplied
`NegativeClaimCoverage` that:

- binds the same `proposition_id` **and** `proposition_sha256`
- binds the same `acquisition_request_fingerprint` and `candidate_pool_fingerprint`
  the source's own ACQUIRE.3 `SourceBinding` carries
- is `coverage_sufficient`, leaves `uncovered_requirements` empty
- names this source's acquisition-receipt fingerprint

Without all of that, the gate downgrades `supports` to `insufficient` with
`promotion_blocked_negative_coverage` and status `coverage_required` — even when
the analyzer asserted `supports` with a perfectly valid span.

EVIDENCE.1 cannot mint the coverage it needs. It has no traversal, no candidate
access and no acquisition, so "was the space searched?" is a question it can only
be *told* the answer to. Insufficiency is reported, not solved.

Contradiction is asymmetric on purpose: one concrete implementation that opens
SQLite refutes a universal negative, and no coverage receipt is needed for that.

## Code existing is not code running

A `runtime_behaviour` scope requires a supplied `CurrentStateReceipt` in **both**
directions. Implementation content proves that code exists; whether it is
reachable, configured, deployed or executed are four further facts ACQUIRE.3 did
not establish, and reading bytes cannot establish them either. Without the
receipt the gate reports `insufficient` with
`promotion_blocked_current_state_receipt`.

The symmetry is the honest reading: an in-memory store contradicts a runtime
claim only if that store is the current one.

## Binding gate, before any analysis

`verify_acquired_source` re-derives every binding from scratch before an analyzer
sees a byte:

- payload bytes are re-hashed and compared to payload, receipt and request
- byte count matches the payload, the receipt and `len(content)`
- candidate identifier matches across payload, receipt and request binding
- the ACQUIRE.3 `SourceBinding` is compared field by field
- the receipt is re-fingerprinted against `acquisition_receipt_fingerprint`
- `acquisition_status == acquired`, `verification_status == unverified`,
  `authority_status == not_verified`
- coverage and current-state receipts bind the same claim, source and digest

Any mismatch is `binding_invalid`, no analyzer is called, and nothing is
promoted. The regression asserts `analyzer.call_count == 0`.

The payload is authoritative for content identity. EVIDENCE.1 never reopens the
path — the verdict is bound to the bytes ACQUIRE.3 acquired, not to whatever is
on disk now, and a test writes different bytes to disk to prove it.

## Spans are bytes somebody read

Every `supports` and `contradicts` must cite bounded spans, and the gate
recomputes each digest from the acquired payload:

| Bound | Value |
|---|---|
| spans per proposal | 8 |
| bytes per span | 4,096 |
| total cited bytes | 16,384 |
| span range | `0 <= start < end <= len(payload)` |

An optional `quoted_text` is verified byte-exactly against the cited range and
then **discarded** — quotes are checked, never kept.

This is the structural answer to the original DeepSeek invented-symbol failure.
`PluginKernel`, `TrajectoryManager` and `StorageProvider` are not in the payload,
so no byte range produces a digest that matches a citation of them. Analyzer
reasons are enum codes rather than prose, so a hallucinated identifier also has
nowhere to be written down.

## Analyzer boundary

```
analyzer proposes -> deterministic gate validates -> promotion or refusal
```

The proposal may carry role status, relation, spans and bounded reason codes. It
may not alter the proposition, name a different source, invent a role, request
another file, search anything, call a tool, choose a provider, set an authority
flag, or promote itself. Most of those are not rules to follow:
`EvidenceVerificationProposal` has no field to write them in.

Two analyzers ship, and neither needs a model. `StaticEvidenceAnalyzer` drives
the entire gate from literal byte markers, so every span it cites is a range it
genuinely found. `ScriptedEvidenceAnalyzer` replays hostile proposals so the gate
can be tested against an analyzer that lies.

The optional model adapter parses strictly: unknown keys, forbidden authority
keys, and any `confidence` / `probability` / `score` / `likelihood` fail the
response closed. Enum *order* is normalized because order carries no meaning in
this schema; membership never is. A single bounded repair may be attempted once,
aimed at the gate's own defect list, explicitly told not to change its findings —
never "think harder", never a second model.

## Disclosure and provider boundaries

Acquired source content is repository content. A client must declare its
`locality`; an undeclared client is treated as cloud and refused. Sending content
to a cloud model requires an explicit `cloud_disclosure_approved` policy, and a
request carrying `local_analysis_only` refuses a cloud analyzer regardless.

That INPUT.2 uses a hosted model for intake semantics grants nothing here: intake
text and repository bytes are different material.

EVIDENCE.1 ships no live transport at all — a protocol and a scripted offline
client. One configured analyzer, one call, no escalation and no failover.

## Result and promotion

`EvidenceVerificationResult` records every outcome:

| Status | Promotes |
|---|---|
| `verified` | yes — `relation = supports` |
| `contradicted` | yes — `relation = contradicts` |
| `insufficient` | no |
| `unrelated` | no |
| `coverage_required` | no |
| `analysis_invalid` | no |
| `binding_invalid` | no |
| `unsupported_source` | no |

`VerifiedEvidence` exists only for the two directional relations and only through
the gate. Its `evidence_id` is a fingerprint over its own canonical identity — no
timestamp, no counter, no random token — so the same inputs always produce the
same record.

`verified` describes the *quality and binding* of the assessment.
`supports` / `contradicts` describe *direction*. A contradiction that survives
every gate is exactly as verified as a supporting one, and keeping the two axes
apart is what stops a skeptical analysis from quietly becoming a confirming one.

## Verification levels: what was proven and what was assessed

This is the closure amendment, and it exists because the phase was one reading
away from laundering a judgement into a proof.

Every deterministic check in the gate can pass — the bytes are the acquired
bytes, the span re-hashes to the range it names, the role was expected and is
competent for the scope — while the cited material still fails to establish the
proposition:

```
Proposition: "Session state survives process restart."
Span:        sqlite3.connect("sessions.db")
```

The span is real. The source really is implementation authority. One line is
still not that claim. Structural validity around a semantic judgement is not
evidence for the judgement, and a record that says only `relation = supports`
invites exactly that inference.

`VerificationLevels` therefore travels on every `EvidenceVerificationResult` and
on every promoted `VerifiedEvidence`, naming four dimensions separately:

| Dimension | Established by | Level it may hold |
|---|---|---|
| `source_binding` | re-hashing bytes, re-fingerprinting the receipt | `deterministically_verified` |
| `citation_integrity` | re-hashing every cited span against the payload | `deterministically_verified` |
| `role_admissibility` | expected-role subset plus the competence table | `deterministically_verified` |
| `semantic_relation` | an analyzer's proposal, accepted through the gate | `analyzer_assessed` |

`DIMENSION_MAX_LEVEL` gives each dimension exactly one level besides
`not_established`, and `VerificationLevels.__post_init__` enforces it. The
consequence is structural rather than documentary:

```
VerificationLevels(semantic_relation="deterministically_verified")  -> ValueError
VerificationLevels(source_binding="analyzer_assessed")              -> ValueError
```

There is no record in the phase that can state a deterministically proven
semantic relation, so no downstream reader can find one to trust.

`not_established` is not a failure value. It is the honest reading for a
dimension nothing settled: a `binding_invalid` refusal cited no span and
proposed no relation, so three of its four dimensions are `not_established` and
the fourth records whether the binding gate itself passed.

### What `VerifiedEvidence` means

Precisely four things, and they are the four dimensions:

> **VerifiedEvidence** = a *tamper-bound, proposition-bound, citation-bound,
> role-admissible* evidence assessment.

It does **not** mean the proposition was proven true, and it is not ground
truth. The name is kept — it is public and downstream code binds to it — and its
semantics are now written into the class docstring, the design record and the
registry notes rather than left to be inferred.

### Attribution without vendor authority

The semantic relation is attributable to the exact proposal it came from:
`analyzer_proposal_fingerprint`, already carried by both records, plus
`semantic_relation_assessed_by = analyzer_proposal`. Provider and model names are
*not* required anywhere in the record. `analyzer_name` remains optional
telemetry. Naming a vendor would turn a brand into an epistemic warrant, and the
fingerprint already answers the only useful question: which assessment path
produced this relation.

### Role and relation stay uncoupled

The new marker is deliberately orthogonal to role verification. Both of these
remain ordinary, valid records:

```
verified_role = implementation_authority   relation = insufficient
verified_role = validation_evidence        relation = contradicts
```

`role_admissibility = deterministically_verified` and
`semantic_relation = analyzer_assessed` are simultaneously true of both, because
they answer different questions.

### Compatibility

Additive. No field was renamed or removed, no vocabulary shrank, and no gate rule
changed — the whole pre-existing 145-test EVIDENCE.1 suite passes unmodified.
`VerifiedEvidence` gained one required field (only the gate constructs one) and
`EvidenceVerificationResult` gained one defaulted field. Because the serialized
shape of those two records changed, their schema versions moved to
`evidence_1_verified_evidence_v2` and `evidence_1_verification_result_v2`;
`Proposition`, `EvidenceVerificationRequest`, `NegativeClaimCoverage`,
`CurrentStateReceipt` and `EvidenceVerificationProposal` are untouched at `_v1`.
`evidence_id` values change, because identity now covers the levels block.

## No content in receipts

Spans are byte ranges and digests. A canary regression embeds a secret token in
the payload and asserts that neither the serialized result nor the promoted
`VerifiedEvidence` record contains the token or any identifier from the source
text, and that `source_content_serialized` is `false`.

## No claim synthesis

One proposition, one source, one result. Several results may be serialized side
by side with `aggregated`, `majority_computed` and `confidence_computed`
explicitly `false`. No majority, no weighted support, no aggregate confidence, no
final truth state. Combining independently verified records is EVIDENCE.2 /
CLAIM.1's job, and doing it badly is precisely how three partial readings became
one confident architectural claim.

## Authority and performed-state separation

Narrow and conditional:

```
evidence_verification_authority   true only for a valid verification operation
evidence_promotion_authority      true only when the gate actually promoted
human_approval_required           always true
```

Everything operational is false: repository read, traversal, external search, web
fetch, acquisition, context selection, indexing, graph, validation execution,
command execution, worker launch, repository write, patch, planning, routing,
provider selection, model selection, project evolution, claim synthesis and final
claim authority.

Guardrails record what actually happened —
`source_content_analyzed`, `evidence_verification_performed`, `model_called` —
and keep `provider_selected_by_evidence_layer` false, because the caller chose
the provider before verification started.

## Bounded regressions

- **Binding:** valid pair proceeds; digest mismatch, receipt-fingerprint
  mismatch, proposition-digest mutation, identifier mismatch, widened provenance
  chain, mis-bound coverage and mis-bound currentness all fail closed
- **Role:** implementation content verifies; a placeholder classified as
  implementation is rejected; a test verifies `validation_evidence` and gains no
  implementation role; a doc verifies `architecture_description` only; a rejected
  design verifies `historical_context` only
- **Positive claims:** implementation supports; interface insufficient; manifest
  insufficient for a persistence claim and supporting for a declaration claim;
  incompatible implementation contradicts; a source that never mentions the
  mechanism does not
- **Negative existential:** one source cannot support absence; an analyzer
  asserting `supports` without coverage is downgraded; insufficient coverage and
  coverage that omits this source are both refused; one counterexample
  contradicts without coverage; valid coverage makes support eligible
- **Distinctions:** verified implementation + insufficient; verified validation
  evidence + contradicts; historical, manifest and test sources against
  current/runtime claims
- **Spans:** valid, out-of-range, wrong digest, zero length, too many, over
  budget, missing supporting span, missing contradicting span, lying quote,
  invented symbol, invented source, invented role
- **Adversarial analyzer:** twelve overreach attempts, each failing closed
- **Anti-DeepSeek:** the negative architecture claim cannot be confirmed from one
  file, and is contradicted by one real implementation
- **Static:** no `os` / `pathlib` / `glob` / `socket` / `subprocess` / database /
  index / graph / selector / validation / model imports across all four modules;
  no traversal; no filesystem access; import-time inert; the gate cannot reach
  the model boundary; nothing in the product imports or calls it; no source file
  contains any spelling of a proven-semantic-truth field
- **Semantic provenance** (`tests/test_evidence_semantic_provenance.py`): the
  ceiling table refuses both a deterministically verified semantic relation and
  an analyzer-vouched digest; supports, contradicts, insufficient, unrelated and
  binding refusals each carry the right levels; a promoted record cannot be
  hand-built without an assessed relation or with a missing deterministic
  dimension; no serialization contains `claim_proven`, `semantic_truth_verified`,
  `proposition_verified_true` or `ground_truth`; changing the proposal rebinds the
  semantics and moves no source, span, receipt or request identity; the negative
  existential coverage rule and the current-state rule are re-asserted unchanged

## Registry limitation

ROAD.1 schema v1 has no field distinguishing an optional caller-supplied model
analyzer from a phase that calls a model itself. EVIDENCE.1 ships no live
transport — only a protocol and a scripted offline client — so
`model_calls_allowed=false` and `network_allowed=false` are exact for everything
in this phase and for its whole test suite. A caller supplying its own client
would be making that call under its own authority and under the disclosure policy
above. `writes_real_repo=false` records that no repository content is modified.
ROAD.1 registry validation and ROAD.2 phase picking execute nothing.

## Not wired

Nothing imports or calls `verify_acquired_source`. EVIDENCE.1 is not wired into
Commander, Instant Run, Project Evolution, Workbench, Mixed Mode, the ACQUIRE.3
runtime, the planner, CTX.SELECT, patching or final response generation. It is
offline and report-only.

## Known limitations

- **Analyzer quality is not verified.** The gate proves that a citation was read
  and that a role could establish a scope. It cannot prove that a well-formed,
  competently-cited `supports` is *correct* — an analyzer that misreads a real
  span still produces a structurally valid proposal. That is a limit of any
  proposer/gate architecture, and the reason `human_approval_required` stays true.
  Since the closure amendment the limit is *stated in the record* rather than only
  in this document: `semantic_relation = analyzer_assessed` is the phase saying so
  in every result it emits.
- **Reasoning from omission is only structurally discouraged.** The static
  analyzer has no absence rule and the model instruction forbids it, but a model
  that concludes `contradicts` from omission while citing a genuine span passes
  the span gate. The competence table and the coverage rule bound the damage;
  they do not detect the reasoning.
- **One competent role per scope.** The table is deliberately strict. Some real
  claims are jointly established by an interface plus an implementation, and
  EVIDENCE.1 has no way to express that — each source is verified alone.
- **Current-state receipts have no producer.** Nothing in the repository mints a
  `CurrentStateReceipt` yet, so `runtime_behaviour` claims are in practice always
  `insufficient` until some later phase can establish deployment truth.
- **Coverage receipts have no producer either.** Same shape of gap: supporting an
  absence is representable and gated, but nothing upstream currently emits the
  coverage that would unlock it.
- **Non-UTF-8 payloads cite bytes but cannot quote.** Spans still bind by digest;
  only the optional `quoted_text` cross-check is unavailable.
- **Direct-context sources cannot be verified.** ACQUIRE.3 direct context is a
  reference with no bytes, so there is nothing for EVIDENCE.1 to analyze.

## Next boundary: EVIDENCE.2 / CLAIM.1

Combining several independently verified records for one proposition: handling
conflict between supporting and contradicting sources, reasoning about coverage
across a *set* rather than a source, and producing a bounded claim assessment.
Not implemented and not authorized here.
