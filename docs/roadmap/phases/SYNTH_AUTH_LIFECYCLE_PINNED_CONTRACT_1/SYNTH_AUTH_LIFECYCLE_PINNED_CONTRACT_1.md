# SYNTH.AUTH.LIFECYCLE.PINNED.CONTRACT.1

2026-10-11 KST. Pure additive execution-lease boundary contract. The normative
machine-readable requirements are in [contract.json](contract.json). Public
operation and type names there are proposals, not available Python APIs. No owner,
provider proof, authorization, execution lease or operational consumer is built
or issued in this phase. Stop after contract freeze. This document grants no
implementation or execution permission.

## Identity and authenticated upstream

The proposed owner is `core.synthetic_runtime_authorization_pinned_lifecycle`,
phase `SYNTH.AUTH.LIFECYCLE.PINNED.1`, schema
`synthetic_runtime_execution_lease_pinned_1_v1`, and distinct exact public type
`PinnedSyntheticRuntimeExecutionLease`. It has no alias to the frozen
`synthetic_runtime_execution_lease_v1`, no reuse of its exact class, and no phase
registry registration in this contract phase.

Only the original live `core.synthetic_runtime_authorization_pinned`
`PinnedSyntheticRuntimeAuthorization`, phase `SYNTH.AUTH.PINNED.1`, schema
`synthetic_runtime_authorization_pinned_1_v1`, is an upstream input. The unchanged
public `validate_pinned_synthetic_runtime_authorization` must return that same
object at issuance and every subsequent validation, state read, readiness check
or terminal transition. Copying fields/HMACs, reconstructing JSON, synthesizing
old auth, relabeling schema or substituting an ID never authenticates it.

The lease retains the exact original authorization, its `authorization_id`,
authenticated fingerprint and `proof_context_id`. Matching scenario projection
!= authorization authenticity. The frozen scenario source is still the old
owner's public spec/source accessors; these supply identity only, never old auth.
The lease binds the scenario from the validated original pinned authorization:
`synthetic.EXECUTOR.1R.decrement_3`, `SyntheticStateBox`,
`boolean SyntheticStateBox.decrement(int)`, argument `(3,)`, field
`SyntheticStateBox.value:int`, and expected `10 / true / 7`. Exact source hash,
239-byte size, definition hash, scenario phase and source kind are bound as well.
No source, method, argument or field override is accepted.

## Explicit provider decision: B

Choose B: additionally sign **every field of the existing public authenticated
`authorization.provider` projection**. After the mandatory unchanged validator
returns the exact original authorization, this projection represents its retained
original `RUNTIME.JAVA.PINNED.1C` /
`runtime_java_pinned_provider_1c_v1` root. The lease retains no alternate caller
provider and reads no private provider or authorization registry.

The signed projection covers root owner/phase/schema, receipt ID, proof-context
identity, fingerprint, evidence digest, exact pinned requirement, immutable image,
sandbox profile/policy, controller identity evidence and cleanup evidence/digest.
Every operation first revalidates the original authorization through its public
owner, then recomputes and compares this projection to the lease's signed value.
Projection equality alone is never proof authentication. The original complete
provider graph remains retained by the unchanged authorization owner; if that
graph or its public validation fails, dependent lease validation fails closed.

This choice makes provenance explicit using an already authenticated public
boundary. It does not require a new provider proof, a private root accessor or
a JAVA.1 compatibility bridge. `exact_provider_proven=true` at authorization
issuance remains required. Provider authority remains false. Provider proof is
evidence, not execution permission, and cannot be reconstructed from JSON.

## Activation policy and unresolved downstream work

The pinned activation policy has its own identity and canonical digest, both
authenticated in the lease. Lease-local preconditions require the exact live
authorization and lease, `ISSUED`, the retained authenticated provider graph,
exact scenario/provider projections, requirement `RUNTIME.JAVA.PINNED.1` /
`runtime_java_pinned_1_v1`, immutable target image and sandbox
`runtime_sandbox_2_v1` with the frozen policy hash. These provider conditions are
already authenticated through the mandatory pinned public validator; no extra
proof issuer or readiness token is invented.

Valid pinned authorization alone is insufficient for behavioral activation.
Lease-local readiness is a pure authenticated snapshot. It cannot establish
acceptance by a reflection/executor consumer, authenticate source/harness
readiness on that consumer's behalf, reserve consumption or accept a caller
Boolean/JSON as readiness evidence. There is currently no public pinned runtime
readiness evidence owner to name. Full behavioral readiness therefore remains
false with `PROOF_UNRESOLVED` until a separately reviewed downstream contract
establishes those gates. A defined prerequisite that subsequently evaluates false
uses `ACTIVATION_PRECONDITION_UNSATISFIED` instead. This introduces no new state.

