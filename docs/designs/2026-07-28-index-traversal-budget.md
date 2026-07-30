# INDEX.1D.3 — Traversal Budget Closure

**Phase:** `INDEX.1D.3`

**Date:** 2026-07-28

**Status:** Implemented

## Mission and boundary

INDEX.1D.3 gives one canonical indexing operation one authoritative repository
membership enumeration. The resulting materialized inventory is reused by the
indexer and compatible language, Code DNA, dependency, ProgramGraph,
project-map, manifest, and web-request consumers.

This is a traversal and interface closure, not incremental execution. It does
not dispatch a repository delta, skip unchanged-file parsing from manifest
state, advance an applied manifest, change database persistence decisions,
alter graph or dependency semantics, or create an Activation Graph runtime.

## Traversal vocabulary

For this phase:

- A **full repository traversal** recursively enumerates repository paths with
  `os.walk`, `Path.rglob`, `Path.glob("**/*")`, recursive `scandir`, a custom
  recursive iterator, or a subprocess inventory command.
- A **bounded subtree traversal** is recursive but rooted beneath a documented
  subdirectory that is smaller than repository membership.
- A **direct path lookup** checks one known path or a finite list of candidate
  paths without recursive enumeration.
- **Inventory reuse** filters or projects the materialized operation inventory
  without touching repository membership again.

Targeted file reads and non-recursive directory checks are not repository
traversals. Parsing and content reads remain separate costs; INDEX.1D.3 pins
membership enumeration, not parse count.

## Inventory owner and lifecycle

The canonical indexing/orchestration boundary owns inventory creation:

```text
canonical operation begins
→ resolve canonical repository root
→ load RepoIgnorePolicy
→ walk once, top-down, with ignored directories pruned
→ materialize and validate RepositoryInventory
→ pass the same snapshot to compatible consumers
→ discard it when the operation ends
```

The web project-input path creates the same operation-scoped inventory and
passes it into canonical indexing. It does not create a second web-specific
membership view. The inventory is neither process-global repository truth nor
persisted state, and it is not shared between concurrent requests.
Inventory-backed graph consumers bypass graph values left by earlier
operations, and inventory-backed Code DNA computation does not trust the
unversioned on-disk compatibility cache.

## Inventory contract

The immutable inventory records:

```text
canonical_root
entries
indexable_entries
ignore_policy_fingerprint
traversal_count
```

Entries use canonical, repository-contained absolute paths paired with
normalized repository-relative paths. Entry collections are tuples ordered by
normalized relative path. `indexable_entries` is a deterministic projection of
`entries` using the existing supported-extension and infrastructure-file
rules; it is not a second filesystem membership policy.

Derived views may calculate counts, primary language, dependency membership,
manifest fingerprints, graph inputs, or Code DNA inputs without walking.
Callers must not mutate the inventory or its entry collections.

## Fail-closed supplied-inventory validation

A supplied inventory is accepted only when:

- its canonical root matches the requested repository;
- every entry resolves inside that canonical root;
- relative and absolute forms identify the same file;
- normalized relative paths are unique;
- entries and filtered views are deterministically ordered; and
- the entries obey the loaded `RepoIgnorePolicy`, the policy fingerprint is
  current, and the indexable view is the canonical deterministic projection
  of the authoritative entries.

Root mismatch, duplicate paths, out-of-repository paths, contradictory entry
forms, or nondeterministic ordering raises a clear validation error. A malformed
supplied inventory is never discarded in favor of a hidden scan. The legacy
compatibility fallback may scan once only when the caller supplied no
inventory.

## Static production traversal inventory

The following inventory characterizes the indexing and project-input request
paths at the closure boundary. “Before” describes the rediscovery site that
INDEX.1D.3 removes or contains; “After” records its budget disposition.

