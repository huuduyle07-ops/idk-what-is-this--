# DATA.ROLLBACK.1 — Verified Rollback Truthfulness

Date: 2026-09-14  
Finding: DATA-02  
Track: HARDEN

## Scope and invariant

This phase changes rollback reporting, verification, and failed-rollback data
retention only. A current receipt may set `rollback_performed=true` only when
the final scoped filesystem state was independently compared with the exact
pre-mutation baseline and every target matched. Calling or returning from a
restore primitive is never sufficient.

EXEC.PLAN.1 preparation, transaction snapshot/recovery mechanics, and its
`mutation_attempted`, `recovery_attempted`, `recovery_complete`,
`remaining_changed_paths`, and `remaining_created_directories` computation are
unchanged. DATA.UNDO.1, AUTH.DREAM.1, SEC.UI.1, Track A, and all authority and
candidate-selection rules are unchanged.

## Producers and consumers

The bounded production audit found three mutation rollback mechanisms:

1. `patching.patch_plan_executor`, backed by the frozen
   `patching.patch_plan_transaction` recovery algorithm.
2. `core.executor`, whose single-file path restores a `.bak` file after a
   post-apply risk refusal or unsuccessful validation.
3. The optional `core.mutation_oracle`, invoked only by `core.executor` in
   production. Its frozen implementation reuses the enclosing `.bak`. The
   executor guards this call with a separate, verified original baseline,
   compares post-oracle bytes against the validated patch, and recovers the
   original baseline if the oracle leaves an unresolved mutant. The oracle's
   scoring, selection, mutation mechanism and source bytes remain unchanged.

`core.validation_side_effects` decorates both result families.
`core.run_lifecycle`, `core.execution_outcome_telemetry`, `core.pipeline`, the
web patch routes/session history, the patch-attempt database projection,
post-run reconciliation, sleeping-consultant artifacts, and lesson builders
consume their results. Current serializers consume the typed outcome. The
database's existing boolean column remains a compatibility projection of the
typed `performed` property; no database migration rewrites historical rows.
`graph.penalty` consumes that database column as one failure signal; its frozen
scoring is unchanged. Because the column now records verified success only, a
`post_apply_blocked` or `oracle_recovery_failed` attempt whose rollback is
measured incomplete is not counted through that column (validation failures
are still counted through the phase and `validation_ok` columns); penalty
scoring and the database schema stay outside this phase, so the delta is
recorded rather than changed.

`core.run_lifecycle` translates the plan outcome for two further consumers. Its
replay event stream records `rollback_performed` only for verified completion
and `rollback_incomplete` (status, unresolved paths and directories, artifact
IDs, material error) for incomplete or unverifiable recovery, so silence never
implies recovery. The frozen post-run shadow input named `rollback_performed`
has always meant that a patched state existed and was reversed before the final
digest; it receives the typed `attempted` fact, so a failed or partial reversal
still marks the observed change identity incomplete, while a failure before
any mutation does not. The frozen benchmark `detect_rollback` text heuristic
counts rollback mentions for benchmark history, including ambiguous mentions;
it is not a current execution receipt or verification authority. Lesson
eligibility uses a conservative negative-evidence projection: failed recovery
and historical rollback claims still disqualify success evidence.

Historically, plan `_failed_result` set `rollback_performed=true` before the
outer transaction attempted recovery, and the single-file executor set it
after `restore_backup()` returned. Neither meaning proved final bytes.

## Authoritative outcome

`core.rollback_outcome.RollbackOutcome` is immutable and uses this closed
status vocabulary:

- `not_required`: no rollback was required.
- `not_attempted`: recovery was required but policy did not attempt it.
- `completed_verified`: recovery was attempted and final state matches the
  authoritative baseline.
- `incomplete`: final inspection completed and identified exact unresolved
  paths/directories.
- `unverifiable`: the final state could not be inspected reliably.

The object separately carries `attempted`, `completed`, `verified`, remaining
paths/directories, bounded failure code/reason, emergency artifact IDs, and
final-state truth. Its constructor rejects contradictory combinations.
Compatibility fields, including `rollback_performed`, are emitted only from
this object. Typed executor facts take precedence over legacy/default metadata;
a later filesystem observation can refute earlier success. A content-only
observation cannot clear unresolved directories, modes, unknown targets, or a
different attempt's baseline. Failed attempt facts and recovery locators are
preserved across aggregate receipts. The correction loop stops on incomplete
or unverifiable recovery before another attempt can overwrite its baseline.

