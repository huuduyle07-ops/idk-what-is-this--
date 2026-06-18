"""Tests for AUTO.2a — Telegram Evidence Summary Contract (report-only).

AUTO.2a reads an AUTO.1e sandbox self-evolution evidence pack and shapes a compact
evidence-summary message plus a contract describing what a human may (and may not)
do on the strength of that summary. It defines the summary; it does not contact a
chat app, send messages, call webhooks, make network calls, call models, apply
patches, run validation or a benchmark check, push, merge, open PRs, or contact a
remote git host / n8n / external automation. Chat approval is never merge authority.

Covers the prescribed cases:
1.  ready evidence pack creates a sendable summary.
2.  needs_more_validation creates a sendable summary that emphasises request_more_validation.
3.  blocked evidence pack is not sendable by default.
4.  incomplete evidence pack is not sendable by default.
5.  allow-blocked-summary permits report creation but keeps sendable false.
6.  a hard guardrail breach blocks sendability.
7.  approval options never include merge/push/apply/run options.
8.  forbidden actions include merge/push/apply/model/worker/network.
9.  guardrail booleans are preserved.
10. telegram_message_sent is always false.
11. network_call_performed is always false.
12. Markdown contains all required sections and boundaries.
13. CLI writes JSON + Markdown.
14. CLI exits nonzero for a blocked source unless the allow flag is used.
15. deterministic output with fixed contract_id/created_at.
16. the source evidence pack is not modified.
17. source contains no forbidden execution/network/model/patch/chat-send tokens.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.telegram_evidence_contract import (
    APPROVAL_OPTIONS,
    FORBIDDEN_ACTIONS,
    REPORT_KIND,
    TELEGRAM_EVIDENCE_GUARDRAIL_NOTE,
    build_telegram_evidence_contract,
    render_telegram_evidence_contract_markdown,
    write_telegram_evidence_contract,
)
import scripts.create_telegram_evidence_contract as script


# ── synthetic evidence-pack builders ───────────────────────────────────────────

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


def _contract(pack=None, **kw) -> dict:
    if pack is None:
        pack = _evidence_pack()
    return build_telegram_evidence_contract(evidence_pack=pack, **kw)


def _write_pack(tmp_path: Path, pack: dict, name: str = "self_evolution_evidence_pack.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    return path


# ── 1. ready pack creates a sendable summary ───────────────────────────────────

def test_ready_pack_creates_sendable_summary():
    contract = _contract(_evidence_pack(), contract_id="c", created_at="t")
    assert contract["is_sendable"] is True
    assert contract["send_blockers"] == []
    assert contract["final_verdict"] == "ready_for_human_review"
    assert contract["trial_id"] == "trial-abc"
    assert contract["report_kind"] == REPORT_KIND == "telegram_evidence_contract"


def test_contract_has_all_required_fields():
    contract = _contract(
        _evidence_pack(),
        contract_id="cid",
        created_at="2026-06-19T00:00:00+00:00",
        source_evidence_pack="packs/evidence.json",
    )
    for key in (
        "contract_id",
        "created_at",
        "source_evidence_pack",
        "trial_id",
        "final_verdict",
        "recommended_next_step",
        "telegram_message",
        "approval_options",
        "forbidden_actions",
        "required_human_checks",
        "risk_summary",
        "evidence_links",
        "guardrails",
        "is_sendable",
        "send_blockers",
        "warnings",
    ):
        assert key in contract, key
    assert contract["contract_id"] == "cid"
    assert contract["created_at"] == "2026-06-19T00:00:00+00:00"
    assert contract["source_evidence_pack"] == "packs/evidence.json"


def test_telegram_message_summarises_key_fields():
    contract = _contract(_evidence_pack())
    message = contract["telegram_message"]
    low = message.lower()
    assert "trial-abc" in low
    assert "ready_for_human_review" in low
    assert "review_patch_candidate" in low
    # changed/touched files surfaced
    assert "auto1f_smoke_demo.txt" in low
    # validation status + side-effect summary surfaced
    assert "validation" in low
    # human action options surfaced
    assert "review" in low


def test_telegram_message_states_human_review_and_not_merge_authority():
    # Rules 5 & 6: never imply chat approval is enough to merge; state that human
    # review / branch protection / local evidence remain required.
    message = _contract(_evidence_pack())["telegram_message"].lower()
    assert "human review" in message
    assert "not merge authority" in message
    assert "branch protection" in message


# ── 2. needs_more_validation is sendable with emphasis ─────────────────────────

def test_needs_more_validation_is_sendable_with_emphasis():
    contract = _contract(_needs_more_validation_pack())
    assert contract["is_sendable"] is True
    assert contract["final_verdict"] == "needs_more_validation"
    # request_more_validation is emphasised: ranked first in the options.
    assert contract["approval_options"][0] == "request_more_validation"
    assert "request_more_validation" in contract["telegram_message"]


# ── 3-4. blocked / incomplete are not sendable by default ──────────────────────

def test_blocked_pack_is_not_sendable_by_default():
    contract = _contract(_blocked_pack())
    assert contract["is_sendable"] is False
    assert contract["send_blockers"]
    assert contract["final_verdict"] == "blocked"


def test_incomplete_pack_is_not_sendable_by_default():
    contract = _contract(_incomplete_pack())
    assert contract["is_sendable"] is False
    assert contract["send_blockers"]


def test_malformed_pack_is_not_sendable():
    for bad in (None, {}, [], "nope", 5):
        contract = build_telegram_evidence_contract(evidence_pack=bad)
        assert contract["is_sendable"] is False
        assert contract["send_blockers"]


# ── 6. hard guardrail breach blocks sendability ────────────────────────────────

def test_hard_guardrail_breach_blocks_sendability():
    # Verdict says ready, but a guardrail boolean reports a breach -> not sendable.
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
        assert contract["is_sendable"] is False, field
        assert any(field in b for b in contract["send_blockers"]), field


def test_missing_human_review_required_blocks_sendability():
    contract = _contract(_evidence_pack(human_review_required=False))
    assert contract["is_sendable"] is False


def test_pack_blockers_block_sendability_even_if_verdict_ready():
    pack = _evidence_pack(blockers=["the dry run reports side effects that were not sandbox-only"])
    contract = _contract(pack)
    assert contract["is_sendable"] is False
    assert any("sandbox-only" in b for b in contract["send_blockers"])


# ── 7. approval options never include dangerous options ────────────────────────

def test_approval_options_are_informational_only():
    contract = _contract(_evidence_pack())
    options = contract["approval_options"]
    assert set(options) == set(APPROVAL_OPTIONS)
    assert set(APPROVAL_OPTIONS) == {"review", "defer", "reject", "request_more_validation"}


def test_approval_options_never_include_merge_push_apply_run():
    for pack in (_evidence_pack(), _needs_more_validation_pack(), _blocked_pack()):
        options = _contract(pack)["approval_options"]
        joined = " ".join(options)
        for bad in ("approve_merge", "push", "apply_patch", "apply", "run_worker", "launch_model", "merge"):
            assert bad not in joined, (bad, options)


# ── 8. forbidden actions include the dangerous operations ──────────────────────

def test_forbidden_actions_include_dangerous_operations():
    actions = _contract(_evidence_pack())["forbidden_actions"]
    assert set(actions) == set(FORBIDDEN_ACTIONS)
    joined = " ".join(actions)
    for concept in ("merge", "push", "apply", "launch_model", "run_worker", "network"):
        assert concept in joined, concept


# ── 9-11. guardrail booleans are preserved / always false ──────────────────────

_EXPECTED_GUARDRAILS = {
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
}


def test_guardrail_booleans_are_preserved():
    # Output guardrails are constant regardless of the input pack's contents.
    for pack in (_evidence_pack(), _blocked_pack(), _incomplete_pack(), _evidence_pack(push_performed=True)):
        guardrails = _contract(pack)["guardrails"]
        assert guardrails == _EXPECTED_GUARDRAILS


def test_telegram_message_sent_is_always_false():
    for pack in (_evidence_pack(), _blocked_pack(), _needs_more_validation_pack()):
        assert _contract(pack)["guardrails"]["telegram_message_sent"] is False


def test_network_call_performed_is_always_false():
    for pack in (_evidence_pack(), _blocked_pack(), _incomplete_pack()):
        assert _contract(pack)["guardrails"]["network_call_performed"] is False


# ── evidence links / required checks / risk summary ────────────────────────────

def test_evidence_links_point_at_the_pack_and_artifacts():
    contract = _contract(_evidence_pack(), source_evidence_pack="packs/evidence.json")
    links = contract["evidence_links"]
    assert isinstance(links, list) and links
    paths = " ".join(str(link.get("path", "")) for link in links)
    assert "packs/evidence.json" in paths
    assert "patch_graduation_review.json" in paths


def test_required_human_checks_present():
    checks = _contract(_evidence_pack())["required_human_checks"]
    assert isinstance(checks, list) and checks
    joined = " ".join(checks).lower()
    assert "human review" in joined or "review" in joined


def test_risk_summary_carries_pack_risk_and_merge_note():
    risk = _contract(_evidence_pack())["risk_summary"]
    assert isinstance(risk, dict)
    for key in ("safety", "scope", "validation", "side_effects"):
        assert key in risk
    # an explicit note that chat approval is not merge authority
    joined = " ".join(str(v) for v in risk.values()).lower()
    assert "merge authority" in joined


def test_guardrail_note_is_report_only():
    assert "report-only" in TELEGRAM_EVIDENCE_GUARDRAIL_NOTE.lower()
    assert _contract(_evidence_pack())["guardrail_note"] == TELEGRAM_EVIDENCE_GUARDRAIL_NOTE


# ── 16. the source evidence pack is not modified ───────────────────────────────

def test_build_does_not_mutate_input_pack():
    pack = _evidence_pack()
    snap = copy.deepcopy(pack)
    build_telegram_evidence_contract(evidence_pack=pack, contract_id="c", created_at="t")
    assert pack == snap


# ── 12. Markdown contains all sections and boundaries ──────────────────────────

def test_markdown_contains_all_sections():
    md = render_telegram_evidence_contract_markdown(_contract(_evidence_pack(), contract_id="c", created_at="t"))
    assert "# Telegram Evidence Summary Contract" in md
    low = md.lower()
    for section in (
        "## summary",
        "## telegram message preview",
        "## approval options",
        "## required human checks",
        "## risk summary",
        "## evidence links",
        "## send blockers",
        "## warnings",
        "## forbidden actions",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    low = render_telegram_evidence_contract_markdown(_contract(_evidence_pack())).lower()
    assert "does not contact telegram" in low
    assert "does not send messages" in low
    assert "does not call webhooks" in low
    assert "does not call models" in low
    assert "does not apply patches" in low
    assert "does not run validation or benchmarks" in low
    assert "does not push, merge" in low
    assert "github" in low and "n8n" in low
    assert "not merge authority" in low


def test_markdown_shows_blocked_send_blockers():
    md = render_telegram_evidence_contract_markdown(_contract(_blocked_pack())).lower()
    assert "merge_performed" in md or "blocked" in md


# ── 13-14-15. CLI behaviour ────────────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    pack_path = _write_pack(tmp_path, _evidence_pack())
    out = tmp_path / "out"
    res = script.run_create_telegram_evidence_contract(
        evidence_pack=str(pack_path),
        output_root=str(out),
        contract_id="cli",
        created_at="2026-06-19T00:00:00+00:00",
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "telegram_evidence_contract.json"
    assert mp.name == "telegram_evidence_contract.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["contract_id"] == "cli"
    assert data["source_evidence_pack"] == str(pack_path)
    assert data["is_sendable"] is True


def test_cli_main_smoke(tmp_path):
    pack_path = _write_pack(tmp_path, _evidence_pack())
    out = tmp_path / "out"
    code = script.main(
        ["--evidence-pack", str(pack_path), "--output-root", str(out), "--contract-id", "s", "--created-at", "t"]
    )
    assert code == 0
    assert (out / "telegram_evidence_contract.json").is_file()
    assert (out / "telegram_evidence_contract.md").is_file()


def test_cli_exits_nonzero_for_blocked_source(tmp_path):
    pack_path = _write_pack(tmp_path, _blocked_pack())
    out = tmp_path / "out"
    code = script.main(
        ["--evidence-pack", str(pack_path), "--output-root", str(out), "--contract-id", "x", "--created-at", "t"]
    )
    assert code != 0
    # the artifact is still written
    assert (out / "telegram_evidence_contract.json").is_file()


def test_cli_exits_nonzero_for_incomplete_source(tmp_path):
    pack_path = _write_pack(tmp_path, _incomplete_pack())
    out = tmp_path / "out"
    code = script.main(
        ["--evidence-pack", str(pack_path), "--output-root", str(out), "--contract-id", "x", "--created-at", "t"]
    )
    assert code != 0


def test_cli_allow_blocked_summary_returns_zero_but_keeps_sendable_false(tmp_path):
    pack_path = _write_pack(tmp_path, _blocked_pack())
    out = tmp_path / "out"
    code = script.main(
        [
            "--evidence-pack", str(pack_path),
            "--output-root", str(out),
            "--contract-id", "x",
            "--created-at", "t",
            "--allow-blocked-summary",
        ]
    )
    assert code == 0
    data = json.loads((out / "telegram_evidence_contract.json").read_text(encoding="utf-8"))
    assert data["is_sendable"] is False


def test_cli_missing_pack_is_not_sendable_and_nonzero(tmp_path):
    out = tmp_path / "out"
    code = script.main(
        ["--evidence-pack", str(tmp_path / "nope.json"), "--output-root", str(out), "--contract-id", "x", "--created-at", "t"]
    )
    assert code != 0
    data = json.loads((out / "telegram_evidence_contract.json").read_text(encoding="utf-8"))
    assert data["is_sendable"] is False
    assert data["send_blockers"]


def test_cli_json_flag_prints_contract(tmp_path, capsys):
    pack_path = _write_pack(tmp_path, _evidence_pack())
    out = tmp_path / "out"
    code = script.main(
        ["--evidence-pack", str(pack_path), "--output-root", str(out), "--contract-id", "j", "--created-at", "t", "--json"]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["contract_id"] == "j"
    assert printed["report_kind"] == "telegram_evidence_contract"


def test_cli_deterministic_output(tmp_path):
    pack_path = _write_pack(tmp_path, _evidence_pack())

    def run(name: str) -> str:
        res = script.run_create_telegram_evidence_contract(
            evidence_pack=str(pack_path),
            output_root=str(tmp_path / name),
            contract_id="fixed",
            created_at="2026-06-19T12:00:00+00:00",
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


def test_cli_does_not_modify_source_pack(tmp_path):
    pack = _evidence_pack()
    pack_path = _write_pack(tmp_path, pack)
    before = pack_path.read_bytes()
    out = tmp_path / "out"
    script.main(
        ["--evidence-pack", str(pack_path), "--output-root", str(out), "--contract-id", "x", "--created-at", "t"]
    )
    assert pack_path.read_bytes() == before


def test_write_core_helper(tmp_path):
    out = tmp_path / "core_out"
    res = write_telegram_evidence_contract(
        _evidence_pack(), str(out), contract_id="cr", created_at="t", source_evidence_pack="p.json"
    )
    assert res["ok"] is True
    assert Path(res["json_path"]).is_file()
    assert Path(res["md_path"]).is_file()
    assert res["contract"]["contract_id"] == "cr"


# ── 17. forbidden-token / import guards (source-only) ──────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "telegram_evidence_contract.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_telegram_evidence_contract.py"
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
            assert top != "core", f"AUTO.2a core must not import other core modules: {module!r}"
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
    # "apply_patch" (no paren) is allowed — it declares what is NOT done.
    for bad in ("generate_patch", "apply_patch(", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_network_or_chat_send_behaviour():
    # No network library, no webhook, no chat-app send behaviour. Bare "telegram"
    # is NOT forbidden (it is a required field/identifier); the *send / API* shapes
    # are.
    for bad in (
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "sendMessage",
        "send_message(",
        "bot_token",
        "bot token",
        "api.telegram.org",
        "telebot",
        "n8n",
        "github",
    ):
        assert bad not in _BOTH, f"Found network/chat-send token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "launch_worker", "worker_launch(", "spawn_worker", "run_worker("):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"


# ── constants exposure ─────────────────────────────────────────────────────────

def test_forbidden_actions_constant_matches_spec():
    for action in ("approve_merge", "push", "merge", "apply_patch", "run_worker", "launch_model", "rerun_automation"):
        assert action in FORBIDDEN_ACTIONS, action


def test_approval_options_constant_matches_spec():
    assert set(APPROVAL_OPTIONS) == {"review", "defer", "reject", "request_more_validation"}
