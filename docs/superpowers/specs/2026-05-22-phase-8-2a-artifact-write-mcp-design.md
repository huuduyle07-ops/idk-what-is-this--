# Phase 8.2a — MCP artifact-write harness for `create_handoff_note` only

> Status: design approved 2026-05-22.
> Scope: a second MCP server that exposes every read-only tool plus exactly one write-capable tool — `create_handoff_note`. No other write/execute tool ships in this phase.

## Goal

Stand up `mcp_server.artifact_write` as a second, narrowly-scoped MCP server. It exposes the same 10 read-only tools as `mcp_server.read_only` plus one new artifact-writing tool: `create_handoff_note`. Every other artifact-write / temp-clone-execute / real-repo-write / memory-write tool stays blocked.

The point is to give an external MCP client a way to *describe* a unit of work it wants a worker to do, without giving it the ability to actually run that worker, apply patches, touch the real repo, or change lesson state.

## Non-goals

- Exposing `import_worker_run_as_proposal` (Phase 8.2b candidate)
- Exposing `validate_imported_worker_proposal` (Phase 8.2c candidate — runs subprocess in temp clone)
- Exposing `run_subagent_handoff`, `apply_patch`, `apply_patch_plan`, `dream_apply`, `promote_lesson`, `block_lesson`
- Changing the behavior or surface of the existing read-only MCP server
- Using `capability_mode="unsafe_dev"` anywhere
- Modifying `core/tool_registry.py` or its capability-mode semantics
- Adding new pip dependencies (still uses optional `mcp` package)
- Running any subprocess inside the harness
- Writing anywhere outside `<project>/.agent/handoffs/`

## Architecture

```
mcp_server/
  read_only.py            # (unchanged)
  artifact_write.py       # NEW — read-only tools + create_handoff_note

scripts/
  mcp_readonly_server.py        # (unchanged)
  mcp_artifact_write_server.py  # NEW — thin shim → mcp_server.artifact_write.main

tests/
  test_mcp_readonly_server.py            # (unchanged; already asserts create_handoff_note NOT exposed)
  test_mcp_artifact_write_server.py      # NEW — allowlist + CLI + missing-dep contract
  test_create_handoff_note_harness.py    # NEW — harness validation + safety
```

The artifact-write module **re-uses** the 10 `_impl_*` callables from `mcp_server.read_only` by importing them directly. This avoids duplicating implementations and guarantees that any future change to a read-only impl flows through automatically. The artifact-write module adds exactly one new impl: `_impl_create_handoff_note`, which delegates to `create_handoff_note_harness`.

No changes to `web/app.py`, `core/tool_registry.py`, or any other module.

## `mcp_server/artifact_write.py`

### Module-level constants

```python
CAPABILITY_MODE = "artifact_write"  # the registry mode the server's surface lives inside
_EXTRA_WRITE_TOOLS: tuple[str, ...] = ("create_handoff_note",)
_SERVER_NAME = "cattus-artifact-write"
_FRIENDLY_MISSING_DEP_MSG = "MCP package not installed. Install optional MCP dependencies to run this server."
```

`CAPABILITY_MODE` is informational — it documents the registry mode the server's surface lives inside, but the server does NOT use `is_tool_allowed(name, "artifact_write")` to populate its full allowlist (because that would expose all three artifact-write tools). Instead, the explicit `_EXTRA_WRITE_TOOLS` tuple is the narrow second-gate, exactly like `_IMPLS` is the second-gate in `read_only.py`.

### Public functions

