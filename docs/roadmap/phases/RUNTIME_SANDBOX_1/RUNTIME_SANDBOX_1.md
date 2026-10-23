# RUNTIME.SANDBOX.1

Outcome: **RUNTIME_SANDBOX_1_COMPLETE_WITH_WARNINGS**. The configured local
Docker/Linux effect boundary passed all eleven mandatory V1 dimensions in two
independent five-probe repetitions. Both produced semantic receipt fingerprint
`53f7dcd60f46cda18adbd8037d996d7beb4e7fa7df4e6778cff69a82935426e9`.
The report is `RUNTIME_SANDBOX_1_LOCAL.json`; its exported JSON is report-only.

Sandbox capability grants no runtime, candidate, scenario, repository-write or
Apply authority. EXECUTOR.1 remains active/blocked, with its existing descriptor
and historical blocked receipts unchanged. This phase stops at verified effect
containment. It neither integrates Java nor resumes behavioral executor work.

The selected backend is Docker Desktop 4.82.0 (233772), Linux engine 29.6.1 on
Windows AMD64 through the fixed local Desktop pipe. The already-present probe
image is `sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de`.
All workloads use that immutable ID with pull=never. No image, package or
dependency was downloaded, installed or built, and no service was started.
The default coding sandbox could not access the pipe; approved local tool
escalation enabled discovery and verification. Those backend checks were
approved. A later optional elevated test-process query timed out in approval
review; normal verified process controls stopped only this task's overbroad
regression run safely. Ordinary lookup remains optional and fail-closed when
inaccessible.

## Scope and threat model

V1 treats the synthetic workload as hostile: it attempts external file reads
and writes, network/socket creation including loopback, DNS and Unix sockets,
environment inspection, extra-process spawning, indefinite execution and
stdout/stderr flooding. Only the embedded phase-owned Python fixture runs.
Its supplied input bytes, executable identity, argument tuple and environment
are closed. The adapter accepts no repository root or caller backend flags.
Its public surface is an authenticated proof handle with no consumer execution
method; the verifier's private backend invocation consumes the closed spec.

The host OS, local Docker daemon/CLI, image bytes, verifier interpreter and
process-local signing state are trusted infrastructure. Kernel/hypervisor/
container zero-days, compromised infrastructure, side channels, comprehensive
denial-of-service resistance and Java execution correctness are outside this
measured claim. This is a defined effect-contract measurement, not universal
sandbox-escape protection. Linux native availability is a separate backend
path; this receipt verifies the Windows-host Docker/WSL2 installation only.

The image contains the Python probe runtime and has no verified Java toolchain.
Exact projection means the fixed probe source and exact synthetic input bytes
match their hashes, with no arbitrary classpath/executable/argument surface.
It is not evidence that Java source projection, javac or a JVM invocation works.
That integration remains owned by a future executor refresh.

## Enforcement and evidence

Every probe gets a fresh container with read-only root, writable /work and /tmp
tmpfs areas, UID/GID 65534, all capabilities dropped, no-new-privileges, private
PID/mount/network/IPC/cgroup boundaries, no host mounts and log-driver=none.
Before start, actual Docker inspect data must match the fixed command, image,
environment, tmpfs options and exact seccomp policy; unsafe settings reject.

The network namespace is disabled and the fixed seccomp policy denies socket,
socketpair and network I/O syscalls, io_uring and namespace creation/joining.
The hostile fixture measured EPERM-style socket denial for IPv4, IPv6, DNS UDP
and Unix sockets, and denied local connect/socketpair operations. Phase-owned
host loopback TCP/UDP endpoints observed no traffic. No public endpoint or
external DNS lookup was used.

The host sentinel lives outside the container in a phase-owned temporary
directory. Both Docker Desktop host path aliases are probed. Reads/writes fail,
the host bytes remain unchanged, root writes fail, and /work writes succeed.
The complete observed environment equals the fixed allowlist, including fixed
HOME/HOSTNAME values; the synthetic host-only variable is absent.

