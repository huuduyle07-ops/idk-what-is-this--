"""Phase 8.2c tests for the MCP validate_imported_worker_proposal harness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import handoff_notes, worker_runs
from mcp_server import artifact_write
from mcp_server.artifact_write import validate_imported_worker_proposal_harness


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    worker_runs_root = tmp_path / "worker_runs"
    proposals_root = tmp_path / "proposals"
    handoff_root = tmp_path / "handoffs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(worker_runs, "DEFAULT_WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(worker_runs, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **_kwargs: None,
        raising=False,
    )
    # Force "no validation command" so the happy path never spawns a real
    # validator subprocess (which would slow down or fail in test envs).
    monkeypatch.setattr(
        worker_runs,
        "_inferred_validation_command",
        lambda _repo: "",
        raising=False,
    )

    return {
        "worker_runs_root": worker_runs_root,
        "proposals_root": proposals_root,
        "handoff_root": handoff_root,
        "fake_repo": fake_repo,
    }


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_imported_proposal(env, run_id: str = "20260523_120000_val") -> str:
    """Create a complete worker run and import it as a proposal.

    Returns the relative `proposal_ref` (run_timestamp/item_subdir) suitable
    for the validate harness MCP input.
    """
    run_dir = env["worker_runs_root"] / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    note = handoff_notes.create_handoff_note(
        title="Validate imported proposal",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(env["fake_repo"]),
        handoff_root=env["handoff_root"],
    )
    (run_dir / "handoff.md").write_text(
        Path(note["path"]).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_json(run_dir / "worker_run.json", {
        "dry_run": False,
        "worker": "codex",
        "command": "codex exec",
        "handoff_path": note["path"],
        "artifact_dir": str(run_dir),
    })
    (run_dir / "raw_output.txt").write_text("worker output\n", encoding="utf-8")
    (run_dir / "proposal.md").write_text("# Worker proposal\n", encoding="utf-8")
    _write_json(run_dir / "patch_plan.json", [{
        "op": "replace_snippet",
        "relative_path": "src/foo.py",
        "target_snippet": "x = 1",
        "patched_snippet": "x = 2",
    }])

    imported = worker_runs.import_worker_run_as_proposal(run_id)
    proposal_dir = Path(imported["proposal_dir"])
    return proposal_dir.relative_to(env["proposals_root"]).as_posix()


def _repo_state(repo: Path) -> dict[str, str]:
    return {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in repo.rglob("*")
        if path.is_file()
    }


def test_valid_proposal_validates_in_temp_clone_and_writes_artifacts(env):
    proposal_ref = _make_imported_proposal(env)

    result = validate_imported_worker_proposal_harness({
        "proposal_ref": proposal_ref,
        "repo_path": str(env["fake_repo"]),
    })

    proposal_dir = Path(result["proposal_dir"])
    assert result["ok"] is True
    assert result["apply_success"] is True
    # No validation command inferred -> validation_ok is None (legitimate).
    assert result["validation_ok"] is None
    assert "no validation command" in result["message"].lower()
    assert (proposal_dir / "apply_result.json").is_file()
    assert (proposal_dir / "validation.json").is_file()
    assert (proposal_dir / "validation_output.txt").is_file()
    # Lesson-synth files must NOT exist when validation didn't pass.
    assert not (proposal_dir / "case.json").exists()
    assert not (proposal_dir / "patch_proposal.json").exists()
    # Artifacts list reflects what actually exists on disk.
    assert str(proposal_dir) in result["artifacts"]
    assert str(proposal_dir / "apply_result.json") in result["artifacts"]
    assert str(proposal_dir / "validation.json") in result["artifacts"]
    assert str(proposal_dir / "validation_output.txt") in result["artifacts"]


def test_missing_proposal_ref_rejected(env):
    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "repo_path": str(env["fake_repo"]),
        })


def test_empty_proposal_ref_rejected(env):
    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": "   ",
            "repo_path": str(env["fake_repo"]),
        })


def test_absolute_proposal_ref_rejected(env):
    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": str((env["proposals_root"] / "abs").resolve()),
            "repo_path": str(env["fake_repo"]),
        })


@pytest.mark.parametrize("proposal_ref", [
    "../escape/01-foo",
    "ts/../escape",
    "../../etc",
    "ts/./01-foo",
    ".",
    "..",
    "ts//01-foo",
    "..\\escape\\01-foo",
])
def test_traversal_proposal_ref_rejected(env, proposal_ref):
    with pytest.raises(ValueError, match="proposal_ref"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
            "repo_path": str(env["fake_repo"]),
        })


def test_unknown_input_field_rejected(env):
    proposal_ref = _make_imported_proposal(env)
    with pytest.raises(ValueError, match="unknown field"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
            "repo_path": str(env["fake_repo"]),
            "extra": "nope",
        })


def test_missing_repo_path_rejected(env):
    proposal_ref = _make_imported_proposal(env)
    with pytest.raises(ValueError, match="repo_path"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
        })


def test_empty_repo_path_rejected(env):
    proposal_ref = _make_imported_proposal(env)
    with pytest.raises(ValueError, match="repo_path"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
            "repo_path": "   ",
        })


def test_non_directory_repo_path_rejected(env, tmp_path):
    proposal_ref = _make_imported_proposal(env)
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="repo_path"):
        validate_imported_worker_proposal_harness({
            "proposal_ref": proposal_ref,
            "repo_path": str(missing),
        })


def test_input_not_dict_rejected(env):
    with pytest.raises(ValueError, match="dict"):
        validate_imported_worker_proposal_harness("not a dict")  # type: ignore[arg-type]
