# Honest Persistence Completion Contract

**Phase:** `INDEX.1D.2C`

**Date:** 2026-07-27

**Status:** Implemented

## Mission and boundary

INDEX.1D.2C defines when a Canonical Incremental Graph operation may honestly
say that its authoritative persistent state completed.

It closes the success-shaped failure discovered by NEXT.SCAN.1:

```text
file processing succeeds
-> one embedding or database replacement fails
-> persistence is disabled for later files
-> reconciliation is skipped
-> the legacy result still returns normally
```

The old return shape remains available, but it now contains an additive
`completion` block whose trust fields fail closed. A partial operation cannot
authorize an applied-manifest advance or a repository-current claim.

This phase deliberately does not load identity state in the production
indexer, dispatch a delta, save a manifest, scan a repository beyond the
existing full index pass, call a new embedding/model/API, migrate a schema,
run an Activation Graph, or migrate a legacy namespace.

## Independent completion dimensions

`core/index_completion.py` defines immutable records for:

- identity authority;
- source processing;
- per-file processing, embedding, and persistence;
- aggregate persistence and mid-run abort evidence;
- scope reconciliation;
- authoritative or auxiliary post-index components;
- the derived completion decision;
- applied-manifest advancement;
- an applied-manifest commit receipt; and
- the trusted-current claim.

`IndexCompletionDecision` exposes these dimensions independently:

```text
processing_ok
persistence_required
persistence_attempted
persistence_ok
reconciliation_required
reconciliation_attempted
reconciliation_ok
auxiliary_graph_ok
trusted_completion
manifest_advance_allowed
trusted_current_claim_allowed
current_claim_requires_manifest_commit
status
failure_stage
failed_files
persistence_aborted_after_failure
unattempted_required_files
warnings
reasons
```

The decision is also bound to:

```text
repository_id
active_index_scope
architecture_epoch
identity_state_revision
completion_run_id
observed_state_id
```

This prevents a completion classified for one repository, epoch, scope, or
identity revision from being replayed against another.

## Stable completion statuses

| Status | Meaning | Trusted completion | Manifest eligible |
| --- | --- | ---: | ---: |
| `complete` | Required processing, persistence, and reconciliation succeeded under confirmed identity. | yes | yes |
| `complete_with_warnings` | The same canonical work succeeded; only explicitly non-authoritative outputs warned or failed. | yes | yes |
| `processing_failed` | Required source extraction, parsing, or fallback processing failed. | no | no |
| `persistence_failed` | A required embedding, replacement, deletion, or other persistent operation failed or remained unattempted after an abort. | no | no |
| `reconciliation_failed` | Required reconciliation failed or was skipped. | no | no |
| `identity_blocked` | Identity confirmation or architecture-epoch authority does not permit canonical mutation. | no | no |
| `persistence_disabled` | Database persistence is intentionally disabled. Processing may still produce read-only diagnostics, but this is not persistent success. | no | no |
| `persistence_not_attempted` | Persistence was required and enabled but never attempted. | no | no |
| `auxiliary_failed` | A component explicitly classified as an authoritative completion dependency failed. | no | no |
| `invalid_completion_evidence` | Evidence is malformed, contradictory, unsafe, duplicated, conflicting, incomplete, or credential-bearing. | no | no |

`complete_with_warnings` is trusted only because every failed component in
that state is explicitly classified as `auxiliary_output`. Unknown authority
fails closed. An authoritative failure never becomes a warning merely because
the canonical database work happened to finish.

## Pure classifier and evidence integrity

`classify_index_completion(...)` performs no I/O and derives every trust field.
There is no caller-supplied `trusted_completion` input.

The classifier:

- requires a full validated `RepositoryIdentityState`, not a status string or
  caller-constructed permission booleans, before it can trust completion;
- checks exact boolean, enum-string, identity-payload, and non-negative
  reconciliation-count types;
- validates normalized safe relative file paths;
- rejects duplicate or conflicting paths, including platform-equivalent path
  aliases;
