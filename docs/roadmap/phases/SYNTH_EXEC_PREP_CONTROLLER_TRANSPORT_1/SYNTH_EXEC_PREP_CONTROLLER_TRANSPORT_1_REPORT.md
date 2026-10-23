# SYNTH.EXEC.PREP.CONTROLLER.TRANSPORT.1

**TRANSPORT_SELECTION_UNRESOLVED**

A persistent single-thread PID1 Python controller, its original stdio channel,
fixed inline-source bootstrap and a 30-second owner lifetime form the preferred
reviewed candidate. **No final architecture/transport is selected.** Independent
safe outer cleanup still lacks a concrete backend-generation binding mechanism,
and complete response fit under the frozen aggregate capture cap is unproved.
Failing closed on either gap does not satisfy the selection criteria. The
requested COMPLETE marker is not earned; no requirement is silently relaxed.

This is design/selection analysis only. No controller source, workspace,
container or capability is implemented, materialized, created or issued.
Stop here. The profiles below record concrete reviewed design decisions for
candidate A; they are not accepted operational architecture or authority.

The frozen owner remains `core.synthetic_execution_preparation_controller_pinned`
and protocol remains `synthetic_preparation_controller_pinned_1_v1`.
The original semantic schema is byte-preserved. [selection.json](selection.json)
records the decision and open blockers; [evidence_index.json](evidence_index.json) records
source hashes, sizes and exact line anchors. No historical API or pin changes.

## Candidate comparison

| Candidate | Decision | Generation, operations and supervision |
|---|---|---|
| A. Persistent in-container controller | Preferred, unresolved | One original PID1/channel can retain fence, challenge/sequence, mount/artifact continuity and compiler ownership. Independent backend-generation cleanup binding and aggregate response fit are still missing. |
| B. Retained container with fixed per-operation host execution | Not selected | Could be designed without intrinsic seccomp widening, but needs a keeper/reaper, per-child identity/admission/capture and fixed exec boundary. Host serialization alone does not prove in-container coherence. No such retained repository implementation exists; adding a persistent authoritative broker converges on A. |
| C. Existing JAVA.1C one-shot | Incompatible with retention | Real repository architecture, but always destroys the container before return and launches its historical target JVM. Its APIs cannot provide a retained preparation workspace and must remain unchanged. |

All sixteen requested dimensions are compared for each candidate in
`selection.json:candidates`: generation, workspace continuity, challenge,
fence, mutation exclusion, observation coherence, child/capture/reaping,
disconnect/reconnect, cleanup after loss, root/tmpfs/network/environment,
complexity and SANDBOX.2 changes. No invented fourth architecture is needed.

Persistent stdio is the preferred transport profile. A container-local Unix endpoint is
**REQUIRES_REQUIREMENT_EVOLUTION**: SANDBOX.2 denies socket/socketpair and
connect/bind/listen/accept for AF_UNIX too; the endpoint also conflicts with
empty `/tmp` and the exact `/work` manifest. Fixed per-operation stdio adds
the unsupported boundaries in B. TCP, host IPC mounts and generic Docker
attach/exec are excluded. No repository-native retained alternative was found.

## Reviewed candidate byte framing and preemption

Framing ID: `synthetic_preparation_controller_u32be_json_1_v1`.
Each frame is four unsigned big-endian length octets followed by exactly that
many canonical JSON octets. Length counts payload only. Payload is 1..8188
bytes and the **whole frame is at most 8192 bytes**. No magic or extra version
is necessary: authenticated launch binds framing ID and the frozen JSON
envelope already requires protocol ID and version 1.

Canonical payload is strict UTF-8 JSON, sorted keys, compact separators,
`ensure_ascii=true`, `allow_nan=false`, with exact frozen types/list order.
Reject BOM, malformed UTF-8, duplicate/unknown/missing fields, bool-as-int,
coercion, nonfinite values and any trailing/noncanonical JSON bytes. Validate
and compare canonical re-encoding before admission. No string command parser.

Kernel partial reads are accumulated, not treated as separate frames. A partial
header/body gets one 1000ms deadline from its first byte, clamped to all shorter
absolute deadlines, never renewed per byte. EOF or timeout before completion
rejects and ends the generation. Frame-boundary EOF is also terminal; final
cleanup response followed by EOF is normal closure, never retained readiness.

