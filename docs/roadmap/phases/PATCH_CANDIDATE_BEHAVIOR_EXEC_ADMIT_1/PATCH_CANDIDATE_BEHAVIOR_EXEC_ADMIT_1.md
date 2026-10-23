# PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1

Pure bounded behavioral execution admission: **COMPLETE_WITH_WARNINGS**.

The immutable admission and validator classify every frozen scenario, preserve
exact lineage, fixtures and observations, and fail closed on current authority.
The requested three-scenario execution admission cannot be issued under the
frozen prerequisites: `PREFLIGHT.REQUEST.1` supports only `compile_evidence`
over Java, while runtime/test evidence is deferred. ACQUIRE.1 explicitly grants
no execution authority. A typed behavioral evidence need is a requirement,
not permission to start Java. No runtime token or human approval mechanism is
invented in this phase.

| Exact BANK scenario | Capability eligibility | Admission | Typed reason |
| --- | --- | --- | --- |
| `BANK.wrong_credential_transfer` | All mechanisms available | `blocked_authority` | `diagnostic_execution_authority_missing` |
| `BANK.successful_transfer` | All mechanisms available | `blocked_authority` | `diagnostic_execution_authority_missing` |
| `BANK.unsuccessful_debit` | All mechanisms available | `blocked_authority` | `diagnostic_execution_authority_missing` |
| `BANK.wrong_credential_interest` | Console missing | `blocked_missing_capability` | `deterministic_console_input` |
| `BANK.savings_interest` | Console missing | `blocked_missing_capability` | `deterministic_console_input` |

Capability-ready IDs are deliberately separate from execution eligibility.
`admitted_scenarios`, admitted invocation targets, admitted observations,
admitted reflection requests and admitted capability descriptors are empty
under current authority. The original plan's historical capability labels and
fingerprint remain unchanged. Blocked obligations are **not yet measured**,
not behavioral failures.

## Files changed

| File | Responsibility |
| --- | --- |
| `core/behavioral_execution_admission.py` | Frozen immutable admission, descriptors, decisions, coverage and pure reconstruction validator |
| `scripts/replay_patch_candidate_behavior_exec_admit1.py` | Guarded synthetic lineage replay and Python performance measurements |
| `tests/test_patch_candidate_behavior_exec_admit1.py` | Pure exact scope, capability, fixture, authority, stale and forgery regressions |
| `tests/_patch_candidate_behavior_exec_admit1_maintenance.py` | Exact new bookkeeping reversal |
| `tests/fixtures/patch_candidate_behavior_exec_admit1_reversal.json` | New entry/post hashes only |
| `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_EXEC_ADMIT_1.md` | This report |
| `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_EXEC_ADMIT_1_SYNTHETIC.json` | Immutable replay results and measured performance |
| `docs/roadmap/phase_registry.json` | One narrow authority-classification slice |
| `tests/test_phase_registry.py` | Registry totals and new slice boundaries |
| `tests/test_phase_picker.py` | History membership and unchanged recommendation |
| `tests/_patch_candidate_behavior_reflect1_maintenance.py` | Unwrap new bookkeeping before exact frozen REFLECT reversal |

Existing candidate/product/frozen owner files and historical receipts are
preserved. Stash, reset and clean are never used. Python phase tests are added;
`SavingAccountBehaviorTest.java` stays a proposed test path with no write grant.

## Reconstruction and execution boundaries

The schema is `patch_candidate_behavior_exec_admit_1_v1`. Its scope is
`diagnostic_behavioral_execution_only`. Frozen dataclasses recursively reject
mutable nested values. Canonical fingerprints exclude external timing data.

The producer first runs `validate_behavioral_evidence_execution_plan` against
the exact frozen SPEC, compile receipt, materialization, candidate, admitted
scope, implementation plan, design, repository identity/path evidence and
supplied source buffers. It independently validates SPEC before deriving the
evidence requirement fingerprint. It accepts no repository-root acquisition
seam, UI state, session decision, source traversal, shell string or runtime
object. A changed parent fails `admission_stale`; historical objects stay intact.

Authority reconstruction binds the exact scope's behavioral
`ValidationEvidenceNeed` rows, SPEC evidence requirements, ACQUIRE.1 authority
and the trusted PREFLIGHT diagnostic policy/adapter registry. It consumes the
contract without calling an acquisition or verification engine. The frozen
EVIDENCE.1 live-import boundary remains intact.

Capability reconstruction independently obtains and validates REFLECT.1's
local descriptor. Its operation is `read_exact_bound_field`, availability is
`available_but_not_execution_admitted`, and mutation, enumeration and method
invocation are false. Caller-authored JSON is rejected as a capability input;
supplied typed descriptors are checked against local implementation truth.
Explicit absence blocks entire state-dependent scenarios without a fallback.

