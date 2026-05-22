# MCP Inspector Web Shutdown Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop any matching local MCP Inspector process tree when the Flask web UI exits from a terminal shutdown path such as `Ctrl+C`.

**Architecture:** Keep process selection and termination in a focused web helper that snapshots local process command lines, matches only the official MCP Inspector package token, and performs best-effort process-tree termination with standard-library subprocess/process APIs. Put lifecycle ownership in `web.runner` through a small Flask run wrapper, and route both documented web entry points through that wrapper.

**Tech Stack:** Python 3, Flask dev server lifecycle, PowerShell/CIM and `taskkill` on Windows, `ps`/signals on POSIX, pytest.

---

## File Map

- Create `web/mcp_inspector_processes.py`: pure helper for Inspector command matching, local process snapshots, and best-effort process-tree cleanup.
- Create `tests/test_mcp_inspector_processes.py`: matcher and cleanup-selection tests that never terminate real processes.
- Modify `web/runner.py`: shared Flask run wrapper that always requests Inspector cleanup after the web server exits.
- Modify `web/app.py`: direct `python -m web.app` entrypoint uses the same runner wrapper.
- Create `tests/test_web_runner_shutdown.py`: lifecycle test proving cleanup is requested even when `app.run()` exits via `KeyboardInterrupt`.

### Task 1: Add Narrow MCP Inspector Process Cleanup

**Files:**
- Create: `web/mcp_inspector_processes.py`
- Create: `tests/test_mcp_inspector_processes.py`

- [ ] **Step 1: Write failing matcher and cleanup-selection tests**

Create `tests/test_mcp_inspector_processes.py`:

```python
"""Process cleanup tests for MCP Inspector shutdown linkage."""
from __future__ import annotations

import pytest

from web import mcp_inspector_processes as inspector_processes


def test_inspector_match_accepts_official_package_token():
    command_line = (
        r"C:\Program Files\nodejs\npx.CMD -y "
        "@modelcontextprotocol/inspector "
        r"D:\anaconda\python.exe scripts/mcp_readonly_server.py"
    )

    assert inspector_processes.is_mcp_inspector_command(command_line) is True


@pytest.mark.parametrize(
    "command_line",
    [
        r"C:\Program Files\nodejs\npx.CMD create-vite demo",
        r"C:\Program Files\nodejs\node.exe inspector-proxy.js",
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
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run:

```powershell
python -m pytest tests/test_mcp_inspector_processes.py -q
```

Expected: FAIL during import because `web.mcp_inspector_processes` does not exist yet.

- [ ] **Step 3: Add the standard-library process cleanup helper**

Create `web/mcp_inspector_processes.py`:

```python
from __future__ import annotations

import csv
import io
import os
import signal
import subprocess
from dataclasses import dataclass
from typing import Iterable

_INSPECTOR_TOKEN = "@modelcontextprotocol/inspector"
_PROCESS_SNAPSHOT_TIMEOUT_SEC = 10


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int | None
    command_line: str


def is_mcp_inspector_command(command_line: str | None) -> bool:
    return bool(command_line) and _INSPECTOR_TOKEN in command_line.lower()


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


def _posix_tree_pids(root_pid: int, processes: Iterable[ProcessInfo]) -> list[int]:
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
    for tree_pid in _posix_tree_pids(pid, snapshot):
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

    stopped = 0
    for process in snapshot:
        if process.pid == os.getpid():
            continue
        if not is_mcp_inspector_command(process.command_line):
            continue
        try:
            stopped += int(_terminate_process_tree(process.pid, snapshot))
        except Exception:
            continue
    return stopped
```

- [ ] **Step 4: Run tests to verify matcher and cleanup selection pass**

Run:

```powershell
python -m pytest tests/test_mcp_inspector_processes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit focused process cleanup work**

Run:

```powershell
git add web/mcp_inspector_processes.py tests/test_mcp_inspector_processes.py
git commit -m "add MCP Inspector shutdown cleanup helper"
```

### Task 2: Link Flask Web Shutdown To Inspector Cleanup

**Files:**
- Modify: `web/runner.py`
- Modify: `web/app.py`
- Create: `tests/test_web_runner_shutdown.py`

