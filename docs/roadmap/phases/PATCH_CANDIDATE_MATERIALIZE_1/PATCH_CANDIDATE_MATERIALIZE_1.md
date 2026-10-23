# PATCH.CANDIDATE.MATERIALIZE.1

The deterministic harness composes one freshly revalidated
`StructuralPatchCandidate` into one immutable virtual post-state. Exact virtual
file bytes, hashes, operation lineage and preservation witnesses are authoritative.
The diff projection is for display only. Neither the candidate nor its
materialization grants source-write, file-creation, execution or Apply authority.

This phase implements materialization only. The frozen author code and semantic
plan remain inputs. Real BANK.2 approval/candidate state and Java repository
files are not consumed or changed. Implementation governance checks use synthetic
frozen AUTHOR.STRUCTURAL.1 candidates and isolated fixtures. Those checks do not
execute javac, java or behavior tests against virtual candidate code; materializer
runtime has no test runner or subprocess path.

1. **Files changed.** Added `core/structural_candidate_materialization.py`,
   `tests/test_patch_candidate_materialize1.py`,
   `scripts/replay_patch_candidate_materialize1.py`, this report,
   `docs/roadmap/PATCH_CANDIDATE_MATERIALIZE_1_SYNTHETIC.json`,
   `tests/_patch_candidate_materialize1_maintenance.py`, and
   `tests/fixtures/patch_candidate_materialize1_reversal.json`. Narrow bookkeeping
   changes: `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`,
   `tests/test_phase_picker.py`, and
   `tests/_patch_author_structural1_maintenance.py`. Existing dirty work is retained.
2. **Materializer owner.** `core/structural_candidate_materialization.py` owns
   deterministic composition. `materialize_structural_candidate` exposes the
   fresh-evidence gate; `validate_materialized_structural_candidate` independently
   reconstructs the same canonical virtual result for downstream callers.
3. **Schema.** `MaterializedStructuralCandidate`, schema
   `patch_candidate_materialize_1_v1`, phase `PATCH.CANDIDATE.MATERIALIZE.1`,
   status `materialized_structural_candidate`, is a frozen, recursively
   immutable representation binding phase/schema/status, original candidate,
   admission/PLAN/approval/semantic lineage, repository identity, before/after
   file evidence, virtual file records, applied operations, preserved support,
   display-only diff and materialization fingerprint. Authority is
   `virtual_post_state_only`. Records are `VirtualStructuralFile`,
   `AppliedStructuralOperation`, `ByteEditEvent`, `BytePreservationSegment`,
   `SupportingDeclarationProof`, and `UnchangedSupportingFile`.
4. **Candidate revalidation.** Frozen `validate_structural_patch_candidate`
   reconstructs admission and candidate against fresh inputs before composition.
   Stored status, fingerprint and UI/session labels cannot replace that gate.
   No second author/model call occurs.
5. **Fresh path/source acquisition.** Only exact bound target and support paths
   and the frozen admission policy evidence are reacquired when
   `repository_root` selects the read-only facade. It discards old supplied path
   witnesses and reacquires source/path evidence before validation and again
   immediately before composition. The pure seam requires the caller to supply
   newly acquired evidence. Existing bytes must
   match candidate/admission source bindings. Every proposed new-file path must
   still be absent. No repository inventory or traversal is performed.
6. **Source encoding policy.** V1 uses the project's deterministic UTF-8 Java
   buffers; strict decoding/encoding must reproduce identical bytes. NUL bytes
   are rejected. A UTF-8 BOM, if already admitted, remains untouched. Unsupported or
   unreadable source encoding fails closed with
   `materialization_unsupported_source_encoding`. No encoding guess is made.
7. **Line-ending policy.** Existing target insertions render canonical candidate
   newlines into that exact target's uniform LF or CRLF convention. Existing
   untouched bytes are not normalized. Mixed LF/CRLF or bare CR conventions fail
   closed with `materialization_unsupported_line_endings`. Newline-free targets
   deterministically use LF. New-file virtual bytes retain the frozen candidate's
   canonical LF convention; style is never obtained by repository scanning.
