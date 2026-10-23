"""Tests for ROAD.2 â€” Phase Picker / Night Candidate Report (report-only).

ROAD.2 reads the ROAD.1 machine-readable phase registry and classifies phases
into safe-candidate buckets. It recommends candidate phases. It does not execute
phases, modify code, call models, run validation or a benchmark check, apply
patches, or create branches, PRs, or automation. It reuses the ROAD.1 validator
and never duplicates the schema validation.

Covers the prescribed cases:
1.  valid registry produces a report.
2.  invalid registry produces no candidates.
3.  complete phases go to complete_or_history.
4.  parked / deferred phases go to deferred_or_parked.
5.  blocked budget goes to blocked.
6.  blocked risk goes to blocked.
7.  merge_allowed=true goes to blocked.
8.  human_approval_required=false goes to blocked for proposed/active.
9.  writes_real_repo=true goes to blocked for proposed/active.
10. requires_sandbox=true goes to sandbox_required.
11. SANDBOX_2_DRAFT_PATCH goes to sandbox_required.
12. REMOTE_3_DRAFT_PR goes to human_approval_required.
13. strong_model_requires_approval goes to human_approval_required.
14. network_allowed=true goes to human_approval_required or blocked.
15. local observe/prepare low-risk phase goes to safe_to_prepare.
16. top recommendation prefers a safe local ROAD phase over higher-risk phases.
17. deterministic sorting within a bucket.
18. Markdown contains all sections and boundaries.
19. CLI writes JSON + Markdown.
20. CLI exits nonzero on invalid registry unless the allow flag is used.
21. seed registry produces expected buckets.
22. source contains no forbidden execution/network/model/patch tokens.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.phase_picker import (
    BUCKETS,
    PHASE_PICKER_GUARDRAIL_NOTE,
    RECOMMENDED_NEXT_STEPS,
    REPORT_KIND,
    pick_phase_candidates,
    render_phase_picker_markdown,
    summarize_phase_candidates,
    write_phase_picker_report,
)
import scripts.create_phase_picker_report as script


# â”€â”€ synthetic registry builders â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _phase(**over) -> dict:
    data = {
        "phase_id": "ROAD.2",
        "title": "Phase Picker / Night Candidate Report",
        "track": "ROAD",
        "status": "proposed",
        "summary": "Report-only selector for safe candidate phases.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/phase_picker.py", "tests/test_phase_picker.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest tests/test_phase_picker.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/roadmap/phase_picker_report.json"],
        "notes": ["Report-only. Does not execute selected phases."],
    }
    data.update(over)
    return data


def _registry(phases=None, **over) -> dict:
    data = {
        "schema_version": "1.0",
        "updated_at": "2026-06-18T00:00:00+00:00",
        "phases": [_phase()] if phases is None else phases,
    }
    data.update(over)
    return data


def _pick_one(phase) -> tuple[str, dict]:
    """Classify a single phase; return (bucket_name, phase_summary)."""
    pick = pick_phase_candidates(_registry(phases=[phase]))
    for name, items in pick["buckets"].items():
        for item in items:
            if item["phase_id"] == phase["phase_id"]:
                return name, item
    raise AssertionError(f"phase {phase['phase_id']} not found in any bucket")


def _bucket_of(phase) -> str:
    return _pick_one(phase)[0]


def _report(data, **kw) -> dict:
    return summarize_phase_candidates(pick_phase_candidates(data), **kw)


# â”€â”€ 1. valid registry produces a report â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_valid_registry_produces_report():
    pick = pick_phase_candidates(_registry())
    assert pick["registry_valid"] is True
    assert pick["phase_count"] == 1
    assert set(pick["buckets"].keys()) == set(BUCKETS)


def test_summary_has_required_report_fields():
    report = _report(
        _registry(),
        report_id="rid",
        created_at="2026-06-18T00:00:00+00:00",
        registry_path="docs/roadmap/phase_registry.json",
    )
    for key in (
        "report_id",
        "created_at",
        "registry_path",
        "registry_valid",
        "phase_count",
        "bucket_counts",
        "safe_to_prepare",
        "sandbox_required",
        "human_approval_required",
        "blocked",
        "deferred_or_parked",
        "complete_or_history",
        "top_recommendation",
        "errors",
        "warnings",
        "boundaries",
    ):
        assert key in report, key
    assert report["report_id"] == "rid"
    assert report["created_at"] == "2026-06-18T00:00:00+00:00"
    assert report["registry_path"] == "docs/roadmap/phase_registry.json"
    assert report["report_kind"] == REPORT_KIND == "phase_picker_report"


def test_phase_summary_fields_present():
    bucket, item = _pick_one(_phase())
    for key in (
        "phase_id",
        "title",
        "track",
        "status",
        "bucket",
        "risk_level",
        "automation_level",
        "budget_tier",
        "reasons",
        "recommended_next_step",
    ):
        assert key in item, key
    assert item["bucket"] == bucket
    assert isinstance(item["reasons"], list) and item["reasons"]
    assert item["recommended_next_step"] in RECOMMENDED_NEXT_STEPS


def test_bucket_counts_sum_to_phase_count():
    report = _report(_registry(), report_id="r", created_at="t")
    assert sum(report["bucket_counts"].values()) == report["phase_count"] == 1


# â”€â”€ 2. invalid registry produces no candidates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_invalid_registry_produces_no_candidates():
    phases = [_phase(phase_id="ROAD.2", merge_allowed=True), _phase(phase_id="AUTO.2a", track="AUTO")]
    pick = pick_phase_candidates(_registry(phases=phases))
    assert pick["registry_valid"] is False
    assert pick["buckets"]["safe_to_prepare"] == []
    assert pick["top_recommendation"] is None


def test_invalid_registry_report_lists_errors_and_no_candidates():
    report = _report(
        _registry(phases=[_phase(merge_allowed=True)]), report_id="r", created_at="t"
    )
    assert report["registry_valid"] is False
    assert report["errors"]
    assert report["safe_to_prepare"] == []
    assert report["top_recommendation"] is None


def test_none_input_is_invalid_and_empty():
    pick = pick_phase_candidates(None)
    assert pick["registry_valid"] is False
    assert pick["phase_count"] == 0
    assert all(pick["buckets"][name] == [] for name in BUCKETS)
    assert pick["top_recommendation"] is None


# â”€â”€ 3. complete phases â†’ complete_or_history â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_complete_phase_goes_to_complete_or_history():
    bucket, item = _pick_one(_phase(status="complete"))
    assert bucket == "complete_or_history"
    assert item["recommended_next_step"] == "no_action_complete"


# â”€â”€ 4. parked / deferred â†’ deferred_or_parked â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_parked_phase_goes_to_deferred_or_parked():
    bucket, item = _pick_one(_phase(status="parked"))
    assert bucket == "deferred_or_parked"
    assert item["recommended_next_step"] == "keep_parked"


def test_deferred_phase_goes_to_deferred_or_parked():
    assert _bucket_of(_phase(status="deferred")) == "deferred_or_parked"


# â”€â”€ 5-6. blocked budget / risk â†’ blocked â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_blocked_budget_goes_to_blocked():
    bucket, item = _pick_one(_phase(budget_tier="blocked"))
    assert bucket == "blocked"
    assert item["recommended_next_step"] == "blocked_until_metadata_fixed"


def test_blocked_risk_goes_to_blocked():
    assert _bucket_of(_phase(risk_level="blocked")) == "blocked"


# â”€â”€ 7. merge_allowed=true â†’ blocked â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_merge_allowed_goes_to_blocked():
    bucket, item = _pick_one(_phase(merge_allowed=True))
    assert bucket == "blocked"
    assert any("merge_allowed" in r for r in item["reasons"])


# â”€â”€ 8. human_approval_required=false â†’ blocked (proposed/active) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_human_approval_false_goes_to_blocked_proposed():
    assert _bucket_of(_phase(status="proposed", human_approval_required=False)) == "blocked"


def test_human_approval_false_goes_to_blocked_active():
    assert _bucket_of(_phase(status="active", human_approval_required=False)) == "blocked"


# â”€â”€ 9. writes_real_repo=true â†’ blocked (proposed/active) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_writes_real_repo_goes_to_blocked_proposed():
    assert _bucket_of(_phase(status="proposed", writes_real_repo=True)) == "blocked"


def test_writes_real_repo_goes_to_blocked_active():
    assert _bucket_of(_phase(status="active", writes_real_repo=True)) == "blocked"


# â”€â”€ missing allowed_files / validation â†’ blocked â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_missing_allowed_files_goes_to_blocked():
    assert _bucket_of(_phase(allowed_files=[])) == "blocked"


def test_missing_validation_goes_to_blocked():
    assert _bucket_of(_phase(validation=[])) == "blocked"


# â”€â”€ 10. requires_sandbox=true â†’ sandbox_required â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_requires_sandbox_goes_to_sandbox_required():
    bucket, item = _pick_one(_phase(requires_sandbox=True))
    assert bucket == "sandbox_required"
    assert item["recommended_next_step"] == "prepare_sandbox_trial_contract"


# â”€â”€ 11. SANDBOX_2_DRAFT_PATCH / patch mention / patch path â†’ sandbox_required â”€â”€â”€

def test_sandbox_automation_goes_to_sandbox_required():
    assert _bucket_of(_phase(automation_level="SANDBOX_2_DRAFT_PATCH")) == "sandbox_required"


def test_patch_candidate_mention_goes_to_sandbox_required():
    phase = _phase(summary="Evaluate the patch candidate quality offline before review.")
    assert _bucket_of(phase) == "sandbox_required"


def test_patch_path_in_allowed_files_goes_to_sandbox_required():
    phase = _phase(allowed_files=["core/patch_safety.py", "tests/test_patch_safety.py"])
    assert _bucket_of(phase) == "sandbox_required"


# â”€â”€ 12. REMOTE_3_DRAFT_PR â†’ human_approval_required â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_remote_pr_goes_to_human_approval_required():
    bucket, item = _pick_one(_phase(automation_level="REMOTE_3_DRAFT_PR"))
    assert bucket == "human_approval_required"
    assert item["recommended_next_step"] == "request_human_approval"


# â”€â”€ 13. strong_model_requires_approval â†’ human_approval_required â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_strong_model_budget_goes_to_human_approval_required():
    assert _bucket_of(_phase(budget_tier="strong_model_requires_approval")) == "human_approval_required"


def test_model_calls_allowed_goes_to_human_approval_required():
    # model_calls_allowed=true is valid only with the approval budget tier.
    phase = _phase(model_calls_allowed=True, budget_tier="strong_model_requires_approval")
    assert _bucket_of(phase) == "human_approval_required"


# â”€â”€ 14. network_allowed=true â†’ human_approval_required or blocked â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_network_allowed_goes_to_human_or_blocked():
    assert _bucket_of(_phase(network_allowed=True)) in {"blocked", "human_approval_required"}


# â”€â”€ 15. local observe/prepare low-risk â†’ safe_to_prepare â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_local_observe_low_risk_goes_to_safe_to_prepare():
    bucket, item = _pick_one(_phase(automation_level="LOCAL_0_OBSERVE", risk_level="low"))
    assert bucket == "safe_to_prepare"
    assert item["recommended_next_step"] == "prepare_worker_assignment"


def test_local_prepare_medium_risk_goes_to_safe_to_prepare():
    assert _bucket_of(_phase(automation_level="LOCAL_1_PREPARE", risk_level="medium")) == "safe_to_prepare"


def test_safe_phase_with_unmet_prerequisite_recommends_complete_prerequisites():
    phases = [
        _phase(phase_id="ROAD.1", status="proposed"),
        _phase(phase_id="ROAD.2", prerequisites=["ROAD.1"]),
    ]
    pick = pick_phase_candidates(_registry(phases=phases))
    safe = {p["phase_id"]: p for p in pick["buckets"]["safe_to_prepare"]}
    assert safe["ROAD.1"]["recommended_next_step"] == "prepare_worker_assignment"
    assert safe["ROAD.2"]["recommended_next_step"] == "complete_prerequisites"


def test_safe_phase_with_completed_prerequisite_is_ready():
    phases = [
        _phase(phase_id="ROAD.1", status="complete"),
        _phase(phase_id="ROAD.2", prerequisites=["ROAD.1"]),
    ]
    pick = pick_phase_candidates(_registry(phases=phases))
    safe = {p["phase_id"]: p for p in pick["buckets"]["safe_to_prepare"]}
    assert safe["ROAD.2"]["recommended_next_step"] == "prepare_worker_assignment"


# â”€â”€ 16. top recommendation prefers a safe local ROAD phase â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_top_recommendation_prefers_safe_local_road_phase():
    phases = [
        _phase(phase_id="AUTO.1a", track="AUTO", risk_level="low", automation_level="LOCAL_0_OBSERVE"),
        _phase(phase_id="MODEL.1", track="MODEL", risk_level="medium", automation_level="LOCAL_0_OBSERVE"),
        _phase(phase_id="ROAD.3", track="ROAD", risk_level="low", automation_level="LOCAL_0_OBSERVE"),
    ]
    pick = pick_phase_candidates(_registry(phases=phases))
    assert {p["phase_id"] for p in pick["buckets"]["safe_to_prepare"]} == {"AUTO.1a", "MODEL.1", "ROAD.3"}
    assert pick["top_recommendation"]["phase_id"] == "ROAD.3"


# â”€â”€ 17. deterministic sorting within a bucket â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_deterministic_sorting_within_bucket():
    phases = [
        _phase(phase_id="A.10", track="A", risk_level="low", automation_level="LOCAL_0_OBSERVE"),
        _phase(phase_id="A.2", track="A", risk_level="low", automation_level="LOCAL_0_OBSERVE"),
        _phase(phase_id="ROAD.3", track="ROAD", risk_level="low", automation_level="LOCAL_0_OBSERVE"),
        _phase(phase_id="AUTO.1a", track="AUTO", risk_level="medium", automation_level="LOCAL_0_OBSERVE"),
        _phase(phase_id="ROAD.1", track="ROAD", risk_level="low", automation_level="LOCAL_1_PREPARE"),
    ]
    pick = pick_phase_candidates(_registry(phases=phases))
    ids = [p["phase_id"] for p in pick["buckets"]["safe_to_prepare"]]
    # risk (low<medium), then automation (LOCAL_0<LOCAL_1), then track (ROAD<AUTO<MODEL<...<A), then natural id.
    assert ids == ["ROAD.3", "A.2", "A.10", "ROAD.1", "AUTO.1a"]


def test_report_bytes_are_deterministic(tmp_path):
    reg = _write_registry(tmp_path, _registry(phases=[
        _phase(phase_id="ROAD.1", status="active"),
        _phase(phase_id="ROAD.2"),
        _phase(phase_id="AUTO.2a", track="AUTO"),
    ]))

    def run(name: str) -> str:
        res = script.run_create_phase_picker_report(
            registry=str(reg),
            output_root=str(tmp_path / name),
            report_id="fixed",
            created_at="2026-06-18T12:00:00+00:00",
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


# â”€â”€ 18. Markdown contains all sections and boundaries â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_markdown_contains_all_sections():
    report = _report(
        _registry(phases=[
            _phase(phase_id="ROAD.2"),
            _phase(phase_id="AUTO.9", track="AUTO", status="complete"),
            _phase(phase_id="MODEL.9", track="MODEL", status="parked"),
            _phase(phase_id="GOV.1", track="GOV", merge_allowed=True),
        ]),
        report_id="r",
        created_at="t",
    )
    md = render_phase_picker_markdown(report)
    assert "# Phase Picker / Night Candidate Report" in md
    low = md.lower()
    for section in (
        "## summary",
        "## top recommendation",
        "## safe to prepare",
        "## sandbox required",
        "## human approval required",
        "## blocked",
        "## deferred or parked",
        "## complete or history",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    low = render_phase_picker_markdown(_report(_registry(), report_id="r", created_at="t")).lower()
    assert "does not execute phases" in low
    assert "does not run validation or benchmarks" in low
    assert "does not call models" in low
    assert "does not apply patches" in low
    assert "does not push, merge" in low
    assert "only classifies phase metadata" in low
    # remote-host / chat / automation are named in the boundary line
    assert "github" in low and "telegram" in low and "n8n" in low


def test_markdown_shows_top_recommendation():
    md = render_phase_picker_markdown(_report(_registry(), report_id="r", created_at="t"))
    assert "ROAD.2" in md


# â”€â”€ 19. CLI writes JSON + Markdown / core writer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _write_registry(tmp_path: Path, data: dict, name: str = "phase_registry.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_cli_writes_json_and_markdown(tmp_path):
    reg = _write_registry(tmp_path, _registry())
    out = tmp_path / "out"
    res = script.run_create_phase_picker_report(
        registry=str(reg), output_root=str(out), report_id="cli", created_at="2026-06-18T00:00:00+00:00"
    )
    assert res["ok"] is True
    assert res["registry_valid"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "phase_picker_report.json"
    assert mp.name == "phase_picker_report.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["registry_valid"] is True
    assert data["report_id"] == "cli"
    assert data["registry_path"] == str(reg)


def test_cli_main_smoke(tmp_path):
    reg = _write_registry(tmp_path, _registry())
    out = tmp_path / "out"
    code = script.main(
        ["--registry", str(reg), "--output-root", str(out), "--report-id", "smoke", "--created-at", "2026-06-18T00:00:00+00:00"]
    )
    assert code == 0
    assert (out / "phase_picker_report.json").is_file()
    assert (out / "phase_picker_report.md").is_file()


def test_write_phase_picker_report_core(tmp_path):
    out = tmp_path / "core_out"
    res = write_phase_picker_report(
        _registry(), str(out), report_id="cr", created_at="2026-06-18T00:00:00+00:00", registry_path="reg.json"
    )
    assert res["ok"] is True
    assert Path(res["json_path"]).is_file()
    assert Path(res["md_path"]).is_file()
    assert res["report"]["report_id"] == "cr"


# â”€â”€ 20. CLI exits nonzero on invalid registry unless allow flag â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_cli_exits_nonzero_on_invalid_registry(tmp_path):
    reg = _write_registry(tmp_path, _registry(phases=[_phase(merge_allowed=True)]))
    out = tmp_path / "out"
    code = script.main(["--registry", str(reg), "--output-root", str(out), "--report-id", "x", "--created-at", "t"])
    assert code != 0
    assert (out / "phase_picker_report.json").is_file()


def test_cli_allow_invalid_registry_report_returns_zero(tmp_path):
    reg = _write_registry(tmp_path, _registry(phases=[_phase(merge_allowed=True)]))
    out = tmp_path / "out"
    code = script.main(
        ["--registry", str(reg), "--output-root", str(out), "--report-id", "x", "--created-at", "t", "--allow-invalid-registry-report"]
    )
    assert code == 0
    assert (out / "phase_picker_report.json").is_file()


def test_cli_missing_registry_is_invalid(tmp_path):
    out = tmp_path / "out"
    code = script.main(
        ["--registry", str(tmp_path / "nope.json"), "--output-root", str(out), "--report-id", "x", "--created-at", "t"]
    )
    assert code != 0
    data = json.loads((out / "phase_picker_report.json").read_text(encoding="utf-8"))
    assert data["registry_valid"] is False
    assert data["errors"]


def test_cli_json_flag_prints_report(tmp_path, capsys):
    reg = _write_registry(tmp_path, _registry())
    out = tmp_path / "out"
    code = script.main(
        ["--registry", str(reg), "--output-root", str(out), "--report-id", "j", "--created-at", "t", "--json"]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "j"
    assert printed["report_kind"] == "phase_picker_report"


# â”€â”€ 21. seed registry produces expected buckets â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_SEED_PATH = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"


def test_seed_registry_file_exists():
    assert _SEED_PATH.is_file()


def test_seed_registry_produces_expected_buckets():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t", registry_path=str(_SEED_PATH))
    assert report["registry_valid"] is True
    assert report["bucket_counts"] == {
        "safe_to_prepare": 3,
        "sandbox_required": 1,
        "human_approval_required": 0,
        "blocked": 1,
        "deferred_or_parked": 0,
        "complete_or_history": 219,
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
    assert report["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"


def test_seed_identity_confirmation_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1D.2B"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1D.2A"]
    assert "INDEX.1D.2B" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "INDEX.1D.2B" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_honest_completion_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1D.2C"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1D.2B"]
    assert "INDEX.1D.2C" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "INDEX.1D.2C" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_traversal_budget_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1D.3"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1D.2C"]
    assert "INDEX.1D.3" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "INDEX.1D.3" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_delta_preflight_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1E.0"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1D.3"]
    assert "INDEX.1E.0" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "INDEX.1E.0" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_shadow_delta_dispatch_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1E.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1E.0"]
    assert "INDEX.1E.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "INDEX.1E.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_context_selection_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.SELECT.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == []
    assert "CTX.SELECT.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "CTX.SELECT.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_context_search_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.SEARCH.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["CTX.SELECT.1"]
    assert "CTX.SEARCH.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "CTX.SEARCH.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_context_read_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.READ.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["CTX.SELECT.1", "CTX.SEARCH.1"]
    assert "CTX.READ.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "CTX.READ.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_context_patch_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.PATCH.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == [
        "CTX.SELECT.1",
        "CTX.SEARCH.1",
        "CTX.READ.1",
    ]
    assert "CTX.PATCH.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "CTX.PATCH.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_context_apply_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.APPLY.0"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == [
        "CTX.SELECT.1",
        "CTX.SEARCH.1",
        "CTX.READ.1",
        "CTX.PATCH.1",
    ]
    assert "CTX.APPLY.0" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "CTX.APPLY.0" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_content_acquisition_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["ACQUIRE.3"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["ACQUIRE.2"]
    assert "ACQUIRE.3" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "ACQUIRE.3" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_evidence_verification_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["EVIDENCE.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["ACQUIRE.3"]
    assert "EVIDENCE.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "EVIDENCE.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_evidence_set_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["EVIDENCE.2"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["EVIDENCE.1"]
    assert "EVIDENCE.2" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "EVIDENCE.2" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_claim_assessment_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CLAIM.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["EVIDENCE.2"]
    assert "CLAIM.1" in {item["phase_id"] for item in report["complete_or_history"]}
    assert "CLAIM.1" not in {item["phase_id"] for item in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_structured_synthesis_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["SYNTHESIS.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["CLAIM.1"]
    assert "SYNTHESIS.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "SYNTHESIS.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_post_run_reconciliation_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    # The execution branch, not the epistemic branch that shipped just before it.
    assert phase["prerequisites"] == ["CTX.APPLY.0"]
    assert "CHECK.1" in {item["phase_id"] for item in report["complete_or_history"]}
    assert "CHECK.1" not in {item["phase_id"] for item in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_goal_fidelity_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.2"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    # The first phase that genuinely joins the execution and epistemic branches.
    assert phase["prerequisites"] == ["CHECK.1", "CLAIM.1"]
    assert "CHECK.2" in {item["phase_id"] for item in report["complete_or_history"]}
    assert "CHECK.2" not in {item["phase_id"] for item in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_shadow_post_run_wiring_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.LIVE.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    # The live wiring consumes the objective checker only; CHECK.2 stays out.
    assert phase["prerequisites"] == ["CHECK.1"]
    assert "CHECK.LIVE.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "CHECK.LIVE.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_independent_worker_declaration_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.LIVE.1B"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["CHECK.LIVE.1"]
    assert "CHECK.LIVE.1B" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "CHECK.LIVE.1B" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_native_worker_declaration_qualification_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "WORKER"
    assert phase["prerequisites"] == ["CHECK.LIVE.1B"]
    assert "WORKER.DECL.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "WORKER.DECL.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_strict_patch_response_envelope_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "WORKER"
    assert phase["prerequisites"] == ["WORKER.DECL.1"]
    assert "WORKER.DECL.2A" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "WORKER.DECL.2A" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_strict_envelope_emission_experiment_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A.1"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "WORKER"
    assert phase["prerequisites"] == ["WORKER.DECL.2A"]
    assert "WORKER.DECL.2A.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "WORKER.DECL.2A.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"




def test_seed_live_strict_envelope_dogfood_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A.2"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "WORKER"
    assert phase["prerequisites"] == ["WORKER.DECL.2A.1"]
    assert "WORKER.DECL.2A.2" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "WORKER.DECL.2A.2" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["safe_to_prepare"] == 3
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_model_call_phase_is_never_recommended_as_safe_to_prepare():
    """A phase that spends provider calls can never land in the safe bucket.

    ``_is_safe`` requires ``model_calls_allowed`` false and a preparable budget
    tier, so the one phase declaring a model call stays out of the night queue
    on two independent counts, not merely because it is already complete.
    """
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = dict(by_id["WORKER.DECL.2A.2"])
    assert phase["model_calls_allowed"] is True

    # Re-open the completed phase; it must still not be recommended.
    phase["status"] = "proposed"
    others = [p for p in data["phases"] if p["phase_id"] != "WORKER.DECL.2A.2"]
    reopened = {**data, "phases": others + [phase]}
    report = _report(reopened, report_id="r", created_at="t")

    assert "WORKER.DECL.2A.2" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_seed_safe_candidates_sorted_deterministically():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    ids = [p["phase_id"] for p in report["safe_to_prepare"]]
    # DOGFOOD.1B stays ahead of its dependent VERIFY.TEST.1 and MIRROR.13.
    assert ids == ["DOGFOOD.1B", "VERIFY.TEST.1", "MIRROR.13"]


def test_seed_shipped_phases_are_complete_and_not_recommended():
    # Shipped phases must read as complete and must never be recommended as work to
    # prepare. ROAD.3 shipped after the whole MODEL track; the AUTO.2 contract track
    # shipped before that.
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    statuses = {p["phase_id"]: p["status"] for p in data["phases"]}
    shipped = ["ROAD.1", "ROAD.2", "ROAD.3", "ROAD.4", "AUTO.2a", "AUTO.2b", "AUTO.2c", "MODEL.1", "MODEL.2", "MODEL.3", "MODEL.N1", "MODEL.N2", "MODEL.N3", "MODEL.N4", "MODEL.N5", "MODEL.N6", "MODEL.N7", "MODEL.CLOSE", "EVAL.1", "EVAL.2", "EVAL.3", "EVAL.N1", "EVAL.N2", "EVAL.N3", "EVAL.N4", "EVAL.N5", "EVAL.N6", "EVAL.N7", "EVAL.CLOSE", "HUMAN.N1", "HUMAN.N2", "HUMAN.N3", "HUMAN.N4", "HUMAN.CLOSE", "ADOPT.MODEL.1", "ADOPT.MODEL.2", "ADOPT.MODEL.CLOSE", "CMD.1", "CMD.2", "CMD.3", "CMD.4", "CMD.N1", "CMD.N2", "CMD.N3", "CMD.N4", "CMD.N5", "CMD.N6", "CMD.CLOSE", "HARDEN.N1", "HARDEN.N2", "HARDEN.N3", "HARDEN.N4", "HARDEN.1", "HARDEN.2", "HARDEN.3", "HARDEN.CLOSE", "HARDEN.PROGRESS.1", "OPS.TEST.1", "OPS.TEST.2", "OPS.TEST.3", "OPS.TEST.CLOSE", "UX.RUN.1", "UX.RUN.2", "UX.RUN.3", "UX.RUN.CLOSE", "UX.LIVE.1", "UX.LIVE.2", "UX.LIVE.3", "UX.LIVE.4", "UX.LIVE.5", "MIRROR.1", "MIRROR.2", "MIRROR.3", "MIRROR.4", "MIRROR.5", "MIRROR.6", "MIRROR.CLOSE", "MIRROR.7", "MIRROR.8", "MIRROR.9", "MIRROR.10", "MIRROR.11", "MIRROR.12", "MIRROR.CLOSE3"]
    for pid in shipped:
        assert statuses[pid] == "complete", pid
    report = _report(data, report_id="r", created_at="t")
    history_ids = {p["phase_id"] for p in report["complete_or_history"]}
    assert set(shipped) <= history_ids
    safe = {p["phase_id"] for p in report["safe_to_prepare"]}
    assert not (set(shipped) & safe)
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


# â”€â”€ purity / constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_pick_does_not_mutate_input():
    data = _registry(phases=[_phase(), _phase(phase_id="AUTO.2a", track="AUTO")])
    snap = copy.deepcopy(data)
    pick_phase_candidates(data)
    summarize_phase_candidates(pick_phase_candidates(data), report_id="r", created_at="t")
    assert data == snap


def test_buckets_constant_matches_spec():
    assert set(BUCKETS) == {
        "safe_to_prepare",
        "sandbox_required",
        "human_approval_required",
        "blocked",
        "deferred_or_parked",
        "complete_or_history",
    }


def test_recommended_next_steps_constant_matches_spec():
    assert set(RECOMMENDED_NEXT_STEPS) == {
        "prepare_worker_assignment",
        "prepare_sandbox_trial_contract",
        "request_human_approval",
        "complete_prerequisites",
        "keep_parked",
        "no_action_complete",
        "blocked_until_metadata_fixed",
    }


def test_guardrail_note_is_report_only():
    assert "report-only" in PHASE_PICKER_GUARDRAIL_NOTE.lower()
    report = _report(_registry(), report_id="r", created_at="t")
    assert report["guardrail_note"] == PHASE_PICKER_GUARDRAIL_NOTE


# â”€â”€ 22. forbidden-token / import guards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_CORE = Path(__file__).parent.parent / "core" / "phase_picker.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_phase_picker_report.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_or_phase_registry():
    allowed_top = {"__future__", "json", "pathlib", "typing", "core"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            if top == "core":
                assert module == "core.phase_registry", (
                    f"ROAD.2 may only import core.phase_registry, got {module!r}"
                )
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
    for bad in ("generate_patch", "apply_patch", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_network_or_external_automation():
    for bad in (
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "telegram",
        "n8n",
        "github",
    ):
        assert bad not in _BOTH, f"Found network/automation token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "launch_worker", "worker_launch(", "spawn_worker"):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"


def test_seed_pre_execution_change_intent_phase_remains_active_for_live_v2():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}["WORKER.DECL.2B"]
    report = _report(data, report_id="r", created_at="t")
    assert phase["status"] == "active"
    assert phase["prerequisites"] == ["WORKER.DECL.2A.2"]
    assert "WORKER.DECL.2B" in {
        item["phase_id"] for item in report["sandbox_required"]
    }
    assert "WORKER.DECL.2B" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["sandbox_required"] == 1
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_candidate_sandbox_validation_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.PATCH.2"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["PATCH.BASIS.LIVE.1"]
    assert "OPS.PATCH.2" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "OPS.PATCH.2" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_typed_patch_basis_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "PATCH.BASIS.LIVE.1"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["WAITER.LIVE.1"]
    assert "PATCH.BASIS.LIVE.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "PATCH.BASIS.LIVE.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_query_symbol_entry_recall_phase_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "RETRIEVE.LIVE.2"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "INDEX"
    assert phase["prerequisites"] == ["RETRIEVE.LIVE.1"]
    assert "RETRIEVE.LIVE.2" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "RETRIEVE.LIVE.2" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_production_query_recall_unification_is_complete_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "RETRIEVE.LIVE.3"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "INDEX"
    assert phase["prerequisites"] == ["RETRIEVE.LIVE.2"]
    assert "RETRIEVE.LIVE.3" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "RETRIEVE.LIVE.3" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_answer_entity_grounding_is_complete_check_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "ANSWER.GROUND.LIVE.1"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "CHECK"
    assert phase["prerequisites"] == ["RETRIEVE.LIVE.3"]
    assert "ANSWER.GROUND.LIVE.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "ANSWER.GROUND.LIVE.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_answer_symbol_grounding_is_complete_check_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "ANSWER.GROUND.LIVE.2"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "CHECK"
    assert phase["prerequisites"] == ["ANSWER.GROUND.LIVE.1"]
    assert "ANSWER.GROUND.LIVE.2" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "ANSWER.GROUND.LIVE.2" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_bounded_defect_probe_is_complete_ops_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "DEFECT.PROBE.LIVE.1"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "OPS"
    assert phase["prerequisites"] == [
        "WAITER.LIVE.1",
        "CONTROL.SAFETY.LIVE.1",
        "PATCH.BASIS.LIVE.1",
        "OPS.VALIDATE.1",
        "OPS.VALIDATE.2",
        "RETRIEVE.LIVE.1",
        "RETRIEVE.LIVE.2",
        "RETRIEVE.LIVE.3",
        "ANSWER.GROUND.LIVE.1",
    ]
    assert "DEFECT.PROBE.LIVE.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "DEFECT.PROBE.LIVE.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_bounded_targeted_validation_is_complete_ops_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "OPS.VALIDATE.3"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "OPS"
    assert phase["prerequisites"] == ["DEFECT.PROBE.LIVE.1"]
    assert "OPS.VALIDATE.3" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "OPS.VALIDATE.3" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_immutable_candidate_defect_closure_is_complete_ops_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "DEFECT.PROBE.LIVE.2"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "OPS"
    assert phase["prerequisites"] == ["OPS.VALIDATE.3"]
    assert "DEFECT.PROBE.LIVE.2" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "DEFECT.PROBE.LIVE.2" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_existing_check_oracle_role_is_complete_ops_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "VALIDATE.ORACLE.LIVE.1"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "OPS"
    assert phase["prerequisites"] == ["DEFECT.PROBE.LIVE.2"]
    assert "VALIDATE.ORACLE.LIVE.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "VALIDATE.ORACLE.LIVE.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_execution_eligibility_policy_is_complete_ops_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "EXEC.POLICY.LIVE.1"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "OPS"
    assert phase["prerequisites"] == ["VALIDATE.ORACLE.LIVE.1"]
    assert "EXEC.POLICY.LIVE.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "EXEC.POLICY.LIVE.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_human_apply_binding_is_complete_ops_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "EXEC.APPROVAL.LIVE.1"
    ]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "OPS"
    assert phase["prerequisites"] == ["EXEC.POLICY.LIVE.1"]
    assert "EXEC.APPROVAL.LIVE.1" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "EXEC.APPROVAL.LIVE.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


def test_seed_repository_specificity_entry_ordering_is_complete_index_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}["RETRIEVE.LIVE.4"]
    report = _report(data, report_id="r", created_at="t")

    assert phase["status"] == "complete"
    assert phase["track"] == "INDEX"
    assert phase["prerequisites"] == ["ANSWER.GROUND.LIVE.2"]
    assert "RETRIEVE.LIVE.4" in {
        item["phase_id"] for item in report["complete_or_history"]
    }
    assert "RETRIEVE.LIVE.4" not in {
        item["phase_id"] for item in report["safe_to_prepare"]
    }
    assert report["bucket_counts"]["complete_or_history"] == 219


# PATCH.SCOPE.EXPAND.1 bookkeeping boundary.
def test_seed_structural_scope_expansion_proposal_is_complete_control_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "PATCH.SCOPE.EXPAND.1"]
    report = _report(data, report_id="r", created_at="t")
    assert phase["track"] == "CONTROL"
    assert phase["status"] == "complete"
    assert phase["model_calls_allowed"] is False
    assert "PATCH.SCOPE.EXPAND.1" in {
        item["phase_id"] for item in report["complete_or_history"]}
    assert "PATCH.SCOPE.EXPAND.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]}
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.SCOPE.EXPAND.1 bookkeeping boundary.


# PATCH.SCOPE.RECHECK.1 bookkeeping boundary.
def test_seed_scope_discovered_semantic_recheck_is_complete_control_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "PATCH.SCOPE.RECHECK.1"]
    report = _report(data, report_id="r", created_at="t")
    assert phase["track"] == "CONTROL"
    assert phase["status"] == "complete"
    assert phase["model_calls_allowed"] is False
    assert "PATCH.SCOPE.RECHECK.1" in {
        item["phase_id"] for item in report["complete_or_history"]}
    assert "PATCH.SCOPE.RECHECK.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]}
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.SCOPE.RECHECK.1 bookkeeping boundary.


# PATCH.SCOPE.REFRESH.1 bookkeeping boundary.
def test_seed_semantic_scope_refresh_is_complete_control_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "PATCH.SCOPE.REFRESH.1"]
    report = _report(data, report_id="r", created_at="t")
    assert phase["track"] == "CONTROL"
    assert phase["status"] == "complete"
    assert phase["model_calls_allowed"] is False
    assert "PATCH.SCOPE.REFRESH.1" in {
        item["phase_id"] for item in report["complete_or_history"]}
    assert "PATCH.SCOPE.REFRESH.1" not in {
        item["phase_id"] for item in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.SCOPE.REFRESH.1 bookkeeping boundary.


# PATCH.SCOPE.APPROVE.1 bookkeeping boundary.
def test_scope_approval_is_complete_control_history():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.SCOPE.APPROVE.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.SCOPE.APPROVE.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.SCOPE.APPROVE.1 bookkeeping boundary.


# PATCH.SCOPE.PLAN.1 bookkeeping boundary.
def test_plan_phase_is_complete_history_not_auto_selected():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.SCOPE.PLAN.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.SCOPE.PLAN.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.SCOPE.PLAN.1 bookkeeping boundary.


# PATCH.SCOPE.ADMIT.1 bookkeeping boundary.
def test_admit_phase_is_history_and_does_not_enable_auto_authoring():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.SCOPE.ADMIT.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.SCOPE.ADMIT.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.SCOPE.ADMIT.1 bookkeeping boundary.


# PATCH.AUTHOR.STRUCTURAL.1 bookkeeping boundary.
def test_structural_author_is_history_without_automatic_author_call():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.AUTHOR.STRUCTURAL.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.AUTHOR.STRUCTURAL.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.AUTHOR.STRUCTURAL.1 bookkeeping boundary.


# PATCH.CANDIDATE.MATERIALIZE.1 bookkeeping boundary.
def test_structural_candidate_materialization_is_history_without_automatic_execution():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.CANDIDATE.MATERIALIZE.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.CANDIDATE.MATERIALIZE.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.CANDIDATE.MATERIALIZE.1 bookkeeping boundary.


# PATCH.CANDIDATE.VALIDATE.1A bookkeeping boundary.
def test_structural_candidate_compile_validation_is_history_without_automatic_execution():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.CANDIDATE.VALIDATE.1A" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.CANDIDATE.VALIDATE.1A" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.CANDIDATE.VALIDATE.1A bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.SPEC.1 bookkeeping boundary.
def test_behavioral_specification_is_history_without_automatic_execution():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.CANDIDATE.BEHAVIOR.SPEC.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.CANDIDATE.BEHAVIOR.SPEC.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.CANDIDATE.BEHAVIOR.SPEC.1 bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1 bookkeeping boundary.
def test_behavioral_execution_plan_is_history_without_execution_authority():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1 bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.REFLECT.1 bookkeeping boundary.
def test_read_only_reflection_is_history_without_behavioral_execution_admission():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.CANDIDATE.BEHAVIOR.REFLECT.1 bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1 bookkeeping boundary.
def test_behavioral_execution_admission_is_history_without_automatic_runtime_authority():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1 bookkeeping boundary.


# PREFLIGHT.RUNTIME.1 bookkeeping boundary.
def test_runtime_diagnostic_policy_is_history_without_a_runtime_executor():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    assert "PREFLIGHT.RUNTIME.1" in {p["phase_id"] for p in report["complete_or_history"]}
    assert "PREFLIGHT.RUNTIME.1" not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PREFLIGHT.RUNTIME.1 bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1 bookkeeping boundary.
def test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {p["phase_id"]: p for p in data["phases"]}["PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1"]
    report = _report(data, report_id="r", created_at="t")
    assert phase["track"] == "CONTROL" and phase["status"] == "active"
    assert phase["risk_level"] == "blocked" and phase["budget_tier"] == "local_only"
    blocked = [p for p in report["blocked"] if p["phase_id"] == phase["phase_id"]]
    assert len(blocked) == 1
    assert "risk_level is blocked" in blocked[0]["reasons"]
    assert phase["phase_id"] not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert phase["phase_id"] not in {p["phase_id"] for p in report["complete_or_history"]}
    assert report["bucket_counts"]["blocked"] == 1
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1 bookkeeping boundary.


# RUNTIME.SANDBOX.1 bookkeeping boundary.
def test_verified_runtime_sandbox_is_history_and_executor_stays_blocked():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    phase = {p["phase_id"]: p for p in data["phases"]}["RUNTIME.SANDBOX.1"]
    report = _report(data, report_id="r", created_at="t")
    assert report["registry_valid"] is True
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["risk_level"] == "medium" and phase["budget_tier"] == "local_only"
    assert phase["phase_id"] in {p["phase_id"] for p in report["complete_or_history"]}
    assert phase["phase_id"] not in {p["phase_id"] for p in report["safe_to_prepare"]}
    assert phase["phase_id"] not in {p["phase_id"] for p in report["sandbox_required"]}
    assert {p["phase_id"] for p in report["blocked"]} == {"PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1"}
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
# End RUNTIME.SANDBOX.1 bookkeeping boundary.
