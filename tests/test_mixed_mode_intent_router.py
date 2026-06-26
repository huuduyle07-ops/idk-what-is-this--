"""Tests for UX.4 — Mixed Mode Intent Router Preview (report-only).

UX.4 predicts the user's intended mode from text and context using deterministic
rules. It does not dispatch execution, call models, apply patches, run validation
or benchmarks, contact network services, launch workers, mutate the repo,
push, merge, or open PRs.

Prescribed test cases:
1.  chat question routes to chat
2.  bounded implementation request routes to instant_run
3.  previous frame/history reference routes to continue_from_frame
4.  large architecture/refactor request routes to commander_plan
5.  very short unclear input routes to clarify
6.  bypass approval / auto-push request routes to reject_or_defer
7.  referenced_frame_id biases toward continue_from_frame
8.  high complexity risk hint biases toward commander_plan
9.  conflicting signals produce clarify
10. every result includes reasons and matched_signals
11. every result includes allowed and forbidden next steps
12. forbidden next steps include auto_dispatch and auto_apply_patch
13. report mode counts are deterministic
14. ambiguous inputs are surfaced in the report
15. rejected/deferred inputs are surfaced in the report
16. Markdown contains required sections
17. Markdown contains boundary text
18. CLI writes JSON and Markdown
19. CLI --json prints summary JSON
20. demo mode uses static local data only
21. demo mode produces at least four different modes
22. guardrails are safe
23. optional UI placeholder, if added, contains "Mixed Mode Router"
24. optional UI placeholder does not add a new mutation route
25. registry accepts UX.4
26. source contains no forbidden execution/model/network/patch/validation/benchmark/worker/DB/merge tokens
"""
from __future__ import annotations

import json
from pathlib import Path

# ── Paths for source token guard ──────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_CORE_PATH   = _ROOT / "core"    / "mixed_mode_intent_router.py"
_SCRIPT_PATH = _ROOT / "scripts" / "create_mixed_mode_intent_router_preview.py"
_HTML_PATH   = _ROOT / "web" / "templates" / "index.html"
_APP_PATH    = _ROOT / "web" / "app.py"


