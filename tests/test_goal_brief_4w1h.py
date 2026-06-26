"""Tests for UX.5 — Goal Brief 4W1H Simplifier (report-only).

UX.5 simplifies task intake by structuring operator goals into a 4W1H frame:
What / Why / Where / When stop / How validate.

UX.5 does not dispatch execution, start runs, call models, apply patches,
run validation or benchmarks, contact network services, launch workers,
mutate the repo, push, merge, or open PRs.

Prescribed test cases:
1.  complete 4W1H brief is ready_for_review
2.  empty brief is needs_more_input
3.  each canonical field exists: what, why, where, when_stop, how_validate
4.  field status can be strong/present/weak/missing
5.  completion score is deterministic
6.  complete strong brief scores 100
7.  missing field lowers score
8.  vague field is marked weak
9.  missing what generates clarifying question
10. missing why generates clarifying question
11. missing where generates clarifying question
12. missing when_stop generates clarifying question
13. missing how_validate generates clarifying question
14. simplified goal brief contains 4W1H fields
15. small complete brief recommends instant_run_preview
16. broad/risky brief recommends commander_contract_preview
17. missing fields recommend clarify
18. discussion-style brief recommends chat
19. allowed next steps are review/clarify/preview only
20. forbidden next steps include auto-dispatch and auto-apply
21. report aggregates missing field counts
22. report aggregates recommended mode counts
23. Markdown contains required sections
24. Markdown contains boundary text
25. CLI writes JSON and Markdown
26. CLI --json prints summary JSON
27. CLI field flags build a brief
28. demo mode uses static local data only
29. demo mode includes strong, weak, commander, and chat examples
30. guardrails are safe
31. optional UI placeholder, if added, contains 4W1H Goal Brief
32. optional UI placeholder does not add a new mutation route
33. registry accepts UX.5
34. source contains no forbidden execution/model/network/patch/validation/benchmark/worker/DB/merge tokens
"""
from __future__ import annotations

import json
from pathlib import Path

# ── Paths for source token guard ──────────────────────────────────────────────
_ROOT        = Path(__file__).parent.parent
_CORE_PATH   = _ROOT / "core"    / "goal_brief_4w1h.py"
_SCRIPT_PATH = _ROOT / "scripts" / "create_goal_brief_4w1h_preview.py"
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
    from core.goal_brief_4w1h import (  # type: ignore
        build_goal_brief_4w1h_preview,    # [0]
        build_simplified_goal_brief,      # [1]
        classify_field_status,            # [2]
        find_missing_fields,              # [3]
        find_weak_fields,                 # [4]
        generate_clarifying_questions,    # [5]
        normalize_goal_brief,             # [6]
        recommend_mode_hint,              # [7]
        render_goal_brief_4w1h_markdown,  # [8]
        score_goal_brief,                 # [9]
        write_goal_brief_4w1h_artifacts,  # [10]
    )
    return (
        build_goal_brief_4w1h_preview,
        build_simplified_goal_brief,
        classify_field_status,
        find_missing_fields,
        find_weak_fields,
        generate_clarifying_questions,
        normalize_goal_brief,
        recommend_mode_hint,
        render_goal_brief_4w1h_markdown,
        score_goal_brief,
        write_goal_brief_4w1h_artifacts,
    )


def _script():
    from scripts.create_goal_brief_4w1h_preview import (  # type: ignore
        main,
        run_create_goal_brief_4w1h_preview,
    )
    return run_create_goal_brief_4w1h_preview, main


# ── Convenience wrappers ──────────────────────────────────────────────────────
def _build(briefs: list[dict], **kw) -> dict:
    return _core()[0](repo_path=".", briefs=briefs, created_at="t", preview_id="r", **kw)


def _norm(raw: dict) -> dict:
    return _core()[6](raw)


def _classify_f(field_id: str, value) -> str:
    return _core()[2](field_id, value)


def _score(raw: dict) -> int:
    return _core()[9](_norm(raw))


def _find_missing(brief: dict) -> list:
    return _core()[3](brief)


def _find_weak(brief: dict) -> list:
    return _core()[4](brief)


def _questions(brief: dict) -> list:
    return _core()[5](brief)


def _hint(brief: dict) -> str:
    return _core()[7](brief)


