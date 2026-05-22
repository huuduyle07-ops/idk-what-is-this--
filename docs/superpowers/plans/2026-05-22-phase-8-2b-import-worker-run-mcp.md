# Phase 8.2b Import Worker Run MCP Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose `import_worker_run_as_proposal` as the second narrow artifact-write MCP tool while preserving the 10-tool read-only surface and proposal-copy-only behavior.

**Architecture:** Extend the explicit `_EXTRA_WRITE_TOOLS` gate in `mcp_server.artifact_write`, add a strict `worker_run_id`-only harness beside the handoff harness, and delegate actual import I/O to `core.worker_runs.import_worker_run_as_proposal`. The harness adds MCP validation, Phase 8.3 audit logging, and fail-open audit persistence behavior without validating proposals, running subprocesses, touching the real repo, or creating lesson-ready artifacts.

**Tech Stack:** Python, pytest, FastMCP allowlist tests, existing `core.worker_runs` artifact import helpers.

**Spec:** `docs/superpowers/specs/2026-05-22-phase-8-2b-import-worker-run-mcp-design.md`

---

## File Map

- Modify `mcp_server/artifact_write.py`: second explicit write allowlist entry, import harness, audit helper, thin MCP impl, `_IMPLS` entry.
- Modify `tests/test_mcp_artifact_write_server.py`: artifact-write surface becomes exactly 12; read-only still exactly 10; forbidden tools remain absent.
- Create `tests/test_import_worker_run_as_proposal_harness.py`: strict input, import success/rejections, proposal artifact output, audit, subprocess, repo snapshot tests.
- Keep `core/worker_runs.py` unchanged: it already owns completeness, dry-run, root guarding, and copy behavior.

## Task 1: Lock The 12-Tool Surface

**Files:**
- Modify: `tests/test_mcp_artifact_write_server.py`
- Modify: `mcp_server/artifact_write.py`

- [ ] **Step 1: Write failing surface tests**

Update the explicit expected surface to include the new import tool and expect
12 names:

```python
_EXPECTED_EXPOSED_TOOLS = {
    "get_health",
    "list_benchmark_reports",
    "read_benchmark_report",
    "list_dream_reports",
    "read_dream_report",
    "list_lessons",
    "read_lesson_proposal",
    "list_worker_runs",
    "read_worker_run",
    "list_tool_registry",
    "create_handoff_note",
    "import_worker_run_as_proposal",
}
```

Keep only forbidden tools in `_FORBIDDEN_TOOLS`:

```python
_FORBIDDEN_TOOLS = {
    "validate_imported_worker_proposal",
    "run_subagent_handoff",
    "apply_patch",
    "apply_patch_plan",
    "dream_apply",
    "promote_lesson",
    "block_lesson",
}
```

Add the read-only regression:

```python
def test_read_only_server_still_omits_artifact_write_tools():
    from mcp_server import read_only
    assert "create_handoff_note" not in read_only.list_exposed_tool_names()
    assert "import_worker_run_as_proposal" not in read_only.list_exposed_tool_names()
    assert len(read_only.list_exposed_tool_names()) == 10
```

- [ ] **Step 2: Run the surface test red**

Run:

```powershell
python -m pytest tests\test_mcp_artifact_write_server.py -v
```

Expected: explicit 12-tool assertions fail because the artifact-write allowlist
still exposes only 11 tools.

- [ ] **Step 3: Make the smallest allowlist change**

In `mcp_server/artifact_write.py`:

```python
_EXTRA_WRITE_TOOLS: tuple[str, ...] = (
    "create_handoff_note",
    "import_worker_run_as_proposal",
)
```

The server remains incomplete until the harness `_IMPLS` entry lands in Task 2,
but the explicit exposed-name contract becomes visible here.

- [ ] **Step 4: Re-run the surface test**

Run:

```powershell
python -m pytest tests\test_mcp_artifact_write_server.py -v
```

Expected: explicit allowlist-name tests pass, forbidden-tool tests stay green.

## Task 2: Strict Import Harness And Audit

**Files:**
- Create: `tests/test_import_worker_run_as_proposal_harness.py`
- Modify: `mcp_server/artifact_write.py`

- [ ] **Step 1: Add failing harness tests**

Use temporary roots and core fixtures shaped like existing worker-run tests:

```python
@pytest.fixture
def env(tmp_path, monkeypatch):
    worker_runs_root = tmp_path / "worker_runs"
    proposals_root = tmp_path / "proposals"
    handoff_root = tmp_path / "handoffs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(worker_runs, "DEFAULT_WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(worker_runs, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(artifact_write, "record_mcp_invocation", lambda **_kwargs: None)
    return {...}
```

Required red cases:

```python
def test_valid_import_creates_review_proposal(env):
    _make_run(env, "20260521_010203_imp")
    result = import_worker_run_as_proposal_harness(
        {"worker_run_id": "20260521_010203_imp"}
    )
    proposal_dir = Path(result["proposal_dir"])
    assert result == {
        "ok": True,
        "proposal_dir": str(proposal_dir),
        "message": "Worker run imported as proposal. Review it before validation or lesson creation.",
    }
    assert (proposal_dir / "proposal.md").is_file()
    for name in ("validation.json", "apply_result.json", "case.json", "patch_proposal.json"):
        assert not (proposal_dir / name).exists()
```

