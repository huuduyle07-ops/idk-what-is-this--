# SYNTH.AUTH.LIFECYCLE.PINNED.1A

2026-10-13 KST.

**SYNTH_AUTH_LIFECYCLE_PINNED_1A_COMPLETE**

The additive pinned lifecycle owner is implemented and pure-validated against the frozen contract. No operational lease has been issued or consumed.

## Identity and API

Owner: `core.synthetic_runtime_authorization_pinned_lifecycle`. Type: `PinnedSyntheticRuntimeExecutionLease`. Schema: `synthetic_runtime_execution_lease_pinned_1_v1`.

- `issue_pinned_synthetic_runtime_execution_lease`
- `validate_pinned_synthetic_runtime_execution_lease`
- `pinned_synthetic_runtime_execution_lease_state`
- `check_pinned_synthetic_runtime_execution_lease_preconditions`
- `consume_pinned_synthetic_runtime_execution_lease`
- `invalidate_pinned_synthetic_runtime_execution_lease`

Every operation authenticates the retained original through the unchanged public pinned validator under the independent owner lock. Provider decision B binds all 15 authenticated public provider fields. No caller provider, scenario override, readiness Boolean/JSON, or compatibility bridge is accepted.

## State and readiness

| Source state | Validation/state read | Local / behavioral readiness | Consume | Invalidate |
| --- | --- | --- | --- | --- |
| ISSUED | Original / ISSUED | true / false; PROOF_UNRESOLVED | PROOF_UNRESOLVED; unchanged | INVALIDATED |
| CONSUMED | Original / CONSUMED, if upstream authenticates | false / false; LEASE_ALREADY_CONSUMED | LEASE_ALREADY_CONSUMED | LEASE_ALREADY_CONSUMED |
| INVALIDATED | Original / INVALIDATED, if upstream authenticates | false / false; LEASE_INVALIDATED | LEASE_INVALIDATED | LEASE_INVALIDATED |

Only ISSUED -> CONSUMED and ISSUED -> INVALIDATED are defined. Consumption machinery exists but the unresolved consumer/source/compile contract blocks its commit. Invalidation needs no behavioral readiness. Terminal tombstones survive collection for the owner process lifetime; no refund, reissue or reset exists. Readiness is an immutable report, never a capability, token or reservation.

## One-shot authentication and atomicity

The key is `(authorization.owner_identity, authorization.phase_id, authorization.schema_version, authorization.issuing_pid, authorization.authorization_id)` from the exact public-validator return. Fingerprint, proof context and provider fingerprint are never alternate keys.

Domain: `CATTUS:SYNTH.AUTH.LIFECYCLE.PINNED.1:exact-execution-lease:v1`. Roles: `activation-policy`, `lease-evidence`, `lease-fingerprint`, `lease-record-hmac`. Strict canonical JSON uses sorted keys, compact separators, no NaN, UTF-8 and NUL-separated domain/role/payload. Public digests use domain-framed SHA256; private current-state records use independent-secret HMAC-SHA256. No secret or record signature is exported.

Activation policy: `SYNTH.AUTH.LIFECYCLE.PINNED.1:exact-decrement-3-activation:v1`. Canonical digest: `0189c9541faf0d45cc1963ccdb4eab749c4ba347a5f553d02d46679a536c74e9`.

Issuance constructs/signs before one `_STORE` replacement publishes the permanent key and signed ISSUED record together. A terminal transition reauthenticates and signs before one replacement. Reads use the same lock; wrong PID rejects before the lock. Failure injection preserves the original store. Race tests verify one duplicate-issuance commit, one consume/invalidate terminal commit (invalidation only), and one commit for competing invalidations. Public leases remain immutable and their issuance fingerprints remain stable.

## Authority matrix

| Authority | ISSUED | CONSUMED | INVALIDATED |
| --- | --- | --- | --- |
| runtime_authority | false | false | false |
| real_task_runtime_authority | false | false | false |
| repository_write_authority | false | false | false |
| apply_authority | false | false | false |
| network_authority | false | false | false |
| host_mount_authority | false | false | false |
| shell_authority | false | false | false |
| arbitrary_java_authority | false | false | false |
| arbitrary_class_authority | false | false | false |
| arbitrary_method_authority | false | false | false |
| arbitrary_source_authority | false | false | false |
| repository_java_authority | false | false | false |
| arbitrary_command_authority | false | false | false |
| executor_authority | false | false | false |
| BANK_authority | false | false | false |
| reflection_execution_authority | false | false | false |
| compilation_authority | false | false | false |

`lease_issued=true` is an immutable issuance fact. `runtime_activation_consumed` is derived only from authenticated current state == CONSUMED. Provider infrastructure compilation grants no scenario compilation authority. Reflection acceptance is not claimed.

## Rejection matrix