8. **Event model.** Immutable `remove [start,end)` and `insert at offset` events
   refer to one immutable original buffer. Event validation rejects overlapping
   removals, insertion inside a removed interval and ambiguous ordering. Events
   are composed once; mutated intermediate source is not reparsed as authority.
9. **Insertion anchor policy.** The harness derives the original exact class
   closing-brace anchor from the admission-owned class-body container. The
   closing-brace bytes are retained. Applied-operation records expose the anchor
   offset. Author text supplies no coordinates or insertion neighbor.
10. **Removal policy.** Removal uses the admission/candidate-owned exact
    declaration byte span and removes exactly those bytes. Comments or whitespace
    outside that span remain. Extra blank lines are acceptable; no cleanup
    widens the removal.
11. **Same-file operation composition.** All operations for one existing file
    share the original coordinate system. Subclass-only saving removal and debit
    insertion compose into one virtual `bank.java` after-state. Multiple
    insertions into one class use PLAN/admitted definition order, independent of
    JSON transport order.
12. **Multi-file atomicity.** Every file, operation and structural post-check
    must succeed before one materialized candidate is returned. Failure exposes
    no authoritative partial virtual file-set. Top-level compatibility,
    subclass-only and specialization layouts bind both virtual files to one
    materialization identity.
13. **New-file absent-to-virtual representation.** `draft_new_file` has
    `before_state=absent`, `before_sha256=null`, `before_size=null` and no fake
    empty before bytes.
    Its after-state is the exact candidate source encoded as virtual bytes.
    File-creation authority remains false.
14. **Virtual file schema.** Each changed record binds path, before-state,
    before/after SHA-256, before/after sizes, operation identities and exact
    virtual `after_source` with an exact UTF-8 `after_bytes` property. Existing
    records also bind exact source context;
    `physical_write_authority=false` is mandatory.
15. **Before/after hashes.** Existing hashes cover the exact original and
    composed bytes. New-file before hash is null; after hash is SHA-256 of exact
    generated bytes. Canonical materialization identity additionally covers
    operation and upstream lineage, so equal source bytes cannot hide a changed
    approval, plan or candidate binding.
16. **Byte-preservation proof.** Unmodified original intervals map to exact
    after-state intervals with equal bytes and hashes. Removed spans and inserted
    payloads are the only event-attributed changes. Preservation checks cover
    the whole original buffer outside removals, including indentation, comments,
    braces and line endings.
17. **Diff preview.** A deterministic unified diff projection supports review.
    It has display authority only and does not overload the old `patch` field.
    New-file previews use `/dev/null` only as a display convention for absence.
    Bounds are 64 named/changed files, 512,000 bytes per file, 2,000,000 total
    named/virtual bytes and 2,000,000 diff bytes. The independent validator caps
    supplied canonical materialization claims at 16,000,000 UTF-8 bytes. Bounds
    fail closed without truncating canonical content.
18. **Java post-parse.** Existing structural Java/tree-sitter parsing examines
    every composed changed source buffer in memory. Syntax/structure failures
    reject composition. This phase provides no javac or runtime correctness
    claim and never reserializes an AST.
19. **Structural post-check.** Removed declarations must be absent, inserted
    definitions present exactly once, and new-file definitions match admitted
    package, top-level identity, inheritance and definition ceiling. Retained
    neighbor identities remain, and composition may introduce no unplanned
    definitions.
20. **Duplicate protection.** Duplicate new-file targets, overlapping event
    targets and duplicate resulting Java definition identity fail closed.
    No rename, deduplication or heuristic event reorder repairs a conflict.
21. **Read-only support preservation.** Exact support source hashes and known
    declaration spans remain bound and unchanged. Unedited declarations in a
    changed file are mapped through the composed event sequence and checked
    byte-for-byte in `exact_declaration` mode. An edited class container uses
    `container_surviving_bytes` to prove retained original bytes without claiming
    its whole span stayed unchanged after authorized child edits. Read-only
    support evidence never becomes an edit.
22. **Compatibility output.** One virtual `bank.java` contains the exact debit
    insertion while existing saving bytes remain. One virtual
    `SavingAccount.java` contains the exact authored draft. Neither is written.
23. **Subclass-only output.** One virtual `bank.java` has the exact admitted
    saving declaration removed and the debit declaration inserted. Other
    declaration bytes remain. Virtual `SavingAccount.java` retains the authored
    subclass draft.
