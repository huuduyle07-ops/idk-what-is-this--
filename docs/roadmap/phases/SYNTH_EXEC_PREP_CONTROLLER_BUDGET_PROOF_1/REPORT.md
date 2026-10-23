# SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1

**AGGREGATE_BUDGET_SCOPE_UNRESOLVED**

The frozen contracts do not uniquely assign the mandatory new readiness observation to the cumulative preparation capture, or freeze the byte-counter endpoint. They therefore support outcome C. This proof does not claim FEASIBLE or IMPOSSIBLE, select a transport, or change a requirement.

## Decisive frozen wording

Controller `contract.json:486`, `/bounds/attempt_budget_scope`, states:

> One monotonic 5000ms deadline starts at materialization admission and includes materialize, compile, in-attempt observations and intervening time; never reset per operation. Outer preparation attempt hard timeout 10000ms. Total outer stdout/stderr each <=8192 over all attempt frames, not 8192 per unlimited frame. Retained lifetime is not this attempt budget and confers no indefinite readiness.

This defines a deadline origin and an unchanged cumulative cap. It does not define whether the byte interval ends at the compile response, owner receipt, fresh readiness observation, handoff, or teardown. The PREP closure separately calls this a fixed materialize-then-compile attempt and sets `cleanup_is_preparation=false`; those statements support conceptual separation but do not specify the outer byte-counter endpoint. No favorable exclusion is inferred.

Schema `cross_field_rules[1]` requires a new `OBSERVE_*` challenge before readiness or handoff. Mutation poststate is explicitly never current readiness. `OBSERVE_PREPARED_ARTIFACTS` already takes an original receipt ID and requires prepared artifacts from the preparation owner; it is not an explicit prerequisite to issuing that same initial receipt. `OBSERVE_CURRENT_WORKSPACE` can return a stage-appropriate prepared manifest, so the exact fresh tag is also not uniquely mandated. Both tags are sized.

All exact source quotes, JSON pointers and line references are in [lifecycle_audit.json](lifecycle_audit.json). [semantic_minima.json](semantic_minima.json) records field-category requirements and unknown encodings.

## Minimum lifecycle and cap membership

The mandatory pre-readiness sequence is current empty evidence, materialize with complete materialized poststate, compile with complete post-reap prepared poststate, preparation-owner receipt authentication, and a new challenged prepared-state observation. Embedded poststates are bytes of the enclosing mutation response; they are not extra frames. Receipt/HMAC/owner registry evidence has no additional controller wire envelope specified by the frozen schema.

| Message/evidence | Requirement | Cap classification |
| --- | --- | --- |
| OBSERVE_EMPTY_WORKSPACE | Initial current empty evidence required | UNRESOLVED_SCOPE |
| MATERIALIZE_EXACT_SCENARIO_SOURCE request/response | Required | MANDATORY_INSIDE_PREPARATION_CAP |
| materialization response.workspace_state | Complete record required, embedded | MANDATORY_INSIDE_PREPARATION_CAP |
| COMPILE_EXACT_SCENARIO request/response | Required | MANDATORY_INSIDE_PREPARATION_CAP |
| compilation response.workspace_state | Complete post-reap record required, embedded | MANDATORY_INSIDE_PREPARATION_CAP |
| new prepared-state OBSERVE_* | Required before readiness/handoff; current/prepared alternatives sized | UNRESOLVED_SCOPE |
| extra OBSERVE_CURRENT_WORKSPACE | Optional unless needed for mandatory current evidence | OPTIONAL; invoked-pair cap scope unresolved |
| PREPARE_EXCLUSIVE_HANDOFF | Optional later reservation; missing consumer/borrower contract prevents current successful admission | OPTIONAL; invoked-pair cap scope unresolved |
| BEGIN_CLEANUP | Eventual cleanup barrier duty required; may preempt an attempt | UNRESOLVED_SCOPE |
| CLEANUP_AND_REPORT | Eventual complete cleanup evidence required | UNRESOLVED_SCOPE |
| independent outer removal and absence | Required cleanup components | UNRESOLVED_SCOPE; independent outer channel |

No operation is assigned MANDATORY_BUT_OUTSIDE_PREPARATION_CAP without frozen byte-scope evidence. Separately bounded observations, retention and cleanup do not by themselves grant an exemption. Local pre-effect empty/source verification remains required; frozen text does not enumerate a distinct additional serialized pair for every local fence check. Additional required pairs would increase the totals.

## Formal bounds and their limits

No attainable semantic minimum or truthful successful lifecycle witness is established. Opaque original relation encodings, kernel identity formats, exact mode representation and actual javac class size/hash are not fully frozen. The proof records these as unresolved. It never turns a one-character ID or one-byte class into truthful evidence.

The canonical length probes give conservative inequalities by relaxing those unresolved values. Every mandatory key, fixed enum, source path/hash/239-byte size, compiler identity, success capture/reap field, required process/task/namespace/cgroup field, and both mount/root records remains. Unspecified nonempty strings have a lower bound of three JSON bytes including quotes, not an asserted attainable identity. Uncertain nullable IDs use the shorter three-byte probe rather than the four-byte `null`; schema mode0 and root link count1 only weaken the bound. Writer-free is a strict mathematical relaxation; a separate profile includes the controller and potential write access to both roots. These probes cannot prove feasibility.

