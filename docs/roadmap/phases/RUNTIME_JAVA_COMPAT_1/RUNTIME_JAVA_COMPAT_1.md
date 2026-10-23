# RUNTIME.JAVA.COMPAT.1 — frozen Java contract audit

2026-10-08 KST. **RUNTIME_JAVA_COMPAT_1_BLOCKED_SEMANTIC_GAP**.

No compatibility bridge is exposed. JAVA.1C proves the same exact Java image, binary paths/digests, fixture source and invocation restrictions, with stronger capture and cleanup checks. It does not prove two explicit prerequisites of the original runtime_java_1_v1 success contract: complete local artifact discovery and matching discovery-to-sandbox backend identity/version. The corresponding original receipt provenance is also unproven.

[Typed audit owner](../../../../core/java_runtime_compatibility.py), [pure tests](../../../../tests/test_runtime_java_compat1.py), [guarded audit replay](../../../../scripts/replay_runtime_java_compat1.py), [full recorded evidence](RUNTIME_JAVA_COMPAT_1_LOCAL.json), and [historical preservation manifest](RUNTIME_JAVA_COMPAT_1_PRESERVATION.json).

## Exact identities

| Role | Java profile | Java schema | Sandbox profile/phase | Sandbox schema | Sandbox policy SHA-256 |
| --- | --- | --- | --- | --- | --- |
| Frozen SYNTH.AUTH.1 requirement | RUNTIME.JAVA.1 | runtime_java_1_v1 | runtime_sandbox_2_v1 (requirement profile ID) | runtime_sandbox_2_v1 | 5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75 |
| Audited provider | RUNTIME.JAVA.1C | runtime_java_1c_v1 | RUNTIME.SANDBOX.2 | runtime_sandbox_2_v1 | 5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75 |
| Original Java owner | RUNTIME.JAVA.1 | runtime_java_1_v1 | RUNTIME.SANDBOX.1 | runtime_sandbox_1_v1 | 855462482bcdd76cd2b52d8cdd40683af1165a47c041d687bc64723acc4e1447 |

The required sandbox profile string is preserved exactly as SYNTH.AUTH.1 defines it. It is distinct from the sandbox owner's phase ID. Identity equality asserted: **false**. Profile/schema relabeling: **false**. Historical receipts rewritten: **false**. Compatibility relation: **none**, relation count **0**, contract_compatible **false**, live_provider_authenticated **false**. All compatibility/runtime/repository-write/Apply authority flags are false. There is no lease or consumption lifecycle for this audit.

## Exact missing proofs

1. **complete_local_artifact_discovery**. The original `verify_sandboxed_java_toolchain` rejects `inventory.complete_inventory == false` with `java_artifact_discovery_incomplete` before any Java workload. Its signed receipt exposes `discovery_complete` and `artifact_inventory`. JAVA.1C inspects the exact pinned image and rehashes both binaries, but performs no complete inventory and publishes no equivalent witness. Exact artifact identity does not prove inventory completeness.
2. **discovery_backend_binding**. The original verifier rejects any mismatch in discovery backend identity or backend version versus the authenticated sandbox descriptor with `java_runtime_boundary_incomplete:backend_binding_changed`. JAVA.1C and SANDBOX.2 expose no corresponding inventory/backend identity/version binding. Shared sandbox fingerprints and a fixed local Docker route do not establish that missing success-gate claim.
3. **runtime_receipt_semantics**. This is the receipt-level consequence of the preceding gaps: the separate JAVA.1C receipt binds successful fixed Java measurements and an evidence digest, but cannot stand in for the original receipt's discovery provenance. No receipt is reconstructed, translated, or re-signed.

New pure negative controls exercise the original unchanged success gates with explicitly fabricated discovery inputs and prove all three missing-witness variants stop before temporary workspace creation, boundary probes or Java launch. They issue no positive runtime evidence. The audit preserves the full original success contract; no owner-defined waiver permits narrowing it to successful fixture execution alone. No JAVA.1C repair or SYNTH.AUTH.1 change is made in this phase.

