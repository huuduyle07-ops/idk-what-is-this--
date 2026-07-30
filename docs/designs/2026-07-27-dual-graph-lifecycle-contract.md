# INDEX.1D.1 — Dual Graph Lifecycle Contract

Status: contract locked

Phase: `INDEX.1D.1`

Date: 2026-07-27

## Decision

C.A.T.T.U.S has two deliberately separate graph systems:

1. An **Activation Graph** is a bounded, task-scoped, disposable context cache.
2. A **Canonical Incremental Graph** is a persistent repository-intelligence
   asset tied to a confirmed repository identity and architecture epoch.

Direct Context is the third context strategy, but it is not a graph artifact.
It applies when the caller already supplies the files, snippets, or replay
evidence needed for the task.

The default architecture is:

```text
ordinary narrow coding task
→ Direct Context or Activation Graph

explicit repository-intelligence operation
→ Canonical Incremental Graph
```

Normal coding requests are not contractually required to perform canonical
repository indexing.

No production graph execution is authorized by INDEX.1D.1. This phase does not
change `index_repository()`, the current web indexing call, graph builders,
repository identity, database state, manifest state, runtime routing, CLI
routes, web routes, or background behavior.

## Stable graph kinds

### `direct_context`

Direct Context represents already-known evidence.

- Persistent: no.
- Graph required: no.
- Repository scan required: no.
- Database writes: forbidden.
- Manifest: not required and may not be advanced.
- Reconciliation: forbidden.
- Human identity confirmation: not required.
- Repository completeness claim: forbidden.

Examples include a pasted function, one explicitly identified source file and
test, or replay evidence that already contains the relevant context.

### `activation_graph`

An Activation Graph supports an ordinary bounded task when the relevant files
are not fully known.

- Scope: one task or run.
- Persistence: temporary cache only.
- Repository-wide completeness claim: forbidden.
- Persistent database write: forbidden.
- Canonical manifest advancement: forbidden.
- Scope reconciliation: forbidden.
- Full-repository embeddings: forbidden.
- Human project-identity confirmation: not required.

Pinning changes only retention preference. Leasing changes only temporary
cleanup protection. Neither operation changes the graph kind or grants
canonical authority.

### `canonical_incremental_graph`

A Canonical Incremental Graph supports explicit repository-intelligence work.

- Scope: repository plus confirmed architecture epoch.
- Persistence: durable.
- Database writes: allowed only under a strict `index_scope`.
- Manifest advancement: allowed only after trusted completion.
- Reconciliation: allowed only after confirmed identity and successful
  persistence.
- Human confirmation: required for an initial build and a major architecture
  change.
- Repository completeness claim: allowed only after trusted completion.

## Authority matrix

| Capability | Direct Context | Activation Graph | Canonical Graph |
|---|---:|---:|---:|
| Full repository scan required | No | No | Initial build only |
| Bounded task scan | Optional | Yes | Not primary purpose |
| Persistent DB writes | No | No | Yes, strict `index_scope` |
| Embeddings | None/selected only | Optional bounded | Optional incremental |
| Manifest required | No | No | Yes |
| Reconciliation allowed | No | No | Yes, identity + persistence gated |
| Human identity confirmation | No | No | Yes |
| TTL cleanup | N/A | Yes | No |
| Pin/lease lifecycle | N/A | Yes | No |
| Repository completeness claim | No | No | Trusted completion only |
| Suitable for narrow Debug task | Yes | Yes | Usually unnecessary |
| Suitable for Project Evolution | Insufficient | Sometimes insufficient | Yes |

## Activation Graph metadata

Every managed Activation Graph record exposes its safety facts:

```json
{
  "schema_version": 1,
  "artifact_kind": "cattus_activation_graph",
  "graph_kind": "activation_graph",
  "activation_id": "act-...",
  "repository_root": "...",
  "task_id": "run-...",
  "created_at": "...",
  "last_used_at": "...",
  "status": "active",
  "ttl_seconds": 259200,
  "pinned": false,
  "lease": {
    "owner": null,
    "acquired_at": null,
    "expires_at": null
  },
  "scope": {
    "seed_files": [],
    "activated_files": [],
    "dependency_depth": 0,
    "file_budget": 30,
    "content_byte_budget": 0
  },
  "freshness": {
    "status": "unknown",
    "checked_at": null,
    "changed_files": []
  },
  "managed_cleanup_allowed": true,
  "persistent_code_index_written": false,
  "canonical_manifest_advanced": false,
  "repository_completeness_claimed": false
}
```

