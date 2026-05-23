import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.penalty import PenaltyResult, build_penalty_map
from graph.schema import ProgramGraph


def test_empty_graph_returns_empty_result_with_no_db_call(tmp_path):
    graph = ProgramGraph()

    with patch("graph.penalty.get_pool") as mock_get_pool:
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert isinstance(result, PenaltyResult)
    assert result.penalty_map == {}
    assert result.unmatched_paths == []
    mock_get_pool.assert_not_called()


def test_blocked_only_two_lessons_same_file_yields_doubled_penalty(tmp_path):
    graph = ProgramGraph()
    graph.add_node("foo.py", "file")

    fake_lessons = [
        {"candidate": {"changed_files": ["foo.py"]}},
        {"candidate": {"changed_files": ["foo.py"]}},
    ]
    with patch("graph.penalty.list_lessons", return_value=fake_lessons), \
         patch("graph.penalty.db_enabled", return_value=False):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.penalty_map == {"foo.py": 10.0}
    assert result.unmatched_paths == []


def test_transient_at_file_level_null_symbol_three_rows_yields_3_0(tmp_path):
    graph = ProgramGraph()
    graph.add_node("bar.py", "file")

    fake_rows = [("bar.py", None, 3)]
    with patch("graph.penalty.list_lessons", return_value=[]), \
         patch("graph.penalty.db_enabled", return_value=True), \
         patch("graph.penalty.build_project_tag", return_value="test-tag"), \
         patch("graph.penalty._fetch_patch_attempt_rows", return_value=fake_rows):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.penalty_map == {"bar.py": 3.0}
    assert result.unmatched_paths == []


def test_transient_at_symbol_level_routes_to_symbol_node(tmp_path):
    graph = ProgramGraph()
    graph.add_node("bar.py", "file")
    graph.add_node("bar.py::do_thing", "function")

    fake_rows = [("bar.py", "do_thing", 2)]
    with patch("graph.penalty.list_lessons", return_value=[]), \
         patch("graph.penalty.db_enabled", return_value=True), \
         patch("graph.penalty.build_project_tag", return_value="test-tag"), \
         patch("graph.penalty._fetch_patch_attempt_rows", return_value=fake_rows):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.penalty_map == {"bar.py::do_thing": 2.0}
    assert result.penalty_map.get("bar.py", 0) == 0
    assert result.unmatched_paths == []


def test_mixed_routing_file_and_multiple_symbols(tmp_path):
    graph = ProgramGraph()
    graph.add_node("bar.py", "file")
    graph.add_node("bar.py::do_thing", "function")
    graph.add_node("bar.py::helper", "function")

    fake_rows = [
        ("bar.py", None, 2),
        ("bar.py", "do_thing", 3),
        ("bar.py", "helper", 1),
    ]
    with patch("graph.penalty.list_lessons", return_value=[]), \
         patch("graph.penalty.db_enabled", return_value=True), \
         patch("graph.penalty.build_project_tag", return_value="test-tag"), \
         patch("graph.penalty._fetch_patch_attempt_rows", return_value=fake_rows):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.penalty_map == {
        "bar.py": 2.0,
        "bar.py::do_thing": 3.0,
        "bar.py::helper": 1.0,
    }
    assert result.unmatched_paths == []


def test_symbol_gone_lands_in_unmatched_no_rollup_to_file(tmp_path):
    graph = ProgramGraph()
    graph.add_node("bar.py", "file")

    fake_rows = [("bar.py", "renamed_func", 4)]
    with patch("graph.penalty.list_lessons", return_value=[]), \
         patch("graph.penalty.db_enabled", return_value=True), \
         patch("graph.penalty.build_project_tag", return_value="test-tag"), \
         patch("graph.penalty._fetch_patch_attempt_rows", return_value=fake_rows):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.penalty_map == {}
    assert "bar.py::renamed_func" in result.unmatched_paths
    assert result.penalty_map.get("bar.py", 0) == 0  # no silent rollup


def test_combined_sources_blocked_plus_transient_on_same_file(tmp_path):
    graph = ProgramGraph()
    graph.add_node("foo.py", "file")

    fake_lessons = [{"candidate": {"changed_files": ["foo.py"]}}]
    fake_rows = [("foo.py", None, 2)]
    with patch("graph.penalty.list_lessons", return_value=fake_lessons), \
         patch("graph.penalty.db_enabled", return_value=True), \
         patch("graph.penalty.build_project_tag", return_value="test-tag"), \
         patch("graph.penalty._fetch_patch_attempt_rows", return_value=fake_rows):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    # 1 blocked * 5.0 + 2 transient * 1.0 = 7.0
    assert result.penalty_map == {"foo.py": 7.0}
    assert result.unmatched_paths == []


