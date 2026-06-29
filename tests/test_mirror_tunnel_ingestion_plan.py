"""Tests for MIRROR.4 - Real Run Trace Ingestion Plan.

MIRROR.4 defines how future real C.A.T.T.U.S runs should emit usable Mirror
Tunnel frames for MIRROR.1-MIRROR.3. It is report-only and must never call
models, run validation/benchmarks, invoke workers/MCP/Docker/subprocess, mutate
routes/auth, or enable automatic tracing.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core import mirror_tunnel_ingestion_plan as plan
from core.mirror_tunnel_ingestion_plan import (
    FRAME_TYPES,
    INGESTION_PRIORITIES,
    STATUSES,
    build_mirror_tunnel_ingestion_plan,
    render_mirror_tunnel_ingestion_markdown,
    write_mirror_tunnel_ingestion_plan,
)
from scripts import create_mirror_tunnel_ingestion_plan as cli


def test_constants_match_mirror_contract_and_priority_spec():
    assert FRAME_TYPES == (
        "user_intent",
        "goal_brief",
        "mode_decision",
        "control_prompt",
        "worker_assignment",
        "worker_reply",
        "patch_or_diff",
        "validation_evidence",
        "benchmark_evidence",
        "replay_evidence",
        "final_answer",
    )
    assert INGESTION_PRIORITIES == {
        "P0": ("user_intent", "control_prompt", "patch_or_diff", "validation_evidence", "final_answer"),
        "P1": ("goal_brief", "worker_assignment", "benchmark_evidence", "replay_evidence"),
        "P2": ("worker_reply", "mode_decision", "teaching_lesson_cards"),
    }
    assert STATUSES == (
        "ready_for_manual_ingestion",
        "partial_mapping_available",
        "insufficient_sources",
        "blocked",
    )


def test_default_plan_is_partial_mapping_and_recommends_mirror5(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".agent" / "benchmarks").mkdir(parents=True)
    (repo / ".agent" / "benchmarks" / "benchmark_report_demo.json").write_text("{}", encoding="utf-8")

    report = build_mirror_tunnel_ingestion_plan(
        repo_path=str(repo),
        plan_id="plan-fixture",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["plan_id"] == "plan-fixture"
    assert report["status"] == "partial_mapping_available"
    assert report["recommended_next_phase"] == "MIRROR.5"
    assert report["recommended_next_action"] == "prepare_mirror_frame_emitter_contract"
    assert report["current_trace_weakness"]["primary_weakness"] == "current traces are dominated by unknown_artifact frames"
    assert report["guardrails"]["automatic_mirror_tracing_enabled"] is False
    assert report["guardrails"]["validation_run"] is False
    assert report["guardrails"]["model_call_performed"] is False


def test_source_inventory_contains_expected_artifact_families(tmp_path):
    report = build_mirror_tunnel_ingestion_plan(repo_path=str(tmp_path), plan_id="inventory")
    sources = {item["source_id"]: item for item in report["artifact_source_inventory"]}

    for source_id in (
        "raw_query_textarea",
        "goal_brief_json",
        "mixed_mode_router_preview",
        "debug_last_control_prompt",
        "worker_assignment_json",
        "worker_result_review",
        "patch_proposal_json",
        "validation_result_json",
        "benchmark_report_json",
        "replay_artifacts",
        "saved_final_answer",
    ):
        assert source_id in sources

    assert sources["benchmark_report_json"]["target_frame_type"] == "benchmark_evidence"
    assert ".agent/benchmarks/benchmark_report_*.json" in sources["benchmark_report_json"]["candidate_paths"]
    assert sources["saved_final_answer"]["current_gap"] is True


def test_frame_mapping_table_covers_all_frame_types_and_priorities(tmp_path):
    report = build_mirror_tunnel_ingestion_plan(repo_path=str(tmp_path), plan_id="mapping")
    mapping = {row["frame_type"]: row for row in report["frame_mapping_plan"]}

    assert set(FRAME_TYPES) <= set(mapping)
    assert mapping["user_intent"]["priority"] == "P0"
    assert mapping["control_prompt"]["priority"] == "P0"
    assert mapping["patch_or_diff"]["required_fields"] == [
        "artifact_path",
        "changed_files",
        "patched_files",
        "generated_artifacts",
        "unexpected_mutations",
    ]
    assert "raw query textarea" in " ".join(mapping["user_intent"]["candidate_sources"]).lower()
    assert "saved answer/result artifacts" in " ".join(mapping["final_answer"]["candidate_sources"]).lower()


def test_missing_gaps_and_future_integration_points_are_explicit(tmp_path):
    report = build_mirror_tunnel_ingestion_plan(repo_path=str(tmp_path), plan_id="gaps")
    gaps = {gap["gap_id"]: gap for gap in report["missing_source_gaps"]}
    points = {point["integration_id"]: point for point in report["future_integration_points"]}

    assert "final_answer_not_consistently_saved" in gaps
    assert "worker_reply_not_mirror_friendly" in gaps
    assert "real_run_frame_emission_missing" in gaps
    assert gaps["final_answer_not_consistently_saved"]["severity"] == "high"
    assert "save_final_answer_frame" in points
    assert "emit_patch_diff_frame" in points
    assert points["emit_patch_diff_frame"]["target_frame_type"] == "patch_or_diff"
    assert points["save_final_answer_frame"]["priority"] == "P0"


def test_write_plan_artifacts(tmp_path):
    repo = tmp_path / "repo"
    result = write_mirror_tunnel_ingestion_plan(
        repo_path=str(repo),
        plan_id="write-smoke",
        created_at="2026-06-29T00:00:00Z",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == repo / ".agent" / "mirror_tunnel" / "ingestion_plan" / "mirror_tunnel_ingestion_plan.json"
    assert Path(result["md_path"]) == repo / ".agent" / "mirror_tunnel" / "ingestion_plan" / "mirror_tunnel_ingestion_plan.md"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["plan_id"] == "write-smoke"
    assert data["status"] == "partial_mapping_available"


def test_markdown_contains_required_sections(tmp_path):
    report = build_mirror_tunnel_ingestion_plan(repo_path=str(tmp_path), plan_id="md")
    markdown = render_mirror_tunnel_ingestion_markdown(report)
    low = markdown.lower()
    for section in (
        "## summary",
        "## current trace weakness",
        "## source artifact inventory",
        "## frame mapping table",
        "## missing frame gaps",
        "## proposed future integration points",
        "## safety / privacy boundaries",
        "## recommended next phase",
    ):
        assert section in low, section


def test_cli_dry_run_prints_report_and_writes_nothing(tmp_path, capsys):
    repo = tmp_path / "repo"
    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--plan-id",
            "cli-dry",
            "--created-at",
            "2026-06-29T00:00:00Z",
            "--dry-run",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["plan_id"] == "cli-dry"
    assert parsed["recommended_next_phase"] == "MIRROR.5"
    assert not (repo / ".agent" / "mirror_tunnel" / "ingestion_plan").exists()


def test_cli_writes_ingestion_plan_artifacts(tmp_path, capsys):
    repo = tmp_path / "repo"
    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--plan-id",
            "cli-write",
            "--created-at",
            "2026-06-29T00:00:00Z",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["report"]["plan_id"] == "cli-write"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()


def test_output_root_rejects_traversal(tmp_path):
    result = write_mirror_tunnel_ingestion_plan(
        repo_path=str(tmp_path / "repo"),
        output_root="../outside",
        plan_id="blocked",
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert "traversal" in result["report"]["blockers"][0]["reason"]


def test_no_forbidden_imports_or_execution_calls_in_ingestion_layers():
    module_tree = ast.parse(Path(plan.__file__).read_text(encoding="utf-8"))
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
        "cohere",
        "database",
        "docker",
        "flask",
        "google",
        "httpx",
        "numpy",
        "openai",
        "patching",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "web",
    }
    forbidden_calls = {
        "apply_patch",
        "call_model",
        "check_call",
        "check_output",
        "connect",
        "create_dream",
        "execute",
        "get_embedding",
        "invoke_mcp",
        "launch_worker",
        "open",
        "Popen",
        "post",
        "run",
        "run_benchmarks",
        "run_validation_command",
        "system",
        "urlopen",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots), imported_roots & forbidden_import_roots
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
