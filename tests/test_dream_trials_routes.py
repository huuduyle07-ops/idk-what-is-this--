"""Phase 4.7c — web routes for structured Dream trials.

Three Flask routes back the Dream tab's Structured Trial Reports section:

    POST /dream/trials/create
    GET  /dream/trials/list
    GET  /dream/trials/file

The trial creation route delegates to `core.dream_trials` (Phase 4.7b),
which is already report-only. The list and file routes are read-only and
must reject path traversal + non-whitelisted filenames.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from core import dream_artifacts, dream_trials


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    # Project-tag fingerprints empty dirs to the same hash, so two tests using
    # `tmp_path / "repo"` collide on the same .agent/<tag>/. Clear any state
    # the test relies on; trial files land under .agent/<tag>/dream_trials/.
    dream_artifacts.write_queue(str(r), [])
    trials_root = Path(dream_trials._trials_root(str(r)))
    if trials_root.exists():
        for sub in trials_root.iterdir():
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


# ---------------------------------------------------------------------------
# POST /dream/trials/create
# ---------------------------------------------------------------------------

def test_create_route_creates_trial_for_idea_trial_report_only(client, repo):
    resp = client.post(
        "/dream/trials/create",
        json={
            "repo_path": str(repo),
            "dream_type": "idea_trial",
            "action_level": "report_only",
            "title": "Try X as a tiny experiment",
            "hint": "see the notes",
            "reference_notes": "context here",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["trial_id"]
    assert body["status"]                  # decision string
    assert body["status"] in dream_trials.DECISION_POLICY
    assert Path(body["artifact_dir"]).is_dir()
    # File list must include all 7 markdown files + trial.json.
    expected = {
        "trial.json",
        "01_reference_study.md",
        "02_baseline_answer.md",
        "03_reasoning_chunks.md",
        "04_multi_perspective_evaluation.md",
        "05_refutation.md",
        "06_judge_report.md",
        "07_final_decision.md",
    }
    assert expected <= set(body["files"])
    # Allowed / blocked actions echo the Phase 4.7b policy.
    assert "patch" not in body["allowed_actions"]
    assert "apply" not in body["allowed_actions"]
    assert "commit" not in body["allowed_actions"]
    assert {"patch", "apply", "commit"} <= set(body["blocked_actions"])


def test_create_route_accepts_markdown_files_as_comma_separated_string(client, repo):
    note = repo / "a.md"
    note.write_text("# A\nGrounded content.\n", encoding="utf-8")
    resp = client.post(
        "/dream/trials/create",
        json={
            "repo_path": str(repo),
            "dream_type": "reference_study",
            "action_level": "report_only",
            "title": "reference t",
            "markdown_files": "a.md , does_not_exist.md",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    # The missing file lands as an unknown, not an exception.
    trial_json = json.loads(
        (Path(body["artifact_dir"]) / "trial.json").read_text(encoding="utf-8")
    )
    unknowns = " ".join(trial_json["reference_study"]["unknowns"])
    assert "does_not_exist.md" in unknowns


@pytest.mark.parametrize("dream_type", ["bug_investigation", "debt_cleanup"])
def test_create_route_rejects_disallowed_dream_types(client, repo, dream_type):
    resp = client.post(
        "/dream/trials/create",
        json={
            "repo_path": str(repo),
            "dream_type": dream_type,
            "action_level": "report_only",
            "title": "t",
        },
    )
    body = resp.get_json()
    assert body.get("ok") is False
    assert dream_type in body["error"]


def test_create_route_rejects_patch_if_safe_action_level(client, repo):
    resp = client.post(
        "/dream/trials/create",
        json={
            "repo_path": str(repo),
            "dream_type": "idea_trial",
            "action_level": "patch_if_safe",
            "title": "t",
        },
    )
    body = resp.get_json()
    assert body.get("ok") is False
    assert "report_only" in body["error"]


def test_create_route_rejects_proposal_draft_action_level(client, repo):
    resp = client.post(
        "/dream/trials/create",
        json={
            "repo_path": str(repo),
            "dream_type": "idea_trial",
            "action_level": "proposal_draft",
            "title": "t",
        },
    )
    body = resp.get_json()
    assert body.get("ok") is False
    assert "report_only" in body["error"]


def test_create_route_rejects_empty_title(client, repo):
    resp = client.post(
        "/dream/trials/create",
        json={
            "repo_path": str(repo),
            "dream_type": "idea_trial",
            "action_level": "report_only",
            "title": "   ",
        },
    )
    body = resp.get_json()
    assert body.get("ok") is False
    assert "title" in body["error"].lower()


def test_create_route_rejects_bad_repo_path(client, tmp_path):
    resp = client.post(
        "/dream/trials/create",
        json={
            "repo_path": str(tmp_path / "does-not-exist"),
            "dream_type": "idea_trial",
            "action_level": "report_only",
            "title": "t",
        },
    )
    body = resp.get_json()
    assert body.get("ok") is False
    assert "repo_path" in body["error"]


# ---------------------------------------------------------------------------
# GET /dream/trials/list
# ---------------------------------------------------------------------------

def _create_via_core(repo: Path, title: str) -> str:
    """Helper: create a trial directly through the core API."""
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title=title,
    )
    return result.trial_id


def test_list_route_returns_trials_newest_first(client, repo):
    first = _create_via_core(repo, "first idea")
    # Sleep just long enough to bump the second-resolution timestamp embedded
    # in the trial_id so the ordering is unambiguous.
    time.sleep(1.1)
    second = _create_via_core(repo, "second idea")

    resp = client.get(f"/dream/trials/list?repo_path={repo}")
    assert resp.status_code == 200
    body = resp.get_json()
    trials = body["trials"]
    ids = [t["trial_id"] for t in trials]
    # The second trial is newest, so it comes first.
    assert ids.index(second) < ids.index(first)
    # Every entry exposes the fields the UI renders.
    for entry in trials:
        assert "title" in entry
        assert "dream_type" in entry
        assert "action_level" in entry
        assert "status" in entry
        assert "created_at" in entry


def test_list_route_ignores_malformed_trial_folders(client, repo):
    good_id = _create_via_core(repo, "good idea")
    trials_root = Path(dream_trials._trials_root(str(repo)))
    # An empty subdir with no trial.json should be skipped silently.
    (trials_root / "20991231-000000-bogus-folder").mkdir(parents=True, exist_ok=True)
    # A subdir with malformed JSON should also be skipped silently.
    broken = trials_root / "20991231-000001-broken-folder"
    broken.mkdir(parents=True, exist_ok=True)
    (broken / "trial.json").write_text("{ not json", encoding="utf-8")

    resp = client.get(f"/dream/trials/list?repo_path={repo}")
    assert resp.status_code == 200
    body = resp.get_json()
    ids = [t["trial_id"] for t in body["trials"]]
    assert good_id in ids
    assert "20991231-000000-bogus-folder" not in ids
    assert "20991231-000001-broken-folder" not in ids


def test_list_route_handles_no_trials_dir(client, repo):
    """Brand-new repo with no .agent/dream_trials/ — returns [] not 500."""
    resp = client.get(f"/dream/trials/list?repo_path={repo}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["trials"] == [] or isinstance(body["trials"], list)


def test_list_route_rejects_bad_repo_path(client, tmp_path):
    resp = client.get(
        f"/dream/trials/list?repo_path={tmp_path / 'does-not-exist'}"
    )
    body = resp.get_json()
    assert body.get("error")


# ---------------------------------------------------------------------------
# GET /dream/trials/file
# ---------------------------------------------------------------------------

def test_file_route_returns_allowed_markdown_file(client, repo):
    trial_id = _create_via_core(repo, "fetch test")
    resp = client.get(
        f"/dream/trials/file?repo_path={repo}&trial_id={trial_id}&file=05_refutation.md"
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("ok") is True
    assert body["file"] == "05_refutation.md"
    assert "Refutation" in body["content"]


def test_file_route_returns_trial_json(client, repo):
    trial_id = _create_via_core(repo, "fetch json")
    resp = client.get(
        f"/dream/trials/file?repo_path={repo}&trial_id={trial_id}&file=trial.json"
    )
    body = resp.get_json()
    assert body.get("ok") is True
    parsed = json.loads(body["content"])
    assert parsed["trial_id"] == trial_id


@pytest.mark.parametrize("traversal", [
    "../../etc/passwd",
    "..\\..\\windows\\system32\\cmd.exe",
    "../trial.json",
    "subdir/../../trial.json",
])
def test_file_route_blocks_path_traversal(client, repo, traversal):
    trial_id = _create_via_core(repo, "traversal probe")
    resp = client.get(
        f"/dream/trials/file?repo_path={repo}&trial_id={trial_id}&file={traversal}"
    )
    body = resp.get_json()
    assert body.get("ok") is not True
    assert body.get("error")


@pytest.mark.parametrize("bad_file", [
    "secrets.txt",
    "raw_model_attempt1.txt",
    "../trial.json",
    "trial.json.bak",
])
def test_file_route_blocks_non_whitelisted_files(client, repo, bad_file):
    trial_id = _create_via_core(repo, "whitelist probe")
    resp = client.get(
        f"/dream/trials/file?repo_path={repo}&trial_id={trial_id}&file={bad_file}"
    )
    body = resp.get_json()
    assert body.get("ok") is not True


@pytest.mark.parametrize("bad_trial_id", [
    "../",
    "..",
    "../../",
    "no-such-trial",
    "20260101-000000-../../etc",
])
def test_file_route_blocks_traversal_in_trial_id(client, repo, bad_trial_id):
    # Make sure at least one real trial exists so the parent dir is present.
    _create_via_core(repo, "anchor")
    resp = client.get(
        "/dream/trials/file"
        f"?repo_path={repo}&trial_id={bad_trial_id}&file=trial.json"
    )
    body = resp.get_json()
    assert body.get("ok") is not True


# ---------------------------------------------------------------------------
# Import purity of the new routes module
# ---------------------------------------------------------------------------

def test_routes_module_does_not_import_patch_executor_or_benchmark_or_model_clients():
    from web.routes import dream_trials_routes  # noqa: F401
    src = Path(dream_trials_routes.__file__).read_text(encoding="utf-8")
    src_lower = src.lower()
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
        "run_gemini_request",
        "agents.gemini_client",
        "agents.deepseek_client",
        "agents.ollama_client",
    ]
    for needle in forbidden:
        assert needle.lower() not in src_lower, (
            f"dream_trials_routes leaked a forbidden import: {needle}"
        )


# ---------------------------------------------------------------------------
# Existing Dream queue routes must still work after Phase 4.7c lands.
# ---------------------------------------------------------------------------

def test_existing_dream_queue_route_still_works_after_phase_4_7c(client, repo):
    resp = client.post(
        "/dream/queue",
        data={
            "repo_path": str(repo),
            "action": "add",
            "dream_type": "bug_investigation",
            "action_level": "plan_only",
            "title": "regression guard",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "error" not in body, body
    assert body["queue"][0]["dream_type"] == "bug_investigation"


def test_existing_dream_taxonomy_route_still_works(client):
    resp = client.get("/dream/taxonomy")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "dream_types" in body
    assert "allowed_combinations" in body
