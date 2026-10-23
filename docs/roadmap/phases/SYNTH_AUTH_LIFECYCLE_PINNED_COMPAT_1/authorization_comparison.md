# SYNTH.AUTH.LIFECYCLE.PINNED.COMPAT.1 authorization comparison

2026-10-11 KST. This is a static audit of the frozen old and pinned authorization owners. No source was imported or executed for this comparison. No authorization, provider proof, runtime execution lease, reflection lease, or runtime attempt was issued or consumed. Existing source, tests, receipts, diagnostics, and historical artifacts were only read.

The exact scenario is unchanged. The authorization types, schemas, owner domains, provider requirements, and proof requirements are different. Field agreement cannot establish interchangeable authentication or authorize direct reuse of the old lifecycle API.

## Exact scenario comparison

| Identity or expectation | SYNTH.AUTH.1 | SYNTH.AUTH.PINNED.1 | Result |
| --- | --- | --- | --- |
| Scenario ID | `synthetic.EXECUTOR.1R.decrement_3` | `synthetic.EXECUTOR.1R.decrement_3` | Same exact scenario |
| Scenario phase | `PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R` | Recovered from the retained old spec; not separately exported in `PinnedSyntheticScenarioIdentity` | Same spec lineage, different projection shape |
| Source SHA-256 | `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302` | `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302` | Exact equality |
| Source size | `239` bytes | `239` bytes | Exact equality |
| Definition SHA-256 | `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d` | `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d` | Exact equality |
| Class | `SyntheticStateBox` | `SyntheticStateBox` | Exact equality |
| Public method | `decrement` | `decrement` | Exact equality |
| Signature | Contract renders `boolean SyntheticStateBox.decrement(int)` | Explicit `method_signature="boolean SyntheticStateBox.decrement(int)"` | Same contract; old has no explicit signature field |
| Arguments | `(3,)` | `(3,)` | Exact tuple and primitive integer |
| Argument types | `("int",)` | `("int",)` | Exact equality |
| Return type | `boolean` | `boolean` | Exact equality |
| Private field owner | `SyntheticStateBox` | `SyntheticStateBox` | Exact equality |
| Private field member | `value` | `value` | Exact equality |
| Private field declared type | `int` | `int` | Exact equality |
| Expected BEFORE | `10` | `10` | Expectation only |
| Expected return | `True` | `True` | Exact bool; expectation only |
| Expected AFTER | `7` | `7` | Expectation only |
| Sandbox profile | `runtime_sandbox_2_v1` | `runtime_sandbox_2_v1` | Same frozen sandbox requirement |
| Sandbox policy SHA-256 | `5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75` | `5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75` | Exact equality |

The old owner defines the source bytes and constants in `core/synthetic_runtime_authorization.py:19-47`, invocation and observation contracts in `:72-99`, and the exact fixed spec in `:135-146`. Its public spec validator requires the exact owner-supported object, recursively exact types, and the complete fixed canonical projection (`:154-174`).

The pinned owner obtains that unchanged public spec and exact source through the old factories and validator, checks size/hash, and renders the 16-field scenario projection in `core/synthetic_runtime_authorization_pinned.py:75-111`. It does not reinterpret the old spec's Java requirement. Frozen tests assert every literal scenario equality and signature in `tests/test_synthetic_runtime_authorization_pinned.py:109-143`; old assertions are in `tests/test_synthetic_runtime_authorization.py:69-115`.

## Owner, schema, provider, and proof comparison

