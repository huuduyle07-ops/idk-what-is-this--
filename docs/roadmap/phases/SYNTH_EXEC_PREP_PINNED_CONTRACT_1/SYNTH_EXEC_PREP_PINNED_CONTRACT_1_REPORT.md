# SYNTH.EXEC.PREP.PINNED.CONTRACT.1

**Typed result: PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION.**

The preparation analysis is frozen and operational readiness remains
`false / PROOF_UNRESOLVED`. No preparation or consumer owner is implemented.
All concrete downstream rules below are blocked proposals until the named
requirement evolution is reviewed. This phase does not supersede history.

## Why requirement evolution is necessary

The frozen [reflection contract](../SYNTH_REFLECT_PINNED_CONTRACT_1/contract.json)
at `first_behavior_boundary.first_behavioral_effect` explicitly says
`BEFORE exact read` (line 389). The exact 239-byte fixture in
`core/synthetic_runtime_authorization.py:36` contains
`private int value = 10;` (line 37). Ordinary construction creates mutable
scenario state and initializes this field before its BEFORE read. There is no
explicit constructor or static initializer in the frozen source.

The abstract consume-before-first-effect policy and the relative pinned
reflection sequence remain compatible with a launch boundary. The stronger
historical assertion that BEFORE read itself is first is incompatible with
truthful constructor semantics. Classifying construction as preparation merely
to retain that assertion would spend scenario activation authority too late.

Required evolution: explicitly supersede that first-effect assertion in a
separate reviewed requirement, preserve all historical bytes, and adopt a
deterministic activation boundary before the scenario-capable JVM is dispatched.
Retain the existing lease order and no-refund policy. The existing runtime
`_consumer_readiness` gate still unconditionally rejects before its terminal
commit; no policy digest, owner, API, registry entry or source fixture changed.

## Effect classifications

| Operation | Proposed class | Exact scope and placement |
| --- | --- | --- |
| Source projection in memory | `PURE_DERIVATION` | Obtain the existing literal; full exact bytes/hash/size comparison; no regeneration. |
| Sandbox source materialization | `PREPARATION_EFFECT` | One exclusive binary write/readback in an authenticated ephemeral workspace; runtime stays ISSUED. |
| Exact `javac` compilation | `PREPARATION_EFFECT` | Closed compiler/input/template/output scope; no scenario loading, initialization, construction or invocation. |
| Scenario JVM startup | `BEHAVIORAL_ACTIVATION_EFFECT` | Conservative first activation operation: consume runtime and BEFORE permission before dispatching this JVM. |
| Target class loading/linking | `BEHAVIORAL_ACTIVATION_EFFECT` | Reserved to the activated consumer; noninitializing metadata loading does not itself imply a field mutation. The loader/full harness is not yet frozen. |
| Target class initialization | `BEHAVIORAL_ACTIVATION_EFFECT` | Separate from loading; exact source has no static initializer. No generic initialization permission. |
| Ordinary object construction | `BEHAVIORAL_EFFECT` | Initializes `value = 10`; the first known source-level state effect, before observation. No constructor reflection. |
| BEFORE reflection read | `BEHAVIORAL_EFFECT` | Exact role-specific primitive read after its permission commit; a later effect, not proof of construction or decrement success. |

The first proposed operational effect is **launch of the exact scenario JVM**.
Its dispatch is gated because it can enter harness/loader code and construct the
scenario before any read. Compiler JVM startup is bounded preparation; an
independently proved inert infrastructure bootstrap has different semantics.
This does not infer that every process launch is scenario behavior or that every
Java execution is preparation. The full harness is unavailable, so no exact
earliest harness instruction is invented.

Proposed order after all proof gates and inert source/harness readiness:

1. Consume pinned runtime lease.
2. Authenticate and consume BEFORE reflection lease.
3. Dispatch scenario JVM; load/link/initialize exact target and ordinarily construct it.
4. Perform BEFORE exact reflection read.
5. Invoke `boolean SyntheticStateBox.decrement(int)` with argument `3`.
6. Authenticate and consume AFTER reflection lease, then perform AFTER exact reflection read.
7. Finish or abort the consumer and verify final cleanup.

