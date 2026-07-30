# Canonical Repository Identity Primitive

**Phase:** `INDEX.1D.2A`

**Date:** 2026-07-27

**Status:** Implemented with a compatibility warning

## Mission and boundary

Persistent C.A.T.T.U.S repository state now has one physical identity source:
the canonical repository root.

```text
physical repository identity != human semantic project label
```

`repository_id`, `storage_key`, and `index_scope` are derived only from the
canonical root. `project_tag` is optional semantic/display metadata and carries
no canonical code-index authority.

This phase does not implement architecture-change detection, identity
confirmation, repository rebinding, epoch advancement, trusted completion,
manifest advancement, production delta execution, Canonical Graph
reconciliation changes, or Activation Graph runtime/cleanup.

## Canonicalization policy

`core.repository_identity.canonicalize_repository_root()` applies this policy:

1. Reject `None`, blank input, missing paths, files, broken symlinks, and other
   invalid roots with `NotADirectoryError`.
2. Expand the user home marker, then call `Path.resolve(strict=True)`.
3. Require the resolved target to be a directory.
4. Preserve the resolved string as the display form of `canonical_root`.
5. Derive hash input from `os.path.normpath(canonical_root)`.
6. On Windows, apply `os.path.normcase(...)` to the hash input. This preserves
   the existing deterministic lowercase/separator digest policy exactly.
7. On non-Windows platforms, do not case-fold.

Consequences:

- relative, absolute, `.`/`..`, trailing-separator, and equivalent separator
  spellings resolve to the same physical identity;
- real paths and symlinks to those paths share identity;
- Windows spelling case does not change identity under the existing
  `normcase` policy;
- case remains significant under the non-Windows policy;
- no repository scan is used to infer filesystem sensitivity;
- identity derivation calls no `os.walk`, `rglob`, source-content reader, Git
  command, model/API, embedding, graph builder, manifest writer, or database.

Moving or copying the repository to another canonical root intentionally may
produce a new identity. Rebinding is reserved for a future approved phase.

## Identity derivation

For a canonical root, C.A.T.T.U.S derives:

```text
path_digest  = sha256(normalized canonical-root hash input)
repository_id = <sanitized-root-name>-<first 32 hex chars>
storage_key   = <bounded-sanitized-root-name>-<first 16 hex chars>
index_scope   = code-index-<repository_id>
```

For root slugs up to 111 characters, the shorter `storage_key` and default
`index_scope` formats exactly preserve the existing path-derived SHA-256
formats. Longer storage slugs are truncated to keep the key within the existing
128-character lesson repository-scope and filesystem-component boundary; the
digest still distinguishes roots.

An explicit architecture epoch may add:

```text
-epoch-<first 16 hex chars of sha256("architecture-epoch:" + normalized epoch)>
```

The epoch never changes `repository_id` or `storage_key`. No epoch is inferred,
created, advanced, persisted, or deleted by this phase.

## Canonical code-index authority matrix

This matrix governs Canonical Incremental Graph/code-index authority. Existing
session, memory, tooling, patch-attempt, and consolidation tables still use
`project_tag` as a legacy semantic partition. They do not gain canonical
code-index authority, and migrating those schemas is outside this phase.

| Field | Purpose | May be `None` | May depend on inventory | May scope DB writes/deletes |
|---|---|---:|---:|---:|
| `canonical_root` | Physical location | No | No | Indirectly |
| `repository_id` | Stable physical identity | No | No | Yes |
| `storage_key` | Artifact namespace | No | No | No |
| `index_scope` | Strict persistent DB isolation | No | No | Yes |
| `project_tag` | Human semantic label | Yes | No | No |

The canonical code-index authority rule is:

```text
project_tag is display/semantic metadata.
index_scope is authority.
```

`RepositoryIdentity.project_tag=None` means that no human-confirmed semantic
label is active. It does not change physical identity and does not grant an
unscoped database path.

## Helper and caller classification

