# INDEX.1E.0 — Delta Integration Preflight

- Phase: `INDEX.1E.0`
- Status: `INDEX_1E_0_BLOCKED`
- Readiness: `blocked_by_contract_mismatch`
- Commit: `a1d3299b69df65137d13f8dbea40044c7fde48fc`
- Dirty worktree: `true`
- Baseline: **6270 passed, 5 skipped, 48 failed**

## 1. Test baseline and failure categories

The repository-wide command was `.\.venv\Scripts\python.exe -m pytest -q`. The frozen failure-set digest is `36c53bb1b62d24429c4d457f9103a1591968b233a6c12b5cb069e599b0c4fbe9`.

The earlier diagnostic supplied aggregate totals only; additions, removals, and renamed node IDs cannot be reconstructed honestly.

| Category | Count |
|---|---:|
| authoritative_index_runtime | 0 |
| index_adjacent_contract | 0 |
| stale_roadmap_expectation | 23 |
| missing_generated_artifact | 0 |
| mirror_tunnel_or_hardening | 25 |
| unrelated_product_feature | 0 |
| environment_or_platform | 0 |
| third_party | 0 |
| unclassified | 0 |

## 2. INDEX intersection analysis

- Authoritative INDEX runtime failures: **0**
- INDEX-adjacent contract failures: **0**
- Unclassified failures: **0**
- Proven unrelated failures: **48**

## 3. Production entrypoints

| Caller | Trigger | Inventory | Identity/scope | Manifest/delta | Persistence | Completion |
|---|---|---|---|---|---|---|
| core.indexer.index_repository | authoritative synchronous canonical indexing operation | validates a supplied RepositoryInventory or creates one | canonical path-derived index_scope; optional identity_state is consumed only by completion classification; core.repository_identity.build_code_index_scope(repo_path); optional semantic display metadata; never DB authority | none; not called | full per-file replacement followed by one scope reconciliation when persistence remains healthy | returns additive result['completion']; does not commit a manifest or assert a trusted-current claim |
| web.runner.run_agent_web | automatic inline indexing for project-directory requests that reach the full web execution path | creates one inventory at the request boundary and supplies it to index_repository and downstream consumers | does not load or pass confirmed identity state; index_repository derives scope from the repository path; build_project_tag produces semantic metadata only | none; not called | inherits synchronous full replacement/reconciliation | completion is not copied to the current web/session payload |
| cli.interactive.create_agent_state | automatic indexing when the interactive input is one project directory | index_repository creates the operation inventory | does not load or pass identity state; index_repository derives scope from the repository path; passes a semantic project tag; it is not authority | none; not called | inherits full replacement/reconciliation | legacy flow consumes phantom-limb data, not completion |
| main.main --index | explicit command-line --index mode | index_repository creates the operation inventory | does not load or pass identity state; index_repository derives scope from the repository path; none by default | none; not called | inherits full replacement/reconciliation | return value is ignored |
| core.indexer.__main__ | direct module/script invocation | index_repository creates the operation inventory | does not load or pass identity state; index_repository derives scope from the repository path; none by default | none; not called | inherits full replacement/reconciliation | return value is ignored |
| web.app.index (POST /, full mode) | form submission selects full mode, then _run_mode calls web.runner.run_agent_web | the web runner creates one request inventory and forwards it to index_repository and downstream consumers | the route creates a semantic project tag but does not load confirmed identity state; index_repository derives scope from the repository path; semantic display metadata only; never DB authority | none; not called | inherits synchronous full replacement/reconciliation | the current session payload does not retain completion |
| benchmarks.run_benchmarks.main (run mode) | normal benchmark execution reaches run_agent_web through _run_case_with_capture; --check performs no agent call | run_agent_web creates one inventory for each benchmark case repository | does not load or pass confirmed identity state; index_repository derives scope from each case repository; case-level semantic metadata only | none; not called | inherits full replacement/reconciliation per executed case | benchmark scoring consumes the broader web result, not an applied-manifest receipt |
| web.app.benchmarks_run_route (POST /benchmarks/run) | starts the existing benchmark worker; each selected case reaches run_agent_web through core.benchmark_web | run_agent_web creates one inventory for each benchmark case repository | does not load or pass confirmed identity state; index_repository derives scope from each case repository; case-level semantic metadata only | none; not called | inherits full replacement/reconciliation per executed case | benchmark reports do not establish trusted-current state |

