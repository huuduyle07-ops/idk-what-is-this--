# OOP.INTENT.CONTINUE.1 — Human answer to typed design continuation

Status: COMPLETE_WITH_WARNINGS. The phase stops at semantic readiness. Only
synthetic waiting sessions and answer records were exercised; the real BANK.2
waiting answer was not read or consumed.

1. **Files changed in this phase.** Added
   `core/clarification_answer_evidence.py`, `core/design_intent_continuation.py`,
   `web/oop_intent_continuation.py`, `tests/test_oop_intent_continue1.py`,
   `tests/_oop_intent_continue1_maintenance.py`,
   `tests/fixtures/oop_intent_continue1_reversal.json`,
   `scripts/replay_oop_intent_continue1.py`, this report and
   `docs/roadmap/OOP_INTENT_CONTINUE_1_BANK2.json`. Updated the validation boundary
   in `core/oop_intent_detector.py`, the answer seam in `web/app.py`, the one
   superseded pending-state assertion in `tests/test_oop_intent_detect2.py`,
   `tests/_oop_intent_detect2_maintenance.py`, `tests/test_phase_registry.py`,
   `tests/test_phase_picker.py`, and `docs/roadmap/phase_registry.json`.
   The checkout already contained DESIGN.1/DETECT.2 changes; those are not
   attributed to this phase.
2. **Continuation owner.** `core.design_intent_continuation.continue_design_intent`.
   The session adapter is `web.oop_intent_continuation.project_stored_oop_answer`.
3. **Answer extraction owner.**
   `core.clarification_answer_evidence.extract_clarification_answer`. It does not
   pass the clarification through ordinary task intake. Intake is reused only
   to reconstruct the original preserved task.
4. **Schema.** Frozen `DesignIntentContinuation`, schema
   `oop_intent_continue_1_v1`, contains status, base/gap/task/answer/answer-record
   fingerprints, repository/source/class bindings, immutable typed commitments,
   resolved and remaining dimensions, conflicts, unclassified answer spans,
   explicit provenance and fixed read-only authority. Its fingerprint excludes
   nondeterministic timing measurements.
5. **Parent binding.** Recompute DESIGN.1, rerun base DETECT.2, reconstruct the
   exact canonical stored gap, and compare the full payload. Rebind the stored
   answer to that gap and compare every answer-record field. Matching hashes
   alone cannot admit altered semantic payloads.
6. **Answer provenance.** Each commitment carries `explicit_human`, the answer
   fingerprint and an exact `EvidenceSpan` with literal text and offsets into
   the stored answer. The continuation additionally binds the full record.
7. **Immutable revision behavior.** Original base commitments and fingerprint
   are retained. Neither the answer nor the continuation replaces them.
8. **Effective design.** Frozen `EffectiveProposedDesignIntent` holds the base
   and continuation separately. It removes only validated resolved dimensions
   from the detector-facing unresolved list, preserves the original structures
   and provenance, and has its own deterministic fingerprint.
9. **Authentication typing.** Supports explicit SavingAccount, BankAccount,
   user/account identity, application/session and named-other ownership;
   simple password semantics; in-memory or across-runs persistence;
   semantic password checks; operation, creation or both verification gates.
   These values choose no visibility, constructor, storage API or security quality.
10. **Savings typing.** Supports transfer from inherited balance, independent
    funding, interest on savingBalance and no interest behavior. Formula, rate
    units, frequency and calendar semantics are not inferred.
11. **Partial answers.** A successfully typed partial answer remains
    `clarification_projected`; re-entry yields one narrower OOPIntentGap.
    That gap is retained in the original session result. This phase does not
    add a new multi-answer supersession lifecycle or another session.
12. **Complete answers.** All seven material human dimensions can be resolved;
    DETECT.2 then returns `no_gap`. The task is not called implemented or complete.
13. **Unknown answers.** Unrecognized clauses retain exact spans in
    `not_resolved_by_continuation`; status is `answer_projection_bounded`.
    Unsupported negations, conditions and technology choices cannot become
    resolved semantics. Even a complete supported answer with an unknown
    qualification cannot establish semantic readiness.
14. **Idempotency.** An identical answer produces the same continuation and
    effective fingerprints. Retry revalidates stored bindings and freshness,
    returns the existing result, and creates no session, event or evidence copy.
15. **Conflicts.** Contradictory values and recognized reversals of inherited
    ownership, inheritance or successful verification produce
    `continuation_conflict`. A different answer after a stored answer/revision
    is rejected as `clarification_conflict`; no semantic history is overwritten.
16. **Stale source.** The adapter reads only the gap's exact contained source
    path and checks its hash before projection and again before publishing.
    Stale bytes produce `reacquisition_required`, including on retry. The pure
    core validates the supplied current byte buffer without file reads.
17. **Wrong gap/task.** Full canonical parent reconstruction and answer-record
    comparison reject wrong gap, task, repository, class, evidence or answer
    bindings. The HTTP route also checks the requested run/gap/repository.
18. **Base validation.** A supplied base must exactly equal freshly recomputed
    DESIGN.1. The detector's existing fingerprint, provenance and payload
    mismatch checks remain active against that base.
19. **DETECT.2 re-entry.** The added boundary requires an effective facade plus
    independently supplied stored gap, stored answer and repository path.
    It recomputes the continuation and effective payload. Materiality and
    machine/human/deferred classification rules are unchanged.
20. **Complete BANK.2.** Synthetic stored answer → typed continuation → effective
    design → `no_gap`; zero human-owned gaps.
