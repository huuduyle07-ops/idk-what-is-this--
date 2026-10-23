"""Zero-capability compatibility audit; never execute a frozen proof or issuer.

Run with python -B --mode baseline|registry_baseline|frozen|focused|
registry_after|benchmark|finalize. Validation scratch is external to the repo.
Audit artifacts are written only after the operational-effect guard closes.
"""
from __future__ import annotations

import argparse
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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
NEW_TEST = "tests/test_synthetic_reflection_lifecycle_pinned_compat.py"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

FROZEN = [
    "tests/test_synthetic_runtime_authorization_pinned_lifecycle.py::test_owner_has_no_provider_issuer_private_upstream_registry_or_old_signing_bridge",
    "tests/test_synthetic_runtime_authorization_lifecycle.py::test_future_consumption_boundary_is_explicit_and_has_no_runtime_implementation",
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py::test_exact_scenario_equality_does_not_equal_authorization_epoch",
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py::test_lifecycle_calls_exact_old_public_validator_and_old_owner_projections",
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py::test_each_record_consumer_reauthenticates_under_the_owner_lock",
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py::test_hmac_algorithm_equality_preserves_separate_owner_domains",
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py::test_state_machine_tombstones_and_terminal_commit_have_no_provider_logic",
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py::test_reflection_keeps_frozen_authentication_and_runtime_state_contracts",
    "tests/test_synthetic_runtime_authorization_lifecycle_pinned_compat.py::test_frozen_reflection_tests_require_issuance_and_are_not_zero_issuance_fixtures",
    "tests/test_synthetic_runtime_authorization.py::test_supported_scenario_has_exact_non_bank_contract",
    "tests/test_synthetic_runtime_authorization.py::test_contract_constructor_has_no_executable_text_extension",
    "tests/test_synthetic_runtime_authorization.py::test_contract_and_nested_metadata_are_immutable",
    "tests/test_synthetic_read_only_reflection.py::test_exact_synthetic_definition_bytes_and_hash_are_bound",
    "tests/test_synthetic_read_only_reflection.py::test_definition_rejects_different_declarations_bytes_and_types",
    "tests/test_synthetic_read_only_reflection.py::test_observation_rejects_coercion_bool_subclasses_and_non_java_int_range",
    "tests/test_synthetic_read_only_reflection.py::test_observation_metadata_and_live_result_types_are_validated",
    "tests/test_synthetic_read_only_reflection.py::test_observation_rejects_equivalent_foreign_types",
    "tests/test_synthetic_read_only_reflection.py::test_observation_remains_data_and_json_cannot_be_used_as_typed_measurement",
    "tests/test_synthetic_read_only_reflection.py::test_observation_subclasses_and_wrappers_are_not_the_exact_typed_result",
    "tests/test_synthetic_read_only_reflection.py::test_uninitialized_exact_observation_and_missing_slots_fail_closed",
    "tests/test_synthetic_reflection_execution_admission.py::test_uninitialized_foreign_and_report_only_values_never_authenticate",
    "tests/test_patch_candidate_behavior_executor1r.py::test_exact_fixture_is_independent_and_bound_to_its_field_definition",
    "tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py::test_java_contract_audit_checks_exact_schema_and_policy_without_inventing_alias",
    "tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py::test_renaming_continuation_module_does_not_change_its_frozen_contract",
]


def write_json(name, data):
    (OUTPUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def historical_files():
    """All existing workspace bytes, including ignored runtime artifacts."""
    for folder, dirs, names in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in {
            ".git", "__pycache__", "node_modules", ".venv", "venv"}]
        parent = Path(folder)
        if parent == OUTPUT:
            dirs[:] = []
            continue
        for name in names:
            path = parent / name
            if path.relative_to(ROOT).as_posix() != NEW_TEST and path.is_file():
                yield path


def snapshot():
    return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in historical_files()}


@contextlib.contextmanager
def operational_guard():
    active = [True]
    evidence = {"process_attempts": 0, "network_attempts": 0,
        "repository_write_attempts": 0, "capability_or_transition_attempts": 0,
        "execution_or_verification_attempts": 0}
    blocked = []

    def reject(kind, detail):
        evidence[kind] += 1
        blocked.append(detail)
        raise AssertionError("Pure reflection audit denied: " + detail)

    def inside_root(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return False
        try:
            return Path(os.fsdecode(path)).resolve().is_relative_to(ROOT)
        except (OSError, ValueError):
            return False

    def audit(event, args):
        if not active[0]:
            return
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile"}:
            reject("process_attempts", event)
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            reject("network_attempts", event)
        if event == "open":
            path, mode, flags = args
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND) and inside_root(path):
                reject("repository_write_attempts", "open:" + str(path))
        if event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename"} and any(inside_root(path) for path in args[:2]):
            reject("repository_write_attempts", event + ":" + str(args))

    def profile(frame, event, arg):
        if not active[0] or event != "call":
            return
        code = frame.f_code
        if not (code.co_filename.startswith(str(ROOT / "core") + os.sep)
                or code.co_filename.startswith("<inert:pinned-lifecycle-tests:")):
            return
        name = code.co_name
        if name in {"_issue", "_issue_upstream", "_transition", "executor1r_before_request", "executor1r_after_request"} or name.startswith(("issue_", "consume_", "invalidate_")):
            reject("capability_or_transition_attempts", code.co_filename + ":" + name)
        if name == "verify" or name.startswith(("execute_", "run_")):
            reject("execution_or_verification_attempts", code.co_filename + ":" + name)

    sys.addaudithook(audit)
    previous = sys.getprofile()
    previous_threads = threading.getprofile()
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