The semantic contracts type generations as `id`; only unaccepted candidate A fixes workspace/controller generations to 32 random bytes encoded as64 hex. These cases remain separate. Full container identity is64 hex; challenges and SHA256 fields always retain64 hex. The controller process has at least PID1/TID1 in the smallest reviewed shape, seven namespaces, cgroup and UID/GID65534. No zero-process observation is used. The compiler is absent from completed snapshots because it is fully reaped; its child/group identity stays in capture/reap evidence.

| Profile | Mat+compile response payload | Same + fresh CURRENT payload | Candidate-A headers for three responses | Framed three-response stdout | Payload excess over8192 | Framed excess |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| frozen_semantic_relaxation | 6702 | 9423 | 12 | 9435 | 1231 | 1243 |
| candidate_a_relaxation | 7332 | 10368 | 12 | 10380 | 2176 | 2188 |
| candidate_a_controller_writer_relaxation | 8052 | 11450 | 12 | 11462 | 3258 | 3270 |
| stress_minimum_class_envelope | 9728 | 13812 | 12 | 13824 | 5620 | 5632 |
| stress_plausible_class | 9732 | 13818 | 12 | 13830 | 5626 | 5638 |

The universal relaxed materialize+compile response payload is6702 bytes, below8192. With a new qualifying CURRENT readiness observation it is9423 bytes, an excess of1231 before framing. Candidate A's generation-width relaxation gives10368 payload bytes plus12 header bytes =10380, an excess of2188. These excesses are **conditional on the fresh pair belonging to the preparation cap** and on response placement on the capped stdout channel. They do not prove the frozen requirement impossible without resolving that scope. The shorter two-response bounds do not prove existence.

The named PREPARED operation adds two response bytes relative to CURRENT (and additional request receipt fields). Candidate-A relaxed three-response stdout is10382 with that tag. The one-controller/two-handle relaxed profile gives8060 framed bytes for materialize+compile and11464 with PREPARED. These differ from the historical8096/11520 illustration because this proof weakens unresolved mode and nullable encodings further; no historical artifact is changed.

## Per-message canonical payload sizes

Rows are an operation-shape catalog in schema enum order, not a chronological authenticated execution. Every synthetic record is schema checked and marked `semantic_execution_witness=false`. Handoff rows do not invent an authenticated borrower. Cleanup rows represent a conditional logical composite, not an inner process reporting its own removal.

| Operation | Semantic relaxation request/response | Candidate-A relaxation request/response | Controller writer request/response | Stress class1 request/response | Stress class512 request/response |
| --- | ---: | ---: | ---: | ---: | ---: |
| OBSERVE_EMPTY_WORKSPACE | 490 / 2206 | 616 / 2521 | 616 / 2883 | 868 / 3557 | 868 / 3557 |
| OBSERVE_CURRENT_WORKSPACE | 494 / 2721 | 620 / 3036 | 620 / 3398 | 872 / 4084 | 872 / 4086 |
| OBSERVE_PREPARED_ARTIFACTS | 553 / 2723 | 679 / 3038 | 679 / 3400 | 1057 / 4086 | 1057 / 4088 |
| MATERIALIZE_EXACT_SCENARIO_SOURCE | 476 / 2576 | 602 / 2891 | 602 / 3251 | 917 / 3996 | 917 / 3996 |
| COMPILE_EXACT_SCENARIO | 454 / 4126 | 580 / 4441 | 580 / 4801 | 895 / 5732 | 895 / 5736 |
| PREPARE_EXCLUSIVE_HANDOFF | 530 / 1233 | 656 / 1485 | 656 / 1485 | 1097 / 1938 | 1097 / 1940 |
| BEGIN_CLEANUP | 434 / 501 | 560 / 627 | 560 / 627 | 812 / 816 | 812 / 816 |
| CLEANUP_AND_REPORT | 418 / 1810 | 544 / 2062 | 544 / 2063 | 796 / 2644 | 796 / 2644 |

Add exactly four bytes to each inner frame in its own direction. There is no magic or extra version prefix. Individual frame fit is recorded separately from aggregate fit.

## Direction totals

| Profile, mat+compile+fresh CURRENT | Request payload | Response payload | Both payloads (informational) | Request headers | Response headers | Controller stdout | Controller stderr |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| frozen_semantic_relaxation | 1424 | 9423 | 10847 | 12 | 12 | 9435 | 0 |
| candidate_a_relaxation | 1802 | 10368 | 12170 | 12 | 12 | 10380 | 0 |
| candidate_a_controller_writer_relaxation | 1802 | 11450 | 13252 | 12 | 12 | 11462 | 0 |
| stress_minimum_class_envelope | 2684 | 13812 | 16496 | 12 | 12 | 13824 | 0 |
| stress_plausible_class | 2684 | 13818 | 16502 | 12 | 12 | 13830 | 0 |

