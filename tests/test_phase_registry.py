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
    assert {"INPUT.1", "INPUT.2", "INPUT.3"} <= ids
    assert {"WAITER.1", "WAITER.2"} <= ids
    assert {"ACQUIRE.1", "ACQUIRE.2", "ACQUIRE.3"} <= ids
    assert {"EVIDENCE.1", "EVIDENCE.2"} <= ids
    assert {"CLAIM.1"} <= ids
    assert {"SYNTHESIS.1"} <= ids
    assert {"CHECK.1", "CHECK.2"} <= ids
    assert {
        "WORKER.DECL.1",
        "WORKER.DECL.2A",
        "WORKER.DECL.2A.1",
        "WORKER.DECL.2A.2",
        "WORKER.DECL.2B",
    } <= ids
    assert "CONTROL.SAFETY.LIVE.1" in ids
    assert "WAITER.LIVE.1" in ids
    assert "PATCH.BASIS.LIVE.1" in ids
    assert "OPS.PATCH.2" in ids
    assert {
        "RETRIEVE.LIVE.1",
        "RETRIEVE.LIVE.2",
        "RETRIEVE.LIVE.3",
        "RETRIEVE.LIVE.4",
    } <= ids
    assert "ANSWER.GROUND.LIVE.1" in ids
    assert "DEFECT.PROBE.LIVE.1" in ids
    assert "VALIDATE.ORACLE.LIVE.1" in ids
    assert "EXEC.POLICY.LIVE.1" in ids
    assert "EXEC.APPROVAL.LIVE.1" in ids
    assert "ANSWER.GROUND.LIVE.2" in ids
    assert "CONTROL.LOCALIZE.LIVE.2" in ids
    assert "REPAIR.INTENT.1" in ids
    assert "REPAIR.INTENT.ADMIT.1" in ids
    assert "REPAIR.INTENT.UI.1" in ids
    assert "CTX.OOP.1A" in ids
    assert "CTX.OOP.1C" in ids
    assert "OOP.INTENT.UI.1" in ids
    assert "OOP.INTENT.DESIGN.1" in ids
    assert "OOP.INTENT.DETECT.2" in ids
    assert "OOP.INTENT.CONTINUE.1" in ids
    assert "PATCH.SCOPE.EXPAND.1" in ids
    assert "PATCH.SCOPE.RECHECK.1" in ids
    assert "PATCH.SCOPE.REFRESH.1" in ids
    assert len(data["phases"]) == 224


def test_input_understanding_phase_is_registered_and_inert():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INPUT.1"]

    assert phase["track"] == "INPUT"
    assert phase["title"] == "Lossless Task Contract & Semantic Waiter Boundary"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["human_approval_required"] is True
    assert "core/input_understanding.py" in phase["allowed_files"]


def test_semantic_waiter_phase_is_registered_and_inert_by_default():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INPUT.2"]

    assert phase["track"] == "INPUT"
    assert phase["title"] == "Semantic Waiter Model Adapter & Semantic Evaluation"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["risk_level"] == "medium"
    assert phase["prerequisites"] == ["INPUT.1"]
    assert phase["human_approval_required"] is True
    assert phase["writes_real_repo"] is False
    assert phase["merge_allowed"] is False
    # The phase itself performs no model or network call: the live adapter is
    # opt-in, off by default, and absent from every validation command.
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert "core/semantic_waiter_adapter.py" in phase["allowed_files"]


def test_semantic_waiter_phase_documents_the_registry_schema_mismatch():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["INPUT.2"]["notes"]).lower()

    assert "opt-in" in notes
    assert "registry" in notes


def test_intake_completion_phase_is_registered_and_inert():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["INPUT.3"]

    assert phase["track"] == "INPUT"
    assert phase["title"] == "Progressive Intake Completion & Clarification Policy"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["INPUT.2"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["writes_real_repo"] is False
    # The optional intake assistant is local-only and opt-in; the phase itself
    # performs no model and no network call.
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert "core/intake_completion.py" in phase["allowed_files"]


def test_intake_completion_phase_keeps_input_1_and_2_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["INPUT.3"]["forbidden_files"]

    for frozen in (
        "core/task_contract.py",
        "core/explicit_evidence.py",
        "core/semantic_waiter.py",
        "core/requirement_preservation.py",
        "core/input_understanding.py",
        "core/semantic_waiter_adapter.py",
        "core/semantic_waiter_runner.py",
        "core/goal_brief.py",
        "core/mode_router.py",
    ):
        assert frozen in forbidden, frozen


def test_intake_completion_phase_documents_its_zero_model_guarantee():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["INPUT.3"]["notes"]).lower()

    assert "zero-model-correct" in notes
    assert "registry" in notes
    assert "opt-in" in notes
    assert "no cloud path" in notes


def test_execution_waiter_phase_is_registered_and_inert():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WAITER.1"]

    assert phase["track"] == "WAITER"
    assert phase["title"] == "Deterministic Capability-Based Execution Router"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["INPUT.3"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["writes_real_repo"] is False
    # The phase is pure: no model, no network, no opt-in adapter of any kind.
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert "core/execution_waiter.py" in phase["allowed_files"]


def test_execution_waiter_phase_keeps_input_1_to_3_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["WAITER.1"]["forbidden_files"]

    for module in (
        "core/task_contract.py",
        "core/explicit_evidence.py",
        "core/requirement_preservation.py",
        "core/semantic_waiter_runner.py",
        "core/intake_completion.py",
        "core/input_completion.py",
    ):
        assert module in forbidden, module


def test_execution_waiter_phase_may_not_touch_live_routing_or_model_selection():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["WAITER.1"]["forbidden_files"]

    for module in (
        "core/mode_router.py",
        "core/mixed_mode_intent_router.py",
        "core/driver_model_routing.py",
        "core/model_role_registry.py",
        "core/project_evolution_mode.py",
        "core/context_selection.py",
    ):
        assert module in forbidden, module


def test_execution_waiter_phase_documents_its_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["WAITER.1"]["notes"]).lower()

    assert "workflow is not compute" in notes
    assert "requirements, not permissions" in notes
    assert "broad is not ongoing" in notes
    assert "report-only and unwired" in notes


def test_evidence_requirement_phase_is_registered_and_inert():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WAITER.2"]

    assert phase["track"] == "WAITER"
    assert phase["title"] == "Deterministic Evidence Requirement Contract"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["WAITER.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["writes_real_repo"] is False
    # The phase is pure: no model, no network, no opt-in adapter of any kind.
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert "core/waiter_evidence.py" in phase["allowed_files"]


def test_evidence_requirement_phase_keeps_input_and_waiter_1_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["WAITER.2"]["forbidden_files"]

    for module in (
        "core/task_contract.py",
        "core/explicit_evidence.py",
        "core/requirement_preservation.py",
        "core/intake_completion.py",
        "core/task_shape.py",
        "core/capability_requirements.py",
        "core/execution_waiter.py",
        "core/waiter_receipt.py",
    ):
        assert module in forbidden, module


def test_evidence_requirement_phase_may_not_touch_acquisition_machinery():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["WAITER.2"]["forbidden_files"]

    for module in (
        "core/context_selection.py",
        "core/context_search_runtime.py",
        "core/retriever.py",
        "core/indexer.py",
        "core/repository_inventory.py",
        "core/mode_router.py",
        "core/executor.py",
    ):
        assert module in forbidden, module


def test_evidence_requirement_phase_documents_its_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["WAITER.2"]["notes"]).lower()

    assert "requirement, not acquisition" in notes
    assert "domain is not role" in notes
    assert "priority, not sweep" in notes
    assert "no capability escalation" in notes
    assert "no required-capability loss" in notes
    assert "external evidence is never reduced to direct context" in notes
    assert "no workflow escalation" in notes
    assert "report-only and unwired" in notes


def test_acquisition_request_phase_is_registered_and_inert():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["ACQUIRE.1"]

    assert phase["track"] == "ACQUIRE"
    assert phase["title"] == "Bounded Evidence Acquisition Request Contract"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["WAITER.2"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["writes_real_repo"] is False
    # The phase is pure: no model, no network, no opt-in adapter of any kind.
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert "core/evidence_acquire_request.py" in phase["allowed_files"]


def test_acquisition_request_phase_keeps_input_and_both_waiters_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["ACQUIRE.1"]["forbidden_files"]

    for module in (
        "core/task_contract.py",
        "core/explicit_evidence.py",
        "core/requirement_preservation.py",
        "core/intake_completion.py",
        "core/task_shape.py",
        "core/capability_requirements.py",
        "core/execution_waiter.py",
        "core/waiter_receipt.py",
        "core/evidence_requirements.py",
        "core/evidence_policy.py",
        "core/waiter_evidence.py",
    ):
        assert module in forbidden, module


def test_acquisition_request_phase_may_not_touch_acquisition_machinery():
    """The phase that describes acquisition is the phase that may not perform it."""
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["ACQUIRE.1"]["forbidden_files"]

    for module in (
        "core/context_selection.py",
        "core/context_search_runtime.py",
        "core/retriever.py",
        "core/indexer.py",
        "core/index_manifest.py",
        "core/repository_inventory.py",
        "core/file_candidate_selector.py",
        "core/direct_file_reader.py",
        "core/graph_walker.py",
        "core/mode_router.py",
        "core/executor.py",
        "core/validation_execution.py",
    ):
        assert module in forbidden, module


def test_acquisition_request_phase_documents_its_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["ACQUIRE.1"]["notes"]).lower()

    assert "request, not acquisition" in notes
    assert "source class is not filename" in notes
    assert "every budget is finite" in notes
    assert "budget follows evidence, not workflow" in notes
    assert "broad is not everything" in notes
    assert "tiers survive translation" in notes
    assert "monotonic in both directions" in notes
    assert "a path is preserved, never produced" in notes
    assert "workflow immutability" in notes
    assert "no planning" in notes
    assert "zero acquisition authority" in notes
    assert "report-only and unwired" in notes


def test_candidate_eligibility_phase_is_registered_and_inert():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["ACQUIRE.2"]

    assert phase["track"] == "ACQUIRE"
    assert phase["title"] == "Bounded Candidate Eligibility & Selector Bridge"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["ACQUIRE.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["writes_real_repo"] is False
    # The phase is pure: no model, no network, no opt-in adapter of any kind.
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert "core/evidence_candidate_pool.py" in phase["allowed_files"]


def test_candidate_eligibility_phase_keeps_every_upstream_contract_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["ACQUIRE.2"]["forbidden_files"]

    for module in (
        "core/task_contract.py",
        "core/task_shape.py",
        "core/capability_requirements.py",
        "core/execution_waiter.py",
        "core/evidence_requirements.py",
        "core/evidence_policy.py",
        "core/waiter_evidence.py",
        "core/acquisition_request.py",
        "core/acquisition_policy.py",
        "core/evidence_acquire_request.py",
    ):
        assert module in forbidden, module


def test_candidate_eligibility_phase_may_not_rewrite_ctx_select_or_walk_a_repository():
    """The phase that bridges to the selector is the phase that may not be one."""
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["ACQUIRE.2"]["forbidden_files"]

    for module in (
        "core/context_selection.py",
        "core/file_candidate_selector.py",
        "core/file_actionability.py",
        "core/file_capabilities.py",
        "core/repository_inventory.py",
        "core/repo_ignore.py",
        "core/index_manifest.py",
        "core/indexer.py",
        "core/graph_walker.py",
        "core/executor.py",
    ):
        assert module in forbidden, module


def test_candidate_eligibility_phase_documents_its_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["ACQUIRE.2"]["notes"]).lower()

    assert "candidate is not evidence" in notes
    assert "explicit-target closure, frozen" in notes
    assert "target_artifact-equivalent" in notes
    assert "acquire.2 is closed / frozen" in notes
    assert "inventory consumed, never built" in notes
    assert "membership is the only door" in notes
    assert "extension is not authority" in notes
    assert "unknown is a safe answer" in notes
    assert "exclusions and deferrals are hard filters" in notes
    assert "monotonic narrowing" in notes
    assert "anti-6087" in notes
    assert "no required-role loss" in notes
    assert "selector bridge, not a second selector" in notes
    assert "zero authority" in notes
    assert "report-only and unwired" in notes


