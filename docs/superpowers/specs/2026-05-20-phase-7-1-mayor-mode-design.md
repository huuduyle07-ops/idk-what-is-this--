# Phase 7.1 — Mayor Mode handoff + optional subagent runner (MVP)

> Status: design approved 2026-05-20.
> Spec scope: MVP only. No auto-promotion, no real-repo writes, no patch-safety bypass.

## Goal

Give the operator a structured, bounded way to ship a task to an external coding
agent (Codex, Claude Code, Gemini, or other) without ever modifying the real repo,
committing, pushing, or auto-promoting a lesson. Default behavior is **create a
handoff note only**. Running the subagent is a separate, explicit, opt-in step
that always happens in a temp clone.

## Non-goals

- Running external agents by default
- Modifying the real repo from a handoff run
- Applying patches to the real repo
- Committing or pushing
- Auto-promoting lessons
- Bypassing the Patch Safety gate
- Replacing the Dream / proposal / lesson flow

## Architecture overview

Three layers, one new UI panel, four new web routes. All consistent with the
existing project patterns (path-traversal guards, `from __future__ import
annotations`, indent=2 JSON, `_safe_rel_path`-style sanitization).

```
core/handoff_notes.py         # pure storage + validation (no subprocess, no flask)
scripts/create_handoff_note.py  # thin CLI wrapper (mirrors create_lesson_from_proposal.py)
scripts/run_subagent_handoff.py # temp clone + subprocess + artifact writing
web/app.py (additions)        # 4 new routes
web/templates/index.html      # new "Mayor Mode" panel in Memory tab
tests/test_handoff_notes.py     # unit tests for core
tests/test_run_subagent_handoff.py  # tests for run script
tests/test_handoff_routes.py    # Flask client tests
```

### Boundary discipline

- `core/handoff_notes.py` is pure. It only knows about `.agent/handoffs/`,
  JSON-in-markdown parsing, and validation. No subprocess. No Flask.
- `scripts/run_subagent_handoff.py` owns: temp clone, subprocess, timeout,
  artifact writing. Exposes `run_handoff(...)` for the web route to call.
- `web/app.py` does no business logic; it only marshals form values into
  function calls and serializes the result.

## Storage layout

Decided: handoffs live in the AI project root, **not** under per-repo agent dirs.
This matches `scripts/run_patch_proposal_queue.py` which uses
`PROJECT_ROOT / ".agent" / "proposals"`.

```
<AI-project>/.agent/handoffs/<YYYYMMDD_HHMMSS>_<slug>.md
<AI-project>/.agent/worker_runs/<YYYYMMDD_HHMMSS>_<slug>/
  handoff.md            # copy of the note as it was at run time
  worker_command.txt    # exact command string that would run / did run
  raw_output.txt        # stdout+stderr (empty in dry-run)
  worker_run.json       # structured run record (dry_run, duration, exit_code, ...)
  proposal.md           # if the worker produced one in the temp clone
  patch_plan.json       # if the worker produced one in the temp clone
```

## Handoff note format

Single `.md` file with JSON frontmatter delimited by HTML comments. Using JSON
(not YAML) avoids a new `pyyaml` dependency — the project already centralizes
JSON I/O in `core/json_utils.py`.

```markdown
<!--HANDOFF_META
{
  "title": "Fix flaky fixtures in foo module",
  "created_at": "2026-05-20T14:30:00+00:00",
  "owner": "human",
  "intended_worker": "codex",
  "task_type": "proposal_only",
  "repo_path": "C:/Users/.../AI project",
  "allowed_files": ["core/foo.py", "tests/test_foo.py"],
  "forbidden_files": [".env", ".agent", ".git", "node_modules", "target", "tests"],
  "validation_command": "python -m pytest tests/test_foo.py -v",
  "status": "draft",
  "safety_rules": [
    "proposal only",
    "do not apply patch",
    "do not commit",
    "do not push",
    "do not edit .env/.agent/.git/node_modules/target/tests unless explicitly allowed",
    "return proposal.md and patch_plan.json if possible"
  ],
  "brain_stamp": { "...": "..." }
}
HANDOFF_META-->

# Fix flaky fixtures in foo module

## Context summary

...operator-written context...

## Expected output

proposal.md and patch_plan.json that fix the fixture ordering.

## How to run this handoff manually

```
codex exec --full-auto < HANDOFF.md
```

(Run inside a temp clone, never against the real repo. The
`scripts/run_subagent_handoff.py` script does this automatically when
invoked with `--allow-run`.)
```

