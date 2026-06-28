"""Tests for UX.CLOSE — UX Branch Freeze Checkpoint (report-only).

UX.CLOSE reads the phase registry, the UX.11 behavior preservation report,
integration evidence, and documentation, then writes a deterministic checkpoint
that proves the UX branch (UX.1 through UX.11) is complete, behavior-preserving,
and safe to freeze. It does not choose new work, execute phases, call models,
apply patches, run a validation command, run a benchmark check, contact network
services, launch workers, write to a database, add a backend or mutation route,
change UI behavior, block execution, push, merge, or open PRs.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.ux_branch_freeze_checkpoint import (
    DOC_PHASE_IDS,
    FREEZE_CRITERIA,
    GUARDRAIL_NOTE,
    INTEGRATION_CHECK_SPEC,
    NEXT_BRANCH_HARDEN,
    PHASE_GUARDRAIL_FIELDS,
    REPORT_KIND,
    REQUIRED_UX_PHASE_IDS,
    STATUS_BLOCKED,
    STATUS_PASS,
    STATUS_WARN,
    THIS_PHASE_ID,
    build_ux_branch_freeze_checkpoint,
    gather_ux_branch_freeze_checkpoint_inputs,
    render_ux_branch_freeze_checkpoint_markdown,
    write_ux_branch_freeze_checkpoint,
)
import scripts.create_ux_branch_freeze_checkpoint as script

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"

# Every UX.11 check id referenced by the freeze criteria.
_ALL_SUPPORTING = tuple(sorted({cid for _id, _title, sup in FREEZE_CRITERIA for cid in sup}))


# ── synthetic registry builders ───────────────────────────────────────────────

def _phase(pid, track=None, status="complete", **over) -> dict:
    data = {
        "phase_id": pid,
        "title": f"{pid} title",
        "track": track or pid.split(".")[0],
        "status": status,
        "summary": "Report-only phase.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/x.py", "tests/test_x.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/x.json"],
        "notes": ["Report-only."],
    }
    data.update(over)
    return data


def _all_ux_phases(status_overrides=None, drop=(), phase_overrides=None, include_close=True) -> list:
    status_overrides = status_overrides or {}
    phase_overrides = phase_overrides or {}
    ids = list(REQUIRED_UX_PHASE_IDS) + ([THIS_PHASE_ID] if include_close else [])
    phases = []
    for pid in ids:
        if pid in drop:
            continue
        p = _phase(pid, track="UX", status=status_overrides.get(pid, "complete"))
        if pid in phase_overrides:
            p.update(phase_overrides[pid])
        phases.append(p)
    return phases


def _registry(phases=None, **over) -> dict:
    data = {
        "schema_version": "1.0",
        "updated_at": "2026-06-28T00:00:00+00:00",
        "phases": _all_ux_phases() if phases is None else phases,
    }
    data.update(over)
    return data


# ── synthetic preservation / integration / docs builders ──────────────────────

def _preservation(status="pass", overrides=None, drop=(), remaining=True, extra=None) -> dict:
    overrides = overrides or {}
    extra = extra or {}
    checks = [
        {"check_id": cid, "title": cid, "status": overrides.get(cid, "pass"), "evidence": "x"}
        for cid in _ALL_SUPPORTING
        if cid not in drop
    ]
    # `extra` carries check ids that no freeze criterion maps onto (e.g.
    # safety_labels_visible), so we can exercise the failed_checks gate directly.
    for cid, st in extra.items():
        checks.append({"check_id": cid, "title": cid, "status": st, "evidence": "x"})
    return {
        "report_kind": "unified_workbench_behavior_preservation",
        "report_id": "ux11",
        "created_at": "t",
        "status": status,
        "preservation_checks": checks,
        "route_safety_checks": [],
        "form_safety_checks": [],
        "workbench_safety_checks": [],
        "remaining_risks": (
            [{"risk_id": "manual_browser_confirmation", "status": "needs_manual_review",
              "note": "A human should confirm the live flow."}]
            if remaining else []
        ),
    }


def _clean_integration() -> list:
    return [{"check_id": cid, "present": True, "evidence": "ok"} for cid, _t, _req in INTEGRATION_CHECK_SPEC]


def _docs(readme_text=None, roadmap_text=None) -> list:
    all_ids = " ".join(DOC_PHASE_IDS)
    return [
        {"name": "README", "path": "README.md", "present": True,
         "text": all_ids if readme_text is None else readme_text},
        {"name": "roadmap", "path": "docs/roadmap.md", "present": True,
         "text": all_ids if roadmap_text is None else roadmap_text},
    ]


def _build(**over) -> dict:
    kwargs = dict(
        registry_data=_registry(),
        behavior_preservation=_preservation(),
        integration_records=_clean_integration(),
        docs=_docs(),
        report_id="r",
        created_at="t",
        repo_path=".",
        registry_path="docs/roadmap/phase_registry.json",
    )
    kwargs.update(over)
    return build_ux_branch_freeze_checkpoint(**kwargs)


# ── 1. valid complete UX branch produces pass ─────────────────────────────────

def test_valid_complete_branch_produces_pass():
    report = _build()
    assert report["checkpoint_status"] == STATUS_PASS == "pass"
    assert report["blockers"] == []
    assert report["warnings"] == []
    assert report["recommended_next_step"] == "freeze_ux_branch"
    assert report["report_kind"] == REPORT_KIND == "ux_branch_freeze_checkpoint"
    assert report["ux_arc_summary"]["all_complete"] is True
    assert report["guardrail_summary"]["all_clear"] is True
    assert report["all_freeze_criteria_satisfied"] is True


def test_report_has_all_required_fields():
    report = _build(report_id="rid", created_at="2026-06-28T00:00:00+00:00")
    for key in (
        "report_id", "created_at", "repo_path", "registry_path",
        "checkpoint_status", "checkpoint_reason",
        "registry_summary", "phase_picker_summary",
        "ux_arc_summary", "integration_coverage",
        "behavior_preservation_summary", "freeze_criteria",
        "all_freeze_criteria_satisfied", "remaining_ux_work",
        "documentation_coverage", "validation_story", "guardrail_summary",
        "open_questions", "recommended_next_branch", "recommended_next_phase",
        "next_branch_candidates", "recommended_next_step",
        "warnings", "blockers", "boundaries",
    ):
        assert key in report, key
    assert report["report_id"] == "rid"
    assert report["created_at"] == "2026-06-28T00:00:00+00:00"


# ── 2. missing / incomplete UX phase blocks ───────────────────────────────────

def test_missing_ux_phase_blocks():
    for missing_pid in REQUIRED_UX_PHASE_IDS:
        report = _build(registry_data=_registry(phases=_all_ux_phases(drop=[missing_pid])))
        assert report["checkpoint_status"] == STATUS_BLOCKED, missing_pid
        assert any(missing_pid in b for b in report["blockers"]), missing_pid
        assert report["ux_arc_summary"]["all_complete"] is False


def test_non_complete_ux_phase_blocks():
    for pid in REQUIRED_UX_PHASE_IDS:
        report = _build(
            registry_data=_registry(phases=_all_ux_phases(status_overrides={pid: "proposed"}))
        )
        assert report["checkpoint_status"] == STATUS_BLOCKED, pid
        assert any(pid in b for b in report["blockers"]), pid


# ── 3-6. phase guardrail flags block ──────────────────────────────────────────

def test_model_calls_allowed_true_blocks():
    for pid in REQUIRED_UX_PHASE_IDS:
        report = _build(
            registry_data=_registry(phases=_all_ux_phases(phase_overrides={pid: {"model_calls_allowed": True}}))
        )
        assert report["checkpoint_status"] == STATUS_BLOCKED, pid
        assert any("model_calls_allowed" in b for b in report["blockers"]), pid


def test_network_allowed_true_blocks():
    for pid in REQUIRED_UX_PHASE_IDS:
        report = _build(
            registry_data=_registry(phases=_all_ux_phases(phase_overrides={pid: {"network_allowed": True}}))
        )
        assert report["checkpoint_status"] == STATUS_BLOCKED, pid
        assert any("network_allowed" in b for b in report["blockers"]), pid


def test_merge_allowed_true_blocks():
    for pid in REQUIRED_UX_PHASE_IDS:
        report = _build(
            registry_data=_registry(phases=_all_ux_phases(phase_overrides={pid: {"merge_allowed": True}}))
        )
        assert report["checkpoint_status"] == STATUS_BLOCKED, pid
        assert any("merge_allowed" in b for b in report["blockers"]), pid


def test_writes_real_repo_true_blocks():
    for pid in REQUIRED_UX_PHASE_IDS:
        report = _build(
            registry_data=_registry(phases=_all_ux_phases(phase_overrides={pid: {"writes_real_repo": True}}))
        )
        assert report["checkpoint_status"] == STATUS_BLOCKED, pid
        assert any("writes_real_repo" in b for b in report["blockers"]), pid


# ── 7. required integration evidence missing blocks ───────────────────────────

def test_missing_required_integration_blocks():
    required_ids = [cid for cid, _t, req in INTEGRATION_CHECK_SPEC if req]
    assert required_ids  # sanity
    for cid in required_ids:
        records = [
            {"check_id": c, "present": (c != cid), "evidence": "x"}
            for c, _t, _r in INTEGRATION_CHECK_SPEC
        ]
        report = _build(integration_records=records)
        assert report["checkpoint_status"] == STATUS_BLOCKED, cid
        assert any(cid in b for b in report["blockers"]), cid


def test_missing_optional_integration_warns_not_blocks():
    optional_ids = [cid for cid, _t, req in INTEGRATION_CHECK_SPEC if not req]
    assert optional_ids
    cid = optional_ids[0]
    records = [
        {"check_id": c, "present": (c != cid), "evidence": "x"}
        for c, _t, _r in INTEGRATION_CHECK_SPEC
    ]
    report = _build(integration_records=records)
    assert report["checkpoint_status"] == STATUS_WARN
    assert report["blockers"] == []
    assert any(cid in w for w in report["warnings"])


# ── 8. behavior preservation absent / not pass blocks ─────────────────────────

def test_preservation_absent_blocks():
    for absent in (None, {}):
        report = _build(behavior_preservation=absent)
        assert report["checkpoint_status"] == STATUS_BLOCKED, absent
        assert any("preservation" in b.lower() for b in report["blockers"])
        assert report["behavior_preservation_summary"]["present"] is False


def test_preservation_status_not_pass_blocks():
    report = _build(behavior_preservation=_preservation(
        status="needs_manual_review",
        overrides={"no_fetch_in_workbench": "needs_manual_review"},
    ))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("preservation status" in b.lower() for b in report["blockers"])


# ── 9. freeze criteria not satisfied blocks ───────────────────────────────────

def test_freeze_criterion_failing_check_blocks():
    # status stays pass, but a supporting check fails → freeze criterion fails.
    report = _build(behavior_preservation=_preservation(
        overrides={"no_workbench_mutation_route": "needs_manual_review"},
    ))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert report["all_freeze_criteria_satisfied"] is False
    assert any("no_new_mutation_route" in b for b in report["blockers"])


def test_freeze_criterion_missing_check_blocks():
    report = _build(behavior_preservation=_preservation(drop=["goal_brief_reachable"]))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("assistive_or_preview_only" in b for b in report["blockers"])


def test_unmapped_failing_check_blocks_even_when_status_pass():
    # A UX.11 check that no freeze criterion maps onto (safety_labels_visible)
    # fails, but the report's self-declared status still claims pass. The freeze
    # gate must trust the per-check evidence and block anyway.
    report = _build(behavior_preservation=_preservation(
        status="pass",
        extra={"safety_labels_visible": "needs_manual_review"},
    ))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert report["behavior_preservation_summary"]["failed_checks"] == ["safety_labels_visible"]
    assert any("safety_labels_visible" in b for b in report["blockers"])
    # The freeze criteria themselves stay satisfied (the check is unmapped) ...
    assert report["all_freeze_criteria_satisfied"] is True
    # ... so the block comes from the independent failed-checks gate, not a criterion.
    assert any("despite status" in b for b in report["blockers"])


def test_every_freeze_criterion_satisfied_on_clean_build():
    report = _build()
    crit_by_id = {c["criterion_id"]: c for c in report["freeze_criteria"]}
    for cid, _title, _sup in FREEZE_CRITERIA:
        assert crit_by_id[cid]["satisfied"] is True, cid


# ── 10. picker leftovers warn ─────────────────────────────────────────────────

def test_picker_safe_to_prepare_not_empty_warns():
    extra = _phase("NEXT.1", track="NEXT", status="proposed")
    report = _build(registry_data=_registry(phases=_all_ux_phases() + [extra]))
    assert report["phase_picker_summary"]["safe_to_prepare_count"] > 0
    assert report["checkpoint_status"] == STATUS_WARN
    assert report["blockers"] == []
    assert any("safe" in w.lower() or "candidate" in w.lower() for w in report["warnings"])


def test_picker_top_recommendation_not_null_warns():
    extra = _phase("NEXT.1", track="NEXT", status="proposed")
    report = _build(registry_data=_registry(phases=_all_ux_phases() + [extra]))
    assert report["phase_picker_summary"]["top_recommendation"] is not None
    assert report["checkpoint_status"] == STATUS_WARN
    assert any("recommend" in w.lower() for w in report["warnings"])


# ── 11. missing docs mention warns ────────────────────────────────────────────

def test_missing_docs_mention_warns():
    present_ids = " ".join(pid for pid in DOC_PHASE_IDS if pid != "UX.5")
    report = _build(docs=_docs(readme_text=present_ids, roadmap_text=present_ids))
    doc = report["documentation_coverage"]
    assert "UX.5" in doc["missing_phase_mentions"]
    assert report["checkpoint_status"] == STATUS_WARN
    assert any("UX.5" in w for w in report["warnings"])


def test_full_doc_mention_has_no_doc_warning():
    report = _build()
    doc = report["documentation_coverage"]
    assert doc["missing_phase_mentions"] == []
    assert set(doc["checked_phase_ids"]) == set(DOC_PHASE_IDS)


# ── 12. remaining risk does not downgrade a clean pass ────────────────────────

def test_remaining_risk_is_future_polish_not_warning():
    report = _build()  # _preservation has a remaining risk by default
    assert report["checkpoint_status"] == STATUS_PASS
    assert report["warnings"] == []
    # the remaining risk note flows into future-polish and an open question
    assert any("human should confirm" in item.lower() for item in report["remaining_ux_work"])
    assert any("click" in q.lower() for q in report["open_questions"])


def test_remaining_ux_work_always_present():
    report = _build(behavior_preservation=_preservation(remaining=False))
    assert report["remaining_ux_work"]  # static future-polish list still present


# ── 13. recommended next branch points away from UX ───────────────────────────

def test_recommended_next_branch_is_harden_away_from_ux():
    report = _build()
    assert report["recommended_next_branch"] == NEXT_BRANCH_HARDEN == "HARDEN"
    assert "HARDEN" in report["recommended_next_phase"]
    assert "HARDEN.3" in report["recommended_next_phase"]
    assert "HARDEN.2" not in report["recommended_next_phase"]
    assert report["next_branch_candidates"]
    assert "UX" not in report["recommended_next_branch"]


# ── 14. this-phase registration surface ───────────────────────────────────────

def test_this_phase_registered_and_complete_when_present():
    report = _build()
    arc = report["ux_arc_summary"]
    assert arc["this_phase_id"] == THIS_PHASE_ID == "UX.CLOSE"
    assert arc["this_phase_registered"] is True
    assert arc["this_phase_complete"] is True
    assert report["warnings"] == []


def test_this_phase_absent_warns_only():
    report = _build(registry_data=_registry(phases=_all_ux_phases(include_close=False)))
    assert report["checkpoint_status"] == STATUS_WARN
    assert report["blockers"] == []
    assert any(THIS_PHASE_ID in w for w in report["warnings"])


# ── 15. markdown sections + boundaries ────────────────────────────────────────

def test_markdown_contains_required_sections():
    md = render_ux_branch_freeze_checkpoint_markdown(_build())
    assert "# UX Branch Freeze Checkpoint" in md
    low = md.lower()
    for section in (
        "## summary",
        "## registry summary",
        "## phase picker summary",
        "## ux arc summary",
        "## integration coverage",
        "## behavior preservation summary",
        "## freeze criteria",
        "## remaining ux work",
        "## documentation coverage",
        "## validation story",
        "## guardrail summary",
        "## recommended next branch",
        "## open questions",
        "## recommended next step",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    low = render_ux_branch_freeze_checkpoint_markdown(_build()).lower()
    for phrase in (
        "does not choose new work",
        "does not execute phases",
        "does not call models",
        "does not apply patches",
        "does not run validation",
        "does not run benchmarks",
        "does not contact network services",
        "does not launch workers",
        "does not write to a database",
        "does not add a backend or mutation route",
        "does not change ui behavior",
        "does not block execution",
        "does not push, merge, or open prs",
        "report-only checkpoint",
    ):
        assert phrase in low, phrase


# ── 16. CLI writes JSON + Markdown (real repo) ────────────────────────────────

def test_cli_writes_json_and_markdown_real_repo(tmp_path):
    out = tmp_path / "out"
    res = script.run_create_ux_branch_freeze_checkpoint(
        repo_path=str(PROJECT_ROOT),
        registry=str(REAL_REGISTRY),
        output_root=str(out),
        report_id="cli",
        created_at="2026-06-28T00:00:00+00:00",
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "ux_branch_freeze_checkpoint.json"
    assert mp.name == "ux_branch_freeze_checkpoint.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["report_id"] == "cli"
    # The real repo should freeze cleanly (pass) or at worst pass_with_warnings.
    assert data["checkpoint_status"] in (STATUS_PASS, STATUS_WARN)
    assert data["ux_arc_summary"]["all_complete"] is True
    assert data["behavior_preservation_summary"]["status"] == "pass"


def test_cli_exits_zero_on_real_repo(tmp_path):
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(PROJECT_ROOT),
        "--registry", str(REAL_REGISTRY),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
        "--allow-warnings",
    ])
    assert code == 0


def test_cli_json_flag_prints_summary_json(tmp_path):
    import io
    import contextlib
    out = tmp_path / "out"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = script.main([
            "--repo-path", str(PROJECT_ROOT),
            "--registry", str(REAL_REGISTRY),
            "--output-root", str(out),
            "--report-id", "j",
            "--created-at", "t",
            "--json",
            "--allow-warnings",
        ])
    assert code == 0
    printed = json.loads(buf.getvalue())
    assert printed["report_id"] == "j"
    assert printed["report_kind"] == "ux_branch_freeze_checkpoint"


def test_cli_exits_nonzero_on_blocked(tmp_path):
    # Real repo (UX.11 passes) but a tmp registry missing UX.5 → blocked.
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(_registry(phases=_all_ux_phases(drop=["UX.5"]))), encoding="utf-8")
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(PROJECT_ROOT),
        "--registry", str(reg),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
    ])
    assert code != 0
    data = json.loads((out / "ux_branch_freeze_checkpoint.json").read_text(encoding="utf-8"))
    assert data["checkpoint_status"] == STATUS_BLOCKED


def test_cli_pass_with_warnings_allows_zero_only_with_flag(tmp_path):
    # Tmp registry with an extra proposed phase → picker warning → warn.
    extra = _phase("NEXT.1", track="NEXT", status="proposed")
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(_registry(phases=_all_ux_phases() + [extra])), encoding="utf-8")
    out = tmp_path / "out"
    base = [
        "--repo-path", str(PROJECT_ROOT),
        "--registry", str(reg),
        "--output-root", str(out),
        "--report-id", "w",
        "--created-at", "t",
    ]
    assert script.main(base) != 0
    assert script.main(base + ["--allow-warnings"]) == 0
    data = json.loads((out / "ux_branch_freeze_checkpoint.json").read_text(encoding="utf-8"))
    assert data["checkpoint_status"] == STATUS_WARN


# ── 17. guardrails are all false (except report_only) ─────────────────────────

def test_guardrails_are_all_false_except_report_only():
    report = _build()
    gs = report["guardrail_summary"]
    ux_g = gs["ux_close_guardrails"]
    assert ux_g["report_only"] is True
    for key, val in ux_g.items():
        if key == "report_only":
            continue
        assert val is False, f"UX.CLOSE guardrail {key!r} is not False"
    assert gs["phase_guardrail_violations"] == []
    assert gs["all_clear"] is True


def test_validation_story_shows_not_run():
    vs = _build()["validation_story"]
    assert vs["validation_run"] is False
    assert "note" in vs


# ── 18. purity / determinism ──────────────────────────────────────────────────

def test_build_does_not_mutate_inputs():
    registry = _registry()
    preservation = _preservation()
    integration = _clean_integration()
    docs = _docs()
    snap = copy.deepcopy([registry, preservation, integration, docs])
    build_ux_branch_freeze_checkpoint(
        registry_data=registry,
        behavior_preservation=preservation,
        integration_records=integration,
        docs=docs,
        report_id="r",
        created_at="t",
    )
    assert [registry, preservation, integration, docs] == snap


def test_report_bytes_are_deterministic(tmp_path):
    def run(name: str) -> str:
        res = script.run_create_ux_branch_freeze_checkpoint(
            repo_path=str(PROJECT_ROOT),
            registry=str(REAL_REGISTRY),
            output_root=str(tmp_path / name),
            report_id="fixed",
            created_at="2026-06-28T12:00:00+00:00",
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


def test_gather_tolerates_missing_everything(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    inputs = gather_ux_branch_freeze_checkpoint_inputs(str(repo), str(repo / "missing.json"))
    assert inputs["registry_data"] is None
    assert inputs["registry_load_error"]
    assert isinstance(inputs["integration_records"], list) and inputs["integration_records"]
    # No source present → required integration evidence absent → build blocks.
    report = build_ux_branch_freeze_checkpoint(
        registry_data=inputs["registry_data"],
        registry_load_error=inputs["registry_load_error"],
        behavior_preservation=inputs["behavior_preservation"],
        integration_records=inputs["integration_records"],
        docs=inputs["docs"],
    )
    assert report["checkpoint_status"] == STATUS_BLOCKED


def test_write_against_real_repo_pass(tmp_path):
    res = write_ux_branch_freeze_checkpoint(
        str(PROJECT_ROOT), str(REAL_REGISTRY), str(tmp_path / "out"),
        report_id="w", created_at="t",
    )
    assert res["report"]["checkpoint_status"] in (STATUS_PASS, STATUS_WARN)
    assert res["report"]["all_freeze_criteria_satisfied"] is True


# ── 19. constants match spec ──────────────────────────────────────────────────

def test_required_ux_phase_ids_match_spec():
    assert REQUIRED_UX_PHASE_IDS == tuple(f"UX.{n}" for n in range(1, 12))
    assert len(REQUIRED_UX_PHASE_IDS) == 11


def test_doc_phase_ids_include_close():
    assert THIS_PHASE_ID == "UX.CLOSE"
    assert THIS_PHASE_ID in DOC_PHASE_IDS
    assert set(REQUIRED_UX_PHASE_IDS) <= set(DOC_PHASE_IDS)


def test_phase_guardrail_fields_match_spec():
    assert set(PHASE_GUARDRAIL_FIELDS) == {
        "model_calls_allowed", "network_allowed", "merge_allowed", "writes_real_repo"
    }


def test_status_constants():
    assert STATUS_PASS == "pass"
    assert STATUS_WARN == "pass_with_warnings"
    assert STATUS_BLOCKED == "blocked"


def test_guardrail_note_is_report_only():
    assert "report-only" in GUARDRAIL_NOTE.lower()
    assert _build()["guardrail_note"] == GUARDRAIL_NOTE


def test_freeze_criteria_cover_spec_bullets():
    ids = {cid for cid, _t, _s in FREEZE_CRITERIA}
    assert {
        "no_new_execution_path",
        "no_new_mutation_route",
        "dangerous_actions_separate_and_human_triggered",
        "assistive_or_preview_only",
        "apply_review_outside_input_requires_human_action",
    } <= ids


# ── 20. registry seed integration (real registry) ─────────────────────────────

def test_seed_registry_registers_ux_close_complete():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {p["phase_id"]: p for p in data["phases"]}
    assert THIS_PHASE_ID in by_id, "UX.CLOSE must be registered"
    close = by_id[THIS_PHASE_ID]
    assert close["status"] == "complete"
    assert close["prerequisites"] == ["UX.11"]
    assert close["merge_allowed"] is False
    assert close["network_allowed"] is False
    assert close["model_calls_allowed"] is False
    assert close["writes_real_repo"] is False


# ── 21. forbidden-token / import guards (source-only) ─────────────────────────

_CORE = PROJECT_ROOT / "core" / "ux_branch_freeze_checkpoint.py"
_SCRIPT = PROJECT_ROOT / "scripts" / "create_ux_branch_freeze_checkpoint.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_or_allowed_modules():
    allowed_top = {"__future__", "json", "pathlib", "typing", "core"}
    allowed_core = {"core.phase_picker", "core.unified_workbench_behavior_preservation"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            if top == "core":
                assert module in allowed_core, f"UX.CLOSE may only import {allowed_core!r}, got {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "check_output", "check_call", "shutil", "copytree"):
        assert bad not in _BOTH, f"Found execution primitive: {bad!r}"


def test_no_model_clients():
    for bad in (
        "anthropic", "openai", "litellm", "ollama", "bedrock", "generativeai",
        "codex", "gemini", "deepseek", "call_model(", "launch_model(",
    ):
        assert bad not in _BOTH, f"Found model client token: {bad!r}"


def test_no_network_or_send():
    for bad in (
        "requests", "httpx", "urllib", "socket", "aiohttp", "webhook",
        "api.telegram.org", "sendMessage", "send_message(", "bot_token",
        "api.github.com", "PyGithub", "from github", "import github", "gh pr",
        "n8n.cloud", "n8n.io", "execute_workflow(",
    ):
        assert bad not in _BOTH, f"Found network/send token: {bad!r}"


def test_no_git_commands():
    for bad in (
        "git push", "git checkout", "git branch", "git commit", "git merge",
        "git clone", "git log", "git status", "git_command(",
    ):
        assert bad not in _BOTH, f"Found git command: {bad!r}"


def test_no_validation_or_benchmark_execution():
    for bad in (
        "run_safe_validation", "SafeValidationCommand", "validation_execution",
        "run_benchmarks", "create_managed_sandbox", "apply_candidate_in_sandbox",
    ):
        assert bad not in _BOTH, f"Found validation/benchmark execution token: {bad!r}"


def test_no_patch_apply():
    for bad in ("generate_patch", "apply_patch(", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token: {bad!r}"


def test_no_worker_launch():
    for bad in (
        "import_proposal", "proposal_runner", "launch_worker(", "worker_launch(",
        "spawn_worker", "run_worker(",
    ):
        assert bad not in _BOTH, f"Found worker launch token: {bad!r}"


def test_no_database_writes():
    for bad in ("sqlite3", "psycopg", "pymongo", "INSERT INTO", "cursor(", "vector_db", "vectordb"):
        assert bad not in _BOTH, f"Found database token: {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token: {bad!r}"
