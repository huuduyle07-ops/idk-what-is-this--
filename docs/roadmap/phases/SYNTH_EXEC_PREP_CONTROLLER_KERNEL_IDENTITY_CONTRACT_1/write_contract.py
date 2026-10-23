"""Write additive declarative artifacts from source reasoning; no observer code."""
from hashlib import sha256
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PHASE = "SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.CONTRACT.1"
ORDER = ["user", "mnt", "net", "pid", "ipc", "cgroup", "uts"]
DOMAIN = "CATTUS:SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.1:"
FROZEN = "OBSERVATION_PROJECTION_FROZEN"
UNRESOLVED = "INCARNATION_ENCODING_UNRESOLVED"


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def row(fields, fact, projection, role, status=UNRESOLVED, minimum=None, maximum=None):
    return dict(fields=fields, semantic_source=fact, canonical_representation=projection,
        semantic_role=role, status=status, minimum_content_bytes=minimum,
        maximum_semantic_content_bytes=maximum,
        finite_semantic_width_guaranteed=maximum is not None,
        admission="Existing id: 1..256 UTF-8 bytes, no NUL; reject unrepresentable evidence, never truncate.")


matrix = [
    row(["mount_identity"], "Mount namespace plus exact mount relation; mountinfo mount ID, parent ID, major:minor, root, mountpoint and filesystem kind are candidates, not historical observations.",
        None, "Exact /tmp or /work mount incarnation, also referenced by writer handles. Numeric mount ID is a reusable namespace-local relation, not standalone incarnation proof."),
    row(["namespace_generation"], "Mount namespace observation plus authenticated generation and continuity.", None,
        "Per-mount stale namespace replacement protection. A raw namespaces.mnt alias would identify the observed namespace but cannot alone prove nonreplacement across an unobserved gap; no alias or hidden counter is adopted."),
    row(["root_identity"], "No-follow root st_dev, st_ino, file type and exact mount relation, bound to current authenticated generation.", None,
        "Exact root object of each tmpfs mount. Device/inode may be reused; metadata mode/uid/gid/link_count are separate observations, not identity inputs. Root path or device equality does not establish no-cross-mount."),
    row(["controller_process_identity", "writer.process_identity"], "PID in observer PID-numbering view; process stat field 22 starttime; target active PID namespace; authenticated container/workspace/controller generation.", None,
        "Both fields must reference the SAME inventoried original controller process on the lower profile. A full process projection is distinct from start_identity alone. Tuple/digest choice deferred: a digest cannot repair noninjective facts or missing continuity."),
    row(["namespace_identity"], "All seven exact controller namespace observations in fixed order.", "64 lowercase hexadecimal SHA256 of the namespace preimage below.",
        "Aggregate equality key for the entire seven-namespace observation. Individual fields remain interpretable kernel facts. A changed component changes the preimage; digest equality alone is neither authentication nor namespace incarnation continuity.", FROZEN, 64, 64),
]
for kind in ORDER:
    matrix.append(row(["namespaces." + kind], "Exact os.readlink('/proc/<pid>/ns/" + kind + "') source convention.",
        kind + ":[<canonical unsigned decimal inode>]", "Namespace object-number observation in the exact authenticated current snapshot. Not a bearer credential or global generation ID.",
        FROZEN, len(kind) + 4))