Direct capabilities bind exact canonical constructors, methods, signatures,
definition/source fingerprints and return targets. Public and package access
are reconstructed from the supplied materialized syntax inventory. Exact query
methods and package-access fields are retained in their appropriate descriptor;
there is no method-name-string invocation operation. Console availability is
always `unavailable` and an interest scenario cannot omit that requirement.

For each capability-ready scenario, the producer reconstructs the exact public
REFLECT.1 requests. Wrong-credential transfer owns four balance reads plus its
exact boolean return; successful transfer owns four balance reads and its exact
planned action; unsuccessful debit owns two savings reads and the planned
failure fixture. No ordinary-balance assertion is added to failed debit.
These requests describe eligibility provenance, and are **not admitted runtime
observations** while the scenario is blocked by authority.

All constructor/action/setup fixtures and `diagnostic_fixture`,
`implementation_fixture`, and `implementation_contract` provenance are copied
from the canonical plan. No balance, amount, credential, holder, rate or oracle
is selected or reduced here. Static `credential_lifecycle` and
`base_savings_transition` obligations are `static_not_executed` with no runtime
actions. Shared obligations retain every associated scenario rather than
collapsing interest blockers into successful transfer evidence.

Every scenario records prospective ephemeral workspace, exact candidate bytes,
fresh instance, no repository source write, 60-second wall-clock timeout,
65,536-byte stdout and stderr limits, child cleanup, no arbitrary command
surface, no persistent diagnostic artifacts, and no network or persistence
grant. These are requirements, **not implemented enforcement**.
`runtime_executor_capability_missing` remains explicit; hard network/filesystem
isolation and minimum runtime-boundary enforcement are not claimed.

Actual reflection evidence still requires the process-local authenticated
adapter receipt. JSON alone cannot authenticate a read. Current receipt issuance
supports only synthetic infrastructure, so candidate-runtime receipt issuance
is separately marked unavailable. A future executor must revalidate all parents,
capabilities, fixtures and exact requests, and cannot invent another field read
or method call. Harness generation, Java execution, reflection execution,
console, network, product/repository/test writes, candidate revision, arbitrary
shell and Apply all remain unauthorized.

## Verification disclosure

The admission owner, new focused tests and pure replay perform zero Java,
reflection reads, console openings, javac, provider/model/author calls,
repository traversals, candidate revisions or Java source generation. Effect
guards deny process launch, adapter source rendering and actual-read receipt
issuance in the new replay and focused suite.

**The session-wide zero-execution constraint was violated during verification.**
An initial REFLECT regression selector accidentally retained
`test_receipt_issuance_remains_closed_to_candidate_runtime`, which depends on
`synthetic_java_probe`. That frozen fixture generated seven ephemeral synthetic
Java files, invoked javac once and started one JVM. It made 20 adapter attempts,
including 14 actual field reads (11 finite successes and three nonfinite values
rejected after reading). It executed no BANK candidate, opened no console and
mutated no product source. The temporary Java workspace was cleaned by the
fixture; its synthetic metrics were written to the existing ignored `.tmp`
diagnostic path. The error was disclosed to the user when discovered.

The corrected REFLECT selection additionally excludes `receipt_issuance`, and
runs with process/compiler/source-rendering guards. It passes **70 tests**;
28 runtime/rendering cases are excluded. The unguarded initial 71-test run is
not evidence of compliance with the user's no-execution requirement.

Final focused EXEC.ADMIT.1 suite: **79 passed** in 383.73 seconds. It includes
seven exact BANK layouts, direct-only/renamed/additional-target fixtures,
descriptor/request/method/fixture/coverage tampering, authority forgery,
constructor bypass, nested immutability, source/receipt/effect guards and exact
bookkeeping restoration.

The ten frozen adjacent phase files pass **655 tests** in 1137.03 seconds:
EXEC.PLAN.1, SPEC.1, MATERIALIZE.1, AUTHOR.STRUCTURAL.1 and
ADMIT/PLAN/APPROVE/REFRESH/RECHECK/EXPAND. Pure VALIDATE.1A selection:
**29 passed**, 27 non-pure/facade cases excluded. Registry/picker:
**293 passed**; separately checked frozen bookkeeping chain: **3 passed**.
Benchmarks `--check`: **54 checked, zero errors**. Compileall over
`core web tests scripts benchmarks` and `git diff --check` pass. An explicit
whitespace check also covers new files, which ordinary Git diff omits while
they remain untracked.