```python
def list_exposed_tool_names() -> list[str]:
    """Returns 11 tool names: 10 read-only + create_handoff_note."""

def create_handoff_note_harness(
    input: dict,
    *,
    handoff_root: Path | None = None,
) -> dict:
    """Validates input, calls core.handoff_notes.create_handoff_note, returns
    {ok, handoff_path, status, message}. Raises ValueError on invalid input.

    `handoff_root` is keyword-only and used only by tests + internal callers
    that want to redirect output to a tmp_path. It is NOT part of `input`
    (which is the MCP-facing schema), so external agents cannot influence it."""

def build_server() -> Any:
    """Construct (but do not run) a FastMCP server with allowed tools wired.
    Raises RuntimeError(friendly msg) if `mcp` not installed."""

def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. --list-tools → print 11 names + exit 0.
    No flag → build_server().run(). Returns 2 on missing mcp dep."""
```

`_impl_create_handoff_note(input: dict) -> dict` is the FastMCP-registered callable; it calls `create_handoff_note_harness(input)` without `handoff_root`, so the default `.agent/handoffs/` root is always used in production. FastMCP's schema introspection only sees `_impl_create_handoff_note`'s signature, so the `handoff_root` keyword stays invisible to external MCP clients.

### Allowlist derivation

```python
def list_exposed_tool_names() -> list[str]:
    names = list(read_only.list_exposed_tool_names())  # 10 read tools
    for n in _EXTRA_WRITE_TOOLS:
        if tool_registry.is_tool_allowed(n, "artifact_write"):  # belt-and-suspenders
            names.append(n)
    return names
```

The `is_tool_allowed(n, "artifact_write")` check is defensive — if someone ever sets `mcp_exposable=False` on `create_handoff_note` in the registry, this server stops exposing it automatically.

### Implementation table

| Tool name | Impl source |
|---|---|
| `get_health` | `read_only._impl_get_health` |
| `list_benchmark_reports` | `read_only._impl_list_benchmark_reports` |
| `read_benchmark_report` | `read_only._impl_read_benchmark_report` |
| `list_dream_reports` | `read_only._impl_list_dream_reports` |
| `read_dream_report` | `read_only._impl_read_dream_report` |
| `list_lessons` | `read_only._impl_list_lessons` |
| `read_lesson_proposal` | `read_only._impl_read_lesson_proposal` |
| `list_worker_runs` | `read_only._impl_list_worker_runs` |
| `read_worker_run` | `read_only._impl_read_worker_run` |
| `list_tool_registry` | `read_only._impl_list_tool_registry` |
| `create_handoff_note` | `_impl_create_handoff_note` (new — wraps the harness) |

`_impl_create_handoff_note` is a thin one-liner: `return create_handoff_note_harness(input)`. The harness is the public boundary.

## `create_handoff_note_harness` — input contract

Signature: `def create_handoff_note_harness(input: dict) -> dict`.

A dict-in/dict-out wrapper is used (rather than exposing `core.handoff_notes.create_handoff_note` directly through MCP) so the MCP-facing schema and JSON response shape are stable and decoupled from the richer internal kwargs API. FastMCP introspects the callable's signature to build the input schema, so the harness gives us full control over what an external agent can pass.

### Input fields

| Field | Type | Required | Validation |
|---|---|---|---|
| `title` | str | ✅ | non-empty after `.strip()`; length ≤ 200 chars |
| `intended_worker` | str | ✅ | must be in `{codex, claude-code, gemini, other}` |
| `task_type` | str | ✅ | must be in `{proposal_only, review_only, explain_only, benchmark_case, research}` |
| `context_summary` | str | ✅ | non-empty after `.strip()`; length ≤ 8000 chars |
| `repo_path` | str | optional | accepted as-is; passed to core; **never written to** by this server |
| `allowed_files` | list[str] | optional | every entry passes `_safe_rel_path` (no abs, no traversal, no leading `/` or `..`) |
| `forbidden_files` | list[str] | optional | same safety check as `allowed_files` |
| `validation_command` | str | optional | length ≤ 500 chars; passed as string only — not executed |
| `expected_output` | str | optional | length ≤ 4000 chars |

**Unknown fields** raise `ValueError("unknown field: <name>")`. This is strict-mode so external agents can't sneak undeclared kwargs through.

