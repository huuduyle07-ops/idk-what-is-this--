"""Reproducible zero-operational-issuance implementation validation.

Run with python -B, --mode registry_baseline|focused_baseline|focused|registry_after|benchmark.
Pytest writes only in a unique external temporary directory. Audit hooks reject
process/network and repository writes; profiling rejects entry into core issuer,
consumer, executor and live verification functions. Artifacts are written after
these guards close, as explicit audit documentation rather than runtime writes.
Implementation mode permits only isolated inert new-owner fixture transitions.
Production core issuers/transitions and all upstream/provider issuers stay denied.
The frozen pinned input-signature test reversibly isolates empty owner/provider
registries and patches virtual transports; it issues no handle or provider proof.
"""
from __future__ import annotations

import argparse
import contextlib
import io
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import runpy
import socket
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
CORE_PREFIX = str(ROOT / "core") + os.sep
# Python's Windows platform fallback runs shell `ver`; populate from OS APIs.
if sys.platform == "win32":
    version = sys.getwindowsversion()
    platform._uname_cache = platform.uname_result("Windows", os.environ.get("COMPUTERNAME", ""),
        str(version.major), ".".join(map(str, version[:3])), os.environ.get("PROCESSOR_ARCHITECTURE", ""))

FOCUSED = [
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_contract.py",
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py",
    "tests/test_synthetic_runtime_authorization.py::test_supported_scenario_has_exact_non_bank_contract",
    "tests/test_synthetic_runtime_authorization.py::test_contract_constructor_has_no_executable_text_extension",
    "tests/test_synthetic_runtime_authorization.py::test_contract_and_nested_metadata_are_immutable",
    "tests/test_synthetic_runtime_authorization_pinned.py::test_public_issuer_accepts_no_free_form_inputs",
    "tests/test_synthetic_runtime_authorization_lifecycle.py::test_future_consumption_boundary_is_explicit_and_has_no_runtime_implementation",
    "tests/test_patch_candidate_behavior_executor1r.py::test_exact_fixture_is_independent_and_bound_to_its_field_definition",
    "tests/test_synthetic_read_only_reflection.py::test_exact_synthetic_definition_bytes_and_hash_are_bound",
    "tests/test_synthetic_reflection_execution_admission.py::test_uninitialized_foreign_and_report_only_values_never_authenticate",
    "tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py::test_java_contract_audit_checks_exact_schema_and_policy_without_inventing_alias",
    "tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py::test_renaming_continuation_module_does_not_change_its_frozen_contract",
]


