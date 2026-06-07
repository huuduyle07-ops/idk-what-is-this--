"""B.2 Project Map v2 contract tests.

Project Map v2 is a read-only artifact builder for Project Evolution Mode. It
must write JSON + Markdown under ``.agent/project_evolution/`` without
touching Debug Mode behavior, patching, validation, benchmarks, lessons,
Docker/subprocess lifecycles, or model/API clients.
"""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core import project_map_v2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "project_map_v2.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_project_map_v2.py"

REQUIRED_JSON_FIELDS = {
    "generated_at",
    "repo_path",
    "mode",
    "schema_version",
    "languages",
    "dependency_files",
    "config_files",
    "entrypoints",
    "test_roots",
    "documentation_files",
    "ignored_generated_or_build_paths",
    "likely_architecture_layers",
    "integration_boundaries",
    "external_services_or_env_vars",
    "full_file_read_candidates",
    "migration_risk_notes",
    "source_components_used",
    "limitations",
}

REQUIRED_MD_SECTIONS = (
    "# Project Map v2",
    "## Summary",
    "## Languages",
    "## Dependency Files",
    "## Config Files",
    "## Entrypoints",
    "## Test Roots",
    "## Documentation Files",
    "## Ignored Generated / Build Paths",
    "## Likely Architecture Layers",
    "## Integration Boundaries",
    "## External Services / Env Vars",
    "## Full-File Read Candidates",
    "## Migration Risk Notes",
    "## Source Components Used",
    "## Limitations",
)


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-project-map-v2"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_builder_writes_json_and_markdown_artifacts(tmp_path):
    repo = _build_sample_repo(tmp_path)

    out = project_map_v2.write_project_map_v2_artifacts(str(repo))

    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.name == "project_map_v2.json"
    assert md_path.name == "project_map_v2.md"
    json_path.resolve().relative_to((repo / ".agent" / "project_evolution").resolve())
    md_path.resolve().relative_to((repo / ".agent" / "project_evolution").resolve())

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved == out["record"]


def test_json_has_required_fields_and_project_evolution_mode(tmp_path):
    repo = _build_sample_repo(tmp_path)

    record = project_map_v2.build_project_map_v2_record(str(repo))

    assert REQUIRED_JSON_FIELDS <= set(record)
    assert record["mode"] == "project_evolution"
    assert record["repo_path"] == str(repo.resolve())
    assert record["schema_version"]
    assert isinstance(record["languages"], list) and record["languages"]
    assert isinstance(record["migration_risk_notes"], list)
    assert isinstance(record["limitations"], list)


def test_markdown_has_required_sections(tmp_path):
    repo = _build_sample_repo(tmp_path)

    record = project_map_v2.build_project_map_v2_record(str(repo))
    markdown = project_map_v2.render_project_map_v2_markdown(record)

    for section in REQUIRED_MD_SECTIONS:
        assert section in markdown


def test_detects_dependencies_configs_entrypoints_tests_docs_and_ignored_paths(tmp_path):
    repo = _build_sample_repo(tmp_path)

    record = project_map_v2.build_project_map_v2_record(str(repo))

    assert "package.json" in record["dependency_files"]
    assert "pyproject.toml" in record["dependency_files"]
    assert "requirements.txt" in record["dependency_files"]

    assert ".env.example" in record["config_files"]
    assert "Dockerfile" in record["config_files"]
    assert "docker-compose.yml" in record["config_files"]
    assert "config.py" in record["config_files"]
    assert "settings.py" in record["config_files"]
    assert "pytest.ini" in record["config_files"]
    assert "tsconfig.json" in record["config_files"]
    assert "vite.config.ts" in record["config_files"]

    assert "main.py" in record["entrypoints"]
    assert "app.py" in record["entrypoints"]
    assert "cli.py" in record["entrypoints"]
    assert "web/app.py" in record["entrypoints"]
    assert "src/main.rs" in record["entrypoints"]

    assert "tests" in record["test_roots"]
    assert "__tests__" in record["test_roots"]

    assert "README.md" in record["documentation_files"]
    assert "CHANGELOG.md" in record["documentation_files"]
    assert "docs/architecture.md" in record["documentation_files"]

    ignored = set(record["ignored_generated_or_build_paths"])
    for expected in ("node_modules", "dist", "build", ".git", ".agent/benchmarks"):
        assert expected in ignored


def test_external_services_and_env_vars_do_not_leak_dotenv_values(tmp_path):
    repo = _build_sample_repo(tmp_path)

    record = project_map_v2.build_project_map_v2_record(str(repo))
    payload = json.dumps(record, ensure_ascii=False)

    names = {item["name"] for item in record["external_services_or_env_vars"]}
    assert "OPENAI_API_KEY" in names
    assert "DATABASE_URL" in names
    assert ".env" in names
    assert "TOP_SECRET_VALUE" not in payload
    assert "postgres://super-secret" not in payload


