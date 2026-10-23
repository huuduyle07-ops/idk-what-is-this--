# PATCH.CANDIDATE.VALIDATE.1A

Virtual Java Compile Validation measures whether an exact, freshly revalidated
MATERIALIZE.1 virtual post-state compiles. A truthful compiler failure completes
this phase. Candidate revision and behavioral validation remain separate work.

The operation has one bounded javac diagnostic capability. The candidate,
materialization and compile receipt retain their existing authority boundaries:
`candidate_only`, `virtual_post_state_only` and `diagnostic_evidence_only`.

## Changed files

| Change | Exact path |
| --- | --- |
| New | `core/structural_compile_validation.py` |
| New | `tests/test_patch_candidate_validate1a.py` |
| New | `scripts/replay_patch_candidate_validate1a.py` |
| New | `docs/roadmap/PATCH_CANDIDATE_VALIDATE_1A.md` |
| New | `docs/roadmap/PATCH_CANDIDATE_VALIDATE_1A_SYNTHETIC.json` |
| New | `tests/_patch_candidate_validate1a_maintenance.py` |
| New | `tests/fixtures/patch_candidate_validate1a_reversal.json` |
| Modified | `docs/roadmap/phase_registry.json` |
| Modified | `tests/test_phase_registry.py` |
| Modified | `tests/test_phase_picker.py` |
| Modified | `tests/_patch_candidate_materialize1_maintenance.py` |

These seven new and four modified paths are the phase delta over the existing
dirty tree. Existing candidate/author/materializer Java code, frozen receipts,
MainApp and session sources are untouched.

## Implementation and evidence contract

1. **Files changed.** The new owner is
   `core/structural_compile_validation.py`, with focused infrastructure tests,
   `scripts/replay_patch_candidate_validate1a.py`, this report and its synthetic
   replay JSON. Registry/picker changes append one phase, adjust counts and add
   an exact newest bookkeeping reversal. Frozen implementation modules and
   historical receipt JSON files remain unchanged.
2. **Validator owner.**
   `compile_materialized_structural_candidate(materialized, *, candidate,
   admitted_scope, repository_root, timings=None, **fresh_inputs)` owns execution.
   It accepts no executable, shell string, flags, provider, classpath or temp-root
   parameter. The pure synthetic provider seam is
   `normalize_structural_compile_result(...)`.
3. **Receipt schema.** Frozen `StructuralCompileValidationReceipt` uses
   `patch_candidate_validate_1a_v1`. Its recursively immutable records bind
   materialization, candidate, admission, PLAN, approval, semantic lineage,
   repository identity/evidence, source manifest, invocation, compiler result,
   normalized diagnostics, evidence satisfaction and authority. Wall-clock
   durations are excluded from fingerprints.
4. **Materialization freshness gate.** Before temp creation, the execution
   facade acquires exact named repository evidence and calls frozen
   `validate_materialized_structural_candidate(...)`. It reacquires the named
   evidence once more to detect changes during this gate. Stored status and
   after-hash claims alone cannot pass it.
5. **Source/path freshness.** A changed before-state returns
   `reacquisition_required`; an absent-to-virtual path that now exists returns
   `materialization_conflict_existing_path`. Both stop before any javac call.
   Altered virtual source, hash, operation or lineage likewise fails before
   workspace creation.
6. **Temp workspace policy.** The harness checks inherited temp settings and the
   resolved system temp parent before creating anything. It owns a system
   `TemporaryDirectory`, checks it is outside the repository, and creates
   separate `sources`, `classes` and empty lookup directories. It never uses a
   repository-relative temp source directory or clones repository inventory.
7. **Exact virtual-byte projection.** Changed/new Java files are written from
   canonical MATERIALIZE.1 `after_bytes`. Exact byte equality and SHA-256 are
   checked after projection, immediately before compile and after compile. A mismatch
   returns `validation_workspace_integrity_failure`. No operation is rerendered.
8. **Dependency policy.** Only MATERIALIZE.1's exact supporting source witnesses
   and their already-acquired bytes can supply `read_only_compile_dependency`
   inputs. Their path, hash and size must match. Missing external type/package
   evidence produces `compile_evidence_incomplete`; no source is discovered in
   response to compiler output.
