# RUNTIME.SANDBOX.2P — backend provenance freshness stop

2026-10-08 KST. **RUNTIME_SANDBOX_2P_BLOCKED_FRESHNESS**.

One fresh SANDBOX.2 invocation passed all eleven frozen infrastructure stages.
Its owner descriptor and receipt authenticated, one fixed-endpoint Docker
version call measured the original backend values, and the same live pair
reauthenticated with unchanged fingerprints and stage-evidence hash.
The frozen owners provide no mechanism to prove daemon continuity across
their separate Docker CLI connections. The request explicitly requires a stop
in this case. No provenance attachment was issued.

[Additive owner](../../../../core/sandbox_backend_provenance.py),
[replay](../../../../scripts/replay_runtime_sandbox2p.py),
[focused tests](../../../../tests/test_runtime_sandbox2p.py),
[live evidence and validation](RUNTIME_SANDBOX_2P_LOCAL.json), and
[byte preservation](RUNTIME_SANDBOX_2P_PRESERVATION.json).

This is a blocked attempt under `runtime_sandbox_2p_v1`. Attachment types,
an HMAC domain, an issuance registry and a public attachment validator were
deferred at the required freshness stop. There is no partial positive
attachment, capability, compatibility bridge or lifecycle state machine.
SANDBOX.2 was not modified. JAVA.1D was not retried and retains its original
`RUNTIME_JAVA_1D_BLOCKED_BACKEND_BINDING` regression. COMPAT.2 was not created.

## Exact original semantics

The original `sandboxed_java_toolchain_discovery.py:392` defines identity as
`'local-docker:' + sandbox._local_endpoint()` and version as
`str(server['Version'])`. It requires `Server` to be an object,
`Server.Os == 'linux'`, and a truthy `Server.Version`.
`candidate_runtime_sandbox.py:378-405` uses the same identity and version
semantics for SANDBOX.1. Both query `version --format '{{json .}}'` through
the frozen owner's `_docker_prefix()`.

`sandboxed_java_toolchain.py:442-444` compares both strings directly with
`!=`. There is no whitespace trimming, casing change, semver normalization or
client-version fallback. The version is the Docker **server's `Version`
field**, not `Client.Version`, `Client.ApiVersion`, or `Server.ApiVersion`.
The identity is an endpoint-route identity; the original contract does not
define it as a daemon-instance ID. Context names, hostname, CLI executable
path, image hash, and timestamps are not substitutes.

On this Windows host, the original endpoint is exactly
`npipe:////./pipe/dockerDesktopLinuxEngine`. The frozen prefix supplies
`--host` explicitly, a randomized absent `--config` directory, a native Docker
executable outside the repository, and a stripped control-process environment.
Neither the replay nor measurement operation accepts caller backend strings,
endpoint/config/context arguments, report JSON, or a freshness override.

The added measurement uses only one bounded
`version --format '{{json .}}'` call (8,000 ms, stdout 65,536 bytes) on that
route. It performs no image enumeration, export or workload launch.
The original discovery owner itself was not run operationally.

## Why freshness remains unproven

The existing JAVA.1C helper `_obtain_live_sandbox2()` runs the SANDBOX.2 owner,
locally reissues the pair through its original issuer, checks fingerprints
against that invocation, and uses the existing public validator. Calling this
helper does not call JAVA.1C `verify()` or compile/run its fixture.

After authenticating that fresh pair and checking its cleanup, SANDBOX.2P
measured the backend, reauthenticated the same object references, and checked
both fingerprints against their saved values and this invocation's exported
fingerprints. It also rechecked the receipt's exact stage-evidence hash.
Those checks establish an unchanged authentic sandbox snapshot. They cannot
establish that the daemon serving a later connection is the daemon that ran
every infrastructure stage.

The frozen owner opens separate CLI connections for each operation. It holds
no daemon session, generation binding, backend continuity lease, or pinned
transport across the ladder and later measurement. The authenticated pair
contains neither backend values nor an owner-defined continuity witness.
A backend can change at the fixed named pipe while preserving the same
endpoint string and server version. Repeated matching values also permit an
ABA replacement. Timestamps and additional endpoint/version comparisons
cannot resolve this. The request therefore blocks positive issuance here;
no invented daemon-identity semantics or timestamp freshness claim was added.

## Requested proof ledger