| Module / function | Triggering caller | Before classification and cadence | Purpose | Can reuse the canonical inventory? | INDEX.1D.3 disposition |
|---|---|---|---|---|---|
| `core.repo_librarian._walk_policy_files` | `iter_repo_files`, `build_repo_manifest`, `inspect_repo_inventory`, `detect_repo_language` | Full traversal; could run multiple times per index run and request | Apply `RepoIgnorePolicy`, infrastructure gating, and deterministic membership | Yes; this is the shared membership boundary | One owner call materializes the operation inventory; compatibility callers without an inventory may invoke it once |
| `core.indexer.index_repository` inventory precheck | CLI index and `web.runner.run_agent_web` | Full traversal once per index run | Abort a repository with zero indexable files and obtain counts | Yes | Derived from the supplied/owned inventory; zero additional walks |
| `core.indexer.index_repository` file iteration | CLI index and `web.runner.run_agent_web` | Full traversal once per index run | Establish processing and dependency membership | It owns or receives the canonical inventory | This is the one authoritative membership walk when no inventory is supplied; otherwise it reuses |
| `core.code_dna.compute_dna` | `index_repository`; later `get_or_compute_dna` cache miss | Full `rglob` once per index run | Compute repository style statistics | Yes | Filters supplied entries; legacy direct callers retain one-scan behavior |
| `graph.builder.build_graph_from_repo` | Index project-map build, CONTROL, retriever, semantic graph, deep understanding | Full traversal on each independent cache miss | Select graph files and dependency membership | Yes | Supplied inventory/entries perform zero additional membership walks; no-inventory callers scan at most once |
| `graph.project_map.build_project_map` | `index_repository` after graph construction | Direct consumption; no full traversal | Render summaries and graph-derived navigation | Already | Continues to consume supplied summaries/graph; `get_agent_dir` output lookup is direct |
| `core.index_manifest.inspect_repository_delta` | Manifest tools and future canonical delta integration | Full traversal per inspection; not dispatched by current production indexing | Fingerprint current membership and classify a supplied previous manifest | Yes | Supplied inventory performs zero additional walks; this phase does not call or save the manifest in production |
| `core.dependency_target.resolve_dependency_target` | Indexer and graph builder per parsed import | Finite direct candidate checks per import when membership is absent | Resolve internal dependency targets | Yes | Supplied repository membership avoids filesystem candidate checks; legacy absence performs bounded direct lookups, never a recursive scan |
| `web.runner.run_agent_web` inventory precheck | Every valid project-input request | Full traversal once per request before indexing | Validate project input | Yes | Creates/reuses the request inventory and passes it downward |
| `RepositoryInventory.summary` from `web.runner.run_agent_web` | Every project-input request | Replaces the former separate `core.repo_librarian.detect_repo_language` traversal | Select primary language | Yes | Reads the materialized inventory summary directly; zero additional walks |
| `core.control_engine.get_cached_graph` | `run_control_structured` after index-time cache invalidation | Full graph membership traversal on cache miss per request | CONTROL graph | Yes | Reuses the operation inventory or graph built from it; zero additional membership walks |
| `reasoning.deep_project_understand.get_cached_graph` | `control_engine.select_entry_nodes` | Separate full graph membership traversal on its cache miss | Deep-understanding evidence | Yes | Reuses the operation graph/inventory; zero additional membership walks |
| `core.retriever.get_cached_graph` / `_get_cached_repo_graph` | Execution trace and retrieval context | Conditional full graph membership traversal on independent cache miss | Retrieval graph evidence | Yes | Reuses operation graph/inventory; zero additional membership walks |
| `core.semantic_graph_pipeline.get_semantic_graph` | Semantic/Obsidian retrieval context | Conditional full graph membership traversal on cache miss | Semantic graph context | Yes | Reuses operation graph/inventory; zero additional membership walks |
| `core.feature_context.build_file_inventory` | Scout-triggered web requests | One inventory scan plus one full `rglob` when Scout runs | Prepare bounded file metadata for Scout | Yes | Projects the operation inventory; no additional membership walk and no new model call is introduced |
| `core.preflight.detect_default_preflight_command` Rust/Go test detection | Web preflight when no explicit validation command is supplied | Language-conditional full `rglob` | Detect an existing test layout | Yes | Uses supplied relative membership where wired; direct file and root-directory checks remain bounded and behavior-equivalent |
| `config.get_agent_dir` | Artifact writers throughout index/web paths | Formerly identity/configuration-driven discovery; now direct | Derive the repository artifact namespace | No traversal is necessary | Pure path-derived storage-key resolution; repeated calls add zero walks |
| `core.project_tag.build_project_tag` and `core.repository_identity` | CLI/web/index identity setup | Legacy fingerprint helper can walk, but default production identity is direct | Display label and canonical physical identity | No traversal is permitted for authority | Default production calls remain path-derived and zero-walk; explicit legacy fingerprint diagnostics are not authority |

