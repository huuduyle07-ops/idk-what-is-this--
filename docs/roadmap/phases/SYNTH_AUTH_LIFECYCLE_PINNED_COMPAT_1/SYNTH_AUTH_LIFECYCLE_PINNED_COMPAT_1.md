# SYNTH.AUTH.LIFECYCLE.PINNED.COMPAT.1

Final typed outcome: **LIFECYCLE_PINNED_REQUIRES_ADDITIVE_ADAPTER**.

Audit date: 2026-10-11, Asia/Seoul. This phase is pure audit and inert fixture analysis. No adapter or new lifecycle owner is implemented. Stop at this conclusion.

The one-shot state-machine semantics can be reused unchanged. The frozen public implementation cannot truthfully accept a pinned authorization: it imports the exact old owner, calls that owner's public validator, retains the old live object, and repeats old authentication whenever it validates, inspects or transitions a lease. An additive owner boundary is necessary. It must authenticate the original pinned handle through the unchanged pinned public validator; matching fields, copied HMACs, relabeled requirements, or synthesized old handles cannot substitute for that boundary.

## Owners and exact comparison

| Boundary | Owner / phase | Schema |
| --- | --- | --- |
| Frozen runtime lifecycle | `core.synthetic_runtime_authorization_lifecycle` / `SYNTH.AUTH.LIFECYCLE.1` | `synthetic_runtime_execution_lease_v1` |
| Old authorization | `core.synthetic_runtime_authorization` / `SYNTH.AUTH.1` | `synthetic_runtime_authorization_v1` |
| Pinned authorization | `core.synthetic_runtime_authorization_pinned` / `SYNTH.AUTH.PINNED.1` | `synthetic_runtime_authorization_pinned_1_v1` |

The old scenario-spec schema is separately `synthetic_runtime_scenario_spec_v1`; it is not the old authorization schema. Old authorization has no explicit `owner_identity` field: exact class and authenticated `issuer_phase_id` establish its owner. Pinned authorization explicitly records `owner_identity`.

Both epochs describe exactly `synthetic.EXECUTOR.1R.decrement_3`, source SHA `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302`, 239 source bytes, definition SHA `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d`, class `SyntheticStateBox`, signature `boolean SyntheticStateBox.decrement(int)`, argument `(3,)` of type `int`, private field `SyntheticStateBox.value:int`, expected BEFORE `10`, expected return `true`, expected AFTER `7`. These are requested expectations; no measurements occurred.

Source proof: `core/synthetic_runtime_authorization.py:135` constructs the old exact spec; `core/synthetic_runtime_authorization_pinned.py:95` obtains that original spec/source and projects only the scenario identity. The complete field, authority, process-local identity, copy/JSON and proof-context comparison is in [authorization_comparison.md](authorization_comparison.md).

| Provider boundary | Old authorization | Pinned authorization |
| --- | --- | --- |
| Requirement identity | `RUNTIME.JAVA.1` / `runtime_java_1_v1` | `RUNTIME.JAVA.PINNED.1` / `runtime_java_pinned_1_v1` |
| Authenticated provider proof | No live provider proof/root required by old authorization issuer | Original `RUNTIME.JAVA.PINNED.1C` / `runtime_java_pinned_provider_1c_v1` root, `exact_provider_proven=true`, complete retained graph |
| Proof context | No provider proof-context field | Authorization `proof_context_id` and provider `proof_context_identity`, both within new authenticated provenance |

Freeze: old provider requirement **!=** new pinned provider requirement. The pinned requirement module is metadata; PINNED.1C supplies authenticated proof. The lifecycle has no executable independent provider-root or Java-requirement admission check. It authenticates the old authorization and therefore inherits its old requirement transitively.

The frozen `CONSUMPTION_POLICY` at `core/synthetic_runtime_authorization_lifecycle.py:38` explicitly names `SANDBOX.2` and `JAVA.1`. That historical activation precondition stays unchanged. A future additive owner must state pinned activation preconditions truthfully; this audit does not reinterpret the old policy. This old wording does not change the epoch-independent terminal state rules and therefore does not require a new semantic state-machine epoch.

Both owners use HMAC-SHA256, with separate secrets and live registries. Old `_sign` (`core/synthetic_runtime_authorization.py:272`) signs canonical old payload without an explicit prefix; its exact class, private key, original-object registry, owner and schema define its domain. Pinned `_sign` (`core/synthetic_runtime_authorization_pinned.py:244`) signs the explicit domain `CATTUS:SYNTH.AUTH.PINNED.1:exact-scenario-authorization:v1\0`, role `authorization-hmac\0`, and canonical new payload. Same algorithm **!=** same authentication domain.

