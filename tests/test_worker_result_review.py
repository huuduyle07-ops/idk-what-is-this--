from __future__ import annotations

import ast
import importlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-worker-result-review"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _module():
    try:
        return importlib.import_module("core.worker_result_review")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"core.worker_result_review is missing: {exc}") from exc


def _cli_module():
    try:
        return importlib.import_module("scripts.import_worker_result_review")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"scripts.import_worker_result_review is missing: {exc}") from exc


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _worker_assignment(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "assignment_id": "wa-checkout",
        "created_at": "2026-01-01T00:00:00Z",
        "source_type": "goal_brief",
        "source_path": "/repo/.agent/goal_briefs/x/goal_brief.json",
        "title": "Fix checkout total regression",
        "mode": "Debug",
        "worker_role": "implementer",
        "repo_path": "/repo",
        "allowed_files": ["core/checkout.py"],
        "forbidden_files": [".env", ".agent", ".git"],
        "validation_commands": ["python -m pytest tests/test_checkout.py -q"],
        "human_approval_required": True,
        "apply_allowed": False,
        "worker_launch_allowed": False,
    }
    record.update(overrides)
    return record


def _driver_decision(**overrides: Any) -> dict[str, Any]:
    record = {
        "driver_decision_id": "driver-checkout",
        "source_type": "worker_assignment",
        "recommended_vehicle": "free_model_ok",
        "approval_required": False,
        "risk_flags": [],
    }
    record.update(overrides)
    return record


def _visual_contract(**overrides: Any) -> dict[str, Any]:
    record = {
        "visual_evidence_id": "visual-checkout",
        "source_type": "worker_assignment",
        "visual_evidence_referenced": True,
        "resolution_claim_allowed": False,
        "risk_flags": ["visual_evidence_unverified"],
    }
    record.update(overrides)
    return record


def _assignment_path(repo: Path) -> Path:
    return _write_json(
        repo / ".agent" / "worker_assignments" / "wa-checkout" / "worker_assignment.json",
        _worker_assignment(repo_path=str(repo)),
    )


def test_import_from_result_text_creates_json_and_markdown(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    result = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Worker says the checkout calculation is fixed. Human should review it.",
        review_id="text-review",
        created_at="2026-01-01T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["status"] == "review_created"
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path == repo / ".agent" / "worker_result_reviews" / "text-review" / "worker_result_review.json"
    assert md_path == json_path.with_name("worker_result_review.md")
    assert json_path.is_file()
    assert md_path.is_file()

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record["review_id"] == "text-review"
    assert record["created_at"] == "2026-01-01T00:00:00Z"
    assert record["source_type"] == "worker_result_review"
    assert record["worker_assignment_path"] == str(assignment.resolve())
    assert record["worker_result_source"] == "manual_paste"
    assert record["worker_result_path"] == ""
    assert "checkout calculation is fixed" in record["worker_result_excerpt"]
    assert record["review_status"] == "pending_review"
    assert record["trust_level"] == "untrusted"
    assert record["human_review_required"] is True
    assert record["eligible_for_proposal_import"] is False
    assert record["eligible_for_teaching_card"] is True
    assert "worker_result_untrusted" in record["risk_flags"]
    assert "external_worker_output" in record["risk_flags"]


def test_import_from_result_file_creates_json_and_markdown(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)
    result_file = _write_text(
        repo / ".agent" / "worker_outputs" / "worker.md",
        "Changed files: core/checkout.py\nRan pytest and tests passed.",
    )

    result = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_file_path=str(result_file),
        review_id="file-review",
        created_at="2026-01-01T00:00:00Z",
    )

    record = result["record"]
    assert result["ok"] is True
    assert record["worker_result_source"] == "file"
    assert record["worker_result_path"] == str(result_file.resolve())
    assert "core/checkout.py" in record["claimed_changed_files"]
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


def test_missing_worker_assignment_returns_clean_error(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)

    result = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(repo / ".agent" / "missing.json"),
        result_text="Worker result",
    )

    assert result["ok"] is False
    assert result["status"] == "not_found"
    assert result["error"]["code"] == "worker_assignment_not_found"
    assert not (repo / ".agent" / "worker_result_reviews").exists()


def test_missing_result_returns_clean_error(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    result = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
    )

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error"]["code"] == "missing_result_text"
    assert not (repo / ".agent" / "worker_result_reviews").exists()


