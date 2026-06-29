"""Tests for MIRROR.1 - Mirror Tunnel Trace Contract.

MIRROR.1 is report-only. It reconstructs a prompt/reply/evidence chain from
already-existing artifacts, records missing frames explicitly, and writes inert
trace-contract artifacts. It must never execute validation, benchmarks, workers,
MCP tools, Docker/subprocess commands, Replay/Dream actions, network calls, model
calls, database writes, route changes, auth changes, or patch application.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from core import mirror_tunnel_trace_contract as mt
from core.mirror_tunnel_trace_contract import (
    FRAME_TYPES,
    TRACE_STATUSES,
    TRUST_LEVELS,
    build_mirror_tunnel_trace_contract,
    render_mirror_tunnel_trace_markdown,
    write_mirror_tunnel_trace_contract,
)
from scripts import create_mirror_tunnel_trace_contract as cli


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    return _write(path, json.dumps(data, indent=2))


def test_frame_types_statuses_and_trust_levels_are_stable():
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
        "unknown_artifact",
    )
    assert TRACE_STATUSES == (
        "complete_trace",
        "partial_trace",
        "insufficient_evidence",
        "blocked",
    )
    assert TRUST_LEVELS == ("high", "medium", "low", "blocked")


def test_complete_trace_orders_available_frames_and_records_missing_frames(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    artifacts = [
        _write(repo / ".agent" / "answers" / "final_answer.md", "Final: shipped with validation."),
        _write_json(
            repo / ".agent" / "worker_assignments" / "wa-1" / "worker_assignment.json",
            {"assignment_id": "wa-1", "worker_role": "implementer", "title": "Fix checkout"},
        ),
        _write(repo / ".agent" / "patches" / "fix.diff", "--- a/core/x.py\n+++ b/core/x.py\n"),
        _write_json(
            repo / ".agent" / "validation" / "validation_report.json",
            {"validation_command": "python -m pytest tests/test_checkout.py -q", "status": "passed"},
        ),
        _write(repo / ".agent" / "intent" / "user_intent.txt", "Please fix the checkout total."),
    ]

    report = build_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=[str(path.relative_to(repo)) for path in artifacts],
        source_run_id="run-123",
        trace_id="trace-complete",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["trace_id"] == "trace-complete"
    assert report["source_run_id"] == "run-123"
    assert report["status"] == "complete_trace"
    assert report["trust_level"] == "high"
    assert report["recommended_next_phase"] == "MIRROR.2"
    assert report["frame_order"] == [
        "user_intent",
        "worker_assignment",
        "patch_or_diff",
        "validation_evidence",
        "final_answer",
    ]
    assert [frame["frame_type"] for frame in report["frames"]] == report["frame_order"]
    assert {frame["frame_type"] for frame in report["missing_frames"]} == {
        "goal_brief",
        "mode_decision",
        "control_prompt",
        "worker_reply",
        "benchmark_evidence",
        "replay_evidence",
    }
    assert all(frame["availability"] == "available" for frame in report["frames"])
    assert all(frame["availability"] == "missing" for frame in report["missing_frames"])
    assert report["available_evidence"]
    assert report["missing_evidence"]
    assert report["guardrails"]["validation_run"] is False
    assert report["guardrails"]["benchmark_run"] is False
    assert report["guardrails"]["model_call_performed"] is False
    assert report["guardrails"]["patch_applied"] is False


def test_partial_trace_does_not_infer_missing_frames(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    goal = _write_json(
        repo / ".agent" / "goal_briefs" / "gb-1" / "goal_brief.json",
        {"goal_brief_id": "gb-1", "problem_statement": "Explain why validation failed."},
    )
    reply = _write(repo / ".agent" / "workers" / "reply.md", "Worker reply: found the issue.")

    report = build_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=[str(reply.relative_to(repo)), str(goal.relative_to(repo))],
        trace_id="partial",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["status"] == "partial_trace"
    assert report["trust_level"] == "medium"
    assert report["frame_order"] == ["goal_brief", "worker_reply"]
    missing = {frame["frame_type"] for frame in report["missing_frames"]}
    assert "validation_evidence" in missing
    assert "final_answer" in missing
    assert "patch_or_diff" in missing
    # The worker reply is preserved as its own frame; no patch or validation is
    # invented from the reply text.
    assert "patch_or_diff" not in report["frame_order"]
    assert "validation_evidence" not in report["frame_order"]


def test_only_unknown_artifact_is_insufficient_evidence(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    artifact = _write(repo / ".agent" / "misc" / "note.txt", "Loose note without trace semantics.")

    report = build_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=[str(artifact.relative_to(repo))],
        trace_id="weak",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["status"] == "insufficient_evidence"
    assert report["trust_level"] == "low"
    assert report["frame_order"] == ["unknown_artifact"]
    assert report["frames"][0]["frame_type"] == "unknown_artifact"


def test_long_text_excerpts_are_capped_and_marked_truncated(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    artifact = _write(repo / ".agent" / "intent" / "user_intent.txt", "A" * 500)

    report = build_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=[str(artifact.relative_to(repo))],
        excerpt_limit=80,
        trace_id="cap",
        created_at="2026-06-29T00:00:00Z",
    )

    frame = report["frames"][0]
    assert len(frame["excerpt"]) <= 80
    assert frame["excerpt_truncated"] is True
    assert report["excerpt_limit"] == 80


def test_secret_env_and_traversal_paths_are_blocked_without_reading(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / ".env", "SECRET=do-not-read")

    secret_report = build_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=[".env"],
        trace_id="secret",
        created_at="2026-06-29T00:00:00Z",
    )
    traversal_report = build_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=["..\\outside.json"],
        trace_id="traversal",
        created_at="2026-06-29T00:00:00Z",
    )

    assert secret_report["status"] == "blocked"
    assert secret_report["trust_level"] == "blocked"
    assert secret_report["frames"] == []
    assert secret_report["blockers"][0]["reason"] == "secret_or_env_path"
    assert "SECRET" not in json.dumps(secret_report)

    assert traversal_report["status"] == "blocked"
    assert traversal_report["blockers"][0]["reason"] == "traversal_attempt"


def test_unreadable_artifact_is_blocked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    report = build_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=[".agent/missing/final_answer.md"],
        trace_id="missing-file",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["status"] == "blocked"
    assert report["blockers"][0]["reason"] == "unreadable_artifact"


def test_write_contract_writes_expected_json_and_markdown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix checkout.")

    result = write_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=[str(intent.relative_to(repo))],
        trace_id="write-smoke",
        created_at="2026-06-29T00:00:00Z",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
    assert Path(result["md_path"]) == repo / ".agent" / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.md"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["trace_id"] == "write-smoke"
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "# Mirror Tunnel Trace Contract" in markdown
    assert "## Boundaries" in markdown
    assert "does not call models" in markdown.lower()


def test_markdown_contains_schema_context_and_boundary_sections(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix checkout.")
    report = build_mirror_tunnel_trace_contract(
        repo_path=str(repo),
        source_artifact_paths=[str(intent.relative_to(repo))],
        trace_id="md",
        created_at="2026-06-29T00:00:00Z",
    )

    markdown = render_mirror_tunnel_trace_markdown(report)
    low = markdown.lower()
    for section in (
        "## frame schema",
        "## frame order",
        "## available evidence",
        "## missing evidence",
        "## reusable context",
        "## excluded context",
        "## artifact references",
        "## boundaries",
    ):
        assert section in low, section


def test_cli_dry_run_prints_json_and_writes_nothing(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix checkout.")

    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--artifact",
            str(intent.relative_to(repo)),
            "--trace-id",
            "cli-dry",
            "--created-at",
            "2026-06-29T00:00:00Z",
            "--dry-run",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["trace_id"] == "cli-dry"
    assert parsed["status"] == "insufficient_evidence"
    assert not (repo / ".agent" / "mirror_tunnel").exists()


def test_cli_writes_contract_artifacts(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix checkout.")

    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--artifact",
            str(intent.relative_to(repo)),
            "--trace-id",
            "cli-write",
            "--created-at",
            "2026-06-29T00:00:00Z",
            "--json",
        ]
    )

    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["report"]["trace_id"] == "cli-write"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()


def test_no_forbidden_imports_or_execution_calls_in_mirror_layers():
    module_tree = ast.parse(Path(mt.__file__).read_text(encoding="utf-8"))
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
