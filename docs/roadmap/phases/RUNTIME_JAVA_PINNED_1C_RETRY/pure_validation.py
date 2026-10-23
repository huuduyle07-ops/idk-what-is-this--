"""Additive corrected-retry pure gates; deny operational process/network effects.

All outputs belong to the retry directory. Attempt 1 artifacts are read only.
The validation temporary directory is unique and removed after each test run.
"""
from __future__ import annotations

import contextlib
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

FROZEN_TESTS = [
    "tests/test_runtime_java_requirement_pinned1.py",
    "tests/test_runtime_java_pinned_target_archive.py",
    "tests/test_runtime_java_pinned_target_inspection.py",
    "tests/test_runtime_java_pinned_backend_target_binding.py",
    "tests/test_runtime_sandbox_bind1.py",
    "tests/test_runtime_sandbox2.py",
    "tests/test_runtime_java1c.py",
    "tests/test_runtime_java_discovery_contract1.py",
    "tests/test_synthetic_runtime_authorization.py",
    "tests/test_patch_candidate_behavior_executor1.py",
    "tests/test_patch_candidate_behavior_executor1r.py",
    "tests/test_patch_candidate_behavior_executor1r_retry.py",
    "tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py",
    "tests/test_runtime_java_discovery_diag1.py",
    "tests/test_runtime_java1.py",
    "tests/test_runtime_java1_discovery.py",
    "tests/test_runtime_java1_governance.py",
    "tests/test_runtime_java_compat1.py",
    "tests/test_runtime_java1d.py",
    "tests/test_runtime_java1d_retry.py",
]
REGISTRY_TESTS = ["tests/test_phase_registry.py", "tests/test_phase_picker.py"]
FOCUSED_TESTS = ["tests/test_runtime_java_pinned_provider.py",
                 "tests/test_runtime_java_pinned_provider_retry.py"]
CONFIG_PATH_TESTS = [
    "tests/test_runtime_java_pinned_provider.py::test_frozen_fresh_empty_docker_config_paths_do_not_change_backend_identity",
    "tests/test_runtime_java_pinned_provider.py::test_existing_docker_configuration_path_cannot_replace_frozen_empty_configuration",
    "tests/test_runtime_java_pinned_provider_retry.py::test_random_distinct_bind_and_runtime_private_configs_accept_exact_backend",
    "tests/test_runtime_java_pinned_provider_retry.py::test_each_private_config_absence_failure_rejects",
    "tests/test_runtime_java_pinned_provider_retry.py::test_backend_route_or_version_difference_rejects",
    "tests/test_runtime_java_pinned_provider_retry.py::test_caller_config_alias_and_report_reconstruction_reject",
]


class Results:
    def __init__(self):
        self.collected = 0
        self.passed = 0
        self.skipped = 0
        self.failures = []
        self.suites = {}
        self.nodeids = []

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)
        self.nodeids = [item.nodeid for item in session.items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.failures.append({"nodeid": report.nodeid, "when": "collect",
                                  "outcome": report.outcome, "detail": str(report.longrepr)})

    def pytest_runtest_logreport(self, report):
        suite = self.suites.setdefault(report.nodeid.split("::")[0],
                                      {"passed": 0, "failed": 0, "skipped": 0})
        if report.failed:
            self.failures.append({"nodeid": report.nodeid, "when": report.when,
                                  "outcome": report.outcome, "detail": str(report.longrepr)})
            suite["failed"] += 1
        elif report.when == "call" and report.passed:
            self.passed += 1
            suite["passed"] += 1
        elif report.skipped:
            self.skipped += 1
            suite["skipped"] += 1


def _remove_validation_temp(path):
    resolved_phase, resolved_path = PHASE.resolve(), path.resolve()
    if (resolved_path.parent != resolved_phase
            or not resolved_path.is_relative_to(resolved_phase)
            or not resolved_path.name.startswith("validation_temp_")):
        raise ValueError("retry_validation_temporary_path_outside_owned_directory")
    shutil.rmtree(resolved_path)
    if resolved_path.exists():
        raise ValueError("retry_validation_temporary_path_cleanup_unverified")


mode = sys.argv[1]
started = time.monotonic()
stream = io.StringIO()
active = [True]
real_effect_attempts = []


def audit_denial(event, args):
    if active[0] and (event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
                              "os.spawn", "pty.spawn", "os.startfile", "socket.connect",
                              "socket.bind", "socket.sendto", "socket.sendmsg"}
                      or event.startswith("os.startfile/")):
        real_effect_attempts.append(event)
        raise AssertionError("PINNED.1C retry pure validation denied real effect: " + event)


sys.addaudithook(audit_denial)
# Avoid Windows platform metadata launching an external `ver` process.
if sys.platform == "win32":
    version = sys.getwindowsversion()
    platform._uname_cache = platform.uname_result(
        "Windows", os.environ.get("COMPUTERNAME", ""), str(version.major),
        ".".join(map(str, version[:3])), os.environ.get("PROCESSOR_ARCHITECTURE", ""))

from tests._preflight_runtime1_guard import no_runtime_effects

if mode == "benchmark_check":
    import runpy

    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        with no_runtime_effects(strict=False) as guard:
            sys.argv = ["benchmarks/run_benchmarks.py", "--check"]
            try:
                runpy.run_path(str(ROOT / "benchmarks/run_benchmarks.py"), run_name="__main__")
            except SystemExit as error:
                exit_code = int(error.code or 0)
            else:
                exit_code = 0
    result = {"mode": mode, "exit_code": exit_code, "real_effect_attempts": real_effect_attempts,
              "denied_attempts": guard.denied_attempts,
              "benchmark_arguments": ["benchmarks/run_benchmarks.py", "--check"]}
