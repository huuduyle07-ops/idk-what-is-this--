"""Tests for UX.3 — Continue-from-Frame Contract (report-only).

UX.3 defines the continuation contract for "Continue from Frame." It does not
implement actual continuation execution, start a run from history, call models,
apply patches, run validation, run benchmarks, contact network services, launch
workers, mutate the repo, push, merge, or open PRs.

Prescribed test cases:
1.  default contract status is ready_for_review
2.  frame definition states frame is not a hidden agent state or resumable process
3.  default frame contains required schema fields
4.  reusable context policy includes summaries and artifact references
5.  excluded context policy blocks secrets, tokens, env vars, hidden chain-of-thought, auto-approval
6.  allowed continuation modes include ask/planning/compare/evidence/commander contract
7.  forbidden continuation modes include auto-apply, auto-validation, auto-benchmark, worker, model, push, merge
8.  human confirmation policy requires approval before mutation/execution actions
9.  staleness policy has fresh/possibly_stale/stale/unknown
10. unknown or incomplete frame is normalized safely
11. stale frame produces warning
12. demo mode uses static local data only
13. Markdown contains required sections
14. Markdown contains boundary text
15. CLI writes JSON and Markdown
16. CLI --json prints summary JSON
17. guardrails are safe
18. optional UI placeholder, if added, contains "Continue From Frame"
19. optional UI placeholder does not add a new mutation route
20. registry accepts UX.3
21. source contains no forbidden execution/model/network/patch/validation/benchmark/worker/DB/merge tokens
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

# ── Paths for source token guard ──────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_CORE_PATH   = _ROOT / "core"   / "continue_from_frame_contract.py"
_SCRIPT_PATH = _ROOT / "scripts" / "create_continue_from_frame_contract.py"
_HTML_PATH   = _ROOT / "web" / "templates" / "index.html"
_APP_PATH    = _ROOT / "web" / "app.py"


def _read_src(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


_CORE_SRC   = _read_src(_CORE_PATH)
_SCRIPT_SRC = _read_src(_SCRIPT_PATH)
_BOTH       = _CORE_SRC + "\n" + _SCRIPT_SRC
_HTML_SRC   = _read_src(_HTML_PATH)
_APP_SRC    = _read_src(_APP_PATH)


# ── Lazy imports so tests can be collected even before core exists ─────────────
def _import_core():
    from core.continue_from_frame_contract import (  # type: ignore
        build_continue_from_frame_contract,
        build_default_frame,
        classify_frame_staleness,
        normalize_frame,
        render_continue_from_frame_markdown,
        summarize_excluded_context,
        summarize_reusable_context,
    )
    return (
        build_continue_from_frame_contract,
        build_default_frame,
        classify_frame_staleness,
        normalize_frame,
        render_continue_from_frame_markdown,
        summarize_excluded_context,
        summarize_reusable_context,
    )


def _import_script():
    from scripts.create_continue_from_frame_contract import (  # type: ignore
        main,
        run_create_continue_from_frame_contract,
    )
    return run_create_continue_from_frame_contract, main


# ── Helper ────────────────────────────────────────────────────────────────────
def _build(repo_path=".", **kwargs):
    (build_continue_from_frame_contract, *_) = _import_core()
    return build_continue_from_frame_contract(repo_path=repo_path, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. default contract status is ready_for_review
# ═══════════════════════════════════════════════════════════════════════════════

def test_default_contract_status_is_ready_for_review():
    contract = _build(contract_id="c1", created_at="2026-06-26T00:00:00+00:00")
    assert contract["contract_status"] == "ready_for_review"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. frame definition states frame is not a hidden agent state or resumable process
# ═══════════════════════════════════════════════════════════════════════════════

def test_frame_definition_excludes_agent_state_and_resumable_process():
    contract = _build(contract_id="c2", created_at="t")
    fd = contract["frame_definition"]
    assert isinstance(fd, dict)
    # Must state what a frame IS NOT
    not_items = fd.get("frame_is_not", [])
    assert isinstance(not_items, list)
    texts = " ".join(str(x).lower() for x in not_items)
    assert "hidden agent state" in texts or "agent state" in texts
    assert "resumable process" in texts or "resumable" in texts


# ═══════════════════════════════════════════════════════════════════════════════
# 3. default frame contains required schema fields
# ═══════════════════════════════════════════════════════════════════════════════

_REQUIRED_FRAME_FIELDS = {
    "frame_id", "created_at", "source_type", "source_run_id",
    "source_artifacts", "title", "task_summary", "mode", "repo_path",
    "branch_hint", "changed_files_summary", "patch_summary",
    "evidence_summary", "validation_summary", "benchmark_summary",
    "decision_summary", "reusable_context", "excluded_context",
    "staleness_risk", "safety_flags", "required_confirmations",
    "allowed_continuation_modes", "forbidden_continuation_modes",
    "next_operator_action",
}


def test_default_frame_has_required_schema_fields():
    (_, build_default_frame, *_) = _import_core()
    frame = build_default_frame(repo_path=".", created_at="2026-06-26T00:00:00+00:00")
    missing = _REQUIRED_FRAME_FIELDS - set(frame.keys())
    assert not missing, f"Missing frame fields: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. reusable context policy includes summaries and artifact references
# ═══════════════════════════════════════════════════════════════════════════════

def test_reusable_context_policy_includes_summaries_and_artifact_references():
    contract = _build(contract_id="c4", created_at="t")
    policy = contract["reusable_context_policy"]
    assert isinstance(policy, dict)
    items = " ".join(str(v).lower() for v in policy.values()
                     if isinstance(v, (str, list)))
    # Must include summaries and artifact references
    assert "summary" in items or "summaries" in items
    assert "artifact" in items


# ═══════════════════════════════════════════════════════════════════════════════
# 5. excluded context policy blocks secrets, tokens, env vars, hidden chain-of-thought, auto-approval
# ═══════════════════════════════════════════════════════════════════════════════

def test_excluded_context_policy_blocks_forbidden_items():
    contract = _build(contract_id="c5", created_at="t")
    policy = contract["excluded_context_policy"]
    assert isinstance(policy, dict)
    excluded_items = policy.get("always_excluded", [])
    text = " ".join(str(x).lower() for x in excluded_items)
    assert "secret" in text
    assert "token" in text or "api key" in text or "key" in text
    assert "env" in text or "environment variable" in text
    assert "chain-of-thought" in text or "chain of thought" in text or "hidden" in text
    assert "auto-approval" in text or "auto_approval" in text or "approval" in text


# ═══════════════════════════════════════════════════════════════════════════════
# 6. allowed continuation modes include ask/planning/compare/evidence/commander contract
# ═══════════════════════════════════════════════════════════════════════════════

_EXPECTED_ALLOWED_MODES = {
    "ask_about_frame",
    "continue_planning",
    "draft_next_patch_plan",
    "compare_with_current",
    "open_evidence_review",
    "create_commander_contract",
}


def test_allowed_continuation_modes_include_expected_modes():
    contract = _build(contract_id="c6", created_at="t")
    modes = set(contract["allowed_continuation_modes"])
    assert _EXPECTED_ALLOWED_MODES <= modes


# ═══════════════════════════════════════════════════════════════════════════════
# 7. forbidden continuation modes include auto-apply, auto-validation, auto-benchmark, worker, model, push, merge
# ═══════════════════════════════════════════════════════════════════════════════

_EXPECTED_FORBIDDEN_MODES = {
    "auto_apply_patch",
    "auto_run_validation",
    "auto_run_benchmark",
    "auto_launch_worker",
    "auto_call_model",
    "auto_merge",
    "auto_push",
    "remote_execute",
}


def test_forbidden_continuation_modes_include_dangerous_modes():
    contract = _build(contract_id="c7", created_at="t")
    modes = set(contract["forbidden_continuation_modes"])
    assert _EXPECTED_FORBIDDEN_MODES <= modes


# ═══════════════════════════════════════════════════════════════════════════════
# 8. human confirmation policy requires approval before mutation/execution actions
# ═══════════════════════════════════════════════════════════════════════════════

_CONFIRMATION_ACTIONS = {
    "apply_patch", "run_validation", "run_benchmark", "launch_worker",
    "commit", "push", "merge",
}


def test_human_confirmation_policy_requires_approval_before_mutations():
    contract = _build(contract_id="c8", created_at="t")
    policy = contract["human_confirmation_policy"]
    assert isinstance(policy, dict)
    required_before = policy.get("required_before", [])
    texts = " ".join(str(x).lower() for x in required_before)
    for action in ("patch", "validation", "benchmark", "commit", "push", "merge"):
        assert action in texts, f"'{action}' missing from required_before"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. staleness policy has fresh/possibly_stale/stale/unknown
# ═══════════════════════════════════════════════════════════════════════════════

_EXPECTED_STALENESS = {"fresh", "possibly_stale", "stale", "unknown"}


def test_staleness_policy_has_all_four_classes():
    contract = _build(contract_id="c9", created_at="t")
    policy = contract["staleness_policy"]
    assert isinstance(policy, dict)
    classes = set(policy.get("staleness_classes", {}).keys())
    assert _EXPECTED_STALENESS <= classes


# ═══════════════════════════════════════════════════════════════════════════════
# 10. unknown or incomplete frame is normalized safely
# ═══════════════════════════════════════════════════════════════════════════════

def test_normalize_frame_handles_empty_dict():
    (_, _, _, normalize_frame, *_) = _import_core()
    frame = normalize_frame({})
    # Must return a dict with at minimum all required fields
    missing = _REQUIRED_FRAME_FIELDS - set(frame.keys())
    assert not missing, f"normalize_frame({{}}) missing fields: {missing}"


def test_normalize_frame_handles_partial_dict():
    (_, _, _, normalize_frame, *_) = _import_core()
    raw = {"title": "My Frame", "repo_path": "/x"}
    frame = normalize_frame(raw)
    assert frame["title"] == "My Frame"
    assert frame["repo_path"] == "/x"
    # No crash, all required fields present
    missing = _REQUIRED_FRAME_FIELDS - set(frame.keys())
    assert not missing


# ═══════════════════════════════════════════════════════════════════════════════
# 11. stale frame produces warning
# ═══════════════════════════════════════════════════════════════════════════════

def test_stale_frame_classification():
    (_, _, classify_frame_staleness, *_) = _import_core()
    stale_frame = {"staleness_risk": "stale", "title": "Old frame"}
    result = classify_frame_staleness(stale_frame)
    assert result["staleness_class"] == "stale"
    assert result["warning"] is not None and len(result["warning"]) > 0


def test_stale_frame_in_contract_produces_warning():
    (_, build_default_frame, *_) = _import_core()
    stale_frame = build_default_frame(repo_path=".", created_at="t")
    stale_frame["staleness_risk"] = "stale"
    (build_continue_from_frame_contract, *_) = _import_core()
    contract = build_continue_from_frame_contract(
        repo_path=".", frames=[stale_frame], contract_id="c11", created_at="t"
    )
    warnings_text = " ".join(str(w).lower() for w in contract.get("warnings", []))
    assert "stale" in warnings_text


# ═══════════════════════════════════════════════════════════════════════════════
# 12. demo mode uses static local data only
# ═══════════════════════════════════════════════════════════════════════════════

def test_demo_mode_uses_static_local_data(tmp_path):
    run, _ = _import_script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        contract_id="demo",
        created_at="2026-06-26T00:00:00+00:00",
        demo=True,
    )
    assert result["ok"] is True
    contract = result["contract"]
    # Demo must use static local data: no network, no subprocess, no model calls
    assert contract["guardrails"]["network_call_performed"] is False
    assert contract["guardrails"]["model_call_performed"] is False
    assert len(contract.get("example_frames", [])) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Markdown contains required sections
# ═══════════════════════════════════════════════════════════════════════════════

_REQUIRED_MD_SECTIONS = [
    "Summary",
    "Frame Definition",
    "Frame Schema",
    "Reusable Context Policy",
    "Excluded Context Policy",
    "Allowed Continuation Modes",
    "Forbidden Continuation Modes",
    "Human Confirmation Policy",
    "Staleness Policy",
    "UI Contract",
    "Example Frames",
    "Next UX Steps",
    "Warnings",
    "Blockers",
    "Guardrails",
    "Boundaries",
]


def test_markdown_contains_required_sections():
    (_, _, _, _, render_continue_from_frame_markdown, *_) = _import_core()
    contract = _build(contract_id="md1", created_at="t")
    md = render_continue_from_frame_markdown(contract)
    for section in _REQUIRED_MD_SECTIONS:
        assert section in md, f"Markdown missing section: {section}"


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Markdown contains boundary text
# ═══════════════════════════════════════════════════════════════════════════════

_REQUIRED_BOUNDARY_PHRASES = [
    "UX.3 defines the continuation contract only",
    "does not implement actual continuation execution",
    "does not start a run from history",
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
    (_, _, _, _, render_continue_from_frame_markdown, *_) = _import_core()
    contract = _build(contract_id="md2", created_at="t")
    md = render_continue_from_frame_markdown(contract)
    for phrase in _REQUIRED_BOUNDARY_PHRASES:
        assert phrase in md, f"Boundary phrase missing: {phrase!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 15. CLI writes JSON and Markdown
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_writes_json_and_markdown(tmp_path):
    run, _ = _import_script()
    out_root = str(tmp_path / "out")
    result = run(
        repo_path=".",
        output_root=out_root,
        contract_id="cli1",
        created_at="2026-06-26T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    # Validate JSON is parseable
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["contract_status"] == "ready_for_review"


# ═══════════════════════════════════════════════════════════════════════════════
# 16. CLI --json prints summary JSON
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_json_flag_prints_summary(capsys, tmp_path):
    _, main = _import_script()
    code = main([
        "--repo-path", ".",
        "--output-root", str(tmp_path / "out"),
        "--contract-id", "j1",
        "--created-at", "2026-06-26T00:00:00+00:00",
        "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "contract_status" in data
    assert "allowed_continuation_modes" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 17. guardrails are safe (all execution fields False)
# ═══════════════════════════════════════════════════════════════════════════════

_GUARDRAIL_FALSE_KEYS = {
    "continuation_execution_implemented",
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
    contract = _build(contract_id="g1", created_at="t")
    gs = contract["guardrails"]
    for key in _GUARDRAIL_FALSE_KEYS:
        assert key in gs, f"Missing guardrail key: {key}"
        assert gs[key] is False, f"Guardrail {key} should be False, got {gs[key]}"
    assert gs.get("contract_only") is True


# ═══════════════════════════════════════════════════════════════════════════════
# 18. optional UI placeholder, if added, contains "Continue From Frame"
# ═══════════════════════════════════════════════════════════════════════════════

def test_ui_placeholder_contains_continue_from_frame_label():
    if not _HTML_PATH.is_file():
        pytest.skip("index.html not found")
    # If UX.3 placeholder was added, it must label "Continue From Frame"
    if "ws-continue-from-frame" not in _HTML_SRC and "continue-from-frame" not in _HTML_SRC.lower():
        pytest.skip("UX.3 placeholder not yet added to index.html")
    assert "Continue From Frame" in _HTML_SRC


# ═══════════════════════════════════════════════════════════════════════════════
# 19. optional UI placeholder does not add a new mutation route
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_new_mutation_route_in_app():
    # The app.py should not have a new POST route for continue-from-frame
    assert "continue_from_frame" not in _APP_SRC.lower() or (
        "route" not in _APP_SRC.lower() and "POST" not in _APP_SRC
    ), "Found an unexpected continue_from_frame route in app.py"


# ═══════════════════════════════════════════════════════════════════════════════
# 20. registry accepts UX.3
# ═══════════════════════════════════════════════════════════════════════════════

_SEED_PATH = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"


def test_registry_contains_ux3():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    ids = {p["phase_id"] for p in data["phases"]}
    assert "UX.3" in ids


def test_registry_ux3_is_complete():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    ux3 = next((p for p in data["phases"] if p["phase_id"] == "UX.3"), None)
    assert ux3 is not None
    assert ux3["status"] == "complete"
    assert ux3["track"] == "UX"
    assert ux3["automation_level"] == "LOCAL_0_OBSERVE"
    assert ux3["merge_allowed"] is False
    assert ux3["network_allowed"] is False
    assert ux3["model_calls_allowed"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 21. source contains no forbidden execution/model/network/patch/validation/benchmark/worker/DB/merge tokens
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
    assert _CORE_SRC, "core/continue_from_frame_contract.py is empty or missing"
    for token in _FORBIDDEN_BARE:
        assert token not in _CORE_SRC, (
            f"Forbidden token {token!r} found in core/continue_from_frame_contract.py"
        )


def test_script_source_has_no_forbidden_tokens():
    assert _SCRIPT_SRC, "scripts/create_continue_from_frame_contract.py is empty or missing"
    for token in _FORBIDDEN_BARE:
        assert token not in _SCRIPT_SRC, (
            f"Forbidden token {token!r} found in scripts/create_continue_from_frame_contract.py"
        )
