# PATCH.SCOPE.APPROVE.1 — Human Structural Scope Ceiling Approval

An explicit human action can approve, decline, or request revision of one exact,
reconstructed REFRESH.1 proposal P1. Approval is immutable evidence for later
deterministic scope admission. It never admits a scope or authorizes editing.
The implementation is complete with the inherited validation warnings below.

1. **Files changed.** Added `core/structural_scope_approval.py`,
   `web/structural_scope_approval.py`, `web/templates/scope_approval_review.html`,
   `web/static/scope_approval.js`, `tests/test_patch_scope_approve1.py`,
   `tests/_patch_scope_approve1_maintenance.py`,
   `tests/fixtures/patch_scope_approve1_reversal.json`,
   `scripts/replay_patch_scope_approve1.py`, this report and
   `PATCH_SCOPE_APPROVE_1_BANK2.json`. Updated `web/app.py`,
   `web/session_presentation.py`, `web/templates/index.html`,
   `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`,
   `tests/test_phase_picker.py`, and `tests/_patch_scope_refresh1_maintenance.py`.
   These 17 files are the APPROVE.1 delta against the preserved dirty entry
   state. Earlier user changes are retained. Temporary logs and the synthetic
   browser screenshot are under `.tmp/`.
2. **Approval owner.** The human owns the decision through the guarded
   `/scope_approval/decision` POST. The core harness owns deterministic
   reconstruction and receipt construction. `register_scope_approval_review`
   exposes the narrow harness seam for a validated P1; registration only waits
   for a human and never approves.
3. **Inputs.** Exact refreshed P1 and REFRESH result, typed task contract,
   original design and CONTINUE.1 lineage, original gap/answer and DETECT.2
   receipt, historical P0, transition continuation and gap/answer, revised
   effective design, RECHECK receipt, acquired source/context buffers, repository
   identity/path and current actual scope with its expected fingerprint.
4. **Receipt schema.** Frozen `StructuralScopeApprovalReceipt`, schema
   `patch_scope_approve_1_v1`, phase `PATCH.SCOPE.APPROVE.1`. It binds decision,
   status, exact proposal and parent fingerprints, semantic design, transition,
   task, repository, all source/context bindings, actual and measured scope
   fingerprints, fixpoint evidence, typed ceiling and ceiling fingerprint,
   human action evidence and fingerprint, review fingerprint and approval
   effect. Canonical sorted JSON determines identity. Timings and wall-clock
   timestamps do not participate.
5. **P1 validation.** Frozen REFRESH reconstruction validates original P0,
   original semantic chain, transition continuation, revised design and exact
   source/repository/scope bindings. Full canonical proposal content must match;
   a fingerprint alone is insufficient. Transport uses closed existing typed
   records and bounded capsules, with no arbitrary imports or class selection.
6. **Fixpoint gate.** Requires literal `structural_semantic_fixpoint=true` and
   an independently reconstructed post-refresh RECHECK with no gap, no remaining
   human-owned semantic assessment and no refresh requirement. A stored flag or
   substituted recheck cannot bypass this gate: `approval_unavailable`.
7. **Freshness.** Core reconstruction uses supplied current buffers. The web
   adapter freshness-reads only exact previously bound paths and checks again
   before persistence. Repository/task binding, proposal, semantics, CONTROL,
   current scope and preserved session semantic evidence must remain exact.
   Changed source requires reacquisition; changed state is `approval_stale`.
8. **Approved ceiling representation.** `ApprovedScopeCeiling` preserves typed
   new logical targets, existing targets, required capabilities, deferred
   decisions, exact source/context bindings and blast radius in separate tuples.
   Categories/certainty remain `MUST_CREATE_LOGICAL`, `MUST_SUPPORT`,
   `MAY_REQUIRE_EXISTING_API_CHANGE`, and `DEFERRED_IMPLEMENTATION_TARGET`.
   It has no authoring renderer or patch envelope.
9. **Logical-target binding.** Exact logical identity, owner, kind, parent and
   evidence references are retained. `SavingAccount` binds parent `BankAccount`;
   its file stays unresolved. Member/capability identities retain their logical
   owner. No invented `SavingAccount.java` path enters approval.
10. **Existing-target binding.** Exact file, owner/class, target/member/capability,
    category, API flag, evidence references and any declaration fingerprint/span
    remain unchanged. Capabilities without a concrete declaration retain the
    exact class/source/context fingerprint binding. No fuzzy member matching.
11. **MAY targets.** Possible debit/base-API modifications are explicit maximum
    ceiling targets. They are never presented or recorded as mandatory edits.
    A later admission phase must choose a justified subset/equal-to ceiling.
12. **Deferred implementation.** Layout, constructors, state representation,
    visibility, credential/helper decomposition, debit signatures and possible
    retirement/migration mechanisms stay deferred. Revision notes do not resolve
    any of these choices or introduce a new semantic design.
13. **UI summary.** The existing workbench contains a bounded review section
    with new logical definitions, required capabilities, existing potentially
    affected structure, possible API changes and deferred choices. Raw JSON is
    transport rather than the only review surface. Apply and Generate actions
    are hidden/disabled on this review, including after a decision.