24. **Specialization output.** One virtual `bank.java` contains the debit
    insertion and preserved base saving bytes. One virtual `SavingAccount.java`
    retains the admitted specialized savings implementation.
25. **Nested output.** One virtual `bank.java` contains both debit insertion and
    the admitted nested class. No separate virtual `SavingAccount.java` exists.
26. **CRLF behavior.** Canonical LF declaration text renders as CRLF only for
    insertion into a uniformly CRLF target. Original bytes remain untouched.
    New-file draft text continues using its own canonical convention.
27. **Collision handling.** A new-file target that appears after authoring is
    rejected before authoritative materialization with
    `materialization_conflict_existing_path`. No overwrite projection occurs.
28. **Stale-source handling.** Fresh existing bytes differing from their exact
    bindings yield `reacquisition_required`. Historical candidate evidence is
    preserved; no buffer repair or automatic rebinding occurs.
29. **Tampered candidate.** Changed declaration text, operation, definition ID,
    source/lineage fingerprint or authority metadata is rejected by frozen
    candidate validation before composition.
30. **Overlapping-event behavior.** Synthetic overlapping removals and
    insertion/removal ambiguity produce
    `materialization_structural_conflict`. No partial result survives.
31. **Candidate semantic preservation.** Authored declaration text is preserved
    except deterministic newline rendering and composition delimiters. The
    frozen fixture's `System.console().readLine()` remains. No API, helper,
    import, syntax repair, semantic policy or warning removal is introduced.
32. **Authority.** `authority=virtual_post_state_only`; `write_authority`,
    `filesystem_write_authority`, `filesystem_file_creation_authority`,
    `execution_authorized`, `apply_authority` and `auto_apply` are all false.
    Diff projections grant display authority only.
33. **Source mutation.** Materializer source mutation is zero. `bank.java`,
    `SavingAccount.java`, `MainApp.java` and real BANK.2 state remain unchanged.
    Isolated test setup may create fixture files before guarded materialization;
    fixture creation is not materializer authority.
34. **Execution.** Runtime launches no shell/subprocess, javac, java, tests,
    formatter, IDE cleanup or import organizer. Governance commands verify the
    Python implementation and frozen boundaries separately from candidate code.
35. **Model/author calls.** Both are zero. The frozen candidate is input evidence,
    and materialization is a pure deterministic harness operation.
36. **Repository traversal.** Zero. No `os.walk`, `scandir`, `listdir`, inventory
    refresh or temporary repository clone is used.
37. **Idempotency.** The same freshly validated candidate and exact source/path
    evidence yield identical virtual bytes, after hashes, canonical operation
    records and materialization fingerprint. Timing measurements are excluded
    from identity.
38. **Stale after materialization.** Materialized evidence stays immutable.
    Independent validation reacquires exact evidence when `repository_root` is
    supplied, or requires fresh caller evidence through its pure seam. It
    revalidates the original candidate and recomposes the canonical result.
    Later source changes or new-path occupancy reject the historical result.
39. **Performance.** Timings distinguish fresh candidate validation, exact
    evidence acquisition, event construction, byte composition, Java post-parse,
    structural post-check, diff projection, fingerprint construction and total
    deterministic overhead. Synthetic replay reports repeated timings and
    confirms equal fingerprints; timings do not grant authority.
40. **Focused tests.** The matrix covers compatibility, subclass-only,
    specialization, nested, LF/CRLF, package identity, multiple insertion order,
    immutable/idempotent results, collision/staleness/tampering/lineage failures,
    event conflicts, duplicate targets/definitions, encoding/newline failures,
    malformed composition and authority escalation. All 73 focused tests pass.
    Measured results below
    distinguish implementation verification from candidate execution.
