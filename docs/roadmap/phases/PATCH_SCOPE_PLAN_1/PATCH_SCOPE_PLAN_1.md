# PATCH.SCOPE.PLAN.1 — Read-Only Implementation Plan Within Approved Structural Ceiling

Implemented only PLAN.1, with inherited regression warnings. An explicitly
approved, reconstructed P1 can yield one validated immutable implementation
proposal. Selected targets remain a subset of the ceiling. No scope is admitted,
no Java source is written, and no candidate, patch, or Apply authority is produced.
The preserved dirty entry state and historical frozen receipts remain intact.

1. **Files changed.** Seven additions: `core/structural_implementation_plan.py`,
   `scripts/replay_patch_scope_plan1.py`, `tests/test_patch_scope_plan1.py`,
   `tests/_patch_scope_plan1_maintenance.py`,
   `tests/fixtures/patch_scope_plan1_reversal.json`, this report, and
   `docs/roadmap/PATCH_SCOPE_PLAN_1_BANK2.json`. Four shared-file modifications:
   `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`,
   `tests/test_phase_picker.py`, and `tests/_patch_scope_approve1_maintenance.py`.
   Temporary entry snapshots, logs, and baseline reproduction tools are under
   `.tmp/plan1/`. This is the phase delta against the dirty entry state.
2. **Planner owner.** The injected `ReadOnlyImplementationPlanner.plan` chooses
   one concrete proposal. `synthetic_planner_proposal` is an illustrative planner
   fixture outside core harness policy. The harness never supplies a fallback
   constructor, filename, credential representation, or debit API implementation.
3. **Harness validator owner.** `core/structural_implementation_plan.py` owns
   approval gating, context projection, normalization, typed containment,
   declaration binding, semantic checks, structural minimality, and the pure
   `validate_structural_implementation_plan` seam for a future admission consumer.
   Frozen APPROVE/REFRESH/RECHECK/EXPAND validators are called unchanged.
4. **Inputs.** Exact APPROVE.1 receipt plus independently stored typed human
   action; the currently selected P1 and REFRESH result; original semantic and
   P0 lineage; resolved transition and effective design; task contract;
   repository identity; exact acquired source/context buffers; and current actual
   scope with its expected fingerprint. Historical P0 is lineage evidence only.
5. **Schema.** Frozen, slotted `StructuralImplementationPlan`, schema
   `patch_scope_plan_1_v1`, phase `PATCH.SCOPE.PLAN.1`, status
   `validated_read_only_plan`. It binds task, effective design, P1, receipt,
   ceiling, repository, source/context and current measured/actual scope
   fingerprints. Its immutable `PlannerProposal` contains selected identities,
   logical creations, existing modifications, decisions, justified MAY choices,
   unused identities, MUST coverage, semantic effects, validation needs,
   rationale, unresolved issue and confidence telemetry. Nested records are closed
   and bounded. Canonical JSON carries an independently checked plan fingerprint.
6. **Approval gate.** Before context projection or any planner call, the frozen
   pure APPROVE.1 validator reconstructs the receipt against current inputs and
   independent action evidence. It requires `approve_exact_scope_ceiling`, literal
   `eligible_for_admission=true`, and `eligible_for_admission_only`. Frontend
   booleans, model claims, declines, revisions, and historical P0 cannot enable
   planning. The approval receipt itself is never changed.
7. **Freshness.** Task, semantic design, transition, exact P1, receipt, ceiling,
   repository, source/context and actual scope must match. Changes return
   `planning_stale` or `reacquisition_required` before the planner. Existing
   declaration mismatches return `plan_stale`. Later validation reconstructs the
   entire normalized plan and compares its full canonical payload and hash.
8. **Planner context.** A bounded 96,000-byte capsule contains explicit preserved
   semantic evidence, resolved transition, exact ceiling and identity inventory,
   relevant class contexts and exact class snippets, declaration fingerprints,
   deferred choices, repository/scope/source bindings, closed nested output
   schemas and vocabulary. Unrelated acquired classes are filtered from planner
   projection. The boundary explicitly says design planning only, no code/patch,
   no permission claim, no extra infrastructure, and no path authority.
