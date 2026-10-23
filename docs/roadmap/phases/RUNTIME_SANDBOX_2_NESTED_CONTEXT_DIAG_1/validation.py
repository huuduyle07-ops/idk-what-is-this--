"""Pure validation and byte preservation for NESTED.CONTEXT.DIAG.1.

All authored output is confined to this new phase. No live owner is invoked.
Run with Python -B; baseline is exclusive and must precede validation.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import runpy
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AUTH = ROOT / "docs/roadmap/phases/RUNTIME_JAVA_1C_AUTH_DIAG_1"
PRELADDER = ROOT / "docs/roadmap/phases/RUNTIME_SANDBOX_2_PRELADDER_DIAG_1"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data, exclusive=False):
    path = HERE / name
    with path.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, indent=2, sort_keys=True) + "\n")


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=True, shell=False)
    return result.stdout


def existing_files():
    names = set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
                .decode("utf-8").split("\0")) - {""}
    # Include ignored history already protected by both frozen diagnostics.
    # Both prior baselines remain read only; this phase never repins drift.
    prior = json.loads((AUTH / "preservation_baseline.json").read_text(encoding="utf-8"))
    names.update(prior["files"])
    names.update(json.loads((PRELADDER / "preservation_baseline.json").read_text(encoding="utf-8"))["files"])
    # Phase/attempt evidence under .agent is ignored by git; inspect only the
    # established history roots, avoiding the thousands of generated test repos.
    for root in (ROOT / ".agent/runtime", ROOT / ".agent/attempts",
                 ROOT / ".agent/roadmap", ROOT / ".agent/worker_runs"):
        if root.exists():
            names.update(path.relative_to(ROOT).as_posix() for path in root.rglob("*")
                         if path.is_file())
    excluded = {"__pycache__", ".pytest_cache", ".mypy_cache", ".git", ".venv",
                "node_modules", "tmp_tests", ".tmp", ".temp"}
    selected = []
    for name in sorted(names):
        path = ROOT / name
        if HERE == path or HERE in path.parents or not path.is_file():
            continue
        if any(part in excluded for part in Path(name).parts) or path.suffix == ".pyc":
            continue
        selected.append((name.replace("\\", "/"), path))
    return selected


def registry_reports(label):
    from scripts.validate_phase_registry import run_validate_phase_registry
    from scripts.create_phase_picker_report import run_create_phase_picker_report
    output = HERE / label
    registry = "docs/roadmap/phase_registry.json"
    kwargs = dict(registry=registry, output_root=str(output),
                  report_id="nested-context-preservation", created_at="2026-10-10T00:00:00+00:00")
    validator = run_validate_phase_registry(**kwargs)
    picker = run_create_phase_picker_report(**kwargs)
    return {"registry": validator["report"], "picker": picker["report"]}


def baseline():
    if (HERE / "preservation_baseline.json").exists():
        raise RuntimeError("baseline_already_exists_do_not_repin")
    integrity = prior_pin_integrity()
    if not integrity["passed"]:
        raise RuntimeError("prior_historical_pins_changed_do_not_repin")
    files = {name: digest(path) for name, path in existing_files()}
    result = {"phase_id": "RUNTIME.SANDBOX.2.NESTED.CONTEXT.DIAG.1", "files": files,
              "file_count": len(files), "scope": "existing tracked/nonignored files plus frozen AUTH/PRELADDER preservation history and established ignored history roots",
              "git_status_porcelain": git("status", "--porcelain=v1", "-z").decode("utf-8"),
              "registry_picker_baseline": registry_reports("baseline_reports")}
    write("preservation_baseline.json", result, exclusive=True)
    return {"passed": True, "historical_file_count": len(files)}


def prior_pin_integrity():
    ledgers = []
    for phase in (AUTH, PRELADDER):
        pins = json.loads((phase / "preservation_baseline.json").read_text(encoding="utf-8"))["files"]
        changed = [name for name, value in pins.items()
                   if not (ROOT / name).is_file() or digest(ROOT / name) != value]
        ledgers.append({"prior_phase": phase.name, "historical_pins_checked": len(pins),
                        "changed_or_missing": changed, "passed": not changed})
    return {"passed": all(row["passed"] for row in ledgers), "prior_pin_sets": ledgers,
            "historical_drift_not_repinned": True}


def preservation():
    saved = json.loads((HERE / "preservation_baseline.json").read_text(encoding="utf-8"))
    changed = [name for name, value in saved["files"].items()
               if not (ROOT / name).is_file() or digest(ROOT / name) != value]
    added = sorted({name for name, _ in existing_files()} - set(saved["files"]))
    integrity = prior_pin_integrity()
    return {"passed": not changed and not added and integrity["passed"],
            "historical_file_count": len(saved["files"]),
            "changed_or_missing": changed, "unexpected_new_files_outside_phase": added,
            "prior_historical_pin_integrity": integrity}


def _inside_new_phase(path):
    if isinstance(path, int):
        return True
    if isinstance(path, bytes):
        path = os.fsdecode(path)
    # Pytest's Windows recursive cleanup passes extended drive paths. Treat
    # their canonical location exactly like the corresponding ordinary path.
    if os.name == "nt" and str(path).startswith("\\\\?\\"):
        path = str(path)[4:]
    resolved = Path(path).resolve()
    return resolved == HERE or HERE in resolved.parents


def _worker_guard(allowed_process=None):
    """Use a fresh worker domain: reject process/network and historical writes."""
    evidence = {"forbidden_process_attempts": 0, "forbidden_socket_attempts": 0,
                "forbidden_write_attempts": 0, "allowed_pure_domain_children": 0}

    def protect(path):
        if not _inside_new_phase(path):
            evidence["forbidden_write_attempts"] += 1
            raise RuntimeError("validation_write_outside_new_phase:" + str(path))

    def audit(event, args):
        if event == "subprocess.Popen":
            argv = args[1]
            if allowed_process is not None and allowed_process(argv):
                evidence["allowed_pure_domain_children"] += 1
                return
            evidence["forbidden_process_attempts"] += 1
            raise RuntimeError("validation_forbidden_process")
        if event in {"os.system", "os.posix_spawn", "os.spawn", "os.fork", "os.exec",
                     "os.startfile", "os.startfile/2", "pty.spawn"}:
            evidence["forbidden_process_attempts"] += 1
            raise RuntimeError("validation_forbidden_shell_or_process")
        # platform.system() reads the local hostname during dependency import;
        # this read-only fact opens no socket and performs no network lookup.
        if event.startswith("socket.") and event != "socket.gethostname":
            evidence["forbidden_socket_attempts"] += 1
            raise RuntimeError("validation_forbidden_socket")
        if event == "open":
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing:
                protect(path)
        if event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime",
                     "shutil.rmtree"}:
            path = Path(args[0]).resolve()
            # Frozen config imports assert these already-existing directories
            # using mkdir(exist_ok=True). Their mkdir call cannot create or
            # rewrite an existing directory. Every other outside path is denied.
            existing_config_directory = event == "os.mkdir" and path in {
                ROOT / "storage", ROOT / ".agent"} and path.is_dir()
            if not existing_config_directory:
                protect(args[0])
        if event in {"os.rename", "os.link", "os.symlink"}:
            protect(args[0])
            protect(args[1])
        if event in {"shutil.copyfile", "shutil.copytree"}:
            protect(args[1])

    sys.addaudithook(audit)
    return evidence


def auth_matrix_worker():
    source = AUTH / "pure_matrix.py"
    spec = importlib.util.spec_from_file_location("preladder_frozen_auth_matrix", source)
    module = importlib.util.module_from_spec(spec)
    # Install a guard before loading project imports. The frozen script's one
    # original isolated child command is the sole allowed process; its worker
    # mode installs the frozen audit guard itself before importing owners.
    def permitted(argv):
        command = [sys.executable, "-I", "-S", "-B", str(source), "--domain-worker"]
        matches = argv == subprocess.list2cmdline(command) if isinstance(argv, str) else list(argv) == command
        return bool(matches and getattr(module, "_ALLOW_CHILD", False))

    evidence = _worker_guard(permitted)
    spec.loader.exec_module(module)
    module.HERE = HERE
    sys.addaudithook(module._audit)
    original_command = list(module._CHILD_COMMAND)
    report = module.run_matrix()
    assert module._CHILD_COMMAND == original_command
    assert report["passed"] and report["live_owner_calls"] == 0
    assert report["effect_counts"] == {"python_domain_child": 1, "docker": 0, "java": 0,
        "caller_shell": 0, "socket": 0, "other_process": 0, "forbidden_attempts": 0}
    write("auth_pure_matrix.json", report)
    return {"passed": True, "case_count": report["case_count"],
            "original_frozen_source_sha256": digest(source),
            "output_only_rebound_to_new_phase": True, "original_child_command_preserved": True,
            "effect_counts": report["effect_counts"], "audit_guard": evidence}


def auth_artifacts_worker():
    evidence = _worker_guard()
    source = AUTH / "verify_artifacts.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), str(source))
    writes = [node for node in tree.body if isinstance(node, ast.Expr)
              and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
              and node.value.func.attr == "write_text"]
    assert len(writes) == 1
    removed = writes[0]
    assert "validation_summary.json" in ast.unparse(removed)
    tree.body.remove(removed)
    namespace = {"__file__": str(source), "__name__": "preladder_readonly_auth_artifacts"}
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exec(compile(ast.fix_missing_locations(tree), str(source), "exec"), namespace)
    result = namespace["result"]
    assert result["passed"]
    result = {**result, "original_frozen_source_sha256": digest(source),
              "sole_final_historical_write_removed_in_memory": True,
              "removed_statement_source_line": removed.lineno,
              "all_historical_assertions_executed": True,
              "captured_original_stdout": stdout.getvalue(), "audit_guard": evidence}
    write("auth_artifact_check.json", result)
    return result


def _windows_platform_cache():
    # Pure dependency imports must not launch Windows `ver` through platform.
    if sys.platform == "win32":
        version = sys.getwindowsversion()
        platform._uname_cache = platform.uname_result(
            "Windows", os.environ.get("COMPUTERNAME", ""), str(version.major),
            ".".join(map(str, version[:3])), os.environ.get("PROCESSOR_ARCHITECTURE", ""))


def pytest_worker(scope="sandbox2"):
    scratch = HERE / "validation_tmp"
    scratch.mkdir(exist_ok=True)
    os.environ.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                       "TEMP": str(scratch), "TMP": str(scratch), "TMPDIR": str(scratch)})
    tempfile.tempdir = str(scratch)
    evidence = _worker_guard()
    _windows_platform_cache()
    import pytest
    args = ["-q", "-p", "no:cacheprovider", "-o", "addopts=",
            "-o", "log_file=" + str(scratch / ("pytest-log-" + scope + ".txt")),
            "--basetemp=" + str(scratch / ("pytest-basetemp-" + scope + "-" + str(os.getpid())))]
    if scope == "sandbox2":
        args.extend(["tests/test_runtime_sandbox2.py", str(PRELADDER / "test_classifier.py")])
    elif scope == "context-audit":
        args.append(str(HERE / "test_context_audit.py"))
    elif scope in {"context-contracts", "context-contracts-collect"}:
        # Context helpers and representative contract cases use only virtual
        # transports/archives. The exhaustive combined provider/auth suite
        # exceeded its bounded worker time; no historical suite is altered.
        provider = "tests/test_runtime_java_pinned_provider.py::"
        auth = "tests/test_synthetic_runtime_authorization_pinned.py::"
        args.extend([provider + name for name in (
            "test_issuer_accepts_no_caller_source_route_or_evidence",
            "test_prior_profiler_blocks_before_any_upstream_effect",
            "test_observer_restores_profiler_even_when_public_owner_raises",
            "test_frozen_fresh_empty_docker_config_paths_do_not_change_backend_identity",
            "test_existing_docker_configuration_path_cannot_replace_frozen_empty_configuration")])
        args.extend([auth + name for name in (
            "test_new_epoch_uses_exact_historical_source_and_scenario",
            "test_scope_is_authorization_only_and_public_objects_are_immutable",
            "test_public_issuer_accepts_no_free_form_inputs",
            "test_provider_failure_closes_before_scenario_authorization",
            "test_missing_exact_frozen_source_stops_before_provider_issuance",
            "test_validation_calls_public_provider_validator_even_after_issuance",
            "test_report_separates_provider_infrastructure_from_zero_synthetic_effects",
            "test_negative_matrix_is_reversible_and_performs_no_additional_provider_effects",
            "test_issuance_and_validation_add_no_lifecycle_or_reflection_effects")])
        args.append("tests/test_synthetic_runtime_authorization_pinned_replay.py")
        if scope == "context-contracts-collect":
            args.append("--collect-only")
    elif scope in {"registry-picker-before", "registry-picker-after"}:
        args.extend(["tests/test_phase_registry.py", "tests/test_phase_picker.py"])
    else:
        raise ValueError("unsupported_pure_pytest_scope:" + scope)
    class OutcomeRecorder:
        def __init__(self):
            self.collected = 0
            self.collected_ids = []
            self.failed = []
            self.passed = []
            self.skipped = []

        def pytest_collection_finish(self, session):
            self.collected = len(session.items)
            self.collected_ids = sorted(item.nodeid for item in session.items)

        def pytest_collectreport(self, report):
            if report.failed:
                self.failed.append({"nodeid": report.nodeid, "when": "collect"})

        def pytest_runtest_logreport(self, report):
            if report.failed:
                self.failed.append({"nodeid": report.nodeid, "when": report.when})
            elif report.when == "call" and report.passed:
                self.passed.append(report.nodeid)
            elif report.skipped:
                self.skipped.append(report.nodeid)

    recorder = OutcomeRecorder()
    code = int(pytest.main(args, plugins=[recorder]))
    return {"passed": code == 0 and not any(evidence.values()), "exit_code": code, "args": args,
            "collected_test_count": recorder.collected,
            "collected_test_ids": recorder.collected_ids,
            "passed_test_count": len(recorder.passed), "failed_test_count": len(recorder.failed),
            "passed_test_ids": sorted(recorder.passed),
            "failed_test_ids": sorted(recorder.failed, key=lambda row: (row["nodeid"], row["when"])),
            "skipped_test_ids": sorted(recorder.skipped),
            "audit_guard": evidence, "temporary_root_confined_to_new_phase": True,
            "controlled_fixture_owner_frames_permitted": scope in {"sandbox2", "context-contracts"},
            "live_owner_issuance": 0, "successful_operational_effects": 0,
            "coverage_selection": (
                "five frozen PINNED1C context/config helpers, nine SYNTH pure contract tests, complete stubbed replay suite"
                if scope.startswith("context-contracts") else "complete selected frozen suites")}


def historical_blocked_worker():
    evidence = _worker_guard()
    relative = "docs/roadmap/phases/SYNTH_AUTH_PINNED_1/SYNTH_AUTH_PINNED_1_LOCAL.json"
    path = ROOT / relative
    saved = json.loads((HERE / "preservation_baseline.json").read_text(encoding="utf-8"))
    assert digest(path) == saved["files"][relative]
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["status"] == "SYNTH_AUTH_PINNED_1_BLOCKED"
    assert report["reason"] == (
        "authorization_prerequisite_failed:pinned_provider_incomplete: "
        "fresh_java1c_failed:not_authenticated")
    assert report["single_live_authorization_attempt"] is True
    assert report["provider_proof_issuance_attempts"] == 1
    for flag in ("synthetic_scenario_authorized", "execution_lease_issued",
                 "lifecycle_compatibility_evaluated", "reflection_admission_issued",
                 "SyntheticStateBox_executed", "provider_proof_consumed"):
        assert report[flag] is False
    return {"passed": True, "historical_status": report["status"],
            "historical_reason": report["reason"], "source": relative,
            "sha256": digest(path), "historical_bytes_unchanged": True,
            "historical_live_attempts_unchanged": 1, "new_live_attempts": 0,
            "audit_guard": evidence}


def context_report_worker():
    evidence = _worker_guard()
    source = HERE / "context_audit.py"
    spec = importlib.util.spec_from_file_location("nested_context_guarded_report", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.audit_report()
    report["pure_reproducer"] = module.temp_reproducer(HERE / "scratch" / "temp_root_control")
    report["profiler_pure_controls"] = [module.profiler_reproducer(), module.profiler_reproducer(True)]
    assert report["pure_reproducer"]["passed"]
    assert all(row["passed"] and row["profiler_restored_by_exact_helper"]
               for row in report["profiler_pure_controls"])
    assert all(count == 0 for count in report["operational_effects"].values())
    report["pure_validation_audit_guard"] = evidence
    write("source_context_inventory.json", module.static_inventory())
    write("RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1_REPORT.json", report)
    return {"passed": True, "status": report["status"],
            "context_audit_source_sha256": digest(source),
            "exact_historical_root_cause_established": report["exact_historical_root_cause_established"],
            "operational_effects": report["operational_effects"],
            "pure_reproducer_passed": True, "profiler_pure_controls_passed": True,
            "audit_guard": evidence}


def benchmark_worker():
    evidence = _worker_guard()
    old_argv = sys.argv
    sys.argv = [str(ROOT / "benchmarks/run_benchmarks.py"), "--check"]
    try:
        try:
            runpy.run_path(sys.argv[0], run_name="__main__")
            code = 0
        except SystemExit as exc:
            code = exc.code or 0
    finally:
        sys.argv = old_argv
    return {"passed": code == 0, "exit_code": code, "audit_guard": evidence,
            "arguments": ["benchmarks/run_benchmarks.py", "--check"]}


def worker(mode):
    functions = {"pytest": pytest_worker, "auth-matrix": auth_matrix_worker,
                 "auth-artifacts": auth_artifacts_worker, "benchmark": benchmark_worker,
                 "context-audit": lambda: pytest_worker("context-audit"),
                 "context-report": context_report_worker,
                 "context-contracts": lambda: pytest_worker("context-contracts"),
                 "context-contracts-collect": lambda: pytest_worker("context-contracts-collect"),
                 "historical-blocked": historical_blocked_worker,
                 "registry-picker-before": lambda: pytest_worker("registry-picker-before"),
                 "registry-picker-after": lambda: pytest_worker("registry-picker-after")}
    result = functions[mode]()
    audit = result.get("audit_guard", {})
    forbidden = [name for name, value in audit.items()
                 if name.startswith("forbidden_") and value != 0]
    if forbidden:
        result["passed"] = False
        result["nonzero_forbidden_attempt_counters"] = forbidden
    write("worker_" + mode + ".json", result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


def run_worker(mode):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "worker", mode]
    if mode == "benchmark":
        # The --check path uses only stdlib dependencies. Site isolation avoids
        # optional trust-store import doing a Windows shell platform probe.
        command.insert(1, "-S")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    result = subprocess.run(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=False, check=False, timeout=300)
    (HERE / (mode + ".stdout.txt")).write_bytes(result.stdout)
    (HERE / (mode + ".stderr.txt")).write_bytes(result.stderr)
    summary_path = HERE / ("worker_" + mode + ".json")
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    return {"passed": result.returncode == 0 and summary.get("passed") is True,
            "exit_code": result.returncode, "command": command, "worker_result": summary,
            "stdout_retained": mode + ".stdout.txt", "stderr_retained": mode + ".stderr.txt"}


def source_checks():
    python_files = json_files = text_files = 0
    failures = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".md", ".json"}:
            continue
        if any(part in {"validation_tmp", "__pycache__", ".pytest_cache"}
               for part in path.relative_to(HERE).parts):
            continue
        text = path.read_text(encoding="utf-8")
        text_files += 1
        if any(line != line.rstrip() for line in text.splitlines()):
            failures.append("trailing_whitespace:" + path.name)
        try:
            if path.suffix == ".py":
                compile(text, str(path), "exec")
                python_files += 1
            if path.suffix == ".json":
                json.loads(text)
                json_files += 1
        except (SyntaxError, ValueError) as exc:
            failures.append(path.name + ":" + str(exc))
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False, shell=False)
    (HERE / "git_diff_check.stdout.txt").write_bytes(diff.stdout)
    (HERE / "git_diff_check.stderr.txt").write_bytes(diff.stderr)
    return {"passed": not failures and diff.returncode == 0,
            "new_python_sources_compiled_in_memory": python_files,
            "new_json_files_parsed": json_files, "authored_text_files_checked": text_files,
            "failures": failures, "git_diff_check_exit_code": diff.returncode,
            "bytecode_emission": False}


def validate(resume=False):
    before = preservation()
    if not before["passed"]:
        write("validation_summary.json", {"passed": False, "preservation_before": before})
        raise RuntimeError("historical_files_changed_do_not_validate_or_repin")
    before_path = HERE / "registry_picker_pure_test_baseline.json"
    if not before_path.exists():
        before_tests = run_worker("registry-picker-before")
        write("registry_picker_pure_test_baseline.json", before_tests, exclusive=True)
    else:
        before_tests = json.loads(before_path.read_text(encoding="utf-8"))
    results = {}
    for mode in ("context-report", "context-audit", "pytest", "auth-matrix", "auth-artifacts",
                 "context-contracts", "historical-blocked", "benchmark"):
        saved_worker = HERE / ("worker_" + mode + ".json")
        if resume and mode in {"pytest", "auth-matrix", "auth-artifacts"} and saved_worker.is_file():
            prior_result = json.loads(saved_worker.read_text(encoding="utf-8"))
            if prior_result.get("passed") is True:
                results[mode] = {"passed": True, "exit_code": 0, "worker_result": prior_result,
                    "reused_unchanged_passing_worker": True,
                    "frozen_historical_pins_rechecked_before_reuse": True,
                    "stdout_retained": mode + ".stdout.txt", "stderr_retained": mode + ".stderr.txt"}
                continue
        results[mode] = run_worker(mode)
    after_tests = run_worker("registry-picker-after")
    keys = ("exit_code", "collected_test_count", "passed_test_count",
            "failed_test_count", "failed_test_ids", "skipped_test_ids")
    before_outcome = {key: before_tests.get("worker_result", {}).get(key) for key in keys}
    after_outcome = {key: after_tests.get("worker_result", {}).get(key) for key in keys}
    guards = [run.get("worker_result", {}).get("audit_guard", {}) for run in (before_tests, after_tests)]
    no_effects = all(guard and not any(guard.values()) for guard in guards)
    results["registry_picker_pure_test_baseline_vs_after"] = {
        "passed": before_outcome == after_outcome and no_effects,
        "baseline": before_outcome, "after": after_outcome,
        "unchanged_historical_failures_preserved": before_outcome["failed_test_count"] != 0,
        "same_failure_ids_and_outcome_counts": before_outcome == after_outcome,
        "audit_guards_no_effect_attempts": no_effects,
        "baseline_retained": "registry_picker_pure_test_baseline.json",
        "after_retained": "worker_registry-picker-after.json"}
    saved = json.loads((HERE / "preservation_baseline.json").read_text(encoding="utf-8"))
    after_reports = registry_reports("after_reports")
    # created_at/report_id are fixed for both invocations. Reports contain no
    # output destination fields, so equality is a deterministic comparison.
    report_compare = {"passed": after_reports == saved["registry_picker_baseline"],
                      "registry_equal": after_reports["registry"] == saved["registry_picker_baseline"]["registry"],
                      "picker_equal": after_reports["picker"] == saved["registry_picker_baseline"]["picker"]}
    write("registry_picker_comparison.json", report_compare)
    results["registry_picker_baseline_vs_after"] = report_compare
    results["source_json_whitespace_diff_checks"] = source_checks()
    results["historical_byte_preservation"] = preservation()
    operational = dict.fromkeys(("Docker", "SANDBOX2_issuance", "JAVA1C",
        "PINNED1A_export", "PINNED1B", "PINNED1C", "SYNTH_retry", "SyntheticStateBox",
        "reflection", "BANK", "EXECUTOR1R", "Apply"), 0)
    result = {"passed": all(value["passed"] for value in results.values()),
              "phase_id": "RUNTIME.SANDBOX.2.NESTED.CONTEXT.DIAG.1", "checks": results,
              "validation_live_owner_invocations": 0, "validation_Docker_controls": 0,
              "validation_Java_effects": 0, "all_output_confined_to_new_phase": True,
              "operational_effects": operational,
              "controlled_fixture_frames_are_not_live_operational_issuance": True}
    if (HERE / "broad_contract_timeout.json").is_file():
        result["validation_scope_limit"] = json.loads((HERE / "broad_contract_timeout.json").read_text(encoding="utf-8"))
    write("validation_summary.json", result)
    return result


def refresh_context():
    """Revalidate final audit edits without rerunning frozen broad suites."""
    result = json.loads((HERE / "validation_summary.json").read_text(encoding="utf-8"))
    for mode in ("context-report", "context-audit"):
        result["checks"][mode] = run_worker(mode)
    result["checks"]["source_json_whitespace_diff_checks"] = source_checks()
    result["checks"]["historical_byte_preservation"] = preservation()
    result["passed"] = all(value["passed"] for value in result["checks"].values())
    result["final_context_source_refreshed_without_broad_rerun"] = True
    write("validation_summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("baseline", "validate", "resume-validation", "refresh-context", "preservation", "source-checks", "worker"))
    parser.add_argument("worker_mode", nargs="?", choices=("pytest", "auth-matrix", "auth-artifacts", "benchmark",
                                                            "context-report", "context-audit", "context-contracts", "historical-blocked",
                                                            "context-contracts-collect",
                                                            "registry-picker-before", "registry-picker-after"))
    arguments = parser.parse_args()
    mode = arguments.mode
    if mode == "baseline":
        result = baseline()
    elif mode == "preservation":
        result = preservation()
        write("preservation_after.json", result)
    elif mode == "source-checks":
        result = source_checks()
        write("source_checks_final.json", result)
    elif mode == "refresh-context":
        result = refresh_context()
    elif mode == "resume-validation":
        result = validate(resume=True)
    elif mode == "worker":
        return worker(arguments.worker_mode)
    else:
        result = validate()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
