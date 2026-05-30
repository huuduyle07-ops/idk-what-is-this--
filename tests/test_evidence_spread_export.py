"""Phase 12.11b - Evidence spread Markdown export."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.schema import ProgramGraph, build_graph


GUARDRAIL = (
    "Evidence spread is explain-only. It does not override grounding, "
    "harness modes, patch safety, or validation."
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _target_graph() -> ProgramGraph:
    return build_graph(
        [
            {"id": "target.py", "type": "file", "label": "target.py"},
            {"id": "target.py::fib", "type": "function", "label": "fib"},
            {"id": "target.py::helper", "type": "function", "label": "helper"},
            {"id": "tests/test_target.py", "type": "file", "label": "test_target.py"},
            {
                "id": "tests/test_target.py::test_fib",
                "type": "function",
                "label": "test_fib",
            },
        ],
        [
            {"source": "target.py", "target": "target.py::fib", "type": "contains"},
            {"source": "target.py", "target": "target.py::helper", "type": "contains"},
            {
                "source": "target.py::fib",
                "target": "target.py::helper",
                "type": "calls",
            },
            {
                "source": "tests/test_target.py",
                "target": "tests/test_target.py::test_fib",
                "type": "contains",
            },
            {
                "source": "tests/test_target.py::test_fib",
                "target": "target.py::fib",
                "type": "calls",
            },
        ],
    )


# -------------------------- formatter unit tests --------------------------

def test_markdown_formatter_includes_top_nodes_and_scope():
    from web.graph_evidence import (
        build_scope_evidence_spread_debug,
        format_evidence_spread_markdown,
    )

    graph = _target_graph()
    result = build_scope_evidence_spread_debug(
        graph,
        "optimize fib",
        target_node="target.py::fib",
        top_n=5,
    )
    md = format_evidence_spread_markdown(result)

    assert "# Evidence Spread Report" in md
    assert "optimize fib" in md
    assert "target.py::fib" in md
    assert "generated_at" in md.lower()
    # Top nodes table headers
    assert "node_id" in md
    assert "final_score" in md
    assert "base_score" in md
    assert "spread_score" in md
    assert "reasons" in md
    # Scope assessment section
    assert "Change scope" in md or "change scope" in md.lower()
    assert "api_contract_risk" in md
    assert "tests/test_target.py::test_fib" in md
    # Guardrail
    assert GUARDRAIL in md


def test_markdown_formatter_empty_result_still_useful():
    from web.graph_evidence import (
        build_scope_evidence_spread_debug,
        format_evidence_spread_markdown,
    )

    result = build_scope_evidence_spread_debug(ProgramGraph(), "anything")
    md = format_evidence_spread_markdown(result)

    assert "# Evidence Spread Report" in md
    assert "No graph evidence" in md
    assert GUARDRAIL in md


# ---------------------------- route tests --------------------------------

def test_export_route_writes_markdown_inside_reports_dir(tmp_path, monkeypatch):
    from web import app as web_app

    graph = _target_graph()
    monkeypatch.setattr(web_app, "build_graph_from_repo", lambda repo_path: graph)
    monkeypatch.setattr(
        web_app,
        "run_gemini_request",
        lambda prompt: (_ for _ in ()).throw(AssertionError("model call not allowed")),
    )

    repo = _repo(tmp_path)
    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread/export",
            data={
                "repo_path": str(repo),
                "query": "optimize fib",
                "target_node": "target.py::fib",
                "top_n": "4",
            },
        )

    data = response.get_json()
    assert response.status_code == 200, data
    assert data["ok"] is True

    out_path = Path(data["path"])
    assert out_path.is_file()
    assert out_path.suffix == ".md"

    # File must live under .agent/.../reports/evidence_spread/
    parts = out_path.parts
    assert "reports" in parts and "evidence_spread" in parts
    idx = parts.index("reports")
    assert parts[idx + 1] == "evidence_spread"

    text = out_path.read_text(encoding="utf-8")
    assert "target.py::fib" in text
    assert GUARDRAIL in text
    assert data["filename"] == out_path.name
    assert "Evidence Spread Report" in data["markdown_preview"]


def test_export_route_rejects_invalid_repo_path(tmp_path):
    from web import app as web_app

    bogus = tmp_path / "does_not_exist"
    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread/export",
            data={"repo_path": str(bogus), "query": "x"},
        )

    assert response.status_code == 400
    data = response.get_json()
    assert data["ok"] is False
    assert "directory" in data["error"].lower() or "path" in data["error"].lower()


def test_export_route_ignores_user_output_path(tmp_path, monkeypatch):
    """User must not be able to redirect output outside the reports dir."""
    from web import app as web_app

    graph = _target_graph()
    monkeypatch.setattr(web_app, "build_graph_from_repo", lambda repo_path: graph)

    repo = _repo(tmp_path)
    evil = tmp_path / "evil.md"
    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread/export",
            data={
                "repo_path": str(repo),
                "query": "x",
                # Attempted overrides — all must be ignored.
                "output_path": str(evil),
                "path": str(evil),
                "filename": "../../../evil.md",
            },
        )

    data = response.get_json()
    assert response.status_code == 200, data
    assert not evil.exists()

    out_path = Path(data["path"])
    parts = out_path.parts
    assert "reports" in parts and "evidence_spread" in parts
    # Filename component should not contain traversal.
    assert ".." not in out_path.name
    assert "evil" not in out_path.name.lower()


def test_export_route_empty_result_still_writes_report(tmp_path, monkeypatch):
    from web import app as web_app

    monkeypatch.setattr(
        web_app, "build_graph_from_repo", lambda repo_path: ProgramGraph()
    )

    repo = _repo(tmp_path)
    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread/export",
            data={"repo_path": str(repo), "query": ""},
        )

    data = response.get_json()
    assert response.status_code == 200, data
    assert data["ok"] is True
    out_path = Path(data["path"])
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "Evidence Spread Report" in text
    assert GUARDRAIL in text


def test_existing_evidence_spread_route_unchanged(tmp_path, monkeypatch):
    """The non-export route should keep returning JSON with no file writes."""
    from web import app as web_app

    graph = _target_graph()
    monkeypatch.setattr(web_app, "build_graph_from_repo", lambda repo_path: graph)

    repo = _repo(tmp_path)
    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread",
            data={
                "repo_path": str(repo),
                "query": "optimize fib",
                "target_node": "target.py::fib",
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert "path" not in data  # export-only field
