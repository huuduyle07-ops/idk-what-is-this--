# Phase 7.2.1 — Validate Imported Worker Proposals (Implementation Plan)

**Goal:** Ship the validate step for worker-run-imported proposals: copy a repo to a temp clone, apply `patch_plan.json` there, run the inferred validation command, and write `apply_result.json` / `validation.json` / `validation_output.txt` into the proposal dir.

**Architecture:** One new function in `core/worker_runs.py`, one new web route, one UI button. Reuses `core.run_lifecycle.run_patch_plan_with_artifacts` for the apply step and `scripts.run_patch_proposal_queue._run_validation_command` for the validation step (same allow-list + segmented timeout as the proposal queue). Real repo / `repo_path` are never modified.

**Spec:** `docs/superpowers/specs/2026-05-21-phase-7-2-1-validate-imported-proposals-design.md`

---

## File map

**Modify:**
- `core/worker_runs.py` — add `validate_imported_worker_proposal()`
- `web/app.py` — add `POST /proposals/validate` route
- `web/templates/index.html` — add Validate button in the Worker Runs import-result flow
- `tests/test_worker_runs.py` — add 7 new tests
- `tests/test_worker_runs_routes.py` — add 4 new route tests
- `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md` — Phase 7.2.1 shipped block

Estimated new lines: ~450 (core ~110, route ~35, UI ~60, tests ~240, docs ~25).

---

## Task A — `validate_imported_worker_proposal` + tests

**Files:**
- Modify: `core/worker_runs.py`
- Modify: `tests/test_worker_runs.py`

### TDD step list

1. **Write the failing tests** — append to `tests/test_worker_runs.py`:

```python
# ---- validate_imported_worker_proposal --------------------------------------


def _import(env, run_id):
    """Import a complete worker run and return the proposal_dir."""
    run_dir = _make_run(env, run_id)
    result = worker_runs.import_worker_run_as_proposal(run_dir)
    return Path(result["proposal_dir"])


def test_validate_refuses_missing_patch_plan_json(env):
    run_dir = _make_run(env, "20260521_010000_a")
    result = worker_runs.import_worker_run_as_proposal(run_dir)
    proposal_dir = Path(result["proposal_dir"])
    (proposal_dir / "patch_plan.json").unlink()
    with pytest.raises(FileNotFoundError, match="patch_plan.json"):
        worker_runs.validate_imported_worker_proposal(
            proposal_dir, env["fake_repo"]
        )


def test_validate_rejects_proposal_path_traversal(env, tmp_path):
    outside = tmp_path / "outside_proposal"
    outside.mkdir()
    (outside / "patch_plan.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        worker_runs.validate_imported_worker_proposal(
            outside, env["fake_repo"]
        )


def test_validate_rejects_missing_repo_path(env):
    proposal_dir = _import(env, "20260521_010000_b")
    with pytest.raises(FileNotFoundError):
        worker_runs.validate_imported_worker_proposal(
            proposal_dir, env["fake_repo"].parent / "does_not_exist"
        )


def test_validate_writes_apply_and_validation_artifacts(env, monkeypatch):
    proposal_dir = _import(env, "20260521_010000_c")

    # Mock the apply step to a no-op success that doesn't actually touch any file.
    def fake_apply(project_root, plan, validation_command=None, user_query="",
                   control_result=None, source="pipeline"):
        return {
            "success": True,
            "applied_ops": plan,
            "diffs": ["--- a\n+++ b\n@@\n-x = 1\n+x = 2\n"],
            "error": None,
            "rollback_performed": False,
            "validation_ok": None,
            "validation_command": "",
            "validation_output": "",
        }
    import core.worker_runs as _wr
    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(_wr, "_inferred_validation_command",
                        lambda repo: "echo OK")

    result = worker_runs.validate_imported_worker_proposal(
        proposal_dir, env["fake_repo"]
    )

    assert result["ok"] is True
    assert result["apply_success"] is True
    assert result["validation_ok"] is True
    assert (proposal_dir / "apply_result.json").is_file()
    assert (proposal_dir / "validation.json").is_file()
    assert (proposal_dir / "validation_output.txt").is_file()

    import json as _json
    item = _json.loads((proposal_dir / "item.json").read_text(encoding="utf-8"))
    assert item["needs_revalidation"] is False
    assert item["validation_status"] == "passed"


def test_validate_real_repo_byte_identical(env, monkeypatch):
    proposal_dir = _import(env, "20260521_010000_d")
    before = _real_repo_state(env["fake_repo"])

    def fake_apply(project_root, plan, **kw):
        # Pretend to apply: write a file into the temp clone to verify
        # the function passed the clone path (not the real repo).
        Path(project_root, "EVIDENCE_FROM_APPLY.txt").write_text("ok", encoding="utf-8")
        return {"success": True, "applied_ops": plan, "diffs": [], "error": None}
    import core.worker_runs as _wr
    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    worker_runs.validate_imported_worker_proposal(proposal_dir, env["fake_repo"])

    after = _real_repo_state(env["fake_repo"])
    assert before == after, "real repo unchanged after validate"
    assert not (env["fake_repo"] / "EVIDENCE_FROM_APPLY.txt").exists()


def test_validate_failed_apply_does_not_crash(env, monkeypatch):
    proposal_dir = _import(env, "20260521_010000_e")

    def fake_apply(project_root, plan, **kw):
        return {"success": False, "error": "snippet not found", "applied_ops": [], "diffs": []}
    import core.worker_runs as _wr
    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    result = worker_runs.validate_imported_worker_proposal(
        proposal_dir, env["fake_repo"]
    )

    assert result["ok"] is True
    assert result["apply_success"] is False
    assert result["validation_ok"] is None
    assert (proposal_dir / "apply_result.json").is_file()
    assert (proposal_dir / "validation.json").is_file()

    import json as _json
    item = _json.loads((proposal_dir / "item.json").read_text(encoding="utf-8"))
    assert item["validation_status"] == "failed"


def test_validate_no_command_inferred_records_no_command(env, monkeypatch):
    proposal_dir = _import(env, "20260521_010000_f")

    def fake_apply(project_root, plan, **kw):
        return {"success": True, "applied_ops": plan, "diffs": [], "error": None}
    import core.worker_runs as _wr
    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "")

    result = worker_runs.validate_imported_worker_proposal(
        proposal_dir, env["fake_repo"]
    )

    assert result["apply_success"] is True
    assert result["validation_ok"] is None
    import json as _json
    item = _json.loads((proposal_dir / "item.json").read_text(encoding="utf-8"))
    assert item["validation_status"] == "no_command"
```

