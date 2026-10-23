# PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1

Bounded Behavioral Evidence Execution Planning — COMPLETE_WITH_WARNINGS / FROZEN.

The immutable plan answers how the frozen behavioral oracle could be measured.
It reconstructs SPEC.1 and its full compile/materialization/candidate/admission/
PLAN/design lineage before selecting bounded diagnostic routes. It never
executes, grants authority, or changes the oracle or product API.

## Changed files

| Path | Role |
| --- | --- |
| `core/behavioral_evidence_execution_plan.py` | Pure planner, immutable records, canonical consumer validator |
| `scripts/replay_patch_candidate_behavior_exec_plan1.py` | Synthetic replay and fully validated direct-surface positive fixture |
| `tests/test_patch_candidate_behavior_exec_plan1.py` | Planning infrastructure regressions, with forbidden-effect guards |
| `tests/_patch_candidate_behavior_exec_plan1_maintenance.py` | Exact phase bookkeeping reversal |
| `tests/fixtures/patch_candidate_behavior_exec_plan1_reversal.json` | New entry/post bookkeeping hashes; no historical repins |
| `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_EXEC_PLAN_1.md` | This implementation and verification report |
| `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_EXEC_PLAN_1_SYNTHETIC.json` | Immutable illustrative plans, negative outcomes, measured Python timings |
| `docs/roadmap/phase_registry.json` | One narrow complete CONTROL slice |
| `tests/test_phase_registry.py` | New row/count/boundary checks |
| `tests/test_phase_picker.py` | History count and unchanged recommendation checks |
| `tests/_patch_candidate_behavior_spec1_maintenance.py` | Unwrap only this new bookkeeping before historical SPEC.1 reversal |

Pre-existing workspace changes and frozen prerequisite sources/receipts remain
preserved. The new reversal helper verifies original bytes throughout the
historical chain. No stash, reset, or clean is used.

## Runtime routes

Every scenario uses a fresh exact candidate instance. Constructor fixture:
opening ordinary balance **1000**, credential **`exec-plan-correct`**. Incorrect
credential: **`exec-plan-incorrect`**. Nonsemantic String constructor parameters,
when present, use **`exec-plan-holder`**. These are bounded synthetic diagnostics,
not production defaults, user secrets, or human commitments.

| Scenario | Action and setup | Observations and frozen oracle | Missing BANK capabilities |
| --- | --- | --- | --- |
| Wrong-credential transfer | Transfer 200 with incorrect credential | Boolean false; ordinary and savings before/after unchanged. Shares authentication-return and failed-auth obligations. | State assertions require exact read-only reflection; return assertion itself does not. |
| Wrong-credential interest | Correct transfer 200 first; verify setup return true; invoke exact interest with incorrect console credential | Nonzero savings 200 and distinct ordinary 800 before operation; both states remain unchanged. Covers the second operation in `request_each_savings_operation`. | Reflection and deterministic console input |
| Successful transfer | Transfer 200 with correct credential and implementation-proven sufficient initial balance | Ordinary decreases by 200, savings increases by 200, total conserved | Reflection |
| Unsuccessful debit | Transfer 1001 with correct credential, against opening balance 1000 | Transfer false; savings before/after has no credit. Ordinary observation is not added as a redundant requirement. | Reflection |
| Savings interest | Correct transfer 200 first; verify setup return true; invoke selected interest with correct credential | Savings follows the frozen selected simple-rate calculation; ordinary stays unchanged | Reflection and deterministic console input |

The rate fixture is **0.0625**, with **2** for a second numeric parameter when
the selected operation has one. These binary-exact fixtures work for float and
double parameters. The current BANK contract has one rate parameter: savings
200 yields expected savings 212.5; ordinary remains 800. Arithmetic provenance
stays `implementation_contract`; amount 1001 is `implementation_fixture`, with
the exact debit-definition hash as evidence. It asserts no permanent overdraft
policy. Other fixture values are `diagnostic_fixture`.

Numeric state relations use finite values and
`abs(actual-expected) <= 1e-9 + 1e-12 * abs(expected)`. This tolerance is
`diagnostic_implementation_policy`, never domain semantics. Boolean relations
retain their exact frozen truth values.

## Implementation contract and requested report

