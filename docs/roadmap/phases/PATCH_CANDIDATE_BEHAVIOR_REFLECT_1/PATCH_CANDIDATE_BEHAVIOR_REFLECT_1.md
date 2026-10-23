# PATCH.CANDIDATE.BEHAVIOR.REFLECT.1

Exact Read-Only Reflection Diagnostic Capability.

This slice adds a deterministic diagnostic primitive for one exact private
`double` field. The target is reconstructed from the frozen execution plan,
behavioral specification and supplied materialized structural inventory.
Implementing the capability grants no product mutation or behavioral execution
authority. Frozen prerequisite owners and historical receipts remain unchanged.

## Files changed

| Path | Responsibility |
| --- | --- |
| `core/read_only_reflection.py` | Immutable requests, observations, descriptor, pure lineage validators and capability availability reconstruction |
| `core/read_only_reflection_java.py` | Exact target Java adapter rendering; receives an existing runtime object |
| `scripts/replay_patch_candidate_behavior_reflect1.py` | Pure BANK request and architecture reconstruction; no runtime observation |
| `tests/test_patch_candidate_behavior_reflect1.py` | Python boundaries and isolated synthetic Java infrastructure proof |
| `tests/_patch_candidate_behavior_reflect1_maintenance.py` | Exact new phase bookkeeping reversal |
| `tests/fixtures/patch_candidate_behavior_reflect1_reversal.json` | This slice's entry and post hashes; no historical repins |
| `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_REFLECT_1.md` | Capability contract and verification report |
| `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_REFLECT_1_SYNTHETIC.json` | Pure deterministic replay requests and capability reconstruction |
| `docs/roadmap/phase_registry.json` | One narrow complete diagnostic CONTROL slice |
| `tests/test_phase_registry.py` | Count, ownership and authority boundary assertions |
| `tests/test_phase_picker.py` | History membership and unchanged recommendation |
| `tests/_patch_candidate_behavior_exec_plan1_maintenance.py` | Unwrap new bookkeeping before frozen EXEC.PLAN reversal |

Pre-existing workspace work is preserved. The new reversal restores exact
entry bytes before the frozen prerequisite reversal chain; no historical
receipt is rewritten. Stash, reset and clean are never used.

## Capability contract

1. **Owner:** `core/read_only_reflection.py`; the Java renderer lives in
   `core/read_only_reflection_java.py`. The capability has one operation:
   `read_exact_bound_field`.
2. **Request schema:** frozen `ReadOnlyReflectionRequest` binds the exact field
   owner/name/type/definition identity/member fingerprint/materialized source
   fingerprint, exact expected runtime class, execution-plan fingerprint,
   scenario ID, obligation IDs, observation ID and closed observation role.
   Requests are reconstructed; user/model/runtime strings never select members.
3. **Observation schema:** frozen `ReadOnlyReflectionObservation` binds the
   request fingerprint, runtime identity, measured type, canonical finite value,
   success/failure and diagnostic adapter provenance; mutation authority is false.
4. **Descriptor:** `read_only_reflection`, `read_exact_bound_field`, supported
   value type `double`, availability `available_but_not_execution_admitted`;
   mutation, source write, reflective write, enumeration and private-method
   invocation authorities are false. It carries no runtime object handle.
5. **Exact target binding:** fields come only from validated EXEC.PLAN reflection
   observations and their SPEC/materialization lineage. Arbitrary fields, owners,
   definition identities or source fingerprints are rejected before reflection.
6. **Owner and inheritance:** `BankAccount.balance` retains `BankAccount` as the
   declaration owner when read on the exact planned `SavingAccount` class. The
   exact structural superclass relationship is bound; fuzzy name matching and
   runtime searches through unrelated superclass chains are absent.
7. **Type binding:** only exact instance `double` declarations are accepted.
   Static members and runtime type mismatches fail; values are never coerced.
8. **Member/source freshness:** exact definition ID, member SHA-256 and
   materialized source SHA-256 are reconstructed from supplied immutable inputs;
   stale fingerprints yield `reflection_target_stale` or a narrower mismatch.
9. **Supported values:** finite IEEE-754 `double` encoded as canonical lowercase
   16-digit bits. NaN and infinities are rejected. No object serialization,
   recursive object walking or additional primitive support is introduced.
10. **Accessibility:** the exact declaring class uses exact `getDeclaredField`;
    accessibility relaxation is scoped to that Field object for the read and is
    restored in `finally`. No accessible handle survives into another read.