41. **Adjacent tests.** Requested governance covers AUTHOR.STRUCTURAL, ADMIT,
    PLAN/APPROVE/REFRESH/RECHECK/EXPAND, frozen AUTHOR.SCOPE/SPAN, PATCH.MINIMAL,
    human authority/Apply and repository/path policy. The broader frozen run
    reports 502 passed, 2 skipped and 14 failures. Twelve exact failures were
    already reproduced in the prior frozen AUTHOR baseline; one additional
    historical picker expectation is disproved by the exact entry registry;
    one unchanged-code performance assertion narrowly misses its timing cap in
    that concurrent run and passes an isolated rerun. AUTHOR.STRUCTURAL, ADMIT,
    PLAN/APPROVE/REFRESH/RECHECK/EXPAND and registry/picker verification reports
    723 passed. Historical assertions and receipts remain unchanged. Direct named-file
    reader/repository identity checks additionally report 133 passed, 5 skipped.
42. **Registry/benchmarks.** Registered one narrow PATCH/CANDIDATE phase in
    CONTROL, with no model/network/merge/repository-write grant. Registry counts
    are 216 phases, 34 CONTROL and 212 complete/history; picker recommendation
    remains DOGFOOD.1B. A new exact bookkeeping reversal restores entry bytes
    before older frozen checks. Historical receipt hashes are not repinned.
    The synthetic JSON is explicitly registered as an allowed/expected artifact.
    After that final metadata addition, three changed registry/picker/reversal
    cases pass and every new receipt still reconstructs exact entry bytes.
    Compileall and `git diff --check` pass. Benchmarks `--check` reports 54 checked
    cases and zero errors. Concrete replay results are recorded below.
43. **First remaining blocker.**
    `STRUCTURAL_CANDIDATE_VALIDATION_NOT_IMPLEMENTED`: compile/behavior
    validation of the independently revalidated virtual file-set is the next
    phase. Apply remains frozen and unimplemented here.

## Explicit answers

| Question | Answer |
| --- | --- |
| Can the structural candidate be exact virtual resulting file bytes? | Yes; one immutable atomic virtual file-set binds content, hashes and lineage. |
| Are untouched existing bytes preserved exactly? | Yes; preservation witnesses and support/declaration checks prove it. |
| Does the harness own insertion locations? | Yes; original admitted class closing braces supply anchors. |
| Can remove + insert compose safely in one existing file? | Yes; immutable original-coordinate events compose once or fail atomically. |
| Is a new file absent-to-virtual rather than an empty existing file? | Yes; absent before-state, null before hash, exact virtual after bytes. |
| Is SavingAccount.java still not created? | Yes; materialization has no physical file-creation authority. |
| Does materialization repair or reinterpret author code? | No; candidate implementation choices and source text stay frozen. |
| Does it execute javac/tests? | No; runtime has no execution path. Separate governance runs verify implementation only. |
| Is the virtual file-set independently revalidatable? | Yes; fresh original candidate validation and canonical recomposition gate use. |
| Does it grant write or Apply authority? | No; every write/execution/Apply authority flag remains false. |

## Implementation verification commands

These commands are governance for the implementation. They are never executed by
the materializer and do not compile or behavior-test virtual candidate source.

```text
python -m pytest tests/test_patch_candidate_materialize1.py -q
python -m pytest tests/test_patch_author_structural1.py tests/test_patch_scope_admit1.py -q
python -m pytest tests/test_patch_scope_plan1.py tests/test_patch_scope_approve1.py tests/test_patch_scope_refresh1.py tests/test_patch_scope_recheck1.py tests/test_patch_scope_expand1.py -q
python -m pytest tests/test_patch_author_scope1.py tests/test_patch_author_span1.py tests/test_patch_basis_scope1.py tests/test_human_authority_branch_checkpoint.py tests/test_human_apply_authorization.py -q
python -m pytest tests/test_patch_minimal_live.py tests/test_patch_minimal_novelty_live.py tests/test_benchmark_patch_minimality.py tests/test_repo_ignore_policy.py tests/test_repository_inventory.py tests/test_canonical_repository_identity.py tests/test_phase_registry.py tests/test_phase_picker.py -q
python -m compileall -q core web tests scripts benchmarks
python benchmarks/run_benchmarks.py --check
git diff --check
python scripts/replay_patch_candidate_materialize1.py --repetitions 5
```

## Measured results

