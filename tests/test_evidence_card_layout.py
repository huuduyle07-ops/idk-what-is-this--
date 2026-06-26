"""Tests for UX.6 — Evidence Card Layout (report-only, preview-only).

UX.6 makes evidence easier to read.  UX.6 does not create new evidence,
dispatch execution, start runs, call AI services, apply patches, run
validation or benchmarks, contact network services, launch workers,
mutate the repo, push, merge, or open PRs.

Prescribed test cases:
1.  default preview status is ready_for_review
2.  card normalization fills safe defaults
3.  required card types are present in demo/default layout
4.  card statuses support pass/warn/fail/missing/info/blocked
5.  card priorities support high/medium/low
6.  display groups include result/change/checks/risk/decision
7.  status counts are deterministic
8.  missing evidence cards are surfaced
9.  high priority cards are surfaced
10. failed card makes operator decision blocked_by_failed_check
11. missing required evidence makes operator decision needs_more_evidence
12. no cards makes operator decision insufficient_information
13. complete non-failing cards make operator decision ready_for_human_review
14. benchmark card is optional
15. Markdown contains required sections
16. Markdown contains boundary text
17. CLI writes JSON and Markdown
18. CLI --json prints summary JSON
19. CLI demo uses static local data only
20. demo mode includes all main evidence card types
21. guardrails are safe
22. optional UI placeholder, if added, contains Evidence Cards
23. optional UI placeholder does not add a new mutation route
24. registry accepts UX.6
25. source contains no forbidden execution/network/patch/validation/benchmark/worker/DB/merge behavior
"""
from __future__ import annotations

import json
from pathlib import Path

# ── Paths for source token guard ──────────────────────────────────────────────
_ROOT        = Path(__file__).parent.parent
_CORE_PATH   = _ROOT / "core"    / "evidence_card_layout.py"
_SCRIPT_PATH = _ROOT / "scripts" / "create_evidence_card_layout_preview.py"
_HTML_PATH   = _ROOT / "web" / "templates" / "index.html"
_APP_PATH    = _ROOT / "web" / "app.py"


