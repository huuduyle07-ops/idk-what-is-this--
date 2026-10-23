# PATCH.SCOPE.EXPAND.1 — Evidence-Bound Structural Scope Expansion Proposal

The synthetic complete BANK.2 continuation now produces a bounded immutable
`StructuralScopeExpansionProposal`: semantic status `ready`, scope status
`expansion_required`, blocker `SCOPE_EXPANSION_REQUIRED`. It proposes logical
targets and capabilities without authoring, admission, filesystem creation or
write authority. The real BANK.2 answer was not read or consumed.

1. **Files changed.** Added `core/structural_scope_expansion.py`,
   `tests/test_patch_scope_expand1.py`, `scripts/replay_patch_scope_expand1.py`,
   `tests/_patch_scope_expand1_maintenance.py`, this report and
   `docs/roadmap/PATCH_SCOPE_EXPAND_1_BANK2.json`. Updated only phase bookkeeping
   in `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`,
   `tests/test_phase_picker.py` and the test-only historical reconstruction seam
   in `tests/_oop_intent_continue1_maintenance.py`. Pre-existing checkout changes
   belong to earlier work. No BANK source or frozen implementation was changed.
2. **Proposal owner.**
   `core.structural_scope_expansion.propose_structural_scope_expansion` returns
   frozen `StructuralScopeExpansionResult` containing status, reasons, evidence
   needs and, only for required expansion, a frozen proposal.
3. **Inputs.** Typed `TaskContract`, `ProposedDesignIntent` or validated
   `EffectiveProposedDesignIntent`, frozen DETECT.2 receipt, exact
   `ClassSemanticContext` and current byte buffer, repository identity, optional
   existing `RepairScope` or `AuthoringRepairScope`, independently retained scope
   fingerprint and optional already-acquired related class/context byte pairs.
   Raw task prose is not reparsed as intent authority.
4. **Schema.** `patch_scope_expand_1_v1` binds task/base/effective-design and
   DETECT.2 fingerprints, repository and exact source/context fingerprints,
   current scope snapshot, required capabilities, existing and new logical
   targets, deferred decisions, reasons, blast radius and evidence. Canonical
   sorted JSON and SHA-256 are deterministic; timing observations are separate.
   Existing method targets bind the exact declaration fingerprint and line span;
   authority for one overload cannot cover another. Ambiguous simple class names
   and inconsistent acquired versions of one file fail closed.
   Bounds are 8 contexts, 32 existing targets, 32 new targets, 48 capabilities,
   8 possible API changes, 64 reasons, 32 deferred items, 128 evidence records
   and 65,536 serialized bytes. Overflow stops explicitly; nothing is truncated.
5. **Semantic-ready gate.** Material human-owned dimensions require a validated
   DETECT.2 `no_gap` receipt. Clarification produces
   `semantic_intent_unresolved` and no proposal. Review-only orders produce
   `not_applicable`. Structural context alone never creates an expansion.
6. **Freshness binding.** Exact current bytes must match the acquired source
   fingerprint and freshly projected context. Task, design, effective
   continuation, DETECT.2, repository, class and current-scope bindings are
   checked. `validate_structural_scope_expansion_proposal` reconstructs the
   proposal against current inputs; altered or stale proposal bindings fail.
   Stale source requires `reacquisition_required`.
7. **Current scope.** The synthetic complete BANK.2 fixture supplies no
   `RepairScope`: `current_edit_scope.status=none`, exact snapshot `null`, members
   empty. A supplied method-local scope records its exact ordered members and
   measured snapshot and requires the independently retained fingerprint.
8. **Required capabilities.** BANK.2 requires a subtype definition,
   subclass-owned savings state, compatible initialization, credential-bearing
   verification, a verification gate for requested savings operations, successful
   funding from inherited balance, and interest on savings state. These are
   structural requirements, not generated code or an implementation plan.
9. **New logical definition.** `SavingAccount`, parent `BankAccount`, is
   `MUST_CREATE_LOGICAL` with kind `new_class`. Absence means absent from the
   acquired byte buffers; this phase makes no repository-wide absence claim.
   The logical target has no chosen file path and grants no file-creation right.
10. **Subclass state.** `SavingAccount::savingBalance` is
    `new_field_required`, `MUST_CREATE_LOGICAL`. Ownership is explicit. Numeric
    type, visibility, initial value and representation remain undecided.
11. **Authentication gate.** `SavingAccount` requires the explicitly committed
    in-memory password and verification capability, with no persistence across
    runs. `SavingAccount::authentication_gated_savings_capability` and
    `SavingAccount::credential_state_and_verification` are logical capabilities.
    No password field declaration or verification method signature is invented.
12. **Savings transfer.** A savings credit requires a successful debit from
    inherited account state. The proposal records the funding transition and
    its typed continuation/source provenance; it creates no transfer API.
13. **Private base state.** `BankAccount.balance` is private, so the subclass
    requires a justified base-debit capability. The harness never makes balance
    protected/public, introduces a getter/setter or selects a return-type change.