11. **No writes:** no field setters, Unsafe, VarHandle/MethodHandle mutation,
    source mutation, visibility change, product getter or product API addition.
12. **No enumeration:** no generic discovery operation or member list is
    exposed. No field scanning, environment inspection, classloader exploration
    or module discovery is implemented.
13. **No invocation:** the adapter does not invoke private/product methods,
    constructors, getters, setters, transfers or interest. Future use supplies
    an already-created exact runtime object.
14. **Request validator:** `validate_read_only_reflection_request(...)`
    reconstructs the frozen execution-plan, SPEC and source lineage, observation
    role, owner relationship, capability and authority without UI/session trust.
15. **Observation validator:** `validate_read_only_reflection_observation(...)`
    checks request/target/runtime/type/canonical value/provenance/descriptor and
    closed false authority. Caller-authored observation JSON does not establish
    that an actual adapter read took place. A process-local authenticated adapter
    receipt seals the actual observation; changing or copying its value cannot
    forge origin. Current receipt issuance accepts synthetic infrastructure only.
16. **Evidence:** a balance observation records one diagnostic runtime state. It
    does not create human semantics, a product default or an oracle decision.
    Conservation, unchanged state and correct interest remain future reducer work.

## Infrastructure and negative matrix

The isolated Java proof uses only tiny synthetic `ReflectionFixture` and
`ReflectionChild` classes created in an ephemeral test workspace. It compiles
the phase-owned adapter and fixture, then exercises exact private, inherited
and independently bound fields. It creates no Java file in the product project
and executes no BANK candidate. The pure replay constructs requests for the
seven frozen BANK layouts without Java or reflection execution.

The focused suite covers exact private read, inherited exact declaration-owner
read, deterministic repeated reads, two independent fields, canonical finite
double values, descriptor/request/observation validation and capability
reconstruction. It rejects arbitrary/wrong fields, owner/type/member/source
mismatches, wrong plan/scenario/observation, static members, arbitrary JDK class,
enumeration, reflective writes, private methods, authority escalation, forged
observations and NaN/infinity. No source/API rewrite supplies observability.

## Resulting architecture truth

The frozen historical EXEC.PLAN receipt remains unchanged. A separate trusted
descriptor reconstruction reports the newly implemented reflection capability
as available without admitting behavioral execution. Direct authentication
return still uses its existing public surface. State observations now have a
bounded reflection primitive. Interest additionally requires deterministic
console input, which remains unavailable. Overall behavioral execution remains
incomplete; no console/PTY or full diagnostic harness is implemented.

The first remaining blocker is
`STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_NOT_IMPLEMENTED`.

## Verification

Registry and picker: **291 passed** in 5.34 seconds with a fresh test workspace.
There are **220 phases**, **38 CONTROL phases** and **216 complete/history
entries**; `DOGFOOD.1B` remains the recommendation. An initial default-workspace
run encountered the existing denied-access `tmp_tests` directory; the isolated
run completed all cases without that environment error.

Focused REFLECT.1 suite: **98 passed** in 199.03 seconds, including the accepted
isolated Java matrix and authenticated observation validator. The single
`google.genai` dependency warning is inherited. The synthetic Java workspace is
removed after the suite.

Benchmarks `--check`: **54 passed, 0 failed**.

Pure replay: **7 layouts**, **126 exact requests**, **13 rejected negative
cases**, with five repeat measurements per layout. Every request is independently
validated against the complete frozen lineage. Repeats yield equal immutable
requests/fingerprints, and original source/candidate/specification/historical
plan bytes remain unchanged. Reflection is reconstructed as
`available_but_not_execution_admitted`, console as `unavailable` and overall
execution as `execution_capability_incomplete`.

VALIDATE.1A pure selections together: **39 passed, 17 excluded non-pure compiler
cases**. No BANK javac or runtime execution occurs.

The ten frozen adjacent phase files pass **655 tests** in 1289.01 seconds:
EXEC.PLAN.1, BEHAVIOR.SPEC.1, MATERIALIZE.1, AUTHOR.STRUCTURAL.1 and
ADMIT/PLAN/APPROVE/REFRESH/RECHECK/EXPAND. Seven inherited dependency warnings
remain separate from test results. This suite compiles and executes no BANK
Java.

