# CHECK.1 — Post-Run Contract Reconciliation

**Status:** complete, report-only, not live-wired
**Date:** 2026-08-27
**Depends on:** CTX.APPLY.0 (bounded patch-safety attachment) and the frozen
`core.patch_safety` / `core.repository_path_policy` contracts

## Boundary

CHECK.1 owns one deterministic transition:

```text
execution authorization
    + worker self-report
    + objective observed change facts
    + validation expectations / receipts
    + execution state bindings
    -> PostRunReconciliation
```

It answers exactly one question:

> Did the execution remain inside the contract it was given, and does its
> self-report agree with what objectively happened?

It does **not** answer:

> Was the implementation semantically good, and does it satisfy the goal?

That is CHECK.2 and is deliberately not implemented here. Every CHECK.1 result,
including a fully `reconciled` one, carries `semantic_goal_review_required`.

`core/post_run_reconciliation.py` is pure and import-time inert. Its only
project import is the frozen lexical `core.repository_path_policy`, from which
it takes exactly two names. It performs no repository traversal, source read,
validation execution, command execution, patch generation or application, model
call, network call, merge, or write.

## Why the phase exists

The project already had *pieces* of post-run safety: worker change notes
(`core.worker_result_review`), a prose-heuristic note-vs-diff check
(`core.mirror_tunnel_claim_diff_check`, MIRROR.3), an apply-time path gate
(`core.patch_safety`), a bounded patch-safety attachment (CTX.APPLY.0), a safe
validation runner (`core.validation_execution`), and validation side-effect
reporting (`core.validation_side_effects`).

None of them formed one authoritative reconciliation contract. MIRROR.3 in
particular scores *prose* claims against evidence with regular expressions;
CHECK.1 reconciles *typed* declarations against typed facts and never reads
prose. The two are complementary and neither replaces the other.

## Architectural split

Fact **collection** and fact **reconciliation** are separate modules:

| Concern | Module | Powers |
| --- | --- | --- |
| "Do the facts agree with the contract?" | `core/post_run_reconciliation.py` | pure; stdlib + one lexical path policy |
| "Shape already-collected facts; reuse the safety gate" | `core/post_run_observation.py` | may import `core.patch_safety`; still observes nothing itself |

The adapter never runs `git`, a subprocess, a validation command, or a
traversal, and never applies, reverts, resets, cleans, or stages anything.
Change records must already have been observed by a trusted upstream collector
and are passed through verbatim. Anything the adapter produces is marked
`facts_collected_externally = true`, which the result carries forward.

## Reused primitives

| Existing primitive | Reuse |
| --- | --- |
| `core.patch_safety.evaluate_patch_safety` | Single source of truth for blocked write paths. The adapter runs every *write-bearing* path through it and demotes anything it blocks to `forbidden`, carrying the gate's own category (`traversal` / `protected_dir` / `env` / `test` / `benchmark_validation`). |
| `core.repository_path_policy.is_safe_repository_relative_path` | Canonical repository-relative path spelling. CHECK.1 invents no second rule. |
| `core.file_capabilities` editability states | The `writable` / `writable_with_review` / read-only / generated / sensitive / outside-scope distinctions are mirrored into CHECK.1's bounded path-authority and forbidden-reason vocabularies rather than rediscovered semantically. |
| CTX.APPLY.0's writable-vs-validation-evidence split | Preserved as `supporting_read_only` and `validation_execute_only`: a file allowed to be *read* as evidence is not allowed to be *written*, and a validation file allowed to *execute* is not allowed to mutate. |

Deliberately **not** reused in the pure core: `core.validation_execution`
(imports `subprocess`), `core.worker_result_review` and
`core.mirror_tunnel_claim_diff_check` (regex prose heuristics), and every
patching, executor and repository-inventory runtime. Importing any of them
would falsify the inertness claim.

No second diff representation is created. Observed changes carry identity only.

## Supplied records

