"""B.4a Project Evolution approval web panel contract tests."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core import project_map_v2, project_migration_planner, project_node_summaries


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROUTE_PATH = PROJECT_ROOT / "web" / "routes" / "project_evolution_approval_routes.py"
HARNESS_ROUTE_PATH = PROJECT_ROOT / "web" / "routes" / "harness_controls_routes.py"


@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


def test_get_page_renders_project_evolution_approval_panel(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Project Evolution Plan Review" in html
    assert "Approve this exact plan hash" in html
    assert "Reject plan" in html
    assert "Mark needs revision" in html
    assert "Approval only applies to this exact plan hash." in html
    assert "settings-project-evolution" in html


def test_missing_plan_shows_friendly_message_and_disabled_buttons(client, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    resp = client.get("/project-evolution/approval-panel", query_string={"repo_path": str(repo)})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is False
    assert body["plan_present"] is False
    assert body["buttons_enabled"] is False
    assert "migration_plan_dry_run.json" in body["message"]


def test_ui_displays_plan_hash_and_exact_hash_warning(client, tmp_path):
    repo = _build_repo(tmp_path)
    _seed_plan(repo)

    resp = client.get("/project-evolution/approval-panel", query_string={"repo_path": str(repo)})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["plan_present"] is True
    assert body["source_plan_hash"]
    assert body["source_plan_path"].endswith("migration_plan_dry_run.json")
    assert body["approval_warning"] == "Approval only applies to this exact plan hash."
    assert body["patch_generation_allowed"] is False


@pytest.mark.parametrize(
    "decision, expected_allowed",
    [
        ("approve", True),
        ("reject", False),
        ("needs_revision", False),
    ],
)
def test_approval_post_creates_record_and_reports_gate_state(
    client,
    tmp_path,
    decision,
    expected_allowed,
):
    repo = _build_repo(tmp_path)
    _seed_plan(repo)
    panel = client.get("/project-evolution/approval-panel", query_string={"repo_path": str(repo)}).get_json()

    resp = client.post(
        "/project-evolution/approval-panel/review",
        json={
            "repo_path": str(repo),
            "decision": decision,
            "reviewer": "Ops Lead",
            "notes": "Manual review complete.",
            "approved_scope": ["provider abstraction"],
            "blocked_scope": ["unrelated UI work"],
            "source_plan_hash": panel["source_plan_hash"],
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["ok"] is True
    assert body["decision"] == decision
    assert body["approved_source_hash"] == panel["source_plan_hash"]
    assert body["patch_generation_allowed"] is expected_allowed
    assert body["message"] == "No patch was generated."
    assert Path(body["approval_record_path"]).is_file()
    assert Path(body["approval_markdown_path"]).is_file()
    approvals_root = (repo / ".agent" / "project_evolution" / "approvals").resolve()
    Path(body["approval_record_path"]).resolve().relative_to(approvals_root)
    Path(body["approval_markdown_path"]).resolve().relative_to(approvals_root)


def test_path_traversal_is_ignored_and_output_stays_in_approvals_dir(client, tmp_path):
    repo = _build_repo(tmp_path)
    _seed_plan(repo)
    panel = client.get("/project-evolution/approval-panel", query_string={"repo_path": str(repo)}).get_json()

    resp = client.post(
        "/project-evolution/approval-panel/review",
        json={
            "repo_path": str(repo),
            "decision": "approve",
            "source_plan_hash": panel["source_plan_hash"],
            "source_plan_path": "../../outside.json",
            "approval_output_path": r"..\..\evil.json",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    approvals_root = (repo / ".agent" / "project_evolution" / "approvals").resolve()
    Path(body["approval_record_path"]).resolve().relative_to(approvals_root)
    Path(body["approval_markdown_path"]).resolve().relative_to(approvals_root)
    assert body["source_plan_path"].endswith("migration_plan_dry_run.json")


def test_stale_source_plan_hash_is_rejected_after_plan_changes(client, tmp_path):
    repo = _build_repo(tmp_path)
    _seed_plan(repo, goal="Migrate embedding provider from MiniLM to Gemini/model2vec/Semble-ready provider abstraction")
    panel = client.get("/project-evolution/approval-panel", query_string={"repo_path": str(repo)}).get_json()

    _seed_plan(repo, goal="Migrate search graph weights to a new ranking strategy")

    resp = client.post(
        "/project-evolution/approval-panel/review",
        json={
            "repo_path": str(repo),
            "decision": "approve",
            "source_plan_hash": panel["source_plan_hash"],
        },
    )
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["ok"] is False
    assert body["current_source_plan_hash"] != body["expected_source_plan_hash"]
    assert not (repo / ".agent" / "project_evolution" / "approvals").exists()


def test_approval_routes_do_not_import_forbidden_runtime_dependencies():
    trees = [
        ast.parse(ROUTE_PATH.read_text(encoding="utf-8")),
        ast.parse((PROJECT_ROOT / "core" / "project_evolution_approval.py").read_text(encoding="utf-8")),
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


def test_harness_controls_routes_remain_separate_from_evolution_approval():
    source = HARNESS_ROUTE_PATH.read_text(encoding="utf-8")
    assert "project_evolution_approval" not in source
    assert "/project-evolution/approval-panel" not in source
    assert "Approve this exact plan hash" not in source


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


def _build_repo(tmp_path: Path) -> Path:
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
