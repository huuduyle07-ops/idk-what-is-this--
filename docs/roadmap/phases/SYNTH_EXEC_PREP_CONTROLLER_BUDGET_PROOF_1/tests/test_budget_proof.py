"""Focused pure checks of accounting, schema fidelity and proof limitations.

These tests never import owners or interpret synthetic records as live evidence.
They calculate bytes from declarative Python values and frozen JSON sources.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
FROZEN = ROOT / "docs/roadmap/phases"


@pytest.fixture(scope="module")
def proof():
    spec = importlib.util.spec_from_file_location("frozen_budget_proof_data", HERE / "proof.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report(proof):
    return proof.build()


def independent_canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def operation_message(report, profile, operation, direction="response"):
    matches = [m for m in report["profiles"][profile]["messages"]
               if m["operation"] == operation and m["direction"] == direction]
    assert len(matches) == 1
    return matches[0]


def resolve_path(value, path):
    if path == "/":
        return value
    for component in path.lstrip("/").split("/"):
        value = value[int(component)] if type(value) is list else value[component]
    return value


@pytest.mark.parametrize("relative", [
    "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json",
    "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/contract.json",
    "SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/contract.json",
    "SYNTH_EXEC_PREP_CONTROLLER_TRANSPORT_1/selection.json",
    "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1/contract.json",
])
def test_frozen_inputs_match_original_external_preservation_baseline(relative):
    baseline = json.loads((HERE / "preservation_baseline.json").read_text(encoding="utf-8"))
    path = FROZEN / relative
    expected = baseline["files"][path.relative_to(ROOT).as_posix()]
    current = path.read_bytes()
    assert expected["kind"] == "file"
    assert len(current) == expected["bytes"]
    assert hashlib.sha256(current).hexdigest() == expected["sha256"]


def test_loaded_schema_is_exact_frozen_source(proof, report):
    raw = (FROZEN / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json").read_bytes()
    assert proof.SCHEMA == json.loads(raw)
    assert report["schema_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["schema_changed"] is False


def test_canonical_encoder_preserves_exact_json_rules(proof):
    value = {"z": "한\n", "a": [True, None, 1], "é": "x"}
    assert proof.canonical(value) == b'{"a":[true,null,1],"z":"\\ud55c\\n","\\u00e9":"x"}'
    with pytest.raises(ValueError):
        proof.canonical({"value": float("nan")})


@pytest.mark.parametrize("definition,value", [
    ("uint", True), ("positive_int", 0), ("positive_int", False),
    ("version", True), ("bool", 1), ("id", ""), ("id", "a\x00b"),
    ("hash", "0" * 63), ("hash", "A" * 64), ("challenge", "f" * 65),
])
def test_schema_types_reject_coercion_and_invalid_identity_shape(proof, definition, value):
    with pytest.raises(AssertionError):
        proof.validate(value, definition)


def test_nested_required_fields_cannot_be_omitted_or_added(proof):
    _, response = proof.pair("COMPILE_EXACT_SCENARIO", proof.PROFILES["candidate_a_relaxation"], 5)
    missing = copy.deepcopy(response)
    del missing["result"]["workspace_state"]["mounts"][0]["root_metadata"]["uid"]
    with pytest.raises(AssertionError):
        proof.validate(missing, "response", "COMPILE_EXACT_SCENARIO")
    extra = copy.deepcopy(response)
    extra["result"]["capture_and_reap"]["stdout"]["raw_bytes"] = ""
    with pytest.raises(AssertionError):
        proof.validate(extra, "response", "COMPILE_EXACT_SCENARIO")


def test_every_payload_validates_against_actual_schema_and_matches_encoder(proof, report):
    schema = json.loads((FROZEN / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json")
                        .read_text(encoding="utf-8"))
    expected_operations = schema["definitions"]["operation"]["values"]
    for profile in report["profiles"].values():
        assert len(profile["messages"]) == 2 * len(expected_operations)
        for message in profile["messages"]:
            record = message["synthetic_record"]
            assert message["operation"] in expected_operations
            proof.validate(record, message["direction"], message["operation"])
            encoded = independent_canonical(record)
            assert encoded.decode("utf-8") == message["canonical_payload"]
            assert len(encoded) == message["canonical_payload_bytes"]
            assert message["candidate_a_header_bytes"] == 4
            assert message["candidate_a_frame_bytes"] == len(encoded) + 4


def test_field_ledgers_are_disjoint_complete_byte_partitions(report):
    for profile in report["profiles"].values():
        for message in profile["messages"]:
            record = message["synthetic_record"]
            rows = message["field_and_subtree_contributions"]
            paths = [row["path"] for row in rows]
            assert len(paths) == len(set(paths))
            assert sum(row["own_bytes"] for row in rows) == len(independent_canonical(record))
            for row in rows:
                subtree = resolve_path(record, row["path"])
                assert row["canonical_subtree_bytes"] == len(independent_canonical(subtree))
                own_value_bytes = 2 if type(subtree) in (dict, list) else len(independent_canonical(subtree))
                assert row["own_bytes"] == (row["key_and_colon_bytes"] +
                                              row["preceding_comma_bytes"] + own_value_bytes)
                assert row["basis"]


def test_direction_totals_count_each_frame_once_and_keep_requests_out_of_stdout(report):
    for profile in report["profiles"].values():
        for total in profile["totals"].values():
            records = [m for m in profile["messages"] if m["operation"] in total["operations"]]
            assert len(records) == 2 * len(total["operations"])
            for direction in ("request", "response"):
                selected = [m for m in records if m["direction"] == direction]
                expected = sum(len(independent_canonical(m["synthetic_record"])) for m in selected)
                values = total["directions"][direction]
                assert values["semantic_payload_bytes"] == expected
                assert values["frame_overhead_bytes"] == 4 * len(selected)
                assert values["candidate_a_wire_bytes"] == expected + 4 * len(selected)
                assert values["payload_minus_8192"] == expected - 8192
                assert values["wire_minus_8192"] == expected + 4 * len(selected) - 8192
            assert total["candidate_a_outer_stdout_bytes"] == total["directions"]["response"]["candidate_a_wire_bytes"]
            assert total["request_bytes_added_to_outer_stdout"] == 0
            assert total["candidate_a_outer_stderr_bytes"] == 0
            assert total["child_compiler_stdout_bytes"] == total["child_compiler_stderr_bytes"] == 0
            assert total["semantic_payload_total_both_directions"] == sum(
                d["semantic_payload_bytes"] for d in total["directions"].values())
            assert total["frame_overhead_both_directions"] == 8 * len(total["operations"])


def test_schema_catalog_is_not_misrepresented_as_true_successful_lifecycle(report):
    assert report["typed_result"] == "AGGREGATE_BUDGET_SCOPE_UNRESOLVED"
    assert report["formal_successful_lifecycle_minimum_bytes"] is None
    assert report["existence_witness_produced"] is False
    assert report["unconditional_impossibility_proved"] is False
    assert report["budget_blocker_removed"] is False
    assert report["transport_selected"] is False
    assert report["no_feasibility_inference_from_subcap_relaxation"] is True
    assert report["no_scope_resolution_by_favorable_exclusion"] is True
    for profile in report["profiles"].values():
        assert "NOT_" in profile["kind"]
        assert all(m["schema_valid"] is True and m["semantic_execution_witness"] is False
                   for m in profile["messages"])


def test_generation_width_choices_are_conditional_and_do_not_create_aliases(report):
    relaxed = report["profiles"]["frozen_semantic_relaxation"]
    candidate = report["profiles"]["candidate_a_relaxation"]
    assert relaxed["generation_width"] == 1
    assert candidate["generation_width"] == 64
    for profile in (relaxed, candidate):
        for message in profile["messages"]:
            value = message["synthetic_record"]
            assert len(value["workspace_generation"]) == profile["generation_width"]
            assert len(value["controller_generation"]) == profile["generation_width"]
            assert len(value["container_identity"]) == 64
            assert profile["opaque_width"] == 1
            assert "relaxation" in profile["kind"]


def test_subcap_core_and_overcap_observation_are_only_conditional_bounds(report):
    for name in ("frozen_semantic_relaxation", "candidate_a_relaxation"):
        profile = report["profiles"][name]
        core = profile["totals"]["materialize_compile"]
        prepared = profile["totals"]["materialize_compile_fresh_prepared"]
        assert core["directions"]["response"]["semantic_payload_bytes"] < 8192
        assert prepared["directions"]["response"]["semantic_payload_bytes"] > 8192
        assert core["attempt_scope"] == "Guaranteed materialize/compile core only"
        assert prepared["attempt_scope"] == "CONDITIONAL_UNRESOLVED_SCOPE"
    assert report["requirement_evolution_required"] == "UNRESOLVED"


def test_freshness_envelopes_and_mutation_poststate_challenges_remain_separate(report):
    observations = {"OBSERVE_EMPTY_WORKSPACE", "OBSERVE_CURRENT_WORKSPACE", "OBSERVE_PREPARED_ARTIFACTS"}
    for profile in report["profiles"].values():
        for operation in observations | {"MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO"}:
            request = next(m["synthetic_record"] for m in profile["messages"]
                           if m["operation"] == operation and m["direction"] == "request")
            response = next(m["synthetic_record"] for m in profile["messages"]
                            if m["operation"] == operation and m["direction"] == "response")
            for key in ("protocol_id", "version", "operation", "request_id", "operation_id",
                        "workspace_capability_id", "container_identity", "workspace_generation",
                        "controller_generation", "sequence", "challenge", "purpose"):
                assert response[key] == request[key]
            assert response["purpose"] == operation
            nested = response["result"]["workspace_state"]["observation_challenge"]
            assert len(nested) == 64
            if operation in observations:
                assert nested == request["challenge"]
            else:
                assert request["challenge"] is None
    assert "cannot substitute" in report["fresh_readiness_observation"]


def test_complete_state_contains_controller_task_namespaces_cgroup_and_two_mounts(report):
    required_namespaces = {"user", "mnt", "net", "pid", "ipc", "cgroup", "uts"}
    for profile in report["profiles"].values():
        for message in profile["messages"]:
            result = message["synthetic_record"].get("result")
            if not result or "workspace_state" not in result:
                continue
            state = result["workspace_state"]
            mounts = state["mounts"]
            assert [m["path"] for m in mounts] == ["/tmp", "/work"]
            assert mounts[0]["options"] == "rw,nosuid,nodev,noexec,size=16m,mode=1777"
            assert mounts[1]["options"] == "rw,nosuid,nodev,size=32m,mode=1777"
            for mount in mounts:
                assert mount["filesystem_kind"] == "tmpfs"
                assert mount["subordinate_mount_count"] == 0
                assert set(mount["root_metadata"]) == {"mode", "uid", "gid", "link_count"}
                assert mount["mount_identity"] and mount["namespace_generation"] and mount["root_identity"]
            process = state["process_exclusivity_observation"]["processes"]
            assert len(process) == 1
            controller = process[0]
            assert controller["role"] == "controller"
            assert controller["pid"] == 1 and controller["parent_pid"] == 0
            assert controller["uid"] == controller["gid"] == 65534
            assert set(controller["namespaces"]) == required_namespaces
            assert all(controller["namespaces"].values()) and controller["cgroup_identity"]
            assert len(controller["tasks"]) == 1 and controller["tasks"][0]["tid"] == 1
            assert controller["start_identity"] and controller["tasks"][0]["start_identity"]
            assert state["tmp_manifest"] == []


def test_writer_profile_accounts_controller_and_both_potential_write_roots(report):
    for name, profile in report["profiles"].items():
        response = operation_message(report, name, "COMPILE_EXACT_SCENARIO")["synthetic_record"]
        exclusivity = response["result"]["workspace_state"]["process_exclusivity_observation"]
        if not profile["writer_inventory"]:
            assert exclusivity["writers"] == []
            assert "relaxation" in profile["basis"].lower()
            continue
        assert len(exclusivity["writers"]) == 1
        writer = exclusivity["writers"][0]
        assert writer["process_identity"] == exclusivity["controller_process_identity"]
        assert writer["accounted_original_relation_id"] == exclusivity["exclusive_owner_relation_id"]
        assert [h["path"] for h in writer["handles"]] == ["/tmp", "/work"]
        assert all(h["access_kind"] == "potential_write_access" for h in writer["handles"])


def test_stage_manifests_preserve_fixed_source_and_complete_prepared_paths(report):
    expected_source = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
    expected_paths = {"preparation-empty": [],
                      "materialized": ["/work/SyntheticStateBox.java", "/work/classes"],
                      "prepared": ["/work/SyntheticStateBox.java", "/work/classes", "/work/classes/SyntheticStateBox.class"]}
    for name, profile in report["profiles"].items():
        for operation in ("OBSERVE_EMPTY_WORKSPACE", "MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO"):
            result = operation_message(report, name, operation)["synthetic_record"]["result"]
            state = result["workspace_state"]
            entries = state["work_manifest"]
            assert [e["path"] for e in entries] == expected_paths[state["stage"]]
            assert [e["path"] for e in entries] == sorted((e["path"] for e in entries), key=lambda s: s.encode("utf-8"))
            for entry in entries:
                assert entry["uid"] == entry["gid"] == 65534
                if entry["kind"] == "directory":
                    assert entry["size_bytes"] is None and entry["sha256"] is None
                else:
                    assert entry["link_count"] == 1
                    assert len(entry["sha256"]) == 64
                    if entry["path"].endswith(".java"):
                        assert entry["size_bytes"] == 239 and entry["sha256"] == expected_source
            if operation == "MATERIALIZE_EXACT_SCENARIO_SOURCE":
                assert result["source_readback_size"] == 239
                assert result["source_readback_sha256"] == expected_source
                assert result["source_readback_exact"] is True


def test_compiler_and_capture_are_exact_success_metadata_and_postreap(report):
    frozen_schema = json.loads((FROZEN / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json")
                              .read_text(encoding="utf-8"))["definitions"]
    empty_hash = hashlib.sha256(b"").hexdigest()
    for name, profile in report["profiles"].items():
        result = operation_message(report, name, "COMPILE_EXACT_SCENARIO")["synthetic_record"]["result"]
        compiler = result["compiler_identity"]
        definitions = frozen_schema["compiler_identity"]["fields"]
        for key in ("path", "sha256", "cwd", "image_identity"):
            assert compiler[key] == definitions[key]["values"][0]
        assert compiler["argv"] == definitions["argv"]["values"]
        environment = frozen_schema["environment"]["fields"]
        assert compiler["environment"] == {key: spec["values"][0] for key, spec in environment.items()}
        assert set(compiler["namespaces"]) == {"user", "mnt", "net", "pid", "ipc", "cgroup", "uts"}
        assert compiler["cgroup_identity"]
        capture = result["capture_and_reap"]
        assert type(capture["exit_code"]) is int and capture["exit_code"] == 0
        assert capture["timed_out"] is False
        assert capture["reaped"] is capture["group_terminated"] is capture["selectors_closed"] is True
        assert capture["child_pid"] > 1 and capture["process_group_identity"] and capture["deadline_identity"]
        expected = {"observed_bytes": 0, "limit_bytes": 2048, "sha256": empty_hash,
                    "eof": True, "overflow": False, "closed": True}
        assert capture["stdout"] == capture["stderr"] == expected
        processes = result["workspace_state"]["process_exclusivity_observation"]["processes"]
        assert [p["role"] for p in processes] == ["controller"]
        assert all(p["pid"] != capture["child_pid"] for p in processes)


def test_one_byte_class_mode_zero_and_nullable_tokens_are_explicit_relaxations(report):
    for name in ("frozen_semantic_relaxation", "candidate_a_relaxation"):
        profile = report["profiles"][name]
        message = operation_message(report, name, "COMPILE_EXACT_SCENARIO")
        result = message["synthetic_record"]["result"]
        assert result["class_metadata"]["size_bytes"] == 1
        assert all(e["mode"] == 0 for e in result["workspace_state"]["work_manifest"])
        assert any("not a successful Java class" in text for text in report["assumptions"])
        assert any("not coherent readiness states" in text for text in report["assumptions"])
        assert message["semantic_execution_witness"] is False


def test_class_stress_changes_only_metadata_decimal_width_not_raw_capture_budget(report):
    minimum = report["profiles"]["stress_minimum_class_envelope"]
    plausible = report["profiles"]["stress_plausible_class"]
    assert minimum["class_size"] == 1 and plausible["class_size"] == 512
    for operation in ("COMPILE_EXACT_SCENARIO", "OBSERVE_PREPARED_ARTIFACTS"):
        low = operation_message(report, minimum["name"], operation)
        high = operation_message(report, plausible["name"], operation)
        copies = 2 if operation == "COMPILE_EXACT_SCENARIO" else 1
        assert high["canonical_payload_bytes"] - low["canonical_payload_bytes"] == copies * (len("512") - len("1"))
        assert high["semantic_execution_witness"] is False


def test_membership_does_not_choose_later_scope_to_make_bytes_fit(proof, report):
    for operation in ("MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO"):
        assert proof.membership(operation)[0] == "MANDATORY_INSIDE_PREPARATION_CAP"
    for operation in ("OBSERVE_EMPTY_WORKSPACE", "OBSERVE_CURRENT_WORKSPACE", "OBSERVE_PREPARED_ARTIFACTS", "BEGIN_CLEANUP", "CLEANUP_AND_REPORT"):
        assert proof.membership(operation)[0] == "UNRESOLVED_SCOPE"
    assert proof.membership("PREPARE_EXCLUSIVE_HANDOFF")[0] == "OPTIONAL"
    assert report["direction_accounting"]["independent_request_aggregate_8192"] is False
    assert report["requirement_evolution_targets_unselected"] == [
        "increase aggregate cap", "separate protocol evidence bytes from historical process capture budget",
        "change mandatory evidence duplication", "change message schema/projection", "change preparation-attempt boundary"]


def test_pure_proof_has_no_operational_imports_or_authority_flags(report):
    source = (HERE / "proof.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append((node.module or "").split(".")[0])
    assert set(modules) <= {"copy", "hashlib", "json", "re", "pathlib"}
    assert report["authority_flags"] and not any(report["authority_flags"].values())
    assert report["operational_effects"] and set(report["operational_effects"].values()) == {0}
