"""HARDEN.3 - Safe Validation / MCP Approval Enforcement Audit tests.

The HARDEN.3 audit is report-only. It statically inspects local source files for
validation execution, MCP/tool-style artifact actions, janitor/apply/delete
paths, and approval-sensitive fields. It must not execute validation, invoke MCP
tools, launch workers, apply patches, run benchmarks, contact the network, or
mutate anything except its JSON/Markdown artifacts.
"""
from __future__ import annotations

import ast
import json
import textwrap
from pathlib import Path

from core.safe_validation_mcp_approval_audit import (
    REPORT_KIND,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
    build_safe_validation_mcp_approval_audit,
    render_safe_validation_mcp_approval_audit_markdown,
    write_safe_validation_mcp_approval_audit,
)
import scripts.create_safe_validation_mcp_approval_audit as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")
    return path


def _surface_ids(items: list[dict]) -> set[str]:
    return {str(item.get("surface_id")) for item in items}


def test_synthetic_guarded_surfaces_pass(tmp_path):
    _write(
        tmp_path / "core" / "validation_execution.py",
        """
        import subprocess

        def run_safe_validation_command(command):
            reason = validate_safe_validation_command(command)
            if reason:
                return {"blocked": True, "reason": reason}
            return subprocess.run(command.command, shell=False, timeout=command.timeout_sec)
        """,
    )
    _write(
        tmp_path / "mcp_server" / "artifact_write.py",
        """
        _EXTRA_WRITE_TOOLS = ("create_handoff_note", "validate_imported_worker_proposal")

        def list_exposed_tool_names():
            names = []
            for name in _EXTRA_WRITE_TOOLS:
                if tool_registry.is_tool_allowed(name, "artifact_write"):
                    names.append(name)
            return names

        def validate_imported_worker_proposal_harness(input):
            proposal_ref, repo_path = _validate_imported_proposal_input(input)
            # Validation happens only in a temp clone; result is an artifact.
            with tempfile.TemporaryDirectory(prefix="worker-validate-"):
                return {"ok": True, "requires_human_approval": True}
        """,
    )
    _write(
        tmp_path / "core" / "replay_janitor.py",
        """
        CONFIRM_TOKEN = "DELETE_REPLAY_CANDIDATES"

        def apply_replay_cleanup(repo_path, *, confirm=None):
            if confirm != CONFIRM_TOKEN:
                return {"confirmed": False, "blocked": True}
            return _rmtree_contained(repo_path)
        """,
    )

    report = build_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        report_id="synthetic",
        created_at="2026-06-29T00:00:00+00:00",
    )

    assert report["report_kind"] == REPORT_KIND
    assert report["verdict"] == STATUS_PASS
    assert report["blockers"] == []
    assert report["warnings"] == []
    assert any(s["gate_status"] == "guarded" for s in report["validation_surfaces"])
    assert any(s["gate_status"] == "guarded" for s in report["mcp_surfaces"])
    assert any(s["gate_status"] == "guarded" for s in report["janitor_or_cleanup_surfaces"])
    assert report["recommended_next_phase"].startswith("HARDEN.CLOSE")


def test_raw_validation_shell_execution_without_safety_gate_blocks(tmp_path):
    _write(
        tmp_path / "core" / "unsafe_validation.py",
        """
        import subprocess

        def run_validation_command(command):
            return subprocess.run(command, shell=True)
        """,
    )

    report = build_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        report_id="raw-validation",
        created_at="t",
    )

    assert report["verdict"] == STATUS_FAIL
    assert any("raw validation execution" in blocker for blocker in report["blockers"])
    surface = report["validation_surfaces"][0]
    assert surface["gate_status"] == "blocked"
    assert "shell_true" in surface["signals"]


def test_mcp_apply_like_surface_without_registry_or_sandbox_gate_blocks(tmp_path):
    _write(
        tmp_path / "mcp_server" / "dangerous.py",
        """
        def validate_imported_worker_proposal_harness(input):
            return apply_patch(input["patch"])
        """,
    )

    report = build_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        report_id="mcp-bypass",
        created_at="t",
    )

    assert report["verdict"] == STATUS_FAIL
    assert any("MCP/tool surface" in blocker for blocker in report["blockers"])
    assert report["mcp_surfaces"][0]["gate_status"] == "blocked"


def test_janitor_delete_without_confirmation_blocks(tmp_path):
    _write(
        tmp_path / "core" / "cleanup.py",
        """
        import shutil

        def apply_replay_cleanup(path):
            shutil.rmtree(path)
        """,
    )

    report = build_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        report_id="delete-bypass",
        created_at="t",
    )

    assert report["verdict"] == STATUS_FAIL
    assert any("delete/apply cleanup" in blocker for blocker in report["blockers"])
    assert report["janitor_or_cleanup_surfaces"][0]["gate_status"] == "blocked"


def test_auto_merge_or_self_approval_true_blocks(tmp_path):
    _write(
        tmp_path / "core" / "approval.py",
        """
        def build_contract():
            return {
                "human_approval_required": False,
                "apply_allowed": True,
                "worker_launch_allowed": True,
                "auto_merge": True,
                "self_approval": True,
            }
        """,
    )

    report = build_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        report_id="approval-bypass",
        created_at="t",
    )

    assert report["verdict"] == STATUS_FAIL
    assert any("approval-sensitive field" in blocker for blocker in report["blockers"])
    assert report["approval_gate_surfaces"][0]["gate_status"] == "blocked"


