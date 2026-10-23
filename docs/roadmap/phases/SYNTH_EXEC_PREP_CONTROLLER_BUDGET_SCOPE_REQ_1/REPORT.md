# SYNTH.EXEC.PREP.CONTROLLER.BUDGET.SCOPE.REQ.1

**SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_COMPLETE**

The cumulative preparation-capture interval is now explicitly defined without
changing the 8192-byte cap or protocol schema. This is a new additive requirement
clarification. The historical contract was underspecified for this newly measured
budget question; its wording and the old proof outcome remain unchanged.

The selected semantic scope is **A: the preparation EFFECT attempt**, one fixed
materialize-then-compile attempt. This does not include the whole retained
workspace readiness lifecycle. The choice follows the two non-interchangeable
effect facets, independent workspace eligibility/readiness, optional handoff, and
the explicit `cleanup_is_preparation=false` rule. It was not chosen by numerical
fit, and does not claim the historical text already uniquely defined these byte
events.

## Exact counter events

Open both counters at zero when the preparation owning boundary records the
authenticated single-operation admission for the already-spent original
materialization facet, **before dispatching the
MATERIALIZE_EXACT_SCENARIO_SOURCE request**. Recording that admission is the
single counter-origin event; facet spending precedes it. No cross-owner atomic
transaction is claimed. This admits the one-shot effect attempt. The earlier mandatory empty
observation is workspace eligibility evidence. The counter origin is justified
by this effect boundary independently of the deadline origin. Do not restart at
the controller's final local checks, first response byte, compile admission or
any observation.

For a successful attempt, close capture at **the final physical byte of the
complete terminal COMPILE_EXACT_SCENARIO response frame**, including actual
framing and all mandatory workspace state, compiler identity, captures/reaping and
class metadata. Success additionally requires a complete valid `COMPLETE`
response. Compiler exit, a parser reaching payload end before full frame capture,
host receipt authentication, a fresh readiness observation, handoff and cleanup
are not the successful endpoint. No effect evidence can be delayed, chunked or
moved into those subsequent lifecycle exchanges to evade the cap.

For a failed attempt, the endpoint is ordinary-response drain termination. With
no ordinary response pending, the recorded irrevocable terminal attempt-abort
event closes capture. With a response pending, the first of complete final
ordinary response capture, observed terminal channel closure/loss, or the
original 10000ms hard preparation deadline closes it. This covers materialization
failure/rejection, inability to admit compilation, partial/invalid responses,
timeout, overflow and cleanup preemption. Preserve every observed ordinary byte
and truthful incomplete/overflow evidence; never fabricate the missing response
or reopen the spent attempt. A terminal failed epoch cannot publish success.

The cleanup barrier immediately withdraws readiness but does **not** erase the
remaining bytes of an already-admitted ordinary response. That suffix still
belongs to failed preparation capture. Separately identifiable cleanup frames
retain cleanup membership even while the ordinary response remains pending.
Neither cancellation nor drain grants a new deadline: the shared 5000ms deadline
and original 10000ms hard bound remain unchanged.

## Message membership and independent bounds

The [normative table](normative_table.md) explicitly classifies initial empty
observation, materialization, compilation, both embedded states, observations
inside the effect attempt, fresh prepared-state observation, receipt
authentication, handoff, cleanup controls, outer removal, independent absence and
host cleanup composition. The [machine-readable requirement](requirement.json)
contains the same table, exact events, source evidence and additive metadata.

Initial `OBSERVE_EMPTY_WORKSPACE` request and response are
`OUTSIDE_PREPARATION_CAPTURE_WITH_SEPARATE_BOUND`. They establish workspace
eligibility before the preparation effect is admitted. Any observation invoked
inside the still-open effect attempt is inside the cumulative cap and also
retains its observation bounds. It cannot reset the cap.

The mandatory new complete challenged observation of prepared current state after
the compile response is
`OUTSIDE_PREPARATION_CAPTURE_WITH_SEPARATE_BOUND`. Its owner/lifecycle class is
**workspace current-liveness/readiness evidence**: it re-establishes current
eligibility after the effects rather than exercising a third preparation facet.
Mutation poststate remains operation evidence, never current readiness. A fresh
challenged `OBSERVE_*` remains mandatory before readiness or handoff.
`OBSERVE_CURRENT_WORKSPACE` can serve the prepared-current-state position before
an initial receipt; `OBSERVE_PREPARED_ARTIFACTS` requires the original receipt and
its existing predicates. No circular pre-receipt requirement or new receipt
ordering rule is introduced.

Each outside observation retains the frozen 5000ms observation timeout, 10000ms
outer timeout, request and response frame ceilings of 8192, work entries 3, tmp
entries 0, process tasks 128, regular-file bytes 33007, writer records 128, writer
handles 128 and mount records 2. Evidence must be full and nontruncated. Missing
reviewed finite retention policy denies readiness; separate per-frame bounds do
not authorize indefinitely repeated observations or retention. Those frame
ceilings do not independently bound arbitrary stderr. There is no free
diagnostic channel: unexpected/nonprotocol output fails closed, and any future
transport must prove finite capture bounds for all outer channels before
operational eligibility. No new universal stderr limit is invented here.

Receipt authentication is preparation-owner evidence in the host process. The
frozen schema defines no additional controller receipt frame. It does not add
the already-serialized effect metadata to stdout a second time or establish
consumer readiness. A future serialization needs its actual bounded channel
accounting.

