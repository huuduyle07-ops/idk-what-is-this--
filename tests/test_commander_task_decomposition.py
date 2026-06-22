"""Tests for CMD.2 - Task Decomposition Preview (report-only)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.commander_run_contract import build_commander_run_contract
from core.commander_task_decomposition import (
    FORBIDDEN_NEXT_STEPS,
    GUARDRAIL_FALSE_FLAGS,
    REPORT_KIND,
    build_task_decomposition_preview,
    render_task_decomposition_markdown,
    write_task_decomposition_preview,
)
import scripts.create_commander_task_decomposition as script


def _cmd1_contract(**over) -> dict:
    data = {
        "task": "Implement CMD.2 Task Decomposition Preview",
        "repo_path": ".",
        "estimated_files_touched": 5,
        "estimated_lines_changed": 130,
        "requires_validation": True,
        "requires_benchmark": True,
        "requires_patch": True,
        "contract_id": "cmd1",
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    data.update(over)
    return build_commander_run_contract(**data)


def _write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _preview(**over) -> dict:
    data = {
        "task": "Implement CMD.2 Task Decomposition Preview",
        "repo_path": ".",
        "preview_id": "preview",
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    data.update(over)
    return build_task_decomposition_preview(**data)


def test_task_only_input_produces_preview():
    preview = _preview()
    assert preview["report_kind"] == REPORT_KIND == "commander_task_decomposition_preview"
    assert preview["task"] == "Implement CMD.2 Task Decomposition Preview"
    assert preview["source_mode"] == "task_only"
    assert preview["phase_plan_preview"]
    assert preview["blockers"] == []


def test_contract_input_produces_preview_from_cmd1_fields():
    contract = _cmd1_contract()
    preview = _preview(task="", source_contract=contract, source_contract_path="contract.json")
    assert preview["task"] == contract["task"]
    assert preview["source_mode"] == "commander_run"
    assert preview["source_risk_level"] == contract["risk_level"]
    assert preview["source_complexity_level"] == contract["complexity_level"]
    assert preview["source_complexity_score"] == contract["complexity_score"]
    assert preview["stop_conditions"] == contract["stop_conditions"]
    assert "human_approval" in preview["human_checkpoint_preview"]["required_gates"]


def test_contract_fields_take_priority_when_both_contract_and_task_are_provided():
    contract = _cmd1_contract(task="Contract task wins")
    preview = _preview(task="Extra task text", source_contract=contract)
    assert preview["task"] == "Contract task wins"
    assert preview["decomposition_summary"]["extra_task_note"] == "Extra task text"
    assert any("contract fields took priority" in warning for warning in preview["warnings"])


def test_missing_contract_produces_blocker(tmp_path):
    result = script.run_create_commander_task_decomposition(
        repo_path=".",
        contract=str(tmp_path / "missing.json"),
        preview_id="missing",
        created_at="t",
        output_root=str(tmp_path / "out"),
    )
    assert result["ok"] is True
    assert result["preview"]["blockers"]
    assert any("could not read contract" in blocker.lower() for blocker in result["preview"]["blockers"])


def test_malformed_contract_produces_blocker(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ nope", encoding="utf-8")
    result = script.run_create_commander_task_decomposition(
        repo_path=".",
        contract=str(bad),
        preview_id="bad",
        created_at="t",
        output_root=str(tmp_path / "out"),
    )
    assert result["preview"]["blockers"]
    assert any("could not read contract" in blocker.lower() for blocker in result["preview"]["blockers"])


def test_phase_plan_is_deterministic():
    kwargs = {
        "task": "Implement a multi-phase roadmap-controlled Commander Mode preview",
        "repo_path": ".",
        "preview_id": "fixed",
        "created_at": "t",
        "source_contract": _cmd1_contract(),
    }
    a = build_task_decomposition_preview(**kwargs)
    b = build_task_decomposition_preview(**kwargs)
    assert json.dumps(a["phase_plan_preview"], sort_keys=True) == json.dumps(b["phase_plan_preview"], sort_keys=True)


def test_max_phases_limit_works():
    preview = _preview(source_contract=_cmd1_contract(), max_phases=3)
    assert [phase["phase_id"] for phase in preview["phase_plan_preview"]] == [
        "scope_review",
        "design_contract",
        "implementation_plan",
    ]


def test_evidence_plan_is_present():
    preview = _preview(source_contract=_cmd1_contract(changed_files=["core/x.py", "tests/test_x.py"]))
    evidence = preview["evidence_plan_preview"]
    assert "changed_files" in evidence
    assert "generated_artifacts" in evidence
    assert "guardrail_confirmation" in evidence


def test_validation_plan_lists_commands_as_text_only():
    plan = _preview(source_contract=_cmd1_contract())["validation_plan_preview"]
    assert plan["text_only"] is True
    assert plan["validation_run"] is False
    commands = " ".join(plan["commands"])
    assert "python -m pytest tests/test_commander_task_decomposition.py -q" in commands
    assert "python -m pytest -q" in commands


def test_benchmark_plan_lists_check_as_text_only():
    plan = _preview(source_contract=_cmd1_contract())["benchmark_plan_preview"]
    assert plan["text_only"] is True
    assert plan["benchmark_run_performed"] is False
    assert "python benchmarks/run_benchmarks.py --check" in plan["commands"]


def test_budget_plan_includes_stop_if_over_budget_rule():
    budget = _preview(source_contract=_cmd1_contract())["budget_plan_preview"]
    assert budget["estimated_files_touched"] == 5
    assert budget["estimated_lines_changed"] == 130
    assert "stop" in budget["stop_if_over_budget_rule"].lower()


def test_rollback_plan_is_conservative():
    rollback = _preview()["rollback_plan_preview"]
    joined = " ".join(rollback["steps"]).lower()
    assert "git diff review" in joined
    assert "commit isolation" in joined
    assert "revert commit" in joined
    assert rollback["auto_rollback_allowed"] is False


def test_human_checkpoints_are_present():
    checkpoint = _preview(source_contract=_cmd1_contract())["human_checkpoint_preview"]
    joined = " ".join(checkpoint["checkpoints"]).lower()
    assert "approve scope" in joined
    assert "inspect evidence" in joined
    assert "approve commit" in joined
    assert "future escalation" in joined


def test_allowed_next_steps_are_conservative():
    assert _preview()["allowed_next_steps"] == [
        "review_decomposition_preview",
        "edit_phase_plan",
        "create_report_only_implementation_prompt",
        "ask_human_for_scope_approval",
        "create_next_cmd_contract",
    ]


def test_forbidden_next_steps_include_execution_worker_patch_model_network_merge():
    forbidden = _preview()["forbidden_next_steps"]
    assert set(forbidden) == set(FORBIDDEN_NEXT_STEPS)
    for step in (
        "execute_decomposition",
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
    md = render_task_decomposition_markdown(_preview(source_contract=_cmd1_contract()))
    assert "# Task Decomposition Preview" in md
    low = md.lower()
    for section in (
        "## summary",
        "## source contract",
        "## phase plan preview",
        "## evidence plan preview",
        "## validation plan preview",
        "## benchmark plan preview",
        "## budget plan preview",
        "## rollback plan preview",
        "## human checkpoints",
        "## allowed next steps",
        "## forbidden next steps",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section
    for boundary in (
        "cmd.2 does not execute the decomposition.",
        "cmd.2 does not run agents.",
        "cmd.2 does not call models.",
        "cmd.2 does not apply patches.",
        "cmd.2 does not run validation.",
        "cmd.2 does not run benchmarks.",
        "cmd.2 does not contact network services.",
        "cmd.2 does not launch workers.",
        "cmd.2 does not push, merge, or open prs.",
        "cmd.2 is a report-only decomposition preview.",
    ):
        assert boundary in low


def test_cli_writes_json_and_markdown(tmp_path):
    contract_path = _write_json(tmp_path / "contract.json", _cmd1_contract())
    result = script.run_create_commander_task_decomposition(
        repo_path=".",
        contract=str(contract_path),
        output_root=str(tmp_path / "out"),
        preview_id="preview-1",
        created_at="2026-06-22T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "preview-1.json"
    assert Path(result["md_path"]).name == "preview-1.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["preview_id"] == "preview-1"
    assert data["source_contract_path"] == str(contract_path)


def test_cli_json_prints_summary_json(tmp_path, capsys):
    code = script.main(
        [
            "--repo-path",
            ".",
            "--task",
            "Implement CMD.2 Task Decomposition Preview",
            "--output-root",
            str(tmp_path),
            "--preview-id",
            "json-preview",
            "--created-at",
            "t",
            "--json",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["preview_id"] == "json-preview"
    assert printed["phase_count"] == 5
    assert printed["json_path"].endswith("json-preview.json")


def test_guardrails_are_all_false():
    guardrails = _preview()["guardrails"]
    assert set(guardrails) == set(GUARDRAIL_FALSE_FLAGS)
    for key in GUARDRAIL_FALSE_FLAGS:
        assert guardrails[key] is False, key


def test_write_core_helper(tmp_path):
    result = write_task_decomposition_preview(
        output_root=tmp_path,
        task="Implement CMD.2",
        repo_path=".",
        preview_id="core",
        created_at="t",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


_CORE = Path(__file__).parent.parent / "core" / "commander_task_decomposition.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_commander_task_decomposition.py"


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