Concrete retrieval consumers of code-index scope: `core.retriever.search_safe_code_units`, `core.retriever.search_dependencies`, `core.retriever.trace_call_chain`, `core.retriever.retrieve_context`, `core.retriever.trace_execution_flow`, `core.retriever.search_global_symbols`, `core.retriever.pick_seed_symbols`, `core.pipeline.maybe_retrieve_context`, `core.control_engine.run_control_structured`, `web.app._run_mode`.
Baseline path scope compatibility is `true`; architecture-epoch scope compatibility is `false`.

## 4. Current Run A / Run B characterization

an unchanged second run repeats all current processing, embedding, and replacement work.

| Counter | Run A (cold) | Run B (unchanged) |
|---|---:|---:|
| repository_walks | 1 | 1 |
| content_reads | 3 | 3 |
| parsed_files | 3 | 3 |
| graph_parsed_files | 3 | 3 |
| embedded_files | 3 | 3 |
| replacement_calls | 3 | 3 |
| deletion_calls | 0 | 0 |
| manifest_loads | 0 | 0 |
| manifests_saved | 0 | 0 |
| delta_plans_built | 0 | 0 |
| reconciliation_calls | 1 | 1 |

## 5. Prerequisite reachability

| Primitive | Status | Reachable symbols | Evidence |
|---|---|---|---|
| inventory | ready | core.repository_inventory.RepositoryInventory<br>core.repository_inventory.create_repository_inventory<br>core.repository_inventory.validate_repository_inventory | index_repository owns one immutable operation inventory; a supplied inventory is root-validated and adds no walk |
| identity | ready | core.repository_identity.build_repository_identity<br>core.repository_identity.build_code_index_scope | canonical_root, repository_id, storage key, and strict index_scope are path-derived; project_tag is semantic only |
| identity_state | ready | core.repository_identity_state.load_repository_identity_state<br>core.repository_identity_state.derive_canonical_identity_permissions | identity status, architecture epoch, state revision, active scope, and mutation/reconciliation/manifest permissions are available without auto-confirmation |
| manifest | ready | core.index_manifest.load_repository_manifest<br>core.index_manifest.inspect_repository_delta<br>core.index_manifest.save_repository_manifest | stable path and root/schema/policy validation exist; inspection reuses metadata/SHA evidence and returns an observed manifest without saving it; gap: delta inspection currently fingerprints default inventory membership, which is broader than indexable membership |
| delta_classifier | ready | core.index_manifest.RepositoryDelta<br>core.index_manifest.inspect_repository_delta | added, modified, deleted, unchanged, hash reuse, and policy-change classification are represented |
| execution_planner | ready | core.index_execution.IndexExecutionPlan<br>core.index_execution.build_index_execution_plan | pure planning covers database availability, embedding off, same-dimension drift, incompatible dimensions, changed files, deletion, and full-baseline/reset cases; gap: production has no authoritative adapter for trusted_index_exists or EmbeddingCompatibility, and the planner does not carry RepositoryDelta.policy_changed |
| completion | ready | core.index_completion.classify_index_completion<br>core.index_completion.may_advance_applied_manifest | processing, per-file persistence, reconciliation, trusted completion, and manifest-advance eligibility are distinct |
| applied_manifest_receipt | ready | core.index_completion.AppliedManifestEvidence<br>core.index_completion.may_claim_repository_intelligence_current | the pure current-claim gate requires matching committed run, repository, epoch, scope, revision, and state IDs; gap: no production observed-state ID generator or successful manifest-save-to-AppliedManifestEvidence receipt builder exists yet |

## 6. Recommended integration seam

Exactly one seam is recommended: `core.indexer.index_repository` after shared operation_inventory acquisition and confirmed identity-permission validation, before DB initialization and the repo_entries processing loop.

inspect_repository_delta builds observed state; only a separately gated successful commit may become applied.

Future controlled loops:

