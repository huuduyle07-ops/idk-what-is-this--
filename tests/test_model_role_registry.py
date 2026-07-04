"""Tests for MODEL.N1 - Model Role Registry / Tower Card Contract."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates
from core.model_role_registry import (
    ALLOWED_ROLE_KINDS,
    FORBIDDEN_AUTHORITY_FLAGS,
    GUARDRAIL_FALSE_FLAGS,
    REPORT_KIND,
    build_model_role_registry,
    render_model_role_registry_markdown,
    write_model_role_registry,
)
import scripts.create_model_role_registry as script


def _card(**over) -> dict:
    data = {
        "role_id": "patch_implementer",
        "display_name": "Patch Implementer",
        "role_kind": "implementer",
        "description": "Prepares patch proposals for human review without applying them.",
        "strengths": ["implementation planning", "localized patch preparation"],
        "weaknesses": ["no final approval", "no hidden mutation"],
        "best_for": ["patch proposal preparation"],
        "not_for": ["patch apply", "final approval", "hidden mutation"],
        "risk_level": "medium",
        "cost_tier": "medium",
        "latency_tier": "medium",
        "context_tier": "large",
        "reliability_tier": "normal",
        "evidence_expectation": "cite files, tests, and unresolved risks",
        "allowed_task_types": ["proposal_preparation"],
        "forbidden_task_types": ["patch_apply", "final_approval"],
        "advisory_only": True,
        "executable_binding_allowed": False,
        "model_ids": ["descriptive-label-only"],
        "fallback_roles": [],
        "human_review_required": True,
        "notes": ["Model IDs are labels only, not executable bindings."],
    }
    data.update(over)
    return data


def _catalog(cards=None, **over) -> dict:
    data = {
        "catalog_name": "manual MODEL.N1 catalog",
        "roles": [_card()] if cards is None else cards,
    }
    data.update(over)
    return data


def test_default_catalog_produces_ready_registry():
    registry = build_model_role_registry()
    assert registry["report_kind"] == REPORT_KIND == "model_role_registry"
    assert registry["validation_status"] == "model_roles_ready"
    assert registry["source_inputs"]["input_source"] == "default_catalog"
    role_ids = {card["role_id"] for card in registry["roles"]}
    assert {"fast_scout", "planner", "patch_implementer", "code_reviewer", "evidence_checker", "risk_auditor", "local_fallback"} <= role_ids
    assert registry["coverage_matrix"]["coverage_status"] == "meaningful_coverage"
    assert registry["recommended_next_phase"]["phase_id"] == "MODEL.N2"


def test_custom_catalog_loads_safely_and_stores_model_ids_as_metadata(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(_catalog(), indent=2), encoding="utf-8")
    result = script.run_create_model_role_registry(
        role_catalog=str(catalog_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is True
    registry = result["registry"]
    card = registry["roles"][0]
    assert registry["source_inputs"]["input_source"] == "manual_role_catalog"
    assert card["model_ids"] == ["descriptive-label-only"]
    assert card["model_id_policy"] == "descriptive_metadata_only"
    assert card["executable_binding_allowed"] is False
    assert registry["guardrails"]["model_call_performed"] is False
    assert registry["guardrails"]["routing_changed"] is False


def test_duplicate_role_id_blocks():
    registry = build_model_role_registry(role_catalog=_catalog(cards=[_card(), _card(display_name="Duplicate")]))
    assert registry["validation_status"] == "model_roles_blocked"
    assert any("duplicate role_id" in reason for reason in registry["blocked_reasons"])


def test_unsafe_role_id_blocks():
    registry = build_model_role_registry(role_catalog=_catalog(cards=[_card(role_id="../escape")]))
    assert registry["validation_status"] == "model_roles_blocked"
    assert any("role_id" in reason and "path" in reason for reason in registry["blocked_reasons"])


def test_executable_binding_allowed_true_blocks():
    registry = build_model_role_registry(role_catalog=_catalog(cards=[_card(executable_binding_allowed=True)]))
    assert registry["validation_status"] == "model_roles_blocked"
    assert any("executable_binding_allowed" in reason for reason in registry["blocked_reasons"])


def test_advisory_only_false_blocks():
    registry = build_model_role_registry(role_catalog=_catalog(cards=[_card(advisory_only=False)]))
    assert registry["validation_status"] == "model_roles_blocked"
    assert any("advisory_only" in reason for reason in registry["blocked_reasons"])


def test_forbidden_authority_flags_block():
    for flag in ("auto_run", "auto_apply", "auto_merge", "launch_worker", "route_tasks"):
        registry = build_model_role_registry(role_catalog=_catalog(cards=[_card(**{flag: True})]))
        assert registry["validation_status"] == "model_roles_blocked", flag
        assert any(flag in reason for reason in registry["blocked_reasons"])


def test_unknown_fallback_role_blocks():
    registry = build_model_role_registry(role_catalog=_catalog(cards=[_card(fallback_roles=["missing_role"])]))
    assert registry["validation_status"] == "model_roles_blocked"
    assert any("unknown fallback role" in reason for reason in registry["blocked_reasons"])


def test_allowed_forbidden_task_conflict_blocks():
    registry = build_model_role_registry(
        role_catalog=_catalog(cards=[_card(allowed_task_types=["same"], forbidden_task_types=["same"])])
    )
    assert registry["validation_status"] == "model_roles_blocked"
    assert any("allowed_task_types conflicts" in reason for reason in registry["blocked_reasons"])


def test_implementer_reviewer_and_risk_roles_require_human_review():
    for kind in ("implementer", "reviewer", "risk_auditor"):
        registry = build_model_role_registry(
            role_catalog=_catalog(cards=[_card(role_id=f"{kind}_role", role_kind=kind, human_review_required=False, fallback_roles=[])])
        )
        assert registry["validation_status"] == "model_roles_blocked", kind
        assert any("human_review_required" in reason for reason in registry["blocked_reasons"])


def test_unknown_and_weak_fields_warn_without_execution_power():
    registry = build_model_role_registry(
        role_catalog=_catalog(
            cards=[
                _card(
                    role_id="weak_unknown",
                    role_kind="unknown",
                    strengths=[],
                    best_for=[],
                    risk_level="unknown",
                    cost_tier="unknown",
                    latency_tier="unknown",
                    context_tier="unknown",
                    reliability_tier="unknown",
                    fallback_roles=[],
                )
            ]
        )
    )
    assert registry["validation_status"] == "model_roles_incomplete"
    assert registry["warnings"]
    assert all(value is False for value in registry["guardrails"].values())


def test_json_and_markdown_artifacts_are_written(tmp_path):
    result = write_model_role_registry(output_dir=tmp_path)
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    assert Path(result["json_path"]).name == "model_role_registry.json"
    assert Path(result["md_path"]).name == "model_role_registry.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["validation_status"] == "model_roles_ready"
    assert "## Model/Tower Cards" in Path(result["md_path"]).read_text(encoding="utf-8")


def test_malformed_catalog_blocks_safely(tmp_path):
    catalog_path = tmp_path / "bad.json"
    catalog_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_registry(
        role_catalog=str(catalog_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["registry"]["validation_status"] == "model_roles_blocked"
    assert any("role_catalog must contain valid JSON" in reason for reason in result["registry"]["blocked_reasons"])


def test_catalog_role_entries_must_be_objects():
    registry = build_model_role_registry(role_catalog={"roles": ["not-an-object"]})
    assert registry["validation_status"] == "model_roles_blocked"
    assert any("roles[0]" in reason and "JSON object" in reason for reason in registry["blocked_reasons"])


def test_markdown_contains_required_sections_and_guardrails():
    md = render_model_role_registry_markdown(build_model_role_registry())
    low = md.lower()
    for section in (
        "## summary",
        "## role catalog source",
        "## model/tower cards",
        "## coverage matrix",
        "## risk and cost tiers",
        "## fallback role map",
        "## forbidden authority checks",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section
    assert "does not route tasks" in low
    assert "does not call models" in low
    assert "writes model role registry artifacts only" in low


def test_constants_match_contract():
    assert set(ALLOWED_ROLE_KINDS) == {
        "scout",
        "planner",
        "implementer",
        "reviewer",
        "evidence_checker",
        "risk_auditor",
        "summarizer",
        "fallback",
        "local_offline",
        "unknown",
    }
    assert set(FORBIDDEN_AUTHORITY_FLAGS) == {
        "auto_run",
        "auto_apply",
        "auto_merge",
        "route_tasks",
        "launch_worker",
        "run_validation",
        "run_benchmark",
        "mutate_files",
        "approve_patch",
    }


_ROOT = Path(__file__).parent.parent
_CORE = _ROOT / "core" / "model_role_registry.py"
_SCRIPT = _ROOT / "scripts" / "create_model_role_registry.py"


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
    for path in (_CORE, _SCRIPT):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path == _CORE and top:
                    assert top in allowed_core_imports, f"Unexpected import in core: {module!r}"
                for bad in (
                    "subprocess",
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


def test_registry_and_picker_recommend_model_n2():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["CMD.CLOSE"]["status"] == "complete"
    assert phases["MODEL.N1"]["status"] == "complete"
    assert phases["MODEL.N1"]["prerequisites"] == ["CMD.CLOSE"]
    assert phases["MODEL.N2"]["status"] == "proposed"
    assert phases["MODEL.N2"]["prerequisites"] == ["MODEL.N1"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "MODEL.N2"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"