Old positive scope is `synthetic_runtime_authority=true`; pinned positive scope is `synthetic_scenario_authorized=true`. Both grant no runtime execution, reflection execution, repository write, Apply, network or real-task authority. Pinned explicitly grants no execution lease, shell, executor or BANK authority. No absent old field is treated as a grant. The complete authority matrices are recorded in the comparison artifact.

## All lifecycle consumers and hard dependencies

The full classified function-by-function inventory is in [lifecycle_trace.md](lifecycle_trace.md). It includes every acceptance, projection, issue, validation, state inspection, readiness, consumption, invalidation and report path, and the excluded `verify`/replay paths. Its classifications distinguish semantic scenario requirements, authentication domains, old owner/schema/Java requirements, state requirements, implementation mechanisms and historical receipt bindings.

The hard authentication path is:

`issue / validate / state / readiness / transition / properties`
-> `_authenticate_authorization` directly or `_authenticated_record_locked`
-> exact old `validate_synthetic_runtime_authorization`.

The direct import is at `core/synthetic_runtime_authorization_lifecycle.py:23`; the old public validator call is at `:93`; retained upstream reauthentication is at `:195`. The old validator at `core/synthetic_runtime_authorization.py:292` requires exact old class, original weak-registry object, old PID, complete old payload including owner/schema/Java requirement, and old HMAC. `_unsigned_lease` at lifecycle `:173` also reads old `issuance_id` and authenticated `fingerprint`; pinned has `authorization_id` and a different nested projection. `_LeaseRecord.authorization` at `:159` annotates the old class; repeated public validation supplies the actual enforcement.

No authorization invalidation API exists in this owner. It keeps the upstream immutable and changes only lease state. Historical receipt IDs and fingerprints are past evidence, not live acceptance constants or reconstructable capabilities. Existing API reuse for pinned: **false**. Semantic state-machine reuse: **true**, with additive authentication binding.

## State-machine reuse

| Rule | Semantic classification | Pinned implementation consequence |
| --- | --- | --- |
| One authenticated authorization -> at most one process-local lease | `REUSABLE_UNCHANGED` | `REQUIRES_ADDITIVE_BINDING` |
| `ISSUED -> CONSUMED` | `REUSABLE_UNCHANGED` | `REQUIRES_ADDITIVE_BINDING` |
| `ISSUED -> INVALIDATED` | `REUSABLE_UNCHANGED` | `REQUIRES_ADDITIVE_BINDING` |
| `CONSUMED` terminal | `REUSABLE_UNCHANGED` | `REQUIRES_ADDITIVE_BINDING` |
| `INVALIDATED` terminal | `REUSABLE_UNCHANGED` | `REQUIRES_ADDITIVE_BINDING` |
| No refund after activation or later failure | `REUSABLE_UNCHANGED` | Preserve activation boundary |
| Atomic authenticate/check/sign/replace under one lock | `REUSABLE_UNCHANGED` | Retain atomicity in additive owner |
| Exact process-local lease object identity | `REUSABLE_UNCHANGED` | Separate truthful type/live registry |
| Permanent tombstones after terminal state or collection | `REUSABLE_UNCHANGED` | Preserve owner-qualified one-shot provenance |
| Wrong-process rejection before lock | `REUSABLE_UNCHANGED` | Preserve issuing-process authentication |
| Copy/reconstruction/JSON rejection | `REUSABLE_UNCHANGED` | Use exact new upstream/live object |
| Exact old public authorization validator | `OLD_AUTH_SPECIFIC` | Cannot reuse for pinned |
| Frozen `JAVA.1` activation wording | `OLD_AUTH_SPECIFIC` | Preserve historical wording; bind pinned preconditions additively |

Source and frozen-test evidence for every row is in the lifecycle trace. Atomic commit is the locked record replacement at lifecycle `:281`; duplicate issuance is denied by the permanent map at `:217`. No lease issuance, consumption, invalidation, contention or runtime activation was dynamically exercised in this audit.

## Reflection downstream dependency map

[reflection_dependencies.md](reflection_dependencies.md) records all downstream validators, exact field/live-object dependencies and historical executor stops. Frozen reflection independently imports old authorization and runtime owners (`core/synthetic_reflection_execution_lifecycle.py:19`) and calls their public validators (`:94`). It requires runtime `lease_id`, authenticated stable `fingerprint`, exact scenario/source fields, upstream issuance ID/fingerprint and the same original runtime/authorization objects.