- a decoupled canonical parse/embed/replace dispatcher will consume translated indexable plan.to_parse
- file deletion will consume plan.to_delete before the existing authoritative reconciliation

Legacy fallback: missing or unusable applied state must fail closed or use an explicitly characterized full-refresh path. Actual dispatch is deferred.

## 7. DB-disabled behavior

Processing-only success is not persistent canonical success. The current completion classifier reports `persistence_disabled`, denies trusted completion, manifest advancement, and a trusted-current claim, and creates no fake applied receipt.

## 8. Web-request boundary

- Invocation: web.runner.run_agent_web full-mode project-input branch calls index_repository inline.
- Confirmed identity enforcement: `false`.
- Completion metadata reaches payload: `false`.
- Credential redaction preserved: `true`.
- One shared inventory: `true`.
- Latency/compatibility: today every request repeats full work; INDEX.1E.1 may reduce unchanged-request work but must preserve the synchronous result shape and explicit degraded errors.

## 9. Guardrails

- `production_file_skipping_changed`: `false`
- `production_manifest_load_for_dispatch`: `false`
- `manifest_saved_or_advanced`: `false`
- `db_behavior_changed`: `false`
- `reconciliation_changed`: `false`
- `activation_graph_runtime_added`: `false`
- `background_worker_added`: `false`
- `legacy_namespace_migrated`: `false`
- `model_api_or_embedding_execution_added`: `false`
- `tests_weakened_or_xfailed`: `false`

## 10. Readiness decision

- Status: `blocked_by_contract_mismatch`
- Phase status: `INDEX_1E_0_BLOCKED`
- Next phase allowed: `false`
- Production behavior: `full_reprocessing_characterized`

Blocking contract mismatches:

- empty_repository_deletion_gap: index_repository rejects a repository with zero indexable files before a delta can delete previous rows, and canonical reconciliation also rejects an empty current_files set
- retriever_epoch_scope_mismatch: core.retriever._index_scope_for ignores a supplied architecture-epoch scope whenever repo_path is valid, so an epoch writer and ordinary retrieval resolve different scopes

## 11. Warnings and deferred work

- Warning: 48 pre-existing proven-unrelated repository-wide failures remain frozen in the baseline.
- Warning: Current direct, CLI, and web callers do not load and enforce confirmed identity permissions before canonical mutations; that dispatcher wiring is deferred to INDEX.1E.1.
- Warning: The web request keeps canonical indexing synchronous and does not expose completion metadata in its session payload.
- Deferred seam requirement: applied_receipt_bridge_missing: no production observed_state_id generator or successful manifest-save receipt builder binds repository, epoch, scope, revision, run, and applied state
- Deferred seam requirement: identity_authority_is_post_hoc: index_repository derives and mutates the baseline path scope before identity permissions are classified, so confirmed epoch authority cannot safely control current writes or reconciliation
- Deferred seam requirement: incremental_auxiliary_coupling: the per-file parse loop also builds the full summaries used by Project Map and Phantom Limb; filtering it directly would make auxiliary outputs partial
- Deferred seam requirement: manifest_indexable_membership_mismatch: delta inspection fingerprints default inventory entries while production parses inventory.indexable_entries; a raw plan may put non-indexable paths such as .gitignore into to_parse
- Deferred seam requirement: planner_input_adapter_missing: production has no trustworthy derivation for trusted_index_exists or EmbeddingCompatibility
- Deferred seam requirement: planner_policy_change_gap: RepositoryDelta.policy_changed is not represented by IndexExecutionPlan or source_state_changed
- Deferred seam requirement: typed_completion_gate_boundary: the manifest-advance gate requires the in-process IndexCompletionDecision, but index_repository exposes only its serialized dictionary
- Deferred: production applied-manifest load and observed-state build
- Deferred: delta-plan-controlled parse/embed/replace/delete dispatch
- Deferred: confirmed identity permission enforcement at every caller
- Deferred: manifest commit and applied-manifest receipt creation
- Deferred: web propagation of additive completion/delta metadata
- Deferred: Activation Graph runtime and legacy namespace migration

## 12. Recommended next phase

BLOCKED — resolve identified INDEX prerequisite/failure first

No production indexing behavior was changed by this preflight.
