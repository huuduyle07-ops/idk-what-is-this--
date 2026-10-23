# RUNTIME.JAVA.1 — resumed verification, 2026-10-07 KST

**Outcome: RUNTIME_JAVA_1_BLOCKED_SANDBOX_INCOMPATIBLE.** The exact local Java artifact and both executable hashes are present and matched. The unchanged verifier failed during its first javac-version bounded-output capture with `RuntimeError: can't start new thread`. No completed version result, compilation or JVM fixture execution was obtained.

Frozen sandbox authentication and the selected image's five boundary probes passed. The sandbox policy was not weakened. No source/test/verifier changes were retained, no acquisition occurred, no runtime authority was consumed, and EXECUTOR.1 remains ACTIVE/BLOCKED. Temporary edits made before the no-mutation clarification were restored before live execution.

The generic signed reason is `sandbox_java_incompatible:sandbox_completed`; the actual bounded controller traceback below identifies the measured failure. No specific syscall diagnosis is claimed. The previous no-artifact report is preserved inside the new JSON as historical evidence and no longer describes current availability.

## Metadata updated

| File | Purpose |
| --- | --- |
| docs/roadmap/RUNTIME_JAVA_1_LOCAL.json | Fresh blocked descriptor/receipt, exact artifact/hash evidence, diagnostics, teardown and preserved prior report. |
| docs/roadmap/RUNTIME_JAVA_1.md | Updated55-item report. |
| docs/roadmap/phase_registry.json | Current Java-only blocked reason; prior rows unchanged. |
| tests/fixtures/runtime_java1_reversal.json | Java-only additive registry post hash; historical entry hash unchanged. |

## Bounded measured diagnostic

```text
Traceback (most recent call last):
  File "<string>", line 90, in <module>
  File "<string>", line 73, in execute
  File "<string>", line 41, in run
  File "/usr/local/lib/python3.12/threading.py", line 994, in start
    _start_new_thread(self._bootstrap, ())
RuntimeError: can't start new thread
```

The unchanged controller traceback points to `run('javac_identity', [request['javac_path'], '-version'], 1024)`. No alternative version invocation, capture method, profile, resource limit or repair was attempted after this failure. Final launch-count fields remain unknown/null rather than falsely zero.

## Requested report index

