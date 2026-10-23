# SYNTH.EXEC.PREP.PINNED.CONTRACT.CLOSE.1

**SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1_COMPLETE**

The prior preparation proposals have been reviewed against the revised activation
boundary and are now frozen preparation semantics. No owner, authority or
operational effect exists. This closure is additive; the prior PREP outcome
`PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION` remains unchanged in history.
`SYNTH.EXEC.ACTIVATION.BOUNDARY.REQ.1` already resolved its named first-effect
conflict for this exact scenario. No additional historical claim is superseded.

| Prior proposal | Effect/constraint | Closure classification |
| --- | --- | --- |
| 1. `in_memory_source_projection` | `PURE_DERIVATION` | `ACCEPTED_UNCHANGED` |
| 2. `sandbox_materialization` | `PREPARATION_EFFECT` | `ACCEPTED_UNCHANGED` |
| 3. `javac_compilation` | `PREPARATION_EFFECT` | `ACCEPTED_WITH_ADDITIVE_CLARIFICATION` |
| 4. `JVM_startup` | `BEHAVIORAL_ACTIVATION_EFFECT` | `ACCEPTED_WITH_ADDITIVE_CLARIFICATION` |
| 5. `target_loading_initialization_construction` | `AFTER_ACTIVATION_BOUNDARY` | `ACCEPTED_UNCHANGED` |
| 6. `no_preparation_after_runtime_consumption` | `ORDERING_INVARIANT` | `ACCEPTED_UNCHANGED` |

Items 3 and 4 add scope clarification: the compiler's infrastructure JVM is
distinct from dispatch of the exact scenario-executing JVM. The latter boundary
is now an adopted requirement. No compiler arguments, source bytes, workspace
controls, preparation limits or runtime/reflection permissions are widened.

The exact scenario is `synthetic.EXECUTOR.1R.decrement_3`: existing 239-byte source
SHA256 `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302`,
definition SHA256 `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d`,
`SyntheticStateBox`, `boolean SyntheticStateBox.decrement(int)`, argument `3`,
field `SyntheticStateBox.value:int`. Source/AST inspection authenticates the
existing literal only. The instance initializer `value = 10` occurs on ordinary
construction before observation. Source evidence contains one class and no
imports, annotations, explicit constructor or static initialization. There is no
source contradiction with the closed inert compilation contract.

Materialization retains the exact exclusive ephemeral `/work` tmpfs and binary
exclusive creation at `/work/SyntheticStateBox.java`: no overwrite, shared writer,
symlink, hardlink, special file, traversal or unexpected mount crossing; full
239-byte readback. No host repository mutation or persistent source/class export
is permitted. The original path and workspace controls are retained verbatim.

Compilation retains `/opt/temurin-26.0.2.1/bin/javac`, SHA256
`e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023`, image
`sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`,
`runtime_sandbox_2_v1` and policy SHA256
`5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75`.
Exact argv:

```json
[
  "/opt/temurin-26.0.2.1/bin/javac",
  "-J-Xms8m",
  "-J-Xmx32m",
  "-J-XX:ActiveProcessorCount=1",
  "-J-XX:-UsePerfData",
  "-d",
  "/work/classes",
  "/work/SyntheticStateBox.java"
]
```

`shell=false`, `cwd=/work`; exact eight-variable environment only, one attempt,
no Maven/Gradle, network, arbitrary classpath, caller flags, argument files,
processors, plugins or dependency inputs. Compilation may only transform the
exact source into inert bytes; no target loading, initialization, construction
or invocation. Any contradictory source evidence stops closure.

Output remains exactly `/work/classes/SyntheticStateBox.class`, one class file
of 1..32768 bytes, no extra outputs, unchanged source, full no-follow workspace
manifest, actual class-byte hashing and bounded inert class metadata inspection.
Never load the class for validation. No predicted class hash or successful
compilation is claimed. Full capture, resource, timeout and reaping bounds remain
the prior contract's acceptance conditions.

