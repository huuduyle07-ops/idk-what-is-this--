# Validation Execution Safety

Status: A.18 and A.19 implemented boundaries.

## A.18 Safe Validation Execution

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

## A.19 Patch-Plan Atomicity Boundary

Patch-plan atomicity is patch-operation scoped. Patch operations are
rollback-protected on apply or validation failure, but validation side effects
are outside patch rollback scope unless validation runs in a disposable sandbox
or a future explicit side-effect rollback mechanism is used.

In short: validation side effects are outside patch rollback scope unless
sandbox validation or a future explicit rollback mechanism brings them inside it.

Patch-plan and executor results expose metadata for this boundary:

```json
{
  "atomicity_scope": "patch_ops_only",
  "patch_ops_rollback_protected": true,
  "validation_side_effects_in_rollback_scope": false,
  "validation_side_effect_policy": "reported_not_rolled_back",
  "sandbox_validation_recommended": true
}
```

When supported, validation is surrounded by lightweight repo snapshots that
report created, modified, and deleted files. The report marks whether each file
is inside the patch-touched scope and whether it looks like generated/noisy
output. A.19 does not auto-delete validation-created files, because validation
may create meaningful user artifacts.

Automation and self-evolution paths must use safe validation execution and must
prefer sandbox validation before relying on validation results. If
`validation_side_effects_in_rollback_scope` is `false`, future automation must
either require sandbox validation or explicitly accept the side-effect boundary.
