# SYNTH.EXEC.PREP.WORKSPACE.CONTRACT.1

**WORKSPACE_REQUIRES_CONTROLLER_EVOLUTION**

The live ephemeral workspace and controller binding boundary is frozen as an
additive pure contract. The existing controller cannot support a truthful
retained live empty workspace or exclusive artifact handoff. An additive
controller is required. No workspace, container, preparation authority,
runtime/reflection permission or operational owner is created by this phase.

## Controller finding

`core/sandboxed_java_positive_probe.py:81` implements one fixed historical
fixture: empty `/work`, exclusive `JavaSandboxProbe.java`, `/work/classes`,
fixed compilation, then fixed Java dispatch. Its `source()` at line 121 accepts
no caller source/flags/environment/stdin. The outer historical controller at
`core/sandboxed_java_positive_continuation.py:338` always kills/removes the
container and independently checks absence before returning. Provider success
requires that cleanup. Historical receipts therefore authenticate completed
proofs, never a current retained workspace. SANDBOX.2 and PINNED provider cleanup
evidence are preserved unchanged.

The historical executable is `/usr/local/bin/python`, resolved to
`/usr/local/bin/python3.12`, SHA256
`0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263`.
Historical generated controller source is 13037 bytes, SHA256
`4f81640e2f01bc1f7a1a833beb269a9d1df51088b69cf24c8369fb6683f11a58`.
These identify the historical proof. They do not identify a new retained
controller. New controller source/hash/size/protocol are unresolved; no digest
is invented and no historical API is widened.

## Workspace boundary

The future independent owner is
`core.synthetic_execution_preparation_workspace_pinned`, exact type
`PinnedSyntheticPreparationWorkspace`, schema
`synthetic_preparation_workspace_pinned_1_v1`. Only an original registered
process-local object may authenticate. Copies, wrappers, subclasses, JSON,
container IDs and fingerprints cannot substitute for it. Its retained original
authorization/runtime/provider graph must authenticate through unchanged public
validators. Same image or route/version strings never establish provider
authenticity, daemon continuity or generation identity.

The exact SANDBOX.2 image, policy, environment, namespaces, resources and tmpfs
settings are retained. `/work` must be the authenticated isolated empty tmpfs.
`/work/classes` is **absent at workspace readiness**. Its exclusive creation
belongs to the frozen preparation materialization/compile attempt, consistent
with PREP closure's `directories_created`; workspace bootstrap creates none.
No source, class, harness, JAR, processor, plugin, config input, link, unexpected
mount, special file, target JVM or SyntheticStateBox instance is present.

Workspace possession represents only exact location/liveness/control binding.
It grants no `/work` write, materialization, compilation, activation, reflection,
shell, arbitrary command/source/class loading, repository write, Apply,
executor or BANK permission. Future materialization and compilation require
both the same original live workspace generation and the appropriate original
unspent preparation-authority facet. Preparation remains the permission owner
and owns facet spending. A receipt is evidence only; no cross-generation
receipt or host source/class export is allowed.

## Authentication and lifecycle

An independent domain is frozen:
`CATTUS:SYNTH.EXEC.PREP.WORKSPACE.PINNED.1:exact-live-workspace:v1`.
Strict canonical domain/role-framed HMAC-SHA256 uses an independent secret and
exact original registry identity. The public stable fingerprint covers only
immutable identity. Current controller/container generation, exclusive control,
manifest, observation sequence/challenge, handoff and cleanup predicates are
separately authenticated. Historical signatures and timestamps cannot establish
current liveness. No SANDBOX, provider, preparation, runtime or reflection
private secret/state is reused.

The current workspace-state digest has a fixed SHA256 domain/role and canonical
payload: exact generations/observation challenge, authenticated mounts, complete
sorted no-follow `/work` and `/tmp` manifests, file sizes/full hashes/link counts,
and process/writer exclusivity observations. Its scope and digest are covered by
the current-state HMAC. Only metadata is hashed for reporting; a scalar digest
cannot authenticate readiness or authorize exporting artifact bytes.

