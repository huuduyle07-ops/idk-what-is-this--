from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from core import worker_assignment
from scripts import create_worker_assignment as cli


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-worker-assignment"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _write_goal_brief(repo: Path, **overrides: Any) -> Path:
    brief = {
        "goal": "Fix checkout total regression",
        "problem_type": "bug_fix",
        "evidence": {
            "expected_result": "checkout total is 20",
            "actual_result": "checkout total is 19",
            "error_output": "FAILED test_checkout_total",
            "changed_files": ["core/checkout.py"],
        },
        "constraints": {
            "allowed_files": ["core/checkout.py"],
            "forbidden_files": ["database/schema.sql"],
            "do_not_weaken": ["Do not loosen checkout assertions"],
        },
        "validation": {
            "command": "python -m pytest tests/test_checkout.py -q",
            "success_criteria": "pytest exits 0",
        },
    }
    brief.update(overrides)
    path = repo / ".agent" / "goal_briefs" / "20260101_000000" / "goal_brief.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(brief, indent=2), encoding="utf-8")
    return path


def _write_seed_draft(repo: Path) -> Path:
    draft = {
        "mode": "external_queue_export_draft",
        "export_id": "queue-1_goal_brief_seed_draft",
        "target": "goal_brief_seed",
        "title": "Research checkout reliability",
        "summary": "Turn external research into a focused checkout task.",
        "source_item_path": str(repo / ".agent" / "external_queue" / "queue-1" / "external_queue_item.json"),
        "source_review_path": str(repo / ".agent" / "external_queue" / "queue-1" / "external_queue_review.json"),
        "suggested_goal": "Improve checkout reliability evidence",
        "constraints": ["Human approval is required before starting the target workflow."],
        "risk_notes": ["No mutation request was reviewed."],
        "suggested_validation": ["Review the source item and review artifact."],
        "human_approval_required": True,
        "patch_applied": False,
    }
    path = repo / ".agent" / "external_queue_exports" / "queue-1" / "goal_brief_seed_draft.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    return path


def test_create_assignment_from_goal_brief_writes_json_and_markdown(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    result = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        mode="debug",
        worker_role="implementer",
        created_at="2026-01-01T00:00:00Z",
        assignment_id="debug-checkout",
    )

    assert result["ok"] is True
    assert result["status"] == "draft_created"
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path == repo / ".agent" / "worker_assignments" / "debug-checkout" / "worker_assignment.json"
    assert md_path == json_path.with_name("worker_assignment.md")
    assert json_path.is_file()
    assert md_path.is_file()

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record["assignment_id"] == "debug-checkout"
    assert record["created_at"] == "2026-01-01T00:00:00Z"
    assert record["source_type"] == "goal_brief"
    assert record["source_path"] == str(source.resolve())
    assert record["title"] == "Fix checkout total regression"
    assert record["mode"] == "Debug"
    assert record["worker_role"] == "implementer"
    assert record["repo_path"] == str(repo.resolve())
    assert record["allowed_files"] == ["core/checkout.py"]
    assert "database/schema.sql" in record["forbidden_files"]
    assert "python -m pytest tests/test_checkout.py -q" in record["validation_commands"]
    assert record["human_approval_required"] is True
    assert record["apply_allowed"] is False
    assert record["worker_launch_allowed"] is False
    assert record["model_call_performed"] is False
    assert record["patch_applied"] is False
    assert record["validation_run"] is False
    assert record["promotion_performed"] is False


def test_markdown_contains_copy_paste_sections(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    result = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        dry_run=True,
        created_at="2026-01-01T00:00:00Z",
        assignment_id="markdown-check",
    )

    markdown = result["markdown"]
    for heading in [
        "# Worker Assignment",
        "## Objective",
        "## Context / Source Artifact",
        "## Allowed Files",
        "## Forbidden Files",
        "## Constraints",
        "## Validation Commands",
        "## Stop Conditions",
        "## Safety Rules",
        "## Expected Output",
        "## Final Summary Format",
    ]:
        assert heading in markdown
    assert "human approval required" in markdown.lower()
    assert "apply_allowed: false" in markdown
    assert "Do not apply patches unless" in markdown
    assert "outside allowed scope" in markdown
    assert "visual evidence is required but unavailable" in markdown


