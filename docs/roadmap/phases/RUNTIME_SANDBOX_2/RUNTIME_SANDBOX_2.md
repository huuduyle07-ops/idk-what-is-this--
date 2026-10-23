# RUNTIME.SANDBOX.2 — thread-compatible seccomp epoch

2026-10-07 KST. **`RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS`**.

The additive `runtime_sandbox_2_v1` profile passed the complete verification
ladder on the existing immutable Temurin image. Its only semantic policy change
is `clone3` returning `ENOSYS` (38) instead of `EPERM` (1). `clone3` execution
remains denied. Native pthread creation succeeded, including a second bounded
test restricted to the expected legacy clone flags. All original sandbox
boundary probes and the JAVA.1B single-threaded controller gate passed.
Both exact Java version commands exited 0. No Java source was projected or
compiled, and no JVM fixture, BANK, behavior, reflection, console, or executor
was run. This phase establishes eligibility for a later JAVA.1 continuation.
It does not complete JAVA.1 or replace the historical SANDBOX.1 adapter.

| Required report item | Measured result |
| --- | --- |
| 1. Candidate identity | Profile `runtime_sandbox_2_v1`; policy SHA-256 `5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75`. Exact canonical UTF-8 policy bytes are in `RUNTIME_SANDBOX_2_SECCOMP.json`, without an added newline. New descriptor fingerprint `f9cc912a4f14d9c2582b10dd0a80269f9ac78f4c582a90e4d1b0fff6ae38807e`; verification receipt fingerprint `b9639a0caf3788a7f8d9dfe145b8b4894639721f7c43e1b08a0b9da4cca523d0`. |
| 2. Semantic diff | Only `clone3`: `SCMP_ACT_ERRNO/1` → `SCMP_ACT_ERRNO/38`. The structured diff is `policy_diff` in the local JSON. Default action, all other denied calls, and all seven clone argument filters are unchanged. No syscall became directly allowed. |
| 3. Clone3 | Fixed invalid-argument syscall 435 returned -1, errno 38 (`ENOSYS`); process count stayed 1, OS threads stayed 1, pids.current stayed 1. No process or thread was created by this probe. |
| 4. Legacy clone | The baseline and candidate both default-allow ordinary legacy clone and argument-filter seven namespace flags. Neither enforces thread-only clone. Native pthread works with the exact 64-bit clone flags `0x003d0f00`; the restrictive witness test and its negative control passed. Namespace clone flags remain denied as measured below. |
| 5. Pthread | Two sequential native pthread calls in one fixed fixture: unmodified candidate, then an additional restrictive clone filter. Both `pthread_create` and `pthread_join` returned 0. Each measured OS threads 1 → 2 → 1, pids.current 1 → 2 → 1, process count 1 throughout. Worker TIDs were 7 and 8; both shared process PID 1 and PPID 0 with the main thread. |
| 6. Namespace/cgroup | Main thread and both workers shared all seven namespace identities: user, mount, net, PID, IPC, cgroup, UTS; cgroup remained `0::/`. Direct clone, unshare, and setns probes for each of those seven namespaces all returned -1/EPERM: 21 denied operations. These probes ran before the restrictive witness filter, so their denial belongs to the candidate container boundary. |
| 7. Processes/descendants | Original descendant and timeout fixtures observed a live child in the same private namespaces and cgroup. Docker inspection independently verified private PID/cgroup settings and PID limit 128. Each container was killed/removed and absence checked. Native threads remained within the same single process. Ordinary contained child processes were already permitted by SANDBOX.1. |
| 8. Network | IPv4 TCP, IPv6 TCP, UDP/DNS, Unix socket, socketpair and local connection probes denied; host TCP/UDP endpoints stayed quiet. Both native worker socket attempts returned EPERM. Network mode remained none; no network authority exists. |
| 9. Filesystem | Host sentinel read/write attempts denied and sentinel bytes unchanged; root write denied. Exact 45-byte projection and writable `/work` passed. Separate fixed tests wrote and removed files in `/work` and `/tmp`. Root remained readonly, with the original tmpfs sizes/flags and no host mounts. |
| 10. Environment | Exact eight-entry frozen environment allowlist reproduced; host-only secret absent. No Java-specific environment variables were added. |
| 11. Privileges | UID/GID 65534:65534; CapDrop ALL, no added capabilities, effective capabilities zero and no-new-privileges true, including both native threads. No privileged container. |
| 12. Timeout/output | Original timeout probe aborted at the existing 5000 ms supervisor cutoff; daemon termination was confirmed at 6881.787 ms, within its unchanged 10000 ms hard bound. Other original probes retained their 5000 ms bounds. Independent hostile stdout and stderr fixtures were stopped at exactly 8192 bytes each. JAVA.1B nested identity caps stayed 1024 bytes per stream; outer Java/controller bounds stayed 8192 bytes, 10000 ms hard/5000 ms cutoff. No successful stage exceeded its deadline. |
| 13. Cleanup | Every one of the eleven phase containers was removed and absence verified. Final phase-container count=0; temporary host workspace removed. Native threads joined, returning to one task. Controller and Java children report closed pipes, waited children, verified group cleanup, no cleanup errors, only PID 1 remaining, and empty `/work`. No persistent diagnostic artifact remains beyond these requested reports. |
| 14. Javac | Exact `/opt/temurin-26.0.2.1/bin/javac -version`; container PID 7, exit 0. Stdout 15 bytes: `javac 26.0.2.1\n`. Stderr empty. Exact binary SHA-256 rechecked before launch: `e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023`. |
| 15. JVM initialization | Successful initialization is supported by successful compiler/runtime version output and exit 0. No VM initialization error occurred. This slice did not trace the JVM's actual pthread syscall. The historical JVM clone3 causality remains an inference; the new native fallback and Java version success are directly measured. |
| 16. Java version | Reached only after javac passed. Exact `/opt/temurin-26.0.2.1/bin/java -version`; PID 7 in a separate container, exit 0. Stdout empty; stderr 188 bytes, reproduced below. Binary SHA-256 `a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2` rechecked before launch. |
| 17. Runtime authority consumed | 0. All seven runtime/write/Apply/shell/arbitrary-command/host-mount/network authority fields remain false. No task runtime authorization was issued or consumed. |
| 18. BANK count | 0. |
| 19. Behavioral count | 0. Reflection=0; console/PTY=0; compilation=0; JVM fixture=0. Exactly one javac-version process and one java-version process ran. EXECUTOR.1 was not refreshed or resumed. |
| 20. Final typed status | `RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS`; compatibility classification `eligible_for_JAVA_1_continuation_only`. JAVA.1 remains historically unchanged. |

