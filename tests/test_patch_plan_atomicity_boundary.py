from __future__ import annotations

import ast
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _replace_plan(relative_path: str) -> list[dict]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": relative_path,
            "target_snippet": "VALUE = 1\n",
            "patched_snippet": "VALUE = 2\n",
        }
    ]


def _write_validation_script(repo: Path, *, exit_code: int = 1) -> Path:
    script = repo / "scripts" / "validation_side_effect.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "from pathlib import Path\n"
        "Path('validation_created.txt').write_text('created by validation\\n', encoding='utf-8')\n"
        f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    return script


def _safe_command(repo: Path, script: Path):
    from core.validation_execution import SafeValidationCommand

    return SafeValidationCommand(
        command=["python", str(script.relative_to(repo))],
        cwd=repo,
        timeout_sec=20,
    )


def test_patch_plan_result_reports_patch_ops_only_atomicity_scope(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")

    result = apply_patch_plan(str(repo), _replace_plan("src/app.py"))

    assert result["success"] is True
    assert result["atomicity_scope"] == "patch_ops_only"
    assert result["patch_ops_rollback_protected"] is True
    assert result["validation_side_effects_in_rollback_scope"] is False
    assert result["validation_side_effect_policy"] == "reported_not_rolled_back"
    assert result["sandbox_validation_recommended"] is True


def test_validation_failure_rolls_back_patch_ops_but_reports_side_effect_boundary(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    script = _write_validation_script(repo, exit_code=1)

    result = apply_patch_plan(
        str(repo),
        _replace_plan("src/app.py"),
        safe_validation_command=_safe_command(repo, script),
    )

    assert result["success"] is False
    assert result["rollback_performed"] is True
    assert target.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (repo / "validation_created.txt").read_text(encoding="utf-8") == (
        "created by validation\n"
    )
    assert result["validation_side_effects_in_rollback_scope"] is False
    assert "Patch operations rolled back" in result["message"]
    assert "Validation side effects are outside patch rollback scope" in result["message"]
    assert "fully rolled back" not in result["message"].lower()


def test_validation_created_file_is_detected_and_marked_outside_patch_scope(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    script = _write_validation_script(repo, exit_code=1)

    result = apply_patch_plan(
        str(repo),
        _replace_plan("src/app.py"),
        safe_validation_command=_safe_command(repo, script),
    )

    side_effects = result["validation_side_effects"]
    assert side_effects["supported"] is True
    assert side_effects["created"] == [
        {
            "path": "validation_created.txt",
            "inside_patch_touched_scope": False,
            "known_generated_or_noisy": False,
        }
    ]
    assert side_effects["summary"] == {"created": 1, "modified": 0, "deleted": 0}


def test_safe_validation_still_passes_with_atomicity_metadata(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    script = _write_validation_script(repo, exit_code=0)

    result = apply_patch_plan(
        str(repo),
        _replace_plan("src/app.py"),
        safe_validation_command=_safe_command(repo, script),
    )

    assert result["success"] is True
    assert result["validation_mode"] == "safe_argv"
    assert result["atomicity_scope"] == "patch_ops_only"
    assert result["validation_side_effects"]["created"][0]["path"] == (
        "validation_created.txt"
    )


def test_require_safe_validation_rejects_legacy_shell_before_patch_ops(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "created.py"

    result = apply_patch_plan(
        str(repo),
        [{"op": "create_file", "relative_path": "created.py", "content": "x = 1\n"}],
        validation_command="pytest -q",
        require_safe_validation=True,
    )

    assert result["success"] is False
    assert result["unsafe_validation_blocked"] is True
    assert result["atomicity_scope"] == "patch_ops_only"
    assert not target.exists()


def test_lifecycle_replay_result_includes_atomicity_and_side_effect_metadata(
    monkeypatch, tmp_path
):
    import core.run_artifacts as run_artifacts
    import core.run_lifecycle as run_lifecycle

    monkeypatch.setattr(
        run_artifacts,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo_path: {"brain_stamp_id": "a19", "schema_version": 2},
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    script = _write_validation_script(repo, exit_code=1)

    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo),
        _replace_plan("src/app.py"),
        safe_validation_command=_safe_command(repo, script),
        source="unit",
    )

    assert result["success"] is False
    assert result["atomicity_scope"] == "patch_ops_only"
    assert result["validation_side_effects"]["created"][0]["path"] == (
        "validation_created.txt"
    )
    replay_result = Path(result["replay_dir"]) / "apply_result.json"
    assert "validation_side_effects" in replay_result.read_text(encoding="utf-8")


def test_executor_result_exposes_same_atomicity_boundary(tmp_path):
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("def value():\n    return 1\n", encoding="utf-8")
    script = _write_validation_script(repo, exit_code=1)
    patch = {
        "file": "src/app.py",
        "relative_path": "src/app.py",
        "target_snippet": "def value():\n    return 1\n",
        "patched_snippet": "def value():\n    return 2\n",
        "target_node_name": "value",
        "target_node_kind": "function",
    }

    result = Executor(str(repo)).run(
        patch,
        language="python",
        safe_validation_command=_safe_command(repo, script),
    )

    assert result.success is False
    assert result.rollback_performed is True
    assert result.atomicity_scope == "patch_ops_only"
    assert result.validation_side_effects_in_rollback_scope is False
    assert result.validation_side_effects["created"][0]["path"] == (
        "validation_created.txt"
    )


def test_patch_plan_source_no_longer_claims_whole_repo_atomicity():
    source = (PROJECT_ROOT / "patching" / "patch_plan_executor.py").read_text(
        encoding="utf-8"
    )

    assert "ALL prior ops are rolled back" not in source
    assert "repo is left exactly as it was found" not in source.lower()


def test_docs_mention_sandbox_validation_for_automation_paths():
    docs = (
        (PROJECT_ROOT / "docs" / "VALIDATION_EXECUTION_SAFETY.md").read_text(
            encoding="utf-8"
        )
        + "\n"
        + (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    ).lower()

    assert "safe validation execution" in docs
    assert "patch-plan atomicity" in docs
    assert "sandbox validation" in docs
    assert "validation side effects are outside patch rollback scope" in docs


def test_a19_guardrail_no_forbidden_execution_imports_or_calls():
    guarded_files = [
        PROJECT_ROOT / "patching" / "patch_plan_executor.py",
        PROJECT_ROOT / "core" / "executor.py",
        PROJECT_ROOT / "core" / "run_lifecycle.py",
        PROJECT_ROOT / "core" / "validation_side_effects.py",
        Path(__file__).resolve(),
    ]
    imports: set[str] = set()
    calls: set[str] = set()
    for path in guarded_files:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports |= _imported_modules(tree)
        calls |= _called_names(tree)

    imported_roots = {name.split(".", 1)[0] for name in imports}
    forbidden_import_roots = {
        "agents",
        "benchmarks",
        "database",
        "docker",
        "google",
        "openai",
        "requests",
        "httpx",
        "socket",
    }
    forbidden_calls = {
        "ChatCompletion",
        "generate_content",
        "run_gemini",
        "run_ollama",
        "build_control_prompt",
        "run_benchmark",
        "run_benchmarks",
        "launch_worker",
        "trigger_dream",
        "run_project_evolution",
        "promote_lesson",
        "import_proposal",
        "create_pull_request",
        "merge",
        "auto_merge",
        "execute",
        "executemany",
        "Popen",
        "check_call",
        "check_output",
        "system",
    }

    assert imported_roots.isdisjoint(forbidden_import_roots)
    assert forbidden_calls.isdisjoint(calls)


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
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
