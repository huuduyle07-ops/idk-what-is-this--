# Historical kernel identity source audit

Recommendation: **KERNEL_IDENTITY_CONTRACT_UNRESOLVED** on historical source evidence alone. This audit supports raw namespace preservation and full stat-mode metadata; it does not claim a completed normative encoding contract.

Read source bytes and frozen JSON/text only; line-anchored source reasoning. No owner module imported or executed, no live kernel or target filesystem observations, no network.

## Evidence and inference

- **namespaces.user,mnt,net,pid,ipc,cgroup,uts** (direct_source_evidence): Raw readlink text and raw cgroup text comparison are historical conventions. Individual namespace raw preservation is supported; source does not validate a canonical decimal grammar or establish an inode digit maximum.
- **namespace_encoding** (contract_design_inference): A new strict lowercase ASCII kind:[canonical decimal] grammar can preserve the conventional observation directly, with no whitespace/normalization alias. Treat this as an explicit new serialization choice, not a historical validator. No finite semantic inode width is pinned by the reviewed sources.
- **cgroup_identity** (direct_source_evidence): Historical open(...).read() preserves text without explicit trim but is text-mode I/O; it is not proof of a newly frozen exact-byte preimage. Namespace cgroup inode and cgroup membership text are distinct facts.
- **mode** (contract_design_inference): Freeze full int(st_mode) consistently for observed entry/root metadata, because observation checks file kind and metadata. Permissions-only S_IMODE is source-supported for restoration only. Do not accept both encodings or infer an unpinned narrow maximum.
- **mount_identity,namespace_generation,root_identity** (contract_design_inference): Mount ID or device/inode equality alone does not prove incarnation continuity. Bind projection to authenticated actual namespace/container/workspace/controller generation and coherent original mount/root relation. Existing containment permits future conditional continuity reasoning but does not provide its implemented observer. No new held descriptor, hidden counter or lifetime mechanism is established by this audit.
- **controller_process_identity,writer.process_identity,writer.task_identity,process.start_identity,task.start_identity,process_group_identity** (contract_design_inference): PID/TID/PGID alone is insufficient. Distinguish whole incarnation projection from starttime component and bind PID namespace plus outer generation. Historical source does not already serialize process/task starttime. Child new-session precedent supports group leader binding only.
- **namespace_identity** (contract_design_inference): Distinct aggregate role requires an explicit purposeful canonical seven-observation tuple/digest preimage or remains underspecified. Concatenation or duplicate alias is not supplied by historical source.
- **writer_handle.descriptor_identity** (contract_design_inference): Use disjoint actual-fd and potential-relation tags only after each relation is defined. A numeric fd slot must be bound to writer incarnation and current coherent observation; it does not identify a durable open-file-description incarnation. Potential access is an interpreted relation, not a kernel fd. If defining that relation requires deciding forbidden potential-access semantics, keep this scalar unresolved.
- **finite_width** (direct_contract_evidence): Accepted integer width is at most 19 digits by the existing schema, accepted ID UTF-8 width is at most 256, and subordinate_mount_count serializes as 0. Neither acceptance cap proves all valid kernel facts have finite semantic widths within it; unrepresentable data must fail closed without truncation or budget-only hashing.
- **missing_historical_primitives** (audit_limit): Reviewed source text contains no mountinfo, fdinfo or process/task stat-starttime observer. Capability-owner issuing PID checks and source hashes must not be relabeled as kernel incarnation identities.

## Exact audited source inventory

SHA-256 values cover current exact source-file bytes. They record this audit input and do not repin or reissue historical evidence. All six mandatory sources and the union of exact core sources in both frozen evidence indexes are included, plus the historical capture helper.

### core/sandboxed_java_positive_probe.py

- SHA-256: `d62e7ab3082f728d77bdfcfde91b5f62f11a6b8a2945b8a8c96fb5c97e3c654f`
- Bytes: 7358; lines: 126; mandatory: true.
- Lines 22-25: boundary(pid) returns os.readlink namespace text for user,mnt,net,pid,ipc,cgroup,uts and open(.../cgroup).read() text with no explicit strip or normalization.
- Lines 27-39: Controller uid/gid/PID/task counts, capability status text, resource strings and statvfs writability are historical boundary evidence; /proc/self/status is not /proc/PID/stat starttime.
- Lines 41-55: lstat mode classifies file/directory/other. This historical manifest does not serialize full root or entry stat identity.

### core/sandbox_backend_provenance.py

- SHA-256: `42e18b86556118ba67f5a62f913e27c5598321af83a7b35c84b89042737da3b8`
- Bytes: 12132; lines: 217; mandatory: true.
- Lines 86-100: Freshness assessment explicitly denies that authenticated snapshots, timestamps, endpoint equality or repeated version equality establish backend replacement/ABA resistance.

### core/direct_read_receipt.py