def _render(report: dict) -> str:
    return _core()[8](report)


# ── Brief fixtures ────────────────────────────────────────────────────────────
def _strong_brief() -> dict:
    return {
        "brief_id": "test-strong",
        "created_at": "t",
        "repo_path": ".",
        "fields": {
            "what": (
                "Add 4W1H field completeness scoring to the Goal Brief system "
                "so operators know exactly what information CATTUS needs before a run starts"
            ),
            "why": (
                "Operators do not know what information CATTUS needs before a run, "
                "causing failed or incomplete runs that waste operator time and budget"
            ),
            "where": (
                "core/goal_brief_4w1h.py, scripts/create_goal_brief_4w1h_preview.py, "
                "tests/test_goal_brief_4w1h.py, docs/roadmap/phase_registry.json"
            ),
            "when_stop": (
                "When all 33 prescribed tests pass and the phase registry validates "
                "UX.5 as complete with status equals complete"
            ),
            "how_validate": (
                "python -m pytest tests/test_goal_brief_4w1h.py -q "
                "and python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json"
            ),
        },
    }


def _empty_brief() -> dict:
    return {"brief_id": "test-empty", "created_at": "t", "repo_path": ".", "fields": {}}


def _vague_brief() -> dict:
    return {
        "brief_id": "test-vague",
        "created_at": "t",
        "repo_path": ".",
        "fields": {
            "what": "fix it",
            "why": "it's broken",
            "where": "stuff",
            "when_stop": "etc",
            "how_validate": "do it",
        },
    }


def _discussion_brief() -> dict:
    return {
        "brief_id": "test-discussion",
        "created_at": "t",
        "repo_path": ".",
        "fields": {
            "what": "How should we approach refactoring the data pipeline architecture?",
            "why": "We are exploring trade-offs and want to discuss options before committing",
        },
    }


