"""Contract/source tests only: never import, construct or call effect owners."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path

import pytest

PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
CONTRACT = json.loads((PHASE / "contract.json").read_text(encoding="utf-8"))


def tree(relative):
    return ast.parse((ROOT / relative).read_text(encoding="utf-8"))


def literal(relative, name):
    for node in tree(relative).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("Missing literal: " + relative + ":" + name)


def function(relative, name):
    return next(node for node in tree(relative).body
        if isinstance(node, ast.FunctionDef) and node.name == name)


def calls(node):
    return {ast.unparse(item.func) for item in ast.walk(node) if isinstance(item, ast.Call)}


def test_outcome_requires_evolution_and_does_not_claim_complete_or_implementation():
    assert CONTRACT["completion_marker"] == "PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION"
    assert CONTRACT["decision_frozen"] is True
    for key in ("implementation_authorized", "owners_implemented", "behavioral_activation_ready",
                "proposed_downstream_rules_are_operational_authority"):
        assert CONTRACT[key] is False
    assert CONTRACT["reason"] == "PROOF_UNRESOLVED"
    assert CONTRACT["stop_after_contract_freeze"] is True


def test_exact_obtained_source_is_existing_literal_not_regenerated():
    data = literal("core/synthetic_runtime_authorization.py", "_SOURCE")
    spec = CONTRACT["scenario"]
    assert type(data) is bytes
    assert len(data) == spec["source_size_bytes"] == 239
    assert sha256(data).hexdigest() == spec["source_sha256"]
    assert spec["source_sha256"] == literal("core/synthetic_runtime_authorization.py", "SOURCE_SHA256")
    assert spec["definition_sha256"] == literal("core/synthetic_runtime_authorization.py", "_DEFINITION_SHA256")
    assert spec["scenario_id"] == literal("core/synthetic_runtime_authorization.py", "SCENARIO_ID")
    assert spec["source_regeneration_allowed"] is spec["source_rewriting_allowed"] is False


def test_exact_source_initializes_mutable_instance_state_before_observation():
    data = literal("core/synthetic_runtime_authorization.py", "_SOURCE")
    assert b"private int value = 10;" in data
    assert b"public boolean decrement(int amount)" in data
    assert b"value -= amount;" in data
    assert b"static" not in data
    assert b"import " not in data and b"@" not in data
    assert data.count(b"class ") == 1
    assert b"SyntheticStateBox(" not in data
    assert CONTRACT["first_behavioral_effect"]["first_source_level_state_effect"] == (
        "SyntheticStateBox implicit constructor initializes value = 10")


def test_frozen_first_read_assertion_is_explicitly_conflicting_not_silently_rewritten():
    evolution = CONTRACT["requirement_evolution"]
    old = json.loads((ROOT / evolution["frozen_conflict_path"]).read_text(encoding="utf-8"))
    assert evolution["frozen_conflict_key"] == "first_behavior_boundary.first_behavioral_effect"
    assert old["first_behavior_boundary"]["first_behavioral_effect"] == evolution["frozen_conflict_value"] == "BEFORE exact read"
    assert evolution["required"] is True
    assert evolution["current_phase_supersedes_history"] is False
    assert evolution["current_phase_implements_revision"] is False
    boundary = CONTRACT["first_behavioral_effect"]
    assert boundary["requirement_evolution_required"] is True
    assert boundary["operation"] == "launch_exact_scenario_JVM"
    assert boundary["status"] == "PROPOSED_BOUNDARY_REQUIRES_EXPLICIT_REQUIREMENT_EVOLUTION"


@pytest.mark.parametrize("operation,expected", [
    ("in_memory_source_projection", "PURE_DERIVATION"),
    ("sandbox_materialization", "PREPARATION_EFFECT"),
    ("javac_compilation", "PREPARATION_EFFECT"),
    ("JVM_startup", "BEHAVIORAL_ACTIVATION_EFFECT"),
    ("class_loading", "BEHAVIORAL_ACTIVATION_EFFECT"),
    ("class_initialization", "BEHAVIORAL_ACTIVATION_EFFECT"),
    ("object_construction", "BEHAVIORAL_EFFECT"),
    ("BEFORE_reflection_read", "BEHAVIORAL_EFFECT"),
])
def test_each_effect_class_is_distinct_and_explicit(operation, expected):
    effect = CONTRACT["effect_classification"][operation]
    assert effect["class"] == expected
    if operation in {"in_memory_source_projection", "sandbox_materialization", "javac_compilation"}:
        assert effect["runtime_lease_consumed"] is False
    else:
        assert effect["permitted_during_preparation"] is False


def test_materialization_is_closed_sandbox_scope_and_exact_file_budget():
    scope = CONTRACT["materialization"]
    assert scope["destination"] == "/work/SyntheticStateBox.java"
    assert scope["directories_created"] == ["/work/classes"]
    assert scope["maximum_materialized_source_files"] == 1
    assert scope["maximum_materialized_source_bytes"] == CONTRACT["scenario"]["source_size_bytes"]
    assert scope["maximum_preparation_regular_files"] == 2
    assert scope["allowed_preparation_regular_files"] == [
        "/work/SyntheticStateBox.java", "/work/classes/SyntheticStateBox.class"]
    assert scope["harness_files_included"] is False
    for flag in ("repository_source_write_authority", "persistent_artifacts_allowed", "export_source_or_class_to_host_allowed"):
        assert scope[flag] is False
    assert "exclusive" in scope["overwrite_policy"]
    assert "expected /work tmpfs root mount" in scope["symlink_policy"]
    assert "unexpected/subordinate mount" in scope["symlink_policy"]
    assert "NUL" in scope["path_policy"] and "traversal" in scope["path_policy"]


def test_exact_historical_compile_flags_are_recovered_without_invention():
    compiler = CONTRACT["compiler"]
    arguments = literal("core/sandboxed_java_toolchain_probe.py", "COMPILE_ARGUMENTS")
    assert compiler["historical_JAVA_1C_argv"] == [compiler["path"], *arguments]
    assert compiler["exact_scenario_argv"][:-1] == compiler["historical_JAVA_1C_argv"][:-1]
    assert compiler["historical_JAVA_1C_argv"][-1] == "/work/JavaSandboxProbe.java"
    assert compiler["exact_scenario_argv"][-1] == CONTRACT["materialization"]["destination"]
    assert "new scope" in compiler["template_derivation"]
    assert compiler["shell"] is False
    assert compiler["max_attempts"] == 1


def test_compiler_binary_image_and_sandbox_match_frozen_requirement_ast():
    compiler = CONTRACT["compiler"]
    relative = "core/runtime_java_pinned_requirement.py"
    assert compiler["image"] == literal(relative, "IMAGE")
    assert compiler["sandbox_policy_sha256"] == literal(relative, "POLICY_SHA256")
    cls = next(node for node in tree(relative).body
        if isinstance(node, ast.ClassDef) and node.name == "PinnedJavaRequirement")
    javac = next(node.value for node in cls.body if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name) and node.target.id == "javac")
    assert isinstance(javac, ast.Call)
    assert [ast.literal_eval(arg) for arg in javac.args] == [compiler["path"], compiler["sha256"]]
    assert compiler["sandbox_profile"] == "runtime_sandbox_2_v1"
    raw = (ROOT / "docs/roadmap/RUNTIME_SANDBOX_2_SECCOMP.json").read_bytes()
    assert sha256(raw).hexdigest() == compiler["sandbox_policy_sha256"]


@pytest.mark.parametrize("flag", ["caller_flags_allowed", "argument_files_allowed", "arbitrary_classpath_allowed",
    "maven_allowed", "gradle_allowed", "dependency_download_allowed", "network_allowed", "processor_plugin_inputs_allowed"])
def test_compiler_has_no_open_input_or_command_authority(flag):
    assert CONTRACT["compiler"][flag] is False


def test_compiler_bounds_and_empty_diagnostics_preserve_infrastructure_envelope():
    compiler = CONTRACT["compiler"]
    assert compiler["compiler_stdout_max_bytes"] == compiler["compiler_stderr_max_bytes"] == 2048
    assert compiler["outer_stdout_max_bytes"] == compiler["outer_stderr_max_bytes"] == 8192
    assert compiler["outer_timeout_ms"] == 10000
    assert compiler["shared_controller_deadline_ms"] == 5000
    assert any("empty stdout/stderr" in item for item in CONTRACT["compile_output"]["success_requirements"])


def test_sandbox_exact_environment_and_tmpfs_are_frozen():
    sandbox = CONTRACT["sandbox"]
    assert sandbox["environment"] == literal("core/candidate_runtime_sandbox.py", "_WORKLOAD_ENVIRONMENT")
    assert len(sandbox["environment"]) == 8
    assert sandbox["tmpfs"] == {"/work": "rw,nosuid,nodev,size=32m,mode=1777",
        "/tmp": "rw,nosuid,nodev,noexec,size=16m,mode=1777"}
    assert sandbox["network"] == "none" and sandbox["rootfs_readonly"] is True
    assert sandbox["host_mounts"] == [] and sandbox["image_declared_volumes_allowed"] is False
    assert sandbox["uid_gid"] == "65534:65534"
    assert sandbox["pids_max"] == 128 and sandbox["memory_bytes"] == 134217728
    assert sandbox["nano_cpus"] == 1000000000
    assert sandbox["provider_proof_workspace_reusable"] is False


def test_exact_output_is_one_inert_class_with_no_fabricated_measured_hash():
    output = CONTRACT["compile_output"]
    assert output["expected_path"] == "/work/classes/SyntheticStateBox.class"
    assert output["expected_relative_class_set"] == ["SyntheticStateBox.class"]
    assert output["maximum_class_files"] == 1
    assert (output["minimum_class_bytes"], output["maximum_class_bytes"]) == (1, 32768)
    assert output["predicted_class_sha256"] is None
    assert output["exit_zero_proves_source_identity"] is False
    assert output["compile_success_proves_behavior_success"] is False
    assert "COMPILE_OUTPUT_MISMATCH" in output["unexpected_file_behavior"]
    assert "never load" in output["manifest"]
    frozen = ast.unparse(function("core/sandboxed_java_positive_continuation.py", "evaluate"))
    assert "32768" in frozen


def test_pair_design_keeps_receipt_evidence_separate_from_each_effect_facet():
    authority = CONTRACT["authority_separation"]
    assert authority["all_authorities_distinct"] is True
    assert authority["proposed_scope_fields"] == ["exact_sandbox_materialization_authority", "exact_scenario_compilation_authority"]
    assert authority["provider_infrastructure_evidence_is_scenario_permission"] is False
    receipt = CONTRACT["preparation_receipt"]
    assert receipt["kind"] == "authenticated_evidence_not_capability"
    assert receipt["owner"] == authority["proposed_owner"]
    assert receipt["runtime_permission"] is receipt["execution_permission"] is receipt["caller_boolean_accepted"] is False
    assert receipt["single_receipt_with_distinct_source_and_compile_sections"] is True
    assert "one-shot" in authority["preparation_authority_design"]
    assert "failures spend" in authority["authority_lifetime"]


def test_exact_helpers_are_not_misrepresented_as_complete_harness():
    harness = CONTRACT["harness_identity"]
    for role in ("before", "after"):
        helper = literal("core/synthetic_read_only_reflection.py", "_" + role.upper() + "_HELPER")
        assert sha256(helper.encode("utf-8")).hexdigest() == harness[role + "_helper_sha256"]
        pinned = literal("core/synthetic_reflection_execution_lifecycle_pinned.py", role.upper() + "_HELPER_SHA256")
        assert harness[role + "_helper_sha256"] == pinned
        assert "field.getInt(instance)" in helper and "main(" not in helper
    assert harness["full_executable_harness_source_frozen"] is False
    assert harness["full_executable_harness_sha256"] is None
    assert harness["renderer_helpers_are_complete_harness"] is False
    assert harness["missing_full_harness_blocks_activation"] is True


def test_current_runtime_consumer_is_unconditionally_unresolved_before_commit():
    relative = "core/synthetic_runtime_authorization_pinned_lifecycle.py"
    unresolved = function(relative, "_consumer_readiness")
    assert calls(unresolved) == {"_fail"}
    assert "PROOF_UNRESOLVED" in ast.unparse(unresolved)
    transition = ast.unparse(function(relative, "_transition"))
    assert transition.index("_consumer_readiness()") < transition.index("_STORE = updated")
    assert CONTRACT["runtime_consumption_gate"]["current_gate_changed"] is False
    assert CONTRACT["ordering"]["current_runtime_consumer_remains_unconditionally_unresolved"] is True


def test_reflection_preparation_issued_and_activation_consumed_remain_compatible():
    order = CONTRACT["ordering"]
    assert order["preparation_runtime_state"] == "ISSUED"
    assert order["both_reflection_admissions_and_leases_prepared_with_runtime"] == "ISSUED"
    assert order["preparation_requires_runtime_CONSUMED"] is False
    relative = "core/synthetic_reflection_execution_lifecycle_pinned.py"
    issue = ast.unparse(function(relative, "issue_pinned_synthetic_reflection_execution_lease"))
    assert "_runtime_state(runtime, authorization) != ISSUED" in issue
    consume = ast.unparse(function(relative, "_transition"))
    assert "target == CONSUMED and runtime_state != CONSUMED" in consume
    sequence = literal(relative, "EXECUTOR_SEQUENCE")
    assert sequence[2:4] == ("consume pinned runtime lease", "consume BEFORE reflection lease")
    proposed = order["sequence"]
    indices = [proposed.index(name) for name in ("consume pinned runtime lease", "consume BEFORE reflection lease",
        "launch exact scenario JVM", "perform BEFORE exact reflection read", "invoke exact public decrement(3)",
        "consume AFTER reflection lease", "perform AFTER exact reflection read")]
    assert indices == sorted(indices)


def test_readiness_is_original_authenticated_same_process_evidence_not_permission():
    ready = CONTRACT["consumer_readiness"]
    assert ready["kind"] == "authenticated_evidence_not_capability"
    assert ready["same_process_required"] is ready["authenticated_originals_retained"] is True
    assert set(ready["rejected_substitutes"]) >= {"Boolean", "JSON", "report copy", "fingerprint string", "copy", "wrong PID"}
    for required in ("BEFORE", "AFTER", "preparation receipt", "full harness", "live", "reflection primitive"):
        assert required in " ".join(ready["minimum_signed_bindings"])
    assert "no recursive" in ready["race_policy"] or "without recursive" in ready["race_policy"]
    assert "non-reentrant runtime lock" in ready["runtime_integration"]
    assert CONTRACT["runtime_consumption_gate"]["new_runtime_states"] == []
    assert CONTRACT["runtime_consumption_gate"]["caller_ready_boolean_allowed"] is False


def test_cleanup_records_live_artifacts_pending_until_consumer_finishes():
    receipt, cleanup = CONTRACT["preparation_receipt"], CONTRACT["cleanup"]
    assert receipt["cleanup_state_at_success"] == "LIVE_EPHEMERAL_ARTIFACTS_CLEANUP_PENDING"
    assert receipt["cleanup_success_claimed_at_preparation_success"] is False
    assert cleanup["preparation_success_implies_cleanup_success"] is False
    assert "consumer completion" in cleanup["after_preparation_success"]
    assert "independently verify absence" in cleanup["after_behavior_or_abandonment"]
    assert "metadata reports" in cleanup["persistent_artifacts"]
    assert "No source, class, harness" in cleanup["persistent_artifacts"]


@pytest.mark.parametrize("code", ["SOURCE_IDENTITY_MISMATCH", "SOURCE_BYTES_MISMATCH",
    "MATERIALIZATION_NOT_AUTHORIZED", "MATERIALIZATION_SCOPE_MISMATCH", "COMPILATION_NOT_AUTHORIZED",
    "COMPILER_IDENTITY_MISMATCH", "COMPILER_ARGUMENT_MISMATCH", "COMPILE_FAILED", "COMPILE_OUTPUT_MISMATCH",
    "HARNESS_IDENTITY_MISMATCH", "PREPARATION_EVIDENCE_UNAUTHENTICATED", "PREPARATION_EVIDENCE_STALE",
    "CONSUMER_READINESS_UNRESOLVED", "PROOF_UNRESOLVED"])
def test_error_taxonomy_preserves_each_required_typed_failure(code):
    assert CONTRACT["error_taxonomy"][code]


def test_all_current_authorities_and_operational_effects_are_exact_false_zero():
    assert all(type(value) is bool and value is False for value in CONTRACT["authority_flags"].values())
    assert all(type(value) is int and value == 0 for value in CONTRACT["operational_effects"].values())
    assert set(CONTRACT["operational_effects"]) >= {"Docker", "SANDBOX2", "JAVA1C", "provider_issuance",
        "pinned_auth_issuance", "runtime_lease_issuance", "reflection_admission_issuance", "reflection_lease_issuance",
        "source_materialization", "filesystem_runtime_writes", "javac", "java", "class_loading", "reflection",
        "SyntheticStateBox", "BANK", "EXECUTOR_1R", "Apply"}


def test_no_preparation_or_consumer_owner_was_created():
    assert not (ROOT / "core/synthetic_execution_preparation_pinned.py").exists()
    assert not (ROOT / "core/synthetic_execution_consumer_pinned.py").exists()
    assert CONTRACT["recommended_implementation_slice"].startswith("First resolve the named requirement evolution")


def test_frozen_source_evidence_index_matches_current_raw_bytes_and_exact_line_anchors():
    index = json.loads((PHASE / "evidence_index.json").read_text(encoding="utf-8"))
    assert index["owner_modules_imported"] is False
    assert index["source_materialized"] is False
    assert len(index["files"]) >= 15
    for relative, record in index["files"].items():
        data = (ROOT / relative).read_bytes()
        assert record["sha256"] == sha256(data).hexdigest()
        assert record["bytes"] == len(data)
        lines = data.decode("utf-8").splitlines()
        for anchor in record["anchors"]:
            assert anchor["text"] in lines[anchor["line"] - 1]