matrix += [
    row(["cgroup_identity"], "Exact bytes of the complete /proc/<pid>/cgroup observation (historical source preserves file text; the new byte preimage is an explicit additive decision).",
        "64 lowercase hexadecimal SHA256 of the cgroup preimage below.",
        "Equality projection of the observed membership listing in its observation/PID/cgroup namespace context. Does not prove same underlying cgroup object after path reuse, rename, recreation or namespace replacement.", FROZEN, 64, 64),
    row(["process.start_identity"], "Field 22 starttime in /proc/<pid>/stat: elapsed boot clock ticks at process start, not wall time.",
        "Unsigned canonical decimal text: 0|[1-9][0-9]*; one JSON string, not a JSON integer.",
        "Exact starttime FACT only, scoped by enclosing pid, active PID namespace, original process and authenticated generation. Tick quantization is not proven collision-free; no PID+tick uniqueness claim.", FROZEN, 1),
    row(["task.start_identity"], "Field 22 of /proc/<pid>/task/<tid>/stat for that task; do not copy the leader's value.",
        "Unsigned canonical decimal text: 0|[1-9][0-9]*; one JSON string, not a JSON integer.",
        "Task's own starttime FACT, scoped by tid and enclosing original process/PID namespace/generation. Distinct role from writer.task_identity; no TID-only or tick-only incarnation assertion.", FROZEN, 1),
    row(["writer.task_identity"], "Enclosing original process relation plus exact task TID, task stat starttime and PID namespace in current generation.", None,
        "Join one writer record to its inventoried task incarnation; do not alias task.start_identity alone. Missing continuity proof is not solved by tuple concatenation."),
    row(["process_group_identity"], "Observed PGID, admitted compiler child and original leader process incarnation/start/PID namespace, bound to the same admitted operation and generation.", None,
        "Capture/reap evidence for the exact admitted child/group. Historical start_new_session makes child PID the group selector, but PGID alone or a recreated same-PGID group cannot be accepted. Preserve retained relation through leader exit/reaping; this phase issues no token."),
    row(["writer_handle.descriptor_identity"], "access_kind selects actual open_writable_handle or synthetic potential_write_access relation.", None,
        "Both kinds exist in the frozen schema. Actual FD requires exact process/task + observed descriptor slot + coherent observation/mount/object relation; close/reopen reuses a number. Potential access is not an FD and needs its independently defined relation semantics. No tagged grammar is frozen until both preimages are truthful; no record counts/topology/potential-access rules are decided."),
]

numerics = []
for field, minimum, meaning in [
    ("mode", 0, "Full int(st_mode), including file type, special and permission bits; never stat.S_IMODE. Check file type against kind, reject special files and links. Root must be directory. Metadata is not object identity."),
    ("uid", 0, "Observed numeric owner user ID in the observer's authenticated user-namespace view; no name lookup, host-ID inference or remapping."),
    ("gid", 0, "Observed numeric owner group ID in the same authenticated user-namespace view; no name lookup or inferred host ID."),
    ("link_count", 1, "Observed st_nlink; regular allowed files must equal 1. Directory counts are observed, not guessed as 2."),
    ("pid", 1, "Inventoried process ID in the fixed controller procfs/observer PID-numbering view (not an unlabelled host PID)."),
    ("parent_pid", 0, "Observed parent process ID in that same view; zero is permitted at the namespace boundary. Not proof of ancestry continuity."),
    ("tid", 1, "Observed task ID in the same procfs/observer PID-numbering view, joined to its enclosing process and own starttime."),
    ("child_pid", 1, "Exact admitted compiler child PID in the same controller view, retained through capture/reaping; not a replacement child."),
    ("subordinate_mount_count", 0, "Exact complete subordinate-mount count for the authenticated root; accepted complete state is integer 0 only, never sampled absence."),
]:
    numerics.append(dict(field=field, semantic_source=meaning, representation="Exact built-in int; ordinary canonical JSON decimal. No bool, float, sign on nonnegative values, leading zeros, exponent, octal, quotes or coercion.",
        minimum_accepted=minimum, maximum_accepted=0 if field == "subordinate_mount_count" else 9223372036854775807,
        minimum_json_bytes=5 if field == "mode" else 1,
        maximum_json_bytes=1 if field == "subordinate_mount_count" else 19,
        range_basis="Existing enum" if field == "subordinate_mount_count" else "Existing uint/positive_int schema admission; not a claimed native Linux kernel type width.",
        mode_width_basis="Allowed Linux regular-file/directory full type bits require at least five decimal digits; schema-only upper envelope remains 19. No permissions-only alternative." if field == "mode" else None))

sources = {
    "controller": "docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/contract.json",
    "schema": "docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json",
    "workspace": "docs/roadmap/phases/SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/contract.json",
    "owner_encoding": "docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_IDENTITY_ENCODING_CONTRACT_1/contract.json",
    "budget": "docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1R/budget_witness.json",
    "candidate": "docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_TRANSPORT_1/selection.json",
}
flags = json.loads((ROOT / sources["workspace"]).read_text(encoding="utf-8"))["authority_flags"]
effects = json.loads((ROOT / sources["workspace"]).read_text(encoding="utf-8"))["operational_effects"]
flags.update({key: False for key in ["observer_implementation", "writer_inventory_implementation", "transport_selection", "schema_change", "repin", "owner_handle_change", "requirement_evolution"]})
effects.update({key: 0 for key in ["owner_import", "network", "live_proc_reads", "live_namespace_inspection", "target_runtime_stat", "runtime_probe", "controller_execution", "identity_generation"]})

