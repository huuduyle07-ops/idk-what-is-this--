# Phase 11-prep-cleanup-b1: History Archive/Delete UX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add archive/pin/delete controls for session history, benchmark reports, and Dream runs to the web UI, using per-domain sidecar files and inline flags in sessions.json; no report files are ever modified or deleted.

**Architecture:** Three new data-layer helpers (one per domain) own per-domain sidecar JSON files. A single new Flask blueprint (`web/routes/history_routes.py`) exposes 7 routes. Existing routes `/benchmarks/list` and `/dream/reports` gain an `include_archived` filter param. Session helpers are extracted to `web/session_store.py` to eliminate a circular import between `web/app.py` and the blueprint.

**Tech Stack:** Python 3.11+, Flask, pathlib, json, pytest, monkeypatch

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `web/session_store.py` | **Create** | SESSION_FILE, load/save/find_session, list_sessions |
| `web/routes/history_routes.py` | **Create** | 7 history management routes as Flask Blueprint |
| `core/benchmarks_view.py` | **Modify** | Add 3 sidecar helpers; update `list_benchmark_reports` signature |
| `core/dream_artifacts.py` | **Modify** | Add 3 sidecar helpers; update `list_all_reports` signature |
| `web/app.py` | **Modify** | Import session helpers from session_store; register new blueprint; thread `include_archived` into 2 existing routes |
| `tests/test_history_management.py` | **Create** | Data-layer unit tests + 8 focused integration tests |

---

## Task 1: Create `web/session_store.py` and unit-test `list_sessions`

**Files:**
- Create: `web/session_store.py`
- Create: `tests/test_history_management.py` (start with 3 unit tests)

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_history_management.py`:

```python
"""Phase 11-prep-cleanup-b1: History Archive/Delete UX tests."""
from __future__ import annotations
import json
from pathlib import Path
import pytest


# ---------------------------------------------------------------------------
# Helpers shared across tasks
# ---------------------------------------------------------------------------

def _write_sessions(path: Path, sessions: list[dict]) -> None:
    path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sessions_file(tmp_path, monkeypatch):
    """Redirect SESSION_FILE to a temp path with two seed sessions."""
    import web.session_store as ss
    f = tmp_path / "sessions.json"
    _write_sessions(f, [
        {"id": "sess_001", "title": "Session 1", "query": "q1"},
        {"id": "sess_002", "title": "Session 2", "query": "q2"},
    ])
    monkeypatch.setattr(ss, "SESSION_FILE", f)
    return f


# ---------------------------------------------------------------------------
# Task 1 — unit tests for list_sessions
# ---------------------------------------------------------------------------

def test_list_sessions_default_excludes_archived(tmp_path, monkeypatch):
    import web.session_store as ss
    f = tmp_path / "sessions.json"
    _write_sessions(f, [
        {"id": "a", "archived": True},
        {"id": "b"},
    ])
    monkeypatch.setattr(ss, "SESSION_FILE", f)
    result = ss.list_sessions()
    assert [s["id"] for s in result] == ["b"]


def test_list_sessions_include_archived(tmp_path, monkeypatch):
    import web.session_store as ss
    f = tmp_path / "sessions.json"
    _write_sessions(f, [
        {"id": "a", "archived": True},
        {"id": "b"},
    ])
    monkeypatch.setattr(ss, "SESSION_FILE", f)
    result = ss.list_sessions(include_archived=True)
    assert {s["id"] for s in result} == {"a", "b"}


def test_list_sessions_default_excludes_deleted(tmp_path, monkeypatch):
    import web.session_store as ss
    f = tmp_path / "sessions.json"
    _write_sessions(f, [
        {"id": "a", "deleted": True},
        {"id": "b"},
    ])
    monkeypatch.setattr(ss, "SESSION_FILE", f)
    result = ss.list_sessions()
    assert [s["id"] for s in result] == ["b"]
```

- [ ] **Step 1.2: Run to confirm failures**

```
pytest tests/test_history_management.py::test_list_sessions_default_excludes_archived tests/test_history_management.py::test_list_sessions_include_archived tests/test_history_management.py::test_list_sessions_default_excludes_deleted -v
```

Expected: 3 failures with `ModuleNotFoundError: No module named 'web.session_store'`

- [ ] **Step 1.3: Create `web/session_store.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

SESSION_FILE = Path(__file__).parent / "sessions.json"


def load_sessions() -> list[dict]:
    if not SESSION_FILE.exists():
        return []
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_sessions(sessions: list[dict]) -> None:
    SESSION_FILE.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def find_session(session_id: str) -> dict | None:
    for s in load_sessions():
        if s.get("id") == session_id:
            return s
    return None


