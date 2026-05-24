"""Phase 12.5b — tests for graph weight explainability helper and CLI."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.penalty import PenaltyResult
from graph.schema import ProgramGraph
from graph.weights import explain_node_weights
from scripts import explain_graph_weights as cli


def _build_simple_graph() -> ProgramGraph:
    graph = ProgramGraph()
    graph.add_node("core/a.py", "file")
    graph.add_node("core/b.py", "file")
    graph.add_node("core/c.py", "file")
    graph.add_node("core/a.py::main", "function")
    graph.add_node("core/b.py::helper", "function")
    graph.add_node("core/c.py::util", "function")

    graph.add_edge("core/a.py", "core/b.py", "imports")
    graph.add_edge("core/a.py", "core/a.py::main", "contains")
    graph.add_edge("core/b.py", "core/b.py::helper", "contains")
    graph.add_edge("core/c.py", "core/c.py::util", "contains")
    graph.add_edge("core/a.py::main", "core/b.py::helper", "resolved_call")
    graph.add_edge("core/c.py::util", "core/b.py::helper", "resolved_call")
    return graph


def test_explain_node_weights_returns_rows_with_breakdown_fields():
    graph = _build_simple_graph()

    rows = explain_node_weights(graph)

    assert isinstance(rows, list)
    assert rows  # non-empty
    sample = rows[0]
    expected_fields = {
        "node_id",
        "node_kind",
        "total_weight",
        "topology_contribution",
        "complexity_contribution",
        "failure_penalty",
        "in_degree",
        "out_degree",
        "complexity",
        "reasons",
    }
    assert expected_fields <= sample.keys()


def test_explain_node_weights_contributions_sum_to_total_weight():
    graph = _build_simple_graph()

    rows = explain_node_weights(graph)

    for row in rows:
        total = (
            row["topology_contribution"]
            + row["complexity_contribution"]
            + row["failure_penalty"]
        )
        assert abs(total - row["total_weight"]) < 1e-6, row


def test_explain_node_weights_empty_graph_returns_empty_list():
    rows = explain_node_weights(ProgramGraph())

    assert rows == []


def test_explain_node_weights_records_penalty_when_repo_path_supplied(tmp_path):
    graph = _build_simple_graph()
    fake = PenaltyResult(
        penalty_map={"core/b.py::helper": 5.0},
        unmatched_paths=[],
        blocked_counts={"core/b.py::helper": 1},
        transient_counts={},
    )

    with patch("graph.weights.build_penalty_map", return_value=fake):
        rows = explain_node_weights(graph, repo_path=str(tmp_path))

    by_id = {row["node_id"]: row for row in rows}
    helper = by_id["core/b.py::helper"]
    assert helper["failure_penalty"] == 5.0
    assert "blocked_lessons=1" in helper["reasons"]


def test_explain_node_weights_includes_node_kind():
    graph = _build_simple_graph()

    rows = explain_node_weights(graph)

    kinds = {row["node_id"]: row["node_kind"] for row in rows}
    assert kinds["core/a.py"] == "file"
    assert kinds["core/b.py::helper"] == "function"


# --- CLI tests ---


def test_cli_prints_table_with_ranked_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(["--repo-path", str(tmp_path), "--include-zero-penalty"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Rank" in captured.out
    assert "Node" in captured.out
    assert "core/b.py::helper" in captured.out
    assert "Traceback" not in captured.err


def test_cli_json_output_returns_valid_json(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        ["--repo-path", str(tmp_path), "--json", "--include-zero-penalty"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert isinstance(payload, list)
    assert payload
    assert "node_id" in payload[0]
    assert "rank" in payload[0]
    assert "total_weight" in payload[0]


def test_cli_top_limit_caps_row_count(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--top",
            "2",
            "--json",
            "--include-zero-penalty",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert len(payload) == 2
    assert payload[0]["rank"] == 1
    assert payload[1]["rank"] == 2


def test_cli_filter_by_kind_excludes_other_kinds(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--filter",
            "function",
            "--json",
            "--include-zero-penalty",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload
    assert all(row["node_kind"] == "function" for row in payload)


def test_cli_default_excludes_zero_penalty_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)
    fake = PenaltyResult(
        penalty_map={"core/b.py::helper": 5.0},
        unmatched_paths=[],
        blocked_counts={"core/b.py::helper": 1},
        transient_counts={},
    )

    with patch("graph.weights.build_penalty_map", return_value=fake):
        exit_code = cli.main(["--repo-path", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert len(payload) == 1
    assert payload[0]["node_id"] == "core/b.py::helper"
    assert payload[0]["failure_penalty"] == 5.0


def test_cli_include_zero_penalty_shows_all_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        ["--repo-path", str(tmp_path), "--json", "--include-zero-penalty"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    # Simple graph has 6 non-noise nodes — all should appear.
    assert len(payload) >= 6


def test_cli_missing_repo_path_fails_friendly(tmp_path, capsys, monkeypatch):
    missing = tmp_path / "does_not_exist"

    exit_code = cli.main(["--repo-path", str(missing)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_fail_soft_when_no_nodes_in_graph(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: ProgramGraph())

    exit_code = cli.main(["--repo-path", str(tmp_path), "--include-zero-penalty"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No nodes" in captured.out or "no nodes" in captured.out.lower()
    assert "Traceback" not in captured.err


def test_cli_invalid_top_value_fails_friendly(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: _build_simple_graph())

    exit_code = cli.main(["--repo-path", str(tmp_path), "--top", "0"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