Apply, human authority and repository/path boundaries: **279 passed, 2 skipped,
3 inherited failures** across the selected groups. The old
`test_human_authority_branch_checkpoint.py::test_real_registry_marks_human_close_complete_and_picker_recommends_adopt_model_1`
expects `UX.RUN.1`; preserved current registry recommends `DOGFOOD.1B`. The same
failure is reproduced against the exact registry before REFLECT.1 using the new
reversal helper. Two frozen author attribution assertions additionally expect
historically reversed `web/runner.py` hash
`6b4e907c6ed14bc89dcaebe27541280b113a62babe01a8b570be6e368a666e6e`;
the preserved reversal computes
`a2d510567968b9bc11193940f0847424631b700bc095ee5628a19654e2227ee5`.
These are the same preserved failures documented in the frozen EXEC.PLAN.1 and
BEHAVIOR.SPEC.1 reports. Their assertions and every frozen receipt remain
unchanged. The path-policy-specific group passes all **46 cases**.

The requested focused, adjacent, pure compiler-validation, authority/path and
registry groups total **1362 passed, 2 skipped, 3 inherited failures**. The
dedicated new/historical bookkeeping reversal check additionally passes both
cases, including appended-byte tamper rejection. Full
`python -m compileall -q core web tests scripts benchmarks` and
`git diff --check` pass. No frozen test or historical receipt is repinned to
change the inherited outcomes.

Synthetic infrastructure accounting: the accepted complete proof batch compiles
once and starts one JVM. Session verification also ran one earlier infrastructure
batch, so cumulative infrastructure Java execution is **2**, with **0 BANK
behavioral Java executions** across both batches. The pure replay itself compiles
nothing, starts no JVM and produces no runtime observations. Fixture compilation
and JVM process time are reported separately from per-read diagnostic latency.

The accepted synthetic probe records JVM identity **26.0.2.1+1-7**, adapter
version **exact_read_only_reflection_v1**, request fingerprints and exact fixture/
adapter source SHA-256 hashes. JVM identity is diagnostic metadata. Fixture
compilation takes **3.0968255 seconds** and the complete JVM process takes
**0.6397236 seconds**; neither is included in the per-read timing below.

| Ten positive synthetic reads | Median ms | Max ms |
| --- | ---: | ---: |
| Exact runtime/field validation | 0.00615 | 0.2044 |
| Scoped accessibility and reflection read | 0.01595 | 15.9812 |
| Canonical Java value normalization | 0.0048 | 0.9438 |
| Total adapter diagnostic read | 0.0274 | 17.7586 |

The maximum includes first-read JVM/reflection initialization within the read
operation. The eight later reads, excluding each adapter's first observation,
have median reflection latency **0.0091 ms** and median total diagnostic latency
**0.02005 ms**. Their maxima are **0.025 ms** and **0.0506 ms**, respectively.
This is synthetic capability verification, not BANK behavioral evidence.

| Compatibility authorization, five pure repeats | Median ms | Max ms |
| --- | ---: | ---: |
| Request authorization reconstruction | 774.7841 | 789.4916 |
| Exact target validation | 4.1695 | 5.4012 |
| Total request diagnostic overhead | 779.4204 | 793.7158 |

These timings reconstruct the full frozen Python lineage and exact source
binding. They perform no reflection read; the replay identifies read,
normalization and observation fingerprint timing fields as unmeasured rather
than interpreting their zero counters as latency. The separate accepted-row
Python bridge benchmark measures normalization at **0.0389 ms median / 1.0027 ms
maximum**, and immutable observation fingerprinting at **0.3387 ms median /
0.5474 ms maximum**, over five repetitions without another JVM invocation.

The saved JSON has distinct pure replay and accepted infrastructure verification
sections. It binds all twenty synthetic runtime rows to adapter/request/source/
JVM metadata and labels them diagnostic evidence. Serialized report metadata
cannot substitute for the separately authenticated process-local adapter receipt.

## Requested report index