## Activation lifecycle

Stable states:

```text
planned
active
stale
expired
cleanup_candidate
deleted
blocked
```

Allowed transitions:

```text
planned → active
planned → blocked
active → stale
active → expired
active → blocked
stale → active        # successful bounded refresh/freshness check required
stale → expired
expired → cleanup_candidate
cleanup_candidate → active  # freshness succeeded before deletion
cleanup_candidate → deleted
```

`deleted` and `blocked` are terminal for an activation identity. A caller that
wants to retry creates a new activation identity; it does not revive the old
one.

The pure transition helper rejects every transition outside this table and
does not mutate metadata.

## Sliding expiry policy

The default Activation Graph TTL is **72 hours** (`259200` seconds).

Expiry is calculated from `last_used_at`, not `created_at`. The exact boundary
is expired:

```text
now - last_used_at >= ttl_seconds
→ expired
```

Metadata viewing, status display, and UI polling do not count as graph use and
must not update `last_used_at`. Actual context retrieval or reuse may update it.

Retention decisions are:

- `keep_active`
- `keep_pinned`
- `keep_leased`
- `mark_expired`
- `cleanup_candidate`
- `invalid_metadata`

Pinned records are retained automatically. A valid lease whose `expires_at` is
strictly later than `now` protects the record. An expired lease offers no
protection. Invalid or timezone-naive timestamps fail closed and never
authorize automatic cleanup.

The classification helper performs no deletion.

## Freshness before reuse

TTL is not a freshness guarantee. Stored fingerprints must be compared with
current fingerprints before reuse.

| State | Meaning | Action |
|---|---|---|
| `fresh` | No stored fingerprint changed | Reuse allowed |
| `partially_changed` | Change count and ratio stay within configured bounds | Bounded refresh recommended |
| `stale` | Change count or ratio exceeds a bound | Rebuild Activation Graph |
| `missing_files` | An activated or seed file is missing | Rebuild Activation Graph |
| `unknown` | Fingerprint metadata is missing or unverifiable | Never claim freshness |

A stale Activation Graph is rebuilt rather than migrated. It never uses
canonical reconciliation semantics.

## Lease contract

A lease has:

```json
{
  "owner": "run-id",
  "acquired_at": "...",
  "expires_at": "..."
}
```

Lease duration is bounded; the contract default maximum is six hours. The
matching owner alone may release an active lease. An expired lease requires no
timer and provides no cleanup protection, so a crashed run cannot retain the
graph forever. A lease never makes an Activation Graph canonical or durable.

## Pin contract

Pinning means:

```text
retention preference
≠ canonical repository intelligence
```

A pin excludes a record from automatic cleanup but not freshness checks or
warnings. A pin never writes index rows, advances a manifest, authorizes
reconciliation, changes project identity, bypasses freshness, or authorizes a
repository completeness claim.

## Lazy cleanup

There is no continuous background janitor. Future cleanup may be requested only
at these controlled lifecycle points:

- `startup`
- `before_activation_create`
- `manual`
- `storage_budget_pressure`

Every cleanup plan is dry-run-first. INDEX.1D.1 only classifies records:

- `keep`
- `cleanup_candidate`
- `invalid_or_unmanaged`
- `blocked_by_pin`
- `blocked_by_lease`

Budget selection order is deterministic:

1. expired, unpinned, unleased graphs;
2. stale, unpinned, unleased graphs;
3. least-recently-used active graphs, only when a hard count or storage budget
   is exceeded.

Pinned records, valid leases, canonical artifacts, missing-marker records,
unknown directories, symlinks, traversal paths, and paths outside the
Activation Graph root are never selected.

The cleanup planner does not delete files.

