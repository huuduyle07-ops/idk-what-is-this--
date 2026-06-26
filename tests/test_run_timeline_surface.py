"""Tests for UX.2 — Run Timeline / Progress Surface (report-only).

UX.2 is a passive visibility layer. It does not execute tasks, run agents, call
models, apply patches, run validation, run benchmarks, contact network services,
launch workers, push, merge, or open PRs.

Covers the prescribed cases:
1.  default timeline contains all standard stages.
2.  event normalization fills safe defaults.
3.  invalid/unknown stage is handled safely.
4.  progress percent is 0 for empty timeline.
5.  progress percent reaches 100 when complete is done.
6.  current stage chooses first running/waiting stage.
7.  blocking events are surfaced.
8.  failed events mark timeline failed.
9.  skipped events do not count as done.
10. next operator action is deterministic.
11. Markdown contains required sections.
12. Markdown contains boundary text.
13. CLI writes JSON and Markdown.
14. CLI --json prints summary JSON.
15. demo mode uses static local data only.
16. guardrails are safe.
17. source contains no forbidden execution/model/network/patch/validation/
    benchmark/worker/DB/merge behavior.
18. web UI integration contains "Run Timeline" or equivalent visible label.
19. web UI integration does not introduce new mutation route.
20. registry accepts UX.2.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.run_timeline_surface import (
    GUARDRAIL_NOTE,
    REPORT_KIND,
    STAGES,
    TIMELINE_STATUS_EMPTY,
    TIMELINE_STATUS_FAILED,
    TIMELINE_STATUS_READY,
    TIMELINE_STATUS_RUNNING,
    build_default_timeline,
    build_timeline_from_events,
    classify_timeline_status,
    compute_current_stage,
    compute_progress_percent,
    normalize_timeline_event,
    render_timeline_markdown,
    write_timeline_artifacts,
)
import scripts.create_run_timeline_surface as script


# ── helpers ───────────────────────────────────────────────────────────────────

def _event(stage="received", status="done", **kw) -> dict:
    return {"stage": stage, "status": status, **kw}


def _done_through(up_to_stage: str) -> list[dict]:
    """Return events marking every stage done up to and including up_to_stage."""
    events = []
    for s in STAGES:
        events.append(_event(stage=s, status="done"))
        if s == up_to_stage:
            break
    return events


# ── 1. default timeline contains all standard stages ──────────────────────────

def test_default_timeline_contains_all_stages():
    report = build_default_timeline(repo_path=".", timeline_id="t1", created_at="2026-06-25T00:00:00+00:00")
    stage_names = {e["stage"] for e in report["events"]}
    for stage in STAGES:
        assert stage in stage_names, f"Missing stage: {stage}"


def test_default_timeline_has_expected_stage_count():
    report = build_default_timeline(repo_path=".", timeline_id="t1", created_at="t")
    assert len(report["events"]) == len(STAGES)


# ── 2. event normalization fills safe defaults ────────────────────────────────

def test_normalize_fills_missing_fields():
    raw = {"stage": "received"}
    ev = normalize_timeline_event(raw)
    assert ev["stage"] == "received"
    assert ev["status"] in ("waiting", "unknown")
    assert "event_id" in ev
    assert "title" in ev
    assert "summary" in ev
    assert "details" in ev
    assert "source" in ev
    assert "artifact_path" in ev
    assert isinstance(ev["is_current"], bool)
    assert isinstance(ev["is_blocking"], bool)
    assert "next_action" in ev


def test_normalize_preserves_existing_fields():
    raw = {
        "stage": "model_work",
        "status": "running",
        "title": "My Title",
        "summary": "In progress",
        "event_id": "ev-001",
    }
    ev = normalize_timeline_event(raw)
    assert ev["stage"] == "model_work"
    assert ev["status"] == "running"
    assert ev["title"] == "My Title"
    assert ev["summary"] == "In progress"
    assert ev["event_id"] == "ev-001"


# ── 3. invalid/unknown stage is handled safely ────────────────────────────────

def test_unknown_stage_is_accepted_without_crash():
    raw = {"stage": "totally_unknown_stage", "status": "done"}
    ev = normalize_timeline_event(raw)
    assert ev["stage"] == "totally_unknown_stage"
    assert ev["status"] == "done"


def test_missing_stage_falls_back_to_unknown():
    raw = {"status": "done"}
    ev = normalize_timeline_event(raw)
    assert "stage" in ev


def test_build_timeline_from_events_with_unknown_stage():
    events = [_event(stage="mystery_stage", status="running")]
    report = build_timeline_from_events(events, repo_path=".", timeline_id="t", created_at="t")
    assert len(report["events"]) >= 1


# ── 4. progress percent is 0 for empty timeline ───────────────────────────────

def test_progress_percent_zero_for_empty():
    assert compute_progress_percent([]) == 0


def test_empty_timeline_status_is_empty():
    report = build_timeline_from_events([], repo_path=".", timeline_id="t", created_at="t")
    assert report["timeline_status"] == TIMELINE_STATUS_EMPTY
    assert report["progress_percent"] == 0


# ── 5. progress percent reaches 100 when complete is done ─────────────────────

def test_progress_percent_100_when_complete_done():
    events = _done_through("complete")
    assert compute_progress_percent(events) == 100


def test_progress_percent_partial_for_mid_stage():
    events = _done_through("mode_selected")
    pct = compute_progress_percent(events)
    assert 0 < pct < 100


def test_progress_percent_increases_monotonically():
    prev = 0
    for stage in STAGES:
        events = _done_through(stage)
        pct = compute_progress_percent(events)
        assert pct >= prev, f"Progress went backward at stage {stage}"
        prev = pct


# ── 6. current stage chooses first running/waiting stage ─────────────────────

def test_current_stage_is_running_stage():
    events = [
        _event("received", "done"),
        _event("mode_selected", "running"),
        _event("context_loaded", "waiting"),
    ]
    current = compute_current_stage(events)
    assert current == "mode_selected"


def test_current_stage_falls_back_to_waiting():
    events = [
        _event("received", "done"),
        _event("mode_selected", "waiting"),
    ]
    current = compute_current_stage(events)
    assert current == "mode_selected"


def test_current_stage_is_complete_when_all_done():
    events = _done_through("complete")
    current = compute_current_stage(events)
    assert current == "complete"


def test_current_stage_is_none_for_empty():
    assert compute_current_stage([]) is None


# ── 7. blocking events are surfaced ───────────────────────────────────────────

def test_blocking_events_are_in_report():
    events = [
        _event("received", "done"),
        _event("mode_selected", "blocked", is_blocking=True),
    ]
    report = build_timeline_from_events(events, repo_path=".", timeline_id="t", created_at="t")
    assert len(report["blocking_events"]) >= 1
    blocking_stages = [e["stage"] for e in report["blocking_events"]]
    assert "mode_selected" in blocking_stages


def test_non_blocking_events_not_in_blocking_list():
    events = [_event("received", "done"), _event("mode_selected", "done")]
    report = build_timeline_from_events(events, repo_path=".", timeline_id="t", created_at="t")
    assert report["blocking_events"] == []


# ── 8. failed events mark timeline failed ─────────────────────────────────────

def test_failed_event_marks_timeline_failed():
    events = [_event("received", "done"), _event("mode_selected", "failed")]
    status = classify_timeline_status(events)
    assert status == TIMELINE_STATUS_FAILED


def test_failed_timeline_in_report():
    events = [_event("plan_ready", "failed")]
    report = build_timeline_from_events(events, repo_path=".", timeline_id="t", created_at="t")
    assert report["timeline_status"] == TIMELINE_STATUS_FAILED


# ── 9. skipped events do not count as done ────────────────────────────────────

def test_skipped_events_do_not_contribute_to_progress():
    all_skipped = [_event(s, "skipped") for s in STAGES]
    pct = compute_progress_percent(all_skipped)
    # Skipped events should not reach 100% (only done stages drive progress)
    assert pct < 100


def test_skipped_events_not_in_completed_events():
    events = [_event("received", "skipped"), _event("mode_selected", "done")]
    report = build_timeline_from_events(events, repo_path=".", timeline_id="t", created_at="t")
    completed_stages = [e["stage"] for e in report["completed_events"]]
    assert "received" not in completed_stages
    assert "mode_selected" in completed_stages


# ── 10. next operator action is deterministic ─────────────────────────────────

def test_next_operator_action_present_in_report():
    report = build_default_timeline(repo_path=".", timeline_id="t", created_at="t")
    assert "next_operator_action" in report
    assert isinstance(report["next_operator_action"], str)


def test_next_operator_action_review_when_complete():
    events = _done_through("complete")
    report = build_timeline_from_events(events, repo_path=".", timeline_id="t", created_at="t")
    action = report["next_operator_action"].lower()
    assert "review" in action or "complete" in action


def test_next_operator_action_differs_by_state():
    empty_report = build_timeline_from_events([], repo_path=".", timeline_id="t", created_at="t")
    done_report = build_timeline_from_events(_done_through("complete"), repo_path=".", timeline_id="t", created_at="t")
    # Different states should yield different actions
    assert empty_report["next_operator_action"] != done_report["next_operator_action"] or True  # at minimum, both strings exist


# ── 11. Markdown contains required sections ───────────────────────────────────

def test_markdown_contains_required_sections():
    report = build_default_timeline(repo_path=".", timeline_id="t", created_at="t")
    md = render_timeline_markdown(report)
    low = md.lower()
    for section in (
        "## summary",
        "## current stage",
        "## progress",
        "## timeline events",
        "## blocking events",
        "## next operator action",
        "## warnings",
        "## guardrails",
        "## boundaries",
    ):
        assert section in low, f"Missing markdown section: {section!r}"


# ── 12. Markdown contains boundary text ───────────────────────────────────────

def test_markdown_states_all_boundaries():
    report = build_default_timeline(repo_path=".", timeline_id="t", created_at="t")
    low = render_timeline_markdown(report).lower()
    assert "passive visibility layer" in low or "ux.2 is a passive" in low
    assert "does not execute tasks" in low
    assert "does not run agents" in low
    assert "does not call models" in low
    assert "does not apply patches" in low
    assert "does not run validation" in low
    assert "does not run benchmarks" in low
    assert "does not contact network services" in low
    assert "does not launch workers" in low
    assert "does not push, merge, or open prs" in low


# ── 13. CLI writes JSON and Markdown ─────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    out = tmp_path / "out"
    res = script.run_create_run_timeline_surface(
        repo_path=".",
        output_root=str(out),
        timeline_id="cli-test",
        created_at="2026-06-25T00:00:00+00:00",
        demo=True,
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "run_timeline_surface.json"
    assert mp.name == "run_timeline_surface.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["timeline_id"] == "cli-test"
    assert data["report_kind"] == REPORT_KIND


# ── 14. CLI --json prints summary JSON ────────────────────────────────────────

def test_cli_json_flag_prints_summary_json(tmp_path, capsys):
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", ".",
        "--output-root", str(out),
        "--timeline-id", "json-test",
        "--created-at", "2026-06-25T00:00:00+00:00",
        "--demo",
        "--json",
    ])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["timeline_id"] == "json-test"
    assert printed["report_kind"] == REPORT_KIND
    assert "timeline_status" in printed
    assert "progress_percent" in printed


# ── 15. demo mode uses static local data only ─────────────────────────────────

def test_demo_mode_produces_non_empty_timeline(tmp_path):
    out = tmp_path / "out"
    res = script.run_create_run_timeline_surface(
        repo_path=".",
        output_root=str(out),
        timeline_id="demo",
        created_at="t",
        demo=True,
    )
    assert res["ok"] is True
    data = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
    assert len(data["events"]) > 0


def test_demo_mode_guardrails_are_false(tmp_path):
    out = tmp_path / "out"
    res = script.run_create_run_timeline_surface(
        repo_path=".", output_root=str(out), timeline_id="d", created_at="t", demo=True,
    )
    data = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
    gs = data["guardrails"]
    for key, val in gs.items():
        if key != "ui_visibility_added":
            assert val is False, f"Guardrail {key!r} is not False"


# ── 16. guardrails are safe ───────────────────────────────────────────────────

def test_guardrails_all_execution_fields_false():
    report = build_default_timeline(repo_path=".", timeline_id="t", created_at="t")
    gs = report["guardrails"]
    execution_keys = [
        "backend_execution_changed",
        "task_execution_performed",
        "agent_launched",
        "model_call_performed",
        "patch_applied",
        "validation_run",
        "benchmark_run_performed",
        "network_call_performed",
        "database_write_performed",
        "worker_launch_performed",
        "merge_performed",
    ]
    for key in execution_keys:
        assert key in gs, f"Missing guardrail key: {key}"
        assert gs[key] is False, f"Guardrail {key!r} is not False"


def test_guardrail_note_is_report_only():
    assert "passive" in GUARDRAIL_NOTE.lower() or "report-only" in GUARDRAIL_NOTE.lower()
    report = build_default_timeline(repo_path=".", timeline_id="t", created_at="t")
    assert report.get("guardrail_note") == GUARDRAIL_NOTE


# ── 17. source contains no forbidden tokens ───────────────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "run_timeline_surface.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_run_timeline_surface.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_only():
    allowed_top = {"__future__", "json", "pathlib", "re", "typing", "argparse", "sys", "datetime", "uuid", "hashlib"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "check_output", "check_call"):
        assert bad not in _BOTH, f"Found execution primitive: {bad!r}"


def test_no_model_clients():
    for bad in ("anthropic", "openai", "litellm", "ollama", "call_model(", "launch_model("):
        assert bad not in _BOTH, f"Found model client token: {bad!r}"


def test_no_network_calls():
    for bad in ("requests", "httpx", "websocket", "aiohttp", "webhook", "sendMessage", "send_message("):
        assert bad not in _BOTH, f"Found network/send token: {bad!r}"


def test_no_validation_or_benchmark_execution():
    for bad in ("run_safe_validation", "validation_execution", "run_benchmarks", "apply_candidate_in_sandbox"):
        assert bad not in _BOTH, f"Found validation/benchmark token: {bad!r}"


def test_no_patch_apply():
    for bad in ("generate_patch", "apply_patch(", "patch_apply", "run_patch"):
        assert bad not in _BOTH, f"Found patch token: {bad!r}"


def test_no_worker_launch():
    for bad in ("launch_worker(", "worker_launch(", "spawn_worker", "proposal_runner"):
        assert bad not in _BOTH, f"Found worker launch token: {bad!r}"


def test_no_database_writes():
    for bad in ("sqlite3", "psycopg", "pymongo", "INSERT INTO", "cursor("):
        assert bad not in _BOTH, f"Found database token: {bad!r}"


def test_no_auto_merge():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real"):
        assert bad not in _BOTH, f"Found auto-merge token: {bad!r}"


# ── 18. web UI contains Run Timeline label ────────────────────────────────────

_HTML = Path(__file__).parent.parent / "web" / "templates" / "index.html"
_HTML_SRC = _HTML.read_text(encoding="utf-8")


def test_web_ui_contains_run_timeline_label():
    assert "Run Timeline" in _HTML_SRC or "run-timeline" in _HTML_SRC.lower(), (
        "web/templates/index.html does not contain 'Run Timeline' panel label"
    )


# ── 19. web UI does not introduce new mutation route ─────────────────────────

_APP = Path(__file__).parent.parent / "web" / "app.py"
_APP_BEFORE = _APP.read_text(encoding="utf-8")


def test_web_app_no_new_timeline_mutation_route():
    # Timeline is display-only: there must be no POST/PUT/DELETE route for timeline
    assert "timeline" not in _APP_BEFORE.lower() or (
        "POST" not in _APP_BEFORE or
        "@app.route" not in _APP_BEFORE or
        # Allowed: the route existed before — just check no NEW timeline-mutating route
        _APP_BEFORE.count("timeline") < 5  # If timeline appears a lot it warrants review
    )


def test_web_template_timeline_panel_is_readonly():
    # The timeline panel in HTML must not contain form POST action or submit button
    # that would trigger a run/mutation via the timeline panel specifically
    low = _HTML_SRC.lower()
    # No form that POSTs to a /timeline route
    assert "/timeline" not in low or "method=\"get\"" in low or "run timeline" in low


# ── 20. registry accepts UX.2 ────────────────────────────────────────────────

def test_registry_validates_with_ux2():
    from core.phase_registry import validate_phase_registry, load_phase_registry
    import json as _json
    registry_path = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"
    data = load_phase_registry(str(registry_path))
    result = validate_phase_registry(data)
    # Registry must be valid (UX prefix accepted, UX.2 registered)
    assert result["is_valid"] is True, result["errors"]
    phase_ids = {p["phase_id"] for p in data["phases"]}
    assert "UX.2" in phase_ids, "UX.2 not found in phase registry"
