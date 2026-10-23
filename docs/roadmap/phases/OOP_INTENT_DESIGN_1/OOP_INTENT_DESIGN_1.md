# OOP.INTENT.DESIGN.1 — Explicit Future-Design Commitment Projection

Implemented only the read-only semantic projection. The exact BANK.2 task now
produces resolved explicit design commitments alongside unresolved human-owned
dimensions. No clarification admission, authoring, application patch, or target
implementation was run. OOP.INTENT.DETECT.2 remains unimplemented.

| Requested report item | Result |
| --- | --- |
| 1. Files changed | Twenty files, listed below. The existing OOP.INTENT.UI.1 registry policy edits were retained. |
| 2. Projection owner | `core/proposed_design_intent.py`, `project_proposed_design_intent(TaskContract, interpretation=None)`. |
| 3. Semantic source owner | Intake's existing `extract_explicit_evidence` invokes the additive bounded extractor in `core/explicit_design_evidence.py`. Evidence travels through `SemanticInterpretation`, the Preservation Gate and `TaskContract`. The projection never parses prose. |
| 4. Schema | Frozen, slotted `ProposedDesignIntent`, schema `oop_intent_design_1_v1`: status, three fingerprints, relationships, state commitments, behavior gates, explicit absences, unresolved dimensions, conflicts, evaluative evidence, overflow, reasons and immutable read-only authority flags. Stable sorted UTF-8 JSON and SHA-256 fingerprint. |
| 5. Inheritance | Explicit `SavingAccount` → `BankAccount`, with `relationship_kind=inheritance` and the exact human source span. |
| 6. Subclass state | Explicit exclusive ownership of `savingBalance` by `SavingAccount`. Combining that commitment with explicit inheritance produces `subclass_only`, excluding `BankAccount`. The derived base exclusion is labeled `inferred_semantic_interpretation` and references the inheritance evidence. |
| 7. Behavior gate | `savings functionality` requires `successful_password_verification`. No mechanism is selected. |
| 8. Explicit absence | `authentication_support` is absent according to the human's exact statement; it is not a source-inspection finding. |
| 9. Provenance | Closed vocabulary: `explicit_human`, `current_source_fact`, `inferred_semantic_interpretation`. All four BANK.2 commitments carry exact human spans and offsets. Derived exclusions and unresolved relevance carry inferred provenance. Nonhuman evidence cannot enter the explicit-human projection. |
| 10. Current versus desired | Relationships, state and gates have `desired_future_design` scope. Absence has `human_assertion_about_current_state` scope. `current_source_status=not_acquired_by_projection`; CTX.OOP keeps independently acquired source facts separately. |
| 11. Task fingerprint binding | SHA-256 binds the complete Task Contract, exact raw request, and the preserved SemanticInterpretation fields. An optional supplied interpretation must match those retained fields. Mismatched raw spans or failed preservation produce an unavailable projection. |
| 12. Identifiers | `BankAccount`, `SavingAccount`, and `savingBalance` are preserved exactly. No pluralization, case normalization, filename, package, constructor or visibility is invented. |
| 13. Unresolved authentication dimensions | Credential ownership, source, persistence, verification mechanism, failure behavior, lifecycle, and account identity. No wrong-password result, retry policy, lockout, session lifecycle, hashing or salt policy is chosen. |
| 14. Unresolved savings dimensions | Funding/transfer semantics and interest semantics are relevant because the task explicitly names savings state and password-gated savings functionality. Subclass creation timing is also unspecified. Unrelated state does not justify savings dimensions. |
| 15. Storage behavior | No persistence, database, CSV, file, memory or storage default. |
| 16. Hashing behavior | No hashing algorithm, salt, credential-security policy or related default. |
| 17. File layout | `source_layout` remains unresolved. No `SavingAccount.java` or other file location is chosen. |
| 18. Contradictions | Inheritance plus an explicit inheritance prohibition yields `conflict` and retains both evidence paths. Incompatible parents and exclusive owners also remain conflicts. No choice or authoring authority follows. |
| 19. Suggestions versus commitments | Inheritance questions and evaluative requests remain evaluative/unresolved. Composition requests and source-only declarations do not become explicit inheritance commitments. Negated or current-behavior claims do not become future gates. |
| 20. Model-call delta | Zero. The existing model adapter transports intake-owned evidence beside its existing response and repair result; prompt/schema/call count are unchanged. Deterministic replay calls no model. |
| 21. Traversal delta | Zero in projection generation. No repository handle, file lookup, source acquisition, scan or traversal is used. |
| 22. Authority delta | Zero. `authority=read_only`; write, execution and Apply flags are permanently false. |
| 23. RepairScope delta | Zero. No RepairScope construction or widening; the projection's repair-scope authority is false. |
| 24. CTX.OOP deltas | Zero production changes to 1A, 1B or 1C. Future design is not inserted into `ClassSemanticContext`. |
| 25. OOP.INTENT.UI delta | Zero production changes. No waiting session, MainApp session change or UI integration. Existing user registry policy changes are preserved. |
| 26. RepairIntent delta | Zero production changes to the RepairIntent chain. |
| 27. Performance | Recorded BANK.2 projection: 4,736 serialized bytes; 100 repetitions; median 0.361 ms, maximum 0.630 ms on this environment. This measures projection, not full intake or a model call. |
| 28. Focused tests | 67 passed, including exact BANK.2, negatives, conflicts, bounds, immutability, preservation loss/forgery, provenance, fingerprint binding, adapter/live carry, and zero side effects. |
| 29. Adjacent tests | 285 input/semantic tests passed, 1 skipped; 94 live-routing passed; 66 behavioral-evidence passed; 53 obligation-preservation passed; 104 frozen OOP/UI/RepairIntent passed. Authority checkpoint: 26 passed, 1 verified pre-existing picker-expectation failure, detailed below. |
| 30. Registry and benchmarks | One CONTROL phase registered. 267 registry/picker tests passed. Benchmark fixture check: 54 checked, 0 errors. `compileall` and `git diff --check` passed. No historical receipt repinned. |
| 31. BANK.2 projection result | Preservation passed, status `resolved`, all four explicit commitments represented, eleven unspecified dimensions retained, no defaults. Replay and full serialized evidence are in `OOP_INTENT_DESIGN_1_BANK2.json`. |
| 32. Recommended DETECT.2 seam | Consume this projection from the preserved Task Contract alongside independently acquired exact CTX.OOP source evidence. Check status, fingerprints and provenance before comparing current source with desired design. Conflict/bounded/unavailable states must remain unresolved. Do not derive admission or authoring authority from DESIGN.1. No DETECT.2 logic was implemented. |