def test_full_file_read_candidates_are_capped_rationalized_and_repo_local(tmp_path):
    repo = _build_sample_repo(tmp_path)

    record = project_map_v2.build_project_map_v2_record(str(repo))
    candidates = record["full_file_read_candidates"]

    assert candidates
    assert len(candidates) <= 30
    assert "build/generated.js" not in {item["path"] for item in candidates}
    assert "dist/bundle.js" not in {item["path"] for item in candidates}

    for item in candidates:
        assert set(item) >= {"path", "reason", "confidence", "category"}
        assert item["path"]
        assert item["reason"].strip()
        assert item["confidence"]
        assert item["category"]
        assert not Path(item["path"]).is_absolute()
        assert ".." not in Path(item["path"]).parts
        (repo / item["path"]).resolve().relative_to(repo.resolve())


def test_source_files_are_not_mutated_by_builder(tmp_path):
    repo = _build_sample_repo(tmp_path)
    before = {
        path.relative_to(repo).as_posix(): path.read_text(encoding="utf-8")
        for path in repo.rglob("*")
        if path.is_file()
    }

    project_map_v2.write_project_map_v2_artifacts(str(repo))

    after = {
        path.relative_to(repo).as_posix(): path.read_text(encoding="utf-8")
        for path in repo.rglob("*")
        if path.is_file() and ".agent/project_evolution" not in path.as_posix()
    }
    for rel_path, content in before.items():
        if rel_path.startswith(".agent/project_evolution/"):
            continue
        assert after[rel_path] == content


def test_cli_writes_both_artifacts(tmp_path, capsys):
    repo = _build_sample_repo(tmp_path)

    from scripts import build_project_map_v2 as cli

    rc = cli.main([str(repo)])
    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "md_path:" in output
    assert (repo / ".agent" / "project_evolution" / "project_map_v2.json").is_file()
    assert (repo / ".agent" / "project_evolution" / "project_map_v2.md").is_file()


def test_source_components_used_mentions_existing_mapping_stack(tmp_path):
    repo = _build_sample_repo(tmp_path)

    record = project_map_v2.build_project_map_v2_record(str(repo))
    text = json.dumps(record["source_components_used"], ensure_ascii=False).lower()

    for phrase in (
        "core.repo_librarian",
        "core.indexer",
        "graph.project_map",
        "graph.builder",
        "graph.weights",
        "core.semantic_graph_pipeline",
        "reasoning.deep_project_understand",
    ):
        assert phrase in text


def test_b2_module_and_cli_have_no_forbidden_imports_or_calls():
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
        "api",
        "benchmarks",
        "docker",
        "openai",
        "patching",
        "psycopg2",
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
        "core.pipeline",
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
        "system",
        "Popen",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots)
    assert imports.isdisjoint(forbidden_imports)
    assert calls.isdisjoint(forbidden_calls)


def _build_sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_repo"
    repo.mkdir()

    files = {
        "README.md": "# Sample Repo\n",
        "CHANGELOG.md": "## 0.1.0\n",
        "package.json": '{ "name": "sample-app" }\n',
        "pyproject.toml": "[project]\nname='sample'\n",
        "requirements.txt": "fastapi==0.1\n",
        ".env.example": "OPENAI_API_KEY=demo\nDATABASE_URL=postgres://localhost/db\n",
        ".env": "OPENAI_API_KEY=TOP_SECRET_VALUE\nDATABASE_URL=postgres://super-secret\n",
        "Dockerfile": "FROM python:3.11\n",
        "docker-compose.yml": "services:\n  app:\n    environment:\n      - DATABASE_URL\n",
        "config.py": "import os\nAPI_BASE_URL = os.getenv('API_BASE_URL')\n",
        "settings.py": "import os\nDATABASE_URL = os.getenv('DATABASE_URL')\n",
        "pytest.ini": "[pytest]\n",
        "tsconfig.json": '{ "compilerOptions": {} }\n',
        "vite.config.ts": "export default {};\n",
        "main.py": "from web.app import app\n",
        "app.py": "def run():\n    return 'ok'\n",
        "cli.py": "def main():\n    return 0\n",
        "web/app.py": "app = object()\n",
        "src/main.rs": "fn main() {}\n",
        "tests/test_app.py": "def test_app():\n    assert True\n",
        "__tests__/ui.test.ts": "test('ui', () => expect(true).toBe(true));\n",
        "docs/architecture.md": "# Architecture\n",
        "docs/migration-plan.md": "# Migration\n",
        "api/client.py": "class ApiClient:\n    pass\n",
        "worker/queue_worker.py": "def run_worker():\n    return True\n",
        "storage/s3_client.py": "class StorageClient:\n    pass\n",
        "retrieval/embedding_provider.py": "class EmbeddingProvider:\n    pass\n",
        "graph/query_bridge.py": "def bridge():\n    return 'graph'\n",
        "auth/provider.py": "class AuthProvider:\n    pass\n",
        "build/generated.js": "console.log('generated');\n",
        "dist/bundle.js": "console.log('bundle');\n",
        "node_modules/pkg/index.js": "module.exports = {};\n",
        ".git/HEAD": "ref: refs/heads/main\n",
        ".agent/benchmarks/noisy.json": "{}\n",
    }

    for index in range(40):
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
