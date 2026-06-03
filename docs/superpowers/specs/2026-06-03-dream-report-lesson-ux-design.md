# Phase 11-prep-cleanup-a: Dream Report + Lesson Review UX

**Date:** 2026-06-03  
**Scope:** UI/report workflow cleanup only — no patch generation, benchmark scoring, model/API, lesson auto-promotion, or active lesson retrieval changes.

---

## Goal

Improve the benchmark-failure → Dream report → proposal/candidate lesson review workflow:

1. Dream runs emit a richer, readable Markdown summary file (`dream_run_summary.md`).
2. The Dream UI prefers Markdown preview; raw txt/JSON stay accessible behind collapsed `<details>`.
3. Users can create a candidate lesson or proposal from any eligible Dream item via a single click.
4. Research/reference controls collapse automatically for bug/debug work types.
5. Lesson filters cover language, source, category, difficulty, and status — all client-side.

---

## Decisions

| Question | Decision |
| --- | --- |
| `dream_run_summary.md` — new file or rename? | **Rename** `morning_report.txt` → `dream_run_summary.md`; update all test references. |
| Create-lesson vs. create-proposal buttons | **Both** shown per eligible item; two separate routes. |
| Lesson filters — client-side or server-side? | **Client-side only** — uses already-loaded lesson data. |

---

## Section 1 — Artifact layer (`core/dream_artifacts.py`)

### `write_report_markdown()` → `write_dream_run_summary()`

- Rename the function. Output file: `dream_run_summary.md` (was `morning_report.txt`).
- All content derivation is **deterministic — no LLM calls**.

**New/enriched content (Req 2):**

| Section | Source |
| --- | --- |
| Run title/time | `# Dream run summary — YYYY-MM-DD HH:MM` |
| Queued items | `Total items: N` (unchanged) |
| Failure summary | `status_counts` table (unchanged) |
| Suspected root cause | Per-item: `item["hint"]` primary; `plan_analysis["root_cause"]` if present |
| Planned action / why no patch | Per-item: `patch_blocker_summary` + each blocker's `override_hint` |
| Candidate lesson text | `## Candidate lessons` — from `lesson_notes` in `case_ideas_payload` |
| Evidence file links | Per-item: `[artifacts](./00-slug/)` from `item_dir_name` |
| Next user actions | `## Next steps` — one bullet per unresolved item, text from blocker `override_hint` |

### `read_report()` fallback

```python
# Try new filename first; fall back to legacy for pre-rename run dirs.
summary_path = report_dir / "dream_run_summary.md"
if not summary_path.exists():
    summary_path = report_dir / "morning_report.txt"
```

- Returned dict key stays `morning_report` — no downstream key changes required.
- All ~20 test fixtures updated from `morning_report.txt` → `dream_run_summary.md`.

---

## Section 2 — `/dream/report` route + Dream modal UI

### Route (`web/app.py`)

One new field added to `dream_report_route()` response:

- `list_json_raw` — raw text of `list.json` (string, not re-parsed). Only included when the file is readable.

Existing `morning_report` and `morning_report_html` fields unchanged.

### Dream modal JS (`web/templates/index.html`)

Current modal body structure extended:

```
<details class="dream-report-summary" open>           ← unchanged, open by default
    <summary>Summary</summary>
    <div class="dream-report-md">…rendered HTML…</div>
</details>

<details class="dream-raw-details">                   ← NEW, collapsed
    <summary>Raw summary (dream_run_summary.md)</summary>
    <pre class="dream-report-pre">…raw text…</pre>
</details>

<details class="dream-raw-details">                   ← NEW, collapsed (only if list_json_raw present)
    <summary>Raw list.json</summary>
    <pre class="dream-report-pre">…list_json_raw…</pre>
</details>

<!-- existing: _renderCaseIdeaCandidates, items list, report meta -->
```

### Research controls collapse

A `change` listener on `#dreamType`:
- If value is `bug_investigation` or `debug`: add `hidden` to `.dream-references-section`; remove `open` from `#dreamTrialsSection`.
- Otherwise: restore both.
- Fires once on page load to set initial state.

`data-ui-group` anchors on both elements are preserved verbatim.

---

## Section 3 — Two new routes

### `POST /dream/create-lesson-candidate`

**Inputs:** `repo_path`, `date`, `run`, `item_idx` (int).

**Logic:**
1. `resolve_run_dir(repo_path, date, run)` → `report_dir`
2. `load_item_for_promotion(report_dir, item_idx)` → `item`
3. Build candidate dict from `{title, hint, kind, source="dream", case_name, language, category}`.
4. Force `LESSON_AUTO_ACTIVE = False` around `lesson_store.save_candidate_lesson()` call.
5. Return `{ok: True, lesson_id, status: "candidate", active_knowledge_allowed: false}`.

**Invariants:**
- Result is always `candidate` bucket, `active_knowledge_allowed=False`.
- Promotion requires an explicit Promote click in the Memory tab.
- No model, patch executor, or validation command is called.

For `ready_to_apply` items the existing `lesson_auto_candidates.maybe_create_lesson_candidate_from_dream_item(enabled=True)` path is used instead (richer artifact extraction). A JS helper selects the endpoint based on `status === "ready_to_apply"`.

### `POST /dream/create-proposal`

**Inputs:** `repo_path`, `date`, `run`, `item_idx`.

