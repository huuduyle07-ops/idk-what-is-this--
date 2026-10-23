# RUNTIME.JAVA.1C.AUTH.DIAG.1 static context comparison

The successful PINNED.1C retry and blocked SYNTH nested attempt used identical frozen provider, JAVA.1C, SANDBOX.2, baseline transport and recovery source bytes. Both used the provider's restricted profiler during JAVA.1C. The successful retry additionally used a private-config trace observer, and the replay scripts selected different temporary roots. These are contextual differences; neither has been established as the cause of rejection.

This artifact performs no live comparison and asserts no standalone outcome. If the sole standalone diagnostic passes, it supports the required `STANDALONE_PASS_CONTEXT_SENSITIVE` comparison without another issuance. A standalone pass does not establish that nesting caused the historical failure. The historical bounds below remain useful if standalone fails.

## Frozen records and source identity

The historical success is `docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C_RETRY/RUNTIME_JAVA_PINNED_1C_RETRY_LOCAL.json`: `RUNTIME_JAVA_PINNED_1C_COMPLETE`, exactly one fresh JAVA.1C invocation, JAVA.1C `RUNTIME_JAVA_1_COMPLETE_WITH_WARNINGS`, cleanup verified and zero remaining phase containers. The historical blocked record is `docs/roadmap/phases/SYNTH_AUTH_PINNED_1/SYNTH_AUTH_PINNED_1_LOCAL.json`: one fresh JAVA.1C invocation, `RUNTIME_JAVA_1C_BLOCKED_AUTHENTICATION`, `not_authenticated`, and `ValueError: java1c_live_sandbox2_binding_rejected`.

SHA256 values were read from both original `pure_preoperational_gates.json` source-binding arrays and compared with current source bytes. All three values match for each entry; no historical hash was updated.

| Source | SHA256, equal in successful record, blocked record and current bytes |
| --- | --- |
| `core/runtime_java_pinned_provider.py` | `bca4a46363a27e23fba60cbc556eb30e3f2b6e03f4ed6e95c81ac7231756ddaa` |
| `core/sandboxed_java_positive_continuation.py` | `ec0f7a7a210fabca4d3df58323072829392bc3fcdb5b41213f5d56750af09f7f` |
| `core/thread_compatible_runtime_sandbox.py` | `8eea18d16c330dc7d116065ac9d23833bb2a0af58448b02438c26526141b1d45` |
| `core/candidate_runtime_sandbox.py` | `ebe409e7e798ec1e8f48c4bd2c49e5cd8b282906251f7c2c38c2933d1ef51913` |
| `core/sandboxed_java_capture_recovery.py` | `4eb248c80c357966018604f208f766120a845935574aba52d9be52e55b6ae861` |

## Context dependencies

