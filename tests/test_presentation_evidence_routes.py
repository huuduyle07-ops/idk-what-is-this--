"""Flask route tests for the Phase 12.8a presentation evidence pack helpers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


EXPECTED_FILES = [
    "00_evidence_index.md",
    "01_full_suite_summary.md",
    "02_held_out_suite_summary.md",
    "03_held_out_watchlist.md",
    "04_patch_minimality_experiment.md",
    "05_same_suite_trends.md",
    "06_graph_weight_explainability.md",
]


@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    return root


def test_build_route_generates_expected_json(client, project):
    resp = client.post(
        "/presentation/evidence/build",
        data={"repo_path": str(project)},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert set(body["files"]) == set(EXPECTED_FILES)
    assert Path(body["output_dir"]).is_dir()
    for name in EXPECTED_FILES:
        assert (Path(body["output_dir"]) / name).exists()


def test_list_route_returns_generated_markdown_files(client, project):
    client.post("/presentation/evidence/build", data={"repo_path": str(project)})

    resp = client.get(
        f"/presentation/evidence/list?repo_path={project}"
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    names = [entry["name"] for entry in body["files"]]
    assert set(names) == set(EXPECTED_FILES)
    for entry in body["files"]:
        assert entry["name"].endswith(".md")
        assert isinstance(entry["size"], int) and entry["size"] > 0


def test_file_route_reads_valid_evidence_markdown(client, project):
    client.post("/presentation/evidence/build", data={"repo_path": str(project)})

    resp = client.get(
        "/presentation/evidence/file"
        f"?repo_path={project}&name=00_evidence_index.md"
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["name"] == "00_evidence_index.md"
    assert "Evidence Index" in body["content"]


@pytest.mark.parametrize(
    "bad_name",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32\\cmd.exe",
        "subdir/00_evidence_index.md",
        "subdir\\file.md",
        "/etc/hosts",
        "00_evidence_index.md/../secret.md",
    ],
)
def test_file_route_blocks_path_traversal(client, project, bad_name):
    client.post("/presentation/evidence/build", data={"repo_path": str(project)})

    resp = client.get(
        "/presentation/evidence/file",
        query_string={"repo_path": str(project), "name": bad_name},
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "name" in body["error"].lower() or "path" in body["error"].lower()


@pytest.mark.parametrize(
    "bad_name",
    ["evidence.json", "evidence.txt", "evidence", "00_evidence_index.MD.exe"],
)
def test_file_route_blocks_non_md_files(client, project, bad_name):
    client.post("/presentation/evidence/build", data={"repo_path": str(project)})

    resp = client.get(
        "/presentation/evidence/file",
        query_string={"repo_path": str(project), "name": bad_name},
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_build_route_does_not_call_benchmarks_or_models(client, project, monkeypatch):
    called: list[str] = []

    from core import benchmark_web

    monkeypatch.setattr(
        benchmark_web,
        "start_benchmark_run_async",
        lambda *a, **k: called.append("benchmark_run") or {"ok": True},
    )
    from agents import gemini_client

    monkeypatch.setattr(
        gemini_client,
        "run_gemini_request",
        lambda *a, **k: called.append("gemini") or {},
    )

    resp = client.post(
        "/presentation/evidence/build", data={"repo_path": str(project)}
    )

    assert resp.status_code == 200
    assert called == []


def test_missing_evidence_folder_gives_friendly_empty_result(client, project):
    resp = client.get(
        f"/presentation/evidence/list?repo_path={project}"
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["files"] == []
    assert body.get("exists") is False


def test_build_does_not_modify_existing_benchmark_reports(client, project):
    bench = project / ".agent" / "benchmarks"
    bench.mkdir(parents=True)
    report = bench / "benchmark_report_1.json"
    report.write_text(
        json.dumps(
            {
                "total": 31,
                "passed": 31,
                "failed": 0,
                "flaky": 0,
                "results": [{"name": "ts_nested_dispatch_root_cause", "success": True}],
                "created_at": "2026-05-24T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    before = report.read_text(encoding="utf-8")

    resp = client.post(
        "/presentation/evidence/build", data={"repo_path": str(project)}
    )

    assert resp.status_code == 200
    assert report.read_text(encoding="utf-8") == before


def test_build_route_rejects_missing_repo_path(client):
    resp = client.post("/presentation/evidence/build", data={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_file_route_renders_markdown_to_html_when_as_html(client, project):
    client.post("/presentation/evidence/build", data={"repo_path": str(project)})

    resp = client.get(
        "/presentation/evidence/file",
        query_string={
            "repo_path": str(project),
            "name": "04_patch_minimality_experiment.md",
            "as": "html",
        },
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    # raw content still present so the client can fall back if needed
    assert "content" in body
    # HTML rendering present and includes proper tags (not raw pipe tables)
    assert "html" in body
    html = body["html"]
    # The empty-state placeholder for this file still rounds-trips to HTML.
    # Any header in the source becomes <h1>; just confirm we got real HTML.
    assert "<h1>" in html or "<p>" in html

