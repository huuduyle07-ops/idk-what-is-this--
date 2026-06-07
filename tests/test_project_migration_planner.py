"""B.3 Migration Planner Dry Run contract tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core import project_map_v2, project_migration_planner, project_node_summaries


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "project_migration_planner.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_migration_plan_dry_run.py"

REQUIRED_JSON_FIELDS = {
    "generated_at",
    "repo_path",
    "mode",
    "schema_version",
    "migration_goal",
    "constraints",
    "risk_tolerance",
    "source_artifacts",
    "likely_affected_files",
    "full_files_to_read_before_patching",
    "impacted_components",
    "dependency_or_config_changes",
    "test_plan",
    "docs_plan",
    "rollout_plan",
    "rollback_plan",
    "risks",
    "open_questions",
    "human_approval_required",
    "approval_gate_reason",
    "patch_generation_allowed",
    "limitations",
}

REQUIRED_MD_SECTIONS = (
    "# Migration Plan Dry Run",
    "## Summary",
    "## Migration Goal",
    "## Source Artifacts",
    "## Likely Affected Files",
    "## Full Files To Read Before Patching",
    "## Impacted Components",
    "## Dependency / Config Changes",
    "## Test Plan",
    "## Docs Plan",
    "## Rollout Plan",
    "## Rollback Plan",
    "## Risks",
    "## Open Questions",
    "## Human Approval Required",
    "## Limitations",
)


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-project-migration-planner"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_builder_writes_json_and_markdown_artifacts(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_artifacts(repo)

    out = project_migration_planner.write_migration_plan_dry_run_artifacts(
        repo_path=str(repo),
        goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
    )

    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.name == "migration_plan_dry_run.json"
    assert md_path.name == "migration_plan_dry_run.md"
    json_path.resolve().relative_to((repo / ".agent" / "project_evolution").resolve())
    md_path.resolve().relative_to((repo / ".agent" / "project_evolution").resolve())

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved == out["record"]


def test_json_has_required_fields_and_approval_gate_is_locked(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_artifacts(repo)

    record = project_migration_planner.build_migration_plan_dry_run_record(
        repo_path=str(repo),
        goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
    )

    assert REQUIRED_JSON_FIELDS <= set(record)
    assert record["mode"] == "project_evolution"
    assert record["repo_path"] == str(repo.resolve())
    assert record["migration_goal"].startswith("Migrate embedding provider")
    assert record["human_approval_required"] is True
    assert record["patch_generation_allowed"] is False
    assert record["constraints"] == []
    assert record["risk_tolerance"] == ""
    assert record["source_artifacts"]
    assert record["source_artifacts"][0]["path"].endswith("project_map_v2.json")


def test_markdown_has_required_sections(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_artifacts(repo)

    record = project_migration_planner.build_migration_plan_dry_run_record(
        repo_path=str(repo),
        goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
    )
    markdown = project_migration_planner.render_migration_plan_dry_run_markdown(record)

    for section in REQUIRED_MD_SECTIONS:
        assert section in markdown


def test_missing_project_map_fails_cleanly(tmp_path):
    repo = _build_sample_repo(tmp_path)

    out = project_migration_planner.write_migration_plan_dry_run_artifacts(
        repo_path=str(repo),
        goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
    )

    assert out["record"]["status"] == "error"
    assert out["record"]["error"]["code"] == "source_map_unavailable"
    assert "project_map_v2.json" in out["record"]["error"]["message"]
    assert Path(out["json_path"]).is_file()
    assert Path(out["md_path"]).is_file()


def test_missing_node_summaries_continues_with_limitation(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_project_map(repo)

    record = project_migration_planner.build_migration_plan_dry_run_record(
        repo_path=str(repo),
        goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
    )

    assert record["status"] == "ok"
    assert any("node_summaries.json" in value for value in record["limitations"])
    assert any(item["path"].endswith("project_map_v2.json") for item in record["source_artifacts"])


def test_embedding_goal_prioritizes_provider_retrieval_indexer_graph_config_test_docs(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_artifacts(repo)

    record = project_migration_planner.build_migration_plan_dry_run_record(
        repo_path=str(repo),
        goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
        max_files=8,
    )

    selected = [item["path"] for item in record["full_files_to_read_before_patching"]]
    text = "\n".join(selected)
    for expected in (
        "config.py",
        "core/indexer.py",
        "graph/project_map.py",
        "graph/weights.py",
        "retrieval/provider_router.py",
        "tests/integration/test_provider_migration.py",
        "docs/project_evolution_mode.md",
    ):
        assert expected in text

    assert record["impacted_components"]
    impacted = " ".join(record["impacted_components"]).lower()
    for keyword in ("provider", "retrieval", "indexer", "graph", "config", "test", "docs"):
        assert keyword in impacted


def test_source_artifacts_are_not_mutated_by_builder(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_artifacts(repo)

    before = {
        path.relative_to(repo).as_posix(): path.read_text(encoding="utf-8")
        for path in repo.rglob("*")
        if path.is_file()
    }

    project_migration_planner.write_migration_plan_dry_run_artifacts(
        repo_path=str(repo),
        goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
    )

    after = {
        path.relative_to(repo).as_posix(): path.read_text(encoding="utf-8")
        for path in repo.rglob("*")
        if path.is_file()
    }
    for rel_path, content in before.items():
        if rel_path.startswith(".agent/project_evolution/"):
            continue
        assert after[rel_path] == content


def test_cli_writes_both_artifacts(tmp_path, capsys):
    repo = _build_sample_repo(tmp_path)
    _seed_artifacts(repo)

    from scripts import create_migration_plan_dry_run as cli

    rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--goal",
            "Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction",
            "--max-files",
            "8",
        ]
    )
    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "md_path:" in output
    assert "likely_affected_files:" in output
    assert (repo / ".agent" / "project_evolution" / "migration_plan_dry_run.json").is_file()
    assert (repo / ".agent" / "project_evolution" / "migration_plan_dry_run.md").is_file()


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


def _seed_project_map(repo: Path) -> dict[str, object]:
    return project_map_v2.write_project_map_v2_artifacts(
        str(repo),
        max_full_file_candidates=80,
    )


def _seed_artifacts(repo: Path) -> dict[str, object]:
    _seed_project_map(repo)
    return project_node_summaries.write_project_node_summaries_artifacts(str(repo))


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
        "core/project_map_v2.py": "def build_project_map_v2_record():\n    return {}\n",
        "graph/project_map.py": "def build_project_map():\n    return ''\n",
        "graph/weights.py": "def rank_nodes_by_weight():\n    return []\n",
        "retrieval/provider_router.py": "class ProviderRouter:\n    pass\n",
        "tests/test_project_map_v2.py": "def test_map():\n    assert True\n",
        "tests/integration/test_provider_migration.py": "def test_provider_migration():\n    assert True\n",
        "docs/project_evolution_mode.md": "# Evolution\n",
        "docs/project_map_upgrade_plan.md": "# Upgrade Plan\n",
        "docs/architecture.md": "# Architecture\n",
        "build/generated.js": "console.log('generated');\n",
        "dist/bundle.js": "console.log('bundle');\n",
        "node_modules/pkg/index.js": "module.exports = {};\n",
        "benchmarks/cases/python/demo/buggy_repo/main.py": "print('noise')\n",
        ".claude/worktrees/noisy/config.py": "API_KEY='noise'\n",
        ".git/HEAD": "ref: refs/heads/main\n",
        ".agent/benchmarks/noisy.json": "{}\n",
    }

    for index in range(50):
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
