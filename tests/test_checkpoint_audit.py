"""Tests for ROAD.3 — Post-MODEL Checkpoint Audit (report-only).

ROAD.3 reads the existing roadmap registry, the picker/registry reports, the
generated model-lab and automation-contract artifacts, and the docs, then writes a
deterministic checkpoint audit report. It audits the completed roadmap arc; it does
not choose new work, execute phases, run validation or a benchmark check, call
models or embeddings, contact a network service, run git, apply patches, launch
workers, or promote / merge / block / retrieve lessons.

Covers the prescribed cases:
1.  valid complete registry with no safe candidates produces pass.
2.  registry invalid produces fail.
3.  missing expected phase produces fail.
4.  incomplete expected phase produces fail.
5.  phase picker still has safe_to_prepare > 0 produces fail.
6.  top_recommendation not null produces fail.
7.  missing optional artifact produces warn, not crash.
8.  malformed artifact produces warn.
9.  guardrail true produces fail.
10. artifact guardrail dictionaries are inspected recursively if needed.
11. docs checks detect missing phase mentions.
12. git history check is optional and does not run git.
13. Markdown contains all required sections and boundaries.
14. CLI writes JSON + Markdown.
15. CLI --json prints summary JSON.
16. CLI exits nonzero on fail.
17. CLI exits nonzero on warn unless allow-warnings.
18. deterministic output with fixed report_id/created_at.
19. source artifacts are not modified.
20. source contains no forbidden model/embedding/network/patch/validation/
    benchmark/worker/git/lesson-promotion/merge behavior.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.checkpoint_audit import (
    CHECKPOINT_AUDIT_GUARDRAIL_NOTE,
    DEFAULT_EXPECTED_COMPLETE_PHASES,
    DOC_PHASE_IDS,
    GUARDRAIL_EXECUTION_FIELDS,
    INSPECTED_ARTIFACT_SPECS,
    REPORT_KIND,
    build_checkpoint_audit,
    gather_checkpoint_inputs,
    render_checkpoint_audit_markdown,
    write_checkpoint_audit,
)
import scripts.create_checkpoint_audit as script


# ── synthetic registry builders ────────────────────────────────────────────────

EXPECTED = list(DEFAULT_EXPECTED_COMPLETE_PHASES)


def _phase(pid="ROAD.1", track=None, status="complete", **over) -> dict:
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


def _arc_phases(status_overrides=None, drop=()) -> list:
    status_overrides = status_overrides or {}
    return [
        _phase(pid=pid, status=status_overrides.get(pid, "complete"))
        for pid in EXPECTED
        if pid not in drop
    ]


def _registry(phases=None, **over) -> dict:
    data = {
        "schema_version": "1.0",
        "updated_at": "2026-06-21T00:00:00+00:00",
        "phases": _arc_phases() if phases is None else phases,
    }
    data.update(over)
    return data


# ── synthetic artifact + docs builders ─────────────────────────────────────────

_INERT = {field: False for field in GUARDRAIL_EXECUTION_FIELDS}


def _inert() -> dict:
    return {"guardrails": dict(_INERT)}


def _artifact(kind, *, path=None, optional=True, present=True, artifact="__inert__", load_error="") -> dict:
    if artifact == "__inert__":
        artifact = {"report_kind": kind, **_inert()}
    return {
        "path": path or f".agent/{kind}.json",
        "kind": kind,
        "optional": optional,
        "present": present,
        "artifact": artifact,
        "load_error": load_error,
    }


def _clean_artifacts() -> list:
    return [
        _artifact(kind, path=rel, optional=optional)
        for kind, rel, optional in INSPECTED_ARTIFACT_SPECS
    ]


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
        artifacts=_clean_artifacts(),
        docs=_docs(),
        report_id="r",
        created_at="t",
        repo_path=".",
        registry_path="docs/roadmap/phase_registry.json",
    )
    kwargs.update(over)
    return build_checkpoint_audit(**kwargs)


# ── 1. valid complete registry with no safe candidates → pass ──────────────────

def test_valid_complete_registry_produces_pass():
    report = _build()
    assert report["checkpoint_verdict"] == "pass"
    assert report["blockers"] == []
    assert report["warnings"] == []
    assert report["recommended_next_step"] == "freeze_current_roadmap_and_plan_next_map"
    assert report["registry_valid"] is True
    assert report["safe_to_prepare_count"] == 0
    assert report["top_recommendation"] is None
    assert report["missing_expected_phases"] == []
    assert set(EXPECTED) <= set(report["observed_complete_phases"])
    assert report["report_kind"] == REPORT_KIND == "checkpoint_audit_report"


def test_report_has_all_required_fields():
    report = _build(report_id="rid", created_at="2026-06-21T00:00:00+00:00")
    for key in (
        "report_id",
        "created_at",
        "repo_path",
        "registry_path",
        "phase_count",
        "registry_valid",
        "complete_phase_count",
        "safe_to_prepare_count",
        "top_recommendation",
        "expected_complete_phases",
        "observed_complete_phases",
        "missing_expected_phases",
        "unexpected_incomplete_phases",
        "artifact_checks",
        "guardrail_checks",
        "validation_summary",
        "docs_checks",
        "git_history_checks",
        "warnings",
        "blockers",
        "checkpoint_verdict",
        "recommended_next_step",
        "guardrails",
    ):
        assert key in report, key
    assert report["report_id"] == "rid"
    assert report["created_at"] == "2026-06-21T00:00:00+00:00"
    assert report["phase_count"] == len(EXPECTED)
    assert report["complete_phase_count"] == len(EXPECTED)


def test_validation_summary_fields_present_and_not_run():
    summary = _build()["validation_summary"]
    for key in ("full_pytest_reported", "benchmark_check_reported", "compileall_reported", "source"):
        assert key in summary, key
    # ROAD.3 never runs validation itself; default reports nothing was provided.
    assert summary["full_pytest_reported"] is False
    assert summary["benchmark_check_reported"] is False
    assert summary["compileall_reported"] is False


def test_guardrails_are_all_inert():
    guardrails = _build()["guardrails"]
    assert guardrails == {
        "chooses_work": False,
        "executes_phases": False,
        "model_call_performed": False,
        "embedding_call_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "worker_launch_performed": False,
        "lesson_promotion_performed": False,
        "merge_performed": False,
        "git_command_performed": False,
    }


# ── 2. registry invalid → fail ─────────────────────────────────────────────────

def test_invalid_registry_produces_fail():
    phases = _arc_phases()
    phases[0]["merge_allowed"] = True  # always a ROAD.1 error → invalid registry.
    report = _build(registry_data=_registry(phases=phases))
    assert report["registry_valid"] is False
    assert report["checkpoint_verdict"] == "fail"
    assert report["recommended_next_step"] == "fix_checkpoint_blockers"
    assert report["blockers"]


def test_unreadable_registry_produces_fail():
    report = _build(registry_data=None, registry_load_error="could not read registry at x.json")
    assert report["registry_valid"] is False
    assert report["checkpoint_verdict"] == "fail"
    assert any("registry" in b.lower() for b in report["blockers"])


# ── 3. missing expected phase → fail ───────────────────────────────────────────

def test_missing_expected_phase_produces_fail():
    report = _build(registry_data=_registry(phases=_arc_phases(drop=["MODEL.3"])))
    assert "MODEL.3" in report["missing_expected_phases"]
    assert report["checkpoint_verdict"] == "fail"
    assert any("MODEL.3" in b for b in report["blockers"])


# ── 4. incomplete expected phase → fail ────────────────────────────────────────

def test_incomplete_expected_phase_produces_fail():
    report = _build(
        registry_data=_registry(phases=_arc_phases(status_overrides={"MODEL.3": "proposed"}))
    )
    assert "MODEL.3" in report["missing_expected_phases"]
    assert report["checkpoint_verdict"] == "fail"


# ── 5. picker still has safe_to_prepare > 0 → fail ─────────────────────────────

def test_safe_to_prepare_present_produces_fail():
    phases = _arc_phases() + [_phase(pid="ROAD.4", status="proposed")]
    report = _build(registry_data=_registry(phases=phases))
    assert report["safe_to_prepare_count"] > 0
    assert report["checkpoint_verdict"] == "fail"
    assert any("safe" in b.lower() or "recommend" in b.lower() for b in report["blockers"])


# ── 6. top_recommendation not null → fail ──────────────────────────────────────

def test_top_recommendation_present_produces_fail():
    phases = _arc_phases() + [_phase(pid="ROAD.4", status="proposed")]
    report = _build(registry_data=_registry(phases=phases))
    assert report["top_recommendation"] is not None
    assert report["checkpoint_verdict"] == "fail"


# ── 7. missing optional artifact → warn (not crash) ────────────────────────────

def test_missing_optional_artifact_produces_warn():
    artifacts = _clean_artifacts()
    artifacts[-1]["present"] = False
    artifacts[-1]["artifact"] = None
    report = _build(artifacts=artifacts)
    assert report["checkpoint_verdict"] == "warn"
    assert report["blockers"] == []
    assert report["recommended_next_step"] == "review_checkpoint_warnings"
    assert report["warnings"]
    missing = [c for c in report["artifact_checks"] if c["present"] is False]
    assert missing and missing[0]["warnings"]


def test_missing_optional_artifact_does_not_crash_with_no_artifacts():
    # No artifacts provided at all: every spec is reported missing as a warning.
    report = _build(artifacts=[])
    assert report["checkpoint_verdict"] in {"warn", "pass"}
    assert isinstance(report["artifact_checks"], list)


# ── 8. malformed artifact → warn (skipped) ─────────────────────────────────────

def test_malformed_artifact_produces_warn():
    artifacts = _clean_artifacts()
    artifacts[0]["artifact"] = None
    artifacts[0]["load_error"] = "could not parse JSON: bad token"
    report = _build(artifacts=artifacts)
    assert report["checkpoint_verdict"] == "warn"
    assert report["blockers"] == []
    skipped = [c for c in report["artifact_checks"] if c["loaded"] is False and c["present"]]
    assert skipped and skipped[0]["warnings"]


def test_malformed_non_object_artifact_does_not_crash():
    for bad in ("nope", 5, [], 3.2):
        artifacts = _clean_artifacts()
        artifacts[0]["artifact"] = bad
        report = _build(artifacts=artifacts)
        assert report["checkpoint_verdict"] in {"warn", "fail", "pass"}


# ── 9. guardrail true → fail ───────────────────────────────────────────────────

def test_guardrail_true_in_artifact_produces_fail():
    for field in sorted(GUARDRAIL_EXECUTION_FIELDS):
        artifacts = _clean_artifacts()
        artifacts[0]["artifact"] = {"report_kind": artifacts[0]["kind"], "guardrails": {field: True}}
        report = _build(artifacts=artifacts)
        assert report["checkpoint_verdict"] == "fail", field
        assert any(field in b for b in report["blockers"]), field
        assert report["guardrail_checks"]["all_clear"] is False, field
        breaches = report["guardrail_checks"]["breaches"]
        assert any(b["field"] == field for b in breaches), field


def test_clean_artifacts_report_all_clear():
    report = _build()
    assert report["guardrail_checks"]["all_clear"] is True
    assert report["guardrail_checks"]["breaches"] == []
    for check in report["artifact_checks"]:
        if check["loaded"]:
            assert check["guardrails_ok"] is True


# ── 10. guardrail dictionaries inspected recursively ───────────────────────────

def test_nested_guardrail_true_is_detected():
    artifacts = _clean_artifacts()
    artifacts[0]["artifact"] = {
        "report_kind": artifacts[0]["kind"],
        "deeply": {"nested": {"node": {"network_call_performed": True}}},
    }
    report = _build(artifacts=artifacts)
    assert report["checkpoint_verdict"] == "fail"
    breaches = report["guardrail_checks"]["breaches"]
    assert any(b["field"] == "network_call_performed" for b in breaches)
    assert any("nested" in b.get("location", "") for b in breaches)


def test_guardrail_true_inside_list_is_detected():
    artifacts = _clean_artifacts()
    artifacts[0]["artifact"] = {
        "report_kind": artifacts[0]["kind"],
        "items": [{"ok": True}, {"merge_performed": True}],
    }
    report = _build(artifacts=artifacts)
    assert report["checkpoint_verdict"] == "fail"
    assert any(b["field"] == "merge_performed" for b in report["guardrail_checks"]["breaches"])


def test_guardrail_false_values_are_not_breaches():
    # Only a literal True is a breach; falsey / non-bool values are inert.
    artifacts = _clean_artifacts()
    artifacts[0]["artifact"] = {
        "report_kind": artifacts[0]["kind"],
        "guardrails": {"merge_performed": False, "patch_applied": "no", "push_performed": 0},
    }
    report = _build(artifacts=artifacts)
    assert report["guardrail_checks"]["all_clear"] is True


# ── 11. docs checks detect missing phase mentions ──────────────────────────────

def test_docs_checks_detect_missing_phase_mention():
    # README + roadmap mention everything except MODEL.2.
    present_ids = " ".join(pid for pid in DOC_PHASE_IDS if pid != "MODEL.2")
    report = _build(docs=_docs(readme_text=present_ids, roadmap_text=present_ids))
    docs = report["docs_checks"]
    assert "MODEL.2" in docs["missing_phase_mentions"]
    assert report["checkpoint_verdict"] == "warn"
    assert any("MODEL.2" in w for w in report["warnings"])


def test_docs_checks_full_mention_has_no_doc_warning():
    report = _build()
    docs = report["docs_checks"]
    assert docs["missing_phase_mentions"] == []
    assert set(docs["checked_phase_ids"]) == set(DOC_PHASE_IDS)


def test_docs_checks_records_per_doc_breakdown():
    report = _build()
    docs = report["docs_checks"]
    assert "mentions" in docs
    for pid in DOC_PHASE_IDS:
        assert pid in docs["mentions"]
        assert docs["mentions"][pid]["mentioned"] is True


# ── 12. git history check is optional and does not run git ─────────────────────

def test_git_history_not_checked_by_default():
    report = _build()
    git = report["git_history_checks"]
    assert git["git_history_checked"] is False
    assert git["warnings"]
    assert any("does not run git" in w for w in git["warnings"])
    # The git boundary is by-design and must NOT block or degrade a clean pass.
    assert report["checkpoint_verdict"] == "pass"
    assert report["guardrails"]["git_command_performed"] is False


def test_git_history_optional_supplied_metadata_is_recorded():
    report = _build(git_history={"source": "supplied log text", "git_history_checked": True})
    git = report["git_history_checks"]
    # Even when metadata is supplied, ROAD.3 does not itself run git.
    assert git["source"] == "supplied log text"
    assert report["guardrails"]["git_command_performed"] is False


# ── 13. Markdown contains all required sections and boundaries ──────────────────

def test_markdown_contains_all_sections():
    md = render_checkpoint_audit_markdown(_build())
    assert "# Post-MODEL Checkpoint Audit" in md
    low = md.lower()
    for section in (
        "## summary",
        "## phase registry check",
        "## phase picker check",
        "## artifact checks",
        "## guardrail checks",
        "## validation summary",
        "## documentation checks",
        "## git history check",
        "## warnings",
        "## blockers",
        "## recommended next step",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    low = render_checkpoint_audit_markdown(_build()).lower()
    assert "does not choose new work" in low
    assert "does not execute phases" in low
    assert "does not run validation or benchmarks" in low
    assert "does not call models or embeddings" in low
    assert "does not contact network services" in low
    assert "does not run git" in low
    assert "does not apply patches" in low
    assert "does not launch workers" in low
    assert "promote, merge, block, or retrieve lessons" in low
    assert "checkpoint audit only" in low


def test_markdown_shows_verdict_and_blockers():
    phases = _arc_phases()
    phases[0]["merge_allowed"] = True
    md = render_checkpoint_audit_markdown(_build(registry_data=_registry(phases=phases))).lower()
    assert "fail" in md


# ── 14-17. CLI behaviour ───────────────────────────────────────────────────────

def _write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _seed_repo(tmp_path: Path, *, include_optional=False, docs_ids=None) -> Path:
    """Write a minimal repo: a complete-arc registry, clean artifacts, full docs."""
    repo = tmp_path / "repo"
    (repo / "docs" / "roadmap").mkdir(parents=True, exist_ok=True)
    _write_json(repo / "docs" / "roadmap" / "phase_registry.json", _registry())

    for kind, rel, _opt in INSPECTED_ARTIFACT_SPECS:
        if not include_optional:
            continue
        _write_json(repo / rel, {"report_kind": kind, **_inert()})

    ids = " ".join(docs_ids if docs_ids is not None else DOC_PHASE_IDS)
    (repo / "README.md").write_text(ids, encoding="utf-8")
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-07.md").write_text(
        ids, encoding="utf-8"
    )
    return repo


def test_cli_writes_json_and_markdown(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=True)
    out = tmp_path / "out"
    res = script.run_create_checkpoint_audit(
        repo_path=str(repo),
        registry=str(repo / "docs" / "roadmap" / "phase_registry.json"),
        output_root=str(out),
        report_id="cli",
        created_at="2026-06-21T00:00:00+00:00",
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "checkpoint_audit_report.json"
    assert mp.name == "checkpoint_audit_report.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["report_id"] == "cli"
    assert data["checkpoint_verdict"] == "pass"


def test_cli_json_flag_prints_summary(tmp_path, capsys):
    repo = _seed_repo(tmp_path, include_optional=True)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "j",
        "--created-at", "t",
        "--json",
    ])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "j"
    assert printed["report_kind"] == "checkpoint_audit_report"
    assert printed["checkpoint_verdict"] == "pass"


def test_cli_exits_zero_on_pass(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=True)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
    ])
    assert code == 0


def test_cli_exits_nonzero_on_fail(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=True)
    # Corrupt the registry so it is invalid → fail.
    phases = _arc_phases()
    phases[0]["merge_allowed"] = True
    _write_json(repo / "docs" / "roadmap" / "phase_registry.json", _registry(phases=phases))
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
    ])
    assert code != 0
    assert (out / "checkpoint_audit_report.json").is_file()


def test_cli_exits_nonzero_on_warn_without_allow(tmp_path):
    # Optional artifacts are absent → warn → nonzero without --allow-warnings.
    repo = _seed_repo(tmp_path, include_optional=False)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
    ])
    assert code != 0
    data = json.loads((out / "checkpoint_audit_report.json").read_text(encoding="utf-8"))
    assert data["checkpoint_verdict"] == "warn"


def test_cli_allow_warnings_returns_zero(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=False)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
        "--allow-warnings",
    ])
    assert code == 0
    data = json.loads((out / "checkpoint_audit_report.json").read_text(encoding="utf-8"))
    assert data["checkpoint_verdict"] == "warn"


def test_cli_expected_phase_override(tmp_path):
    # Drop MODEL.3 from the registry, but only expect ROAD.1 → still passes.
    repo = _seed_repo(tmp_path, include_optional=True)
    _write_json(
        repo / "docs" / "roadmap" / "phase_registry.json",
        _registry(phases=_arc_phases(drop=["MODEL.3"])),
    )
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
        "--expected-phase", "ROAD.1",
        "--expected-phase", "ROAD.2",
    ])
    assert code == 0
    data = json.loads((out / "checkpoint_audit_report.json").read_text(encoding="utf-8"))
    assert set(data["expected_complete_phases"]) == {"ROAD.1", "ROAD.2"}
    assert data["missing_expected_phases"] == []


def test_cli_missing_registry_is_fail(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=True)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "nope.json"),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
    ])
    assert code != 0
    data = json.loads((out / "checkpoint_audit_report.json").read_text(encoding="utf-8"))
    assert data["registry_valid"] is False
    assert data["checkpoint_verdict"] == "fail"


# ── 18. deterministic output ───────────────────────────────────────────────────

def test_report_bytes_are_deterministic(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=True)

    def run(name: str) -> str:
        res = script.run_create_checkpoint_audit(
            repo_path=str(repo),
            registry=str(repo / "docs" / "roadmap" / "phase_registry.json"),
            output_root=str(tmp_path / name),
            report_id="fixed",
            created_at="2026-06-21T12:00:00+00:00",
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


def test_builder_is_deterministic():
    assert build_checkpoint_audit(
        registry_data=_registry(), artifacts=_clean_artifacts(), docs=_docs(),
        report_id="r", created_at="t",
    ) == build_checkpoint_audit(
        registry_data=_registry(), artifacts=_clean_artifacts(), docs=_docs(),
        report_id="r", created_at="t",
    )


# ── 19. source artifacts are not modified ──────────────────────────────────────

def test_build_does_not_mutate_inputs():
    registry = _registry()
    artifacts = _clean_artifacts()
    docs = _docs()
    snap = copy.deepcopy([registry, artifacts, docs])
    build_checkpoint_audit(
        registry_data=registry, artifacts=artifacts, docs=docs, report_id="r", created_at="t"
    )
    assert [registry, artifacts, docs] == snap


def test_cli_does_not_modify_registry_or_artifacts(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=True)
    reg_path = repo / "docs" / "roadmap" / "phase_registry.json"
    before = {
        reg_path: reg_path.read_bytes(),
    }
    for _kind, rel, _opt in INSPECTED_ARTIFACT_SPECS:
        p = repo / rel
        before[p] = p.read_bytes()
    out = tmp_path / "out"
    script.main([
        "--repo-path", str(repo),
        "--registry", str(reg_path),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
        "--allow-warnings",
    ])
    for path, content in before.items():
        assert path.read_bytes() == content, path


# ── gather + write helpers ─────────────────────────────────────────────────────

def test_gather_checkpoint_inputs_tolerates_missing(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=False)
    inputs = gather_checkpoint_inputs(
        str(repo), str(repo / "docs" / "roadmap" / "phase_registry.json")
    )
    assert isinstance(inputs["registry_data"], dict)
    assert len(inputs["artifacts"]) == len(INSPECTED_ARTIFACT_SPECS)
    # All optional artifacts are absent in this repo.
    assert all(a["present"] is False for a in inputs["artifacts"])
    assert isinstance(inputs["docs"], list) and inputs["docs"]


def test_gather_skips_malformed_artifact(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=True)
    # Corrupt one artifact file.
    bad = repo / INSPECTED_ARTIFACT_SPECS[0][1]
    bad.write_text("{not json", encoding="utf-8")
    inputs = gather_checkpoint_inputs(
        str(repo), str(repo / "docs" / "roadmap" / "phase_registry.json")
    )
    corrupt = [a for a in inputs["artifacts"] if a["present"] and a["artifact"] is None]
    assert corrupt and corrupt[0]["load_error"]


def test_write_checkpoint_audit_core(tmp_path):
    repo = _seed_repo(tmp_path, include_optional=True)
    out = tmp_path / "core_out"
    res = write_checkpoint_audit(
        str(repo),
        str(repo / "docs" / "roadmap" / "phase_registry.json"),
        str(out),
        report_id="cr",
        created_at="t",
    )
    assert res["ok"] is True
    assert Path(res["json_path"]).is_file()
    assert Path(res["md_path"]).is_file()
    assert res["report"]["report_id"] == "cr"


# ── constants + guardrail note ─────────────────────────────────────────────────

def test_default_expected_phases_constant():
    assert DEFAULT_EXPECTED_COMPLETE_PHASES == (
        "ROAD.1", "ROAD.2", "AUTO.2a", "AUTO.2b", "AUTO.2c", "MODEL.1", "MODEL.2", "MODEL.3",
    )


def test_doc_phase_ids_include_road3():
    assert "ROAD.3" in DOC_PHASE_IDS
    assert set(DEFAULT_EXPECTED_COMPLETE_PHASES) <= set(DOC_PHASE_IDS)


def test_guardrail_execution_fields_match_spec():
    assert GUARDRAIL_EXECUTION_FIELDS == frozenset({
        "model_call_performed",
        "model_api_call_performed",
        "llm_call_performed",
        "embedding_call_performed",
        "network_call_performed",
        "database_write_performed",
        "patch_applied",
        "patch_applied_to_real_repo",
        "validation_run",
        "validation_run_by_tool",
        "benchmark_run",
        "benchmark_run_by_tool",
        "worker_launch_performed",
        "merge_performed",
        "push_performed",
        "pr_created",
        "branch_created",
        "github_contacted",
        "telegram_message_sent",
        "n8n_contacted",
        "lesson_promotion_performed",
        "lesson_merge_performed",
        "lesson_block_performed",
        "lesson_retrieval_changed",
        "prompt_injection_changed",
        "live_routing_performed",
        "driver_override_performed",
    })


def test_inspected_artifact_specs_cover_inputs():
    paths = {rel for _kind, rel, _opt in INSPECTED_ARTIFACT_SPECS}
    assert ".agent/roadmap/phase_registry_report.json" in paths
    assert ".agent/roadmap/phase_picker_report.json" in paths
    assert ".agent/automation_contracts/telegram_evidence_contract.json" in paths
    assert ".agent/automation_contracts/github_pr_safety_contract.json" in paths
    assert ".agent/automation_contracts/n8n_orchestration_dry_run.json" in paths
    assert ".agent/model_lab/artifact_dataset/artifact_dataset_report.json" in paths
    assert ".agent/model_lab/driver_classifier_baseline/driver_classifier_baseline_report.json" in paths
    assert ".agent/model_lab/lesson_activation_dataset/lesson_activation_dataset_report.json" in paths
    # Every inspected artifact is optional (missing → warn, never a crash).
    assert all(opt is True for _kind, _rel, opt in INSPECTED_ARTIFACT_SPECS)


def test_guardrail_note_is_report_only():
    assert "report-only" in CHECKPOINT_AUDIT_GUARDRAIL_NOTE.lower()
    assert _build()["guardrail_note"] == CHECKPOINT_AUDIT_GUARDRAIL_NOTE


# ── 20. forbidden-token / import guards (source-only) ──────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "checkpoint_audit.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_checkpoint_audit.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_or_phase_modules():
    allowed_top = {"__future__", "json", "pathlib", "typing", "core"}
    allowed_core = {"core.phase_picker", "core.phase_registry"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            if top == "core":
                assert module in allowed_core, f"ROAD.3 may only import {allowed_core}, got {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_model_clients():
    for bad in (
        "anthropic", "openai", "litellm", "ollama", "bedrock", "generativeai",
        "claude", "codex", "gemini", "deepseek", "call_model(", "launch_model(",
    ):
        assert bad not in _BOTH, f"Found model client token {bad!r}"


def test_no_embedding_calls():
    for bad in ("embeddings.create", "embed_query(", "get_embedding(", "OpenAIEmbeddings", ".embed("):
        assert bad not in _BOTH, f"Found embedding-call token {bad!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "check_output", "check_call", "shutil", "copytree"):
        assert bad not in _BOTH, f"Found execution primitive token {bad!r}"


def test_no_validation_or_benchmark_execution():
    for bad in (
        "run_safe_validation", "SafeValidationCommand", "validation_execution",
        "run_benchmarks", "create_managed_sandbox", "apply_candidate_in_sandbox",
    ):
        assert bad not in _BOTH, f"Found validation/benchmark execution token {bad!r}"


def test_no_patch_generation_or_apply():
    for bad in ("generate_patch", "apply_patch(", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_database_writes():
    for bad in ("sqlite3", "psycopg", "pymongo", "INSERT INTO", "cursor(", "vector_db", "vectordb"):
        assert bad not in _BOTH, f"Found database token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_network_send_or_git_behaviour():
    # Bare "n8n"/"telegram"/"github"/"git" are required field / path identifiers in
    # the inspected-artifact specs and guardrail field names; only the *call /
    # command / API* shapes are forbidden.
    for bad in (
        "requests", "httpx", "urllib", "socket", "aiohttp", "webhook",
        "api.telegram.org", "sendMessage", "send_message(", "bot_token",
        "api.github.com", "PyGithub", "from github", "import github", "gh pr",
        "n8n.cloud", "n8n.io", "execute_workflow(",
        "git push", "git checkout", "git branch", "git commit", "git merge",
        "git clone", "git log", "git status", "git_command(",
    ):
        assert bad not in _BOTH, f"Found network/send/git token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson", "block_lesson", "create_merge"):
        assert bad not in _BOTH, f"Found lesson/merge token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "launch_worker(", "worker_launch(", "spawn_worker", "run_worker("):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"