Predicates describe live, exclusive, preparation-empty, prepared artifacts,
handoff-active, cleanup-started, cleanup-complete and invalid conditions; no
speculative public state machine/API is implemented. Partial preparation proves
neither emptiness nor prepared readiness. Controller loss, generation change or
unexpected artifacts invalidates readiness. Cleaned or invalid generations
cannot be revived. Exclusive handoff still requires separately reviewed consumer
authority and exact original artifact/receipt/generation binding.

Before every future guarded effect, relevant owners reauthenticate their own
originals; runtime must be `ISSUED`. Its report-only lease-local preconditions
may be satisfied while behavioral activation readiness remains false with
`PROOF_UNRESOLVED`. No cross-owner transaction or private lock bridge is claimed.
The future controller must enforce its own operation/cleanup admission fence;
unobservable coordination gaps fail closed. Cleanup-started denies new
preparation. Eligibility loss before effect aborts it; spent facets receive no
refund. Provider/backend mismatch, controller loss, disappearance and generation
replacement cannot be repaired using equal scalar projections.

## Cleanup and remaining gates

Preparation retains its existing attempt lifecycle accountability. The workspace
owner/controller owns containment identity and cleanup evidence; consumer
handoff never removes the cleanup duty. Cleanup must remain possible after
preparation/consumer/activation failure, timeout, abandonment or upstream
invalidation, including controller loss. The independently authorized fixed
teardown path uses retained immutable identity without requiring current
readiness, an `ISSUED` runtime, unspent facets or a lost controller challenge.
It never recreates authority or readiness.

Cleanup evidence separately proves child/process-group reaping, closed
captures, exact container removal, disappearance of both tmpfs generations,
fresh independent absence observation and no surviving raw artifact export.
Preparation success retains live artifacts with cleanup pending until final
consumer/attempt completion. Cleanup success, preparation success and behavior
success remain distinct. `WORKSPACE_CLEANUP_UNRESOLVED` blocks readiness.
All requested workspace errors are defined; known upstream typed errors retain
their status/reason, and semantic mismatches are not authentication failures.

The future additive controller must provide exact executable/source/protocol
identity, fresh liveness observations, fixed bounded preparation operations,
exclusive handoff, capture/reaping and independent cleanup. Implementation and
issuance are outside this phase. Full harness source, main, scenario JVM argv,
loader and staged BEFORE/AFTER protocol remain unresolved. Behavioral readiness
is **false / PROOF_UNRESOLVED**. No consumer, harness or executor is implemented.

## Measured pure validation

- Focused contract checks: **25/25 passed**.
- Registry/picker baseline and after: **299 collected,
  292 passed, 7 pre-existing failures**;
  node results, assertion signatures and projections are unchanged. Comparison
  normalizes only Python repr allocator addresses; raw diagnostics are retained.
- Benchmark `--check`: **54 cases, 0 errors**.
- In-memory Python compilation: **1351 files**. JSON,
  authored AST imports, whitespace and Git whitespace checks passed; no bytecode
  or Git index mutation. Existing Git whitespace baseline is unchanged.
- **26787 existing non-cache files/links unchanged**,
  with no additions outside this new phase. The immutable inventory records
  cache/Git exclusions and never follows links.
- All operational guard counters and capability-owner imports are zero.
  All 36 authority flags are false and all
  24 operational counters are zero. Full
  issuance-dependent suites were not run.

Preserved registry/picker failures:

- `tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation` (call)
- `tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets` (call)
- `tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked` (call)
- `tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call` (call)
- `tests/test_phase_registry.py::test_seed_registry_has_expected_phases` (call)
- `tests/test_phase_registry.py::test_seed_registry_is_conservative` (call)
- `tests/test_phase_registry.py::test_seed_registry_summary_counts` (call)

See [contract.json](contract.json), [evidence_index.json](evidence_index.json),
[validation_summary.json](validation_summary.json) and
[preservation_comparison.json](preservation_comparison.json).

**STOP. Do not implement or issue the workspace or preparation owner.**
