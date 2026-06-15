"""B.16 External Queue Detail/View tests."""
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
MODULE_PATH = PROJECT_ROOT / "core" / "external_queue_index.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "show_external_queue_item.py"


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-external-queue-detail"
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
        "discord_channel": "research-output",
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
    "recommendation": "convert_to_dream_candidate",
    "recommendation_confidence": "medium",
    "recommendation_reasons": ["narrow research item with concrete result"],
    "missing_evidence": ["confirm current provider pricing"],
    "suggested_next_prompt": "Create a Dream candidate after human approval.",
    "allowed_next_steps": ["review_manually", "reject"],
    "forbidden_next_steps": ["auto_dream", "auto_patch", "apply_patch"],
    "human_approval_required": True,
    "action_performed": False,
    "guardrails": ["No conversion was performed."],
}


def test_existing_valid_item_loads_by_queue_id(tmp_path):
    from core.external_queue_index import load_external_queue_item_detail

    repo, item_path, queue_id = _seed_queue_item(tmp_path)

    detail = load_external_queue_item_detail(str(repo), queue_id)

    assert detail["found"] is True
    assert detail["status"] == "queued"
    assert detail["identity"]["queue_id"] == queue_id
    assert detail["identity"]["item_path"] == str(item_path)
    assert detail["identity"]["review_path"] == ""
    assert detail["identity"]["source_kind"] == "manual"
    assert detail["identity"]["source_label"] == "manual"
    assert detail["identity"]["source_channel"] == "research-output"
    assert detail["content_summary"]["title"] == "Embedding provider research"
    assert detail["content_summary"]["summary"] == "Compare local and remote embedding providers."
    assert detail["content_summary"]["source_url"] == "https://discord.com/channels/123/456"
    assert detail["content_summary"]["tags"] == ["embeddings", "retrieval"]
    assert detail["gate_status"]["human_review_required"] is True
    assert detail["gate_status"]["auto_dream_allowed"] is False
    assert detail["gate_status"]["action_performed"] is False
    assert detail["gate_status"]["recommendation"] == ""
    assert detail["risk_safety"]["risk_level"] == "low"
    assert detail["risk_safety"]["safe_to_display"] is True
    assert detail["review_details"]["present"] is False
    assert "raw" not in detail


def test_missing_queue_id_returns_clean_not_found_and_cli_nonzero(tmp_path, capsys):
    from core.external_queue_index import load_external_queue_item_detail
    from scripts import show_external_queue_item as cli

    repo = _make_repo(tmp_path)

    detail = load_external_queue_item_detail(str(repo), "missing-id")

    assert detail["found"] is False
    assert detail["status"] == "not_found"
    assert detail["error"]["code"] == "queue_id_not_found"

    rc = cli.main(["--repo-path", str(repo), "--queue-id", "missing-id"])
    captured = capsys.readouterr()

    assert rc == 1
    assert "not found" in captured.err.lower()
    assert "missing-id" in captured.err


def test_invalid_item_json_returns_invalid_detail_not_crash(tmp_path):
    from core.external_queue_index import load_external_queue_item_detail

    repo = _make_repo(tmp_path)
    item_path = repo / ".agent" / "external_queue" / "bad-item" / "external_queue_item.json"
    item_path.parent.mkdir(parents=True)
    item_path.write_text("{ not valid json", encoding="utf-8")

    detail = load_external_queue_item_detail(str(repo), "bad-item")

    assert detail["found"] is True
    assert detail["status"] == "invalid"
    assert detail["identity"]["queue_id"] == "bad-item"
    assert detail["identity"]["item_path"] == str(item_path)
    assert detail["risk_safety"]["safe_to_display"] is False
    assert "valid JSON" in detail["risk_safety"]["validation_error_summary"]


def test_missing_optional_fields_are_tolerated(tmp_path):
    from core.external_queue_index import load_external_queue_item_detail

    repo, _item_path, queue_id = _seed_queue_item(
        tmp_path,
        result=None,
        source_url=None,
        metadata=None,
        risk_reasons=None,
        title=None,
        summary=None,
    )

    detail = load_external_queue_item_detail(str(repo), queue_id)

    assert detail["found"] is True
    assert detail["status"] == "queued"
    assert detail["content_summary"]["summary"] == ""
    assert detail["content_summary"]["source_url"] == ""
    assert detail["content_summary"]["tags"] == []
    assert detail["content_summary"]["categories"] == []
    assert detail["risk_safety"]["risk_reasons"] == []


