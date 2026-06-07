"""B.5 Approval-Gated Evolution Patch Draft Package contract tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core import project_evolution_approval, project_evolution_patch_draft, project_map_v2, project_migration_planner, project_node_summaries


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "project_evolution_patch_draft.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_evolution_patch_draft.py"


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-project-evolution-patch-draft"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_creates_json_and_markdown_draft_package_from_approved_matching_plan(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(repo, decision="approve")

    out = project_evolution_patch_draft.write_project_evolution_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=str(approval),
        max_files=8,
        draft_title="Embedding provider patch draft",
        notes="Operator notes for the later patch phase.",
    )

    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.name.endswith("_patch_draft_package.json")
    assert md_path.name.endswith("_patch_draft_package.md")
    approvals_root = (repo / ".agent" / "project_evolution" / "patch_drafts").resolve()
    json_path.resolve().relative_to(approvals_root)
    md_path.resolve().relative_to(approvals_root)

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record == out["record"]
    assert record["draft_package_only"] is True
    assert record["patch_generation_allowed"] is False
    assert record["patch_apply_allowed"] is False
    assert record["validation_execution_allowed"] is False
    assert "This is a draft package only. No patch was generated, applied, or validated." in md_path.read_text(encoding="utf-8")


def test_refuses_when_approval_is_missing(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_plan(repo)
    missing_approval = repo / ".agent" / "project_evolution" / "approvals" / "missing.json"

    out = project_evolution_patch_draft.write_project_evolution_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=str(missing_approval),
        max_files=8,
    )

    assert out["record"]["status"] == "error"
    assert out["record"]["error"]["code"] == "approval_missing"
    assert out["json_path"] == ""
    assert out["md_path"] == ""
    assert not (repo / ".agent" / "project_evolution" / "patch_drafts").exists()


def test_approval_path_traversal_is_rejected(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_plan(repo)

    out = project_evolution_patch_draft.build_project_evolution_patch_draft_package(
        repo_path=str(repo),
        approval_path=r"..\outside.json",
        max_files=8,
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "approval_path_outside_approvals"


@pytest.mark.parametrize("decision", ["reject", "needs_revision"])
def test_refuses_when_approval_decision_is_not_approve(tmp_path, decision):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(repo, decision=decision)

    out = project_evolution_patch_draft.build_project_evolution_patch_draft_package(
        repo_path=str(repo),
        approval_path=str(approval),
        max_files=8,
    )

    assert out["status"] == "error"
    assert "approval decision must be approve" in out["error"]["message"]


def test_refuses_when_source_plan_hash_does_not_match_approval_hash(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(
        repo,
        decision="approve",
        goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
    )

    _seed_plan(
        repo,
        goal="Migrate search graph weights to a new ranking strategy",
    )

    out = project_evolution_patch_draft.build_project_evolution_patch_draft_package(
        repo_path=str(repo),
        approval_path=str(approval),
        max_files=8,
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "approval_source_hash_mismatch"


def test_draft_package_sets_required_boolean_gates_and_does_not_emit_patch_content(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(repo, decision="approve")

    record = project_evolution_patch_draft.build_project_evolution_patch_draft_package(
        repo_path=str(repo),
        approval_path=str(approval),
        max_files=8,
    )

    assert record["status"] == "ok"
    assert record["patch_generation_allowed"] is False
    assert record["patch_apply_allowed"] is False
    assert record["validation_execution_allowed"] is False
    assert record["draft_package_only"] is True
    assert "patch_candidate" not in json.dumps(record)
    assert "unified_diff" not in json.dumps(record)


def test_likely_files_come_from_migration_plan_fields_only(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(repo, decision="approve")

    record = project_evolution_patch_draft.build_project_evolution_patch_draft_package(
        repo_path=str(repo),
        approval_path=str(approval),
        max_files=5,
    )

    source_plan = json.loads((repo / ".agent" / "project_evolution" / "migration_plan_dry_run.json").read_text(encoding="utf-8"))
    source_paths = {
        item["path"]
        for item in source_plan.get("likely_affected_files", [])
        if isinstance(item, dict) and item.get("path")
    } | {
        item["path"]
        for item in source_plan.get("full_files_to_read_before_patching", [])
        if isinstance(item, dict) and item.get("path")
    }
    selected_paths = {item["path"] for item in record["likely_files_to_change"]}
    assert selected_paths <= source_paths


def test_output_path_stays_under_patch_drafts(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(repo, decision="approve")

    out = project_evolution_patch_draft.write_project_evolution_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=str(approval),
        max_files=8,
    )

    draft_root = (repo / ".agent" / "project_evolution" / "patch_drafts").resolve()
    Path(out["json_path"]).resolve().relative_to(draft_root)
    Path(out["md_path"]).resolve().relative_to(draft_root)


def test_source_plan_and_approval_record_are_not_mutated(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(repo, decision="approve")

    plan_before = (repo / ".agent" / "project_evolution" / "migration_plan_dry_run.json").read_text(encoding="utf-8")
    approval_before = Path(approval).read_text(encoding="utf-8")
    project_evolution_patch_draft.write_project_evolution_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=str(approval),
        max_files=8,
    )
    plan_after = (repo / ".agent" / "project_evolution" / "migration_plan_dry_run.json").read_text(encoding="utf-8")
    approval_after = Path(approval).read_text(encoding="utf-8")

    assert plan_before == plan_after
    assert approval_before == approval_after


def test_no_secret_values_are_extracted_from_env_files(tmp_path):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(repo, decision="approve")

    out = project_evolution_patch_draft.write_project_evolution_patch_draft_artifacts(
        repo_path=str(repo),
        approval_path=str(approval),
        max_files=8,
    )

    markdown = Path(out["md_path"]).read_text(encoding="utf-8")
    record = json.loads(Path(out["json_path"]).read_text(encoding="utf-8"))
    assert "TOP_SECRET_VALUE" not in markdown
    assert "TOP_SECRET_VALUE" not in json.dumps(record)


def test_cli_writes_draft_package_artifacts(tmp_path, capsys):
    repo = _build_sample_repo(tmp_path)
    approval = _seed_matching_plan_and_approval(repo, decision="approve")

    from scripts import create_evolution_patch_draft as cli

    rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--approval-path",
            str(approval),
            "--max-files",
            "8",
            "--draft-title",
            "Embedding provider draft",
            "--notes",
            "CLI run.",
        ]
    )
    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "md_path:" in output
    assert "likely_files_to_change:" in output
    assert (repo / ".agent" / "project_evolution" / "patch_drafts").exists()


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


def _seed_matching_plan_and_approval(repo: Path, *, decision: str, goal: str | None = None) -> Path:
    source_plan = _seed_plan(repo, goal=goal)
    out = project_evolution_approval.write_project_evolution_approval_artifacts(
        source_plan_path=str(source_plan),
        decision=decision,
        reviewer="Ops Lead",
        notes="Manual review.",
    )
    return Path(out["json_path"])


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