14. **Blast-radius presentation.** Exact P1 radius is displayed and included in
    the review and ceiling fingerprints. Altering a displayed radius breaks
    canonical review binding and rejects submission.
15. **Approve action.** `approve_exact_scope_ceiling` creates
    `approved_for_scope_admission`, `eligible_for_admission=true`, and
    `approval_effect=eligible_for_admission_only`.
16. **Decline action.** `decline_scope_expansion` creates
    `scope_approval_declined`, grants no eligibility, preserves P1/semantics and
    triggers no retry or candidate.
17. **Revision action.** `request_scope_revision` creates
    `scope_revision_requested`, grants no eligibility and may retain a bounded
    1,000-character human note. Line endings are canonicalized; unsafe controls
    are rejected. The note is never parsed into design or implementation.
18. **Approval provenance.** `HumanScopeDecisionAction` requires
    `explicit_human` and the dedicated scope-review channel. The guarded POST
    constructs that evidence itself; submitted provenance, confidence, targets,
    partial toggles and arbitrary fields are rejected. Tests/replay use a
    separately identified synthetic human channel. Original task wording,
    semantic clarification, model output, Generate and confidence cannot approve.
19. **Admission eligibility semantics.** Evidence permits only a later harness
    admission operation consistent with this exact semantic design and bounded
    ceiling. `validate_structural_scope_approval_receipt` requires independent
    stored human evidence and fresh typed inputs, compares the complete receipt,
    and defaults to rejecting decline/revision evidence for admission.
20. **P1 authority after approval.** Still `scope_authority=proposal_only`.
    P1 is never mutated or renamed as implementation authority.
21. **Idempotency.** The same P1, review and decision evidence produce the same
    semantic receipt/fingerprint. Web retries return the stored result without
    a session write or duplicate event. Concurrent identical actions are
    serialized within the existing local session owner.
22. **Conflicting retry behavior.** Approve→decline and decline→approve fail
    closed as `conflicting_human_scope_decision`; evidence is never overwritten.
    Changed decision evidence also fails binding. No revocation is introduced.
23. **Stale after approval.** Historical receipts remain unchanged. The pure
    validator refuses source/design/scope/repository/proposal changes. Web
    history displays stale/unavailable state with no action, while preserving
    the historical decision. Subsequent changes to an attached session's
    semantic chain also invalidate eligibility.
24. **Current-scope binding.** Receipt binds the exact scope fingerprint and
    its measured RepairScope fingerprint. Frozen reconstruction checks the
    existing scope snapshot. Web custody also binds the current proposal/scope
    marker and original CONTROL. Existing measured and authoring scope fixtures
    remain byte-for-byte equivalent before/after approval.
25. **P0 rejection.** Historical EXPAND.1 P0 cannot enter the approval seam:
    `historical_proposal_not_approvable`. Only refreshed P1 is accepted.
26. **Wrong-P1 rejection.** A different transition, proposal, ceiling or review
    fingerprint cannot reuse the action/receipt. Full lineage is reconstructed.
27. **Model/self-approval rejection.** No receipt can be created by this seam
    without separately supplied trusted human action evidence. Model/author/
    harness/confidence/original-task payloads are not such evidence. The future
    validator does not trust the receipt's embedded provenance on its own.
28. **History durability.** Uses existing `web.session_store` JSON session
    storage, ordinary history, statuses and events. There is no second storage
    system. It can attach to an explicitly selected semantic session, retaining
    that chain and its identity, or register a new normal scope-review session.
    No real BANK.2 session is discovered or consumed automatically.
29. **GET/read-only behavior.** Session/history GETs only reconstruct and
    project. They never invoke the refresh action, decide, persist or widen
    authority. Reload tests compare durable file bytes before/after. Existing
    origin, CSRF, authentication and read-Host guards remain intact.
30. **RepairScope delta.** `0`, including a non-empty measured-scope fixture.
31. **AuthoringRepairScope delta.** `0`, including an existing authoring-scope
    fixture. Approval does not manufacture an actual scope or write envelope.
32. **Candidate.** `null`; patch is empty. No author-compatible target list or
    candidate is emitted.
33. **Subject-source mutation.** None. Java source buffers/files are unchanged;
    no SavingAccount file is created. Synthetic fixture files stay under test
    directories. Harness implementation files are the scoped changes in item 1.
34. **Write/Apply authority.** `write_authority=false`,
    `execution_authorized=false`, `auto_apply=false`, `apply_authority=false`,
    `repair_scope_authority=false` throughout. Scope approval is a distinct action
    and does not reuse Apply.
35. **Model calls.** `0` in the approval phase and guarded replay. Provider
    latency is not applicable.
36. **Author calls.** `0`; no code generation, prompt construction or authoring
    context admission occurs.
37. **Traversal.** `0` repository traversals. Core validation consumes bound
    buffers; web reads only bound exact source paths and normal session storage.
    Replay guards provider access, authoring, file I/O, subprocesses and traversal.
