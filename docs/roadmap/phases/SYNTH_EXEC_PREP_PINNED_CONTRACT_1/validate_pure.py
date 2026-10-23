"""Reproducible pure validation with no imports of capability owners.

The frozen regression selection executes only inspected AST/source test bodies,
using file-name facades; no owner module, capability, registry or secret exists.
Registry/picker tests and benchmark --check are report-only. All scratch and
evidence writes stay in this new phase; every write outside it is denied.
The baseline already exists and must never be overwritten.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
from hashlib import sha256
import io
import builtins
import re
import subprocess
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
NEW_TEST = "docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/test_contract.py"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
CAPABILITY_PREFIXES = (
    "core.synthetic_", "core.runtime_java_", "core.behavioral_diagnostic_executor",
    "core.read_only_reflection", "core.sandboxed_java_",
    "core.candidate_runtime_", "core.thread_compatible_runtime_",
    "core.sandbox_backend_", "core.runtime_diagnostic_",
    "core.behavioral_execution_admission", "core.behavioral_validation_specification",
    "core.behavioral_evidence_execution_plan",
)


def write_json(name, data):
    (OUTPUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@contextlib.contextmanager
def operational_guard():
    active = [True]
    evidence = dict.fromkeys(("process_attempts", "network_attempts",
        "outside_phase_write_attempts", "capability_owner_import_attempts",
        "capability_or_transition_attempts", "execution_or_verification_attempts"), 0)
    blocked = []

    def reject(kind, detail):
        evidence[kind] += 1
        blocked.append(str(detail))
        raise AssertionError("Pure preparation contract denied: " + str(detail))

    def outside_phase(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return False
        resolved = Path(os.fsdecode(path)).resolve()
        return not resolved.is_relative_to(OUTPUT)

    def audit(event, args):
        if not active[0]:
            return
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile"}:
            reject("process_attempts", event)
        if event in {"socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo"}:
            reject("network_attempts", event)
        if event == "import" and str(args[0]).startswith(CAPABILITY_PREFIXES):
            reject("capability_owner_import_attempts", args[0])
        if event == "open":
            path, mode, flags = args
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                if outside_phase(path):
                    reject("outside_phase_write_attempts", "open:" + str(path))
        if event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.chmod", "os.truncate", "os.utime"}:
            if any(outside_phase(path) for path in args[:2]):
                reject("outside_phase_write_attempts", event + ":" + str(args))

    def profile(frame, event, arg):
        if not active[0] or event != "call":
            return
        code = frame.f_code
        if not code.co_filename.startswith(str(ROOT / "core") + os.sep):
            return
        name = code.co_name
        if name in {"_issue", "_issue_upstream", "_transition", "executor1r_before_request", "executor1r_after_request"} or name.startswith(("issue_", "consume_", "invalidate_")):
            reject("capability_or_transition_attempts", code.co_filename + ":" + name)
        if name == "verify" or name.startswith(("execute_", "run_")):
            reject("execution_or_verification_attempts", code.co_filename + ":" + name)

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        candidates = [name, *(name + "." + item for item in (fromlist or ()) if isinstance(item, str))]
        if any(value.startswith(CAPABILITY_PREFIXES) for value in candidates):
            reject("capability_owner_import_attempts", name)
        return original_import(name, globals, locals, fromlist, level)

    sys.addaudithook(audit)
    previous, previous_threads = sys.getprofile(), threading.getprofile()
    sys.setprofile(profile)
    threading.setprofile(profile)
    try:
        with patch.object(builtins, "__import__", guarded_import):
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
        with patch.object(socket, "has_ipv6", False), operational_guard() as (evidence, blocked), contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
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
                nodes = [NEW_TEST] if mode == "focused" else ["tests/test_phase_registry.py", "tests/test_phase_picker.py"]
                result["selected_nodes"] = nodes
                result["exit_code"] = int(pytest.main([*nodes, "-q", "-p", "no:cacheprovider",
                    "-o", "addopts=", "-o", "log_file=" + str(scratch / "pytest.log"),
                    "--basetemp=" + str(scratch / "pytest")], plugins=[plugin]))
                result.update(collected=plugin.collected, passed_count=len(plugin.passed),
                    passed_nodes=plugin.passed, failed=sorted(plugin.failed, key=lambda row: (row["nodeid"], row["when"])),
                    skipped=plugin.skipped)
                if mode.startswith("registry"):
                    from core.phase_registry import load_phase_registry, summarize_phase_registry
                    from core.phase_picker import pick_phase_candidates
                    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
                    result["registry_summary"] = summarize_phase_registry(registry,
                        report_id="execution-preparation-pinned-contract", created_at="2026-10-18")
                    result["picker"] = pick_phase_candidates(registry)
    except Exception as error:
        traceback.print_exc(file=log)
        result.update(exit_code=2, error=type(error).__name__ + ": " + str(error))
    result.update(audit_guard=evidence, blocked_actions=blocked,
        all_operational_effects_zero=not any(evidence.values()) and not blocked,
        imported_capability_owners=sorted(name for name in sys.modules if name.startswith(CAPABILITY_PREFIXES)))
    if result["imported_capability_owners"] or not result["all_operational_effects_zero"]:
        result["exit_code"] = result.get("exit_code") or 3
    (OUTPUT / (mode + ".txt")).write_text(log.getvalue(), encoding="utf-8")
    write_json(mode + ".json", result)
    print(json.dumps({key: value for key, value in result.items() if key not in {
        "picker", "registry_summary", "passed_nodes", "selected_nodes"}}, indent=2))
    return result["exit_code"]



PRESERVATION_SCOPES = ("core", "tests", "scripts", "benchmarks", "docs/roadmap")
CACHE_NAMES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv", "node_modules"}


def read_json(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def preservation_check():
    files = {}
    excluded = []
    for scope in PRESERVATION_SCOPES:
        for current, dirs, names in os.walk(ROOT / scope):
            base = Path(current)
            retained = []
            for name in sorted(dirs):
                target = base / name
                if target == OUTPUT or name in CACHE_NAMES:
                    excluded.append(target.relative_to(ROOT).as_posix() + "/")
                else:
                    retained.append(name)
            dirs[:] = retained
            for name in sorted(names):
                path = base / name
                data = path.read_bytes()
                files[path.relative_to(ROOT).as_posix()] = {"sha256": sha256(data).hexdigest(), "bytes": len(data)}
    baseline = read_json("preservation_baseline.json")["files"]
    result = {
        "baseline_file_count": len(baseline), "after_file_count": len(files),
        "changed": sorted(name for name in baseline.keys() & files.keys() if baseline[name] != files[name]),
        "deleted": sorted(baseline.keys() - files.keys()),
        "added_outside_new_phase": sorted(files.keys() - baseline.keys()),
        "scope": list(PRESERVATION_SCOPES), "allowed_additions_outside_phase": [],
    }
    result["historical_preservation_passed"] = not any(result[key] for key in ("changed", "deleted", "added_outside_new_phase"))
    write_json("preservation_after.json", {"file_count": len(files), "files": files, "excluded": excluded})
    write_json("preservation_comparison.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["historical_preservation_passed"] else 1


def static_validation():
    compiled, json_validated, errors, whitespace = [], [], [], []
    phase_files = [path for path in OUTPUT.rglob("*") if path.is_file()
        and "validation_tmp" not in path.relative_to(OUTPUT).parts]
    frozen_python = [path for scope in PRESERVATION_SCOPES for path in (ROOT / scope).rglob("*.py")
        if not path.is_relative_to(OUTPUT) and not any(name in CACHE_NAMES for name in path.parts)]
    for path in [*phase_files, *frozen_python]:
        if path.suffix not in {".py", ".json", ".md"}:
            continue
        name = path.relative_to(ROOT).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix == ".py":
                compile(content, str(path), "exec")
                compiled.append(name)
            elif path.suffix == ".json":
                json.loads(content)
                json_validated.append(name)
            if path in phase_files:
                whitespace.extend({"file": name, "line": line} for line, value in enumerate(content.splitlines(), 1) if value.rstrip() != value)
        except Exception as error:
            errors.append({"file": name, "error": type(error).__name__ + ": " + str(error)})
    result = {"compiled_in_memory": compiled, "compiled_count": len(compiled),
        "json_validated": json_validated, "json_count": len(json_validated), "errors": errors,
        "whitespace_errors": whitespace, "bytecode_written": False, "owner_modules_imported": False,
        "whitespace_scope": "new phase authored .py/.json/.md; captured diagnostics preserved verbatim",
        "passed": not errors and not whitespace}
    write_json("static_validation.json", result)
    print(json.dumps({key: value for key, value in result.items() if key not in {"compiled_in_memory", "json_validated"}}, indent=2))
    return 0 if result["passed"] else 1


def git_diff_check():
    # Explicit exception: source-control whitespace validation, outside the
    # operational guard. This launches git only; it does not run an owner.
    command = ["git", "diff", "--check"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    (OUTPUT / "git_diff_check.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    evidence = {"command": command, "exit_code": result.returncode,
        "executed_outside_operational_guard": True, "source_validation_only": True,
        "operational_command_invoked": False}
    write_json("git_diff_check.json", evidence)
    print(json.dumps(evidence))
    return result.returncode


def finalize():
    baseline, after = read_json("registry_baseline.json"), read_json("registry_after.json")
    keys = ("collected", "passed_nodes", "failed", "skipped", "registry_summary", "picker")
    comparison = {"unchanged": all(baseline[key] == after[key] for key in keys),
        "baseline_collected": baseline["collected"], "after_collected": after["collected"],
        "baseline_passed": baseline["passed_count"], "after_passed": after["passed_count"],
        "baseline_failed": baseline["failed"], "after_failed": after["failed"],
        "existing_failures_preserved": baseline["failed"] == after["failed"],
        "registry_and_picker_projections_identical": all(baseline[key] == after[key] for key in ("registry_summary", "picker")),
        "old_files_not_modified_to_repair_baseline": True}
    write_json("registry_comparison.json", comparison)
    runs = {name: read_json(name + ".json") for name in ("registry_baseline", "registry_after", "focused", "frozen", "benchmark")}
    benchmark_text = (OUTPUT / "benchmark.txt").read_text(encoding="utf-8")
    checked = re.search(r"^Checked: (\d+)$", benchmark_text, re.MULTILINE)
    errors = re.search(r"^Errors: (\d+)$", benchmark_text, re.MULTILINE)
    preservation, static, diff = (read_json(name + ".json") for name in ("preservation_comparison", "static_validation", "git_diff_check"))
    zero = all(item["all_operational_effects_zero"] and not item["imported_capability_owners"] for item in runs.values())
    result = {"phase_id": "SYNTH.EXEC.PREP.PINNED.CONTRACT.1", "registry_picker": comparison,
        "all_guarded_runs_zero_attempts": zero, "all_actual_operational_effects_zero": zero,
        "capability_owners_imported": False, "owner_tests_run": False,
        "benchmark_cases_checked": int(checked.group(1)) if checked else None,
        "benchmark_errors": int(errors.group(1)) if errors else None,
        "historical_preservation": preservation, "static_validation_passed": static["passed"], "git_diff_check": diff,
        "source_validation_subprocess_exception": "git status baseline and git diff --check only, outside operational guard",
        "artifact_hashes": {path.name: sha256(path.read_bytes()).hexdigest() for path in (OUTPUT / "contract.json", OUTPUT / "test_contract.py", Path(__file__))}}
    for name, item in runs.items():
        result[name] = {key: item[key] for key in ("exit_code", "audit_guard", "all_operational_effects_zero")}
        if name != "benchmark":
            result[name].update(collected=item["collected"], passed=item["passed_count"], failed=item["failed"])
    result["validation_passed"] = comparison["unchanged"] and zero and preservation["historical_preservation_passed"] and static["passed"] and diff["exit_code"] == 0 and result["benchmark_errors"] == 0 and all(runs[name]["exit_code"] == 0 for name in ("focused", "frozen", "benchmark"))
    result["preexisting_registry_test_failures_accepted_only_if_identical"] = bool(baseline["failed"]) and comparison["unchanged"]
    write_json("validation_summary.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["validation_passed"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("registry_baseline", "registry_after", "frozen", "focused", "benchmark", "static", "preservation", "finalize", "git_diff"))
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.mode == "static":
        return static_validation()
    if args.mode == "preservation":
        return preservation_check()
    if args.mode == "git_diff":
        return git_diff_check()
    if args.mode == "finalize":
        return finalize()
    return validate(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