def list_sessions(
    include_archived: bool = False,
    include_deleted: bool = False,
) -> list[dict]:
    result = []
    for s in load_sessions():
        if s.get("deleted") and not include_deleted:
            continue
        if s.get("archived") and not include_archived:
            continue
        result.append(s)
    return result
```

- [ ] **Step 1.4: Run to confirm passing**

```
pytest tests/test_history_management.py::test_list_sessions_default_excludes_archived tests/test_history_management.py::test_list_sessions_include_archived tests/test_history_management.py::test_list_sessions_default_excludes_deleted -v
```

Expected: 3 PASSED

- [ ] **Step 1.5: Update `web/app.py` to import session helpers from the new module**

In `web/app.py`, replace the block at lines 78–142 that defines `SESSION_FILE`, `load_sessions`, `save_sessions`, and `find_session` with imports:

```python
WEB_DIR = Path(__file__).parent
from web.session_store import load_sessions, save_sessions, find_session
from scripts.run_patch_proposal_queue import PROPOSAL_ROOT as _DREAM_PROPOSAL_ROOT
BACKUP_DIR = WEB_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
```

The exact old block to replace (lines 76–142):

```python
WEB_DIR = Path(__file__).parent
from scripts.run_patch_proposal_queue import PROPOSAL_ROOT as _DREAM_PROPOSAL_ROOT
SESSION_FILE = WEB_DIR / "sessions.json"
BACKUP_DIR = WEB_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

def load_sessions() -> list[dict]:
    if not SESSION_FILE.exists():
        return []

    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_sessions(sessions: list[dict]) -> None:
    SESSION_FILE.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

```

Replace with:

```python
WEB_DIR = Path(__file__).parent
from web.session_store import load_sessions, save_sessions, find_session
from scripts.run_patch_proposal_queue import PROPOSAL_ROOT as _DREAM_PROPOSAL_ROOT
BACKUP_DIR = WEB_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

```

Also replace the standalone `find_session` definition at lines 138–142:

```python
def find_session(session_id: str) -> dict | None:
    for s in load_sessions():
        if s.get("id") == session_id:
            return s
    return None
```

with nothing (it is now provided by the import).

- [ ] **Step 1.6: Verify no regressions**

```
pytest tests/ -x -q --ignore=tests/test_history_management.py
```

Expected: same pass count as before (no new failures from the refactor)

- [ ] **Step 1.7: Commit**

```bash
git add web/session_store.py web/app.py tests/test_history_management.py
git commit -m "feat: extract session helpers to web/session_store.py with list_sessions filter"
```

---

## Task 2: Add benchmark sidecar helpers to `core/benchmarks_view.py`

**Files:**
- Modify: `core/benchmarks_view.py`
- Modify: `tests/test_history_management.py` (append 3 unit tests)

- [ ] **Step 2.1: Append unit tests to `tests/test_history_management.py`**

Append after the Task 1 tests:

```python
# ---------------------------------------------------------------------------
# Task 2 — unit tests for benchmark sidecar helpers
# ---------------------------------------------------------------------------

def _make_bench_dir(tmp_path: Path, filename: str = "benchmark_report_1000000000.json") -> tuple[Path, str]:
    """Create a minimal .agent/benchmarks dir with one report file."""
    repo = tmp_path / "repo"
    bench = repo / ".agent" / "benchmarks"
    bench.mkdir(parents=True)
    data = {"total": 10, "passed": 8, "failed": 2, "skipped": 0,
            "success_rate": 0.8, "duration_sec": 30}
    (bench / filename).write_text(json.dumps(data), encoding="utf-8")
    return repo, filename


def test_benchmark_meta_roundtrip(tmp_path):
    from core.benchmarks_view import read_benchmark_meta, write_benchmark_meta
    repo, filename = _make_bench_dir(tmp_path)
    assert read_benchmark_meta(repo) == {}
    write_benchmark_meta(repo, {filename: {"archived": True, "pinned": False}})
    meta = read_benchmark_meta(repo)
    assert meta[filename]["archived"] is True
    assert meta[filename]["pinned"] is False


def test_update_benchmark_entry_merges(tmp_path):
    from core.benchmarks_view import update_benchmark_entry, read_benchmark_meta
    repo, filename = _make_bench_dir(tmp_path)
    update_benchmark_entry(repo, filename, archived=True)
    entry = read_benchmark_meta(repo)[filename]
    assert entry["archived"] is True
    update_benchmark_entry(repo, filename, pinned=True)
    entry2 = read_benchmark_meta(repo)[filename]
    assert entry2["archived"] is True   # preserved
    assert entry2["pinned"] is True


