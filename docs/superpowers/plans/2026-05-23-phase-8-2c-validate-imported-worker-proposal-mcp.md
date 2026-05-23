# Phase 8.2c - MCP Validate Imported Worker Proposal Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose `validate_imported_worker_proposal` as the 13th tool on the artifact-write MCP server, wrapping the existing core helper with input validation, narrow response shaping, and audit logging.

**Architecture:** Add a thin harness inside `mcp_server/artifact_write.py` that validates input shape, delegates to `core.worker_runs.validate_imported_worker_proposal` (which already runs in a temp clone and writes evidence artifacts under `.agent/proposals/<run>/<item>/`), then returns a narrow response and records the audit event. No new files in `mcp_server/`; one new test file in `tests/`.

**Tech Stack:** Python 3.13, pytest, `mcp_server.artifact_write`, `core.worker_runs.validate_imported_worker_proposal`, `core.mcp_audit.record_mcp_invocation`. The tool is already registered with `mcp_exposable=True, category="artifact_write"` in `core/tool_registry.py:291`.

**Spec:** `docs/superpowers/specs/2026-05-23-phase-8-2c-validate-imported-worker-proposal-mcp-design.md`

---

## File Plan

| File | Action | Responsibility |
|---|---|---|
| `mcp_server/artifact_write.py` | Modify | Add `validate_imported_worker_proposal` to `_EXTRA_WRITE_TOOLS`, four new helpers, the public harness, and a thin `_impl_*` wrapper registered in `_IMPLS`. |
| `tests/test_mcp_artifact_write_server.py` | Modify | Bump surface expectations from 12 to 13; move `validate_imported_worker_proposal` from `_FORBIDDEN_TOOLS` to `_EXPECTED_EXPOSED_TOOLS`. |
| `tests/test_validate_imported_worker_proposal_harness.py` | Create | All harness behavior + audit + safety tests. |

---

## Task 1: Bump artifact-write MCP surface to 13 tools

**Files:**
- Modify: `tests/test_mcp_artifact_write_server.py`
- Modify: `mcp_server/artifact_write.py:40-43` (the `_EXTRA_WRITE_TOOLS` tuple) and `mcp_server/artifact_write.py:425-438` (the `_IMPLS` dict)

- [ ] **Step 1: Update the expected/forbidden sets in the surface test**

Edit `tests/test_mcp_artifact_write_server.py` lines 16-40 so the expected set includes `validate_imported_worker_proposal` and the forbidden set drops it:

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
    "validate_imported_worker_proposal",
}

# Tools that must NEVER be exposed by the artifact-write MCP server.
_FORBIDDEN_TOOLS = {
    "run_subagent_handoff",
    "apply_patch",
    "apply_patch_plan",
    "dream_apply",
    "promote_lesson",
    "block_lesson",
}
```

- [ ] **Step 2: Update the "exactly N" surface tests**

Rename `test_exposed_names_are_exactly_twelve` to `test_exposed_names_are_exactly_thirteen` (line 69) and bump the count assertion:

```python
def test_exposed_names_are_exactly_thirteen():
    from mcp_server import artifact_write
    assert set(artifact_write.list_exposed_tool_names()) == _EXPECTED_EXPOSED_TOOLS
    assert len(artifact_write.list_exposed_tool_names()) == 13
```

Add a new exposure regression assertion next to `test_import_worker_run_as_proposal_is_exposed` (line 80):

```python
def test_validate_imported_worker_proposal_is_exposed():
    from mcp_server import artifact_write
    assert "validate_imported_worker_proposal" in artifact_write.list_exposed_tool_names()
```

Update the read-only cross-server regression (line 91) so it covers the new tool too:

```python
def test_read_only_server_still_omits_artifact_write_tools():
    """Cross-server regression: the read-only server must not gain
    artifact-write tools just because the artifact-write module exists."""
    from mcp_server import read_only
    assert "create_handoff_note" not in read_only.list_exposed_tool_names()
    assert "import_worker_run_as_proposal" not in read_only.list_exposed_tool_names()
    assert "validate_imported_worker_proposal" not in read_only.list_exposed_tool_names()
    # And the read-only server should still expose exactly 10.
    assert len(read_only.list_exposed_tool_names()) == 10
