from __future__ import annotations

import csv
import io
import os
import re
import shlex
import signal
import subprocess
from dataclasses import dataclass
from typing import Iterable

_INSPECTOR_TOKEN = "@modelcontextprotocol/inspector"
_PROCESS_SNAPSHOT_TIMEOUT_SEC = 10
_INSPECTOR_CLI_PATH_RE = re.compile(
    r"(?:^|/)@modelcontextprotocol/inspector/(?:dist|cli/build)/cli\.js$",
    re.IGNORECASE,
)
_NPM_NPX_CLI_PATH_RE = re.compile(
    r"(?:^|/)npm/bin/npx-cli\.js$",
    re.IGNORECASE,
)
_NODE_COMMAND_RE = re.compile(
    r'^\s*(?:"(?:[^"]*/)?node(?:\.exe)?"|'
    r"'(?:[^']*/)?node(?:\.exe)?'|"
    r"(?:[^\s\"']*/)?node(?:\.exe)?)(?=$|\s)",
    re.IGNORECASE,
)
_NPX_COMMAND_RE = re.compile(
    r'^\s*(?:"(?:[^"]*/)?npx(?:\.cmd|\.exe|-cli\.js)?"|'
    r"'(?:[^']*/)?npx(?:\.cmd|\.exe|-cli\.js)?'|"
    r"(?:[^\s\"']*/)?npx(?:\.cmd|\.exe|-cli\.js)?)(?=$|\s)",
    re.IGNORECASE,
)
_NPM_EXEC_COMMAND_RE = re.compile(
    r'^\s*(?:"(?:[^"]*/)?(?:npm(?:\.cmd|\.exe)?|npm-cli\.js)"|'
    r"'(?:[^']*/)?(?:npm(?:\.cmd|\.exe)?|npm-cli\.js)'|"
    r"(?:[^\s\"']*/)?(?:npm(?:\.cmd|\.exe)?|npm-cli\.js))"
    r"\s+exec(?=$|\s)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int | None
    command_line: str


def is_mcp_inspector_command(command_line: str | None) -> bool:
    if not command_line:
        return False

    normalized = command_line.replace("\\", "/")
    node_args = _command_args(normalized, _NODE_COMMAND_RE)
    if node_args is not None:
        if not node_args:
            return False
        if _INSPECTOR_CLI_PATH_RE.search(node_args[0]):
            return True
        return bool(
            _NPM_NPX_CLI_PATH_RE.search(node_args[0])
            and _inspector_is_package_target(node_args[1:])
        )

    npm_args = _command_args(normalized, _NPM_EXEC_COMMAND_RE)
    if npm_args is not None:
        return _inspector_is_package_target(npm_args)

    npx_args = _command_args(normalized, _NPX_COMMAND_RE)
    return npx_args is not None and _inspector_is_package_target(npx_args)


def _command_args(command_line: str, command_re: re.Pattern[str]) -> list[str] | None:
    match = command_re.match(command_line)
    if not match:
        return None
    try:
        return shlex.split(command_line[match.end() :])
    except ValueError:
        return []


def _inspector_is_package_target(arguments: list[str]) -> bool:
    while arguments and arguments[0].lower() in {"-y", "--yes"}:
        arguments = arguments[1:]
    return bool(arguments and arguments[0].lower() == _INSPECTOR_TOKEN)


def _run_snapshot_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=_PROCESS_SNAPSHOT_TIMEOUT_SEC,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _read_windows_processes() -> list[ProcessInfo]:
    output = _run_snapshot_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process | "
                "Select-Object ProcessId,ParentProcessId,CommandLine | "
                "ConvertTo-Csv -NoTypeInformation"
            ),
        ]
    )
    processes = []
    for row in csv.DictReader(io.StringIO(output)):
        try:
            processes.append(
                ProcessInfo(
                    pid=int(row["ProcessId"]),
                    ppid=int(row["ParentProcessId"]),
                    command_line=row.get("CommandLine") or "",
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return processes


def _read_posix_processes() -> list[ProcessInfo]:
    output = _run_snapshot_command(["ps", "-eo", "pid=,ppid=,args="])
    processes = []
    for line in output.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        try:
            processes.append(
                ProcessInfo(
                    pid=int(parts[0]),
                    ppid=int(parts[1]),
                    command_line=parts[2],
                )
            )
        except ValueError:
            continue
    return processes


def _read_processes() -> list[ProcessInfo]:
    return _read_windows_processes() if os.name == "nt" else _read_posix_processes()


def _snapshot_tree_pids(root_pid: int, processes: Iterable[ProcessInfo]) -> list[int]:
    children_by_parent: dict[int, list[int]] = {}
    for process in processes:
        if process.ppid is not None:
            children_by_parent.setdefault(process.ppid, []).append(process.pid)

    tree = []
    pending = [root_pid]
    seen = set()
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        tree.append(pid)
        pending.extend(children_by_parent.get(pid, []))
    return list(reversed(tree))


def _terminate_process_tree(pid: int, snapshot: list[ProcessInfo]) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
                text=True,
                timeout=_PROCESS_SNAPSHOT_TIMEOUT_SEC,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    stopped = False
    for tree_pid in _snapshot_tree_pids(pid, snapshot):
        try:
            os.kill(tree_pid, signal.SIGTERM)
        except (OSError, PermissionError, ProcessLookupError):
            continue
        stopped = True
    return stopped


def stop_mcp_inspectors() -> int:
    try:
        snapshot = _read_processes()
    except Exception:
        return 0

    current_pid = os.getpid()
    stopped = 0
    for process in snapshot:
        if current_pid in _snapshot_tree_pids(process.pid, snapshot):
            continue
        if not is_mcp_inspector_command(process.command_line):
            continue
        try:
            stopped += int(_terminate_process_tree(process.pid, snapshot))
        except Exception:
            continue
    return stopped
