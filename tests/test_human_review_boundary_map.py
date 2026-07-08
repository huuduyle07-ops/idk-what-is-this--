"""Tests for HUMAN.N1 - Human Review Boundary Map.

HUMAN.N1 is report-only. It maps advisory systems to human-only authority
boundaries without adding enforcement, execution, approval, routing, validation,
benchmark, model, network, worker, MCP, Docker/subprocess, database, auth, Dream,
Replay, or patch-apply behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.human_review_boundary_map import (
    ACTION_CATEGORIES,
    AUTHORITY_LEVELS,
    BRANCHES,
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY_WITH_WARNINGS,
    build_human_review_boundary_map,
    render_human_review_boundary_map_markdown,
    write_human_review_boundary_map,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from scripts.create_human_review_boundary_map import run_create_human_review_boundary_map


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "human_review_boundary_map.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_human_review_boundary_map.py"


def _report(**kwargs) -> dict:
    return build_human_review_boundary_map(
        report_id="human-n1-test",
        created_at="2026-07-07T00:00:00+00:00",
        **kwargs,
    )


def _matrix(report: dict) -> dict[str, dict]:
    return {item["action_id"]: item for item in report["boundary_matrix"]}


def test_constants_match_human_n1_contract():
    assert REPORT_KIND == "human_review_boundary_map"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "human" / "review_boundary_map"
    assert JSON_NAME == "human_review_boundary_map.json"
    assert MD_NAME == "human_review_boundary_map.md"
    assert AUTHORITY_LEVELS == (
        "advisory_only",
        "human_review_required",
        "explicit_human_approval_required",
        "forbidden_without_separate_phase",
        "blocked",
    )
    assert set(BRANCHES) == {"MIRROR", "CMD", "MODEL", "EVAL", "HARDEN", "UX"}


def test_boundary_map_covers_all_critical_action_categories():
    report = _report()
    matrix = _matrix(report)

    assert report["report_kind"] == REPORT_KIND
    assert report["boundary_status"] == STATUS_READY_WITH_WARNINGS
    assert set(matrix) == set(ACTION_CATEGORIES)
    assert report["summary"]["critical_action_category_count"] == len(ACTION_CATEGORIES)
    assert report["summary"]["missing_critical_action_categories"] == []
    assert report["guardrails"]["report_only"] is True
    assert report["guardrails"]["approval_or_rejection_performed"] is False


def test_required_authority_levels_are_mapped():
    matrix = _matrix(_report())

    assert matrix["advisory_reports"]["authority_level"] == "advisory_only"
    assert matrix["patch_apply"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["direct_file_mutation"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["worker_launch"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["model_routing"]["authority_level"] == "forbidden_without_separate_phase"
    assert matrix["model_calls"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["validation_execution"]["automatic_allowed"] is False
    assert matrix["benchmark_execution"]["automatic_allowed"] is False
    assert matrix["mcp_tool_invocation"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["network_access"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["subprocess_docker_execution"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["database_writes"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["web_route_auth_policy_changes"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["registry_adoption"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["model_role_catalog_adoption"]["authority_level"] == "explicit_human_approval_required"
    assert matrix["evidence_quality_acceptance"]["authority_level"] == "forbidden_without_separate_phase"
    assert matrix["automatic_approval_rejection"]["authority_level"] == "blocked"
    assert matrix["hidden_mutation"]["authority_level"] == "blocked"


def test_forbidden_automatic_actions_are_blocked():
    report = _report()
    forbidden = {item["action_id"]: item for item in report["forbidden_automatic_actions"]}

    for action_id in (
        "auto_apply_patch",
        "auto_reject_patch",
        "auto_approve_patch",
        "auto_launch_worker",
        "auto_route_model",
        "auto_run_validation",
        "auto_run_benchmark",
        "auto_mutate_registry",
        "auto_adopt_model_catalog",
        "auto_call_mcp_tool",
        "auto_write_database",
        "auto_change_auth_policy",
        "auto_execute_remote_command",
    ):
        assert forbidden[action_id]["authority_level"] == "blocked"
        assert forbidden[action_id]["automatic_allowed"] is False


def test_branch_specific_boundaries_are_present():
    report = _report()
    branches = report["branch_specific_boundaries"]

    assert set(branches) == set(BRANCHES)
    assert "may display drift/derailment evidence" in branches["MIRROR"]["may"]
    assert "may not auto-reject a run" in branches["MIRROR"]["may_not"]
    assert "may fracture and plan tasks" in branches["CMD"]["may"]
    assert "may not launch workers" in branches["CMD"]["may_not"]
    assert "may define tower cards" in branches["MODEL"]["may"]
    assert "may not route to models" in branches["MODEL"]["may_not"]
    assert "may report evidence quality" in branches["EVAL"]["may"]
    assert "may not run missing validation" in branches["EVAL"]["may_not"]
    assert "may audit safety boundaries" in branches["HARDEN"]["may"]
    assert "may display advisory status" in branches["UX"]["may"]


def test_markdown_contains_required_report_sections():
    markdown = render_human_review_boundary_map_markdown(_report())
    low = markdown.lower()
    for section in (
        "## summary",
        "## authority philosophy",
        "## advisory systems covered",
        "## human-only decisions",
        "## explicit approval actions",
        "## forbidden automatic actions",
        "## boundary matrix",
        "## branch-specific boundaries",
        "## mirror",
        "## cmd",
        "## model",
        "## eval",
        "## harden",
        "## ux",
        "## human review checklist",
        "## guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_missing_critical_boundary_reports_incomplete():
    base_matrix = _report()["boundary_matrix"]
    reduced = [item for item in base_matrix if item["action_id"] != "patch_apply"]

    report = _report(action_boundaries=reduced)

    assert report["boundary_status"] == STATUS_INCOMPLETE
    assert "patch_apply" in report["summary"]["missing_critical_action_categories"]


def test_auto_approval_allowed_blocks_boundary_map():
    base_matrix = _report()["boundary_matrix"]
    changed = []
    for item in base_matrix:
        next_item = dict(item)
        if next_item["action_id"] == "automatic_approval_rejection":
            next_item["automatic_allowed"] = True
        changed.append(next_item)

    report = _report(action_boundaries=changed)

    assert report["boundary_status"] == STATUS_BLOCKED
    assert "auto_approval_allowed" in {item["reason"] for item in report["blocked_reasons"]}


def test_hidden_mutation_allowed_blocks_boundary_map():
    base_matrix = _report()["boundary_matrix"]
    changed = []
    for item in base_matrix:
        next_item = dict(item)
        if next_item["action_id"] == "hidden_mutation":
            next_item["authority_level"] = "explicit_human_approval_required"
            next_item["automatic_allowed"] = True
        changed.append(next_item)

    report = _report(action_boundaries=changed)

    assert report["boundary_status"] == STATUS_BLOCKED
    assert "hidden_mutation_allowed" in {item["reason"] for item in report["blocked_reasons"]}


def test_ai_executable_authority_blocks_boundary_map():
    base_matrix = _report()["boundary_matrix"]
    changed = []
    for item in base_matrix:
        next_item = dict(item)
        if next_item["action_id"] == "patch_apply":
            next_item["ai_may_execute"] = True
        changed.append(next_item)

    report = _report(action_boundaries=changed)

    assert report["boundary_status"] == STATUS_BLOCKED
    assert "ai_executable_authority" in {item["reason"] for item in report["blocked_reasons"]}


def test_json_and_markdown_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "human-n1"

    result = write_human_review_boundary_map(
        output_dir=output_dir,
        report_id="write-test",
        created_at="2026-07-07T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["boundary_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "HUMAN.N2"
    assert "# Human Review Boundary Map" in markdown
    assert "HUMAN.N2" in markdown


def test_cli_writes_summary_json(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = run_create_human_review_boundary_map(
        output_dir=output_dir,
        report_id="cli-test",
        created_at="2026-07-07T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["summary"]["boundary_status"] == STATUS_READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "HUMAN.N2"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_core_and_cli_do_not_import_or_call_execution_primitives():
    forbidden_imports = {"subprocess", "socket", "requests", "httpx", "urllib", "openai", "anthropic"}
    forbidden_calls = {
        "run_validation",
        "run_safe_validation",
        "run_benchmarks",
        "run_gemini_request",
        "run_deepseek_review",
        "call_model",
        "route_model",
        "apply_patch",
        "launch_worker",
        "invoke_mcp",
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


def test_real_registry_marks_human_n1_complete_and_picker_recommends_adopt_model_1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HUMAN.N1"]["status"] == "complete"
    assert by_id["HUMAN.N1"]["prerequisites"] == ["EVAL.CLOSE"]
    assert by_id["HUMAN.N1"]["expected_artifacts"] == [
        ".agent/human/review_boundary_map/human_review_boundary_map.json",
        ".agent/human/review_boundary_map/human_review_boundary_map.md",
    ]
    assert by_id["HUMAN.N1"]["network_allowed"] is False
    assert by_id["HUMAN.N1"]["model_calls_allowed"] is False
    assert by_id["HUMAN.N1"]["writes_real_repo"] is False
    assert by_id["HUMAN.N2"]["status"] == "complete"
    assert by_id["HUMAN.N2"]["prerequisites"] == ["HUMAN.N1"]
    assert by_id["HUMAN.N2"]["title"] == "Human Approval Token / Confirmation Contract"

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="human-n1-registry",
        created_at="2026-07-07T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "HARDEN.CLOSE"