## Canonical Incremental Graph lifecycle

Stable states:

```text
not_built
initial_confirmation_required
building
current
stale
major_change_confirmation_required
refreshing
degraded
blocked
archived_epoch
```

Primary transitions:

```text
not_built
→ initial_confirmation_required
→ building
→ current

current
→ stale
→ refreshing
→ current

current
→ major_change_confirmation_required
→ refreshing
→ current

current
→ major_change_confirmation_required
→ archived_epoch
```

Human confirmation gates the move from
`initial_confirmation_required → building` and from
`major_change_confirmation_required → refreshing|archived_epoch`.

Trusted completion gates `building → current` and `refreshing → current`.
INDEX.1D.2 will define repository identity and trusted-completion mechanics; the
present phase defines only the authority boundary.

## Major-change boundary

Major-change signals are advisory evidence:

- primary entrypoint family changes;
- the dominant web/CLI/service surface changes;
- a high added/deleted-file ratio;
- a major framework or dependency-manifest shift;
- a dominant project-structure change.

The allowed conclusion is:

```text
major_change_candidate = true
human_confirmation_required = true
```

The system may not automatically conclude that the repository is definitely a
new project.

While confirmation is pending, canonical work may not reconcile or delete old
scope rows, advance the applied manifest, replace the trusted architecture
epoch, or claim that repository intelligence is current. Independent narrow
Activation Graph work remains allowed.

## Future command contract

The following names reserve distinct future interfaces. They are not
implemented by this phase.

| Command | Graph kind | Temporary mutation | Human confirmation | Trusted completion | Canonical storage |
|---|---|---:|---:|---:|---:|
| `cattus context activate` | Activation | Yes | No | No | No |
| `cattus context status` | Activation | No | No | No | No |
| `cattus context pin` | Activation | Yes | Yes | No | No |
| `cattus context unpin` | Activation | Yes | Yes | No | No |
| `cattus context cleanup --dry-run` | Activation | No | No | No | No |
| `cattus context cleanup` | Activation | Yes | Yes | No | No |
| `cattus intelligence build` | Canonical | No | Yes | Yes | Yes |
| `cattus intelligence refresh` | Canonical | No | Major changes | Yes | Yes |
| `cattus intelligence status` | Canonical | No | No | No | Read only |
| `cattus intelligence rebuild` | Canonical | No | Yes | Yes | Yes |

One ambiguous command named only `index` is forbidden by the contract.

## Storage separation

Managed roots are separate:

```text
.agent/activation_graphs/<activation_id>/
.agent/repository_intelligence/<repository_id>/<epoch>/
```

Hard invariant:

```text
Activation Graph cleanup code must never receive
the Canonical Graph storage root as a deletion candidate.
```

Future cleanup requires both marker facts:

```json
{
  "artifact_kind": "cattus_activation_graph",
  "managed_cleanup_allowed": true
}
```

The pure planner additionally requires an asserted non-symlink path and checks
that the path is the exact child for its activation identity. A future runtime
must independently verify the no-symlink fact before supplying a record.
Invalid, missing, symlinked, traversal, out-of-root, canonical, and
unknown/unmanaged paths fail closed.

## Phase boundary

INDEX.1D.1 may produce only contract metadata, documentation, deterministic
artifacts, tests, and roadmap metadata. It does not:

- change `index_repository()` or remove the current web indexing call;
- create an Activation Graph;
- wire a production command or route;
- access code-index database state or production manifest state;
- modify graph-builder or repository-identity behavior;
- add background workers or schedulers;
- delete graph artifacts;
- call models, APIs, embeddings, repository indexing, validation execution, or
  patch execution;
- modify benchmark scoring/cases, Dream, Commander, Project Evolution, lessons,
  patching, or validation behavior.

## Next phases

Recommended sequence:

1. `INDEX.1D.2` — Canonical Identity & Trusted Completion
2. `INDEX.1D.3` — Traversal Budget Closure
3. `INDEX.1E` — Canonical Delta Execution Wiring
4. `INDEX.1F` — Activation Graph Fast Path

INDEX.1D.1 does not start any of these phases.
