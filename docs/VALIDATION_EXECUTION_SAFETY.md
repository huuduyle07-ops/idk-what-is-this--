# Validation Execution Safety

Status: A.18 implemented boundary.

## Safe Validation

Automation-capable validation must use `core.validation_execution.SafeValidationCommand`.

Safe commands are argv-style, not shell strings:

```python
SafeValidationCommand(
    command=["python", "-m", "pytest", "tests/test_example.py", "-q"],
    cwd=repo_or_sandbox_path,
    timeout_sec=60,
)
```

The safe runner uses `subprocess.run(..., shell=False)`, requires a bounded
timeout, runs from an explicit cwd, and scrubs secret-looking environment
variables by default.

Safe mode rejects:

- shell metacharacters such as `&&`, `||`, `;`, backticks, pipes, and redirects
- shell interpreters such as `bash`, `sh`, `cmd`, and PowerShell
- arbitrary `python -c`
- destructive filesystem commands and destructive `git reset --hard` / `git clean`
- direct environment-dumping tools such as `env`, `printenv`, and `set`

## Legacy Manual Shell Validation

`core.validator.run_validation_command` is retained as the legacy/manual shell
runner for existing human-driven flows. It is also exported as
`run_legacy_validation_command` to make the boundary explicit.

This path still uses `shell=True` after the existing destructive-command screen.
Do not use it for automation, background self-evolution, or any flow that applies
patches without a human/manual decision point.

## Patch Execution Boundary

`core.executor.Executor.run`, `patching.patch_plan_executor.apply_patch_plan`,
and `core.run_lifecycle.run_patch_plan_with_artifacts` now accept
`safe_validation_command`.

When a safe command is supplied, it is preferred over any legacy shell string.
Automation-oriented callers can pass `require_safe_validation=True`; with that
flag, a raw `validation_command` string is rejected before patch operations run.

This change adds no automation or self-evolution capability. It only creates the
validation execution boundary those future paths must use.