```text
AuthorizedPath:
    path
    authority                 writable | writable_with_review
                              | supporting_read_only | validation_execute_only
                              | forbidden
    forbidden_reason          (required iff forbidden)
    worker_id                 (optional per-worker ownership)

PathExpansionReceipt:
    path
    authority                 write-bearing only
    approval_receipt_sha256

ValidationExpectation:
    validation_id
    validation_kind           unit_tests | targeted_regression | static_check
                              | build | benchmark | invariant_check
    required
    target_scope[]
    expected_state_fingerprint   (optional)

PreservationObligation:
    obligation_id
    kind
    text_sha256
    certifying_validation_id     (optional)

ExecutionAuthorization:
    authorization_id, execution_run_id, repository_id
    task_contract_fingerprint
    pre_execution_state_fingerprint
    authorized_paths[], validation_expectations[]
    preservation_obligations[], path_expansion_receipts[]
    worker_id
```

The worker self-report is bounded and factual. There is deliberately **no**
free-prose verdict field — "everything looks good" has nowhere to live:

```text
DeclaredChange:
    path, change_kind, from_path
    expected_change_identity_sha256   (optional revision binding)

DeclaredValidationAction:
    validation_id | null, validation_kind, declared_result

WorkerReport:
    report_id, execution_run_id, worker_id
    declared_status           success | partial | failed | blocked
    declared_changes[]
    declared_validation_actions[]
    declared_limitations[]
    declared_unresolved_items[]
```

Observed facts are identity-only. No diff text, patch body, hunk, or file
content appears anywhere in CHECK.1:

```text
ObservedChange:
    path, change_kind          added | deleted | modified | renamed
    before_sha256, after_sha256
    from_path                  (renamed only)
    change_identity_sha256     derived

ValidationReceipt:
    receipt_id, validation_id
    execution_run_id, repository_id
    validation_kind, result, state_fingerprint, target_scope[]

ObservedPostRunFacts:
    facts_id, execution_run_id, repository_id
    pre_execution_state_fingerprint
    post_execution_state_fingerprint
    post_validation_state_fingerprint   (optional)
    final_state_fingerprint
    observed_changes[], validation_receipts[]
    rename_detection_supported
    facts_collected_externally
```

## Note vs diff

Observed facts outrank the self-report, always.

| Declared | Observed | Classification | Severity |
| --- | --- | --- | --- |
| A | A | `matched` | informational (blocked if the path is not writable) |
| A | A, B (B allowed) | B → `undeclared_change` | suspicious |
| A | A, B (B forbidden) | B → `undeclared_change` | **blocked** |
| A, B | A | B → `declared_but_unobserved_change` | suspicious |
| — | A | A → `undeclared_change` + `no_change_claimed_while_changes_observed` | suspicious |
| A | — | A → `declared_but_unobserved_change` + `changes_claimed_while_none_observed` | suspicious |
| A (modified) | A (added) | `declared_change_kind_mismatch` | suspicious |
| A (revision R1) | A (revision R2) | `declared_change_identity_mismatch` | suspicious |

An undeclared change is never silently normalised away, even when the path was
allowed: self-report fidelity is itself an audit property. A declared change
that was never observed never gains a fabricated diff.

## Path authority

`actual_changed_paths ⊆ authorized_change_paths` is a hard rule. The single
route to widening is an explicit `PathExpansionReceipt`, which:

- may grant only `writable` or `writable_with_review`;
- can never reach a path the authorization marks `forbidden` — an expansion
  receipt naming a forbidden path makes the whole fact set
  `inconsistent_input`;
- is recorded on the finding as `authorized_by_path_expansion_receipt`.

A forbidden path change is **blocked** regardless of whether the worker
declared it, whether every required test passed, whether the patch was minimal,
or whether the change was claimed to be necessary. Writing a
`supporting_read_only` file or a `validation_execute_only` file is likewise
blocked: read authority and execute authority are never write authority.

## Validation reconciliation

A required expectation is discharged only by a receipt that matches on
`validation_id`, `validation_kind`, `execution_run_id`, `repository_id`, any
declared `expected_state_fingerprint`, and **exact** `target_scope` equality.
There is no prefix, glob, or approximate test equivalence — a receipt for
`tests/test_parser.py` does not satisfy an expectation for
`tests/test_indexer.py`, and a broad receipt does not satisfy a narrow
expectation unless the upstream expectation declares the broader scope.

Coverage states: `satisfied`, `missing`, `failed`, `stale`, `scope_mismatch`,
`receipt_invalid`, `optional_missing`, `additional_observed`.

- A worker declaring a passing validation with no matching receipt yields
  `unverified_worker_validation_claim`. Prose never mints a receipt.
