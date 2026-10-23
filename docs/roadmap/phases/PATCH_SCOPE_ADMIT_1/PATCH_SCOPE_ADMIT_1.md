# PATCH.SCOPE.ADMIT.1 — deterministic structural authoring admission

Status: **COMPLETE_WITH_WARNINGS**. Admission is implemented and validated.
Warnings are the twelve independently reproduced entry-state failures in frozen
authoring/minimality/authority tests, plus two inherited policy-test skips.

The result satisfies `admitted scope ⊆ validated PLAN ⊆ human-approved ceiling`.
Unused ceiling targets confer no authority. Admission grants candidate drafting
only; no author integration, candidate, patch, Java execution, source mutation,
filesystem creation, write or Apply authority is introduced.

1. **Files changed.** New: `core/structural_scope_admission.py`,
   `tests/test_patch_scope_admit1.py`, `scripts/replay_patch_scope_admit1.py`,
   `docs/roadmap/PATCH_SCOPE_ADMIT_1.md`,
   `docs/roadmap/PATCH_SCOPE_ADMIT_1_BANK2.json`,
   `tests/_patch_scope_admit1_maintenance.py`,
   `tests/fixtures/patch_scope_admit1_reversal.json`. Four existing files receive
   attributed bookkeeping only: `docs/roadmap/phase_registry.json`,
   `tests/test_phase_registry.py`, `tests/test_phase_picker.py`,
   `tests/_patch_scope_plan1_maintenance.py`. All other entry changes are preserved.
2. **Admission owner.** `core/structural_scope_admission.py` owns exact-path
   evidence acquisition, pure admission and the pure future-author validator.
   No live author, UI, session store, executor or Apply path is wired.
3. **Schema.** `AdmittedStructuralAuthoringScope`, schema
   `patch_scope_admit_1_v1`, phase `PATCH.SCOPE.ADMIT.1`, status
   `admitted_candidate_authoring_scope`. Frozen dataclasses and transitive
   immutable-field checks prohibit mutable authority/evidence containers.
   Canonical sorted JSON and SHA-256 bind task, design, P1, receipt, ceiling,
   complete reconstructed plan, repository, measured paths/policy,
   source/context, prior actual scope, definitions, operations, support and
   semantic/validation contracts. Timing and wall-clock time are excluded.
4. **PLAN validation.** Every admission calls the frozen pure
   `validate_structural_implementation_plan`. It reconstructs the full typed
   proposal, containment, MUST coverage, semantics and structural minimality.
   Serialized status, a claimed fingerprint or a frontend flag cannot replace
   this gate. PLAN.1's implementation is byte-identical to entry.
5. **Approval lineage validation.** Frozen PLAN revalidation invokes APPROVE.1
   reconstruction with independent stored human-action evidence and all fresh
   typed inputs. Only exact approval of the eligible P1 ceiling is sufficient.
   Declines, revisions, missing independent actions and wrong receipts fail.
   Admission binds the receipt fingerprint; the plan never becomes independent
   authority. No human is asked to approve the same subset again.
6. **Freshness.** Fresh task, effective design, P1, receipt, repository,
   source/context and prior actual scope are reconstructed before projection.
   Newly measured file bytes must also match the supplied source buffers.
   Source mismatch returns `reacquisition_required`; lineage/plan mismatch
   returns `admission_stale`.
7. **Current-scope binding.** Both current actual scope and measured RepairScope
   fingerprints are copied from the freshly validated plan. Nonempty
   RepairScope and AuthoringRepairScope fixtures are admitted without mutation.
   A changed or removed baseline returns `admission_stale`; no union occurs.
8. **Path-policy validation.** The exact-path acquisition seam uses the existing
   canonical repository identity primitive. Pure policy checking uses
   `is_safe_repository_relative_path`, `RepoIgnorePolicy`, its non-overridable
   exclusions and the canonical supported-extension inventory. Only Java source
   is supported by this structural phase. Absolute, traversal, noncanonical,
   unsupported, ignored and hard-excluded paths fail closed. Exact ancestor
   resolution rejects symlink escapes, occupied/non-directory parents and unsafe
   resolved locations. Optional policy files are read by exact name; unreadable
   or escaping policy sources fail rather than silently admitting a path.
