"""Safe source/AST and isolated validation for pinned reflection lifecycle.

The frozen regression selection executes only inspected AST/source test bodies,
using file-name facades; no owner module, capability, registry or secret exists.
Registry/picker tests and benchmark --check are report-only. All scratch and
evidence writes stay in this new phase; operational writes are denied.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import platform
import runpy
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace
import traceback
from unittest.mock import patch

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
CONTRACT_TEST = "tests/test_synthetic_reflection_pinned_contract.py"
ISOLATED_TEST = "tests/test_synthetic_reflection_execution_lifecycle_pinned.py"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
CAPABILITY_PREFIXES = (
    "core.synthetic_", "core.runtime_java_", "core.behavioral_diagnostic_executor",
    "core.read_only_reflection", "core.sandboxed_java_",
)


def write_json(name, data):
    (OUTPUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@contextlib.contextmanager
def operational_guard(*, allow_owner_imports=False):
    active = [True]
    evidence = dict.fromkeys(("process_attempts", "network_attempts",
        "repository_runtime_write_attempts", "capability_owner_import_attempts",
        "capability_or_transition_attempts", "execution_or_verification_attempts",
        "production_validator_attempts"), 0)
    blocked = []

    def reject(kind, detail):
        evidence[kind] += 1
        blocked.append(str(detail))
        raise AssertionError("Pure reflection lifecycle audit denied: " + str(detail))

    def outside_phase_inside_root(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return False
        resolved = Path(os.fsdecode(path)).resolve()
        return resolved.is_relative_to(ROOT) and not resolved.is_relative_to(OUTPUT)

    def audit(event, args):
        if not active[0]:
            return
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile"}:
            reject("process_attempts", event)
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            reject("network_attempts", event)
        if event == "import" and not allow_owner_imports and str(args[0]).startswith(CAPABILITY_PREFIXES):
            reject("capability_owner_import_attempts", args[0])
        if event == "open":
            path, mode, flags = args
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                if outside_phase_inside_root(path):
                    reject("repository_runtime_write_attempts", "open:" + str(path))
        if event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename"}:
            if any(outside_phase_inside_root(path) for path in args[:2]):
                reject("repository_runtime_write_attempts", event + ":" + str(args))

    def profile(frame, event, arg):
        if not active[0] or event != "call":
            return
        code = frame.f_code
        if not code.co_filename.startswith(str(ROOT / "core") + os.sep):
            return
        name = code.co_name
        if allow_owner_imports and name.startswith("validate_") and Path(code.co_filename).name.startswith(("synthetic_", "runtime_java_")):
            reject("production_validator_attempts", code.co_filename + ":" + name)
        if name in {"_issue", "_issue_upstream", "_transition", "executor1r_before_request", "executor1r_after_request"} or name.startswith(("issue_", "consume_", "invalidate_")):
            reject("capability_or_transition_attempts", code.co_filename + ":" + name)
        if name == "verify" or name.startswith(("execute_", "run_")):
            reject("execution_or_verification_attempts", code.co_filename + ":" + name)

    sys.addaudithook(audit)
    previous, previous_threads = sys.getprofile(), threading.getprofile()
    sys.setprofile(profile)
    threading.setprofile(profile)
    try:
        yield evidence, blocked
    finally:
        active[0] = False
        sys.setprofile(previous)
        threading.setprofile(previous_threads)


class Results:
    def __init__(self):
        self.collected, self.passed, self.failed, self.skipped = 0, [], [], []

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.failed.append({"nodeid": report.nodeid, "when": report.when})
        elif report.skipped:
            self.skipped.append(report.nodeid)
        elif report.when == "call" and report.passed:
            self.passed.append(report.nodeid)


def facade(name, literals=()):
    """A source path plus explicitly whitelisted literal values; never a module."""
    path = ROOT / "core" / (name + ".py")
    result = SimpleNamespace(__file__=str(path), __name__="core." + name)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for literal in literals:
        node = next(node for node in tree.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == literal for target in node.targets))
        setattr(result, literal, ast.literal_eval(node.value))
    return result


def extract_functions(relative, names, namespace):
    """Strip test decorators, imports and fixtures; preserve inspected bodies."""
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = []
    for name in names:
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        node.decorator_list = []
        nodes.append(node)
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, "<source-only:" + relative + ">", "exec"), namespace)


def frozen_regressions():
    source = "tests/test_synthetic_reflection_lifecycle_pinned_compat.py"
    helpers = ("_tree", "_function", "_calls", "_call_names", "_attributes")
    checks = [
        ("test_exact_old_runtime_type_gate_precedes_registry_and_live_identity_checks", [()]),
        ("test_reflection_lease_projects_runtime_and_old_authorization_identity", [()]),
        ("test_reflection_validation_reauthenticates_live_upstreams_and_signed_current_state", [()]),
        ("test_runtime_state_is_authenticated_through_old_public_state_api", [()]),
        ("test_issuance_and_precheck_require_issued_runtime_for_both_roles", [()]),
        ("test_active_precheck_and_reflection_consumption_require_consumed_runtime_for_both_roles", [()]),
        ("test_before_after_sequence_preserves_pinned_first_behavior_boundary_and_compile_dependency", [()]),
        ("test_exact_read_primitive_literals_are_authorization_epoch_independent", [("_BEFORE_HELPER",), ("_AFTER_HELPER",)]),
        ("test_positive_frozen_lifecycle_and_reflection_verifiers_are_outside_zero_issuance_scope", [()]),
        ("test_historical_executor_blocked_semantics_remain_source_only", [
            ("behavioral_diagnostic_executor_refresh", "existing_synthetic_issuer_cannot_reconstruct_independent_scenario"),
            ("behavioral_diagnostic_executor_retry", "frozen_synth_auth_1_has_no_public_consumption_contract"),
            ("behavioral_diagnostic_executor_lifecycle_retry", "java_profile_contract_mismatch")]),
    ]
    namespace = {
        "ast": ast, "Path": Path, "json": json, "ROOT": ROOT,
        "PINNED_CONTRACT": ROOT / "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/contract.json",
        "old_auth": facade("synthetic_runtime_authorization"),
        "old_runtime": facade("synthetic_runtime_authorization_lifecycle"),
        "pinned_runtime": facade("synthetic_runtime_authorization_pinned_lifecycle"),
        "primitive": facade("synthetic_read_only_reflection", ("_BEFORE_HELPER", "_AFTER_HELPER")),
        "admission": facade("synthetic_reflection_execution_admission"),
        "reflection": facade("synthetic_reflection_execution_lifecycle", ("EXECUTOR_SEQUENCE",)),
    }
    extract_functions(source, (*helpers, *(name for name, _ in checks)), namespace)
    passed, failed = [], []
    for name, cases in checks:
        for values in cases:
            label = source + "::" + name + ("[" + ",".join(values) + "]" if values else "")
            try:
                namespace[name](*values)
                passed.append(label)
            except Exception as error:
                failed.append({"nodeid": label, "error": type(error).__name__ + ": " + str(error)})
                traceback.print_exc()
    pinned_source = "tests/test_synthetic_runtime_authorization_pinned_lifecycle.py"
    pinned_check = "test_owner_has_no_provider_issuer_private_upstream_registry_or_old_signing_bridge"
    pinned_namespace = {"ast": ast, "OWNER_PATH": ROOT / "core/synthetic_runtime_authorization_pinned_lifecycle.py"}
    extract_functions(pinned_source, (pinned_check,), pinned_namespace)
    try:
        pinned_namespace[pinned_check]()
        passed.append(pinned_source + "::" + pinned_check)
    except Exception as error:
        failed.append({"nodeid": pinned_source + "::" + pinned_check, "error": str(error)})
        traceback.print_exc()
    return {"exit_code": 0 if not failed else 1, "collected": len(passed) + len(failed),
        "passed_count": len(passed), "passed_nodes": passed, "failed": failed, "skipped": [],
        "source_only_extraction": True, "capability_classes_constructed": False,
        "owner_modules_imported": False, "test_fixtures_executed": False}


def validate(mode):
    if mode == "registry_baseline" and (OUTPUT / "registry_baseline.json").exists():
        raise AssertionError("Original baseline cannot be overwritten")
    scratch = OUTPUT / "validation_tmp" / mode
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch))
    tempfile.tempdir = str(scratch)
    if sys.platform == "win32":
        version = sys.getwindowsversion()
        platform._uname_cache = platform.uname_result("Windows", os.environ.get("COMPUTERNAME", ""),
            str(version.major), ".".join(map(str, version[:3])), os.environ.get("PROCESSOR_ARCHITECTURE", ""))
    log = io.StringIO()
    result = {"mode": mode, "scratch_inside_new_phase": str(scratch),
        "bytecode_writes_disabled": True, "full_issuance_dependent_suites_run": False,
        "production_registries_seeded": False, "production_validators_patched": False,
        "harness_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    evidence, blocked = {}, []
    try:
        # urllib3 probes IPv6 by binding a socket during import. Disable only
        # that dependency availability probe, as in the frozen pure audit.
        with patch.object(socket, "has_ipv6", False), operational_guard(allow_owner_imports=mode == "isolated") as (evidence, blocked), contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            if mode == "frozen":
                result.update(frozen_regressions())
            elif mode == "benchmark":
                sys.argv = [str(ROOT / "benchmarks/run_benchmarks.py"), "--check"]
                try:
                    runpy.run_path(sys.argv[0], run_name="__main__")
                    result["exit_code"] = 0
                except SystemExit as error:
                    result["exit_code"] = error.code
            else:
                import pytest
                plugin = Results()
                nodes = [ISOLATED_TEST] if mode == "isolated" else [CONTRACT_TEST] if mode == "focused" else ["tests/test_phase_registry.py", "tests/test_phase_picker.py"]
                result["selected_nodes"] = nodes
                result["exit_code"] = int(pytest.main([*nodes, "-q", "-p", "no:cacheprovider",
                    "-o", "addopts=", "-o", "log_file=" + str(scratch / "pytest.log"),
                    "--basetemp=" + str(scratch / "pytest"), "-k", "not test_contract_freezes_semantics_and_creates_no_owners_types_or_registry_entries"], plugins=[plugin]))
                result.update(collected=plugin.collected, passed_count=len(plugin.passed),
                    passed_nodes=plugin.passed, failed=sorted(plugin.failed, key=lambda row: (row["nodeid"], row["when"])),
                    skipped=plugin.skipped)
                if mode.startswith("registry"):
                    from core.phase_registry import load_phase_registry, summarize_phase_registry
                    from core.phase_picker import pick_phase_candidates
                    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
                    result["registry_summary"] = summarize_phase_registry(registry,
                        report_id="reflection-lifecycle-pinned-implementation", created_at="2026-10-15")
                    result["picker"] = pick_phase_candidates(registry)
    except Exception as error:
        traceback.print_exc(file=log)
        result.update(exit_code=2, error=type(error).__name__ + ": " + str(error))
    result.update(audit_guard=evidence, blocked_actions=blocked,
        all_operational_effects_zero=not any(evidence.values()) and not blocked,
        imported_capability_owners=sorted(name for name in sys.modules if name.startswith(CAPABILITY_PREFIXES)))
    result["readonly_production_imports_for_preservation_snapshots"] = mode == "isolated"
    if (result["imported_capability_owners"] and mode != "isolated") or not result["all_operational_effects_zero"]:
        result["exit_code"] = result.get("exit_code") or 3
    (OUTPUT / (mode + ".txt")).write_text(log.getvalue(), encoding="utf-8")
    write_json(mode + ".json", result)
    print(json.dumps({key: value for key, value in result.items() if key not in {
        "picker", "registry_summary", "passed_nodes", "selected_nodes"}}, indent=2))
    return result["exit_code"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("registry_baseline", "registry_after", "frozen", "focused", "isolated", "benchmark"))
    args = parser.parse_args()
    os.chdir(ROOT)
    return validate(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
