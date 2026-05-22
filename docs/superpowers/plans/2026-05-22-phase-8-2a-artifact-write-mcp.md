# Phase 8.2a — MCP Artifact-Write Harness (`create_handoff_note` only) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `mcp_server.artifact_write` — a second MCP server that exposes the 10 read-only tools plus exactly one write-capable tool (`create_handoff_note`). Every other write/execute tool stays blocked.

**Architecture:** New `mcp_server/artifact_write.py` mirrors the `read_only.py` structure and re-uses its 10 `_impl_*` callables by direct import. Adds one new harness `create_handoff_note_harness` (validated dict-in/dict-out wrapper around `core.handoff_notes.create_handoff_note`) and one new MCP-registered impl `_impl_create_handoff_note`. New thin shim `scripts/mcp_artifact_write_server.py`. No registry changes. No new pip deps.

**Tech Stack:** Python 3.13, pytest, FastMCP (optional dep). PowerShell on Windows for shell commands.

**Spec:** [docs/superpowers/specs/2026-05-22-phase-8-2a-artifact-write-mcp-design.md](docs/superpowers/specs/2026-05-22-phase-8-2a-artifact-write-mcp-design.md)

---

## File map

**Create:**
- `mcp_server/artifact_write.py` — server module: re-exports read-only impls, adds harness + `_impl_create_handoff_note`, owns `list_exposed_tool_names`, `build_server`, `main`. ~200 lines.
- `scripts/mcp_artifact_write_server.py` — 30-line shim → `mcp_server.artifact_write.main`.
- `tests/test_mcp_artifact_write_server.py` — 13 tests: allowlist + CLI + missing-dep + cross-server regression.
- `tests/test_create_handoff_note_harness.py` — 23 tests: validation + path safety + isolation guarantees.

**Modify:** none. (No changes to `mcp_server/read_only.py`, `core/tool_registry.py`, `core/handoff_notes.py`, or `web/app.py`.)

Estimated new lines: ~700 (server ~200, shim ~30, tests ~470).

---

## Task 1: Module skeleton + allowlist contract

**Files:**
- Create: `mcp_server/artifact_write.py`
- Create: `tests/test_mcp_artifact_write_server.py`

In this task the module exists as a skeleton: it imports the 10 read-only impls, declares `_EXTRA_WRITE_TOOLS = ("create_handoff_note",)`, and `list_exposed_tool_names()` returns 11 names. `_IMPLS` only contains the 10 read impls (the harness wiring comes in Task 2). `build_server` and `main` are deferred to Tasks 6–7.

- [ ] **Step 1: Create the test file with 7 allowlist tests**

Create `tests/test_mcp_artifact_write_server.py`:

```python
"""Phase 8.2a — tests for the artifact-write MCP server module.

Mirrors tests/test_mcp_readonly_server.py. The MCP package may not be
installed on the test machine; tests exercise the allowlist contract and
friendly missing-dep error without ever requiring `mcp` to be importable.
"""
from __future__ import annotations

import importlib

import pytest

from core import tool_registry


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
}

# Tools that must NEVER be exposed by the artifact-write MCP server.
_FORBIDDEN_TOOLS = {
    "import_worker_run_as_proposal",
    "validate_imported_worker_proposal",
    "run_subagent_handoff",
    "apply_patch",
    "apply_patch_plan",
    "dream_apply",
    "promote_lesson",
    "block_lesson",
}


# ---- import / no-side-effect contract --------------------------------------


def test_importing_module_does_not_start_server():
    mod = importlib.import_module("mcp_server.artifact_write")
    assert hasattr(mod, "list_exposed_tool_names")
    assert hasattr(mod, "create_handoff_note_harness")
    assert hasattr(mod, "CAPABILITY_MODE")


def test_module_importable_without_mcp_package():
    from mcp_server import artifact_write
    names = artifact_write.list_exposed_tool_names()
    assert isinstance(names, list)
    assert names  # not empty


def test_capability_mode_constant_is_artifact_write():
    from mcp_server import artifact_write
    assert artifact_write.CAPABILITY_MODE == "artifact_write"
    assert artifact_write.CAPABILITY_MODE != "unsafe_dev"


# ---- allowlist contract ----------------------------------------------------


def test_exposed_names_are_exactly_eleven():
    from mcp_server import artifact_write
    assert set(artifact_write.list_exposed_tool_names()) == _EXPECTED_EXPOSED_TOOLS
    assert len(artifact_write.list_exposed_tool_names()) == 11


def test_create_handoff_note_is_exposed():
    from mcp_server import artifact_write
    assert "create_handoff_note" in artifact_write.list_exposed_tool_names()


@pytest.mark.parametrize("forbidden", sorted(_FORBIDDEN_TOOLS))
def test_specific_forbidden_tool_not_exposed(forbidden):
    from mcp_server import artifact_write
    assert forbidden not in artifact_write.list_exposed_tool_names()


def test_read_only_server_still_omits_create_handoff_note():
    """Cross-server regression: the read-only server must not gain
    create_handoff_note just because the artifact-write module exists."""
    from mcp_server import read_only
    assert "create_handoff_note" not in read_only.list_exposed_tool_names()
    # And the read-only server should still expose exactly 10.
    assert len(read_only.list_exposed_tool_names()) == 10
```