def _read_src(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


_CORE_SRC   = _read_src(_CORE_PATH)
_SCRIPT_SRC = _read_src(_SCRIPT_PATH)
_HTML_SRC   = _read_src(_HTML_PATH)
_APP_SRC    = _read_src(_APP_PATH)


# ── Lazy imports so tests can be collected before core exists ──────────────────
def _core():
    from core.evidence_card_layout import (  # type: ignore
        build_evidence_card_layout_preview,    # [0]
        build_default_evidence_cards,          # [1]
        normalize_evidence_card,               # [2]
        summarize_card_counts,                 # [3]
        summarize_status_counts,               # [4]
        find_missing_evidence_cards,           # [5]
        find_high_priority_cards,              # [6]
        build_operator_decision_summary,       # [7]
        render_evidence_card_layout_markdown,  # [8]
        write_evidence_card_layout_artifacts,  # [9]
    )
    return (
        build_evidence_card_layout_preview,
        build_default_evidence_cards,
        normalize_evidence_card,
        summarize_card_counts,
        summarize_status_counts,
        find_missing_evidence_cards,
        find_high_priority_cards,
        build_operator_decision_summary,
        render_evidence_card_layout_markdown,
        write_evidence_card_layout_artifacts,
    )


def _script():
    from scripts.create_evidence_card_layout_preview import (  # type: ignore
        main,
        run_create_evidence_card_layout_preview,
    )
    return run_create_evidence_card_layout_preview, main


# ── Convenience wrappers ──────────────────────────────────────────────────────
def _build(cards: list, **kw) -> dict:
    return _core()[0](repo_path=".", cards=cards, created_at="t", preview_id="r", **kw)

def _defaults() -> list:
    return _core()[1](repo_path=".")

def _norm(raw: dict) -> dict:
    return _core()[2](raw)

def _card_counts(cards: list) -> dict:
    return _core()[3](cards)

def _status_counts(cards: list) -> dict:
    return _core()[4](cards)

def _find_missing(cards: list) -> list:
    return _core()[5](cards)

def _find_high(cards: list) -> list:
    return _core()[6](cards)

def _decision(cards: list) -> str:
    return _core()[7](cards)

def _render(report: dict) -> str:
    return _core()[8](report)


# ── Shared constants ──────────────────────────────────────────────────────────
_REQUIRED_CARD_TYPES = (
    "answer_summary",
    "patch_summary",
    "validation_summary",
    "risk_summary",
    "human_review",
    "next_action",
)

_ALL_CARD_FIELDS = (
    "card_id", "card_type", "title", "status", "summary",
    "details", "evidence_refs", "missing_evidence", "risk_flags",
    "operator_action", "priority", "display_group",
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. default preview status is ready_for_review
# ═══════════════════════════════════════════════════════════════════════════════

def test_default_preview_status_is_ready_for_review():
    cards = _defaults()
    report = _build(cards)
    assert report["preview_status"] == "ready_for_review"


def test_default_cards_produce_ready_for_human_review_decision():
    cards = _defaults()
    report = _build(cards)
    assert report["operator_decision_summary"] == "ready_for_human_review"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. card normalization fills safe defaults
# ═══════════════════════════════════════════════════════════════════════════════

def test_card_normalization_fills_all_fields():
    card = _norm({})
    for field in _ALL_CARD_FIELDS:
        assert field in card, f"Normalized card missing field: {field!r}"


def test_card_normalization_preserves_provided_values():
    raw = {
        "card_id":    "test-v",
        "card_type":  "validation_summary",
        "status":     "pass",
        "priority":   "high",
        "title":      "Validation",
        "summary":    "All checks passed.",
    }
    card = _norm(raw)
    assert card["card_id"]   == "test-v"
    assert card["card_type"] == "validation_summary"
    assert card["status"]    == "pass"
    assert card["priority"]  == "high"
    assert card["title"]     == "Validation"


def test_card_normalization_empty_raw_has_list_fields():
    card = _norm({})
    assert isinstance(card["details"],          list)
    assert isinstance(card["evidence_refs"],    list)
    assert isinstance(card["missing_evidence"], list)
    assert isinstance(card["risk_flags"],       list)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. required card types are present in demo/default layout
# ═══════════════════════════════════════════════════════════════════════════════

def test_required_card_types_present_in_default_layout():
    cards = _defaults()
    card_types = {c["card_type"] for c in cards}
    for ct in _REQUIRED_CARD_TYPES:
        assert ct in card_types, f"Required card type missing from defaults: {ct!r}"


def test_required_card_types_present_in_demo_layout(tmp_path):
    run, _ = _script()
    result = run(repo_path=".", output_root=str(tmp_path / "out"), demo=True)
    card_types = {c["card_type"] for c in result["report"]["cards"]}
    for ct in _REQUIRED_CARD_TYPES:
        assert ct in card_types, f"Required card type missing from demo: {ct!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. card statuses support pass/warn/fail/missing/info/blocked
# ═══════════════════════════════════════════════════════════════════════════════

def test_card_statuses_all_accepted():
    for status in ("pass", "warn", "fail", "missing", "info", "blocked"):
        card = _norm({"status": status})
        assert card["status"] == status, f"Status {status!r} not preserved"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. card priorities support high/medium/low
# ═══════════════════════════════════════════════════════════════════════════════

def test_card_priorities_all_accepted():
    for priority in ("high", "medium", "low"):
        card = _norm({"priority": priority})
        assert card["priority"] == priority, f"Priority {priority!r} not preserved"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. display groups include result/change/checks/risk/decision
# ═══════════════════════════════════════════════════════════════════════════════

def test_display_groups_all_present_in_default_cards():
    cards = _defaults()
    groups = {c["display_group"] for c in cards}
    for group in ("result", "change", "checks", "risk", "decision"):
        assert group in groups, f"Display group {group!r} missing from defaults"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. status counts are deterministic
# ═══════════════════════════════════════════════════════════════════════════════

def test_status_counts_are_deterministic():
    cards = _defaults()
    assert _status_counts(cards) == _status_counts(cards)


def test_status_counts_reflect_actual_statuses():
    cards = [
        _norm({"status": "pass"}),
        _norm({"status": "pass"}),
        _norm({"status": "warn"}),
    ]
    sc = _status_counts(cards)
    assert sc.get("pass", 0) == 2
    assert sc.get("warn", 0) == 1


def test_card_counts_reflect_card_types():
    cards = [
        _norm({"card_type": "answer_summary"}),
        _norm({"card_type": "answer_summary"}),
        _norm({"card_type": "risk_summary"}),
    ]
    cc = _card_counts(cards)
    assert cc.get("answer_summary", 0) == 2
    assert cc.get("risk_summary", 0) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 8. missing evidence cards are surfaced
# ═══════════════════════════════════════════════════════════════════════════════

def test_missing_evidence_empty_cards_surfaces_all_required():
    missing = _find_missing([])
    assert len(missing) > 0
    assert "answer_summary"    in missing
    assert "human_review"      in missing
    assert "next_action"       in missing


def test_missing_evidence_complete_required_types_is_empty():
    cards = [_norm({"card_type": ct, "status": "pass"}) for ct in _REQUIRED_CARD_TYPES]
    assert _find_missing(cards) == []


def test_missing_evidence_partial_types_surfaces_gaps():
    cards = [_norm({"card_type": "answer_summary", "status": "pass"})]
    missing = _find_missing(cards)
    assert "answer_summary"     not in missing
    assert "validation_summary" in missing
    assert "human_review"       in missing


def test_card_with_missing_status_is_treated_as_absent():
    cards = [_norm({"card_type": "answer_summary", "status": "missing"})]
    missing = _find_missing(cards)
    assert "answer_summary" in missing


# ═══════════════════════════════════════════════════════════════════════════════
# 9. high priority cards are surfaced
# ═══════════════════════════════════════════════════════════════════════════════

def test_high_priority_cards_surfaced_from_defaults():
    cards = _defaults()
    high = _find_high(cards)
    assert len(high) > 0
    assert all(c["priority"] == "high" for c in high)


def test_high_priority_excludes_non_high():
    cards = [
        _norm({"priority": "high", "card_type": "validation_summary"}),
        _norm({"priority": "low",  "card_type": "answer_summary"}),
        _norm({"priority": "medium", "card_type": "risk_summary"}),
    ]
    high = _find_high(cards)
    assert len(high) == 1
    assert high[0]["card_type"] == "validation_summary"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. failed card makes operator decision blocked_by_failed_check
# ═══════════════════════════════════════════════════════════════════════════════

def test_fail_status_card_makes_decision_blocked():
    cards = [_norm({"card_type": "validation_summary", "status": "fail"})]
    assert _decision(cards) == "blocked_by_failed_check"


def test_blocked_status_card_makes_decision_blocked():
    cards = [_norm({"card_type": "human_review", "status": "blocked"})]
    assert _decision(cards) == "blocked_by_failed_check"


def test_fail_status_beats_missing_evidence():
    # Even with missing required cards, fail status takes priority
    cards = [_norm({"card_type": "validation_summary", "status": "fail"})]
    assert _decision(cards) == "blocked_by_failed_check"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. missing required evidence makes operator decision needs_more_evidence
# ═══════════════════════════════════════════════════════════════════════════════

def test_only_optional_card_makes_decision_needs_more_evidence():
    cards = [_norm({"card_type": "changed_files", "status": "pass"})]
    assert _decision(cards) == "needs_more_evidence"


def test_partial_required_cards_make_decision_needs_more_evidence():
    # Only one required type present
    cards = [_norm({"card_type": "answer_summary", "status": "pass"})]
    assert _decision(cards) == "needs_more_evidence"


# ═══════════════════════════════════════════════════════════════════════════════
# 12. no cards makes operator decision insufficient_information
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_cards_makes_decision_insufficient_information():
    assert _decision([]) == "insufficient_information"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. complete non-failing cards make operator decision ready_for_human_review
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_required_pass_makes_decision_ready_for_human_review():
    cards = [_norm({"card_type": ct, "status": "pass"}) for ct in _REQUIRED_CARD_TYPES]
    assert _decision(cards) == "ready_for_human_review"


def test_warn_status_does_not_block_decision():
    cards = [_norm({"card_type": ct, "status": "warn"}) for ct in _REQUIRED_CARD_TYPES]
    assert _decision(cards) == "ready_for_human_review"


def test_mix_of_pass_and_info_makes_decision_ready():
    cards = (
        [_norm({"card_type": ct, "status": "pass"}) for ct in _REQUIRED_CARD_TYPES[:3]] +
        [_norm({"card_type": ct, "status": "info"}) for ct in _REQUIRED_CARD_TYPES[3:]]
    )
    assert _decision(cards) == "ready_for_human_review"


# ═══════════════════════════════════════════════════════════════════════════════
# 14. benchmark card is optional
# ═══════════════════════════════════════════════════════════════════════════════

def test_benchmark_card_is_optional_for_ready_decision():
    cards = [_norm({"card_type": ct, "status": "pass"}) for ct in _REQUIRED_CARD_TYPES]
    assert "benchmark_summary" not in [c["card_type"] for c in cards]
    assert _decision(cards) == "ready_for_human_review"


def test_benchmark_not_in_missing_evidence_when_absent():
    cards = [_norm({"card_type": ct, "status": "pass"}) for ct in _REQUIRED_CARD_TYPES]
    report = _build(cards)
    assert "benchmark_summary" not in report.get("missing_evidence_cards", [])


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Markdown contains required sections
# ═══════════════════════════════════════════════════════════════════════════════

_REQUIRED_SECTIONS = [
    "Summary",
    "Evidence Cards",
    "Card Counts",
    "Status Counts",
    "Missing Evidence",
    "High Priority Cards",
    "Operator Decision Summary",
    "Layout Policy",
    "UI Contract",
    "Next UX Steps",
    "Warnings",
    "Blockers",
    "Guardrails",
    "Boundaries",
]


def test_markdown_contains_required_sections():
    report = _build(_defaults())
    md = _render(report)
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"Markdown missing section: {section!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Markdown contains boundary text
# ═══════════════════════════════════════════════════════════════════════════════

_BOUNDARY_PHRASES = [
    "UX.6 is a preview-only evidence layout phase",
    "does not create new evidence",
    "does not dispatch execution",
    "does not start runs",
    "does not call AI services",
    "does not apply patches",
    "does not run validation",
    "does not run benchmarks",
    "does not contact network services",
    "does not launch workers",
    "does not mutate the repo",
    "does not push, merge, or open PRs",
]


def test_markdown_contains_boundary_text():
    report = _build(_defaults())
    md = _render(report)
    for phrase in _BOUNDARY_PHRASES:
        assert phrase in md, f"Missing boundary phrase: {phrase!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 17. CLI writes JSON and Markdown
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_writes_json_and_markdown(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        preview_id="cli1",
        created_at="2026-06-26T00:00:00+00:00",
        demo=True,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert "preview_status" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 18. CLI --json prints summary JSON
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_json_flag_prints_summary_json(capsys, tmp_path):
    _, main = _script()
    code = main([
        "--repo-path", ".",
        "--output-root", str(tmp_path / "out"),
        "--preview-id", "j1",
        "--created-at", "2026-06-26T00:00:00+00:00",
        "--demo",
        "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "preview_status" in data
    assert "card_counts"    in data


# ═══════════════════════════════════════════════════════════════════════════════
# 19. CLI demo uses static local data only
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
    assert report["guardrails"]["network_call_performed"]   is False
    assert report["guardrails"]["ai_service_call_performed"] is False
    assert len(report["cards"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 20. demo mode includes all main evidence card types
# ═══════════════════════════════════════════════════════════════════════════════

def test_demo_mode_includes_all_main_card_types(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        preview_id="demo2",
        created_at="2026-06-26T00:00:00+00:00",
        demo=True,
    )
    card_types = {c["card_type"] for c in result["report"]["cards"]}
    for ct in (
        "answer_summary", "patch_summary", "changed_files",
        "validation_summary", "benchmark_summary", "risk_summary",
        "human_review", "next_action",
    ):
        assert ct in card_types, f"Missing demo card type: {ct!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 21. guardrails are safe
# ═══════════════════════════════════════════════════════════════════════════════

_GUARDRAIL_FALSE_KEYS = {
    "new_evidence_created",
    "router_dispatch_implemented",
    "new_route_added",
    "mutation_route_added",
    "backend_execution_changed",
    "task_execution_performed",
    "agent_launched",
    "ai_service_call_performed",
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
    report = _build(_defaults())
    gs = report["guardrails"]
    for key in _GUARDRAIL_FALSE_KEYS:
        assert key in gs,          f"Missing guardrail key: {key}"
        assert gs[key] is False,   f"Guardrail {key!r} should be False, got {gs[key]}"
    assert gs.get("preview_only")          is True
    assert gs.get("evidence_layout_only")  is True


# ═══════════════════════════════════════════════════════════════════════════════
# 22. optional UI placeholder, if added, contains Evidence Cards
# ═══════════════════════════════════════════════════════════════════════════════

def test_ui_placeholder_contains_evidence_cards_label():
    if not _HTML_PATH.is_file():
        import pytest; pytest.skip("index.html not found")
    if "ws-evidence-cards" not in _HTML_SRC and "evidence-cards" not in _HTML_SRC.lower():
        import pytest; pytest.skip("UX.6 Evidence Cards placeholder not yet added to index.html")
    assert "Evidence Cards" in _HTML_SRC


# ═══════════════════════════════════════════════════════════════════════════════
# 23. optional UI placeholder does not add a new mutation route
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_new_evidence_mutation_route_in_app():
    has_route = (
        "evidence_card" in _APP_SRC.lower()
        and ("@app.route" in _APP_SRC or "methods=[" in _APP_SRC)
        and "POST" in _APP_SRC
    )
    assert not has_route, "Found unexpected evidence_card mutation route in app.py"


# ═══════════════════════════════════════════════════════════════════════════════
# 24. registry accepts UX.6
# ═══════════════════════════════════════════════════════════════════════════════

_SEED_PATH = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"


def test_registry_contains_ux6():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    ids = {p["phase_id"] for p in data["phases"]}
    assert "UX.6" in ids


def test_registry_ux6_is_complete():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    ux6 = next((p for p in data["phases"] if p["phase_id"] == "UX.6"), None)
    assert ux6 is not None
    assert ux6["status"]           == "complete"
    assert ux6["track"]            == "UX"
    assert ux6["automation_level"] == "LOCAL_0_OBSERVE"
    assert ux6["merge_allowed"]    is False
    assert ux6["network_allowed"]  is False
    assert ux6["model_calls_allowed"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 25. source contains no forbidden tokens
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
    "gemini",
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
    assert _CORE_SRC, "core/evidence_card_layout.py is empty or missing"
    for token in _FORBIDDEN_BARE:
        assert token not in _CORE_SRC, (
            f"Forbidden token {token!r} found in core/evidence_card_layout.py"
        )


def test_script_source_has_no_forbidden_tokens():
    assert _SCRIPT_SRC, "scripts/create_evidence_card_layout_preview.py is empty or missing"
    for token in _FORBIDDEN_BARE:
        assert token not in _SCRIPT_SRC, (
            f"Forbidden token {token!r} found in scripts/create_evidence_card_layout_preview.py"
        )
