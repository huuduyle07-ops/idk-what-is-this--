# Frozen reflection lifecycle consumer trace

2026-10-13 KST. Pure source audit of `SYNTH.REFLECT.LIFECYCLE.1` against the implemented `SYNTH.AUTH.LIFECYCLE.PINNED.1A` owner. No function described below was invoked as part of this trace. This audit creates only this new document.

## Source-derived conclusion

**`REFLECTION_PINNED_REQUIRES_ADDITIVE_ADAPTER`** is supported by the lifecycle source. Frozen state, one-shot, exact field, and BEFORE/AFTER ordering semantics can be reused. The frozen public implementation cannot authenticate pinned authorization or lease objects: it deliberately authenticates distinct old exact classes through distinct old public owners. Matching projected values do not cross that authentication boundary.

This is a compatibility conclusion, not present-day operational readiness or permission to implement an adapter. The pinned owner's consumer/source/compile dependency still reports `PROOF_UNRESOLVED`, and its current consume path rejects before a CONSUMED commit (`core/synthetic_runtime_authorization_pinned_lifecycle.py:459-492`). The frozen consumption ordering agrees with the pinned contract; unresolved downstream readiness does not establish a different reflection state machine.

## Exact owners, types, and validator domains

All lifecycle references below use these aliases, imported in `core/synthetic_reflection_execution_lifecycle.py:19-22`:

| Alias | Exact imported owner | Exact expected public class | Public authentication boundary |
| --- | --- | --- | --- |
| A | `core.synthetic_runtime_authorization` | `SyntheticRuntimeAuthorization` | `validate_synthetic_runtime_authorization(authorization, spec=executor1r_decrement_3_spec(), source=get_executor1r_decrement_3_source())` |
| R | `core.synthetic_runtime_authorization_lifecycle` | `SyntheticRuntimeExecutionLease` | `validate_synthetic_runtime_execution_lease(runtime, authorization)`; state comes only from `synthetic_runtime_execution_lease_state(runtime, authorization)` |
| Q | `core.synthetic_read_only_reflection` | `SyntheticReflectionRequest` | `validate_synthetic_reflection_request(request)` |
| D | `core.synthetic_reflection_execution_admission` | `SyntheticReflectionExecutionAdmission` | `validate_synthetic_reflection_execution_admission(admission)` and `synthetic_reflection_admission_satisfies_executor(admission, authorization, request)` |
| L | `core.synthetic_reflection_execution_lifecycle` | `SyntheticReflectionExecutionLease` | `validate_synthetic_reflection_execution_lease(lease)`; private authentication closure described below |

A is phase `SYNTH.AUTH.1`, schema `synthetic_runtime_authorization_v1` (`core/synthetic_runtime_authorization.py:19-21,197-215`). R is phase `SYNTH.AUTH.LIFECYCLE.1`, schema `synthetic_runtime_execution_lease_v1` (`core/synthetic_runtime_authorization_lifecycle.py:25-26,113-129`). Q is phase `SYNTH.REFLECT.1`, schema `synthetic_reflection_request_v1` (`core/synthetic_read_only_reflection.py:19-20,77`). D is phase `SYNTH.REFLECT.ADMIT.1`, schema `synthetic_reflection_execution_admission_v1` (`core/synthetic_reflection_execution_admission.py:22-23,83`). L is phase `SYNTH.REFLECT.LIFECYCLE.1`, schema `synthetic_reflection_execution_lease_v1` (`core/synthetic_reflection_execution_lifecycle.py:24-25,127-149`).

The private reflection `_LeaseRecord` declares A/R/Q/D types and strongly retains the original objects; it weakly retains the lease (`core/synthetic_reflection_execution_lifecycle.py:192-202`). These annotations document expected types. Runtime enforcement comes from public validators and exact identity checks, not the annotations.

The upstream validators enforce the following:

