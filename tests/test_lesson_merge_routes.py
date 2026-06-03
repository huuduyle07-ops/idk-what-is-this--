import json
import pytest
from core import lesson_store


def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(
        lesson_store, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent"
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)


def _candidate():
    return {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": [],
    }


# ── GET /lessons/duplicates ──────────────────────────────────────────────────

def test_duplicates_route_returns_empty_for_no_lessons(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    resp = web_app.app.test_client().get("/lessons/duplicates")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["groups"] == []


def test_duplicates_route_groups_same_source_report(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    lesson_store.save_candidate_lesson(
        _candidate(), source_report="r1.json", case_name="case_x", title="Lesson A"
    )
    lesson_store.save_candidate_lesson(
        _candidate(), source_report="r1.json", case_name="case_x", title="Lesson B"
    )
    resp = web_app.app.test_client().get("/lessons/duplicates")
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["groups"]) == 1
    assert len(body["groups"][0]["lesson_ids"]) == 2


# ── POST /lessons/merge/preview ──────────────────────────────────────────────

def test_merge_preview_route_returns_preview(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate(), title="A")
    b = lesson_store.save_candidate_lesson(_candidate(), title="B")
    resp = web_app.app.test_client().post(
        "/lessons/merge/preview",
        json={"lesson_ids": [a["id"], b["id"]]},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["preview"]["status"] == "candidate"
    assert body["preview"]["active_knowledge_allowed"] is False


def test_merge_preview_route_requires_two_ids(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    resp = web_app.app.test_client().post(
        "/lessons/merge/preview",
        json={"lesson_ids": [a["id"]]},
    )
    assert resp.status_code == 400


def test_merge_preview_route_no_file_writes(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    b = lesson_store.save_candidate_lesson(_candidate())
    before = set((tmp_path / ".agent" / "lessons").rglob("*.json"))
    web_app.app.test_client().post(
        "/lessons/merge/preview",
        json={"lesson_ids": [a["id"], b["id"]]},
    )
    after = set((tmp_path / ".agent" / "lessons").rglob("*.json"))
    assert before == after


# ── POST /lessons/merge/create ───────────────────────────────────────────────

def test_merge_create_route_creates_candidate(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    b = lesson_store.save_candidate_lesson(_candidate())
    resp = web_app.app.test_client().post(
        "/lessons/merge/create",
        json={"lesson_ids": [a["id"], b["id"]], "title": "Merged", "summary": "", "tags": []},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["lesson"]["status"] == "candidate"
    assert set(body["superseded"]) == {a["id"], b["id"]}


def test_merge_create_route_rejects_active_without_confirm(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    b = lesson_store.save_candidate_lesson(_candidate())
    lesson_store.promote_lesson(a["id"])
    resp = web_app.app.test_client().post(
        "/lessons/merge/create",
        json={"lesson_ids": [a["id"], b["id"]], "title": "M", "summary": "", "tags": []},
    )
    assert resp.status_code == 400
    assert "confirm_supersede_active" in resp.get_json()["error"]


def test_merge_create_route_requires_title(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    b = lesson_store.save_candidate_lesson(_candidate())
    resp = web_app.app.test_client().post(
        "/lessons/merge/create",
        json={"lesson_ids": [a["id"], b["id"]], "title": "", "summary": "", "tags": []},
    )
    assert resp.status_code == 400


# ── POST /lessons/archive ─────────────────────────────────────────────────────

def test_archive_route_sets_flag(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    resp = web_app.app.test_client().post(
        "/lessons/archive",
        json={"lesson_id": a["id"]},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["lesson"]["archived"] is True


def test_archive_route_rejects_active(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    a = lesson_store.save_candidate_lesson(_candidate())
    lesson_store.promote_lesson(a["id"])
    resp = web_app.app.test_client().post(
        "/lessons/archive",
        json={"lesson_id": a["id"]},
    )
    assert resp.status_code == 400


def test_archive_route_404_for_unknown(tmp_path, monkeypatch):
    from web import app as web_app
    _redirect(tmp_path, monkeypatch)
    resp = web_app.app.test_client().post(
        "/lessons/archive",
        json={"lesson_id": "20240101_000000_000000"},
    )
    assert resp.status_code == 404
