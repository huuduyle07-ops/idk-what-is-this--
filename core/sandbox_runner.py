"""Phase 7.3 — Temp-Clone Sandbox Runner.

Centralised primitive for running a validation command against a *copy* of a
repo. Not a full security sandbox — there is no OS-level isolation; this layer
protects the real repository from accidental mutations and gives every caller
the same default safeties:

* path-resolved ``repo_path``,
* copy-tree exclusions for noisy/dangerous folders,
* command allowlist (validation tools only) + shell-metachar block,
* environment scrub (KEY/TOKEN/SECRET/PASSWORD/CREDENTIAL stripped unless
  explicitly allow-listed),
* hard timeout with best-effort tree kill,
* stdout/stderr cap that preserves head + tail,
* artifact log under ``<repo>/.agent/sandbox_runs/<id>/`` with ``run.json``
  + ``stdout.txt`` + ``stderr.txt``,
* changed-file detection by pre/post hash snapshot of the temp clone,
* cleanup with Windows-friendly retry, with ``keep_temp`` opt-out.

This module is read-only with respect to the real repo (it writes only to the
artifact directory). It never calls a model, never runs the benchmark runner,
never applies a patch, never seeds a lesson, and never promotes memory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Folders we never want copied into the temp clone. Mirrors the existing
# patterns in core/worker_runs.py and core/sleeping_consultant.py so callers
# migrating to this primitive see identical exclusions.
#
# ``.tmp`` / ``tmp`` / ``temp`` / ``.pytest-tmp`` were added in Phase 7.3a's
# Windows fix: pytest leaves locked file handles inside ``.tmp`` between the
# time a test finishes and the OS releases the handle, which made
# ``shutil.copytree`` raise ``PermissionError`` (``WinError 5``) on the
# ``docker_ubuntu`` smoke. These folders are never needed by a validation
# command, so dropping them from the staging copy is both safe and consistent
# with the existing exclusions for ``build`` / ``dist`` / ``__pycache__``.
DEFAULT_COPY_IGNORE: tuple[str, ...] = (
    ".git",
    ".agent",
    "node_modules",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".pytest-tmp",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tmp",
    "tmp",
    "temp",
)

# Tools that may appear as the first token of a validation command. Anything
# else is refused before the subprocess starts.
DEFAULT_ALLOWED_TOOLS: tuple[str, ...] = (
    "python",
    "python3",
    "py",
    "node",
    "npm",
    "npx",
    "go",
    "cargo",
    "rustc",
    "g++",
    "gcc",
    "make",
    "pytest",
    "echo",
)

# Shells / interpreters we refuse outright even if a caller adds them to
# ``allowed_commands`` — they make the metachar block meaningless.
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

# Always-block substrings — command substitution / chained execution. These
# have no legitimate use in a validation command even inside quotes, so the
# check is unconditional.
UNCONDITIONAL_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "$(", "`", "&&", "||",
)

# Quote-aware metachars — they can appear legitimately inside a quoted Python
# expression (``python -c "import os; print(1)"``) so we only refuse them
# when they show up *outside* a quoted region.
FORBIDDEN_METACHAR_CHARS: tuple[str, ...] = (
    "&", ";", "|", ">", "<",
)

# Kept for backward compatibility with callers / tests that imported the old
# name; populated to the union of the two stricter sets above.
FORBIDDEN_METACHAR_SUBSTRINGS: tuple[str, ...] = UNCONDITIONAL_FORBIDDEN_SUBSTRINGS

# Env var name fragments that mark the value as a secret. Stripped from the
# subprocess env unless the name is in ``env_allowlist``.
SECRET_NAME_FRAGMENTS: tuple[str, ...] = (
    "KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL",
)

# Default per-stream cap. Callers may override per-call with
# ``max_output_chars``; we always preserve head + tail when truncating.
DEFAULT_MAX_OUTPUT_CHARS = 20_000
DEFAULT_TIMEOUT_SEC = 60

# Path under the *real* repo where artifacts land.
SANDBOX_RUNS_SUBDIR = Path(".agent") / "sandbox_runs"

# Label sanitiser: only letters, digits, dash, underscore. Any other run of
# characters is collapsed to a single underscore so artifact dirs stay safe.
_LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")
_MAX_LABEL_LEN = 60


@dataclass
class SandboxRunResult:
    """Structured result returned by :func:`run_in_temp_clone`.

    Fields match the Phase 7.3 spec exactly so callers can ``asdict(result)``
    or ``result.as_dict()`` for JSON serialisation.
    """

    ok: bool = False
    exit_code: int | None = None
    timed_out: bool = False
    blocked: bool = False
    block_reason: str = ""
    command: str = ""
    cwd: str = ""
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    elapsed_sec: float = 0.0
    temp_path: str = ""
    cleanup_ok: bool = False
    artifact_dir: str = ""
    changed_files: list[str] = field(default_factory=list)
    created_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers — validation, snapshot, env, output capping
# ---------------------------------------------------------------------------


def _sanitize_label(label: str | None) -> str:
    raw = (label or "").strip()
    cleaned = _LABEL_SAFE_RE.sub("_", raw).strip("._-")
    if not cleaned:
        cleaned = "run"
    return cleaned[:_MAX_LABEL_LEN]


def _tool_basename(token: str) -> str:
    name = Path(token).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def _scan_unquoted_metachars(text: str) -> str | None:
    """Return the first single-character forbidden metachar found *outside*
    a quoted region, or ``None`` if the command is clean.

    Shell metacharacters like ``;`` and ``|`` are only dangerous when the
    shell sees them — inside a quoted argument (e.g.
    ``python -c "import os; print(1)"``) they are literal characters that
    subprocess passes through unchanged. Command-substitution patterns
    (``$(...)``, backticks, ``&&``, ``||``) are flagged earlier by the
    unconditional check.
    """
    in_single = False
    in_double = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_single:
            if ch == "'":
                in_single = False
        elif in_double:
            if ch == '"' and not (i > 0 and text[i - 1] == "\\"):
                in_double = False
        else:
            if ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif ch in FORBIDDEN_METACHAR_CHARS:
                return ch
        i += 1
    return None


def _validate_command(
    command: str,
    *,
    allowed_commands: Iterable[str] | None,
) -> tuple[list[str], str | None]:
    """Return (argv, block_reason). On any failure ``argv`` is empty."""
    text = (command or "").strip()
    if not text:
        return [], "command is empty"

    for sub in UNCONDITIONAL_FORBIDDEN_SUBSTRINGS:
        if sub in text:
            return [], f"command contains forbidden token {sub!r}"

    unquoted_bad = _scan_unquoted_metachars(text)
    if unquoted_bad is not None:
        return [], f"command contains forbidden character {unquoted_bad!r}"

    # We deliberately parse with POSIX rules on every platform so that the
    # same command string ("python -c \"print(1)\"") behaves identically on
    # Windows and Linux. The Windows-cmd default (posix=False) would keep
    # surrounding quotes attached to argv entries, which Python then
    # mis-interprets as a string literal expression instead of a statement.
    try:
        argv = shlex.split(text, posix=True)
    except ValueError as exc:
        return [], f"could not parse command: {exc}"
    if not argv:
        return [], "command parsed to empty argv"

    tool = _tool_basename(argv[0])
    if tool in BLOCKED_INTERPRETERS:
        return [], f"command interpreter is blocked: {argv[0]}"

    extra = {
        _tool_basename(item) for item in (allowed_commands or ())
    } - {""}
    allowed = set(DEFAULT_ALLOWED_TOOLS) | extra
    if tool not in allowed:
        return [], f"command tool not in allowlist: {argv[0]}"

    return argv, None


def _resolve_repo(repo_path: str | Path) -> Path:
    if not repo_path:
        raise ValueError("repo_path is required")
    repo = Path(repo_path).expanduser().resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"repo_path is not a directory: {repo}")
    return repo


def _env_is_secret(name: str) -> bool:
    upper = name.upper()
    return any(fragment in upper for fragment in SECRET_NAME_FRAGMENTS)


def _build_env(env_allowlist: Iterable[str] | None) -> dict[str, str]:
    allow = {name.strip() for name in (env_allowlist or ()) if name and name.strip()}
    env: dict[str, str] = {}
    for name, value in os.environ.items():
        if _env_is_secret(name) and name not in allow:
            continue
        env[name] = value
    # Ensure UTF-8 friendly Python child processes.
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _snapshot_tree(root: Path) -> dict[str, str]:
    """Return ``{relpath_posix: sha256-of-file}``.

    Directories and symlinks pointing outside ``root`` are skipped silently.
    On any per-file IO error the file is recorded with a sentinel so a later
    successful read counts as a change.
    """
    snapshot: dict[str, str] = {}
    if not root.is_dir():
        return snapshot
    root_resolved = root.resolve()
    for current_root, dirs, files in os.walk(root):
        dirs.sort()
        files.sort()
        for fname in files:
            fpath = Path(current_root) / fname
            try:
                resolved = fpath.resolve()
                resolved.relative_to(root_resolved)
            except (OSError, ValueError):
                continue
            try:
                with open(fpath, "rb") as handle:
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: handle.read(65_536), b""):
                        digest.update(chunk)
                    snapshot[
                        fpath.resolve().relative_to(root_resolved).as_posix()
                    ] = digest.hexdigest()
            except OSError:
                snapshot[
                    fpath.resolve().relative_to(root_resolved).as_posix()
                ] = "io_error"
    return snapshot


def _diff_snapshots(
    before: dict[str, str], after: dict[str, str]
) -> list[str]:
    keys = set(before) | set(after)
    changed: list[str] = []
    for key in sorted(keys):
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def _cap_text(text: str, cap: int) -> tuple[str, bool]:
    if cap <= 0 or len(text) <= cap:
        return text, False
    if cap < 200:
        return text[:cap], True
    keep_each = max(1, (cap - 80) // 2)
    head = text[:keep_each]
    tail = text[-keep_each:]
    removed = len(text) - len(head) - len(tail)
    return f"{head}\n...[truncated {removed} chars]...\n{tail}", True


def _safe_rmtree(path: Path, retries: int = 6) -> bool:
    """Windows occasionally holds file handles open just after a subprocess
    exits. Retry with a short backoff before giving up."""
    if not path.exists():
        return True
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            shutil.rmtree(path, ignore_errors=False)
            return True
        except (OSError, PermissionError) as exc:
            last_error = exc
            time.sleep(0.1 * (attempt + 1))
    try:
        shutil.rmtree(path, ignore_errors=True)
        return not path.exists()
    except Exception:
        return False
    finally:
        if last_error is not None:
            # Best-effort: callers can still see the path in the result.
            pass


def _kill_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Best-effort process-tree kill. Posix uses ``killpg``; Windows uses
    ``taskkill /T`` when available, else falls back to ``Popen.kill``."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            taskkill = shutil.which("taskkill")
            if taskkill:
                subprocess.run(
                    [taskkill, "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    check=False,
                    timeout=5,
                )
                return
        else:
            try:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGKILL)
                return
            except (OSError, AttributeError):
                pass
    except Exception:
        pass
    try:
        process.kill()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------


def _run_subprocess(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_sec: int,
) -> tuple[int | None, str, str, bool, float]:
    """Run ``argv`` and return ``(exit_code, stdout, stderr, timed_out, elapsed_sec)``."""
    # Rebind ``python``-family tools to the interpreter that's currently
    # running so the sandbox doesn't drift onto a different Python.
    run_argv = list(argv)
    if _tool_basename(run_argv[0]) in {"python", "python3", "py"}:
        run_argv[0] = sys.executable

    popen_kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        popen_kwargs["start_new_session"] = True

    started = time.time()
    try:
        process = subprocess.Popen(run_argv, **popen_kwargs)
    except FileNotFoundError as exc:
        # Tool passed the allowlist gate but isn't installed on this host.
        # Surface it as a non-zero result instead of crashing the runner.
        elapsed = round(time.time() - started, 4)
        return None, "", f"executable not found: {exc}", False, elapsed
    except OSError as exc:
        elapsed = round(time.time() - started, 4)
        return None, "", f"failed to start subprocess: {exc}", False, elapsed

    timed_out = False
    try:
        stdout_b, stderr_b = process.communicate(timeout=max(1, int(timeout_sec)))
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        _kill_process_tree(process)
        try:
            stdout_b, stderr_b = process.communicate(timeout=5)
        except Exception:
            stdout_b = exc.stdout if isinstance(exc.stdout, bytes) else b""
            stderr_b = exc.stderr if isinstance(exc.stderr, bytes) else b""
    elapsed = round(time.time() - started, 4)
    exit_code = process.returncode
    stdout = (stdout_b or b"").decode("utf-8", errors="replace")
    stderr = (stderr_b or b"").decode("utf-8", errors="replace")
    return exit_code, stdout, stderr, timed_out, elapsed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _ignore_factory(extra: Iterable[str] | None) -> Any:
    names = set(DEFAULT_COPY_IGNORE)
    names.update(extra or ())
    return shutil.ignore_patterns(*sorted(names))


def _write_artifacts(
    artifact_dir: Path,
    result: SandboxRunResult,
    stdout_full: str,
    stderr_full: str,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "stdout.txt").write_text(stdout_full, encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(stderr_full, encoding="utf-8")
    (artifact_dir / "run.json").write_text(
        json.dumps(result.as_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_in_temp_clone(
    repo_path: str | Path,
    command: str,
    *,
    allowed_commands: Iterable[str] | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    env_allowlist: Iterable[str] | None = None,
    copy_ignore: Iterable[str] | None = None,
    run_label: str | None = None,
    keep_temp: bool = False,
) -> SandboxRunResult:
    """Run ``command`` against a temp copy of ``repo_path``.

    Returns a :class:`SandboxRunResult` regardless of outcome (no exceptions
    bubble up for normal validation failures). Raises :class:`ValueError` or
    :class:`FileNotFoundError` only for caller-supplied repo-path errors,
    matching the existing ``validate_imported_worker_proposal`` pattern.
    """
    repo = _resolve_repo(repo_path)
    label = _sanitize_label(run_label)
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%S")
    run_id = f"{timestamp}_{label}"

    result = SandboxRunResult(
        command=command or "",
        created_at=now.isoformat(),
    )

    # 1. Allowlist + metachar block --------------------------------------
    argv, block_reason = _validate_command(
        command, allowed_commands=allowed_commands
    )
    if block_reason:
        result.blocked = True
        result.block_reason = block_reason
        # Still emit an artifact so callers see why the run refused.
        artifact_dir = repo / SANDBOX_RUNS_SUBDIR / run_id
        result.artifact_dir = str(artifact_dir)
        _write_artifacts(artifact_dir, result, "", "")
        return result

    # 2. Build temp clone -------------------------------------------------
    temp_root = Path(tempfile.mkdtemp(prefix=f"sandbox-{label}-"))
    temp_clone = temp_root / "repo"
    try:
        shutil.copytree(repo, temp_clone, ignore=_ignore_factory(copy_ignore))
    except Exception as exc:
        result.blocked = True
        result.block_reason = f"copytree failed: {type(exc).__name__}: {exc}"
        # Best-effort cleanup.
        result.cleanup_ok = _safe_rmtree(temp_root)
        artifact_dir = repo / SANDBOX_RUNS_SUBDIR / run_id
        result.artifact_dir = str(artifact_dir)
        _write_artifacts(artifact_dir, result, "", "")
        return result

    result.cwd = str(temp_clone)
    result.temp_path = str(temp_root)

    # 3. Snapshot before run ---------------------------------------------
    before = _snapshot_tree(temp_clone)

    # 4. Run subprocess ---------------------------------------------------
    env = _build_env(env_allowlist)
    exit_code, stdout_full, stderr_full, timed_out, elapsed = _run_subprocess(
        argv,
        cwd=temp_clone,
        env=env,
        timeout_sec=timeout_sec,
    )

    # 5. Snapshot after run ----------------------------------------------
    after = _snapshot_tree(temp_clone)
    changed = _diff_snapshots(before, after)

    # 6. Cap output -------------------------------------------------------
    stdout_capped, stdout_truncated = _cap_text(stdout_full, max_output_chars)
    stderr_capped, stderr_truncated = _cap_text(stderr_full, max_output_chars)

    result.exit_code = exit_code
    result.timed_out = timed_out
    result.ok = (not timed_out) and exit_code == 0
    result.stdout = stdout_capped
    result.stderr = stderr_capped
    result.output_truncated = stdout_truncated or stderr_truncated
    result.elapsed_sec = elapsed
    result.changed_files = changed

    # 7. Persist artifacts before touching the temp dir ------------------
    artifact_dir = repo / SANDBOX_RUNS_SUBDIR / run_id
    result.artifact_dir = str(artifact_dir)

    # 8. Cleanup ----------------------------------------------------------
    if keep_temp:
        # Caller will inspect / remove the clone themselves.
        result.cleanup_ok = True
    else:
        result.cleanup_ok = _safe_rmtree(temp_root)
        if result.cleanup_ok:
            result.temp_path = ""  # nothing left on disk

    _write_artifacts(artifact_dir, result, stdout_full, stderr_full)
    return result


# ---------------------------------------------------------------------------
# Phase 7.3a — Optional Docker / Ubuntu backend
#
# The Docker backend layers on top of the temp-clone runner. It still copies
# the repo into a host-side staging dir (so changed_files / cleanup / artifact
# logging keep working), then mounts ONLY that staging dir into a Docker
# container and runs the same allowlisted command there.
#
# This is defense-in-depth, not perfect OS-level isolation. Specifically:
#   * The default network is ``--network none``.
#   * No ``--privileged``, no docker.sock mount, no host-home mount.
#   * Memory + CPU limits are applied (callable can override).
#   * Secrets are stripped from the environment by default; only env vars
#     present in ``env_allowlist`` (and harmless ``PYTHON*`` knobs) cross
#     into the container.
#   * The temp staging path — not the real repo — is what the container sees.
#   * If ``docker`` is not on PATH, the call returns a friendly blocked
#     result instead of raising.
# ---------------------------------------------------------------------------

DEFAULT_DOCKER_IMAGE = "python:3.12-slim"
DOCKER_CONTAINER_WORKDIR = "/work"

# Toolchain → recommended Docker image for the ``docker_ubuntu`` backend.
#
# The health probe iterates this list to report which language images the
# user has pulled locally. None of these are *required* — ``DEFAULT_DOCKER_IMAGE``
# alone covers ``python -m pytest``-style commands. Callers running a Node /
# Go / Rust / C-toolchain command should pass the matching image explicitly
# via ``run_in_sandbox(..., docker_image=...)``.
#
# Keys are tools from ``DEFAULT_ALLOWED_TOOLS``; values are reasonably-small
# official images. Users who prefer different tags can override at call time —
# this constant only drives the health-panel "is it pulled?" hint.
SANDBOX_LANGUAGE_IMAGES: tuple[tuple[str, str], ...] = (
    ("python",      "python:3.12-slim"),
    ("node / npm",  "node:20-slim"),
    ("go",          "golang:1.22-alpine"),
    ("rust",        "rust:1.80-slim"),
    ("gcc / g++",   "gcc:13"),
)


def _is_docker_available() -> tuple[bool, str]:
    """Return ``(available, reason)``. ``reason`` is empty when available."""
    docker = shutil.which("docker")
    if not docker:
        return False, "docker binary not on PATH"
    return True, ""


def _build_docker_command(
    *,
    image: str,
    mount_src: Path,
    argv: list[str],
    container_workdir: str = DOCKER_CONTAINER_WORKDIR,
    network: bool = False,
    memory: str = "1g",
    cpus: str = "1.0",
    env: dict[str, str] | None = None,
    container_name: str | None = None,
    use_posix_user: bool = True,
) -> list[str]:
    """Return the ``docker run`` argv we would invoke for the given context.

    Pure function — no subprocess is spawned here so tests can assert the
    exact security flags without needing Docker installed.
    """
    cmd: list[str] = ["docker", "run", "--rm"]
    if container_name:
        cmd.extend(["--name", container_name])
    cmd.extend(["-v", f"{Path(mount_src).as_posix()}:{container_workdir}"])
    cmd.extend(["-w", container_workdir])
    cmd.extend(["--network", "none" if not network else "bridge"])
    cmd.extend(["--memory", str(memory)])
    cmd.extend(["--cpus", str(cpus)])
    # Defense-in-depth: read-only root FS keeps stray writes out of the
    # container layer. We still allow writes to the mounted workdir.
    cmd.append("--read-only")
    cmd.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
    # Drop all capabilities by default; the allowlisted Python/Node toolchain
    # needs none of them.
    cmd.extend(["--cap-drop", "ALL"])
    cmd.extend(["--security-opt", "no-new-privileges"])
    if use_posix_user and os.name == "posix":
        try:
            uid = os.getuid()  # type: ignore[attr-defined]
            gid = os.getgid()  # type: ignore[attr-defined]
            cmd.extend(["--user", f"{uid}:{gid}"])
        except AttributeError:
            pass
    for name in sorted((env or {}).keys()):
        cmd.extend(["-e", f"{name}={env[name]}"])
    cmd.append(image)
    cmd.extend(argv)
    return cmd


def _docker_env_subset(
    full_env: dict[str, str],
    env_allowlist: Iterable[str] | None,
) -> dict[str, str]:
    """Choose which env vars cross into the container.

    Always-allowed inside the container: the ``PYTHON*`` knobs we set on the
    host so child Python processes behave consistently. Anything else must be
    explicitly listed in ``env_allowlist``. Secrets that survived
    :func:`_build_env` (because the caller allow-listed them) still propagate.
    """
    allow_names = {name.strip() for name in (env_allowlist or ()) if name and name.strip()}
    out: dict[str, str] = {}
    for name, value in full_env.items():
        if name.startswith("PYTHON") or name in allow_names:
            out[name] = value
    return out


def _docker_kill_container(name: str) -> None:
    """Best-effort cleanup if a timed-out container is still alive."""
    docker = shutil.which("docker")
    if not docker:
        return
    try:
        subprocess.run(
            [docker, "kill", name],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except Exception:
        pass


def _run_docker_subprocess(
    docker_argv: list[str],
    *,
    timeout_sec: int,
    container_name: str,
) -> tuple[int | None, str, str, bool, float]:
    """Run ``docker_argv`` and return the same tuple shape as
    :func:`_run_subprocess`. On timeout we also send ``docker kill`` so the
    container doesn't outlive the CLI process."""
    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        popen_kwargs["start_new_session"] = True

    started = time.time()
    try:
        process = subprocess.Popen(docker_argv, **popen_kwargs)
    except FileNotFoundError as exc:
        elapsed = round(time.time() - started, 4)
        return None, "", f"docker executable not found: {exc}", False, elapsed
    except OSError as exc:
        elapsed = round(time.time() - started, 4)
        return None, "", f"failed to start docker: {exc}", False, elapsed

    timed_out = False
    try:
        stdout_b, stderr_b = process.communicate(timeout=max(1, int(timeout_sec)))
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        _docker_kill_container(container_name)
        _kill_process_tree(process)
        try:
            stdout_b, stderr_b = process.communicate(timeout=5)
        except Exception:
            stdout_b = exc.stdout if isinstance(exc.stdout, bytes) else b""
            stderr_b = exc.stderr if isinstance(exc.stderr, bytes) else b""

    elapsed = round(time.time() - started, 4)
    exit_code = process.returncode
    stdout = (stdout_b or b"").decode("utf-8", errors="replace")
    stderr = (stderr_b or b"").decode("utf-8", errors="replace")
    return exit_code, stdout, stderr, timed_out, elapsed


