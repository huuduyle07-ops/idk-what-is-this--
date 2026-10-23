# PREFLIGHT.RUNTIME.1

Bounded Runtime Diagnostic Authorization Contract: **COMPLETE_WITH_WARNINGS**.

`RuntimeDiagnosticAuthorization` deterministically separates evidence need,
capability availability, exact runtime policy authority and executor
availability. A trusted synthetic source proves an exact positive authority
path without consuming real human consent. The real BANK lineage still has no
valid runtime authority source and remains `diagnostic_execution_authority_missing`.
An authorized synthetic non-console scenario reaches
`authorized_but_executor_unavailable`; no executor is implemented.

## Files changed

| File | Responsibility |
| --- | --- |
| `core/runtime_diagnostic_authorization.py` | Additive immutable authority/source types and pure reconstruction validator. |
| `tests/test_preflight_runtime1.py` | Positive, scope, provenance, stale and effect-boundary regressions. |
| `tests/_preflight_runtime1_guard.py` | Beginning-of-suite process/effect denial. |
| `scripts/replay_preflight_runtime1.py` | Guarded synthetic replay and Python timing measurements. |
| `docs/roadmap/PREFLIGHT_RUNTIME_1.md` | Full authority/governance report. |
| `docs/roadmap/PREFLIGHT_RUNTIME_1_SYNTHETIC.json` | Synthetic authorization/negative results and measurements. |
| `docs/roadmap/phase_registry.json` | One narrow completed runtime-policy phase. |
| `tests/test_phase_registry.py` | Current registry counts and bounded phase metadata. |
| `tests/test_phase_picker.py` | History membership and unchanged recommendation. |
| `tests/_preflight_runtime1_maintenance.py` | Exact new bookkeeping reversal. |
| `tests/fixtures/preflight_runtime1_reversal.json` | Current phase's entry/post hashes only. |
| `tests/_patch_candidate_behavior_exec_admit1_maintenance.py` | Additive unwrap before prior exact historical reversal. |

Pre-existing work and frozen prerequisites are preserved. No stash, reset or
clean command is used. The maintenance layer restores the four changed shared
bookkeeping files byte-for-byte to their current entry state, then lets the
unchanged historical receipt chain apply. No older hash is repinned.

## Authority owner and schema

The additive owner is `core/runtime_diagnostic_authorization.py`. Its immutable
schema is `preflight_runtime_1_v1`, with separate recursively immutable lineage,
scope, source, effect-boundary and scenario-decision records. Its authority is
`bounded_runtime_diagnostic_only`; its purpose is exactly
`diagnostic_behavioral_evidence_acquisition`.

The closed source categories are `explicit_typed_task_runtime_authority`,
`explicit_human_runtime_authorization` and `frozen_policy_pre_authorization`.
**No category is operationally available from the existing frozen owners.**
Frozen Task Contract does not supply exact runtime-validation permission;
compile, evidence acquisition, structural scope, patch approval and Apply
records do not supply it either. The implementation adds no UI approval flow,
generic execute bit or interpretation of task prose as consent.

`issue_synthetic_runtime_authorization_source` is an explicitly separate fixture
seam. Its `SyntheticRuntimeAuthorizationSource` requires a synthetic fixture ID,
exact typed parents and exact scenario IDs. A process-local HMAC authenticates
issuance. Report JSON omits the private attestation and is rejected as an
authority input, including JSON claiming human approval. Even the source kind
`explicit_human_runtime_authorization` remains unmistakably synthetic, with
`real_human_approval=false`, `real_session_consumed=false` and
`operational_source=false`. Source kinds retain their own provenance rather
than becoming an unqualified boolean.

## Exact contract and freshness

The owner independently reconstructs the frozen execution plan and admission.
It binds task, repository identity and repository evidence, effective design,
implementation plan, admitted scope, candidate, exact virtual materialization,
successful compile receipt, behavioral specification, execution plan,
behavioral admission and evidence-requirement fingerprints. It never receives
a repository discovery root, UI waiting state or runtime object.

