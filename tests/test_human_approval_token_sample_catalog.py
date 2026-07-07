"""Tests for HUMAN.N4 - Human Approval Token Sample Catalog.

HUMAN.N4 writes documentation-only sample approval tokens and a catalog of
expected HUMAN.N3 dry-run outcomes. It must not issue or consume approvals,
approve/reject work, enforce route behavior, apply patches, run validation or
benchmarks, call models, launch workers, invoke MCP tools, use network access,
or write to databases.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.human_approval_token_contract import build_human_approval_token_contract
from core.human_approval_token_dry_run_validator import (
    STATUS_BLOCKED as DRY_RUN_BLOCKED,
    STATUS_INVALID as DRY_RUN_INVALID,
    STATUS_VALID as DRY_RUN_VALID,
    STATUS_VALID_WITH_WARNINGS as DRY_RUN_VALID_WITH_WARNINGS,
    build_human_approval_token_dry_run,
)
from core.human_approval_token_sample_catalog import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_READY,
    SAMPLE_FILE_NAMES,
    build_human_approval_token_sample_catalog,
    render_human_approval_token_sample_catalog_markdown,
    write_human_approval_token_sample_catalog,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from scripts.create_human_approval_token_sample_catalog import (
    run_create_human_approval_token_sample_catalog,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "human_approval_token_sample_catalog.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_human_approval_token_sample_catalog.py"


def _contract() -> dict:
    return build_human_approval_token_contract(
        report_id="human-n4-contract",
        created_at="2026-07-07T00:00:00+00:00",
        warnings=[],
    )


def _catalog(**kwargs) -> dict:
    return build_human_approval_token_sample_catalog(
        catalog_id="human-n4-test",
        created_at="2026-07-07T00:00:00+00:00",
        **kwargs,
    )


def _samples(catalog: dict) -> dict[str, dict]:
    return {sample["sample_id"]: sample for sample in catalog["sample_tokens"]}


def test_constants_match_human_n4_catalog():
    assert REPORT_KIND == "human_approval_token_sample_catalog"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "human" / "approval_token_sample_catalog"
    assert JSON_NAME == "human_approval_token_sample_catalog.json"
    assert MD_NAME == "human_approval_token_sample_catalog.md"
    assert SAMPLE_FILE_NAMES["valid_patch_apply_token"] == "valid_patch_apply_token.json"


def test_catalog_contains_required_sample_classes_and_status():
    catalog = _catalog()
    samples = _samples(catalog)

    assert catalog["report_kind"] == REPORT_KIND
    assert catalog["catalog_status"] == STATUS_READY
    assert catalog["source_contract_phase"] == "HUMAN.N2"
    assert catalog["source_validator_phase"] == "HUMAN.N3"
    assert {
        "valid_patch_apply_token",
        "warning_validation_run_token",
        "invalid_generic_confirmation_token",
        "blocked_hidden_mutation_token",
    } <= set(samples)
    assert catalog["recommended_next_phase"]["phase_id"] == "HUMAN.CLOSE"


def test_samples_are_documentation_only_and_never_real_approvals():
    catalog = _catalog()

    for sample in catalog["sample_tokens"]:
        assert sample["documentation_only"] is True
        assert sample["safe_to_use_as_real_approval"] is False
        assert sample["token"]["metadata"]["documentation_only"] is True
        assert sample["token"]["metadata"]["sample_catalog_only"] is True
        assert sample["token"]["metadata"]["safe_to_use_as_real_approval"] is False


def test_sample_validation_expectations_cover_valid_warning_invalid_and_blocked():
    catalog = _catalog()
    expectations = catalog["sample_validation_expectations"]
    samples = _samples(catalog)

    assert samples["valid_patch_apply_token"]["expected_dry_run_status"] in {
        DRY_RUN_VALID,
        DRY_RUN_VALID_WITH_WARNINGS,
    }
    assert expectations["valid_patch_apply_token"] in {DRY_RUN_VALID, DRY_RUN_VALID_WITH_WARNINGS}
    assert samples["warning_validation_run_token"]["expected_dry_run_status"] == DRY_RUN_VALID_WITH_WARNINGS
    assert expectations["warning_validation_run_token"] == DRY_RUN_VALID_WITH_WARNINGS
    assert samples["invalid_generic_confirmation_token"]["expected_dry_run_status"] == DRY_RUN_INVALID
    assert expectations["invalid_generic_confirmation_token"] == DRY_RUN_INVALID
    assert samples["blocked_hidden_mutation_token"]["expected_dry_run_status"] == DRY_RUN_BLOCKED
    assert expectations["blocked_hidden_mutation_token"] == DRY_RUN_BLOCKED


def test_samples_match_human_n3_dry_run_expectations():
    catalog = _catalog()
    contract = _contract()

    for sample in catalog["sample_tokens"]:
        report = build_human_approval_token_dry_run(
            token=sample["token"],
            contract=contract,
            source_token_path=f"samples/{sample['sample_id']}.json",
            source_contract_path=".agent/human/approval_token_contract/human_approval_token_contract.json",
            report_id=f"human-n4-{sample['sample_id']}",
            created_at="2026-07-07T00:00:00+00:00",
            now="2026-07-07T12:00:00+00:00",
        )
        expected = sample["expected_dry_run_status"]
        if sample["sample_id"] == "valid_patch_apply_token":
            assert report["dry_run_status"] in {DRY_RUN_VALID, DRY_RUN_VALID_WITH_WARNINGS}
        else:
            assert report["dry_run_status"] == expected
        assert report["final_verdict"]["authorizes_action"] is False


def test_forbidden_usage_section_says_samples_authorize_no_actions():
    catalog = _catalog()
    forbidden = " ".join(catalog["forbidden_usage"]).lower()

    assert "documentation only" in forbidden
    assert "not live approvals" in forbidden
    assert "must not authorize patch apply" in forbidden
    assert "must not authorize worker launch" in forbidden
    assert "must not authorize tool/mcp/network/database actions" in forbidden
    assert "must not bypass auth" in forbidden
    assert "sample presence must not imply user consent" in forbidden


def test_markdown_contains_required_catalog_sections():
    markdown = render_human_approval_token_sample_catalog_markdown(_catalog())
    low = markdown.lower()

    for section in (
        "## summary",
        "## sample tokens",
        "## validation expectations",
        "## documentation notes",
        "## forbidden usage",
        "## warnings",
        "## blocked reasons",
        "## boundaries",
        "## recommended next phase",
    ):
        assert section in low, section
    assert "documentation-only" in low
    assert "human.close" in low


def test_json_markdown_and_optional_sample_files_are_written(tmp_path):
    output_dir = tmp_path / "human-n4"

    result = write_human_approval_token_sample_catalog(
        output_dir=output_dir,
        catalog_id="write-test",
        created_at="2026-07-07T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["catalog_status"] == STATUS_READY
    assert "# Human Approval Token Sample Catalog" in markdown
    for sample_id, file_name in SAMPLE_FILE_NAMES.items():
        path = output_dir / "samples" / file_name
        assert path.is_file(), sample_id
        token = json.loads(path.read_text(encoding="utf-8"))
        assert token == _samples(saved)[sample_id]["token"]


def test_cli_writes_summary_json(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = run_create_human_approval_token_sample_catalog(
        output_dir=output_dir,
        catalog_id="cli-test",
        created_at="2026-07-07T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["summary"]["catalog_status"] == STATUS_READY
    assert result["summary"]["sample_count"] == 4
    assert result["summary"]["recommended_next_phase"] == "HUMAN.CLOSE"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_core_and_cli_do_not_import_or_call_execution_primitives():
    forbidden_imports = {"subprocess", "socket", "requests", "httpx", "urllib", "openai", "anthropic"}
    forbidden_calls = {
        "run_validation",
        "run_safe_validation",
        "run_benchmarks",
        "run_gemini_request",
        "run_deepseek_review",
        "call_model",
        "route_model",
        "apply_patch",
        "launch_worker",
        "invoke_mcp",
    }

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

        assert imports.isdisjoint(forbidden_imports)
        assert calls.isdisjoint(forbidden_calls)


def test_real_registry_marks_human_n4_complete_and_picker_recommends_adopt_model_1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HUMAN.N4"]["status"] == "complete"
    assert by_id["HUMAN.N4"]["prerequisites"] == ["HUMAN.N3"]
    assert by_id["HUMAN.N4"]["expected_artifacts"] == [
        ".agent/human/approval_token_sample_catalog/human_approval_token_sample_catalog.json",
        ".agent/human/approval_token_sample_catalog/human_approval_token_sample_catalog.md",
        ".agent/human/approval_token_sample_catalog/samples/valid_patch_apply_token.json",
        ".agent/human/approval_token_sample_catalog/samples/warning_validation_run_token.json",
        ".agent/human/approval_token_sample_catalog/samples/invalid_generic_confirmation_token.json",
        ".agent/human/approval_token_sample_catalog/samples/blocked_hidden_mutation_token.json",
    ]
    assert by_id["HUMAN.N4"]["network_allowed"] is False
    assert by_id["HUMAN.N4"]["model_calls_allowed"] is False
    assert by_id["HUMAN.N4"]["writes_real_repo"] is False
    assert by_id["HUMAN.CLOSE"]["status"] == "complete"
    assert by_id["HUMAN.CLOSE"]["prerequisites"] == ["HUMAN.N4"]
    assert by_id["HUMAN.CLOSE"]["title"] == "Human Authority Branch Checkpoint"
    assert by_id["ADOPT.MODEL.1"]["status"] == "proposed"
    assert by_id["ADOPT.MODEL.1"]["prerequisites"] == ["HUMAN.CLOSE"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="human-n4-registry",
        created_at="2026-07-07T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "ADOPT.MODEL.1"
