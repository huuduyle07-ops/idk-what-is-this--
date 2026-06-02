"""Phase 6.4e tests: optional, gated creation of repo-scoped lesson CANDIDATES
from Dream/proposal artifacts via core.lesson_auto_candidates.

Core rule under test:
  * Auto-CREATE candidate lessons is allowed.
  * Auto-PROMOTE to active lessons is NEVER allowed.

Isolation mirrors tests/test_seed_lessons_from_proposals.py: monkeypatch
lesson_store.get_agent_dir to a tmp .agent dir, force LESSON_AUTO_ACTIVE=False,
and point the proposal seeder's DEFAULT_PROPOSALS_ROOT at a tmp dir.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import config
from core import lesson_auto_candidates as lac
from core import lesson_store
from scripts import seed_lessons_from_proposals as seeder

THIS_FILE = Path(__file__).resolve()
MODULE_PATH = THIS_FILE.parents[1] / "core" / "lesson_auto_candidates.py"


# ---------------------------------------------------------------------------
# Shared artifact builders
# ---------------------------------------------------------------------------
def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _proposal_dir(root: Path, run: str = "20260601_120000", item: str = "01-python-discount") -> Path:
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
                {"op": "replace_snippet", "relative_path": f, "target_snippet": "old", "patched_snippet": "new"}
                for f in changed_files
            ],
            "needs_human_review": False,
        },
        "apply_result.json": {
            "success": apply_success,
            "applied_ops": [
                {"op": "replace_snippet", "relative_path": f, "target_snippet": "old", "patched_snippet": "new"}
                for f in changed_files
            ],
            "diffs": [f"--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n-old\n+new\n" for f in changed_files],
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


def _write_dream_item(
    item_dir: Path,
    *,
    validation_ok: bool = True,
    apply_success: bool = True,
    rollback: bool = False,
    changed_files: list[str] | None = None,
    with_revalidation: bool = True,
    embed_candidate: bool = True,
) -> None:
    changed_files = list(changed_files or ["src/app.py"])
    item_dir.mkdir(parents=True, exist_ok=True)
    plan = [
        {"op": "replace_snippet", "relative_path": f, "target_snippet": "old", "patched_snippet": "new"}
        for f in changed_files
    ]
    _write_json(item_dir / "patch_plan.json", plan)
    (item_dir / "diff.txt").write_text("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
    (item_dir / "validation.log").write_text("OK" if validation_ok else "FAIL", encoding="utf-8")
    if not with_revalidation:
        return
    diffs = [f"--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n-old\n+new\n" for f in changed_files]
    candidate = {
        "validation_ok": validation_ok,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_plan",
        "rollback_happened": rollback,
        "changed_files": changed_files,
        "diff": "\n".join(diffs),
        "diffs": diffs,
    }
    artifact = {
        "ok": apply_success,
        "success": apply_success,
        "message": "Revalidation completed.",
        "error": None if apply_success else "apply failed",
        "validation_command": "python -m pytest -q",
        "validation_ok": validation_ok,
        "validation_output": "OK" if validation_ok else "FAIL",
        "changed_files": changed_files,
        "rollback_performed": rollback,
        "diff": "\n".join(diffs),
        "diffs": diffs,
        "failed_op_index": None,
        "failed_op": None,
        "lesson_evaluation": {"promotion": "auto_approved"},
    }
    if embed_candidate:
        artifact["lesson_candidate"] = candidate
    _write_json(item_dir / "patch_revalidation_pass1.json", artifact)


def _lesson_files(repo: Path) -> list[Path]:
    lessons_root = repo / ".agent" / "lessons"
    if not lessons_root.exists():
        return []
    return sorted(lessons_root.rglob("*.json"))


def _configure_env(tmp_path, monkeypatch):
    agent_dir = tmp_path / ".agent"
    proposals_root = agent_dir / "proposals"
    dreams_root = agent_dir / "dreams"
    proposals_root.mkdir(parents=True)
    dreams_root.mkdir(parents=True)
    monkeypatch.setattr(lesson_store, "get_agent_dir", lambda repo_path=None: agent_dir)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    monkeypatch.setattr(seeder, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(seeder, "DEFAULT_REPORTS_ROOT", agent_dir / "reports")
    return proposals_root, dreams_root


# ===========================================================================
# 1. Disabled flag is an EXACT no-op.
# ===========================================================================
def test_disabled_flag_is_exact_noop(tmp_path, monkeypatch):
    _configure_env(tmp_path, monkeypatch)
    # Bogus, nonexistent ref: a true no-op must not even touch the filesystem.
    result = lac.maybe_create_lesson_candidate_from_proposal(
        tmp_path / "does" / "not" / "exist",
        repo_path=str(tmp_path),
    )
    dream_result = lac.maybe_create_lesson_candidate_from_dream_item(
        tmp_path / "nope",
        repo_path=str(tmp_path),
    )

    assert result["status"] == "disabled"
    assert dream_result["status"] == "disabled"
    assert lesson_store.list_lessons() == []
    assert _lesson_files(tmp_path) == []


# ===========================================================================
# 2. Validated proposal creates a repo-scoped candidate.
# ===========================================================================
def test_validated_proposal_creates_repo_scoped_candidate(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo), worker_run_id="worker-123")

    result = lac.maybe_create_lesson_candidate_from_proposal(
        item_dir, repo_path=str(repo), enabled=True
    )

    assert result["status"] == "created"
    assert result["source"] == "proposal_artifact"
    assert result["scope"] == "repo"
    assert result["source_key"]
    assert result["lesson_id"]
    assert result["active_knowledge_allowed"] is False

    lessons = lesson_store.list_lessons(status="candidate", repo_path=str(repo), include_global=False)
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson["source"] == "proposal_artifact"
    assert lesson["scope"] == "repo"
    assert lesson["active_knowledge_allowed"] is False


# ===========================================================================
# 3. Duplicate source_key is skipped.
# ===========================================================================
def test_duplicate_source_key_is_skipped(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))

    first = lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)
    second = lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)

    assert first["status"] == "created"
    assert second["status"] == "duplicate"
    assert second["source_key"] == first["source_key"]
    assert len(lesson_store.list_lessons(repo_path=str(repo), include_global=False)) == 1


# ===========================================================================
# 4. Incomplete proposal is skipped with a reason.
# ===========================================================================
def test_incomplete_proposal_is_skipped_with_reason(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo), omit=("patch_proposal.json",))

    result = lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)

    assert result["status"] == "skipped"
    assert result["reason"] == "missing_artifacts"
    assert lesson_store.list_lessons() == []


# ===========================================================================
# 5. Failed validation is skipped by default.
# ===========================================================================
def test_failed_validation_is_skipped_by_default(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo), validation_ok=False)

    result = lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)

    assert result["status"] == "skipped"
    assert result["reason"] == "failed_or_incomplete_evidence"
    assert lesson_store.list_lessons() == []


# ===========================================================================
# 6. include_failed routes through lesson_quality and never creates active.
# ===========================================================================
def test_include_failed_never_creates_active_knowledge(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo), validation_ok=False)

    result = lac.maybe_create_lesson_candidate_from_proposal(
        item_dir, repo_path=str(repo), enabled=True, include_failed=True
    )

    assert result["status"] == "blocked"
    assert result["active_knowledge_allowed"] is False
    assert lesson_store.list_lessons(status="active") == []
    blocked = lesson_store.list_lessons(status="blocked", repo_path=str(repo), include_global=False)
    assert len(blocked) == 1
    assert blocked[0]["evaluation"]["promotion"] == "blocked"


# ===========================================================================
# 7. Global candidate requires the explicit flag.
# ===========================================================================
def test_global_candidate_requires_explicit_flag(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=None, project_tag=None)

    default = lac.maybe_create_lesson_candidate_from_proposal(item_dir, enabled=True)
    glob = lac.maybe_create_lesson_candidate_from_proposal(item_dir, enabled=True, global_candidate=True)

    assert default["status"] == "skipped"
    assert default["reason"] in {"missing_repo_path", "missing_repo_scope"}
    assert glob["status"] == "created"
    assert glob["scope"] == "global"
    lesson = lesson_store.list_lessons(scope="global")[0]
    assert lesson["scope"] == "global"
    assert lesson["candidate"].get("repo_path") is None


# ===========================================================================
# 8. Candidate passes through lesson_quality (evaluation is recorded).
# ===========================================================================
def test_candidate_passes_through_lesson_quality(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))

    result = lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)

    assert result["promotion"] in {"auto_approved", "needs_human_review", "blocked"}
    lesson = lesson_store.list_lessons(repo_path=str(repo), include_global=False)[0]
    assert isinstance(lesson.get("evaluation"), dict)
    assert lesson["evaluation"].get("promotion") == result["promotion"]


# ===========================================================================
# 9. active_knowledge_allowed remains false on the stored record.
# ===========================================================================
def test_active_knowledge_allowed_remains_false(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))

    # Even if an operator left LESSON_AUTO_ACTIVE on, candidates must not go active.
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)
    lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)

    assert lesson_store.list_lessons(status="active") == []
    lesson = lesson_store.list_lessons(repo_path=str(repo), include_global=False)[0]
    assert lesson["status"] == "candidate"
    assert lesson["active_knowledge_allowed"] is False


# ===========================================================================
# 10. Source artifacts are byte-identical before/after (proposal AND dream).
# ===========================================================================
def test_source_artifacts_are_byte_identical(tmp_path, monkeypatch):
    proposals_root, dreams_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))
    dream_dir = dreams_root / "2026-06-01" / "120000-run" / "01-fix"
    _write_dream_item(dream_dir)

    def _snapshot(d: Path) -> dict[str, bytes]:
        return {p.name: p.read_bytes() for p in sorted(d.glob("*"))}

    prop_before = _snapshot(item_dir)
    dream_before = _snapshot(dream_dir)

    lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)
    lac.maybe_create_lesson_candidate_from_dream_item(
        dream_dir, repo_path=str(repo), enabled=True, dreams_root=dreams_root
    )

    assert _snapshot(item_dir) == prop_before
    assert _snapshot(dream_dir) == dream_before


# ===========================================================================
# 11. LESSON_RETRIEVAL_ENABLED is never mutated.
# ===========================================================================
def test_lesson_retrieval_enabled_is_never_mutated(tmp_path, monkeypatch):
    proposals_root, dreams_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))
    dream_dir = dreams_root / "2026-06-01" / "120000-run" / "01-fix"
    _write_dream_item(dream_dir)

    before = config.LESSON_RETRIEVAL_ENABLED
    lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)
    lac.maybe_create_lesson_candidate_from_dream_item(
        dream_dir, repo_path=str(repo), enabled=True, dreams_root=dreams_root
    )
    assert config.LESSON_RETRIEVAL_ENABLED is before


# ===========================================================================
# 12. CLI returns friendly created/skipped JSON.
# ===========================================================================
def test_cli_returns_friendly_json(tmp_path, monkeypatch, capsys):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))

    from scripts import create_lesson_candidate as cli

    exit_code = cli._main(["--proposal-dir", str(item_dir), "--repo-path", str(repo)])
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert exit_code == 0
    assert payload["status"] == "created"
    assert payload["scope"] == "repo"
    assert payload["source_key"]
    assert "reason" in payload


def test_route_returns_friendly_json(tmp_path, monkeypatch):
    proposals_root, _dreams = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))

    from web.app import app

    client = app.test_client()
    resp = client.post(
        "/lessons/create-candidate-from-proposal",
        data={"proposal_dir": str(item_dir), "repo_path": str(repo)},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["result"]["status"] == "created"
    assert body["result"]["scope"] == "repo"
    assert body["result"]["active_knowledge_allowed"] is False


# ===========================================================================
# 13. Path-traversal refs are rejected (no crash, friendly skip).
# ===========================================================================
def test_path_traversal_proposal_ref_is_rejected(tmp_path, monkeypatch):
    _configure_env(tmp_path, monkeypatch)
    result = lac.maybe_create_lesson_candidate_from_proposal("..\\evil", repo_path=str(tmp_path), enabled=True)
    assert result["status"] == "skipped"
    assert "traversal" in (result["reason"] or "").lower() or "outside" in (result["reason"] or "").lower()
    assert lesson_store.list_lessons() == []


def test_path_traversal_dream_ref_is_rejected(tmp_path, monkeypatch):
    _proposals, dreams_root = _configure_env(tmp_path, monkeypatch)
    result = lac.maybe_create_lesson_candidate_from_dream_item(
        "../../evil", repo_path=str(tmp_path), enabled=True, dreams_root=dreams_root
    )
    assert result["status"] == "skipped"
    assert "traversal" in (result["reason"] or "").lower() or "outside" in (result["reason"] or "").lower()
    assert lesson_store.list_lessons() == []


# ===========================================================================
# Dream path — happy path, duplicate, failed-by-default.
# ===========================================================================
def test_validated_dream_item_creates_repo_scoped_candidate(tmp_path, monkeypatch):
    _proposals, dreams_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    dream_dir = dreams_root / "2026-06-01" / "120000-run" / "01-fix-discount"
    _write_dream_item(dream_dir, changed_files=["src/pricing.py"])
    record = {
        "idx": 1,
        "status": "ready_to_apply",
        "title": "Fix discount path",
        "summary": "Discount validation bug",
        "case_name": "python_discount",
        "language": "python",
        "category": "logic_validation",
        "item_dir": str(dream_dir),
    }

    result = lac.maybe_create_lesson_candidate_from_dream_item(
        record, repo_path=str(repo), enabled=True, dreams_root=dreams_root
    )

    assert result["status"] == "created"
    assert result["source"] == "dream_artifact"
    assert result["scope"] == "repo"
    assert result["source_key"].startswith("dream:")
    assert result["active_knowledge_allowed"] is False
    lessons = lesson_store.list_lessons(status="candidate", repo_path=str(repo), include_global=False)
    assert len(lessons) == 1
    assert lessons[0]["source"] == "dream_artifact"


def test_dream_duplicate_source_key_is_skipped(tmp_path, monkeypatch):
    _proposals, dreams_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    dream_dir = dreams_root / "2026-06-01" / "120000-run" / "01-fix"
    _write_dream_item(dream_dir)

    first = lac.maybe_create_lesson_candidate_from_dream_item(
        dream_dir, repo_path=str(repo), enabled=True, dreams_root=dreams_root
    )
    second = lac.maybe_create_lesson_candidate_from_dream_item(
        dream_dir, repo_path=str(repo), enabled=True, dreams_root=dreams_root
    )

    assert first["status"] == "created"
    assert second["status"] == "duplicate"
    assert len(lesson_store.list_lessons(repo_path=str(repo), include_global=False)) == 1


def test_dream_failed_validation_skipped_by_default(tmp_path, monkeypatch):
    _proposals, dreams_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    dream_dir = dreams_root / "2026-06-01" / "120000-run" / "01-fix"
    _write_dream_item(dream_dir, validation_ok=False, apply_success=True)

    result = lac.maybe_create_lesson_candidate_from_dream_item(
        dream_dir, repo_path=str(repo), enabled=True, dreams_root=dreams_root
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "failed_or_incomplete_evidence"
    assert lesson_store.list_lessons() == []


def test_dream_no_revalidation_artifact_is_skipped(tmp_path, monkeypatch):
    _proposals, dreams_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    dream_dir = dreams_root / "2026-06-01" / "120000-run" / "01-fix"
    _write_dream_item(dream_dir, with_revalidation=False)

    result = lac.maybe_create_lesson_candidate_from_dream_item(
        dream_dir, repo_path=str(repo), enabled=True, dreams_root=dreams_root
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "no_revalidation_evidence"
    assert lesson_store.list_lessons() == []


# ===========================================================================
# 14. AST guard: the new module introduces no forbidden behavior.
# ===========================================================================
def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def _assigned_names(tree: ast.AST) -> set[str]:
    assigned: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
                elif isinstance(target, ast.Attribute):
                    assigned.add(target.attr)
    return assigned


def test_lesson_auto_candidates_ast_guard():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    calls = _called_names(tree)
    assigned = _assigned_names(tree)

    imported_roots = {name.split(".", 1)[0] for name in imports}
    forbidden_import_roots = {
        "agents", "benchmarks", "database", "docker", "google",
        "openai", "requests", "httpx", "subprocess", "socket",
    }
    assert imported_roots.isdisjoint(forbidden_import_roots)

    forbidden_imports = {
        "core.sleeping_consultant",
        "core.run_lifecycle",
        "core.prompter",
        "core.control_engine",
        "patching.patch_plan_executor",
        "patching",
    }
    assert imports.isdisjoint(forbidden_imports)

    forbidden_calls = {
        "run_patch_plan_with_artifacts", "apply_patch_plan",
        "run_benchmarks", "run_benchmark", "run_gemini", "run_gemini_request_2",
        "run_ollama", "ChatCompletion", "generate_content",
        "build_control_prompt", "build_prompt", "build_deepseek_review",
        "Popen", "check_call", "check_output", "system",
        "promote_lesson",
    }
    assert calls.isdisjoint(forbidden_calls)

    # The module may force LESSON_AUTO_ACTIVE=False (the safety mechanism) but
    # must NEVER assign the retrieval-enable flag.
    assert "LESSON_RETRIEVAL_ENABLED" not in assigned


def test_no_benchmark_runner_model_client_or_patch_executor_is_imported(tmp_path, monkeypatch):
    proposals_root, dreams_root = _configure_env(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    item_dir = _proposal_dir(proposals_root)
    _write_proposal(item_dir, repo_path=str(repo))
    dream_dir = dreams_root / "2026-06-01" / "120000-run" / "01-fix"
    _write_dream_item(dream_dir)

    guarded = (
        "benchmarks.run_benchmarks",
        "agents.gemini_client",
        "agents.ollama_client",
        "agents.deepseek_client",
        "core.sleeping_consultant",
        "core.run_lifecycle",
        "patching.patch_plan_executor",
    )
    # Use monkeypatch.delitem so the removal is auto-restored on teardown — a
    # raw sys.modules.pop would leak the absence to later test files (e.g.
    # test_run_lifecycle.py monkeypatches a symbol on core.run_lifecycle).
    for name in guarded:
        monkeypatch.delitem(sys.modules, name, raising=False)

    lac.maybe_create_lesson_candidate_from_proposal(item_dir, repo_path=str(repo), enabled=True)
    lac.maybe_create_lesson_candidate_from_dream_item(
        dream_dir, repo_path=str(repo), enabled=True, dreams_root=dreams_root
    )

    for name in guarded:
        assert name not in sys.modules, f"forbidden module imported: {name}"
