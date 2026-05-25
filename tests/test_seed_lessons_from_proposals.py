"""Phase 6.4c tests: seed lesson candidates from proposal artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from core import lesson_store
from scripts import seed_lessons_from_proposals as seeder


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _proposal_dir(
    root: Path,
    run: str = "20260525_120000",
    item: str = "01-python-discount",
) -> Path:
    return root / run / item


def _write_proposal(
    item_dir: Path,
    *,
    repo_path: str | None = None,
    project_tag: str | None = None,
    worker_run_id: str | None = "worker-run-1",
    validation_ok: bool = True,
    apply_success: bool = True,
    changed_files: list[str] | None = None,
    omit: tuple[str, ...] = (),
) -> None:
    changed_files = list(changed_files or ["pricing.py"])
    item = {
        "kind": "worker_run_import",
        "case_name": "python_discount_validation",
        "language": "python",
        "category": "logic_validation",
        "difficulty": "easy",
    }
    if repo_path:
        item["repo_path"] = repo_path
    if project_tag:
        item["project_tag"] = project_tag
    if worker_run_id:
        item["source_run_id"] = worker_run_id

    files: dict[str, dict] = {
        "item.json": item,
        "case.json": {
            "name": "python_discount_validation",
            "language": "python",
            "category": "logic_validation",
            "difficulty": "easy",
            "expected_changed_files": ["pricing.py"],
            "forbidden_changed_files": ["main.py"],
        },
        "patch_proposal.json": {
            "summary": "Fix the discount validation path.",
            "patch_candidate": None,
            "patch_plan": [
                {
                    "op": "replace_snippet",
                    "relative_path": f,
                    "target_snippet": "old",
                    "patched_snippet": "new",
                }
                for f in changed_files
            ],
            "needs_human_review": False,
        },
        "apply_result.json": {
            "success": apply_success,
            "applied_ops": [
                {
                    "op": "replace_snippet",
                    "relative_path": f,
                    "target_snippet": "old",
                    "patched_snippet": "new",
                }
                for f in changed_files
            ],
            "diffs": [
                f"--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n-old\n+new\n"
                for f in changed_files
            ],
            "rollback_performed": False,
            "error": None if apply_success else "patch did not apply",
        },
        "validation.json": {
            "ok": validation_ok,
            "validation_ok": validation_ok,
            "command": "python main.py",
            "duration_sec": 0.2,
            "output": "OK" if validation_ok else "AssertionError: failed",
        },
        "source_metadata.json": {
            "source": "worker_run",
            "source_run_id": worker_run_id,
            "repo_path": repo_path,
            "project_tag": project_tag,
        },
    }
    for name, payload in files.items():
        if name in omit:
            continue
        _write_json(item_dir / name, payload)


def _lesson_files(repo: Path) -> list[Path]:
    lessons_root = repo / ".agent" / "lessons"
    if not lessons_root.exists():
        return []
    return sorted(lessons_root.rglob("*.json"))


def _configure_env(tmp_path, monkeypatch):
    agent_dir = tmp_path / ".agent"
    proposals_root = agent_dir / "proposals"
    reports_root = agent_dir / "reports"
    proposals_root.mkdir(parents=True)
    monkeypatch.setattr(
        lesson_store,
        "get_agent_dir",
        lambda repo_path=None: agent_dir,
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    monkeypatch.setattr(seeder, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(seeder, "DEFAULT_REPORTS_ROOT", reports_root)
    return proposals_root, reports_root


def test_dry_run_creates_no_lesson_files(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))

    summary = seeder.seed_lessons_from_proposals(
        proposal_refs=[item_dir],
        dry_run=True,
    )

    assert summary["counts"]["dry_run"] == 1
    assert summary["counts"]["created"] == 0
    assert _lesson_files(tmp_path) == []


def test_validated_proposal_creates_repo_scoped_candidate(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pricing.py").write_text("PRICE = 1\n", encoding="utf-8")
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo), worker_run_id="worker-123")

    summary = seeder.seed_lessons_from_proposals(proposal_refs=[item_dir])

    assert summary["counts"]["created"] == 1
    lessons = lesson_store.list_lessons(status="candidate")
    assert len(lessons) == 1
    lesson = lessons[0]
    candidate = lesson["candidate"]
    assert lesson["source"] == "proposal_artifact"
    assert candidate["source"] == "proposal_artifact"
    assert candidate["scope"] == "repo"
    assert candidate["repo_path"] == str(repo)
    assert candidate["project_tag"].startswith("repo-")
    assert candidate["proposal_ref"] == "20260525_120000/01-python-discount"
    assert candidate["worker_run_id"] == "worker-123"
    assert candidate["changed_files"] == ["pricing.py"]
    assert candidate["patch_summary"] == "Fix the discount validation path."
    assert lesson["active_knowledge_allowed"] is False
    assert "python" in lesson["tags"]


def test_incomplete_proposal_is_skipped(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo), omit=("patch_proposal.json",))

    summary = seeder.seed_lessons_from_proposals(proposal_refs=[item_dir])

    assert summary["counts"]["skipped"] == 1
    assert summary["skipped"][0]["reason"] == "missing_artifacts"
    assert lesson_store.list_lessons() == []


def test_failed_validation_is_skipped_by_default(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo), validation_ok=False)

    summary = seeder.seed_lessons_from_proposals(proposal_refs=[item_dir])

    assert summary["counts"]["skipped"] == 1
    assert summary["skipped"][0]["reason"] == "failed_or_incomplete_evidence"
    assert lesson_store.list_lessons() == []


def test_include_failed_goes_through_lesson_quality_never_active(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo), validation_ok=False)

    summary = seeder.seed_lessons_from_proposals(
        proposal_refs=[item_dir],
        include_failed=True,
    )

    assert summary["counts"]["blocked"] == 1
    assert lesson_store.list_lessons(status="active") == []
    blocked = lesson_store.list_lessons(status="blocked")
    assert len(blocked) == 1
    assert blocked[0]["evaluation"]["promotion"] == "blocked"
    assert blocked[0]["candidate"]["validation_ok"] is False


def test_duplicate_source_key_prevents_repeated_candidate_spam(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))

    first = seeder.seed_lessons_from_proposals(proposal_refs=[item_dir])
    second = seeder.seed_lessons_from_proposals(proposal_refs=[item_dir])

    assert first["counts"]["created"] == 1
    assert second["counts"]["duplicates"] == 1
    assert len(lesson_store.list_lessons()) == 1


def test_global_candidate_requires_explicit_flag(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=None, project_tag=None)

    default_summary = seeder.seed_lessons_from_proposals(proposal_refs=[item_dir])
    global_summary = seeder.seed_lessons_from_proposals(
        proposal_refs=[item_dir],
        global_candidate=True,
    )

    assert default_summary["counts"]["skipped"] == 1
    assert default_summary["skipped"][0]["reason"] == "missing_repo_scope"
    assert global_summary["counts"]["created"] == 1
    lesson = lesson_store.list_lessons()[0]
    assert lesson["candidate"]["scope"] == "global"
    assert lesson["candidate"].get("repo_path") is None


def test_path_traversal_in_proposal_ref_is_blocked(tmp_path, monkeypatch, capsys):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, project_tag="project-x")

    exit_code = seeder._main(["--proposal-ref", "..\\evil"])

    assert exit_code == 2
    err = capsys.readouterr().err
    assert "outside" in err or "path traversal" in err


def test_source_proposal_artifacts_are_not_modified(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))
    before = {
        path.name: path.read_text(encoding="utf-8")
        for path in item_dir.glob("*.json")
    }

    seeder.seed_lessons_from_proposals(proposal_refs=[item_dir])

    after = {
        path.name: path.read_text(encoding="utf-8")
        for path in item_dir.glob("*.json")
    }
    assert after == before


def test_no_benchmark_runner_model_client_or_patch_executor_is_called(tmp_path, monkeypatch):
    proposals_root, _reports_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))
    for name in (
        "benchmarks.run_benchmarks",
        "agents.gemini_client",
        "agents.ollama_client",
        "agents.deepseek_client",
        "core.run_lifecycle",
        "patching.patch_plan_executor",
    ):
        sys.modules.pop(name, None)

    seeder.seed_lessons_from_proposals(proposal_refs=[item_dir])

    assert "benchmarks.run_benchmarks" not in sys.modules
    assert "agents.gemini_client" not in sys.modules
    assert "agents.ollama_client" not in sys.modules
    assert "agents.deepseek_client" not in sys.modules
    assert "core.run_lifecycle" not in sys.modules
    assert "patching.patch_plan_executor" not in sys.modules
