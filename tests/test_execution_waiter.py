"""WAITER.1 — deterministic capability-based execution routing tests.

Three things are proved here.

The **routing matrix**: an explanation and a pasted-snippet comparison stay in
Chat, a bounded repository edit goes to Instant Run, a broad investigation and a
comparative architecture analysis go to Commander, and only an explicit,
literally-backed lifecycle declaration reaches Project Evolution.

The **shape sensitivity**: the same words route differently when the structured
evidence requirements differ, and different words route the same when they do
not.  The regression that motivated the phase — the DeepSeek Harness dogfood
falling into Instant Run — is pinned here, together with its mirror image: the
identical prompt over supplied context stays in Chat.

The **boundary**: no route names a model or a provider, no route grants
authority, no route carries a plan, and a handoff INPUT did not verify produces
no route at all.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from core.capability_requirements import (
    CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE,
    CAPABILITY_CODE_CHANGE,
    CAPABILITY_COMPARISON,
    CAPABILITY_CONVERSATIONAL_RESPONSE,
    CAPABILITY_CROSS_SOURCE_SYNTHESIS,
    CAPABILITY_DIRECT_CONTEXT_ANALYSIS,
    CAPABILITY_EXTERNAL_INFORMATION,
    CAPABILITY_MULTI_STAGE_COORDINATION,
    CAPABILITY_NAMES,
    CAPABILITY_PERSISTENT_PROJECT_CONTEXT,
    CAPABILITY_REPOSITORY_READ,
    CAPABILITY_VALIDATION,
    CapabilityRequirement,
    derive_capability_requirements,
)
from core.execution_waiter import (
    DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NEGATED,
    DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED,
    DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED,
    DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED,
    DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED,
    ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY,
    ROUTE_CHAT_DIRECT_CONTEXT_ONLY,
    ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY,
    ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED,
    ROUTE_COMMANDER_BROAD_REPOSITORY_RECON,
    ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS,
    ROUTE_COMMANDER_MULTI_STAGE,
    ROUTE_INSTANT_BOUNDED_REPO_OPERATION,
    ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON,
    ROUTE_REASONS,
    ROUTE_REASON_DESCRIPTIONS,
    STATUS_NOT_HANDOFF_READY,
    STATUS_ROUTED,
    WAITER_DISQUALIFIERS,
    WORKFLOW_CHAT,
    WORKFLOW_COMMANDER,
    WORKFLOW_INSTANT_RUN,
    WORKFLOW_PROJECT_EVOLUTION,
    WORKFLOW_TARGETS,
    WaiterDecision,
    canonical_waiter_fingerprint,
    render_waiter_decision_json,
    route_execution_workflow,
)
from core.input_completion import complete_intake, complete_intake_from_semantic_outcome
from core.input_understanding import understand_request
from core.intake_completion import (
    STATE_ASK_CLARIFICATION,
    STATE_GOAL_BRIEF_ASSIST,
    STATE_READY,
    STATE_SEMANTIC_SYSTEM_FAILURE,
)
from core.semantic_waiter_adapter import (
    ScriptedSemanticModelClient,
    SemanticWaiterModelAdapter,
)
from core.semantic_waiter_runner import understand_request_semantically
from core.task_contract import PRESERVATION_FAILED, PreservationReport
from core.task_shape import (
    ANALYSIS_COMPARATIVE,
    DECLARATION_SOURCE_EXPLICIT_INPUT_EVIDENCE,
    DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
    PROJECT_EVOLUTION_DISQUALIFIERS,
    TRUSTED_DECLARATION_SOURCES,
    UNTRUSTED_DECLARATION_SOURCES,
    ANALYSIS_INVESTIGATIVE,
    ANALYSIS_SIMPLE,
    CHANGE_BOUNDED,
    CHANGE_NONE,
    EVIDENCE_BOUNDED_REPOSITORY,
    EVIDENCE_BROAD_REPOSITORY,
    EVIDENCE_DIRECT_CONTEXT,
    EVIDENCE_EXTERNAL_INFORMATION,
    EVIDENCE_MIXED_SOURCES,
    EVIDENCE_NONE,
    FAMILY_COMPARATIVE_ANALYSIS,
    FAMILY_EXPLANATORY,
    FAMILY_IMPLEMENTATION,
    FAMILY_PROJECT_EVOLUTION,
    HORIZON_IMMEDIATE,
    HORIZON_LONG_RUNNING,
    INTERACTION_MULTI_STAGE,
    INTERACTION_SINGLE_STAGE,
    ProjectEvolutionRequest,
    check_project_evolution_request,
    derive_task_shape,
)
from core.waiter_receipt import (
    GATE_CONTRACT_ROUTING_NOT_ALLOWED,
    GATE_PRESERVATION_FAILED,
    GATE_SEMANTIC_RECEIPT_MISSING,
    check_handoff_eligibility,
    waiter_authority,
)


# ══ Fixtures ══════════════════════════════════════════════════════════════════

#: The request that motivated the phase.  It was misclassified into Instant Run
#: because nothing between "what did they say" and "which mode" ever asked what
#: the order would require.
DOGFOOD_PROMPT = """Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:

- Equivalent
- DeepSeek stronger
- C.A.T.T.U.S stronger
- Orthogonal
- Not worth adopting
"""

BROAD_REPOSITORY = {
    "multi_stage": True,
    "repository_inspection_required": True,
    "local_repository_required": True,
}

BOUNDED_REPOSITORY = {
    "repository_inspection_required": True,
    "local_repository_required": True,
}


class _DeadSemanticClient:
    """A configured model that cannot be reached."""

    model_id = "unreachable-model"

    def complete(self, system_instruction, user_message):
        raise TimeoutError("the semantic model did not answer")


def _semantic(prompt: str, *payloads: dict):
    """Run one request through INPUT.1 and INPUT.2 with a scripted model."""
    adapter = SemanticWaiterModelAdapter(
        ScriptedSemanticModelClient([json.dumps(item) for item in payloads])
    )
    return understand_request_semantically(prompt, adapter=adapter)


def _handoff(prompt: str, payload: dict):
    """A handoff-ready ``(contract, decision)`` pair from INPUT.1 through 3."""
    outcome = _semantic(prompt, payload)
    completion = complete_intake_from_semantic_outcome(outcome)
    assert completion.state == STATE_READY, completion.decision.reasons
    assert completion.ready_for_future_handoff is True, (
        completion.decision.handoff_blockers
    )
    return outcome.contract, completion.decision


def _request_fingerprint(prompt: str) -> str:
    """The stable INPUT.1 identifier a declaration must be bound to."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _route(prompt: str, payload: dict, **kwargs) -> WaiterDecision:
    contract, decision = _handoff(prompt, payload)
    return route_execution_workflow(contract, decision, **kwargs)