| Item | Result |
| --- | --- |
| 1. Files changed | Resumed run changes only four Java-owned metadata files: this report, RUNTIME_JAVA_1_LOCAL.json, the Java registry row, and its additive reversal post hash. Verifier/test/program source has no retained changes. Initial implementation file list remains in prior phase history. |
| 2. Java runtime capability owner | core/sandboxed_java_toolchain.py; separate fixed probe and local discovery owners. |
| 3. Discovery sources | The unchanged frozen sandbox was authenticated first. Local immutable metadata and stopped-container file exports verified the specified image, paths and both hashes; it was the sole eligible toolchain in the measured local inventory. No remote source, fallback or acquisition. |
| 4. Local Java artifact availability | The specified local Java artifact is now present. available=true, verified=false; safe successful Java execution is unproven. |
| 5. Artifact/image identity | sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a; already-present logical image size 188948499 bytes (about180.2MiB). No image was added by this run. |
| 6. Platform/architecture compatibility | Selected image and exact ELF executables are Linux/amd64. JDK root /opt/temurin-26.0.2.1; user-supplied Temurin26.0.2.1+1 provenance is distinct from an observed version result. |
| 7. Sandbox descriptor binding | 4b36a9f12aa4411bc41f869f437d66a470b5eb36403b90147091d2555859bf9c; fresh process-local authenticated binding equals the frozen historical identity. |
| 8. Sandbox verification binding | 53f7dcd60f46cda18adbd8037d996d7beb4e7fa7df4e6778cff69a82935426e9; frozen verifier remeasured all eleven requirements in memory; historical report untouched. |
| 9. Nonroot policy | Nonroot65534:65534, ALL capabilities dropped, no-new-privileges; frozen resource, mount and namespace policy unchanged. Image-specific frozen probes passed. |
| 10. Seccomp compatibility | Fixed frozen seccomp retained exactly. Measured failure is controller RuntimeError: cannot start new thread; a specific denied syscall or JVM failure cause was not diagnosed. No weakening or alternate profile. |
| 11. Environment policy | Image-specific complete environment equality and host-secret absence passed. Java prelaunch configuration uses the same closed environment without new defaults or inherited variables. |
| 12. Source projection | The unchanged controller places only fixed JavaSandboxProbe source in /work before javac identity. It failed before final protocol facts were emitted; no positive Java source-projection capability receipt exists. |
| 13. Source hash verification | Exact planned source SHA-256 3975c5e03edb79439d6146b7714a6d3c31af86ce42f05624cdf6c28f69b4e224. The fixed controller checks binary/source readback before reaching the traced version stage; final readback facts were not emitted and cannot grant verified capability. |
| 14. javac executable identity | /opt/temurin-26.0.2.1/bin/javac@sha256:e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023; exact expected image binary hash matched before the Java route. |
| 15. javac version | No completed javac version result. Failure occurred inside the bounded-output controller for /opt/temurin-26.0.2.1/bin/javac -version. |
| 16. Compile result | Compilation not reached. The first version call failed in the existing controller; no repair or retry occurred. |
| 17. Class output | Empty class manifest; no javac compilation was reached. All writable workspace/container resources were removed. |
| 18. java executable identity | /opt/temurin-26.0.2.1/bin/java@sha256:a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2; exact expected image binary hash matched before the Java route. |
| 19. Runtime version | No completed java -version result. The earlier javac identity stage stopped the fixed sequence. |
| 20. Runtime result | JVM fixture launch not reached. Receipt toolchain/synthetic launch counts remain null because final controller facts were not emitted; do not interpret missing facts as zero launches. |
| 21. Expected output | JAVA_SANDBOX_OK remains the exact required infrastructure output; it was not observed. |
| 22. Timeout | Unchanged frozen10000ms hard maximum/5000ms early cutoff and daemon stop path. This attempt ended with controller error; baseline and image-specific forced-timeout probes passed. |
| 23. Stdout/stderr bounds | Frozen independent8192-byte outer caps remain; first version stage has1024-byte per-stream caps. The nested reader could not start a thread, so it cannot claim successful bounded Java output capture; the outer capture retained the bounded controller traceback. |
| 24. Descendant containment | Image-specific frozen Python descendant/private namespace/cgroup checks passed. No completed Java descendant facts were emitted. Actual container destruction removed the entire process boundary. |
| 25. Cleanup | cleanup_result=all_phase_resources_removed. Final fixed-pipe query found zero runtime-java1/runtime-sandbox1 containers; no persistent source/class runtime artifacts. |
| 26. Network behavior | Local control pipe and frozen phase-owned loopback sentinel tests only; no public network/DNS. Workload network none plus identical syscall denial; no artifact acquisition. |
| 27. Filesystem behavior | No repository/host bind mounts, readonly root, /work32MiB and /tmp16MiB tmpfs. pgvector image declared volume rejects before start. Tar inspection never extracts files to host. |
| 28. Host fallback behavior | No host java.exe/javac.exe or plain candidate subprocess fallback. |
| 29. Dependency/download behavior | Zero download, image pull, image build, installation, Maven/Gradle/SDK/package acquisition or new service. |
| 30. Verification receipt | 6d9121d1f3e84b4ed47c704bbf674d70322b4035c9afaa3ff39e7c38f52ffab3; fresh authenticated blocked receipt from the unchanged owner. Bounded controller diagnostics are retained separately in operational_diagnostics. |
| 31. Authenticity | Private process-local HMAC signs local verifier output; typed descriptor validated against exact receipt. JSON omits signatures and is report-only; no rehydration authority. |
| 32. Descriptor | 5f738cee049f10972bf25800f027ddb5360bb98ae47931c3b0598d8556c74da5; available=true, verified=false, sandbox/source/class-output support=false; runtime/write/Apply authority=false. |
| 33. Executor compatibility | Pure compatibility=false. EXECUTOR.1 remains ACTIVE/BLOCKED; no integration or runtime authorization. |
| 34. BANK execution count | 0. |
| 35. Behavioral scenario count | 0. |
| 36. Reflection count | 0 candidate reflection reads; no reflection adapter execution. |
| 37. Console count | 0 console/PTY; no console surface implemented. |
| 38. Model/author calls | 0 / 0. |
| 39. Traversal | 0 host repository traversals by Java owner; no repository root accepted or repository classpath. Governance/test reads are separate. |
| 40. Source mutation | 0 diagnostic product-source mutations; only authorized phase implementation/governance files changed. |
| 41. Write/Apply authority | runtime_authority=false, repository_write_authority=false, apply_authority=false; PREFLIGHT.RUNTIME authorizations consumed=0. |
| 42. Missing-artifact negative | Historical no-artifact result is retained under previous_phase_report. Current measured blocker is controller execution under the frozen boundary, not absent Java. |
| 43. Wrong-platform negative | Pure metadata/ELF/Windows PE rejection tests pass; unsuitable platform never launches. |
| 44. Root-required negative | Pure root-only executable permission and UID/capability/config rejection tests pass; safe nonroot image-specific probes required. |
| 45. Seccomp-incompatible negative | Live exact-boundary Java-route incompatibility observed: RuntimeError: cannot start new thread during first javac-version capture. Specific syscall attribution remains unmeasured; no seccomp edits. |
| 46. Compile-failure negative | Compilation was not reached; no compile diagnostics or class output exist. No automatic probe repair. |
| 47. Output-mismatch negative | Expected fixture output was not produced because execution did not reach the fixture. Existing pure mismatch tests remain unchanged. |
| 48. Cleanup negative | Pure stopped-container cleanup success/failure and runtime cleanup predicates pass; any failed removal/remaining resource fails verification. |
| 49. Forged-descriptor negative | Pure JSON/constructor/replaced signature/cross-binding/noncanonical field forgery tests pass for Java and frozen sandbox; no caller result can become capability. |
| 50. Determinism | One resumed live attempt; no positive compiler/class determinism claim and no failed-attempt repetition. Previous two identical no-artifact receipts remain historical only. |
| 51. Performance | Resumed total208.795s: prelaunch local pin inspection67.114s; unchanged Java owner99.673s (discovery51.529s, image-specific frozen boundary42.074s, Java container setup2.214s, teardown2.654s). Stage projection/javac/JVM timings0 indicate missing final measurements, not proof those stages consumed no time. Existing selected image180.2MiB; zero new images/workers/services. No resumed Docker/WSL memory snapshot; prior snapshot is historical. |
| 52. Focused tests | 272 pure tests were already run before the latest no-test-repeat instruction (122 original Java and150 frozen sandbox tests,15.31s). No further pytest, compileall, benchmarks or adjacent checks during resumed work. |
| 53. Adjacent tests | No fresh executor/preflight/authority/Apply/path suite was run during this resume. Original phase validation results remain historical. EXECUTOR.1 and all frozen owners/receipts remain unchanged. |
| 54. Registry/benchmarks | Java registry remains ACTIVE/BLOCKED with truthful current incompatibility metadata; only its own additive post hash changes. Historical rows/hashes are preserved. No new registry/picker/benchmark/check commands after the instruction to stop such checks. |
| 55. First remaining blocker | The existing Java controller cannot start its bounded-output reader thread under the exact frozen boundary. No verified Java compiler/runtime descriptor exists. Further diagnosis or any code/contract revision needs a separate explicit instruction; this run stops. |

## Explicit answers

| Question | Answer |
| --- | --- |
| Already-present suitable local toolchain/runtime? | Exact Linux/amd64 Java/javac artifact is present; its existing execution/capture route is incompatible/incomplete under the frozen boundary. |
| Anything downloaded, installed or pulled? | No; acquisition counts are zero. |
| Exact source compiled inside the same boundary? | No; compilation was not reached. |
| Resulting class executed there? | No; no class was produced or JVM fixture launched. |
| Any sandbox requirement weakened? | No; exact frozen policy retained. |
| Any behavioral runtime authority granted? | No; all runtime/write/Apply authority remains false. |
| Any BANK code executed? | No; BANK/candidate/scenario/reflection/console counts remain zero. |
| Verified Java descriptor satisfies EXECUTOR.1 Java-specific requirements? | No; verified=false and pure compatibility=false. |