- **Common profiler:** `core/runtime_java_pinned_provider.py:246-293` installs `sys.setprofile(observer)` around `runtime.verify()` and restores it in `finally`. Its fixed return-frame observation is present in both historical paths. Profiler presence alone cannot explain their different results.
- **Additional successful-retry trace:** `docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C_RETRY/authentication_controls.py:27-69` checks existing system/thread profiling, tracing and monitoring, then traces only the exact prefix generator and bounded control code objects. Lines 130-144 restore tracing and verify config absence. `scripts/replay_runtime_java_pinned1c_retry.py:53-65` enters this observer before provider invocation; `scripts/replay_synth_auth_pinned1.py:49-65` does not. No frozen SANDBOX/JAVA predicate directly branches on profiler or tracer presence. Possible timing influence remains unmeasured.
- **Temporary roots and config paths:** successful retry sets `tempfile.tempdir` to its retry directory at `scripts/replay_runtime_java_pinned1c_retry.py:58`; blocked SYNTH sets it to its own phase directory at `scripts/replay_synth_auth_pinned1.py:61`. `core/candidate_runtime_sandbox.py:363-372` derives a random absent Docker config path from `tempfile.gettempdir()`. SANDBOX workspace/file/socket setup is at `core/thread_compatible_runtime_sandbox.py:335-344`. The records establish different roots, without establishing a path failure.
- **Temporary owner wrappers:** `core/runtime_java_pinned_backend_target_binding.py:347-373` scopes transport and SANDBOX replay wrappers with `patch.object`. BIND's nested transport wrapper is scoped at `core/sandbox_backend_binding.py:290-333`. These scopes finish before JAVA.1C is invoked at `core/runtime_java_pinned_provider.py:537`. Static source provides no evidence of residual wrappers. Historical runtime function identities were not separately retained, so absence of residue cannot be retrospectively measured.
- **Target-export cleanup:** `core/runtime_java_pinned_target_inspection.py:352-379` stops and joins export threads, waits for the child and closes pipes. Lines 487-494 reject unverified cleanup. The blocked record reports upstream bind/inspection cleanup true and zero remaining upstream containers. It supplies no evidence of live export-thread residue during JAVA.1C.
- **Authentication domains and registries:** SANDBOX.2 has a module-local HMAC secret at `core/thread_compatible_runtime_sandbox.py:44`; exact type/HMAC and pair binding are checked at lines 136-150. JAVA.1C's independent key is at `core/sandboxed_java_positive_continuation.py:38`. Neither frozen owner exposes an issuing PID or live-object registry, and SANDBOX validation does not enforce exact object membership. Provider-local registries exist at `core/runtime_java_pinned_provider.py:42-44` and are populated by earlier graph work at lines 505-550; SANDBOX/JAVA validators do not consume them. No secret or signature is disclosed.
- **Caller frames and imports:** SYNTH invokes the provider at `core/synthetic_runtime_authorization_pinned.py:303-335`. The provider invokes fresh PINNED.1B and then JAVA.1C at `core/runtime_java_pinned_provider.py:505-537`. Its observer walks caller frames only to classify effect accounting at lines 271-287. Frozen SANDBOX/JAVA semantic predicates do not directly depend on a SYNTH caller identity.

## Historical pre-ladder bound

The blocked record's `/provider_proof_report/runtime_docker_controls` contains exactly three runtime controls: successful exact-image inspection, successful SANDBOX.2 container listing, and successful JAVA.1C/SANDBOX.2 container listing. Each exited zero and records completed/reaped/closed controls. Its effect ledger at record lines 2736-2775 records zero JAVA.1C-owned SANDBOX container creates/starts and zero fixed-controller creates/starts, Java compiles or JVM probes. The earlier BIND SANDBOX.2 invocation completed successfully.

The JAVA.1C-owned SANDBOX replay therefore stopped before any ladder invocation. `core/thread_compatible_runtime_sandbox.py:328-344` permits failure while parsing/checking image metadata or creating its temporary directory, policy/sentinel files and sockets before `invoke()`. The retained report cannot distinguish those deeper causes. Successful Docker command completion does not itself establish that the parsed image metadata satisfied the owner.

The named error occurs after `sandbox2.validate_descriptor()` and `sandbox2.validate_policy_bytes()` returned at `core/sandboxed_java_positive_continuation.py:51-67`. It records a semantic rejection and does not demonstrate HMAC failure. The frozen blocked report does not retain the particular semantic operand or the live SANDBOX report.

## Observation constraints and limitations

JAVA.1C builds the consumed pair at `core/sandboxed_java_positive_continuation.py:71-85`; SANDBOX replay signs an earlier pair at `core/thread_compatible_runtime_sandbox.py:378-382`. To retain the actual gate objects, observe `authenticate_sandbox2` call arguments or the `_evidence_pair` return whose caller is `_obtain_live_sandbox2`.

A diagnostic observer must block incompatible existing system/thread tracing, profiling or monitoring; restrict observation to fixed code objects; read original locals/arguments/returns without mutation; preserve owner functions and validators; retain original objects only within the diagnostic process; and restore instrumentation in `finally`. It must not expose HMAC secrets, change return values or receipts, or reconstruct objects before live validation. Retained frames are unnecessary. Instrumentation timing influence cannot be excluded merely by observing no owner mutation.

Matching source bytes do not prove equal process-global state or Docker responses at different times. Historical instrumentation state, runtime function identities, consumed object identities and the blocked SANDBOX report were not independently retained. This static comparison identifies possible dependencies and narrows the historical execution point; it establishes no particular contextual cause and implements no remediation.

This comparison made zero runtime-owner, Docker, Java or synthetic-authorization calls. It changed no owner or historical file.