def _dogfood_interpretation(execution: dict) -> dict:
    """The faithful interpretation of the dogfood request.

    The rubric is user-supplied, ordered, and carried verbatim; the comparison
    the user literally wrote survives as a relationship.  Only ``execution``
    varies across the tests that use it.
    """
    return {
        "task": {"type": "comparative_analysis", "provenance": "inferred"},
        "subjects": [
            {"value": "DeepSeek Harness", "provenance": "explicit"},
            {"value": "C.A.T.T.U.S", "provenance": "explicit"},
        ],
        "relationships": [
            {
                "type": "comparison",
                "subjects": ["DeepSeek Harness", "C.A.T.T.U.S"],
                "provenance": "explicit",
            }
        ],
        "user_supplied_framework": {
            "type": "framework",
            "values": [
                "Equivalent",
                "DeepSeek stronger",
                "C.A.T.T.U.S stronger",
                "Orthogonal",
                "Not worth adopting",
            ],
            "provenance": "explicit",
            "ordered": True,
        },
        "constraints": [
            {
                "kind": "framework_reference",
                "text": "Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:",
                "provenance": "explicit",
            }
        ],
        "execution_requirements": execution,
    }


def _without_authority(value):
    """Strip the authority blocks, which name powers in order to deny them."""
    if isinstance(value, dict):
        return {
            key: _without_authority(item)
            for key, item in value.items()
            if key not in ("authority", "guardrails")
        }
    if isinstance(value, list):
        return [_without_authority(item) for item in value]
    return value


# ══ A — a simple explanation is answered in place ═════════════════════════════