The future narrow owner `core.synthetic_execution_preparation_pinned`, type
`PinnedSyntheticPreparationAuthority`, schema
`synthetic_preparation_authority_pinned_1_v1` retains two non-interchangeable
facets: `exact_sandbox_materialization_authority` and
`exact_scenario_compilation_authority`. Each has one attempt, reserved immediately
before its effect; failure spends it, with no refund or reissue. Both bind exact
original runtime/auth/workspace generation and controller/provider graph.
Compilation requires verified materialization. No generic file/command API or
sandbox issuance is defined. This phase implements or issues none of them.

`PinnedSyntheticPreparationReceipt`, schema
`synthetic_preparation_receipt_pinned_1_v1`, remains authenticated evidence with
false runtime and execution permission. It may prove only exact source
authentication, materialization/readback, compiler identity, exact
argv/environment, compile result, bounded output manifest, live workspace
generation and cleanup pending. Its original graph/signature/context bindings
authenticate those claims; they add no harness, consumer or behavior claim.
It cannot alone unlock runtime consumption.

**Preparation contract complete != harness contract complete.** Full harness
source/hash/size, main class, scenario JVM argv, loader/controller source and
staged permission protocol remain null/unresolved. Existing reflection helper
hashes are insufficient. Consumer review is dependency shape only: the receipt
may later be one input. No final consumer owner, schema, API, authentication
domain or runtime-lock integration is frozen or implemented. Runtime consumption
remains **PROOF_UNRESOLVED** until full harness and consumer evidence are
separately reviewed; the existing unconditional owner gate is unchanged.

The revised sequence is:

1. Authenticate all gates; prepare BEFORE/AFTER admissions and leases while runtime is ISSUED.
2. Authenticate/project exact source, exclusively materialize/read back, compile, and authenticate bounded preparation evidence.
3. Authenticate separately reviewed full harness and consumer readiness and complete live integrity/handoff checks.
4. Consume runtime lease, then consume BEFORE reflection permission.
5. Dispatch exact scenario JVM; only then target loading/linking/initialization/construction, BEFORE read and exact decrement(3).
6. Consume AFTER permission before AFTER read; finish/abort and independently verify cleanup.

No preparation occurs after runtime consumption; only mandatory authenticated
permission checks/commits may precede dispatch. No launch before both runtime
and BEFORE commits, and no refund after runtime consumption, including launch
failure. Required teardown/reaping/absence verification are cleanup duties and
do not authorize a new preparation attempt. Permission consumption proves no
observed effect.

Measured validation: **20 focused closure tests passed**;
registry/picker baseline and after each collected 299
tests, with 292 passing and
7 identical existing failures. Exact node results
and registry/picker projections are unchanged. Benchmark `--check`: **54
cases, zero errors**. In-memory Python compilation: **1347
files**. JSON/whitespace and `git diff --check` passed.
**26759 pre-existing non-cache files/links are
unchanged**, with no additions outside this phase. Snapshot records exclusions
and never follows links. All operational guard counters and capability-owner
imports are zero. No full issuance-dependent suite was run.

Existing registry/picker failures, preserved exactly:

- `tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation` (call)
- `tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets` (call)
- `tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked` (call)
- `tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call` (call)
- `tests/test_phase_registry.py::test_seed_registry_has_expected_phases` (call)
- `tests/test_phase_registry.py::test_seed_registry_is_conservative` (call)
- `tests/test_phase_registry.py::test_seed_registry_summary_counts` (call)

All 33 authority flags are false; all
21 operational effect counters are zero.
No owner implementation, capability issuance/consumption, source/class
materialization, javac/java/Docker invocation or runtime/reflection modification
occurred. Only additive documentation and pure validation support were written.

See [contract.json](contract.json), [evidence_index.json](evidence_index.json),
[validation_summary.json](validation_summary.json) and
[preservation_comparison.json](preservation_comparison.json).

**STOP after closure. No preparation owner implementation is authorized.**
