# Phase 8.2c - MCP Validate Imported Worker Proposal Harness

> Status: design approved 2026-05-23.
> Ship criterion: `mcp_server.artifact_write` exposes exactly 13 tools and
> `validate_imported_worker_proposal` validates an imported proposal only in a
> temp clone, writes validation evidence into the proposal artifact directory,
> and never modifies the real repo, runs subagents, creates lessons, or promotes
> lessons.

## Goal

Expose one additional Phase 8 artifact-write MCP tool:

```text
validate_imported_worker_proposal
```

The tool runs the existing core validation helper against an already-imported
worker proposal. It applies the proposal's `patch_plan.json` in a temp clone,
runs the inferred validation command in that clone, and writes evidence
artifacts back into the proposal directory under `.agent/proposals/`. It does
not touch the real repo, spawn a subagent, or change lesson state.

## Non-goals

- Exposing `run_subagent_handoff`
- Exposing `apply_patch`, `apply_patch_plan`, or `dream_apply`
- Exposing `promote_lesson` or `block_lesson`
- Applying any patch to the real repo
- Auto-creating lessons beyond the existing Phase 7.2.1.1 self-gated
  `case.json` / `patch_proposal.json` files
- Auto-promoting lessons
- Changing `mcp_server.read_only`
- Operating under `unsafe_dev`
- Accepting arbitrary absolute proposal directories from MCP

## Existing Core Boundary

`core.worker_runs.validate_imported_worker_proposal` already owns the
validation behavior:

- accepts a proposal directory under `.agent/proposals/` and a repo path
- path-guards proposal resolution under `.agent/proposals/`
- copies the repo into a temp clone (ignoring `.git`, `.agent`, build caches)
- applies `patch_plan.json` via `run_patch_plan_with_artifacts` inside the
  clone
- infers a validation command via `repo_librarian` and
  `validation_command.get_default_validation_command`
- runs that command in the clone with a bounded timeout
- writes `apply_result.json`, `validation.json`, and `validation_output.txt`
  into the proposal directory
- updates `item.json` validation status
- calls `synthesize_lesson_artifacts_for_validated_worker_proposal`, which
  self-gates on apply success and `validation_ok=True` before writing a
  minimal `case.json` and `patch_proposal.json`; existing files are preserved
  rather than overwritten

Phase 8.2c wraps that core API. It does not duplicate temp-clone logic, patch
application, validation execution, or lesson synthesis.

## Architecture

Phase 8.2c stays inside the existing artifact-write MCP server:

```text
mcp_server/
  artifact_write.py        # extend narrow allowlist + add validate harness

tests/
  test_mcp_artifact_write_server.py
  test_validate_imported_worker_proposal_harness.py
```

The server allowlist remains explicit. `_EXTRA_WRITE_TOOLS` grows from two
tools to three:

```python
_EXTRA_WRITE_TOOLS = (
    "create_handoff_note",
    "import_worker_run_as_proposal",
    "validate_imported_worker_proposal",
)
```

The new public harness mirrors the existing harness pattern:

```python
def validate_imported_worker_proposal_harness(input: dict) -> dict:
    ...
```

The FastMCP-facing impl stays thin:

```python
def _impl_validate_imported_worker_proposal(input: dict) -> dict:
    return validate_imported_worker_proposal_harness(input)
```

## MCP Input Contract

The harness accepts exactly two fields:

```json
{
  "proposal_ref": "20260523_115045/01-review-cpp-account-interest-benchmark-flow",
  "repo_path": "C:\\Users\\Admin\\Documents\\Code\\day 14\\AI project"
}
```

Allowed input fields:

```python
_VALIDATE_IMPORTED_PROPOSAL_ALLOWED_INPUT_FIELDS = frozenset({
    "proposal_ref",
    "repo_path",
})
```

`proposal_ref` is a relative path inside `.agent/proposals/` with the natural
two-segment shape `<run_timestamp>/<item_subdir>`. Slashes are valid; only
unsafe segments are rejected.