- A requires `type(authorization) is SyntheticRuntimeAuthorization`, `_ISSUED_HANDLES[issuance_id] is authorization`, exact PID, immutable payload, and process-local HMAC (`core/synthetic_runtime_authorization.py:292-314`). Its `fingerprint` authenticates again (`:244-247`).
- R requires `type(lease) is SyntheticRuntimeExecutionLease`, the private record's `lease_ref() is lease`, a supplied authorization `is` its retained original, reauthentication of that A object, the permanent `issuance_id` binding, exact immutable projection, and an HMAC-authenticated current state (`core/synthetic_runtime_authorization_lifecycle.py:184-208`). Both its public validator and state API use that closure (`:231-244`). Its fingerprint authenticates and hashes only the immutable issuance projection (`:145-149`).
- Q requires its exact class and `_ISSUED_REQUESTS[issuance_id] is request` plus exact issuing PID (`core/synthetic_read_only_reflection.py:164-173`). D requires its exact class and `_ISSUED_ADMISSIONS[admission_id] is admission` plus exact issuing PID (`core/synthetic_reflection_execution_admission.py:187-206`). D's validator checks its own signed upstream identity fields; its executor predicate separately authenticates the supplied original A/Q pair and matches their IDs/fingerprints (`:318-341` through `:219-229`). Neither makes a pinned A object old-authentic.

## Reusable trace notation

Every line reference in the function inventory is to `core/synthetic_reflection_execution_lifecycle.py` unless another file is named. The inventory covers all 29 explicit function/method definitions, including support functions and the issuance-dependent `verify()`.

The following closures are concrete call paths, not abstract authentication assertions:

| Closure | Exact calls and projected fields | Original live objects / old identifiers / old schema |
| --- | --- | --- |
| I | `_authenticate_inputs` at :91-119 calls A/R/Q/D validators at :94-101. It checks authorization/runtime/admission `scenario_phase_id`, request `phase_id`, every object's `scenario_id` and `source_sha256`; Q/D `observation_role`, `definition_sha256`, `owner`, `member`, `declared_type`, `operation`; R `upstream_authorization_issuance_id`, `upstream_authorization_fingerprint` against A `issuance_id`, `fingerprint`. | All original live objects required by owners. A `issuance_id` directly assumed at :117. R exact old class/schema enforced transitively by R's validator, not duck typing. |
| P | `_unsigned_lease` at :209-214 projects Q `issuance_id`, `fingerprint`; D `admission_id`, `fingerprint`; R `lease_id`, `fingerprint`; A `issuance_id`, `fingerprint`; exact scenario/source/definition/field/role constants; local issuing PID. `_projection` at :205-206 includes all L dataclass fields at :128-164. | Fingerprint getters authenticate upstreams. Helper itself does not independently validate plain ID reads. A `issuance_id` directly assumed at :214. Called after I by issuance or while rebuilding an authenticated record. |
| H | `_authenticated_record_locked` at :222-248 checks local PID, exact L class, hex lease ID, `record.lease_ref() is lease`, then I, permanent D-to-L binding, P reconstruction, exact primitive types/equality and immutable JSON, valid current state and L-owner HMAC. | Original lease plus all retained original upstreams required. A `issuance_id` and R old class/schema remain transitively mandatory through I/P. Authentic terminal L records are valid evidence. |
| B | `_bound_record_locked` at :251-258 runs H and requires caller D/Q/R/A objects `is` each retained original and caller role equals retained role. | Stronger explicit caller-to-record identity requirement. Same old identifier/type/schema assumptions as H. |
| S | `_runtime_state` at :261-267 calls only R's `synthetic_runtime_execution_lease_state(runtime, authorization)` and compares its authenticated result with the required state. | Exact original R and supplied original A required by R. Reads no caller state field, no JSON, no private R registry; old exact type/schema and A `issuance_id` assumptions are transitive. |

L's projection binds scenario phase/ID, source hash and definition hash, exact field operation/role, request issuance ID/fingerprint, admission ID/fingerprint, runtime lease ID/fingerprint, upstream A issuance ID/fingerprint, its own lease ID/PID, L phase/schema/initial state, and the full frozen false authority matrix (`:128-164`). It does not directly project runtime source size, invocation, provider proof, or proof context. Old source/invocation scope is authenticated through upstream owners; the old reflection path authenticates no provider object or provider graph. Absence of a direct field does not mean matching a subset authenticates a different epoch.

## Complete function inventory

### Functions directly or transitively coupled to old runtime/authentication