```

Rename `test_list_tools_flag_prints_twelve_names` to `test_list_tools_flag_prints_thirteen_names` (line 154). The body already compares against `_EXPECTED_EXPOSED_TOOLS`, so only the function name needs to change.

- [ ] **Step 3: Run the surface tests to confirm they fail in the expected way**

Run: `python -m pytest tests/test_mcp_artifact_write_server.py -v`

Expected: failures on `test_exposed_names_are_exactly_thirteen`, `test_validate_imported_worker_proposal_is_exposed`, and the renamed `--list-tools` test. The assertion message should mention the missing `validate_imported_worker_proposal` or the count `12 != 13`.

- [ ] **Step 4: Extend `_EXTRA_WRITE_TOOLS` and add a stub impl**

Edit `mcp_server/artifact_write.py` lines 40-43 to grow the tuple:

```python
_EXTRA_WRITE_TOOLS: tuple[str, ...] = (
    "create_handoff_note",
    "import_worker_run_as_proposal",
    "validate_imported_worker_proposal",
)
```

Edit lines 425-438 to add a placeholder impl and register it in `_IMPLS`. Place the impl right after `_impl_import_worker_run_as_proposal` (around line 420):

```python
def _impl_validate_imported_worker_proposal(input: dict) -> dict:
    """MCP-registered impl for the narrow worker-proposal validation harness."""
    return validate_imported_worker_proposal_harness(input)
```

Extend `_IMPLS`:

```python
_IMPLS: dict[str, Callable[..., Any]] = {
    "get_health": read_only._impl_get_health,
    "list_benchmark_reports": read_only._impl_list_benchmark_reports,
    "read_benchmark_report": read_only._impl_read_benchmark_report,
    "list_dream_reports": read_only._impl_list_dream_reports,
    "read_dream_report": read_only._impl_read_dream_report,
    "list_lessons": read_only._impl_list_lessons,
    "read_lesson_proposal": read_only._impl_read_lesson_proposal,
    "list_worker_runs": read_only._impl_list_worker_runs,
    "read_worker_run": read_only._impl_read_worker_run,
    "list_tool_registry": read_only._impl_list_tool_registry,
    "create_handoff_note": _impl_create_handoff_note,
    "import_worker_run_as_proposal": _impl_import_worker_run_as_proposal,
    "validate_imported_worker_proposal": _impl_validate_imported_worker_proposal,
}
```

`validate_imported_worker_proposal_harness` does not exist yet. The module would fail to import. Add a temporary placeholder right after `import_worker_run_as_proposal_harness` (around line 402) so the surface tests can run:

```python
def validate_imported_worker_proposal_harness(input: dict) -> dict:
    """Phase 8.2c placeholder — implemented in Task 2."""
    raise NotImplementedError("validate_imported_worker_proposal_harness")
```

- [ ] **Step 5: Run the surface tests to confirm they pass**

Run: `python -m pytest tests/test_mcp_artifact_write_server.py -v`

Expected: all surface tests pass, including the 13-name assertions and the read-only cross-server regression.

- [ ] **Step 6: Commit**

```bash
git add tests/test_mcp_artifact_write_server.py mcp_server/artifact_write.py
git commit -m "Phase 8.2c step 1: register validate_imported_worker_proposal in MCP surface

