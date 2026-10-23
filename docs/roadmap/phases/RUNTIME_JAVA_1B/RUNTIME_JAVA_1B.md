# RUNTIME.JAVA.1B — single-threaded bounded capture recovery

2026-10-07 KST. **`RUNTIME_JAVA_1B_JAVA_STAGE_REACHED_WITH_MEASURED_FAILURE`**.

The new selector capture works inside the unchanged sandbox. The non-Java
boundary fixture completed successfully; the controller remained at one Python
thread and one OS thread, with zero `Thread.start()` attempts. The exact
`/opt/temurin-26.0.2.1/bin/javac -version` retry then executed as container PID 7,
and its complete bounded output was captured. It exited with code 1 during JVM
initialization, reporting `pthread_create failed (EPERM)` for the VM Periodic
Task Thread and VM Thread.

Live execution stopped at this new Java-stage blocker. No `java -version`, Java
source projection, compilation, class verification, or JVM fixture execution
followed. Controller recovery does not establish Java capability. The existing
JAVA.1 positive sequence and EXECUTOR.1 remain blocked.

| Required report item | Result |
| --- | --- |
| 1. Exact new capture implementation | `core/java_single_thread_capture.py:capture_process()` uses `selectors.DefaultSelector`, nonblocking stdout/stderr fds, and `os.read` with at most 256 bytes per operation. `core/sandboxed_java_single_thread_probe.py` embeds it in the container controller and replaces only the original `run()` body in memory. `core/sandboxed_java_capture_recovery.py` owns the fixed health gates and conditional handoff. The recovery entrypoint is `scripts/replay_runtime_java1b.py`. Historical controller files retain their exact bytes. |
| 2. No reader threads started | Capture source has no thread constructor, thread start, asyncio, `communicate()`, or background worker. The embedded controller makes Python `Thread.start()` fail if attempted and counts attempts. Both live gates measured zero attempts. Pure tests also make thread construction fail. Frozen host Docker-control readers are unchanged; this recovery replaces only capture inside the Linux container. |
| 3. Before/after Python thread count | Non-Java: 1 → 1. Javac version: 1 → 1. OS thread count also stayed 1 → 1 in each container's PID 1 controller. |
| 4. Non-Java capture | Existing RUNTIME.SANDBOX.1 boundary fixture, fixed projection bytes and argv, exit 0. Captured stdout=799 bytes, stderr=0. Projection hash, UID, exact environment, host-secret absence, and namespace/cgroup inheritance passed. No Java child was launched before this gate passed. |
| 5. Stdout/stderr caps | Independent nested caps remain 1024 bytes per stream for identities and the JVM fixture, 2048 per stream for compilation. Outer caps remain 8192 per stream. The helper stores at most the limit on each stream and reads at most one byte beyond its remaining allowance to detect overflow. Live javac output was 417 stdout bytes and 0 stderr bytes; no truncation or overflow occurred. Pure tests cover each overflow independently, exact-cap EOF, interleaving, and both EOF orders. |
| 6. Timeout | The frozen outer 10000 ms hard bound and 5000 ms early daemon cutoff remain unchanged. The new controller adds a shared five-second monotonic deadline and polls at most 10 ms at a time. It does not extend the outer deadline. Pure timeout tests cover a running child after pipe EOF and an exited child whose inherited pipe stays open. No live gate timed out. |
| 7. Cleanup | Each child starts a new session/process group. The helper kills that group on every exit path, waits for the child, reaps adopted members of that group with bounded work, unregisters selector fds before closing pipes, and closes the selector. Failures in cleanup revoke health. Both live gates report `child_waited=true`, `pipes_closed=true`, `cleanup_verified=true`, no cleanup errors, only PID 1 remaining, and an empty `/work`. Both containers were removed and absence checked; the final phase-container count is 0. The temporary host profile workspace was removed. |
| 8. Javac process started | Yes. The exact fixed executable passed an in-container SHA-256 check before launch; `Popen` returned PID 7 and the selector captured its output to EOF. |
| 9. Javac PID | 7 in its private container PID namespace. The non-Java child was also PID 7 in a separate container. |
| 10. Javac exit code | 1. |
| 11. Javac stdout/stderr | Complete 417-byte stdout is reproduced below. Stderr was empty, zero bytes. Both streams reached EOF. |
| 12. JVM initialization observed | Yes, an initialization attempt is directly observed in the JVM's native warning/error output. Initialization failed; no successful compiler version result or JVM fixture result was obtained. |
| 13. Seccomp causality | The new measured Java-stage failure is native thread creation returning `EPERM`. Frozen `clone3 → EPERM`, JAVA.1A's native pthread/clone3 probes, and glibc's fallback behavior support a policy interaction. This slice did not obtain a syscall trace of the JVM's pthread call, so the exact syscall cause remains an inference. The JVM's generic “Out of system resources” wording is not evidence of PID or memory exhaustion. No sandbox policy or resource limit changed. |
| 14. Java compile/runtime counts | One javac-version process; compilation=0; `java -version`=0; JVM fixture=0. The conditional JAVA.1 continuation was not entered. |
| 15. BANK count | 0. |
| 16. Behavioral count | 0. Reflection=0; console/PTY=0. |
| 17. Runtime authority consumed | 0. `runtime_authority=false`, `repository_write_authority=false`, `apply_authority=false`. EXECUTOR.1 was not resumed or refreshed. |
| 18. Final typed status | `RUNTIME_JAVA_1B_JAVA_STAGE_REACHED_WITH_MEASURED_FAILURE`. This is separate from the historical controller failure and does not complete RUNTIME.JAVA.1. |