```python
def test_incomplete_worker_run_is_rejected(env): ...
def test_dry_run_worker_run_is_rejected(env): ...
def test_worker_run_id_traversal_is_rejected(env): ...
def test_worker_run_id_absolute_path_is_rejected(env): ...
def test_unknown_input_field_is_rejected(env): ...
def test_harness_does_not_invoke_subprocess(env, monkeypatch): ...
def test_harness_does_not_modify_real_repo(env): ...
def test_success_records_audit_event(env, monkeypatch): ...
def test_blocked_import_records_audit_event(env, monkeypatch): ...
def test_audit_write_failure_keeps_import_success(env, monkeypatch): ...
def test_audit_write_failure_keeps_import_error(env, monkeypatch): ...
```

- [ ] **Step 2: Run the harness test red**

Run:

```powershell
python -m pytest tests\test_import_worker_run_as_proposal_harness.py -v
```

Expected: import failure because
`import_worker_run_as_proposal_harness` does not exist yet.

- [ ] **Step 3: Implement strict input validation**

In `mcp_server/artifact_write.py`, add:

```python
_IMPORT_WORKER_RUN_ALLOWED_INPUT_FIELDS: frozenset[str] = frozenset({
    "worker_run_id",
})

def _validate_worker_run_id(input: Any) -> str:
    if not isinstance(input, dict):
        raise ValueError(f"input must be a dict, got {type(input).__name__}")
    unknown = set(input) - _IMPORT_WORKER_RUN_ALLOWED_INPUT_FIELDS
    if unknown:
        raise ValueError(f"unknown field(s): {sorted(unknown)}")
    raw = input.get("worker_run_id")
    if not isinstance(raw, str):
        raise ValueError("worker_run_id is required and must be a string")
    worker_run_id = raw.strip()
    if not worker_run_id:
        raise ValueError("worker_run_id is required and must be non-empty")
    if Path(worker_run_id).is_absolute():
        raise ValueError("worker_run_id must be a relative run id")
    if "/" in worker_run_id or "\\" in worker_run_id:
        raise ValueError("worker_run_id must not contain path separators")
    if worker_run_id in {".", ".."}:
        raise ValueError("worker_run_id is not a safe run id")
    return worker_run_id
```

- [ ] **Step 4: Implement the audit helper and harness**

Use a sibling helper pattern to the handoff audit integration:

```python
def _record_worker_run_import_audit(...):
    try:
        record_mcp_invocation(
            tool_name="import_worker_run_as_proposal",
            capability_mode=CAPABILITY_MODE,
            allowed=allowed,
            input_summary=_worker_run_import_input_summary(input),
            result_summary=result_summary,
            artifacts=artifacts or [],
            error=error,
        )
    except Exception:
        logger.warning("failed to record import_worker_run_as_proposal MCP audit event", exc_info=True)
```

```python
def import_worker_run_as_proposal_harness(input: dict) -> dict:
    try:
        worker_run_id = _validate_worker_run_id(input)
        from core.worker_runs import import_worker_run_as_proposal as _core_import
        result = _core_import(worker_run_id)
    except (FileNotFoundError, ValueError) as error:
        _record_worker_run_import_audit(input, allowed=False, error=str(error))
        raise
    response = {
        "ok": True,
        "proposal_dir": result["proposal_dir"],
        "message": "Worker run imported as proposal. Review it before validation or lesson creation.",
    }
    _record_worker_run_import_audit(
        input,
        allowed=True,
        result_summary={"ok": True, "message": response["message"]},
        artifacts=[response["proposal_dir"]],
    )
    return response
```

- [ ] **Step 5: Wire the MCP impl**

Add:

```python
def _impl_import_worker_run_as_proposal(input: dict) -> dict:
    return import_worker_run_as_proposal_harness(input)
```

and `_IMPLS["import_worker_run_as_proposal"]`.

- [ ] **Step 6: Run the harness tests green**

Run:

```powershell
python -m pytest tests\test_import_worker_run_as_proposal_harness.py -v
```

Expected: the strict harness, safety, audit, and artifact absence tests pass.

## Task 3: Verification

- [ ] **Step 1: Run focused Phase 8.2b verification**

```powershell
python -m pytest tests\test_import_worker_run_as_proposal_harness.py tests\test_mcp_artifact_write_server.py -v
```

- [ ] **Step 2: Run read-only and existing audit/handoff regressions**

```powershell
python -m pytest tests\test_mcp_readonly_server.py tests\test_create_handoff_note_harness.py tests\test_mcp_audit.py -v
```

- [ ] **Step 3: Inspect the diff**

Confirm:

- `_EXTRA_WRITE_TOOLS` contains only the two allowed artifact-write tools
- `_IMPLS` adds only `import_worker_run_as_proposal`
- no `validate_imported_worker_proposal` exposure was added
- no subprocess or lesson-creation call was added
- no UI or read-only MCP module changes were made