@contextlib.contextmanager
def audit_guard():
    active = [True]
    evidence = {"process_attempts": 0, "network_attempts": 0,
        "repository_write_attempts": 0, "owner_issuance_or_consumption_attempts": 0,
        "live_verification_or_execution_attempts": 0}
    blocked = []
    inert_calls = {"issue": 0, "consume": 0, "invalidate": 0}

    def reject(kind, detail):
        evidence[kind] += 1
        blocked.append(str(detail))
        raise AssertionError("Pure pinned contract denied: " + str(detail))

    def inside_root(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return False
        try:
            return Path(os.fsdecode(path)).resolve().is_relative_to(ROOT)
        except (OSError, ValueError):
            return False

    def hook(event, args):
        if not active[0]:
            return
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile"}:
            reject("process_attempts", event)
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            reject("network_attempts", event)
        if event == "open":
            path, mode, flags = args
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and inside_root(path):
                reject("repository_write_attempts", "open:" + str(path))
        if event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename"}:
            if any(inside_root(path) for path in args[:2]):
                reject("repository_write_attempts", event + ":" + str(args))

    def profile(frame, event, arg):
        if not active[0] or event != "call":
            return
        code = frame.f_code
        path = code.co_filename
        if path.startswith("<inert:pinned-lifecycle-tests:"):
            name = code.co_name
            operational = name in {"_transition", "_issue", "_issue_upstream"} or name.startswith(("issue_", "consume_", "invalidate_"))
            if operational:
                isolated = (frame.f_globals.get("__name__") == "_test_pinned_lifecycle_owner"
                    and getattr(sys.modules.get("_test_pinned_lifecycle_owner"), "__dict__", None) is frame.f_globals
                    and getattr(frame.f_globals.get("authorization_owner"), "__name__", None) == "_test_pinned_lifecycle_upstream"
                    and frame.f_globals.get("authorization_owner") is sys.modules.get("_test_pinned_lifecycle_upstream"))
                if isolated and path == "<inert:pinned-lifecycle-tests:owner>" and (name in {"_transition", "_issue"} or name in {
                    "issue_pinned_synthetic_runtime_execution_lease", "consume_pinned_synthetic_runtime_execution_lease", "invalidate_pinned_synthetic_runtime_execution_lease"}):
                    if name.startswith("issue_"):
                        inert_calls["issue"] += 1
                    elif name.startswith("consume_"):
                        inert_calls["consume"] += 1
                    elif name.startswith("invalidate_"):
                        inert_calls["invalidate"] += 1
                else:
                    reject("owner_issuance_or_consumption_attempts", path + ":" + name)
            if name == "verify" or name.startswith(("execute_", "run_")):
                reject("live_verification_or_execution_attempts", path + ":" + name)
            return
        if not path.startswith(CORE_PREFIX):
            return
        name = code.co_name
        if name in {"_transition", "_issue", "_issue_upstream"} or name.startswith(("issue_", "consume_", "invalidate_")):
            reject("owner_issuance_or_consumption_attempts", str(path) + ":" + name)
        if name == "verify" or name.startswith(("execute_", "run_")):
            reject("live_verification_or_execution_attempts", str(path) + ":" + name)

    sys.addaudithook(hook)
    previous = sys.getprofile()
    previous_threads = threading.getprofile()
    sys.setprofile(profile)
    threading.setprofile(profile)
    try:
        yield evidence, blocked, inert_calls
    finally:
        active[0] = False
        sys.setprofile(previous)
        threading.setprofile(previous_threads)


class Results:
    def __init__(self):
        self.collected = 0
        self.passed = []
        self.failed = []
        self.skipped = []

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.failed.append({"nodeid": report.nodeid, "when": report.when})
        elif report.skipped:
            self.skipped.append(report.nodeid)
        elif report.when == "call" and report.passed:
            self.passed.append(report.nodeid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("registry_baseline", "focused_baseline", "focused", "implementation", "registry_after", "benchmark"), required=True)
    parser.add_argument("--scratch-root", required=True, help="Writable external validation directory")
    args = parser.parse_args()
    if args.mode == "registry_baseline" and (OUTPUT / "registry_baseline.json").exists():
        raise AssertionError("Original registry baseline must never be overwritten")
    os.chdir(ROOT)
    scratch = Path(args.scratch_root).resolve()
    assert not scratch.is_relative_to(ROOT), "validation scratch must be external"
    temporary = tempfile.mkdtemp(prefix="cattus-pinned-1a-", dir=scratch)
    os.environ.update(TEMP=temporary, TMP=temporary, TMPDIR=temporary)
    tempfile.tempdir = temporary
    log = io.StringIO()
    run_sources = [ROOT / "core/synthetic_runtime_authorization_pinned_lifecycle.py",
        ROOT / "tests/test_synthetic_runtime_authorization_pinned_lifecycle.py", Path(__file__).resolve()]
    result = {"mode": args.mode, "external_pytest_directory": temporary,
        "run_source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in run_sources if path.is_file()},
        "full_frozen_suites_run": False, "production_validators_patched": False,
        "live_registry_fixtures_seeded": False,
        "test_local_isolated_owner_fixture_possible": args.mode == "implementation",
        "historical_owners_modified": False,
        "operational_provider_proofs_or_registered_handles_constructed": False,
        "bytecode_writes_disabled": sys.dont_write_bytecode,
        "frozen_pinned_test_fixture_isolates_empty_registries": args.mode in {"focused_baseline", "focused"},
        "frozen_pinned_test_fixture_patches_virtual_transports": args.mode in {"focused_baseline", "focused"},
        "frozen_pinned_test_fixture_replaces_unused_provider_entrypoints": args.mode in {"focused_baseline", "focused"}}
    try:
        # urllib3's IPv6 import probe binds a socket; this audit has no networking.
        # Disable only that dependency availability probe; no owner is changed.
        with patch.object(socket, "has_ipv6", False), audit_guard() as (evidence, blocked, inert_calls), contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            if args.mode == "benchmark":
                sys.argv = [str(ROOT / "benchmarks/run_benchmarks.py"), "--check"]
                try:
                    runpy.run_path(sys.argv[0], run_name="__main__")
                    code = 0
                except SystemExit as error:
                    code = error.code
                result["exit_code"] = code
            else:
                if args.mode in {"focused_baseline", "focused", "implementation"}:
                    original_mkdir = Path.mkdir

                    def bootstrap_mkdir(path, *values, **options):
                        # Existing config import requests these two existing
                        # directories with exist_ok=True; perform no OS write.
                        if options.get("exist_ok") and path in (ROOT / "storage", ROOT / ".agent"):
                            assert path.is_dir(), "pre-existing bootstrap directory required"
                            return None
                        return original_mkdir(path, *values, **options)

                    with patch.object(Path, "mkdir", bootstrap_mkdir):
                        import config
                    result["existing_config_directory_mkdir_elided"] = ["storage", ".agent"]
                import pytest
                plugin = Results()
                nodes = ["tests/test_synthetic_runtime_authorization_pinned_lifecycle.py"] if args.mode == "implementation" else FOCUSED if args.mode in {"focused_baseline", "focused"} else ["tests/test_phase_registry.py", "tests/test_phase_picker.py"]
                deselection = ["--deselect=tests/test_synthetic_runtime_authorization_lifecycle_pinned_contract.py::test_contract_is_additive_and_has_no_owner_implementation_or_registry_entry"] if args.mode == "focused" else []
                result["excluded_absence_only_historical_snapshot_test"] = args.mode == "focused"
                result["exclusion_reason"] = "Frozen contract-phase snapshot asserted the additive owner file did not exist before implementation. Baseline ran the full safe selection. After implementation excludes only that phase-stage assertion; frozen test bytes and all semantic assertions remain unchanged." if args.mode == "focused" else None
                code = pytest.main([*nodes, *deselection, "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                    "-o", "log_file=" + str(Path(temporary) / "pytest.log"),
                    "--basetemp=" + str(Path(temporary) / "pytest")], plugins=[plugin])
                result.update(exit_code=int(code), collected=plugin.collected,
                    passed_count=len(plugin.passed), failed=sorted(plugin.failed, key=lambda row: (row["nodeid"], row["when"])),
                    passed_nodes=plugin.passed, skipped=plugin.skipped, selected_nodes=nodes)
                if args.mode.startswith("registry"):
                    from core.phase_registry import load_phase_registry, summarize_phase_registry
                    from core.phase_picker import pick_phase_candidates
                    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
                    result["registry_summary"] = summarize_phase_registry(registry, report_id="pinned-lifecycle-1a", created_at="2026-10-13")
                    result["picker"] = pick_phase_candidates(registry)
        result["audit_guard"] = evidence
        result["inert_new_owner_calls"] = inert_calls
        result["blocked_actions"] = blocked
    except Exception as error:
        import traceback
        traceback.print_exc(file=log)
        result.update(exit_code=2, error=type(error).__name__ + ": " + str(error))
        result["audit_guard"] = evidence
        result["inert_new_owner_calls"] = inert_calls
        result["blocked_actions"] = blocked
    result["all_operational_effects_zero"] = not any(result["audit_guard"].values()) and not result["blocked_actions"]
    if not result["all_operational_effects_zero"]:
        result["exit_code"] = result.get("exit_code") or 3
    (OUTPUT / (args.mode + ".txt")).write_text(log.getvalue(), encoding="utf-8")
    (OUTPUT / (args.mode + ".json")).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {
        "registry_summary", "picker", "selected_nodes", "passed_nodes"}}, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
