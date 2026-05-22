# Phase 8.3 - MCP Invocation Audit Ledger

> Status: design approved 2026-05-22.
> Scope: add a bounded JSONL audit ledger for MCP invocation accountability,
> starting with the Phase 8.2a `create_handoff_note` harness and a read-only
> web route for recent audit events.

## Goal

Record a lightweight audit trail for MCP tool invocations without changing
which MCP tools are exposed or how they are authorized. Phase 8.3 starts with
the only narrow write tool already exposed by the artifact-write server:
`create_handoff_note`.

The audit trail is observability and accountability only. It must make
successful and validation-blocked harness calls visible while avoiding full
prompt capture, secret capture, subprocess execution, or new MCP permissions.

## Non-goals

- Exposing any new MCP write tool
- Exposing `import_worker_run_as_proposal`
- Exposing `validate_imported_worker_proposal`
- Exposing `run_subagent_handoff`
- Exposing `apply_patch`, `apply_patch_plan`, or `dream_apply`
- Promoting or blocking lessons
- Adding approval-token enforcement
- Capturing environment variables
- Logging full secrets or raw long prompts
- Auditing every MCP tool through a generic registration wrapper in this phase
- Adding the optional MCP Audit UI section in this phase

## Architecture

Phase 8.3 adds one focused core module and two integrations:

```text
core/
  mcp_audit.py              # New JSONL ledger, sanitization, listing API

mcp_server/
  artifact_write.py         # Existing create_handoff_note harness records events

web/
  app.py                    # New GET /mcp/audit read-only route
```

`core.mcp_audit` owns storage paths, event construction, string truncation,
append-only JSONL writes, and tolerant JSONL reads. The artifact-write harness
supplies only invocation data at the point where it already knows whether
validation blocked the call or a handoff note was created. The Flask route
delegates directly to `list_mcp_invocations` and does not add a write surface.
Audit persistence failures are swallowed and logged at the harness integration
boundary so observability cannot change the existing handoff result or
validation error behavior.

This avoids two broader alternatives:

- Keeping persistence and redaction logic inline in
  `mcp_server.artifact_write`, which would couple observability policy to one
  server module.
- Wrapping every MCP implementation at registration time, which is useful
  later but broader than a Phase 8.3 ledger seeded by the Phase 8.2a harness.

## Storage

Audit records live under the global agent directory:

```text
.agent/mcp_audit/invocations.jsonl
```

The module resolves that location through the existing `get_agent_dir(None)`
convention used by global `.agent` artifacts.

The file is append-only JSONL. Each successful `record_mcp_invocation` call
appends exactly one JSON object followed by a newline. Listing treats each line
independently so one corrupt line cannot hide the rest of the ledger.

## Public API

`core.mcp_audit` exposes:

```python
def record_mcp_invocation(
    *,
    tool_name: str,
    capability_mode: str,
    allowed: bool,
    input_summary: dict | None = None,
    result_summary: dict | None = None,
    artifacts: list[str] | None = None,
    error: str | None = None,
) -> dict:
    """Append one sanitized invocation event and return it."""


def list_mcp_invocations(limit: int = 50) -> list[dict]:
    """Return recent valid invocation events, newest first."""
```

`record_mcp_invocation` constructs the canonical event. Callers do not provide
`id` or `created_at`.

Each returned and stored event has exactly these ledger fields:

```json
{
  "id": "<event id>",
  "created_at": "<ISO timestamp>",
  "tool_name": "create_handoff_note",
  "capability_mode": "artifact_write",
  "allowed": true,
  "input_summary": {},
  "result_summary": {},
  "artifacts": [],
  "error": null
}
```

`result_summary` is `null` when no result exists. `error` is `null` when the
invocation was not blocked or failed.

## Sanitization

The ledger records summaries, not raw external prompts or ambient process
state.

- Long strings are truncated recursively before storage.
- `context_summary` is hard-capped at 500 characters even though the handoff
  harness accepts larger input.
- Other summary strings and error messages use a bounded audit-string limit so
  a single event cannot grow without limit.
- Summary dicts, nested dicts, lists, booleans, numbers, and `None` stay JSON
  compatible.
- Unexpected summary values are stringified and bounded rather than causing the
  audit path to capture arbitrary object internals.
- No audit API accepts or reads environment variables.

The audit module applies sanitization regardless of whether its caller already
provided a short summary. That makes redaction and size limits a ledger
invariant instead of a harness convention.

## Listing And Failure Tolerance

`list_mcp_invocations` is read-only and defensive:

- Missing audit directory or file returns `[]`.
- Corrupt JSONL lines are skipped.
- Valid JSON objects on other lines are still returned.
- Parsed JSON values that are not dict events are skipped.
- Results are ordered newest-first by file order and capped by `limit`.
- Invalid, non-positive, or oversized route limits are normalized at the route
  boundary so the HTTP endpoint cannot request an unbounded response.

Audit persistence should stay lightweight. A failure to parse an old line must
not break inspection of current events.

## Harness Integration

`mcp_server.artifact_write.create_handoff_note_harness` records only the
Phase 8.2a invocation it owns.