38. **Performance.** Ten guarded samples per decision for all three transitions.
    The JSON artifact records median/max for proposal reconstruction/validation,
    fixpoint validation, presentation, receipt construction, receipt validation
    and total. The table below summarizes approve decisions. No provider latency.
39. **Subclass-only replay.** Logical SavingAccount/state/auth/savings structure,
    possible debit API ceiling and base savings transition preserved. It does
    not choose deletion. Approve receipt validates; no scope admission occurs.
40. **Compatibility replay.** BankAccount.saving remains semantically required
    and the subclass has separate savings state. Approve receipt validates; no
    deletion is selected and no scope admission occurs.
41. **Specialization replay.** Preserves the common base savings contract and
    subclass specialization. No abstract/override mechanism is invented. Approve
    receipt validates without scope admission.
42. **Decline replay.** All three P1 fixtures produce immutable declined
    receipts, no eligibility and unchanged authority; retries are idempotent.
43. **Revision replay.** All three P1 fixtures produce immutable revision
    receipts with uninterpreted synthetic notes, no eligibility or semantic
    change; retries are idempotent.
44. **Focused tests.** **62 passed** after the final semantic-chain freshness check. Covers all required positive and
    negative cases, exact/schema/provenance binding, immutable retries,
    existing non-empty scopes, concurrent duplicate decisions, source/semantics/
    repository/current scope changes, displayed-radius forgery, stale historical
    receipts, structured guarded POSTs, durable read-only history and attached
    semantic-chain preservation. The browser also successfully submitted a
    synthetic approval, then showed approved status with no decision form,
    Generate or Apply; screenshot `.tmp/approve1_browser_approved.png`.
45. **Adjacent tests.** Scope REFRESH/RECHECK/EXPAND and OOP DESIGN/DETECT/
    CONTINUE/UI: **291 passed**, one existing browser test could not import its
    unreadable Playwright package. Authoring-scope/authority/registry/picker:
    **417 passed, 3 inherited failures**. Session/history/auth/read-Host:
    **298 passed, 6 inherited frozen-attribution failures**. Read-only substitution
    of the preserved entry bytes reproduces all nine failures: two frozen
    `web/runner.py` mismatches, a stale picker expectation (`UX.RUN.1` versus
    `DOGFOOD.1B`), and six historical registry attribution mismatches. These are
    not new APPROVE.1 failures. No historical frozen receipt was repinned.
46. **Registry/benchmarks.** One narrow CONTROL phase registered. Registry:
    **212 phases / 30 CONTROL**; history picker: **208**. Final registry/picker
    plus historical DESIGN transport: **276 passed**. **54 benchmark cases /
    0 errors**, `compileall`, JavaScript syntax and `git diff --check` pass.
    This phase's reversal restores all six shared files exactly to their dirty
    entry bytes, including original newline conventions.
47. **First remaining blocker.** `SCOPE_ADMISSION_NOT_IMPLEMENTED`. Stop here;
    actual admission, planning, authoring and Apply are outside this phase.

| Explicit question | Answer |
| --- | --- |
| Can a human approve an exact refreshed P1? | Yes, using the structured review action. |
| Does approval bind the exact proposal and semantic/source lineage? | Yes, with canonical reconstruction and full bindings. |
| Is approval admission eligibility rather than actual scope? | Yes. |
| Are MAY targets a maximum ceiling rather than mandatory edits? | Yes. |
| Do source layout and implementation details remain unresolved? | Yes. |
| Can historical P0 be approved? | No. |
| Can a model or original task imply approval? | No. |
| Does an approved receipt widen RepairScope or AuthoringRepairScope? | No; both deltas are zero. |
| Does approval create a candidate? | No. |
| Does approval grant write or Apply authority? | No. |
| Is the receipt durable and idempotent? | Yes, in existing session history. |
| Can future admission validate without trusting UI state? | Yes; the pure validator requires fresh typed inputs and independent human action evidence. |

Approved decisions, milliseconds **median / maximum**:

| Stage | Subclass only | Compatibility | Specialization |
| --- | ---: | ---: | ---: |
| Proposal reconstruction/validation | 360.377 / 400.891 | 361.894 / 381.070 | 370.982 / 587.270 |
| Fixpoint validation | 358.198 / 441.947 | 360.339 / 424.490 | 368.788 / 453.645 |
| Presentation projection | 4.241 / 6.832 | 4.786 / 8.181 | 5.262 / 9.795 |
| Receipt construction | 7.996 / 10.713 | 8.080 / 13.037 | 8.142 / 10.719 |
| Receipt validation | 748.942 / 790.523 | 749.194 / 798.024 | 769.421 / 817.143 |
| Total | 1488.928 / 1586.729 | 1502.277 / 1557.154 | 1527.745 / 1688.185 |

Replay: `python scripts/replay_patch_scope_approve1.py --repetitions 10 --output
docs/roadmap/PATCH_SCOPE_APPROVE_1_BANK2.json`. Only synthetic human decisions and
the frozen synthetic semantic fixtures are used. No real BANK.2 answer or real
scope approval is consumed.
