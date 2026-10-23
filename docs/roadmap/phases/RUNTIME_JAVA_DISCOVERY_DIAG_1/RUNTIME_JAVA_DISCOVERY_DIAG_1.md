# RUNTIME.JAVA.DISCOVERY.DIAG.1

2026-10-09 KST. **RUNTIME_JAVA_DISCOVERY_DIAG_1_COMPLETE_WITH_WARNINGS**.

Measured classification: **EXPORT_TRANSPORT_EXCEEDS_BOUND**. One raw-drain export received **384,237,059 bytes** without completing within the unchanged **30,000 ms** export budget. No archive semantic parsing occurred. The required raw-timeout decision boundary stopped this phase before the parser trial, a third export, or remediation. The frozen complete-export resource bound is incompatible with this artifact under these measured local conditions.

This is diagnostic evidence only. No runtime capability schema, compatibility relation, provider authority, complete inventory witness or production discovery success was created. JAVA.1D remains blocked. No JAVA.1D retry, JAVA.1C verification, COMPAT.2 or EXECUTOR.1R ran.

[Full diagnostic evidence](RUNTIME_JAVA_DISCOVERY_DIAG_1_LOCAL.json), [preservation manifest](RUNTIME_JAVA_DISCOVERY_DIAG_1_PRESERVATION.json), [diagnostic controller](../../../../scripts/measure_runtime_java_discovery_diag1.py), [pure tests](../../../../tests/test_runtime_java_discovery_diag1.py), and [unchanged original discovery owner](../../../../core/sandboxed_java_toolchain_discovery.py).

## Exact target and endpoint

| Field | Observation |
| --- | --- |
| Exact verified image ID | `sha256:09361da47d33ad0d44f89947d5e99003e94594e885328cdb5cd7b1c515a1a089` |
| Recorded repository digest | `cattus-cattus-web@sha256:09361da47d33ad0d44f89947d5e99003e94594e885328cdb5cd7b1c515a1a089` |
| Frozen local endpoint | `npipe:////./pipe/dockerDesktopLinuxEngine` |
| Docker server version | `29.6.1` |
| Platform / configured image user | linux/amd64 / appuser |
| Docker image size metadata | 139,358,132 bytes; this does not establish complete export-stream size |
| Root filesystem layers / declared volumes | 11 / none |
| Image creation metadata | `2026-07-18T13:56:06.820503358Z` |
| Frozen original export timeout | 30,000 ms; unchanged |

The frozen `_docker_prefix()` supplies the resolved local Docker binary, an absent private config directory and the explicit local endpoint. The diagnostic verified this exact immutable image through `_image_metadata()` before container creation. No image inventory or inspection of other images occurred. The target remains in the historical discovery domain, regardless of its name or whether it provides Java.

## Original implementation and reuse

The original `_container_files()` was executed unchanged for the one live trial. It creates a randomly named stopped container with `--pull never`, `--network none`, a read-only root filesystem, uid/gid 65534, dropped capabilities, the frozen seccomp profile and no-new-privileges, private cgroup/IPC isolation, fixed resource limits, disabled logs and the original temporary-filesystem options. Its fixed controller entrypoint and `raise SystemExit(64)` arguments remain inert because the container is never started. `_stopped_configuration_safe()` verifies the immutable image, stopped state, absence of host mounts and the full frozen configuration. The complete argv is retained in the JSON.

The original `_export_filesystem()` launches `docker export <stopped-name>` with stdin DEVNULL, stdout/stderr PIPE, `shell=False`, the original minimal environment and a hidden Windows child. Its 30-second deadline starts after `Popen` returns. The main thread parses buffered stdout through `_BoundedArchiveStream` and `tarfile` stream mode `r|`. A daemon deadline guard checks every 20 ms and kills the child at expiry; a second daemon reader consumes stderr in 256-byte reads, retains at most 8,192 bytes and kills on overflow. After parsing, the original code drains a bounded remainder in 65,536-byte reads, waits up to two seconds and checks exit/timeout/overflow. Finally it stops the guard, kills a living child, waits, joins both threads and closes stdout/stderr. DEVNULL supplies no parent stdin pipe.

