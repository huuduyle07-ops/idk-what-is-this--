"""Tests for MODEL.1 — C.A.T.T.U.S Artifact Dataset Builder (report-only).

MODEL.1 scans existing C.A.T.T.U.S artifacts under ``.agent`` and normalizes
each one into a stable dataset row for future model / classifier experiments.
It builds data only: it does not train or call models, does not call embeddings,
does not write to a database, does not apply patches, does not run validation or
a benchmark check, does not launch workers, and does not contact Telegram,
GitHub, n8n, or any network service. Dataset rows are advisory artifacts only and
grant no execution authority.

Covers the prescribed cases:
1.  missing .agent directory produces an empty dataset with a warning, not a crash.
2.  a goal brief artifact becomes a normalized row.
3.  a worker assignment artifact becomes a normalized row.
4.  a driver decision artifact captures the recommended vehicle.
5.  a visual evidence contract captures visual policy features.
6.  a self-evolution evidence pack captures the final verdict and next step.
7.  a Telegram evidence contract captures a remote-safety-policy row.
8.  a GitHub PR safety contract captures a remote-safety-policy row.
9.  an n8n dry run captures an orchestration-safety row.
10. a lesson teaching card becomes a lesson_teaching row.
11. malformed JSON is skipped with a warning.
12. an unknown / partial artifact produces a best-effort row.
13. row ids are deterministic.
14. JSONL output is deterministic with fixed report_id / created_at.
15. report counts by kind / task / risk / target label are correct.
16. the include-kind filter works.
17. the limit works deterministically.
18. source artifacts are not modified.
19. Markdown contains all required sections and boundaries.
20. CLI writes JSONL + JSON + Markdown.
21. CLI --json prints summary JSON.
22. source contains no forbidden model / training / embedding / network / patch /
    validation / benchmark / worker / DB / merge behavior.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.artifact_dataset_builder import (
    ARTIFACT_DATASET_GUARDRAIL_NOTE,
    ARTIFACT_KINDS,
    AUTOMATION_LEVELS,
    DATASET_TASKS,
    JSONL_NAME,
    REPORT_JSON_NAME,
    REPORT_KIND,
    REPORT_MD_NAME,
    RISK_LEVELS,
    normalize_artifact,
    render_artifact_dataset_markdown,
    scan_artifacts,
    write_artifact_dataset,
)
import scripts.build_artifact_dataset as script


# ── synthetic artifact builders (modeled on the real producers) ─────────────────

def _goal_brief(**over) -> dict:
    data = {
        "goal": "My hard TypeScript benchmark case failed",
        "problem_type": "",
        "status": "draft",
        "evidence": {"command_run": "", "changed_files": []},
        "constraints": {"allowed_files": [], "forbidden_files": []},
        "validation": {"command": "npm test", "success_criteria": "tests pass"},
        "missing_information": ["problem_type"],
        "created_at": "2026-05-25T16:37:41+00:00",
        "updated_at": "2026-05-25T16:37:41+00:00",
    }
    data.update(over)
    return data


def _worker_assignment(**over) -> dict:
    data = {
        "assignment_id": "2026-06-16t04-59-54z-test-mayor-mode-smoke-flow",
        "title": "Test Mayor Mode smoke flow",
        "mode": "Debug",
        "worker_role": "implementer",
        "created_at": "2026-06-16T04:59:54Z",
        "allowed_files": [],
        "forbidden_files": [".env", ".agent", ".git"],
        "apply_allowed": False,
        "patch_applied": False,
        "validation_run": False,
        "validation_commands": ["python -m pytest -q"],
        "worker_launch_allowed": False,
        "human_approval_required": True,
        "model_call_performed": False,
        "source_type": "goal_brief",
    }
    data.update(over)
    return data


def _driver_decision(**over) -> dict:
    data = {
        "driver_decision_id": "2026-06-16t05-00-00z-test-driver-decision",
        "created_at": "2026-06-16T05:00:00Z",
        "source_type": "worker_assignment",
        "title": "Test Mayor Mode smoke flow",
        "mode": "Debug",
        "worker_role": "implementer",
        "recommended_vehicle": "cheap_api_ok",
        "approval_required": True,
        "blocked": False,
        "reasons": ["debug task with narrow scope"],
        "risk_flags": [],
        "model_call_performed": False,
        "worker_launch_performed": False,
        "patch_applied": False,
        "validation_run": False,
    }
    data.update(over)
    return data


def _visual_evidence(**over) -> dict:
    data = {
        "visual_evidence_id": "2026-06-16t05-01-00z-visual-evidence",
        "created_at": "2026-06-16T05:01:00Z",
        "source_type": "goal_brief",
        "title": "Button misaligned on settings page",
        "visual_evidence_present": False,
        "visual_evidence_referenced": True,
        "visual_verification_required": True,
        "risk_flags": ["visual_verification_required"],
    }
    data.update(over)
    return data


def _worker_result_review(**over) -> dict:
    data = {
        "review_id": "2026-06-16t05-02-00z-worker-result-review",
        "created_at": "2026-06-16T05:02:00Z",
        "source_type": "worker_result_review",
        "review_status": "pending_review",
        "trust_level": "untrusted",
        "human_review_required": True,
        "risk_flags": ["worker_result_untrusted", "security_sensitive_claim"],
        "claimed_validation_commands": ["python -m pytest -q"],
        "claimed_validation_passed": False,
        "recommended_next_actions": ["human_review_required"],
        "eligible_for_proposal_import": False,
    }
    data.update(over)
    return data


def _flaky_case_review(**over) -> dict:
    data = {
        "report_kind": "flaky_case_review",
        "source_report_path": ".agent/benchmarks/benchmark_report_1781584091.json",
        "summary": {
            "total_cases_read": 54,
            "flaky_cases_found": 3,
            "high_confidence_count": 2,
            "source_report_modified": False,
        },
        "flaky_cases": [{"name": "cpp_string_view_lifetime_trap", "attempts": 2}],
    }
    data.update(over)
    return data


def _evidence_pack(**over) -> dict:
    data = {
        "report_kind": "sandbox_self_evolution_evidence_pack",
        "pack_id": "auto1f_smoke_evidence",
        "created_at": "2026-06-18T00:00:00+00:00",
        "trial_id": "auto1f_smoke",
        "final_verdict": "ready_for_human_review",
        "recommended_next_step": "review_patch_candidate",
        "risk_summary": {
            "safety": "no hard safety breach detected",
            "scope": "patch touches 1 file(s)",
            "validation": "declared validation ran in the sandbox",
            "side_effects": "sandbox-only",
            "human_gate": "intact",
        },
        "summary": {"human_review_required": True},
        "source_artifacts": [{"kind": "graduation_review"}],
        "missing_artifacts": [],
    }
    data.update(over)
    return data


def _telegram_contract(**over) -> dict:
    data = {
        "report_kind": "telegram_evidence_contract",
        "contract_id": "smoke",
        "created_at": "2026-06-19T00:00:00+00:00",
        "trial_id": "auto1f_smoke",
        "final_verdict": "ready_for_human_review",
        "recommended_next_step": "review_patch_candidate",
        "risk_summary": {"validation": "declared validation ran in the sandbox"},
        "guardrails": {"human_review_required": True, "telegram_message_sent": False},
        "approval_options": ["review", "defer", "reject"],
        "forbidden_actions": ["approve_merge", "push", "merge"],
        "boundaries": {"sends_messages": False, "is_merge_authority": False},
    }
    data.update(over)
    return data


def _github_contract(**over) -> dict:
    data = {
        "report_kind": "github_pr_safety_contract",
        "contract_id": "gh_smoke",
        "created_at": "2026-06-19T00:00:00+00:00",
        "trial_id": "auto1f_smoke",
        "final_verdict": "ready_for_human_review",
        "recommended_next_step": "review_patch_candidate",
        "risk_summary": {"validation": "declared validation ran in the sandbox"},
        "guardrails": {"human_review_required": True, "github_contacted": False},
        "blockers": [],
        "forbidden_actions": ["merge", "push", "enable_auto_merge"],
    }
    data.update(over)
    return data


def _n8n_dry_run(**over) -> dict:
    data = {
        "report_kind": "n8n_orchestration_dry_run",
        "dry_run_id": "n8n_smoke",
        "created_at": "2026-06-19T00:00:00+00:00",
        "trial_id": "auto1f_smoke",
        "overall_verdict": "dry_run_ready_for_human_review",
        "detected_sources": ["self_evolution_evidence_pack"],
        "risk_summary": {"validation": "declared validation ran in the sandbox"},
        "guardrails": {"human_review_required": True, "n8n_contacted": False},
        "is_live_execution_allowed": False,
    }
    data.update(over)
    return data


def _phase_registry_report(**over) -> dict:
    data = {
        "report_kind": "phase_registry_report",
        "report_id": "reg_smoke",
        "created_at": "2026-06-19T00:00:00+00:00",
        "registry_path": "docs/roadmap/phase_registry.json",
        "is_valid": True,
        "phase_count": 8,
        "counts_by_status": {"complete": 5, "proposed": 3},
    }
    data.update(over)
    return data


def _phase_picker_report(**over) -> dict:
    data = {
        "report_kind": "phase_picker_report",
        "report_id": "pick_smoke",
        "created_at": "2026-06-19T00:00:00+00:00",
        "registry_path": "docs/roadmap/phase_registry.json",
        "registry_valid": True,
        "top_recommendation": {"phase_id": "MODEL.1", "recommended_next_step": "prepare_worker_assignment"},
        "bucket_counts": {"safe_to_prepare": 3},
    }
    data.update(over)
    return data


def _teaching_card(**over) -> dict:
    data = {
        "teaching_card_id": "2026-06-16t05-03-00z-teaching-card",
        "created_at": "2026-06-16T05:03:00Z",
        "source_type": "lesson",
        "title": "Lesson: keep patches minimal",
        "summary": "Minimal patches are easier to review and safer to apply.",
        "related_artifacts": [".agent/lessons/x.json"],
        "human_review_recommended": True,
    }
    data.update(over)
    return data


# ── repo helpers ────────────────────────────────────────────────────────────────

#: kind -> (relative artifact path under the repo, synthetic builder).
_KIND_FIXTURES = {
    "goal_brief": (".agent/goal_briefs/20260525/goal_brief.json", _goal_brief),
    "worker_assignment": (".agent/worker_assignments/wa1/worker_assignment.json", _worker_assignment),
    "driver_decision": (".agent/driver_decisions/dd1/driver_decision.json", _driver_decision),
    "visual_evidence_contract": (".agent/visual_evidence/v1/visual_evidence_contract.json", _visual_evidence),
    "worker_result_review": (".agent/worker_result_reviews/wr1/worker_result_review.json", _worker_result_review),
    "flaky_case_review": (".agent/reliability/flaky_case_reviews/f1/flaky_case_review.json", _flaky_case_review),
    "self_evolution_evidence_pack": (".agent/self_evolution_trials/t1/self_evolution_evidence_pack.json", _evidence_pack),
    "telegram_evidence_contract": (".agent/automation_contracts/telegram_evidence_contract.json", _telegram_contract),
    "github_pr_safety_contract": (".agent/automation_contracts/github_pr_safety_contract.json", _github_contract),
    "n8n_orchestration_dry_run": (".agent/automation_contracts/n8n_orchestration_dry_run.json", _n8n_dry_run),
    "phase_registry_report": (".agent/roadmap/phase_registry_report.json", _phase_registry_report),
    "phase_picker_report": (".agent/roadmap/phase_picker_report.json", _phase_picker_report),
    "teaching_card": (".agent/teaching_cards/c1/teaching_card.json", _teaching_card),
}


def _write_json(repo: Path, rel: str, data) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _populate(repo: Path, kinds) -> None:
    for kind in kinds:
        rel, builder = _KIND_FIXTURES[kind]
        _write_json(repo, rel, builder())


def _row_by_kind(rows, kind):
    for row in rows:
        if row["artifact_kind"] == kind:
            return row
    raise AssertionError(f"no row for kind {kind!r}")


# ── 1. missing .agent → empty dataset + warning ─────────────────────────────────

def test_missing_agent_directory_produces_empty_dataset_with_warning(tmp_path):
    out = tmp_path / "out"
    result = write_artifact_dataset(
        str(tmp_path), str(out), report_id="r", created_at="t"
    )
    assert result["ok"] is True
    assert result["report"]["row_count"] == 0
    assert result["report"]["warnings"]  # at least one warning, no crash
    assert Path(result["jsonl_path"]).is_file()
    assert Path(result["jsonl_path"]).read_text(encoding="utf-8") == ""


# ── 2-10, 12. per-kind normalization ───────────────────────────────────────────

def test_goal_brief_becomes_normalized_row():
    row = normalize_artifact(
        "goal_brief", _goal_brief(), artifact_path=".agent/goal_briefs/x/goal_brief.json"
    )
    assert row["artifact_kind"] == "goal_brief"
    assert row["artifact_path"] == ".agent/goal_briefs/x/goal_brief.json"
    assert row["created_at"] == "2026-05-25T16:37:41+00:00"
    assert row["task_summary"]
    assert row["target"]["dataset_task"] == "validation_planning"
    assert row["features"]["has_validation"] is True
    assert row["target"]["authority"] == "advisory_only"
    assert row["quality"]["parse_status"] == "ok"


def test_worker_assignment_becomes_normalized_row():
    row = normalize_artifact(
        "worker_assignment", _worker_assignment(),
        artifact_path=".agent/worker_assignments/wa1/worker_assignment.json",
    )
    assert row["artifact_kind"] == "worker_assignment"
    assert row["source_id"] == "2026-06-16t04-59-54z-test-mayor-mode-smoke-flow"
    assert row["mode"] == "debug"
    assert row["human_approval_required"] is True
    assert row["target"]["dataset_task"] == "routing_or_policy_learning"
    assert row["target"]["target_label"] == "prepare_worker_assignment"
    assert row["features"]["has_validation"] is True


def test_driver_decision_captures_recommended_vehicle():
    row = normalize_artifact(
        "driver_decision", _driver_decision(),
        artifact_path=".agent/driver_decisions/dd1/driver_decision.json",
    )
    assert row["artifact_kind"] == "driver_decision"
    assert row["labels"]["recommended_vehicle"] == "cheap_api_ok"
    assert row["target"]["dataset_task"] == "routing_or_policy_learning"
    assert row["target"]["target_label"] == "cheap_api_ok"


def test_driver_decision_blocked_is_high_risk():
    row = normalize_artifact(
        "driver_decision", _driver_decision(blocked=True),
        artifact_path=".agent/driver_decisions/dd1/driver_decision.json",
    )
    assert row["risk_level"] == "high"
    assert row["labels"]["final_verdict"] == "blocked"


def test_visual_evidence_contract_captures_visual_features():
    row = normalize_artifact(
        "visual_evidence_contract", _visual_evidence(),
        artifact_path=".agent/visual_evidence/v1/visual_evidence_contract.json",
    )
    assert row["features"]["has_visual_issue"] is True
    assert row["target"]["dataset_task"] == "visual_evidence_policy"


def test_self_evolution_pack_captures_verdict_and_next_step():
    row = normalize_artifact(
        "self_evolution_evidence_pack", _evidence_pack(),
        artifact_path=".agent/self_evolution_trials/t1/self_evolution_evidence_pack.json",
    )
    assert row["labels"]["final_verdict"] == "ready_for_human_review"
    assert row["labels"]["recommended_next_step"] == "review_patch_candidate"
    assert row["target"]["dataset_task"] == "self_evolution_review"
    assert row["features"]["has_patch_candidate"] is True
    assert row["features"]["has_human_gate"] is True


def test_telegram_contract_captures_remote_safety_row():
    row = normalize_artifact(
        "telegram_evidence_contract", _telegram_contract(),
        artifact_path=".agent/automation_contracts/telegram_evidence_contract.json",
    )
    assert row["target"]["dataset_task"] == "remote_safety_policy"
    assert row["features"]["has_remote_component"] is True
    assert row["automation_level"] == "remote"
    assert "merge" in row["blocked_actions"]


def test_github_contract_captures_remote_safety_row():
    row = normalize_artifact(
        "github_pr_safety_contract", _github_contract(),
        artifact_path=".agent/automation_contracts/github_pr_safety_contract.json",
    )
    assert row["target"]["dataset_task"] == "remote_safety_policy"
    assert row["features"]["has_remote_component"] is True
    assert row["automation_level"] == "remote"


def test_n8n_dry_run_captures_orchestration_safety_row():
    row = normalize_artifact(
        "n8n_orchestration_dry_run", _n8n_dry_run(),
        artifact_path=".agent/automation_contracts/n8n_orchestration_dry_run.json",
    )
    assert row["target"]["dataset_task"] == "remote_safety_policy"
    assert row["features"]["has_remote_component"] is True
    assert row["labels"]["final_verdict"] == "dry_run_ready_for_human_review"


def test_teaching_card_becomes_lesson_teaching_row():
    row = normalize_artifact(
        "teaching_card", _teaching_card(),
        artifact_path=".agent/teaching_cards/c1/teaching_card.json",
    )
    assert row["artifact_kind"] == "teaching_card"
    assert row["source_id"] == "2026-06-16t05-03-00z-teaching-card"
    assert row["target"]["dataset_task"] == "lesson_teaching"


def test_worker_result_review_captures_security_claim():
    row = normalize_artifact(
        "worker_result_review", _worker_result_review(),
        artifact_path=".agent/worker_result_reviews/wr1/worker_result_review.json",
    )
    assert row["target"]["dataset_task"] == "risk_classification"
    assert row["features"]["has_security_sensitive_claim"] is True


def test_partial_artifact_produces_best_effort_row():
    row = normalize_artifact(
        "goal_brief", {}, artifact_path=".agent/goal_briefs/empty/goal_brief.json"
    )
    assert row["artifact_kind"] == "goal_brief"
    assert row["quality"]["parse_status"] == "partial"
    assert row["quality"]["missing_fields"]
    assert row["target"]["dataset_task"] == "validation_planning"


def test_row_has_all_required_fields():
    row = normalize_artifact("driver_decision", _driver_decision(), artifact_path="a.json")
    for key in (
        "row_id",
        "artifact_kind",
        "artifact_path",
        "created_at",
        "source_id",
        "task_title",
        "task_summary",
        "mode",
        "risk_level",
        "automation_level",
        "human_approval_required",
        "allowed_actions",
        "blocked_actions",
        "labels",
        "features",
        "target",
        "quality",
    ):
        assert key in row, key
    for key in ("recommended_vehicle", "final_verdict", "recommended_next_step"):
        assert key in row["labels"], key
    for key in (
        "has_validation",
        "has_visual_issue",
        "has_security_sensitive_claim",
        "has_remote_component",
        "has_patch_candidate",
        "has_human_gate",
    ):
        assert key in row["features"], key
    for key in ("dataset_task", "target_label", "authority"):
        assert key in row["target"], key
    for key in ("parse_status", "missing_fields", "warnings"):
        assert key in row["quality"], key
    assert row["risk_level"] in RISK_LEVELS
    assert row["automation_level"] in AUTOMATION_LEVELS
    assert row["target"]["dataset_task"] in DATASET_TASKS


# ── 11. malformed JSON is skipped with a warning ───────────────────────────────

def test_malformed_json_is_skipped_with_warning(tmp_path):
    path = tmp_path / ".agent" / "goal_briefs" / "bad" / "goal_brief.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not valid json", encoding="utf-8")
    scan = scan_artifacts(str(tmp_path))
    assert scan["rows"] == []
    assert scan["skipped_files"]
    assert any("goal_brief.json" in s["path"] for s in scan["skipped_files"])
    assert scan["warnings"]


def test_non_object_json_is_skipped(tmp_path):
    path = tmp_path / ".agent" / "goal_briefs" / "list" / "goal_brief.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    scan = scan_artifacts(str(tmp_path))
    assert scan["rows"] == []
    assert scan["skipped_files"]


# ── 13. row ids are deterministic ──────────────────────────────────────────────

def test_row_ids_are_deterministic():
    art = _driver_decision()
    a = normalize_artifact("driver_decision", art, artifact_path="a/b/driver_decision.json")
    b = normalize_artifact("driver_decision", copy.deepcopy(art), artifact_path="a/b/driver_decision.json")
    assert a["row_id"] == b["row_id"]
    assert a["row_id"]


def test_row_id_changes_with_path():
    art = _driver_decision()
    a = normalize_artifact("driver_decision", art, artifact_path="a/driver_decision.json")
    b = normalize_artifact("driver_decision", art, artifact_path="b/driver_decision.json")
    assert a["row_id"] != b["row_id"]


def test_row_id_has_no_backslashes_or_drive_letters():
    row = normalize_artifact(
        "goal_brief", _goal_brief(),
        artifact_path=".agent/goal_briefs/x/goal_brief.json",
    )
    assert "\\" not in row["row_id"]
    assert ":" not in row["row_id"]


# ── 14. JSONL output is deterministic ──────────────────────────────────────────

def test_jsonl_output_is_deterministic(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, list(_KIND_FIXTURES))

    def run(name: str) -> str:
        res = write_artifact_dataset(
            str(repo), str(tmp_path / name), report_id="fixed", created_at="2026-06-20T00:00:00+00:00"
        )
        return Path(res["jsonl_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


def test_jsonl_has_one_row_per_line(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief", "driver_decision", "teaching_card"])
    res = write_artifact_dataset(str(repo), str(tmp_path / "out"), report_id="r", created_at="t")
    lines = [l for l in Path(res["jsonl_path"]).read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3
    for line in lines:
        json.loads(line)  # each line is a standalone JSON object


# ── 15. report counts ──────────────────────────────────────────────────────────

def test_report_counts_are_correct(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, [
        "goal_brief",
        "worker_assignment",
        "driver_decision",
        "telegram_evidence_contract",
        "github_pr_safety_contract",
        "n8n_orchestration_dry_run",
    ])
    res = write_artifact_dataset(str(repo), str(tmp_path / "out"), report_id="r", created_at="t")
    report = res["report"]
    assert report["row_count"] == 6
    assert report["counts_by_artifact_kind"] == {
        "driver_decision": 1,
        "github_pr_safety_contract": 1,
        "goal_brief": 1,
        "n8n_orchestration_dry_run": 1,
        "telegram_evidence_contract": 1,
        "worker_assignment": 1,
    }
    assert report["counts_by_dataset_task"] == {
        "remote_safety_policy": 3,
        "routing_or_policy_learning": 2,
        "validation_planning": 1,
    }
    assert report["counts_by_risk_level"] == {"low": 3, "medium": 3}
    assert report["counts_by_target_label"] == {
        "cheap_api_ok": 1,
        "draft": 1,
        "dry_run_ready_for_human_review": 1,
        "prepare_worker_assignment": 1,
        "review_patch_candidate": 2,
    }
    assert report["report_kind"] == REPORT_KIND


def test_report_has_required_fields_and_sample_rows(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief", "driver_decision"])
    res = write_artifact_dataset(str(repo), str(tmp_path / "out"), report_id="rid", created_at="2026-06-20")
    report = res["report"]
    for key in (
        "report_id",
        "created_at",
        "repo_path",
        "output_dir",
        "jsonl_path",
        "row_count",
        "counts_by_artifact_kind",
        "counts_by_dataset_task",
        "counts_by_risk_level",
        "counts_by_target_label",
        "scanned_paths",
        "skipped_files",
        "warnings",
        "guardrails",
        "sample_rows",
    ):
        assert key in report, key
    assert report["report_id"] == "rid"
    assert report["created_at"] == "2026-06-20"
    assert isinstance(report["sample_rows"], list) and report["sample_rows"]


# ── 16. include-kind filter ────────────────────────────────────────────────────

def test_include_kind_filter_limits_kinds(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief", "driver_decision", "teaching_card"])
    res = write_artifact_dataset(
        str(repo), str(tmp_path / "out"), report_id="r", created_at="t", include_kinds=["goal_brief"]
    )
    kinds = {row["artifact_kind"] for row in res["rows"]}
    assert kinds == {"goal_brief"}


# ── 17. limit ──────────────────────────────────────────────────────────────────

def test_limit_is_deterministic(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, list(_KIND_FIXTURES))
    res1 = write_artifact_dataset(str(repo), str(tmp_path / "a"), report_id="r", created_at="t", limit=2)
    res2 = write_artifact_dataset(str(repo), str(tmp_path / "b"), report_id="r", created_at="t", limit=2)
    assert len(res1["rows"]) == 2
    assert [r["row_id"] for r in res1["rows"]] == [r["row_id"] for r in res2["rows"]]


# ── 18. source artifacts are not modified ──────────────────────────────────────

def test_source_artifacts_are_not_modified(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    path = _write_json(repo, ".agent/goal_briefs/x/goal_brief.json", _goal_brief())
    before = path.read_bytes()
    write_artifact_dataset(str(repo), str(tmp_path / "out"), report_id="r", created_at="t")
    assert path.read_bytes() == before


def test_normalize_does_not_mutate_artifact():
    art = _evidence_pack()
    snap = copy.deepcopy(art)
    normalize_artifact("self_evolution_evidence_pack", art, artifact_path="a.json")
    assert art == snap


# ── 19. Markdown sections + boundaries ─────────────────────────────────────────

def test_markdown_contains_all_sections(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief", "driver_decision", "telegram_evidence_contract"])
    res = write_artifact_dataset(str(repo), str(tmp_path / "out"), report_id="r", created_at="t")
    md = render_artifact_dataset_markdown(res["report"])
    assert "# C.A.T.T.U.S Artifact Dataset Report" in md
    low = md.lower()
    for section in (
        "## summary",
        "## dataset files",
        "## counts by artifact kind",
        "## counts by dataset task",
        "## counts by risk level",
        "## counts by target label",
        "## skipped files",
        "## warnings",
        "## sample rows",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief"])
    res = write_artifact_dataset(str(repo), str(tmp_path / "out"), report_id="r", created_at="t")
    low = render_artifact_dataset_markdown(res["report"]).lower()
    assert "does not train models" in low
    assert "does not call models" in low
    assert "does not call embeddings" in low
    assert "does not write to databases" in low
    assert "does not apply patches" in low
    assert "does not run validation or benchmarks" in low
    assert "does not launch workers" in low
    assert "telegram" in low and "github" in low and "n8n" in low
    assert "advisory artifacts only" in low
    assert "no execution authority" in low


def test_guardrail_note_is_report_only():
    assert "report-only" in ARTIFACT_DATASET_GUARDRAIL_NOTE.lower()


# ── 20-21. CLI ─────────────────────────────────────────────────────────────────

def test_cli_writes_jsonl_json_and_markdown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief", "driver_decision"])
    out = tmp_path / "out"
    res = script.run_build_artifact_dataset(
        repo_path=str(repo), output_root=str(out), report_id="cli", created_at="2026-06-20T00:00:00+00:00"
    )
    assert res["ok"] is True
    assert Path(res["jsonl_path"]).name == JSONL_NAME
    assert Path(res["json_path"]).name == REPORT_JSON_NAME
    assert Path(res["md_path"]).name == REPORT_MD_NAME
    assert (out / JSONL_NAME).is_file()
    assert (out / REPORT_JSON_NAME).is_file()
    assert (out / REPORT_MD_NAME).is_file()
    report = json.loads((out / REPORT_JSON_NAME).read_text(encoding="utf-8"))
    assert report["report_id"] == "cli"
    assert report["row_count"] == 2


def test_cli_main_smoke(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief"])
    out = tmp_path / "out"
    code = script.main(
        ["--repo-path", str(repo), "--output-root", str(out), "--report-id", "s", "--created-at", "t"]
    )
    assert code == 0
    assert (out / JSONL_NAME).is_file()
    assert (out / REPORT_JSON_NAME).is_file()
    assert (out / REPORT_MD_NAME).is_file()


def test_cli_json_flag_prints_summary(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief", "driver_decision"])
    out = tmp_path / "out"
    code = script.main(
        ["--repo-path", str(repo), "--output-root", str(out), "--report-id", "j", "--created-at", "t", "--json"]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "j"
    assert printed["row_count"] == 2
    assert printed["report_kind"] == REPORT_KIND


def test_cli_include_kind_and_limit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief", "driver_decision", "teaching_card"])
    out = tmp_path / "out"
    code = script.main(
        [
            "--repo-path", str(repo),
            "--output-root", str(out),
            "--report-id", "x",
            "--created-at", "t",
            "--include-kind", "goal_brief",
            "--include-kind", "driver_decision",
            "--limit", "1",
        ]
    )
    assert code == 0
    report = json.loads((out / REPORT_JSON_NAME).read_text(encoding="utf-8"))
    assert report["row_count"] == 1


def test_cli_missing_agent_directory_is_not_a_crash(tmp_path):
    out = tmp_path / "out"
    code = script.main(["--repo-path", str(tmp_path), "--output-root", str(out), "--report-id", "x", "--created-at", "t"])
    assert code == 0
    report = json.loads((out / REPORT_JSON_NAME).read_text(encoding="utf-8"))
    assert report["row_count"] == 0
    assert report["warnings"]


# ── constants ───────────────────────────────────────────────────────────────────

def test_artifact_kinds_constant_matches_spec():
    assert set(ARTIFACT_KINDS) == {
        "goal_brief",
        "worker_assignment",
        "driver_decision",
        "visual_evidence_contract",
        "worker_result_review",
        "flaky_case_review",
        "self_evolution_evidence_pack",
        "telegram_evidence_contract",
        "github_pr_safety_contract",
        "n8n_orchestration_dry_run",
        "phase_registry_report",
        "phase_picker_report",
        "teaching_card",
    }


def test_dataset_tasks_constant_matches_spec():
    assert set(DATASET_TASKS) == {
        "routing_or_policy_learning",
        "risk_classification",
        "artifact_summarization",
        "validation_planning",
        "visual_evidence_policy",
        "remote_safety_policy",
        "self_evolution_review",
        "lesson_teaching",
        "unknown",
    }


def test_every_kind_maps_to_a_known_dataset_task(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, list(_KIND_FIXTURES))
    res = write_artifact_dataset(str(repo), str(tmp_path / "out"), report_id="r", created_at="t")
    assert res["report"]["row_count"] == len(_KIND_FIXTURES)
    for row in res["rows"]:
        assert row["target"]["dataset_task"] in DATASET_TASKS
        assert row["target"]["dataset_task"] != "unknown"
        assert row["target"]["authority"] == "advisory_only"


def test_guardrails_all_false(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _populate(repo, ["goal_brief"])
    res = write_artifact_dataset(str(repo), str(tmp_path / "out"), report_id="r", created_at="t")
    guardrails = res["report"]["guardrails"]
    for key in (
        "model_training_performed",
        "model_call_performed",
        "embedding_call_performed",
        "database_write_performed",
        "patch_applied",
        "validation_run",
        "benchmark_run",
        "network_call_performed",
        "worker_launch_performed",
        "lesson_promotion_performed",
        "merge_performed",
    ):
        assert guardrails[key] is False, key


# ── 22. forbidden-token / import guards (source-only) ──────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "artifact_dataset_builder.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "build_artifact_dataset.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_only():
    allowed_top = {"__future__", "json", "pathlib", "typing", "hashlib"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            assert top != "core", f"MODEL.1 core must not import other core modules: {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_model_clients_or_training():
    # Bare "model"/"classifier" are allowed (they name the dataset's purpose); the
    # client / training *call shapes* are forbidden.
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
        "sklearn",
        "tensorflow",
        "lightgbm",
        "xgboost",
        "joblib",
        "call_model(",
        "launch_model(",
        "fit(",
        "predict(",
        ".fit(",
        ".train(",
        "model.train(",
    ):
        assert bad not in _BOTH, f"Found model client/training token {bad!r}"


def test_no_embedding_calls():
    # Bare "embeddings" is allowed in the boundary text; the call/client shapes are not.
    for bad in (
        "embed_query(",
        "embed_documents(",
        "embeddings.create",
        "OpenAIEmbeddings",
        "SentenceTransformer",
        "embedding_model(",
        "get_embedding(",
    ):
        assert bad not in _BOTH, f"Found embedding token {bad!r}"


def test_no_database_writes():
    # Bare "database" is allowed in the boundary text; the client / write shapes are not.
    for bad in (
        "sqlite3",
        "psycopg",
        "sqlalchemy",
        "pymongo",
        "chromadb",
        "pinecone",
        "qdrant",
        "weaviate",
        "faiss",
        "INSERT INTO",
        "conn.execute(",
        "cursor.execute(",
        "session.add(",
    ):
        assert bad not in _BOTH, f"Found database token {bad!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "check_output", "check_call", "shutil", "copytree", "os.popen"):
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


def test_no_network_remote_send_or_git_behaviour():
    # Bare "telegram"/"github"/"n8n" are required artifact-kind identifiers; only the
    # call / command / API shapes are forbidden.
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
        assert bad not in _BOTH, f"Found network/remote/git token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "launch_worker(", "worker_launch(", "spawn_worker", "run_worker("):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"