- requires the declared required-file set to match the file outcome records;
- distinguishes required embeddings from intentionally omitted embeddings;
- requires aggregate processing failures to match file processing evidence;
- requires the persistence and reconciliation scopes to match each other and
  the confirmed repository/epoch identity;
- rejects `ok=true` with `attempted=false`;
- rejects aggregate success with failures, pending work, aborts, unattempted
  files, or error fields;
- rejects reconciliation attempts after required persistence failed;
- requires concrete file-level or aggregate evidence for every reported
  processing, persistence, or reconciliation failure;
- rejects contradictory failure stages;
- rejects unknown auxiliary authority; and
- rejects error text that was not already credential-redacted while returning
  only its sanitized copy.

The manifest gate does not trust mutable-looking derived fields simply because
they came from a frozen dataclass. A completion decision retains its normalized
source evidence privately; the gate reclassifies that evidence and compares the
entire public decision with recursive type-sensitive equality. Relabelling a
failed decision, run ID, observed-state ID, nested outcome, or trust field with
`dataclasses.replace` therefore fails as invalid completion evidence, including
crafted Python equality/truthiness values.

## File-level persistence evidence

Each eligible file record carries:

```text
file_path
action
processing_status
embedding_required
embedding_status
persistence_status
error_category
error_message
```

Stable persistence outcomes are:

```text
not_required
pending
persisted
deleted
skipped_unchanged
parse_failed
embedding_failed
replacement_failed
deletion_failed
blocked
```

Rules:

- required added, modified, or current compatibility `full_refresh` files must
  finish `persisted`;
- required deleted files must finish `deleted`;
- unchanged files must be explicitly `skipped_unchanged`;
- a required embedding must finish `embedded`;
- an empty file may validly persist zero units and mark embedding not required;
- every required file must have exactly one record; and
- any required failure, pending record, blocked record, or omitted required
  record blocks trusted completion.

`full_refresh` describes the existing production full-pass behavior honestly.
It does not introduce or imply production delta dispatch.

## Mid-run failure policy

The current conservative production behavior is retained and made explicit:

```text
failure on file N
-> latch persistence failure
-> retain the sanitized failing-file outcome
-> continue source processing for later-file diagnostics
-> stop later embedding/replacement attempts
-> record later required files as pending and unattempted
-> skip reconciliation
-> return an explicit degraded completion block
```

The result records:

```text
persistence_aborted_after_failure = true
unattempted_required_files = [...]
persistence_ok = false
trusted_completion = false
manifest_advance_allowed = false
trusted_current_claim_allowed = false
```

A Tree-sitter exception is not automatically a terminal parse failure. If the
existing text/file-unit fallback succeeds and persists, processing succeeds
with a warning. If required processing itself fails, its file record is
`parse_failed`, reconciliation is skipped, and completion is blocked.

## Independent reconciliation evidence

Reconciliation records:

```text
required
attempted
ok
index_scope
deleted_units
deleted_dependencies
preserved_external_targets
skipped_reason
error_category
error_message
```

Required reconciliation that was not attempted must name its skip reason and
blocks completion. A reconciliation exception records `attempted=true` and
`ok=false`; it is no longer indistinguishable from a step that never ran. An
attempted reconciliation failure also blocks completion when a caller marked
the step non-required; an actual failed cleanup attempt is never silently
reported as `complete`.

The database implementation and transaction tests retain the existing
preservation rule for external dependency targets whose `target_file IS NULL`.
INDEX.1D.2C changes no cleanup query or schema.

## Applied-manifest advancement gate

`may_advance_applied_manifest(...)` is pure and independently revalidates:

1. the full identity state is structurally valid and literally `confirmed`;
2. canonical mutation, reconciliation, and identity-layer manifest permission
   are enabled;
3. the decision still exactly matches reclassified source evidence;
4. its repository ID, scope, epoch, and state revision match the supplied
   identity;
5. processing succeeded;
6. required persistence was attempted and succeeded;
7. required reconciliation was attempted and succeeded; and
8. no failed, aborted, or unattempted required work remains.

