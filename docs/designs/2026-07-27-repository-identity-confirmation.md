# Repository Identity Confirmation and Architecture Epoch State

**Phase:** `INDEX.1D.2B`

**Date:** 2026-07-27

**Status:** Implemented

## Mission and boundary

INDEX.1D.2B defines the persistent, human-confirmed identity gate for the
Canonical Incremental Graph.

It answers one question:

```text
Is this repository identity confirmed strongly enough to permit a canonical
build, refresh, reconciliation, or identity-layer manifest advancement?
```

The answer is represented by an immutable state record, deterministic
transition helpers, and an explicit permission matrix in
`core/repository_identity_state.py`.

This is an identity-authority contract, not a graph-operation lifecycle or a
completion contract:

- INDEX.1D.1 continues to own graph kinds and operational states such as
  `building`, `refreshing`, and `current`.
- INDEX.1D.2A continues to own canonical-root, `repository_id`, `storage_key`,
  and strict `index_scope` derivation.
- INDEX.1D.2B owns human semantic confirmation, major-change review, and
  architecture-epoch identity authority.
- INDEX.1D.2C must later prove honest persistence completion before an applied
  manifest can actually advance or a repository can claim trusted-current
  status.

INDEX.1D.2B does not scan a repository, build or refresh a graph, call a model,
access a database, inspect or advance a manifest, reconcile rows, execute an
Activation Graph, migrate legacy namespaces, or delete old state.

## Persistent state record

`RepositoryIdentityState` records:

- schema and artifact identity;
- immutable physical repository identity;
- current and candidate semantic labels;
- the active architecture epoch and strict index scope;
- the preceding scope and complete archived-epoch history;
- the latest applied human confirmation;
- advisory major-change signals and evidence;
- supplied legacy-namespace warnings;
- derived canonical identity permissions;
- Activation Graph independence metadata;
- the 1D.2C completion boundary; and
- a monotonic state revision.

The important authority fields are:

```text
repository_id
canonical_root
storage_key
identity_status
project_tag
candidate_project_tag
architecture_epoch
active_index_scope
confirmation
major_change
archived_epochs
permissions
permission_layer = "identity_only"
trusted_completion_required = true
trusted_completion_phase = "INDEX.1D.2C"
state_revision
```

`repository_id`, `canonical_root`, and `storage_key` are immutable across every
ordinary transition. The active scope must always be derivable from the stored
repository ID and epoch by the 1D.2A primitive. A project tag never substitutes
for either physical identity or strict database scope.

Persisted permissions are redundant by design: they make authority visible in
the artifact, but validation recomputes them and rejects any contradiction.

## Stable identity statuses

### `uninitialized`

No `identity_state.json` artifact exists.

This status is an in-memory missing-artifact view with revision zero. It is
never serialized. The repository already has a strict 1D.2A index scope, but
every canonical mutation permission is false.

The only persistable transition from this view is:

```text
uninitialized -> initial_confirmation_required
```

### `initial_confirmation_required`

Physical repository identity is known, but no human-confirmed semantic project
label exists.

Invariants:

```text
project_tag = None
human_confirmation_required = true
state_revision = 1 on first persistence
all canonical mutation permissions = false
```

A supplied or 1D.2A-derived candidate tag may be recorded as
`candidate_project_tag`, but it grants no authority and is never inferred as
confirmation.

### `confirmed`

The semantic project label and active architecture epoch have an explicit human
decision. The confirmation record contains a timezone-aware timestamp, a human
actor, and a bounded reason.

The identity layer permits canonical build, refresh, reconciliation, and
manifest advancement. This does not prove that any operation completed
successfully, and `trusted_current_claim_allowed` remains false.

### `major_change_confirmation_required`

A positive advisory major-change candidate was applied to a confirmed state.

Entering review preserves:

```text
repository_id
project_tag
architecture_epoch
active_index_scope
archived epoch history
```

All canonical mutation permissions become false until an explicit human
decision resolves the review.

### `archived`

An archived epoch is readable historical repository intelligence. It has:

```text
readable = true
writes_allowed = false
reconciliation_allowed = false
deleted = false
```

New-epoch transitions append `ArchivedEpochRecord` entries to the active state,
so repeated epoch changes preserve complete history. Archived history cannot be
removed or rewritten by a later transition. An archived top-level state is
terminal and cannot be reopened in place.

### `blocked`

Malformed, unsafe, contradictory, unsupported, or wrong-repository state fails
closed as an explicit blocked view.

Blocked state cannot self-heal through the ordinary save or confirmation API,
and it is not serializable as a replacement artifact. Repair or recreation
requires a separately authorized future workflow.

## Human decisions

Every decision requires explicit caller-supplied values:

```text
decision
confirmed_at
confirmed_by
reason
```

`confirmed_at` must be a timezone-aware ISO timestamp. `confirmed_by` must be
`human` or begin with `human:`. No timestamp, actor, reason, project tag, or
decision is inferred.

