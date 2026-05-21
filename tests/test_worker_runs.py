"""Phase 7.2 — unit tests for core/worker_runs.py."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import handoff_notes, worker_runs


# ---- Fixtures ---------------------------------------------------------------


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

    return {
        "worker_runs_root": worker_runs_root,
        "proposals_root": proposals_root,
        "handoff_root": handoff_root,
        "fake_repo": fake_repo,
    }


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_run(env, run_id, *, complete=True, dry_run=False, handoff_title="Test"):
    """Synthesize a worker run dir resembling Phase 7.1 output."""
    run_dir = env["worker_runs_root"] / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # handoff.md (use real create_handoff_note to ensure parseable HANDOFF_META)
    note = handoff_notes.create_handoff_note(
        title=handoff_title,
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(env["fake_repo"]),
        handoff_root=env["handoff_root"],
    )
    handoff_text = Path(note["path"]).read_text(encoding="utf-8")
    (run_dir / "handoff.md").write_text(handoff_text, encoding="utf-8")

    # worker_run.json
    _write_json(run_dir / "worker_run.json", {
        "dry_run": dry_run,
        "started_at": "2026-05-21T01:02:03+00:00",
        "finished_at": "2026-05-21T01:02:15+00:00",
        "duration_sec": 12.4,
        "exit_code": 0,
        "timed_out": False,
        "command": "codex exec --full-auto",
        "worker": "codex",
        "handoff_path": note["path"],
        "artifact_dir": str(run_dir),
        "timeout_sec": 300,
        "error": None,
    })

    # raw_output.txt
    (run_dir / "raw_output.txt").write_text(
        "worker said:\n" + ("A" * 5000), encoding="utf-8"
    )

    # worker_command.txt
    (run_dir / "worker_command.txt").write_text("codex exec --full-auto\n", encoding="utf-8")

    if complete:
        (run_dir / "proposal.md").write_text("# Worker proposal\n\nDo X.\n", encoding="utf-8")
        _write_json(run_dir / "patch_plan.json", [
            {"op": "replace_snippet", "relative_path": "src/foo.py",
             "target_snippet": "x = 1", "patched_snippet": "x = 2"}
        ])

    return run_dir


def _real_repo_state(repo: Path) -> dict[str, str]:
    state: dict[str, str] = {}
    for p in repo.rglob("*"):
        if p.is_file():
            state[p.relative_to(repo).as_posix()] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    return state


# ---- list_worker_runs -------------------------------------------------------


def test_list_worker_runs_empty_returns_empty_list(env):
    assert worker_runs.list_worker_runs() == []


def test_list_worker_runs_returns_newest_first(env):
    import time

    _make_run(env, "20260521_010000_a", handoff_title="a")
    time.sleep(1.1)
    _make_run(env, "20260521_010002_b", handoff_title="b")
    runs = worker_runs.list_worker_runs()
    assert len(runs) == 2
    assert runs[0]["run_id"] == "20260521_010002_b"
    assert runs[1]["run_id"] == "20260521_010000_a"


def test_list_worker_runs_respects_limit(env):
    for i in range(5):
        _make_run(env, f"20260521_01000{i}_x{i}")
    runs = worker_runs.list_worker_runs(limit=3)
    assert len(runs) == 3


def test_list_worker_runs_includes_legacy_fields(env):
    """The legacy /worker-runs/list response shape must remain intact."""
    _make_run(env, "20260521_010203_foo")
    runs = worker_runs.list_worker_runs()
    item = runs[0]
    for legacy_key in (
        "artifact_dir", "name", "dry_run", "worker", "exit_code",
        "timed_out", "duration_sec", "command", "handoff_path",
        "started_at", "finished_at", "error",
    ):
        assert legacy_key in item, f"missing legacy field: {legacy_key}"


def test_list_worker_runs_includes_new_fields(env):
    _make_run(env, "20260521_010203_foo", handoff_title="Hello")
    runs = worker_runs.list_worker_runs()
    item = runs[0]
    assert item["run_id"] == "20260521_010203_foo"
    assert item["has_proposal_md"] is True
    assert item["has_patch_plan_json"] is True
    assert item["handoff_title"] == "Hello"


def test_list_worker_runs_skips_dirs_without_worker_run_json(env):
    (env["worker_runs_root"] / "20260521_999999_broken").mkdir(parents=True)
    runs = worker_runs.list_worker_runs()
    assert runs == []


# ---- read_worker_run --------------------------------------------------------


def test_read_worker_run_via_run_id_returns_full_detail(env):
    _make_run(env, "20260521_010203_foo", handoff_title="hello detail")
    detail = worker_runs.read_worker_run("20260521_010203_foo")
    assert detail["run_id"] == "20260521_010203_foo"
    assert detail["handoff_title"] == "hello detail"
    assert detail["has_proposal_md"] is True
    assert detail["has_patch_plan_json"] is True
    assert detail["raw_output_preview"].startswith("worker said:")
    assert len(detail["raw_output_preview"]) <= worker_runs.RAW_OUTPUT_PREVIEW_CHARS + 64


def test_read_worker_run_via_absolute_path(env):
    run_dir = _make_run(env, "20260521_010203_foo")
    detail = worker_runs.read_worker_run(str(run_dir))
    assert detail["run_id"] == "20260521_010203_foo"


def test_read_worker_run_blocks_path_traversal(env, tmp_path):
    outside = tmp_path / "outside_run"
    outside.mkdir()
    (outside / "worker_run.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        worker_runs.read_worker_run(str(outside))


def test_read_worker_run_missing_raises_file_not_found(env):
    with pytest.raises(FileNotFoundError):
        worker_runs.read_worker_run("20260521_000000_nope")


# ---- detect_worker_outputs --------------------------------------------------


def test_detect_worker_outputs_complete(env):
    run_dir = _make_run(env, "20260521_010203_complete")
    detect = worker_runs.detect_worker_outputs(run_dir)
    assert detect["complete"] is True
    assert detect["has_proposal_md"] is True
    assert detect["has_patch_plan_json"] is True
    assert detect["has_handoff_md"] is True
    assert detect["has_worker_run_json"] is True
    assert detect["missing"] == []


def test_detect_worker_outputs_incomplete(env):
    run_dir = _make_run(env, "20260521_010203_incomplete", complete=False)
    detect = worker_runs.detect_worker_outputs(run_dir)
    assert detect["complete"] is False
    assert detect["has_proposal_md"] is False
    assert detect["has_patch_plan_json"] is False
    assert "proposal.md" in detect["missing"]
    assert "patch_plan.json" in detect["missing"]


# ---- import_worker_run_as_proposal ------------------------------------------


def test_import_creates_proposal_dir_with_all_artifacts(env):
    run_dir = _make_run(env, "20260521_010203_imp", handoff_title="Import me")
    before = _real_repo_state(env["fake_repo"])

    result = worker_runs.import_worker_run_as_proposal(run_dir)

    proposal_dir = Path(result["proposal_dir"])
    assert proposal_dir.is_dir()
    for f in ("item.json", "source_metadata.json", "handoff.md",
              "worker_run.json", "proposal.md", "patch_plan.json", "raw_output.txt"):
        assert (proposal_dir / f).is_file(), f"missing {f}"

    item = json.loads((proposal_dir / "item.json").read_text(encoding="utf-8"))
    assert item["source"] == "worker_run"
    assert item["source_run_id"] == "20260521_010203_imp"
    assert item["worker"] == "codex"
    assert item["human_approved_for_proposal"] is False
    assert item["needs_revalidation"] is True
    assert item["title"] == "Import me"

    src = json.loads((proposal_dir / "source_metadata.json").read_text(encoding="utf-8"))
    assert src["source"] == "worker_run"
    assert src["source_run_dir"].endswith("20260521_010203_imp")
    assert set(src["imported_files"]) >= {"handoff.md", "worker_run.json",
                                          "proposal.md", "patch_plan.json", "raw_output.txt"}

    after = _real_repo_state(env["fake_repo"])
    assert before == after, "real repo must be byte-identical after import"


def test_import_refuses_incomplete_run(env):
    run_dir = _make_run(env, "20260521_010203_inc", complete=False)
    with pytest.raises(FileNotFoundError, match="incomplete"):
        worker_runs.import_worker_run_as_proposal(run_dir)


def test_import_refuses_dry_run(env):
    run_dir = _make_run(env, "20260521_010203_dry", dry_run=True)
    with pytest.raises(ValueError, match="dry-run"):
        worker_runs.import_worker_run_as_proposal(run_dir)


def test_import_refuses_path_outside_worker_runs(env, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    for f in ("handoff.md", "proposal.md", "patch_plan.json", "raw_output.txt"):
        (outside / f).write_text("x", encoding="utf-8")
    _write_json(outside / "worker_run.json", {"dry_run": False, "worker": "codex"})
    with pytest.raises(ValueError, match="outside"):
        worker_runs.import_worker_run_as_proposal(str(outside))


def test_import_handles_directory_collision(env):
    run_dir = _make_run(env, "20260521_010203_collide")
    first = worker_runs.import_worker_run_as_proposal(run_dir)
    second = worker_runs.import_worker_run_as_proposal(run_dir)
    assert first["proposal_dir"] != second["proposal_dir"]
    assert Path(first["proposal_dir"]).is_dir()
    assert Path(second["proposal_dir"]).is_dir()


# ---- validate_imported_worker_proposal (Phase 7.2.1) ------------------------


def _import(env, run_id):
    """Import a complete worker run and return the resulting proposal_dir."""
    run_dir = _make_run(env, run_id)
    result = worker_runs.import_worker_run_as_proposal(run_dir)
    return Path(result["proposal_dir"])


def test_validate_refuses_missing_patch_plan_json(env):
    proposal_dir = _import(env, "20260521_010000_a")
    (proposal_dir / "patch_plan.json").unlink()
    with pytest.raises(FileNotFoundError, match="patch_plan.json"):
        worker_runs.validate_imported_worker_proposal(
            proposal_dir, env["fake_repo"]
        )


def test_validate_rejects_proposal_path_traversal(env, tmp_path):
    outside = tmp_path / "outside_proposal"
    outside.mkdir()
    (outside / "patch_plan.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        worker_runs.validate_imported_worker_proposal(
            outside, env["fake_repo"]
        )


def test_validate_rejects_missing_repo_path(env):
    proposal_dir = _import(env, "20260521_010000_b")
    with pytest.raises(FileNotFoundError):
        worker_runs.validate_imported_worker_proposal(
            proposal_dir, env["fake_repo"].parent / "does_not_exist"
        )


def test_validate_writes_apply_and_validation_artifacts(env, monkeypatch):
    proposal_dir = _import(env, "20260521_010000_c")

    import core.worker_runs as _wr

    def fake_apply(project_root, plan, validation_command=None, user_query="",
                   control_result=None, source="pipeline"):
        return {
            "success": True,
            "applied_ops": plan,
            "diffs": ["--- a\n+++ b\n@@\n-x = 1\n+x = 2\n"],
            "error": None,
            "rollback_performed": False,
        }

    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    result = worker_runs.validate_imported_worker_proposal(
        proposal_dir, env["fake_repo"]
    )

    assert result["ok"] is True
    assert result["apply_success"] is True
    assert result["validation_ok"] is True
    assert (proposal_dir / "apply_result.json").is_file()
    assert (proposal_dir / "validation.json").is_file()
    assert (proposal_dir / "validation_output.txt").is_file()

    item = json.loads((proposal_dir / "item.json").read_text(encoding="utf-8"))
    assert item["needs_revalidation"] is False
    assert item["validation_status"] == "passed"


def test_validate_real_repo_byte_identical(env, monkeypatch):
    proposal_dir = _import(env, "20260521_010000_d")
    before = _real_repo_state(env["fake_repo"])

    import core.worker_runs as _wr

    def fake_apply(project_root, plan, **kw):
        # Write a sentinel file inside the temp clone path to confirm
        # the function passed the clone path (not the real repo).
        Path(project_root, "EVIDENCE_FROM_APPLY.txt").write_text("ok", encoding="utf-8")
        return {"success": True, "applied_ops": plan, "diffs": [], "error": None}

    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    worker_runs.validate_imported_worker_proposal(proposal_dir, env["fake_repo"])

    after = _real_repo_state(env["fake_repo"])
    assert before == after, "real repo unchanged after validate"
    assert not (env["fake_repo"] / "EVIDENCE_FROM_APPLY.txt").exists()


def test_validate_failed_apply_does_not_crash(env, monkeypatch):
    proposal_dir = _import(env, "20260521_010000_e")

    import core.worker_runs as _wr

    def fake_apply(project_root, plan, **kw):
        return {"success": False, "error": "snippet not found",
                "applied_ops": [], "diffs": []}

    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    result = worker_runs.validate_imported_worker_proposal(
        proposal_dir, env["fake_repo"]
    )

    assert result["ok"] is True
    assert result["apply_success"] is False
    assert result["validation_ok"] is None
    assert (proposal_dir / "apply_result.json").is_file()
    assert (proposal_dir / "validation.json").is_file()

    item = json.loads((proposal_dir / "item.json").read_text(encoding="utf-8"))
    assert item["validation_status"] == "failed"


def test_validate_no_command_inferred_records_no_command(env, monkeypatch):
    proposal_dir = _import(env, "20260521_010000_f")

    import core.worker_runs as _wr

    def fake_apply(project_root, plan, **kw):
        return {"success": True, "applied_ops": plan, "diffs": [], "error": None}

    monkeypatch.setattr(_wr, "run_patch_plan_with_artifacts", fake_apply)
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "")

    result = worker_runs.validate_imported_worker_proposal(
        proposal_dir, env["fake_repo"]
    )

    assert result["apply_success"] is True
    assert result["validation_ok"] is None
    item = json.loads((proposal_dir / "item.json").read_text(encoding="utf-8"))
    assert item["validation_status"] == "no_command"


# ---- synthesize_lesson_artifacts_for_validated_worker_proposal (7.2.1.1) ----


def _validated_proposal(env, run_id, *, apply_success=True, validation_ok=True,
                       validation_command="echo OK"):
    """Set up an imported worker proposal with the four artifacts the
    synth helper requires. No actual subprocess work — we just lay the
    files down so the helper can read them.
    """
    proposal_dir = _import(env, run_id)
    apply_result = {
        "success": apply_success,
        "applied_ops": [
            {"op": "replace_snippet", "relative_path": "src/foo.py",
             "target_snippet": "x = 1", "patched_snippet": "x = 2"}
        ],
        "diffs": ["--- a/src/foo.py\n+++ b/src/foo.py\n@@\n-x = 1\n+x = 2\n"],
        "rollback_performed": False,
        "error": None,
    }
    validation = {
        "ok": validation_ok,
        "validation_ok": validation_ok,
        "command": validation_command,
        "duration_sec": 0.1,
        "segments": [],
        "output": "OK" if validation_ok else "AssertionError",
        "error": None,
    }
    (proposal_dir / "apply_result.json").write_text(
        json.dumps(apply_result, indent=2), encoding="utf-8"
    )
    (proposal_dir / "validation.json").write_text(
        json.dumps(validation, indent=2), encoding="utf-8"
    )
    return proposal_dir, apply_result, validation


def test_synthesize_creates_case_and_patch_proposal_after_passing_validation(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_a")
    result = worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )

    assert result["ok"] is True
    assert set(result["created"]) == {"case.json", "patch_proposal.json"}
    assert result["preserved"] == []
    assert result["skipped_reason"] is None

    case = json.loads((proposal_dir / "case.json").read_text(encoding="utf-8"))
    assert case["category"] == "worker_import"
    assert case["source"] == "worker_run"
    assert case["difficulty"] == "unknown"
    assert case["validation_command"] == "echo OK"
    # Both name keys for compatibility:
    assert case["name"] == case["case_name"]
    assert isinstance(case["name"], str) and case["name"]
    assert case["language"] == "python"  # inferred from .py extension

    proposal = json.loads((proposal_dir / "patch_proposal.json").read_text(encoding="utf-8"))
    assert proposal["source"] == "worker_run"
    assert proposal["patch_kind"] == "patch_plan"
    assert proposal["validation_ok"] is True
    assert proposal["apply_success"] is True
    assert proposal["changed_files"] == ["src/foo.py"]
    # Full patch_plan embedded so _determine_patch_kind returns "patch_plan":
    assert isinstance(proposal["patch_plan"], list) and proposal["patch_plan"]
    assert proposal["patch_candidate"] is None
    assert proposal["needs_human_review"] is False
    # Summary picks up the first useful line of proposal.md
    # (which our import writes as "# Worker proposal\n\nDo X.\n"):
    assert proposal["summary"] == "Do X."


def test_synthesize_skips_on_apply_failure(env):
    proposal_dir, _ap, val = _validated_proposal(
        env, "20260521_011000_b", apply_success=False
    )
    result = worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )
    assert result["ok"] is False
    assert result["created"] == []
    assert "apply" in (result["skipped_reason"] or "").lower()
    assert not (proposal_dir / "case.json").exists()
    assert not (proposal_dir / "patch_proposal.json").exists()


def test_synthesize_skips_on_validation_failure(env):
    proposal_dir, _ap, val = _validated_proposal(
        env, "20260521_011000_c", validation_ok=False
    )
    result = worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )
    assert result["ok"] is False
    assert result["created"] == []
    assert "validation" in (result["skipped_reason"] or "").lower()
    assert not (proposal_dir / "case.json").exists()


def test_synthesize_preserves_existing_case_json(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_d")
    existing = {"name": "preexisting", "language": "rust", "category": "manual"}
    (proposal_dir / "case.json").write_text(
        json.dumps(existing, indent=2), encoding="utf-8"
    )
    result = worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )
    assert result["ok"] is True
    assert "case.json" in result["preserved"]
    assert "case.json" not in result["created"]
    assert "patch_proposal.json" in result["created"]
    # Existing content untouched:
    case = json.loads((proposal_dir / "case.json").read_text(encoding="utf-8"))
    assert case == existing


def test_synthesize_preserves_existing_patch_proposal_json(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_e")
    existing = {"summary": "previously authored", "patch_plan": [{"op": "noop"}]}
    (proposal_dir / "patch_proposal.json").write_text(
        json.dumps(existing, indent=2), encoding="utf-8"
    )
    result = worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )
    assert result["ok"] is True
    assert "patch_proposal.json" in result["preserved"]
    assert "case.json" in result["created"]
    proposal = json.loads((proposal_dir / "patch_proposal.json").read_text(encoding="utf-8"))
    assert proposal == existing


def test_synthesize_refuses_missing_proposal_md(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_f")
    (proposal_dir / "proposal.md").unlink()
    with pytest.raises(FileNotFoundError, match="proposal.md"):
        worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
            proposal_dir, validation_result=val
        )


def test_synthesize_refuses_missing_patch_plan_json(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_g")
    (proposal_dir / "patch_plan.json").unlink()
    with pytest.raises(FileNotFoundError, match="patch_plan.json"):
        worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
            proposal_dir, validation_result=val
        )


def test_synthesize_rejects_path_traversal(env, tmp_path):
    outside = tmp_path / "outside_proposal"
    outside.mkdir()
    for f in ("proposal.md", "patch_plan.json", "apply_result.json", "validation.json"):
        (outside / f).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(outside)


def test_synthesize_infers_go_language_from_go_files(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_h")
    # Overwrite patch_plan.json with go-only ops.
    (proposal_dir / "patch_plan.json").write_text(
        json.dumps([
            {"op": "replace_snippet", "relative_path": "cmd/main.go",
             "target_snippet": "a", "patched_snippet": "b"}
        ], indent=2),
        encoding="utf-8",
    )
    worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )
    case = json.loads((proposal_dir / "case.json").read_text(encoding="utf-8"))
    assert case["language"] == "go"


def test_synthesize_summary_skips_headers_and_code_fences(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_i")
    (proposal_dir / "proposal.md").write_text(
        "# Header line\n"
        "\n"
        "```python\n"
        "code = 1\n"
        "```\n"
        "<!-- hidden comment -->\n"
        "Real summary first line.\n"
        "Trailing line.\n",
        encoding="utf-8",
    )
    worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )
    proposal = json.loads((proposal_dir / "patch_proposal.json").read_text(encoding="utf-8"))
    assert proposal["summary"] == "Real summary first line."


def test_synthesize_summary_fallback_when_proposal_md_has_no_useful_line(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_j")
    (proposal_dir / "proposal.md").write_text("# only header\n", encoding="utf-8")
    worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )
    proposal = json.loads((proposal_dir / "patch_proposal.json").read_text(encoding="utf-8"))
    assert proposal["summary"].startswith("Worker-run import:")


def test_synthesize_real_repo_byte_identical(env):
    proposal_dir, _ap, val = _validated_proposal(env, "20260521_011000_k")
    before = _real_repo_state(env["fake_repo"])
    worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir, validation_result=val
    )
    after = _real_repo_state(env["fake_repo"])
    assert before == after, "synth must not modify the real repo"


def test_synthesize_reads_validation_from_disk_when_no_in_memory_result(env):
    proposal_dir, _ap, _val = _validated_proposal(env, "20260521_011000_l")
    result = worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(
        proposal_dir  # no validation_result kwarg → read from disk
    )
    assert result["ok"] is True
    assert "case.json" in result["created"]


# ---- validate_imported_worker_proposal: lesson_artifacts wiring (7.2.1.1) ---


def test_validate_includes_lesson_artifacts_on_success(env, monkeypatch):
    proposal_dir = _import(env, "20260521_012000_a")

    import core.worker_runs as _wr
    monkeypatch.setattr(
        _wr, "run_patch_plan_with_artifacts",
        lambda project_root, plan, **kw: {
            "success": True, "applied_ops": plan,
            "diffs": [], "error": None,
        },
    )
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    result = worker_runs.validate_imported_worker_proposal(
        proposal_dir, env["fake_repo"]
    )

    assert result["apply_success"] is True
    assert result["validation_ok"] is True
    assert "lesson_artifacts" in result
    la = result["lesson_artifacts"]
    assert la["ok"] is True
    assert set(la["created"]) == {"case.json", "patch_proposal.json"}
    assert la["skipped_reason"] is None


def test_validate_lesson_artifacts_skipped_when_validation_failed(env, monkeypatch):
    proposal_dir = _import(env, "20260521_012000_b")

    import core.worker_runs as _wr

    class FailValidation:
        ok = False
        validation_ok = False

    monkeypatch.setattr(
        _wr, "run_patch_plan_with_artifacts",
        lambda project_root, plan, **kw: {
            "success": True, "applied_ops": plan, "diffs": [], "error": None,
        },
    )
    monkeypatch.setattr(_wr, "_inferred_validation_command", lambda repo: "echo OK")

    # Make _run_validation_command return a failing record by monkeypatching
    # the import inside validate_imported_worker_proposal. Easiest: patch the
    # source module's function so the lazy import picks up our stub.
    import scripts.run_patch_proposal_queue as _ppq
    monkeypatch.setattr(_ppq, "_run_validation_command",
                        lambda *a, **kw: {
                            "ok": False, "validation_ok": False,
                            "command": "echo OK", "duration_sec": 0.0,
                            "segments": [], "output": "FAIL", "error": None,
                        })

    result = worker_runs.validate_imported_worker_proposal(
        proposal_dir, env["fake_repo"]
    )

    assert result["apply_success"] is True
    assert result["validation_ok"] is False
    la = result["lesson_artifacts"]
    assert la["ok"] is False
    assert la["created"] == []
    assert "validation" in (la["skipped_reason"] or "").lower()
    # No case.json / patch_proposal.json should have been written.
    assert not (proposal_dir / "case.json").exists()
    assert not (proposal_dir / "patch_proposal.json").exists()