9. **New-file absence binding.** Each new-file envelope contains an immutable
   witness of the exact absent path, resolved repository-relative destination
   and ancestor states. Existing files, directories and occupied paths produce
   `admission_conflict_existing_path`. No timestamps enter the witness.
10. **Logical-to-physical mapping.** Definition allowances copy exact
    PLAN-selected logical identities and definitions into the PLAN-selected
    physical path/layout. Public top-level class filename compatibility is
    checked using the planned class name, without hard-coding SavingAccount.
    Parsed package evidence and the exact acquired parent directory establish
    the corresponding source location; unknown directory/package compatibility
    returns `scope_evidence_incomplete`. A packaged `edu/SavingAccount.java`
    positive fixture passes without creating that file.
11. **Existing-file structural boundaries.** Operations name the exact file,
    class owner, selected approved identity, planned definition IDs and
    source/context-bound class or declaration evidence. Whole-class replacement
    is not an editable operation. No neighboring declarations are included.
12. **Member insertion boundaries.** `insert_member` binds the exact parsed
    class body span/fingerprint and the exact planned new member IDs.
    `insert_nested_class` similarly binds the exact existing parent body and
    enumerates the nested class's planned definitions. Body evidence identifies
    an insertion container; it confers no arbitrary body-replacement permission.
13. **Exact member removal boundaries.** `remove_declaration` binds the exact
    declaration fingerprint, owner, line span and acquired byte span.
    Subclass-only BANK permits removal of the selected `BankAccount::saving`
    declaration only. Unrelated methods and fields remain read-only.
14. **New-file definition ceiling.** A `draft_new_file` envelope contains only
    planned class, constructor, savings state, credential state, verification,
    transfer and interest definitions. Each allowance retains definition ID,
    owner, kind, name, parameter order/shape, visibility, type, parent, roles,
    contract and physical target/layout. No code or replacement body is produced.
15. **Read-only supporting declarations.** Relevant acquired class,
    constructor, field and callable declarations are tagged `read_only_support`
    in a separate collection. Exact edited declarations are removed from that
    collection. Support relevance cannot add an operation or edit definition.
16. **Selected MAY admission.** A selected MAY gets only its exact mapped PLAN
    realization. In the fixtures the chosen protected boolean debit helper
    becomes one member insertion with its chosen parameters and debit contract.
    Admission never substitutes a public API or changes balance visibility.
17. **Unused MAY exclusion.** The nested fixture leaves private-constructor
    access available in the ceiling but unused by PLAN. It appears in no
    definition allowance or edit operation. Injecting it into serialized scope
    transport fails `admission_scope_nonminimal`. Ceiling availability cannot
    recover it for this admission.
18. **MUST capability preservation.** All nine MUST capabilities remain covered
    in each replay fixture. Typed PLAN capability coverage, semantic commitments,
    implementation decisions, successful-debit credit guard, balance
    encapsulation and chosen base-saving transition are carried unchanged.
19. **Test-file handling.** `SavingAccountBehaviorTest.java` remains a
    `validation_evidence_need`, with `test_write_authority=false`. It never
    appears in the editable or new-file sets. Injected test-file operations fail.
20. **Validation-command handling.** The javac need stays descriptive evidence.
    No command admission or Java validation is performed by ADMIT.1.
    `execution_authorized=false` throughout.
21. **Subclass-only admitted scope.** One new-file drafting envelope containing
    seven SavingAccount definitions; one exact BankAccount debit insertion;
    one exact BankAccount saving removal. Nine definition allowances total.
22. **Compatibility admitted scope.** One new-file drafting envelope containing
    seven SavingAccount definitions and one debit insertion. Base saving is
    read-only support, with no removal/modification authority. Eight allowances.
23. **Specialization admitted scope.** One new-file drafting envelope containing
    seven SavingAccount definitions, including the chosen subclass saving
    specialization, and one debit insertion. Base saving remains read-only
    support. Eight allowances.
24. **Nested-layout admitted scope.** One `insert_nested_class` operation inside
    BankAccount in `bank.java`, containing seven SavingAccount definitions;
    one exact debit insertion in the same source. No new-file envelope and no
    private-constructor edit. Eight allowances.
