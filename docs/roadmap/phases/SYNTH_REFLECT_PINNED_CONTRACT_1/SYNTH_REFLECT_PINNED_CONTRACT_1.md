# SYNTH.REFLECT.PINNED.CONTRACT.1

Date: 2026-10-13, Asia/Seoul. Pure contract freeze.

The additive pinned reflection admission and one-shot lifecycle semantics are
frozen by [contract.json](contract.json). No adapter, reflection capability or
behavioral effect exists. Completion is recorded only after measured validation
in [SYNTH_REFLECT_PINNED_CONTRACT_1_REPORT.json](SYNTH_REFLECT_PINNED_CONTRACT_1_REPORT.json).

This phase authorizes documents and pure source/AST validation only. It creates
no owner implementation, class, registry, secret, request, admission, lease,
consumer or executor. All API names below describe future contracts. Stop after
this contract freeze.

The predecessor compatibility result remains
`REFLECTION_PINNED_REQUIRES_ADDITIVE_ADAPTER`. Its reusable primitive and lifecycle
semantics do not make its frozen old-auth implementation accept pinned objects.
The existing runtime owner remains
`core.synthetic_runtime_authorization_pinned_lifecycle`, exact class
`PinnedSyntheticRuntimeExecutionLease`, schema
`synthetic_runtime_execution_lease_pinned_1_v1`, implementation status
`SYNTH_AUTH_LIFECYCLE_PINNED_1A_COMPLETE`.

## Exact primitive and request decision

Reuse the existing `SYNTH.REFLECT.1` read semantics unchanged:

| Binding | Exact value |
| --- | --- |
| Scenario phase / ID | `PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R` / `synthetic.EXECUTOR.1R.decrement_3` |
| Source kind / bytes | `phase_owned_synthetic_fixture` / 239 |
| Source SHA-256 | `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302` |
| Definition SHA-256 | `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d` |
| Field / operation | `SyntheticStateBox.value:int` / `read_exact_bound_field` |
| Public invocation | `boolean SyntheticStateBox.decrement(int)`, argument `3:int` |
| BEFORE request role | `exact_private_state_before` |
| AFTER request role | `exact_private_state_after` |

BEFORE and AFTER are semantic role labels mapped exactly to the existing request
role literals. No request bytes or role literals change. The observations 10,
true, 7 are expected data; these values do not prove an actual execution.

**Request decision A: reuse the exact original `SyntheticReflectionRequest`.**
Its exact class fields and complete signed payload contain its own request
identity, fixed scope and role, with no old authorization identity. Its public
validator and renderer take only the request. Only the separate frozen
`synthetic_reflection_satisfies_authorization` predicate requires old auth.
Source proof: primitive :77, :120, :125, :164, :207, :263; full references are in
[source_proof.md](source_proof.md).

Define a new conceptual predicate
`pinned_synthetic_reflection_request_satisfies_runtime` in the new admission
owner. It authenticates the exact original request, pinned authorization and
pinned runtime lease through unchanged public validators, then compares fixed
scope and role. Compatibility grants no permission. It never calls the frozen
old-auth compatibility predicate or fabricates an old authorization.

Request fingerprint is a fixed per-role scope digest, not an original-object
identity. Retain the exact live request and bind its own `issuance_id`, PID and
validated fingerprint separately. Pinned authorization uses
`authorization_id`; no authorization `issuance_id` is assumed. Request
`phase_id` identifies the scenario phase; renderer phase is `SYNTH.REFLECT.1`.

Retain renderer identity
`SYNTH.REFLECT.1.render_synthetic_read_only_reflection`. A future admission binds
the unchanged public renderer's fixed helper UTF-8 SHA-256 and an independently
domain-separated renderer-evidence digest. It uses no old private helper or
secret. Rendering is text generation, grants no compilation authority and proves
no read. No renderer is operationally invoked by this phase.

## Distinct owners and exact original graph

Repository additive pinned module/type/schema conventions support freezing:

| Boundary | Owner / exact type | Phase / schema |
| --- | --- | --- |
| Admission | `core.synthetic_reflection_execution_admission_pinned` / `PinnedSyntheticReflectionExecutionAdmission` | `SYNTH.REFLECT.ADMIT.PINNED.1` / `synthetic_reflection_execution_admission_pinned_1_v1` |
| Lifecycle | `core.synthetic_reflection_execution_lifecycle_pinned` / `PinnedSyntheticReflectionExecutionLease` | `SYNTH.REFLECT.LIFECYCLE.PINNED.1` / `synthetic_reflection_execution_lease_pinned_1_v1` |

These identities are contract declarations only. They are not implemented or
registered. No alias or subclass of an old admission/lease type is permitted.

Every public operation—including predicates, validation, fingerprints, state
and readiness—must reauthenticate through both unchanged public APIs:

- `core.synthetic_runtime_authorization_pinned.validate_pinned_synthetic_runtime_authorization`
- `core.synthetic_runtime_authorization_pinned_lifecycle.validate_pinned_synthetic_runtime_execution_lease`

