"""Web route guards for Phase 4.7e Dream research references."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from core import dream_references


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    refs_root = dream_references.references_root(str(r))
    if refs_root.exists():
        for sub in refs_root.iterdir():
            if sub.is_dir():
                for f in sub.iterdir():
                    try:
                        f.unlink()
                    except OSError:
                        pass
                try:
                    sub.rmdir()
                except OSError:
                    pass
    yield r


def test_import_route_creates_reference_and_list_route_returns_it(client, repo):
    resp = client.post(
        "/dream/references/import",
        json={
            "repo_path": str(repo),
            "topic": "Graph role classification",
            "raw_input": "Discord notes claim graph roles might help search.",
            "source_type": "zapier_discord",
            "sources": [{"title": "Thread summary", "url": "https://example.test/t"}],
        },
    )
    body = resp.get_json()
    assert body["ok"] is True
    assert body["reference_id"]
    assert body["markdown_path"].endswith("reference.md")
    assert body["json_path"].endswith("reference.json")
    assert body["summary"].startswith("Imported notes claim")

    listed = client.get(f"/dream/references/list?repo_path={repo}").get_json()
    refs = listed["references"]
    assert refs
    assert refs[0]["reference_id"] == body["reference_id"]
    assert refs[0]["topic"] == "Graph role classification"
    assert refs[0]["markdown_path"] == body["markdown_path"]


def test_import_route_rejects_empty_topic(client, repo):
    resp = client.post(
        "/dream/references/import",
        json={
            "repo_path": str(repo),
            "topic": " ",
            "raw_input": "notes",
        },
    )
    body = resp.get_json()
    assert body["ok"] is False
    assert "topic" in body["error"].lower()


def test_list_route_returns_newest_first_and_ignores_malformed_folders(client, repo):
    first = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="First",
        raw_input="Notes claim first.",
    )
    time.sleep(1.1)
    second = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Second",
        raw_input="Notes claim second.",
    )

    refs_root = dream_references.references_root(str(repo))
    (refs_root / "not-a-reference").mkdir(parents=True, exist_ok=True)
    broken = refs_root / "20991231-000000-broken"
    broken.mkdir(parents=True, exist_ok=True)
    (broken / "reference.json").write_text("{ not json", encoding="utf-8")

    resp = client.get(f"/dream/references/list?repo_path={repo}")
    body = resp.get_json()
    ids = [r["reference_id"] for r in body["references"]]
    assert ids.index(second.reference_id) < ids.index(first.reference_id)
    assert "not-a-reference" not in ids
    assert "20991231-000000-broken" not in ids


def test_file_route_serves_only_reference_markdown_and_json(client, repo):
    ref = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Fetch me",
        raw_input="Notes claim file routes should be narrow.",
    )

    md_resp = client.get(
        "/dream/references/file"
        f"?repo_path={repo}&reference_id={ref.reference_id}&file=reference.md"
    )
    md_body = md_resp.get_json()
    assert md_body["ok"] is True
    assert "Dream Research Reference" in md_body["content"]

    json_resp = client.get(
        "/dream/references/file"
        f"?repo_path={repo}&reference_id={ref.reference_id}&file=reference.json"
    )
    json_body = json_resp.get_json()
    assert json_body["ok"] is True
    assert json.loads(json_body["content"])["reference_id"] == ref.reference_id


@pytest.mark.parametrize("file_name", [
    "../reference.md",
    "..\\reference.md",
    "raw.txt",
    "reference.md.bak",
])
def test_file_route_blocks_path_traversal_and_unlisted_files(client, repo, file_name):
    ref = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Traversal",
        raw_input="Notes claim traversal should fail.",
    )
    resp = client.get(
        "/dream/references/file"
        f"?repo_path={repo}&reference_id={ref.reference_id}&file={file_name}"
    )
    body = resp.get_json()
    assert body.get("ok") is not True
    assert body.get("error")


@pytest.mark.parametrize("reference_id", [
    "../",
    "..",
    "no-such-reference",
    "20260527-000000-../../escape",
])
def test_file_route_blocks_bad_reference_id(client, repo, reference_id):
    dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Anchor",
        raw_input="Notes claim bad ids should fail.",
    )
    resp = client.get(
        "/dream/references/file"
        f"?repo_path={repo}&reference_id={reference_id}&file=reference.md"
    )
    body = resp.get_json()
    assert body.get("ok") is not True


def test_routes_module_has_no_forbidden_imports():
    from web.routes import dream_references_routes

    src = Path(dream_references_routes.__file__).read_text(encoding="utf-8").lower()
    forbidden = [
        "subprocess",
        "patch_engine",
        "patch_plan_executor",
        "patch_planner",
        "run_patch_plan",
        "run_benchmarks",
        "benchmark_runner",
        "anthropic",
        "openai",
        "google.genai",
        "litellm",
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "socket",
    ]
    for needle in forbidden:
        assert needle.lower() not in src, (
            f"dream_references_routes leaked a forbidden import: {needle}"
        )

