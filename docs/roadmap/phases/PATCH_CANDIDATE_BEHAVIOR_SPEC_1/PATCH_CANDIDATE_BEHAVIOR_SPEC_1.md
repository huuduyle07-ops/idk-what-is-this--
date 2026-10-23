# PATCH.CANDIDATE.BEHAVIOR.SPEC.1

The compile-valid virtual candidate now has one immutable behavioral oracle
derived from its validated typed semantic lineage and implementation contract.
This phase defines the required evidence. It does not supply that evidence or
authorize its execution. The BANK fixture still has private-state observation
gaps and a console-dependent interest operation.

## Phase delta

| Change | Exact path |
| --- | --- |
| New | `core/behavioral_validation_specification.py` |
| New | `tests/test_patch_candidate_behavior_spec1.py` |
| New | `scripts/replay_patch_candidate_behavior_spec1.py` |
| New | `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_SPEC_1.md` |
| New | `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_SPEC_1_SYNTHETIC.json` |
| New | `tests/_patch_candidate_behavior_spec1_maintenance.py` |
| New | `tests/fixtures/patch_candidate_behavior_spec1_reversal.json` |
| Modified | `docs/roadmap/phase_registry.json` |
| Modified | `tests/test_phase_registry.py` |
| Modified | `tests/test_phase_picker.py` |
| Modified | `tests/_patch_candidate_validate1a_maintenance.py` |

These paths are the phase delta over the existing dirty workspace. The newest
bookkeeping reversal removes only the added registry phase, count changes,
narrow governance assertions and its two-line maintenance-chain hook. All
historical receipt files remain unchanged and retain their original hashes.

## Required evidence after compile success

| Semantic obligation | Expected evidence | Current BANK evidence mode |
| --- | --- | --- |
| `authentication_gate` | Incorrect credential produces failed transfer return | `runtime_required` |
| `failed_auth_no_state_change` | Failed verification leaves ordinary and savings balances unchanged | `unresolved_observability` |
| `successful_transfer_conservation` | Authenticated successful debit of A reduces ordinary balance by A and increases savings balance by A | `unresolved_observability` |
| `unsuccessful_debit_no_credit` | Failed inherited debit cannot increase savings balance | `unresolved_observability` |
| `savings_interest_target` | The admitted simple-rate operation uses savings principal and does not use ordinary balance as principal | `unresolved_observability` |
| `credential_lifecycle` | The scoped admitted operation needs no persistent credential dependency | `static_satisfied` |
| `base_savings_transition` | The selected base/subclass savings contract remains available in the chosen domain model | `static_satisfied` for the frozen fixtures |

`unresolved_observability` means runtime evidence is still necessary but its
exact measurement path is absent. Its obligation status is
`observation_evidence_missing`. Boolean transfer return is a useful observation
of success or failure; it cannot prove conservation or unchanged private state.
The specification carries a typed coverage map linking semantic dimensions to
obligation identifiers, evidence modes and statuses.

| Existing typed semantic dimension | Obligation family mapping |
| --- | --- |
| Successful-verification gate; `verification_lifecycle` | Authentication return and failed-auth state |
| `savings_funding_semantics` | Successful conservation and unsuccessful-debit no-credit |
| `savings_credit_guard` | Unsuccessful-debit no-credit |
| `savings_interest_semantics`; `candidate_interest_calculation` | Savings-interest target |
| `credential_ownership`; `credential_persistence` | Bounded static credential lifecycle |
| Optional typed `credential_source`, `credential_verification_mechanism`, `exercise_hashing_constraint` | Bounded static credential lifecycle |
| `existing_savings_transition` | Selected base availability; specialization also maps to savings-interest target |

Each mapping carries the aggregated evidence mode/status of its obligations;
the exact immutable rows and fingerprint are in the synthetic JSON. Optional
credential facts are projected only when the validated typed lineage carries
them, including the existing hashing-out-of-scope commitment.

Private `BankAccount.balance` and `SavingAccount.savingBalance` lack an existing
exact state query in the frozen candidate. Display/output and success booleans
do not establish exact before/after balances. The oracle records a future
reflection requirement, without selecting or authorizing that access mechanism.
No getter, visibility change or product API is added.
A later separately authorized reflection harness could inspect private state
without widening the product API; no such harness or authority exists here.

The bound interest operation uses `System.console().readLine()`. A deterministic
automated execution environment may not supply a console. This is an
`execution_harness_constraint` with console-input capability, separately bound
to the exact target definition. It is not a compile or semantic defect and
grants no revision authority.

