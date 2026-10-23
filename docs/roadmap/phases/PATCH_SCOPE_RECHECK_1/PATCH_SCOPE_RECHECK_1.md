# PATCH.SCOPE.RECHECK.1 — Scope-Discovered Semantic Recheck

This phase routes a material transition discovered by a validated structural
scope proposal back to the existing `OOPIntentGap` human clarification lifecycle.
Semantic readiness from DETECT.2 does not settle the treatment of an existing
base-class behavior discovered during exact structural comparison. The phase
stops before expanded scope admission or authoring.

1. **Files changed.** Added `core/scope_semantic_recheck.py`,
   `web/scope_semantic_recheck.py`, `tests/test_patch_scope_recheck1.py`,
   `scripts/replay_patch_scope_recheck1.py`,
   `tests/_patch_scope_recheck1_maintenance.py`,
   `docs/roadmap/PATCH_SCOPE_RECHECK_1.md` and
   `docs/roadmap/PATCH_SCOPE_RECHECK_1_BANK2.json`. Updated bounded OOP UI
   dispatch in `web/app.py` and `web/session_presentation.py`, bookkeeping in
   `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`,
   `tests/test_phase_picker.py`, and the test-only chain in
   `tests/_patch_scope_expand1_maintenance.py`. No BANK source or MainApp source
   is modified. No frozen core implementation or historical receipt is repinned.
2. **Recheck owner.** `core.scope_semantic_recheck.recheck_scope_semantics`
   validates and classifies proposal transitions. The immutable transition
   continuation records an additional semantic revision.
3. **Inputs.** Typed `TaskContract`, validated
   `EffectiveProposedDesignIntent`, frozen DETECT.2 `no_gap` receipt, validated
   `StructuralScopeExpansionProposal`, exact supplied `ClassSemanticContext`
   and source bytes, repository identity, and retained original OOP gap/answer
   evidence used to reconstruct the effective design. Raw task prose is not
   reparsed as independent question authority.
4. **Proposal validation.** Reconstruct EXPAND.1 against the supplied frozen
   typed inputs and compare the entire canonical proposal. Changed proposal,
   effective intent, source, context or repository bindings cannot produce a
   human question. No recheck bypass can make forged scope data authoritative.
5. **Transition candidate selection.** Inspect only targets marked
   `NEEDS_TRANSITION_DECISION` or `semantic_recheck_if_behavior_changes=true`.
   A proposal without a transition candidate returns
   `semantic_recheck_not_required`; ordinary deferred decisions stay deferred.
6. **Implementation-only filter.** Constructor signature and argument order,
   source layout, private helper names, field visibility and debit API shape
   remain `implementation_only` unless different choices change a requested
   external/domain behavior or preserved commitment.
7. **Materiality rule.** Two plausible choices must materially differ in
   externally visible behavior, domain ownership, compatibility or preserved
   user commitments. Code shape by itself is insufficient.
8. **BANK.2 current saving fact.** Exact supplied source establishes
   `BankAccount.saving(...)` mutating ordinary `BankAccount.balance`.
   The question does not ask the human to rediscover its current location.
9. **Desired ownership fact.** Validated effective intent establishes a
   `SavingAccount` subclass with subclass-only `savingBalance`, and interest
   acting on that savings state. Inheritance, credentials, verification,
   transfer and interest semantics remain settled by the prior continuation.
10. **Transition gap.** At most one `OOPIntentGap` is produced for the closed
    subdimension `existing_savings_transition`. It is owned by the human and
    introduces no `HumanEvidenceGap`, `ScopeClarificationGap` or global type.
11. **Question.** "BankAccount currently has saving(...) that modifies its
    ordinary balance. Your future design puts savings state and interest
    behavior on SavingAccount. What should the existing BankAccount.saving
    behavior mean in the future?"
12. **Alternatives.** Savings behavior only on `SavingAccount`; preserve legacy
    base savings behavior alongside independent subclass savings state; retain
    a common savings operation that the subclass specializes; or another
    intended compatibility rule. These choices do not directly select patches.
13. **Evidence refs.** Bind the question to proposal, effective design,
    exact `BankAccount::saving` declaration, source, task and repository
    fingerprints. Current and desired facts retain their producer evidence.
14. **Freshness.** Stale source/declaration requires reacquisition and produces
    no stale question. Source, repository and design consistency are checked
    again during answer projection and post-answer recheck.
15. **UI admission.** A closed scope-transition codec feeds the existing OOP
    clarification UI with `gap_kind=oop_intent`. It carries the established
    facts, alternatives, evidence, freshness and unchanged authority flags.
16. **Waiting state.** Synthetic complete BANK.2 proceeds from DETECT.2
    `no_gap` and EXPAND.1 `expansion_required` to one transition clarification,
    `waiting_for_clarification`, then stops. The real waiting answer is unused.
17. **Answer continuation.** Preserve the original DESIGN.1 and CONTINUE.1
    fingerprints. A provenance-bound `ScopeTransitionContinuation` adds one
    semantic revision; `compose_scope_transition_design` retains its immutable
    parent instead of overwriting earlier commitments.
18. **Subclass-only result.** Synthetic answer projects
    `existing_savings_transition=savings_only_on_subclass`. Base savings
    behavior is no longer part of the intended API. This does not choose method
    deletion, deprecation, an adapter or a migration mechanism.
19. **Compatibility result.** Synthetic answer projects
    `preserve_base_compatibility`. Legacy base behavior remains semantically
    available while the subclass owns savings-state behavior. Callers and
    compatibility duration are not inferred.
