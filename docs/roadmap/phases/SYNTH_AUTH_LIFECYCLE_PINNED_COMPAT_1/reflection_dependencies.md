# Reflection dependencies and historical executor constraints

This is source-level dependency mapping for `SYNTH.AUTH.LIFECYCLE.PINNED.COMPAT.1`.
It establishes neither pinned reflection compatibility nor authority to issue,
consume, reflect, execute, compile, or retry. The observations below were obtained
by reading frozen source and tests. No historical replay or test was executed for
this mapping, and no existing source or historical artifact was edited.

## Frozen downstream owners

`core/synthetic_reflection_execution_lifecycle.py:19-22` imports the exact old
authorization, runtime lifecycle, reflection request, and reflection admission
owners. Its owner/schema are `SYNTH.REFLECT.LIFECYCLE.1` and
`synthetic_reflection_execution_lease_v1` (`:24-25`). Its roles are exactly
`exact_private_state_before` and `exact_private_state_after` (`:32-34`).

The immediate authentication chain is `_authenticate_inputs` (`:91-119`):

| Dependency | Exact source evidence | Classification |
| --- | --- | --- |
| Old authorization public validator with the owned old spec/source | `:94-96` calls `authorization_owner.validate_synthetic_runtime_authorization` | `OLD_AUTH_OWNER_REQUIREMENT` and `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Frozen runtime lifecycle public validator | `:97` calls `runtime_owner.validate_synthetic_runtime_execution_lease(runtime, authorization)` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Frozen reflection request public validator | `:98` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Frozen admission public validator and pair predicate | `:99-101` | `AUTHENTICATION_DOMAIN_REQUIREMENT` and `OLD_AUTH_OWNER_REQUIREMENT` transitively |
| Scenario phase, ID, and source SHA across authorization, runtime, request, admission | `:107-111` | `SEMANTIC_SCENARIO_REQUIREMENT` |
| Exact observation role, definition SHA, class, field, declared type, and operation | `:112-116` | `SEMANTIC_SCENARIO_REQUIREMENT` |
| Runtime authorization issuance ID and fingerprint equal the authorization's | `:117-119` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |

The admission owner independently imports the old authorization owner at
`core/synthetic_reflection_execution_admission.py:20`. Its `_validate_upstream_pair`
obtains the old owned spec and calls the old public validator (`:219-226`);
`synthetic_reflection_admission_satisfies_executor` calls that same pair validation
(`:318-328`). Therefore replacing only the runtime lease provider would not remove
the old authorization boundary from this downstream chain.

## Required runtime lease shape and identity

The currently consumed runtime handle is the concrete frozen
`SyntheticRuntimeExecutionLease` from `core/synthetic_runtime_authorization_lifecycle.py`.
Its immutable dataclass projection is at `:113-139` and its owner/schema defaults
are at `:127-128`: `SYNTH.AUTH.LIFECYCLE.1` /
`synthetic_runtime_execution_lease_v1`.

The reflection lifecycle accesses these runtime members directly:

| Runtime requirement | Reflection source | Why it matters |
| --- | --- | --- |
| `scenario_phase_id`, `scenario_id`, `source_sha256` | `core/synthetic_reflection_execution_lifecycle.py:107-111` | Exact scenario consistency |
| `upstream_authorization_issuance_id`, `upstream_authorization_fingerprint` | `:117-119` | Same authorization for one activation |
| `lease_id`, authenticated `fingerprint` | `:213` | Immutable subordinate read-lease bindings |
| Exact live runtime object | `_LeaseRecord.runtime` at `:196`; identity comparison at `:254-255` | A copied or replacement runtime cannot bind an issued read lease |
| Public runtime validation API | `:97` | Shape alone does not authenticate a runtime lease |
| Public runtime state API taking `(runtime, authorization)` | `:261-267` | Issuance/readiness/consumption depend on the same authenticated activation state |

The reflection projection stores `runtime_execution_lease_id` and
`runtime_execution_lease_fingerprint` (`:141-142`), alongside upstream authorization
issuance ID/fingerprint (`:143-144`). Its convenience
`scenario_execution_lease_id`/`scenario_execution_lease_fingerprint` properties are
aliases for those runtime identifiers (`:166-172`).

A future additive pinned lifecycle could preserve the informational field layout
and state meanings. That would preserve a data-shape prerequisite only. This audit
does not establish API compatibility: the frozen reflection owner invokes the old
runtime public validator and old authorization validator, and retains the exact
live handles. Matching field names or values cannot satisfy those boundaries.

## BEFORE, activation, and AFTER ordering

| Stage | Frozen requirement | Source evidence |
| --- | --- | --- |
| BEFORE reflection lease issuance | Runtime must still be `ISSUED`; admission has no prior lease tombstone | `core/synthetic_reflection_execution_lifecycle.py:270-288` |
| AFTER reflection lease issuance | Same `ISSUED` runtime; separate exact AFTER admission and role | `:86-119`, `:270-288` |
| Pre-execution readiness for either read | Read lease `ISSUED`, exact live bindings, runtime `ISSUED` | `:304-317` |
| Runtime activation | Executor consumes the runtime lease before the first read effect | `EXECUTOR_SEQUENCE` at `:37-41` |
| BEFORE read-lease consumption | Exact retained runtime must be `CONSUMED`, read lease must be `ISSUED` | `:320-335`, `:341-344` |
| BEFORE read / invocation | Executor owns actual read and exact public `decrement(3)` invocation | `:37-41`; module contract `:3-6` |
| AFTER read-lease consumption | Same exact consumed runtime; independent AFTER read lease | `:251-257`, `:320-335` |
| AFTER read | Executor owns the actual read | `:41`; no reflection executor exists in this owner |

The reflection owner never consumes runtime authority itself. Its consumption
function spends only the reflection effect (`:341-344`). Runtime state is queried
through `runtime_owner.synthetic_runtime_execution_lease_state` (`:263`). The
`CONSUMED` check is justified by terminal runtime semantics (`:333-335`).

Source evidence does not require BEFORE lease consumption to precede AFTER lease
consumption. The declared sequence makes actual read/invocation ordering an
executor responsibility. The two roles are separate exact effects within one
activation, not a replacement runtime state machine.

## Authentication, PID, state, and tombstones

`core/synthetic_reflection_execution_lifecycle.py` has its own secret, issuer PID,
lock, permanent admission-to-lease records, and lease registry (`:48-53`).

| Requirement | Source evidence | Classification |
| --- | --- | --- |
| Issuing process rejection before inherited lock acquisition | `:76-83` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Exact reflection lease type and valid ID | `:224-226` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Registry record and exact weak live identity | `:227-229` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Reauthenticate all retained upstreams on every lease validation | `:230-231` | `AUTHENTICATION_DOMAIN_REQUIREMENT` and `OLD_AUTH_OWNER_REQUIREMENT` |
| Permanent admission binding | `:232-233` | `LIFECYCLE_STATE_REQUIREMENT` |
| Exact immutable issuance projection with exact Python primitive types | `:234-243` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Independent HMAC over immutable projection plus current state | `:217-219`, `:244-247` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| Exact live admission/request/runtime/authorization and observation role | `:251-257` | `AUTHENTICATION_DOMAIN_REQUIREMENT` |
| One lease per admission, retained after collection/terminal state | `:270-288`; comment at `:51` | `LIFECYCLE_STATE_REQUIREMENT` |
| Only `ISSUED -> CONSUMED` or `ISSUED -> INVALIDATED` | `:325-337` | `LIFECYCLE_STATE_REQUIREMENT` |
| Authenticate/check/sign/registry replacement under one lock | `:325-337` | `IMPLEMENTATION_MECHANISM_ONLY` supporting atomic lifecycle semantics |

These checks preserve copy/JSON rejection, terminality, and no refund. They also
make a generic projected object insufficient for reflection compatibility.

## Frozen test evidence

All evidence in this subsection is inspection of test source, not an execution
result for this audit.

`tests/test_synthetic_reflection_execution_lifecycle.py` covers:

| Contract | Test evidence |
| --- | --- |
| One runtime/auth shared by exact BEFORE/AFTER scopes | `:115-137` |
| Runtime must be consumed before spending a reflection lease; upstream projections stay unchanged | `:140-162` |
| Independent BEFORE and AFTER effects in one activation | `:165-173` |
| Terminal invalidation independent of runtime state | `:176-190` |
| Collected/terminal lease cannot refund admission | `:193-206` |
| Nonissued runtime cannot issue a read lease | `:209-217` |
| Exact roles and no generic role | `:220-238` |
| Copies, JSON, reconstruction, or unrelated live inputs rejected | `:241-307` |
| Role cross-use rejected | `:310-319` |
| Typed wrappers/subclasses/incomplete leases rejected | `:322-341` |
| No refund after subsequent reflection/invocation/protocol/timeout/cleanup failure | `:344-355` |
| Every field and exact primitive type authenticated | `:358-387` |
| Independent authentication keys and retained upstream identities | `:390-409` |
| Wrong PID rejected before inherited lock | `:412-430` |
| Forged state / reset / persistence / refund API unavailable | `:433-458` |
| Stale competing prechecks allow one transition; consume vs invalidate terminal | `:461-493` |
| Lock covers authentication, signing, and commit | `:496-523` |
| All four upstream public validators called | `:526-546` |
| Runtime invalidation after precheck cannot start reflection | `:549-555` |

Crucial validation constraint: `_activation` invokes old authorization issuance
and runtime lease issuance (`:41-45`); `_activate` and `_consume` perform lease
transitions (`:64-73`). Every test in this frozen reflection lifecycle file calls
those helpers, `_pair`, or `owner.verify`. `owner.verify` itself issues an old
authorization, runtime lease, admissions, and read leases
(`core/synthetic_reflection_execution_lifecycle.py:353-365`). Consequently there
are **no runnable frozen reflection lifecycle test nodeids that call no issuance
or consumption method**. The old test file may be read/compiled/collected under
appropriate guards; execution of its complete suite would violate this audit's
zero-issuance constraint. Additive pure source/AST dependency tests must supply
the current phase's runnable reflection mapping checks.

## Historical EXECUTOR.1R stops

The historical attempts must remain separate, with their original reasons:

1. Original `EXECUTOR.1R`: the independent scenario cannot satisfy the prior
   reconstructed BANK-family authorization/reflection contracts. Its source
   describes the mandatory stop (`core/behavioral_diagnostic_executor_refresh.py:1-5`).
   The compatibility audit attempts closed invalid inputs (`:49-79`) and
   `verify` creates report-only blocked evidence with no refreshed capabilities
   (`:141-160`). Frozen tests pin that stop and all unmeasured facts
   (`tests/test_patch_candidate_behavior_executor1r.py:25-53`). Do not replay it.
2. Shared-authority retry: it obtains one old authorization and two subordinate
   admissions, then stops because the frozen old auth owner has no consumption
   contract. The status is
   `PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_BLOCKED_AUTH_LIFECYCLE`
   (`core/behavioral_diagnostic_executor_retry.py:15-17`, `:175-189`). Its tests
   pin one authorization and the retained block
   (`tests/test_patch_candidate_behavior_executor1r_retry.py:41-76`, `:79-105`).
   This retry's tests construct `live_pair` or call `verify`, so no safe zero-
   issuance nodeid was found in that file.
3. Lifecycle-closed retry: authenticates one `ISSUED` runtime lease plus exact
   BEFORE/AFTER read leases and stops at the historical Java profile conflict.
   Authority graph validation uses all public owner APIs and exact same-runtime
   IDs/fingerprints (`core/behavioral_diagnostic_executor_lifecycle_retry.py:37-67`).
   Its contract audit compares actual frozen descriptor/receipt defaults against
   the old authorization's required JAVA.1 schema/policy (`:70-105`). JAVA.1 binds
   SANDBOX.1 policy while SANDBOX.2 continuation has JAVA.1C schema (`:105`).
   `verify` issues one graph (`:154-188`) then retains
   `java_profile_contract_mismatch` (`:195-199`); even changed contracts stop with
   `infrastructure_contract_changed_requires_review` (`:200-202`). It supplies no
   implemented effectful executor (`:155-158`). Do not call `verify` or replay.

These Java constraints belong to the historical executor consumer, not an
independent provider inspection inside runtime lease validation. The runtime
owner's frozen consumption policy nevertheless explicitly names old JAVA.1
(`core/synthetic_runtime_authorization_lifecycle.py:38-41`), and its boundary test
pins that wording. An additive future owner must preserve that historical
requirement as historical evidence rather than reinterpret old JAVA.1 as pinned
JAVA.1 or JAVA.1C.

## Safe runnable frozen selections and bootstrap

Inspection verified these nodeids do not invoke any issuance or consumption
method:

- `tests/test_synthetic_runtime_authorization_lifecycle.py::test_future_consumption_boundary_is_explicit_and_has_no_runtime_implementation` (`:457-462`)
- `tests/test_patch_candidate_behavior_executor1r.py::test_exact_fixture_is_independent_and_bound_to_its_field_definition` (`:17-22`)
- `tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py::test_java_contract_audit_checks_exact_schema_and_policy_without_inventing_alias` (`:96-103`)
- `tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py::test_renaming_continuation_module_does_not_change_its_frozen_contract` (`:106-109`)
- `tests/test_synthetic_runtime_authorization.py::test_supported_scenario_has_exact_non_bank_contract` (`:69-115`)
- `tests/test_synthetic_runtime_authorization.py::test_contract_constructor_has_no_executable_text_extension` (`:160-167`; parametrized)
- `tests/test_synthetic_runtime_authorization.py::test_contract_and_nested_metadata_are_immutable` (`:195-207`)

Do not select a frozen test merely because its docstring says pure/effect-free.
For example, the lifecycle-closed retry's graph helper issues capabilities
(`tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py:29-42`), and
its test named `test_retry_issues_exactly_one_graph_and_stops_before_all_infrastructure`
explicitly counts issuance (`:112-124`). Its replay test also invokes issuance
through replay (`:161-164`).

Existing maintenance harnesses provide the reusable environment setup, without
authorization to run their broader suite selections:

- Disable bytecode and pytest plugin auto-loading before project import:
  `docs/roadmap/phases/RUNTIME_JAVA_PINNED_1A/validate_pure_phase.py:21-23`.
- Populate Windows `platform._uname_cache` from `sys.getwindowsversion` and
  process environment before dependency imports, avoiding platform's shell
  fallback: same file `:77-83`; later helper at
  `docs/roadmap/phases/RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1/validation.py:248-254`.
- Use workspace scratch `TEMP`/`TMP`/`TMPDIR`, disable cache provider, override
  project `addopts`, use explicit log and basetemp paths:
  `docs/roadmap/phases/RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1/validation.py:257-268`.
- Install effect denial before project imports. `tests/_preflight_runtime1_guard.py`
  denies process and network effects before imported project helpers (`:30-89`)
  and strict mode denies repository writes/traversal (`:116-157`). This guard
  does **not** itself prohibit process-local authorization/lease issuance. The
  current audit needs an additional issuance/consumption deny guard and narrow
  safe selection, without weakening frozen public validators.
- `tests/conftest.py:13` pins
  `MEMORY_TEMPERATURE_RETRIEVAL_ENABLED=false` before config imports.

No historical harness, provider replay, full runtime lifecycle suite, or
reflection lifecycle replay was run to produce this dependency map. A future
pinned reflection boundary remains a separate audit/implementation slice.
