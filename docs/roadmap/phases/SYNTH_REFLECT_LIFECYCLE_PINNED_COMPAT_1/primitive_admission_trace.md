# SYNTH.REFLECT.LIFECYCLE.PINNED.COMPAT.1: primitive and admission trace

Audit date: 2026-10-13 KST. Source analysis only. This document adds no
capability, schema, adapter, renderer, runtime entry point, or compilation
authority. Line references below refer to the unchanged working-tree sources
inspected for this audit. Historical reports provide context; present source
defines the public authentication boundaries.

## Separate conclusions

1. **Reflection primitive semantics: `REUSABLE_UNCHANGED`.** The exact bounded
   `SyntheticStateBox.value:int` read, fixed source/declaration identity, two
   private observation roles, and signed-Java-int data-shape validation do not
   intrinsically depend on an authorization epoch. Renderer output is text,
   not a read or proof of execution.
2. **Primitive authorization-compatibility API: `OLD_AUTH_SPECIFIC`.**
   `synthetic_reflection_satisfies_authorization` requires the exact old
   `SyntheticRuntimeAuthorization` class and old live-owner validator. A
   pinned authorization cannot truthfully satisfy this frozen API.
3. **Admission concept: `REQUIRES_ADDITIVE_BINDING`.** Role-specific permission
   for an exact read, subordinate to an independently authenticated scenario
   scope, is reusable. Its upstream authentication and identity binding must
   belong to the pinned domain if used for pinned execution.
4. **Admission implementation API: `OLD_AUTH_SPECIFIC`.** Frozen admission
   issuance and executor compatibility authenticate old authorization objects,
   read old `issuance_id`, and bind old fingerprints. Neither public admission
   function accepts a runtime execution lease or a provider receipt. Admission
   alone therefore cannot establish compatibility with either runtime lease
   epoch. Reflection lease lifecycle compatibility is a separate conclusion.

These findings do not imply a lifecycle ordering conflict. They establish an
implementation authentication-domain boundary, not a defect in the frozen
owners. Matching field values never establish type or live-object compatibility.

## Frozen owners, types, and schemas

| Domain | Exact owner / type | Phase / schema | Source evidence |
| --- | --- | --- | --- |
| Reflection request / rendering | `core.synthetic_read_only_reflection.SyntheticReflectionRequest` | `SYNTH.REFLECT.1` / `synthetic_reflection_request_v1` | `core/synthetic_read_only_reflection.py:17-20,77-103` |
| Reflection observation data shape | `core.synthetic_read_only_reflection.SyntheticPrivateFieldObservation` | No capability schema, issuer, signature, or live registry | `core/synthetic_read_only_reflection.py:269-300` |
| Reflection admission | `core.synthetic_reflection_execution_admission.SyntheticReflectionExecutionAdmission` | `SYNTH.REFLECT.ADMIT.1` / `synthetic_reflection_execution_admission_v1` | `core/synthetic_reflection_execution_admission.py:19-23,83-117` |
| Old authorization consumed by these APIs | `core.synthetic_runtime_authorization.SyntheticRuntimeAuthorization` | `SYNTH.AUTH.1` / `synthetic_runtime_authorization_v1` | `core/synthetic_runtime_authorization.py:19-21,197-242` |
| Pinned authorization, a distinct authentication domain | `core.synthetic_runtime_authorization_pinned.PinnedSyntheticRuntimeAuthorization` | `SYNTH.AUTH.PINNED.1` / `synthetic_runtime_authorization_pinned_1_v1` | `core/synthetic_runtime_authorization_pinned.py:26-27,185-220` |

The primitive imports the old authorization owner at line 17. Admission imports
the primitive owner at line 19 and the old authorization owner at line 20.
Neither source imports old runtime lifecycle, pinned authorization, pinned
runtime lifecycle, or a runtime/provider owner. Their runtime requirement
dependency is indirect through authenticated old authorization and its frozen
scenario specification, not independent runtime-provider authentication.

## Reflection primitive dependency map