The semantic consumption boundary is settled: consume the runtime lease
immediately before the first behavioral runtime effect, after all authenticated
consumer capability and source/harness readiness gates. Consumption is the
atomic `ISSUED -> CONSUMED` record commit; the owner itself performs no behavior.
The consumer must repeat the preconditions at that boundary. If the first effect
is an exact BEFORE reflection read, runtime consumption precedes it, preserving
the historical ordering principle. Frozen reflection acceptance is still absent.

Do not consume during provider/auth validation, lease issuance, reflection
admission planning, source inspection or static validation. A failure before
commit preserves `ISSUED`; a failure after commit never refunds, including launch,
BEFORE read, invocation, AFTER read, protocol, timeout and cleanup failures.

Actual source projection/materialization and scenario compilation placement are
**unresolved downstream dependencies**. Current executors stop before those
operations. Exact source/harness readiness must precede consumption, but that
requirement does not settle how preparation obtains authority or whether a future
compile contract classifies compilation as activation. Record a separate
classification/authority contract before any such preparation or consumption;
never invent its placement here. Compilation authority remains false. Provider
infrastructure compilation != synthetic scenario compilation authority.

These dependencies block operational activation without making the provider
binding or semantic first-behavior boundary ambiguous. If either of those two
boundary decisions cannot be upheld, the result must instead be
`CONTRACT_UNRESOLVED`. No implementation may work around uncertainty.

Authorization issuance != lease issuance != lease consumption != behavior
execution. The old `CONSUMPTION_POLICY` continues to name SANDBOX.2 and JAVA.1
verbatim; this new policy neither rewrites nor reinterprets that history.

## One-shot state, identity and atomicity

Reuse precisely `ISSUED`, `CONSUMED`, `INVALIDATED`. Only `ISSUED -> CONSUMED` and
`ISSUED -> INVALIDATED` are permitted; both targets are permanent terminal states.
One authorization has at most one lease, including after collection, terminal
transition or downstream failure. No refund, restore, reset, persistence/reload
or fresh issuance on an old tombstone exists. A proposed new semantic state
requires a requirement-evolution stop instead of adapter expansion.

The permanent map key is the exact authenticated tuple
`(owner_identity, phase_id, schema_version, issuing_pid, authorization_id)` from
the original pinned authorization. The maps belong only to this new owner.
Pinned `authorization_id` is real; old `issuance_id` is not assumed. Fingerprint,
proof context, provider projection or caller string is never an alternate key
that could reopen issuance. Keep the authorization-to-lease binding and lease
record tombstones for the issuing process lifetime, including dead handles.

One independent process-local lock covers public upstream authentication,
duplicate check, lease construction/signing and installation of both records.
Installation must be atomic: an exception cannot publish a partial key/record.
The same lock protects read authentication and each terminal transition's
reauthentication, scope/provider/policy/state/precondition checks, signing and
single record replacement. Competing consumes, or consume versus invalidate,
permit at most one terminal commit. Stale readiness checks reserve nothing.
Reject a foreign PID before acquiring a potentially inherited lock.

Use an immutable issuance projection and stable authenticated issuance
fingerprint/evidence digest. Initial state is bound there. Current state is
separately authenticated in a private immutable record signed together with
that issuance projection; transition replaces the record, not the public lease
or upstream auth. The stable fingerprint must not change with terminal state.
Exact live lease identity can use a weak identity reference like the old owner,
while permanent records strongly retain the original authorization. Collection
does not remove tombstones. Terminal handles remain inspectable only while all
retained original upstream evidence still authenticates.

## Authentication and authority

Use an independent private secret and distinct domain
`CATTUS:SYNTH.AUTH.LIFECYCLE.PINNED.1:exact-execution-lease:v1`, with NUL-separated
role/payload boundaries. HMAC-SHA256 is allowed; reuse of any old or pinned auth
secret/domain is prohibited. Canonical JSON uses sorted keys, compact separators,
UTF-8, no NaN, and exact primitive/nested types before serialization. Separate
roles authenticate evidence digest, stable fingerprint and current record.

Exact class, original live identity, retained original upstream, process and
signed records are mandatory. Reject copies, deepcopy, replace, equivalent manual
constructors, JSON/report reconstructions, ID/fingerprint strings, wrappers,
subclasses, incomplete exact objects and primitive equality aliases. Exported
JSON is report-only and contains no secret, private signature or registry record.

