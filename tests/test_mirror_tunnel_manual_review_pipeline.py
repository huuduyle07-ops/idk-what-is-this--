"""Tests for MIRROR.6 - Manual Trace Score Pipeline.

MIRROR.6 reads a manually assembled MIRROR.5/MIRROR.1 trace, derives or loads
MIRROR.2 and MIRROR.3 reports, and writes one combined manual review pack. It is
report-only and must never shell out to CLIs, call models, run validation or
benchmarks, invoke workers/MCP/Docker/subprocess, or change route/auth behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from core import mirror_tunnel_manual_review_pipeline as pipeline
from core.mirror_tunnel_manual_review_pipeline import (
    RECOMMENDED_NEXT_ACTIONS,
    REVIEW_VERDICTS,
    build_mirror_tunnel_manual_review,
    render_mirror_tunnel_manual_review_markdown,
    write_mirror_tunnel_manual_review,
)
from core.mirror_tunnel_manual_trace_assembler import build_manual_mirror_tunnel_trace
from scripts import create_mirror_tunnel_manual_review as cli


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    return _write(path, json.dumps(data, indent=2))


def _manual_trace(tmp_path: Path, *, trace_id: str = "trace-1") -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix checkout total.")
    patch = _write_json(repo / ".agent" / "patches" / "patch.json", {"changed_files": ["core/checkout.py"]})
    validation = _write_json(repo / ".agent" / "validation" / "validation.json", {"status": "passed"})
    final = _write(repo / ".agent" / "answers" / "final_answer.md", "Fixed core/checkout.py. Validation passed.")
    return build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={
            "user_intent_file": str(intent.relative_to(repo)),
            "patch_json": str(patch.relative_to(repo)),
            "validation_json": str(validation.relative_to(repo)),
            "final_answer_file": str(final.relative_to(repo)),
        },
        trace_id=trace_id,
        created_at="2026-06-30T00:00:00Z",
    )


def test_constants_are_stable():
    assert REVIEW_VERDICTS == (
        "trustworthy_trace",
        "review_recommended",
        "do_not_trust_without_more_evidence",
        "insufficient_trace",
        "blocked",
    )
    assert RECOMMENDED_NEXT_ACTIONS == {
        "trustworthy_trace": "continue_normal_review",
        "review_recommended": "human_review_recommended",
        "do_not_trust_without_more_evidence": "collect_evidence_or_replay",
        "insufficient_trace": "assemble_better_manual_trace",
        "blocked": "fix_unsafe_or_missing_artifact",
    }


def test_build_pipeline_derives_score_and_claim_diff_from_trace(tmp_path):
    trace = _manual_trace(tmp_path)

    report = build_mirror_tunnel_manual_review(
        trace=trace,
        trace_path=".agent/mirror_tunnel/manual_trace/trace-1/mirror_tunnel_trace_contract.json",
        review_id="review-derived",
        created_at="2026-06-30T00:00:00Z",
    )

    assert report["report_kind"] == "mirror_tunnel_manual_review"
    assert report["review_id"] == "review-derived"
    assert report["trace_id"] == "trace-1"
    assert report["trace_status"] == "complete_trace"
    assert report["score_source"] == "derived"
    assert report["claim_diff_source"] == "derived"
    assert report["derailment_score_summary"]["verdict"] in {"aligned", "minor_drift", "moderate_drift", "severe_derailment"}
    assert report["claim_diff_summary"]["overall_claim_support"] in {
        "supported",
        "partially_supported",
        "unsupported",
        "contradicted",
        "insufficient_evidence",
    }
    assert report["frame_coverage"]["has_user_intent"] is True
    assert report["strongest_drift_dimensions"]
    assert report["recommended_next_action"] == RECOMMENDED_NEXT_ACTIONS[report["combined_verdict"]]
    assert report["guardrails"]["validation_run"] is False
    assert report["guardrails"]["benchmark_run"] is False
    assert report["guardrails"]["model_call_performed"] is False
    assert report["guardrails"]["writes_manual_review_artifacts_only"] is True


def test_build_pipeline_uses_supplied_score_and_claim_diff_reports(tmp_path):
    trace = _manual_trace(tmp_path, trace_id="trace-supplied")
    score = {
        "report_kind": "mirror_tunnel_derailment_score",
        "score_id": "score-fixture",
        "trace_id": "trace-supplied",
        "verdict": "severe_derailment",
        "overall_derailment_score": 0.91,
        "dimension_scores": {"intent_drift": {"score": 0.91, "reasons": ["fixture"]}},
        "frame_coverage": {"available_frame_count": 4, "has_user_intent": True},
        "missing_evidence": [],
        "detected_drift_points": [{"dimension": "intent_drift", "score": 0.91, "evidence": "fixture"}],
    }
    claim = {
        "report_kind": "mirror_tunnel_claim_diff_check",
        "check_id": "claim-fixture",
        "trace_id": "trace-supplied",
        "overall_claim_support": "contradicted",
        "mismatches": [{"claim_category": "validation_claim", "status": "mismatch", "message": "fixture"}],
        "unsupported_claims": [],
        "missing_evidence": [{"category": "validation_status", "reason": "fixture"}],
    }

    report = build_mirror_tunnel_manual_review(
        trace=trace,
        score=score,
        claim_diff=claim,
        trace_path="trace.json",
        score_path="score.json",
        claim_diff_path="claim.json",
        review_id="review-supplied",
    )

    assert report["score_source"] == "provided"
    assert report["claim_diff_source"] == "provided"
    assert report["derailment_score_summary"]["score_id"] == "score-fixture"
    assert report["claim_diff_summary"]["check_id"] == "claim-fixture"
    assert report["combined_verdict"] == "do_not_trust_without_more_evidence"
    assert report["recommended_next_action"] == "collect_evidence_or_replay"
    assert report["human_review_notes"]


def test_insufficient_trace_verdict_flows_through(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Only intent.")
    trace = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": str(intent.relative_to(repo))},
        trace_id="weak-trace",
    )

    report = build_mirror_tunnel_manual_review(trace=trace, review_id="weak-review")

    assert report["trace_status"] == "insufficient_evidence"
    assert report["combined_verdict"] == "insufficient_trace"
    assert report["recommended_next_action"] == "assemble_better_manual_trace"


def test_write_pipeline_outputs_json_and_markdown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    trace = _manual_trace(tmp_path, trace_id="write-trace")
    trace_path = _write_json(
        repo / ".agent" / "mirror_tunnel" / "manual_trace" / "write-trace" / "mirror_tunnel_trace_contract.json",
        trace,
    )

    result = write_mirror_tunnel_manual_review(
        repo_path=str(repo),
        trace_path=str(trace_path.relative_to(repo)),
        review_id="write-review",
        created_at="2026-06-30T00:00:00Z",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == repo / ".agent" / "mirror_tunnel" / "manual_review" / "write-review" / "mirror_tunnel_manual_review.json"
    assert Path(result["md_path"]) == repo / ".agent" / "mirror_tunnel" / "manual_review" / "write-review" / "mirror_tunnel_manual_review.md"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["review_id"] == "write-review"


def test_markdown_contains_required_sections(tmp_path):
    report = build_mirror_tunnel_manual_review(trace=_manual_trace(tmp_path), review_id="md")
    markdown = render_mirror_tunnel_manual_review_markdown(report).lower()
    for section in (
        "## summary",
        "## trace coverage",
        "## derailment score summary",
        "## claim-vs-diff summary",
        "## missing evidence",
        "## human review notes",
        "## recommended next action",
        "## boundaries / guardrails",
    ):
        assert section in markdown, section


def test_unsafe_or_missing_inputs_are_blocked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / ".env", "SECRET=do-not-read")
    secret_result = write_mirror_tunnel_manual_review(
        repo_path=str(repo),
        trace_path=".env",
        review_id="secret",
    )
    traversal_result = write_mirror_tunnel_manual_review(
        repo_path=str(repo),
        trace_path="../outside.json",
        review_id="traversal",
    )
    missing_result = write_mirror_tunnel_manual_review(
        repo_path=str(repo),
        trace_path=".agent/missing/trace.json",
        review_id="missing",
    )

    assert secret_result["ok"] is False
    assert secret_result["status"] == "blocked"
    assert secret_result["report"]["blockers"][0]["reason"] == "secret_or_env_path"
    assert "SECRET" not in json.dumps(secret_result)
    assert traversal_result["report"]["blockers"][0]["reason"] == "traversal_attempt"
    assert missing_result["report"]["blockers"][0]["reason"] == "unreadable_artifact"


def test_cli_writes_manual_review_pack(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    trace = _manual_trace(tmp_path, trace_id="cli-trace")
    trace_path = _write_json(
        repo / ".agent" / "mirror_tunnel" / "manual_trace" / "cli-trace" / "mirror_tunnel_trace_contract.json",
        trace,
    )

    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--trace",
            str(trace_path.relative_to(repo)),
            "--review-id",
            "cli-review",
            "--created-at",
            "2026-06-30T00:00:00Z",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["report"]["review_id"] == "cli-review"
    assert parsed["report"]["score_source"] == "derived"
    assert parsed["report"]["claim_diff_source"] == "derived"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()


def test_no_forbidden_imports_or_execution_calls_in_pipeline_layers():
    module_tree = ast.parse(Path(pipeline.__file__).read_text(encoding="utf-8"))
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
