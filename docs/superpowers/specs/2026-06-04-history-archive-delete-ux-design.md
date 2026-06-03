# Phase 11-prep-cleanup-b1: History Archive/Delete UX

**Date:** 2026-06-04  
**Phase:** 11-prep-cleanup-b1  
**Scope:** Web/history management only. No patch generation, benchmark scoring, Dream reasoning, lesson retrieval, model/API calls, subprocess, or Docker changes.

---

## Goal

Allow the user to manage session history, benchmark report history, and Dream run history from the web UI without manually editing JSON files.

---

## Data Model

### Sessions (`web/sessions.json`)

Two new optional fields added inline to each session entry:

```json
{"id": "20260604123000", "archived": true, "deleted": false, ...}
```

- `archived` — absent/false by default. Hidden from the default session list. Shown when `include_archived=1` is passed.
- `deleted` — absent/false by default. Hidden from all normal views. Shown only with `include_deleted=1` (debug).
- Existing sessions with neither field behave as active.
- No entries are physically removed from the array in this phase.

### Benchmarks (`.agent/benchmarks/history_meta.json`)

Keyed by filename (stable relative ID):

```json
{
  "benchmark_report_1234567.json": {"archived": false, "pinned": true},
  "benchmark_report_9876543.json": {"archived": true,  "pinned": false}
}
```

- `archived: true` → hidden from `/benchmarks/list` default response.
- `pinned: true` → deletion refused even with the correct confirm string.
- `benchmark_report_*.json` files on disk are **never modified or deleted** in this phase.

### Dream runs (`.agent/dreams/history_meta.json`)

Keyed by `"date/run_id"` (e.g. `"2026-06-01/010203-run"`):

```json
{
  "2026-06-01/010203-run": {"archived": false, "pinned": false, "deleted": false},
  "2026-06-01/152030-run": {"archived": true,  "pinned": true,  "deleted": false}
}
```

- `archived: true` → hidden from `/dream/reports` default response.
- `deleted: true` → hidden from all views; run directory left on disk (soft-delete only).
- `pinned: true` → deletion refused.
- Hard purge (physical directory removal) is out of scope for b1.

---

## Routes

All new routes live in `web/routes/history_routes.py` as a Flask Blueprint registered on `web/app.py`.

### Session routes

| Method | Path | Inputs | Response |
|--------|------|--------|----------|
| GET | `/history/sessions` | `?include_archived=1` | `{sessions: [...]}` |
| POST | `/history/session/archive` | `session_id`, `archived=true\|false` | `{ok, session_id, archived}` |
| POST | `/history/session/delete` | `session_id`, `confirm=DELETE_SESSION` | `{ok, session_id}` |

### Benchmark routes

| Method | Path | Inputs | Response |
|--------|------|--------|----------|
| POST | `/history/benchmark/update` | `repo_path`, `filename`, `archived?`, `pinned?` | `{ok, filename, meta}` |
| POST | `/history/benchmark/delete` | `repo_path`, `filename`, `confirm=DELETE_BENCHMARK_REPORT` | `{ok, filename}` |

`/benchmarks/list` gains `?include_archived=1` — reads the sidecar to annotate/filter.

### Dream routes

| Method | Path | Inputs | Response |
|--------|------|--------|----------|
| POST | `/history/dream/update` | `repo_path`, `date`, `run`, `archived?`, `pinned?` | `{ok, run_key, meta}` |
| POST | `/history/dream/delete` | `repo_path`, `date`, `run`, `confirm=DELETE_DREAM_RUN` | `{ok, run_key}` |

`/dream/reports` gains `?include_archived=1`.

### Error shapes

- Missing or wrong confirm string → `{"ok": false, "error": "confirm string required: DELETE_..."}, 400`
- Delete while pinned → `{"ok": false, "error": "cannot delete a pinned item — unpin first"}, 409`
- Resource not found → `{"ok": false, "error": "..."}, 404`

---

## Internal Architecture

### `core/benchmarks_view.py` additions

Three new functions; no changes to existing signatures:

- `read_benchmark_meta(repo_path) -> dict` — load `.agent/benchmarks/history_meta.json`; return `{}` if missing or unparseable.
- `write_benchmark_meta(repo_path, meta: dict) -> None` — atomic write (write to `.tmp`, rename).
- `update_benchmark_entry(repo_path, filename, **fields) -> dict` — merge fields into the entry, save, return updated entry.

`list_benchmark_reports()` gains `include_archived: bool = False`. Entries that have `archived: true` in the sidecar are filtered out unless the flag is set. Each returned summary dict gains `archived` and `pinned` fields.

### `core/dream_artifacts.py` additions

Same pattern:

- `read_dream_meta(repo_path) -> dict`
- `write_dream_meta(repo_path, meta: dict) -> None`
- `update_dream_entry(repo_path, run_key: str, **fields) -> dict`

`list_all_reports()` gains `include_archived: bool = False`. Entries with `archived: true` or `deleted: true` are filtered unless the flag is set. Each summary gains `archived`, `pinned`, `deleted` fields.

### `web/session_store.py` (new file)

Extracted from `web/app.py` to avoid circular imports. Contains:

- `SESSION_FILE` path constant
- `load_sessions() -> list[dict]`
- `save_sessions(sessions: list[dict]) -> None`
- `find_session(session_id: str) -> dict | None`
- `list_sessions(include_archived: bool = False, include_deleted: bool = False) -> list[dict]` — wraps `load_sessions()` with flag-based filtering

`web/app.py` is updated to import these from `web.session_store` (no logic change, just moving the definitions).

### `web/app.py` changes

- Import `load_sessions`, `save_sessions`, `find_session` from `web.session_store` (moved, not changed)
- `/benchmarks/list` route: pass `include_archived` from `request.values` to `list_benchmark_reports()`
- `/dream/reports` route: pass `include_archived` from `request.values` to `list_all_reports()`

### `web/routes/history_routes.py` (new file)

Flask Blueprint `bp`. Imports:
- `web.session_store`: `load_sessions`, `save_sessions`, `find_session`, `list_sessions`
- `core.benchmarks_view`: benchmark meta helpers
- `core.dream_artifacts`: dream meta helpers

No model calls. No subprocess. No benchmark execution. No patch execution.

---

## Tests

File: `tests/test_history_management.py`

| # | Test name | Verifies |
|---|-----------|---------|
| 1 | `test_archive_session_hides_from_default` | Archived session absent from `GET /history/sessions` default |
| 2 | `test_archived_session_shown_with_include_archived` | Same session present with `include_archived=1` |
| 3 | `test_benchmark_report_can_be_archived` | `POST /history/benchmark/update` writes sidecar; `/benchmarks/list` hides it |
| 4 | `test_pinned_benchmark_report_cannot_be_deleted` | Correct confirm + pinned → 409 |
| 5 | `test_dream_run_can_be_archived` | `POST /history/dream/update` writes sidecar; `/dream/reports` hides it |
| 6 | `test_pinned_dream_run_cannot_be_deleted` | Correct confirm + pinned → 409 |
| 7 | `test_delete_requires_confirmation_token` | Missing/wrong confirm → 400 for all three resource types |
| 8 | `test_no_execution_routes_called` | `benchmark_web.start_benchmark_run_async`, `start_overnight_async`, `run_gemini_request` monkeypatched to raise; all history routes complete without touching them |

All tests: Flask `app.test_client()` + `tmp_path` + `monkeypatch`. No model calls, no subprocesses.

---

## Safety Guarantees

1. Benchmark report files (`benchmark_report_*.json`) are never modified or deleted.
2. Dream run directories and `list.json` are never modified or deleted.
3. Pinned items cannot be deleted even with the correct confirm string.
4. Deletion requires a resource-specific confirm string (`DELETE_SESSION`, `DELETE_BENCHMARK_REPORT`, `DELETE_DREAM_RUN`).
5. No active lessons or lesson evidence are touched.
6. No model, patch, or subprocess calls in any history management route.

---

## Out of Scope (b1)

- Hard purge of Dream run directories
- UI wiring (buttons, modals) — routes only
- Benchmark report file deletion
- Lesson or evidence management
