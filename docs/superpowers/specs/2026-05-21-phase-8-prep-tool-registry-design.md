# Phase 8-prep — Tool Registry MVP (for future MCP integration)

> Status: design approved 2026-05-21.
> Scope: metadata-only. No MCP server, no network exposure, no behavior changes.

## Goal

Stand up a single source of truth describing which C.A.T.T.U.S operations are candidates for external exposure (via MCP or another agent protocol). Each tool entry is read-only metadata; nothing in this slice executes anything. The registry is the answer to the question "if we hand the keys to an external agent tomorrow, what's safe to give them?"

## Non-goals

- Adding the MCP SDK or any new network dependency
- Running an MCP server
- Wiring tools to their underlying functions (the registry just *describes* them; routing is future work)
- Running subagents, applying patches, committing/pushing, auto-promoting lessons
- Changing the behavior of any existing route

## Architecture

```
core/tool_registry.py            # pure metadata + four public functions
web/app.py (additions)            # GET /tools/registry route
tests/test_tool_registry.py       # 14 unit tests
tests/test_tool_registry_routes.py  # 1 Flask client test
docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md  # shipped block
```

No new pip dependencies. No changes to any other module.

## `core/tool_registry.py`

### Public API

```python
def list_tools() -> list[dict]: ...
def get_tool(name: str) -> dict | None: ...
def tools_by_category(category: str) -> list[dict]: ...
def is_tool_allowed(name: str, capability_mode: str = "read_only") -> bool: ...
```

All four functions return **copies** of the underlying registry dicts so a caller cannot accidentally mutate the source of truth.

### Constants

```python
VALID_CATEGORIES: frozenset[str] = frozenset({
    "read",
    "artifact_write",
    "temp_clone_execute",
    "real_repo_write",
    "memory_write",
})

VALID_CAPABILITY_MODES: frozenset[str] = frozenset({
    "read_only",
    "artifact_write",
    "operator",
    "unsafe_dev",
})
```

### Tool metadata schema

Every tool dict has exactly these keys:

| Field | Type | Notes |
|---|---|---|
| `name` | str | unique identifier; matches function or route id |
| `title` | str | human-readable label |
| `description` | str | one-sentence summary |
| `category` | str | one of `VALID_CATEGORIES` |
| `phase` | str | e.g. `"5"`, `"6.2"`, `"7.1"`, `"7.2.1.1"` |
| `reads` | list[str] | informal: what the tool reads (env, DB, files, etc.) |
| `writes` | list[str] | informal: what the tool writes (artifacts, files, etc.) |
| `can_touch_real_repo` | bool | True only for `category=real_repo_write` |
| `can_run_subprocess` | bool | True if the tool execs anything (subprocess.run, etc.) |
| `requires_human_approval` | bool | True if a human must explicitly click a button or run a CLI to invoke this |
| `mcp_exposable` | bool | global kill switch — False means never expose, even in `unsafe_dev` (mode-aware below) |
| `default_enabled` | bool | suggested default for a future MCP server's configuration |
| `route_or_function` | str | e.g. `"GET /health"` or `"core.handoff_notes.create_handoff_note"` |
| `notes` | str | free-form |

### Capability-mode semantics for `is_tool_allowed`

| Mode | Behavior |
|---|---|
| `read_only` | True iff tool exists AND `mcp_exposable=True` AND `category="read"` |
| `artifact_write` | True iff tool exists AND `mcp_exposable=True` AND `category in {"read", "artifact_write"}` |
| `operator` | True iff tool exists AND `mcp_exposable=True` AND (`category in {"read", "artifact_write"}` OR (`category in {"memory_write", "temp_clone_execute"}` AND `requires_human_approval=True`)). Never includes `real_repo_write`. |
| `unsafe_dev` | True iff tool exists. `mcp_exposable=False` is **ignored** here — this mode is for local debugging only and never reaches a production MCP server. |
| any other mode | `ValueError("unknown capability_mode: ...")` |

`get_tool(unknown_name)` returns `None`. `is_tool_allowed(unknown_name, ...)` returns `False`. `tools_by_category(invalid)` raises `ValueError`.

### Initial tool roster (18 tools)

**Read (9):**

| Name | route_or_function | phase |
|---|---|---|
| `get_health` | `GET /health` | 5 |
| `list_benchmark_reports` | `GET /benchmarks/list` | 5 |
| `read_benchmark_report` | `GET /benchmarks/report` | 5 |
| `list_dream_reports` | `GET /dream/reports` | 5 |
| `read_dream_report` | `GET /dream/report` | 5 |
| `list_lessons` | `GET /lessons/list` | 6.2 |
| `read_lesson_proposal` | `GET /lessons/proposal` | 6.2 |
| `list_worker_runs` | `GET /worker-runs/list` | 7.2 |
| `read_worker_run` | `GET /worker-runs/view` | 7.2 |

All: `mcp_exposable=True`, `can_touch_real_repo=False`, `can_run_subprocess=False`, `requires_human_approval=False`, `default_enabled=True`.

