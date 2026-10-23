"""Pure JSON/source/AST assertions; never import or invoke an effect owner."""
import ast
from hashlib import sha256
import json
from pathlib import Path


PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
CLOSE_PATH = "docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1/contract.json"


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def contract():
    return json.loads((PHASE / "contract.json").read_text(encoding="utf-8"))


def source(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def tree(path):
    return ast.parse(source(path), filename=path)


def definition(path, name):
    return next(node for node in tree(path).body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name)


def literal(path, name):
    assignment = next(node for node in tree(path).body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == name
                              for target in node.targets))
    return ast.literal_eval(assignment.value)


def text(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def generated_historical_controller():
    """Reproduce fixed text assembly as data; execute no extracted function."""
    capture_path = "core/java_single_thread_capture.py"
    capture = definition(capture_path, "capture_process")
    lines = source(capture_path).splitlines(keepends=True)
    captured_text = "".join(lines[capture.lineno - 1:capture.end_lineno])
    if not captured_text.endswith("\n"):
        captured_text += "\n"
    fixture = "core/sandboxed_java_toolchain_probe.py"
    single = "core/sandboxed_java_single_thread_probe.py"
    threaded = "core/thread_compatible_runtime_sandbox_probe.py"
    positive = "core/sandboxed_java_positive_probe.py"
    values = {name: literal(fixture, name) for name in (
        "JAVA_SOURCE", "EXPECTED_OUTPUT", "COMPILE_ARGUMENTS", "RUNTIME_ARGUMENTS")}
    values.update({name: literal(single, name) for name in ("JAVAC_PATH", "JAVAC_SHA256")})
    values.update({name: literal(threaded, name) for name in ("JAVA_PATH", "JAVA_SHA256")})
    values["SOURCE_SHA256"] = literal(positive, "SOURCE_SHA256")
    values["COMPILE_ARGV"] = (values["JAVAC_PATH"], *values["COMPILE_ARGUMENTS"])
    values["RUNTIME_ARGV"] = (values["JAVA_PATH"], *values["RUNTIME_ARGUMENTS"])
    names = ("JAVA_SOURCE", "EXPECTED_OUTPUT", "SOURCE_SHA256", "JAVAC_PATH",
             "JAVAC_SHA256", "JAVA_PATH", "JAVA_SHA256", "COMPILE_ARGV", "RUNTIME_ARGV")
    return ("import base64, hashlib, json, stat, sys, threading\n"
            + "import os, selectors, signal, subprocess, time\n" + captured_text + "\n"
            + "".join(name + " = " + repr(values[name]) + "\n" for name in names)
            + literal(positive, "BODY")).encode("utf-8")


def test_frozen_result_records_controller_gap_and_no_operational_workspace():
    value = contract()
    assert value["typed_result"] == value["completion_marker"] == "WORKSPACE_REQUIRES_CONTROLLER_EVOLUTION"
    assert value["workspace_semantics_frozen"] is value["controller_requirement_frozen"] is True
    for key in ("existing_controller_satisfies_requirement", "operational_controller_binding_resolved",
                "implementation_authorized", "owners_implemented", "workspace_exists_by_this_phase",
                "capabilities_issued", "behavioral_activation_ready", "runtime_consumption_ready"):
        assert value[key] is False
    assert value["reason"] == "PROOF_UNRESOLVED" and value["stop_after_contract"] is True
    for name in ("synthetic_execution_preparation_workspace_pinned.py",
                 "synthetic_execution_preparation_pinned.py"):
        assert not (ROOT / "core" / name).exists()


def test_foundation_is_exact_frozen_preparation_closure_without_widening():
    frozen = read_json(CLOSE_PATH)
    value = contract()["foundation"]
    assert frozen["completion_marker"] == "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1_COMPLETE"
    assert value["preparation_contract"] == CLOSE_PATH
    assert value["sandbox"] == frozen["sandbox"]
    assert value["scenario"] == frozen["scenario"]
    assert value["image_identity"] == frozen["compiler"]["image"] == "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a"
    assert value["sandbox_profile"] == frozen["compiler"]["sandbox_profile"] == "runtime_sandbox_2_v1"
    assert value["sandbox_policy_sha256"] == frozen["compiler"]["sandbox_policy_sha256"] == "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"
    assert value["dimensions_widened"] == [] and value["historical_contracts_modified"] is False


def test_exact_eight_variable_environment_comes_from_source_literal():
    expected = literal("core/candidate_runtime_sandbox.py", "_WORKLOAD_ENVIRONMENT")
    assert len(expected) == 8
    assert expected == {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
                        "GPG_KEY": "", "PYTHON_VERSION": "", "PYTHON_SHA256": "",
                        "SANDBOX_PUBLIC_SENTINEL": "phase-owned", "HOME": "/work",
                        "HOSTNAME": "runtime-sandbox1"}
    assert contract()["foundation"]["sandbox"]["environment"] == expected


def test_exact_sandbox_policy_and_configuration_predicate_are_source_backed():
    value = contract()["foundation"]
    policy = read_json("docs/roadmap/RUNTIME_SANDBOX_2_SECCOMP.json")
    encoded = json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert sha256(encoded).hexdigest() == value["sandbox_policy_sha256"]
    clone3 = [rule for rule in policy["syscalls"] if rule["names"] == ["clone3"]]
    assert clone3 == [{"names": ["clone3"], "action": "SCMP_ACT_ERRNO", "errnoRet": 38}]
    sandbox = value["sandbox"]
    assert sandbox["network"] == "none" and sandbox["rootfs_readonly"] is True
    assert sandbox["host_mounts"] == [] and sandbox["image_declared_volumes_allowed"] is False
    assert sandbox["uid_gid"] == "65534:65534" and sandbox["cap_drop"] == ["ALL"]
    assert sandbox["no_new_privileges"] is True
    assert (sandbox["pids_max"], sandbox["memory_bytes"], sandbox["nano_cpus"]) == (128, 134217728, 1000000000)
    assert sandbox["tmpfs"] == {"/work": "rw,nosuid,nodev,size=32m,mode=1777",
                                "/tmp": "rw,nosuid,nodev,noexec,size=16m,mode=1777"}
    checked = ast.unparse(definition("core/candidate_runtime_sandbox.py", "_safe_configuration_facts"))
    for name in ("ReadonlyRootfs", "NetworkMode", "IpcMode", "CgroupnsMode", "CapDrop", "PidsLimit",
                 "Memory", "NanoCpus", "WorkingDir", "Entrypoint", "Tmpfs", "SecurityOpt"):
        assert name in checked
    delegated = ast.unparse(definition("core/thread_compatible_runtime_sandbox.py", "safe_configuration"))
    assert "baseline._safe_configuration" in delegated and "POLICY_BYTES" in delegated


def test_workspace_is_independent_exact_original_and_never_scalar_authentication():
    value = contract()["exact_live_object"]
    assert value["future_owner"] == "core.synthetic_execution_preparation_workspace_pinned"
    assert value["type"] == "PinnedSyntheticPreparationWorkspace"
    assert value["schema"] == "synthetic_preparation_workspace_pinned_1_v1"
    assert value["phase"] == "SYNTH.EXEC.PREP.WORKSPACE.PINNED.1"
    for key in ("exact_type_required", "original_registry_object_identity_required",
                "issuing_pid_required", "strong_original_graph_retention_required"):
        assert value[key] is True
    assert value["scalar_projection_sufficient"] is False
    assert set(value["forbidden_substitutes"]) >= {"JSON", "container ID string", "fingerprint",
        "copied dataclass", "wrapper", "subclass", "historical SANDBOX.2 descriptor", "caller provider JSON"}
    assert "workspace generation" in text(value["immutable_signed_bindings"])
    assert "controller source bytes" in text(value["immutable_signed_bindings"])


def test_authentication_domain_registry_canonical_framing_and_roles_are_separate():
    value = contract()["authentication"]
    assert value["domain"] == "CATTUS:SYNTH.EXEC.PREP.WORKSPACE.PINNED.1:exact-live-workspace:v1"
    assert value["algorithm"] == "HMAC-SHA256" and value["independent_secret"] is True
    assert set(value["secret_reuse_forbidden"]) == {"SANDBOX.2 private verifier", "provider owners",
        "preparation owner", "runtime owner", "reflection owners"}
    assert value["roles"] == ["workspace-identity", "workspace-current-state", "workspace-cleanup-evidence"]
    assert "ASCII domain + NUL + ASCII fixed role + NUL" in value["framing"]
    for term in ("bool is not int", "duplicate keys", "nonfinite", "No caller JSON restore"):
        assert term in value["canonical_types"]
    for term in ("UTF-8", "sort_keys=true", "ensure_ascii=true", "allow_nan=false", "no normalization"):
        assert term in value["canonical_encoding"]
    assert "original workspace object" in value["registry"] and "terminal tombstones" in value["registry"]
    assert "constant time" in value["validation"]


def test_stable_fingerprint_excludes_mutable_state_and_cannot_establish_freshness():
    value = contract()
    identity, auth = value["exact_live_object"], value["authentication"]
    assert identity["current_state_authentication_separate"] is True
    for term in ("immutable", "excludes mutable liveness", "handoff", "cleanup"):
        assert term in identity["stable_fingerprint_scope"]
    assert "excluding signature and fingerprint" in auth["stable_fingerprint"]
    for term in ("sequence", "challenge", "generation", "cleanup barrier"):
        assert term in auth["state_hmac_payload"]
    assert "Cached HMACs" in auth["freshness"] and "timestamp" in auth["freshness"]
    assert auth["terminal_evidence_may_authenticate"] is True
    assert auth["terminal_evidence_grants_readiness"] is False


def test_current_state_digest_has_fixed_canonical_domain_and_complete_generation_scope():
    value = contract()["workspace_state_digest"]
    assert value["algorithm"] == "SHA256"
    assert value["domain"] == contract()["authentication"]["domain"]
    assert value["role"] == "workspace-state-digest"
    assert "NUL" in value["framing"] and "authentication.canonical_encoding" in value["framing"]
    assert set(value["top_level_payload_fields"]) == {"workspace_capability_id", "stable_fingerprint",
        "issuing_pid", "container_identity", "workspace_generation", "controller_identity",
        "controller_generation", "observation_sequence", "observation_challenge", "stage", "mounts",
        "work_manifest", "tmp_manifest", "process_exclusivity_observation"}
    assert value["manifest_entry_fields"] == ["path", "kind", "mode", "uid", "gid", "link_count", "size_bytes", "sha256"]
    for term in ("no-follow", "sorted by UTF-8 path bytes", "complete content SHA256",
                 "link_count=1", "Links/special files are rejected"):
        assert term in value["manifest_scope"]
    assert "subordinate_mount_count=0" in value["mounts"]
    assert "Complete no-follow manifest under /tmp" in value["tmp_manifest"]
    assert "full bounded process/writer inventory" in value["process_exclusivity_observation"]


def test_current_state_digest_remains_metadata_and_requires_its_state_HMAC():
    value = contract()["workspace_state_digest"]
    assert value["metadata_only"] is True
    assert value["artifact_bytes_exported"] is value["digest_alone_authenticates"] is False
    assert "workspace-current-state HMAC" in value["authenticated_by"]
    assert "fixed algorithm/domain/role/scope identity" in value["authenticated_by"]
    assert "No predicted class hash" in value["work_manifest"]
    assert "No harness stage is authorized" in value["stage"]
    assert "Unknown entries or unproved /tmp closure abort" in value["tmp_manifest"]


def test_public_provider_validation_chain_names_and_parameters_match_source_AST():
    value = contract()["provider_binding"]
    assert value["original_graph_only"] is value["public_validators_unchanged"] is True
    assert value["private_PINNED_1C_semantics_cloned"] is False
    chain = value["public_validation_chain"]
    assert len(chain) == 7
    for item in chain:
        node = definition(item["module"].replace(".", "/") + ".py", item["function"])
        assert isinstance(node, ast.FunctionDef)
        if "parameter_names" in item:
            assert [argument.arg for argument in node.args.posonlyargs + node.args.args] == item["parameter_names"]
    names = {item["function"] for item in chain}
    assert names >= {"validate_pinned_java_exact_provider", "validate_runtime_attachment",
        "validate_sandbox_backend_binding", "validate_pinned_synthetic_runtime_authorization",
        "validate_pinned_synthetic_runtime_execution_lease", "pinned_synthetic_runtime_execution_lease_state"}


def test_original_provider_graph_authentication_and_current_workspace_bridge_are_distinct():
    value = contract()["provider_binding"]
    assert value["same_image_proves_provider_authenticity"] is False
    assert value["same_backend_name_proves_generation_continuity"] is False
    assert value["new_live_binding_available_now"] is False
    for term in ("exact Server.Version", "actual new scenario container", "actual retained controller",
                 "independently authorized creation"):
        assert term in text(value["live_relation_required"])
    for term in ("daemon instance identity", "continuity proof", "ABA resistance"):
        assert term in value["route_version_limit"]
    assert "historical fixed controller source unchanged" in value["new_controller_relation"]
    owner = "core/runtime_java_pinned_provider.py"
    original = ast.unparse(definition(owner, "_authenticate_owned"))
    assert "is not value" in original and "os.getpid()" in original and "hmac.compare_digest" in original
    validator = ast.unparse(definition(owner, "validate_pinned_java_exact_provider"))
    assert "validate_runtime_attachment" in validator and "actual is not original" in validator


def test_historical_controller_executable_and_generated_source_identity_match_source():
    value = contract()["controller_boundary"]["historical_controller"]
    owner = "core/runtime_java_pinned_provider.py"
    assert value["normalized_executable"] == "/usr/local/bin/python"
    assert value["resolved_executable"] == literal(owner, "CONTROLLER_RESOLVED") == "/usr/local/bin/python3.12"
    assert value["executable_sha256"] == literal(owner, "CONTROLLER_SHA256")
    raw = generated_historical_controller()
    assert len(raw) == value["source_size_bytes"] == 13037
    assert sha256(raw).hexdigest() == value["source_sha256"] == "4f81640e2f01bc1f7a1a833beb269a9d1df51088b69cf24c8369fb6683f11a58"
    ast.parse(raw, filename="<historical-controller-source-data>")


def test_historical_controller_AST_is_fixed_fixture_compile_then_JVM_and_no_handoff():
    embedded = ast.parse(literal("core/sandboxed_java_positive_probe.py", "BODY"))
    execute = next(node for node in embedded.body if isinstance(node, ast.FunctionDef) and node.name == "execute")
    calls = [node for node in ast.walk(execute) if isinstance(node, ast.Call)]
    stages = [node.args[0].value for node in calls if isinstance(node.func, ast.Name)
              and node.func.id == "run" and isinstance(node.args[0], ast.Constant)]
    assert stages == ["javac", "java"]
    executed = ast.unparse(execute)
    assert "if facts['work_before']:" in executed
    assert "open('/work/JavaSandboxProbe.java', 'xb')" in executed
    assert "os.mkdir('/work/classes')" in executed
    assembled = ast.unparse(definition("core/sandboxed_java_positive_probe.py", "source"))
    assert "No caller source, flags, environment or stdin payload is accepted." in assembled
    historical = contract()["controller_boundary"]["historical_controller"]
    assert historical["retains_live_empty_workspace"] is False
    assert historical["offers_exclusive_live_artifact_handoff"] is False
    assert historical["may_be_widened_here"] is False


def test_historical_outer_controller_always_removes_and_independently_observes_absence():
    invoked = definition("core/sandboxed_java_positive_continuation.py", "_invoke")
    outer_try = next(node for node in invoked.body if isinstance(node, ast.Try))
    final = ast.unparse(ast.Module(body=outer_try.finalbody, type_ignores=[]))
    assert "cleanup_control('kill', name)" in final
    assert "cleanup_control('rm', '--force', '--volumes', name)" in final
    assert "cleanup_control('inspect', name" in final
    assert "removed.exit_code == 0" in final and "absent.exit_code != 0" in final
    assert "no such object" in final and "no such container" in final
    checked = ast.unparse(definition("core/runtime_java_pinned_provider.py", "_check_runtime"))
    assert "all_actual_runtime_and_control_cleanup_required" in checked
    assert "phase_container_count_after_teardown" in checked


def test_additive_controller_gap_stays_unresolved_without_invented_API_or_source():
    value = contract()["controller_boundary"]
    assert value["additive_controller_required"] is True
    assert value["additive_controller_implemented"] is value["historical_API_modified"] is False
    for key in ("future_controller_source_sha256", "future_controller_source_size_bytes",
                "future_controller_protocol_identity"):
        assert value[key] is None
    assert value["missing_identity_is_accepted"] is False
    assert "every workspace readiness request fails PROOF_UNRESOLVED" in value["unresolved_gate"]
    assert set(value["forbidden_API"]) >= {"generic shell", "caller command string", "arbitrary argv",
        "Docker CLI passthrough", "generic filesystem API", "arbitrary Java", "arbitrary source",
        "arbitrary class loading"}
    for term in ("liveness", "handoff", "child processes", "reaping", "teardown", "absence"):
        assert term in text(value["responsibilities_required"])
    assert "preparation success retains live artifacts with cleanup pending" in text(value["responsibilities_required"])


def test_initial_empty_workspace_and_classes_directory_have_explicit_creation_owner():
    value = contract()["initial_workspace"]
    assert value["work_root"] == "/work" and value["expected_work_entries"] == []
    classes = value["classes_directory"]
    assert classes["path"] == "/work/classes" and classes["exists_at_workspace_ready"] is False
    assert classes["creation_owner"] == "preparation materialization/compile attempt"
    assert classes["workspace_bootstrap_may_create"] is False
    assert "materialization facet" in classes["permission"]
    assert "never repairs/recreates" in classes["permission"]
    for key in ("source_file_present", "class_files_present", "harness_files_present",
                "JAR_processor_plugin_config_inputs_present", "unexpected_regular_files_present",
                "symlinks_hardlinks_subordinate_mounts_special_files_shared_writers_present",
                "target_JVM_present", "target_class_loaded_or_initialized", "SyntheticStateBox_present"):
        assert value[key] is False
    for term in ("no-follow", "link counts", "exclusive writers/processes"):
        assert term in value["observation"]


def test_historical_cleanup_can_never_be_reused_or_resurrected_as_live_generation():
    value = contract()["historical_workspace_rule"]
    assert value["must_be_new_generation"] is value["requires_independent_creation_authorization"] is True
    assert set(value["reuse_forbidden_after_cleanup_in"]) == {"SANDBOX.2", "JAVA.1C", "PINNED.1A",
        "PINNED.1B", "PINNED.1C", "provider verification"}
    assert value["container_ID_or_name_reuse_resurrects_generation"] is value["creation_authorized_here"] is False
    lifecycle = contract()["lifecycle"]
    assert lifecycle["representation"] == "predicates; no speculative public state enum/API is frozen"
    assert set(lifecycle["predicates"]) == {"live", "exclusive", "preparation-empty",
        "prepared-artifacts-present", "handoff-active", "cleanup-started", "cleanup-complete", "invalid"}
    assert lifecycle["no_refund_or_generation_rebind"] is True
    for term in ("never become live again", "lost controller", "generation change", "cleanup is terminal",
                 "historical evidence remains auditable"):
        assert term in text(lifecycle["terminal_invariants"])
    assert "partial success never confers readiness" in lifecycle["partial_preparation"]


def test_preparation_facets_remain_separate_and_bind_the_same_original_generation():
    value = contract()
    frozen = read_json(CLOSE_PATH)
    separation = value["authority_separation"]
    assert len(set(separation["independent_objects"])) == 4
    assert len(separation["effect_requires_conjunction"]) == 2
    for key in ("possession_allows_work_write", "workspace_consumes_preparation_facets",
                "historical_provider_evidence_is_live_readiness"):
        assert separation[key] is False
    prepare = value["preparation_interaction"]
    assert prepare["future_owner"] == frozen["preparation_authority"]["future_owner"]
    assert prepare["authority_type"] == frozen["preparation_authority"]["type"]
    assert prepare["authority_schema"] == frozen["preparation_authority"]["schema"]
    assert prepare["receipt_type"] == frozen["preparation_receipt"]["proposed_type"]
    assert prepare["receipt_schema"] == frozen["preparation_receipt"]["schema"]
    assert prepare["facets"] == frozen["preparation_authority"]["facets"]
    assert "materialization facet" in prepare["materialization"]
    assert "compilation facet" in prepare["compilation"] and "SAME workspace generation" in prepare["compilation"]
    assert "Do not require emptiness after authorized materialization" in prepare["compilation"]
    for key in ("workspace_substitution_allowed", "source_or_class_export_to_host_allowed",
                "cross_generation_receipt_allowed", "workspace_owner_spends_facets",
                "preparation_permission_owner_changed", "frozen_preparation_details_redefined"):
        assert prepare[key] is False


def test_runtime_ISSUED_is_required_while_behavioral_readiness_remains_false():
    lifecycle = "core/synthetic_runtime_authorization_pinned_lifecycle.py"
    node = definition(lifecycle, "check_pinned_synthetic_runtime_execution_lease_preconditions")
    call = next(item for item in ast.walk(node) if isinstance(item, ast.Call)
                and isinstance(item.func, ast.Name)
                and item.func.id == "PinnedSyntheticRuntimeExecutionLeaseReadiness")
    assert ast.unparse(call.args[0]) == "record.lifecycle_state == ISSUED"
    assert isinstance(call.args[1], ast.Constant) and call.args[1].value is False
    assert "PROOF_UNRESOLVED" in ast.unparse(node)
    assert "_fail('PROOF_UNRESOLVED'" in ast.unparse(definition(lifecycle, "_consumer_readiness"))
    value = contract()
    assert "runtime currently ISSUED" in text(value["preparation_interaction"]["issuance_requires"])
    assert "behavioral readiness stays false/PROOF_UNRESOLVED" in text(value["preparation_interaction"]["issuance_requires"])
    assert value["behavioral_activation_ready"] is value["runtime_consumption_ready"] is False


def test_race_rules_require_local_admission_fence_without_cross_owner_atomicity():
    value = contract()["atomicity_and_races"]
    assert value["cross_owner_transaction_claimed"] is value["private_lock_bridge_allowed"] is False
    assert "local generation/exclusive-operation/cleanup admission fence" in value["before_each_guarded_effect"]
    assert "Sequential validation cannot prove runtime/provider continuity across an unobservable gap" in value["cross_owner_limit"]
    assert "abort before effect with PROOF_UNRESOLVED" in value["cross_owner_limit"]
    assert set(value["rules"]) == {"controller_loss", "container_disappearance", "generation_replacement",
        "unexpected_file_creation", "cleanup_racing_preparation", "runtime_leaving_ISSUED",
        "provider_backend_mismatch"}
    assert "Admit no new operation" in value["rules"]["cleanup_racing_preparation"]
    assert "Already spent facets stay spent" in value["rules"]["runtime_leaving_ISSUED"]
    assert value["eligibility_changed_before_effect"] == "abort before effect"
    assert value["spent_facet_refunded"] is False
    assert "No refund" in value["late_loss_after_effect"] and "independent cleanup" in value["late_loss_after_effect"]


def test_cleanup_is_unconditional_terminal_and_requires_independent_absence_evidence():
    value = contract()["cleanup"]
    assert value["independent_of_behavior_success"] is True
    assert set(value["required_after"]) == {"preparation failure", "consumer failure", "timeout",
        "runtime activation failure", "abandonment", "invalidated upstream"}
    assert value["cleanup_requires_ISSUED_runtime_or_unspent_facet"] is False
    assert value["cleanup_requires_live_controller_challenge_or_current_upstream_readiness"] is False
    assert value["historical_PREP_cleanup_ownership_rewritten"] is False
    assert "Preparation owner retains frozen responsibility" in value["attempt_lifecycle_accountability"]
    assert "Workspace owner" in value["location_liveness_cleanup_custodian"]
    for term in ("process groups terminated and reaped", "captures/pipes/selectors", "container removed",
                 "/work and /tmp generation gone", "independent same-backend", "no source/class/harness"):
        assert term in text(value["evidence_required"])
    assert "not merely removal exit status or controller self-report" in text(value["evidence_required"])
    assert "even when the inner controller is lost" in value["lost_controller_path"]
    assert value["successful_cleanup_is_preparation_success"] is value["successful_cleanup_is_behavior_success"] is False
    assert value["cleanup_failure_status"] == "WORKSPACE_CLEANUP_UNRESOLVED"
    assert value["cleanup_failure_blocks_current_readiness"] is True
    assert "no new creation, preparation, authority refund or handoff" in value["cleanup_retry"]


def test_typed_errors_distinguish_semantic_mismatch_authentication_and_cleanup():
    value = contract()
    assert set(value["errors"]) == {"WORKSPACE_UNAUTHENTICATED", "WORKSPACE_WRONG_PROCESS",
        "WORKSPACE_NOT_LIVE", "WORKSPACE_NOT_EMPTY", "WORKSPACE_NOT_EXCLUSIVE",
        "WORKSPACE_GENERATION_MISMATCH", "WORKSPACE_CONTROLLER_MISMATCH",
        "WORKSPACE_PROVIDER_MISMATCH", "WORKSPACE_SANDBOX_POLICY_MISMATCH",
        "WORKSPACE_UNEXPECTED_ARTIFACT", "WORKSPACE_HANDOFF_MISMATCH", "WORKSPACE_ALREADY_CLEANED",
        "WORKSPACE_CLEANUP_UNRESOLVED", "PROOF_UNRESOLVED"}
    assert value["error_rules"]["known_upstream_typed_errors_preserved"] is True
    assert value["error_rules"]["semantic_mismatch_relabelled_as_authentication_failure"] is False
    provider = "core/runtime_java_pinned_provider.py"
    assert value["error_rules"]["upstream_examples"] == [literal(provider, name) for name in
        ("BACKEND_MISMATCH", "CONTROLLER_MISMATCH", "RUNTIME_MISMATCH", "CLEANUP_FAILURE")]
    assert "never use for an authenticated semantic mismatch" in value["errors"]["WORKSPACE_UNAUTHENTICATED"]
    assert "no readiness revival" in value["errors"]["WORKSPACE_ALREADY_CLEANED"]
    assert "Separate cleanup failure" in value["errors"]["WORKSPACE_CLEANUP_UNRESOLVED"]


def test_harness_stays_unresolved_and_all_operational_authorities_and_effects_are_zero():
    value = contract()
    assert value["harness_boundary"] == read_json(CLOSE_PATH)["harness_boundary"]
    assert value["harness_boundary"]["decision"] == "UNRESOLVED"
    for key in ("source_bytes", "source_sha256", "source_size_bytes", "main_class", "scenario_JVM_argv",
                "loader_controller_implementation", "staged_BEFORE_AFTER_protocol_implementation"):
        assert value["harness_boundary"]["full_harness"][key] is None
    assert value["authority_flags"] and all(item is False for item in value["authority_flags"].values())
    effects = value["operational_effects"]
    assert set(effects) >= {"Docker", "SANDBOX2", "provider_issuance", "workspace_issuance",
        "container_creation", "container_removal", "source_materialization", "javac", "java",
        "class_loading", "reflection", "SyntheticStateBox", "BANK", "EXECUTOR_1R", "Apply"}
    assert all(type(item) is int and item == 0 for item in effects.values())


def test_evidence_hashes_sizes_line_anchors_and_AST_definitions_match_actual_sources():
    value = json.loads((PHASE / "evidence_index.json").read_text(encoding="utf-8"))
    assert value["historical_metadata_is_current_liveness"] is False
    assert value["method"] == "source/JSON/AST only; no operational imports or live remeasurement"
    assert len(value["sources"]) >= 12
    for item in value["sources"]:
        raw = (ROOT / item["path"]).read_bytes()
        assert len(raw) == item["bytes"] and sha256(raw).hexdigest() == item["sha256"]
        lines = raw.decode("utf-8").splitlines()
        for anchor in item["anchors"]:
            assert lines[anchor["line"] - 1].strip()[:240] == anchor["text"]
        if item["path"].endswith(".py"):
            definitions = {node.name: node for node in tree(item["path"]).body
                           if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
            for measured in item["AST_definitions"]:
                node = definitions[measured["name"]]
                assert (node.lineno, node.end_lineno) == (measured["line"], measured["end_line"])


def test_tests_remain_source_only_and_historical_preservation_is_explicit():
    own = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(own) if isinstance(node, ast.ImportFrom)}
    modules.update(alias.name for node in ast.walk(own) if isinstance(node, ast.Import) for alias in node.names)
    assert modules <= {"ast", "hashlib", "json", "pathlib"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"eval", "exec", "__import__"} for node in ast.walk(own))
    value = contract()["historical_preservation"]
    for key in ("entire_preexisting_noncache_inventory_unchanged", "existing_user_changes_preserved",
                "runtime_reflection_owners_unchanged", "registry_picker_configuration_unchanged"):
        assert value[key] is True
    assert value["historical_receipts_reissued_or_reused"] is False