def test_content_acquisition_phase_is_registered_as_a_conditional_read_runtime():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["ACQUIRE.3"]

    assert phase["track"] == "ACQUIRE"
    assert phase["title"] == "Bounded Content Acquisition & Source Receipt"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["prerequisites"] == ["ACQUIRE.2"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    assert "core/content_acquisition.py" in phase["allowed_files"]
    assert "core/evidence_content_acquisition.py" in phase["allowed_files"]
    assert "tests/test_evidence_content_acquisition_boundaries.py" in phase[
        "allowed_files"
    ]


def test_content_acquisition_phase_keeps_upstream_and_live_wiring_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["ACQUIRE.3"]["forbidden_files"]

    for module in (
        "core/acquisition_request.py",
        "core/acquisition_policy.py",
        "core/evidence_acquire_request.py",
        "core/candidate_inventory.py",
        "core/candidate_eligibility.py",
        "core/eligibility_policy.py",
        "core/evidence_candidate_pool.py",
        "core/context_selection.py",
        "core/file_candidate_selector.py",
        "core/repository_inventory.py",
        "core/indexer.py",
        "core/graph_walker.py",
        "core/mode_router.py",
        "core/mixed_mode_intent_router.py",
        "core/unified_workbench_input_plan.py",
        "core/project_evolution_mode.py",
        "core/commander_run_contract.py",
        "core/executor.py",
        "core/pipeline.py",
        "core/validation_execution.py",
    ):
        assert module in forbidden, module


def test_content_acquisition_phase_documents_schema_limit_and_epistemic_boundary():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["ACQUIRE.3"]["notes"]).lower()

    assert "explicit selection, never self-selection" in notes
    assert "explicit human-approved authorization" in notes
    assert "authorization only narrows" in notes
    assert "candidate-addressed reads, no traversal" in notes
    assert "payload and receipt are separate" in notes
    assert "acquired is not verified" in notes
    assert "registry capability limitation" in notes
    assert "schema v1 has no field" in notes
    assert "absent or invalid authorization means zero reads" in notes
    assert "writes_real_repo=false" in notes
    assert "registry validation and road.2 phase picking execute nothing" in notes
    assert "import-time inert and not live-wired" in notes
    assert "future evidence.1" in notes


def test_evidence_verification_phase_is_registered_as_a_deterministic_gate():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["EVIDENCE.1"]

    assert phase["track"] == "EVIDENCE"
    assert phase["title"] == "Acquired Source Verification & Evidence Promotion Contract"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["prerequisites"] == ["ACQUIRE.3"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for module in (
        "core/evidence_verification.py",
        "core/evidence_analyzer.py",
        "core/evidence_promotion_gate.py",
        "core/evidence_analyzer_adapter.py",
    ):
        assert module in phase["allowed_files"], module
    for suite in (
        "tests/test_evidence_verification.py",
        "tests/test_evidence_verification_boundaries.py",
        "tests/test_evidence_analyzer_adapter.py",
        "tests/test_evidence_semantic_provenance.py",
    ):
        assert suite in phase["allowed_files"], suite


def test_evidence_verification_phase_keeps_acquisition_and_live_wiring_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["EVIDENCE.1"]["forbidden_files"]

    for module in (
        "core/content_acquisition.py",
        "core/evidence_content_acquisition.py",
        "core/acquisition_request.py",
        "core/candidate_eligibility.py",
        "core/evidence_requirements.py",
        "core/task_contract.py",
        "core/context_selection.py",
        "core/file_candidate_selector.py",
        "core/repository_inventory.py",
        "core/indexer.py",
        "core/graph_walker.py",
        "core/mode_router.py",
        "core/mixed_mode_intent_router.py",
        "core/unified_workbench_input_plan.py",
        "core/project_evolution_mode.py",
        "core/commander_run_contract.py",
        "core/executor.py",
        "core/pipeline.py",
        "core/validation_execution.py",
    ):
        assert module in forbidden, module


def test_evidence_verification_phase_documents_its_epistemic_boundary():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["EVIDENCE.1"]["notes"]).lower()

    assert "the proposition arrives, it is never invented" in notes
    assert "two separate gates, role and relation" in notes
    assert "expected role is a hypothesis, not a verdict" in notes
    assert "scope competence is a frozen table" in notes
    assert "absence needs coverage, a counterexample does not" in notes
    assert "code existing is not code running" in notes
    assert "omission is not contradiction" in notes
    assert "the payload is authoritative and the path is never reopened" in notes
    assert "spans are bytes somebody read" in notes
    assert "the model is an analyzer, not the gate" in notes
    assert "no numeric confidence anywhere" in notes
    assert "contradiction is verified evidence" in notes
    assert "no claim synthesis" in notes
    assert "source content never reaches a receipt" in notes
    assert "cloud disclosure is a configuration act" in notes
    assert "one analyzer, one call, no escalation" in notes
    assert "registry capability limitation" in notes
    assert "ships no live transport" in notes
    assert "import-time inert and not live-wired" in notes
    assert "anti-deepseek negative claim regression" in notes
    assert "evidence.2 / claim.1" in notes
    # The closure amendment: a judgement accepted through a deterministic gate
    # is not a judgement produced by one, and the record has to say which.
    assert "semantic relation is analyzer-assessed, not deterministically proven" in notes
    assert "verifiedevidence means tamper-bound" in notes
    assert "it does not mean the proposition was proven true" in notes
    assert "evidence.1 closed and frozen" in notes



def test_evidence_set_assessment_phase_is_registered_as_a_report_only_layer():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["EVIDENCE.2"]

    assert phase["track"] == "EVIDENCE"
    assert phase["title"] == "Evidence Set Coverage, Conflict & Independence Contract"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["EVIDENCE.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    assert "core/evidence_set_assessment.py" in phase["allowed_files"]
    for suite in (
        "tests/test_evidence_set_assessment.py",
        "tests/test_evidence_set_assessment_boundaries.py",
    ):
        assert suite in phase["allowed_files"], suite


def test_evidence_set_assessment_phase_keeps_evidence_1_and_acquisition_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["EVIDENCE.2"]["forbidden_files"]

    for module in (
        "core/evidence_verification.py",
        "core/evidence_analyzer.py",
        "core/evidence_promotion_gate.py",
        "core/evidence_analyzer_adapter.py",
        "core/content_acquisition.py",
        "core/evidence_content_acquisition.py",
        "core/acquisition_request.py",
        "core/evidence_requirements.py",
        "core/context_selection.py",
        "core/executor.py",
        "core/pipeline.py",
        "core/validation_execution.py",
    ):
        assert module in forbidden, module


def test_evidence_set_assessment_phase_documents_its_epistemic_boundary():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["EVIDENCE.2"]["notes"]).lower()

    assert "one proposition, many records, no claim" in notes
    assert "counting is not weighing" in notes
    assert "relations are grouped, never regraded" in notes
    assert "role presence and directional support are different dimensions" in notes
    assert "role requirements are supplied, never invented" in notes
    assert "identical content proves duplication; a different digest proves nothing" in notes
    assert "independence is consumed, never derived" in notes
    assert "anti-mirror-tunnel" in notes
    assert "absence still needs coverage across a set" in notes
    assert "no producer for coverage or current-state receipts" in notes
    assert "aggregation cannot upgrade epistemic status" in notes
    assert "tamper binding is re-derived, never trusted" in notes
    assert "admission before description" in notes
    assert "canonical ordering and deterministic identity" in notes
    assert "no source bytes, no analyzer, no model" in notes
    assert "claim decision authority is a property, not a field" in notes
    assert "upstream regression amended, not weakened" in notes
    assert "deepseek dogfood evidence-set regression" in notes
    assert "claim.1" in notes