**Path safety** for `allowed_files` and `forbidden_files`: each entry must be a relative POSIX-style path with no `..` segments and no leading slash. Backslash is normalized to `/` before validation. Rejecting input here is one of two gates — `core.handoff_notes._safe_rel_path` is the other; the harness's gate fires first so we never call into core with bad data.

### Safety defaults — never overridden

The harness always passes `extra_safety_rules=None` to `core.handoff_notes.create_handoff_note`, so the core module's `DEFAULT_SAFETY_RULES` and `DEFAULT_FORBIDDEN_FILES` apply. The defaults already include:

- "proposal only"
- "do not apply patch"
- "do not commit"
- "do not push"
- "do not edit .env/.agent/.git/node_modules/target/tests unless explicitly allowed"
- "return proposal.md and patch_plan.json if possible"

…and forbidden files: `.env`, `.agent`, `.git`, `node_modules`, `target`, `tests`.

The harness does NOT expose a way to disable or override these. (A future Phase 8.2x might expose `extra_safety_rules`, but Phase 8.2a does not.)

### Output shape

On success — exactly these four keys:

```json
{
  "ok": true,
  "handoff_path": "<absolute path under .agent/handoffs/>",
  "status": "draft",
  "message": "Handoff note created. This did not run a subagent."
}
```

On validation failure: raises `ValueError` with a clear message. FastMCP surfaces this to the caller as a tool error. We do NOT return `{"ok": false, ...}` because the existing read-only impls also raise on bad input; consistency wins.

## `scripts/mcp_artifact_write_server.py`

A 30-line shim mirroring `scripts/mcp_readonly_server.py`:

```python
import sys
from pathlib import Path

def _ensure_project_root_on_path() -> None:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

def main() -> int:
    _ensure_project_root_on_path()
    from mcp_server.artifact_write import main as _server_main
    return _server_main(sys.argv[1:])

if __name__ == "__main__":
    raise SystemExit(main())
```

## CLI behavior

| Flag | Behavior | Exit code |
|---|---|---|
| `--list-tools` | Print 11 tool names (one per line) to stdout. Never imports `mcp`. | 0 |
| (no flag) | `build_server().run()`. Blocks on stdio. | 0 (clean shutdown) |
| (no flag) + `mcp` not installed | Print friendly message to stderr, do not attempt to construct server. | 2 |

Identical exit-code contract to `mcp_server.read_only.main`.

## What's exposed

| Tool | Read-only server | Artifact-write server |
|---|---|---|
| `get_health` | ✅ | ✅ |
| `list_benchmark_reports` | ✅ | ✅ |
| `read_benchmark_report` | ✅ | ✅ |
| `list_dream_reports` | ✅ | ✅ |
| `read_dream_report` | ✅ | ✅ |
| `list_lessons` | ✅ | ✅ |
| `read_lesson_proposal` | ✅ | ✅ |
| `list_worker_runs` | ✅ | ✅ |
| `read_worker_run` | ✅ | ✅ |
| `list_tool_registry` | ✅ | ✅ |
| **`create_handoff_note`** | ❌ | **✅** |
| `import_worker_run_as_proposal` | ❌ | ❌ |
| `validate_imported_worker_proposal` | ❌ | ❌ |
| `apply_patch` | ❌ | ❌ |
| `apply_patch_plan` | ❌ | ❌ |
| `dream_apply` | ❌ | ❌ |
| `run_subagent_handoff` | ❌ | ❌ |
| `promote_lesson` | ❌ | ❌ |
| `block_lesson` | ❌ | ❌ |

The artifact-write server adds **exactly one** capability over read-only.

## Tests

### `tests/test_mcp_artifact_write_server.py`

Mirrors `tests/test_mcp_readonly_server.py`'s structure.