1. **Files changed:** the eleven paths above; historical hashes are not repinned.
2. **Owner:** `core/behavioral_evidence_execution_plan.py` exposes
   `build_behavioral_evidence_execution_plan(specification, *, compile_receipt,
   materialized, candidate, admitted_scope, timings=None, **fresh_inputs)`.
3. **Schema:** `patch_candidate_behavior_exec_plan_1_v1`. Frozen slotted records
   recursively bind complete lineage, obligations, scenarios, fixtures, exact
   members, observations, capabilities, blockers and selected calculations.
4. **SPEC gate:** the frozen `validate_behavioral_validation_specification`
   reconstructs its full canonical lineage before candidate analysis begins.
5. **Compile gate:** exact bound receipt must be `compile_validated` and
   `compile_success=true`. Failure is unavailable; wrong/stale evidence is stale.
6. **Freshness:** the plan binds task, effective design, PLAN, admission,
   candidate, materialization, compile receipt and behavioral-spec fingerprints.
7. **Scenario schema:** exact constructor and literal arguments, bounded setup
   calls, exact action call/arguments/console input, before/after/return
   observations, obligation IDs, capability requirements, blockers, comparison
   policy, fresh-instance isolation and ephemeral cleanup requirement.
8. **Observation vocabulary:** `direct_return`, `read_only_reflection`,
   `compile_static_evidence`, `deterministic_console_input`,
   `unsupported_observation`; existing direct surfaces additionally use
   `direct_state_access` and `existing_exact_state_query`. No execution DSL.
9. **Capability vocabulary:** `direct_public_invocation`,
   `direct_return_observation`, `existing_package_access`,
   `direct_state_observation`, `read_only_reflection`,
   `deterministic_console_input`, `unsupported_observation`,
   `execution_setup_unavailable`. Each has a closed availability status.
10. **Static mapping:** credential lifecycle and base savings transition map to
    `static_already_satisfied`; they schedule no runtime action or reflection.
11. **Authentication return:** direct boolean observation, with no reflection
    requirement on its obligation even when sharing the wrong-transfer scenario.
12. **Failed-auth state:** snapshots both fields around transfer and interest.
    Wrong-interest setup establishes nonzero savings through existing behavior.
13. **Successful transfer:** constructor initialization and the exact debit
    witness prove the chosen finite positive amount can reach successful debit.
14. **Unsuccessful debit:** exact selected debit body proves amount greater than
    ordinary balance returns false. Only the existing no-credit oracle is used.
15. **Interest:** selected exact admitted method, transfer setup, both state
    snapshots, credential channel and frozen `AdmittedInterestCalculation`.
16. **Reflection targets:** exact `BankAccount.balance: double` and
    `SavingAccount.savingBalance: double`, with path, qualified owner, exact
    definition identity, member hash and materialized source hash.
17. **Read-only rule:** `read_exact_bound_field` only. Future admission may locate
    the exact field, make that field readable, and read it; no writes, private
    method invocation, unrelated accessibility mutation or runtime enumeration.
18. **Console/PTY:** both current interest scenarios require a typed bounded
    deterministic console attachment. No such adapter exists in current code.
19. **Stdin distinction:** redirected stdin is not evidence that
    `System.console().readLine()` is usable or deterministic.
20. **Fixture values:** 1000, 200, 1001, 0.0625, optional numeric 2, and bounded
    synthetic holder/correct/incorrect strings; none become human semantics.
21. **Constructor setup:** exact existing constructor/forwarded base parameter
    assignment; unknown arithmetic/setup shapes produce
    `execution_setup_unavailable`. No constructor change or reflective write.
22. **Floating point:** finite absolute-plus-relative tolerance above, and
    binary-exact diagnostic values; no statistical testing machinery.
23. **Minimization:** wrong-transfer scenario shares two obligations. Separate
    wrong-interest is necessary because failed-auth covers each savings action.
24. **Isolation:** fresh object per scenario; only each interest setup and action
    share state. No test-order coupling.
25. **Harness:** a future ephemeral diagnostic harness is explicitly required;
    its setup-return observation capability is included in each interest route.
26. **Test files:** proposed `SavingAccountBehaviorTest.java` is never an
    executable target; test/harness source and command fields are forbidden.
