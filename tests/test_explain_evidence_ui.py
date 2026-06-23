"""Phase 12.13f - Explainability evidence pack + UI polish (explain-only).

Covers:
  * the new 07_graph_attraction_explainability.md evidence-pack file,
  * the evidence index linking it,
  * graceful handling when no attraction report exists,
  * a read-only UI/debug route that renders the explain-only sections
    (Evidence Confidence, Graph Attraction / Repulsion, Related Notes / Lessons),
  * no model/API calls and no forbidden imports.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import build_presentation_evidence_pack as pack

ATTRACTION_FILE = "07_graph_attraction_explainability.md"


# ----------------------------- evidence pack -------------------------------

def test_pack_includes_graph_attraction_file_when_report_exists(tmp_path):
    project = tmp_path / "project"
    report_dir = project / ".agent" / "reports" / "graph_attraction"
    report_dir.mkdir(parents=True)
    (report_dir / "latest.md").write_text(
        "# Graph Attraction / Repulsion\n\nSENTINEL_ATTRACTION_BODY\n",
        encoding="utf-8",
    )

    result = pack.build_evidence_pack(project)
    md_path = result["output_dir"] / ATTRACTION_FILE

    assert md_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    assert "SENTINEL_ATTRACTION_BODY" in text
    assert "explain-only" in text.lower()


def test_pack_attraction_file_handles_missing_report_gracefully(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md_path = result["output_dir"] / ATTRACTION_FILE

    assert md_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    # Placeholder must be non-empty, explain-only, and not crash the pack.
    assert text.strip()
    assert "explain-only" in text.lower()
    assert "attraction" in text.lower()


def test_evidence_index_links_graph_attraction_file(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    index = (result["output_dir"] / "00_evidence_index.md").read_text(encoding="utf-8")

    assert f"]({ATTRACTION_FILE})" in index


def test_pack_does_not_modify_source_attraction_report(tmp_path):
    project = tmp_path / "project"
    report_dir = project / ".agent" / "reports" / "graph_attraction"
    report_dir.mkdir(parents=True)
    source = report_dir / "latest.md"
    source.write_text("# Graph Attraction\n\noriginal\n", encoding="utf-8")
    before = source.read_text(encoding="utf-8")

    pack.build_evidence_pack(project)

    assert source.read_text(encoding="utf-8") == before


# --------------------------------- UI route --------------------------------

@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


def _repo_with_graph(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "fib.py").write_text(
        "def fib(n):\n    return helper(n)\n\n\ndef helper(n):\n    return n\n",
        encoding="utf-8",
    )
    return repo


def test_explainability_view_renders_explain_only_sections(client, tmp_path, monkeypatch):
    from web import app as web_app

    # No model calls allowed.
    monkeypatch.setattr(
        web_app,
        "run_gemini_request",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("model call not allowed")),
        raising=False,
    )

    repo = _repo_with_graph(tmp_path)
    resp = client.get(
        "/graph/explainability/view",
        query_string={"repo_path": str(repo), "query": "fib", "as": "html"},
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["ok"] is True

    md = body["markdown"]
    assert "## Evidence Confidence" in md
    assert "## Graph Attraction / Repulsion" in md
    assert "Related Notes" in md
    # explain-only guardrails carried through
    assert "explain-only" in md.lower()

    # HTML rendering present and structural.
    assert "html" in body
    assert "<h2" in body["html"] or "<table" in body["html"] or "<p>" in body["html"]

    # Declares which explain-only sections it surfaced.
    assert "Evidence Confidence" in body["sections"]
    assert "Graph Attraction / Repulsion" in body["sections"]
    assert "Related Notes / Lessons" in body["sections"]


def test_explainability_view_requires_valid_repo_path(client, tmp_path):
    missing = tmp_path / "nope"
    resp = client.get(
        "/graph/explainability/view",
        query_string={"repo_path": str(missing)},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_explainability_view_does_not_call_models(client, tmp_path, monkeypatch):
    from web import app as web_app

    called: list[str] = []
    monkeypatch.setattr(
        web_app,
        "run_gemini_request",
        lambda *a, **k: called.append("gemini") or "",
        raising=False,
    )

    repo = _repo_with_graph(tmp_path)
    resp = client.get(
        "/graph/explainability/view",
        query_string={"repo_path": str(repo), "query": "fib"},
    )

    assert resp.status_code == 200
    assert called == []


def test_direct_run_block_starts_after_explainability_route_registration():
    from web import app as web_app

    rules = {rule.rule for rule in web_app.app.url_map.iter_rules()}
    assert "/graph/explainability/view" in rules

    source = Path(web_app.__file__).read_text(encoding="utf-8")
    route_index = source.index('@app.route("/graph/explainability/view"')
    main_index = source.index('if __name__ == "__main__":')

    assert route_index < main_index
    assert "@app.route(" not in source[main_index:]
    assert "run_web_app(app, debug=False)" in source[main_index:]


# ------------------------------- guardrails --------------------------------

def test_builder_has_no_forbidden_imports():
    source = Path(pack.__file__).read_text(encoding="utf-8")
    for forbidden in ("patching", "agents", "benchmarks.run_benchmarks"):
        assert f"import {forbidden}" not in source, forbidden
        assert f"from {forbidden}" not in source, forbidden
