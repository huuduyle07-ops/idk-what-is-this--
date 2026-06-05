from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from core import invariant_verification as invariants
from scripts import create_invariant_verification_report as report_cli


REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_SOURCE = REPO_ROOT / "core" / "invariant_verification.py"
CLI_SOURCE = REPO_ROOT / "scripts" / "create_invariant_verification_report.py"
SENSITIVE_SOURCE_PATHS = (
    REPO_ROOT / "core" / "control_engine.py",
    REPO_ROOT / "core" / "prompter.py",
    REPO_ROOT / "core" / "lesson_retrieval.py",
    REPO_ROOT / "core" / "anti_lesson_control_injection.py",
)

FORBIDDEN_IMPORT_ROOTS = {
    "agents",
    "aiohttp",
    "anthropic",
    "benchmarks",
    "database",
    "docker",
    "google",
    "httpx",
    "openai",
    "patching",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
FORBIDDEN_IMPORTS = {
    "benchmarks.run_benchmarks",
    "core.anti_lesson_control_injection",
    "core.anti_lesson_retrieval_shadow",
    "core.anti_lessons",
    "core.control_engine",
    "core.dream_artifacts",
    "core.dream_references",
    "core.dream_trials",
    "core.lesson_retrieval",
    "core.lesson_store",
    "core.mutation_oracle",
    "core.prompter",
    "core.proposal_runner",
    "core.run_lifecycle",
    "core.sleeping_consultant",
    "patching.patch_plan_executor",
}
FORBIDDEN_CALLS = {
    "apply_patch",
    "apply_patch_plan",
    "archive_lesson",
    "block_lesson",
    "build_control_prompt",
    "build_deepseek_review",
    "build_prompt",
    "call_api",
    "call_model",
    "check_call",
    "check_output",
    "ChatCompletion",
    "create_manual_anti_lesson",
    "create_merge",
    "create_mutation_oracle",
    "generate_content",
    "generate_patch",
    "patch_lesson_fields",
    "Popen",
    "promote_lesson",
    "run_benchmark",
    "run_benchmarks",
    "run_deepseek",
    "run_dream",
    "run_gemini",
    "run_gemini_request_2",
    "run_mutation_oracle",
    "run_ollama",
    "run_patch_plan_with_artifacts",
    "run_reverse_dream",
    "save_candidate_lesson",
    "save_raw_lesson_record",
    "system",
}


def _record(**overrides):
    record = {
        "source_ref": "benchmark_report_20260605.json:ts_wrong_file_honeypot",
        "code_invariant": "normalizeStatus(' shipped ') returns 'shipped' before displayStatus is called.",
        "plain_english_invariant": (
            "Orders with extra spaces around a valid status should still display as shipped."
        ),
        "changed_files": ["normalizer.ts"],
        "patched_files": ["normalizer.ts"],
        "validation_command": "node --experimental-strip-types main.ts",
        "validation_ok": True,
        "validation_output": "OK\nall status display checks passed\n",
        "patch_summary": "Trim and lowercase status before display.",
    }
    record.update(overrides)
    return record


def _tmp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".agent" / "experiments").mkdir(parents=True)
    return repo