def test_inert_flags_regression(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    record = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        dry_run=True,
    )["record"]

    expected_flags = {
        "human_approval_required": True,
        "apply_allowed": False,
        "worker_launch_allowed": False,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "promotion_performed": False,
    }
    for key, expected in expected_flags.items():
        assert record[key] is expected


def test_dry_run_writes_nothing(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    result = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        dry_run=True,
        assignment_id="dry-run-only",
        created_at="2026-01-01T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert not (repo / ".agent" / "worker_assignments").exists()


def test_missing_source_returns_clean_error(tmp_path):
    repo = _repo(tmp_path)

    result = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(repo / ".agent" / "goal_briefs" / "missing" / "goal_brief.json"),
    )

    assert result["ok"] is False
    assert result["status"] == "not_found"
    assert result["error"]["code"] == "source_not_found"
    assert not (repo / ".agent" / "worker_assignments").exists()


def test_mode_specific_defaults_are_applied(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    debug = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        mode="debug",
        dry_run=True,
    )["record"]
    project = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        mode="project-evolution",
        dry_run=True,
    )["record"]
    dream = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        mode="dream_trial",
        dry_run=True,
    )["record"]
    review = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        mode="review-only",
        worker_role="reviewer",
        dry_run=True,
    )["record"]

    assert any("minimal" in item.lower() for item in debug["safety_rules"])
    assert any("validation" in item.lower() for item in debug["stop_conditions"])
    assert any("plan/review gate" in item.lower() for item in project["safety_rules"])
    assert any("draft/review-only" in item.lower() for item in project["safety_rules"])
    assert any("no real repo apply" in item.lower() for item in dream["safety_rules"])
    assert any("sandbox/temp clone only" in item.lower() for item in dream["safety_rules"])
    assert any("no patch generation" in item.lower() for item in review["safety_rules"])
    assert "critique/report" in review["expected_output"].lower()


def test_stop_conditions_include_required_guardrails(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    record = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        dry_run=True,
    )["record"]

    joined = "\n".join(record["stop_conditions"]).lower()
    assert "required files are missing" in joined
    assert "outside allowed scope" in joined
    assert "validation command is unavailable" in joined
    assert "secrets/env/protected files" in joined
    assert "patch safety would block" in joined
    assert "visual evidence is required but unavailable" in joined
    assert "before applying real repo changes" in joined


def test_seed_draft_source_is_supported_without_starting_target_workflow(tmp_path):
    repo = _repo(tmp_path)
    source = _write_seed_draft(repo)

    result = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        seed_draft_path=str(source),
        mode="documentation",
        worker_role="documenter",
        dry_run=True,
        created_at="2026-01-01T00:00:00Z",
        assignment_id="seed-docs",
    )

    record = result["record"]
    assert result["ok"] is True
    assert record["source_type"] == "seed_draft"
    assert record["title"] == "Research checkout reliability"
    assert record["mode"] == "Documentation"
    assert record["worker_role"] == "documenter"
    assert record["worker_launch_allowed"] is False
    assert record["model_call_performed"] is False


def test_forbidden_files_and_validation_commands_are_preserved(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    record = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        forbidden_files=["secrets.json"],
        validation_commands=["python -m compileall -q core"],
        dry_run=True,
    )["record"]

    assert "database/schema.sql" in record["forbidden_files"]
    assert "secrets.json" in record["forbidden_files"]
    assert "python -m pytest tests/test_checkout.py -q" in record["validation_commands"]
    assert "python -m compileall -q core" in record["validation_commands"]


def test_deterministic_json_output_with_fixed_metadata(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)
    kwargs = {
        "repo_path": str(repo),
        "goal_brief_path": str(source),
        "dry_run": True,
        "created_at": "2026-01-01T00:00:00Z",
        "assignment_id": "stable",
    }

    first = worker_assignment.render_worker_assignment_json(
        worker_assignment.create_worker_assignment(**kwargs)
    )
    second = worker_assignment.render_worker_assignment_json(
        worker_assignment.create_worker_assignment(**kwargs)
    )

    assert first == second
    assert json.loads(first)["record"]["assignment_id"] == "stable"


