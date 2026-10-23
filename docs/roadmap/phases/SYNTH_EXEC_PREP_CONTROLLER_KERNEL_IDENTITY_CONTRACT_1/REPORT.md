# Kernel observation identity and metadata serialization

**KERNEL_IDENTITY_CONTRACT_UNRESOLVED**. This additive partial contract freezes supported observation projections and numeric meanings. It cannot truthfully freeze every requested exact incarnation encoding from the available evidence. No requirement evolution is performed or proven necessary. No observer or writer inventory is implemented.

`raw kernel fact != serialized field projection != authenticated workspace state != authority`.

Every projection belongs to one exact original authenticated container/workspace/controller generation and coherent current observation. Equality alone does not prove continuity, freshness, original-object authenticity, eligibility or authority. A copied `/proc` string is never a bearer credential. Current readiness still requires the unchanged owner registry/HMAC, original objects, observation challenge/sequence, admission fence and terminal rules. An unproved relation fails `PROOF_UNRESOLVED` before effects.

The source audit covers all six mandatory files, the exact core-source union referenced by both frozen controller/workspace evidence indexes, and the historical child capture helper. See [source_audit.md](source_audit.md) for exact hashes and line anchors. Historical convention is evidence, not an automatic new requirement. No capability owner was imported.

## Field-by-field decisions

| Field | Raw fact and serialized projection | Decision and binding |
|---|---|---|
| `mount_identity` | Candidate mountinfo ID with mount namespace and exact retained mount relation | Unresolved. Mount ID alone is reusable. `/tmp` and `/work` must be distinct exact mounts, including writer references. Parent ID supports topology checks; major:minor, paths and filesystem kind do not prove incarnation. No decorative tuple or digest is selected. |
| `namespace_generation` | Candidate alias of `namespaces.mnt` plus independently authenticated continuity | Unresolved. Alias purpose is intelligible but equality does not prevent stale reuse after unobserved replacement. No timestamp, PID, container name or hidden counter. |
| `root_identity` | Candidate no-follow `st_dev`, `st_ino`, file type, exact mount and generation | Unresolved. Device/inode reuse and mount binding need retained relation proof. Root metadata remains separate. |
| `controller_process_identity` | Candidate PID, process starttime, active PID namespace and original generation | Unresolved. PID alone fails; tick quantization/reuse and coherent lifetime binding are not discharged by a tuple. |
| `namespace_identity` | SHA256 of exact ordered seven-value namespace tuple | Frozen equality projection; purposeful aggregate over all seven components. Raw fields remain separately interpretable. No authentication or continuity claim. |
| `namespaces.user` | `user:[<D>]` | Frozen raw observation grammar. |
| `namespaces.mnt` | `mnt:[<D>]` | Frozen raw observation grammar; not implicitly a generation counter. |
| `namespaces.net` | `net:[<D>]` | Frozen raw observation grammar. |
| `namespaces.pid` | `pid:[<D>]` | Frozen raw observation grammar; active namespace, not `pid_for_children`. |
| `namespaces.ipc` | `ipc:[<D>]` | Frozen raw observation grammar. |
| `namespaces.cgroup` | `cgroup:[<D>]` | Frozen raw observation grammar. |
| `namespaces.uts` | `uts:[<D>]` | Frozen raw observation grammar. |
| `cgroup_identity` | SHA256 of exact complete membership-listing bytes with domain and length | Frozen membership observation equality projection; not durable cgroup-object identity after path reuse. |
| `process.start_identity` | Canonical decimal text of process stat field 22 starttime ticks | Frozen fact projection. Enclosing process/PID namespace/generation supplies context. Distinct from full process identity. |
| `task.start_identity` | Canonical decimal text of that task's own stat field 22 | Frozen fact projection. Never copy the process leader's ticks; enclosing original process and TID supply context. |
| `process_group_identity` | Candidate observed PGID plus exact admitted child/leader incarnation, operation and generation | Unresolved. Historical `start_new_session=True` supports child-as-leader selection, not indefinite PGID identity. Must retain the group relation through leader exit/reaping. |
| `writer.process_identity` | Same original process projection referenced by controller/process inventory | Unresolved with the process encoding. This is a join with a distinct role, not a newly minted ID. |
| `writer.task_identity` | Exact inventoried task incarnation within its original process | Unresolved. Start ticks or TID alone do not identify that relation. |
| `writer_handle.descriptor_identity` | Actual writable FD or synthetic potential-access relation, selected by existing `access_kind` | Unresolved. Numeric FD slot, file-table sharing and close/reopen need coherent observed binding. Potential access has no FD; its semantics remain outside this phase. No incomplete tagged grammar is declared frozen. |

For every family, [contract.json](contract.json) records the direct/raw, structured and digest alternatives and the reason for adoption or deferral. Digesting incomplete facts does not repair an incarnation proof. There is no default SHA256 conversion, random token or HMAC substitution.

## Exact settled projections

