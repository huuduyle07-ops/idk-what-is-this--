"""Tests for ROAD.2 — Phase Picker / Night Candidate Report (report-only).

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


# ── synthetic registry builders ───────────────────────────────────────────────

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


# ── 1. valid registry produces a report ────────────────────────────────────────

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


# ── 2. invalid registry produces no candidates ─────────────────────────────────

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


# ── 3. complete phases → complete_or_history ───────────────────────────────────

def test_complete_phase_goes_to_complete_or_history():
    bucket, item = _pick_one(_phase(status="complete"))
    assert bucket == "complete_or_history"
    assert item["recommended_next_step"] == "no_action_complete"


# ── 4. parked / deferred → deferred_or_parked ──────────────────────────────────

def test_parked_phase_goes_to_deferred_or_parked():
    bucket, item = _pick_one(_phase(status="parked"))
    assert bucket == "deferred_or_parked"
    assert item["recommended_next_step"] == "keep_parked"


def test_deferred_phase_goes_to_deferred_or_parked():
    assert _bucket_of(_phase(status="deferred")) == "deferred_or_parked"


# ── 5-6. blocked budget / risk → blocked ───────────────────────────────────────

def test_blocked_budget_goes_to_blocked():
    bucket, item = _pick_one(_phase(budget_tier="blocked"))
    assert bucket == "blocked"
    assert item["recommended_next_step"] == "blocked_until_metadata_fixed"


def test_blocked_risk_goes_to_blocked():
    assert _bucket_of(_phase(risk_level="blocked")) == "blocked"


# ── 7. merge_allowed=true → blocked ────────────────────────────────────────────

def test_merge_allowed_goes_to_blocked():
    bucket, item = _pick_one(_phase(merge_allowed=True))
    assert bucket == "blocked"
    assert any("merge_allowed" in r for r in item["reasons"])


# ── 8. human_approval_required=false → blocked (proposed/active) ───────────────

def test_human_approval_false_goes_to_blocked_proposed():
    assert _bucket_of(_phase(status="proposed", human_approval_required=False)) == "blocked"


def test_human_approval_false_goes_to_blocked_active():
    assert _bucket_of(_phase(status="active", human_approval_required=False)) == "blocked"


# ── 9. writes_real_repo=true → blocked (proposed/active) ───────────────────────

def test_writes_real_repo_goes_to_blocked_proposed():
    assert _bucket_of(_phase(status="proposed", writes_real_repo=True)) == "blocked"


def test_writes_real_repo_goes_to_blocked_active():
    assert _bucket_of(_phase(status="active", writes_real_repo=True)) == "blocked"


# ── missing allowed_files / validation → blocked ───────────────────────────────

def test_missing_allowed_files_goes_to_blocked():
    assert _bucket_of(_phase(allowed_files=[])) == "blocked"


def test_missing_validation_goes_to_blocked():
    assert _bucket_of(_phase(validation=[])) == "blocked"


# ── 10. requires_sandbox=true → sandbox_required ───────────────────────────────

def test_requires_sandbox_goes_to_sandbox_required():
    bucket, item = _pick_one(_phase(requires_sandbox=True))
    assert bucket == "sandbox_required"
    assert item["recommended_next_step"] == "prepare_sandbox_trial_contract"


# ── 11. SANDBOX_2_DRAFT_PATCH / patch mention / patch path → sandbox_required ───

def test_sandbox_automation_goes_to_sandbox_required():
    assert _bucket_of(_phase(automation_level="SANDBOX_2_DRAFT_PATCH")) == "sandbox_required"


def test_patch_candidate_mention_goes_to_sandbox_required():
    phase = _phase(summary="Evaluate the patch candidate quality offline before review.")
    assert _bucket_of(phase) == "sandbox_required"


def test_patch_path_in_allowed_files_goes_to_sandbox_required():
    phase = _phase(allowed_files=["core/patch_safety.py", "tests/test_patch_safety.py"])
    assert _bucket_of(phase) == "sandbox_required"


# ── 12. REMOTE_3_DRAFT_PR → human_approval_required ────────────────────────────

def test_remote_pr_goes_to_human_approval_required():
    bucket, item = _pick_one(_phase(automation_level="REMOTE_3_DRAFT_PR"))
    assert bucket == "human_approval_required"
    assert item["recommended_next_step"] == "request_human_approval"


# ── 13. strong_model_requires_approval → human_approval_required ───────────────

def test_strong_model_budget_goes_to_human_approval_required():
    assert _bucket_of(_phase(budget_tier="strong_model_requires_approval")) == "human_approval_required"


def test_model_calls_allowed_goes_to_human_approval_required():
    # model_calls_allowed=true is valid only with the approval budget tier.
    phase = _phase(model_calls_allowed=True, budget_tier="strong_model_requires_approval")
    assert _bucket_of(phase) == "human_approval_required"


# ── 14. network_allowed=true → human_approval_required or blocked ──────────────

def test_network_allowed_goes_to_human_or_blocked():
    assert _bucket_of(_phase(network_allowed=True)) in {"blocked", "human_approval_required"}


# ── 15. local observe/prepare low-risk → safe_to_prepare ───────────────────────

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


# ── 16. top recommendation prefers a safe local ROAD phase ─────────────────────

def test_top_recommendation_prefers_safe_local_road_phase():
    phases = [
        _phase(phase_id="AUTO.1a", track="AUTO", risk_level="low", automation_level="LOCAL_0_OBSERVE"),
        _phase(phase_id="MODEL.1", track="MODEL", risk_level="medium", automation_level="LOCAL_0_OBSERVE"),
        _phase(phase_id="ROAD.3", track="ROAD", risk_level="low", automation_level="LOCAL_0_OBSERVE"),
    ]
    pick = pick_phase_candidates(_registry(phases=phases))
    assert {p["phase_id"] for p in pick["buckets"]["safe_to_prepare"]} == {"AUTO.1a", "MODEL.1", "ROAD.3"}
    assert pick["top_recommendation"]["phase_id"] == "ROAD.3"


# ── 17. deterministic sorting within a bucket ──────────────────────────────────

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


# ── 18. Markdown contains all sections and boundaries ──────────────────────────

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


# ── 19. CLI writes JSON + Markdown / core writer ───────────────────────────────

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


# ── 20. CLI exits nonzero on invalid registry unless allow flag ────────────────

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


# ── 21. seed registry produces expected buckets ────────────────────────────────

_SEED_PATH = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"


def test_seed_registry_file_exists():
    assert _SEED_PATH.is_file()


def test_seed_registry_produces_expected_buckets():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t", registry_path=str(_SEED_PATH))
    assert report["registry_valid"] is True
    assert report["bucket_counts"] == {
        "safe_to_prepare": 1,
        "sandbox_required": 0,
        "human_approval_required": 0,
        "blocked": 0,
        "deferred_or_parked": 0,
        "complete_or_history": 39,
    }
    assert report["top_recommendation"]["phase_id"] == "MIRROR.CLOSE"
    assert report["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"


def test_seed_safe_candidates_sorted_deterministically():
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    report = _report(data, report_id="r", created_at="t")
    ids = [p["phase_id"] for p in report["safe_to_prepare"]]
    # Completed phases drop out; MIRROR.CLOSE remains the next safe report-only candidate.
    assert ids == ["MIRROR.CLOSE"]


def test_seed_shipped_phases_are_complete_and_not_recommended():
    # Shipped phases must read as complete and must never be recommended as work to
    # prepare. ROAD.3 shipped after the whole MODEL track; the AUTO.2 contract track
    # shipped before that.
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    statuses = {p["phase_id"]: p["status"] for p in data["phases"]}
    shipped = ["ROAD.1", "ROAD.2", "ROAD.3", "ROAD.4", "AUTO.2a", "AUTO.2b", "AUTO.2c", "MODEL.1", "MODEL.2", "MODEL.3", "EVAL.1", "EVAL.2", "EVAL.3", "CMD.1", "CMD.2", "CMD.3", "CMD.4", "HARDEN.1", "HARDEN.2", "HARDEN.3", "HARDEN.CLOSE", "MIRROR.1", "MIRROR.2", "MIRROR.3", "MIRROR.4", "MIRROR.5", "MIRROR.6"]
    for pid in shipped:
        assert statuses[pid] == "complete", pid
    report = _report(data, report_id="r", created_at="t")
    history_ids = {p["phase_id"] for p in report["complete_or_history"]}
    assert set(shipped) <= history_ids
    safe = {p["phase_id"] for p in report["safe_to_prepare"]}
    assert not (set(shipped) & safe)
    assert report["top_recommendation"]["phase_id"] == "MIRROR.CLOSE"


# ── purity / constants ─────────────────────────────────────────────────────────

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


# ── 22. forbidden-token / import guards ────────────────────────────────────────

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
