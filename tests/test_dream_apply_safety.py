from __future__ import annotations

import json
import subprocess

import pytest


def test_dream_apply_blocks_unsafe_patch_plan_before_apply(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    report_dir = tmp_path / "dreams" / "2026-05-21" / "010203-run"
    item_dir = report_dir / "01-unsafe-env-edit"
    item_dir.mkdir(parents=True)
    (report_dir / "list.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "idx": 1,
                        "kind": "bug",
                        "title": "Unsafe env edit",
                        "status": "ready_to_apply",
                        "item_dir_name": item_dir.name,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (item_dir / "patch_plan.json").write_text(
        json.dumps(
            [
                {
                    "op": "replace_snippet",
                    "relative_path": ".env",
                    "target_snippet": "TOKEN=old",
                    "patched_snippet": "TOKEN=new",
                }
            ]
        ),
        encoding="utf-8",
    )

    import web.app as web_app

    apply_called = False

    def fake_apply(*_args, **_kwargs):
        nonlocal apply_called
        apply_called = True
        return {"success": True, "message": "should not apply"}

    git_called = False

    def fake_subprocess_run(*_args, **_kwargs):
        nonlocal git_called
        git_called = True
        return subprocess.CompletedProcess(args=[], returncode=0)

    monkeypatch.setattr(web_app.dream_artifacts, "latest_report_dir", lambda _repo: report_dir)
    monkeypatch.setattr(web_app.dream_artifacts, "dreams_root", lambda _repo: report_dir.parent.parent)
    monkeypatch.setattr(web_app, "inspect_repo_inventory", lambda _repo: {"primary_language": "python"})
    monkeypatch.setattr(web_app, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    web_app.app.config["TESTING"] = True
    client = web_app.app.test_client()
    reviewed = client.get("/dream/list", query_string={"repo_path": str(repo)}).get_json()
    binding = reviewed["items"][0]["review_binding"]
    resp = client.post(
        "/dream/apply",
        data={"repo_path": str(repo), "selection": "1", "review_bindings": json.dumps([binding])},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    result = body["results"][0]
    assert result["status"] == "blocked_by_safety"
    assert "Dream apply blocked by safety gate" in result["message"]
    assert result["patch_safety"]["ok"] is False
    assert result["patch_safety"]["blocked_paths"][0]["path"] == ".env"
    assert apply_called is False
    assert git_called is False