- A `skipped` receipt is not an execution.
- A receipt no expectation asked for is recorded as `additional_observed` and,
  because matching is keyed on `validation_id`, is structurally incapable of
  discharging a missing required expectation.
- A missing *optional* expectation warns; it does not block.
- A failed required validation is **blocked**, not merely incomplete. That is
  the deliberate policy choice: a red required check is a hard stop, while a
  missing or stale one is an unknown.

## Validation freshness

Validation is meaningful only for the state it validated.

```text
patch  -> state H1
validation passes for H1
another change -> final state H2
```

A passing receipt whose `state_fingerprint` is not `final_state_fingerprint` is
`stale`, the run is `incomplete`, and `validated_state_current` is false. No
rerun is attempted; CHECK.1 records the mismatch. This holds even when the
later change is itself authorized and declared — the phase fails closed rather
than reasoning that an A-only validation still covers A + B.

A supplied `post_validation_state_fingerprint` that differs from the final state
is separately recorded as `state_mutated_after_validation`.

## Worker status claim

The claim is reconciled against the facts, never accepted:

| Claim | Consistent when |
| --- | --- |
| `success` | no blocked finding, coverage complete, nothing stale, no undeclared or unobserved change, no kind/identity mismatch, no unverified validation claim |
| `partial` | no blocked finding |
| `failed` / `blocked` | no blocked finding (under-claiming is never punished) |

A `success` claim contradicted by the facts adds
`worker_success_claim_inconsistent`; any other contradicted claim adds
`worker_status_claim_inconsistent`.

## Status vocabulary

`reconciled`, `reconciled_with_warnings`, `incomplete`, `suspicious`,
`blocked`, `inconsistent_input`.

Precedence: `inconsistent_input` > `blocked` > `incomplete` > `suspicious` >
`reconciled_with_warnings` > `reconciled`.

There is deliberately no `semantically_correct`, `implementation_good`, or
`goal_satisfied` value, and the boundary suite asserts that no such key can
appear in a serialized result.

**`reconciled` means:** the observed execution facts agree with the bounded
execution contract, the worker self-report, path authority and required
validation receipts. **It does not mean** the implementation satisfies the
user's semantic goal. The result serializes that sentence as
`reconciled_meaning` so no downstream consumer can read it as a verdict.

## Preservation obligations and the CHECK.2 handoff

A carried obligation ("do not change embedding behavior") stays
`unresolved_semantic_check_required` unless a deterministic upstream validation
receipt explicitly certifies that exact obligation *and* binds the final state.
An obligation whose certifying validation is missing, failed or stale becomes
`certifying_validation_not_satisfied`. Path-level reconciliation never pretends
to prove semantic preservation, and an uncertified obligation caps the status at
`reconciled_with_warnings`.

Identical diff facts under a *change router behaviour* contract and a *preserve
router behaviour* contract therefore produce different preserved obligations and
different `task_contract_fingerprint` bindings, without either being judged.

CHECK.1 exposes to a future CHECK.2: changed paths and change identities,
execution scope and path authority, validation coverage and freshness,
preservation obligations, worker limitations and unresolved items, suspicious
mismatches, and the final state binding — but never source content.

## Fingerprints, tamper binding and determinism

Canonical SHA-256 identities bind the task contract, execution authorization,
worker report, observed fact set, every validation receipt, the request, and the
result. The request carries the expected fingerprints; the reconciliation
re-derives all of them.

| Tamper | Outcome |
| --- | --- |
| worker report edited after fingerprint | `inconsistent_input` |
| observed facts edited after fingerprint | `inconsistent_input` |
| authorization edited (e.g. widened) | `inconsistent_input` |
| validation receipt edited | `inconsistent_input` |
| final state moved (coherently re-fingerprinted) | receipts go `stale`, `incomplete` |

Structural coherence is also enforced: run and repository identity must agree
across the authorization, report, facts and receipts; the pre-execution state
must match the authorization; observed changes with an unmoved state, or a moved
state with no observed changes, break the state chain; and a `renamed` change is
rejected unless the collector declares `rename_detection_supported`.

Path, change and receipt input is unordered and canonicalises, so the same fact
set reconciles byte-identically whatever order it arrives in. Time, randomness
and machine state are absent.

## Renames