Validation rules:

- `input` must be a dict
- unknown fields raise `ValueError`
- `proposal_ref` is required and must be a non-empty trimmed string
- `Path(proposal_ref).is_absolute()` is rejected
- normalized form `proposal_ref.replace("\\", "/")` must not start with `/`
- splitting the normalized form by `/` must yield at least one segment
- no segment may be empty, `.`, or `..`
- `repo_path` is required and must be a non-empty trimmed string
- `repo_path` may be an absolute filesystem path but must resolve to an
  existing directory; non-directory `repo_path` is rejected

The existing core helper remains the second path-safety gate; if a malformed
`proposal_ref` ever escaped the harness shape check, core's
`_resolve_proposal_dir` would still reject it.

## Harness Behavior

For a valid input the harness calls:

```python
from core.worker_runs import validate_imported_worker_proposal as _core_validate

result = _core_validate(
    proposal_dir=proposal_ref,   # relative; core resolves under proposals root
    repo_path=repo_path,
    proposals_root=None,         # tests monkeypatch worker_runs.DEFAULT_PROPOSALS_ROOT
)
```

The harness does not pass `proposals_root` itself. It lets core resolve
`proposal_ref` under `worker_runs.DEFAULT_PROPOSALS_ROOT` so tests can swap the
default without touching MCP input.

Core returns a richer dict. The MCP harness response is narrow:

```json
{
  "ok": true,
  "proposal_dir": "<resolved proposal directory>",
  "apply_success": true,
  "validation_ok": true,
  "message": "Apply and validation passed.",
  "artifacts": [
    "<proposal_dir>",
    "<proposal_dir>/apply_result.json",
    "<proposal_dir>/validation.json",
    "<proposal_dir>/validation_output.txt"
  ]
}
```

`validation_ok` is `true`, `false`, or `null`. `null` is the legitimate value
when the core helper skipped validation (apply failed or no validation
command could be inferred).

`artifacts` only lists files that actually exist on disk after core returns.
Phase 7.2.1.1 success-gated `case.json` and `patch_proposal.json` appear only
when core's lesson-artifact synthesizer self-promotes them; the harness never
forces their creation.

The harness does not call:

- `run_subagent_handoff` or any worker launcher
- any real-repo patch apply path
- any lesson creation, promotion, or block helper

Apply failures and validation failures are propagated structurally rather
than via exceptions: the core helper writes failure artifacts and returns
`apply_success=False` or `validation_ok=False`, and the harness mirrors that
shape with `ok: true`. Genuine input validation failures and missing-proposal
failures still raise `ValueError` and `FileNotFoundError`.

## Audit

Phase 8.3 audit logging covers the new harness at the artifact-write boundary.

Success event:

- `tool_name="validate_imported_worker_proposal"`
- `capability_mode="artifact_write"`
- `allowed=True`
- input summary includes the bounded `proposal_ref` and `repo_path` basename
- input summary does not include validation output contents
- result summary contains the narrow response fields (`ok`, `apply_success`,
  `validation_ok`, `message`)
- `artifacts` lists every validation artifact path that exists on disk after
  core returns
- `error=None`

Blocked event:

- input validation or core rejection records `allowed=False`
- `result_summary=None`
- `artifacts=[]`
- `error` contains the bounded rejection message
- the original exception is re-raised

Audit persistence is observational. If recording fails, the harness logs and
swallows the audit failure so the harness success or harness rejection
behavior stays unchanged.

## MCP Surface

`mcp_server.artifact_write` exposes exactly 13 tools:

| Surface slice | Count |
|---|---:|
| read-only tools reused from `mcp_server.read_only` | 10 |
| `create_handoff_note` | 1 |
| `import_worker_run_as_proposal` | 1 |
| `validate_imported_worker_proposal` | 1 |
| total | 13 |

`mcp_server.read_only` remains exactly 10 tools and omits all three
artifact-write tools.

The artifact-write server continues to omit:

- `run_subagent_handoff`
- `apply_patch`
- `apply_patch_plan`
- `dream_apply`
- `promote_lesson`
- `block_lesson`

## Safety

Phase 8.2c relies on an already-isolated core validation path. The MCP harness
must keep these properties visible in tests:

- validation runs entirely inside the temp clone created by core
- the real repo (`repo_path`) is byte-identical before and after the call
- no subagent launcher is invoked (the subprocess used by the validation
  command runs in the temp clone and is part of the core's existing behavior;
  it is not a forbidden subagent spawn)
- no lesson store write or promote helper is invoked
- only Phase 7.2.1.1 self-gated `case.json` / `patch_proposal.json` may be
  created, and only when core's synthesizer self-approves them
- `proposal_ref` cannot escape `.agent/proposals/` via traversal or absolute
  path because the harness validates shape and core re-validates resolution

## Tests

### MCP surface tests

`tests/test_mcp_artifact_write_server.py` changes its explicit surface
expectation from 12 to 13 names and adds `validate_imported_worker_proposal`
to `_EXPECTED_EXPOSED_TOOLS`. The name is removed from `_FORBIDDEN_TOOLS`.

It continues to assert that forbidden tools stay absent:

- `run_subagent_handoff`
- `apply_patch`
- `apply_patch_plan`
- `dream_apply`
- `promote_lesson`
- `block_lesson`

The read-only regression checks assert that all three artifact-write tools
remain absent from the 10-tool read-only server, and that the read-only
server still exposes exactly 10 tools.

### Validation harness tests

New harness tests use temporary worker-runs, proposal, handoff, and fake-repo
roots so they do not write real `.agent` artifacts. The fake repo carries a
real source file that the patch_plan can target so apply can actually succeed
inside the temp clone.

Coverage:

- valid imported proposal validates in temp clone and writes
  `apply_result.json`, `validation.json`, `validation_output.txt` into the
  proposal directory
- real repo state is byte-identical before and after validation
- missing `proposal_ref` is rejected with `ValueError`
- absolute `proposal_ref` is rejected
- traversal-shaped `proposal_ref` (`..`, `.`, `..\\escape`) is rejected
- unknown input field is rejected
- missing `repo_path` is rejected
- non-directory `repo_path` is rejected
- failed apply returns a structured response with `apply_success=False`
  without crashing, when core's behavior allows it
- success audit event records `allowed=True` with validation artifact paths
- blocked audit event records `allowed=False`
- audit persistence failure does not change harness success or rejection
- no subagent launcher (`run_subagent_handoff` import path) is invoked
- no lesson store write or promote helper is invoked

The "no subprocess" assertion does not apply here. Validation legitimately
runs the inferred validation command as a subprocess inside the temp clone.
Tripwires target subagent and worker launchers, not `subprocess.run`.

## Acceptance Criteria

1. `mcp_server.artifact_write.list_exposed_tool_names()` returns exactly 13
   tools.
2. The 13-tool artifact-write surface contains only the 10 read-only tools,
   `create_handoff_note`, `import_worker_run_as_proposal`, and
   `validate_imported_worker_proposal`.
3. `mcp_server.read_only` remains exactly 10 tools and omits all three
   artifact-write tools.
4. `run_subagent_handoff`, apply tools, and lesson-state tools remain absent
   from the artifact-write MCP server.
5. `validate_imported_worker_proposal_harness` accepts only a strict
   `{proposal_ref, repo_path}` input dict.
6. A valid imported proposal validates in a temp clone and writes
   `apply_result.json`, `validation.json`, and `validation_output.txt` into
   its proposal directory.
7. The real repo at `repo_path` is byte-identical before and after the call.
8. `case.json` and `patch_proposal.json` appear only when core's existing
   Phase 7.2.1.1 self-gated synthesizer approves them.
9. The harness does not invoke subagent launchers, apply patches to the real
   repo, or create/promote lessons.
10. Successful and blocked validation attempts are recorded in the MCP audit
    ledger.
11. Audit write failures are swallowed/logged without changing harness
    results.
