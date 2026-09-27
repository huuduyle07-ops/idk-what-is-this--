# CHECK.LIVE.1 — Shadow Post-Run Reconciliation Wiring

**Status:** complete, shadow-only, default off
**Date:** 2026-08-28
**Depends on:** CHECK.1 (frozen). Not CHECK.2.

## The question this phase answers

CHECK.1 shipped with a documented gap: *"No production phase currently emits an
`ExecutionAuthorization`, a typed `WorkerReport`, an `ObservedPostRunFacts` set,
or a `ValidationReceipt`."* Its only callers were tests.

So the open question stopped being *how should post-run reconciliation work?*
and became:

> Does the live execution path actually emit the typed receipts and facts
> CHECK.1 requires?

CHECK.LIVE.1 answers it by wiring the frozen checker into a real apply path in
shadow mode and letting it disagree out loud.

## Boundary

```text
                      execution (unchanged)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   authoritative run result          typed live facts
        (UNCHANGED)                          │
                            ┌────────────────┼────────────────┐
                            ▼                ▼                ▼
                  ExecutionAuthorization  WorkerReport  ValidationReceipt
                            │                │                │
                            └────────────────┼────────────────┘
                                             ▼
                                   ObservedPostRunFacts
                                             ▼
                                    CHECK.1 (frozen)
                                             ▼
                              ShadowPostRunCheckReceipt
```

The shadow result is stored **beside** the run result, never in place of it.

## The live execution path, as it actually is

Traced before anything was written:

```text
web/runner.py :: run_agent_web
    → harness gate → repository inventory → index → CONTROL → preflight
    → run_draft_pipeline → run_review_pipeline → finalize_answer
    → run_postprocess_gate_battery → harness gate again
    → core/pipeline.py :: maybe_run_auto_patch
         ├── patch_plan branch → core/run_lifecycle.py ::
         │       run_patch_plan_with_artifacts
         │         → collect_brain_stamp
         │         → create_replay_bundle (.agent/replays/<id>)
         │         → evaluate_patch_safety(plan target paths, project_root)
         │         → patching/patch_plan_executor.py :: apply_patch_plan
         │              → per-op write (create_file | replace_snippet)
         │              → snapshot_repo_files (pre-validation)
         │              → run_validation_command / run_safe_validation_command
         │              → snapshot_repo_files (post-validation)
         │              → diff_validation_side_effects
         │              → rollback on failure (LIFO, patch ops only)
         │         → write apply_result.json / validation_output.txt / events
         │         → finalize_replay_bundle
         └── patch_candidate branch → core/self_correct_loop.py
                 → core/executor.py :: Executor.run
                      → dry_run → evaluate_patch_safety
                      → patching/patch_engine.py :: apply_patch_from_json
                      → snapshot / validate / snapshot → rollback on failure
    → save_message → result dict → web response
```

Two apply engines, one shared safety gate, one shared side-effect collector.

## Integration point, and why it is genuinely post-mutation

CHECK.LIVE.1 is wired into **`core.run_lifecycle.run_patch_plan_with_artifacts`**,
immediately after the rollback event and immediately before `finish(...)`.

At that point:

- every patch operation has been written or reverted (`apply_patch_plan` has
  returned, and rollback is LIFO-complete inside it);
- the one validation has run and its result is known;
- the validation side-effect diff has been computed;
- the replay bundle has recorded `apply_result.json`;
- **nothing below writes to the worktree** — `finish()` only writes
  `final_status.json` and refreshes the bundle manifest.

That is the true terminal boundary for this path. Ordering:

```text
apply ops → validation → side-effect diff → rollback (if any)
    → final observed state captured
    → CHECK.1 shadow invocation
    → shadow receipt persisted into the existing bundle
    → existing authoritative terminal response
```

### What is deliberately not wired

| Path | Status | Why |
| --- | --- | --- |
| Patch-plan apply (`run_lifecycle`) | **wired** | shares the safety gate, the side-effect collector and the replay bundle; used by the web app, patch routes, pipeline auto-patch, worker-run import, sleeping consultant and the proposal-queue script |
| Single-file `Executor` / self-correct loop | not wired | `apply_patch_from_json` returns replaced *snippets*, not before/after file identity, so no honest content digest exists; `core/executor.py` is frozen for this phase |
| `dry_run_only` / preview | not wired | never mutates, never reaches the post-run boundary; a write-oriented reconciliation does not apply |
| Commander multi-worker units | not wired | no per-worker path ownership exists to bind; recorded as `worker_ownership_unavailable` rather than guessed |