9. **javac executable policy.** Frozen PREFLIGHT.REQUEST.1's
   `resolve_javac(excluded_root=...)` checks absolute PATH entries, excludes
   repository compilers and rejects script wrappers. No JDK is installed when
   resolution fails; the typed receipt status is `validator_unavailable`.
10. **Argument policy.** The harness uses PREFLIGHT's closed argv builder:
    UTF-8, `-proc:none`, `-implicit:none`, an empty sourcepath/classpath, an
    isolated `-d`, frozen JVM/output options, error/warning count limits and the
    exact sorted source paths. Candidate source text cannot supply flags. No
    additional lint, analyzer or arbitrary command is admitted.
11. **Shell setting.** PREFLIGHT's process launcher uses `shell=False`, disabled
    stdin and hidden Windows process creation. Source comments are bytes.
12. **Output-directory policy.** Class files belong only to the separate
    ephemeral `classes` directory. They never alter repository source or enter
    the virtual source identity.
13. **Timeout/output bounds.** The frozen limits are 60 seconds for compile,
    30 seconds for the version probe, 65,536 captured bytes per stream and 32
    typed diagnostics. Timeout is `compile_timeout`. Stream or diagnostic
    overflow is `compile_output_bounded`; bounded prefixes cannot claim success.
14. **Compiler identity.** `JavacIdentity` records the exact executable path,
    SHA-256 and measured `javac -version`. Executable bytes are checked again
    after the probe and after compile. The evidence speaks for this measured
    compiler only.
15. **Input manifest.** Each `CompileInput` binds a logical path, byte size,
    SHA-256 and `materialized_virtual_file` or
    `read_only_compile_dependency` provenance. Temp absolute paths supply no
    semantic authority.
16. **Raw output capture.** Bounded stdout/stderr remain separately available in
    `CompilerResult`. Their only canonical display normalization is temp-path
    replacement and CRLF-to-LF output normalization. Source bytes are untouched.
17. **Normalized diagnostics.** Located records preserve compiler kind, logical
    file, line, caret column, message and full bounded diagnostic block; safely
    parsed symbol data is optional. Global warnings/notes remain evidence too.
    Every located record binds the exact file hash, compiler receipt fingerprint
    and materialization fingerprint.
18. **Temp-path normalization.** Source-root paths normalize to logical input
    paths, and other workspace paths to `<isolated>`. Both slash spellings are
    handled; temporary identity cannot alter the semantic receipt fingerprint.
19. **Structural owner mapping.** Exact in-memory Java structural inventories
    and diagnostic coordinates identify the smallest unambiguous declaration.
    Definition IDs require exact admitted identity and containment in the
    materialized operation span. Deterministic known-class references retain
    both sides of cross-file diagnostics; ambiguous names are left unresolved.
20. **Compile-success semantics.** A completed javac exit code zero against the
    exact source set returns `compile_validated` and `compile_success=true`.
    `behavior_validated` and `correctness_proven` remain false.
21. **Compile-failure semantics.** Nonzero javac returns `compile_failed`, or
    `compile_evidence_incomplete` for missing external source evidence. Structural
    parse success and language compile failure are compatible measurements.
22. **Warning semantics.** Warnings and notes are retained separately. A bounded
    warning-only exit code zero still satisfies compile validation.
23. **javac evidence-need satisfaction.** A separate immutable
    `JavacEvidenceSatisfaction` relation binds each javac need to PLAN and the
    compiler receipt. Only compile success produces satisfaction relations;
    failure leaves that relation empty. Historical PLAN is not mutated.
24. **Remaining behavioral evidence need.**
    `behavioral_validation_pending=true` records applicable focused behavioral
    evidence needs. Compilation cannot satisfy those assertions.
25. **Test-write behavior.** `SavingAccountBehaviorTest.java` remains a proposed
    test file with `test_write_authority=false`. Proposed test paths are rejected
    from compile inputs. No test is generated in the repository or temp space.
26. **No-auto-revision behavior.** Compiler failure returns evidence without an
    author call, plan regeneration, scope expansion, clarification or repair.
    Generated-definition ownership describes the evidence; it grants no revision
    authority.
27. **Workspace cleanup.** Normal `TemporaryDirectory` lifetime removes sources,
    compiler output, capture files and classes on success, failure and timeout.
    Timeout directly kills/reaps the javac child under a bounded cleanup wait;
    no taskkill or second cleanup executable is invoked.
    Cleanup is allowed to enumerate its own ephemeral workspace; repository
    discovery is forbidden.