contract = dict(phase_id=PHASE, schema_version="kernel_observation_identity_contract_1_v1",
    artifact_kind="pure_additive_partial_observation_projection_contract_and_unresolved_identity_report",
    typed_result="KERNEL_IDENTITY_CONTRACT_UNRESOLVED", created_at="2026-10-19",
    contract_frozen=False, settled_projection_rules_frozen=True, stop_after_contract=True,
    result_meaning="Observation projections and numeric meanings are frozen below. Exact incarnation-bearing mount/root/process/task/group/descriptor encodings remain unresolved. No impossibility or mandatory requirement evolution is established.",
    schema_modified=False, historical_contracts_modified=False, requirement_evolution_required=False,
    historical_budget_result="BUDGET_WITNESS_UNRESOLVED", cap_bytes=8192, candidate_A_selected=False,
    sources={key: dict(path=path, sha256=sha256((ROOT / path).read_bytes()).hexdigest()) for key, path in sources.items()},
    core_distinction=["raw kernel fact", "serialized field projection", "authenticated workspace state", "authority"],
    binding=dict(required=["exact original authenticated container/workspace/controller generation", "exact original retained controller and process/PID-numbering view", "current single coherent observation sequence/challenge or operation-bound poststate", "complete same-generation snapshot and workspace-local admission fence", "unchanged owner registry/HMAC/current eligibility and permanent terminal rules"],
        equality_rule="Projection equality is necessary equality evidence only. Never use it as a bearer credential, authentication, generation freshness or proof that no replacement occurred. Retain exact source observations separately in authenticated original state; digest collisions or aliases cannot upgrade equality to continuity.",
        continuity_rule="If namespace/mount/process/task/group/descriptor continuity is not independently proved in the same authenticated generation, fail PROOF_UNRESOLVED before effects. A new spelling, digest, PID, timestamp, container name or hidden generation counter cannot fill the proof gap.",
        snapshot_limit="No claim that sequential proc/stat reads are atomic. Future coherent observation/lifetime proof remains unimplemented and unaudited."),
    identity_matrix=matrix,
    namespaces=dict(order=ORDER, fields={kind: dict(regex=kind + r":\[(0|[1-9][0-9]*)\]", minimum_content_bytes=len(kind)+4, minimum_canonical_json_bytes=len(kind)+6,
        maximum_semantic_inode_digits=None, maximum_admitted_inode_digits=256-len(kind)-3) for kind in ORDER},
        canonical="Exact built-in str, ASCII, lowercase kind, literal colon and square brackets, canonical unsigned decimal. Reject whitespace, signs, leading-zero aliases, alternate case, escape spellings and non-ASCII; no normalization. JSON uses the frozen canonical encoder.",
        source="core/sandboxed_java_positive_probe.py:22-25",
        active_pid_namespace="Use /proc/<pid>/ns/pid, not pid_for_children. Numeric IDs are interpreted in the fixed observer procfs PID-numbering view; a target's namespace inode alone does not define observer numbering.",
        width_limit="No Linux semantic inode digit maximum is established by historical source or frozen platform requirements. 256 is an accepted wire ceiling only. Reject unrepresentable observations without truncation or silent hashing."),
    namespace_identity=dict(role="aggregate equality projection", algorithm="SHA256", content_regex="[0-9a-f]{64}",
        domain=DOMAIN+"namespace-tuple:v1", preimage="ASCII domain + one NUL byte + canonical JSON bytes of the fixed seven-element list [user,mnt,net,pid,ipc,cgroup,uts] containing the exact validated raw strings. ensure_ascii=true, sort_keys=true, separators=(',', ':'), allow_nan=false, ASCII encoding, no newline. No outer generation or dictionary keys are added to this preimage; they remain independently authenticated bindings.",
        collision_rule="SHA256 collision resistance is a projection assumption, not proof of authentication or unique kernel incarnation. Raw components are retained and compared where exact equality is required.",
        decision="Raw tuple-as-string would embed JSON quoting and conflate the aggregate equality key with human-readable individual observations; ad hoc concatenation is rejected. Digest chosen for this aggregate equality role with frozen preimage, not to meet the cap."),
    cgroup_identity=dict(role="membership observation equality projection", algorithm="SHA256", content_regex="[0-9a-f]{64}",
        domain=DOMAIN+"cgroup-raw:v1", preimage="ASCII domain + one NUL byte + exact raw-byte length encoded as unsigned 8-byte big-endian + the complete exact raw bytes. No decode/re-encode, strip, trim, line-ending conversion, line sorting, path normalization, parsed normalization or automatic final newline. Reject incomplete/oversized reads before a complete claim. Length >=2^64 is unrepresentable and fails unresolved.",
        raw_width="No semantic listing byte maximum is pinned; the length-prefix acceptance ceiling is 2^64-1, not a kernel bound or an observer input budget. A future observer must prove a complete bounded read under existing timeout/byte/record limits.",
        source_limit="Historical open(...).read() preserves text at Python's text layer; it does not prove byte-exact acquisition or a cgroup object-incarnation identity. This explicit raw-byte digest rule is new declarative semantics only.",
        decision="Direct raw text can contain multiple lines and arbitrary path bytes, with no established 256-byte semantic bound. Parsing/normalizing would erase distinctions. Digest chosen because consumers compare complete membership observations; raw bytes remain authenticated retained evidence, not protocol-exported content. No HMAC substitution or budget-driven digest choice."),
    start_facts=dict(regex=r"0|[1-9][0-9]*", minimum_content_bytes=1, maximum_semantic_digits=None,
        maximum_admitted_digits=256, parser_requirement="Stat field 22 is a numbered Linux format field. comm can contain spaces and parentheses; naive whitespace split of the whole stat line or first ')' delimiter is insufficient. Process/task fact collection must prove correct parsing and coherent binding; no parser or live read is implemented here.",
        counter_limit="No architecture clock width, tick frequency, wrap semantics, boot-ID encoding or PID reuse interval is pinned. Do not infer 19 digits from the numeric schema: start_identity is an id string, not a uint field."),
    numeric_metadata=numerics,
    representation_decisions=[
        dict(family="namespaces.*", raw="Adopt exact readlink spelling; directly interpretable and source-supported.", structured="Already typed by seven exact field names; no extra tuple inside each scalar.", digest="Rejected for individual fields: hides useful kernel interpretation and cannot prove namespace continuity."),
        dict(family="namespace_identity", raw="No independent aggregate raw kernel string exists in the audited source.", structured="Adopt the exact ordered seven-string tuple as canonical preimage, not ambiguous concatenation.", digest="Adopt SHA256 equality projection with distinct domain; raw observations stay retained."),
        dict(family="cgroup_identity", raw="Complete exact raw listing has no established small semantic width and may contain arbitrary path bytes; keep it internally.", structured="Parsed/normalized listing rejected: would silently identify distinct raw observations.", digest="Adopt role-separated exact-byte equality digest, not authentication or durable cgroup object identity."),
        dict(family="process.start_identity,task.start_identity", raw="Adopt canonical decimal clock-tick FACT text with contextual binding.", structured="PID/TID/namespace/generation remain separately bound; adding them here would conflate start fact with full process/task identity.", digest="Rejected: hides meaningful ticks without resolving reuse or quantization."),
        dict(family="namespace_generation", raw="Raw mount namespace alias considered but not adopted: cannot certify no replacement in an unobserved interval.", structured="Needs explicit retained namespace lifetime context; no owner generation counter exists here.", digest="Rejected as repair for missing continuity; no chosen preimage or grammar."),
        dict(family="mount_identity", raw="Mount ID alone can be reused. Parent ID, root/mountpoint path, filesystem kind or device number alone are also insufficient.", structured="Mount-namespace plus mount/root incarnation relation is the smallest candidate. Parent ID/topology belongs to subordinate-mount verification; paths/options/fs kind remain separately checked. No fields added merely for apparent uniqueness.", digest="Deferred: no truthful continuity-bearing tuple is frozen, so hashing candidate primitives cannot complete identity."),
        dict(family="root_identity", raw="Device/inode/type alone is reusable and not a mount discriminator.", structured="Candidate no-follow (st_dev,st_ino,file_type) bound to the exact mount and generation. Metadata remains separate; retained original-object relation still needs proof.", digest="Deferred: obscures interpretable facts without curing incarnation gaps."),
        dict(family="controller_process_identity,writer.process_identity,writer.task_identity", raw="PID/TID or start ticks alone rejected.", structured="Process candidate PID+own start+PID namespace; task adds enclosing original process+TID+own start. Exact equality is not proven injective under tick quantization/reuse, and coherent lifetime binding remains missing.", digest="Deferred: no advantage until the canonical relation and continuity proof are established."),
        dict(family="process_group_identity", raw="Numeric PGID alone rejected.", structured="Candidate original admitted leader process incarnation plus observed PGID, operation and authenticated generation; must retain group relation through leader exit.", digest="Deferred; no random token or cryptographic credential substitutes for observed group ownership."),
        dict(family="writer_handle.descriptor_identity", raw="Bare numeric FD aliases potential-access records and fd close/reopen.", structured="Distinct actual versus potential tags are necessary, but not sufficient without fully defined per-kind relation preimages. Potential-access semantics are outside scope.", digest="Deferred: no fully frozen truthful preimages; must not hash an underspecified relation."),
        dict(family="numeric metadata", raw="Adopt exact JSON decimal int from the stated fact; full st_mode for mode.", structured="No scalar string wrappers or alternate octal display serialization.", digest="Rejected: these fields require numeric interpretation, not equality-only identity."),
    ],
    unresolved_decisions=[dict(field=item["fields"], reason=item["semantic_role"], next_evidence="A separately reviewed read-only lifetime/continuity projection and canonical grammar; no owner counter/token invented here.") for item in matrix if item["status"] == UNRESOLVED],
    descriptor_boundary=dict(actual="Actual numeric FD denotes a slot within a file table at an observation. Slot reuse and shared file tables require explicit scope; inode/readlink/fdinfo equality alone is no durable open-file-description identity.",
        potential="Synthetic potential-access relation has no kernel FD. Its causal semantics are intentionally outside this phase. A future tagged grammar must bind exact process/task, mount/path/access kind and independently established relation without aliasing actual handles.",
        selection=None, tagged_grammar_frozen=False, records_per_writer_decided=False),
    excluded_scope=["writer record count", "writer completeness topology", "potential-access semantics", "descendant/per-path handle enumeration", "umask/creation topology", "borrower identities", "handoff identities", "container/workspace/controller-generation encodings", "future owner IDs", "physical framing/stream mapping"],
    writer_completeness="WRITER_INVENTORY_COMPLETENESS_UNRESOLVED",
    budget_projection="Read budget_projection.json: exact partial lower subtotals and symbolic residuals only; full projected response sizes remain unestablished. Conditional physical arithmetic does not select Candidate A or alter 8192.",
    authority_flags=flags, operational_effects=effects,
    effect_counter_scope="Scenario/runtime operations only. Additive documentation/test/evidence writes and guarded validation are not target workspace effects.")
