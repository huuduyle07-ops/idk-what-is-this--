# Phase 7.2.1 — Validate Imported Worker Proposals (MVP)

> Status: design approved 2026-05-21.
> Scope: temp-clone apply + validation only. No real-repo writes, no lesson promotion changes.

## Goal

After `import_worker_run_as_proposal` (Phase 7.2) lands a worker run under `.agent/proposals/<run>/01-<slug>/`, let the operator revalidate the imported `patch_plan.json` by applying it in a temp clone of a chosen repo and running the inferred validation command. Write `apply_result.json`, `validation.json`, and `validation_output.txt` next to the existing import artifacts, so subsequent tooling can read the evidence.

This is the validation half of the Phase 7.1 → 7.2 bridge. After 7.2.1, the operator can see whether the worker's patch_plan actually applies and validates without touching the real repo.

## Non-goals

- Applying to the real repo
- Committing or pushing
- Auto-promoting a lesson (still blocked because `case.json` / `patch_proposal.json` are intentionally absent for worker-run imports — that's 7.2.2's job)
- Running subagents
- Changing the handoff execution flow
- Changing Patch Safety gate semantics
- Validating proposals that did not come from worker-run imports (out of scope for MVP)

## Architecture

```
core/worker_runs.py (additions)        # validate_imported_worker_proposal()
web/app.py (additions)                  # POST /proposals/validate route
web/templates/index.html               # Validate button in Worker Runs section
tests/test_worker_runs.py (additions)   # 7 new tests
tests/test_worker_runs_routes.py (additions)  # 4 new route tests
```

Reuses:
- `core.run_lifecycle.run_patch_plan_with_artifacts` for the apply step
- `scripts.run_patch_proposal_queue._run_validation_command` for the validation step (same allow-list + segmented timeout discipline as the existing proposal queue)
- `core.repo_librarian.inspect_repo_inventory` + `core.validation_command.get_default_validation_command` for language → command inference

The function pattern mirrors `scripts/run_patch_proposal_queue._process_item`: copy repo → apply with validation_command=None → run validation separately → write `apply_result.json` + `validation.json` + `validation_output.txt`. That way the artifact shape matches the existing proposal queue's output exactly, and future lesson tooling treats both kinds of proposals uniformly.

## `core/worker_runs.py` API addition

```python
def validate_imported_worker_proposal(
    proposal_dir: str | Path,
    repo_path: str | Path,
    *,
    proposals_root: Path | None = None,
    validation_timeout_sec: int = 60,
) -> dict[str, Any]:
    """Apply the worker proposal's patch_plan.json in a temp clone of
    `repo_path` and run the inferred validation command. Writes
    apply_result.json, validation.json, validation_output.txt into
    proposal_dir. Never modifies the real repo or `repo_path`.

    Returns:
      {
        "ok": True,
        "proposal_dir": str,
        "apply_success": bool,
        "validation_ok": bool | None,
        "message": str,
        "apply_result_path": str,
        "validation_path": str,
      }
    """
```

### Behavior contract (enforced in order)

1. `proposal_dir` resolves to a directory **strictly under** `proposals_root` (default `<AI-project>/.agent/proposals/`). Otherwise `ValueError("proposal_dir is outside ...")`.
2. The directory contains `patch_plan.json`. Otherwise `FileNotFoundError("proposal_dir missing patch_plan.json")`.
3. `repo_path` resolves to an existing directory. Otherwise `FileNotFoundError`.
4. Copy `repo_path` to a temp directory using `shutil.copytree` with the same ignore_patterns Phase 7.1 uses (`.git`, `.agent`, `node_modules`, `target`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, `dist`, `build`).
5. Read `patch_plan.json` from the proposal_dir. Refuse non-list / empty plans with `ValueError`.
6. Apply via `run_patch_plan_with_artifacts(temp_clone, plan, validation_command=None, user_query=title_from_item_json, control_result={"route": "worker_run_validate", "proposal_dir": ...}, source="worker_run_validate")`. Captures `apply_result`.
7. Write `apply_result.json` (the full dict from step 6) into `proposal_dir`.
8. If apply succeeded: infer language via `inspect_repo_inventory(temp_clone)`, get validation_command via `get_default_validation_command(language, temp_clone)`. If a non-empty command was inferred, run `_run_validation_command(command, temp_clone, timeout_sec)`. Write the resulting dict to `validation.json` and the `output` field to `validation_output.txt`.
9. If apply failed: write a minimal `validation.json` with `validation_ok=null`, `error="apply did not succeed; validation skipped"`, and an empty `validation_output.txt`.
10. Update `item.json` in proposal_dir: set `needs_revalidation=False`, set `validation_status` to `"passed"` (when both apply_success and validation_ok), `"failed"` (when apply failed or validation returned non-zero), or `"no_command"` (when no validation command could be inferred).
11. Return the result dict.