Under reviewed candidate A, requests use controller stdin and responses use controller stdout. Request bytes are not added to captured stdout or stderr. No independent cumulative8192 stdin limit is frozen; observation requests have an8192 per-request bound and candidate frames include headers within8192. The reviewed retained session separately has65536 bytes per direction and64 requests including cleanup, which does not relax the preparation cap. Successful controller stderr is empty. Raw successful compiler stdout/stderr are independently captured with2048 limits and each contain0 bytes; their exact hashes/EOF/closure/reap metadata is already counted once in the compile response. No raw source, class or capture bytes are inserted into semantic messages.

Independent outer-custodian requests/responses are cataloged with payload and subtree sizes under `outer_cleanup_messages`. Their transport framing is unselected; the inner four-byte u32be prefix is not silently assigned to that channel. Candidate cleanup composition is host-side in-process evidence after retained inner results, not another inner wire response.

## Field and subtree evidence

`budget_witness.json` contains each exact canonical payload string, declarative record, payload length, direction, candidate-A frame length, cap-scope reason, every field's byte contribution and every nested subtree length. Each ledger assigns object/array delimiters, key/colon bytes, commas and scalar tokens exactly once. Its summed `own_bytes` is checked against the actual canonical encoder. Subtree sizes are inclusive and are never summed again into the message total.

| Candidate-A relaxed response subtree | Materialize | Compile | Fresh CURRENT |
| --- | ---: | ---: | ---: |
| /result/workspace_state | 2118 | 2316 | 2316 |
| /result/workspace_state/mounts | 495 | 495 | 495 |
| /result/workspace_state/work_manifest | 320 | 522 | 522 |
| /result/workspace_state/process_exclusivity_observation | 654 | 654 | 654 |
| /result/compiler_identity | — | 712 | — |
| /result/capture_and_reap | — | 496 | — |
| /result/class_metadata | — | 255 | — |

Canonical encoding is the exact standard encoder: UTF-8, sorted keys, separators `(',', ':')`, ASCII escapes enabled, NaN forbidden, exact Python/schema types, exact list order, no whitespace or omitted nullable fields. There is no compression, binary alias, renamed key or custom serializer. The schema SHA256 is `1c40559d4a48b747632ec4e75b49eaeae33bad9ed63fa7cbd5b19337d840406e`.

## Stress profiles and Java class limits

Stress profiles use64-hex owner/relation tokens and generation strings, a full64-hex container ID, actual SHA256 computations for named synthetic inputs, and small illustrative PID/start/namespace/cgroup strings. Controller PID1 and compiler child7 are distinct. The hypothetical class envelope is either1 or512 bytes. Size512 is an illustrative plausible scale, never a measured minimum. Class1 is schema-envelope-only and cannot be successful javac output. Metadata size affects decimal tokens twice in the compile response and once in a later observation; raw class content is never counted.

The stress materialize+compile framed stdout values are9736 (class1) and9740 (class512); including fresh CURRENT yields13824 and13830. These show practical pressure but do not replace formal scope/semantic proof. Actual class content/hash and exact minimum Java output remain unresolved, so no infeasibility claim relies on predicting them.

## Result and unselected evolution candidates

The budget blocker remains unresolved. Transport selection remains TRANSPORT_SELECTION_UNRESOLVED, with its independent outer-backend-generation blocker also preserved. No architecture or persistent-stdio implementation is accepted. A scope clarification is necessary before the cap can be adjudicated; no specific numerical or schema evolution is proved unavoidable by this audit.

If the mandatory fresh observation is assigned to the cap and these complete responses use the same capped outer stream, even the weakened response-payload bound exceeds8192 before framing. Possible later evolution targets are: increase aggregate cap; separate protocol evidence from historical process capture; change mandatory duplication; change schema/projection; change attempt boundary. None is selected or modified here. All authority flags remain false and all operational effect counters remain zero. No controller, workspace, capability, Java compilation, process/network probe, kernel inspection, source materialization, runtime activation or reflection is performed.

## Reproduction and validation

Run with the workspace Python, from the repository root:

```text
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1/validate_pure.py --mode proof
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1/validate_pure.py --mode focused
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1/validate_pure.py --mode benchmark
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1/validate_pure.py --mode static
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1/write_report.py
```

The harness denies subprocess/process/network effects, capability-owner imports and writes outside this additive phase. Validation invokes pure pytest/benchmark entry points in the current interpreter, compiles source in memory and checks JSON/whitespace. Immutable preservation snapshots and registry/picker baseline/after comparisons are retained separately; never overwrite their original baselines.

Validation: 33 focused tests passed; benchmark --check passed all 54 cases. Registry/picker before and after each collected299:292 passed with the same7 existing failures; projections and failure signatures are preserved. Historical preservation compared26,893 non-cache files with zero changes/deletions/additions outside this new phase. In-memory compilation, JSON, whitespace and Git diff checks passed. All guarded operational counters are zero.

See [validation_summary.json](validation_summary.json) for exact evidence. Existing baseline failures are not repaired by this phase.
