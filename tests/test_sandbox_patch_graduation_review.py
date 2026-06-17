"""Tests for AUTO.1d — Sandbox Patch Graduation Review.

AUTO.1d is a *review-only* graduation gate. It consumes an AUTO.1c patch
candidate evaluation artifact and decides whether the candidate is eligible for
human review. It never applies patches, runs validation, runs benchmarks, calls
models, touches the real repo, or contacts any remote service.

Covers the prescribed cases:
1.  a clean AUTO.1c passed artifact -> eligible_for_human_review.
2.  validation skipped -> needs_more_validation.
3.  failed validation -> blocked or not reviewable.
4.  failed patch apply -> not_reviewable.
5.  rejected by safety -> blocked_by_safety.
6.  real_repo_modified=true -> blocked_by_safety.
7.  patch_applied_to_real_repo=true -> blocked_by_safety.
8.  self_approval_allowed=true -> blocked_by_safety.
9.  eligible_for_auto_merge=true -> blocked_by_safety.
10. forbidden touched path -> blocked_by_safety.
11. suspicious side effects -> warning / needs_more_validation.
12. malformed artifact -> not_reviewable.
13. Markdown has summary / checks / blockers / warnings / human review packet /
    boundaries.
14. JSON has all guardrail booleans.
15. CLI writes JSON + Markdown.
16. deterministic --review-id and --created-at.
17. no forbidden imports / calls (model client, patch generation, patch apply,
    validation execution, benchmark execution, Dream, Project Evolution,
    network, lesson promotion, proposal import, worker launch, remote git host /
    chat / external automation, or auto-merge).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.sandbox_patch_graduation_review import (
    GRADUATION_GUARDRAIL_NOTE,
    GRADUATION_VERDICTS,
    RECOMMENDED_NEXT_STEPS,
    REPORT_KIND,
    build_graduation_review,
    render_graduation_review_markdown,
    source_verdict_category,
)
import scripts.create_sandbox_patch_graduation_review as script


# ── helpers ───────────────────────────────────────────────────────────────────

def _passed_eval(**over) -> dict:
    """A realistic, clean AUTO.1c 'patch_candidate_passed' artifact."""
    ev = {
        "report_kind": "sandbox_patch_candidate_evaluation",
        "trial_id": "t-pass",
        "created_at": "2026-06-17T00:00:00+00:00",
        "source_repo": "/repo",
        "sandbox_path": "/repo/.agent/self_evolution_sandboxes/t-pass",
        "patch_source": "candidate.patch",
        "verdict": "patch_candidate_passed",
        "validation_status": "ran",
        "patch_touched_paths": ["pkg/demo.txt"],
        "patch_changed_lines": 2,
        "patch_file_count": 1,
        "patch_changed_files": ["pkg/demo.txt"],
        "patch_safety": {
            "ok": True,
            "empty": False,
            "too_large": False,
            "rejected_paths": [],
            "reasons": [],
        },
        "validation_commands": [
            {
                "command": ["python", "-m", "compileall", "-q", "core"],
                "ok": True,
                "blocked": False,
                "exit_code": 0,
                "timed_out": False,
            }
        ],
        "patch_side_effects": {
            "created": [
                {
                    "path": "pkg/demo.txt",
                    "inside_patch_touched_scope": True,
                    "known_generated_or_noisy": False,
                }
            ],
            "modified": [],
            "deleted": [],
            "summary": {"created": 1, "modified": 0, "deleted": 0},
        },
        "validation_side_effects": {
            "created": [],
            "modified": [],
            "deleted": [],
            "summary": {"created": 0, "modified": 0, "deleted": 0},
        },
        "side_effects_sandbox_only": True,
        "sandbox_created": True,
        "sandbox_only": True,
        "patch_candidate_supplied": True,
        "patch_generated": False,
        "patch_applied_to_sandbox": True,
        "patch_applied_to_real_repo": False,
        "real_repo_modified": False,
        "validation_run_by_tool": True,
        "benchmark_run_by_tool": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "push_performed": False,
        "merge_performed": False,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "human_approval_required": True,
        "cleanup_performed": True,
    }
    ev.update(over)
    return ev


def _review(evaluation, **over) -> dict:
    params = dict(
        evaluation=evaluation,
        source_evaluation_path=".agent/self_evolution_trials/t-pass/patch_candidate_evaluation.json",
        review_id="rev-1",
        created_at="2026-06-17T01:00:00+00:00",
    )
    params.update(over)
    return build_graduation_review(**params)


# ── 1. clean passed artifact -> eligible_for_human_review ─────────────────────

def test_clean_passed_artifact_is_eligible():
    rec = _review(_passed_eval())
    assert rec["graduation_verdict"] == "eligible_for_human_review"
    assert rec["recommended_next_step"] == "prepare_human_review_packet"
    assert rec["source_verdict"] == "patch_candidate_passed"
    assert rec["blockers"] == []


# ── 2. validation skipped -> needs_more_validation ────────────────────────────

def test_validation_skipped_needs_more_validation():
    ev = _passed_eval(
        verdict="validation_skipped",
        validation_status="skipped",
        validation_run_by_tool=False,
        validation_commands=[],
    )
    rec = _review(ev)
    assert rec["graduation_verdict"] == "needs_more_validation"
    assert rec["recommended_next_step"] == "request_more_validation"


# ── 3. failed validation -> blocked or not reviewable ─────────────────────────

def test_failed_validation_is_blocked_or_not_reviewable():
    ev = _passed_eval(
        verdict="patch_candidate_failed_validation",
        validation_commands=[
            {
                "command": ["python", "boom.py"],
                "ok": False,
                "blocked": False,
                "exit_code": 2,
                "timed_out": False,
            }
        ],
    )
    rec = _review(ev)
    assert rec["graduation_verdict"] in ("blocked_by_safety", "not_reviewable")
    assert rec["graduation_verdict"] != "eligible_for_human_review"


# ── 4. failed patch apply -> not_reviewable ───────────────────────────────────

def test_failed_apply_is_not_reviewable():
    ev = _passed_eval(
        verdict="patch_candidate_failed_apply",
        patch_applied_to_sandbox=False,
        apply_error="hunk context did not match the sandbox file",
    )
    rec = _review(ev)
    assert rec["graduation_verdict"] == "not_reviewable"


# ── 5. rejected by safety -> blocked_by_safety ────────────────────────────────

def test_rejected_by_safety_is_blocked():
    ev = _passed_eval(
        verdict="patch_candidate_rejected_by_safety",
        patch_applied_to_sandbox=False,
        patch_safety={
            "ok": False,
            "empty": False,
            "too_large": False,
            "rejected_paths": [{"path": ".env", "reason": "forbidden path"}],
            "reasons": ["forbidden path"],
        },
    )
    rec = _review(ev)
    assert rec["graduation_verdict"] == "blocked_by_safety"
    assert rec["recommended_next_step"] in RECOMMENDED_NEXT_STEPS


# ── 6-9. guardrail breaches in the source artifact -> blocked_by_safety ────────

def test_real_repo_modified_is_blocked():
    rec = _review(_passed_eval(real_repo_modified=True))
    assert rec["graduation_verdict"] == "blocked_by_safety"
    assert any("real repo" in b.lower() for b in rec["blockers"])


def test_patch_applied_to_real_repo_is_blocked():
    rec = _review(_passed_eval(patch_applied_to_real_repo=True))
    assert rec["graduation_verdict"] == "blocked_by_safety"


def test_self_approval_allowed_is_blocked():
    rec = _review(_passed_eval(self_approval_allowed=True))
    assert rec["graduation_verdict"] == "blocked_by_safety"
    assert any("self-approval" in b.lower() or "self approval" in b.lower() for b in rec["blockers"])


def test_eligible_for_auto_merge_is_blocked():
    rec = _review(_passed_eval(eligible_for_auto_merge=True))
    assert rec["graduation_verdict"] == "blocked_by_safety"


def test_human_approval_not_required_is_blocked():
    rec = _review(_passed_eval(human_approval_required=False))
    assert rec["graduation_verdict"] == "blocked_by_safety"


def test_sandbox_only_false_is_blocked():
    rec = _review(_passed_eval(sandbox_only=False))
    assert rec["graduation_verdict"] == "blocked_by_safety"


def test_patch_generated_true_is_blocked():
    rec = _review(_passed_eval(patch_generated=True))
    assert rec["graduation_verdict"] == "blocked_by_safety"


# ── 10. forbidden touched path -> blocked_by_safety ───────────────────────────

def test_forbidden_touched_path_is_blocked():
    # Defense in depth: even a 'passed' artifact that lists a forbidden touched
    # path is blocked by AUTO.1d's own path scan.
    rec = _review(_passed_eval(patch_touched_paths=[".env"], patch_changed_files=[".env"]))
    assert rec["graduation_verdict"] == "blocked_by_safety"


def test_secrets_touched_path_is_blocked():
    rec = _review(_passed_eval(patch_touched_paths=["secrets/key.txt"]))
    assert rec["graduation_verdict"] == "blocked_by_safety"


def test_parent_traversal_touched_path_is_blocked():
    rec = _review(_passed_eval(patch_touched_paths=["../evil.py"]))
    assert rec["graduation_verdict"] == "blocked_by_safety"


def test_rejected_paths_in_safety_block_even_if_verdict_passed():
    ev = _passed_eval(
        patch_safety={
            "ok": False,
            "empty": False,
            "too_large": False,
            "rejected_paths": [{"path": ".git/config", "reason": "protected"}],
            "reasons": ["protected"],
        }
    )
    rec = _review(ev)
    assert rec["graduation_verdict"] == "blocked_by_safety"


# ── 11. suspicious side effects -> warning / needs_more_validation ────────────

def test_suspicious_validation_side_effects_downgrade_to_needs_more_validation():
    ev = _passed_eval(
        validation_side_effects={
            "created": [
                {
                    "path": "mystery.bin",
                    "inside_patch_touched_scope": False,
                    "known_generated_or_noisy": False,
                }
            ],
            "modified": [],
            "deleted": [],
            "summary": {"created": 1, "modified": 0, "deleted": 0},
        }
    )
    rec = _review(ev)
    assert rec["graduation_verdict"] == "needs_more_validation"
    assert rec["warnings"]


def test_generated_noisy_side_effects_are_warning_only():
    ev = _passed_eval(
        validation_side_effects={
            "created": [
                {
                    "path": "core/__pycache__/x.pyc",
                    "inside_patch_touched_scope": False,
                    "known_generated_or_noisy": True,
                }
            ],
            "modified": [],
            "deleted": [],
            "summary": {"created": 1, "modified": 0, "deleted": 0},
        }
    )
    rec = _review(ev)
    # generated/noisy files do not block graduation
    assert rec["graduation_verdict"] == "eligible_for_human_review"


# ── 12. malformed artifact -> not_reviewable ──────────────────────────────────

def test_none_artifact_is_not_reviewable():
    rec = _review(None)
    assert rec["graduation_verdict"] == "not_reviewable"
    assert rec["recommended_next_step"] == "manual_review_required"
    assert rec["blockers"]


def test_wrong_kind_artifact_is_not_reviewable():
    rec = _review({"report_kind": "something_else", "verdict": "patch_candidate_passed"})
    assert rec["graduation_verdict"] == "not_reviewable"


def test_missing_verdict_artifact_is_not_reviewable():
    # correct source kind but no verdict to review
    rec = _review({"report_kind": "sandbox_patch_candidate_evaluation"})
    assert rec["graduation_verdict"] == "not_reviewable"


def test_non_dict_artifact_is_not_reviewable():
    rec = _review("not a dict")
    assert rec["graduation_verdict"] == "not_reviewable"


# ── 13. Markdown sections ─────────────────────────────────────────────────────

def test_markdown_contains_required_sections():
    rec = _review(_passed_eval())
    md = render_graduation_review_markdown(rec)
    assert "# Sandbox Patch Graduation Review" in md
    assert "## Summary" in md
    assert "## Graduation Checks" in md
    assert "## Blockers" in md
    assert "## Warnings" in md
    assert "## Human Review Packet" in md
    assert "## Boundaries" in md
    # the checks table header
    assert "| Check | Result | Reason |" in md
    low = md.lower()
    assert "does not apply patches" in low
    assert "does not run validation" in low
    assert "does not call models" in low
    assert "does not modify the real repo" in low
    assert "does not push, merge, open prs" in low
    assert "human approval is required before any real repo change" in low


def test_markdown_blocked_lists_blockers():
    rec = _review(_passed_eval(real_repo_modified=True))
    md = render_graduation_review_markdown(rec)
    assert "## Blockers" in md
    # at least one blocker bullet appears under the section
    assert "real repo" in md.lower()


def test_markdown_human_review_packet_lists_touched_files():
    rec = _review(_passed_eval(patch_touched_paths=["pkg/a.txt", "pkg/b.txt"]))
    md = render_graduation_review_markdown(rec)
    assert "pkg/a.txt" in md
    assert "pkg/b.txt" in md


# ── 14. guardrail booleans ────────────────────────────────────────────────────

def test_json_contains_all_guardrail_booleans():
    rec = _review(_passed_eval())
    required_true = ("human_review_required",)
    required_false = (
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
    )
    for key in required_true:
        assert rec[key] is True, key
    for key in required_false:
        assert rec[key] is False, key
    # required non-boolean fields
    for key in (
        "review_id",
        "created_at",
        "source_evaluation_path",
        "trial_id",
        "source_verdict",
        "graduation_verdict",
        "checks",
        "blockers",
        "warnings",
        "recommended_next_step",
    ):
        assert key in rec, key
    assert rec["report_kind"] == REPORT_KIND
    assert rec["graduation_verdict"] in GRADUATION_VERDICTS
    assert rec["recommended_next_step"] in RECOMMENDED_NEXT_STEPS
    assert isinstance(rec["checks"], list) and rec["checks"]


# ── 15. CLI writes JSON + Markdown ────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    eval_path = tmp_path / "patch_candidate_evaluation.json"
    eval_path.write_text(json.dumps(_passed_eval()), encoding="utf-8")
    out = tmp_path / "out"
    res = script.run_create_sandbox_patch_graduation_review(
        evaluation_path=str(eval_path),
        review_id="cli-rev",
        created_at="2026-06-17T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file()
    assert mp.is_file()
    assert jp.name == "patch_graduation_review.json"
    assert mp.name == "patch_graduation_review.md"
    # writes under the trial directory revealed by the artifact
    assert jp.parent.name == "t-pass"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["graduation_verdict"] == "eligible_for_human_review"
    assert data["trial_id"] == "t-pass"


def test_cli_main_smoke(tmp_path):
    eval_path = tmp_path / "patch_candidate_evaluation.json"
    eval_path.write_text(json.dumps(_passed_eval()), encoding="utf-8")
    out = tmp_path / "out"
    code = script.main(
        [
            "--evaluation",
            str(eval_path),
            "--review-id",
            "smoke",
            "--created-at",
            "2026-06-17T00:00:00+00:00",
            "--output-root",
            str(out),
        ]
    )
    assert code == 0
    data = json.loads((out / "t-pass" / "patch_graduation_review.json").read_text(encoding="utf-8"))
    assert data["graduation_verdict"] == "eligible_for_human_review"


def test_cli_missing_file_writes_not_reviewable(tmp_path):
    out = tmp_path / "out"
    res = script.run_create_sandbox_patch_graduation_review(
        evaluation_path=str(tmp_path / "nope.json"),
        review_id="missing",
        created_at="2026-06-17T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["ok"] is True
    data = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
    assert data["graduation_verdict"] == "not_reviewable"
    # falls back to the review id for the directory
    assert Path(res["json_path"]).parent.name == "missing"


# ── 16. deterministic --review-id and --created-at ────────────────────────────

def test_deterministic_review_id_and_created_at(tmp_path):
    eval_path = tmp_path / "patch_candidate_evaluation.json"
    eval_path.write_text(json.dumps(_passed_eval()), encoding="utf-8")

    def run(name: str) -> str:
        res = script.run_create_sandbox_patch_graduation_review(
            evaluation_path=str(eval_path),
            review_id="fixed",
            created_at="2026-06-17T12:00:00+00:00",
            output_root=str(tmp_path / name),
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    a = run("a")
    b = run("b")
    assert a == b
    data = json.loads(a)
    assert data["review_id"] == "fixed"
    assert data["created_at"] == "2026-06-17T12:00:00+00:00"


# ── source verdict classification (direct unit) ───────────────────────────────

def test_source_verdict_category_mapping():
    assert source_verdict_category("patch_candidate_passed") == "pass"
    assert source_verdict_category("validation_skipped") == "conditional"
    assert source_verdict_category("patch_candidate_failed_apply") == "not_reviewable"
    assert source_verdict_category("sandbox_setup_failed") == "not_reviewable"
    assert source_verdict_category("patch_candidate_failed_validation") == "not_reviewable"
    assert source_verdict_category("patch_candidate_rejected_by_safety") == "blocked"
    assert source_verdict_category("blocked_by_contract") == "blocked"
    assert source_verdict_category("") == "unknown"
    assert source_verdict_category("garbage") == "unknown"


def test_checks_cover_all_dimensions():
    rec = _review(_passed_eval())
    names = {c["check"] for c in rec["checks"]}
    for expected in (
        "source_verdict_acceptable",
        "real_repo_unchanged",
        "sandbox_only",
        "human_gate_preserved",
        "patch_safety",
        "validation",
        "side_effects",
        "reviewability",
    ):
        assert expected in names, expected


def test_guardrail_note_is_present():
    rec = _review(_passed_eval())
    assert rec["guardrail_note"] == GRADUATION_GUARDRAIL_NOTE
    assert "human review" in GRADUATION_GUARDRAIL_NOTE.lower()


# ── 17. import / side-effect guard ────────────────────────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "sandbox_patch_graduation_review.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_sandbox_patch_graduation_review.py"
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
            assert top != "core", f"AUTO.1d core must not import other core modules: {module!r}"
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
    for bad in (
        "subprocess",
        "Popen",
        "os.system",
        "check_output",
        "check_call",
        "shutil",
        "copytree",
    ):
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
