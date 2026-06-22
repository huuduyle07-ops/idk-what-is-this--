"""Tests for CMD.4 - Commander Readiness / Stop Condition Report."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.commander_run_contract import build_commander_run_contract
from core.commander_task_decomposition import build_task_decomposition_preview
from core.commander_budget_governor import build_budget_governor_preview
from core.commander_readiness_report import (
    FORBIDDEN_NEXT_STEPS,
    GUARDRAIL_FALSE_FLAGS,
    REPORT_KIND,
    build_commander_readiness_report,
    render_commander_readiness_markdown,
    write_commander_readiness_report,
)
import scripts.create_commander_readiness_report as script


def _cmd1_contract(**over) -> dict:
    data = {
        "task": "Implement CMD.4 Commander Readiness Report",
        "repo_path": ".",
        "changed_files": ["core/commander_readiness_report.py", "tests/test_commander_readiness_report.py"],
        "estimated_files_touched": 3,
        "estimated_lines_changed": 90,
        "requires_validation": True,
        "requires_benchmark": True,
        "requires_patch": True,
        "time_budget_minutes": 30,
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
        "task": "",
        "repo_path": ".",
        "source_contract": _cmd1_contract(),
        "source_contract_path": "contract.json",
        "source_decomposition": _decomposition(),
        "source_decomposition_path": "decomp.json",
        "max_files": 5,
        "max_lines": 150,
        "max_minutes": 60,
        "preview_id": "budget",
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    data.update(over)
    return build_budget_governor_preview(**data)


def _report(**over) -> dict:
    data = {
        "repo_path": ".",
        "report_id": "readiness",
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    data.update(over)
    return build_commander_readiness_report(**data)


def _write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_no_sources_produces_insufficient_evidence():
    report = _report()
    assert report["report_kind"] == REPORT_KIND == "commander_readiness_report"
    assert report["readiness_status"] == "insufficient_evidence"
    assert "No CMD.1, CMD.2, or CMD.3 source artifacts were supplied." in report["readiness_reason"]
    assert report["source_summary"]["source_count"] == 0


def test_malformed_contract_produces_blocker(tmp_path):
    bad = tmp_path / "bad-contract.json"
    bad.write_text("{ nope", encoding="utf-8")
    result = script.run_create_commander_readiness_report(
        repo_path=".",
        contract=str(bad),
        output_root=str(tmp_path / "out"),
        report_id="bad-contract",
        created_at="t",
    )
    assert result["report"]["readiness_status"] == "blocked"
    assert any("could not read contract" in blocker.lower() for blocker in result["report"]["blockers"])


def test_malformed_decomposition_produces_blocker(tmp_path):
    bad = tmp_path / "bad-decomposition.json"
    bad.write_text("{ nope", encoding="utf-8")
    result = script.run_create_commander_readiness_report(
        repo_path=".",
        decomposition=str(bad),
        output_root=str(tmp_path / "out"),
        report_id="bad-decomp",
        created_at="t",
    )
    assert result["report"]["readiness_status"] == "blocked"
    assert any("could not read decomposition" in blocker.lower() for blocker in result["report"]["blockers"])


def test_malformed_budget_produces_blocker(tmp_path):
    bad = tmp_path / "bad-budget.json"
    bad.write_text("{ nope", encoding="utf-8")
    result = script.run_create_commander_readiness_report(
        repo_path=".",
        budget=str(bad),
        output_root=str(tmp_path / "out"),
        report_id="bad-budget",
        created_at="t",
    )
    assert result["report"]["readiness_status"] == "blocked"
    assert any("could not read budget" in blocker.lower() for blocker in result["report"]["blockers"])


def test_complete_within_budget_sources_produce_ready_for_human_approval():
    contract = _cmd1_contract()
    decomposition = _decomposition(source_contract=contract)
    budget = _budget(source_contract=contract, source_decomposition=decomposition)
    report = _report(source_contract=contract, source_decomposition=decomposition, source_budget=budget)
    assert report["readiness_status"] == "ready_for_human_approval"
    assert "ready for human approval" in report["readiness_reason"].lower()
    assert report["gate_summary"]["all_required_gates_present"] is True


def test_budget_needs_human_reapproval_produces_needs_human_reapproval():
    contract = _cmd1_contract(estimated_files_touched=8, estimated_lines_changed=200, time_budget_minutes=90)
    decomposition = _decomposition(source_contract=contract)
    budget = _budget(source_contract=contract, source_decomposition=decomposition)
    report = _report(source_contract=contract, source_decomposition=decomposition, source_budget=budget)
    assert report["readiness_status"] == "needs_human_reapproval"
    assert report["budget_summary"]["human_reapproval_required"] is True
    assert "human_budget_reapproval" in report["required_before_implementation"]


def test_over_budget_produces_needs_human_reapproval():
    budget = _budget(source_contract=_cmd1_contract(estimated_files_touched=9))
    report = _report(source_contract=_cmd1_contract(), source_decomposition=_decomposition(), source_budget=budget)
    assert report["readiness_status"] == "needs_human_reapproval"
    assert report["budget_summary"]["limit_classification"] == "over_budget"


def test_missing_human_approval_gate_blocks_readiness():
    contract = _cmd1_contract()
    contract["required_gates"] = [gate for gate in contract["required_gates"] if gate != "human_approval"]
    decomposition = _decomposition(source_contract=contract)
    checkpoint = decomposition["human_checkpoint_preview"]
    checkpoint["required_gates"] = [gate for gate in checkpoint["required_gates"] if gate != "human_approval"]
    budget = _budget(source_contract=contract, source_decomposition=decomposition)
    budget["source_summary"]["required_gates"] = [gate for gate in budget["source_summary"]["required_gates"] if gate != "human_approval"]
    report = _report(source_contract=contract, source_decomposition=decomposition, source_budget=budget)
    assert report["readiness_status"] == "blocked"
    assert "human_approval" in report["gate_summary"]["missing_gates"]


def test_remote_model_merge_escalation_blocks_readiness():
    budget = _budget()
    budget["escalation_rules"].append(
        {"trigger": "remote_action_requested", "action": "stop_and_escalate", "severity": "hard_stop", "active": True}
    )
    report = _report(source_contract=_cmd1_contract(), source_decomposition=_decomposition(), source_budget=budget)
    assert report["readiness_status"] == "blocked"
    assert any("remote/model/merge" in blocker.lower() for blocker in report["blockers"])


def test_gate_summary_is_deterministic():
    contract = _cmd1_contract()
    decomposition = _decomposition(source_contract=contract)
    budget = _budget(source_contract=contract, source_decomposition=decomposition)
    a = _report(source_contract=contract, source_decomposition=decomposition, source_budget=budget)
    b = _report(source_contract=contract, source_decomposition=decomposition, source_budget=budget)
    assert json.dumps(a["gate_summary"], sort_keys=True) == json.dumps(b["gate_summary"], sort_keys=True)
    assert list(a["gate_summary"]["gates"].keys()) == [
        "human_approval",
        "scope_confirmed",
        "budget_confirmed",
        "evidence_required",
        "validation_required",
        "benchmark_check_required",
        "rollback_plan_required",
    ]


def test_stop_conditions_are_aggregated_deterministically():
    contract = _cmd1_contract()
    decomposition = _decomposition(source_contract=contract)
    budget = _budget(source_contract=contract, source_decomposition=decomposition)
    report = _report(source_contract=contract, source_decomposition=decomposition, source_budget=budget)
    conditions = report["stop_condition_summary"]["stop_conditions"]
    assert conditions == sorted(set(conditions))
    joined = " ".join(conditions).lower()
    assert "validation fails" in joined
    assert "benchmark check fails" in joined
    assert "human approval is missing" in joined


def test_required_before_implementation_list_is_conservative():
    required = _report(source_budget=_budget(source_contract=_cmd1_contract(estimated_files_touched=8)))["required_before_implementation"]
    assert required == [
        "human_scope_approval",
        "human_budget_reapproval",
        "review_decomposition_preview",
        "review_budget_preview",
        "confirm_validation_plan",
        "confirm_benchmark_plan",
        "confirm_rollback_plan",
        "confirm_no_remote_or_model_authority_change",
    ]


def test_allowed_next_steps_are_conservative():
    assert _report()["allowed_next_steps"] == [
        "review_readiness_report",
        "request_human_approval",
        "revise_scope",
        "revise_budget",
        "create_report_only_implementation_prompt",
        "create_next_cmd_contract",
    ]


def test_forbidden_next_steps_include_execution_worker_patch_model_network_merge():
    forbidden = _report()["forbidden_next_steps"]
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
    md = render_commander_readiness_markdown(
        _report(source_contract=_cmd1_contract(), source_decomposition=_decomposition(), source_budget=_budget())
    )
    assert "# Commander Readiness Report" in md
    low = md.lower()
    for section in (
        "## summary",
        "## readiness status",
        "## source coverage",
        "## gate summary",
        "## budget summary",
        "## stop conditions",
        "## human approval requirements",
        "## required before implementation",
        "## allowed next steps",
        "## forbidden next steps",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section
    for boundary in (
        "cmd.4 does not execute the commander plan.",
        "cmd.4 does not run agents.",
        "cmd.4 does not call models.",
        "cmd.4 does not apply patches.",
        "cmd.4 does not run validation.",
        "cmd.4 does not run benchmarks.",
        "cmd.4 does not contact network services.",
        "cmd.4 does not launch workers.",
        "cmd.4 does not push, merge, or open prs.",
        "cmd.4 is a report-only readiness check.",
    ):
        assert boundary in low


def test_cli_writes_json_and_markdown(tmp_path):
    contract_path = _write_json(tmp_path / "contract.json", _cmd1_contract())
    decomp_path = _write_json(tmp_path / "decomp.json", _decomposition())
    budget_path = _write_json(tmp_path / "budget.json", _budget())
    result = script.run_create_commander_readiness_report(
        repo_path=".",
        contract=str(contract_path),
        decomposition=str(decomp_path),
        budget=str(budget_path),
        output_root=str(tmp_path / "out"),
        report_id="readiness-1",
        created_at="2026-06-22T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "readiness-1.json"
    assert Path(result["md_path"]).name == "readiness-1.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_id"] == "readiness-1"
    assert data["source_contract_path"] == str(contract_path)
    assert data["source_decomposition_path"] == str(decomp_path)
    assert data["source_budget_path"] == str(budget_path)


def test_cli_json_prints_summary_json(tmp_path, capsys):
    code = script.main(
        [
            "--repo-path",
            ".",
            "--output-root",
            str(tmp_path),
            "--report-id",
            "json-readiness",
            "--created-at",
            "t",
            "--json",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "json-readiness"
    assert printed["readiness_status"] == "insufficient_evidence"
    assert printed["json_path"].endswith("json-readiness.json")


def test_guardrails_are_all_false():
    guardrails = _report()["guardrails"]
    assert set(guardrails) == set(GUARDRAIL_FALSE_FLAGS)
    for key in GUARDRAIL_FALSE_FLAGS:
        assert guardrails[key] is False, key


def test_write_core_helper(tmp_path):
    result = write_commander_readiness_report(
        output_root=tmp_path,
        repo_path=".",
        report_id="core",
        created_at="t",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


_CORE = Path(__file__).parent.parent / "core" / "commander_readiness_report.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_commander_readiness_report.py"


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
