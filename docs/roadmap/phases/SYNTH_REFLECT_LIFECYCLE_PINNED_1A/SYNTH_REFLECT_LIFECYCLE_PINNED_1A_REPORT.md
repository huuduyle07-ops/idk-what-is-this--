# SYNTH.REFLECT.LIFECYCLE.PINNED.1A

SYNTH_REFLECT_LIFECYCLE_PINNED_1A_COMPLETE

The additive pinned reflection one-shot lifecycle owner is implemented and pure-validated. No operational reflection lease was issued or consumed and no reflection effect occurred.

## Owner and authentication

`core.synthetic_reflection_execution_lifecycle_pinned` defines the independent immutable `PinnedSyntheticReflectionExecutionLease`, schema `synthetic_reflection_execution_lease_pinned_1_v1`.

Domain: `CATTUS:SYNTH.REFLECT.LIFECYCLE.PINNED.1:exact-reflection-lease:v1`. Secret, lock, registry, permanent admission map and signed state are independent of every historical owner.

The exact original pinned admission, reflection request, pinned runtime lease and pinned authorization are strongly retained and reauthenticated through unchanged public validators on every operation. Validators must return their original input. Optional inputs must be the retained object by identity. Provider provenance is inherited transitively.

Public APIs:

- `issue_pinned_synthetic_reflection_execution_lease`
- `validate_pinned_synthetic_reflection_execution_lease`
- `pinned_synthetic_reflection_execution_lease_fingerprint`
- `pinned_synthetic_reflection_execution_lease_state`
- `check_pinned_synthetic_reflection_execution_lease_preexecution_readiness`
- `check_pinned_synthetic_reflection_execution_lease_active_readiness`
- `consume_pinned_synthetic_reflection_execution_lease`
- `invalidate_pinned_synthetic_reflection_execution_lease`

## One-shot identity and state

The permanent key contains authenticated admission owner/phase/schema/PID/admission ID inside this lifecycle's private process store. It is derived after public admission authentication. The retained admission and permanent tombstone survive lease collection and terminal transitions. BEFORE and AFTER use distinct admissions.

| Operation | Reflection prerequisite | Runtime prerequisite | Result |
|---|---|---|---|
| Issue | No permanent admission slot | ISSUED | ISSUED |
| Preexecution readiness | ISSUED | ISSUED | local_ready=true |
| Active readiness | ISSUED | CONSUMED | reflection_active_ready=true |
| Consume | ISSUED | CONSUMED | CONSUMED |
| Invalidate | ISSUED | Any authentic state | INVALIDATED |
| Validate terminal | CONSUMED or INVALIDATED | Any authentic state | Evidence only; both readiness flags false |

Every graph must authenticate. Runtime state comes from the public pinned state API with the exact authorization, never initial-state or report fields. Overall `behavioral_activation_ready=false`, `reason=PROOF_UNRESOLVED` in every report. Separate `readiness_reason` preserves typed mismatch/terminal diagnostics.

The immutable projection binds owner/process/issuance identity, both role literals, admission/request/renderer/auth/runtime identifiers and fingerprints, authorization proof context, exact scenario/source/invocation/field/read scope, initial runtime ISSUED state, and the authority matrix. Domain-framed public SHA256 fingerprints identify issuance. A private independent HMAC authenticates current state separately. No secret, record HMAC, registry or mutable record is exported.

## Atomicity, rejection, and authority

Wrong PID rejects before lock acquisition. Issuance prepares a fully signed store, performs a final public runtime ISSUED check, and publishes the permanent slot plus ISSUED record in one store replacement. Transition failure preserves the previous record. There is no cross-owner lock or transaction. Runtime changes after publication are rechecked on later readiness/consume.

Race tests cover duplicate issuance, consume/consume, invalidate/invalidate and consume/invalidate; exactly one publication or terminal commit succeeds. Copies, reconstruction, projections, IDs, substituted originals, wrong role/scope/state/process, repeat transitions, unknown validators, and provider/readiness input bypasses are rejected. Known upstream code/reason is retained; unknown failures become PROOF_UNRESOLVED. The JSON report lists the complete typed taxonomy and rejection matrix.

Only the exact bound read role for `SyntheticStateBox.value:int`, operation `read_exact_bound_field`, is represented. Runtime, real-task runtime, repository writes, Apply, network, mounts, shell, arbitrary Java/reflection/class/method, private methods, field writes, enumeration, executor, BANK, compilation, constructor reflection and arbitrary class loading authority remain false in every state.

## Ordering and unresolved dependencies

Normative ordering remains:

1. all capability/authentication gates
2. source/harness ready
3. consume pinned runtime lease
4. consume BEFORE reflection lease
5. perform BEFORE exact reflection read
6. invoke exact public decrement(3)
7. consume AFTER reflection lease
8. perform AFTER exact reflection read

The lifecycle performs no read or invocation. CONSUMED reflection permission does not prove a read; CONSUMED runtime permission does not prove invocation. Source placement, compilation timing/authority and consumer/executor proof remain `UNRESOLVED_DOWNSTREAM_DEPENDENCY`. Compilation authority remains false and the production runtime consumer stays fail-closed.

## Validation and preservation

- Focused isolated lifecycle tests: 176 passed; no production issuance, transitions, validators or reads called.
- Contract source/AST: 151 passed. One stale contract-freeze absence assertion is deselected; frozen bytes remain unchanged.
- Historical source/AST regressions: 14 passed; additional frozen source checks: 14 passed.
- Registry/picker: 292 passed and 7 pre-existing failures, identical baseline/after; projections unchanged.
- Benchmark --check: 54 cases, 0 errors. In-memory compilation, JSON/whitespace and git diff --check passed.
- Preservation: all 2444 pre-existing files unchanged, including old reflection lifecycle, pinned admission, runtime/provider owners, registry, reversals and historical executor attempts.
- Full suite and issuance-dependent production suites were not run. Initial collection hit a denied no-op directory bootstrap before any test; the local guard was corrected and the blocked attempt evidence is retained.

Old lifecycle source changed: **false**. Pinned admission source changed: **false**. Operational reflection lease issued: **false**. Operational reflection effect: **false**. All requested operational effect counts: **zero**.

STOP. No source/compile resolution or live capability issuance.