- [ ] **Step 2: Run the tests, expect ImportError on `mcp_server.artifact_write`**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -x --tb=short
```

Expected: all 13 collected tests fail with `ModuleNotFoundError: No module named 'mcp_server.artifact_write'`.

- [ ] **Step 3: Create the module skeleton**

Create `mcp_server/artifact_write.py`:

```python
"""Phase 8.2a — artifact-write MCP server for C.A.T.T.U.S.

Exposes every tool the read-only server exposes PLUS exactly one
write-capable tool: `create_handoff_note`. Every other artifact-write,
temp-clone-execute, real-repo-write, and memory-write tool stays blocked.

Design constraints:
  - Re-uses the 10 `_impl_*` callables from mcp_server.read_only by direct
    import; no duplication.
  - The narrow write surface is declared by `_EXTRA_WRITE_TOOLS`, NOT by
    the registry's `artifact_write` capability mode (which would expose
    all 3 artifact_write tools).
  - The module must be importable without the `mcp` package installed.
  - Importing this module must NOT start a server or open stdio.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import tool_registry
from mcp_server import read_only


# Documentation-only label — see list_exposed_tool_names for the actual gate.
CAPABILITY_MODE = "artifact_write"

# The *narrow* slice of artifact-write tools this server exposes. Phase 8.2a
# ships with exactly one. Future phases may extend.
_EXTRA_WRITE_TOOLS: tuple[str, ...] = ("create_handoff_note",)

_SERVER_NAME = "cattus-artifact-write"

_FRIENDLY_MISSING_DEP_MSG = (
    "MCP package not installed. "
    "Install optional MCP dependencies to run this server."
)


# ---------------------------------------------------------------------------
# Allowlist API (works without `mcp` installed)
# ---------------------------------------------------------------------------

def list_exposed_tool_names() -> list[str]:
    """Tool names this server exposes: the 10 read-only tools + the narrow
    `_EXTRA_WRITE_TOOLS` slice (currently just `create_handoff_note`).

    The `is_tool_allowed(n, "artifact_write")` check is defensive — if the
    registry ever sets mcp_exposable=False on an extra write tool, this
    server stops exposing it automatically.
    """
    names = list(read_only.list_exposed_tool_names())
    for n in _EXTRA_WRITE_TOOLS:
        if tool_registry.is_tool_allowed(n, "artifact_write"):
            names.append(n)
    return names


# ---------------------------------------------------------------------------
# Harness stub — real implementation lands in Task 2.
# ---------------------------------------------------------------------------

def create_handoff_note_harness(
    input: dict,
    *,
    handoff_root: Path | None = None,
) -> dict:
    """STUB — replaced in Task 2 by validated wrapper around
    core.handoff_notes.create_handoff_note. Kept as a NotImplementedError
    raiser so importers see the symbol but no callers succeed yet.
    """
    raise NotImplementedError("create_handoff_note_harness not yet implemented")


# ---------------------------------------------------------------------------
# Thin tool implementations
# ---------------------------------------------------------------------------

# Re-use the read-only impls verbatim by direct import (sibling module in
# the same package — leading underscore signals "internal to mcp_server",
# not "internal to read_only.py").
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
    # "create_handoff_note" wired in Task 2 after harness lands.
}
```

- [ ] **Step 4: Run the tests, expect all 13 to pass**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -v
```

Expected: 13 passed (7 unique names + the 6 forbidden-tool parametrizations of `test_specific_forbidden_tool_not_exposed`).

If the registry returns `is_tool_allowed("create_handoff_note", "artifact_write") == False` for any reason, `test_exposed_names_are_exactly_eleven` would fail with 10 names. Sanity-check by running:

```powershell
python -c "from core import tool_registry; print(tool_registry.is_tool_allowed('create_handoff_note', 'artifact_write'))"
```

Expected output: `True`.

- [ ] **Step 5: Confirm the read-only test suite still passes (cross-server regression)**

Run:

```powershell
python -m pytest tests/test_mcp_readonly_server.py -v
```

Expected: all existing read-only tests pass unchanged. None should suddenly see `create_handoff_note` in their exposed list.

- [ ] **Step 6: Commit**

```powershell
git add mcp_server/artifact_write.py tests/test_mcp_artifact_write_server.py
git commit -m "feat(mcp): Phase 8.2a — artifact-write server module + allowlist contract

Adds mcp_server/artifact_write.py as a second narrowly-scoped MCP server
module. Exposes the 10 read-only tools (re-used by direct import from
mcp_server.read_only) plus exactly one write-capable tool name:
create_handoff_note. Every other artifact_write/temp_clone_execute/
real_repo_write/memory_write tool stays blocked.

Module-level constant _EXTRA_WRITE_TOOLS = ('create_handoff_note',) is
the narrow second-gate; the registry's artifact_write capability mode is
NOT used as the sole allowlist gate (it would expose all 3 artifact_write
tools).

This commit ships the allowlist contract only. The harness, build_server,
main, and shim script land in follow-up commits.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: `create_handoff_note_harness` — happy path + wire into `_IMPLS`

**Files:**
- Modify: `mcp_server/artifact_write.py`
- Create: `tests/test_create_handoff_note_harness.py`

This task implements the happy-path harness logic (no validation rejections yet — those come in Tasks 3 and 4) and wires it into `_IMPLS` so `build_server` (Task 6) will register it.

- [ ] **Step 1: Create the test file with 5 happy-path tests**

Create `tests/test_create_handoff_note_harness.py`:

```python
"""Phase 8.2a — tests for create_handoff_note_harness.

Tests the MCP-facing dict-in/dict-out wrapper around
core.handoff_notes.create_handoff_note. Uses tmp_path + the keyword-only
handoff_root arg so no test writes into the real .agent/handoffs/ dir.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mcp_server.artifact_write import create_handoff_note_harness


def _valid_input() -> dict:
    """Returns a fresh dict of valid input for use as a baseline."""
    return {
        "title": "Refactor compute_compound_interest",
        "intended_worker": "codex",
        "task_type": "proposal_only",
        "context_summary": (
            "compute_compound_interest in interest.cpp accepts negative inputs."
            " Add validation per the case spec."
        ),
    }