9. **Model-call policy.** `plan_structural_implementation` allows one injected
   planner call only after fresh approval validation and explicit prior call
   authorization. There is no retry, resampling, reviewer swarm or author
   fallback. Missing providers and provider exceptions return typed failures
   with no plan. Provider diagnostics and rejected output are not retained.
10. **Target identity.** `PlanTargetIdentity` binds target, owner, name, kind,
    category, parent, file, evidence references, declaration fingerprint/span,
    and a fingerprint of the entire approved target. Set membership uses exact
    typed equality. Prefixes and fuzzy member matches have no authority.
11. **Logical-to-physical mapping.** Each selected logical identity maps through
    `PlannedTarget` to one explicit proposed physical path, layout and definition
    list. All pieces of one logical class agree on location and new-file intent.
    Mappings preserve approved inheritance and ownership. Later admission still
    needs independent repository/path policy validation.
12. **MUST coverage.** Every `MUST_SUPPORT` capability has an exact coverage entry
    referencing one or several planned definition IDs, or a source-bound existing
    sufficient mechanism. Every required logical creation and MUST existing edit
    is selected. Coverage checks definition kind, owner, named state, and bounded
    contracts for construction, verification, debit, credit and interest. Each
    replay fixture accounts for all nine MUST capabilities.
13. **MAY selection.** Selected MAY identities require explicit reasons and
    concrete mappings. In the measured void-withdrawal fixture, an internal
    observable debit is justified because withdrawal cannot establish successful
    debit for the savings credit. Subclass-only savings also selects the approved
    existing-saving transition target. Selection remains a proposal.
14. **Unused MAY targets.** Unselected ceiling identities are exhaustive and
    disjoint from selected identities, with status
    `ceiling_available_but_unused`. A synthetic P1 with a private base constructor
    permits a constructor-access MAY change. A planner instead proposes a static
    nested subclass in the exact parent source, leaving that MAY identity unused.
    The later consumer cannot infer an edit from its ceiling availability.
15. **Implementation decisions.** Typed decisions identify layout, constructor,
    state, credential, debit, funding, interest and existing-saving transition.
    Decisions reference exact approved identities. Definition IDs are local
    reference labels supplied by the planner; the model need not calculate hashes
    for its proposed definitions. Confidence and prose confer no authority.
16. **Source-layout proposal.** Ordinary fixtures propose a top-level
    `SavingAccount.java`; the unused-MAY fixture proposes a static nested
    `SavingAccount` in `bank.java`. Another valid test uses a package-visible class
    in `education/Savings.java`. Public top-level class filenames are checked
    against the actual proposed class name, without hard-coding SavingAccount as
    the only layout. No proposed file is created.
17. **Constructor plan.** The illustrative planner proposes parameters matching
    the exact base constructor plus an in-memory credential, compatible super
    construction, and initial savings state. Measured-shaped tests propose
    `(String accountHolder, double balance, String password)`; the smaller frozen
    replay source uses `(double opening, String password)`. Parameter order can
    vary. Private base construction requires a proposed access change or the
    compatible nested layout. No one signature is required by harness policy.
18. **Credential plan.** Fixtures choose a private String password owned by
    SavingAccount and a private equality-check helper, used before each requested
    savings operation. Typed commitments preserve simple password semantics,
    in-memory storage, semantic password checking and operation-gated verification.
    This is the educational fixture's representation. Persistence and new
    authentication infrastructure are rejected.
19. **Savings funding plan.** Verification precedes the funding operation. The
    proposed savings credit occurs only after an observable successful inherited
    debit. Both the overall guard and the funding definition's typed contract are
    checked. Unconditional savings credit, unproven void withdrawal, or missing
    debit/funding coverage fails validation.