| Exact function / lines | Owner/type/validator dependency and fields | Live identity and old assumptions | State/role meaning |
| --- | --- | --- | --- |
| `_authenticate_inputs` :91-119 | I; exact A/R/Q/D owners and public validators above. | Original A/R/Q/D; direct A `issuance_id`; old R class/schema through public validator. | Validates exact scenario/field/role and shared A binding; does not require a particular runtime lifecycle state. |
| `SyntheticReflectionExecutionLease.lifecycle_state` :175-176 | Calls L state API, therefore H and I/P. | Original L plus original upstreams; old A ID/R type/schema transitive. | Authenticated L state in any authentic lifecycle state. |
| `SyntheticReflectionExecutionLease.fingerprint` :179-182 | H under local lock; hashes `record.projection_json`. | Original L/upstreams; old assumptions via H. | Stable issuance fingerprint; does not hash current state. |
| `SyntheticReflectionExecutionLease.as_dict` :184-189 | H, then `_projection(self)` and signed-record state/fingerprint. | Original L/upstreams; old assumptions via H. | Report-only export includes current state; export is not a new authority object. |
| `_unsigned_lease` :209-214 | P; reads exact Q/D/R/A identity/fingerprint fields. | No standalone identity check on plain IDs; authenticated fingerprint getters and callers supply validation. Direct old A `issuance_id`; old R fingerprint getter authenticates R. | Builds immutable L projection; no state transition. |
| `_authenticated_record_locked` :222-248 | H, including I/P and public A/R/Q/D validators. | Exact L type/live record; retained originals; old A ID/R type/schema mandatory. | Authenticates current L state, including CONSUMED/INVALIDATED evidence; no particular R state demanded. |
| `_bound_record_locked` :251-258 | B = H plus supplied/retained D/Q/R/A `is` comparisons. | Exact supplied original objects, not merely matching values; old assumptions via H. | Exact role match; no lifecycle readiness by itself. |
| `_runtime_state` :261-267 | S; R exact public state API. | Exact R and original A; old ID/type/schema transitive. | Required runtime state comparison; wraps upstream failure and fails closed. |
| `issue_synthetic_reflection_execution_lease` :270-289 | I, P, and final S(runtime, A, ISSUED), under L lock. Retains D/Q/R/A in new record. | Originals required; direct/transitive old assumptions. Permanent D admission-ID-to-L binding. | Both BEFORE/AFTER issued only against ISSUED R; at most one L per D, including dead/terminal tombstones. |
| `validate_synthetic_reflection_execution_lease` :292-296 | H under L lock. | Exact original L/upstreams; old assumptions via H. | Authentication only; no readiness or state transition. |
| `synthetic_reflection_execution_lease_state` :299-301 | H under L lock. | Exact original L/upstreams; old assumptions via H. | Returns authenticated L current state; does not require R ISSUED/CONSUMED. |
| `_compatible` :304-311 | B then S for the requested runtime state; compares L state to ISSUED. | Exact caller originals/role; old assumptions via B/S. | Pure precheck returns false on L-owner error; no reservation. |
| `synthetic_reflection_execution_lease_satisfies_executor` :314-317 | `_compatible(..., ISSUED)`, hence B/S. | Exact originals/role; old assumptions transitive. | Both L and R must be ISSUED for either role. |
| `consumable_during_active_execution` :320-322 | `_compatible(..., CONSUMED)`, hence B/S. | Exact originals/role; old assumptions transitive. | L ISSUED and R CONSUMED for either role. |
| `_transition` :325-338 | B; S(CONSUMED) only for consume; immutable-record replacement and private signature. | Exact original objects/role; old assumptions via B/S. | Only L ISSUED -> CONSUMED/INVALIDATED; consume demands R CONSUMED, invalidation accepts any authentic R state. |
| `consume_synthetic_reflection_execution_lease` :341-344 | `_transition(..., CONSUMED)`, hence B/S. | Exact original objects/role; old assumptions transitive. | Spends exactly the selected reflection effect once; never consumes R. |
| `invalidate_synthetic_reflection_execution_lease` :347-350 | `_transition(..., INVALIDATED)`, hence B; no S target-state requirement. | Exact original objects/role; old assumptions transitive. | Permanently abandons ISSUED L, including when authentic R is INVALIDATED; no refund/reissue. |
| `verify` :353-419 | Calls A spec/source accessors and A issuer (:355-357), R issuer (:358), Q BEFORE/AFTER factories (:361-363), D issuer (:364), L issuer (:365-366), validation/precheck; duplicates issuance deliberately (:371-376). Projects all reports (:382-418). | Constructs original old-domain objects; directly assumes A `issuance_id` at :394 and old R identity fields at :379-380,392-393. | Leaves strict proof leases ISSUED, but still issues capabilities. It is prohibited in this zero-issuance audit and was not run. Its name/docstring is not proof that running it satisfies the audit scope. |

