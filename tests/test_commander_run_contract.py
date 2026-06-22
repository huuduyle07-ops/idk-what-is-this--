"""Tests for CMD.1 - Commander Run Contract (report-only).

CMD.1 classifies a user task into planning modes and previews gates, stop
conditions, evidence, budget, validation, and rollback plans. It never executes
Commander Mode, launches agents, calls models, applies patches, runs validation
or benchmarks, contacts network services, writes to a database, or pushes/merges.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.commander_run_contract import (
    FORBIDDEN_NEXT_STEPS,
    GUARDRAIL_FALSE_FLAGS,
    REPORT_KIND,
    build_commander_run_contract,
    render_commander_run_contract_markdown,
    write_commander_run_contract,
)
import scripts.create_commander_run_contract as script


def _contract(task="Fix a typo in README", **over) -> dict:
    data = {
        "task": task,
        "repo_path": ".",
        "contract_id": "cmd",
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    data.update(over)
    return build_commander_run_contract(**data)


def test_small_low_risk_task_recommends_instant_run():
    contract = _contract(
        "Fix a typo in README",
        changed_files=["README.md"],
        estimated_files_touched=1,
        estimated_lines_changed=2,
    )
    assert contract["recommended_mode"] == "instant_run"
    assert contract["risk_level"] == "low"
    assert contract["complexity_level"] == "low"
    assert contract["report_kind"] == REPORT_KIND == "commander_run_contract"


def test_multi_file_large_task_recommends_commander_run():
    contract = _contract(
        "Implement a multi-phase report builder with docs and tests",
        estimated_files_touched=5,
        estimated_lines_changed=120,
        requires_validation=True,
        requires_benchmark=True,
        requires_patch=True,
    )
    assert contract["recommended_mode"] == "commander_run"
    assert contract["complexity_score"] >= 7
    assert "validation_required" in contract["required_gates"]
    assert "benchmark_check_required" in contract["required_gates"]
    assert "rollback_plan_required" in contract["required_gates"]


def test_roadmap_or_architecture_task_recommends_commander_run():
    contract = _contract("Update roadmap architecture for model authority and lessons")
    assert contract["recommended_mode"] == "commander_run"
    assert contract["signals"]["architecture_signal"]["value"] > 0


def test_remote_action_task_requires_remote_contract_required():
    contract = _contract("Prepare a remote workflow handoff", requires_remote_action=True)
    assert contract["recommended_mode"] == "commander_run"
    assert "remote_contract_required" in contract["required_gates"]
    assert any("remote" in warning.lower() for warning in contract["warnings"])


def test_model_authority_task_blocks_model_authority():
    contract = _contract("Increase model authority for routing decisions", requires_model_calls=True)
    assert contract["recommended_mode"] == "commander_run"
    assert "model_authority_blocked" in contract["required_gates"]
    assert any("model authority" in blocker.lower() for blocker in contract["blockers"])


def test_vague_task_recommends_needs_clarification():
    contract = _contract("Make it better", repo_path="")
    assert contract["recommended_mode"] == "needs_clarification"
    assert contract["blockers"]
    assert contract["signals"]["ambiguity_signal"]["value"] > 0


def test_forbidden_auto_merge_task_recommends_reject_or_defer():
    contract = _contract("Auto-merge this change into main without review")
    assert contract["recommended_mode"] == "reject_or_defer"
    assert any("auto-merge" in blocker.lower() for blocker in contract["blockers"])


def test_forbidden_file_or_secret_task_recommends_reject_or_defer():
    for task in ("Read .env and extract the API key", "Modify .git/config for the run"):
        contract = _contract(task)
        assert contract["recommended_mode"] == "reject_or_defer"
        assert contract["risk_level"] == "blocked"
        assert contract["blockers"], task


def test_complexity_score_is_deterministic():
    kwargs = {
        "task": "Implement a multi-phase roadmap-controlled Commander Mode preview for large tasks",
        "repo_path": ".",
        "estimated_files_touched": 5,
        "estimated_lines_changed": 120,
        "requires_validation": True,
        "requires_benchmark": True,
        "contract_id": "fixed",
        "created_at": "t",
    }
    a = build_commander_run_contract(**kwargs)
    b = build_commander_run_contract(**kwargs)
    assert a["complexity_score"] == b["complexity_score"]
    assert json.dumps(a["signals"], sort_keys=True) == json.dumps(b["signals"], sort_keys=True)


def test_required_gates_are_deterministic():
    a = _contract(
        "Prepare remote model authority architecture",
        requires_remote_action=True,
        requires_model_calls=True,
        requires_validation=True,
        time_budget_minutes=30,
    )
    b = _contract(
        "Prepare remote model authority architecture",
        requires_remote_action=True,
        requires_model_calls=True,
        requires_validation=True,
        time_budget_minutes=30,
    )
    assert a["required_gates"] == b["required_gates"]
    assert a["required_gates"] == sorted(a["required_gates"])


def test_stop_conditions_include_human_approval_and_scope_expansion():
    contract = _contract("Implement a large task", estimated_files_touched=3, estimated_lines_changed=70)
    joined = " ".join(contract["stop_conditions"]).lower()
    assert "human approval" in joined
    assert "scope expands" in joined


def test_commander_preview_is_present_but_marked_non_executing():
    preview = _contract("Implement a multi-phase roadmap task")["commander_preview"]
    assert preview["non_executing"] is True
    for key in (
        "phase_plan_preview",
        "evidence_plan_preview",
        "validation_plan_preview",
        "budget_plan_preview",
        "rollback_plan_preview",
        "human_checkpoint_preview",
    ):
        assert key in preview
        assert preview[key]


def test_allowed_next_steps_are_conservative():
    allowed = _contract()["allowed_next_steps"]
    assert allowed == [
        "review_contract",
        "edit_task_scope",
        "create_followup_design_phase",
        "create_report_only_plan",
        "ask_human_for_approval",
    ]
    assert not any("execute" in step or "merge" in step or "patch" == step for step in allowed)


def test_forbidden_next_steps_include_execution_worker_patch_model_network_merge():
    forbidden = _contract()["forbidden_next_steps"]
    assert set(forbidden) == set(FORBIDDEN_NEXT_STEPS)
    for step in (
        "execute_commander_plan",
        "launch_worker",
        "apply_patch",
        "run_benchmark",
        "run_validation",
        "call_model",
        "contact_remote_service",
        "push_or_merge",
        "open_pr",
        "auto_approve",
    ):
        assert step in forbidden


def test_markdown_contains_required_sections_and_boundaries():
    md = render_commander_run_contract_markdown(_contract("Implement a large roadmap task"))
    assert "# Commander Run Contract" in md
    low = md.lower()
    for section in (
        "## summary",
        "## recommended mode",
        "## complexity signals",
        "## required gates",
        "## stop conditions",
        "## commander preview",
        "## allowed next steps",
        "## forbidden next steps",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section
    for boundary in (
        "cmd.1 does not execute commander mode.",
        "cmd.1 does not run agents.",
        "cmd.1 does not call models.",
        "cmd.1 does not apply patches.",
        "cmd.1 does not run validation.",
        "cmd.1 does not run benchmarks.",
        "cmd.1 does not contact network services.",
        "cmd.1 does not launch workers.",
        "cmd.1 does not push, merge, or open prs.",
        "cmd.1 is a report-only planning contract.",
    ):
        assert boundary in low


def test_cli_writes_json_and_markdown(tmp_path):
    result = script.run_create_commander_run_contract(
        repo_path=".",
        task="Implement a large roadmap task",
        output_root=str(tmp_path),
        contract_id="contract-1",
        created_at="2026-06-22T00:00:00+00:00",
        estimated_files_touched=4,
        estimated_lines_changed=80,
        requires_validation=True,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "contract-1.json"
    assert Path(result["md_path"]).name == "contract-1.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["contract_id"] == "contract-1"
    assert data["recommended_mode"] == "commander_run"


def test_cli_json_flag_prints_summary_json(tmp_path, capsys):
    code = script.main(
        [
            "--repo-path",
            ".",
            "--task",
            "Fix typo",
            "--output-root",
            str(tmp_path),
            "--contract-id",
            "json-contract",
            "--created-at",
            "t",
            "--json",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["contract_id"] == "json-contract"
    assert printed["recommended_mode"] == "instant_run"
    assert printed["json_path"].endswith("json-contract.json")
    assert printed["md_path"].endswith("json-contract.md")


def test_guardrails_are_all_false():
    guardrails = _contract()["guardrails"]
    assert set(guardrails) == set(GUARDRAIL_FALSE_FLAGS)
    for key in GUARDRAIL_FALSE_FLAGS:
        assert guardrails[key] is False, key


def test_write_core_helper(tmp_path):
    result = write_commander_run_contract(
        output_root=tmp_path,
        task="Fix typo",
        repo_path=".",
        contract_id="core",
        created_at="t",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


_CORE = Path(__file__).parent.parent / "core" / "commander_run_contract.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_commander_run_contract.py"


def test_source_contains_no_forbidden_behavior():
    both = _CORE.read_text(encoding="utf-8") + "\n" + _SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "subprocess",
        "Popen",
        "os.system",
        "check_output",
        "check_call",
        "requests.",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "openai",
        "anthropic",
        "litellm",
        "ollama",
        "generativeai",
        "run_safe_validation",
        "validation_execution",
        "run_benchmarks(",
        "generate_patch(",
        "apply_patch(",
        "patch_apply(",
        "launch_worker(",
        "worker_launch(",
        "spawn_worker",
        "sqlite3",
        "psycopg",
        "sqlalchemy",
        "pymongo",
        "git push",
        "gh pr",
        "auto_merge(",
        "perform_merge",
    )
    for bad in forbidden:
        assert bad not in both, f"Found forbidden behavior token {bad!r}"


def test_core_imports_are_stdlib_only():
    allowed_top = {"__future__", "json", "pathlib", "typing"}
    tree = ast.parse(_CORE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top in allowed_top, node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, alias.name
