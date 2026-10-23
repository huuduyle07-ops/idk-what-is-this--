"""Pure JSON/raw-source/AST protocol checks; never import an operational owner.

Existing Java and historical controller bytes are inspected as in-memory data.
No controller, container, workspace, compiler, capability or consumer is run.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path


PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
PREP = "docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1/contract.json"
WORKSPACE = "docs/roadmap/phases/SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/contract.json"
PROTOCOL = "synthetic_preparation_controller_pinned_1_v1"
WORKSPACE_OWNER = "core.synthetic_execution_preparation_workspace_pinned"
PREPARATION_OWNER = "core.synthetic_execution_preparation_pinned"
TAGS = {
    "OBSERVE_EMPTY_WORKSPACE", "OBSERVE_CURRENT_WORKSPACE", "OBSERVE_PREPARED_ARTIFACTS",
    "MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO",
    "PREPARE_EXCLUSIVE_HANDOFF", "BEGIN_CLEANUP", "CLEANUP_AND_REPORT",
}
OBSERVATION_TAGS = {tag for tag in TAGS if tag.startswith("OBSERVE_")}


def no_duplicates(pairs):
    result = {}
    for name, value in pairs:
        assert name not in result, "duplicate JSON key: " + name
        result[name] = value
    return result


def reject_nonfinite(value):
    raise AssertionError("nonfinite JSON number: " + value)


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"),
                      object_pairs_hook=no_duplicates, parse_constant=reject_nonfinite)


def contract():
    return read_json(str((PHASE / "contract.json").relative_to(ROOT)))


def source(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def tree(path):
    return ast.parse(source(path), filename=path)


def definition(path, name):
    matches = [node for node in tree(path).body
               if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name]
    assert len(matches) == 1, (path, name)
    return matches[0]


def literal(path, name):
    matches = [node.value for node in tree(path).body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    assert len(matches) == 1, (path, name)
    return ast.literal_eval(matches[0])


def text(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def operations():
    items = contract()["operations"]
    assert len(items) == len(TAGS)
    result = {item["tag"]: item for item in items}
    assert len(result) == len(items) and set(result) == TAGS
    return result


def message_schema():
    return read_json(str((PHASE / "message_schema.json").relative_to(ROOT)))


def generated_historical_controller():
    """Reproduce historical fixed text assembly as data, executing no owner."""
    path = "core/java_single_thread_capture.py"
    capture = definition(path, "capture_process")
    lines = source(path).splitlines(keepends=True)
    captured_text = "".join(lines[capture.lineno - 1:capture.end_lineno])
    if not captured_text.endswith("\n"):
        captured_text += "\n"
    fixture = "core/sandboxed_java_toolchain_probe.py"
    values = {name: literal(fixture, name) for name in (
        "JAVA_SOURCE", "EXPECTED_OUTPUT", "COMPILE_ARGUMENTS", "RUNTIME_ARGUMENTS")}
    values.update({name: literal("core/sandboxed_java_single_thread_probe.py", name)
                   for name in ("JAVAC_PATH", "JAVAC_SHA256")})
    values.update({name: literal("core/thread_compatible_runtime_sandbox_probe.py", name)
                   for name in ("JAVA_PATH", "JAVA_SHA256")})
    values["SOURCE_SHA256"] = literal("core/sandboxed_java_positive_probe.py", "SOURCE_SHA256")
    values["COMPILE_ARGV"] = (values["JAVAC_PATH"], *values["COMPILE_ARGUMENTS"])
    values["RUNTIME_ARGV"] = (values["JAVA_PATH"], *values["RUNTIME_ARGUMENTS"])
    names = ("JAVA_SOURCE", "EXPECTED_OUTPUT", "SOURCE_SHA256", "JAVAC_PATH", "JAVAC_SHA256",
             "JAVA_PATH", "JAVA_SHA256", "COMPILE_ARGV", "RUNTIME_ARGV")
    return ("import base64, hashlib, json, stat, sys, threading\n"
            + "import os, selectors, signal, subprocess, time\n" + captured_text + "\n"
            + "".join(name + " = " + repr(values[name]) + "\n" for name in names)
            + literal("core/sandboxed_java_positive_probe.py", "BODY")).encode("utf-8")


def test_completion_freezes_only_protocol_and_keeps_every_operational_gate_closed():
    value = contract()
    assert value["phase_id"] == "SYNTH.EXEC.PREP.CONTROLLER.CONTRACT.1"
    assert value["typed_result"] == value["completion_marker"] == "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1_COMPLETE"
    assert value["protocol_frozen"] is value["stop_after_contract"] is True
    assert value["reason"] == "PROOF_UNRESOLVED"
    for key in ("implementation_authorized", "owners_implemented", "controller_implemented",
                "workspace_exists_by_this_phase", "capabilities_issued", "behavioral_activation_ready",
                "runtime_consumption_ready"):
        assert value[key] is False, key
    for name in ("synthetic_execution_preparation_controller_pinned.py",
                 "synthetic_execution_preparation_workspace_pinned.py",
                 "synthetic_execution_preparation_pinned.py"):
        assert not (ROOT / "core" / name).exists(), name


def test_additive_identity_is_exact_but_has_no_invented_controller_source_pin():
    value = contract()["identity"]
    assert value["conceptual_owner"] == "core.synthetic_execution_preparation_controller_pinned"
    assert value["protocol_id"] == PROTOCOL and value["python_class_frozen"] is False
    for key in ("source_bytes", "source_sha256", "source_size_bytes"):
        assert value[key] is None, key
    assert value["normalized_executable"] == "/usr/local/bin/python"
    assert value["resolved_executable"] == literal("core/runtime_java_pinned_provider.py", "CONTROLLER_RESOLVED")
    assert value["resolved_executable"] == "/usr/local/bin/python3.12"
    assert value["interpreter_sha256"] == literal("core/runtime_java_pinned_provider.py", "CONTROLLER_SHA256")
    assert value["interpreter_sha256"] == "0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263"
    assert value["interpreter_authenticates_new_source"] is False
    assert value["missing_source_identity_permits_readiness"] is False
    assert value["no_historical_repin"] is True
    for term in ("source bytes/SHA256/size", "host process", "container identity", "incarnation/generation",
                 "workspace generation", "launch/bootstrap", "closed environment", "transport",
                 "framing/version", "resource/capture", "cleanup responsibility"):
        assert term in text(value["must_bind"]), term


def test_all_frozen_foundations_are_reused_without_rewriting_workspace_or_prep():
    value, prep, workspace = contract()["foundation"], read_json(PREP), read_json(WORKSPACE)
    assert value["preparation_contract"] == PREP and value["workspace_contract"] == WORKSPACE
    assert value["workspace_result_preserved"] == workspace["typed_result"] == "WORKSPACE_REQUIRES_CONTROLLER_EVOLUTION"
    assert value["image_identity"] == prep["compiler"]["image"] == "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a"
    assert value["sandbox_profile"] == prep["compiler"]["sandbox_profile"] == "runtime_sandbox_2_v1"
    assert value["sandbox_policy_sha256"] == prep["compiler"]["sandbox_policy_sha256"] == "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"
    assert value["sandbox"] == prep["sandbox"]
    assert value["scenario"] == prep["scenario"]
    assert value["additional_unchanged_inspection_pins"] == workspace["foundation"]["additional_unchanged_inspection_pins"]
    assert value["historical_controller"] == workspace["controller_boundary"]["historical_controller"]
    assert value["dimensions_widened"] == [] and value["historical_provider_is_live_authority"] is False


def test_controller_permission_workspace_receipt_runtime_and_consumer_remain_separate():
    value = contract()["authority_separation"]
    assert value["independent_boundaries"] == ["controller protocol", "workspace capability",
        "preparation authority", "preparation receipt", "runtime activation authority", "consumer authority"]
    workspace = read_json(WORKSPACE)["exact_live_object"]
    assert value["workspace_owner"] == WORKSPACE_OWNER
    assert value["workspace_type"] == workspace["type"] == "PinnedSyntheticPreparationWorkspace"
    assert value["workspace_schema"] == workspace["schema"] == "synthetic_preparation_workspace_pinned_1_v1"
    assert value["preparation_owner"] == PREPARATION_OWNER
    for key in ("controller_decides_policy_permission", "controller_spends_authority",
                "scalar_admission_id_is_authority", "receipt_is_workspace_or_runtime_authority"):
        assert value[key] is False, key
    for term in ("separately authenticated", "single-operation admission", "exact originals", "generations",
                 "local fence", "cannot replace owner validation", "spend/refund facets"):
        assert term in value["admission"], term


def test_exact_eight_operations_are_closed_and_each_has_full_effect_contract():
    items, value = operations(), contract()
    required = {"tag", "required_admission_owner", "permissible_predicates", "input_projection",
                "fixed_paths", "allowed_subprocess", "bounds_profile", "postconditions", "failure_behavior",
                "cleanup_interaction", "controller_spends_authority", "downstream_requirement"}
    for tag, item in items.items():
        assert set(item) == required, tag
        assert item["required_admission_owner"] and item["permissible_predicates"], tag
        assert type(item["input_projection"]) is dict and type(item["fixed_paths"]) is list
        assert item["postconditions"] and item["failure_behavior"] and item["cleanup_interaction"]
        assert item["bounds_profile"] in value["bounds"]
        assert item["controller_spends_authority"] is False
        assert PREP in item["downstream_requirement"] or WORKSPACE in item["downstream_requirement"]
    review = value["minimum_operation_review"]
    assert set(review["accepted_tags"]) == TAGS and len(review["accepted_tags"]) == len(TAGS)
    assert review["scenario_JVM_dispatch_included"] is False
    assert set(review["forbidden_surfaces"]) == {"shell", "caller command string", "arbitrary argv",
        "arbitrary environment", "Docker CLI passthrough", "generic file read/write", "generic subprocess execution",
        "generic Java execution", "generic class loading", "generic reflection", "arbitrary path"}


def test_only_compilation_has_child_argv_and_no_operation_accepts_effect_parameters():
    items = operations()
    compiler = read_json(PREP)["compiler"]
    for tag, item in items.items():
        assert item["allowed_subprocess"] == (compiler["exact_scenario_argv"] if tag == "COMPILE_EXACT_SCENARIO" else None)
        assert set(item["input_projection"]) <= {"preparation_attempt_id", "preparation_receipt_id",
            "authenticated_borrower_relation_id", "cleanup_reason"}
        assert all(value in {"id", "cleanup_reason_enum"} for value in item["input_projection"].values())
        assert set(item["fixed_paths"]) <= {"/work", "/tmp", "/work/classes",
            "/work/SyntheticStateBox.java", "/work/classes/SyntheticStateBox.class"}
    for tag in OBSERVATION_TAGS:
        assert items[tag]["required_admission_owner"] == WORKSPACE_OWNER
        assert items[tag]["bounds_profile"] == "observation"
    for tag in ("MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO"):
        assert items[tag]["required_admission_owner"] == PREPARATION_OWNER
        predicates = text(items[tag]["permissible_predicates"])
        assert "already spent/admitted" in predicates and "ISSUED" in predicates


def test_three_observations_keep_empty_current_and_prepared_semantics_distinct():
    items = operations()
    empty = items["OBSERVE_EMPTY_WORKSPACE"]
    current = items["OBSERVE_CURRENT_WORKSPACE"]
    prepared = items["OBSERVE_PREPARED_ARTIFACTS"]
    assert empty["input_projection"] == current["input_projection"] == {}
    assert prepared["input_projection"] == {"preparation_attempt_id": "id", "preparation_receipt_id": "id"}
    assert "/work/classes absent" in text(empty["postconditions"])
    assert "partial progress is neither preparation-empty nor prepared-artifacts-present" in text(current["postconditions"])
    assert "never caller stage" in text(current["postconditions"])
    assert "original same-attempt receipt" in text(prepared["postconditions"])
    assert "cleanup pending" in text(prepared["permissible_predicates"])
    assert "no consumer readiness" in text(prepared["postconditions"])


def test_observation_is_complete_bounded_source_evidence_and_never_scalar_authority():
    value = contract()["observations"]
    assert value["source_observations_only"] is value["single_bounded_current_generation_snapshot"] is True
    assert value["mutates_workspace"] is False
    assert value["workspace_state_digest"] == read_json(WORKSPACE)["workspace_state_digest"]
    assert set(value["required_observations"]) == {"container identity/generation", "controller identity/generation",
        "/work mount identity", "/tmp mount identity", "complete descriptor-relative no-follow manifests",
        "file kinds", "link counts", "regular file sizes and full SHA256", "unexpected mount crossings",
        "process and task inventory", "writer/exclusivity inventory", "cleanup barrier sequence",
        "active operation/handoff identity"}
    assert value["workspace_owner_independently_authenticates"] is True
    assert value["controller_digest_is_workspace_HMAC"] is value["controller_digest_is_readiness"] is False
    assert set(value["forbidden_shortcuts"]) >= {"caller booleans", "directory listing alone", "timestamp alone",
        "replayed observation", "unchanged manifest", "container name", "scalar digest"}
    assert "CONTROLLER_OBSERVATION_INCOMPLETE" in value["failure_status"]
    assert "PROOF_UNRESOLVED" in value["failure_status"]


def test_owner_challenge_binds_original_generation_sequence_purpose_and_complete_state():
    value = contract()["observations"]
    assert set(value["freshness_bindings"]) == {"workspace_capability_id", "controller_generation",
        "workspace_generation", "observation_sequence", "owner_challenge", "requested_operation",
        "requested_purpose", "complete_observed_state"}
    challenge = value["owner_challenge"]
    assert challenge["issuer"] == WORKSPACE_OWNER and challenge["random_bytes"] == 32
    assert challenge["encoding"] == "64 lowercase hex characters"
    assert challenge["fresh_unpredictable_single_use"] is True
    assert "never reset/wrap" in challenge["sequence"]
    for term in ("outstanding", "operation/purpose/generations/sequence/challenge", "original object/controller", "No caller challenge", "no replay"):
        assert term in challenge["verification"], term
    assert value["challenge_proves_daemon_continuity"] is False
    assert "ABA" in value["continuity_limit"] and "PROOF_UNRESOLVED" in value["continuity_limit"]


def test_materialization_uses_existing_exact_source_bytes_and_exclusive_fixed_paths():
    value, prep = contract()["materialization"], read_json(PREP)
    raw = literal("core/synthetic_runtime_authorization.py", "_SOURCE")
    assert type(raw) is bytes and len(raw) == 239
    assert sha256(raw).hexdigest() == "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
    assert value["source_identity"] == {"sha256": sha256(raw).hexdigest(), "size_bytes": len(raw)}
    assert value["frozen_effect"] == prep["materialization"]
    sequence = value["sequence"]
    assert "spends exact materialization facet" in sequence[0]
    assert "fence admission" in sequence[1]
    assert "/work/classes mkdir" in sequence[2] and "no preexisting path even if identical" in sequence[2]
    assert "exclusive /work/SyntheticStateBox.java creation" in sequence[3]
    assert "never caller bytes" in sequence[4]
    assert "no-follow readback" in sequence[5] and "bytes/size/hash" in sequence[5] and "single link" in sequence[5]
    assert "same generation" in sequence[6]
    assert value["compile_in_materialize"] is False and value["failure_spends_facet"] is True
    assert value["fsync_required"] is False and "No frozen repository/runtime convention" in value["fsync_basis"]


def test_compiler_identity_and_argv_come_from_frozen_source_without_new_flags():
    value, prep = contract()["compilation"], read_json(PREP)
    compiler = value["compiler"]
    assert compiler == prep["compiler"]
    path = literal("core/sandboxed_java_single_thread_probe.py", "JAVAC_PATH")
    historical = [path, *literal("core/sandboxed_java_toolchain_probe.py", "COMPILE_ARGUMENTS")]
    assert path == compiler["path"] == "/opt/temurin-26.0.2.1/bin/javac"
    assert compiler["sha256"] == literal("core/sandboxed_java_single_thread_probe.py", "JAVAC_SHA256")
    assert compiler["historical_JAVA_1C_argv"] == historical
    assert compiler["exact_scenario_argv"] == historical[:-1] + ["/work/SyntheticStateBox.java"]
    assert "-proc:none" not in compiler["exact_scenario_argv"]
    assert compiler["cwd"] == "/work" and compiler["shell"] is False
    for key in ("caller_flags_allowed", "argument_files_allowed", "arbitrary_classpath_allowed", "maven_allowed",
                "gradle_allowed", "dependency_download_allowed", "network_allowed", "processor_plugin_inputs_allowed"):
        assert compiler[key] is False, key
    assert value["runtime_state_required"] == "ISSUED"
    assert value["classes_directory_recreation_allowed"] is value["class_loading_allowed"] is False
    assert value["behavior_success_claimed"] is False
    assert "PROOF_UNRESOLVED before launch" in value["revalidate"]


def test_exact_environment_sandbox_and_attempt_capture_bounds_remain_frozen():
    value, prep = contract(), read_json(PREP)
    sandbox, compiler = value["foundation"]["sandbox"], value["compilation"]["compiler"]
    expected = literal("core/candidate_runtime_sandbox.py", "_WORKLOAD_ENVIRONMENT")
    assert sandbox["environment"] == expected and len(expected) == 8
    for variable in ("CLASSPATH", "JDK_JAVAC_OPTIONS", "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS"):
        assert variable not in expected
    assert sandbox["network"] == "none" and sandbox["host_mounts"] == []
    assert sandbox["rootfs_readonly"] is True and sandbox["uid_gid"] == "65534:65534"
    assert (sandbox["pids_max"], sandbox["memory_bytes"], sandbox["nano_cpus"]) == (128, 134217728, 1000000000)
    assert sandbox["tmpfs"] == {"/work": "rw,nosuid,nodev,size=32m,mode=1777", "/tmp": "rw,nosuid,nodev,noexec,size=16m,mode=1777"}
    bounds = value["bounds"]["preparation_attempt"]
    assert bounds == {key: prep["compiler"][key] for key in ("max_attempts", "compiler_stdout_max_bytes",
        "compiler_stderr_max_bytes", "outer_stdout_max_bytes", "outer_stderr_max_bytes", "outer_timeout_ms",
        "shared_controller_deadline_ms")}
    assert (bounds["max_attempts"], bounds["compiler_stdout_max_bytes"], bounds["compiler_stderr_max_bytes"]) == (1, 2048, 2048)
    assert (bounds["outer_stdout_max_bytes"], bounds["outer_stderr_max_bytes"], bounds["outer_timeout_ms"], bounds["shared_controller_deadline_ms"]) == (8192, 8192, 10000, 5000)
    assert compiler["outer_timeout_ms"] == literal("core/sandboxed_java_positive_continuation.py", "TIMEOUT_MS")
    assert compiler["shared_controller_deadline_ms"] == literal("core/sandboxed_java_positive_continuation.py", "ABORT_AFTER_MS")
    assert "never reset per operation" in value["bounds"]["attempt_budget_scope"]
    assert "over all attempt frames" in value["bounds"]["attempt_budget_scope"]


def test_observation_and_cleanup_bounds_never_allow_truncated_success_or_indefinite_retention():
    bounds = contract()["bounds"]
    observation = bounds["observation"]
    assert (observation["timeout_ms"], observation["outer_timeout_ms"]) == (5000, 10000)
    assert (observation["request_max_bytes"], observation["response_max_bytes"]) == (8192, 8192)
    assert (observation["work_entries_max"], observation["tmp_entries_max"], observation["process_tasks_max"]) == (3, 0, 128)
    assert observation["regular_file_bytes_max"] == 239 + 32768
    assert (observation["writer_records_max"], observation["writer_handles_max"], observation["mount_records_max"]) == (128, 128, 2)
    cleanup = bounds["cleanup"]
    assert (cleanup["outer_timeout_ms"], cleanup["response_max_bytes"], cleanup["automatic_retry_max"]) == (10000, 8192, 0)
    assert "never a truncated successful snapshot" in bounds["limit_rule"]
    assert "no first-N process sample" in bounds["limit_rule"]
    assert "separately reviewed bounded lifetime policy before readiness" in bounds["retention"]
    assert "Nonempty /tmp invalidates" in contract()["observations"]["tmp_entries_policy"]


def test_compile_output_is_one_inert_class_with_actual_hash_and_complete_eof_reaping():
    value = contract()["compilation"]
    output = value["compile_output"]
    assert output == read_json(PREP)["compile_output"]
    assert output["expected_relative_class_set"] == ["SyntheticStateBox.class"]
    assert output["expected_path"] == "/work/classes/SyntheticStateBox.class"
    assert (output["maximum_class_files"], output["minimum_class_bytes"], output["maximum_class_bytes"]) == (1, 1, 32768)
    assert output["predicted_class_sha256"] is None
    assert output["compile_success_proves_behavior_success"] is False
    for term in ("Fully reap", "both EOFs", "unchanged source", "full class hash", "inert bounded classfile metadata", "No target load/link/initialize"):
        assert term in value["postprocess"], term
    assert "complete empty captures and both EOFs" in text(operations()["COMPILE_EXACT_SCENARIO"]["postconditions"])


def test_handoff_is_only_conditional_local_reservation_with_no_consumer_identity_invented():
    value = contract()["handoff"]
    assert value["kind"] == "controller-local exclusive reservation/binding only"
    assert set(value["bindings"]) == {"workspace_generation", "controller_generation", "preparation_attempt_id",
        "preparation_receipt_id", "exact_artifact_manifest", "authenticated_future_borrower_identity"}
    assert value["consumer_type"] is value["consumer_schema"] is None
    assert value["activation_status"] == "PROOF_UNRESOLVED"
    for key in ("consumer_authority_granted", "artifact_export_allowed", "generation_transfer_allowed", "target_activation_allowed"):
        assert value[key] is False, key
    assert "current request cannot establish reservation or activation" in value["current_admission"]
    assert "never a placeholder borrower token" in value["current_admission"]
    required = text(operations()["PREPARE_EXCLUSIVE_HANDOFF"]["permissible_predicates"])
    for term in ("cleanup pending", "same source/class manifest", "no compiler/target process",
                 "captures complete/reaped", "no unexpected writer", "no active handoff or mutation", "not cleanup-started"):
        assert term in required, term


def test_transport_defers_implementation_and_cannot_reconnect_a_lost_generation():
    value = contract()["transport"]
    assert value["architecture"] is value["concrete_transport"] is value["launch_bootstrap_argv"] is None
    assert value["status"] == "IMPLEMENTATION_SELECTION_DEFERRED"
    assert value["unselected_transport_grants_readiness"] is False
    requirements = text(value["requirements"])
    for term in ("source/executable/protocol", "incarnation/generation", "channel endpoints", "closed env",
                 "disconnect", "truncation", "endpoint replacement", "no reconnection resurrects", "outer cleanup"):
        assert term in requirements, term


def test_controller_local_fence_serializes_mutations_and_cleanup_preempts_without_busy():
    value = contract()["serialization"]
    assert value["controller_local_admission_fence"] is True
    assert type(value["max_active_mutation_or_exclusive_handoff"]) is int
    assert value["max_active_mutation_or_exclusive_handoff"] == 1
    assert value["observation_races_mutation"] is False
    assert value["cleanup_started_monotonic"] is value["cleanup_preempts_busy"] is True
    assert set(value["after_cleanup_reject"]) == {"materialize", "compile", "new handoff", "preparation observation as ready"}
    for term in ("revoke success publication", "cancel/terminate", "fully reap", "close/EOF", "cancel reservation", "outer teardown", "Cleanup bypasses BUSY"):
        assert term in value["active_on_cleanup"], term
    for term in ("repeated operation/request/admission IDs", "consumed challenges", "stale sequences",
                 "Never rerun a mutation", "previous response lost", "bounded same-identity retry"):
        assert term in value["duplicate_or_replay"], term


def test_cross_owner_sequence_fails_unobservable_gaps_without_shared_locks_or_refund():
    value = contract()["coordination"]
    assert value["cross_owner_transaction_claimed"] is value["private_lock_bridge_allowed"] is False
    assert value["runtime_owner_unchanged"] is True
    assert value["report_only_runtime_check_is_reservation"] is value["coordination_implementation_proven"] is False
    sequence = value["sequence"]
    assert "workspace owner authenticates original" in sequence[0]
    assert "runtime ISSUED" in sequence[1]
    assert "spends exact one-shot facet" in sequence[2]
    assert "controller final local admission" in sequence[3]
    assert "unobservable gap, abort before effect with PROOF_UNRESOLVED" in sequence[4]
    assert "perform fixed effect only after" in sequence[5] and "no owner lock sharing" in sequence[5]
    assert "owning boundary authenticates evidence" in sequence[6]
    assert "late loss suppresses success/receipt/readiness" in sequence[7]
    assert "no facet refund" in sequence[7] and "independent cleanup" in sequence[7]


def test_cleanup_normal_sequence_is_terminal_and_keeps_independent_outer_verification():
    value = contract()["cleanup"]
    assert value["required_after"] == read_json(WORKSPACE)["cleanup"]["required_after"]
    assert set(value["required_after"]) == {"preparation failure", "consumer failure", "timeout",
        "runtime activation failure", "abandonment", "invalidated upstream"}
    assert value["inner_can_remove_self_and_report_absence"] is False
    sequence = value["normal_sequence"]
    assert "cleanup-started barrier" in sequence[0] and "readiness withdrawal" in sequence[0]
    for item, term in zip(sequence[1:], ("deny new work", "kill active", "fully reap", "observe EOF",
                                       "independent outer", "fresh independent absence", "unresolved components")):
        assert term in item, term
    for tag in ("BEGIN_CLEANUP", "CLEANUP_AND_REPORT"):
        item = operations()[tag]
        assert item["bounds_profile"] == "cleanup"
        assert "invalid" in text(item["permissible_predicates"]) or "cleanup-started" in text(item["permissible_predicates"])


def test_outer_teardown_can_target_only_retained_identity_without_upstream_readiness():
    value = contract()["cleanup"]["outer"]
    assert value["operations"] == ["TERMINATE_REMOVE_EXACT_RETAINED_GENERATION", "OBSERVE_EXACT_RETAINED_GENERATION_ABSENCE"]
    for key in ("requires_workspace_readiness", "requires_runtime_ISSUED", "requires_unspent_preparation_facet",
                "requires_inner_controller_challenge", "generic_Docker_command_authority", "may_create_or_restore"):
        assert value[key] is False, key
    assert value["input_projection"] == ["retained_authenticated_cleanup_relation_id", "fresh_cleanup_request_id"]
    for term in ("full original container ID/backend", "workspace/controller generation", "never name or caller ID alone",
                 "safe targeting", "fail unresolved"):
        assert term in value["target"], term
    assert value["identity_target_failure"] == "WORKSPACE_CLEANUP_UNRESOLVED"
    assert "transient inspect failure" in value["absence"] and "alone insufficient" in value["absence"]
    assert "Unknown child/group reap or capture EOF stays unresolved even if container absent" in value["lost_inner_evidence"]
    assert "never fabricate composite cleanup success" in value["lost_inner_evidence"]


def test_cleanup_evidence_binds_original_generations_and_never_grants_success_or_authority():
    value = contract()["cleanup"]
    assert set(value["evidence_fields"]) == {"original_workspace_capability_id", "original_workspace_generation",
        "original_controller_identity", "original_controller_generation", "original_full_container_identity",
        "original_backend_relation", "preparation_attempt_id", "handoff_identity", "cleanup_barrier_sequence",
        "children_and_process_group_results", "capture_closure_and_EOF", "remove_result",
        "fresh_independent_absence_observation", "observer_method_and_identity", "work_and_tmp_generation_gone",
        "no_surviving_artifact_export", "typed_unresolved_components"}
    for key in ("evidence_is_preparation_success", "evidence_is_behavior_success", "evidence_is_future_authority"):
        assert value[key] is False, key
    assert value["workspace_failure_status"] == "WORKSPACE_CLEANUP_UNRESOLVED"


def test_framing_has_exact_closed_request_response_fields_and_no_implicit_types():
    value = contract()["framing"]
    assert value["protocol_id"] == PROTOCOL and type(value["version"]) is int and value["version"] == 1
    assert value["canonical_types"] == read_json(WORKSPACE)["authentication"]["canonical_types"]
    assert value["canonical_payload_encoding"] == read_json(WORKSPACE)["authentication"]["canonical_encoding"]
    assert value["wire_transport_frozen"] is False and value["operation_payloads_closed"] is True
    assert value["request_max_bytes"] == value["response_max_bytes"] == 8192
    common = {"protocol_id", "version", "operation", "request_id", "operation_id", "workspace_capability_id",
              "container_identity", "workspace_generation", "controller_generation", "sequence", "challenge", "purpose"}
    assert set(value["request_fields"]) == common | {"admission_relation_id", "payload"}
    assert set(value["response_fields"]) == common | {"status", "result", "error"}
    assert value["request_fields"]["operation"] == "closed_operation_enum"
    assert value["request_fields"]["payload"] == "exact_per_operation_input_projection"
    assert value["response_fields"]["request_id"] == "exact_request_id"
    assert value["response_fields"]["operation_id"] == "exact_operation_id"
    rules = value["primitive_rules"]
    assert "exact int" in rules["positive_int"] and "bool rejected" in rules["positive_int"]
    for term in ("duplicate/missing/unknown keys at every nesting", "nonfinite/float", "coercion", "exact schema"):
        assert term in rules["json"], term
    assert "owner 32 unpredictable bytes" in rules["challenge"]
    assert "required for three observation tags" in rules["challenge"]
    assert set(rules["status_enum"]) == {"COMPLETE", "REJECTED", "FAILED", "PROOF_UNRESOLVED"}
    assert set(rules["cleanup_reason_enum"]) == {"preparation_failure", "consumer_failure", "activation_failure",
        "timeout", "abandonment", "upstream_invalidation", "normal_completion", "controller_loss"}


def test_framing_requires_complete_exact_evidence_and_rejects_partial_or_extra_frames():
    value = contract()["framing"]
    for term in ("length-delimited", "overlong", "trailing", "partial", "duplicate", "unexpected", "before any effect"):
        assert term in value["framing_requirement"], term
    assert set(value["result_schemas"]) == {"observation", "materialize", "compile", "handoff", "begin_cleanup", "cleanup"}
    for schema in value["result_schemas"].values():
        assert type(schema) is list and schema and len(schema) == len(set(schema))
    for term in ("complete bounded operation-specific evidence", "null error", "matched IDs/generations/sequence/challenge/purpose",
                 "Other statuses carry exact typed error and null result", "never means owner readiness or behavior success",
                 "cleanup operations may carry bounded partial cleanup evidence", "Partial cleanup evidence never claims completion/readiness"):
        assert term in value["success_rule"], term
    assert set(value["error_fields"]) == {"layer", "code", "origin_status", "origin_reason",
        "authenticated_origin_relation_id", "operation_id", "cleanup_required", "detail_id"}


def test_semantic_message_schema_closes_every_nested_record_list_reference_and_primitive():
    value = message_schema()
    assert value["schema_id"] == PROTOCOL + ":semantic-message-schema"
    assert value["kind"] == "declarative_pure_contract_data"
    assert value["parser_implemented"] is False and value["transport_byte_prefix_unselected"] is True
    assert value["root_types"] == ["request", "response", "outer_cleanup_request", "outer_cleanup_response"]
    definitions = value["definitions"]

    def inspect(spec):
        if type(spec) is str:
            assert spec in definitions, spec
            return
        assert type(spec) is dict and "type" in spec, spec
        kind = spec["type"]
        assert kind in {"record", "list", "nullable", "enum", "fixed_list", "operation_selected_record", "str", "int", "bool"}
        if kind == "record":
            assert set(spec) == {"type", "fields", "additional_fields", "all_fields_required"}
            assert spec["additional_fields"] is False and spec["all_fields_required"] is True
            for item in spec["fields"].values():
                inspect(item)
        elif kind == "list":
            assert set(spec) == {"type", "items", "max_items"}
            assert type(spec["max_items"]) is int and 0 <= spec["max_items"] <= 128
            inspect(spec["items"])
        elif kind == "nullable":
            assert set(spec) == {"type", "item"}
            inspect(spec["item"])
        elif kind == "operation_selected_record":
            assert set(spec) == {"type", "by_operation"} and set(spec["by_operation"]) == TAGS
            for item in spec["by_operation"].values():
                inspect(item)
        elif kind in {"enum", "fixed_list"}:
            assert set(spec) == {"type", "values"} and spec["values"]
            assert all(type(item) in {str, int, bool} for item in spec["values"])
            if kind == "enum":
                assert len(spec["values"]) == len({(type(item).__name__, text(item)) for item in spec["values"]})
        elif kind == "int":
            assert spec["bool_allowed"] is False
            assert type(spec["minimum"]) is int and type(spec["maximum"]) is int
            assert spec["minimum"] <= spec["maximum"]
        elif kind == "str":
            assert type(spec["max_utf8_bytes"]) is int and 0 < spec["max_utf8_bytes"] <= 1024
        elif kind == "bool":
            assert spec["exact_type"] is True

    for spec in definitions.values():
        inspect(spec)
    assert definitions["operation"]["values"] == contract()["minimum_operation_review"]["accepted_tags"]
    assert definitions["protocol"]["values"] == [PROTOCOL]
    assert definitions["version"]["values"] == [1]
    assert definitions["positive_int"]["minimum"] == 1 and definitions["positive_int"]["bool_allowed"] is False
    assert contract()["framing"]["semantic_schema_file"] == "message_schema.json"


def test_semantic_payload_result_environment_and_state_records_match_frozen_contracts():
    definitions, value = message_schema()["definitions"], contract()
    for tag, item in operations().items():
        expected = {key: ("cleanup_reason" if kind == "cleanup_reason_enum" else kind)
                    for key, kind in item["input_projection"].items()}
        assert definitions["payload_" + tag]["fields"] == expected, tag
    assert set(definitions["request"]["fields"]) == set(value["framing"]["request_fields"])
    assert set(definitions["response"]["fields"]) == set(value["framing"]["response_fields"])
    assert set(definitions["typed_error"]["fields"]) == set(value["framing"]["error_fields"])
    assert definitions["request"]["fields"]["payload"]["by_operation"] == {
        tag: "payload_" + tag for tag in TAGS}
    expected_results = {tag: "result_observation" for tag in OBSERVATION_TAGS}
    expected_results.update({"MATERIALIZE_EXACT_SCENARIO_SOURCE": "result_materialize",
        "COMPILE_EXACT_SCENARIO": "result_compile", "PREPARE_EXCLUSIVE_HANDOFF": "result_handoff",
        "BEGIN_CLEANUP": "result_begin_cleanup", "CLEANUP_AND_REPORT": "result_cleanup"})
    assert definitions["response"]["fields"]["result"]["item"]["by_operation"] == expected_results
    for name, fields in value["framing"]["result_schemas"].items():
        assert set(definitions["result_" + name]["fields"]) == set(fields), name
    state = read_json(WORKSPACE)["workspace_state_digest"]
    assert set(definitions["workspace_state"]["fields"]) == set(state["top_level_payload_fields"])
    assert list(definitions["manifest_entry"]["fields"]) == state["manifest_entry_fields"]
    assert definitions["workspace_state"]["fields"]["work_manifest"]["max_items"] == 3
    assert definitions["workspace_state"]["fields"]["tmp_manifest"]["max_items"] == 0
    assert set(definitions["path"]["values"]) == {"/work", "/tmp", "/work/classes",
        "/work/SyntheticStateBox.java", "/work/classes/SyntheticStateBox.class"}
    environment = definitions["environment"]["fields"]
    frozen_env = value["foundation"]["sandbox"]["environment"]
    assert {key: item["values"][0] for key, item in environment.items()} == frozen_env
    compiler = definitions["compiler_identity"]["fields"]
    assert compiler["argv"] == {"type": "fixed_list", "values": read_json(PREP)["compiler"]["exact_scenario_argv"]}
    assert definitions["capture_stream"]["fields"]["limit_bytes"]["values"] == [2048]
    assert definitions["class_metadata"]["fields"]["size_bytes"]["maximum"] == 32768
    assert definitions["class_metadata"]["fields"]["class_loaded"]["values"] == [False]


def test_semantic_cross_field_rules_cover_challenges_total_inventory_and_partial_cleanup():
    value = message_schema()
    rules = text(value["cross_field_rules"])
    for term in ("bool is never int", "duplicate/missing/extra keys recursively", "purpose=operation",
                 "Challenge non-null exactly for three observation tags", "single-use owner-issued post-observation challenge/sequence",
                 "new OBSERVE_* challenge before readiness or handoff", "file link_count=1", "directory size/hash=null",
                 "process tasks sum<=128", "all handles sum<=128", "no unknown writer/process",
                 "never caller paths or generic file reads", "total<=33007", "observed_bytes=0", "eof/closed=true",
                 "preserved origin relation", "partial cleanup_evidence with complete=false", "unresolved_components empty",
                 "Removal/absence alone never establishes lost reaping/EOF", "All frames <=8192 bytes"):
        assert term in rules, term


def test_outer_message_schema_is_independent_and_preserves_typed_partial_cleanup_components():
    definitions = message_schema()["definitions"]
    request = definitions["outer_cleanup_request"]["fields"]
    response = definitions["outer_cleanup_response"]["fields"]
    assert set(request) == {"protocol_id", "version", "operation", "request_id",
        "retained_authenticated_cleanup_relation_id", "original_identity", "cleanup_barrier_sequence"}
    assert set(response) == {"protocol_id", "version", "operation", "request_id", "original_identity",
        "cleanup_barrier_sequence", "status", "remove_result", "absence", "error"}
    assert set(request["operation"]["values"]) == set(contract()["cleanup"]["outer"]["operations"])
    assert request["original_identity"] == response["original_identity"] == "cleanup_identity"
    assert set(definitions["cleanup_identity"]["fields"]) == {"original_workspace_capability_id",
        "original_workspace_generation", "original_controller_identity", "original_controller_generation",
        "original_full_container_identity", "original_backend_relation"}
    assert not ({"challenge", "admission_relation_id", "runtime_state", "preparation_facet"} & set(request))
    assert definitions["component_outcome"]["values"] == ["verified", "failed", "unresolved", "not_applicable"]
    cleanup = definitions["cleanup_evidence"]["fields"]
    assert cleanup["complete"] == "bool" and cleanup["typed_unresolved_components"]["max_items"] == 10
    assert cleanup["remove_result"] == {"type": "nullable", "item": "remove_result"}
    assert cleanup["fresh_independent_absence_observation"] == {"type": "nullable", "item": "absence"}
    assert definitions["child_cleanup"]["fields"]["reaping"] == "component_outcome"
    assert definitions["capture_cleanup"]["fields"]["EOF"] == "component_outcome"
    rules = text(message_schema()["cross_field_rules"])
    for term in ("typed_error.operation_id equals this outer request_id",
                 "TERMINATE_REMOVE returns remove_result with absence=null",
                 "OBSERVE_ABSENCE returns absence with remove_result=null",
                 "Outer COMPLETE requires the selected component outcome=verified and error=null"):
        assert term in rules, term


def test_controller_authentication_never_reuses_other_owners_secrets_or_signs_receipt():
    value = contract()["authentication"]
    assert value["protocol_is_authority"] is False and value["future_workspace_owner_binds_exact_controller"] is True
    assert value["original_workspace_authentication"] == read_json(WORKSPACE)["authentication"]
    assert set(value["secret_reuse_forbidden"]) == {"provider", "preparation", "runtime", "reflection", "SANDBOX.2"}
    assert value["secret_or_signature_created"] is False
    assert "No separately signed controller receipt type or issuer is required/frozen" in value["controller_evidence"]


def test_typed_controller_errors_preserve_upstream_semantic_layers_and_cleanup_root_cause():
    value = contract()["errors"]
    assert set(value["controller_codes"]) == {"CONTROLLER_UNAUTHENTICATED", "CONTROLLER_WRONG_GENERATION",
        "CONTROLLER_PROTOCOL_MISMATCH", "CONTROLLER_OPERATION_NOT_ALLOWED", "CONTROLLER_BUSY",
        "CONTROLLER_OBSERVATION_INCOMPLETE", "CONTROLLER_SOURCE_MISMATCH", "CONTROLLER_EXECUTABLE_MISMATCH",
        "CONTROLLER_CHILD_START_FAILED", "CONTROLLER_CHILD_TIMEOUT", "CONTROLLER_CAPTURE_INCOMPLETE",
        "CONTROLLER_CHILD_REAP_UNRESOLVED", "CONTROLLER_HANDOFF_UNRESOLVED", "CONTROLLER_CLEANUP_UNRESOLVED",
        "PROOF_UNRESOLVED"}
    assert len(value["controller_codes"]) == len(set(value["controller_codes"]))
    assert "retain original layer and exact typed code" in value["classification"]
    assert "never rebrand as CONTROLLER_UNAUTHENTICATED" in value["classification"]
    assert "never BEGIN_CLEANUP/mandatory teardown" in value["busy_exception"]
    assert "without erasing root cause" in value["cleanup_mapping"]


def test_historical_controller_source_identity_and_fixed_fixture_flow_are_preserved():
    historical = contract()["foundation"]["historical_controller"]
    raw = generated_historical_controller()
    assert len(raw) == historical["source_size_bytes"] == 13037
    assert sha256(raw).hexdigest() == historical["source_sha256"] == "4f81640e2f01bc1f7a1a833beb269a9d1df51088b69cf24c8369fb6683f11a58"
    embedded = ast.parse(literal("core/sandboxed_java_positive_probe.py", "BODY"))
    execute = next(node for node in embedded.body if isinstance(node, ast.FunctionDef) and node.name == "execute")
    stages = [node.args[0].value for node in ast.walk(execute) if isinstance(node, ast.Call)
              and isinstance(node.func, ast.Name) and node.func.id == "run"
              and node.args and isinstance(node.args[0], ast.Constant)]
    assert stages == ["javac", "java"]
    rendered = ast.unparse(execute)
    assert "open('/work/JavaSandboxProbe.java', 'xb')" in rendered
    assert "os.mkdir('/work/classes')" in rendered
    assert "if facts['work_before']:" in rendered
    assert historical["retains_live_empty_workspace"] is False
    assert historical["offers_exclusive_live_artifact_handoff"] is False
    assert historical["may_be_widened_here"] is False


def test_historical_controller_finally_still_removes_and_independently_inspects_absence():
    invoked = definition("core/sandboxed_java_positive_continuation.py", "_invoke")
    outer = next(node for node in invoked.body if isinstance(node, ast.Try))
    final = ast.unparse(ast.Module(body=outer.finalbody, type_ignores=[]))
    assert "cleanup_control('kill', name)" in final
    assert "cleanup_control('rm', '--force', '--volumes', name)" in final
    assert "cleanup_control('inspect', name" in final
    assert "removed.exit_code == 0" in final and "absent.exit_code != 0" in final
    assert "no such object" in final and "no such container" in final
    capture = ast.unparse(definition("core/java_single_thread_capture.py", "capture_process"))
    for term in ("os.killpg", "child.wait", "os.waitpid", "poller.close", "stream.close", "eof"):
        assert term in capture, term


def test_runtime_readiness_remains_unconditionally_fail_closed_and_no_harness_is_frozen():
    path = "core/synthetic_runtime_authorization_pinned_lifecycle.py"
    readiness = definition(path, "check_pinned_synthetic_runtime_execution_lease_preconditions")
    call = next(node for node in ast.walk(readiness) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "PinnedSyntheticRuntimeExecutionLeaseReadiness")
    assert ast.unparse(call.args[0]) == "record.lifecycle_state == ISSUED"
    assert isinstance(call.args[1], ast.Constant) and call.args[1].value is False
    consumer = ast.unparse(definition(path, "_consumer_readiness"))
    assert "_fail('PROOF_UNRESOLVED'" in consumer
    value = contract()["harness_boundary"]
    assert value["scenario_JVM_dispatch"] is value["full_harness_source"] is False
    for key in ("scenario_main_class", "scenario_JVM_argv", "behavioral_loader_protocol", "BEFORE_AFTER_runtime_protocol"):
        assert value[key] is None, key
    assert value["runtime_fail_closed_preserved"] is True


def test_all_authority_flags_are_false_and_all_operational_effect_counts_are_exact_zero():
    value = contract()
    flags = value["authority_flags"]
    assert flags and all(item is False for item in flags.values())
    assert set(flags) >= {"workspace_issuance", "container_creation", "source_materialization", "scenario_compilation",
        "runtime_activation", "reflection", "repository_write", "Apply", "network", "host_mount", "shell",
        "arbitrary_command", "arbitrary_Java", "arbitrary_filesystem", "executor", "BANK"}
    effects = value["operational_effects"]
    assert all(type(item) is int and item == 0 for item in effects.values())
    assert set(effects) >= {"Docker", "container_creation", "container_removal", "SANDBOX2", "JAVA1C", "provider_issuance",
        "auth_issuance", "runtime_issuance", "reflection_issuance", "workspace_issuance", "preparation_authority_issuance",
        "source_materialization", "javac", "java", "class_loading", "reflection", "SyntheticStateBox", "BANK", "EXECUTOR.1R", "Apply"}


def test_evidence_pins_and_AST_anchors_match_immutable_frozen_sources():
    value = read_json(str((PHASE / "evidence_index.json").relative_to(ROOT)))
    assert value["method"] == "source/JSON/AST only; no owner import or operation"
    assert value["historical_metadata_is_current_liveness"] is False
    paths = {item["path"] for item in value["sources"]}
    assert paths >= {PREP, WORKSPACE, "core/sandboxed_java_positive_probe.py",
        "core/sandboxed_java_positive_continuation.py", "core/runtime_java_pinned_provider.py",
        "core/synthetic_runtime_authorization_pinned_lifecycle.py"}
    assert len(paths) == len(value["sources"])
    for item in value["sources"]:
        raw = (ROOT / item["path"]).read_bytes()
        assert len(raw) == item["bytes"] and sha256(raw).hexdigest() == item["sha256"], item["path"]
        lines = raw.decode("utf-8-sig").splitlines()
        definitions = {node.name: node for node in tree(item["path"]).body
                       if isinstance(node, (ast.FunctionDef, ast.ClassDef))} if item["path"].endswith(".py") else {}
        for anchor in item["anchors"]:
            assert lines[anchor["line"] - 1][:240] == anchor["text"], (item["path"], anchor["line"])
            if "name" in anchor:
                node = definitions[anchor["name"]]
                assert (node.lineno, node.end_lineno) == (anchor["line"], anchor["end_line"])


def test_tests_and_writer_import_only_pure_libraries_and_never_call_operational_owners():
    for name, allowed in (("test_contract.py", {"ast", "hashlib", "json", "pathlib"}),
                          ("write_contract.py", {"ast", "copy", "hashlib", "json", "pathlib"})):
        own = ast.parse((PHASE / name).read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(own) if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name for node in ast.walk(own) if isinstance(node, ast.Import) for alias in node.names)
        assert imports <= allowed, (name, imports)
        assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id in {"eval", "exec", "__import__", "compile", "open"} for node in ast.walk(own))
    writer = ast.parse((PHASE / "write_contract.py").read_text(encoding="utf-8"))
    writes = [node for node in ast.walk(writer) if isinstance(node, ast.Call)
              and isinstance(node.func, ast.Name) and node.func.id == "write"]
    assert [ast.literal_eval(node.args[0]) for node in writes] == ["message_schema.json", "contract.json", "evidence_index.json"]
    value = contract()["historical_preservation"]
    assert value["all_prior_noncache_bytes_unchanged"] is value["no_repin"] is value["no_stash_reset_clean"] is True
    assert value["historical_controller_API_or_cleanup_changed"] is False