Evidence/diagnostic authority, human/Apply and repository/path selections have
**564 passing checks, five skips and six inherited failures** after fixing the
introduced EVIDENCE import boundary. Repository/path accounts for 172 passing
checks; pure human/Apply accounts for 85; diagnostic policy accounts for 40
under external-process denial. The original evidence run passed 266 checks;
its fixed EVIDENCE import regression now passes independently.

Two frozen broad unreachable scans also inspect pre-existing
`.tmp/admit1/test_phase_registry.py` and
`.tmp/exec-plan1-governance-entry/test_phase_registry.py` snapshots as live
production callers. They fail on the identical paths with only this new owner
excluded from scanning. Those snapshots are preserved. Four human registry
checks expect historical picker winners or historical `HARDEN.CLOSE` status;
current and exact pre-admission registries produce the same failures. The
pre-admission registry SHA-256 is
`d9730741dcc7052473e3377b51d9dc777deaea0aab8a75d9d299b6e9713aae31`.
No frozen expectation, historical receipt or prerequisite is repinned.

Verification logs are retained in ignored `.tmp/exec_admit1_authority`,
`.tmp/exec_admit1_adjacent.log`, `.tmp/exec_admit1_validate.log`,
`.tmp/exec_admit1_reflect_guarded.log` and the new replay artifact. Dependency
deprecation and cache-directory warnings remain distinct from test outcomes.

The replay completes seven BANK layouts plus the direct-only existing-surface
fixture, with five independently reconstructed identical admission fingerprints
per fixture. Every exported admission is validated against the exact frozen
parents; every parent snapshot remains unchanged. Twenty replay boundary cases
record the absent reflection/console/authority state and rejected authority,
source/command/test-path and stale-parent payloads. The focused suite contains
the additional request, method, fixture, semantic and schema forgery matrix.

Accepted selected verification totals are **1690 passed, five skipped and six
baseline-confirmed failures**. The separate three bookkeeping checks and initial
71-test accidental synthetic run are excluded from that total to avoid counting
duplicates or treating the erroneous run as a pure regression result.

## Performance

Five samples per fixture; Python admission construction only. Timings are
outside immutable admissions and were measured alongside regression processes.
No compiler/JVM/provider latency is included. Reflection-request reconstruction
calls the public frozen REFLECT request builder, which revalidates the full
parent lineage for each exact request; these are not actual reflection-read
timings. Direct-only scenarios perform no request reconstruction.

| Stage | BANK compatibility median ms | BANK max ms | Direct-only median ms | Direct-only max ms |
| --- | ---: | ---: | ---: | ---: |
| Execution-plan/SPEC reconstruction | 1510.1207 | 1864.1741 | 1331.7633 | 1357.0504 |
| Evidence-authority validation | 2.5985 | 2.9475 | 2.0398 | 2.1879 |
| Capability descriptor reconstruction | 3.2627 | 3.5195 | 3.1037 | 3.9454 |
| Exact reflection-request reconstruction | 7809.2190 | 8472.2294 | 0.0080 | 0.0091 |
| Scenario classification | 1.7729 | 2.6208 | 1.7491 | 2.0299 |
| Coverage projection | 0.1387 | 0.1688 | 0.1294 | 0.1360 |
| Admission fingerprinting | 11.6449 | 13.5259 | 8.8069 | 8.8882 |
| Total | 9247.2608 | 10364.1641 | 1353.7220 | 1379.1137 |

The saved JSON contains all eight fixtures' timing distributions, exact
admissions, capability eligibility, fingerprints, parent preservation and
negative outcomes. These measurements establish reconstruction cost, not BANK
behavioral validity or future executor throughput.

## Requested report index