### Successful create

After `core.handoff_notes.create_handoff_note` returns successfully, the
harness records:

- `tool_name="create_handoff_note"`
- `capability_mode=CAPABILITY_MODE`
- `allowed=True`
- sanitized input summary derived from the MCP-facing input dict
- a bounded result summary with success metadata
- `artifacts=[handoff_path]`
- `error=None`

The user-visible harness result stays unchanged:

```json
{
  "ok": true,
  "handoff_path": "<created note>",
  "status": "draft",
  "message": "Handoff note created. This did not run a subagent."
}
```

### Validation block

If harness validation raises `ValueError`, the harness records before re-raising:

- `allowed=False`
- the same tool name and capability mode
- sanitized input summary where possible
- `result_summary=None`
- `artifacts=[]`
- bounded `error=str(validation_error)`

The existing ValueError behavior remains the MCP error path. The audit event is
observational; it does not change validation messages or convert failures into
successful results.

### Audit write failure

If `record_mcp_invocation` itself fails while the harness is recording either
success or a validation block, the harness logs the audit persistence error and
continues its original path:

- successful handoff creation still returns the existing success dict
- blocked validation still raises the original `ValueError`

The audit trail is not an authorization or durability gate for handoff notes in
this phase.

## Web Route

`web.app` adds:

```http
GET /mcp/audit?limit=50
```

The route returns recent valid events from `list_mcp_invocations`. It has no
POST, PUT, PATCH, or DELETE companion and it never executes MCP tools.

Route limit behavior is fixed:

- default is `50`
- maximum is `200`
- invalid and non-positive values fall back to `50`

Response shape:

```json
{
  "ok": true,
  "events": [],
  "count": 0,
  "limit": 50
}
```

The route is for recent inspection only. It does not create an MCP tool and
does not add a control path back into the artifact-write server.

## Permission And Safety Guarantees

Phase 8.3 does not change MCP capability exposure:

- `mcp_server.read_only` still exposes exactly the existing 10 read-only tools.
- `mcp_server.artifact_write` still exposes exactly the existing 11 tools:
  those 10 read-only tools plus `create_handoff_note`.
- Forbidden write, execution, and lesson-state tools remain unexposed.

The audit path must not run subprocesses. Existing handoff harness subprocess
tripwires remain part of the regression surface after audit recording is wired
in.

## Tests

### Audit module

New focused tests for `core.mcp_audit` cover:

- a recorded event is written as JSONL
- `list_mcp_invocations` returns `[]` when the file is missing
- corrupt JSONL lines are skipped while valid lines survive
- long `context_summary` input is truncated at the ledger boundary
- required event fields and `None` summary/error states stay JSON compatible

Tests redirect the audit storage root with monkeypatching so they never write
to the real `.agent/mcp_audit` directory.

### Harness

Existing Phase 8.2a harness tests gain audit expectations:

- a successful `create_handoff_note_harness` call records `allowed=True`
- success includes the created `handoff_path` in event artifacts
- failed validation records `allowed=False` and the validation error
- audit persistence errors do not change harness success or validation failure
  behavior
- the no-subprocess tripwire still passes

### Route

The Flask route tests cover:

- `GET /mcp/audit?limit=50` returns `{ok, events, count, limit}`
- the endpoint remains GET-only
- route limit parsing uses default `50`, max `200`, and default fallback for
  invalid or non-positive values

### MCP surface regressions

Existing MCP server tests remain the permission guardrail:

- no new MCP tools are exposed
- read-only server allowlist is unchanged
- artifact-write server still exposes exactly 11 tools
- forbidden write, execution, apply, and lesson-state tools stay blocked

## Acceptance Criteria

1. `core.mcp_audit.record_mcp_invocation` appends sanitized JSONL events to
   `.agent/mcp_audit/invocations.jsonl`.
2. `core.mcp_audit.list_mcp_invocations(limit=50)` returns recent valid events
   and tolerates missing files and corrupt lines.
3. Stored events contain `id`, `created_at`, `tool_name`, `capability_mode`,
   `allowed`, `input_summary`, `result_summary`, `artifacts`, and `error`.
4. `context_summary` is never stored beyond 500 characters.
5. Audit recording does not read or log environment variables.
6. Successful `create_handoff_note_harness` calls record an allowed event with
   the handoff path in `artifacts`.
7. Harness validation `ValueError` calls record a blocked event and then keep
   raising the original validation error.
8. Audit persistence failures are logged and swallowed by the handoff harness
   integration so success and validation error behavior stay unchanged.
9. `GET /mcp/audit?limit=50` returns recent audit events through a read-only
   endpoint as `{ok, events, count, limit}`.
10. The route limit defaults to `50`, clamps at `200`, and falls back to `50`
    for invalid or non-positive values.
11. The audit work does not run subprocesses through the handoff harness.
12. `mcp_server.read_only` keeps its existing 10-tool surface.
13. `mcp_server.artifact_write` keeps its existing 11-tool surface and exposes
    no additional MCP write or execute tools.
