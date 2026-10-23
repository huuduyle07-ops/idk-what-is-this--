"""Pure retained-live controller contract validation; no owner import or operational effect.

All generated evidence and scratch files stay in this additive phase. Snapshot
is immutable and must precede validation. Existing registry test failures are
compared exactly rather than repaired. The only permitted child process is the
explicit source-control git modes, outside the operational guard. Every other
mode is read-only outside this additive phase. No Git index mutation is used.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import contextlib
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import platform
import re
import runpy
import socket
import subprocess
import sys
import tempfile
import threading
import traceback
from unittest.mock import patch

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
NEW_TEST = OUTPUT.relative_to(ROOT).as_posix() + "/test_contract.py"
BASELINE_NAME = "preservation_baseline.json"
GIT_BASELINE_NAME = "git_diff_baseline.json"
CACHE_NAMES = {".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tmp", "tmp_tests"}
STATIC_SCOPES = ("core", "tests", "scripts", "benchmarks", "web", "docs/roadmap")
CAPABILITY_PREFIXES = (
    "core.synthetic_", "core.runtime_java_", "core.behavioral_diagnostic_executor",
    "core.read_only_reflection", "core.sandboxed_java_", "core.candidate_runtime_",
    "core.thread_compatible_runtime_", "core.sandbox_backend_", "core.runtime_diagnostic_",
    "core.behavioral_execution_admission", "core.behavioral_validation_specification",
    "core.behavioral_evidence_execution_plan",
)
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
os.environ.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    PYTEST_ADDOPTS="", PYTEST_PLUGINS="")


def write_json(name, value, *, exclusive=False):
    with (OUTPUT / name).open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=True)
        stream.write("\n")


def read_json(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def write_log(name, value):
    # Captured historical diagnostics can contain the offending whitespace;
    # preserve the exact bytes in JSON and keep the reviewable text file clean.
    normalized = "\n".join(line.rstrip() for line in value.splitlines())
    (OUTPUT / name).write_text(normalized + ("\n" if normalized else ""), encoding="utf-8")


def compact(value):
    print(json.dumps(value, sort_keys=True, ensure_ascii=True))


def link_record(path):
    return {"kind": "link", "target": os.readlink(path)}


def inventory():
    """Hash every non-cache workspace file; never traverse a link or junction."""
    files, excluded = {}, []
    for current, dirs, names in os.walk(ROOT, followlinks=False):
        base = Path(current)
        retained = []
        for name in sorted(dirs):
            target = base / name
            relative = target.relative_to(ROOT).as_posix()
            if target == OUTPUT or name in CACHE_NAMES:
                excluded.append(relative + "/")
            elif target.is_symlink() or getattr(target, "is_junction", lambda: False)():
                files[relative] = link_record(target)
            else:
                retained.append(name)
        dirs[:] = retained
        for name in sorted(names):
            path = base / name
            relative = path.relative_to(ROOT).as_posix()
            if path.is_symlink():
                files[relative] = link_record(path)
                continue
            digest, size = sha256(), 0
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
            files[relative] = {"kind": "file", "bytes": size, "sha256": digest.hexdigest()}
    return {"scope": "entire non-cache workspace including root/config/web and frozen history",
        "file_count": len(files), "files": files, "excluded": sorted(excluded),
        "links_followed": False, "new_phase_excluded": OUTPUT.relative_to(ROOT).as_posix()}


def snapshot():
    if (OUTPUT / BASELINE_NAME).exists():
        raise AssertionError("Original preservation baseline cannot be overwritten")
    value = inventory()
    write_json(BASELINE_NAME, value, exclusive=True)
    compact({"mode": "snapshot", "file_count": value["file_count"],
        "baseline_sha256": sha256((OUTPUT / BASELINE_NAME).read_bytes()).hexdigest()})
    return 0


@contextlib.contextmanager
def operational_guard():
    active = [True]
    counters = dict.fromkeys(("process_attempts", "network_attempts",
        "outside_phase_write_attempts", "capability_owner_import_attempts",
        "capability_or_transition_attempts", "execution_or_verification_attempts"), 0)
    blocked = []

    def reject(kind, detail):
        counters[kind] += 1
        blocked.append(str(detail))
        raise AssertionError("Pure retained-live controller contract validation denied: " + str(detail))

    def outside(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return False
        resolved = Path(os.fsdecode(path)).resolve()
        return not resolved.is_relative_to(OUTPUT) or resolved in {
            OUTPUT / BASELINE_NAME, OUTPUT / GIT_BASELINE_NAME,
            OUTPUT / "registry_baseline.json", OUTPUT / "registry_baseline.txt"}

    def audit(event, args):
        if not active[0]:
            return
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
                "os.spawn", "os.startfile", "os.fork", "os.forkpty"}:
            reject("process_attempts", event)
        if event in {"socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo"}:
            reject("network_attempts", event)
        if event == "import" and str(args[0]).startswith(CAPABILITY_PREFIXES):
            reject("capability_owner_import_attempts", args[0])
        if event == "open":
            path, mode, flags = args
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND) and outside(path):
                reject("outside_phase_write_attempts", "open:" + str(path))
        if event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link",
                "os.symlink", "os.chmod", "os.truncate", "os.utime"}:
            if any(outside(path) for path in args[:2]):
                reject("outside_phase_write_attempts", event + ":" + str(args))

    def profile(frame, event, arg):
        if not active[0] or event != "call":
            return
        code = frame.f_code
        if not code.co_filename.startswith(str(ROOT / "core") + os.sep):
            return
        name = code.co_name
        if name in {"_issue", "_issue_upstream", "_transition", "executor1r_before_request",
                "executor1r_after_request"} or name.startswith(("issue_", "consume_", "invalidate_")):
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
            yield counters, blocked
    finally:
        active[0] = False
        sys.setprofile(previous)
        threading.setprofile(previous_threads)


class Results:
    def __init__(self):
        self.collected, self.passed, self.failed, self.skipped = 0, [], [], []
        self.collection_errors = []

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.failed.append({"nodeid": report.nodeid, "when": report.when,
                "signature": report.longreprtext})
        elif report.skipped:
            self.skipped.append({"nodeid": report.nodeid, "when": report.when,
                "signature": str(report.longrepr)})
        elif report.when == "call" and report.passed:
            self.passed.append(report.nodeid)

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append({"nodeid": report.nodeid,
                "signature": report.longreprtext})


def validate(mode):
    if mode == "registry_baseline" and (OUTPUT / "registry_baseline.json").exists():
        raise AssertionError("Original registry baseline cannot be overwritten")
    scratch = OUTPUT / "validation_tmp" / mode
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch))
    tempfile.tempdir = str(scratch)
    if sys.platform == "win32":
        # platform.processor() otherwise starts a Windows helper during pytest.
        version = sys.getwindowsversion()
        platform._uname_cache = platform.uname_result("Windows", os.environ.get("COMPUTERNAME", ""),
            str(version.major), ".".join(map(str, version[:3])), os.environ.get("PROCESSOR_ARCHITECTURE", ""))
    log = io.StringIO()
    result = {"mode": mode, "scratch_inside_new_phase": str(scratch),
        "bytecode_writes_disabled": True, "full_issuance_dependent_suites_run": False,
        "production_registries_seeded": False, "production_validators_patched": False,
        "validator_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    counters, blocked = {}, []
    try:
        # urllib3's import-time IPv6 availability probe binds a socket. Suppress
        # only that optional probe; no production validator or owner is patched.
        with patch.object(socket, "has_ipv6", False), operational_guard() as (counters, blocked), contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            if mode in {"benchmark", "author", "report"}:
                target = ROOT / "benchmarks/run_benchmarks.py" if mode == "benchmark" else OUTPUT / (
                    "write_contract.py" if mode == "author" else "finalize_report.py")
                sys.argv = [str(target), *(["--check"] if mode == "benchmark" else [])]
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
                    passed_nodes=sorted(plugin.passed),
                    failed=sorted(plugin.failed, key=lambda row: (row["nodeid"], row["when"])),
                    skipped=sorted(plugin.skipped, key=lambda row: (row["nodeid"], row["when"])),
                    collection_errors=sorted(plugin.collection_errors, key=lambda row: row["nodeid"]))
                if mode.startswith("registry"):
                    from core.phase_registry import load_phase_registry, summarize_phase_registry
                    from core.phase_picker import pick_phase_candidates
                    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
                    result["registry_summary"] = summarize_phase_registry(registry,
                        report_id="preparation-controller-contract", created_at="2026-10-18")
                    result["picker"] = pick_phase_candidates(registry)
    except Exception as error:
        traceback.print_exc(file=log)
        result.update(exit_code=2, error=type(error).__name__ + ": " + str(error))
    result.update(audit_guard=counters, blocked_actions=blocked,
        all_operational_effects_zero=not any(counters.values()) and not blocked,
        imported_capability_owners=sorted(name for name in sys.modules if name.startswith(CAPABILITY_PREFIXES)))
    if result["imported_capability_owners"] or not result["all_operational_effects_zero"]:
        result["exit_code"] = result.get("exit_code") or 3
    if mode == "benchmark":
        checked = re.search(r"^Checked: (\d+)$", log.getvalue(), re.MULTILINE)
        errors = re.search(r"^Errors: (\d+)$", log.getvalue(), re.MULTILINE)
        result.update(benchmark_cases_checked=int(checked.group(1)) if checked else None,
            benchmark_errors=int(errors.group(1)) if errors else None)
    write_log(mode + ".txt", log.getvalue())
    write_json(mode + ".json", result, exclusive=mode == "registry_baseline")
    compact({key: value for key, value in result.items() if key not in {
        "picker", "registry_summary", "passed_nodes", "selected_nodes", "scratch_inside_new_phase",
        "failed", "skipped", "collection_errors"}})
    return result["exit_code"]


def compare():
    baseline, after = read_json("registry_baseline.json"), read_json("registry_after.json")
    def semantic(value):
        if isinstance(value, str):
            # Pytest includes process-specific allocator addresses in generator
            # reprs. Raw diagnostics remain immutable in each run's JSON/text.
            return re.sub(r" at 0x[0-9A-Fa-f]+>", " at <process-address>>", value)
        if isinstance(value, list):
            return [semantic(item) for item in value]
        if isinstance(value, dict):
            return {key: semantic(item) for key, item in value.items()}
        return value
    keys = ("exit_code", "collected", "passed_nodes", "failed", "skipped",
        "collection_errors", "registry_summary", "picker", "audit_guard",
        "blocked_actions", "all_operational_effects_zero", "imported_capability_owners")
    result = {"unchanged": all(semantic(baseline[key]) == semantic(after[key]) for key in keys),
        "baseline_collected": baseline["collected"], "after_collected": after["collected"],
        "baseline_passed": baseline["passed_count"], "after_passed": after["passed_count"],
        "baseline_failed": baseline["failed"], "after_failed": after["failed"],
        "existing_failures_preserved": semantic(baseline["failed"]) == semantic(after["failed"]),
        "skip_signatures_preserved": baseline["skipped"] == after["skipped"],
        "collection_failures_preserved": baseline["collection_errors"] == after["collection_errors"],
        "exact_compared_keys": list(keys),
        "signature_comparison": "Raw diagnostics retained; normalize only Python repr allocator ' at 0x...>' addresses before comparing. All node IDs, assertion text, expected/actual values and failure phases are exact.",
        "registry_and_picker_projections_identical": all(baseline[key] == after[key] for key in ("registry_summary", "picker")),
        "old_files_not_modified_to_repair_baseline": True}
    write_json("registry_comparison.json", result)
    compact({key: value for key, value in result.items() if key not in {"baseline_failed", "after_failed"}})
    return 0 if result["unchanged"] else 1


def preservation():
    baseline, after = read_json(BASELINE_NAME)["files"], inventory()
    files = after["files"]
    result = {"baseline_file_count": len(baseline), "after_file_count": len(files),
        "changed": sorted(name for name in baseline.keys() & files.keys() if baseline[name] != files[name]),
        "deleted": sorted(baseline.keys() - files.keys()),
        "added_outside_new_phase": sorted(files.keys() - baseline.keys()),
        "scope": after["scope"], "allowed_additions_outside_phase": []}
    result["historical_preservation_passed"] = not any(result[key] for key in ("changed", "deleted", "added_outside_new_phase"))
    write_json("preservation_after.json", after)
    write_json("preservation_comparison.json", result)
    compact(result)
    return 0 if result["historical_preservation_passed"] else 1


def static():
    compiled, validated, errors, whitespace, ast_checks = [], [], [], [], []
    authored = [path for path in OUTPUT.rglob("*") if path.is_file()
        and "validation_tmp" not in path.relative_to(OUTPUT).parts]
    frozen = [ROOT / name for name in read_json(BASELINE_NAME)["files"]
        if name.endswith(".py") and any(name.startswith(scope + "/") for scope in STATIC_SCOPES)]
    for path in [*authored, *frozen]:
        if path.suffix not in {".py", ".json", ".md"}:
            continue
        name = path.relative_to(ROOT).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix == ".py":
                tree = ast.parse(content, filename=str(path))
                compile(content, str(path), "exec")
                compiled.append(name)
                if path in authored:
                    imports = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            imports.extend(alias.name for alias in node.names)
                        elif isinstance(node, ast.ImportFrom):
                            module = node.module or ""
                            imports.extend([module, *(module + "." + alias.name for alias in node.names)])
                    forbidden = sorted(value for value in imports if value.startswith(CAPABILITY_PREFIXES))
                    ast_checks.append({"file": name, "imports": sorted(set(imports)),
                        "capability_owner_imports": forbidden, "source_executed": False})
                    if forbidden:
                        errors.append({"file": name, "error": "Capability owner import in pure phase source: " + repr(forbidden)})
            elif path.suffix == ".json":
                json.loads(content)
                validated.append(name)
            if path in authored:
                whitespace.extend({"file": name, "line": line} for line, value in enumerate(content.splitlines(), 1)
                    if value.rstrip() != value)
        except Exception as error:
            errors.append({"file": name, "error": type(error).__name__ + ": " + str(error)})
    result = {"compiled_in_memory": compiled, "compiled_count": len(compiled),
        "json_validated": validated, "json_count": len(validated), "errors": errors,
        "authored_python_ast_checks": ast_checks,
        "whitespace_errors": whitespace, "bytecode_written": False, "owner_modules_imported": False,
        "passed": not errors and not whitespace}
    write_json("static_validation.json", result)
    compact({key: value for key, value in result.items() if key not in {
        "compiled_in_memory", "json_validated", "authored_python_ast_checks"}})
    return 0 if result["passed"] else 1


def run_git(arguments):
    command = ["git", *arguments]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    return {"command": command, "exit_code": completed.returncode,
        "stdout": completed.stdout, "stderr": completed.stderr}


def tracked_diff_checks():
    return [run_git(["diff", "--check"]), run_git(["diff", "--cached", "--check"])]


def git_baseline():
    if (OUTPUT / GIT_BASELINE_NAME).exists():
        raise AssertionError("Original Git whitespace baseline cannot be overwritten")
    checks = tracked_diff_checks()
    if any(row["exit_code"] not in (0, 1, 2) or "fatal:" in row["stderr"].lower()
            for row in checks):
        raise AssertionError("Git baseline could not be captured: " + repr(checks))
    result = {"tracked_checks": checks,
        "executed_outside_operational_guard": True, "source_validation_only": True,
        "git_index_modified": False, "operational_command_invoked": False}
    write_json(GIT_BASELINE_NAME, result, exclusive=True)
    compact({"mode": "git_baseline", "immutable_baseline_created": True,
        "existing_whitespace_exit_codes": [row["exit_code"] for row in result["tracked_checks"]]})
    return 0


def git_diff():
    baseline = read_json(GIT_BASELINE_NAME)
    tracked = tracked_diff_checks()
    scratch = OUTPUT / "validation_tmp" / "git_diff"
    scratch.mkdir(parents=True, exist_ok=True)
    empty = scratch / "empty"
    empty.write_bytes(b"")
    phase_checks = []
    for path in sorted(OUTPUT.rglob("*")):
        if not path.is_file() or any(part in CACHE_NAMES | {"validation_tmp"}
                for part in path.relative_to(OUTPUT).parts):
            continue
        row = run_git(["-c", "core.autocrlf=false", "-c",
            "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
            "diff", "--no-index", "--check", "--",
            str(empty.relative_to(ROOT)), str(path.relative_to(ROOT))])
        row["file"] = path.relative_to(ROOT).as_posix()
        # --no-index may return 1 merely because two files differ. Actual check
        # diagnostics (including fatal errors) remain a failure.
        row["passed"] = row["exit_code"] in (0, 1) and not row["stdout"] and not row["stderr"]
        phase_checks.append(row)
    unchanged = baseline["tracked_checks"] == tracked
    result = {"tracked_checks": tracked, "existing_whitespace_unchanged": unchanged,
        "new_phase_whitespace_policy": "Git default blank-at-eol/blank-at-eof/space-before-tab checks with cr-at-eol for Windows CRLF terminators; actual trailing spaces remain errors",
        "phase_files_checked_without_index_mutation": len(phase_checks),
        "phase_checks": phase_checks, "phase_whitespace_passed": all(row["passed"] for row in phase_checks),
        "executed_outside_operational_guard": True, "source_validation_only": True,
        "git_index_modified": False, "operational_command_invoked": False}
    result["passed"] = unchanged and result["phase_whitespace_passed"]
    result["exit_code"] = 0 if result["passed"] else 1
    logs = [" ".join(row["command"]) + "\n" + row["stdout"] + row["stderr"]
        for row in [*tracked, *phase_checks] if row["stdout"] or row["stderr"]]
    write_log("git_diff_check.txt", "\n".join(logs))
    write_json("git_diff_check.json", result)
    compact({key: value for key, value in result.items() if key not in {"tracked_checks", "phase_checks"}})
    return result["exit_code"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("snapshot", "author", "report", "focused", "registry_baseline",
        "registry_after", "benchmark", "static", "preservation", "git_baseline", "git_diff", "compare"))
    mode = parser.parse_args().mode
    os.chdir(ROOT)
    if mode == "snapshot":
        return snapshot()
    if not (OUTPUT / BASELINE_NAME).is_file():
        raise AssertionError("Capture immutable preservation baseline before any validation")
    commands = {"compare": compare, "preservation": preservation, "static": static,
        "git_baseline": git_baseline, "git_diff": git_diff}
    return commands[mode]() if mode in commands else validate(mode)


if __name__ == "__main__":
    raise SystemExit(main())
