# Additive pinned reflection source proof

Phase: `SYNTH.REFLECT.PINNED.CONTRACT.1`

Date: 2026-10-13, Asia/Seoul

This is read-only source evidence for a pure contract freeze. No capability
module was imported or executed during this source inspection. No request,
authorization, provider proof, admission or lease was issued; no capability was
consumed or invalidated. Source lines below refer to the unchanged existing
workspace files. New owner/type/API names in the contract are future boundaries,
not implemented APIs.

## Exact request reuse: decision A

Reuse the exact existing
`core.synthetic_read_only_reflection.SyntheticReflectionRequest`, schema
`synthetic_reflection_request_v1`. A separate pinned request is unnecessary.

| Source | Proof |
| --- | --- |
| `core/synthetic_read_only_reflection.py:77-102` | The complete request dataclass contains scenario/source/definition, field/read/role, source kind, its own issuance ID/PID/signature and immutable authority flags. It contains no authorization object, old authorization issuance ID, runtime lease, provider or authorization fingerprint. |
| `core/synthetic_read_only_reflection.py:114-127` | The fixed request and complete canonical payload introduce no additional upstream auth identity. `request.phase_id` is the frozen scenario phase, not the renderer owner phase. |
| `core/synthetic_read_only_reflection.py:164-188` | Public request validation authenticates exact request class, original weak-registry identity, issuing process, fixed immutable scope, role fingerprint and independent process-local HMAC. It validates fixed source bytes without issuing or authenticating old authorization. |
| `core/synthetic_read_only_reflection.py:207-237` | The separate `synthetic_reflection_satisfies_authorization` predicate explicitly accepts the exact old `SyntheticRuntimeAuthorization` and its unchanged public validator. This old-auth-specific predicate cannot be the new pinned compatibility predicate. |
| `core/synthetic_read_only_reflection.py:263-265` | Public rendering accepts only the independently authenticated original request and returns a fixed role-specific helper string. It accepts no authorization or runtime lease. |

The request contract fingerprint is intentionally shared by all valid requests
of one role: `fingerprint` at :104-107 uses :130-137; the contract payload at
:125-127 excludes request `issuance_id` and PID. A request fingerprint alone
therefore cannot bind the exact original request. Future pinned admission and
lease owners must retain and reauthenticate the original object and bind its
own issuance ID as well as its authenticated contract fingerprint. The frozen
request bytes, fingerprints, registry, HMAC and old compatibility predicate stay
unchanged.

## Primitive, role and renderer continuity

| Identity | Unchanged source evidence |
| --- | --- |
| Scenario | `synthetic.EXECUTOR.1R.decrement_3`, scenario phase `PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R`, primitive :21-22 |
| Source | `phase_owned_synthetic_fixture`, 239 bytes, SHA-256 `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302`, primitive :23-25/:61-64 |
| Definition | SHA-256 `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d`, exact `private int value = 10;` slice `[36:59]`, primitive :24/:65-69 |
| Exact field/read | `SyntheticStateBox.value:int`, `read_exact_bound_field`, primitive :114-117 |
| Roles | Semantic BEFORE = `exact_private_state_before`; AFTER = `exact_private_state_after`, primitive :26-27 |
| Exact public invocation | `boolean SyntheticStateBox.decrement(int)`, argument `(3,)`, pinned scenario projection in `core/synthetic_runtime_authorization_pinned_lifecycle.py:168-177` |
| Renderer identity | `SYNTH.REFLECT.1.render_synthetic_read_only_reflection`, frozen admission `core/synthetic_reflection_execution_admission.py:33` |
| Renderer output | Complete fixed helper literals at primitive :243-260 use `SyntheticStateBox.class`, `getDeclaredField("value")`, `setAccessible(true)` and `getInt(instance)`, with different BEFORE/AFTER helper names. |

Frozen admission :237-242 binds renderer identity, primitive owner phase/schema,
and SHA-256 of the rendered helper. The future pinned admission can preserve
that architecture by calling unchanged public rendering after request
authentication, hashing the returned fixed helper bytes, and forming its own
domain-separated renderer digest. It must not call old private hash/signing
helpers or reinterpret rendered text as an observed runtime read.

`SyntheticPrivateFieldObservation` at primitive :269-300 is a data shape, not
capability or receipt provenance. Its validator accepts any exact Python `int`
in the Java signed-int range; it does not prove a read occurred or compare a
measurement to expected 10/7. Fixed helper text, validated observation data,
request validity, admission authority, lease authority and actual read evidence
remain distinct.

