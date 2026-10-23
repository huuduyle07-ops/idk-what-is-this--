"""Declarative byte accounting only; never an owner, controller or wire parser.

Unspecified identity encodings are unresolved. A length-probe token in a relaxed
object is not an identity, capability, observation, class hash or feasible run.
No historical helper is imported (some historical generators write on import).
"""
import copy
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PHASES = ROOT / "docs/roadmap/phases"
SCHEMA_FILE = PHASES / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json"
CONTRACT_FILE = PHASES / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/contract.json"
SCHEMA = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
DEFS = SCHEMA["definitions"]
CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
CAP = 8192
SOURCE_HASH = CONTRACT["materialization"]["source_identity"]["sha256"]
EMPTY_HASH = hashlib.sha256(b"").hexdigest()
OPS = DEFS["operation"]["values"]
OBS = tuple(op for op in OPS if op.startswith("OBSERVE_"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def resolve(spec):
    return DEFS[spec] if type(spec) is str else spec


def validate(value, spec, operation=None):
    """Validate synthetic Python data against the unchanged declarative schema.

    This is a proof-data checker, with no byte reader, dispatch or authentication.
    Cross-field semantic checks below are a separate layer, never implied here.
    """
    spec = resolve(spec)
    kind = spec["type"]
    if kind == "record":
        assert type(value) is dict and set(value) == set(spec["fields"])
        for key, child in spec["fields"].items():
            validate(value[key], child, operation)
    elif kind == "enum":
        assert any(type(value) is type(v) and value == v for v in spec["values"])
    elif kind == "fixed_list":
        assert canonical(value) == canonical(spec["values"])
        assert type(value) is list
    elif kind == "nullable":
        if value is not None:
            validate(value, spec["item"], operation)
    elif kind == "list":
        assert type(value) is list and len(value) <= spec["max_items"]
        for child in value:
            validate(child, spec["items"], operation)
    elif kind == "str":
        assert type(value) is str
        length = len(value.encode("utf-8"))
        assert spec.get("min_utf8_bytes", 0) <= length <= spec["max_utf8_bytes"]
        assert spec.get("NUL_allowed", True) or "\x00" not in value
        assert "pattern" not in spec or re.fullmatch(spec["pattern"], value)
    elif kind == "int":
        assert type(value) is int and spec["minimum"] <= value <= spec["maximum"]
    elif kind == "bool":
        assert type(value) is bool
    elif kind == "operation_selected_record":
        validate(value, spec["by_operation"][operation], operation)
    else:
        raise AssertionError(kind)


def default(spec):
    spec = resolve(spec)
    kind = spec["type"]
    if kind == "record":
        return {k: default(v) for k, v in spec["fields"].items()}
    if kind == "enum":
        return copy.deepcopy(min(spec["values"], key=lambda v: len(canonical(v))))
    if kind == "fixed_list":
        return copy.deepcopy(spec["values"])
    if kind == "nullable":
        return None
    if kind == "list":
        return []
    if kind == "str":
        return "0" * (64 if "pattern" in spec else spec.get("min_utf8_bytes", 0))
    if kind == "int":
        return max(0, spec["minimum"])
    if kind == "bool":
        return True
    if kind == "operation_selected_record":
        return {}
    raise AssertionError(kind)


PROFILES = {
    "frozen_semantic_relaxation": {
        "kind": "universal_length_relaxation_NOT_attainable_witness",
        "generation_width": 1, "opaque_width": 1, "class_size": 1,
        "writer_inventory": False, "realistic": False,
        "basis": "Frozen semantic id fields have no generation-token encoding. All unresolved id slots use the schema lower bound as a length probe only. Writer list empty is a relaxation, not a zero-writer claim. Class size 1 is a conservative envelope bound, never valid javac output."
    },
    "candidate_a_relaxation": {
        "kind": "candidate_specific_length_relaxation_NOT_attainable_witness",
        "generation_width": 64, "opaque_width": 1, "class_size": 1,
        "writer_inventory": False, "realistic": False,
        "basis": "Reviewed unaccepted candidate A fixes two 32-byte hex generations. No width is invented for other unresolved identities. Empty writers remains a strict relaxation."
    },
    "candidate_a_controller_writer_relaxation": {
        "kind": "conditional_kernel_shape_NOT_attainable_witness",
        "generation_width": 64, "opaque_width": 1, "class_size": 1,
        "writer_inventory": True, "realistic": False,
        "basis": "One accounted controller/task with potential write access to both tmpfs roots. All identity length probes remain unresolved; this shape is not an observed or authenticated kernel state."
    },
    "stress_minimum_class_envelope": {
        "kind": "representative_stress_NOT_formal_minimum_or_live_evidence",
        "generation_width": 64, "opaque_width": 64, "class_size": 1,
        "writer_inventory": True, "realistic": True,
        "basis": "64-hex relation/token slots; full container ID; small illustrative Linux namespace/start/cgroup/descriptor strings; one controller plus task; real SHA256 values of clearly synthetic inputs. Class envelope minimum 1 is not Java-valid."
    },
    "stress_plausible_class": {
        "kind": "representative_stress_NOT_formal_minimum_or_live_evidence",
        "generation_width": 64, "opaque_width": 64, "class_size": 512,
        "writer_inventory": True, "realistic": True,
        "basis": "Same stress shape with an illustrative 512-byte class size. No measured or predicted class output/hash; changing the decimal size affects metadata, never adds raw class bytes."
    },
}


def token(label, width):
    return hashlib.sha256(label.encode("ascii")).hexdigest()[:width]


def namespaces(realistic):
    return {name: (f"{name}:[4026532001]" if realistic else "0")
            for name in DEFS["namespaces"]["fields"]}


def manifest(stage, profile):
    if stage == "preparation-empty":
        return []
    paths = ["/work/SyntheticStateBox.java", "/work/classes"]
    if stage == "prepared":
        paths.append("/work/classes/SyntheticStateBox.class")
    result = []
    for path in paths:
        directory = path == "/work/classes"
        value = default("manifest_entry")
        value.update(path=path, kind="directory" if directory else "file",
                     mode=(16832 if directory else 33152) if profile["realistic"] else 0,
                     uid=65534, gid=65534, link_count=2 if directory else 1)
        if not directory:
            source = path.endswith(".java")
            value.update(size_bytes=239 if source else profile["class_size"],
                         sha256=SOURCE_HASH if source else hashlib.sha256(
                             b"illustrative-class-sizing-input-not-a-classfile").hexdigest())
        result.append(value)
    return result


def state(stage, profile, obs_sequence, obs_label):
    value = default("workspace_state")
    width = profile["opaque_width"]
    gen = profile["generation_width"]
    value.update(workspace_capability_id=token("workspace", width),
                 stable_fingerprint=token("unattested-fingerprint", 64),
                 issuing_pid=1234 if profile["realistic"] else 1,
                 container_identity=token("container", 64),
                 workspace_generation=token("workspace-generation", gen),
                 controller_identity=token("controller", width),
                 controller_generation=token("controller-generation", gen),
                 observation_sequence=obs_sequence,
                 observation_challenge=token(obs_label, 64), stage=stage)
    for path, options in (("/tmp", "rw,nosuid,nodev,noexec,size=16m,mode=1777"),
                          ("/work", "rw,nosuid,nodev,size=32m,mode=1777")):
        mount = default("mount")
        mount.update(path=path, options=options,
                     mount_identity=("30" if path == "/tmp" else "31") if profile["realistic"] else "0",
                     namespace_generation="mnt:[4026532001]" if profile["realistic"] else "0",
                     root_identity=("0:30:1" if path == "/tmp" else "0:31:1") if profile["realistic"] else "0")
        mount["root_metadata"].update(mode=17407 if profile["realistic"] else 0,
                                      link_count=2 if profile["realistic"] else 1)
        value["mounts"].append(mount)
    process = default("process")
    process.update(pid=1, parent_pid=0, role="controller", uid=65534, gid=65534,
                   start_identity="123456" if profile["realistic"] else "0",
                   namespaces=namespaces(profile["realistic"]),
                   cgroup_identity="0::/" if profile["realistic"] else "0",
                   tasks=[{"tid": 1, "start_identity": "123456" if profile["realistic"] else "0"}])
    exclusive = value["process_exclusivity_observation"]
    exclusive.update(controller_process_identity="1:123456" if profile["realistic"] else "0",
                     controller_generation=value["controller_generation"],
                     namespace_identity="pid:[4026532001]" if profile["realistic"] else "0",
                     exclusive_owner_relation_id=token("owner", width), processes=[process])
    if profile["writer_inventory"]:
        writer = default("writer")
        writer.update(process_identity=exclusive["controller_process_identity"],
                      task_identity="1:123456" if profile["realistic"] else "0",
                      accounted_original_relation_id=token("owner", width))
        for mount in value["mounts"]:
            handle = default("writer_handle")
            handle.update(path=mount["path"], mount_identity=mount["mount_identity"],
                          descriptor_identity="1:potential" if profile["realistic"] else "0",
                          access_kind="potential_write_access")
            writer["handles"].append(handle)
        exclusive["writers"] = [writer]
    value["work_manifest"] = manifest(stage, profile)
    return value


def envelope(operation, direction, profile, sequence):
    value = default(direction)
    width = profile["opaque_width"]
    value.update(operation=operation, purpose=operation, sequence=sequence,
                 request_id=token("request-" + str(sequence), width),
                 operation_id=token("operation-" + str(sequence), width),
                 workspace_capability_id=token("workspace", width),
                 container_identity=token("container", 64),
                 workspace_generation=token("workspace-generation", profile["generation_width"]),
                 controller_generation=token("controller-generation", profile["generation_width"]))
    if operation in OBS:
        value["challenge"] = token("observation-" + str(sequence), 64)
    if direction == "request":
        value["admission_relation_id"] = token("admission-" + str(sequence), width)
        value["payload"] = default("payload_" + operation)
        for key in value["payload"]:
            if key.endswith("_id"):
                value["payload"][key] = token(key, width)
    else:
        value["status"] = "COMPLETE"
    return value


def pair(operation, profile, sequence):
    request = envelope(operation, "request", profile, sequence)
    response = envelope(operation, "response", profile, sequence)
    result_type = DEFS["response"]["fields"]["result"]["item"]["by_operation"][operation]
    result = default(result_type)
    width = profile["opaque_width"]
    if "workspace_state" in result:
        stage = "preparation-empty" if operation == "OBSERVE_EMPTY_WORKSPACE" else (
            "materialized" if operation == "MATERIALIZE_EXACT_SCENARIO_SOURCE" else "prepared")
        result["workspace_state"] = state(stage, profile, sequence,
            "observation-" + str(sequence) if operation in OBS else "poststate-" + str(sequence))
    if "preparation_attempt_id" in result:
        result["preparation_attempt_id"] = token("preparation_attempt_id", width)
    if operation == "MATERIALIZE_EXACT_SCENARIO_SOURCE":
        result["source_readback_sha256"] = SOURCE_HASH
    if operation == "COMPILE_EXACT_SCENARIO":
        capture = result["capture_and_reap"]
        capture.update(child_pid=7 if profile["realistic"] else 2, exit_code=0,
                       timed_out=False, reaped=True, group_terminated=True, selectors_closed=True,
                       process_group_identity="7:123457" if profile["realistic"] else "0",
                       deadline_identity=token("deadline", width))
        for name in ("stdout", "stderr"):
            capture[name].update(observed_bytes=0, sha256=EMPTY_HASH, eof=True,
                                 overflow=False, closed=True)
        result["compiler_identity"].update(namespaces=namespaces(profile["realistic"]),
                                          cgroup_identity="0::/" if profile["realistic"] else "0")
        result["class_metadata"].update(size_bytes=profile["class_size"],
            sha256=hashlib.sha256(b"illustrative-class-sizing-input-not-a-classfile").hexdigest())
    if operation == "PREPARE_EXCLUSIVE_HANDOFF":
        bindings = result["reservation_bindings"]
        for key in bindings:
            if key != "exact_artifact_manifest":
                bindings[key] = token(key, profile["generation_width"] if key.endswith("generation") else width)
        bindings["exact_artifact_manifest"] = manifest("prepared", profile)
        result["reservation_identity"] = token("reservation", width)
    if operation == "BEGIN_CLEANUP":
        result.update(outer_teardown_required=True)
    if operation == "CLEANUP_AND_REPORT":
        evidence = result["cleanup_evidence"]
        for key in evidence["original_identity"]:
            field_width = 64 if "full_container" in key else (profile["generation_width"] if "generation" in key else width)
            evidence["original_identity"][key] = token(key, field_width)
        evidence.update(preparation_attempt_id=token("preparation_attempt_id", width),
                        complete=True, work_and_tmp_generation_gone="verified",
                        no_surviving_artifact_export="verified")
        evidence["children_and_process_group_results"] = [{
            "process_identity": "7:123457" if profile["realistic"] else "0",
            "process_group_identity": "7:123457" if profile["realistic"] else "0",
            "termination": "verified", "reaping": "verified"}]
        evidence["capture_closure_and_EOF"] = [{"capture_identity": token(name, width),
            "closure": "verified", "EOF": "verified"} for name in ("stdout", "stderr")]
        evidence["remove_result"] = default("remove_result")
        evidence["remove_result"].update(target_full_container_identity=token("container", 64), outcome="verified")
        evidence["fresh_independent_absence_observation"] = default("absence")
        evidence["fresh_independent_absence_observation"].update(
            target_full_container_identity=token("container", 64), outcome="verified", evidence_sha256=token("absence", 64))
    response["result"] = result
    validate(request, "request", operation)
    validate(response, "response", operation)
    return request, response


def basis(path):
    leaf = path.rsplit("/", 1)[-1]
    if leaf in ("workspace_generation", "controller_generation"):
        return "Frozen schema id; semantic textual minimum UNRESOLVED. Candidate A alone fixes 64 hex."
    if leaf in ("challenge", "observation_challenge"):
        return "Observation fresh single-use owner challenge = 32 random bytes, 64 lowercase hex; mutation envelope null."
    if leaf == "container_identity" or "full_container_identity" in leaf:
        return "Exact full 64-hex container identity; never a short name."
    if leaf in ("sha256", "stable_fingerprint", "source_readback_sha256", "evidence_sha256"):
        return "SHA256 is exactly 64 lowercase hex; source and empty-capture digests exact; other samples unattested."
    if leaf == "size_bytes":
        return "Source 239 fixed; directory null; class envelope >=1, truthful Java output size UNRESOLVED."
    if leaf in ("uid", "gid"):
        return "Controller/source/class owner65534; mount roots0 is a conservative numeric bound, not observed metadata."
    if leaf in ("pid", "tid", "parent_pid"):
        return "Smallest controller PID1 and task TID1; parent0; compiler child PID>=2 and absent after reap."
    if leaf == "mode":
        return "Exact mode encoding (full st_mode versus permission bits) UNRESOLVED;0 is only the uint lower relaxation. Stress uses illustrative full st_mode."
    if leaf in ("sequence", "observation_sequence", "cleanup_barrier_sequence"):
        return "One decimal digit lower bound; illustrative strict observation/request order stays within1..9. Zero barrier before cleanup."
    if leaf in ("workspace_capability_id", "request_id", "operation_id", "admission_relation_id",
                "preparation_attempt_id", "preparation_receipt_id", "controller_identity",
                "mount_identity", "namespace_generation", "root_identity", "start_identity",
                "process_identity", "task_identity", "cgroup_identity", "descriptor_identity",
                "controller_process_identity", "namespace_identity", "exclusive_owner_relation_id",
                "accounted_original_relation_id", "process_group_identity", "deadline_identity"):
        return "Authenticated original relation required; semantic encoding/attainable minimum UNRESOLVED. Nonempty schema id lower bound1 used only as length relaxation. Stress format is illustrative."
    return "Exact schema structure, fixed enum/path/list, success predicate or explicitly labeled conservative kernel-shape relaxation; see semantic_minima.json."


def ledger(value, path="", key_bytes=0, comma_bytes=0):
    is_dict, is_list = type(value) is dict, type(value) is list
    row = {"path": path or "/", "kind": "object" if is_dict else "array" if is_list else "scalar",
           "canonical_subtree_bytes": len(canonical(value)), "key_and_colon_bytes": key_bytes,
           "preceding_comma_bytes": comma_bytes, "basis": basis(path)}
    row["own_bytes"] = key_bytes + comma_bytes + (2 if is_dict or is_list else len(canonical(value)))
    rows = [row]
    if is_dict:
        for index, key in enumerate(sorted(value)):
            rows.extend(ledger(value[key], path + "/" + key,
                               len(canonical(key)) + 1, int(index > 0)))
    elif is_list:
        for index, child in enumerate(value):
            rows.extend(ledger(child, path + "/" + str(index), 0, int(index > 0)))
    return rows


def membership(operation):
    if operation in ("MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO"):
        return "MANDATORY_INSIDE_PREPARATION_CAP", "Attempt starts at materialization; compilation shares same attempt; full poststates mandatory."
    if operation == "OBSERVE_EMPTY_WORKSPACE":
        return "UNRESOLVED_SCOPE", "Mandatory initial current empty evidence; admission precedes materialization deadline origin; cap prose never explicitly identifies its byte-start boundary."
    if operation in ("OBSERVE_PREPARED_ARTIFACTS", "OBSERVE_CURRENT_WORKSPACE"):
        return "UNRESOLVED_SCOPE", "A new prepared-state OBSERVE_* is mandatory before readiness/handoff; exact tag and attempt-end membership are not uniquely fixed."
    if operation == "PREPARE_EXCLUSIVE_HANDOFF":
        return "OPTIONAL", "Later consumer handoff is optional, requires a missing separately reviewed borrower; no successful current reservation witness. Conditional attempt membership unresolved."
    return "UNRESOLVED_SCOPE", "Terminal cleanup duty mandatory, but initial readiness precedes cleanup and attempt-end inclusion is not explicitly fixed. Final composite is host-side, not a second inner wire frame."


def outer_cleanup_shapes(profile):
    """Logical outer schema sizes, never silently routed onto inner stdout."""
    rows = []
    for index, operation in enumerate(("TERMINATE_REMOVE_EXACT_RETAINED_GENERATION",
            "OBSERVE_EXACT_RETAINED_GENERATION_ABSENCE"), 1):
        for direction in ("request", "response"):
            value = default("outer_cleanup_" + direction)
            value.update(operation=operation, request_id=token("outer-" + str(index), profile["opaque_width"]))
            for key in value["original_identity"]:
                width = 64 if "full_container" in key else (profile["generation_width"] if "generation" in key else profile["opaque_width"])
                value["original_identity"][key] = token(key, width)
            if direction == "request":
                value["retained_authenticated_cleanup_relation_id"] = token("outer-cleanup", profile["opaque_width"])
            else:
                value["status"] = "COMPLETE"
                component = "remove_result" if index == 1 else "absence"
                value[component] = default(component)
                value[component].update(request_id=value["request_id"],
                    target_full_container_identity=token("original_full_container_identity", 64), outcome="verified")
                if component == "absence":
                    value[component]["evidence_sha256"] = token("outer-absence", 64)
            validate(value, "outer_cleanup_" + direction, operation)
            parts = ledger(value)
            assert sum(part["own_bytes"] for part in parts) == len(canonical(value))
            rows.append({"operation": operation, "direction": direction,
                "channel": "independent_outer_custodian_NOT_inner_stdio",
                "attempt_membership": "UNRESOLVED_SCOPE",
                "canonical_payload_bytes": len(canonical(value)),
                "candidate_a_inner_header_bytes": 0,
                "outer_channel_framing_bytes": None,
                "framing_basis": "u32be profile belongs to inner wire; outer custodian schema is not assigned that transport.",
                "semantic_execution_witness": False, "schema_valid": True,
                "synthetic_record": value, "canonical_payload": canonical(value).decode("ascii"),
                "field_and_subtree_contributions": parts})
    return rows


def lower_bound_nullable_relaxation(value, path=""):
    """Keep null where required; relax uncertain nullable id to shorter id token.

    This avoids treating JSON null (4 bytes) as a universal lower bound when an
    unresolved one-byte id (3 JSON bytes) might be permitted by frozen semantics.
    """
    uncertain = {"admitted_operation_id", "active_operation_id", "authorized_borrower_relation_id", "handoff_identity"}
    if type(value) is dict:
        for key in value:
            if key in uncertain and value[key] is None:
                value[key] = "0"
            else:
                lower_bound_nullable_relaxation(value[key], path + "/" + key)
    elif type(value) is list:
        for child in value:
            lower_bound_nullable_relaxation(child, path)


def make_profile(name, profile):
    messages = []
    for index, operation in enumerate(OPS, 1):
        request, response = pair(operation, profile, index)
        for direction, value in (("request", request), ("response", response)):
            if name in ("frozen_semantic_relaxation", "candidate_a_relaxation"):
                lower_bound_nullable_relaxation(value)
                validate(value, direction, operation)
            payload = canonical(value)
            rows = ledger(value)
            assert sum(row["own_bytes"] for row in rows) == len(payload)
            scope, reason = membership(operation)
            messages.append({"operation": operation, "direction": direction,
                "candidate_a_channel": "controller_stdin" if direction == "request" else "controller_stdout",
                "attempt_membership": scope, "attempt_inclusion_reason": reason,
                "canonical_payload_bytes": len(payload), "candidate_a_header_bytes": 4,
                "candidate_a_frame_bytes": len(payload) + 4,
                "individual_frame_fits": len(payload) + 4 <= CAP,
                "schema_valid": True, "semantic_execution_witness": False,
                "canonical_payload": payload.decode("utf-8"),
                "synthetic_record": value, "field_and_subtree_contributions": rows})
    groups = {
        "materialize_compile": ["MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO"],
        "materialize_compile_fresh_current": ["MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO", "OBSERVE_CURRENT_WORKSPACE"],
        "materialize_compile_fresh_prepared": ["MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO", "OBSERVE_PREPARED_ARTIFACTS"],
        "empty_materialize_compile_fresh_current": ["OBSERVE_EMPTY_WORKSPACE", "MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO", "OBSERVE_CURRENT_WORKSPACE"],
        "empty_materialize_compile_fresh_prepared": ["OBSERVE_EMPTY_WORKSPACE", "MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO", "OBSERVE_PREPARED_ARTIFACTS"],
    }
    totals = {}
    for group, operations in groups.items():
        selected = [m for m in messages if m["operation"] in operations]
        directions = {}
        for direction in ("request", "response"):
            subset = [m for m in selected if m["direction"] == direction]
            total = sum(m["canonical_payload_bytes"] for m in subset)
            directions[direction] = {"semantic_payload_bytes": total,
                "frame_overhead_bytes": 4 * len(subset), "candidate_a_wire_bytes": total + 4 * len(subset),
                "payload_minus_8192": total - CAP, "wire_minus_8192": total + 4 * len(subset) - CAP}
        totals[group] = {"operations": operations, "directions": directions,
            "semantic_payload_total_both_directions": sum(d["semantic_payload_bytes"] for d in directions.values()),
            "frame_overhead_both_directions": 8 * len(operations),
            "candidate_a_outer_stdout_bytes": directions["response"]["candidate_a_wire_bytes"],
            "candidate_a_outer_stderr_bytes": 0,
            "child_compiler_stdout_bytes": 0, "child_compiler_stderr_bytes": 0,
            "request_bytes_added_to_outer_stdout": 0,
            "attempt_scope": "Guaranteed materialize/compile core only" if group == "materialize_compile" else "CONDITIONAL_UNRESOLVED_SCOPE"}
    return {"name": name, **profile,
            "catalog_order_is_chronological_lifecycle": False,
            "messages": messages, "outer_cleanup_messages": outer_cleanup_shapes(profile), "totals": totals}


def build():
    profiles = {name: make_profile(name, p) for name, p in PROFILES.items()}
    return {
        "phase_id": "SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1",
        "typed_result": "AGGREGATE_BUDGET_SCOPE_UNRESOLVED",
        "proof_kind": "pure_declarative_canonical_schema_and_scope_audit",
        "cap_per_outer_stream": CAP,
        "canonical_encoding": {"encoding": "UTF-8", "sort_keys": True,
            "separators": [",", ":"], "ensure_ascii": True, "allow_nan": False},
        "schema_sha256": hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest(),
        "schema_changed": False, "transport_selected": False,
        "formal_successful_lifecycle_minimum_bytes": None,
        "formal_successful_lifecycle_minimum_reason": "Frozen attempt endpoint/readiness-observation membership and attainable encodings of original identity references are unresolved. Canonical lower relaxations are bounds, not fully truthful successful witnesses.",
        "existence_witness_produced": False, "unconditional_impossibility_proved": False,
        "budget_blocker_removed": False, "requirement_evolution_required": "UNRESOLVED",
        "no_feasibility_inference_from_subcap_relaxation": True,
        "no_scope_resolution_by_favorable_exclusion": True,
        "formal_conservative_payload_lower_bounds": {
            "guaranteed_materialize_compile_response_payload_bytes": profiles["frozen_semantic_relaxation"]["totals"]["materialize_compile"]["directions"]["response"]["semantic_payload_bytes"],
            "conditional_with_fresh_current_response_payload_bytes": profiles["frozen_semantic_relaxation"]["totals"]["materialize_compile_fresh_current"]["directions"]["response"]["semantic_payload_bytes"],
            "conditional_basis": "If the new readiness OBSERVE_* belongs to the same attempt, these three complete logical response payloads are a universal conservative lower relaxation. Physical outer-stream placement is also conditional on transport.",
            "attainable_minimum_claimed": False,
        },
        "fresh_readiness_observation": "New OBSERVE_* challenge mandatory before readiness/handoff; mutation poststate cannot substitute. OBSERVE_PREPARED_ARTIFACTS requires an existing receipt, so not a prerequisite to initial receipt. OBSERVE_CURRENT_WORKSPACE permits stage-appropriate prepared snapshot; exact fresh tag unresolved.",
        "direction_accounting": {
            "semantic_schema": "No finally selected physical response channel; logical payload sizes remain transport independent.",
            "candidate_a_requests": "Host to controller stdin; independently bounded frames/session; not captured controller stdout or stderr.",
            "candidate_a_responses": "Controller stdout; full canonical response evidence plus4-byte header counted exactly once.",
            "candidate_a_stderr": "Empty on success;0 bytes. No request or response duplication into stderr.",
            "compiler": "Child stdout/stderr separate,2048 each; successful actual captures empty; their metadata already counted within response, no raw capture bytes exist in messages.",
            "headers": "Exactly4 per frame, no magic/version prefix; request headers remain request-direction bytes.",
            "independent_request_aggregate_8192": False,
            "request_bounds": "Frozen observation request<=8192; candidate A all frames<=8192 and retained session<=65536 per direction,64 requests including reserved cleanup slots. No independent frozen8192 cumulative stdin cap stated.",
            "cleanup": "Candidate final composite is in-process host evidence, not a second inner wire response; cleanup shape sizes are conditional logical schema sizes only."
        },
        "assumptions": [
            "No physical transport selected. Candidate A accounting is conditional and does not accept its architecture.",
            "PID1 plus one task is the smallest reviewed controller shape; all process namespace/cgroup fields included. Compiler is reaped, so absent from postcompile process list; capture retains its child/group identity.",
            "Two tmpfs mounts with roots/metadata and exact options always included; no zero-process or omitted namespaces.",
            "Writer-free lower relaxation does NOT assert truthful absence of the controller's potential write access. Separate controller-writer shape accounts for both roots.",
            "Unspecified identity strings have schema lower bound1 but NO proven attainable semantic minimum. Probe strings do not create aliases or actual identities.",
            "Frozen semantic schema alone does not impose candidate A's64-hex generation choices; both profiles are separated.",
            "Relaxed non-null nullable-id slots only make universal byte bounds smaller; they are not coherent readiness states.",
            "Class size1 and numeric mode0 are conservative length probes, not a successful Java class or measured filesystem metadata. Frozen mode textual semantics do not specify full st_mode versus permission bits.",
            "Stress hashes are actual SHA256 computations over named synthetic inputs; only source, compiler/image and empty-capture hashes are frozen identities. No class bytes/hash predicted.",
            "Operation catalog order follows the schema enum, not a chronological execution. Independent shape probes may violate identity relations; grouped byte sums do not authenticate those probe values.",
            "Handoff and cleanup shape probes describe conditional schema records only. They do not invent a borrower, prove independent backend continuity or claim an inner process can report complete removal of itself.",
            "Pre-effect local empty/source verification is mandatory evidence; no additional serialized pair inferred unless frozen semantics require it. Additional freshness pairs can only increase conditional totals."
        ],
        "requirement_evolution_targets_unselected": ["increase aggregate cap", "separate protocol evidence bytes from historical process capture budget", "change mandatory evidence duplication", "change message schema/projection", "change preparation-attempt boundary"],
        "authority_flags": {key: False for key in CONTRACT["authority_flags"]},
        "operational_effects": {key: 0 for key in CONTRACT["operational_effects"]},
        "profiles": profiles,
    }


def main():
    report = build()
    (HERE / "budget_witness.json").write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    compact = {name: p["totals"] for name, p in report["profiles"].items()}
    (HERE / "byte_totals.json").write_text(json.dumps(compact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"typed_result": report["typed_result"], "profiles": {
        name: {g: t["candidate_a_outer_stdout_bytes"] for g, t in p["totals"].items()}
        for name, p in report["profiles"].items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