def test_case_a_simple_explanation_routes_to_chat():
    decision = _route(
        "Explain the Bellman equation.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )

    assert decision.status == STATUS_ROUTED
    assert decision.recommended_workflow == WORKFLOW_CHAT
    assert decision.reasons == (ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED,)
    assert decision.task_shape.task_family == FAMILY_EXPLANATORY
    assert decision.task_shape.evidence_scope == EVIDENCE_NONE
    assert decision.task_shape.horizon == HORIZON_IMMEDIATE


def test_case_a_requires_no_repository_and_no_execution_capability():
    decision = _route(
        "Explain the Bellman equation.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )

    assert decision.requires(CAPABILITY_REPOSITORY_READ) is False
    assert decision.requires(CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE) is False
    assert decision.requires(CAPABILITY_CODE_CHANGE) is False
    assert decision.requires(CAPABILITY_VALIDATION) is False
    assert decision.requires(CAPABILITY_MULTI_STAGE_COORDINATION) is False
    assert decision.capability_requirements.any_execution_capability_required is False
    assert decision.capability_requirements.required_names() == (
        CAPABILITY_CONVERSATIONAL_RESPONSE,
    )


# ══ B — a pasted snippet comparison stays in chat ═════════════════════════════

_PASTED_COMPARISON = (
    "Compare these two pasted functions for readability:\n\n"
    "`def a(x): return x + 1`\n\n"
    "`def b(x): return sum([x, 1])`\n"
)

_PASTED_COMPARISON_INTERPRETATION = {
    "task": {"type": "comparative_analysis", "provenance": "inferred"},
    "subjects": [
        {"value": "def a(x): return x + 1", "provenance": "explicit"},
        {"value": "def b(x): return sum([x, 1])", "provenance": "explicit"},
    ],
    "relationships": [
        {
            "type": "comparison",
            "subjects": ["def a(x): return x + 1", "def b(x): return sum([x, 1])"],
            "provenance": "inferred",
            "confidence": 0.9,
        }
    ],
    "execution_requirements": {},
}


def test_case_b_pasted_snippet_comparison_routes_to_chat():
    decision = _route(_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION)

    assert decision.recommended_workflow == WORKFLOW_CHAT
    assert decision.reasons == (ROUTE_CHAT_DIRECT_CONTEXT_ONLY,)
    assert decision.requires(CAPABILITY_COMPARISON) is True
    assert decision.requires(CAPABILITY_DIRECT_CONTEXT_ANALYSIS) is True
    assert decision.task_shape.evidence_scope == EVIDENCE_DIRECT_CONTEXT


def test_case_b_comparison_alone_never_reaches_commander():
    decision = _route(_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION)

    assert decision.task_shape.analysis_shape == ANALYSIS_COMPARATIVE
    assert decision.recommended_workflow != WORKFLOW_COMMANDER
    assert decision.requires(CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE) is False
    assert decision.requires(CAPABILITY_REPOSITORY_READ) is False


# ══ C — a bounded edit is a bounded operation ═════════════════════════════════

def test_case_c_typo_fix_routes_to_instant_run():
    decision = _route(
        "Fix the typo 'teh' to 'the' in README.md.",
        {
            "task": {"type": "implementation", "provenance": "inferred"},
            "subjects": [{"value": "README.md", "provenance": "explicit"}],
            "execution_requirements": BOUNDED_REPOSITORY,
        },
    )

    assert decision.recommended_workflow == WORKFLOW_INSTANT_RUN
    assert decision.reasons == (ROUTE_INSTANT_BOUNDED_REPO_OPERATION,)
    assert decision.task_shape.evidence_scope == EVIDENCE_BOUNDED_REPOSITORY
    assert decision.task_shape.change_shape == CHANGE_BOUNDED
    assert decision.task_shape.interaction_shape == INTERACTION_SINGLE_STAGE
    assert decision.requires(CAPABILITY_REPOSITORY_READ) is True
    assert decision.requires(CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE) is False
    assert decision.requires(CAPABILITY_VALIDATION) is True


# ══ D — a bounded implementation is a bounded operation ═══════════════════════

def test_case_d_bounded_implementation_routes_to_instant_run():
    decision = _route(
        "Implement a slugify helper in core/text_utils.py.",
        {
            "task": {"type": "implementation", "provenance": "inferred"},
            "subjects": [{"value": "core/text_utils.py", "provenance": "explicit"}],
            "execution_requirements": BOUNDED_REPOSITORY,
        },
    )

    assert decision.recommended_workflow == WORKFLOW_INSTANT_RUN
    assert decision.task_shape.task_family == FAMILY_IMPLEMENTATION
    assert decision.task_shape.evidence_scope == EVIDENCE_BOUNDED_REPOSITORY
    assert decision.requires(CAPABILITY_MULTI_STAGE_COORDINATION) is False


# ══ E — a broad investigation needs orchestration ═════════════════════════════

_BROAD_DEBUGGING = (
    "Investigate why project indexing takes more than an hour, and determine the "
    "causes across core/indexer.py and the rest of the indexing pipeline."
)


def test_case_e_broad_repository_debugging_routes_to_commander():
    decision = _route(
        _BROAD_DEBUGGING,
        {
            "task": {"type": "debugging", "provenance": "inferred"},
            "subjects": [{"value": "core/indexer.py", "provenance": "explicit"}],
            "execution_requirements": BROAD_REPOSITORY,
        },
    )

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert ROUTE_COMMANDER_MULTI_STAGE in decision.reasons
    assert ROUTE_COMMANDER_BROAD_REPOSITORY_RECON in decision.reasons
    assert decision.task_shape.evidence_scope == EVIDENCE_BROAD_REPOSITORY
    assert decision.task_shape.analysis_shape == ANALYSIS_INVESTIGATIVE


# ══ F — the DeepSeek Harness dogfood regression ═══════════════════════════════

def _dogfood_decision() -> WaiterDecision:
    return _route(DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY))


def test_case_f_dogfood_routes_to_commander():
    decision = _dogfood_decision()

    assert decision.status == STATUS_ROUTED
    assert decision.recommended_workflow == WORKFLOW_COMMANDER


def test_case_f_dogfood_must_not_route_to_instant_run():
    """The original failure, pinned as a first-class regression."""
    decision = _dogfood_decision()

    assert decision.recommended_workflow != WORKFLOW_INSTANT_RUN
    assert ROUTE_INSTANT_BOUNDED_REPO_OPERATION not in decision.reasons


def test_case_f_dogfood_task_shape_is_comparative_repository_analysis():
    shape = _dogfood_decision().task_shape

    assert shape.task_family == FAMILY_COMPARATIVE_ANALYSIS
    assert shape.analysis_shape == ANALYSIS_COMPARATIVE
    assert shape.evidence_scope == EVIDENCE_BROAD_REPOSITORY
    assert shape.broad_repository_scope is True
    assert shape.comparison_present is True
    assert shape.interaction_shape == INTERACTION_MULTI_STAGE


def test_case_f_dogfood_capabilities_name_comparison_and_repository_evidence():
    decision = _dogfood_decision()

    assert decision.requires(CAPABILITY_COMPARISON) is True
    assert decision.requires(CAPABILITY_REPOSITORY_READ) is True
    assert decision.requires(CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE) is True
    assert decision.requires(CAPABILITY_MULTI_STAGE_COORDINATION) is True


def test_case_f_dogfood_capabilities_are_requirements_not_permissions():
    decision = _dogfood_decision()
    authority = decision.as_dict()["authority"]

    assert decision.requires(CAPABILITY_REPOSITORY_READ) is True
    assert authority["repository_read_authority"] is False
    assert authority["routing_execution_authority"] is False
    assert authority["execution_authority"] is False


def test_case_f_dogfood_repository_requirement_cites_structured_facts():
    """Provenance may cite an INPUT field; it may not invent a user quotation."""
    decision = _dogfood_decision()
    reasons = decision.capability_requirements.reasons_for(CAPABILITY_REPOSITORY_READ)

    assert (
        "task_contract.execution_requirements.repository_inspection_required=true" in reasons
    )
    joined = " ".join(reasons).lower()
    assert "user" not in joined
    assert "requested" not in joined


def test_case_f_dogfood_produces_no_plan_and_no_read_set():
    rendered = json.dumps(_without_authority(_dogfood_decision().as_dict())).lower()

    for forbidden in ("stage 1", "read_set", "file_list", "steps", "plan_steps", "subtasks"):
        assert forbidden not in rendered, forbidden


# ══ G — the same comparison over supplied context stays in chat ═══════════════

def test_case_g_direct_context_comparison_routes_to_chat():
    """Identical prompt, identical rubric — only the evidence needs differ."""
    decision = _route(DOGFOOD_PROMPT, _dogfood_interpretation({}))

    assert decision.recommended_workflow == WORKFLOW_CHAT
    assert decision.reasons == (ROUTE_CHAT_DIRECT_CONTEXT_ONLY,)
    assert decision.requires(CAPABILITY_COMPARISON) is True
    assert decision.requires(CAPABILITY_REPOSITORY_READ) is False


def test_comparison_is_not_the_thing_that_chooses_commander():
    """The two dogfood shapes agree on everything except where evidence lives."""
    broad = _dogfood_decision()
    direct = _route(DOGFOOD_PROMPT, _dogfood_interpretation({}))

    assert broad.task_shape.task_family == direct.task_shape.task_family
    assert broad.task_shape.analysis_shape == direct.task_shape.analysis_shape
    assert broad.requires(CAPABILITY_COMPARISON) is True
    assert direct.requires(CAPABILITY_COMPARISON) is True

    assert broad.task_shape.evidence_scope != direct.task_shape.evidence_scope
    assert broad.recommended_workflow == WORKFLOW_COMMANDER
    assert direct.recommended_workflow == WORKFLOW_CHAT


# ══ H — a broad migration is Commander, not Project Evolution ═════════════════

_BROAD_MIGRATION = (
    "Migrate the storage backend from SQLite to PostgreSQL across database/schema.py, "
    "storage/backend.py and graph/store.py, and validate every affected path."
)

_BROAD_MIGRATION_INTERPRETATION = {
    "task": {"type": "implementation", "provenance": "inferred"},
    "subjects": [
        {"value": "database/schema.py", "provenance": "explicit"},
        {"value": "storage/backend.py", "provenance": "explicit"},
        {"value": "graph/store.py", "provenance": "explicit"},
    ],
    "execution_requirements": BROAD_REPOSITORY,
}


def test_case_h_broad_migration_routes_to_commander():
    decision = _route(_BROAD_MIGRATION, _BROAD_MIGRATION_INTERPRETATION)

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert ROUTE_COMMANDER_MULTI_STAGE in decision.reasons


def test_case_h_breadth_alone_does_not_reach_project_evolution():
    decision = _route(_BROAD_MIGRATION, _BROAD_MIGRATION_INTERPRETATION)

    assert decision.recommended_workflow != WORKFLOW_PROJECT_EVOLUTION
    assert decision.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT) is False
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED in decision.disqualifiers
    )