25. **Path collision.** A path appearing between planning/admission or after
    admission is detected using newly acquired evidence and produces
    `admission_conflict_existing_path`. The occupied path is never overwritten.
26. **Stale source.** Both changed supplied buffers and actual disk bytes hidden
    behind an old supplied buffer fail `reacquisition_required`. Context and
    declaration freshness are reconstructed through frozen PLAN validation.
27. **Wrong-plan behavior.** A different valid plan, even one changing only the
    selected helper name, cannot reuse an admission. Forged labels, hashes and
    plan authority fields also fail `admission_stale`.
28. **Outside-repo/ignore behavior.** Exact acquisition rejects unsafe spelling
    and symlink escape without normalizing into another authorized path.
    Frozen PLAN can reject unsafe proposals even earlier. Hard exclusions and
    either repository ignore source are independently enforced by admission.
29. **Over-admission behavior.** Extra Database/UserRepository/AccountSession/
    helper definitions and altered signatures/contracts fail
    `admission_outside_validated_plan`. Wider class/file operations, unused MAY
    edits and injected test writes fail `admission_scope_nonminimal`.
    A recomputed attacker-supplied scope hash does not bypass reconstruction.
30. **Authority escalation rejection.** `write_authority`,
    `execution_authorized`, `apply_authority`, `auto_apply`, filesystem creation
    and test-write flags must remain literal false, including nested transport
    objects. Escalations fail `admission_authority_escalation`; all other unknown
    or altered canonical authority fields fail full reconstruction.
31. **RepairScope delta.** Zero. Frozen implementation and supplied baselines
    retain entry bytes/immutable content.
32. **Frozen AuthoringRepairScope delta.** Zero. No facade or adapter is added.
33. **Candidate.** Null; patch empty on every admitted scope. No candidate body,
    replacement text or generated-code byte envelope exists.
34. **Write/Apply authority.** False. Exact new-file targets have
    `candidate_may_propose_new_file=true` and
    `filesystem_file_creation_authority=false`. All authoring authority is
    `candidate_authoring_only`. Apply and auto-apply remain false.
35. **Model calls.** Zero in admission, pure validation and governance replay.
36. **Author calls.** Zero. No author prompt is constructed and no author
    provider is integrated.
37. **Traversal.** Repository traversal delta zero. Guards prohibit walk,
    scandir and listdir in exact acquisition, admission and future validation.
    Parsing supplied bounded source buffers is in-memory syntax inspection.
38. **Source integrity.** All 21 protected artifacts retain entry SHA-256,
    including frozen core modules, historical phase receipts, actual Java
    sources and `web/sessions.json`. Real bank.java and MainApp.java remain
    unchanged. SavingAccount.java is absent from the real Java repository and
    workspace root. No real BANK.2 approval is consumed. Filesystem tests use
    isolated synthetic repositories; replay uses in-memory synthetic path facts.
39. **Idempotency.** Identical fresh inputs yield equal scope and identical
    admission fingerprint. Five repeated admissions per fixture prove this.
    There is no persistent authority store to append duplicate records to.
40. **Stale-after-admission behavior.** Historical scopes remain immutable.
    `validate_admitted_structural_authoring_scope` reconstructs everything using
    the supplied fresh typed inputs and newly measured exact-path evidence.
    Changed source, path absence, task/design, plan, approval, scope or policy
    invalidates the historical scope. A caller must reacquire evidence directly
    before invoking this pure gate; an old witness never guarantees continuing
    absence. Future integration remains responsible for this acquisition call.
41. **Performance.** Five synthetic repetitions per scenario measure frozen
    PLAN revalidation, path policy, source/declaration freshness, physical
    projection, structural minimality, fingerprint construction and total
    separately. No provider latency exists. Full stage medians/maxima appear
    below and in the replay JSON; wall-clock values do not affect identity.
42. **Focused tests.** 67 passed. Positive coverage includes all three savings
    transitions, nested/unused MAY, selected MAY, explicit package evidence,
    immutable transport, nonempty prior measured/authoring scope and idempotency.
    Negatives cover the required approval, freshness, plan, path, collision,
    symlink, definition, over-admission, test-file and authority cases.