Exact captured javac stdout:

```text
[0.065s][warning][os,thread] Failed to start thread "VM Periodic Task Thread" - pthread_create failed (EPERM) for attributes: stacksize: 1024k, guardsize: 4k, detached.
[0.069s][warning][os,thread] Failed to start thread "VM Thread" - pthread_create failed (EPERM) for attributes: stacksize: 1024k, guardsize: 4k, detached.
Error occurred during initialization of VM
Cannot create VM thread. Out of system resources.
```

The selector follows Python's documented
[registration, readiness, EOF and close lifecycle](https://docs.python.org/3/library/selectors.html).
The policy-interaction inference uses the previously reviewed upstream
[glibc clone fallback implementation](https://sourceware.org/pipermail/glibc-cvs/2023q1/081815.html).
Neither source replaces the measured process output above.

The exact immutable image remains
`sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`.
Fresh frozen sandbox authentication reproduced descriptor
`4b36a9f12aa4411bc41f869f437d66a470b5eb36403b90147091d2555859bf9c`
and receipt
`53f7dcd60f46cda18adbd8037d996d7beb4e7fa7df4e6778cff69a82935426e9`.
Seccomp SHA-256 remains
`855462482bcdd76cd2b52d8cdd40683af1165a47c041d687bc64723acc4e1447`.
PID limit 128, memory 128 MiB, UID/GID 65534:65534, readonly root, network none,
ALL capability drop, no-new-privileges, namespaces, tmpfs limits, and environment
are unchanged and independently checked before each gate starts.

The original `execute()` text and its Java flags, source, class manifest,
expected output, validation rules, and authority semantics remain unchanged.
The optional positive handoff binds the new controller only in memory, restores
the original bindings afterwards, and refuses a different image before launch.
Capture observations and PIDs stay outside semantic receipt facts in that
prepared positive path; cleanup failures fail closed even on its final stage.
Pure tests verify these contracts. The handoff was not executed live because
the javac gate failed.

All 40 protected historical files are checked against their pre-slice hashes,
including frozen sandbox owners, historical JAVA.1/JAVA.1A code and reports,
registry, reversal records, authorization owner, and executor owner. No
historical bytes, receipt signature, or pinned hash was rewritten. Only separate
JAVA.1B implementation, tests, entrypoint, and reports were added. No image
acquisition, installation, download, pull, build, resource increase, host mount,
backend redesign, or second Java attempt occurred.

Validation passed: 45 focused JAVA.1B tests and 23 JAVA.1A diagnostic tests;
the final required adjacent run passed all 785 tests in 193.32 seconds. That run
included sandbox authentication/lifecycle, JAVA.1 blocked and positive contracts,
selected EXECUTOR.1 blocked-state checks, PREFLIGHT.RUNTIME.1 denial checks,
authority/Apply/path safety, and registry/picker regressions. Frozen regression
projections used the existing `tests._runtime_java1_frozen_regressions` plugin;
historical source and test files were not edited. The new test fixture restores
its mocked process hooks before the effect guard exits, and the final combined
run confirms adjacent tests retain their original process hooks.

`compileall` passed. `benchmarks --check` passed 54 cases with zero errors and
zero agent calls. `git diff --check` and whitespace checks of all seven new
JAVA.1B files passed. The test run emitted one existing `google.genai` Python
3.17 deprecation warning. All 40 historical file hashes still match. The raw
local report records every before/after hash and the complete live observations.
