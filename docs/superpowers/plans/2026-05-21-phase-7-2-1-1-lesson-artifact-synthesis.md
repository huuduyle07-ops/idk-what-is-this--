# Phase 7.2.1.1 — Lesson Artifact Synthesis (Implementation Plan)

**Goal:** After `validate_imported_worker_proposal` confirms apply+validation passed, deterministically synthesize the missing `case.json` + `patch_proposal.json` so `scripts/create_lesson_from_proposal.py` accepts the worker-run import.

**Architecture:** One new public function in `core/worker_runs.py`, one new call site inside `validate_imported_worker_proposal`, additive `lesson_artifacts` field in the validate route response, one tiny UI line in the validate-result panel. No new dependencies. No changes to `lesson_quality`, `create_lesson_from_proposal.py`, or any safety gate.

**Spec:** `docs/superpowers/specs/2026-05-21-phase-7-2-1-1-lesson-artifact-synthesis-design.md`

---

## File map

**Modify:**
- `core/worker_runs.py` — add `synthesize_lesson_artifacts_for_validated_worker_proposal()`; call it from `validate_imported_worker_proposal()` at the end.
- `web/templates/index.html` — extend `validateImportedProposalWith` to render a `lesson_artifacts` line.
- `tests/test_worker_runs.py` — ~10 new tests (helper + wiring + integration).
- `tests/test_worker_runs_routes.py` — 2 new tests (route response includes `lesson_artifacts`).
- `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md` — Phase 7.2.1.1 shipped block.

Estimated new lines: ~450 (core ~140, UI ~25, tests ~270, docs ~20).

---

## Task A — `synthesize_lesson_artifacts_for_validated_worker_proposal` + tests

**Files:**
- Modify: `core/worker_runs.py`
- Modify: `tests/test_worker_runs.py`

### TDD step list

1. **Append the failing tests** to `tests/test_worker_runs.py`. See the spec for the full schema and the helper's behavior contract. Tests must cover:
   - happy path (writes both files with correct shape)
   - skip on apply failure
   - skip on validation_ok=False
   - preserve existing case.json
   - preserve existing patch_proposal.json
   - missing proposal.md raises FileNotFoundError
   - missing patch_plan.json raises FileNotFoundError
   - path traversal raises ValueError("outside")
   - language inference from `.py`/`.go`/`.rs`/etc.
   - summary extracts first useful line, skipping `#`-headers and ```` ```code ```` fences and `<!--` comments
   - real-repo byte-identical SHA-256

2. **Run** — expect AttributeError.

3. **Implement** in `core/worker_runs.py`. Add the helper and its private dependencies (file readers, summary extractor, language inferrer, slug helper). Reuse `_resolve_proposal_dir` from 7.2.1. Use `config.LANGUAGE_MAP` for extension → language.

4. **Run** — expect all new tests passing plus the existing 24.

5. **Commit** — `core/worker_runs.py` and `tests/test_worker_runs.py`.

```
feat(worker_runs): synthesize_lesson_artifacts_for_validated_worker_proposal

After a worker-run-imported proposal has apply_result + validation showing
success, write a minimal case.json and patch_proposal.json so
scripts/create_lesson_from_proposal.py accepts the import end-to-end.

Helper is deterministic (no LLM), preserves existing artifacts, and
self-gates: refuses to write anything if apply_result.success is not True
or validation.validation_ok is not True. Returns
{ok, created, preserved, skipped_reason} for caller-side rendering.

Synthesized case.json carries name + case_name (both = slug), language
(inferred from changed-file extensions via config.LANGUAGE_MAP),
category="worker_import", source="worker_run", validation_command from
validation.json, plus explicit empty expected_changed_files /
forbidden_changed_files lists so the lesson promoter's set math
short-circuits cleanly.

Synthesized patch_proposal.json embeds the full patch_plan list so
_determine_patch_kind returns "patch_plan", plus summary (first useful
proposal.md line with markdown headers / code fences / HTML comments
skipped) and an explicit patch_candidate=null / needs_human_review=false.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task B — Wire into `validate_imported_worker_proposal` + UI message