Both BEFORE and AFTER reflection leases can be issued and prechecked only while that runtime lease is `ISSUED`. The declared executor sequence requires runtime consumption to precede BEFORE reflection consumption/read, public invocation, and AFTER reflection consumption/read. The reflection owner does not independently enforce the BEFORE-versus-AFTER read order. Both reflection consumption paths require that same runtime lease to be `CONSUMED`. Runtime state is obtained through the frozen owner's public API (`:261`); field shape alone cannot establish that state or owner.

A future additive runtime lease can preserve the logical projection and state expectations, but its exact shape, owner/type/schema, live binding and compatibility with the frozen reflection validators remain undecided. No future reflection compatibility is claimed. No reflection lifecycle, request or admission owner changed.

## Validation, preservation and operational ledger

Focused validation: 30 tests passed. These include new inert compatibility tests, unchanged safe old/pinned authorization tests, the frozen runtime lifecycle policy test, and historical executor source/provider-contract tests. Reflection dependency contracts were read from the frozen suite and tested additively through AST and inert rejection paths. Every existing frozen reflection lifecycle test issues a pair or calls `verify`; none is runnable unchanged under literal zero issuance. Full frozen issuance/consumption suites were intentionally excluded to honor the stronger zero-effect constraint.

The negative fixtures are unregistered dataclasses and projections. They reject at exact type/live-registry boundaries before altered owner/schema/MAC values are individually checked. Domain/schema requirements are established by source proof, not represented as isolated dynamic positive authentication tests. No fixture is described as a valid live pinned authorization; no private registry was seeded and no public validator was weakened.

The single frozen pinned signature test installs its existing reversible fixture patches: empty registry isolation, virtual transports, and unused provider entrypoint replacements. Wrong-arity calls raise before entering the authorization issuer; neither original nor substituted provider entrypoints are invoked. This fixture setup grants no authority. Validation profiles deny issuer/consumer/invalidation/private-transition entry and live verification/execution; audit hooks deny process/network and repository writes. Pytest temporary files and logs reside in the external writable visualization directory.

Registry/picker before and after: 299 collected, 292 passed, the same seven pre-existing failures. Those failure IDs also match the frozen PINNED.1R validation summary. Registry JSON, generated in-memory summaries, picker output and existing report files are unchanged. These failures are preserved baseline debt; the audit does not claim an all-green registry suite.

Benchmark `--check`: 54 checked, zero errors. In-memory compilation, authored JSON/whitespace, `git diff --check`, current-file preservation and original historical source-pin checks are recorded in [validation_summary.json](validation_summary.json) and [historical_preservation.json](historical_preservation.json).

| Required operational effect | Count |
| --- | --- |
| Docker / provider infrastructure / provider issuance | 0 |
| JAVA.1C / SANDBOX.2 issuance / PINNED.1A export | 0 |
| Authorization issuance / live authorization attempt | 0 |
| Execution lease issuance / consumption / invalidation | 0 |
| SyntheticStateBox behavior / reflection execution | 0 |
| BANK / EXECUTOR.1R execution or replay / Apply | 0 |
| Repository runtime writes | 0 |

Audit documents, tests and validation artifacts are the only authored repository files. Bootstrap diagnostics are retained: initial guards blocked one Windows shell metadata fallback, one dependency socket-bind availability probe, and four redundant existing-directory mkdir attempts. No blocked effect succeeded. The final focused, benchmark and registry workers report zero such attempts after pure harness fixes. Initial pytest Temp-directory permissions also required moving validation scratch to the explicitly writable external directory. No sandbox escalation or approval was needed.

Existing lifecycle source changed: **false**. Pinned authorization source changed: **false**. Any execution lease issued: **false**. Frozen authorizations, reflection phases, pinned provider/runtime phases, diagnostics, historical executor attempts, registry and reversal history remain byte-preserved. Original historical hash expectations are checked, never repinned. No stash/reset/clean operation was used.

Recommended next slice: define and review a new additive pinned authorization-to-execution-lease owner boundary, with exact pinned public authentication and retained provider graph, preserved one-shot/terminal/atomic/process-local rules, explicit pinned activation prerequisites and zero compilation authority. Keep old owner/API/policy/receipts untouched. Audit reflection ownership and downstream acceptance separately before claiming reflection or executor readiness. No implementation, lease or runtime attempt is authorized by this report.