The rollback outcome wire schema is
`data_rollback_1_outcome_v1`. Execution telemetry is versioned from
`exec_auth_live_1_execution_telemetry_v1` to `v2` because its existing
`rollback_performed` semantics materially changed and it now embeds the typed
outcome. Historical payloads are not rewritten. A legacy true boolean loads
as `unverifiable`. Missing evidence defaults conservatively with
`final_state_verified=false`, including a receipt that is not a mapping at all;
malformed or unsupported typed evidence becomes `unverifiable` and cannot fall
back to an older success field. A typed success is not accepted beside measured
unresolved transaction facts in the same receipt (`recovery_complete=false` or
non-empty remaining sets): that conflict loads as `unverifiable` with
`conflicting_rollback_evidence`.

`patch_ops_rollback_protected=true` retains its existing capability meaning:
the execution path has patch-operation rollback machinery. The additive
`patch_ops_rollback_protection_semantics="capability_only"` marker prevents it
from being interpreted as the result of this run. Actual success is solely
`rollback_outcome.status=completed_verified`.

## Verification and final state

The plan adapter consumes EXEC.PLAN.1 transaction facts directly. Complete
recovery plus empty remaining sets maps to `completed_verified`; incomplete
recovery maps to `incomplete`. It does not reimplement the recovery algorithm.

The single-file owner reads the exact backup bytes, attempts restore, and reads
the target again. A raised restore, silent no-op, partial recovery, or external
write that leaves a mismatch cannot report success. An unreadable final target
is `unverifiable`. Where state is unobservable, `final_repository_changed`
fails closed to true and `final_state_verified=false`; where it is observable,
the actual byte/hash comparison determines the result.

Validation side-effect metadata never defaults rollback success to true. Its
rollback protection field remains capability-only and its decorator applies
the typed outcome last, so a default cannot overwrite measured failure.

## Emergency recovery artifacts

`core.failed_rollback_recovery` persists material only for incomplete or
unverifiable automatic recovery. Artifacts live under
`.agent/failed_rollback_recovery/v1` and bind:

- opaque artifact identity;
- canonical repository identity;
- exact repository-relative target;
- server-generated source execution identity;
- exact baseline existence/bytes/hash and file mode when owned by the plan;
- observed unresolved post-failure existence/hash when readable;
- originating rollback status.

The bytes and manifest are written atomically and read back for integrity
verification. IDs are locators for manual repair only; there is no restore
endpoint and `automated_restore_authority=false`. These artifacts are not
DATA.UNDO.1 backup IDs and cannot be consumed by its Undo API. Successful
verified rollback creates no emergency artifact and removes the ordinary
single-file `.bak`; incomplete single-file recovery retains both its existing
backup and the bound emergency copy.
Cleanup failures are reported separately and do not discard verified rollback
truth. Operator text on every current surface (single-file executor, plan
executor, execution telemetry, web API) comes from one presenter over the
outcome: complete material reads as available, partial persistence as only
partially available, a store failure as not fully persisted, and absent
material as not recorded; a policy-disabled rollback reads "not attempted"
rather than "failed". Emergency and Undo IDs share one 64-hex format, so their
separation is enforced by store location and manifest schema and is tested in
both directions. Artifact destination components and target components reject symlinks
and Windows reparse points, including junctions. Destination checks run before
each committed write and integrity read. Invalid/empty store requests create
no directories. Source identities and originating failure statuses are checked.

Web and Dream dry runs use disposable clones. Their final responses retain
clone-scoped rollback truth, explicitly identify that scope, and clear material
locators before the clone is removed. They do not promise durable access to a
deleted clone. Manual Apply failure messages use the final telemetry outcome,
and the single-file response's `failure_info` keeps its validation cause while
its rollback code and reason are rendered from that same final outcome.

## Boundaries and performance

Only named patch targets are inspected; no repository traversal was added to
rollback verification or artifact persistence. Existing process-local plan and
web Undo locks remain as-is. There is no cross-process compare-and-swap claim:
an external write observed during verification produces mismatch/incomplete or
unverifiable truth. This phase does not claim power-loss or process-kill crash
recovery; it addresses normal-process failure and durably retains material when
the artifact write completes.

Normal failure recovery adds bounded final reads/hashes proportional to named
target bytes; normal successful mutation uses the same bounded comparison.
Typed outcome construction is constant-sized aside from sorted named paths.
Emergency artifact I/O occurs only on incomplete/unverifiable rollback and is
proportional to unresolved baseline bytes. Model calls and external network
requests are zero.