Extra processes are allowed only within the same private namespaces and cgroup.
The fixture proves a live child shares those boundaries, attempts to outlive its
parent, and is removed with the container. This proves confinement and cleanup;
it does not claim all child creation is prevented. Both normal exit and forced
teardown remove the container, writable areas, and phase-owned host directory.
No probe source/output/compiled artifacts or persistent workers remain.

Two readers cap independently at 8,192 bytes while reading fixed 256-byte chunks.
Overflow is typed `sandbox_output_limit_exceeded`, never silent success. The
attached client is killed before daemon termination to release output
backpressure, without a preceding reader join. The timeout probe has a 10,000 ms
maximum and a stricter 5,000 ms supervisor cutoff that reserves stop-confirmation
time within the original maximum. Confirmed forced stops were 7,491 and 7,512 ms.
The stdout and stderr floods were confirmed stopped within their 5,000 ms bounds
at 3,683/3,888 ms and 3,819/4,018 ms respectively. Every outcome must finish inside
its own requested maximum; one late confirmation revokes timeout verification.
Teardown metadata queries continue after workload termination and are timed
separately. No allowance extends the requested execution maximum.

Early diagnostic revisions did not qualify: extra image/environment defaults,
case-sensitive cleanup-error parsing and delayed daemon kill under output
backpressure were corrected. Those exploratory reports remain ignored governance
metadata; only the final tightened two-repetition report supports this result.

## Files changed

| File | Purpose |
| --- | --- |
| core/candidate_runtime_sandbox.py | Local discovery, closed typed specs, fixed Docker adapter/verifier, immutable signed receipts/descriptors, pure compatibility and lookup. |
| core/candidate_runtime_sandbox_probe.py | Embedded hostile synthetic probe source, with no candidate/Java harness. |
| scripts/replay_runtime_sandbox1.py | Bounded local verification replay and report export. |
| tests/test_runtime_sandbox1.py | Pure authenticity, policy, negative-outcome, collector and exact-history tests. |
| docs/roadmap/RUNTIME_SANDBOX_1.md | Scope, result and requested report index. |
| docs/roadmap/RUNTIME_SANDBOX_1_LOCAL.json | Final measured descriptor/receipt and operational metadata. |
| core/phase_registry.py | RUNTIME ID namespace inside existing CONTROL track. |
| docs/roadmap/phase_registry.json | One narrow complete-with-warnings infrastructure phase. |
| tests/test_phase_registry.py | Attributed count and exact new phase assertions. |
| tests/test_phase_picker.py | Attributed history count and phase classification assertions. |
| tests/_runtime_sandbox1_maintenance.py | Exact reversal of this phase's additive bookkeeping. |
| tests/fixtures/runtime_sandbox1_reversal.json | New entry/post hashes; no old hash repinning. |
| tests/_patch_candidate_behavior_executor1_maintenance.py | Two lines unwrap this phase before its frozen historical reversal. |

Pre-existing workspace changes were preserved. Frozen runtime owners, executor
descriptors/receipts and historical reversal fixtures were not rewritten. The
implementation changes above are authorized development; diagnostic product,
candidate and source mutation counts remain zero.

## Requested report index