### Remaining functions/methods: no old authorization/runtime input

| Exact function / lines | Fields and dependency | Authentication consequence |
| --- | --- | --- |
| `SyntheticReflectionExecutionLeaseError.__init__` :57-60 | Error code/reason only. | No owner/type/validator or live-object dependency. |
| `_fail` :63-64 | Raises L-owner typed error. | No capability authentication. |
| `_json` :67-68 | Canonical sorted compact JSON, no NaN. | Serialization alone grants no authority. |
| `_hex_id` :71-73 | Exact string, 64 lowercase hex characters. | Shape only, not identity/authentication. |
| `_local_process` :76-78 | Exact current integer PID equals module issuer PID. | Rejects foreign process; no old A/R validator. |
| `_local_lock` :81-83 | Calls `_local_process` before returning L lock. | Avoids inherited-lock wait in foreign process; no old A/R validator. |
| `_role` :86-88 | Exact string in BEFORE/AFTER roles. | Role scope only. |
| `SyntheticReflectionExecutionLease.scenario_execution_lease_id` :167-168 | Returns `runtime_execution_lease_id`. | Alias of immutable projected field; does not authenticate either lease. |
| `SyntheticReflectionExecutionLease.scenario_execution_lease_fingerprint` :171-172 | Returns `runtime_execution_lease_fingerprint`. | Alias of immutable projected field; no live authentication. |
| `_projection` :205-206 | Iterates fields of exact L class and reads matching attributes. | Internal serialization helper, not public validation or runtime/auth validator. |
| `_sign` :217-219 | Independent L secret, immutable issuance JSON and current state. | Signs L records only; no old/pinned HMAC reuse and no upstream authentication by itself. |

These support functions cannot be composed by a caller to replace H/I/B/S. The authoritative public paths always enter the owner lock and the required authentication closures.

## State/order semantics and epoch classification

| Frozen rule | Evidence | Classification | Pinned compatibility |
| --- | --- | --- | --- |
| Two exact scopes: BEFORE and AFTER for `SyntheticStateBox.value:int`, operation `read_exact_bound_field`. | :30-34,86-88,112-116 | `REUSABLE_UNCHANGED` | Pinned scenario retains exact field, source/definition and invocation identities (`core/synthetic_runtime_authorization_pinned_lifecycle.py:164-176`). |
| Issuance and pre-execution readiness require runtime ISSUED for both roles. | :43-46,270-288,314-317 | `REUSABLE_UNCHANGED` | Pinned abstract state has the same ISSUED meaning; current frozen APIs still require additive pinned binding. |
| Active readiness and actual reflection consumption require the same runtime CONSUMED for both roles. | :320-335 | `REUSABLE_UNCHANGED` | Pinned CONSUMED is likewise terminal. Pinned current consume rejects unresolved consumer readiness; this audit does not bypass that blocker. |
| Reflection itself must remain ISSUED to be consumed or invalidated, with terminal CONSUMED/INVALIDATED and no refund. | :325-338; :51-53,274-288 | `REUSABLE_UNCHANGED` | Same pinned abstract one-shot state semantics; reflection's independent single-effect state remains needed. |
| Issuance eligibility is the final authenticated runtime ISSUED check under the reflection lock; stale checks reserve nothing. | :283-288,304-311,329-337 | `REUSABLE_UNCHANGED` | Pinned public state/validation must provide authentic snapshots and terminal CONSUMED; no private upstream lock/registry needed. |
| Runtime must be consumed before BEFORE reflection consumption/read. | :37-42 | `REUSABLE_UNCHANGED` | Directly matches pinned first-behavior boundary, detailed below. |
| BEFORE consume/read, exact public `decrement(3)`, AFTER consume/read order belongs to executor. | :37-42; module description :3-6 | `REUSABLE_UNCHANGED` | Owner states cannot prove either read or invocation took place; future consumer must preserve the sequence. |
| Both reflection effects bind one exact runtime lease ID/stable fingerprint and one upstream authorization. | :117-119,137-144,209-214,251-258 | `REQUIRES_ADDITIVE_BINDING` | Concept reusable; pinned lease/auth public identities and original objects need a separate truthful boundary. |
| Old `authorization.issuance_id` and `runtime.upstream_authorization_issuance_id` spelling/epoch. | :117-119,143-144,214 | `OLD_AUTH_SPECIFIC` | Pinned authentic identifier is `authorization_id`; no invented `issuance_id` alias. |
| Old runtime exact class/schema and old public state API. | :20,97,196,263; old R :184-208 | `OLD_RUNTIME_SPECIFIC` | Pinned exact class, schema, validator and state API are distinct. |
| Old authorization exact owner/type/validator, including old spec/source parameter signature. | :19,94-96,197; old A :292-314 | `OLD_AUTH_SPECIFIC` | Existing pinned validator has its own exact class/live graph/domain. Old spec/source accessors can supply immutable scenario identity only. |
| Role/object identity, PID, signed state and stable fingerprint authentication principles. | :222-258; :179-189 | `REUSABLE_UNCHANGED` | Principles preserved; concrete owner secret/class/records must remain separate and require additive binding. |
| Old JAVA.1 requirement inherited through the old authorization/spec validator. | Lifecycle calls A/D :95-101; old A :27-30 | `OLD_AUTH_SPECIFIC` | Admission accepts neither provider nor runtime lease and does not explicitly inspect a Java profile. Its old authorization domain indirectly binds JAVA.1 through validation of the exact old auth/spec. A future pinned binding must keep mandatory public validation of the retained pinned provider graph; the frozen reflection code establishes no independent provider input requirement. |
| Source/harness readiness precedes runtime consumption. | :37-40; pinned contract :83-89 | `REUSABLE_UNCHANGED` | Necessary ordering fact only. |
| Authority and placement for source materialization/scenario compilation. | Pinned contract :96-103; pinned owner :116,285-286,469-471 | `UNRESOLVED` | Neither old reflection lifecycle nor this compatibility audit grants preparation/compilation authority or settles its placement. |