| Test | Assertion |
|---|---|
| `test_importing_module_does_not_start_server` | Module imports without side effects; exports `list_exposed_tool_names`, `build_server`, `main`, `CAPABILITY_MODE` |
| `test_module_importable_without_mcp_package` | `list_exposed_tool_names()` works without `mcp` installed |
| `test_capability_mode_constant` | `CAPABILITY_MODE == "artifact_write"`; never `"unsafe_dev"` |
| `test_exposed_names_are_exactly_eleven` | `set(list_exposed_tool_names()) == _EXPECTED_11` |
| `test_create_handoff_note_is_exposed` | `"create_handoff_note" in list_exposed_tool_names()` |
| `test_no_other_write_tools_exposed` (parametrized) | Each of `import_worker_run_as_proposal`, `validate_imported_worker_proposal`, `run_subagent_handoff`, `apply_patch`, `apply_patch_plan`, `dream_apply`, `promote_lesson`, `block_lesson` NOT in exposed names |
| `test_read_only_server_still_omits_create_handoff_note` | `mcp_server.read_only.list_exposed_tool_names()` does NOT contain `create_handoff_note` (cross-server regression guard) |
| `test_build_server_raises_friendly_error_when_mcp_missing` | Monkeypatch `_import_mcp` → `RuntimeError("MCP package not installed...")` |
| `test_main_exits_nonzero_with_friendly_stderr_when_mcp_missing` | `main([])` returns 2 + writes friendly stderr |
| `test_main_does_not_run_server_when_dep_missing` | Verified via tripwire that `server.run()` is never called |
| `test_list_tools_flag_prints_eleven_names` | `main(["--list-tools"])` exits 0, prints 11 names |
| `test_list_tools_flag_works_without_mcp_dep` | `--list-tools` doesn't touch `_import_mcp` |
| `test_list_tools_flag_does_not_build_or_run_server` | Tripwire on `build_server` — never called for `--list-tools` |

### `tests/test_create_handoff_note_harness.py`

Tests the harness independently of FastMCP.