On `ISSUED`, `lease_issued=true` and `runtime_activation_consumed=false` are
distinct. The latter is derived from authenticated current state; it is true
only after `CONSUMED`, never a mutable or immutable public issuance counter.
The lease represents at most one exact synthetic activation capability. Runtime,
real task, repository write, Apply, network, host mounts, shell, arbitrary Java,
class/method/source/command, repository Java, executor, BANK, reflection execution
and compilation authority remain false in every state. Consumption grants no
broader authority and no general executor/reflection permission.

## Conceptual public operations and typed failure

The six complete per-operation contracts in `contract.json` define exact inputs,
authentication, source states, outputs, mutation, atomicity, terminal behavior and
errors. No functions or classes are implemented here.

| Proposed operation | Exact input types | Output / state effect |
| --- | --- | --- |
| `issue_pinned_synthetic_runtime_execution_lease` | Original pinned auth | New original pinned lease, `ISSUED`; permanent one-shot install |
| `validate_pinned_synthetic_runtime_execution_lease` | Original pinned lease, optional original pinned auth | Same original lease; any authentic semantic state; no mutation |
| `pinned_synthetic_runtime_execution_lease_state` | Original pinned lease, optional original pinned auth | Authenticated state string; no mutation |
| `check_pinned_synthetic_runtime_execution_lease_preconditions` | Original pinned lease and original pinned auth | Immutable report-only readiness result; no reservation or mutation |
| `consume_pinned_synthetic_runtime_execution_lease` | Original pinned lease and original pinned auth | Same lease after one terminal consume; unresolved downstream proof rejects |
| `invalidate_pinned_synthetic_runtime_execution_lease` | Original pinned lease, optional original pinned auth | Same lease after terminal invalidation; no activation readiness needed |

An omitted optional upstream uses only the retained original. A supplied upstream
must be exactly that object. Consumer readiness proof APIs/types are intentionally
not fabricated: their absence raises `PROOF_UNRESOLVED`, leaves state unchanged
and blocks activation. This contract defines no operational integration adapter.

Follow the repository typed `ValueError` convention with `.code` and `.reason`.
Use the distinct categories `PINNED_AUTH_UNAUTHENTICATED`,
`PINNED_AUTH_SCOPE_MISMATCH`, `PINNED_PROVIDER_PROVENANCE_MISMATCH`,
`DUPLICATE_LEASE_ISSUANCE`, `LEASE_UNAUTHENTICATED`, `LEASE_WRONG_PROCESS`,
`LEASE_NOT_ISSUED`, `LEASE_ALREADY_CONSUMED`, `LEASE_INVALIDATED`,
`ACTIVATION_PRECONDITION_UNSATISFIED`, `PROOF_UNRESOLVED`.
The consumed/invalidated categories are specific `LEASE_NOT_ISSUED` conditions
for authentic terminal records; forged or unknown states fail authentication.
Readiness validation failures raise typed authentication/scope/provenance errors.
Authentic ISSUED with unresolved consumer proof reports lease-local readiness and
false behavioral readiness with `PROOF_UNRESOLVED`. Authentic terminal leases
report both readiness flags false with their specific terminal category; mutating
operations raise those terminal errors. Authentication/state reads accept authentic
terminal evidence. Signature/record-integrity failures remain authentication
errors; semantic scenario/policy or provider mismatches keep their separate codes.

Preserve upstream public error codes/reasons. Map explicit scope errors to scope,
provider/graph/requirement errors to provenance, and identity/HMAC/original-object
errors to authentication. An unfamiliar validator failure is unresolved proof,
never success. Do not relabel a semantic mismatch as an authentication failure
or infer successful authentication from a rejected projection. Any rejected check
or unresolved dependency publishes no lease/transition.

## Reflection projection and old-owner isolation

The stable audit projection includes lease ID/fingerprint, authenticated state
API, scenario phase/ID, source kind/hash/size/definition, exact invocation and
observation, pinned auth ID/fingerprint/proof context, and original auth binding
observable by public lease validation with that exact original auth. It supports
a future reflection audit. Reflection-compatible projection != reflection
acceptance. The frozen reflection owners still require the old public validators,
exact owners/types and retained objects. No acceptance or interchangeability is
claimed; do not design solely to mimic old fields.

