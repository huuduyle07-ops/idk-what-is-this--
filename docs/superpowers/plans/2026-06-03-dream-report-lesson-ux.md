# Phase 11-prep-cleanup-a: Dream Report + Lesson Review UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `write_report_markdown` → `write_dream_run_summary` (output `dream_run_summary.md`), enrich report content, add raw-panel collapse in the Dream modal, add two new Dream-item → lesson/proposal routes, collapse research controls for debug work types, and add client-side lesson filters — no patch/model/API/benchmark changes.

**Architecture:** Three layers: (1) `core/dream_artifacts.py` owns artifact writing/reading; (2) `web/app.py` owns new routes and the `list_json_raw` field; (3) `web/templates/index.html` owns all UI/JS changes. The compat alias `write_report_markdown = write_dream_run_summary` keeps untouched callers working until all sites are updated. Each task is test-first (write failing test → implement → verify green → commit).

**Tech Stack:** Python 3.x, Flask, Jinja2, vanilla JS (no new libraries).

---

## File Map

| File | Change |
|---|---|
| `core/dream_artifacts.py` | Rename fn, change output file, enrich content, update `read_report()` fallback |
| `core/sleeping_consultant.py` | Update call site to use `write_dream_run_summary` with `lesson_notes` |
| `web/app.py` | Add `list_json_raw` to `/dream/report`; add `/dream/create-lesson-candidate`; add `/dream/create-proposal` |
| `web/templates/index.html` | Raw collapsed panels, research controls collapse, per-item buttons, lesson filter UI + JS |
| `tests/test_dream_run_summary.py` | **NEW** – artifact writing + `read_report()` fallback tests |
| `tests/test_dream_lesson_proposal_routes.py` | **NEW** – new route tests |
| `tests/test_dream_research_controls_collapse.py` | **NEW** – template structure tests |
| `tests/test_lesson_filters_client.py` | **NEW** – lesson filter template/route tests |
| `tests/test_dream_report_markdown_rendering.py` | Update fixture filenames + add `list_json_raw` test |
| `tests/test_dream_case_ideas.py` | Update if it asserts `morning_report.txt` filename |

---

## Task 1: Write failing tests for write_dream_run_summary

**Files:**
- Create: `tests/test_dream_run_summary.py`

- [ ] **Step 1: Create the test file**

```python
"""Tests for core.dream_artifacts.write_dream_run_summary (Phase 11-prep-cleanup-a)."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from core import dream_artifacts


def _make_item(idx=1, kind="bug", title="Slow case", status="planned_no_patch",
               hint="", item_dir_name="", summary=""):
    return {"idx": idx, "kind": kind, "title": title, "status": status,
            "hint": hint, "item_dir_name": item_dir_name, "summary": summary}


def test_write_dream_run_summary_creates_md_file(tmp_path):
    """Output file must be dream_run_summary.md — not morning_report.txt."""
    p = dream_artifacts.write_dream_run_summary(tmp_path, [_make_item()])
    assert p.name == "dream_run_summary.md"
    assert (tmp_path / "dream_run_summary.md").is_file()
    assert not (tmp_path / "morning_report.txt").is_file()


def test_dream_run_summary_content_sections(tmp_path):
    """File must contain the required top-level headings."""
    items = [_make_item(status="planned_no_patch")]
    dream_artifacts.write_dream_run_summary(tmp_path, items)
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "# Dream run summary" in text
    assert "## Summary" in text
    assert "## Items" in text
    assert "## Next steps" in text


def test_dream_run_summary_includes_root_cause_from_hint(tmp_path):
    """A non-empty hint must appear under 'suspected root cause'."""
    items = [_make_item(hint="off-by-one in loop condition")]
    dream_artifacts.write_dream_run_summary(tmp_path, items)
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "suspected root cause" in text
    assert "off-by-one in loop condition" in text


def test_dream_run_summary_includes_candidate_lesson_text(tmp_path):
    """lesson_notes kwarg must produce a ## Candidate lessons section."""
    items = [_make_item()]
    dream_artifacts.write_dream_run_summary(
        tmp_path, items, lesson_notes=["always validate loop bounds"]
    )
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "## Candidate lessons" in text
    assert "always validate loop bounds" in text


def test_dream_run_summary_includes_evidence_link(tmp_path):
    """item_dir_name must produce a Markdown link, not a bare backtick string."""
    items = [_make_item(item_dir_name="01-slow-case")]
    dream_artifacts.write_dream_run_summary(tmp_path, items)
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "[01-slow-case/](./01-slow-case/)" in text


def test_dream_run_summary_no_candidate_lessons_section_when_empty(tmp_path):
    """No ## Candidate lessons section when lesson_notes is None or []."""
    dream_artifacts.write_dream_run_summary(tmp_path, [_make_item()])
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "## Candidate lessons" not in text


def test_read_report_falls_back_to_morning_report_txt(tmp_path):
    """Legacy dirs that only have morning_report.txt must still load."""
    (tmp_path / "morning_report.txt").write_text("# Legacy report\n", encoding="utf-8")
    (tmp_path / "list.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    data = dream_artifacts.read_report(tmp_path)
    assert data["morning_report"] == "# Legacy report\n"


def test_read_report_prefers_dream_run_summary_md(tmp_path):
    """When both files exist, dream_run_summary.md takes precedence."""
    (tmp_path / "morning_report.txt").write_text("OLD", encoding="utf-8")
    (tmp_path / "dream_run_summary.md").write_text("NEW", encoding="utf-8")
    (tmp_path / "list.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    data = dream_artifacts.read_report(tmp_path)
    assert data["morning_report"] == "NEW"
```

- [ ] **Step 2: Run tests to verify they FAIL**

```
pytest tests/test_dream_run_summary.py -v
```
Expected: FAILED — `AttributeError: module 'core.dream_artifacts' has no attribute 'write_dream_run_summary'`

---

## Task 2: Implement write_dream_run_summary in core/dream_artifacts.py

**Files:**
- Modify: `core/dream_artifacts.py`

- [ ] **Step 1: Add write_dream_run_summary after the existing write_report_markdown function**

In `core/dream_artifacts.py`, add the new function immediately after the existing `write_report_markdown` definition (around line 1019), then add the compat alias at the end:

```python
def write_dream_run_summary(
    report_dir: Path,
    items: list[dict],
    dream_mode: str | None = None,
    case_ideas: list[dict] | None = None,
    lesson_notes: list[str] | None = None,
) -> Path:
    """Write dream_run_summary.md — richer successor to morning_report.txt.

    All content is derived deterministically from the already-processed items
    and lesson_notes. No LLM calls, no subprocess, no patch execution.
    """
    lines: list[str] = [
        f"# Dream run summary — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Total items: {len(items)}",
    ]
    if dream_mode:
        lines.append(f"Dream mode: `{dream_mode}`")
    lines.append("")

    status_counts: dict[str, int] = {}
    for it in items:
        st = it.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    if status_counts:
        lines.append("## Summary")
        for st, count in sorted(status_counts.items()):
            descr = STATUS_LEGEND.get(st)
            if descr:
                lines.append(f"- **{st}** ({count}) — {descr}")
            else:
                lines.append(f"- **{st}** ({count})")
        lines.append("")

    notes = [str(n).strip() for n in (lesson_notes or []) if str(n or "").strip()]
    if notes:
        lines.append("## Candidate lessons")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    if case_ideas is not None:
        lines.append("## Case idea candidates")
        lines.append("")
        if case_ideas:
            lines.append("| Pattern | Suggested case | Language | Category | Difficulty | Approved? |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for idea in case_ideas:
                approved = "yes" if idea.get("human_approved_for_case_creation") is True else "no"
                lines.append(
                    "| "
                    + " | ".join([
                        _md_cell(idea.get("pattern")),
                        _md_cell(idea.get("suggested_case_name")),
                        _md_cell(idea.get("language")),
                        _md_cell(idea.get("category")),
                        _md_cell(idea.get("difficulty")),
                        approved,
                    ])
                    + " |"
                )
        else:
            lines.append("No case ideas were generated from the provided reference notes.")
        lines.append("")

    lines.append("## Items")
    lines.append("")
    next_steps: list[str] = []
    for it in items:
        idx = it.get("idx", "?")
        kind = it.get("kind", "?")
        title = it.get("title", "?")
        status = it.get("status", "?")
        summary = it.get("summary", "")
        hint = it.get("hint", "")
        item_dir_name = it.get("item_dir_name", "")

        lines.append(f"### {idx}. [{kind}] {title}")
        lines.append(f"- status: **{status}**")
        if summary:
            lines.append(f"- summary: {summary}")
        if hint:
            lines.append(f"- suspected root cause: {hint}")
        if item_dir_name:
            lines.append(f"- evidence: [{item_dir_name}/](./{item_dir_name}/)")

        blockers = it.get("patch_blockers") or []
        if blockers:
            blocker_summary_text = it.get("patch_blocker_summary") or patch_blocker_summary(blockers)
            lines.append(f"- {blocker_summary_text}")
            for blocker in blockers:
                code = blocker.get("code", "unknown")
                message = blocker.get("message", "")
                evidence = blocker.get("evidence", "")
                override_hint = blocker.get("override_hint", "")
                detail = f"  - `{code}`: {message}"
                if evidence:
                    detail += f" ({evidence})"
                lines.append(detail)
                if override_hint:
                    lines.append(f"    - *Override path*: {override_hint}")
                    next_steps.append(f"**{title}** (`{code}`): {override_hint}")
        lines.append("")

    if next_steps:
        lines.append("## Next steps")
        lines.append("")
        for step in next_steps:
            lines.append(f"- {step}")
        lines.append("")

    out_path = report_dir / "dream_run_summary.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# Backward-compat alias — remove once all callers are updated.
write_report_markdown = write_dream_run_summary
```

- [ ] **Step 2: Run tests to verify they pass**

```
pytest tests/test_dream_run_summary.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add core/dream_artifacts.py tests/test_dream_run_summary.py
git commit -m "feat: add write_dream_run_summary with dream_run_summary.md output"
```

---

## Task 3: Update read_report() to prefer dream_run_summary.md

**Files:**
- Modify: `core/dream_artifacts.py` (the `read_report` function around line 204)

- [ ] **Step 1: Replace the morning_report.txt block in read_report()**

Find and replace this block in `read_report()`:

```python
# BEFORE (around line 210-216):
morning_path = report_dir / "morning_report.txt"

morning = ""
if morning_path.exists():
    try:
        morning = morning_path.read_text(encoding="utf-8")
    except Exception:
        morning = ""
```

Replace with:

```python
# Prefer the new .md file; fall back to legacy .txt for pre-rename run dirs.
_summary_path = report_dir / "dream_run_summary.md"
if not _summary_path.exists():
    _summary_path = report_dir / "morning_report.txt"

morning = ""
if _summary_path.exists():
    try:
        morning = _summary_path.read_text(encoding="utf-8")
    except Exception:
        morning = ""
```

- [ ] **Step 2: Run fallback tests**

```
pytest tests/test_dream_run_summary.py::test_read_report_falls_back_to_morning_report_txt tests/test_dream_run_summary.py::test_read_report_prefers_dream_run_summary_md -v
```
Expected: both PASS.

- [ ] **Step 3: Commit**

```bash
git add core/dream_artifacts.py
git commit -m "feat: read_report() prefers dream_run_summary.md, falls back to morning_report.txt"
```

---

## Task 4: Update callers and test fixtures

**Files:**
- Modify: `core/sleeping_consultant.py`
- Modify: `tests/test_dream_report_markdown_rendering.py`
- Check and maybe modify: `tests/test_dream_case_ideas.py`

- [ ] **Step 1: Update sleeping_consultant.py call site**

Find this block in `core/sleeping_consultant.py` (around line 1448):
```python
dream_artifacts.write_report_markdown(
    report_dir,
    results,
    dream_mode=mode,
    case_ideas=case_ideas if case_idea_run else None,
)
```

Replace with:
```python
dream_artifacts.write_dream_run_summary(
    report_dir,
    results,
    dream_mode=mode,
    case_ideas=case_ideas if case_idea_run else None,
    lesson_notes=lesson_notes if case_idea_run else None,
)
```

- [ ] **Step 2: Update test_dream_report_markdown_rendering.py fixture filenames**

Find every occurrence of `"morning_report.txt"` in `tests/test_dream_report_markdown_rendering.py` (two fixtures in `test_dream_report_route_returns_rendered_morning_html` and `test_dream_report_route_html_escapes_injected_markup`) and change to `"dream_run_summary.md"`:

In `test_dream_report_route_returns_rendered_morning_html`:
```python
# BEFORE:
(report_dir / "morning_report.txt").write_text(
    "# Morning report\n\n- one\n- two\n", encoding="utf-8"
)
# AFTER:
(report_dir / "dream_run_summary.md").write_text(
    "# Dream run summary\n\n- one\n- two\n", encoding="utf-8"
)
```

In `test_dream_report_route_html_escapes_injected_markup`:
```python
# BEFORE:
(report_dir / "morning_report.txt").write_text(
    "<script>alert(1)</script>", encoding="utf-8"
)
# AFTER:
(report_dir / "dream_run_summary.md").write_text(
    "<script>alert(1)</script>", encoding="utf-8"
)
```

