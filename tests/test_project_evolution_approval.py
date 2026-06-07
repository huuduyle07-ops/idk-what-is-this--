"""B.4 Approval-Gated Evolution Plan Review contract tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core import project_map_v2, project_migration_planner, project_node_summaries, project_evolution_approval


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "project_evolution_approval.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "review_migration_plan.py"

REQUIRED_JSON_FIELDS = {
    "generated_at",
    "repo_path",
    "mode",
    "schema_version",
    "source_plan_path",
    "source_plan_hash",
    "migration_goal",
    "decision",
    "reviewer",
    "notes",
    "approved_scope",
    "blocked_scope",
    "human_approval_recorded",
    "patch_generation_allowed",
    "patch_generation_gate_reason",
    "limitations",
}

REQUIRED_MD_SECTIONS = (
    "# Evolution Plan Review",
    "## Decision",
    "## Source Plan",
    "## Migration Goal",
    "## Reviewer Notes",
    "## Approved Scope",
    "## Blocked Scope",
    "## Patch Generation Gate",
    "## Limitations",
)


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-project-evolution-approval"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_approve_creates_json_and_markdown_approval_record(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo)

    out = project_evolution_approval.write_project_evolution_approval_artifacts(
        source_plan_path=str(source_plan),
        decision="approve",
        reviewer="Ops Lead",
        notes="Looks safe after the dry run.",
        approved_scope=["provider abstraction", "retrieval wiring"],
        blocked_scope=["unrelated UI changes"],
    )

    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.name.endswith("_approval.json")
    assert md_path.name.endswith("_approval.md")
    json_path.resolve().relative_to((repo / ".agent" / "project_evolution" / "approvals").resolve())
    md_path.resolve().relative_to((repo / ".agent" / "project_evolution" / "approvals").resolve())

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved == out["record"]
    assert saved["decision"] == "approve"
    assert saved["patch_generation_allowed"] is True
    assert saved["human_approval_recorded"] is True


def test_reject_and_needs_revision_keep_patch_generation_disabled(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo)

    reject = project_evolution_approval.build_project_evolution_approval_record(
        source_plan_path=str(source_plan),
        decision="reject",
    )
    needs_revision = project_evolution_approval.build_project_evolution_approval_record(
        source_plan_path=str(source_plan),
        decision="needs_revision",
    )

    assert reject["patch_generation_allowed"] is False
    assert needs_revision["patch_generation_allowed"] is False
    assert "reject" in reject["patch_generation_gate_reason"].lower()
    assert "revision" in needs_revision["patch_generation_gate_reason"].lower()


def test_approval_contains_source_plan_hash_and_hash_is_stable_for_same_plan(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo)

    first = project_evolution_approval.build_project_evolution_approval_record(
        source_plan_path=str(source_plan),
        decision="approve",
    )
    _seed_migration_plan(repo)
    second = project_evolution_approval.build_project_evolution_approval_record(
        source_plan_path=str(source_plan),
        decision="approve",
    )

    assert first["source_plan_hash"]
    assert first["source_plan_hash"] == second["source_plan_hash"]


def test_changed_plan_produces_different_hash(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo, goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction")

    first = project_evolution_approval.build_project_evolution_approval_record(
        source_plan_path=str(source_plan),
        decision="approve",
    )
    _seed_migration_plan(repo, goal="Migrate search graph weights to a new ranking strategy")
    second = project_evolution_approval.build_project_evolution_approval_record(
        source_plan_path=str(source_plan),
        decision="approve",
    )

    assert first["source_plan_hash"] != second["source_plan_hash"]


def test_missing_migration_plan_fails_gracefully(tmp_path):
    repo = _build_sample_repo(tmp_path)
    missing_plan = repo / ".agent" / "project_evolution" / "migration_plan_dry_run.json"

    out = project_evolution_approval.write_project_evolution_approval_artifacts(
        source_plan_path=str(missing_plan),
        decision="reject",
    )

    assert out["record"]["status"] == "error"
    assert "migration_plan_dry_run.json" in out["record"]["error"]["message"]
    assert Path(out["json_path"]).is_file()
    assert Path(out["md_path"]).is_file()


def test_invalid_decision_is_rejected(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo)

    with pytest.raises(ValueError):
        project_evolution_approval.build_project_evolution_approval_record(
            source_plan_path=str(source_plan),
            decision="maybe",
        )


def test_empty_reviewer_and_notes_are_handled_safely(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo)

    record = project_evolution_approval.build_project_evolution_approval_record(
        source_plan_path=str(source_plan),
        decision="approve",
        reviewer="",
        notes="",
        approved_scope=None,
        blocked_scope=None,
    )

    assert record["reviewer"] == ""
    assert record["notes"] == ""
    assert record["approved_scope"] == []
    assert record["blocked_scope"] == []


def test_output_path_stays_inside_approvals_directory(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo)

    out = project_evolution_approval.write_project_evolution_approval_artifacts(
        source_plan_path=str(source_plan),
        decision="needs_revision",
    )

    approvals_root = (repo / ".agent" / "project_evolution" / "approvals").resolve()
    Path(out["json_path"]).resolve().relative_to(approvals_root)
    Path(out["md_path"]).resolve().relative_to(approvals_root)


def test_approval_does_not_mutate_source_migration_plan(tmp_path):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo)

    before = source_plan.read_text(encoding="utf-8")
    project_evolution_approval.write_project_evolution_approval_artifacts(
        source_plan_path=str(source_plan),
        decision="approve",
    )
    after = source_plan.read_text(encoding="utf-8")

    assert after == before


def test_cli_writes_approval_artifacts(tmp_path, capsys):
    repo = _build_sample_repo(tmp_path)
    source_plan = _seed_migration_plan(repo)

    from scripts import review_migration_plan as cli

    rc = cli.main(
        [
            "--source-plan-path",
            str(source_plan),
            "--decision",
            "approve",
            "--reviewer",
            "Ops Lead",
            "--notes",
            "Looks safe.",
        ]
    )
    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "md_path:" in output
    assert (repo / ".agent" / "project_evolution" / "approvals").exists()


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


def _seed_migration_plan(repo: Path, goal: str | None = None) -> Path:
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
        "package.json": '{ "name": "sample-app" }\n',
        "pyproject.toml": "[project]\nname='sample'\n",
        "requirements.txt": "fastapi==0.1\npydantic==2.0\n",
        ".env.example": "OPENAI_API_KEY=demo\nDATABASE_URL=postgres://localhost/db\nPROVIDER_ID=mock\n",
        "config.py": "import os\nPROVIDER_ID = os.getenv('PROVIDER_ID')\n",
        "settings.py": "import os\nDATABASE_URL = os.getenv('DATABASE_URL')\n",
        "main.py": "from web.app import app\n",
        "web/app.py": "app = object()\n",
        "core/indexer.py": "def index_repository():\n    return 'index'\n",
        "graph/project_map.py": "def build_project_map():\n    return ''\n",
        "graph/weights.py": "def rank_nodes_by_weight():\n    return []\n",
        "retrieval/provider_router.py": "class ProviderRouter:\n    pass\n",
        "tests/integration/test_provider_migration.py": "def test_provider_migration():\n    assert True\n",
        "docs/project_evolution_mode.md": "# Evolution\n",
        "docs/project_map_upgrade_plan.md": "# Upgrade Plan\n",
    }

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
