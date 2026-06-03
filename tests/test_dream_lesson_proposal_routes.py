"""Tests for POST /dream/create-lesson-candidate and POST /dream/create-proposal."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

import config as app_config


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_run(tmp_path, date="2026-06-02", run="010203-run"):
    """Create a minimal run dir with one item in list.json."""
    dreams = tmp_path / "dreams"
    report_dir = dreams / date / run
    report_dir.mkdir(parents=True)
    item_dir_name = "01-slow-case"
    (report_dir / item_dir_name).mkdir()
    items = [{
        "idx": 1,
        "kind": "bug",
        "title": "Slow case: x",
        "hint": "loop is O(n^2)",
        "status": "planned_no_patch",
        "item_dir_name": item_dir_name,
        "case_name": "python_slow",
        "language": "python",
        "category": "performance",
    }]
    (report_dir / "list.json").write_text(
        json.dumps({"items": items}), encoding="utf-8"
    )
    return dreams, report_dir, item_dir_name


def test_create_lesson_candidate_returns_candidate_status(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    dreams, report_dir, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)

    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    resp = client.post("/dream/create-lesson-candidate", data={
        "repo_path": repo,
        "date": "2026-06-02",
        "run": "010203-run",
        "item_idx": "1",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("ok") is True
    assert body.get("status") == "candidate"
    assert body.get("active_knowledge_allowed") is False


def test_create_lesson_candidate_never_auto_promotes(client, tmp_path, monkeypatch):
    """Even if LESSON_AUTO_ACTIVE is True, result must be candidate."""
    import core.dream_artifacts as da
    dreams, report_dir, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)
    monkeypatch.setattr(app_config, "LESSON_AUTO_ACTIVE", True)

    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    resp = client.post("/dream/create-lesson-candidate", data={
        "repo_path": repo,
        "date": "2026-06-02",
        "run": "010203-run",
        "item_idx": "1",
    })
    body = resp.get_json()
    assert body.get("ok") is True
    assert body.get("active_knowledge_allowed") is False
    assert body.get("status") == "candidate"


def test_create_proposal_writes_proposal_md_and_json(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    dreams, _, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)

    # Redirect proposal root to tmp so the test is hermetic.
    fake_proposal_root = tmp_path / "proposals"
    import web.app as webapp
    monkeypatch.setattr(webapp, "_DREAM_PROPOSAL_ROOT", fake_proposal_root)

    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    resp = client.post("/dream/create-proposal", data={
        "repo_path": repo,
        "date": "2026-06-02",
        "run": "010203-run",
        "item_idx": "1",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("ok") is True
    proposal_dir = Path(body["proposal_dir"])
    assert (proposal_dir / "proposal.md").is_file()
    assert (proposal_dir / "proposal.json").is_file()
    assert (proposal_dir / "item.json").is_file()


def test_create_proposal_no_model_call(client, tmp_path, monkeypatch):
    """proposal.md content must be purely derived from item data — marker phrase present."""
    import core.dream_artifacts as da
    dreams, _, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)
    fake_proposal_root = tmp_path / "proposals"
    import web.app as webapp
    monkeypatch.setattr(webapp, "_DREAM_PROPOSAL_ROOT", fake_proposal_root)

    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    client.post("/dream/create-proposal", data={
        "repo_path": repo,
        "date": "2026-06-02",
        "run": "010203-run",
        "item_idx": "1",
    })
    # Find the written proposal.md
    md_files = list(fake_proposal_root.rglob("proposal.md"))
    assert len(md_files) == 1
    text = md_files[0].read_text(encoding="utf-8")
    assert "human review required" in text.lower()
    assert "Slow case: x" in text  # title from item


def test_create_lesson_candidate_missing_item_idx(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    dreams, _, _ = _make_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda repo_path: dreams)
    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    resp = client.post("/dream/create-lesson-candidate", data={
        "repo_path": repo, "date": "2026-06-02", "run": "010203-run",
    })
    assert resp.status_code == 400