Only mandatory permission checks/commits intervene between runtime consumption
and launch. No compilation, source preparation, unreviewed behavior or retries
may be inserted there. A later failure spends activation without refund. The
future exact harness/controller must stage the AFTER read until the real owner
has committed AFTER permission; a caller Boolean/string cannot authorize it.

## Exact source and materialization authority

Only `synthetic.EXECUTOR.1R.decrement_3` is in scope. Source SHA256:
`813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302`;
size **239 bytes**; definition SHA256:
`e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d`.
The class is `SyntheticStateBox`; field is `SyntheticStateBox.value:int`.
The existing source accessor owns exact bytes; unchanged public pinned
authorization validation authenticates their scenario identity. Identity,
obtained bytes, sandbox write, class output and behavior are separate facts.

Proposed `core.synthetic_execution_preparation_pinned` independently owns one
narrow one-shot preparation authority plus an immutable success receipt. Its
materialization and compilation facets are separately scoped, never
interchangeable. Each facet is reserved immediately before its one attempted
effect; failure spends that attempt and creates no ready receipt. Bind the
original runtime/auth graph and actual workspace generation; no refund/reissue
for the same attempt. No generic write/command API or broad runtime authority.

Materialize only `/work/SyntheticStateBox.java`, by exclusive binary creation
with exact full readback. `/work` must be an initially empty, exclusively
controlled, already-authorized container tmpfs. Allow that authenticated mount;
reject unexpected subordinate mounts, symlinks, hardlink aliases, special files,
path traversal/NUL/backslash/aliases and any overwrite, even identical bytes.
Create only `/work/classes`. Maximum source files: **1**, source bytes: **239**;
maximum source/output regular files under `/work`: **2**. No host repository
mutation, arbitrary materialization, source conversion or host extraction.

## Exact compilation contract

JAVA.1C proves infrastructure compilation of `JavaSandboxProbe.java`; it does
not grant scenario compilation. Its no-argument operational API/controller is
unchanged and must not be adapted or called for this scenario. Recover all
historical flags from `core/sandboxed_java_toolchain_probe.py:9` and the
[JAVA.1C report](../RUNTIME_JAVA_1C/RUNTIME_JAVA_1C.md). The proposed new exact
scenario template changes only the final source operand:

```json
["/opt/temurin-26.0.2.1/bin/javac", "-J-Xms8m", "-J-Xmx32m", "-J-XX:ActiveProcessorCount=1", "-J-XX:-UsePerfData", "-d", "/work/classes", "/work/SyntheticStateBox.java"]
```

Use an argument array, `shell=false`, cwd `/work`, and the exact eight-variable
frozen sandbox environment recorded in the contract. No new flags, argument
files, Maven, Gradle, plugins/processors, dependencies, classpath selection,
environment extensions, shell or network. The exact source has no
imports/annotations; immutable image/JDK plus the empty exclusive input closure
must preclude external processor/config/JAR inputs. Do not invent `-proc:none`.

| Binding | Exact value |
| --- | --- |
| Javac path | `/opt/temurin-26.0.2.1/bin/javac` |
| Javac SHA256 | `e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023` |
| Immutable image | `sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a` |
| Sandbox | `runtime_sandbox_2_v1` |
| Policy SHA256 | `5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75` |
| Output | `/work/classes/SyntheticStateBox.class` only |

Preserve every SANDBOX.2 gate: network none, read-only root, no host mounts or
image volumes, UID/GID 65534:65534, CapDrop ALL, no-new-privileges, exact namespace
and cgroup isolation, 128 PIDs, 134217728 bytes memory and one CPU. Only `/work`
32 MiB `rw,nosuid,nodev,1777` and `/tmp` 16 MiB
`rw,nosuid,nodev,noexec,1777` tmpfs are writable. Authenticate actual backend,
container, generation, controller executable/source and live workspace against
the retained provider graph. Provider proof's already-cleaned workspace cannot
be the live scenario workspace. This contract grants no sandbox issuance.

One compilation attempt; compiler streams at most 2048 bytes each, outer streams
8192 bytes each, 10000 ms outer timeout and 5000 ms shared controller deadline.
Success requires zero exit, empty complete compiler stdout/stderr, both EOFs,
reaped compiler, unchanged exact source and the full bounded output manifest.
Exactly one regular class file, **1..32768 bytes**: explicitly adopt JAVA.1C's
envelope, without inventing a measured scenario class hash/size. Hash actual
bytes; check complete paths/types/sizes/digests and bounded inert class metadata.
Never load a class to verify it. Unexpected output fails closed and tears down
the attempt. Zero exit alone proves neither source identity nor behavior.

