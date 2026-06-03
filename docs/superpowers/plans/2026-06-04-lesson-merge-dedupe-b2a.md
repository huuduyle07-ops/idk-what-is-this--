# Lesson Merge/Dedupe — Phase b2a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add duplicate detection, safe merge, and archive operations for lessons — backend only, no UI changes.

**Architecture:** Three new pure-Python modules (`lesson_duplicates`, `lesson_merge`) plus three new helpers in `lesson_store`. Four new routes in `web/app.py`. All storage stays file-based in the existing bucket layout; `archived`/`superseded_by` are JSON metadata flags, not new filesystem buckets.

**Tech Stack:** Python 3.13, pytest, Flask test client. No model calls anywhere in this feature.

**Design doc:** `docs/superpowers/designs/2026-06-04-lesson-merge-dedupe-design.md`

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `core/lesson_store.py` | Add `get_lesson_by_id`, `patch_lesson_fields`, `save_raw_lesson_record` helpers; add 7 new fields to `save_candidate_lesson` record |
| Modify | `tests/test_lesson_store.py` | Add tests for new helpers; update field-count test from 16 → 23 keys |
| Create | `core/lesson_duplicates.py` | Pure-Python duplicate group detection over a lesson list |
| Create | `tests/test_lesson_duplicates.py` | Tests for all five hint signals |
| Create | `core/lesson_merge.py` | `preview_merge`, `create_merge`, `archive_lesson` |
| Create | `tests/test_lesson_merge.py` | Tests for preview + create (no-write guarantee, guard errors, evidence preservation) |
| Create | `tests/test_lesson_archive.py` | Tests for archive (candidate OK, blocked OK, active → error) |
| Modify | `web/app.py` | Import `lesson_merge`, `lesson_duplicates`; add 4 new routes |
| Create | `tests/test_lesson_merge_routes.py` | HTTP-level tests for the 4 new routes |

---

## Task 1 — lesson_store.py: new helpers + new fields

**Files:**
- Modify: `core/lesson_store.py`
- Modify: `tests/test_lesson_store.py`

- [ ] **Step 1: Write failing tests for the three new helpers and the new fields**

Add to the bottom of `tests/test_lesson_store.py`:

```python
# ── new helpers ──────────────────────────────────────────────────────────────

def test_get_lesson_by_id_returns_normalized_record(lessons_repo):
    saved = lesson_store.save_candidate_lesson(_valid_candidate())
    record = lesson_store.get_lesson_by_id(saved["id"])
    assert record["id"] == saved["id"]
    assert record["status"] == "candidate"


def test_get_lesson_by_id_raises_for_unknown(lessons_repo):
    with pytest.raises(LookupError):
        lesson_store.get_lesson_by_id("20240101_000000_000000")


def test_patch_lesson_fields_updates_in_place(lessons_repo):
    saved = lesson_store.save_candidate_lesson(_valid_candidate())
    updated = lesson_store.patch_lesson_fields(
        saved["id"], {"superseded_by": "20240101_000000_000001"}
    )
    assert updated["superseded_by"] == "20240101_000000_000001"
    # File must still be in the candidate bucket, not moved
    bucket = _bucket_dir(lessons_repo, "candidate") / f"{saved['id']}.json"
    assert bucket.is_file()


def test_patch_lesson_fields_rejects_status_and_id(lessons_repo):
    saved = lesson_store.save_candidate_lesson(_valid_candidate())
    with pytest.raises(ValueError):
        lesson_store.patch_lesson_fields(saved["id"], {"status": "active"})
    with pytest.raises(ValueError):
        lesson_store.patch_lesson_fields(saved["id"], {"id": "other"})


def test_patch_lesson_fields_raises_for_unknown(lessons_repo):
    with pytest.raises(LookupError):
        lesson_store.patch_lesson_fields(
            "20240101_000000_000000", {"archived": True}
        )


def test_save_raw_lesson_record_writes_to_candidate_bucket(lessons_repo):
    record = {
        "id": "20240101_000000_000001",
        "status": "candidate",
        "scope": "global",
        "repo_scope_id": None,
        "title": "raw",
        "summary": "",
        "tags": [],
    }
    lesson_store.save_raw_lesson_record(record)
    bucket = _bucket_dir(lessons_repo, "candidate") / "20240101_000000_000001.json"
    assert bucket.is_file()


def test_save_raw_lesson_record_rejects_non_candidate(lessons_repo):
    record = {
        "id": "20240101_000000_000001",
        "status": "active",
        "scope": "global",
        "repo_scope_id": None,
    }
    with pytest.raises(ValueError):
        lesson_store.save_raw_lesson_record(record)


# ── new fields on save_candidate_lesson ──────────────────────────────────────

def test_save_candidate_lesson_includes_new_fields(lessons_repo):
    saved = lesson_store.save_candidate_lesson(_valid_candidate())
    assert saved["kind"] == "lesson"
    assert saved["archived"] is False
    assert saved["superseded_by"] is None
    assert saved["supersedes"] == []
    assert saved["merge_sources"] == []
    assert saved["merge_sources_data"] == []
    assert saved["duplicate_of"] is None
```

Also update the existing `test_lesson_record_has_all_13_fields` test — find the `expected_keys` set and replace it:

```python
    expected_keys = {
        "id", "status", "scope", "repo_scope_id", "repo_path_hint",
        "created_at", "updated_at", "source", "source_report", "case_name",
        "title", "summary", "tags", "candidate", "evaluation",
        "active_knowledge_allowed",
        # Phase b2 additions
        "kind", "archived", "superseded_by", "supersedes",
        "merge_sources", "merge_sources_data", "duplicate_of",
    }
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_lesson_store.py -k "get_lesson_by_id or patch_lesson_fields or save_raw or new_fields or all_13" -v
```

Expected: multiple `FAILED` / `AttributeError: module 'core.lesson_store' has no attribute 'get_lesson_by_id'`

