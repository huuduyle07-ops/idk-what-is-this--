"""B.12 External Queue Import Contract tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from core import external_queue_import


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "external_queue_import.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "import_external_queue_item.py"


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-external-queue-import"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------

def test_imports_minimal_manual_item(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Research embedding providers for the project",
    )

    assert record["status"] == "ok"
    assert record["mode"] == "external_queue_import"
    assert record["schema_version"] == "external_queue_import_v1"
    assert record["source"] == "manual"
    assert record["kind"] == "research_wishlist"
    assert "Research embedding" in record["query"]
    assert record["queue_id"]
    assert record["generated_at"]


def test_imports_discord_research_wishlist_item(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="discord",
        kind="research_wishlist",
        query="What embedding providers are compatible with our retrieval stack?",
        result="Gemini embeddings and model2vec look viable.",
        submitted_by="alice",
        source_url="https://discord.com/channels/123/456/789",
    )

    assert record["status"] == "ok"
    assert record["source"] == "discord"
    assert record["submitted_by"] == "alice"
    assert record["source_url"] == "https://discord.com/channels/123/456/789"
    assert "Gemini" in record["result"]


def test_writes_json_and_markdown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    out = external_queue_import.write_external_queue_item_artifacts(
        repo_path=str(repo),
        source="discord",
        kind="research_wishlist",
        query="Evaluate graph weight alternatives",
    )

    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file(), "JSON artifact not written"
    assert md_path.is_file(), "Markdown artifact not written"
    assert json_path.name == "external_queue_item.json"
    assert md_path.name == "external_queue_item.md"

    queue_root = (repo / ".agent" / "external_queue").resolve()
    json_path.resolve().relative_to(queue_root)
    md_path.resolve().relative_to(queue_root)

    persisted = json.loads(json_path.read_text(encoding="utf-8"))
    assert persisted == out["record"]


# ---------------------------------------------------------------------------
# Hardcoded gates
# ---------------------------------------------------------------------------

def test_auto_dream_allowed_defaults_false(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Test query",
    )
    assert record["auto_dream_allowed"] is False


def test_human_review_required_defaults_true(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Test query",
    )
    assert record["human_review_required"] is True


def test_import_status_defaults_pending_review(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Test query",
    )
    assert record["import_status"] == "pending_review"


def test_gates_cannot_be_overridden_by_caller(tmp_path):
    repo = _make_repo(tmp_path)
    # The function signature intentionally doesn't accept these kwargs.
    # Calling with only the expected args should still lock the gates.
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="n8n",
        kind="bug_seed",
        query="Found a bug in the retrieval layer",
    )
    assert record["auto_dream_allowed"] is False
    assert record["human_review_required"] is True
    assert record["import_status"] == "pending_review"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_rejects_empty_query(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="",
    )
    assert record["status"] == "error"
    assert record["error"]["code"] == "empty_query"
    assert record["auto_dream_allowed"] is False
    assert record["human_review_required"] is True


def test_rejects_whitespace_only_query(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="   \n\t  ",
    )
    assert record["status"] == "error"
    assert record["error"]["code"] == "empty_query"


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def test_normalizes_unknown_source_to_manual(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="telegram",
        kind="research_wishlist",
        query="Research query",
    )
    assert record["status"] == "ok"
    assert record["source"] == "manual"


def test_normalizes_unknown_kind_to_research_wishlist(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="unknown_kind_xyz",
        query="Research query",
    )
    assert record["status"] == "ok"
    assert record["kind"] == "research_wishlist"


def test_known_sources_preserved(tmp_path):
    repo = _make_repo(tmp_path)
    for source in ("discord", "n8n", "zalo", "webhook", "manual"):
        record = external_queue_import.build_external_queue_item(
            repo_path=str(repo),
            source=source,
            kind="research_wishlist",
            query=f"Query from {source}",
        )
        assert record["source"] == source, f"source {source!r} was not preserved"


def test_known_kinds_preserved(tmp_path):
    repo = _make_repo(tmp_path)
    for kind in ("research_wishlist", "bug_seed", "project_evolution_seed", "lesson_candidate_seed"):
        record = external_queue_import.build_external_queue_item(
            repo_path=str(repo),
            source="manual",
            kind=kind,
            query=f"Query of kind {kind}",
        )
        assert record["kind"] == kind, f"kind {kind!r} was not preserved"


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

def test_marks_auto_patch_request_high_risk(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="discord",
        kind="bug_seed",
        query="Please auto patch the retrieval layer to fix this bug automatically",
    )
    assert record["risk_level"] == "high"
    combined = " ".join(record["risk_reasons"])
    assert "auto patch" in combined or "mutation" in combined or "apply" in combined


def test_marks_deploy_keyword_high_risk(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="n8n",
        kind="bug_seed",
        query="deploy this fix to production right away",
    )
    assert record["risk_level"] == "high"


def test_marks_project_evolution_seed_planning_only_medium(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="project_evolution_seed",
        query="Plan a migration from Flask to FastAPI for better async support",
        result="FastAPI has native async and better OpenAPI support",
    )
    assert record["risk_level"] in ("medium", "high")
    combined = " ".join(record["risk_reasons"])
    assert "project_evolution" in combined or "planning" in combined or "architecture" in combined


def test_marks_project_evolution_with_apply_high_risk(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="n8n",
        kind="project_evolution_seed",
        query="Migrate the repo from Flask to FastAPI and apply the patch automatically",
    )
    assert record["risk_level"] == "high"


def test_marks_narrow_research_low_risk(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="What are the differences between model2vec and sentence-transformers?",
        result="model2vec is static, sentence-transformers is contextual",
    )
    assert record["risk_level"] == "low"


def test_missing_result_increases_risk(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Short query",
    )
    assert record["risk_level"] in ("medium", "high")


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

def test_redacts_openai_style_key_in_query(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="discord",
        kind="research_wishlist",
        query="Use this key: sk-abc123xyz789defghi to call the API",
    )
    assert record["status"] == "ok"
    assert "sk-abc123" not in record["query"]
    assert "[REDACTED_SECRET]" in record["query"]
    assert any("possible secret" in r for r in record["risk_reasons"])


def test_redacts_password_assignment_in_result(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Test with credentials",
        result="Connect with password=supersecret123 to the database",
    )
    assert "supersecret123" not in record["result"]
    assert "[REDACTED_SECRET]" in record["result"]
    assert any("possible secret" in r for r in record["risk_reasons"])


def test_redacts_bearer_token(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="webhook",
        kind="bug_seed",
        query="Authenticate using Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9 in the header",
    )
    assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in record["query"]
    assert "[REDACTED_SECRET]" in record["query"]


def test_no_raw_secret_in_markdown_when_redacted(tmp_path):
    repo = _make_repo(tmp_path)
    secret = "sk-verysecretkey12345678"
    out = external_queue_import.write_external_queue_item_artifacts(
        repo_path=str(repo),
        source="discord",
        kind="research_wishlist",
        query=f"Please use {secret} to fetch embeddings",
    )
    md_text = Path(out["md_path"]).read_text(encoding="utf-8")
    assert secret not in md_text
    assert "[REDACTED_SECRET]" in md_text


# ---------------------------------------------------------------------------
# Result truncation
# ---------------------------------------------------------------------------

def test_result_is_truncated_at_limit(tmp_path):
    repo = _make_repo(tmp_path)
    long_result = "x" * 6000
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Short query",
        result=long_result,
    )
    assert record["status"] == "ok"
    assert len(record["result"]) < 6000
    assert "truncated" in record["result"]


def test_result_within_limit_is_not_truncated(tmp_path):
    repo = _make_repo(tmp_path)
    short_result = "x" * 100
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Short query",
        result=short_result,
    )
    assert record["result"] == short_result


# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------

def test_allowed_next_steps_do_not_include_auto_actions(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Test query",
    )
    allowed = record["allowed_next_steps"]
    assert "auto_dream" not in allowed
    assert "auto_patch" not in allowed
    assert "apply_patch" not in allowed
    assert "modify_real_repo" not in allowed
    assert "review_manually" in allowed
    assert "reject" in allowed


def test_forbidden_next_steps_include_auto_and_apply(tmp_path):
    repo = _make_repo(tmp_path)
    record = external_queue_import.build_external_queue_item(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Test query",
    )
    forbidden = record["forbidden_next_steps"]
    assert "auto_dream" in forbidden
    assert "auto_patch" in forbidden
    assert "apply_patch" in forbidden
    assert "modify_real_repo" in forbidden
    assert "promote_lesson_without_review" in forbidden
    assert "run_subagent_without_approval" in forbidden


# ---------------------------------------------------------------------------
# Output artifact containment
# ---------------------------------------------------------------------------

def test_output_stays_under_external_queue_directory(tmp_path):
    repo = _make_repo(tmp_path)
    out = external_queue_import.write_external_queue_item_artifacts(
        repo_path=str(repo),
        source="discord",
        kind="research_wishlist",
        query="Evaluate retrieval improvements",
    )
    queue_root = (repo / ".agent" / "external_queue").resolve()
    Path(out["json_path"]).resolve().relative_to(queue_root)
    Path(out["md_path"]).resolve().relative_to(queue_root)


def test_source_repo_files_not_modified(tmp_path):
    repo = _make_repo(tmp_path)
    source_file = repo / "core" / "main.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("def main(): pass\n", encoding="utf-8")
    original = source_file.read_text(encoding="utf-8")

    external_queue_import.write_external_queue_item_artifacts(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Does not touch source files",
    )

    assert source_file.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# input-json handling
# ---------------------------------------------------------------------------

def test_cli_input_json_error_on_missing_file(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    missing = tmp_path / "nonexistent.json"

    from scripts import import_external_queue_item as cli

    rc = cli.main(["--repo-path", str(repo), "--input-json", str(missing)])
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_cli_input_json_error_on_invalid_json(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ not valid json", encoding="utf-8")

    from scripts import import_external_queue_item as cli

    rc = cli.main(["--repo-path", str(repo), "--input-json", str(bad_json)])
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_cli_input_json_loads_item(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    item = {
        "source": "discord",
        "kind": "research_wishlist",
        "query": "What is the best retrieval strategy?",
        "result": "Hybrid search looks promising",
    }
    item_path = tmp_path / "item.json"
    item_path.write_text(json.dumps(item), encoding="utf-8")

    from scripts import import_external_queue_item as cli

    rc = cli.main(["--repo-path", str(repo), "--input-json", str(item_path)])
    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "queue_id:" in output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_writes_artifacts_under_external_queue(tmp_path, capsys):
    repo = _make_repo(tmp_path)

    from scripts import import_external_queue_item as cli

    rc = cli.main([
        "--repo-path", str(repo),
        "--source", "discord",
        "--kind", "research_wishlist",
        "--query", "Investigate embedding provider latency",
        "--result", "Gemini embeddings are faster in our tests",
    ])

    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "md_path:" in output
    assert "queue_id:" in output
    assert "risk_level:" in output
    assert "import_status:" in output
    assert "auto_dream_allowed:" in output
    assert "human_review_required:" in output
    assert (repo / ".agent" / "external_queue").exists()


def test_cli_rejects_empty_query(tmp_path, capsys):
    repo = _make_repo(tmp_path)

    from scripts import import_external_queue_item as cli

    rc = cli.main([
        "--repo-path", str(repo),
        "--source", "manual",
        "--kind", "research_wishlist",
        "--query", "",
    ])

    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def test_markdown_includes_guardrail_text(tmp_path):
    repo = _make_repo(tmp_path)
    out = external_queue_import.write_external_queue_item_artifacts(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Evaluate new retrieval methods",
    )
    md = Path(out["md_path"]).read_text(encoding="utf-8")
    assert "# External Queue Item" in md
    assert "This item is review-only." in md
    assert "It cannot trigger Dream automatically." in md
    assert "It cannot apply patches." in md
    assert "It cannot modify the real repository." in md
    assert "Human review is required before conversion into any stronger mode." in md


def test_markdown_has_all_required_sections(tmp_path):
    repo = _make_repo(tmp_path)
    out = external_queue_import.write_external_queue_item_artifacts(
        repo_path=str(repo),
        source="manual",
        kind="research_wishlist",
        query="Evaluate new retrieval methods",
    )
    md = Path(out["md_path"]).read_text(encoding="utf-8")
    for section in (
        "## Status",
        "## Source",
        "## Query",
        "## Result Summary",
        "## Risk",
        "## Allowed Next Steps",
        "## Forbidden Next Steps",
        "## Reviewer Checklist",
        "## Guardrails",
    ):
        assert section in md, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# Purity: no forbidden imports or calls
# ---------------------------------------------------------------------------

def test_no_forbidden_imports_or_calls():
    trees = [
        ast.parse(MODULE_PATH.read_text(encoding="utf-8")),
        ast.parse(SCRIPT_PATH.read_text(encoding="utf-8")),
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
        "n8n",
        "openai",
        "patching",
        "requests",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "validator",
        "web",
        "zalo",
    }
    forbidden_imports = {
        "core.control_engine",
        "core.debug_workflow",
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
    assert imported_roots.isdisjoint(forbidden_import_roots), (
        f"Forbidden import roots: {imported_roots & forbidden_import_roots}"
    )
    assert imports.isdisjoint(forbidden_imports), (
        f"Forbidden imports: {imports & forbidden_imports}"
    )
    assert calls.isdisjoint(forbidden_calls), (
        f"Forbidden calls: {calls & forbidden_calls}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
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
