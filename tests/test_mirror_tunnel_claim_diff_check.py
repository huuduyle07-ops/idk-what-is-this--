"""Tests for MIRROR.3 - Claim-vs-Diff Mirror Check.

MIRROR.3 compares agent/worker/final claims against trace, patch/diff,
validation, benchmark, and artifact evidence. It is report-only and must never
call models, embeddings, semantic APIs, validation, benchmarks, MCP tools,
workers, Docker/subprocess, Dream, Replay janitor apply, network services,
database writes, route/auth changes, or execution blockers.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from core import mirror_tunnel_claim_diff_check as check
from core.mirror_tunnel_claim_diff_check import (
    CLAIM_CATEGORIES,
    EVIDENCE_CATEGORIES,
    VERDICTS,
    build_mirror_tunnel_claim_diff_check,
    render_mirror_tunnel_claim_diff_markdown,
    write_mirror_tunnel_claim_diff_check,
)
from scripts import create_mirror_tunnel_claim_diff_check as cli


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
        {"frame_type": ft, "availability": "missing", "reason": "missing in fixture"}
        for ft in [
            "user_intent",
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
        "trace_id": "trace-claim-fixture",
        "created_at": "2026-06-29T00:00:00Z",
        "status": "complete_trace",
        "trust_level": "high",
        "source_run_id": "run-fixture",
        "frame_order": frame_types,
        "frames": frames,
        "missing_frames": missing,
        "missing_evidence": [{"frame_type": item["frame_type"], "evidence_status": "missing"} for item in missing],
        "artifact_references": [],
    }
    data.update(overrides)
    return data


def _score(verdict: str = "aligned") -> dict[str, Any]:
    return {
        "report_kind": "mirror_tunnel_derailment_score",
        "score_id": "score-fixture",
        "trace_id": "trace-claim-fixture",
        "verdict": verdict,
        "overall_derailment_score": None if verdict == "insufficient_trace" else 0.05,
        "recommended_next_phase": "MIRROR.3",
    }


def _supported_trace() -> dict[str, Any]:
    return _trace(
        [
            _frame("user_intent", "Fix checkout total. Allowed files: core/checkout.py."),
            _frame("worker_reply", "Changed only core/checkout.py. I did not touch web/app.py."),
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n@@ fixed checkout total\n"),
            _frame("validation_evidence", "python -m pytest tests/test_checkout.py -q PASSED"),
            _frame("benchmark_evidence", "benchmark check PASSED"),
            _frame(
                "final_answer",
                "Changed only core/checkout.py. Validation passed. Tests passed. Benchmark passed. "
                "The checkout fix is complete.",
            ),
        ]
    )


def test_claim_and_evidence_categories_are_stable():
    assert CLAIM_CATEGORIES == (
        "changed_files_claim",
        "no_change_claim",
        "validation_claim",
        "benchmark_claim",
        "test_claim",
        "safety_claim",
        "scope_claim",
        "completion_claim",
        "uncertainty_claim",
    )
    assert EVIDENCE_CATEGORIES == (
        "actual_changed_files",
        "patched_files",
        "generated_artifacts",
        "unexpected_mutations",
        "validation_status",
        "benchmark_status",
        "replay_status",
        "patch_safety_status",
        "missing_evidence",
    )
    assert VERDICTS == (
        "supported",
        "partially_supported",
        "unsupported",
        "contradicted",
        "insufficient_evidence",
    )


def test_supported_claims_match_diff_validation_and_benchmark_evidence():
    report = build_mirror_tunnel_claim_diff_check(
        trace=_supported_trace(),
        score=_score("aligned"),
        check_id="supported",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["check_id"] == "supported"
    assert report["overall_claim_support"] == "supported"
    assert report["recommended_next_action"] == "continue_normal_review"
    assert report["recommended_next_phase"] == "MIRROR.4"
    assert report["evidence_detected"]["patched_files"] == ["core/checkout.py"]
    assert not report["mismatches"]
    assert not report["unsupported_claims"]
    assert {match["claim_category"] for match in report["matches"]} >= {
        "changed_files_claim",
        "validation_claim",
        "benchmark_claim",
        "test_claim",
        "completion_claim",
    }
    assert report["guardrails"]["model_call_performed"] is False
    assert report["guardrails"]["validation_run"] is False
    assert report["guardrails"]["execution_blocking_performed"] is False


def test_only_changed_claim_is_contradicted_by_extra_diff_file():
    trace = _trace(
        [
            _frame("worker_reply", "Changed only core/checkout.py."),
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n--- a/web/app.py\n+++ b/web/app.py\n"),
            _frame("validation_evidence", "pytest passed"),
            _frame("final_answer", "Only changed core/checkout.py and tests passed."),
        ]
    )

    report = build_mirror_tunnel_claim_diff_check(trace=trace, score=_score("aligned"), check_id="scope")

    assert report["overall_claim_support"] == "contradicted"
    assert report["recommended_next_action"] == "do_not_trust_without_replay"
    assert any("web/app.py" in item["message"] for item in report["mismatches"])


def test_validation_claim_without_validation_evidence_is_unsupported():
    trace = _trace(
        [
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n"),
            _frame("final_answer", "Fixed checkout total and tests passed."),
        ],
        status="partial_trace",
        trust_level="medium",
    )

    report = build_mirror_tunnel_claim_diff_check(trace=trace, score=_score("minor_drift"), check_id="missing-validation")

    assert report["overall_claim_support"] in {"unsupported", "partially_supported"}
    assert any(item["claim_category"] in {"validation_claim", "test_claim"} for item in report["unsupported_claims"])
    assert report["recommended_next_action"] in {"collect_missing_evidence", "human_review_recommended"}


def test_no_change_claim_is_contradicted_by_patch_or_diff():
    trace = _trace(
        [
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n"),
            _frame("final_answer", "No code changes were made."),
        ]
    )

    report = build_mirror_tunnel_claim_diff_check(trace=trace, score=_score("aligned"), check_id="no-change")

    assert report["overall_claim_support"] == "contradicted"
    assert any(item["claim_category"] == "no_change_claim" for item in report["mismatches"])


def test_completion_claim_is_unsupported_when_mirror2_trace_is_insufficient():
    trace = _trace([_frame("final_answer", "The work is complete.")], status="insufficient_evidence", trust_level="low")

    report = build_mirror_tunnel_claim_diff_check(
        trace=trace,
        score=_score("insufficient_trace"),
        check_id="completion-unsupported",
    )

    assert report["overall_claim_support"] in {"unsupported", "insufficient_evidence"}
    assert any(item["claim_category"] == "completion_claim" for item in report["unsupported_claims"])


def test_honest_uncertainty_is_supported_when_validation_is_missing():
    trace = _trace(
        [
            _frame("patch_or_diff", "--- a/core/checkout.py\n+++ b/core/checkout.py\n"),
            _frame(
                "final_answer",
                "I did not run validation. The full suite timed out and is not counted as passed.",
            ),
        ],
        status="partial_trace",
        trust_level="medium",
    )

    report = build_mirror_tunnel_claim_diff_check(trace=trace, score=_score("minor_drift"), check_id="uncertain")

    assert report["overall_claim_support"] != "contradicted"
    assert any(item["claim_category"] == "uncertainty_claim" for item in report["honest_uncertainty_claims"])
    assert not any("timed out" in item["message"].lower() for item in report["mismatches"])


def test_explicit_diff_and_answer_files_are_read_and_written(tmp_path):
    repo = tmp_path / "repo"
    trace_path = repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
    score_path = repo / ".agent" / "mirror_tunnel" / "derailment_score" / "mirror_tunnel_derailment_score.json"
    diff_path = repo / "artifacts" / "change.diff"
    answer_path = repo / "artifacts" / "final.txt"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    score_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(_trace([]), indent=2), encoding="utf-8")
    score_path.write_text(json.dumps(_score("aligned"), indent=2), encoding="utf-8")
    diff_path.write_text("--- a/core/checkout.py\n+++ b/core/checkout.py\n", encoding="utf-8")
    answer_path.write_text("Changed only core/checkout.py. The fix is complete.", encoding="utf-8")

    result = write_mirror_tunnel_claim_diff_check(
        repo_path=str(repo),
        trace_path=str(trace_path),
        score_path=str(score_path),
        diff_path=str(diff_path),
        final_answer_file=str(answer_path),
        check_id="write-smoke",
        created_at="2026-06-29T00:00:00Z",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == repo / ".agent" / "mirror_tunnel" / "claim_diff_check" / "mirror_tunnel_claim_diff_check.json"
    assert Path(result["md_path"]) == repo / ".agent" / "mirror_tunnel" / "claim_diff_check" / "mirror_tunnel_claim_diff_check.md"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["check_id"] == "write-smoke"
    assert data["evidence_detected"]["patched_files"] == ["core/checkout.py"]


def test_path_guardrails_block_secret_env_and_outside_repo(tmp_path):
    repo = tmp_path / "repo"
    trace_path = repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(_supported_trace(), indent=2), encoding="utf-8")
    secret_diff = repo / ".env"
    secret_diff.write_text("--- a/core/checkout.py\n+++ b/core/checkout.py\n", encoding="utf-8")
    outside = tmp_path / "outside.diff"
    outside.write_text("--- a/core/checkout.py\n+++ b/core/checkout.py\n", encoding="utf-8")

    secret_result = write_mirror_tunnel_claim_diff_check(
        repo_path=str(repo),
        trace_path=str(trace_path),
        diff_path=str(secret_diff),
        check_id="secret",
    )
    outside_result = write_mirror_tunnel_claim_diff_check(
        repo_path=str(repo),
        trace_path=str(trace_path),
        diff_path=str(outside),
        check_id="outside",
    )

    assert secret_result["ok"] is False
    assert secret_result["status"] == "blocked"
    assert outside_result["ok"] is False
    assert outside_result["status"] == "blocked"
    assert not (repo / ".agent" / "mirror_tunnel" / "claim_diff_check").exists()


def test_markdown_contains_required_sections():
    report = build_mirror_tunnel_claim_diff_check(trace=_supported_trace(), score=_score("aligned"), check_id="md")
    markdown = render_mirror_tunnel_claim_diff_markdown(report)
    low = markdown.lower()
    for section in (
        "## summary",
        "## overall claim support",
        "## claims detected",
        "## evidence detected",
        "## matches",
        "## mismatches",
        "## unsupported claims",
        "## honest uncertainty claims",
        "## missing evidence",
        "## recommended next action",
        "## boundaries / guardrails",
    ):
        assert section in low, section


def test_cli_dry_run_prints_report_and_writes_nothing(tmp_path, capsys):
    repo = tmp_path / "repo"
    trace_path = repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(_supported_trace(), indent=2), encoding="utf-8")

    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--trace",
            str(trace_path),
            "--check-id",
            "cli-dry",
            "--created-at",
            "2026-06-29T00:00:00Z",
            "--dry-run",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["check_id"] == "cli-dry"
    assert parsed["recommended_next_phase"] == "MIRROR.4"
    assert not (repo / ".agent" / "mirror_tunnel" / "claim_diff_check").exists()


def test_cli_writes_claim_diff_artifacts(tmp_path, capsys):
    repo = tmp_path / "repo"
    trace_path = repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(_supported_trace(), indent=2), encoding="utf-8")

    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--trace",
            str(trace_path),
            "--check-id",
            "cli-write",
            "--created-at",
            "2026-06-29T00:00:00Z",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["report"]["check_id"] == "cli-write"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()


def test_no_forbidden_imports_or_execution_calls_in_claim_diff_layers():
    module_tree = ast.parse(Path(check.__file__).read_text(encoding="utf-8"))
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