## Producers

Each producer translates a fact the run already held. None discovers anything.

### ExecutionAuthorization — `core/live_execution_authorization.py`

Source of authority: the **same `evaluate_patch_safety` verdict the apply path
already computed** against the real project root, over the plan's own target
paths. Blocked paths become `forbidden` carrying the gate's own category;
everything else the run treated as writable becomes `writable`.

The result is then passed through the frozen
`core.post_run_observation.classify_authorized_paths`, which re-runs the gate
and demotes anything it blocks — so a caller that believes a path is writable
cannot launder it in.

Monotonicity is explicit and two-sided: the producer takes both what upstream
recorded and what the caller wants represented, and raises
`LiveAuthorityWideningError` if the second is stronger than the first, if it
relabels read authority as execute authority, or if it names a path upstream
never authorized. No `PathExpansionReceipt` is ever minted.

`authorization_id` is `live-auth-<sha256[:32]>` over the run id, the repository
id and the upstream authority fingerprint, so changing the upstream gate verdict
changes the produced authorization fingerprint.

### WorkerReport — `core/live_worker_report.py`

Built from structure only:

| Live fact | Typed declaration |
| --- | --- |
| `{"op": "create_file", "relative_path": p}` | `DeclaredChange(p, added)` |
| `{"op": "replace_snippet", "relative_path": p}` | `DeclaredChange(p, modified)` |
| unknown op type | not declared; recorded as `typed_worker_fact_unavailable` |
| `success and not rollback_performed` | `declared_status = success` |
| blocked | `declared_status = blocked` |
| otherwise | `declared_status = failed` |
| validation executed + ok | `DeclaredValidationAction(..., passed)` |
| validation not executed | no action at all |

There is **no `re` import**, no completion-note read, no diff parse and no model
call. Existing completion prose is untouched; the typed report is additive and
renders nothing.

### ValidationExpectation / ValidationReceipt — `core/live_validation_receipt.py`

One expectation is emitted only when the run structurally requested a
validation; when it did not, none is emitted and
`validation_expectation_missing` is recorded rather than a required check being
invented. The validation *kind* is a fixed declared mapping
(`unit_tests`) because the live runtime holds one project validation command and
no taxonomy — it is never inferred from command text or changed filenames.

Receipt results preserve four distinct states:

| Live outcome | Receipt |
| --- | --- |
| ran, ok | `passed` |
| ran, not ok | `failed` |
| runner crashed | `errored` |
| refused (unsafe legacy shell under an automation policy) | `skipped` |
| never ran | **no receipt** — the expectation stays `missing` |

A failed validation still produces a receipt. Reserving receipts for passing
checks would make a red required check indistinguishable from a missing one, and
CHECK.1 treats those very differently (blocked versus incomplete).

### ObservedPostRunFacts — `core/live_change_observation.py`

The one genuinely new collector, and the narrowest possible one. It imports
neither `os` nor `glob`, so it **structurally cannot enumerate a directory**;
it digests only paths it is handed.

```text
pre-apply    digest_known_paths(root, plan target paths)
                 ↓ (apply, validate, maybe roll back)
post-run     digest_known_paths(root, plan paths ∪ side-effect paths)
                 ↓
             derive_observed_change_records(before, after)
```

Side-effect paths come from the **existing** `diff_validation_side_effects`
report, which the apply path already produced from its own pre/post-validation
snapshots. A path the collector reports as *created* during validation was
absent when validation started, and the patch engine writes only plan paths, so
its pre-apply absence is an observation rather than a guess and it types
cleanly as `added`.

Actual facts outrank the intended patch: a validation side effect that the plan
never named appears in the observed set, is undeclared, and is outside the
authorized scope.

Honest gaps are recorded, never filled:

- a path whose *before* identity was never observed (a side effect that
  modified or deleted a file outside the plan) is `untyped`, and the receipt
  reports `observed_change_identity_incomplete`;
- a rolled-back run reports the same code, because the patched state existed
  between apply and rollback and was never digested;
- a file larger than 8 MiB, or one that cannot be read, is recorded rather than
  digested.

`rename_detection_supported` is `False`: nothing in the live path
authoritatively reports a rename, so a delete plus an add stays a delete plus an
add.

## State identity

CHECK.1 needs state identity for validation freshness. A full-repository hash
would regress the whole indexing philosophy, and a timestamp, run id or UUID
would not be a *state* identity at all. So the identity is the **canonical
observed-change-set fingerprint**:

```text
state = sha256(canonical_json({
    state_kind, phase_id,
    repository_id,
    base:    pre-apply digests of the observed path set,
    changes: the observed change set,
}))
```

Assignments:

| CHECK.1 field | Value |
| --- | --- |
| `pre_execution_state_fingerprint` | `F(base, ∅)` |
| `post_execution_state_fingerprint` | `F(base, final changes)` |
| `post_validation_state_fingerprint` | `F(base, final changes)` — nothing mutates after validation on this path |
| `final_state_fingerprint` | `F(base, final changes)` |
| `ValidationReceipt.state_fingerprint` | `F(base, final changes − validation-window changes)` |

Three properties follow by construction, and CHECK.1 depends on all three:

1. **A no-op does not break the state chain.** An empty change set fingerprints
   identically to the pre-execution state, which is exactly what CHECK.1
   requires when `observed_changes` is empty.
2. **Any real change moves the identity.** A different path, kind or content
   digest produces a different fingerprint. No clock, randomness or machine
   state takes part, so the same actual state always fingerprints identically.
3. **Stale validation is detectable.** If validation mutated anything in the
   observed set, the validated state is not the final state, and CHECK.1 marks
   the receipt `stale`.

### The one honest imprecision, stated

The validated state is *reconstructed*: the final change set minus whatever the
authoritative side-effect collector attributes to the validation window, rather
than a digest taken between apply and validation. Inserting a real observation
point there would require editing `patching/patch_plan_executor.py`, which this
phase deliberately does not touch.

The reconstruction is exact where CHECK.1 uses it. Freshness only matters for a
*passing* receipt, and a passing validation never triggers a rollback, so the
final state is the state that was validated whenever it matters. Where it does
not matter — a failed receipt, which CHECK.1 blocks on regardless of freshness —
the run is additionally marked `observed_change_identity_incomplete`.

## Shadow receipt

```text
ShadowPostRunCheckReceipt:
    execution_run_id            the replay bundle's own id
    repository_id               canonical path-derived identity
    authoritative_run_status    success | failed | blocked | not_reached
    authoritative_effect        always False, not a settable field
    shadow_outcome              evaluated | not_reached
                                | producer_unavailable | checker_error
    reconciliation_status       copied from CHECK.1, or null
    reconciliation_fingerprint  CHECK.1's own result identity
    producer_completeness       complete | partial | unavailable
    missing_live_facts[]        bounded vocabulary
    disagreement                none | checker_stricter_than_run
                                | checker_weaker_than_run | not_comparable
    disagreement_reasons[]      CHECK.1's own bounded inconsistency codes
    shadow_error_category       one of six bounded categories, or null
    observation                 bounded counts, paths and flags
    reconciliation              the frozen CHECK.1 result, verbatim
```

`authoritative_effect` is a property, not a constructor field: there is no state
of this phase in which the shadow check may affect the run it observed.

The CHECK.1 result is carried whole because there is nowhere else to reference
it from — and it is safe to carry: CHECK.1's own boundary suite proves it holds
only paths, change kinds, digests and bounded reason codes, never a diff, patch
body or source byte.

### Producer completeness

Three explicit bands, no numeric score. `task_contract_unavailable` and
`worker_ownership_unavailable` are excluded from the band because no
CHECK.LIVE.1 producer could repair them — the upstream contracts that would
supply them do not exist — and CHECK.1 already reports the second honestly. They
remain listed so a reader sees them.

### Disagreement

The single most valuable output of shadow mode:

