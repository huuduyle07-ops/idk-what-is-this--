# RUNTIME.JAVA.REQUIREMENT.PINNED.1

Status: `RUNTIME_JAVA_REQUIREMENT_PINNED_1_COMPLETE`.

Requirement profile: `RUNTIME.JAVA.PINNED.1`.
Requirement schema: `runtime_java_pinned_1_v1`.
Date: 2026-10-09, Asia/Seoul.

This additive phase freezes a requirement for one explicitly pinned immutable
provider. It defines semantics only. The immutable metadata owner is
`core/runtime_java_pinned_requirement.py`; its dictionary projection and the
companion report are requirement documentation, never authenticated provider
evidence, runtime capability, compatibility relation or execution authority.
The historical registry is unchanged; this phase is not registered as an
available runtime or selected by any current authorization/executor consumer.

## Required provider

| Identity | Required value |
| --- | --- |
| Image | `sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a` |
| java path | `/opt/temurin-26.0.2.1/bin/java` |
| java SHA-256 | `a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2` |
| javac path | `/opt/temurin-26.0.2.1/bin/javac` |
| javac SHA-256 | `e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023` |
| Controller path | `/usr/local/bin/python` |
| Controller identity primitive | Exact path plus owner-authenticated runtime measurement coherently bound to inspected resolved executable bytes/hash and immutable image |
| Controller expected digest | Unset; explicit future provider-proof obligation |
| Sandbox profile | `runtime_sandbox_2_v1` |
| Sandbox policy SHA-256 | `5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75` |

There is no discovery/selection step. Only the required immutable provider may
be inspected and proved. Generic candidate ranking, first matching image,
alternative providers, fallback, mutable tag selection, automatic substitution,
pull, build and provisioning are prohibited. Any mismatch blocks proof. The
contract does not require classifying unrelated images, proving no other Java
provider exists or proving exactly one Java provider exists.

Freeze these distinctions, with no boolean adapter or compatibility shim:

- `exact_provider_proven != complete_inventory`.
- `exact_provider_proven != complete_local_artifact_discovery`.
- `target_provider_absent != global_java_provider_absent`.
- `provider evidence != requirement identity`.
- Event A preceding event B does not authenticate them as one provider proof.

Global inventory is neither required nor claimed. Global absence and uniqueness
are neither required nor claimed. Target absence means only that the explicitly
required provider is unavailable locally. Inspection/transport failure does not
even establish target absence. Future receipts must not include
`complete_inventory=true` as a shim or assert complete local inventory. A later
separate full-inventory proof would need its own truthful evidence; it cannot
be inferred from this proof kind.

## Controller decision and source basis

JAVA.1 discovery fixes `/usr/local/bin/python`, resolves links and hashes the
actual executable (`core/sandboxed_java_toolchain_discovery.py:24-39,125-161,208-224`).
JAVA.1 and JAVA.1D gate exact path plus digest shape, rather than a requirement
pin for the controller hash (`core/sandboxed_java_toolchain.py:427-446`;
`core/sandboxed_java_discovery_continuation.py:81-88`). A historical LOCAL report
hash is not a stable authenticated requirement pin.

JAVA.1C fixes the controller entrypoint and source, validates runtime state and
signs its measurement digest, but rehashes only java/javac; its receipt has no
controller executable identity (`core/sandboxed_java_positive_continuation.py:123-169,210-241,320`;
`core/sandboxed_java_positive_probe.py:85-88`). Therefore a future owner must
measure/authenticate controller normalized path, resolved path, bounded bytes
and SHA-256 in target inspection and prove that runtime uses that same executable
in the same image. It must also bind the frozen controller source/invocation.
An additive authenticated controller measurement attachment is required; mere
presence, a digest-shaped string or unchanged historical prose is insufficient.
This is a precise provider-proof obligation, so requirement definition can
complete while provider proof remains unavailable.

## Target-local safety and budgets

Retain every target-local property listed in the metadata, including immutable
image identity, Linux/amd64 image metadata and Linux amd64 ELF64 little-endian
executable validation. Measure the complete java/javac executable bytes at the
exact paths and validate one same-directory resolved toolchain pair. Ambiguous
target records/pairs block. Require controller identity/authenticity, uid/gid
65534 executable and ancestor traversal checks, normalized POSIX paths, root
escape prevention, and bounded/cycle-free symlink/hardlink resolution (40 hops).
Unlisted ancestor permissions still require runtime confirmation.

Use bounded streamed archive inspection without host extraction. Inspect only a
stopped phase-owned container, with no Java, javac, controller or other workload
execution during target inspection. Independently verify its exact image and
frozen safe configuration; reject declared volumes, host binds/mounts, privilege,
network or added capabilities. Retain nonroot identity, read-only root, private
cgroup/IPC, resource limits and temporary filesystem restrictions. Verify export
and control-process reaping, pipe closure, removal/absence of phase containers
and temporary-state cleanup. Any failure blocks proof.

| Target inspection limit | Frozen value |
| --- | --- |
| Per-target export | 30 seconds |
| Archive bytes | 2 GiB (2147483648) |
| Archive entries | 250000 |
| Executable bytes | 128 MiB (134217728) |
| Link resolution | 40 hops |