def test_route_inventory_extracts_audited_routes(tmp_path):
    _write(
        tmp_path / "web" / "routes" / "replay_routes.py",
        """
        @bp.route("/replays/janitor/apply", methods=["POST"])
        def replays_janitor_apply_route():
            confirm = request.values.get("confirm")
            return apply_replay_cleanup(repo, confirm=confirm)
        """,
    )

    report = build_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        report_id="routes",
        created_at="t",
    )

    assert report["audited_routes"]
    route = report["audited_routes"][0]
    assert route["rule"] == "/replays/janitor/apply"
    assert route["methods"] == ["POST"]
    assert route["function_name"] == "replays_janitor_apply_route"


def test_real_repo_audit_inventories_known_surfaces_without_blockers():
    report = build_safe_validation_mcp_approval_audit(
        repo_path=PROJECT_ROOT,
        report_id="real",
        created_at="t",
    )

    assert report["verdict"] in {STATUS_PASS, STATUS_WARN}
    assert report["blockers"] == []
    audited_paths = {item["path"] for item in report["audited_files"]}
    assert "core/validation_execution.py" in audited_paths
    assert "mcp_server/artifact_write.py" in audited_paths
    assert "core/replay_janitor.py" in audited_paths
    assert any(
        surface["path"] == "core/validation_execution.py"
        and surface["function_name"] == "run_safe_validation_command"
        and surface["gate_status"] == "guarded"
        for surface in report["validation_surfaces"]
    )
    assert any(
        surface["path"] == "mcp_server/artifact_write.py"
        and surface["gate_status"] == "guarded"
        for surface in report["mcp_surfaces"]
    )
    assert any(
        surface["path"] == "core/replay_janitor.py"
        and surface["function_name"] == "apply_replay_cleanup"
        and surface["gate_status"] == "guarded"
        for surface in report["janitor_or_cleanup_surfaces"]
    )
    assert any(route["rule"] == "/proposals/validate" for route in report["audited_routes"])
    assert any(route["rule"] == "/replays/janitor/apply" for route in report["audited_routes"])


def test_markdown_contains_required_sections(tmp_path):
    _write(
        tmp_path / "core" / "validation_execution.py",
        """
        def run_safe_validation_command(command):
            return validate_safe_validation_command(command)
        """,
    )
    report = build_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        report_id="md",
        created_at="t",
    )
    md = render_safe_validation_mcp_approval_audit_markdown(report)
    low = md.lower()
    assert "# safe validation / mcp approval enforcement audit" in low
    for section in (
        "## summary",
        "## audited files",
        "## audited routes",
        "## validation surfaces",
        "## mcp surfaces",
        "## janitor / cleanup surfaces",
        "## approval gate surfaces",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section


def test_write_outputs_json_and_markdown(tmp_path):
    _write(
        tmp_path / "core" / "validation_execution.py",
        """
        def run_safe_validation_command(command):
            return validate_safe_validation_command(command)
        """,
    )
    out = tmp_path / "out"
    result = write_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        output_dir=out,
        report_id="write",
        created_at="2026-06-29T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "safe_validation_mcp_approval_audit.json"
    assert Path(result["md_path"]).name == "safe_validation_mcp_approval_audit.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    assert data["report_id"] == "write"


def test_script_writes_real_app_artifacts(tmp_path):
    out = tmp_path / "audit"
    result = script.run_create_safe_validation_mcp_approval_audit(
        repo_path=str(PROJECT_ROOT),
        output_root=str(out),
        report_id="script",
        created_at="2026-06-29T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert result["verdict"] in {STATUS_PASS, STATUS_WARN}
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


def test_guardrail_flags_show_report_only_boundaries(tmp_path):
    _write(
        tmp_path / "core" / "validation_execution.py",
        """
        def run_safe_validation_command(command):
            return validate_safe_validation_command(command)
        """,
    )
    report = build_safe_validation_mcp_approval_audit(
        repo_path=tmp_path,
        report_id="guards",
        created_at="t",
    )
    guardrails = report["guardrails"]
    assert guardrails["report_only"] is True
    for key, value in guardrails.items():
        if key == "report_only":
            continue
        assert value is False, key


def test_core_and_script_do_not_call_execution_sinks():
    core_src = (PROJECT_ROOT / "core" / "safe_validation_mcp_approval_audit.py").read_text(encoding="utf-8")
    script_src = (PROJECT_ROOT / "scripts" / "create_safe_validation_mcp_approval_audit.py").read_text(encoding="utf-8")
    tree = ast.parse(core_src + "\n" + script_src)
    imported_roots: set[str] = set()
    call_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)
            elif isinstance(node.func, ast.Name):
                call_names.append(node.func.id)

    forbidden_imports = {
        "subprocess",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "mcp",
        "agents",
        "database",
    }
    assert sorted(forbidden_imports & imported_roots) == []

    forbidden_calls = {
        "run_gemini_request",
        "run_deepseek_review",
        "run_agent_web",
        "apply_patch",
        "run_patch_plan_with_artifacts",
        "run_safe_validation_command",
        "run_benchmarks",
        "start_benchmark_run_async",
        "start_overnight_async",
        "Popen",
        "run",
        "call",
        "check_call",
        "check_output",
        "request",
        "urlopen",
        "launch_worker",
        "consolidate_all",
        "copytree",
        "rmtree",
        "unlink",
    }
    assert sorted(forbidden_calls & set(call_names)) == []