20. **Specialization result.** Synthetic answer projects
    `subclass_specialization`, recording the behavior relationship without
    selecting Java override syntax, signature, visibility or abstract members.
21. **Unknown answer.** Unsafe free-text mapping remains bounded/unresolved;
    it does not invent a semantic choice or clear the transition gap.
22. **Conflict.** Contradicting subclass-only savings ownership or another
    established commitment produces `continuation_conflict`, leaving the
    immutable earlier semantic chain intact.
23. **Idempotency.** Identical answer and gap produce the same continuation
    fingerprint and evidence. A changed conflicting answer after projection
    fails closed because no revision contract is introduced.
24. **Source layout.** Same-file versus `SavingAccount.java` stays deferred and
    produces no human semantic gap.
25. **Constructor detail.** Exact signatures, parameter ordering and layout
    remain implementation-only and produce no human semantic gap.
26. **API detail.** Boolean debit, protected helper and another debit
    implementation do not create clarification merely from code shape.
27. **Post-answer semantic result.** Rebuild the effective semantic view and
    validate/recheck the original transition discovery. Each valid closed
    synthetic answer removes the scope-discovered human semantic gap.
28. **Proposal invalidation.** The old EXPAND.1 proposal is bound to the previous
    effective design. A valid semantic revision marks `scope_refresh_required`;
    a future scope planner must regenerate the proposal. It is never silently
    reused as current scope authority.
29. **Author calls.** Zero.
30. **Candidate.** `null`; patch empty; no Java source is generated.
31. **Scope delta.** Zero repair/authoring scope delta. No new class or admitted
    authoring target is created.
32. **Authority.** `write_authority=false`, `execution_authorized=false`,
    `auto_apply=false`, `repair_scope_authority=false`,
    `scope_authority=proposal_only` before and after answers.
33. **Model calls.** Zero detector, continuation, provider and author calls.
34. **Traversal.** Zero phase/replay repository traversal. Only the already
    supplied source bytes, context and proposal are consumed. Reports are saved
    after guarded execution.
35. **Performance.** 100 guarded samples, median / maximum ms: proposal
    validation **46.022 / 73.2245**, transition classification
    **0.06175 / 0.3336**, gap construction **2.7154 / 4.977**, initial total
    **49.3913 / 78.1549**. Subclass-only answer projection is
    **0.69815 / 1.759**; its post-answer semantic recheck stage is
    **51.9054 / 70.9621**, total **103.95835 / 135.7606**. Each of the five
    synthetic answer fixtures has separately recorded stage timings in the
    JSON evidence. Provider latency is not applicable.
36. **BANK.1 regression.** Review-only BANK.1 remains outside patch-scope
    semantic recheck and generates no transition question or patch.
37. **MainApp regression.** Source and semantic intent are unchanged; it is
    neither answered nor modified.
38. **Focused tests.** **55 passed**. Core/UI transition matrix covers the three known choices,
    unknown/conflicting answers, retries, stale and forged inputs, no-transition
    and implementation-only decisions, and authority preservation. Durable UI
    admission and answer retries preserve one session and immutable revisions;
    forged questions, result authority, scope receipts and stripped origin
    metadata fail closed. Stale questions cannot be displayed. BANK.1 and
    MainApp regression fixtures remain unchanged.
39. **Adjacent tests.** Registry/picker uses one additional CONTROL phase:
    210 phases, 28 CONTROL, 206 complete/history. Registry/picker: **271 passed**
    with a fresh workspace-local test directory. Final OOP CONTINUE.1, DETECT.2,
    UI.1, EXPAND.1 and registry/picker batch: **427 passed**. Selected broader adjacent checks:
    **1,043 passed, 14 failed** across frozen EXPAND.1, CONTINUE.1, DETECT.2,
    UI.1, DESIGN.1, CTX, authoring scope/span, RepairIntent, minimality and
    authority checks. The failures reproduce incoming frozen byte drift in
    `web/runner.py`, `core/pipeline.py`, `core/control_engine.py` and registry
    receipts, an incoming picker expectation (`DOGFOOD.1B` versus `UX.RUN.1`),
    and candidate verification unavailable/inconclusive when the sandbox copies
    existing access-denied temporary directories. No new phase behavior failure
    is present. Registry validation is valid; `compileall` passes, all **54
    benchmarks pass**, and `git diff --check` passes.
    Historical receipts remain unchanged through exact test-only reversal.
40. **First remaining blocker.** Before an answer,
    `human_clarification_required` with UI state `waiting_for_clarification`.
    After a valid answer, `SCOPE_REFRESH_REQUIRED`;
    expansion remains proposal-only. Scope approval/admission is a later phase.

Explicit answers: **Yes**, BANK.2 scope planning discovers a new human-owned
question about the future meaning of existing `BankAccount.saving`. **Yes**, the
system asks that transition while avoiding constructor signatures, file layout
and visibility questions. **Yes**, it avoids automatically deleting or
preserving base saving behavior. **Yes**, a typed human answer resolves meaning
without edit authority and requires a scope refresh after semantic changes.
**No**, authoring or actual scope widening occurs. **Yes**, a global
`HumanEvidenceGap` remains absent.

Replay command:
`python scripts/replay_patch_scope_recheck1.py --repetitions 100 --output docs/roadmap/PATCH_SCOPE_RECHECK_1_BANK2.json`.
