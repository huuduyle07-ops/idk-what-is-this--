"""Author protocol data from frozen source/AST only; no operational owner import."""
from copy import deepcopy
from hashlib import sha256
import ast
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
PREFIX = "docs/roadmap/phases/"
WORKSPACE = PREFIX + "SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/contract.json"
PREP = PREFIX + "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1/contract.json"
PROTOCOL = "synthetic_preparation_controller_pinned_1_v1"
RESULT = "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1_COMPLETE"
WORKSPACE_OWNER = "core.synthetic_execution_preparation_workspace_pinned"
PREPARATION_OWNER = "core.synthetic_execution_preparation_pinned"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, ensure_ascii=True,
        allow_nan=False) + "\n", encoding="utf-8")


def operation(tag, owner, predicates, inputs, paths, child, bounds, post, failure, cleanup, requirement):
    return dict(tag=tag, required_admission_owner=owner,
        permissible_predicates=predicates, input_projection=inputs,
        fixed_paths=paths, allowed_subprocess=child, bounds_profile=bounds,
        postconditions=post, failure_behavior=failure, cleanup_interaction=cleanup,
        controller_spends_authority=False, downstream_requirement=requirement)


def message_schema(contract):
    """Declarative closed semantic schemas, never a controller/parser implementation."""
    def record(fields):
        return {"type": "record", "fields": fields, "additional_fields": False,
            "all_fields_required": True}

    def array(item, maximum):
        return {"type": "list", "items": item, "max_items": maximum}

    def nullable(item):
        return {"type": "nullable", "item": item}

    def enum(*values):
        return {"type": "enum", "values": list(values)}

    schemas = {
        "id": {"type": "str", "min_utf8_bytes": 1, "max_utf8_bytes": 256, "NUL_allowed": False},
        "text": {"type": "str", "max_utf8_bytes": 1024, "NUL_allowed": False},
        "bool": {"type": "bool", "exact_type": True},
        "uint": {"type": "int", "minimum": 0, "maximum": 9223372036854775807, "bool_allowed": False},
        "positive_int": {"type": "int", "minimum": 1, "maximum": 9223372036854775807, "bool_allowed": False},
        "exit_code": {"type": "int", "minimum": -255, "maximum": 255, "bool_allowed": False},
        "hash": {"type": "str", "pattern": "[0-9a-f]{64}", "max_utf8_bytes": 64},
        "challenge": {"type": "str", "pattern": "[0-9a-f]{64}", "max_utf8_bytes": 64},
        "path": enum("/tmp", "/work", "/work/classes", "/work/SyntheticStateBox.java",
            "/work/classes/SyntheticStateBox.class"),
        "operation": enum(*contract["minimum_operation_review"]["accepted_tags"]),
        "cleanup_reason": enum(*contract["framing"]["primitive_rules"]["cleanup_reason_enum"]),
        "protocol": enum(PROTOCOL), "version": enum(1),
        "environment": record({key: enum(value) for key, value in contract["foundation"]["sandbox"]["environment"].items()}),
        "namespaces": record({name: "id" for name in ("user", "mnt", "net", "pid", "ipc", "cgroup", "uts")}),
        "manifest_entry": record({"path": "path", "kind": enum("file", "directory"),
            "mode": "uint", "uid": "uint", "gid": "uint", "link_count": "positive_int",
            "size_bytes": nullable("uint"), "sha256": nullable("hash")}),
        "mount": record({"path": enum("/tmp", "/work"), "mount_identity": "id",
            "namespace_generation": "id", "filesystem_kind": enum("tmpfs"),
            "options": enum("rw,nosuid,nodev,size=32m,mode=1777", "rw,nosuid,nodev,noexec,size=16m,mode=1777"),
            "subordinate_mount_count": enum(0), "root_identity": "id",
            "root_metadata": record({"mode": "uint", "uid": "uint", "gid": "uint", "link_count": "positive_int"})}),
        "task": record({"tid": "positive_int", "start_identity": "id"}),
        "process": record({"pid": "positive_int", "parent_pid": "uint", "start_identity": "id",
            "role": enum("controller", "admitted_compiler", "unexpected"), "namespaces": "namespaces",
            "cgroup_identity": "id", "uid": "uint", "gid": "uint", "tasks": array("task", 128),
            "admitted_operation_id": nullable("id")}),
        "writer_handle": record({"descriptor_identity": "id", "path": "path", "mount_identity": "id",
            "access_kind": enum("potential_write_access", "open_writable_handle"),
            "admitted_operation_id": nullable("id")}),
        "writer": record({"process_identity": "id", "task_identity": "id",
            "handles": array("writer_handle", 128), "accounted_original_relation_id": nullable("id")}),
        "process_exclusivity": record({"controller_process_identity": "id", "controller_generation": "id",
            "namespace_identity": "id", "processes": array("process", 128),
            "writers": array("writer", 128), "exclusive_owner_relation_id": "id",
            "authorized_borrower_relation_id": nullable("id"), "inventory_method": enum("complete_readonly_kernel_inventory"),
            "cleanup_barrier_sequence": "uint", "active_operation_id": nullable("id"),
            "handoff_identity": nullable("id")}),
        "workspace_state": record({"workspace_capability_id": "id", "stable_fingerprint": "hash",
            "issuing_pid": "positive_int", "container_identity": "id", "workspace_generation": "id",
            "controller_identity": "id", "controller_generation": "id", "observation_sequence": "positive_int",
            "observation_challenge": "challenge", "stage": enum("preparation-empty", "materialized", "prepared"),
            "mounts": array("mount", 2), "work_manifest": array("manifest_entry", 3),
            "tmp_manifest": array("manifest_entry", 0), "process_exclusivity_observation": "process_exclusivity"}),
        "capture_stream": record({"observed_bytes": "uint", "limit_bytes": enum(2048),
            "sha256": "hash", "eof": "bool", "overflow": "bool", "closed": "bool"}),
        "capture_and_reap": record({"child_pid": "positive_int", "process_group_identity": "id",
            "exit_code": "exit_code", "timed_out": "bool", "reaped": "bool",
            "group_terminated": "bool", "stdout": "capture_stream", "stderr": "capture_stream",
            "selectors_closed": "bool", "deadline_identity": "id"}),
        "compiler_identity": record({"path": enum(contract["compilation"]["compiler"]["path"]),
            "sha256": enum(contract["compilation"]["compiler"]["sha256"]),
            "argv": {"type": "fixed_list", "values": contract["compilation"]["compiler"]["exact_scenario_argv"]},
            "cwd": enum("/work"), "environment": "environment", "image_identity": enum(contract["foundation"]["image_identity"]),
            "namespaces": "namespaces", "cgroup_identity": "id"}),
        "class_metadata": record({"path": enum("/work/classes/SyntheticStateBox.class"),
            "size_bytes": {"type": "int", "minimum": 1, "maximum": 32768, "bool_allowed": False},
            "sha256": "hash", "internal_class_name": enum("SyntheticStateBox"),
            "inspection_kind": enum("inert_bounded_classfile_metadata"), "class_loaded": enum(False)}),
        "reservation_bindings": record({"workspace_generation": "id", "controller_generation": "id",
            "preparation_attempt_id": "id", "preparation_receipt_id": "id",
            "exact_artifact_manifest": array("manifest_entry", 3), "authenticated_future_borrower_identity": "id"}),
        "component_outcome": enum("verified", "failed", "unresolved", "not_applicable"),
        "child_cleanup": record({"process_identity": "id", "process_group_identity": nullable("id"),
            "termination": "component_outcome", "reaping": "component_outcome"}),
        "capture_cleanup": record({"capture_identity": "id", "closure": "component_outcome", "EOF": "component_outcome"}),
        "remove_result": record({"request_id": "id", "target_full_container_identity": "id", "outcome": "component_outcome"}),
        "absence": record({"request_id": "id", "target_full_container_identity": "id", "backend_relation_id": "id",
            "observer_identity": "id", "method": enum("fresh_independent_full_ID_control_plane_inspection"),
            "observation_sequence": "positive_int", "outcome": "component_outcome", "evidence_sha256": nullable("hash")}),
        "cleanup_identity": record({"original_workspace_capability_id": "id", "original_workspace_generation": "id",
            "original_controller_identity": "id", "original_controller_generation": "id",
            "original_full_container_identity": "id", "original_backend_relation": "id"}),
        "cleanup_evidence": record({"original_identity": "cleanup_identity", "preparation_attempt_id": nullable("id"),
            "handoff_identity": nullable("id"), "cleanup_barrier_sequence": "positive_int",
            "children_and_process_group_results": array("child_cleanup", 128),
            "capture_closure_and_EOF": array("capture_cleanup", 128),
            "remove_result": nullable("remove_result"), "fresh_independent_absence_observation": nullable("absence"),
            "work_and_tmp_generation_gone": "component_outcome", "no_surviving_artifact_export": "component_outcome",
            "typed_unresolved_components": array(enum("identity", "barrier", "children", "groups", "captures",
                "EOF", "removal", "absence", "mount_generations", "artifact_export"), 10), "complete": "bool"}),
        "typed_error": record({"layer": enum("controller", "workspace", "preparation", "provider", "runtime"),
            "code": "id", "origin_status": "id", "origin_reason": "text",
            "authenticated_origin_relation_id": nullable("id"), "operation_id": "id",
            "cleanup_required": "bool", "detail_id": enum("authentication", "generation", "protocol", "admission",
                "busy", "observation", "source", "executable", "child_start", "timeout", "capture", "reap",
                "handoff", "cleanup", "coordination", "preserved_upstream")}),
    }
    per_tag = {}
    for op in contract["operations"]:
        fields = {key: "cleanup_reason" if value == "cleanup_reason_enum" else value
            for key, value in op["input_projection"].items()}
        tag = op["tag"]
        payload_name = "payload_" + tag
        schemas[payload_name] = record(fields)
        per_tag[tag] = payload_name
    common = {"protocol_id": "protocol", "version": "version", "operation": "operation", "request_id": "id",
        "operation_id": "id", "workspace_capability_id": "id", "container_identity": "id",
        "workspace_generation": "id", "controller_generation": "id", "sequence": "positive_int",
        "challenge": nullable("challenge"), "purpose": "operation"}
    schemas["request"] = record({**common, "admission_relation_id": "id",
        "payload": {"type": "operation_selected_record", "by_operation": per_tag}})
    results = {
        "observation": record({"workspace_state": "workspace_state", "cleanup_barrier_sequence": "uint",
            "active_operation_id": nullable("id"), "handoff_identity": nullable("id")}),
        "materialize": record({"workspace_state": "workspace_state", "preparation_attempt_id": "id",
            "source_readback_size": enum(239), "source_readback_sha256": "hash", "source_readback_exact": enum(True)}),
        "compile": record({"workspace_state": "workspace_state", "preparation_attempt_id": "id",
            "compiler_identity": "compiler_identity", "capture_and_reap": "capture_and_reap", "class_metadata": "class_metadata"}),
        "handoff": record({"reservation_identity": "id", "reservation_bindings": "reservation_bindings",
            "activation_status": enum("PROOF_UNRESOLVED")}),
        "begin_cleanup": record({"cleanup_barrier_sequence": "positive_int", "cancelled_operation_id": nullable("id"),
            "outer_teardown_required": "bool"}),
        "cleanup": record({"cleanup_evidence": "cleanup_evidence"}),
    }
    mapping = ["observation"] * 3 + ["materialize", "compile", "handoff", "begin_cleanup", "cleanup"]
    result_map = {}
    for op, name in zip(contract["operations"], mapping):
        schemas["result_" + name] = results[name]
        result_map[op["tag"]] = "result_" + name
    schemas["response"] = record({**common, "status": enum("COMPLETE", "REJECTED", "FAILED", "PROOF_UNRESOLVED"),
        "result": nullable({"type": "operation_selected_record", "by_operation": result_map}),
        "error": nullable("typed_error")})
    # This separate envelope is usable after inner transport/incarnation loss.
    schemas["outer_cleanup_request"] = record({"protocol_id": "protocol", "version": "version",
        "operation": enum(*contract["cleanup"]["outer"]["operations"]), "request_id": "id",
        "retained_authenticated_cleanup_relation_id": "id", "original_identity": "cleanup_identity",
        "cleanup_barrier_sequence": "positive_int"})
    schemas["outer_cleanup_response"] = record({"protocol_id": "protocol", "version": "version",
        "operation": enum(*contract["cleanup"]["outer"]["operations"]), "request_id": "id",
        "original_identity": "cleanup_identity", "cleanup_barrier_sequence": "positive_int",
        "status": enum("COMPLETE", "FAILED", "PROOF_UNRESOLVED"),
        "remove_result": nullable("remove_result"), "absence": nullable("absence"), "error": nullable("typed_error")})
    return {"schema_id": PROTOCOL + ":semantic-message-schema", "kind": "declarative_pure_contract_data",
        "parser_implemented": False, "transport_byte_prefix_unselected": True,
        "root_types": ["request", "response", "outer_cleanup_request", "outer_cleanup_response"],
        "definitions": schemas,
        "cross_field_rules": [
            "Exact primitive types including enum values: bool is never int. All records reject duplicate/missing/extra keys recursively; arrays are complete, unique and bounded, never prefix samples.",
            "Request/response IDs, purpose=operation, all generations and owner sequence/challenge match exact original relation. Challenge non-null exactly for three observation tags. Mutation poststate uses a separate single-use owner-issued post-observation challenge/sequence prebound in its spent admission; it is operation-bound source evidence only, never a current-readiness response. Owner consumes that reference once and requires a new OBSERVE_* challenge before readiness or handoff.",
            "workspace_state fields exactly match frozen workspace-state digest top-level fields. Manifest paths sorted UTF-8, file link_count=1 with size/hash, directory size/hash=null. Empty work=[], materialized source+classes, prepared exact source+classes+one class. tmp=[]; no unknown entry accepted.",
            "Mounts exactly /tmp then /work with their corresponding frozen options and roots/generations. Complete process tasks sum<=128; writer records and all handles sum<=128. Every potential/open writer accounted by original relation; no unknown writer/process or subordinate mount. Unprovable inventory fails unresolved.",
            "Kernel observation scope is fixed read-only mount/namespace/cgroup/process/task/descriptor metadata derived from observed generation and inventoried PIDs, never caller paths or generic file reads. Fixed source/class reads only; source<=239 and class<=32768, total<=33007. Observation timeout/byte/record limits apply before accepting completion.",
            "Compilation result exit=0, timed_out=false, reaped/group_terminated/selectors_closed=true, each stream observed_bytes=0, overflow=false,eof/closed=true and exact empty-content hashes; no raw captures/source/class bytes in messages.",
            "Only controller error codes use controller_codes enum frozen in contract. Other layer codes/status/reasons must match exact authenticated originating owner result verbatim, with preserved origin relation. Bounded projection failure is incomplete; never invent a new upstream code or replace semantic failure with controller authentication.",
            "COMPLETE result and null error only with all operation postconditions; otherwise typed error and null result, except BEGIN_CLEANUP may retain exact barrier evidence only, and CLEANUP_AND_REPORT may retain partial cleanup_evidence with complete=false and unresolved components. Never truncate a successful response.",
            "Cleanup composite complete=true requires all required process/group/capture/EOF/removal/independent absence/mount/export outcomes verified and unresolved_components empty; not_applicable only if authenticated original no-child/no-capture evidence proves it. Removal/absence alone never establishes lost reaping/EOF.",
            "Outer request/response matches authenticated retained cleanup identity, operation and barrier with fresh request ID; typed_error.operation_id equals this outer request_id. No inner observation challenge/admission or runtime/facet/readiness prerequisite. TERMINATE_REMOVE returns remove_result with absence=null; OBSERVE_ABSENCE returns absence with remove_result=null. Outer COMPLETE requires the selected component outcome=verified and error=null; other statuses preserve typed error and available partial component evidence. No arbitrary target or command.",
            "All frames <=8192 bytes; preparation total outer stream captures remain <=8192 each over whole attempt. Larger/incomplete evidence fails typed incomplete and cleanup duty continues. No generic string command, path, argv, environment or arbitrary map.",
        ]}


