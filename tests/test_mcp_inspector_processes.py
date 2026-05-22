"""Process cleanup tests for MCP Inspector shutdown linkage."""
from __future__ import annotations

import pytest

from web import mcp_inspector_processes as inspector_processes


def test_inspector_match_accepts_official_package_token():
    command_line = (
        r'"C:\Program Files\nodejs\npx.CMD" -y '
        "@modelcontextprotocol/inspector "
        r"D:\anaconda\python.exe scripts/mcp_readonly_server.py"
    )

    assert inspector_processes.is_mcp_inspector_command(command_line) is True


def test_inspector_match_accepts_spawned_cli_package_path():
    command_line = (
        r'"C:\Program Files\nodejs\node.exe" '
        r"C:\Users\Admin\AppData\Local\npm-cache\_npx\abc\node_modules"
        r"\@modelcontextprotocol\inspector\dist\cli.js "
        "python scripts/mcp_readonly_server.py"
    )

    assert inspector_processes.is_mcp_inspector_command(command_line) is True


@pytest.mark.parametrize(
    "command_line",
    [
        r"C:\Program Files\nodejs\npx.CMD create-vite demo",
        r"C:\Program Files\nodejs\node.exe inspector-proxy.js",
        "npm install @modelcontextprotocol/inspector",
        "npm view @modelcontextprotocol/inspector",
        "npx -y @modelcontextprotocol/inspector-something",
        "npx -y cowsay @modelcontextprotocol/inspector",
        (
            r"node tools/scan.js C:\tmp\node_modules"
            r"\@modelcontextprotocol\inspector\dist\cli.js"
        ),
        "python tools/render_docs.py npx @modelcontextprotocol/inspector",
        (
            r"python tools/scan.py node C:\tmp\node_modules"
            r"\@modelcontextprotocol\inspector\dist\cli.js"
        ),
        r"D:\anaconda\python.exe scripts/mcp_readonly_server.py",
        "http://127.0.0.1:6274",
        "",
        None,
    ],
)
def test_inspector_match_rejects_unrelated_processes(command_line):
    assert inspector_processes.is_mcp_inspector_command(command_line) is False


def test_stop_mcp_inspectors_terminates_matching_roots_only(monkeypatch):
    processes = [
        inspector_processes.ProcessInfo(
            pid=101,
            ppid=1,
            command_line="npx -y @modelcontextprotocol/inspector python scripts/mcp_readonly_server.py",
        ),
        inspector_processes.ProcessInfo(
            pid=102,
            ppid=101,
            command_line="python scripts/mcp_readonly_server.py",
        ),
        inspector_processes.ProcessInfo(
            pid=201,
            ppid=1,
            command_line="npx create-vite demo",
        ),
    ]
    terminated = []

    monkeypatch.setattr(inspector_processes, "_read_processes", lambda: processes)
    monkeypatch.setattr(
        inspector_processes,
        "_terminate_process_tree",
        lambda pid, snapshot: terminated.append((pid, snapshot)) or True,
    )

    assert inspector_processes.stop_mcp_inspectors() == 1
    assert terminated == [(101, processes)]


def test_stop_mcp_inspectors_skips_tree_containing_current_process(monkeypatch):
    processes = [
        inspector_processes.ProcessInfo(
            pid=101,
            ppid=1,
            command_line="npx -y @modelcontextprotocol/inspector",
        ),
        inspector_processes.ProcessInfo(
            pid=102,
            ppid=101,
            command_line="node inspector child",
        ),
        inspector_processes.ProcessInfo(
            pid=103,
            ppid=102,
            command_line="python current process",
        ),
        inspector_processes.ProcessInfo(
            pid=201,
            ppid=1,
            command_line="npx -y @modelcontextprotocol/inspector",
        ),
    ]
    terminated = []

    monkeypatch.setattr(inspector_processes.os, "getpid", lambda: 103)
    monkeypatch.setattr(inspector_processes, "_read_processes", lambda: processes)
    monkeypatch.setattr(
        inspector_processes,
        "_terminate_process_tree",
        lambda pid, snapshot: terminated.append((pid, snapshot)) or True,
    )

    assert inspector_processes.stop_mcp_inspectors() == 1
    assert terminated == [(201, processes)]


