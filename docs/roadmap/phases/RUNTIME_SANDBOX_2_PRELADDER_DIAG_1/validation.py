"""Pure validation and byte preservation for PRELADDER.DIAG.1.

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
import runpy
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AUTH = ROOT / "docs/roadmap/phases/RUNTIME_JAVA_1C_AUTH_DIAG_1"
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
    # Include the exact ignored history already protected by the frozen auth
    # diagnostic. Its list is read only; no prior baseline is rewritten.
    prior = json.loads((AUTH / "preservation_baseline.json").read_text(encoding="utf-8"))
    names.update(prior["files"])
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
                  report_id="preladder-preservation", created_at="2026-10-10T00:00:00+00:00")
    validator = run_validate_phase_registry(**kwargs)
    picker = run_create_phase_picker_report(**kwargs)
    return {"registry": validator["report"], "picker": picker["report"]}


def baseline():
    if (HERE / "preservation_baseline.json").exists():
        raise RuntimeError("baseline_already_exists_do_not_repin")
    files = {name: digest(path) for name, path in existing_files()}
    result = {"phase_id": "RUNTIME.SANDBOX.2.PRELADDER.DIAG.1", "files": files,
              "file_count": len(files), "scope": "existing tracked/nonignored files plus frozen auth preservation history and established ignored history roots",
              "git_status_porcelain": git("status", "--porcelain=v1", "-z").decode("utf-8"),
              "registry_picker_baseline": registry_reports("baseline_reports")}
    write("preservation_baseline.json", result, exclusive=True)
    return {"passed": True, "historical_file_count": len(files)}


def preservation():
    saved = json.loads((HERE / "preservation_baseline.json").read_text(encoding="utf-8"))
    changed = [name for name, value in saved["files"].items()
               if not (ROOT / name).is_file() or digest(ROOT / name) != value]
    added = sorted({name for name, _ in existing_files()} - set(saved["files"]))
    return {"passed": not changed and not added, "historical_file_count": len(saved["files"]),
            "changed_or_missing": changed, "unexpected_new_files_outside_phase": added}


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


def pytest_worker(scope="sandbox2"):
    scratch = HERE / "validation_tmp"
    scratch.mkdir(exist_ok=True)
    os.environ.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                       "TEMP": str(scratch), "TMP": str(scratch), "TMPDIR": str(scratch)})
    tempfile.tempdir = str(scratch)
    evidence = _worker_guard()
    import pytest
    args = ["-q", "-p", "no:cacheprovider", "-o", "addopts=",
            "-o", "log_file=" + str(scratch / ("pytest-log-" + scope + ".txt")),
            "--basetemp=" + str(scratch / ("pytest-basetemp-" + scope + "-" + str(os.getpid())))]
    if scope == "sandbox2":
        args.extend(["tests/test_runtime_sandbox2.py", str(HERE / "test_classifier.py")])
    else:
        args.extend(["tests/test_phase_registry.py", "tests/test_phase_picker.py"])
    class OutcomeRecorder:
        def __init__(self):
            self.failed = []
            self.passed = []
            self.skipped = []

        def pytest_runtest_logreport(self, report):
            if report.failed:
                self.failed.append({"nodeid": report.nodeid, "when": report.when})
            elif report.when == "call" and report.passed:
                self.passed.append(report.nodeid)
            elif report.skipped:
                self.skipped.append(report.nodeid)

    recorder = OutcomeRecorder()
    code = int(pytest.main(args, plugins=[recorder]))
    return {"passed": code == 0, "exit_code": code, "args": args,
            "passed_test_count": len(recorder.passed), "failed_test_count": len(recorder.failed),
            "failed_test_ids": sorted(recorder.failed, key=lambda row: (row["nodeid"], row["when"])),
            "skipped_test_ids": sorted(recorder.skipped),
            "audit_guard": evidence, "temporary_root_confined_to_new_phase": True}


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
                 "registry-picker-before": lambda: pytest_worker("registry-picker-before"),
                 "registry-picker-after": lambda: pytest_worker("registry-picker-after")}
    result = functions[mode]()
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


def validate():
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
    results = {mode: run_worker(mode) for mode in ("pytest", "auth-matrix", "auth-artifacts", "benchmark")}
    after_tests = run_worker("registry-picker-after")
    keys = ("exit_code", "passed_test_count", "failed_test_count", "failed_test_ids", "skipped_test_ids")
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
    result = {"passed": all(value["passed"] for value in results.values()),
              "phase_id": "RUNTIME.SANDBOX.2.PRELADDER.DIAG.1", "checks": results,
              "validation_live_owner_invocations": 0, "validation_Docker_controls": 0,
              "validation_Java_effects": 0, "all_output_confined_to_new_phase": True}
    write("validation_summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("baseline", "validate", "preservation", "worker"))
    parser.add_argument("worker_mode", nargs="?", choices=("pytest", "auth-matrix", "auth-artifacts", "benchmark",
                                                            "registry-picker-before", "registry-picker-after"))
    arguments = parser.parse_args()
    mode = arguments.mode
    if mode == "baseline":
        result = baseline()
    elif mode == "preservation":
        result = preservation()
        write("preservation_after.json", result)
    elif mode == "worker":
        return worker(arguments.worker_mode)
    else:
        result = validate()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