One complete request receives one terminal response if transport survives;
lost responses do not permit effect replay. Multiple pairs share one channel.
Ordinary operation traffic alternates request/reply. The sole necessary
exception is **one FIFO BEGIN_CLEANUP control request behind one pending ordinary
request**, allowing the frozen immediate cleanup barrier. There are no
independent multiplexed streams, interleaved frames, out-of-order replies,
general queue or concurrent mutations. Barrier admission precedes reaping or
either reply. If its reply has not started, the cancelled original gets frozen
typed failure, then cleanup gets its reply. If original reply bytes already
started, finish that bounded frame and suppress readiness/receipt at the host
barrier; do not rewrite bytes or claim rollback. Every other extra/duplicate
frame is terminal. A stalled or unavailable cleanup channel uses outer cleanup.

Before effects, reject already-buffered/readable unexpected trailing data.
Later invalid stream bytes cancel and suppress success; no finite parser can
promise that future invalid bytes undo an already admitted effect. IDs and
sequences are generation-wide single-use, never reset on lost responses.

Retain the frozen **8192-byte cumulative per-stream preparation capture cap**,
including wire headers, across materialize/compile/observation. A separate
65536-byte per-direction/64-request lifetime ceiling bounds retained protocol
state, and never relaxes the preparation cap. Reserve both cleanup request slots and response
budget before ordinary admission. Incomplete or oversized evidence fails
closed, with independent outer teardown; never truncate a successful snapshot.
Controller stdout contains only frames; child stdout/stderr are separate and
controller stderr is empty on success.

## Reviewed candidate bootstrap and source delivery

Entrypoint `/usr/local/bin/python` resolves to frozen `/usr/local/bin/python3.12`,
SHA256 `0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263`.
The exact six-element argv is that executable, `-I`, `-S`, `-B`, `-c`, and one
future reviewed source string. Its last literal value awaits implementation;
its position, delivery and validation semantics are specified for this candidate.

Future fixed source belongs to
`core.synthetic_execution_preparation_controller_source_pinned`, an additive
source accessor which does not exist yet. Inside the container it has **no
filesystem source location**: it is the exact immutable create `Config.Cmd`
argument and Python memory (`<string>`). It is not embedded in the pinned image.
No tmpfs script, stdin source upload, generic copy, caller script, host mount or
image rebuild is selected. The existing JAVA.1C `-c` bootstrap is source
precedent; its exact-source validator and one-shot capture helper cannot be
reused unchanged for this retained session.

The new fixed bootstrap adapter is an explicit effect/input boundary. Future
workspace creation/launch needs its own reviewed fixed launch admission binding
actual source bytes/hash/size and exact inspected Cmd before create/start.
Historical provider authority and preparation facets do not authorize it.
This phase issues no bootstrap authority. Missing identity/admission fails
before creation, without a generalized delivery fallback.

Measure exact future source bytes, `SHA256(bytes)` and `len(bytes)` without text
normalization; all three values remain null now. Require strict UTF-8 roundtrip,
no NUL/BOM, no interpolation and one argument. The 65536-byte secondary source
ceiling does not guarantee native argv fit: preflight the full quoted Windows
command line below 32767 UTF-16 code units and Linux argument/system limits.
Oversize fails closed without alternate delivery. Bind actual argv, exact
eight-variable environment, interpreter/image/policy, protocol/framing,
original host registry/handles and all generation relations before readiness.

Create uses the unchanged image, read-only root, exact `/work` and `/tmp`
tmpfs, nonroot 65534:65534, network none, pids 128, memory 128MiB, CPU 1,
cap-drop ALL, no-new-privileges and exact SANDBOX.2 seccomp. No environment
extension. Use no TTY, OpenStdin=true, StdinOnce=true, restart policy no,
AutoRemove=false. Inspect these plus exact Cmd/config before a sole fixed
`start --attach --interactive` using the retained full container ID. Every
control call is clamped to remaining work-cutoff time. No generic command or
attach API is exposed and ambiguous start cannot be retried.

## Generations, observations and local fence