In `test_dream_report_route_returns_rendered_morning_html`, the assertion:
```python
assert body["morning_report"].startswith("# Morning report")
```
Change to:
```python
assert body["morning_report"].startswith("# Dream run summary")
```

- [ ] **Step 3: Check test_dream_case_ideas.py**

```
grep -n "morning_report" tests/test_dream_case_ideas.py
```

If any assertion checks for `morning_report.txt` filename (not just the function call), update those too. The function call via the compat alias still works, but if the test asserts `path.name == "morning_report.txt"`, change to `"dream_run_summary.md"`.

- [ ] **Step 4: Run the markdown rendering tests**

```
pytest tests/test_dream_report_markdown_rendering.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/sleeping_consultant.py tests/test_dream_report_markdown_rendering.py tests/test_dream_case_ideas.py
git commit -m "feat: update callers + test fixtures for dream_run_summary.md rename"
```

---

## Task 5: Add list_json_raw to /dream/report route

**Files:**
- Modify: `tests/test_dream_report_markdown_rendering.py`
- Modify: `web/app.py`

- [ ] **Step 1: Add failing tests for list_json_raw**

Add to `tests/test_dream_report_markdown_rendering.py`:

```python
def test_dream_report_route_exposes_list_json_raw(client, tmp_path, monkeypatch):
    from core import dream_artifacts

    repo = tmp_path / "repo"
    repo.mkdir()
    dreams = tmp_path / "dreams"
    date = "2026-06-02"
    run = "030405-run"
    report_dir = dreams / date / run
    report_dir.mkdir(parents=True)
    (report_dir / "dream_run_summary.md").write_text("# summary\n", encoding="utf-8")
    list_payload = {"items": [{"idx": 1, "title": "x", "status": "planned_no_patch"}], "dream_mode": "plan_only"}
    (report_dir / "list.json").write_text(json.dumps(list_payload), encoding="utf-8")
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    resp = client.get(f"/dream/report?repo_path={repo}&date={date}&run={run}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "list_json_raw" in body
    assert isinstance(body["list_json_raw"], str)
    parsed = json.loads(body["list_json_raw"])
    assert "items" in parsed
```

- [ ] **Step 2: Run to verify FAIL**

```
pytest tests/test_dream_report_markdown_rendering.py::test_dream_report_route_exposes_list_json_raw -v
```
Expected: FAIL — `list_json_raw` not in response.

- [ ] **Step 3: Add list_json_raw to dream_report_route in web/app.py**

Find `dream_report_route()` (around line 706). After the line:
```python
report["morning_report_html"] = render_dream_report_markdown(
    report.get("morning_report", "")
)
```
Add:
```python
# Phase 11-prep-cleanup-a: expose raw list.json for the modal's collapsed panel.
_list_json_path = report_dir / "list.json"
try:
    report["list_json_raw"] = (
        _list_json_path.read_text(encoding="utf-8") if _list_json_path.is_file() else ""
    )
except Exception:
    report["list_json_raw"] = ""
```

- [ ] **Step 4: Run to verify PASS**

```
pytest tests/test_dream_report_markdown_rendering.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/app.py tests/test_dream_report_markdown_rendering.py
git commit -m "feat: expose list_json_raw in /dream/report response"
```

---

## Task 6: Write failing tests for new routes

**Files:**
- Create: `tests/test_dream_lesson_proposal_routes.py`

- [ ] **Step 1: Create the test file**

```python
"""Tests for POST /dream/create-lesson-candidate and POST /dream/create-proposal."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

import config as app_config


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_run(tmp_path, date="2026-06-02", run="010203-run"):
    """Create a minimal run dir with one item in list.json."""
    from config import get_agent_dir
    import core.dream_artifacts as da

    dreams = tmp_path / "dreams"
    report_dir = dreams / date / run
    report_dir.mkdir(parents=True)
    item_dir_name = "01-slow-case"
    (report_dir / item_dir_name).mkdir()
    items = [{
        "idx": 1,
        "kind": "bug",
        "title": "Slow case: x",
        "hint": "loop is O(n^2)",
        "status": "planned_no_patch",
        "item_dir_name": item_dir_name,
        "case_name": "python_slow",
        "language": "python",
        "category": "performance",
    }]
    (report_dir / "list.json").write_text(
        json.dumps({"items": items}), encoding="utf-8"
    )
    return dreams, report_dir, item_dir_name


def test_create_lesson_candidate_returns_candidate_status(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    dreams, report_dir, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)

    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    resp = client.post("/dream/create-lesson-candidate", data={
        "repo_path": repo,
        "date": "2026-06-02",
        "run": "010203-run",
        "item_idx": "1",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("ok") is True
    assert body.get("status") == "candidate"
    assert body.get("active_knowledge_allowed") is False


def test_create_lesson_candidate_never_auto_promotes(client, tmp_path, monkeypatch):
    """Even if LESSON_AUTO_ACTIVE is True, result must be candidate."""
    import core.dream_artifacts as da
    dreams, report_dir, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)
    monkeypatch.setattr(app_config, "LESSON_AUTO_ACTIVE", True)

    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    resp = client.post("/dream/create-lesson-candidate", data={
        "repo_path": repo,
        "date": "2026-06-02",
        "run": "010203-run",
        "item_idx": "1",
    })
    body = resp.get_json()
    assert body.get("ok") is True
    assert body.get("active_knowledge_allowed") is False
    assert body.get("status") == "candidate"


def test_create_proposal_writes_proposal_md_and_json(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    from scripts.run_patch_proposal_queue import PROPOSAL_ROOT
    dreams, _, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)

    # Redirect proposal root to tmp so the test is hermetic.
    fake_proposal_root = tmp_path / "proposals"
    import web.app as webapp
    monkeypatch.setattr(webapp, "_DREAM_PROPOSAL_ROOT", fake_proposal_root)

    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    resp = client.post("/dream/create-proposal", data={
        "repo_path": repo,
        "date": "2026-06-02",
        "run": "010203-run",
        "item_idx": "1",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("ok") is True
    proposal_dir = Path(body["proposal_dir"])
    assert (proposal_dir / "proposal.md").is_file()
    assert (proposal_dir / "proposal.json").is_file()
    assert (proposal_dir / "item.json").is_file()


def test_create_proposal_no_model_call(client, tmp_path, monkeypatch):
    """proposal.md content must be purely derived from item data — marker phrase present."""
    import core.dream_artifacts as da
    dreams, _, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)
    fake_proposal_root = tmp_path / "proposals"
    import web.app as webapp
    monkeypatch.setattr(webapp, "_DREAM_PROPOSAL_ROOT", fake_proposal_root)

    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    client.post("/dream/create-proposal", data={
        "repo_path": repo,
        "date": "2026-06-02",
        "run": "010203-run",
        "item_idx": "1",
    })
    # Find the written proposal.md
    md_files = list(fake_proposal_root.rglob("proposal.md"))
    assert len(md_files) == 1
    text = md_files[0].read_text(encoding="utf-8")
    assert "human review required" in text.lower()
    assert "Slow case: x" in text  # title from item


def test_create_lesson_candidate_missing_item_idx(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    dreams, _, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)
    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    resp = client.post("/dream/create-lesson-candidate", data={
        "repo_path": repo, "date": "2026-06-02", "run": "010203-run",
    })
    assert resp.status_code == 400
```