## Exact unchanged pinned upstream APIs

| Existing public boundary | Signature and source |
| --- | --- |
| Pinned auth validator | `validate_pinned_synthetic_runtime_authorization(authorization, *, provider_outcome=None)`, `core/synthetic_runtime_authorization_pinned.py:261-288` |
| Pinned runtime validator | `validate_pinned_synthetic_runtime_execution_lease(lease, authorization=None)`, `core/synthetic_runtime_authorization_pinned_lifecycle.py:448-451` |
| Authenticated runtime state | `pinned_synthetic_runtime_execution_lease_state(lease, authorization=None)`, pinned runtime :454-456 |
| Pinned runtime readiness report | `check_pinned_synthetic_runtime_execution_lease_preconditions(lease, authorization)`, pinned runtime :459-466 |

The authorization validator requires the exact new class at :264, exact live
registry object and PID at :268-272, retained original provider graph and source
spec at :273-281, exact canonical scope at :282-284 and independent HMAC at
:285-287, then returns the supplied original at :288. Its public fields are
`authorization_id`, `proof_context_id`, `issuing_pid`, nested `scenario` and
`provider` (:185-192). There is no old `issuance_id`. Public auth `.fingerprint`
(:223-225) repeats public authentication before deriving the authenticated
authorization fingerprint.

Pinned runtime validation calls `_authenticated_record_locked` (:383-422). It
requires the exact pinned lease class, independent live weak identity and
permanent binding. At :390-391, supplied auth must be the exact retained original
by `is`; omitted auth uses only the retained original. `_authenticate_authorization`
at :208-227 delegates to unchanged public auth validation at :212 and requires the
same original object return at :215-216. Scenario/provider projections, upstream
auth ID/fingerprint/proof context, lease evidence digest, stable fingerprint,
canonical immutable record, authentic current semantic state and HMAC are all
verified before success.

The existing runtime lease carries `authorization_id`,
`authorization_fingerprint`, `authorization_proof_context_id`, PID, nested
scenario/provider, activation policy identity/digest, lease ID, evidence digest
and `stable_fingerprint` (:250-286). Its `.fingerprint` property (:289-292)
authenticates then returns the stable issuance fingerprint. Current state is an
authenticated owner-record API, not the immutable `initial_state`, a caller
Boolean, a report string or JSON projection. Every future pinned reflection
operation must call the unchanged auth and runtime public validators using the
retained originals, passing that exact auth to runtime validation.

## Provider provenance is inherited

Frozen reflection admission and lifecycle accept no direct provider input:
admission :276-278; `core/synthetic_reflection_execution_lifecycle.py:91-119`.
No independent reflection requirement for a second provider input is shown.

Pinned auth `_authenticate_provider` at :145-181 delegates to the public exact
pinned provider validator at :150. It requires the original proof-only root,
exact requirement, immutable image, sandbox policy and cleanup. Public auth
validation then checks original root, binding and all retained graph objects by
identity (:275-281). Pinned runtime repeats mandatory auth validation and checks
its signed public provider projection (:392-399). Thus the truthful chain is:

`exact reflection lease/admission -> exact pinned runtime lease -> exact pinned
authorization -> retained authenticated PINNED provider graph`.

Freeze transitive provenance, with no independent provider argument or new direct
provider projection. Matching provider projection remains evidence, never
reflection permission or substitute for original-object authentication.

## Frozen lifecycle state and order

| Rule | Frozen source |
| --- | --- |
| Exactly `ISSUED`, `CONSUMED`, `INVALIDATED` | Old reflection lifecycle :34; pinned runtime :27 |
| One reflection lease per admission; permanent dead/terminal tombstones | Old reflection lifecycle :51-53/:232-233/:270-288 |
| Reflection lease issuance requires authenticated runtime `ISSUED` | Old reflection lifecycle :283-288 |
| Local/pre-execution readiness requires reflection `ISSUED` and runtime `ISSUED` | Old reflection lifecycle :304-318 |
| Active readiness requires reflection `ISSUED` and runtime `CONSUMED` | Old reflection lifecycle :320-322 |
| Consume only reflection `ISSUED` with runtime `CONSUMED` | Old reflection lifecycle :325-337 |
| Invalidate only reflection `ISSUED`; runtime authenticates with no specific state requirement | Old reflection lifecycle :325-337/:347-350 |
| Authenticate terminal reflection evidence without readiness | Old reflection lifecycle :222-248/:292-301 |
| Exact retained admission/request/runtime/auth/role binding | Old reflection lifecycle :193-204/:251-258 |
| Wrong PID before inherited lock wait | Old reflection lifecycle :81-83; pinned runtime :130-140 |

