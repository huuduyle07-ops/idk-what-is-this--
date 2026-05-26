"""Tests for Phase 7.3 — Temp-Clone Sandbox Runner.

Behaviour exercised here corresponds to the 14 spec test scenarios:

1.  Runs a safe command inside the temp clone.
2.  Real repo is unchanged when the command edits a file in the clone.
3.  Changed files inside the temp clone are reported.
4.  Shell-metacharacter abuse is blocked (default mode).
5.  Environment secrets are stripped by default.
6.  Explicitly allow-listed env vars survive the scrub.
7.  Timeout returns ``timed_out=true`` (and kills the child).
8.  stdout/stderr are capped and ``output_truncated=True``.
9.  Cleanup either succeeds or reports its status honestly.
10. ``keep_temp=True`` preserves the temp path.
11. ``copy_ignore`` excludes ``.agent`` / ``.git`` (and anything caller adds).
12. Path-traversal in ``run_label`` is sanitised; bad ``repo_path`` is refused.
13. Artifact ``run.json`` / ``stdout.txt`` / ``stderr.txt`` are written under
    ``<repo>/.agent/sandbox_runs/<id>/``.
14. The module never pulls in model / patch / lesson / benchmark-runner code.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from core import sandbox_runner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "real_repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('hello from main')\n", encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (repo / ".agent").mkdir()
    (repo / ".agent" / "notes.md").write_text("private agent state\n", encoding="utf-8")
    return repo


# ---------------------------------------------------------------------------
# 1. Safe command runs in temp clone
# ---------------------------------------------------------------------------


def test_safe_command_runs_in_temp_clone(real_repo: Path):
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "print(\'hello sandbox\')"',
        timeout_sec=30,
        run_label="safe-cmd",
    )

    assert result.ok is True
    assert result.exit_code == 0
    assert result.blocked is False
    assert result.timed_out is False
    assert "hello sandbox" in result.stdout
    # The reported cwd is the temp clone, not the real repo.
    assert real_repo.as_posix() not in Path(result.cwd).as_posix()
    assert Path(result.cwd).name == "repo"


# ---------------------------------------------------------------------------
# 2 & 3. Real repo unchanged; changed files in temp clone are reported
# ---------------------------------------------------------------------------


def test_changed_files_reported_and_real_repo_untouched(real_repo: Path):
    real_main_before = (real_repo / "main.py").read_text(encoding="utf-8")
    real_main_mtime = (real_repo / "main.py").stat().st_mtime

    program = (
        "import pathlib; "
        "pathlib.Path('main.py').write_text('print(\"mutated\")\\n', encoding='utf-8'); "
        "pathlib.Path('NEW_FILE.txt').write_text('hello', encoding='utf-8')"
    )
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        f'python -c "{program}"',
        timeout_sec=30,
        run_label="mutate",
        keep_temp=True,  # so the test can verify the clone was actually mutated
    )

    assert result.ok is True
    # The clone reports both modified main.py and the new file.
    assert "main.py" in result.changed_files
    assert "NEW_FILE.txt" in result.changed_files

    # Real repo is untouched.
    assert (real_repo / "main.py").read_text(encoding="utf-8") == real_main_before
    assert (real_repo / "main.py").stat().st_mtime == real_main_mtime
    assert not (real_repo / "NEW_FILE.txt").exists()

    # Clean up the kept temp dir so the test doesn't litter the temp filesystem.
    if result.temp_path and Path(result.temp_path).exists():
        sandbox_runner._safe_rmtree(Path(result.temp_path))


# ---------------------------------------------------------------------------
# 4. Shell-metacharacter abuse is blocked in default mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_command",
    [
        "python -c 'print(1)' && rm -rf /",
        "python -c 'print(1)' || echo nope",
        "python -c 'print(1)'; echo chained",
        "python -c 'print(1)' | cat",
        "python -c 'print(1)' > out.txt",
        "python -c \"$(echo evil)\"",
        "powershell -Command Get-ChildItem",
        "bash -lc 'echo bad'",
    ],
)
def test_dangerous_commands_are_blocked(real_repo: Path, bad_command: str):
    result = sandbox_runner.run_in_temp_clone(
        real_repo, bad_command, run_label="block"
    )

    assert result.blocked is True
    assert result.ok is False
    assert result.block_reason
    # The block happens before any subprocess starts so there's no stdout to show.
    assert result.stdout == ""


def test_unknown_tool_is_blocked(real_repo: Path):
    result = sandbox_runner.run_in_temp_clone(
        real_repo, "rmdir something", run_label="block"
    )
    assert result.blocked is True
    assert "allowlist" in result.block_reason


def test_caller_can_extend_allowlist(real_repo: Path):
    """``allowed_commands`` should let a caller add a custom tool past the
    default allowlist gate."""
    # ``ruff`` (or any other tool name not in DEFAULT_ALLOWED_TOOLS) is fine
    # here — we only need the gate decision; subprocess may fail to find it
    # afterwards and that's not what we're asserting.
    result_default = sandbox_runner.run_in_temp_clone(
        real_repo,
        "ruff check .",
        run_label="custom-block",
    )
    assert result_default.blocked is True
    assert "allowlist" in result_default.block_reason

    result_allowed = sandbox_runner.run_in_temp_clone(
        real_repo,
        "ruff check .",
        allowed_commands=["ruff"],
        timeout_sec=10,
        run_label="custom-allow",
    )
    # The gate decision is "not blocked"; the subprocess may still fail with
    # exit_code != 0 / FileNotFoundError if ruff isn't installed, which is
    # captured as a non-zero exit, not a block.
    assert result_allowed.blocked is False, result_allowed.block_reason


# ---------------------------------------------------------------------------
# 5 & 6. Environment secrets stripped by default; allowlist passes them through
# ---------------------------------------------------------------------------


def test_environment_secrets_are_stripped_by_default(real_repo: Path, monkeypatch):
    monkeypatch.setenv("MY_FAKE_API_KEY", "should-not-leak")
    monkeypatch.setenv("MY_FAKE_TOKEN", "should-not-leak")
    monkeypatch.setenv("PUBLIC_FLAG", "ok-to-pass")

    program = (
        "import os; "
        "print('KEY=' + os.environ.get('MY_FAKE_API_KEY','MISSING')); "
        "print('TOKEN=' + os.environ.get('MY_FAKE_TOKEN','MISSING')); "
        "print('PUB=' + os.environ.get('PUBLIC_FLAG','MISSING'))"
    )
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        f'python -c "{program}"',
        timeout_sec=30,
        run_label="env-strip",
    )

    assert result.ok, result.stderr
    assert "KEY=MISSING" in result.stdout
    assert "TOKEN=MISSING" in result.stdout
    assert "should-not-leak" not in result.stdout
    # Non-secret env vars still propagate.
    assert "PUB=ok-to-pass" in result.stdout


def test_env_allowlist_passes_specific_secret(real_repo: Path, monkeypatch):
    monkeypatch.setenv("MY_FAKE_API_KEY", "explicit-allow")

    program = (
        "import os; "
        "print('KEY=' + os.environ.get('MY_FAKE_API_KEY','MISSING'))"
    )
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        f'python -c "{program}"',
        env_allowlist=["MY_FAKE_API_KEY"],
        timeout_sec=30,
        run_label="env-allow",
    )

    assert result.ok, result.stderr
    assert "KEY=explicit-allow" in result.stdout


# ---------------------------------------------------------------------------
# 7. Timeout returns timed_out=True
# ---------------------------------------------------------------------------


def test_timeout_returns_timed_out_true(real_repo: Path):
    started = time.time()
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "import time; time.sleep(20)"',
        timeout_sec=2,
        run_label="timeout",
    )
    elapsed_wall = time.time() - started

    assert result.timed_out is True
    assert result.ok is False
    # We must have killed the child well before its natural finish.
    assert elapsed_wall < 15, f"timeout took too long: {elapsed_wall:.2f}s"


# ---------------------------------------------------------------------------
# 8. stdout/stderr are capped and output_truncated=True
# ---------------------------------------------------------------------------


def test_output_is_capped_and_marked_truncated(real_repo: Path):
    # Print roughly 50 KB so we comfortably exceed the 4 KB cap below.
    program = "print('A' * 50000)"
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        f'python -c "{program}"',
        max_output_chars=4096,
        timeout_sec=30,
        run_label="cap",
    )

    assert result.ok, result.stderr
    assert result.output_truncated is True
    assert len(result.stdout) <= 4096 + 200  # cap + truncation marker slack
    assert "truncated" in result.stdout
    # Head and tail of the original text both survived.
    assert result.stdout.startswith("AAAA")
    assert result.stdout.rstrip().endswith("AAAA")


# ---------------------------------------------------------------------------
# 9 & 10. Cleanup status; keep_temp preserves clone
# ---------------------------------------------------------------------------


def test_cleanup_default_removes_temp_dir(real_repo: Path):
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "print(\'hi\')"',
        timeout_sec=30,
        run_label="cleanup",
    )
    assert result.cleanup_ok is True
    # After successful cleanup the runner blanks ``temp_path``.
    assert result.temp_path == ""


def test_keep_temp_preserves_temp_path(real_repo: Path):
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "print(\'kept\')"',
        timeout_sec=30,
        run_label="kept",
        keep_temp=True,
    )
    try:
        assert result.cleanup_ok is True
        assert result.temp_path
        assert Path(result.temp_path).is_dir()
        assert (Path(result.cwd) / "main.py").is_file()
    finally:
        if result.temp_path and Path(result.temp_path).exists():
            sandbox_runner._safe_rmtree(Path(result.temp_path))


# ---------------------------------------------------------------------------
# 11. copy_ignore excludes .agent and .git (and extras)
# ---------------------------------------------------------------------------


def test_copy_ignore_excludes_dot_agent_and_git(real_repo: Path):
    # Add an extra folder so we can confirm caller-supplied ignores apply.
    (real_repo / "huge_artifacts").mkdir()
    (real_repo / "huge_artifacts" / "blob.bin").write_text("x" * 100, encoding="utf-8")

    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "print(\'ignore-test\')"',
        copy_ignore=["huge_artifacts"],
        run_label="ignore",
        keep_temp=True,
    )
    try:
        clone_root = Path(result.cwd)
        assert (clone_root / "main.py").is_file()  # copied
        assert not (clone_root / ".git").exists()  # default ignore
        assert not (clone_root / ".agent").exists()  # default ignore
        assert not (clone_root / "huge_artifacts").exists()  # caller-supplied
    finally:
        if result.temp_path and Path(result.temp_path).exists():
            sandbox_runner._safe_rmtree(Path(result.temp_path))


def test_default_copy_ignore_excludes_pytest_temp_folders(real_repo: Path):
    """Phase 7.3a Windows regression — pytest occasionally leaves locked
    handles inside ``.tmp`` between teardown and the OS releasing them, which
    used to crash ``shutil.copytree`` with ``WinError 5``. ``.tmp`` and its
    family (``tmp`` / ``temp`` / ``.pytest-tmp``) are now part of the default
    ignore set so staging copies skip them entirely.
    """
    for folder in (".tmp", "tmp", "temp", ".pytest-tmp"):
        sub = real_repo / folder
        sub.mkdir()
        (sub / "leftover.lock").write_text("locked content", encoding="utf-8")

    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "print(\'tmp-ignore\')"',
        timeout_sec=30,
        run_label="tmp-ignore",
        keep_temp=True,
    )
    try:
        assert result.ok is True
        clone_root = Path(result.cwd)
        # The fixture file we want to keep is still there.
        assert (clone_root / "main.py").is_file()
        # None of the pytest temp variants made it into the staging copy.
        for folder in (".tmp", "tmp", "temp", ".pytest-tmp"):
            assert not (clone_root / folder).exists(), (
                f"{folder!r} should be excluded by DEFAULT_COPY_IGNORE"
            )
        # Sanity check: those names also appear in the public constant so
        # the docker_ubuntu staging path uses the same exclusions.
        for folder in (".tmp", "tmp", "temp", ".pytest-tmp"):
            assert folder in sandbox_runner.DEFAULT_COPY_IGNORE
    finally:
        if result.temp_path and Path(result.temp_path).exists():
            sandbox_runner._safe_rmtree(Path(result.temp_path))


# ---------------------------------------------------------------------------
# 12. Path traversal in label / bad repo_path
# ---------------------------------------------------------------------------


def test_label_with_path_traversal_is_sanitized(real_repo: Path):
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "print(\'ok\')"',
        run_label="../../escape/../etc/passwd",
        timeout_sec=30,
    )
    assert result.ok
    artifact_dir = Path(result.artifact_dir)
    sandbox_root = (real_repo / ".agent" / "sandbox_runs").resolve()
    # Sanitised path stays inside the sandbox_runs root.
    assert artifact_dir.resolve().is_relative_to(sandbox_root)
    assert ".." not in artifact_dir.name
    assert "/" not in artifact_dir.name
    assert "\\" not in artifact_dir.name


def test_missing_repo_path_is_refused(tmp_path: Path):
    with pytest.raises((FileNotFoundError, ValueError)):
        sandbox_runner.run_in_temp_clone(tmp_path / "does_not_exist", "python -c \"1\"")


def test_empty_repo_path_is_refused():
    with pytest.raises(ValueError):
        sandbox_runner.run_in_temp_clone("", "python -c \"1\"")


# ---------------------------------------------------------------------------
# 13. Artifacts are written under <repo>/.agent/sandbox_runs/<id>/
# ---------------------------------------------------------------------------


def test_artifacts_are_written_under_real_repo_agent_dir(real_repo: Path):
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "import sys; print(\'OUT\'); print(\'ERR\', file=sys.stderr)"',
        timeout_sec=30,
        run_label="artifacts",
    )
    assert result.ok, result.stderr
    artifact_dir = Path(result.artifact_dir)
    sandbox_root = real_repo / ".agent" / "sandbox_runs"
    assert artifact_dir.resolve().is_relative_to(sandbox_root.resolve())
    assert (artifact_dir / "run.json").is_file()
    assert (artifact_dir / "stdout.txt").is_file()
    assert (artifact_dir / "stderr.txt").is_file()

    run_json = json.loads((artifact_dir / "run.json").read_text(encoding="utf-8"))
    assert run_json["ok"] is True
    assert run_json["exit_code"] == 0
    assert "artifacts" in artifact_dir.name


def test_blocked_command_still_writes_artifact(real_repo: Path):
    result = sandbox_runner.run_in_temp_clone(
        real_repo,
        "python -c 'print(1)' && rm -rf /",
        run_label="blocked",
    )
    assert result.blocked is True
    artifact_dir = Path(result.artifact_dir)
    assert (artifact_dir / "run.json").is_file()
    run_json = json.loads((artifact_dir / "run.json").read_text(encoding="utf-8"))
    assert run_json["blocked"] is True
    assert run_json["block_reason"]


# ---------------------------------------------------------------------------
# 14. Safety — no forbidden module imports
# ---------------------------------------------------------------------------


def test_runner_does_not_import_model_patch_lesson_benchmark_modules(real_repo: Path):
    forbidden = {
        "benchmarks.run_benchmarks",
        "agents.gemini_client",
        "agents.deepseek_client",
        "agents.ollama_client",
        "core.executor",
        "core.run_lifecycle",
        "core.proposal_runner",
        "core.lesson_store",
        "core.benchmark_web",
        "patching.patch_executor",
        "core.sleeping_consultant",
    }
    before = set(sys.modules)
    sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "print(\'safety check\')"',
        timeout_sec=30,
        run_label="safety",
    )
    after = set(sys.modules)
    newly_loaded = (after - before) & forbidden
    assert newly_loaded == set(), (
        f"sandbox_runner pulled in forbidden modules: {sorted(newly_loaded)}"
    )

    # Source-level guard: the module file must not name any forbidden import.
    source = Path(sandbox_runner.__file__).read_text(encoding="utf-8")
    for name in forbidden:
        assert name not in source, (
            f"core/sandbox_runner.py references forbidden module {name}"
        )


# ===========================================================================
# Phase 7.3a — Docker / Ubuntu backend tests
# ===========================================================================
#
# Docker isn't installed on most dev / CI machines, so every assertion below
# either tests pure-Python builder code or monkeypatches the docker shim. We
# never spawn an actual ``docker run`` from these tests.


def _record_docker_argv(monkeypatch, *, exit_code=0, stdout="", stderr=""):
    """Replace ``_run_docker_subprocess`` with a stub that records its argv
    and returns the requested result tuple. Returns the ``recorded`` list."""
    recorded: list[list[str]] = []

    def fake_run(docker_argv, *, timeout_sec, container_name):
        recorded.append(list(docker_argv))
        return exit_code, stdout, stderr, False, 0.01

    monkeypatch.setattr(sandbox_runner, "_run_docker_subprocess", fake_run)
    monkeypatch.setattr(
        sandbox_runner, "_is_docker_available", lambda: (True, "")
    )
    return recorded


# ---------------------------------------------------------------------------
# Backend dispatch
# ---------------------------------------------------------------------------


def test_run_in_sandbox_defaults_to_temp_clone(real_repo: Path):
    result = sandbox_runner.run_in_sandbox(
        real_repo,
        'python -c "print(\'hello sandbox\')"',
        timeout_sec=30,
        run_label="dispatch-default",
    )
    assert result.ok is True
    assert "hello sandbox" in result.stdout
    # Temp-clone backend cleans up by default.
    assert result.cleanup_ok is True


def test_run_in_sandbox_temp_clone_matches_direct_call(real_repo: Path):
    """Going through ``run_in_sandbox`` must behave identically to calling
    ``run_in_temp_clone`` directly. Guards against the dispatcher dropping
    kwargs."""
    direct = sandbox_runner.run_in_temp_clone(
        real_repo,
        'python -c "print(\'direct\')"',
        timeout_sec=30,
        run_label="direct",
    )
    dispatched = sandbox_runner.run_in_sandbox(
        real_repo,
        'python -c "print(\'direct\')"',
        backend="temp_clone",
        timeout_sec=30,
        run_label="dispatched",
    )
    assert direct.ok is True
    assert dispatched.ok is True
    assert direct.exit_code == dispatched.exit_code
    assert direct.stdout.strip() == dispatched.stdout.strip()


def test_run_in_sandbox_unknown_backend_returns_friendly_block(real_repo: Path):
    result = sandbox_runner.run_in_sandbox(
        real_repo,
        'python -c "print(1)"',
        backend="space_station",
        run_label="bad-backend",
    )
    assert result.blocked is True
    assert "unknown backend" in result.block_reason
    assert "space_station" in result.block_reason
    # Does not crash, does not write any artifact for an unknown backend
    # (we never resolved a repo path beyond the dispatcher).


# ---------------------------------------------------------------------------
# Docker unavailability
# ---------------------------------------------------------------------------


def test_docker_unavailable_returns_blocked_not_traceback(
    real_repo: Path, monkeypatch
):
    monkeypatch.setattr(
        sandbox_runner, "_is_docker_available",
        lambda: (False, "docker binary not on PATH"),
    )

    result = sandbox_runner.run_in_sandbox(
        real_repo,
        'python -c "print(1)"',
        backend="docker_ubuntu",
        run_label="docker-missing",
    )
    assert result.blocked is True
    assert "docker backend unavailable" in result.block_reason
    # Still emits an artifact so the refusal is auditable.
    assert Path(result.artifact_dir, "run.json").is_file()


# ---------------------------------------------------------------------------
# Docker command builder — pure-function assertions
# ---------------------------------------------------------------------------


def test_docker_command_builder_uses_network_none_by_default(tmp_path: Path):
    argv = sandbox_runner._build_docker_command(
        image="python:3.12-slim",
        mount_src=tmp_path,
        argv=["python", "-c", "print(1)"],
        env={},
        container_name="t",
    )
    assert "--network" in argv
    network_value = argv[argv.index("--network") + 1]
    assert network_value == "none"


def test_docker_command_builder_does_not_use_privileged(tmp_path: Path):
    argv = sandbox_runner._build_docker_command(
        image="python:3.12-slim",
        mount_src=tmp_path,
        argv=["python", "-c", "print(1)"],
        env={},
        container_name="t",
    )
    assert "--privileged" not in argv


def test_docker_command_builder_does_not_mount_docker_socket(tmp_path: Path):
    argv = sandbox_runner._build_docker_command(
        image="python:3.12-slim",
        mount_src=tmp_path,
        argv=["python", "-c", "print(1)"],
        env={},
        container_name="t",
    )
    joined = " ".join(argv).lower()
    assert "docker.sock" not in joined
    # The only -v mount should be the staging dir → /work, nothing else.
    mount_args = [
        argv[i + 1] for i, token in enumerate(argv[:-1]) if token == "-v"
    ]
    assert len(mount_args) == 1
    assert mount_args[0].endswith(":/work")


def test_docker_command_builder_does_not_mount_host_home(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("HOME", str(Path.home()))
    argv = sandbox_runner._build_docker_command(
        image="python:3.12-slim",
        mount_src=tmp_path,
        argv=["python", "-c", "print(1)"],
        env={},
        container_name="t",
    )
    home_marker = str(Path.home()).replace("\\", "/")
    mount_args = [
        argv[i + 1] for i, token in enumerate(argv[:-1]) if token == "-v"
    ]
    for mount in mount_args:
        host_side = mount.split(":", 1)[0]
        assert home_marker not in host_side or host_side == str(tmp_path).replace("\\", "/"), (
            f"host mount {mount!r} looks like the host home directory"
        )


def test_docker_command_builder_applies_memory_and_cpu_limits(tmp_path: Path):
    argv = sandbox_runner._build_docker_command(
        image="python:3.12-slim",
        mount_src=tmp_path,
        argv=["python", "-c", "print(1)"],
        env={},
        container_name="t",
        memory="512m",
        cpus="0.5",
    )
    assert "--memory" in argv and argv[argv.index("--memory") + 1] == "512m"
    assert "--cpus" in argv and argv[argv.index("--cpus") + 1] == "0.5"


def test_docker_command_builder_has_no_new_privileges_and_drops_caps(
    tmp_path: Path,
):
    """Defense-in-depth flags. We don't test them as separate scenarios in
    the spec but they live next to the other security flags so they belong
    in the same test family."""
    argv = sandbox_runner._build_docker_command(
        image="python:3.12-slim",
        mount_src=tmp_path,
        argv=["python", "-c", "print(1)"],
        env={},
        container_name="t",
    )
    assert "--cap-drop" in argv and argv[argv.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in argv
    sec_value = argv[argv.index("--security-opt") + 1]
    assert "no-new-privileges" in sec_value
    assert "--read-only" in argv


# ---------------------------------------------------------------------------
# Docker backend integration (with the docker shim mocked out)
# ---------------------------------------------------------------------------


def test_docker_backend_mounts_temp_staging_not_real_repo(
    real_repo: Path, monkeypatch
):
    recorded = _record_docker_argv(monkeypatch, exit_code=0, stdout="OK\n")

    result = sandbox_runner.run_in_sandbox(
        real_repo,
        'python -c "print(\'docker-stage\')"',
        backend="docker_ubuntu",
        timeout_sec=30,
        run_label="stage-test",
    )
    assert result.blocked is False
    assert result.ok is True

    assert recorded, "docker subprocess was not invoked"
    docker_argv = recorded[0]
    mount_args = [
        docker_argv[i + 1]
        for i, token in enumerate(docker_argv[:-1])
        if token == "-v"
    ]
    assert len(mount_args) == 1
    host_side = mount_args[0].split(":", 1)[0]
    # The host side must point at the staging copy, NEVER at the real repo.
    real_repo_posix = real_repo.resolve().as_posix()
    assert host_side != real_repo_posix
    assert real_repo_posix not in host_side


def test_docker_backend_result_matches_schema_and_writes_artifacts(
    real_repo: Path, monkeypatch
):
    _record_docker_argv(
        monkeypatch,
        exit_code=0,
        stdout="hello from container\n",
        stderr="warn from container\n",
    )

    result = sandbox_runner.run_in_sandbox(
        real_repo,
        'python -c "print(\'hi\')"',
        backend="docker_ubuntu",
        timeout_sec=30,
        run_label="docker-artifacts",
    )

    # Field-for-field schema check.
    for field_name in (
        "ok", "exit_code", "timed_out", "blocked", "block_reason",
        "command", "cwd", "stdout", "stderr", "output_truncated",
        "elapsed_sec", "temp_path", "cleanup_ok", "artifact_dir",
        "changed_files", "created_at",
    ):
        assert hasattr(result, field_name), f"missing field {field_name}"

    assert result.ok is True
    assert "hello from container" in result.stdout
    assert "warn from container" in result.stderr

    artifact_dir = Path(result.artifact_dir)
    sandbox_root = real_repo / ".agent" / "sandbox_runs"
    assert artifact_dir.resolve().is_relative_to(sandbox_root.resolve())
    assert (artifact_dir / "run.json").is_file()
    assert (artifact_dir / "stdout.txt").is_file()
    assert (artifact_dir / "stderr.txt").is_file()


def test_docker_backend_strips_secret_env_by_default(
    real_repo: Path, monkeypatch
):
    monkeypatch.setenv("MY_FAKE_API_KEY", "should-not-leak")
    monkeypatch.setenv("MY_FAKE_TOKEN", "should-not-leak")
    monkeypatch.setenv("PYTHONUTF8", "1")
    recorded = _record_docker_argv(monkeypatch, exit_code=0)

    sandbox_runner.run_in_sandbox(
        real_repo,
        'python -c "print(1)"',
        backend="docker_ubuntu",
        timeout_sec=30,
        run_label="docker-env-strip",
    )

    assert recorded
    docker_argv = recorded[0]
    env_pairs = [
        docker_argv[i + 1]
        for i, token in enumerate(docker_argv[:-1])
        if token == "-e"
    ]
    for pair in env_pairs:
        name = pair.split("=", 1)[0]
        assert "KEY" not in name.upper()
        assert "TOKEN" not in name.upper()
        assert "SECRET" not in name.upper()
        assert "PASSWORD" not in name.upper()
        assert "CREDENTIAL" not in name.upper()


def test_docker_backend_env_allowlist_passes_only_allowed_vars(
    real_repo: Path, monkeypatch
):
    monkeypatch.setenv("MY_FAKE_API_KEY", "explicit-allow")
    monkeypatch.setenv("MY_FAKE_TOKEN", "blocked")
    monkeypatch.setenv("PUBLIC_FLAG", "ok-to-pass")
    recorded = _record_docker_argv(monkeypatch, exit_code=0)

    sandbox_runner.run_in_sandbox(
        real_repo,
        'python -c "print(1)"',
        backend="docker_ubuntu",
        env_allowlist=["MY_FAKE_API_KEY"],
        timeout_sec=30,
        run_label="docker-env-allow",
    )

    assert recorded
    docker_argv = recorded[0]
    env_pairs = [
        docker_argv[i + 1]
        for i, token in enumerate(docker_argv[:-1])
        if token == "-e"
    ]
    env_names = {pair.split("=", 1)[0] for pair in env_pairs}

    # Explicitly allow-listed secret crosses into the container.
    assert "MY_FAKE_API_KEY" in env_names
    # Other secret stays out.
    assert "MY_FAKE_TOKEN" not in env_names
    # Public non-secret without allowlist also stays out (docker subset is
    # stricter than the temp-clone env scrub: only PYTHON* + allowlist).
    assert "PUBLIC_FLAG" not in env_names
    # Python knobs always propagate so the container's interpreter behaves.
    assert any(name.startswith("PYTHON") for name in env_names)


def test_docker_backend_blocks_dangerous_command_before_subprocess(
    real_repo: Path, monkeypatch
):
    recorded = _record_docker_argv(monkeypatch)

    result = sandbox_runner.run_in_sandbox(
        real_repo,
        "python -c 'print(1)' && rm -rf /",
        backend="docker_ubuntu",
        run_label="docker-blocked",
    )
    assert result.blocked is True
    # The docker shim should never have been called.
    assert recorded == []
    # Blocked artifact still written.
    assert Path(result.artifact_dir, "run.json").is_file()


def test_docker_backend_blocks_interpreter_command(
    real_repo: Path, monkeypatch
):
    _record_docker_argv(monkeypatch)
    result = sandbox_runner.run_in_sandbox(
        real_repo,
        "bash -lc 'echo bad'",
        backend="docker_ubuntu",
        run_label="docker-bash",
    )
    assert result.blocked is True
    assert "blocked" in result.block_reason or "allowlist" in result.block_reason