def test_review_json_is_included_when_present(tmp_path):
    from core.external_queue_index import load_external_queue_item_detail

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    review_path = _seed_review(item_path.parent)

    detail = load_external_queue_item_detail(str(repo), queue_id)

    assert detail["status"] == "reviewed"
    assert detail["identity"]["review_path"] == str(review_path)
    assert detail["gate_status"]["review_status"] == "ok"
    assert detail["gate_status"]["recommendation"] == "convert_to_dream_candidate"
    assert detail["gate_status"]["action_performed"] is False
    assert detail["review_details"]["present"] is True
    assert detail["review_details"]["valid"] is True
    assert detail["review_details"]["recommendation"] == "convert_to_dream_candidate"
    assert detail["review_details"]["reason"] == "narrow research item with concrete result"
    assert detail["review_details"]["evidence_summary"]["reasons"] == [
        "narrow research item with concrete result"
    ]
    assert detail["review_details"]["human_approval_required"] is True
    assert detail["review_details"]["action_performed"] is False
    assert detail["review_details"]["created_at"] == "2026-01-02T00:00:00Z"


def test_invalid_review_json_is_reported_not_crash(tmp_path):
    from core.external_queue_index import load_external_queue_item_detail

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    review_path = item_path.parent / "external_queue_review.json"
    review_path.write_text("{ not valid json", encoding="utf-8")

    detail = load_external_queue_item_detail(str(repo), queue_id)

    assert detail["status"] == "queued"
    assert detail["gate_status"]["review_status"] == "invalid"
    assert detail["review_details"]["present"] is True
    assert detail["review_details"]["valid"] is False
    assert detail["review_details"]["path"] == str(review_path)
    assert "valid JSON" in detail["review_details"]["error"]
    assert "valid JSON" in detail["risk_safety"]["validation_error_summary"]


def test_missing_linked_paths_are_reported(tmp_path):
    from core.external_queue_index import load_external_queue_item_detail

    repo, _item_path, queue_id = _seed_queue_item(
        tmp_path,
        proposal_path=".agent/proposals/missing-proposal.json",
        linked_report_path=".agent/reports/missing-report.md",
    )

    detail = load_external_queue_item_detail(str(repo), queue_id)

    missing = detail["risk_safety"]["invalid_or_missing_linked_paths"]
    assert "proposal_path=.agent/proposals/missing-proposal.json" in missing
    assert "linked_report_path=.agent/reports/missing-report.md" in missing
    linked = {entry["label"]: entry for entry in detail["linked_artifacts"]}
    assert linked["proposal_path"]["exists"] is False
    assert linked["linked_report_path"]["exists"] is False


