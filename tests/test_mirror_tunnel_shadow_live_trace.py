"""Tests for MIRROR.7 - Shadow Live Trace Writer.

MIRROR.7 adds default-off, shadow-only trace writing at a single existing run
boundary. It must never score, check claims, call models, run validation or
benchmarks, apply patches, invoke tools, or change caller return shapes.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.mirror_tunnel_shadow_live_trace import (
    JSON_NAME,
    MD_NAME,
    RECOMMENDED_NEXT_PHASE,
    STATUS_BLOCKED,
    STATUS_DISABLED,
    STATUS_LIVE_TRACE_WRITTEN,
    STATUS_SKIPPED_NO_RUN_ID,
    build_shadow_live_trace,
    is_shadow_trace_enabled,
    maybe_write_shadow_live_trace,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = PROJECT_ROOT / "core" / "mirror_tunnel_shadow_live_trace.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def test_shadow_trace_flag_is_default_off(monkeypatch):
    monkeypatch.delenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", raising=False)
    assert is_shadow_trace_enabled() is False

    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "false")
    assert is_shadow_trace_enabled() is False

    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "true")
    assert is_shadow_trace_enabled() is True


def test_disabled_mode_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "false")

    result = maybe_write_shadow_live_trace(
        repo_path=tmp_path,
        run_id="run-1",
        user_intent="Fix the bug.",
        final_answer="Done.",
    )

    assert result["enabled"] is False
    assert result["status"] == STATUS_DISABLED
    assert result["artifact_paths"] == {}
    assert not (tmp_path / ".agent" / "mirror_tunnel" / "live_traces").exists()


def test_enabled_mode_writes_trace_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "true")

    result = maybe_write_shadow_live_trace(
        repo_path=tmp_path,
        run_id="run-42",
        user_intent="Repair the checkout total.",
        control_prompt={"intent": "repair", "target": "checkout.py"},
        patch_or_diff={"patch": [{"file": "checkout.py", "op": "replace"}]},
        validation_evidence="pytest passed",
        final_answer="Updated checkout total handling.",
    )

    assert result["enabled"] is True
    assert result["status"] == STATUS_LIVE_TRACE_WRITTEN
    assert result["recommended_next_phase"] == RECOMMENDED_NEXT_PHASE == "MIRROR.8"

    json_path = Path(result["artifact_paths"]["json"])
    md_path = Path(result["artifact_paths"]["markdown"])
    assert json_path == tmp_path / ".agent" / "mirror_tunnel" / "live_traces" / "run-42" / JSON_NAME
    assert md_path == tmp_path / ".agent" / "mirror_tunnel" / "live_traces" / "run-42" / MD_NAME
    assert json_path.is_file()
    assert md_path.is_file()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["status"] == STATUS_LIVE_TRACE_WRITTEN
    assert data["run_id"] == "run-42"
    assert {frame["frame_type"] for frame in data["frames"] if frame["availability"] == "available"} >= {
        "user_intent",
        "control_prompt",
        "patch_or_diff",
        "validation_evidence",
        "final_answer",
    }
    assert any(item["frame_type"] == "benchmark_evidence" for item in data["missing_evidence"])
    assert "Shadow Live Trace" in md_path.read_text(encoding="utf-8")


def test_enabled_missing_run_id_skips_safely(tmp_path, monkeypatch):
    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "true")

    result = maybe_write_shadow_live_trace(
        repo_path=tmp_path,
        run_id="",
        user_intent="Fix the bug.",
    )

    assert result["status"] == STATUS_SKIPPED_NO_RUN_ID
    assert result["artifact_paths"] == {}
    assert not (tmp_path / ".agent" / "mirror_tunnel" / "live_traces").exists()


def test_bad_run_id_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "true")

    result = maybe_write_shadow_live_trace(
        repo_path=tmp_path,
        run_id="../escape",
        user_intent="Fix the bug.",
    )

    assert result["status"] == STATUS_BLOCKED
    assert any("run_id" in reason for reason in result["blocked_reasons"])
    assert result["artifact_paths"] == {}
    assert not (tmp_path / ".agent" / "mirror_tunnel" / "live_traces").exists()


def test_secret_fields_are_blocked_and_not_echoed(tmp_path, monkeypatch):
    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "true")

    result = maybe_write_shadow_live_trace(
        repo_path=tmp_path,
        run_id="run-secret",
        user_intent="Inspect credentials.",
        patch_or_diff={"api_key": "super-secret-value", "file": "app.py"},
    )

    encoded = json.dumps(result, sort_keys=True)
    assert result["status"] == STATUS_BLOCKED
    assert "super-secret-value" not in encoded
    assert result["artifact_paths"] == {}


def test_long_text_is_capped():
    trace = build_shadow_live_trace(
        run_id="run-long",
        user_intent="x" * 500,
        final_answer="done",
        created_at="2026-06-30T00:00:00+00:00",
        excerpt_limit=80,
    )

    frame = next(item for item in trace["frames"] if item["frame_type"] == "user_intent")
    assert frame["excerpt_truncated"] is True
    assert len(frame["excerpt"]) <= 80


def test_writer_failures_do_not_break_caller_result(tmp_path, monkeypatch):
    import core.mirror_tunnel_shadow_live_trace as shadow

    caller_result = {"answer": "unchanged", "validation": ""}

    def boom(**_kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "true")
    monkeypatch.setattr(shadow, "write_shadow_live_trace", boom)

    trace_result = shadow.maybe_write_shadow_live_trace(
        repo_path=tmp_path,
        run_id="run-fail",
        user_intent="Fix",
        final_answer="Done",
    )

    assert caller_result == {"answer": "unchanged", "validation": ""}
    assert trace_result["status"] == STATUS_BLOCKED
    assert any("trace write failed" in reason for reason in trace_result["blocked_reasons"])


def test_live_writer_has_no_scoring_claim_diff_or_execution_imports():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    call_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    assert "core.mirror_tunnel_derailment_score" not in imported_modules
    assert "core.mirror_tunnel_claim_diff_check" not in imported_modules

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
    assert sorted({name.split(".", 1)[0] for name in imported_modules} & forbidden_import_roots) == []

    forbidden_calls = {
        "apply_patch",
        "build_mirror_tunnel_claim_diff_check",
        "build_mirror_tunnel_derailment_score",
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
    assert sorted(call_names & forbidden_calls) == []


def test_web_boundary_preserves_result_shape_when_disabled(tmp_path, monkeypatch):
    from web.runner import _maybe_write_web_shadow_live_trace

    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_TRACE_ENABLED", "false")
    result = {
        "answer": "Done.",
        "context": "{}",
        "graph": "{}",
        "state": "",
        "patch": "",
        "validation": "",
    }
    before = copy.deepcopy(result)

    returned = _maybe_write_web_shadow_live_trace(
        result=result,
        query="Fix checkout.",
        repo_path=str(tmp_path),
        session_id="run-web",
        control_result={"intent": "repair"},
        patch_or_diff={},
        validation_evidence="",
        final_answer="Done.",
    )

    assert returned is result
    assert result == before
    assert not (tmp_path / ".agent" / "mirror_tunnel" / "live_traces").exists()


def test_registry_and_phase_picker_recommend_mirror8():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["MIRROR.7"]["status"] == "complete"
    assert by_id["MIRROR.7"]["prerequisites"] == ["MIRROR.CLOSE"]
    assert by_id["MIRROR.8"]["status"] == "complete"
    assert by_id["MIRROR.8"]["prerequisites"] == ["MIRROR.7"]
    assert by_id["MIRROR.9"]["status"] == "proposed"
    assert by_id["MIRROR.9"]["prerequisites"] == ["MIRROR.8"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="r",
        created_at="2026-06-30T00:00:00+00:00",
    )
    assert report["top_recommendation"]["phase_id"] == "MIRROR.9"
