# Phase 8.3 MCP Invocation Audit Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded JSONL MCP invocation audit ledger seeded by the Phase 8.2a `create_handoff_note` harness and exposed through a read-only `GET /mcp/audit` route.

**Architecture:** `core.mcp_audit` owns ledger paths, event construction, sanitization, JSONL append, and tolerant listing. `mcp_server.artifact_write.create_handoff_note_harness` records success and validation blocks while swallowing/logging audit persistence failures so the existing harness contract stays intact. `web.app` adds a read-only route with a bounded limit and no MCP surface change.

**Tech Stack:** Python, pytest, Flask, JSONL artifacts under `.agent`.

**Spec:** `docs/superpowers/specs/2026-05-22-phase-8-3-mcp-invocation-audit-ledger-design.md`

---

## File Map

- Create `core/mcp_audit.py`: audit event API, sanitization, JSONL storage, tolerant reads.
- Create `tests/test_mcp_audit.py`: core ledger red tests for JSONL, missing/corrupt reads, truncation.
- Modify `mcp_server/artifact_write.py`: audit the `create_handoff_note` harness without changing the exposed tool list.
- Modify `tests/test_create_handoff_note_harness.py`: success, blocked validation, audit failure, and subprocess regression tests.
- Modify `web/app.py`: read-only audit route and route limit normalization.
- Create `tests/test_mcp_audit_route.py`: response shape, route limit, GET-only tests.
- Re-run `tests/test_mcp_readonly_server.py` and `tests/test_mcp_artifact_write_server.py`: MCP surface guardrails.

## Task 1: Core Audit Ledger

**Files:**
- Create: `tests/test_mcp_audit.py`
- Create: `core/mcp_audit.py`

- [ ] Write failing core tests that monkeypatch the ledger root:

```python
def test_record_mcp_invocation_appends_jsonl(tmp_path, monkeypatch):
    from core import mcp_audit
    monkeypatch.setattr(mcp_audit, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    event = mcp_audit.record_mcp_invocation(
        tool_name="create_handoff_note",
        capability_mode="artifact_write",
        allowed=True,
        input_summary={"context_summary": "short"},
        result_summary={"ok": True},
        artifacts=["handoff.md"],
    )
    lines = (tmp_path / ".agent" / "mcp_audit" / "invocations.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert json.loads(lines[0]) == event
```

```python
def test_list_mcp_invocations_handles_missing_file(tmp_path, monkeypatch):
    from core import mcp_audit
    monkeypatch.setattr(mcp_audit, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    assert mcp_audit.list_mcp_invocations() == []
```

```python
def test_list_mcp_invocations_skips_corrupt_lines(tmp_path, monkeypatch):
    from core import mcp_audit
    monkeypatch.setattr(mcp_audit, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    path = tmp_path / ".agent" / "mcp_audit" / "invocations.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('{"id":"old"}\nnot-json\n["skip"]\n{"id":"new"}\n', encoding="utf-8")
    assert [event["id"] for event in mcp_audit.list_mcp_invocations()] == ["new", "old"]
```

```python
def test_context_summary_is_truncated(tmp_path, monkeypatch):
    from core import mcp_audit
    monkeypatch.setattr(mcp_audit, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    event = mcp_audit.record_mcp_invocation(
        tool_name="create_handoff_note",
        capability_mode="artifact_write",
        allowed=False,
        input_summary={"nested": {"context_summary": "x" * 900}},
        error="blocked",
    )
    assert len(event["input_summary"]["nested"]["context_summary"]) <= 500
```

- [ ] Run `python -m pytest tests/test_mcp_audit.py -v` and confirm import/API failures before creating production code.
- [ ] Implement the minimal core module:

```python
from config import get_agent_dir

AUDIT_DIRNAME = "mcp_audit"
INVOCATIONS_FILENAME = "invocations.jsonl"
MAX_CONTEXT_SUMMARY_CHARS = 500
MAX_AUDIT_STRING_CHARS = 1000

def record_mcp_invocation(...): ...
def list_mcp_invocations(limit: int = 50) -> list[dict]: ...
```

The implementation generates `id` and `created_at`, sanitizes nested summary
values, appends one JSON object per line, and lists valid dict events newest
first.

- [ ] Run `python -m pytest tests/test_mcp_audit.py -v` and keep iterating until the focused core tests pass.

## Task 2: Harness Audit Integration