**Artifact-write (3):**

| Name | route_or_function | phase |
|---|---|---|
| `create_handoff_note` | `POST /handoffs/create` | 7.1 |
| `import_worker_run_as_proposal` | `POST /worker-runs/import` | 7.2 |
| `validate_imported_worker_proposal` | `POST /proposals/validate` | 7.2.1 |

All: `mcp_exposable=True`, `can_touch_real_repo=False`. `validate_imported_worker_proposal` has `can_run_subprocess=True` (inside temp clone) and `requires_human_approval=True`; the other two have `can_run_subprocess=False` and `requires_human_approval=False`. `default_enabled=True`.

**Disabled for MCP, registered for visibility (6):**

| Name | category | route_or_function | phase |
|---|---|---|---|
| `apply_patch` | real_repo_write | `POST /apply_patch` | 7 (preexisting) |
| `apply_patch_plan` | real_repo_write | `POST /apply_patch_plan` | 7 (preexisting) |
| `dream_apply` | real_repo_write | `POST /dream/apply` | preexisting |
| `run_subagent_handoff` | temp_clone_execute | `scripts.run_subagent_handoff.run_handoff` | 7.1 |
| `promote_lesson` | memory_write | `POST /lessons/promote` | 6.2 |
| `block_lesson` | memory_write | `POST /lessons/block` | 6.2 |

All: `mcp_exposable=False`, `requires_human_approval=True`, `default_enabled=False`. `can_touch_real_repo=True` for the three `real_repo_write` entries; False for the other three. `can_run_subprocess=True` for `apply_patch`, `apply_patch_plan`, `dream_apply` (validation commands), and `run_subagent_handoff` (subagent worker); False for the lesson-state changes.

## Web route

`GET /tools/registry` — returns `{"ok": True, "tools": list_tools()}`. Pure read; no parameters, no side effects.

Errors: 500 only on unexpected exceptions (shouldn't happen — pure in-process data). No 4xx paths.

## Tests (15 total)

| File | Test | What it asserts |
|---|---|---|
| `tests/test_tool_registry.py` | `test_list_tools_returns_initial_set` | All 18 expected tools present with required keys |
| | `test_list_tools_returns_copies` | Mutating result doesn't affect subsequent calls |
| | `test_get_tool_known` | `get_tool("get_health")` returns a dict with `name="get_health"` |
| | `test_get_tool_unknown_returns_none` | `get_tool("does_not_exist")` is None |
| | `test_tools_by_category_read` | Returns 9 read tools |
| | `test_tools_by_category_artifact_write` | Returns 3 artifact_write tools |
| | `test_tools_by_category_invalid_raises` | Unknown category → ValueError |
| | `test_read_only_allows_read_tools` | `is_tool_allowed("get_health", "read_only")` True |
| | `test_read_only_blocks_artifact_write` | `is_tool_allowed("create_handoff_note", "read_only")` False |
| | `test_read_only_blocks_real_repo_write` | `is_tool_allowed("apply_patch", "read_only")` False |
| | `test_artifact_write_allows_import_and_validate` | Both pass under artifact_write |
| | `test_artifact_write_blocks_apply_patch` | False under artifact_write |
| | `test_mcp_disabled_blocked_in_read_only` | apply_patch (mcp_exposable=False) blocked |
| | `test_is_tool_allowed_invalid_mode_raises` | `ValueError("unknown capability_mode")` |
| | `test_is_tool_allowed_unknown_tool_returns_false` | Unknown name → False (not exception) |
| `tests/test_tool_registry_routes.py` | `test_tools_registry_route_returns_tool_list` | GET /tools/registry returns ok+tools |

## What this MVP does NOT do (deferred)

- MCP server. Future Phase 8.0+.
- Wiring tools to actual function references (right now `route_or_function` is a string).
- Per-tool input schemas. Future Phase 8.x; would mirror JSON-Schema for MCP.
- Capability-mode persistence (env var, config file). Future Phase 8.x.
- Per-tool audit log. Future Phase 8.x.

## Acceptance criteria

1. `from core import tool_registry; tool_registry.list_tools()` returns 18 dicts.
2. Each dict has all 14 required keys.
3. `tool_registry.is_tool_allowed("get_health", "read_only")` is True.
4. `tool_registry.is_tool_allowed("apply_patch", "read_only")` is False (category mismatch AND mcp_exposable=False).
5. `tool_registry.is_tool_allowed("import_worker_run_as_proposal", "artifact_write")` is True.
6. `tool_registry.is_tool_allowed("apply_patch", "artifact_write")` is False.
7. `tool_registry.is_tool_allowed("apply_patch", "unsafe_dev")` is True (kill switch ignored only in unsafe_dev).
8. `tool_registry.is_tool_allowed("nonexistent", "read_only")` is False (no exception).
9. `tool_registry.is_tool_allowed("get_health", "bogus_mode")` raises ValueError.
10. `GET /tools/registry` returns `{"ok": True, "tools": [...18...]}`.
11. All 10 above covered by tests.