| Item | Result |
| --- | --- |
| 1. Files changed | Twelve scoped files listed above; frozen core/product files and historical receipts are preserved. |
| 2. Capability owner | `core/read_only_reflection.py`, with exact Java renderer `core/read_only_reflection_java.py`. |
| 3. Request schema | `patch_candidate_behavior_reflect_1_v1`; immutable exact target/runtime/plan/scenario/obligation/observation binding. |
| 4. Observation schema | Request and descriptor fingerprints, exact runtime/declaration/type, canonical value, status, provenance, mutation=false. |
| 5. Descriptor | Read-only field operation, double-only, available without execution admission; all authority flags false. |
| 6. Exact target | Only the two exact EXEC.PLAN-bound private balances. |
| 7. Owner/inheritance | Same exact class or exact validated direct superclass; declaration owner is retained. |
| 8. Type | Exact private instance `double`, with no coercion. |
| 9. Member/source | Exact definition identity/member SHA-256/materialized source SHA-256 revalidated. |
| 10. Value types | Finite IEEE-754 double only; negative zero bits retained. |
| 11. Accessibility | Fresh exact Field; relaxation used for one read and restored in `finally`. |
| 12. No-write | Setter/mutation paths absent; authority escalation rejected. |
| 13. No-enumeration | Exact `getDeclaredField` only; discovery schema rejected. |
| 14. No-method invocation | No private/product call, constructor, getter or action operation. |
| 15. Request validator | Pure `validate_read_only_reflection_request` reconstructs exact frozen lineage. |
| 16. Observation validator | `validate_read_only_reflection_observation` checks lineage plus authenticated actual-read receipt. |
| 17. Private-field positive | Synthetic exact private field read passes without a getter. |
| 18. Inherited positive | Synthetic exact superclass read retains declaration owner. |
| 19. Wrong field | Rejected before reflection. |
| 20. Wrong owner | Rejected before reflection; no owner aliasing. |
| 21. Wrong type | Request mismatch rejected; synthetic runtime int rejected without conversion. |
| 22. Stale source | Rejected before reflection. |
| 23. Wrong plan | Plan/scenario/obligation/observation drift rejected. |
| 24. Arbitrary class | Arbitrary JDK target and unplanned runtime subclass rejected. |
| 25. Enumeration | Invalid closed schema. |
| 26. Write | `reflection_authority_escalation`; no mutable transport or adapter path. |
| 27. Method | `reflection_authority_escalation`; no invocation operation. |
| 28. Authority | Product/source/reflective write/private invocation/discovery/execution/test-write/Apply false. |
| 29. Infrastructure Java | Accepted batch: one javac and one JVM; session cumulative: two of each. |
| 30. BANK behavioral Java | Zero, including no BANK construction, compile, action or runtime read. |
| 31. Console | Zero console/PTY openings; deterministic input remains unavailable. |
| 32. Model/author | Zero calls. |
| 33. Repository traversal | Zero in capability/replay/runtime; only supplied exact typed buffers consumed. |
| 34. Source mutation | Zero product source/API/candidate mutation or Apply. |
| 35. Capability reconstruction | Separate immutable descriptor projection; frozen EXEC.PLAN bytes and fingerprint retained. |
| 36. Partial readiness | Direct returns available, reflection available without admission, console unavailable, execution incomplete. |
| 37. Performance | Independent authorization/target/read/normalization/fingerprint/total timing tables above; javac/startup excluded. |
| 38. Focused tests | 98 passed; authentic synthetic receipt and mutation/discovery/invocation negatives included. |
| 39. Adjacent tests | Ten prerequisite files: 655 passed; pure VALIDATE: 39 passed/17 non-pure excluded; authority/path: 279 passed/2 skipped/3 inherited failures. |
| 40. Registry/benchmarks | Registry/picker 291 passed; benchmarks 54 passed, zero errors. |
| 41. First blocker | `STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_NOT_IMPLEMENTED`; console remains missing. |

## Direct answers

| Question | Answer |
| --- | --- |
| Can the harness now read one exact private field without adding a getter? | The exact adapter primitive supports it; the isolated synthetic proof passes. A future harness still needs execution admission. |
| Can it read inherited `BankAccount.balance` on `SavingAccount` while retaining the owner? | Supported by the exact direct-superclass binding and verified with the equivalent synthetic fixture. BANK runtime is not executed. |
| Can it enumerate arbitrary fields? | No. |
| Can it write private state? | No. |
| Can it invoke private methods? | No. |
| Are reflection targets fixed by EXEC.PLAN rather than runtime strings? | Yes. |
| Did any BANK behavioral scenario execute? | No. |
| Did product source/API change? | No. |
| Does this phase authorize future behavioral execution? | No. |
| Is deterministic console/PTY still missing? | Yes. |

Model calls, author calls, runtime repository traversals and product source
mutation are zero; write and Apply authorities remain false.
