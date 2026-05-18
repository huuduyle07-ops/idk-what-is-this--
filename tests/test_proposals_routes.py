"""Flask client tests for the Phase 5 Polish promote-to-lesson routes:
/proposals/list, /proposals/view, /proposals/promote.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import lesson_store
from scripts import create_lesson_from_proposal as cl
from scripts import run_patch_proposal_queue


def _write_artifacts(
    item_dir: Path,
    *,
    validation_ok: bool = True,
    apply_success: bool = True,
    changed_files=None,
    case_name: str = "python_discount_validation",
    language: str = "python",
    category: str = "logic_validation",
    summary: str = "Fix the discount validation logic.",
    omit: tuple[str, ...] = (),
    write_proposal_md: bool = True,
) -> None:
    item_dir.mkdir(parents=True, exist_ok=True)
    changed_files = list(changed_files or ["pricing.py"])
    files = {
        "item.json": {
            "kind": "bug",
            "case_name": case_name,
            "language": language,
            "category": category,
        },
        "case.json": {
            "name": case_name,
            "language": language,
            "category": category,
            "validation_command": "python main.py",
            "expected_changed_files": changed_files,
            "forbidden_changed_files": ["main.py"],
        },
        "patch_proposal.json": {
            "summary": summary,
            "patch_candidate": None,
            "patch_plan": [
                {"op": "replace_snippet", "relative_path": f,
                 "target_snippet": "x", "patched_snippet": "y"}
                for f in changed_files
            ],
            "needs_human_review": False,
        },
        "apply_result.json": {
            "success": apply_success,
            "applied_ops": [
                {"op": "replace_snippet", "relative_path": f,
                 "target_snippet": "x", "patched_snippet": "y"}
                for f in changed_files
            ],
            "diffs": [
                f"--- a/{f}\n+++ b/{f}\n@@ -1,1 +1,2 @@\n-old\n+new1\n+new2\n"
                for f in changed_files
            ],
            "rollback_performed": False,
            "failed_op_index": None,
            "failed_op": None,
            "error": None,
        },
        "validation.json": {
            "ok": validation_ok,
            "validation_ok": validation_ok,
            "command": "python main.py",
            "duration_sec": 1.2,
            "output": "OK" if validation_ok else "FAIL",
        },
    }
    for name, data in files.items():
        if name in omit:
            continue
        (item_dir / name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )
    if write_proposal_md:
        (item_dir / "proposal.md").write_text(
            f"# Proposal: {case_name}\n\n{summary}\n", encoding="utf-8",
        )


@pytest.fixture
def proposals_repo(tmp_path, monkeypatch):
    """Isolated .agent/proposals/ tree for the Flask client."""
    monkeypatch.setattr(
        lesson_store,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)

    proposals_root = tmp_path / ".agent" / "proposals"
    proposals_root.mkdir(parents=True, exist_ok=True)

    # Redirect both the script's default proposals root AND the queue script's
    # PROPOSAL_ROOT module-level constant (which /proposals/list reads).
    monkeypatch.setattr(cl, "_default_proposals_root", lambda: proposals_root)
    monkeypatch.setattr(run_patch_proposal_queue, "PROPOSAL_ROOT", proposals_root)

    return tmp_path


@pytest.fixture
def client(proposals_repo):
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --- /proposals/list -------------------------------------------------------

def test_list_empty_when_no_proposals(client, proposals_repo):
    # Wipe the proposals root contents entirely.
    proposals_root = proposals_repo / ".agent" / "proposals"
    for child in proposals_root.iterdir():
        if child.is_dir():
            import shutil
            shutil.rmtree(child)
    resp = client.get("/proposals/list")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["runs"] == []


def test_list_returns_recent_runs(client, proposals_repo):
    item_a = proposals_repo / ".agent" / "proposals" / "20260518_100000" / "01-case-a"
    item_b = proposals_repo / ".agent" / "proposals" / "20260518_120000" / "01-case-b"
    _write_artifacts(item_a, case_name="case_a")
    _write_artifacts(item_b, case_name="case_b", validation_ok=False)

    resp = client.get("/proposals/list")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["runs"]) == 2
    # Newer run first.
    assert body["runs"][0]["run_id"] == "20260518_120000"
    assert body["runs"][0]["items"][0]["case_name"] == "case_b"
    assert body["runs"][0]["items"][0]["validation_ok"] is False
    assert body["runs"][0]["items"][0]["apply_success"] is True
    assert body["runs"][0]["items"][0]["has_proposal_md"] is True
    assert body["runs"][1]["items"][0]["case_name"] == "case_a"


def test_list_ignores_unreadable_jsons(client, proposals_repo):
    item = proposals_repo / ".agent" / "proposals" / "20260518_100000" / "01-broken"
    item.mkdir(parents=True)
    (item / "item.json").write_text("not json", encoding="utf-8")
    resp = client.get("/proposals/list")
    assert resp.status_code == 200
    body = resp.get_json()
    # Item still appears, just with None fields.
    assert body["runs"][0]["items"][0]["case_name"] is None


# --- /proposals/view -------------------------------------------------------

def test_view_returns_proposal_md(client, proposals_repo):
    item = proposals_repo / ".agent" / "proposals" / "20260518_100000" / "01-case"
    _write_artifacts(item, summary="here is what changed")
    resp = client.get("/proposals/view", query_string={"proposal_dir": str(item)})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "here is what changed" in body["content"]
    assert body["proposal_path"].endswith("proposal.md")


def test_view_rejects_path_outside_proposals(client, proposals_repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    resp = client.get("/proposals/view", query_string={"proposal_dir": str(outside)})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_view_handles_missing_proposal_md(client, proposals_repo):
    item = proposals_repo / ".agent" / "proposals" / "20260518_100000" / "01-no-md"
    _write_artifacts(item, write_proposal_md=False)
    resp = client.get("/proposals/view", query_string={"proposal_dir": str(item)})
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["ok"] is False


# --- /proposals/promote ----------------------------------------------------

def test_promote_validated_proposal_creates_candidate(client, proposals_repo):
    item = proposals_repo / ".agent" / "proposals" / "20260518_100000" / "01-good"
    _write_artifacts(item, case_name="python_off_by_one")
    resp = client.post(
        "/proposals/promote",
        data={"proposal_dir": str(item)},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["lesson_id"]
    assert body["promotion"] in {"auto_approved", "needs_human_review", "blocked"}


def test_promote_failed_proposal_refused_by_default(client, proposals_repo):
    item = proposals_repo / ".agent" / "proposals" / "20260518_100000" / "01-fail"
    _write_artifacts(item, validation_ok=False)
    resp = client.post(
        "/proposals/promote",
        data={"proposal_dir": str(item)},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is False
    assert body["refused"] is True


def test_promote_allow_failed_creates_blocked_lesson(client, proposals_repo):
    item = proposals_repo / ".agent" / "proposals" / "20260518_100000" / "01-fail-allow"
    _write_artifacts(item, validation_ok=False)
    resp = client.post(
        "/proposals/promote",
        data={"proposal_dir": str(item), "allow_failed": "true"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    # lesson_quality will normally block this because validation_ok=False.
    assert body["promotion"] == "blocked"


def test_promote_rejects_path_outside_proposals(client, proposals_repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    resp = client.post(
        "/proposals/promote",
        data={"proposal_dir": str(outside)},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_promote_missing_artifacts_returns_404(client, proposals_repo):
    item = proposals_repo / ".agent" / "proposals" / "20260518_100000" / "01-empty"
    item.mkdir(parents=True)
    resp = client.post(
        "/proposals/promote",
        data={"proposal_dir": str(item)},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