28. **Receipt validator.**
    `validate_structural_compile_receipt(receipt, *, materialized, candidate,
    admitted_scope, repository_root=None, timings=None, **fresh_inputs)`
    independently revalidates materialization, reconstructs inputs/diagnostics/
    invocation/evidence relations and compares every canonical receipt field.
    With a root it freshly reads exact named evidence; pure mode requires caller
    acquisition. It reruns no javac. Provider output is measured evidence, not a
    cryptographic execution attestation.
29. **Stale-after-validation behavior.** A receipt remains immutable historical
    evidence if the repository later changes. Fresh downstream reconstruction
    rejects stale source/path evidence; downstream revision or Apply must repeat
    the freshness gate.
30. **Authority.** The receipt sets `write_authority`,
    `filesystem_write_authority`, `filesystem_file_creation_authority`,
    `execution_authorized`, `apply_authority`, `auto_apply` and
    `test_write_authority` to false. Diagnostic capability belongs to the harness
    operation only.
31. **javac invocation count.** Each normally measured receipt has one compile
    invocation and one separately counted version probe. Unavailable compiler or
    pre-execution freshness rejection has zero compile invocations.
    `javac_total_invocation_count` explicitly reports compile plus probe calls.
32. **Arbitrary command count.** Zero. Only fixed javac version/compile actions
    are executed; no command string is interpreted.
33. **Model/author calls.** Zero. Frozen synthetic candidate construction uses
    supplied fixture text and pure normalization; it invokes no provider.
34. **Repository traversal.** Zero. Exact named source/path/policy evidence only;
    empty compiler lookup paths prevent javac from reading unbound neighbors.
35. **Real BANK.2 consumption.** Zero. Replay uses frozen synthetic MATERIALIZE.1
    fixtures and temporary before-state repositories.
36. **Source/session integrity.** Replay compares source bytes, scope, candidate,
    materialization and PLAN before/after every call and confirms new virtual
    paths remain absent in the fixture repository. MainApp and real UI/session
    state are untouched.
37. **Exact frozen BANK compile outcome.** `compile_validated`, exit code zero
    under `javac 26.0.2.1`, for all three unchanged compatibility repetitions.
    The other six frozen materialization scenarios also compile as-is.
38. **BANK diagnostics.** None: stdout and stderr are empty, and the normalized
    diagnostics/warnings tuples are empty. Exact source hashes and the measured
    compiler result are retained in the replay receipt.
39. **Focused tests.** Focused verification reports 56 verified cases: a full
    run of 53 passed in 198.06 seconds, followed by three final targeted
    regressions passed in 13.63 seconds. This is not a single 56-case run.
    The Python infrastructure tests cover source projection,
    compiler results, freshness/tampering, receipt reconstruction, authority,
    dependency bounds and the requested positive/negative matrix. They create no
    Java behavioral test or execution oracle.
40. **Adjacent tests.** MATERIALIZE/AUTHOR/ADMIT/PLAN/APPROVE/REFRESH/RECHECK/
    EXPAND and registry/picker verification reports 798 passed, seven warnings
    and no failures in 810.88 seconds. Frozen PREFLIGHT compile and
    author/minimality/Apply boundaries plus repository identity/path policy are
    governed separately, with inherited failures attributed below.
41. **Registry/benchmarks.** One CONTROL slice; 217 phases, 35 CONTROL and 213
    complete/history. Picker recommendation remains DOGFOOD.1B. Registry/picker
    and historical MATERIALIZE bookkeeping verification report 286 passed.
    Newest reversal restores exact dirty-entry bytes before older immutable
    checks; historical receipts are never repinned. Benchmark `--check` validates
    all 54 cases with zero errors. Compileall across `core web tests scripts
    benchmarks` and `git diff --check` pass.
42. **Performance.** Replay records acquisition, materialization validation, temp
    construction, integrity checks, compiler identity, javac provider time,
    diagnostic normalization, owner mapping, fingerprints, total time and
    harness overhead separately. Provider latency is excluded from harness
    overhead and timing is excluded from semantic fingerprints.
    The final replay ran concurrently with broader governance verification;
    these measured latencies are not an isolated throughput benchmark.
43. **First remaining blocker.**
    `STRUCTURAL_CANDIDATE_BEHAVIORAL_VALIDATION_NOT_IMPLEMENTED`. Candidate
    revision is a later seam; compile evidence does not open Apply.

