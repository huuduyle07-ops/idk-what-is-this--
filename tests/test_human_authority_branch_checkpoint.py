"""Tests for HUMAN.CLOSE - Human Authority Branch Checkpoint.

HUMAN.CLOSE is report-only. It freezes HUMAN.N1-HUMAN.N4 before any runtime
approval enforcement, route integration, token issuance, token consumption,
worker launch, validation run, benchmark run, model routing, or patch apply path
is added.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.human_authority_branch_checkpoint import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REQUIRED_HUMAN_PHASE_IDS,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_INCOMPLETE,
    THIS_PHASE_ID,
    build_human_authority_branch_checkpoint,
    render_human_authority_branch_checkpoint_markdown,
    write_human_authority_branch_checkpoint,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from scripts.create_human_authority_branch_checkpoint import (
    run_create_human_authority_branch_checkpoint,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "human_authority_branch_checkpoint.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_human_authority_branch_checkpoint.py"


def _phase(phase_id: str, **over) -> dict:
    data = {
        "phase_id": phase_id,
        "title": f"{phase_id} title",
        "track": "HUMAN" if phase_id.startswith("HUMAN") else "ADOPT",
        "status": "complete",
        "summary": "Report-only phase.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/x.py", "tests/test_x.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest tests/test_x.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/human/x.json"],
        "notes": ["Report-only; adds no runtime power."],
    }
    data.update(over)
    return data


def _registry(*, drop: tuple[str, ...] = (), close_status: str = "complete") -> dict:
    phases = []
    for phase_id in REQUIRED_HUMAN_PHASE_IDS:
        if phase_id not in drop:
            phases.append(_phase(phase_id))
    if THIS_PHASE_ID not in drop:
        phases.append(_phase(THIS_PHASE_ID, status=close_status, prerequisites=["HUMAN.N4"]))
    if "ADOPT.MODEL.1" not in drop:
        phases.append(
            _phase(
                "ADOPT.MODEL.1",
                title="Human-Approved Model Role Catalog Adoption",
                track="ADOPT",
                status="proposed",
                prerequisites=[THIS_PHASE_ID],
                expected_artifacts=[
                    ".agent/adopt/model_role_catalog_adoption/model_role_catalog_adoption.json",
                    ".agent/adopt/model_role_catalog_adoption/model_role_catalog_adoption.md",
                ],
            )
        )
    return {"schema_version": "1.0", "updated_at": "2026-07-08T00:00:00+09:00", "phases": phases}


def _guardrails(**over) -> dict:
    data = {
        "report_only": True,
        "model_call_performed": False,
        "model_routing_performed": False,
        "worker_launch_performed": False,
        "patch_apply_performed": False,
        "validation_run_performed": False,
        "benchmark_run_performed": False,
        "mcp_invocation_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "docker_or_subprocess_used": False,
        "network_contacted": False,
        "database_write_performed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "approval_or_rejection_performed": False,
        "token_consumption_performed": False,
        "runtime_enforcement_added": False,
    }
    data.update(over)
    return data


def _boundary_map(**over) -> dict:
    data = {
        "report_kind": "human_review_boundary_map",
        "boundary_status": "human_review_boundary_ready",
        "authority_philosophy": [
            "Humans retain authority over approval, rejection, mutation, routing, execution, and risk acceptance.",
            "Automatic approval/rejection and hidden mutation remain blocked.",
        ],
        "human_only_decisions": [
            "approve patch apply",
            "approve worker launch",
            "approve model catalog adoption",
            "accept validation or benchmark execution risk",
        ],
        "explicit_approval_actions": [
            {"action_id": "patch_apply", "human_decision": "explicit human approval required"},
            {"action_id": "worker_launch", "human_decision": "explicit human approval required"},
            {"action_id": "model_catalog_adoption", "human_decision": "explicit human approval required"},
            {"action_id": "validation_benchmark_execution", "human_decision": "explicit human approval required"},
        ],
        "forbidden_automatic_actions": [
            {"action_id": "auto_approve", "automatic_allowed": False},
            {"action_id": "auto_reject", "automatic_allowed": False},
            {"action_id": "hidden_mutation", "automatic_allowed": False},
        ],
        "branch_specific_boundaries": {
            "MODEL": {
                "may": ["display advisory model-role labels"],
                "may_not": ["route models automatically"],
                "human_only": ["adopt model catalog changes"],
            },
            "HUMAN": {
                "may": ["document approval-token boundaries"],
                "may_not": ["enforce approvals at runtime"],
                "human_only": ["approve or reject work"],
            },
        },
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": _guardrails(),
    }
    data.update(over)
    return data


def _contract(**over) -> dict:
    data = {
        "report_kind": "human_approval_token_contract",
        "contract_status": "approval_token_contract_ready",
        "allowed_approval_actions": [
            "approve_patch_apply",
            "approve_worker_launch",
            "approve_validation_run",
            "approve_benchmark_run",
            "approve_model_catalog_adoption",
        ],
        "forbidden_token_behavior": [
            "approval tokens are documentation/dry-run only",
            "dry-run valid tokens do not authorize real actions",
            "auto-approve and auto-reject are blocked",
            "hidden mutation is blocked",
            "token issuance and consumption are future enforcement work only",
        ],
        "policy_sections": {
            "documentation_only": {"approval_tokens_authorize_runtime_action": False},
            "future_enforcement": {"requires_explicit_human_approval": True},
        },
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": _guardrails(),
    }
    data.update(over)
    return data


def _sample(sample_id: str, file_name: str, **over) -> dict:
    data = {
        "sample_id": sample_id,
        "sample_class": "valid_sample",
        "expected_dry_run_status": "token_dry_run_valid",
        "documentation_only": True,
        "safe_to_use_as_real_approval": False,
        "sample_artifact_path": f".agent/human/approval_token_sample_catalog/samples/{file_name}",
        "token": {
            "token_id": sample_id,
            "metadata": {
                "documentation_only": True,
                "sample_catalog_only": True,
                "safe_to_use_as_real_approval": False,
            },
        },
    }
    data.update(over)
    return data


def _catalog(**over) -> dict:
    samples = [
        _sample("valid_patch_apply_token", "valid_patch_apply_token.json"),
        _sample("warning_validation_run_token", "warning_high_risk_no_expiry_token.json"),
        _sample("invalid_generic_confirmation_token", "invalid_generic_confirmation_token.json"),
        _sample("blocked_hidden_mutation_token", "blocked_hidden_mutation_token.json"),
    ]
    data = {
        "report_kind": "human_approval_token_sample_catalog",
        "catalog_status": "approval_token_sample_catalog_ready",
        "source_contract_phase": "HUMAN.N2",
        "source_validator_phase": "HUMAN.N3",
        "sample_tokens": samples,
        "sample_validation_expectations": {
            str(sample["sample_id"]): str(sample["expected_dry_run_status"]) for sample in samples
        },
        "documentation_notes": [
            "Sample tokens are documentation only.",
            "Sample tokens are not live approvals.",
            "A valid dry-run sample does not authorize a real action.",
        ],
        "forbidden_usage": [
            "samples must not authorize patch apply",
            "samples must not authorize worker launch",
            "samples must not be accepted by runtime routes",
        ],
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": _guardrails(),
    }
    data.update(over)
    return data


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_fake_repo(
    root: Path,
    *,
    registry: dict | None = None,
    boundary_map: dict | None = None,
    contract: dict | None = None,
    catalog: dict | None = None,
    write_boundary: bool = True,
    write_catalog: bool = True,
    write_validator: bool = True,
) -> Path:
    _write_json(root / "docs" / "roadmap" / "phase_registry.json", registry or _registry())
    if write_boundary:
        _write_json(root / ".agent" / "human" / "review_boundary_map" / "human_review_boundary_map.json", boundary_map or _boundary_map())
    _write_json(
        root / ".agent" / "human" / "approval_token_contract" / "human_approval_token_contract.json",
        contract or _contract(),
    )
    if write_validator:
        validator = root / "core" / "human_approval_token_dry_run_validator.py"
        validator.parent.mkdir(parents=True, exist_ok=True)
        validator.write_text('REPORT_KIND = "human_approval_token_dry_run"\n', encoding="utf-8")
    if write_catalog:
        sample_catalog = catalog or _catalog()
        _write_json(
            root / ".agent" / "human" / "approval_token_sample_catalog" / "human_approval_token_sample_catalog.json",
            sample_catalog,
        )
        for sample in sample_catalog.get("sample_tokens", []):
            path = root / str(sample.get("sample_artifact_path", ""))
            _write_json(path, sample.get("token") or {})
    return root


def _build(root: Path, **kwargs) -> dict:
    _write_fake_repo(root, **kwargs)
    return build_human_authority_branch_checkpoint(
        repo_root=root,
        registry_path="docs/roadmap/phase_registry.json",
        report_id="test-human-close",
        created_at="2026-07-08T00:00:00+09:00",
    )


def _blocked_reasons(report: dict) -> list[str]:
    return [str(item.get("reason", item)) for item in report.get("blocked_reasons", [])]


def test_constants_match_spec():
    assert REPORT_KIND == "human_authority_branch_checkpoint"
    assert THIS_PHASE_ID == "HUMAN.CLOSE"
    assert REQUIRED_HUMAN_PHASE_IDS == ("HUMAN.N1", "HUMAN.N2", "HUMAN.N3", "HUMAN.N4")
    assert STATUS_FROZEN == "human_authority_branch_frozen"
    assert STATUS_FROZEN_WITH_WARNINGS == "human_authority_branch_frozen_with_warnings"
    assert STATUS_INCOMPLETE == "human_authority_branch_incomplete"
    assert STATUS_BLOCKED == "human_authority_branch_blocked"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "human" / "authority_branch_checkpoint"


def test_complete_human_n1_to_n4_registry_produces_frozen_with_warnings(tmp_path):
    report = _build(tmp_path)

    assert report["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert report["summary"]["all_required_human_phases_complete"] is True
    assert report["summary"]["required_artifacts_present"] is True
    assert report["authority_boundary_summary"]["patch_apply_requires_explicit_human_approval"] is True
    assert report["authority_boundary_summary"]["worker_launch_requires_explicit_human_approval"] is True
    assert report["authority_boundary_summary"]["model_catalog_adoption_requires_explicit_human_approval"] is True
    assert report["approval_token_contract_summary"]["approval_tokens_are_documentation_or_dry_run_only"] is True
    assert report["sample_catalog_summary"]["sample_tokens_are_not_real_approvals"] is True
    assert report["runtime_non_enforcement_verification"]["no_runtime_enforcement_route_added"] is True
    assert report["forbidden_authority_checks"]["auto_approve_and_auto_reject_blocked"] is True
    assert report["human_approval_boundary"]["planning_only"] is True
    assert report["blocked_reasons"] == []
    assert any("future work" in warning.lower() for warning in report["warnings"])
    assert report["recommended_next_phase"]["phase_id"] == "ADOPT.MODEL.1"


def test_complete_human_branch_can_freeze_without_warnings_when_enforcement_boundary_is_explicit(tmp_path):
    report = _build(
        tmp_path,
        contract=_contract(
            policy_sections={
                "documentation_only": {"approval_tokens_authorize_runtime_action": False},
                "future_enforcement": {"requires_explicit_human_approval": True},
                "future_enforcement_boundary": {"explicit": True},
            }
        ),
        catalog=_catalog(warnings=[]),
    )

    assert report["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS}
    assert report["blocked_reasons"] == []


def test_missing_human_n4_reports_incomplete(tmp_path):
    report = _build(tmp_path, registry=_registry(drop=("HUMAN.N4",)))

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("HUMAN.N4" in reason for reason in report["incomplete_reasons"])


def test_missing_sample_catalog_reports_incomplete(tmp_path):
    report = _build(tmp_path, write_catalog=False)

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("sample catalog" in reason.lower() for reason in report["incomplete_reasons"])


def test_missing_boundary_map_reports_incomplete(tmp_path):
    report = _build(tmp_path, write_boundary=False)

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("boundary map" in reason.lower() for reason in report["incomplete_reasons"])


def test_missing_dry_run_validator_reports_incomplete(tmp_path):
    report = _build(tmp_path, write_validator=False)

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("dry-run validator" in reason.lower() for reason in report["incomplete_reasons"])


def test_approval_token_treated_as_real_authority_blocks(tmp_path):
    report = _build(
        tmp_path,
        catalog=_catalog(
            sample_tokens=[
                _sample(
                    "valid_patch_apply_token",
                    "valid_patch_apply_token.json",
                    safe_to_use_as_real_approval=True,
                )
            ]
        ),
    )

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert "approval_token_treated_as_real_authority" in _blocked_reasons(report)


@pytest.mark.parametrize("marker", ["auto_approve_allowed", "auto_reject_allowed"])
def test_auto_approve_or_auto_reject_allowed_blocks(tmp_path, marker):
    report = _build(tmp_path, boundary_map=_boundary_map(**{marker: True}))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert marker in _blocked_reasons(report)


def test_hidden_mutation_allowed_blocks(tmp_path):
    report = _build(tmp_path, boundary_map=_boundary_map(hidden_mutation_allowed=True))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert "hidden_mutation_allowed" in _blocked_reasons(report)


def test_blocked_hidden_mutation_sample_documents_forbidden_case_without_blocking(tmp_path):
    catalog = _catalog()
    catalog["sample_tokens"][3]["expected_dry_run_status"] = "token_dry_run_blocked"
    catalog["sample_tokens"][3]["token"]["metadata"]["hidden_mutation"] = True
    catalog["sample_tokens"][3]["token"]["metadata"]["bypass_auth"] = True

    report = _build(tmp_path, catalog=catalog)

    assert report["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert "hidden_mutation_allowed" not in _blocked_reasons(report)


@pytest.mark.parametrize(
    "marker",
    [
        "token_issuance_path",
        "token_consumption_path",
        "runtime_enforcement_added",
        "approval_gate_added",
        "route_behavior_changed",
        "auth_policy_changed",
        "patch_apply_path_changed",
        "validation_execution_path_changed",
        "benchmark_execution_path_changed",
        "worker_launch_path_changed",
    ],
)
def test_forbidden_runtime_or_route_markers_block(tmp_path, marker):
    report = _build(tmp_path, contract=_contract(**{marker: True}))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert marker in _blocked_reasons(report)


def test_checkpoint_json_and_markdown_artifacts_are_written(tmp_path):
    _write_fake_repo(tmp_path)
    output_dir = tmp_path / "out"

    result = write_human_authority_branch_checkpoint(
        repo_root=tmp_path,
        registry_path="docs/roadmap/phase_registry.json",
        output_dir=output_dir,
        report_id="write-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    for section in (
        "## Summary",
        "## Phase Completion",
        "## Artifact Coverage",
        "## Authority Boundary Summary",
        "## Approval Token Contract Summary",
        "## Dry-Run Validator Summary",
        "## Sample Catalog Summary",
        "## Runtime Non-Enforcement Verification",
        "## Forbidden Authority Checks",
        "## Human Approval Boundary",
        "## Warnings",
        "## Blocked Reasons",
        "## Final Verdict",
        "## Recommended Next Phase",
        "## Boundaries / Guardrails",
    ):
        assert section in markdown


def test_script_writes_summary_json(tmp_path):
    _write_fake_repo(tmp_path)

    result = run_create_human_authority_branch_checkpoint(
        repo_root=tmp_path,
        registry_path="docs/roadmap/phase_registry.json",
        output_dir=tmp_path / "cli-out",
        report_id="cli-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "ADOPT.MODEL.1"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_renderer_does_not_mutate_report(tmp_path):
    report = _build(tmp_path)
    before = json.loads(json.dumps(report, sort_keys=True))
    assert render_human_authority_branch_checkpoint_markdown(report)
    assert report == before


def test_checkpoint_core_and_cli_do_not_import_or_call_execution_primitives():
    for path in (CORE_PATH, SCRIPT_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.add(func.attr)

        assert imports.isdisjoint(
            {"subprocess", "socket", "requests", "httpx", "urllib", "openai", "anthropic", "sqlite3"}
        )
        assert calls.isdisjoint(
            {
                "run_validation",
                "run_safe_validation",
                "run_benchmarks",
                "run_gemini_request",
                "run_deepseek_review",
                "apply_patch",
                "patch_apply",
                "launch_worker",
                "spawn_worker",
                "invoke_mcp",
                "issue_token",
                "consume_token",
            }
        )


def test_real_registry_marks_human_close_complete_and_picker_recommends_adopt_model_1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HUMAN.CLOSE"]["status"] == "complete"
    assert by_id["HUMAN.CLOSE"]["prerequisites"] == ["HUMAN.N4"]
    assert by_id["HUMAN.CLOSE"]["expected_artifacts"] == [
        ".agent/human/authority_branch_checkpoint/human_authority_branch_checkpoint.json",
        ".agent/human/authority_branch_checkpoint/human_authority_branch_checkpoint.md",
    ]
    assert by_id["HUMAN.CLOSE"]["network_allowed"] is False
    assert by_id["HUMAN.CLOSE"]["model_calls_allowed"] is False
    assert by_id["HUMAN.CLOSE"]["writes_real_repo"] is False
    assert by_id["ADOPT.MODEL.1"]["status"] == "proposed"
    assert by_id["ADOPT.MODEL.1"]["prerequisites"] == ["HUMAN.CLOSE"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="human-close-checkpoint",
        created_at="2026-07-08T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "ADOPT.MODEL.1"
    assert report["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