# ══ I — explicit project evolution ════════════════════════════════════════════

_EVOLUTION_PROMPT = (
    "Continue evolving this project through the roadmap phases, starting from the "
    "current registry in docs/roadmap/phase_registry.json."
)

_EVOLUTION_INTERPRETATION = {
    "task": {"type": "planning", "provenance": "inferred"},
    "subjects": [
        {"value": "docs/roadmap/phase_registry.json", "provenance": "explicit"}
    ],
    "execution_requirements": BROAD_REPOSITORY,
}

_EVOLUTION_DECLARATION = ProjectEvolutionRequest(
    evidence_text="Continue evolving this project through the roadmap phases",
    declared_by=DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
    source_raw_request_sha256=_request_fingerprint(_EVOLUTION_PROMPT),
)


def test_case_i_explicit_project_evolution_routes_to_project_evolution():
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=_EVOLUTION_DECLARATION,
    )

    assert decision.recommended_workflow == WORKFLOW_PROJECT_EVOLUTION
    assert decision.reasons == (ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON,)
    assert decision.task_shape.task_family == FAMILY_PROJECT_EVOLUTION
    assert decision.task_shape.horizon == HORIZON_LONG_RUNNING
    assert decision.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT) is True


def test_case_i_the_same_order_without_the_declaration_is_commander():
    decision = _route(_EVOLUTION_PROMPT, _EVOLUTION_INTERPRETATION)

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert decision.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT) is False


def test_case_i_a_declaration_the_user_never_typed_is_refused():
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=ProjectEvolutionRequest(
            evidence_text="run the ongoing project evolution process forever",
            declared_by=DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
            source_raw_request_sha256=_request_fingerprint(_EVOLUTION_PROMPT),
        ),
    )

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED
        in decision.disqualifiers
    )


def test_case_i_a_project_evolution_route_grants_no_project_evolution_authority():
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=_EVOLUTION_DECLARATION,
    )
    authority = decision.as_dict()["authority"]

    assert decision.recommended_workflow == WORKFLOW_PROJECT_EVOLUTION
    assert authority["project_evolution_authority"] is False
    assert authority["execution_authority"] is False
    assert authority["human_approval_required"] is True


def test_a_project_evolution_declaration_may_not_be_inferred():
    with pytest.raises(ValueError):
        ProjectEvolutionRequest(evidence_text="keep evolving it", provenance="inferred")


# ══ J — a large refactor is still Commander ═══════════════════════════════════

def test_case_j_large_architecture_refactor_is_commander_not_project_evolution():
    decision = _route(
        "Refactor the whole context-selection architecture across core/context_selection.py "
        "and core/context_search_runtime.py, keeping every public contract stable.",
        {
            "task": {"type": "implementation", "provenance": "inferred"},
            "subjects": [
                {"value": "core/context_selection.py", "provenance": "explicit"},
                {"value": "core/context_search_runtime.py", "provenance": "explicit"},
            ],
            "execution_requirements": BROAD_REPOSITORY,
        },
    )

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert decision.task_shape.task_family == FAMILY_IMPLEMENTATION
    assert decision.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT) is False


# ══ K–O — a handoff INPUT did not verify produces no route ════════════════════