21. **Auth-only result.** One remaining gap containing only
    `savings_funding_semantics` and `savings_interest_semantics`.
22. **Savings-only result.** One remaining gap containing the five credential
    ownership/source/persistence/mechanism/lifecycle dimensions.
23. **Persistent-auth result.** `credential_persistence=persists_across_runs`
    resolves; the other six material dimensions remain in one gap.
24. **Storage behavior.** No DB/CSV question, storage choice or storage policy is
    invented. Across-runs persistence is a semantic commitment only.
25. **Hashing behavior.** No hashing policy when omitted. Explicit practice-only
    deferral is represented as `hashing_out_of_scope_for_this_exercise`, bound
    to this answer/task/gap. It is not a production-security policy.
26. **Source layout.** Layout and exact construction details remain deferred.
    They do not create a human clarification when material intent is settled.
27. **Session state.** Existing `waiting_for_clarification` session → stored
    `human_provided_semantic_evidence` answer → pending projection →
    `clarification_projected`, or bounded/conflict/reacquisition state. Existing
    pending answers can be explicitly resumed. No real waiting answer was used.
28. **Author calls.** Zero in the continuation/replay. Tests forbid entry into
    the prompt builder and author when handling future-design answers.
29. **Candidate.** None. Patch text is empty; patch plan is absent.
30. **RepairScope/scope expansion.** No expanded edit set is constructed, and
    no RepairIntent or RepairScope implementation is changed.
31. **Authority.** `write_authority=false`, `execution_authorized=false`,
    `auto_apply=false`, `repair_scope_authority=false`. Cached payload forgery
    is rejected even when it alters authority or detection instead of commitments.
32. **Model-call delta.** Zero. Provider paths are denied in synthetic replay
    and test fixtures. The live Semantic Waiter smoke test remains opt-in.
33. **Traversal delta.** Zero. Tests/replay forbid walking/scanning directories;
    source freshness uses only the gap's exact file.
34. **Performance.** 120 local samples across four fixtures, 30 per fixture.
    Median / maximum milliseconds: extraction **0.2282 / 1.0032**;
    continuation construction **0.44325 / 1.7962**; effective projection
    **1.4386 / 3.9656**; DETECT.2 validation/re-entry **14.6596 / 40.4132**;
    total semantic continuation **22.77275 / 60.3097**. Total includes original
    parent reconstruction. Provider latency is not applicable. Session results
    also retain per-stage timing observations, separate from immutable evidence.
35. **BANK.1 regression.** Existing CTX.OOP.1C review still records shared balance
    mutation as a fact and asks the original human-owned domain-overlap question;
    it is not routed through this future-design schema. OOP UI legacy answer
    behavior is preserved.
36. **MainApp regression.** CTX.OOP.1A/1B structure and static/instance evidence
    tests pass. The synthetic MainApp source remains byte-identical.
37. **Focused tests.** 59 CONTINUE.1 tests pass, covering complete/partial/persistent
    answers, vocabulary, exact provenance, unknown/conditional/negative clauses,
    immutable base/source, retries, conflicts, stale source, wrong bindings,
    forged continuations/cached results and session/authority behavior.
38. **Adjacent tests.** The required DESIGN.1, DETECT.2, OOP UI (including browser),
    CTX.OOP.1A/1B/1C, Task Contract, Preservation, Semantic Waiter, RepairIntent,
    history, registry/picker and authority-checkpoint run produced **783 passed,
    1 skipped, 1 pre-existing failure**. The skip is the opt-in live-provider smoke.
    The failure expects `UX.RUN.1`; both the incoming 207-phase registry and the
    new 208-phase registry recommend `DOGFOOD.1B`.
    Additional AUTH.WEB.1/AUTH.DREAM.1 checks produced **208 passed** and four
    old receipt failures, all reproduced against the pre-CONTINUE.1 state in
    memory: registry drift in two checks and `core/control_engine.py` drift in
    two checks. No frozen digest was repinned. The final authority browser rerun
    passed all **8** selected tests (one had already passed in the wider run),
    bringing the additional authority coverage to **215 passed, 4 pre-existing
    failures**. Initial missing-driver/import-path errors were resolved by using
    the installed driver and pinning the workspace path before fixture chdir.
39. **Registry/benchmarks.** One narrow CONTROL phase registered; registry/picker
    tests pass. All **54 benchmarks pass**, compilation succeeds and
    `git diff --check` passes. Test-only exact reversal preserves earlier phase
    receipts. Existing line-ending and provider dependency deprecation warnings
    are nonfunctional environment warnings.
40. **First remaining blocker.** For the complete fixture,
    `SCOPE_EXPANSION_REQUIRED` is reported as later work; no scope is built.
    For partial fixtures, the narrower human-owned semantic gap remains.

Explicit answers: **Yes**, a valid real human answer can now become typed
future-design evidence; the original DESIGN.1 projection stays immutable;
partial answers produce narrower gaps; complete answers can eliminate the
human-owned gap; persistent intent avoids a DB/CSV choice; provenance is explicit;
conflicting/forged evidence is rejected. **No**, this adds no model call, scope
widening or authority. Current source facts remain separate from desired design.
**HumanEvidenceGap remains absent.**

Replay: `python scripts/replay_oop_intent_continue1.py --output docs/roadmap/OOP_INTENT_CONTINUE_1_BANK2.json`.
For browser tests in this environment, the venv reused the already-installed
Python 3.14 user-site Playwright driver and local Chromium; no dependency was
downloaded or installed.