20. **Base debit plan.** The fixture chooses a protected boolean helper while
    preserving private base balance. It can use another helper name or bounded
    signature; the harness requires its observable atomic successful-debit
    contract. Existing debit mechanisms must pass the frozen source proof.
    A new public base debit API is flagged `plan_scope_nonminimal` because a
    narrower internal mechanism suffices.
21. **Existing saving transition plan.** Subclass-only fixtures propose retirement
    of the current base savings behavior through a source-bound removal mapping.
    Compatibility fixtures leave base saving unchanged and implement separate
    subclass savings state. Specialization fixtures preserve base saving and
    propose a compatible subclass operation for the common savings contract.
    Exact parameter types come from source. No `@Override` syntax is mandated.
22. **Semantic drift detection.** The closed proposal must preserve the effective
    semantic commitments exactly, use permitted in-memory infrastructure, and
    introduce no new policy or semantic role. Typed funding, encapsulation,
    credential, interest and transition contracts are checked. Code-bearing
    strings and material policy indicators in explanatory prose are quarantined.
    Database, file persistence, lockout, public balance and altered commitments
    have focused negative tests. Prose cannot justify new semantics into existence.
23. **New clarification detection.** A genuinely material unresolved issue returns
    `semantic_clarification_required`, no plan, and no retry. The caller can later
    route this typed status through the existing clarification lifecycle. No new
    clarification UI/session or human semantic answer is created in PLAN.1.
    Helper naming, internal decomposition, parameter order and other equivalent
    code shape remain planner-owned.
24. **Ceiling containment.** Exact selected identities are subset/equal-to the
    reconstructed ceiling; selected and unused identities partition it. Every
    proposed edit maps to exactly one approved logical/existing identity. Existing
    modifications retain exact file, class and declaration bindings. Unapproved
    third classes, referenced types, altered logical ownership, unsafe paths or
    mismatched declarations cannot enter a valid plan.
25. **Structural minimality.** Separate from textual PATCH.MINIMAL, a bounded
    structural deletion/witness check requires every selected target and planned
    definition to serve required capability coverage. It rejects duplicates,
    unnecessary edits to preserved base savings, debit edits when an existing
    source mechanism suffices, unnecessary constructor access with a nested
    layout, and avoidable public base API exposure. It validates the supplied
    concrete dependency mapping without asserting that the fixture is the only
    valid design or globally optimizing arbitrary implementation alternatives.
26. **Validation strategy.** Typed needs include later javac and focused behavior
    evidence for failed verification, failed debit, transfer conservation,
    subclass state interest and the chosen base transition. A proposed test file
    is recorded as `validation_evidence_need`, with test-write authority false.
    These descriptions are not executable commands. PLAN.1 does not execute the
    proposed Java validation strategy.
27. **Code/patch output handling.** Unknown transport fields are rejected. Patch,
    candidate, code, source or command payloads and code-bearing strings yield
    `plan_output_contains_patch`. The operation quarantines the output by returning
    no plan and retaining no rejected source body. Nothing is sent to Apply.
28. **New-file authority.** Proposed paths and `proposed_new_file` are explicit.
    The latter must agree with the supplied acquired source inventory. Every
    mapping and plan carries `file_creation_authority=false`; proposed test files
    also retain `test_write_authority=false`.
29. **RepairScope delta.** Zero. No writable scope is introduced or admitted.
30. **AuthoringRepairScope delta.** Zero. Existing scope fingerprints are bound,
    while the supplied scope remains untouched.
31. **Candidate.** Null; patch empty, on both successful and failed operations.
32. **Write/Apply authority.** `authority=read_only_plan`; write, execution, Apply,
    file creation and repair-scope authority are false. A plan is never rendered
    into an authoring or filesystem write envelope.
33. **Author calls.** Zero. The module does not call patch authors, build author
    prompts, or use the patch-author provider functions.
34. **Model calls measured.** Zero live calls in governance replay. Synthetic
    planner protocol tests exercise one injected call, invalid output, provider
    failure, unavailable provider, lack of authorization and new clarification.
    Ineligible/stale operations call it zero times; no operation calls twice.