The original historical JAVA.1 descriptor remains available=true, verified=false. JAVA.1C's historical successful report is evidence of its own frozen contract, never a fresh capability in this process.

## Semantic comparison matrix

| Dimension | Original requirement / frozen promise | JAVA.1C provider | Assessment |
| --- | --- | --- | --- |
| toolchain_image_identity | sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a | sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a | equal |
| platform | linux/amd64 | linux/amd64 | equal |
| java_executable_path | /opt/temurin-26.0.2.1/bin/java | /opt/temurin-26.0.2.1/bin/java | equal |
| java_executable_digest | a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2 | a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2 | equal |
| javac_executable_path | /opt/temurin-26.0.2.1/bin/javac | /opt/temurin-26.0.2.1/bin/javac | equal |
| javac_executable_digest | e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023 | e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023 | equal |
| java_version_expectations | Nonempty successful exact binary -version; no generic version range | Same binaries; versions bound through freshly authenticated SANDBOX.2 ladder | intentionally_different |
| compiler_invocation_restrictions | Frozen javac argv; phase source only; no caller flags | Imports identical COMPILE_ARGUMENTS; no caller inputs | equal |
| runtime_invocation_restrictions | Frozen JVM argv; /work/classes; JavaSandboxProbe only | Imports identical RUNTIME_ARGUMENTS; no caller inputs | equal |
| bounded_capture | Independent bounded pipes with two reader threads | Independent bounded nonblocking pipes with one selector thread, EOF and cleanup checks | stronger_provider |
| timeout | 10000 ms outer bound; 5000 ms abort cutoff | Same outer bounds plus shared 5000 ms controller deadline | stronger_provider |
| stdout_cap | 8192 outer; 2048 compiler; 1024 runtime/version | 8192 outer; 2048 compiler; 1024 runtime/version | equal |
| stderr_cap | 8192 outer; 2048 compiler; 1024 runtime/version | 8192 outer; 2048 compiler; 1024 runtime/version; bounded separate progress | equal |
| cleanup | Child wait, pipe close and verified container removal; ephemeral outputs | Also process-group kill/reap, selector cleanup, both EOFs, only PID 1 remains | stronger_provider |
| network_prohibition | network none; socket/connect syscall denials | Identical restriction and original hostile probes | equal |
| host_mount_prohibition | No Binds, Mounts or image volumes | Same independently inspected prohibition | equal |
| root_filesystem | Read-only root | Same; also measured before/after | stronger_provider |
| uid_gid | 65534:65534 | 65534:65534 | equal |
| capability_drop | ALL; no CapAdd; effective capabilities zero | Same | equal |
| no_new_privileges | true | true | equal |
| pid_namespace_budget | Private PID namespace/cgroup; 128 PIDs; descendants contained | Same; observes all seven namespaces and child cgroups | stronger_provider |
| memory_limit | 134217728 bytes | 134217728 bytes | equal |
| cpu_limit | 1000000000 NanoCpus (one CPU) | Same; measured quota equals period | stronger_provider |
| environment_closure | Exact frozen eight-variable environment | Exact same environment | equal |
| temporary_filesystems | /work rw,nosuid,nodev,32m,1777; /tmp rw,nosuid,nodev,noexec,16m,1777 | Same; removal of container destroys both | equal |
| seccomp_policy | SYNTH.AUTH.1 explicitly requires exact SANDBOX.2 hash 5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75 | Exact required hash; clone3 errno EPERM -> ENOSYS; execution remains denied | intentionally_different |
| controller_threads | Historical controller attempts reader threads; no single-thread guarantee | Python/OS thread count one before/after; Thread.start forbidden | stronger_provider |
| source_projection | Only fixed 129 bytes, SHA256 3975c5e03edb79439d6146b7714a6d3c31af86ce42f05624cdf6c28f69b4e224 | Imports exact source; also checks full byte readback and empty initial workdir | stronger_provider |
| class_projection | One JavaSandboxProbe.class, valid digest, 1..32768 bytes; tmpfs only | Same; exact entire work manifest; runtime cannot change workspace | stronger_provider |
| arbitrary_command_prohibition | No caller command/source/main/classpath | Same; no-argument verifier | equal |
| shell_prohibition | shell=False | shell=False; shell_available=False | equal |
| runtime_receipt_semantics | Signed original receipt includes discovery_complete and inventory, results and boundary outcomes | Separate signed receipt binds exact image/source/argv/class/output and evidence digest; lacks discovery witnesses | unproven |
| descriptor_authentication | Original process-local HMAC; authentic receipt and exact descriptor payload | Separate process-local HMAC; authentic descriptor/receipt binding; JSON rejected | equal |
| sandbox_owner_relationship | Original JAVA.1 public predicate only accepts original SANDBOX.1 | JAVA.1C explicitly authenticates fresh SANDBOX.2 pair and exact required policy | intentionally_different |
| complete_local_artifact_discovery | Complete inventory required before Java success; authenticated discovery_complete field | Only exact pinned image inspect and executable hashes; no complete inventory claim | unproven |
| discovery_backend_binding | Inventory backend identity AND version must equal authenticated sandbox backend | SANDBOX.2 descriptor/receipt and JAVA.1C receipt expose no corresponding discovery/backend identity/version witness | unproven |