| Item | Result |
| --- | --- |
| 1. Files changed | Eleven scoped files listed above; pre-existing workspace work preserved. |
| 2. Admission owner | `core/behavioral_execution_admission.py`. |
| 3. Schema | `patch_candidate_behavior_exec_admit_1_v1`; frozen nested records and deterministic fingerprint. |
| 4. Evidence authority | Exact typed scope/SPEC needs plus frozen ACQUIRE.1 and PREFLIGHT.REQUEST.1 policy; runtime grant missing. |
| 5. EXEC.PLAN reconstruction | Full public frozen validator before classification. |
| 6. Descriptor reconstruction | Local exact REFLECT descriptor; canonical exact direct surfaces; unavailable console. |
| 7. Scenario classification | Every runtime scenario explicit; three authority blockers and two console blockers. |
| 8. Wrong transfer | Capability-ready, authority-blocked; exact two-field before/after reads and boolean return retained. |
| 9. Successful transfer | Capability-ready, authority-blocked; exact planned constructor, credentials, amount and four reads retained. |
| 10. Unsuccessful debit | Capability-ready, authority-blocked; selected failure fixture and two savings reads only. |
| 11. Wrong interest | Atomic console-capability blocker. |
| 12. Savings interest | Atomic console-capability blocker. |
| 13. Reflection requests | Ten exact eligible-request reconstructions per BANK layout; admitted request set empty. |
| 14. Direct invocation | Exact bound constructor/method surface descriptors; no invocation is currently admitted. |
| 15. Direct return | Exact planned boolean targets, including planned setup returns; no capture currently admitted. |
| 16. Process-local receipt | Required; serialized observation JSON is insufficient; candidate receipt issuer unavailable. |
| 17. Fixture preservation | Exact canonical plan values and diagnostic/implementation provenance; no reselection. |
| 18. Partial coverage | Static facts separated from blocked, unmeasured runtime evidence; no all-scenarios gate. |
| 19. Static obligations | Credential lifecycle and base savings transition remain static satisfied, not executed. |
| 20. Isolation | Explicit prospective requirements above; no false enforcement claim. |
| 21. Executor capability | `runtime_executor_capability_missing`. |
| 22. Network | No grant. |
| 23. Repository/product write | False. |
| 24. Reflection write | False. |
| 25. Console | False; no adapter added. |
| 26. Test file | Proposed only; Java/JUnit test write false. |
| 27. Harness generation | Unauthorized. |
| 28. Java execution | Owner/replay zero; session verification one accidental synthetic JVM, zero BANK. |
| 29. Reflection execution | Owner/replay zero; session verification 14 synthetic field reads. |
| 30. Console execution | Zero. |
| 31. Javac execution | Owner/replay zero; session verification one accidental synthetic compiler call. |
| 32. Model/author calls | Zero in admission/replay/verification providers. |
| 33. Traversal | Zero in admission/replay; test governance inspections are outside the admission consumer. |
| 34. Validator | `validate_behavioral_execution_admission` reconstructs exact parents, policy, descriptors, decisions, requests, fixtures and authority. |
| 35. Stale handling | Changed parent/policy/descriptor fails; historical admission immutable. |
| 36. Idempotency | Same current inputs, capabilities and authority yield identical rows and fingerprint. |
| 37. Direct-only fixture | All five capability-ready; renamed and additional targets also covered; runtime authority still missing. |
| 38. Reflection missing | All state scenarios atomically blocked, no getter fallback. |
| 39. Console-missing partial | Only interest loses capability eligibility; other three retain their independent authority blocker. |
| 40. Forged descriptor | Mutation/authorization/operation drift and caller JSON rejected. |
| 41. Scope mismatch | Extra field, method, fixture, observation, coverage or scenario rejected even after rehashing. |
| 42. Authority negatives | Execution/write/Apply/test/reflection/console/network/harness grants and shell/source payloads rejected. |
| 43. Performance | Eight external timing stages; Python reconstruction only; final table below. |
| 44. Focused tests | Final results below. |
| 45. Adjacent tests | Final results below; runtime/compiler test exclusions explicit. |
| 46. Registry/benchmarks | 221 phases, CONTROL 39, history 217; DOGFOOD.1B unchanged; 54 benchmarks valid. |
| 47. First blocker | `diagnostic_execution_authority_missing`, followed by safe runtime executor and console capability. |

## Direct answers

| Question | Answer |
| --- | --- |
| Which BANK scenarios are now eligible for future execution? | None under current frozen authority. Wrong transfer, successful transfer and unsuccessful debit have all mechanisms but remain authority-blocked. |
| Which remain blocked? | All five: three by missing authority, two by console capability. |
| Can console absence block only interest? | Yes. Classification is atomic per scenario and imposes no pipeline-wide capability gate. |
| Does any scenario gain product write or Apply? | No. |
| Are observations limited to REFLECT.1 requests? | Yes; only canonical exact requests are reconstructed. No request is currently execution-admitted. |
| Can an executor add reads or calls? | No; exact reconstruction rejects extensions, and any future executor must revalidate. |
| Is process-local authentication preserved? | Yes. |
| Is diagnostic harness generation authorized? | No. |
| Did Java/reflection/console execute? | The new phase did not execute them. Session verification mistakenly ran one synthetic JVM/compiler and 14 synthetic reads; console and BANK execution remained zero. |
| Does this permit incremental coverage? | Its classifications and coverage preserve independent per-scenario progress. Actual runtime admission needs an existing valid runtime authority contract; this phase does not invent one. |

The requested positive stop condition (three admitted BANK scenarios with zero
session execution) is **not achieved**. The authority prerequisite remains
missing, and the verification-selection breach cannot be undone. No harness or
executor implementation is added to conceal either limitation.