def test_read_windows_processes_parses_cim_csv(monkeypatch):
    calls = []
    csv_output = (
        '"ProcessId","ParentProcessId","CommandLine"\n'
        '"101","1","npx -y @modelcontextprotocol/inspector"\n'
        '"102","101","python scripts/mcp_readonly_server.py"\n'
        '"skip","101","bad pid"\n'
    )

    monkeypatch.setattr(
        inspector_processes,
        "_run_snapshot_command",
        lambda command: calls.append(command) or csv_output,
    )

    assert inspector_processes._read_windows_processes() == [
        inspector_processes.ProcessInfo(
            pid=101,
            ppid=1,
            command_line="npx -y @modelcontextprotocol/inspector",
        ),
        inspector_processes.ProcessInfo(
            pid=102,
            ppid=101,
            command_line="python scripts/mcp_readonly_server.py",
        ),
    ]
    assert calls[0][:3] == ["powershell", "-NoProfile", "-Command"]
    assert "Get-CimInstance Win32_Process" in calls[0][-1]
    assert "ConvertTo-Csv" in calls[0][-1]


def test_read_posix_processes_parses_ps_snapshot(monkeypatch):
    calls = []
    ps_output = (
        " 101 1 npx -y @modelcontextprotocol/inspector\n"
        " 102 101 python scripts/mcp_readonly_server.py\n"
        " incomplete row\n"
        " bad 101 bad pid\n"
    )

    monkeypatch.setattr(
        inspector_processes,
        "_run_snapshot_command",
        lambda command: calls.append(command) or ps_output,
    )

    assert inspector_processes._read_posix_processes() == [
        inspector_processes.ProcessInfo(
            pid=101,
            ppid=1,
            command_line="npx -y @modelcontextprotocol/inspector",
        ),
        inspector_processes.ProcessInfo(
            pid=102,
            ppid=101,
            command_line="python scripts/mcp_readonly_server.py",
        ),
    ]
    assert calls == [["ps", "-eo", "pid=,ppid=,args="]]


def test_run_snapshot_command_returns_empty_on_adapter_failure(monkeypatch):
    def fail_run(*_args, **_kwargs):
        raise OSError("missing process adapter")

    monkeypatch.setattr(inspector_processes.subprocess, "run", fail_run)

    assert inspector_processes._run_snapshot_command(["ps"]) == ""


def test_terminate_process_tree_windows_uses_taskkill_flags(monkeypatch):
    calls = []

    class Completed:
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    monkeypatch.setattr(inspector_processes.os, "name", "nt")
    monkeypatch.setattr(inspector_processes.subprocess, "run", fake_run)

    assert inspector_processes._terminate_process_tree(101, []) is True
    assert calls == [
        (
            ["taskkill", "/PID", "101", "/T", "/F"],
            {
                "capture_output": True,
                "check": False,
                "text": True,
                "timeout": inspector_processes._PROCESS_SNAPSHOT_TIMEOUT_SEC,
            },
        )
    ]


def test_terminate_process_tree_windows_returns_false_on_taskkill_failure(
    monkeypatch,
):
    def fail_run(*_args, **_kwargs):
        raise OSError("taskkill unavailable")

    monkeypatch.setattr(inspector_processes.os, "name", "nt")
    monkeypatch.setattr(inspector_processes.subprocess, "run", fail_run)

    assert inspector_processes._terminate_process_tree(101, []) is False


def test_terminate_process_tree_posix_signals_descendants_before_root(monkeypatch):
    signals = []
    snapshot = [
        inspector_processes.ProcessInfo(101, 1, "npx inspector"),
        inspector_processes.ProcessInfo(102, 101, "node inspector child"),
        inspector_processes.ProcessInfo(103, 102, "python inspector server"),
    ]

    monkeypatch.setattr(inspector_processes.os, "name", "posix")
    monkeypatch.setattr(
        inspector_processes.os,
        "kill",
        lambda pid, sig: signals.append((pid, sig)),
    )

    assert inspector_processes._terminate_process_tree(101, snapshot) is True
    assert signals == [
        (103, inspector_processes.signal.SIGTERM),
        (102, inspector_processes.signal.SIGTERM),
        (101, inspector_processes.signal.SIGTERM),
    ]


def test_terminate_process_tree_posix_ignores_kill_failures(monkeypatch):
    attempts = []
    snapshot = [
        inspector_processes.ProcessInfo(101, 1, "npx inspector"),
        inspector_processes.ProcessInfo(102, 101, "node inspector child"),
    ]

    def fail_kill(pid, _sig):
        attempts.append(pid)
        raise ProcessLookupError(pid)

    monkeypatch.setattr(inspector_processes.os, "name", "posix")
    monkeypatch.setattr(inspector_processes.os, "kill", fail_kill)

    assert inspector_processes._terminate_process_tree(101, snapshot) is False
    assert attempts == [102, 101]