- [ ] **Step 2: Run to verify FAIL**

```
pytest tests/test_dream_lesson_proposal_routes.py -v
```
Expected: all FAIL — routes don't exist yet.

---

## Task 7: Add POST /dream/create-lesson-candidate route

**Files:**
- Modify: `web/app.py`

- [ ] **Step 1: Add the route after the existing /dream/promote-artifact route**

Find the end of `dream_promote_artifact_route()` in `web/app.py` and add after it:

```python
@app.route("/dream/create-lesson-candidate", methods=["POST"])
def dream_create_lesson_candidate_route():
    """Create a candidate lesson from any eligible Dream item (not just ready_to_apply).

    For ready_to_apply items, prefer /lessons/create-candidate-from-dream which
    uses the richer lesson_auto_candidates artifact extraction path. This route
    handles all other statuses via a direct lesson_store call.

    Never calls any model, patch executor, validation command, or subprocess.
    Always produces a candidate-bucket lesson with active_knowledge_allowed=False.
    Promotion requires an explicit Promote click in the Memory tab.
    """
    import config as _cfg
    from core import lesson_store as _ls
    from core.dream_artifacts import resolve_run_dir, load_item_for_promotion

    repo_path = request.form.get("repo_path", "").strip() or None
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()
    item_idx_raw = request.form.get("item_idx", "").strip()

    if not item_idx_raw:
        return {"ok": False, "error": "item_idx is required"}, 400
    try:
        item_idx = int(item_idx_raw)
    except ValueError:
        return {"ok": False, "error": "item_idx must be an integer"}, 400

    if not date or not run:
        return {"ok": False, "error": "date and run are required"}, 400

    # Validate date/run format to guard path traversal.
    import re as _re
    if not _re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {"ok": False, "error": "invalid date format"}, 400
    if not _re.match(r"^[\w.-]{1,64}$", run):
        return {"ok": False, "error": "invalid run id format"}, 400

    try:
        report_dir = dream_artifacts.resolve_run_dir(repo_path or "", date, run)
    except (ValueError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 400

    try:
        _list_data, item = load_item_for_promotion(report_dir, item_idx)
    except (LookupError, RuntimeError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 404

    candidate = {
        "title": item.get("title", ""),
        "hint": item.get("hint", ""),
        "kind": item.get("kind", ""),
        "source": "dream",
        "case_name": item.get("case_name") or None,
        "language": item.get("language", ""),
        "category": item.get("category", ""),
        "item_status": item.get("status", ""),
        "dream_ref": f"{date}/{run}/{item.get('item_dir_name', str(item_idx))}",
    }

    # Force LESSON_AUTO_ACTIVE off — candidate must never land in active/.
    _prev = getattr(_cfg, "LESSON_AUTO_ACTIVE", False)
    _cfg.LESSON_AUTO_ACTIVE = False
    try:
        record = _ls.save_candidate_lesson(
            candidate,
            source="dream",
            source_report=f"{date}/{run}",
            case_name=candidate["case_name"],
            title=f"Dream item: {item.get('title', 'untitled')}",
            summary=item.get("hint", ""),
            repo_path=repo_path,
        )
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    finally:
        _cfg.LESSON_AUTO_ACTIVE = _prev

    return {
        "ok": True,
        "lesson_id": record.get("id"),
        "status": record.get("status"),
        "active_knowledge_allowed": record.get("active_knowledge_allowed", False),
        "scope": record.get("scope"),
    }
```

- [ ] **Step 2: Run route tests**

```
pytest tests/test_dream_lesson_proposal_routes.py::test_create_lesson_candidate_returns_candidate_status tests/test_dream_lesson_proposal_routes.py::test_create_lesson_candidate_never_auto_promotes tests/test_dream_lesson_proposal_routes.py::test_create_lesson_candidate_missing_item_idx -v
```
Expected: all PASS.

---

## Task 8: Add POST /dream/create-proposal route

**Files:**
- Modify: `web/app.py`

- [ ] **Step 1: Add module-level _DREAM_PROPOSAL_ROOT constant near the top of web/app.py**

Find where `WEB_DIR` is defined (around line 76) and add after it:

```python
# Phase 11-prep-cleanup-a: proposal root for dream-created proposal drafts.
# Monkeypatched in tests for hermeticity.
from scripts.run_patch_proposal_queue import PROPOSAL_ROOT as _DREAM_PROPOSAL_ROOT
```

- [ ] **Step 2: Add the route after dream_create_lesson_candidate_route**