The exact image identity is independently present in JAVA.1's frozen explicit artifact selection and JAVA.1C's signed receipt contract. Source and compile/runtime arguments are imported directly from the original fixed probe. Original successful version commands require nonempty output without a generic version range; JAVA.1C obtains those versions from freshly authenticated SANDBOX.2 gates and rehashes the same binaries before compile/run. It preserves raw version whitespace rather than the original receipt's strip operation. That representation and measurement-location difference is recorded without asserting receipt interchangeability.

The seccomp difference is intentional and satisfies the explicitly requested policy identity: clone3 remains denied but returns ENOSYS rather than EPERM. All other denied syscalls and the seven namespace-bit clone restrictions remain pinned. Neither sandbox claims thread-only legacy clone enforcement; descendants remain confined and destroyed. Arbitrary future policies are ineligible. The fixed infrastructure fixture supports neither caller Java source nor the 239-byte SYNTH.AUTH.1 source by itself; this audit grants no projection or execution authority for either.

## Authentication boundary and stopping point

`contract_compatible != live_provider_authenticated`. The pure owner imports only dataclasses, performs no I/O, accepts only the exact typed frozen metadata and rejects changed requirement tuples, aliases, unknown profiles, wrong schemas/policies, changed semantic dimensions, and report JSON. Its typed result is blocked; it exposes no satisfaction predicate or compatibility descriptor that could enable execution. Caller metadata cannot fill missing owner-defined promises.

If the gap is resolved in a separate phase, a future EXECUTOR.1R must still freshly authenticate live SANDBOX.2 and JAVA.1C descriptor/receipt pairs through their public owners and apply a separately proven compatibility relation. Saved reports and this audit cannot authenticate a live provider. Original public predicates retain their existing owner boundaries; no executor adapter is changed or connected.

## Strict recorded proof

The guarded contract replay denies process starts, threads, network effects, filesystem writes, runtime verifiers, operational executor retry and runtime/reflection lease consumption. It reads the 16 exact frozen source/evidence files listed by SHA-256 in the JSON; these reads establish only static contract provenance. Denied attempts: `{}`.

| Effect or claim | Recorded audit result |
| --- | --- |
| Docker calls / containers created | 0 / 0 |
| Java / javac executions | 0 / 0 |
| Child processes / network calls | 0 / 0 |
| Source projection | false |
| Runtime / reflection lease consumptions | 0 / 0 |
| Repository runtime writes / Apply actions | 0 / 0 |
| BANK executions / EXECUTOR.1R operational retries | 0 / 0 |
| Live provider authentication claim | false |
| Controller Thread.start attempts | 0 |