def test_db_disabled_yields_zero_transient_but_keeps_blocked(tmp_path):
    graph = ProgramGraph()
    graph.add_node("foo.py", "file")

    fake_lessons = [{"candidate": {"changed_files": ["foo.py"]}}]
    with patch("graph.penalty.list_lessons", return_value=fake_lessons), \
         patch("graph.penalty.db_enabled", return_value=False), \
         patch("graph.penalty._fetch_patch_attempt_rows") as mock_fetch:
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.penalty_map == {"foo.py": 5.0}
    assert result.unmatched_paths == []
    mock_fetch.assert_not_called()


def test_stale_lesson_referencing_missing_file_lands_in_unmatched(tmp_path):
    graph = ProgramGraph()
    graph.add_node("foo.py", "file")

    fake_lessons = [{"candidate": {"changed_files": ["removed.py"]}}]
    with patch("graph.penalty.list_lessons", return_value=fake_lessons), \
         patch("graph.penalty.db_enabled", return_value=False):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.penalty_map == {}
    assert "removed.py" in result.unmatched_paths


def test_malformed_lesson_records_are_skipped_without_exception(tmp_path):
    graph = ProgramGraph()
    graph.add_node("foo.py", "file")

    fake_lessons = [
        {"candidate": {"changed_files": ["foo.py"]}},   # valid
        "not a dict",                                    # bad shape
        {"candidate": "not a dict"},                     # candidate wrong type
        {"candidate": {"changed_files": "not a list"}},  # changed_files wrong type
        {"candidate": {"changed_files": [42, "foo.py"]}},  # bad path entry then valid
    ]
    with patch("graph.penalty.list_lessons", return_value=fake_lessons), \
         patch("graph.penalty.db_enabled", return_value=False):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    # Two valid increments for foo.py (from records 1 and 5)
    assert result.penalty_map == {"foo.py": 10.0}
    assert result.unmatched_paths == []


def test_path_normalization_handles_dotslash_backslash_and_foreign_absolute(tmp_path):
    graph = ProgramGraph()
    graph.add_node("foo.py", "file")
    graph.add_node("foo/bar.py", "file")

    fake_lessons = [
        {"candidate": {"changed_files": ["./foo.py", "foo\\bar.py", "/etc/passwd"]}},
    ]
    with patch("graph.penalty.list_lessons", return_value=fake_lessons), \
         patch("graph.penalty.db_enabled", return_value=False):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.penalty_map == {"foo.py": 5.0, "foo/bar.py": 5.0}
    assert "/etc/passwd" in result.unmatched_paths


def test_penalty_result_exposes_per_source_count_breakdown(tmp_path):
    graph = ProgramGraph()
    graph.add_node("foo.py", "file")
    graph.add_node("foo.py::do_thing", "function")

    fake_lessons = [
        {"candidate": {"changed_files": ["foo.py"]}},
        {"candidate": {"changed_files": ["foo.py"]}},
    ]
    fake_rows = [
        ("foo.py", None, 3),
        ("foo.py", "do_thing", 4),
    ]
    with patch("graph.penalty.list_lessons", return_value=fake_lessons), \
         patch("graph.penalty.db_enabled", return_value=True), \
         patch("graph.penalty.build_project_tag", return_value="test-tag"), \
         patch("graph.penalty._fetch_patch_attempt_rows", return_value=fake_rows):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    assert result.blocked_counts == {"foo.py": 2}
    assert result.transient_counts == {"foo.py": 3, "foo.py::do_thing": 4}


def test_case_insensitive_fallback_matches_windows_style_path(tmp_path):
    graph = ProgramGraph()
    graph.add_node("src/foo.py", "file")
    graph.add_node("src/foo.py::DoThing", "function")

    # Blocked lesson recorded with different case in the path part.
    fake_lessons = [{"candidate": {"changed_files": ["src/Foo.py"]}}]
    # Transient symbol-level row also with mismatched path case but exact symbol case.
    fake_rows = [("SRC/foo.py", "DoThing", 4)]

    with patch("graph.penalty.list_lessons", return_value=fake_lessons), \
         patch("graph.penalty.db_enabled", return_value=True), \
         patch("graph.penalty.build_project_tag", return_value="test-tag"), \
         patch("graph.penalty._fetch_patch_attempt_rows", return_value=fake_rows):
        result = build_penalty_map(graph, repo_path=str(tmp_path))

    # Both contributions land on the canonical (graph) node ids.
    assert result.penalty_map["src/foo.py"] == 5.0           # blocked
    assert result.penalty_map["src/foo.py::DoThing"] == 4.0  # transient
    assert result.unmatched_paths == []