## Authenticated preparation and consumer evidence

One proposed `PinnedSyntheticPreparationReceipt`, schema
`synthetic_preparation_receipt_pinned_1_v1`, contains distinct authenticated
source/readback and compile/manifest evidence. It binds original authority,
auth/runtime/provider graph, PID, exact source/definition/invocation, live
backend/container/workspace/controller generation, image/compiler/argv/
environment, capture/reaping, manifest and cleanup state. It is **evidence**,
never runtime authority or execution permission. Scenario preparation excludes
harness files and cannot claim whole-executor readiness.

The known renderer is
`SYNTH.REFLECT.1.render_synthetic_read_only_reflection`, schema
`synthetic_reflection_request_v1`. Exact helper SHA256s are:

- BEFORE: `c88aeea914c88ef17a335a184abe6d5b618a9c0c70a7121621ba67edd9919531`.
- AFTER: `4d85951e886bfedabae50c7f64e8e0fa4985e8fa515e4edab9af0a355b10f4ea`.

These are methods, not a runnable harness. Historical retry fields retain
`harness_sha256=None`. Full harness source bytes/hash/size, compiler manifests,
main/JVM argv, loader/controller source and staged permission protocol must be
separately reviewed and pinned. No caller-selected digest can replace that
missing proof, and this phase invents no harness bytes or permissions.

Proposed consumer owner `core.synthetic_execution_consumer_pinned` produces
`PinnedSyntheticConsumerReadinessEvidence`, schema
`synthetic_consumer_readiness_pinned_1_v1`. It binds the exact original
runtime/auth graph, both role-specific request/admission/lease graphs in ISSUED,
original preparation receipt, separately reviewed full harness preparation
proof, renderer/helpers, reflection primitive, actual live sandbox/controller,
exclusive artifact integrity and fixed launch handoff. Runtime understands its
narrow public authenticated evidence contract, not arbitrary executor internals.

Both proposed owners use independent process-local secrets/domains and original
live object registries. Strict canonical domain-framed HMAC-SHA256 authenticates
bindings; an evidence digest is only an identifier. Reject wrong PID before
locks, copies, reconstruction, JSON, report copies, IDs, fingerprints, Boolean,
wrappers and substituted graphs. Retain exact originals and public upstream
validators. JSON exports remain report-only; never export secrets/signatures or
restore authority from a report.

Readiness is reusable only for read-only validation of the same preactivation
attempt/process. It grants no effect and has no extra consumption state. Live
artifact changes, cleanup, timeout/abort, lost controller, generation change or
terminal runtime state ends eligibility. Runtime consumption makes it unusable
for another activation; authentic historical evidence may remain inspectable.

The future gate must fully authenticate the graph and live artifact handoff
**outside** runtime lock, then verify a narrow locally authenticated handoff and
repeat runtime-local checks before its single locked terminal commit. The
runtime lock is non-reentrant, and reflection validation calls back into runtime:
no full graph callback may recursively acquire it. Recheck public role gates
at each reflection consume outside runtime lock. There is no cross-owner atomic
transaction; races abort before the affected effect, without refund after runtime
commit. Exact integration/signatures/lock order require a later reviewed slice.

BEFORE and AFTER admissions/leases are prepared while runtime remains ISSUED.
Their existing preexecution/active distinction is preserved: runtime CONSUMED
is required for reflection consumption, not preparation. Neither preparation nor
readiness requires premature runtime consumption.

## Cleanup, errors and authority

Preparation success records `LIVE_EPHEMERAL_ARTIFACTS_CLEANUP_PENDING`.
Keep exact artifacts in the same exclusively controlled ephemeral workspace
until consumer completion/abort/timeout. Preparation owner owns workspace
lifetime; the consumer borrows it; bound controller performs and independently
verifies teardown. Preparation failure also requires teardown. Reap all children
and groups, observe EOFs, close captures, remove container and both tmpfs
workspaces, and verify absence. Cleanup success is a separate result from
preparation and behavior success. Cleanup failure blocks readiness and is never
hidden by a successful compile.