27. **Readiness:** all seven frozen BANK layouts are capability incomplete;
    fully validated direct-only synthetic input can reach `execution_ready`.
    Ready denotes a complete measurement route, with execution still forbidden.
28. **Capability blockers:** reflection is `plannable_but_not_authorized`; console
    is `unavailable`. They are implementation evidence blockers, not questions.
29. **Human blockers:** only existing SPEC oracle gaps propagate. Complete BANK
    fixtures have none; mechanism limitations invent no human semantic gap.
30. **Authority:** `behavioral_execution_plan_only`; execution, Java, reflection,
    console, harness generation, test-write, write and Apply grants all false.
31. **Model/author calls:** zero; illustrative frozen author fixture text is
    normalized without any provider invocation.
32. **Javac calls:** zero; existing synthetic compile evidence is reconstructed.
33. **Java execution:** zero, as are reflection execution and console opening.
34. **Generation:** zero Java/JUnit/product behavioral test or diagnostic harness
    sources generated. Python regressions verify planning infrastructure only.
35. **Source mutation:** zero during planning/replay; virtual candidates unchanged.
36. **Traversal:** zero in planner/validator. Only named supplied buffers and
    typed inventories are parsed. Development governance checks are separate.
37. **Validator:** `validate_behavioral_evidence_execution_plan` reconstructs the
    oracle, lineage, complete coverage, targets, fixture provenance, capabilities
    and authority. It trusts neither UI/session data nor fingerprints alone.
38. **Idempotency:** same exact inputs produce equal records, ordering and SHA-256
    fingerprint. Performance timings are measured outside immutable receipts.
39. **Stale handling:** historical objects remain immutable; any changed source,
    design, PLAN, admission, candidate, materialization, compile receipt or SPEC
    needs replanning. Forged payloads cannot make historical evidence current.
40. **Compatibility:** five runtime routes plus existing static base/lifecycle.
41. **Subclass-only:** same runtime routes; base absence remains static evidence.
42. **Specialization:** interest targets exact selected `SavingAccount.saving`.
43. **Nested:** exact `bank.java` / `BankAccount::SavingAccount`, binary owner
    `BankAccount$SavingAccount`; package prefix comes from the exact source.
44. **Direct-only positive:** independently valid synthetic PLAN/candidate with
    existing exact ordinary query, public savings field and credential argument;
    full frozen gates pass with no reflection/console requirement or authority.
45. **Private negative:** exact private states require missing reflection;
    no getter or API change is proposed.
46. **Console negative:** missing deterministic console capability blocks both
    interest routes, with stdin explicitly distinguished.
47. **Authority negatives:** all grant escalation, reflection writes/arbitrary
    targets, unbound methods, oracle drift, commands, executable test paths and
    source payloads are rejected. Canonical comparison includes every nested row.
48. **Performance:** seven measured segments: SPEC reconstruction, inventory,
    observation selection, scenario minimization, capability classification,
    fingerprinting, total. Replay excludes compiler/provider/execution latency.
49. **Focused tests:** recorded in verification below.
50. **Adjacent tests:** frozen pure prerequisites and Apply/human-authority
    boundaries run without real-compiler cases; results below.
51. **Registry/benchmarks:** one CONTROL slice; 219 phases, 37 CONTROL phases,
    215 history entries; recommendation unchanged. Checks below.
52. **First remaining blocker:**
    `STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_NOT_IMPLEMENTED`.

## Verification

Focused suite: **64 passed** in 121.99 seconds, then the additional fully
validated multi-transfer regression: **1 passed, 64 deselected** in 15.89 seconds.
The focused suite has 65 cases total. The additional case proves each admitted
transfer target gets wrong-credential, successful-transfer and failed-debit
routes; its two-transfer input has eight unique scenarios and no exact operation
silently disappears. Dependency/cache warnings are
separate from test failures.

Registry/picker: **289 passed** in 10.05 seconds. Exact new bookkeeping reversal,
tamper rejection and the frozen prerequisite reversal chains passed.

Apply/human-authority and frozen attribution boundaries: **142 passed, 3 failed**
in 44.61 seconds. All three failures were reproduced with exact phase-entry
governance bytes and the original SPEC helper restored **in memory**:
**3 failed** in 10.11 seconds. No frozen receipt or source was changed to hide
them. The failures match the inherited SPEC.1 report:

* `test_patch_author_scope1.py::test_frozen_attribution_and_registry`
* `test_patch_author_span1.py::test_frozen_attribution_and_phase_registration`
* `test_human_authority_branch_checkpoint.py::test_real_registry_marks_human_close_complete_and_picker_recommends_adopt_model_1`

The two attribution receipts expect
`6b4e907c6ed14bc89dcaebe27541280b113a62babe01a8b570be6e368a666e6e`
for historically reversed `web/runner.py`; the preserved existing reversal
computes `a2d510567968b9bc11193940f0847424631b700bc095ee5628a19654e2227ee5`.
Current preserved source is
`d312e9c30fdde20c7427a6cd4abed7560d280c33490f6594e03a79c964103b8f`,
exactly the source hash already recorded in SPEC.1. The picker mismatch remains
`DOGFOOD.1B` versus the old `UX.RUN.1` expectation before and after this slice.

Frozen pure adjacent prerequisite suite: **631 passed, 15 deselected** in
1165.25 seconds, with seven upstream dependency deprecation warnings. This
includes BEHAVIOR.SPEC.1, VALIDATE.1A pure, MATERIALIZE.1,
AUTHOR.STRUCTURAL.1 and ADMIT/PLAN/APPROVE/REFRESH/RECHECK/EXPAND.
VALIDATE.1A excludes its six real-compiler test functions (15 parameterized
cases), preserving zero javac/Java execution.

Combined requested Python verification: **1127 passed, 3 inherited failures**
across the focused, adjacent, frozen-boundary and registry/picker checks.
The three failures are the independently reproduced phase-entry limitations
above. Fresh fixture directories were used without altering older denied-access
temporary directories. Detailed captured logs are
`.tmp/exec-plan1-pure-adjacent-20261005.log`,
`.tmp/exec-plan1-frozen-authority-20261005.log`, and
`.tmp/exec-plan1-frozen-entry-baseline-20261005.log`.

Benchmarks `--check`: **54 passed, 0 failed**. Full
`python -m compileall -q core scripts web tests benchmarks` and
`git -c core.safecrlf=false diff --check`: **passed**.

Five-repeat replay: **all eight layouts and 20 negative cases passed**. Seven
frozen BANK layouts are `execution_capability_incomplete`; the independently
validated direct-only input is `execution_ready`. Input objects and source
bytes remain unchanged and all repeats have identical fingerprints. Compiler
data is labeled `synthetic_provider_evidence_only`, without claiming a new
compiler measurement or successful behavioral execution.

All eight saved JSON plans were then independently reconstructed against the
final owner through the public validator under the forbidden-effect guards.
Every full canonical receipt matched, including package/nested bindings and
the direct-ready fixture, after the multiple-target coverage fix.

Compatibility plan fingerprint:
`18f1a0282be419ff433485a94ed916ab7c0d764c7bcb385e30ac1b66608ddeae`.

| Compatibility timings, five repetitions | Median ms | Max ms |
| --- | ---: | ---: |
| SPEC reconstruction | 915.5002 | 954.9450 |
| Candidate/inventory analysis | 2.6603 | 3.8276 |
| Observation-path selection | 4.4494 | 5.0995 |
| Scenario minimization | 0.0100 | 0.0122 |
| Capability classification | 4.7155 | 5.6773 |
| Plan fingerprinting | 11.2208 | 11.4630 |
| Total | 943.6393 | 980.0008 |

These are Python planning and frozen-lineage reconstruction timings, with no
compiler/provider/Java/reflection/console latency.

## Direct answers

The five scenarios in the runtime table cover the unresolved oracle. Both exact
private balances need read-only reflection for failed-auth state, successful
transfer and interest; failed-debit needs only savings reflection. Authentication
return alone is directly observable. Every reflection target is exact and
read-only. No scenario requires a product API change.

Ordinary redirected stdin cannot establish deterministic execution of the
current console-dependent interest operation. A console/PTY capability is
required and currently unavailable; only its requirement is planned. A future
ephemeral diagnostic harness is required, with separately bounded admission.
No Java/JUnit test or harness source is generated. No Java, reflection or
console executes. The execution plan grants none of those authorities.
