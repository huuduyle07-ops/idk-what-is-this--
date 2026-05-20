from __future__ import annotations


def test_patch_plan_routes_are_registered_from_blueprint():
    from web.app import app

    assert "patch_routes" in app.blueprints
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "patch_routes.apply_patch" in endpoints
    assert "patch_routes.test_patch" in endpoints
    assert "patch_routes.test_patch_plan" in endpoints
    assert "patch_routes.apply_patch_plan_route" in endpoints


def test_patch_plan_routes_preserve_safe_minimal_refusals():
    from web.app import app

    app.config["TESTING"] = True
    client = app.test_client()

    dry_run = client.post(
        "/test_patch_plan",
        data={"patch_style": "safe_minimal", "patch": "{}"},
    )
    apply = client.post(
        "/apply_patch_plan",
        data={"patch_style": "safe_minimal", "patch": "{}"},
    )

    assert dry_run.status_code == 200
    assert apply.status_code == 200
    assert dry_run.get_json()["success"] is False
    assert apply.get_json()["success"] is False
    assert "safe_minimal mode forbids patch_plan" in dry_run.get_json()["message"]
    assert "safe_minimal mode forbids patch_plan" in apply.get_json()["message"]


def test_test_patch_blocks_env_target_with_patch_safety(tmp_path):
    from web.app import app

    repo = tmp_path / "repo"
    repo.mkdir()
    patch = {
        "relative_path": ".env",
        "target_snippet": "TOKEN=old",
        "patched_snippet": "TOKEN=new",
    }

    app.config["TESTING"] = True
    client = app.test_client()
    resp = client.post(
        "/test_patch",
        data={"repo_path": str(repo), "patch": __import__("json").dumps(patch)},
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["success"] is False
    assert "Patch blocked by safety gate" in body["message"]
    assert body["patch_safety"]["ok"] is False
    assert body["patch_safety"]["blocked_paths"][0]["path"] == ".env"


def test_apply_patch_blocks_traversal_with_patch_safety(tmp_path):
    from web.app import app

    repo = tmp_path / "repo"
    repo.mkdir()
    patch = {
        "relative_path": "../outside.py",
        "target_snippet": "old",
        "patched_snippet": "new",
    }

    app.config["TESTING"] = True
    client = app.test_client()
    resp = client.post(
        "/apply_patch",
        data={"repo_path": str(repo), "patch": __import__("json").dumps(patch)},
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["success"] is False
    assert "Patch blocked by safety gate" in body["message"]
    assert body["patch_safety"]["ok"] is False
    assert body["patch_safety"]["blocked_paths"][0]["path"] == "../outside.py"