- [ ] **Step 3: Add the three new helpers to `core/lesson_store.py`**

Add after the existing `block_lesson` function (end of file):

```python
def get_lesson_by_id(
    lesson_id: str,
    repo_path: str | None = None,
    *,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Return a normalized lesson record by ID. Raises LookupError if not found."""
    _validate_lesson_id(lesson_id)
    lessons_root = _lessons_root(repo_path)
    found = _find_lesson_for_operation(
        lessons_root,
        lesson_id,
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    if found is None:
        raise LookupError(f"lesson not found: {lesson_id}")
    _, _, _, _, _, record = found
    return record


def patch_lesson_fields(
    lesson_id: str,
    fields: dict,
    repo_path: str | None = None,
    *,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Update fields on an existing lesson record in-place (atomic).

    The file stays in its current bucket. Cannot change 'id' or 'status'.
    """
    _forbidden = {"id", "status"}
    bad = _forbidden & set(fields)
    if bad:
        raise ValueError(f"patch_lesson_fields: cannot change {bad!r}")

    _validate_lesson_id(lesson_id)
    lessons_root = _lessons_root(repo_path)
    found = _find_lesson_for_operation(
        lessons_root,
        lesson_id,
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    if found is None:
        raise LookupError(f"lesson not found: {lesson_id}")

    path, current_status, scope_name, resolved_repo_scope_id, repo_path_hint, record = found
    record.update(fields)
    record["updated_at"] = _now_iso()
    _atomic_write_json(path, record)
    return _normalize_record(
        record,
        bucket_status=current_status,
        scope=scope_name,
        repo_scope_id=resolved_repo_scope_id,
        repo_path_hint=repo_path_hint,
    )


def save_raw_lesson_record(
    record: dict,
    *,
    repo_path: str | None = None,
) -> dict:
    """Write a pre-built lesson record directly to the candidate bucket (atomic).

    The record must already have a valid 'id' and status='candidate'.
    Used by lesson_merge.create_merge() to write merged records.
    """
    lesson_id = record.get("id")
    _validate_lesson_id(lesson_id)
    if record.get("status") != STATUS_CANDIDATE:
        raise ValueError("save_raw_lesson_record: status must be 'candidate'")
    scope_name = record.get("scope", SCOPE_GLOBAL)
    resolved_repo_scope_id = record.get("repo_scope_id")
    lessons_root = _lessons_root(repo_path)
    scope_root = _scope_root(lessons_root, scope_name, resolved_repo_scope_id)
    path = _lesson_path(scope_root, STATUS_CANDIDATE, lesson_id)
    _atomic_write_json(path, record)
    return record
```

- [ ] **Step 4: Add 7 new fields to the `record` dict in `save_candidate_lesson`**

Find the `record = {` block in `save_candidate_lesson` (around line 539). After the `"active_knowledge_allowed"` line, add:

```python
        "kind": "lesson",
        "archived": False,
        "superseded_by": None,
        "supersedes": [],
        "merge_sources": [],
        "merge_sources_data": [],
        "duplicate_of": None,
```

- [ ] **Step 5: Run tests — all must pass**

```
pytest tests/test_lesson_store.py -v
```

Expected: all tests pass (previously 23 tests + the new 8 = 31 total)

- [ ] **Step 6: Commit**

```
git add core/lesson_store.py tests/test_lesson_store.py
git commit -m "feat: add get_lesson_by_id/patch_lesson_fields/save_raw helpers + 7 new lesson fields"
```

---

## Task 2 — core/lesson_duplicates.py

**Files:**
- Create: `tests/test_lesson_duplicates.py`
- Create: `core/lesson_duplicates.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lesson_duplicates.py`:

```python
import pytest
from core.lesson_duplicates import find_duplicate_groups


def _lesson(id, **kwargs):
    return {
        "id": id,
        "title": "Generic lesson",
        "summary": "",
        "tags": [],
        "candidate": {},
        "source_report": None,
        "case_name": None,
        **kwargs,
    }


# ── Signal 1: source_key ─────────────────────────────────────────────────────

def test_source_key_groups_same_report_and_case():
    a = _lesson("A", source_report="report_1.json", case_name="off_by_one")
    b = _lesson("B", source_report="report_1.json", case_name="off_by_one")
    groups = find_duplicate_groups([a, b])
    assert len(groups) == 1
    assert set(groups[0]["lesson_ids"]) == {"A", "B"}
    assert any("source_report" in r for r in groups[0]["hint_reasons"])


def test_source_key_different_case_name_not_grouped():
    a = _lesson("A", source_report="report_1.json", case_name="case_x")
    b = _lesson("B", source_report="report_1.json", case_name="case_y")
    assert find_duplicate_groups([a, b]) == []


def test_source_key_null_report_not_grouped():
    a = _lesson("A", source_report=None, case_name="case_x")
    b = _lesson("B", source_report=None, case_name="case_x")
    # null source_report must not match
    groups = find_duplicate_groups([a, b])
    # may still group via other signals if title is same — use distinct titles
    a["title"] = "Unique A"
    b["title"] = "Unique B"
    assert find_duplicate_groups([a, b]) == []


# ── Signal 2: title_match ────────────────────────────────────────────────────

def test_title_match_groups_same_normalized_title():
    a = _lesson("A", title="Fix: off-by-one error!")
    b = _lesson("B", title="Fix  off-by-one error ")
    groups = find_duplicate_groups([a, b])
    assert len(groups) == 1
    assert any("title" in r for r in groups[0]["hint_reasons"])


def test_title_match_different_titles_not_grouped():
    a = _lesson("A", title="Python list slicing bug")
    b = _lesson("B", title="Go channel deadlock fix")
    assert find_duplicate_groups([a, b]) == []


# ── Signal 3: tag_overlap ────────────────────────────────────────────────────

def test_tag_overlap_groups_same_lang_category_and_two_tags():
    a = _lesson(
        "A",
        tags=["python", "loops", "off-by-one"],
        candidate={"language": "python", "category": "loops"},
    )
    b = _lesson(
        "B",
        tags=["python", "loops", "boundary"],
        candidate={"language": "python", "category": "loops"},
    )
    groups = find_duplicate_groups([a, b])
    assert len(groups) == 1
    assert any("language" in r or "tag" in r for r in groups[0]["hint_reasons"])


def test_tag_overlap_only_one_shared_tag_not_grouped():
    a = _lesson(
        "A",
        title="Tag overlap test A",
        tags=["python", "loops"],
        candidate={"language": "python", "category": "loops"},
    )
    b = _lesson(
        "B",
        title="Tag overlap test B",
        tags=["python", "strings"],
        candidate={"language": "python", "category": "loops"},
    )
    assert find_duplicate_groups([a, b]) == []


def test_tag_overlap_different_language_not_grouped():
    a = _lesson(
        "A",
        title="Tag diff lang A",
        tags=["python", "loops", "bounds"],
        candidate={"language": "python", "category": "loops"},
    )
    b = _lesson(
        "B",
        title="Tag diff lang B",
        tags=["go", "loops", "bounds"],
        candidate={"language": "go", "category": "loops"},
    )
    assert find_duplicate_groups([a, b]) == []


# ── Signal 4: summary_token_overlap ─────────────────────────────────────────

def test_summary_jaccard_groups_high_overlap():
    text = "always check the boundary condition when iterating over a list in python"
    a = _lesson("A", title="Jaccard A", summary=text)
    b = _lesson("B", title="Jaccard B", summary=text)
    groups = find_duplicate_groups([a, b])
    assert len(groups) == 1
    assert any("Jaccard" in r or "summary" in r for r in groups[0]["hint_reasons"])


def test_summary_jaccard_low_overlap_not_grouped():
    a = _lesson("A", title="Low Jaccard A", summary="python list boundary check")
    b = _lesson("B", title="Low Jaccard B", summary="go goroutine channel synchronization deadlock")
    assert find_duplicate_groups([a, b]) == []


# ── Signal 5: same case, different run ──────────────────────────────────────

def test_same_case_different_run_groups():
    a = _lesson("A", case_name="my_case", source_report="run_1.json")
    b = _lesson("B", case_name="my_case", source_report="run_2.json")
    groups = find_duplicate_groups([a, b])
    assert len(groups) == 1
    assert any("run" in r or "case" in r for r in groups[0]["hint_reasons"])


def test_same_case_same_run_groups_via_source_key():
    a = _lesson("A", case_name="my_case", source_report="run_1.json")
    b = _lesson("B", case_name="my_case", source_report="run_1.json")
    groups = find_duplicate_groups([a, b])
    assert len(groups) == 1


# ── Multi-lesson grouping ────────────────────────────────────────────────────

def test_single_lesson_no_groups():
    assert find_duplicate_groups([_lesson("A")]) == []


def test_empty_list_no_groups():
    assert find_duplicate_groups([]) == []


def test_unrelated_third_lesson_stays_separate():
    a = _lesson("A", source_report="r1", case_name="case")
    b = _lesson("B", source_report="r1", case_name="case")
    c = _lesson("C", title="Completely unrelated Go goroutine", summary="channel close before read")
    groups = find_duplicate_groups([a, b, c])
    assert len(groups) == 1
    assert set(groups[0]["lesson_ids"]) == {"A", "B"}


def test_hint_reasons_list_is_non_empty_for_each_group():
    a = _lesson("A", source_report="r1", case_name="case")
    b = _lesson("B", source_report="r1", case_name="case")
    groups = find_duplicate_groups([a, b])
    assert all(len(g["hint_reasons"]) > 0 for g in groups)
```

- [ ] **Step 2: Run to confirm they fail**

```
pytest tests/test_lesson_duplicates.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.lesson_duplicates'`

- [ ] **Step 3: Write `core/lesson_duplicates.py`**