| Boundary | SYNTH.AUTH.1 | SYNTH.AUTH.PINNED.1 |
| --- | --- | --- |
| Owner implementation | `core.synthetic_runtime_authorization` | `core.synthetic_runtime_authorization_pinned` |
| Owner phase | `SYNTH.AUTH.1` | `SYNTH.AUTH.PINNED.1` |
| Owner field | `issuer_phase_id="SYNTH.AUTH.1"`; no `owner_identity` field | `owner_identity="core.synthetic_runtime_authorization_pinned"`, `phase_id="SYNTH.AUTH.PINNED.1"` |
| Exact authorization class | `SyntheticRuntimeAuthorization` | `PinnedSyntheticRuntimeAuthorization` |
| Authorization schema | `synthetic_runtime_authorization_v1` | `synthetic_runtime_authorization_pinned_1_v1` |
| Old scenario-spec schema | `synthetic_runtime_scenario_spec_v1` | Original spec retained for scenario identity only |
| Authorization status | `SYNTHETIC_RUNTIME_AUTHORIZATION_ISSUED` | `SYNTH_AUTH_PINNED_1_COMPLETE` |
| Required Java profile | `RUNTIME.JAVA.1` | `RUNTIME.JAVA.PINNED.1` |
| Required Java schema | `runtime_java_1_v1` | `runtime_java_pinned_1_v1` |
| Provider proof phase | No authenticated provider proof required by old auth issuance/validation | `RUNTIME.JAVA.PINNED.1C` |
| Provider proof schema | No provider proof field | `runtime_java_pinned_provider_1c_v1` |
| Provider proof owner | No provider proof field | `core.runtime_java_pinned_provider` |
| Exact proof condition | None in old auth owner | Original authenticated root, complete provider graph, complete status, `exact_provider_proven is True`, authority flags false |
| Target image | No provider image field | `sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a` |
| Authorization local ID | Random 64-hex `issuance_id` | Random 64-hex `authorization_id` |
| Authorization proof context | No separate proof-context field | Independent random 64-hex `proof_context_id` |
| Provider proof context | No provider proof-context field | Root's separate `proof_context_identity`, projected with its receipt ID, fingerprint, evidence digest, controller evidence, and cleanup evidence |
| Process field | `issuer_process_id` | `issuing_pid` |
| Retention | `_ISSUED_HANDLES`, a `WeakValueDictionary`, retains identity while the original auth is live | `_LIVE` retains exact auth, original spec, original provider outcome, original root, original binding wrapper, and ten original provider upstream objects |
| Public validator | `validate_synthetic_runtime_authorization(authorization, *, spec, source)` | `validate_pinned_synthetic_runtime_authorization(authorization, *, provider_outcome=None)` |

Old constants and dataclass fields: `core/synthetic_runtime_authorization.py:19-31,48-50,196-242`. Old issuer checks only the supported spec and exact supplied source before creating/signing the local handle (`:282-289`); its imports do not include a provider owner (`:9-17`).

Pinned constants and fields: `core/synthetic_runtime_authorization_pinned.py:26-34,114-130,184-220`. Provider authentication and requirement checks are at `:133-181`; exact provider graph retention is at `:340-344`, and reauthentication on every authorization validation is at `:273-278`. The target image literal is defined in `core/runtime_java_pinned_requirement.py:13`.

`RUNTIME.JAVA.REQUIREMENT.PINNED.1` is metadata only and authenticates no object (`core/runtime_java_pinned_requirement.py:1-5`). Its requirement profile/schema are `RUNTIME.JAVA.PINNED.1` and `runtime_java_pinned_1_v1` (`:9-11`). The proof owner's distinct phase/schema/owner constants are in `core/runtime_java_pinned_provider.py:30-32`. The pinned auth checks proof identity/status and the different requirement identity separately (`core/synthetic_runtime_authorization_pinned.py:150-164`). A successful proof is evidence, not runtime authority or an execution lease.

The pinned requirement retains fixed JAVA.1C infrastructure proof obligations (`core/runtime_java_pinned_requirement.py:89-100`). That does not make the old `RUNTIME.JAVA.1/runtime_java_1_v1` requirement identical to the new pinned requirement. Frozen tests explicitly require inequality (`tests/test_synthetic_runtime_authorization_pinned.py:138-143`) and reject attempts to relabel the pinned requirement as old Java (`:254-289`).

## HMAC and process-local authentication

Both owners use HMAC-SHA256 and separate random module-local 32-byte secrets. Their authentication domains are different.