The original limits remain 2 GiB of archive bytes, 250,000 entries and 128 MiB per executable. `_inspect_tar()` checks every normalized entry path and directory traversal permissions; resolves relative symlinks and hardlinks with root-escape, cycle and 40-link bounds; and hashes eligible java/javac/python basename candidates incrementally. It requires executable permission for uid/gid 65534 and Linux amd64 ELF64 little-endian ET_EXEC/ET_DYN headers. Java/javac resolve to a shared actual parent directory. The controller remains `/usr/local/bin/python`. Image PATH is retained as metadata: the original scanner does **not** filter candidates by PATH. No extraction or execution occurs. Function source hashes and line references are in the JSON, alongside the full unchanged owner-file hash.

For the raw control only, an in-memory wrapper replaced the export body with incremental `PeekNamedPipe`/`os.read` draining, using reads of at most 65,536 bytes and an 8,192-byte stderr retention bound. It retained counters and timings, no full archive buffer, and persisted no archive. The original stopped-container setup, configuration checks and cleanup remained in use. Windows anonymous pipes cannot use the Linux selector capture directly; this one-thread polling method is recorded explicitly. Its timeout begins after export launch, matching the original budget anchor.

The additive controller also contains an instrumented original-parser path, which delegates to the actual original exporter/scanner, retains all archive and entry rules, and counts yielded entries and read durations. It was **not run live**, because the raw timeout required stopping. Pure fixture tests verify its semantic delegation and rejection rules. No original owner source was modified.

## Trial 1: raw drain

| Measurement | Result |
| --- | --- |
| Trial order / count | raw drain first; one export total |
| Container ID | `365d119c6414863f1201d8cb93144a6d9dbe80d50572f950fc24f6e8d322c5bb` |
| Container started | false |
| Create + stopped configuration inspection | 2,171.398 ms |
| Export process launch | 771.788 ms; separate from original post-launch export budget |
| First stdout byte | 218.008 ms after budget anchor |
| Bytes received | 384,237,059 |
| Bounded stdout reads / poll iterations | 13,432 / 29,314 |
| Average measured stream rate | 12,800,866 bytes/s, approximately 12.8 MB/s |
| Raw pipe probe wall time | 3,337.419 ms |
| Raw stdout read/copy wall time | 1,142.319 ms |
| Idle polling sleeps, including scheduling | 23,870.471 ms |
| Main-thread CPU time across raw capture and launch, sampled before child cleanup | 6,343.750 ms |
| Archive entries / semantic parser time | unmeasured; parsing disabled |
| Kill requested | 30,000.689 ms after budget anchor |
| Timeout-supervisor scheduling overshoot | 0.689 ms; no timeout extension |
| Kill-to-reap time | 15.659 ms |
| Export elapsed including reaping/pipe cleanup | 30,016.489 ms |
| Entire trial including setup, launch and container removal | 35,204.578 ms |
| Exit code / timed out | 1 / true |
| Export stderr received / retained | 0 bytes / empty |
| Export `Thread.start` attempts | 0 |
| Python active threads before / after trial | 1 / 1 |
| Container removal + known-absence verification | 2,243.773 ms; successful |
| Export child reaped / stdin-stdout-stderr closed | true / true; stdin was DEVNULL |
| Temporary profile state removed / archive persisted | true / false |
| Remaining diagnostic containers | 0; final filtered container check passed |

The 30-second budget measures export transport/capture; setup, process-launch latency and post-kill cleanup are reported separately. CPU and wall measurements overlap and must not be summed as independent stages. Idle sleep time includes delayed observation of readiness and host scheduling; it is not a direct measurement of daemon inactivity.

## Classification, uncertainty and stopping point

Raw drain completed within the bound: **false**. Parser path completed within the bound: **unmeasured**. Throughput comparison and parser-specific overhead: **unavailable**. Producer blocking/backpressure was not deterministically observed.

Confidence is high that this measured complete-export path exceeded the frozen bound with semantic parsing removed. This trace does not identify Docker daemon production, Docker CLI transport, host pipe draining and host scheduling as independent causes. Capture itself has measurable CPU and probe costs. The corrected pure baseline fixture selection overlapped the operational run, so host contention is an additional limitation. The evidence does not establish that Docker alone is slow, or that capture overhead dominates.