def main():
    assert (PHASE / "preservation_baseline.json").is_file()
    workspace, prep = read(WORKSPACE), read(PREP)
    assert workspace["typed_result"] == "WORKSPACE_REQUIRES_CONTROLLER_EVOLUTION"
    assert prep["completion_marker"] == "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1_COMPLETE"
    observations = [
        operation("OBSERVE_EMPTY_WORKSPACE", WORKSPACE_OWNER,
            ["same original live controller/container/workspace generation", "exclusive",
             "no active mutation or handoff", "not cleanup-started", "not invalid"], {},
            ["/work", "/tmp"], None, "observation",
            ["one complete current snapshot; /work and /tmp empty; /work/classes absent",
             "full mounts/manifests/process/writer inventory; no target JVM or target activation",
             "observed exact preparation-empty predicate; owner independently authenticates readiness"],
            "Incomplete observation yields CONTROLLER_OBSERVATION_INCOMPLETE or PROOF_UNRESOLVED; unexpected state preserves workspace semantic error; never repair.",
            "Read-only; cleanup barrier preempts observation and prevents ready result.",
            WORKSPACE + "#initial_workspace"),
        operation("OBSERVE_CURRENT_WORKSPACE", WORKSPACE_OWNER,
            ["same original live generation", "exclusive", "coherent controller fence",
             "no active mutation or handoff", "not cleanup-started", "not invalid"], {},
            ["/work", "/tmp"], None, "observation",
            ["complete current snapshot of stage-appropriate exact manifest",
             "stage derived from original same-attempt preparation evidence, never caller stage",
             "partial progress is neither preparation-empty nor prepared-artifacts-present"],
            "No cached/unchanged-manifest shortcut; incomplete observation fails closed; altered inputs invalidate eligibility.",
            "Read-only; cleanup preempts and denies readiness.",
            WORKSPACE + "#workspace_state_digest"),
        operation("OBSERVE_PREPARED_ARTIFACTS", WORKSPACE_OWNER,
            ["same original live generation", "prepared-artifacts-present from preparation owner",
             "cleanup pending", "exclusive", "no active mutation or handoff",
             "compiler fully reaped; captures closed and EOF", "not cleanup-started", "not invalid"],
            {"preparation_attempt_id": "id", "preparation_receipt_id": "id"},
            ["/work", "/tmp", "/work/SyntheticStateBox.java", "/work/classes",
             "/work/classes/SyntheticStateBox.class"], None, "observation",
            ["fresh complete source/class manifest matches original same-attempt receipt",
             "no compiler/target JVM/unexpected writer; live artifacts remain in same generation",
             "evidence only; no consumer readiness or runtime activation permission"],
            "Missing original receipt relation or changed artifacts fail closed; no recompile or repair.",
            "Read-only; cleanup preempts and denies readiness.",
            WORKSPACE + "#preparation_interaction.receipt_readiness"),
    ]
    operations = observations + [
        operation("MATERIALIZE_EXACT_SCENARIO_SOURCE", PREPARATION_OWNER,
            ["same original live eligible generation", "preparation-empty", "exclusive",
             "runtime ISSUED according to owning boundary at admission",
             "exact materialization facet already spent/admitted", "no active operation/handoff",
             "not cleanup-started", "not invalid"], {"preparation_attempt_id": "id"},
            ["/work", "/tmp", "/work/classes", "/work/SyntheticStateBox.java"], None,
            "preparation_attempt",
            ["exclusive /work/classes creation then exclusive source creation",
             "exact authenticated existing 239 bytes; complete no-follow readback size/hash/bytes",
             "exact materialized manifest, no compilation"],
            "Facet remains spent on any failure; no overwrite/refund/reissue/retry; begin bounded cleanup; no success receipt.",
            "Cleanup preempts active write; cancel, account for partial files, no readiness, tear down whole generation.",
            PREP + "#materialization; " + WORKSPACE + "#initial_workspace.classes_directory"),
        operation("COMPILE_EXACT_SCENARIO", PREPARATION_OWNER,
            ["same original eligible generation", "verified same-attempt materialization",
             "exact source/readback unchanged; exclusive classes directory from materialization",
             "runtime ISSUED according to owning boundary at admission",
             "exact compilation facet already spent/admitted", "exclusive",
             "no active operation/handoff", "not cleanup-started", "not invalid"],
            {"preparation_attempt_id": "id"},
            ["/work", "/tmp", "/work/SyntheticStateBox.java", "/work/classes",
             "/work/classes/SyntheticStateBox.class"],
            deepcopy(prep["compiler"]["exact_scenario_argv"]), "preparation_attempt",
            ["one bounded javac only; fully reap; complete empty captures and both EOFs",
             "exact one-class 1..32768 byte envelope; hash actual bytes; source unchanged",
             "inert bounded classfile metadata inspection only, never load target",
             "return preparation observations; preparation owner alone authenticates success receipt"],
            "Spent facet stays spent; child start/timeout/capture/reap failures typed separately; compile/output semantic errors preserved; cleanup mandatory.",
            "Cleanup barrier cancels/kills/reaps compiler group; no raced success readiness.",
            PREP + "#compiler; #compile_output"),
        operation("PREPARE_EXCLUSIVE_HANDOFF", WORKSPACE_OWNER + " with separately authenticated future consumer boundary",
            ["same controller/workspace generation", "prepared-artifacts-present", "cleanup pending",
             "same source/class manifest", "exact original preparation attempt/receipt",
             "no compiler/target process", "all preparation captures complete/reaped",
             "no unexpected writer", "no active handoff or mutation", "not cleanup-started", "not invalid"],
            {"preparation_attempt_id": "id", "preparation_receipt_id": "id",
             "authenticated_borrower_relation_id": "id"},
            ["/work", "/tmp", "/work/SyntheticStateBox.java", "/work/classes",
             "/work/classes/SyntheticStateBox.class"], None, "observation",
            ["controller-local exclusive reservation binds exact generation/attempt/receipt/artifact manifest/borrower relation",
             "no artifact copy/export or target launch; reservation is not consumer authority",
             "activation unavailable until separately reviewed consumer contract; currently PROOF_UNRESOLVED"],
            "CONTROLLER_HANDOFF_UNRESOLVED or PROOF_UNRESOLVED without authenticated future borrower; no anonymous reservation; disconnect/failure triggers cleanup.",
            "Reservation holds exclusive fence; cleanup cancels it and never returns BUSY.",
            WORKSPACE + "#lifecycle.handoff; " + PREP + "#cleanup.after_preparation_success"),
        operation("BEGIN_CLEANUP", "independent exact-generation cleanup custodian",
            ["retained authenticated immutable cleanup identity", "any lifecycle condition including invalid or controller lost"],
            {"cleanup_reason": "cleanup_reason_enum"}, [], None, "cleanup",
            ["set monotonic barrier under controller-local fence if controller reachable",
             "outer custodian records terminal readiness withdrawal even if inner lost",
             "deny new work; cancel active mutation/handoff; no success readiness"],
            "Never BUSY and never requires ISSUED, unspent facets or inner challenge; lost inner delegates outer teardown; unknown identity yields WORKSPACE_CLEANUP_UNRESOLVED.",
            "Preempts every operation; idempotent barrier re-observation never reopens generation.",
            WORKSPACE + "#lifecycle.predicates.cleanup-started"),
        operation("CLEANUP_AND_REPORT", "independent exact-generation cleanup custodian",
            ["retained authenticated immutable cleanup identity", "cleanup-started (establish barrier first if absent)"],
            {}, ["/work", "/tmp"], None, "cleanup",
            ["kill/reap children/groups; close captures/pipes/selectors; observe EOF",
             "outer fixed primitive removes exact container and independently verifies absence",
             "complete bounded composite cleanup evidence; /work and /tmp generation gone",
             "terminal evidence only; incomplete child/EOF/absence proof remains unresolved"],
            "CONTROLLER_CLEANUP_UNRESOLVED at controller layer, WORKSPACE_CLEANUP_UNRESOLVED at workspace mapping; do not infer lost reaping/EOF from removal success.",
            "Only bounded exact-identity teardown retry allowed; no readiness restoration or new generation.",
            WORKSPACE + "#cleanup; " + PREP + "#cleanup"),
    ]
    errors = ["CONTROLLER_UNAUTHENTICATED", "CONTROLLER_WRONG_GENERATION",
        "CONTROLLER_PROTOCOL_MISMATCH", "CONTROLLER_OPERATION_NOT_ALLOWED", "CONTROLLER_BUSY",
        "CONTROLLER_OBSERVATION_INCOMPLETE", "CONTROLLER_SOURCE_MISMATCH",
        "CONTROLLER_EXECUTABLE_MISMATCH", "CONTROLLER_CHILD_START_FAILED", "CONTROLLER_CHILD_TIMEOUT",
        "CONTROLLER_CAPTURE_INCOMPLETE", "CONTROLLER_CHILD_REAP_UNRESOLVED",
        "CONTROLLER_HANDOFF_UNRESOLVED", "CONTROLLER_CLEANUP_UNRESOLVED", "PROOF_UNRESOLVED"]
    contract = {
        "phase_id": "SYNTH.EXEC.PREP.CONTROLLER.CONTRACT.1",
        "schema_version": "synthetic_execution_preparation_controller_contract_1_v1",
        "artifact_kind": "pure_additive_retained_preparation_controller_protocol_contract",
        "typed_result": RESULT, "completion_marker": RESULT, "protocol_frozen": True,
        "result_meaning": "The additive retained-live preparation controller protocol is frozen. No controller implementation, workspace or operational capability exists.",
        "implementation_authorized": False, "owners_implemented": False,
        "controller_implemented": False, "workspace_exists_by_this_phase": False,
        "capabilities_issued": False, "behavioral_activation_ready": False,
        "runtime_consumption_ready": False, "reason": "PROOF_UNRESOLVED", "stop_after_contract": True,
        "foundation": {"workspace_contract": WORKSPACE, "preparation_contract": PREP,
            "workspace_result_preserved": workspace["typed_result"],
            "image_identity": workspace["foundation"]["image_identity"],
            "sandbox_profile": workspace["foundation"]["sandbox_profile"],
            "sandbox_policy_sha256": workspace["foundation"]["sandbox_policy_sha256"],
            "sandbox": deepcopy(prep["sandbox"]),
            "additional_unchanged_inspection_pins": deepcopy(workspace["foundation"]["additional_unchanged_inspection_pins"]),
            "scenario": deepcopy(prep["scenario"]), "dimensions_widened": [],
            "historical_controller": deepcopy(workspace["controller_boundary"]["historical_controller"]),
            "historical_provider_is_live_authority": False},
        "identity": {
            "conceptual_owner": "core.synthetic_execution_preparation_controller_pinned",
            "protocol_id": PROTOCOL, "python_class_frozen": False,
            "source_bytes": None, "source_sha256": None, "source_size_bytes": None,
            "normalized_executable": "/usr/local/bin/python", "resolved_executable": "/usr/local/bin/python3.12",
            "interpreter_sha256": "0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263",
            "interpreter_authenticates_new_source": False, "missing_source_identity_permits_readiness": False,
            "must_bind": ["protocol ID/schema", "exact controller source bytes/SHA256/size",
                "normalized/resolved executable paths and interpreter SHA256", "immutable image identity",
                "sandbox profile/policy and exact configuration/environment/resources",
                "issuing/owning host process and exact original workspace object relation",
                "actual full container identity and backend generation relation", "controller incarnation/generation",
                "workspace generation", "launch/bootstrap arguments", "closed environment",
                "stdin/stdout/stderr or other transport endpoint/session identity",
                "protocol framing/version", "resource/capture limits", "cleanup responsibility"],
            "no_historical_repin": True,
        },
        "authority_separation": {
            "independent_boundaries": ["controller protocol", "workspace capability", "preparation authority",
                "preparation receipt", "runtime activation authority", "consumer authority"],
            "workspace_owner": WORKSPACE_OWNER,
            "workspace_type": workspace["exact_live_object"]["type"],
            "workspace_schema": workspace["exact_live_object"]["schema"],
            "preparation_owner": PREPARATION_OWNER,
            "permission_decision_owner": "appropriate original capability owner only",
            "controller_decides_policy_permission": False, "controller_spends_authority": False,
            "admission": "Owning boundary authenticates and spends its own exact facet where required, then supplies a separately authenticated single-operation admission bound to exact originals, tag, attempt, generations, observation and local fence. Controller checks only this authenticated relation and its local operational predicates; it cannot replace owner validation, issue permission or spend/refund facets.",
            "scalar_admission_id_is_authority": False,
            "receipt_is_workspace_or_runtime_authority": False,
        },
        "transport": {
            "architecture": None, "concrete_transport": None, "launch_bootstrap_argv": None,
            "status": "IMPLEMENTATION_SELECTION_DEFERRED",
            "reason": "Repository proves only a historical one-shot in-container controller plus host supervisor that always removes it. No retained transport/launch evidence yet selects an inner persistent process or host-supervised fixed operations truthfully.",
            "logical_responsibilities": ["retained generation-local observation/admission fence",
                "bounded fixed preparation children/captures", "independent host/control-plane teardown/absence observer"],
            "requirements": ["authenticate exact source/executable/protocol and host/container/endpoint relation",
                "observable exact controller incarnation/generation; bind all channel endpoints and closed env",
                "complete bounded canonical typed messages; no caller commands or generic attach/exec",
                "detect disconnect, truncation, extra frames, endpoint replacement and generation loss",
                "no reconnection resurrects lost generation; permanent invalidity and outer cleanup",
                "prove containment inspection/SANDBOX.2 controller gates without changing historical pins"],
            "unselected_transport_grants_readiness": False,
        },
        "operations": operations,
        "minimum_operation_review": {
            "accepted_tags": [item["tag"] for item in operations],
            "observations_distinct": "Empty verifies issuance predicate; current authenticates stage-appropriate state; prepared verifies exact original receipt/artifacts for handoff. All share one complete snapshot schema, never a generic file-read API.",
            "cleanup_split": "BEGIN_CLEANUP must preempt without waiting for active effect completion; CLEANUP_AND_REPORT completes bounded teardown/evidence. Both belong to one monotonic cleanup duty.",
            "scenario_JVM_dispatch_included": False,
            "forbidden_surfaces": ["shell", "caller command string", "arbitrary argv", "arbitrary environment",
                "Docker CLI passthrough", "generic file read/write", "generic subprocess execution",
                "generic Java execution", "generic class loading", "generic reflection", "arbitrary path"],
        },
        "bounds": {
            "preparation_attempt": {key: prep["compiler"][key] for key in (
                "max_attempts", "compiler_stdout_max_bytes", "compiler_stderr_max_bytes",
                "outer_stdout_max_bytes", "outer_stderr_max_bytes", "outer_timeout_ms", "shared_controller_deadline_ms")},
            "attempt_budget_scope": "One monotonic 5000ms deadline starts at materialization admission and includes materialize, compile, in-attempt observations and intervening time; never reset per operation. Outer preparation attempt hard timeout 10000ms. Total outer stdout/stderr each <=8192 over all attempt frames, not 8192 per unlimited frame. Retained lifetime is not this attempt budget and confers no indefinite readiness.",
            "observation": {"timeout_ms": 5000, "outer_timeout_ms": 10000,
                "request_max_bytes": 8192, "response_max_bytes": 8192,
                "work_entries_max": 3, "tmp_entries_max": 0, "process_tasks_max": 128,
                "regular_file_bytes_max": 33007, "writer_records_max": 128,
                "writer_handles_max": 128, "mount_records_max": 2},
            "cleanup": {"outer_timeout_ms": 10000, "response_max_bytes": 8192,
                "automatic_retry_max": 0, "explicit_retry_scope": "bounded same original identity only; permanent invalidity"},
            "limit_rule": "All limits are ceilings, never permission to expand PREP/SANDBOX.2. Full metadata/inventory exceeding any bound is incomplete, never a truncated successful snapshot. All tasks/threads count against pids128; no first-N process sample. Timeout/overflow denies success and invokes bounded cleanup.",
            "retention": "Exclusive workspace remains only until completion/abort/timeout/abandonment/upstream loss. No new retained lifetime numeric duration is preauthorized; future owner must enforce separately reviewed bounded lifetime policy before readiness.",
        },
        "observations": {
            "source_observations_only": True, "mutates_workspace": False,
            "single_bounded_current_generation_snapshot": True,
            "workspace_state_digest": deepcopy(workspace["workspace_state_digest"]),
            "required_observations": ["container identity/generation", "controller identity/generation",
                "/work mount identity", "/tmp mount identity", "complete descriptor-relative no-follow manifests",
                "file kinds", "link counts", "regular file sizes and full SHA256",
                "unexpected mount crossings", "process and task inventory", "writer/exclusivity inventory",
                "cleanup barrier sequence", "active operation/handoff identity"],
            "freshness_bindings": ["workspace_capability_id", "controller_generation", "workspace_generation",
                "observation_sequence", "owner_challenge", "requested_operation", "requested_purpose", "complete_observed_state"],
            "owner_challenge": {"issuer": WORKSPACE_OWNER, "random_bytes": 32,
                "encoding": "64 lowercase hex characters", "fresh_unpredictable_single_use": True,
                "sequence": "strictly owner-monotonic for original live relation; never reset/wrap within generation",
                "verification": "Owner matches outstanding exact operation/purpose/generations/sequence/challenge and original object/controller relation before independently authenticating full observations. No caller challenge and no replay."},
            "workspace_owner_independently_authenticates": True,
            "controller_digest_is_workspace_HMAC": False, "controller_digest_is_readiness": False,
            "challenge_proves_daemon_continuity": False,
            "continuity_limit": "Fresh challenge proves current response only by separately authenticated exact retained controller relation. Backend route/version/name equality and cryptographic freshness do not prove daemon continuity or eliminate ABA; unobservable generation continuity is PROOF_UNRESOLVED.",
            "forbidden_shortcuts": ["caller booleans", "directory listing alone", "timestamp alone",
                "replayed observation", "unchanged manifest", "container name", "scalar digest"],
            "tmp_entries_policy": "No /tmp infrastructure entries are accepted by this protocol. Nonempty /tmp invalidates its closed input envelope; any future exception needs a separately reviewed fixed operation and cannot become compiler input.",
            "failure_status": "CONTROLLER_OBSERVATION_INCOMPLETE or PROOF_UNRESOLVED",
        },
        "materialization": {
            "frozen_effect": deepcopy(prep["materialization"]),
            "source_identity": {"sha256": prep["scenario"]["source_sha256"], "size_bytes": 239},
            "sequence": ["owner authenticates existing frozen source and spends exact materialization facet",
                "controller final same-generation fence admission with complete empty current snapshot",
                "descriptor-relative exclusive /work/classes mkdir; no preexisting path even if identical",
                "descriptor-relative binary exclusive /work/SyntheticStateBox.java creation",
                "write exactly original authenticated 239 bytes from frozen source relation, never caller bytes",
                "full bounded no-follow readback verifies exact bytes/size/hash and single link",
                "observe complete exact materialized manifest and same generation; retain cleanup pending"],
            "source_projection": "Existing source owner accessor is a future authenticated in-memory projection only, not a protocol payload/source upload. This contract reads AST source identity and writes no Java file.",
            "fsync_required": False, "fsync_basis": "No frozen repository/runtime convention requires it; ephemeral tmpfs with full readback, not persistence.",
            "compile_in_materialize": False, "failure_spends_facet": True,
        },
        "compilation": {
            "compiler": deepcopy(prep["compiler"]), "compile_output": deepcopy(prep["compile_output"]),
            "runtime_state_required": "ISSUED", "classes_directory_recreation_allowed": False,
            "class_loading_allowed": False, "behavior_success_claimed": False,
            "revalidate": "Immediately before launch, exact same-attempt source/readback/manifest and original generations under local fence plus separately authenticated owner admission. If owner ISSUED continuity at effect cannot be observed, PROOF_UNRESOLVED before launch.",
            "postprocess": "Fully reap compiler and observe both EOFs; verify unchanged source and exact single-class envelope; full class hash and inert bounded classfile metadata identity only. No target load/link/initialize, JVM dispatch, reflection or SyntheticStateBox instance.",
        },
        "handoff": {
            "kind": "controller-local exclusive reservation/binding only",
            "bindings": ["workspace_generation", "controller_generation", "preparation_attempt_id",
                "preparation_receipt_id", "exact_artifact_manifest", "authenticated_future_borrower_identity"],
            "consumer_type": None, "consumer_schema": None, "activation_status": "PROOF_UNRESOLVED",
            "consumer_authority_granted": False, "artifact_export_allowed": False,
            "generation_transfer_allowed": False, "target_activation_allowed": False,
            "current_admission": "No consumer contract/borrower authenticator exists, so current request cannot establish reservation or activation. Freeze conditional semantics only, never a placeholder borrower token.",
        },
        "serialization": {
            "controller_local_admission_fence": True,
            "max_active_mutation_or_exclusive_handoff": 1,
            "observation_races_mutation": False,
            "snapshot_boundary": "Acquire local fence, verify exact generations and owner admission, inspect complete state without mutation/writer race, bind result to same fence epoch. If coherence cannot be observed fail unresolved; read-only inventory is not an external writer lock.",
            "cleanup_started_monotonic": True,
            "after_cleanup_reject": ["materialize", "compile", "new handoff", "preparation observation as ready"],
            "cleanup_preempts_busy": True,
            "active_on_cleanup": "Set barrier and revoke success publication under fence first; cancel/terminate active child group or write, fully reap, close/EOF captures, cancel reservation, then continue outer teardown. Never publish raced readiness. Cleanup bypasses BUSY.",
            "duplicate_or_replay": "Reject repeated operation/request/admission IDs, consumed challenges and stale sequences. Never rerun a mutation even if previous response lost; mark outcome unresolved and clean. Cleanup barrier/teardown may be re-observed with a fresh cleanup request and bounded same-identity retry only.",
        },
        "coordination": {
            "cross_owner_transaction_claimed": False, "private_lock_bridge_allowed": False,
            "sequence": ["workspace owner authenticates original retained graph and fresh exact-generation current state",
                "preparation owner independently authenticates own originals/facet and runtime ISSUED report",
                "preparation owner spends exact one-shot facet and authenticates fixed-operation admission bound to same state/generation/fence",
                "controller final local admission checks generation/fence/barrier/current state and exact admitted operation",
                "if any relevant owner precondition can change across unobservable gap, abort before effect with PROOF_UNRESOLVED",
                "perform fixed effect only after all relevant observable admission predicates; no owner lock sharing",
                "post-observe complete same-generation state/captures/reaping under fence; owning boundary authenticates evidence",
                "late loss suppresses success/receipt/readiness, no facet refund; mandatory independent cleanup"],
            "runtime_owner_unchanged": True,
            "report_only_runtime_check_is_reservation": False,
            "coordination_implementation_proven": False,
        },
        "cleanup": {
            "required_after": deepcopy(workspace["cleanup"]["required_after"]),
            "normal_sequence": ["set cleanup-started barrier; terminal readiness withdrawal",
                "deny new work/handoff and cancel active operations", "kill active bounded children/process groups",
                "fully reap children/groups", "close captures/pipes/selectors; observe EOF",
                "invoke independent outer fixed removal of exact container/workspace",
                "fresh independent absence verification; exact /work and /tmp generation gone",
                "return bounded composite evidence; preserve unresolved components truthfully"],
            "inner_can_remove_self_and_report_absence": False,
            "outer": {
                "owner_role": "independently authorized fixed host/control-plane cleanup custodian",
                "operations": ["TERMINATE_REMOVE_EXACT_RETAINED_GENERATION", "OBSERVE_EXACT_RETAINED_GENERATION_ABSENCE"],
                "target": "Retained authenticated immutable full original container ID/backend and workspace/controller generation relation, never name or caller ID alone; independently prove safe targeting on current control plane or fail unresolved.",
                "requires_workspace_readiness": False, "requires_runtime_ISSUED": False,
                "requires_unspent_preparation_facet": False, "requires_inner_controller_challenge": False,
                "input_projection": ["retained_authenticated_cleanup_relation_id", "fresh_cleanup_request_id"],
                "generic_Docker_command_authority": False,
                "may_create_or_restore": False,
                "bounds": "Fixed 10000ms invocation deadline and <=8192-byte bounded response, no automatic retry. Explicit same-identity cleanup retry never restores readiness.",
                "absence": "Fresh independent exact same-backend full-ID inspect/absence observation with authenticated observer identity/method and generation relation. Removal exit status, transient inspect failure, name absence or inner self-report alone insufficient.",
                "identity_target_failure": "WORKSPACE_CLEANUP_UNRESOLVED",
                "lost_inner_evidence": "Kill/remove/absence must still be attempted safely after inner loss. Unknown child/group reap or capture EOF stays unresolved even if container absent; never fabricate composite cleanup success.",
            },
            "evidence_fields": ["original_workspace_capability_id", "original_workspace_generation",
                "original_controller_identity", "original_controller_generation", "original_full_container_identity",
                "original_backend_relation", "preparation_attempt_id", "handoff_identity",
                "cleanup_barrier_sequence", "children_and_process_group_results", "capture_closure_and_EOF",
                "remove_result", "fresh_independent_absence_observation", "observer_method_and_identity",
                "work_and_tmp_generation_gone", "no_surviving_artifact_export", "typed_unresolved_components"],
            "evidence_is_preparation_success": False, "evidence_is_behavior_success": False,
            "evidence_is_future_authority": False,
            "workspace_failure_status": "WORKSPACE_CLEANUP_UNRESOLVED",
        },
        "framing": {
            "protocol_id": PROTOCOL, "version": 1,
            "canonical_types": workspace["authentication"]["canonical_types"],
            "canonical_payload_encoding": workspace["authentication"]["canonical_encoding"],
            "wire_transport_frozen": False,
            "framing_requirement": "Exactly one length-delimited canonical typed payload per request/response with unambiguous length/version/endpoint relation. Concrete transport prefix/encoding is deferred; reject overlong, trailing, partial, duplicate, unexpected or multiplexed frames before any effect. Never caller text commands.",
            "request_max_bytes": 8192, "response_max_bytes": 8192,
            "request_fields": {"protocol_id": "constant_protocol", "version": "constant_int_1",
                "operation": "closed_operation_enum", "request_id": "id", "operation_id": "id",
                "workspace_capability_id": "id", "container_identity": "id",
                "workspace_generation": "id", "controller_generation": "id",
                "sequence": "positive_int", "challenge": "challenge_or_null_by_operation",
                "purpose": "same_closed_operation_tag", "admission_relation_id": "id",
                "payload": "exact_per_operation_input_projection"},
            "response_fields": {"protocol_id": "constant_protocol", "version": "constant_int_1",
                "operation": "closed_operation_enum", "request_id": "exact_request_id",
                "operation_id": "exact_operation_id", "workspace_capability_id": "exact_request_workspace_id",
                "container_identity": "exact_original_full_container_identity",
                "workspace_generation": "exact_request_generation", "controller_generation": "exact_request_generation",
                "sequence": "exact_request_sequence", "challenge": "exact_request_challenge",
                "purpose": "exact_request_purpose", "status": "status_enum",
                "result": "exact_per_operation_result_or_null", "error": "typed_error_or_null"},
            "operation_payloads_closed": True,
            "primitive_rules": {"id": "exact str, nonempty, <=256 UTF-8 bytes, no NUL; reference only to authenticated original relation, never restore authority from string",
                "positive_int": "exact int in 1..9223372036854775807; bool rejected; no wrap/reuse",
                "challenge": "exact str, 64 lowercase hex chars from owner 32 unpredictable bytes; required for three observation tags; null for other tags, whose admission still binds final observation",
                "json": "Reject duplicate/missing/unknown keys at every nesting, nonfinite/float values, unknown enum, coercion and unsupported types; exact schema str/int/bool/null/list/dict only.",
                "status_enum": ["COMPLETE", "REJECTED", "FAILED", "PROOF_UNRESOLVED"],
                "cleanup_reason_enum": ["preparation_failure", "consumer_failure", "activation_failure", "timeout",
                    "abandonment", "upstream_invalidation", "normal_completion", "controller_loss"]},
            "result_schemas": {
                "observation": ["workspace_state", "cleanup_barrier_sequence", "active_operation_id", "handoff_identity"],
                "materialize": ["workspace_state", "preparation_attempt_id", "source_readback_size", "source_readback_sha256", "source_readback_exact"],
                "compile": ["workspace_state", "preparation_attempt_id", "compiler_identity", "capture_and_reap", "class_metadata"],
                "handoff": ["reservation_identity", "reservation_bindings", "activation_status"],
                "begin_cleanup": ["cleanup_barrier_sequence", "cancelled_operation_id", "outer_teardown_required"],
                "cleanup": ["cleanup_evidence"],
            },
            "nested_schema_rule": "message_schema.json freezes every exact closed nested record and cross-field predicate as declarative data. Workspace state uses unchanged digest payload fields plus the full mount/manifest/process source observations within those fields. No raw source/class/capture bytes or arbitrary maps. Wire transport prefix remains deferred; semantic schemas are frozen here.",
            "success_rule": "COMPLETE requires exactly complete bounded operation-specific evidence, null error, matched IDs/generations/sequence/challenge/purpose, and all postconditions. Other statuses carry exact typed error and null result, except cleanup operations may carry bounded partial cleanup evidence with explicit unresolved components. Partial cleanup evidence never claims completion/readiness. COMPLETE never means owner readiness or behavior success; BEGIN_CLEANUP completion only means barrier recorded.",
            "error_fields": {"layer": "controller|workspace|preparation|provider|runtime",
                "code": "closed originating layer enum", "origin_status": "exact originating status",
                "origin_reason": "exact bounded originating reason", "authenticated_origin_relation_id": "id_or_null",
                "operation_id": "exact_operation_id", "cleanup_required": "exact_bool",
                "detail_id": "closed controller reason enum in message_schema.json"},
        },
        "authentication": {
            "protocol_is_authority": False,
            "future_workspace_owner_binds_exact_controller": True,
            "original_workspace_authentication": deepcopy(workspace["authentication"]),
            "controller_evidence": "Only semantics frozen: exact original source/executable/protocol/incarnation/host/container/generation/transport/bootstrap/configuration and bounded observations; independently authenticated by future workspace owner. No separately signed controller receipt type or issuer is required/frozen here, and none is issued.",
            "secret_reuse_forbidden": ["provider", "preparation", "runtime", "reflection", "SANDBOX.2"],
            "secret_or_signature_created": False,
        },
        "errors": {"controller_codes": errors,
            "classification": "Controller authentication/source/executable/protocol/generation failures describe controller layer only. Existing provider/workspace/preparation/runtime semantic failures retain original layer and exact typed code; never rebrand as CONTROLLER_UNAUTHENTICATED.",
            "busy_exception": "CONTROLLER_BUSY applies to ordinary operations only, never BEGIN_CLEANUP/mandatory teardown.",
            "observation_failure": "Incomplete full inventory/capture/coherence/response is failure, never ready. Unobservable owner/generation continuity is PROOF_UNRESOLVED.",
            "cleanup_mapping": "Keep CONTROLLER_CLEANUP_UNRESOLVED evidence separate; workspace owner may report its existing WORKSPACE_CLEANUP_UNRESOLVED without erasing root cause."},
        "harness_boundary": {"scenario_JVM_dispatch": False, "full_harness_source": False,
            "scenario_main_class": None, "scenario_JVM_argv": None,
            "behavioral_loader_protocol": None, "BEFORE_AFTER_runtime_protocol": None,
            "runtime_fail_closed_preserved": True},
        "authority_flags": {key: False for key in set(workspace["authority_flags"]) | {
            "controller_implementation", "workspace_issuance", "container_creation", "source_materialization",
            "scenario_compilation", "runtime_activation", "reflection", "repository_write", "Apply", "network",
            "host_mount", "shell", "arbitrary_command", "arbitrary_Java", "arbitrary_filesystem", "executor", "BANK"}},
        "operational_effects": {key: 0 for key in set(workspace["operational_effects"]) | {
            "Docker", "container_creation", "container_removal", "SANDBOX2", "JAVA1C", "provider_issuance",
            "auth_issuance", "runtime_issuance", "reflection_issuance", "workspace_issuance",
            "preparation_authority_issuance", "source_materialization", "javac", "java", "class_loading",
            "reflection", "SyntheticStateBox", "BANK", "EXECUTOR.1R", "Apply"}},
        "effect_counter_scope": "Required zero by design plus measured pure-validation guards; described future effects are not run or issued by this phase.",
        "historical_preservation": {"all_prior_noncache_bytes_unchanged": True,
            "no_repin": True, "no_stash_reset_clean": True,
            "historical_controller_API_or_cleanup_changed": False,
            "immutable_foundations": ["core.sandboxed_java_positive_probe", "core.sandboxed_java_positive_continuation",
                "SANDBOX.2", "JAVA.1C", "PINNED provider chain", "pinned auth/runtime/reflection owners",
                "PREP closure", "workspace contract", "historical receipts"]},
        "unresolved": ["new controller source bytes/SHA256/size and implementation",
            "concrete retained architecture/transport/bootstrap satisfying frozen semantic message schemas",
            "truthful live controller/backend generation continuity and independent cleanup targeting",
            "observable effect coordination without private cross-owner locks",
            "authorized bounded retained lifetime and live workspace/preparation owner implementation",
            "separately reviewed harness/consumer/borrower authentication and activation"],
    }
    # Sort unordered flag sets so repeated source-only authoring is deterministic.
    for key in ("authority_flags", "operational_effects"):
        contract[key] = dict(sorted(contract[key].items()))
    contract["framing"]["semantic_schema_file"] = "message_schema.json"
    write("message_schema.json", message_schema(contract))
    write("contract.json", contract)
    previous = read(PREFIX + "SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/evidence_index.json")
    paths = sorted({item["path"] for item in previous["sources"]} | {WORKSPACE, PREP})
    sources = []
    for name in paths:
        raw = (ROOT / name).read_bytes()
        lines = raw.decode("utf-8-sig").splitlines()
        if name.endswith(".py"):
            tree = ast.parse("\n".join(lines), filename=name)
            anchors = [{"line": node.lineno, "end_line": node.end_lineno,
                "name": node.name, "text": lines[node.lineno - 1]}
                for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
        else:
            anchors = [{"line": i, "text": line[:240]} for i, line in enumerate(lines, 1)
                if any(word in line for word in ('"compiler"', '"cleanup"', '"controller_boundary"',
                    '"workspace_state_digest"', '"atomicity_and_races"', '"initial_workspace"'))]
        sources.append(dict(path=name, sha256=sha256(raw).hexdigest(), bytes=len(raw), anchors=anchors))
    write("evidence_index.json", {"method": "source/JSON/AST only; no owner import or operation",
        "sources": sources, "historical_metadata_is_current_liveness": False})


if __name__ == "__main__":
    main()