| Function / source lines | Imported owner / exact expected type and public validator | Projected identity / state / authority | Live original required / epoch assumptions |
| --- | --- | --- | --- |
| `validate_synthetic_definition`, `core/synthetic_read_only_reflection.py:54-69` | Old authorization owner's `get_executor1r_decrement_3_source()`; exact `bytes`; no authorization validator | Exactly 239 bytes, exact source bytes and SHA-256, fixed lexical-owner prefix, declaration bytes `[36:59]`, declaration SHA-256 | No capability is accepted. Old owner supplies immutable scenario bytes; this is source identity dependence, not old authorization issuance dependence. No materialization or compilation. |
| `SyntheticReflectionRequest.fingerprint`, `:104-107`; `as_dict`, `:109-111` | Local exact `SyntheticReflectionRequest`; `validate_synthetic_reflection_request(self)` | Literal per-role contract fingerprint; report payload without signature; `report_only=True` | Exact live request required. Fingerprint excludes request issuance ID/PID through the contract projection, so equal-role requests share a contract fingerprint without sharing provenance. No runtime authorization/lease accepted. |
| `_fixed_request`, `:114-117`; `_payload`, `:120-122`; `_contract_payload`, `:125-127`; `_pinned_fingerprint`, `:130-136` | Local request type; scalar complete projection | Request schema, scenario phase/ID, source/definition, owner/member/type, operation, role, source kind, request issuance ID/PID, authority false matrix; contract projection removes issuance ID/PID | Constructs inert request data, never live authentication by itself. Two literal per-role fingerprint pins. The word `pinned` here denotes frozen request fingerprints, not pinned runtime authorization. |
| `_exact_immutable`, `:139-147`; `_local_process`, `:150-152`; `_hex_id`, `:155-157`; `_sign`, `:160-161` | Local exact scalar types, issuing process, local HMAC domain | Exact types/values, issuing PID, 64-hex identity and signature, complete non-signature payload | No caller can replace an equal scalar subclass, PID, projection, or signature with an equivalent-looking value and retain validation. No upstream authentication is performed in these helpers. |
| `validate_synthetic_reflection_request`, `:164-187` | Exact local request class `:166`; complete fields `:168`; local registry and HMAC; `validate_synthetic_definition` `:186` | Request identity/PID `:170-174`; exact role `:175-177`; complete fixed projection and contract hash `:178-183`; signature `:184-185`; fixed source | `_ISSUED_REQUESTS.get(request.issuance_id) is request` `:171`, local PID, independent HMAC. Constructors, copies, subclasses, JSON and unregistered equal objects cannot validate. No runtime authorization, lease, state API, provider or old authorization issuance ID used. |
| `_issue`, `:190-196`; `executor1r_before_request`, `:199-200`; `executor1r_after_request`, `:203-204` | Local process; old source getter; exact local request; local public request validator | Fixed role only, fresh request issuance ID/PID/signature, weak-registry entry | Issuance paths; not invoked in this audit. No authorization or runtime lease accepted. Request validity alone grants no execution authority. |
| `synthetic_reflection_satisfies_authorization`, `:207-238` | Exact **old** `authorization_owner.SyntheticRuntimeAuthorization` `:209-212`; local public request validator `:214`; old `executor1r_decrement_3_spec()` `:215`; old `validate_synthetic_runtime_authorization(..., spec=spec, source=old source getter)` `:216-218` | Scenario ID `:224`, scenario phase `:225`, source SHA `:226`, exact owner/member/type/definition `:227-229`, source kind `:230`, full role tuple `:231`, request role `:232`, exact reflection-required flags `:233-234`, reflection authority false `:235-236`, old auth `execution_ready=False` `:237` | Original live request and original live old authorization required through their owners. Does not project `auth.issuance_id` itself, but old validator requires old issuance ID, PID, exact class and live identity. No lease type/schema/state is accepted or read. Pinned auth returns false at the exact old-class gate even if all semantic target values match. |
| Fixed `_BEFORE_HELPER` / `_AFTER_HELPER`, `:243-260` | No owner or capability API is called by these literals | Role-specific helper name; fixed `SyntheticStateBox.class`, `getDeclaredField("value")`, `setAccessible(true)`, `getInt(instance)` | Epoch-independent Java read text. No enumeration, setters, private method/constructor reflection, class loading, public invocation or measured receipt. No helper is compiled or invoked here. |
| `render_synthetic_read_only_reflection`, `:263-265` | Local exact live request through `validate_synthetic_reflection_request` | Selects one complete fixed helper according to authenticated request role | Original live request required, but this API accepts no authorization or runtime lease. Its pure text semantics can be reused if an additive pinned boundary separately authenticates pinned execution authority. Reuse must not claim the old compatibility predicate accepts pinned auth. |
| `SyntheticPrivateFieldObservation.__post_init__`, `:284-285`; `validate_synthetic_private_field_observation`, `:288-300` | Exact local **data** class `:289`; complete fields `:291`; exact scalar type/value validator | Scenario, owner/member/type, source/definition `:293-295`; role `:297`; exact Python `int` within Java signed-int range `:298-299` | No live-object issuance identity, signature, authorization, runtime lease or state. Any in-range exact int is accepted; expected 10/7 are not compared. Dataclass copies remain valid data; dict/JSON is not the exact typed data shape. This does not prove a read occurred. |
| `verify`, `:303-340` | Calls both local request factories `:305`, old auth factory `:307-308`, old compatibility predicate, renderer and reports | Issues requests and old authorization, renders text, reports no measurements | **Not called.** Historical no-runtime proof includes capability issuance; it is not an acceptable zero-issuance validation entry point for this audit. |