def test_existing_assignment_is_not_overwritten(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    first = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        assignment_id="same-id",
        created_at="2026-01-01T00:00:00Z",
    )
    json_path = Path(first["json_path"])
    changed = json_path.read_text(encoding="utf-8") + "\n"
    json_path.write_text(changed, encoding="utf-8")

    second = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        assignment_id="same-id",
        created_at="2026-01-01T00:00:00Z",
    )

    assert second["ok"] is False
    assert second["status"] == "already_exists"
    assert json_path.read_text(encoding="utf-8") == changed


def test_output_root_must_stay_under_worker_assignments(tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    result = worker_assignment.create_worker_assignment(
        repo_path=str(repo),
        goal_brief_path=str(source),
        output_root=str(repo / ".agent" / "somewhere_else"),
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_output_root"
    assert not (repo / ".agent" / "somewhere_else").exists()


def test_cli_json_dry_run_and_missing_source(capsys, tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    rc = cli.main([
        "--repo-path",
        str(repo),
        "--goal-brief",
        str(source),
        "--mode",
        "debug",
        "--role",
        "implementer",
        "--dry-run",
        "--json",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    assert parsed["status"] == "dry_run"
    assert parsed["record"]["source_type"] == "goal_brief"
    assert not (repo / ".agent" / "worker_assignments").exists()

    missing_rc = cli.main([
        "--repo-path",
        str(repo),
        "--goal-brief",
        str(repo / "missing.json"),
    ])
    captured = capsys.readouterr()
    assert missing_rc == 1
    assert "source_not_found" in captured.err


def test_cli_creates_json_and_markdown_from_goal_brief(capsys, tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    rc = cli.main([
        "--repo-path",
        str(repo),
        "--goal-brief",
        str(source),
        "--mode",
        "debug",
        "--role",
        "implementer",
        "--assignment-id",
        "cli-smoke",
        "--created-at",
        "2026-01-01T00:00:00Z",
        "--json",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    assert parsed["status"] == "draft_created"
    assert parsed["record"]["assignment_id"] == "cli-smoke"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()
    markdown = Path(parsed["md_path"]).read_text(encoding="utf-8")
    assert "## Stop Conditions" in markdown
    assert "Do not apply patches unless" in markdown


def test_cli_json_output_is_deterministic_with_fixed_metadata(capsys, tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)
    argv = [
        "--repo-path",
        str(repo),
        "--goal-brief",
        str(source),
        "--assignment-id",
        "stable-cli",
        "--created-at",
        "2026-01-01T00:00:00Z",
        "--dry-run",
        "--json",
    ]

    first_rc = cli.main(argv)
    first = capsys.readouterr().out
    second_rc = cli.main(argv)
    second = capsys.readouterr().out

    assert first_rc == 0
    assert second_rc == 0
    assert first == second
    assert json.loads(first)["record"]["assignment_id"] == "stable-cli"


def test_cli_existing_assignment_does_not_overwrite(capsys, tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)
    argv = [
        "--repo-path",
        str(repo),
        "--goal-brief",
        str(source),
        "--assignment-id",
        "no-overwrite",
        "--created-at",
        "2026-01-01T00:00:00Z",
        "--json",
    ]

    first_rc = cli.main(argv)
    first = json.loads(capsys.readouterr().out)
    json_path = Path(first["json_path"])
    original = json_path.read_text(encoding="utf-8")
    json_path.write_text(original + "\n", encoding="utf-8")
    changed = json_path.read_text(encoding="utf-8")
    second_rc = cli.main(argv)
    second = json.loads(capsys.readouterr().out)

    assert first_rc == 0
    assert second_rc == 1
    assert second["status"] == "already_exists"
    assert json_path.read_text(encoding="utf-8") == changed


def test_no_forbidden_imports_or_calls_in_worker_assignment_layers():
    module_tree = ast.parse(Path(worker_assignment.__file__).read_text(encoding="utf-8"))
    script_tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    calls: set[str] = set()
    for tree in (module_tree, script_tree):
        imports.update(_imported_modules(tree))
        calls.update(_called_names(tree))

    forbidden_import_roots = {
        "agents",
        "anthropic",
        "benchmarks",
        "database",
        "discord",
        "docker",
        "flask",
        "http",
        "httpx",
        "n8n",
        "openai",
        "patching",
        "project_evolution_mode",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "validator",
        "web",
    }
    forbidden_imports = {
        "core.control_engine",
        "core.executor",
        "core.lesson_store",
        "core.project_evolution_mode",
        "core.run_lifecycle",
        "core.sleeping_consultant",
        "core.validator",
        "scripts.run_background_dream_planner",
        "scripts.run_patch_proposal_queue",
        "scripts.seed_lessons_from_benchmark",
        "scripts.seed_lessons_from_proposals",
        "scripts.validate_evolution_patch_sandbox",
    }
    forbidden_calls = {
        "apply_patch",
        "apply_patch_plan",
        "call_api",
        "call_model",
        "connect",
        "create_dream",
        "create_lesson",
        "create_project_evolution",
        "execute",
        "executemany",
        "generate_content",
        "get_embedding",
        "open",
        "promote_lesson",
        "promote",
        "Popen",
        "post",
        "run",
        "run_benchmark",
        "run_benchmarks",
        "run_handoff",
        "run_overnight",
        "run_validation_command",
        "system",
        "urlopen",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots), imported_roots & forbidden_import_roots
    assert imports.isdisjoint(forbidden_imports), imports & forbidden_imports
    assert calls.isdisjoint(forbidden_calls), calls & forbidden_calls


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_assignment, "DEFAULT_WORKER_ASSIGNMENTS_DIRNAME", "worker_assignments")
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c


def test_web_route_creates_assignment_artifact(client, tmp_path):
    repo = _repo(tmp_path)
    source = _write_goal_brief(repo)

    resp = client.post(
        "/worker-assignments/create",
        json={
            "repo_path": str(repo),
            "goal_brief_path": str(source),
            "mode": "debug",
            "role": "implementer",
        },
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert Path(body["json_path"]).is_file()
    assert Path(body["md_path"]).is_file()
    assert body["record"]["assignment_id"]
    assert body["json_path"].endswith("worker_assignment.json")
    assert body["md_path"].endswith("worker_assignment.md")
    assert body["markdown"].startswith("# Worker Assignment")
    assert body["record"]["worker_launch_allowed"] is False
    assert body["record"]["apply_allowed"] is False
    assert body["record"]["validation_run"] is False


def test_web_button_is_draft_only(client):
    html = client.get("/").get_data(as_text=True)

    assert "Create Worker Assignment" in html
    assert 'id="workerAssignmentPreview"' in html
    assert 'id="workerAssignmentMarkdownText"' in html
    assert ">Copy assignment</button>" in html
    start = html.index("async function createWorkerAssignmentFromGoalBrief()")
    end = html.index("function _renderWorkerAssignmentPreview", start)
    function_body = html[start:end]

    assert 'fetch("/worker-assignments/create"' in function_body
    forbidden_endpoints = [
        "/handoffs/run",
        "/generate_patch",
        "/apply_patch",
        "/test_patch",
        "/benchmarks/run",
        "/dream",
        "/validation",
        "/lessons/create",
    ]
    for endpoint in forbidden_endpoints:
        assert endpoint not in function_body


def test_web_preview_renders_assignment_paths_and_copyable_markdown(client):
    html = client.get("/").get_data(as_text=True)
    start = html.index("function _renderWorkerAssignmentPreview")
    end = html.index("function copyWorkerAssignmentMarkdown", start)
    function_body = html[start:end]

    assert "Assignment ID" in function_body
    assert "JSON path" in function_body
    assert "Markdown path" in function_body
    assert "workerAssignmentMarkdownText" in function_body
    assert ".value = _workerAssignmentMarkdown" in function_body


def test_web_route_source_is_not_worker_launch_apply_validate_or_promote():
    source = Path("web/app.py").read_text(encoding="utf-8")
    route_start = source.index('@app.route("/worker-assignments/create"')
    route_end = source.index('@app.route("/handoffs/compose"', route_start)
    route_source = source[route_start:route_end]

    forbidden_tokens = [
        "run_handoff",
        "run_agent_web",
        "run_patch_plan_with_artifacts",
        "evaluate_patch_safety",
        "run_benchmarks",
        "run_overnight",
        "promote",
        "create_handoff_note",
    ]
    for token in forbidden_tokens:
        assert token not in route_source


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