No recovered abstract reflection state/order invariant requires a new epoch of reflection semantics or conflicts with the pinned first-behavior boundary. The distinct pinned authentication epoch does require an additive implementation boundary. `OLD_RUNTIME_SPECIFIC` and `OLD_AUTH_SPECIFIC` above identify concrete authentication/field contracts, not a contradictory ordering rule.

## BEFORE/AFTER ordering proof

The exact frozen sequence is:

1. All capability/authentication gates.
2. Source/harness ready.
3. Consume the scenario runtime lease.
4. Consume BEFORE reflection lease.
5. Perform BEFORE exact reflection read.
6. Invoke exact public `decrement(3)`.
7. Consume AFTER reflection lease.
8. Perform AFTER exact reflection read.

This is a literal recovery of `EXECUTOR_SEQUENCE` at :37-42, corroborated by `docs/roadmap/phases/SYNTH_REFLECT_LIFECYCLE_1/SYNTH_REFLECT_LIFECYCLE_1.md` under its frozen future executor sequence. Both BEFORE and AFTER use identical abstract runtime-state rules. The difference is the exact observation role and its immutable binding, not a requirement for different runtime states.

The frozen lifecycle does **not** enforce that BEFORE was spent/read before AFTER, nor that public invocation occurred between them. Its role-specific leases can authenticate and become consumable against one CONSUMED runtime independently. Ordering remains an executor obligation, as the module states at :3-6. The audit therefore does not infer completed reads/invocation from CONSUMED state, or treat AFTER consumption as evidence of public invocation.

The pinned contract says consume runtime immediately before the first behavioral runtime effect, after capability and source/harness gates, and specifically says that if the first effect is an exact BEFORE reflection read, runtime consumption precedes that read (`docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1.md:83-89`). Reflection lease consumption is an authority state transition and performs no read, Java, or executor behavior. Thus consuming runtime, then consuming the BEFORE reflection effect, then performing the BEFORE read preserves the frozen boundary. No rule requires runtime consumption after the BEFORE read; that would contradict both recovered sequences.

A failure before runtime commit leaves runtime ISSUED; a failure after commit does not refund runtime. Likewise a failure after a reflection-effect commit does not refund that effect. Read order remains necessary even though neither lifecycle owner executes or observes the reads. Scenario compilation/materialization remain separate unresolved work; the sequence establishes readiness before commit without supplying that authority.

