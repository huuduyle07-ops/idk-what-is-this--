from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_safe_argv_command_passes_through_without_shell(monkeypatch, tmp_path):
    from core.validation_execution import SafeValidationCommand, run_safe_validation_command

    calls: list[dict] = []

    def fake_run(argv, **kwargs):
        calls.append({"argv": argv, "kwargs": kwargs})
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr("core.validation_execution.subprocess.run", fake_run)

    command = SafeValidationCommand(
        command=["python", "-m", "pytest", "tests/test_example.py", "-q"],
        cwd=tmp_path,
        timeout_sec=15,
    )

    result = run_safe_validation_command(command)

    assert result.ok is True
    assert result.blocked is False
    assert calls
    assert calls[0]["kwargs"]["shell"] is False
    assert calls[0]["kwargs"]["timeout"] == 15
    assert calls[0]["kwargs"]["cwd"] == str(tmp_path)
    assert calls[0]["argv"][0] == sys.executable


def test_safe_mode_rejects_shell_metacharacters(tmp_path):
    from core.validation_execution import SafeValidationCommand, run_safe_validation_command

    command = SafeValidationCommand(
        command=["pytest", "-q", "tests/test_safe.py;rm -rf build"],
        cwd=tmp_path,
        timeout_sec=10,
    )

    result = run_safe_validation_command(command)

    assert result.ok is False
    assert result.blocked is True
    assert "shell metacharacter" in result.block_reason


def test_safe_mode_rejects_python_dash_c(tmp_path):
    from core.validation_execution import SafeValidationCommand, run_safe_validation_command

    command = SafeValidationCommand(
        command=["python", "-c", "print('unsafe')"],
        cwd=tmp_path,
        timeout_sec=10,
    )

    result = run_safe_validation_command(command)

    assert result.ok is False
    assert result.blocked is True
    assert "python -c" in result.block_reason


def test_safe_mode_rejects_destructive_commands(tmp_path):
    from core.validation_execution import SafeValidationCommand, run_safe_validation_command

    command = SafeValidationCommand(
        command=["git", "reset", "--hard", "HEAD~1"],
        cwd=tmp_path,
        timeout_sec=10,
    )

    result = run_safe_validation_command(command)

    assert result.ok is False
    assert result.blocked is True
    assert "destructive" in result.block_reason


def test_safe_mode_rejects_env_dumping_tools(tmp_path):
    from core.validation_execution import SafeValidationCommand, run_safe_validation_command

    command = SafeValidationCommand(
        command=["env"],
        cwd=tmp_path,
        timeout_sec=10,
    )

    result = run_safe_validation_command(command)

    assert result.ok is False
    assert result.blocked is True
    assert "environment dumping" in result.block_reason


def test_safe_mode_requires_bounded_timeout(tmp_path):
    from core.validation_execution import SafeValidationCommand, run_safe_validation_command

    command = SafeValidationCommand(
        command=["pytest"],
        cwd=tmp_path,
        timeout_sec=None,
    )

    result = run_safe_validation_command(command)

    assert result.ok is False
    assert result.blocked is True
    assert "timeout" in result.block_reason


def test_automation_path_cannot_use_legacy_shell_validation(tmp_path):
    from core.run_lifecycle import run_patch_plan_with_artifacts

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "created.py"

    result = run_patch_plan_with_artifacts(
        str(repo),
        [
            {
                "op": "create_file",
                "relative_path": "created.py",
                "content": "print('created')\n",
            }
        ],
        validation_command="pytest -q",
        require_safe_validation=True,
        source="automation_test",
    )

    assert result["success"] is False
    assert result["unsafe_validation_blocked"] is True
    assert "safe validation" in result["error"]
    assert not target.exists()


def test_patch_plan_uses_safe_validation_when_provided(monkeypatch, tmp_path):
    from core.validation_execution import (
        SafeValidationCommand,
        SafeValidationResult,
    )
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "app.py"
    target.write_text("old\n", encoding="utf-8")
    safe_command = SafeValidationCommand(
        command=["pytest", "-q"],
        cwd=repo,
        timeout_sec=10,
    )
    calls: list[SafeValidationCommand] = []

    def fake_safe_runner(command):
        calls.append(command)
        return SafeValidationResult(
            ok=True,
            blocked=False,
            block_reason="",
            exit_code=0,
            stdout="safe ok",
            stderr="",
            timed_out=False,
            command=["pytest", "-q"],
            cwd=str(repo),
        )

    monkeypatch.setattr(
        "patching.patch_plan_executor.run_safe_validation_command",
        fake_safe_runner,
    )

    result = apply_patch_plan(
        str(repo),
        [
            {
                "op": "replace_snippet",
                "relative_path": "app.py",
                "target_snippet": "old\n",
                "patched_snippet": "new\n",
            }
        ],
        validation_command="pytest -q",
        safe_validation_command=safe_command,
    )

    assert result["success"] is True
    assert result["validation_mode"] == "safe_argv"
    assert result["validation_output"] == "safe ok"
    assert calls == [safe_command]


def test_legacy_manual_shell_runner_is_explicitly_named():
    import core.validator as validator

    assert validator.run_legacy_validation_command is validator.run_validation_command
    assert "legacy/manual shell" in (validator.run_validation_command.__doc__ or "")