```python
"""Deterministic duplicate-hint detection for lesson records.

No model calls. Takes an already-loaded list[dict] and returns groups of
likely-duplicate lessons based on five pure-Python signals.
"""
from __future__ import annotations

import re
from collections import defaultdict


_TITLE_NORM_RE = re.compile(r"[^\w\s]")
_JACCARD_THRESHOLD = 0.5
_MIN_SHARED_TAGS = 2


def _normalize_title(title: str) -> str:
    return _TITLE_NORM_RE.sub("", title.lower()).strip()


def _jaccard(a: str, b: str) -> float:
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _duplicate_hints(a: dict, b: dict) -> list[str]:
    """Return hint reason strings if a and b are likely duplicates, else []."""
    reasons: list[str] = []

    sr_a = a.get("source_report")
    sr_b = b.get("source_report")
    cn_a = a.get("case_name")
    cn_b = b.get("case_name")

    # Signal 1: same source_report + case_name
    if sr_a and sr_b and cn_a and cn_b and sr_a == sr_b and cn_a == cn_b:
        reasons.append(
            f"same source_report ({sr_a!r}) and case_name ({cn_a!r})"
        )

    # Signal 2: same normalized title
    t_a = _normalize_title(a.get("title") or "")
    t_b = _normalize_title(b.get("title") or "")
    if t_a and t_b and t_a == t_b:
        reasons.append(f"same normalized title: {t_a!r}")

    # Signal 3: same language + category + >=2 shared tags
    cand_a = a.get("candidate") or {}
    cand_b = b.get("candidate") or {}
    lang_a = (cand_a.get("language") or "").lower().strip()
    lang_b = (cand_b.get("language") or "").lower().strip()
    cat_a = (cand_a.get("category") or "").lower().strip()
    cat_b = (cand_b.get("category") or "").lower().strip()
    tags_a = set(a.get("tags") or [])
    tags_b = set(b.get("tags") or [])
    shared = tags_a & tags_b
    if (
        lang_a and lang_a == lang_b
        and cat_a and cat_a == cat_b
        and len(shared) >= _MIN_SHARED_TAGS
    ):
        reasons.append(
            f"same language ({lang_a!r}) + category ({cat_a!r}) "
            f"with {len(shared)} shared tags: {sorted(shared)}"
        )

    # Signal 4: summary token Jaccard >= threshold
    sum_a = a.get("summary") or ""
    sum_b = b.get("summary") or ""
    if sum_a and sum_b and _jaccard(sum_a, sum_b) >= _JACCARD_THRESHOLD:
        reasons.append(f"summary token Jaccard >= {_JACCARD_THRESHOLD}")

    # Signal 5: same case_name, different source_report (different runs)
    if cn_a and cn_b and cn_a == cn_b and sr_a and sr_b and sr_a != sr_b:
        reasons.append(
            f"same case_name ({cn_a!r}) from different runs"
        )

    return reasons


def find_duplicate_groups(
    lessons: list[dict],
    *,
    min_group_size: int = 2,
) -> list[dict]:
    """Return groups of lessons sharing at least one duplicate hint signal.

    Each group: {"lesson_ids": [...], "hint_reasons": [...]}
    """
    n = len(lessons)
    parent = list(range(n))
    edge_reasons: dict[tuple[int, int], list[str]] = {}

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(x: int, y: int) -> None:
        rx, ry = _find(x), _find(y)
        if rx != ry:
            parent[ry] = rx

    for i in range(n):
        for j in range(i + 1, n):
            hints = _duplicate_hints(lessons[i], lessons[j])
            if hints:
                edge_reasons[(i, j)] = hints
                _union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[_find(i)].append(i)

    result = []
    for members in groups.values():
        if len(members) < min_group_size:
            continue
        seen: set[str] = set()
        all_reasons: list[str] = []
        for ai in members:
            for bi in members:
                if ai >= bi:
                    continue
                for r in edge_reasons.get((ai, bi), []):
                    if r not in seen:
                        seen.add(r)
                        all_reasons.append(r)
        ids = [lessons[k]["id"] for k in members if lessons[k].get("id")]
        result.append({"lesson_ids": ids, "hint_reasons": all_reasons})

    return result
```

- [ ] **Step 4: Run tests — all must pass**

```
pytest tests/test_lesson_duplicates.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```
git add core/lesson_duplicates.py tests/test_lesson_duplicates.py
git commit -m "feat: add lesson_duplicates module with 5-signal duplicate detection"
```

---

## Task 3 — core/lesson_merge.py: preview_merge + archive_lesson

**Files:**
- Create: `tests/test_lesson_merge.py` (preview tests only for now)
- Create: `tests/test_lesson_archive.py`
- Create: `core/lesson_merge.py` (preview_merge + archive_lesson; create_merge added in Task 4)

- [ ] **Step 1: Write failing tests for `preview_merge`**

Create `tests/test_lesson_merge.py`:

```python
import pytest
from core import lesson_merge, lesson_store


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(
        lesson_store, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent"
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    return tmp_path


def _saved(lessons_repo, **kwargs):
    candidate = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": [],
    }
    return lesson_store.save_candidate_lesson(candidate, **kwargs)


# ── preview_merge ─────────────────────────────────────────────────────────────

def test_preview_merge_returns_candidate_shaped_dict(lessons_repo):
    a = _saved(lessons_repo, title="Lesson A", summary="summary A")
    b = _saved(lessons_repo, title="Lesson B", summary="summary B")
    record, warnings = lesson_merge.preview_merge([a, b])
    assert record["status"] == "candidate"
    assert record["active_knowledge_allowed"] is False
    assert record["source"] == "merge"