2. **Run the tests** — expect attribute errors / module-level missing symbol.

3. **Implement** — append to `core/worker_runs.py`:

```python
import shutil
import tempfile
from core.run_lifecycle import run_patch_plan_with_artifacts


_VALIDATE_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".agent", "node_modules", "target",
    ".venv", "venv", "__pycache__", ".pytest_cache",
    "dist", "build",
)


def _inferred_validation_command(repo: Path) -> str:
    """Best-effort inference: language from `inspect_repo_inventory`, command
    from `get_default_validation_command`. Returns "" if no command applies.

    Isolated in a thin helper so tests can monkeypatch it.
    """
    try:
        from core.repo_librarian import inspect_repo_inventory
        from core.validation_command import get_default_validation_command
        language = inspect_repo_inventory(str(repo)).get("primary_language", "unknown")
        return get_default_validation_command(language, repo) or ""
    except Exception:
        return ""


def _read_proposal_title(proposal_dir: Path) -> str:
    item_path = proposal_dir / "item.json"
    if item_path.is_file():
        try:
            data = json.loads(item_path.read_text(encoding="utf-8"))
            title = data.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
        except (OSError, json.JSONDecodeError):
            pass
    return proposal_dir.name


def _resolve_proposal_dir(
    path_or_id: str | Path, proposals_root: Path
) -> Path:
    raw = str(path_or_id).strip()
    if not raw:
        raise ValueError("proposal_dir is empty")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = proposals_root / candidate
    candidate = candidate.expanduser().resolve()
    root_resolved = proposals_root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"proposal_dir is outside {root_resolved}: {candidate}"
        ) from exc
    if not candidate.is_dir():
        raise FileNotFoundError(f"proposal_dir not found: {candidate}")
    return candidate


def _update_item_status(proposal_dir: Path, status: str) -> None:
    item_path = proposal_dir / "item.json"
    if not item_path.is_file():
        return
    try:
        item = json.loads(item_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(item, dict):
        return
    item["needs_revalidation"] = False
    item["validation_status"] = status
    item["validation_status_at"] = _now_iso()
    item_path.write_text(
        json.dumps(item, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def validate_imported_worker_proposal(
    proposal_dir: str | Path,
    repo_path: str | Path,
    *,
    proposals_root: Path | None = None,
    validation_timeout_sec: int = 60,
) -> dict[str, Any]:
    proposals_dst_root = _resolve_proposals_root(proposals_root)
    resolved = _resolve_proposal_dir(proposal_dir, proposals_dst_root)

    plan_path = resolved / "patch_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError(
            f"proposal_dir missing patch_plan.json: {resolved}"
        )
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"patch_plan.json is not valid JSON: {exc}") from exc
    if not isinstance(plan, list) or not plan:
        raise ValueError("patch_plan.json must be a non-empty JSON list")

    repo_src = Path(repo_path).expanduser().resolve()
    if not repo_src.is_dir():
        raise FileNotFoundError(f"repo_path is not a directory: {repo_src}")

    title = _read_proposal_title(resolved)
    apply_result: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    validation_output_text = ""

    with tempfile.TemporaryDirectory(
        prefix="worker-validate-", ignore_cleanup_errors=True
    ) as tmp_dir:
        temp_clone = Path(tmp_dir) / "repo"
        shutil.copytree(repo_src, temp_clone, ignore=_VALIDATE_COPY_IGNORE)

        try:
            apply_result = run_patch_plan_with_artifacts(
                str(temp_clone),
                plan,
                validation_command=None,
                user_query=title,
                control_result={
                    "route": "worker_run_validate",
                    "proposal_dir": str(resolved),
                    "title": title,
                },
                source="worker_run_validate",
            )
        except Exception as exc:
            apply_result = {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "applied_ops": [],
                "diffs": [],
            }

        (resolved / "apply_result.json").write_text(
            json.dumps(apply_result, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        validation_command = _inferred_validation_command(temp_clone)

        if apply_result.get("success") and validation_command:
            try:
                from scripts.run_patch_proposal_queue import _run_validation_command
                validation = _run_validation_command(
                    validation_command,
                    cwd=temp_clone,
                    timeout_sec=max(1, int(validation_timeout_sec)),
                )
            except Exception as exc:
                validation = {
                    "ok": False,
                    "validation_ok": False,
                    "command": validation_command,
                    "error": f"validation runner error: {type(exc).__name__}: {exc}",
                    "duration_sec": 0.0,
                    "segments": [],
                    "output": "",
                }
        elif not apply_result.get("success"):
            validation = {
                "ok": False,
                "validation_ok": None,
                "command": validation_command,
                "error": "apply did not succeed; validation skipped",
                "duration_sec": 0.0,
                "segments": [],
                "output": "",
            }
        else:
            # apply succeeded but no command could be inferred
            validation = {
                "ok": True,
                "validation_ok": None,
                "command": "",
                "error": "no validation command inferred",
                "duration_sec": 0.0,
                "segments": [],
                "output": "",
            }

        validation_output_text = validation.get("output") or ""

    (resolved / "validation.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (resolved / "validation_output.txt").write_text(
        validation_output_text, encoding="utf-8"
    )

    apply_success = bool(apply_result.get("success"))
    val_ok = validation.get("validation_ok")
    if not apply_success:
        status = "failed"
        message = "Apply failed: " + str(apply_result.get("error") or "(no detail)")
    elif val_ok is True:
        status = "passed"
        message = "Apply and validation passed."
    elif val_ok is False:
        status = "failed"
        message = "Apply succeeded but validation failed."
    else:
        status = "no_command"
        message = "Apply succeeded; no validation command inferred — record only."

    _update_item_status(resolved, status)

    return {
        "ok": True,
        "proposal_dir": str(resolved),
        "apply_success": apply_success,
        "validation_ok": val_ok,
        "message": message,
        "apply_result_path": str(resolved / "apply_result.json"),
        "validation_path": str(resolved / "validation.json"),
    }
```

