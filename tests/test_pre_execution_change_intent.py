"""WORKER.DECL.2B — pre-execution change intent channel."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from core.live_worker_declaration import (
    DECLARATION_SOURCE_LEGACY_PLAN_DERIVED,
    DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
    DECLARATION_STAGE_PRE_EXECUTION_INTENT,
)
from core.post_run_reconciliation_shadow import load_shadow_post_run_check
from core.pre_execution_change_intent import (
    INTENDED_KIND_MISMATCH,
    INTENDED_NOT_OBSERVED,
    INTENT_ARTIFACT_NAME,
    INTENT_MISSING_PLAN_CHANGE,
    INTENT_OBSERVED_AGREED,
    INTENT_PLAN_AGREED,
    INTENT_PLAN_KIND_MISMATCH,
    INTENT_PLAN_MIXED,
    INTENT_PLAN_UNAVAILABLE,
    OBSERVED_NOT_INTENDED,
    PLAN_CHANGE_MISSING_INTENT,
    STRICT_V2_NOT_REQUESTED,
    PreExecutionIntentCapture,
    build_durable_intent_receipt,
    capture_pre_execution_change_intent,
    compare_intent_with_observed_changes,
    intent_emission_directive,
    safe_capture_pre_execution_change_intent,
    summarize_durable_intent_receipts,
    worker_change_declaration_from_intent_capture,
)
from core.run_lifecycle import run_patch_plan_with_artifacts
from core.strict_envelope_emission import (
    PROVIDER_GOOGLE,
    STRATEGY_PROVIDER_NATIVE_JSON,
    STRATEGY_STRICT_PROMPT,
    strict_emission_directive,
)
from core.worker_patch_envelope import (
    MAX_INTENDED_CHANGES,
    STATUS_BOUND_EXCEEDED,
    STATUS_SCHEMA_INVALID,
    STATUS_UNKNOWN_FIELD,
    STATUS_VALID,
    WORKER_PATCH_ENVELOPE_SCHEMA_VERSION,
    WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2,
    parse_strict_worker_patch_envelope,
    parse_strict_worker_patch_envelope_v2,
)
import scripts.run_patch_proposal_queue as proposal_queue


EDIT_A = {
    "op": "replace_snippet",
    "relative_path": "A.py",
    "target_snippet": "VALUE = 1\n",
    "patched_snippet": "VALUE = 2\n",
}
EDIT_B = {**EDIT_A, "relative_path": "B.py"}


def _v2(plan=None, changes=None, **extra):
    payload = {
        "schema_version": WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2,
        "patch_plan": list(plan if plan is not None else [EDIT_A]),
        "change_intent": {
            "stage": "pre_execution_intent",
            "intended_changes": list(
                changes
                if changes is not None
                else [{"path": "A.py", "change_kind": "modified"}]
            ),
        },
    }
    payload.update(extra)
    return json.dumps(payload)


def _directive(strategy="strict_prompt"):
    return intent_emission_directive(
        strict_emission_directive(
            PROVIDER_GOOGLE,
            patch_plan_is_declared_shape=True,
            value=strategy,
        ),
        value=True,
    )


def _capture(plan=None, changes=None, strategy="strict_prompt"):
    return capture_pre_execution_change_intent(
        _v2(plan=plan, changes=changes),
        _directive(strategy),
        value=True,
    )


def test_v2_exact_object_is_valid_and_v1_keeps_its_original_meaning():
    v2 = parse_strict_worker_patch_envelope_v2(_v2())
    assert v2.status == STATUS_VALID
    assert v2.envelope is not None
    assert v2.envelope.change_intent is not None
    assert v2.envelope.change_intent.intended_changes[0].path == "A.py"

    v1_text = json.dumps(
        {
            "schema_version": WORKER_PATCH_ENVELOPE_SCHEMA_VERSION,
            "patch_plan": [EDIT_A],
        }
    )
    assert parse_strict_worker_patch_envelope(v1_text).status == STATUS_VALID
    assert parse_strict_worker_patch_envelope(_v2()).status == STATUS_UNKNOWN_FIELD


def test_v2_missing_intent_is_rejected_without_backfill():
    raw = json.dumps(
        {
            "schema_version": WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2,
            "patch_plan": [EDIT_A],
        }
    )
    parsed = parse_strict_worker_patch_envelope_v2(raw)
    assert parsed.status == STATUS_SCHEMA_INVALID
    assert parsed.envelope is None
    assert parsed.unknown_keys == ("change_intent",)


@pytest.mark.parametrize("path", ["/abs.py", "../escape.py", "C:/drive.py"])
def test_unsafe_intent_paths_are_rejected(path):
    parsed = parse_strict_worker_patch_envelope_v2(
        _v2(changes=[{"path": path, "change_kind": "modified"}])
    )
    assert parsed.status == STATUS_SCHEMA_INVALID


def test_unknown_intent_field_and_invalid_kind_are_rejected():
    payload = json.loads(_v2())
    payload["change_intent"]["confidence"] = 1
    assert (
        parse_strict_worker_patch_envelope_v2(json.dumps(payload)).status
        == STATUS_UNKNOWN_FIELD
    )
    assert (
        parse_strict_worker_patch_envelope_v2(
            _v2(changes=[{"path": "A.py", "change_kind": "deleted"}])
        ).status
        == STATUS_SCHEMA_INVALID
    )


def test_duplicate_conflicting_intent_is_rejected_not_normalized():
    parsed = parse_strict_worker_patch_envelope_v2(
        _v2(
            changes=[
                {"path": "A.py", "change_kind": "modified"},
                {"path": "A.py", "change_kind": "added"},
            ]
        )
    )
    assert parsed.status == STATUS_SCHEMA_INVALID


def test_oversized_intent_rejects_the_whole_envelope():
    changes = [
        {"path": f"p{index}.py", "change_kind": "modified"}
        for index in range(MAX_INTENDED_CHANGES + 1)
    ]
    parsed = parse_strict_worker_patch_envelope_v2(_v2(changes=changes))
    assert parsed.status == STATUS_BOUND_EXCEEDED
    assert parsed.envelope is None


@pytest.mark.parametrize(
    ("plan", "changes", "expected"),
    [
        ([EDIT_A], [{"path": "A.py", "change_kind": "modified"}], INTENT_PLAN_AGREED),
        (
            [EDIT_A, EDIT_B],
            [{"path": "A.py", "change_kind": "modified"}],
            PLAN_CHANGE_MISSING_INTENT,
        ),
        (
            [EDIT_A],
            [
                {"path": "A.py", "change_kind": "modified"},
                {"path": "B.py", "change_kind": "modified"},
            ],
            INTENT_MISSING_PLAN_CHANGE,
        ),
        (
            [EDIT_A],
            [{"path": "A.py", "change_kind": "added"}],
            INTENT_PLAN_KIND_MISMATCH,
        ),
    ],
)
def test_intent_and_plan_may_disagree_without_invalidating_v2(plan, changes, expected):
    capture = _capture(plan=plan, changes=changes)
    assert capture is not None
    assert capture.strict_v2_status == STATUS_VALID
    assert capture.intent_plan_agreement == expected


def test_a_legacy_directive_never_launders_json_into_native_intent():
    legacy = strict_emission_directive(
        PROVIDER_GOOGLE,
        patch_plan_is_declared_shape=True,
        value="legacy_prompt",
    )
    capture = capture_pre_execution_change_intent(_v2(), legacy, value=True)
    assert capture is not None
    assert capture.strict_v2_status == STRICT_V2_NOT_REQUESTED
    assert not capture.native_intent_available
    assert capture.intent_plan_agreement == INTENT_PLAN_UNAVAILABLE


def test_v2_uses_the_existing_strict_prompt_and_native_json_transports():
    prompt = _directive("strict_prompt")
    native = _directive("provider_native_json")
    assert prompt.strategy == STRATEGY_STRICT_PROMPT
    assert prompt.response_mime_type is None
    assert native.strategy == STRATEGY_PROVIDER_NATIVE_JSON
    assert native.response_mime_type == "application/json"
    assert WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2 in prompt.prompt_suffix
    assert '"change_intent"' in native.prompt_suffix


@pytest.mark.parametrize(
    ("strategy", "expected_kwargs"),
    [
        ("strict_prompt", {}),
        ("provider_native_json", {"response_mime_type": "application/json"}),
    ],
)
def test_proposal_queue_v2_adds_no_model_or_network_call(
    tmp_path, monkeypatch, strategy, expected_kwargs
):
    repo = tmp_path / "repo"
    repo.mkdir()
    case = {"name": "case", "language": "python", "prompt": "fix it"}
    monkeypatch.setattr(proposal_queue, "_file_context", lambda _repo, _case: "")
    calls = []

    def fake_model(*, prompt, repo_path=None, **kwargs):
        calls.append({"prompt": prompt, "repo_path": repo_path, "kwargs": kwargs})
        return _v2()

    gemini = ModuleType("agents.gemini_client")
    gemini.run_gemini_request_2 = fake_model
    monkeypatch.setitem(sys.modules, "agents.gemini_client", gemini)
    emission = _directive(strategy)
    payload, raw = proposal_queue._generate_patch_payload(
        temp_repo=repo,
        item={"title": "t"},
        case=case,
        emission=emission,
    )

    assert len(calls) == 1
    assert calls[0]["kwargs"] == expected_kwargs
    assert calls[0]["prompt"].endswith(emission.prompt_suffix)
    assert payload["patch_plan"] == [EDIT_A]
    assert json.loads(raw)["change_intent"]["stage"] == "pre_execution_intent"


def test_native_intent_adapts_to_the_live_declaration_stage_and_provenance():
    capture = _capture()
    declaration = worker_change_declaration_from_intent_capture(
        capture, execution_run_id="run-1"
    )
    assert declaration is not None
    assert declaration.declaration_stage == DECLARATION_STAGE_PRE_EXECUTION_INTENT
    assert declaration.source_provenance == DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT
    assert declaration.intent_fidelity_measurable is True
    assert declaration.self_report_fidelity_measurable is False
    assert declaration.channel_provenance == "independently_declared_channel"
    assert declaration.declared_changes[0].path == "A.py"


def test_intent_observed_diagnostics_keep_three_way_disagreement_visible():
    intent = _capture(
        changes=[
            {"path": "A.py", "change_kind": "modified"},
            {"path": "B.py", "change_kind": "modified"},
        ]
    ).intent
    diagnostic = compare_intent_with_observed_changes(
        intent,
        [
            SimpleNamespace(path="A.py", change_kind="modified"),
            SimpleNamespace(path="generated.py", change_kind="added"),
        ],
    )
    assert diagnostic.relation == "mixed"
    assert diagnostic.intended_and_observed == ("A.py",)
    assert diagnostic.intended_not_observed == ("B.py",)
    assert diagnostic.observed_not_intended == ("generated.py",)


@pytest.mark.parametrize(
    ("observed", "relation"),
    [
        ([SimpleNamespace(path="A.py", change_kind="modified")], INTENT_OBSERVED_AGREED),
        ([], INTENDED_NOT_OBSERVED),
        (
            [
                SimpleNamespace(path="A.py", change_kind="modified"),
                SimpleNamespace(path="extra.py", change_kind="added"),
            ],
            OBSERVED_NOT_INTENDED,
        ),
        ([SimpleNamespace(path="A.py", change_kind="deleted")], INTENDED_KIND_MISMATCH),
    ],
)
def test_each_intent_observed_relation_is_bounded_and_derived(observed, relation):
    diagnostic = compare_intent_with_observed_changes(_capture().intent, observed)
    assert diagnostic.relation == relation


def test_malformed_native_intent_cannot_fail_or_replace_the_authoritative_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("PRE_EXECUTION_CHANGE_INTENT", "1")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "A.py").write_text("VALUE = 1\n", encoding="utf-8")
    malformed = _v2(changes=[{"path": "../escape.py", "change_kind": "modified"}])
    capture = safe_capture_pre_execution_change_intent(
        malformed, _directive(), value=True
    )
    assert capture is not None and not capture.native_intent_available

    result = run_patch_plan_with_artifacts(
        str(repo),
        [EDIT_A],
        pre_execution_intent_capture=capture,
    )
    assert result["success"] is True
    assert (repo / "A.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    receipt = load_shadow_post_run_check(result["replay_dir"])
    assert receipt["worker_declaration_source"] == DECLARATION_SOURCE_LEGACY_PLAN_DERIVED
    assert receipt["intent_fidelity_measurable"] is False


def test_intent_grants_no_authority_and_changes_no_patch_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("PRE_EXECUTION_CHANGE_INTENT", "1")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "A.py").write_text("VALUE = 1\n", encoding="utf-8")
    capture = _capture(changes=[{"path": "forbidden.py", "change_kind": "modified"}])

    result = run_patch_plan_with_artifacts(
        str(repo),
        [EDIT_A],
        pre_execution_intent_capture=capture,
    )
    assert result["success"] is True
    assert not (repo / "forbidden.py").exists()
    assert result["applied_ops"] == [EDIT_A]

    receipt = load_shadow_post_run_check(result["replay_dir"])
    assert receipt["declaration_stage"] == DECLARATION_STAGE_PRE_EXECUTION_INTENT
    assert receipt["worker_declaration_source"] == DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT
    assert receipt["intent_fidelity_measurable"] is True
    assert receipt["self_report_fidelity_measurable"] is False
    assert receipt["authoritative_effect"] is False
    assert receipt["same_model_channel_is_independent_evidence"] is False
    assert (Path(result["replay_dir"]) / INTENT_ARTIFACT_NAME).is_file()


def test_durable_receipt_contains_only_bounded_identity_status_telemetry():
    capture = _capture()
    durable = build_durable_intent_receipt(
        case_identity="case-a",
        run_identity="run-a",
        capture=capture,
        shadow_receipt={
            "declaration_stage": "pre_execution_intent",
            "worker_declaration_source": "pre_execution_worker_intent",
            "intent_observed_relation": "agreed",
            "reconciliation_status": "reconciled",
        },
        authoritative_outcome="success",
    )
    rendered = json.dumps(durable, sort_keys=True)
    assert durable["contains_raw_response"] is False
    assert "raw_model_response" not in rendered
    assert "target_snippet" not in rendered
    assert "patched_snippet" not in rendered
    assert "VALUE = 2" not in rendered
    assert durable["intent_fingerprint"] == capture.intent_fingerprint
    assert durable["same_model_channel_is_independent_evidence"] is False


def test_durable_summary_is_counts_only_and_decides_nothing():
    receipts = [
        {
            "source_provenance": "pre_execution_worker_intent",
            "strict_v2_status": "valid",
            "intent_plan_agreement": "agreed",
            "intent_observed_relation": "agreed",
            "check_1_shadow_status": "reconciled",
            "transport_strategy": "strict_prompt",
            "provider_family": "google",
        }
    ]
    summary = summarize_durable_intent_receipts(receipts)
    assert summary["records"] == 1
    assert summary["counts"]["intent_plan_agreement"] == {"agreed": 1}
    assert summary["counts_decide_nothing"] is True
    assert summary["authoritative_effect"] is False


def test_proposal_queue_exports_bounded_receipt_before_temp_repo_cleanup(
    tmp_path, monkeypatch
):
    benchmark_root = tmp_path / "benchmarks"
    cases_root = tmp_path / "cases"
    case_root = cases_root / "case-2b"
    buggy_repo = case_root / "buggy_repo"
    benchmark_root.mkdir()
    buggy_repo.mkdir(parents=True)
    (buggy_repo / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    case_file = case_root / "case.json"
    case_file.write_text(
        json.dumps(
            {
                "name": "case-2b",
                "language": "python",
                "category": "test",
                "difficulty": "small",
                "prompt": "change the value",
                "validation_command": "python -m py_compile main.py",
                "expected_changed_files": ["main.py"],
                "forbidden_changed_files": [],
            }
        ),
        encoding="utf-8",
    )
    report = benchmark_root / "benchmark_report_case_2b.json"
    report.write_text(
        json.dumps(
            {
                "results": [
                    {"name": "case-2b", "case_file": str(case_file.resolve())}
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(proposal_queue, "BENCH_DIR", benchmark_root)
    monkeypatch.setattr(proposal_queue, "CASES_DIR", cases_root)
    monkeypatch.setenv("STRICT_WORKER_PATCH_ENVELOPE_EMISSION", "strict_prompt")
    monkeypatch.setenv("PRE_EXECUTION_CHANGE_INTENT", "1")
    monkeypatch.setenv("DB_ENABLED", "false")

    response = _v2(
        plan=[
            {
                "op": "replace_snippet",
                "relative_path": "main.py",
                "target_snippet": "VALUE = 1\n",
                "patched_snippet": "VALUE = 2\n",
            }
        ],
        changes=[{"path": "main.py", "change_kind": "modified"}],
    )
    calls = []

    def fake_model(*, prompt, repo_path=None, **kwargs):
        calls.append({"prompt": prompt, "repo_path": repo_path, "kwargs": kwargs})
        return response

    gemini = ModuleType("agents.gemini_client")
    gemini.run_gemini_request_2 = fake_model
    monkeypatch.setitem(sys.modules, "agents.gemini_client", gemini)

    original_temp_dir = proposal_queue.tempfile.TemporaryDirectory
    temp_locations = []

    def tracking_temp_dir(*args, **kwargs):
        directory = original_temp_dir(*args, **kwargs)
        temp_locations.append(Path(directory.name))
        return directory

    monkeypatch.setattr(proposal_queue.tempfile, "TemporaryDirectory", tracking_temp_dir)
    run_dir = tmp_path / "durable-proposals"
    run_dir.mkdir()
    result = proposal_queue._process_item(
        item={
            "case_name": "case-2b",
            "title": "intent dogfood fixture",
            "source_benchmark_report": report.name,
            "human_approved_for_proposal": True,
        },
        idx=1,
        run_dir=run_dir,
        validation_timeout_sec=30,
    )

    assert result["status"] == "proposal_validated"
    assert len(calls) == 1
    durable_path = run_dir / "01-case-2b" / INTENT_ARTIFACT_NAME
    durable = json.loads(durable_path.read_text(encoding="utf-8"))
    assert durable["strict_v2_status"] == STATUS_VALID
    assert durable["native_intent_available"] is True
    assert durable["intent_plan_agreement"] == INTENT_PLAN_AGREED
    assert durable["intent_observed_relation"] == INTENT_OBSERVED_AGREED
    assert durable["source_provenance"] == DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT
    assert durable["contains_raw_response"] is False
    assert all(not path.exists() for path in temp_locations)
