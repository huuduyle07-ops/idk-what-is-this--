"""Tests for MIRROR.8 - Live Trace Scoring Preview.

MIRROR.8 is post-run and report-only: it reads an existing MIRROR.7 live trace
artifact, derives MIRROR.2/MIRROR.3 evidence through pure builders, reuses
MIRROR.6-style aggregation, and writes a separate preview pack.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.mirror_tunnel_live_trace_scoring_preview import (
    JSON_NAME,
    MD_NAME,
    PREVIEW_READY,
    PREVIEW_WITH_WARNINGS,
    STATUS_BLOCKED,
    STATUS_INSUFFICIENT_TRACE,
    build_mirror_tunnel_live_trace_scoring_preview,
    write_mirror_tunnel_live_trace_scoring_preview,
)
import scripts.create_mirror_tunnel_live_trace_scoring_preview as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = PROJECT_ROOT / "core" / "mirror_tunnel_live_trace_scoring_preview.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_mirror_tunnel_live_trace_scoring_preview.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _frame(frame_type: str, excerpt: str) -> dict:
    return {
        "frame_id": frame_type,
        "frame_index": 0,
        "frame_type": frame_type,
        "availability": "available",
        "artifact_path": "",
        "resolved_artifact_path": "",
        "artifact_kind": "in_memory",
        "excerpt": excerpt,
        "excerpt_truncated": False,
        "classification_reason": "test frame",
    }


def _live_trace(*, complete: bool = True, missing: bool = False, insufficient: bool = False) -> dict:
    frames = []
    if not insufficient:
        frames.extend(
            [
                _frame("user_intent", "Fix checkout total in checkout.py and validate it."),
                _frame("control_prompt", "Target checkout.py. Keep the fix narrow."),
                _frame("patch_or_diff", "diff --git a/checkout.py b/checkout.py\n+++ b/checkout.py\n+total = subtotal + tax"),
                _frame("validation_evidence", "pytest passed with 0 errors."),
                _frame("final_answer", "Updated checkout.py and validation passed."),
            ]
        )
        if complete:
            frames.extend(
                [
                    _frame("benchmark_evidence", "benchmark check passed"),
                    _frame("replay_evidence", "replay evidence available"),
                ]
            )
    else:
        frames.append(_frame("final_answer", "Done."))
    trace = {
        "report_kind": "mirror_tunnel_shadow_live_trace",
        "enabled": True,
        "status": "live_trace_written",
        "trace_id": "mirror-live-test",
        "run_id": "run-test",
        "created_at": "2026-06-30T00:00:00+00:00",
        "frames": frames,
        "missing_evidence": [],
        "blocked_reasons": [],
        "artifact_paths": {},
        "boundaries": ["MIRROR.7 is shadow-only."],
        "recommended_next_phase": "MIRROR.8",
        "guardrails": {"report_only": True, "model_call_performed": False},
    }
    if missing:
        trace["missing_evidence"] = [
            {"frame_type": "benchmark_evidence", "reason": "source value was not available"},
            {"frame_type": "replay_evidence", "reason": "source value was not available"},
        ]
    return trace


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_valid_live_trace_writes_preview(tmp_path):
    trace_path = _write_json(tmp_path / ".agent" / "mirror_tunnel" / "live_traces" / "run-1" / "mirror_tunnel_trace_contract.json", _live_trace())

    result = write_mirror_tunnel_live_trace_scoring_preview(
        repo_path=tmp_path,
        trace_path=str(trace_path),
        preview_id="preview-1",
        created_at="2026-06-30T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["status"] in {PREVIEW_READY, PREVIEW_WITH_WARNINGS}
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path.name == JSON_NAME
    assert md_path.name == MD_NAME
    assert json_path.parent == tmp_path / ".agent" / "mirror_tunnel" / "live_trace_scoring_preview" / "preview-1"
    assert json_path.is_file()
    assert md_path.is_file()

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["report_kind"] == "mirror_tunnel_live_trace_scoring_preview"
    assert report["preview_id"] == "preview-1"
    assert report["trace_id"] == "mirror-live-test"
    assert report["derailment_score_preview"]["verdict"] != ""
    assert report["claim_vs_diff_preview"]["overall_claim_support"] != ""
    assert report["combined_review_verdict"]["combined_verdict"] != ""
    assert report["recommended_next_phase"] == "MIRROR.9"
    assert "Live Trace Scoring Preview" in md_path.read_text(encoding="utf-8")


def test_missing_frames_warns(tmp_path):
    trace_path = _write_json(tmp_path / "trace.json", _live_trace(complete=False, missing=True))

    result = write_mirror_tunnel_live_trace_scoring_preview(
        repo_path=tmp_path,
        trace_path=str(trace_path),
        preview_id="warn",
        created_at="2026-06-30T00:00:00+00:00",
    )

    report = result["report"]
    assert report["status"] == PREVIEW_WITH_WARNINGS
    assert any("missing" in warning.lower() for warning in report["warnings"])
    assert report["recommended_next_action"] == "improve_live_trace_frame_capture"


def test_insufficient_trace_is_honest(tmp_path):
    trace_path = _write_json(tmp_path / "trace.json", _live_trace(insufficient=True))

    result = write_mirror_tunnel_live_trace_scoring_preview(
        repo_path=tmp_path,
        trace_path=str(trace_path),
        preview_id="thin",
        created_at="2026-06-30T00:00:00+00:00",
    )

    assert result["status"] == STATUS_INSUFFICIENT_TRACE
    assert result["report"]["recommended_next_action"] == "collect_richer_live_trace_frames"
    assert result["report"]["derailment_score_preview"]["verdict"] == "insufficient_trace"


def test_unsafe_trace_path_blocks(tmp_path):
    result = write_mirror_tunnel_live_trace_scoring_preview(
        repo_path=tmp_path,
        trace_path="../outside.json",
        preview_id="bad",
    )

    assert result["ok"] is False
    assert result["status"] == STATUS_BLOCKED
    assert result["json_path"] == ""
    assert any("traversal" in blocker["reason"] for blocker in result["report"]["blockers"])


def test_malformed_trace_blocks(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text("{not-json", encoding="utf-8")

    result = write_mirror_tunnel_live_trace_scoring_preview(
        repo_path=tmp_path,
        trace_path=str(trace_path),
        preview_id="bad-json",
    )

    assert result["status"] == STATUS_BLOCKED
    assert any("malformed" in blocker["reason"] or "unreadable" in blocker["reason"] for blocker in result["report"]["blockers"])


def test_preview_never_writes_into_live_trace_dir(tmp_path):
    live_dir = tmp_path / ".agent" / "mirror_tunnel" / "live_traces" / "run-2"
    trace_path = _write_json(live_dir / "mirror_tunnel_trace_contract.json", _live_trace())

    result = write_mirror_tunnel_live_trace_scoring_preview(
        repo_path=tmp_path,
        trace_path=str(trace_path),
        preview_id="separate",
    )

    assert result["status"] != STATUS_BLOCKED
    out = Path(result["json_path"]).resolve()
    assert live_dir.resolve() not in [out, *out.parents]
    assert out.parent.name == "separate"


def test_build_accepts_mirror1_compatible_trace():
    trace = _live_trace()
    trace["report_kind"] = "mirror_tunnel_trace_contract"
    trace["status"] = "partial_trace"
    report = build_mirror_tunnel_live_trace_scoring_preview(
        trace=trace,
        trace_path="trace.json",
        preview_id="compat",
        created_at="2026-06-30T00:00:00+00:00",
    )
    assert report["status"] in {PREVIEW_READY, PREVIEW_WITH_WARNINGS}
    assert report["live_trace_input"]["trace_compatibility"] == "mirror1_compatible"


def test_cli_writes_json(tmp_path, capsys):
    trace_path = _write_json(tmp_path / "trace.json", _live_trace())

    code = script.main(
        [
            "--repo-path",
            str(tmp_path),
            "--trace",
            str(trace_path),
            "--preview-id",
            "cli",
            "--created-at",
            "2026-06-30T00:00:00+00:00",
            "--json",
        ]
    )

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] in {PREVIEW_READY, PREVIEW_WITH_WARNINGS}
    assert Path(printed["json_path"]).is_file()


def test_source_uses_core_builders_not_cli_or_live_writer():
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

    assert "core.mirror_tunnel_derailment_score" in imports
    assert "core.mirror_tunnel_claim_diff_check" in imports
    assert "core.mirror_tunnel_manual_review_pipeline" in imports
    assert "core.mirror_tunnel_shadow_live_trace" not in imports
    assert "maybe_write_shadow_live_trace" not in calls
    assert "write_shadow_live_trace" not in calls

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
    assert "scripts.create_mirror_tunnel_derailment_score" not in core_src
    assert "scripts.create_mirror_tunnel_claim_diff_check" not in core_src


def test_registry_picker_recommends_cmd_n2_after_live_trace_chain():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["MIRROR.8"]["status"] == "complete"
    assert by_id["MIRROR.8"]["title"] == "Live Trace Scoring Preview"
    assert by_id["MIRROR.8"]["prerequisites"] == ["MIRROR.7"]
    assert by_id["MIRROR.9"]["status"] == "complete"
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
    assert report["top_recommendation"]["phase_id"] == "CMD.N2"