## Implementation and evidence contract

1. **Files changed.** Seven new phase-owned paths and four bookkeeping paths
   appear in the table above. Existing source, candidate, materialization,
   semantic-chain, Apply, UI/session and historical receipts are preserved.
2. **Specification owner.** `core/behavioral_validation_specification.py` owns
   `project_behavioral_validation_specification(compile_receipt, *, materialized,
   candidate, admitted_scope, timings=None, **fresh_inputs)` and pure consumer
   `validate_behavioral_validation_specification(...)`. It accepts only bound
   typed lineage and evidence; it has no repository-root execution facade.
3. **Schema.** `patch_candidate_behavior_spec_1_v1` contains frozen, slotted,
   recursively immutable specification, obligation, coverage, provenance,
   target-definition, observation-capability, evidence-requirement, observation
   gap, human-oracle-gap and harness-constraint records. The canonical SHA-256
   fingerprint excludes timing. Closed bounded fields contain no executable
   source, assertion code, command or execution configuration.
4. **Compile receipt gate.** The frozen pure compile-receipt validator
   reconstructs canonical receipt evidence first. Both `compile_validated` and
   `compile_success=true` are required. A valid failed-compile receipt yields
   `behavior_spec_unavailable_due_compile_failure` with no obligations.
5. **Freshness and lineage.** Compile receipt, materialization, candidate,
   admission, PLAN and semantic design are reconstructed together using supplied
   current bound evidence. Task/design/PLAN/admission/candidate/materialization/
   compile fingerprints and the selected base transition bind the result.
   Mismatched canonical lineage yields `behavior_spec_stale` before projection.
6. **Obligation vocabulary.** Only the seven families in the evidence table are
   supported. Preconditions, actions, observations and observation capabilities
   likewise come from closed vocabularies. This is a bounded BANK.2 oracle.
7. **Semantic provenance.** Typed effective-design commitments supply credential
   ownership, in-memory persistence, operation-gated verification, funding from
   inherited ordinary balance, savings interest principal and the selected base
   savings transition. Their evidence references remain attached as
   `explicit_human`; raw task prose is not reparsed into new assertions.
8. **Implementation-contract provenance.** Successful debit before savings
   credit, boolean transfer shape and the admitted simple-interest calculation
   derive from the validated PLAN/candidate contract. Formula details retain
   `implementation_contract` provenance and are not elevated into permanent
   human domain intent.
9. **Authentication obligations.** Incorrect credentials must fail transfer;
   failed verification cannot perform protected savings transitions. No retry,
   lockout, error-message or exception policy is invented.
10. **Transfer-conservation obligations.** Successful authenticated transfer of A
    must debit ordinary balance by A and credit savings balance by A. No fees or
    minimum-balance policy is asserted.
11. **Failed-debit obligations.** Savings credit requires a successful inherited
    debit. Failed debit cannot increase savings balance. The oracle does not
    choose a new reason or policy for debit failure.
12. **Interest obligations.** Distinct ordinary and savings principals must show
    that the admitted simple-rate operation affects savings balance and does not
    use ordinary balance as principal. Frequency/calendar policy is absent.
13. **Credential-lifecycle evidence.** Existing structural evidence supports the
    bounded in-memory credential commitment and absence of a persistent
    dependency inside the admitted candidate. This is static evidence, without
    claiming repository-wide absence of persistence infrastructure.
14. **Base-transition obligations.** Compatibility preserves semantically
    available base savings behavior. Subclass-only savings does not depend on a
    retired base savings operation. Specialization preserves the base concept
    while subclass interest acts on savings state. No behavioral assertion
    demands exact deletion, identical internals or a Java annotation.
15. **Static-satisfied obligations.** The bounded credential-lifecycle commitment
    and measured selected base availability are covered by existing structural
    evidence. Inheritance, definition containment, field ownership and compile
    correctness are not expanded into redundant runtime obligations.
16. **Runtime-required obligations.** Authentication return evidence remains
    pending. Exact failed-auth state, conservation, failed-debit no-credit and
    interest-target evidence remain pending with explicit observation gaps.
17. **Unresolved observability.** Known meaning with absent measurement is an
    implementation-owned evidence problem, classified
    `observation_evidence_missing`. It is input to later execution planning.
18. **SavingBalance observability.** The private field has no existing exact
    public/package-visible query in the frozen BANK fixture. Reflection is a
    conceptual required capability; its availability remains false.
19. **BankAccount.balance observability.** The private inherited ordinary state
    also lacks exact observable access. Its gap is independently attached to
    every affected obligation.