# ---- happy path ------------------------------------------------------------


def test_valid_input_writes_file(tmp_path: Path):
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert result["ok"] is True
    handoff_path = Path(result["handoff_path"])
    assert handoff_path.is_file()
    # File lives strictly under tmp_path.
    handoff_path.resolve().relative_to(tmp_path.resolve())
    # Filename matches handoff_notes convention: YYYYMMDD_HHMMSS_<slug>.md.
    assert re.match(r"^\d{8}_\d{6}_.+\.md$", handoff_path.name)


def test_message_text_is_exact(tmp_path: Path):
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert result["message"] == "Handoff note created. This did not run a subagent."


def test_status_is_draft(tmp_path: Path):
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert result["status"] == "draft"


def test_default_safety_rules_applied(tmp_path: Path):
    """The harness must never override the do-not-apply/commit/push defaults."""
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    text = Path(result["handoff_path"]).read_text(encoding="utf-8")
    match = re.search(
        r"<!--HANDOFF_META\s*(?P<json>\{.*?\})\s*HANDOFF_META-->", text, re.DOTALL
    )
    assert match, "HANDOFF_META block missing"
    meta = json.loads(match.group("json"))
    rules = meta.get("safety_rules", [])
    assert "do not apply patch" in rules
    assert "do not commit" in rules
    assert "do not push" in rules


def test_default_forbidden_files_applied(tmp_path: Path):
    """The harness must inherit the default forbidden_files list."""
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    text = Path(result["handoff_path"]).read_text(encoding="utf-8")
    match = re.search(
        r"<!--HANDOFF_META\s*(?P<json>\{.*?\})\s*HANDOFF_META-->", text, re.DOTALL
    )
    meta = json.loads(match.group("json"))
    forbidden = meta.get("forbidden_files", [])
    for required in (".env", ".git", ".agent"):
        assert required in forbidden, f"{required} should be in forbidden_files"
```

- [ ] **Step 2: Run the tests, expect 5 failures (NotImplementedError)**

Run:

```powershell
python -m pytest tests/test_create_handoff_note_harness.py -v
```

Expected: 5 failed with `NotImplementedError: create_handoff_note_harness not yet implemented`.

- [ ] **Step 3: Replace the stub with the happy-path implementation**

In `mcp_server/artifact_write.py`, **replace** the `create_handoff_note_harness` stub function with this happy-path implementation (validation comes in Tasks 3–4):

```python
def create_handoff_note_harness(
    input: dict,
    *,
    handoff_root: Path | None = None,
) -> dict:
    """Validated dict-in/dict-out wrapper around
    core.handoff_notes.create_handoff_note.

    `handoff_root` is keyword-only and used only by tests + internal callers
    that want to redirect output to a tmp_path. It is NOT part of `input`
    (which is the MCP-facing schema), so external MCP callers cannot
    influence it.

    Returns: {ok, handoff_path, status, message} on success.
    Raises: ValueError on invalid input (validation lands in Tasks 3-4).
    """
    from core.handoff_notes import create_handoff_note as _core_create

    result = _core_create(
        title=input["title"],
        intended_worker=input["intended_worker"],
        task_type=input["task_type"],
        repo_path=input.get("repo_path"),
        allowed_files=input.get("allowed_files"),
        forbidden_files=input.get("forbidden_files"),
        validation_command=input.get("validation_command"),
        context_summary=input.get("context_summary", ""),
        expected_output=input.get("expected_output", ""),
        # extra_safety_rules intentionally NOT exposed via the harness:
        # defaults from core.handoff_notes.DEFAULT_SAFETY_RULES always apply.
        handoff_root=handoff_root,
    )
    return {
        "ok": True,
        "handoff_path": result["path"],
        "status": "draft",
        "message": "Handoff note created. This did not run a subagent.",
    }
```

Then **add** `create_handoff_note` to `_IMPLS` by inserting this entry at the end of the dict (and remove the `"create_handoff_note" wired in Task 2` comment):

```python
def _impl_create_handoff_note(input: dict) -> dict:
    """MCP-registered impl. Delegates to the harness without exposing
    `handoff_root` so external clients cannot redirect output."""
    return create_handoff_note_harness(input)


_IMPLS: dict[str, Callable[..., Any]] = {
    # ... existing 10 read impls ...
    "create_handoff_note": _impl_create_handoff_note,
}
```

(Put `_impl_create_handoff_note` just above the `_IMPLS` dict so the dict reference resolves.)

- [ ] **Step 4: Run the harness tests, expect all 5 to pass**

Run:

```powershell
python -m pytest tests/test_create_handoff_note_harness.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Re-run the server tests, confirm allowlist is unchanged**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -v
```

Expected: all 13 still pass.

- [ ] **Step 6: Commit**

```powershell
git add mcp_server/artifact_write.py tests/test_create_handoff_note_harness.py
git commit -m "feat(mcp): Phase 8.2a — create_handoff_note_harness happy path

Implements the dict-in/dict-out harness create_handoff_note_harness as a
validated wrapper around core.handoff_notes.create_handoff_note. The
harness exposes the MCP-facing schema (single 'input' dict) and a stable
JSON response shape: {ok, handoff_path, status, message}.

Keyword-only handoff_root parameter is used by tests + internal callers
to redirect output to tmp_path; it is NOT part of the MCP input schema,
so external clients cannot influence where notes are written.

Wires _impl_create_handoff_note (thin pass-through to the harness) into
_IMPLS so build_server (Task 6) will register it.

Validation rejections (empty title, bad worker, path traversal, etc.)
land in follow-up commits.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Harness — input validation rejections

**Files:**
- Modify: `mcp_server/artifact_write.py`
- Modify: `tests/test_create_handoff_note_harness.py`