4. **Run the tests** — expect 7 passing. Fix any signature mismatches.

5. **Commit** — `core/worker_runs.py` and `tests/test_worker_runs.py`.

```
feat(worker_runs): validate_imported_worker_proposal applies + validates in temp clone

Copies repo_path to a temp clone, applies patch_plan.json via
run_patch_plan_with_artifacts, runs the inferred validation command
via the proposal queue's _run_validation_command, and writes
apply_result.json / validation.json / validation_output.txt into the
proposal_dir. Updates item.json's validation_status to
passed/failed/no_command without touching other fields.

Refuses path traversal, missing patch_plan.json, missing repo_path,
non-list / empty plans. Real repo and repo_path are byte-identical
before and after (verified by SHA-256 round-trip test).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task B — `POST /proposals/validate` route

**Files:**
- Modify: `web/app.py`
- Modify: `tests/test_worker_runs_routes.py`

### TDD step list

1. **Write the failing tests** — append to `tests/test_worker_runs_routes.py`:

```python
def test_validate_route_happy_path(client, monkeypatch):
    # Import a complete worker run so a proposal_dir exists.
    _make_complete_run(client, run_id="20260521_010001_v")
    resp = client.post("/worker-runs/import", data={"run_id": "20260521_010001_v"})
    proposal_dir = resp.get_json()["proposal_dir"]

    # Mock the heavy lifting so the route is the only thing under test.
    import core.worker_runs as _wr
    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts",
                        lambda project_root, plan, **kw: {
                            "success": True, "applied_ops": plan,
                            "diffs": [], "error": None,
                        })
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    resp = client.post("/proposals/validate", data={
        "proposal_dir": proposal_dir,
        "repo_path": str(client._fake_repo),
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["apply_success"] is True
    assert body["validation_ok"] is True
    assert body["proposal_dir"] == proposal_dir


def test_validate_route_requires_proposal_dir(client):
    resp = client.post("/proposals/validate",
                       data={"repo_path": str(client._fake_repo)})
    assert resp.status_code == 400


def test_validate_route_requires_repo_path(client, monkeypatch):
    _make_complete_run(client, run_id="20260521_010002_v")
    resp = client.post("/worker-runs/import", data={"run_id": "20260521_010002_v"})
    proposal_dir = resp.get_json()["proposal_dir"]
    resp = client.post("/proposals/validate", data={"proposal_dir": proposal_dir})
    assert resp.status_code == 400


def test_validate_route_rejects_path_traversal(client, tmp_path):
    outside = tmp_path / "outside_proposal"
    outside.mkdir()
    (outside / "patch_plan.json").write_text("[]", encoding="utf-8")
    resp = client.post("/proposals/validate", data={
        "proposal_dir": str(outside),
        "repo_path": str(client._fake_repo),
    })
    assert resp.status_code == 400
    body = resp.get_json()
    assert "outside" in body["error"]
```

2. **Run** — expect 404 / Flask route-not-found.

3. **Add the route** in `web/app.py` after `/worker-runs/import`:

```python
@app.route("/proposals/validate", methods=["POST"])
def proposals_validate_route():
    """Phase 7.2.1: revalidate an imported worker proposal's patch_plan.json
    in a temp clone of repo_path. Writes apply_result.json + validation.json +
    validation_output.txt into the proposal_dir. Never modifies the real repo.
    """
    from core import worker_runs as _worker_runs
    proposal_dir = (request.form.get("proposal_dir") or "").strip()
    repo_path = (request.form.get("repo_path") or "").strip()
    if not proposal_dir:
        return {"ok": False, "error": "proposal_dir is required"}, 400
    if not repo_path:
        return {"ok": False, "error": "repo_path is required"}, 400
    try:
        timeout_sec = int(request.form.get("validation_timeout_sec") or 60)
    except ValueError:
        return {"ok": False, "error": "validation_timeout_sec must be int"}, 400
    try:
        result = _worker_runs.validate_imported_worker_proposal(
            proposal_dir,
            repo_path,
            validation_timeout_sec=timeout_sec,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}, 400
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return result
```

4. **Run the tests** — expect green.

5. **Commit** — `web/app.py` and `tests/test_worker_runs_routes.py`.

```
feat(web): POST /proposals/validate route for worker-run-imported proposals

Takes proposal_dir + repo_path (both required) and an optional
validation_timeout_sec. Returns the dict from
validate_imported_worker_proposal verbatim. Rejects missing args /
path-traversal / non-existent paths with 400.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task C — Validate button in the Worker Runs UI

**Files:**
- Modify: `web/templates/index.html`

After `importWorkerRun` succeeds, the inline status block currently shows the new proposal_dir. Extend it to include a "Validate" button.

### Step 1 — Modify `importWorkerRun` in `web/templates/index.html`

Find the success branch (look for `Imported to <code>`) and replace the `status.innerHTML = ...` line with a structure that includes the button and a result panel:

```javascript
if (status) {
    const proposalDir = body.proposal_dir;
    const escapedDir = _escapeHtml(proposalDir).replace(/'/g, "\\'");
    status.innerHTML =
        `Imported to <code>${_escapeHtml(proposalDir)}</code>. ` +
        `<button type="button" onclick="validateImportedProposal('${escapedDir}', this)">Validate imported proposal</button>` +
        `<div class="validate-result" style="margin-top:8px;"></div>`;
}
```

### Step 2 — Add `validateImportedProposal` next to `importWorkerRun`

```javascript
async function validateImportedProposal(proposalDir, btn) {
    const repoPathInput = document.querySelector("input[name='repo_path']");
    const repoPath = (repoPathInput && repoPathInput.value.trim()) || "";
    if (!repoPath) {
        const prompted = prompt("Enter repo_path to validate against (absolute path):");
        if (!prompted || !prompted.trim()) return;
        // (intentionally do not write back to the input — keep this opt-in)
        return validateImportedProposalWith(proposalDir, prompted.trim(), btn);
    }
    return validateImportedProposalWith(proposalDir, repoPath, btn);
}

async function validateImportedProposalWith(proposalDir, repoPath, btn) {
    const card = btn.closest("div") || btn.parentElement;
    const resultEl = card.querySelector(".validate-result");
    btn.disabled = true;
    if (resultEl) resultEl.innerHTML = "<em>Validating in temp clone... (this can take ~60s)</em>";
    try {
        const fd = new FormData();
        fd.append("proposal_dir", proposalDir);
        fd.append("repo_path", repoPath);
        const resp = await fetch("/proposals/validate", { method: "POST", body: fd });
        const body = await resp.json();
        if (!body.ok) {
            if (resultEl) resultEl.innerHTML = `<strong style="color:#b91c1c;">Error:</strong> ${_escapeHtml(body.error || "unknown")}`;
            btn.disabled = false;
            return;
        }
        const applyMark = body.apply_success ? "✓" : "✗";
        const valMark = body.validation_ok === true ? "✓" : (body.validation_ok === false ? "✗" : "·");
        if (resultEl) {
            resultEl.innerHTML =
                `<div><strong>apply:</strong> ${applyMark} · <strong>validation:</strong> ${valMark}</div>` +
                `<div style="font-size:12px; color:#475569; margin-top:4px;">${_escapeHtml(body.message || "")}</div>` +
                `<div style="font-size:11px; color:#64748b; margin-top:4px;">` +
                `apply_result: <code>${_escapeHtml(body.apply_result_path || "")}</code>` +
                `<br>validation: <code>${_escapeHtml(body.validation_path || "")}</code></div>`;
        }
    } catch (e) {
        if (resultEl) resultEl.innerHTML = `<strong style="color:#b91c1c;">Error:</strong> ${_escapeHtml(e.message)}`;
        btn.disabled = false;
    }
}
```

### Step 3 — Smoke test

`python web/app.py`, open Memory tab → Mayor Mode → Worker Runs. Import a complete worker run (you can create one via the existing handoff flow with a fake worker command — or rely on the test fixtures). After import, the status block should show a Validate button. Clicking it (with the repo path input filled or via prompt) runs validation and surfaces the result inline.

### Step 4 — Commit

```
feat(ui): Validate button in Worker Runs import-result flow

After importWorkerRun succeeds, the status block now offers a
Validate imported proposal button. Clicking it calls /proposals/validate
with the freshly-imported proposal_dir and the operator's repo_path
(taken from the existing repo_path input, falling back to a prompt).
Result (apply ✓/✗, validation ✓/✗/·, message, artifact paths) is
rendered inline next to the import success message.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task D — Roadmap entry

**Files:**
- Modify: `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`

Append after the Phase 7.2 shipped block:

```markdown

---

## Phase 7.2.1 — Validate Imported Worker Proposals (shipped 2026-05-21)

Spec: `docs/superpowers/specs/2026-05-21-phase-7-2-1-validate-imported-proposals-design.md`
Plan: `docs/superpowers/plans/2026-05-21-phase-7-2-1-validate-imported-proposals.md`

### What this phase adds

- `core.worker_runs.validate_imported_worker_proposal(proposal_dir, repo_path)` — copies `repo_path` to a temp clone, applies the imported `patch_plan.json` via `run_patch_plan_with_artifacts(validation_command=None)`, then runs the inferred validation command via `scripts.run_patch_proposal_queue._run_validation_command` (allow-list + segmented timeout discipline). Writes `apply_result.json`, `validation.json`, `validation_output.txt` into the proposal_dir. Updates `item.json` with `needs_revalidation=False` and `validation_status` (`passed` / `failed` / `no_command`).
- Web route: `POST /proposals/validate` (`proposal_dir`, `repo_path`, optional `validation_timeout_sec`).
- UI: Worker Runs section's import-result message now includes a Validate button. Result rendered inline (apply ✓/✗, validation ✓/✗/·, message, artifact paths).
- Tests: 7 new in `tests/test_worker_runs.py`, 4 new in `tests/test_worker_runs_routes.py`. Real-repo SHA-256 byte-identical assertion in the validate tests.

### Guardrails (verified by tests)

- Real repo / `repo_path` byte-identical before and after.
- Subagents do not run in this slice.
- Patch is never applied to the real repo or to `repo_path` directly.
- `case.json` / `patch_proposal.json` are NOT synthesized — worker-run imports remain non-lesson-promotable via the existing `create_lesson_from_proposal.py` CLI until a future slice handles them explicitly.
- Path traversal: any `proposal_dir` that escapes `.agent/proposals/` is rejected before any file read.

### 🤖 Claude-proposed Phase 7.2.1+ follow-ups

1. **Worker-run lesson candidacy.** Synthesize a minimal `case.json` + `patch_proposal.json` from `handoff.md` + worker artifacts so a passing validate enables the existing `create_lesson_from_proposal.py` flow.
2. **Validate button on every worker-run-import proposal card.** Today the button only appears in the Worker Runs section's post-import status. Adding it to each row in the Proposals list lets the operator re-validate later.
3. **Custom validation_command override.** UI input to override the inferred command (useful when `inspect_repo_inventory` guesses wrong).
4. **Explicit patch-safety call.** The validate step currently relies on `apply_patch_plan`'s per-op gates. Calling `evaluate_patch_safety` upfront would short-circuit clearly-unsafe plans with a 400 instead of an apply error.
5. **Async + progress polling.** The route is synchronous; long validation can hit Flask's default timeout. Mirror `core/proposal_runner.py` for an async variant.
```

Commit:

```
docs(roadmap): record Phase 7.2.1 Validate Imported Worker Proposals shipment

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Self-review

- **Spec coverage:** core function ↔ Task A, route ↔ Task B, UI ↔ Task C, roadmap ↔ Task D. All four spec sections mapped.
- **No placeholders.** Every step includes the exact code or command.
- **Type consistency.** `validate_imported_worker_proposal` returns `{ok, proposal_dir, apply_success, validation_ok, message, apply_result_path, validation_path}` in the spec, in the implementation, in the route response, and in the tests.

## Execution

Inline TDD, same cadence as Phase 7.2: one commit per task, full test suite green after each task, real-repo SHA-256 assertion in the temp-clone test.