No budget changes are justified by the unrelated historical image's diagnostic
failure. That observation does not establish that this exact target exceeds its
inspection budget. No target/image inspection occurred in this phase.

Fresh JAVA.1C component evidence must preserve exact fixed source/hash/readback,
argv, main/classpath, class manifest/output, version measurements and runtime
constraints. This includes SANDBOX.2's full frozen ladder/policy; network/mount/
shell/command prohibitions; PID 1 and uid/gid 65534; zero capabilities;
no-new-privileges; exact environment; namespaces/cgroups/descendant containment;
128 PIDs, 128 MiB memory and one CPU; /work 32 MiB and /tmp 16 MiB noexec tmpfs;
one controller thread and zero thread starts; independent bounded streams;
10-second outer timeout and 5-second abort/shared controller deadline; 8192-byte
outer streams, 2048-byte compiler and 1024-byte version/runtime streams; sole
class of 1..32768 bytes; and verified child, process-group, pipe, selector,
container and workspace cleanup. The frozen 129-byte infrastructure source is
the only future JAVA.1C fixture, not an authorization for candidate execution.

## Authenticated evidence graph

The arrows below denote required authenticated bindings, never chronological
evidence. The metadata enumerates the field equalities and obligations of every
edge. One future exact-provider owner must authenticate all nodes/edges and bind
their full identities/fingerprints/digests plus requirement profile/schema and
cleanup into one authenticated proof root.

```text
fresh backend binding -----> exact target inspection -----> exact provider identity
        |                             |                              |
        v                             v                              v
BIND's own sandbox pair            cleanup <--------------- fresh JAVA.1C runtime
        |                                                            ^
        | authenticated route/version bridge                         |
        v                                                            |
actual JAVA.1C sandbox pair ------------------------------------------+
```

Both sandbox pairs and the backend binding also have their own authenticated
cleanup edges. The bridge binds image, measured route/version, both pairs and
target inspection owner/fingerprint. Pair fingerprints and evidence digests
remain distinct; no cross-pair fingerprint equality is required. Route/version
on the sandbox nodes are future authenticated attachment measurements, not
fields claimed to exist in frozen SANDBOX.2 receipts.

Required roles include proof owner and owner-established fresh proof context;
inspection owner; target image; measured backend route and Linux server version;
inspection evidence fingerprint; backend attachment fingerprint; BIND's own
sandbox descriptor/receipt fingerprints and receipt evidence digest; actual
JAVA.1C sandbox descriptor/receipt fingerprints and receipt evidence digest;
JAVA.1C descriptor/receipt fingerprints and receipt evidence digest/image;
java/javac paths and hashes; controller normalized/resolved path, measured hash,
source identity and runtime identity evidence fingerprint; and cleanup result
and evidence fingerprint.

The target-binding owner must authenticate inspection provenance, owner and
fingerprint and compare its actual measured route/Server.Version to the
authenticated backend bracket. The provider owner must authenticate the exact
inspection object and bind its image/tools/controller to runtime identity. The
runtime descriptor must authenticate its exact receipt, which must authenticate
its own sandbox pair, exact image/tools/policy, evidence digest and cleanup.
Missing, stale, mismatched, fabricated or incomplete evidence blocks.

Owner fingerprints retain their frozen canonical full-payload SHA-256 meanings.
Future additive attachments must define canonical domain-separated payloads
covering all bindings and successful cleanup. Hash equality alone is not
authentication. Original owner authenticators must validate the exact typed
evidence; serialized JSON, copied objects and caller-supplied identifiers cannot
substitute for authenticated ownership. Independently issued contexts require
explicit owner-authenticated attachments. Freshness means newly authenticated
evidence for this proof attempt; historical receipt/report replay is prohibited.
Common process, common endpoint and time ordering supply no provenance.

### BIND.1 participation

`validate_sandbox_backend_binding(...)` may authenticate its exact live
attachment and own SANDBOX.2 objects, fingerprints, digest and image
(`core/sandbox_backend_binding.py:121-190`). Its route means the frozen
`local-docker:` endpoint and exact Linux `Server.Version` bracket equality
(`:211-237`). It does not prove daemon instance identity, continuity or ABA
resistance; the new requirement makes no such claims.

`sandbox_backend_binding_satisfies_java1_discovery(...)` explicitly expects
original JAVA.1 discovery-owner values and says strings do not authenticate
discovery (`:193-208`). It cannot be repurposed for target evidence. A future
additive target-binding attachment or exact-provider evidence owner is required.

JAVA.1C independently issues a fresh SANDBOX.2 pair internally
(`core/sandboxed_java_positive_continuation.py:71-84,369-394`). Preserve distinct
BIND and JAVA.1C sandbox fingerprints/digests when the pairs differ. Authenticate
both and their explicit route/version bridge, binding the actual JAVA.1C pair
to target inspection and runtime; do not infer they are the same pair. A prior
fresh BIND plus later fresh JAVA.1C is insufficient. No attachment or bridge is
implemented here.