Implemented with inherited governance warnings. Focused verification reports
73 passed: the initial 68 cases completed in 163.93 seconds and five final
regressions completed in 0.83 seconds. The broader frozen suite reports
502 passed, 2 skipped, 14 failures and 25 warnings in 150.85 seconds. Additional
direct named-file reader and repository identity checks report 133 passed and
5 skipped in 3.77 seconds. AUTHOR.STRUCTURAL/ADMIT/PLAN/APPROVE/REFRESH/RECHECK/
EXPAND and registry/picker verification reports 723 passed and 8 warnings in
688.97 seconds, with no failures. Warnings cover deprecation and unavailable
pytest-cache creation; later runs disable the cache provider. Following the
final synthetic-artifact metadata registration, three affected registry/picker/
new-receipt cases pass in 1.81 seconds. The isolated binding-context timing
rerun passes in 9.35 seconds. Thus 13 inherited failure nodes remain after the
timing assertion passes independently; the original broader-run result remains
reported without rewriting its failure count.

Compileall passes across `core web tests scripts benchmarks`, including a final
check after the latest source/test edits. `git diff --check` passes after the
latest changes. Benchmark `--check` validates 54 cases with zero errors.

The [synthetic replay](PATCH_CANDIDATE_MATERIALIZE_1_SYNTHETIC.json) contains
five repetitions of seven pure scenarios, ten typed negatives and an isolated
read-only facade case. Every repetition has identical virtual bytes/hashes and
materialization fingerprint for its own candidate/evidence. The facade reports
unchanged original source bytes, no newly created file and zero traversal.
Real BANK.2 approval/candidate and MainApp/session state are not consumed.
Runtime model/author calls, source writes, file creation, execution and Apply
remain zero; no virtual source is compiled or behavior-tested.

Each non-nested scenario contains two virtual files. Every new-file record has
`before_state=absent`, `before_size=null`, `before_sha256=null`; the exact
`after_source.encode("utf-8")` supplies virtual bytes. Nested materialization
contains only virtual `bank.java`.

| Synthetic scenario | Virtual files | Existing bank bytes, before → after | New-file virtual bytes |
| --- | ---: | ---: | ---: |
| Compatibility | 2 | 270 → 401 | 746 |
| Subclass only | 2 | 270 → 346 | 746 |
| Specialization | 2 | 270 → 401 | 731 |
| Nested | 1 | 278 → 1,164 | No new file |
| LF | 2 | 270 → 401 | 746 |
| CRLF | 2 | 276 → 412 | 746, canonical LF retained |
| Packaged `edu/` | 2 | 283 → 414 | 759 |

The compatibility/subclass-only/LF/CRLF new-file bytes have SHA-256
`3460262bfa3d9ece43c5d8df97f76a08fd83cbb7ad224557a837c1ee6ef56588`.
Specialization's authored new-file bytes have SHA-256
`d74892acb1dd0a278d37daffc55c9f66602ef1512a6783eed9dd4dbf9a2e3598`.
Packaged new-file bytes have SHA-256
`f04666f2b7a33236fbee8de53b279d71154b734d72a202a3ee3a28045dd94fd9`.
All existing before/after hashes, preservation spans, applied anchor offsets,
rendered declarations, complete virtual sources and display-only diffs are in
the replay artifact. These are synthetic outputs, not real BANK.2 receipts.

Milliseconds, five samples. Pure acquisition measures supplied exact evidence
checks; facade acquisition measures actual named-path reads before/after the
frozen validator. The two samples exercise separate runs and are not a controlled
performance comparison. Stage medians need not sum to the total median.

| Stage | Compatibility pure median / max ms | Isolated facade median / max ms |
| --- | ---: | ---: |
| Fresh candidate revalidation | 394.2117 / 611.6075 | 633.3239 / 717.0342 |
| Exact evidence acquisition | 0.0222 / 0.0460 | 14.8577 / 17.4690 |
| Event construction | 2.0939 / 2.6132 | 4.2569 / 5.3330 |
| Byte composition | 0.1091 / 0.1404 | 0.1904 / 0.2028 |
| Java post-parse | 0.4586 / 0.6799 | 0.7717 / 0.9305 |
| Structural post-check | 2.5381 / 4.2228 | 4.1311 / 5.7903 |
| Diff projection | 0.1337 / 0.2466 | 0.2392 / 0.2401 |
| Fingerprint construction | 0.5965 / 0.8000 | 1.0169 / 3.1936 |
| Total deterministic overhead | 401.8901 / 617.6172 | 666.6136 / 742.6880 |

