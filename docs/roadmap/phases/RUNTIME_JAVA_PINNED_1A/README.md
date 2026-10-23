# RUNTIME.JAVA.PINNED.1A — exact target inspection evidence

This additive owner implements only the target-inspection node of the frozen
`RUNTIME.JAVA.PINNED.1` / `runtime_java_pinned_1_v1` requirement. The final typed
operational outcome is recorded in `RUNTIME_JAVA_PINNED_1A_LOCAL.json`, with
validation and preservation in `validation.json` and `preservation.json`.
The final phase report is `RUNTIME_JAVA_PINNED_1A_REPORT.json`.

The final typed result is **`RUNTIME_JAVA_PINNED_1A_COMPLETE`**. The single live
inspection exported 443077120 bytes and 6057 archive entries in 15927.052 ms,
within the frozen 30000 ms deadline. Six fixed Docker controls created one
stopped container, inspected its configuration, then removed it and verified
absence. All child/thread/pipe/profile/workspace cleanup facts passed, with
zero remaining phase containers and all prohibited workload effects zero.

| Executable | Normalized path | Resolved path | Complete bytes | Measured SHA-256 |
| --- | --- | --- | ---: | --- |
| java | `/opt/temurin-26.0.2.1/bin/java` | `/opt/temurin-26.0.2.1/bin/java` | 16296 | `a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2` |
| javac | `/opt/temurin-26.0.2.1/bin/javac` | `/opt/temurin-26.0.2.1/bin/javac` | 16384 | `e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023` |
| controller | `/usr/local/bin/python` | `/usr/local/bin/python3.12` | 14472 | `0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263` |

Java and javac matched the requirement and formed one exact same-directory
pair. All three measured files are ELF64 little-endian x86-64, mode 0755,
executable by uid/gid 65534. The controller resolves through `python3` to
`python3.12`. Every listed ancestor permits traversal; the archive omits root
directory metadata, so `/` remains explicitly unknown and full ancestor
metadata completeness is false. No runtime traversal or controller linkage is
claimed. The controller hash above is inspection evidence only.

The measured backend route is
`local-docker:npipe:////./pipe/dockerDesktopLinuxEngine`, with Linux Docker
`Server.Version` exactly `29.6.1`. The frozen JAVA.1C controller source metadata
is SHA-256 `4f81640e2f01bc1f7a1a833beb269a9d1df51088b69cf24c8369fb6683f11a58`,
13037 bytes, without invoking JAVA.1C.

The original receipt authenticated before and after all 11 live negative
controls. Its report fingerprint is
`de18a7f83a2defb6d33378b3d9a58d80cf0137ee4e1ac0296b4b0416e91dab0d`.
Authentication was checked inside the issuing process; the saved JSON remains
report-only after that process exits. The phase establishes target inspection
evidence only, with exact-provider proof, runtime authority, BIND linkage and
controller runtime identity all false.

The operational entry point `inspect_target()` accepts no arguments. It queries
only image `sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`.
There is no inventory, caller target, tag, alternative provider, selection,
fallback, pull, build or provisioning path. The fixed replay reserves its output
exclusively and checks all recorded pure gates and safety-source hashes before
performing one live attempt. Historical attempts are never overwritten.

## Inspection and measurements

The owner measures the frozen local Docker route and Linux `Server.Version`
string through the original BIND.1 pure route/version primitives. This is a
target-inspection measurement, with no BIND attachment, authenticated bridge,
daemon identity, continuity or ABA claim. The original discovery comparator is
never called with target evidence.

Exact image metadata must establish the immutable ID, Linux/amd64 and no
declared volumes. Conclusive exact-target absence returns
`PINNED_PROVIDER_ABSENT`, without global Java absence. Unavailable/ambiguous
inspection, including malformed JSON, returns
`PINNED_PROVIDER_INSPECTION_INCOMPLETE`. Established metadata mismatch returns
`PINNED_PROVIDER_METADATA_MISMATCH`.

The owner creates one fresh stopped container with pull never, network none,
read-only root, uid/gid 65534, all capabilities dropped, no-new-privileges, the
frozen SANDBOX.1 stopped-inspection seccomp policy, private cgroup, IPC none,
128 PIDs, 128 MiB memory, one CPU, /work 32 MiB tmpfs and /tmp 16 MiB noexec
tmpfs, and no host bind/mount. The inert frozen controller command is never
started. Independent configuration inspection uses the original pure safety
predicate and additionally matches the returned container ID, exact Config.Image,
PID zero and created state. Configuration failure blocks before export.
The inspection policy is not a claim of SANDBOX.2 runtime verification.

One streamed export preserves the fixed 30000 ms, 2147483648-byte,
250000-entry, 134217728-byte executable and 40-link-hop limits. No archive or
executable is extracted or persisted; no full archive is retained in memory.
Tar member caching is disabled. The parser verifies complete archive termination,
drains the complete bounded stream, rejects trailing nonzero data/truncation,
and validates every path/link, including unrelated links. Duplicate normalized
or conflicting resolved file records are ambiguous and block.

An additive parser restriction caps each GNU/PAX extension and the accumulated
effective PAX metadata at 64 KiB, rejecting oversized metadata before tarfile
buffers it. Unsupported sparse metadata is rejected. Physical headers,
including extensions, count within the existing 250000-entry bound. These
restrictions prevent metadata from retaining most of an archive; none increases
or edits the frozen requirement budgets. Header-first ELF classification skips
hashing scripts and other non-ELF executable files while preserving complete
byte hashing for candidate Linux amd64 ELF executables and arbitrary link aliases.

