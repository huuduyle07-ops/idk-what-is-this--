"""Tests for OPS.TEST.1 - Test Suite Runtime Profile Audit.

OPS.TEST.1 is report-only. It documents practical pytest runtime profiles and
validation reporting policy so a quick timeout is reported honestly without
weakening or deleting tests.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.test_suite_runtime_profile_audit import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    build_test_suite_runtime_profile_audit,
    render_test_suite_runtime_profile_audit_markdown,
    write_test_suite_runtime_profile_audit,
)
import scripts.create_test_suite_runtime_profile_audit as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "test_suite_runtime_profile_audit.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_test_suite_runtime_profile_audit.py"


def _audit(**kwargs) -> dict:
    return build_test_suite_runtime_profile_audit(
        repo_root=PROJECT_ROOT,
        audit_id="ops-test-1-test",
        created_at="2026-07-09T00:00:00+09:00",
        **kwargs,
    )


def _profiles_by_name(report: dict) -> dict[str, dict]:
    return {str(item["name"]): item for item in report["suite_profiles"]}


def test_constants_match_ops_test_1_contract():
    assert REPORT_KIND == "test_suite_runtime_profile_audit"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ops" / "test_suite_runtime_profile_audit"
    assert JSON_NAME == "test_suite_runtime_profile_audit.json"
    assert MD_NAME == "test_suite_runtime_profile_audit.md"


def test_default_audit_is_ready_with_warnings_and_report_only():
    report = _audit()

    assert report["report_kind"] == REPORT_KIND
    assert report["phase_id"] == "OPS.TEST.1"
    assert report["audit_status"] == STATUS_READY_WITH_WARNINGS
    assert report["audit_id"] == "ops-test-1-test"
    assert report["known_full_suite_runtime_estimate"]["display"] == "20-25 minutes"
    assert report["quick_timeout_seconds"] == 304
    assert report["full_timeout_seconds"] >= 30 * 60
    assert report["recommended_next_phase"]["phase_id"] == "OPS.TEST.2"
    assert report["guardrails"]["report_only"] is True
    assert report["guardrails"]["no_test_deletion"] is True
    assert report["guardrails"]["no_safety_weakening"] is True
    assert report["guardrails"]["no_production_behavior_change"] is True
    assert report["guardrails"]["no_validation_run"] is True
    assert report["guardrails"]["no_benchmark_mutation"] is True
    assert report["blocked_reasons"] == []
    assert any("exact per-test runtime" in warning.lower() for warning in report["warnings"])


def test_report_schema_contains_required_audit_fields():
    report = _audit()

    for key in (
        "audit_id",
        "audit_status",
        "known_full_suite_runtime_estimate",
        "quick_timeout_seconds",
        "full_timeout_seconds",
        "suite_profiles",
        "recommended_phase_gate",
        "recommended_branch_close_gate",
        "recommended_release_gate",
        "known_timeout_interpretation",
        "validation_reporting_policy",
        "slow_suite_notes",
        "blocked_reasons",
        "warnings",
        "recommended_next_phase",
        "guardrails",
    ):
        assert key in report, key


def test_required_suite_profiles_are_defined_with_commands():
    report = _audit()
    profiles = _profiles_by_name(report)

    assert set(profiles) == {
        "smoke",
        "phase",
        "branch",
        "registry_picker",
        "benchmark",
        "full",
        "nightly",
    }
    assert "python -m compileall -q core scripts tests benchmarks web" in profiles["smoke"]["commands"]
    assert "python -m pytest tests/test_<current_phase>.py -q" in profiles["phase"]["commands"]
    assert "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q" in profiles["registry_picker"]["commands"]
    assert profiles["benchmark"]["commands"] == ["python benchmarks/run_benchmarks.py --check"]
    assert profiles["full"]["commands"] == ["python -m pytest -q"]
    assert profiles["full"]["recommended_timeout_seconds"] >= 30 * 60
    assert "python -m pytest -q" in profiles["nightly"]["commands"]


def test_phase_branch_and_release_gate_recommendations_are_practical():
    report = _audit()

    phase_commands = report["recommended_phase_gate"]["commands"]
    assert "python -m compileall -q core scripts tests benchmarks web" in phase_commands
    assert "python -m pytest tests/test_<current_phase>.py -q" in phase_commands
    assert "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q" in phase_commands
    assert "python benchmarks/run_benchmarks.py --check" in phase_commands

    branch_commands = report["recommended_branch_close_gate"]["commands"]
    assert any("branch-chain" in command for command in branch_commands)
    assert "python benchmarks/run_benchmarks.py --check" in branch_commands
    assert report["recommended_branch_close_gate"]["full_pytest_required"] is False

    release_commands = report["recommended_release_gate"]["commands"]
    assert "python -m pytest -q" in release_commands
    assert "python benchmarks/run_benchmarks.py --check" in release_commands
    assert "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json" in release_commands
    assert "python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json" in release_commands


def test_timeout_interpretation_is_honest_and_never_passes_partial_output():
    report = _audit()
    timeout = report["known_timeout_interpretation"]
    policy_text = " ".join(report["validation_reporting_policy"]).lower()

    assert timeout["quick_timeout_on_full_suite"] == "full suite not completed within quick gate"
    assert timeout["timeout_counts_as_pass"] is False
    assert timeout["full_suite_health_requires_exit_success"] is True
    assert timeout["timeout_without_final_report"] == "timed out without final report"
    assert "do not claim full-suite health from partial output alone" in policy_text


def test_status_is_ready_when_exact_runtime_measurements_are_collected():
    report = _audit(exact_per_test_runtime_measurements_collected=True)

    assert report["audit_status"] == STATUS_READY
    assert report["warnings"] == []


def test_audit_is_incomplete_when_profiles_or_reporting_policy_are_missing():
    missing_profile = _audit(suite_profiles=[{"name": "smoke", "purpose": "Fast", "commands": ["python -m compileall -q core"]}])
    missing_policy = _audit(validation_reporting_policy=[])

    assert missing_profile["audit_status"] == STATUS_INCOMPLETE
    assert any("missing required suite profile" in reason.lower() for reason in missing_profile["incomplete_reasons"])
    assert missing_policy["audit_status"] == STATUS_INCOMPLETE
    assert any("validation reporting policy" in reason.lower() for reason in missing_policy["incomplete_reasons"])


def test_audit_blocks_policies_that_delete_tests_or_weaken_safety():
    for markers in (
        {"test_deletion_recommended": True},
        {"safety_coverage_weakened": True},
        {"failed_assertions_ignored": True},
        {"timeout_treated_as_pass": True},
        {"slow_tests_marked_unimportant": True},
        {"failures_hidden": True},
    ):
        report = _audit(policy_violation_markers=markers)
        assert report["audit_status"] == STATUS_BLOCKED
        assert report["blocked_reasons"], markers


def test_json_and_markdown_audit_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "ops-test-1"

    result = write_test_suite_runtime_profile_audit(
        repo_root=PROJECT_ROOT,
        output_dir=output_dir,
        audit_id="write-test",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["audit_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "OPS.TEST.2"
    assert "# Test Suite Runtime Profile Audit" in markdown
    assert "## Suite Profiles" in markdown
    assert "5-minute timeout" in markdown


def test_cli_writes_summary_json(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = script.run_create_test_suite_runtime_profile_audit(
        repo_root=str(PROJECT_ROOT),
        output_dir=str(output_dir),
        audit_id="cli-test",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["audit_status"] == STATUS_READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "OPS.TEST.2"
    assert result["summary"]["quick_timeout_seconds"] == 304
    assert result["summary"]["full_timeout_seconds"] >= 1800
    assert result["summary"]["suite_profile_count"] == 7
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_operator_sections():
    markdown = render_test_suite_runtime_profile_audit_markdown(_audit())
    low = markdown.lower()
    for section in (
        "## summary",
        "## suite profiles",
        "## phase gate",
        "## branch close gate",
        "## release gate",
        "## timeout interpretation",
        "## validation reporting policy",
        "## slow suite notes",
        "## warnings",
        "## blocked reasons",
        "## recommended next phase",
        "## guardrails",
    ):
        assert section in low, section


def test_real_registry_marks_ops_test_1_complete_and_recommends_ops_test_2():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["OPS.TEST.1"]["status"] == "complete"
    assert by_id["OPS.TEST.1"]["title"] == "Test Suite Runtime Profile Audit"
    assert by_id["OPS.TEST.1"]["expected_artifacts"] == [
        ".agent/ops/test_suite_runtime_profile_audit/test_suite_runtime_profile_audit.json",
        ".agent/ops/test_suite_runtime_profile_audit/test_suite_runtime_profile_audit.md",
    ]
    assert by_id["OPS.TEST.2"]["status"] == "proposed"
    assert by_id["OPS.TEST.2"]["title"] == "Slow Test Timing Collector"
    assert by_id["OPS.TEST.2"]["prerequisites"] == ["OPS.TEST.1"]
    assert by_id["OPS.TEST.2"]["network_allowed"] is False
    assert by_id["OPS.TEST.2"]["model_calls_allowed"] is False
    assert by_id["OPS.TEST.2"]["writes_real_repo"] is False

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="ops-test-1-registry",
        created_at="2026-07-09T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "OPS.TEST.2"


def test_core_and_cli_do_not_import_or_call_runtime_or_mutation_primitives():
    forbidden_imports = {
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "openai",
        "anthropic",
        "flask",
        "sqlite3",
        "benchmark",
        "benchmarks",
    }
    forbidden_calls = {
        "run_validation",
        "run_safe_validation_command",
        "run_benchmarks",
        "call_model",
        "route_model",
        "launch_worker",
        "invoke_mcp",
        "apply_patch",
        "delete_test",
        "remove_test",
        "Popen",
        "run",
        "check_call",
        "check_output",
        "urlopen",
    }

    for path in (CORE_PATH, SCRIPT_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.add(func.attr)

        assert imports.isdisjoint(forbidden_imports)
        assert calls.isdisjoint(forbidden_calls)