def _run_in_docker_ubuntu(
    repo_path: str | Path,
    command: str,
    *,
    allowed_commands: Iterable[str] | None,
    timeout_sec: int,
    max_output_chars: int,
    env_allowlist: Iterable[str] | None,
    copy_ignore: Iterable[str] | None,
    run_label: str | None,
    keep_temp: bool,
    docker_image: str | None,
    docker_network: bool,
    docker_memory: str,
    docker_cpus: str,
) -> SandboxRunResult:
    repo = _resolve_repo(repo_path)
    label = _sanitize_label(run_label)
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%S")
    run_id = f"{timestamp}_{label}"
    artifact_dir = repo / SANDBOX_RUNS_SUBDIR / run_id

    result = SandboxRunResult(
        command=command or "",
        created_at=now.isoformat(),
        artifact_dir=str(artifact_dir),
    )

    # 1. Docker availability ---------------------------------------------
    available, reason = _is_docker_available()
    if not available:
        result.blocked = True
        result.block_reason = f"docker backend unavailable: {reason}"
        _write_artifacts(artifact_dir, result, "", "")
        return result

    # 2. Command allowlist + metachar gate -------------------------------
    argv, block_reason = _validate_command(
        command, allowed_commands=allowed_commands
    )
    if block_reason:
        result.blocked = True
        result.block_reason = block_reason
        _write_artifacts(artifact_dir, result, "", "")
        return result

    # 3. Staging copy ----------------------------------------------------
    temp_root = Path(tempfile.mkdtemp(prefix=f"sandbox-docker-{label}-"))
    staging = temp_root / "repo"
    try:
        shutil.copytree(repo, staging, ignore=_ignore_factory(copy_ignore))
    except Exception as exc:
        result.blocked = True
        result.block_reason = f"copytree failed: {type(exc).__name__}: {exc}"
        result.cleanup_ok = _safe_rmtree(temp_root)
        _write_artifacts(artifact_dir, result, "", "")
        return result

    # The reported cwd points at the host-side staging dir so changed-file
    # diffing keeps working. Inside the container the workdir is /work.
    result.cwd = str(staging)
    result.temp_path = str(temp_root)

    # 4. Snapshot before run ---------------------------------------------
    before = _snapshot_tree(staging)

    # 5. Env filtering ----------------------------------------------------
    full_env = _build_env(env_allowlist)
    docker_env = _docker_env_subset(full_env, env_allowlist)

    # 6. Build docker argv -----------------------------------------------
    container_name = f"sandbox-{label}-{int(time.time() * 1000)}"
    docker_argv = _build_docker_command(
        image=(docker_image or DEFAULT_DOCKER_IMAGE),
        mount_src=staging,
        argv=argv,
        network=bool(docker_network),
        memory=str(docker_memory),
        cpus=str(docker_cpus),
        env=docker_env,
        container_name=container_name,
    )

    # 7. Run docker -------------------------------------------------------
    exit_code, stdout_full, stderr_full, timed_out, elapsed = _run_docker_subprocess(
        docker_argv,
        timeout_sec=timeout_sec,
        container_name=container_name,
    )

    # 8. Snapshot after run ----------------------------------------------
    after = _snapshot_tree(staging)
    changed = _diff_snapshots(before, after)

    # 9. Cap output -------------------------------------------------------
    stdout_capped, stdout_trunc = _cap_text(stdout_full, max_output_chars)
    stderr_capped, stderr_trunc = _cap_text(stderr_full, max_output_chars)

    result.exit_code = exit_code
    result.timed_out = timed_out
    result.ok = (not timed_out) and exit_code == 0
    result.stdout = stdout_capped
    result.stderr = stderr_capped
    result.output_truncated = stdout_trunc or stderr_trunc
    result.elapsed_sec = elapsed
    result.changed_files = changed

    # 10. Cleanup ---------------------------------------------------------
    if keep_temp:
        result.cleanup_ok = True
    else:
        result.cleanup_ok = _safe_rmtree(temp_root)
        if result.cleanup_ok:
            result.temp_path = ""

    _write_artifacts(artifact_dir, result, stdout_full, stderr_full)
    return result


