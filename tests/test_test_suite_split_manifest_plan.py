"""Tests for OPS.TEST.3 - Suite Split Manifest Plan.

OPS.TEST.3 is report-only. It plans named test-suite manifests and validation
gates without moving tests, deleting tests, skipping tests, weakening coverage,
hiding failures, or changing production behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.test_suite_split_manifest_plan import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    build_test_suite_split_manifest_plan,
    render_test_suite_split_manifest_plan_markdown,
    write_test_suite_split_manifest_plan,
)
import scripts.create_test_suite_split_manifest_plan as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "test_suite_split_manifest_plan.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_test_suite_split_manifest_plan.py"


def _plan(**kwargs) -> dict:
    return build_test_suite_split_manifest_plan(
        repo_root=PROJECT_ROOT,
        plan_id="ops-test-3-test",
        created_at="2026-07-09T00:00:00+09:00",
        **kwargs,
    )


def test_constants_match_ops_test_3_contract():
    assert REPORT_KIND == "test_suite_split_manifest_plan"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ops" / "test_suite_split_manifest_plan"
    assert JSON_NAME == "test_suite_split_manifest_plan.json"
    assert MD_NAME == "test_suite_split_manifest_plan.md"


def test_default_plan_is_ready_with_warnings_and_report_only():
    plan = _plan()

    assert plan["phase_id"] == "OPS.TEST.3"
    assert plan["plan_status"] == STATUS_READY_WITH_WARNINGS
    assert plan["plan_id"] == "ops-test-3-test"
    assert plan["source_runtime_profile_audit_path"].endswith(
        ".agent/ops/test_suite_runtime_profile_audit/test_suite_runtime_profile_audit.json"
    )
    assert plan["source_slow_timing_report_path"].endswith(
        ".agent/ops/slow_test_timing_collector/slow_test_timing_report.json"
    )
    assert any("executable manifest files" in warning.lower() for warning in plan["warnings"])
    assert plan["guardrails"]["report_only"] is True
    assert plan["guardrails"]["no_production_behavior_change"] is True
    assert plan["recommended_next_phase"]["phase_id"] == "OPS.TEST.CLOSE"


def test_required_manifest_profiles_are_present_with_expected_purposes():
    plan = _plan()
    profiles = {profile["profile_id"]: profile for profile in plan["manifest_profiles"]}

    assert set(profiles) == {
        "smoke",
        "phase",
        "branch",
        "registry_picker",
        "benchmark",
        "full",
        "nightly",
        "release_freeze",
    }
    assert "syntax and registry health" in profiles["smoke"]["purpose"].lower()
    assert "current phase implementation" in profiles["phase"]["purpose"].lower()
    assert "whole branch chain" in profiles["branch"]["purpose"].lower()
    assert "roadmap integrity" in profiles["registry_picker"]["purpose"].lower()
    assert "benchmark metadata" in profiles["benchmark"]["purpose"].lower()
    assert "full verification" in profiles["full"]["purpose"].lower()
    assert "timing collection" in " ".join(profiles["nightly"]["should_include"]).lower()
    assert "pre-release" in profiles["release_freeze"]["purpose"].lower()


def test_profile_command_templates_include_commands_timeouts_and_failure_policy():
    plan = _plan()
    templates = {template["profile_id"]: template for template in plan["profile_command_templates"]}

    assert "python -m compileall -q core scripts tests benchmarks web" in templates["smoke"]["command_templates"]
    assert "tests/test_<current_phase>.py" in " ".join(templates["phase"]["command_templates"])
    assert "direct dependency" in " ".join(templates["phase"]["notes"]).lower()
    assert "branch chain" in " ".join(templates["branch"]["notes"]).lower()
    assert "python benchmarks/run_benchmarks.py --check" in templates["benchmark"]["command_templates"]
    assert templates["full"]["command_templates"] == ["python -m pytest -q"]
    assert templates["full"]["recommended_timeout_seconds"] >= 1800
    assert templates["nightly"]["recommended_timeout_seconds"] >= 1800
    assert templates["release_freeze"]["recommended_timeout_seconds"] >= 1800
    assert templates["full"]["failure_policy"]["timeout_is_pass"] is False
    assert templates["full"]["failure_policy"]["requires_successful_pytest_exit"] is True


def test_required_gates_by_context_are_explicit():
    plan = _plan()
    gates = plan["required_gates_by_context"]

    assert gates["before_commit"] == ["smoke", "phase"]
    assert gates["registry_change"] == ["registry_picker", "benchmark"]
    assert gates["before_branch_close"] == ["smoke", "phase", "branch", "registry_picker", "benchmark"]
    assert gates["before_release"] == ["release_freeze"]


def test_timeout_and_failure_policies_preserve_full_suite_truth():
    plan = _plan()
    timeout_policy = plan["timeout_policy"]
    failure_policy = plan["failure_reporting_policy"]

    assert timeout_policy["smoke"]["recommended_timeout_seconds"] < 1800
    assert timeout_policy["phase"]["recommended_timeout_seconds"] < 1800
    assert timeout_policy["branch"]["recommended_timeout_seconds"] < 1800
    assert timeout_policy["full"]["recommended_timeout_seconds"] >= 1800
    assert timeout_policy["nightly"]["recommended_timeout_seconds"] >= 1800
    assert timeout_policy["release_freeze"]["recommended_timeout_seconds"] >= 1800
    assert failure_policy["timeout_is_pass"] is False
    assert failure_policy["full_suite_pass_requires_successful_pytest_exit"] is True
    assert "not completed within quick-gate timeout" in failure_policy["quick_gate_timeout_message"]
    assert failure_policy["partial_output_can_claim_full_suite_health"] is False
    assert failure_policy["skipped_tests_must_be_reported"] is True
    assert failure_policy["xfail_tests_remain_visible"] is True


def test_blocks_policies_that_delete_weaken_hide_timeout_or_silently_exclude():
    for markers in (
        {"test_deletion_recommended": True},
        {"safety_coverage_weakened": True},
        {"failures_hidden": True},
        {"timeout_treated_as_pass": True},
        {"slow_tests_silently_excluded": True},
        {"production_behavior_mutated": True},
        {"benchmark_check_weakened": True},
        {"automatic_test_skipping_added": True},
    ):
        plan = _plan(policy_violation_markers=markers)
        assert plan["plan_status"] == STATUS_BLOCKED
        assert plan["blocked_reasons"], markers


def test_incomplete_when_required_profiles_templates_or_policies_are_missing():
    missing_profiles = _plan(manifest_profiles=[])
    missing_templates = _plan(profile_command_templates=[])
    missing_timeout = _plan(timeout_policy={})
    missing_failure = _plan(failure_reporting_policy={})

    assert missing_profiles["plan_status"] == STATUS_INCOMPLETE
    assert any("required manifest profiles" in reason.lower() for reason in missing_profiles["incomplete_reasons"])
    assert missing_templates["plan_status"] == STATUS_INCOMPLETE
    assert any("command templates" in reason.lower() for reason in missing_templates["incomplete_reasons"])
    assert missing_timeout["plan_status"] == STATUS_INCOMPLETE
    assert any("timeout policy" in reason.lower() for reason in missing_timeout["incomplete_reasons"])
    assert missing_failure["plan_status"] == STATUS_INCOMPLETE
    assert any("failure reporting policy" in reason.lower() for reason in missing_failure["incomplete_reasons"])


def test_ready_status_available_when_future_manifest_boundary_is_marked_clear():
    plan = _plan(executable_manifest_boundary_clear=True)

    assert plan["plan_status"] == STATUS_READY
    assert not plan["warnings"]
    assert plan["final_verdict"]["ready_for_next_phase"] is True


def test_json_and_markdown_manifest_plan_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "ops-test-3"

    result = write_test_suite_split_manifest_plan(
        repo_root=PROJECT_ROOT,
        output_dir=output_dir,
        plan_id="write-test",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["plan_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "OPS.TEST.CLOSE"
    assert "# Test Suite Split Manifest Plan" in markdown
    assert "## Profile Command Templates" in markdown


def test_cli_writes_summary_json_without_running_validation(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = script.run_create_test_suite_split_manifest_plan(
        repo_root=str(PROJECT_ROOT),
        output_dir=str(output_dir),
        plan_id="cli-test",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["plan_status"] == STATUS_READY_WITH_WARNINGS
    assert result["summary"]["profile_count"] == 8
    assert result["summary"]["recommended_next_phase"] == "OPS.TEST.CLOSE"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_sections():
    markdown = render_test_suite_split_manifest_plan_markdown(_plan())
    low = markdown.lower()
    for section in (
        "## summary",
        "## manifest profiles",
        "## profile command templates",
        "## required gates by context",
        "## timeout policy",
        "## failure reporting policy",
        "## suite split recommendations",
        "## no weakening policy",
        "## warnings",
        "## blocked reasons",
        "## incomplete reasons",
        "## recommended next phase",
        "## guardrails",
    ):
        assert section in low, section


def test_real_registry_marks_ops_test_3_complete_and_recommends_ops_test_close():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["OPS.TEST.3"]["status"] == "complete"
    assert by_id["OPS.TEST.3"]["title"] == "Suite Split Manifest Plan"
    assert by_id["OPS.TEST.3"]["expected_artifacts"] == [
        ".agent/ops/test_suite_split_manifest_plan/test_suite_split_manifest_plan.json",
        ".agent/ops/test_suite_split_manifest_plan/test_suite_split_manifest_plan.md",
    ]
    assert by_id["OPS.TEST.CLOSE"]["status"] == "complete"
    assert by_id["OPS.TEST.CLOSE"]["title"] == "Test Runtime Operations Branch Checkpoint"
    assert by_id["OPS.TEST.CLOSE"]["prerequisites"] == ["OPS.TEST.3"]
    assert by_id["OPS.TEST.CLOSE"]["network_allowed"] is False
    assert by_id["OPS.TEST.CLOSE"]["model_calls_allowed"] is False
    assert by_id["OPS.TEST.CLOSE"]["writes_real_repo"] is False

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="ops-test-3-registry",
        created_at="2026-07-09T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "UX.RUN.1"


def test_core_and_cli_do_not_import_or_call_pytest_execution_or_mutation_primitives():
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
    forbidden_text = ("subprocess", "pytest.main(")

    for path in (CORE_PATH, SCRIPT_PATH):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
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
        for text in forbidden_text:
            assert text not in source
