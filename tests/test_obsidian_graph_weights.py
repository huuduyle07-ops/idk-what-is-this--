import sys
import shutil
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.obsidian_exporter import export_graph_to_obsidian
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
