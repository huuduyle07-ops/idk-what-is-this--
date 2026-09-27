"""Static subprocess worker for :mod:`core.defect_probe`.

The parent supplies JSON data only.  This file contains the complete execution
logic; no model-authored program, command, assertion or import expression is
ever evaluated.
"""

from __future__ import annotations

import builtins
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Any, Callable


_WORKER_ENV = "CATTUS_DEFECT_PROBE_PAYLOAD"
_WRITE_FLAGS = (
    getattr(os, "O_WRONLY", 0)
    | getattr(os, "O_RDWR", 0)
    | getattr(os, "O_CREAT", 0)
    | getattr(os, "O_TRUNC", 0)
    | getattr(os, "O_APPEND", 0)
)


class SideEffectRefused(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside_repo(repo: Path, value: Any) -> bool:
    if isinstance(value, int):
        return False
    try:
        path = Path(os.fspath(value))
        resolved = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
        resolved.relative_to(repo)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _deny(message: str) -> None:
    raise SideEffectRefused(message)


def _install_side_effect_guards(repo: Path) -> None:
    """Refuse repository writes, child processes and network connections."""

    real_builtin_open = builtins.open
    real_io_open = io.open
    real_os_open = os.open

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        if any(flag in str(mode) for flag in ("w", "a", "x", "+")) and _inside_repo(repo, file):
            _deny("repository write refused")
        return real_builtin_open(file, mode, *args, **kwargs)

    def guarded_io_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        if any(flag in str(mode) for flag in ("w", "a", "x", "+")) and _inside_repo(repo, file):
            _deny("repository write refused")
        return real_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(file: Any, flags: int, *args: Any, **kwargs: Any):
        if flags & _WRITE_FLAGS and _inside_repo(repo, file):
            _deny("repository write refused")
        return real_os_open(file, flags, *args, **kwargs)

    builtins.open = guarded_open
    io.open = guarded_io_open
    os.open = guarded_os_open

    def guard_unary(real: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(path: Any, *args: Any, **kwargs: Any) -> Any:
            if _inside_repo(repo, path):
                _deny("repository mutation refused")
            return real(path, *args, **kwargs)

        return wrapped

    def guard_binary(real: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(source: Any, destination: Any, *args: Any, **kwargs: Any) -> Any:
            if _inside_repo(repo, source) or _inside_repo(repo, destination):
                _deny("repository mutation refused")
            return real(source, destination, *args, **kwargs)

        return wrapped

    for name in (
        "remove",
        "unlink",
        "mkdir",
        "makedirs",
        "rmdir",
        "removedirs",
        "chmod",
        "truncate",
    ):
        real = getattr(os, name, None)
        if callable(real):
            setattr(os, name, guard_unary(real))
    for name in ("rename", "replace", "link", "symlink"):
        real = getattr(os, name, None)
        if callable(real):
            setattr(os, name, guard_binary(real))

    for name in ("copy", "copy2", "copyfile", "copytree", "move"):
        real = getattr(shutil, name, None)
        if callable(real):
            setattr(shutil, name, guard_binary(real))
    shutil.rmtree = guard_unary(shutil.rmtree)

    def no_process(*args: Any, **kwargs: Any) -> Any:
        _deny("child process refused")

    subprocess.Popen = no_process
    subprocess.run = no_process
    subprocess.call = no_process
    subprocess.check_call = no_process
    subprocess.check_output = no_process
    os.system = no_process

    def no_network(*args: Any, **kwargs: Any) -> Any:
        _deny("network access refused")

    socket.socket = no_network
    socket.create_connection = no_network


def _safe_target(repo: Path, relative: str) -> Path:
    text = str(relative or "").replace("\\", "/")
    if not text or text.startswith("/") or ":" in text:
        raise ValueError("unsafe target path")
    if any(part in {"", ".", ".."} for part in text.split("/")):
        raise ValueError("unsafe target path")
    target = (repo / text).resolve()
    target.relative_to(repo)
    if not target.is_file() or target.suffix.lower() != ".py":
        raise ValueError("target is not a Python source file")
    return target


def _load_function(repo: Path, target: Path, symbol: str) -> Callable[..., Any]:
    if not str(symbol or "").isidentifier():
        raise ValueError("target symbol is not a simple identifier")
    module_name = f"_cattus_defect_probe_{hashlib.sha256(str(target).encode()).hexdigest()[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, target)
    if spec is None or spec.loader is None:
        raise ImportError("target module loader is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(repo))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(repo))
        except ValueError:
            pass
    function = getattr(module, symbol, None)
    if not callable(function):
        raise TypeError("target symbol is not callable")
    return function


def _run_python_function(payload: dict[str, Any], repo: Path, target: Path) -> dict[str, Any]:
    target_binding = payload.get("target") or {}
    inputs = payload.get("structured_input") or {}
    args = inputs.get("args")
    kwargs = inputs.get("kwargs")
    if not isinstance(args, list) or not isinstance(kwargs, dict):
        raise ValueError("structured input must contain JSON args and kwargs")
    function = _load_function(repo, target, str(target_binding.get("symbol") or ""))
    # INDENT.RUNTIME.1 — kwargs is generic transport a target's real signature
    # may or may not accept: the same indentation-style contract can be built
    # against core/code_dna.py::_classify_indent (language-aware) or against
    # an arbitrary target CONTROL localized in a real user's own repository
    # (not language-aware). Checked via signature binding, never a bare
    # call-and-catch, so a TypeError the target's own logic raises is never
    # mistaken for an unsupported keyword and silently retried.
    if kwargs:
        try:
            inspect.signature(function).bind(*args, **kwargs)
        except TypeError:
            kwargs = {}
    observed = function(*args, **kwargs)
    # The parent accepts only JSON-structured observations.
    json.dumps(observed, ensure_ascii=False)
    return {"status": "completed", "observed": observed}


def _run_existing_pytest(payload: dict[str, Any], repo: Path, pytest: Any) -> dict[str, Any]:
    selector = str(payload.get("test_selector") or "")
    # The parent already validates the grammar and source binding.  Repeating
    # the narrow argv here makes pytest collection explicit and cache-free.
    sys.path.insert(0, str(repo))
    try:
        exit_code = int(
            pytest.main(
                [
                    selector,
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--tb=short",
                    f"--rootdir={repo}",
                    f"--confcutdir={repo}",
                ]
            )
        )
    finally:
        try:
            sys.path.remove(str(repo))
        except ValueError:
            pass
    return {"status": "completed", "test_exit_code": exit_code}


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main() -> int:
    try:
        payload = json.loads(os.environ.get(_WORKER_ENV, ""))
        if not isinstance(payload, dict):
            raise ValueError("probe payload must be an object")
        repo = Path(str(payload.get("repo_path") or "")).resolve()
        target_binding = payload.get("target") or {}
        target = _safe_target(repo, str(target_binding.get("file") or ""))
        before = _sha256(target)
        # Pytest's own initialization imports asyncio/ssl, which subclasses
        # socket.socket.  Load the framework before replacing connection
        # constructors; collection and the test still run under the guards.
        pytest_module = None
        if payload.get("invocation_kind") == "existing_pytest":
            import pytest as pytest_module
            import ssl  # noqa: F401 - initialize socket subclasses before guards
            import asyncio  # noqa: F401 - initialize Popen subclasses before guards
        _install_side_effect_guards(repo)

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            if payload.get("invocation_kind") == "python_pure_function":
                result = _run_python_function(payload, repo, target)
            elif payload.get("invocation_kind") == "existing_pytest":
                result = _run_existing_pytest(payload, repo, pytest_module)
            else:
                raise ValueError("unsupported invocation kind")

        if result.get("test_exit_code") not in {None, 0, 1}:
            result["tool_diagnostic"] = (
                captured_out.getvalue() + captured_err.getvalue()
            )[-2000:]

        after = _sha256(target)
        if before != after:
            _emit({"status": "source_changed_during_probe", "source_sha256": after})
            return 0
        result["source_sha256"] = after
        _emit(result)
        return 0
    except SideEffectRefused:
        _emit({"status": "side_effect_refused"})
        return 0
    except Exception as exc:  # noqa: BLE001 - isolated tool failure is data
        _emit({"status": "tool_failure", "error_kind": type(exc).__name__})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
