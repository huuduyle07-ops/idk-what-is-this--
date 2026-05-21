"""Phase 7.2 — Flask client tests for /worker-runs/view and /worker-runs/import."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import handoff_notes, worker_runs
from scripts import run_subagent_handoff as runner


@pytest.fixture
def client(tmp_path, monkeypatch):
    worker_runs_root = tmp_path / "worker_runs"
    proposals_root = tmp_path / "proposals"
    handoff_root = tmp_path / "handoffs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(worker_runs, "DEFAULT_WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(worker_runs, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(runner, "HANDOFF_ROOT", handoff_root)

    from web import app as web_app
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        c._worker_runs_root = worker_runs_root  # type: ignore[attr-defined]
        c._proposals_root = proposals_root  # type: ignore[attr-defined]
        c._handoff_root = handoff_root  # type: ignore[attr-defined]
        c._fake_repo = fake_repo  # type: ignore[attr-defined]
        yield c


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_complete_run(client, run_id="20260521_010203_imp", title="Import me"):
    note = handoff_notes.create_handoff_note(
        title=title,
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(client._fake_repo),
        handoff_root=client._handoff_root,
    )
    handoff_text = Path(note["path"]).read_text(encoding="utf-8")
    run_dir = client._worker_runs_root / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "handoff.md").write_text(handoff_text, encoding="utf-8")
    _write_json(run_dir / "worker_run.json", {
        "dry_run": False, "worker": "codex", "command": "codex exec --full-auto",
        "exit_code": 0, "timed_out": False, "duration_sec": 5.0,
        "started_at": "2026-05-21T01:02:03+00:00",
        "finished_at": "2026-05-21T01:02:08+00:00",
        "handoff_path": note["path"],
        "artifact_dir": str(run_dir), "timeout_sec": 300, "error": None,
    })
    (run_dir / "raw_output.txt").write_text("hello world", encoding="utf-8")
    (run_dir / "worker_command.txt").write_text("codex exec --full-auto\n", encoding="utf-8")
    (run_dir / "proposal.md").write_text("# proposal\n", encoding="utf-8")
    _write_json(run_dir / "patch_plan.json", [{"op": "noop"}])
    return run_dir


def test_view_returns_full_detail(client):
    _make_complete_run(client, run_id="20260521_010203_view", title="V")
    resp = client.get("/worker-runs/view?run_id=20260521_010203_view")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    run = body["run"]
    assert run["run_id"] == "20260521_010203_view"
    assert run["handoff_title"] == "V"
    assert run["has_proposal_md"] is True
    assert "raw_output_preview" in run


def test_view_rejects_path_traversal(client, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "worker_run.json").write_text("{}", encoding="utf-8")
    resp = client.get(f"/worker-runs/view?path={outside.as_posix()}")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "outside" in body["error"]


def test_view_missing_run_returns_404(client):
    resp = client.get("/worker-runs/view?run_id=20260521_000000_nope")
    assert resp.status_code == 404


def test_view_requires_run_id_or_path(client):
    resp = client.get("/worker-runs/view")
    assert resp.status_code == 400


def _repo_state(repo: Path) -> dict[str, str]:
    return {
        p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in repo.rglob("*") if p.is_file()
    }


def test_import_creates_proposal_and_does_not_modify_real_repo(client):
    _make_complete_run(client, run_id="20260521_010203_imp", title="Imp")
    before = _repo_state(client._fake_repo)

    resp = client.post("/worker-runs/import",
                       data={"run_id": "20260521_010203_imp"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    proposal_dir = Path(body["proposal_dir"])
    assert proposal_dir.is_dir()
    assert (proposal_dir / "proposal.md").is_file()
    assert (proposal_dir / "patch_plan.json").is_file()
    assert (proposal_dir / "item.json").is_file()
    assert body["source_run_id"] == "20260521_010203_imp"

    after = _repo_state(client._fake_repo)
    assert before == after, "real repo unchanged by import"


def test_import_refuses_incomplete_run(client):
    run_dir = client._worker_runs_root / "20260521_010203_inc"
    run_dir.mkdir(parents=True)
    _write_json(run_dir / "worker_run.json", {"dry_run": False, "worker": "codex"})
    (run_dir / "handoff.md").write_text("x", encoding="utf-8")
    # no proposal.md, no patch_plan.json

    resp = client.post("/worker-runs/import",
                       data={"run_id": "20260521_010203_inc"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "incomplete" in body["error"]
    assert "proposal.md" in body["error"]
    assert "patch_plan.json" in body["error"]


def test_import_refuses_dry_run(client):
    _make_complete_run(client, run_id="20260521_010203_dry", title="D")
    # Flip the run to dry_run=True after creation.
    run_json_path = client._worker_runs_root / "20260521_010203_dry" / "worker_run.json"
    record = json.loads(run_json_path.read_text(encoding="utf-8"))
    record["dry_run"] = True
    run_json_path.write_text(json.dumps(record), encoding="utf-8")

    resp = client.post("/worker-runs/import",
                       data={"run_id": "20260521_010203_dry"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "dry-run" in body["error"]


def test_import_requires_run_id_or_path(client):
    resp = client.post("/worker-runs/import", data={})
    assert resp.status_code == 400


# ---- /proposals/validate (Phase 7.2.1) --------------------------------------


def _import_via_route(client, run_id="20260521_010001_v", title="V"):
    _make_complete_run(client, run_id=run_id, title=title)
    resp = client.post("/worker-runs/import", data={"run_id": run_id})
    return resp.get_json()["proposal_dir"]


def test_validate_route_happy_path(client, monkeypatch):
    proposal_dir = _import_via_route(client, "20260521_010101_v1")

    import core.worker_runs as _wr
    monkeypatch.setattr(
        _wr, "run_patch_plan_with_artifacts",
        lambda project_root, plan, **kw: {
            "success": True, "applied_ops": plan, "diffs": [], "error": None,
        },
    )
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    resp = client.post("/proposals/validate", data={
        "proposal_dir": proposal_dir,
        "repo_path": str(client._fake_repo),
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["apply_success"] is True
    assert body["validation_ok"] is True
    assert body["proposal_dir"] == proposal_dir


def test_validate_route_requires_proposal_dir(client):
    resp = client.post("/proposals/validate",
                       data={"repo_path": str(client._fake_repo)})
    assert resp.status_code == 400


def test_validate_route_requires_repo_path(client):
    proposal_dir = _import_via_route(client, "20260521_010102_v2")
    resp = client.post("/proposals/validate", data={"proposal_dir": proposal_dir})
    assert resp.status_code == 400


def test_validate_route_rejects_path_traversal(client, tmp_path):
    outside = tmp_path / "outside_proposal"
    outside.mkdir()
    (outside / "patch_plan.json").write_text("[]", encoding="utf-8")
    resp = client.post("/proposals/validate", data={
        "proposal_dir": str(outside),
        "repo_path": str(client._fake_repo),
    })
    assert resp.status_code == 400
    body = resp.get_json()
    assert "outside" in body["error"]


def test_validate_route_includes_lesson_artifacts_on_success(client, monkeypatch):
    proposal_dir = _import_via_route(client, "20260521_012100_v1")

    import core.worker_runs as _wr
    monkeypatch.setattr(
        _wr, "run_patch_plan_with_artifacts",
        lambda project_root, plan, **kw: {
            "success": True, "applied_ops": plan, "diffs": [], "error": None,
        },
    )
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    resp = client.post("/proposals/validate", data={
        "proposal_dir": proposal_dir,
        "repo_path": str(client._fake_repo),
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert "lesson_artifacts" in body
    la = body["lesson_artifacts"]
    assert la["ok"] is True
    assert set(la["created"]) == {"case.json", "patch_proposal.json"}


def test_validate_route_includes_lesson_artifacts_skipped_on_failure(client, monkeypatch):
    proposal_dir = _import_via_route(client, "20260521_012100_v2")

    import core.worker_runs as _wr
    monkeypatch.setattr(
        _wr, "run_patch_plan_with_artifacts",
        lambda project_root, plan, **kw: {
            "success": False, "applied_ops": [], "diffs": [],
            "error": "snippet not found",
        },
    )
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    resp = client.post("/proposals/validate", data={
        "proposal_dir": proposal_dir,
        "repo_path": str(client._fake_repo),
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["apply_success"] is False
    la = body["lesson_artifacts"]
    assert la["ok"] is False
    assert la["created"] == []
    assert la["skipped_reason"]