```python
@app.route("/dream/create-proposal", methods=["POST"])
def dream_create_proposal_route():
    """Write a static proposal draft (proposal.md + proposal.json + item.json)
    to .agent/proposals/dream-<date>-<run>/<item_dir_name>/.

    No model call, no subprocess, no patch execution. The proposal appears in
    Memory → Proposals for human review. It clearly marks itself as a human-
    review-required draft so it is not confused with a validated patch proposal.
    """
    from core.dream_artifacts import resolve_run_dir, load_item_for_promotion

    repo_path = request.form.get("repo_path", "").strip() or None
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()
    item_idx_raw = request.form.get("item_idx", "").strip()

    if not item_idx_raw:
        return {"ok": False, "error": "item_idx is required"}, 400
    try:
        item_idx = int(item_idx_raw)
    except ValueError:
        return {"ok": False, "error": "item_idx must be an integer"}, 400

    import re as _re
    if not date or not _re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {"ok": False, "error": "invalid date format"}, 400
    if not run or not _re.match(r"^[\w.-]{1,64}$", run):
        return {"ok": False, "error": "invalid run id format"}, 400

    try:
        report_dir = dream_artifacts.resolve_run_dir(repo_path or "", date, run)
    except (ValueError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 400

    try:
        _list_data, item = load_item_for_promotion(report_dir, item_idx)
    except (LookupError, RuntimeError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 404

    # Build a safe slug for the proposal dir name.
    item_dir_name = item.get("item_dir_name") or dream_artifacts.slugify(
        f"{item_idx:02d}-{item.get('title', 'item')}"
    )
    run_label = f"dream-{date}-{run}"
    proposal_dir = _DREAM_PROPOSAL_ROOT / run_label / item_dir_name
    try:
        proposal_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"ok": False, "error": f"could not create proposal dir: {e}"}, 500

    now_iso = datetime.now().isoformat(timespec="seconds")
    title = item.get("title", "untitled")
    hint = item.get("hint", "")
    status = item.get("status", "unknown")
    kind = item.get("kind", "?")
    blockers = item.get("patch_blockers") or []

    # proposal.json
    proposal_json = {
        "source": "dream",
        "date": date,
        "run_id": run,
        "item_idx": item_idx,
        "title": title,
        "hint": hint,
        "kind": kind,
        "status": status,
        "patch_blockers": blockers,
        "created_at": now_iso,
        "human_review_required": True,
    }

    # item.json — minimal shape compatible with proposals_list_route
    item_json = {
        "case_name": item.get("case_name") or dream_artifacts.slugify(title),
        "title": title,
        "hint": hint,
        "source": "dream",
        "created_at": now_iso,
    }

    # proposal.md — deterministic Markdown draft
    blocker_lines = []
    for b in blockers:
        code = b.get("code", "unknown")
        msg = b.get("message", "")
        hint_text = b.get("override_hint", "")
        blocker_lines.append(f"- `{code}`: {msg}")
        if hint_text:
            blocker_lines.append(f"  - *Override path*: {hint_text}")

    evidence_link = ""
    if item.get("item_dir_name"):
        evidence_link = f"\n**Evidence:** [{item['item_dir_name']}/](./{item['item_dir_name']}/)\n"

    proposal_md_lines = [
        f"# Proposal draft: {title}",
        "",
        "> **Human review required.** This is a static draft generated from a Dream",
        "> item. It has not been validated, patched, or reviewed by any model.",
        "> Review the content below and decide whether to create a candidate lesson.",
        "",
        f"**Kind:** {kind}  ",
        f"**Status at creation:** {status}  ",
        f"**Created:** {now_iso}",
        f"**Dream run:** {date} / {run}",
        "",
    ]
    if hint:
        proposal_md_lines += [
            "## Suspected root cause",
            "",
            hint,
            "",
        ]
    if blocker_lines:
        proposal_md_lines += [
            "## Why no patch",
            "",
        ] + blocker_lines + [""]
    if evidence_link:
        proposal_md_lines.append(evidence_link)
    proposal_md_lines += [
        "## Next steps",
        "",
        "1. Review this draft.",
        "2. If the root cause is confirmed, click **Create candidate lesson** on the Dream item card.",
        "3. Promote the candidate lesson in the Memory → Lessons tab once it looks correct.",
        "",
    ]

    try:
        (proposal_dir / "proposal.json").write_text(
            json.dumps(proposal_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (proposal_dir / "item.json").write_text(
            json.dumps(item_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (proposal_dir / "proposal.md").write_text(
            "\n".join(proposal_md_lines), encoding="utf-8"
        )
    except OSError as e:
        return {"ok": False, "error": f"write failed: {e}"}, 500

    return {"ok": True, "proposal_dir": str(proposal_dir)}
```

- [ ] **Step 3: Run proposal route tests**

```
pytest tests/test_dream_lesson_proposal_routes.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add web/app.py tests/test_dream_lesson_proposal_routes.py
git commit -m "feat: add /dream/create-lesson-candidate and /dream/create-proposal routes"
```

---

## Task 9: Write tests for template/UI structure changes

**Files:**
- Create: `tests/test_dream_research_controls_collapse.py`
- Create: `tests/test_lesson_filters_client.py`

- [ ] **Step 1: Create test_dream_research_controls_collapse.py**

```python
"""Structural tests for Dream research controls collapse (Phase 11-prep-cleanup-a)."""
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


def test_research_section_has_no_inline_hidden_attribute():
    """The .dream-references-section must start visible — JS hides it, not HTML."""
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    # Find the section start
    idx = tpl.find("dream-references-section")
    assert idx != -1, "dream-references-section not found in template"
    # The div opening tag (up to 200 chars before the class) must not have `hidden`
    snippet = tpl[max(0, idx - 50) : idx + 60]
    assert "hidden" not in snippet


def test_trials_section_is_details_element():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert '<details id="dreamTrialsSection"' in tpl


def test_research_controls_collapse_js_function_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "_updateDreamResearchControlsVisibility" in tpl


def test_research_controls_collapse_targets_bug_investigation():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "bug_investigation" in tpl


def test_dream_taxonomy_route_returns_bug_investigation(client):
    resp = client.get("/dream/taxonomy")
    assert resp.status_code == 200
    data = resp.get_json()
    dream_types = data.get("dream_types") or []
    assert "bug_investigation" in dream_types


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
```

- [ ] **Step 2: Create test_lesson_filters_client.py**

```python
"""Tests for lesson filter UI and data shape (Phase 11-prep-cleanup-a)."""
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


def test_lesson_filter_language_dropdown_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="lessonFilterLanguage"' in tpl


def test_lesson_filter_source_dropdown_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="lessonFilterSource"' in tpl


def test_lesson_filter_category_dropdown_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="lessonFilterCategory"' in tpl


def test_lesson_filter_difficulty_dropdown_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="lessonFilterDifficulty"' in tpl


def test_apply_lesson_filters_function_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "_applyLessonFilters" in tpl


def test_populate_lesson_filter_dropdowns_function_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "_populateLessonFilterDropdowns" in tpl


def test_lesson_card_has_data_lesson_id_attribute():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "data-lesson-id" in tpl


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_lessons_list_route_returns_source_field(client):
    """The /lessons/list response records must include 'source' and 'candidate' keys."""
    resp = client.get("/lessons/list")
    assert resp.status_code == 200
    data = resp.get_json()
    # If there are no lessons this just verifies the route returns ok=True + lessons list.
    assert data.get("ok") is True
    for lesson in data.get("lessons", []):
        assert "source" in lesson
        assert "candidate" in lesson or "tags" in lesson
```

- [ ] **Step 3: Run to verify FAIL**

```
pytest tests/test_dream_research_controls_collapse.py tests/test_lesson_filters_client.py -v
```
Expected: most fail — JS functions and filter dropdowns not in template yet.

---

## Task 10: Update Dream modal — raw panels + research controls collapse

**Files:**
- Modify: `web/templates/index.html`

This task has three sub-changes in the JS section of the template.

### Sub-change A: Add raw collapsed panels to viewDreamRun

- [ ] **Step 1: Find the body template in viewDreamRun**

Search for `<details class="dream-report-summary" open>` in the template JS. It is inside the `.then(data => {` handler of `viewDreamRun`.

Find the current block:
```javascript
        const body = `
            <details class="dream-report-summary" open>
                <summary>Morning report</summary>
                ${morningHtml}
            </details>
            ${_renderCaseIdeaCandidates(caseIdeas)}