Require same-original validator returns and pass the retained exact auth to
runtime validation. The unchanged public
`pinned_synthetic_runtime_execution_lease_state(lease, authorization=original_auth)`
supplies current runtime state. Public authenticated fingerprints supply stable
identity. Immutable `initial_state`, report state or caller JSON cannot.

Admission strongly retains its original auth, runtime and request. Lease records
strongly retain original admission, request, runtime and auth. Supplied optional
upstreams must be those same objects by `is`; omitted inputs use retained
originals. Owner records retain original capability identity weakly and permanent
tombstones strongly. No reconstruction after collection authenticates.

Matching projection != authenticity. Reject field copies, deepcopy, replace,
manual construction, wrappers, subclasses, JSON/reports, IDs/fingerprints as
inputs, old types and schema relabels. No private upstream registry/lock access,
old-auth synthesis or old-runtime synthesis is permitted.

**Provider decision: inherit transitively.** Authenticate the exact runtime ->
exact pinned auth -> retained authenticated PINNED provider graph. Accept no
independent provider input and require no direct provider projection. No
independent reflection provider requirement was found. Provider proof remains
evidence, not reflection permission.

## Admission identity and permanent one-shot slots

Both BEFORE and AFTER admission issuance require authenticated runtime ISSUED.
Old admission took no runtime lease; this additive pinned admission gate preserves
the frozen lifecycle's preparation-before-activation rule. It cannot issue a
reflection permission after runtime CONSUMED or INVALIDATED.

Sign the admission owner/phase/schema/PID/ID, both role representations,
authenticated original auth ID/fingerprint/proof context, original runtime
ID/stable fingerprint, runtime ISSUED at issuance, fixed scenario/source/size/
definition/invocation/field/read scope, original request identity, renderer
identity/fingerprint and admission evidence digest/fingerprint. Original objects
remain retained outside the scalar payload. Issuance performs no behavior.

The permanent admission key comprises new owner identity/PID, authenticated
pinned auth identity/authorization ID, authenticated runtime identity/lease ID,
role and exact fixed read scope. At most one admission slot exists for each role
on that runtime. Request IDs/fingerprints, renderer fingerprints and mutable or
replaceable proof projections cannot form alternate keys. A fresh same-role
request cannot reopen issuance. The original request is still signed and retained.

At most one reflection lease may ever be issued per admission. BEFORE and AFTER
have independent admissions and leases. Tombstones survive terminal transitions
and collection for the issuing process lifetime. No refund or reissue exists.

## State and runtime eligibility

Reflection states remain exactly ISSUED, CONSUMED and INVALIDATED.
Only ISSUED -> CONSUMED and ISSUED -> INVALIDATED are allowed; both are terminal.

| Operation, for either role | Reflection state | Authenticated runtime state |
| --- | --- | --- |
| Admission issuance | No lease yet | ISSUED |
| Reflection lease issuance | Initial state becomes ISSUED | ISSUED |
| Pre-execution/local readiness | ISSUED | ISSUED |
| Active readiness | ISSUED | CONSUMED |
| Reflection consumption | ISSUED -> CONSUMED | CONSUMED |
| Reflection invalidation | ISSUED -> INVALIDATED | Any authentic state |
| Terminal validation | CONSUMED or INVALIDATED | Any authentic state; no readiness |

Admission validation and lease validation/fingerprints/state queries remain
available after activation or invalidation if all original upstreams authenticate.
Validation of ISSUED evidence is also allowed; validity alone grants no readiness.
Reflection invalidation does not require a specific runtime state.

Stable fingerprints bind immutable issuance identity and exclude mutable current
state. Each current-state record separately signs that projection and state.
No new semantic state, reset or terminal recovery exists.

The immutable signed lease projection binds its lifecycle owner/phase/schema/PID,
lease ID, initial ISSUED, both role identities, original admission and request
identities/fingerprints, renderer identity/fingerprint, pinned auth ID/fingerprint/
proof context, runtime ID/stable fingerprint and issuance eligibility state,
fixed scenario/source/size/definition/invocation/field/read scope, authority matrix,
lease evidence digest and stable fingerprint. Exact original objects stay retained
outside the scalar payload. Issuance-state evidence never substitutes for the
authenticated current runtime state API; private record signatures stay private.

## Ordering and first behavior boundary

The required downstream executor order is:

1. Authenticate all capability gates.
2. Establish source/harness readiness.
3. Consume pinned runtime lease.
4. Consume BEFORE reflection lease.
5. Perform BEFORE exact read.
6. Invoke public `decrement(3)`.
7. Consume AFTER reflection lease.
8. Perform AFTER exact read.

Runtime ISSUED -> CONSUMED commits immediately before the first behavioral
effect. BEFORE reflection lease consumption is permission-state mutation,
not a field read; the intervening permission commit preserves the frozen
boundary. Runtime consumption must precede both BEFORE permission consumption
and BEFORE read.

