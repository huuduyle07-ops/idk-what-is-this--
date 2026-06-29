"""Tests for MIRROR.2 - Mirror Tunnel Derailment Score Report.

MIRROR.2 consumes a MIRROR.1 trace contract and calculates deterministic
report-only drift scores. It must never call models, embeddings, semantic APIs,
validation, benchmarks, MCP tools, workers, Docker/subprocess, Dream, Replay
janitor apply, network services, database writes, route/auth changes, or any
execution blocker.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from core import mirror_tunnel_derailment_score as score
from core.mirror_tunnel_derailment_score import (
    DIMENSION_WEIGHTS,
    SCORE_DIMENSIONS,
    VERDICTS,
    build_mirror_tunnel_derailment_score,
    load_trace_contract,
    render_mirror_tunnel_derailment_markdown,
    write_mirror_tunnel_derailment_score,
)
from scripts import create_mirror_tunnel_derailment_score as cli


def _frame(frame_type: str, excerpt: str, artifact_path: str = "") -> dict[str, Any]:
    return {
        "frame_id": f"{frame_type}-1",
        "frame_index": 0,
        "frame_type": frame_type,
        "availability": "available",
        "artifact_path": artifact_path or f".agent/{frame_type}.txt",
        "resolved_artifact_path": artifact_path or f".agent/{frame_type}.txt",
        "artifact_kind": "text",
        "excerpt": excerpt,
        "excerpt_truncated": False,
        "classification_reason": "test fixture",
    }


def _trace(frames: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    frame_types = [frame["frame_type"] for frame in frames]
    missing = [
        {
            "frame_type": ft,
            "availability": "missing",
            "reason": "missing in fixture",
            "artifact_path": "",
            "excerpt": "",
        }
        for ft in [
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
        ]
        if ft not in frame_types
    ]
    data: dict[str, Any] = {
        "report_kind": "mirror_tunnel_trace_contract",
        "trace_id": "trace-fixture",
        "created_at": "2026-06-29T00:00:00Z",
        "status": "complete_trace",
        "trust_level": "high",
        "source_run_id": "run-fixture",
        "frame_order": frame_types,
        "frames": frames,
        "missing_frames": missing,
        "available_evidence": [
            {
                "frame_type": frame["frame_type"],
                "artifact_path": frame["artifact_path"],
                "evidence_status": "available",
            }
            for frame in frames
        ],
        "missing_evidence": [
            {"frame_type": item["frame_type"], "evidence_status": "missing"}
            for item in missing
        ],
        "reusable_context": {"items": ["allowed_files", "validation_commands"], "frame_context": []},
        "excluded_context": {"items": ["secrets", ".env"]},
        "artifact_references": [],
    }
    data.update(overrides)
    return data


def _aligned_trace() -> dict[str, Any]:
    return _trace(
        [
            _frame(
                "user_intent",
                "Fix checkout total in core/checkout.py. Allowed files: core/checkout.py. "
                "Validate with python -m pytest tests/test_checkout.py -q.",
            ),
            _frame(
                "worker_assignment",
                "Worker assignment: fix checkout total. Allowed files: core/checkout.py. "
                "Validation commands: python -m pytest tests/test_checkout.py -q.",
            ),
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n@@ fixed total\n"),
            _frame(
                "validation_evidence",
                "python -m pytest tests/test_checkout.py -q PASSED",
            ),
            _frame(
                "final_answer",
                "Fixed checkout total in core/checkout.py and validated with "
                "python -m pytest tests/test_checkout.py -q.",
            ),
        ]
    )


def test_dimension_weights_and_verdicts_are_stable():
    assert SCORE_DIMENSIONS == (
        "intent_drift",
        "scope_drift",
        "evidence_loss",
        "claim_action_mismatch",
        "validation_gap",
        "confidence_inflation",
    )
    assert DIMENSION_WEIGHTS == {
        "intent_drift": 0.25,
        "scope_drift": 0.20,
        "evidence_loss": 0.20,
        "claim_action_mismatch": 0.15,
        "validation_gap": 0.10,
        "confidence_inflation": 0.10,
    }
    assert VERDICTS == (
        "aligned",
        "minor_drift",
        "moderate_drift",
        "severe_derailment",
        "insufficient_trace",
    )


def test_aligned_trace_scores_low_and_recommends_normal_review():
    report = build_mirror_tunnel_derailment_score(
        trace=_aligned_trace(),
        score_id="aligned",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["score_id"] == "aligned"
    assert report["verdict"] == "aligned"
    assert report["recommended_next_action"] == "continue_normal_review"
    assert report["overall_derailment_score"] <= 0.19
    assert report["dimension_scores"]["validation_gap"]["score"] == 0.0
    assert report["dimension_scores"]["claim_action_mismatch"]["score"] == 0.0
    assert report["guardrails"]["model_call_performed"] is False
    assert report["guardrails"]["validation_run"] is False
    assert report["guardrails"]["execution_blocking_performed"] is False
    assert report["recommended_next_phase"] == "MIRROR.3"


def test_missing_user_intent_is_insufficient_trace():
    trace = _trace(
        [
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n"),
            _frame("final_answer", "Fixed and validated."),
        ],
        status="partial_trace",
        trust_level="medium",
    )

    report = build_mirror_tunnel_derailment_score(
        trace=trace,
        score_id="insufficient",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["verdict"] == "insufficient_trace"
    assert report["overall_derailment_score"] is None
    assert report["recommended_next_action"] == "collect_more_trace_artifacts"
    assert "missing_user_intent_frame" in report["insufficient_reasons"]


def test_validation_claim_without_evidence_raises_gap_and_mismatch():
    trace = _trace(
        [
            _frame("user_intent", "Fix checkout total in core/checkout.py."),
            _frame("worker_assignment", "Allowed files: core/checkout.py."),
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n"),
            _frame("final_answer", "The checkout bug is fixed, complete, and validation passed."),
        ],
        status="partial_trace",
        trust_level="medium",
    )

    report = build_mirror_tunnel_derailment_score(
        trace=trace,
        score_id="validation-gap",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["verdict"] in {"moderate_drift", "severe_derailment"}
    assert report["dimension_scores"]["validation_gap"]["score"] >= 0.8
    assert report["dimension_scores"]["claim_action_mismatch"]["score"] >= 0.5
    assert any(point["dimension"] == "validation_gap" for point in report["detected_drift_points"])
    assert report["recommended_next_action"] in {
        "human_review_recommended",
        "do_not_trust_result_without_replay",
    }


def test_out_of_scope_patch_path_raises_scope_drift_and_evidence_loss():
    trace = _trace(
        [
            _frame(
                "user_intent",
                "Fix checkout total only. Allowed files: core/checkout.py. "
                "Do not touch web/app.py.",
            ),
            _frame("worker_assignment", "Allowed files: core/checkout.py. Forbidden files: web/app.py."),
            _frame(
                "patch_or_diff",
                "--- a/core/checkout.py\n+++ b/core/checkout.py\n--- a/web/app.py\n+++ b/web/app.py\n",
            ),
            _frame("validation_evidence", "pytest passed"),
            _frame("final_answer", "Fixed checkout."),
        ]
    )

    report = build_mirror_tunnel_derailment_score(
        trace=trace,
        score_id="scope",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["dimension_scores"]["scope_drift"]["score"] >= 0.5
    assert report["dimension_scores"]["evidence_loss"]["score"] >= 0.2
    assert any("web/app.py" in point["evidence"] for point in report["detected_drift_points"])


def test_benchmark_failure_ignored_by_final_answer_raises_mismatch():
    trace = _trace(
        [
            _frame("user_intent", "Fix checkout benchmark failure."),
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n"),
            _frame("benchmark_evidence", "benchmark report: FAILED checkout_case"),
            _frame("final_answer", "Everything passed and the fix is complete."),
        ]
    )

    report = build_mirror_tunnel_derailment_score(
        trace=trace,
        score_id="bench-mismatch",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["dimension_scores"]["claim_action_mismatch"]["score"] >= 0.6
    assert any(check["status"] == "mismatch" for check in report["claim_action_checks"])


def test_many_unknown_artifacts_raise_evidence_loss():
    trace = _trace(
        [
            _frame("user_intent", "Fix checkout total."),
            _frame("unknown_artifact", "Loose debug note."),
            _frame("unknown_artifact", "Another loose note."),
            _frame("unknown_artifact", "Third loose note."),
            _frame("final_answer", "I looked into it."),
        ],
        status="partial_trace",
        trust_level="low",
    )

    report = build_mirror_tunnel_derailment_score(
        trace=trace,
        score_id="unknowns",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["dimension_scores"]["evidence_loss"]["score"] >= 0.4
    assert report["frame_coverage"]["unknown_artifact_count"] == 3


def test_write_score_report_reads_trace_and_writes_json_markdown(tmp_path):
    repo = tmp_path / "repo"
    trace_path = repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(_aligned_trace(), indent=2), encoding="utf-8")

    result = write_mirror_tunnel_derailment_score(
        trace_path=str(trace_path),
        repo_path=str(repo),
        score_id="write-smoke",
        created_at="2026-06-29T00:00:00Z",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == repo / ".agent" / "mirror_tunnel" / "derailment_score" / "mirror_tunnel_derailment_score.json"
    assert Path(result["md_path"]) == repo / ".agent" / "mirror_tunnel" / "derailment_score" / "mirror_tunnel_derailment_score.md"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["score_id"] == "write-smoke"
    assert data["trace_path"] == str(trace_path)


def test_trace_loader_refuses_secret_env_paths(tmp_path):
    secret_path = tmp_path / ".env"
    secret_path.write_text(json.dumps(_aligned_trace()), encoding="utf-8")

    try:
        load_trace_contract(secret_path)
    except ValueError as exc:
        assert "secret/env" in str(exc)
    else:
        raise AssertionError("expected secret/env trace path refusal")


def test_markdown_contains_required_report_sections():
    report = build_mirror_tunnel_derailment_score(
        trace=_aligned_trace(),
        score_id="md",
        created_at="2026-06-29T00:00:00Z",
    )
    markdown = render_mirror_tunnel_derailment_markdown(report)
    low = markdown.lower()
    for section in (
        "## summary",
        "## overall derailment score",
        "## dimension scores",
        "## frame coverage",
        "## detected drift points",
        "## evidence used",
        "## missing evidence",
        "## claim / action checks",
        "## validation gap checks",
        "## recommended next action",
        "## boundaries / guardrails",
    ):
        assert section in low, section


def test_cli_dry_run_prints_report_and_writes_nothing(tmp_path, capsys):
    repo = tmp_path / "repo"
    trace_path = repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(_aligned_trace(), indent=2), encoding="utf-8")

    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--trace",
            str(trace_path),
            "--score-id",
            "cli-dry",
            "--created-at",
            "2026-06-29T00:00:00Z",
            "--dry-run",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["score_id"] == "cli-dry"
    assert parsed["verdict"] == "aligned"
    assert not (repo / ".agent" / "mirror_tunnel" / "derailment_score").exists()


def test_cli_writes_score_artifacts(tmp_path, capsys):
    repo = tmp_path / "repo"
    trace_path = repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(_aligned_trace(), indent=2), encoding="utf-8")

    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--trace",
            str(trace_path),
            "--score-id",
            "cli-write",
            "--created-at",
            "2026-06-29T00:00:00Z",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["report"]["score_id"] == "cli-write"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()


def test_no_forbidden_imports_or_execution_calls_in_derailment_layers():
    module_tree = ast.parse(Path(score.__file__).read_text(encoding="utf-8"))
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