elif mode == "preservation_check":
    baseline = json.loads((PHASE / "preservation_baseline.json").read_text(encoding="utf-8"))
    changed = []
    missing = []
    for row in baseline["files"]:
        path = ROOT / row["path"]
        if not path.is_file():
            missing.append(row["path"])
            continue
        content = path.read_bytes()
        if len(content) != row["size_bytes"] or sha256(content).hexdigest() != row["sha256"]:
            changed.append(row["path"])
    exit_code = int(bool(changed or missing))
    result = {"mode": mode, "exit_code": exit_code, "checked_file_count": len(baseline["files"]),
              "changed_existing_files": changed, "missing_existing_files": missing,
              "all_existing_bytes_preserved": not changed and not missing,
              "real_effect_attempts": real_effect_attempts, "denied_attempts": []}
elif mode == "in_memory_compile":
    paths = [ROOT / "core/runtime_java_pinned_provider.py",
             ROOT / "scripts/replay_runtime_java_pinned1c.py",
             ROOT / "scripts/replay_runtime_java_pinned1c_retry.py",
             ROOT / "tests/test_runtime_java_pinned_provider.py",
             ROOT / "tests/test_runtime_java_pinned_provider_retry.py",
             PHASE / "check_validation.py", PHASE / "authentication_controls.py", Path(__file__)]
    failures = []
    for path in paths:
        try:
            compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
        except (OSError, SyntaxError, ValueError) as error:
            failures.append({"path": str(path.relative_to(ROOT)), "error": str(error)})
    exit_code = int(bool(failures))
    result = {"mode": mode, "exit_code": exit_code, "compiled_file_count": len(paths) - len(failures),
              "files": [str(path.relative_to(ROOT)) for path in paths], "failures": failures,
              "real_effect_attempts": real_effect_attempts, "denied_attempts": []}
else:
    import pytest

    if mode in {"registry_baseline", "registry_after"}:
        test_files = REGISTRY_TESTS
    elif mode == "frozen_validation":
        test_files = FROZEN_TESTS
    elif mode == "focused_validation":
        test_files = FOCUSED_TESTS
    elif mode == "config_path_validation":
        test_files = CONFIG_PATH_TESTS
    else:
        raise ValueError("Unsupported retry pure validation mode: " + mode)
    temp_root = PHASE / ("validation_temp_" + mode + "_" + uuid.uuid4().hex)
    temp_root.mkdir(exist_ok=False)
    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = str(temp_root)
    args = ["-q", "-p", "no:cacheprovider", "--basetemp=" + str(temp_root / "pytest"), *test_files]
    plugin = Results()
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            with no_runtime_effects(strict=False) as guard:
                exit_code = int(pytest.main(args, plugins=[plugin]))
    finally:
        tempfile.tempdir = previous_tempdir
        _remove_validation_temp(temp_root)
    result = {"mode": mode, "exit_code": exit_code, "collected": plugin.collected,
              "passed": plugin.passed, "skipped": plugin.skipped, "failures": plugin.failures,
              "suites": plugin.suites, "test_nodeids": plugin.nodeids,
              "test_files": test_files, "pytest_arguments": args,
              "real_effect_attempts": real_effect_attempts, "denied_attempts": guard.denied_attempts,
              "registry_projection_plugin_used": False,
              "validation_temporary_directory_removed": not temp_root.exists(),
              "validation_temporary_directory": str(temp_root.relative_to(ROOT))}
    if mode == "registry_after" and (PHASE / "registry_baseline.json").is_file():
        baseline = json.loads((PHASE / "registry_baseline.json").read_text(encoding="utf-8"))
        failure_key = lambda row: (row["nodeid"], row["when"], row["outcome"])
        before = {failure_key(row) for row in baseline["failures"]}
        after = {failure_key(row) for row in result["failures"]}
        result["baseline_comparison"] = {
            "baseline_collected": baseline["collected"], "after_collected": result["collected"],
            "baseline_passed": baseline["passed"], "after_passed": result["passed"],
            "unchanged_failure_ids": sorted(before & after),
            "new_failure_ids": sorted(after - before), "resolved_failure_ids": sorted(before - after),
            "no_new_failures": not (after - before),
        }

active[0] = False
result["elapsed_seconds"] = round(time.monotonic() - started, 3)
result["retry_validation"] = True
result["attempt1_artifacts_modified"] = False
result["scope"] = (
    "Pure host maintenance and fabricated in-memory fixtures only. Audit hook and frozen guard deny "
    "operational processes/network before execution. Owner/control mocks validate contracts; no live "
    "Docker, Java, javac, controller, authorization, lease, executor or Apply executes. Repository reads, "
    "Python validation and new retry-owned temporary/artifact writes are maintenance. Historical registry "
    "projection is deliberately disabled so pre-existing drift remains visible.")
result["successful_operational_effect_counts"] = dict.fromkeys([
    "Docker", "containers", "exports", "Java", "javac", "controller", "network", "shell",
    "host mounts", "source projection", "runtime lease consumption", "reflection lease consumption",
    "BANK", "EXECUTOR.1R", "Apply"], 0)
(PHASE / (mode + ".txt")).write_text(stream.getvalue(), encoding="utf-8")
(PHASE / (mode + ".json")).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
print(json.dumps({key: result[key] for key in ["mode", "exit_code", "collected", "passed", "skipped",
                                             "checked_file_count", "all_existing_bytes_preserved",
                                             "real_effect_attempts", "denied_attempts", "elapsed_seconds"]
                  if key in result}))
sys.exit(exit_code)