The reflection owner performs no reads, invocation or behavior. CONSUMED reflection
means permission was consumed, not that the read occurred. CONSUMED runtime
does not prove BEFORE read or public invocation. Observation data and renderer
text are not read evidence. The executor owns ordering and evidence of actual
effects. Failure after a terminal permission commit never refunds it.

## Independent authentication and atomicity

Freeze independent domains:

- `CATTUS:SYNTH.REFLECT.ADMIT.PINNED.1:exact-reflection-admission:v1`
- `CATTUS:SYNTH.REFLECT.LIFECYCLE.PINNED.1:exact-reflection-lease:v1`

Each future owner has an independent secret, lock, registry and records. Neither
uses old reflection, pinned authorization or pinned runtime secrets/domains.
Strict exact nested primitive types, sorted compact JSON, no NaN, UTF-8 and
domain + NUL + role + NUL + canonical bytes follow repository convention.
Domain-framed SHA-256 derives public evidence/fingerprints; HMAC-SHA256 signs
private records. No secret, private signature or registry is exported.

Reject wrong PID before acquiring an inherited owner lock. Under each owner's
lock: authenticate originals, derive/check permanent keys, construct/sign all
records and prepare the complete store, then publish with one store replacement.
A final public runtime ISSUED check is the admission/lease issuance eligibility
point. Failed construction publishes nothing. Terminal transitions reauthenticate
all originals, check reflection ISSUED and required runtime state, sign the target
record, then replace exactly once. Concurrent terminal operations permit at most
one commit.

The unchanged upstream APIs have independent locks. The contract claims atomic
publication within each new owner, not a cross-owner transaction. Runtime can
change after the final ISSUED eligibility check. Readiness/prechecks reserve
nothing; consumption rechecks gates. Authenticated runtime CONSUMED is terminal.
No private locking bridge is introduced.

## Readiness, authority and unresolved dependencies

Keep three distinct report-only meanings:

- `reflection_local_ready`: exact original graph authentic, reflection ISSUED,
  runtime ISSUED.
- `reflection_active_ready`: exact original graph authentic, reflection ISSUED,
  runtime CONSUMED.
- `behavioral_activation_ready`: **false**, reason `PROOF_UNRESOLVED`.

Terminal reflection readiness is false. Local/active readiness does not imply
overall readiness. The abstract active-state rule is not evidence that pinned
runtime consumption is currently reachable: its frozen consumer gate rejects
`PROOF_UNRESOLVED` before terminal publication. This contract changes no such gate
and accepts no caller Boolean/JSON readiness.

Source materialization position, scenario compilation timing/authority and pinned
consumer/executor proof remain `UNRESOLVED_DOWNSTREAM_DEPENDENCY`. They continue
to block behavioral activation and pinned runtime consumption.
**Compilation authority remains false.** Provider infrastructure compilation
does not grant scenario compilation authority.

The admission prepares a lease for one exact role effect. The lease grants only
that exact read-only scope. Neither grants runtime, repository write, Apply,
network, host mount, shell, arbitrary Java/reflection, private method, field write,
enumeration, executor, BANK or compilation authority. Terminal consumption never
widens scope.

## Public projection, errors and preservation

A future executor needs role, lease ID, stable authenticated fingerprint and
authenticated state API; scenario/source/definition and exact invocation/field/
read identity; runtime ID/fingerprint; authorization ID/fingerprint/proof context;
and original admission/request bindings. The public projection includes no
capability secrets and always requires original objects alongside scalars.

[contract.json](contract.json) freezes conceptual operation inputs, outputs,
state requirements and error categories. Distinguish pinned auth/runtime
authentication, runtime state mismatch, request authentication, reflection scope,
admission authentication/duplicate, lease authentication/duplicate, consumed,
invalidated, role mismatch and unresolved proof. Preserve known upstream
scope/provider categories and original code/reason. Unknown validator failure
becomes PROOF_UNRESOLVED. State/scope mismatch never becomes authentication failure.

All historical primitive/admission/lifecycle/auth/pinned runtime/provider/executor
sources, registries, HMAC domains, receipts and reversal history remain unchanged.
No old registry insertion, old capability fabrication, subclass/schema bridge,
private signing reuse, request-byte rewrite, repin, stash/reset/clean or runtime
repository write is allowed.

Required zero effects: Docker, SANDBOX2, JAVA1C, provider/auth/runtime issuance,
runtime consume/invalidate, request/admission/reflection-lease issuance,
reflection consume/invalidate/read, SyntheticStateBox, BANK, EXECUTOR.1R and Apply.
Validation creates documents/tests/results only. Safe source/AST regressions,
registry/picker before/after, benchmark --check, in-memory compilation,
JSON/whitespace, git diff --check and historical hashes are recorded separately.
Issuance-dependent suites and owner verify() functions are excluded.

Success: `SYNTH_REFLECT_PINNED_CONTRACT_1_COMPLETE`. If request reuse, exact graph
binding or ordering cannot preserve frozen invariants, use CONTRACT_UNRESOLVED.
The completed phase stops at the contract; implementation requires a later slice.
