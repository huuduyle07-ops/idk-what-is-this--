# RUNTIME.SANDBOX.BIND.1

2026-10-08 KST. **RUNTIME_SANDBOX_BIND_1_COMPLETE_WITH_WARNINGS**.

One PRE measurement, one fresh SANDBOX.2 invocation, and one POST measurement
completed. Both original JAVA.1 route and server-version strings matched
exactly. One live process-local attachment authenticated against that exact
descriptor/receipt pair. All 50 recorded negative controls rejected.

[Owner](../../../../core/sandbox_backend_binding.py),
[replay](../../../../scripts/replay_runtime_sandbox_bind1.py),
[focused tests](../../../../tests/test_runtime_sandbox_bind1.py),
[recorded proof and validation](RUNTIME_SANDBOX_BIND_1_LOCAL.json), and
[historical byte preservation](RUNTIME_SANDBOX_BIND_1_PRESERVATION.json).

The binding means: the original JAVA.1 route identity and Server.Version
values were stable over the bounded SANDBOX.2 verification window.
`daemon_instance_identity_available`, `daemon_continuity_proven`,
`aba_resistance_proven`, and `daemon_continuity_authority` are explicitly false.
No daemon-generation equality was tested or claimed.

The original discovery owner defines identity as
`"local-docker:" + sandbox._local_endpoint()` and version as
`str(server["Version"])`, with a dict Server, `Server.Os == "linux"`, and a
truthy Server.Version. The binding uses the frozen owner's fixed native Docker
route and `version --format '{{json .}}'` on each side. It preserves literal
Python string equality, including case and whitespace. Client.Version,
ApiVersion, context names, and caller backend aliases cannot substitute.
No strip, lower, semver coercion, client fallback, or other normalization occurs.

The no-argument `issue_sandbox_backend_binding()` obtains its own values and
fresh pair, and returns `(attachment, descriptor, receipt)` in the issuing
process. It accepts no backend identifiers, endpoints, config, context, or
measurement method. It uses the frozen SANDBOX.2 owner and public validator,
then rechecks the same fingerprints and exact stage-evidence digest after
POST. Cleanup failure or either bracket mismatch blocks issuance.

`SandboxBackendBindingAttachment` is a frozen dataclass with a random ID,
issuing PID, independent private HMAC key, live object registry, and retained
immutable signed projection. The registry retains the exact sandbox objects.
Its pure validator performs no Docker or filesystem I/O and does not mutate
or consume evidence. Exported JSON is report-only; it cannot recreate the
live attachment after the replay process exits. There is no ticket lifecycle.

The pure discovery predicate compares both canonical strings exactly after
authenticating the attachment and retained pair. Its recorded true result
uses controlled test values. Those strings are not authenticated discovery
evidence. A future JAVA.1D integration must obtain them from the exact original
discovery owner. This phase performs no discovery or JAVA.1D integration.

