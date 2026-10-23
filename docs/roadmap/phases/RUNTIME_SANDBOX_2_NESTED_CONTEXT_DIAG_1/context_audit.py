"""Static historical context audit; never import or invoke operational owners.

Only the exact tempfile statement, pre-socket workspace statements, and the
return-frame observer helper may be extracted for isolated pure controls.
Historical folders are read only. All outputs belong to this new phase.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PHASE_ID = "RUNTIME.SANDBOX.2.NESTED.CONTEXT.DIAG.1"
HISTORY = ROOT / "docs/roadmap/phases/SYNTH_AUTH_PINNED_1"
RUNNER = "scripts/replay_synth_auth_pinned1.py"
SANDBOX = "core/thread_compatible_runtime_sandbox.py"
BASELINE = "core/candidate_runtime_sandbox.py"
PROVIDER = "core/runtime_java_pinned_provider.py"
JAVA = "core/sandboxed_java_positive_continuation.py"
CAUSAL = "PROVEN_CAUSAL_CONTEXT_DIFFERENCE"
CAPABLE = "CAPABLE_CONTEXT_DIFFERENCE"
NONCAUSAL = "OBSERVED_NONCAUSAL_DIFFERENCE"
INACTIVE = "NOT_ACTIVE_AT_FAILURE_BOUNDARY"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
EFFECTS = dict.fromkeys(("Docker", "SANDBOX2_issuance", "JAVA1C", "PINNED1A_export",
    "PINNED1B", "PINNED1C", "SYNTH_retry", "SyntheticStateBox", "reflection", "BANK",
    "EXECUTOR.1R", "Apply", "provider_root", "execution_leases"), 0)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def tree(path):
    return ast.parse(source(path), filename=path)


def function(path, name):
    return next(node for node in tree(path).body
                if isinstance(node, ast.FunctionDef) and node.name == name)


def ref(path, start, end=None):
    return {"path": path, "start_line": start, "end_line": end or start}


def source_identity(path, bindings):
    data = (ROOT / path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    historical = bindings.get(path)
    return {"path": path, "sha256": digest, "size_bytes": len(data),
            "retained_gate_sha256": historical,
            "matches_historical_gate": digest == historical if historical else None}


def outcome(candidates, historical_complete=False):
    """Fail closed: current capability alone cannot prove historical causality."""
    if any(row["classification"] == CAUSAL for row in candidates):
        return "NESTED_CONTEXT_CAUSE_ESTABLISHED"
    if any(row["classification"] == CAPABLE for row in candidates):
        return "NESTED_CONTEXT_CANDIDATE_ESTABLISHED"
    return "NO_RELEVANT_CONTEXT_DIFFERENCE_FOUND" if historical_complete else "UNRESOLVED"


def scoped_sources():
    """Exact live graph and conservative transitive project import inventory."""
    seeds = [RUNNER, PROVIDER, JAVA, SANDBOX, BASELINE,
             "core/synthetic_runtime_authorization_pinned.py"]
    pending, seen = list(seeds), set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        for node in ast.walk(tree(path)):
            # Imports in functions are included conservatively; validation-only
            # matches are classified separately and never assumed active.
            if isinstance(node, ast.ImportFrom):
                if node.module == "core":
                    names = ["core/" + alias.name + ".py" for alias in node.names]
                elif node.module and node.module.startswith("core."):
                    names = [node.module.replace(".", "/") + ".py"]
                else:
                    names = []
                pending.extend(name for name in names if (ROOT / name).is_file())
    return sorted(seen)


def static_inventory():
    needles = ("addaudithook", "audit", "setprofile", "settrace", "monitoring",
               "tempfile.tempdir", "gettempdir", "TemporaryDirectory", "os.environ",
               "chdir", "Popen", "subprocess.run", "shutil.which", "socket.socket",
               ".bind(", ".listen(", "patch.object", "JAVA_PROBE_SOURCE", "._invoke_java")
    findings = []
    for path in scoped_sources():
        for number, line in enumerate(source(path).splitlines(), 1):
            if any(needle in line for needle in needles):
                findings.append({"path": path, "line": number, "text": line.strip()})
    return {"scope": "AST-discovered project imports from exact retained live graph; line matches are lexical evidence and can include embedded workload strings",
            "sources": scoped_sources(), "matches": findings,
            "not_runtime_attestation": True,
            "limitation": "Parent harness, native policy, optional dependency import behavior and historical dynamic state were not fully retained."}


def temp_reproducer(scratch):
    """Use exact frozen statement/subtree, with PHASE rebound to new scratch."""
    scratch = Path(scratch).resolve()
    if not scratch.is_relative_to(HERE) or scratch == HISTORY:
        raise ValueError("new_phase_scratch_required")
    scratch.mkdir(parents=True, exist_ok=True)
    runner = function(RUNNER, "main")
    assignments = [n for n in ast.walk(runner) if isinstance(n, ast.Assign)
                   and any(ast.unparse(t) == "tempfile.tempdir" for t in n.targets)]
    setting = next(n for n in assignments if ast.unparse(n.value) == "str(PHASE)")
    workspace = next(n for n in ast.walk(function(SANDBOX, "replay"))
                     if isinstance(n, ast.With) and "TemporaryDirectory" in ast.unparse(n.items[0].context_expr))
    workspace = deepcopy(workspace)
    # The exact three setup statements precede the socket context. Socket and
    # ladder code are never compiled/executed in this pure control.
    assert len(workspace.body) == 4 and isinstance(workspace.body[3], ast.With)
    workspace.body = workspace.body[:3]
    workspace.body.append(ast.parse("captured.append({'root': root, 'profile': profile.read_bytes(), 'sentinel': sentinel.read_bytes()})").body[0])
    namespace = {"tempfile": tempfile, "PHASE": scratch, "Path": Path,
                 "POLICY_BYTES": (ROOT / "docs/roadmap/RUNTIME_SANDBOX_2_SECCOMP.json").read_bytes(), "captured": []}
    previous = tempfile.tempdir
    environment = {key: os.environ.get(key) for key in ("TMP", "TEMP", "TMPDIR")}
    try:
        exec(compile(ast.Module(body=[deepcopy(setting)], type_ignores=[]), RUNNER, "exec"), namespace)
        config_root = tempfile.gettempdir()
        exec(compile(ast.fix_missing_locations(ast.Module(body=[workspace], type_ignores=[])), SANDBOX, "exec"), namespace)
        captured = namespace["captured"][0]
        result = {"passed": Path(config_root) == scratch and Path(captured["root"]).parent == scratch,
                  "override_statement": ref(RUNNER, setting.lineno),
                  "workspace_subtree": ref(SANDBOX, workspace.lineno, workspace.end_lineno),
                  "config_root": config_root, "workspace": captured["root"],
                  "workspace_parent_equals_config_root": Path(captured["root"]).parent == Path(config_root),
                  "exact_workspace_file_writes_succeeded": bool(captured["profile"]) and captured["sentinel"] == b"phase-owned-host-sentinel",
                  "workspace_removed": not Path(captured["root"]).exists(),
                  "TMP_TEMP_TMPDIR_unchanged": environment == {key: os.environ.get(key) for key in environment},
                  "historical_folder_used": False, "socket_operations": 0, "owner_invocations": 0,
                  "historical_causality_proven": False}
    finally:
        tempfile.tempdir = previous
    result["tempfile_state_restored"] = tempfile.tempdir == previous
    return result


def profiler_reproducer(raise_in_verify=False):
    """Execute exact observer helper with stand-in functions; no runtime owner."""
    node = deepcopy(function(PROVIDER, "_runtime_snapshot"))
    class PureBlocked(ValueError):
        pass
    namespace = {"sys": sys, "PinnedProviderBlocked": PureBlocked,
                 "UNRESOLVED": "unresolved", "RUNTIME_MISMATCH": "mismatch"}
    state = {"profile_active_at_stub_boundary": False}
    def bounded(argv):
        return SimpleNamespace(exit_code=0, status="sandbox_completed")
    def invoke():
        return None
    def replay():
        state["profile_active_at_stub_boundary"] = sys.getprofile() is namespace["observer_installed"]
        return bounded(("docker-stub", "--config", "new-scratch", "--host", "stub", "image", "inspect"))
    def verify():
        namespace["observer_installed"] = sys.getprofile()
        if raise_in_verify:
            raise ValueError("pure_stub_failure")
        replay()
        return (None, None, {"pure_stub": True})
    namespace.update(sandbox=SimpleNamespace(_bounded_process=bounded),
                     sandbox2=SimpleNamespace(invoke=invoke, replay=replay),
                     runtime=SimpleNamespace(verify=verify),
                     _VERIFY_CODE=verify.__code__, _INVOKE_CODE=invoke.__code__)
    exec(compile(ast.Module(body=[node], type_ignores=[]), PROVIDER, "exec"), namespace)
    previous = sys.getprofile()
    try:
        result = namespace["_runtime_snapshot"]()
        assert len(result["controls"]) == 1
        assert result["controls"][0]["scope"] == "JAVA1C_SANDBOX2_infrastructure"
        state.update(passed=True, stub_controls_observed=1)
    except ValueError as error:
        if not raise_in_verify or str(error) != "pure_stub_failure":
            raise
        state.update(passed=True, expected_stub_exception_propagated=True)
    finally:
        # Frozen helper's finally must restore the existing instrumentation.
        state["profiler_restored_by_exact_helper"] = sys.getprofile() is previous
    state.update(owner_invocations=0, socket_operations=0, historical_causality_proven=False)
    return state


def audit_report():
    gates = read_json(HISTORY / "pure_preoperational_gates.json")
    bindings = {row["path"]: row["sha256"] for row in gates["source_bindings"]}
    local = read_json(HISTORY / "SYNTH_AUTH_PINNED_1_LOCAL.json")
    provider = local["provider_proof_report"]
    earlier = provider["pinned1b_report"]["bind_sandbox2_report"]
    controls = provider["runtime_docker_controls"]
    image = next(row for row in controls if row["command"] == "image")
    normal = read_json(ROOT / "docs/roadmap/phases/RUNTIME_SANDBOX_2_PRELADDER_DIAG_1/observed_controls.json")
    candidates = [
        {"id": "phase_local_temp_root", "owner": RUNNER,
         "sources": [ref(RUNNER, 49, 65), ref(RUNNER, 101, 102), ref(BASELINE, 363, 372), ref(SANDBOX, 335, 338)],
         "lifetime": "Whole authorization/provider call; restored only in outer finally after JAVA1C returns",
         "active_at_SANDBOX2": True, "restored_before_SANDBOX2": False,
         "affected_steps": ["private_config_path_derivation", "TemporaryDirectory", "policy_and_sentinel_writes"],
         "classification": NONCAUSAL,
         "basis": "Observed root difference is not itself a demonstrated denial. Earlier retained SANDBOX2 completed all 11 stages in this same lexical override. An unconditional root-wide denial is excluded; later state/ACL changes are unrecorded.",
         "historical_causality_proven": False},
        {"id": "provider_return_frame_profiler", "owner": PROVIDER,
         "sources": [ref(PROVIDER, 246, 297), ref(PROVIDER, 505, 537)],
         "lifetime": "sys.setprofile(observer) around runtime.verify(), including JAVA1C and SANDBOX2",
         "active_at_SANDBOX2": True, "restored_before_SANDBOX2": False,
         "affected_steps": ["Python_return_events", "bounded_process_return_accounting"],
         "classification": NONCAUSAL,
         "basis": "Exact observer reads returns/locals and appends private accounting; contains no audit registration, socket/write/process rejection or owner replacement. Same frozen observer existed in successful PINNED1C retry. Timing effects cannot be reconstructed.",
         "historical_causality_proven": False},
        {"id": "PINNED1B_transport_and_replay_observers", "owner": "core/runtime_java_pinned_backend_target_binding.py",
         "sources": [ref("core/runtime_java_pinned_backend_target_binding.py", 347, 373), ref(PROVIDER, 523, 537)],
         "lifetime": "patch.object only around upstream backend binding; exits before target inspection and provider JAVA1C call",
         "active_at_SANDBOX2": False, "restored_before_SANDBOX2": True,
         "affected_steps": ["earlier_upstream_bounded_process_and_SANDBOX2_only"],
         "classification": INACTIVE, "basis": "Lexical with scope exited before fresh JAVA1C; no persistent function assignment follows."},
        {"id": "BIND_transport_observer", "owner": "core/sandbox_backend_binding.py",
         "sources": [ref("core/sandbox_backend_binding.py", 290, 362)],
         "lifetime": "Scoped transport patch during upstream BIND replay",
         "active_at_SANDBOX2": False, "restored_before_SANDBOX2": True,
         "affected_steps": ["earlier_upstream_transport_only"],
         "classification": INACTIVE, "basis": "Upstream BIND returns before PINNED1B and provider runtime snapshot."},
        {"id": "successful_retry_private_config_tracer", "owner": "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C_RETRY/authentication_controls.py",
         "sources": [ref("scripts/replay_runtime_java_pinned1c_retry.py", 53, 65), ref(RUNNER, 60, 65), ref("docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C_RETRY/authentication_controls.py", 27, 69)],
         "lifetime": "Different successful retry runner only; not entered by blocked SYNTH runner",
         "active_at_SANDBOX2": False, "restored_before_SANDBOX2": None,
         "affected_steps": [], "classification": INACTIVE,
         "basis": "Exact blocked runner does not import or enter this context manager."},
        {"id": "validation_only_audit_guards", "owner": "retained validation workers and tests",
         "sources": [ref("docs/roadmap/phases/RUNTIME_SANDBOX_2_PRELADDER_DIAG_1/validation.py", 114, 169)],
         "lifetime": "Separate pure validation worker processes; direct live launch starts a fresh Python interpreter",
         "active_at_SANDBOX2": False, "restored_before_SANDBOX2": None,
         "affected_steps": [], "classification": INACTIVE,
         "basis": "Recovered original launch invokes python -B scripts/replay_synth_auth_pinned1.py directly. Audit hooks in other Python validation workers are not inherited by this fresh process. No exact live-path registration exists; possible startup/native policy is separately unretained."},
        {"id": "runner_import_path_and_bytecode_flag", "owner": RUNNER,
         "sources": [ref(RUNNER, 10, 11)],
         "lifetime": "Entire fresh process",
         "active_at_SANDBOX2": True, "restored_before_SANDBOX2": False,
         "affected_steps": ["module_resolution", "implicit_bytecode_output"], "classification": NONCAUSAL,
         "basis": "Workspace import root and bytecode suppression do not reject explicit workspace writes or sockets; source bindings match. -B is also used by the successful diagnostic."},
        {"id": "negative_authentication_controls", "owner": "provider and SYNTH negative matrices",
         "sources": [ref(RUNNER, 69, 92), ref(PROVIDER, 656), ref("core/synthetic_runtime_authorization_pinned.py", 400, 411),
             ref("core/runtime_java_pinned_backend_target_binding.py", 525), ref("core/sandbox_backend_binding.py", 417)],
         "lifetime": "After successful authorization only; branch skipped in blocked attempt",
         "active_at_SANDBOX2": False, "restored_before_SANDBOX2": None,
         "affected_steps": [], "classification": INACTIVE,
         "basis": "PID/HMAC/authority/object mutation controls are later success-only functions; no entry before historical failed SANDBOX2."},
        {"id": "JAVA1B_recovered_controller_binding", "owner": "core/sandboxed_java_capture_recovery.py",
         "sources": [ref("core/sandboxed_java_capture_recovery.py", 134, 149), ref("core/sandboxed_java_capture_recovery.py", 191)],
         "lifetime": "Scoped JAVA1B replay context replaces JAVA_PROBE_SOURCE/_invoke_java and restores in finally",
         "active_at_SANDBOX2": False, "restored_before_SANDBOX2": None,
         "affected_steps": [], "classification": INACTIVE,
         "basis": "Imported helper is not entered by the historical PINNED1C->JAVA1C live call path; JAVA1B replay is not run."},
        {"id": "provider_registry_globals", "owner": "core.runtime_java_pinned_provider and upstream owners",
         "sources": [ref(PROVIDER, 42, 44), ref(PROVIDER, 507, 529), ref(SANDBOX, 317, 344),
             ref("core/runtime_java_pinned_backend_target_binding.py", 34, 39),
             ref("core/runtime_java_pinned_backend_target_binding.py", 249, 273),
             ref("core/runtime_java_pinned_backend_target_binding.py", 334),
             ref("core/sandbox_backend_binding.py", 43, 46), ref("core/sandbox_backend_binding.py", 346),
             ref("core/runtime_java_pinned_target_inspection.py", 198)],
         "lifetime": "Process-local attempts/origins and authenticated upstream registries persist",
         "active_at_SANDBOX2": True, "restored_before_SANDBOX2": False,
         "affected_steps": [], "classification": NONCAUSAL,
         "basis": "SANDBOX2 pre-ladder code does not consume provider registries. Their source bindings match retained gates; historical dynamic values/function identities were not retained. No surviving replacement is prescribed by the live source."},
        {"id": "unretained_parent_or_late_host_state", "owner": "historical caller/harness/OS",
         "sources": [ref(RUNNER, 42, 65)], "lifetime": "Unknown",
         "active_at_SANDBOX2": None, "restored_before_SANDBOX2": None,
         "affected_steps": ["metadata_parse", "workspace_creation_and_writes", "TCP_UDP_socket_setup"],
         "classification": INSUFFICIENT,
         "basis": "Original nested SANDBOX2 report/pair, startup/native policies, socket policy, env snapshot, and first failed statement were not retained. Direct original launch and cwd are recovered separately."},
    ]
    identities = [source_identity(path, bindings) for path in scoped_sources()]
    result = {"phase_id": PHASE_ID, "status": outcome(candidates),
        "historical_truth": "historical nested root cause unresolved",
        "historical_failure_summary": {"SYNTH_status": local["status"], "SYNTH_reason": local["reason"],
            "provider_status": provider["status"], "provider_reason": provider["reason"],
            "JAVA1C_status": provider["java1c_report"]["status"],
            "JAVA1C_error": provider["java1c_report"]["controller_error"],
            "generic_not_authenticated_demonstrates_HMAC_failure": False,
            "failed_period_container_creates": sum(row["command"] == "create" for row in controls),
            "failed_period_container_starts": sum(row["command"] == "start" for row in controls)},
        "exact_historical_root_cause_established": False,
        "historical_runner": source_identity(RUNNER, bindings),
        "historical_source_identities": identities,
        "all_available_live_graph_gate_hashes_match": all(row["matches_historical_gate"] is not False for row in identities),
        "historical_temp_state": {"tempfile.tempdir_at_boundary": str(HISTORY),
            "tempfile.gettempdir_at_boundary": str(HISTORY), "previous_tempfile.tempdir": "NOT_RETAINED",
            "TMP": "NOT_RETAINED", "TEMP": "NOT_RETAINED", "TMPDIR": "NOT_RETAINED",
            "explicit_override_owner": ref(RUNNER, 61), "restoration": ref(RUNNER, 102),
            "pytest_basetemp_in_live_runner": "No pytest invocation; pytest.ini is validation-only",
            "lexical_phase_context": "Whole issuer call; temp root itself is not a TemporaryDirectory context"},
        "historical_cwd": {"value": str(ROOT), "runner_chdir": False,
            "evidence": "historical_launch_provenance.json: original session_meta/turn_context plus direct launch without workdir override",
            "validation_cwd_is_not_live_cwd_proof": True,
            "effect": "Config/workspace roots are absolute; Docker binary is absolute. Parent cwd can affect PATH resolution but image inspect already succeeded."},
        "environment_overlays": {"live_runner_overlays": [],
            "Docker_child": {"source": ref(BASELINE, 294, 303),
                "keys": ["SystemRoot_if_present", "WINDIR_if_present", "CATTUS_SANDBOX_HOST_ONLY"],
                "description": "Same minimal env for image inspect and subsequent controls; TMP/TEMP/TMPDIR and Docker env/context variables are not inherited into child."},
            "historical_full_environment": "NOT_RETAINED"},
        "historical_audit_hooks": {"registration_on_retained_live_path": [], "startup_or_native_hooks": "NOT_RETAINED",
            "pure_validation_worker_hooks_inherited_into_live_process": False,
            "unconditional_subprocess_ban_excluded": True, "unconditional_socket_ban_for_whole_attempt_excluded": True},
        "historical_socket_guards": {"live_graph_socket_patches_found": [],
            "required_operations": ["socket.socket()", "socket.socket(AF_INET, SOCK_DGRAM)", "TCP bind 127.0.0.1:0", "TCP listen(1)", "UDP bind 127.0.0.1:selected_port"],
            "historical_later_setup_outcome": "NOT_RETAINED", "current_sockets_attempted": 0,
            "exact_rule_active_at_boundary_proven": False},
        "historical_process_guards": {"Popen_run_which_patches_on_live_path": [],
            "scoped_bounded_process_observers": "Exited before JAVA1C", "image_inspect_allowed": image["completed"] and image["exit_code"] == 0,
            "later_SANDBOX2_ps_allowed": all(row["completed"] and row["exit_code"] == 0 for row in controls),
            "pre_create_process_after_image": "No additional subprocess until ladder; workspace/socket work occurs first"},
        "historical_instrumentation": {"sys_profile": "Exact provider return-frame observer active",
            "preexisting_sys_profile": "Required None by provider guards; reaching JAVA1C demonstrates gates returned",
            "sys_trace": "NOT_RETAINED; no setter in blocked live graph",
            "threading_profile": "NOT_RETAINED; no setter in blocked live graph",
            "threading_trace": "NOT_RETAINED; no setter in blocked live graph",
            "sys_monitoring": "NOT_RETAINED; no mutation in blocked live graph"},
        "historical_module_globals": {"tempfile_tempdir": "Override survives boundary",
            "provider_registries": "Persist but unused by SANDBOX2 pre-ladder",
            "candidate_runtime_sandbox_functions": "Scoped observer restored before JAVA1C",
            "thread_compatible_runtime_sandbox_replay": "Scoped observer restored before JAVA1C",
            "environment_mapping_mutations": [], "historical_dynamic_function_identities": "NOT_RETAINED"},
        "active_at_SANDBOX2_matrix": candidates,
        "temp_root_differential": {"historical_config_path": image["argv"][2],
            "same_root_governs_TemporaryDirectory": True,
            "successful_standalone_control_artifact": "docs/roadmap/phases/RUNTIME_SANDBOX_2_PRELADDER_DIAG_1/observed_controls.json",
            "standalone_private_config_roots": sorted({str(Path(row["argv"][2]).parent) for row in normal}),
            "standalone_control_count": len(normal),
            "earlier_same_attempt_SANDBOX2": {"status": earlier["status"], "stage_count": len(earlier["stages"]),
                "cleanup_verified": earlier["cleanup_verified"], "workspace_removed": earlier["temporary_workspace_removed"]},
            "historical_presence_and_writes": "Output reservation and earlier successful workspace prove presence and writable operations earlier in same call; later ACL/path state is unknown",
            "historical_symlink_ACL_write_denial_cleanup": "No retained boundary snapshot; no source code cleans phase root before JAVA1C",
            "current_readonly_path_observation_artifact": "historical_path_current_observation.json"},
        "socket_differential": "Earlier same-attempt sockets succeeded; no active denying rule identified at later boundary. Conditional startup/native policy or OS failure remains unmeasured. No unrelated validation audit rule is promoted to a candidate.",
        "subprocess_differential": {"historical_controls": controls,
            "global_processes_forbidden_theory": "EXCLUDED by successful exact image inspect and cleanup ps",
            "source_observer_does_not_reject_processes": True},
        "missing_historical_evidence": ["nested_SANDBOX2_report_descriptor_receipt", "parsed_image_metadata", "private_config_absence_at_boundary", "workspace_setup", "host_socket_setup", "first_pre_ladder_failure", "owner_cleanup_details", "stage_list", "parent_process_context"],
        "separate_strict_resolution_probe": {"artifact": "docs/roadmap/phases/SYNTH_AUTH_PINNED_1/workspace_strict_resolution_sandbox_probe.json",
            "classification": INSUFFICIENT,
            "basis": "Separate restricted metadata probe is not the direct host live attempt; SANDBOX2 post-image setup does not use strict workspace resolution. It cannot establish a historical write/socket denial."},
        "SANDBOX2_source_changed": False, "JAVA1C_source_changed": False, "SYNTH_retried": False,
        "remediation_implemented": False, "operational_effects": EFFECTS,
        "recommended_next_slice": {"action": "One separately authorized instrumented fresh SYNTH.AUTH.PINNED.1 authorization retry",
            "execute_in_this_phase": False,
            "retain": ["original fresh SANDBOX2 full report", "original pair observed and authenticated in issuing process; exported pair remains report only", "parsed image metadata and private config absence", "ordered pre-ladder entries/completions/exceptions including first failed statement", "tempdir/gettempdir/TMP/TEMP/TMPDIR/cwd at boundary", "workspace/symlink/ACL and socket outcomes", "system/thread profile/trace/monitoring and guard ownership", "owner cleanup and remaining container evidence"],
            "design": "Bind exact owner source hashes; observe exact code objects without owner replacement; retain every outcome including failures; restore instrumentation; avoid secrets, frames and capability persistence; stop at authorization boundary."}}
    return result


def main():
    if len(sys.argv) != 1:
        raise ValueError("no_arguments_required")
    report = audit_report()
    report["pure_reproducer"] = temp_reproducer(HERE / "scratch" / "temp_root_control")
    report["profiler_pure_controls"] = [profiler_reproducer(), profiler_reproducer(True)]
    for name, data in (("source_context_inventory.json", static_inventory()),
                       ("RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1_REPORT.json", report)):
        (HERE / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "exact_historical_root_cause_established": False,
                      "operational_effects": EFFECTS}, sort_keys=True))


if __name__ == "__main__":
    main()
