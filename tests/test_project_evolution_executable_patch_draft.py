"""B.9 Executable Evolution Patch Draft Format contract tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core import (
    project_evolution_approval,
    project_evolution_executable_patch_draft,
    project_evolution_patch_candidates,
    project_evolution_patch_draft,
    project_evolution_patch_text_draft,
    project_map_v2,
    project_migration_planner,
    project_node_summaries,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "project_evolution_executable_patch_draft.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_evolution_executable_patch_draft.py"


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-project-evolution-executable-patch-draft"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_creates_json_and_markdown_executable_patch_draft_from_matching_chain(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)

    out = project_evolution_executable_patch_draft.write_project_evolution_executable_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=str(approval),
        patch_draft_package_path=str(draft),
        patch_candidates_path=str(candidates),
        patch_text_draft_path=str(text),
    )

    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.name.endswith("_executable_patch_draft.json")
    assert md_path.name.endswith("_executable_patch_draft.md")
    draft_root = (repo / ".agent" / "project_evolution" / "executable_patch_drafts").resolve()
    json_path.resolve().relative_to(draft_root)
    md_path.resolve().relative_to(draft_root)

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record == out["record"]
    assert record["approval_verified"] is True
    assert record["executable_patch_draft_only"] is True
    assert record["source_files_mutated"] is False
    assert record["real_repo_apply_allowed"] is False
    assert record["sandbox_apply_allowed_later"] is True
    assert record["validation_execution_allowed"] is False
    assert record["requires_patch_safety_before_apply"] is True
    assert record["requires_sandbox_before_validation"] is True
    assert record["target_files"]
    assert record["executable_edit_units"]
    assert "No patch was generated, applied, validated, or committed." in md_path.read_text(encoding="utf-8")


def test_refuses_when_approval_is_missing(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_chain(repo)

    missing_approval = repo / ".agent" / "project_evolution" / "approvals" / "missing.json"
    out = project_evolution_executable_patch_draft.build_project_evolution_executable_patch_draft(
        repo_path=str(repo),
        approval_path=str(missing_approval),
        patch_draft_package_path=str(repo / ".agent" / "project_evolution" / "patch_drafts" / "missing.json"),
        patch_candidates_path=str(repo / ".agent" / "project_evolution" / "patch_candidates" / "missing.json"),
        patch_text_draft_path=str(repo / ".agent" / "project_evolution" / "patch_text_drafts" / "missing.json"),
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "approval_missing"


@pytest.mark.parametrize("decision", ["reject", "needs_revision"])
def test_refuses_when_approval_decision_is_not_approve(tmp_path, decision):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)
    plan_path = repo / ".agent" / "project_evolution" / "migration_plan_dry_run.json"
    gate_approval = project_evolution_approval.write_project_evolution_approval_artifacts(
        source_plan_path=str(plan_path),
        decision=decision,
        reviewer="Gate Reviewer",
        notes=f"Decision is {decision}.",
    )["json_path"]

    out = project_evolution_executable_patch_draft.build_project_evolution_executable_patch_draft(
        repo_path=str(repo),
        approval_path=str(gate_approval),
        patch_draft_package_path=str(draft),
        patch_candidates_path=str(candidates),
        patch_text_draft_path=str(text),
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "approval_not_approved"


def test_refuses_when_plan_hash_mismatches_approval(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)
    _seed_plan(repo, goal="Migrate search graph weights to a new ranking strategy")

    out = project_evolution_executable_patch_draft.build_project_evolution_executable_patch_draft(
        repo_path=str(repo),
        approval_path=str(approval),
        patch_draft_package_path=str(draft),
        patch_candidates_path=str(candidates),
        patch_text_draft_path=str(text),
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "approval_source_hash_mismatch"


def test_refuses_when_artifact_chain_mismatches(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)
    text_path = Path(text)
    text_record = json.loads(text_path.read_text(encoding="utf-8"))
    text_record["patch_candidates_path"] = str(repo / ".agent" / "project_evolution" / "patch_candidates" / "alternate.json")
    text_path.write_text(json.dumps(text_record, indent=2, ensure_ascii=False), encoding="utf-8")

    out = project_evolution_executable_patch_draft.build_project_evolution_executable_patch_draft(
        repo_path=str(repo),
        approval_path=str(approval),
        patch_draft_package_path=str(draft),
        patch_candidates_path=str(candidates),
        patch_text_draft_path=str(text),
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "text_candidates_mismatch"


def test_target_files_are_subset_of_approved_plan_draft_and_candidates(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)

    record = project_evolution_executable_patch_draft.build_project_evolution_executable_patch_draft(
        repo_path=str(repo),
        approval_path=str(approval),
        patch_draft_package_path=str(draft),
        patch_candidates_path=str(candidates),
        patch_text_draft_path=str(text),
    )

    allowed_files = _allowed_files(repo, draft, candidates, text)
    target_paths = {item["path"] for item in record["target_files"]}
    unit_paths = {item["target_file"] for item in record["executable_edit_units"]}
    assert target_paths
    assert target_paths.issubset(allowed_files)
    assert unit_paths.issubset(allowed_files)
    assert ".env" not in target_paths
    assert ".env" not in unit_paths


def test_executable_draft_flags_and_units_are_locked_down(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)

    record = project_evolution_executable_patch_draft.build_project_evolution_executable_patch_draft(
        repo_path=str(repo),
        approval_path=str(approval),
        patch_draft_package_path=str(draft),
        patch_candidates_path=str(candidates),
        patch_text_draft_path=str(text),
    )

    assert record["status"] == "ok"
    assert record["executable_patch_draft_only"] is True
    assert record["source_files_mutated"] is False
    assert record["real_repo_apply_allowed"] is False
    assert record["validation_execution_allowed"] is False
    assert all(unit["apply_allowed"] is False for unit in record["executable_edit_units"])
    assert all(unit["sandbox_only_later"] is True for unit in record["executable_edit_units"])
    assert all(unit["requires_full_file_read"] is True for unit in record["executable_edit_units"])
    assert all(unit["old_text"] is None for unit in record["executable_edit_units"])
    assert all(unit["new_text"] is None for unit in record["executable_edit_units"])
    assert all(unit["unified_diff"] is None for unit in record["executable_edit_units"])


def test_source_artifacts_are_not_mutated(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)

    plan_path = repo / ".agent" / "project_evolution" / "migration_plan_dry_run.json"
    paths = [plan_path, Path(approval), Path(draft), Path(candidates), Path(text)]
    before = {path: path.read_text(encoding="utf-8") for path in paths}

    project_evolution_executable_patch_draft.write_project_evolution_executable_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=str(approval),
        patch_draft_package_path=str(draft),
        patch_candidates_path=str(candidates),
        patch_text_draft_path=str(text),
    )

    assert before == {path: path.read_text(encoding="utf-8") for path in paths}


def test_output_path_stays_under_executable_patch_drafts(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)

    out = project_evolution_executable_patch_draft.write_project_evolution_executable_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=str(approval),
        patch_draft_package_path=str(draft),
        patch_candidates_path=str(candidates),
        patch_text_draft_path=str(text),
    )

    draft_root = (repo / ".agent" / "project_evolution" / "executable_patch_drafts").resolve()
    Path(out["json_path"]).resolve().relative_to(draft_root)
    Path(out["md_path"]).resolve().relative_to(draft_root)


def test_cli_writes_executable_patch_draft_artifacts(tmp_path, capsys):
    repo = _build_sample_repo(tmp_path)
    approval, draft, candidates, text = _seed_chain(repo)

    from scripts import create_evolution_executable_patch_draft as cli

    rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--approval-path",
            str(approval),
            "--patch-draft-package-path",
            str(draft),
            "--patch-candidates-path",
            str(candidates),
            "--patch-text-draft-path",
            str(text),
        ]
    )

    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "md_path:" in output
    assert "edit_unit_count:" in output
    assert (repo / ".agent" / "project_evolution" / "executable_patch_drafts").exists()


def test_debug_runtime_code_is_not_imported_or_wired():
    trees = [
        ast.parse(MODULE_PATH.read_text(encoding="utf-8")),
        ast.parse(SCRIPT_PATH.read_text(encoding="utf-8")),
    ]
    imports = set()
    calls = set()
    for tree in trees:
        imports.update(_imported_modules(tree))
        calls.update(_called_names(tree))

    forbidden_import_roots = {
        "agents",
        "anthropic",
        "benchmarks",
        "docker",
        "openai",
        "patching",
        "requests",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "validator",
        "web",
    }
    forbidden_imports = {
        "core.control_engine",
        "core.debug_workflow",
        "core.executor",
        "core.mode_router",
        "core.run_lifecycle",
        "core.validator",
        "database",
    }
    forbidden_calls = {
        "apply_patch",
        "apply_patch_plan",
        "build_graph_from_repo",
        "call_api",
        "call_model",
        "connect",
        "create_lesson",
        "execute",
        "executemany",
        "generate_content",
        "get_embedding",
        "index_repository",
        "promote_lesson",
        "run_benchmark",
        "run_benchmarks",
        "run_validation_command",
        "Popen",
        "system",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots)
    assert imports.isdisjoint(forbidden_imports)
    assert calls.isdisjoint(forbidden_calls)


def _seed_chain(repo: Path, *, decision: str = "approve"):
    source_plan = _seed_plan(repo)
    approval_out = project_evolution_approval.write_project_evolution_approval_artifacts(
        source_plan_path=str(source_plan),
        decision=decision,
        reviewer="Ops Lead",
        notes="Approved after dry run review.",
    )
    draft_out = project_evolution_patch_draft.write_project_evolution_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=approval_out["json_path"],
        max_files=8,
        draft_title="Embedding provider patch draft",
        notes="Generated from the approved Project Evolution plan.",
    )
    candidates_out = project_evolution_patch_candidates.write_project_evolution_patch_candidate_artifacts(
        repo_path=str(repo),
        approval_path=approval_out["json_path"],
        patch_draft_package_path=draft_out["json_path"],
        max_candidates=8,
    )
    text_out = project_evolution_patch_text_draft.write_project_evolution_patch_text_draft_artifacts(
        repo_path=str(repo),
        approval_path=approval_out["json_path"],
        patch_draft_package_path=draft_out["json_path"],
        patch_candidates_path=candidates_out["json_path"],
        max_files=8,
    )
    return (
        Path(approval_out["json_path"]),
        Path(draft_out["json_path"]),
        Path(candidates_out["json_path"]),
        Path(text_out["json_path"]),
    )


def _seed_plan(repo: Path, goal: str | None = None) -> Path:
    goal_text = goal or "Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction"
    project_map_v2.write_project_map_v2_artifacts(str(repo), max_full_file_candidates=80)
    project_node_summaries.write_project_node_summaries_artifacts(str(repo))
    out = project_migration_planner.write_migration_plan_dry_run_artifacts(
        repo_path=str(repo),
        goal=goal_text,
        max_files=8,
    )
    return Path(out["json_path"])


def _build_sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_repo"
    repo.mkdir()

    files = {
        "README.md": "# Sample Repo\n",
        "CHANGELOG.md": "## 0.1.0\n",
        "package.json": '{ "name": "sample-app" }\n',
        "pyproject.toml": "[project]\nname='sample'\n",
        "requirements.txt": "fastapi==0.1\npydantic==2.0\n",
        ".env.example": "OPENAI_API_KEY=demo\nDATABASE_URL=postgres://localhost/db\nPROVIDER_ID=mock\n",
        ".env": "OPENAI_API_KEY=TOP_SECRET_VALUE\nDATABASE_URL=postgres://super-secret\n",
        "Dockerfile": "FROM python:3.11\n",
        "docker-compose.yml": "services:\n  app:\n    environment:\n      - DATABASE_URL\n",
        "config.py": "import os\nPROVIDER_ID = os.getenv('PROVIDER_ID')\n",
        "settings.py": "import os\nDATABASE_URL = os.getenv('DATABASE_URL')\n",
        "pytest.ini": "[pytest]\n",
        "main.py": "from web.app import app\n",
        "web/app.py": "app = object()\n",
        "core/indexer.py": "def index_repository():\n    return 'index'\n",
        "core/repo_librarian.py": "def inspect_repo_inventory():\n    return {}\n",
        "graph/project_map.py": "def build_project_map():\n    return ''\n",
        "graph/weights.py": "def rank_nodes_by_weight():\n    return []\n",
        "retrieval/provider_router.py": "class ProviderRouter:\n    pass\n",
        "tests/test_project_map_v2.py": "def test_map():\n    assert True\n",
        "tests/integration/test_provider_migration.py": "def test_provider_migration():\n    assert True\n",
        "docs/project_evolution_mode.md": "# Evolution\n",
        "docs/project_map_upgrade_plan.md": "# Upgrade Plan\n",
        "docs/architecture.md": "# Architecture\n",
    }

    for index in range(10):
        files[f"providers/provider_{index:02d}.py"] = (
            f"class Provider{index:02d}:\n    pass\n"
        )

    for rel_path, content in files.items():
        path = repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return repo


def _allowed_files(repo: Path, draft: Path, candidates: Path, text: Path) -> set[str]:
    plan_path = repo / ".agent" / "project_evolution" / "migration_plan_dry_run.json"
    plan_record = json.loads(plan_path.read_text(encoding="utf-8"))
    draft_record = json.loads(Path(draft).read_text(encoding="utf-8"))
    candidates_record = json.loads(Path(candidates).read_text(encoding="utf-8"))
    text_record = json.loads(Path(text).read_text(encoding="utf-8"))
    allowed: set[str] = set()
    for collection in (
        plan_record.get("likely_affected_files", []),
        plan_record.get("full_files_to_read_before_patching", []),
        draft_record.get("likely_files_to_change", []),
        draft_record.get("files_to_read_first", []),
        text_record.get("files_to_read_first", []),
    ):
        allowed.update(item["path"] for item in collection if isinstance(item, dict) and item.get("path"))
    for candidate in candidates_record.get("candidates", []):
        allowed.update(item["path"] for item in candidate.get("target_files", []) if isinstance(item, dict) and item.get("path"))
    for draft_item in text_record.get("patch_text_drafts", []):
        allowed.update(item["path"] for item in draft_item.get("target_files", []) if isinstance(item, dict) and item.get("path"))
    return allowed


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
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