| Surface | Classification | INDEX.1D.2A behavior |
|---|---|---|
| `core.repository_identity` | Canonical | Owns canonical root, repository ID, storage key, scope, epoch suffix, and authority matrix. |
| `build_repository_storage_key` | Compatibility wrapper | Delegates to canonical path identity and preserves its existing output format. |
| `build_code_index_scope` | Compatibility wrapper | Delegates to canonical path identity and preserves its default output format. |
| `core.project_tag.build_project_tag` | Compatibility/display wrapper | Explicit labels retain legacy sanitization; automatic labels use `storage_key` with zero walks. |
| `core.project_tag.fingerprint_repo` | Legacy display-only | Retained for explicit callers; forbidden as persistent identity or DB authority. |
| `config.get_agent_dir` | Canonical artifact boundary | Uses `storage_key`; performs zero repository walks. |
| `core.index_manifest` identity/path match | Canonical | Uses the shared storage key and canonical-root policy. Manifest delta behavior is unchanged. |
| `core.indexer` code-index writer | Canonical | Derives `index_scope` from repository path and writes through the strict facade. `project_tag` remains display metadata. |
| `core.retriever` code-index reader | Canonical | Derives the same scope from repository path, or accepts only an explicitly validated `index_scope`. It ignores `project_tag` for authority. |
| `database.code_index` | Canonical strict boundary | Requires a non-empty, format-valid canonical scope before DB state is checked; never selects legacy unscoped branches. |
| `database.memory` code-index functions | Legacy/unsafe when unscoped | Retained for compatibility and characterized by tests; production indexer/retriever do not import these code-index entry points. |
| `core.lesson_store.repo_scope_id_for_path` | Compatibility artifact scope | Delegates to `storage_key`; it is not canonical code-index authority. |
| Other session, memory, penalty, and tooling `project_tag` callers | Semantic/legacy namespace | Remain outside canonical code-index authority; full memory-schema redesign is out of scope. |

## Database boundary

The physical schema still names its compatibility column `project_tag`.
Renaming or migrating that column is explicitly out of scope. The canonical
facade maps a validated `index_scope` to the old column internally.

Canonical replacement, deletion, reconciliation, code search, and dependency
search:

- validate scope before checking whether the DB is enabled;
- reject `None`, blank, and semantic-label-shaped scopes;
- use only parameterized queries;
- include the same scope in every affected query;
- cannot select an unscoped branch;
- copy collection inputs before passing them to the compatibility layer.

Legacy unscoped search behavior in `database.memory` remains only for existing
non-canonical compatibility callers and has characterization coverage. No live
database migration or reconciliation was performed.

## Storage compatibility and warning

For ordinary roots whose sanitized basename is at most 111 characters, the
existing manifest `storage_key` and code-index default scope are byte-for-byte
compatible. Existing canonical manifests and indexed rows remain in the same
namespaces.

Very long root names are an explicit edge-case cutover: `storage_key` is now
bounded to 128 characters so it is accepted by the existing lesson repository
scope validator and remains a safe filesystem component. Any old manifest
stored under a longer key is retained but requires a future explicit migration.
The default code-index scope remains unchanged for these roots.

There is one intentional namespace cutover: the automatic legacy
`build_project_tag` value was `<name>-<inventory-sha1>`, while the automatic
value is now the path-derived `storage_key`. As a result, old auto-tagged
session, memory, tooling, penalty, lesson-script, and `.agent` namespaces may
remain stranded under their previous names. Explicit user tags keep their old
sanitization and are unaffected.

This phase performs no scan-based migration, merge, deletion, or rebinding.
Both old database rows and old artifact directories remain recoverable. A
future migration must be separately approved because reconstructing the old
inventory-derived name is neither stable nor zero-walk.

## Credential redaction

`core.credential_redaction.redact_credentials()` is a pure error-boundary
helper. It:

- masks PostgreSQL/Postgres userinfo;
- masks every URL query value and fragments;
- masks common password/token/API-key assignments;
- replaces exact configured secret values, including non-URI DSNs;
- redacts detached configured URL credential tokens at token boundaries without
  corrupting safe substrings;
- handles quoted and JSON-style sensitive assignments;
- fails closed for malformed database URLs;
- leaves unrelated safe text readable;
- does not mutate inputs.

The confirmed `DATABASE_URL` construction leak in `database.memory.get_pool`
no longer interpolates the raw URL. The shared connection context also
sanitizes acquisition, entry, operation, and exit exceptions before they can
reach downstream stdout or web sinks. Redaction is additionally wired at
code-index results/stdout, retriever stdout, the database health payload, CLI
initialization, the main web runner error result, and the web route's rendered,
logged, validation, and persisted-session error boundaries.

## Activation Graph and future-phase isolation

Activation Graph code was not changed. A future Activation Graph may reference
`canonical_root` or `repository_id` for association only; those fields do not
grant DB writes, manifest advancement, reconciliation, epoch mutation, or
canonical-completeness authority.

The next normal phase is:

```text
INDEX.1D.2B - Identity Confirmation & Architecture Epoch State
```

That phase must be separately approved before confirmation or epoch state is
implemented.
