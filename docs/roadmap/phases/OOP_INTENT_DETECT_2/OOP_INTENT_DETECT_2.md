# OOP.INTENT.DETECT.2 — Missing Future-Design Contract Admission

The exact BANK.2 task now deterministically reaches one evidence-bound,
candidate-free `OOPIntentGap`, then one durable
`waiting_for_clarification` session through the frozen OOP.INTENT.UI.1
lifecycle. The replay does not answer that clarification and performs no
authoring, scope expansion, model call, repository traversal, or source
mutation.

Important boundary: frozen OOP.INTENT.DESIGN.1 does not type arbitrary raw
complete-answer or partial-answer prose. DETECT.2 therefore rejects altered
projection payloads and fails those raw fixtures closed as
`projection_bounded`; it does not pretend that deleting unresolved dimensions
is a valid typed answer. A supplied answer is durably recorded as pending a
future typed-projection continuation and never reaches an author.

| Requested report item | Result |
| --- | --- |
| 1. Files changed | DETECT.2 adds `core/oop_intent_detector.py`, `tests/test_oop_intent_detect2.py`, `tests/_oop_intent_detect2_maintenance.py`, `scripts/replay_oop_intent_detect2.py`, this report, and `OOP_INTENT_DETECT_2_BANK2.json`. It minimally extends `core/oop_semantic_review.py`, `core/oop_intent_session.py`, `web/oop_intent_adapter.py`, `web/app.py`, `web/runner.py`, and `main.py`; registry/picker metadata and maintenance seams are updated without repinning historical receipts. The adjacent DESIGN.1 files remain prerequisite work, not DETECT.2 output. |
| 2. Detector owner | `core/oop_intent_detector.py::detect_missing_future_design_contract` is the single deterministic owner. It accepts already typed/preserved inputs, owns no file access, provider, discovery, candidate, or authority. |
| 3. Inputs | A preserved `TaskContract`, its bound `ProposedDesignIntent`, one exact `ClassSemanticContext`, the exact source bytes that produced that context, and canonical repository identity. It never independently reparses raw prose. |
| 4. Admission schema | `OOPIntentDetection`, schema `oop_intent_detect_2_v1`, carries a closed status, current/desired comparisons, one disposition per unresolved dimension, at most one gap, stage timings, and permanently read-only side-effect counters. The admitted gap uses `dimension=future_design_contract` with seven typed subdimensions. |
| 5. Projection-status gate | Preservation/routing failure or unavailable projection returns `projection_unavailable`; binding or full-payload disagreement with a freshly projected DESIGN.1 value returns `projection_mismatch`; conflict returns `design_conflict`; relevant bounded/omitted evidence returns `projection_bounded`. No such state manufactures a human question or calls an author. |
| 6. Provenance gate | Human commitments must be `explicit_human`; unresolved relevance may be `inferred_semantic_interpretation`; acquired implementation comparisons are `current_source_fact`. Forged nonhuman commitments produce `provenance_rejected`. |
| 7. Current-vs-desired comparison | BANK.2 records three non-defect transition facts: the acquired context is `BankAccount` and does not prove repository-wide `SavingAccount` absence; acquired `BankAccount` lacks `savingBalance`; and the acquired class has no authentication-shaped field, parameter, or callable. Desired facts remain explicit inheritance, subclass-only state, and password-gated savings. |
| 8. Materiality rule | A dimension blocks only when at least two plausible remaining human choices materially change owned state, balance mutation, persistence semantics, or gate lifecycle. Unspecified alone is never sufficient. |
| 9. Machine-resolvable rule | Only a narrow exact structural fact may resolve its matching dimension—for example, a credential field or parameter on the desired owner may resolve current ownership/source. A token, field, or method does not settle persistence, verification lifecycle, funding direction, or interest arithmetic. Relevant projection evidence that DESIGN.1 could not type fails closed rather than becoming a question. |
| 10. Human-owned rule | Only `human_owned_material` dimensions enter a gap. Every unresolved dimension receives exactly one of `deferred_implementation`, `machine_resolvable`, `human_owned_material`, or `irrelevant_to_current_transition`. |
| 11. Blocking-dimension policy | Exact BANK.2 makes credential ownership, source, persistence, verification mechanism, verification lifecycle, savings funding, and savings interest material. These seven are represented as typed subdimensions of one transition contract. |
| 12. Deferred-dimension policy | `source_layout` and subclass creation lifecycle are `deferred_implementation`. Verification failure behavior and account identity are secondary and `irrelevant_to_current_transition` unless later evidence makes them independently material. |
| 13. Auth-contract detection | The explicit password-verification behavior gate, combined with exact absence of an auth-shaped surface in the acquired class, exposes a missing credential owner/source/persistence/verification-lifecycle contract. The acquired-context claim is deliberately not repository-wide. |
| 14. Savings-contract detection | The desired subclass-only `savingBalance` is absent from acquired `BankAccount`; funding from inherited balance versus independent funding and interest application produce materially different state transitions, so both savings dimensions remain human-owned. |
| 15. Source-layout handling | No filename/location question is asked. The replay records `source_layout=deferred_implementation`, leaves the CONTROL free of `repair_scope`, and stops before any exact edit-set selection. |
| 16. Resolved commitment suppression | The detector preserves and leads with: `SavingAccount extends BankAccount`; `savingBalance` belongs only to `SavingAccount`; savings functionality requires successful password verification. It never re-asks those choices. |
| 17. Explicit-answer suppression | Existing explicit inheritance, subclass-state, and password-gate commitments are never re-asked. The requested raw fully specified answer fixture currently reaches `projection_bounded`, not `no_gap`, because frozen DESIGN.1 marks its additional clauses `not_resolved_by_projection`. DETECT.2 refuses both a misleading question and authoring; it does not forge a “resolved” projection. |
| 18. Partial-answer behavior | Raw auth-only and savings-only answer fixtures likewise fail closed at the frozen projection boundary, so no resolved group is repeated and no partial free text reaches an author. The question builder itself is dimension-scoped, but producing a narrower admitted gap requires the first remaining blocker: a typed answer-to-DESIGN continuation. Persistent intent selects no DB/CSV/file mechanism. |
| 19. Grouping/deduplication | BANK.2 produces exactly one `OOPIntentGap`, not separate credential/persistence/lifecycle/savings sessions. A content-bound stable `gap_id` lets two identical UI admissions reuse one waiting session; replay observed one session and identical session IDs. |
| 20. Question | “You've already specified that SavingAccount extends BankAccount, savingBalance belongs only to SavingAccount, and savings functionality requires successful password verification. For this exercise, how should the remaining verification and savings behavior work? Please specify who owns or supplies the credential, whether it persists, how it is verified, what operation or lifecycle verification gates, how savingBalance is funded, how interest applies.” |
| 21. Alternatives | Four bounded semantic prompts: an in-memory credential; a credential contract that persists across runs without selecting storage technology; transfer from inherited balance; or independent funding. They are alternatives, never defaults. Question text and alternatives are both scoped to the remaining typed dimensions. |
| 22. Evidence refs | The gap uses eight bounded system-owned refs covering the Task Contract, design projection, exact current-source structure, repository identity, explicit relationship/state/gate commitments, and grouped unresolved dimensions. Seven distinct unresolved-dimension refs bind its seven subdimensions; arbitrary source quotes are not gap authority. |
| 23. Freshness | Task hash, Task Contract fingerprint, full freshly recomputed design fingerprint, exact source fingerprint, repository identity, class/path, and relevant refs are bound into the stored gap and stable `gap_id`. CRLF bytes are reacquired exactly from the already selected path. Stale source, stale/altered design, or repository mismatch cannot reuse the clarification. |
| 24. UI admission | `make_stored_future_design_gap` adapts the validated detector result into the existing `oop_intent` schema. `create_oop_intent_wait` and the frozen OOP.INTENT.UI.1 lifecycle are reused; no new global clarification type exists. A future-design answer is stored as `clarification_supplied_pending_projection`, with no prompt or provider call, until a typed continuation exists. |
| 25. Waiting session | Exact replay terminal: `waiting_for_clarification`, `clarification_kind=oop_intent`, one durable session after two admissions, no supplied answer, candidate `null`, patch empty, patch plan `null`, Apply unavailable. |
| 26. Author-call count | Zero. Admission runs before patch authoring in Generate Patch, all three Generate Candidates authors, the agent web runner, and terminal `main`; the future-answer endpoint also cannot author from free text. |
| 27. Candidate | `patch_candidate=null`, `patch=""`, `patch_plan=null`. No `SavingAccount`, authentication implementation, or candidate is generated. |
| 28. Infrastructure invention | None. Question/alternatives contain no database, CSV, JSON, hashing algorithm, salt, token, OAuth, retry-limit, or lockout choice. Replay records an empty implementation-default set. |
| 29. RepairScope/scope-expansion behavior | Detection/admission runs before every covered `build_control_prompt`/draft-author seam. The stored gap says only `scope_expansion=deferred`; replay confirms no `repair_scope` key and no exact edit set. RepairIntentGap is unchanged. |
| 30. Authority | `authority=read_only`; `write_authority=false`, `execution_authorized=false`, `auto_apply=false`, and `repair_scope_authority=false`. No authority is inferred from clarification. |
| 31. Model-call delta | Zero detector/provider calls. The dogfood replay is entirely deterministic and offline; provider latency is `not_applicable`. |
| 32. Traversal delta | Zero detector repository traversals. The UI adapters freshness-read only the exact CONTROL-named or already selected evidence path; they do not list, glob, walk, search, index, or broaden context. |
| 33. Performance | BANK.2 replay, 100 detector runs: median/max projection validation 2.00545/3.6971 ms; comparison 0.33285/0.6692 ms; materiality classification 0.1525/0.2918 ms; gap construction 1.13035/3.3081 ms; total 3.63675/6.7003 ms. These are local run measurements, not provider latency. |
| 34. BANK.1 regression | Educational current-code review, a suggestion-only inheritance question, and a password-word-only task return `not_applicable`; BANK.1 remains informational and creates no DETECT.2 wait. A future-design `no_gap` yields to the independent frozen current review, and an unrelated singleton Java class cannot bind the future detector. CTX.OOP.1C output is not mutated to force admission. |
| 35. BANK.2 replay | `scripts/replay_oop_intent_detect2.py` replayed the exact task over exact source, produced one gap with auth+savings subdimensions, admitted it twice, observed one durable unanswered wait, and asserted all stop-condition invariants. Serialized evidence is in `OOP_INTENT_DETECT_2_BANK2.json`. |
| 36. MainApp integrity | Replay used an isolated sentinel `MainApp.java`; its bytes and `bank.java` bytes were identical before/after. The existing MainApp RepairIntent session was neither read, answered, nor modified. No tracked application source was touched by replay. |
| 37. Focused tests | `python -m pytest tests/test_oop_intent_detect2.py -q`: **30 passed**. Coverage includes exact BANK.2, classification/materiality, honest raw complete/partial fail-closed behavior, dimension-scoped questions, no storage invention, negatives, conflict/bounded/stale/payload/provenance states, exact CRLF bytes, stale-design rejection, exact-class selection, current-review preservation after future `no_gap`, durable UI, pending-projection answer stop, Generate Patch/Candidates/web/terminal ordering, determinism, side effects, and performance. |
| 38. Adjacent tests | DESIGN.1 + frozen CTX.OOP.1A/1B/1C + OOP.INTENT.UI.1: **115 passed**, one third-party deprecation warning. No full-suite-green claim is made. |
| 39. Registry/benchmarks | Registry/picker: **267 passed**. Benchmark metadata: **54 checked, 0 errors**. `compileall` across core/web/scripts/tests and `git diff --check` passed (only Git line-ending notices). One narrow CONTROL phase is registered; frozen receipts were not repinned. |
| 40. First remaining blocker | Runtime is correctly blocked on the human's grouped future-design answer. Frozen DESIGN.1 cannot yet admit that answer—or the requested raw complete/partial fixtures—into a revised typed projection. An upstream typed answer-admission/continuation phase is required before they can honestly advance to `no_gap` or a narrower gap. Scope expansion remains later and separate. |

## Explicit answers

- Did BANK.2 now produce one typed `OOPIntentGap`? **Yes.**
- Did the detector preserve resolved inheritance and subclass-state commitments? **Yes.**
- Did it identify missing authentication semantics? **Yes.**
- Did it identify missing savings funding/interest semantics? **Yes.**
- Did it avoid asking about source layout first? **Yes; it deferred layout.**
- Did it avoid database/CSV/storage selection? **Yes.**
- Did it avoid hashing/security-policy invention? **Yes.**
- Did it group the problem into one useful clarification? **Yes.**
- Did it skip authoring while human intent remained unresolved? **Yes; zero author calls.**
- Did it leave RepairScope and authority unchanged? **Yes.**
- Did BANK.1 remain informational? **Yes.**
- Was any global `HumanEvidenceGap` introduced? **No.**

Reproduce the replay from the repository root:

```powershell
python scripts/replay_oop_intent_detect2.py
```

Regenerate the checked evidence artifact:

```powershell
python scripts/replay_oop_intent_detect2.py --output docs/roadmap/OOP_INTENT_DETECT_2_BANK2.json
```