## Explicit answers

| Question | Answer |
| --- | --- |
| Did the exact virtual candidate compile? | Yes. All seven frozen synthetic MATERIALIZE.1 candidates compiled unchanged under javac 26.0.2.1. |
| If not, which exact diagnostics were measured? | The frozen BANK compile passed with no diagnostics; failure infrastructure is covered by separate synthetic tests. |
| Were virtual bytes changed to make it compile? | No. |
| Was a dependency discovered by repository traversal? | No. |
| Was any test generated? | No. |
| Was any Java code executed? | No Java program, JUnit or main method; only javac diagnostics. |
| Does compile success imply behavioral correctness? | No. |
| Does compile success grant write or Apply authority? | No. |
| Can downstream revision consume the receipt without trusting UI/session state? | Yes, through independent receipt reconstruction and fresh materialization/source/path evidence. Revision authority remains a separate requirement. |

## Verification commands

Use a distinct fresh `--basetemp` for each pytest run. The repository's default
`tmp_tests` location contains inherited inaccessible test artifacts.

```text
python -m pytest tests/test_patch_candidate_validate1a.py -q
python -m pytest tests/test_patch_candidate_materialize1.py tests/test_patch_author_structural1.py tests/test_patch_scope_admit1.py -q
python -m pytest tests/test_patch_scope_plan1.py tests/test_patch_scope_approve1.py tests/test_patch_scope_refresh1.py tests/test_patch_scope_recheck1.py tests/test_patch_scope_expand1.py -q
python -m pytest tests/test_preflight_request1.py -q
python -m pytest tests/test_patch_author_scope1.py tests/test_patch_author_span1.py tests/test_patch_basis_scope1.py tests/test_human_authority_branch_checkpoint.py tests/test_human_apply_authorization.py -q
python -m pytest tests/test_patch_minimal_live.py tests/test_patch_minimal_novelty_live.py tests/test_benchmark_patch_minimality.py tests/test_repo_ignore_policy.py tests/test_repository_inventory.py tests/test_canonical_repository_identity.py tests/test_phase_registry.py tests/test_phase_picker.py -q
python -m compileall -q core web tests scripts benchmarks
python benchmarks/run_benchmarks.py --check
git diff --check
python scripts/replay_patch_candidate_validate1a.py --repetitions 3
```

## Measured replay

The [synthetic replay](PATCH_CANDIDATE_VALIDATE_1A_SYNTHETIC.json) is the canonical
record of frozen BANK, subclass-only, specialization, nested, LF, CRLF-origin and
packaged measurements. It binds exact unchanged virtual input manifests,
compiler identity, raw compiler capture, normalized ownership, deterministic
receipt fingerprints and separate performance measurements.

All seven scenarios report `compile_validated` with exit code zero, no output
overflow and no diagnostics/warnings. Three repetitions per scenario produce
identical semantic receipts, 21 compile invocations and 21 separately counted
version probes. No source or virtual byte is repaired. Arbitrary commands,
model/author calls, repository traversal, test generation and Java execution are
zero. Every receipt leaves behavioral evidence pending and all write/Apply
authority false.

Every logical path, byte size and materialized SHA-256 in all seven manifests
matches the unchanged historical
`PATCH_CANDIDATE_MATERIALIZE_1_SYNTHETIC.json` virtual post-state exactly.

The compiler is `javac 26.0.2.1`; executable SHA-256 is
`c788d3369408b0dd43be8e0732f24b4493e047e4cb5b5bda46fece05e9ba7039`.
The replay records its exact resolved executable identity. Portability to another
JDK is unmeasured.

| Frozen BANK virtual input | Bytes | Exact SHA-256 |
| --- | ---: | --- |
| `bank.java` | 401 | `8771b7def21331c615a88991a1117a716a6c22b18b8fc5ea5e20d2802d99aa39` |
| `SavingAccount.java` | 746 | `3460262bfa3d9ece43c5d8df97f76a08fd83cbb7ad224557a837c1ee6ef56588` |

The compatibility receipt fingerprint is
`d4467479c8963629947ac75b29990c95f6b0e8fde286c6217758d540b0a5da7e`.
Its javac need is satisfied through a separate PLAN-bound relation; the
behavioral need remains pending. The nested scenario compiles exactly one
virtual `bank.java`; packaged input preserves its logical `edu/` paths. All
other scenarios compile their two exact materialized Java files.