20. **Boolean-return observability.** The admitted public boolean transfer method
    exposes success/failure. It supplies the authentication return observation,
    without satisfying exact state-change obligations.
21. **System.console constraint.** The bound console use is recorded separately
    as a deterministic execution harness constraint. The method is unchanged.
22. **Human-owned oracle gaps.** Creating a materially different desired behavior
    without typed semantics would produce `behavioral_semantic_gap` and bind the
    missing decision. Complete frozen BANK fixtures need no new human decision.
23. **Implementation-owned evidence gaps.** Private state access and console
    plumbing require future evidence planning; they trigger neither an automatic
    semantic question nor permission to add a getter.
24. **Minimal oracle set.** Projection emits independent material behavior
    obligations in deterministic order. Authentication return and unchanged
    private state are separate facts; conservation and debit failure are separate
    scenarios. The implementation does not hard-code an expected obligation
    count in its replay or build a test-like obligation per code line.
25. **Semantic coverage map.** The specification and synthetic JSON retain typed
    dimension → obligation(s) → evidence mode → current status mappings. This is
    semantic coverage, without a test coverage percentage.
26. **Test-file handling.** `SavingAccountBehaviorTest.java` remains only the
    PLAN's proposed path in `proposed_test_files`. It is never created or filled.
27. **Source and test generation.** Neither production projection nor replay
    generates Java/JUnit/Python behavioral test implementations. The Python
    regression suite checks this specification infrastructure only. Source
    mutation and behavioral test generation are zero.
28. **Commands and execution.** The declarative schema rejects commands and
    executable payloads. This phase invokes neither javac nor Java/JUnit. Python
    implementation/regression checks run as development verification; the
    candidate's Java behavior does not execute.
29. **Authority.** `authority=behavioral_oracle_only`;
    `test_write_authority=false`, `execution_authorized=false`,
    `write_authority=false`, `apply_authority=false`. Existing task/session/UI
    claims cannot increase those immutable grants.
30. **Model and author calls.** Both are zero. Projection is deterministic over
    typed evidence. Replay reuses frozen illustrative fixture construction and
    the pure synthetic compile-result normalizer.
31. **Traversal.** Repository traversal is zero. Observation analysis inspects
    only supplied source buffers/materialization and existing typed structures.
32. **Idempotency.** Repeated unchanged lineage produces equal obligations,
    ordering, coverage and specification fingerprint. Canonical consumer
    reconstruction rejects altered or extra fields.
33. **Performance.** Timings measure compile-receipt reconstruction, semantic
    coverage projection, observability analysis, obligation normalization,
    fingerprint construction and total. Per-scenario median/max milliseconds
    are in the synthetic replay JSON; no provider/execution latency is included.
34. **Compatibility fixture.** Failed credential, state non-change,
    transfer-conservation, failed-debit no-credit and savings-interest principal
    are covered alongside static base compatibility and lifecycle evidence.
35. **Subclass-only fixture.** The selected oracle requires subclass savings
    availability without dependence on the retired base operation. Static
    absence evidence is reused without turning deletion into desired behavior.
36. **Specialization fixture.** Base savings remains semantically available;
    subclass state behavior is covered by the same savings-interest obligation.
37. **Nested fixture.** Identical semantics produce the same behavioral families
    and observations. Physical nesting changes target identity, without
    inventing a behavior requirement.
38. **Negative cases.** Focused regression checks and replay reject stale compile
    receipts, wrong transitions, forged observations/coverage, executable source,
    commands and authority grants. A valid compile failure produces no oracle.
    Private state never becomes executable conservation evidence merely because
    a boolean operation is observable.
39. **Focused tests.** 77 cases pass against the final stable owner. All cases
    operate on synthetic typed lineage, with zero compiler/Java/provider calls.
40. **Adjacent tests.** Frozen prerequisite, Apply and human-authority boundary
    regressions are run without behavioral Java execution. The nine frozen
    prerequisite suites have 554 passing cases. VALIDATE.1A's six real-compiler
    test functions, covering 15 parameterized cases, are excluded for this phase;
    its pure tests still run.
41. **Registry and benchmarks.** One complete CONTROL slice is appended: 218
    phases, 36 CONTROL phases, 214 complete/history picker entries. Registry and
    picker preserve the existing top recommendation. Historical receipts are
    never repinned; exact new reversal checks preserve them. Compileall,
    benchmark `--check` and diff whitespace validation pass.
42. **First remaining blocker.**
    `STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_PLANNING_NOT_IMPLEMENTED`.

## Verification

