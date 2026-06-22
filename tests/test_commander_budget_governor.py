"""Tests for CMD.3 - Budget Governor Preview (report-only)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.commander_run_contract import build_commander_run_contract
from core.commander_task_decomposition import build_task_decomposition_preview
from core.commander_budget_governor import (
    FORBIDDEN_NEXT_STEPS,
    GUARDRAIL_FALSE_FLAGS,
    REPORT_KIND,
    build_budget_governor_preview,
    render_budget_governor_markdown,
    write_budget_governor_preview,
)
import scripts.create_commander_budget_governor as script


def _cmd1_contract(**over) -> dict:
    data = {
        "task": "Implement CMD.3 Budget Governor Preview",
        "repo_path": ".",
        "changed_files": ["core/commander_budget_governor.py", "tests/test_commander_budget_governor.py"],
        "estimated_files_touched": 4,
        "estimated_lines_changed": 120,
        "requires_validation": True,
        "requires_benchmark": True,
        "requires_patch": True,
        "time_budget_minutes": 45,
        "contract_id": "cmd1",
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    data.update(over)
    return build_commander_run_contract(**data)


def _decomposition(**over) -> dict:
    data = {
        "task": "",
        "repo_path": ".",
        "source_contract": _cmd1_contract(),
        "source_contract_path": "contract.json",
        "preview_id": "decomposition",
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    data.update(over)
    return build_task_decomposition_preview(**data)


def _budget(**over) -> dict:
    data = {
        "task": "Implement CMD.3 Budget Governor Preview",
        "repo_path": ".",
        "preview_id": "budget-preview",
        "created_at": "2026-06-22T00:00:00+00:00",
        "max_files": 5,
        "max_lines": 150,
        "max_minutes": 60,
    }
    data.update(over)
    return build_budget_governor_preview(**data)


def _write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_task_only_input_creates_budget_preview():
    preview = _budget()
    assert preview["report_kind"] == REPORT_KIND == "commander_budget_governor_preview"
    assert preview["task"] == "Implement CMD.3 Budget Governor Preview"
    assert preview["source_contract_path"] == ""
    assert preview["source_decomposition_path"] == ""
    assert preview["budget_status"] == "insufficient_information"
    assert preview["blockers"] == []


def test_contract_input_imports_estimated_scope_and_gates():
    contract = _cmd1_contract(estimated_files_touched=3, estimated_lines_changed=90, time_budget_minutes=30)
    preview = _budget(task="", source_contract=contract, source_contract_path="contract.json")
    assert preview["task"] == contract["task"]
    assert preview["estimated_scope"]["estimated_files_touched"] == 3
    assert preview["estimated_scope"]["estimated_lines_changed"] == 90
    assert preview["estimated_scope"]["estimated_minutes"] == 30
    assert "validation_required" in preview["source_summary"]["required_gates"]
    assert "benchmark_check_required" in preview["source_summary"]["required_gates"]


def test_decomposition_input_imports_phase_count_and_evidence_plan():
    decomposition = _decomposition()
    preview = _budget(task="", source_decomposition=decomposition, source_decomposition_path="decomp.json")
    assert preview["task"] == decomposition["task"]
    assert preview["estimated_scope"]["phase_count"] == 5
    assert preview["estimated_scope"]["evidence_artifact_count"] == 2
    assert preview["source_summary"]["decomposition_source"] == "decomp.json"


def test_contract_and_decomposition_merge_deterministically():
    contract = _cmd1_contract(task="Contract task wins", estimated_files_touched=4, estimated_lines_changed=110)
    decomposition = _decomposition(source_contract=_cmd1_contract(task="Decomposition task loses", estimated_files_touched=2))
    kwargs = {
        "task": "Extra task text",
        "repo_path": ".",
        "source_contract": contract,
        "source_contract_path": "contract.json",
        "source_decomposition": decomposition,
        "source_decomposition_path": "decomp.json",
        "preview_id": "fixed",
        "created_at": "t",
        "max_files": 5,
        "max_lines": 150,
        "max_minutes": 60,
    }
    a = build_budget_governor_preview(**kwargs)
    b = build_budget_governor_preview(**kwargs)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["task"] == "Contract task wins"
    assert a["source_summary"]["source_count"] == 2
    assert a["estimated_scope"]["estimated_files_touched"] == 4


def test_missing_sources_produce_blockers(tmp_path):
    result = script.run_create_commander_budget_governor(
        repo_path=".",
        contract=str(tmp_path / "missing-contract.json"),
        decomposition=str(tmp_path / "missing-decomposition.json"),
        output_root=str(tmp_path / "out"),
        preview_id="missing",
        created_at="t",
    )
    blockers = result["preview"]["blockers"]
    assert blockers
    assert any("could not read contract" in blocker.lower() for blocker in blockers)
    assert any("could not read decomposition" in blocker.lower() for blocker in blockers)


def test_within_budget_classification():
    preview = _budget(source_contract=_cmd1_contract(estimated_files_touched=2, estimated_lines_changed=60, time_budget_minutes=20))
    assert preview["budget_status"] == "within_budget"
    assert preview["budget_summary"]["limit_classification"] == "within_budget"
    assert preview["budget_summary"]["human_reapproval_required"] is False


def test_near_limit_classification():
    preview = _budget(source_contract=_cmd1_contract(estimated_files_touched=4, estimated_lines_changed=120, time_budget_minutes=48))
    assert preview["budget_status"] == "near_limit"
    assert preview["budget_summary"]["limit_classification"] == "near_limit"
    assert preview["budget_summary"]["human_reapproval_required"] is False


def test_over_budget_classification_requires_reapproval():
    preview = _budget(source_contract=_cmd1_contract(estimated_files_touched=6, estimated_lines_changed=151, time_budget_minutes=61))
    assert preview["budget_status"] == "needs_human_reapproval"
    assert preview["budget_summary"]["limit_classification"] == "over_budget"
    assert preview["budget_summary"]["human_reapproval_required"] is True


def test_insufficient_information_classification():
    preview = _budget(source_contract=_cmd1_contract(changed_files=[], estimated_files_touched=0, estimated_lines_changed=0, time_budget_minutes=None))
    assert preview["budget_status"] == "insufficient_information"
    assert preview["budget_summary"]["limit_classification"] == "insufficient_information"
    assert any("missing scope" in warning.lower() for warning in preview["warnings"])


def test_human_reapproval_checkpoint_is_added_when_over_limit():
    checkpoints = _budget(source_contract=_cmd1_contract(estimated_files_touched=9))["human_approval_checkpoints"]
    ids = {checkpoint["checkpoint_id"] for checkpoint in checkpoints}
    assert "human_reapprove_budget" in ids
    assert all(checkpoint["required"] is True for checkpoint in checkpoints)


def test_escalation_rules_are_conservative():
    preview = _budget(source_contract=_cmd1_contract())
    triggers = {rule["trigger"] for rule in preview["escalation_rules"]}
    assert "estimated_files_touched_exceeds_max_files" in triggers
    assert "estimated_lines_changed_exceeds_max_lines" in triggers
    assert "estimated_minutes_exceeds_max_minutes" in triggers
    assert "remote_action_requested" in triggers
    assert "model_authority_requested" in triggers
    assert "network_service_requested" in triggers
    assert "push_merge_or_pr_requested" in triggers
    assert all(rule["action"] in {"stop_and_request_human_reapproval", "stop_and_escalate"} for rule in preview["escalation_rules"])


def test_stop_conditions_include_budget_and_gate_failures():
    joined = " ".join(_budget()["stop_conditions"]).lower()
    for phrase in (
        "estimated files exceed",
        "estimated lines exceed",
        "estimated minutes exceed",
        "forbidden files",
        "validation fails",
        "benchmark check fails",
        "remote action",
        "human approval is missing",
    ):
        assert phrase in joined


def test_allowed_next_steps_are_conservative():
    assert _budget()["allowed_next_steps"] == [
        "review_budget_governor_preview",
        "edit_budget_limits",
        "ask_human_for_budget_approval",
        "create_stop_condition_report",
        "create_next_cmd_contract",
    ]


def test_forbidden_next_steps_include_execution_worker_patch_model_network_merge():
    forbidden = _budget()["forbidden_next_steps"]
    assert set(forbidden) == set(FORBIDDEN_NEXT_STEPS)
    for step in (
        "execute_plan",
        "launch_worker",
        "apply_patch",
        "run_validation",
        "run_benchmark",
        "call_model",
        "contact_remote_service",
        "push_or_merge",
        "open_pr",
        "auto_approve",
    ):
        assert step in forbidden


def test_markdown_contains_required_sections_and_boundaries():
    md = render_budget_governor_markdown(_budget(source_contract=_cmd1_contract(), source_decomposition=_decomposition()))
    assert "# Budget Governor Preview" in md
    low = md.lower()
    for section in (
        "## summary",
        "## sources",
        "## estimated scope",
        "## budget limits",
        "## budget status",
        "## escalation rules",
        "## stop conditions",
        "## human approval checkpoints",
        "## allowed next steps",
        "## forbidden next steps",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section
    for boundary in (
        "cmd.3 does not execute tasks.",
        "cmd.3 does not run agents.",
        "cmd.3 does not call models.",
        "cmd.3 does not apply patches.",
        "cmd.3 does not run validation.",
        "cmd.3 does not run benchmarks.",
        "cmd.3 does not contact network services.",
        "cmd.3 does not launch workers.",
        "cmd.3 does not push, merge, or open prs.",
        "cmd.3 is a report-only budget governor preview.",
    ):
        assert boundary in low


def test_cli_writes_json_and_markdown(tmp_path):
    decomposition_path = _write_json(tmp_path / "decomp.json", _decomposition())
    result = script.run_create_commander_budget_governor(
        repo_path=".",
        decomposition=str(decomposition_path),
        output_root=str(tmp_path / "out"),
        preview_id="budget-1",
        created_at="2026-06-22T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "budget-1.json"
    assert Path(result["md_path"]).name == "budget-1.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["preview_id"] == "budget-1"
    assert data["source_decomposition_path"] == str(decomposition_path)


def test_cli_json_prints_summary_json(tmp_path, capsys):
    code = script.main(
        [
            "--repo-path",
            ".",
            "--task",
            "Implement CMD.3 Budget Governor Preview",
            "--output-root",
            str(tmp_path),
            "--preview-id",
            "json-budget",
            "--created-at",
            "t",
            "--json",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["preview_id"] == "json-budget"
    assert printed["budget_status"] == "insufficient_information"
    assert printed["json_path"].endswith("json-budget.json")


def test_guardrails_are_all_false():
    guardrails = _budget()["guardrails"]
    assert set(guardrails) == set(GUARDRAIL_FALSE_FLAGS)
    for key in GUARDRAIL_FALSE_FLAGS:
        assert guardrails[key] is False, key


def test_write_core_helper(tmp_path):
    result = write_budget_governor_preview(
        output_root=tmp_path,
        task="Implement CMD.3",
        repo_path=".",
        preview_id="core",
        created_at="t",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


_CORE = Path(__file__).parent.parent / "core" / "commander_budget_governor.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_commander_budget_governor.py"


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
