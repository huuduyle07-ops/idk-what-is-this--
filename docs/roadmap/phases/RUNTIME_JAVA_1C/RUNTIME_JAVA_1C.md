# RUNTIME.JAVA.1C — positive Java compile/run continuation

2026-10-07 KST. **`RUNTIME_JAVA_1_COMPLETE_WITH_WARNINGS`**.

The exact frozen 129-byte JavaSandboxProbe compiled and ran successfully on live-authenticated `runtime_sandbox_2_v1`. The resulting 439-byte class produced exactly `JAVA_SANDBOX_OK`. Cleanup passed. This completes the requested Java infrastructure proof and stops before EXECUTOR.1.

[Full measured JSON evidence](../../RUNTIME_JAVA_1C_LOCAL.json) contains source/class manifests, stage PIDs and captures, namespace/cgroup observations, live SANDBOX.2 evidence, process-local authentication results, historical file hashes and validation results.

| Required report item | Measured result |
| --- | --- |
| 1. Live SANDBOX.2 authentication | PASS: live issuing owner reran all eleven gates; its process-local receipt and descriptor signatures were validated. Fresh descriptor `e8aa3dbccada7d8b92163a47444861ee78715fc204c4f340a393303b43701215`; receipt `e7746e2b0195abc4c981c590792a5a5cac4f25a52422d1528d91a2f288a80012`. Classification `eligible_for_JAVA_1_continuation_only`. |
| 2. Java image identity | `sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`; exact local image ID inspected, Linux/amd64, no declared volumes, pull=never. |
| 3. Source hash | `3975c5e03edb79439d6146b7714a6d3c31af86ce42f05624cdf6c28f69b4e224`; 129 bytes, exactly the frozen JAVA.1 value. |
| 4. Projection/readback | PASS: only `/work/JavaSandboxProbe.java` projected; exclusive create, full readback, exact byte comparison and SHA-256 verified before compile. Initial `/work` was empty. |
| 5. javac identity/version | `/opt/temurin-26.0.2.1/bin/javac`; SHA-256 `e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023` verified in this controller before launch. Authenticated live version stdout: `javac 26.0.2.1\n`; version stderr empty. |
| 6. Compile argv | Exact frozen argv reproduced below; `shell=false`, fixed environment, no caller flags or repository classpath. |
| 7. Compile PID | 7 (inside the private phase container). |
| 8. Compile exit code | 0 |
| 9. Compile stdout/stderr | Both exactly empty; zero bytes each. |
| 10. Class output path | `/work/classes/JavaSandboxProbe.class`; class bytes stayed in ephemeral tmpfs and were never extracted. |
| 11. Class SHA-256/size | `4f208c5185c89288900305283884ac0e4d71fd7088488d8a57ee50673393bd0e`; 439 bytes. |
| 12. Unexpected output files | `[]`. Exact work manifest: source file, `classes` directory, one regular `JavaSandboxProbe.class`. Verified before runtime; the complete manifest remained identical afterward. |
| 13. java identity/version | `/opt/temurin-26.0.2.1/bin/java`; SHA-256 `a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2` verified before launch. Exact authenticated live version output is reproduced below. |
| 14. Runtime argv | Exact frozen argv reproduced below; `shell=false`, only `/work/classes` and the frozen `JavaSandboxProbe` main class. |
| 15. Runtime PID | 20 (same private phase container as the compiler). |
| 16. Runtime exit code | 0 |
| 17. Runtime stdout | Exactly `JAVA_SANDBOX_OK`: 15 bytes, no newline, no trimming or normalization. |
| 18. Runtime stderr | Exactly empty: zero bytes. |
| 19. JVM thread compatibility | PASS for this fixed fixture. The authenticated native pthread gate and both Java version gates passed; compile and runtime completed on SANDBOX.2. Controller Python and OS threads stayed 1 → 1 with zero Thread.start attempts. No JVM syscall trace was collected. |
| 20. Timeout/output bounds | PASS: unchanged 10000 ms outer hard bound, 5000 ms abort cutoff and five-second controller deadline. Compiler caps 2048 bytes per stream; runtime caps 1024; outer caps 8192. No stage timed out or overflowed; termination was within deadline. Outer facts: 5069 bytes; separate bounded progress diagnostics: 284 bytes. |
| 21. Cleanup | PASS: compiler/runtime waited and reaped, process groups removed, both EOFs observed, pipes and selectors closed without errors; only PID 1 remained before container teardown. Container removal/absence destroyed `/work` source/class outputs and `/tmp` contents. Host profile workspace contained only `seccomp.json` and was removed. No Java bytes were extracted to host; workspace Java artifact inventory gained zero files. |
| 22. Remaining phase containers | 0 |
| 23. Runtime authority consumed | 0; no PREFLIGHT.RUNTIME authorization consumed. All seven authority fields remain false. |
| 24. BANK executions | 0 |
| 25. Behavioral executions | 0; reflection, console/PTY, executor runs, model calls and author calls also remain zero. |
| 26. Pure executor compatibility | `true`, computed with the new additive `java_toolchain_satisfies_executor_runtime(descriptor, receipt, sandbox_descriptor, sandbox_receipt)` facade in the issuing process. This pure predicate performs no effects and connects no executor adapter. EXECUTOR.1 was not wired, refreshed, resumed or executed. |
| 27. Final typed status | `RUNTIME_JAVA_1_COMPLETE_WITH_WARNINGS` |

Exact compile argv, passed as an argument array with `shell=false`:

