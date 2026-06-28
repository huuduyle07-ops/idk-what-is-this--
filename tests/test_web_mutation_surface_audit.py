"""HARDEN.2 - Web Mutation Surface Audit tests.

HARDEN.2 inventories Flask routes and reports the web mutation surface. It is
report-only: no model calls, no patch application, no validation/benchmark runs,
no worker launches, no network, no DB writes, and no route behavior changes.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from flask import Flask

from core.web_mutation_surface_audit import (
    REPORT_KIND,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
    build_web_mutation_surface_audit,
    render_web_mutation_surface_audit_markdown,
    write_web_mutation_surface_audit,
)
import scripts.create_web_mutation_surface_audit as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _write_harden1_files(repo: Path) -> None:
    web = repo / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "auth_gate.py").write_text(
        "def should_allow_mutation(*args, **kwargs):\n"
        "    return True\n",
        encoding="utf-8",
    )
    (web / "app.py").write_text(
        "from web.auth_gate import should_allow_mutation\n"
        "@app.before_request\n"
        "def _web_mutation_gate():\n"
        "    return should_allow_mutation()\n",
        encoding="utf-8",
    )


def _app_with_gate(repo: Path) -> Flask:
    _write_harden1_files(repo)
    app = Flask(__name__)

    @app.before_request
    def _web_mutation_gate():
        should_allow_mutation = True
        return None if should_allow_mutation else ("blocked", 403)

    return app


def _by_rule(report: dict, rule: str) -> dict:
    for route in report["routes"]:
        if route["rule"] == rule:
            return route
    raise AssertionError(f"route not found: {rule}")


def test_safe_get_route_is_read_only_by_default(tmp_path):
    app = _app_with_gate(tmp_path)

    @app.get("/status")
    def status_route():
        return "ok"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    route = _by_rule(report, "/status")
    assert report["verdict"] == STATUS_PASS
    assert route["method_classification"] == "read_only"
    assert route["categories"] == ["safe/read-only"]
    assert route["mutating_methods"] == []


def test_post_route_is_mutating_dangerous_and_covered_by_gate(tmp_path):
    app = _app_with_gate(tmp_path)

    @app.post("/apply_patch")
    def apply_patch_route():
        return "ok"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    route = _by_rule(report, "/apply_patch")
    assert report["verdict"] == STATUS_PASS
    assert route["method_classification"] == "mutating"
    assert route["covered_by_auth_gate"] is True
    assert "mutating" in route["categories"]
    assert "dangerous" in route["categories"]
    assert "apply" in route["risk_keywords"]
    assert "patch" in route["risk_keywords"]


def test_dangerous_get_only_route_warns_for_manual_review(tmp_path):
    app = _app_with_gate(tmp_path)

    @app.get("/replays/janitor")
    def replay_janitor_route():
        return "dry-run"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    assert report["verdict"] == STATUS_WARN
    assert report["dangerous_get_only_routes"][0]["rule"] == "/replays/janitor"
    assert any("GET-only" in warning for warning in report["warnings"])


def test_mixed_safe_and_mutating_methods_warn(tmp_path):
    app = _app_with_gate(tmp_path)

    @app.route("/dream/queue", methods=["GET", "POST"])
    def dream_queue_route():
        return "ok"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    route = _by_rule(report, "/dream/queue")
    assert route["method_classification"] == "mixed"
    assert report["mixed_method_routes"][0]["rule"] == "/dream/queue"
    assert report["verdict"] == STATUS_WARN


def test_missing_auth_gate_module_fails(tmp_path):
    app = Flask(__name__)

    @app.post("/apply_patch")
    def apply_patch_route():
        return "ok"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    assert report["verdict"] == STATUS_FAIL
    assert any("auth gate module" in blocker for blocker in report["blockers"])


def test_missing_before_request_wiring_fails(tmp_path):
    _write_harden1_files(tmp_path)
    app = Flask(__name__)

    @app.post("/apply_patch")
    def apply_patch_route():
        return "ok"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    assert report["verdict"] == STATUS_FAIL
    assert any("before_request" in blocker for blocker in report["blockers"])


def test_dangerous_route_with_unclear_method_is_reported(tmp_path):
    app = _app_with_gate(tmp_path)

    def patch_trace_route():
        return "ok"

    app.add_url_rule("/patch-trace", view_func=patch_trace_route, methods=["TRACE"])
    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    route = _by_rule(report, "/patch-trace")
    assert route["method_classification"] == "unclear"
    assert report["dangerous_unclear_method_routes"][0]["rule"] == "/patch-trace"
    assert report["verdict"] == STATUS_WARN


def test_uninspected_mutating_route_module_blocks(tmp_path):
    app = _app_with_gate(tmp_path)
    route_module = tmp_path / "web" / "forgotten_routes.py"
    route_module.write_text(
        "from flask import Blueprint\n"
        "bp = Blueprint('forgotten', __name__)\n"
        "@bp.route('/forgotten/apply', methods=['POST'])\n"
        "def forgotten_apply():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    assert report["verdict"] == STATUS_FAIL
    assert report["uninspected_route_modules"][0]["module"] == "web.forgotten_routes"
    assert any("outside the app.url_map" in blocker for blocker in report["blockers"])


def test_known_dangerous_route_missing_blocks(tmp_path):
    app = _app_with_gate(tmp_path)

    @app.get("/status")
    def status_route():
        return "ok"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=("/apply_patch",),
    )
    assert report["verdict"] == STATUS_FAIL
    assert report["known_dangerous_missing"] == ["/apply_patch"]


def test_markdown_contains_compact_route_table(tmp_path):
    app = _app_with_gate(tmp_path)

    @app.post("/benchmarks/run")
    def benchmark_run_route():
        return "ok"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    md = render_web_mutation_surface_audit_markdown(report)
    assert "# Web Mutation Surface Audit" in md
    assert "| Method class | Methods | Rule | Endpoint | Categories | Gate | Notes |" in md
    assert "/benchmarks/run" in md
    assert "benchmark-running" in md


def test_write_outputs_json_and_markdown(tmp_path):
    app = _app_with_gate(tmp_path)

    @app.post("/upload_folder")
    def upload_folder_route():
        return "ok"

    out = tmp_path / "out"
    result = write_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        output_dir=out,
        report_id="write",
        created_at="2026-06-28T00:00:00+00:00",
        known_dangerous_routes=(),
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "web_mutation_surface_audit.json"
    assert Path(result["md_path"]).name == "web_mutation_surface_audit.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    assert data["report_id"] == "write"


def test_real_app_all_mutating_routes_are_covered_by_harden1_gate():
    from web.app import app

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=PROJECT_ROOT,
        report_id="real",
        created_at="t",
    )
    mutating = [route for route in report["routes"] if route["mutating_methods"]]
    assert mutating
    assert all(route["covered_by_auth_gate"] for route in mutating)
    assert _by_rule(report, "/apply_patch")["covered_by_auth_gate"] is True
    assert "validation-running" in _by_rule(report, "/proposals/validate")["categories"]
    assert "benchmark-running" in _by_rule(report, "/benchmarks/run")["categories"]


def test_real_app_report_passes_or_warns_but_does_not_fail():
    from web.app import app

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=PROJECT_ROOT,
        report_id="real",
        created_at="t",
    )
    assert report["verdict"] in {STATUS_PASS, STATUS_WARN}
    assert report["auth_gate"]["gate_module_exists"] is True
    assert report["auth_gate"]["before_request_wiring_detected"] is True
    assert report["route_counts"]["mutating"] > 0
    assert report["blockers"] == []


def test_script_writes_real_app_artifacts(tmp_path):
    out = tmp_path / "audit"
    result = script.run_create_web_mutation_surface_audit(
        repo_path=str(PROJECT_ROOT),
        output_root=str(out),
        report_id="script",
        created_at="2026-06-28T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert result["verdict"] in {STATUS_PASS, STATUS_WARN}
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


def test_guardrail_flags_show_report_only_boundaries(tmp_path):
    app = _app_with_gate(tmp_path)

    @app.get("/status")
    def status_route():
        return "ok"

    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=tmp_path,
        report_id="r",
        created_at="t",
        known_dangerous_routes=(),
    )
    guardrails = report["guardrails"]
    assert guardrails["report_only"] is True
    for key, value in guardrails.items():
        if key == "report_only":
            continue
        assert value is False, key


def test_core_and_script_do_not_call_execution_sinks():
    core_src = (PROJECT_ROOT / "core" / "web_mutation_surface_audit.py").read_text(encoding="utf-8")
    script_src = (PROJECT_ROOT / "scripts" / "create_web_mutation_surface_audit.py").read_text(encoding="utf-8")
    tree = ast.parse(core_src + "\n" + script_src)
    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)
            elif isinstance(node.func, ast.Name):
                call_names.append(node.func.id)

    forbidden = {
        "run_gemini_request",
        "run_deepseek_review",
        "run_agent_web",
        "apply_patch",
        "run_patch_plan_with_artifacts",
        "run_safe_validation",
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
    }
    hits = sorted(forbidden & set(call_names))
    assert hits == []