The archive wrapper imports the exact frozen POSIX path, root-contained
symlink/hardlink, cycle/hop, traversal, uid/gid execute, ELF and complete bounded
hash primitives. It records normalized/resolved paths, complete hash and byte
size, ELF facts, owner/group/mode, nonroot executable permission, ancestor
traversal/completeness, and link chains for java, javac and the controller.
Known ancestor permission failures block; unlisted ancestors remain explicitly
unknown under the frozen primitive and require later runtime confirmation.

Java and javac must match the frozen required normalized paths/hashes and one
resolved same-directory pair. There is no ranking among target toolchains.
The controller must resolve from `/usr/local/bin/python` to a measured accessible
Linux amd64 ELF executable. Its measured hash is evidence, never a requirement
constant. The expected frozen JAVA.1C controller source hash/size is metadata
computed without executing its controller or invoking JAVA.1C.

Freeze `target_controller_measured != runtime_controller_same_executable_proven`
and `inspection_route/version_measured != BIND-backed_backend_linkage_proven`.

## Cleanup and independent authentication

Success requires reaping the export and all control processes, closing pipes,
stopping/joining the deadline supervisor and stderr reader, removing the stopped
container and verifying its known absence, removing the temporary policy and
workspace, and zero remaining containers from this invocation. Missing cleanup
facts or any failure yields `PINNED_CLEANUP_FAILURE`, overriding positive bytes
or other mismatch outcomes. No partial executable measurements can issue a
receipt after incomplete export or cleanup.

`PinnedJavaTargetInspectionReceipt` binds phase/schema, requirement identity,
inspection owner, fresh proof context, random receipt ID, issuing PID, exact
image/metadata digest, route/version, container/configuration/policy identity,
archive counts/result, complete executable facts, controller source metadata,
cleanup result/digest, full evidence digest, elapsed export time and operation
counts. Independent random owner HMAC uses domain-separated canonical payloads.
The live registry retains the original object, signed bytes and evidence bytes.
Validation requires exact type, object identity, current issuing process, HMAC
and unchanged retained payload/digest. A matching hash alone never authenticates.

Copies, dataclasses.replace, deepcopy, JSON projection/reconstruction,
subclasses/wrappers, wrong process, wrong HMAC and changed identities, cleanup
or evidence are rejected. JSON is report-only. Authentication neither consumes
nor invalidates evidence; there is no ISSUED/CONSUMED/INVALIDATED state machine,
lease, execution ticket, runtime authority or compatibility relation.

`RUNTIME_JAVA_PINNED_1A_COMPLETE` means only that the exact target's inspection,
executables, local backend measurement and cleanup were authenticated within
the inspection bounds. No receipt claims complete inventory/local discovery,
global provider absence/uniqueness, exact_provider_proven, runtime availability,
controller runtime identity, BIND/JAVA.1C linkage, SYNTH authorization or executor
permission. Only the requirement-defined target absence, metadata mismatch,
inspection incomplete, toolchain mismatch, controller mismatch, cleanup failure
and unresolved outcomes are emitted here.

## Scope and validation

All existing requirement, JAVA, COMPAT, DISCOVERY, SANDBOX, SYNTH, EXECUTOR,
registry/history and reversal artifacts remain unchanged. The previous pinned
requirement/test/report/validation/preservation artifacts are included in the
fresh source baseline. Unrelated working-tree edits and historical drift are
preserved without repinning.

Pure fixtures cover target identity, truthful absence, platform/volumes/config,
paths/links/hops/cycles, ELF/access, exact hashes/pair/controller measurements,
all resource bounds, timeout/truncation/metadata buffering, cleanup precedence,
receipt tampering and copy/JSON/process/HMAC rejection. Frozen pure regressions,
registry/picker baseline versus after, benchmarks --check, in-memory compilation,
diff/whitespace/JSON checks and preservation must pass before the live attempt.
Pre-existing direct registry/picker failures are compared by exact identity.

Final validation passed 163 focused target/archive tests and 735 frozen pure
regressions. The direct registry/picker baseline and after result both remain
292 passed and the same seven pre-existing failures, with no new failures.
Benchmark structure validation checked 54 scenarios with zero errors. All 46
in-memory Python compilations, authored whitespace/JSON and `git diff --check`
passed; pre-existing line-ending notices were retained. All 1931 freshly hashed
source/artifact files remain byte-for-byte unchanged, with no missing files or
unexpected additions. The 24199 guidance hashes are carried forward from the
previous verified phase, rather than claimed as freshly rehashed here.
Historical drift from ten prior manifests was preserved without repinning.
Six newly created pure-test fixture directories were removed; the live
inspection's separate workspace/profile had already been removed before
receipt issuance.

Allowed live effects are the fixed local Docker controls, one stopped container
and one bounded export where possible. Container starts, Java/javac/controller
workload execution, Java compilation, source projection, outbound network,
workload shell, host mounts, pulls/builds, inventory/alternative-image queries,
SYNTH/reflection lease consumption, BANK, EXECUTOR, Apply and JAVA.1C invocations
must remain zero. Host Python/test/benchmark and artifact operations are recorded
as maintenance, separate from workload effects.

Stop after target inspection evidence. Backend binding, the sandbox/runtime
bridge, authorization, compatibility and executor retries remain unimplemented.