For namespace values, `<D>` is `0|[1-9][0-9]*`: exact ASCII decimal, no sign or leading zeros. Kind is the exact lowercase field kind; colon and square brackets are literal. Reject whitespace, aliases, alternate case and non-ASCII; never normalize them. The scalar is an exact built-in string encoded through the unchanged canonical JSON encoder. The seven-field order is `user,mnt,net,pid,ipc,cgroup,uts`.

`namespace_identity` is 64 lowercase hex digits of SHA256 over:

```text
ASCII("CATTUS:SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.1:namespace-tuple:v1")
+ NUL
+ canonical_JSON([user,mnt,net,pid,ipc,cgroup,uts])
```

The list contains the exact validated namespace strings. JSON uses `ensure_ascii=true`, `sort_keys=true`, separators `(',', ':')`, `allow_nan=false`, ASCII bytes and no trailing newline. No dictionary, extra context or convenient concatenation is added. Outer generations are independently authenticated state bindings. This aggregate supports equality of the entire observed namespace relation; it does not duplicate any one component.

`cgroup_identity` is 64 lowercase hex digits of SHA256 over:

```text
ASCII("CATTUS:SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.1:cgroup-raw:v1")
+ NUL
+ uint64_big_endian(len(raw_bytes))
+ raw_bytes
```

Raw bytes mean the complete exact observed listing: no trimming, decode/re-encode, newline conversion, line sorting or parsed normalization. Historical Python text reads establish the source convention, not byte-exact acquisition; this new preimage is explicitly additive. Reject incomplete reads or length outside the representable range. The length prefix is unambiguous, not a new practical observer-read budget. Raw listing width has no source-pinned semantic maximum; future bounded complete acquisition remains unproved. Equality consumers use the projection while exact source observations remain retained and authenticated separately. Raw component comparisons remain necessary wherever exact equality is required; hash collision resistance supplies no authority or continuity.

Process and task `start_identity` use `<D>` as a JSON string of boot clock ticks, not a timestamp or an integer metadata field. No native tick width, frequency, boot-ID projection, wrap semantics or reuse interval is pinned. Correct field-22 parsing and same-observation binding remain future obligations: comm may contain spaces and parentheses, so a naive whole-line split is insufficient.

## Numeric metadata and finite widths

All numeric fields are exact built-in integers: reject bool, floats and coercion. Canonical JSON decimal has no quotes, leading zeros, exponent, octal or redundant sign. These are metadata facts and never identity substitutes.

| Field | Exact meaning | Minimum / accepted maximum decimal bytes |
|---|---|---:|
| `mode` | Full `int(st_mode)`, including file type and special/permission bits; verify type against regular-file/directory kind | 5 / 19 safe schema envelope |
| `uid` | Observed numeric owner UID in authenticated observer user-namespace view | 1 / 19 |
| `gid` | Observed numeric owner GID in that same view | 1 / 19 |
| `link_count` | Actual `st_nlink`; regular allowed files must be 1; directory count is observed | 1 / 19 |
| `pid` | Observed process ID in the fixed observer procfs PID-numbering view | 1 / 19 |
| `parent_pid` | Observed parent ID in that view, including zero at namespace boundary | 1 / 19 |
| `tid` | Observed task ID in that view and enclosing original process | 1 / 19 |
| `child_pid` | Exact admitted compiler child ID retained through capture/reaping | 1 / 19 |
| `subordinate_mount_count` | Complete count under each exact root; accepted state is exactly integer 0 | 1 / 1 |

UID/GID/parent PID are nonnegative; link count and PID/TID/child PID are positive. The unchanged schema caps unsigned/positive integers at `9223372036854775807`. This guarantees accepted numeric width, not a native Linux ABI or completeness of unrepresentable facts. Full allowed regular/directory mode type bits require five decimal digits. No narrow native maximum is claimed; 19 is a conservative existing admission ceiling. `issuing_pid`, though outside the requested new-field family, stays the same existing positive-integer ledger term.

Full mode follows observation precedents in `direct_read_receipt.py` and `repository_inventory.py`. `undo_backup.py` uses permissions-only `S_IMODE` for chmod restoration, and `failed_rollback_recovery.py` validates that restoration range. Restoration purpose does not define observation metadata. Both mode interpretations are never permitted interchangeably.