### Field validation

| Field               | Type        | Validation                                    |
|---------------------|-------------|-----------------------------------------------|
| `title`             | str (req)   | non-empty after strip                         |
| `intended_worker`   | str (req)   | one of `codex / claude-code / gemini / other` |
| `task_type`         | str (req)   | one of `proposal_only / review_only / explain_only / benchmark_case / research` |
| `repo_path`         | str (opt)   | exists, is dir; default = AI project root     |
| `allowed_files`     | list[str]   | each entry passes `_safe_rel_path`            |
| `forbidden_files`   | list[str]   | each entry passes `_safe_rel_path`; merged with defaults |
| `validation_command`| str (opt)   | free-form; only the run script vets it        |
| `context_summary`   | str (opt)   | becomes markdown body                         |
| `expected_output`   | str (opt)   | becomes markdown body                         |
| `safety_rules`      | list[str]   | merged with defaults, dedup, order preserved  |
| `status`            | str         | draft on create; ran/failed/archived later    |
| `brain_stamp`       | dict        | populated via `core.brain_stamp.collect_brain_stamp` at create time |

### Default safety rules (always included)

1. proposal only
2. do not apply patch
3. do not commit
4. do not push
5. do not edit .env/.agent/.git/node_modules/target/tests unless explicitly allowed
6. return proposal.md and patch_plan.json if possible

### Default forbidden_files (always merged in)

`.env`, `.agent`, `.git`, `node_modules`, `target`, `tests`

If the operator explicitly listed a default-forbidden path under `allowed_files`,
the create function will NOT add it to `forbidden_files` (allowed wins) but will
record a `safety_overrides` list in the metadata for audit.

### Slug derivation

`_slug(title, fallback="handoff")` — same shape as the helper in
`scripts/run_patch_proposal_queue.py`. Lowercase alphanumeric joined by `-`,
max 60 chars, fallback if empty.

## `core/handoff_notes.py` API

```python
VALID_WORKERS = {"codex", "claude-code", "gemini", "other"}
VALID_TASK_TYPES = {"proposal_only", "review_only", "explain_only",
                    "benchmark_case", "research"}
VALID_STATUSES = {"draft", "ran", "failed", "archived"}

DEFAULT_SAFETY_RULES: list[str]
DEFAULT_FORBIDDEN_FILES: list[str]

def create_handoff_note(
    *,
    title: str,
    intended_worker: str,
    task_type: str,
    repo_path: str | None = None,
    allowed_files: list[str] | None = None,
    forbidden_files: list[str] | None = None,
    validation_command: str | None = None,
    context_summary: str = "",
    expected_output: str = "",
    extra_safety_rules: list[str] | None = None,
    handoff_root: Path | None = None,
) -> dict: ...

def list_handoff_notes(
    handoff_root: Path | None = None,
    *,
    limit: int = 50,
    include_archived: bool = False,
) -> list[dict]: ...

def read_handoff_note(
    path: str | Path,
    handoff_root: Path | None = None,
) -> dict: ...

def update_handoff_status(
    path: str | Path,
    status: str,
    handoff_root: Path | None = None,
) -> dict: ...
```

`handoff_root` defaults to `PROJECT_ROOT / ".agent" / "handoffs"` and is
overridable in tests via monkeypatch (same pattern as `PROPOSAL_ROOT`).

`read_handoff_note` is path-traversal guarded: resolved path must live under
`handoff_root`. Mirrors `_resolve_proposal_dir` in
`scripts/create_lesson_from_proposal.py`.

## `scripts/run_subagent_handoff.py`