### What `validate_imported_worker_proposal` does NOT do

- Does not call `evaluate_patch_safety` explicitly — `apply_patch_plan` (invoked by `run_patch_plan_with_artifacts`) already enforces its own per-op safety. Adding the global patch-safety gate at this layer would be a 7.2.2 hardening, not a 7.2.1 requirement.
- Does not synthesize `case.json` or `patch_proposal.json`. Those remain missing for worker-run imports, so `scripts/create_lesson_from_proposal.py` will still refuse to lessonize them. This is deliberate: it keeps the safety story clear and leaves "what shape should worker-derived lessons take?" as a separate design conversation.
- Does not delete or move existing artifacts in proposal_dir. Re-running validation overwrites `apply_result.json`, `validation.json`, `validation_output.txt`, and the `validation_status` field in item.json, but leaves `proposal.md`, `patch_plan.json`, `handoff.md`, `worker_run.json`, `source_metadata.json`, and `raw_output.txt` untouched.

## Web route

| Method | Path                | Body                                                            | Returns |
|--------|---------------------|-----------------------------------------------------------------|---------|
| POST   | `/proposals/validate` | `proposal_dir` (required), `repo_path` (required), `validation_timeout_sec` (optional, default 60) | `{ok, proposal_dir, apply_success, validation_ok, message, apply_result_path, validation_path}` |

Errors return `{ok: False, error: "..."}` with `400` for validation errors (path-traversal, missing patch_plan, bad repo_path), `500` for unexpected.

## UI

Inside the Worker Runs subsection, after a successful import the status block already shows the new `proposal_dir`. Extend that flow:

- After `importWorkerRun` succeeds, the status `innerHTML` includes a small **"Validate imported proposal"** button. Clicking it opens a minimal prompt (or auto-fills) for `repo_path`, then POSTs to `/proposals/validate` with the freshly-imported `proposal_dir`.
- The result is rendered inline: `apply_success`, `validation_ok`, and the truncated message. Path to `apply_result.json` / `validation.json` is shown so the operator can `cat` it if they want.

For MVP we keep the button only in the Worker Runs section's import-result message. Adding it to every existing worker-run-import row in the Proposals list is deferred (7.2.1.1 polish).

## Tests

| File | Coverage |
|---|---|
| `tests/test_worker_runs.py` | `validate_imported_worker_proposal` refuses missing `patch_plan.json` · rejects path traversal · uses temp clone (subprocess `cwd` ≠ real repo) · real repo SHA-256 byte-identical before/after · writes `apply_result.json` + `validation.json` + `validation_output.txt` · updates `item.json.validation_status` · failed validation does not raise · works with `validation_command=""` (records `no_command`) |
| `tests/test_worker_runs_routes.py` | `/proposals/validate` happy path · refuses missing `proposal_dir` · refuses path traversal · refuses non-existent `repo_path` · returns `apply_success` + `validation_ok` keys |

## What this MVP does NOT do (deferred to 7.2.1.1+ or 7.2.2)

- Synthesizing `case.json` + `patch_proposal.json` so worker-run imports become lesson-promotable.
- Patch Safety call at the validate layer (currently relies on `apply_patch_plan`'s per-op checks).
- "Validate" button on every worker-run-import card in the Proposals list (only appears in Worker Runs section's post-import status for now).
- Re-running with a custom `validation_command` override from the UI.
- Asynchronous validation with progress polling (the route is synchronous, blocking on the subprocess).
- Concurrency lock — calling `/proposals/validate` on the same proposal twice in parallel is undefined behavior; the user shouldn't.

## Acceptance criteria

1. `core.worker_runs.validate_imported_worker_proposal(proposal_dir, repo_path)` returns a dict with `ok`, `apply_success`, `validation_ok`, `message`.
2. A proposal_dir with `patch_plan.json` produces `apply_result.json` + `validation.json` + `validation_output.txt` inside the proposal_dir.
3. A proposal_dir missing `patch_plan.json` raises `FileNotFoundError` with a clear message.
4. A path that escapes `<AI-project>/.agent/proposals/` raises `ValueError("...outside...")`.
5. Real repo files (under `repo_path`) are byte-identical before and after the call (verified via SHA-256 over every file).
6. A patch_plan whose application fails records `apply_success=False`, writes apply_result.json with the error, and does NOT raise.
7. A repo where no validation command can be inferred records `validation_status="no_command"` in item.json and does NOT raise.
8. The route `POST /proposals/validate` accepts `proposal_dir` + `repo_path`, returns the dict from #1, and rejects bad inputs with 400.
9. All eight items above are covered by tests.