```json
[
  "/opt/temurin-26.0.2.1/bin/javac",
  "-J-Xms8m",
  "-J-Xmx32m",
  "-J-XX:ActiveProcessorCount=1",
  "-J-XX:-UsePerfData",
  "-d",
  "/work/classes",
  "/work/JavaSandboxProbe.java"
]
```

Exact runtime argv, passed as an argument array with `shell=false`:

```json
[
  "/opt/temurin-26.0.2.1/bin/java",
  "-Xms8m",
  "-Xmx32m",
  "-XX:ActiveProcessorCount=1",
  "-XX:-UsePerfData",
  "-cp",
  "/work/classes",
  "JavaSandboxProbe"
]
```

The versions were measured by the mandatory live SANDBOX.2 ladder in separate containers. Its authenticated receipt binds those stage bytes and exact image. JAVA.1C rehashed both exact binaries and used its unchanged controller window for compilation and execution, avoiding duplicate version launches. The frozen Java source and compile/runtime arguments were unchanged.

Exact java-version stderr from that live ladder (version stdout was empty):

```text
openjdk version "26.0.2.1" 2026-08-18
OpenJDK Runtime Environment Temurin-26.0.2.1+1 (build 26.0.2.1+1)
OpenJDK 64-Bit Server VM Temurin-26.0.2.1+1 (build 26.0.2.1+1, mixed mode, sharing)
```

SANDBOX.2 seccomp SHA-256 remained `5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75`. Inspection verified network none, no host mounts, readonly root, only the frozen `/work` and `/tmp` tmpfs mounts, UID/GID 65534:65534, CapDrop ALL, no-new-privileges, private namespaces, PID limit 128, memory 134217728 bytes and CPU quota one. Runtime observations rechecked privileges, environment, writable/read-only mounts, resource limits, all seven namespace identities and cgroup identity. Compiler and runtime shared the controller boundary; controller resource state remained stable.

The new Java descriptor fingerprint is `2250667c59a57f33125e5a5cbeae05dc92b4c0d012e7b967298f8307f2be63f0`, and its receipt fingerprint is `fe149c271d2856728cc862355f34393a29f11a4dd070be443342e80a7d3a716c`. Receipt evidence SHA-256 is `08ef8f9923b17892b527cfe898bf8af2fd633cc6c9c06006e5d37224dab8dd42`. The signed receipt binds the fresh SANDBOX.2 descriptor/receipt, exact policy and image, compiler/runtime paths, versions and hashes, frozen invocations, source/class hashes, expected byte output and cleanup. Descriptor flags `available`, `verified`, `sandbox_compatibility`, `source_projection_supported` and `class_output_projection_supported` are all true.

```json
{
  "runtime_authority": false,
  "repository_write_authority": false,
  "apply_authority": false,
  "shell_available": false,
  "arbitrary_command_authority": false,
  "network_authority": false,
  "host_mount_authority": false
}
```

The supplied historical SANDBOX.2 descriptor `f9cc912a4f14d9c2582b10dd0a80269f9ac78f4c582a90e4d1b0fff6ae38807e` and receipt `b9639a0caf3788a7f8d9dfe145b8b4894639721f7c43e1b08a0b9da4cca523d0` remain preserved context. Its frozen report explicitly defines fingerprints as run-specific evidence snapshots, including measured IDs. JAVA.1C therefore authenticates and binds the fresh live pair rather than importing that historical JSON as capability. The Java receipt was authenticated in its issuing process. Exported JSON omits signatures and secrets and remains report-only; loading it cannot recreate authenticated capability.

[The first attempt](RUNTIME_JAVA_1C_ATTEMPT1.json) is preserved as an inconclusive outer-timeout result. It returned no nested stage facts, so compiler/runtime launch counts and internal capture cleanup were unknown; no positive Java receipt was issued. Container and host-profile removal were verified. Its initial zero-count inference was corrected to unknown. The final controller emits bounded stage-progress diagnostics separately from child stdout/stderr. It reuses the already-authenticated live version evidence. The successful final attempt compiled once and ran the fixture once; those counts describe that verified attempt. No policy, Java source, Java flags or timeout/resource/output limits were loosened.

All **104 protected historical files** retain their initial SHA-256 bytes: SANDBOX.1/2 owners, profiles, reports and receipts; JAVA.1/1A/1B sources and reports; executor and runtime-authorization owners; registry and historical reversal records. No historical fixture was repinned. The JSON records every before/after hash. Only additive JAVA.1C owner, probe, tests, replay and report artifacts were created.

Final validation passed **976 tests** in separate processes:

- SANDBOX.1/2 authentication, compatibility and frozen regressions: 225 passed.
- JAVA.1 historical blocked/positive contracts, discovery and governance: 122 passed.
- JAVA.1C focused tests plus JAVA.1A diagnostics and JAVA.1B recovery: 157 passed (89 + 68).
- Selected PREFLIGHT.RUNTIME.1 authority/effect-denial and EXECUTOR.1 blocked-state tests: 8 passed.
- Authority/Apply/path and patch safety, validation safety, registry and picker: 464 passed.
- `compileall`: passed. `benchmarks --check`: all 54 cases passed, zero errors, zero agent calls.
- `git diff --check`, new-file whitespace, protected historical hashes and recorded evidence hashes: passed.

The existing frozen-regression projection plugin was used without modifying historical fixtures. Larger combined test attempts were interrupted for runtime and are excluded from the passing counts. The final groups emitted the existing google.genai Python 3.17 deprecation warning.