14. **Existing withdraw suitability.** A closed Java syntax proof recognizes
    only a proven subclass-visible unconditional debit or a guarded debit with
    an exact success result. A conditional `void withdraw(double)` with no
    success signal cannot prove a safe transfer. The frozen replay fixture uses
    a package-visible unconditional `void withdraw(double)`; its visibility is
    insufficiently established while layout is deferred. These are distinct
    source facts, not an assumed shared implementation. Names or boolean return
    types alone are insufficient proof.
15. **Possible BankAccount API change.**
    `BankAccount::successful_balance_debit_capability` is
    `MAY_REQUIRE_EXISTING_API_CHANGE` when current behavior cannot establish the
    required successful debit. The capability is mandatory; selecting and
    changing an API remains potential. Proven existing sufficient behavior
    suppresses unnecessary API expansion.
16. **Existing saving transition.** When exact source shows `BankAccount.saving`
    mutating base balance, it is `DEFERRED_IMPLEMENTATION_TARGET` with
    `NEEDS_TRANSITION_DECISION`. Retirement, override, relocation and compatibility
    preservation remain alternatives. No operation is selected. A transition
    that changes meaningful public/domain behavior requires semantic recheck;
    a final savings modifier alone is an implementation constraint and records
    a possible base transition-capability requirement. It does not manufacture
    a human-owned semantic question. Retirement or other behavior-changing
    transitions are not decided or authorized by this proposal.
17. **Constructor requirement.** An explicit base constructor requires a
    compatible base-initialization path eventually using `super` construction.
    Exact subclass signature, argument order and initialization details are
    deferred. The frozen replay's base constructor takes `double opening`; it
    is not substituted for the measured source's `(accountHolder, balance)`.
    Private-only constructors record a possible base initialization API/layout
    requirement. A final base declaration records a definite base inheritability
    edit requirement. Neither fact selects a constructor signature or source layout.
18. **Source layout.** `source_layout` stays deferred. Every new logical target
    has `file=null`. Repository-convention evidence may be needed later. No
    same-file/new-file decision, filename, traversal or convention discovery
    occurs here.
19. **Expansion set.** Complete BANK.2 has five logical targets: the class,
    savings state, authentication-gated savings capability, credential/verification
    capability and savings-interest capability. Existing targets are the possible
    base-debit API capability and deferred `BankAccount::saving` transition.
    There is no unconditional existing-member edit selected for this fixture.
20. **Certainty categories.** `MUST_CREATE_LOGICAL`, `MUST_EDIT_EXISTING`,
    `MAY_REQUIRE_EXISTING_API_CHANGE` and `DEFERRED_IMPLEMENTATION_TARGET` remain
    distinct. Capabilities separately use `MUST_SUPPORT` and
    `NEEDS_TRANSITION_DECISION`. Empty categories are retained as empty facts;
    structural possibilities are not promoted to mandatory edits.
21. **Blast radius.** Replay reports `member`, `cross-class`, `new-definition`
    and `API-surface`. Other bounded fixtures can report `class`. API-surface
    targets are marked separately from internal implementation targets. Blast
    radius never grants authority.
22. **Evidence/provenance.** Targets and capabilities reference explicit human
    commitments, validated continuation commitments and exact current source
    facts. Each evidence record binds the producer fingerprint. New decisions
    are never justified by arbitrary prose or model judgment.
23. **Proposal authority.** `scope_authority=proposal_only`,
    `authority=proposal_only`, `repair_scope_authority=false`. Passing this type
    to frozen authoring-scope consumption does not create authoring authority.
    Admission/approval is a later seam and is absent from this phase.
24. **RepairScope delta.** Zero. No mutation, replacement, expansion or new
    `RepairScope` is performed. Replay snapshots and tests compare inputs before
    and after proposal construction.
25. **Authoring-scope delta.** Zero. Existing definition-change rejection,
    measured members, scope bounds and replacement-span guards remain unchanged.
26. **Candidate.** `null`; patch is empty. No Java, replacement text or patch
    authoring request is generated.
27. **Write/Apply authority.** `write_authority=false`,
    `execution_authorized=false`, `auto_apply=false`, `apply_authority=false`.
    Logical creation requirements grant no filesystem authority.
28. **Model-call delta.** Zero, including zero author calls. Deterministic code
    compares typed inputs and structural facts; replay forbids provider/author
    entry points and reports all counters as zero.
29. **Traversal delta.** Zero in the phase/replay. Only supplied byte buffers
    and typed contexts are consumed. Walk/list/scan and file I/O are forbidden
    during the guarded replay. The report is written only after proposal work.
30. **Performance.** 100 deterministic guarded samples, median / maximum ms:
    semantic-ready validation **7.3884 / 18.1407**; structural comparison
    **12.4918 / 24.647**; expansion classification **0.0034 / 0.0064**;
    proposal serialization **8.3363 / 15.9536**; total **28.88065 / 56.5869**.
    Provider latency is not applicable.