def test_case_k_a_ready_preview_over_a_failed_preservation_gate_is_not_routed():
    contract, decision = _handoff(
        "Explain the Bellman equation.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )
    broken = dataclasses.replace(
        contract,
        preservation=PreservationReport(
            status=PRESERVATION_FAILED,
            missing_items=(),
            reasons=("an explicit subject was dropped",),
        ),
        routing_allowed=False,
    )

    routed = route_execution_workflow(broken, decision)

    assert routed.status == STATUS_NOT_HANDOFF_READY
    assert routed.recommended_workflow is None
    assert routed.task_shape is None
    assert routed.capability_requirements is None
    assert GATE_PRESERVATION_FAILED in routed.disqualifiers
    assert GATE_CONTRACT_ROUTING_NOT_ALLOWED in routed.disqualifiers


def test_case_l_a_missing_semantic_receipt_is_not_routed():
    contract = understand_request("Explain the Bellman equation.")
    outcome = complete_intake(contract)

    decision = route_execution_workflow(contract, outcome.decision)

    assert outcome.state == STATE_READY
    assert decision.status == STATUS_NOT_HANDOFF_READY
    assert decision.disqualifiers == (GATE_SEMANTIC_RECEIPT_MISSING,)
    assert decision.reasons == (ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY,)


def test_case_m_ask_clarification_is_not_routed():
    outcome = _semantic(
        "Replace it with the other one.",
        {
            "task": {"type": "unknown", "provenance": "inferred"},
            "ambiguities": ["'it' has no resolvable referent in the supplied context"],
        },
    )
    completion = complete_intake_from_semantic_outcome(outcome)

    decision = route_execution_workflow(outcome.contract, completion.decision)

    assert completion.state == STATE_ASK_CLARIFICATION
    assert decision.status == STATUS_NOT_HANDOFF_READY
    assert decision.recommended_workflow is None


def test_case_n_goal_brief_assist_is_not_routed():
    outcome = _semantic(
        "Migrate the storage backend to PostgreSQL.",
        {
            "task": {"type": "implementation", "provenance": "inferred"},
            "execution_requirements": BROAD_REPOSITORY,
            "missing_information": ["which compatibility guarantee to keep"],
        },
    )
    completion = complete_intake_from_semantic_outcome(outcome)

    decision = route_execution_workflow(outcome.contract, completion.decision)

    assert completion.state == STATE_GOAL_BRIEF_ASSIST
    assert decision.status == STATUS_NOT_HANDOFF_READY
    assert decision.task_shape is None


def test_case_o_a_semantic_system_failure_is_not_routed():
    outcome = understand_request_semantically(
        "Explain the Bellman equation.",
        adapter=SemanticWaiterModelAdapter(_DeadSemanticClient()),
    )
    completion = complete_intake_from_semantic_outcome(outcome)

    decision = route_execution_workflow(outcome.contract, completion.decision)

    assert completion.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert outcome.contract is None
    assert decision.status == STATUS_NOT_HANDOFF_READY
    assert decision.recommended_workflow is None
    assert decision.receipt.source_contract_fingerprint is None


def test_a_blocked_handoff_is_never_reinterpreted_to_rescue_it():
    """No shape, no capabilities, no second reading of the prompt."""
    contract = understand_request(DOGFOOD_PROMPT)
    outcome = complete_intake(contract)

    decision = route_execution_workflow(contract, outcome.decision)

    assert decision.status == STATUS_NOT_HANDOFF_READY
    assert decision.task_shape is None
    assert decision.capability_requirements is None
    assert decision.reasons == (ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY,)


# ══ P–Q — policy runs over structured semantics, not language ═════════════════

def test_case_p_vietnamese_explanation_routes_to_chat():
    decision = _route(
        "Giải thích phương trình Bellman.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )

    assert decision.recommended_workflow == WORKFLOW_CHAT
    assert decision.task_shape.task_family == FAMILY_EXPLANATORY


def test_case_q_vietnamese_broad_repository_analysis_routes_to_commander():
    decision = _route(
        "Phân tích toàn bộ kiến trúc lập chỉ mục trong core/indexer.py và graph/builder.py.",
        {
            "task": {"type": "analysis", "provenance": "inferred"},
            "subjects": [
                {"value": "core/indexer.py", "provenance": "explicit"},
                {"value": "graph/builder.py", "provenance": "explicit"},
            ],
            "execution_requirements": BROAD_REPOSITORY,
        },
    )

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert decision.requires(CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE) is True


def test_english_and_vietnamese_explanations_route_identically():
    english = _route(
        "Explain the Bellman equation.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )
    vietnamese = _route(
        "Giải thích phương trình Bellman.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )

    assert english.task_shape.as_dict() == vietnamese.task_shape.as_dict()
    assert english.recommended_workflow == vietnamese.recommended_workflow


# ══ R — external information is preserved, never acted on ═════════════════════

def test_case_r_an_external_lookup_with_no_repository_work_routes_to_chat():
    decision = _route(
        "What is the current stable release of Python?",
        {
            "task": {"type": "question", "provenance": "inferred"},
            "execution_requirements": {"external_information_required": True},
        },
    )

    assert decision.recommended_workflow == WORKFLOW_CHAT
    assert decision.reasons == (ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY,)
    assert decision.requires(CAPABILITY_EXTERNAL_INFORMATION) is True
    assert decision.task_shape.evidence_scope == EVIDENCE_EXTERNAL_INFORMATION


def test_repository_plus_external_information_needs_cross_source_synthesis():
    decision = _route(
        "Compare our retry policy in core/executor.py against the current published "
        "guidance for exponential backoff.",
        {
            "task": {"type": "comparative_analysis", "provenance": "inferred"},
            "subjects": [
                {"value": "our retry policy in core/executor.py", "provenance": "explicit"},
                {
                    "value": "current published guidance for exponential backoff",
                    "provenance": "explicit",
                },
            ],
            "relationships": [
                {
                    "type": "comparison",
                    "subjects": [
                        "our retry policy in core/executor.py",
                        "current published guidance for exponential backoff",
                    ],
                    "provenance": "explicit",
                }
            ],
            "execution_requirements": {
                "repository_inspection_required": True,
                "local_repository_required": True,
                "external_information_required": True,
            },
        },
    )

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS in decision.reasons
    assert decision.task_shape.evidence_scope == EVIDENCE_MIXED_SOURCES
    assert decision.requires(CAPABILITY_CROSS_SOURCE_SYNTHESIS) is True


def test_external_information_is_a_requirement_and_nothing_was_searched():
    decision = _route(
        "What is the current stable release of Python?",
        {
            "task": {"type": "question", "provenance": "inferred"},
            "execution_requirements": {"external_information_required": True},
        },
    )
    guardrails = decision.as_dict()["guardrails"]

    assert decision.requires(CAPABILITY_EXTERNAL_INFORMATION) is True
    assert guardrails["web_search_performed"] is False
    assert guardrails["network_call_performed"] is False


# ══ Task-shape sensitivity ════════════════════════════════════════════════════

def test_the_word_compare_does_not_decide_a_route():
    """Four orders that all compare something, routed by what they require."""
    supplied = _route(DOGFOOD_PROMPT, _dogfood_interpretation({}))
    inspected = _dogfood_decision()
    bounded_change = _route(
        "Based on that comparison, change the retry limit in config.py to 5.",
        {
            "task": {"type": "implementation", "provenance": "inferred"},
            "subjects": [
                {"value": "config.py", "provenance": "explicit"},
                {"value": "retry limit", "provenance": "inferred", "confidence": 0.8},
            ],
            "relationships": [
                {
                    "type": "comparison",
                    "subjects": ["config.py", "retry limit"],
                    "provenance": "inferred",
                    "confidence": 0.6,
                }
            ],
            "execution_requirements": BOUNDED_REPOSITORY,
        },
    )
    evolving = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=_EVOLUTION_DECLARATION,
    )

    assert supplied.recommended_workflow == WORKFLOW_CHAT
    assert inspected.recommended_workflow == WORKFLOW_COMMANDER
    assert bounded_change.recommended_workflow == WORKFLOW_INSTANT_RUN
    assert evolving.recommended_workflow == WORKFLOW_PROJECT_EVOLUTION

    assert bounded_change.requires(CAPABILITY_COMPARISON) is True


def test_the_same_family_routes_differently_by_evidence_scope():
    bounded = _route(
        "Fix the typo 'teh' to 'the' in README.md.",
        {
            "task": {"type": "implementation", "provenance": "inferred"},
            "subjects": [{"value": "README.md", "provenance": "explicit"}],
            "execution_requirements": BOUNDED_REPOSITORY,
        },
    )
    broad = _route(_BROAD_MIGRATION, _BROAD_MIGRATION_INTERPRETATION)

    assert bounded.task_shape.task_family == broad.task_shape.task_family
    assert bounded.recommended_workflow == WORKFLOW_INSTANT_RUN
    assert broad.recommended_workflow == WORKFLOW_COMMANDER


# ══ Model and provider separation ═════════════════════════════════════════════

_COMPUTE_TOKENS: tuple[str, ...] = (
    "gemini",
    "gemma",
    "qwen",
    "claude",
    "gpt",
    "ollama",
    "cloud",
    "local model",
    "stronger model",
    "bigger model",
    "smaller model",
    "model_size",
    "num_ctx",
    "temperature",
    "api key",
    "endpoint",
    "fallback chain",
)


@pytest.mark.parametrize(
    "prompt, payload, extra",
    [
        ("Explain the Bellman equation.", {"task": {"type": "question", "provenance": "inferred"}}, {}),
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY), {}),
        (
            "Fix the typo 'teh' to 'the' in README.md.",
            {
                "task": {"type": "implementation", "provenance": "inferred"},
                "subjects": [{"value": "README.md", "provenance": "explicit"}],
                "execution_requirements": BOUNDED_REPOSITORY,
            },
            {},
        ),
        (
            _EVOLUTION_PROMPT,
            _EVOLUTION_INTERPRETATION,
            {"project_evolution_request": _EVOLUTION_DECLARATION},
        ),
    ],
)
def test_no_route_names_a_model_a_provider_or_a_budget(prompt, payload, extra):
    """The authority block names these powers to deny them; nothing else may."""
    decision = _route(prompt, payload, **extra)
    rendered = json.dumps(_without_authority(decision.as_dict()), ensure_ascii=False).lower()

    for token in _COMPUTE_TOKENS:
        assert token not in rendered, token


def test_a_commander_route_does_not_ask_for_more_compute():
    decision = _dogfood_decision()
    rendered = render_waiter_decision_json(decision).lower()
    without_denials = json.dumps(
        _without_authority(decision.as_dict()), ensure_ascii=False
    ).lower()

    assert "commander" in rendered
    for token in ("escalat", "stronger", "bigger", "provider_name", "model_id"):
        assert token not in without_denials, token


def test_no_waiter_module_can_reach_a_file_a_process_or_a_network():
    """A static proof, so the boundary cannot be lost to a future refactor."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "core"
    for name in (
        "task_shape.py",
        "capability_requirements.py",
        "execution_waiter.py",
        "waiter_receipt.py",
    ):
        source = (root / name).read_text(encoding="utf-8")
        for forbidden in (
            "import os",
            "import subprocess",
            "import socket",
            "import requests",
            "import urllib",
            "from pathlib",
            "import pathlib",
            "open(",
        ):
            assert forbidden not in source, f"{name}: {forbidden}"


# ══ Authority, determinism and shape invariants ═══════════════════════════════

@pytest.mark.parametrize("workflow", list(WORKFLOW_TARGETS))
def test_every_workflow_target_is_authority_free(workflow):
    authority = waiter_authority()

    assert workflow in WORKFLOW_TARGETS
    assert authority["human_approval_required"] is True
    for name, value in authority.items():
        if name == "human_approval_required":
            continue
        assert value is False, name


def test_routing_is_deterministic_across_repeated_runs():
    first = canonical_waiter_fingerprint(_dogfood_decision())
    second = canonical_waiter_fingerprint(_dogfood_decision())

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_the_decision_fingerprints_the_exact_input_it_consumed():
    contract, decision = _handoff(
        DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)
    )
    routed = route_execution_workflow(contract, decision)

    assert routed.receipt.source_raw_request_sha256 == contract.raw_request.sha256
    assert len(routed.receipt.source_contract_fingerprint) == 64
    assert len(routed.receipt.source_completion_fingerprint) == 64


def test_a_rendered_decision_is_stable_json():
    rendered = render_waiter_decision_json(_dogfood_decision())

    assert json.loads(rendered)["recommended_workflow"] == WORKFLOW_COMMANDER
    assert rendered == render_waiter_decision_json(_dogfood_decision())


def test_mixed_mode_and_goal_brief_are_not_workflow_targets():
    assert "mixed_mode" not in WORKFLOW_TARGETS
    assert "goal_brief" not in WORKFLOW_TARGETS
    assert set(WORKFLOW_TARGETS) == {
        WORKFLOW_CHAT,
        WORKFLOW_INSTANT_RUN,
        WORKFLOW_COMMANDER,
        WORKFLOW_PROJECT_EVOLUTION,
    }


def test_every_reason_code_has_a_description():
    assert set(ROUTE_REASON_DESCRIPTIONS) == set(ROUTE_REASONS)
    for text in ROUTE_REASON_DESCRIPTIONS.values():
        assert text.strip()


def test_reason_descriptions_carry_no_score():
    joined = " ".join(ROUTE_REASON_DESCRIPTIONS.values()).lower()

    for token in ("score", "probability", "confidence", "%"):
        assert token not in joined, token


# ══ Unit-level guards on the derivations ══════════════════════════════════════

def test_capability_requirements_are_total_and_ordered():
    contract, _ = _handoff(
        "Explain the Bellman equation.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )
    capabilities = derive_capability_requirements(derive_task_shape(contract), contract)

    assert tuple(item.name for item in capabilities.requirements) == CAPABILITY_NAMES


def test_a_required_capability_must_name_the_fact_it_came_from():
    with pytest.raises(ValueError):
        CapabilityRequirement(name=CAPABILITY_REPOSITORY_READ, value=True, reasons=())


def test_an_unrequired_capability_may_not_carry_reasons():
    with pytest.raises(ValueError):
        CapabilityRequirement(
            name=CAPABILITY_REPOSITORY_READ,
            value=False,
            reasons=("task_shape.evidence_scope=none",),
        )


def test_a_capability_reason_must_come_from_the_bounded_vocabulary():
    with pytest.raises(ValueError):
        CapabilityRequirement(
            name=CAPABILITY_REPOSITORY_READ,
            value=True,
            reasons=("the user explicitly requested repository traversal",),
        )


def test_task_shape_refuses_project_evolution_without_a_declaration():
    from core.task_shape import TaskShape

    with pytest.raises(ValueError):
        TaskShape(
            task_family=FAMILY_PROJECT_EVOLUTION,
            interaction_shape=INTERACTION_MULTI_STAGE,
            evidence_scope=EVIDENCE_BROAD_REPOSITORY,
            change_shape=CHANGE_NONE,
            analysis_shape=ANALYSIS_SIMPLE,
            horizon=HORIZON_LONG_RUNNING,
            broad_repository_scope=True,
            explicit_project_evolution=False,
        )


def test_the_entry_gate_reports_every_blocker_it_found():
    contract = understand_request("Explain the Bellman equation.")
    outcome = complete_intake(contract)
    receipt = check_handoff_eligibility(contract, outcome.decision)

    assert receipt.handoff_verified is False
    assert GATE_SEMANTIC_RECEIPT_MISSING in receipt.gate_blockers
    assert receipt.as_dict()["authority"]["execution_authority"] is False


# ══ P — Project Evolution provenance hardening ════════════════════════════════
#
# Literal presence is necessary and not sufficient.  Three failures are pinned
# here that a literal substring check alone cannot see:
#
#   * a real span of the user's words carrying an externally invented label,
#   * a span the user wrote inside their own prohibition,
#   * a declaration made about some other request entirely.
#
# In every refusal the order still routes: an unauthorised Project Evolution
# claim disqualifies one workflow, it does not fail the request.

_TRUSTED_EVOLUTION_DECLARATION = _EVOLUTION_DECLARATION

#: A real refactor order that names Project Evolution only to forbid it.
_NEGATED_EVOLUTION_PROMPT = (
    "Do not use Project Evolution; just refactor this architecture across "
    "core/context_selection.py and core/context_search_runtime.py."
)

_NEGATED_EVOLUTION_INTERPRETATION = {
    "task": {"type": "implementation", "provenance": "inferred"},
    "subjects": [
        {"value": "core/context_selection.py", "provenance": "explicit"},
        {"value": "core/context_search_runtime.py", "provenance": "explicit"},
    ],
    "constraints": [
        {
            "kind": "prohibition",
            "text": (
                "Do not use Project Evolution; just refactor this architecture across "
                "core/context_selection.py and core/context_search_runtime.py"
            ),
            "provenance": "explicit",
        }
    ],
    "execution_requirements": BROAD_REPOSITORY,
}


# ── case 1: a trusted declaration is honoured ─────────────────────────────────

def test_provenance_case_1_a_trusted_declaration_reaches_project_evolution():
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=_TRUSTED_EVOLUTION_DECLARATION,
    )

    assert decision.recommended_workflow == WORKFLOW_PROJECT_EVOLUTION
    assert decision.task_shape.explicit_project_evolution is True
    assert decision.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT) is True
    assert not [
        item
        for item in decision.disqualifiers
        if item in PROJECT_EVOLUTION_DISQUALIFIERS
    ]


def test_provenance_case_1_explicit_input_evidence_is_equally_trusted():
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=dataclasses.replace(
            _TRUSTED_EVOLUTION_DECLARATION,
            declared_by=DECLARATION_SOURCE_EXPLICIT_INPUT_EVIDENCE,
        ),
    )

    assert decision.recommended_workflow == WORKFLOW_PROJECT_EVOLUTION


# ── case 2: an inference-sourced declaration is never honoured ────────────────

@pytest.mark.parametrize("source", UNTRUSTED_DECLARATION_SOURCES)
def test_provenance_case_2_an_inferred_declaration_never_reaches_project_evolution(source):
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=dataclasses.replace(
            _TRUSTED_EVOLUTION_DECLARATION, declared_by=source
        ),
    )

    assert decision.recommended_workflow != WORKFLOW_PROJECT_EVOLUTION
    assert decision.task_shape.explicit_project_evolution is False
    assert decision.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT) is False
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED
        in decision.disqualifiers
    )


def test_provenance_case_2_an_inferred_declaration_still_routes_the_order():
    """Fail closed on the claim, not on the request."""
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=dataclasses.replace(
            _TRUSTED_EVOLUTION_DECLARATION, declared_by="waiter_inference"
        ),
    )

    assert decision.status == STATUS_ROUTED
    assert decision.recommended_workflow == WORKFLOW_COMMANDER


# ── case 3: real words, invented label ────────────────────────────────────────

def test_provenance_case_3_a_prohibited_mention_may_not_declare_project_evolution():
    decision = _route(
        _NEGATED_EVOLUTION_PROMPT,
        _NEGATED_EVOLUTION_INTERPRETATION,
        project_evolution_request=ProjectEvolutionRequest(
            evidence_text="Project Evolution",
            declared_by=DECLARATION_SOURCE_EXPLICIT_INPUT_EVIDENCE,
            source_raw_request_sha256=_request_fingerprint(_NEGATED_EVOLUTION_PROMPT),
        ),
    )

    assert decision.recommended_workflow != WORKFLOW_PROJECT_EVOLUTION
    assert decision.task_shape.explicit_project_evolution is False
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NEGATED in decision.disqualifiers
    )


def test_provenance_case_3_the_refactor_order_itself_still_routes():
    decision = _route(
        _NEGATED_EVOLUTION_PROMPT,
        _NEGATED_EVOLUTION_INTERPRETATION,
        project_evolution_request=ProjectEvolutionRequest(
            evidence_text="Project Evolution",
            declared_by=DECLARATION_SOURCE_EXPLICIT_INPUT_EVIDENCE,
            source_raw_request_sha256=_request_fingerprint(_NEGATED_EVOLUTION_PROMPT),
        ),
    )

    assert decision.status == STATUS_ROUTED
    assert decision.recommended_workflow == WORKFLOW_COMMANDER


def test_provenance_a_later_prohibition_does_not_negate_an_earlier_declaration():
    """The user's own scope, read literally: a prohibition binds what follows it."""
    prompt = (
        "Continue evolving this project through the roadmap phases in "
        "docs/roadmap/phase_registry.json, but do not touch database/schema.py."
    )
    decision = _route(
        prompt,
        {
            "task": {"type": "planning", "provenance": "inferred"},
            "subjects": [
                {"value": "docs/roadmap/phase_registry.json", "provenance": "explicit"},
                {"value": "database/schema.py", "provenance": "explicit"},
            ],
            "constraints": [
                {
                    "kind": "prohibition",
                    "text": (
                        "Continue evolving this project through the roadmap phases in "
                        "docs/roadmap/phase_registry.json, but do not touch "
                        "database/schema.py"
                    ),
                    "provenance": "explicit",
                }
            ],
            "execution_requirements": BROAD_REPOSITORY,
        },
        project_evolution_request=ProjectEvolutionRequest(
            evidence_text="Continue evolving this project through the roadmap phases",
            declared_by=DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
            source_raw_request_sha256=_request_fingerprint(prompt),
        ),
    )

    assert decision.recommended_workflow == WORKFLOW_PROJECT_EVOLUTION


# ── case 4: an invented declaration over a silent request ─────────────────────

def test_provenance_case_4_an_invented_declaration_is_refused():
    prompt = (
        "Refactor the retry handling in core/retriever.py and core/executor.py so "
        "both share one backoff policy."
    )
    decision = _route(
        prompt,
        {
            "task": {"type": "implementation", "provenance": "inferred"},
            "subjects": [
                {"value": "core/retriever.py", "provenance": "explicit"},
                {"value": "core/executor.py", "provenance": "explicit"},
            ],
            "execution_requirements": BROAD_REPOSITORY,
        },
        project_evolution_request=ProjectEvolutionRequest(
            evidence_text="continue the project evolution lifecycle",
            declared_by=DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
            source_raw_request_sha256=_request_fingerprint(prompt),
        ),
    )

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED
        in decision.disqualifiers
    )


