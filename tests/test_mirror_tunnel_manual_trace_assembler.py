"""Tests for MIRROR.5 - Manual Trace Assembler.

MIRROR.5 manually assembles an explicit set of artifact paths into a
MIRROR.1-compatible trace. It is report-only: no model calls, validation or
benchmark runs, workers, MCP tools, Docker/subprocess, route/auth changes, live
tracing, database writes, patch application, or network calls.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from core import mirror_tunnel_manual_trace_assembler as manual
from core.mirror_tunnel_manual_trace_assembler import (
    FRAME_INPUTS,
    MANUAL_TRUST_LEVELS,
    TRACE_STATUSES,
    build_manual_mirror_tunnel_trace,
    render_manual_mirror_tunnel_trace_markdown,
    write_manual_mirror_tunnel_trace,
)
from scripts import create_mirror_tunnel_manual_trace as cli


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    return _write(path, json.dumps(data, indent=2))


def _rel(repo: Path, path: Path) -> str:
    return str(path.relative_to(repo)).replace("\\", "/")


def test_frame_inputs_statuses_and_trust_levels_are_stable():
    assert {item["source_key"]: item["frame_type"] for item in FRAME_INPUTS} == {
        "user_intent_file": "user_intent",
        "goal_brief_json": "goal_brief",
        "mode_decision_json": "mode_decision",
        "control_prompt_file": "control_prompt",
        "worker_assignment_json": "worker_assignment",
        "worker_reply_file": "worker_reply",
        "patch_json": "patch_or_diff",
        "diff_file": "patch_or_diff",
        "validation_json": "validation_evidence",
        "benchmark_json": "benchmark_evidence",
        "replay_json": "replay_evidence",
        "final_answer_file": "final_answer",
    }
    assert MANUAL_TRUST_LEVELS == (
        "user_provided",
        "generated_artifact",
        "validation_artifact",
        "benchmark_artifact",
        "replay_artifact",
        "unknown",
    )
    assert TRACE_STATUSES == (
        "complete_trace",
        "partial_trace",
        "insufficient_evidence",
        "blocked",
    )


def test_complete_manual_trace_uses_explicit_frame_types_and_trust_levels(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Implement MIRROR.5 safely.")
    patch = _write_json(
        repo / ".agent" / "patches" / "patch.json",
        {"changed_files": ["core/mirror_tunnel_manual_trace_assembler.py"], "patched_files": []},
    )
    validation = _write_json(
        repo / ".agent" / "validation" / "validation.json",
        {"command": "python -m pytest tests/test_mirror_tunnel_manual_trace_assembler.py -q", "status": "passed"},
    )
    final = _write(repo / ".agent" / "answers" / "final_answer.md", "Implemented and validated MIRROR.5.")

    report = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={
            "final_answer_file": _rel(repo, final),
            "patch_json": _rel(repo, patch),
            "validation_json": _rel(repo, validation),
            "user_intent_file": _rel(repo, intent),
        },
        trace_id="manual-complete",
        created_at="2026-06-29T00:00:00Z",
    )

    assert report["report_kind"] == "mirror_tunnel_trace_contract"
    assert report["trace_id"] == "manual-complete"
    assert report["status"] == "complete_trace"
    assert report["trust_level"] == "high"
    assert report["recommended_next_phase"] == "MIRROR.2"
    assert report["frame_order"] == ["user_intent", "patch_or_diff", "validation_evidence", "final_answer"]
    assert [frame["frame_type"] for frame in report["frames"]] == report["frame_order"]
    assert [frame["source_key"] for frame in report["frames"]] == [
        "user_intent_file",
        "patch_json",
        "validation_json",
        "final_answer_file",
    ]
    trusts = {frame["frame_type"]: frame["trust_level"] for frame in report["frames"]}
    assert trusts == {
        "user_intent": "user_provided",
        "patch_or_diff": "generated_artifact",
        "validation_evidence": "validation_artifact",
        "final_answer": "generated_artifact",
    }
    assert "unknown_artifact" not in report["frame_order"]
    assert any(item["source_key"] == "benchmark_json" for item in report["missing_evidence"])
    assert any(item["frame_type"] == "goal_brief" for item in report["missing_frames"])
    assert report["artifact_references"][0]["artifact_path"] == _rel(repo, intent)
    assert report["reusable_context"]["items"]
    assert report["excluded_context"]["items"]
    assert report["guardrails"]["automatic_live_tracing_enabled"] is False
    assert report["guardrails"]["validation_run"] is False
    assert report["guardrails"]["model_call_performed"] is False


def test_missing_user_intent_is_insufficient_even_with_other_frames(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    patch = _write_json(repo / ".agent" / "patches" / "patch.json", {"changed_files": ["core/x.py"]})
    validation = _write_json(repo / ".agent" / "validation" / "validation.json", {"status": "passed"})

    report = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"patch_json": _rel(repo, patch), "validation_json": _rel(repo, validation)},
        trace_id="no-intent",
    )

    assert report["status"] == "insufficient_evidence"
    assert report["trust_level"] == "low"
    assert any(item["source_key"] == "user_intent_file" for item in report["missing_evidence"])


def test_user_intent_and_final_answer_without_evidence_is_partial(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix a bug.")
    final = _write(repo / ".agent" / "answers" / "final_answer.md", "Fixed the bug.")

    report = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": _rel(repo, intent), "final_answer_file": _rel(repo, final)},
        trace_id="partial",
    )

    assert report["status"] == "partial_trace"
    assert report["trust_level"] == "medium"
    assert report["frame_order"] == ["user_intent", "final_answer"]


def test_explicit_missing_and_unsafe_paths_block_without_reading(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / ".env", "SECRET=do-not-read")
    _write(repo / ".agent" / "token.txt", "TOKEN=do-not-read")

    missing = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": ".agent/missing/user_intent.txt"},
        trace_id="missing",
    )
    secret = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": ".env"},
        trace_id="secret",
    )
    token = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": ".agent/token.txt"},
        trace_id="token",
    )
    traversal = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": "../outside.txt"},
        trace_id="traversal",
    )

    assert missing["status"] == "blocked"
    assert missing["blockers"][0]["reason"] == "unreadable_artifact"
    assert secret["status"] == "blocked"
    assert secret["blockers"][0]["reason"] == "secret_or_env_path"
    assert "SECRET" not in json.dumps(secret)
    assert token["status"] == "blocked"
    assert token["blockers"][0]["reason"] == "secret_or_env_path"
    assert "TOKEN" not in json.dumps(token)
    assert traversal["status"] == "blocked"
    assert traversal["blockers"][0]["reason"] == "traversal_attempt"


def test_excerpts_are_capped_and_marked_truncated(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "A" * 500)

    report = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": _rel(repo, intent)},
        trace_id="cap",
        excerpt_limit=64,
    )

    frame = report["frames"][0]
    assert len(frame["excerpt"]) <= 64
    assert frame["excerpt_truncated"] is True
    assert report["excerpt_limit"] == 64


def test_write_manual_trace_artifacts_under_trace_id_directory(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix checkout.")

    result = write_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": _rel(repo, intent)},
        trace_id="write-smoke",
        created_at="2026-06-29T00:00:00Z",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == repo / ".agent" / "mirror_tunnel" / "manual_trace" / "write-smoke" / "mirror_tunnel_trace_contract.json"
    assert Path(result["md_path"]) == repo / ".agent" / "mirror_tunnel" / "manual_trace" / "write-smoke" / "mirror_tunnel_trace_contract.md"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["trace_id"] == "write-smoke"


def test_markdown_contains_mirror1_sections_and_manual_assembly_context(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix checkout.")
    report = build_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={"user_intent_file": _rel(repo, intent)},
        trace_id="md",
    )

    markdown = render_manual_mirror_tunnel_trace_markdown(report)
    low = markdown.lower()
    for section in (
        "## frame schema",
        "## frame order",
        "## available frames",
        "## missing frames",
        "## available evidence",
        "## missing evidence",
        "## reusable context",
        "## excluded context",
        "## artifact references",
        "## boundaries",
    ):
        assert section in low, section
    assert "manual trace assembler" in low


def test_cli_writes_manual_trace_from_explicit_paths(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    intent = _write(repo / ".agent" / "intent" / "user_intent.txt", "Fix checkout.")
    final = _write(repo / ".agent" / "answers" / "final_answer.md", "Fixed checkout.")

    code = cli.main(
        [
            "--repo-path",
            str(repo),
            "--user-intent-file",
            _rel(repo, intent),
            "--final-answer-file",
            _rel(repo, final),
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
    assert parsed["report"]["frame_order"] == ["user_intent", "final_answer"]
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()


def test_output_dir_rejects_traversal(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    result = write_manual_mirror_tunnel_trace(
        repo_path=str(repo),
        artifact_paths={},
        trace_id="blocked",
        output_dir="../outside",
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["report"]["blockers"][0]["reason"] == "traversal_attempt"


def test_no_forbidden_imports_or_execution_calls_in_manual_trace_layers():
    module_tree = ast.parse(Path(manual.__file__).read_text(encoding="utf-8"))
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