write("contract.json", contract)
write("finite_width.json", dict(phase_id=PHASE, identity_families=matrix, numeric_families=numerics,
    distinction="Semantic kernel maxima, admitted wire ceilings, grammar lower bounds, actual attainable widths and symbolic budget placeholders are separate. No unspecified one-byte identity is asserted attainable.",
    direct_ascii_id_ceiling=dict(content=256, canonical_json=258, basis="Only the frozen ASCII namespace/start projections; not every generic id."),
    unknown_id_ceiling=dict(content_utf8=256, canonical_json_safe_ceiling=1538, basis="Existing generic id permits escapes; 1536 canonical content plus two quotes. Not a chosen kernel grammar.")))
write("SYNTH_EXEC_PREP_CONTROLLER_KERNEL_IDENTITY_CONTRACT_1_REPORT.json", dict(phase_id=PHASE,
    typed_result=contract["typed_result"], contract_frozen=False, settled_projection_rules_frozen=True,
    historical_budget_result="BUDGET_WITNESS_UNRESOLVED", writer_completeness=contract["writer_completeness"],
    candidate_A_selected=False, cap_bytes=8192, requirement_evolution_performed=False,
    identity_matrix="contract.json#/identity_matrix", finite_width="finite_width.json", source_audit="source_audit.json",
    conditional_budget="budget_projection.json", validation="validation_summary.json", authority_flags=flags, operational_effects=effects,
    stop=True, operational_observer_or_writer_inventory_implemented=False))
print(json.dumps(dict(typed_result=contract["typed_result"], identity_rows=len(matrix), numeric_rows=len(numerics))))