| Authentication property | SYNTH.AUTH.1 | SYNTH.AUTH.PINNED.1 |
| --- | --- | --- |
| Secret | Independent `_SECRET=secrets.token_bytes(32)` | Independent `_SECRET=secrets.token_bytes(32)` |
| Canonical payload | Sorted compact JSON; excludes `_signature` | Sorted compact JSON; excludes `_signature`, expands scenario/provider dataclasses |
| Explicit byte domain | None; HMAC directly covers canonical payload | `b"CATTUS:SYNTH.AUTH.PINNED.1:exact-scenario-authorization:v1\x00"` |
| HMAC message | Canonical payload bytes | Domain + `b"authorization-hmac\x00"` + canonical payload bytes |
| Owner separation | Old key, exact old class, original old live object, signed issuer phase/schema/scope | New key/domain, exact new class, original new live object/graph, signed new owner/phase/schema/scope |
| Process requirement | Current PID equals module `_ISSUER_PID`; auth PID equals `_ISSUER_PID` | Same process checks; auth PID is `issuing_pid` |
| Exported capability | None; report excludes HMAC | None; report excludes HMAC |
| Provider authenticity | Not part of old auth issuance | Public PINNED.1C validation of original complete proof graph on every check |

Old canonicalization/payload/HMAC/PID code: `core/synthetic_runtime_authorization.py:64-69,254-279`. The old key's lack of an explicit prefix is not evidence of a shared domain: exact old type, old live provenance, and the full old owner/schema-bearing signed payload are mandatory (`:292-314`).

Pinned domain/canonicalization/digest code: `core/synthetic_runtime_authorization_pinned.py:31-34,62-72`; payload/evidence/HMAC code: `:232-246`; validator: `:261-288`. Fingerprints and evidence digests use role-separated SHA-256 over the same domain (`:66-67,223-225,238-241`), but a hash is not a capability.

The old validator first validates the original spec/source and requires `type(authorization) is SyntheticRuntimeAuthorization` (`core/synthetic_runtime_authorization.py:294-298`). It then requires the original old registry object and exact old PID (`:299-304`), recreates the entire old expected payload including owner/schema/Java fields (`:305-309`), and verifies old-key HMAC (`:310-313`). A pinned object cannot pass this unchanged validator by matching scenario fields.

The pinned validator requires `type(authorization) is PinnedSyntheticRuntimeAuthorization` (`core/synthetic_runtime_authorization_pinned.py:264-265`), original registry identity/PID/outcome (`:268-272`), public authentication of the retained exact provider graph (`:273-278`), exact new owner/schema/context/payload (`:279-283`), and the separate HMAC (`:284-287`). The two owner validators cannot truthfully substitute for each other.

Authentication is an owner boundary inside trusted Python, not isolation from hostile Python capable of rewriting module internals. Frozen documentation states this limit for both owners (`docs/roadmap/phases/SYNTH_AUTH_1/SYNTH_AUTH_1.md:34-41`; `docs/roadmap/phases/SYNTH_AUTH_PINNED_1/SYNTH_AUTH_PINNED_1.md:37-47`).

## Authority matrix

`absent` below means the dataclass has no such field. It is not a positive grant. Different positive-scope field names must not be treated as aliases without an additive authenticated boundary.

| Field | SYNTH.AUTH.1 | SYNTH.AUTH.PINNED.1 |
| --- | --- | --- |
| `synthetic_runtime_authority` | `True` (exact synthetic invocation scope only) | absent |
| `synthetic_scenario_authorized` | absent | `True` (exact scenario on retained exact pinned provider graph) |
| `future_exact_reflection_required` | `True` | absent; old spec retained for scenario lineage |
| `runtime_authority` | `False` | absent |
| `runtime_execution_authority` | absent | `False` |
| `execution_lease_authority` | absent | `False` |
| `reflection_authority` | `False` | absent |
| `reflection_execution_authority` | absent | `False` |
| `real_task_runtime_authority` | `False` | `False` |
| `repository_access_authority` | `False` | absent |
| `repository_write_authority` | `False` | `False` |
| `apply_authority` | `False` | `False` |
| `network_authority` | `False` | `False` |
| `console_authority` | `False` | absent |
| `host_mount_authority` | absent | `False` |
| `shell_authority` | absent | `False` |
| `arbitrary_command_authority` | `False` | `False` |
| `executor_authority` | absent | `False` |
| `BANK_authority` | absent | `False` |
| `arbitrary_java_authority` | absent | `False` |
| `arbitrary_class_authority` | absent | `False` |
| `arbitrary_method_authority` | absent | `False` |
| `arbitrary_source_authority` | absent | `False` |
| `repository_java_authority` | absent | `False` |

