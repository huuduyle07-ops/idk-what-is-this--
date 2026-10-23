# RUNTIME.JAVA.PINNED.1B

This additive phase authenticates one exact backend-to-target evidence edge:
fresh `RUNTIME.SANDBOX.BIND.1`, with its exact own `SANDBOX.2` pair, to fresh
`RUNTIME.JAVA.PINNED.1A` target inspection. The image is the frozen immutable
`sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`.
The requirement is `RUNTIME.JAVA.PINNED.1 / runtime_java_pinned_1_v1`.

The recorded final typed result is **`RUNTIME_JAVA_PINNED_1B_COMPLETE`**.
Exactly one live issuing process obtained and authenticated both fresh
upstreams, issued the binding receipt, rejected all 61 live negative controls,
and reauthenticated the original binding and upstream objects afterward.
Route, Server.Version (`29.6.1`), and immutable image equalities are true.
All upstream cleanup succeeded; zero phase containers remain. The saved JSON
is report-only and does not recreate the original process-local evidence.

The binding receipt ID is
`142e42c0ce55bdfa2ea6fe1e062a84ba4121e8f8a9293c9ee593f923ec1812cf`;
its fingerprint is
`52ec3bb7e46373dc1e1bcbcfd6bd512373150a285367f8a2608016d0aeace63b`.
The full upstream IDs, fingerprints, evidence digests, controller measurement,
cleanup digests, comparisons and authentication results are recorded in
`RUNTIME_JAVA_PINNED_1B_REPORT.json` and the immutable attempt artifact
`RUNTIME_JAVA_PINNED_1B_LOCAL.json`.

`core/runtime_java_pinned_backend_target_binding.py` is the new owner. Its only
operational entry obtains both upstreams through their existing public issuers,
authenticates them through their public validators, and retains their exact
original objects in a fresh process-local attempt. It compares exact route,
Server.Version, and immutable image identities. It then issues a typed receipt
with its own random ID, PID, domain-separated canonical digest, private HMAC,
and original-object registry. Independent upstream proof contexts are bound
without requiring them to be equal. Reusing upstream IDs or inspection contexts
from an earlier binding attempt is rejected.

`validate_pinned_backend_target_binding` is pure and requires the original
binding receipt, BIND attachment, sandbox descriptor, sandbox receipt, and target
inspection receipt in their issuing process. Exported JSON remains report-only.
Copying, reconstructing, matching hashes, or substituting report objects cannot
authenticate evidence. Cleanup must succeed before a positive receipt exists.

The receipt binds the measured controller path, resolved path, SHA-256 and
measurement digest as target evidence. Runtime controller identity remains
unproven. The phase issues no runtime proof or execution authority and creates
no lifecycle or lease. It makes no daemon identity, continuity, ABA resistance,
complete inventory, provider uniqueness, or provider availability claim.

`scripts/replay_runtime_java_pinned1b.py` checks recorded pure gates and exact
source hashes, checks historical preservation, then reserves its fixed report
exclusively before invoking either owner. It performs one live attempt and a
pure negative authentication matrix, reauthenticates the originals, and stops.
The existing 1A operational report is never used as live provenance. No JAVA.1C,
runtime bridge, SYNTH.AUTH.PINNED.1, COMPAT.2, or EXECUTOR.1R retry is invoked.

Operational accounting separates BIND's PRE/POST Docker version controls,
frozen SANDBOX.2 containment/controller/version infrastructure probes, and the
stopped target inspection's controls and single export. Frozen Java/javac
version probes are infrastructure measurements, with no Java compilation or
behavioral Java fixture. The stopped inspection starts no container and runs no
Java, javac, or controller workload. Repository validation and report writing
are host maintenance and are recorded separately from live runtime effects.

| Live scope | Docker controls | Creates | Starts | Exports |
| --- | ---: | ---: | ---: | ---: |
| BIND PRE Server.Version | 1 | 0 | 0 | 0 |
| BIND POST Server.Version | 1 | 0 | 0 | 0 |
| Frozen SANDBOX.2 infrastructure | 74 | 11 | 11 | 0 |
| PINNED.1A stopped target inspection | 6 | 1 | 0 | 1 |

The frozen infrastructure ran one `java --version` and one `javac --version`
probe, with zero compilations and zero behavioral Java fixtures. Its containment
machinery includes local listening endpoint fixtures. All workload execution,
source projection, network, shell, host mount, pull/build, generic image
inventory, alternative-image inspection, lease consumption, BANK, EXECUTOR.1R,
Apply and JAVA.1C counts outside those frozen infrastructure probes are zero.

Validation passed 152 focused pure binding tests and 1,048 frozen tests.
The additional historical reversal bookkeeping assertion still fails because
its older expected registry hash disagrees with the initial working-tree bytes.
The exact failure was present before the live attempt, and the registry and
all related historical bytes remain unchanged. That drift is documented in
`frozen_regression_assessment.json`; the raw failed test result remains intact.
The 75 historical EXECUTOR.1 blocked semantic tests all passed. The full frozen
suite needed directory metadata access outside the Windows filesystem sandbox;
its process/network/runtime denial guard remained active, with no owner or
validator adaptations and no runtime effects.

Registry/picker baseline and after results both have 292 passes and the same
seven pre-existing failures, with zero new failures. Benchmarks checked 54 cases
with zero errors. In-memory compilation, Git whitespace checks, authored JSON
and whitespace checks passed. All 1,962 initial source/artifact files remain
byte-for-byte unchanged. Historical drift was not repinned. Five phase-owned
pure-test temporary directories were removed after validation.

The phase directory contains the single live report, source-bound pure gates,
focused and frozen test results, benchmark check, registry/picker baseline and
after results, final validation, and preservation evidence. Historical drift
is reported against its original manifests and is never repinned.