Initial confirmation, major-change confirmation, archived epochs, blocked
identity, disabled persistence, unattempted or partial persistence, failed or
skipped reconciliation, malformed evidence, and replayed identity all reject
manifest advancement.

The gate returns permission evidence only. It does not call
`save_repository_manifest` or commit any state in this phase.

## Trusted-current boundary

The classifier always returns:

```text
trusted_current_claim_allowed = false
current_claim_requires_manifest_commit = true
```

Completion is a prerequisite for committing an applied manifest; it is not
proof that the commit occurred.

`may_claim_repository_intelligence_current(...)` additionally requires an
explicit successful applied-manifest receipt whose values exactly match:

```text
completion_run_id
observed_state_id
applied_state_id
repository_id
active_index_scope
architecture_epoch
identity_state_revision
```

The completed decision's observed-state ID, the receipt's observed-state ID,
and the committed applied-state ID must all be identical. Missing, unsafe,
stale, self-relabelled, cross-repository, cross-epoch, cross-scope, or
mismatched evidence blocks the claim.

This receipt is a pure future-wiring facade. The current
`RepositoryManifest` schema has no run receipt, and production manifest commit
wiring remains intentionally deferred.

## Observed versus applied state

The contract formalizes two distinct concepts:

### Observed repository state

Observed state may contain scan results, file metadata, hashes, and detected
changes. `inspect_repository_delta` already returns a candidate next manifest
without saving it. Observation proves what was seen, not what was persisted.

### Applied persistent state

Applied state describes the database-backed repository intelligence that
successfully completed and whose manifest commit succeeded for the same run.

Hard invariant:

```text
observed repository state must never be mistaken for applied persistent state
```

## Auxiliary authority review

| Component | Current classification | Canonical persistence remains trusted if it fails? |
| --- | --- | ---: |
| Required code-unit/dependency replacement | `authoritative_completion_dependency` | no |
| Required embedding generation | `authoritative_completion_dependency` | no |
| Required file deletion | `authoritative_completion_dependency` | no |
| Required scope reconciliation | `authoritative_completion_dependency` | no |
| Current `ProgramGraph` used only for Project Map rendering | `auxiliary_output` | yes, with warnings |
| Project Map | `auxiliary_output` | yes, with warnings |
| Code DNA | `auxiliary_output` | yes; a swallowed write failure is emitted as `complete_with_warnings`, while a compute exception prevents a result |
| Phantom Limb report | `auxiliary_output` | yes; an exception still prevents a success-shaped return today |
| Obsidian export | `auxiliary_output` | yes |
| Presentation/report artifacts and UI summaries | `auxiliary_output` | yes |

No current `ProgramGraph` is the authoritative persisted Canonical Incremental
Graph. If a future phase gives a graph that authority, its evidence must be
reclassified explicitly as `authoritative_completion_dependency`. Unknown
authority is invalid rather than implicitly warning-only.

## Result compatibility

The legacy index result keys remain:

```text
repo_path
project_tag
index_scope
files_processed
symbols_stored
code_index_reconciliation
project_map
phantom_limb
```

The exact legacy `code_index_reconciliation` dictionary is unchanged. The new
top-level `completion` block is additive.

Existing CLI and web callers may continue reading legacy fields temporarily.
New canonical logic must use the completion block and the pure gates.

Production callers do not yet load or pass the 1D.2B identity artifact.
Therefore an otherwise successful legacy production call returns honest
`identity_blocked` completion metadata, not trusted canonical completion.
Future identity/delta/manifest orchestration must be separately authorized.

## Exclusions and INDEX.1D.3 handoff

INDEX.1D.2C adds:

- no production delta dispatch;
- no manifest save or commit wiring;
- no new repository scan;
- no new embeddings, model call, API call, or network access;
- no schema migration;
- no Activation Graph runtime;
- no legacy namespace migration; and
- no broad index execution-flow redesign.

Recommended next phase:

```text
INDEX.1D.3 — Traversal Budget Closure
```

Traversal-budget work, production delta execution, applied-manifest commit
wiring, Activation Graph runtime, and legacy namespace migration remain
separate and unauthorized.