These counters describe the strict contract audit. Development artifact export occurs after the guard exits. Regression fixtures are separate validation processes; safety fixtures may exercise temporary repository writes/Apply and their exact read-only Git or Python pytest commands. Lifecycle regressions use test-only effect-denied graphs. No operational Java, Docker, BANK or EXECUTOR.1R replay was run.

## Validation and preservation

| Validation selection | Baseline | After |
| --- | --- | --- |
| SYNTH.AUTH / reflection / lifecycles / historical EXECUTOR.1R | 801 passed, 0 failed | 801 passed, 0 failed |
| Frozen JAVA.1 / 1A / 1B / 1C and SANDBOX.1 / 2 pure subset | 498 passed, 1 failed, 5 deselected | 498 passed, 1 failed, 5 deselected |
| Authority / Apply / path / patch safety | 241 passed, 1 failed | 241 passed, 1 failed |
| Registry / picker / historical reversals | 292 passed, 12 failed | 292 passed, 12 failed |
| Current EXECUTOR.1R lifecycle retry unit regression | 46 passed, 0 failed | 46 passed, 0 failed |
| New compatibility audit / mismatches / original success-gate controls | Not present | 67 passed, 0 failed |

The same **12 distinct pre-existing failure identities** remain; no new regression failure identities appeared. The known registry/reversal drift was neither projected away nor repinned. The five historical reader-thread deselections use the existing frozen pure selection and are recorded explicitly in the JSON. The lifecycle retry unit regression preserves its `PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_BLOCKED_UNRESOLVED` / `java_profile_contract_mismatch` outcome.

`benchmarks --check`: 54 checked, 0 errors, 0 agent calls, no benchmark executions. In-memory Python compilation: 1225 files, 0 failures, no bytecode emission; benchmark input fixture repositories excluded. `git diff --check` and additive-file whitespace checks pass. The existing google.genai Python 3.17 deprecation warning remains. The full suite was not run.

All **1818 pre-existing nonignored tracked/untracked files** are byte-identical, and eight already-missing paths remain missing. Historical manifests for SYNTH.AUTH.LIFECYCLE.1, SYNTH.REFLECT.LIFECYCLE.1 and the current EXECUTOR.1R lifecycle retry also match every frozen hash. All Java/sandbox/synthetic owners, original executor and historical retries, registry snapshots, reversal receipts and unrelated working-tree edits are preserved. No stash/reset/clean was used. Only the new audit owner, replay, tests and three report/evidence artifacts were added.

Exact distinct baseline/after failures:

- `tests/test_human_authority_branch_checkpoint.py::test_real_registry_marks_human_close_complete_and_picker_recommends_adopt_model_1 [call]`
- `tests/test_patch_candidate_behavior_executor1.py::test_bookkeeping_reversal_preserves_exact_frozen_receipts [call]`
- `tests/test_patch_candidate_behavior_reflect1.py::test_bookkeeping_reversal_preserves_frozen_prerequisite_entry_receipts [call]`
- `tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation [call]`
- `tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets [call]`
- `tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked [call]`
- `tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call [call]`
- `tests/test_phase_registry.py::test_seed_registry_has_expected_phases [call]`
- `tests/test_phase_registry.py::test_seed_registry_is_conservative [call]`
- `tests/test_phase_registry.py::test_seed_registry_summary_counts [call]`
- `tests/test_preflight_runtime1.py::test_bookkeeping_reversal_preserves_frozen_receipts [call]`
- `tests/test_runtime_sandbox1.py::test_maintenance_reverses_only_exact_additive_bookkeeping [call]`

Work stops at the typed semantic-gap result. No bridge, runtime repair or EXECUTOR.1R retry follows.