Frozen BANK performance, three repetitions:

| Measurement | Median ms | Maximum ms |
| --- | ---: | ---: |
| Fresh materialization validation | 616.7267 | 681.3998 |
| Exact named evidence acquisition | 12.9047 | 17.5382 |
| Temporary workspace construction | 4.8135 | 5.2532 |
| Virtual-byte integrity verification | 2.6208 | 2.7023 |
| javac provider, version probe + compile | 1255.7777 | 1444.5426 |
| Compiler identity | 8.4599 | 8.8926 |
| Diagnostic normalization | 2.9483 | 3.3180 |
| Structural owner mapping | 1.3816 | 1.4647 |
| Receipt fingerprinting | 1.6150 | 1.6426 |
| Total harness overhead, excluding javac | 671.5196 | 731.0085 |
| Total operation | 1986.7862 | 2116.0622 |

The initial registry/picker command used the repository's configured inaccessible
`tmp_tests` directory and returned 271 passed plus 15 fixture setup permission
errors. Repeating with a fresh unique base directory passed all 286 cases in
2.12 seconds, including the frozen MATERIALIZE bookkeeping reversal. No
assertion failure remained in that suite.

## Frozen governance results and entry attribution

| Verification run | Measured result |
| --- | --- |
| Focused full run | 53 passed, 198.06 seconds |
| Final targeted regressions | 3 passed, 13.63 seconds |
| MATERIALIZE/AUTHOR/ADMIT/PLAN/APPROVE/REFRESH/RECHECK/EXPAND + registry/picker | 798 passed, 7 warnings, 810.88 seconds; `.tmp/validate1a/adjacent.log` |
| Broad frozen boundaries and repository policy | 335 passed, 2 skipped, 10 inherited failures, 116.11 seconds |
| Frozen PREFLIGHT | 93 passed, 4 inherited failures, 103.81 seconds |
| Benchmark `--check` | 54 checked cases, zero errors |
| Compileall and Git whitespace check | Passed |

The broad frozen author/minimality/Apply and repository-policy run reports
335 passed, 2 skipped and 10 failed in 116.11 seconds. The frozen PREFLIGHT run
reports 93 passed and 4 failed in 103.81 seconds. These are 14 inherited failures
in two distinct groups, not passing governance claims.

All ten broad failure nodes reproduce before this phase with exact entry-byte
in-memory substitution; that baseline run reports 10 failed in 57.74 seconds.
All four PREFLIGHT failure nodes likewise reproduce on the entry state; that
baseline run reports 4 failed in 8.19 seconds. This attribution leaves frozen
sources, assertions and historical receipt pins unchanged. Verification also
checks 28 named protected files, including prior Java sources, sessions and
frozen artifacts, with every entry/current byte hash equal.

| Verification | Result log | Entry-state attribution log |
| --- | --- | --- |
| Frozen author/minimality/Apply and repository policy | `.tmp/validate1a/frozen.log` | `.tmp/validate1a/frozen_baseline.log` |
| Frozen PREFLIGHT compile boundaries | `.tmp/validate1a/preflight.log` | `.tmp/validate1a/preflight_baseline.log` |

The inherited failures concern historical attribution/registry pins,
verification-producer/matrix expectations and the preflight generate route.
They are retained as limitations; this phase neither repins them nor changes
the frozen boundaries to force a green result.

Focused infrastructure verification passes the full requested matrix:

| Matrix | Passing coverage |
| --- | --- |
| Positive | Exact LF and CRLF-origin virtual bytes, packaged and nested candidates, synthetic compile success, compile warnings, receipt idempotency, exact frozen BANK compile |
| Negative | Stale source, new-path collision, tampered materialization, wrong lineage, missing exact dependency, unbound extra source, unavailable javac, timeout, output overflow, temp-byte integrity mismatch, authority escalation, receipt tampering |
| Boundary regressions | Postcompile byte/compiler integrity, temp-parent rejection before workspace creation, no author/repair/test/Java execution, exact source/input manifest ownership and unchanged historical bookkeeping |

The three final targeted cases verify preservation of raw output when typed
diagnostic count overflows, exact packaged cross-file references and rejection
of a repository-supplied compiler identity by the pure consumer gate.