Renames are preserved only when the authoritative collector supports them. A
declared rename against an observed delete-plus-add is *not* matched: the delete
and the add are undeclared changes and the declared rename is a kind mismatch.
CHECK.1 performs no fuzzy rename inference.

## Authority and guardrails

`post_run_reconciliation_authority` is true only for a coherent supplied fact
set. Always false: `semantic_goal_review_authority`,
`implementation_correctness_authority`, `final_success_authority`,
`merge_authority`, `patch_authority`, `write_authority`,
`repository_read_authority`, `repository_traversal_authority`,
`validation_execution_authority`, `command_execution_authority`,
`model_selection_authority`, `provider_selection_authority`,
`final_response_authority`. `human_approval_required` is always true.

Honest true guardrails: `worker_report_reconciled`, `change_scope_checked`,
`declared_vs_observed_compared`, `validation_receipts_checked`,
`validation_freshness_checked`, `final_state_binding_checked`,
`facts_collected_externally` — each reported only when that work actually ran.
Always false: `repository_traversed`, `source_content_read`,
`validation_executed`, `patch_applied`, `files_modified`,
`semantic_goal_review_performed`, `model_called`, `conflict_resolved`,
`merge_performed`, `final_success_declared`.

## DeepSeek-style execution regression

```text
Worker reports:  core/router.py, core/session.py changed; tests passed
Actual:          core/router.py, core/session.py, core/config.py changed
Authorization:   router/session writable; config forbidden
Receipt:         passed, bound to the state before config.py changed
```

Result: `undeclared_change_observed`, `forbidden_path_changed`,
`validation_stale_for_final_state`, `worker_success_claim_inconsistent`,
status `blocked` — derived with no semantic reviewer, no model, and no test
execution.

## No success laundering

`tests_passed -> overall_success` is structurally impossible. A run reaches
`reconciled` only with clean scope, a consistent report, complete required
validation coverage, fresh validation and no forbidden change — and even then
`reconciled != semantically_correct`, and `semantic_goal_review_required` plus
`human_review_required` remain outstanding.

## Known limitations

1. **No upstream producer.** No production phase currently emits an
   `ExecutionAuthorization`, a typed `WorkerReport`, an `ObservedPostRunFacts`
   set, or a `ValidationReceipt`. Today's worker notes are prose and today's
   validation runner returns an untyped result. Tests and fixtures are CHECK.1's
   only callers.
2. **No collector.** The observation adapter shapes facts; it does not collect
   them. A separately governed collector that turns a real repository state into
   `ObservedChange` records is future work.
3. **Worker ownership is optional.** When the authorization exposes no
   per-worker path ownership, the result reports
   `worker_scope_ownership_unavailable` rather than inventing an owner.
4. **One execution unit.** No cross-worker aggregation, majority, or voting.
   Multi-worker merge arbitration would be a separate CHECK.MERGE.1.
5. **No repair loop.** CHECK.1 never asks a worker to revise its note, so an
   original mismatch stays auditable. Any future repair must preserve the
   original evidence.
6. **Fail-closed scope equality.** Exact `target_scope` equality means a broad
   validation receipt does not satisfy a narrow expectation. Widening that
   requires an upstream expectation change, not a heuristic here.
7. **Windows path guard.** `Path("/etc/passwd")` is not absolute on Windows, so
   the frozen lexical path policy admits a POSIX-rooted spelling.
   `core.patch_safety` already guards that exact shape at apply time; CHECK.1
   adds the same leading-separator rejection rather than editing the frozen
   module.

## Not wired

No Commander, Instant Run, Project Evolution, Workbench, Mixed Mode, executor,
merge path, or response generation imports or calls CHECK.1. Existing checker,
note-vs-diff and patch-safety behaviour is unchanged by this slice; the boundary
suite asserts both facts.

## Recommended next phase

**CHECK.2 — Semantic Goal-Fidelity Review.** It may consume the TaskContract,
the preservation obligations CHECK.1 preserved, bounded diff/change evidence
under a separate read authorization, and the CHECK.1 reconciliation facts, and
answer: *did this execution actually satisfy the intended semantic goal, and did
it violate a preserved behaviour?* CHECK.2 may use a reviewer model; CHECK.1
never does. It should not run unless CHECK.1 first reports a status that makes
semantic review meaningful.
