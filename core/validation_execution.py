from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping


DEFAULT_ALLOWED_TOOLS: tuple[str, ...] = (
    "python",
    "python3",
    "py",
    "pytest",
    "node",
    "npm",
    "npx",
    "go",
    "cargo",
    "rustc",
    "g++",
    "gcc",
    "make",
    "dotnet",
)

BLOCKED_INTERPRETERS: tuple[str, ...] = (
    "powershell",
    "pwsh",
    "cmd",
    "bash",
    "sh",
    "zsh",
    "fish",
    "tcsh",
    "ksh",
    "csh",
)

DESTRUCTIVE_TOOLS: tuple[str, ...] = (
    "rm",
    "del",
    "erase",
    "rmdir",
    "rd",
    "remove-item",
    "format",
    "mkfs",
    "shutdown",
    "reboot",
)

ENV_DUMP_TOOLS: tuple[str, ...] = (
    "env",
    "printenv",
    "set",
)

SECRET_NAME_FRAGMENTS: tuple[str, ...] = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
)

SHELL_META_TOKENS: tuple[str, ...] = ("&&", "||", "$(", "`")
SHELL_META_CHARS: tuple[str, ...] = ("&", ";", "|", ">", "<")
MAX_TIMEOUT_SEC = 600


@dataclass(frozen=True)
class SafeValidationCommand:
    """A validation command safe enough for automation boundaries.

    The command is argv-style, never shell text. `timeout_sec` is required and
    bounded so an automated caller cannot start an unbounded child process.
    """

    command: list[str]
    cwd: str | Path
    timeout_sec: int | None
    env: Mapping[str, str] | None = None
    env_allowlist: Iterable[str] = field(default_factory=tuple)
    allowed_tools: Iterable[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class SafeValidationResult:
    ok: bool
    blocked: bool
    block_reason: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    command: list[str]
    cwd: str

    @property
    def output(self) -> str:
        return ((self.stdout or "") + (self.stderr or "")).strip()


def _blocked_result(
    command: SafeValidationCommand,
    reason: str,
) -> SafeValidationResult:
    return SafeValidationResult(
        ok=False,
        blocked=True,
        block_reason=reason,
        exit_code=None,
        stdout="",
        stderr="",
        timed_out=False,
        command=list(command.command or []),
        cwd=str(command.cwd or ""),
    )


def _tool_basename(token: str) -> str:
    name = Path(str(token)).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def _contains_shell_meta(arg: str) -> str:
    for token in SHELL_META_TOKENS:
        if token in arg:
            return token
    for char in SHELL_META_CHARS:
        if char in arg:
            return char
    return ""


def _env_is_secret(name: str) -> bool:
    upper = name.upper()
    return any(fragment in upper for fragment in SECRET_NAME_FRAGMENTS)


def _build_scrubbed_env(command: SafeValidationCommand) -> dict[str, str]:
    allow = {
        name.strip()
        for name in (command.env_allowlist or ())
        if isinstance(name, str) and name.strip()
    }
    env = dict(os.environ)
    if command.env:
        env.update({str(key): str(value) for key, value in command.env.items()})
    for name in list(env.keys()):
        if _env_is_secret(name) and name not in allow:
            env.pop(name, None)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def validate_safe_validation_command(command: SafeValidationCommand) -> str:
    """Return an unsafe reason, or an empty string when the command is safe."""

    if not isinstance(command.command, list) or not command.command:
        return "safe validation command must be a non-empty argv list"
    if not isinstance(command.timeout_sec, int) or isinstance(command.timeout_sec, bool):
        return "safe validation timeout must be an integer number of seconds"
    if command.timeout_sec <= 0:
        return "safe validation timeout must be greater than zero"
    if command.timeout_sec > MAX_TIMEOUT_SEC:
        return f"safe validation timeout exceeds maximum {MAX_TIMEOUT_SEC}s"

    try:
        cwd = Path(command.cwd).resolve()
    except (TypeError, OSError):
        return "safe validation cwd is invalid"
    if not cwd.is_dir():
        return f"safe validation cwd is not a directory: {command.cwd}"

    argv = command.command
    for arg in argv:
        if not isinstance(arg, str) or not arg.strip():
            return "safe validation argv entries must be non-empty strings"
        meta = _contains_shell_meta(arg)
        if meta:
            return f"safe validation rejects shell metacharacter {meta!r}"

    tool = _tool_basename(argv[0])
    if tool in ENV_DUMP_TOOLS:
        return f"safe validation rejects environment dumping tool: {argv[0]}"
    if tool in BLOCKED_INTERPRETERS:
        return f"safe validation rejects shell interpreter: {argv[0]}"
    if tool in DESTRUCTIVE_TOOLS:
        return f"safe validation rejects destructive command: {argv[0]}"
    if tool == "git":
        lowered = [arg.lower() for arg in argv[1:]]
        if "reset" in lowered and "--hard" in lowered:
            return "safe validation rejects destructive git reset --hard"
        if "clean" in lowered and any(arg.startswith("-") and "f" in arg for arg in lowered):
            return "safe validation rejects destructive git clean"

    if tool in {"python", "python3", "py"} and any(arg == "-c" for arg in argv[1:]):
        return "safe validation rejects arbitrary python -c execution"

    allowed = {
        _tool_basename(item)
        for item in (tuple(DEFAULT_ALLOWED_TOOLS) + tuple(command.allowed_tools or ()))
        if item
    }
    if tool not in allowed:
        return f"safe validation command tool not in allowlist: {argv[0]}"
    return ""


def parse_safe_validation_command(
    command_text: str,
    *,
    cwd: str | Path,
    timeout_sec: int,
    allowed_tools: Iterable[str] = (),
) -> tuple[SafeValidationCommand | None, str]:
    """Convert simple manual text into a safe argv command when possible."""

    text = (command_text or "").strip()
    if not text:
        return None, "validation command is empty"
    for token in SHELL_META_TOKENS:
        if token in text:
            return None, f"safe validation rejects shell metacharacter {token!r}"
    for char in SHELL_META_CHARS:
        if char in text:
            return None, f"safe validation rejects shell metacharacter {char!r}"
    try:
        argv = shlex.split(text, posix=True)
    except ValueError as exc:
        return None, f"safe validation could not parse command: {exc}"
    command = SafeValidationCommand(
        command=argv,
        cwd=cwd,
        timeout_sec=timeout_sec,
        allowed_tools=allowed_tools,
    )
    reason = validate_safe_validation_command(command)
    if reason:
        return None, reason
    return command, ""


def run_safe_validation_command(command: SafeValidationCommand) -> SafeValidationResult:
    reason = validate_safe_validation_command(command)
    if reason:
        return _blocked_result(command, reason)

    cwd = Path(command.cwd).resolve()
    argv = list(command.command)
    if _tool_basename(argv[0]) in {"python", "python3", "py"}:
        argv[0] = sys.executable

    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            shell=False,
            capture_output=True,
            text=True,
            timeout=command.timeout_sec,
            encoding="utf-8",
            errors="replace",
            env=_build_scrubbed_env(command),
        )
        return SafeValidationResult(
            ok=completed.returncode == 0,
            blocked=False,
            block_reason="",
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            timed_out=False,
            command=argv,
            cwd=str(cwd),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return SafeValidationResult(
            ok=False,
            blocked=False,
            block_reason="",
            exit_code=None,
            stdout=stdout,
            stderr=f"validation timeout after {command.timeout_sec}s\n{stderr}",
            timed_out=True,
            command=argv,
            cwd=str(cwd),
        )
    except OSError as exc:
        return SafeValidationResult(
            ok=False,
            blocked=False,
            block_reason="",
            exit_code=None,
            stdout="",
            stderr=f"safe validation execution error: {exc}",
            timed_out=False,
            command=argv,
            cwd=str(cwd),
        )