```

Replace with:
```javascript
        const rawSummaryPanel = morning.length > 0
            ? `<details class="dream-raw-details"><summary>Raw summary (dream_run_summary.md)</summary><pre class="dream-report-pre">${_escapeHtml(morning)}</pre></details>`
            : "";
        const rawJsonPanel = (typeof data.list_json_raw === "string" && data.list_json_raw.length > 0)
            ? `<details class="dream-raw-details"><summary>Raw list.json</summary><pre class="dream-report-pre">${_escapeHtml(data.list_json_raw)}</pre></details>`
            : "";

        const body = `
            <details class="dream-report-summary" open>
                <summary>Summary</summary>
                ${morningHtml}
            </details>
            ${rawSummaryPanel}
            ${rawJsonPanel}
            ${_renderCaseIdeaCandidates(caseIdeas)}
```

### Sub-change B: Add _updateDreamResearchControlsVisibility

- [ ] **Step 2: Add the function and wire it**

Find `function fetchDreamTaxonomy()` in the template. Add the new function BEFORE it:

```javascript
// Phase 11-prep-cleanup-a: collapse research/reference controls for debug work types.
const _RESEARCH_HEAVY_WORK_TYPES = new Set(["bug_investigation", "debug"]);

function _updateDreamResearchControlsVisibility() {
    const dreamTypeEl = document.getElementById("dreamType");
    const workType = dreamTypeEl ? dreamTypeEl.value : "";
    const referencesSection = document.querySelector(".dream-references-section");
    const trialsSection = document.getElementById("dreamTrialsSection");
    const isResearchHeavy = _RESEARCH_HEAVY_WORK_TYPES.has(workType);
    if (referencesSection) {
        referencesSection.hidden = isResearchHeavy;
    }
    if (trialsSection) {
        if (isResearchHeavy) {
            trialsSection.removeAttribute("open");
        }
    }
}
```

Inside `fetchDreamTaxonomy()`, add `_updateDreamResearchControlsVisibility();` as the last line of the `.then(data => { ... })` block:
```javascript
function fetchDreamTaxonomy() {
    return fetch("/dream/taxonomy")
        .then(r => r.json())
        .then(data => {
            if (data && data.dream_types) {
                _dreamTaxonomy = data;
                _renderDreamTypeOptions(data);
                _renderActionLevelOptions(_dreamType());
                _updateDreamResearchControlsVisibility();  // ← ADD THIS
            }
            return data;
        })
        .catch(err => console.warn("dream taxonomy fetch failed", err));
}
```