Frozen old admission itself accepts no runtime input and does not check runtime
state (`core/synthetic_reflection_execution_admission.py:276-278`). The new pinned
admission `ISSUED`-at-issuance gate is the requested additive runtime binding,
consistent with the frozen reflection lease preparation constraint. It should
not be described as a runtime gate already implemented by old admission.

The frozen executor sequence at old reflection lifecycle :37-41 is exactly:

1. Authenticate all capability gates.
2. Source/harness ready.
3. Consume scenario runtime lease.
4. Consume BEFORE reflection lease.
5. Perform BEFORE exact reflection read.
6. Invoke exact public `decrement(3)`.
7. Consume AFTER reflection lease.
8. Perform AFTER exact reflection read.

Reflection permission-state mutation performs no field read or invocation.
`CONSUMED` is permission spending, not actual effect evidence. The pinned
first-behavior boundary therefore remains runtime consume, BEFORE lease consume,
then BEFORE read. Neither frozen reflection owner verifies that BEFORE read or
the invocation preceded AFTER; effect ordering and proof belong to the future
executor, not the reflection lifecycle owner.

## Atomicity and identity constraints

The pinned runtime convention is one immutable owner-store replacement for
issuance (:425-445) or terminal commit (:474-487). Canonicalization at :71-85
rejects nonexact primitive/list/dict types. Domain framing at :88-92 is owner
domain + NUL + role UTF-8 + NUL + canonical JSON UTF-8. Current-record HMAC at
:359-361 authenticates immutable issuance projection and current state; stable
fingerprint derives only from immutable issuance identity (:364-380).

Future pinned admission/lifecycle must use independent owner secrets and distinct
new domains with that framing convention. The existing domains must remain
unchanged: pinned auth `CATTUS:SYNTH.AUTH.PINNED.1:exact-scenario-authorization:v1`
with its existing framing, and runtime
`CATTUS:SYNTH.AUTH.LIFECYCLE.PINNED.1:exact-execution-lease:v1`. Old reflection
owner registries/secrets/private helpers cannot be borrowed.

The permanent pinned admission key should bind original auth owner/phase/schema/
PID/authorization ID, original runtime owner/phase/schema/lease ID and exact
role. Fresh request IDs or matching fingerprints must not reopen the same
role permission. The exact original request stays retained as a separate binding.
One admission has at most one lease. Collection, a terminal state or downstream
failure never deletes one-shot tombstones or permits refund/reissue.

The independent runtime owner lock is not a reflection owner lock. Frozen
reflection issuance explicitly treats the last public `ISSUED` state check as
the issuance eligibility point (:282-285); checks are snapshots and reserve
nothing. A future pinned contract can require an own-owner atomic publication
and final authenticated runtime eligibility check. It cannot claim a cross-owner
transaction or hold/modify private upstream locks using the unchanged public
API. A later state change makes readiness stale and is rechecked at the next
operation. Consumption requires `CONSUMED`, which is terminal in pinned runtime
semantics; competing reflection terminal operations permit at most one own-owner
commit.

## Fail-closed readiness and downstream dependencies

Pinned runtime readiness :459-466 always reports
`behavioral_activation_ready=false`; authentic ISSUED reports
`PROOF_UNRESOLVED`. `_consumer_readiness` at :469-471 always fails closed, and the
consume transition calls it at :483 before any terminal store publication.
Runtime compilation authority is fixed false (:286), with no new readiness
evidence owner or caller bypass (:113-119).

Source materialization position and scenario compilation classification/timing/
authority remain `UNRESOLVED_DOWNSTREAM_DEPENDENCY`. These block overall behavior
and runtime consumption. Freezing pinned reflection local/active semantic
readiness does not make currently unreachable active execution available.
Compilation authority remains false. The existing frozen audit records this
boundary at
`docs/roadmap/phases/SYNTH_REFLECT_LIFECYCLE_PINNED_COMPAT_1/SYNTH_REFLECT_LIFECYCLE_PINNED_COMPAT_1_REPORT.md:17-20,85-120,145-169`.

Source proves request reuse, exact pinned upstream binding and unchanged ordering
can be defined without violating frozen invariants. The contract can therefore
freeze while downstream behavioral proof stays unresolved. No pinned reflection
owner, capability, runtime consumer, executor or behavioral effect exists as a
result of this source proof.