| Input/failure | Result |
| --- | --- |
| Auth copy/deepcopy/replace/manual/JSON/report/ID/fingerprint/wrapper/subclass/old epoch | PINNED_AUTH_UNAUTHENTICATED; supplied nonoriginal auth to lease API is LEASE_UNAUTHENTICATED |
| Lease copy/deepcopy/replace/manual/JSON/report/ID/fingerprint/wrapper/subclass/old type/schema relabel | LEASE_UNAUTHENTICATED |
| Wrong process/PID | LEASE_WRONG_PROCESS before lock |
| Scenario/policy mismatch or primitive equality alias | PINNED_AUTH_SCOPE_MISMATCH |
| Provider projection mismatch | PINNED_PROVIDER_PROVENANCE_MISMATCH |
| Unknown public-validator failure | PROOF_UNRESOLVED; no publication/transition |
| Caller Boolean/JSON readiness/override | Rejected by exact input/signature; no transition |

Known upstream codes and reasons are retained. Terminal errors retain parent category LEASE_NOT_ISSUED. ACTIVATION_PRECONDITION_UNSATISFIED remains the category for a future defined authenticated false consumer prerequisite; the absent consumer contract currently yields PROOF_UNRESOLVED.

## Pure validation and preservation

- Focused implementation: 144 passed, zero failed/skipped.
- Frozen safe baseline: 71 passed. After: 70 passed; one historical test asserting module absence is excluded after implementation, with its bytes unchanged.
- Registry/picker: 292 passed and the same 7 existing baseline failures; all compared results, summary and picker output unchanged.
- Benchmark --check, in-memory Python compilation, strict JSON, whitespace and git diff --check passed.
- All 1463 baseline historical files are byte-identical. Old lifecycle/auth/pinned auth/provider/reflection owners, registries, consumption policy, historical attempts and frozen artifacts are unchanged. No phase registration occurred.

Tests use isolated source-loaded owner/upstream copies and an inert public-validator seam. Production validators are unchanged and production registries are not seeded. The CONSUMED inspection fixture is only a signed isolated historical record; no positive consume or fake consumer-readiness object is tested. All effect-guard counters are zero. Full issuance-dependent suites were not run and are not claimed.

Operational lease issued: **false**. Operational lease consumed: **false**. Reflection acceptance claimed: **false**. Docker, SANDBOX2, JAVA1C, pinned provider/auth issuance, operational lease issuance/consumption/invalidation, SyntheticStateBox, reflection, BANK, EXECUTOR.1R, Apply and repository runtime writes: **all zero**.

## Source hashes

Scenario source: `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302`. Definition: `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d`.

| Source | SHA256 |
| --- | --- |
| core/synthetic_runtime_authorization_pinned_lifecycle.py | `235f630b6e888e55b0fae1fda7699c4a962c0f003feb0bf08e7885c91d63e3c4` |
| tests/test_synthetic_runtime_authorization_pinned_lifecycle.py | `fd5025dec5782363bacae14c48683dfd997cbc09789dbe0682fd16167920a30d` |
| docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/contract.json | `dccb2d374d28cb3754e11ac8f46f8b667cc164bb165f27af62bdf8b7b15d9473` |
| core/synthetic_runtime_authorization.py | `219c868080a6cca3f02dfcfbd4729f012439b8af1e8db5762c09760a41100b88` |
| core/synthetic_runtime_authorization_lifecycle.py | `dc7cc307a17c63cf65eea0e898015140806ca98e2614c391423c50adfd0e6029` |
| core/synthetic_runtime_authorization_pinned.py | `c216aaba910b5907d754f51358f1fca4ba4c77bfd38692de7cc192b5e263516c` |
| core/runtime_java_pinned_provider.py | `bca4a46363a27e23fba60cbc556eb30e3f2b6e03f4ed6e95c81ac7231756ddaa` |
| core/runtime_java_pinned_requirement.py | `2f070084b7a62a46bce33cd5dcdf0a06236bfdcc21d5d82ed508ff4b961b8af1` |
| core/synthetic_read_only_reflection.py | `d24422b68c0eae96890a7e63a177ebc8adcbd64300bf7cfb42d3ada041a5d5bc` |
| core/synthetic_reflection_execution_admission.py | `ae6d60d7ef418cff366317ad4507d0f2de93f2aa9d188e8e12d453c66ed77b19` |
| core/synthetic_reflection_execution_lifecycle.py | `c2b85e845f79332b83f3c17e754ba290db739e9c19378317fed16c6402e686ba` |

Evidence: [machine report](SYNTH_AUTH_LIFECYCLE_PINNED_1A_REPORT.json), [validation summary](validation_summary.json), [implementation tests](implementation.json), [preservation](preservation_check.json), [registry comparison](registry_comparison.json), [source review](implementation_review.json).

STOP: implementation and pure validation only; no live authorization/provider/lease attempt.