# ── cases 5 and 6: size and persistence are not authority ─────────────────────

def test_provenance_case_5_a_large_architecture_refactor_is_commander():
    decision = _route(_BROAD_MIGRATION, _BROAD_MIGRATION_INTERPRETATION)

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert decision.task_shape.explicit_project_evolution is False


def test_provenance_case_6_a_persistent_multi_stage_order_is_commander():
    decision = _route(_EVOLUTION_PROMPT, _EVOLUTION_INTERPRETATION)

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert decision.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT) is False
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED in decision.disqualifiers
    )


# ── the declaration must be bound to the request it was read from ────────────

def test_provenance_a_declaration_bound_to_another_request_is_refused():
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=dataclasses.replace(
            _TRUSTED_EVOLUTION_DECLARATION,
            source_raw_request_sha256=_request_fingerprint("some other request"),
        ),
    )

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED in decision.disqualifiers
    )


def test_provenance_a_declaration_bound_to_no_request_is_refused():
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=ProjectEvolutionRequest(
            evidence_text="Continue evolving this project through the roadmap phases",
            declared_by=DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
        ),
    )

    assert decision.recommended_workflow == WORKFLOW_COMMANDER
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED in decision.disqualifiers
    )


# ── the vocabulary itself ─────────────────────────────────────────────────────