The V1 vocabulary is deliberately bounded. Intake recognizes supported complete
declarative clauses; it does not claim general natural-language coverage. When a
design-bearing request contains additional unclassified clauses, dimensions use
`not_resolved_by_projection` instead of `unspecified`. Thus a sentence such as
"Do not persist credentials across runs" is preserved without falsely claiming
the human omitted that decision. No fallback model call is made.

Bounds are explicit: intake scans at most 100,000 characters; evidence spans are
at most 600 characters; each evidence collection holds at most 16 records; typed
evidence is at most 32,768 bytes. Projection limits are 16 relationships, 16 state
commitments, 8 gates, 8 absences, 11 unresolved dimensions, 32 conflicts, 16
evaluative spans and 65,536 serialized bytes. Overflow is reported and the
projection returns `bounded` without a partial set masquerading as complete.
Frozen constructors reject mutable collections and invalid typed values.

Files added:

- `core/explicit_design_evidence.py`
- `core/proposed_design_intent.py`
- `scripts/replay_oop_intent_design1.py`
- `tests/test_oop_intent_design1.py`
- `tests/_oop_intent_design1_maintenance.py`
- `tests/fixtures/oop_intent_design1_reversal.json`
- `docs/roadmap/OOP_INTENT_DESIGN_1.md`
- `docs/roadmap/OOP_INTENT_DESIGN_1_BANK2.json`

Files updated:

- `core/explicit_evidence.py`
- `core/semantic_waiter.py`
- `core/semantic_waiter_adapter.py`
- `core/live_task_shape.py`
- `core/input_understanding.py`
- `core/task_contract.py`
- `core/requirement_preservation.py`
- `tests/test_input_understanding.py`
- `tests/test_phase_registry.py`
- `tests/test_phase_picker.py`
- `tests/_oop_intent_ui1_maintenance.py`
- `docs/roadmap/phase_registry.json`

The only failing executed test is
`tests/test_human_authority_branch_checkpoint.py::test_real_registry_marks_human_close_complete_and_picker_recommends_adopt_model_1`,
line 587. It expects `UX.RUN.1`; the starting working tree, including the user's
pre-existing OOP.INTENT.UI.1 policy edits, already selects `DOGFOOD.1B`. Pure HEAD
has no recommendation. Adding the completed DESIGN.1 phase does not cause this
failure. The unrelated assertion was not changed.

Distinct executed results: **962 passed, 1 skipped, 1 pre-existing failure**.
No full-suite claim is made. The eight additive transport/test seams also
reconstruct byte-for-byte to the unchanged DATA.UNDO.1 historical pins, including
the existing mixed newline convention. Historical receipts themselves were not
edited.

Reproduce the semantic-only replay from the repository root:

```powershell
python scripts/replay_oop_intent_design1.py
```

Explicit answers: inheritance **yes**; subclass-only `savingBalance` **yes**;
password-verification requirement without a mechanism **yes**; current versus
desired distinction **yes**; unspecified authentication decisions retained
**yes**. Invented persistence/storage **no**; invented hashing/security policy
**no**; chosen savings-transfer semantics **no**; widened edit scope **no**;
additional model call **no**.