```text
authoritative: success        CHECK.1: blocked
    → checker_stricter_than_run
    → reasons: forbidden_path_changed, out_of_authorized_scope_change,
               validation_stale_for_final_state, ...
```

Measured across real runs, this is the dataset that decides whether CHECK.1 is
ready to be promoted.

## What the wiring may not do

`if forbidden_path: status = blocked` appears nowhere in the live path. The
boundary suite proves that `reconcile_post_run` is called from exactly one
module, that a shadow reconciliation status can only be copied from the CHECK.1
result attribute or be null, and that no CHECK.1 status vocabulary is redefined
locally. One reconciliation policy, in one frozen module.

Where live producer data did not satisfy CHECK.1, the producer or the recorded
missing fact was fixed. CHECK.1 was not weakened. Its two core modules are
unmodified and are in this phase's `forbidden_files`.

## Failure isolation

`safe_run_shadow_post_run_reconciliation` converts every failure into one of six
bounded categories — `producer_input_error`, `producer_bound_exceeded`,
`authority_widening_refused`, `reconciliation_contract_error`,
`artifact_persistence_failed`, `unexpected_shadow_error` — with no traceback,
command text, environment value or secret serialized anywhere. The original
application, validation or worker failure remains the authoritative result. A
shadow error never produces a fake `reconciled` status.

An execution that ends before the post-run boundary (patch-safety block, unsafe
validation refusal) records `not_reached` with
`execution_did_not_reach_post_run_boundary`, not an empty successful
reconciliation.

## Persistence and compatibility

No second run-history store. The receipt is one additive JSON artifact,
`post_run_reconciliation_shadow.json`, inside the replay bundle the run already
created, bound to that run's replay id and repository id. The only schema change
is one name added to `core.replay_recorder.JSON_ARTIFACT_NAMES` — additive and
migration-safe, because `files_present` is derived from disk. Bundles written
before this phase load fine and report `reconciliation_available = false`.

`run_progress` UX is untouched. The apply result carries four additive,
non-authoritative metadata keys when the flag is on and nothing when it is off.

## Feature flag

`POST_RUN_RECONCILIATION_SHADOW`, **default off**.

Off is the right default while the checker's false-positive rate is unmeasured:
a new checker must not change production behaviour, not even additively. Off
means the apply path takes no extra read, writes no extra artifact and returns a
byte-identical result dict. On means observation only — the regression suite
asserts zero extra validation executions, zero extra patch applications, zero
extra model calls and zero extra repository walks against an instrumented
baseline.

## Measured cost

Instrumented baseline versus shadow on one real patch-plan run with a passing
validation:

| Metric | Baseline | Shadow | Delta |
| --- | --- | --- | --- |
| repository-rooted enumerations (`os.walk`) | 2 | 2 | **0** |
| validation executions | 1 | 1 | **0** |
| patch applications | 1 | 1 | **0** |
| model calls | 0 | 0 | **0** |
| network calls | 0 | 0 | **0** |
| artifact-store `iterdir` (bundle manifest refresh) | 12 | 14 | +2 |
| bounded file digests | 0 | N + M | N = plan paths, M = side-effect paths |

The two repository walks are the pre/post-validation snapshots the apply path
already took. The +2 enumerations are the artifact store listing its own replay
bundle when the additive event and receipt are written — the same bookkeeping it
already does for every artifact.

Wall-clock: the producers plus the frozen CHECK.1 invocation take a **median
2.3 ms** (p95 3.5 ms) for a three-file change. End-to-end run time is dominated
by the validation subprocess spawn (130–400 ms on the measurement machine), so
the shadow step sits below run-to-run noise; the structural deltas above are the
meaningful guarantee, and they are asserted by instrumented regressions rather
than by a wall-clock threshold, which this repository has no convention for.

## Observed live behaviour

Real runs through the wired path:

| Run | Authoritative | Shadow CHECK.1 | Why |
| --- | --- | --- | --- |
| patch + passing validation | success | `reconciled` | declared = observed, receipt binds the final state |
| patch + validation that creates a file | success | `blocked` | undeclared + out-of-scope change, and the receipt no longer binds the final state (`stale`) |
| patch + failing validation | failed (rolled back) | `blocked` | typed receipt `failed`; declared change never observed after rollback |
| apply failure before validation | failed | `incomplete` | `required_validation_missing`, not a false `failed` |
| genuine no-op | success | `suspicious` | a declared change that did not materialise |
| plan wider than the receipt scope bound | success | `suspicious` | validation passed but no receipt could be bound: `unverified_worker_validation_claim` |
| patch-safety block | failed | *not reached* | no facts, no fabricated reconciliation |

Every authoritative outcome is what it was before this phase.

## Progress UI

Deferred, deliberately. The run-progress shadow writer has a closed stage
vocabulary with its own required-field contract, loader and panel tests, and
`core/run_progress_snapshot_shadow_writer.py` is outside this phase's allowed
files. Adding a `post_run_reconciliation` stage would be a UX change with
regression surface, and §77's own instruction is to defer in exactly that case.
The receipt is discoverable from the replay bundle in the meantime.

## Dogfood measurement

`summarize_shadow_post_run_checks(replay_dirs)` is a read-only aggregation over
receipts that already exist. It runs no execution of any kind and returns
categorical counts only — authoritative run status, reconciliation status,
shadow outcome, producer completeness, disagreement direction, missing-fact
codes and CHECK.1's own inconsistency codes. It exists so that one question is
directly answerable:

> Across real C.A.T.T.U.S runs, how often would CHECK.1 have disagreed with the
> current executor?

The report carries `counts_decide_nothing = True`. Counts measure the checker;
they never decide whether a run was correct.

## Known limitations

1. **The live worker report cannot lie about paths.** The declaration and the
   authorization are both derived from the same patch plan, so an
   undeclared-but-authorized change is structurally unreachable through the
   wired path today. The note-versus-diff failure mode CHECK.1 was built for
   needs a worker whose declaration is *independent* of the applied operations.
   The producers classify it correctly when given such a fact set; nothing in
   production produces one yet. This is the single most important finding of
   the phase.
2. **`forbidden_path_changed` is unreachable through the wired path.** The apply
   gate refuses a plan naming a forbidden path before writing anything, so a
   forbidden change surfaces as an out-of-scope side effect instead. Both block.
3. **Validation side effects dominate the disagreements.** Any run whose
   validation writes a non-excluded file lands `blocked`. That is CHECK.1
   behaving correctly, and it is exactly the frequency this phase exists to
   measure.
4. **The validated-state reconstruction** described above.
5. **One execution unit.** No cross-worker aggregation; no `CHECK.MERGE.1`.
6. **No TaskContract.** The `task_contract_fingerprint` is a live *task-shape*
   fingerprint over the plan's operations, recorded alongside
   `task_contract_unavailable` so it is never read as an INPUT.1 binding.
7. **The single-file executor path is unobserved.**

## CHECK.2 handoff readiness

| CHECK.2 input | Available? |
| --- | --- |
| execution run identity | yes |
| final-state identity | yes |
| CHECK.1 reconciliation | yes |
| preservation obligations | only if an upstream contract supplies them — none does |
| TaskContract | no |
| requirement ledger | no |
| goal → proposition binding + polarity | no |
| post-run ClaimAssessment | no |

None of the missing ones are manufactured. CHECK.2 is not invoked, and the
boundary suite asserts it is unreachable from the live wiring.

## Recommended next phase

**CHECK.LIVE.2 — Semantic Producer Wiring.** Two candidate slices, in order of
dogfood value:

1. **An independent worker declaration.** Give the worker/commander path a typed
   change declaration that is produced *before* and *separately from* the applied
   operations, so declared-versus-observed becomes a real measurement rather
   than a tautology. This is what unlocks the failure mode CHECK.1 was designed
   for.
2. **Semantic inputs for CHECK.2.** Project the INPUT.1 TaskContract into the
   apply path, build a typed requirement ledger, mint explicit obligation →
   proposition polarity, reuse ACQUIRE → EVIDENCE → CLAIM for post-run
   assessments, and invoke frozen CHECK.2 in shadow mode.

Only after real dogfood data exists should **CHECK.GATE.1** consider promoting
proven CHECK.1/CHECK.2 results into authoritative human-acceptance gating. Not
now.