def test_provenance_the_trusted_source_vocabulary_is_bounded():
    assert TRUSTED_DECLARATION_SOURCES == (
        DECLARATION_SOURCE_EXPLICIT_INPUT_EVIDENCE,
        DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
    )
    for rejected in (
        "inferred",
        "waiter_inference",
        "model_inference",
        "task_shape_inference",
        "task_complexity",
        "repository_scope",
    ):
        assert rejected in UNTRUSTED_DECLARATION_SOURCES
        assert rejected not in TRUSTED_DECLARATION_SOURCES


def test_provenance_a_source_outside_the_vocabulary_is_a_construction_error():
    with pytest.raises(ValueError):
        ProjectEvolutionRequest(
            evidence_text="Continue evolving this project through the roadmap phases",
            declared_by="because_the_task_looked_big",
        )


def test_provenance_every_project_evolution_disqualifier_is_a_waiter_disqualifier():
    for code in PROJECT_EVOLUTION_DISQUALIFIERS:
        assert code in WAITER_DISQUALIFIERS


def test_provenance_a_refused_declaration_is_reported_not_hidden():
    decision = _route(
        _EVOLUTION_PROMPT,
        _EVOLUTION_INTERPRETATION,
        project_evolution_request=dataclasses.replace(
            _TRUSTED_EVOLUTION_DECLARATION, declared_by="model_inference"
        ),
    )
    rendered = json.loads(render_waiter_decision_json(decision))

    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED
        in rendered["disqualifiers"]
    )


