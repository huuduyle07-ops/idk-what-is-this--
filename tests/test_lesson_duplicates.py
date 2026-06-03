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
    a = _lesson("A", source_report="report_1.json", case_name="case_x", title="Source Key Test A")
    b = _lesson("B", source_report="report_1.json", case_name="case_y", title="Source Key Test B")
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