- SHA-256: `0ae7b33ed3273f978e6edb540f551365f255bd0513463f0e79b0a6aff2e0c1ad`
- Bytes: 17813; lines: 454; mandatory: true.
- Lines 42-69: DirectReadFileIdentity stores device/inode/full mode and rejects bool/noninteger/negative metadata; no narrow Linux ABI width is established.
- Lines 91-98: from_stat_result projects int(st_dev), int(st_ino), int(st_mode), size and timestamps.
- Lines 397-420: Freshness compares device/inode/mode and checks S_ISREG(full mode); full mode carries file type, unlike S_IMODE restoration permissions.

### core/repository_inventory.py

- SHA-256: `14e7c93df03f0881bf8abdf8301a0308b9265f4a03398e845452863154a789b0`
- Bytes: 21634; lines: 653; mandatory: true.
- Lines 28-49: RepositoryFileIdentity is descriptor-comparable inventory metadata and captures device/inode/int(st_mode), size and timestamps. It is not an observed namespace or mount-incarnation primitive.

### core/undo_backup.py

- SHA-256: `1c5c6cd16f00dd08c56232e30fc4d378c178a996dd8820dedf19c3b4e9b17050`
- Bytes: 11338; lines: 230; mandatory: true.
- Lines 105-115: Atomic restoration extracts stat.S_IMODE(st_mode) and applies it with chmod; this is permissions restoration, a different purpose from observation metadata.

### core/failed_rollback_recovery.py

- SHA-256: `7ff20ce943df6d4f45e625530b82da32e15ee027237a5bb3213e80b1f9ebcf19`
- Bytes: 13568; lines: 345; mandatory: true.
- Lines 136-148: Recovery baseline_mode admits exact int 0..0o7777 or None. This bounds restoration permissions, not full observed st_mode.

### core/candidate_runtime_sandbox.py

- SHA-256: `ebe409e7e798ec1e8f48c4bd2c49e5cd8b282906251f7c2c38c2933d1ef51913`
- Bytes: 34833; lines: 665; mandatory: false.
- Lines 51-58: Frozen syscall denial list includes unshare,setns,mount,umount2 and other privileged mechanisms; source evidence supports conditional containment constraints.
- Lines 419-436: Independent prelaunch configuration predicate checks private PID/cgroup settings, IPC none, no binds/mounts, dropped capabilities, frozen UID/GID, resources and environment. Configuration equality is not an observed mount-incarnation identity.

### core/thread_compatible_runtime_sandbox.py

- SHA-256: `8eea18d16c330dc7d116065ac9d23833bb2a0af58448b02438c26526141b1d45`
- Bytes: 22400; lines: 382; mandatory: false.
- Lines 226-235: Thread containment assessment compares raw namespace dictionaries and cgroup text before/during/after, verifies distinct TID/PID, and rejects changes. No starttime-based task identity is constructed.

### core/sandbox_backend_binding.py

- SHA-256: `202cd1190494beaaf24874ac798b89a8eac276fa8361b496663a573770cdf1ed`
- Bytes: 26216; lines: 469; mandatory: false.
- Lines 138-175: Attachment validation requires exact retained original, issuing process, signature/projection and route/version bracket equality while daemon identity/continuity/ABA flags remain false. Issuing PID is local capability-owner provenance, not observed process incarnation.

### core/runtime_java_pinned_provider.py

- SHA-256: `bca4a46363a27e23fba60cbc556eb30e3f2b6e03f4ed6e95c81ac7231756ddaa`
- Bytes: 42111; lines: 687; mandatory: false.
- Lines 341-437: Runtime evidence binds authenticated provider/runtime observations and frozen controller identity/configuration. It does not add mountinfo, process stat starttime or fdinfo observation primitives.
- Lines 445-456: Owned attachment authentication checks retained original and current issuing process. This capability authentication must remain distinct from a nonsecret kernel projection.

### core/runtime_java_pinned_requirement.py

- SHA-256: `2f070084b7a62a46bce33cd5dcdf0a06236bfdcc21d5d82ed508ff4b961b8af1`
- Bytes: 22597; lines: 293; mandatory: false.
- Lines 93-98: Frozen requirements specify private namespaces/cgroup, controller PID1/UIDGID65534, matching seven observed boundaries, bounded resources, fixed mounts and capture limits; no kernel ABI digit widths are frozen.

### core/runtime_java_pinned_backend_target_binding.py

- SHA-256: `94c95d674c0b43cde5811762998d13a65c3eee71c442cf05ff8699e02ec59da9`
- Bytes: 34173; lines: 561; mandatory: false.
- Lines 277-309: Validator authenticates exact current-process original binding and all original upstream objects/signature/evidence. This owner graph does not supply observed process/task or mount incarnations.

### core/runtime_java_pinned_target_inspection.py

- SHA-256: `dd65d5731486e0a4d92e858d7d3c3853eba6d6377b0884f988fcf0641bec6e59`
- Bytes: 28903; lines: 521; mandatory: false.
- Lines 141-156: Receipt validation requires original live registry object, current issuing PID and authenticated canonical evidence.
- Lines 382-385: Controller source identity is explicitly frozen-controller-source metadata only. The accessor is read as source here and is never called by this audit.

