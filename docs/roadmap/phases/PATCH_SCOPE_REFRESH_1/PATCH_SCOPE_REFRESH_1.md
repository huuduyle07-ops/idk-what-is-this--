# PATCH.SCOPE.REFRESH.1 — Semantically Revised Structural Scope Re-Proposal

This phase reconstructs the historical EXPAND.1 proposal against its original
effective design, validates one resolved scope-transition answer and the
RECHECK.1 no-gap receipt, then produces a new immutable proposal from the same
source bytes. The old proposal is retained as evidence. A refreshed proposal
does not expand `RepairScope` or `AuthoringRepairScope` and is not an approval.

1. **Files changed.** Updated `core/structural_scope_expansion.py` with a
   refresh-only internal adapter while preserving the frozen public EXPAND.1
   entry point. Added `core/structural_scope_refresh.py`,
   `tests/test_patch_scope_refresh1.py`,
   `scripts/replay_patch_scope_refresh1.py`,
   `docs/roadmap/PATCH_SCOPE_REFRESH_1.md` and its synthetic BANK.2 JSON
   artifact. Registered one CONTROL phase and added registry/picker assertions
   plus a test-only bookkeeping reversal. No web, Java source, authoring scope,
   candidate, or patch-execution files were changed.
2. **Refresh owner.** `core.structural_scope_refresh.refresh_structural_scope_proposal`
   owns validation and re-proposal. `core.scope_semantic_recheck.recheck_refreshed_scope_semantics`
   reconstructs P1 and checks the post-refresh semantic fixpoint.
3. **Inputs.** Typed `TaskContract`, original `ProposedDesignIntent`, original
   CONTINUE.1 continuation and stored evidence, validated original DETECT.2
   no-gap receipt, historical P0, transition continuation and stored answer,
   scope-transition effective design, RECHECK.1 no-gap receipt, exact acquired
   context and source bytes, repository identity, and current scope plus its
   independently retained fingerprint.
4. **P0 validation.** The original design and CONTINUE.1 chain are reconstructed;
   the original DETECT.2 receipt is regenerated; and EXPAND.1 is rebuilt and
   compared as a complete canonical proposal. Forged, stale, or rebound P0
   cannot be a refresh parent.
5. **Revised-design validation.** The transition continuation is regenerated
   from its bound gap and human answer. Its P0, original design, CONTINUE.1,
   task, repository, source and declaration bindings are checked. The supplied
   transition-effective design must exactly equal the composition of those
   validated inputs.
6. **RECHECK gate.** P1 requires an exactly reconstructed RECHECK.1 receipt
   with `status=no_gap` and `scope_refresh_required=true`. Partial, unknown,
   conflicting or otherwise unresolved transitions produce no P1.
7. **Schema.** P1 is an immutable `RefreshedStructuralScopeExpansionProposal`,
   a subtype of `StructuralScopeExpansionProposal`, using
   `patch_scope_refresh_1_v1`. The frozen EXPAND.1 schema and external entry
   point remain unchanged.
8. **Parentage.** P1 records P0's fingerprint, the transition continuation
   fingerprint, E1's fingerprint, `refresh_reason=semantic_transition_resolved`,
   the same repository identity and exact source/context bindings.
9. **Savings-only proposal.** P1 makes `BankAccount::saving` a
   `MAY_REQUIRE_EXISTING_API_CHANGE` transition target and gives the capability
   `MUST_SUPPORT` certainty: the behavior must leave the intended base API.
   Removal, deprecation and compatibility migration remain possible mechanisms;
   none is selected here.
10. **Compatibility proposal.** P1 records `BankAccount.saving` as
    `MUST_SUPPORT`, with the target deferred only for implementation detail.
    It explicitly preserves the legacy behavior and proposes no retirement.
11. **Specialization proposal.** P1 keeps a required common savings contract
    with a deferred implementation target and a distinct specialization reason.
    It does not select `@Override`, an abstract method, visibility or an exact
    signature. A possible API transition is added only when exact source proves
    the current method is `private` or `final`.
12. **P0→P1 diff.** The deterministic semantic diff includes targets added and
    removed, target classification and reason changes, capability certainty
    changes, resolved and retained deferred decisions, proposal reason changes,
    and blast-radius changes. In the three BANK.2 cases, P1 resolves the old
    `existing_savings_transition` decision and changes its certainty from
    `NEEDS_TRANSITION_DECISION` to `MUST_SUPPORT`.
13. **BankAccount.saving classification.** Subclass-only: possible base API
    transition, reason `base_savings_behavior_must_leave_intended_api`.
    Compatibility: deferred implementation detail, reason
    `legacy_base_savings_behavior_is_semantically_preserved`. Specialization:
    deferred implementation detail, reason
    `base_savings_contract_supports_subclass_specialization`.
14. **Base debit.** `balance` remains private. Under EXPAND.1's deterministic
    method proof, the measured conditional `void withdraw` does not establish
    successful transfer, so P1 retains the `base_balance_debit` capability and
    possible `BankAccount::successful_balance_debit_capability` API target in
    all three cases. A refreshed-source test with a sufficient unconditional
    debit suppresses that API target.
15. **New logical targets.** `SavingAccount`, `SavingAccount::savingBalance`,
    credential/verification capability, authentication-gated savings,
    savings-interest behavior and compatible subclass initialization remain
    represented where the typed design supports them. P1 selects no Java path.
16. **Constructor requirement.** Compatible initialization of the existing
    base constructor remains a capability. Constructor signatures and exact
    initialization code remain deferred.
17. **Source layout.** The `SavingAccount` source-layout decision stays
    deferred. No `SavingAccount.java` path is chosen during refresh.
