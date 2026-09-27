"""Static boundary regressions for WORKER.DECL.2B."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import core.pre_execution_change_intent as intent
import core.run_lifecycle as lifecycle
import core.worker_patch_envelope as envelope
import scripts.run_patch_proposal_queue as queue


ROOT = Path(__file__).resolve().parents[1]
INTENT_SOURCE = (ROOT / "core" / "pre_execution_change_intent.py").read_text(
    encoding="utf-8"
)


def _calls(function) -> list[str]:
    tree = ast.parse(inspect.getsource(function))
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Attribute):
            names.append(target.attr)
    return names


def test_the_v2_parser_is_strict_and_does_not_call_the_legacy_extractor():
    calls = _calls(envelope.parse_strict_worker_patch_envelope_v2)
    assert "extract_json_block" not in calls
    assert "raw_decode" not in calls
    assert "search" not in calls
    assert "findall" not in calls
    assert "strip" in calls
    assert "loads" in calls


def test_intent_capture_performs_no_model_network_validation_or_repository_work():
    forbidden = {
        "run_gemini_request",
        "run_gemini_request_2",
        "generate_content",
        "requests",
        "urlopen",
        "subprocess",
        "run",
        "apply_patch_plan",
        "run_validation",
        "rglob",
        "glob",
        "walk",
    }
    calls = set(_calls(intent.capture_pre_execution_change_intent))
    calls |= set(_calls(intent.safe_capture_pre_execution_change_intent))
    assert calls.isdisjoint(forbidden)
    assert "core.json_utils" not in INTENT_SOURCE
    assert "extract_json_block" not in INTENT_SOURCE
    assert "import re" not in INTENT_SOURCE


def test_intent_is_not_imported_by_or_fed_into_the_patch_executor():
    apply_source = inspect.getsource(lifecycle.run_patch_plan_with_artifacts)
    patch_files_source = inspect.getsource(lifecycle._patch_plan_files)
    assert apply_source.count("apply_patch_plan(") == 1
    assert "apply_patch_plan(\n        project_root,\n        plan," in apply_source
    assert "intent" not in patch_files_source
    assert "change_intent.patch_plan" not in apply_source
    assert "union(" not in apply_source


def test_the_proposal_queue_still_has_exactly_one_generation_call():
    assert _calls(queue._generate_patch_payload).count("run_gemini_request_2") == 1
    process_calls = _calls(queue._process_item)
    assert process_calls.count("_generate_patch_payload") == 1
    assert "run_gemini_request_2" not in _calls(
        intent.capture_pre_execution_change_intent
    )


def test_no_checker_is_promoted_and_check_2_is_absent():
    lowered = INTENT_SOURCE.lower()
    assert "goal_fidelity_review" not in lowered
    assert "claim_assessment" not in lowered
    assert "check_2" not in lowered.replace('"check_2_invoked": false', "")
    guardrails = intent.pre_execution_change_intent_guardrails()
    assert guardrails["checker_promoted"] is False
    assert guardrails["check_2_invoked"] is False
    assert guardrails["authoritative_effect"] is False


def test_guardrails_pin_all_required_zero_deltas():
    guardrails = intent.pre_execution_change_intent_guardrails()
    assert guardrails["model_call_added"] is False
    assert guardrails["network_call_added"] is False
    assert guardrails["validation_executed"] is False
    assert guardrails["repository_traversed"] is False
    assert guardrails["patch_plan_modified"] is False
    assert guardrails["path_authority_granted"] is False
    assert guardrails["temp_repository_retained"] is False


def test_durable_receipt_builder_has_no_response_or_source_body_parameter():
    parameters = set(inspect.signature(intent.build_durable_intent_receipt).parameters)
    assert parameters == {
        "case_identity",
        "run_identity",
        "capture",
        "shadow_receipt",
        "authoritative_outcome",
    }
    assert "raw_response" not in parameters
    assert "prompt" not in parameters
    assert "source" not in parameters