| Item | Result |
| --- | --- |
| 1. Files changed | Thirteen scoped files listed above; ignored governance logs separately. |
| 2. Sandbox owner | core/candidate_runtime_sandbox.py; fixture source separate. |
| 3. Supported backends | Fixed local Docker Linux engine; Windows Desktop pipe and Linux Unix socket paths. Only Windows installation verified. No generic broker or native Windows fallback. |
| 4. Selected backend | Windows-host Docker Desktop / WSL2 Linux engine. |
| 5. Identity/version | Docker Desktop 4.82.0 (233772); engine/client 29.6.1; pinned image ID above; WSL2 kernel 6.18.33.2-microsoft-standard-WSL2. |
| 6. Availability | Existing engine and exact local image available through approved local access; inaccessible ordinary invocation returns typed unavailable. |
| 7. Verification | All eleven mandatory dimensions passed twice; verified=true. |
| 8. Threat model | Hostile file/network/environment/process/time/output effects; trusted infrastructure and explicit exclusions above. |
| 9. Ephemeral workspace | /work 32 MiB tmpfs per fresh container; /tmp 16 MiB tmpfs; removed at teardown. |
| 10. Host-repository exposure | No host/repository mount; no repository bytes projected. |
| 11. Workspace write | Positive write and exact projection hash/readback measured. |
| 12. External filesystem | Sentinel reads/writes and root write denied; host sentinel unchanged. |
| 13. Network | OS seccomp denial measured for IPv4/IPv6/DNS UDP/Unix socket, socketpair and local connect; host endpoints quiet. |
| 14. Environment | Exact closed observed environment; host synthetic secret absent. |
| 15. Extra-process policy | Constrained descendants in same private namespaces/cgroup; creation is not categorically denied. |
| 16. Descendant cleanup | Live child boundary measured; parent-exit and timeout teardown leave container absent. |
| 17. Timeout | 10 s maximum, 5 s early cutoff, confirmed stop ~7.5 s; every probe also must meet its own maximum. |
| 18. Stdout | Independent 8,192 byte hard capture; flood typed overflow; stopped <5 s. |
| 19. Stderr | Independent 8,192 byte hard capture; flood typed overflow; stopped <5 s. |
| 20. Artifact cleanup | All five containers and writable areas removed; host temp/profile/sentinel directory removed; governance metadata only retained. |
| 21. Shell surface | None for consumer; subprocess shell=false; fixed embedded runtime arguments only. A shell binary inside the image does not grant a caller shell surface. |
| 22. Typed interface | Frozen executable identity, one fixed probe argv, exact typed input bytes, empty consumer environment and bounded timeout/stream limits. No arbitrary command string or backend flags. |
| 23. Privilege | Nonroot UID/GID 65534, cap-drop ALL, no-new-privileges; actual prelaunch inspect and measured UID/capability facts. |
| 24. Network/PID | Network none plus seccomp denial; host network/PID forbidden; private namespaces and cgroup verified. |
| 25. Resource bounds | Protective configured memory 128 MiB, CPU 1 and PID count 128; actual configuration checked. Resource-exhaustion/scheduling guarantees are not claimed or stress-verified. |
| 26. Dependencies/image | Existing exact local image only; immutable ID, pull never; no download/install/build/service start. |
| 27. Receipt | Frozen phase/contract/backend/image/source hashes, requested bounds, canonical measured outcomes and cleanup result; fingerprint above. |
| 28. Authenticity | Private process-local HMAC; descriptor authenticated against freshly signed local receipt; JSON omits signature and grants no authority. |
| 29. Descriptor | Immutable available/verified separated; measured enforcement dimensions; command/shell/runtime/write/Apply authority false. |
| 30. Executor compatibility | Pure authenticated check satisfies all eleven frozen dimension names. No executor wiring or Java invocation evidence. |
| 31. BANK count | 0. |
| 32. Behavioral scenario count | 0. |
| 33. Java candidate count | 0; adjacent existing REFLECT synthetic infrastructure is separate. |
| 34. Model/author calls | 0. |
| 35. Repository traversal | 0 by sandbox owner; external governance collection is separate. |
| 36. Product/source mutation | 0 diagnostic mutations; thirteen ordinary implementation/governance changes listed above. |
| 37. Write/Apply authority | 0; no consent/authorization source consumed or issued. |
| 38. Missing backend negative | Typed unavailable, no workload launch, no subprocess/cwd/temp/security-manager fallback. |
| 39. Network leak negative | Any family/local endpoint/socketpair leak removes network enforcement. Predicate tests are not live positive evidence. |
| 40. Filesystem leak negative | Host read/write/root-write failure or sentinel change removes filesystem enforcement. |
| 41. Environment leak negative | Secret presence, extra/missing keys or altered values remove environment enforcement. |
| 42. Surviving child negative | Unconfined namespaces/cgroup, missing live-child evidence or cleanup failure removes child/cleanup eligibility. |
| 43. Timeout negative | Missing forced stop or confirmation after original maximum removes hard timeout; any other outcome overrun also revokes it. |
| 44. Output negative | Oversized either stream, absent overflow status or failed teardown cannot pass bound predicate. Collector tests also measure caps directly using in-memory fake streams. |
| 45. Privileged config negative | Privileged, host-network/PID, arbitrary mounts/commands/env/tmpfs/security options reject before start. |
| 46. Forged descriptor negative | Caller dictionaries, constructors, replaced/tampered data, copied signatures and forged receipt inputs reject; exported JSON is report-only. |
| 47. Determinism | Two live receipts identical; duration, PID/namespace/temp/container IDs and signatures excluded. Fixed HOSTNAME avoids accidental temp identity. |
| 48. Performance | Two samples: median 51.015 s total, 2.291 s availability, 12.406 s aggregate setup, 18.605 s aggregate execution, 17.687 s aggregate teardown. Shared boundary probe ~7.475 s covers file/network/environment together, not three additive costs. Existing matching Docker/WSL/helper footprint snapshot ~690.5 MiB over ten processes; phase adds zero persistent processes. |
| 49. Focused tests | 150 sandbox tests and 299 registry/picker tests passed together (449, 8.29 s). Actual positive enforcement comes from the separate live replay. |
| 50. Adjacent tests | 21 scoped executor/preflight/admission/reflection checks passed (219.36 s), including four exact historical reversals and one existing synthetic reflection fixture. Exact node IDs are in JSON. The overbroad 347-case run was stopped after verified worker identification, superseded by this selection, and is not reported as passed. Authority/path run: 276 passed, 2 skipped, 3 pre-existing registry snapshot failures; all three reproduced after exact reversal of this phase. |
| 51. Registry/benchmarks | Registry/picker and frozen reversals recorded in final JSON. Benchmarks --check: 54 cases, 0 errors; compileall and git diff --check passed (existing line-ending warnings only). |
| 52. First remaining blocker | Future executor refresh and exact Java runtime/source/classpath integration, outside this phase. Real BANK still requires diagnostic_execution_authority_missing; console remains separate. |

