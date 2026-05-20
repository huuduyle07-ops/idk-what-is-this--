import json
from pathlib import Path

import pytest

from core.run_artifacts import RunArtifactRecorder, TRUNCATION_MARKER


def test_recorder_creates_replay_directory_under_agent_dir(tmp_path, monkeypatch):
    import core.run_artifacts as run_artifacts

    repo = tmp_path / "repo"
    repo.mkdir()
    agent_dir = tmp_path / ".agent"
    monkeypatch.setattr(run_artifacts, "get_agent_dir", lambda repo_path=None: agent_dir)

    recorder = RunArtifactRecorder.start(
        repo_path=str(repo),
        source="test",
        brain_stamp={"brain_stamp_id": "stamp-1"},
    )

    assert recorder.replay_dir.parent == agent_dir / "replays"
    assert (recorder.replay_dir / "brain_stamp.json").is_file()
    assert json.loads((recorder.replay_dir / "brain_stamp.json").read_text(encoding="utf-8"))[
        "brain_stamp_id"
    ] == "stamp-1"


def test_recorder_rejects_unapproved_artifact_names(tmp_path, monkeypatch):
    import core.run_artifacts as run_artifacts

    monkeypatch.setattr(run_artifacts, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    recorder = RunArtifactRecorder.start(
        repo_path=str(tmp_path),
        source="test",
        brain_stamp={"brain_stamp_id": "stamp-1"},
    )

    with pytest.raises(ValueError):
        recorder.write_text("../escape.txt", "nope")

    with pytest.raises(ValueError):
        recorder.write_json("unexpected.json", {})


def test_recorder_caps_large_text_with_marker(tmp_path, monkeypatch):
    import core.run_artifacts as run_artifacts

    monkeypatch.setattr(run_artifacts, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    recorder = RunArtifactRecorder.start(
        repo_path=str(tmp_path),
        source="test",
        brain_stamp={"brain_stamp_id": "stamp-1"},
    )

    max_chars = len(TRUNCATION_MARKER) + 3
    recorder.write_text("validation_output.txt", "abcdef" * 20, max_chars=max_chars)

    text = (recorder.replay_dir / "validation_output.txt").read_text(encoding="utf-8")
    assert text.startswith("abc")
    assert "[truncated" in text
    assert len(text) <= max_chars


def test_recorder_appends_ordered_events_and_final_status(tmp_path, monkeypatch):
    import core.run_artifacts as run_artifacts

    monkeypatch.setattr(run_artifacts, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    recorder = RunArtifactRecorder.start(
        repo_path=str(tmp_path),
        source="test",
        brain_stamp={"brain_stamp_id": "stamp-1"},
    )

    recorder.append_event("started", {"a": 1})
    recorder.append_event("finished", {"b": 2})
    recorder.finish("success", {"ok": True})

    events = [
        json.loads(line)
        for line in (recorder.replay_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["phase"] for event in events] == ["started", "finished"]
    final_status = json.loads((recorder.replay_dir / "final_status.json").read_text(encoding="utf-8"))
    assert final_status["status"] == "success"
    assert final_status["result"]["ok"] is True