Only the raw trial ran, so there is no faster-second-trial comparison or cache-warming claim. Complete archive size, remaining bytes and entry count are unknown. Cache/transient behavior across repeated runs remains unresolved. The mandatory raw-timeout stop takes precedence over performing the otherwise requested parser measurement; no second or third trial was justified after that boundary.

No parser optimization or timeout/domain/provider special case was implemented. A later architectural decision would need to explicitly choose between evolving the discovery contract, changing its domain, or defining a semantically equivalent provider-specific discovery proof. No option is selected here, and no later Java phase is unblocked by this diagnostic.

## Effects, threads and cleanup

| Operational effect | Successful measurement | Including failed endpoint preflight |
| --- | --- | --- |
| Exact image identity inspections | 1 | 1 |
| Container creates / starts | 1 / 0 | 1 / 0 |
| Exports: raw / parser / third | 1 / 0 / 0 | 1 / 0 / 0 |
| Docker control calls, excluding export | 7 | 8 |
| Docker calls / host Docker child processes | 8 / 8 | 9 / 9 |
| Bytes streamed | 384,237,059 | 384,237,059 |
| Archive entries processed | none; unmeasured | none; unmeasured |
| Java / javac executions / Java compilations | 0 / 0 / 0 | 0 / 0 / 0 |
| Source projections / network / shell / host mounts | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| SYNTH runtime / reflection lease consumption | 0 / 0 | 0 / 0 |
| BANK / EXECUTOR.1R / Apply / repository runtime writes | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

The initial sandbox endpoint preflight failed at `docker version`, before any image inspection, create or export. Its stderr/exit/thread metrics were not retained by that failed preflight. The successful diagnostic used authorized access to the same frozen endpoint. The raw trial remains the only export attempt. Development commands, pytest fixtures, evidence writes and temporary host profiles are separate from these operational counters; every actual Docker child uses `shell=False`.

The successful measurement recorded 14 `Thread.start` attempts, all belonging to the frozen bounded Docker-control readers: two per control. These benign host threads are separate from raw export capture, which starts none. Active Python threads returned from one to one. All eight successful-measurement Docker children were reaped and their pipes closed. Removal, absence verification and temporary-profile deletion passed independently of export timing. No archive was saved. No cleanup failure is hidden by the timeout classification.

## Validation and historical preservation

| Selection | Baseline | After |
| --- | --- | --- |
| Frozen Java / sandbox / discovery | 498 passed, 1 failed, 5 deselected | 498 passed, 1 failed, 5 deselected |
| BIND.1 / SANDBOX.2P / COMPAT.1 / JAVA.1D / frozen retry | 287 passed | 287 passed |
| Registry / picker / historical reversals | 292 passed, 12 failed | 292 passed, 12 failed |
| New diagnostic tests | additive | 15 passed |

Baseline and after failure identities match exactly; the full lists are retained in the JSON. Initial infrastructure testing in the sandbox default Temp produced 14 fixture failures because directory cleanup was denied. That tooling diagnostic is retained under `.tmp/runtime_java_discovery_diag1_20261009`; corrected baseline and after runs use workspace temporary state. No fixture or registry projection was used. The full repository suite was not run.

Both additive Python files compile in memory without bytecode output. `git diff --check` passed. The diagnostic tests cover unchanged scanner results and entry/path/link limits, bounded capture, timeout termination/pipe cleanup, no raw semantic parsing, and the mandatory raw-timeout stop before inventory or provider continuation.

All **1,847 pre-existing files** remain byte-identical, and all eight already-missing tracked paths remain missing. All eight historical preservation manifests match, including BIND.1, SANDBOX.2P and both JAVA.1D attempts. Original sandbox/Java/SYNTH/executor owners, reports, registry history, reversal receipts and unrelated edits were neither modified nor repinned. No stash/reset/clean was used. The only additions are the diagnostic controller, its pure tests, this report, diagnostic JSON and preservation manifest. Work stops at the measured classification.
