# Phase 7.2.1.1 — Make Validated Worker Imports Lesson-Promotable (MVP)

> Status: design approved 2026-05-21.
> Scope: synthesize missing `case.json` + `patch_proposal.json` after a validated worker import. Deterministic, no LLM.

## Goal

After `validate_imported_worker_proposal` (Phase 7.2.1) writes `apply_result.json` and `validation.json` and they show success, synthesize the two artifacts that `scripts/create_lesson_from_proposal.py` still demands (`case.json`, `patch_proposal.json`) so the existing proposal → candidate-lesson flow accepts a worker-run import end-to-end.

The lesson is still **candidate** after this — never auto-promoted. `lesson_quality` evaluates the synthesized artifacts the same way it evaluates queue-proposal artifacts.

## Non-goals

- Auto-creating a lesson on a successful validate
- Auto-promoting a candidate → active
- Calling an LLM
- Applying anything to the real repo
- Changing `lesson_quality` rules
- Changing `create_lesson_from_proposal.py`'s required-files gate
- Changing the Patch Safety gate
- Re-running subagents

## Architecture

```
core/worker_runs.py (additions)        # synthesize_lesson_artifacts_for_validated_worker_proposal()
                                        # validate_imported_worker_proposal() wires in the synth call
web/app.py                              # /proposals/validate response now includes lesson_artifacts
web/templates/index.html               # tiny UI line in the validate-result panel
tests/test_worker_runs.py (additions)   # helper + wiring + integration tests
docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md  # shipped block
```

No new pip dependencies. No changes to `scripts/create_lesson_from_proposal.py`.

## `core/worker_runs.py` additions

### Public helper

```python
def synthesize_lesson_artifacts_for_validated_worker_proposal(
    proposal_dir: str | Path,
    validation_result: dict | None = None,
    *,
    proposals_root: Path | None = None,
) -> dict[str, Any]:
    """If apply+validation passed, synthesize a minimal case.json and
    patch_proposal.json so `scripts/create_lesson_from_proposal.py` can
    accept the worker-run import.

    Returns:
      {
        "ok": bool,
        "created": ["case.json", "patch_proposal.json"],  # subset
        "preserved": [...],
        "skipped_reason": None | "...",
      }
    """
```

### Behavior contract

1. `proposal_dir` resolves to a directory **strictly under** `proposals_root` (default `<AI-project>/.agent/proposals/`). Otherwise `ValueError("proposal_dir is outside ...")`.
2. The dir must contain **all four**: `proposal.md`, `patch_plan.json`, `apply_result.json`, `validation.json`. Missing any → `FileNotFoundError("lesson synthesis missing: ...")`.
3. Parse `apply_result.json` and (either) the in-memory `validation_result` parameter or read `validation.json` from disk.
4. **Gate:** if `apply_result.success` is not `True` OR `validation.validation_ok` is not `True`, return `{"ok": False, "created": [], "preserved": [], "skipped_reason": "..."}`. Do **not** write any file claiming success.
5. Read `patch_plan.json` (must be a non-empty list) and `proposal.md` (text, possibly empty).
6. If `case.json` does **not** exist, write a minimal stub (see schema below). If it exists, preserve it byte-for-byte; record in `preserved`.
7. Same rule for `patch_proposal.json`.
8. Never modifies any other file, never touches the real repo, never modifies the source `worker_runs/` dir.

### Synthesized `case.json` shape

```json
{
  "name": "<slug>",
  "case_name": "<slug>",
  "language": "<inferred from patch_plan extensions or 'unknown'>",
  "category": "worker_import",
  "difficulty": "unknown",
  "validation_command": "<from validation.json.command or ''>",
  "source": "worker_run",
  "expected_changed_files": [],
  "forbidden_changed_files": []
}
```

- `name` and `case_name` are both written for compatibility (the existing case-shape convention uses `name`; the user-facing spec used `case_name`).
- `expected_changed_files=[]` and `forbidden_changed_files=[]` are explicit so `create_lesson_from_proposal._build_candidate` doesn't compute spurious missing/forbidden lists.

### Synthesized `patch_proposal.json` shape

```json
{
  "source": "worker_run",
  "patch_kind": "patch_plan",
  "summary": "<first useful line of proposal.md or fallback>",
  "changed_files": ["<relative_path from each plan op>"],
  "validation_ok": true,
  "apply_success": true,
  "patch_plan": [<verbatim copy of patch_plan.json>],
  "patch_candidate": null,
  "needs_human_review": false
}
```

