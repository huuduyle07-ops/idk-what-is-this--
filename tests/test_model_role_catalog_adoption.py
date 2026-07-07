"""Tests for ADOPT.MODEL.1 - Human-Approved Model Role Catalog Adoption."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.model_role_coverage_report import build_model_role_coverage_report
from core.model_role_gap_plan import build_model_role_gap_plan
from core.model_role_registry import (
    build_model_role_registry,
    render_model_role_registry_markdown,
)
from core.model_role_catalog_update_proposal import build_model_role_catalog_update_proposal
from core.phase_picker import pick_phase_candidates
from core.model_role_catalog_adoption import (
    ADDED_ROLE_IDS,
    ADOPTION_STATUSES,
    REPORT_KIND,
    build_model_role_catalog_adoption,
    render_model_role_catalog_adoption_markdown,
    write_model_role_catalog_adoption,
)
import scripts.adopt_model_role_catalog as script


def _assignment() -> dict:
    return {
        "report_kind": "commander_manual_assignment_plan",
        "assignment_status": "assignment_ready",
        "assignments": [
            {
                "assignment_id": "sub-1-advisory-assignment",
                "sub_boss_id": "sub-1",
                "title": "Implement safe report",
                "risk_level": "low",
                "advisory_roles": ["planner", "implementer", "reviewer"],
                "role_binding": "advisory_labels_only",
                "executable_assignment": False,
                "model_id": "",
                "source_evidence_required": ["pytest evidence"],
                "warnings": [],
                "blocked_reasons": [],
            }
        ],
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {"model_call_performed": False, "worker_launch_performed": False},
    }


def _proposal_bundle() -> tuple[dict, dict]:
    active = build_model_role_registry()
    coverage = build_model_role_coverage_report(
        model_registry_path="model_role_registry.json",
        model_registry_data=active,
        assignment_path="assignment.json",
        assignment_data=_assignment(),
    )
    gap_plan = build_model_role_gap_plan(
        coverage_path="model_role_coverage_report.json",
        coverage_data=coverage,
        model_registry_path="model_role_registry.json",
        model_registry_data=active,
    )
    proposal = build_model_role_catalog_update_proposal(
        gap_plan_path="model_role_gap_plan.json",
        gap_plan_data=gap_plan,
        model_registry_path="model_role_registry.json",
        model_registry_data=active,
    )
    return active, copy.deepcopy(proposal["proposed_registry"])


def _write_catalogs(tmp_path: Path) -> tuple[Path, Path, Path, dict, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    active, proposed = _proposal_bundle()
    active_path = tmp_path / "model_role_registry.json"
    active_md_path = tmp_path / "model_role_registry.md"
    proposed_path = tmp_path / "proposed_model_role_registry.json"
    active_path.write_text(json.dumps(active, indent=2, sort_keys=True), encoding="utf-8")
    active_md_path.write_text(render_model_role_registry_markdown(active), encoding="utf-8")
    proposed_path.write_text(json.dumps(proposed, indent=2, sort_keys=True), encoding="utf-8")
    return active_path, active_md_path, proposed_path, active, proposed


def _role_ids(data: dict) -> list[str]:
    return [role["role_id"] for role in data["roles"]]


def test_adoption_backs_up_active_catalog_writes_receipt_and_adopts_ten_roles(tmp_path):
    active_path, active_md_path, proposed_path, active, _proposed = _write_catalogs(tmp_path)
    result = write_model_role_catalog_adoption(
        active_catalog_path=active_path,
        active_catalog_md_path=active_md_path,
        proposed_catalog_path=proposed_path,
        output_dir=tmp_path / "adoption",
    )

    assert result["ok"] is True
    receipt = result["receipt"]
    assert receipt["report_kind"] == REPORT_KIND == "model_role_catalog_adoption_receipt"
    assert receipt["adopted_phase_id"] == "ADOPT.MODEL.1"
    assert receipt["source_proposal_phase_id"] == "MODEL.N4"
    assert receipt["adoption_status"] == "model_role_catalog_adoption_complete_with_warnings"
    assert receipt["previous_role_count"] == 7
    assert receipt["adopted_role_count"] == 10
    assert receipt["added_roles"] == list(ADDED_ROLE_IDS)
    assert set(receipt["preserved_roles"]) == set(_role_ids(active))
    assert receipt["advisory_only_confirmed"] is True
    assert receipt["executable_binding_allowed_confirmed_false"] is True
    assert receipt["model_routing_enabled_confirmed_false"] is True
    assert receipt["model_calls_allowed_confirmed_false"] is True
    assert receipt["worker_launch_allowed_confirmed_false"] is True
    assert receipt["model_ids_metadata_only_confirmed"] is True
    assert receipt["blocked_reasons"] == []
    assert receipt["recommended_next_phase"]["phase_id"] == "ADOPT.MODEL.2"

    backup_json = Path(receipt["backup_paths"]["json"])
    backup_md = Path(receipt["backup_paths"]["markdown"])
    assert backup_json.is_file()
    assert backup_md.is_file()
    assert json.loads(backup_json.read_text(encoding="utf-8"))["role_count"] == 7
    assert backup_md.read_text(encoding="utf-8") == render_model_role_registry_markdown(active)

    adopted = json.loads(active_path.read_text(encoding="utf-8"))
    assert adopted["report_kind"] == "model_role_registry"
    assert adopted["role_count"] == 10
    assert set(ADDED_ROLE_IDS) <= set(_role_ids(adopted))
    assert all(role["advisory_only"] is True for role in adopted["roles"])
    assert all(role["executable_binding_allowed"] is False for role in adopted["roles"])
    assert all(role["model_id_policy"] == "descriptive_metadata_only" for role in adopted["roles"])

    assert Path(result["json_path"]).name == "model_role_catalog_adoption_receipt.json"
    assert Path(result["md_path"]).name == "model_role_catalog_adoption_receipt.md"
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "ui_reviewer" in md
    assert "ADOPT.MODEL.2" in md
    assert "no model routing" in md.lower()


def test_build_receipt_confirms_added_roles_and_preserves_existing_roles():
    active, proposed = _proposal_bundle()
    receipt = build_model_role_catalog_adoption(
        active_catalog_path="model_role_registry.json",
        active_catalog_data=active,
        proposed_catalog_path="proposed_model_role_registry.json",
        proposed_catalog_data=proposed,
        backup_paths={
            "json": "backups/model_role_registry_before_adoption.json",
            "markdown": "backups/model_role_registry_before_adoption.md",
        },
        receipt_paths={
            "json": "model_role_catalog_adoption_receipt.json",
            "markdown": "model_role_catalog_adoption_receipt.md",
        },
    )

    assert receipt["previous_role_count"] == 7
    assert receipt["adopted_role_count"] == 10
    assert receipt["added_roles"] == ["ui_reviewer", "test_designer", "documentation_reviewer"]
    assert set(receipt["preserved_roles"]) == set(_role_ids(active))
    assert receipt["adoption_status"] == "model_role_catalog_adoption_complete_with_warnings"


def test_missing_or_malformed_proposed_catalog_blocks_adoption():
    active, _proposed = _proposal_bundle()
    receipt = build_model_role_catalog_adoption(
        active_catalog_path="model_role_registry.json",
        active_catalog_data=active,
        proposed_catalog_path="missing.json",
        proposed_catalog_data=None,
    )
    assert receipt["adoption_status"] == "model_role_catalog_adoption_blocked"
    assert any("proposed catalog" in reason for reason in receipt["blocked_reasons"])


def test_losing_required_existing_role_blocks_adoption(tmp_path):
    active_path, active_md_path, proposed_path, active, proposed = _write_catalogs(tmp_path)
    proposed["roles"] = [role for role in proposed["roles"] if role.get("role_id") != "planner"]
    proposed["role_count"] = len(proposed["roles"])
    proposed_path.write_text(json.dumps(proposed, indent=2), encoding="utf-8")

    result = write_model_role_catalog_adoption(
        active_catalog_path=active_path,
        active_catalog_md_path=active_md_path,
        proposed_catalog_path=proposed_path,
        output_dir=tmp_path / "adoption",
    )

    assert result["ok"] is False
    assert result["receipt"]["adoption_status"] == "model_role_catalog_adoption_blocked"
    assert any("loses required existing role: planner" in reason for reason in result["receipt"]["blocked_reasons"])
    assert json.loads(active_path.read_text(encoding="utf-8")) == active


def test_unsafe_authority_flags_block_without_mutating_active_catalog(tmp_path):
    cases = [
        ("executable_binding_allowed", lambda role, data: role.__setitem__("executable_binding_allowed", True)),
        ("model routing", lambda role, data: data.__setitem__("model_routing_enabled", True)),
        ("model calls", lambda role, data: data.__setitem__("model_calls_allowed", True)),
        ("worker launch", lambda role, data: role.__setitem__("launch_worker", True)),
        ("model_id_policy", lambda role, data: role.__setitem__("model_id_policy", "routing_authority")),
    ]
    for fragment, mutate in cases:
        active_path, active_md_path, proposed_path, active, proposed = _write_catalogs(tmp_path / fragment.replace(" ", "_"))
        role = next(role for role in proposed["roles"] if role["role_id"] == "ui_reviewer")
        mutate(role, proposed)
        proposed_path.write_text(json.dumps(proposed, indent=2), encoding="utf-8")

        result = write_model_role_catalog_adoption(
            active_catalog_path=active_path,
            active_catalog_md_path=active_md_path,
            proposed_catalog_path=proposed_path,
            output_dir=active_path.parent / "adoption",
        )

        assert result["ok"] is False, fragment
        assert result["receipt"]["adoption_status"] == "model_role_catalog_adoption_blocked"
        assert any(fragment in reason for reason in result["receipt"]["blocked_reasons"])
        assert json.loads(active_path.read_text(encoding="utf-8")) == active


def test_script_writes_json_and_markdown_receipts(tmp_path):
    active_path, active_md_path, proposed_path, _active, _proposed = _write_catalogs(tmp_path)
    result = script.run_adopt_model_role_catalog(
        active_catalog=str(active_path),
        active_catalog_md=str(active_md_path),
        proposed_catalog=str(proposed_path),
        output_dir=str(tmp_path / "adoption"),
    )

    assert result["ok"] is True
    assert result["summary"]["adoption_status"] == "model_role_catalog_adoption_complete_with_warnings"
    assert Path(result["summary"]["json_path"]).is_file()
    assert Path(result["summary"]["md_path"]).is_file()
    assert result["summary"]["active_catalog_path"] == str(active_path)
    assert result["summary"]["adopted_role_count"] == 10
    assert result["summary"]["recommended_next_phase"] == "ADOPT.MODEL.2"


def test_markdown_contains_required_sections():
    active, proposed = _proposal_bundle()
    receipt = build_model_role_catalog_adoption(
        active_catalog_path="model_role_registry.json",
        active_catalog_data=active,
        proposed_catalog_path="proposed_model_role_registry.json",
        proposed_catalog_data=proposed,
    )
    md = render_model_role_catalog_adoption_markdown(receipt)
    low = md.lower()
    for section in (
        "## summary",
        "## source and active catalog",
        "## role adoption",
        "## safety confirmations",
        "## backups",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_status_constants_match_contract():
    assert set(ADOPTION_STATUSES) == {
        "model_role_catalog_adoption_complete",
        "model_role_catalog_adoption_complete_with_warnings",
        "model_role_catalog_adoption_incomplete",
        "model_role_catalog_adoption_blocked",
    }


def test_phase_registry_marks_adoption_complete_and_picker_recommends_model_2():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}

    assert phases["ADOPT.MODEL.1"]["status"] == "complete"
    assert phases["ADOPT.MODEL.1"]["prerequisites"] == ["HUMAN.CLOSE"]
    assert "core/model_role_catalog_adoption.py" in phases["ADOPT.MODEL.1"]["allowed_files"]
    assert ".agent/model_role_registry/adoption/model_role_catalog_adoption_receipt.json" in phases["ADOPT.MODEL.1"]["expected_artifacts"]
    assert phases["ADOPT.MODEL.2"]["status"] == "proposed"
    assert phases["ADOPT.MODEL.2"]["prerequisites"] == ["ADOPT.MODEL.1"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "ADOPT.MODEL.2"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"


def test_source_has_no_model_routing_worker_launch_or_runtime_imports():
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_catalog_adoption.py",
        root / "scripts" / "adopt_model_role_catalog.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                for bad in (
                    "requests",
                    "httpx",
                    "urllib.request",
                    "socket",
                    "aiohttp",
                    "openai",
                    "anthropic",
                    "litellm",
                    "ollama",
                    "generativeai",
                    "sqlite3",
                    "psycopg",
                    "sqlalchemy",
                    "pymongo",
                    "core.router",
                    "core.driver_model_routing",
                    "web.auth_gate",
                ):
                    assert bad not in imported, f"{path} imports {bad}"
            elif isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                assert name not in {
                    "Popen",
                    "run",
                    "call",
                    "check_call",
                    "check_output",
                    "urlopen",
                    "request",
                    "run_safe_validation",
                    "run_benchmarks",
                    "apply_patch",
                    "patch_apply",
                    "launch_worker",
                    "worker_launch",
                    "spawn_worker",
                }, f"{path} calls forbidden function {name}"
