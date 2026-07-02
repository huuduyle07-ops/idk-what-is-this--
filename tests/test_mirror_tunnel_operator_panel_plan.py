"""Tests for MIRROR.9 - Live Trace Operator Report Panel Plan.

MIRROR.9 is report-only UX planning: it defines how MIRROR.7 live traces and
MIRROR.8 scoring previews should be shown to the operator without becoming an
automatic judge, blocker, trust authority, or UI implementation.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.mirror_tunnel_operator_panel_plan import (
    JSON_NAME,
    MD_NAME,
    PANEL_PLAN_READY,
    STATUS_BLOCKED,
    build_mirror_tunnel_operator_panel_plan,
    write_mirror_tunnel_operator_panel_plan,
)
import scripts.create_mirror_tunnel_operator_panel_plan as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = PROJECT_ROOT / "core" / "mirror_tunnel_operator_panel_plan.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_mirror_tunnel_operator_panel_plan.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _preview(status: str = "preview_with_warnings") -> dict:
    return {
        "report_kind": "mirror_tunnel_live_trace_scoring_preview",
        "preview_id": "preview-1",
        "status": status,
        "trace_id": "trace-1",
        "run_id": "run-1",
        "frame_coverage": {
            "available_frame_count": 5,
            "missing_evidence_count": 2,
            "available_frame_types": ["user_intent", "patch_or_diff", "validation_evidence", "final_answer"],
        },
        "derailment_score_preview": {
            "verdict": "moderate_drift",
            "overall_derailment_score": 0.42,
            "dimension_scores": {"intent_drift": {"score": 0.1}, "evidence_loss": {"score": 0.5}},
        },
        "claim_vs_diff_preview": {
            "overall_claim_support": "partially_supported",
            "mismatch_count": 1,
            "unsupported_claim_count": 2,
        },
        "missing_evidence": [
            {"source": "trace", "frame_type": "benchmark_evidence", "reason": "not captured"},
            {"source": "trace", "frame_type": "replay_evidence", "reason": "not captured"},
        ],
        "warnings": [
            "live trace has missing evidence frames",
            "MIRROR.2 verdict is moderate_drift",
            "claim mismatches detected",
            "unsupported claims detected",
        ],
        "artifact_paths": {"json": "preview.json", "markdown": "preview.md"},
        "recommended_next_action": "improve_live_trace_frame_capture",
    }


def _trace() -> dict:
    return {
        "report_kind": "mirror_tunnel_shadow_live_trace",
        "enabled": True,
        "status": "live_trace_written",
        "trace_id": "trace-1",
        "run_id": "run-1",
        "frames": [
            {"frame_type": "user_intent", "availability": "available", "excerpt": "Fix checkout total."},
            {"frame_type": "patch_or_diff", "availability": "available", "excerpt": "diff --git"},
            {"frame_type": "final_answer", "availability": "available", "excerpt": "Done."},
        ],
        "missing_evidence": [{"frame_type": "benchmark_evidence", "reason": "not captured"}],
        "artifact_paths": {"json": "trace.json", "markdown": "trace.md"},
    }


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_build_plan_defines_advisory_operator_panel_contract():
    report = build_mirror_tunnel_operator_panel_plan(
        preview=_preview(),
        trace=_trace(),
        preview_path="preview.json",
        trace_path="trace.json",
        created_at="2026-06-30T00:00:00+00:00",
    )

    assert report["report_kind"] == "mirror_tunnel_operator_panel_plan"
    assert report["status"] == PANEL_PLAN_READY
    assert report["recommended_next_phase"] == "MIRROR.10"
    assert "Evidence Cards" in report["panel_placement"]["primary_recommendation"]
    assert "primary submit" not in report["panel_placement"]["primary_recommendation"].lower()
    assert report["panel_placement"]["never_place_beside_apply_as_gate"] is True
    assert report["non_blocking_policy"]["is_approval_gate"] is False
    assert report["non_blocking_policy"]["may_block_run"] is False
    assert report["non_blocking_policy"]["may_hide_apply_button"] is False

    visible = report["visible_fields"]
    assert visible["trace_status"] == "live_trace_written"
    assert visible["frame_coverage"]["available_frame_count"] == 5
    assert visible["derailment_verdict"] == "moderate_drift"
    assert visible["overall_score"] == 0.42
    assert visible["claim_support_verdict"] == "partially_supported"
    assert visible["missing_evidence_count"] == 2
    assert len(visible["top_warnings"]) == 3
    assert visible["recommended_next_action"] == "improve_live_trace_frame_capture"


def test_plan_contains_required_warning_language_and_badge_rules():
    report = build_mirror_tunnel_operator_panel_plan(preview=_preview(status="insufficient_trace"))
    warning_text = "\n".join(report["warning_language"])
    assert "advisory evidence, not an approval gate" in warning_text
    assert "low derailment score does not prove correctness" in warning_text
    assert "high derailment score means review the evidence" in warning_text
    assert "Missing evidence should be shown plainly." in warning_text

    badges = {rule["status"]: rule for rule in report["status_badge_rules"]}
    assert badges["insufficient_trace"]["color"] == "gray"
    assert badges["insufficient_trace"]["label"] == "Needs more evidence"
    assert badges["preview_with_warnings"]["color"] == "amber"
    assert badges["preview_ready"]["label"] == "Evidence available"
    assert badges["blocked"]["color"] == "red"
    assert all("safe" not in rule["label"].lower() for rule in badges.values())
    assert all("approved" not in rule["label"].lower() for rule in badges.values())


def test_plan_defines_operator_actions_and_forbidden_ui_actions():
    report = build_mirror_tunnel_operator_panel_plan(preview=_preview(), trace=_trace())
    action_ids = {item["action_id"] for item in report["operator_actions"]}
    assert {
        "open_trace_artifact",
        "open_scoring_preview",
        "copy_mirror_review_summary",
        "rerun_preview_manually",
        "mark_reviewed_manually_future",
    } <= action_ids

    forbidden = {item["action_id"] for item in report["forbidden_ui_actions"]}
    assert {
        "auto_block_run",
        "auto_apply_patch",
        "auto_reject_patch",
        "auto_trust_result",
        "auto_launch_replay_validation_benchmark",
        "auto_call_model",
        "hide_apply_button_based_on_mirror_score",
        "change_prompt_or_routing_based_on_mirror_score",
    } <= forbidden


def test_collapsed_debug_fields_and_evidence_rules_are_complete():
    report = build_mirror_tunnel_operator_panel_plan(preview=_preview(), trace=_trace())
    collapsed_ids = {item["field_id"] for item in report["collapsed_debug_fields"]}
    assert {
        "full_frame_list",
        "dimension_scores",
        "claim_list",
        "mismatches",
        "unsupported_claims",
        "artifact_paths",
        "raw_json_links",
    } <= collapsed_ids
    rules = "\n".join(rule["rule"] for rule in report["evidence_display_rules"])
    assert "plainly" in rules.lower()
    assert "cap" in rules.lower()
    assert "raw json" in rules.lower()


def test_write_plan_artifacts_from_optional_preview_and_trace(tmp_path):
    preview_path = _write_json(tmp_path / "preview.json", _preview())
    trace_path = _write_json(tmp_path / "trace.json", _trace())

    result = write_mirror_tunnel_operator_panel_plan(
        repo_path=tmp_path,
        preview_path=str(preview_path),
        trace_path=str(trace_path),
        created_at="2026-06-30T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["status"] == PANEL_PLAN_READY
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path == tmp_path / ".agent" / "mirror_tunnel" / "operator_panel_plan" / JSON_NAME
    assert md_path == tmp_path / ".agent" / "mirror_tunnel" / "operator_panel_plan" / MD_NAME
    assert json_path.is_file()
    assert md_path.is_file()
    written = json.loads(json_path.read_text(encoding="utf-8"))
    assert written["input_summary"]["preview"]["status"] == "preview_with_warnings"
    assert "Mirror Tunnel Operator Report Panel Plan" in md_path.read_text(encoding="utf-8")


def test_no_input_still_writes_generic_panel_plan(tmp_path):
    result = write_mirror_tunnel_operator_panel_plan(
        repo_path=tmp_path,
        created_at="2026-06-30T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["status"] == PANEL_PLAN_READY
    assert result["report"]["input_summary"]["preview"]["available"] is False
    assert result["report"]["input_summary"]["trace"]["available"] is False


def test_unsafe_preview_path_blocks_and_writes_nothing(tmp_path):
    result = write_mirror_tunnel_operator_panel_plan(repo_path=tmp_path, preview_path="../secret.json")

    assert result["ok"] is False
    assert result["status"] == STATUS_BLOCKED
    assert result["json_path"] == ""
    assert any("traversal" in blocker["reason"] for blocker in result["report"]["blockers"])
    assert not (tmp_path / ".agent" / "mirror_tunnel" / "operator_panel_plan" / JSON_NAME).exists()


def test_cli_json_output_writes_plan(tmp_path, capsys):
    preview_path = _write_json(tmp_path / "preview.json", _preview())

    code = script.main(
        [
            "--repo-path",
            str(tmp_path),
            "--preview",
            str(preview_path),
            "--created-at",
            "2026-06-30T00:00:00+00:00",
            "--json",
        ]
    )

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == PANEL_PLAN_READY
    assert Path(printed["json_path"]).is_file()
    assert printed["report"]["recommended_next_phase"] == "MIRROR.10"


def test_source_has_no_runtime_or_authority_expanding_primitives():
    core_src = CORE_PATH.read_text(encoding="utf-8")
    script_src = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(core_src + "\n" + script_src)
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    forbidden_import_roots = {
        "agents",
        "benchmarks",
        "database",
        "docker",
        "flask",
        "google",
        "httpx",
        "mcp",
        "openai",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    assert sorted({item.split(".", 1)[0] for item in imports} & forbidden_import_roots) == []
    forbidden_calls = {
        "apply_patch",
        "call_model",
        "check_call",
        "check_output",
        "connect",
        "create_dream",
        "invoke_mcp",
        "launch_worker",
        "Popen",
        "post",
        "request",
        "run_benchmarks",
        "run_safe_validation_command",
        "run_validation_command",
        "system",
        "urlopen",
    }
    assert sorted(calls & forbidden_calls) == []


def test_registry_picker_recommends_cmd_n4_after_operator_panel_plan():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["MIRROR.9"]["status"] == "complete"
    assert by_id["MIRROR.9"]["title"] == "Live Trace Operator Report Panel Plan"
    assert by_id["MIRROR.9"]["prerequisites"] == ["MIRROR.8"]
    assert by_id["MIRROR.10"]["status"] == "complete"
    assert by_id["MIRROR.10"]["prerequisites"] == ["MIRROR.9"]
    assert by_id["MIRROR.11"]["status"] == "complete"
    assert by_id["MIRROR.11"]["prerequisites"] == ["MIRROR.10"]
    assert by_id["MIRROR.12"]["status"] == "complete"
    assert by_id["MIRROR.12"]["prerequisites"] == ["MIRROR.11"]
    assert by_id["MIRROR.CLOSE3"]["status"] == "complete"
    assert by_id["MIRROR.CLOSE3"]["prerequisites"] == ["MIRROR.12"]
    assert by_id["MIRROR.13"]["status"] == "proposed"
    assert by_id["MIRROR.13"]["prerequisites"] == ["MIRROR.CLOSE3"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="r",
        created_at="2026-06-30T00:00:00+00:00",
    )
    assert report["top_recommendation"]["phase_id"] == "CMD.N5"