### `same_project`

For initial confirmation, `same_project` requires an explicitly supplied,
nonblank confirmed project tag. A candidate tag is deliberately not promoted
automatically.

For major-change resolution, the current confirmed tag may be retained, or the
human may explicitly confirm a replacement tag.

The result is:

```text
identity_status = confirmed
repository_id = unchanged
architecture_epoch = unchanged
active_index_scope = unchanged
major-change candidate = resolved
```

No archive record is created.

### `new_architecture_epoch`

This decision is valid only from
`major_change_confirmation_required`. It cannot create an initial epoch or run
automatically.

The requested epoch must be the exact next positive integer:

```text
compatibility baseline None -> 1
epoch 1 -> 2
epoch N -> N + 1
```

The result:

- retains the physical repository ID and storage key;
- derives a distinct index scope from the same repository ID and new epoch;
- appends the previous epoch, scope, project tag, actor, timestamp, and reason
  as a preserved archive record;
- makes the new epoch the active confirmed identity state; and
- never deletes or reconciles rows from the old scope.

### `new_project`

This is a report-only outcome:

```text
outcome = repository_identity_rebinding_required
rebinding_required = true
```

The identity-state artifact is unchanged. This phase does not derive a new
repository ID, rebind the directory, move artifacts, migrate rows, or delete
old state.

### `reject_or_defer`

This is also report-only:

```text
outcome = confirmation_deferred
artifact changed by decision = false
```

The pending state remains locked and no canonical permission is enabled.
Activation Graph work remains independently available.

## Compatibility-baseline epoch

The first identity state intentionally preserves the INDEX.1D.2A default:

```text
architecture_epoch = None
active_index_scope = code-index-<repository_id>
```

`None` is the compatibility baseline, not a missing strict scope. Automatically
changing an existing repository to an explicit epoch `1` would derive a new
scope and strand the pre-1D.2B namespace. Therefore initial confirmation and a
later `same_project` decision preserve the unsuffixed baseline scope.

Only an explicit `new_architecture_epoch` decision during major-change review
moves the baseline to epoch `1`. Later epochs advance by exactly one. Epoch
booleans, zero, negative values, gaps, repeats, and non-integer values fail
closed. Explicit epochs are bounded at `1,024`; this also bounds retained epoch
lineage and prevents hostile state from causing unbounded validation work.

## Advisory major-change classifier

`classify_major_change_candidate()` consumes only bounded caller-supplied
signals. It performs no repository traversal or model call.

The canonical signal vocabulary is:

```text
entrypoint_family_changed
primary_interface_changed
high_deleted_file_ratio
high_added_file_ratio
framework_manifest_changed
dominant_structure_changed
runtime_environment_changed
manual_operator_flag
```

Signals and evidence are copied, normalized, deduplicated, and sorted so input
ordering cannot change the result. Unknown or oversized input returns an
explicit invalid decision.

The default policy requires two distinct signals. `manual_operator_flag` is
decisive by default. Callers may supply bounded `minimum_signal_count` and
`force_signal_ids` policy values. A positive classification means only:

```text
major_change_candidate = true
human_confirmation_required = true
```

The classifier always keeps these false:

```text
automatically_create_new_epoch
automatically_classify_new_project
```

Applying a positive candidate is a separate pure transition and is allowed only
from `confirmed`.

## Identity-only permission matrix

| Identity status | Build | Refresh | Reconcile | Advance manifest | Claim current |
|---|---:|---:|---:|---:|---:|
| `uninitialized` | No | No | No | No | No |
| `initial_confirmation_required` | No | No | No | No | No |
| `confirmed` | Yes | Yes | Yes | Yes* | No |
| `major_change_confirmation_required` | No | No | No | No | No |
| `archived` | No | No | No | No | No |
| `blocked` | No | No | No | No | No |

`*` This is identity-layer eligibility only. Effective manifest advancement
must later be composed as:

```text
identity permission
AND successful canonical persistence
AND trusted INDEX.1D.2C completion evidence
```

No 1D.2B state can claim trusted-current status. No state grants unscoped
database authority: any future canonical mutation must use the state’s strict
`active_index_scope`.

## Transition and revision rules

The persistable state machine is:

```text
missing artifact
  -> initial_confirmation_required
  -> confirmed                         # explicit same_project
  -> major_change_confirmation_required
  -> confirmed                         # same_project, or explicit new epoch
```

`new_project` and `reject_or_defer` return reports without applying a state
transition.

Every applied transition increments `state_revision` by exactly one. An
identical state is an idempotent no-op. Optimistic `expected_revision` checks
reject stale writers. Physical identity is immutable, legacy warnings are
append-only, and archived-epoch history is append-only.

## Storage, validation, and atomicity

The state artifact is stored under the canonical repository-intelligence root:

```text
.agent/repository_intelligence/<storage_key>/identity_state.json
```