**Files:**
- Modify: `core/worker_runs.py`
- Modify: `web/templates/index.html`
- Modify: `tests/test_worker_runs.py` (2 wiring tests)
- Modify: `tests/test_worker_runs_routes.py` (2 route tests)

### Step list

1. **Wiring test** — happy path: validate returns `lesson_artifacts.ok=True` with non-empty `created` array.
2. **Wiring test** — failure path: validate returns `lesson_artifacts.ok=False` with `skipped_reason`.
3. **Route test** — happy path: `/proposals/validate` response includes `lesson_artifacts`.
4. **Route test** — failure path: same, with `ok=False`.
5. **Run** — expect 4 failures (KeyError on `lesson_artifacts`).
6. **Wire** — in `validate_imported_worker_proposal`, after writing artifacts + updating item.json, call `synthesize_lesson_artifacts_for_validated_worker_proposal(resolved, validation_result=validation)`. Add to the returned dict.
7. **UI** — in `validateImportedProposalWith`, after the existing result lines, append:
   ```js
   const la = body.lesson_artifacts || {};
   if (la.ok === true) {
     const created = (la.created || []).join(", ") || "all preserved";
     resultEl.innerHTML += `<div style="font-size:11px; color:#475569; margin-top:4px;">Lesson artifacts ready (${_escapeHtml(created)})</div>`;
   } else if (la.ok === false) {
     resultEl.innerHTML += `<div style="font-size:11px; color:#a16207; margin-top:4px;">Lesson artifacts not created: ${_escapeHtml(la.skipped_reason || "unknown")}</div>`;
   }
   ```
8. **Run all** — expect green.
9. **Commit** — all four files.

```
feat(worker_runs/web/ui): surface lesson_artifacts result through validate

validate_imported_worker_proposal now always calls the synth helper
(which self-gates on success). The returned dict carries lesson_artifacts
{ok, created, preserved, skipped_reason}. POST /proposals/validate forwards
the field verbatim. The validate-result panel in the UI renders one extra
muted line: "Lesson artifacts ready (...)" or "Lesson artifacts not
created: <reason>".

No existing response keys change. No existing UI elements removed.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task C — End-to-end integration test + roadmap

**Files:**
- Modify: `tests/test_worker_runs.py` (integration test)
- Modify: `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`

### Step list

1. **Integration test** — set up a complete worker import + happy-path validate (with mocks for apply + inferred command), then call `scripts.create_lesson_from_proposal.create_lesson_from_proposal(proposal_dir)`. Monkeypatch `core.lesson_store.get_agent_dir` and `lesson_store.config.LESSON_AUTO_ACTIVE` (same pattern as `test_proposal_queue_lesson_candidates`). Assert the returned lesson has `status="candidate"` and `source="patch_proposal"`.
2. **Run** — expect green.
3. **Roadmap append** — Phase 7.2.1.1 shipped block + remaining 7.2.1.1.1+ candidates.
4. **Commit** — both files.

```
feat(worker_runs): integration test — synthesized worker imports lessonize end-to-end

After validate_imported_worker_proposal passes, calling
scripts.create_lesson_from_proposal.create_lesson_from_proposal on the
same proposal_dir returns a candidate lesson with status="candidate"
and source="patch_proposal". Closes the last gap between Phase 7.1
handoff output and the lesson candidacy path.

Roadmap entry records the shipment and the remaining 7.2.1.1.x
follow-up candidates (UI "Create candidate lesson" button, custom
synth fields, etc.) for the user's accept/reject decision.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Self-review

- **Spec coverage:** helper ↔ Task A, wiring + UI ↔ Task B, integration + roadmap ↔ Task C.
- **No placeholders.**
- **Type consistency:** `lesson_artifacts` keys are `ok`, `created`, `preserved`, `skipped_reason` everywhere.
- **No safety regressions:** helper self-gates on apply_success+validation_ok; nothing in this slice changes `lesson_quality`, `create_lesson_from_proposal.py`, or the Patch Safety gate.

## Execution

Inline TDD, same cadence as 7.2.1: one commit per task, full suite green after each, real-repo SHA-256 check in the helper test.