### core/sandboxed_java_positive_continuation.py

- SHA-256: `ec0f7a7a210fabca4d3df58323072829392bc3fcdb5b41213f5d56750af09f7f`
- Bytes: 28167; lines: 462; mandatory: false.
- Lines 123-157: Historical evaluator requires controller PID1/UIDGID65534, one Python/OS task, unchanged raw boundary, exact namespace key set and equal child boundary. These are historical observations, not a retained live workspace or new observer implementation.

### core/synthetic_runtime_authorization_pinned.py

- SHA-256: `c216aaba910b5907d754f51358f1fca4ba4c77bfd38692de7cc192b5e263516c`
- Bytes: 24720; lines: 445; mandatory: false.
- Lines 261-288: Authorization validator requires issuing process and exact original authorization/provider graph plus independent process-local HMAC. Exported scalar observations cannot replace these originals or grant authority.

### core/synthetic_runtime_authorization_pinned_lifecycle.py

- SHA-256: `235f630b6e888e55b0fae1fda7699c4a962c0f003feb0bf08e7885c91d63e3c4`
- Bytes: 25692; lines: 497; mandatory: false.
- Lines 130-140: Local lock access checks issuing process and original issuing PID. This is process-local owner provenance and supplies no /proc starttime incarnation serialization.

### core/java_single_thread_capture.py

- SHA-256: `4ac691b2919b3e778a98c044fb166fd9804b102cdd651995eb8689839ac438fb`
- Bytes: 6312; lines: 135; mandatory: false.
- Lines 28-32: Fixed child starts with start_new_session=True and its PID is retained/callback-observed.
- Lines 64-99: Cleanup addresses the phase child group with child.pid, waits/reaps, and checks group survival. This supports leader/child binding context but does not make PGID durable or observe leader starttime.

## Frozen contract references

### docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/evidence_index.json

- SHA-256: `2db38cb014750909877f99e0e233e71942f30472f9baae755673df0347a35054`; bytes: 39072; lines: 1329.
- Lines 3: Exact historical core source reference list used for this audit.

### docs/roadmap/phases/SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/evidence_index.json

- SHA-256: `2765a37d963f9ff0430f583e31c750d78e6e551f7644eefc2a1ff83afb1b9815`; bytes: 33928; lines: 972.
- Lines 3: Exact historical core source reference list used for this audit.

### docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json

- SHA-256: `1c40559d4a48b747632ec4e75b49eaeae33bad9ed63fa7cbd5b19337d840406e`; bytes: 30969; lines: 1034.
- Lines 13-17: Existing ID envelope admits 1..256 UTF-8 bytes; this is not a semantic kernel digit-width guarantee.
- Lines 28-38: Existing uint/positive_int fields admit up to 9223372036854775807: maximum accepted decimal width 19; bool excluded.
- Lines 159-171: Exact seven namespace fields are required.
- Lines 210-238: Separate mount identity, namespace generation, root identity and root metadata; subordinate_mount_count is the sole allowed value 0.
- Lines 287-303: writer_handle explicitly permits both potential_write_access and open_writable_handle; serialization must distinguish synthetic relation from actual descriptor.
- Lines 1024-1027: Complete no-cross-mount/writer observations, fixed read-only kernel scope and capture rules remain unchanged.

### docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/contract.json

- SHA-256: `98569ab0083cab8269e75ef5a5b00f2758ac33e61ef7ab77ab56d5760542a328`; bytes: 61888; lines: 1146.
- Lines 536-554: Mount/root and complete manifest/process/writer observations are generation-bound metadata; state digest alone does not authenticate readiness.
- Lines 748-752: Local observation fence requires coherent current generations; read-only inventory is not an external writer lock.

### docs/roadmap/phases/SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/contract.json

- SHA-256: `259f3e60a9f33677a335cb6f309b5b89a4f60d7321a2dc623dff186fd98a692d`; bytes: 44595; lines: 664.
- Lines 287-307: Mount/root and descriptor-relative no-follow metadata scope, original identities and outer authenticated current state remain required.
- Lines 466-473: Loss/replacement invalidates the generation; equivalent names, image, paths or manifest do not repair original relations.

## Preserved boundaries

- exact mount/root incarnation serialization and continuity proof
- namespace_generation alias/continuity semantics
- aggregate namespace identity role
- process/task/start/group exact canonical projections
- cgroup exact canonical text/byte preimage choice
- actual descriptor versus potential-access relation projection
- WRITER_INVENTORY_COMPLETENESS_UNRESOLVED

All listed authority flags are false and all listed runtime/operational effects are zero. No owner was imported, no observer/controller executed, no live kernel fact sampled, and no network used. Audit and artifact generation only. The two requested audit document writes are not scenario/runtime effects. Existing historical source/contracts are read-only.