def test_list_benchmark_reports_filters_archived(tmp_path):
    from core.benchmarks_view import update_benchmark_entry, list_benchmark_reports
    repo, filename = _make_bench_dir(tmp_path)
    # Default: report visible
    assert any(r["filename"] == filename for r in list_benchmark_reports(repo))
    # Archive it
    update_benchmark_entry(repo, filename, archived=True)
    # Default list hides it
    assert not any(r["filename"] == filename for r in list_benchmark_reports(repo))
    # include_archived shows it
    assert any(r["filename"] == filename for r in list_benchmark_reports(repo, include_archived=True))
```

- [ ] **Step 2.2: Run to confirm failures**

```
pytest tests/test_history_management.py::test_benchmark_meta_roundtrip tests/test_history_management.py::test_update_benchmark_entry_merges tests/test_history_management.py::test_list_benchmark_reports_filters_archived -v
```

Expected: 3 failures — `ImportError` for missing functions

- [ ] **Step 2.3: Add helpers to `core/benchmarks_view.py`**

Append after the existing imports block and before `_FILENAME_RE`:

```python
_META_FILENAME = "history_meta.json"


def _meta_path(repo_path: str | Path) -> Path:
    return _bench_dir(repo_path) / _META_FILENAME


def read_benchmark_meta(repo_path: str | Path) -> dict:
    path = _meta_path(repo_path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_benchmark_meta(repo_path: str | Path, meta: dict) -> None:
    path = _meta_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def update_benchmark_entry(repo_path: str | Path, filename: str, **fields) -> dict:
    meta = read_benchmark_meta(repo_path)
    entry = dict(meta.get(filename, {}))
    entry.update(fields)
    meta[filename] = entry
    write_benchmark_meta(repo_path, meta)
    return entry
```

Then update `list_benchmark_reports` to accept and use `include_archived`:

Replace:

```python
def list_benchmark_reports(repo_path: str | Path) -> list[dict]:
    """All benchmark reports for a repo, newest first.

    Returns an empty list if .agent/benchmarks/ doesn't exist or contains no
    parseable reports."""
    bench_dir = _bench_dir(repo_path)
    if not bench_dir.is_dir():
        return []
    summaries: list[dict] = []
    for p in bench_dir.glob("benchmark_report_*.json"):
        s = _summarize_one(p)
        if s is not None:
            summaries.append(s)
    summaries.sort(key=lambda s: s["timestamp_epoch"], reverse=True)
    return summaries
```

With:

```python
def list_benchmark_reports(
    repo_path: str | Path,
    include_archived: bool = False,
) -> list[dict]:
    """All benchmark reports for a repo, newest first.

    Returns an empty list if .agent/benchmarks/ doesn't exist or contains no
    parseable reports. Entries with deleted=True are always hidden.
    Entries with archived=True are hidden unless include_archived is set."""
    bench_dir = _bench_dir(repo_path)
    if not bench_dir.is_dir():
        return []
    meta = read_benchmark_meta(repo_path)
    summaries: list[dict] = []
    for p in bench_dir.glob("benchmark_report_*.json"):
        s = _summarize_one(p)
        if s is None:
            continue
        entry = meta.get(s["filename"], {})
        s["archived"] = bool(entry.get("archived", False))
        s["pinned"] = bool(entry.get("pinned", False))
        s["deleted"] = bool(entry.get("deleted", False))
        if s["deleted"]:
            continue
        if s["archived"] and not include_archived:
            continue
        summaries.append(s)
    summaries.sort(key=lambda s: s["timestamp_epoch"], reverse=True)
    return summaries
```

- [ ] **Step 2.4: Run to confirm passing**

```
pytest tests/test_history_management.py::test_benchmark_meta_roundtrip tests/test_history_management.py::test_update_benchmark_entry_merges tests/test_history_management.py::test_list_benchmark_reports_filters_archived -v
```

Expected: 3 PASSED

- [ ] **Step 2.5: Commit**

```bash
git add core/benchmarks_view.py tests/test_history_management.py
git commit -m "feat: add benchmark sidecar helpers (read/write/update/list with include_archived)"
```

---

## Task 3: Add dream run sidecar helpers to `core/dream_artifacts.py`

**Files:**
- Modify: `core/dream_artifacts.py`
- Modify: `tests/test_history_management.py` (append 3 unit tests)

- [ ] **Step 3.1: Append unit tests to `tests/test_history_management.py`**

Append after the Task 2 tests:

```python
# ---------------------------------------------------------------------------
# Task 3 — unit tests for dream run sidecar helpers
# ---------------------------------------------------------------------------

def _make_dream_run(
    tmp_path: Path,
    date: str = "2026-06-04",
    run: str = "010203-run",
) -> tuple[Path, str, str]:
    """Create a minimal dream run dir under tmp_path/repo."""
    repo = tmp_path / "repo"
    run_dir = repo / ".agent" / "dreams" / date / run
    run_dir.mkdir(parents=True)
    items = [{"idx": 1, "title": "Fix T", "status": "planned_no_patch"}]
    (run_dir / "list.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    return repo, date, run


def test_dream_meta_roundtrip(tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")
    assert da.read_dream_meta(str(repo)) == {}
    run_key = f"{date}/{run}"
    da.write_dream_meta(str(repo), {run_key: {"archived": True, "pinned": False, "deleted": False}})
    meta = da.read_dream_meta(str(repo))
    assert meta[run_key]["archived"] is True


def test_update_dream_entry_merges(tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")
    run_key = f"{date}/{run}"
    da.update_dream_entry(str(repo), run_key, archived=True)
    entry = da.read_dream_meta(str(repo))[run_key]
    assert entry["archived"] is True
    da.update_dream_entry(str(repo), run_key, pinned=True)
    entry2 = da.read_dream_meta(str(repo))[run_key]
    assert entry2["archived"] is True   # preserved
    assert entry2["pinned"] is True


def test_list_all_reports_filters_archived_and_deleted(tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")
    run_key = f"{date}/{run}"

    # Default: run is visible
    reports = da.list_all_reports(str(repo))
    assert any(r["run_id"] == run for r in reports)

    # Archive it — hidden by default, shown with include_archived
    da.update_dream_entry(str(repo), run_key, archived=True)
    assert not any(r["run_id"] == run for r in da.list_all_reports(str(repo)))
    assert any(r["run_id"] == run for r in da.list_all_reports(str(repo), include_archived=True))

    # Soft-delete — always hidden regardless of include_archived
    da.update_dream_entry(str(repo), run_key, archived=False, deleted=True)
    assert not any(r["run_id"] == run for r in da.list_all_reports(str(repo), include_archived=True))
```

- [ ] **Step 3.2: Run to confirm failures**

```
pytest tests/test_history_management.py::test_dream_meta_roundtrip tests/test_history_management.py::test_update_dream_entry_merges tests/test_history_management.py::test_list_all_reports_filters_archived_and_deleted -v
```

Expected: 3 failures — `AttributeError` for missing functions

- [ ] **Step 3.3: Add helpers to `core/dream_artifacts.py`**

After the existing `dreams_root` function definition, add:

```python
_DREAM_META_FILENAME = "history_meta.json"


def _dream_meta_path(repo_path: str) -> Path:
    return dreams_root(repo_path) / _DREAM_META_FILENAME


def read_dream_meta(repo_path: str) -> dict:
    path = _dream_meta_path(repo_path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_dream_meta(repo_path: str, meta: dict) -> None:
    path = _dream_meta_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def update_dream_entry(repo_path: str, run_key: str, **fields) -> dict:
    meta = read_dream_meta(repo_path)
    entry = dict(meta.get(run_key, {}))
    entry.update(fields)
    meta[run_key] = entry
    write_dream_meta(repo_path, meta)
    return entry
```

Then update `list_all_reports` to accept and use `include_archived`. Replace the current function (lines 165–201):

```python
def list_all_reports(repo_path: str, include_archived: bool = False) -> list[dict]:
    """All past dream runs for this repo, newest first.

    Slice γ.3.1: each entry now has BOTH `date` (YYYY-MM-DD) and `run_id`
    (HHMMSS-run, or None for legacy reports without a run subdir). The web
    sidebar uses both to identify a specific run; the `/dream/report` route
    accepts an optional `run` query param matching `run_id`.

    Entries with archived=True or deleted=True in the sidecar are hidden
    unless include_archived is set (deleted entries are ALWAYS hidden).
    """
    meta = read_dream_meta(repo_path)
    summaries: list[dict] = []
    for date_str, run_id, report_dir in _iter_report_dirs(repo_path):
        list_path = report_dir / "list.json"
        try:
            data = json.loads(list_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        run_key = f"{date_str}/{run_id}" if run_id else date_str
        entry = meta.get(run_key, {})
        archived = bool(entry.get("archived", False))
        deleted = bool(entry.get("deleted", False))
        pinned = bool(entry.get("pinned", False))

        if deleted:
            continue
        if archived and not include_archived:
            continue

        items = data.get("items", []) or []
        statuses: dict[str, int] = {}
        for it in items:
            st = it.get("status", "unknown")
            statuses[st] = statuses.get(st, 0) + 1

        summaries.append({
            "date": date_str,
            "run_id": run_id,
            "report_dir": str(report_dir),
            "item_count": len(items),
            "statuses": statuses,
            "patch_style": data.get("patch_style"),
            "dream_mode": data.get("dream_mode"),
            "completed_at": data.get("completed_at"),
            "archived": archived,
            "pinned": pinned,
            "deleted": deleted,
        })
    return summaries
```

- [ ] **Step 3.4: Run to confirm passing**

```
pytest tests/test_history_management.py::test_dream_meta_roundtrip tests/test_history_management.py::test_update_dream_entry_merges tests/test_history_management.py::test_list_all_reports_filters_archived_and_deleted -v
```

Expected: 3 PASSED

- [ ] **Step 3.5: Commit**

```bash
git add core/dream_artifacts.py tests/test_history_management.py
git commit -m "feat: add dream run sidecar helpers (read/write/update/list with include_archived)"
```

---

## Task 4: Create `web/routes/history_routes.py`, update `web/app.py`, pass all 8 integration tests

**Files:**
- Create: `web/routes/history_routes.py`
- Modify: `web/app.py`
- Modify: `tests/test_history_management.py` (append 8 integration tests)

- [ ] **Step 4.1: Append 8 integration tests to `tests/test_history_management.py`**

Append after the Task 3 tests:

```python
# ---------------------------------------------------------------------------
# Integration tests 1–8 (require history_routes blueprint + app updates)
# ---------------------------------------------------------------------------

# Test 1
def test_archive_session_hides_from_default(client, sessions_file):
    resp = client.post(
        "/history/session/archive",
        data={"session_id": "sess_001", "archived": "true"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    resp2 = client.get("/history/sessions")
    assert resp2.status_code == 200
    ids = [s["id"] for s in resp2.get_json()["sessions"]]
    assert "sess_001" not in ids
    assert "sess_002" in ids


# Test 2
def test_archived_session_shown_with_include_archived(client, sessions_file):
    client.post(
        "/history/session/archive",
        data={"session_id": "sess_001", "archived": "true"},
    )
    resp = client.get("/history/sessions?include_archived=1")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.get_json()["sessions"]]
    assert "sess_001" in ids
    assert "sess_002" in ids


# Test 3
def test_benchmark_report_can_be_archived(client, tmp_path, monkeypatch):
    repo, filename = _make_bench_dir(tmp_path)

    resp = client.post(
        "/history/benchmark/update",
        data={"repo_path": str(repo), "filename": filename, "archived": "true"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    resp2 = client.get(f"/benchmarks/list?repo_path={repo}")
    assert resp2.status_code == 200
    reports = resp2.get_json()["reports"]
    assert not any(r["filename"] == filename for r in reports)


# Test 4
def test_pinned_benchmark_report_cannot_be_deleted(client, tmp_path, monkeypatch):
    repo, filename = _make_bench_dir(tmp_path)
    client.post(
        "/history/benchmark/update",
        data={"repo_path": str(repo), "filename": filename, "pinned": "true"},
    )
    resp = client.post(
        "/history/benchmark/delete",
        data={
            "repo_path": str(repo),
            "filename": filename,
            "confirm": "DELETE_BENCHMARK_REPORT",
        },
    )
    assert resp.status_code == 409
    assert "pinned" in resp.get_json()["error"]


# Test 5
def test_dream_run_can_be_archived(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")

    resp = client.post(
        "/history/dream/update",
        data={"repo_path": str(repo), "date": date, "run": run, "archived": "true"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    resp2 = client.get(f"/dream/reports?repo_path={repo}")
    assert resp2.status_code == 200
    reports = resp2.get_json()["reports"]
    assert not any(r["run_id"] == run for r in reports)


# Test 6
def test_pinned_dream_run_cannot_be_deleted(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")

    client.post(
        "/history/dream/update",
        data={"repo_path": str(repo), "date": date, "run": run, "pinned": "true"},
    )
    resp = client.post(
        "/history/dream/delete",
        data={
            "repo_path": str(repo),
            "date": date,
            "run": run,
            "confirm": "DELETE_DREAM_RUN",
        },
    )
    assert resp.status_code == 409
    assert "pinned" in resp.get_json()["error"]


# Test 7
def test_delete_requires_confirmation_token(client, sessions_file, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo_b, filename = _make_bench_dir(tmp_path)
    repo_d, date, run = _make_dream_run(tmp_path, date="2026-06-04", run="020304-run")
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo_d / ".agent" / "dreams")

    # Session: wrong confirm
    r = client.post("/history/session/delete", data={"session_id": "sess_001", "confirm": "WRONG"})
    assert r.status_code == 400
    assert "DELETE_SESSION" in r.get_json()["error"]

    # Session: missing confirm
    r = client.post("/history/session/delete", data={"session_id": "sess_001"})
    assert r.status_code == 400

    # Benchmark: wrong confirm
    r = client.post("/history/benchmark/delete", data={
        "repo_path": str(repo_b), "filename": filename, "confirm": "WRONG",
    })
    assert r.status_code == 400
    assert "DELETE_BENCHMARK_REPORT" in r.get_json()["error"]

    # Dream: wrong confirm
    r = client.post("/history/dream/delete", data={
        "repo_path": str(repo_d), "date": date, "run": run, "confirm": "WRONG",
    })
    assert r.status_code == 400
    assert "DELETE_DREAM_RUN" in r.get_json()["error"]


# Test 8
def test_no_execution_routes_called(client, sessions_file, tmp_path, monkeypatch):
    import core.benchmark_web as bw
    import core.sleeping_consultant as sc
    import agents.gemini_client as gc
    import core.dream_artifacts as da

    def _raise(*a, **kw):
        raise AssertionError("execution route was called unexpectedly")

    monkeypatch.setattr(bw, "start_benchmark_run_async", _raise)
    monkeypatch.setattr(sc, "start_overnight_async", _raise)
    monkeypatch.setattr(gc, "run_gemini_request", _raise)

    repo_b, filename = _make_bench_dir(tmp_path)
    repo_d, date, run = _make_dream_run(tmp_path, date="2026-06-04", run="030405-run")
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo_d / ".agent" / "dreams")

    # All 7 history routes must complete without triggering execution functions
    client.get("/history/sessions")
    client.post("/history/session/archive",
                data={"session_id": "sess_001", "archived": "true"})
    client.post("/history/session/delete",
                data={"session_id": "sess_001", "confirm": "DELETE_SESSION"})
    client.post("/history/benchmark/update",
                data={"repo_path": str(repo_b), "filename": filename, "archived": "true"})
    client.post("/history/benchmark/delete",
                data={"repo_path": str(repo_b), "filename": filename,
                      "confirm": "DELETE_BENCHMARK_REPORT"})
    client.post("/history/dream/update",
                data={"repo_path": str(repo_d), "date": date, "run": run, "archived": "true"})
    client.post("/history/dream/delete",
                data={"repo_path": str(repo_d), "date": date, "run": run,
                      "confirm": "DELETE_DREAM_RUN"})
    # If _raise was triggered, the test would have failed above
```

- [ ] **Step 4.2: Run integration tests to confirm all 8 fail**

```
pytest tests/test_history_management.py -k "test_archive_session or test_archived_session or test_benchmark_report_can or test_pinned_benchmark or test_dream_run_can or test_pinned_dream or test_delete_requires or test_no_execution" -v
```

Expected: 8 failures with `404 NOT FOUND` (routes don't exist yet)

- [ ] **Step 4.3: Create `web/routes/history_routes.py`**

```python
from __future__ import annotations

import re
from pathlib import Path

from flask import Blueprint, request

from web.session_store import load_sessions, save_sessions, list_sessions
from core import benchmarks_view
from core import dream_artifacts

bp = Blueprint("history_routes", __name__)

_CONFIRM_SESSION = "DELETE_SESSION"
_CONFIRM_BENCHMARK = "DELETE_BENCHMARK_REPORT"
_CONFIRM_DREAM = "DELETE_DREAM_RUN"
_BENCH_FILENAME_RE = re.compile(r"^benchmark_report_\d+\.json$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RUN_RE = re.compile(r"^\d{6}-run(-\d+)?$")


def _bool_field(name: str) -> bool:
    return request.form.get(name, "").strip().lower() not in {"0", "false", "no", "off", ""}


# ---------------------------------------------------------------------------
# Session routes
# ---------------------------------------------------------------------------

@bp.route("/history/sessions", methods=["GET"])
def history_sessions():
    include_archived = request.values.get("include_archived", "").strip() in {"1", "true", "yes"}
    return {"sessions": list_sessions(include_archived=include_archived)}


@bp.route("/history/session/archive", methods=["POST"])
def history_session_archive():
    session_id = request.form.get("session_id", "").strip()
    if not session_id:
        return {"ok": False, "error": "session_id is required"}, 400

    archived = _bool_field("archived")
    sessions = load_sessions()
    for s in sessions:
        if s.get("id") == session_id:
            s["archived"] = archived
            save_sessions(sessions)
            return {"ok": True, "session_id": session_id, "archived": archived}

    return {"ok": False, "error": f"session not found: {session_id}"}, 404


@bp.route("/history/session/delete", methods=["POST"])
def history_session_delete():
    session_id = request.form.get("session_id", "").strip()
    confirm = request.form.get("confirm", "").strip()

    if not session_id:
        return {"ok": False, "error": "session_id is required"}, 400
    if confirm != _CONFIRM_SESSION:
        return {"ok": False, "error": f"confirm string required: {_CONFIRM_SESSION}"}, 400

    from datetime import datetime, timezone
    sessions = load_sessions()
    for s in sessions:
        if s.get("id") == session_id:
            s["deleted"] = True
            s["deleted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            save_sessions(sessions)
            return {"ok": True, "session_id": session_id}

    return {"ok": False, "error": f"session not found: {session_id}"}, 404


# ---------------------------------------------------------------------------
# Benchmark routes
# ---------------------------------------------------------------------------

@bp.route("/history/benchmark/update", methods=["POST"])
def history_benchmark_update():
    repo_path = request.form.get("repo_path", "").strip()
    filename = request.form.get("filename", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not filename:
        return {"ok": False, "error": "filename is required"}, 400
    if not _BENCH_FILENAME_RE.match(filename):
        return {"ok": False, "error": f"invalid filename: {filename}"}, 400

    fields: dict[str, bool] = {}
    if "archived" in request.form:
        fields["archived"] = _bool_field("archived")
    if "pinned" in request.form:
        fields["pinned"] = _bool_field("pinned")
    if not fields:
        return {"ok": False, "error": "at least one of archived or pinned is required"}, 400

    entry = benchmarks_view.update_benchmark_entry(repo_path, filename, **fields)
    return {"ok": True, "filename": filename, "meta": entry}


@bp.route("/history/benchmark/delete", methods=["POST"])
def history_benchmark_delete():
    repo_path = request.form.get("repo_path", "").strip()
    filename = request.form.get("filename", "").strip()
    confirm = request.form.get("confirm", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not filename:
        return {"ok": False, "error": "filename is required"}, 400
    if not _BENCH_FILENAME_RE.match(filename):
        return {"ok": False, "error": f"invalid filename: {filename}"}, 400
    if confirm != _CONFIRM_BENCHMARK:
        return {"ok": False, "error": f"confirm string required: {_CONFIRM_BENCHMARK}"}, 400

    meta = benchmarks_view.read_benchmark_meta(repo_path)
    if meta.get(filename, {}).get("pinned"):
        return {"ok": False, "error": "cannot delete a pinned item — unpin first"}, 409

    entry = dict(meta.get(filename, {}))
    entry["deleted"] = True
    meta[filename] = entry
    benchmarks_view.write_benchmark_meta(repo_path, meta)
    return {"ok": True, "filename": filename}


# ---------------------------------------------------------------------------
# Dream routes
# ---------------------------------------------------------------------------

def _run_key(date: str, run: str) -> str:
    return f"{date}/{run}" if run else date


@bp.route("/history/dream/update", methods=["POST"])
def history_dream_update():
    repo_path = request.form.get("repo_path", "").strip()
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not date:
        return {"ok": False, "error": "date is required"}, 400
    if not _DATE_RE.match(date):
        return {"ok": False, "error": f"invalid date format: {date}"}, 400
    if run and not _RUN_RE.match(run):
        return {"ok": False, "error": f"invalid run id: {run}"}, 400

    fields: dict[str, bool] = {}
    if "archived" in request.form:
        fields["archived"] = _bool_field("archived")
    if "pinned" in request.form:
        fields["pinned"] = _bool_field("pinned")
    if not fields:
        return {"ok": False, "error": "at least one of archived or pinned is required"}, 400

    key = _run_key(date, run)
    entry = dream_artifacts.update_dream_entry(repo_path, key, **fields)
    return {"ok": True, "run_key": key, "meta": entry}


@bp.route("/history/dream/delete", methods=["POST"])
def history_dream_delete():
    repo_path = request.form.get("repo_path", "").strip()
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()
    confirm = request.form.get("confirm", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not date:
        return {"ok": False, "error": "date is required"}, 400
    if not _DATE_RE.match(date):
        return {"ok": False, "error": f"invalid date format: {date}"}, 400
    if run and not _RUN_RE.match(run):
        return {"ok": False, "error": f"invalid run id: {run}"}, 400
    if confirm != _CONFIRM_DREAM:
        return {"ok": False, "error": f"confirm string required: {_CONFIRM_DREAM}"}, 400

    key = _run_key(date, run)
    meta = dream_artifacts.read_dream_meta(repo_path)
    if meta.get(key, {}).get("pinned"):
        return {"ok": False, "error": "cannot delete a pinned item — unpin first"}, 409

    entry = dict(meta.get(key, {}))
    entry["deleted"] = True
    meta[key] = entry
    dream_artifacts.write_dream_meta(repo_path, meta)
    return {"ok": True, "run_key": key}
```

- [ ] **Step 4.4: Register the blueprint and thread `include_archived` in `web/app.py`**

**4.4a — Register blueprint.** In `web/app.py`, add the import after the existing blueprint imports (around line 55–59):

```python
from web.routes.history_routes import bp as history_routes_bp
```

And register it just after the existing `app.register_blueprint` calls:

```python
app.register_blueprint(history_routes_bp)
```

**4.4b — Thread `include_archived` into `/benchmarks/list`** (lines 1237–1245). Replace:

```python
@app.route("/benchmarks/list", methods=["GET"])
def benchmarks_list_route():
    """List past benchmark reports for the Benchmarks tab (Phase 5 Slice 3).
    Returns metadata only — call /benchmarks/report for full content."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    from core.benchmarks_view import list_benchmark_reports
    return {"reports": list_benchmark_reports(repo_path)}
```

With:

```python
@app.route("/benchmarks/list", methods=["GET"])
def benchmarks_list_route():
    """List past benchmark reports for the Benchmarks tab (Phase 5 Slice 3).
    Returns metadata only — call /benchmarks/report for full content."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    include_archived = request.values.get("include_archived", "").strip() in {"1", "true", "yes"}
    from core.benchmarks_view import list_benchmark_reports
    return {"reports": list_benchmark_reports(repo_path, include_archived=include_archived)}
```

**4.4c — Thread `include_archived` into `/dream/reports`** (lines 698–704). Replace:

```python
@app.route("/dream/reports", methods=["GET"])
def dream_reports_route():
    """All past dream runs for a repo, newest first. Feeds the sidebar list."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    return {"reports": dream_artifacts.list_all_reports(repo_path)}
```

With:

```python
@app.route("/dream/reports", methods=["GET"])
def dream_reports_route():
    """All past dream runs for a repo, newest first. Feeds the sidebar list."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    include_archived = request.values.get("include_archived", "").strip() in {"1", "true", "yes"}
    return {"reports": dream_artifacts.list_all_reports(repo_path, include_archived=include_archived)}
```

- [ ] **Step 4.5: Run the 8 integration tests**

```
pytest tests/test_history_management.py -k "test_archive_session or test_archived_session or test_benchmark_report_can or test_pinned_benchmark or test_dream_run_can or test_pinned_dream or test_delete_requires or test_no_execution" -v
```

Expected: 8 PASSED

- [ ] **Step 4.6: Run full test file**

```
pytest tests/test_history_management.py -v
```

Expected: All 17 tests PASSED (3 unit-session + 3 unit-benchmark + 3 unit-dream + 8 integration)

- [ ] **Step 4.7: Commit**

```bash
git add web/routes/history_routes.py web/app.py tests/test_history_management.py
git commit -m "feat: add history archive/pin/delete routes (Phase 11-prep-cleanup-b1)"
```

---

## Task 5: Full validation

**Files:** none (read-only validation)

- [ ] **Step 5.1: Compile-check all modified modules**

```
python -m compileall core web tests
```

Expected: no syntax errors

- [ ] **Step 5.2: Run the focused history management tests**

```
python -m pytest tests/test_history_management.py -q --basetemp .fresh_tmp_history_b1
```

Expected: 17 passed, 0 errors

- [ ] **Step 5.3: Run full pytest suite**

```
python -m pytest tests -q --basetemp .fresh_tmp_history_full
```

Expected: All existing tests still pass, no regressions

- [ ] **Step 5.4: Run benchmark --check**

```
python benchmarks/run_benchmarks.py --check
```

Expected: 50 checked, 0 errors

- [ ] **Step 5.5: If all pass, commit a validation record**

```bash
git commit --allow-empty -m "ci: Phase 11-prep-cleanup-b1 validation pass (history archive/delete UX)"
```

---

## Summary of files changed

| File | Change |
|------|--------|
| `web/session_store.py` | **New** — SESSION_FILE, load/save/find/list_sessions |
| `web/routes/history_routes.py` | **New** — 7 history routes as Flask Blueprint |
| `core/benchmarks_view.py` | **+50 lines** — 4 sidecar functions, updated list_benchmark_reports |
| `core/dream_artifacts.py` | **+55 lines** — 4 sidecar functions, updated list_all_reports |
| `web/app.py` | **−20 / +5 lines** — import from session_store, register blueprint, 2 route edits |
| `tests/test_history_management.py` | **New** — 17 tests (3+3+3 unit + 8 integration) |

## Safety guarantees delivered

1. `benchmark_report_*.json` files: never read for modification, never deleted
2. Dream `list.json` and run directories: never touched
3. Pinned items: 409 on delete regardless of confirm string
4. All deletes require resource-specific confirm string
5. No model, subprocess, patch, or benchmark execution in any history route
6. Soft-delete only — `deleted=true` in sidecar, directory remains