The complete selected scenario contract includes exact setup steps, constructor
and action definitions, literal fixtures and their provenance, exact return
observations and exact state observations. Authorization may select a subset
of planned scenarios; it cannot authorize a partial scenario, wildcard,
unplanned method or extra debugging field. It evaluates no behavioral oracle
and adds no fixtures, getter, reflection request or harness.

Read-only reflection scope consists only of the existing REFLECT.1
`read_exact_bound_field` requests. Their exact declaration/field identity,
request fingerprint, materialized source and trusted local descriptor remain
bound. Mutation, private-method invocation and field enumeration remain false.
A caller descriptor claiming execution permission, mutation or a different
target is rejected. Capability availability never supplies authority.

The authorization owner consumes exact existing admission requests or separately
supplied typed REFLECT parents and independently validates them. It has no
fallback that issues a new reflection request. For the console-blocked interest
fixture, the replay first constructs the exact frozen REFLECT parents outside
the authorization owner, then supplies them unchanged to source issuance,
authorization and validation. Missing required request parents fail closed;
authorization cannot omit observations to make a scenario fit.

`validate_runtime_diagnostic_authorization` reconstructs parents, source
authenticity, purpose, scenario subset, invocation/observation/reflection scope,
capability descriptors and effect restrictions. It accepts exported authorization
JSON only with a separately authentic current source, and rejects rehashed
extensions. Changed task, repository, candidate, materialization, compile,
SPEC, EXEC.PLAN or source invalidates the original authorization structurally;
`authorization_stale` is distinct from `authorization_source_invalid`,
`authorization_scope_mismatch` and authority escalation. No wall-clock expiry
is introduced.

Frozen historical admission/plan/SPEC/compile/reflection receipts retain their
bytes and fingerprints. Future-facing decisions remove the authority blocker
only from an exactly selected synthetic scenario. No historical admission is
rewritten or repinned.

## Independent authority and capability facts

| Case | Policy authority | Capability | Executor | Result |
| --- | --- | --- | --- | --- |
| Three real BANK non-console scenarios | False | Available | Unavailable | `diagnostic_execution_authority_missing` |
| Real BANK interest scenarios | False | Console missing | Unavailable | `blocked_missing_capability`, plus missing runtime authority |
| Direct-only fixture without source | False | Available | Unavailable | `diagnostic_execution_authority_missing` |
| Exact synthetic non-console scenario | True | Available | Unavailable | `authorized_but_executor_unavailable` |
| Exact synthetic read-only reflection scenario | True | Exact descriptor available | Unavailable | Policy authorizes bound requests; no reflection executes |
| Synthetic interest scenario | True for exact scope | Console missing | Unavailable | `blocked_missing_capability`; no console grant |

The three capability-ready BANK IDs remain
`BANK.wrong_credential_transfer`, `BANK.successful_transfer` and
`BANK.unsuccessful_debit`. `BANK.wrong_credential_interest` and
`BANK.savings_interest` still require `deterministic_console_input`. Independent
fields include `diagnostic_runtime_policy_authorized`,
`runtime_executor_available`, `reflection_capability_available` and
`console_capability_available`. `execution_ready=false` and
`execution_completed=false` remain explicit even on the positive path.

The contract forbids repository source writes, product-state persistence,
network use, process spawning beyond a future fixed runtime adapter, arbitrary
filesystem effects, arbitrary environment inspection and arbitrary shell. All
repository/product/reflection/test write and Apply authorities remain false.
Console and harness-generation authority remain false. These are policy
restrictions; their technical enforcement by a safe candidate executor has
**not** been implemented or claimed. No shell, Java, javac, PowerShell, bash or
cmd command payload can appear in this semantic authorization contract.

PREFLIGHT.REQUEST.1 remains compile-evidence-only for Java; its semantics are
unchanged. ACQUIRE.1 remains frozen and grants no execution permission. Real
BANK.2 waiting state, prior OOP clarification and patch-scope approval are not
consumed. MainApp is untouched.

## Verification and prior disclosure

The guard in `tests/_preflight_runtime1_guard.py` installs process, network and
console denial before project effect owners are imported. The outer pytest
bootstrap uses `strict=False` only to permit collection/cache I/O; the focused
suite and replay use `strict=True` before any fixture construction. Process
launch, compiler/Java, reflection adapter execution/source rendering, actual
runtime receipt issuance, console/PTY, model/provider/author paths, traversal
and writes are denied. It is verification machinery, not runtime isolation.

