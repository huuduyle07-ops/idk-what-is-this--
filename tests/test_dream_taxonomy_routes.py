"""Phase 4.7a — Flask routes for the new dream_type / action_level taxonomy.

The web layer must:
- Accept new `dream_type` + `action_level` form fields on /dream/queue.
- Continue to accept the legacy `kind` + `mode` fields (mapped into the new
  taxonomy by `core.dream_taxonomy.normalize_legacy`).
- Reject invalid combinations with a friendly error (not a silent coercion).
- Expose the allowed-combinations matrix at /dream/taxonomy so the UI can
  hide/disable invalid action levels per work type.

No benchmark execution, no model patch execution, no patch behavior changes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import dream_artifacts


@pytest.fixture
def client(tmp_path, monkeypatch):
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    # Project-tag fingerprints empty dirs to the same hash, so two tests using
    # `tmp_path / "repo"` collide on the same .agent/<tag>/dreams/queue.json.
    # Reset the queue at the start of each test so we get a clean slate.
    dream_artifacts.write_queue(str(r), [])
    yield r
    dream_artifacts.write_queue(str(r), [])


# ---------------------------------------------------------------------------
# /dream/taxonomy — read-only matrix endpoint
# ---------------------------------------------------------------------------

def test_dream_taxonomy_route_returns_dream_types_and_allowed_combinations(client):
    resp = client.get("/dream/taxonomy")
    assert resp.status_code == 200
    data = resp.get_json()

    assert set(data["dream_types"]) == {
        "bug_investigation",
        "debt_cleanup",
        "idea_trial",
        "research_study",
        "reference_study",
        "case_idea_research",
    }
    # action_levels appears alongside the matrix so the UI can render labels
    # in a stable order without inferring them from the combinations dict.
    assert {"report_only", "plan_only", "proposal_draft", "patch_if_safe"}.issubset(
        set(data["action_levels"])
    )
    # The allowed-combinations matrix is exposed verbatim — the UI uses it
    # to hide/disable invalid action levels when the work type changes.
    allowed = data["allowed_combinations"]
    assert set(allowed["bug_investigation"]) == {"plan_only", "patch_if_safe"}
    assert set(allowed["reference_study"]) == {"report_only", "case_idea_research"}


# ---------------------------------------------------------------------------
# /dream/queue add — new fields path
# ---------------------------------------------------------------------------

def test_queue_add_with_new_dream_type_and_action_level_succeeds(client, repo):
    resp = client.post(
        "/dream/queue",
        data={
            "repo_path": str(repo),
            "action": "add",
            "dream_type": "bug_investigation",
            "action_level": "plan_only",
            "title": "investigate null deref",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "error" not in body, body
    queue = body["queue"]
    assert len(queue) == 1
    item = queue[0]
    # New canonical fields land on the item.
    assert item["dream_type"] == "bug_investigation"
    assert item["action_level"] == "plan_only"
    # Backward-compat fields are also populated so existing run code keeps
    # working without a flag day.
    assert item.get("kind") == "bug"
    assert item.get("title") == "investigate null deref"


def test_queue_add_rejects_invalid_combo_with_friendly_error(client, repo):
    resp = client.post(
        "/dream/queue",
        data={
            "repo_path": str(repo),
            "action": "add",
            "dream_type": "research_study",
            "action_level": "patch_if_safe",  # not allowed for research_study
            "title": "should be rejected",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "error" in body
    # The friendly error names both pieces and lists the allowed levels.
    assert "research_study" in body["error"]
    assert "patch_if_safe" in body["error"]
    assert "report_only" in body["error"]
    # Crucially the queue must not silently coerce the invalid combo — the
    # item is rejected, not stored under a different action_level.
    assert dream_artifacts.read_queue(str(repo)) == []


def test_queue_add_rejects_unknown_dream_type(client, repo):
    resp = client.post(
        "/dream/queue",
        data={
            "repo_path": str(repo),
            "action": "add",
            "dream_type": "totally_made_up_type",
            "action_level": "plan_only",
            "title": "x",
        },
    )
    body = resp.get_json()
    assert "error" in body
    assert "totally_made_up_type" in body["error"]
    assert dream_artifacts.read_queue(str(repo)) == []


# ---------------------------------------------------------------------------
# /dream/queue add — legacy fields path (backward compat)
# ---------------------------------------------------------------------------

def test_queue_add_with_legacy_kind_only_still_works(client, repo):
    """Old POSTs that only send `kind` (no dream_type) keep working and get
    normalized into the new taxonomy on the way in."""
    resp = client.post(
        "/dream/queue",
        data={
            "repo_path": str(repo),
            "action": "add",
            "kind": "bug",
            "title": "legacy add",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "error" not in body, body
    item = body["queue"][0]
    assert item["dream_type"] == "bug_investigation"
    assert item["action_level"] in {"plan_only", "patch_if_safe"}
    # The original kind value is preserved for the existing run code.
    assert item["kind"] == "bug"


def test_queue_add_with_legacy_research_kind_maps_to_research_study(client, repo):
    resp = client.post(
        "/dream/queue",
        data={
            "repo_path": str(repo),
            "action": "add",
            "kind": "research",
            "title": "legacy research",
        },
    )
    body = resp.get_json()
    assert "error" not in body, body
    item = body["queue"][0]
    assert item["dream_type"] == "research_study"
    assert item["action_level"] == "report_only"


def test_queue_add_with_reference_study_kind_maps_correctly(client, repo):
    resp = client.post(
        "/dream/queue",
        data={
            "repo_path": str(repo),
            "action": "add",
            "kind": "reference_study",
            "title": "legacy ref",
        },
    )
    body = resp.get_json()
    assert "error" not in body, body
    item = body["queue"][0]
    assert item["dream_type"] == "reference_study"


def test_queue_add_with_unknown_legacy_kind_returns_friendly_error(client, repo):
    """Unknown legacy kinds (random user input) are still rejected at the
    queue boundary so we don't pollute the queue with garbage."""
    resp = client.post(
        "/dream/queue",
        data={
            "repo_path": str(repo),
            "action": "add",
            "kind": "garbage_value_xyz",
            "title": "x",
        },
    )
    body = resp.get_json()
    assert "error" in body
    assert "garbage_value_xyz" in body["error"]
    assert dream_artifacts.read_queue(str(repo)) == []


# ---------------------------------------------------------------------------
# Guarantees that this phase does NOT add execution-side surprises.
# ---------------------------------------------------------------------------

def test_taxonomy_module_contains_no_benchmark_or_patch_runtime_imports():
    """Phase 4.7a is taxonomy cleanup only — no benchmark execution, no model
    calls, no patch application logic. The taxonomy module must stay pure.
    """
    import core.dream_taxonomy as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    forbidden_substrings = [
        "run_benchmarks",
        "run_gemini_request",
        "run_patch_plan_with_artifacts",
        "subprocess",
    ]
    for needle in forbidden_substrings:
        assert needle not in source, (
            f"Phase 4.7a forbids runtime side effects in dream_taxonomy.py "
            f"(found {needle!r})"
        )
