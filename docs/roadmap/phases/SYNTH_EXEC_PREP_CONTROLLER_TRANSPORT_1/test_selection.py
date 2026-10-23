"""Pure source/contract selection checks, with no controller/protocol implementation."""
import ast
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRIOR = HERE.parent / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1"
SELECTION = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
CONTRACT = json.loads((PRIOR / "contract.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((PRIOR / "message_schema.json").read_text(encoding="utf-8"))


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def tree(path):
    return ast.parse(source(path))


def test_selection_is_design_only_and_authority_free():
    assert SELECTION["typed_result"] == "TRANSPORT_SELECTION_UNRESOLVED"
    assert SELECTION["selection_complete"] is SELECTION["completion_marker_earned"] is False
    assert SELECTION["selected_architecture"] is SELECTION["selected_transport"] is None
    assert {item["id"] for item in SELECTION["selection_blockers"]} == {
        "INDEPENDENT_OUTER_BACKEND_GENERATION_BINDING", "FROZEN_AGGREGATE_CAPTURE_FEASIBILITY"}
    assert SELECTION["scope"] == "DESIGN_SELECTION_ONLY"
    assert SELECTION["stop_after_selection"] is True
    for name in ("controller_implemented", "implementation_authorized", "workspace_created", "capabilities_issued"):
        assert SELECTION[name] is False
    assert all(value is False for value in SELECTION["authority_flags"].values())
    assert all(type(value) is int and value == 0 for value in SELECTION["operational_effects"].values())
    for item in SELECTION["future_modules"]:
        assert not (ROOT / (item["module"].replace(".", "/") + ".py")).exists()


def test_frozen_contract_schema_and_all_evidence_bytes_match():
    for item in SELECTION["evidence"]:
        content = (ROOT / item["path"]).read_bytes()
        assert sha256(content).hexdigest() == item["sha256"]
        assert len(content) == item["size_bytes"]
    assert SELECTION["foundation"] == CONTRACT["foundation"]
    assert SELECTION["protocol_id"] == CONTRACT["identity"]["protocol_id"]
    assert SELECTION["conceptual_owner"] == CONTRACT["identity"]["conceptual_owner"]
    assert SELECTION["semantic_schema_changed"] is False
    assert SCHEMA["transport_byte_prefix_unselected"] is True  # Historical artifact remains frozen.


def test_three_real_architectures_cover_every_requested_dimension():
    items = SELECTION["candidates"]
    assert [item["id"] for item in items] == ["A", "B", "C"]
    assert [item["classification"] for item in items] == ["PREFERRED_BUT_SELECTION_UNRESOLVED", "NOT_SELECTED", "INCOMPATIBLE_WITH_RETAINED_SEMANTICS"]
    required = {"controller_generation", "workspace_continuity", "challenge_sequence", "local_fence",
        "single_active_mutation", "observation_coherence", "child_supervision", "capture_reaping",
        "disconnect", "reconnect_resurrection", "cleanup_after_loss", "readonly_root_exact_tmpfs",
        "no_network", "closed_environment", "complexity", "sandbox2_change"}
    assert all(set(item["criteria"]) == required for item in items)
    invoke = next(node for node in tree("core/sandboxed_java_positive_continuation.py").body
        if isinstance(node, ast.FunctionDef) and node.name == "_invoke")
    assert any(isinstance(node, ast.Try) and node.finalbody for node in ast.walk(invoke))
    assert "cleanup_control('rm', '--force', '--volumes', name)" in ast.get_source_segment(
        source("core/sandboxed_java_positive_continuation.py"), invoke)


def test_unix_socket_is_requirement_evolution_not_accepted():
    policy = json.loads(source("docs/roadmap/RUNTIME_SANDBOX_2_SECCOMP.json"))
    denied = {name for row in policy["syscalls"] if row["action"] == "SCMP_ACT_ERRNO" for name in row["names"]}
    assert {"socket", "socketpair", "bind", "connect", "listen", "accept"} <= denied
    unix = next(item for item in SELECTION["transport_candidates"] if item["transport"] == "container_local_unix_endpoint")
    assert unix["classification"] == "REQUIRES_REQUIREMENT_EVOLUTION"
    assert "No /tmp infrastructure" in CONTRACT["observations"]["tmp_entries_policy"]
    assert SELECTION["sandbox2_changes_required"] is False
    assert SELECTION["sandbox_dimensions_widened"] == []


def test_exact_bootstrap_is_fixed_inline_source_not_file_or_stdin_upload():
    boot = SELECTION["bootstrap"]
    assert boot["argv_prefix"] == ["/usr/local/bin/python", "-I", "-S", "-B", "-c"]
    assert boot["source_argument_index"] == len(boot["argv_prefix"])
    assert boot["argv_count"] == len(boot["argv_prefix"]) + 1
    assert boot["resolved_executable"] == CONTRACT["identity"]["resolved_executable"]
    assert boot["interpreter_sha256"] == CONTRACT["identity"]["interpreter_sha256"]
    assert boot["environment"] == CONTRACT["foundation"]["sandbox"]["environment"]
    assert len(boot["environment"]) == 8
    assert boot["tty"] is False and boot["open_stdin"] is True and boot["stdin_once"] is True
    assert boot["restart_policy"] == "no" and boot["auto_remove"] is False
    assert boot["historical_validator_reused_for_new_source"] is False
    historical = source("core/sandboxed_java_positive_continuation.py")
    assert "IMAGE, '-I', '-S', '-B', '-c', probe.source())" in historical
    assert "32767" in boot["native_argv_limit"] and "no file/stdin/copy/mount/image fallback" in boot["native_argv_limit"]
    assert "NEW additive fixed bootstrap" in boot["delivery_boundary"]


def test_source_measurement_has_no_predicted_values():
    identity = SELECTION["future_source_identity"]
    assert identity["source_bytes"] is identity["source_sha256"] is identity["source_size_bytes"] is None
    assert "SHA256(bytes)" in identity["measurement"]
    assert "PROOF_UNRESOLVED" in identity["missing_any_binding"]
    assert len(identity["staged_gates"]) == 3
    assert identity["staged_gates"][0].startswith("BEFORE_CREATE")
    assert identity["staged_gates"][1].startswith("BEFORE_START")
    assert identity["staged_gates"][2].startswith("BEFORE_READINESS_OR_EFFECT")
    assert SELECTION["bootstrap"]["argv_literal_pending_source_identity"] is True


def test_wire_length_includes_header_and_keeps_frozen_semantics():
    wire = SELECTION["wire"]
    assert wire["maximum_frame_bytes"] == 8192
    assert wire["maximum_payload_bytes"] + wire["maximum_header_bytes"] == 8192
    assert wire["maximum_header_bytes"] == 4
    assert wire["length_encoding"] == "unsigned 32-bit big-endian binary, exactly four octets"
    assert wire["magic"] is wire["version_prefix"] is None
    assert "version=1" in wire["version_reason"]
    assert wire["partial_frame_timeout_ms"] == 1000
    assert "not reset per byte" in wire["partial_timeout_rule"]
    assert "cumulatively over whole preparation attempt" in wire["stream_budgets"]
    assert "65536" in wire["stream_budgets"] and "64 requests" in wire["stream_budgets"]
    assert "8192" in SCHEMA["cross_field_rules"][-1]


def test_partial_duplicate_trailing_and_noncanonical_data_are_fail_closed():
    wire = SELECTION["wire"]
    for word in ("duplicate keys", "unknown/missing", "bool-as-int", "BOM", "noncanonical", "trailing"):
        assert word in wire["semantic_validation"]
    assert "Partial header/body is protocol failure" in wire["eof"]
    assert "never ignored" in wire["duplicate_trailing"]
    assert "later invalid bytes" in wire["admission_boundary"]
    assert "never claim to undo" in wire["admission_boundary"]


def test_cleanup_preempts_without_general_queue_or_multiplex():
    wire = SELECTION["wire"]
    assert wire["maximum_outstanding_requests"] == 2
    assert "Only one complete BEGIN_CLEANUP" in wire["priority_control_exception"]
    assert "set barrier before waiting" in wire["priority_control_exception"]
    assert "FIFO" in wire["priority_control_exception"]
    assert "No second mutation or observation" in wire["priority_control_exception"]
    assert "No logical multiplex" in wire["ordering"]
    assert CONTRACT["serialization"]["cleanup_preempts_busy"] is True
    assert "without waiting" in CONTRACT["minimum_operation_review"]["cleanup_split"]
    assert "monotonic cleanup_barrier_sequence" in SELECTION["local_fence"]["state"]


def test_generations_separate_observation_from_owner_tokens_and_never_restore():
    generation = SELECTION["generations"]
    for key in ("container_generation", "workspace_generation", "controller_generation", "session_channel_generation"):
        assert "32-byte" in generation[key]
    assert len(generation["independent_observations"]) >= 5
    assert "PID/starttime/timestamp tuple alone" in generation["controller_incarnation"]
    assert "ABA" in generation["continuity_limit"]
    assert "new semantic field" not in generation["session_channel_generation"].lower()
    assert "Not an added semantic field" in generation["session_channel_generation"]
    assert SELECTION["disconnect_reconnect"]["reconnect_allowed"] is False
    assert SELECTION["disconnect_reconnect"]["restore_state_allowed"] is False
    assert "No automatic replay" in SELECTION["disconnect_reconnect"]["uncertain_effect"]
    assert "frozen_owner_has_no_backend_continuity_binding" in source("core/sandbox_backend_provenance.py")


def test_fresh_challenge_and_mutation_poststate_preserve_frozen_rules():
    value = SELECTION["challenge"]
    assert value["bytes"] == CONTRACT["observations"]["owner_challenge"]["random_bytes"] == 32
    assert value["wire_encoding"] == "64 lowercase hex characters"
    assert "previous accepted+1" in value["sequence"]
    assert "separate spent-admission" in value["observation_only"]
    assert "new wire challenge field" in value["observation_only"]
    assert "challenge non-null exactly" in SCHEMA["cross_field_rules"][1].lower()


def test_exact_javac_only_and_source_supervision_primitives():
    child = SELECTION["child_process"]
    assert child["argv"] == CONTRACT["compilation"]["compiler"]["exact_scenario_argv"]
    assert child["compiler_sha256"] == CONTRACT["compilation"]["compiler"]["sha256"]
    assert child["shell"] is False and child["stdin"] == "DEVNULL"
    assert child["start_new_session"] is True and child["maximum_launches"] == 1
    assert child["stdout_limit_bytes"] == child["stderr_limit_bytes"] == 2048
    assert child["attempt_deadline_ms"] == 5000 and child["outer_hard_deadline_ms"] == 10000
    capture = tree("core/java_single_thread_capture.py")
    calls = [node for node in ast.walk(capture) if isinstance(node, ast.Call)]
    assert any(isinstance(node.func, ast.Attribute) and node.func.attr == "Popen"
        and any(word.arg == "start_new_session" and isinstance(word.value, ast.Constant)
            and word.value.value is True for word in node.keywords) for node in calls)
    attrs = {node.func.attr for node in calls if isinstance(node.func, ast.Attribute)}
    assert {"killpg", "waitpid", "wait", "close", "select"} <= attrs
    assert "not reused unchanged" in SELECTION["local_fence"]["cooperation"]
    assert "No target JVM launch" in child["ownership"]


def test_retained_total_reserves_cleanup_and_runs_foreground_timer():
    life = SELECTION["retained_lifetime"]
    assert life["total_ms"] == 30000
    assert life["cleanup_reserve_ms"] + life["work_cutoff_ms"] == life["total_ms"]
    assert life["cleanup_reserve_ms"] >= SELECTION["child_process"]["outer_hard_deadline_ms"]
    assert life["renewable"] is False
    assert "BEFORE first container creation" in life["start"]
    assert "foreground event loop" in life["enforcement"]
    assert "no detached worker" in life["enforcement"]
    assert "WORKSPACE_CLEANUP_UNRESOLVED" in life["expiration"]
    assert "never claim physical absence" in life["expiration"]


def test_outer_cleanup_survives_inner_loss_and_does_not_fabricate_reaping():
    outer = SELECTION["outer_cleanup"]
    assert outer["operations"] == CONTRACT["cleanup"]["outer"]["operations"]
    assert "64-lowercase-hex" in outer["target_supply"]
    assert "Before starting" in outer["target_supply"]
    assert "no inner channel" in outer["independence"]
    assert "Neither proves lost child wait/EOF" in outer["absence"]
    assert "PROOF_UNRESOLVED" in SELECTION["cleanup_response_composition"]
    assert "not a second inner wire response" in SELECTION["cleanup_response_composition"]
    assert "NOT guaranteed" in SELECTION["disconnect_reconnect"]["response"]
    assert len(SELECTION["future_modules"]) == 3
    assert len(SELECTION["separate_future_owners"]) == 2


def test_complete_record_sizing_is_reproducible_and_not_live_evidence():
    sizing = json.loads((HERE / "sizing_witness.json").read_text(encoding="utf-8"))
    assert sizing["live_observations"] is sizing["controller_or_protocol_implementation"] is False
    assert sizing["frozen_attempt_outer_stdout_limit"] == SELECTION["wire"]["maximum_frame_bytes"] == 8192
    for item in sizing["cases"]:
        lengths = [4 + len(json.dumps(value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False).encode("utf-8")) for value in item["illustrative_records"]]
        assert lengths == item["payload_plus_four_header_bytes"]
        assert sum(lengths[:2]) == item["materialize_compile_total"]
        assert sum(lengths) == item["materialize_compile_fresh_observation_total"]
    writer_case = next(item for item in sizing["cases"] if item["one_controller_writer_two_root_handles"])
    assert writer_case["materialize_compile_total"] == 8096
    assert writer_case["materialize_compile_fresh_observation_total"] == 11520
    assert 8192 - writer_case["materialize_compile_total"] == 96
    for item in SELECTION["sizing_evidence"]:
        raw = (ROOT / item["path"]).read_bytes()
        assert sha256(raw).hexdigest() == item["sha256"]
        assert len(raw) == item["size_bytes"]
    guard = json.loads((HERE / "sizing_validation.json").read_text(encoding="utf-8"))
    assert guard["passed"] is True and guard["blocked_effects"] == []
    assert not any(guard["operational_guard_counters"].values())


def test_missing_cleanup_mechanism_and_budget_proof_preclude_completion():
    assert SELECTION["selection_complete"] is False
    assert all(item["status"].startswith("UNRESOLVED") for item in SELECTION["selection_blockers"])
    cleanup, budget = SELECTION["selection_blockers"]
    assert "not a mechanism" in cleanup["required_resolution"]
    assert "not itself demonstrate" in budget["effect"]
    assert "No source identity substitutes" in SELECTION["future_source_identity"]["staged_gates"][2]
    assert "may fire later" in SELECTION["retained_lifetime"]["enforcement"]
    assert SELECTION["wire"]["status"] == SELECTION["bootstrap"]["status"] == "REVIEWED_CANDIDATE_PROFILE_NOT_FINAL_SELECTION"


def test_phase_sources_do_not_contain_controller_implementation_or_owner_imports():
    for name in ("write_selection.py", "test_selection.py", "finalize_report.py", "sizing_analysis.py"):
        content = (HERE / name).read_text(encoding="utf-8")
        parsed = ast.parse(content)
        for node in ast.walk(parsed):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("core")
            elif isinstance(node, ast.Import):
                assert all(not item.name.startswith("core") for item in node.names)
        assert not any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in {
            "capture_process", "Controller", "decode_frame", "encode_frame", "compile_exact_scenario"}
            for node in ast.walk(parsed))