- `patch_plan` is embedded verbatim because `create_lesson_from_proposal._determine_patch_kind` returns `"patch_plan"` only when `proposal.get("patch_plan")` is truthy.
- `summary` is the first non-empty, non-`#`, non-````-fence, non-`<!--` line of `proposal.md`. Falls back to `"Worker-run import: <slug>"` if no such line exists.
- `changed_files` is derived from `patch_plan` ops (`relative_path` or `file`), deduped, order-preserved.

### Slug + language inference

- **Slug** comes from (in order): `item.json.title` → slug of that; else proposal_dir name with leading `NN-` stripped if numeric.
- **Language** comes from the first plan op whose `relative_path` extension matches `config.LANGUAGE_MAP`. Otherwise `"unknown"`.

## Wiring into `validate_imported_worker_proposal`

After writing `apply_result.json`, `validation.json`, `validation_output.txt`, and updating `item.json.validation_status`:

```python
lesson_artifacts = synthesize_lesson_artifacts_for_validated_worker_proposal(
    resolved, validation_result=validation
)
return {
    "ok": True,
    "proposal_dir": str(resolved),
    "apply_success": apply_success,
    "validation_ok": val_ok,
    "message": message,
    "apply_result_path": str(resolved / "apply_result.json"),
    "validation_path": str(resolved / "validation.json"),
    "lesson_artifacts": lesson_artifacts,
}
```

The helper is **always** called (even on apply/validation failure) because it self-gates and returns `ok=False` with `skipped_reason` for failures. Callers can render a clean message in either case.

## Web route

`POST /proposals/validate` already returns the validate dict verbatim, so adding `lesson_artifacts` to that dict surfaces it through the route with **no other shape changes**. Existing fields (`ok`, `apply_success`, `validation_ok`, `message`, `apply_result_path`, `validation_path`, `proposal_dir`) are untouched.

## UI

In the validate-result panel (Phase 7.2.1's inline panel inside the Worker Runs section), add one line below the apply/validation marks:

- `body.lesson_artifacts.ok == True`: `Lesson artifacts ready (created: case.json, patch_proposal.json)` (mention only what's in `created` — empty if both were preserved).
- `body.lesson_artifacts.ok == False`: `Lesson artifacts not created: <skipped_reason>`.

No new buttons. The operator still has to run `create_lesson_from_proposal.py` (CLI or future UI button) to actually create the candidate lesson — this slice only removes the "missing files" blocker.

## Tests

| File | Coverage |
|---|---|
| `tests/test_worker_runs.py` | Helper: writes case.json + patch_proposal.json on success · skips on apply failure · skips on validation_ok=False · preserves existing case.json · preserves existing patch_proposal.json · refuses missing proposal.md · refuses missing patch_plan.json · rejects path traversal · infers language from changed-file extensions · real-repo SHA-256 unchanged · summary extraction skips markdown headers and code fences. Wiring: validate returns `lesson_artifacts.ok=True` on happy path · returns `lesson_artifacts.ok=False` with skipped_reason on validation failure. Integration: `scripts/create_lesson_from_proposal.create_lesson_from_proposal(proposal_dir)` succeeds after validate, producing a candidate lesson with status="candidate" |
| `tests/test_worker_runs_routes.py` | `/proposals/validate` happy-path response includes `lesson_artifacts.ok=True` with `created` array; failure path includes `lesson_artifacts.ok=False` with `skipped_reason` |

## What this slice does NOT do (deferred)

- A "Create candidate lesson" button in the Worker Runs section. The synth makes the CLI work; the UI button is 7.2.1.1.1 polish.
- Pretty-printing the patch_plan body inside the synthesized `patch_proposal.json` (already pretty-printed via `json.dumps(..., indent=2)`).
- Re-synthesizing if `validation_status` changes after the first synth (caller should delete and re-run if they want re-derivation).
- Synth on validation runs where `apply_success=True` and `validation_ok=None` (no command inferred). Treated as failure: nothing to vouch for.

## Acceptance criteria

1. `synthesize_lesson_artifacts_for_validated_worker_proposal(proposal_dir)` returns `{ok, created, preserved, skipped_reason}`.
2. On apply+validation success, `case.json` and `patch_proposal.json` exist in the proposal_dir.
3. On apply or validation failure, `ok=False` and `skipped_reason` names the failure; no files are created.
4. Existing `case.json` / `patch_proposal.json` are preserved verbatim (byte-identical) and listed in `preserved`.
5. Missing `proposal.md` → `FileNotFoundError`.
6. Missing `patch_plan.json` → `FileNotFoundError`.
7. Path traversal → `ValueError("...outside...")`.
8. After a happy-path validate, `scripts/create_lesson_from_proposal.create_lesson_from_proposal(proposal_dir)` returns a lesson with `status="candidate"`.
9. Real-repo files byte-identical before and after the whole flow.
10. All nine above covered by tests.