`core.repo_inventory.inspect_repo_inventory` is now a compatibility facade
over the canonical scanner and no longer carries an alternate recursive
implementation. The `core.project_map_v2` / `core.project_node_summaries`
scanners remain explicit offline report builders rather than the canonical
index or web-request path. They are documented, not counted as runtime
traversals, and are not silently used as fallbacks. Test-only scans and CLI
audit/report scans are likewise excluded unless a runtime caller invokes them.

## Traversal budget and diagnostics

The test-pinned membership budget is:

| Operation / consumer | Full membership traversals |
|---|---:|
| Canonical index operation | 1 |
| Project-input web request that invokes canonical indexing | 1 |
| Canonical identity derivation | 0 |
| Repeated `get_agent_dir()` calls | 0 |
| Indexer after inventory creation | 0 additional |
| ProgramGraph / project-map construction with inventory | 0 additional |
| Manifest inspection with inventory | 0 additional |
| Code DNA with inventory | 0 additional |
| Dependency resolution with inventory membership | 0 additional |

Traversal diagnostics are pure/test-oriented and deterministically ordered.
They expose stable site labels and reuse booleans, not internal absolute paths,
source content, environment values, or credentials. The diagnostic contract
can represent:

```json
{
  "repository_walks": 1,
  "walk_sites": ["core.repo_librarian._walk_policy_files"],
  "inventory_reuse": {
    "code_dna": true,
    "dependency_resolver": true,
    "graph_builder": true,
    "indexer": true,
    "manifest": true,
    "project_map": true,
    "web_request": true
  }
}
```

No noisy production log stream is required for this evidence.
Canonical indexing reports `manifest: false` because INDEX.1D.3 deliberately
does not invoke manifest work in production. Standalone manifest tests
separately prove supplied-inventory reuse by forbidding a rescan; inventory
diagnostic tests pin deterministic ordering and path-safe output.

## Membership snapshot and mutation boundary

The inventory describes membership at one instant:

```text
inventory membership snapshot
≠
content freshness guarantee
```

Content reads still happen after enumeration. If an inventoried file
disappears or becomes unreadable, processing records the explicit file failure,
the INDEX.1D.2C completion contract denies trusted completion, and no consumer
automatically rescans the repository. INDEX.1D.3 adds no retry loop, watcher,
background refresh, or persisted cache.

## Test guardrails

The traversal tests pin behavior at recursive primitives and at the shared
scanner boundary, rather than counting only a conveniently stubbed helper.
They cover:

- one deterministic, ignore-policy-compliant inventory walk;
- immutable inputs and deterministic filtered/diagnostic ordering;
- duplicate, out-of-root, root-mismatch, and malformed supplied inventories;
- no fallback scan after supplied-inventory validation failure;
- zero-walk identity and repeated `get_agent_dir()` calls;
- zero additional graph, project-map, manifest, Code DNA, and dependency
  membership walks when inventory is supplied;
- at most one compatibility scan when inventory is absent;
- exactly one characterized canonical-index and project-input web membership
  traversal;
- explicit failure and no rescan when a file disappears after enumeration; and
- source/AST guards against new recursive inventory implementations,
  production delta dispatch, manifest save/advancement, database behavior
  changes, graph-semantic changes, model/API/network/subprocess inventory,
  background caches/workers, Activation Graph runtime, and deletion.

The existing NEXT.SCAN.1 production-readiness characterization continues to
pin full parsing, embedding, and replacement behavior. INDEX.1D.3 changes its
traversal expectations only; unchanged-file skipping remains deferred.

## Exclusions and INDEX.1E.1 handoff

INDEX.1D.3 intentionally adds:

- no production manifest load, save, commit, or advancement;
- no delta planner dispatch or unchanged-file parse skipping;
- no per-file deletion execution;
- no database schema, persistence, reconciliation, or authority change;
- no graph node, edge, scoring, or dependency-resolution semantic change;
- no model, API, network, subprocess inventory, or dependency installation;
- no background cache service, scheduler, watcher, or worker;
- no filesystem deletion or legacy namespace migration; and
- no Direct Context or Activation Graph runtime.

Recommended next phase:

```text
INDEX.1E.1 — Canonical Delta Dispatch Integration
```

That phase must separately wire delta actions and applied-manifest commit rules
through the INDEX.1D.2C trusted-completion gate. INDEX.1D.3 does not authorize
or begin that work.