### JAVA.1C participation and future receipt

Fresh JAVA.1C may be authenticated as the runtime component under its own frozen
semantics. Its own signed descriptor/receipt links must validate
(`core/sandboxed_java_positive_continuation.py:210-302`). It is not the new
requirement and cannot alone supply target/backend/controller linkage.

A future receipt must truthfully state: "The explicitly required immutable
provider was inspected, authenticated, coherently bound to the required backend
and runtime evidence, and verified under the required sandbox/runtime constraints."
It must carry `exact_provider_proven=true`, provider image/java/javac/controller
identities and authenticated target inspection, backend binding, sandbox,
runtime and cleanup evidence. These are conceptual field roles; this phase
freezes no receipt class layout and issues no receipt or positive proof.

## Truthful unavailable outcomes

Every outcome blocks proof and permits no fallback. None asserts global absence.
Cleanup failure blocks regardless of otherwise positive evidence.

| Outcome | Meaning |
| --- | --- |
| `PINNED_PROVIDER_ABSENT` | Exact required target conclusively unavailable locally; never the global `NO_SUITABLE_LOCAL_JAVA_ARTIFACT` result |
| `PINNED_PROVIDER_METADATA_MISMATCH` | Required image/platform/volume/configuration mismatch |
| `PINNED_PROVIDER_INSPECTION_INCOMPLETE` | Failed, truncated, over-budget, unavailable or ambiguous target inspection; absence unproven |
| `PINNED_TOOLCHAIN_MISMATCH` | Required paths, measured bytes/hashes, ELF, access or pair failed |
| `PINNED_CONTROLLER_MISMATCH` | Required controller identity/authenticity/linkage missing or mismatched |
| `PINNED_BACKEND_BINDING_MISMATCH` | Required route/version/owner/sandbox/target linkage missing or mismatched |
| `PINNED_RUNTIME_EVIDENCE_MISMATCH` | Required fresh JAVA.1C evidence, constraints or linkage missing or mismatched |
| `PINNED_CLEANUP_FAILURE` | Any required cleanup failed or incomplete |
| `PINNED_PROOF_UNRESOLVED` | Unknown/unclassified condition; fail closed without absence inference |

## Historical and future boundaries

The old `RUNTIME.JAVA.1` / `runtime_java_1_v1` remains generic ordered discovery
and provider selection with complete-domain classification, authenticated full
inventory and global absence semantics. The new epoch intentionally changes
those four semantics. It asserts no compatibility relation, schema/profile
alias, old JAVA.1 satisfaction of this new requirement, or retroactive receipt
meaning. `complete_inventory` is never reinterpreted. COMPAT.2 is not created.

SYNTH.AUTH.1 and its existing handles remain bound to the old requirement. Future
SYNTH use requires an additive authorization epoch (proposed
`SYNTH.AUTH.PINNED.1`) explicitly requiring this profile/schema. It requires a
later lifecycle compatibility review; SYNTH.AUTH.LIFECYCLE.1 acceptance cannot
be assumed. No authorization/lifecycle migration or mutation occurs here.

The following remains proposed architecture only:

```text
requirement boundary -> target-specific provider proof implementation
 -> provider proof validation -> new SYNTH authorization epoch
 -> lifecycle compatibility review -> operational EXECUTOR retry
```

All existing JAVA.1/1A/1B/1C/1D, COMPAT.1, DISCOVERY.DIAG.1/CONTRACT.1,
SANDBOX.1/2/2P/BIND.1, SYNTH.AUTH/REFLECT/lifecycle/admission,
EXECUTOR.1/1R, registry/history and reversal artifacts are preserved byte for
byte against the pre-edit snapshot. Existing historical drift is recorded, not
repinned. The validation artifact records focused and frozen pure tests,
registry/picker baseline versus after, benchmark structure check, in-memory
Python compilation, diff/whitespace checks and preservation comparison.

Operational effects are zero: Docker, containers, exports, Java, javac, runtime
compile, network, workload shell, host mounts, source projection, runtime and
reflection lease consumption, BANK, EXECUTOR.1R and Apply. Repository file edits,
Python test/benchmark/compilation checks and their host command invocations are
development validation only, separate from those prohibited runtime effects.

Stop at this requirement boundary. No provider discovery, target inspection,
provider implementation, runtime capability, JAVA.1D/EXECUTOR retry or downstream
authorization work is authorized by completion of this phase.

## Validation result

64 focused requirement tests and 671 frozen pure regressions passed. The
benchmark structure check passed all 54 cases. Direct registry/picker tests
produced 292 passes and the same seven baseline failures, with no new failure
identities. All 26106 pre-existing snapshotted files remain unchanged; no
historical drift was repinned. In-memory compilation passed for 41 Python
files; diff, authored whitespace and JSON checks passed.

See `RUNTIME_JAVA_REQUIREMENT_PINNED_1_REPORT.json`, `validation.json` and
`preservation.json` for the full contract projection, evidence and baseline
comparison. Denied dependency-bootstrap process/network attempts are recorded
separately from zero successful operational effects.