def validate(mode, scratch):
    if mode == "registry_baseline" and (OUTPUT / "registry_baseline.json").exists():
        raise AssertionError("Original baseline cannot be overwritten")
    temporary = tempfile.mkdtemp(prefix="cattus-reflect-pinned-audit-", dir=scratch)
    os.environ.update(TEMP=temporary, TMP=temporary, TMPDIR=temporary)
    tempfile.tempdir = temporary
    # Windows platform's fallback shells out to `ver`; use OS API values.
    if sys.platform == "win32":
        version = sys.getwindowsversion()
        platform._uname_cache = platform.uname_result("Windows", os.environ.get("COMPUTERNAME", ""),
            str(version.major), ".".join(map(str, version[:3])), os.environ.get("PROCESSOR_ARCHITECTURE", ""))
    log = io.StringIO()
    result = {"mode": mode, "external_scratch": temporary,
        "bytecode_writes_disabled": True, "production_registries_seeded": False,
        "production_validators_patched": False, "full_issuance_dependent_suites_run": False}
    result["validator_source_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    if mode == "focused":
        result["focused_test_sha256"] = sha256((ROOT / NEW_TEST).read_bytes()).hexdigest()
    evidence, blocked = {}, []
    try:
        # Elide config's no-op mkdir requests for two already existing directories.
        original_mkdir = Path.mkdir

        def bootstrap_mkdir(path, *args, **kwargs):
            if kwargs.get("exist_ok") and path in (ROOT / "storage", ROOT / ".agent"):
                assert path.is_dir()
                return None
            return original_mkdir(path, *args, **kwargs)

        # Disable urllib3's import-time IPv6 socket-bind availability probe.
        with patch.object(socket, "has_ipv6", False), operational_guard() as (evidence, blocked), contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            with patch.object(Path, "mkdir", bootstrap_mkdir):
                import config
            if mode == "benchmark":
                sys.argv = [str(ROOT / "benchmarks/run_benchmarks.py"), "--check"]
                try:
                    runpy.run_path(sys.argv[0], run_name="__main__")
                    result["exit_code"] = 0
                except SystemExit as error:
                    result["exit_code"] = error.code
            else:
                import pytest
                plugin = Results()
                nodes = FROZEN if mode == "frozen" else [NEW_TEST] if mode == "focused" else [
                    "tests/test_phase_registry.py", "tests/test_phase_picker.py"]
                result["selected_nodes"] = nodes
                result["exit_code"] = int(pytest.main([*nodes, "-q", "-p", "no:cacheprovider",
                    "-o", "addopts=", "-o", "log_file=" + str(Path(temporary) / "pytest.log"),
                    "--basetemp=" + str(Path(temporary) / "pytest")], plugins=[plugin]))
                result.update(collected=plugin.collected, passed_count=len(plugin.passed),
                    passed_nodes=plugin.passed, failed=sorted(plugin.failed, key=lambda row: (row["nodeid"], row["when"])),
                    skipped=plugin.skipped)
                if mode.startswith("registry"):
                    from core.phase_registry import load_phase_registry, summarize_phase_registry
                    from core.phase_picker import pick_phase_candidates
                    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
                    result["registry_summary"] = summarize_phase_registry(registry,
                        report_id="reflection-pinned-compat-audit", created_at="2026-10-13")
                    result["picker"] = pick_phase_candidates(registry)
    except Exception as error:
        import traceback
        traceback.print_exc(file=log)
        result.update(exit_code=2, error=type(error).__name__ + ": " + str(error))
    result.update(audit_guard=evidence, blocked_actions=blocked,
        all_operational_effects_zero=not any(evidence.values()) and not blocked)
    if not result["all_operational_effects_zero"]:
        result["exit_code"] = result.get("exit_code") or 3
    (OUTPUT / (mode + ".txt")).write_text(log.getvalue(), encoding="utf-8")
    write_json(mode + ".json", result)
    print(json.dumps({key: value for key, value in result.items() if key not in {
        "picker", "registry_summary", "passed_nodes", "selected_nodes"}}, indent=2))
    return result["exit_code"]


def finalize():
    before = json.loads((OUTPUT / "preservation_baseline.json").read_text(encoding="utf-8"))["sha256"]
    after = snapshot()
    preservation = {"baseline_file_count": len(before),
        "changed": sorted(name for name in before.keys() & after.keys() if before[name] != after[name]),
        "missing": sorted(before.keys() - after.keys()), "unexpected_additions": sorted(after.keys() - before.keys())}
    preservation["historical_bytes_preserved"] = not any(preservation[key] for key in ("changed", "missing", "unexpected_additions"))
    write_json("preservation_check.json", preservation)
    registry = [json.loads((OUTPUT / (mode + ".json")).read_text(encoding="utf-8"))
        for mode in ("registry_baseline", "registry_after")]
    comparison = {"unchanged": all(registry[0][key] == registry[1][key]
        for key in ("failed", "passed_nodes", "registry_summary", "picker", "collected")),
        "baseline_passed": registry[0]["passed_count"], "after_passed": registry[1]["passed_count"],
        "baseline_failures": registry[0]["failed"], "after_failures": registry[1]["failed"]}
    write_json("registry_comparison.json", comparison)
    paths = list(OUTPUT.rglob("*")) + [ROOT / NEW_TEST]
    compile_errors, json_errors, whitespace_errors = [], [], []
    for path in paths:
        if not path.is_file() or path.suffix not in {".py", ".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(ROOT).as_posix()
        if path.suffix == ".py":
            try:
                compile(text, str(path), "exec")
            except SyntaxError as error:
                compile_errors.append({"file": name, "error": str(error)})
        if path.suffix == ".json":
            try:
                json.loads(text)
            except ValueError as error:
                json_errors.append({"file": name, "error": str(error)})
        for line, value in enumerate(text.splitlines(), 1):
            if value.rstrip() != value:
                whitespace_errors.append({"file": name, "line": line})
    # Compile frozen audited owners in memory too; no source execution or .pyc.
    for path in (ROOT / "core").glob("synthetic*.py"):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as error:
            compile_errors.append({"file": path.relative_to(ROOT).as_posix(), "error": str(error)})
    static = {"in_memory_compile_errors": compile_errors, "json_errors": json_errors,
        "whitespace_errors": whitespace_errors, "bytecode_written": False,
        "passed": not (compile_errors or json_errors or whitespace_errors)}
    write_json("static_validation.json", static)
    summary = {"historical_preservation": preservation, "registry_picker": comparison,
        "static_validation": static, "full_suite_claimed": False,
        "issuance_dependent_tests_excluded": True}
    summary["git_diff_check"] = json.loads((OUTPUT / "git_diff_check.json").read_text(encoding="utf-8"))
    for mode in ("frozen", "focused", "benchmark"):
        data = json.loads((OUTPUT / (mode + ".json")).read_text(encoding="utf-8"))
        summary[mode] = {key: data[key] for key in ("exit_code", "audit_guard", "all_operational_effects_zero")}
        if mode != "benchmark":
            summary[mode].update(passed=data["passed_count"], failed=data["failed"], collected=data["collected"])
    initial = json.loads((OUTPUT / "frozen_initial.json").read_text(encoding="utf-8"))
    summary["frozen_initial_selection"] = {"passed": initial["passed_count"],
        "failed": initial["failed"], "audit_guard": initial["audit_guard"],
        "reason_final_selection_narrowed": "Avoid legacy unregistered old negative-data construction; final selection uses source-only old compatibility nodes."}
    summary["all_operational_effects_zero"] = all(json.loads((OUTPUT / (mode + ".json")).read_text(encoding="utf-8"))["all_operational_effects_zero"]
        for mode in ("registry_baseline", "registry_after", "frozen_initial", "frozen", "focused", "benchmark"))
    write_json("validation_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if preservation["historical_bytes_preserved"] and comparison["unchanged"] and static["passed"] and summary["all_operational_effects_zero"] and summary["git_diff_check"]["exit_code"] == 0 and all(summary[mode]["exit_code"] == 0 for mode in ("frozen", "focused", "benchmark")) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "registry_baseline", "frozen", "focused", "registry_after", "benchmark", "finalize"), required=True)
    parser.add_argument("--scratch-root", required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    scratch = Path(args.scratch_root).resolve()
    assert scratch.is_dir() and not scratch.is_relative_to(ROOT)
    if args.mode == "baseline":
        assert not (OUTPUT / "preservation_baseline.json").exists()
        files = snapshot()
        write_json("preservation_baseline.json", {"sha256": files, "file_count": len(files)})
        print(json.dumps({"baseline_file_count": len(files)}))
        return 0
    if args.mode == "finalize":
        return finalize()
    return validate(args.mode, scratch)


if __name__ == "__main__":
    raise SystemExit(main())