No source, class, harness or workspace snapshot persists after final cleanup.
Only bounded source-free/class-free hashes, sizes, manifests and cleanup
metadata may survive as report-only audit evidence. Documentation/validation
writes in this phase are distinct from runtime filesystem writes, which are zero.

Typed failures are `SOURCE_IDENTITY_MISMATCH`, `SOURCE_BYTES_MISMATCH`,
`MATERIALIZATION_NOT_AUTHORIZED`, `MATERIALIZATION_SCOPE_MISMATCH`,
`COMPILATION_NOT_AUTHORIZED`, `COMPILER_IDENTITY_MISMATCH`,
`COMPILER_ARGUMENT_MISMATCH`, `COMPILE_FAILED`, `COMPILE_OUTPUT_MISMATCH`,
`HARNESS_IDENTITY_MISMATCH`, `PREPARATION_EVIDENCE_UNAUTHENTICATED`,
`PREPARATION_EVIDENCE_STALE`, `CONSUMER_READINESS_UNAUTHENTICATED`,
`CONSUMER_READINESS_UNRESOLVED`, `CLEANUP_UNRESOLVED`, and `PROOF_UNRESOLVED`.
The machine contract defines each condition. Preserve known upstream code/reason;
semantic mismatches are not relabeled as authentication failures. Missing full
harness/consumer proof is unresolved; forged proof is unauthenticated; an
authentic expired workspace snapshot is stale.

All **31 authority flags** in `contract.json.authority_flags` are false,
including exact materialization/compilation, runtime activation/runtime,
repository/source writes, Apply, network, host mounts, shell, arbitrary
Java/commands/source/classes/methods/loading/reflection, field writes, private
methods, enumeration, executor and BANK. Source identity validation grants no
write authority; reflection permission grants no preparation authority; effect
evidence grants neither.

All **21 operational effect counters** in `contract.json.operational_effects`
are zero: Docker, SANDBOX2, JAVA1C, every issuance, capability consumption and
invalidation, source materialization/runtime writes, javac/java/loading,
reflection, SyntheticStateBox, BANK, EXECUTOR.1R and Apply. No operational owner
is imported/called by guarded validation. No source or compiled class is written.

## Validation and historical preservation

Measured counts and exact failed nodes are in [validation_summary.json](validation_summary.json).

Measured final results: contract/source **49 passed**; frozen AST **14 passed**; 2196 pre-existing scoped files unchanged; in-memory Python compilation **1313 files**; no syntax/JSON/whitespace errors; git diff --check exit 0. Guarded operational attempts and owner imports: **zero**.
The [evidence index](evidence_index.json) pins 23 source/contract files by raw
byte SHA256 and exact line anchors. AST/source tests verify exact frozen bytes,
the first-effect contradiction, recovered argv, requirement pins, helper hashes,
bounded proposed scopes, fail-closed owner gates, ordering and absent new owners.
They never import operational owners or execute their test fixtures.

Guarded registry/picker baseline and after must have identical test outcomes
and projections. Baseline: **299 collected, 292 passed, 7 pre-existing failed**;
failures are preserved rather than repaired. Benchmark `--check`: **54 cases,
0 errors**. In-memory Python compilation, JSON/whitespace, `git diff --check`
and raw-byte preservation cover this phase. Git status/diff are source-control
validation processes recorded outside the operational guard. Full operational
and issuance-dependent suites are not run. There are no new registry entries.

Historical hashes include pre-existing dirty/untracked sources and reports,
provider/auth/runtime/reflection owners, compiler/sandbox policies, registry,
reversals and executor stops. Preserve the executor refresh's independent-source
stop, retry's missing old consumption contract, and lifecycle retry's frozen
Java profile mismatch. They are source-audited, never replayed.

## Recommended next slice

Resolve the explicit historical first-effect requirement conflict in a separate
contract review. After that review, consider an independently authorized pure
preparation authority/receipt implementation with inert fixtures and no effect
adapter. Separately freeze the full harness/protocol, then review narrow
consumer evidence and runtime integration. Keep operational readiness false
until all original authenticated proofs and authority gates exist.

**STOP. No preparation or consumer owner implementation; no operational authority.**
