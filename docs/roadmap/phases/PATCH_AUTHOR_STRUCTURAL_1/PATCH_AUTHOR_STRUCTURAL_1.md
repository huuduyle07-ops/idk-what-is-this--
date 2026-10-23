# PATCH.AUTHOR.STRUCTURAL.1

Implemented with inherited verification warnings. A freshly reconstructed
admission can be presented to one injected structural author and normalized to
one immutable multi-target Java draft. Every candidate operation is bounded by
the admitted operation and definition set. No materialization or Apply layer is
introduced. The real BANK.2 approval and session remain untouched.

1. **Files changed.** Added `core/structural_patch_author.py`,
   `core/structural_java.py`, `tests/test_patch_author_structural1.py`,
   `scripts/replay_patch_author_structural1.py`, this report,
   `docs/roadmap/PATCH_AUTHOR_STRUCTURAL_1_BANK2.json`,
   `tests/_patch_author_structural1_maintenance.py`, and
   `tests/fixtures/patch_author_structural1_reversal.json`. Attributed
   bookkeeping changes only: `docs/roadmap/phase_registry.json`,
   `tests/test_phase_registry.py`, `tests/test_phase_picker.py`, and
   `tests/_patch_scope_admit1_maintenance.py`. Other entry changes are preserved.
2. **Structural author owner.** `StructuralAuthorInvocation` in
   `core/structural_patch_author.py` owns the read-only integration. Its injected
   `ReadOnlyStructuralAuthor.author(context)` supplies implementation text.
   The harness owns paths, admission, definitions, freshness and containment.
3. **Candidate schema.** `StructuralPatchCandidate`, schema
   `patch_author_structural_1_v1`, phase `PATCH.AUTHOR.STRUCTURAL.1`, status
   `structural_patch_candidate`. Frozen dataclasses and transitive immutable
   field checks bind admission, PLAN, task/design/P1/approval/ceiling lineage,
   repository evidence, source bindings, new-path absence witnesses and operations.
4. **Admission revalidation.** Before the prompt and after the response,
   frozen `validate_admitted_structural_authoring_scope` reconstructs ADMIT,
   PLAN and explicit human approval from supplied typed lineage. Fingerprints
   and serialized labels cannot substitute for reconstruction.
5. **Fresh acquisition.** The I/O facade calls frozen
   `acquire_structural_admission_evidence` at both gates. Only exact named
   targets, their ancestor evidence and the two repository policy files are
   acquired. An old caller-supplied path witness is refused by the facade.
   Existing file hashes must match their bound source/declaration buffers.
6. **Author context.** A bounded JSON prompt carries original task meaning,
   effective commitments, PLAN decisions, contracts, admitted operations,
   exact definitions/paths and the closed output schema. Maximum context size
   is 128,000 bytes; output is limited to 96,000 bytes and 64 operations.
7. **READ versus EDIT.** `[READ-ONLY SUPPORT]` contains declaration evidence
   and needed exact source context. `[AUTHORABLE STRUCTURE]` enumerates the
   only operations and definition allowances. Showing a whole class as context
   grants no class-body replacement or neighbor editing permission.
8. **Provider/call policy.** One retained invocation object has an atomic
   one-shot budget. No retry/reset/resample or reviewer is present. Calls need
   literal `author_call_authorized=True`. Provider failures remain typed and
   consume the attempt. `model_backed` explicitly controls model-call accounting;
   synthetic providers are separate from actual live model activity. A caller
   must retain the invocation for its attempt; there is no persistent session
   authority store or global provider dispatcher.
9. **Response envelope.** Exactly `candidate`, finite confidence in [0,1],
   boolean `needs_escalation`, and `escalation_reason`. Duplicate JSON keys,
   extra fields and malformed/unbounded values fail closed. Confidence is
   excluded from candidate identity and cannot grant authority.