Adds 10 negative tests + the validation layer. The harness must reject empty/oversize strings, invalid enums, and unknown extra fields BEFORE calling into `core.handoff_notes`.

- [ ] **Step 1: Append the 10 validation tests**

**Append** to `tests/test_create_handoff_note_harness.py`:

```python
# ---- input validation: rejections ------------------------------------------


def test_title_empty_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["title"] = ""
    with pytest.raises(ValueError, match="title"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_title_whitespace_only_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["title"] = "   \t  "
    with pytest.raises(ValueError, match="title"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_title_too_long_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["title"] = "x" * 201
    with pytest.raises(ValueError, match="title.*200"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_context_summary_empty_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["context_summary"] = ""
    with pytest.raises(ValueError, match="context_summary"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_context_summary_too_long_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["context_summary"] = "x" * 8001
    with pytest.raises(ValueError, match="context_summary.*8000"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_invalid_worker_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["intended_worker"] = "hacker"
    with pytest.raises(ValueError, match="intended_worker"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_invalid_task_type_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["task_type"] = "rm-rf"
    with pytest.raises(ValueError, match="task_type"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_unknown_field_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["shell"] = "rm -rf /"
    with pytest.raises(ValueError, match="unknown field"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_validation_command_too_long_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["validation_command"] = "x" * 501
    with pytest.raises(ValueError, match="validation_command.*500"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_expected_output_too_long_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["expected_output"] = "x" * 4001
    with pytest.raises(ValueError, match="expected_output.*4000"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)
```

- [ ] **Step 2: Run the tests, expect 10 failures**

Run:

```powershell
python -m pytest tests/test_create_handoff_note_harness.py -v -k "rejected"
```

Expected: 10 failed. Some will fail with `KeyError`/`ValueError` from `core.handoff_notes` rather than the expected harness-layer message. That's fine — the next step makes the harness validate first.

- [ ] **Step 3: Add the validation layer**

In `mcp_server/artifact_write.py`, **add** these constants just below `_FRIENDLY_MISSING_DEP_MSG`:

```python
# Field length caps. These bound external agent input so a runaway prompt
# can't write a 5MB handoff note.
MAX_TITLE_LEN = 200
MAX_CONTEXT_SUMMARY_LEN = 8000
MAX_VALIDATION_COMMAND_LEN = 500
MAX_EXPECTED_OUTPUT_LEN = 4000

_VALID_WORKERS: frozenset[str] = frozenset({"codex", "claude-code", "gemini", "other"})
_VALID_TASK_TYPES: frozenset[str] = frozenset({
    "proposal_only", "review_only", "explain_only", "benchmark_case", "research",
})

_ALLOWED_INPUT_FIELDS: frozenset[str] = frozenset({
    "title", "intended_worker", "task_type", "context_summary",
    "repo_path", "allowed_files", "forbidden_files",
    "validation_command", "expected_output",
})
```

Then **replace** `create_handoff_note_harness`'s body with a validated version. The function should now read:

```python
def create_handoff_note_harness(
    input: dict,
    *,
    handoff_root: Path | None = None,
) -> dict:
    """Validated dict-in/dict-out wrapper around
    core.handoff_notes.create_handoff_note.

    `handoff_root` is keyword-only and used only by tests + internal callers.
    External MCP callers cannot influence it (FastMCP introspects the
    signature of `_impl_create_handoff_note`, not this function).

    Returns: {ok, handoff_path, status, message} on success.
    Raises: ValueError on invalid input.
    """
    if not isinstance(input, dict):
        raise ValueError(f"input must be a dict, got {type(input).__name__}")

    unknown = set(input.keys()) - _ALLOWED_INPUT_FIELDS
    if unknown:
        raise ValueError(f"unknown field(s): {sorted(unknown)}")

    title = str(input.get("title") or "").strip()
    if not title:
        raise ValueError("title is required and must be non-empty")
    if len(title) > MAX_TITLE_LEN:
        raise ValueError(f"title must be <= {MAX_TITLE_LEN} chars")

    intended_worker = input.get("intended_worker")
    if intended_worker not in _VALID_WORKERS:
        raise ValueError(
            f"intended_worker must be one of {sorted(_VALID_WORKERS)}, "
            f"got {intended_worker!r}"
        )

    task_type = input.get("task_type")
    if task_type not in _VALID_TASK_TYPES:
        raise ValueError(
            f"task_type must be one of {sorted(_VALID_TASK_TYPES)}, "
            f"got {task_type!r}"
        )

    context_summary = str(input.get("context_summary") or "").strip()
    if not context_summary:
        raise ValueError("context_summary is required and must be non-empty")
    if len(context_summary) > MAX_CONTEXT_SUMMARY_LEN:
        raise ValueError(
            f"context_summary must be <= {MAX_CONTEXT_SUMMARY_LEN} chars"
        )

    validation_command = input.get("validation_command")
    if validation_command is not None:
        validation_command = str(validation_command)
        if len(validation_command) > MAX_VALIDATION_COMMAND_LEN:
            raise ValueError(
                f"validation_command must be <= {MAX_VALIDATION_COMMAND_LEN} chars"
            )

    expected_output = str(input.get("expected_output") or "")
    if len(expected_output) > MAX_EXPECTED_OUTPUT_LEN:
        raise ValueError(
            f"expected_output must be <= {MAX_EXPECTED_OUTPUT_LEN} chars"
        )

    # Path safety for allowed_files / forbidden_files lands in Task 4.
    # Pass through as-is for now; core.handoff_notes does its own safety
    # check as a backstop.
    allowed_files = input.get("allowed_files")
    forbidden_files = input.get("forbidden_files")

    from core.handoff_notes import create_handoff_note as _core_create
    result = _core_create(
        title=title,
        intended_worker=intended_worker,
        task_type=task_type,
        repo_path=input.get("repo_path"),
        allowed_files=allowed_files,
        forbidden_files=forbidden_files,
        validation_command=validation_command,
        context_summary=context_summary,
        expected_output=expected_output,
        handoff_root=handoff_root,
    )
    return {
        "ok": True,
        "handoff_path": result["path"],
        "status": "draft",
        "message": "Handoff note created. This did not run a subagent.",
    }
```