PREFLIGHT.RUNTIME.1 counters are independent: Java executions **0**, reflection
executions **0**, console openings **0**, javac invocations **0**, harness/JUnit
generation **0**, model/author calls **0**, consumer repository traversal **0**
and candidate/product source mutation **0**. Implementation and governance
files are the authorized phase changes, not candidate mutations.

**The prior EXEC.ADMIT.1 disclosed verification breach is preserved.** That
earlier phase accidentally selected an executed synthetic REFLECT fixture: one
synthetic JVM, one javac call, seven ephemeral Java files and 14 actual synthetic
field reads (11 finite and three rejected nonfinite reads). It ran no BANK
candidate and opened no console. Its prior disclosure and historical artifacts
are unchanged. None of those effects is counted as PREFLIGHT.RUNTIME.1 work.

The synthetic replay uses normalization-only illustrative compile receipts and
in-memory supplied BANK/direct-only fixture buffers. It never imports a
`synthetic_java_probe`. Its guard starts before project imports and covers
fixture construction, source issuance, reconstruction and every negative.
Serialized source reports cannot replay consent in another process.

Focused verification has **94 accepted passing cases** under process denial.
The full guarded run passed 93 cases in 549.73 seconds and exposed one overly
strict verification assertion: it treated the frozen validator's reconstruction
of supplied REFLECT parents as issuance of new requests. The corrected assertion
requires reconstruction to equal the supplied observation IDs, while the missing
required parent still fails closed. Its targeted guarded rerun passed in 31.29
seconds. The authorization owner needed no change; the provisional assertion
failure is excluded from accepted results. Both runs recorded zero actual Java,
javac, reflection and console execution. Two subagent warmup runs were stopped
while fixture reconstruction was optimized; their partial results are not counted.
Subagents later hit a usage limit, so the primary agent completed the final guarded
run, correction and report directly.

Accepted adjacent selections total **1350 passed, two skipped and six
baseline-confirmed failures**:

| Guarded selection | Passing checks | Other result |
| --- | ---: | --- |
| EXEC.ADMIT.1 / EXEC.PLAN.1 / SPEC.1 / MATERIALIZE.1 / AUTHOR.STRUCTURAL.1 | 381 | Pure selection. |
| REFLECT.1 / VALIDATE.1A | 99 | 70 REFLECT + 29 VALIDATE; execution/rendering fixtures excluded. |
| INPUT / Task Contract / EVIDENCE / ACQUIRE authority | 270 | Two inherited broad scans treat existing ignored `.tmp` test snapshots as production callers. |
| INPUT completion / preservation authority | 63 | Two dead semantic transport stub cases excluded because their stale stub seam reaches the guarded provider path; no model call occurs. |
| Human authority / Apply | 121 | Four inherited assertions expect historical UX.RUN picker winners or historical HARDEN.CLOSE status. |
| Registry / picker | 295 | New phase boundaries and unchanged DOGFOOD.1B recommendation. |
| Repository / path policy | 83 | Two skips. |
| PREFLIGHT compile/evidence authority | 38 | Compile semantics preserved; no compiler executed. |

The four human/Apply failures also occur against the exact before-runtime
registry restored by the new reversal helper. The two broad-scan failures are
the previously disclosed `.tmp/admit1/test_phase_registry.py` and
`.tmp/exec-plan1-governance-entry/test_phase_registry.py` snapshot paths; both
produce identical failure lists with this phase's new files excluded. No
historical expectation, receipt or artifact is repinned to make them pass.

The two initial transient bookkeeping failures occurred while the new reversal
receipt was not yet present; their corrected isolated rerun passes and is the
accepted result above. An initial INPUT/EVIDENCE selection hit guard denial on
its deterministic canned semantic client; the corrected guard explicitly
permits that exact offline fixture and all real provider effects remain denied.
Those provisional errors are excluded from accepted counts.