10. **Operation vocabulary.** Only `insert_member`, `remove_declaration`,
    `draft_new_file`, and `insert_nested_class`. An admission containing another
    operation, including ADMIT's reserved modification operation, abstains with
    `unsupported_structural_operation` before any author call.
11. **Insert-member representation.** Exact operation, physical path, class
    owner, sorted PLAN definition IDs and generated declaration text. The
    freshly reconstructed admission owns the insertion-container byte boundary.
    No replacement of the existing file or class is represented.
12. **Removal representation.** Exact admitted `DeclarationBinding` and
    `removal_intent=True`, with source text null. Model-selected byte spans or
    replacement neighbors are rejected. The admission retains the exact span.
13. **New-file representation.** Complete proposed Java text for the exact
    absent path. Package, top-level identity, parent, signatures, visibility
    and all contained definitions are checked in memory. The file is not created.
14. **Nested representation.** An entire admitted nested class declaration,
    bound through admission to its exact existing parent insertion container.
    Package/import changes and separate new-file operations are forbidden.
15. **Generated Java parsing.** Tree-sitter parses supplied source buffers
    in memory. Inserted members use a synthetic class wrapper. Syntax errors,
    ambiguous Unicode preprocessing, extra top-level/local/anonymous classes,
    initializer blocks, lambdas, unsupported annotations/modifiers and other
    unplanned declaration structures fail closed. There is no javac invocation.
16. **Definition identity.** Parsed owner, kind, name, type, ordered parameter
    types/names, visibility and parent match exact PLAN definitions. Every
    generated definition has one allowance; merely claiming an ID is insufficient.
17. **Semantic contracts.** Necessary AST witnesses check subclass credential
    ownership, in-memory equality verification of operation input, compatible
    super construction, encapsulated base debit, successful debit before exact
    savings credit, and planned simple interest on savingBalance. New fee,
    limit, retry, lockout, persistence/networking and timing shapes are rejected.
    Only a referenced `java.util.Objects` equality import is supported in V1.
    Unrecognized implementations fail closed; this is deliberately not a
    compiler, full behavior proof, or general Java semantic verifier. The
    fixture reads console input for the frozen interest signature without
    inventing another parameter/field; runtime input availability is unverified.
18. **Multi-target atomicity.** The successful candidate accounts for every
    admitted operation and every generated definition. Missing debit insertion,
    missing subclass content or missing required removal yields
    `author_output_incomplete`. Duplicate operations are rejected.
19. **Read-only support protection.** Constructor, balance, deposit, withdraw
    and preserved saving declarations are usable context only. Extra generated
    edits to any of them fail exact operation/definition containment.
20. **Unused ceiling protection.** Only admitted selected PLAN definitions
    enter the authorable prompt. The nested/private-constructor fixture proves
    an approved but unused constructor MAY cannot be recovered by the author.
21. **Test-file protection.** `SavingAccountBehaviorTest.java` remains a PLAN
    validation-evidence need. It has no candidate operation or test-write grant;
    generated test files are rejected by exact-path containment.
22. **Command handling.** There is no command field or executable tool adapter.
    Shell/javac/file-write payloads fail schema or Java parsing. Command/tool
    instructions in generated comments are also rejected. Infrastructure calls
    are restricted by parsed receivers/types and the admitted contract vocabulary.
23. **Escalation.** Bounded reasons: `missing_context`,
    `admitted_scope_insufficient`, `semantic_clarification_required`,
    `unsupported_structural_operation`, `author_output_invalid`, or
    `other_bounded_reason`. At most eight bounded requested-capability strings
    carry information only. No new global human clarification type is introduced.
24. **Abstention.** A null candidate without escalation is `author_abstained`.
    Candidate plus escalation is quarantined as `author_output_invalid`.
25. **Compatibility fixture.** Valid debit insertion and admitted subclass
    file draft; base saving remains read-only and absent from candidate edits.
26. **Subclass-only fixture.** Valid exact base-saving removal, debit insertion
    and admitted subclass file draft, represented atomically.