Separate types, secrets, locks, maps, receipts and tombstones are mandatory.
Never modify the old lifecycle registry; insert pinned objects into old auth;
call private old signing helpers; fabricate old auth/leases; change old policy,
receipts or tombstones; or modify old reflection owners. Preserve SYNTH.AUTH.1,
SYNTH.AUTH.PINNED.1/1R, SYNTH.AUTH.LIFECYCLE.1, all three SYNTH.REFLECT phases,
all RUNTIME.JAVA.PINNED phases, executor attempts and registry/reversal history.
Never repin, stash, reset or clean.

The compatibility declaration is frozen as:

```
state_machine_semantics_reused = true
old_implementation_api_reused = false
old_authorization_domain_reused = false
old_lease_type_reused = false
old_lifecycle_history_preserved = true
pinned_owner_additive = true
```

## Architecture evidence and validation

Evidence is source inspection, not fresh issuance or operational proof:

- `core/synthetic_runtime_authorization_pinned.py:115-130`: existing public
  provider projection; `145-164`: original graph/proof-only requirement checks;
  `261-287`: unchanged exact original-object public validation.
- `core/runtime_java_pinned_requirement.py:222-232`: pinned requirement,
  immutable provider and SANDBOX.2 policy identities.
- `core/synthetic_runtime_authorization_lifecycle.py:38-47`: unchanged old
  consumption/compilation policies; `184-294`: old authenticated record,
  atomic issuance/read/transition and stable fingerprint semantics.
- `core/synthetic_reflection_execution_lifecycle.py:19-22,37-45,91-117`:
  exact old owners and established readiness/consumption/behavior ordering.
- `core/behavioral_diagnostic_executor_lifecycle_retry.py:154-158,195-202`:
  no effectful executor and preserved historical Java mismatch stop.
- `docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_1/SYNTH_AUTH_LIFECYCLE_1.md` and
  `SYNTH_AUTH_LIFECYCLE_PINNED_COMPAT_1/reflection_dependencies.md`: compilation
  classification unresolved and no zero-issuance frozen reflection lifecycle
  test node exists.

Pure tests verify the semantic contract, exact upstream boundaries, state table,
error distinctions, lock requirements, projection completeness and historical
owner isolation without issuing or consuming handles. Frozen safe selections
cover pinned auth, old lifecycle, compat audit, reflection dependencies and
historical executor stops. Full issuance-dependent frozen suites are not run.
Validation also compares actual registry/picker baseline versus after, checks
benchmarks, compiles Python in memory, checks JSON/whitespace and git diff, and
compares existing bytes and original historical pins without replacing them.

All phase operational counts must be zero: Docker, SANDBOX2, JAVA1C, pinned
provider issuance, authorization/lease issuance, lease consumption/invalidation,
SyntheticStateBox, reflection, BANK, EXECUTOR.1R, Apply and repository runtime
writes. New authored contract/test/evidence files are validation artifacts.
See the final report and `validation_summary.json` for measured checks and
preserved baseline failures. Successful contract freeze means: "The additive
pinned execution-lease owner boundary is semantically frozen, while no
implementation or lease exists."

## Recorded contract-freeze result

`SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1_COMPLETE`. Provider provenance and the
semantic first-behavior consumption boundary are defined; the two downstream
dependencies above remain explicit activation blockers, not new lifecycle states.

| Check | Recorded result |
| --- | --- |
| Pure contract and safe frozen selections | 71 passed, 0 failed |
| Registry/picker before and after | 299 collected; 292 passed, same 7 pre-existing failures; all compared projections and failure IDs identical |
| Benchmarks `--check` | 54 checked, 0 errors |
| Python compilation in memory | 1,349 files, 0 errors; no bytecode written |
| JSON, authored whitespace and git diff | Passed |
| Starting workspace preservation | All 2,289 baseline paths retain their starting bytes or pre-existing absence |
| Original historical manifests | 23 checks, 2,257 unique files, zero drift; no replacement pins |
| Final guarded workers | All process/network/runtime-write/issuance/consumption/execution attempt counters zero |
| Operational phase effects | All required counts zero; no owner, authorization, provider proof or lease issued |

The first guarded selection denied a directory scan in a preservation test and
entry into a historical invalid-input issuer before its body executed. No
capability or runtime effect resulted. The test now uses baseline paths and the
unsafe frozen node is excluded. `focused_initial_guarded.json/txt` and
`validation_summary.json` retain those denials alongside the passing final run.
This is selected pure coverage with preserved existing registry failures; it is
not a claim that every frozen issuance-dependent suite or the full suite passed.
