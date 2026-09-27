"""EVIDENCE.1 — the model-backed analyzer boundary.

Three questions:

1.  can a structurally valid response become a proposal?
2.  does every way of overreaching fail closed?
3.  does acquired repository content stay where the operator put it?

No live model and no network is used anywhere in this file.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from core.acquisition_request import SOURCE_CLASS_RUNTIME_IMPLEMENTATION
from core.content_acquisition import (
    MODE_REPOSITORY_READ,
    AcquiredSourcePayload,
    SourceAcquisitionReceipt,
    SourceBinding,
)
from core.evidence_analyzer import (
    EvidenceAnalysisRejected,
    EvidenceAnalyzerUnavailable,
)
from core.evidence_analyzer_adapter import (
    ADAPTER_NAME,
    ALLOWED_RESPONSE_KEYS,
    EVIDENCE_ANALYZER_SYSTEM_INSTRUCTION,
    FORBIDDEN_RESPONSE_KEYS,
    LOCALITY_CLOUD,
    LOCALITY_LOCAL,
    MAX_ANALYZER_PROMPT_BYTES,
    SOURCE_DISCLOSURE_CLOUD_APPROVED,
    SOURCE_DISCLOSURE_LOCAL_ONLY,
    EvidenceAnalyzerModelAdapter,
    ScriptedEvidenceModelClient,
    SourceDisclosureRefused,
    build_analysis_request,
    build_repair_request,
    parse_analysis_response,
    render_payload_window,
    render_proposal_response,
)
from core.evidence_promotion_gate import verify_acquired_source
from core.evidence_requirements import (
    DOMAIN_REPOSITORY,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_IMPLEMENTATION_AUTHORITY,
    TIER_REQUIRED_PRIMARY,
)
from core.evidence_verification import (
    ANALYSIS_MECHANISM_IMPLEMENTED,
    ANALYSIS_PROPOSITION_TERMS_PRESENT,
    ANALYSIS_ROLE_CONTENT_CONSISTENT,
    CONSTRAINT_LOCAL_ANALYSIS_ONLY,
    CONSTRAINT_ROLE_VERIFICATION_REQUIRED,
    GATE_ANALYZER_PROPOSAL_INVALID,
    GATE_ANALYZER_UNAVAILABLE,
    PROPOSAL_SCHEMA_VERSION,
    PROMOTION_NOT_PROMOTED,
    RELATION_SUPPORTS,
    ROLE_STATUS_VERIFIED,
    SCOPE_IMPLEMENTATION_STATE,
    SPAN_SUPPORTING,
    STATUS_ANALYSIS_INVALID,
    STATUS_VERIFIED,
    EvidenceVerificationProposal,
    EvidenceVerificationRequest,
    Proposition,
    RoleAssessment,
    bounded_payload_view,
    source_receipt_fingerprint,
    span_from_view,
)


SOURCE = b'''"""Session storage backed by SQLite."""

import sqlite3


class SessionStore:
    def save_session(self, session_id, state):
        sqlite3.connect("sessions.db").execute(
            "INSERT OR REPLACE INTO sessions (id, state) VALUES (?, ?)",
            (session_id, state),
        )
'''


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _binding(identifier: str = "core/session_store.py") -> SourceBinding:
    return SourceBinding(
        candidate_identifier=identifier,
        acquisition_mode=MODE_REPOSITORY_READ,
        task_contract_fingerprint=_digest("task-contract"),
        completion_fingerprint=_digest("completion"),
        waiter_decision_fingerprint=_digest("waiter-decision"),
        evidence_requirement_fingerprint=_digest("evidence-requirement"),
        acquisition_request_fingerprint=_digest("acquisition-request"),
        candidate_receipt_fingerprint=_digest("candidate-pool"),
        selection_fingerprint=_digest("selection"),
        authorization_fingerprint=_digest("authorization"),
        inventory_fingerprint=_digest("inventory"),
        repository_identity="repo:deepseek-harness",
    )


def _acquired() -> tuple[AcquiredSourcePayload, SourceAcquisitionReceipt]:
    binding = _binding()
    digest = hashlib.sha256(SOURCE).hexdigest()
    payload = AcquiredSourcePayload(
        candidate_identifier=binding.candidate_identifier,
        content=SOURCE,
        content_sha256=digest,
        bytes_acquired=len(SOURCE),
        source_binding=binding,
    )
    receipt = SourceAcquisitionReceipt(
        candidate_identifier=binding.candidate_identifier,
        domain=DOMAIN_REPOSITORY,
        tier=TIER_REQUIRED_PRIMARY,
        expected_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
        eligible_source_classes=(SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        target_artifact=False,
        content_sha256=digest,
        bytes_acquired=len(SOURCE),
        source_binding=binding,
    )
    return payload, receipt


def _proposition() -> Proposition:
    return Proposition(
        proposition_id="P-1",
        text="SessionStore writes session state to SQLite.",
        proposition_type="positive",
        scope=SCOPE_IMPLEMENTATION_STATE,
    )


def _request(
    receipt: SourceAcquisitionReceipt,
    *,
    constraints: tuple[str, ...] = (CONSTRAINT_ROLE_VERIFICATION_REQUIRED,),
) -> EvidenceVerificationRequest:
    return EvidenceVerificationRequest(
        proposition=_proposition(),
        requested_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
        acquisition_receipt_fingerprint=source_receipt_fingerprint(receipt),
        source_content_sha256=receipt.content_sha256,
        source_binding=receipt.source_binding,
        verification_constraints=constraints,
    )


def _honest_proposal(payload, receipt) -> EvidenceVerificationProposal:
    view = bounded_payload_view(payload, receipt)
    start, end = view.locate(b"sqlite3.connect")
    return EvidenceVerificationProposal(
        proposition_id="P-1",
        proposition_sha256=_proposition().proposition_sha256,
        source_identifier=receipt.candidate_identifier,
        source_content_sha256=payload.content_sha256,
        relation=RELATION_SUPPORTS,
        role_assessments=(
            RoleAssessment(
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                status=ROLE_STATUS_VERIFIED,
                span_indexes=(0,),
                reasons=(ANALYSIS_ROLE_CONTENT_CONSISTENT,),
            ),
        ),
        evidence_spans=(span_from_view(view, start, end, SPAN_SUPPORTING),),
        reasons=(ANALYSIS_PROPOSITION_TERMS_PRESENT, ANALYSIS_MECHANISM_IMPLEMENTED),
    )


def _local_adapter(responses: list[str]) -> EvidenceAnalyzerModelAdapter:
    return EvidenceAnalyzerModelAdapter(
        ScriptedEvidenceModelClient(responses, locality=LOCALITY_LOCAL)
    )


# ── The happy path ────────────────────────────────────────────────────────────

def test_a_well_formed_response_reaches_the_gate_and_promotes():
    payload, receipt = _acquired()
    request = _request(receipt)
    adapter = _local_adapter([render_proposal_response(_honest_proposal(payload, receipt))])

    result = verify_acquired_source(request, payload, receipt, adapter, model_called=True)

    assert adapter.call_count == 1
    assert result.status == STATUS_VERIFIED
    assert result.analyzer_name == ADAPTER_NAME
    assert result.model_called is True
    assert json.loads(
        json.dumps(result.as_dict())
    )["guardrails"]["provider_selected_by_evidence_layer"] is False


def test_a_fenced_response_is_still_parsed():
    payload, receipt = _acquired()
    body = render_proposal_response(_honest_proposal(payload, receipt))
    parsed = parse_analysis_response(
        f"Here is my analysis.\n```json\n{body}\n```\nThanks."
    )
    assert parsed.relation == RELATION_SUPPORTS


def test_enum_order_is_normalized_but_membership_is_not():
    payload, receipt = _acquired()
    body = json.loads(render_proposal_response(_honest_proposal(payload, receipt)))
    body["reasons"] = [ANALYSIS_MECHANISM_IMPLEMENTED, ANALYSIS_PROPOSITION_TERMS_PRESENT]

    parsed = parse_analysis_response(json.dumps(body))

    assert parsed.reasons == (
        ANALYSIS_PROPOSITION_TERMS_PRESENT,
        ANALYSIS_MECHANISM_IMPLEMENTED,
    )


# ── The prompt ────────────────────────────────────────────────────────────────

def test_the_request_carries_one_proposition_and_one_source_and_nothing_else():
    payload, receipt = _acquired()
    request = _request(receipt)
    view = bounded_payload_view(payload, receipt)

    rendered = build_analysis_request(request, view)

    assert "SessionStore writes session state to SQLite." in rendered
    assert receipt.candidate_identifier in rendered
    assert payload.content_sha256 in rendered
    for absent in ("project map", "repository index", "graph", "benchmark", "lesson"):
        assert absent not in rendered.lower()


def test_the_rendered_window_labels_exact_byte_ranges():
    payload, receipt = _acquired()
    view = bounded_payload_view(payload, receipt)

    window, truncated = render_payload_window(view)

    assert truncated is False
    first = window.splitlines()[0]
    start, end = first[1 : first.index("]")].split(",")
    assert view.slice(int(start), int(end)).decode("utf-8").rstrip("\n") == first[
        first.index("] ") + 2 :
    ]


def test_an_oversized_payload_window_is_truncated_and_says_so():
    binding = _binding()
    content = b"# padding\n" * (MAX_ANALYZER_PROMPT_BYTES // 5)
    digest = hashlib.sha256(content).hexdigest()
    payload = AcquiredSourcePayload(
        candidate_identifier=binding.candidate_identifier,
        content=content,
        content_sha256=digest,
        bytes_acquired=len(content),
        source_binding=binding,
    )
    receipt = SourceAcquisitionReceipt(
        candidate_identifier=binding.candidate_identifier,
        domain=DOMAIN_REPOSITORY,
        tier=TIER_REQUIRED_PRIMARY,
        expected_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
        eligible_source_classes=(SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        target_artifact=False,
        content_sha256=digest,
        bytes_acquired=len(content),
        source_binding=binding,
    )
    view = bounded_payload_view(payload, receipt)

    _, truncated = render_payload_window(view)
    rendered = build_analysis_request(_request(receipt), view)

    assert truncated is True
    assert "rendered_window_truncated: true" in rendered


def test_the_system_instruction_forbids_the_failure_modes_it_needs_to():
    text = EVIDENCE_ANALYZER_SYSTEM_INSTRUCTION.lower()
    assert "omission is not counter-evidence" in text
    assert "absence of something in one file never establishes" in text
    assert "confidence" in text
    assert "web search" in text


# ── Adversarial responses ─────────────────────────────────────────────────────

def _tampered(**changes: object) -> str:
    payload, receipt = _acquired()
    body = json.loads(render_proposal_response(_honest_proposal(payload, receipt)))
    body.update(changes)
    return json.dumps(body)


def test_1_an_analyzer_cannot_change_the_proposition_text():
    payload, receipt = _acquired()
    other = Proposition(
        proposition_id="P-1",
        text="SessionStore writes session state to Postgres.",
        proposition_type="positive",
        scope=SCOPE_IMPLEMENTATION_STATE,
    )
    adapter = _local_adapter(
        [_tampered(proposition_sha256=other.proposition_sha256)]
    )

    result = verify_acquired_source(_request(receipt), payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID
    assert GATE_ANALYZER_PROPOSAL_INVALID in result.reasons


def test_2_an_analyzer_cannot_rename_the_proposition():
    payload, receipt = _acquired()
    adapter = _local_adapter([_tampered(proposition_id="P-INVENTED")])

    result = verify_acquired_source(_request(receipt), payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID


def test_3_an_analyzer_cannot_invent_an_expected_role():
    payload, receipt = _acquired()
    body = json.loads(_tampered())
    body["role_assessments"].append(
        {
            "role": ROLE_ARCHITECTURE_DESCRIPTION,
            "status": ROLE_STATUS_VERIFIED,
            "span_indexes": [],
            "reasons": [ANALYSIS_ROLE_CONTENT_CONSISTENT],
        }
    )
    adapter = _local_adapter([json.dumps(body)])

    result = verify_acquired_source(_request(receipt), payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID


def test_4_an_analyzer_cannot_name_a_source_that_was_not_acquired():
    payload, receipt = _acquired()
    adapter = _local_adapter([_tampered(source_identifier="core/plugin_kernel.py")])

    result = verify_acquired_source(_request(receipt), payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID


@pytest.mark.parametrize(
    "key, value",
    [
        ("confidence", 0.99),
        ("probability", 0.87),
        ("support_score", 83),
        ("likelihood", "high"),
    ],
)
def test_5_a_numeric_confidence_fails_the_response_closed(key, value):
    with pytest.raises(EvidenceAnalysisRejected, match=key):
        parse_analysis_response(_tampered(**{key: value}))


@pytest.mark.parametrize(
    "key, value",
    [
        ("read_more_files", ["core/router.py"]),
        ("files_to_read", ["core/router.py"]),
        ("search_repository", "session persistence"),
        ("search_web", "sqlite session store"),
        ("tool_calls", [{"name": "read_file"}]),
        ("acquire_more", True),
    ],
)
def test_6_and_7_asking_for_more_material_fails_the_response_closed(key, value):
    with pytest.raises(EvidenceAnalysisRejected, match=key):
        parse_analysis_response(_tampered(**{key: value}))


@pytest.mark.parametrize(
    "key, value",
    [
        ("verified_evidence", True),
        ("evidence_promoted", True),
        ("claim_verified", True),
        ("claim_true", True),
        ("verification_status", "verified"),
        ("promotion_status", "promoted"),
        ("authority", {"repository_write_authority": True}),
        ("write_authority", True),
        ("routing", "commander"),
        ("execution", "run"),
        ("provider", "gemini"),
        ("model", "gemma-4-31b-it"),
        ("human_approval_required", False),
        ("guardrails", {"network_called": False}),
    ],
)
def test_8_claiming_authority_fails_the_response_closed(key, value):
    with pytest.raises(EvidenceAnalysisRejected, match=key):
        parse_analysis_response(_tampered(**{key: value}))


@pytest.mark.parametrize("key", ["reasoning", "thinking", "chain_of_thought"])
def test_hidden_reasoning_is_refused_rather_than_stored(key):
    with pytest.raises(EvidenceAnalysisRejected, match=key):
        parse_analysis_response(_tampered(**{key: "first I considered..."}))


def test_9_an_invalid_relation_fails_the_response_closed():
    with pytest.raises(EvidenceAnalysisRejected, match="relation"):
        parse_analysis_response(_tampered(relation="probably_supports"))


def test_10_a_nonexistent_span_is_refused_by_the_gate():
    payload, receipt = _acquired()
    body = json.loads(_tampered())
    body["evidence_spans"] = [
        {
            "start_byte": 0,
            "end_byte": 32,
            "span_sha256": hashlib.sha256(b"class PluginKernel:").hexdigest(),
            "purpose": SPAN_SUPPORTING,
            "source_content_sha256": payload.content_sha256,
        }
    ]
    adapter = _local_adapter([json.dumps(body)])

    result = verify_acquired_source(_request(receipt), payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID
    assert result.promotion_status == PROMOTION_NOT_PROMOTED


def test_11_a_free_prose_answer_is_refused_rather_than_interpreted():
    with pytest.raises(EvidenceAnalysisRejected, match="no JSON object"):
        parse_analysis_response(
            "Yes, the harness clearly uses SQLite for session persistence, and the "
            "architecture is well factored."
        )


def test_12_an_unknown_key_is_refused_rather_than_dropped():
    with pytest.raises(EvidenceAnalysisRejected, match="unsupported keys"):
        parse_analysis_response(_tampered(architecture_summary="looks fine"))


def test_an_unsupported_schema_version_is_refused():
    with pytest.raises(EvidenceAnalysisRejected, match="schema"):
        parse_analysis_response(_tampered(schema_version="evidence_1_analysis_v2"))


def test_an_empty_response_is_unavailability_not_a_verdict():
    payload, receipt = _acquired()
    adapter = _local_adapter(["   "])

    result = verify_acquired_source(_request(receipt), payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID
    assert GATE_ANALYZER_UNAVAILABLE in result.reasons


def test_a_client_that_raises_becomes_unavailability_not_a_verdict():
    class _Broken:
        model_id = "broken"
        locality = LOCALITY_LOCAL

        def complete(self, system_instruction: str, user_message: str) -> str:
            raise RuntimeError("connection refused")

    payload, receipt = _acquired()
    adapter = EvidenceAnalyzerModelAdapter(_Broken())

    result = verify_acquired_source(_request(receipt), payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID
    assert GATE_ANALYZER_UNAVAILABLE in result.reasons


def test_forbidden_and_allowed_keys_do_not_overlap():
    assert not set(ALLOWED_RESPONSE_KEYS) & set(FORBIDDEN_RESPONSE_KEYS)


# ── Disclosure and provider boundaries ────────────────────────────────────────

def test_a_cloud_client_is_refused_without_explicit_approval():
    with pytest.raises(SourceDisclosureRefused, match="cloud_disclosure_approved"):
        EvidenceAnalyzerModelAdapter(
            ScriptedEvidenceModelClient([], locality=LOCALITY_CLOUD)
        )


def test_a_cloud_client_is_allowed_only_with_explicit_approval():
    adapter = EvidenceAnalyzerModelAdapter(
        ScriptedEvidenceModelClient([], locality=LOCALITY_CLOUD),
        source_disclosure=SOURCE_DISCLOSURE_CLOUD_APPROVED,
    )
    assert adapter.locality == LOCALITY_CLOUD
    assert adapter.source_disclosure == SOURCE_DISCLOSURE_CLOUD_APPROVED


def test_a_client_that_declares_no_locality_is_treated_as_cloud():
    class _Undeclared:
        model_id = "mystery"

        def complete(self, system_instruction: str, user_message: str) -> str:
            return "{}"

    with pytest.raises(SourceDisclosureRefused, match="declare locality"):
        EvidenceAnalyzerModelAdapter(_Undeclared())


def test_local_analysis_only_refuses_an_approved_cloud_analyzer():
    payload, receipt = _acquired()
    adapter = EvidenceAnalyzerModelAdapter(
        ScriptedEvidenceModelClient(
            [render_proposal_response(_honest_proposal(payload, receipt))],
            locality=LOCALITY_CLOUD,
        ),
        source_disclosure=SOURCE_DISCLOSURE_CLOUD_APPROVED,
    )
    request = _request(
        receipt,
        constraints=(
            CONSTRAINT_ROLE_VERIFICATION_REQUIRED,
            CONSTRAINT_LOCAL_ANALYSIS_ONLY,
        ),
    )

    result = verify_acquired_source(request, payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID
    assert adapter.call_count == 0


def test_the_default_disclosure_policy_is_local_only():
    adapter = _local_adapter([])
    assert adapter.source_disclosure == SOURCE_DISCLOSURE_LOCAL_ONLY


def test_one_verification_uses_one_configured_model_with_no_escalation():
    payload, receipt = _acquired()
    client = ScriptedEvidenceModelClient(["not json at all"], locality=LOCALITY_LOCAL)
    adapter = EvidenceAnalyzerModelAdapter(client)

    result = verify_acquired_source(_request(receipt), payload, receipt, adapter)

    assert result.status == STATUS_ANALYSIS_INVALID
    assert adapter.call_count == 1
    assert len(client.calls) == 1


def test_evidence_1_ships_no_live_transport():
    import inspect

    from core import evidence_analyzer_adapter

    source = inspect.getsource(evidence_analyzer_adapter)
    for stack in ("requests", "httpx", "urllib", "socket", "openai", "anthropic"):
        assert f"import {stack}" not in source, stack


# ── Bounded repair ────────────────────────────────────────────────────────────

def test_a_repair_brief_states_the_defect_and_forbids_changing_the_finding():
    payload, receipt = _acquired()
    view = bounded_payload_view(payload, receipt)

    brief = build_repair_request(
        _request(receipt),
        view,
        ("a 'supports' relation must cite at least one 'supporting' span",),
    )

    assert "structural reasons only" in brief
    assert "Do not change your findings" in brief
    assert "must cite at least one" in brief
    assert "think harder" not in brief.lower()


def test_the_adapter_remembers_its_last_proposal_for_a_targeted_repair():
    payload, receipt = _acquired()
    adapter = _local_adapter([render_proposal_response(_honest_proposal(payload, receipt))])

    assert adapter.last_proposal is None
    adapter.analyze(_request(receipt), bounded_payload_view(payload, receipt))
    assert adapter.last_proposal is not None
    assert adapter.last_proposal.relation == RELATION_SUPPORTS


def test_the_scripted_client_runs_out_rather_than_inventing_a_response():
    client = ScriptedEvidenceModelClient([], locality=LOCALITY_LOCAL)
    with pytest.raises(EvidenceAnalyzerUnavailable):
        client.complete("system", "user")


def test_a_rendered_proposal_round_trips_through_the_parser():
    payload, receipt = _acquired()
    original = _honest_proposal(payload, receipt)

    parsed = parse_analysis_response(render_proposal_response(original))

    assert parsed == original
    assert parsed.schema_version == PROPOSAL_SCHEMA_VERSION
