"""B.14 External Queue Review Recommendation tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from core import external_queue_review


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "external_queue_review.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "review_external_queue_item.py"


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-external-queue-review"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _seed_queue_item(base_dir: Path, **overrides: Any) -> tuple[Path, Path, str]:
    """Create a fake repo with a seeded external_queue_item.json. Returns (repo, item_path, queue_id)."""
    repo = base_dir / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    item = dict(_DEFAULT_ITEM)
    item.update(overrides)
    queue_id = item["queue_id"]
    queue_dir = repo / ".agent" / "external_queue" / queue_id
    queue_dir.mkdir(parents=True, exist_ok=True)
    item_path = queue_dir / "external_queue_item.json"
    item_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
    return repo, item_path, queue_id


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------

def test_reviews_valid_low_risk_research_item(tmp_path):
    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))

    assert record["status"] == "ok"
    assert record["mode"] == "external_queue_review"
    assert record["schema_version"] == "external_queue_review_v1"
    assert record["queue_id"] == queue_id
    assert record["source"] == "manual"
    assert record["kind"] == "research_wishlist"
    assert "Research embedding" in record["query"]
    assert record["recommendation"] in {
        "convert_to_dream_candidate",
        "convert_to_goal_brief_seed",
        "needs_more_evidence",
        "convert_to_project_evolution_candidate",
        "reject",
    }
    assert record["generated_at"]


def test_writes_json_and_markdown_artifacts(tmp_path):
    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    out = external_queue_review.write_external_queue_review_artifacts(str(repo), str(item_path))

    assert out["record"]["status"] == "ok"
    assert out["json_path"]
    assert out["md_path"]
    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.exists()
    assert md_path.exists()
    # Both files sit in the same directory as the source item
    assert json_path.parent == item_path.parent
    assert md_path.parent == item_path.parent
    assert json_path.name == "external_queue_review.json"
    assert md_path.name == "external_queue_review.md"


def test_human_approval_required_is_always_true(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["human_approval_required"] is True


def test_action_performed_is_always_false(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["action_performed"] is False


# ---------------------------------------------------------------------------
# Recommendation rules
# ---------------------------------------------------------------------------

def test_recommends_needs_more_evidence_when_result_missing(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        query="Find tools for codebase visualization",
        result="",
        source_url="",
        risk_level="medium",
        risk_reasons=["no result provided"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "needs_more_evidence"


def test_recommends_project_evolution_candidate_for_project_evolution_seed(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        kind="project_evolution_seed",
        query="Plan migration of authentication module from Flask-Login to FastAPI OAuth2",
        result="",
        risk_level="medium",
        risk_reasons=["project_evolution_seed without apply/deploy keywords (planning-only)"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "convert_to_project_evolution_candidate"


def test_recommends_project_evolution_candidate_for_broad_migration_query(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        kind="research_wishlist",
        query="We should migrate from Flask to FastAPI across the whole backend",
        result="",
        risk_level="medium",
        risk_reasons=["broad/architecture keyword: 'migrate from'"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "convert_to_project_evolution_candidate"


def test_recommends_goal_brief_seed_for_vague_user_goal(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        kind="research_wishlist",
        query="We need a better caching strategy for our API endpoints",
        result="",
        source_url="",
        risk_level="medium",
        risk_reasons=["no result provided"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "convert_to_goal_brief_seed"


def test_recommends_dream_candidate_for_narrow_bug_follow_up(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        kind="bug_seed",
        query="Fix memory leak in session_manager.py cleanup method",
        result="Heap profiling shows excessive allocations at session_manager.py:142 in cleanup().",
        risk_level="low",
        risk_reasons=["narrow research item with no mutation request"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "convert_to_dream_candidate"


def test_recommends_dream_candidate_for_narrow_research_with_result(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        kind="research_wishlist",
        query="Evaluate model2vec for our retrieval stack — is it faster than sentence-transformers",
        result="Benchmarks show model2vec is 3x faster with comparable recall on our test corpus.",
        risk_level="low",
        risk_reasons=["narrow research item with no mutation request"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "convert_to_dream_candidate"


def test_rejects_item_asking_for_direct_apply_patch(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        query="Apply patch to fix the broken imports in core/router.py",
        result="",
        risk_level="high",
        risk_reasons=["mutation/apply keyword: 'apply patch'"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "reject"
    assert record["recommendation_confidence"] == "high"


def test_rejects_item_asking_for_deploy_to_production(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        query="Deploy to production after merging the hotfix",
        result="",
        risk_level="high",
        risk_reasons=["mutation/apply keyword: 'production deploy'"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "reject"


def test_rejects_item_with_bypass_safety_phrase(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        query="Bypass safety checks and commit directly to main",
        result="",
        risk_level="high",
        risk_reasons=["high-risk keyword: 'credential'"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "reject"


def test_rejects_secret_heavy_item(tmp_path):
    repo, item_path, _ = _seed_queue_item(
        tmp_path,
        query="Use [REDACTED_SECRET] for the API call",
        result="",
        risk_level="high",
        risk_reasons=["possible secret detected: api_key_sk"],
    )
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["recommendation"] == "reject"
    assert any("possible secret detected" in r for r in record["recommendation_reasons"])


# ---------------------------------------------------------------------------
# Path containment and traversal
# ---------------------------------------------------------------------------

def test_blocks_item_path_outside_external_queue(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "malicious_item.json"
    outside.write_text(json.dumps(_DEFAULT_ITEM), encoding="utf-8")

    record = external_queue_review.build_external_queue_review(str(repo), str(outside))
    assert record["status"] == "error"
    assert record["error"]["code"] == "item_path_outside_external_queue"


def test_blocks_path_traversal_attempt(tmp_path):
    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    # Construct a traversal path that would escape external_queue/
    traversal = str(item_path.parent / ".." / ".." / "external_queue_item.json")
    record = external_queue_review.build_external_queue_review(str(repo), traversal)
    # After resolution the path escapes external_queue/ → blocked
    assert record["status"] == "error"
    assert record["error"]["code"] == "item_path_outside_external_queue"


def test_blocks_absolute_path_to_system_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    # Absolute path that is not inside .agent/external_queue/
    fake = tmp_path / "etc_passwd_fake.json"
    fake.write_text(json.dumps(_DEFAULT_ITEM), encoding="utf-8")

    record = external_queue_review.build_external_queue_review(str(repo), str(fake))
    assert record["status"] == "error"
    assert record["error"]["code"] == "item_path_outside_external_queue"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_validates_required_fields_missing(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    # Overwrite with item missing required fields
    bad = {"mode": "external_queue_import", "schema_version": "external_queue_import_v1"}
    item_path.write_text(json.dumps(bad), encoding="utf-8")

    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["status"] == "error"
    assert record["error"]["code"] == "item_missing_required_fields"


def test_validates_wrong_mode(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path, mode="wrong_mode")
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["status"] == "error"
    assert record["error"]["code"] == "item_wrong_mode"


def test_validates_wrong_schema_version(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path, schema_version="bad_version_v99")
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["status"] == "error"
    assert record["error"]["code"] == "item_wrong_schema_version"


def test_handles_missing_item_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    fake = repo / ".agent" / "external_queue" / "nonexistent-id" / "external_queue_item.json"

    record = external_queue_review.build_external_queue_review(str(repo), str(fake))
    assert record["status"] == "error"
    assert record["error"]["code"] == "item_file_missing"


def test_handles_invalid_json_item_file(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    item_path.write_text("this is not json", encoding="utf-8")

    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    assert record["status"] == "error"
    assert record["error"]["code"] == "item_file_invalid_json"


# ---------------------------------------------------------------------------
# Output gates
# ---------------------------------------------------------------------------

def test_forbidden_next_steps_include_auto_dream_apply_patch_modify_real_repo(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    forbidden = record["forbidden_next_steps"]
    assert "auto_dream" in forbidden
    assert "apply_patch" in forbidden
    assert "modify_real_repo" in forbidden
    assert "convert_without_human_approval" in forbidden


def test_allowed_next_steps_are_manual_only(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    allowed = record["allowed_next_steps"]
    for step in allowed:
        assert "auto" not in step, f"allowed step must not be automatic: {step}"
    assert "review_manually" in allowed
    assert "reject" in allowed


def test_guardrails_list_present_in_record(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    record = external_queue_review.build_external_queue_review(str(repo), str(item_path))
    guardrails = record["guardrails"]
    assert isinstance(guardrails, list)
    assert len(guardrails) >= 6


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def test_markdown_includes_all_guardrail_sentences(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    out = external_queue_review.write_external_queue_review_artifacts(str(repo), str(item_path))
    md = Path(out["md_path"]).read_text(encoding="utf-8")
    assert "This review is advisory only." in md
    assert "No conversion was performed." in md
    assert "No Dream item was created." in md
    assert "No Project Evolution plan was created." in md
    assert "No patch was generated or applied." in md
    assert "Human approval is required before entering any stronger mode." in md


def test_markdown_has_required_sections(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    out = external_queue_review.write_external_queue_review_artifacts(str(repo), str(item_path))
    md = Path(out["md_path"]).read_text(encoding="utf-8")
    for section in (
        "# External Queue Review",
        "## Decision",
        "## Source Item",
        "## Recommendation",
        "## Reasons",
        "## Missing Evidence",
        "## Suggested Next Prompt",
        "## Allowed Next Steps",
        "## Forbidden Next Steps",
        "## Guardrails",
    ):
        assert section in md, f"markdown missing section: {section}"


# ---------------------------------------------------------------------------
# No side-effects: no Dream/GoalBrief/ProjectEvolution artifacts created
# ---------------------------------------------------------------------------

def test_does_not_create_dream_or_evolution_artifacts(tmp_path):
    repo, item_path, queue_id = _seed_queue_item(
        tmp_path,
        kind="project_evolution_seed",
        query="Plan migration from Flask to FastAPI",
    )
    external_queue_review.write_external_queue_review_artifacts(str(repo), str(item_path))

    assert not (repo / ".agent" / "dream").exists()
    assert not (repo / ".agent" / "goal_briefs").exists()
    assert not (repo / ".agent" / "project_evolution").exists()
    # Only the review artifacts should exist alongside the item
    queue_dir = repo / ".agent" / "external_queue" / queue_id
    created = {p.name for p in queue_dir.iterdir()}
    assert "external_queue_item.json" in created
    assert "external_queue_review.json" in created
    assert "external_queue_review.md" in created
    # Nothing else
    assert created == {
        "external_queue_item.json",
        "external_queue_review.json",
        "external_queue_review.md",
    }


def test_does_not_modify_source_item_file(tmp_path):
    repo, item_path, _ = _seed_queue_item(tmp_path)
    original = item_path.read_text(encoding="utf-8")
    external_queue_review.write_external_queue_review_artifacts(str(repo), str(item_path))
    assert item_path.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_writes_artifacts(tmp_path):
    from scripts.review_external_queue_item import main as cli_main

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    rc = cli_main(["--repo-path", str(repo), "--item-path", str(item_path)])
    assert rc == 0
    assert (item_path.parent / "external_queue_review.json").exists()
    assert (item_path.parent / "external_queue_review.md").exists()


def test_cli_returns_nonzero_on_bad_path(tmp_path):
    from scripts.review_external_queue_item import main as cli_main

    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "bad.json"
    outside.write_text(json.dumps(_DEFAULT_ITEM), encoding="utf-8")

    rc = cli_main(["--repo-path", str(repo), "--item-path", str(outside)])
    assert rc == 1


# ---------------------------------------------------------------------------
# AST purity — no forbidden imports or calls
# ---------------------------------------------------------------------------

def test_no_forbidden_imports_or_calls_in_module():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE_PATH))

    forbidden_imports = {
        "anthropic", "subprocess", "requests", "httpx", "openai", "aiohttp",
    }
    found_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in forbidden_imports:
                    found_imports.append(alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in forbidden_imports:
                found_imports.append(node.module)
    assert not found_imports, f"forbidden imports found: {found_imports}"

    forbidden_calls = {
        "apply_patch", "call_model", "run_benchmark",
        "create_dream", "create_goal_brief", "create_project_evolution",
    }
    found_calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name and name in forbidden_calls:
                found_calls.append(name)
    assert not found_calls, f"forbidden calls found: {found_calls}"