Container generation, workspace generation, controller generation and channel
generation each use independent owner-generated unpredictable 32-byte hex IDs.
They identify a retained authenticated relation; random tokens do not prove
liveness. Independently observe full immutable container ID/configuration,
actual start/no-restart relation, PID1 start ticks/namespace/cgroup incarnation,
`/work` and `/tmp` mount identities, and original host process/pipe handles.
PID alone, name, timestamp, route/version equality and token echo are insufficient.
Controller incarnation describes the observed live process; controller generation
binds that incarnation to exact source/bootstrap and original owner/channel.
Session identity is retained in that authenticated relation, without adding
semantic fields. First authenticated inner request pins the immutable relation.

The original live channel plus challenged complete snapshots supports that
retained controller relation. It does not prove daemon continuity or eliminate
unobservable ABA. The repository expressly leaves backend continuity unproved.
Any gap invalidates the original workspace permanently; new controller in the
same container cannot inherit it. No reconnect, reattach, restart, state restore,
generation import or uncertain mutation retry. Unsafe backend/target relation
returns unresolved rather than inventing continuity.

Workspace owner supplies fresh unpredictable 32-byte challenges, strict
increasing sequence, operation/purpose, request/operation IDs and original
generations. Verify and consume each response once. Non-null request challenge
is still limited to the three OBSERVE operations. Mutation poststate uses the
separate single-use spent-admission reference exactly as frozen; it never
substitutes for a fresh readiness observation.

One PID1 selector loop owns active operation ID, exclusive handoff identity,
used IDs, deadlines and monotonic cleanup barrier. At most one mutation or
handoff exists; observations require quiescent same-generation state and full
writer/task/mount evidence. Preparation/workspace owners validate and spend
their own permissions. The fixed adapter validates original admission before
forwarding; a scalar ID is not authority. Controller checks local predicates,
issues no permissions and spends no facets. There is no cross-owner atomicity
or private lock bridge: an unobservable admission-to-effect gap aborts unresolved.

Cleanup input, disconnect, timeout or invalidity installs the barrier first,
withdraws readiness, cancels reservation/operation, then terminates/reaps and
reports. After barrier no new preparation, handoff or readiness observation.
Materialization and compile remain in this same controller generation.

## Child ownership, lifetime and cleanup

Only PREP's exact scenario javac argv is selected, copied without flag changes
in `selection.json:child_process`, with exact cwd `/work`, environment,
compiler hash and DEVNULL stdin. Launch one child with shell=false and a new
session/process group. PID1 retains stdout/stderr ownership and adopts orphaned
group children. Integrate child pipes/status and stdin cleanup control in one
nonblocking selector; existing blocking capture is a pattern only.

One host-monotonic preparation admission deadline gives materialization and
compile a shared 5000ms, with 10000ms hard preparation bound. Neither resets
at compile. Group kill, direct-child wait, adopted group reap, complete EOF and
capture closure fit inside the original hard deadline. Both child streams cap
at 2048 bytes and must be empty on success. Prove group/task/writer absence,
unchanged source and exact bounded inert class output; no target JVM or class
loading. Controller stays alive after successful preparation. Source analysis
supports these syscalls under the current policy/resources; future live checks
must fail rather than widen if they cannot satisfy the bounds.

**Retained total lifetime is 30000ms from host monotonic time immediately before
first create attempt.** Work/readiness/reservation stop by 20000ms, reserving
10000ms for cleanup. Require a complete remaining hard preparation window before
admission. This small foreground envelope allows creation/observation and one
preparation/handoff opportunity; it is not a service or indefinite ready lease.
No renewal. A synchronous foreground host reactor spans creation to cleanup,
so idle deadlines are serviced without background workers or a detached live
capability. Inner startup watchdog bounds disconnected execution to <=30s from
actual inner start; after total host loss that may extend past the host's
creation-origin total. It grants no readiness and proves neither synchronized
deadlines nor physical absence by host deadline. Completion, abandonment,
upstream loss or timeout starts cleanup earlier. At expiry withdraw readiness,
cancel operation/handoff and clean. Failed removal remains terminal
WORKSPACE_CLEANUP_UNRESOLVED, not a renewed lease or a fabricated absence.