Old full dataclass authority/source/capability/effect flags are fixed at `core/synthetic_runtime_authorization.py:213-242`; pinned full dataclass flags are fixed at `core/synthetic_runtime_authorization_pinned.py:194-220`, and its exhaustive negative-authority tuple is at `:35-43`.

| Other capability/state field | SYNTH.AUTH.1 | SYNTH.AUTH.PINNED.1 |
| --- | --- | --- |
| `real_task_source` | `False` | absent |
| `human_approval_required` | `False` | absent |
| `real_human_approval` | `False` | absent |
| `real_session_consumed` | `False` | absent |
| `operational_real_task_source` | `False` | absent |
| `reflection_capability_available` | `False` | absent |
| `sandbox_capability_available` | `False` | absent |
| `java_capability_available` | `False` | absent |
| `execution_ready` | `False` | absent |
| `execution_completed` | `False` | absent |
| `execution_lease_issued` | absent | `False` |
| `lifecycle_compatibility_evaluated` | absent | `False` |
| `lifecycle_execution_ready` | absent | `False` |
| `reflection_admission_issued` | absent | `False` |
| `scenario_executed` | absent | `False` |
| `measured_runtime_outcome` | absent | `False` |

The old fields `compile_count`, `jvm_execution_count`, `reflection_execution_count`, `real_runtime_authorizations_consumed`, and `synthetic_runtime_authorizations_consumed` are all fixed at `0` (`core/synthetic_runtime_authorization.py:238-242`). Pinned authorization is neither a lease nor a measured runtime result (`core/synthetic_runtime_authorization_pinned.py:215-220`; `tests/test_synthetic_runtime_authorization_pinned.py:146-165`).

Pinned provider proof's positive fact is `exact_provider_proven=True`. Its `runtime_authority`, `real_task_runtime_authority`, `repository_write_authority`, `apply_authority`, `compatibility_authority`, `SYNTH_authority`, and `executor_authority` are all false (frozen assertions in `tests/test_synthetic_runtime_authorization_pinned.py:40-43,152-155`). The auth owner additionally rejects any root field containing `authority` that is not exactly false (`core/synthetic_runtime_authorization_pinned.py:155-157`). Provider proof is not itself a SYNTH grant, lease, or execution authority.

## Copy, JSON, mutation, and wrong-process rejection

| Control | Old evidence | Pinned evidence |
| --- | --- | --- |
| Matching typed constructor / dataclass replacement | Original old registry identity required (`core/synthetic_runtime_authorization.py:299-304`); frozen rejection tests `tests/test_synthetic_runtime_authorization.py:257-271` | Original new registry identity required (`core/synthetic_runtime_authorization_pinned.py:268-272`); frozen rejection tests `tests/test_synthetic_runtime_authorization_pinned.py:206-227` |
| Copy / deepcopy | Identity check rejects distinct old object even with a copied signature (`core/synthetic_runtime_authorization.py:301`) | Explicit frozen controls `tests/test_synthetic_runtime_authorization_pinned.py:206-227` |
| Dictionary / JSON / typed JSON reconstruction | Exact old class plus original live object required; tests `tests/test_synthetic_runtime_authorization.py:257-286` | Exact new class plus original live object/graph required; tests `tests/test_synthetic_runtime_authorization_pinned.py:206-227`; typed reconstruction control `core/synthetic_runtime_authorization_pinned.py:386-393` |
| Wrapper / subclass | Exact type check (`core/synthetic_runtime_authorization.py:297`) | Exact type check (`core/synthetic_runtime_authorization_pinned.py:264`); tests `tests/test_synthetic_runtime_authorization_pinned.py:206-227` |
| Field mutation or Python equality alias | Full recursive type/scope checks; tests `tests/test_synthetic_runtime_authorization.py:247-254,295-307` | Full recursive type/scope checks; tests `tests/test_synthetic_runtime_authorization_pinned.py:230-274` |
| Wrong process | Current and issuing PID checks (`core/synthetic_runtime_authorization.py:277-279,302-304`) | Current and issuing PID checks (`core/synthetic_runtime_authorization_pinned.py:70-72,270`); tests `tests/test_synthetic_runtime_authorization_pinned.py:384-395` |
| Wrong HMAC key / copied signature | Old-key comparison plus live-object check (`core/synthetic_runtime_authorization.py:301,310-313`) | Independent-key comparison plus live-object check (`core/synthetic_runtime_authorization_pinned.py:269,284-287`); test `tests/test_synthetic_runtime_authorization_pinned.py:405-407` |
| Removed registry | No original live handle remains (`core/synthetic_runtime_authorization.py:301`) | New registry removal and provider registry removal invalidate dependent scope (`tests/test_synthetic_runtime_authorization_pinned.py:410-417`) |
| Provider aliases or chronology | Old auth neither accepts nor authenticates a provider report | Original proof graph and public validator mandatory (`core/synthetic_runtime_authorization_pinned.py:133-181,273-278`); tests `tests/test_synthetic_runtime_authorization_pinned.py:306-326,398-402` |
| Report export | `report_only=True`, no HMAC; tests `tests/test_synthetic_runtime_authorization.py:274-286` | `report_only=True`, no HMAC; tests `tests/test_synthetic_runtime_authorization_pinned.py:420-428` |