| Scalar family | Minimum content / quoted JSON bytes | Maximum semantic width | Admitted wire ceiling |
|---|---:|---|---|
| `namespaces.user` | 8 / 10 | No inode digit bound established | 256 / 258 ASCII bytes |
| `namespaces.mnt` | 7 / 9 | Not established | 256 / 258 |
| `namespaces.net` | 7 / 9 | Not established | 256 / 258 |
| `namespaces.pid` | 7 / 9 | Not established | 256 / 258 |
| `namespaces.ipc` | 7 / 9 | Not established | 256 / 258 |
| `namespaces.cgroup` | 10 / 12 | Not established | 256 / 258 |
| `namespaces.uts` | 7 / 9 | Not established | 256 / 258 |
| `namespace_identity` | 64 / 66 | Exactly 64 projection bytes | 64 / 66 |
| `cgroup_identity` | 64 / 66 | Exactly 64 projection bytes; raw preimage maximum unestablished | 64 / 66 |
| `process.start_identity` | 1 / 3 | No native tick digit bound established | 256 / 258 ASCII bytes |
| `task.start_identity` | 1 / 3 | No native tick digit bound established | 256 / 258 ASCII bytes |
| `mount_identity` | Unestablished | Unresolved grammar/incarnation | Existing generic ID ceiling only |
| `namespace_generation` | Unestablished | Unresolved grammar/incarnation | Existing generic ID ceiling only |
| `root_identity` | Unestablished | Unresolved grammar/incarnation | Existing generic ID ceiling only |
| `controller_process_identity` | Unestablished | Unresolved grammar/incarnation | Existing generic ID ceiling only |
| `writer.process_identity` | Unestablished | Unresolved grammar/incarnation | Existing generic ID ceiling only |
| `writer.task_identity` | Unestablished | Unresolved grammar/incarnation | Existing generic ID ceiling only |
| `process_group_identity` | Unestablished | Unresolved grammar/incarnation | Existing generic ID ceiling only |
| `writer_handle.descriptor_identity` | Unestablished | Unresolved per-kind semantics | Existing generic ID ceiling only |

Namespace/start minima are grammar bounds, not jointly attainable kernel assignments. One-digit namespace inodes are not claimed to occur on the pinned image. For unknown generic IDs, the existing 256 UTF-8 byte admission ceiling can expand to 1536 canonical JSON content bytes, plus two quotes; it is not an accepted grammar or a truthful value. Oversized direct observations fail incomplete; they are never truncated or silently hashed. See [finite_width.json](finite_width.json) for every row and its evidence basis.

## Read-only symbolic budget substitution

Only frozen `BUDGET.PROOF.1R` JSON ledger widths are read and substituted. The historical proof is not imported, executed, edited or repinned. The owner contract's 17-content-byte / 19-JSON-byte handles remain unchanged. Lower topology remains one accounted controller writer with two potential-root handles per response; this does not decide completeness. Class-size maximum width stays five decimal digits in both locations. Container/workspace/controller-generation assumptions stay conditional and unchanged. Request bytes are not added to Candidate-A stdout.

| Quantity | Conditional partial lower subtotal |
|---|---:|
| Materialize response | `3567 + R_M` |
| Compile response | `5254 + R_C` |
| Semantic total | `8821 + R_M + R_C` |
| Candidate-A conditional framed total | `8829 + R_M + R_C` |
| Semantic margin versus 8192 | `-629 - R_M - R_C` |
| Conditional framed margin | `-637 - R_M - R_C` |

`R_M` and `R_C` independently sum every remaining path's actual canonical width minus its partial lower assignment, with exact occurrence counts. They include unresolved identities/numerics, namespace widths above grammar minima and any mode width beyond five. Sequence/post-sequence and observation-dependent widths can differ between operations, so these residuals must not be factored into one shared term. They are nonnegative relaxations, not authentic assigned values. Full exact response sizes remain **unestablished**. [budget_projection.json](budget_projection.json) records each path, source hash, delta and residual term; [budget_projection.py](budget_projection.py) reproduces only the substitution arithmetic.

The owner-substituted historical subtotals were 3379/4953. The new common delta is 188: namespaces +46, aggregate +63, cgroup +63, four modes +16. Compile additionally adds another namespace set +46, cgroup +63 and class mode +4. The semantic subtotal alone exceeds 8192 by 629 under these selected projections and conditional ledger assumptions, before framing or positive residuals. This is no universal transport-independent infeasibility claim about separate physical streams. Candidate A's +8 is conditional arithmetic only; Candidate A remains **UNSELECTED**. There is no requirement evolution or cap change.

## Remaining boundaries and validation

**WRITER_INVENTORY_COMPLETENESS_UNRESOLVED**. No writer count, descendant potential-access entries, per-path handle rules or umask/creation topology is decided. Borrower/handoff identities, owner IDs and workspace/controller generation encodings remain separate. Physical transport framing and stream mapping remain unselected. A future phase must provide the exact continuity-bearing relations and descriptor per-kind semantics before this partial contract can become a complete kernel identity contract.

Guarded validation runs focused synthetic contract tests, benchmark `--check`, registry/picker before-versus-after, source AST and in-memory Python compilation, JSON/whitespace/Git checks and whole non-cache historical preservation. Evidence lives in this additive folder; [validation_summary.json](validation_summary.json) records final counts and any preserved baseline failures.

All authority flags are **false**. All scenario/runtime operational effects are **zero**: no live `/proc`/namespace/target-stat sampling, Docker, runtime child probe, network, capability issuance, controller execution, Java compilation or source materialization. STOP after this contract report.
