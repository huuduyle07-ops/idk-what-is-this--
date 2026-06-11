"""B.15 External Queue Index/List tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "external_queue_index.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "list_external_queue.py"


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-external-queue-index"
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
    "received_at": "",
    "auto_dream_allowed": False,
    "human_review_required": True,
    "import_status": "pending_review",
    "risk_level": "low",
    "risk_reasons": ["narrow research item with no mutation request"],
    "allowed_next_steps": ["review_manually", "reject"],
    "forbidden_next_steps": ["auto_dream", "auto_patch"],
    "reviewer_checklist": ["Review the item."],
    "metadata": {},
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
    "recommendation": "convert_to_dream_candidate",
    "recommendation_confidence": "medium",
    "recommendation_reasons": ["narrow research item with concrete result"],
    "missing_evidence": [],
    "suggested_next_prompt": "Create a Dream candidate after human approval.",
    "allowed_next_steps": ["review_manually", "reject"],
    "forbidden_next_steps": ["auto_dream", "auto_patch", "apply_patch"],
    "human_approval_required": True,
    "action_performed": False,
    "guardrails": ["No conversion was performed."],
}


def test_empty_queue_returns_empty_index(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo = _make_repo(tmp_path)

    assert build_external_queue_index(str(repo)) == []


def test_valid_queue_artifact_appears_in_index(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, item_path, queue_id = _seed_queue_item(
        tmp_path,
        queue_id="20260101T000000Z_discord-embedding",
        source="discord",
        title="Embedding provider research",
        summary="Compare local and remote embedding providers.",
    )

    items = build_external_queue_index(str(repo))

    assert len(items) == 1
    item = items[0]
    assert item["queue_id"] == queue_id
    assert item["path"] == str(item_path)
    assert item["title"] == "Embedding provider research"
    assert item["summary"] == "Compare local and remote embedding providers."
    assert item["source_kind"] == "discord"
    assert item["status"] == "queued"
    assert item["risk_level"] == "low"
    assert item["created_at"] == "2026-01-01T00:00:00Z"
    assert item["gate_status"]["auto_dream_allowed"] is False
    assert item["gate_status"]["human_review_required"] is True
    assert item["safe_to_display"] is True
    assert item["executable_or_promotable"] is False
    assert item["linked_paths"]["item"] == str(item_path)


def test_review_artifact_marks_item_reviewed_and_promotable_candidate(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    review_path = _seed_review(item_path.parent)

    [item] = build_external_queue_index(str(repo))

    assert item["queue_id"] == queue_id
    assert item["status"] == "reviewed"
    assert item["review_status"] == "ok"
    assert item["recommendation"] == "convert_to_dream_candidate"
    assert item["recommendation_confidence"] == "medium"
    assert item["executable_or_promotable"] is True
    assert item["linked_paths"]["item"] == str(item_path)
    assert item["linked_paths"]["review"] == str(review_path)
    assert item["gate_status"]["human_approval_required"] is True
    assert item["gate_status"]["action_performed"] is False


def test_invalid_json_artifact_appears_as_invalid_not_crash(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo = _make_repo(tmp_path)
    item_path = repo / ".agent" / "external_queue" / "bad-item" / "external_queue_item.json"
    item_path.parent.mkdir(parents=True)
    item_path.write_text("{ not valid json", encoding="utf-8")

    [item] = build_external_queue_index(str(repo))

    assert item["queue_id"] == "bad-item"
    assert item["path"] == str(item_path)
    assert item["status"] == "invalid"
    assert item["source_kind"] == "unknown"
    assert item["risk_level"] == "unknown"
    assert item["safe_to_display"] is False
    assert item["executable_or_promotable"] is False
    assert "valid JSON" in item["validation_error_summary"]


def test_invalid_review_artifact_does_not_make_item_promotable(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    review_path = item_path.parent / "external_queue_review.json"
    review_path.write_text("{ not valid json", encoding="utf-8")

    [item] = build_external_queue_index(str(repo))

    assert item["queue_id"] == queue_id
    assert item["status"] == "queued"
    assert item["review_status"] == "invalid"
    assert item["recommendation"] == ""
    assert item["executable_or_promotable"] is False
    assert item["linked_paths"]["review"] == str(review_path)
    assert "valid JSON" in item["validation_error_summary"]


def test_wrong_schema_review_artifact_does_not_make_item_promotable(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(
        item_path.parent,
        mode="wrong_mode",
        schema_version="wrong_schema",
        recommendation="convert_to_dream_candidate",
    )

    [item] = build_external_queue_index(str(repo))

    assert item["queue_id"] == queue_id
    assert item["status"] == "queued"
    assert item["review_status"] == "invalid"
    assert item["recommendation"] == ""
    assert item["executable_or_promotable"] is False
    assert "review expected mode" in item["validation_error_summary"]


def test_missing_optional_fields_are_tolerated(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, _item_path, queue_id = _seed_queue_item(
        tmp_path,
        result=None,
        kind=None,
        risk_level=None,
        risk_reasons=None,
        summary=None,
        title=None,
    )

    [item] = build_external_queue_index(str(repo))

    assert item["queue_id"] == queue_id
    assert item["status"] == "queued"
    assert item["kind"] == "unknown"
    assert item["risk_level"] == "unknown"
    assert item["summary"] == ""


def test_status_filter_returns_only_matching_items(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, queued_path, _ = _seed_queue_item(
        tmp_path,
        queue_id="a-queued",
        source="discord",
    )
    reviewed_path = _seed_second_item(repo, queue_id="b-reviewed", source="n8n")
    _seed_review(reviewed_path.parent, queue_id="b-reviewed")
    rejected_path = _seed_second_item(repo, queue_id="c-rejected", source="manual")
    _seed_review(
        rejected_path.parent,
        queue_id="c-rejected",
        recommendation="reject",
        recommendation_confidence="high",
    )

    assert [i["queue_id"] for i in build_external_queue_index(str(repo), status="queued")] == [
        "a-queued"
    ]
    assert [i["queue_id"] for i in build_external_queue_index(str(repo), status="reviewed")] == [
        "b-reviewed"
    ]
    assert [i["queue_id"] for i in build_external_queue_index(str(repo), status="rejected")] == [
        "c-rejected"
    ]
    assert queued_path.exists()


def test_source_filter_returns_only_matching_items(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, _item_path, _ = _seed_queue_item(
        tmp_path,
        queue_id="a-discord",
        source="discord",
    )
    _seed_second_item(repo, queue_id="b-n8n", source="n8n")

    items = build_external_queue_index(str(repo), source="n8n")

    assert [i["queue_id"] for i in items] == ["b-n8n"]


def test_limit_returns_deterministic_prefix(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, _item_path, _ = _seed_queue_item(tmp_path, queue_id="b-second")
    _seed_second_item(repo, queue_id="a-first")
    _seed_second_item(repo, queue_id="c-third")

    items = build_external_queue_index(str(repo), limit=2)

    assert [i["queue_id"] for i in items] == ["a-first", "b-second"]


def test_json_output_is_deterministic(tmp_path):
    from core.external_queue_index import (
        build_external_queue_index,
        render_external_queue_index_json,
    )

    repo, _item_path, _ = _seed_queue_item(tmp_path, queue_id="a-json")
    items = build_external_queue_index(str(repo))

    first = render_external_queue_index_json(items)
    second = render_external_queue_index_json(items)

    assert first == second
    assert json.loads(first) == items
    assert first.endswith("\n")


def test_cli_table_and_json_are_read_only(tmp_path, capsys):
    from scripts import list_external_queue as cli

    repo, item_path, queue_id = _seed_queue_item(
        tmp_path,
        queue_id="a-cli",
        source="discord",
    )
    before = item_path.read_text(encoding="utf-8")

    rc = cli.main(["--repo-path", str(repo)])
    table_output = capsys.readouterr().out

    assert rc == 0
    assert "QUEUE ID" in table_output
    assert queue_id in table_output
    assert item_path.read_text(encoding="utf-8") == before

    rc = cli.main(["--repo-path", str(repo), "--json", "--source", "discord", "--limit", "1"])
    json_output = capsys.readouterr().out

    assert rc == 0
    assert json.loads(json_output)[0]["queue_id"] == queue_id
    assert item_path.read_text(encoding="utf-8") == before


def test_listing_does_not_mutate_source_files(tmp_path):
    from core.external_queue_index import build_external_queue_index

    repo, _item_path, _ = _seed_queue_item(tmp_path)
    source_file = repo / "core" / "main.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("def main():\n    return 'unchanged'\n", encoding="utf-8")
    original = source_file.read_text(encoding="utf-8")

    build_external_queue_index(str(repo))

    assert source_file.read_text(encoding="utf-8") == original


def test_no_forbidden_imports_or_calls_in_index_layer():
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
        "discord",
        "docker",
        "httpx",
        "n8n",
        "openai",
        "patching",
        "requests",
        "subprocess",
        "validator",
        "web",
        "zalo",
    }
    forbidden_imports = {
        "core.control_engine",
        "core.executor",
        "core.mode_router",
        "core.run_lifecycle",
        "core.sleeping_consultant",
        "core.validator",
        "database",
    }
    forbidden_calls = {
        "apply_patch",
        "apply_patch_plan",
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
        "promote_lesson",
        "run_benchmark",
        "run_benchmarks",
        "run_validation_command",
        "Popen",
        "system",
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
    item = dict(_DEFAULT_ITEM)
    item.update({k: v for k, v in overrides.items() if v is not None})
    for key, value in overrides.items():
        if value is None:
            item.pop(key, None)
    queue_id = item.get("queue_id", "artifact-without-id")
    queue_dir = repo / ".agent" / "external_queue" / queue_id
    queue_dir.mkdir(parents=True, exist_ok=True)
    item_path = queue_dir / "external_queue_item.json"
    item_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
    return repo, item_path, queue_id


def _seed_second_item(repo: Path, **overrides: Any) -> Path:
    item = dict(_DEFAULT_ITEM)
    item.update({k: v for k, v in overrides.items() if v is not None})
    for key, value in overrides.items():
        if value is None:
            item.pop(key, None)
    queue_id = item.get("queue_id", "artifact-without-id")
    queue_dir = repo / ".agent" / "external_queue" / queue_id
    queue_dir.mkdir(parents=True, exist_ok=True)
    item_path = queue_dir / "external_queue_item.json"
    item_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
    return item_path


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