def test_claim_assessment_phase_is_registered_as_a_report_only_layer():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CLAIM.1"]

    assert phase["track"] == "CLAIM"
    assert phase["title"] == "Bounded Proposition Assessment Contract"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["EVIDENCE.2"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    assert "core/claim_assessment.py" in phase["allowed_files"]
    for suite in (
        "tests/test_claim_assessment.py",
        "tests/test_claim_assessment_boundaries.py",
    ):
        assert suite in phase["allowed_files"], suite


def test_claim_assessment_phase_keeps_the_whole_evidence_track_frozen():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["CLAIM.1"]["forbidden_files"]

    for module in (
        "core/evidence_set_assessment.py",
        "core/evidence_verification.py",
        "core/evidence_analyzer.py",
        "core/evidence_promotion_gate.py",
        "core/evidence_analyzer_adapter.py",
        "core/content_acquisition.py",
        "core/evidence_content_acquisition.py",
        "core/acquisition_request.py",
        "core/evidence_requirements.py",
        "core/context_selection.py",
        "core/executor.py",
        "core/pipeline.py",
        "core/validation_execution.py",
    ):
        assert module in forbidden, module


def test_claim_assessment_phase_documents_its_epistemic_boundary():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    notes = " ".join(by_id["CLAIM.1"]["notes"]).lower()

    assert "one proposition, one assessed set, no truth" in notes
    assert "supported is not proven" in notes
    assert "anti-truth-laundering is structural" in notes
    assert "conflict is terminal and has no winner" in notes
    assert "no majority, proved statically" in notes
    assert "duplicates do not strengthen" in notes
    assert "a different digest is not independence" in notes
    assert "absence still needs coverage" in notes
    assert "code existing is not code running" in notes
    assert "role presence is not directional support" in notes
    assert "relations are read, never regraded" in notes
    assert "the entry gate fails closed and repairs nothing" in notes
    assert "authority is narrow and final claim authority is a property" in notes
    assert "no source bytes, no paths, no spans, no model" in notes
    assert "determinism and fingerprint binding" in notes
    assert "upstream regressions amended, not weakened" in notes
    assert "deepseek dogfood claim regression" in notes
    assert "synthesis.1" in notes


def test_claim_assessment_phase_emits_no_final_claim_and_no_confidence():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    summary = by_id["CLAIM.1"]["summary"].lower()

    assert "never 'what is ultimately true?'" in summary
    assert "no true, false, likely_true, probably_false, confidence_high" in summary
    assert "emits no final claim" in summary
    assert "calls no model" in summary
    assert "is not wired into any live product path" in summary


def test_structured_synthesis_phase_is_registered_as_report_only_history():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["SYNTHESIS.1"]

    assert phase["track"] == "SYNTHESIS"
    assert phase["title"] == "Task-Shaped Claim Composition Contract"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["CLAIM.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for artifact in (
        "core/structured_synthesis.py",
        "tests/test_structured_synthesis.py",
        "tests/test_structured_synthesis_boundaries.py",
        "tests/test_claim_assessment_boundaries.py",
        "docs/designs/2026-08-26-task-shaped-claim-composition-contract.md",
    ):
        assert artifact in phase["allowed_files"], artifact


def test_structured_synthesis_phase_documents_composition_boundaries_and_gap():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["SYNTHESIS.1"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    assert "report-only" in summary
    assert "invent" in summary
    assert "winner selection" in summary
    assert "final-response generation" in summary
    assert "task-shaped composition, not claim creation" in notes
    assert "the preserved user structure is authoritative" in notes
    assert "explicit bindings only" in notes
    assert "known missing proposition-binding producer" in notes
    assert "claim status and semantic basis survive" in notes
    assert "no winner, score or confidence" in notes
    assert "output is structured data, not response prose" in notes
    assert "determinism and tamper binding" in notes
    assert "authority is narrow and report-only" in notes
    assert "no source, evidence or model access" in notes
    assert "deepseek five-way regression" in notes
    assert "no live wiring" in notes
    assert "response.1" in notes


def test_structured_synthesis_phase_freezes_upstream_and_live_paths():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["SYNTHESIS.1"]["forbidden_files"]

    for module in (
        "core/task_contract.py",
        "core/claim_assessment.py",
        "core/evidence_set_assessment.py",
        "core/evidence_verification.py",
        "core/evidence_analyzer.py",
        "core/evidence_promotion_gate.py",
        "core/content_acquisition.py",
        "core/evidence_content_acquisition.py",
        "core/context_selection.py",
        "core/mode_router.py",
        "core/mixed_mode_intent_router.py",
        "core/unified_workbench_input_plan.py",
        "core/project_evolution_mode.py",
        "core/commander_run_contract.py",
        "core/executor.py",
        "core/pipeline.py",
        "core/validation_execution.py",
    ):
        assert module in forbidden, module


def test_post_run_reconciliation_phase_is_registered_as_report_only_history():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.1"]

    assert phase["track"] == "CHECK"
    assert phase["title"] == "Post-Run Contract Reconciliation"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for artifact in (
        "core/post_run_reconciliation.py",
        "core/post_run_observation.py",
        "tests/test_post_run_reconciliation.py",
        "tests/test_post_run_reconciliation_boundaries.py",
        "docs/designs/2026-08-27-post-run-contract-reconciliation.md",
    ):
        assert artifact in phase["allowed_files"], artifact
        assert artifact in phase["expected_artifacts"] or artifact.startswith(
            "docs/"
        ), artifact


def test_post_run_reconciliation_depends_on_the_execution_branch_not_synthesis():
    """CHECK.1 shipped after SYNTHESIS.1 but consumes nothing from it."""
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.1"]

    assert phase["prerequisites"] == ["CTX.APPLY.0"]
    assert "SYNTHESIS.1" not in phase["prerequisites"]
    assert "CLAIM.1" not in phase["prerequisites"]
    assert by_id["CTX.APPLY.0"]["status"] == "complete"
    notes = " ".join(phase["notes"]).lower()
    assert "execution branch, not the epistemic branch" in notes
    assert "registry records architecture, not implementation order" in notes


def test_post_run_reconciliation_phase_documents_its_reconciliation_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.1"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    assert "report-only" in summary
    assert "outrank" in summary
    assert "no semantic goal review" in summary
    assert "objective facts outrank the self-report" in notes
    assert "path authority is fail-closed" in notes
    assert "patch safety is reused, not rediscovered" in notes
    assert "validation cannot be faked by prose" in notes
    assert "stale validation cannot certify a later state" in notes
    assert "no success laundering" in notes
    assert "preservation obligations hand off to check.2" in notes
    assert "determinism and tamper binding" in notes
    assert "authority is narrow and report-only" in notes
    assert "no diff, source, model or repair loop" in notes
    assert "one execution unit at a time" in notes
    assert "deepseek-style execution regression" in notes
    assert "no live wiring" in notes
    assert "check.2" in notes


def test_post_run_reconciliation_phase_freezes_upstream_and_live_paths():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["CHECK.1"]["forbidden_files"]

    for module in (
        "core/patch_safety.py",
        "core/repository_path_policy.py",
        "core/direct_context_patch_attachment.py",
        "core/direct_patch_candidate_gate.py",
        "core/validation_execution.py",
        "core/validation_command.py",
        "core/validation_side_effects.py",
        "core/executor.py",
        "core/pipeline.py",
        "core/self_correct_loop.py",
        "core/worker_result_review.py",
        "core/worker_runs.py",
        "core/mirror_tunnel_claim_diff_check.py",
        "core/project_evolution_mode.py",
        "core/commander_run_contract.py",
        "core/mode_router.py",
        "core/task_contract.py",
        "core/claim_assessment.py",
        "core/structured_synthesis.py",
        "patching/",
    ):
        assert module in forbidden, module


def test_goal_fidelity_phase_is_registered_as_report_only_history():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.2"]

    assert phase["track"] == "CHECK"
    assert phase["title"] == "Post-Run Goal-Fidelity Verification Contract"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for artifact in (
        "core/goal_fidelity_review.py",
        "tests/test_goal_fidelity_review.py",
        "tests/test_goal_fidelity_review_boundaries.py",
        "docs/designs/2026-08-27-post-run-goal-fidelity-verification.md",
    ):
        assert artifact in phase["allowed_files"], artifact
        assert artifact in phase["expected_artifacts"] or artifact.startswith(
            "docs/"
        ), artifact


def test_goal_fidelity_phase_depends_on_both_upstream_branches():
    """CHECK.2 is the first phase to consume the execution *and* claim branches."""
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.2"]

    assert phase["prerequisites"] == ["CHECK.1", "CLAIM.1"]
    assert "SYNTHESIS.1" not in phase["prerequisites"]
    assert by_id["CHECK.1"]["status"] == "complete"
    assert by_id["CLAIM.1"]["status"] == "complete"
    notes = " ".join(phase["notes"]).lower()
    assert "two branches, one join" in notes
    assert "consumes no synthesis.1" in notes


def test_goal_fidelity_phase_documents_its_verification_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.2"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    assert "report-only" in summary
    assert "never 'should this run be accepted?'" in summary
    assert "no reviewer model, no reviewer bypass" in notes
    assert "execution severity is monotonic" in notes
    assert "no obligation invention" in notes
    assert "no obligation loss" in notes
    assert "polarity is supplied, never inferred" in notes
    assert "claim status is never laundered" in notes
    assert "a validation receipt is not a semantic claim" in notes
    assert "semantic basis survives aggregation" in notes
    assert "post-run state binding is a known gap" in notes
    assert "no majority, no score, no reduction" in notes
    assert "determinism and tamper binding" in notes
    assert "check.2 is not check.3" in notes
    assert "upstream producers are missing and documented" in notes
    assert "no live wiring" in notes


def test_goal_fidelity_phase_freezes_upstream_and_live_paths():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    forbidden = by_id["CHECK.2"]["forbidden_files"]

    for module in (
        "core/post_run_reconciliation.py",
        "core/post_run_observation.py",
        "core/claim_assessment.py",
        "core/evidence_set_assessment.py",
        "core/evidence_verification.py",
        "core/evidence_analyzer.py",
        "core/content_acquisition.py",
        "core/structured_synthesis.py",
        "core/task_contract.py",
        "core/patch_safety.py",
        "core/validation_execution.py",
        "core/executor.py",
        "core/self_correct_loop.py",
        "core/worker_result_review.py",
        "core/commander_run_contract.py",
        "core/mode_router.py",
        "patching/",
        "agents/",
    ):
        assert module in forbidden, module


def test_shadow_post_run_wiring_phase_is_registered_as_live_but_shadow_only():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.LIVE.1"]

    assert phase["track"] == "CHECK"
    assert phase["title"] == "Shadow Post-Run Reconciliation Wiring"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for artifact in (
        "core/live_change_observation.py",
        "core/live_execution_authorization.py",
        "core/live_worker_report.py",
        "core/live_validation_receipt.py",
        "core/post_run_reconciliation_shadow.py",
        "tests/test_post_run_reconciliation_shadow.py",
        "tests/test_post_run_reconciliation_shadow_boundaries.py",
        "docs/designs/2026-08-28-shadow-post-run-reconciliation-wiring.md",
    ):
        assert artifact in phase["allowed_files"], artifact
        assert artifact in phase["expected_artifacts"] or artifact.startswith(
            "docs/"
        ), artifact


def test_shadow_post_run_wiring_requires_check_1_and_not_check_2():
    """The live wiring consumes the objective checker only."""
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.LIVE.1"]

    assert phase["prerequisites"] == ["CHECK.1"]
    assert "CHECK.2" not in phase["prerequisites"]
    assert "CLAIM.1" not in phase["prerequisites"]
    assert by_id["CHECK.1"]["status"] == "complete"


def test_shadow_post_run_wiring_documents_its_shadow_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.LIVE.1"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    assert "shadow-only" in summary
    assert "no repository traversal" in summary
    assert "cannot widen upstream write authority" in summary
    assert "neither invokes check.2 nor promotes check.1 to enforcement" in summary
    assert "shadow only, and that is the point" in notes
    assert "one reconciliation policy" in notes
    assert "authority is translated, never widened" in notes
    assert "no prose is parsed" in notes
    assert "no new repository traversal" in notes
    assert "state identity is the observed change set" in notes
    assert "stale validation is detected through the live path" in notes
    assert "a failed validation still produces a receipt" in notes
    assert "known empty is not missing" in notes
    assert "failure is isolated and bounded" in notes
    assert "the existing artifact store is reused" in notes
    assert "no repository source write" in notes
    assert "what is wired, and what is not" in notes
    assert "check.2 is not invoked and check.3 is not built" in notes
    assert "default off, enabled for dogfood" in notes


def test_shadow_post_run_wiring_freezes_the_checkers_and_the_apply_engines():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.LIVE.1"]
    forbidden = phase["forbidden_files"]

    for module in (
        "core/post_run_reconciliation.py",
        "core/post_run_observation.py",
        "core/goal_fidelity_review.py",
        "core/claim_assessment.py",
        "core/patch_safety.py",
        "core/repository_path_policy.py",
        "core/executor.py",
        "core/pipeline.py",
        "core/self_correct_loop.py",
        "core/validator.py",
        "core/validation_execution.py",
        "core/validation_side_effects.py",
        "core/worker_result_review.py",
        "core/mirror_tunnel_claim_diff_check.py",
        "patching/",
        "agents/",
        "web/",
    ):
        assert module in forbidden, module
        assert module not in phase["allowed_files"], module


def test_independent_worker_declaration_phase_is_registered_as_shadow_history():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.LIVE.1B"]

    assert phase["track"] == "CHECK"
    assert phase["title"] == "Independent Typed Worker Declaration Wiring"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["prerequisites"] == ["CHECK.LIVE.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for artifact in (
        "core/live_worker_declaration.py",
        "core/live_worker_report.py",
        "core/post_run_reconciliation_shadow.py",
        "core/run_lifecycle.py",
        "tests/test_live_worker_declaration.py",
        "tests/test_post_run_reconciliation_shadow.py",
        "tests/test_post_run_reconciliation_shadow_boundaries.py",
        "tests/test_post_run_reconciliation_boundaries.py",
        "docs/designs/2026-08-28-independent-typed-worker-declaration-wiring.md",
    ):
        assert artifact in phase["allowed_files"], artifact
        assert artifact in phase["expected_artifacts"] or artifact.startswith(
            "docs/"
        ), artifact


def test_independent_worker_declaration_phase_freezes_worker_protocol_and_checkers():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["CHECK.LIVE.1B"]

    for frozen in (
        "core/post_run_reconciliation.py",
        "core/post_run_observation.py",
        "core/goal_fidelity_review.py",
        "core/patch_safety.py",
        "core/repository_path_policy.py",
        "core/executor.py",
        "core/pipeline.py",
        "core/self_correct_loop.py",
        "core/worker_result_review.py",
        "core/worker_runs.py",
        "core/worker_assignment.py",
        "patching/",
        "agents/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen


def test_independent_worker_declaration_phase_documents_the_honest_gap():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {
        item["phase_id"]: item for item in data["phases"]
    }["CHECK.LIVE.1B"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    assert "independently supplied typed worker self-report" in summary
    assert "no production caller" in notes
    assert "structural independence is enforced" in notes
    assert "unknown kind stays unknown" in notes
    assert "legacy preserved" in notes
    assert "dogfood telemetry" in notes
    assert "kind mismatch" in notes
    assert "no cost or power expansion" in notes


def test_native_worker_declaration_qualification_is_registered_as_history():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.1"]

    assert phase["track"] == "WORKER"
    assert phase["title"] == (
        "Native Worker Declaration Source Qualification & Wiring"
    )
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "low"
    assert phase["prerequisites"] == ["CHECK.LIVE.1B"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for artifact in (
        "tests/test_native_worker_declaration_qualification.py",
        "docs/designs/"
        "2026-08-28-native-worker-declaration-source-qualification.md",
    ):
        assert artifact in phase["allowed_files"], artifact
        assert artifact in phase["expected_artifacts"], artifact


def test_native_worker_declaration_qualification_modifies_no_producer():
    """A qualification phase may read the wiring, never rewrite it.

    The CHECK.LIVE.1B seam, the worker protocol and every prompt contract the
    qualification inspected are all forbidden to it, so the recorded outcome
    cannot have been produced by quietly changing what it was measuring.
    """
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.1"]

    for frozen in (
        "core/live_worker_declaration.py",
        "core/live_worker_report.py",
        "core/post_run_reconciliation_shadow.py",
        "core/run_lifecycle.py",
        "core/post_run_reconciliation.py",
        "core/post_run_observation.py",
        "core/goal_fidelity_review.py",
        "core/claim_assessment.py",
        "core/prompter.py",
        "core/control_engine.py",
        "core/json_utils.py",
        "core/pipeline.py",
        "core/executor.py",
        "core/self_correct_loop.py",
        "core/worker_result_review.py",
        "core/worker_runs.py",
        "patching/patch_gates.py",
        "scripts/run_subagent_handoff.py",
        "scripts/run_patch_proposal_queue.py",
        "patching/",
        "agents/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen


def test_native_worker_declaration_qualification_records_the_unavailable_outcome():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["WORKER.DECL.1"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    # The classification itself, not a hedge about it.
    assert "worker_decl_1_source_unavailable" in summary
    assert "legacy_plan_derived" in summary
    assert "outcome is worker_decl_1_source_unavailable, and that is a result" in notes

    # The three findings the classification rests on.
    assert "no field declaring changed paths" in summary
    assert "timing is provenance" in notes
    assert "the near miss is recorded" in notes

    # And the boundary it did not cross.
    assert "no production module modified" in summary
    assert "no manufactured source and no silent widening" in notes
    assert "measurability stays honest" in notes
    assert "a future producer must fix the stage vocabulary first" in notes


def test_strict_patch_response_envelope_is_registered_as_shadow_history():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A"]

    assert phase["track"] == "WORKER"
    assert phase["title"] == "Strict Structured Patch Response Envelope"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["prerequisites"] == ["WORKER.DECL.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for artifact in (
        "core/worker_patch_envelope.py",
        "tests/test_worker_patch_envelope.py",
        "tests/test_worker_patch_envelope_boundaries.py",
        "docs/designs/2026-08-29-strict-structured-patch-response-envelope.md",
    ):
        assert artifact in phase["allowed_files"], artifact
        assert artifact in phase["expected_artifacts"], artifact


def test_strict_patch_response_envelope_freezes_the_channels_it_measures():
    """It may wire a shadow beside the legacy reader; it may not edit either.

    The legacy extractor, the apply engine, the prompt contracts and every
    frozen checker stay out of reach, so a recorded compatibility number cannot
    have been obtained by changing what was being measured.
    """
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A"]

    for frozen in (
        "core/json_utils.py",
        "core/prompter.py",
        "core/control_engine.py",
        "patching/patch_gates.py",
        "patching/patch_plan_executor.py",
        "core/executor.py",
        "core/self_correct_loop.py",
        "core/post_run_reconciliation.py",
        "core/post_run_observation.py",
        "core/goal_fidelity_review.py",
        "core/claim_assessment.py",
        "core/live_worker_declaration.py",
        "core/live_worker_report.py",
        "core/post_run_reconciliation_shadow.py",
        "agents/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    # The producer sites it does wire are allowed, and only those.
    for wired in (
        "core/worker_patch_envelope.py",
        "core/run_lifecycle.py",
        "core/replay_recorder.py",
        "core/agent_state.py",
        "core/pipeline.py",
        "core/sleeping_consultant.py",
        "scripts/run_patch_proposal_queue.py",
    ):
        assert wired in phase["allowed_files"], wired
        assert wired not in phase["forbidden_files"], wired


def test_strict_patch_response_envelope_documents_the_transport_boundary():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["WORKER.DECL.2A"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    # What the contract actually is.
    assert "exactly one json object" in summary
    assert "surrounding_prose_rejected" in summary
    assert "a protocol, not a second heuristic reader" in notes

    # And the four things it refuses.
    assert "one response, two parsers, zero extra model calls" in notes
    assert "reject whole, never truncate" in notes
    assert "authority cannot enter through the envelope" in notes
    assert "no change intent yet, on purpose" in notes
    assert "no prompt change in this phase" in notes


def test_strict_envelope_emission_experiment_is_registered_as_shadow_history():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A.1"]

    assert phase["track"] == "WORKER"
    assert phase["title"] == "Strict Envelope Emission Adoption Experiment"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["budget_tier"] == "local_only"
    assert phase["risk_level"] == "medium"
    assert phase["prerequisites"] == ["WORKER.DECL.2A"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert phase["requires_sandbox"] is False
    for artifact in (
        "core/strict_envelope_emission.py",
        "scripts/strict_envelope_emission_baseline.py",
        "tests/test_strict_envelope_emission.py",
        "tests/test_strict_envelope_emission_boundaries.py",
        "docs/designs/2026-08-30-strict-envelope-emission-adoption-experiment.md",
    ):
        assert artifact in phase["allowed_files"], artifact
        assert artifact in phase["expected_artifacts"], artifact


def test_strict_envelope_emission_experiment_freezes_what_it_measures():
    """It may change the request; it may not change the parser or the patch.

    The frozen envelope, the legacy extractor, the patch prompt contracts, the
    apply engine and every checker stay out of reach, so a recorded adoption
    number cannot have been obtained by moving the target.
    """
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A.1"]

    for frozen in (
        "core/worker_patch_envelope.py",
        "core/json_utils.py",
        "core/prompter.py",
        "core/control_engine.py",
        "policy/decision_helper.py",
        "patching/patch_gates.py",
        "patching/patch_plan_executor.py",
        "core/executor.py",
        "core/self_correct_loop.py",
        "core/post_run_reconciliation.py",
        "core/post_run_reconciliation_shadow.py",
        "core/live_worker_declaration.py",
        "core/live_worker_report.py",
        "core/goal_fidelity_review.py",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    # The one provider adapter it experiments on is allowed; the others are not.
    assert "agents/gemini_client.py" in phase["allowed_files"]
    assert "agents/" not in phase["allowed_files"]
    for other_provider in ("agents/deepseek_client.py", "agents/ollama_client.py"):
        assert other_provider in phase["forbidden_files"], other_provider

    for wired in (
        "core/strict_envelope_emission.py",
        "core/run_lifecycle.py",
        "core/replay_recorder.py",
        "core/agent_state.py",
        "core/pipeline.py",
        "core/sleeping_consultant.py",
        "scripts/run_patch_proposal_queue.py",
    ):
        assert wired in phase["allowed_files"], wired
        assert wired not in phase["forbidden_files"], wired


def test_strict_envelope_emission_experiment_documents_its_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["WORKER.DECL.2A.1"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    # What actually changed, and what could not.
    assert "strict_worker_patch_envelope_emission" in summary
    assert "legacy_prompt, strict_prompt and provider_native_json" in summary
    assert "the request is the experimental variable, and the only one" in notes

    # And the things it refuses.
    assert "flag off is argument-identical, not merely equivalent" in notes
    assert "the parser is not weakened to raise the number" in notes
    assert "no second call and no repair turn" in notes
    assert "legacy extraction remains authoritative throughout" in notes
    assert "no threshold yet, on purpose" in notes
    assert "no change intent, no checker promotion" in notes




def test_live_strict_envelope_dogfood_is_registered_as_observation_history():
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A.2"]

    assert phase["track"] == "WORKER"
    assert phase["title"] == "Live Strict Envelope Adoption Dogfood"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_0_OBSERVE"
    assert phase["risk_level"] == "medium"
    assert phase["prerequisites"] == ["WORKER.DECL.2A.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["writes_real_repo"] is False
    for artifact in (
        "docs/designs/2026-08-30-live-strict-envelope-adoption-dogfood.md",
        ".agent/roadmap/strict_emission_dogfood.json",
    ):
        assert artifact in phase["expected_artifacts"], artifact


def test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call():
    """It spends provider calls, and the registry says so in the only way it can.

    ``model_calls_allowed`` is the registry's vocabulary for provider traffic and
    is legal only under the approval budget tier, so a dogfood phase must carry
    both.  ``network_allowed`` stays false because ROAD.1 rejects true outright;
    that flag is not this phase claiming it made no requests.
    """
    data = load_phase_registry(str(_SEED_PATH))
    phases = data["phases"]
    by_id = {phase["phase_id"]: phase for phase in phases}
    phase = by_id["WORKER.DECL.2A.2"]

    assert phase["model_calls_allowed"] is True
    assert phase["budget_tier"] == "strong_model_requires_approval"
    assert phase["requires_sandbox"] is True
    # ROAD.1 forbids raw network access for every managed phase, this one included.
    assert phase["network_allowed"] is False
    assert not validate_phase_registry(data)["errors"]

    # And it really is the first.  The set of phases allowed to spend provider
    # calls is enumerated here, deliberately: a phase that wants provider
    # traffic has to be added to this literal and to pay the approval price
    # below, so it cannot arrive quietly.  PATCH.AUTHOR.LIVE.1 joined on
    # 2026-09-09 with a hard cap of one verification-guided revision per run.
    declared_model_call_phases = {
        "WORKER.DECL.2A.2",
        "WORKER.DECL.2B",
        "PATCH.AUTHOR.LIVE.1",
        # CONTROL.BOOTSTRAP.1 joined on 2026-09-18 with one bootstrap authoring call per fresh request.
        "CONTROL.BOOTSTRAP.1",
        # PLAN.1 exposes one already-authorized planner call and no author call.
        "PATCH.SCOPE.PLAN.1",
        # AUTHOR.STRUCTURAL.1 permits one injected read-only author call.
        "PATCH.AUTHOR.STRUCTURAL.1",
    }
    others = [
        item for item in phases if item["phase_id"] not in declared_model_call_phases
    ]
    assert all(item["model_calls_allowed"] is False for item in others)
    assert all(item["budget_tier"] == "local_only" for item in others)

    # The invariant is not "there are exactly two"; it is "every declarer is
    # named here and every declarer pays".  Asserting both directions means a
    # new phase cannot be added to the set without also being made to pay, and
    # cannot be made to pay without being named.
    spenders = {
        item["phase_id"] for item in phases if item["model_calls_allowed"] is True
    }
    assert spenders == declared_model_call_phases
    for phase_id in sorted(spenders):
        declarer = by_id[phase_id]
        assert declarer["budget_tier"] == "strong_model_requires_approval", phase_id
        assert declarer["human_approval_required"] is True, phase_id
        assert declarer["network_allowed"] is False, phase_id
        assert declarer["merge_allowed"] is False, phase_id


def test_live_strict_envelope_dogfood_changes_no_production_code():
    """An observation phase whose diff is a document, the registry and its tests.

    Nothing WORKER.DECL.2A or WORKER.DECL.2A.1 shipped may be edited here: a
    live adoption number obtained by adjusting the thing being measured would
    describe nothing.
    """
    data = load_phase_registry(str(_SEED_PATH))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = by_id["WORKER.DECL.2A.2"]

    assert phase["allowed_files"] == [
        "docs/designs/2026-08-30-live-strict-envelope-adoption-dogfood.md",
        "docs/roadmap/phase_registry.json",
        "tests/test_phase_registry.py",
        "tests/test_phase_picker.py",
    ]
    for allowed in phase["allowed_files"]:
        assert not allowed.startswith("core/"), allowed
        assert not allowed.startswith("agents/"), allowed
        assert not allowed.startswith("scripts/"), allowed

    for frozen in (
        "core/strict_envelope_emission.py",
        "core/worker_patch_envelope.py",
        "core/json_utils.py",
        "core/prompter.py",
        "core/control_engine.py",
        "core/run_lifecycle.py",
        "core/pipeline.py",
        "core/sleeping_consultant.py",
        "agents/gemini_client.py",
        "scripts/run_patch_proposal_queue.py",
        "tests/test_strict_envelope_emission.py",
        "tests/test_worker_patch_envelope.py",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen


def test_live_strict_envelope_dogfood_reports_observations_not_a_verdict():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["WORKER.DECL.2A.2"]
    summary = phase["summary"].lower()
    notes = " ".join(phase["notes"]).lower()

    # What was actually observed, named with the frozen vocabulary.
    assert "legacy_prompt" in summary
    assert "strict_prompt" in summary
    assert "provider_native_json" in summary
    assert "surrounding_prose_rejected" in summary
    assert "additional calls caused by strict checking is zero" in summary

    # And the powers it declines.
    assert "observation only, and it shows in the diff" in notes
    assert "one call per run, proven at the boundary" in notes
    assert "the observation is tied to the response it describes" in notes
    assert "legacy stayed authoritative with a valid strict parse in hand" in notes
    assert "patch quality is out of scope and stays there" in notes
    assert "no change intent, no parser relaxation, no promotion" in notes
    assert "what the evidence does not cover" in notes

    # No adoption rate is published from a handful of runs: the summary says
    # what happened in each arm and explicitly refuses to derive a policy.
    assert "no threshold, rate or routing policy is derived from it" in summary
    for forbidden in ("percent", "%", "compliance rate", "success rate"):
        assert forbidden not in summary, forbidden


def test_seed_registry_is_conservative():
    """No phase merges or reaches the network, and none writes speculatively.

    A phase may declare model calls, but only by paying the registry's price for
    them: the approval budget tier, which routes it to human approval and out of
    the safe-to-prepare bucket.  A phase cannot quietly grant itself provider
    traffic under ``local_only``.

    ``writes_real_repo`` is the same shape of price.  It is not forbidden - a
    live production fix such as OPS.PATCH.1 genuinely edits shipped runtime
    code, and recording that as observation-only would make the registry lie -
    but it is only ever true for shipped history that already went through
    human approval and still may not merge itself.  That is the rule the
    registry validator enforces at ``core/phase_registry.py``; this asserts the
    seed actually obeys it, so no *proposed* or *active* phase can hold write
    authority over the real worktree.
    """
    data = load_phase_registry(str(_SEED_PATH))
    for phase in data["phases"]:
        assert phase["automation_level"] != "AUTO_4_AUTO_MERGE"
        assert phase["merge_allowed"] is False
        assert phase["network_allowed"] is False
        if phase["writes_real_repo"]:
            assert phase["status"] == "complete", phase["phase_id"]
            assert phase["human_approval_required"] is True, phase["phase_id"]
            assert phase["merge_allowed"] is False, phase["phase_id"]
        if phase["model_calls_allowed"]:
            assert phase["budget_tier"] == "strong_model_requires_approval", (
                phase["phase_id"]
            )
            assert phase["human_approval_required"] is True, phase["phase_id"]
        else:
            assert phase["budget_tier"] == "local_only", phase["phase_id"]
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
        "HARDEN": 16,
        "HUMAN": 5,
        # RETRIEVE.LIVE.* is an ID namespace inside INDEX, not a new track.
        "INDEX": 12,
        "ACQUIRE": 3,
        "CLAIM": 1,
        "EVIDENCE": 2,
        "INPUT": 4,
        "SYNTHESIS": 1,
            "CHECK": 9,
            "CONTROL": 42,
            "WAITER": 5,
        "WORKER": 5,
        "MIRROR": 15,
        "MODEL": 11,
        "OPS": 22,
        "ROAD": 4,
            "UX": 31,
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
    assert "INPUT" in PHASE_ID_PREFIXES
    assert "SYNTHESIS" in PHASE_ID_PREFIXES
    assert "CHECK" in PHASE_ID_PREFIXES
    assert "CONTROL" in PHASE_ID_PREFIXES
    assert "PATCH" in PHASE_ID_PREFIXES
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


def test_pre_execution_change_intent_phase_is_registered_with_frozen_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["WORKER.DECL.2B"]
    assert phase["title"] == "Pre-Execution Change Intent Channel"
    assert phase["track"] == "WORKER"
    assert phase["status"] == "active"
    assert phase["prerequisites"] == ["WORKER.DECL.2A.2"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert "core/post_run_reconciliation.py" in phase["forbidden_files"]
    assert "core/goal_fidelity_review.py" in phase["forbidden_files"]
    summary = phase["summary"]
    assert "same already-scheduled strict worker invocation" in summary
    assert "not evidential independence" in summary
    assert "zero model calls" in summary
    assert "Legacy extraction remains the only executable plan source" in summary


def test_byte_preserving_patch_apply_phase_is_registered_as_a_live_fix():
    """OPS.PATCH.1 is recorded as what it is: a production write-path fix.

    It is the registry's first ``writes_real_repo`` phase, because it is the
    first phase that edited shipped runtime code rather than observing it.
    Recording it as observation-only would misdescribe a live change.
    """
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.PATCH.1"]

    assert phase["title"] == "Byte-Preserving Multi-File Apply & Rollback"
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["CHECK.LIVE.1"]

    # A live fix, not a report: it touches the executor and says so.
    assert phase["writes_real_repo"] is True
    assert "patching/patch_plan_executor.py" in phase["allowed_files"]
    assert "patching/patch_plan_executor.py" in phase["expected_artifacts"]

    # And it still pays every price the registry charges for that.
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert phase["requires_sandbox"] is False


def test_byte_preserving_patch_apply_phase_freezes_everything_but_the_write():
    """Write fidelity only: no authority, policy or matching surface moves."""
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.PATCH.1"]

    for frozen in (
        "core/patch_safety.py",
        "core/repository_path_policy.py",
        "core/validator.py",
        "core/validation_execution.py",
        "core/validation_side_effects.py",
        "core/run_lifecycle.py",
        "core/post_run_reconciliation.py",
        "core/post_run_reconciliation_shadow.py",
        "core/live_worker_declaration.py",
        "core/pre_execution_change_intent.py",
        "patching/patch_engine.py",
        "patching/patch_gates.py",
        "benchmarks/cases/",
        "web/",
        "agents/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen


def test_byte_preserving_patch_apply_phase_states_the_byte_invariant():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.PATCH.1"]
    summary = phase["summary"]
    notes = " ".join(phase["notes"])

    # The defect, in the terms that make it reproducible.
    assert "Path.write_text()" in summary
    assert "os.linesep" in summary
    assert "line-ending-only diff" in summary

    # The invariant, stated in bytes rather than in content.
    assert "restored verbatim on rollback" in summary
    assert "keeps its own newline convention" in summary

    # The things it refused to change, and the honest schema note.
    assert "literal grounding" in summary
    assert "no repository traversal" in summary
    assert "not report-only" in summary
    assert "Registry schema limitation" in notes
    assert "Benchmark blind spot" in notes


def test_validation_recovery_phase_is_registered_as_a_live_fix():
    """OPS.VALIDATE.1 is recorded as what it is: a production validation fix.

    Like OPS.PATCH.1 it writes real repository code, so it pays the registry's
    full price for that - human approval, no merge, no network, no model calls -
    rather than being filed as observation.
    """
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.VALIDATE.1"]

    assert phase["title"] == "Real Repository Validation Recovery"
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["OPS.PATCH.1"]

    assert phase["writes_real_repo"] is True
    for live_file in (
        "core/preflight.py",
        "core/validation_command.py",
        "core/validator.py",
        "core/validation_outcome.py",
    ):
        assert live_file in phase["allowed_files"], live_file
    assert "core/validation_outcome.py" in phase["expected_artifacts"]

    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert phase["requires_sandbox"] is False


def test_validation_recovery_phase_freezes_authority_and_neighbours():
    """Validation is evidence and safety input; it grants nothing."""
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.VALIDATE.1"]

    for frozen in (
        "core/patch_safety.py",
        "core/repository_path_policy.py",
        "core/post_run_reconciliation.py",
        "core/control_engine.py",
        "core/prompter.py",
        "core/indexer.py",
        "core/repo_librarian.py",
        "cli/interactive.py",
        "patching/patch_engine.py",
        "patching/patch_gates.py",
        "benchmarks/cases/",
        "web/",
        "agents/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen


def test_validation_recovery_phase_states_the_three_way_invariant():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.VALIDATE.1"]
    summary = phase["summary"]
    notes = " ".join(phase["notes"])

    # The defect, in the terms that make it reproducible.
    assert "bare PATH pytest" in summary
    assert "arrived as 'validation passed'" in summary
    assert "flat root-level" in summary

    # The invariant, stated as three answers rather than one boolean.
    assert "passed, failed or inconclusive" in summary
    assert "never a test failure nor a pass" in summary
    assert "keep their grounding semantics" in summary

    # The things it refused to change, and the honest schema note.
    assert "byte-exact rollback is unchanged" in summary
    assert "no repository traversal" in summary
    assert "not report-only" in summary
    assert "Registry schema limitation" in notes
    assert "CLI.RUNTIME.1" in notes
    assert "CONTROL.SAFETY.LIVE.1" in notes


def test_control_safety_phase_is_registered_as_a_live_fix():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "CONTROL.SAFETY.LIVE.1"
    ]

    assert phase["title"] == "Localization Rank / Patch Authority Separation"
    assert phase["track"] == "CONTROL"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["OPS.VALIDATE.1"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["budget_tier"] == "local_only"


def test_control_safety_phase_records_authority_and_scope_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "CONTROL.SAFETY.LIVE.1"
    ]
    notes = " ".join(phase["notes"])

    for live_file in (
        "core/control_engine.py",
        "core/pipeline.py",
        "core/postprocess_gates.py",
        "policy/decision_helper.py",
        "tests/test_control_safety_live.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/indexer.py",
        "core/retriever.py",
        "core/validation_outcome.py",
        "core/patch_safety.py",
        "core/context_selection.py",
        "patching/patch_plan_executor.py",
        "benchmarks/cases/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    assert "non-probabilistic and non-authoritative" in notes
    assert "write_authority=false" in notes
    assert "calc.py" in notes
    assert "WAITER.LIVE.1" in notes
    assert "Zero added model calls, network calls or repository traversals" in notes


def test_live_task_shape_routing_phase_is_registered_as_a_live_routing_fix():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["WAITER.LIVE.1"]

    assert phase["title"] == "Live Task-Shape Routing & Change-Need Separation"
    assert phase["track"] == "WAITER"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["CONTROL.SAFETY.LIVE.1"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["budget_tier"] == "local_only"

    summary = phase["summary"]
    # The three shapes it separates, and the boundary it does not cross.
    assert "ANALYSIS, DEFECT_REPAIR and EXPLICIT_CHANGE" in summary
    assert "before patch-localization CONTROL" in summary
    assert "not report-only" in summary


def test_live_task_shape_routing_phase_records_reuse_and_authority_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["WAITER.LIVE.1"]
    notes = " ".join(phase["notes"])

    for live_file in (
        "core/live_task_shape.py",
        "core/live_task_routing.py",
        "core/analysis_evidence.py",
        "core/control_engine.py",
        "core/pipeline.py",
        "web/runner.py",
        "cli/interactive.py",
        "tests/test_waiter_live_routing.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    # The frozen contracts were reused, never edited.
    for frozen in (
        "core/task_shape.py",
        "core/execution_waiter.py",
        "core/capability_requirements.py",
        "core/waiter_receipt.py",
        "core/semantic_waiter.py",
        "core/input_understanding.py",
        "core/explicit_evidence.py",
        "core/preflight.py",
        "core/validation_outcome.py",
        "core/patch_safety.py",
        "patching/patch_plan_executor.py",
        "benchmarks/cases/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    assert "live compatibility adapter" in notes
    assert "model_call_count >= 1" in notes
    assert "change_need_source" in notes
    assert "write_authority=false" in notes
    assert "never an automatic write" in notes
    assert "Zero added model calls, network calls, index builds or graph traversals" in notes
    assert "WORKER.DECL.2B (parked, untouched)" in notes


def test_candidate_sandbox_validation_phase_is_registered_as_a_live_gate():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.PATCH.2"]

    assert phase["title"] == "Explicit-Change Candidate Sandbox Validation"
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["PATCH.BASIS.LIVE.1"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False


def test_candidate_sandbox_validation_phase_records_reuse_and_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["OPS.PATCH.2"]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    for live_file in (
        "core/candidate_sandbox_validation.py",
        "core/pipeline.py",
        "tests/test_candidate_sandbox_validation.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    # The sandbox, the apply primitive, the validation vocabulary and the basis
    # were reused, never edited.
    for frozen in (
        "core/sandbox_self_evolution_runner.py",
        "core/sandbox_runner.py",
        "patching/patch_plan_executor.py",
        "core/validation_outcome.py",
        "core/validation_command.py",
        "core/patch_safety.py",
        "core/patch_basis.py",
        "policy/decision_helper.py",
        "core/indexer.py",
        "core/retriever.py",
        "benchmarks/cases/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "explicit_change_request",
        "candidate_validation",
        "approval_ready",
        "fingerprint",
        "disposable managed sandbox",
        "apply_patch_plan",
        "OPS.VALIDATE.1",
        "legacy_unvalidated",
        "EXEC.AUTH.LIVE.1",
    ):
        assert term in text, term

    assert "no git stash, git reset or git clean" in text.lower()
    assert "passed != write_authority" in text
    assert "Zero added model calls and zero added network calls" in text
    assert "Not report-only" in text
    # This phase does not spawn planning/readiness/closure siblings.
    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden in (
        "OPS.PATCH.2.PLAN",
        "OPS.PATCH.2.READINESS",
        "OPS.PATCH.2.CLOSE",
    ):
        assert forbidden not in ids, forbidden


def test_typed_patch_basis_phase_is_registered_as_the_live_control_fix():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "PATCH.BASIS.LIVE.1"
    ]

    assert phase["title"] == "Typed Patch Basis & Failure-Relevance Binding"
    assert phase["track"] == "CONTROL"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["WAITER.LIVE.1"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["requires_sandbox"] is False


def test_typed_patch_basis_phase_records_binding_scope_and_frozen_boundaries():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "PATCH.BASIS.LIVE.1"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    for live_file in (
        "core/patch_basis.py",
        "core/control_engine.py",
        "core/pipeline.py",
        "policy/decision_helper.py",
        "tests/test_patch_basis_live.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/live_task_shape.py",
        "core/live_task_routing.py",
        "core/preflight.py",
        "core/validation_outcome.py",
        "core/patch_safety.py",
        "core/direct_context_patch_attachment.py",
        "patching/patch_plan_executor.py",
        "patching/patch_gates.py",
        "core/indexer.py",
        "core/retriever.py",
        "benchmarks/cases/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "grounded_defect",
        "explicit_change_request",
        "direct_executed_reference",
        "graph causality",
        "Every replacement target",
        "write_authority=false",
        "Zero added model calls",
        "timeout",
        "not report-only",
    ):
        assert term in text, term


def test_query_symbol_entry_recall_phase_is_registered_as_a_live_fix():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "RETRIEVE.LIVE.2"
    ]

    assert phase["title"] == (
        "Query-to-Symbol Entry Recall & Identifier Decomposition"
    )
    assert phase["track"] == "INDEX"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["RETRIEVE.LIVE.1"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert "not report-only" in phase["summary"]


def test_query_symbol_entry_recall_phase_freezes_ranking_and_authority():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "RETRIEVE.LIVE.2"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    for live_file in (
        "core/identifier_recall.py",
        "core/control_engine.py",
        "reasoning/deep_project_understand.py",
        "tests/test_query_symbol_entry_recall.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/code_dna.py",
        "core/localization_candidate.py",
        "core/treesitter_parse.py",
        "core/indexer.py",
        "core/retriever.py",
        "core/repository_inventory.py",
        "core/context_profiles.py",
        "core/patch_basis.py",
        "core/candidate_sandbox_validation.py",
        "core/live_execution_authorization.py",
        "core/validation_outcome.py",
        "core/validation_command.py",
        "core/validation_execution.py",
        "core/validator.py",
        "core/preflight.py",
        "core/executor.py",
        "core/patch_safety.py",
        "core/pipeline.py",
        "graph/builder.py",
        "graph/weights.py",
        "patching/",
        "policy/",
        "agents/",
        "database/",
        "web/",
        "benchmarks/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "exact_symbol",
        "identifier_token",
        "multi_token_identifier",
        "indentation -> indent",
        "cat does not retrieve concatenate",
        "Call nodes remain structural-only",
        "zero ranking-coefficient changes",
        "zero model calls",
        "zero embedding/vector calls",
        "zero network calls",
        "zero added repository traversal",
        "zero authority change",
        "_classify_indent remains deliberately broken",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "RETRIEVE.LIVE.2.PLAN",
        "RETRIEVE.LIVE.2.READINESS",
        "RETRIEVE.LIVE.2.CLOSE",
    ):
        assert forbidden_phase not in ids


def test_production_query_recall_unification_phase_is_registered_as_live_fix():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "RETRIEVE.LIVE.3"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    assert phase["title"] == "Production Query-Recall Path Unification"
    assert phase["track"] == "INDEX"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["RETRIEVE.LIVE.2"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert "not report-only" in phase["summary"]

    for live_file in (
        "core/identifier_recall.py",
        "core/control_engine.py",
        "tests/test_production_query_recall_path.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/code_dna.py",
        "core/localization_candidate.py",
        "core/treesitter_parse.py",
        "core/indexer.py",
        "core/retriever.py",
        "core/patch_basis.py",
        "core/live_execution_authorization.py",
        "core/pipeline.py",
        "reasoning/deep_project_understand.py",
        "graph/builder.py",
        "graph/weights.py",
        "patching/",
        "policy/",
        "agents/",
        "web/",
        "benchmarks/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "FIRST DIVERGENCE",
        "ONE CANONICAL RAW-QUERY RESOLVER",
        "VISIBLE FACTS",
        "NO NEW MATCHING POWER",
        "NAVIGATION ONLY",
        "zero new morphology rules",
        "_classify_indent",
    ):
        assert term in text, term


def test_answer_entity_grounding_phase_is_registered_as_live_truthfulness_fix():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "ANSWER.GROUND.LIVE.1"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    assert "ANSWER" in PHASE_ID_PREFIXES
    assert phase["title"] == (
        "Repository Entity Claim Grounding & Evidence-Bounded Fallback"
    )
    assert phase["track"] == "CHECK"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["RETRIEVE.LIVE.3"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False

    for live_file in (
        "core/answer_entity_grounding.py",
        "core/agent_state.py",
        "core/session_io.py",
        "cli/interactive.py",
        "main.py",
        "web/runner.py",
        "tests/test_answer_entity_grounding.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/code_dna.py",
        "core/identifier_recall.py",
        "core/localization_candidate.py",
        "core/control_engine.py",
        "core/retriever.py",
        "core/indexer.py",
        "core/repository_inventory.py",
        "core/patch_basis.py",
        "core/live_execution_authorization.py",
        "core/execution_outcome_telemetry.py",
        "core/validation_execution.py",
        "core/executor.py",
        "core/patch_safety.py",
        "patching/",
        "policy/",
        "agents/",
        "database/",
        "graph/",
        "reasoning/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "ENTITY IDENTITY, NOT SEMANTIC TRUTH",
        "CHECK.2 remains unwired",
        "LAST DISPLAY-SAFE BOUNDARY",
        "No new walk",
        "user_supplied_unverified",
        "unverified_model_assertion",
        "Confidence is absent",
        "never silently replaced",
        "authority_effect=none",
        "patch_candidate=null",
        "Historical artifacts are not rewritten",
        "no PLAN, READINESS, or CLOSE siblings",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "ANSWER.GROUND.LIVE.1.PLAN",
        "ANSWER.GROUND.LIVE.1.READINESS",
        "ANSWER.GROUND.LIVE.1.CLOSE",
    ):
        assert forbidden_phase not in ids


def test_answer_symbol_grounding_phase_is_registered_as_live_truthfulness_fix():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "ANSWER.GROUND.LIVE.2"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    assert "ANSWER" in PHASE_ID_PREFIXES
    assert phase["title"] == "Bare Symbol & Qualified Member Claim Grounding"
    assert phase["track"] == "CHECK"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["ANSWER.GROUND.LIVE.1"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False

    for live_file in (
        "core/answer_entity_grounding.py",
        "core/repository_symbol_membership.py",
        "tests/test_answer_symbol_grounding.py",
        "tests/test_answer_entity_grounding.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/code_dna.py",
        "core/identifier_recall.py",
        "core/localization_candidate.py",
        "core/control_engine.py",
        "core/retriever.py",
        "core/indexer.py",
        "core/repository_inventory.py",
        "core/patch_basis.py",
        "core/live_execution_authorization.py",
        "core/validation_execution.py",
        "core/executor.py",
        "core/patch_safety.py",
        "patching/",
        "policy/",
        "agents/",
        "database/",
        "graph/",
        "reasoning/",
        "web/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "ONE BOUNDARY, NOT A SECOND CHECKER",
        "no answer_entity_grounding_v2",
        "ENTITY IDENTITY, NOT SEMANTIC TRUTH",
        "_classify_indent is not fixed here",
        "CHECK.2 remains unwired",
        "FILE AND SYMBOL GROUNDING STAY DISTINCT",
        "never validates OtherClass.method",
        "No new walk",
        "ambiguous_symbol",
        "unverified_model_assertion",
        "Confidence is absent",
        "never silently substitutes another symbol",
        "authority_effect=none",
        "retrieval_effect=none",
        "Historical artifacts are not rewritten",
        "no PLAN, READINESS, or CLOSE siblings",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "ANSWER.GROUND.LIVE.2.PLAN",
        "ANSWER.GROUND.LIVE.2.READINESS",
        "ANSWER.GROUND.LIVE.2.CLOSE",
        "RETRIEVE.LIVE.5",
    ):
        assert forbidden_phase not in ids


def test_bounded_defect_probe_phase_is_registered_as_live_execution_evidence():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "DEFECT.PROBE.LIVE.1"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    assert "DEFECT" in PHASE_ID_PREFIXES
    assert phase["title"] == "Bounded Defect Reproduction Evidence"
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
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
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False

    for live_file in (
        "core/defect_probe.py",
        "core/defect_probe_worker.py",
        "core/control_engine.py",
        "core/patch_basis.py",
        "core/live_task_routing.py",
        "tests/test_defect_probe_live.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/code_dna.py",
        "core/identifier_recall.py",
        "core/localization_candidate.py",
        "core/indexer.py",
        "core/retriever.py",
        "core/validation_outcome.py",
        "core/validation_bytecode_cache.py",
        "core/validation_execution.py",
        "core/preflight.py",
        "core/patch_safety.py",
        "core/executor.py",
        "core/pipeline.py",
        "patching/",
        "policy/",
        "agents/",
        "database/",
        "graph/",
        "reasoning/",
        "web/",
        "benchmarks/cases/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "Whole-repository validation",
        "independently",
        "model_authored",
        "invalid_probe",
        "static worker",
        "validation_budget_exhausted",
        "bounded_defect_reproduction",
        "write_authority=false",
        "T1/T2/T3",
        "observed=4space",
        "expected=2space",
        "_classify_indent remains deliberately unfixed",
        "zero model calls",
        "zero network",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "DEFECT.PROBE.LIVE.1.PLAN",
        "DEFECT.PROBE.LIVE.1.READINESS",
        "DEFECT.PROBE.LIVE.1.CLOSE",
    ):
        assert forbidden_phase not in ids


def test_bounded_targeted_repository_validation_is_registered_as_live_ops():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "OPS.VALIDATE.3"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    assert phase["title"] == "Bounded Targeted Repository Validation"
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["DEFECT.PROBE.LIVE.1"]
    assert phase["requires_sandbox"] is True
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False

    for live_file in (
        "core/targeted_repository_validation.py",
        "core/pipeline.py",
        "cli/interactive.py",
        "tests/test_targeted_repository_validation.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/code_dna.py",
        "core/identifier_recall.py",
        "core/retriever.py",
        "core/validation_outcome.py",
        "core/validation_bytecode_cache.py",
        "core/validation_execution.py",
        "core/preflight.py",
        "core/candidate_sandbox_validation.py",
        "core/live_execution_authorization.py",
        "core/patch_safety.py",
        "core/control_engine.py",
        "core/defect_probe.py",
        "patching/",
        "policy/",
        "agents/",
        "database/",
        "graph/",
        "reasoning/",
        "web/",
        "benchmarks/cases/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "THREE FACTS",
        "no_relevant_existing_checks",
        "selection_budget_exceeded",
        "same check set",
        "selected_validation_check_modified",
        "validation_budget_exhausted",
        "targeted_validation_authority_effect=none",
        "T1/T2/T3",
        "Zero model calls",
        "new repository traversal",
        "global-timeout increase",
        "_classify_indent remains unfixed",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "OPS.VALIDATE.3.PLAN",
        "OPS.VALIDATE.3.READINESS",
        "OPS.VALIDATE.3.CLOSE",
    ):
        assert forbidden_phase not in ids


def test_immutable_candidate_defect_closure_is_registered_as_live_ops():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "DEFECT.PROBE.LIVE.2"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    assert phase["title"] == "Immutable Pre/Post Candidate Reproduction Closure"
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["OPS.VALIDATE.3"]
    assert phase["requires_sandbox"] is True
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False

    for live_file in (
        "core/candidate_defect_probe.py",
        "core/defect_probe.py",
        "core/pipeline.py",
        "tests/test_defect_probe_live.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/code_dna.py",
        "core/candidate_sandbox_validation.py",
        "core/targeted_repository_validation.py",
        "core/validation_bytecode_cache.py",
        "core/validation_execution.py",
        "core/patch_safety.py",
        "core/live_execution_authorization.py",
        "patching/",
        "policy/",
        "agents/",
        "database/",
        "graph/",
        "reasoning/",
        "web/",
        "benchmarks/cases/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "same probe",
        "Probe fingerprints",
        "Candidate fingerprints",
        "patch safety",
        "real patching.patch_plan_executor.apply_patch_plan",
        "model_authored",
        "invalid_comparison",
        "still_reproduced",
        "changed_but_unresolved",
        "inconclusive",
        "targeted failure",
        "full validation",
        "candidate_probe_authority_effect=none",
        "T1/T2/T3",
        "observed=4space",
        "2space",
        "byte-identical",
        "Zero model calls",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "DEFECT.PROBE.LIVE.2.PLAN",
        "DEFECT.PROBE.LIVE.2.READINESS",
        "DEFECT.PROBE.LIVE.2.CLOSE",
    ):
        assert forbidden_phase not in ids


def test_existing_check_oracle_role_is_registered_as_live_ops():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "VALIDATE.ORACLE.LIVE.1"
    ]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    assert "VALIDATE" in PHASE_ID_PREFIXES
    assert phase["title"] == (
        "Existing Check Role & Candidate-Oracle Conflict Classification"
    )
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["DEFECT.PROBE.LIVE.2"]
    assert phase["requires_sandbox"] is False
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False

    for live_file in (
        "core/check_oracle_assessment.py",
        "core/phase_registry.py",
        "core/pipeline.py",
        "tests/test_check_oracle_assessment.py",
        "tests/test_targeted_repository_validation.py",
        "tests/test_defect_probe_live.py",
    ):
        assert live_file in phase["allowed_files"], live_file

    for frozen in (
        "core/code_dna.py",
        "core/identifier_recall.py",
        "core/localization_candidate.py",
        "core/retriever.py",
        "core/targeted_repository_validation.py",
        "core/defect_probe.py",
        "core/candidate_defect_probe.py",
        "core/validation_outcome.py",
        "core/validation_execution.py",
        "core/live_execution_authorization.py",
        "core/execution_outcome_telemetry.py",
        "patching/",
        "policy/",
        "agents/",
        "database/",
        "graph/",
        "reasoning/",
        "web/",
        "benchmarks/cases/",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen

    for term in (
        "check_execution_outcome",
        "defect_preservation_oracle",
        "candidate_regression_oracle",
        "conflict_unresolved",
        "insufficient_basis",
        "Model-only",
        "failed remains failed",
        "not their names",
        "probe fingerprint",
        "candidate-modified",
        "not inconsistent_input",
        "check_oracle_authority_effect=none",
        "T1/T2/T3",
        "Zero model calls",
        "no PLAN, READINESS or CLOSE siblings",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "VALIDATE.ORACLE.LIVE.1.PLAN",
        "VALIDATE.ORACLE.LIVE.1.READINESS",
        "VALIDATE.ORACLE.LIVE.1.CLOSE",
    ):
        assert forbidden_phase not in ids


def test_execution_eligibility_policy_is_registered_as_live_ops():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "EXEC.POLICY.LIVE.1"
    ]

    assert phase["title"] == (
        "Evidence-Bounded Large-Repository Execution Eligibility"
    )
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["VALIDATE.ORACLE.LIVE.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["requires_sandbox"] is False

    for live_file in (
        "core/execution_eligibility_policy.py",
        "core/pipeline.py",
        "tests/test_execution_eligibility_policy.py",
        "tests/test_defect_probe_live.py",
    ):
        assert live_file in phase["allowed_files"]

    for frozen in (
        "core/code_dna.py",
        "core/patch_safety.py",
        "core/defect_probe.py",
        "core/candidate_defect_probe.py",
        "core/targeted_repository_validation.py",
        "core/check_oracle_assessment.py",
        "core/live_execution_authorization.py",
        "core/execution_outcome_telemetry.py",
        "policy/decision_helper.py",
        "patching/",
        "agents/",
        "graph/",
        "web/",
    ):
        assert frozen in phase["forbidden_files"]
        assert frozen not in phase["allowed_files"]

    text = phase["summary"] + " " + " ".join(phase["notes"])
    for term in (
        "full_validation_required",
        "bounded_evidence_human_review",
        "policy_eligible=true != execution_authorized=true",
        "defect_preservation_oracle",
        "candidate_regression_oracle",
        "validation_budget_exhausted",
        "legacy_unassessed",
        "Zero model calls",
        "_classify_indent remains intentionally broken",
        "not report-only",
    ):
        assert term in text

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "EXEC.POLICY.PLAN",
        "EXEC.POLICY.READINESS",
        "EXEC.POLICY.CLOSE",
    ):
        assert forbidden_phase not in ids


def test_human_apply_binding_is_registered_as_live_ops():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "EXEC.APPROVAL.LIVE.1"
    ]

    assert phase["title"] == (
        "Human Apply Binding, Freshness Revalidation & Authorization Handoff"
    )
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["EXEC.POLICY.LIVE.1"]
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is True

    for live_file in (
        "core/human_apply_authorization.py",
        "core/pipeline.py",
        "core/run_lifecycle.py",
        "web/routes/patch_routes.py",
        "web/templates/index.html",
        "tests/test_human_apply_authorization.py",
    ):
        assert live_file in phase["allowed_files"]

    for frozen in (
        "core/code_dna.py",
        "core/patch_safety.py",
        "core/execution_eligibility_policy.py",
        "core/defect_probe.py",
        "core/targeted_repository_validation.py",
        "policy/decision_helper.py",
        "agents/",
        "graph/",
    ):
        assert frozen in phase["forbidden_files"]
        assert frozen not in phase["allowed_files"]

    text = phase["summary"] + " " + " ".join(phase["notes"])
    for term in (
        "live human authority boundary",
        "exact candidate",
        "freshness revalidation",
        "pre-mutation authorization",
        "manual_apply_action",
        "bounded_evidence_human_review",
        "no bounded auto-apply",
        "Zero model calls",
        "Zero network calls",
        "no repository traversal",
        "_classify_indent remains intentionally broken",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "EXEC.APPROVAL.PLAN",
        "EXEC.APPROVAL.READINESS",
        "EXEC.APPROVAL.CLOSE",
    ):
        assert forbidden_phase not in ids


def test_repository_specificity_entry_ordering_is_registered_as_live_ordering_fix():
    data = load_phase_registry(str(_SEED_PATH))
    phase = {item["phase_id"]: item for item in data["phases"]}["RETRIEVE.LIVE.4"]
    text = phase["summary"] + " " + " ".join(phase["notes"])

    assert "RETRIEVE" in PHASE_ID_PREFIXES
    assert phase["title"] == "Repository-Specificity Weighted Entry Ordering"
    # RETRIEVE.* is an ID namespace inside INDEX, not a new track.
    assert phase["track"] == "INDEX"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["ANSWER.GROUND.LIVE.2"]
    assert phase["writes_real_repo"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["requires_sandbox"] is False
    assert phase["budget_tier"] == "local_only"

    for live_file in (
        "core/identifier_recall.py",
        "tests/test_repository_specificity_entry_ordering.py",
        "docs/designs/2026-09-06-repository-specificity-weighted-entry-ordering.md",
    ):
        assert live_file in phase["allowed_files"]

    # The phase must not be able to edit the target it is retrieving, the
    # candidate-eligibility surface, downstream ranking, or authority.
    for frozen in (
        "core/code_dna.py",
        "core/localization_candidate.py",
        "core/treesitter_parse.py",
        "core/patch_basis.py",
        "graph/weights.py",
        "graph/penalty.py",
    ):
        assert frozen in phase["forbidden_files"]
    assert "core/identifier_recall.py" not in phase["forbidden_files"]

    for term in (
        "ordering",
        "repository-local lexical specificity",
        "token_idf",
        "identifier_precision",
        "candidate-level document frequency",
        "matched candidate population before the cap is byte-identical",
        "entry cap of 6",
        "_QUERY_STOP_WORDS is unchanged",
        "no model call",
        "no embedding",
        "no network call",
        "no repository traversal",
        "no persisted index",
        "navigation evidence",
        "intentionally unfixed",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "RETRIEVE.LIVE.4.PLAN",
        "RETRIEVE.LIVE.4.READINESS",
        "RETRIEVE.LIVE.4.CLOSE",
    ):
        assert forbidden_phase not in ids


# PATCH.SCOPE.EXPAND.1 bookkeeping boundary.
def test_structural_scope_expansion_phase_is_bounded_proposal_only():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [item for item in data["phases"]
              if item["phase_id"] == "PATCH.SCOPE.EXPAND.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["merge_allowed"] is False
    assert phase["human_approval_required"] is True
    assert "core/structural_scope_expansion.py" in phase["allowed_files"]
    assert "tests/test_patch_scope_expand1.py" in phase["allowed_files"]
    assert {"OOP.INTENT.DESIGN.1", "OOP.INTENT.DETECT.2",
            "OOP.INTENT.CONTINUE.1", "PATCH.BASIS.SCOPE.1",
            "PATCH.AUTHOR.SCOPE.1", "PATCH.AUTHOR.SPAN.1"} <= set(
                phase["prerequisites"])
    assert {"core/repair_scope.py", "core/authoring_repair_scope.py",
            "core/candidate_replacement_span.py", "bank.java",
            "SavingAccount.java", "agents/", "patching/"} <= set(
                phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    notes = " ".join(phase["notes"])
    for required in ("scope_authority=proposal_only", "write_authority=false",
                     "execution_authorized=false", "candidate=null",
                     "no admission/approval seam", "source layout",
                     "no author/model call", "repository traversal"):
        assert required in notes, required
# End PATCH.SCOPE.EXPAND.1 bookkeeping boundary.


# PATCH.SCOPE.RECHECK.1 bookkeeping boundary.
def test_scope_discovered_semantic_recheck_is_bounded_patch_oop_bridge():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [item for item in data["phases"]
              if item["phase_id"] == "PATCH.SCOPE.RECHECK.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["merge_allowed"] is False
    assert {"PATCH.SCOPE.EXPAND.1", "OOP.INTENT.DESIGN.1", "OOP.INTENT.DETECT.2",
            "OOP.INTENT.CONTINUE.1", "OOP.INTENT.UI.1"} <= set(phase["prerequisites"])
    assert "core/scope_semantic_recheck.py" in phase["allowed_files"]
    assert {"core/repair_scope.py", "core/authoring_repair_scope.py",
            "core/candidate_replacement_span.py", "bank.java", "SavingAccount.java",
            "MainApp.java", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    notes = " ".join(phase["notes"])
    for required in ("scope_authority=proposal_only", "write_authority=false",
                     "execution_authorized=false", "candidate=null", "OOPIntentGap",
                     "implementation_only", "human_owned_material_semantics",
                     "scope refresh required", "no author/model call", "repository traversal"):
        assert required in notes, required
# End PATCH.SCOPE.RECHECK.1 bookkeeping boundary.


# PATCH.SCOPE.REFRESH.1 bookkeeping boundary.
def test_semantic_scope_refresh_is_new_proposal_only_control_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [item for item in data["phases"]
              if item["phase_id"] == "PATCH.SCOPE.REFRESH.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL"
    assert phase["status"] == "complete"
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["budget_tier"] == "local_only"
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["merge_allowed"] is False
    assert phase["human_approval_required"] is True
    assert {"PATCH.SCOPE.EXPAND.1", "PATCH.SCOPE.RECHECK.1",
            "OOP.INTENT.DETECT.2", "OOP.INTENT.CONTINUE.1"} <= set(
                phase["prerequisites"])
    assert "core/structural_scope_refresh.py" in phase["allowed_files"]
    assert "tests/test_patch_scope_refresh1.py" in phase["allowed_files"]
    assert {"core/repair_scope.py", "core/authoring_repair_scope.py",
            "bank.java", "SavingAccount.java", "MainApp.java",
            "patching/", "agents/", "web/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    notes = " ".join(phase["notes"]).lower()
    for required in ("p0 is reconstructed", "new immutable", "proposal_only",
                     "write_authority=false", "candidate=null", "no source edit",
                     "repository traversal"):
        assert required in notes, required
# End PATCH.SCOPE.REFRESH.1 bookkeeping boundary.


# PATCH.SCOPE.APPROVE.1 bookkeeping boundary.
def test_scope_approval_phase_is_evidence_only_control_history():
    data = load_phase_registry(str(_SEED_PATH))
    phase = next(p for p in data["phases"] if p["phase_id"] == "PATCH.SCOPE.APPROVE.1")
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["model_calls_allowed"] is phase["network_allowed"] is phase["merge_allowed"] is False
    assert phase["human_approval_required"] is True
    assert "PATCH.SCOPE.REFRESH.1" in phase["prerequisites"]
    assert "core/structural_scope_approval.py" in phase["allowed_files"]
    assert "bank.java" in phase["forbidden_files"]
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("explicit_human", "proposal_only", "candidate=null", "MAY_REQUIRE_EXISTING_API_CHANGE", "idempotent", "GET is read-only"):
        assert term in " ".join(phase["notes"])
# End PATCH.SCOPE.APPROVE.1 bookkeeping boundary.


# PATCH.SCOPE.PLAN.1 bookkeeping boundary.
def test_plan_phase_is_read_only_planner_harness_boundary():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.SCOPE.PLAN.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "strong_model_requires_approval"
    assert phase["model_calls_allowed"] is phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is False
    assert "PATCH.SCOPE.APPROVE.1" in phase["prerequisites"]
    assert "core/structural_implementation_plan.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "MainApp.java", "core/repair_scope.py",
            "core/authoring_repair_scope.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("read_only_plan", "subset/equal-to", "MAY", "file_creation_authority=false",
                 "zero RepairScope/AuthoringRepairScope delta", "candidate=null", "SCOPE_ADMISSION_NOT_IMPLEMENTED"):
        assert term in " ".join(phase["notes"])
# End PATCH.SCOPE.PLAN.1 bookkeeping boundary.


# PATCH.SCOPE.ADMIT.1 bookkeeping boundary.
def test_admit_phase_is_deterministic_candidate_only_control_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.SCOPE.ADMIT.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "local_only"
    assert phase["model_calls_allowed"] is phase["network_allowed"] is phase["merge_allowed"] is False
    assert phase["human_approval_required"] is True
    assert "PATCH.SCOPE.PLAN.1" in phase["prerequisites"]
    assert "core/structural_scope_admission.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "MainApp.java", "core/repair_scope.py",
            "core/authoring_repair_scope.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("candidate_authoring_only", "subset/equal-to", "Unused MAY", "write_authority=false",
                 "zero RepairScope/AuthoringRepairScope delta", "candidate=null", "author calls=0"):
        assert term in " ".join(phase["notes"])
# End PATCH.SCOPE.ADMIT.1 bookkeeping boundary.


# PATCH.AUTHOR.STRUCTURAL.1 bookkeeping boundary.
def test_structural_author_phase_is_candidate_only_history():
    data = load_phase_registry(str(_SEED_PATH))
    phase = next(p for p in data["phases"] if p["phase_id"] == "PATCH.AUTHOR.STRUCTURAL.1")
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["model_calls_allowed"] is phase["human_approval_required"] is True
    assert phase["budget_tier"] == "strong_model_requires_approval"
    assert phase["network_allowed"] is phase["merge_allowed"] is False
    assert "PATCH.SCOPE.ADMIT.1" in phase["prerequisites"]
    assert "core/structural_patch_author.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "MainApp.java", "core/repair_scope.py",
            "core/authoring_repair_scope.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("candidate_only", "READ-ONLY SUPPORT", "unused MAY", "one-shot", "no real BANK.2",
                 "write_authority=false", "STRUCTURAL_CANDIDATE_MATERIALIZATION_NOT_IMPLEMENTED"):
        assert term in " ".join(phase["notes"])
# End PATCH.AUTHOR.STRUCTURAL.1 bookkeeping boundary.


# PATCH.CANDIDATE.MATERIALIZE.1 bookkeeping boundary.
def test_structural_candidate_materialization_is_virtual_only_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.CANDIDATE.MATERIALIZE.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "local_only"
    assert phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert "PATCH.AUTHOR.STRUCTURAL.1" in phase["prerequisites"]
    assert "core/structural_candidate_materialization.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "MainApp.java", "core/structural_patch_author.py",
            "core/structural_java.py", "core/structural_scope_admission.py", "core/repair_scope.py",
            "core/authoring_repair_scope.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("virtual_post_state_only", "write_authority=false", "Source mutation=0",
                 "model calls=0", "author calls=0", "repository traversal=0", "Harness-owned",
                 "before_sha256=null", "PLAN/admitted", "No candidate repair", "display-only",
                 "validate_materialized_structural_candidate", "synthetic frozen AUTHOR",
                 "STRUCTURAL_CANDIDATE_VALIDATION_NOT_IMPLEMENTED"):
        assert term in " ".join(phase["notes"])
# End PATCH.CANDIDATE.MATERIALIZE.1 bookkeeping boundary.


# PATCH.CANDIDATE.VALIDATE.1A bookkeeping boundary.
def test_structural_candidate_compile_validation_is_diagnostic_only_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.CANDIDATE.VALIDATE.1A"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "local_only" and phase["requires_sandbox"] is True
    assert phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {"PATCH.CANDIDATE.MATERIALIZE.1", "PATCH.AUTHOR.STRUCTURAL.1",
            "PATCH.SCOPE.ADMIT.1", "PREFLIGHT.REQUEST.1"} <= set(phase["prerequisites"])
    assert "core/structural_compile_validation.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "SavingAccountBehaviorTest.java", "MainApp.java",
            "core/structural_candidate_materialization.py", "core/structural_patch_author.py",
            "core/structural_java.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("diagnostic_evidence_only", "write_authority=false", "shell=false", "after_bytes",
                 "SHA-256", "read_only_compile_dependency", "Compile failure != permission to repair",
                 "no real BANK.2", "validate_structural_compile_receipt", "repository traversal=0",
                 "STRUCTURAL_CANDIDATE_BEHAVIORAL_VALIDATION_NOT_IMPLEMENTED"):
        assert term in " ".join(phase["notes"])
# End PATCH.CANDIDATE.VALIDATE.1A bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.SPEC.1 bookkeeping boundary.
def test_behavioral_specification_is_oracle_only_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.CANDIDATE.BEHAVIOR.SPEC.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "local_only" and phase["requires_sandbox"] is False
    assert phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {"PATCH.CANDIDATE.VALIDATE.1A", "PATCH.CANDIDATE.MATERIALIZE.1",
            "PATCH.AUTHOR.STRUCTURAL.1", "PATCH.SCOPE.ADMIT.1", "PATCH.SCOPE.PLAN.1"} <= set(phase["prerequisites"])
    assert "core/behavioral_validation_specification.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "SavingAccountBehaviorTest.java", "MainApp.java",
            "core/structural_compile_validation.py", "core/structural_candidate_materialization.py",
            "core/structural_patch_author.py", "core/structural_java.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("behavioral_oracle_only", "test_write_authority=false", "execution_authorized=false",
                 "write_authority=false", "apply_authority=false", "compile_success=true",
                 "behavior_spec_stale", "implementation_contract", "observation_evidence_missing",
                 "execution_harness_constraint", "Actual javac invocations=0", "java execution=0",
                 "model calls=0", "author calls=0", "repository traversal=0",
                 "STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_PLANNING_NOT_IMPLEMENTED"):
        assert term in " ".join(phase["notes"])
# End PATCH.CANDIDATE.BEHAVIOR.SPEC.1 bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1 bookkeeping boundary.
def test_behavioral_execution_plan_is_bounded_capability_incomplete_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "local_only" and phase["requires_sandbox"] is False
    assert phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {"PATCH.CANDIDATE.BEHAVIOR.SPEC.1", "PATCH.CANDIDATE.VALIDATE.1A",
            "PATCH.CANDIDATE.MATERIALIZE.1", "PATCH.AUTHOR.STRUCTURAL.1",
            "PATCH.SCOPE.ADMIT.1", "PATCH.SCOPE.PLAN.1", "PREFLIGHT.REQUEST.1"} <= set(phase["prerequisites"])
    assert "core/behavioral_evidence_execution_plan.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "SavingAccountBehaviorTest.java", "MainApp.java",
            "core/behavioral_validation_specification.py", "core/structural_compile_validation.py",
            "core/structural_candidate_materialization.py", "core/structural_patch_author.py",
            "core/structural_java.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("COMPLETE_WITH_WARNINGS / FROZEN", "behavioral_execution_plan_only",
                 "validate_behavioral_validation_specification", "compile_success=true", "execution_plan_stale",
                 "java_execution_authorized=false", "reflection_authorized=false", "console_authorized=false",
                 "test_write_authority=false", "write_authority=false", "apply_authority=false",
                 "read_only_reflection", "deterministic_console_input", "redirected stdin",
                 "execution_capability_incomplete", "execution_ready", "ephemeral diagnostic harness",
                 "diagnostic_fixture", "implementation_fixture", "implementation_contract",
                 "validate_behavioral_evidence_execution_plan", "Actual javac invocations=0", "Java execution=0",
                 "model calls=0", "author calls=0", "repository traversal=0",
                 "STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_NOT_IMPLEMENTED"):
        assert term in " ".join(phase["notes"])
# End PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1 bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.REFLECT.1 bookkeeping boundary.
def test_read_only_reflection_is_bounded_diagnostic_capability_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "local_only" and phase["requires_sandbox"] is True
    assert phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1" in phase["prerequisites"]
    assert {"core/read_only_reflection.py", "core/read_only_reflection_java.py"} <= set(phase["allowed_files"])
    assert {"bank.java", "SavingAccount.java", "SavingAccountBehaviorTest.java", "MainApp.java",
            "core/behavioral_evidence_execution_plan.py", "core/behavioral_validation_specification.py",
            "core/structural_java.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("read_exact_bound_field", "ReadOnlyReflectionRequest", "ReadOnlyReflectionObservation",
                 "validate_read_only_reflection_request", "validate_read_only_reflection_observation",
                 "available_but_not_execution_admitted", "product_mutation_authority=false",
                 "source_write_authority=false", "reflection_write_authority=false",
                 "private_method_invocation_authority=false", "arbitrary_member_discovery_authority=false",
                 "BANK_behavioral_java_execution_count=0", "deterministic_console_input remains unavailable",
                 "model calls=0", "author calls=0", "repository traversal=0"):
        assert term in " ".join(phase["notes"])
# End PATCH.CANDIDATE.BEHAVIOR.REFLECT.1 bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1 bookkeeping boundary.
def test_behavioral_execution_admission_is_bounded_authority_classification_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "local_only" and phase["requires_sandbox"] is False
    assert phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {"PATCH.CANDIDATE.BEHAVIOR.REFLECT.1", "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1",
            "PATCH.CANDIDATE.BEHAVIOR.SPEC.1", "PATCH.CANDIDATE.VALIDATE.1A",
            "PATCH.CANDIDATE.MATERIALIZE.1", "PREFLIGHT.REQUEST.1"} <= set(phase["prerequisites"])
    assert "core/behavioral_execution_admission.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "SavingAccountBehaviorTest.java", "MainApp.java",
            "core/behavioral_evidence_execution_plan.py", "core/behavioral_validation_specification.py",
            "core/read_only_reflection.py", "core/read_only_reflection_java.py",
            "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("COMPLETE_WITH_WARNINGS / FROZEN", "BehavioralExecutionAdmission",
                 "diagnostic_behavioral_execution_only", "validate_behavioral_evidence_execution_plan",
                 "read_exact_bound_field", "available_but_not_execution_admitted",
                 "diagnostic_execution_authority_missing", "blocked_authority",
                 "blocked_missing_capability", "static_not_executed", "Partial evidence coverage is valid",
                 "process-local authenticated adapter receipt", "admission_stale",
                 "runtime_executor_capability_missing", "network capability=false",
                 "product_write_authority=false", "repository_write_authority=false",
                 "apply_authority=false", "test_write_authority=false",
                 "reflection_write_authority=false", "console_authorized=false",
                 "diagnostic_harness_generation_authorized=false", "java_execution_authorized=false",
                 "Java execution=0", "reflection execution=0", "console/PTY opened=0",
                 "Actual javac invocations=0", "model calls=0", "author calls=0", "repository traversal=0"):
        assert term in " ".join(phase["notes"])
# End PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1 bookkeeping boundary.


# PREFLIGHT.RUNTIME.1 bookkeeping boundary.
def test_runtime_diagnostic_authorization_is_exact_bounded_policy_history():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PREFLIGHT.RUNTIME.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["budget_tier"] == "local_only" and phase["requires_sandbox"] is False
    assert phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {"PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1", "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1",
            "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1", "PATCH.CANDIDATE.BEHAVIOR.SPEC.1",
            "PREFLIGHT.REQUEST.1", "ACQUIRE.1"} <= set(phase["prerequisites"])
    assert {"core/runtime_diagnostic_authorization.py", "tests/_preflight_runtime1_guard.py"} <= set(phase["allowed_files"])
    assert {"bank.java", "SavingAccount.java", "SavingAccountBehaviorTest.java", "MainApp.java",
            "core/behavioral_execution_admission.py", "core/behavioral_evidence_execution_plan.py",
            "core/behavioral_validation_specification.py", "core/read_only_reflection.py",
            "core/read_only_reflection_java.py", "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("RuntimeDiagnosticAuthorization", "bounded_runtime_diagnostic_only",
                 "Evidence requirement != execution authority", "capability availability != authorization",
                 "authorization != executor availability", "no implied human consent",
                 "validate_runtime_diagnostic_authorization", "read_exact_bound_field",
                 "diagnostic_execution_authority_missing", "authorized_but_executor_unavailable",
                 "runtime_executor_capability_missing", "deterministic_console_input",
                 "repository_write_authority=false", "product_write_authority=false",
                 "reflection_write_authority=false", "test_write_authority=false", "apply_authority=false",
                 "Java execution=0", "reflection execution=0", "compiler execution=0",
                 "Prior EXEC.ADMIT.1 disclosed synthetic verification breach"):
        assert term in " ".join(phase["notes"])
# End PREFLIGHT.RUNTIME.1 bookkeeping boundary.


# PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1 bookkeeping boundary.
def test_behavioral_runtime_executor_remains_blocked_without_required_isolation():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["title"] == "Bounded Ephemeral Java Diagnostic Executor"
    assert phase["track"] == "CONTROL" and phase["status"] == "active"
    assert phase["risk_level"] == "blocked" and phase["budget_tier"] == "local_only"
    assert phase["requires_sandbox"] is True
    assert phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert {"PREFLIGHT.RUNTIME.1", "PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1",
            "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1", "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1",
            "PATCH.CANDIDATE.BEHAVIOR.SPEC.1", "PATCH.CANDIDATE.VALIDATE.1A",
            "PATCH.CANDIDATE.MATERIALIZE.1", "PATCH.AUTHOR.STRUCTURAL.1",
            "EXEC.APPROVAL.LIVE.1"} <= set(phase["prerequisites"])
    assert "core/behavioral_diagnostic_executor.py" in phase["allowed_files"]
    assert {"bank.java", "SavingAccount.java", "SavingAccountBehaviorTest.java", "MainApp.java",
            "core/runtime_diagnostic_authorization.py", "core/behavioral_execution_admission.py",
            "core/behavioral_evidence_execution_plan.py", "core/behavioral_validation_specification.py",
            "core/read_only_reflection.py", "core/read_only_reflection_java.py",
            "core/structural_compile_validation.py", "core/structural_candidate_materialization.py",
            "core/structural_patch_author.py", "core/human_apply_authorization.py",
            "web/", "agents/", "patching/"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("runtime_executor_capability_incomplete", "runtime_executor_available=false",
                 "RuntimeDiagnosticEffectBoundary", "mandatory_enforcement",
                 "filesystem_isolation_unavailable", "network_isolation_unavailable",
                 "environment_isolation_unavailable", "child_process_isolation_unavailable",
                 "validate_runtime_diagnostic_authorization", "BehavioralDiagnosticExecutionReceipt",
                 "validate_behavioral_diagnostic_execution_receipt", "diagnostic_runtime_evidence_only",
                 "executor_authorization_missing", "diagnostic_execution_authority_missing",
                 "deterministic_console_input", "execution_completed=false", "process-local",
                 "no oracle", "write_authority=false", "apply_authority=false", "Java execution=0",
                 "compiler execution=0", "harness generation=0", "repository traversal=0",
                 "model calls=0", "author calls=0", "Historical hashes remain frozen"):
        assert term in " ".join(phase["notes"])
# End PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1 bookkeeping boundary.


# RUNTIME.SANDBOX.1 bookkeeping boundary.
def test_runtime_sandbox_is_measured_complete_without_executor_or_authority_widening():
    data = load_phase_registry(str(_SEED_PATH))
    phases = [p for p in data["phases"] if p["phase_id"] == "RUNTIME.SANDBOX.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert "RUNTIME" in PHASE_ID_PREFIXES
    assert phase["title"] == "Verified OS-Enforced Candidate Runtime Isolation Adapter"
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["risk_level"] == "medium" and phase["budget_tier"] == "local_only"
    assert phase["requires_sandbox"] is phase["human_approval_required"] is True
    assert phase["network_allowed"] is phase["merge_allowed"] is phase["model_calls_allowed"] is False
    assert phase["writes_real_repo"] is False
    assert set(phase["prerequisites"]) == {
        "PREFLIGHT.RUNTIME.1", "PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1",
        "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1", "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1",
        "PATCH.CANDIDATE.BEHAVIOR.SPEC.1", "PATCH.CANDIDATE.VALIDATE.1A",
        "PATCH.CANDIDATE.MATERIALIZE.1", "PATCH.AUTHOR.STRUCTURAL.1"}
    assert {"core/candidate_runtime_sandbox.py", "core/candidate_runtime_sandbox_probe.py",
            "tests/test_runtime_sandbox1.py", "scripts/replay_runtime_sandbox1.py",
            "docs/roadmap/RUNTIME_SANDBOX_1.md", "docs/roadmap/RUNTIME_SANDBOX_1_LOCAL.json",
            "tests/_runtime_sandbox1_maintenance.py", "tests/fixtures/runtime_sandbox1_reversal.json"} <= set(phase["allowed_files"])
    assert {"core/behavioral_diagnostic_executor.py", "core/runtime_diagnostic_authorization.py",
            "core/read_only_reflection.py", "bank.java", "SavingAccount.java",
            "SavingAccountBehaviorTest.java", "MainApp.java", "web/", "agents/", "patching/",
            "docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1_SYNTHETIC.json"} <= set(phase["forbidden_files"])
    assert not set(phase["allowed_files"]) & set(phase["forbidden_files"])
    for term in ("CandidateRuntimeSandboxAdapter", "CandidateRuntimeSandboxDescriptor",
                 "CandidateRuntimeSandboxVerificationReceipt", "CandidateRuntimeSandboxExecutionSpec",
                 "backend_available=true", "backend_verified=true", "sandbox_verified=true",
                 "SANDBOX CAPABILITY != RUNTIME AUTHORITY", "SANDBOX CAPABILITY != EXECUTOR",
                 "actual adversarial local execution", "report-only", "two repetitions",
                 "shell_available=false", "arbitrary_command_authority=false",
                 "repository_write_authority=false", "apply_authority=false",
                 "RUNTIME_SANDBOX_1_COMPLETE_WITH_WARNINGS", "sandbox_output_limit_exceeded",
                 "sandbox_backend_unavailable", "RUNTIME_SANDBOX_1_BLOCKED_BACKEND_UNAVAILABLE",
                 "sandbox_satisfies_executor_boundary", "all eleven mandatory",
                 "BANK execution=0", "behavioral scenario execution=0", "Java candidate execution=0",
                 "model calls=0", "author calls=0", "repository traversal=0",
                 "no resource-exhaustion enforcement claim", "Historical hashes remain frozen",
                 "executor_refresh_and_exact_java_runtime_integration_not_in_this_phase"):
        assert term in " ".join(phase["notes"])
    executor = next(p for p in data["phases"] if p["phase_id"] == "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1")
    assert executor["status"] == "active" and executor["risk_level"] == "blocked"
# End RUNTIME.SANDBOX.1 bookkeeping boundary.