The old authorization public validator itself is the decisive delegated
authentication boundary: `core/synthetic_runtime_authorization.py:292-314`.
It revalidates exact owned spec and source (`:295-296`), requires exact class
(`:297-298`), requires `_ISSUED_HANDLES.get(authorization.issuance_id) is
authorization` with issuing PID (`:299-304`), checks exact immutable complete
scope (`:305-309`), and authenticates with its independent process-local HMAC
(`:310-313`). Reflection must not bypass or alter this domain to accept pinned
objects.

## Admission dependency map

| Function / source lines | Imported owner / exact expected type and public validator | Projected identity / state / authority | Live original required / epoch assumptions |
| --- | --- | --- | --- |
| `SyntheticReflectionExecutionAdmission.fingerprint`, `core/synthetic_reflection_execution_admission.py:119-122`; `as_dict`, `:124-127` | Local exact admission, local public admission validator | Full signed admission payload hash; report-only export without signature | Original live admission required. Unlike the request contract fingerprint, admission fingerprint binds issuance/upstream identities as part of full payload. No upstream lease accepted or state read. |
| `_payload`, `:130-133`; `_exact_immutable`, `:136-139`; `_scope_values`, `:142-168` | Local admission class and scalar type checks | Fixed scenario/field/role/operation/renderer identity; own phase/schema; reflection-execution permission true; runtime, real-task, write, Apply, setters, enumeration, private-method, constructor, arbitrary-loading permission false; `single_execution_use=True`; fixed `consumption_state="issued"` | No upstream validation in these helpers. Fixed consumption state is an immutable admission contract field, not an implemented lifecycle transition. |
| `_unsigned_admission`, `:171-180`; `_sign`, `:183-184` | Local exact admission data, local independent HMAC | Old authorization fingerprint/**issuance ID**, request fingerprint/issuance ID, renderer fingerprint, role, fresh admission ID/PID | Inert construction cannot confer authenticity. No runtime lease ID/fingerprint/schema/provider/proof context is present. |
| `validate_synthetic_reflection_execution_admission`, `:187-216` | Exact local admission `:191`; complete payload/signature `:193-198`; local registry/HMAC | Role `:199-201`; own admission ID/PID `:202-206`; exact scope and authority `:207-209`; 64-hex renderer, old auth and request identity bindings `:210-213`; HMAC `:214-215` | `_ISSUED_ADMISSIONS.get(admission_id) is admission` `:203`, issuing process, independent HMAC. This validator authenticates the admission itself; it does **not** independently revalidate current upstream objects or any runtime lease. A separately successful full compatibility predicate is needed for upstream matching. |
| `_validate_upstream_pair`, `:219-273` | `reflection_owner.validate_synthetic_reflection_request` `:222`; **old** `authorization_owner.validate_synthetic_runtime_authorization` with exact owned spec/source `:223-226`; primitive old-auth compatibility predicate `:229`; public fixed renderer `:234` | Renderer identity/phase/schema and fixed-helper SHA `:237-242`; old auth authority projection `:244-246`; request validity/nonexecution `:247-248`; scenario/source/kind `:249-252`; exact public `decrement(3):boolean` invocation `:253-255`; exact field/definition/operation `:256-260`; full role tuple and reflection-required flags `:261-265`; old auth execution readiness false `:266`; request role `:267` | Both exact original live upstream objects required. Any validation exception fails closed `:270-273`. Old auth type/issuance schema/registry/HMAC assumed by delegated public validator. No runtime lease or authenticated runtime state required here. No direct provider authentication. Renderer text is generated in memory before issuance; no source file/Java compile. |
| `issue_synthetic_reflection_execution_admission`, `:276-315` | Signature explicitly takes **old** auth class and exact primitive request `:277-278`; local process; `_validate_upstream_pair` `:282`; local public admission validator `:315` | Auth fingerprint `:287`, request fingerprint `:288`, role `:289`, **old `auth.issuance_id`** `:290`, request issuance ID `:291`, fresh admission ID/PID and HMAC `:294-314` | Validated old upstream originals needed at issuance; stores identity strings, not upstream object references. No runtime lease parameter, runtime lease fingerprint/ID, runtime state, provider receipt or provider-proof projection. Issues BEFORE/AFTER from authenticated request role; caller cannot override role/renderer/source. Not invoked in this audit. |
| `synthetic_reflection_admission_satisfies_executor`, `:318-341` | Local public admission validator `:322`; `_validate_upstream_pair` `:325`, hence both upstream public validators and old compatibility predicate | Role `:331`, renderer identity/fingerprint `:332-333`, old auth fingerprint/issuance ID `:334-335`, request fingerprint/issuance ID `:336-337`, fixed `consumption_state="issued"` `:338` | All three original live objects authenticate and exact identities match. Pure/repeatable, no consumption. Does not accept a runtime lease or inspect its state. Cannot accept pinned auth because upstream validator is exact-old-type. |
| `_issue_upstream`, `:344-350`; `verify`, `:353-418` | Old authorization issuance factory and primitive request factories; public admission issuer/compatibility | Creates old upstream handles and two admissions for historical proof | **Not called.** These paths issue capabilities even though they perform no Java/reflection execution. |

There is no admission consume or invalidate function. The admission source
records future single-use policy at `:36-39`, and its historical report explicitly
sets `consumption_implemented=False` at `:401`. The later reflection lifecycle
owns state transitions; admission's immutable `consumption_state` cannot serve
as an authenticated runtime-lease state API.

Historical context was read from
`docs/roadmap/phases/SYNTH_REFLECT_1/SYNTH_REFLECT_1.md` and
`docs/roadmap/phases/SYNTH_REFLECT_ADMIT_1/SYNTH_REFLECT_ADMIT_1.md`. They confirm
that primitive rendering is text, result objects are data without origin proof,
admission is subordinate to separate runtime authorization, and consumption
was not implemented by the admission phase. The admission report's different
BEFORE/AFTER authorization IDs describe its two historical proof fixtures;
the public source does not require BEFORE and AFTER to use different
authorizations. It requires each admission to match the specific original
authorization/request identities it actually bound. Shared-runtime lifecycle
rules therefore must come from the lifecycle owner rather than those report IDs.

## Admission runtime/provider requirement and pinned boundary

Frozen admission binds old authorization and request, scenario/source,
field/operation/role, exact public invocation, fixed renderer, and its own
read-only authority matrix. It does **not** bind an old runtime lease directly.
It depends on the old authorization's authenticated scope/spec, which includes
sandbox/Java requirement fields (`core/synthetic_runtime_authorization.py:206-211`
and old validator `:292-314`), and includes the complete old authorization
fingerprint. It independently calls no provider validator and accepts no
provider proof input. Runtime execution authority is expressly separate.

Pinned authorization uses `authorization_id`, `proof_context_id`, `issuing_pid`,
nested `scenario` and `provider` projections, and an evidence digest
(`core/synthetic_runtime_authorization_pinned.py:185-192`). Its public validator
is `validate_pinned_synthetic_runtime_authorization`, not the old validator
(`:261-288`). It requires exact pinned class, the original local authorization
and retained provider graph, exact immutable projection, and its own
domain-separated HMAC. Its scenario identity is explicitly recovered from
the unchanged frozen spec/source (`:95-111`). Thus target/source semantic
continuity is proved by source, while old-type API compatibility is disproved
by source.

Neither old authorization `issuance_id` nor an old authorization fingerprint
may be fabricated for pinned execution. Field copying, subclass tricks,
schema aliases, production registry insertion, old-object fabrication, and
old-HMAC reuse would undermine the frozen authentication domain. A future
additive owner must authenticate pinned objects through their actual owners.

## Semantic classification for these two layers

| Rule | Classification | Evidence / limit |
| --- | --- | --- |
| Exact private primitive instance field `SyntheticStateBox.value:int` | `REUSABLE_UNCHANGED` | Primitive fixed declaration and helper target; pinned scenario recovers same metadata |
| Exact source size/hash and raw declaration identity | `REUSABLE_UNCHANGED` | Fixed 239-byte source and `[36:59]` declaration; use does not decide materialization |
| BEFORE/AFTER role separation and direct-public-return exclusion | `REUSABLE_UNCHANGED` | Primitive full role tuple and request-role gate; admission exact role binding; public return is outside reflection |
| Exact `getInt` bounded read, no setters/enumeration/private calls/loading | `REUSABLE_UNCHANGED` | Entire helpers are fixed literals; authority matrices stay read-only |
| In-range primitive-int result data validation, no expected-value measurement claim | `REUSABLE_UNCHANGED` | Observation validator accepts any exact signed Java int; no capability/provenance claim |
| Original request authentication / independent request HMAC | `REUSABLE_UNCHANGED` | Exact class/complete projection/live identity/PID/signature; unchanged primitive can authenticate its own requests |
| Primitive compatibility predicate's old auth exact type and validator | `OLD_AUTH_SPECIFIC` | Explicit old class gate `:209`; old public validator `:216` |
| Role-specific admission subordinate to a separately authenticated runtime scope | `REQUIRES_ADDITIVE_BINDING` | Same role/field concept; pinned execution must bind its exact pinned auth domain |
| Admission old auth issuance ID and old auth fingerprint projection | `OLD_AUTH_SPECIFIC` | `auth.issuance_id` at issuance `:290` and matching `:335`; old validator and payload semantics |
| Admission own process/HMAC/live identity; report/copy rejection | `REUSABLE_UNCHANGED` | Safety concept stays; future pinned admission must have its own truthful owner domain |
| Admission runtime lease / provider proof state binding | `UNRESOLVED` **in these two APIs** | No lease/provider parameter or state API exists here; inspect the distinct lifecycle owner for its actual rule |
| Admission single-use immediate-before-read policy | `REUSABLE_UNCHANGED` as policy; no transition API here | Historical `CONSUMPTION_POLICY`; later lifecycle enforcement must be examined separately |

No `OLD_RUNTIME_SPECIFIC` runtime lease type dependency occurs in these two
sources: they accept no runtime lease. This does not contradict old-runtime
specific dependencies in the separate frozen reflection lifecycle owner.

## Necessary source/compile observations only

The primitive requires exact source bytes to be recoverable and revalidates
them while authenticating requests. Admission additionally requires the pure
renderer output to be recoverable so that it can fingerprint the role-specific
fixed helper. Both checks occur in memory. Neither owner materializes source,
builds a harness, compiles Java, grants compilation permission, launches a JVM,
creates `SyntheticStateBox`, or performs reflection. Consequently these two
layers impose no compiler placement decision. Source materialization and
scenario compilation placement remain separate downstream dependencies.

Any ordering fact in reflection lifecycle (for example readiness before
runtime consumption) must be reported from that owner and its frozen contract,
without importing an unproved compilation grant into these pure APIs.

## Minimum truthful future projection, without a proposed schema

For an additive pinned admission/reflection boundary, retain the exact original
pinned authorization and authenticate it via its owner's public validator;
bind its `authorization_id` and validated fingerprint. Bind the unchanged
scenario/source/declaration and exact public invocation projection to the
exact field/role/operation. If reusing the frozen primitive, retain/authenticate
the original request and bind its issuance ID, contract fingerprint, renderer
identity and fixed-helper fingerprint. Preserve exact type, issuing-process,
independent authentication domain, live-object and copy/JSON rejection.

The separate pinned reflection lifecycle boundary additionally needs the
exact original pinned runtime lease, its actual lease ID and stable fingerprint,
and authenticated current state from the pinned lifecycle owner. This document
does not define their schema or assert acceptance by the old lifecycle. Pinned
authorization/lease validators already retain provider provenance; these two
frozen reflection layers independently require no direct provider object.
Whether a future pinned boundary requires another provider input depends on
its actual owner contracts and must not be inferred from field resemblance.

## Safe frozen test selection

These are exact pytest function node selectors for the unchanged suites.
Parameterized selectors expand only the indicated zero-issuance cases. They
validate inert source/data/rejection and do not issue requests, authorizations,
admissions, runtime/reflection leases, provider proofs, or perform a read.
This document records source review, not a claim that these tests were run.

| Exact frozen selector | Cases from source | Why zero issuance is safe |
| --- | --- | --- |
| `tests/test_synthetic_read_only_reflection.py::test_exact_synthetic_definition_bytes_and_hash_are_bound` | 1 | Pure fixed source bytes/hash/declaration validation |
| `tests/test_synthetic_read_only_reflection.py::test_definition_rejects_different_declarations_bytes_and_types` | 17 | Pure rejection of mutated source/declaration/types |
| `tests/test_synthetic_read_only_reflection.py::test_definition_exact_bytes_and_declaration_survive_equal_digest` | 1 | Temporarily substitutes source/hash functions; validates inert rejection, restores via monkeypatch |
| `tests/test_synthetic_read_only_reflection.py::test_observation_rejects_coercion_bool_subclasses_and_non_java_int_range` | 10 | Inert observation constructor rejection only |
| `tests/test_synthetic_read_only_reflection.py::test_observation_metadata_and_live_result_types_are_validated` | 8 | Inert observation data validation; temporary data mutation restored |
| `tests/test_synthetic_read_only_reflection.py::test_observation_rejects_equivalent_foreign_types` | 8 | Inert observation data rejection for scalar subclasses |
| `tests/test_synthetic_read_only_reflection.py::test_observation_remains_data_and_json_cannot_be_used_as_typed_measurement` | 1 | Inert data copy accepted; dict/JSON/foreign-role rejection |
| `tests/test_synthetic_read_only_reflection.py::test_observation_subclasses_and_wrappers_are_not_the_exact_typed_result` | 1 | Inert data subclass/proxy rejection |
| `tests/test_synthetic_read_only_reflection.py::test_uninitialized_exact_observation_and_missing_slots_fail_closed` | 1 | Unregistered, inert data constructor/missing-slot rejection |
| `tests/test_synthetic_reflection_execution_admission.py::test_uninitialized_foreign_and_report_only_values_never_authenticate` | 1 | Foreign reports/uninitialized unregistered admission rejection; no issuance path |

Total safe cases by source: 48 primitive and 1 admission. The unchanged autouse
strict runtime-denial fixtures wrap these tests, but those fixtures do not deny
capability issuance. The selected functions were therefore audited beyond that
guard.

**Do not run the remaining frozen tests from these two suites in this phase.**
Every other primitive test calls a request factory, authorization issuer,
`verify()`, or a historical BANK authorization builder; every other admission
test calls `_pair`, `_authorization`, an issuance factory, or `verify()`.
In particular, the apparently data-only
`test_observation_data_accepts_exact_java_int_without_expected_value_comparison`
ends with `_issue_authorization()` (`tests/test_synthetic_read_only_reflection.py:550`)
and is excluded. Negative-path tests that first issue valid handles are also
excluded; safety names and historical no-Java reports do not make them
zero-issuance tests. Source/AST analysis and inert unregistered rejection tests
provide the compatibility evidence those omitted effectful fixtures cannot
provide under this audit scope.

## Preservation and scope

This sub-audit creates only this new document. It makes no reflection source,
pinned lifecycle source, historical document, registry/reversal, executor,
runtime/provider, test or adapter edits. It issues/consumes/invalidates no
capability and invokes no read, provider, Java, Docker, sandbox, BANK,
EXECUTOR.1R or Apply operation. Broader validation and historical preservation
results are recorded by the parent compatibility audit.