`PREPARE_EXCLUSIVE_HANDOFF` is outside preparation capture, in the retained-session
and handoff lifecycle, with the existing observation bounds. It is not required
for preparation eligibility. Future consumer execution/capture scope remains
unresolved; no consumer authority is supplied. Handoff activation remains
`PROOF_UNRESOLVED`.

## Cleanup and safety capacity

`BEGIN_CLEANUP`, `CLEANUP_AND_REPORT`, outer terminate/remove, and outer independent
absence evidence are outside the preparation cap under separate cleanup bounds,
including when cleanup preempts an active attempt. Cleanup is mandatory and is
not preparation. Its admission cannot depend on readiness, runtime `ISSUED`, an
unspent facet, a live inner challenge, or unused normal effect capture capacity.

The frozen cleanup profile remains 10000ms outer timeout, response at most 8192
bytes, no automatic retry, and bounded exact-original-identity explicit retry
only. Request frames retain the universal 8192 ceiling. Each independent outer
custodian invocation retains its fixed 10000ms deadline and at-most-8192-byte
response. Preserve exact immutable targeting, provenance, permanent readiness
withdrawal and truthful unresolved components. Removal and absence cannot stand
in for lost child reaping or capture EOF.

Before ordinary admission, a future transport must guarantee independent or
reserved capacity for both bounded cleanup exchanges and outer fallback. A
successful preparation effect using all 8192 normal bytes cannot spend that
capacity. If the channel cannot guarantee it, ordinary admission fails. During
preemption, finishing an already-started ordinary response still consumes its
ordinary allowance; channel/quota failure must leave independent outer teardown
available. This freezes the required separation without implementing it or
selecting a channel.

The unaccepted Candidate A profile remains conditional: 65536 bytes per direction
and 64 requests per retained session including cleanup, two protected cleanup
request slots plus bounded cleanup/error response capacity, 30000ms retained
lifetime, 20000ms work cutoff and 10000ms cleanup reserve. These are not universal
selected architecture limits. Ordinary traffic cannot consume the candidate's
reserves. Its larger session ceiling never increases the preparation cap.

## Physical streams

Controller stdin requests, stdout responses and stderr remain separate. A
request's semantic membership does not make its stdin bytes stdout or stderr;
no new cumulative 8192 stdin cap or sum of both directions is introduced. Actual
headers count in the physical direction they occupy. Candidate A's four-byte
prefix remains conditional, including the whole-frame maximum of 8192; it is
not assigned to the unselected outer-custodian channel.

Every counted response includes its complete embedded workspace state once.
All partial, malformed, unexpected and unframed captured bytes during the effect
epoch count and deny success. Untagged/shared stderr during that epoch is charged
to preparation unless independently attributable to a separately bounded
lifecycle channel. Missing labels cannot create an exemption. An exhausted
ordinary allowance fails preparation while independent bounded cleanup proceeds.

Compiler child stdout and stderr retain their separate 2048-byte bounds and must
be empty on success. Their metadata is already in the compile response; do not
add it twice. Host receipt authentication and provenance-preserving cleanup
composition are in-process evidence, not extra inner wire responses. A physical
byte can be checked against both an attempt and an enclosing session ceiling,
but is never added twice within one ledger. Preparation attempt, controller
session and retained workspace lifetime remain distinct.

## Additive interpretation and proof consequence

`requirement.json#/clarifications` records the new requirement ID, each historical
artifact/key, its exact old ambiguous wording/value, new interpretation, limited
scope, reason and `historical_bytes_preserved=true`. `#/evidence` retains exact
JSON pointers, original values, source byte sizes and SHA256 hashes. The key
architectural sources are PREP closure's fixed attempt/facets/ordering/cleanup
distinction; controller admission, operation profiles and bounds; workspace
lifecycle and receipt-readiness distinction; and schema's new-challenge rule.

The historical `SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1` remains
`AGGREGATE_BUDGET_SCOPE_UNRESOLVED`, with every historical byte unchanged. It is
neither rerun nor retrospectively relabeled. The next phase is
**SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1R**, requiring a truthful attainable
witness under this new scope. The known 6702-byte materialize-plus-compile lower
relaxation alone cannot establish feasibility. The known 9423-byte
with-fresh-CURRENT relaxation is preserved as conditional historical arithmetic.
This phase makes no final feasibility or impossibility claim, and removes no
transport, identity-encoding, backend-generation or implementation proof blocker.

## Validation and stop

The pure harness runs focused requirement and frozen contract/selection tests,
registry/picker baseline-versus-after comparison, benchmark `--check`, in-memory
compilation, JSON/whitespace checks and whole prior non-cache workspace
preservation. It denies child processes, network, capability-owner imports,
issuance/transition calls and writes outside this new phase. It does not invoke
the old budget proof or its tests. Read-only Git validation is recorded
separately. Exact results are in [validation_summary.json](validation_summary.json)
and the [phase report](SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_REPORT.json).
Existing registry/picker baseline failures are preserved and reported, not
repaired by this phase.

All authority flags are false and operational effect counters zero. No
controller/workspace/preparation owner, schema, operation, transport selection,
pin, historical artifact, capability, runtime or reflection behavior is changed.
No Docker, compiler, controller, process or network probe runs. Local Python
validation launches perform only the explicitly requested source analysis and
in-process checks. No stash, reset, clean or repin is used. **STOP.**
