"""B.17 External Queue Export Draft tests."""
from __future__ import annotations

import ast
import json
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
README_PATH = PROJECT_ROOT / "README.md"
MODULE_PATH = PROJECT_ROOT / "core" / "external_queue_export.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "export_external_queue_item.py"


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-external-queue-export"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


_DEFAULT_ITEM: dict[str, Any] = {
    "generated_at": "2026-01-01T00:00:00Z",
    "mode": "external_queue_import",
    "schema_version": "external_queue_import_v1",
    "status": "ok",
    "queue_id": "20260101T000000Z_manual-test-item",
    "source": "manual",
    "kind": "research_wishlist",
    "query": "Research embedding providers for codebase mapping in AI coding agents",
    "result": "model2vec and Gemini embeddings look viable for our retrieval stack.",
    "source_url": "https://discord.com/channels/123/456",
    "submitted_by": "operator",
    "received_at": "2026-01-01T00:00:00Z",
    "auto_dream_allowed": False,
    "human_review_required": True,
    "import_status": "pending_review",
    "risk_level": "low",
    "risk_reasons": ["narrow research item with no mutation request"],
    "allowed_next_steps": ["review_manually", "reject"],
    "forbidden_next_steps": ["auto_dream", "auto_patch"],
    "reviewer_checklist": ["Review the item."],
    "metadata": {
        "title": "Embedding provider research",
        "summary": "Compare local and remote embedding providers.",
        "tags": ["embeddings", "retrieval"],
        "categories": ["research"],
    },
}

_DEFAULT_REVIEW: dict[str, Any] = {
    "generated_at": "2026-01-02T00:00:00Z",
    "mode": "external_queue_review",
    "schema_version": "external_queue_review_v1",
    "status": "ok",
    "queue_id": "20260101T000000Z_manual-test-item",
    "source_item_path": "",
    "source": "manual",
    "kind": "research_wishlist",
    "query": "Research embedding providers for codebase mapping in AI coding agents",
    "import_status": "pending_review",
    "source_risk_level": "low",
    "recommendation": "convert_to_goal_brief_seed",
    "recommendation_confidence": "medium",
    "recommendation_reasons": ["query expresses a user goal that needs clarification"],
    "missing_evidence": ["confirm current provider pricing"],
    "suggested_next_prompt": "Create a Goal Brief seed after human approval.",
    "allowed_next_steps": ["review_manually", "reject"],
    "forbidden_next_steps": ["auto_dream", "auto_patch", "apply_patch"],
    "human_approval_required": True,
    "action_performed": False,
    "guardrails": ["No conversion was performed."],
}


