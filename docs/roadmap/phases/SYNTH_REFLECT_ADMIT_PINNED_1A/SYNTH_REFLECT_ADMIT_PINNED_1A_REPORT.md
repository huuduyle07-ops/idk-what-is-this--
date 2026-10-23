# SYNTH.REFLECT.ADMIT.PINNED.1A implementation report

Date: 2026-10-13, Asia/Seoul. Admission implementation only.

Status: `SYNTH_REFLECT_ADMIT_PINNED_1A_COMPLETE`.
The additive pinned reflection admission owner is implemented and pure-validated.
No operational admission, reflection lease or reflection effect exists.

## Owner and public boundary

| Binding | Value |
| --- | --- |
| Module | `core.synthetic_reflection_execution_admission_pinned` |
| Exact type | `PinnedSyntheticReflectionExecutionAdmission` |
| Phase | `SYNTH.REFLECT.ADMIT.PINNED.1` |
| Schema | `synthetic_reflection_execution_admission_pinned_1_v1` |
| Authentication domain | `CATTUS:SYNTH.REFLECT.ADMIT.PINNED.1:exact-reflection-admission:v1` |
| Typed error | `PinnedSyntheticReflectionExecutionAdmissionError` |

The type is an independent frozen dataclass, never an alias/subclass of the old
admission. The owner has its own 32-byte secret, process-local lock, store,
permanent slot map and HMAC records. SHA-256 public evidence/fingerprints and
HMAC-SHA256 private records use domain + NUL + role + NUL + strict canonical JSON.
Exact nested types, sorted keys, compact separators, no NaN and UTF-8 are enforced.
No secret, record HMAC or registry contents appear in public reports.

Implemented public APIs:

- `issue_pinned_synthetic_reflection_execution_admission(authorization, runtime, request, role)`
- `validate_pinned_synthetic_reflection_execution_admission(admission, authorization=None, runtime=None, request=None, role=None)`
- `pinned_synthetic_reflection_execution_admission_fingerprint(admission)`
- `pinned_synthetic_reflection_request_satisfies_runtime(authorization, runtime, request, role)`
- `pinned_synthetic_reflection_admission_satisfies_executor(admission, authorization, runtime, request, role)`
- Authenticated `admission.fingerprint` and report-only `admission.as_dict()`.

There is no consume, invalidate, reflection-state or reflection-lease API.

## Request decision and exact graph

Request decision A is preserved. The owner requires the exact unchanged
`SyntheticReflectionRequest` and unchanged public request validator. Its role
literals map only to `BEFORE / exact_private_state_before` and
`AFTER / exact_private_state_after`. No pinned request class or role alias exists.
Request schema, source bytes, validator and old-auth predicate are unchanged.
The old-auth compatibility predicate is never called; no old authorization or
registry entry is fabricated.

The pinned compatibility predicate requires the same original request, pinned
authorization and pinned runtime lease to return from their unchanged public
validators. Runtime validation receives the exact original authorization. It
checks fixed scenario/source/definition/invocation/field/read scope, exact
primitive types and semantic role, and authenticates current state through the
public pinned runtime state API. Compatibility is truth only, accepts any
authenticated runtime state and publishes nothing. Executor preparation
compatibility additionally requires current runtime `ISSUED`, while behavioral
readiness remains false with `PROOF_UNRESOLVED`.

Admission records strongly retain exact original auth/runtime/request and weakly
retain the admission. Every public validation/fingerprint/report operation
reauthenticates all three originals. Optional supplied objects must be the
retained originals by `is`; omitted inputs use retained objects. Scalar
projections never substitute for these originals. Validation remains available
after authenticated runtime `CONSUMED` or `INVALIDATED`, with a stable unchanged
admission fingerprint; this does not imply preparation readiness.

Provider provenance is inherited transitively through runtime validation ->
pinned authorization validation -> retained provider graph. There is no provider
argument, direct PINNED.1C validation or independent reflection provider gate.

## Permanent slots and publication

The permanent key binds admission owner/phase/schema/PID, authenticated
authorization owner/phase/schema/PID/authorization ID, authenticated runtime
owner/phase/schema/PID/lease ID, semantic role and exact fixed read scope.
Request ID/fingerprint, renderer fingerprint, authorization fingerprint/proof
context and runtime fingerprint are excluded from the slot key.

BEFORE and AFTER have independent slots: at most one of each for the same exact
runtime graph. A fresh same-role request, admission collection or terminal runtime
state never reopens a slot. Permanent records retain the originals even after
admission collection.

Both roles require authenticated runtime `ISSUED` to issue. `CONSUMED` and
`INVALIDATED` raise `PINNED_RUNTIME_STATE_MISMATCH`; unresolved state raises
`PROOF_UNRESOLVED`. Under one independent owner lock, issuance authenticates the
request/auth/runtime, checks state and scope, derives/checks the slot, constructs
and signs the complete new store, performs a final public authenticated `ISSUED`
check, then publishes by one store replacement. Failure before publication leaves
the original store unchanged. Wrong PID rejects before the owner lock.

There is no upstream private lock access or cross-owner transaction. The final
public state check is an eligibility snapshot; runtime may change afterward.
Future lifecycle/consumer gates must recheck their own eligibility.

## Immutable projection and renderer binding

