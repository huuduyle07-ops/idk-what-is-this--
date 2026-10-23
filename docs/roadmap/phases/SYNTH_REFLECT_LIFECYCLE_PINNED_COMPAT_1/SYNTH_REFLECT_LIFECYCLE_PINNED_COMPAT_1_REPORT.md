# Pinned runtime lease to reflection lifecycle compatibility audit

Phase: `SYNTH.REFLECT.LIFECYCLE.PINNED.COMPAT.1`

Date: 2026-10-13, Asia/Seoul

**Outcome: `REFLECTION_PINNED_REQUIRES_ADDITIVE_ADAPTER`.**

Frozen reflection state/order/read semantics are reusable. Frozen public
authorization compatibility, admission, and lease lifecycle implementations
cannot authenticate the new pinned authorization/lease domain. They call
exact old public validators and assume old authorization identity fields;
the reflection lifecycle additionally retains original upstream objects.
This is an intentional implementation boundary,
not a validator defect. No adapter or new schema is implemented or frozen here.

This conclusion establishes compatibility of semantics only. The implemented
pinned runtime owner still reports behavioral readiness `PROOF_UNRESOLVED`;
its consume path fails closed before committing CONSUMED. Reflection acceptance,
operational readiness, and source/compile authority remain unclaimed.

## Three separate compatibility decisions

| Layer | Semantic reuse | Frozen public API acceptance of pinned inputs |
| --- | --- | --- |
| `SYNTH.REFLECT.1` exact read | `REUSABLE_UNCHANGED`: exact `SyntheticStateBox.value:int`, fixed definition, role-specific helper and exact Java-int observation data | Request validator/renderer accepts independent original reflection requests and takes no auth/lease. Its authorization compatibility predicate requires exact old auth, so pinned auth cannot satisfy it. |
| `SYNTH.REFLECT.ADMIT.1` admission | `REQUIRES_ADDITIVE_BINDING`: subordinate exact read permission, source/scenario/field/role and renderer identity remain meaningful | Exact old auth validator/predicate and `auth.issuance_id`/fingerprint bind admission to the old domain. Admission takes no runtime lease or provider and cannot prove pinned runtime acceptance. |
| `SYNTH.REFLECT.LIFECYCLE.1` lease | State/order rules `REUSABLE_UNCHANGED`; pinned identity binding `REQUIRES_ADDITIVE_BINDING` | Exact old auth and runtime lease validators, old authenticated state API and retained original upstream objects prevent pinned-domain acceptance. |

The full function/field/live-identity maps are in
[primitive_admission_trace.md](primitive_admission_trace.md) and
[reflection_lifecycle_trace.md](reflection_lifecycle_trace.md). The latter
enumerates all 29 explicit lifecycle functions/methods, including support
functions and the prohibited issuance-dependent `verify()` path. These traces
record source lines, imported owners, expected exact types, public validators,
projected fields, live-object requirements and old ID/type/schema assumptions.

## Exact domains

| Capability | Exact owner and class | Phase / schema |
| --- | --- | --- |
| Old authorization | `core.synthetic_runtime_authorization.SyntheticRuntimeAuthorization` | `SYNTH.AUTH.1` / `synthetic_runtime_authorization_v1` |
| Old runtime lease | `core.synthetic_runtime_authorization_lifecycle.SyntheticRuntimeExecutionLease` | `SYNTH.AUTH.LIFECYCLE.1` / `synthetic_runtime_execution_lease_v1` |
| Reflection request | `core.synthetic_read_only_reflection.SyntheticReflectionRequest` | `SYNTH.REFLECT.1` / `synthetic_reflection_request_v1` |
| Reflection admission | `core.synthetic_reflection_execution_admission.SyntheticReflectionExecutionAdmission` | `SYNTH.REFLECT.ADMIT.1` / `synthetic_reflection_execution_admission_v1` |
| Reflection lease | `core.synthetic_reflection_execution_lifecycle.SyntheticReflectionExecutionLease` | `SYNTH.REFLECT.LIFECYCLE.1` / `synthetic_reflection_execution_lease_v1` |
| Pinned authorization | `core.synthetic_runtime_authorization_pinned.PinnedSyntheticRuntimeAuthorization` | `SYNTH.AUTH.PINNED.1` / `synthetic_runtime_authorization_pinned_1_v1` |
| Pinned runtime lease | `core.synthetic_runtime_authorization_pinned_lifecycle.PinnedSyntheticRuntimeExecutionLease` | `SYNTH.AUTH.LIFECYCLE.PINNED.1` / `synthetic_runtime_execution_lease_pinned_1_v1` |