def test_valid_reviewed_item_exports_goal_brief_seed(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    review_path = _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")

    result = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")

    assert result["ok"] is True
    assert result["status"] == "draft_created"
    assert result["queue_id"] == queue_id
    assert result["target"] == "goal_brief_seed"
    assert result["json_path"].endswith("goal_brief_seed_draft.json")
    assert result["md_path"].endswith("goal_brief_seed_draft.md")
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()

    draft = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert draft["export_id"] == f"{queue_id}_goal_brief_seed_draft"
    assert draft["queue_id"] == queue_id
    assert draft["source_item_path"] == str(item_path)
    assert draft["source_review_path"] == str(review_path)
    assert draft["target"] == "goal_brief_seed"
    assert draft["target_recommendation"] == "convert_to_goal_brief_seed"
    assert draft["title"] == "Embedding provider research"
    assert draft["summary"] == "Compare local and remote embedding providers."
    assert draft["export_status"] == "draft_created"
    assert draft["action_performed"] is False
    assert draft["human_approval_required"] is True
    assert draft["target_workflow_started"] is False
    assert draft["model_called"] is False
    assert draft["webhook_called"] is False
    assert draft["patch_applied"] is False
    assert draft["promotion_performed"] is False


def test_missing_queue_id_returns_not_found_without_export(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo = _make_repo(tmp_path)

    result = export_external_queue_item(str(repo), "missing-id", "goal_brief_seed")

    assert result["ok"] is False
    assert result["status"] == "not_found"
    assert result["error"]["code"] == "queue_id_not_found"
    assert not (repo / ".agent" / "external_queue_exports").exists()


def test_duplicate_queue_id_returns_ambiguous_without_export(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, _ = _seed_queue_item(tmp_path, queue_id="duplicate-id")
    _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")
    second_path = _seed_second_item(repo, queue_id="duplicate-id", directory="other-artifact")
    _seed_review(second_path.parent, recommendation="convert_to_goal_brief_seed")

    result = export_external_queue_item(str(repo), "duplicate-id", "goal_brief_seed")

    assert result["ok"] is False
    assert result["status"] == "ambiguous"
    assert result["error"]["code"] == "queue_id_ambiguous"
    assert len(result["matches"]) == 2
    assert not (repo / ".agent" / "external_queue_exports").exists()


def test_invalid_item_blocks_export(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo = _make_repo(tmp_path)
    item_path = repo / ".agent" / "external_queue" / "bad-item" / "external_queue_item.json"
    item_path.parent.mkdir(parents=True)
    item_path.write_text("{ not valid json", encoding="utf-8")

    result = export_external_queue_item(str(repo), "bad-item", "goal_brief_seed")

    assert result["ok"] is False
    assert result["status"] == "invalid"
    assert result["error"]["code"] == "item_invalid"
    assert "valid JSON" in result["error"]["message"]
    assert not (repo / ".agent" / "external_queue_exports").exists()


def test_invalid_or_missing_review_blocks_export_by_default(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)

    missing = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")
    assert missing["ok"] is False
    assert missing["status"] == "blocked"
    assert missing["error"]["code"] == "review_missing"

    review_path = item_path.parent / "external_queue_review.json"
    review_path.write_text("{ not valid json", encoding="utf-8")

    invalid = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")
    assert invalid["ok"] is False
    assert invalid["status"] == "blocked"
    assert invalid["error"]["code"] == "review_invalid"
    assert not (repo / ".agent" / "external_queue_exports").exists()


@pytest.mark.parametrize(
    ("recommendation", "target"),
    [
        ("convert_to_goal_brief_seed", "goal_brief_seed"),
        ("convert_to_dream_candidate", "dream_candidate_seed"),
        ("convert_to_project_evolution_candidate", "project_evolution_seed"),
    ],
)
def test_review_recommendation_allows_matching_target(tmp_path, recommendation, target):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation=recommendation)

    result = export_external_queue_item(str(repo), queue_id, target)

    assert result["ok"] is True
    assert result["status"] == "draft_created"
    draft = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert draft["target"] == target
    assert draft["target_recommendation"] == recommendation


def test_mismatched_target_is_blocked(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_dream_candidate")

    result = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["error"]["code"] == "target_mismatch"
    assert result["expected_target"] == "dream_candidate_seed"
    assert not (repo / ".agent" / "external_queue_exports").exists()


def test_unreviewed_item_is_blocked_by_default(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, _item_path, queue_id = _seed_queue_item(tmp_path)

    result = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["error"]["code"] == "review_missing"


def test_markdown_draft_written(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")

    result = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")

    assert "# External Queue Export Draft" in markdown
    assert "goal_brief_seed" in markdown
    assert "Target workflow started: `False`" in markdown
    assert "Human approval required: `True`" in markdown


def test_existing_draft_returns_already_exists_and_does_not_overwrite(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")

    first = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")
    json_path = Path(first["json_path"])
    original = json_path.read_text(encoding="utf-8")
    json_path.write_text(original + "\n", encoding="utf-8")
    changed = json_path.read_text(encoding="utf-8")

    second = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")

    assert second["ok"] is False
    assert second["status"] == "already_exists"
    assert second["json_path"] == str(json_path)
    assert json_path.read_text(encoding="utf-8") == changed


def test_dry_run_writes_nothing(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")

    result = export_external_queue_item(
        str(repo),
        queue_id,
        "goal_brief_seed",
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert result["record"]["action_performed"] is False
    assert not Path(result["json_path"]).exists()
    assert not Path(result["md_path"]).exists()


def test_json_output_is_deterministic(tmp_path, capsys):
    from core.external_queue_export import render_external_queue_export_json
    from scripts import export_external_queue_item as cli

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")

    rc = cli.main([
        "--repo-path",
        str(repo),
        "--queue-id",
        queue_id,
        "--target",
        "goal_brief_seed",
        "--dry-run",
        "--json",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    assert parsed["status"] == "dry_run"
    assert parsed["record"]["target"] == "goal_brief_seed"
    assert render_external_queue_export_json(parsed) == output


def test_target_specific_goal_brief_fields(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")

    result = export_external_queue_item(str(repo), queue_id, "goal_brief_seed")
    draft = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))

    assert draft["suggested_goal"]
    assert isinstance(draft["constraints"], list)
    assert draft["likely_mode"] == "goal_brief_seed"
    assert isinstance(draft["risk_notes"], list)
    assert isinstance(draft["evidence_needed"], list)
    assert isinstance(draft["suggested_validation"], list)


def test_target_specific_dream_fields(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_dream_candidate")

    result = export_external_queue_item(str(repo), queue_id, "dream_candidate_seed")
    draft = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))

    assert draft["dream_seed_title"]
    assert draft["dream_seed_summary"]
    assert isinstance(draft["research_sources"], list)
    assert draft["why_interesting"]
    assert isinstance(draft["risk_notes"], list)
    assert draft["no_dream_run"] is True


def test_target_specific_project_evolution_fields(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(
        tmp_path,
        kind="project_evolution_seed",
        query="Plan a retrieval architecture migration for core/retriever.py",
    )
    _seed_review(item_path.parent, recommendation="convert_to_project_evolution_candidate")

    result = export_external_queue_item(str(repo), queue_id, "project_evolution_seed")
    draft = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))

    assert draft["evolution_goal"]
    assert draft["affected_area_guess"]
    assert isinstance(draft["constraints"], list)
    assert isinstance(draft["risk_notes"], list)
    assert isinstance(draft["suggested_read_first_files"], list)
    assert draft["no_project_plan_created"] is True


def test_cli_default_output_and_nonzero_blocked_status(tmp_path, capsys):
    from scripts import export_external_queue_item as cli

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")

    rc = cli.main([
        "--repo-path",
        str(repo),
        "--queue-id",
        queue_id,
        "--target",
        "goal_brief_seed",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    assert "draft_created" in output
    assert "goal_brief_seed_draft.json" in output

    blocked_rc = cli.main([
        "--repo-path",
        str(repo),
        "--queue-id",
        "missing-id",
        "--target",
        "goal_brief_seed",
    ])
    captured = capsys.readouterr()
    assert blocked_rc == 1
    assert "not_found" in captured.err


def test_output_root_can_redirect_draft_folder(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_goal_brief_seed")
    custom_root = repo / ".agent" / "custom_external_exports"

    result = export_external_queue_item(
        str(repo),
        queue_id,
        "goal_brief_seed",
        output_root=str(custom_root),
    )

    assert result["status"] == "draft_created"
    assert Path(result["json_path"]).parent == custom_root / queue_id


def test_dream_candidate_seed_smoke_inert_flags_and_no_dream_artifact(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent, recommendation="convert_to_dream_candidate")

    result = export_external_queue_item(str(repo), queue_id, "dream_candidate_seed")

    assert result["ok"] is True
    assert result["status"] == "draft_created"
    assert result["target"] == "dream_candidate_seed"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()

    draft = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    # target-specific inert guard
    assert draft["no_dream_run"] is True
    # shared inert safety flags
    assert draft["action_performed"] is False
    assert draft["human_approval_required"] is True
    assert draft["target_workflow_started"] is False
    assert draft["model_called"] is False
    assert draft["webhook_called"] is False
    assert draft["patch_applied"] is False
    assert draft["promotion_performed"] is False
    # no Dream inbox artifact created anywhere under repo
    dream_inbox = repo / ".agent" / "dream"
    assert not dream_inbox.exists(), "dream inbox must not be created by export"


def test_project_evolution_seed_smoke_inert_flags_and_no_plan_artifact(tmp_path):
    from core.external_queue_export import export_external_queue_item

    repo, item_path, queue_id = _seed_queue_item(
        tmp_path,
        kind="project_evolution_seed",
        query="Plan a retrieval architecture migration",
    )
    _seed_review(item_path.parent, recommendation="convert_to_project_evolution_candidate")

    result = export_external_queue_item(str(repo), queue_id, "project_evolution_seed")

    assert result["ok"] is True
    assert result["status"] == "draft_created"
    assert result["target"] == "project_evolution_seed"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()

    draft = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    # target-specific inert guard
    assert draft["no_project_plan_created"] is True
    # shared inert safety flags
    assert draft["action_performed"] is False
    assert draft["human_approval_required"] is True
    assert draft["target_workflow_started"] is False
    assert draft["model_called"] is False
    assert draft["webhook_called"] is False
    assert draft["patch_applied"] is False
    assert draft["promotion_performed"] is False
    # no Project Evolution plan artifact created anywhere under repo
    pe_dir = repo / ".agent" / "project_evolution"
    assert not pe_dir.exists(), "project_evolution dir must not be created by export"


def test_readme_external_queue_export_examples_use_supported_cli_flags():
    from scripts import export_external_queue_item as cli

    section = _markdown_section(
        README_PATH.read_text(encoding="utf-8"),
        "#### Export reviewed item as draft",
        "#### Manual CLI import",
    )
    commands = [
        line.strip()
        for line in section.splitlines()
        if line.strip().startswith("python scripts/export_external_queue_item.py")
    ]

    assert len(commands) >= 3
    assert any("--json" in command for command in commands)
    assert any("--dry-run" in command for command in commands)

    parser = cli.build_parser()
    for command in commands:
        argv = shlex.split(command)[2:]
        parser.parse_args(argv)


def test_readme_export_examples_cover_all_three_targets():
    """All three supported targets must appear in the README export section."""
    section = _markdown_section(
        README_PATH.read_text(encoding="utf-8"),
        "#### Export reviewed item as draft",
        "#### Manual CLI import",
    )
    commands = [
        line.strip()
        for line in section.splitlines()
        if line.strip().startswith("python scripts/export_external_queue_item.py")
    ]
    targets_in_readme = {
        part
        for command in commands
        for i, part in enumerate(command.split())
        if i > 0 and command.split()[i - 1] == "--target"
    }
    from core.external_queue_export import SUPPORTED_TARGETS
    for target in SUPPORTED_TARGETS:
        assert target in targets_in_readme, (
            f"README export section is missing an example for target {target!r}"
        )


def test_no_forbidden_imports_or_calls_in_export_layer():
    trees = [
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH)),
        ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"), filename=str(SCRIPT_PATH)),
    ]
    imports: set[str] = set()
    calls: set[str] = set()
    for tree in trees:
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
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "validator",
        "web",
        "zalo",
    }
    forbidden_imports = {
        "core.control_engine",
        "core.executor",
        "core.external_queue_import",
        "core.external_queue_review",
        "core.goal_brief",
        "core.lesson_store",
        "core.mode_router",
        "core.project_evolution_mode",
        "core.run_lifecycle",
        "core.sleeping_consultant",
        "core.validator",
        "database",
    }
    forbidden_calls = {
        "apply_patch",
        "apply_patch_plan",
        "build_external_queue_review",
        "call_api",
        "call_model",
        "connect",
        "create_dream",
        "create_goal_brief",
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
        "run_validation_command",
        "system",
        "urlopen",
        "write_external_queue_review_artifacts",
        "write_external_queue_item_artifacts",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots), (
        f"Forbidden import roots: {imported_roots & forbidden_import_roots}"
    )
    assert imports.isdisjoint(forbidden_imports), (
        f"Forbidden imports: {imports & forbidden_imports}"
    )
    assert calls.isdisjoint(forbidden_calls), (
        f"Forbidden calls: {calls & forbidden_calls}"
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return repo


def _seed_queue_item(base_dir: Path, **overrides: Any) -> tuple[Path, Path, str]:
    repo = _make_repo(base_dir)
    item_path, queue_id = _write_queue_item(repo, **overrides)
    return repo, item_path, queue_id


def _seed_second_item(repo: Path, *, directory: str | None = None, **overrides: Any) -> Path:
    item_path, _queue_id = _write_queue_item(repo, directory=directory, **overrides)
    return item_path


def _write_queue_item(
    repo: Path,
    *,
    directory: str | None = None,
    **overrides: Any,
) -> tuple[Path, str]:
    item = dict(_DEFAULT_ITEM)
    metadata = dict(_DEFAULT_ITEM["metadata"])
    if "title" in overrides:
        metadata["title"] = overrides.pop("title")
    if "summary" in overrides:
        metadata["summary"] = overrides.pop("summary")
    item["metadata"] = metadata
    item.update({k: v for k, v in overrides.items() if v is not None})
    for key, value in overrides.items():
        if value is None:
            item.pop(key, None)
    queue_id = item.get("queue_id", "artifact-without-id")
    artifact_dir = directory or queue_id
    queue_dir = repo / ".agent" / "external_queue" / artifact_dir
    queue_dir.mkdir(parents=True, exist_ok=True)
    item_path = queue_dir / "external_queue_item.json"
    item_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
    return item_path, queue_id


def _seed_review(queue_dir: Path, **overrides: Any) -> Path:
    review = dict(_DEFAULT_REVIEW)
    item_path = queue_dir / "external_queue_item.json"
    if item_path.exists():
        item = json.loads(item_path.read_text(encoding="utf-8"))
        review["queue_id"] = item.get("queue_id", review["queue_id"])
        review["source_item_path"] = str(item_path)
        review["source"] = item.get("source", review["source"])
        review["kind"] = item.get("kind", review["kind"])
        review["query"] = item.get("query", review["query"])
        review["import_status"] = item.get("import_status", review["import_status"])
        review["source_risk_level"] = item.get("risk_level", review["source_risk_level"])
    review.update(overrides)
    review_path = queue_dir / "external_queue_review.json"
    review_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
    return review_path


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


def _markdown_section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]