- [ ] **Step 1: Write failing web-runner shutdown test**

Create `tests/test_web_runner_shutdown.py`:

```python
"""Web runner lifecycle tests."""
from __future__ import annotations

import pytest


def test_web_runner_requests_inspector_cleanup_after_ctrl_c(monkeypatch):
    from web import runner

    calls = []

    class FakeApp:
        def run(self, **kwargs):
            calls.append(("run", kwargs))
            raise KeyboardInterrupt

    monkeypatch.setattr(
        runner,
        "stop_mcp_inspectors",
        lambda: calls.append(("cleanup", {})) or 1,
    )

    with pytest.raises(KeyboardInterrupt):
        runner.run_web_app(FakeApp(), host="127.0.0.1", port=5000)

    assert calls == [
        ("run", {"host": "127.0.0.1", "port": 5000}),
        ("cleanup", {}),
    ]
```

- [ ] **Step 2: Run test to verify it fails before lifecycle wrapper exists**

Run:

```powershell
python -m pytest tests/test_web_runner_shutdown.py -q
```

Expected: FAIL because `web.runner.run_web_app` and the cleanup import do not exist yet.

- [ ] **Step 3: Add shared runner cleanup wrapper**

Add this import to `web/runner.py` near the other imports:

```python
from web.mcp_inspector_processes import stop_mcp_inspectors
```

Add this helper above `launch_web`:

```python
def run_web_app(flask_app, **run_kwargs) -> None:
    try:
        flask_app.run(**run_kwargs)
    finally:
        stopped = stop_mcp_inspectors()
        if stopped:
            print(f"Stopped {stopped} MCP Inspector process tree(s).")
```

Replace the final line of `launch_web` with:

```python
    run_web_app(app, host=host, port=port, debug=False, use_reloader=False)
```

- [ ] **Step 4: Route the direct Flask module entrypoint through the wrapper**

Replace the final block in `web/app.py` with:

```python
if __name__ == "__main__":
    from web.runner import run_web_app

    run_web_app(app, debug=True)
```

- [ ] **Step 5: Run lifecycle and Inspector route tests**

Run:

```powershell
python -m pytest tests/test_web_runner_shutdown.py tests/test_mcp_inspector_route.py -q
```

Expected: PASS. Route behavior still selects the same fixed Inspector targets.

- [ ] **Step 6: Commit lifecycle linkage**

Run:

```powershell
git add web/runner.py web/app.py tests/test_web_runner_shutdown.py
git commit -m "stop MCP Inspector on web shutdown"
```

### Task 3: Verify The Web And MCP Surface

**Files:**
- Test: `tests/test_mcp_inspector_processes.py`
- Test: `tests/test_web_runner_shutdown.py`
- Test: `tests/test_mcp_inspector_route.py`
- Test: `tests/test_mayor_mode_ui.py`
- Test: `tests/test_mcp_audit_route.py`
- Test: `tests/test_mcp_readonly_server.py`
- Test: `tests/test_mcp_artifact_write_server.py`
- Test: `tests/test_tool_registry_routes.py`

- [ ] **Step 1: Run focused Inspector, web UI, audit, and MCP allowlist tests**

Run:

```powershell
python -m pytest tests/test_mcp_inspector_processes.py tests/test_web_runner_shutdown.py tests/test_mcp_inspector_route.py tests/test_mayor_mode_ui.py tests/test_mcp_audit_route.py tests/test_mcp_readonly_server.py tests/test_mcp_artifact_write_server.py tests/test_tool_registry_routes.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run:

```powershell
python -m pytest -q
```

Expected: PASS. If the sandbox blocks Windows temp-directory access, rerun the same command with permission to use the normal temp directory and report both results.

- [ ] **Step 3: Inspect the final diff**

Run:

```powershell
git diff -- web/mcp_inspector_processes.py web/runner.py web/app.py tests/test_mcp_inspector_processes.py tests/test_web_runner_shutdown.py tests/test_mcp_inspector_route.py
```

Expected: only Inspector cleanup helper, shared web shutdown linkage, direct-entrypoint linkage, and focused tests are present.