- [ ] **Step 4: Run the tests, expect all 15 (5 happy + 10 rejected) to pass**

Run:

```powershell
python -m pytest tests/test_create_handoff_note_harness.py -v
```

Expected: 15 passed.

- [ ] **Step 5: Commit**

```powershell
git add mcp_server/artifact_write.py tests/test_create_handoff_note_harness.py
git commit -m "feat(mcp): Phase 8.2a — harness input validation (strict mode)

Adds the validation layer to create_handoff_note_harness:
- title required, non-empty, <= 200 chars
- context_summary required, non-empty, <= 8000 chars
- intended_worker must be in {codex, claude-code, gemini, other}
- task_type must be in {proposal_only, review_only, explain_only,
  benchmark_case, research}
- validation_command <= 500 chars
- expected_output <= 4000 chars
- unknown extra fields rejected with ValueError('unknown field(s): ...')

The strict-mode allowlist on input fields means external agents cannot
sneak undeclared kwargs through to core.handoff_notes.

Path safety for allowed_files/forbidden_files is deferred to the next
commit; core.handoff_notes already enforces its own backstop.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Harness — path safety for `allowed_files` / `forbidden_files`

**Files:**
- Modify: `mcp_server/artifact_write.py`
- Modify: `tests/test_create_handoff_note_harness.py`

Adds the harness-side path safety gate. (`core.handoff_notes` already has its own `_safe_rel_path` backstop — the harness gate fires first so we never call into core with bad data, and the error message is consistent with the other harness rejections.)

- [ ] **Step 1: Append the 5 path-safety tests**

**Append** to `tests/test_create_handoff_note_harness.py`:

```python
# ---- path safety: allowed_files / forbidden_files --------------------------