Expand mcp_server.artifact_write to 13 tools by adding validate_imported_worker_proposal
to _EXTRA_WRITE_TOOLS and _IMPLS with a placeholder harness. Update the surface tests
to expect 13 tools and assert the new tool is exposed; keep read_only at 10 tools.
The harness body is implemented in the next steps."
```

---

## Task 2: Input validation + harness skeleton (happy path)

**Files:**
- Create: `tests/test_validate_imported_worker_proposal_harness.py`
- Modify: `mcp_server/artifact_write.py` — add four helpers and flesh out the harness

- [ ] **Step 1: Create the harness test fixture and happy-path test**

Create `tests/test_validate_imported_worker_proposal_harness.py`:

```python
"""Phase 8.2c tests for the MCP validate_imported_worker_proposal harness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import handoff_notes, worker_runs
from mcp_server import artifact_write
from mcp_server.artifact_write import validate_imported_worker_proposal_harness


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    worker_runs_root = tmp_path / "worker_runs"
    proposals_root = tmp_path / "proposals"
    handoff_root = tmp_path / "handoffs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(worker_runs, "DEFAULT_WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(worker_runs, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **_kwargs: None,
        raising=False,
    )
    # Force "no validation command" so the happy path never spawns a real
    # validator subprocess (which would slow down or fail in test envs).
    monkeypatch.setattr(
        worker_runs,
        "_inferred_validation_command",
        lambda _repo: "",
        raising=False,
    )

    return {
        "worker_runs_root": worker_runs_root,
        "proposals_root": proposals_root,
        "handoff_root": handoff_root,
        "fake_repo": fake_repo,
    }


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_imported_proposal(env, run_id: str = "20260523_120000_val") -> str:
    """Create a complete worker run and import it as a proposal.

    Returns the relative `proposal_ref` (run_timestamp/item_subdir) suitable
    for the validate harness MCP input.
    """
    run_dir = env["worker_runs_root"] / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    note = handoff_notes.create_handoff_note(
        title="Validate imported proposal",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(env["fake_repo"]),
        handoff_root=env["handoff_root"],
    )
    (run_dir / "handoff.md").write_text(
        Path(note["path"]).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_json(run_dir / "worker_run.json", {
        "dry_run": False,
        "worker": "codex",
        "command": "codex exec",
        "handoff_path": note["path"],
        "artifact_dir": str(run_dir),
    })
    (run_dir / "raw_output.txt").write_text("worker output\n", encoding="utf-8")
    (run_dir / "proposal.md").write_text("# Worker proposal\n", encoding="utf-8")
    _write_json(run_dir / "patch_plan.json", [{
        "op": "replace_snippet",
        "relative_path": "src/foo.py",
        "target_snippet": "x = 1",
        "patched_snippet": "x = 2",
    }])

    imported = worker_runs.import_worker_run_as_proposal(run_id)
    proposal_dir = Path(imported["proposal_dir"])
    return proposal_dir.relative_to(env["proposals_root"]).as_posix()


def _repo_state(repo: Path) -> dict[str, str]:
    return {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in repo.rglob("*")
        if path.is_file()
    }


def test_valid_proposal_validates_in_temp_clone_and_writes_artifacts(env):
    proposal_ref = _make_imported_proposal(env)

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    proposal_dir = Path(result["proposal_dir"])
    assert result["ok"] is True
    assert result["apply_success"] is True
    # No validation command inferred -> validation_ok is None (legitimate).
    assert result["validation_ok"] is None
    assert "no validation command" in result["message"].lower()
    assert (proposal_dir / "apply_result.json").is_file()
    assert (proposal_dir / "validation.json").is_file()
    assert (proposal_dir / "validation_output.txt").is_file()
    # Lesson-synth files must NOT exist when validation didn't pass.
    assert not (proposal_dir / "case.json").exists()
    assert not (proposal_dir / "patch_proposal.json").exists()
    # Artifacts list reflects what actually exists on disk.
    assert str(proposal_dir) in result["artifacts"]
    assert str(proposal_dir / "apply_result.json") in result["artifacts"]
    assert str(proposal_dir / "validation.json") in result["artifacts"]
    assert str(proposal_dir / "validation_output.txt") in result["artifacts"]
```

- [ ] **Step 2: Run the happy-path test to confirm it fails**

Run: `python -m pytest tests/test_validate_imported_worker_proposal_harness.py::test_valid_proposal_validates_in_temp_clone_and_writes_artifacts -v`

Expected: FAIL with `NotImplementedError: validate_imported_worker_proposal_harness` from the Task 1 placeholder.

- [ ] **Step 3: Add the allowed-fields constant, input validator, input summary, and audit helper**

Insert into `mcp_server/artifact_write.py` near the other constants (around line 72, right after `_IMPORT_WORKER_RUN_ALLOWED_INPUT_FIELDS`):

```python
_VALIDATE_IMPORTED_PROPOSAL_ALLOWED_INPUT_FIELDS: frozenset[str] = frozenset({
    "proposal_ref",
    "repo_path",
})
```

Insert these four helpers right above the existing `validate_imported_worker_proposal_harness` placeholder (around line 400). The helpers mirror the patterns already used for the handoff-note and worker-run-import harnesses:

```python
def _validate_imported_proposal_input(input: Any) -> tuple[str, str]:
    """Validate MCP input for validate_imported_worker_proposal.

    Returns (proposal_ref, repo_path) on success. Raises ValueError on any
    shape problem so the harness can audit `allowed=False` and re-raise.
    """
    if not isinstance(input, dict):
        raise ValueError(f"input must be a dict, got {type(input).__name__}")

    unknown = set(input) - _VALIDATE_IMPORTED_PROPOSAL_ALLOWED_INPUT_FIELDS
    if unknown:
        raise ValueError(f"unknown field(s): {sorted(unknown)}")

    proposal_ref_raw = input.get("proposal_ref")
    if not isinstance(proposal_ref_raw, str):
        raise ValueError("proposal_ref is required and must be a string")
    proposal_ref = proposal_ref_raw.strip()
    if not proposal_ref:
        raise ValueError("proposal_ref is required and must be non-empty")
    if Path(proposal_ref).is_absolute():
        raise ValueError("proposal_ref must be a relative path")
    normalized = proposal_ref.replace("\\", "/")
    if normalized.startswith("/"):
        raise ValueError("proposal_ref must be a relative path")
    segments = normalized.split("/")
    if not segments:
        raise ValueError("proposal_ref must have at least one path segment")
    for part in segments:
        if part == "" or part == "." or part == "..":
            raise ValueError(
                f"proposal_ref must not contain empty, '.', or '..' segments: {proposal_ref!r}"
            )

    repo_path_raw = input.get("repo_path")
    if not isinstance(repo_path_raw, str):
        raise ValueError("repo_path is required and must be a string")
    repo_path = repo_path_raw.strip()
    if not repo_path:
        raise ValueError("repo_path is required and must be non-empty")
    repo_dir = Path(repo_path).expanduser().resolve()
    if not repo_dir.is_dir():
        raise ValueError(f"repo_path must be an existing directory: {repo_path!r}")

    return proposal_ref, repo_path


def _validate_imported_proposal_input_summary(input: Any) -> dict:
    if not isinstance(input, dict):
        return {"input_type": type(input).__name__}

    summary: dict[str, Any] = {}
    if "proposal_ref" in input:
        summary["proposal_ref"] = input["proposal_ref"]
    if "repo_path" in input:
        rp = input["repo_path"]
        if isinstance(rp, str):
            summary["repo_path_basename"] = Path(rp).name
        else:
            summary["repo_path_type"] = type(rp).__name__
    unknown_fields = sorted(
        str(name)
        for name in set(input)
        - _VALIDATE_IMPORTED_PROPOSAL_ALLOWED_INPUT_FIELDS
    )
    if unknown_fields:
        summary["unknown_fields"] = unknown_fields
    return summary


def _record_validate_imported_proposal_audit(
    input: Any,
    *,
    allowed: bool,
    result_summary: dict | None = None,
    artifacts: list[str] | None = None,
    error: str | None = None,
) -> None:
    try:
        record_mcp_invocation(
            tool_name="validate_imported_worker_proposal",
            capability_mode=CAPABILITY_MODE,
            allowed=allowed,
            input_summary=_validate_imported_proposal_input_summary(input),
            result_summary=result_summary,
            artifacts=artifacts or [],
            error=error,
        )
    except Exception:
        logger.warning(
            "failed to record validate_imported_worker_proposal MCP audit event",
            exc_info=True,
        )
```

- [ ] **Step 4: Replace the harness placeholder with the real implementation**

Replace the `NotImplementedError` placeholder added in Task 1 (around line 402) with the real harness body:

```python
def validate_imported_worker_proposal_harness(input: dict) -> dict:
    """Validate an already-imported worker proposal in a temp clone.

    Delegates resolution to `core.worker_runs.validate_imported_worker_proposal`,
    which resolves `proposal_ref` under `worker_runs.DEFAULT_PROPOSALS_ROOT` and
    re-enforces the path-traversal guard. The harness never accepts an
    absolute proposal directory.

    Returns the narrow MCP response shape:
      {ok, proposal_dir, apply_success, validation_ok, message, artifacts}

    Raises:
      ValueError on invalid input shape.
      FileNotFoundError if the proposal directory or repo_path is missing.
    """
    try:
        proposal_ref, repo_path = _validate_imported_proposal_input(input)
        from core.worker_runs import validate_imported_worker_proposal as _core_validate
        result = _core_validate(
            proposal_dir=proposal_ref,
            repo_path=repo_path,
            proposals_root=None,
        )
    except (ValueError, FileNotFoundError) as error:
        _record_validate_imported_proposal_audit(input, allowed=False, error=str(error))
        raise

    proposal_dir_str = result["proposal_dir"]
    proposal_dir = Path(proposal_dir_str)
    artifacts: list[str] = [proposal_dir_str]
    for fname in (
        "apply_result.json",
        "validation.json",
        "validation_output.txt",
        "case.json",
        "patch_proposal.json",
    ):
        candidate = proposal_dir / fname
        if candidate.is_file():
            artifacts.append(str(candidate))

    response = {
        "ok": True,
        "proposal_dir": proposal_dir_str,
        "apply_success": bool(result.get("apply_success")),
        "validation_ok": result.get("validation_ok"),
        "message": result.get("message") or "",
        "artifacts": artifacts,
    }
    _record_validate_imported_proposal_audit(
        input,
        allowed=True,
        result_summary={
            "ok": response["ok"],
            "apply_success": response["apply_success"],
            "validation_ok": response["validation_ok"],
            "message": response["message"],
        },
        artifacts=artifacts,
    )
    return response
```

- [ ] **Step 5: Run the happy-path test to confirm it passes**

Run: `python -m pytest tests/test_validate_imported_worker_proposal_harness.py::test_valid_proposal_validates_in_temp_clone_and_writes_artifacts -v`

Expected: PASS. The proposal directory should contain `apply_result.json`, `validation.json`, and `validation_output.txt`, with no lesson-synth files.

- [ ] **Step 6: Re-run the surface tests as a regression**

Run: `python -m pytest tests/test_mcp_artifact_write_server.py -v`

Expected: all 11 surface tests still pass (no `NotImplementedError` is raised on import).

- [ ] **Step 7: Commit**

```bash
git add tests/test_validate_imported_worker_proposal_harness.py mcp_server/artifact_write.py
git commit -m "Phase 8.2c step 2: implement validate_imported_worker_proposal harness

Add input validation, input-summary helper, audit helper, and the public
validate_imported_worker_proposal_harness. The harness delegates to the
existing core helper, returns the narrow {ok, proposal_dir, apply_success,
validation_ok, message, artifacts} shape, and records the audit event with
the artifacts that exist on disk after core returns."
```

---

## Task 3: Input-rejection tests

**Files:**
- Modify: `tests/test_validate_imported_worker_proposal_harness.py`

- [ ] **Step 1: Add the input-rejection tests**

Append the following tests to `tests/test_validate_imported_worker_proposal_harness.py`:

```python
def test_missing_proposal_ref_rejected(env):
    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "repo_path": str(env["fake_repo"]),
        })


def test_empty_proposal_ref_rejected(env):
    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": "   ",
            "repo_path": str(env["fake_repo"]),
        })


def test_absolute_proposal_ref_rejected(env):
    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": str((env["proposals_root"] / "abs").resolve()),
            "repo_path": str(env["fake_repo"]),
        })


@pytest.mark.parametrize("proposal_ref", [
    "../escape/01-foo",
    "ts/../escape",
    "../../etc",
    "ts/./01-foo",
    ".",
    "..",
    "ts//01-foo",
    "..\\escape\\01-foo",
])
def test_traversal_proposal_ref_rejected(env, proposal_ref):
    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
            "repo_path": str(env["fake_repo"]),
        })


def test_unknown_input_field_rejected(env):
    proposal_ref = _make_imported_proposal(env)
    with pytest.raises(ValueError, match="unknown field"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
            "repo_path": str(env["fake_repo"]),
            "extra": "nope",
        })


def test_missing_repo_path_rejected(env):
    proposal_ref = _make_imported_proposal(env)
    with pytest.raises(ValueError, match="repo_path"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
        })


def test_empty_repo_path_rejected(env):
    proposal_ref = _make_imported_proposal(env)
    with pytest.raises(ValueError, match="repo_path"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
            "repo_path": "   ",
        })


def test_non_directory_repo_path_rejected(env, tmp_path):
    proposal_ref = _make_imported_proposal(env)
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="repo_path"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
            "repo_path": str(missing),
        })


def test_input_not_dict_rejected(env):
    with pytest.raises(ValueError, match="dict"):
        validate_imported_worker_proposal_harness("not a dict")  # type: ignore[arg-type]
```

The two-segment shape `<run>/<item>` is intentionally allowed — that is the natural proposal_ref shape produced by `import_worker_run_as_proposal`. The `test_traversal_proposal_ref_rejected` set covers all the unsafe variants instead.

- [ ] **Step 2: Run the input-rejection tests**

Run: `python -m pytest tests/test_validate_imported_worker_proposal_harness.py -v -k "rejected"`

Expected: every rejection test passes. The validators implemented in Task 2 already cover every variant.

- [ ] **Step 3: Commit**

```bash
git add tests/test_validate_imported_worker_proposal_harness.py
git commit -m "Phase 8.2c step 3: input-rejection coverage for validate harness

Add tests for missing/empty/absolute/traversal proposal_ref, unknown input
field, missing/empty/non-dir repo_path, and non-dict input. The two-segment
proposal_ref shape <run>/<item> is intentionally allowed; only unsafe
segments are rejected."
```

---

## Task 4: Real-repo unchanged + failed-apply graceful + no-lesson + no-subagent

**Files:**
- Modify: `tests/test_validate_imported_worker_proposal_harness.py`

- [ ] **Step 1: Add the safety-property tests**

Append the following tests:

```python
def test_real_repo_byte_identical_before_and_after_validation(env):
    proposal_ref = _make_imported_proposal(env)
    before = _repo_state(env["fake_repo"])

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    assert result["ok"] is True
    assert _repo_state(env["fake_repo"]) == before


def test_failed_apply_returns_failure_without_crashing(env, monkeypatch):
    proposal_ref = _make_imported_proposal(env)
    proposal_dir = env["proposals_root"] / proposal_ref
    # Corrupt the patch_plan so apply cannot succeed.
    _write_json(proposal_dir / "patch_plan.json", [{
        "op": "replace_snippet",
        "relative_path": "src/foo.py",
        "target_snippet": "does-not-exist-in-source",
        "patched_snippet": "anything",
    }])

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    assert result["ok"] is True
    assert result["apply_success"] is False
    assert (proposal_dir / "apply_result.json").is_file()
    # Validation must have been skipped (apply did not succeed).
    assert (proposal_dir / "validation.json").is_file()
    # No lesson synth on failure.
    assert not (proposal_dir / "case.json").exists()
    assert not (proposal_dir / "patch_proposal.json").exists()


def test_harness_does_not_create_lesson_artifacts_when_validation_inconclusive(env):
    """Per Phase 7.2.1.1 self-gate: no case.json / patch_proposal.json when
    validation_ok is not True."""
    proposal_ref = _make_imported_proposal(env)
    proposal_dir = env["proposals_root"] / proposal_ref

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    assert result["ok"] is True
    assert result["validation_ok"] is None
    assert not (proposal_dir / "case.json").exists()
    assert not (proposal_dir / "patch_proposal.json").exists()


def test_harness_does_not_invoke_subagent_launcher(env, monkeypatch):
    """The MCP harness must never reach into run_subagent_handoff."""
    proposal_ref = _make_imported_proposal(env)
    tripped = {"hit": False}

    def _trip(*_args, **_kwargs):
        tripped["hit"] = True
        raise AssertionError(
            "validate harness must not invoke run_subagent_handoff"
        )

    # The subagent launcher lives in scripts.run_subagent_handoff; tripwire
    # both the module function and any direct import the harness might try.
    import scripts.run_subagent_handoff as _subagent
    monkeypatch.setattr(_subagent, "run_subagent_handoff", _trip, raising=False)

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    assert result["ok"] is True
    assert tripped["hit"] is False


def test_harness_does_not_invoke_lesson_store_writes(env, monkeypatch):
    """Lesson store creation / promotion must not be triggered by the
    validate harness, even when validation passes."""
    proposal_ref = _make_imported_proposal(env)
    tripped = {"hit": False}

    def _trip(*_args, **_kwargs):
        tripped["hit"] = True
        raise AssertionError(
            "validate harness must not write to the lesson store"
        )

    from core import lesson_store
    for attr in ("create_lesson", "promote_lesson", "block_lesson"):
        if hasattr(lesson_store, attr):
            monkeypatch.setattr(lesson_store, attr, _trip, raising=False)

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    assert result["ok"] is True
    assert tripped["hit"] is False
```

- [ ] **Step 2: Run the safety-property tests**

Run: `python -m pytest tests/test_validate_imported_worker_proposal_harness.py -v -k "byte_identical or failed_apply or lesson or subagent"`

Expected: every safety test passes. If `test_harness_does_not_invoke_subagent_launcher` fails because `scripts.run_subagent_handoff` does not expose `run_subagent_handoff`, replace the attribute name with the actual exported callable from that module (confirm via `python -c "import scripts.run_subagent_handoff as m; print(dir(m))"`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_validate_imported_worker_proposal_harness.py
git commit -m "Phase 8.2c step 4: safety properties for validate harness

Assert real repo is byte-identical before and after validation, failed apply
is returned structurally without crashing, lesson-synth files are absent
when validation is inconclusive, and the harness never reaches into the
subagent launcher or lesson store."
```

---

## Task 5: Audit-event coverage

**Files:**
- Modify: `tests/test_validate_imported_worker_proposal_harness.py`

- [ ] **Step 1: Add the audit tests**

Append the following tests:

```python
def test_success_records_audit_event(env, monkeypatch):
    proposal_ref = _make_imported_proposal(env)
    events: list[dict] = []
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **kwargs: events.append(kwargs),
    )

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    assert len(events) == 1
    event = events[0]
    assert event["tool_name"] == "validate_imported_worker_proposal"
    assert event["capability_mode"] == "artifact_write"
    assert event["allowed"] is True
    assert event["input_summary"]["proposal_ref"] == proposal_ref
    assert event["input_summary"]["repo_path_basename"] == Path(env["fake_repo"]).name
    # Validation output text must not be logged.
    summary_str = json.dumps(event["input_summary"], default=str)
    assert "validation_output" not in summary_str
    # Result summary mirrors the narrow response, not core's full dict.
    assert set(event["result_summary"].keys()) == {
        "ok", "apply_success", "validation_ok", "message",
    }
    # Artifacts include the existing on-disk evidence files.
    assert result["proposal_dir"] in event["artifacts"]
    proposal_dir = Path(result["proposal_dir"])
    assert str(proposal_dir / "apply_result.json") in event["artifacts"]
    assert str(proposal_dir / "validation.json") in event["artifacts"]
    assert str(proposal_dir / "validation_output.txt") in event["artifacts"]


def test_blocked_input_records_audit_event(env, monkeypatch):
    events: list[dict] = []
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **kwargs: events.append(kwargs),
    )

    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": "../escape",
            "repo_path": str(env["fake_repo"]),
        })

    assert len(events) == 1
    event = events[0]
    assert event["tool_name"] == "validate_imported_worker_proposal"
    assert event["allowed"] is False
    assert event["result_summary"] is None
    assert event["artifacts"] == []
    assert "proposal_ref" in (event["error"] or "")


def test_audit_write_failure_keeps_harness_success(env, monkeypatch):
    proposal_ref = _make_imported_proposal(env)
    attempts = {"count": 0}

    def _raise_audit_error(**_kwargs):
        attempts["count"] += 1
        raise OSError("audit offline")

    monkeypatch.setattr(artifact_write, "record_mcp_invocation", _raise_audit_error)

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    assert result["ok"] is True
    assert attempts["count"] == 1


def test_audit_write_failure_keeps_harness_rejection(env, monkeypatch):
    attempts = {"count": 0}

    def _raise_audit_error(**_kwargs):
        attempts["count"] += 1
        raise OSError("audit offline")

    monkeypatch.setattr(artifact_write, "record_mcp_invocation", _raise_audit_error)

    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": "../escape",
            "repo_path": str(env["fake_repo"]),
        })
    assert attempts["count"] == 1
```

- [ ] **Step 2: Run the audit tests**

Run: `python -m pytest tests/test_validate_imported_worker_proposal_harness.py -v -k "audit"`

Expected: every audit test passes. The success event lists evidence artifacts; the blocked event carries `allowed=False, result_summary=None, artifacts=[]`; audit write failures are swallowed without altering the harness outcome.

- [ ] **Step 3: Commit**

```bash
git add tests/test_validate_imported_worker_proposal_harness.py
git commit -m "Phase 8.2c step 5: audit coverage for validate harness

Verify success audit event includes the narrow result summary plus on-disk
validation artifacts, blocked audit event records allowed=False with empty
artifacts, and audit write failures do not change harness success/rejection
behavior."
```

---

## Task 6: Full-suite regression and final check

**Files:** none.

- [ ] **Step 1: Run the full Phase 8 MCP test suite**

Run: `python -m pytest tests/test_mcp_artifact_write_server.py tests/test_mcp_readonly_server.py tests/test_create_handoff_note_harness.py tests/test_import_worker_run_as_proposal_harness.py tests/test_validate_imported_worker_proposal_harness.py -v`

Expected: every test passes; no regressions in the read-only server, handoff harness, or worker-run import harness.

- [ ] **Step 2: Confirm the exposed-tools CLI prints 13 names**

Run: `python -m mcp_server.artifact_write --list-tools`

Expected: 13 lines, including `validate_imported_worker_proposal`.

- [ ] **Step 3: Re-check the read-only surface for accidental drift**

Run: `python -m mcp_server.read_only --list-tools`

Expected: 10 lines, none of which are `create_handoff_note`, `import_worker_run_as_proposal`, or `validate_imported_worker_proposal`.

- [ ] **Step 4: Confirm git status is clean**

Run: `git status`

Expected: working tree clean. All five commits from this plan should appear in `git log` with `Phase 8.2c` prefixes.

---

## Self-Review

**Spec coverage check (against `docs/superpowers/specs/2026-05-23-phase-8-2c-validate-imported-worker-proposal-mcp-design.md`):**

| Spec requirement | Task |
|---|---|
| `_EXTRA_WRITE_TOOLS` grows to 3 including `validate_imported_worker_proposal` | Task 1 step 4 |
| `validate_imported_worker_proposal_harness(input)` public | Task 2 step 4 |
| `_impl_validate_imported_worker_proposal(input)` registered in `_IMPLS` | Task 1 step 4 |
| Input dict-only, fields `{proposal_ref, repo_path}`, unknown rejected | Task 2 step 3 + Task 3 |
| `proposal_ref` required/non-empty/relative/no traversal | Task 2 step 3 + Task 3 |
| `proposal_ref` two-segment shape allowed | Task 3 (no rejection of `<ts>/<item>` shape) |
| `repo_path` required/non-empty/absolute-OK/must be existing dir | Task 2 step 3 + Task 3 |
| Resolution under `.agent/proposals/` via core helper, never arbitrary absolute | Task 2 step 4 |
| Validation only in temp clone via existing core helper | Task 2 step 4 + Task 4 step 1 |
| Writes `apply_result.json`, `validation.json`, `validation_output.txt` into proposal_dir | Task 2 step 1 + Task 4 step 1 |
| `case.json` / `patch_proposal.json` only via Phase 7.2.1.1 self-gate | Task 4 step 1 |
| Real repo byte-identical before/after | Task 4 step 1 |
| No subagent invoked | Task 4 step 1 |
| No lesson created/promoted | Task 4 step 1 |
| Narrow response `{ok, proposal_dir, apply_success, validation_ok, message, artifacts}` | Task 2 step 4 |
| `validation_ok` may be `null` | Task 2 step 1 (assertion) + Task 2 step 4 (pass-through) |
| Success audit `allowed=True` + artifact paths | Task 5 step 1 |
| Blocked audit `allowed=False`, `result_summary=None`, `artifacts=[]` | Task 5 step 1 |
| Audit input_summary excludes validation output | Task 5 step 1 (regex check) |
| Audit write failures swallowed/logged, same pattern as previous harnesses | Task 2 step 3 + Task 5 step 1 |
| Surface stays exactly 13 tools, read_only stays 10, forbidden tools stay absent | Task 1 + Task 6 |
| Failed validation returns/records failure without crashing | Task 4 step 1 |

**Placeholder scan:** No "TBD" / "implement later" / "similar to Task N" text. Every test step shows the test body; every implementation step shows the code to insert.

**Type consistency:**
- Harness function name: `validate_imported_worker_proposal_harness` (used in Tasks 1, 2, 3, 4, 5).
- Impl wrapper: `_impl_validate_imported_worker_proposal` (Task 1).
- Constants: `_VALIDATE_IMPORTED_PROPOSAL_ALLOWED_INPUT_FIELDS` (Task 2).
- Audit recorder: `_record_validate_imported_proposal_audit` (Task 2).
- Input summary: `_validate_imported_proposal_input_summary` (Task 2).
- All references match.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-23-phase-8-2c-validate-imported-worker-proposal-mcp.md`.