| # | Item | Recorded result |
| --- | --- | --- |
| 1 | Final typed status | RUNTIME_SANDBOX_2P_BLOCKED_FRESHNESS |
| 2 | Original backend identity semantics | Literal `local-docker:` plus frozen local endpoint |
| 3 | Original backend version semantics | Exact `str(Server.Version)`; Linux server, truthy version; no normalization |
| 4 | Fresh descriptor fingerprint | 7d10a76513fb651271aace91335ebd35e1bf1c1aef918cbc7d645f17b9216bc2 |
| 5 | Fresh receipt fingerprint | 84da1e33a55a94f4e17da6eb3083d3bb7ea4fef5074cd33aff5739d420d9937f |
| 6 | Sandbox policy SHA-256 | 5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75 |
| 7 | Measured backend identity | local-docker:npipe:////./pipe/dockerDesktopLinuxEngine |
| 8 | Measured backend version | 29.6.1 |
| 9 | Measurement method | frozen_local_docker_version_server_v1; one bounded fixed-route server-version control |
| 10 | Attachment ID / fingerprint | None / None; issuance blocked |
| 11 | Exact binding | Same sandbox pair reauthenticated and fingerprint/evidence equality passed; authenticated backend attachment binding remains unproven |
| 12 | Process-local authentication | Fresh SANDBOX.2 authentication passed; attachment authentication not attempted because no attachment exists |
| 13 | Copy / JSON rejection | SANDBOX.2 JSON and replacement negatives pass; attachment-copy/JSON authentication matrix not run because attachment issuance was blocked |
| 14 | Freshness | Unproven; frozen owner has no backend continuity binding |
| 15 | SANDBOX.2 Docker/container effects | 74 Docker calls; 11 create attempts, 11 containers created, 11 starts, 1 exact pinned-image inspection |
| 16 | Additional provenance Docker effects | 1 version call; 0 containers, image inspections, inventories, exports, pulls or builds |
| 17 | Java/javac version probes | 1 java version and 1 javac version, only in frozen SANDBOX.2 ladder |
| 18 | Compilation / fixture execution | 0 / 0 |
| 19 | Artifact discovery calls | 0 |
| 20 | Artifact exports / pulls / builds | 0 / 0 / 0 |
| 21 | Outbound network / shell / host mounts | 0 / 0 / 0; original sandbox's two loopback isolation listeners stayed quiet |
| 22 | Runtime / reflection lease consumptions | 0 / 0 |
| 23 | BANK / EXECUTOR.1R / JAVA.1D retries | 0 / 0 / 0 |
| 24 | Cleanup | All sandbox cleanup checks passed; temporary workspace removed; bounded provenance control reaped and pipes closed |
| 25 | Remaining phase containers | 0, measured by SANDBOX.2's frozen final teardown check |
| 26 | Historical preservation | All 1,829 existing tracked/nonignored files retain exact bytes; eight already-missing paths stay missing |
| 27 | Baseline vs after failures | Same twelve distinct pre-existing failure identities; zero new failures; no repinning or registry projection |
| 28 | Validation | 54 new focused tests pass; required adjacent baseline/after selections match; benchmark checks, in-memory compilation, diff/whitespace and byte preservation pass |

All requested authority fields, plus the frozen `shell_available` field,
remain false. Java source projection, repository runtime writes, Apply,
behavioral Java execution, inventory hashing, image-membership proof and
fresh JAVA.1C verification are all absent. SANDBOX.2's fixed data projections,
containment probes and two toolchain version commands are infrastructure
effects and are reported separately from the added provenance control.
Development test fixture processes and report writes are outside the
operational counts; their exact selections/effects are recorded in JSON.

## Validation and limits

| Selection | Baseline | After |
| --- | --- | --- |
| SANDBOX.2P preflight negatives and original value semantics | New selection | 54 passed |
| Frozen SANDBOX.1/2 and JAVA.1/1A/1B/1C pure/infrastructure regressions | 498 passed, 1 failed, 5 deselected | Same |
| Five fake-process reader/observer tests | 5 passed | Same |
| SYNTH.AUTH/reflection/lifecycles and historical EXECUTOR.1R | 801 passed | Same |
| EXECUTOR.1R lifecycle retry blocked regressions | 46 passed | Same |
| JAVA.COMPAT.1 and JAVA.1D blocked regressions, including original discovery/backend binding controls | 77 passed | Same |
| Authority / Apply / patch / path safety | 241 passed, 1 failed | Same |
| Registry / picker / historical reversal checks | 292 passed, 12 failed | Same |

The same twelve distinct registry/reversal-drift failures appear in both
runs; some occur in more than one selection. Existing fixture pins and
registry bytes were left untouched. Test audit guards deny actual Java,
Docker, network and other runtime process starts. The safety selection
allows only its existing bounded read-only Git and Python-pytest fixture
commands; a known failing-command fixture is denied before launch in both
runs. Fake reader tests permit benign host Python threads with no actual
subprocesses. The existing `google.genai` Python 3.17 deprecation warning
remains. The full repository suite was not run.

`benchmarks/run_benchmarks.py --check --quiet` checks all 54 definitions with
zero errors and no workload/agent execution. Python compilation is in memory
with no bytecode output. `git diff --check` and whitespace checks pass.
The preservation manifest records every pre-existing file's before/after
SHA-256, including all Java/sandbox/synthetic/lifecycle owners and reports,
executor attempts, registry snapshots and reversal receipts. Unrelated
working-tree edits were preserved; no stash/reset/clean was used.

The positive attachment authentication matrix (copy, reconstruction,
subclass, wrong process/HMAC, modified witness and cross-invocation binding)
cannot be claimed as passed: there is no issued attachment or validator to
test. The preflight instead rejects nonowner sandbox objects, wrong exact
phase/schema/policy, missing or substituted backend metadata, changed pairs,
changed stage evidence, and cleanup failures, and stops before any signer.
All successful attachment-schema/authentication work remains deferred until
an owner-defined backend continuity mechanism can satisfy the explicit
freshness requirement. Work stops here; no JAVA.1D operational retry follows.