The signed projection binds owner/phase/schema/PID/admission ID, semantic role and
request literal; authorization owner epoch/PID/ID/fingerprint/proof context;
runtime owner epoch/PID/lease ID/stable fingerprint; runtime state at issuance
`ISSUED`; scenario phase/ID; source kind/hash/239-byte size/definition; exact
`boolean SyntheticStateBox.decrement(int)` and argument `3:int`; field
`SyntheticStateBox.value:int` and operation `read_exact_bound_field`; request
issuance ID/PID/validated fingerprint; renderer identity/helper hash/fingerprint;
admission evidence digest/stable fingerprint; and authority matrix.

Renderer identity remains
`SYNTH.REFLECT.1.render_synthetic_read_only_reflection`. Fixed UTF-8 helper hashes
are established and checked from the unchanged renderer's source literals:

| Role | Helper SHA-256 |
| --- | --- |
| BEFORE | `c88aeea914c88ef17a335a184abe6d5b618a9c0c70a7121621ba67edd9919531` |
| AFTER | `4d85951e886bfedabae50c7f64e8e0fa4985e8fa515e4edab9af0a355b10f4ea` |

The owner derives independent `renderer-evidence` digests over renderer identity,
phase, schema and helper hash. The renderer is never invoked. Text and expected
10/true/7 values are not measurements, execution permission or compilation
authority.

## Authority and rejection matrix

Admission permits preparation of exactly one role-specific read-only reflection
effect through a future lifecycle owner. Admission itself performs no read.
Runtime, real-task runtime, repository write, Apply, network, host mount, shell,
arbitrary Java/reflection/class/method, private method, field write, enumeration,
executor, BANK, constructor reflection, arbitrary class loading and compilation
authority remain false. Behavioral activation readiness is false.

| Rejection | Typed category |
| --- | --- |
| Foreign/copy/nonoriginal pinned auth | `PINNED_AUTH_UNAUTHENTICATED` |
| Foreign/copy/nonoriginal runtime lease | `PINNED_RUNTIME_LEASE_UNAUTHENTICATED` |
| Known upstream auth scope | `PINNED_AUTH_SCOPE_MISMATCH` |
| Known retained provider graph failure | `PINNED_PROVIDER_PROVENANCE_MISMATCH` |
| Authentic runtime differs from ISSUED | `PINNED_RUNTIME_STATE_MISMATCH` |
| Foreign/copy/nonoriginal request | `REFLECTION_REQUEST_UNAUTHENTICATED` |
| Fixed scenario/source/invocation/field/type mismatch | `REFLECTION_SCOPE_MISMATCH` |
| Permanent role slot already used | `DUPLICATE_REFLECTION_ADMISSION` |
| Admission clone/reconstruction/report/ID/wrapper/subclass/old type or wrong supplied original binding | `REFLECTION_ADMISSION_UNAUTHENTICATED` |
| Unsupported semantic role or request-role disagreement | `REFLECTION_ROLE_MISMATCH` |
| Foreign owner/original issuing PID | `REFLECTION_WRONG_PROCESS` |
| Unknown validator failure or unavailable authenticated state/fingerprint | `PROOF_UNRESOLVED` |

Known upstream code/reason are retained in typed errors. Predicate rejection
returns false. Known scope/provider/state failures retain their categories.

## Validation evidence and historical preservation

The [isolated admission results](inert_admission_tests.json) record 140 passing
focused tests, zero failures and zero effect-denial attempts. One third-party
Python deprecation warning was emitted. The suite exercises structural positive issuance,
all original validators and same-object returns, copy/reconstruction rejection,
role/type/scope gates, permanent slots and collection, terminal stable reads,
final state change and failed-signing nonpublication, concurrent duplicate
publication, renderer pins, error preservation and false authority. Fixtures
source-load independent owner copies, never seed production registries and never
issue upstream capabilities or operational admissions.

The [safe validation summary](safe_validation_summary.json) records:

- Frozen contract source/AST tests: 152/152 passed.
- Selected historical source/AST tests: 14/14 passed; additional checks: 10/10.
- Benchmark `--check`: 54 cases checked, zero errors.
- Registry/picker baseline versus after: identical projections and test nodes,
  292/299 passed with the same seven preexisting failures. Those failures were
  preserved, not repaired in this phase.
- In-memory Python compilation/AST parse, UTF-8 JSON, whitespace and
  `git diff --check`: passed.
- Historical preservation: 2,410 preexisting files unchanged against the initial
  workspace snapshot, including existing untracked history.

Full issuance-dependent frozen suites were not run. Safe historical checks
authenticate source assertions, not operational capabilities. Independent
contract review completed with no remaining actionable findings.

| Required preservation/scope result | Value |
| --- | --- |
| Old admission/request sources changed | false |
| Pinned auth/runtime owners changed | false |
| Provider owners/executor/registry/reversal history changed | false |
| Pinned reflection lifecycle owner implemented | false |
| Operational admission issued | false |
| Production registry seeded | false |
| Production validators changed | false |
| Behavioral readiness resolved | false |
| Compilation authority | false |

Required operational effects remain zero: Docker, SANDBOX2, JAVA1C, provider
issuance, pinned authorization issuance, pinned runtime lease issuance, runtime
consume/invalidate, operational reflection request issuance, operational pinned
admission issuance, reflection lease issuance/consume/invalidate, reflection read,
SyntheticStateBox, BANK, EXECUTOR.1R, Apply and repository runtime writes.

The completion status and measured focused test counts are recorded in
[the machine-readable report](SYNTH_REFLECT_ADMIT_PINNED_1A_REPORT.json).
Success means only: "The additive pinned reflection admission owner is implemented
and pure-validated. No operational admission, reflection lease or reflection
effect exists." Stop; do not implement the pinned reflection lifecycle here.