CLI:
```
python scripts/run_subagent_handoff.py \
  --note .agent/handoffs/20260520_143000_fix-flaky-fixtures.md \
  [--allow-run] \
  [--worker codex|claude-code|gemini|other] \
  [--worker-command "..."] \
  [--timeout-sec 300]
```

### Worker command map (module-level)

```python
WORKER_COMMAND_MAP = {
    "codex":       "codex exec --full-auto",
    "claude-code": "claude --print",
    "gemini":      "gemini --prompt-file HANDOFF.md",
    "other":       None,
}

# Env-var overrides take precedence over the map.
HANDOFF_CODEX_CMD, HANDOFF_CLAUDE_CODE_CMD, HANDOFF_GEMINI_CMD,
HANDOFF_OTHER_CMD
```

If `intended_worker == "other"` and neither env override nor `--worker-command`
is set, the run refuses (exit 2, clean message).

### Default behavior (no `--allow-run`)

1. Read the note (path-traversal guarded).
2. Resolve the would-be command.
3. Print a copyable command block:
   ```
   DRY RUN — no subprocess will be executed.
   To run this handoff in a temp clone:
     <command>
   ```
4. Write artifacts as if it had run, but with `dry_run: true`, `exit_code: null`,
   `raw_output.txt` empty, no proposal.md / patch_plan.json.
5. Do **not** update the handoff status; it stays `draft`.

### `--allow-run` behavior

1. Read the note. Refuse if status is `archived`.
2. `shutil.copytree(repo_path, temp_dir / "repo", ignore=ignore_patterns)` —
   excludes `.git, .agent, node_modules, target, .venv, venv, __pycache__,
   .pytest_cache, dist, build`. Same set as `_copy_case_repo` in
   `run_patch_proposal_queue.py`.
3. Write the note body (markdown + metadata) to `<temp_clone>/HANDOFF.md`.
4. `subprocess.run(command, cwd=temp_clone, capture_output=True, timeout=timeout_sec)`.
5. After the run, scan `temp_clone` for `proposal.md` and `patch_plan.json` (root
   level only) and copy them into the artifact dir if present.
6. Write `worker_run.json` with: `dry_run=False`, `started_at`, `finished_at`,
   `duration_sec`, `exit_code`, `timed_out`, `command`, `worker`, `handoff_path`,
   `artifact_dir`.
7. Update status to `ran` (exit code 0) or `failed` (non-zero / timeout).
8. **Never** copy files from the temp clone back to the real repo, except into
   the artifact dir. `shutil.rmtree(temp_clone)` regardless of outcome.

### Timeout enforcement

`subprocess.run(..., timeout=timeout_sec)` raises `TimeoutExpired`. We catch it,
write `timed_out: true` and a clean error message, kill the process group on
POSIX (best-effort on Windows via `proc.kill()`), and set status to `failed`.

## Web routes

All return JSON. Errors return `{"ok": False, "error": "..."}` with appropriate
status codes — same shape as `/proposals/promote`.

| Method | Path                  | Body / query                                   | Returns |
|--------|-----------------------|-----------------------------------------------|---------|
| POST   | `/handoffs/create`    | title, intended_worker, task_type, repo_path?, allowed_files?, forbidden_files?, validation_command?, context_summary?, expected_output? | `{ok, handoff_path, slug, meta}` |
| GET    | `/handoffs/list`      | `?include_archived=true`                       | `{ok, handoffs: [...]}` |
| POST   | `/handoffs/run`       | handoff_path, allow_run, worker?, worker_command?, timeout_sec? | `{ok, dry_run, artifact_dir, run: {...}}` |
| GET    | `/worker-runs/list`   | none                                          | `{ok, runs: [...]}` |

The `/handoffs/run` route imports `run_handoff(...)` from
`scripts.run_subagent_handoff` and calls it in-process (not via subprocess).
This keeps Flask responsive and lets tests monkeypatch easily.

## Web UI

In `web/templates/index.html`, add a `memory-section handoffs-section` block
between the proposals section and the lessons section.