**Files:**
- Modify: `tests/test_create_handoff_note_harness.py`
- Modify: `mcp_server/artifact_write.py`

- [ ] Add failing harness audit tests using monkeypatch on `artifact_write.record_mcp_invocation`:

```python
def test_success_records_audit_event(tmp_path, monkeypatch):
    from mcp_server import artifact_write
    events = []
    monkeypatch.setattr(artifact_write, "record_mcp_invocation", lambda **kwargs: events.append(kwargs))
    result = artifact_write.create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert events[0]["allowed"] is True
    assert result["handoff_path"] in events[0]["artifacts"]
```

```python
def test_failed_validation_records_blocked_audit_event(tmp_path, monkeypatch):
    from mcp_server import artifact_write
    events = []
    monkeypatch.setattr(artifact_write, "record_mcp_invocation", lambda **kwargs: events.append(kwargs))
    bad = _valid_input()
    bad["title"] = ""
    with pytest.raises(ValueError, match="title"):
        artifact_write.create_handoff_note_harness(bad, handoff_root=tmp_path)
    assert events[0]["allowed"] is False
    assert "title" in events[0]["error"]
```

```python
def test_audit_write_failure_does_not_change_success(tmp_path, monkeypatch):
    from mcp_server import artifact_write
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("audit offline")),
    )
    assert artifact_write.create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)["ok"] is True
```

```python
def test_audit_write_failure_keeps_validation_error(tmp_path, monkeypatch):
    from mcp_server import artifact_write
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("audit offline")),
    )
    bad = _valid_input()
    bad["title"] = ""
    with pytest.raises(ValueError, match="title"):
        artifact_write.create_handoff_note_harness(bad, handoff_root=tmp_path)
```

- [ ] Run the new focused harness tests and confirm they fail because the harness has no audit integration yet.
- [ ] Add one `_record_handoff_audit` helper in `mcp_server/artifact_write.py` that calls `record_mcp_invocation` inside `try/except Exception`, logs failures, and never raises.
- [ ] Wrap harness validation and success paths so `ValueError` records `allowed=False` before re-raising, and successful create records `allowed=True` with `handoff_path` in `artifacts`.
- [ ] Run `python -m pytest tests/test_create_handoff_note_harness.py -v`.

## Task 3: Read-Only Audit Route

**Files:**
- Create: `tests/test_mcp_audit_route.py`
- Modify: `web/app.py`

- [ ] Add failing route tests:

```python
def test_mcp_audit_route_returns_count_and_limit(client, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "list_mcp_invocations", lambda limit=50: [{"id": "one"}])
    body = client.get("/mcp/audit?limit=7").get_json()
    assert body == {"ok": True, "events": [{"id": "one"}], "count": 1, "limit": 7}
```

```python
@pytest.mark.parametrize(("raw_limit", "expected"), [("", 50), ("nope", 50), ("0", 50), ("-3", 50), ("999", 200)])
def test_mcp_audit_route_normalizes_limit(client, monkeypatch, raw_limit, expected):
    from web import app as web_app
    seen = []
    monkeypatch.setattr(web_app, "list_mcp_invocations", lambda limit=50: seen.append(limit) or [])
    client.get("/mcp/audit" + (f"?limit={raw_limit}" if raw_limit else ""))
    assert seen == [expected]
```

```python
def test_mcp_audit_route_is_get_only(client):
    assert client.post("/mcp/audit").status_code in (404, 405)
```

- [ ] Run `python -m pytest tests/test_mcp_audit_route.py -v` and confirm the route is absent before implementation.
- [ ] Import `list_mcp_invocations` into `web/app.py`, add `_mcp_audit_limit`, and add `GET /mcp/audit` returning `{ok, events, count, limit}`.
- [ ] Run `python -m pytest tests/test_mcp_audit_route.py -v`.

## Task 4: Verification And Surface Regression

- [ ] Run focused feature verification:

```powershell
python -m pytest tests/test_mcp_audit.py tests/test_mcp_audit_route.py tests/test_create_handoff_note_harness.py -v
```

- [ ] Run MCP surface guardrails:

```powershell
python -m pytest tests/test_mcp_readonly_server.py tests/test_mcp_artifact_write_server.py -v
```

- [ ] Inspect the diff and confirm:
  - no new names were added to MCP `_IMPLS` or allowlists
  - no UI files changed
  - audit storage stays under `.agent/mcp_audit/invocations.jsonl`
  - subprocess tripwire test still covers the harness path