**Logic:**
1. Resolve run dir; load item.
2. Compute `proposal_dir = .agent/proposals/<date>-<run>/<item_dir_name or idx-slug>/`.
3. Write (no model call):
   - `proposal.json`: `{source, date, run_id, item_idx, title, hint, status, patch_blockers, created_at}`
   - `proposal.md`: Markdown with title, kind, hint, status, blocker details + override hints, evidence dir link, `## Next steps`.
4. Return `{ok: True, proposal_dir}`.

The written proposal surfaces in **Memory → Proposals** via `refreshProposals()` and follows the normal promote flow from there.

### Per-item buttons in the Dream report modal

Any item where `status` is not `error`/`skipped_*` and `item_dir_name` is set gets two buttons:

```
[Create candidate lesson]   [Create proposal]
```

The existing `lessonizeBtn` logic (only for `ready_to_apply`) is replaced by this broader eligibility check. Both buttons call their respective routes and show inline success/error feedback on the card without reloading the modal.

---

## Section 4 — Lesson filters (client-side)

### Filter row

The existing `.lessons-filters` row gains four `<select>` dropdowns appended after the status buttons, visually separated:

```
[All] [Candidate] [Active] [Blocked]  |  Language ▾  Source ▾  Category ▾  Difficulty ▾
```

Each defaults to an "All …" option (empty string = no filter). Difficulty dropdown is hidden if no loaded lesson has a `difficulty` field.

### Population

`_populateLessonFilterDropdowns(lessons)` runs after every `loadLessons()` fetch:

- **Language**: from `lesson.candidate?.language` → falling back to first tag matching a known-language set.
- **Source**: from `lesson.source` directly.
- **Category**: from `lesson.candidate?.category` → falling back to heuristic tag after language tag.
- **Difficulty**: from `lesson.candidate?.difficulty`; dropdown hidden if no values found.

### Unified filter pass

`_applyLessonFilters()` owns all five dimensions (status + four new):

```js
function _applyLessonFilters() {
    // reads _lessonFilters.{status, language, source, category, difficulty}
    // shows/hides .lesson-card elements via hidden attribute
    // no re-fetch
}
```

`filterLessons(status)` sets `_lessonFilters.status` then calls `_applyLessonFilters()`.  
New `_lessonData = []` and `_lessonFilters = {}` module-level vars cache state between filter interactions.

---

## Section 5 — Tests

### New test files

**`tests/test_dream_run_summary.py`**
- `test_write_dream_run_summary_creates_md_file` — `dream_run_summary.md` exists; `morning_report.txt` does NOT
- `test_dream_run_summary_content_sections` — file contains `# Dream run summary`, `## Summary`, `## Items`, `## Next steps`
- `test_dream_run_summary_includes_root_cause_from_hint` — item hint appears under item section
- `test_dream_run_summary_includes_candidate_lesson_text` — `lesson_notes` → `## Candidate lessons` section
- `test_dream_run_summary_includes_evidence_link` — `item_dir_name="00-slug"` → `[artifacts](./00-slug/)` in output
- `test_read_report_falls_back_to_morning_report_txt` — legacy dir with only `.txt` file → `morning_report` key still populated

**`tests/test_dream_lesson_proposal_routes.py`**
- `test_create_lesson_candidate_returns_candidate_status`
- `test_create_lesson_candidate_never_auto_promotes` — even with `LESSON_AUTO_ACTIVE=True`, result is `candidate`
- `test_create_proposal_writes_proposal_md_and_json`
- `test_create_proposal_no_model_call` — content derived from item data only; no subprocess or API call
- `test_create_lesson_candidate_active_knowledge_allowed_is_false`

**`tests/test_dream_research_controls_collapse.py`**
- `test_research_section_present_in_template` — `.dream-references-section` exists with no inline `hidden`
- `test_trials_section_is_details_element` — `#dreamTrialsSection` is a `<details>`
- `test_dream_taxonomy_has_bug_investigation` — GET `/dream/taxonomy` returns `bug_investigation` work type

**`tests/test_lesson_filters_client.py`**
- `test_lesson_filter_dropdowns_present_in_template` — `id="lessonFilterLanguage"`, `"lessonFilterSource"`, `"lessonFilterCategory"`, `"lessonFilterDifficulty"` all in `index.html`
- `test_lessons_list_route_returns_candidate_and_source_fields` — GET `/lessons/list` returns records with `source` and `candidate` dict

### Updated test files

**`tests/test_dream_report_markdown_rendering.py`**
- All `morning_report.txt` fixture writes → `dream_run_summary.md`
- `test_dream_report_route_returns_rendered_morning_html` — add assertion: `list_json_raw` present and non-empty
- New: `test_dream_report_route_exposes_list_json_raw` — `list_json_raw` parses as valid JSON with `items` key

### Regression guard (all test files)

- `test_no_forbidden_imports_in_new_route_code` — assert none of: `patch_engine`, `patch_plan_executor`, `run_benchmarks`, `anthropic`, `openai`, `run_gemini_request` appear in the new route handlers

### Validation sequence

1. `python -m compileall .` — zero syntax errors
2. Focused new test files — all green
3. Full `pytest` — all green
4. `benchmark --check` — 50 checked, 0 errors (patch/scoring/model behavior unchanged)

---

## Invariants (never violated)

- `active_knowledge_allowed` is only `true` when a lesson file lives in `active/` and was explicitly promoted by a human Promote click.
- No route added by this phase calls any model, runs any subprocess, executes any validation command, or reads/writes patch artifacts.
- All new file writes are atomic (temp-file + `os.replace` pattern, matching the rest of the codebase).
- `morning_report.txt` is never written by new code; existing run dirs that only have `.txt` continue to work.