# ── the check itself, exercised directly ──────────────────────────────────────

def test_provenance_check_reports_every_reason_a_declaration_failed():
    contract, _ = _handoff(_EVOLUTION_PROMPT, _EVOLUTION_INTERPRETATION)
    verification = check_project_evolution_request(
        contract,
        ProjectEvolutionRequest(
            evidence_text="run the ongoing evolution process forever",
            declared_by="waiter_inference",
        ),
    )

    assert verification.verified is False
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED
        in verification.disqualifiers
    )
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED
        in verification.disqualifiers
    )
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED
        in verification.disqualifiers
    )


def test_provenance_an_absent_declaration_is_not_an_error():
    contract, _ = _handoff(_EVOLUTION_PROMPT, _EVOLUTION_INTERPRETATION)
    verification = check_project_evolution_request(contract, None)

    assert verification.verified is False
    assert (
        DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED
        in verification.disqualifiers
    )


def test_provenance_verification_is_deterministic():
    first = _route(
        _NEGATED_EVOLUTION_PROMPT,
        _NEGATED_EVOLUTION_INTERPRETATION,
        project_evolution_request=ProjectEvolutionRequest(
            evidence_text="Project Evolution",
            source_raw_request_sha256=_request_fingerprint(_NEGATED_EVOLUTION_PROMPT),
        ),
    )
    second = _route(
        _NEGATED_EVOLUTION_PROMPT,
        _NEGATED_EVOLUTION_INTERPRETATION,
        project_evolution_request=ProjectEvolutionRequest(
            evidence_text="Project Evolution",
            source_raw_request_sha256=_request_fingerprint(_NEGATED_EVOLUTION_PROMPT),
        ),
    )

    assert canonical_waiter_fingerprint(first) == canonical_waiter_fingerprint(second)