Benchmarks `--check`: **54 checked, zero errors**, under process denial. Windows
platform discovery initially attempted `subprocess.check_output`; the guard
denied it before process creation. The accepted rerun supplies the native
`sys.getwindowsversion` value to the metadata helper and performs no subprocess.
This denied attempt is separate from an execution count. Compileall, frozen
entry-hash preservation and final diff checks pass: compileall covers
`core web tests scripts benchmarks`, `git diff --check` reports no whitespace
errors, and all **25** exact frozen core/policy/source/BANK historical lineage
entry hashes remain unchanged. A separate whitespace check covers the new
untracked files. Logs are retained under ignored
`.tmp/preflight_runtime1_*` paths. Dependency/cache warnings are separate from
test results.

## Pure performance

Only Python stages are timed: parent reconstruction, authority-source
validation, scope projection, scenario binding, effect-boundary validation,
fingerprinting and total. Compile/JVM/provider latency is excluded. Timings are
external to the immutable authorization fingerprint. The saved JSON summarizes
three samples per fixture for two BANK layouts and the direct-only fixture,
determinism checks, exact exported authorization/source reports and unchanged
parent snapshots.

| Stage | BANK compatibility median ms | BANK max ms | Direct-only median ms | Direct-only max ms |
| --- | ---: | ---: | ---: | ---: |
| Parent reconstruction | 4567.0512 | 4595.8040 | 864.5112 | 973.3359 |
| Authority-source validation | 3.6575 | 6.5410 | 2.1579 | 2.4608 |
| Scope projection | 0.7449 | 1.4473 | 0.6126 | 0.6723 |
| Scenario binding | 1.7093 | 2.7367 | 1.5778 | 1.9094 |
| Effect-boundary validation | 1.2328 | 1.2943 | 1.1553 | 1.3200 |
| Authorization fingerprinting | 2.9555 | 3.0370 | 2.6431 | 4.0898 |
| Total | 4578.5564 | 4606.9028 | 875.7625 | 982.1803 |

Nested BANK total median/max: **3791.3971 / 4393.9043 ms**. Measurements ran
alongside guarded regression processes, so they characterize Python
reconstruction cost without claiming isolated throughput. The final replay
validates every exported exact authorization, preserves every parent snapshot,
rejects all **14** recorded negatives, preserves three synthetic source kinds,
and reports the console-blocked interest result with four independently supplied
REFLECT parents. No forbidden effect was attempted by the final replay:
`denied_effect_attempts={}`; all execution/generation/provider/traversal/source
mutation counters are zero.

## Requested report index