| Test | Assertion |
|---|---|
| `test_valid_input_writes_file` | Returns `{ok, handoff_path, status="draft", message}`; file exists under `tmp_path` (passed via core's `handoff_root` kwarg) |
| `test_message_text_is_exact` | `result["message"] == "Handoff note created. This did not run a subagent."` |
| `test_status_is_draft` | `result["status"] == "draft"` |
| `test_title_empty_rejected` | `title=""` → `ValueError` |
| `test_title_whitespace_only_rejected` | `title="   "` → `ValueError` |
| `test_title_too_long_rejected` | `title="x" * 201` → `ValueError` |
| `test_context_summary_empty_rejected` | `context_summary=""` → `ValueError` |
| `test_context_summary_too_long_rejected` | `context_summary="x" * 8001` → `ValueError` |
| `test_invalid_worker_rejected` | `intended_worker="hacker"` → `ValueError` |
| `test_invalid_task_type_rejected` | `task_type="rm-rf"` → `ValueError` |
| `test_allowed_files_traversal_rejected` | `allowed_files=["../../etc/passwd"]` → `ValueError` matching "safe relative path" |
| `test_allowed_files_absolute_rejected` | `allowed_files=["/etc/passwd"]` → `ValueError` |
| `test_allowed_files_windows_traversal_rejected` | `allowed_files=["..\\windows\\system32"]` → `ValueError` |
| `test_forbidden_files_traversal_rejected` | `forbidden_files=["../../secret"]` → `ValueError` |
| `test_forbidden_files_absolute_rejected` | `forbidden_files=["/etc/shadow"]` → `ValueError` |
| `test_unknown_field_rejected` | `{..., "shell": "rm -rf"}` → `ValueError("unknown field")` |
| `test_validation_command_too_long_rejected` | `validation_command="x" * 501` → `ValueError` |
| `test_expected_output_too_long_rejected` | `expected_output="x" * 4001` → `ValueError` |
| `test_harness_does_not_invoke_subprocess` | Monkeypatch `subprocess.run` / `subprocess.Popen` / `os.system` as tripwires; valid call must not trip them |
| `test_harness_does_not_write_outside_handoff_root` | After a valid call, exactly one new file exists, and it sits inside the given handoff_root |
| `test_default_safety_rules_applied` | Parse the written file's HANDOFF_META JSON; `safety_rules` contains "do not apply patch", "do not commit", "do not push" |
| `test_default_forbidden_files_applied` | Parse meta JSON; `forbidden_files` contains `.env`, `.git`, `.agent` |
| `test_repo_path_not_written_to` | Pass a `repo_path` that exists but is read-only-snapshotted before/after the call; assert no files in `repo_path` changed |

Test file uses `tmp_path` fixtures and passes `handoff_root=tmp_path` directly to `create_handoff_note_harness` (the keyword-only second arg). This is the documented test-injection path; external MCP callers never see this parameter.

## Test count

- `tests/test_mcp_artifact_write_server.py`: 13 tests
- `tests/test_create_handoff_note_harness.py`: 23 tests
- **Total new tests: 36**

Plus regression: `tests/test_mcp_readonly_server.py` continues to pass unchanged — its existing `test_specific_forbidden_tool_not_exposed[create_handoff_note]` test is the cross-server regression guard from the read-only side.

## What this slice does NOT do (deferred)

- Exposing `import_worker_run_as_proposal` (Phase 8.2b)
- Exposing `validate_imported_worker_proposal` (Phase 8.2c — requires subprocess in temp clone)
- Exposing `run_subagent_handoff` (Phase 9+ — burns external worker quota)
- A capability mode flag (`--mode read_only|artifact_write`) on a single server binary — the two servers stay as separate entrypoints so an operator picks the surface explicitly via which script they launch
- Per-tool audit log of MCP invocations (Phase 8.x)
- Per-tool input JSON-Schema overrides (Phase 8.x — currently inferred from Python type hints by FastMCP)
- Adding `artifact_write` mode to `web/app.py`'s `/tools/registry` (already supported by Phase 8-prep)

## Acceptance criteria

1. `from mcp_server import artifact_write; artifact_write.list_exposed_tool_names()` returns 11 names: the 10 read-only tools + `create_handoff_note`.
2. `mcp_server.read_only.list_exposed_tool_names()` is unchanged — does NOT contain `create_handoff_note`.
3. `import mcp_server.artifact_write` does NOT require the `mcp` package to be installed.
4. `import mcp_server.artifact_write` does NOT start a server, open stdio, or block.
5. `mcp_server.artifact_write.CAPABILITY_MODE == "artifact_write"`. It is never `"unsafe_dev"`.
6. `python scripts/mcp_artifact_write_server.py --list-tools` prints 11 names and exits 0, even when `mcp` is not installed.
7. `python scripts/mcp_artifact_write_server.py` (no flag) without `mcp` installed prints the friendly message to stderr and exits 2.
8. `create_handoff_note_harness({...valid...})` writes a markdown file under `.agent/handoffs/` and returns `{ok: True, handoff_path, status: "draft", message: "Handoff note created. This did not run a subagent."}`.
9. `create_handoff_note_harness` raises `ValueError` for: empty title, oversize title, empty context_summary, unknown worker, unknown task_type, traversal in `allowed_files`, absolute path in `allowed_files`, traversal in `forbidden_files`, absolute path in `forbidden_files`, unknown extra field.
10. `create_handoff_note_harness` does NOT invoke any subprocess and does NOT write outside the configured handoff root.
11. The 36 new tests pass under `pytest tests/test_mcp_artifact_write_server.py tests/test_create_handoff_note_harness.py`.
12. The existing `tests/test_mcp_readonly_server.py` continues to pass unchanged.
13. The existing `tests/test_tool_registry.py` and `tests/test_tool_registry_routes.py` continue to pass unchanged.