31. **Complete BANK.2 replay.** Uses the exact frozen synthetic
    `replay_oop_intent_detect2.BANK` and `BANK2_TASK`, and
    `replay_oop_intent_continue1.ANSWERS['complete']`. Continuation → effective
    design → DETECT.2 `no_gap` → bounded proposal, identical across 100 samples.
    The proposal is 15,207 serialized bytes, below the 65,536-byte bound;
    fingerprint `7f5387de185dff7df32cd0fd591fd718ce700558612b732e9e497be1cce50779`.
    No source/session file is created or modified. This intentionally preserves
    the previously proven synthetic fixture rather than reading the real answer.
32. **Partial BANK.2.** A still-unresolved continuation/detection produces
    `semantic_intent_unresolved`, `proposal=null`; no structural planning follows.
33. **BANK.1 regression.** Review-only future-scope request returns
    `not_applicable`, with no proposal or patch intent. Existing review semantics
    and OOP clarification ownership remain frozen.
34. **Same-member negative.** When requirements fit exact current authorized
    members, result is `scope_expansion_not_required` and no proposal. Explicit
    new methods/classes instead require logical definition expansion.
35. **Private-field fixture.** Required inherited transfer records the base-debit
    capability and, where existing subclass-visible success behavior is unproven,
    a possible API change. Sufficient current methods suppress that change.
    No visibility widening is selected.
36. **Missing-context fixture.** Named required related classes without exact
    acquired contexts produce `scope_evidence_incomplete` and bounded evidence
    needs, no complete proposal. Exact contexts allow bounded cross-class scope.
37. **Focused tests.** **58 passed**, including complete/partial BANK.2, BANK.1,
    same-member negative, new method/class, measured conditional-void withdraw,
    sufficient debit methods, exact/missing cross-class context, stale source and
    effective design, forged scopes/proposals, immutable inputs, semantic
    transition deferral, final base/private-constructor constraints, overload
    containment, duplicate class identities, conflicting source versions,
    forged readiness, bounded serialization and no-authority/call/traversal
    guards. Java fixtures remain in memory.
38. **Adjacent tests.** Registry/picker: **269 passed**. Frozen
    CONTINUE.1/DETECT.2/DESIGN.1 and authoring scope/span/RepairScope batch:
    **250 passed, 2 failed**. Both failures are incoming
    frozen `web/runner.py` digest drift (`a2d510…` actual versus `6b4e907…` pinned),
    on a file unchanged by this phase and unchanged by its test-only reversal.
    Authority/pipeline/RepairIntent batch: **256 passed, 1 failed**. The failure
    expects picker recommendation `UX.RUN.1`; both the incoming 208-phase registry
    and new 209-phase registry recommend `DOGFOOD.1B`. Removing only EXPAND.1 in
    memory reproduced the incoming recommendation with a valid registry. No
    historical digest or frozen expectation was repinned.
    CTX.OOP.1A/1B/1C, OOP.UI.1 and PATCH.MINIMAL batch: **307 passed, 9 failed**.
    Six failures arise when the frozen candidate sandbox cannot copy the existing
    access-denied `tmp_tests_*` directories; an isolated diagnostic confirms
    `candidate_apply_status=unavailable` and Windows access-denied copy failures.
    Retrying all six checks outside the sandbox leaves the same six failures.
    Three additional historical-byte assertions fail on unchanged existing files.
    The new proposal replay neither copies these directories nor executes
    candidates. Required checks were run; the full adjacent suite is not green.
39. **Registry/benchmarks.** Exactly one narrow PATCH namespace phase under
    CONTROL; 209 phases, 27 CONTROL, 205 complete/history. New test-only
    bookkeeping reversal reconstructs pre-EXPAND.1 registry/test bytes before
    frozen historical reconstruction. All **54 benchmarks pass**;
    `compileall core web scripts tests benchmarks` succeeds. The final
    `git diff --check` passes. No historical receipt was repinned.
40. **First remaining blocker.** `SCOPE_EXPANSION_REQUIRED`: required structural
    targets exceed the current authorized scope and remain a proposal. This phase
    stops before any widened-authoring contract, admission or approval.

Explicit answers: **Yes**, semantic-ready BANK.2 requires structural expansion.
The class, subclass savings state, credential/verification capability,
authentication-gated savings capability, compatible initialization, successful
funding transition and savings-interest behavior are definitely required.
Changing the base debit API is potentially required; treatment of the existing
base `saving` member remains deferred. **Yes**, private balance requires a
justified base-debit capability. **Yes**, the harness avoids automatic visibility
widening and exact constructor/API signatures, defers source layout and preserves
existing `RepairScope` unchanged. **No**, it creates no candidate, grants no write
authority, calls no model and traverses no repository.

Replay command:
`python scripts/replay_patch_scope_expand1.py --repetitions 100 --output docs/roadmap/PATCH_SCOPE_EXPAND_1_BANK2.json`.
