"""Tests for UX.RUN.1 - Run Progress / Operator Visibility.

UX.RUN.1 is a read-only/operator-facing visibility layer. It defines a stage
contract and writes report artifacts so long runs can describe progress without
changing execution behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.phase_registry import load_phase_registry, validate_phase_registry
from core.run_progress_visibility import (
    GUARDRAIL_NOTE,
    JSON_NAME,
    MD_NAME,
    READY_WITH_WARNINGS,
    REQUIRED_STAGE_FIELDS,
    REQUIRED_STAGE_IDS,
    SAFETY_CONTEXT_FALSE_FLAGS,
    SAFETY_RULE_IDS,
    build_run_progress_visibility_report,
    render_run_progress_visibility_markdown,
    write_run_progress_visibility_report,
)
import scripts.create_run_progress_visibility_report as script


def _stage_by_id(report: dict, stage_id: str) -> dict:
    stages = {stage["stage_id"]: stage for stage in report["stage_contract"]}
    return stages[stage_id]


def test_writes_json_and_markdown_progress_visibility_artifacts(tmp_path):
    out = tmp_path / "out"
    result = write_run_progress_visibility_report(
        output_dir=out,
        report_id="ux-run-1",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]).name == JSON_NAME
    assert Path(result["md_path"]).name == MD_NAME
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == "run_progress_visibility"
    assert data["status"] == READY_WITH_WARNINGS


def test_defines_required_progress_stages():
    report = build_run_progress_visibility_report(created_at="t")
    ids = [stage["stage_id"] for stage in report["stage_contract"]]

    assert ids == list(REQUIRED_STAGE_IDS)


def test_every_stage_has_required_schema_fields():
    report = build_run_progress_visibility_report(created_at="t")

    for stage in report["stage_contract"]:
        assert set(REQUIRED_STAGE_FIELDS) <= set(stage), stage["stage_id"]


def test_every_stage_is_safe_to_display_or_explicitly_limited():
    report = build_run_progress_visibility_report(created_at="t")

    for stage in report["stage_contract"]:
        assert (
            stage["safe_to_display"] is True
            or stage["visibility_level"] in {"debug_visible", "hidden_until_available"}
        ), stage["stage_id"]


def test_every_stage_is_non_authoritative_and_non_action_triggering():
    report = build_run_progress_visibility_report(created_at="t")

    for stage in report["stage_contract"]:
        assert stage["is_runtime_authority"] is False
        assert stage["may_trigger_action"] is False


def test_progress_visibility_does_not_imply_success():
    report = build_run_progress_visibility_report(created_at="t")

    assert report["progress_semantics"]["progress_implies_success"] is False
    assert "does not imply success" in " ".join(report["safety_rules"]).lower()


def test_validation_not_run_is_distinct_from_validation_reported():
    report = build_run_progress_visibility_report(created_at="t")
    not_run = _stage_by_id(report, "validation_not_run")
    reported = _stage_by_id(report, "validation_reported")

    assert not_run["stage_id"] != reported["stage_id"]
    assert "not run" in not_run["operator_meaning"].lower()
    assert "passed" not in not_run["label"].lower()
    assert "reported" in reported["operator_meaning"].lower()


def test_benchmark_not_run_is_distinct_from_benchmark_reported():
    report = build_run_progress_visibility_report(created_at="t")
    not_run = _stage_by_id(report, "benchmark_not_run")
    reported = _stage_by_id(report, "benchmark_reported")

    assert not_run["stage_id"] != reported["stage_id"]
    assert "not run" in not_run["operator_meaning"].lower()
    assert "passed" not in not_run["label"].lower()
    assert "reported" in reported["operator_meaning"].lower()


def test_errors_are_visible_not_hidden():
    report = build_run_progress_visibility_report(created_at="t")
    error_stage = _stage_by_id(report, "error_reported")

    assert error_stage["visibility_level"] == "always_visible"
    assert error_stage["safe_to_display"] is True
    assert report["error_visibility"]["errors_must_be_visible"] is True
    assert report["guardrails"]["errors_hidden"] is False


def test_status_ready_with_warnings_when_no_live_stream_exists():
    report = build_run_progress_visibility_report(created_at="t", live_stream_implemented=False)

    assert report["status"] == READY_WITH_WARNINGS
    assert any("live progress stream" in warning.lower() for warning in report["warnings"])


def test_blocks_if_progress_stage_can_trigger_action():
    report = build_run_progress_visibility_report(
        created_at="t",
        stage_overrides={
            "model_call_pending": {
                "may_trigger_action": True,
                "notes": "Unsafe: this stage would trigger runtime behavior.",
            }
        },
    )

    assert report["status"] == "run_progress_visibility_blocked"
    assert any("may_trigger_action" in reason["reason"] for reason in report["blocked_reasons"])


def test_blocks_if_runtime_power_is_reported():
    for flag in (
        "patch_apply_performed",
        "validation_run_performed",
        "benchmark_run_performed",
        "worker_launch_performed",
        "model_call_performed",
    ):
        context = {flag: True}
        report = build_run_progress_visibility_report(created_at="t", safety_context=context)
        assert report["status"] == "run_progress_visibility_blocked", flag
        assert any(flag in reason["reason"] for reason in report["blocked_reasons"]), flag


def test_safety_rules_are_complete_and_named():
    report = build_run_progress_visibility_report(created_at="t")
    rule_ids = {rule["rule_id"] for rule in report["safety_rule_details"]}

    assert set(SAFETY_RULE_IDS) <= rule_ids
    assert len(report["safety_rules"]) >= len(SAFETY_RULE_IDS)


def test_ui_stub_plan_is_read_only_and_inert():
    report = build_run_progress_visibility_report(created_at="t")
    stub = report["ui_stub_plan"]

    assert stub["status"] == "planned_stub_only"
    assert stub["fetch_live_data"] is False
    assert stub["action_controls"] is False
    assert "No live progress stream yet" in stub["empty_state"]


def test_markdown_contains_sections_and_boundaries():
    report = build_run_progress_visibility_report(created_at="t")
    md = render_run_progress_visibility_markdown(report)
    low = md.lower()

    for section in (
        "## summary",
        "## stage contract",
        "## safety rules",
        "## ui stub plan",
        "## warnings",
        "## blocked reasons",
        "## recommended next phase",
    ):
        assert section in low, section
    assert "does not run validation" in low
    assert "does not apply patches" in low
    assert "does not launch workers" in low


def test_cli_writes_report_and_prints_summary_json(tmp_path, capsys):
    out = tmp_path / "out"
    code = script.main(
        [
            "--output-dir",
            str(out),
            "--report-id",
            "cli",
            "--created-at",
            "2026-07-09T00:00:00+09:00",
            "--json",
        ]
    )

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_kind"] == "run_progress_visibility"
    assert printed["status"] == READY_WITH_WARNINGS
    assert Path(printed["json_path"]).is_file()
    assert Path(printed["md_path"]).is_file()


def test_registry_marks_ux_run_1_complete_and_adds_ux_run_2_proposed():
    registry_path = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"
    data = load_phase_registry(registry_path)
    result = validate_phase_registry(data)
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert result["is_valid"] is True, result["errors"]
    assert by_id["UX.RUN.1"]["status"] == "complete"
    assert by_id["UX.RUN.1"]["expected_artifacts"] == [
        ".agent/ux/run_progress_visibility/run_progress_visibility_report.json",
        ".agent/ux/run_progress_visibility/run_progress_visibility_report.md",
    ]
    assert by_id["UX.RUN.2"]["status"] == "proposed"
    assert by_id["UX.RUN.2"]["title"] == "Run Progress Snapshot Loader"
    assert by_id["UX.RUN.2"]["prerequisites"] == ["UX.RUN.1"]


def test_phase_picker_recommends_ux_run_2():
    registry_path = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"
    data = load_phase_registry(registry_path)
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="r", created_at="t")

    assert report["top_recommendation"]["phase_id"] == "UX.RUN.2"
    safe_ids = [phase["phase_id"] for phase in report["safe_to_prepare"]]
    assert safe_ids[:2] == ["UX.RUN.2", "MIRROR.13"]


def test_guardrails_have_all_runtime_power_flags_false():
    report = build_run_progress_visibility_report(created_at="t")

    for flag in SAFETY_CONTEXT_FALSE_FLAGS:
        assert report["guardrails"][flag] is False, flag


def test_core_imports_are_stdlib_only():
    core_path = Path(__file__).parent.parent / "core" / "run_progress_visibility.py"
    source = core_path.read_text(encoding="utf-8")
    allowed_top = {"__future__", "copy", "json", "pathlib", "typing"}
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".")[0] in allowed_top, module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_top, alias.name


def test_no_forbidden_runtime_integrations_in_source():
    core_path = Path(__file__).parent.parent / "core" / "run_progress_visibility.py"
    script_path = Path(__file__).parent.parent / "scripts" / "create_run_progress_visibility_report.py"
    source = core_path.read_text(encoding="utf-8") + "\n" + script_path.read_text(encoding="utf-8")

    for bad in (
        "subprocess",
        "Popen",
        "os.system",
        "requests",
        "httpx",
        "socket",
        "sqlite3",
        "apply_patch(",
        "run_safe_validation",
        "run_benchmarks(",
        "launch_worker(",
        "spawn_worker",
        "route_model",
        "approval_token",
    ):
        assert bad not in source, bad


def test_guardrail_note_is_read_only():
    assert "read-only" in GUARDRAIL_NOTE.lower()
    assert "does not call models" in GUARDRAIL_NOTE.lower()
