import sys
import shutil
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph import weights as weights_module
from graph.obsidian_exporter import export_graph_to_obsidian
from graph.penalty import PenaltyResult
from graph.schema import ProgramGraph


def test_obsidian_summary_uses_universal_weight_and_omits_call_noise():
    graph = ProgramGraph()
    graph.add_node("app.py", "file")
    graph.add_node("app.py::caller", "function")
    graph.add_node("app.py::complex_target", "function")
    graph.add_node("app.py::simple_target", "function")
    graph.add_node("app.py::complex_target::expr::1", "expression")
    graph.add_node("app.py::complex_target::expr::2", "expression")
    graph.add_node("call::simple_target", "call")
    graph.add_node("unprefixed_raw_call", "call")

    graph.add_edge("app.py", "app.py::caller", "contains")
    graph.add_edge("app.py", "app.py::complex_target", "contains")
    graph.add_edge("app.py", "app.py::simple_target", "contains")
    graph.add_edge("app.py::caller", "app.py::complex_target", "resolved_call")
    graph.add_edge("app.py::caller", "app.py::simple_target", "resolved_call")
    graph.add_edge("app.py::complex_target", "app.py::complex_target::expr::1", "executes")
    graph.add_edge("app.py::complex_target", "app.py::complex_target::expr::2", "executes")
    graph.add_edge("app.py::caller", "call::simple_target", "calls")
    graph.add_edge("app.py::caller", "unprefixed_raw_call", "calls")

    vault_root = Path.cwd() / f".pytest_obsidian_vault_{uuid.uuid4().hex}"
    try:
        vault = Path(export_graph_to_obsidian(graph, str(vault_root)))
        summary = (vault / "GRAPH_SUMMARY.md").read_text(encoding="utf-8")
        exported_files = {path.name for path in vault.glob("*.md")}
    finally:
        shutil.rmtree(vault_root, ignore_errors=True)
    read_first_lines = [
        line for line in summary.splitlines() if line.startswith("- [[")
    ]

    assert read_first_lines[0].startswith("- [[app.py__complex_target]] score=")
    assert "type=function" in read_first_lines[0]
    assert read_first_lines.index(
        next(line for line in read_first_lines if "app.py__complex_target" in line)
    ) < read_first_lines.index(
        next(line for line in read_first_lines if "app.py__simple_target" in line)
    )
    assert "score=2.33" in read_first_lines[0]
    assert "call__simple_target" not in summary
    assert "unprefixed_raw_call" not in summary
    assert "unprefixed_raw_call.md" not in exported_files
    assert "complex_target__expr__" not in summary


def test_obsidian_ai_read_first_reflects_penalty_when_repo_path_passed(monkeypatch):
    graph = ProgramGraph()
    # structural.py is the heavier of the two by structural weight alone:
    # contains two functions, one of which calls the other.
    graph.add_node("structural.py", "file")
    graph.add_node("structural.py::primary", "function")
    graph.add_node("structural.py::secondary", "function")
    graph.add_edge("structural.py", "structural.py::primary", "contains")
    graph.add_edge("structural.py", "structural.py::secondary", "contains")
    graph.add_edge("structural.py::primary", "structural.py::secondary", "resolved_call")

    # penalized.py is lighter structurally but carries heavy lesson history.
    graph.add_node("penalized.py", "file")
    graph.add_node("penalized.py::quiet", "function")
    graph.add_edge("penalized.py", "penalized.py::quiet", "contains")

    fake = PenaltyResult(
        penalty_map={"penalized.py": 20.0},
        unmatched_paths=[],
        blocked_counts={"penalized.py": 4},
        transient_counts={},
    )
    monkeypatch.setattr(weights_module, "build_penalty_map", lambda g, rp: fake)

    vault_root = Path.cwd() / f".pytest_obsidian_vault_{uuid.uuid4().hex}"
    try:
        vault = Path(export_graph_to_obsidian(
            graph, str(vault_root), repo_path="/some/repo"
        ))
        summary = (vault / "GRAPH_SUMMARY.md").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(vault_root, ignore_errors=True)

    file_lines = [
        line for line in summary.splitlines()
        if line.startswith("- [[") and "type=file" in line
    ]
    penalized_idx = next(i for i, line in enumerate(file_lines) if "penalized.py" in line)
    structural_idx = next(i for i, line in enumerate(file_lines) if "structural.py" in line)

    assert penalized_idx < structural_idx, (
        f"penalty failed to flip AI_READ_FIRST order:\n{file_lines}"
    )