def test_result_text_and_file_together_are_ambiguous(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)
    result_file = _write_text(repo / "worker.md", "Changed files: core/checkout.py")

    result = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Changed files: core/other.py",
        result_file_path=str(result_file),
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "ambiguous_result_input"
    assert not (repo / ".agent" / "worker_result_reviews").exists()


def test_dry_run_writes_nothing(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    result = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Changed files: core/checkout.py",
        dry_run=True,
        review_id="dry-run-review",
        created_at="2026-01-01T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert not (repo / ".agent" / "worker_result_reviews").exists()


def test_deterministic_hooks_work(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)
    kwargs = {
        "repo_path": str(repo),
        "worker_assignment_path": str(assignment),
        "result_text": "Changed files: core/checkout.py",
        "dry_run": True,
        "review_id": "stable-review",
        "created_at": "2026-01-01T00:00:00Z",
    }

    first = mod.render_worker_result_review_json(mod.create_worker_result_review(**kwargs))
    second = mod.render_worker_result_review_json(mod.create_worker_result_review(**kwargs))

    assert first == second
    assert json.loads(first)["record"]["review_id"] == "stable-review"


def test_no_overwrite_by_default(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    first = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Changed files: core/checkout.py",
        review_id="same-review",
        created_at="2026-01-01T00:00:00Z",
    )
    json_path = Path(first["json_path"])
    changed = json_path.read_text(encoding="utf-8") + "\n"
    json_path.write_text(changed, encoding="utf-8")

    second = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Changed files: core/checkout.py",
        review_id="same-review",
        created_at="2026-01-01T00:00:00Z",
    )

    assert second["ok"] is False
    assert second["status"] == "already_exists"
    assert json_path.read_text(encoding="utf-8") == changed


def test_changed_files_are_extracted_as_claims(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text=(
            "Changed files:\n"
            "- core/checkout.py\n"
            "- tests/test_checkout.py\n"
            "Also reviewed README.md."
        ),
        dry_run=True,
    )["record"]

    assert record["claimed_changed_files"] == [
        "core/checkout.py",
        "tests/test_checkout.py",
        "README.md",
    ]
    assert "patch_claim_unverified" in record["risk_flags"]
    assert record["eligible_for_proposal_import"] is True


def test_validation_command_and_tests_passed_claim_are_unverified(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text=(
            "Changed files: core/checkout.py\n"
            "Ran python -m pytest tests/test_checkout.py -q and tests passed."
        ),
        dry_run=True,
    )["record"]

    assert record["claimed_validation_commands"] == [
        "python -m pytest tests/test_checkout.py -q"
    ]
    assert record["claimed_validation_passed"] is True
    assert "validation_claim_unverified" in record["risk_flags"]
    assert "Run validation yourself before trusting this result." in record["recommended_next_actions"]


def test_validation_failed_claim_is_recorded(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Ran npm test and validation failed on checkout assertions.",
        dry_run=True,
    )["record"]

    assert "npm test" in record["claimed_validation_commands"]
    assert record["claimed_validation_passed"] is False
    assert "Review failure before promotion/import." in record["recommended_next_actions"]


def test_visual_claim_without_visual_contract_adds_missing_requirement(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Changed files: web/app.py\nThe screenshot and UI layout now look fixed.",
        dry_run=True,
    )["record"]

    assert "visual_claim_requires_visual_contract" in record["risk_flags"]
    assert "visual_evidence_contract" in record["missing_requirements"]
    assert (
        "Create or attach A.16 Visual Evidence Contract before claiming visual result is fixed."
        in record["recommended_next_actions"]
    )


def test_visual_claim_with_visual_contract_links_it(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)
    visual = _write_json(
        repo / ".agent" / "visual_evidence" / "visual-checkout" / "visual_evidence_contract.json",
        _visual_contract(),
    )

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        visual_evidence_contract_path=str(visual),
        result_text="Changed files: web/app.py\nThe screenshot and UI layout now look fixed.",
        dry_run=True,
    )["record"]

    assert record["visual_evidence_contract_path"] == str(visual.resolve())
    assert "visual_claim_requires_visual_contract" in record["risk_flags"]
    assert "visual_evidence_contract" not in record["missing_requirements"]


def test_security_sensitive_claim_adds_warning(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Changed files: core/auth.py\nUpdated API key token handling and .env secret loading.",
        dry_run=True,
    )["record"]

    assert "security_sensitive_claim" in record["risk_flags"]
    assert (
        "Manually review security-sensitive changes before importing as a proposal."
        in record["recommended_next_actions"]
    )