| Pure scenario | Total median ms | Total maximum ms |
| --- | ---: | ---: |
| Compatibility | 401.8901 | 617.6172 |
| Subclass only | 830.4249 | 1,905.0516 |
| Specialization | 777.5977 | 1,013.4999 |
| Nested | 782.1647 | 914.0284 |
| LF | 840.1911 | 985.7393 |
| CRLF | 750.3535 | 810.1695 |
| Packaged | 780.6338 | 880.9069 |

Fresh frozen candidate/admission/PLAN reconstruction dominates measured
overhead. Composition, Java parsing and preservation checks are separately
instrumented; no timing data becomes fingerprint input or execution authority.

All ten negative replay cases return no authoritative virtual candidate:
occupied new path → `materialization_conflict_existing_path`; stale source →
`reacquisition_required`; overlapping removals or insertion inside removed bytes
→ `materialization_structural_conflict`; duplicate new-file path or altered
generated declaration → `author_output_outside_admitted_scope`; altered Apply
authority → `author_output_authority_escalation`; altered candidate authority,
fingerprint or implementation-plan lineage → `candidate_stale`.

## Frozen baseline attribution

A read-only audit verifies every new reversal record's current/post SHA-256 and
reconstructed entry SHA-256. All four records match exactly. The reconstructed
entry registry has 215 phases and already recommends `DOGFOOD.1B`, proving this
phase did not change the earlier picker recommendation. All 24 protected
artifacts in `.tmp/structural1/protected.json` remain byte-identical to the prior
frozen AUTHOR proof, including `core/pipeline.py`, `web/runner.py`, real Java
bank/MainApp files, sessions and historical receipts.

The prior `.tmp/structural1/baseline.log` and `baseline_additional.log`
experimentally reproduced 12 exact failing node IDs that recur now. Those nodes
also appear in the prior `frozen_final.log` and frozen AUTHOR phase report:

| Failure group | Count | Attribution evidence |
| --- | ---: | --- |
| AUTHOR.SCOPE/SPAN frozen attribution | 2 | Same restored `web/runner.py` hash mismatch already present in prior baseline; runner bytes unchanged. |
| PATCH.MINIMAL verification producers | 1 | Prior baseline already returned `unavailable` where fixture expected `applied`; pipeline/producer implementation unchanged. |
| PATCH.MINIMAL novelty smoke B/C/D | 4 | Prior baseline already returned inconclusive matrix or rejected verification outcomes; no producer repair in this phase. |
| Novelty frozen boundary receipts | 2 | Prior baseline already failed older control-engine reversal attribution; protected control-engine bytes unchanged. |
| Result-fields frozen lifecycle/receipt | 2 | Prior read-only entry substitution reproduced unavailable lifecycle and old pipeline attribution failure. |
| Human authority branch picker expectation | 1 | Prior baseline already expected `UX.RUN.1` and received `DOGFOOD.1B`; exact entry registry confirms unchanged recommendation. |
| Human approval token picker expectation | 1 | This additional historical assertion also expects `UX.RUN.1`; read-only exact entry registry already recommends `DOGFOOD.1B`. |
| Binding-context performance cap | 1 initial, 0 persistent | Concurrent broader-run median 0.102102 seconds exceeds unchanged 0.1-second cap; isolated rerun passes in 9.35 seconds after concurrent load ends. No materialization import/code change in this runtime path; no pre-phase timing reproduction was performed. |

The AUTHOR.SCOPE/SPAN historical runner reconstruction remains
`a2d510567968b9bc11193940f0847424631b700bc095ee5628a19654e2227ee5`,
where both frozen receipts expect
`6b4e907c6ed14bc89dcaebe27541280b113a62babe01a8b570be6e368a666e6e`.
These exact hashes match the prior baseline failure. Twelve failures are
experimentally established inherited failures; the extra picker failure is
established by restored entry metadata. The timing miss is reported separately
and passes an isolated rerun, without claiming a reproduced pre-phase timing
failure. There are 13 persistent inherited failure nodes. No historical receipt,
assertion, timing cap or expected recommendation is repinned or weakened.