def test_preview_merge_has_no_id(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    record, _ = lesson_merge.preview_merge([a, b])
    assert "id" not in record


def test_preview_merge_writes_no_files(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    before = set((lessons_repo / ".agent" / "lessons").rglob("*.json"))
    lesson_merge.preview_merge([a, b])
    after = set((lessons_repo / ".agent" / "lessons").rglob("*.json"))
    assert before == after


def test_preview_merge_unions_tags(lessons_repo):
    a = _saved(lessons_repo, tags=["python", "loops"])
    b = _saved(lessons_repo, tags=["python", "strings"])
    record, _ = lesson_merge.preview_merge([a, b])
    assert set(record["tags"]) == {"python", "loops", "strings"}


def test_preview_merge_accepts_explicit_tags(lessons_repo):
    a = _saved(lessons_repo, tags=["python"])
    b = _saved(lessons_repo, tags=["go"])
    record, _ = lesson_merge.preview_merge([a, b], tags=["custom-tag"])
    assert record["tags"] == ["custom-tag"]


def test_preview_merge_sets_merge_sources(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    record, _ = lesson_merge.preview_merge([a, b])
    assert record["merge_sources"] == [a["id"], b["id"]]
    assert record["supersedes"] == [a["id"], b["id"]]


def test_preview_merge_preserves_sources_data(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    record, _ = lesson_merge.preview_merge([a, b])
    ids_in_data = {e["id"] for e in record["merge_sources_data"]}
    assert ids_in_data == {a["id"], b["id"]}
    for entry in record["merge_sources_data"]:
        assert "candidate" in entry
        assert "evaluation" in entry


def test_preview_merge_warns_about_active_source(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    lesson_store.promote_lesson(a["id"])
    a_active = lesson_store.get_lesson_by_id(a["id"])
    _, warnings = lesson_merge.preview_merge([a_active, b])
    assert any("active" in w for w in warnings)


def test_preview_merge_warns_about_mixed_kinds(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    lesson_store.patch_lesson_fields(b["id"], {"kind": "anti_lesson"})
    b_patched = lesson_store.get_lesson_by_id(b["id"])
    _, warnings = lesson_merge.preview_merge([a, b_patched])
    assert any("kind" in w for w in warnings)


def test_preview_merge_requires_at_least_two(lessons_repo):
    a = _saved(lessons_repo)
    with pytest.raises(ValueError, match="at least 2"):
        lesson_merge.preview_merge([a])
```

- [ ] **Step 2: Write failing tests for `archive_lesson`**

Create `tests/test_lesson_archive.py`:

```python
import pytest
from core import lesson_merge, lesson_store


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(
        lesson_store, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent"
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    return tmp_path


def _saved(lessons_repo, **kwargs):
    candidate = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": [],
    }
    return lesson_store.save_candidate_lesson(candidate, **kwargs)


def test_archive_candidate_sets_flag(lessons_repo):
    saved = _saved(lessons_repo)
    updated = lesson_merge.archive_lesson(saved["id"])
    assert updated["archived"] is True
    # File still in candidate bucket
    bucket = (
        lessons_repo / ".agent" / "lessons" / "candidate" / f"{saved['id']}.json"
    )
    assert bucket.is_file()


def test_archive_blocked_sets_flag(lessons_repo):
    saved = _saved(lessons_repo)
    lesson_store.block_lesson(saved["id"])
    updated = lesson_merge.archive_lesson(saved["id"])
    assert updated["archived"] is True
    # File still in blocked bucket
    bucket = (
        lessons_repo / ".agent" / "lessons" / "blocked" / f"{saved['id']}.json"
    )
    assert bucket.is_file()


def test_archive_active_raises(lessons_repo):
    saved = _saved(lessons_repo)
    lesson_store.promote_lesson(saved["id"])
    with pytest.raises(ValueError, match="cannot archive an active lesson"):
        lesson_merge.archive_lesson(saved["id"])


def test_archive_idempotent(lessons_repo):
    saved = _saved(lessons_repo)
    lesson_merge.archive_lesson(saved["id"])
    updated2 = lesson_merge.archive_lesson(saved["id"])
    assert updated2["archived"] is True


def test_archive_unknown_raises(lessons_repo):
    with pytest.raises(LookupError):
        lesson_merge.archive_lesson("20240101_000000_000000")
```

- [ ] **Step 3: Run all new tests to confirm failure**

```
pytest tests/test_lesson_merge.py tests/test_lesson_archive.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.lesson_merge'`

- [ ] **Step 4: Write `core/lesson_merge.py` with `preview_merge` and `archive_lesson`**

```python
"""Lesson merge and archive operations.

All writes use helpers from core.lesson_store. No model calls anywhere.
"""
from __future__ import annotations

from core.lesson_store import (
    STATUS_ACTIVE,
    STATUS_CANDIDATE,
    _coerce_tags,
    get_lesson_by_id,
    patch_lesson_fields,
    save_raw_lesson_record,
    _generate_lesson_id,
    _lessons_root,
    _now_iso,
)


_MAX_SUMMARY_CHARS = 500


def _union_tags(lessons: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lesson in lessons:
        for tag in lesson.get("tags") or []:
            if isinstance(tag, str) and tag not in seen:
                seen.add(tag)
                out.append(tag)
    return out


def _join_summaries(lessons: list[dict]) -> str:
    parts = [l.get("summary", "").strip() for l in lessons if l.get("summary", "").strip()]
    joined = " | ".join(parts)
    if len(joined) > _MAX_SUMMARY_CHARS:
        return joined[:_MAX_SUMMARY_CHARS] + "…"
    return joined


def preview_merge(
    lessons: list[dict],
    *,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> tuple[dict, list[str]]:
    """Build a merged lesson preview dict without writing anything.

    Returns (preview_record, warnings).
    The preview_record has no id/created_at/updated_at.
    """
    if len(lessons) < 2:
        raise ValueError("preview_merge requires at least 2 lessons")

    warnings: list[str] = []

    active_ids = [l["id"] for l in lessons if l.get("status") == STATUS_ACTIVE]
    if active_ids:
        warnings.append(f"{len(active_ids)} active lesson(s) will be superseded")

    kinds = {l.get("kind") or "lesson" for l in lessons}
    if len(kinds) > 1:
        warnings.append(f"mixing lesson kinds: {sorted(kinds)}")
    resolved_kind = next(iter(kinds)) if len(kinds) == 1 else "mixed"

    merged_tags = _union_tags(lessons) if tags is None else _coerce_tags(tags)
    source_ids = [l["id"] for l in lessons]
    sources_data = [
        {
            "id": l["id"],
            "candidate": l.get("candidate") or {},
            "evaluation": l.get("evaluation") or {},
        }
        for l in lessons
    ]

    record = {
        "kind": resolved_kind,
        "status": STATUS_CANDIDATE,
        "active_knowledge_allowed": False,
        "scope": lessons[0].get("scope", "global"),
        "repo_scope_id": lessons[0].get("repo_scope_id"),
        "repo_path_hint": lessons[0].get("repo_path_hint"),
        "source": "merge",
        "source_report": None,
        "case_name": None,
        "title": title if title is not None else (lessons[0].get("title") or "Merged lesson"),
        "summary": summary if summary is not None else _join_summaries(lessons),
        "tags": merged_tags,
        "candidate": {},
        "evaluation": {
            "promotion": "needs_human_review",
            "active_knowledge_allowed": False,
            "score": 0.0,
            "reasons": ["merged lesson — human review required"],
        },
        "archived": False,
        "superseded_by": None,
        "supersedes": source_ids,
        "merge_sources": source_ids,
        "merge_sources_data": sources_data,
        "duplicate_of": None,
    }
    return record, warnings


def archive_lesson(
    lesson_id: str,
    *,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Set archived=True on a candidate or blocked lesson.

    Idempotent. Raises ValueError if the lesson is active.
    """
    record = get_lesson_by_id(
        lesson_id, repo_path=repo_path, scope=scope, repo_scope_id=repo_scope_id
    )
    if record.get("status") == STATUS_ACTIVE:
        raise ValueError(f"cannot archive an active lesson: {lesson_id}")
    if record.get("archived"):
        return record
    return patch_lesson_fields(
        lesson_id,
        {"archived": True},
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
```

- [ ] **Step 5: Run all tests — all must pass**

```
pytest tests/test_lesson_merge.py tests/test_lesson_archive.py -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```
git add core/lesson_merge.py tests/test_lesson_merge.py tests/test_lesson_archive.py
git commit -m "feat: add lesson_merge module — preview_merge and archive_lesson"
```

---

## Task 4 — core/lesson_merge.py: create_merge

**Files:**
- Modify: `tests/test_lesson_merge.py` (add create_merge tests)
- Modify: `core/lesson_merge.py` (add create_merge)

- [ ] **Step 1: Add failing tests for `create_merge` to `tests/test_lesson_merge.py`**

Append to `tests/test_lesson_merge.py`:

```python
# ── create_merge ──────────────────────────────────────────────────────────────

def test_create_merge_writes_candidate_to_disk(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    new, _ = lesson_merge.create_merge(
        [a["id"], b["id"]], title="Merged", summary="combined", tags=[]
    )
    assert new["status"] == "candidate"
    assert new["active_knowledge_allowed"] is False
    bucket = (
        lessons_repo / ".agent" / "lessons" / "candidate" / f"{new['id']}.json"
    )
    assert bucket.is_file()


def test_create_merge_sources_get_superseded_by(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    new, superseded = lesson_merge.create_merge(
        [a["id"], b["id"]], title="M", summary="", tags=[]
    )
    a_after = lesson_store.get_lesson_by_id(a["id"])
    b_after = lesson_store.get_lesson_by_id(b["id"])
    assert a_after["superseded_by"] == new["id"]
    assert b_after["superseded_by"] == new["id"]
    assert set(superseded) == {a["id"], b["id"]}


def test_create_merge_active_without_confirm_raises(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    lesson_store.promote_lesson(a["id"])
    with pytest.raises(ValueError, match="confirm_supersede_active"):
        lesson_merge.create_merge([a["id"], b["id"]], title="M", summary="", tags=[])


def test_create_merge_active_with_confirm_succeeds(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    lesson_store.promote_lesson(a["id"])
    new, _ = lesson_merge.create_merge(
        [a["id"], b["id"]],
        title="M",
        summary="",
        tags=[],
        confirm_supersede_active=True,
    )
    assert new["status"] == "candidate"
    assert new["active_knowledge_allowed"] is False


def test_create_merge_mixed_kinds_without_confirm_raises(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    lesson_store.patch_lesson_fields(b["id"], {"kind": "anti_lesson"})
    with pytest.raises(ValueError, match="confirm_mix_kinds"):
        lesson_merge.create_merge([a["id"], b["id"]], title="M", summary="", tags=[])


def test_create_merge_mixed_kinds_with_confirm_succeeds(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    lesson_store.patch_lesson_fields(b["id"], {"kind": "anti_lesson"})
    new, _ = lesson_merge.create_merge(
        [a["id"], b["id"]], title="M", summary="", tags=[], confirm_mix_kinds=True
    )
    assert new["status"] == "candidate"


def test_create_merge_preserves_sources_data(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    new, _ = lesson_merge.create_merge(
        [a["id"], b["id"]], title="M", summary="", tags=[]
    )
    ids_in_data = {e["id"] for e in new["merge_sources_data"]}
    assert ids_in_data == {a["id"], b["id"]}


def test_create_merge_never_auto_promotes(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    new, _ = lesson_merge.create_merge(
        [a["id"], b["id"]], title="M", summary="", tags=[]
    )
    assert new["status"] == "candidate"
    assert new["active_knowledge_allowed"] is False


def test_create_merge_requires_at_least_two_ids(lessons_repo):
    a = _saved(lessons_repo)
    with pytest.raises(ValueError, match="at least 2"):
        lesson_merge.create_merge([a["id"]], title="M", summary="", tags=[])


def test_create_merge_raises_for_unknown_source_id(lessons_repo):
    a = _saved(lessons_repo)
    with pytest.raises(LookupError):
        lesson_merge.create_merge(
            [a["id"], "20240101_000000_000000"], title="M", summary="", tags=[]
        )
```

- [ ] **Step 2: Run to confirm new tests fail**

```
pytest tests/test_lesson_merge.py -k "create_merge" -v
```

Expected: `AttributeError: module 'core.lesson_merge' has no attribute 'create_merge'`

- [ ] **Step 3: Add `create_merge` to `core/lesson_merge.py`**

Append to `core/lesson_merge.py` after the `archive_lesson` function:

```python
def create_merge(
    source_ids: list[str],
    title: str,
    summary: str,
    tags: list[str],
    *,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
    confirm_supersede_active: bool = False,
    confirm_mix_kinds: bool = False,
) -> tuple[dict, list[str]]:
    """Create a merged lesson candidate from source_ids.

    Returns (new_record, superseded_ids).
    Raises ValueError if guards not confirmed; LookupError if any ID not found.
    The merged record is always candidate and never auto-promoted.
    """
    if len(source_ids) < 2:
        raise ValueError("create_merge requires at least 2 source IDs")

    lessons = [
        get_lesson_by_id(
            lid, repo_path=repo_path, scope=scope, repo_scope_id=repo_scope_id
        )
        for lid in source_ids
    ]

    active_ids = [l["id"] for l in lessons if l.get("status") == STATUS_ACTIVE]
    if active_ids and not confirm_supersede_active:
        raise ValueError(
            f"active lessons require confirm_supersede_active=True: {active_ids}"
        )

    kinds = {l.get("kind") or "lesson" for l in lessons}
    if len(kinds) > 1 and not confirm_mix_kinds:
        raise ValueError(
            f"mixed lesson kinds require confirm_mix_kinds=True: {sorted(kinds)}"
        )

    record, _ = preview_merge(lessons, title=title, summary=summary, tags=tags)

    # Assign identity
    lessons_root = _lessons_root(repo_path)
    lesson_id = _generate_lesson_id(lessons_root)
    now = _now_iso()
    record["id"] = lesson_id
    record["created_at"] = now
    record["updated_at"] = now

    # Write merged record first — patch sources only after successful write
    save_raw_lesson_record(record, repo_path=repo_path)

    superseded: list[str] = []
    for lid in source_ids:
        patch_lesson_fields(lid, {"superseded_by": lesson_id}, repo_path=repo_path)
        superseded.append(lid)

    return record, superseded
```

- [ ] **Step 4: Run all lesson_merge tests — all must pass**

```
pytest tests/test_lesson_merge.py -v
```

Expected: all pass

- [ ] **Step 5: Run full lesson test suite to catch regressions**

```
pytest tests/test_lesson_store.py tests/test_lesson_merge.py tests/test_lesson_archive.py tests/test_lesson_duplicates.py -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```
git add core/lesson_merge.py tests/test_lesson_merge.py
git commit -m "feat: add create_merge to lesson_merge — merge candidates with guard confirmation"
```

---

## Task 5 — web/app.py: four new routes

**Files:**
- Modify: `web/app.py`
- Create: `tests/test_lesson_merge_routes.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/test_lesson_merge_routes.py`:

```python
import json
import pytest
from core import lesson_store


def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(
        lesson_store, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent"
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)


def _candidate():
    return {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": [],
    }


# ── GET /lessons/duplicates ──────────────────────────────────────────────────

def test_duplicates_route_returns_empty_for_no_lessons(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    resp = web_app.app.test_client().get("/lessons/duplicates")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["groups"] == []


def test_duplicates_route_groups_same_source_report(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    lesson_store.save_candidate_lesson(
        _candidate(), source_report="r1.json", case_name="case_x", title="Lesson A"
    )
    lesson_store.save_candidate_lesson(
        _candidate(), source_report="r1.json", case_name="case_x", title="Lesson B"
    )
    resp = web_app.app.test_client().get("/lessons/duplicates")
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["groups"]) == 1
    assert len(body["groups"][0]["lesson_ids"]) == 2


# ── POST /lessons/merge/preview ──────────────────────────────────────────────

def test_merge_preview_route_returns_preview(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate(), title="A")
    b = lesson_store.save_candidate_lesson(_candidate(), title="B")
    resp = web_app.app.test_client().post(
        "/lessons/merge/preview",
        json={"lesson_ids": [a["id"], b["id"]]},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["preview"]["status"] == "candidate"
    assert body["preview"]["active_knowledge_allowed"] is False


def test_merge_preview_route_requires_two_ids(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    resp = web_app.app.test_client().post(
        "/lessons/merge/preview",
        json={"lesson_ids": [a["id"]]},
    )
    assert resp.status_code == 400


def test_merge_preview_route_no_file_writes(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    b = lesson_store.save_candidate_lesson(_candidate())
    before = set((tmp_path / ".agent" / "lessons").rglob("*.json"))
    web_app.app.test_client().post(
        "/lessons/merge/preview",
        json={"lesson_ids": [a["id"], b["id"]]},
    )
    after = set((tmp_path / ".agent" / "lessons").rglob("*.json"))
    assert before == after


# ── POST /lessons/merge/create ───────────────────────────────────────────────

def test_merge_create_route_creates_candidate(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    b = lesson_store.save_candidate_lesson(_candidate())
    resp = web_app.app.test_client().post(
        "/lessons/merge/create",
        json={"lesson_ids": [a["id"], b["id"]], "title": "Merged", "summary": "", "tags": []},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["lesson"]["status"] == "candidate"
    assert set(body["superseded"]) == {a["id"], b["id"]}


def test_merge_create_route_rejects_active_without_confirm(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    b = lesson_store.save_candidate_lesson(_candidate())
    lesson_store.promote_lesson(a["id"])
    resp = web_app.app.test_client().post(
        "/lessons/merge/create",
        json={"lesson_ids": [a["id"], b["id"]], "title": "M", "summary": "", "tags": []},
    )
    assert resp.status_code == 400
    assert "confirm_supersede_active" in resp.get_json()["error"]


def test_merge_create_route_requires_title(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    b = lesson_store.save_candidate_lesson(_candidate())
    resp = web_app.app.test_client().post(
        "/lessons/merge/create",
        json={"lesson_ids": [a["id"], b["id"]], "title": "", "summary": "", "tags": []},
    )
    assert resp.status_code == 400


# ── POST /lessons/archive ─────────────────────────────────────────────────────

def test_archive_route_sets_flag(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    resp = web_app.app.test_client().post(
        "/lessons/archive",
        json={"lesson_id": a["id"]},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["lesson"]["archived"] is True


def test_archive_route_rejects_active(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    lesson_store.promote_lesson(a["id"])
    resp = web_app.app.test_client().post(
        "/lessons/archive",
        json={"lesson_id": a["id"]},
    )
    assert resp.status_code == 400


def test_archive_route_404_for_unknown(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    resp = web_app.app.test_client().post(
        "/lessons/archive",
        json={"lesson_id": "20240101_000000_000000"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to confirm they fail**

```
pytest tests/test_lesson_merge_routes.py -v
```

Expected: failures on `duplicates` / `merge/preview` / `merge/create` / `archive` returning 404

- [ ] **Step 3: Add imports to `web/app.py`**

Find the existing `from core import lesson_store` line (around line 45) and add below it:

```python
from core import lesson_duplicates
from core import lesson_merge
```

- [ ] **Step 4: Add the four routes to `web/app.py`**

Add the following four route functions after the existing `lessons_block_route` function (around line 2410). Follow the exact indentation style of the surrounding code:

```python
@app.route("/lessons/duplicates", methods=["GET"])
def lessons_duplicates_route():
    """Return duplicate hint groups for the current lesson set.

    Query params: status?, scope?, repo_path?, repo_scope_id?, include_global?
    """
    repo_path = _lesson_repo_path(request.values.get("repo_path"))
    status = (request.values.get("status") or "").strip() or None
    scope = _lesson_scope_arg(request.values.get("scope"))
    repo_scope_id = _lesson_repo_scope_id_arg(request.values.get("repo_scope_id"))
    include_global = (request.values.get("include_global") or "true").lower() != "false"
    if status is not None and status not in lesson_store.LESSON_STATUSES:
        return {"ok": False, "error": f"invalid status: {status!r}"}, 400
    try:
        lessons = lesson_store.list_lessons(
            status=status,
            repo_path=repo_path,
            include_global=include_global,
            scope=scope,
            repo_scope_id=repo_scope_id,
        )
        groups = lesson_duplicates.find_duplicate_groups(lessons)
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"failed to find duplicates: {type(e).__name__}"}, 500
    return {"ok": True, "groups": groups}


@app.route("/lessons/merge/preview", methods=["POST"])
def lessons_merge_preview_route():
    """Preview a merged lesson without writing anything.

    JSON body: {lesson_ids: [str, ...], title?: str, summary?: str, tags?: [str]}
    """
    payload = request.get_json(silent=True) or {}
    repo_path = _lesson_repo_path(payload.get("repo_path"))
    scope = _lesson_scope_arg(payload.get("scope"))
    repo_scope_id = _lesson_repo_scope_id_arg(payload.get("repo_scope_id"))
    lesson_ids = payload.get("lesson_ids")
    if not isinstance(lesson_ids, list) or len(lesson_ids) < 2:
        return {"ok": False, "error": "lesson_ids must be a list of at least 2 IDs"}, 400
    title = payload.get("title") or None
    summary = payload.get("summary") or None
    raw_tags = payload.get("tags")
    tags = raw_tags if isinstance(raw_tags, list) else None
    try:
        lessons = [
            lesson_store.get_lesson_by_id(
                lid, repo_path=repo_path, scope=scope, repo_scope_id=repo_scope_id
            )
            for lid in lesson_ids
        ]
        record, warnings = lesson_merge.preview_merge(
            lessons, title=title, summary=summary, tags=tags
        )
    except LookupError as e:
        return {"ok": False, "error": str(e)}, 404
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"preview failed: {type(e).__name__}"}, 500
    return {"ok": True, "preview": record, "warnings": warnings}


@app.route("/lessons/merge/create", methods=["POST"])
def lessons_merge_create_route():
    """Create a merged lesson candidate.

    JSON body: {lesson_ids, title, summary, tags,
                confirm_supersede_active?: bool, confirm_mix_kinds?: bool,
                scope?, repo_path?, repo_scope_id?}
    """
    payload = request.get_json(silent=True) or {}
    repo_path = _lesson_repo_path(payload.get("repo_path"))
    scope = _lesson_scope_arg(payload.get("scope"))
    repo_scope_id = _lesson_repo_scope_id_arg(payload.get("repo_scope_id"))
    lesson_ids = payload.get("lesson_ids")
    if not isinstance(lesson_ids, list) or len(lesson_ids) < 2:
        return {"ok": False, "error": "lesson_ids must be a list of at least 2 IDs"}, 400
    title = (payload.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "title is required"}, 400
    summary = payload.get("summary") or ""
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    confirm_supersede_active = payload.get("confirm_supersede_active") is True
    confirm_mix_kinds = payload.get("confirm_mix_kinds") is True
    try:
        new_record, superseded = lesson_merge.create_merge(
            lesson_ids,
            title,
            summary,
            tags,
            repo_path=repo_path,
            scope=scope,
            repo_scope_id=repo_scope_id,
            confirm_supersede_active=confirm_supersede_active,
            confirm_mix_kinds=confirm_mix_kinds,
        )
    except LookupError as e:
        return {"ok": False, "error": str(e)}, 404
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"merge failed: {type(e).__name__}"}, 500
    return {"ok": True, "lesson": new_record, "superseded": superseded}


@app.route("/lessons/archive", methods=["POST"])
def lessons_archive_route():
    """Archive a candidate or blocked lesson (set archived=True).

    JSON body: {lesson_id, scope?, repo_path?, repo_scope_id?}
    """
    payload = request.get_json(silent=True) or {}
    repo_path = _lesson_repo_path(payload.get("repo_path"))
    scope = _lesson_scope_arg(payload.get("scope"))
    repo_scope_id = _lesson_repo_scope_id_arg(payload.get("repo_scope_id"))
    lesson_id = (payload.get("lesson_id") or "").strip()
    if not lesson_id:
        return {"ok": False, "error": "lesson_id is required"}, 400
    try:
        record = lesson_merge.archive_lesson(
            lesson_id,
            repo_path=repo_path,
            scope=scope,
            repo_scope_id=repo_scope_id,
        )
    except LookupError as e:
        return {"ok": False, "error": str(e)}, 404
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"archive failed: {type(e).__name__}"}, 500
    return {"ok": True, "lesson": record}
```

- [ ] **Step 5: Run the route tests — all must pass**

```
pytest tests/test_lesson_merge_routes.py -v
```

Expected: all pass

- [ ] **Step 6: Run the full b2a test suite — no regressions**

```
pytest tests/test_lesson_store.py tests/test_lesson_duplicates.py tests/test_lesson_merge.py tests/test_lesson_archive.py tests/test_lesson_merge_routes.py -v
```

Expected: all pass

- [ ] **Step 7: Commit**

```
git add web/app.py tests/test_lesson_merge_routes.py
git commit -m "feat: add /lessons/duplicates, /merge/preview, /merge/create, /archive routes"
```

---

## b2a Complete

At this point b2a is done: duplicate detection, merge preview/create, archive, all routes, all tests — no UI changes.

**b2b (separate plan)** will cover:
- Filter bar additions (kind, superseded/archived toggles)
- Select mode + lesson card checkboxes
- Preview merge modal
- Duplicate hints collapsible panel
- Optional `POST /lessons/supersede` route
