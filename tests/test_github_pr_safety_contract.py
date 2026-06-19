"""Tests for AUTO.2b — GitHub Remote PR Safety Contract (report-only).

AUTO.2b reads one upstream evidence artifact (an AUTO.1e self-evolution evidence
pack or an AUTO.2a evidence summary contract) and shapes a contract describing
what must be true before a *future* system may draft a remote pull request. It
defines the safety contract; it does not contact a remote git host, create
branches, push commits, open or merge PRs, call webhooks, make network calls,
call models, apply patches, run validation or a benchmark check, or contact a
chat app / n8n. A future PR is never merge authority.

Covers the prescribed cases:
1.  ready evidence pack allows a future draft PR but not merge.
2.  needs_more_validation blocks draft-PR readiness.
3.  blocked source blocks PR readiness.
4.  incomplete source blocks PR readiness.
5.  allow-blocked-contract writes the report but keeps a PR not allowed.
6.  a hard guardrail breach blocks PR readiness.
7.  merge and auto-merge are always false.
8.  pr_created / branch_created / github_contacted / network_call_performed are always false.
9.  forbidden actions include push / merge / auto-merge / bypass protection / apply patch / model / worker / remote contact.
10. required checks include human review / branch protection / validation evidence / evidence pack / no direct main push.
11. Markdown contains all required sections and boundaries.
12. CLI writes JSON + Markdown.
13. CLI exits nonzero for a blocked source unless the allow flag is used.
14. deterministic output with fixed contract_id/created_at.
15. the source artifact is not modified.
16. source contains no forbidden execution/network/model/patch/git/remote-send tokens.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.github_pr_safety_contract import (
    ALLOWED_FUTURE_ACTIONS,
    FORBIDDEN_ACTIONS,
    GITHUB_PR_SAFETY_GUARDRAIL_NOTE,
    REPORT_KIND,
    build_github_pr_safety_contract,
    render_github_pr_safety_contract_markdown,
    write_github_pr_safety_contract,
)
import scripts.create_github_pr_safety_contract as script


# ── synthetic source-artifact builders ─────────────────────────────────────────

def _evidence_pack(**over) -> dict:
    """A realistic AUTO.1e evidence-pack record (ready-for-review by default)."""
    pack = {
        "report_kind": "sandbox_self_evolution_evidence_pack",
        "pack_id": "pack-1",
        "created_at": "2026-06-19T00:00:00+00:00",
        "trial_id": "trial-abc",
        "final_verdict": "ready_for_human_review",
        "recommended_next_step": "review_patch_candidate",
        "source_artifacts": [
            {
                "kind": "contract",
                "label": "Contract",
                "report_kind": "sandbox_self_evolution_trial",
                "verdict": "ready_for_sandbox",
                "path": ".agent/self_evolution_trials/trial-abc/self_evolution_trial.json",
            },
            {
                "kind": "graduation_review",
                "label": "Graduation review",
                "report_kind": "sandbox_patch_graduation_review",
                "verdict": "eligible_for_human_review",
                "path": ".agent/self_evolution_trials/trial-abc/patch_graduation_review.json",
            },
        ],
        "missing_artifacts": [],
        "risk_summary": {
            "safety": "no hard safety breach detected across 4 present artifact(s)",
            "scope": "automation level SANDBOX_2_DRAFT_PATCH; patch touches 1 file(s)",
            "validation": "declared validation ran in the sandbox",
            "side_effects": "sandbox-only: patch (created 1, modified 0, deleted 0)",
            "budget_or_model_use": "no model call reported; report-only / local budget",
            "human_gate": "intact: human approval required, no self-approval, no auto-merge",
        },
        "human_review_packet": {
            "phase_or_objective": "AUTO.1f — smoke demo: create a demo file",
            "patch_touched_files": ["pkg/auto1f_smoke_demo.txt"],
            "patch_size": "3 changed lines across 1 files",
            "validation_status": "ran",
            "sandbox_side_effects": {
                "patch": {"created": 1, "modified": 0, "deleted": 0},
                "validation": {"created": 0, "modified": 0, "deleted": 0},
            },
            "graduation_decision": "eligible_for_human_review -> review_patch_candidate",
            "inspect_manually": "Inspect the touched files and the sandbox validation result.",
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
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "worker_launch_performed": False,
    }
    pack.update(over)
    return pack


def _needs_more_validation_pack(**over) -> dict:
    return _evidence_pack(
        final_verdict="needs_more_validation",
        recommended_next_step="request_more_validation",
        warnings=["validation was skipped in the dry run; more validation is recommended before review"],
        **over,
    )


def _blocked_pack(**over) -> dict:
    return _evidence_pack(
        final_verdict="blocked",
        recommended_next_step="reject_candidate",
        blockers=["the graduation review artifact reports a merge was performed (merge_performed)"],
        **over,
    )


def _incomplete_pack(**over) -> dict:
    return _evidence_pack(
        final_verdict="incomplete_pack",
        recommended_next_step="complete_missing_artifacts",
        missing_artifacts=["graduation_review"],
        source_artifacts=[
            {
                "kind": "contract",
                "label": "Contract",
                "report_kind": "sandbox_self_evolution_trial",
                "verdict": "ready_for_sandbox",
                "path": "a.json",
            }
        ],
        **over,
    )


def _telegram_contract_source(**over) -> dict:
    """A realistic AUTO.2a evidence-summary contract used as the source artifact."""
    src = {
        "report_kind": "telegram_evidence_contract",
        "contract_id": "tg-1",
        "created_at": "2026-06-19T00:00:00+00:00",
        "trial_id": "trial-abc",
        "final_verdict": "ready_for_human_review",
        "recommended_next_step": "review_patch_candidate",
        "risk_summary": {
            "safety": "no hard safety breach detected",
            "scope": "patch touches 1 file(s)",
            "validation": "declared validation ran in the sandbox",
            "side_effects": "sandbox-only",
            "budget_or_model_use": "no model call reported",
            "human_gate": "intact",
            "merge_authority": "chat approval is not merge authority",
        },
        "evidence_links": [
            {"label": "Evidence pack", "path": ".agent/self_evolution_trials/trial-abc/self_evolution_evidence_pack.json"},
            {"label": "Graduation review", "path": ".agent/self_evolution_trials/trial-abc/patch_graduation_review.json"},
        ],
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


def _contract(artifact=None, **kw) -> dict:
    if artifact is None:
        artifact = _evidence_pack()
    return build_github_pr_safety_contract(artifact=artifact, **kw)


def _write_artifact(tmp_path: Path, artifact: dict, name: str = "source_artifact.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return path


# ── 1. ready pack allows a future draft PR but not merge ───────────────────────

def test_ready_source_allows_future_draft_pr_not_merge():
    contract = _contract(_evidence_pack(), contract_id="c", created_at="t")
    assert contract["is_pr_draft_allowed_in_future"] is True
    assert contract["is_merge_allowed"] is False
    assert contract["is_auto_merge_allowed"] is False
    assert contract["pr_readiness"]["status"] == "draft_pr_allowed_after_human_review"
    assert contract["blockers"] == []
    assert contract["final_verdict"] == "ready_for_human_review"
    assert contract["trial_id"] == "trial-abc"
    assert contract["report_kind"] == REPORT_KIND == "github_pr_safety_contract"


def test_contract_has_all_required_fields():
    contract = _contract(
        _evidence_pack(),
        contract_id="cid",
        created_at="2026-06-19T00:00:00+00:00",
        source_artifact="packs/evidence.json",
    )
    for key in (
        "contract_id",
        "created_at",
        "source_artifact",
        "source_kind",
        "trial_id",
        "final_verdict",
        "recommended_next_step",
        "pr_readiness",
        "required_checks",
        "required_branch_protection",
        "required_human_checks",
        "forbidden_actions",
        "allowed_future_actions",
        "risk_summary",
        "evidence_links",
        "guardrails",
        "is_pr_draft_allowed_in_future",
        "is_merge_allowed",
        "is_auto_merge_allowed",
        "blockers",
        "warnings",
    ):
        assert key in contract, key
    assert contract["contract_id"] == "cid"
    assert contract["created_at"] == "2026-06-19T00:00:00+00:00"
    assert contract["source_artifact"] == "packs/evidence.json"


# ── 2. needs_more_validation blocks draft-PR readiness ─────────────────────────

def test_needs_more_validation_blocks_draft_pr():
    contract = _contract(_needs_more_validation_pack())
    assert contract["is_pr_draft_allowed_in_future"] is False
    assert contract["is_merge_allowed"] is False
    assert contract["is_auto_merge_allowed"] is False
    assert contract["pr_readiness"]["status"] == "needs_more_validation"
    assert contract["blockers"]
    assert any("validation" in b.lower() for b in contract["blockers"])


# ── 3-4. blocked / incomplete block PR readiness ───────────────────────────────

def test_blocked_source_blocks_pr_readiness():
    contract = _contract(_blocked_pack())
    assert contract["is_pr_draft_allowed_in_future"] is False
    assert contract["is_merge_allowed"] is False
    assert contract["is_auto_merge_allowed"] is False
    assert contract["pr_readiness"]["status"] == "blocked"
    assert contract["blockers"]
    assert contract["final_verdict"] == "blocked"


def test_incomplete_source_blocks_pr_readiness():
    contract = _contract(_incomplete_pack())
    assert contract["is_pr_draft_allowed_in_future"] is False
    assert contract["pr_readiness"]["status"] == "incomplete"
    assert contract["blockers"]


def test_malformed_source_blocks_pr_readiness():
    for bad in (None, {}, [], "nope", 5):
        contract = build_github_pr_safety_contract(artifact=bad)
        assert contract["is_pr_draft_allowed_in_future"] is False
        assert contract["is_merge_allowed"] is False
        assert contract["is_auto_merge_allowed"] is False
        assert contract["blockers"]
        assert contract["final_verdict"] == "incomplete_pack"


# ── 6. hard guardrail breach blocks PR readiness ───────────────────────────────

def test_hard_guardrail_breach_blocks_pr_readiness():
    # Verdict says ready, but a guardrail boolean reports a breach -> not ready.
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
        pack = _evidence_pack(**{field: True})
        contract = _contract(pack)
        assert contract["is_pr_draft_allowed_in_future"] is False, field
        assert contract["pr_readiness"]["status"] == "blocked", field
        assert any(field in b for b in contract["blockers"]), field


def test_missing_human_review_required_blocks_pr_readiness():
    contract = _contract(_evidence_pack(human_review_required=False))
    assert contract["is_pr_draft_allowed_in_future"] is False
    assert contract["pr_readiness"]["status"] == "blocked"


def test_source_blockers_block_pr_readiness_even_if_verdict_ready():
    pack = _evidence_pack(blockers=["the dry run reports side effects that were not sandbox-only"])
    contract = _contract(pack)
    assert contract["is_pr_draft_allowed_in_future"] is False
    assert any("sandbox-only" in b for b in contract["blockers"])


# ── 7. merge and auto-merge are always false ───────────────────────────────────

def test_merge_and_auto_merge_are_always_false():
    for art in (
        _evidence_pack(),
        _needs_more_validation_pack(),
        _blocked_pack(),
        _incomplete_pack(),
        _evidence_pack(eligible_for_auto_merge=True),
        _telegram_contract_source(),
        {},
    ):
        contract = build_github_pr_safety_contract(artifact=art)
        assert contract["is_merge_allowed"] is False
        assert contract["is_auto_merge_allowed"] is False
        assert contract["pr_readiness"]["merge_allowed"] is False
        assert contract["pr_readiness"]["auto_merge_allowed"] is False


# ── 8 + guardrails. remote/branch/network booleans are always false ────────────

_EXPECTED_GUARDRAILS = {
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
}


def test_guardrail_booleans_are_preserved():
    for art in (_evidence_pack(), _blocked_pack(), _incomplete_pack(), _evidence_pack(push_performed=True), {}):
        guardrails = build_github_pr_safety_contract(artifact=art)["guardrails"]
        assert guardrails == _EXPECTED_GUARDRAILS


def test_remote_and_creation_booleans_are_always_false():
    for art in (_evidence_pack(), _blocked_pack(), _needs_more_validation_pack(), _telegram_contract_source()):
        guardrails = build_github_pr_safety_contract(artifact=art)["guardrails"]
        assert guardrails["pr_created"] is False
        assert guardrails["branch_created"] is False
        assert guardrails["github_contacted"] is False
        assert guardrails["network_call_performed"] is False
        assert guardrails["push_performed"] is False
        assert guardrails["merge_performed"] is False


# ── 9. forbidden actions include the dangerous operations ──────────────────────

def test_forbidden_actions_include_dangerous_operations():
    actions = _contract(_evidence_pack())["forbidden_actions"]
    assert set(actions) == set(FORBIDDEN_ACTIONS)
    for action in (
        "push_to_main",
        "force_push",
        "open_pr_without_human_review",
        "merge_pr",
        "enable_auto_merge",
        "bypass_branch_protection",
        "apply_patch_to_real_repo",
        "launch_worker",
        "call_model",
        "contact_remote_service",
    ):
        assert action in actions, action


# ── allowed future actions are informational only ──────────────────────────────

def test_allowed_future_actions_are_informational_only():
    contract = _contract(_evidence_pack())
    actions = contract["allowed_future_actions"]
    assert set(actions) == set(ALLOWED_FUTURE_ACTIONS)
    assert set(ALLOWED_FUTURE_ACTIONS) == {
        "prepare_draft_pr_after_human_review",
        "request_more_validation",
        "reject_candidate",
        "keep_local_only",
    }
    joined = " ".join(actions)
    for bad in ("push_to_main", "force_push", "merge_pr", "enable_auto_merge", "bypass_branch_protection"):
        assert bad not in joined, bad


def test_needs_more_validation_emphasises_request_more_validation():
    contract = _contract(_needs_more_validation_pack())
    assert contract["allowed_future_actions"][0] == "request_more_validation"


# ── 10. required checks / branch protection / human checks ─────────────────────

def test_required_checks_include_required_concepts():
    checks = _contract(_evidence_pack())["required_checks"]
    assert isinstance(checks, list) and checks
    joined = " ".join(checks).lower()
    assert "human review" in joined
    assert "branch protection" in joined
    assert "validation" in joined
    assert "evidence pack" in joined
    assert "no direct push" in joined and "main" in joined


def test_required_branch_protection_present():
    protections = _contract(_evidence_pack())["required_branch_protection"]
    assert isinstance(protections, list) and protections
    joined = " ".join(protections).lower()
    assert "review" in joined
    assert "merge" in joined


def test_required_human_checks_present():
    checks = _contract(_evidence_pack())["required_human_checks"]
    assert isinstance(checks, list) and checks
    assert "human review" in " ".join(checks).lower() or "review" in " ".join(checks).lower()


# ── evidence links / risk summary / source kind ────────────────────────────────

def test_evidence_links_point_at_source_and_artifacts():
    contract = _contract(_evidence_pack(), source_artifact="packs/evidence.json")
    links = contract["evidence_links"]
    assert isinstance(links, list) and links
    paths = " ".join(str(link.get("path", "")) for link in links)
    assert "packs/evidence.json" in paths
    assert "patch_graduation_review.json" in paths


def test_risk_summary_carries_source_risk_and_merge_note():
    risk = _contract(_evidence_pack())["risk_summary"]
    assert isinstance(risk, dict)
    for key in ("safety", "scope", "validation", "side_effects"):
        assert key in risk
    joined = " ".join(str(v) for v in risk.values()).lower()
    assert "merge authority" in joined


def test_source_kind_detected_for_pack_and_contract():
    pack_contract = _contract(_evidence_pack())
    assert pack_contract["source_kind"] == "self_evolution_evidence_pack"
    tg_contract = _contract(_telegram_contract_source())
    assert tg_contract["source_kind"] == "telegram_evidence_contract"


def test_telegram_contract_source_ready_allows_draft_pr():
    contract = _contract(_telegram_contract_source())
    assert contract["is_pr_draft_allowed_in_future"] is True
    assert contract["is_merge_allowed"] is False
    # evidence links from the AUTO.2a contract are carried through
    paths = " ".join(str(link.get("path", "")) for link in contract["evidence_links"])
    assert "patch_graduation_review.json" in paths


def test_telegram_contract_source_blocked_blocks_pr():
    src = _telegram_contract_source(final_verdict="blocked", send_blockers=["the pack verdict is blocked"])
    contract = _contract(src)
    assert contract["is_pr_draft_allowed_in_future"] is False
    assert contract["blockers"]


def test_guardrail_note_is_report_only():
    assert "report-only" in GITHUB_PR_SAFETY_GUARDRAIL_NOTE.lower()
    assert _contract(_evidence_pack())["guardrail_note"] == GITHUB_PR_SAFETY_GUARDRAIL_NOTE


# ── 15. the source artifact is not modified ────────────────────────────────────

def test_build_does_not_mutate_input_artifact():
    pack = _evidence_pack()
    snap = copy.deepcopy(pack)
    build_github_pr_safety_contract(artifact=pack, contract_id="c", created_at="t")
    assert pack == snap


# ── 11. Markdown contains all sections and boundaries ──────────────────────────

def test_markdown_contains_all_sections():
    md = render_github_pr_safety_contract_markdown(_contract(_evidence_pack(), contract_id="c", created_at="t"))
    assert "# GitHub Remote PR Safety Contract" in md
    low = md.lower()
    for section in (
        "## summary",
        "## pr readiness",
        "## required checks",
        "## required branch protection",
        "## required human checks",
        "## risk summary",
        "## evidence links",
        "## blockers",
        "## warnings",
        "## forbidden actions",
        "## allowed future actions",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    low = render_github_pr_safety_contract_markdown(_contract(_evidence_pack())).lower()
    assert "does not contact github" in low
    assert "does not create branches" in low
    assert "does not push commits" in low
    assert "does not open prs" in low
    assert "does not merge prs" in low
    assert "does not call webhooks" in low
    assert "does not call models" in low
    assert "does not apply patches" in low
    assert "does not run validation or benchmarks" in low
    assert "telegram" in low and "n8n" in low
    assert "not merge authority" in low
    assert "human review and branch protection remain required" in low


def test_markdown_shows_blocked_blockers():
    md = render_github_pr_safety_contract_markdown(_contract(_blocked_pack())).lower()
    assert "blocked" in md or "merge_performed" in md


# ── 12-14. CLI behaviour ───────────────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    art_path = _write_artifact(tmp_path, _evidence_pack())
    out = tmp_path / "out"
    res = script.run_create_github_pr_safety_contract(
        source_artifact=str(art_path),
        output_root=str(out),
        contract_id="cli",
        created_at="2026-06-19T00:00:00+00:00",
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "github_pr_safety_contract.json"
    assert mp.name == "github_pr_safety_contract.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["contract_id"] == "cli"
    assert data["source_artifact"] == str(art_path)
    assert data["is_pr_draft_allowed_in_future"] is True


def test_cli_main_smoke(tmp_path):
    art_path = _write_artifact(tmp_path, _evidence_pack())
    out = tmp_path / "out"
    code = script.main(
        ["--source-artifact", str(art_path), "--output-root", str(out), "--contract-id", "s", "--created-at", "t"]
    )
    assert code == 0
    assert (out / "github_pr_safety_contract.json").is_file()
    assert (out / "github_pr_safety_contract.md").is_file()


def test_cli_exits_nonzero_for_blocked_source(tmp_path):
    art_path = _write_artifact(tmp_path, _blocked_pack())
    out = tmp_path / "out"
    code = script.main(
        ["--source-artifact", str(art_path), "--output-root", str(out), "--contract-id", "x", "--created-at", "t"]
    )
    assert code != 0
    assert (out / "github_pr_safety_contract.json").is_file()


def test_cli_exits_nonzero_for_incomplete_source(tmp_path):
    art_path = _write_artifact(tmp_path, _incomplete_pack())
    out = tmp_path / "out"
    code = script.main(
        ["--source-artifact", str(art_path), "--output-root", str(out), "--contract-id", "x", "--created-at", "t"]
    )
    assert code != 0


def test_cli_allow_blocked_contract_returns_zero_but_keeps_pr_not_allowed(tmp_path):
    art_path = _write_artifact(tmp_path, _blocked_pack())
    out = tmp_path / "out"
    code = script.main(
        [
            "--source-artifact", str(art_path),
            "--output-root", str(out),
            "--contract-id", "x",
            "--created-at", "t",
            "--allow-blocked-contract",
        ]
    )
    assert code == 0
    data = json.loads((out / "github_pr_safety_contract.json").read_text(encoding="utf-8"))
    assert data["is_pr_draft_allowed_in_future"] is False
    assert data["is_merge_allowed"] is False


def test_cli_missing_source_is_not_allowed_and_nonzero(tmp_path):
    out = tmp_path / "out"
    code = script.main(
        ["--source-artifact", str(tmp_path / "nope.json"), "--output-root", str(out), "--contract-id", "x", "--created-at", "t"]
    )
    assert code != 0
    data = json.loads((out / "github_pr_safety_contract.json").read_text(encoding="utf-8"))
    assert data["is_pr_draft_allowed_in_future"] is False
    assert data["blockers"]


def test_cli_json_flag_prints_contract(tmp_path, capsys):
    art_path = _write_artifact(tmp_path, _evidence_pack())
    out = tmp_path / "out"
    code = script.main(
        ["--source-artifact", str(art_path), "--output-root", str(out), "--contract-id", "j", "--created-at", "t", "--json"]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["contract_id"] == "j"
    assert printed["report_kind"] == "github_pr_safety_contract"


def test_cli_detects_telegram_contract_source(tmp_path):
    art_path = _write_artifact(tmp_path, _telegram_contract_source(), name="telegram_evidence_contract.json")
    out = tmp_path / "out"
    res = script.run_create_github_pr_safety_contract(
        source_artifact=str(art_path),
        output_root=str(out),
        contract_id="tg",
        created_at="t",
    )
    assert res["contract"]["source_kind"] == "telegram_evidence_contract"
    assert res["contract"]["is_pr_draft_allowed_in_future"] is True


def test_cli_deterministic_output(tmp_path):
    art_path = _write_artifact(tmp_path, _evidence_pack())

    def run(name: str) -> str:
        res = script.run_create_github_pr_safety_contract(
            source_artifact=str(art_path),
            output_root=str(tmp_path / name),
            contract_id="fixed",
            created_at="2026-06-19T12:00:00+00:00",
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


def test_cli_does_not_modify_source_artifact(tmp_path):
    pack = _evidence_pack()
    art_path = _write_artifact(tmp_path, pack)
    before = art_path.read_bytes()
    out = tmp_path / "out"
    script.main(
        ["--source-artifact", str(art_path), "--output-root", str(out), "--contract-id", "x", "--created-at", "t"]
    )
    assert art_path.read_bytes() == before


def test_write_core_helper(tmp_path):
    out = tmp_path / "core_out"
    res = write_github_pr_safety_contract(
        _evidence_pack(), str(out), contract_id="cr", created_at="t", source_artifact="p.json"
    )
    assert res["ok"] is True
    assert Path(res["json_path"]).is_file()
    assert Path(res["md_path"]).is_file()
    assert res["contract"]["contract_id"] == "cr"


# ── 16. forbidden-token / import guards (source-only) ──────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "github_pr_safety_contract.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_github_pr_safety_contract.py"
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
            assert top != "core", f"AUTO.2b core must not import other core modules: {module!r}"
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
    # Behaviour tokens only: the *call* shapes. The forbidden-action data value
    # "apply_patch_to_real_repo" is allowed — it declares what is NOT done.
    for bad in ("generate_patch", "apply_patch(", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_network_github_send_or_git_behaviour():
    # No network library, no webhook, no GitHub API/CLI, no git subcommands, no
    # chat-app send, no n8n. Bare "github"/"git"/"telegram"/"n8n" are NOT forbidden
    # (they are required field names / prose); the *call / command / API* shapes are.
    for bad in (
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
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
        "sendMessage",
        "bot_token",
        "api.telegram.org",
        "n8n",
    ):
        assert bad not in _BOTH, f"Found network/github/git token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    # "launch_worker" appears as a forbidden-action DATA value, so only the *call*
    # shapes are forbidden in source.
    for bad in ("import_proposal", "proposal_runner", "launch_worker(", "worker_launch(", "spawn_worker", "run_worker("):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    # "enable_auto_merge" is a forbidden-action DATA value; only the call shape
    # "auto_merge(" is forbidden in source.
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"


# ── constants exposure ─────────────────────────────────────────────────────────

def test_forbidden_actions_constant_matches_spec():
    for action in (
        "push_to_main",
        "force_push",
        "open_pr_without_human_review",
        "merge_pr",
        "enable_auto_merge",
        "bypass_branch_protection",
        "apply_patch_to_real_repo",
        "launch_worker",
        "call_model",
        "contact_remote_service",
    ):
        assert action in FORBIDDEN_ACTIONS, action


def test_allowed_future_actions_constant_matches_spec():
    assert set(ALLOWED_FUTURE_ACTIONS) == {
        "prepare_draft_pr_after_human_review",
        "request_more_validation",
        "reject_candidate",
        "keep_local_only",
    }