## Explicit answers

| Question | Answer |
| --- | --- |
| Verified local backend capable of containing candidate Java? | A verified local V1 OS effect-containment boundary exists. Candidate Java and a Java toolchain/invocation path were not executed, integrated or verified. The Python probe image alone is not a Java executor. |
| Host filesystem technically blocked? | Yes: namespace isolation/read-only root, denied sentinel effects, unchanged host bytes; positive workspace writes succeed. |
| Network technically blocked? | Yes: measured kernel syscall denial, including namespace-local sockets and DNS UDP; no host endpoint traffic. |
| Environment inheritance bounded? | Yes: complete measured allowlist equality, fixed image defaults and Docker-injected values, host secret absent. |
| Descendants contained and cleaned? | Yes: same private namespaces/cgroup; cleanup after parent exit and forced termination. |
| Timeout/output limits hard-enforced? | Yes for the measured fixed V1 probes: confirmed stop within original maxima; both captures hard-capped independently. A failed or late confirmation revokes eligibility. |
| Arbitrary shell commands accepted? | No. |
| Any BANK candidate executed? | No, 0. |
| Availability grants runtime policy authority? | No. |
| Availability grants write/Apply authority? | No. |
| Descriptor satisfies every mandatory EXECUTOR.1 boundary? | Yes, the pure authenticated dimension check passes. EXECUTOR.1 remains frozen/blocked; no automatic integration or Java execution authority follows. |

Warnings are material: verification takes about 51 seconds per five-probe run,
the pre-existing Docker/WSL footprint is substantial, only two timing samples
were taken under local load, the image provides Python only, optional resource
exhaustion limits were not stress-tested, and three unrelated authority-test
registry snapshots already fail on the pre-phase registry. No frozen artifacts
were repinned to conceal those failures.
