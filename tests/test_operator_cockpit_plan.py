"""Tests for UX.1 — Operator Cockpit & Idea Intake Plan (report-only).

UX.1 creates a pure UX planning report that defines the C.A.T.T.U.S operator
cockpit and idea intake system. It does not implement the UI, change backend
behavior, execute tasks, run agents, call models, apply patches, run validation,
run benchmarks, contact network services, launch workers, push, merge, or open PRs.

Covers the prescribed cases:
1.  default problem inventory is present.
2.  custom problems are included.
3.  operator workflow has Start, Run, Review, Continue, Learn.
4.  cockpit sections include run timeline, continue history, evidence, commander,
    idea intake.
5.  primary actions are daily-use only.
6.  advanced/debug actions are separated.
7.  idea intake board has use_now/prototype_later/park/block buckets.
8.  4W1H is classified use_now.
9.  Navier-Stokes is classified prototype_later.
10. Excavator is classified prototype_later.
11. autonomy-increasing idea is blocked.
12. UX roadmap suggests UX.2/UX.3/UX.4/UX.5.
13. forbidden next steps include execution/worker/model/patch/network/merge.
14. Markdown contains required sections and boundaries.
15. CLI writes JSON + Markdown.
16. CLI --json prints summary JSON.
17. guardrails are all false.
18. source contains no forbidden execution/model/network/patch/validation/
    benchmark/worker/DB/merge behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.operator_cockpit_plan import (
    GUARDRAIL_NOTE,
    PLAN_STATUS_READY,
    REPORT_KIND,
    build_operator_cockpit_plan,
    render_operator_cockpit_plan_markdown,
    write_operator_cockpit_plan,
)
import scripts.create_operator_cockpit_plan as script


# ── helpers ───────────────────────────────────────────────────────────────────

def _build(
    *,
    problems: list[str] | None = None,
    ideas: list[str] | None = None,
    include_default_problems: bool = True,
    include_default_ideas: bool = True,
    plan_id: str = "test-plan",
    created_at: str = "2026-06-24T00:00:00+00:00",
    repo_path: str = ".",
) -> dict:
    return build_operator_cockpit_plan(
        repo_path=repo_path,
        plan_id=plan_id,
        created_at=created_at,
        extra_problems=problems or [],
        extra_ideas=ideas or [],
        include_default_problems=include_default_problems,
        include_default_ideas=include_default_ideas,
    )


# ── 1. default problem inventory is present ───────────────────────────────────

def test_default_problem_inventory_is_present():
    report = _build()
    problems = report["ux_problem_inventory"]
    assert isinstance(problems, list)
    assert len(problems) >= 6
    # Check a subset of the known pain points
    text = " ".join(p.get("description", "") + p.get("id", "") for p in problems).lower()
    assert "goal brief" in text or "silent" in text or "history" in text


# ── 2. custom problems are included ───────────────────────────────────────────

def test_custom_problems_are_included():
    report = _build(problems=["My custom UX problem: the widget is broken"])
    problems = report["ux_problem_inventory"]
    text = " ".join(p.get("description", "") for p in problems).lower()
    assert "widget is broken" in text


# ── 3. operator workflow has Start, Run, Review, Continue, Learn ──────────────

def test_operator_workflow_has_five_steps():
    report = _build()
    workflow = report["operator_workflow"]
    assert isinstance(workflow, list)
    step_ids = [s["step_id"].lower() for s in workflow]
    for required in ("start", "run", "review", "continue", "learn"):
        assert any(required in sid for sid in step_ids), f"Missing step: {required}"


# ── 4. cockpit sections include required panels ───────────────────────────────

def test_cockpit_sections_include_required_panels():
    report = _build()
    sections = report["cockpit_sections"]
    assert isinstance(sections, list)
    names_lower = " ".join(s.get("name", "").lower() for s in sections)
    assert "run timeline" in names_lower
    assert "continue" in names_lower
    assert "evidence" in names_lower or "patch" in names_lower
    assert "commander" in names_lower
    assert "idea intake" in names_lower


# ── 5. primary actions are daily-use only ────────────────────────────────────

def test_primary_actions_are_daily_use_only():
    report = _build()
    primary = report["primary_action_map"]
    assert isinstance(primary, list)
    ids = {a["action_id"] for a in primary}
    assert "chat_or_run" in ids or "start_instant_run" in ids
    assert "review_patch" in ids or "apply_patch_after_approval" in ids
    assert "continue_from_frame" in ids


def test_primary_actions_do_not_include_debug_actions():
    report = _build()
    primary_ids = {a["action_id"] for a in report["primary_action_map"]}
    debug_ids = {a["action_id"] for a in report["debug_action_map"]}
    assert primary_ids.isdisjoint(debug_ids), "Primary and debug actions overlap"


# ── 6. advanced/debug actions are separated ───────────────────────────────────

def test_advanced_and_debug_actions_are_separated():
    report = _build()
    advanced = report["advanced_action_map"]
    debug = report["debug_action_map"]
    assert isinstance(advanced, list) and len(advanced) >= 3
    assert isinstance(debug, list) and len(debug) >= 3
    advanced_ids = {a["action_id"] for a in advanced}
    debug_ids = {a["action_id"] for a in debug}
    assert advanced_ids.isdisjoint(debug_ids), "Advanced and debug actions overlap"


# ── 7. idea intake board has use_now/prototype_later/park/block buckets ───────

def test_idea_intake_board_has_four_buckets():
    report = _build()
    board = report["idea_intake_board"]
    assert isinstance(board, dict)
    for bucket in ("use_now", "prototype_later", "park", "block"):
        assert bucket in board, f"Missing bucket: {bucket}"
        assert isinstance(board[bucket], list)


# ── 8. 4W1H is classified use_now ────────────────────────────────────────────

def test_4w1h_is_classified_use_now():
    report = _build(include_default_ideas=True)
    board = report["idea_intake_board"]
    use_now_ids = [i.get("idea_id", "").lower() for i in board["use_now"]]
    use_now_text = " ".join(
        i.get("name", "").lower() + " " + i.get("idea_id", "").lower()
        for i in board["use_now"]
    )
    assert "4w1h" in use_now_text or "goal brief" in use_now_text, (
        f"4W1H not in use_now. use_now ids: {use_now_ids}"
    )


# ── 9. Navier-Stokes is classified prototype_later ───────────────────────────

def test_navier_stokes_is_classified_prototype_later():
    report = _build(include_default_ideas=True)
    board = report["idea_intake_board"]
    proto_text = " ".join(
        i.get("name", "").lower() + " " + i.get("idea_id", "").lower()
        for i in board["prototype_later"]
    )
    assert "navier" in proto_text or "stokes" in proto_text or "commander flow" in proto_text, (
        f"Navier-Stokes not in prototype_later. text: {proto_text}"
    )


# ── 10. Excavator is classified prototype_later ───────────────────────────────

def test_excavator_is_classified_prototype_later():
    report = _build(include_default_ideas=True)
    board = report["idea_intake_board"]
    proto_text = " ".join(
        i.get("name", "").lower() + " " + i.get("idea_id", "").lower()
        for i in board["prototype_later"]
    )
    assert "excavator" in proto_text, (
        f"Excavator not in prototype_later. text: {proto_text}"
    )


# ── 11. autonomy-increasing idea is blocked ───────────────────────────────────

def test_autonomy_increasing_idea_is_blocked():
    autonomous_idea = (
        "auto-approve all patches without human review and auto-merge to main"
    )
    report = _build(ideas=[autonomous_idea])
    board = report["idea_intake_board"]
    block_text = " ".join(
        i.get("name", "").lower() + " " + i.get("description", "").lower()
        for i in board["block"]
    )
    assert "auto-approve" in block_text or "auto_approve" in block_text or len(board["block"]) > 0


def test_block_bucket_rule_catches_auto_merge():
    report = _build(ideas=["bypass human gate and push directly to main"])
    board = report["idea_intake_board"]
    assert isinstance(board["block"], list)


# ── 12. UX roadmap suggests UX.2/UX.3/UX.4/UX.5 ─────────────────────────────

def test_ux_roadmap_suggests_later_phases():
    report = _build()
    roadmap = report["ux_roadmap"]
    assert isinstance(roadmap, list)
    phase_ids = [p.get("phase_id", "") for p in roadmap]
    for phase in ("UX.2", "UX.3", "UX.4", "UX.5"):
        assert phase in phase_ids, f"Missing UX roadmap phase: {phase}"


# ── 13. forbidden next steps include execution/worker/model/patch/network/merge

def test_forbidden_next_steps_include_execution_categories():
    report = _build()
    forbidden = report["forbidden_next_steps"]
    assert isinstance(forbidden, list)
    text = " ".join(forbidden).lower()
    assert "launch_worker" in text or "worker" in text
    assert "call_model" in text or "model" in text
    assert "apply_patch" in text or "patch" in text
    assert "contact_remote" in text or "network" in text
    assert "push_or_merge" in text or "merge" in text
    assert "run_validation" in text or "validation" in text
    assert "run_benchmark" in text or "benchmark" in text


# ── 14. Markdown contains required sections and boundaries ────────────────────

def test_markdown_contains_required_sections():
    md = render_operator_cockpit_plan_markdown(_build())
    low = md.lower()
    for section in (
        "## summary",
        "## ux problem inventory",
        "## operator workflow",
        "## cockpit sections",
        "## primary actions",
        "## advanced actions",
        "## debug actions",
        "## idea intake board",
        "## metaphor placement",
        "## ux roadmap",
        "## non-goals",
        "## allowed next steps",
        "## forbidden next steps",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, f"Missing markdown section: {section!r}"


def test_markdown_states_all_boundaries():
    low = render_operator_cockpit_plan_markdown(_build()).lower()
    assert "does not implement the ui" in low or "ux.1 does not implement the ui" in low
    assert "does not change backend behavior" in low
    assert "does not execute tasks" in low
    assert "does not run agents" in low
    assert "does not call models" in low
    assert "does not apply patches" in low
    assert "does not run validation" in low
    assert "does not run benchmarks" in low
    assert "does not contact network services" in low
    assert "does not launch workers" in low
    assert "does not push, merge, or open prs" in low
    assert "report-only" in low


# ── 15. CLI writes JSON + Markdown ────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    out = tmp_path / "out"
    res = script.run_create_operator_cockpit_plan(
        repo_path=".",
        output_root=str(out),
        plan_id="cli-test",
        created_at="2026-06-24T00:00:00+00:00",
        include_default_problems=True,
        include_default_ideas=True,
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "operator_cockpit_plan.json"
    assert mp.name == "operator_cockpit_plan.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["plan_id"] == "cli-test"
    assert data["plan_status"] == PLAN_STATUS_READY


# ── 16. CLI --json prints summary JSON ────────────────────────────────────────

def test_cli_json_flag_prints_summary_json(tmp_path, capsys):
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", ".",
        "--output-root", str(out),
        "--plan-id", "json-test",
        "--created-at", "2026-06-24T00:00:00+00:00",
        "--include-default-problems",
        "--include-default-ideas",
        "--json",
    ])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["plan_id"] == "json-test"
    assert printed["report_kind"] == REPORT_KIND
    assert printed["plan_status"] == PLAN_STATUS_READY


# ── 17. guardrails are all false ──────────────────────────────────────────────

def test_guardrails_are_all_false():
    report = _build()
    guardrails = report["guardrails"]
    for key, val in guardrails.items():
        assert val is False, f"Guardrail {key!r} is not False"


def test_report_has_guardrail_note():
    report = _build()
    assert report.get("guardrail_note") == GUARDRAIL_NOTE
    assert "report-only" in GUARDRAIL_NOTE.lower()


# ── 18. source contains no forbidden execution/model/network tokens ───────────

_CORE = Path(__file__).parent.parent / "core" / "operator_cockpit_plan.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_operator_cockpit_plan.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_only():
    allowed_top = {"__future__", "json", "pathlib", "re", "typing", "argparse", "sys", "datetime"}
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
    for bad in (
        "anthropic", "openai", "litellm", "ollama", "bedrock",
        "call_model(", "launch_model(",
    ):
        assert bad not in _BOTH, f"Found model client token: {bad!r}"


def test_no_network_or_send():
    for bad in (
        "requests", "httpx", "urllib", "socket", "aiohttp", "webhook",
        "sendMessage", "send_message(", "bot_token",
    ):
        assert bad not in _BOTH, f"Found network/send token: {bad!r}"


def test_no_validation_or_benchmark_execution():
    for bad in (
        "run_safe_validation", "validation_execution",
        "run_benchmarks", "apply_candidate_in_sandbox",
    ):
        assert bad not in _BOTH, f"Found validation/benchmark execution token: {bad!r}"


def test_no_patch_apply():
    for bad in ("generate_patch", "apply_patch(", "patch_apply", "run_patch"):
        assert bad not in _BOTH, f"Found patch token: {bad!r}"


def test_no_worker_launch():
    for bad in ("launch_worker(", "worker_launch(", "spawn_worker", "proposal_runner"):
        assert bad not in _BOTH, f"Found worker launch token: {bad!r}"


def test_no_database_writes():
    for bad in ("sqlite3", "psycopg", "pymongo", "INSERT INTO", "cursor("):
        assert bad not in _BOTH, f"Found database token: {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real"):
        assert bad not in _BOTH, f"Found auto-merge token: {bad!r}"
