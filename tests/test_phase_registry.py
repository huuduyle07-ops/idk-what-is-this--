"""Tests for ROAD.1 â€” Machine-Readable Phase Registry (report-only).

ROAD.1 defines, validates, and summarizes roadmap phase metadata. It does not
choose work, execute phases, run validation or a benchmark check, call models,
apply patches, write to the real repo, push, merge, open PRs, or contact a remote
git host / chat service / external automation. Validation commands are stored as
text only; ROAD.1 never runs them.

Covers the prescribed cases:
1.  valid registry passes.
2.  missing root fields fails.
3.  missing phase fields fails.
4.  duplicate phase IDs fail.
5.  invalid enum values fail.
6.  AUTO_4_AUTO_MERGE rejected.
7.  merge_allowed=true rejected.
8.  human_approval_required=false rejected for proposed/active phases.
9.  model_calls_allowed=true rejected unless budget tier requires approval.
10. writes_real_repo=true rejected for proposed/active phases.
11. empty allowed_files rejected for proposed implementation phase.
12. empty validation rejected for proposed implementation phase.
13. forbidden_files must include .env, .git, .agent/private.
14. summary counts by track/status/automation level are correct.
15. Markdown contains summary / table / boundaries.
16. CLI writes JSON + Markdown.
17. CLI returns nonzero for invalid registry.
18. deterministic report output with fixed report_id/created_at.
19. seed registry validates.
20. source contains no forbidden execution/network/model/patch tokens.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.phase_registry import (
    AUTOMATION_LEVELS,
    BUDGET_TIERS,
    PHASE_ID_PREFIXES,
    PHASE_REGISTRY_GUARDRAIL_NOTE,
    REPORT_KIND,
    REQUIRED_PHASE_FIELDS,
    REQUIRED_ROOT_FIELDS,
    RISK_LEVELS,
    STATUSES,
    load_phase_registry,
    render_phase_registry_markdown,
    summarize_phase_registry,
    validate_phase_registry,
    write_phase_registry_report,
)
import scripts.validate_phase_registry as script


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


def _errors(data) -> list[str]:
    return validate_phase_registry(data)["errors"]


# â”€â”€ 1. valid registry passes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_valid_registry_passes():
    result = validate_phase_registry(_registry())
    assert result["is_valid"] is True
    assert result["errors"] == []


def test_valid_registry_with_multiple_phases_passes():
    phases = [_phase(phase_id="ROAD.1", track="ROAD", status="active"), _phase(phase_id="AUTO.2a", track="AUTO")]
    result = validate_phase_registry(_registry(phases=phases))
    assert result["is_valid"] is True
    assert result["errors"] == []


# â”€â”€ 2. missing root fields fails â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_missing_phases_root_field_fails():
    data = _registry()
    del data["phases"]
    result = validate_phase_registry(data)
    assert result["is_valid"] is False
    assert any("phases" in e for e in result["errors"])


def test_missing_schema_version_root_field_fails():
    data = _registry()
    del data["schema_version"]
    assert any("schema_version" in e for e in _errors(data))


def test_missing_updated_at_root_field_fails():
    data = _registry()
    del data["updated_at"]
    assert any("updated_at" in e for e in _errors(data))


def test_non_dict_root_fails():
    result = validate_phase_registry(["not", "a", "dict"])
    assert result["is_valid"] is False
    assert result["errors"]


# â”€â”€ 3. missing phase fields fails â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_missing_phase_field_fails():
    phase = _phase()
    del phase["summary"]
    result = validate_phase_registry(_registry(phases=[phase]))
    assert result["is_valid"] is False
    assert any("summary" in e and "missing" in e for e in result["errors"])


def test_each_required_phase_field_is_enforced():
    for field in REQUIRED_PHASE_FIELDS:
        phase = _phase()
        del phase[field]
        errs = _errors(_registry(phases=[phase]))
        assert any(field in e and "missing" in e for e in errs), field


# â”€â”€ 4. duplicate phase IDs fail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_duplicate_phase_ids_fail():
    phases = [_phase(phase_id="ROAD.2"), _phase(phase_id="ROAD.2")]
    result = validate_phase_registry(_registry(phases=phases))
    assert result["is_valid"] is False
    assert any("duplicate" in e.lower() and "ROAD.2" in e for e in result["errors"])


# â”€â”€ 5. invalid enum values fail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_invalid_status_fails():
    assert any("status" in e for e in _errors(_registry(phases=[_phase(status="bogus")])))


def test_invalid_automation_level_fails():
    errs = _errors(_registry(phases=[_phase(automation_level="HYPER_9")]))
    assert any("automation_level" in e for e in errs)


def test_invalid_budget_tier_fails():
    assert any("budget_tier" in e for e in _errors(_registry(phases=[_phase(budget_tier="free_money")])))


def test_invalid_risk_level_fails():
    assert any("risk_level" in e for e in _errors(_registry(phases=[_phase(risk_level="spicy")])))


# â”€â”€ 6. AUTO_4_AUTO_MERGE rejected â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_auto_4_auto_merge_rejected():
    errs = _errors(_registry(phases=[_phase(automation_level="AUTO_4_AUTO_MERGE")]))
    assert any("AUTO_4_AUTO_MERGE" in e for e in errs)


# â”€â”€ 7. merge_allowed=true rejected â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_merge_allowed_true_rejected():
    errs = _errors(_registry(phases=[_phase(merge_allowed=True)]))
    assert any("merge_allowed" in e for e in errs)


# â”€â”€ 8. human_approval_required=false rejected for proposed/active â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_human_approval_false_rejected_for_proposed():
    errs = _errors(_registry(phases=[_phase(status="proposed", human_approval_required=False)]))
    assert any("human_approval_required" in e for e in errs)


def test_human_approval_false_rejected_for_active():
    errs = _errors(_registry(phases=[_phase(status="active", human_approval_required=False)]))
    assert any("human_approval_required" in e for e in errs)


def test_human_approval_false_allowed_for_complete():
    errs = _errors(_registry(phases=[_phase(status="complete", human_approval_required=False)]))
    assert not any("human_approval_required" in e for e in errs)


# â”€â”€ 9. model_calls_allowed=true rejected unless budget tier requires approval â”€â”€

def test_model_calls_allowed_rejected_for_local_budget():
    errs = _errors(
        _registry(phases=[_phase(model_calls_allowed=True, budget_tier="local_only")])
    )
    assert any("model_calls_allowed" in e for e in errs)


def test_model_calls_allowed_ok_when_budget_requires_approval():
    errs = _errors(
        _registry(
            phases=[_phase(model_calls_allowed=True, budget_tier="strong_model_requires_approval")]
        )
    )
    assert not any("model_calls_allowed" in e for e in errs)


# â”€â”€ 10. writes_real_repo=true rejected for proposed/active â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_writes_real_repo_rejected_for_proposed():
    errs = _errors(_registry(phases=[_phase(status="proposed", writes_real_repo=True)]))
    assert any("writes_real_repo" in e for e in errs)


def test_writes_real_repo_allowed_for_complete():
    errs = _errors(_registry(phases=[_phase(status="complete", writes_real_repo=True)]))
    assert not any("writes_real_repo" in e for e in errs)


# â”€â”€ 11-12. empty allowed_files / validation rejected for proposed impl phase â”€â”€â”€

def test_empty_allowed_files_rejected_for_proposed():
    errs = _errors(_registry(phases=[_phase(status="proposed", allowed_files=[])]))
    assert any("allowed_files" in e and "empty" in e for e in errs)


def test_empty_validation_rejected_for_proposed():
    errs = _errors(_registry(phases=[_phase(status="proposed", validation=[])]))
    assert any("validation" in e and "empty" in e for e in errs)


def test_empty_allowed_files_allowed_for_parked():
    errs = _errors(_registry(phases=[_phase(status="parked", allowed_files=[], validation=[])]))
    assert not any("allowed_files" in e and "empty" in e for e in errs)
    assert not any(e.startswith("phase ROAD.2 has empty validation") for e in errs)


# â”€â”€ 13. forbidden_files must include .env, .git, .agent/private â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_forbidden_files_must_include_required_entries():
    errs = _errors(_registry(phases=[_phase(forbidden_files=[".env", ".git"])]))
    assert any("forbidden_files" in e and ".agent/private" in e for e in errs)


def test_forbidden_files_missing_env_fails():
    errs = _errors(_registry(phases=[_phase(forbidden_files=[".git", ".agent/private"])]))
    assert any("forbidden_files" in e and ".env" in e for e in errs)


# â”€â”€ extra structural rules â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_non_string_validation_command_rejected():
    errs = _errors(_registry(phases=[_phase(validation=[{"cmd": "python"}])]))
    assert any("validation" in e and "text" in e for e in errs)


def test_invalid_phase_id_prefix_warns_not_errors():
    result = validate_phase_registry(_registry(phases=[_phase(phase_id="ZZZ.9")]))
    # unknown prefix is a warning, not a hard error
    assert any("ZZZ.9" in w for w in result["warnings"])


def test_dangling_prerequisite_warns():
    result = validate_phase_registry(_registry(phases=[_phase(prerequisites=["NOPE.1"])]))
    assert any("NOPE.1" in w for w in result["warnings"])


# â”€â”€ 14. summary counts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _mixed_registry() -> dict:
    return _registry(
        phases=[
            _phase(phase_id="ROAD.1", track="ROAD", status="active", automation_level="LOCAL_0_OBSERVE"),
            _phase(phase_id="ROAD.2", track="ROAD", status="proposed", automation_level="LOCAL_0_OBSERVE"),
            _phase(phase_id="AUTO.2a", track="AUTO", status="proposed", automation_level="LOCAL_1_PREPARE"),
            _phase(phase_id="MODEL.1", track="MODEL", status="proposed", automation_level="LOCAL_1_PREPARE"),
        ]
    )


def test_summary_counts_are_correct():
    report = summarize_phase_registry(_mixed_registry(), report_id="r", created_at="t")
    assert report["phase_count"] == 4
    assert report["counts_by_track"] == {"AUTO": 1, "MODEL": 1, "ROAD": 2}
    assert report["counts_by_status"] == {"active": 1, "proposed": 3}
    assert report["counts_by_automation_level"] == {"LOCAL_0_OBSERVE": 2, "LOCAL_1_PREPARE": 2}


def test_summary_phases_sorted_by_track_then_natural_id():
    report = summarize_phase_registry(_mixed_registry(), report_id="r", created_at="t")
    ids = [p["phase_id"] for p in report["phases"]]
    assert ids == ["AUTO.2a", "MODEL.1", "ROAD.1", "ROAD.2"]


def test_summary_natural_id_ordering_within_track():
    phases = [_phase(phase_id=f"A.{n}", track="A") for n in (2, 18, 1, 21, 10)]
    report = summarize_phase_registry(_registry(phases=phases), report_id="r", created_at="t")
    ids = [p["phase_id"] for p in report["phases"]]
    assert ids == ["A.1", "A.2", "A.10", "A.18", "A.21"]


def test_summary_has_required_report_fields():
    report = summarize_phase_registry(_registry(), report_id="rid", created_at="2026-06-18T00:00:00+00:00", registry_path="docs/roadmap/phase_registry.json")
    for key in (
        "report_id",
        "created_at",
        "schema_version",
        "registry_path",
        "phase_count",
        "counts_by_track",
        "counts_by_status",
        "counts_by_automation_level",
        "errors",
        "warnings",
        "is_valid",
        "phases",
    ):
        assert key in report, key
    assert report["report_id"] == "rid"
    assert report["created_at"] == "2026-06-18T00:00:00+00:00"
    assert report["registry_path"] == "docs/roadmap/phase_registry.json"
    assert report["schema_version"] == "1.0"
    assert report["report_kind"] == REPORT_KIND


def test_summary_reports_invalid_registry():
    report = summarize_phase_registry(_registry(phases=[_phase(merge_allowed=True)]), report_id="r", created_at="t")
    assert report["is_valid"] is False
    assert report["errors"]


# â”€â”€ 15. Markdown sections + boundaries â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_markdown_contains_required_sections():
    report = summarize_phase_registry(_mixed_registry(), report_id="r", created_at="t")
    md = render_phase_registry_markdown(report)
    assert "# Machine-Readable Phase Registry Report" in md
    low = md.lower()
    for section in (
        "## summary",
        "## counts by track",
        "## counts by status",
        "## counts by automation level",
        "## validation result",
        "## errors",
        "## warnings",
        "## boundaries",
    ):
        assert section in low, section
    # phase table header
    assert "| Phase " in md
    assert "ROAD.1" in md and "AUTO.2a" in md


def test_markdown_boundaries_state_no_power():
    report = summarize_phase_registry(_registry(), report_id="r", created_at="t")
    low = render_phase_registry_markdown(report).lower()
    assert "does not execute phases" in low
    assert "does not run validation or benchmarks" in low
    assert "does not call models" in low
    assert "does not apply patches" in low
    assert "does not push, merge" in low
    assert "only validates and summarizes roadmap metadata" in low


def test_markdown_shows_validation_result():
    valid = render_phase_registry_markdown(summarize_phase_registry(_registry(), report_id="r", created_at="t"))
    invalid = render_phase_registry_markdown(
        summarize_phase_registry(_registry(phases=[_phase(merge_allowed=True)]), report_id="r", created_at="t")
    )
    assert "VALID" in valid
    assert "INVALID" in invalid


# â”€â”€ 16-18. CLI behaviour â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _write_registry(tmp_path: Path, data: dict, name: str = "phase_registry.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_cli_writes_json_and_markdown(tmp_path):
    reg = _write_registry(tmp_path, _registry())
    out = tmp_path / "out"
    res = script.run_validate_phase_registry(
        registry=str(reg), output_root=str(out), report_id="cli", created_at="2026-06-18T00:00:00+00:00"
    )
    assert res["ok"] is True
    assert res["is_valid"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "phase_registry_report.json"
    assert mp.name == "phase_registry_report.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["is_valid"] is True
    assert data["report_id"] == "cli"
    assert data["registry_path"] == str(reg)


def test_cli_main_smoke(tmp_path):
    reg = _write_registry(tmp_path, _registry())
    out = tmp_path / "out"
    code = script.main(
        ["--registry", str(reg), "--output-root", str(out), "--report-id", "smoke", "--created-at", "2026-06-18T00:00:00+00:00"]
    )
    assert code == 0
    assert (out / "phase_registry_report.json").is_file()
    assert (out / "phase_registry_report.md").is_file()


def test_cli_returns_nonzero_for_invalid_registry(tmp_path):
    reg = _write_registry(tmp_path, _registry(phases=[_phase(merge_allowed=True)]))
    out = tmp_path / "out"
    code = script.main(["--registry", str(reg), "--output-root", str(out), "--report-id", "x", "--created-at", "t"])
    assert code != 0
    # a report is still written
    assert (out / "phase_registry_report.json").is_file()


def test_cli_allow_invalid_report_returns_zero(tmp_path):
    reg = _write_registry(tmp_path, _registry(phases=[_phase(merge_allowed=True)]))
    out = tmp_path / "out"
    code = script.main(
        ["--registry", str(reg), "--output-root", str(out), "--report-id", "x", "--created-at", "t", "--allow-invalid-report"]
    )
    assert code == 0
    assert (out / "phase_registry_report.json").is_file()


def test_cli_missing_registry_file_is_invalid(tmp_path):
    out = tmp_path / "out"
    code = script.main(
        ["--registry", str(tmp_path / "nope.json"), "--output-root", str(out), "--report-id", "x", "--created-at", "t"]
    )
    assert code != 0
    data = json.loads((out / "phase_registry_report.json").read_text(encoding="utf-8"))
    assert data["is_valid"] is False
    assert data["errors"]


def test_cli_deterministic_report(tmp_path):
    reg = _write_registry(tmp_path, _mixed_registry())

    def run(name: str) -> str:
        res = script.run_validate_phase_registry(
            registry=str(reg),
            output_root=str(tmp_path / name),
            report_id="fixed",
            created_at="2026-06-18T12:00:00+00:00",
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    a = run("a")
    b = run("b")
    assert a == b
    data = json.loads(a)
    assert data["report_id"] == "fixed"
    assert data["created_at"] == "2026-06-18T12:00:00+00:00"


def test_write_phase_registry_report_core(tmp_path):
    out = tmp_path / "core_out"
    res = write_phase_registry_report(
        _registry(), str(out), report_id="cr", created_at="2026-06-18T00:00:00+00:00", registry_path="reg.json"
    )
    assert res["ok"] is True
    assert Path(res["json_path"]).is_file()
    assert Path(res["md_path"]).is_file()
    assert res["report"]["report_id"] == "cr"


# â”€â”€ 19. seed registry validates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_SEED_PATH = Path(__file__).parent.parent / "docs" / "roadmap" / "phase_registry.json"


def test_seed_registry_file_exists():
    assert _SEED_PATH.is_file()


def test_seed_registry_validates():
    data = load_phase_registry(str(_SEED_PATH))
    result = validate_phase_registry(data)
    assert result["is_valid"] is True, result["errors"]
    assert result["errors"] == []
    assert result["warnings"] == []


def test_seed_registry_has_expected_phases():
    data = load_phase_registry(str(_SEED_PATH))
    ids = {p["phase_id"] for p in data["phases"]}
    assert {
        "ROAD.1", "ROAD.2", "ROAD.3", "ROAD.4", "AUTO.2a", "AUTO.2b", "AUTO.2c",
        "MODEL.1", "MODEL.2", "MODEL.3", "MODEL.N1", "MODEL.N2", "MODEL.N3", "MODEL.N4", "MODEL.N5", "MODEL.N6", "MODEL.N7", "MODEL.CLOSE", "EVAL.1", "EVAL.2", "EVAL.3", "EVAL.N1", "EVAL.N2", "EVAL.N3", "EVAL.N4", "EVAL.N5", "EVAL.N6", "EVAL.N7", "EVAL.CLOSE", "HUMAN.N1", "HUMAN.N2", "HUMAN.N3", "HUMAN.N4", "HUMAN.CLOSE", "ADOPT.MODEL.1", "ADOPT.MODEL.2", "ADOPT.MODEL.CLOSE", "CMD.1", "CMD.2", "CMD.3", "CMD.4", "CMD.N1", "CMD.N2", "CMD.N3", "CMD.N4", "CMD.N5", "CMD.N6", "CMD.CLOSE",
        "HARDEN.1", "HARDEN.2", "HARDEN.3", "HARDEN.CLOSE", "HARDEN.N1", "HARDEN.N2", "HARDEN.N3", "HARDEN.N4", "HARDEN.PROGRESS.1", "OPS.TEST.1", "OPS.TEST.2", "OPS.TEST.3", "OPS.TEST.CLOSE", "UX.RUN.1", "UX.RUN.2", "UX.RUN.3", "UX.1", "UX.2", "UX.3", "UX.4", "UX.5", "UX.6", "UX.7", "UX.8", "UX.9", "UX.10", "UX.11",
        "UX.CLOSE", "MIRROR.1", "MIRROR.2", "MIRROR.3", "MIRROR.4", "MIRROR.5", "MIRROR.6", "MIRROR.CLOSE", "MIRROR.7", "MIRROR.8", "MIRROR.9", "MIRROR.10", "MIRROR.11", "MIRROR.12", "MIRROR.CLOSE3", "MIRROR.13",
    } <= ids
    assert {"UX.RUN.CLOSE", "UX.LIVE.1", "UX.LIVE.2", "UX.LIVE.3", "UX.LIVE.4", "UX.LIVE.5", "UX.LIVE.6", "UX.LIVE.7", "UX.LIVE.8", "UX.LIVE.9", "UX.LIVE.10", "UX.LIVE.CLOSE", "DOGFOOD.1A", "DOGFOOD.1B", "VERIFY.TEST.1"} <= ids
    assert {
        "INDEX.1D.1",
        "INDEX.1D.2A",
        "INDEX.1D.2B",
        "INDEX.1D.2C",
        "INDEX.1D.3",
        "INDEX.1E.0",
        "INDEX.1E.1",
        "INDEX.1E.2",
    } <= ids
    assert {
        "CTX.SELECT.1",
        "CTX.SEARCH.1",
        "CTX.READ.1",
        "CTX.PATCH.1",
        "CTX.APPLY.0",
    } <= ids
    assert len(data["phases"]) == 119


def test_seed_registry_is_conservative():
    data = load_phase_registry(str(_SEED_PATH))
    for phase in data["phases"]:
        assert phase["automation_level"] != "AUTO_4_AUTO_MERGE"
        assert phase["merge_allowed"] is False
        assert phase["network_allowed"] is False
        assert phase["model_calls_allowed"] is False
        assert phase["writes_real_repo"] is False
        for required in (".env", ".git", ".agent/private"):
            assert required in phase["forbidden_files"]


def test_seed_registry_summary_counts():
    data = load_phase_registry(str(_SEED_PATH))
    report = summarize_phase_registry(data, report_id="r", created_at="t")
    assert report["counts_by_track"] == {
        "ADOPT": 3,
        "AUTO": 3,
        "CMD": 11,
        "CTX": 5,
        "DOGFOOD": 2,
        "VERIFY": 1,
        "EVAL": 11,
        "HARDEN": 9,
        "HUMAN": 5,
        "INDEX": 8,
        "MIRROR": 15,
        "MODEL": 11,
        "OPS": 4,
        "ROAD": 4,
        "UX": 27,
    }


def test_identity_confirmation_phase_is_complete_after_identity_primitive():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1D.2B"]

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1D.2A"]


def test_honest_completion_phase_is_complete_after_identity_confirmation():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1D.2C"]

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1D.2B"]


def test_traversal_budget_phase_is_complete_after_honest_completion():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1D.3"]

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1D.2C"]


def test_delta_preflight_phase_is_complete_with_dispatch_block_preserved():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1E.0"]

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1D.3"]
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["risk_level"] == "medium"
    assert phase["writes_real_repo"] is False
    assert any(
        "historical readiness decision remains blocked"
        in note
        for note in phase["notes"]
    )


def test_shadow_delta_dispatch_phase_is_complete_after_preflight():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INDEX.1E.1"]

    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INDEX.1E.0"]
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["risk_level"] == "high"
    assert phase["writes_real_repo"] is False
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["expected_artifacts"] == [
        ".agent/audits/index-1e-1-shadow-delta-dispatch.json",
        ".agent/audits/index-1e-1-shadow-delta-dispatch.md",
        "docs/audits/2026-07-29-index-1e-1-shadow-delta-dispatch.md",
    ]


def test_context_selection_phase_is_complete_and_index_independent():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.SELECT.1"]

    assert phase["title"] == "Bounded Candidate Discovery & File Actionability Contract"
    assert phase["track"] == "CTX"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == []
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    assert phase["expected_artifacts"] == [
        ".agent/context_selection/candidate_selection_contract.json",
        ".agent/context_selection/candidate_selection_contract.md",
        "docs/designs/2026-08-01-direct-file-candidate-selection.md",
    ]
    assert {
        "config.py",
        "core/repository_inventory.py",
        "core/repository_path_policy.py",
        "core/source_file_policy.py",
    } <= set(phase["allowed_files"])
    assert {"database/", "graph/", "patching/", "core/indexer.py"} <= set(
        phase["forbidden_files"]
    )
    assert "python -m pytest -q" not in phase["validation"]
    assert any("CTX.READ.1" in note for note in phase["notes"])


def test_context_search_phase_is_complete_bounded_and_candidate_only():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.SEARCH.1"]

    assert phase["title"] == "Bounded Lexical Search Runtime"
    assert phase["track"] == "CTX"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["CTX.SELECT.1"]
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {
        "core/bounded_lexical_search.py",
        "core/context_search_runtime.py",
        "tests/test_bounded_lexical_search.py",
        "tests/test_context_search_runtime.py",
    } <= set(phase["allowed_files"])
    assert {"database/", "graph/", "patching/", "core/indexer.py"} <= set(
        phase["forbidden_files"]
    )
    assert any("CTX.READ.1" in note for note in phase["notes"])


def test_context_read_phase_is_complete_bounded_and_never_writable():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.READ.1"]

    assert phase["title"] == "Bounded Direct File Read Runtime"
    assert phase["track"] == "CTX"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["CTX.SELECT.1", "CTX.SEARCH.1"]
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {
        "core/direct_file_reader.py",
        "core/direct_context_runtime.py",
        "core/direct_read_receipt.py",
        "tests/test_direct_file_reader.py",
        "tests/test_direct_context_runtime.py",
        "tests/test_direct_read_receipt.py",
    } <= set(phase["allowed_files"])
    assert {"database/", "graph/", "patching/", "core/indexer.py"} <= set(
        phase["forbidden_files"]
    )
    assert any("CTX.PATCH.1" in note for note in phase["notes"])


def test_context_patch_phase_is_complete_pure_and_never_writable():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.PATCH.1"]

    assert phase["title"] == "Direct Context Patch Candidate Gate"
    assert phase["track"] == "CTX"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == [
        "CTX.SELECT.1",
        "CTX.SEARCH.1",
        "CTX.READ.1",
    ]
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {
        "core/file_patchability.py",
        "core/direct_patch_candidate_gate.py",
        "core/proposed_patch_set.py",
        "tests/test_file_patchability.py",
        "tests/test_direct_patch_candidate_gate.py",
        "tests/test_proposed_patch_set.py",
    } <= set(phase["allowed_files"])
    assert {"database/", "graph/", "patching/", "core/indexer.py"} <= set(
        phase["forbidden_files"]
    )
    assert any("CTX.APPLY.0" in note for note in phase["notes"])


def test_context_apply_phase_is_complete_and_remains_non_authorizing():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CTX.APPLY.0"]

    assert phase["title"] == "Direct Context Patch Safety Attachment"
    assert phase["track"] == "CTX"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == [
        "CTX.SELECT.1",
        "CTX.SEARCH.1",
        "CTX.READ.1",
        "CTX.PATCH.1",
    ]
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {
        "core/direct_context_patch_attachment.py",
        "core/patch_safety.py",
        "tests/test_direct_context_patch_attachment.py",
        "docs/designs/2026-08-02-direct-context-patch-safety-attachment.md",
    } <= set(phase["allowed_files"])
    assert {"database/", "graph/", "patching/", "web/", "core/indexer.py"} <= set(
        phase["forbidden_files"]
    )
    assert any("CTX.APPLY.1" in note for note in phase["notes"])


def test_early_error_hardening_completes_before_real_dogfood_resumes():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    assert "DOGFOOD.1" not in by_id
    assert by_id["DOGFOOD.1A"]["title"] == "Live Progress Operator Evaluation Framework"
    assert by_id["DOGFOOD.1A"]["status"] == "complete"
    assert by_id["DOGFOOD.1A"]["prerequisites"] == ["UX.LIVE.CLOSE"]
    assert by_id["HARDEN.PROGRESS.1"]["title"] == "Early Error Terminal Snapshot Coverage"
    assert by_id["HARDEN.PROGRESS.1"]["status"] == "complete"
    assert by_id["HARDEN.PROGRESS.1"]["prerequisites"] == ["DOGFOOD.1A"]
    assert by_id["DOGFOOD.1B"]["title"] == "Real Operator Run Evaluation"
    assert by_id["DOGFOOD.1B"]["status"] == "proposed"
    assert by_id["DOGFOOD.1B"]["prerequisites"] == ["DOGFOOD.1A", "HARDEN.PROGRESS.1"]
    assert by_id["VERIFY.TEST.1"]["status"] == "proposed"
    assert by_id["VERIFY.TEST.1"]["prerequisites"] == ["DOGFOOD.1B"]


# â”€â”€ enum / constant exposure â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_enums_match_spec():
    assert STATUSES == ("proposed", "active", "complete", "parked", "deferred")
    assert AUTOMATION_LEVELS == (
        "LOCAL_0_OBSERVE",
        "LOCAL_1_PREPARE",
        "SANDBOX_2_DRAFT_PATCH",
        "REMOTE_3_DRAFT_PR",
        "AUTO_4_AUTO_MERGE",
    )
    assert BUDGET_TIERS == ("local_only", "cheap_api_allowed", "strong_model_requires_approval", "blocked")
    assert RISK_LEVELS == ("low", "medium", "high", "blocked")
    assert "CTX" in PHASE_ID_PREFIXES
    assert set(REQUIRED_ROOT_FIELDS) == {"schema_version", "updated_at", "phases"}


def test_validate_does_not_mutate_input():
    data = _registry(phases=[_phase(), _phase(phase_id="AUTO.2a", track="AUTO")])
    snap = copy.deepcopy(data)
    validate_phase_registry(data)
    summarize_phase_registry(data, report_id="r", created_at="t")
    assert data == snap


# â”€â”€ 20. forbidden-token / import guards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_CORE = Path(__file__).parent.parent / "core" / "phase_registry.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "validate_phase_registry.py"
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
            assert top != "core", f"ROAD.1 core must not import other core modules: {module!r}"
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


def test_guardrail_note_present_and_clean():
    assert "report-only" in PHASE_REGISTRY_GUARDRAIL_NOTE.lower()
    report = summarize_phase_registry(_registry(), report_id="r", created_at="t")
    assert report["guardrail_note"] == PHASE_REGISTRY_GUARDRAIL_NOTE