def test_redaction_and_secret_warnings_are_displayed(tmp_path, capsys):
    from core.external_queue_index import load_external_queue_item_detail
    from scripts import show_external_queue_item as cli

    repo, _item_path, queue_id = _seed_queue_item(
        tmp_path,
        risk_level="high",
        risk_reasons=[
            "possible secret detected: api_key_sk",
            "sensitive field warning: metadata.token",
            "redaction applied to result",
        ],
    )

    detail = load_external_queue_item_detail(str(repo), queue_id)

    assert "possible secret detected: api_key_sk" in detail["risk_safety"]["secret_warnings"]
    assert "sensitive field warning: metadata.token" in detail["risk_safety"]["sensitive_field_warnings"]
    assert "redaction applied to result" in detail["risk_safety"]["redaction_warnings"]
    assert detail["risk_safety"]["safe_to_display"] is False

    rc = cli.main([
        "--repo-path",
        str(repo),
        "--queue-id",
        queue_id,
        "--show-redaction-warnings",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    assert "possible secret detected: api_key_sk" in output
    assert "sensitive field warning: metadata.token" in output
    assert "redaction applied to result" in output


def test_default_cli_output_includes_title_status_and_recommendation(tmp_path, capsys):
    from scripts import show_external_queue_item as cli

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent)

    rc = cli.main(["--repo-path", str(repo), "--queue-id", queue_id])
    output = capsys.readouterr().out

    assert rc == 0
    assert "Embedding provider research" in output
    assert "Status: reviewed" in output
    assert "Recommendation: convert_to_dream_candidate" in output
    assert "Action performed: False" in output


def test_json_output_is_valid_deterministic_and_can_include_raw(tmp_path, capsys):
    from scripts import show_external_queue_item as cli

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent)

    rc = cli.main(["--repo-path", str(repo), "--queue-id", queue_id, "--json"])
    first = capsys.readouterr().out
    rc2 = cli.main(["--repo-path", str(repo), "--queue-id", queue_id, "--json"])
    second = capsys.readouterr().out

    assert rc == 0
    assert rc2 == 0
    assert first == second
    assert first.endswith("\n")
    parsed = json.loads(first)
    assert parsed["identity"]["queue_id"] == queue_id
    assert parsed["review_details"]["recommendation"] == "convert_to_dream_candidate"
    assert "raw" not in parsed

    rc = cli.main([
        "--repo-path",
        str(repo),
        "--queue-id",
        queue_id,
        "--json",
        "--include-raw",
    ])
    raw_output = capsys.readouterr().out

    assert rc == 0
    assert json.loads(raw_output)["raw"]["item"]["queue_id"] == queue_id


def test_show_review_includes_review_details(tmp_path, capsys):
    from scripts import show_external_queue_item as cli

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    _seed_review(item_path.parent)

    rc = cli.main(["--repo-path", str(repo), "--queue-id", queue_id, "--show-review"])
    output = capsys.readouterr().out

    assert rc == 0
    assert "Review Details" in output
    assert "narrow research item with concrete result" in output
    assert "confirm current provider pricing" in output
    assert "Create a Dream candidate after human approval." in output


def test_cli_does_not_mutate_queue_files(tmp_path, capsys):
    from scripts import show_external_queue_item as cli

    repo, item_path, queue_id = _seed_queue_item(tmp_path)
    review_path = _seed_review(item_path.parent)
    before = _snapshot_files(repo / ".agent" / "external_queue")

    rc = cli.main([
        "--repo-path",
        str(repo),
        "--queue-id",
        queue_id,
        "--json",
        "--show-review",
        "--show-linked",
    ])
    _ = capsys.readouterr()

    assert rc == 0
    assert _snapshot_files(repo / ".agent" / "external_queue") == before
    assert item_path.exists()
    assert review_path.exists()


def test_duplicate_queue_id_is_reported_as_ambiguous(tmp_path, capsys):
    from core.external_queue_index import load_external_queue_item_detail
    from scripts import show_external_queue_item as cli

    repo, _item_path, _ = _seed_queue_item(tmp_path, queue_id="duplicate-id")
    _seed_second_item(repo, queue_id="duplicate-id", directory="other-artifact")

    detail = load_external_queue_item_detail(str(repo), "duplicate-id")

    assert detail["found"] is False
    assert detail["status"] == "ambiguous"
    assert detail["error"]["code"] == "queue_id_ambiguous"
    assert len(detail["matches"]) == 2

    rc = cli.main(["--repo-path", str(repo), "--queue-id", "duplicate-id"])
    captured = capsys.readouterr()

    assert rc == 1
    assert "ambiguous" in captured.err.lower()


def test_readme_external_queue_detail_examples_use_supported_cli_flags():
    from scripts import show_external_queue_item as cli

    section = _markdown_section(
        README_PATH.read_text(encoding="utf-8"),
        "#### View one queue item",
        "#### Manual CLI import",
    )
    commands = [
        line.strip()
        for line in section.splitlines()
        if line.strip().startswith("python scripts/show_external_queue_item.py")
    ]

    assert len(commands) >= 2
    assert any("--json" in command for command in commands)

    parser = cli.build_parser()
    for command in commands:
        argv = shlex.split(command)[2:]
        parser.parse_args(argv)


def test_no_forbidden_imports_or_calls_in_detail_layer():
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
        "write_text",
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


def _snapshot_files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


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