27. **Specialization fixture.** Valid subclass saving specialization and debit
    insertion; base saving's existing common contract remains read-only.
28. **Nested fixture.** Valid static nested SavingAccount and debit insertion
    inside bank.java; no SavingAccount.java operation, no file creation and
    unused constructor MAY authority unrecoverable.
29. **Stale source.** Changed on-disk source with an old supplied buffer yields
    `reacquisition_required` and zero pre-call author invocations. A post-call
    change also rejects the candidate without modifying historical evidence.
30. **Pre-call path collision.** An occupied admitted new-file path yields
    `admission_conflict_existing_path`; author calls are zero.
31. **Post-call path collision.** Newly acquired post-response evidence detects
    occupancy and returns `admission_conflict_existing_path`. Occupied bytes
    are preserved. Historical candidate validation independently detects this too.
32. **Outside-scope output.** Wrong path/owner/definition IDs, extra class/field/
    method/helper, altered balance visibility, read-only edits, wrong parent or
    signature and an unadmitted test fail `author_output_outside_admitted_scope`.
33. **Missing-operation output.** Required structural operations cannot be
    silently omitted. Required subclass-only removal is mandatory.
34. **Semantic-drift output.** Bypassed verification, stored-password
    self-authentication, constant comparison/input, combined limit predicates,
    incorrect debit arguments, fee credit and base-balance interest are rejected.
35. **Authority escalation.** Literal false is required for all carried write,
    execution, Apply and creation flags. Model escalation claims fail
    `author_output_authority_escalation`; changing candidate metadata also fails
    independent canonical reconstruction.
36. **Fingerprint/idempotency.** Canonical sorted JSON and SHA-256 exclude
    latency, call provenance and confidence. Operation/ID transport ordering
    and CRLF/LF normalization are canonicalized. Identical output and admission
    produce identical fingerprints; five repeated samples per layout prove it.
37. **Candidate.** Four non-null synthetic immutable candidates appear in the
    replay JSON. The pure seam has zero author/model calls. The separately
    tested facade exercises one injected synthetic author per eligible attempt.
38. **Source mutation.** Zero application-source mutation. No whole-file byte
    patch, materialized source, on-disk patch or filesystem writer is produced.
39. **Write/Apply authority.** Candidate/result authority is `candidate_only`.
    `write_authority`, `filesystem_write_authority`,
    `filesystem_file_creation_authority`, `execution_authorized` and
    `apply_authority` are literal false; patch empty; both repair-scope deltas zero.
40. **Model calls.** Actual live model calls during implementation/proof: zero.
    Explicit model-backed synthetic failure tests only check counter accounting.
41. **Author calls.** Live external author calls: zero. Injected facade tests
    prove one-call success/failure, zero-call stale gates and refusal of a
    second attempt on the retained invocation. Normalization/replay make zero calls.
42. **Repository traversal.** Runtime traversal delta zero. Guards prohibit
    walk/scandir/listdir. Named-path acquisition is read/stat only; AST inspection
    uses bounded in-memory source, not a repository inventory.
43. **Real BANK.2 consumption.** None. Fixtures build synthetic typed approval,
    PLAN and admission lineage. No real waiting session/action is read or consumed.
44. **Source/session integrity.** Twenty-four protected artifacts match recorded
    hashes, including frozen core modules, historical receipts, real bank.java/
    MainApp.java and web/sessions.json. SavingAccount.java remains absent in
    both the workspace root and the real Java repository. All four shared-file
    changes reverse exactly to their dirty entry bytes using this phase's new
    receipt; historical receipts are never repinned.
45. **Performance.** Five synthetic samples per layout measure fresh ADMIT
    reconstruction, context projection, normalization, parsing, containment and
    fingerprinting separately. Provider latency is separately zero in this pure
    replay; the facade measures its injected provider call independently. The
    table below covers normalization plus context projection and excludes the
    separately exercised future-validator pass and filesystem acquisition.