def _parse_source(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


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
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def _module_references(tree: ast.AST, module_name: str) -> set[str]:
    references: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[-1] == module_name:
                    references.add(alias.name)
                if alias.asname == module_name:
                    references.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[-1] == module_name:
                references.add(node.module)
            for alias in node.names:
                if alias.name == module_name:
                    references.add(alias.name)
                if alias.asname == module_name:
                    references.add(alias.asname)
        elif isinstance(node, ast.Name) and node.id == module_name:
            references.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr == module_name:
            references.add(node.attr)
    return references


def test_explicit_invariants_with_successful_validation_are_supported():
    report = invariants.build_invariant_verification(
        _record(),
        generated_at="2026-06-05T00:00:00+00:00",
    )

    assert report["title"] == "Patch Invariant Verification"
    assert report["generated_at"] == "2026-06-05T00:00:00+00:00"
    assert report["source_ref"] == "benchmark_report_20260605.json:ts_wrong_file_honeypot"
    assert report["code_invariant"].startswith("normalizeStatus")
    assert report["plain_english_invariant"].startswith("Orders with extra spaces")
    assert report["evidence"]["changed_files"] == ["normalizer.ts"]
    assert report["evidence"]["patched_files"] == ["normalizer.ts"]
    assert report["evidence"]["validation_ok"] is True
    assert "all status display" in report["evidence"]["validation_output_excerpt"]
    assert report["verdict"] == "supported"
    assert "validation succeeded" in " ".join(report["reasons"])
    assert invariants.GUARDRAIL_NOTE == report["guardrail"]


def test_nested_invariant_fields_are_accepted():
    report = invariants.build_invariant_verification(
        _record(
            code_invariant=None,
            plain_english_invariant=None,
            invariants={
                "code": "BuildInvite trims request.Email before validation stores it.",
                "plain_english": "Invite emails with accidental spaces should still work.",
            },
        )
    )

    assert report["code_invariant"] == "BuildInvite trims request.Email before validation stores it."
    assert report["plain_english_invariant"] == (
        "Invite emails with accidental spaces should still work."
    )
    assert report["verdict"] == "supported"


def test_validation_failure_is_unsupported():
    report = invariants.build_invariant_verification(
        _record(validation_ok=False, validation_output="FAIL: still displays pending\n")
    )

    assert report["verdict"] == "unsupported"
    assert any("validation failed" in reason for reason in report["reasons"])


def test_missing_explicit_invariants_is_unknown():
    report = invariants.build_invariant_verification(
        _record(code_invariant="", plain_english_invariant="")
    )

    assert report["code_invariant"] == "unknown"
    assert report["plain_english_invariant"] == "unknown"
    assert report["verdict"] == "unknown"
    assert report["reasons"] == ["No explicit invariant was provided."]


def test_missing_validation_output_degrades_to_weakly_supported():
    report = invariants.build_invariant_verification(_record(validation_output=""))

    assert report["verdict"] == "weakly_supported"
    assert any("validation output is missing" in reason for reason in report["reasons"])


def test_missing_validation_status_is_unknown():
    report = invariants.build_invariant_verification(_record(validation_ok=None))

    assert report["verdict"] == "unknown"
    assert any("validation status is unknown" in reason for reason in report["reasons"])


def test_forbidden_files_or_unexpected_mutations_are_unsupported_with_warnings():
    report = invariants.build_invariant_verification(
        _record(
            touched_forbidden_files=["tests/test_display.ts"],
            unexpected_mutations=["main.ts"],
        )
    )

    assert report["verdict"] == "unsupported"
    assert report["evidence"]["touched_forbidden_files"] == ["tests/test_display.ts"]
    assert report["evidence"]["unexpected_mutations"] == ["main.ts"]
    assert any("forbidden" in reason for reason in report["reasons"])
    assert any("unexpected mutations" in reason for reason in report["reasons"])


def test_obvious_no_behavior_change_contradiction_is_unsupported():
    report = invariants.build_invariant_verification(
        _record(
            code_invariant="No behavior change is expected from this patch.",
            plain_english_invariant="Behavior unchanged for users.",
            patch_summary="Fix shipped status display bug.",
        )
    )

    assert report["verdict"] == "unsupported"
    assert any("contradicts" in reason for reason in report["reasons"])


def test_builder_does_not_mutate_input_record():
    record = _record(
        changed_files=["normalizer.ts"],
        evidence={"validation_output": "nested evidence\n"},
    )
    before = copy.deepcopy(record)

    invariants.build_invariant_verification(record)

    assert record == before


def test_markdown_includes_both_invariant_forms_and_guardrail():
    report = invariants.build_invariant_verification(_record())

    markdown = invariants.format_invariant_verification_markdown(report)

    assert "# Patch Invariant Verification" in markdown
    assert "## Code Invariant" in markdown
    assert "normalizeStatus" in markdown
    assert "## Plain-English Invariant" in markdown
    assert "Orders with extra spaces" in markdown
    assert "## Evidence" in markdown
    assert invariants.GUARDRAIL_NOTE in markdown


def test_cli_writes_json_and_markdown_and_preserves_source_artifact(tmp_path):
    repo = _tmp_repo(tmp_path)
    source = repo / ".agent" / "experiments" / "source_patch_artifact.json"
    source.write_text(json.dumps(_record(), indent=2) + "\n", encoding="utf-8")
    before_bytes = source.read_bytes()
    output_json = repo / ".agent" / "experiments" / "invariant.json"
    output_md = repo / ".agent" / "experiments" / "invariant.md"

    exit_code = report_cli.main(
        [
            "--repo-path",
            str(repo),
            "--input-json",
            str(source),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert exit_code == 0
    assert source.read_bytes() == before_bytes
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["verdict"] == "supported"
    assert "# Patch Invariant Verification" in output_md.read_text(encoding="utf-8")


def test_cli_default_outputs_land_under_agent_experiments(tmp_path):
    repo = _tmp_repo(tmp_path)
    source = repo / ".agent" / "experiments" / "source_patch_artifact.json"
    source.write_text(json.dumps(_record()) + "\n", encoding="utf-8")

    exit_code = report_cli.main(
        ["--repo-path", str(repo), "--input-json", ".agent/experiments/source_patch_artifact.json"]
    )

    assert exit_code == 0
    outputs = sorted((repo / ".agent" / "experiments").glob("*_invariant-verification.*"))
    assert [path.suffix for path in outputs] == [".json", ".md"]


def test_cli_rejects_traversal_and_writes_no_artifacts(tmp_path):
    repo = _tmp_repo(tmp_path)

    exit_code = report_cli.main(
        ["--repo-path", str(repo), "--input-json", "../outside.json"]
    )

    assert exit_code == 2
    assert not list((repo / ".agent" / "experiments").glob("*_invariant-verification.*"))


def test_cli_rejects_input_as_output(tmp_path):
    repo = _tmp_repo(tmp_path)
    source = repo / ".agent" / "experiments" / "source_patch_artifact.json"
    source.write_text(json.dumps(_record()) + "\n", encoding="utf-8")

    exit_code = report_cli.main(
        [
            "--repo-path",
            str(repo),
            "--input-json",
            str(source),
            "--output-json",
            str(source),
        ]
    )

    assert exit_code == 2


def test_core_and_cli_have_no_forbidden_execution_or_behavior_edges():
    for source in (CORE_SOURCE, CLI_SOURCE):
        tree = _parse_source(source)
        imports = _imported_modules(tree)
        roots = {name.split(".", maxsplit=1)[0] for name in imports}
        calls = _called_names(tree)

        assert imports & FORBIDDEN_IMPORTS == set(), source
        assert roots & FORBIDDEN_IMPORT_ROOTS == set(), source
        assert calls & FORBIDDEN_CALLS == set(), source


@pytest.mark.parametrize("source_path", SENSITIVE_SOURCE_PATHS)
def test_control_lesson_and_anti_lesson_modules_do_not_reference_invariant_verification(source_path):
    assert _module_references(_parse_source(source_path), "invariant_verification") == set()