## Old-versus-pinned runtime comparison relevant to this consumer

| Property | Frozen old runtime | Implemented pinned runtime | Compatibility implication |
| --- | --- | --- | --- |
| Owner / phase / schema / exact class | `core.synthetic_runtime_authorization_lifecycle`; `SYNTH.AUTH.LIFECYCLE.1`; `synthetic_runtime_execution_lease_v1`; `SyntheticRuntimeExecutionLease` (:25-26,113-129). | `core.synthetic_runtime_authorization_pinned_lifecycle`; `SYNTH.AUTH.LIFECYCLE.PINNED.1`; `synthetic_runtime_execution_lease_pinned_1_v1`; `PinnedSyntheticRuntimeExecutionLease` (:23-25,250-264). | Separate exact authentication domain, not interchangeable. |
| Lease identity / stable fingerprint | `lease_id`; authenticated SHA256 of immutable issuance JSON (:145-149,184-208). | `lease_id`; `stable_fingerprint`, returned by authenticated `fingerprint`; domain-framed evidence/fingerprint digests (:250-261,288-292,411-421). | Same stable identity purpose, distinct authenticated implementation/digest. |
| Issuing PID | `issuing_process_id` (:126), module-local process check. | `issuing_pid` (:254), foreign-PID rejection before lock (:130-141). | Must bind exact pinned field/API, not alias old fields. |
| Authenticated state API | `synthetic_runtime_execution_lease_state(lease, authorization)` (:242-244). | `pinned_synthetic_runtime_execution_lease_state(lease, authorization)` (:454-456). | Abstract ISSUED/CONSUMED/INVALIDATED reusable; concrete API binding additive. |
| Scenario phase/ID | Top-level `scenario_phase_id`, `scenario_id` (:118-119). | Top-level `scenario_phase_id`; nested `scenario.scenario_id` (:255,265). | Scenario identity matches, shape differs. |
| Source kind/hash/size/definition | Top-level kind/hash (:120-121); size/definition through retained A and frozen spec. | Top-level `source_kind`; nested `scenario.source_sha256`, `source_size_bytes`, `definition_sha256` (:164-176,255-266). | Same source identity; explicit projection placement differs. |
| Method/invocation | Top-level owner/method/argument; exact old spec also authenticates argument and return types (:89-104,122-124). | Nested class/method/signature/arguments/types/return identity (:164-176). | Same exact `boolean SyntheticStateBox.decrement(int)` with `(3,)`; equality is scope, not authentication. |
| Observation field | Through old A frozen spec/request/admission, not direct old runtime fields. | Nested `scenario.field_owner`, `field_name`, `field_type`, definition and expected 10/true/7 (:164-176). | Exact field semantics match; future binding must authenticate original pinned objects. |
| Upstream authorization | `upstream_authorization_issuance_id`, `upstream_authorization_fingerprint`; retained original A (:116-117,160-161,192-197). | `authorization_id`, `authorization_fingerprint`, `authorization_proof_context_id`; retained original pinned A (:251-253,320-321,389-410). | Old `issuance_id` is absent; truthful new identity binding required. |
| Proof context | No old runtime field. | Exact original pinned auth proof context bound in lease (:253,406). | Additional authenticated provenance; never an alternate authority or issuance key. |
| Provider projection | Old A binds SANDBOX.2 / JAVA.1 requirement fields through its exact auth/spec validator, not a provider graph. Admission accepts no provider/lease and performs no independent provider validation. | All 15 public authenticated pinned provider fields, exact `RUNTIME.JAVA.PINNED.1C` root/requirement/image/sandbox/controller/cleanup identities (:50-55,189-205,398-399). | Future reflection must retain mandatory pinned upstream public validation of the provider graph. A direct provider object is needed only if a separately reviewed independent reflection requirement establishes it; frozen reflection source shows none. Projected equality never replaces provider authentication. |
| Authority matrix | Exact synthetic lease flag true; runtime, real task, repository, Apply, network, mounts, shell, arbitrary command and reflection false (:130-139). | Exact one-shot synthetic capability/lease fact true; all 17 runtime/general/reflection/compile authorities false (:268-286). | No general runtime/reflection/compilation grant emerges from either lifecycle. |
| Live-object semantics | Exact R class, weak lease identity, retained original A, permanent maps and signed record (:184-208). | Exact pinned class, weak original lease identity, retained original pinned A, independent permanent store and signed record (:383-421). | Principles compatible; maps/secrets/objects remain distinct. |
| Copies / JSON | Exact class plus original registry/weak identity reject equal copies, subclass/wrapper/exports (:187-194). | Same rejection principles with distinct class/store and original pinned auth (:384-391). | Matching source/schema/IDs/fingerprints cannot authenticate either domain. |
| Consumption readiness | Old R transitions after reauthentication and ISSUED check; executor is responsible for policy gates (:268-287,38-47). | Pinned consume additionally calls fail-closed `_consumer_readiness` before commit (:474-492). | Current operation remains blocked; an additive consumer contract must truthfully resolve readiness. No old consume fallback. |