Also wire the `change` listener by adding inside the `DOMContentLoaded` block (search for `document.addEventListener("DOMContentLoaded"` or add one if it doesn't exist):
```javascript
document.addEventListener("DOMContentLoaded", function () {
    const dreamTypeEl = document.getElementById("dreamType");
    if (dreamTypeEl) {
        dreamTypeEl.addEventListener("change", _updateDreamResearchControlsVisibility);
    }
});
```

- [ ] **Step 3: Run structural tests**

```
pytest tests/test_dream_research_controls_collapse.py -v
```
Expected: all PASS.

---

## Task 11: Update per-item Dream card buttons

**Files:**
- Modify: `web/templates/index.html`

- [ ] **Step 1: Add createDreamLessonCandidateSimple and createDreamProposal JS functions**

Find the existing `function createDreamLessonCandidate(date, runId, itemDirName)` and add two new functions AFTER it:

```javascript
// Phase 11-prep-cleanup-a: create a candidate lesson from any eligible Dream item
// (non-ready_to_apply path — uses the simple text-based route).
function createDreamLessonCandidateSimple(date, runId, itemIdx) {
    const repoEl = document.querySelector("input[name='repo_path']");
    const repo = repoEl ? repoEl.value.trim() : "";
    if (!repo) { alert("Set a repo path first."); return; }
    const warn = "Create a candidate lesson from this Dream item?\n\nIt will appear in the Lessons list as a CANDIDATE. You still need to click \"Promote\" to move it to active.";
    if (!confirm(warn)) return;

    openAppModal("Dream lesson candidate", `<div class="health-empty">Creating candidate…</div>`);
    fetch("/dream/create-lesson-candidate", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ repo_path: repo, date, run: runId, item_idx: String(itemIdx) }),
    })
        .then(r => r.json())
        .then(data => {
            if (!data.ok) {
                openAppModal("Dream lesson candidate", `<div class="health-empty">Failed: ${_escapeHtml(data.error || "unknown error")}</div>`);
                return;
            }
            const rows = [
                ["status", data.status],
                ["lesson_id", data.lesson_id],
                ["active_knowledge_allowed", String(data.active_knowledge_allowed)],
                ["scope", data.scope],
            ].filter(([, v]) => v !== undefined && v !== null && v !== "")
             .map(([k, v]) => `<tr><th>${_escapeHtml(k)}</th><td><code>${_escapeHtml(String(v))}</code></td></tr>`)
             .join("");
            openAppModal("Dream lesson candidate", `<table class="lesson-result-table">${rows}</table>`);
            if (typeof loadLessons === "function") loadLessons(true);
        })
        .catch(err => openAppModal("Dream lesson candidate", `<div class="health-empty">Network error: ${_escapeHtml(err)}</div>`));
}

// Phase 11-prep-cleanup-a: create a proposal draft from any eligible Dream item.
function createDreamProposal(date, runId, itemIdx) {
    const repoEl = document.querySelector("input[name='repo_path']");
    const repo = repoEl ? repoEl.value.trim() : "";
    if (!repo) { alert("Set a repo path first."); return; }
    const warn = "Create a proposal draft from this Dream item?\n\nThis writes a static proposal.md (no model call). It will appear in Memory → Proposals for review.";
    if (!confirm(warn)) return;

    openAppModal("Dream proposal", `<div class="health-empty">Creating proposal draft…</div>`);
    fetch("/dream/create-proposal", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ repo_path: repo, date, run: runId, item_idx: String(itemIdx) }),
    })
        .then(r => r.json())
        .then(data => {
            if (!data.ok) {
                openAppModal("Dream proposal", `<div class="health-empty">Failed: ${_escapeHtml(data.error || "unknown error")}</div>`);
                return;
            }
            openAppModal("Dream proposal", `<div class="health-empty">✓ Proposal draft written to <code>${_escapeHtml(data.proposal_dir || "")}</code>. Reload Memory → Proposals to see it.</div>`);
        })
        .catch(err => openAppModal("Dream proposal", `<div class="health-empty">Network error: ${_escapeHtml(err)}</div>`));
}
```

- [ ] **Step 2: Update _renderDreamItemCard eligibility and buttons**

Find this block in `_renderDreamItemCard`:
```javascript
    const canLessonize = status === "ready_to_apply" && !!opts.runId && !!it.item_dir_name;
    const lessonizeBtn = canLessonize
        ? `<button type="button" class="dream-action-btn" onclick="createDreamLessonCandidate('${_escapeHtml(opts.date || "")}', '${_escapeHtml(opts.runId)}', '${_escapeHtml(it.item_dir_name)}')" title="Create a repo-scoped lesson candidate from this validated Dream item. It still needs Promote in the Memory tab before retrieval can use it.">Create candidate lesson</button>`
        : "";
    const dreamActionButtons = [promoteBtn, lessonizeBtn].filter(Boolean).join("");
```

Replace with:
```javascript
    // Eligible: any non-error, non-skipped item with a known item_dir_name and a run context.
    const _skippedOrError = status === "error" || status.startsWith("skipped_");
    const canAction = !!opts.runId && !!it.item_dir_name && !_skippedOrError;

    // ready_to_apply uses the richer lesson_auto_candidates path (existing function).
    // All other eligible statuses use the simple text-based route.
    const lessonizeBtn = canAction
        ? (status === "ready_to_apply"
            ? `<button type="button" class="dream-action-btn" onclick="createDreamLessonCandidate('${_escapeHtml(opts.date || "")}', '${_escapeHtml(opts.runId)}', '${_escapeHtml(it.item_dir_name)}')" title="Create a repo-scoped lesson candidate from this validated Dream item. It still needs Promote in the Memory tab before retrieval can use it.">Create candidate lesson</button>`
            : `<button type="button" class="dream-action-btn" onclick="createDreamLessonCandidateSimple('${_escapeHtml(opts.date || "")}', '${_escapeHtml(opts.runId)}', ${Number(it.idx)})" title="Create a candidate lesson from this Dream item. It still needs Promote in the Memory tab before retrieval can use it.">Create candidate lesson</button>`)
        : "";
    const proposalBtn = canAction
        ? `<button type="button" class="dream-action-btn" onclick="createDreamProposal('${_escapeHtml(opts.date || "")}', '${_escapeHtml(opts.runId)}', ${Number(it.idx)})" title="Write a proposal draft (no model call). Appears in Memory → Proposals.">Create proposal</button>`
        : "";
    const dreamActionButtons = [promoteBtn, lessonizeBtn, proposalBtn].filter(Boolean).join("");
```

---

## Task 12: Add lesson filter UI and JS

**Files:**
- Modify: `web/templates/index.html`

### Sub-change A: HTML — add filter dropdowns

- [ ] **Step 1: Extend the .lessons-filters div in the HTML section**

Find the `.lessons-filters` div (around line 875):
```html
            <div class="lessons-filters" role="group" aria-label="Lesson status filter">
              <button type="button" class="lessons-filter lessons-filter--active"
                      data-status="" onclick="filterLessons('')">All</button>
              <button type="button" class="lessons-filter"
                      data-status="candidate" onclick="filterLessons('candidate')">Candidate</button>
              <button type="button" class="lessons-filter"
                      data-status="active" onclick="filterLessons('active')">Active</button>
              <button type="button" class="lessons-filter"
                      data-status="blocked" onclick="filterLessons('blocked')">Blocked</button>
            </div>
```

Replace with:
```html
            <div class="lessons-filters" role="group" aria-label="Lesson filter">
              <button type="button" class="lessons-filter lessons-filter--active"
                      data-status="" onclick="filterLessons('')">All</button>
              <button type="button" class="lessons-filter"
                      data-status="candidate" onclick="filterLessons('candidate')">Candidate</button>
              <button type="button" class="lessons-filter"
                      data-status="active" onclick="filterLessons('active')">Active</button>
              <button type="button" class="lessons-filter"
                      data-status="blocked" onclick="filterLessons('blocked')">Blocked</button>
              <span class="lessons-filter-sep" aria-hidden="true">|</span>
              <select id="lessonFilterLanguage" class="lessons-filter-select"
                      onchange="_applyLessonFilters()" title="Filter by language">
                <option value="">All languages</option>
              </select>
              <select id="lessonFilterSource" class="lessons-filter-select"
                      onchange="_applyLessonFilters()" title="Filter by source">
                <option value="">All sources</option>
              </select>
              <select id="lessonFilterCategory" class="lessons-filter-select"
                      onchange="_applyLessonFilters()" title="Filter by category">
                <option value="">All categories</option>
              </select>
              <select id="lessonFilterDifficulty" class="lessons-filter-select"
                      onchange="_applyLessonFilters()" title="Filter by difficulty"
                      style="display:none">
                <option value="">All difficulties</option>
              </select>
            </div>
```

### Sub-change B: JS — add filter logic and update _renderLessonsList + _renderLessonCard

- [ ] **Step 2: Add module-level vars and helper functions before _renderLessonsList**

Find `let _lessonsLoaded = false;` in the JS section. Change:
```javascript
let _lessonsLoaded = false;
let _lessonsCurrentStatus = "";
```
To:
```javascript
let _lessonsLoaded = false;
let _lessonsCurrentStatus = "";
let _lessonsData = [];  // Phase 11-prep-cleanup-a: cached for client-side filters
const _KNOWN_LESSON_LANGUAGES = new Set([
    "python", "go", "javascript", "typescript", "rust", "cpp", "java",
    "html", "ruby", "kotlin", "swift", "c", "bash", "sql"
]);

function _lessonLanguage(lesson) {
    const lang = lesson.candidate && lesson.candidate.language;
    if (typeof lang === "string" && lang.trim()) return lang.trim().toLowerCase();
    const tags = Array.isArray(lesson.tags) ? lesson.tags : [];
    return tags.find(t => _KNOWN_LESSON_LANGUAGES.has(String(t).toLowerCase())) || "";
}

function _lessonCategory(lesson) {
    const cat = lesson.candidate && lesson.candidate.category;
    if (typeof cat === "string" && cat.trim()) return cat.trim().toLowerCase();
    const tags = Array.isArray(lesson.tags) ? lesson.tags : [];
    const lang = _lessonLanguage(lesson);
    const idx = tags.findIndex(t => String(t).toLowerCase() === lang);
    return (idx >= 0 && idx + 1 < tags.length) ? String(tags[idx + 1]).toLowerCase() : "";
}

function _lessonDifficulty(lesson) {
    const diff = lesson.candidate && lesson.candidate.difficulty;
    return (typeof diff === "string" && diff.trim()) ? diff.trim().toLowerCase() : "";
}

function _populateLessonFilterDropdowns(lessons) {
    const langs = new Set(), sources = new Set(), cats = new Set(), diffs = new Set();
    for (const l of lessons) {
        const lang = _lessonLanguage(l); if (lang) langs.add(lang);
        const src = typeof l.source === "string" ? l.source : ""; if (src) sources.add(src);
        const cat = _lessonCategory(l); if (cat) cats.add(cat);
        const diff = _lessonDifficulty(l); if (diff) diffs.add(diff);
    }
    function fillSelect(id, values, label) {
        const el = document.getElementById(id);
        if (!el) return;
        const current = el.value;
        el.innerHTML = `<option value="">All ${label}</option>`;
        for (const v of [...values].sort()) {
            const opt = document.createElement("option");
            opt.value = v; opt.textContent = v;
            if (v === current) opt.selected = true;
            el.appendChild(opt);
        }
    }
    fillSelect("lessonFilterLanguage", langs, "languages");
    fillSelect("lessonFilterSource", sources, "sources");
    fillSelect("lessonFilterCategory", cats, "categories");
    fillSelect("lessonFilterDifficulty", diffs, "difficulties");
    const diffEl = document.getElementById("lessonFilterDifficulty");
    if (diffEl) diffEl.style.display = diffs.size ? "" : "none";
}

function _applyLessonFilters() {
    const lang = (document.getElementById("lessonFilterLanguage") || {}).value || "";
    const src  = (document.getElementById("lessonFilterSource")   || {}).value || "";
    const cat  = (document.getElementById("lessonFilterCategory") || {}).value || "";
    const diff = (document.getElementById("lessonFilterDifficulty") || {}).value || "";

    document.querySelectorAll("#lessonsList .lesson-card").forEach(card => {
        const lessonId = card.dataset.lessonId;
        const lesson = _lessonsData.find(l => l.id === lessonId);
        if (!lesson) { card.hidden = false; return; }
        let show = true;
        if (lang && _lessonLanguage(lesson) !== lang) show = false;
        if (src  && (lesson.source || "") !== src)    show = false;
        if (cat  && _lessonCategory(lesson) !== cat)  show = false;
        if (diff && _lessonDifficulty(lesson) !== diff) show = false;
        card.hidden = !show;
    });
}
```

- [ ] **Step 3: Update _renderLessonsList to cache data and call populate + apply**

Find:
```javascript
function _renderLessonsList(lessons) {
    const listEl = document.getElementById("lessonsList");
    if (!listEl) return;
    if (!lessons.length) {
        listEl.innerHTML = '<div class="health-empty">No lessons in this view.</div>';
        return;
    }
    listEl.innerHTML = lessons.map(_renderLessonCard).join("");
}
```

Replace with:
```javascript
function _renderLessonsList(lessons) {
    _lessonsData = lessons;
    const listEl = document.getElementById("lessonsList");
    if (!listEl) return;
    if (!lessons.length) {
        listEl.innerHTML = '<div class="health-empty">No lessons in this view.</div>';
        return;
    }
    listEl.innerHTML = lessons.map(_renderLessonCard).join("");
    _populateLessonFilterDropdowns(lessons);
    _applyLessonFilters();
}
```

- [ ] **Step 4: Add data-lesson-id to the lesson card div in _renderLessonCard**

Find the return statement in `_renderLessonCard`:
```javascript
    return `
      <div class="lesson-card lesson-card--${_escapeHtml(status)}">
```

Replace with:
```javascript
    return `
      <div class="lesson-card lesson-card--${_escapeHtml(status)}" data-lesson-id="${idAttr}">
```

- [ ] **Step 5: Run filter tests**

```
pytest tests/test_lesson_filters_client.py -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add web/templates/index.html tests/test_dream_research_controls_collapse.py tests/test_lesson_filters_client.py
git commit -m "feat: add Dream modal raw panels, research controls collapse, lesson filters, per-item buttons"
```

---

## Task 13: Full validation

- [ ] **Step 1: Compile check**

```
python -m compileall core web tests -q
```
Expected: no output (zero errors).

- [ ] **Step 2: Run focused test files**

```
pytest tests/test_dream_run_summary.py tests/test_dream_report_markdown_rendering.py tests/test_dream_lesson_proposal_routes.py tests/test_dream_research_controls_collapse.py tests/test_lesson_filters_client.py -v
```
Expected: all PASS.

- [ ] **Step 3: Run full test suite**

```
pytest -x -q
```
Expected: all PASS, no regressions.

- [ ] **Step 4: Benchmark check**

```
python benchmarks/run_benchmarks.py --check
```
Expected: 50 checked, 0 errors. (Confirms no patch/scoring/model behavior changed.)

- [ ] **Step 5: Final commit**

```bash
git add -u
git commit -m "Phase 11-prep-cleanup-a: Dream Report + Lesson Review UX complete"
```

---

## Self-review against spec

| Spec requirement | Task(s) |
|---|---|
| Rename `write_report_markdown` → `write_dream_run_summary` | Task 2, 4 |
| Output `dream_run_summary.md` | Task 2 |
| Content: run title/time, queued items, failure summary | Task 2 |
| Content: suspected root cause (from hint) | Task 2 |
| Content: planned action / why no patch (blockers + override_hint) | Task 2 |
| Content: candidate lesson text (from lesson_notes) | Task 2 |
| Content: evidence file links (from item_dir_name) | Task 2 |
| Content: next user actions (from override_hint) | Task 2 |
| `read_report()` fallback to legacy `morning_report.txt` | Task 3 |
| `/dream/report` exposes `list_json_raw` | Task 5 |
| Dream modal: rendered HTML open by default | Task 10 |
| Dream modal: raw summary collapsed | Task 10 |
| Dream modal: raw JSON collapsed | Task 10 |
| Research controls hidden for bug_investigation/debug | Task 10 |
| `data-ui-group` anchors preserved | Task 10 (no changes to existing attrs) |
| `POST /dream/create-lesson-candidate` | Task 7 |
| `POST /dream/create-proposal` | Task 8 |
| Candidate always `active_knowledge_allowed=False` | Task 7 |
| Proposal is static, human review required | Task 8 |
| Per-item buttons on all eligible statuses | Task 11 |
| Lesson filter: language | Task 12 |
| Lesson filter: source | Task 12 |
| Lesson filter: category | Task 12 |
| Lesson filter: difficulty | Task 12 |
| Lesson filter: status (existing, now unified via `_applyLessonFilters`) | Task 12 |
| Tests: Markdown file generated | Task 1, 2 |
| Tests: raw JSON remains available | Task 5, 6 |
| Tests: no auto-promotion | Task 6, 7 |
| Tests: lesson filters | Task 9, 12 |
| Tests: debug Dream UI collapse | Task 9, 10 |
| No patch/validation/benchmark/model/API behavior changed | Task 13 |
| `morning_report.txt` never written by new code | Enforced in Task 2 (`write_dream_run_summary` only writes `.md`) |
