"""Boundary controls, using exact historical source and inert stand-ins only."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nested_context_audit", HERE / "context_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_exact_runner_is_bound_to_historical_gates():
    gates = audit.read_json(audit.HISTORY / "pure_preoperational_gates.json")
    rows = {row["path"]: row["sha256"] for row in gates["source_bindings"]}
    for path in (audit.RUNNER, audit.PROVIDER, audit.SANDBOX, audit.BASELINE, audit.JAVA):
        assert hashlib.sha256((audit.ROOT / path).read_bytes()).hexdigest() == rows[path]


def test_runner_override_lexically_contains_issuer_and_restores_afterward():
    main = audit.function(audit.RUNNER, "main")
    scope = next(node for node in ast.walk(main) if isinstance(node, ast.Try)
                 and any(isinstance(n, ast.Assign) and ast.unparse(n.value) == "str(PHASE)"
                         for n in node.body))
    assignment = next(node for node in scope.body if isinstance(node, ast.Assign))
    assert ast.unparse(assignment) == "tempfile.tempdir = str(PHASE)"
    issuance = next(node for node in scope.body if isinstance(node, ast.Assign)
                    and "issue_pinned_synthetic_runtime_authorization" in ast.unparse(node))
    assert assignment.lineno < issuance.lineno
    assert any(ast.unparse(node) == "tempfile.tempdir = previous_tempdir" for node in scope.finalbody)
    assert not any(isinstance(node, ast.With) and "pytest" in ast.unparse(node)
                   for node in ast.walk(main))


def test_same_temp_state_selects_config_and_exact_workspace_without_historical_writes(tmp_path):
    result = audit.temp_reproducer(tmp_path)
    assert result["passed"]
    assert result["workspace_parent_equals_config_root"]
    assert result["exact_workspace_file_writes_succeeded"]
    assert result["workspace_removed"] and result["tempfile_state_restored"]
    assert result["TMP_TEMP_TMPDIR_unchanged"]
    assert not result["historical_folder_used"]
    assert result["socket_operations"] == result["owner_invocations"] == 0


def test_reproducer_refuses_historical_root_before_any_write():
    with pytest.raises(ValueError, match="new_phase_scratch_required"):
        audit.temp_reproducer(audit.HISTORY)


def test_upstream_wrappers_exit_before_runtime_snapshot():
    upstream = audit.function("core/runtime_java_pinned_backend_target_binding.py",
                              "issue_pinned_backend_target_binding")
    patch_scope = next(node for node in ast.walk(upstream) if isinstance(node, ast.With)
                       and "observed_sandbox" in ast.unparse(node.items))
    target = next(node for node in ast.walk(upstream) if isinstance(node, ast.Call)
                  and ast.unparse(node.func) == "target.inspect_target")
    assert patch_scope.end_lineno < target.lineno
    provider = audit.function(audit.PROVIDER, "issue_pinned_java_exact_provider")
    binding = next(node for node in ast.walk(provider) if isinstance(node, ast.Call)
                   and ast.unparse(node.func) == "pinned.issue_pinned_backend_target_binding")
    snapshot = next(node for node in ast.walk(provider) if isinstance(node, ast.Call)
                    and ast.unparse(node.func) == "_runtime_snapshot")
    assert binding.lineno < snapshot.lineno


@pytest.mark.parametrize("raise_in_verify", [False, True])
def test_exact_profiler_is_active_at_stub_boundary_and_restored(raise_in_verify):
    previous = sys.getprofile()
    result = audit.profiler_reproducer(raise_in_verify)
    assert result["passed"] and result["profiler_restored_by_exact_helper"]
    assert sys.getprofile() is previous
    if not raise_in_verify:
        assert result["profile_active_at_stub_boundary"]
        assert result["stub_controls_observed"] == 1
    assert result["owner_invocations"] == result["socket_operations"] == 0


def test_exact_profiler_does_not_install_denial_or_mutate_owner_functions():
    snapshot = audit.function(audit.PROVIDER, "_runtime_snapshot")
    observer = next(node for node in snapshot.body if isinstance(node, ast.FunctionDef)
                    and node.name == "observer")
    calls = [ast.unparse(node.func) for node in ast.walk(observer) if isinstance(node, ast.Call)]
    assert not any("socket" in call or "addaudithook" in call or "patch" in call for call in calls)
    assert not any(isinstance(node, ast.Raise) for node in ast.walk(observer))
    for node in ast.walk(observer):
        if isinstance(node, ast.Assign):
            assert all(not isinstance(target, ast.Attribute) for target in node.targets)


def test_same_attempt_success_excludes_unconditional_temp_socket_process_denial():
    retained = audit.read_json(audit.HISTORY / "SYNTH_AUTH_PINNED_1_LOCAL.json")
    provider = retained["provider_proof_report"]
    earlier = provider["pinned1b_report"]["bind_sandbox2_report"]
    assert earlier["status"] == "RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS"
    assert len(earlier["stages"]) == 11
    assert earlier["cleanup_verified"] and earlier["temporary_workspace_removed"]
    controls = provider["runtime_docker_controls"]
    assert [row["command"] for row in controls] == ["image", "ps", "ps"]
    assert all(row["completed"] and row["exit_code"] == 0 for row in controls)
    assert provider["java1c_report"]["controller_error"] == "ValueError: java1c_live_sandbox2_binding_rejected"
    assert retained["status"] == "SYNTH_AUTH_PINNED_1_BLOCKED"


def test_missing_boundary_evidence_fails_closed_without_promoting_differences():
    report = audit.audit_report()
    assert report["status"] == "UNRESOLVED"
    assert report["historical_truth"] == "historical nested root cause unresolved"
    assert not report["exact_historical_root_cause_established"]
    assert not report["SANDBOX2_source_changed"]
    assert not report["JAVA1C_source_changed"]
    assert not report["SYNTH_retried"]
    assert all(value == 0 for value in report["operational_effects"].values())
    matrix = {row["id"]: row for row in report["active_at_SANDBOX2_matrix"]}
    assert matrix["phase_local_temp_root"]["active_at_SANDBOX2"] is True
    assert matrix["PINNED1B_transport_and_replay_observers"]["classification"] == audit.INACTIVE
    assert matrix["provider_return_frame_profiler"]["active_at_SANDBOX2"] is True
    assert not any(row["classification"] in (audit.CAUSAL, audit.CAPABLE) for row in matrix.values())


def test_outcome_distinguishes_capability_from_historical_proof():
    assert audit.outcome([{"classification": audit.CAPABLE}]) == "NESTED_CONTEXT_CANDIDATE_ESTABLISHED"
    assert audit.outcome([{"classification": audit.CAUSAL}]) == "NESTED_CONTEXT_CAUSE_ESTABLISHED"
    assert audit.outcome([{"classification": audit.INACTIVE}], historical_complete=True) == "NO_RELEVANT_CONTEXT_DIFFERENCE_FOUND"
    assert audit.outcome([{"classification": audit.INACTIVE}]) == "UNRESOLVED"
