import json

from core.run_lifecycle import run_patch_plan_with_artifacts


def test_lifecycle_success_writes_replay_bundle(tmp_path, monkeypatch):
    import core.run_artifacts as run_artifacts
    import core.run_lifecycle as run_lifecycle

    monkeypatch.setattr(run_artifacts, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    monkeypatch.setattr(run_lifecycle, "collect_brain_stamp", lambda repo: {
        "brain_stamp_id": "stamp-success",
        "schema_version": 2,
    })
    repo = tmp_path / "repo"
    repo.mkdir()
    plan = [{"op": "create_file", "relative_path": "created.txt", "content": "hello\n"}]

    result = run_patch_plan_with_artifacts(
        str(repo),
        plan,
        user_query="create a file",
        control_result={"summary": "test"},
        source="unit",
    )

    assert result["success"] is True
    assert result["brain_stamp_id"] == "stamp-success"
    replay_dir = tmp_path / result["replay_dir"]
    assert replay_dir.is_dir()
    assert json.loads((replay_dir / "apply_result.json").read_text(encoding="utf-8"))[
        "success"
    ] is True
    assert (replay_dir / "user_query.txt").read_text(encoding="utf-8") == "create a file"


def test_lifecycle_validation_failure_records_rollback_and_restores_file(tmp_path, monkeypatch):
    import core.run_artifacts as run_artifacts
    import core.run_lifecycle as run_lifecycle

    monkeypatch.setattr(run_artifacts, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    monkeypatch.setattr(run_lifecycle, "collect_brain_stamp", lambda repo: {
        "brain_stamp_id": "stamp-fail",
        "schema_version": 2,
    })
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "main.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    plan = [{
        "op": "replace_snippet",
        "relative_path": "main.py",
        "target_snippet": "VALUE = 1\n",
        "patched_snippet": "VALUE = 2\n",
    }]

    result = run_patch_plan_with_artifacts(
        str(repo),
        plan,
        validation_command='python -c "raise SystemExit(1)"',
        source="unit",
    )

    assert result["success"] is False
    assert result["rollback_performed"] is True
    assert target.read_text(encoding="utf-8") == "VALUE = 1\n"
    replay_dir = tmp_path / result["replay_dir"]
    assert (replay_dir / "validation_output.txt").is_file()
    events = [
        json.loads(line)
        for line in (replay_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert "rollback_performed" in [event["phase"] for event in events]


def test_lifecycle_apply_failure_still_writes_replay_bundle(tmp_path, monkeypatch):
    import core.run_artifacts as run_artifacts
    import core.run_lifecycle as run_lifecycle

    monkeypatch.setattr(run_artifacts, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    monkeypatch.setattr(run_lifecycle, "collect_brain_stamp", lambda repo: {
        "brain_stamp_id": "stamp-apply-fail",
        "schema_version": 2,
    })
    repo = tmp_path / "repo"
    repo.mkdir()
    plan = [{
        "op": "replace_snippet",
        "relative_path": "missing.py",
        "target_snippet": "x",
        "patched_snippet": "y",
    }]

    result = run_patch_plan_with_artifacts(str(repo), plan, source="unit")

    assert result["success"] is False
    replay_dir = tmp_path / result["replay_dir"]
    assert json.loads((replay_dir / "apply_result.json").read_text(encoding="utf-8"))[
        "success"
    ] is False
    final_status = json.loads((replay_dir / "final_status.json").read_text(encoding="utf-8"))
    assert final_status["status"] == "failed"