43. **Adjacent tests.** PLAN/APPROVE/REFRESH/RECHECK/EXPAND: 272 passed.
    Frozen OOP DESIGN/DETECT/CONTINUE/UI: 165 passed. Frozen author scope/span,
    basis scope, human authority/Apply and PATCH.MINIMAL suites: 401 passed,
    twelve entry-state failures. Repository/path/identity policy: 64 passed,
    two inherited skips. A read-only snapshot substitution reproduces the
    identical twelve failing node IDs: six inconclusive verification failures,
    five earlier frozen attribution failures in untouched runner/control/pipeline
    modules, and one prior picker expectation. No failing frozen receipt is
    repinned or assertion weakened. Logs and baseline reproduction script are
    under `.tmp/admit1/`.
44. **Registry/benchmarks.** Registry/picker: 279 passed. One completed PATCH
    authority slice in CONTROL: 214 phases, 32 CONTROL entries, 210 history
    entries. Registry implementation approval metadata retains the conservative
    repository-write convention; it does not request a second runtime scope
    approval. All four shared-file bookkeeping changes reverse exactly to
    their dirty entry bytes via the new ADMIT.1 attribution record. Historical
    receipts are unchanged. Compileall and git diff --check pass; benchmark
    check reports 54 cases and zero errors. Across the required final suites:
    1,248 passed, twelve reproduced inherited failures, two inherited skips.
45. **First remaining blocker.**
    `STRUCTURAL_AUTHOR_INTEGRATION_NOT_IMPLEMENTED`. A later phase can build an
    explicit author facade and must call the pure fresh-scope validator before
    creating a prompt. ADMIT.1 stops before this integration.

| Explicit question | Answer |
| --- | --- |
| Is admitted scope bounded by validated PLAN rather than the larger ceiling? | Yes; operations and definitions exactly realize the selected PLAN. |
| Can approved-but-unused MAY targets enter it? | No; injection is rejected. |
| Are exact physical paths validated before admission? | Yes; lexical, repository, ignore, source-type, ancestor and symlink policy gates apply. |
| Can a planned new file be admitted for drafting without creation? | Yes; immutable absence evidence and definition bounds grant drafting only. |
| Does existing BankAccount edit authority stay member/definition bounded? | Yes; exact insertion/removal operations only. |
| Does compatibility keep BankAccount.saving read-only? | Yes. |
| Does subclass-only permit only the selected transition edit? | Yes; exact saving declaration removal. |
| Are validation test files outside write scope? | Yes; evidence only, test-write false. |
| Does admission grant filesystem write or Apply authority? | No. |
| Does it call a model or author? | No. |
| Can a future author independently validate without UI/session labels? | Yes; use the pure validator with freshly acquired evidence and typed lineage inputs. |

Replay: `python scripts/replay_patch_scope_admit1.py --repetitions 5 --output
docs/roadmap/PATCH_SCOPE_ADMIT_1_BANK2.json`. It records four positive scenarios,
fifteen negative outcomes, physical edits, read-only support, unused ceiling
targets, authority flags and performance. Exact-path acquisition and symlink
checks additionally run against isolated filesystem fixtures in focused tests.

Median / maximum milliseconds, five synthetic repetitions:

| Stage | Subclass only | Compatibility | Specialization | Unused MAY / nested |
| --- | ---: | ---: | ---: | ---: |
| PLAN revalidation | 599.830 / 605.608 | 573.542 / 667.304 | 585.761 / 598.494 | 581.842 / 615.600 |
| Path policy | 0.986 / 1.239 | 0.977 / 1.156 | 0.921 / 1.045 | 0.650 / 0.722 |
| Source/declaration freshness | 2.748 / 2.958 | 2.964 / 3.113 | 2.573 / 2.658 | 2.571 / 3.239 |
| Logical/physical projection | 3.459 / 3.803 | 2.947 / 3.285 | 2.948 / 3.164 | 2.762 / 3.722 |
| Structural minimality | 0.064 / 0.084 | 0.054 / 0.065 | 0.057 / 0.057 | 0.055 / 0.082 |
| Fingerprint construction | 4.231 / 4.725 | 4.073 / 5.165 | 3.751 / 4.164 | 4.696 / 4.899 |
| Total | 611.812 / 616.974 | 586.159 / 677.625 | 596.679 / 609.081 | 591.660 / 627.041 |
