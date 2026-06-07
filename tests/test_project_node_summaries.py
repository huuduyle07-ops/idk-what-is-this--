"""B.2a heuristic Project Evolution node summary contract tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core import project_map_v2, project_node_summaries


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "project_node_summaries.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_project_node_summaries.py"

REQUIRED_SUMMARY_FIELDS = {
    "node_id",
    "path",
    "node_type",
    "summary",
    "responsibilities",
    "migration_relevance",
    "risk_notes",
    "evidence",
    "summary_source",
    "confidence",
    "category",
    "source_map_generated_at",
}


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-project-node-summaries"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_builder_writes_json_and_markdown_artifacts(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_project_map(repo)

    out = project_node_summaries.write_project_node_summaries_artifacts(str(repo))

    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.name == "node_summaries.json"
    assert md_path.name == "node_summaries.md"
    json_path.resolve().relative_to((repo / ".agent" / "project_evolution").resolve())
    md_path.resolve().relative_to((repo / ".agent" / "project_evolution").resolve())

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved == out["record"]


def test_only_selected_and_capped_nodes_are_summarized(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_project_map(repo)

    record = project_node_summaries.build_project_node_summaries_record(
        str(repo),
        max_nodes=12,
    )

    assert record["status"] == "ok"
    assert record["summary_count"] <= 12
    paths = {item["path"] for item in record["summaries"]}

    for expected in (
        "requirements.txt",
        "config.py",
        "core/indexer.py",
        "graph/weights.py",
        "tests/integration/test_provider_migration.py",
        "docs/project_evolution_mode.md",
    ):
        assert expected in paths

    for rejected in (
        "build/generated.js",
        "dist/bundle.js",
        ".env",
        "benchmarks/cases/python/demo/buggy_repo/main.py",
        ".claude/worktrees/noisy/config.py",
    ):
        assert rejected not in paths


def test_summaries_have_required_fields_and_heuristic_source(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_map = _seed_project_map(repo)

    record = project_node_summaries.build_project_node_summaries_record(str(repo))

    assert record["status"] == "ok"
    for item in record["summaries"]:
        assert REQUIRED_SUMMARY_FIELDS <= set(item)
        assert item["node_id"]
        assert item["path"]
        assert item["node_type"] in {
            "file",
            "config",
            "dependency",
            "test",
            "doc",
            "provider",
            "entrypoint",
            "unknown",
        }
        assert item["summary"].strip()
        assert item["responsibilities"]
        assert item["migration_relevance"].strip()
        assert item["risk_notes"]
        assert item["evidence"]
        assert item["summary_source"] == "heuristic"
        assert 0.0 <= item["confidence"] <= 1.0
        assert item["source_map_generated_at"] == source_map["record"]["generated_at"]


def test_no_env_secret_values_are_extracted(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_project_map(repo)

    out = project_node_summaries.write_project_node_summaries_artifacts(str(repo))
    payload = json.dumps(out["record"], ensure_ascii=False)
    markdown = Path(out["md_path"]).read_text(encoding="utf-8")

    assert "TOP_SECRET_VALUE" not in payload
    assert "postgres://super-secret" not in payload
    assert "TOP_SECRET_VALUE" not in markdown
    assert "postgres://super-secret" not in markdown


def test_generated_and_build_folders_are_ignored(tmp_path):
    repo = _build_sample_repo(tmp_path)
    _seed_project_map(repo)

    record = project_node_summaries.build_project_node_summaries_record(str(repo))
    paths = {item["path"] for item in record["summaries"]}

    assert "build/generated.js" not in paths
    assert "dist/bundle.js" not in paths
    assert "node_modules/pkg/index.js" not in paths


def test_missing_project_map_v2_fails_gracefully_with_clear_error(tmp_path):
    repo = _build_sample_repo(tmp_path)

    out = project_node_summaries.write_project_node_summaries_artifacts(str(repo))

    assert out["record"]["status"] == "error"
    assert out["record"]["summary_count"] == 0
    assert not out["record"]["summaries"]
    assert "project_map_v2.json" in out["record"]["error"]["message"]
    assert Path(out["json_path"]).is_file()
    assert Path(out["md_path"]).is_file()


def test_cli_writes_both_artifacts(tmp_path, capsys):
    repo = _build_sample_repo(tmp_path)
    _seed_project_map(repo)

    from scripts import build_project_node_summaries as cli

    rc = cli.main([str(repo), "--max-nodes", "9"])
    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "md_path:" in output
    assert "summary_count:" in output
    assert (repo / ".agent" / "project_evolution" / "node_summaries.json").is_file()
    assert (repo / ".agent" / "project_evolution" / "node_summaries.md").is_file()


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