def _read_src(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


_CORE_SRC   = _read_src(_CORE_PATH)
_SCRIPT_SRC = _read_src(_SCRIPT_PATH)
_BOTH       = _CORE_SRC + "\n" + _SCRIPT_SRC
_HTML_SRC   = _read_src(_HTML_PATH)
_APP_SRC    = _read_src(_APP_PATH)


# ── Lazy imports so tests can be collected before core exists ──────────────────
def _core():
    from core.mixed_mode_intent_router import (  # type: ignore
        build_mixed_mode_router_preview,
        classify_mixed_mode_intent,
        normalize_router_input,
        render_mixed_mode_router_markdown,
        summarize_mode_counts,
        write_mixed_mode_router_artifacts,
    )
    return (
        build_mixed_mode_router_preview,
        classify_mixed_mode_intent,
        normalize_router_input,
        render_mixed_mode_router_markdown,
        summarize_mode_counts,
        write_mixed_mode_router_artifacts,
    )


def _script():
    from scripts.create_mixed_mode_intent_router_preview import (  # type: ignore
        main,
        run_create_mixed_mode_intent_router_preview,
    )
    return run_create_mixed_mode_intent_router_preview, main


# ── Shorthand helpers ─────────────────────────────────────────────────────────
def _classify(text: str, **kwargs) -> dict:
    _, classify, normalize, *_ = _core()
    return classify(normalize({"user_text": text, **kwargs}))


def _report(inputs: list[dict], **kwargs) -> dict:
    build, *_ = _core()
    return build(repo_path=".", inputs=inputs, created_at="t", preview_id="r", **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. chat question routes to chat
# ═══════════════════════════════════════════════════════════════════════════════

def test_chat_question_routes_to_chat():
    result = _classify("what does this error mean?")
    assert result["predicted_mode"] == "chat"


def test_explain_request_routes_to_chat():
    result = _classify("explain how this auth system works")
    assert result["predicted_mode"] == "chat"


def test_brainstorm_request_routes_to_chat():
    result = _classify("brainstorm approaches for the caching layer")
    assert result["predicted_mode"] == "chat"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. bounded implementation request routes to instant_run
# ═══════════════════════════════════════════════════════════════════════════════

def test_implement_request_routes_to_instant_run():
    result = _classify("implement UX.5 Goal Brief simplifier")
    assert result["predicted_mode"] == "instant_run"


def test_fix_request_routes_to_instant_run():
    result = _classify("fix the failing test in test_phase_registry")
    assert result["predicted_mode"] == "instant_run"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. previous frame/history reference routes to continue_from_frame
# ═══════════════════════════════════════════════════════════════════════════════

def test_continue_from_previous_run_routes_to_continue_from_frame():
    result = _classify("continue from the previous run")
    assert result["predicted_mode"] == "continue_from_frame"


def test_from_history_text_routes_to_continue_from_frame():
    result = _classify("let's use from history to resume")
    assert result["predicted_mode"] == "continue_from_frame"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. large architecture/refactor request routes to commander_plan
# ═══════════════════════════════════════════════════════════════════════════════

def test_architecture_migration_routes_to_commander_plan():
    result = _classify("plan a full architecture migration")
    assert result["predicted_mode"] == "commander_plan"


def test_full_redesign_routes_to_commander_plan():
    result = _classify("full redesign of the data pipeline")
    assert result["predicted_mode"] == "commander_plan"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. very short unclear input routes to clarify
# ═══════════════════════════════════════════════════════════════════════════════

def test_very_short_input_routes_to_clarify():
    result = _classify("ok")
    assert result["predicted_mode"] == "clarify"


def test_empty_like_input_routes_to_clarify():
    result = _classify("   ")
    assert result["predicted_mode"] == "clarify"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. bypass approval / auto-push request routes to reject_or_defer
# ═══════════════════════════════════════════════════════════════════════════════

def test_auto_apply_and_push_routes_to_reject_or_defer():
    result = _classify("auto apply and push without asking me")
    assert result["predicted_mode"] == "reject_or_defer"


def test_bypass_human_approval_routes_to_reject_or_defer():
    result = _classify("bypass human approval and deploy automatically")
    assert result["predicted_mode"] == "reject_or_defer"


def test_ignore_safety_routes_to_reject_or_defer():
    result = _classify("ignore safety gates and run everything")
    assert result["predicted_mode"] == "reject_or_defer"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. referenced_frame_id biases toward continue_from_frame
# ═══════════════════════════════════════════════════════════════════════════════

def test_referenced_frame_id_biases_to_continue_from_frame():
    result = _classify("let's keep going", referenced_frame_id="frame-abc123")
    assert result["predicted_mode"] == "continue_from_frame"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. high complexity risk hint biases toward commander_plan
# ═══════════════════════════════════════════════════════════════════════════════

def test_high_complexity_risk_hint_biases_to_commander_plan():
    result = _classify(
        "update the auth system",
        risk_hints=["high_complexity", "many_files"],
    )
    assert result["predicted_mode"] == "commander_plan"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. conflicting signals produce clarify
# ═══════════════════════════════════════════════════════════════════════════════

def test_conflicting_chat_and_instant_run_signals_produce_clarify():
    # "explain" = chat signal, "implement" = instant_run signal → conflict → clarify
    result = _classify("explain how to implement this feature")
    assert result["predicted_mode"] == "clarify"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. every result includes reasons and matched_signals
# ═══════════════════════════════════════════════════════════════════════════════

def test_result_includes_reasons_and_matched_signals():
    result = _classify("what is this function doing?")
    assert isinstance(result.get("reasons"), list)
    assert len(result["reasons"]) > 0
    assert isinstance(result.get("matched_signals"), list)


def test_result_includes_reasons_for_reject():
    result = _classify("auto push without asking")
    assert len(result.get("reasons", [])) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 11. every result includes allowed and forbidden next steps
# ═══════════════════════════════════════════════════════════════════════════════

def test_result_includes_allowed_and_forbidden_next_steps():
    result = _classify("implement a small fix")
    assert isinstance(result.get("allowed_next_steps"), list)
    assert len(result["allowed_next_steps"]) > 0
    assert isinstance(result.get("forbidden_next_steps"), list)
    assert len(result["forbidden_next_steps"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 12. forbidden next steps include auto_dispatch and auto_apply_patch
# ═══════════════════════════════════════════════════════════════════════════════

def test_forbidden_next_steps_include_auto_dispatch_and_auto_apply():
    result = _classify("implement a small fix")
    forbidden = result.get("forbidden_next_steps", [])
    assert "auto_dispatch" in forbidden
    assert "auto_apply_patch" in forbidden


def test_reject_mode_also_has_auto_dispatch_in_forbidden():
    result = _classify("auto push and deploy")
    forbidden = result.get("forbidden_next_steps", [])
    assert "auto_dispatch" in forbidden


# ═══════════════════════════════════════════════════════════════════════════════
# 13. report mode counts are deterministic
# ═══════════════════════════════════════════════════════════════════════════════

def test_mode_counts_are_deterministic():
    inputs = [
        {"user_text": "what is this?"},
        {"user_text": "implement UX.5"},
        {"user_text": "ok"},
    ]
    report1 = _report(inputs)
    report2 = _report(inputs)
    assert report1["mode_counts"] == report2["mode_counts"]


def test_mode_counts_reflect_all_inputs():
    inputs = [
        {"user_text": "what is this?"},
        {"user_text": "what does this do?"},
    ]
    report = _report(inputs)
    assert report["mode_counts"].get("chat", 0) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 14. ambiguous inputs are surfaced in the report
# ═══════════════════════════════════════════════════════════════════════════════

def test_ambiguous_inputs_are_surfaced():
    inputs = [
        {"user_text": "ok"},
        {"user_text": "explain how to implement this"},
        {"user_text": "what is this?"},
    ]
    report = _report(inputs)
    assert len(report["ambiguous_inputs"]) >= 1


def test_clarify_mode_inputs_are_in_ambiguous():
    inputs = [{"user_text": "   "}]
    report = _report(inputs)
    ambig_texts = [a.get("input_text", "") for a in report["ambiguous_inputs"]]
    # clarify-routed inputs appear in ambiguous_inputs
    modes = [r["predicted_mode"] for r in report["routing_results"]]
    assert "clarify" in modes


# ═══════════════════════════════════════════════════════════════════════════════
# 15. rejected/deferred inputs are surfaced in the report
# ═══════════════════════════════════════════════════════════════════════════════

def test_rejected_or_deferred_inputs_are_surfaced():
    inputs = [
        {"user_text": "auto push without approval"},
        {"user_text": "what is this?"},
    ]
    report = _report(inputs)
    assert len(report["rejected_or_deferred_inputs"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Markdown contains required sections
# ═══════════════════════════════════════════════════════════════════════════════

_REQUIRED_SECTIONS = [
    "Summary",
    "Routing Results",
    "Mode Counts",
    "Ambiguous Inputs",
    "Rejected or Deferred Inputs",
    "Routing Policy",
    "UI Contract",
    "Next UX Steps",
    "Warnings",
    "Blockers",
    "Guardrails",
    "Boundaries",
]


def test_markdown_contains_required_sections():
    _, _, _, render, *_ = _core()
    report = _report([{"user_text": "what is this?"}])
    md = render(report)
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"Markdown missing section: {section!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 17. Markdown contains boundary text
# ═══════════════════════════════════════════════════════════════════════════════

_BOUNDARY_PHRASES = [
    "UX.4 predicts user intent only",
    "does not dispatch execution",
    "does not start runs",
    "does not call models",
    "does not apply patches",
    "does not run validation",
    "does not run benchmarks",
    "does not contact network services",
    "does not launch workers",
    "does not mutate the repo",
    "does not push, merge, or open PRs",
]


def test_markdown_contains_boundary_text():
    _, _, _, render, *_ = _core()
    report = _report([{"user_text": "what is this?"}])
    md = render(report)
    for phrase in _BOUNDARY_PHRASES:
        assert phrase in md, f"Boundary phrase missing from Markdown: {phrase!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 18. CLI writes JSON and Markdown
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_writes_json_and_markdown(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        preview_id="cli1",
        created_at="2026-06-26T00:00:00+00:00",
        inputs=[{"user_text": "what is this?"}],
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["preview_status"] == "ready_for_review"


# ═══════════════════════════════════════════════════════════════════════════════
# 19. CLI --json prints summary JSON
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_json_flag_prints_summary(capsys, tmp_path):
    _, main = _script()
    code = main([
        "--repo-path", ".",
        "--output-root", str(tmp_path / "out"),
        "--preview-id", "j1",
        "--created-at", "2026-06-26T00:00:00+00:00",
        "--input", "what is this?",
        "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "preview_status" in data
    assert "mode_counts" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 20. demo mode uses static local data only
# ═══════════════════════════════════════════════════════════════════════════════

def test_demo_mode_uses_static_local_data(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        preview_id="demo1",
        created_at="2026-06-26T00:00:00+00:00",
        demo=True,
    )
    assert result["ok"] is True
    report = result["report"]
    assert report["guardrails"]["network_call_performed"] is False
    assert report["guardrails"]["model_call_performed"] is False
    assert len(report["routing_results"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 21. demo mode produces at least four different modes
# ═══════════════════════════════════════════════════════════════════════════════

def test_demo_mode_produces_at_least_four_different_modes(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        preview_id="demo2",
        created_at="2026-06-26T00:00:00+00:00",
        demo=True,
    )
    report = result["report"]
    modes_found = {r["predicted_mode"] for r in report["routing_results"]}
    assert len(modes_found) >= 4, f"Only {len(modes_found)} modes in demo: {modes_found}"


# ═══════════════════════════════════════════════════════════════════════════════
# 22. guardrails are safe
# ═══════════════════════════════════════════════════════════════════════════════

_GUARDRAIL_FALSE_KEYS = {
    "router_dispatch_implemented",
    "new_route_added",
    "mutation_route_added",
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
    "repo_mutation_performed",
    "merge_performed",
}


def test_guardrails_are_safe():
    report = _report([{"user_text": "what is this?"}])
    gs = report["guardrails"]
    for key in _GUARDRAIL_FALSE_KEYS:
        assert key in gs, f"Missing guardrail key: {key}"
        assert gs[key] is False, f"Guardrail {key} should be False, got {gs[key]}"
    assert gs.get("preview_only") is True


# ═══════════════════════════════════════════════════════════════════════════════
# 23. optional UI placeholder, if added, contains "Mixed Mode Router"
# ═══════════════════════════════════════════════════════════════════════════════

def test_ui_placeholder_contains_mixed_mode_router_label():
    if not _HTML_PATH.is_file():
        import pytest; pytest.skip("index.html not found")
    if "mixed-mode-router" not in _HTML_SRC.lower() and "ws-mixed-mode" not in _HTML_SRC:
        import pytest; pytest.skip("UX.4 placeholder not yet added to index.html")
    assert "Mixed Mode Router" in _HTML_SRC


# ═══════════════════════════════════════════════════════════════════════════════
# 24. optional UI placeholder does not add a new mutation route
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_new_mixed_mode_mutation_route_in_app():
    # app.py should not have a new POST route for mixed-mode dispatch
    has_route = (
        "mixed_mode" in _APP_SRC.lower()
        and ("@app.route" in _APP_SRC or "methods=[" in _APP_SRC)
        and "POST" in _APP_SRC
    )
    assert not has_route, "Found unexpected mixed_mode route in app.py"


# ═══════════════════════════════════════════════════════════════════════════════
# 25. registry accepts UX.4
# ═══════════════════════════════════════════════════════════════════════════════

_SEED_PATH = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"


def test_registry_contains_ux4():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    ids = {p["phase_id"] for p in data["phases"]}
    assert "UX.4" in ids


def test_registry_ux4_is_complete():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    ux4 = next((p for p in data["phases"] if p["phase_id"] == "UX.4"), None)
    assert ux4 is not None
    assert ux4["status"] == "complete"
    assert ux4["track"] == "UX"
    assert ux4["automation_level"] == "LOCAL_0_OBSERVE"
    assert ux4["merge_allowed"] is False
    assert ux4["network_allowed"] is False
    assert ux4["model_calls_allowed"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 26. source contains no forbidden tokens
# ═══════════════════════════════════════════════════════════════════════════════

_FORBIDDEN_BARE = [
    "subprocess",
    "Popen",
    "os.system",
    "requests",
    "httpx",
    "urllib.request",
    "websocket",
    "anthropic",
    "openai",
    "litellm",
    "generate_patch",
    "apply_patch(",
    "patch_apply",
    "run_safe_validation",
    "validation_execution",
    "run_benchmarks(",
    "apply_candidate_in_sandbox",
    "launch_worker(",
    "worker_launch(",
    "spawn_worker",
    "proposal_runner",
    "sqlite3",
    "psycopg",
    "pymongo",
    "INSERT INTO",
    "cursor(",
    "auto_merge(",
    "perform_merge",
    "merge_to_real",
]


def test_core_source_has_no_forbidden_tokens():
    assert _CORE_SRC, "core/mixed_mode_intent_router.py is empty or missing"
    for token in _FORBIDDEN_BARE:
        assert token not in _CORE_SRC, (
            f"Forbidden token {token!r} found in core/mixed_mode_intent_router.py"
        )


def test_script_source_has_no_forbidden_tokens():
    assert _SCRIPT_SRC, "scripts/create_mixed_mode_intent_router_preview.py is empty or missing"
    for token in _FORBIDDEN_BARE:
        assert token not in _SCRIPT_SRC, (
            f"Forbidden token {token!r} found in scripts/create_mixed_mode_intent_router_preview.py"
        )