```
+----------------------------------------------------------+
| Mayor Mode (Handoffs)                       [⟳ Refresh] |
+----------------------------------------------------------+
| Create a bounded handoff note for an external coding    |
| agent. Default = note only. To actually run the agent,  |
| you must tick "Allow running subagent in temp clone".   |
| The real repo is never modified.                        |
+----------------------------------------------------------+
| [ Create new handoff ▼ ]                                |
|   Title:    [______________________________]            |
|   Worker:   ( codex | claude-code | gemini | other )    |
|   Type:     ( proposal_only | review_only | ... )       |
|   Allowed files (comma):  [_____________________]       |
|   Validation command:      [_____________________]      |
|   Context summary:                                      |
|     [_______________________________________]           |
|   [ ] Allow running subagent in temp clone              |
|   [ Create handoff ]   [ Create + Run (in temp clone) ] |
|   ⚠ This may consume Claude/Codex quota. It will not   |
|     apply changes to the real repo.                     |
+----------------------------------------------------------+
| Handoff: 20260520_143000_fix-flaky-fixtures             |
|   status: draft   worker: codex   task: proposal_only   |
|   [ Show command ]  [ Run in temp clone ]  [ Archive ]  |
+----------------------------------------------------------+
```

Show command opens a small modal with the exact command string + a clipboard
copy button. Run in temp clone is gated by the same checkbox — clicking it
without the checkbox shows a warning toast and does nothing.

A "Create handoff from this item" link in proposal/dream item cards is **deferred
to a follow-up slice** if it adds friction; for MVP the Memory tab form is the
only entry point. (Tracked in the roadmap entry.)

## Tests

| File                              | Purpose                                |
|-----------------------------------|----------------------------------------|
| `tests/test_handoff_notes.py`     | Core API: create/list/read/update, slug sanitization, default safety rules, validation errors, path traversal |
| `tests/test_run_subagent_handoff.py` | Dry-run does not execute; --allow-run uses temp clone; real repo unmodified; timeout enforced; artifacts written; status transitions |
| `tests/test_handoff_routes.py`    | Flask client: POST /handoffs/create, GET /handoffs/list, POST /handoffs/run (dry-run path), GET /worker-runs/list |

Each test that involves I/O uses `tmp_path` + monkeypatch on the module-level
`HANDOFF_ROOT` / `WORKER_RUNS_ROOT` constants — same pattern as
`test_proposal_routes.py`.

## What this MVP does NOT do (deferred to 7.1.1+)

- Surfacing `proposal.md` from a worker run back into the proposals queue
- Per-proposal / per-dream "Create handoff from this item" button
- Streaming worker output to the web UI (the run route is synchronous and
  blocks until done; long runs can hit Flask request timeout)
- Multi-tenancy — assumes one operator on `127.0.0.1:5000`
- Pagination on `/handoffs/list` and `/worker-runs/list` (limit 50 hardcoded)
- Worker-output diff visualization

## Acceptance criteria

1. `python scripts/create_handoff_note.py --title "Foo" --worker codex --task-type proposal_only` writes a note under `.agent/handoffs/` with default safety rules, default forbidden files, brain stamp, and slug.
2. `python scripts/run_subagent_handoff.py --note <path>` (no `--allow-run`) prints the dry-run command, writes a `worker_runs/<...>/worker_run.json` with `dry_run: true`, and leaves the handoff status as `draft`. No subprocess is launched.
3. `python scripts/run_subagent_handoff.py --note <path> --allow-run` copies the repo to a temp clone, runs the subprocess, writes `raw_output.txt` and any produced `proposal.md` / `patch_plan.json`, updates status to `ran` or `failed`, and the **real repo files are byte-identical before and after** (`hashlib.sha256` over each tracked file).
4. With a deliberately slow worker command, the run aborts at `timeout_sec` and the artifact records `timed_out: true`.
5. With `intended_worker="other"` and no worker_command, the run refuses with exit code 2.
6. From the web UI, creating a handoff without ticking the allow-run checkbox produces only a handoff note — no worker run dir is created.
7. From the web UI, ticking the checkbox + clicking "Create + Run (in temp clone)" produces a worker run dir with `dry_run: false`.
8. All seven items above are covered by automated tests.
