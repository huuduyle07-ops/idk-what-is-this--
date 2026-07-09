"""Tests for OPS.TEST.CLOSE - Test Runtime Operations Branch Checkpoint.

OPS.TEST.CLOSE is report-only. It verifies that OPS.TEST.1 through OPS.TEST.3
are complete, safe, non-mutating, and ready to freeze before any executable
suite runner, manifest files, or CI behavior is implemented.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.test_runtime_operations_branch_checkpoint import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_INCOMPLETE,
    build_test_runtime_operations_branch_checkpoint,
    render_test_runtime_operations_branch_checkpoint_markdown,
    write_test_runtime_operations_branch_checkpoint,
)
from core.test_suite_runtime_profile_audit import build_test_suite_runtime_profile_audit
from core.slow_test_timing_collector import build_slow_test_timing_report
from core.test_suite_split_manifest_plan import build_test_suite_split_manifest_plan
import scripts.create_test_runtime_operations_branch_checkpoint as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "test_runtime_operations_branch_checkpoint.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_test_runtime_operations_branch_checkpoint.py"


def _phase(phase_id: str, status: str = "complete", **overrides) -> dict:
    data = {
        "phase_id": phase_id,
        "title": phase_id,
        "track": phase_id.split(".", 1)[0],
        "status": status,
        "summary": f"Report-only phase {phase_id}.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/example.py", "tests/test_example.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest tests/test_example.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/example/report.json"],
        "notes": ["Report-only."],
    }
    data.update(overrides)
    return data


def _registry(*, include_ops_test_3: bool = True, close_status: str = "complete") -> dict:
    phases = [
        _phase("OPS.TEST.1", title="Test Suite Runtime Profile Audit"),
        _phase("OPS.TEST.2", title="Slow Test Timing Collector", prerequisites=["OPS.TEST.1"]),
    ]
    if include_ops_test_3:
        phases.append(_phase("OPS.TEST.3", title="Suite Split Manifest Plan", prerequisites=["OPS.TEST.2"]))
    phases.extend(
        [
            _phase(
                "OPS.TEST.CLOSE",
                status=close_status,
                title="Test Runtime Operations Branch Checkpoint",
                prerequisites=["OPS.TEST.3"],
            ),
            _phase(
                "UX.RUN.1",
                status="proposed",
                title="Run Progress / Operator Visibility",
                track="UX",
                prerequisites=["OPS.TEST.CLOSE"],
            ),
        ]
    )
    return {
        "schema_version": "1.0",
        "updated_at": "2026-07-09T00:00:00+09:00",
        "phases": phases,
    }


def _runtime_profile_report(**kwargs) -> dict:
    return build_test_suite_runtime_profile_audit(
        repo_root=PROJECT_ROOT,
        audit_id="ops-test-1-source",
        created_at="2026-07-09T00:00:00+09:00",
        exact_per_test_runtime_measurements_collected=True,
        **kwargs,
    )


def _timing_report(**kwargs) -> dict:
    return build_slow_test_timing_report(
        repo_root=PROJECT_ROOT,
        report_id="ops-test-2-source",
        created_at="2026-07-09T00:00:00+09:00",
        timing_text="2.50s call     tests/test_cli.py::test_a\n",
        allow_sample_timing=False,
        **kwargs,
    )


def _manifest_plan(**kwargs) -> dict:
    return build_test_suite_split_manifest_plan(
        repo_root=PROJECT_ROOT,
        plan_id="ops-test-3-source",
        created_at="2026-07-09T00:00:00+09:00",
        **kwargs,
    )


def _checkpoint(**kwargs) -> dict:
    args = {
        "registry_data": _registry(),
        "source_runtime_profile_audit": _runtime_profile_report(),
        "source_slow_timing_report": _timing_report(),
        "source_suite_split_manifest_plan": _manifest_plan(),
        "checkpoint_id": "ops-test-close-test",
        "created_at": "2026-07-09T00:00:00+09:00",
    }
    args.update(kwargs)
    return build_test_runtime_operations_branch_checkpoint(**args)


def test_constants_match_ops_test_close_contract():
    assert REPORT_KIND == "test_runtime_operations_branch_checkpoint"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ops" / "test_runtime_operations_branch_checkpoint"
    assert JSON_NAME == "test_runtime_operations_branch_checkpoint.json"
    assert MD_NAME == "test_runtime_operations_branch_checkpoint.md"


def test_complete_ops_test_1_to_3_registry_produces_frozen_or_warning_status():
    report = _checkpoint()

    assert report["checkpoint_id"] == "ops-test-close-test"
    assert report["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS}
    assert report["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert report["phase_completion_summary"]["all_required_phases_complete"] is True
    assert report["artifact_coverage"]["all_required_artifacts_present"] is True
    assert report["profile_coverage"]["runtime_profiles_exist"] is True
    assert report["timing_collector_summary"]["slow_timing_collector_exists"] is True
    assert report["suite_manifest_summary"]["suite_manifest_plan_exists"] is True
    assert report["timeout_policy_summary"]["full_timeout_policy_explicit"] is True
    assert report["timeout_policy_summary"]["timeout_is_not_pass"] is True
    assert report["failure_reporting_policy_summary"]["full_pytest_pass_requires_successful_exit"] is True
    assert report["no_weakening_verification"]["all_clear"] is True
    assert report["non_execution_verification"]["all_clear"] is True
    assert report["recommended_next_phase"]["phase_id"] == "UX.RUN.1"
    assert any("future" in warning.lower() for warning in report["warnings"])
    assert report["blocked_reasons"] == []
    assert report["incomplete_reasons"] == []


def test_missing_ops_test_3_reports_incomplete():
    report = _checkpoint(registry_data=_registry(include_ops_test_3=False))

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("OPS.TEST.3" in reason for reason in report["incomplete_reasons"])


def test_missing_runtime_profile_artifact_reports_incomplete():
    report = _checkpoint(source_runtime_profile_audit=None, source_runtime_profile_audit_load_error="missing runtime profile")

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("runtime profile" in reason.lower() for reason in report["incomplete_reasons"])


def test_missing_timing_report_artifact_reports_incomplete():
    report = _checkpoint(source_slow_timing_report=None, source_slow_timing_report_load_error="missing timing report")

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("timing report" in reason.lower() for reason in report["incomplete_reasons"])


def test_missing_manifest_plan_artifact_reports_incomplete():
    report = _checkpoint(
        source_suite_split_manifest_plan=None,
        source_suite_split_manifest_plan_load_error="missing manifest plan",
    )

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("manifest plan" in reason.lower() for reason in report["incomplete_reasons"])


def test_blocking_policy_markers_block_checkpoint():
    for markers in (
        {"test_deletion_recommended": True},
        {"safety_coverage_weakened": True},
        {"timeout_treated_as_pass": True},
        {"hidden_failure_policy": True},
        {"executable_runner_behavior_added": True},
    ):
        report = _checkpoint(policy_violation_markers=markers)
        assert report["checkpoint_status"] == STATUS_BLOCKED
        assert report["blocked_reasons"], markers


def test_checkpoint_json_and_markdown_artifacts_are_written(tmp_path):
    registry_path = tmp_path / "phase_registry.json"
    runtime_path = tmp_path / "runtime.json"
    timing_path = tmp_path / "timing.json"
    manifest_path = tmp_path / "manifest.json"
    output_dir = tmp_path / "checkpoint"
    registry_path.write_text(json.dumps(_registry(), indent=2), encoding="utf-8")
    runtime_path.write_text(json.dumps(_runtime_profile_report(), indent=2), encoding="utf-8")
    timing_path.write_text(json.dumps(_timing_report(), indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(_manifest_plan(), indent=2), encoding="utf-8")

    result = write_test_runtime_operations_branch_checkpoint(
        repo_root=PROJECT_ROOT,
        registry_path=registry_path,
        output_dir=output_dir,
        source_runtime_profile_audit_path=runtime_path,
        source_slow_timing_report_path=timing_path,
        source_suite_split_manifest_plan_path=manifest_path,
        checkpoint_id="write-test",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert "# Test Runtime Operations Branch Checkpoint" in markdown
    assert "## Non-Execution Verification" in markdown


def test_cli_writes_summary_json(tmp_path):
    registry_path = tmp_path / "phase_registry.json"
    runtime_path = tmp_path / "runtime.json"
    timing_path = tmp_path / "timing.json"
    manifest_path = tmp_path / "manifest.json"
    output_dir = tmp_path / "cli-out"
    registry_path.write_text(json.dumps(_registry(), indent=2), encoding="utf-8")
    runtime_path.write_text(json.dumps(_runtime_profile_report(), indent=2), encoding="utf-8")
    timing_path.write_text(json.dumps(_timing_report(), indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(_manifest_plan(), indent=2), encoding="utf-8")

    result = script.run_create_test_runtime_operations_branch_checkpoint(
        repo_root=str(PROJECT_ROOT),
        registry=str(registry_path),
        output_dir=str(output_dir),
        source_runtime_profile_audit_path=str(runtime_path),
        source_slow_timing_report_path=str(timing_path),
        source_suite_split_manifest_plan_path=str(manifest_path),
        checkpoint_id="cli-test",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "UX.RUN.1"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_sections():
    markdown = render_test_runtime_operations_branch_checkpoint_markdown(_checkpoint())
    low = markdown.lower()
    for section in (
        "## summary",
        "## phase completion",
        "## artifact coverage",
        "## runtime profile summary",
        "## timing collector summary",
        "## suite manifest plan summary",
        "## timeout and failure policy",
        "## no-weakening verification",
        "## non-execution verification",
        "## warnings",
        "## blocked reasons",
        "## incomplete reasons",
        "## final verdict",
        "## recommended next phase",
        "## guardrails",
    ):
        assert section in low, section


def test_real_registry_marks_ops_test_close_complete_and_adds_ux_run_1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["OPS.TEST.CLOSE"]["status"] == "complete"
    assert by_id["OPS.TEST.CLOSE"]["title"] == "Test Runtime Operations Branch Checkpoint"
    assert by_id["OPS.TEST.CLOSE"]["prerequisites"] == ["OPS.TEST.3"]
    assert by_id["OPS.TEST.CLOSE"]["expected_artifacts"] == [
        ".agent/ops/test_runtime_operations_branch_checkpoint/test_runtime_operations_branch_checkpoint.json",
        ".agent/ops/test_runtime_operations_branch_checkpoint/test_runtime_operations_branch_checkpoint.md",
    ]
    assert by_id["UX.RUN.1"]["status"] == "proposed"
    assert by_id["UX.RUN.1"]["title"] == "Run Progress / Operator Visibility"
    assert by_id["UX.RUN.1"]["prerequisites"] == ["OPS.TEST.CLOSE"]
    assert by_id["UX.RUN.1"]["network_allowed"] is False
    assert by_id["UX.RUN.1"]["model_calls_allowed"] is False
    assert by_id["UX.RUN.1"]["writes_real_repo"] is False


def test_phase_picker_recommends_ux_run_1_after_ops_test_close():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="ops-test-close-registry",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert report["top_recommendation"]["phase_id"] == "UX.RUN.1"
    assert report["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"


def test_build_does_not_mutate_inputs():
    registry = _registry()
    runtime = _runtime_profile_report()
    timing = _timing_report()
    manifest = _manifest_plan()
    snapshot = copy.deepcopy((registry, runtime, timing, manifest))

    build_test_runtime_operations_branch_checkpoint(
        registry_data=registry,
        source_runtime_profile_audit=runtime,
        source_slow_timing_report=timing,
        source_suite_split_manifest_plan=manifest,
    )

    assert (registry, runtime, timing, manifest) == snapshot


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