Nine frozen prerequisite suites: **554 passed, 15 deselected** in 970.97 seconds.
The deselected cases are the six real-compiler VALIDATE.1A test functions with
their parameterizations. No javac or Java process ran. Seven upstream dependency
deprecation warnings are separate from the three actual inherited failures
below.

Final focused SPEC.1 suite: **77 passed** in 145.14 seconds, with one upstream
`google-genai` deprecation warning. The latest
console-link/access/formula/coverage/nesting subset has
**13 passed, 64 deselected** in 65.46 seconds, with the same upstream dependency
deprecation warning. These warnings are separate from the inherited failures.

Registry/picker: **287 passed**. Their tests used a fresh external fixture
directory because the existing workspace `tmp_tests` directory has denied
Windows access. No historical fixture directory was cleaned to resolve that
environment constraint.

Frozen boundaries and registry: **429 passed, 3 failed** from inherited checks.
The two frozen-attribution checks in `test_patch_author_scope1.py` and
`test_patch_author_span1.py` expect an older `web/runner.py` hash; that source
already differed at phase entry and is unchanged by SPEC.1. The registry
checkpoint in `test_human_authority_branch_checkpoint.py` expects `UX.RUN.1`
while the pre-existing picker recommends `DOGFOOD.1B`. The same limitations were
documented in VALIDATE.1A; this slice neither edits the frozen source nor repins
its expected receipt to hide them.

All three were reproduced with SPEC.1 bookkeeping reversed in memory to exact
phase-entry state: **3 failed in 8.91 seconds**, with the same failures. The
failing checks are
`test_patch_author_scope1.py::test_frozen_attribution_and_registry`,
`test_patch_author_span1.py::test_frozen_attribution_and_phase_registration` and
`test_human_authority_branch_checkpoint.py::test_real_registry_marks_human_close_complete_and_picker_recommends_adopt_model_1`.
The two attribution receipts expect
`6b4e907c6ed14bc89dcaebe27541280b113a62babe01a8b570be6e368a666e6e`
for `web/runner.py`; their existing prerequisite reversal computes
`a2d510567968b9bc11193940f0847424631b700bc095ee5628a19654e2227ee5`.
The preserved current source bytes themselves hash to
`d312e9c30fdde20c7427a6cd4abed7560d280c33490f6594e03a79c964103b8f`.
The picker mismatch remains `DOGFOOD.1B` versus its old `UX.RUN.1` expectation
both before and after this slice.

Benchmarks `--check`: **54 passed, 0 failed**.
Final compileall and `git -c core.safecrlf=false diff --check`: **passed**.

Final replay: **all seven frozen layouts and nine negative cases passed**, with
five repetitions per layout and deterministic oracle fingerprints. Every saved
JSON oracle was then independently reconstructed against the final owner under
the same no-effect guards; all seven matched. The compatibility oracle
fingerprint is
`03cadf9c1c7cb5708796b54abbeea166fd4a31edd62e20e8a2f0c54929375371`.

| Compatibility timing, five repetitions | Median ms | Max ms |
| --- | ---: | ---: |
| Compile receipt reconstruction | 790.8174 | 1009.1224 |
| Semantic coverage projection | 0.7217 | 1.3040 |
| Observability analysis | 5.9616 | 10.6778 |
| Obligation normalization | 15.0076 | 24.6172 |
| Fingerprint construction | 4.1317 | 5.4604 |
| Total | 823.6689 | 1040.4449 |

These timings measure projection and frozen-lineage reconstruction on this
machine, with no compiler/provider/execution latency.

The synthetic replay JSON labels compiler data as
`synthetic_provider_evidence_only`: replay validates bindings but makes no claim
to have measured a new compiler run or behavioral success. Its actual compiler,
Java, behavioral-test-generation, model, author and traversal counts are zero.

## Direct answers

After javac success, failed-auth state, authenticated transfer conservation,
failed-debit no-credit and correct savings interest principal still require
behavioral evidence, as does observable authentication return. Scoped credential
lifecycle and selected base-contract availability already have static evidence.

Existing boolean return can be observed without widening the product API.
Exact ordinary/savings balance relations cannot currently be observed from the
frozen public/package-visible BANK surface. Both private balances create a
measurement gap; interest additionally requires console-capable future plumbing.
A separately authorized reflection approach could resolve state access without
adding a product getter, but remains future execution-planning work.

The harness invents no retry, lockout, fee, minimum-balance, calendar, exception
or other desired policy. No behavioral test is generated. No Java candidate is
executed. The specification grants no test-write, execution, write or Apply
authority.
