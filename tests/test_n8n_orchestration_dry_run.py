"""Tests for AUTO.2c — n8n Orchestration Dry Run (report-only).

AUTO.2c reads one or more upstream artifacts (an AUTO.1e self-evolution evidence
pack, an AUTO.2a evidence summary contract, and/or an AUTO.2b PR safety contract)
and produces a deterministic *simulation* of how a future n8n workflow would
orchestrate the review chain. It simulates only: it contacts no n8n, calls no
webhooks, makes no network call, sends no chat messages, contacts no remote git
host, runs no git, launches no worker, applies no patch, and calls no model. Live
execution is never performed; human review remains required.

Covers the prescribed cases:
1.  valid ready sources produce dry_run_ready_for_human_review.
2.  needs_more_validation source produces a needs_more_validation verdict.
3.  blocked source blocks the dry run.
4.  missing source blocks the dry run.
5.  malformed source blocks the dry run without crashing.
6.  allow-blocked-dry-run writes a report but keeps live execution false.
7.  a hard guardrail breach blocks the dry run.
8.  live execution is always false.
9.  merge and auto-merge are always false.
10. n8n_contacted / telegram_message_sent / github_contacted / network_call_performed are always false.
11. all steps have actual_contact_performed=false.
12. simulated notifications are previews only.
13. simulated remote actions are previews only.
14. required human checks cover review / branch protection / evidence pack / validation / no direct main push / no auto-merge.
15. Markdown contains all required sections and boundaries.
16. CLI writes JSON + Markdown.
17. CLI exits nonzero for a blocked source unless the allow flag is used.
18. deterministic output with fixed dry_run_id/created_at.
19. source artifacts are not modified.
20. source contains no forbidden execution/network/model/patch/git/remote-send tokens.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.n8n_orchestration_dry_run import (
    N8N_ORCHESTRATION_GUARDRAIL_NOTE,
    REPORT_KIND,
    SOURCE_KINDS,
    STEP_IDS,
    build_n8n_orchestration_dry_run,
    detect_source_kind,
    render_n8n_orchestration_dry_run_markdown,
    write_n8n_orchestration_dry_run,
)
import scripts.create_n8n_orchestration_dry_run as script


# ── synthetic source-artifact builders ─────────────────────────────────────────

def _evidence_pack(**over) -> dict:
    """A realistic AUTO.1e evidence-pack record (ready-for-review by default)."""
    pack = {
        "report_kind": "sandbox_self_evolution_evidence_pack",
        "trial_id": "trial-abc",
        "final_verdict": "ready_for_human_review",
        "recommended_next_step": "review_patch_candidate",
        "source_artifacts": [
            {"label": "Graduation review", "path": ".agent/x/patch_graduation_review.json"},
        ],
        "risk_summary": {
            "safety": "no hard safety breach detected",
            "scope": "patch touches 1 file(s)",
            "validation": "declared validation ran in the sandbox",
            "side_effects": "sandbox-only",
            "budget_or_model_use": "no model call reported",
            "human_gate": "intact",
        },
        "human_review_packet": {
            "phase_or_objective": "AUTO.1f — smoke demo",
            "patch_touched_files": ["pkg/auto1f_smoke_demo.txt"],
            "validation_status": "ran",
        },
        "blockers": [],
        "warnings": [],
        "human_review_required": True,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "real_repo_modified": False,
        "patch_applied_to_real_repo": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
    }
    pack.update(over)
    return pack


def _telegram_contract(**over) -> dict:
    """A realistic AUTO.2a evidence-summary contract record."""
    src = {
        "report_kind": "telegram_evidence_contract",
        "trial_id": "trial-abc",
        "final_verdict": "ready_for_human_review",
        "recommended_next_step": "review_patch_candidate",
        "telegram_message": "Sandbox self-evolution review — trial trial-abc\nVerdict: ready_for_human_review",
        "risk_summary": {
            "safety": "no hard safety breach detected",
            "scope": "patch touches 1 file(s)",
            "validation": "declared validation ran in the sandbox",
            "side_effects": "sandbox-only",
            "human_gate": "intact",
            "merge_authority": "chat approval is not merge authority",
        },
        "guardrails": {
            "human_review_required": True,
            "self_approval_allowed": False,
            "eligible_for_auto_merge": False,
            "real_repo_modified": False,
            "patch_applied_to_real_repo": False,
            "push_performed": False,
            "merge_performed": False,
            "model_call_performed": False,
            "validation_run_by_tool": False,
            "benchmark_run_by_tool": False,
            "worker_launch_performed": False,
            "network_call_performed": False,
            "telegram_message_sent": False,
        },
        "is_sendable": True,
        "send_blockers": [],
        "warnings": [],
    }
    src.update(over)
    return src


def _github_contract(**over) -> dict:
    """A realistic AUTO.2b PR safety contract record."""
    src = {
        "report_kind": "github_pr_safety_contract",
        "trial_id": "trial-abc",
        "final_verdict": "ready_for_human_review",
        "recommended_next_step": "review_patch_candidate",
        "risk_summary": {
            "safety": "no hard safety breach detected",
            "scope": "patch touches 1 file(s)",
            "validation": "declared validation ran in the sandbox",
            "side_effects": "sandbox-only",
            "human_gate": "intact",
            "merge_authority": "a future PR is not merge authority",
        },
        "guardrails": {
            "human_review_required": True,
            "self_approval_allowed": False,
            "eligible_for_auto_merge": False,
            "push_performed": False,
            "merge_performed": False,
            "pr_created": False,
            "branch_created": False,
            "github_contacted": False,
            "network_call_performed": False,
            "model_call_performed": False,
            "worker_launch_performed": False,
            "patch_applied_to_real_repo": False,
            "validation_run_by_tool": False,
            "benchmark_run_by_tool": False,
        },
        "is_pr_draft_allowed_in_future": True,
        "is_merge_allowed": False,
        "is_auto_merge_allowed": False,
        "blockers": [],
        "warnings": [],
    }
    src.update(over)
    return src


def _src(artifact, path="a.json", load_error="") -> dict:
    return {"path": path, "artifact": artifact, "load_error": load_error}


def _ready_sources() -> list:
    return [
        _src(_evidence_pack(), "pack.json"),
        _src(_telegram_contract(), "tg.json"),
        _src(_github_contract(), "gh.json"),
    ]


def _build(sources=None, **kw) -> dict:
    if sources is None:
        sources = _ready_sources()
    return build_n8n_orchestration_dry_run(sources=sources, **kw)


def _step(report: dict, step_id: str) -> dict:
    for step in report["steps"]:
        if step["step_id"] == step_id:
            return step
    raise AssertionError(f"step {step_id!r} not found")


def _write(tmp_path: Path, artifact: dict, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return path


# ── 1. ready sources → dry_run_ready_for_human_review ──────────────────────────

def test_ready_sources_produce_dry_run_ready():
    report = _build(dry_run_id="d", created_at="t")
    assert report["overall_verdict"] == "dry_run_ready_for_human_review"
    assert report["is_orchestration_allowed_in_future"] is True
    assert report["is_live_execution_allowed"] is False
    assert report["is_merge_allowed"] is False
    assert report["is_auto_merge_allowed"] is False
    assert report["trial_id"] == "trial-abc"
    assert report["report_kind"] == REPORT_KIND == "n8n_orchestration_dry_run"
    assert report["blockers"] == []


def test_report_has_all_required_fields():
    report = _build(dry_run_id="d", created_at="2026-06-19T00:00:00+00:00")
    for key in (
        "dry_run_id",
        "created_at",
        "source_artifacts",
        "detected_sources",
        "trial_id",
        "overall_verdict",
        "orchestration_plan",
        "steps",
        "simulated_notifications",
        "simulated_remote_actions",
        "required_human_checks",
        "risk_summary",
        "blockers",
        "warnings",
        "guardrails",
        "is_orchestration_allowed_in_future",
        "is_live_execution_allowed",
        "is_merge_allowed",
        "is_auto_merge_allowed",
    ):
        assert key in report, key
    assert report["dry_run_id"] == "d"
    assert report["created_at"] == "2026-06-19T00:00:00+00:00"


def test_detected_sources_lists_kinds():
    report = _build()
    assert set(report["detected_sources"]) == {
        "self_evolution_evidence_pack",
        "telegram_evidence_contract",
        "github_pr_safety_contract",
    }


def test_source_artifact_records_have_fields():
    report = _build()
    assert len(report["source_artifacts"]) == 3
    for rec in report["source_artifacts"]:
        for key in ("path", "source_kind", "loaded", "verdict", "recommended_next_step", "errors", "warnings"):
            assert key in rec, key
        assert rec["loaded"] is True


# ── steps ──────────────────────────────────────────────────────────────────────

def test_steps_have_expected_ids_in_order():
    report = _build()
    ids = [s["step_id"] for s in report["steps"]]
    assert ids == list(STEP_IDS)
    assert ids == [
        "load_evidence_pack",
        "build_telegram_summary",
        "build_github_pr_safety_contract",
        "prepare_human_review_notification",
        "wait_for_human_review",
        "prepare_future_draft_pr_request",
        "stop_before_live_execution",
    ]


def test_steps_have_all_fields():
    report = _build()
    for step in report["steps"]:
        for key in (
            "step_id",
            "name",
            "status",
            "input_artifacts",
            "output_preview",
            "would_contact",
            "actual_contact_performed",
            "allowed_in_dry_run",
            "blocked_actions",
        ):
            assert key in step, (step["step_id"], key)


# ── 11. all steps actual_contact_performed=false ───────────────────────────────

def test_all_steps_actual_contact_performed_false():
    for sources in (_ready_sources(), [_src(_blocked := _evidence_pack(final_verdict="blocked"))], []):
        report = build_n8n_orchestration_dry_run(sources=sources)
        for step in report["steps"]:
            assert step["actual_contact_performed"] is False, step["step_id"]


# ── 2. needs_more_validation ───────────────────────────────────────────────────

def test_needs_more_validation_verdict():
    sources = [
        _src(_evidence_pack(final_verdict="needs_more_validation", recommended_next_step="request_more_validation")),
        _src(_telegram_contract(final_verdict="needs_more_validation")),
        _src(_github_contract(final_verdict="needs_more_validation")),
    ]
    report = build_n8n_orchestration_dry_run(sources=sources)
    assert report["overall_verdict"] == "needs_more_validation"
    assert report["is_orchestration_allowed_in_future"] is False
    assert report["is_live_execution_allowed"] is False
    # A review notification may be prepared, but no draft-PR request.
    assert _step(report, "prepare_human_review_notification")["allowed_in_dry_run"] is True
    draft = _step(report, "prepare_future_draft_pr_request")
    assert draft["allowed_in_dry_run"] is False
    assert draft["status"] == "blocked"


# ── 3-5. blocked / missing / malformed ─────────────────────────────────────────

def test_blocked_source_blocks_dry_run():
    sources = [_src(_evidence_pack(final_verdict="blocked", blockers=["a merge was performed (merge_performed)"]))]
    report = build_n8n_orchestration_dry_run(sources=sources)
    assert report["overall_verdict"] == "blocked"
    assert report["is_orchestration_allowed_in_future"] is False
    assert report["is_live_execution_allowed"] is False
    assert report["blockers"]


def test_missing_source_blocks_dry_run():
    # A provided path that could not be loaded (artifact is None).
    sources = [_src(None, path="gone.json", load_error="could not read gone.json")]
    report = build_n8n_orchestration_dry_run(sources=sources)
    assert report["overall_verdict"] == "blocked"
    assert report["is_orchestration_allowed_in_future"] is False
    assert report["blockers"]
    assert report["source_artifacts"][0]["loaded"] is False


def test_no_sources_blocks_dry_run():
    report = build_n8n_orchestration_dry_run(sources=[])
    assert report["overall_verdict"] == "blocked"
    assert report["is_orchestration_allowed_in_future"] is False
    assert report["blockers"]


def test_malformed_source_blocks_without_crashing():
    for bad in ("nope", 5, [], None, {}):
        report = build_n8n_orchestration_dry_run(sources=[_src(bad)])
        assert report["overall_verdict"] == "blocked"
        assert report["is_live_execution_allowed"] is False
        assert report["is_merge_allowed"] is False


# ── 7. hard guardrail breach blocks dry run ────────────────────────────────────

def test_hard_guardrail_breach_in_pack_blocks_dry_run():
    for field in (
        "eligible_for_auto_merge",
        "real_repo_modified",
        "patch_applied_to_real_repo",
        "push_performed",
        "merge_performed",
        "model_call_performed",
        "worker_launch_performed",
        "self_approval_allowed",
    ):
        sources = [_src(_evidence_pack(**{field: True})), _src(_telegram_contract()), _src(_github_contract())]
        report = build_n8n_orchestration_dry_run(sources=sources)
        assert report["overall_verdict"] == "blocked", field
        assert report["is_orchestration_allowed_in_future"] is False, field
        assert any(field in b for b in report["blockers"]), field


def test_hard_guardrail_breach_in_github_contract_blocks_dry_run():
    gh = _github_contract()
    gh["guardrails"]["pr_created"] = True
    report = build_n8n_orchestration_dry_run(sources=[_src(_evidence_pack()), _src(gh)])
    assert report["overall_verdict"] == "blocked"
    assert any("pr_created" in b for b in report["blockers"])


def test_missing_human_review_required_blocks_dry_run():
    report = build_n8n_orchestration_dry_run(sources=[_src(_evidence_pack(human_review_required=False))])
    assert report["overall_verdict"] == "blocked"


# ── 8-9. live / merge / auto-merge always false ────────────────────────────────

def test_live_execution_is_always_false():
    for sources in (
        _ready_sources(),
        [_src(_evidence_pack(final_verdict="needs_more_validation"))],
        [_src(_evidence_pack(final_verdict="blocked"))],
        [_src(None)],
        [],
        [_src(_evidence_pack(push_performed=True))],
    ):
        report = build_n8n_orchestration_dry_run(sources=sources)
        assert report["is_live_execution_allowed"] is False
        assert report["guardrails"]["live_execution_allowed"] is False


def test_merge_and_auto_merge_are_always_false():
    for sources in (_ready_sources(), [_src(_evidence_pack(final_verdict="blocked"))], []):
        report = build_n8n_orchestration_dry_run(sources=sources)
        assert report["is_merge_allowed"] is False
        assert report["is_auto_merge_allowed"] is False


# ── 10 + guardrails. remote booleans always false ──────────────────────────────

_EXPECTED_GUARDRAILS = {
    "human_review_required": True,
    "self_approval_allowed": False,
    "eligible_for_auto_merge": False,
    "live_execution_allowed": False,
    "network_call_performed": False,
    "n8n_contacted": False,
    "telegram_message_sent": False,
    "github_contacted": False,
    "pr_created": False,
    "branch_created": False,
    "push_performed": False,
    "merge_performed": False,
    "model_call_performed": False,
    "worker_launch_performed": False,
    "patch_applied_to_real_repo": False,
    "validation_run_by_tool": False,
    "benchmark_run_by_tool": False,
}


def test_guardrail_booleans_are_preserved():
    for sources in (_ready_sources(), [_src(_evidence_pack(final_verdict="blocked"))], [], [_src(None)]):
        guardrails = build_n8n_orchestration_dry_run(sources=sources)["guardrails"]
        assert guardrails == _EXPECTED_GUARDRAILS


def test_remote_contact_booleans_are_always_false():
    for sources in (_ready_sources(), [_src(_evidence_pack(final_verdict="needs_more_validation"))]):
        guardrails = build_n8n_orchestration_dry_run(sources=sources)["guardrails"]
        assert guardrails["n8n_contacted"] is False
        assert guardrails["telegram_message_sent"] is False
        assert guardrails["github_contacted"] is False
        assert guardrails["network_call_performed"] is False
        assert guardrails["pr_created"] is False
        assert guardrails["branch_created"] is False


# ── 12-13. notifications / remote actions are previews only ────────────────────

def test_simulated_notifications_are_previews_only():
    notes = _build()["simulated_notifications"]
    assert isinstance(notes, list) and notes
    for note in notes:
        assert note["actual_send_performed"] is False
        assert "channel" in note and "body_preview" in note


def test_simulated_remote_actions_are_previews_only():
    actions = _build()["simulated_remote_actions"]
    assert isinstance(actions, list) and actions
    for action in actions:
        assert action["actual_action_performed"] is False
        assert "target" in action and "action" in action


# ── 14. required human checks ──────────────────────────────────────────────────

def test_required_human_checks_cover_required_concepts():
    checks = _build()["required_human_checks"]
    assert isinstance(checks, list) and checks
    joined = " ".join(checks).lower()
    assert "review" in joined
    assert "branch protection" in joined
    assert "evidence pack" in joined
    assert "validation" in joined
    assert "no direct push" in joined and "main" in joined
    assert "auto-merge" in joined


# ── risk summary / orchestration plan ──────────────────────────────────────────

def test_risk_summary_carries_orchestration_and_merge_note():
    risk = _build()["risk_summary"]
    assert isinstance(risk, dict)
    joined = " ".join(str(v) for v in risk.values()).lower()
    assert "merge authority" in joined
    assert "live execution" in joined


def test_orchestration_plan_halts_before_live_execution():
    plan = _build()["orchestration_plan"]
    assert isinstance(plan, dict)
    assert plan["halts_at"] == "stop_before_live_execution"
    assert plan["is_live_execution_allowed"] is False


def test_guardrail_note_is_report_only():
    assert "report-only" in N8N_ORCHESTRATION_GUARDRAIL_NOTE.lower()
    assert _build()["guardrail_note"] == N8N_ORCHESTRATION_GUARDRAIL_NOTE


# ── source kind detection ──────────────────────────────────────────────────────

def test_detect_source_kind():
    assert detect_source_kind(_evidence_pack()) == "self_evolution_evidence_pack"
    assert detect_source_kind(_telegram_contract()) == "telegram_evidence_contract"
    assert detect_source_kind(_github_contract()) == "github_pr_safety_contract"
    assert detect_source_kind({"report_kind": "mystery"}) == "unknown"


# ── 19. sources are not modified ───────────────────────────────────────────────

def test_build_does_not_mutate_sources():
    pack = _evidence_pack()
    tg = _telegram_contract()
    gh = _github_contract()
    snap = copy.deepcopy([pack, tg, gh])
    build_n8n_orchestration_dry_run(sources=[_src(pack), _src(tg), _src(gh)], dry_run_id="d", created_at="t")
    assert [pack, tg, gh] == snap


# ── 15. Markdown sections + boundaries ─────────────────────────────────────────

def test_markdown_contains_all_sections():
    md = render_n8n_orchestration_dry_run_markdown(_build(dry_run_id="d", created_at="t"))
    assert "# n8n Orchestration Dry Run" in md
    low = md.lower()
    for section in (
        "## summary",
        "## source artifacts",
        "## orchestration plan",
        "## simulated steps",
        "## simulated notifications",
        "## simulated remote actions",
        "## required human checks",
        "## risk summary",
        "## blockers",
        "## warnings",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    low = render_n8n_orchestration_dry_run_markdown(_build()).lower()
    assert "does not contact n8n" in low
    assert "does not call webhooks" in low
    assert "does not send telegram messages" in low
    assert "does not contact github" in low
    assert "does not run git commands" in low
    assert "does not create branches" in low
    assert "does not open prs" in low
    assert "does not push or merge" in low
    assert "does not call models" in low
    assert "does not launch workers" in low
    assert "does not apply patches" in low
    assert "does not run validation or benchmarks" in low
    assert "dry-run contract only" in low
    assert "human review remains required" in low


def test_markdown_shows_blocked_blockers():
    sources = [_src(_evidence_pack(final_verdict="blocked", blockers=["a merge was performed (merge_performed)"]))]
    md = render_n8n_orchestration_dry_run_markdown(build_n8n_orchestration_dry_run(sources=sources)).lower()
    assert "blocked" in md


# ── 16-18. CLI behaviour ───────────────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    pack = _write(tmp_path, _evidence_pack(), "pack.json")
    tg = _write(tmp_path, _telegram_contract(), "tg.json")
    gh = _write(tmp_path, _github_contract(), "gh.json")
    out = tmp_path / "out"
    res = script.run_create_n8n_orchestration_dry_run(
        evidence_pack=str(pack),
        telegram_contract=str(tg),
        github_pr_contract=str(gh),
        output_root=str(out),
        dry_run_id="cli",
        created_at="2026-06-19T00:00:00+00:00",
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "n8n_orchestration_dry_run.json"
    assert mp.name == "n8n_orchestration_dry_run.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["dry_run_id"] == "cli"
    assert data["overall_verdict"] == "dry_run_ready_for_human_review"
    assert set(data["detected_sources"]) == {
        "self_evolution_evidence_pack",
        "telegram_evidence_contract",
        "github_pr_safety_contract",
    }


def test_cli_main_smoke(tmp_path):
    pack = _write(tmp_path, _evidence_pack(), "pack.json")
    out = tmp_path / "out"
    code = script.main(["--evidence-pack", str(pack), "--output-root", str(out), "--dry-run-id", "s", "--created-at", "t"])
    assert code == 0
    assert (out / "n8n_orchestration_dry_run.json").is_file()
    assert (out / "n8n_orchestration_dry_run.md").is_file()


def test_cli_exits_nonzero_for_blocked_source(tmp_path):
    pack = _write(tmp_path, _evidence_pack(final_verdict="blocked", blockers=["x"]), "pack.json")
    out = tmp_path / "out"
    code = script.main(["--evidence-pack", str(pack), "--output-root", str(out), "--dry-run-id", "x", "--created-at", "t"])
    assert code != 0
    assert (out / "n8n_orchestration_dry_run.json").is_file()


def test_cli_exits_nonzero_for_missing_source(tmp_path):
    out = tmp_path / "out"
    code = script.main(
        ["--evidence-pack", str(tmp_path / "nope.json"), "--output-root", str(out), "--dry-run-id", "x", "--created-at", "t"]
    )
    assert code != 0
    data = json.loads((out / "n8n_orchestration_dry_run.json").read_text(encoding="utf-8"))
    assert data["is_live_execution_allowed"] is False
    assert data["blockers"]


def test_cli_no_sources_exits_nonzero(tmp_path):
    out = tmp_path / "out"
    code = script.main(["--output-root", str(out), "--dry-run-id", "x", "--created-at", "t"])
    assert code != 0


def test_cli_allow_blocked_dry_run_returns_zero_but_keeps_live_false(tmp_path):
    pack = _write(tmp_path, _evidence_pack(final_verdict="blocked", blockers=["x"]), "pack.json")
    out = tmp_path / "out"
    code = script.main(
        [
            "--evidence-pack", str(pack),
            "--output-root", str(out),
            "--dry-run-id", "x",
            "--created-at", "t",
            "--allow-blocked-dry-run",
        ]
    )
    assert code == 0
    data = json.loads((out / "n8n_orchestration_dry_run.json").read_text(encoding="utf-8"))
    assert data["is_live_execution_allowed"] is False
    assert data["is_orchestration_allowed_in_future"] is False


def test_cli_json_flag_prints_report(tmp_path, capsys):
    pack = _write(tmp_path, _evidence_pack(), "pack.json")
    out = tmp_path / "out"
    code = script.main(
        ["--evidence-pack", str(pack), "--output-root", str(out), "--dry-run-id", "j", "--created-at", "t", "--json"]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["dry_run_id"] == "j"
    assert printed["report_kind"] == "n8n_orchestration_dry_run"


def test_cli_deterministic_output(tmp_path):
    pack = _write(tmp_path, _evidence_pack(), "pack.json")
    tg = _write(tmp_path, _telegram_contract(), "tg.json")

    def run(name: str) -> str:
        res = script.run_create_n8n_orchestration_dry_run(
            evidence_pack=str(pack),
            telegram_contract=str(tg),
            output_root=str(tmp_path / name),
            dry_run_id="fixed",
            created_at="2026-06-19T12:00:00+00:00",
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


def test_cli_does_not_modify_sources(tmp_path):
    pack = _evidence_pack()
    pack_path = _write(tmp_path, pack, "pack.json")
    before = pack_path.read_bytes()
    out = tmp_path / "out"
    script.main(["--evidence-pack", str(pack_path), "--output-root", str(out), "--dry-run-id", "x", "--created-at", "t"])
    assert pack_path.read_bytes() == before


def test_write_core_helper(tmp_path):
    out = tmp_path / "core_out"
    res = write_n8n_orchestration_dry_run(_ready_sources(), str(out), dry_run_id="cr", created_at="t")
    assert res["ok"] is True
    assert Path(res["json_path"]).is_file()
    assert Path(res["md_path"]).is_file()
    assert res["report"]["dry_run_id"] == "cr"


# ── 20. forbidden-token / import guards (source-only) ──────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "n8n_orchestration_dry_run.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_n8n_orchestration_dry_run.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_only():
    allowed_top = {"__future__", "json", "pathlib", "typing"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            assert top != "core", f"AUTO.2c core must not import other core modules: {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_model_clients():
    for bad in (
        "anthropic",
        "openai",
        "litellm",
        "ollama",
        "bedrock",
        "generativeai",
        "claude",
        "codex",
        "gemini",
        "deepseek",
        "call_model(",
        "launch_model(",
    ):
        assert bad not in _BOTH, f"Found model client token {bad!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "check_output", "check_call", "shutil", "copytree"):
        assert bad not in _BOTH, f"Found execution primitive token {bad!r}"


def test_no_validation_or_benchmark_execution():
    for bad in (
        "run_safe_validation",
        "SafeValidationCommand",
        "validation_execution",
        "run_benchmarks",
        "create_managed_sandbox",
        "apply_candidate_in_sandbox",
    ):
        assert bad not in _BOTH, f"Found validation/benchmark execution token {bad!r}"


def test_no_patch_generation_or_apply():
    for bad in ("generate_patch", "apply_patch(", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_network_n8n_send_or_git_behaviour():
    # No network library, no webhook, no n8n/Telegram/GitHub API/CLI, no git
    # subcommands. Bare "n8n"/"telegram"/"github"/"git" are NOT forbidden (they are
    # required module / field / source-kind identifiers); the *call / command / API*
    # shapes are.
    for bad in (
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "n8n.cloud",
        "n8n.io",
        "execute_workflow(",
        "api.telegram.org",
        "sendMessage",
        "send_message(",
        "bot_token",
        "api.github.com",
        "PyGithub",
        "from github",
        "import github",
        "gh pr",
        "git push",
        "git checkout",
        "git branch",
        "git commit",
        "git merge",
        "git clone",
    ):
        assert bad not in _BOTH, f"Found network/n8n/send/git token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "launch_worker(", "worker_launch(", "spawn_worker", "run_worker("):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"


# ── constants exposure ─────────────────────────────────────────────────────────

def test_source_kinds_constant_matches_spec():
    assert set(SOURCE_KINDS) == {
        "self_evolution_evidence_pack",
        "telegram_evidence_contract",
        "github_pr_safety_contract",
        "unknown",
    }


def test_step_ids_constant_matches_spec():
    assert STEP_IDS == (
        "load_evidence_pack",
        "build_telegram_summary",
        "build_github_pr_safety_contract",
        "prepare_human_review_notification",
        "wait_for_human_review",
        "prepare_future_draft_pr_request",
        "stop_before_live_execution",
    )