The bounded 1D.2A `storage_key` is used as the directory component to remain
safe for long repository names and Windows component limits. The complete
`repository_id` remains inside the artifact and is verified against the
requested repository during every load.

Reads are fail-soft:

- a missing regular file returns `uninitialized`;
- malformed UTF-8 or JSON returns `blocked`;
- duplicate JSON keys and non-standard numeric constants return `blocked`;
- unsupported, missing, or unknown fields return `blocked`;
- a mismatched repository ID, canonical root, storage key, scope, schema,
  permission record, or completion boundary returns `blocked`; and
- payloads over 256 KiB return `blocked`.

Serialization is deterministic UTF-8 JSON with sorted keys, two-space
indentation, no NaN values, and one trailing newline.

Saves:

1. validate the candidate state and its expected physical identity;
2. create or reuse the contained zero-content `.identity_state.lock` coordination
   file;
3. acquire both a process-local lock and an OS-backed cross-process lock, with
   a 30-second fail-closed timeout;
4. reload and validate the current artifact while both locks are held;
5. enforce the state transition and optional expected revision;
6. create an exclusive temporary file in the target directory;
7. write, flush, and `fsync` the complete payload;
8. recheck path safety; and
9. atomically replace the target with `os.replace`.

The reload, revision comparison, transition check, and replacement therefore
form one cross-process compare-and-swap section. A concurrent writer with the
same expected revision fails stale after the first writer commits.

Write or replace failure leaves the existing artifact intact and removes the
temporary file. Existing blocked state cannot be overwritten through this
path.

Path validation permits only the fixed storage-key directory and the
`identity_state.json` or `.identity_state.lock` filename beneath the configured
root. Both files apply the same containment and reparse-point checks. Symlinks,
Windows junctions, other reparse points, non-directory root/namespace
components, and resolved out-of-root paths are rejected.

The local threat boundary covers malformed artifacts, static unsafe paths,
ordinary failures, stale revisions, and cooperating concurrent writers. The
artifact is not signed and does not claim to withstand an independently
privileged process continuously replacing its namespace during a commit; such
an actor can already replace the state after the operation completes.

Human reasons, project labels, major-change evidence, and legacy namespace
evidence have explicit length and count bounds. Control characters,
credential-shaped assignments, credential-bearing URLs, and secret-shaped JSON
fields are rejected rather than persisted.

## Activation Graph independence

Identity-state metadata pins the Activation Graph boundary for all blocking
identity statuses, including `uninitialized`,
`initial_confirmation_required`, `major_change_confirmation_required`, and
`blocked`.

The identity contract does not prevent a bounded Activation Graph operation
when its own INDEX.1D.1 safety contract passes. It also grants the Activation
Graph no ability to:

- confirm a semantic project;
- create an architecture epoch;
- advance a canonical manifest;
- reconcile canonical rows; or
- change a project tag.

The implementation exposes metadata only; it does not invoke Activation Graph
runtime behavior.

## Legacy namespace warnings

Legacy inventory-derived namespaces are recorded only when the caller supplies
evidence. INDEX.1D.2B performs no discovery or inventory scan.

Each warning is bounded, deduplicated, sorted, append-only, and explicitly
records:

```text
preserve = true
deletion_allowed = false
automatic_epoch_binding_allowed = false
recommended_phase =
  "INDEX.MIGRATE.1 - Legacy Identity Namespace Inventory"
```

This phase neither validates those namespaces as canonical identity nor changes
their storage or database contents.

## Command surface

`scripts/create_repository_identity_state.py` provides a contract-only command
surface for:

- initializing a missing artifact into
  `initial_confirmation_required`;
- appending newly supplied legacy-namespace warnings to an existing active
  artifact without rebinding or migration;
- applying one explicit human decision;
- classifying and applying supplied major-change evidence; and
- emitting a text or deterministic JSON report.

Confirmation and epoch operations require explicit timestamp, human actor,
reason, decision, and any required project tag or epoch. The command does not
infer them. `new_project` and `reject_or_defer` return decision reports without
changing the artifact.

## Exclusions and 1D.2C handoff

INDEX.1D.2B intentionally excludes:

- production delta execution;
- repository traversal or architecture discovery;
- graph construction, refresh, or embedding execution;
- database reads, writes, deletes, or reconciliation;
- applied-manifest reads or advancement;
- repository completeness or trusted-current claims;
- Activation Graph runtime or cleanup;
- automatic project rebinding;
- legacy namespace migration; and
- old-scope or archive deletion.

The next phase is:

```text
INDEX.1D.2C - Honest Persistence Completion Contract
```

INDEX.1D.2C must combine the identity-only permission from this phase with
trusted evidence that the intended canonical persistence operation completed
successfully. Until then, the stored identity state can authorize the identity
side of an operation but cannot make that operation complete, advance an
applied manifest in production, or claim that repository intelligence is
current.