EOF/attach failure immediately invalidates host state. Docker disconnect does
not guarantee immediate inner stdin EOF; the outer custodian removes the exact
generation independently, and the inner watchdog bounds disconnected execution.
The custodian retains the authenticated original full 64-hex container ID,
creation/backend/generation relation **before start**. It exposes only the
frozen TERMINATE_REMOVE_EXACT_RETAINED_GENERATION and
OBSERVE_EXACT_RETAINED_GENERATION_ABSENCE, using fixed full-ID kill/remove and
separate inspect absence. Never names, caller targets, generic Docker args,
or readiness/upstream/inner-channel prerequisites. Lost create reply or unsafe
backend continuity leaves targeting unresolved; do not guess. A nonzero inspect
or connection error is not absence. Full host loss has no magically durable
in-memory issuer; watchdog is not removal evidence.

The logical controller includes the host adapter. Inner CLEANUP_AND_REPORT
can return bounded partial evidence only, with frozen PROOF_UNRESOLVED until
outer evidence exists. The adapter retains that response and separately composes
the public in-process result from inner evidence and custodian removal/absence.
This is not a second inner wire reply or a claim that inner removed itself.
Preserve component provenance and originating errors; lost child wait/EOF
evidence stays unresolved even after verified container absence.

## Future implementation and remaining fields

Three additive modules are required: fixed controller source/protocol,
host fixed controller adapter, and independent outer cleanup custodian.
Workspace and preparation owners remain separate. Source/executable identity,
actual argv fit, original-object authentication/admission, live observation,
capture/aggregate frame fit and safe backend cleanup targeting need future
implementation/validation. Consumer/harness/borrower authentication and activation
remain deferred; handoff is only exclusive reservation with PROOF_UNRESOLVED
activation. **No SANDBOX.2 widening is identified for candidate A's primitives.**
This does not establish a fully compliant selected architecture.

Two selection blockers remain substantive, beyond unknown implementation bytes:

1. **Independent backend-generation cleanup binding.** Existing provenance
   explicitly has no owner-defined continuity mechanism. A retained inner
   channel cannot authenticate the outer custodian after that channel is lost.
   Full-ID targeting plus endpoint/version equality is insufficient. The
   proposed custodian's requirement for a provable original backend relation
   specifies a necessary predicate, but supplies no concrete mechanism. No
   candidate satisfies the independent cleanup selection criterion yet.
2. **Aggregate capture feasibility.** The complete canonical materialize and
   compile records repeat substantial workspace/kernel/writer metadata. A
   fresh prepared observation is also required before readiness/handoff.
   [sizing_witness.json](sizing_witness.json) records optimistic synthetic
   sizes: **8096 bytes** for materialize+compile, with only **96 bytes** spare;
   **11520 bytes** including fresh prepared observation. These use one-character
   kernel IDs/minimum class size and are not live observations or capabilities.
   The unchanged 8192-byte
   cumulative preparation cap needs an explicit, faithful attempt/lifecycle
   allocation and truthful complete identity encoding proved to fit. Merely
   promising to fail on overflow is not success feasibility. Do not reset the
   cap, omit required records, invent aliases or exclude an observation by
   silently redefining attempt. The sizing is not a proof that every possible
   encoding is impossible; requirement evolution is not presumed.

These prevent the COMPLETE outcome. The historical contract, message schema,
workspace/PREP closure and sandbox are unchanged. No candidate is accepted as
the least-bad option and no network, mount or generic execution alternative
is introduced to hide the gaps.

## Measured pure validation

- Focused selection tests: 17/17 passed.
- Registry/picker: 292/299 before and after; identical projections and 7 existing failures.
- Benchmark --check: 54 cases, 0 errors.
- In-memory compilation: 1360 Python files; JSON, whitespace and Git checks passed.
- Whole prior non-cache workspace: 26856 files unchanged, no outside-phase additions.

Existing failures (exact raw diagnostics retained in registry baseline/after JSON):

- `tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation`
- `tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets`
- `tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked`
- `tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call`
- `tests/test_phase_registry.py::test_seed_registry_has_expected_phases`
- `tests/test_phase_registry.py::test_seed_registry_is_conservative`
- `tests/test_phase_registry.py::test_seed_registry_summary_counts`

Required checks are detailed in [validation_summary.json](validation_summary.json)
and raw evidence beside it. Registry/picker baseline failures were preserved,
without repairing historical tests. All guarded modes had zero process,
network, capability import/issuance/transition, execution/verification and
outside-phase-write attempts. Read-only Git checks are separately identified.
No Docker, javac/java, materialization, runtime/reflection or capability effects.
STOP after selection; do not implement controller source.