Exact java stderr (stdout was empty):

```text
openjdk version "26.0.2.1" 2026-08-18
OpenJDK Runtime Environment Temurin-26.0.2.1+1 (build 26.0.2.1+1)
OpenJDK 64-Bit Server VM Temurin-26.0.2.1+1 (build 26.0.2.1+1, mixed mode, sharing)
```

The frozen image remains
`sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`.
No image was acquired, pulled, built, replaced, or supplemented. PID budget 128,
memory 128 MiB, CPU quota 1, environment, UID/GID, security options, mount rules,
and timeout/output limits remain unchanged. Actual Docker configuration is
checked before every start, with the exact new policy verified separately and
all other settings delegated to SANDBOX.1's unchanged configuration predicate.

The native flag witness uses a second seccomp BPF filter only inside the native
fixture, after the original native call and namespace tests. It denies legacy
clone unless the full 64-bit flag word is `0x003d0f00`, and rejects non-x86_64
audit architectures. It is used only by the fixed x86_64 native fixture.
A `clone(SIGCHLD)` negative control then returned EPERM, while a second pthread
succeeded. This is a constrained execution witness for that native fixture,
not a JVM syscall trace and not the candidate's process policy. The glibc 2.41
[pthread implementation](https://raw.githubusercontent.com/bminor/glibc/glibc-2.41/nptl/pthread_create.c)
specifies VM, FS, FILES, SYSVSEM, SIGHAND, THREAD, SETTLS, PARENT_SETTID and
CHILD_CLEARTID. Its
[clone fallback implementation](https://raw.githubusercontent.com/bminor/glibc/glibc-2.41/sysdeps/unix/sysv/linux/clone-internal.c)
falls back on ENOSYS. The kernel's
[seccomp filter documentation](https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html)
explains why stacking this additional filter cannot override the outer Docker
denials. The expected flags are independently checked by the fixture's filter;
the source references alone are not the measurement.

The threat-model effect is explicit: glibc can now take a legacy fallback that
the former error prevented. That enabled the measured bounded pthread routine
and the two Java version commands. It may also make other libc fallback paths
usable; this is not a claim that pthread is the sole newly usable library API.
The seccomp set of directly allowed syscalls and clone flag predicates did not
expand. Ordinary contained processes were already allowed; this profile does
not impose thread-only clone. New namespace creation/joining, network syscalls,
mounting, ptrace, process-VM access, and the other historical denied operations
retain their exact static rules. The requested namespace and effect probes
passed. No assertion of universal security equivalence or arbitrary Java
program compatibility follows from this bounded fixture ladder.

The controller-health, javac, and java containers independently measured Python
threads 1 → 1, OS threads 1 → 1, and zero `Thread.start()` attempts. Their source
reuses JAVA.1B's exact selector capture and observer; reader threads were not
reintroduced. The java-version gate uses the same fixed identity wrapper with
the exact java path/hash. Its internal historical stage key remains
`javac_identity`; the mode, argv, binary digest, and evidence identify java
unambiguously.

`core/thread_compatible_runtime_sandbox.py` owns the new epoch, predicates,
fixed verification ladder, independent process-local HMAC key, receipt and
descriptor types. `core/thread_compatible_runtime_sandbox_probe.py` owns the
fixed native and tmpfs probes. `scripts/replay_runtime_sandbox2.py` is the only
new replay entrypoint. No arbitrary source, argv, image, profile, shell, or
environment input is accepted. New receipt authenticity was checked in its
issuing process. Exported JSON omits the signature/key and remains report-only;
it cannot authenticate a future process or satisfy the old executor adapter.
The evidence hash binds this run's stage observations, including measured IDs;
it is a snapshot fingerprint, not a promise of identical IDs on future runs.

SANDBOX.1 remains the baseline, with descriptor
`4b36a9f12aa4411bc41f869f437d66a470b5eb36403b90147091d2555859bf9c`,
receipt `53f7dcd60f46cda18adbd8037d996d7beb4e7fa7df4e6778cff69a82935426e9`,
and seccomp SHA-256
`855462482bcdd76cd2b52d8cdd40683af1165a47c041d687bc64723acc4e1447`.
Those identities are relationship fields in the new epoch; no historical
receipt was re-signed or reinterpreted. All 47 protected historical files,
including the seven JAVA.1B files, retain their pre-slice bytes. The local JSON
records their before/after hashes. Registry and all historical reports and
authorization/executor owners remain unchanged.

Validation passed: 75 focused SANDBOX.2 tests, alongside 68 JAVA.1A/JAVA.1B
focused regressions. The final required adjacent run passed **860 tests** in
213.73 seconds, covering SANDBOX.1 authentication/lifecycle, JAVA.1A diagnostics,
JAVA.1B capture recovery, JAVA.1 blocked/positive contracts, selected EXECUTOR.1
blocked states, PREFLIGHT.RUNTIME.1 effect/authority denials, authority/Apply/path
and patch safety, registry, and picker. It used the existing frozen regression
projection plugin; no historical tests or pinned hashes were edited.

`compileall` passed. `benchmarks --check` passed all 54 cases with zero errors
and zero agent calls. `git diff --check`, new-file whitespace checks, exact
canonical policy-byte validation, embedded probe-source hashes, and all 47
historical before/after hashes passed. The adjacent run emitted one existing
`google.genai` Python 3.17 deprecation warning. Live stage observations still
match the authenticated receipt's evidence hash.
