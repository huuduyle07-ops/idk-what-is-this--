# RUNTIME.JAVA.1A — controller output-reader failure isolation

2026-10-07 KST. Typed classification: **`sandbox_controller_thread_failure`**.
Final phase status: **`RUNTIME_JAVA_1A_CONTROLLER_FAILURE_UNRESOLVED`**.
The failing layer and native error are isolated; recovery is unresolved under
the frozen policy. The allowed phase-status vocabulary has no separate
container-controller permission-denial outcome. This status does not claim
host exhaustion, a PID-budget failure, Java capability, or phase completion.

The first stdout-reader thread cannot start inside the sandbox's Python
controller. Three non-Java repetitions reproduce the same failure with one
controller thread, only 2/128 cgroup PID slots in use, no PID-limit events, and
no memory-limit or OOM events. A direct native `pthread_create` probe returns
`1` (`EPERM`), and a non-creating `clone3(NULL, 0)` probe returns `-1` with
`errno=1`. These are measured errors, independent of Java.

The frozen seccomp profile explicitly returns `EPERM` for `clone3`. The image
reports glibc 2.41. Glibc's published implementation falls back from `clone3`
only for `ENOSYS`, not `EPERM`. The inferred mechanism is that this denial
prevents glibc from creating the controller reader thread. No syscall trace
of the historical `pthread_create` invocation was obtained; the native probes,
policy bytes, and upstream implementation support this mechanism. This does
not establish any JVM/seccomp incompatibility. See the upstream
[clone fallback implementation](https://sourceware.org/pipermail/glibc-cvs/2023q1/081815.html)
and [pthread creation integration](https://sourceware.org/pipermail/glibc-cvs/2021q3/073721.html).

The immutable image remains
`sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`.
The seccomp SHA-256 remains
`855462482bcdd76cd2b52d8cdd40683af1165a47c041d687bc64723acc4e1447`.
No policy, resource limit, image, environment, mount, or network setting changed.

| Required report item | Measured result and limits |
| --- | --- |
| 1. Exact failing thread owner | Python 3.12.13, `/usr/local/bin/python`, PID 1 in the selected image's private PID namespace, UID/GID 65534:65534. Host diagnostic verifier PID 30816. |
| 2. Exact thread creation site | `core/sandboxed_java_toolchain_probe.py`, embedded `JAVA_PROBE_SOURCE`, function `run()`, module line 56 / embedded `<string>` line 41: `for reader in readers: reader.start()`. The first reader in the fixed order is stdout; stderr's start is never reached. The underlying historical exception is at Python `threading.py:994`. |
| 3. Host vs container | Inside the sandbox controller container, after the child `Popen` returns. It is not the host Docker-control reader. |
| 4. Pre-failure thread count | All three repeats: OS threads=1, Python active threads=1, live reader threads=0. Six reader objects total are constructed, with no successfully started reader. |
| 5. Post-cleanup thread count | All three repeats: OS threads=1, Python active threads=1, live readers=0. Host Python active threads=1 before and after. Host OS thread count was unavailable without an additional dependency and is recorded as null. |
| 6. Leak evidence | No surviving or accumulating threads measured. Each inner attempt constructs two readers, starts zero, and joins zero; unstarted readers cannot be joined. All 92 host control-reader threads start and join successfully, with zero survivors. Successful inner reader lifecycle cannot be proven because the first start always fails. |
| 7. Container PID current/max | Immediately before each failed start: 2/128; after each cleanup: 1/128. `pids.events: max 0` throughout. After cleanup, the only visible container process is PID 1. Memory current is 13,357,056 / 13,348,864 / 13,471,744 bytes at the three starts, versus max 134,217,728. `memory.events` max/oom/oom_kill all zero. RLIMIT_NPROC and RLIMIT_AS are unlimited; stack soft limit is 8 MiB. |
| 8. Did javac actually start? | No javac launch in this slice: the controller-health gate failed. Historically, the preserved traceback and frozen source prove the requested `javac -version` call's `Popen` returned before the reader failure. Successful executable launch follows from `Popen` semantics, but its PID, completion, and Java initialization were not measured. |
| 9. Did javac produce bytes? | Current slice: zero javac bytes, because javac was not invoked. Historical output production is unknown; no reader captured its bytes. The historical traceback is controller stderr, not javac output. |
| 10. Was JVM reached? | No JVM fixture was reached historically or in this slice. Whether the JVM inside the historical javac process initialized before teardown is unknown. No Java compilation or class output was reached. |
| 11. Seccomp causality | Controller native permission denial is measured; frozen `clone3` denial and glibc fallback behavior support the mechanism above. JVM/seccomp causality is not proven. |
| 12. Cleanup result | Every diagnostic child is killed if needed and waited; zero live children and zero open child stdout/stderr streams after each attempt. No surviving readers. `/work` is empty; no Java source/classes were projected. Container removal and subsequent absence are checked. Temporary host profile workspace is absent. The report itself is retained as diagnostic evidence. |
| 13. Phase containers after teardown | 0, from a bounded local Docker name-filter query covering `runtime-java1` (including JAVA.1A/discovery) and `runtime-sandbox1`. |
| 14. Runtime authority consumed | 0. `runtime_authority=false`, `repository_write_authority=false`, `apply_authority=false`. |
| 15. BANK execution | 0. |
| 16. Behavioral execution | 0. Reflection=0; console/PTY=0. EXECUTOR.1 was not refreshed or resumed. |
| 17. Final typed status | `RUNTIME_JAVA_1A_CONTROLLER_FAILURE_UNRESOLVED`, classification `sandbox_controller_thread_failure`. Recovery requires a separately owned decision; no speculative fix was applied. |

The non-Java repeat uses the exact `boundary()` and `run()` function text
extracted from the frozen embedded Java controller. Only the already-proven
RUNTIME.SANDBOX.1 boundary fixture is used as the child, with a fixed in-memory
request. A diagnostic observer measures immediately before `Thread.start()`.
The diagnostic wrapper handles failure cleanup; the frozen functions and files
are not edited. There are no arbitrary caller commands or Java execution routes
in this diagnostic.

There is a static failure-cleanup gap in the original `run()`: reader startup
precedes its normal waits, joins, and stream closes. Tests cover failure on both
the first and second reader. The live failure occurs on the first reader, so no
reader leak is demonstrated. Container destruction provided historical cleanup;
the new diagnostic explicitly cleans its own children after every repeat. The
gap is documented without treating it as the measured cause or patching the
frozen owner.

Frozen RUNTIME.SANDBOX.1 authentication passed in a fresh process, reproducing
descriptor fingerprint
`4b36a9f12aa4411bc41f869f437d66a470b5eb36403b90147091d2555859bf9c`
and receipt fingerprint
`53f7dcd60f46cda18adbd8037d996d7beb4e7fa7df4e6778cff69a82935426e9`.
The restricted-shell precheck initially could not access the local Docker pipe;
the authorized diagnostic then ran with access to that same fixed local pipe.
That host-access restriction is separate from the measured container failure.

The historical `RUNTIME_JAVA_1_BLOCKED_SANDBOX_INCOMPATIBLE` was an umbrella
blocked outcome. Its measured cause was **controller output-reader thread start
failure**. **No JVM/seccomp incompatibility was proven.** The prior JSON, prior
Markdown, registry, reversal hashes, sandbox owner, Java owner, executor owner,
authorization owner, and historical receipts retain their exact bytes. All 14
protected files match their pre-investigation SHA-256 values, recorded in
`RUNTIME_JAVA_1A_LOCAL.json`. No historical receipt was re-signed or repinned.

Only separate JAVA.1A diagnostic modules, replay, focused tests, and reports were
added. No acquisition, installation, download, pull, build, host mount, resource
increase, backend redesign, or Java retry occurred. The investigation stops at
the controller-layer failure.

Validation: **740 passed** in 86.87 seconds, including all 23 JAVA.1A tests,
the frozen sandbox authentication/lifecycle regressions, Java negative/blocked
and artifact/governance regressions, selected EXECUTOR.1 blocked-state and
PREFLIGHT.RUNTIME.1 authority/effect-denial regressions, authority/Apply/path
tests, and registry/picker tests. The existing explicit
`tests._runtime_java1_frozen_regressions` pytest plugin projects authenticated
historical registry bytes in memory for historical suites; current Java
governance tests still inspect the actual current registry. No test or receipt
was repinned. One dependency emits an existing `google.genai` deprecation
warning.

`compileall` passed for the project Python directories and entry points. The
benchmark `--check` validated all 54 cases with zero errors and no agent or
behavioral execution. `git diff --check` passed; all six new diagnostic files
also pass a whitespace check. All 14 protected file hashes were rechecked after
validation and remain identical.

An initial combined regression command was stopped without an observed failure
to omit extensive unrelated executor scope-forgery variants. The narrower
required command completed successfully with the results above. The container
diagnostic itself ran once, with three non-Java repetitions in the same process;
no live diagnostic or Java retry was made during validation.