| Item | Result |
| --- | --- |
| 1. Files changed | Owner; focused tests; guard; replay; report/JSON; registry; registry/picker tests; new reversal helper/receipt; additive prior maintenance unwrap. |
| 2. Authority owner | `core/runtime_diagnostic_authorization.py`. |
| 3. Schema | `preflight_runtime_1_v1`; frozen recursively immutable exact typed records. |
| 4. Accepted source kinds | Three closed task/human/policy categories, explicit provenance. |
| 5. Real source availability | None operational. |
| 6. Synthetic authorization seam | `issue_synthetic_runtime_authorization_source`, process-local authenticated fixture only. |
| 7. Task Contract reuse | Inspected; no exact typed runtime permission, so fail closed. |
| 8. Human-authority provenance | Synthetic human kind is not real consent; report JSON cannot authenticate. |
| 9. Evidence purpose | Exact `diagnostic_behavioral_evidence_acquisition`. |
| 10. Scenario binding | Exact IDs and complete contracts; no wildcard/partial scenario. |
| 11. Invocation binding | Exact planned constructors, actions and setup definitions. |
| 12. Observation binding | Exact planned returns/state observations; no debug additions. |
| 13. Reflection binding | Only exact trusted REFLECT.1 `read_exact_bound_field` requests. |
| 14. Capability vs authority | Separate descriptor availability and policy authority facts. |
| 15. Policy vs executor | True synthetic policy authority, executor unavailable, execution-ready false. |
| 16. Effect prohibitions | Explicit mandatory policy prohibitions; enforcement unavailable. |
| 17. Network policy | Forbidden; any network grant rejects. |
| 18. Filesystem/write policy | Arbitrary effects forbidden; repository/product/reflection/test writes and Apply false. |
| 19. Console policy | No added capability or authority; interest remains console-blocked. |
| 20. Compile separation | PREFLIGHT.REQUEST.1 compile-evidence authority remains frozen. |
| 21. ACQUIRE.1 preservation | Frozen no-execution authority unchanged. |
| 22. Real BANK result | Missing diagnostic runtime authority. |
| 23. Synthetic result | Exact non-console scope policy-authorized, executor unavailable, completion false. |
| 24. Direct-only result | Capability alone remains unauthorized; trusted source proves positive policy path. |
| 25. Reflection result | Exact requests may be policy-authorized; no reflection runs. |
| 26. Interest result | Source cannot create deterministic console capability. |
| 27. Validator | Pure independent reconstruction of lineage/source/scope/effects. |
| 28. Stale handling | Structural task/repository/candidate/materialization/compile/SPEC/plan/source invalidation. |
| 29. Forged human negative | Caller JSON, missing/forged process-local attestation rejected. |
| 30. Overbroad scenario negative | Scenario outside EXEC.PLAN rejected. |
| 31. Extra method negative | Rehashed unplanned invocation rejected. |
| 32. Extra observation negative | Rehashed unplanned state/debug target rejected. |
| 33. Authority escalation negative | Any repository/product/reflection/test write, Apply, network or shell grant rejected. |
| 34. Console negative | Capability/console grant rejected; missing console remains missing. |
| 35. Source/session integrity | Exact synthetic provenance bound; real sessions untouched. |
| 36. Real BANK approval consumption | Zero. |
| 37. Java execution count | Zero for this phase. |
| 38. Reflection execution count | Zero for this phase. |
| 39. Console count | Zero. |
| 40. Javac count | Zero. |
| 41. Harness generation | Zero; JUnit generation zero; test-write authority false. |
| 42. Model/author calls | Zero provider/author effects. |
| 43. Traversal | Zero in the typed authorization consumer/replay; governance collection is external. |
| 44. Source mutation | Zero candidate/product mutation; MainApp untouched. |
| 45. Pure-suite effect guard | Installed before project imports/collection; strict guard before fixture creation. |
| 46. Prior EXEC.ADMIT.1 breach | One disclosed synthetic verification breach preserved separately. |
| 47. Performance | Seven Python stages only; measured replay artifact. |
| 48. Focused tests | 94 accepted passing cases: 93 in the full guarded run plus the corrected assertion's one passing targeted rerun. |
| 49. Adjacent tests | 1350 passed, two skipped, six baseline-confirmed inherited failures; provisional guard/bookkeeping failures and two dead provider transport stubs excluded. |
| 50. Registry/benchmarks | 295 registry/picker passes; 222 phases, CONTROL 40, history 218; unchanged DOGFOOD.1B; 54 benchmarks checked, zero errors. |
| 51. First remaining blocker | Real: `diagnostic_execution_authority_missing`; authorized synthetic: `runtime_executor_capability_missing`; console remains independent. |

## Direct answers

| Question | Answer |
| --- | --- |
| What exact typed source can grant runtime diagnostic authority? | An authenticated `SyntheticRuntimeAuthorizationSource` from the explicit fixture seam can prove it for exact current typed lineage/scope. No frozen real task/human/policy owner currently supplies a usable source. |
| Does behavioral evidence need grant authority? | No. |
| Does reflection capability grant authority? | No. |
| Does patch approval grant authority? | No. |
| Is real BANK currently authorized to execute? | No; `diagnostic_execution_authority_missing`. |
| Can synthetic explicit authorization prove a positive path without consuming real BANK? | Yes; process-local trusted synthetic records leave the real session untouched. |
| Does policy authorization imply a safe executor exists? | No; runtime executor unavailable and execution-ready false. |
| Does policy authorization make console available? | No. |
| Can authorization add methods or observations outside EXEC.PLAN? | No; exact scope reconstruction rejects them. |
| Did this phase run Java, reflection, compiler or console? | No; all four counters are zero under beginning-of-suite effect denial. |

The phase's stop condition is the deterministic separation of four facts and
the authenticated synthetic positive policy path with zero runtime effects.
Real approval/UI integration, enforceable runtime isolation, executor adapter
implementation and deterministic console capability remain future work.
