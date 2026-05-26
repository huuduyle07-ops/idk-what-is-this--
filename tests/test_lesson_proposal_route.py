from pathlib import Path

from core import lesson_store


def _candidate() -> dict:
    return {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_plan",
        "rollback_happened": False,
        "changed_files": ["pricing.py"],
        "diff_stats": {"added": 2, "removed": 1},
        "language": "python",
        "category": "logic_validation",
        "summary": "Fix the discount validation logic.",
    }


def _redirect_lesson_store(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        lesson_store,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)


def test_lesson_proposal_route_reads_proposal_md(tmp_path, monkeypatch):
    from web import app as web_app

    _redirect_lesson_store(tmp_path, monkeypatch)
    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)

    proposal_dir = tmp_path / ".agent" / "proposals" / "20260517_120000" / "01-test"
    proposal_dir.mkdir(parents=True)
    (proposal_dir / "proposal.md").write_text(
        "# Patch Proposal\n\nThis is the idea from the proposal.",
        encoding="utf-8",
    )

    lesson = lesson_store.save_candidate_lesson(
        _candidate(),
        source="patch_proposal",
        source_report=str(proposal_dir),
        title="Patch proposal: python_discount_validation",
        summary="Fix the discount validation logic.",
    )

    resp = web_app.app.test_client().get(
        "/lessons/proposal",
        query_string={"lesson_id": lesson["id"]},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["lesson_id"] == lesson["id"]
    assert body["proposal_path"].endswith("proposal.md")
    assert "idea from the proposal" in body["content"]


def test_lesson_proposal_route_rejects_source_report_outside_proposals(
    tmp_path, monkeypatch
):
    from web import app as web_app

    _redirect_lesson_store(tmp_path, monkeypatch)
    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "proposal.md").write_text("# Not allowed", encoding="utf-8")

    lesson = lesson_store.save_candidate_lesson(
        _candidate(),
        source="patch_proposal",
        source_report=str(outside_dir),
        title="Unsafe proposal source",
        summary="Should not read outside the proposal artifact root.",
    )

    resp = web_app.app.test_client().get(
        "/lessons/proposal",
        query_string={"lesson_id": lesson["id"]},
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "outside allowed proposal roots" in body["error"]


def test_memory_lesson_list_exposes_scope_fields_and_badge_markup(
    tmp_path, monkeypatch
):
    from web import app as web_app

    _redirect_lesson_store(tmp_path, monkeypatch)
    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    global_lesson = lesson_store.save_candidate_lesson(
        _candidate(),
        source="benchmark_report",
        scope="global",
        title="Global lesson",
    )
    repo_lesson = lesson_store.save_candidate_lesson(
        _candidate(),
        source="proposal_artifact",
        repo_path=str(repo),
        scope="repo",
        title="Repo lesson",
    )

    client = web_app.app.test_client()
    resp = client.get("/lessons/list", query_string={"repo_path": str(repo)})

    assert resp.status_code == 200
    body = resp.get_json()
    ids = {lesson["id"] for lesson in body["lessons"]}
    assert ids == {global_lesson["id"], repo_lesson["id"]}
    by_id = {lesson["id"]: lesson for lesson in body["lessons"]}
    assert by_id[global_lesson["id"]]["scope"] == "global"
    assert by_id[global_lesson["id"]]["repo_scope_id"] is None
    assert by_id[repo_lesson["id"]]["scope"] == "repo"
    assert by_id[repo_lesson["id"]]["repo_scope_id"]

    html = client.get("/").get_data(as_text=True)
    assert "lesson-scope-badge" in html
    assert "repo:&quot;" in html or "repo:" in html