def test_large_result_is_truncated_and_flagged(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)
    large = "Changed files: core/checkout.py\n" + ("A" * 5000)

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text=large,
        dry_run=True,
    )["record"]

    assert len(record["worker_result_excerpt"]) == 4000
    assert "large_result_truncated" in record["risk_flags"]


def test_json_includes_all_inert_flags(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Changed files: core/checkout.py",
        dry_run=True,
    )["record"]

    expected = {
        "model_call_performed": False,
        "worker_launch_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "proposal_imported": False,
        "lesson_promotion_performed": False,
        "teaching_card_created": False,
        "dream_triggered": False,
        "project_evolution_triggered": False,
        "webhook_called": False,
    }
    for key, expected_value in expected.items():
        assert record[key] is expected_value, key


def test_markdown_includes_required_sections_and_execution_boundary(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    markdown = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Changed files: core/checkout.py\nTests passed.",
        dry_run=True,
    )["markdown"]

    for heading in [
        "# Worker Result Review Stub",
        "## Source Assignment",
        "## Linked Driver / Visual Evidence",
        "## Worker Result Excerpt",
        "## Claimed Changed Files",
        "## Claimed Validation",
        "## Risk Flags",
        "## Missing Requirements",
        "## Recommended Next Actions",
        "## Review Status",
        "## Execution Boundary",
    ]:
        assert heading in markdown, heading
    lowered = markdown.lower()
    assert "no model was called" in lowered
    assert "no worker was launched" in lowered
    assert "no patch was applied" in lowered
    assert "no validation was run" in lowered
    assert "no proposal was imported" in lowered
    assert "no lesson was promoted" in lowered
    assert "no teaching card was created" in lowered
    assert "dream / project evolution" in lowered
    assert "no webhook/network call occurred" in lowered


def test_eligibility_defaults_stay_conservative(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    record = mod.create_worker_result_review(
        repo_path=str(repo),
        worker_assignment_path=str(assignment),
        result_text="Worker says they reviewed the issue but did not list files.",
        dry_run=True,
    )["record"]

    assert record["eligible_for_proposal_import"] is False
    assert record["eligible_for_teaching_card"] is True
    assert record["trust_level"] == "untrusted"


def test_cli_creates_json_and_markdown(capsys: Any, tmp_path: Path):
    cli = _cli_module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)
    result_file = _write_text(repo / "worker.md", "Changed files: core/checkout.py")

    rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--worker-assignment",
            str(assignment),
            "--result-file",
            str(result_file),
            "--review-id",
            "cli-review",
            "--created-at",
            "2026-01-01T00:00:00Z",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    assert parsed["status"] == "review_created"
    assert parsed["record"]["review_id"] == "cli-review"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()


def test_cli_result_text_dry_run_writes_nothing(capsys: Any, tmp_path: Path):
    cli = _cli_module()
    repo = _repo(tmp_path)
    assignment = _assignment_path(repo)

    rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--worker-assignment",
            str(assignment),
            "--result-text",
            "Changed files: core/checkout.py",
            "--dry-run",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert rc == 0
    assert json.loads(output)["status"] == "dry_run"
    assert not (repo / ".agent" / "worker_result_reviews").exists()


def test_cli_missing_source_errors_are_clean(capsys: Any, tmp_path: Path):
    cli = _cli_module()
    repo = _repo(tmp_path)

    missing_assignment_rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--worker-assignment",
            str(repo / "missing.json"),
            "--result-text",
            "result",
        ]
    )
    missing_assignment_err = capsys.readouterr().err
    assert missing_assignment_rc == 1
    assert "worker_assignment_not_found" in missing_assignment_err

    assignment = _assignment_path(repo)
    missing_result_rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--worker-assignment",
            str(assignment),
        ]
    )
    missing_result_err = capsys.readouterr().err
    assert missing_result_rc == 1
    assert "missing_result_text" in missing_result_err


def test_no_forbidden_imports_or_calls_in_worker_result_review_layers():
    mod = _module()
    cli = _cli_module()
    module_tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
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
        "core.lesson_teaching_card",
        "core.project_evolution_mode",
        "core.run_lifecycle",
        "core.sleeping_consultant",
        "core.validator",
        "core.worker_runs",
        "scripts.create_lesson_teaching_card",
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
        "create_teaching_card",
        "execute",
        "executemany",
        "generate_content",
        "get_embedding",
        "import_proposal",
        "open",
        "promote_lesson",
        "promote",
        "Popen",
        "post",
        "run",
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