# ---------------------------------------------------------------------------
# High-level dispatcher
# ---------------------------------------------------------------------------


SUPPORTED_BACKENDS: tuple[str, ...] = ("temp_clone", "docker_ubuntu")


def run_in_sandbox(
    repo_path: str | Path,
    command: str,
    *,
    backend: str = "temp_clone",
    allowed_commands: Iterable[str] | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    env_allowlist: Iterable[str] | None = None,
    copy_ignore: Iterable[str] | None = None,
    run_label: str | None = None,
    keep_temp: bool = False,
    docker_image: str | None = None,
    docker_network: bool = False,
    docker_memory: str = "1g",
    docker_cpus: str = "1.0",
) -> SandboxRunResult:
    """Dispatch ``command`` to the requested sandbox backend.

    Backends:

    * ``"temp_clone"`` (default) — runs the command in a host-side temp copy
      via :func:`run_in_temp_clone`. Behaviour is unchanged from Phase 7.3.
    * ``"docker_ubuntu"`` — runs the command in an unprivileged, network-less
      Docker container mounted only at the staging copy. Defense-in-depth,
      not perfect OS-level isolation.

    Unknown backends return a friendly ``blocked`` :class:`SandboxRunResult`
    instead of raising, so callers don't need to wrap calls in try/except.
    """
    if backend == "temp_clone":
        return run_in_temp_clone(
            repo_path,
            command,
            allowed_commands=allowed_commands,
            timeout_sec=timeout_sec,
            max_output_chars=max_output_chars,
            env_allowlist=env_allowlist,
            copy_ignore=copy_ignore,
            run_label=run_label,
            keep_temp=keep_temp,
        )

    if backend == "docker_ubuntu":
        return _run_in_docker_ubuntu(
            repo_path,
            command,
            allowed_commands=allowed_commands,
            timeout_sec=timeout_sec,
            max_output_chars=max_output_chars,
            env_allowlist=env_allowlist,
            copy_ignore=copy_ignore,
            run_label=run_label,
            keep_temp=keep_temp,
            docker_image=docker_image,
            docker_network=docker_network,
            docker_memory=docker_memory,
            docker_cpus=docker_cpus,
        )

    now = datetime.now(timezone.utc)
    result = SandboxRunResult(
        command=command or "",
        created_at=now.isoformat(),
        blocked=True,
        block_reason=(
            f"unknown backend: {backend!r} "
            f"(supported: {', '.join(SUPPORTED_BACKENDS)})"
        ),
    )
    return result

