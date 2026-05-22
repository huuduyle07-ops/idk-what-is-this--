# Phase 8.2b - MCP Import Worker Run Harness

> Status: design approved 2026-05-22.
> Ship criterion: `mcp_server.artifact_write` exposes exactly 12 tools and
> `import_worker_run_as_proposal` only copies an existing complete worker run
> into `.agent/proposals/` with audit logging, no subprocess, no real-repo
> write, no validation, and no lesson creation.

## Goal

Expose one additional Phase 8 artifact-write MCP tool:

```text
import_worker_run_as_proposal
```

The tool turns an already-complete worker-run artifact into an imported
proposal artifact for operator review. It does not validate the proposal,
execute another worker, apply a patch, create a lesson, or promote memory.

## Non-goals

- Exposing `validate_imported_worker_proposal`
- Exposing `run_subagent_handoff`
- Exposing `apply_patch`, `apply_patch_plan`, or `dream_apply`
- Exposing `promote_lesson` or `block_lesson`
- Adding validation subprocess execution
- Touching the real repo
- Auto-creating or auto-promoting lessons
- Changing `mcp_server.read_only`
- Expanding the MCP input to accept arbitrary worker-run paths or `repo_path`

## Existing Core Boundary

`core.worker_runs.import_worker_run_as_proposal` already owns the import
behavior:

- accepts a worker run id under the configured worker-runs root
- rejects incomplete worker outputs
- rejects dry-run worker outputs
- path-guards worker-run resolution under `.agent/worker_runs/`
- copies the existing worker-run artifacts into `.agent/proposals/`
- writes proposal import metadata for downstream review

Phase 8.2b wraps that core API. It does not duplicate the copy logic or add a
second validation path.

## Architecture

Phase 8.2b stays inside the existing artifact-write MCP server:

```text
mcp_server/
  artifact_write.py        # extend narrow allowlist + add import harness

tests/
  test_mcp_artifact_write_server.py
  test_import_worker_run_as_proposal_harness.py
```

The server allowlist remains explicit. `_EXTRA_WRITE_TOOLS` grows from one tool
to two:

```python
_EXTRA_WRITE_TOOLS = (
    "create_handoff_note",
    "import_worker_run_as_proposal",
)
```

The new public harness mirrors the existing `create_handoff_note` harness
pattern:

```python
def import_worker_run_as_proposal_harness(input: dict) -> dict:
    ...
```

The FastMCP-facing impl stays thin:

```python
def _impl_import_worker_run_as_proposal(input: dict) -> dict:
    return import_worker_run_as_proposal_harness(input)
```

## MCP Input Contract

The harness accepts exactly one input shape:

```json
{
  "worker_run_id": "20260521_010203_imp"
}
```

No `repo_path`, worker-runs-root override, proposal-root override, absolute
path, or arbitrary path is exposed through MCP.

Validation rules:

- `input` must be a dict
- unknown fields raise `ValueError`
- `worker_run_id` is required
- `worker_run_id` must be a non-empty string after trimming
- absolute paths are rejected
- values with `/` or `\` path separators are rejected
- traversal-shaped ids such as `.` or `..` are rejected before reaching core

The existing core importer remains the second path-safety gate.

## Harness Behavior

For a valid input the harness calls:

```python
core.worker_runs.import_worker_run_as_proposal(worker_run_id)
```

Core returns a richer import result, but the MCP harness response is narrow:

```json
{
  "ok": true,
  "proposal_dir": "<imported proposal directory>",
  "message": "Worker run imported as proposal. Review it before validation or lesson creation."
}
```

The harness does not call:

- `validate_imported_worker_proposal`
- any patch apply path
- any subprocess runner
- any lesson creation or lesson promotion path

Import errors from core preserve the existing behavior. Incomplete imports keep
raising `FileNotFoundError`; dry-run imports keep raising `ValueError`.

## Audit

Phase 8.3 audit logging covers the new harness at the artifact-write boundary.

Success event:

- `tool_name="import_worker_run_as_proposal"`
- `capability_mode="artifact_write"`
- `allowed=True`
- input summary includes the bounded `worker_run_id`
- result summary contains imported-proposal success metadata
- `artifacts=[proposal_dir]`
- `error=None`

Blocked event:

- validation or core import rejection records `allowed=False`
- `result_summary=None`
- `artifacts=[]`
- `error` contains the bounded rejection message
- the original exception is re-raised

Audit persistence is observational. If recording fails, the harness logs and
swallows the audit failure so import success or import rejection behavior stays
unchanged.

## MCP Surface

`mcp_server.artifact_write` exposes exactly 12 tools:

| Surface slice | Count |
|---|---:|
| read-only tools reused from `mcp_server.read_only` | 10 |
| `create_handoff_note` | 1 |
| `import_worker_run_as_proposal` | 1 |
| total | 12 |

`mcp_server.read_only` remains exactly 10 tools and omits both artifact-write
tools.

The artifact-write server continues to omit:

- `validate_imported_worker_proposal`
- `run_subagent_handoff`
- `apply_patch`
- `apply_patch_plan`
- `dream_apply`
- `promote_lesson`
- `block_lesson`

## Safety

Phase 8.2b reuses an artifact-only core import path. The MCP harness must keep
these properties visible in tests:

- valid import writes proposal artifacts only
- no subprocess helper is invoked
- source worker run is copied rather than executed
- real-repo files remain byte-identical
- no validation or lesson-ready artifacts are created by the harness:
  `validation.json`, `apply_result.json`, `case.json`, and
  `patch_proposal.json` stay absent after import
- no lesson artifacts are created or promoted by the harness

## Tests

### MCP surface tests

`tests/test_mcp_artifact_write_server.py` changes its explicit surface
expectation from 11 to 12 names and adds
`import_worker_run_as_proposal` to the expected set.

It continues to assert that forbidden tools stay absent, especially:

- `validate_imported_worker_proposal`
- `run_subagent_handoff`
- `apply_patch`
- `promote_lesson`

The read-only regression checks assert that both `create_handoff_note` and
`import_worker_run_as_proposal` remain absent from the 10-tool read-only
server.

### Import harness tests

New harness tests use temporary worker-runs, proposal, handoff, and fake-repo
roots so they do not write real `.agent` artifacts.

Coverage:

- valid worker-run import creates a proposal artifact and returns the narrow
  success response
- incomplete worker run is rejected
- dry-run worker run is rejected
- traversal-shaped `worker_run_id` is rejected
- absolute `worker_run_id` is rejected
- unknown input fields are rejected
- subprocess tripwires stay quiet
- fake real-repo state stays unchanged
- imported proposal output omits `validation.json`, `apply_result.json`,
  `case.json`, and `patch_proposal.json`
- success audit event records `allowed=True` and `proposal_dir`
- blocked audit event records `allowed=False`
- audit persistence failures do not change success or blocked behavior

## Acceptance Criteria

1. `mcp_server.artifact_write.list_exposed_tool_names()` returns exactly 12
   tools.
2. The 12-tool artifact-write surface contains only the 10 read-only tools,
   `create_handoff_note`, and `import_worker_run_as_proposal`.
3. `mcp_server.read_only` remains exactly 10 tools and omits both
   artifact-write tools.
4. `validate_imported_worker_proposal`, `run_subagent_handoff`, apply tools,
   and lesson-state tools remain absent from the artifact-write MCP server.
5. `import_worker_run_as_proposal_harness` accepts only a strict
   `worker_run_id` input dict.
6. A complete non-dry-run worker run is copied into `.agent/proposals/` and
   returns the narrow success response.
7. Incomplete and dry-run worker runs preserve existing core rejection
   behavior.
8. The harness does not run subprocesses, validate proposals, write the real
   repo, or create/promote lessons.
9. Successful and blocked import attempts are recorded in the MCP audit ledger.
10. Audit write failures are swallowed/logged without changing harness results.