46. **Focused tests.** 101 passed (99 matrix cases and two final state-shadow
    regressions). Final instrumentation/comment handling also
    passed an 11-test selected recheck. Positives include packaged source,
    deterministic normalization, exact removals, all layouts and immutable
    transport. Required negative governance cases are covered with synthetic
    output and isolated filesystem collision/source-change fixtures.
47. **Adjacent tests.** ADMIT/PLAN/APPROVE/REFRESH/RECHECK/EXPAND: 339 passed.
    Frozen author scope/span, basis scope, human authority/Apply and PATCH.MINIMAL:
    401 passed and 12 reproduced inherited failures. Ten failures occurred in
    the pre-change baseline; the other two reproduced with read-only entry
    snapshot substitution. Final failing node IDs equal the baseline union.
    Unchanged runner/control/pipeline attribution, inconclusive verification
    and an earlier picker expectation account for these warnings. Logs and
    reproduction script are in `.tmp/structural1/`; no frozen assertion is weakened.
48. **Registry/benchmarks.** One completed PATCH/AUTHOR slice in CONTROL:
    215 phases, 33 CONTROL entries, 211 history entries. Registry/picker and
    repository/ignore/identity policy: 345 passed, two inherited skips.
    Compileall and git diff --check pass. Benchmark check: 54 cases, zero errors.
    Required final suites total 1,186 passed, 12 inherited failures, two skips.
    Registry's conservative `writes_real_repo` implementation metadata is
    separate from the runtime candidate's literal-false write authority.
49. **First remaining blocker.**
    `STRUCTURAL_CANDIDATE_MATERIALIZATION_NOT_IMPLEMENTED`. Any later consumer
    must reacquire source/path absence and reconstruct admission/plan/semantics/
    repository lineage before materialization, validation execution or Apply.
    This phase implements none of those downstream effects.

| Explicit question | Answer |
| --- | --- |
| Is every generated structural edit inside freshly validated admitted scope? | Yes, for every successful candidate. |
| Can read-only support be edited because the model saw it? | No. |
| Can the author recover an unused MAY target? | No. |
| Can it draft SavingAccount.java without creating it? | Yes. |
| Is new-file source limited to admitted definitions? | Yes, with exact package and bounded referenced import syntax. |
| Can compatibility remove BankAccount.saving? | No. |
| Can subclass-only omit its required saving transition? | No; output is incomplete. |
| Can specialization destroy its base contract? | No; the base contract is read-only. |
| Does a candidate contain write/Apply authority? | No; all effect-authority fields are literal false. |
| Does candidate generation execute validation commands? | No; Java validation remains downstream. |
| Can a future consumer independently revalidate without UI/session state? | Yes, through the pure validator with freshly acquired evidence and typed lineage. |

Median milliseconds, five samples per synthetic layout. Maxima and complete
candidate/lineage payloads are recorded in the replay JSON.

| Stage | Compatibility | Subclass only | Specialization | Nested |
| --- | ---: | ---: | ---: | ---: |
| Fresh ADMIT reconstruction | 686.4713 | 696.1492 | 665.1971 | 645.4870 |
| Context projection | 3.2125 | 3.3315 | 3.1797 | 3.6776 |
| Provider latency | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Normalization | 0.1338 | 0.1714 | 0.1145 | 0.1249 |
| Java structural parsing | 2.7473 | 2.8354 | 2.7105 | 2.7039 |
| Scope/contract containment | 2.8534 | 3.3586 | 2.7774 | 3.3167 |
| Fingerprint | 2.3229 | 2.9405 | 2.0427 | 2.5571 |
| Total deterministic overhead | 698.4712 | 708.7931 | 676.4765 | 658.2367 |

Replay command: `python scripts/replay_patch_author_structural1.py --repetitions 5
--output docs/roadmap/PATCH_AUTHOR_STRUCTURAL_1_BANK2.json`. It writes the
explicitly requested governance artifact only; candidate Java remains in memory.
The replay includes four positive layouts and eleven typed negative outcomes.