The pinned implementation completion marker remains
`SYNTH_AUTH_LIFECYCLE_PINNED_1A_COMPLETE`. The public owner phase is
`SYNTH.AUTH.LIFECYCLE.PINNED.1`; implementation slice 1A does not rename it.

## Authentication boundary proof

`core/synthetic_reflection_execution_lifecycle.py:91` authenticates old auth
with `authorization_owner.validate_synthetic_runtime_authorization` at :95,
then old runtime with `runtime_owner.validate_synthetic_runtime_execution_lease`
at :97. It also authenticates exact request/admission objects and their shared
upstream binding. At :117 it compares old runtime
`upstream_authorization_issuance_id` to `authorization.issuance_id`.

Old auth's public validator requires `type(authorization) is
SyntheticRuntimeAuthorization`, its own live registry identity, issuing PID,
immutable scope and process-local HMAC
(`core/synthetic_runtime_authorization.py:292`). Old runtime's validator
requires its exact class, original weak lease identity, retained original auth,
permanent issuance binding, signed immutable projection and current state
(`core/synthetic_runtime_authorization_lifecycle.py:184`). These requirements
are transitive across reflection validation, fingerprints, state reads,
readiness and terminal transitions.

Focused inert tests demonstrate that the exact pinned lease class is rejected
by the unchanged old public lease validator at its exact-type gate, before
registry lookup. The pinned public validator independently rejects those
unregistered pinned data objects. Pinned auth is rejected by old auth validation
and reflection authentication for each role. Copies, JSON and wrappers do not
establish authority. Matching fields, fingerprints, state labels or schemas do
not make these objects authentication compatible.

Field copying, subclass tricks, schema aliases, old registry insertion,
authenticated old-object fabrication and old HMAC reuse cannot bridge this
boundary truthfully. No such bridge was attempted or implemented.

## State and ordering reuse matrix

| Frozen rule | Classification | Proof / pinned implication |
| --- | --- | --- |
| Issue BEFORE and AFTER reflection leases only while authenticated runtime is ISSUED | `REUSABLE_UNCHANGED` | Lifecycle :270, final state check :283 before publication. Both roles use the same rule. |
| Pre-execution reflection readiness requires reflection ISSUED and runtime ISSUED | `REUSABLE_UNCHANGED` | Lifecycle :304/:314; precheck reserves nothing. |
| Active readiness requires reflection ISSUED and runtime CONSUMED | `REUSABLE_UNCHANGED` | Lifecycle :320 for both roles. |
| Consume reflection only from ISSUED and after runtime CONSUMED | `REUSABLE_UNCHANGED` | Lifecycle :325; exact caller identities/role reauthenticated before commit. |
| Validate/read terminal reflection evidence without claiming readiness | `REUSABLE_UNCHANGED` | Lifecycle :222/:292/:299 authenticate CONSUMED/INVALIDATED records; validity alone imposes no specific runtime state. |
| Invalidate an ISSUED reflection effect permanently without requiring runtime CONSUMED | `REUSABLE_UNCHANGED` | Lifecycle :325/:347; upstream runtime must authenticate, but no target runtime state is imposed for invalidation. |
| At most one reflection lease per admission, including dead/terminal tombstones | `REUSABLE_UNCHANGED` | Lifecycle :274/:233; no refund/reissue. |
| One shared original runtime/auth graph; stable IDs/fingerprints; source/field/role binding | `REQUIRES_ADDITIVE_BINDING` | Lifecycle :91/:209/:251; pinned originals and nested scope require an additive authentication binding. |
| Exact old runtime type/schema/state API | `OLD_RUNTIME_SPECIFIC` | Lifecycle import :20, validator :97, state API :263. |
| Old auth type/validator/`issuance_id` and upstream ID field spelling | `OLD_AUTH_SPECIFIC` | Lifecycle import :19, validator :95, binding :117/:214; admission :290/:335. |
| Old JAVA.1 requirement inherited through old auth/spec validation | `REQUIRES_ADDITIVE_BINDING` | Pinned domain validates its retained PINNED.1C provider graph. Frozen reflection directly authenticates no provider object. |
| Runtime consume before BEFORE consume/read, then public invocation, then AFTER consume/read | `REUSABLE_UNCHANGED` | Literal lifecycle sequence :37 matches pinned first-behavior boundary. |
| Source/harness ready before runtime consumption | `REUSABLE_UNCHANGED` | Both frozen sequence and pinned consumption contract require it. |
| Source materialization and scenario compilation placement/authority | `UNRESOLVED` | No frozen reflection rule resolves placement or grants compilation authority. |

The required order is:

1. Authenticate all capability gates; establish source/harness readiness.
2. Consume the scenario runtime lease.
3. Consume BEFORE reflection lease, then perform the exact BEFORE read.
4. Invoke exact public `decrement(3)`.
5. Consume AFTER reflection lease, then perform the exact AFTER read.

The pinned contract commits consumption immediately before the first behavioral
effect. When that effect is the BEFORE read, runtime commit precedes that read.
The intervening reflection lease transition performs no behavioral read and
preserves that boundary. No frozen rule requires runtime consumption after a
first reflection read. There is no demonstrated semantic ordering conflict.

The frozen reflection lifecycle does not verify that BEFORE was read or that
the public invocation occurred before AFTER. The executor must preserve the
sequence; a CONSUMED lease is not evidence of a completed read or invocation.

## Old versus pinned runtime lease

The detailed comparison table in `reflection_lifecycle_trace.md` covers owner,
phase, schema, exact class, ID, stable fingerprint, PID, state API, scenario,
source kind/hash/size/definition, invocation, field, upstream ID/fingerprint,
proof context, provider, authority matrix, live identity and copy/JSON rejection.

The old lease exposes top-level scenario/source/invocation fields and old auth
`upstream_authorization_issuance_id`. The pinned lease binds nested authenticated
`scenario` and `provider` projections, `authorization_id`,
`authorization_fingerprint`, `authorization_proof_context_id`, issuing PID,
activation policy identity/digest, evidence digest and stable fingerprint.
Pinned provider projection carries exact root/requirement/image/sandbox,
controller and cleanup identity, backed by mandatory upstream public validation
of the retained original graph. Old auth binds frozen JAVA.1/SANDBOX.2
requirements rather than that pinned provider graph.

Both owners preserve exact original live lease/upstream identity, permanent
one-shot records, stable issuance fingerprint and owner-authenticated current
state. Their classes, registries, secrets and digest domains remain separate.
Both keep general runtime/write/Apply/network authorities false; pinned also
explicitly keeps reflection-execution and compilation authority false.

## Minimum future pinned reflection projection

A future separately reviewed additive boundary would need:

- Exact original pinned authorization and runtime lease, retained and
  reauthenticated through their unchanged pinned public validators; passing the
  auth to lease validation must match the retained original by identity.
- Exact pinned owner/phase/schema/PID, lease ID and authenticated stable
  fingerprint, auth ID/fingerprint and proof context. Scalars describe originals
  and cannot replace them.
- Authenticated current runtime state from
  `pinned_synthetic_runtime_execution_lease_state`, checked at issuance,
  precheck and consume; independent one-shot reflection effect state.
- Authenticated scenario phase/ID, source kind/hash/size/definition, invocation
  identity, exact `SyntheticStateBox.value:int` field, read operation and
  BEFORE/AFTER role, with original request/admission identity bindings.
- Pinned admission authentication and upstream binding. Existing independent
  request validator/renderer semantics may be reusable; existing old-auth
  compatibility predicates/admissions cannot be presumed compatible.
- Provider provenance through mandatory pinned upstream validation. A separate
  direct provider input is needed only if a future reflection contract establishes
  an independent requirement; frozen reflection shows none.

No new schema is frozen by this list. Defining that additive reflection contract
does not resolve consumer readiness, source preparation or scenario compilation.

## Validation, effects and preservation

See [validation_summary.json](validation_summary.json), individual result/log
artifacts, [registry_comparison.json](registry_comparison.json),
[static_validation.json](static_validation.json),
[preservation_check.json](preservation_check.json) and
[git_diff_check.json](git_diff_check.json) for final measured results.

Focused audit tests: **23 passed**. Final frozen safe selection: **68 passed**.
Registry/picker baseline and after: **292 passed, the same 7 existing failures**
in each run, with identical registry summaries and picker results. Benchmark
`--check` passed. In-memory compilation, JSON/whitespace and `git diff --check`
passed. All guarded operational-effect counters are zero.

Frozen safe selection covers pinned lifecycle 1A, old lifecycle, primitive and
admission validation, historical executor contract checks and source/AST
regressions. Frozen reflection lifecycle's positive tests and proof verifiers
issue handles, and pinned 1A's broader suite issues/transitions isolated test
leases; those are excluded from the final zero-capability selection. Reflection
lifecycle is instead covered by full source trace and focused AST/inert rejection
tests. No complete frozen-suite run is claimed.

The first frozen selection also included a historical negative-fixture suite
that constructs unregistered old data projections. It issued no capabilities,
seeded no registries and performed no effects. Its result is retained as
`frozen_initial.json`/`.txt`; the final selection narrows that suite to source-only
checks to avoid old-object construction entirely. No authentication masquerading
or old signing helper was used in either run.

Every operational effect remains zero: Docker, SANDBOX2, JAVA1C, provider
issuance, pinned authorization issuance, pinned execution lease issuance,
runtime/reflection lease consumption or invalidation, reflection admission/lease
issuance, reflection reads, SyntheticStateBox, BANK, EXECUTOR.1R, Apply and
repository runtime writes. Guarded validation also records zero process/network,
capability/transition, execution/proof and repository-write attempts. Explicit
audit documents/tests/results are the only new repository artifacts.

Required source-change assertions:

| Assertion | Value |
| --- | --- |
| Reflection primitive/admission/lifecycle source changed | **false** |
| Pinned lifecycle source changed | **false** |
| Any preexisting historical/runtime/provider/executor/registry/reversal bytes changed by this audit | **false** |
| Repin, stash, reset, clean, Apply | **false** |

Baseline preservation hashes cover preexisting workspace files, including
historical phase documents and ignored runtime artifacts. The audit retains the
user's preexisting dirty worktree. Registry/picker baseline and after results
are compared, including existing failures rather than claiming a clean suite.
Benchmark `--check`, in-memory compilation, JSON/whitespace checks and
`git diff --check` are recorded separately.

## Recommended next slice and stop

Review a contract-only additive pinned reflection admission/lifecycle boundary
using original pinned objects and unchanged ordering. Preserve fail-closed
operational readiness and leave source/compilation classification to its separate
downstream slice. This audit stops at the compatibility conclusion. No pinned
reflection adapter is implemented.