def test_allowed_files_traversal_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = ["../../etc/passwd"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_allowed_files_absolute_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = ["/etc/passwd"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_allowed_files_windows_traversal_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = ["..\\windows\\system32"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_forbidden_files_traversal_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["forbidden_files"] = ["../../secret"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_forbidden_files_absolute_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["forbidden_files"] = ["/etc/shadow"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)
```

- [ ] **Step 2: Run the tests, expect 5 failures**

Run:

```powershell
python -m pytest tests/test_create_handoff_note_harness.py -v -k "files"
```

Expected: 5 failed. They'll mostly fail with messages from `core.handoff_notes._safe_rel_path` (which says "not a safe relative path") — that's close to the harness's intended message, but the harness should fire first.

- [ ] **Step 3: Add the path safety gate**

In `mcp_server/artifact_write.py`, add this helper just above `create_handoff_note_harness`:

```python
def _validate_rel_path_list(values: Any, field_name: str) -> list[str] | None:
    """Reject absolute paths and `..` traversal. Backslash is normalized to
    `/` first so Windows-style traversal is caught the same way as POSIX.

    Returns the original list unchanged on success (we don't mutate input).
    Returns None if values is None.
    """
    if values is None:
        return None
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of strings")
    for v in values:
        if not isinstance(v, str):
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
        normalized = v.replace("\\", "/").strip()
        if not normalized:
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
        if normalized.startswith("/"):
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
        if any(part == ".." for part in normalized.split("/")):
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
    return values
```

Then **replace** the two `allowed_files`/`forbidden_files` lines in `create_handoff_note_harness` (currently pass-through):

```python
    allowed_files = input.get("allowed_files")
    forbidden_files = input.get("forbidden_files")
```

with:

```python
    allowed_files = _validate_rel_path_list(
        input.get("allowed_files"), "allowed_files"
    )
    forbidden_files = _validate_rel_path_list(
        input.get("forbidden_files"), "forbidden_files"
    )
```

- [ ] **Step 4: Run the tests, expect all 20 (15 + 5 new) to pass**

Run:

```powershell
python -m pytest tests/test_create_handoff_note_harness.py -v
```

Expected: 20 passed.

- [ ] **Step 5: Commit**

```powershell
git add mcp_server/artifact_write.py tests/test_create_handoff_note_harness.py
git commit -m "feat(mcp): Phase 8.2a — harness path safety for file lists

Adds _validate_rel_path_list to gate allowed_files/forbidden_files BEFORE
calling into core.handoff_notes. Rejects:
- absolute paths (leading /)
- POSIX traversal (..)
- Windows traversal (..\\) via backslash normalization
- non-string entries
- empty / whitespace-only entries

core.handoff_notes._safe_rel_path is still the backstop, but the harness
gate fires first so the error message is consistent across all harness
rejections.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Harness — isolation guarantees (no subprocess, no out-of-root writes)

**Files:**
- Modify: `tests/test_create_handoff_note_harness.py`

These are tripwire tests that verify the harness has the safety properties the spec promises. No production-code changes — if the tripwires trip, the implementation is wrong and must be fixed.

- [ ] **Step 1: Append the 3 isolation tests**

**Append** to `tests/test_create_handoff_note_harness.py`:

```python
# ---- isolation guarantees --------------------------------------------------


def test_harness_does_not_invoke_subprocess(tmp_path: Path, monkeypatch):
    """Tripwire: harness must never call subprocess.run / Popen / os.system."""
    import os
    import subprocess

    tripped = {"hit": False}

    def _trip(*_args, **_kwargs):
        tripped["hit"] = True
        raise AssertionError("harness must not invoke subprocess")

    monkeypatch.setattr(subprocess, "run", _trip)
    monkeypatch.setattr(subprocess, "Popen", _trip)
    monkeypatch.setattr(os, "system", _trip)

    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert result["ok"] is True
    assert tripped["hit"] is False


def test_harness_does_not_write_outside_handoff_root(tmp_path: Path):
    """After a valid call, exactly one new file exists under tmp_path and
    nothing else on disk was touched (within the test's observable surface)."""
    before = set(tmp_path.rglob("*"))
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    after = set(tmp_path.rglob("*"))
    new = after - before
    # Exactly one new file (the .md note). No incidental dirs/files.
    new_files = {p for p in new if p.is_file()}
    assert len(new_files) == 1
    written = next(iter(new_files))
    assert written == Path(result["handoff_path"])
    # And the file is strictly inside tmp_path.
    written.resolve().relative_to(tmp_path.resolve())


def test_repo_path_not_written_to(tmp_path: Path):
    """repo_path is accepted as a string but the harness must never write
    to it. We point repo_path at a sibling directory and snapshot it
    before/after the call.
    """
    repo_dir = tmp_path / "fake_repo"
    repo_dir.mkdir()
    (repo_dir / "interest.cpp").write_text("// sentinel\n", encoding="utf-8")

    handoff_dir = tmp_path / "handoffs"
    handoff_dir.mkdir()

    snapshot_before = {
        p.relative_to(repo_dir): p.read_bytes()
        for p in repo_dir.rglob("*") if p.is_file()
    }

    inp = _valid_input()
    inp["repo_path"] = str(repo_dir)
    result = create_handoff_note_harness(inp, handoff_root=handoff_dir)
    assert result["ok"] is True

    snapshot_after = {
        p.relative_to(repo_dir): p.read_bytes()
        for p in repo_dir.rglob("*") if p.is_file()
    }
    assert snapshot_before == snapshot_after, "harness wrote to repo_path"
```

- [ ] **Step 2: Run the tests, expect all 3 to pass immediately**

Run:

```powershell
python -m pytest tests/test_create_handoff_note_harness.py -v -k "subprocess or outside or repo_path"
```

Expected: 3 passed. (If any of these fail, the implementation from Tasks 2–4 is unsafe and must be fixed before continuing.)

- [ ] **Step 3: Run the full harness file to confirm all 23 tests pass**

Run:

```powershell
python -m pytest tests/test_create_handoff_note_harness.py -v
```

Expected: 23 passed.

- [ ] **Step 4: Commit**

```powershell
git add tests/test_create_handoff_note_harness.py
git commit -m "test(mcp): Phase 8.2a — harness isolation tripwires

Adds 3 tripwire tests that lock in the harness's isolation guarantees:
- monkeypatched subprocess.run / Popen / os.system must never be called
- after a valid call, exactly one new file exists, strictly under
  handoff_root
- repo_path is accepted as input but the directory is byte-identical
  before and after the harness runs

Production code unchanged — these tests verify properties already present
in the Task 2-4 implementation.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: `build_server` + friendly missing-dep error

**Files:**
- Modify: `mcp_server/artifact_write.py`
- Modify: `tests/test_mcp_artifact_write_server.py`

Implements the FastMCP server construction with lazy `mcp` import + the friendly RuntimeError path. Adds a minimal `main()` that handles the missing-dep case (the `--list-tools` branch lands in Task 7).

- [ ] **Step 1: Append the 3 build_server + missing-dep tests**

**Append** to `tests/test_mcp_artifact_write_server.py`:

```python
# ---- friendly missing-dep error -------------------------------------------


def test_build_server_raises_friendly_error_when_mcp_missing(monkeypatch):
    from mcp_server import artifact_write

    def fake_import_mcp():
        return None, ImportError("No module named 'mcp'")

    monkeypatch.setattr(artifact_write, "_import_mcp", fake_import_mcp)

    with pytest.raises(RuntimeError) as exc_info:
        artifact_write.build_server()
    assert "MCP package not installed" in str(exc_info.value)


def test_main_exits_nonzero_with_friendly_stderr_when_mcp_missing(
    monkeypatch, capsys
):
    from mcp_server import artifact_write

    monkeypatch.setattr(
        artifact_write,
        "_import_mcp",
        lambda: (None, ImportError("no mcp")),
    )

    exit_code = artifact_write.main([])
    err = capsys.readouterr().err
    assert exit_code == 2
    assert "MCP package not installed" in err


def test_main_does_not_run_server_when_dep_missing(monkeypatch):
    from mcp_server import artifact_write

    monkeypatch.setattr(
        artifact_write,
        "_import_mcp",
        lambda: (None, ImportError("no mcp")),
    )

    called = {"run": False}

    class _StubServer:
        def run(self):
            called["run"] = True

    artifact_write.main([])
    assert called["run"] is False
```

- [ ] **Step 2: Run the tests, expect 3 failures (`AttributeError`)**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -v -k "mcp_missing or main_does_not_run"
```

Expected: 3 failed with `AttributeError: module 'mcp_server.artifact_write' has no attribute '_import_mcp'` (or `build_server` / `main`).

- [ ] **Step 3: Add `_import_mcp`, `build_server`, and minimal `main` to `mcp_server/artifact_write.py`**

**Append** to `mcp_server/artifact_write.py` (after the `_IMPLS` dict):

```python
# ---------------------------------------------------------------------------
# Lazy MCP import
# ---------------------------------------------------------------------------

def _import_mcp() -> tuple[Any | None, BaseException | None]:
    """Try to import FastMCP. Returns (FastMCP_class_or_None, error_or_None).

    Isolated as its own function so tests can monkeypatch the missing-dep
    branch even on machines where `mcp` IS installed.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
        return FastMCP, None
    except ImportError as e:
        return None, e


# ---------------------------------------------------------------------------
# Server construction + CLI entrypoint
# ---------------------------------------------------------------------------

def build_server() -> Any:
    """Construct (but do not run) a FastMCP server with allowed tools wired.

    Raises RuntimeError with the friendly message if the `mcp` package is
    not installed. Never starts a server or opens stdio.
    """
    FastMCP, err = _import_mcp()
    if FastMCP is None:
        raise RuntimeError(_FRIENDLY_MISSING_DEP_MSG) from err

    server = FastMCP(_SERVER_NAME)
    allowed = set(list_exposed_tool_names())

    for name in list(_IMPLS.keys()):
        if name not in allowed:
            continue
        impl = _IMPLS[name]
        meta = tool_registry.get_tool(name) or {}
        description = meta.get("description") or meta.get("title") or name
        server.add_tool(impl, name=name, description=description)

    return server


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns a process exit code.

    --list-tools branch lands in Task 7. For now: try to build + run a
    server; exit 2 with a friendly stderr if `mcp` is missing.
    """
    args = list(argv if argv is not None else sys.argv[1:])

    try:
        server = build_server()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    server.run()
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via scripts/ shim
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests, expect all 3 to pass**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -v -k "mcp_missing or main_does_not_run"
```

Expected: 3 passed.

- [ ] **Step 5: Run the whole server test file to confirm nothing regressed**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -v
```

Expected: 16 passed (13 from Task 1 + 3 new).

- [ ] **Step 6: Commit**

```powershell
git add mcp_server/artifact_write.py tests/test_mcp_artifact_write_server.py
git commit -m "feat(mcp): Phase 8.2a — build_server + friendly missing-dep error

Adds:
- _import_mcp: isolated FastMCP import helper so tests can monkeypatch
  the missing-dep branch even on machines where mcp IS installed
- build_server: constructs a FastMCP server, raises
  RuntimeError(friendly msg) if mcp is not installed, registers exactly
  the 11 allowlisted tools (read_only impls re-used + create_handoff_note)
- main: minimal version that builds + runs the server, exits 2 + writes
  friendly stderr on missing dep

--list-tools branch lands in the next commit.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: CLI — `--list-tools` flag

**Files:**
- Modify: `mcp_server/artifact_write.py`
- Modify: `tests/test_mcp_artifact_write_server.py`

`--list-tools` prints exposed tool names one per line, exit 0. It MUST NOT touch the `mcp` package — operators must be able to inspect the artifact-write surface even on machines without the optional dep.

- [ ] **Step 1: Append the 3 --list-tools tests**

**Append** to `tests/test_mcp_artifact_write_server.py`:

```python
# ---- --list-tools CLI flag -------------------------------------------------


def test_list_tools_flag_prints_eleven_names(capsys):
    from mcp_server import artifact_write

    exit_code = artifact_write.main(["--list-tools"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert set(out) == _EXPECTED_EXPOSED_TOOLS
    # Order must match list_exposed_tool_names() for predictable scripting.
    assert out == artifact_write.list_exposed_tool_names()


def test_list_tools_flag_works_without_mcp_dep(monkeypatch, capsys):
    from mcp_server import artifact_write

    def fake_import_mcp():
        raise AssertionError("--list-tools must NOT attempt to import mcp")

    monkeypatch.setattr(artifact_write, "_import_mcp", fake_import_mcp)

    exit_code = artifact_write.main(["--list-tools"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert set(out) == _EXPECTED_EXPOSED_TOOLS


def test_list_tools_flag_does_not_build_or_run_server(monkeypatch):
    from mcp_server import artifact_write

    build_called = {"hit": False}
    original_build = artifact_write.build_server

    def tripwire_build_server(*args, **kwargs):
        build_called["hit"] = True
        return original_build(*args, **kwargs)

    monkeypatch.setattr(artifact_write, "build_server", tripwire_build_server)

    exit_code = artifact_write.main(["--list-tools"])
    assert exit_code == 0
    assert build_called["hit"] is False
```

- [ ] **Step 2: Run the tests, expect failures**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -v -k "list_tools"
```

Expected: at minimum, `test_list_tools_flag_works_without_mcp_dep` fails because the current `main` always calls `_import_mcp` via `build_server`. May see other failures depending on monkeypatch behavior.

- [ ] **Step 3: Add the --list-tools branch to `main`**

In `mcp_server/artifact_write.py`, **replace** the `main` function with:

```python
def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns a process exit code.

    Recognized flags:
      --list-tools   Print the exposed tool names (one per line) and exit 0
                     without constructing or starting a server. Does NOT
                     require the `mcp` package to be installed.

    Exit codes:
      0 — server ran cleanly OR --list-tools printed successfully
      2 — `mcp` package not installed; friendly message printed to stderr
    """
    args = list(argv if argv is not None else sys.argv[1:])

    # --list-tools is a registry-only query. Handle it BEFORE any attempt
    # to import `mcp` — operators must be able to inspect the surface even
    # on machines without the optional dependency.
    if "--list-tools" in args:
        for name in list_exposed_tool_names():
            print(name)
        return 0

    try:
        server = build_server()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    server.run()
    return 0
```

- [ ] **Step 4: Run the tests, expect all 3 to pass**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -v -k "list_tools"
```

Expected: 3 passed.

- [ ] **Step 5: Run the full server test file to confirm everything passes**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py -v
```

Expected: 19 collected, 19 passed. Counted as: Task 1 contributed 5 unique test functions + 8 parametrized instances of `test_specific_forbidden_tool_not_exposed` (one per forbidden tool) = 13 collected. Task 6 added 3 + Task 7 added 3 = 19 total collected items.

- [ ] **Step 6: Commit**

```powershell
git add mcp_server/artifact_write.py tests/test_mcp_artifact_write_server.py
git commit -m "feat(mcp): Phase 8.2a — --list-tools CLI flag

main() now handles --list-tools BEFORE attempting to import mcp:
- prints the 11 exposed tool names one per line, exit 0
- never imports the mcp package (verified by monkeypatch tripwire)
- never calls build_server (verified by monkeypatch tripwire)

Mirrors the contract of mcp_server.read_only.main's --list-tools handling
so operator scripts can interrogate either server surface uniformly.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Shim script + final regression sweep

**Files:**
- Create: `scripts/mcp_artifact_write_server.py`

- [ ] **Step 1: Create the shim**

Create `scripts/mcp_artifact_write_server.py`:

```python
"""Phase 8.2a — launcher for the artifact-write MCP server.

Usage:
    python scripts/mcp_artifact_write_server.py
    python scripts/mcp_artifact_write_server.py --list-tools

This is a thin shim that delegates to `mcp_server.artifact_write.main`. It
exists so the entrypoint is discoverable under `scripts/` alongside the
other operator scripts; the real implementation (allowlist, harness,
friendly missing-dep error) lives in the `mcp_server` package.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_root_on_path() -> None:
    """Allow `python scripts/mcp_artifact_write_server.py` to work from anywhere."""
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

- [ ] **Step 2: Smoke-test the shim via the CLI**

Run:

```powershell
python scripts/mcp_artifact_write_server.py --list-tools
```

Expected output (one name per line, in this order):

```
get_health
list_benchmark_reports
read_benchmark_report
list_dream_reports
read_dream_report
list_lessons
read_lesson_proposal
list_worker_runs
read_worker_run
list_tool_registry
create_handoff_note
```

Exit code 0.

- [ ] **Step 3: Run the full new-test suite**

Run:

```powershell
python -m pytest tests/test_mcp_artifact_write_server.py tests/test_create_handoff_note_harness.py -v
```

Expected: 42 collected, 42 passed (19 server + 23 harness). The spec's "36 tests" count refers to unique test functions; pytest's collected count is 42 because `test_specific_forbidden_tool_not_exposed` is parametrized across 8 forbidden tool names.

- [ ] **Step 4: Run the cross-server regression: read-only suite must still be clean**

Run:

```powershell
python -m pytest tests/test_mcp_readonly_server.py -v
```

Expected: all existing read-only tests pass unchanged.

- [ ] **Step 5: Run the registry suites: no surface change there either**

Run:

```powershell
python -m pytest tests/test_tool_registry.py tests/test_tool_registry_routes.py -v
```

Expected: all pass unchanged.

- [ ] **Step 6: Confirm nothing was written into the real .agent/handoffs/ directory during the test run**

Run:

```powershell
if (Test-Path ".agent\handoffs") { Get-ChildItem ".agent\handoffs" -Recurse | Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-10) } } else { "no handoffs dir yet" }
```

Expected: empty result OR "no handoffs dir yet". (If files appear from the last 10 minutes, a test failed to pass `handoff_root=tmp_path` and instead wrote to the default location. Fix that test before committing.)

- [ ] **Step 7: Commit**

```powershell
git add scripts/mcp_artifact_write_server.py
git commit -m "feat(mcp): Phase 8.2a — scripts shim for artifact-write server

Adds scripts/mcp_artifact_write_server.py as a 30-line shim mirroring
scripts/mcp_readonly_server.py. Delegates to
mcp_server.artifact_write.main so operators can launch the server
(or interrogate its surface via --list-tools) without remembering the
module path.

Closes Phase 8.2a: 36 new tests (42 collected with parametrization), no
changes to the read-only server, no registry changes, no new pip deps.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Acceptance criteria (must all be true at end of Task 8)

1. `from mcp_server import artifact_write; artifact_write.list_exposed_tool_names()` returns 11 names: the 10 read-only tools + `create_handoff_note`.
2. `mcp_server.read_only.list_exposed_tool_names()` is unchanged — does NOT contain `create_handoff_note`.
3. `import mcp_server.artifact_write` does NOT require the `mcp` package to be installed.
4. `import mcp_server.artifact_write` does NOT start a server, open stdio, or block.
5. `mcp_server.artifact_write.CAPABILITY_MODE == "artifact_write"`. Never `"unsafe_dev"`.
6. `python scripts/mcp_artifact_write_server.py --list-tools` prints 11 names and exits 0, even when `mcp` is not installed.
7. `python scripts/mcp_artifact_write_server.py` (no flag) without `mcp` installed prints the friendly message to stderr and exits 2.
8. `create_handoff_note_harness({...valid...})` writes a markdown file under `.agent/handoffs/` (or the test-supplied `handoff_root`) and returns `{ok: True, handoff_path, status: "draft", message: "Handoff note created. This did not run a subagent."}`.
9. `create_handoff_note_harness` raises `ValueError` for: empty title, oversize title, empty/oversize context_summary, unknown worker, unknown task_type, traversal in `allowed_files`, absolute path in `allowed_files`, Windows-style traversal in `allowed_files`, traversal/absolute in `forbidden_files`, oversize validation_command, oversize expected_output, unknown extra field.
10. `create_handoff_note_harness` does NOT invoke any subprocess and does NOT write outside the configured handoff root. `repo_path` is accepted as input but never written to.
11. `pytest tests/test_mcp_artifact_write_server.py tests/test_create_handoff_note_harness.py` shows 42 collected, 42 passed.
12. `pytest tests/test_mcp_readonly_server.py` continues to pass unchanged.
13. `pytest tests/test_tool_registry.py tests/test_tool_registry_routes.py` continues to pass unchanged.