## Implementation boundary and minimum future inputs

The first lifecycle authorization validation is old A's exact-class check (`:95-96` -> `core/synthetic_runtime_authorization.py:297-298`). The runtime validation independently reaches old R's exact-class check (`:97` -> `core/synthetic_runtime_authorization_lifecycle.py:187-188`). Even if a caller supplied authentic old A with pinned R, R would reject the pinned exact class before accepting a record. Copies of matching fields, subclasses, schema aliases, old-object fabrication, old-registry insertion, or old HMAC reuse are not truthful compatibility mechanisms. They are outside this audit and must not be used.

A future separately reviewed pinned reflection owner would minimally need:

- The exact original `PinnedSyntheticRuntimeAuthorization`, authenticated by `core.synthetic_runtime_authorization_pinned.validate_pinned_synthetic_runtime_authorization` with a return of that same object.
- The exact original `PinnedSyntheticRuntimeExecutionLease`, authenticated by `core.synthetic_runtime_authorization_pinned_lifecycle.validate_pinned_synthetic_runtime_execution_lease(lease, original_authorization)`; its public authenticated current-state API must be used at issuance/precheck/consumption.
- The pinned lease ID and authenticated stable fingerprint; pinned owner/phase/schema/PID; pinned authorization ID/fingerprint/proof context. Values describe authenticated retained originals and do not substitute for them.
- The exact authenticated scenario/source projection, invocation identity and `SyntheticStateBox.value:int` definition; BEFORE or AFTER role and `read_exact_bound_field` operation.
- Authentic reflection request/admission inputs in a truthful pinned admission boundary, plus separate one-shot effect identity and permanent admission binding. Existing old-auth admission/request satisfaction cannot be presumed reusable as a public API.
- Mandatory provider provenance through public validation of the retained original pinned authorization/runtime lease and their original provider graph. Frozen admission accepts no provider/lease and does not independently inspect JAVA.1; its requirement is inherited through the exact old auth/spec validator. A direct provider object would be necessary only if a separately established independent reflection requirement demanded one, which frozen source does not show. No inherited old requirement or projected equality can substitute for pinned upstream validation.
- Preservation of runtime ISSUED issuance/readiness and CONSUMED spending rules, independent reflection single-use state, exact object/role identity, process locality, immutable projection/current-state authentication, and executor-owned BEFORE/invocation/AFTER ordering.

This is an input/dependency assessment, not a frozen new schema or adapter design. Source/harness and compilation classification remain explicit unresolved dependencies. Completing the proposed reflection boundary alone would not authorize pinned runtime consumption, source preparation, compilation, executor operation, or a reflection read.

## Audit effect statement

This trace used only filesystem source/document reads and creation of this document. No issuers, transitions, reflection read primitive, provider, runtime, Java, Docker, SyntheticStateBox, BANK, EXECUTOR.1R, or Apply function was invoked. Production registries and all frozen source files were untouched. Capability issuance, consumption, invalidation, reflection execution, runtime operations and repository runtime writes are zero for this delegated source-audit work. Broader validation and preservation counts belong to the parent phase report and are not inferred here.

Recommended next slice: separately review a minimal additive pinned reflection admission/lifecycle contract with original pinned authentication and the unchanged ordering. Retain `PROOF_UNRESOLVED` for operational readiness until the separate consumer/source/compile contracts exist. Stop after this compatibility conclusion; do not implement an adapter in this phase.