| # | Requested item | Recorded result |
| --- | --- | --- |
| 1 | Final typed status | RUNTIME_SANDBOX_BIND_1_COMPLETE_WITH_WARNINGS |
| 2 | Identity semantics | Literal `local-docker:` plus `sandbox._local_endpoint()` |
| 3 | Version semantics | Exact `str(Server.Version)`; dict Server, Linux Os, truthy Version |
| 4 | PRE identity | local-docker:npipe:////./pipe/dockerDesktopLinuxEngine |
| 5 | PRE version | 29.6.1 |
| 6 | POST identity | local-docker:npipe:////./pipe/dockerDesktopLinuxEngine |
| 7 | POST version | 29.6.1 |
| 8 | Route/version bracket equal | true |
| 9 | Daemon continuity proven | false |
| 10 | ABA resistance proven | false |
| 11 | Fresh descriptor fingerprint | fc78c9b36c51bfb49fb99ac145f2aac0f0e1672a612594c7738efa349fc0a504 |
| 12 | Fresh receipt fingerprint | e3a67bf7ca7919c933fa46dfe7e7b8ee1a666c1f5689cc6088e1b67f765a638d |
| 13 | Receipt evidence SHA-256 | 7241120ac81ed1a46a08ad029881eb25368cb71e2a09cc602d8d7e0f223efe42 |
| 14 | Policy SHA-256 | 5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75 |
| 15 | Image identity | sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a |
| 16 | Attachment ID / fingerprint | ce1463527098fde303a10164c8de818c6d99b157ac28c3b834624e26318eb193 / c6f820460d23ec779c51bf2c8fd52691ef5d24d1d5086c38fad336a105bb4a89 |
| 17 | Attachment authentication | Passed in issuing process |
| 18 | Exact pair binding | Passed; descriptor, receipt, evidence digest, phase, schema, policy, image bound |
| 19 | Copy/JSON/process/HMAC matrix | 50 recorded negative controls rejected; wrong-process control substitutes a different PID without starting another process |
| 20 | Discovery compatibility helper | true with controlled matching values; wrong identity/version false; actual discovery evidence not produced |
| 21 | SANDBOX.2 infrastructure effects | 74 Docker calls; 11 creates, 11 starts, 1 exact image inspection; 1 javac and 1 java version probe |
| 22 | Binding-only effects | Exactly 2 Docker version calls; 0 containers, image inspections, inventories, exports, pulls, builds |
| 23 | Discovery calls | 0 |
| 24 | Java compilation / fixture execution | 0 / 0 |
| 25 | Runtime / reflection lease consumptions | 0 / 0 |
| 26 | BANK / JAVA.1D / EXECUTOR.1R retries | 0 / 0 / 0 |
| 27 | Cleanup | SANDBOX.2 cleanup true; both version controls reaped and pipes closed; temporary workspace removed |
| 28 | Remaining phase containers | 0 from the frozen SANDBOX.2 final teardown check |
| 29 | Historical preservation | All 1,843 pre-existing paths unchanged: 1,835 exact file hashes and 8 already-missing paths |
| 30 | Baseline versus after | Same 12 pre-existing registry/reversal failures; zero new failures; exact selections/counts in JSON |
| 31 | Validation | 129 focused tests pass; required frozen and authority regressions match; 54 benchmark definitions valid; 1,233 Python files compile in memory; diff, whitespace and preservation checks pass |

All runtime, real-task, repository-write, Apply, network, host-mount, shell,
arbitrary-command, compatibility, and daemon-continuity authority fields remain
false. Outbound network, shell, host mounts, repository runtime writes, and
Apply counts are zero. The frozen SANDBOX.2 loopback isolation listeners and
fixed java/javac version probes remain infrastructure effects. They are not
behavioral Java execution.

Validation uses isolated test processes to avoid accumulating historical
audit hooks. The before baseline runs against a byte-exact copy of the
pre-change tracked/nonignored snapshot; after runs against the working tree.
No registry projection or historical repinning is used. The original
registry/picker selection also ran directly before edits and after, with
292 passed and the same 7 failures both times. Additional reversal and
authority tests account for the other 5 known failures.

The development harness denies real runtime subprocesses and outbound
connections. Its existing safety fixtures permit only read-only Git commands
and bounded Python-pytest within their temporary repositories; a known
failing-command shell fixture is denied before launch. Those development
fixture effects and report writes are separate from operational phase counts.
Fake-process reader tests use benign host threads. The existing google.genai
deprecation warning remains. The full repository suite was not run.

Historical SANDBOX.1/2/2P, JAVA.1/1A/1B/1C/1D/COMPAT.1, all SYNTH owners,
EXECUTOR.1/1R attempts, registry history, reversal receipts, and unrelated edits
retain their exact bytes. SANDBOX.2P remains
`RUNTIME_SANDBOX_2P_BLOCKED_FRESHNESS`. No stash, reset, clean, registry edit,
or reversal repin was used. The recorded proof stops here: JAVA.1C, JAVA.1D,
COMPAT.2, discovery, and executor operational work do not follow.
