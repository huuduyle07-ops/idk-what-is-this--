# Phase 7.2 — Worker Run Review / Import (MVP)

> Status: design approved 2026-05-21.
> Scope: read + import only. No execution, no validation, no patch apply, no auto-promotion.

## Goal

After a Phase 7.1 handoff has produced artifacts in `.agent/worker_runs/<run>/`, give the operator a way to (a) browse and inspect those runs from the web UI, and (b) optionally import a complete worker run as a proposal under `.agent/proposals/<run>/<item>/` so it can flow through the existing proposal → lesson review path.

The bridge from worker-produced output to the existing proposal/lesson safety machinery — without bypassing any of it.

## Non-goals

- Running subagents (Phase 7.1's job, and only with explicit opt-in)
- Applying patches to the real repo
- Validating worker output (validation happens later, via the existing proposal queue path if the operator chooses to re-run it)
- Committing or pushing
- Auto-creating active lessons
- Bypassing Patch Safety or any other safety gate
- Surfacing worker output as a lesson directly

## Architecture

```
core/worker_runs.py             # pure storage + validation (no Flask, no subprocess)
web/app.py (additions)          # 2 new routes, 1 refactored route
web/templates/index.html        # new "Worker Runs" subsection inside Mayor Mode panel
tests/test_worker_runs.py       # unit tests for core
tests/test_worker_runs_routes.py # Flask client tests
```

The refactor of the existing `/worker-runs/list` route is behavior-preserving: it now delegates to `core.worker_runs.list_worker_runs()` and returns the same JSON shape.

## Storage layout

Reads from (Phase 7.1):
```
<AI-project>/.agent/worker_runs/<YYYYMMDD_HHMMSS>_<slug>/
  handoff.md
  worker_run.json
  raw_output.txt
  worker_command.txt
  proposal.md         # optional, worker-produced
  patch_plan.json     # optional, worker-produced
```

Writes to (when imported):
```
<AI-project>/.agent/proposals/<YYYYMMDD_HHMMSS>/01-<slug>/
  item.json               # synthetic, marks source=worker_run + pointers
  source_metadata.json    # full pointer back to the worker run
  handoff.md              # copy of the original handoff note
  worker_run.json         # copy of the original worker run record
  proposal.md             # copy from worker output (required for import)
  patch_plan.json         # copy from worker output (required for import)
  raw_output.txt          # copy of raw worker output
```

**Intentionally absent:** `apply_result.json`, `validation.json`, `case.json`, `patch_proposal.json`. A worker-run-imported proposal has not been applied, validated, or grounded in a benchmark case. The `create_lesson_from_proposal.py` script requires all of those, so a worker-run import is **not directly lesson-promotable** — the operator must re-run it through the validation/apply flow first. That asymmetry is deliberate: it preserves the proposal → lesson safety story.

## `core/worker_runs.py` API

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKER_RUNS_ROOT = PROJECT_ROOT / ".agent" / "worker_runs"
DEFAULT_PROPOSALS_ROOT = PROJECT_ROOT / ".agent" / "proposals"

RAW_OUTPUT_PREVIEW_CHARS = 2000  # web preview cap

def list_worker_runs(
    worker_runs_root: Path | None = None,
    *,
    limit: int = 50,
) -> list[dict]: ...

def read_worker_run(
    path_or_id: str | Path,
    worker_runs_root: Path | None = None,
) -> dict: ...

def detect_worker_outputs(
    run_dir: str | Path,
    worker_runs_root: Path | None = None,
) -> dict: ...
# returns {"has_proposal_md": bool, "has_patch_plan_json": bool,
#          "has_handoff_md": bool, "has_worker_run_json": bool,
#          "missing": [...], "complete": bool}

def import_worker_run_as_proposal(
    run_dir: str | Path,
    worker_runs_root: Path | None = None,
    proposals_root: Path | None = None,
) -> dict: ...
# returns {"proposal_dir": str, "source_run_dir": str,
#          "item": dict, "imported_at": iso}
```

### Worker run detail fields

`read_worker_run` returns:

| Field | Source |
|---|---|
| `run_id` | directory name |
| `path` | absolute path |
| `artifact_dir` | alias of `path` (for `/worker-runs/list` compat) |
| `name` | alias of `run_id` (for `/worker-runs/list` compat) |
| `handoff_title` | parsed from `handoff.md` HANDOFF_META; `None` on parse failure |
| `worker` | `worker_run.json` |
| `command` | `worker_run.json` |
| `dry_run` | `worker_run.json` |
| `timed_out` | `worker_run.json` |
| `exit_code` | `worker_run.json` |
| `duration_sec` | `worker_run.json` |
| `started_at` | `worker_run.json` |
| `finished_at` | `worker_run.json` |
| `error` | `worker_run.json` |
| `created_at` | alias of `started_at` (spec name) |
| `handoff_path` | `worker_run.json` |
| `has_proposal_md` | `detect_worker_outputs` |
| `has_patch_plan_json` | `detect_worker_outputs` |
| `raw_output_preview` | first `RAW_OUTPUT_PREVIEW_CHARS` of `raw_output.txt` |

`list_worker_runs` returns the same fields except `raw_output_preview` (kept off the listing for size) and adds nothing extra. The listing entries are a strict superset of the legacy `/worker-runs/list` route's shape so the existing UI keeps working during the refactor.

### Import rules

`import_worker_run_as_proposal` enforces, in order:

1. `run_dir` resolves to a directory **strictly under** `worker_runs_root`. Otherwise `ValueError("worker run path is outside ...")`.
2. The run dir contains all four required files: `handoff.md`, `worker_run.json`, `proposal.md`, `patch_plan.json`. Otherwise `FileNotFoundError("worker run is incomplete: missing X, Y, ...")`.
3. `worker_run.json` parses and has `dry_run == False`. Importing a dry-run worker output as a proposal is refused — there was no real worker output. `ValueError("cannot import a dry-run worker output as a proposal")`.
4. The destination is a fresh dir `proposals_root / <YYYYMMDD_HHMMSS> / 01-<slug>/`. If it exists (sub-second collisions), a `-1`, `-2` suffix is appended on the run dir, same as Phase 7.1's collision handling.

The function **never** modifies the source `worker_runs/` dir, the real repo, or anything outside the new proposal dir.

### Synthetic `item.json` shape

```json
{
  "kind": "worker_run_import",
  "source": "worker_run",
  "source_run_id": "20260521_010203_fix-foo",
  "source_run_dir": "<absolute path>",
  "title": "<handoff title or run_id>",
  "worker": "codex",
  "imported_at": "2026-05-21T01:02:03+00:00",
  "human_approved_for_proposal": false,
  "needs_revalidation": true
}
```

`human_approved_for_proposal=false` keeps it out of the auto-processing path in `scripts/run_patch_proposal_queue.py`. `needs_revalidation=true` is a hint to future tooling (Phase 7.2.1+) that this proposal hasn't been applied/validated yet.

### Synthetic `source_metadata.json` shape

```json
{
  "source": "worker_run",
  "source_run_id": "20260521_010203_fix-foo",
  "source_run_dir": "<absolute path>",
  "handoff_path": "<original handoff .md absolute path or None>",
  "worker": "codex",
  "command": "codex exec --full-auto",
  "imported_at": "2026-05-21T01:02:03+00:00",
  "imported_files": ["handoff.md", "worker_run.json", "proposal.md", "patch_plan.json", "raw_output.txt"]
}
```

## Web routes

| Method | Path                    | Body / query             | Returns |
|--------|-------------------------|--------------------------|---------|
| GET    | `/worker-runs/list`     | (existing; refactored)   | `{ok, runs: [list_worker_runs() output]}` |
| GET    | `/worker-runs/view`     | `?run_id=...` or `?path=...` | `{ok, run: {read_worker_run() output}}` |
| POST   | `/worker-runs/import`   | `run_id` or `path`       | `{ok, proposal_dir, item, source_run_id}` |

Errors return `{ok: False, error: "..."}` with `400` on validation errors (path-traversal, dry-run, incomplete), `404` on missing run, `500` on unexpected.

## UI additions

Inside the existing "Mayor Mode (Handoffs)" memory section, a new subsection:

```
+----------------------------------------------------------+
| Worker Runs                                  [⟳ Refresh] |
+----------------------------------------------------------+
| Subagent runs from .agent/worker_runs/. Import a         |
| complete run to surface it in the Proposals section,     |
| where you can review it before any lesson promotion.     |
+----------------------------------------------------------+
| 20260521_010203_fix-foo                                  |
|   worker: codex · exit: 0 · 12.4s · proposal.md ✓        |
|   [ View details ]  [ Import as proposal ]               |
+----------------------------------------------------------+
| 20260520_233045_review-cleanup                            |
|   worker: claude-code · DRY RUN · no proposal            |
|   [ View details ]   (Import disabled — incomplete)      |
+----------------------------------------------------------+
```

- **View details** opens an inline expansion (or a small modal) showing: handoff title, worker, command, exit, timeouts, full raw output, and rendered proposal.md preview.
- **Import as proposal** is enabled only when `detect_worker_outputs(run).complete == True` AND the run is not a dry-run. After successful import, status changes to "Imported — see Proposals" and the proposal section can be refreshed.

## Tests

| File | Coverage |
|---|---|
| `tests/test_worker_runs.py` | `list_worker_runs` happy path + sort order + limit · `read_worker_run` via run_id and via path · path-traversal blocked · `detect_worker_outputs` flags all four files · `import_worker_run_as_proposal` refuses incomplete / dry-run / outside-root · import creates the expected proposal dir with synthetic item.json + source_metadata.json + 5 copied files · real repo SHA-256 byte-identical before/after import |
| `tests/test_worker_runs_routes.py` | `/worker-runs/list` keeps legacy shape · `/worker-runs/view` returns full detail · `/worker-runs/view` rejects path traversal · `/worker-runs/import` happy path · `/worker-runs/import` refuses incomplete |

## What this MVP does NOT do (deferred to 7.2.1+)

- Validate or apply the worker patch_plan against a temp clone — that bridge is the natural next slice.
- Show a diff preview between the worker's `patch_plan.json` and the real repo.
- Idempotency / dedup — re-importing the same worker_run creates a new proposal dir.
- Pagination on `/worker-runs/list` and `/worker-runs/view` (limit hardcoded at 50).
- A dedicated "imported from worker_run" badge in the Proposals list (the existing list reads from `item.json` and will silently see `kind: worker_run_import`; the badge is a 7.2.1 polish).

## Acceptance criteria

1. `python -c "from core import worker_runs; print(worker_runs.list_worker_runs())"` returns a list (possibly empty) without import errors.
2. A run with all four required files imports cleanly to `.agent/proposals/<...>/01-<slug>/` and the new dir is visible in `GET /proposals/list`.
3. A run missing `proposal.md` or `patch_plan.json` returns a 400 with a clear `error` field naming the missing file(s).
4. A run with `dry_run: true` is refused at import time with a clear error.
5. A `run_id` or `path` that escapes `.agent/worker_runs/` is rejected before any disk read of the contents.
6. The existing `/worker-runs/list` shape is preserved (the Phase 7.1 UI keeps working without changes — the new fields are additive).
7. Real repo files are byte-identical before and after any worker-run import.
8. All 7 items above are covered by tests.