35. **Traversal.** Zero repository traversals during planning and validation.
    Acquired buffers are supplied by the caller. Replay/tests guard file I/O,
    traversal, network, subprocess and author functions against use by the core.
36. **Source integrity.** Real `Side quest/java/bank.java` remains byte-identical:
    SHA-256 `da3880d225c207079765e06f84358ba979b41c97e695a31a2f2618eaf7fa027d`.
    Real MainApp remains byte-identical, and `web/sessions.json` is unchanged at
    SHA-256 `de982b5914f8c75f1a2a1e8468bfcd36e3768bd97fd5b7682724a96f1a04fa25`.
    SavingAccount.java is absent from the real Java repository and workspace root.
    All 18 protected entry artifacts, including frozen BANK.2 receipts and core
    validators, retain their entry hashes. No real BANK.2 approval is consumed.
37. **Subclass-only fixture.** Seven selected of seven ceiling targets. All nine
    MUST capabilities are covered. The base saving declaration is explicitly
    retired, the necessary debit MAY target is justified, and no persistence is
    introduced. Reusing current base savings as intended behavior is rejected.
38. **Compatibility fixture.** Six selected of seven ceiling targets. Current
    BankAccount.saving is an existing sufficient mechanism and remains unused as
    an edit target. Removal or a changed transition is rejected. All nine MUST
    capabilities remain covered.
39. **Specialization fixture.** Six selected of seven ceiling targets. Base saving
    remains; a source-compatible subclass savings definition specializes the
    common contract. Missing common contract, incompatible specialization or
    removal is rejected. A final/private base declaration requires a justified
    approved specialization mechanism.
40. **Too-broad negative.** Forged public balance, database, user repository,
    unrelated class and prefix-matching identities outside the ceiling yield
    `plan_outside_approved_ceiling`. Unsafe paths and unapproved referenced types
    also fail containment. Infrastructure invention inside otherwise valid
    identities is separately `plan_semantic_drift`.
41. **Missing-MUST negative.** Omitting authentication, savings funding or debit
    coverage, missing a required logical creation, or substituting an unproven
    void withdrawal yields `plan_incomplete`.
42. **Semantic-drift negative.** Three attempts then lockout, persistence,
    unconditional savings credit, exposed balance, changed semantic commitments,
    unknown semantic roles and contradictory transition effects fail closed.
43. **Stale-approval negative.** Source, context, task, design, repository, scope
    and P1 changes prevent planner invocation. Declaration fingerprints and later
    forged plan/authority bindings are rejected. Existing receipts are preserved.
44. **Wrong-receipt negative.** A receipt for another transition, historical P0,
    missing independent human evidence and a frontend approved boolean cannot
    enable planning. Decline/revision receipts produce `planning_unavailable`.
45. **Performance.** Five synthetic repetitions per scenario measure approval
    validation, context projection, normalization, containment, semantic checks,
    structural minimality and total deterministic overhead separately. Provider
    latency is zero/not applicable in replay; an injected latency test confirms
    that it is measured separately and subtracted from deterministic overhead.
    Timing does not participate in plan identity. The table below records the
    replay's median/maximum milliseconds.
46. **Focused tests.** 83 PLAN.1 tests pass, including three transitions, unused
    MAY, alternate legal code shapes/layouts, exact identity and declaration
    binding, output bounds, semantic drift, source compatibility, safe validation
    needs, provider call budget, no effects and pure future-admission validation.
47. **Adjacent tests.** APPROVE/REFRESH/RECHECK/EXPAND and OOP DESIGN/DETECT/
    CONTINUE/UI: 354 passed. Authoring scope/basis/span and human authority:
    142 passed, three inherited failures. PATCH.MINIMAL/benchmark minimality/history:
    278 passed, nine inherited failures. Read-only substitution of all four shared
    entry snapshots reproduces all twelve failures. Six concern inconclusive
    sandbox verification; five concern prior frozen byte attribution in
    web/runner.py, core/control_engine.py or core/pipeline.py; one is the historical
    UX.RUN.1 versus DOGFOOD.1B picker expectation. Those modules are untouched.
    Logs and entry reproduction evidence are under `.tmp/plan1/`. No historical
    receipt is repinned to conceal a failure.