18. **Implementation details.** Helper names, field representation and
    visibility, debit API signature, exact override syntax, constructor
    signature and filename remain deferred.
19. **Post-refresh recheck.** RECHECK.1's refresh adapter reconstructs P1 and
    verifies the bound transition is no longer marked
    `NEEDS_TRANSITION_DECISION` and no behavior-changing semantic decision is
    left unresolved. Its result is `semantic_recheck_not_required` for all three
    supported answers.
20. **Fixpoint.** `structural_semantic_fixpoint=true` for subclass-only,
    compatibility and specialization. It means the known semantic consequence
    of this proposal has been resolved; it does not authorize implementation.
21. **Stale handling.** Changed or missing source/context bindings return
    `reacquisition_required`; the old proposal is not refreshed over changed
    code.
22. **Forged handling.** Modified P0, semantic continuation, effective design
    or RECHECK receipt cannot reconstruct the expected canonical inputs and is
    rejected.
23. **Wrong parent.** A transition continuation bound to another P0 fails the
    regenerated RECHECK.1 continuation comparison and produces no P1.
24. **Idempotency.** Repeating a refresh with the same P0, semantic chain,
    source and current scope returns the same P1 fingerprint. Passing P1 as if
    it were the historical P0 is rejected; no P2 revision is created.
25. **RepairScope delta.** `0`.
26. **AuthoringRepairScope delta.** `0`.
27. **Candidate.** `null`; patch is empty.
28. **Authority.** P1 has `authority=proposal_only`,
    `scope_authority=proposal_only`, `write_authority=false`,
    `repair_scope_authority=false`, `execution_authorized=false`,
    `auto_apply=false` and `apply_authority=false`.
29. **Model and author calls.** Zero.
30. **Traversal.** Zero repository traversal. Replay guards filesystem reads and
    writes, subprocesses, provider connections and traversal; semantic work
    consumes only supplied buffers and typed evidence.
31. **Performance.** Ten guarded samples per transition; milliseconds shown as
    median / maximum for parent validation, revised semantic validation, scope
    regeneration, semantic diff, full post-refresh recheck, and total. Subclass-
    only: **36.283 / 96.484**, **76.688 / 171.240**, **12.310 / 30.105**,
    **0.063 / 0.169**, **134.277 / 315.712**, total **274.743 / 614.677**.
    Compatibility: **87.313 / 91.527**, **175.264 / 182.622**, **27.448 /
    29.345**, **0.131 / 0.281**, **308.621 / 319.803**, total **609.189 /
    624.859**. Specialization: **88.740 / 92.713**, **172.883 / 183.371**,
    **28.000 / 29.730**, **0.117 / 0.228**, **311.424 / 328.168**, total
    **610.757 / 617.272**. Provider latency is not applicable.
32. **BANK.1.** A review-only task remains `not_applicable`; it produces no
    refreshed proposal.
33. **Focused tests.** `tests/test_patch_scope_refresh1.py` covers all three
    answers, distinct target semantics, lineage, determinism, fixpoint, source
    freshness, forged P0/continuation, wrong parent, unresolved/unknown/conflict
    answers, BANK.1, current-scope binding, debit sufficiency, zero authority,
    and blocked provider/filesystem/traversal operations. The focused suite
    passes **14 tests**.
34. **Adjacent tests.** After the final full P1 recheck, the refresh, RECHECK.1,
    EXPAND.1 and registry/picker batch passes **400 tests**. The broader
    CONTINUE.1, DETECT.2, DESIGN.1 and UI.1 integration batch passed **565
    tests** before the final post-recheck timing adjustment; the focused refresh
    suite was rerun after that adjustment and passes **14 tests**. The
    authoring/scope and authority batch: **256 passed, 3 failed**. Two frozen
    attribution checks fail on the pre-existing `web/runner.py` byte mismatch.
    The human-authority picker check expects `UX.RUN.1`; the test-only reversal
    that removes this phase still selects `DOGFOOD.1B`, confirming that mismatch
    predates REFRESH.1. These failures are outside this patch's allowed files;
    historical receipts were left unchanged.
35. **Registry, benchmarks and diff checks.** One CONTROL phase is registered;
    its current registry total is **211 phases** with **29 CONTROL** entries,
    and its picker history bucket is **207**. All **54 benchmarks pass**,
    `compileall` passes, and `git diff --check` passes.
36. **First remaining blocker.** `SCOPE_APPROVAL_NOT_IMPLEMENTED`. P1 is a
    reviewable proposal only. Scope approval/admission is deliberately outside
    this phase.

## Explicit answers

- **Was P0 historical rather than reused?** Yes. It was fully reconstructed
  against the original effective design; P1 is a separate immutable object.
- **Did every valid transition produce a proposal bound to new semantics?**
  Yes. Each P1 binds its P0, transition continuation, E1 and exact source.
- **Did `BankAccount::saving` stop being `NEEDS_TRANSITION_DECISION`?** Yes.
- **Did choices produce meaningfully different scope requirements?** Yes.
  Subclass-only has a possible base API transition; compatibility preserves the
  base behavior; specialization preserves a compatible contract.
- **Was private `balance` handled without visibility invention?** Yes.
- **Did source layout stay deferred?** Yes.
- **Did planning discover another human-owned semantic gap?** No for the three
  supported transitions; the post-refresh RECHECK.1 adapter reports no gap.
- **Was a semantic/structural fixpoint reached?** Yes for all three supported
  transitions.
- **Was actual scope admitted, a candidate produced, or authority granted?**
  No to all three.
- **Did any model or repository traversal run?** No.

Replay command:
`python scripts/replay_patch_scope_refresh1.py --repetitions 10 --output docs/roadmap/PATCH_SCOPE_REFRESH_1_BANK2.json`.