## Historical pinned 1R proof is evidence, not a retained capability

The frozen `SYNTH_AUTH_PINNED_1R_SUMMARY.json` records one authorization-owner call, one public provider-owner call, successful public validation, and all execution authorities false (`docs/roadmap/phases/SYNTH_AUTH_PINNED_1R/SYNTH_AUTH_PINNED_1R_SUMMARY.json:95-122`). Its exported authorization is report-only and includes the original owner/phase/schema, provider proof identity, exact scenario identity, and no executed scenario (`:123-198`). The report states `capability_or_HMAC_key_persisted=false` at `:198`.

Those IDs, hashes, schemas, and historical successful validation cannot restore the original process-local authorization or provider graph in this audit process. This audit neither attempts restoration nor issues a replacement. Historical 1R evidence remains unchanged.

## Dependency classification and API consequence

| Dependency exposed by this comparison | Classification |
| --- | --- |
| Exact scenario/source/invocation/private-field/expectation identity | `SEMANTIC_SCENARIO_REQUIREMENT` |
| Exact class, issuing PID, live original object, owner-local key, signed immutable scope | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Old `SyntheticRuntimeAuthorization` exact type and `issuer_phase_id="SYNTH.AUTH.1"` | `OLD_AUTH_OWNER_REQUIREMENT` |
| Old `synthetic_runtime_authorization_v1` payload | `OLD_AUTH_SCHEMA_REQUIREMENT` |
| Old `RUNTIME.JAVA.1/runtime_java_1_v1` projected into the old authenticated payload | `OLD_JAVA_REQUIREMENT` |
| HMAC-SHA256 algorithm, canonical JSON, weak versus strong registry implementation | `IMPLEMENTATION_MECHANISM_ONLY` when considered alone; keys, domains, and original-object requirements remain authentication requirements |
| Frozen 1R exported IDs, fingerprints, successful validation and authority report | `HISTORICAL_RECEIPT_BINDING` |

Direct reuse of the old public authorization validator for pinned handles is incompatible with its exact owner/schema/authentication checks. That is sufficient to reject compatibility by field coincidence. It does not alone establish that generic one-shot state transitions require a new lifecycle semantic epoch. The final lifecycle outcome must combine this comparison with the complete lifecycle consumer/state-machine trace and reflection dependency map.

Any future additive boundary must authenticate the original pinned handle through its unchanged pinned public validator and retain the exact provider proof requirements. It must preserve the old validator, old payload/schema/requirement, process-local original-object requirements, and historical semantics. It must not synthesize an old authorization, copy a signature, relabel the pinned provider requirement as old JAVA.1, or treat exported JSON as capability. This audit implements no such boundary.

## Pure-test accounting limit

The existing frozen tests use effect-denial guards and virtual runtime transports. They nevertheless call the public authorization issuers to establish controlled fixture capabilities: `tests/test_synthetic_runtime_authorization.py:65-66` and `tests/test_synthetic_runtime_authorization_pinned.py:99-106`. The pinned negative matrix additionally calls the old public issuer for an old-handle rejection control (`core/synthetic_runtime_authorization_pinned.py:397-398`). Running these unchanged tests would require separating fixture issuance from real operational issuance in the phase's effect ledger; it would not support a literal claim that no issuer function was invoked.

This comparison ran none of those tests or functions. It used only source/test/document reads and created only this additive audit document.