48. **Registry/benchmarks.** One narrow PATCH/PLAN slice is registered in the
    existing CONTROL track: 213 phases, 31 CONTROL, 209 history entries. Registry
    and picker tests pass (277 tests); the model-capable phase enumeration includes
    PLAN.1's already-authorized planning seam. All four bookkeeping changes
    reconstruct their dirty entry bytes exactly through the new phase-specific
    reversal. Benchmarks check 54 cases with zero errors; compileall and git diff
    --check pass.
49. **First remaining blocker.** `SCOPE_ADMISSION_NOT_IMPLEMENTED`. The normalized
    plan and pure validator are available for a later deterministic ADMIT.1, which
    must reacquire evidence, validate repository/path policy and admit only the
    selected justified subset. ADMIT.1 is not implemented here.

| Explicit question | Answer |
| --- | --- |
| Does planning use only an explicitly approved P1 ceiling? | Yes; frozen receipt reconstruction gates every operation. |
| Can the planner choose a concrete implementation without gaining write authority? | Yes; all authority stays read-only. |
| Are selected targets a strict subset/equal-to the approved ceiling? | Yes; 7/7, 6/7, 6/7 and 6/8 in the four fixtures. |
| Can approved MAY targets remain unused? | Yes; the private-constructor access MAY remains unused in the nested-layout fixture. |
| Are all MUST capabilities accounted for? | Yes; nine in every valid fixture. |
| Can logical SavingAccount map to a proposed physical file without creating it? | Yes; the mapping has file-creation authority false. |
| Does the harness reject database/auth infrastructure invention? | Yes; typed infrastructure, referenced-type, containment and narrative checks fail closed. |
| Does it reject new semantic policy not supplied by the human? | Yes; unbound policies/effects/roles and material narrative drift are quarantined. |
| Does it preserve the chosen BankAccount.saving transition? | Yes; all three transitions have positive and negative coverage. |
| Does it produce any candidate or patch? | No; candidate null, patch empty. |
| Does it widen RepairScope or AuthoringRepairScope? | No; both deltas zero. |
| Does it grant write/Apply authority? | No. |
| Is the normalized plan suitable for later deterministic ADMIT.1? | Yes; exact bindings, selected subset, immutable mappings and pure revalidation are available. Admission remains unimplemented. |

Replay command: `python scripts/replay_patch_scope_plan1.py --repetitions 5
--output docs/roadmap/PATCH_SCOPE_PLAN_1_BANK2.json`. The artifact includes four
positive scenarios, ten typed negative outcomes and separate performance stages.

Median / maximum milliseconds, five synthetic repetitions per scenario:

| Stage | Subclass only | Compatibility | Specialization | Unused MAY / nested |
| --- | ---: | ---: | ---: | ---: |
| Approval validation | 547.491 / 570.670 | 535.348 / 563.473 | 554.366 / 575.948 | 538.200 / 597.533 |
| Context projection | 8.226 / 9.366 | 8.232 / 8.485 | 8.390 / 11.007 | 8.469 / 8.780 |
| Planner call latency | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 |
| Normalization | 15.577 / 16.464 | 13.849 / 15.501 | 14.063 / 15.696 | 15.207 / 15.717 |
| Ceiling containment | 5.204 / 6.476 | 5.404 / 6.231 | 4.979 / 5.633 | 5.442 / 6.735 |
| Semantic validation | 2.489 / 3.084 | 2.816 / 3.322 | 2.300 / 2.621 | 2.263 / 3.489 |
| Structural minimality | 2.130 / 3.031 | 2.181 / 3.204 | 2.724 / 4.207 | 2.281 / 2.726 |
| Total deterministic overhead | 581.007 / 606.186 | 565.857 / 600.460 | 589.828 / 609.292 | 575.143 / 631.196 |
