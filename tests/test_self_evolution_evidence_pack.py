"""Tests for AUTO.1e — Sandbox Self-Evolution Evidence Pack.

AUTO.1e is a *report-only* evidence pack builder. It consumes the AUTO.1a/1b/1c/1d
artifacts and produces one human-readable package. It packages evidence; it does
not execute, approve, apply, push, merge, or contact external systems.

Covers the prescribed cases:
1.  complete clean chain -> ready_for_human_review.
2.  missing graduation review -> incomplete_pack.
3.  missing patch evaluation -> incomplete_pack.
4.  graduation needs more validation -> needs_more_validation.
5.  graduation blocked by safety -> blocked.
6.  real_repo_modified=true in any artifact -> blocked.
7.  patch_applied_to_real_repo=true in any artifact -> blocked.
8.  self_approval_allowed=true in any artifact -> blocked.
9.  eligible_for_auto_merge=true in any artifact -> blocked.
10. validation skipped creates a warning.
11. sandbox-only side effects are summarized.
12. malformed artifact handled as incomplete / not reviewable.
13. trial-dir auto-discovery finds known artifacts.
14. Markdown has summary / timeline / verdicts / risk / human review packet /
    boundaries.
15. JSON has all guardrail booleans.
16. CLI writes JSON + Markdown.
17. deterministic --pack-id and --created-at.
18. source artifacts are not modified.
19. no forbidden imports / calls.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.self_evolution_evidence_pack import (
    EVIDENCE_PACK_GUARDRAIL_NOTE,
    FINAL_VERDICTS,
    RECOMMENDED_NEXT_STEPS,
    REPORT_KIND,
    artifact_verdict,
    build_evidence_pack,
    render_evidence_pack_markdown,
)
import scripts.create_self_evolution_evidence_pack as script


# ── synthetic source artifacts ────────────────────────────────────────────────

def _contract(**over) -> dict:
    data = {
        "report_kind": "sandbox_self_evolution_trial",
        "trial_id": "t1",
        "phase": {"id": "AUTO.x", "title": "Tidy a helper", "summary": "One-file cleanup."},
        "automation_level": "SANDBOX_2_DRAFT_PATCH",
        "verdict": "eligible_for_review",
        "next_safe_step": "run_sandbox_trial_manually",
        "real_repo_modified": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "human_approval_required": True,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
    }
    data.update(over)
    return data


def _dry_run(**over) -> dict:
    data = {
        "report_kind": "sandbox_self_evolution_dry_run",
        "trial_id": "t1",
        "contract_verdict": "eligible_for_review",
        "dry_run_verdict": "dry_run_passed",
        "validation_status": "ran",
        "side_effects": {"created": [], "modified": [], "deleted": [], "summary": {"created": 0, "modified": 0, "deleted": 0}},
        "side_effects_sandbox_only": True,
        "real_repo_modified": False,
        "patch_applied_to_real_repo": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "validation_run_by_tool": True,
        "benchmark_run_by_tool": False,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "human_approval_required": True,
    }
    data.update(over)
    return data


def _patch_eval(**over) -> dict:
    data = {
        "report_kind": "sandbox_patch_candidate_evaluation",
        "trial_id": "t1",
        "verdict": "patch_candidate_passed",
        "validation_status": "ran",
        "patch_touched_paths": ["pkg/demo.txt"],
        "patch_changed_lines": 2,
        "patch_file_count": 1,
        "patch_safety": {"ok": True, "empty": False, "too_large": False, "rejected_paths": [], "reasons": []},
        "patch_side_effects": {
            "created": [{"path": "pkg/demo.txt", "inside_patch_touched_scope": True, "known_generated_or_noisy": False}],
            "modified": [],
            "deleted": [],
            "summary": {"created": 1, "modified": 0, "deleted": 0},
        },
        "validation_side_effects": {"created": [], "modified": [], "deleted": [], "summary": {"created": 0, "modified": 0, "deleted": 0}},
        "side_effects_sandbox_only": True,
        "real_repo_modified": False,
        "patch_applied_to_real_repo": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "validation_run_by_tool": True,
        "benchmark_run_by_tool": False,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "human_approval_required": True,
    }
    data.update(over)
    return data


def _grad(**over) -> dict:
    data = {
        "report_kind": "sandbox_patch_graduation_review",
        "trial_id": "t1",
        "graduation_verdict": "eligible_for_human_review",
        "recommended_next_step": "prepare_human_review_packet",
        "source_verdict": "patch_candidate_passed",
        "source_patch_touched_paths": ["pkg/demo.txt"],
        "source_validation_status": "ran",
        "source_side_effects": {"patch": {"created": 1, "modified": 0, "deleted": 0}, "validation": {"created": 0, "modified": 0, "deleted": 0}},
        "blockers": [],
        "warnings": [],
        "real_repo_modified": False,
        "patch_applied_to_real_repo": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "human_review_required": True,
    }
    data.update(over)
    return data


def _build(contract=None, dry_run=None, patch_evaluation=None, graduation_review=None, **over) -> dict:
    artifacts = {
        "contract": contract,
        "dry_run": dry_run,
        "patch_evaluation": patch_evaluation,
        "graduation_review": graduation_review,
    }
    params = dict(artifacts=artifacts, pack_id="pack-1", created_at="2026-06-18T00:00:00+00:00")
    params.update(over)
    return build_evidence_pack(**params)


# ── 1. complete clean chain -> ready_for_human_review ─────────────────────────

def test_complete_clean_chain_is_ready_for_human_review():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad())
    assert rec["final_verdict"] == "ready_for_human_review"
    assert rec["recommended_next_step"] == "review_patch_candidate"
    assert rec["blockers"] == []
    assert rec["warnings"] == []
    assert rec["missing_artifacts"] == []
    assert rec["trial_id"] == "t1"


# ── 2-3. missing artifacts -> incomplete_pack ─────────────────────────────────

def test_missing_graduation_review_is_incomplete():
    rec = _build(_contract(), _dry_run(), _patch_eval(), None)
    assert rec["final_verdict"] == "incomplete_pack"
    assert rec["recommended_next_step"] == "complete_missing_artifacts"
    assert "graduation_review" in rec["missing_artifacts"]


def test_missing_patch_evaluation_is_incomplete():
    rec = _build(_contract(), _dry_run(), None, None)
    assert rec["final_verdict"] == "incomplete_pack"
    assert "patch_evaluation" in rec["missing_artifacts"]
    assert "graduation_review" in rec["missing_artifacts"]


def test_contract_only_is_incomplete_not_failed():
    rec = _build(_contract(), None, None, None)
    assert rec["final_verdict"] == "incomplete_pack"
    # contract-only is a valid early pack, not a failure
    assert rec["recommended_next_step"] in RECOMMENDED_NEXT_STEPS
    assert rec["blockers"] == []


# ── 4. graduation needs more validation -> needs_more_validation ──────────────

def test_graduation_needs_more_validation():
    rec = _build(
        _contract(),
        _dry_run(),
        _patch_eval(),
        _grad(graduation_verdict="needs_more_validation", recommended_next_step="request_more_validation"),
    )
    assert rec["final_verdict"] == "needs_more_validation"
    assert rec["recommended_next_step"] == "request_more_validation"


# ── 5. graduation blocked by safety / not reviewable -> blocked ───────────────

def test_graduation_blocked_by_safety():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad(graduation_verdict="blocked_by_safety"))
    assert rec["final_verdict"] == "blocked"
    assert rec["recommended_next_step"] == "reject_candidate"


def test_graduation_not_reviewable_is_blocked():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad(graduation_verdict="not_reviewable"))
    assert rec["final_verdict"] == "blocked"


# ── 6-9. hard breaches in any artifact -> blocked ─────────────────────────────

def test_real_repo_modified_in_any_artifact_blocks():
    rec = _build(_contract(), _dry_run(real_repo_modified=True), _patch_eval(), _grad())
    assert rec["final_verdict"] == "blocked"
    assert any("real repo" in b.lower() for b in rec["blockers"])


def test_patch_applied_to_real_repo_blocks():
    rec = _build(_contract(), _dry_run(), _patch_eval(patch_applied_to_real_repo=True), _grad())
    assert rec["final_verdict"] == "blocked"


def test_self_approval_allowed_in_contract_blocks():
    rec = _build(_contract(self_approval_allowed=True), _dry_run(), _patch_eval(), _grad())
    assert rec["final_verdict"] == "blocked"
    assert any("self-approval" in b.lower() or "self approval" in b.lower() for b in rec["blockers"])


def test_eligible_for_auto_merge_blocks():
    rec = _build(_contract(), _dry_run(eligible_for_auto_merge=True), _patch_eval(), _grad())
    assert rec["final_verdict"] == "blocked"


def test_push_performed_blocks():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad(push_performed=True))
    assert rec["final_verdict"] == "blocked"


def test_merge_performed_blocks():
    rec = _build(_contract(), _dry_run(merge_performed=True), _patch_eval(), _grad())
    assert rec["final_verdict"] == "blocked"


def test_non_sandbox_side_effects_block():
    rec = _build(_contract(), _dry_run(), _patch_eval(side_effects_sandbox_only=False), _grad())
    assert rec["final_verdict"] == "blocked"


# ── 10. validation skipped creates a warning ──────────────────────────────────

def test_validation_skipped_creates_warning():
    rec = _build(
        _contract(),
        _dry_run(validation_status="skipped", dry_run_verdict="validation_skipped"),
        _patch_eval(),
        _grad(),
    )
    assert any("validation" in w.lower() and "skip" in w.lower() for w in rec["warnings"])


# ── 11. sandbox-only side effects summarized ──────────────────────────────────

def test_sandbox_side_effects_are_summarized():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad())
    packet = rec["human_review_packet"]
    assert packet["sandbox_side_effects"]["patch"]["created"] == 1
    assert "sandbox-only" in rec["risk_summary"]["side_effects"].lower()


# ── 12. malformed artifact handled ────────────────────────────────────────────

def test_malformed_graduation_is_treated_as_missing():
    rec = _build(_contract(), _dry_run(), _patch_eval(), {"report_kind": "something_else"})
    assert rec["final_verdict"] == "incomplete_pack"
    assert "graduation_review" in rec["missing_artifacts"]
    assert any("graduation" in w.lower() for w in rec["warnings"])


def test_non_dict_artifact_is_treated_as_missing():
    rec = _build(_contract(), "not a dict", _patch_eval(), _grad())
    assert "dry_run" in rec["missing_artifacts"]
    # still drivable by the graduation review
    assert rec["final_verdict"] == "ready_for_human_review"


def test_all_missing_is_incomplete():
    rec = _build(None, None, None, None)
    assert rec["final_verdict"] == "incomplete_pack"
    assert set(rec["missing_artifacts"]) == {"contract", "dry_run", "patch_evaluation", "graduation_review"}


# ── 13. trial-dir auto-discovery ──────────────────────────────────────────────

def test_trial_dir_discovery_finds_known_artifacts(tmp_path):
    (tmp_path / "self_evolution_trial.json").write_text(json.dumps(_contract()), encoding="utf-8")
    (tmp_path / "sandbox_dry_run.json").write_text(json.dumps(_dry_run()), encoding="utf-8")
    (tmp_path / "patch_candidate_evaluation.json").write_text(json.dumps(_patch_eval()), encoding="utf-8")
    (tmp_path / "patch_graduation_review.json").write_text(json.dumps(_grad()), encoding="utf-8")
    found = script.discover_artifacts_in_trial_dir(str(tmp_path))
    assert set(found.keys()) == {"contract", "dry_run", "patch_evaluation", "graduation_review"}
    assert Path(found["contract"]).name == "self_evolution_trial.json"


def test_trial_dir_discovery_partial(tmp_path):
    (tmp_path / "self_evolution_trial.json").write_text(json.dumps(_contract()), encoding="utf-8")
    found = script.discover_artifacts_in_trial_dir(str(tmp_path))
    assert set(found.keys()) == {"contract"}


# ── 14. Markdown sections ─────────────────────────────────────────────────────

def test_markdown_contains_required_sections():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad())
    md = render_evidence_pack_markdown(rec)
    assert "# Sandbox Self-Evolution Evidence Pack" in md
    assert "## Summary" in md
    assert "## Timeline" in md
    assert "## Verdicts" in md
    assert "| Artifact | Verdict | Notes |" in md
    assert "## Risk Summary" in md
    assert "## Human Review Packet" in md
    assert "## Blockers" in md
    assert "## Warnings" in md
    assert "## Boundaries" in md
    low = md.lower()
    assert "does not run automation" in low
    assert "does not apply patches" in low
    assert "does not run validation or benchmarks" in low
    assert "does not call models" in low
    assert "does not modify the real repo" in low
    assert "does not push, merge, open prs" in low
    assert "human approval is required before any real repo change" in low


def test_markdown_timeline_lists_four_steps():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad())
    md = render_evidence_pack_markdown(rec)
    for label in ("Contract", "Dry run", "Patch candidate evaluation", "Graduation review"):
        assert label in md


# ── 15. guardrail booleans ────────────────────────────────────────────────────

def test_json_contains_all_guardrail_booleans():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad())
    assert rec["human_review_required"] is True
    for key in (
        "self_approval_allowed",
        "eligible_for_auto_merge",
        "real_repo_modified",
        "patch_applied_to_real_repo",
        "push_performed",
        "merge_performed",
        "model_call_performed",
        "validation_run_by_tool",
        "benchmark_run_by_tool",
        "worker_launch_performed",
    ):
        assert rec[key] is False, key
    for key in (
        "pack_id",
        "created_at",
        "trial_id",
        "source_artifacts",
        "missing_artifacts",
        "source_verdicts",
        "final_verdict",
        "recommended_next_step",
        "summary",
        "timeline",
        "risk_summary",
        "human_review_packet",
        "blockers",
        "warnings",
    ):
        assert key in rec, key
    assert rec["report_kind"] == REPORT_KIND
    assert rec["final_verdict"] in FINAL_VERDICTS
    assert rec["recommended_next_step"] in RECOMMENDED_NEXT_STEPS
    assert len(rec["timeline"]) == 4
    assert rec["source_verdicts"]["graduation_review"] == "eligible_for_human_review"
    assert rec["source_verdicts"]["dry_run"] == "dry_run_passed"


def test_artifact_verdict_helper():
    assert artifact_verdict("contract", _contract()) == "eligible_for_review"
    assert artifact_verdict("dry_run", _dry_run()) == "dry_run_passed"
    assert artifact_verdict("patch_evaluation", _patch_eval()) == "patch_candidate_passed"
    assert artifact_verdict("graduation_review", _grad()) == "eligible_for_human_review"
    assert artifact_verdict("contract", None) is None


# ── 16-17. CLI writes JSON + Markdown; deterministic ──────────────────────────

def _write_trial_dir(tmp_path) -> Path:
    trial = tmp_path / "trial"
    trial.mkdir()
    (trial / "self_evolution_trial.json").write_text(json.dumps(_contract()), encoding="utf-8")
    (trial / "sandbox_dry_run.json").write_text(json.dumps(_dry_run()), encoding="utf-8")
    (trial / "patch_candidate_evaluation.json").write_text(json.dumps(_patch_eval()), encoding="utf-8")
    (trial / "patch_graduation_review.json").write_text(json.dumps(_grad()), encoding="utf-8")
    return trial


def test_cli_writes_json_and_markdown(tmp_path):
    trial = _write_trial_dir(tmp_path)
    out = tmp_path / "out"
    res = script.run_create_self_evolution_evidence_pack(
        trial_dir=str(trial),
        pack_id="cli-pack",
        created_at="2026-06-18T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "self_evolution_evidence_pack.json"
    assert mp.name == "self_evolution_evidence_pack.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["final_verdict"] == "ready_for_human_review"
    # source paths recorded
    kinds = {a["kind"] for a in data["source_artifacts"]}
    assert kinds == {"contract", "dry_run", "patch_evaluation", "graduation_review"}


def test_cli_main_smoke(tmp_path):
    trial = _write_trial_dir(tmp_path)
    out = tmp_path / "out"
    code = script.main(
        [
            "--trial-dir",
            str(trial),
            "--pack-id",
            "smoke",
            "--created-at",
            "2026-06-18T00:00:00+00:00",
            "--output-root",
            str(out),
        ]
    )
    assert code == 0
    data = json.loads((out / "t1" / "self_evolution_evidence_pack.json").read_text(encoding="utf-8"))
    assert data["final_verdict"] == "ready_for_human_review"


def test_cli_explicit_paths_override_discovery(tmp_path):
    trial = _write_trial_dir(tmp_path)
    # an explicit graduation review elsewhere that blocks
    other = tmp_path / "blocked_grad.json"
    other.write_text(json.dumps(_grad(graduation_verdict="blocked_by_safety")), encoding="utf-8")
    out = tmp_path / "out"
    res = script.run_create_self_evolution_evidence_pack(
        trial_dir=str(trial),
        graduation_review=str(other),
        pack_id="ov",
        created_at="2026-06-18T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["record"]["final_verdict"] == "blocked"


def test_deterministic_pack_id_and_created_at(tmp_path):
    trial = _write_trial_dir(tmp_path)

    def run(name: str) -> str:
        res = script.run_create_self_evolution_evidence_pack(
            trial_dir=str(trial),
            pack_id="fixed",
            created_at="2026-06-18T12:00:00+00:00",
            output_root=str(tmp_path / name),
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    a = run("a")
    b = run("b")
    assert a == b
    data = json.loads(a)
    assert data["pack_id"] == "fixed"
    assert data["created_at"] == "2026-06-18T12:00:00+00:00"


# ── 18. source artifacts are not modified ─────────────────────────────────────

def test_source_artifacts_not_modified_in_core():
    contract, dry_run, patch_eval, grad = _contract(), _dry_run(), _patch_eval(), _grad()
    snap = copy.deepcopy([contract, dry_run, patch_eval, grad])
    build_evidence_pack(
        artifacts={"contract": contract, "dry_run": dry_run, "patch_evaluation": patch_eval, "graduation_review": grad},
        pack_id="p",
        created_at="x",
    )
    assert [contract, dry_run, patch_eval, grad] == snap


def test_source_files_not_modified_by_cli(tmp_path):
    trial = _write_trial_dir(tmp_path)
    before = {p.name: p.read_text(encoding="utf-8") for p in trial.glob("*.json")}
    script.run_create_self_evolution_evidence_pack(
        trial_dir=str(trial),
        pack_id="p",
        created_at="2026-06-18T00:00:00+00:00",
        output_root=str(tmp_path / "out"),
    )
    after = {p.name: p.read_text(encoding="utf-8") for p in trial.glob("*.json")}
    assert before == after


# ── 19. import / side-effect guard ────────────────────────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "self_evolution_evidence_pack.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_self_evolution_evidence_pack.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_only():
    allowed_top = {"__future__", "json", "os", "pathlib", "typing", "dataclasses", "re"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            assert top != "core", f"AUTO.1e core must not import other core modules: {module!r}"
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


def test_no_patch_generation_or_real_repo_apply():
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


def test_guardrail_note_present():
    rec = _build(_contract(), _dry_run(), _patch_eval(), _grad())
    assert rec["guardrail_note"] == EVIDENCE_PACK_GUARDRAIL_NOTE
    assert "report-only" in EVIDENCE_PACK_GUARDRAIL_NOTE.lower() or "packages evidence" in EVIDENCE_PACK_GUARDRAIL_NOTE.lower()