def _broad_risky_brief() -> dict:
    return {
        "brief_id": "test-commander",
        "created_at": "t",
        "repo_path": ".",
        "risk_notes": ["high_complexity", "many_files", "touches_production"],
        "fields": {
            "what": (
                "Full redesign of the authentication system across all "
                "microservices and client applications in the repository"
            ),
            "why": (
                "The current authentication system has critical security vulnerabilities "
                "and does not scale to the new microservice architecture being adopted"
            ),
            "where": (
                "web/, core/, scripts/, tests/, docs/, and all authentication-related "
                "files across the entire codebase and all environments"
            ),
            "when_stop": (
                "When all authentication services are migrated, all security tests pass "
                "across all environments, and sign-off from the security team is received"
            ),
            "how_validate": (
                "python -m pytest tests/ -k auth -q and manual security review "
                "and penetration testing report signed off by the security team"
            ),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. complete 4W1H brief is ready_for_review
# ═══════════════════════════════════════════════════════════════════════════════

def test_complete_brief_is_ready_for_review():
    report = _build([_strong_brief()])
    assert report["preview_status"] == "ready_for_review"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. empty brief is needs_more_input
# ═══════════════════════════════════════════════════════════════════════════════

def test_empty_brief_is_needs_more_input():
    report = _build([_empty_brief()])
    assert report["preview_status"] == "needs_more_input"


def test_all_vague_brief_is_needs_more_input():
    report = _build([_vague_brief()])
    assert report["preview_status"] == "needs_more_input"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. each canonical field exists: what, why, where, when_stop, how_validate
# ═══════════════════════════════════════════════════════════════════════════════

def test_canonical_field_what_is_recognized():
    status = _classify_f("what", "A detailed description of the change needed")
    assert status in {"strong", "present", "weak", "missing"}


def test_canonical_field_why_is_recognized():
    status = _classify_f("why", "Because the operators need this to run efficiently")
    assert status in {"strong", "present", "weak", "missing"}


def test_canonical_field_where_is_recognized():
    status = _classify_f("where", "core/goal_brief_4w1h.py and tests/test_goal_brief_4w1h.py")
    assert status in {"strong", "present", "weak", "missing"}


def test_canonical_field_when_stop_is_recognized():
    status = _classify_f("when_stop", "When all tests pass and the registry validates")
    assert status in {"strong", "present", "weak", "missing"}


def test_canonical_field_how_validate_is_recognized():
    status = _classify_f("how_validate", "python -m pytest tests/test_goal_brief_4w1h.py -q")
    assert status in {"strong", "present", "weak", "missing"}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. field status can be strong/present/weak/missing
# ═══════════════════════════════════════════════════════════════════════════════

def test_empty_string_is_missing():
    assert _classify_f("what", "") == "missing"


def test_none_value_is_missing():
    assert _classify_f("what", None) == "missing"


def test_vague_short_what_is_weak():
    assert _classify_f("what", "fix it") == "weak"


def test_vague_short_why_is_weak():
    assert _classify_f("why", "broken") == "weak"


def test_specific_file_path_where_is_not_missing_or_weak():
    status = _classify_f(
        "where",
        "core/goal_brief_4w1h.py and tests/test_goal_brief_4w1h.py",
    )
    assert status in {"strong", "present"}


def test_detailed_what_is_strong_or_present():
    status = _classify_f(
        "what",
        "Add 4W1H completeness scoring to the Goal Brief system so operators know what is needed before a run starts",
    )
    assert status in {"strong", "present"}


# ═══════════════════════════════════════════════════════════════════════════════
# 5. completion score is deterministic
# ═══════════════════════════════════════════════════════════════════════════════

def test_completion_score_is_deterministic():
    s1 = _score(_strong_brief())
    s2 = _score(_strong_brief())
    assert s1 == s2
    assert isinstance(s1, (int, float))


# ═══════════════════════════════════════════════════════════════════════════════
# 6. complete strong brief scores 100
# ═══════════════════════════════════════════════════════════════════════════════

def test_complete_strong_brief_scores_100():
    assert _score(_strong_brief()) == 100


# ═══════════════════════════════════════════════════════════════════════════════
# 7. missing field lowers score
# ═══════════════════════════════════════════════════════════════════════════════

def test_missing_what_lowers_score_below_100():
    brief = dict(_strong_brief())
    brief["fields"] = dict(brief["fields"])
    brief["fields"].pop("what")
    assert _score(brief) < 100


def test_missing_all_fields_scores_zero():
    assert _score(_empty_brief()) == 0


def test_one_weak_field_scores_below_100():
    brief = dict(_strong_brief())
    brief["fields"] = dict(brief["fields"])
    brief["fields"]["what"] = "fix it"
    assert _score(brief) < 100


# ═══════════════════════════════════════════════════════════════════════════════
# 8. vague field is marked weak
# ═══════════════════════════════════════════════════════════════════════════════

def test_vague_what_appears_in_weak_fields():
    brief = _norm(_vague_brief())
    weak = _find_weak(brief)
    assert "what" in weak


def test_where_without_file_hint_is_in_weak_fields():
    brief = _norm({
        "fields": {
            "what": "change something in the code base",
            "where": "stuff and things everywhere",
        },
    })
    weak = _find_weak(brief)
    assert "where" in weak


def test_how_validate_without_check_is_weak():
    brief = _norm({
        "fields": {
            "how_validate": "do it better",
        },
    })
    weak = _find_weak(brief)
    assert "how_validate" in weak


# ═══════════════════════════════════════════════════════════════════════════════
# 9. missing what → clarifying question
# ═══════════════════════════════════════════════════════════════════════════════

def test_missing_what_generates_clarifying_question():
    brief = _norm({"fields": {}})
    qs = _questions(brief)
    assert any("change" in q.lower() or "what" in q.lower() for q in qs)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. missing why → clarifying question
# ═══════════════════════════════════════════════════════════════════════════════

def test_missing_why_generates_clarifying_question():
    brief = _norm({"fields": {}})
    qs = _questions(brief)
    assert any("why" in q.lower() or "needed" in q.lower() for q in qs)


# ═══════════════════════════════════════════════════════════════════════════════
# 11. missing where → clarifying question
# ═══════════════════════════════════════════════════════════════════════════════

def test_missing_where_generates_clarifying_question():
    brief = _norm({"fields": {}})
    qs = _questions(brief)
    assert any("where" in q.lower() or "focus" in q.lower() for q in qs)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. missing when_stop → clarifying question
# ═══════════════════════════════════════════════════════════════════════════════

def test_missing_when_stop_generates_clarifying_question():
    brief = _norm({"fields": {}})
    qs = _questions(brief)
    assert any("stop" in q.lower() or "boundary" in q.lower() for q in qs)


# ═══════════════════════════════════════════════════════════════════════════════
# 13. missing how_validate → clarifying question
# ═══════════════════════════════════════════════════════════════════════════════

def test_missing_how_validate_generates_clarifying_question():
    brief = _norm({"fields": {}})
    qs = _questions(brief)
    assert any("validate" in q.lower() or "verify" in q.lower() for q in qs)


# ═══════════════════════════════════════════════════════════════════════════════
# 14. simplified goal brief contains 4W1H fields
# ═══════════════════════════════════════════════════════════════════════════════

def test_simplified_goal_brief_contains_4w1h_fields():
    simp_fn = _core()[1]  # build_simplified_goal_brief
    brief = _norm(_strong_brief())
    result = simp_fn(brief)
    for field in ("what", "why", "where", "when_stop", "how_validate"):
        assert field in result, f"Simplified brief missing field: {field!r}"


def test_simplified_goal_brief_preserves_field_values():
    simp_fn = _core()[1]
    brief = _norm(_strong_brief())
    result = simp_fn(brief)
    assert result["what"]  # non-empty
    assert result["why"]


# ═══════════════════════════════════════════════════════════════════════════════
# 15. small complete brief recommends instant_run_preview
# ═══════════════════════════════════════════════════════════════════════════════

def test_small_complete_brief_recommends_instant_run_preview():
    brief = _norm(_strong_brief())
    assert _hint(brief) == "instant_run_preview"


# ═══════════════════════════════════════════════════════════════════════════════
# 16. broad/risky brief recommends commander_contract_preview
# ═══════════════════════════════════════════════════════════════════════════════

def test_broad_risky_brief_recommends_commander_contract_preview():
    brief = _norm(_broad_risky_brief())
    assert _hint(brief) == "commander_contract_preview"


# ═══════════════════════════════════════════════════════════════════════════════
# 17. missing fields recommend clarify
# ═══════════════════════════════════════════════════════════════════════════════

def test_empty_brief_recommends_clarify():
    brief = _norm(_empty_brief())
    assert _hint(brief) == "clarify"


def test_mostly_missing_brief_recommends_clarify():
    brief = _norm({"fields": {"what": "fix something"}})
    assert _hint(brief) == "clarify"


# ═══════════════════════════════════════════════════════════════════════════════
# 18. discussion-style brief recommends chat
# ═══════════════════════════════════════════════════════════════════════════════

def test_discussion_brief_recommends_chat():
    brief = _norm(_discussion_brief())
    assert _hint(brief) == "chat"


# ═══════════════════════════════════════════════════════════════════════════════
# 19. allowed next steps are review/clarify/preview only
# ═══════════════════════════════════════════════════════════════════════════════

_EXPECTED_ALLOWED = {
    "review_goal_brief",
    "answer_clarifying_questions",
    "revise_goal_brief",
}


def test_allowed_next_steps_include_review_and_revise():
    report = _build([_strong_brief()])
    preview = report["brief_previews"][0]
    allowed = set(preview.get("allowed_next_steps", []))
    assert _EXPECTED_ALLOWED.issubset(allowed)


def test_allowed_next_steps_include_open_preview():
    report = _build([_strong_brief()])
    preview = report["brief_previews"][0]
    allowed = set(preview.get("allowed_next_steps", []))
    assert "open_instant_run_preview" in allowed or "open_commander_contract_preview" in allowed


# ═══════════════════════════════════════════════════════════════════════════════
# 20. forbidden next steps include auto-dispatch and auto-apply
# ═══════════════════════════════════════════════════════════════════════════════

_FORBIDDEN_NEXT = {
    "auto_dispatch",
    "auto_apply_patch",
    "auto_run_validation",
    "auto_run_benchmark",
    "auto_call_model",
    "auto_launch_worker",
    "auto_merge",
    "auto_push",
    "remote_execute",
    "bypass_human_approval",
}


def test_forbidden_next_steps_include_auto_dispatch_and_auto_apply():
    report = _build([_strong_brief()])
    preview = report["brief_previews"][0]
    forbidden = set(preview.get("forbidden_next_steps", []))
    assert "auto_dispatch" in forbidden
    assert "auto_apply_patch" in forbidden


def test_forbidden_next_steps_include_all_unsafe_actions():
    report = _build([_strong_brief()])
    preview = report["brief_previews"][0]
    forbidden = set(preview.get("forbidden_next_steps", []))
    assert _FORBIDDEN_NEXT.issubset(forbidden)


# ═══════════════════════════════════════════════════════════════════════════════
# 21. report aggregates missing field counts
# ═══════════════════════════════════════════════════════════════════════════════

def test_report_aggregates_missing_field_counts():
    report = _build([_empty_brief()])
    mfc = report.get("missing_field_counts", {})
    assert isinstance(mfc, dict)
    assert sum(mfc.values()) >= 5


def test_missing_field_counts_are_accurate_across_briefs():
    b1 = dict(_strong_brief())
    b1["fields"] = dict(b1["fields"])
    b1["fields"].pop("what")

    b2 = dict(_strong_brief())
    b2["brief_id"] = "b2-copy"

    report = _build([b1, b2])
    mfc = report.get("missing_field_counts", {})
    assert mfc.get("what", 0) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 22. report aggregates recommended mode counts
# ═══════════════════════════════════════════════════════════════════════════════

def test_report_aggregates_recommended_mode_counts():
    report = _build([_strong_brief(), _empty_brief()])
    rmc = report.get("recommended_mode_counts", {})
    assert isinstance(rmc, dict)
    assert sum(rmc.values()) == 2


def test_recommended_mode_counts_reflect_single_strong_brief():
    report = _build([_strong_brief()])
    rmc = report.get("recommended_mode_counts", {})
    assert rmc.get("instant_run_preview", 0) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 23. Markdown contains required sections
# ═══════════════════════════════════════════════════════════════════════════════

_REQUIRED_SECTIONS = [
    "Summary",
    "Brief Previews",
    "4W1H Field Status",
    "Missing Fields",
    "Weak Fields",
    "Clarifying Questions",
    "Simplified Goal Briefs",
    "Recommended Mode Hints",
    "Brief Policy",
    "UI Contract",
    "Next UX Steps",
    "Warnings",
    "Blockers",
    "Guardrails",
    "Boundaries",
]


def test_markdown_contains_required_sections():
    report = _build([_strong_brief()])
    md = _render(report)
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"Markdown missing section: {section!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 24. Markdown contains boundary text
# ═══════════════════════════════════════════════════════════════════════════════

_BOUNDARY_PHRASES = [
    "UX.5 simplifies task intake only",
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
    report = _build([_strong_brief()])
    md = _render(report)
    for phrase in _BOUNDARY_PHRASES:
        assert phrase in md, f"Missing boundary phrase: {phrase!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 25. CLI writes JSON and Markdown
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_writes_json_and_markdown(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        preview_id="cli1",
        created_at="2026-06-26T00:00:00+00:00",
        briefs=[_strong_brief()],
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["preview_status"] == "ready_for_review"


# ═══════════════════════════════════════════════════════════════════════════════
# 26. CLI --json prints summary JSON
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_json_flag_prints_summary(capsys, tmp_path):
    _, main = _script()
    code = main([
        "--repo-path", ".",
        "--output-root", str(tmp_path / "out"),
        "--preview-id", "j1",
        "--created-at", "2026-06-26T00:00:00+00:00",
        "--what", "Add completeness scoring to Goal Brief",
        "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "preview_status" in data
    assert "brief_count" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 27. CLI field flags build a brief
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_field_flags_build_a_brief(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        preview_id="f1",
        created_at="2026-06-26T00:00:00+00:00",
        what="Add 4W1H simplifier to CATTUS Goal Brief system",
        why="Operators need clearer structured task intake before a run",
        where="core/goal_brief_4w1h.py",
        when_stop="When all 33 tests pass",
        how_validate="python -m pytest tests/test_goal_brief_4w1h.py -q",
    )
    assert result["ok"] is True
    assert result["report"]["brief_count"] == 1


def test_cli_partial_fields_produce_clarify_hint(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out2"),
        preview_id="f2",
        created_at="2026-06-26T00:00:00+00:00",
        what="do something",
    )
    assert result["ok"] is True
    report = result["report"]
    preview = report["brief_previews"][0]
    assert preview["recommended_mode_hint"] in {"clarify", "chat"}


# ═══════════════════════════════════════════════════════════════════════════════
# 28. demo mode uses static local data only
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
    assert report["brief_count"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 29. demo mode includes strong, weak, commander, and chat examples
# ═══════════════════════════════════════════════════════════════════════════════

def test_demo_mode_includes_all_four_example_types(tmp_path):
    run, _ = _script()
    result = run(
        repo_path=".",
        output_root=str(tmp_path / "out"),
        preview_id="demo2",
        created_at="2026-06-26T00:00:00+00:00",
        demo=True,
    )
    report = result["report"]
    hints = {bp["recommended_mode_hint"] for bp in report["brief_previews"]}
    assert "instant_run_preview" in hints, f"Missing instant_run_preview; got {hints}"
    assert "clarify" in hints, f"Missing clarify; got {hints}"
    assert "commander_contract_preview" in hints, f"Missing commander_contract_preview; got {hints}"
    assert "chat" in hints, f"Missing chat; got {hints}"


# ═══════════════════════════════════════════════════════════════════════════════
# 30. guardrails are safe
# ═══════════════════════════════════════════════════════════════════════════════

_GUARDRAIL_FALSE_KEYS = {
    "goal_brief_execution_implemented",
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
    report = _build([_strong_brief()])
    gs = report["guardrails"]
    for key in _GUARDRAIL_FALSE_KEYS:
        assert key in gs, f"Missing guardrail key: {key}"
        assert gs[key] is False, f"Guardrail {key} should be False, got {gs[key]}"
    assert gs.get("preview_only") is True


# ═══════════════════════════════════════════════════════════════════════════════
# 31. optional UI placeholder, if added, contains 4W1H Goal Brief
# ═══════════════════════════════════════════════════════════════════════════════

def test_ui_placeholder_contains_4w1h_goal_brief_label():
    if not _HTML_PATH.is_file():
        import pytest; pytest.skip("index.html not found")
    if "4w1h-goal-brief" not in _HTML_SRC.lower() and "ws-goal-brief-4w1h" not in _HTML_SRC:
        import pytest; pytest.skip("UX.5 4W1H placeholder not yet added to index.html")
    assert "4W1H Goal Brief" in _HTML_SRC


# ═══════════════════════════════════════════════════════════════════════════════
# 32. optional UI placeholder does not add a new mutation route
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_new_4w1h_mutation_route_in_app():
    has_route = (
        "goal_brief_4w1h" in _APP_SRC.lower()
        and ("@app.route" in _APP_SRC or "methods=[" in _APP_SRC)
        and "POST" in _APP_SRC
    )
    assert not has_route, "Found unexpected goal_brief_4w1h mutation route in app.py"


# ═══════════════════════════════════════════════════════════════════════════════
# 33. registry accepts UX.5
# ═══════════════════════════════════════════════════════════════════════════════

_SEED_PATH = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"


def test_registry_contains_ux5():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    ids = {p["phase_id"] for p in data["phases"]}
    assert "UX.5" in ids


def test_registry_ux5_is_complete():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    ux5 = next((p for p in data["phases"] if p["phase_id"] == "UX.5"), None)
    assert ux5 is not None
    assert ux5["status"] == "complete"
    assert ux5["track"] == "UX"
    assert ux5["automation_level"] == "LOCAL_0_OBSERVE"
    assert ux5["merge_allowed"] is False
    assert ux5["network_allowed"] is False
    assert ux5["model_calls_allowed"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 34. source contains no forbidden tokens
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
    assert _CORE_SRC, "core/goal_brief_4w1h.py is empty or missing"
    for token in _FORBIDDEN_BARE:
        assert token not in _CORE_SRC, (
            f"Forbidden token {token!r} found in core/goal_brief_4w1h.py"
        )


def test_script_source_has_no_forbidden_tokens():
    assert _SCRIPT_SRC, "scripts/create_goal_brief_4w1h_preview.py is empty or missing"
    for token in _FORBIDDEN_BARE:
        assert token not in _SCRIPT_SRC, (
            f"Forbidden token {token!r} found in scripts/create_goal_brief_4w1h_preview.py"
        )
